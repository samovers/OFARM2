"""Closed lifecycle for one dual-approved temporary audit export LOGIN.

The production surface owns authority time, first-use consumption, one fixed
temporary PostgreSQL credential, one existing bounded export call, and exact
credential closure before a page can cross this module boundary.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol, cast
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from deployment.postgresql.catalog_identity import verify_catalog_identity
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    MigrationService,
)
from deployment.postgresql.security_audit_approval import (
    SecurityAuditApprovalRefused,
    SecurityAuditDualApprovalVerifier,
    _VerifiedSecurityAuditApproval,
)
from deployment.postgresql.security_audit_export import (
    AcknowledgedSecurityAuditExport,
    SecurityAuditExportRunner,
)


TEMPORARY_EXPORT_LOGIN = "ofarm_security_audit_export_login"
TEMPORARY_EXPORT_CAPABILITY = "ofarm_security_audit_export"
SECURITY_AUDIT_DATABASE = "ofarm_security_audit"
BREAK_GLASS_CONNECT_TIMEOUT_SECONDS = 5
BREAK_GLASS_CONNECTION_OPTIONS = (
    "-c statement_timeout=5000 "
    "-c lock_timeout=500 "
    "-c idle_in_transaction_session_timeout=10000 "
    "-c transaction_timeout=15000 "
    "-c work_mem=1024kB "
    "-c TimeZone=UTC "
    "-c DateStyle=ISO,MDY "
    "-c synchronous_commit=on"
)
CONSUME_TEMPORARY_EXPORT_APPROVAL_SQL = (
    "SELECT ofarm_security.consume_temporary_export_approval("
    "%s, %s, %s, %s, %s)"
)

_MAX_CARRIER_BYTES = 16_384
_MAX_DSN_BYTES = 8_192
_MAX_UNIX_MICROSECONDS = 9_223_372_036_854_775_807
_MAX_AUTHORITY_DATABASE_DIVERGENCE_GROWTH_US = 1_000_000
_MAX_PASSWORD_AUTHORITY_ADVANCE_US = 61_000_000
_POSTGRES_TIMESTAMP_QUANTUM_US = 1
_PASSWORD_BYTES = 48
_SCRAM_SALT_BYTES = 16
_SCRAM_ITERATIONS = 4_096
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_SCRAM = re.compile(
    r"SCRAM-SHA-256\$4096:[A-Za-z0-9+/]+={0,2}\$"
    r"[A-Za-z0-9+/]+={0,2}:[A-Za-z0-9+/]+={0,2}"
)
_ROLE_SETTINGS = (
    ("idle_in_transaction_session_timeout", "10000"),
    ("jit", "off"),
    ("lock_timeout", "500"),
    ("max_parallel_workers_per_gather", "0"),
    ("row_security", "on"),
    ("search_path", "pg_catalog"),
    ("statement_timeout", "5000"),
    ("synchronous_commit", "on"),
    ("temp_file_limit", "0"),
    ("transaction_timeout", "15000"),
    ("work_mem", "1024"),
)
_EXPECTED_SETTING_ROWS = frozenset(
    (SECURITY_AUDIT_DATABASE, f"{name}={value}")
    for name, value in _ROLE_SETTINGS
)
_EXPECTED_MEMBERSHIP_ROWS = (
    (
        TEMPORARY_EXPORT_CAPABILITY,
        TEMPORARY_EXPORT_LOGIN,
        True,
        False,
        False,
    ),
)

_ADMIN_IDENTITY_SQL = """
SELECT session_user::pg_catalog.text,
       current_user::pg_catalog.text,
       pg_catalog.current_database()::pg_catalog.text,
       role.rolsuper,
       pg_catalog.pg_is_in_recovery(),
       pg_catalog.current_setting('transaction_read_only'),
       control.system_identifier::pg_catalog.text
FROM pg_catalog.pg_roles AS role
CROSS JOIN pg_catalog.pg_control_system() AS control
WHERE role.rolname = session_user
"""
_CONTROL_IDENTITY_SQL = """
SELECT session_user::pg_catalog.text,
       current_user::pg_catalog.text,
       pg_catalog.current_database()::pg_catalog.text,
       pg_catalog.pg_is_in_recovery(),
       pg_catalog.current_setting('transaction_read_only')
"""
_STORE_ID_SQL = """
SELECT execution_id
FROM ofarm_security.schema_migration
WHERE version = 1
  AND filename = '0001_initial.sql'
  AND service_identity = 'ofarm.security-audit-postgresql.v1'
"""
_CLOCK_SQL = """
SELECT high_water_microseconds, clock_regressed
FROM ofarm_security._observe_nonregressing_access_clock()
"""
_STRUCTURE_SQL = (
    "SELECT * FROM ofarm_security.verify_security_audit_structure()"
)
_ROLE_SQL = """
SELECT role.rolsuper,
       role.rolinherit,
       role.rolcreaterole,
       role.rolcreatedb,
       role.rolcanlogin,
       role.rolreplication,
       role.rolconnlimit,
       role.rolvaliduntil,
       role.rolbypassrls,
       role.rolconfig,
       authentication.rolpassword
FROM pg_catalog.pg_roles AS role
JOIN pg_catalog.pg_authid AS authentication ON authentication.oid = role.oid
WHERE role.rolname = 'ofarm_security_audit_export_login'
"""
_ROLE_SETTINGS_SQL = """
SELECT COALESCE(database.datname::pg_catalog.text, '*'), setting.value
FROM pg_catalog.pg_db_role_setting AS configured
JOIN pg_catalog.pg_roles AS role ON role.oid = configured.setrole
LEFT JOIN pg_catalog.pg_database AS database
  ON database.oid = configured.setdatabase
CROSS JOIN LATERAL pg_catalog.unnest(configured.setconfig) AS setting(value)
WHERE role.rolname = 'ofarm_security_audit_export_login'
ORDER BY 1, 2
"""
_ROLE_MEMBERSHIPS_SQL = """
SELECT granted.rolname::pg_catalog.text,
       member.rolname::pg_catalog.text,
       membership.inherit_option,
       membership.set_option,
       membership.admin_option
FROM pg_catalog.pg_auth_members AS membership
JOIN pg_catalog.pg_roles AS granted ON granted.oid = membership.roleid
JOIN pg_catalog.pg_roles AS member ON member.oid = membership.member
WHERE granted.rolname = 'ofarm_security_audit_export_login'
   OR member.rolname = 'ofarm_security_audit_export_login'
ORDER BY 1, 2
"""
_TERMINATE_SQL = """
SELECT pg_catalog.pg_terminate_backend(activity.pid)
FROM pg_catalog.pg_stat_activity AS activity
WHERE activity.usename = 'ofarm_security_audit_export_login'
  AND activity.pid <> pg_catalog.pg_backend_pid()
ORDER BY activity.pid
"""
_SESSION_COUNT_SQL = """
SELECT pg_catalog.count(*)
FROM pg_catalog.pg_stat_activity AS activity
WHERE activity.usename = 'ofarm_security_audit_export_login'
  AND activity.pid <> pg_catalog.pg_backend_pid()
"""


class SecurityAuditBreakGlassError(RuntimeError):
    """Base class for fixed temporary-export lifecycle outcomes."""


class SecurityAuditBreakGlassRefused(SecurityAuditBreakGlassError):
    """The lifecycle refused before an acknowledged approval consumption."""


class SecurityAuditBreakGlassOutcomeUnknown(SecurityAuditBreakGlassError):
    """The approval-consumption commit outcome is unknown and not retryable."""


class SecurityAuditBreakGlassFailed(SecurityAuditBreakGlassError):
    """The approval was spent but no closed page is available."""


class SecurityAuditBreakGlassQuarantined(SecurityAuditBreakGlassError):
    """The fixed temporary role or final structure could not be closed."""


@dataclass(frozen=True, slots=True, repr=False)
class SecurityAuditBreakGlassSecrets:
    """Trusted routes whose values are never included in public outcomes."""

    admin_dsn: str
    control_dsn: str


@dataclass(frozen=True, slots=True, repr=False)
class _ClosedSecurityAuditBreakGlassExport:
    """One buffered page released only after complete credential closure."""

    operation_id: UUID
    page_bytes: bytes


@dataclass(frozen=True, slots=True)
class _Routes:
    admin: str
    control: str


@dataclass(frozen=True, slots=True)
class _Preflight:
    routes: _Routes
    store_migration_execution_id: UUID
    database_high_water_us: int


@dataclass(frozen=True, slots=True)
class _ExpectedRole:
    valid_until: datetime | None
    password_verifier: str | None


@dataclass(frozen=True, slots=True)
class _CurrentApprovalCarrier:
    approval: _VerifiedSecurityAuditApproval
    authority_now_us: int


@dataclass(frozen=True, slots=True)
class _LoginCreationOutcome:
    expected_role: _ExpectedRole
    commit_acknowledged: bool


class _Cursor(Protocol):
    def fetchone(self) -> object: ...

    def fetchall(self) -> object: ...


class _ConnectionInfo(Protocol):
    @property
    def transaction_status(self) -> TransactionStatus: ...


class _Connection(Protocol):
    closed: bool
    autocommit: bool

    @property
    def info(self) -> _ConnectionInfo: ...

    def execute(
        self,
        query: object,
        parameters: tuple[object, ...] | None = None,
    ) -> _Cursor: ...

    def rollback(self) -> None: ...

    def commit(self) -> None: ...

    def close(self) -> None: ...


class _ConnectionFactory(Protocol):
    def __call__(
        self,
        conninfo: str,
        *,
        autocommit: bool,
        connect_timeout: int,
        options: str,
    ) -> _Connection: ...


class _TimeNs(Protocol):
    def __call__(self) -> int: ...


class _RandomBytes(Protocol):
    def __call__(self, length: int) -> bytes: ...


class _ApprovalVerifier(Protocol):
    def verify(
        self,
        authority_receipt_bytes: bytes,
        approval_bundle_bytes: bytes,
        *,
        now_us: int,
    ) -> _VerifiedSecurityAuditApproval: ...


class _ExportRunner(Protocol):
    def run(
        self,
        control_conninfo: str,
        export_conninfo: str,
        cursor: object,
    ) -> AcknowledgedSecurityAuditExport: ...


class _CatalogVerifier(Protocol):
    def __call__(
        self,
        connection: _Connection,
        service: MigrationService,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class _Dependencies:
    connection_factory: _ConnectionFactory
    time_ns: _TimeNs
    random_bytes: _RandomBytes
    approval_verifier: _ApprovalVerifier
    export_runner: _ExportRunner
    catalog_verifier: _CatalogVerifier


class _Refusal(RuntimeError):
    pass


class _ConsumptionUnknown(RuntimeError):
    pass


class _ConsumedFailure(RuntimeError):
    pass


class _Quarantine(RuntimeError):
    pass


def _exact_row(cursor: _Cursor, length: int) -> tuple[object, ...]:
    row = cursor.fetchone()
    second = cursor.fetchone()
    if type(row) is not tuple or len(row) != length or second is not None:
        raise ValueError
    return row


def _rollback_suppressed(connection: _Connection | None) -> None:
    if connection is None:
        return
    try:
        connection.rollback()
    except Exception:
        pass


def _close_suppressed(connection: _Connection | None) -> None:
    if connection is None:
        return
    try:
        connection.close()
    except Exception:
        pass


def _validated_route(value: object) -> str:
    if (
        type(value) is not str
        or not value.strip()
        or len(value.encode("utf-8")) > _MAX_DSN_BYTES
    ):
        raise ValueError
    parameters = psycopg.conninfo.conninfo_to_dict(value)
    parameters["dbname"] = SECURITY_AUDIT_DATABASE
    parameters.pop("options", None)
    parameters.pop("connect_timeout", None)
    return psycopg.conninfo.make_conninfo(**parameters)


def _validated_invocation(
    secret_carrier: object,
    authority_receipt_bytes: object,
    approval_bundle_bytes: object,
) -> tuple[_Routes, bytes, bytes]:
    if type(secret_carrier) is not SecurityAuditBreakGlassSecrets:
        raise ValueError
    if (
        type(authority_receipt_bytes) is not bytes
        or not authority_receipt_bytes
        or len(authority_receipt_bytes) > _MAX_CARRIER_BYTES
        or type(approval_bundle_bytes) is not bytes
        or not approval_bundle_bytes
        or len(approval_bundle_bytes) > _MAX_CARRIER_BYTES
    ):
        raise ValueError
    routes = _Routes(
        admin=_validated_route(secret_carrier.admin_dsn),
        control=_validated_route(secret_carrier.control_dsn),
    )
    return routes, authority_receipt_bytes, approval_bundle_bytes


def _open(connection_factory: _ConnectionFactory, route: str) -> _Connection:
    connection = connection_factory(
        route,
        autocommit=False,
        connect_timeout=BREAK_GLASS_CONNECT_TIMEOUT_SECONDS,
        options=BREAK_GLASS_CONNECTION_OPTIONS,
    )
    if (
        connection.closed is not False
        or connection.autocommit is not False
        or connection.info.transaction_status != TransactionStatus.IDLE
    ):
        raise ValueError
    return connection


def _require_admin(connection: _Connection) -> str:
    row = _exact_row(connection.execute(_ADMIN_IDENTITY_SQL), 7)
    if (
        any(type(row[index]) is not str for index in (0, 1, 2, 5, 6))
        or type(row[3]) is not bool
        or type(row[4]) is not bool
        or row[0] != row[1]
        or not row[0]
        or row[2] != SECURITY_AUDIT_DATABASE
        or row[3] is not True
        or row[4] is not False
        or row[5] != "off"
        or not row[6]
    ):
        raise ValueError
    return cast(str, row[6])


def _store_id(connection: _Connection) -> UUID:
    row = _exact_row(connection.execute(_STORE_ID_SQL), 1)
    if type(row[0]) is not UUID or row[0].int == 0:
        raise ValueError
    return cast(UUID, row[0])


def _clock_high_water(connection: _Connection) -> int:
    row = _exact_row(connection.execute(_CLOCK_SQL), 2)
    if (
        type(row[0]) is not int
        or not 0 <= row[0] <= _MAX_UNIX_MICROSECONDS
        or row[1] is not False
    ):
        raise ValueError
    return cast(int, row[0])


def _require_normal_structure(
    dependencies: _Dependencies,
    route: str,
    expected_store: UUID,
) -> None:
    connection = None
    try:
        connection = _open(dependencies.connection_factory, route)
        _require_admin(connection)
        if _store_id(connection) != expected_store:
            raise ValueError
        dependencies.catalog_verifier(connection, SECURITY_AUDIT_SERVICE)
        connection.execute("SET SESSION AUTHORIZATION ofarm_migrator")
        connection.execute("SET ROLE ofarm_security_audit_owner")
        if _exact_row(connection.execute(_STRUCTURE_SQL), 3) != (
            True,
            0,
            False,
        ):
            raise ValueError
        _rollback_suppressed(connection)
        connection.close()
        if connection.closed is not True:
            raise ValueError
        connection = None
    finally:
        _rollback_suppressed(connection)
        _close_suppressed(connection)


def _require_control_route(
    dependencies: _Dependencies,
    route: str,
) -> None:
    connection = None
    try:
        connection = _open(dependencies.connection_factory, route)
        row = _exact_row(connection.execute(_CONTROL_IDENTITY_SQL), 5)
        if row != (
            "ofarm_security_audit_control_login",
            "ofarm_security_audit_control_login",
            SECURITY_AUDIT_DATABASE,
            False,
            "off",
        ):
            raise ValueError
    finally:
        _rollback_suppressed(connection)
        _close_suppressed(connection)


def _preflight(dependencies: _Dependencies, routes: _Routes) -> _Preflight:
    connection = None
    try:
        connection = _open(dependencies.connection_factory, routes.admin)
        _require_admin(connection)
        store_id = _store_id(connection)
        high_water = _clock_high_water(connection)
    finally:
        _rollback_suppressed(connection)
        _close_suppressed(connection)
    _require_normal_structure(dependencies, routes.admin, store_id)
    _require_control_route(dependencies, routes.control)
    return _Preflight(routes, store_id, high_water)


def _authority_time_us(dependencies: _Dependencies) -> int:
    value = dependencies.time_ns()
    if (
        type(value) is not int
        or value < 0
        or value // 1_000 > _MAX_UNIX_MICROSECONDS
    ):
        raise ValueError
    return value // 1_000


def _advance_current_approval(
    dependencies: _Dependencies,
    current: _CurrentApprovalCarrier,
) -> _CurrentApprovalCarrier:
    authority_now_us = _authority_time_us(dependencies)
    if authority_now_us < current.authority_now_us:
        raise ValueError
    return _CurrentApprovalCarrier(current.approval, authority_now_us)


def _consume(
    dependencies: _Dependencies,
    route: str,
    current: _CurrentApprovalCarrier,
) -> None:
    approval = current.approval
    connection = None
    try:
        connection = _open(dependencies.connection_factory, route)
        row = _exact_row(
            connection.execute(
                CONSUME_TEMPORARY_EXPORT_APPROVAL_SQL,
                (
                    approval.operation_id,
                    approval.store_migration_execution_id,
                    approval.valid_from_us,
                    approval.valid_until_us,
                    current.authority_now_us,
                ),
            ),
            1,
        )
        if row != (True,):
            raise ValueError
    except Exception:
        _rollback_suppressed(connection)
        _close_suppressed(connection)
        raise _Refusal()
    try:
        connection.commit()
    except Exception:
        _close_suppressed(connection)
        raise _ConsumptionUnknown()
    _close_suppressed(connection)


def _password_material(dependencies: _Dependencies) -> tuple[str, str]:
    material = dependencies.random_bytes(_PASSWORD_BYTES + _SCRAM_SALT_BYTES)
    if type(material) is not bytes or len(material) != 64:
        raise ValueError
    password = base64.urlsafe_b64encode(
        material[:_PASSWORD_BYTES]
    ).rstrip(b"=").decode("ascii")
    salt = material[_PASSWORD_BYTES:]
    salted_password = hashlib.pbkdf2_hmac(
        "sha256", password.encode("ascii"), salt, _SCRAM_ITERATIONS
    )
    client_key = hmac.digest(salted_password, b"Client Key", "sha256")
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.digest(salted_password, b"Server Key", "sha256")
    verifier = (
        f"SCRAM-SHA-256${_SCRAM_ITERATIONS}:"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(stored_key).decode('ascii')}:"
        f"{base64.b64encode(server_key).decode('ascii')}"
    )
    return password, verifier


def _expiry(value_us: int) -> datetime:
    if type(value_us) is not int or not 0 <= value_us <= _MAX_UNIX_MICROSECONDS:
        raise ValueError
    return _EPOCH + timedelta(microseconds=value_us)


def _role_state(
    connection: _Connection,
    expected: _ExpectedRole,
    *,
    allow_disabled: bool,
) -> str:
    cursor = connection.execute(_ROLE_SQL)
    row = cursor.fetchone()
    if cursor.fetchone() is not None:
        raise ValueError
    if row is None:
        return "ABSENT"
    if type(row) is not tuple or len(row) != 11:
        return "DRIFTED"
    valid_until = row[7]
    password = row[10]
    can_login = row[4]
    fixed = (
        row[0] is False
        and row[1] is True
        and row[2] is False
        and row[3] is False
        and type(can_login) is bool
        and (can_login is True or allow_disabled and can_login is False)
        and row[5] is False
        and row[6] == 1
        and type(valid_until) is datetime
        and valid_until.utcoffset() == timedelta(0)
        and row[8] is False
        and row[9] is None
        and type(password) is str
        and _SCRAM.fullmatch(password) is not None
    )
    if expected.valid_until is not None:
        fixed = fixed and valid_until == expected.valid_until
    if expected.password_verifier is not None:
        fixed = fixed and password == expected.password_verifier
    settings = connection.execute(_ROLE_SETTINGS_SQL).fetchall()
    memberships = connection.execute(_ROLE_MEMBERSHIPS_SQL).fetchall()
    if (
        not fixed
        or type(settings) is not list
        or any(type(item) is not tuple or len(item) != 2 for item in settings)
        or frozenset(settings) != _EXPECTED_SETTING_ROWS
        or type(memberships) is not list
        or tuple(memberships) != _EXPECTED_MEMBERSHIP_ROWS
    ):
        return "DRIFTED"
    return "EXPECTED"


def _create_role_statement(
    valid_until: datetime,
    password_verifier: str,
) -> sql.Composed:
    return sql.SQL(
        "CREATE ROLE {} WITH LOGIN INHERIT NOBYPASSRLS NOSUPERUSER "
        "NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 1 "
        "VALID UNTIL {} PASSWORD {}"
    ).format(
        sql.Identifier(TEMPORARY_EXPORT_LOGIN),
        sql.Literal(valid_until.isoformat(timespec="microseconds")),
        sql.Literal(password_verifier),
    )


def _derived_expected_role(
    database_now_us: int,
    current: _CurrentApprovalCarrier,
    password_verifier: str,
) -> _ExpectedRole:
    safe_remaining_us = (
        current.approval.valid_until_us
        - max(current.authority_now_us, database_now_us)
        - _MAX_AUTHORITY_DATABASE_DIVERGENCE_GROWTH_US
        - _MAX_PASSWORD_AUTHORITY_ADVANCE_US
        - _POSTGRES_TIMESTAMP_QUANTUM_US
    )
    if safe_remaining_us <= 0:
        raise ValueError
    return _ExpectedRole(
        _expiry(database_now_us + safe_remaining_us),
        password_verifier,
    )


def _configure_login(
    connection: _Connection,
    expected_role: _ExpectedRole,
) -> None:
    connection.execute(
        _create_role_statement(
            cast(datetime, expected_role.valid_until),
            cast(str, expected_role.password_verifier),
        )
    )
    for name, value in _ROLE_SETTINGS:
        connection.execute(
            sql.SQL("ALTER ROLE {} IN DATABASE {} SET {} = {}").format(
                sql.Identifier(TEMPORARY_EXPORT_LOGIN),
                sql.Identifier(SECURITY_AUDIT_DATABASE),
                sql.Identifier(name),
                sql.Literal(value),
            )
        )
    grant = sql.SQL("GRANT {} TO {} WITH ").format(
        sql.Identifier(TEMPORARY_EXPORT_CAPABILITY),
        sql.Identifier(TEMPORARY_EXPORT_LOGIN),
    )
    for option, enabled in (
        ("ADMIN", False),
        ("INHERIT", True),
        ("SET", False),
    ):
        connection.execute(
            grant
            + sql.SQL("{} {}").format(
                sql.SQL(option),
                sql.SQL("TRUE" if enabled else "FALSE"),
            )
        )


def _create_login(
    dependencies: _Dependencies,
    route: str,
    expected_store: UUID,
    current: _CurrentApprovalCarrier,
    password_verifier: str,
) -> _LoginCreationOutcome:
    connection = None
    expected_role = None
    try:
        connection = _open(dependencies.connection_factory, route)
        _require_admin(connection)
        if _store_id(connection) != expected_store:
            raise ValueError
        if _role_state(
            connection, _ExpectedRole(None, None), allow_disabled=False
        ) != "ABSENT":
            raise ValueError
        database_now_us = _clock_high_water(connection)
        current = _advance_current_approval(dependencies, current)
        expected_role = _derived_expected_role(
            database_now_us,
            current,
            password_verifier,
        )
        _configure_login(connection, expected_role)
    except Exception:
        _rollback_suppressed(connection)
        _close_suppressed(connection)
        raise _ConsumedFailure()
    try:
        connection.commit()
    except Exception:
        _close_suppressed(connection)
        return _LoginCreationOutcome(cast(_ExpectedRole, expected_role), False)
    _close_suppressed(connection)
    return _LoginCreationOutcome(cast(_ExpectedRole, expected_role), True)


def _export_route(admin_route: str, password: str) -> str:
    parameters = psycopg.conninfo.conninfo_to_dict(admin_route)
    parameters["dbname"] = SECURITY_AUDIT_DATABASE
    parameters["user"] = TEMPORARY_EXPORT_LOGIN
    parameters["password"] = password
    parameters.pop("options", None)
    parameters.pop("connect_timeout", None)
    return psycopg.conninfo.make_conninfo(**parameters)


def _lock_disabled_role(
    connection: _Connection,
    expected_role: _ExpectedRole,
) -> None:
    connection.execute(
        sql.SQL("ALTER ROLE {} NOLOGIN").format(
            sql.Identifier(TEMPORARY_EXPORT_LOGIN)
        )
    )
    if _role_state(
        connection, expected_role, allow_disabled=True
    ) != "EXPECTED":
        raise ValueError


def _disable_login(
    dependencies: _Dependencies,
    route: str,
    expected_store: UUID,
    expected_role: _ExpectedRole,
) -> None:
    connection = None
    try:
        connection = _open(dependencies.connection_factory, route)
        _require_admin(connection)
        if _store_id(connection) != expected_store:
            raise ValueError
        _lock_disabled_role(connection, expected_role)
        connection.commit()
    finally:
        _close_suppressed(connection)


def _terminate_sessions(
    dependencies: _Dependencies,
    route: str,
    expected_store: UUID,
    expected_role: _ExpectedRole,
) -> None:
    connection = None
    try:
        connection = _open(dependencies.connection_factory, route)
        _require_admin(connection)
        if _store_id(connection) != expected_store:
            raise ValueError
        _lock_disabled_role(connection, expected_role)
        rows = connection.execute(_TERMINATE_SQL).fetchall()
        if type(rows) is not list or any(row != (True,) for row in rows):
            raise ValueError
        if _exact_row(connection.execute(_SESSION_COUNT_SQL), 1) != (0,):
            raise ValueError
        connection.commit()
    finally:
        _close_suppressed(connection)


def _drop_login(
    dependencies: _Dependencies,
    route: str,
    expected_store: UUID,
    expected_role: _ExpectedRole,
) -> None:
    connection = None
    try:
        connection = _open(dependencies.connection_factory, route)
        _require_admin(connection)
        if _store_id(connection) != expected_store:
            raise ValueError
        _lock_disabled_role(connection, expected_role)
        connection.execute(
            sql.SQL("REVOKE {} FROM {}").format(
                sql.Identifier(TEMPORARY_EXPORT_CAPABILITY),
                sql.Identifier(TEMPORARY_EXPORT_LOGIN),
            )
        )
        connection.execute(
            sql.SQL("DROP ROLE {}").format(
                sql.Identifier(TEMPORARY_EXPORT_LOGIN)
            )
        )
        connection.commit()
    finally:
        _close_suppressed(connection)


def _close_login(
    dependencies: _Dependencies,
    route: str,
    expected_store: UUID,
    expected_role: _ExpectedRole,
) -> None:
    failed = False
    try:
        _disable_login(dependencies, route, expected_store, expected_role)
        _terminate_sessions(
            dependencies, route, expected_store, expected_role
        )
        _drop_login(dependencies, route, expected_store, expected_role)
        _require_normal_structure(dependencies, route, expected_store)
    except Exception:
        failed = True
    if failed:
        raise _Quarantine()


def _role_observation(
    dependencies: _Dependencies,
    route: str,
    expected_store: UUID,
    expected_role: _ExpectedRole,
    *,
    allow_disabled: bool,
) -> str:
    connection = None
    try:
        connection = _open(dependencies.connection_factory, route)
        _require_admin(connection)
        if _store_id(connection) != expected_store:
            raise ValueError
        return _role_state(
            connection, expected_role, allow_disabled=allow_disabled
        )
    finally:
        _rollback_suppressed(connection)
        _close_suppressed(connection)


def _verified_approval(
    dependencies: _Dependencies,
    preflight: _Preflight,
    authority_bytes: bytes,
    approval_bytes: bytes,
) -> _CurrentApprovalCarrier:
    authority_now_us = _authority_time_us(dependencies)
    verifier_now_us = max(authority_now_us, preflight.database_high_water_us)
    try:
        approval = dependencies.approval_verifier.verify(
            authority_bytes,
            approval_bytes,
            now_us=verifier_now_us,
        )
    except SecurityAuditApprovalRefused:
        raise _Refusal()
    if (
        type(approval) is not _VerifiedSecurityAuditApproval
        or approval.store_migration_execution_id
        != preflight.store_migration_execution_id
    ):
        raise _Refusal()
    return _CurrentApprovalCarrier(approval, authority_now_us)


def _resolve_unacknowledged_login(
    dependencies: _Dependencies,
    preflight: _Preflight,
    outcome: _LoginCreationOutcome,
) -> None:
    expected_role = outcome.expected_role
    try:
        state = _role_observation(
            dependencies,
            preflight.routes.admin,
            preflight.store_migration_execution_id,
            expected_role,
            allow_disabled=True,
        )
        if state == "EXPECTED":
            _close_login(
                dependencies,
                preflight.routes.admin,
                preflight.store_migration_execution_id,
                expected_role,
            )
            raise _ConsumedFailure()
        if state == "ABSENT":
            _require_normal_structure(
                dependencies,
                preflight.routes.admin,
                preflight.store_migration_execution_id,
            )
            raise _ConsumedFailure()
    except (_ConsumedFailure, _Quarantine):
        raise
    except Exception:
        raise _Quarantine()
    raise _Quarantine()


def _create_or_resolve_login(
    dependencies: _Dependencies,
    preflight: _Preflight,
    current: _CurrentApprovalCarrier,
) -> tuple[str, _ExpectedRole]:
    try:
        password, password_verifier = _password_material(dependencies)
    except Exception:
        raise _ConsumedFailure()
    try:
        outcome = _create_login(
            dependencies,
            preflight.routes.admin,
            preflight.store_migration_execution_id,
            current,
            password_verifier,
        )
    except _ConsumedFailure:
        try:
            _require_normal_structure(
                dependencies,
                preflight.routes.admin,
                preflight.store_migration_execution_id,
            )
        except Exception:
            raise _Quarantine()
        raise
    if outcome.commit_acknowledged is not True:
        _resolve_unacknowledged_login(dependencies, preflight, outcome)
    return password, outcome.expected_role


def _export_and_close(
    dependencies: _Dependencies,
    preflight: _Preflight,
    approval: _VerifiedSecurityAuditApproval,
    password: str,
    expected_role: _ExpectedRole,
) -> _ClosedSecurityAuditBreakGlassExport:
    exported = None
    export_failed = False
    interrupted: BaseException | None = None
    try:
        exported = dependencies.export_runner.run(
            preflight.routes.control,
            _export_route(preflight.routes.admin, password),
            approval.cursor,
        )
        if type(exported) is not AcknowledgedSecurityAuditExport:
            raise ValueError
    except Exception:
        export_failed = True
    except BaseException as error:
        interrupted = error
    _close_login(
        dependencies,
        preflight.routes.admin,
        preflight.store_migration_execution_id,
        expected_role,
    )
    if interrupted is not None:
        raise interrupted
    if export_failed or exported is None:
        raise _ConsumedFailure()
    return _ClosedSecurityAuditBreakGlassExport(
        operation_id=approval.operation_id,
        page_bytes=exported.page_bytes,
    )


def _execute(
    dependencies: _Dependencies,
    secret_carrier: object,
    authority_receipt_bytes: object,
    approval_bundle_bytes: object,
) -> _ClosedSecurityAuditBreakGlassExport:
    routes, authority_bytes, approval_bytes = _validated_invocation(
        secret_carrier,
        authority_receipt_bytes,
        approval_bundle_bytes,
    )
    preflight = _preflight(dependencies, routes)
    current = _verified_approval(
        dependencies, preflight, authority_bytes, approval_bytes
    )
    current = _advance_current_approval(dependencies, current)
    _consume(dependencies, routes.control, current)
    password, expected_role = _create_or_resolve_login(
        dependencies, preflight, current
    )
    return _export_and_close(
        dependencies,
        preflight,
        current.approval,
        password,
        expected_role,
    )


def _close_expired(
    dependencies: _Dependencies,
    secret_carrier: object,
) -> None:
    if type(secret_carrier) is not SecurityAuditBreakGlassSecrets:
        raise ValueError
    routes = _Routes(
        admin=_validated_route(secret_carrier.admin_dsn),
        control=_validated_route(secret_carrier.control_dsn),
    )
    connection = None
    try:
        connection = _open(dependencies.connection_factory, routes.admin)
        _require_admin(connection)
        store_id = _store_id(connection)
        high_water = _clock_high_water(connection)
    finally:
        _rollback_suppressed(connection)
        _close_suppressed(connection)
    unbound_role = _ExpectedRole(None, None)
    state = _role_observation(
        dependencies,
        routes.admin,
        store_id,
        unbound_role,
        allow_disabled=True,
    )
    if state == "ABSENT":
        _require_normal_structure(dependencies, routes.admin, store_id)
        return
    if state != "EXPECTED":
        raise _Refusal()
    connection = None
    try:
        connection = _open(dependencies.connection_factory, routes.admin)
        _require_admin(connection)
        row = _exact_row(connection.execute(_ROLE_SQL), 11)
        expiry = row[7]
        password_verifier = row[10]
        if (
            type(expiry) is not datetime
            or expiry.utcoffset() != timedelta(0)
            or type(password_verifier) is not str
        ):
            raise _Quarantine()
        expected_role = _ExpectedRole(expiry, password_verifier)
        if _role_state(
            connection, expected_role, allow_disabled=True
        ) != "EXPECTED":
            raise _Quarantine()
    finally:
        _rollback_suppressed(connection)
        _close_suppressed(connection)
    now_us = max(_authority_time_us(dependencies), high_water)
    if expiry > _expiry(now_us):
        raise _Refusal()
    _close_login(dependencies, routes.admin, store_id, expected_role)


def _public_run(
    dependencies: _Dependencies,
    secret_carrier: object,
    authority_receipt_bytes: object,
    approval_bundle_bytes: object,
) -> _ClosedSecurityAuditBreakGlassExport:
    outcome = ""
    result = None
    try:
        result = _execute(
            dependencies,
            secret_carrier,
            authority_receipt_bytes,
            approval_bundle_bytes,
        )
    except _ConsumptionUnknown:
        outcome = "UNKNOWN"
    except _Quarantine:
        outcome = "QUARANTINED"
    except _ConsumedFailure:
        outcome = "FAILED"
    except Exception:
        outcome = "REFUSED"
    if outcome == "UNKNOWN":
        raise SecurityAuditBreakGlassOutcomeUnknown()
    if outcome == "QUARANTINED":
        raise SecurityAuditBreakGlassQuarantined()
    if outcome == "FAILED":
        raise SecurityAuditBreakGlassFailed()
    if outcome == "REFUSED" or result is None:
        raise SecurityAuditBreakGlassRefused()
    return result


class SecurityAuditBreakGlassRunner:
    """Execute or close the one repository-fixed temporary export LOGIN."""

    __slots__ = ("_approval_verifier",)

    def __init__(self, observer_public_key: bytes) -> None:
        refused = False
        try:
            self._approval_verifier = SecurityAuditDualApprovalVerifier(
                observer_public_key
            )
        except Exception:
            refused = True
        if refused:
            raise SecurityAuditBreakGlassRefused()

    def run(
        self,
        secret_carrier: SecurityAuditBreakGlassSecrets,
        authority_receipt_bytes: bytes,
        approval_bundle_bytes: bytes,
    ) -> _ClosedSecurityAuditBreakGlassExport:
        """Return one page only after acknowledged consumption and closure."""

        dependencies = _Dependencies(
            connection_factory=cast(_ConnectionFactory, psycopg.connect),
            time_ns=time.time_ns,
            random_bytes=secrets.token_bytes,
            approval_verifier=self._approval_verifier,
            export_runner=SecurityAuditExportRunner(),
            catalog_verifier=cast(_CatalogVerifier, verify_catalog_identity),
        )
        return _public_run(
            dependencies,
            secret_carrier,
            authority_receipt_bytes,
            approval_bundle_bytes,
        )

    def close_expired(
        self,
        secret_carrier: SecurityAuditBreakGlassSecrets,
    ) -> None:
        """Close only an absent or expired exact-shape stale fixed LOGIN."""

        dependencies = _Dependencies(
            connection_factory=cast(_ConnectionFactory, psycopg.connect),
            time_ns=time.time_ns,
            random_bytes=secrets.token_bytes,
            approval_verifier=self._approval_verifier,
            export_runner=SecurityAuditExportRunner(),
            catalog_verifier=cast(_CatalogVerifier, verify_catalog_identity),
        )
        outcome = ""
        try:
            _close_expired(dependencies, secret_carrier)
        except _Quarantine:
            outcome = "QUARANTINED"
        except Exception:
            outcome = "REFUSED"
        if outcome == "QUARANTINED":
            raise SecurityAuditBreakGlassQuarantined()
        if outcome == "REFUSED":
            raise SecurityAuditBreakGlassRefused()


def _run_security_audit_break_glass_for_testing(
    secret_carrier: object,
    authority_receipt_bytes: object,
    approval_bundle_bytes: object,
    dependencies: _Dependencies,
) -> _ClosedSecurityAuditBreakGlassExport:
    """Private deterministic seam exercising the equal production machine."""

    return _public_run(
        dependencies,
        secret_carrier,
        authority_receipt_bytes,
        approval_bundle_bytes,
    )


__all__ = (
    "BREAK_GLASS_CONNECTION_OPTIONS",
    "BREAK_GLASS_CONNECT_TIMEOUT_SECONDS",
    "CONSUME_TEMPORARY_EXPORT_APPROVAL_SQL",
    "SECURITY_AUDIT_DATABASE",
    "SecurityAuditBreakGlassError",
    "SecurityAuditBreakGlassFailed",
    "SecurityAuditBreakGlassOutcomeUnknown",
    "SecurityAuditBreakGlassQuarantined",
    "SecurityAuditBreakGlassRefused",
    "SecurityAuditBreakGlassRunner",
    "SecurityAuditBreakGlassSecrets",
    "TEMPORARY_EXPORT_CAPABILITY",
    "TEMPORARY_EXPORT_LOGIN",
)
