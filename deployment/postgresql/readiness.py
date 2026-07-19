"""Independent read-only PostgreSQL structural compatibility observations.

The tenant and security-audit lanes authenticate their own checked-in migration
release against their own live observation of the pinned PostgreSQL 17.10
build.  A separate, narrow attestation can prove only that the two observed
routes use different PostgreSQL system identifiers.  None of these results is
an application, audit-runtime, promotion, provenance, or continuity decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import psycopg

from deployment.postgresql.catalog_identity import (
    CATALOG_OUTPUT_SETTING_ASSIGNMENTS,
    CATALOG_OUTPUT_SETTING_VALUES,
    CatalogIdentityError,
    verify_catalog_identity,
)
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    MigrationService,
    MigrationSet,
    load_authoritative_migration_set,
)
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC,
    ProvisioningSpec,
)
from deployment.postgresql.version_policy import (
    SUPPORTED_POSTGRESQL_SERVER_VERSION,
    SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_CONNECT_TIMEOUT_SECONDS = 5
_STATEMENT_TIMEOUT_MILLISECONDS = 2_000
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")

_IDENTITY_SQL = """
    SELECT SESSION_USER::text,
           CURRENT_USER::text,
           pg_catalog.current_database()::text,
           pg_catalog.current_setting('server_version_num')::integer,
           pg_catalog.current_setting('server_version')::text,
           control.system_identifier::text,
           pg_catalog.current_setting('transaction_isolation')::text,
           pg_catalog.current_setting('transaction_read_only')::text,
           pg_catalog.current_setting('standard_conforming_strings')::text,
           pg_catalog.current_setting('TimeZone')::text,
           pg_catalog.current_setting('DateStyle')::text,
           pg_catalog.current_setting('quote_all_identifiers')::text
    FROM pg_catalog.pg_control_system() AS control
"""

_TENANT_HISTORY_SQL = """
    SELECT version,
           filename,
           source_sha256,
           source_byte_length,
           applied_prefix_digest,
           service_identity,
           provisioning_spec_digest
    FROM ofarm.schema_migration
    ORDER BY version
"""

_AUDIT_HISTORY_SQL = """
    SELECT version,
           filename,
           source_sha256,
           source_byte_length,
           applied_prefix_digest,
           service_identity,
           provisioning_spec_digest
    FROM ofarm_security.schema_migration
    ORDER BY version
"""

_TENANT_OBSERVER_SQL = "SELECT * FROM ofarm.observe_tenant_contract()"
_AUDIT_OBSERVER_SQL = (
    "SELECT * FROM ofarm_security.observe_security_audit_contract()"
)


class PostgreSQLVerificationError(RuntimeError):
    """One exact read-only structural observation could not be proven."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"PostgreSQL verification refused: {reason}")


@dataclass(frozen=True, slots=True)
class PostgreSQLStructuralCompatibilityReport:
    """Safe version-only evidence for one exact structural observation."""

    service_identity: str
    supported_version: int
    observed_version: int

    def manifest(self) -> dict[str, object]:
        return {
            "schemaVersion": "ofarm.postgresql-structural-compatibility.v1",
            "serviceIdentity": self.service_identity,
            "supportedVersion": self.supported_version,
            "observedVersion": self.observed_version,
        }


@dataclass(frozen=True, slots=True)
class PostgreSQLServiceSeparationAttestation:
    """Evidence only that the two fixed routes have different system IDs."""

    tenant_service_identity: str
    audit_service_identity: str

    def manifest(self) -> dict[str, object]:
        return {
            "schemaVersion": "ofarm.postgresql-service-separation.v1",
            "tenantServiceIdentity": self.tenant_service_identity,
            "securityAuditServiceIdentity": self.audit_service_identity,
            "distinctPostgreSQLSystemIdentifiers": True,
        }


@dataclass(frozen=True, slots=True)
class _Lane:
    label: str
    session_user: str
    database_name: str
    service: MigrationService
    spec: ProvisioningSpec
    history_sql: str
    observer_sql: str


_TENANT_LANE = _Lane(
    label="tenant",
    session_user="ofarm_readiness",
    database_name="ofarm_tenant",
    service=TENANT_SERVICE,
    spec=TENANT_PROVISIONING_SPEC,
    history_sql=_TENANT_HISTORY_SQL,
    observer_sql=_TENANT_OBSERVER_SQL,
)

_AUDIT_LANE = _Lane(
    label="security-audit",
    session_user="ofarm_security_audit_readiness_login",
    database_name="ofarm_security_audit",
    service=SECURITY_AUDIT_SERVICE,
    spec=SECURITY_AUDIT_PROVISIONING_SPEC,
    history_sql=_AUDIT_HISTORY_SQL,
    observer_sql=_AUDIT_OBSERVER_SQL,
)


@dataclass(slots=True)
class _ConnectionState:
    connection: psycopg.Connection
    transaction_started: bool = False


@dataclass(frozen=True, slots=True)
class _LaneObservation:
    system_identifier: str
    server_version_num: int
    migration_version: int


def _refuse(reason: str) -> PostgreSQLVerificationError:
    return PostgreSQLVerificationError(reason)


def _load_authoritative_set(
    package_root: Path,
    lane: _Lane,
) -> MigrationSet:
    failed = False
    migration_set = None
    try:
        migration_set = load_authoritative_migration_set(
            package_root, lane.service
        )
    except Exception:
        failed = True
    if failed or migration_set is None:
        raise _refuse(
            f"{lane.label} authoritative migration identity is unavailable"
        )
    if migration_set.service != lane.service:
        raise _refuse(
            f"{lane.label} authoritative migration service identity differs"
        )
    return migration_set


def _connect(dsn: str, lane: _Lane) -> _ConnectionState:
    failed = False
    connection = None
    try:
        connection = psycopg.connect(
            dsn,
            autocommit=True,
            connect_timeout=_CONNECT_TIMEOUT_SECONDS,
        )
    except Exception:
        failed = True
    if failed or connection is None:
        raise _refuse(f"{lane.label} structural route is unavailable")
    return _ConnectionState(connection)


def _execute(connection: psycopg.Connection, statement: str, reason: str) -> None:
    failed = False
    try:
        connection.execute(statement)
    except Exception:
        failed = True
    if failed:
        raise _refuse(reason)


def _fetch_rows(
    connection: psycopg.Connection,
    statement: str,
    reason: str,
) -> tuple[tuple[object, ...], ...]:
    failed = False
    rows = None
    try:
        rows = connection.execute(statement).fetchall()
    except Exception:
        failed = True
    if failed or type(rows) is not list:
        raise _refuse(reason)
    if any(type(row) is not tuple for row in rows):
        raise _refuse(reason)
    return tuple(rows)


def _begin_read_only_transaction(state: _ConnectionState, lane: _Lane) -> None:
    _execute(
        state.connection,
        "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
        f"{lane.label} structural observation transaction could not begin",
    )
    state.transaction_started = True
    _execute(
        state.connection,
        f"SET LOCAL statement_timeout = '{_STATEMENT_TIMEOUT_MILLISECONDS}ms'",
        f"{lane.label} structural observation timeout could not be fixed",
    )
    for assignment in CATALOG_OUTPUT_SETTING_ASSIGNMENTS:
        _execute(
            state.connection,
            f"SET LOCAL {assignment}",
            f"{lane.label} catalog observation posture could not be fixed",
        )


def _observe_identity(
    connection: psycopg.Connection,
    lane: _Lane,
) -> tuple[str, int]:
    rows = _fetch_rows(
        connection,
        _IDENTITY_SQL,
        f"{lane.label} structural route identity is unreadable",
    )
    if len(rows) != 1 or len(rows[0]) != 12:
        raise _refuse(f"{lane.label} structural route identity differs")
    row = rows[0]
    if row[0:3] != (
        lane.session_user,
        lane.session_user,
        lane.database_name,
    ):
        raise _refuse(f"{lane.label} structural route identity differs")
    if (
        type(row[3]) is not int
        or row[3] != SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM
        or row[4] != SUPPORTED_POSTGRESQL_SERVER_VERSION
    ):
        raise _refuse(f"{lane.label} PostgreSQL version differs")
    if (
        type(row[5]) is not str
        or not row[5]
        or not row[5].isascii()
        or not row[5].isdigit()
    ):
        raise _refuse(f"{lane.label} PostgreSQL system identifier is unreadable")
    if row[6:12] != (
        "repeatable read",
        "on",
        *CATALOG_OUTPUT_SETTING_VALUES,
    ):
        raise _refuse(
            f"{lane.label} transaction or catalog observation posture differs"
        )
    return row[5], row[3]


def _expected_history(
    lane: _Lane,
    migration_set: MigrationSet,
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            migration.version,
            migration.filename,
            migration.source_sha256,
            migration.byte_length,
            migration_set.prefix_digest(migration.version),
            lane.service.identity,
            lane.spec.digest,
        )
        for migration in migration_set.migrations
    )


def _observe_history(
    connection: psycopg.Connection,
    lane: _Lane,
    migration_set: MigrationSet,
) -> int:
    rows = _fetch_rows(
        connection,
        lane.history_sql,
        f"{lane.label} migration history is unreadable",
    )
    if any(
        len(row) != 7
        or type(row[0]) is not int
        or type(row[1]) is not str
        or type(row[2]) is not str
        or type(row[3]) is not int
        or type(row[4]) is not str
        or type(row[5]) is not str
        or type(row[6]) is not str
        for row in rows
    ):
        raise _refuse(f"{lane.label} migration history differs")
    if rows != _expected_history(lane, migration_set):
        raise _refuse(f"{lane.label} migration history differs")
    return len(rows)


def _exact_observer_row(
    connection: psycopg.Connection,
    lane: _Lane,
) -> tuple[object, ...]:
    rows = _fetch_rows(
        connection,
        lane.observer_sql,
        f"{lane.label} contract observation is unreadable",
    )
    if len(rows) != 1:
        raise _refuse(f"{lane.label} contract observation differs")
    return rows[0]


def _is_digest(value: object) -> bool:
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def _verify_tenant_observer(
    connection: psycopg.Connection,
    migration_set: MigrationSet,
) -> None:
    from deployment.postgresql.tenant_contract import TENANT_CONTEXT_CONTRACT

    row = _exact_observer_row(connection, _TENANT_LANE)
    latest_version = len(migration_set.migrations)
    if (
        len(row) != 11
        or row[0] is not True
        or row[1] != TENANT_CONTEXT_CONTRACT.digest
        or type(row[2]) is not int
        or row[2] != 0
        or not _is_digest(row[3])
        or not _is_digest(row[4])
        or row[5] != TENANT_PROVISIONING_SPEC.digest
        or row[6] != TENANT_SERVICE.identity
        or type(row[7]) is not int
        or row[7] != latest_version
        or row[8] != migration_set.prefix_digest(latest_version)
        or type(row[9]) is not int
        or row[9] != latest_version
        or row[10] is not False
    ):
        raise _refuse("tenant contract observation differs")


def _verify_audit_observer(
    connection: psycopg.Connection,
    migration_set: MigrationSet,
) -> None:
    from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT

    row = _exact_observer_row(connection, _AUDIT_LANE)
    latest_version = len(migration_set.migrations)
    expected = (
        SECURITY_AUDIT_CONTRACT.identity,
        SECURITY_AUDIT_CONTRACT.digest,
        SECURITY_AUDIT_CONTRACT.event_format_identity,
        SECURITY_AUDIT_CONTRACT.redaction_policy_identity,
        SECURITY_AUDIT_CONTRACT.retention_policy_identity,
        SECURITY_AUDIT_CONTRACT.correlation_hmac.domain,
        SECURITY_AUDIT_CONTRACT.correlation_hmac.key_version,
        SECURITY_AUDIT_SERVICE.identity,
        SECURITY_AUDIT_PROVISIONING_SPEC.digest,
        latest_version,
        migration_set.prefix_digest(latest_version),
        True,
        False,
    )
    if len(row) != 13 or row != expected:
        raise _refuse("security-audit contract observation differs")
    if type(row[6]) is not int or type(row[9]) is not int:
        raise _refuse("security-audit contract observation differs")
    if row[11] is not True or row[12] is not False:
        raise _refuse("security-audit contract observation differs")


def _observe_lane(
    state: _ConnectionState,
    lane: _Lane,
    migration_set: MigrationSet,
) -> _LaneObservation:
    system_identifier, server_version_num = _observe_identity(
        state.connection, lane
    )
    migration_version = _observe_history(
        state.connection, lane, migration_set
    )
    try:
        verify_catalog_identity(state.connection, lane.service)
    except CatalogIdentityError:
        raise _refuse(f"{lane.label} catalog verifier identity differs") from None
    if lane is _TENANT_LANE:
        _verify_tenant_observer(state.connection, migration_set)
    elif lane is _AUDIT_LANE:
        _verify_audit_observer(state.connection, migration_set)
    else:
        raise _refuse("structural observation service identity differs")
    return _LaneObservation(
        system_identifier=system_identifier,
        server_version_num=server_version_num,
        migration_version=migration_version,
    )


def _cleanup(states: list[_ConnectionState]) -> bool:
    failed = False
    for state in reversed(states):
        if state.transaction_started:
            try:
                state.connection.rollback()
            except Exception:
                failed = True
        try:
            state.connection.close()
        except Exception:
            failed = True
    return not failed


def _verify_lane_structural_compatibility(
    *,
    structural_dsn: str,
    lane: _Lane,
    package_root: Path,
) -> PostgreSQLStructuralCompatibilityReport:
    if type(structural_dsn) is not str or not structural_dsn:
        raise _refuse(f"{lane.label} structural route is required")
    if not isinstance(package_root, Path):
        raise _refuse("package root must be a pathlib.Path")

    migration_set = _load_authoritative_set(package_root, lane)
    states: list[_ConnectionState] = []
    failure_reason: str | None = None
    report: PostgreSQLStructuralCompatibilityReport | None = None
    cleanup_succeeded = False
    try:
        state = _connect(structural_dsn, lane)
        states.append(state)
        _begin_read_only_transaction(state, lane)
        observation = _observe_lane(state, lane, migration_set)
        report = PostgreSQLStructuralCompatibilityReport(
            service_identity=lane.service.identity,
            supported_version=len(migration_set.migrations),
            observed_version=observation.migration_version,
        )
    except PostgreSQLVerificationError as exc:
        failure_reason = exc.reason
    except Exception:
        failure_reason = f"{lane.label} structural observation failed"
    finally:
        cleanup_succeeded = _cleanup(states)

    if not cleanup_succeeded:
        failure_reason = f"{lane.label} structural observation cleanup failed"
    if failure_reason is not None:
        raise _refuse(failure_reason)
    if report is None:
        raise _refuse(f"{lane.label} structural observation failed")
    return report


def verify_tenant_structural_compatibility(
    *,
    tenant_structural_dsn: str,
    package_root: Path = _PACKAGE_ROOT,
) -> PostgreSQLStructuralCompatibilityReport:
    """Verify only the tenant database's exact structural contract."""

    return _verify_lane_structural_compatibility(
        structural_dsn=tenant_structural_dsn,
        lane=_TENANT_LANE,
        package_root=package_root,
    )


def verify_security_audit_structural_compatibility(
    *,
    audit_structural_dsn: str,
    package_root: Path = _PACKAGE_ROOT,
) -> PostgreSQLStructuralCompatibilityReport:
    """Verify only the security-audit database's structural contract."""

    return _verify_lane_structural_compatibility(
        structural_dsn=audit_structural_dsn,
        lane=_AUDIT_LANE,
        package_root=package_root,
    )


def verify_postgresql_service_separation(
    *,
    tenant_structural_dsn: str,
    audit_structural_dsn: str,
) -> PostgreSQLServiceSeparationAttestation:
    """Attest only that the two fixed routes have different system IDs.

    The result says nothing about uninterrupted history, restore provenance,
    physical resources, operational health, or whether either service should
    accept traffic.
    """

    if type(tenant_structural_dsn) is not str or not tenant_structural_dsn:
        raise _refuse("tenant structural route is required")
    if type(audit_structural_dsn) is not str or not audit_structural_dsn:
        raise _refuse("security-audit structural route is required")

    states: list[_ConnectionState] = []
    failure_reason: str | None = None
    attestation: PostgreSQLServiceSeparationAttestation | None = None
    cleanup_succeeded = False
    try:
        tenant_state = _connect(tenant_structural_dsn, _TENANT_LANE)
        states.append(tenant_state)
        _begin_read_only_transaction(tenant_state, _TENANT_LANE)

        audit_state = _connect(audit_structural_dsn, _AUDIT_LANE)
        states.append(audit_state)
        _begin_read_only_transaction(audit_state, _AUDIT_LANE)

        tenant_system_identifier, tenant_version = _observe_identity(
            tenant_state.connection, _TENANT_LANE
        )
        audit_system_identifier, audit_version = _observe_identity(
            audit_state.connection, _AUDIT_LANE
        )
        if tenant_version != audit_version:
            raise _refuse("tenant and security-audit PostgreSQL versions differ")
        if tenant_system_identifier == audit_system_identifier:
            raise _refuse(
                "tenant and security-audit routes use one PostgreSQL "
                "system identifier"
            )
        attestation = PostgreSQLServiceSeparationAttestation(
            tenant_service_identity=TENANT_SERVICE.identity,
            audit_service_identity=SECURITY_AUDIT_SERVICE.identity,
        )
    except PostgreSQLVerificationError as exc:
        failure_reason = exc.reason
    except Exception:
        failure_reason = "PostgreSQL service-separation observation failed"
    finally:
        cleanup_succeeded = _cleanup(states)

    if not cleanup_succeeded:
        failure_reason = "PostgreSQL service-separation cleanup failed"
    if failure_reason is not None:
        raise _refuse(failure_reason)
    if attestation is None:
        raise _refuse("PostgreSQL service-separation observation failed")
    return attestation


__all__ = (
    "PostgreSQLServiceSeparationAttestation",
    "PostgreSQLStructuralCompatibilityReport",
    "PostgreSQLVerificationError",
    "verify_postgresql_service_separation",
    "verify_security_audit_structural_compatibility",
    "verify_tenant_structural_compatibility",
)
