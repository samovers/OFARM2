"""Real PostgreSQL 17 migration-runner boundary tests for issue #174.

Every migration used here is synthetic and lives under pytest's temporary
directory.  This module must never create either authoritative checked-in
migration directory.
"""

from __future__ import annotations

import inspect
import os
import secrets
import socket
import struct
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event, Thread
from typing import Mapping
from uuid import UUID, uuid4

import psycopg
import psycopg.conninfo
import pytest
from psycopg import sql

import deployment.postgresql.migration_runner as migration_runner_module
import deployment.postgresql.provisioning as provisioning_module
from deployment.postgresql.migration_runner import (
    MigrationDirtyError,
    MigrationExecutionError,
    MigrationInputError,
    MigrationOutcomeUnknown,
    MigrationRunReport,
    MigrationTargetError,
    _authenticate_tenant_binding_selection_control_admission_row,
    _authenticate_tenant_current_context_selection_owner_admission_row,
    _authenticate_tenant_write_lock_selection_owner_admission_row,
    _begin_and_lock,
    _migrate_service_for_testing as migrate_service,
    initial_ledger_sql,
    migrate_service as migrate_authoritative_service,
    validate_migration_source,
)
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    AuthoritativeMigration,
    MigrationService,
    MigrationSet,
    load_authoritative_migration_set,
    load_migration_set,
)
from deployment.postgresql.provisioning import (
    ProvisioningDriftError,
    provision_service,
    verify_service,
    verify_service_infrastructure,
)
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC,
    ProvisioningSpec,
)
from deployment.postgresql.version_policy import (
    SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
)


TENANT_ADMIN_ENV = "OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN"
AUDIT_ADMIN_ENV = "OFARM_SECURITY_AUDIT_PG_ADMIN_DSN"
MAINTENANCE_DATABASES = ("postgres", "template0", "template1")
RELEASE_IDENTITY = "ofarm-tests/issue-174"


class _FailingTransactionSetup:
    def __init__(self, failure_prefix: str) -> None:
        self.failure_prefix = failure_prefix
        self.rolled_back = False

    def execute(self, statement):
        rendered = str(statement)
        if rendered.startswith(self.failure_prefix):
            raise psycopg.OperationalError("SECRET-TRANSACTION-SETUP-SENTINEL")
        return self

    def fetchone(self):
        return (None,)

    def rollback(self) -> None:
        self.rolled_back = True


@pytest.mark.parametrize("failure_prefix", ("BEGIN", "SET LOCAL"))
def test_transaction_setup_failures_are_normalized_and_rolled_back(
    failure_prefix: str,
) -> None:
    connection = _FailingTransactionSetup(failure_prefix)

    with pytest.raises(
        MigrationTargetError,
        match="protected migration transaction setup failed",
    ) as raised:
        _begin_and_lock(connection, TENANT_PROVISIONING_SPEC)  # type: ignore[arg-type]

    assert connection.rolled_back is True
    assert "SECRET-TRANSACTION-SETUP-SENTINEL" not in str(raised.value)


@dataclass(frozen=True, slots=True)
class _TenantTarget:
    admin_dsn: str
    target_admin_dsn: str
    migrator_dsn: str
    passwords: Mapping[str, str]


class _CommitAcknowledgementDropProxy:
    """Drop only the server acknowledgement of one forwarded COMMIT."""

    _COMMIT_MARKER = b"COMMIT\x00"

    def __init__(self, upstream_dsn: str) -> None:
        parameters = psycopg.conninfo.conninfo_to_dict(upstream_dsn)
        host = parameters.get("host")
        if not host or host.startswith("/"):
            pytest.skip("a TCP migrator DSN is required for acknowledgement loss")
        self._upstream = (host, int(parameters.get("port") or 5432))
        self._listener = socket.create_server(("127.0.0.1", 0), backlog=1)
        self._listener.settimeout(10)
        self._stopped = Event()
        self.acknowledgement_dropped = Event()
        self._errors: list[BaseException] = []
        self._thread = Thread(target=self._serve, daemon=True)
        parameters.pop("hostaddr", None)
        parameters.update(
            host="127.0.0.1",
            port=str(self._listener.getsockname()[1]),
            sslmode="disable",
            connect_timeout="5",
        )
        self.dsn = psycopg.conninfo.make_conninfo(**parameters)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._stopped.set()
        self._listener.close()
        self._thread.join(timeout=10)
        if self._thread.is_alive():
            raise AssertionError("commit acknowledgement proxy did not stop")
        if self._errors:
            raise AssertionError("commit acknowledgement proxy failed") from self._errors[0]

    def _serve(self) -> None:
        try:
            client, _address = self._listener.accept()
            with client, socket.create_connection(
                self._upstream,
                timeout=10,
            ) as upstream:
                client.settimeout(10)
                upstream.settimeout(10)
                commit_forwarded = Event()

                def stop_relays() -> None:
                    self._stopped.set()
                    for relay_socket in (client, upstream):
                        try:
                            relay_socket.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass

                def forward_client() -> None:
                    tail = b""
                    try:
                        while not self._stopped.is_set():
                            data = client.recv(65_536)
                            if not data:
                                return
                            if self._COMMIT_MARKER in tail + data:
                                commit_forwarded.set()
                            upstream.sendall(data)
                            tail = (tail + data)[-len(self._COMMIT_MARKER) :]
                    except OSError as exc:
                        if not self._stopped.is_set():
                            self._errors.append(exc)
                    finally:
                        stop_relays()

                def forward_server() -> None:
                    tail = b""
                    try:
                        while not self._stopped.is_set():
                            data = upstream.recv(65_536)
                            if not data:
                                return
                            if commit_forwarded.is_set():
                                if self._COMMIT_MARKER in tail + data:
                                    self.acknowledgement_dropped.set()
                                    return
                                tail = (tail + data)[-len(self._COMMIT_MARKER) :]
                                continue
                            client.sendall(data)
                    except OSError as exc:
                        if not self._stopped.is_set():
                            self._errors.append(exc)
                    finally:
                        stop_relays()

                with ThreadPoolExecutor(max_workers=2) as executor:
                    client_future = executor.submit(forward_client)
                    server_future = executor.submit(forward_server)
                    client_future.result()
                    server_future.result()
        except OSError as exc:
            if not self._stopped.is_set():
                self._errors.append(exc)
        finally:
            self._stopped.set()


class _V6LedgerBindSubstitutionProxy:
    """Substitute one V6 ledger bind value at the real connection boundary."""

    _INSERT_MARKER = (
        b'INSERT INTO "ofarm"."schema_migration" '
        b'(version, filename, source_sha256, source_byte_length, '
        b'applied_prefix_digest, service_identity, '
        b'provisioning_spec_digest, release_identity, execution_id)'
    )
    _FIELD_INDEX = {
        field: index for index, field in enumerate(
            (
                "version",
                "filename",
                "source_sha256",
                "source_byte_length",
                "applied_prefix_digest",
                "service_identity",
                "provisioning_spec_digest",
                "release_identity",
                "execution_id",
            )
        )
    }

    def __init__(self, upstream_dsn: str, substituted_field: str) -> None:
        parameters = psycopg.conninfo.conninfo_to_dict(upstream_dsn)
        host = parameters.get("host")
        if not host or host.startswith("/"):
            pytest.skip("a TCP migrator DSN is required for ledger substitution")
        self._upstream = (host, int(parameters.get("port") or 5432))
        self._substituted_field = substituted_field
        self._listener = socket.create_server(("127.0.0.1", 0), backlog=1)
        self._listener.settimeout(10)
        self._stopped = Event()
        self.parameter_substituted = Event()
        self._errors: list[BaseException] = []
        self._thread = Thread(target=self._serve, daemon=True)
        parameters.pop("hostaddr", None)
        parameters.update(
            host="127.0.0.1",
            port=str(self._listener.getsockname()[1]),
            sslmode="disable",
            connect_timeout="5",
        )
        self.dsn = psycopg.conninfo.make_conninfo(**parameters)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._stopped.set()
        self._listener.close()
        self._thread.join(timeout=10)
        if self._thread.is_alive():
            raise AssertionError("ledger substitution proxy did not stop")
        if self._errors:
            raise AssertionError(
                "ledger substitution proxy failed"
            ) from self._errors[0]

    @staticmethod
    def _cstring_end(payload: bytes, start: int) -> int:
        end = payload.find(b"\x00", start)
        if end < 0:
            raise AssertionError("PostgreSQL frontend cstring is incomplete")
        return end

    def _substitute_value(self, value: bytes, format_code: int) -> bytes:
        field = self._substituted_field
        if field == "version":
            if format_code == 0:
                return b"7"
            return (7).to_bytes(len(value), "big", signed=True)
        if field == "filename":
            replacement = value.replace(b"owner", b"ownez", 1)
            if replacement == value:
                raise AssertionError("V6 filename bind value is not recognizable")
            return replacement
        if field == "source_sha256":
            return b"sha256:" + b"0" * 64
        if field == "source_byte_length":
            if format_code == 0:
                return str(int(value) + 1).encode("ascii")
            number = int.from_bytes(value, "big", signed=True) + 1
            return number.to_bytes(len(value), "big", signed=True)
        if field == "applied_prefix_digest":
            return b"sha256:" + b"1" * 64
        if field == "service_identity":
            return value[:-1] + (b"2" if value[-1:] != b"2" else b"3")
        if field == "provisioning_spec_digest":
            return b"sha256:" + b"2" * 64
        if field == "release_identity":
            return value[:-1] + (b"x" if value[-1:] != b"x" else b"y")
        if field == "execution_id":
            replacement = bytearray(value)
            if format_code == 0:
                replacement[-1] = (
                    ord("0") if replacement[-1] != ord("0") else ord("1")
                )
            else:
                replacement[-1] = replacement[-1] ^ 1
            return bytes(replacement)
        raise AssertionError(f"unsupported V6 ledger field {field!r}")

    def _rewrite_bind(self, frame: bytes) -> bytes:
        payload = frame[5:]
        portal_end = self._cstring_end(payload, 0)
        statement_start = portal_end + 1
        statement_end = self._cstring_end(payload, statement_start)
        offset = statement_end + 1
        format_count = struct.unpack_from("!H", payload, offset)[0]
        offset += 2
        formats = [
            struct.unpack_from("!H", payload, offset + index * 2)[0]
            for index in range(format_count)
        ]
        offset += format_count * 2
        parameter_count = struct.unpack_from("!H", payload, offset)[0]
        offset += 2
        parameters: list[tuple[int, int, int]] = []
        for _index in range(parameter_count):
            length_offset = offset
            length = struct.unpack_from("!i", payload, offset)[0]
            offset += 4
            if length < 0:
                parameters.append((length_offset, offset, offset))
                continue
            value_start = offset
            offset += length
            parameters.append((length_offset, value_start, offset))

        target_index = self._FIELD_INDEX[self._substituted_field]
        if target_index >= len(parameters):
            raise AssertionError("V6 ledger bind parameter list is incomplete")
        length_offset, value_start, value_end = parameters[target_index]
        if value_start == value_end:
            raise AssertionError("V6 ledger bind parameter is null or empty")
        if format_count == 0:
            format_code = 0
        elif format_count == 1:
            format_code = formats[0]
        elif format_count == parameter_count:
            format_code = formats[target_index]
        else:
            raise AssertionError("PostgreSQL bind format list is malformed")
        replacement = self._substitute_value(
            payload[value_start:value_end],
            format_code,
        )
        rewritten_payload = (
            payload[:length_offset]
            + struct.pack("!i", len(replacement))
            + replacement
            + payload[value_end:]
        )
        self.parameter_substituted.set()
        return (
            b"B"
            + struct.pack("!I", len(rewritten_payload) + 4)
            + rewritten_payload
        )

    def _serve(self) -> None:
        try:
            client, _address = self._listener.accept()
            with client, socket.create_connection(
                self._upstream,
                timeout=10,
            ) as upstream:
                client.settimeout(10)
                upstream.settimeout(10)
                v6_statements: set[bytes] = set()

                def stop_relays() -> None:
                    self._stopped.set()
                    for relay_socket in (client, upstream):
                        try:
                            relay_socket.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass

                def forward_client() -> None:
                    buffer = b""
                    startup_forwarded = False
                    try:
                        while not self._stopped.is_set():
                            data = client.recv(65_536)
                            if not data:
                                return
                            buffer += data
                            while True:
                                header_size = 5 if startup_forwarded else 4
                                if len(buffer) < header_size:
                                    break
                                if startup_forwarded:
                                    frame_size = 1 + struct.unpack_from(
                                        "!I", buffer, 1
                                    )[0]
                                else:
                                    frame_size = struct.unpack_from(
                                        "!I", buffer, 0
                                    )[0]
                                if len(buffer) < frame_size:
                                    break
                                frame, buffer = (
                                    buffer[:frame_size],
                                    buffer[frame_size:],
                                )
                                if not startup_forwarded:
                                    startup_forwarded = True
                                elif frame[:1] == b"P":
                                    payload = frame[5:]
                                    name_end = self._cstring_end(payload, 0)
                                    query_start = name_end + 1
                                    query_end = self._cstring_end(
                                        payload,
                                        query_start,
                                    )
                                    statement_name = payload[:name_end]
                                    if self._INSERT_MARKER in payload[
                                        query_start:query_end
                                    ]:
                                        v6_statements.add(statement_name)
                                    else:
                                        v6_statements.discard(statement_name)
                                elif (
                                    frame[:1] == b"B"
                                    and not self.parameter_substituted.is_set()
                                ):
                                    payload = frame[5:]
                                    portal_end = self._cstring_end(payload, 0)
                                    statement_start = portal_end + 1
                                    statement_end = self._cstring_end(
                                        payload,
                                        statement_start,
                                    )
                                    if payload[
                                        statement_start:statement_end
                                    ] in v6_statements:
                                        frame = self._rewrite_bind(frame)
                                upstream.sendall(frame)
                    except OSError as exc:
                        if not self._stopped.is_set():
                            self._errors.append(exc)
                    finally:
                        stop_relays()

                def forward_server() -> None:
                    try:
                        while not self._stopped.is_set():
                            data = upstream.recv(65_536)
                            if not data:
                                return
                            client.sendall(data)
                    except OSError as exc:
                        if not self._stopped.is_set():
                            self._errors.append(exc)
                    finally:
                        stop_relays()

                with ThreadPoolExecutor(max_workers=2) as executor:
                    client_future = executor.submit(forward_client)
                    server_future = executor.submit(forward_server)
                    client_future.result()
                    server_future.result()
        except OSError as exc:
            if not self._stopped.is_set():
                self._errors.append(exc)
        finally:
            self._stopped.set()


class _V7LedgerBindSubstitutionProxy(_V6LedgerBindSubstitutionProxy):
    """Substitute one V7 ledger bind value at the same real boundary."""

    def _substitute_value(self, value: bytes, format_code: int) -> bytes:
        if self._substituted_field == "version":
            if format_code == 0:
                return b"8"
            return (8).to_bytes(len(value), "big", signed=True)
        return super()._substitute_value(value, format_code)


def _admin_dsn() -> str:
    value = os.environ.get(TENANT_ADMIN_ENV)
    if value:
        return value
    raise RuntimeError(
        f"{TENANT_ADMIN_ENV} must identify a dedicated PostgreSQL 17 service"
    )


def _audit_admin_dsn() -> str:
    value = os.environ.get(AUDIT_ADMIN_ENV)
    if value:
        return value
    raise RuntimeError(
        f"{AUDIT_ADMIN_ENV} must identify a dedicated PostgreSQL 17 service"
    )


def _database_dsn(admin_dsn: str, database_name: str, **overrides: str) -> str:
    parameters = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    parameters["dbname"] = database_name
    parameters.update(overrides)
    return psycopg.conninfo.make_conninfo(**parameters)


def _assert_clean_service(admin_dsn: str, spec: ProvisioningSpec) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        database = connection.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (spec.database_name,),
        ).fetchone()
        roles = connection.execute(
            r"""
            SELECT rolname::text
            FROM pg_catalog.pg_roles
            WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
            ORDER BY rolname
            """
        ).fetchall()
        databases = connection.execute(
            "SELECT datname::text FROM pg_catalog.pg_database ORDER BY datname"
        ).fetchall()
        public_database_privileges = connection.execute(
            """
            SELECT database.datname::text, acl.privilege_type
            FROM pg_catalog.pg_database AS database
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(
                    database.datacl,
                    pg_catalog.acldefault('d', database.datdba)
                )
            ) AS acl
            WHERE database.datname = ANY (%s::text[])
              AND acl.grantee = 0
            ORDER BY 1, 2
            """,
            (list(MAINTENANCE_DATABASES),),
        ).fetchall()
    assert database is None, (
        f"disposable database already exists: {spec.database_name}"
    )
    assert roles == [], f"disposable service has governed roles: {roles}"
    assert databases == [(name,) for name in MAINTENANCE_DATABASES]
    assert public_database_privileges == [
        ("postgres", "CONNECT"),
        ("postgres", "TEMPORARY"),
        ("template0", "CONNECT"),
        ("template1", "CONNECT"),
    ]


def _destroy_test_service(admin_dsn: str, spec: ProvisioningSpec) -> None:
    """Remove only the fixed disposable resources this module provisioned."""

    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        role_names = [
            row[0]
            for row in connection.execute(
                r"""
                SELECT rolname::text
                FROM pg_catalog.pg_roles
                WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
                ORDER BY rolname
                """
            ).fetchall()
        ]
        unexpected_roles = sorted(set(role_names) - set(spec.role_names))
        if unexpected_roles:
            raise AssertionError(
                "refusing disposable cleanup with unexpected governed roles: "
                f"{unexpected_roles}"
            )
        connection.execute(
            """
            SELECT pg_catalog.pg_terminate_backend(pid)
            FROM pg_catalog.pg_stat_activity
            WHERE datname = %s AND pid <> pg_catalog.pg_backend_pid()
            """,
            (spec.database_name,),
        )
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(spec.database_name)
            )
        )
        if role_names:
            connection.execute(
                sql.SQL("DROP ROLE {}").format(
                    sql.SQL(", ").join(
                        sql.Identifier(role_name) for role_name in role_names
                    )
                )
            )
        for maintenance_database in MAINTENANCE_DATABASES:
            connection.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO PUBLIC").format(
                    sql.Identifier(maintenance_database)
                )
            )
        connection.execute("GRANT TEMPORARY ON DATABASE postgres TO PUBLIC")
        connection.execute(
            "REVOKE TEMPORARY ON DATABASE template0, template1 FROM PUBLIC"
        )


def _passwords(spec: ProvisioningSpec, nonce: str) -> dict[str, str]:
    return {
        role_name: f"{nonce}-{index}-{secrets.token_urlsafe(32)}"
        for index, role_name in enumerate(spec.required_password_role_names)
    }


@pytest.fixture
def tenant_target() -> _TenantTarget:
    admin_dsn = _admin_dsn()
    spec = TENANT_PROVISIONING_SPEC
    _assert_clean_service(admin_dsn, spec)
    passwords = _passwords(spec, "migration-runner-" + secrets.token_urlsafe(12))
    try:
        provision_service(admin_dsn, spec, login_passwords=passwords)
        yield _TenantTarget(
            admin_dsn=admin_dsn,
            target_admin_dsn=_database_dsn(admin_dsn, spec.database_name),
            migrator_dsn=_database_dsn(
                admin_dsn,
                spec.database_name,
                user="ofarm_migrator",
                password=passwords["ofarm_migrator"],
            ),
            passwords=passwords,
        )
    finally:
        _destroy_test_service(admin_dsn, spec)


@pytest.fixture
def audit_target() -> _TenantTarget:
    admin_dsn = _audit_admin_dsn()
    spec = SECURITY_AUDIT_PROVISIONING_SPEC
    _assert_clean_service(admin_dsn, spec)
    passwords = _passwords(spec, "audit-runner-" + secrets.token_urlsafe(12))
    try:
        provision_service(admin_dsn, spec, login_passwords=passwords)
        yield _TenantTarget(
            admin_dsn=admin_dsn,
            target_admin_dsn=_database_dsn(admin_dsn, spec.database_name),
            migrator_dsn=_database_dsn(
                admin_dsn,
                spec.database_name,
                user="ofarm_migrator",
                password=passwords["ofarm_migrator"],
            ),
            passwords=passwords,
        )
    finally:
        _destroy_test_service(admin_dsn, spec)


def _load_synthetic_set(
    tmp_path: Path,
    sources: Mapping[str, bytes],
    *,
    service: MigrationService = TENANT_SERVICE,
) -> MigrationSet:
    package_root = tmp_path / "synthetic-package"
    directory = package_root.joinpath(*service.relative_directory.split("/"))
    directory.mkdir(parents=True)
    for filename, source_bytes in sources.items():
        (directory / filename).write_bytes(source_bytes)
    return load_migration_set(package_root, service)


def _initial_source(*, delay_seconds: float | None = None) -> bytes:
    source = initial_ledger_sql(TENANT_PROVISIONING_SPEC).encode("utf-8")
    if delay_seconds is not None:
        source += f"\nSELECT pg_catalog.pg_sleep({delay_seconds});\n".encode("ascii")
    source += b"""
CREATE FUNCTION ofarm.create_tenant_challenge()
RETURNS pg_catalog.uuid
LANGUAGE sql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT NULL::pg_catalog.uuid';

CREATE FUNCTION ofarm.current_tenant_id()
RETURNS pg_catalog.uuid
LANGUAGE sql STABLE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT NULL::pg_catalog.uuid';

CREATE FUNCTION ofarm.current_backend_start()
RETURNS pg_catalog.timestamptz
LANGUAGE sql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'SELECT pg_catalog.clock_timestamp()';

CREATE FUNCTION ofarm.backend_incarnation_is_live(
    pg_catalog.int4,
    pg_catalog.timestamptz
)
RETURNS pg_catalog.bool
LANGUAGE sql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'SELECT TRUE';

CREATE FUNCTION ofarm.validate_promotion_edge()
RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN RETURN NEW; END';

CREATE FUNCTION ofarm.require_promotion_reachability()
RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN RETURN NEW; END';

CREATE FUNCTION ofarm.take_tenant_write_lock()
RETURNS pg_catalog.void
LANGUAGE sql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'SELECT pg_catalog.pg_sleep(0)';

REVOKE ALL PRIVILEGES ON FUNCTION ofarm.take_tenant_write_lock()
FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ofarm.take_tenant_write_lock()
TO ofarm_app, ofarm_worker;

CREATE TABLE ofarm.migration_runner_probe (
    probe_id pg_catalog.int4 PRIMARY KEY,
    value pg_catalog.text NOT NULL
);
"""
    existing_routine_identities = {
        ("create_tenant_challenge", ()),
        ("current_tenant_id", ()),
        ("current_backend_start", ()),
        (
            "backend_incarnation_is_live",
            ("integer", "timestamp with time zone"),
        ),
        ("validate_promotion_edge", ()),
        ("require_promotion_reachability", ()),
        ("take_tenant_write_lock", ()),
    }
    sealer = TENANT_PROVISIONING_SPEC.tenant_initial_owner_sealer
    assert sealer is not None
    for transfer in sealer.transfers:
        identity = (transfer.function_name, transfer.argument_types)
        if identity in existing_routine_identities:
            continue
        source += (
            f"""
CREATE FUNCTION {transfer.qualified_identity}
RETURNS pg_catalog.void
LANGUAGE sql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT pg_catalog.pg_sleep(0)';
"""
        ).encode("ascii")
    return source


def _run(
    target: _TenantTarget,
    migration_set: MigrationSet,
    *,
    execution_id: UUID | None = None,
    release_identity: str = RELEASE_IDENTITY,
    spec: ProvisioningSpec = TENANT_PROVISIONING_SPEC,
) -> MigrationRunReport:
    return migrate_service(
        admin_dsn=target.admin_dsn,
        migrator_dsn=target.migrator_dsn,
        spec=spec,
        migration_set=migration_set,
        release_identity=release_identity,
        execution_id=execution_id or uuid4(),
    )


def _ledger_rows(target: _TenantTarget) -> list[tuple[object, ...]]:
    with psycopg.connect(target.target_admin_dsn) as connection:
        return connection.execute(
            """
            SELECT version,
                   filename,
                   source_sha256,
                   source_byte_length,
                   applied_prefix_digest,
                   service_identity,
                   provisioning_spec_digest,
                   release_identity,
                   execution_id::text
            FROM ofarm.schema_migration
            ORDER BY version
            """
        ).fetchall()


def _relation_exists(target: _TenantTarget, qualified_name: str) -> bool:
    with psycopg.connect(target.target_admin_dsn) as connection:
        return connection.execute(
            "SELECT pg_catalog.to_regclass(%s) IS NOT NULL",
            (qualified_name,),
        ).fetchone()[0]


def _tamper_ledger_value(
    target: _TenantTarget,
    column: str,
    value: str,
    *,
    drop_fixed_constraint: bool,
) -> None:
    with psycopg.connect(target.target_admin_dsn, autocommit=True) as connection:
        if drop_fixed_constraint:
            constraints = connection.execute(
                """
                SELECT constraint_name.conname::text
                FROM pg_catalog.pg_constraint AS constraint_name
                WHERE constraint_name.conrelid =
                      'ofarm.schema_migration'::pg_catalog.regclass
                  AND constraint_name.contype = 'c'
                  AND pg_catalog.pg_get_constraintdef(
                          constraint_name.oid,
                          true
                      ) LIKE %s
                ORDER BY constraint_name.conname
                """,
                (f"%{column}%",),
            ).fetchall()
            assert constraints, f"no ledger constraint governs {column}"
            for (constraint_name,) in constraints:
                connection.execute(
                    sql.SQL(
                        "ALTER TABLE ofarm.schema_migration DROP CONSTRAINT {}"
                    ).format(sql.Identifier(constraint_name))
                )
        connection.execute(
            "ALTER TABLE ofarm.schema_migration "
            "DISABLE TRIGGER schema_migration_reject_update_delete"
        )
        connection.execute(
            sql.SQL(
                "UPDATE ofarm.schema_migration SET {} = %s WHERE version = 1"
            ).format(sql.Identifier(column)),
            (value,),
        )
        connection.execute(
            "ALTER TABLE ofarm.schema_migration "
            "ENABLE TRIGGER schema_migration_reject_update_delete"
        )


def test_source_validator_ignores_prohibited_words_inside_lexical_bodies():
    source = b"""
-- BEGIN; COMMIT; COPY hidden FROM STDIN;
/* ROLLBACK; /* SET ROLE hidden; */ SAVEPOINT hidden; */
SELECT 'START TRANSACTION; RESET ROLE;';
SELECT "COMMIT" FROM (SELECT 1 AS "COMMIT") AS quoted_identifier;
SELECT $body$PREPARE TRANSACTION 'hidden'; \\i hidden.sql$body$;
CREATE FUNCTION ofarm.example() RETURNS pg_catalog.void
LANGUAGE plpgsql AS $function$
BEGIN
    PERFORM 'ROLLBACK PREPARED';
END
$function$;
"""

    assert validate_migration_source(source, "0001_initial.sql") == source.decode(
        "utf-8"
    )


@pytest.mark.parametrize(
    "source",
    (
        b"BEGIN;",
        b"START TRANSACTION;",
        b"COMMIT;",
        b"END;",
        b"ROLLBACK;",
        b"ABORT;",
        b"SAVEPOINT migration_step;",
        b"RELEASE SAVEPOINT migration_step;",
        b"PREPARE TRANSACTION 'migration_step';",
        b"COMMIT PREPARED 'migration_step';",
        b"ROLLBACK PREPARED 'migration_step';",
        b"SET ROLE ofarm_owner;",
        b"RESET ROLE;",
        b"SET SESSION AUTHORIZATION ofarm_owner;",
        b"SET LOCAL SESSION AUTHORIZATION ofarm_owner;",
        b"RESET SESSION AUTHORIZATION;",
        b"SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;",
        b"SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY;",
        b"SET LOCAL synchronous_commit = off;",
        b"RESET ALL;",
        b"COPY ofarm.example FROM STDIN;",
        b"\\i hidden.sql\n",
        b"SELECT 1; -- hidden only until CR\rCOMMIT;",
    ),
)
def test_source_validator_rejects_runner_owned_or_client_side_control(
    source: bytes,
):
    with pytest.raises(MigrationInputError):
        validate_migration_source(source, "0001_initial.sql")


@pytest.mark.parametrize("source", (b"-- comment only\r", b"/* only */; ;"))
def test_source_validator_rejects_sources_without_a_sql_statement(source: bytes):
    with pytest.raises(MigrationInputError, match="no SQL statement"):
        validate_migration_source(source, "0001_initial.sql")


def test_cr_line_comment_control_refuses_before_any_target_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {
            "0001_initial.sql": (
                b"CREATE TABLE ofarm.partial (id pg_catalog.int4); "
                b"-- only until CR\rCOMMIT;"
            )
        },
    )

    def target_must_not_be_observed(*_args, **_kwargs):
        raise AssertionError("target was observed before SQL preflight completed")

    monkeypatch.setattr(
        migration_runner_module,
        "verify_service_infrastructure",
        target_must_not_be_observed,
    )
    with pytest.raises(MigrationInputError, match="runner-owned SQL control"):
        migrate_service(
            admin_dsn="must-not-connect",
            migrator_dsn="must-not-connect",
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=migration_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )


def test_public_runner_refuses_synthetic_history_before_target_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )

    def target_must_not_be_observed(*_args, **_kwargs):
        raise AssertionError("target was observed before release authentication")

    monkeypatch.setattr(
        migration_runner_module,
        "verify_service_infrastructure",
        target_must_not_be_observed,
    )
    with pytest.raises(MigrationInputError, match="authoritative release history"):
        migrate_authoritative_service(
            admin_dsn="must-not-connect",
            migrator_dsn="must-not-connect",
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=migration_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )


def test_test_executor_refuses_tenant_migration_0008_before_target_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    filenames = ["0001_initial.sql"] + [
        f"{version:04d}_synthetic.sql" for version in range(2, 8)
    ] + ["0008_tenant_command_runtime_bundle_selection.sql"]
    migration_set = _load_synthetic_set(
        tmp_path,
        {
            filename: f"SELECT {version};\n".encode("ascii")
            for version, filename in enumerate(filenames, start=1)
        },
    )

    def target_must_not_be_observed(*_args, **_kwargs):
        raise AssertionError("test executor observed a target for migration 0008")

    monkeypatch.setattr(
        migration_runner_module,
        "verify_service_infrastructure",
        target_must_not_be_observed,
    )
    with pytest.raises(
        MigrationInputError,
        match="test migration executor cannot execute tenant migration 0008",
    ):
        migrate_service(
            admin_dsn="must-not-connect",
            migrator_dsn="must-not-connect",
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=migration_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )


def test_tenant_v8_branch_is_ordered_and_reauthenticates_literal_set() -> None:
    source = inspect.getsource(migration_runner_module._migrate_service)
    execute_at = source.index("connection.execute(source_text)")
    intrans_at = source.index("TransactionStatus.INTRANS", execute_at)
    branch_at = source.index("observed_version == 7", intrans_at)
    reauthenticate_at = source.index(
        "require_authoritative_migration_set(migration_set)",
        branch_at,
    )
    private_verifier_at = source.index(
        "_locked_tenant_v8_post_source_boundary_differences",
        reauthenticate_at,
    )
    ledger_append_at = source.index("_insert_ledger_row(", private_verifier_at)

    assert execute_at < intrans_at < branch_at
    assert branch_at < reauthenticate_at < private_verifier_at < ledger_append_at
    assert "verify_final_structure" not in source[branch_at:private_verifier_at]
    assert "_TENANT_SELECTION_ACTIVATION_MIGRATION_FILENAME" in source[
        branch_at:reauthenticate_at
    ]
    testing_source = inspect.getsource(
        migration_runner_module._migrate_service_for_testing
    )
    assert "cannot execute tenant migration 0008" in testing_source
    assert (
        "_locked_tenant_v8_post_source_boundary_differences"
        not in testing_source
    )


def test_applies_exact_0001_then_verifies_a_noop_without_creating_the_ledger(
    tenant_target: _TenantTarget,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )

    def _runner_must_not_create_ledger(_spec: ProvisioningSpec) -> str:
        raise AssertionError("the runner called the test-only ledger DDL helper")

    monkeypatch.setattr(
        migration_runner_module,
        "initial_ledger_sql",
        _runner_must_not_create_ledger,
    )
    first_execution_id = uuid4()
    report = _run(
        tenant_target,
        migration_set,
        execution_id=first_execution_id,
    )

    assert report.service_identity == TENANT_SERVICE.identity
    assert report.provisioning_spec_digest == TENANT_PROVISIONING_SPEC.digest
    assert report.migration_set_digest == migration_set.digest
    assert report.database_name == TENANT_PROVISIONING_SPEC.database_name
    assert report.system_identifier.isdigit()
    assert report.server_version_num == SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM
    assert report.previous_version == 0
    assert report.final_version == 1
    assert report.applied_versions == (1,)
    assert report.execution_id == first_execution_id
    assert report.observed_head_execution_id == first_execution_id
    assert report.verified_noop is False
    assert _relation_exists(tenant_target, "ofarm.migration_runner_probe")
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        assert connection.execute(
            "SELECT pg_catalog.to_regprocedure("
            "'ofarm_infrastructure.seal_tenant_routine_owners()') IS NULL"
        ).fetchone() == (True,)
        sealer = TENANT_PROVISIONING_SPEC.tenant_initial_owner_sealer
        assert sealer is not None
        transfer_names = sorted(
            {transfer.function_name for transfer in sealer.transfers}
        )
        assert connection.execute(
            """
            SELECT routine.proname::text,
                   pg_catalog.pg_get_function_identity_arguments(routine.oid),
                   owner.rolname::text
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
            WHERE namespace.nspname = 'ofarm'
              AND routine.proname = ANY (%s::text[])
            ORDER BY 1, 2
            """,
            (transfer_names,),
        ).fetchall() == sorted(
            (
                transfer.function_name,
                transfer.identity_arguments,
                transfer.owner_role,
            )
            for transfer in sealer.transfers
        )
    assert _ledger_rows(tenant_target) == [
        (
            1,
            "0001_initial.sql",
            migration_set.migrations[0].source_sha256,
            migration_set.migrations[0].byte_length,
            migration_set.prefix_digest(1),
            TENANT_SERVICE.identity,
            TENANT_PROVISIONING_SPEC.digest,
            RELEASE_IDENTITY,
            str(first_execution_id),
        )
    ]

    def _noop_must_not_use_write_commit(*_args, **_kwargs):
        raise AssertionError("verified no-op used the migration commit path")

    monkeypatch.setattr(
        migration_runner_module,
        "_commit",
        _noop_must_not_use_write_commit,
    )
    second_execution_id = uuid4()
    noop = _run(
        tenant_target,
        migration_set,
        execution_id=second_execution_id,
    )
    assert noop.previous_version == noop.final_version == 1
    assert noop.applied_versions == ()
    assert noop.execution_id == second_execution_id
    assert noop.observed_head_execution_id == first_execution_id
    assert noop.verified_noop is True
    assert _ledger_rows(tenant_target)[0][-1] == str(first_execution_id)
    for mutation in (
        "UPDATE ofarm.schema_migration SET release_identity = 'changed'",
        "DELETE FROM ofarm.schema_migration",
        "TRUNCATE TABLE ofarm.schema_migration",
    ):
        with psycopg.connect(
            tenant_target.target_admin_dsn,
            autocommit=True,
        ) as connection:
            with pytest.raises(
                psycopg.errors.ObjectNotInPrerequisiteState,
                match="append-only",
            ):
                connection.execute(mutation)
    assert len(_ledger_rows(tenant_target)) == 1


def test_commit_phase_interrupt_has_an_explicit_unknown_outcome(tmp_path: Path):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": b"SELECT 1;"},
    )
    migration = migration_set.migrations[0]
    execution_id = uuid4()

    class InterruptedCommit:
        def commit(self):
            raise KeyboardInterrupt

    with pytest.raises(MigrationOutcomeUnknown) as raised:
        migration_runner_module._commit(
            InterruptedCommit(),
            migration,
            execution_id,
        )

    assert raised.value.execution_id == execution_id
    assert raised.value.version == 1


def test_v5_capsule_requires_the_complete_current_runner_row() -> None:
    migration_set = load_migration_set(
        Path(__file__).resolve().parents[2],
        TENANT_SERVICE,
    )
    migration = migration_set.migrations[4]
    release_identity = "ofarm-tests/issue-176-v5-row"
    execution_id = uuid4()
    exact_row = (
        5,
        "0005_tenant_binding_selection_control_admission.sql",
        migration.source_sha256,
        migration.byte_length,
        migration_set.prefix_digest(5),
        TENANT_SERVICE.identity,
        TENANT_PROVISIONING_SPEC.digest,
        release_identity,
        execution_id,
    )

    class RowConnection:
        def __init__(self, row):
            self.row = row

        def execute(self, _statement):
            return self

        def fetchone(self):
            return self.row

    _authenticate_tenant_binding_selection_control_admission_row(
        RowConnection(exact_row),  # type: ignore[arg-type]
        TENANT_PROVISIONING_SPEC,
        migration_set,
        migration,
        release_identity,
        execution_id,
    )

    wrong_values = (
        4,
        "0005_wrong.sql",
        "sha256:" + "0" * 64,
        migration.byte_length + 1,
        "sha256:" + "1" * 64,
        SECURITY_AUDIT_SERVICE.identity,
        "sha256:" + "2" * 64,
        "ofarm-tests/other-release",
        uuid4(),
    )
    for index, wrong_value in enumerate(wrong_values):
        wrong_row = list(exact_row)
        wrong_row[index] = wrong_value
        with pytest.raises(
            MigrationDirtyError,
            match="admission row is not exact",
        ):
            _authenticate_tenant_binding_selection_control_admission_row(
                RowConnection(tuple(wrong_row)),  # type: ignore[arg-type]
                TENANT_PROVISIONING_SPEC,
                migration_set,
                migration,
                release_identity,
                execution_id,
            )


def test_v6_capsule_requires_all_nine_current_runner_row_fields() -> None:
    migration_set = load_migration_set(
        Path(__file__).resolve().parents[2],
        TENANT_SERVICE,
    )
    migration = migration_set.migrations[5]
    release_identity = "ofarm-tests/issue-176-v6-row"
    execution_id = uuid4()
    exact_row = (
        6,
        "0006_tenant_current_context_selection_owner_admission.sql",
        migration.source_sha256,
        migration.byte_length,
        migration_set.prefix_digest(6),
        TENANT_SERVICE.identity,
        TENANT_PROVISIONING_SPEC.digest,
        release_identity,
        execution_id,
    )

    class RowConnection:
        def __init__(self, row):
            self.row = row

        def execute(self, _statement):
            return self

        def fetchone(self):
            return self.row

    _authenticate_tenant_current_context_selection_owner_admission_row(
        RowConnection(exact_row),  # type: ignore[arg-type]
        TENANT_PROVISIONING_SPEC,
        migration_set,
        migration,
        release_identity,
        execution_id,
    )

    wrong_values = (
        5,
        "0006_wrong.sql",
        "sha256:" + "0" * 64,
        migration.byte_length + 1,
        "sha256:" + "1" * 64,
        SECURITY_AUDIT_SERVICE.identity,
        "sha256:" + "2" * 64,
        "ofarm-tests/other-release",
        uuid4(),
    )
    for index, wrong_value in enumerate(wrong_values):
        wrong_row = list(exact_row)
        wrong_row[index] = wrong_value
        with pytest.raises(
            MigrationDirtyError,
            match="admission row is not exact",
        ):
            _authenticate_tenant_current_context_selection_owner_admission_row(
                RowConnection(tuple(wrong_row)),  # type: ignore[arg-type]
                TENANT_PROVISIONING_SPEC,
                migration_set,
                migration,
                release_identity,
                execution_id,
            )


def test_v7_capsule_requires_all_nine_current_runner_row_fields() -> None:
    migration_set = load_migration_set(
        Path(__file__).resolve().parents[2],
        TENANT_SERVICE,
    )
    migration = migration_set.migrations[6]
    release_identity = "ofarm-tests/issue-176-v7-row"
    execution_id = uuid4()
    exact_row = (
        7,
        "0007_tenant_write_lock_selection_owner_admission.sql",
        migration.source_sha256,
        migration.byte_length,
        migration_set.prefix_digest(7),
        TENANT_SERVICE.identity,
        TENANT_PROVISIONING_SPEC.digest,
        release_identity,
        execution_id,
    )

    class RowConnection:
        def __init__(self, row):
            self.row = row

        def execute(self, _statement):
            return self

        def fetchone(self):
            return self.row

    _authenticate_tenant_write_lock_selection_owner_admission_row(
        RowConnection(exact_row),  # type: ignore[arg-type]
        TENANT_PROVISIONING_SPEC,
        migration_set,
        migration,
        release_identity,
        execution_id,
    )

    wrong_values = (
        6,
        "0007_wrong.sql",
        "sha256:" + "0" * 64,
        migration.byte_length + 1,
        "sha256:" + "1" * 64,
        SECURITY_AUDIT_SERVICE.identity,
        "sha256:" + "2" * 64,
        "ofarm-tests/other-release",
        uuid4(),
    )
    for index, wrong_value in enumerate(wrong_values):
        wrong_row = list(exact_row)
        wrong_row[index] = wrong_value
        with pytest.raises(
            MigrationDirtyError,
            match="admission row is not exact",
        ):
            _authenticate_tenant_write_lock_selection_owner_admission_row(
                RowConnection(tuple(wrong_row)),  # type: ignore[arg-type]
                TENANT_PROVISIONING_SPEC,
                migration_set,
                migration,
                release_identity,
                execution_id,
            )


def test_v5_precommit_failure_restores_v4_capsule_and_absent_grants(
    tenant_target: _TenantTarget,
    monkeypatch,
) -> None:
    full_set = load_migration_set(
        Path(__file__).resolve().parents[2],
        TENANT_SERVICE,
    )
    v5_set = MigrationSet(
        service=TENANT_SERVICE,
        migrations=full_set.migrations[:5],
        digest=full_set.prefix_digest(5),
    )
    v4_set = MigrationSet(
        service=TENANT_SERVICE,
        migrations=full_set.migrations[:4],
        digest=full_set.prefix_digest(4),
    )
    migrate_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=v4_set,
        release_identity=RELEASE_IDENTITY + "-v4-prefix",
        execution_id=uuid4(),
    )

    original_consume = (
        migration_runner_module
        ._consume_tenant_binding_selection_control_admission_sealer
    )

    def refuse_after_capsule(*args, **kwargs):
        original_consume(*args, **kwargs)
        raise MigrationDirtyError("injected V5 final verification refusal")

    monkeypatch.setattr(
        migration_runner_module,
        "_consume_tenant_binding_selection_control_admission_sealer",
        refuse_after_capsule,
    )
    with pytest.raises(
        MigrationDirtyError,
        match="injected V5 final verification refusal",
    ):
        migrate_service(
            admin_dsn=tenant_target.admin_dsn,
            migrator_dsn=tenant_target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=v5_set,
            release_identity=RELEASE_IDENTITY + "-v5-refusal",
            execution_id=uuid4(),
        )
    monkeypatch.setattr(
        migration_runner_module,
        "_consume_tenant_binding_selection_control_admission_sealer",
        original_consume,
    )

    sealer = (
        TENANT_PROVISIONING_SPEC
        .tenant_binding_selection_control_admission_sealer
    )
    assert sealer is not None
    with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
        assert admin.execute(
            "SELECT pg_catalog.count(*), pg_catalog.max(version) "
            "FROM ofarm.schema_migration"
        ).fetchone() == (4, 4)
        assert admin.execute(
            """
            SELECT owner.rolsuper,
                   pg_catalog.left(owner.rolname::text, 6) = 'ofarm_',
                   routine.prosecdef,
                   routine.prosrc
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
            WHERE namespace.nspname = %s
              AND routine.proname = %s
              AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = ''
            """,
            (sealer.schema_name, sealer.function_name),
        ).fetchone() == (True, False, True, sealer.source)
        assert admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            CROSS JOIN LATERAL pg_catalog.aclexplode(routine.proacl) AS acl
            JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
            WHERE namespace.nspname = 'ofarm'
              AND grantee.rolname =
                    'ofarm_command_runtime_bundle_selection_controller'
            """
        ).fetchone() == (0,)
        admin.execute(
            "GRANT EXECUTE ON FUNCTION "
            "ofarm.create_tenant_challenge() TO "
            "ofarm_command_runtime_bundle_selection_controller"
        )
        with pytest.raises(
            MigrationTargetError,
            match="tenant binding selection-control admission ACL differs",
        ):
            migrate_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=tenant_target.migrator_dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=v5_set,
                release_identity=RELEASE_IDENTITY + "-v4-with-grant",
                execution_id=uuid4(),
            )
        assert admin.execute(
            "SELECT pg_catalog.count(*), pg_catalog.max(version) "
            "FROM ofarm.schema_migration"
        ).fetchone() == (4, 4)
        admin.execute(
            "REVOKE EXECUTE ON FUNCTION "
            "ofarm.create_tenant_challenge() FROM "
            "ofarm_command_runtime_bundle_selection_controller"
        )
        admin.execute(
            sql.SQL("DROP FUNCTION {}()").format(
                sql.Identifier(sealer.schema_name, sealer.function_name)
            )
        )

    with pytest.raises(MigrationTargetError, match="sealer differs"):
        migrate_service(
            admin_dsn=tenant_target.admin_dsn,
            migrator_dsn=tenant_target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=v5_set,
            release_identity=RELEASE_IDENTITY + "-v4-missing-capsule",
            execution_id=uuid4(),
        )


def test_v5_precommit_backend_loss_reconnects_from_exact_v4(
    tenant_target: _TenantTarget,
    monkeypatch,
) -> None:
    full_set = load_migration_set(
        Path(__file__).resolve().parents[2],
        TENANT_SERVICE,
    )
    v5_set = MigrationSet(
        service=TENANT_SERVICE,
        migrations=full_set.migrations[:5],
        digest=full_set.prefix_digest(5),
    )
    v4_set = MigrationSet(
        service=TENANT_SERVICE,
        migrations=full_set.migrations[:4],
        digest=full_set.prefix_digest(4),
    )
    migrate_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=v4_set,
        release_identity=RELEASE_IDENTITY + "-disconnect-v4-prefix",
        execution_id=uuid4(),
    )

    original_commit = migration_runner_module._commit

    def terminate_backend_at_commit(connection, migration, execution_id):
        with psycopg.connect(
            tenant_target.target_admin_dsn,
            autocommit=True,
        ) as admin:
            terminated = admin.execute(
                "SELECT pg_catalog.pg_terminate_backend(%s)",
                (connection.info.backend_pid,),
            ).fetchone()
        assert terminated == (True,)
        original_commit(connection, migration, execution_id)

    monkeypatch.setattr(
        migration_runner_module,
        "_commit",
        terminate_backend_at_commit,
    )
    uncertain_execution_id = uuid4()
    with pytest.raises(MigrationOutcomeUnknown) as uncertain:
        migrate_service(
            admin_dsn=tenant_target.admin_dsn,
            migrator_dsn=tenant_target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=v5_set,
            release_identity=RELEASE_IDENTITY + "-disconnect-unknown",
            execution_id=uncertain_execution_id,
        )
    assert uncertain.value.version == 5
    assert uncertain.value.execution_id == uncertain_execution_id

    sealer = (
        TENANT_PROVISIONING_SPEC
        .tenant_binding_selection_control_admission_sealer
    )
    assert sealer is not None
    with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
        assert admin.execute(
            "SELECT pg_catalog.count(*), pg_catalog.max(version) "
            "FROM ofarm.schema_migration"
        ).fetchone() == (4, 4)
        assert admin.execute(
            "SELECT pg_catalog.to_regprocedure(%s) IS NOT NULL",
            (sealer.qualified_function + "()",),
        ).fetchone() == (True,)
        assert admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            CROSS JOIN LATERAL pg_catalog.aclexplode(routine.proacl) AS acl
            JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
            WHERE namespace.nspname = 'ofarm'
              AND grantee.rolname =
                    'ofarm_command_runtime_bundle_selection_controller'
            """
        ).fetchone() == (0,)

    monkeypatch.setattr(migration_runner_module, "_commit", original_commit)
    recovered = migrate_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=v5_set,
        release_identity=RELEASE_IDENTITY + "-disconnect-recovered",
        execution_id=uuid4(),
    )
    assert recovered.previous_version == 4
    assert recovered.applied_versions == (5,)
    assert recovered.final_version == 5

    with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
        assert admin.execute(
            "SELECT pg_catalog.count(*), pg_catalog.max(version) "
            "FROM ofarm.schema_migration"
        ).fetchone() == (5, 5)
        assert admin.execute(
            "SELECT pg_catalog.to_regprocedure(%s) IS NULL",
            (sealer.qualified_function + "()",),
        ).fetchone() == (True,)
        assert admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            CROSS JOIN LATERAL pg_catalog.aclexplode(routine.proacl) AS acl
            JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
            WHERE namespace.nspname = 'ofarm'
              AND grantee.rolname =
                    'ofarm_command_runtime_bundle_selection_controller'
            """
        ).fetchone() == (2,)


def test_v5_postcommit_acknowledgement_loss_reconnects_as_verified_noop(
    tenant_target: _TenantTarget,
) -> None:
    full_set = load_migration_set(
        Path(__file__).resolve().parents[2],
        TENANT_SERVICE,
    )
    v5_set = MigrationSet(
        service=TENANT_SERVICE,
        migrations=full_set.migrations[:5],
        digest=full_set.prefix_digest(5),
    )
    v4_set = MigrationSet(
        service=TENANT_SERVICE,
        migrations=full_set.migrations[:4],
        digest=full_set.prefix_digest(4),
    )
    migrate_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=v4_set,
        release_identity=RELEASE_IDENTITY + "-ack-loss-v4-prefix",
        execution_id=uuid4(),
    )

    proxy = _CommitAcknowledgementDropProxy(tenant_target.migrator_dsn)
    proxy.start()
    uncertain_execution_id = uuid4()
    try:
        with pytest.raises(MigrationOutcomeUnknown) as uncertain:
            migrate_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=proxy.dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=v5_set,
                release_identity=RELEASE_IDENTITY + "-ack-loss-unknown",
                execution_id=uncertain_execution_id,
            )
        assert uncertain.value.version == 5
        assert uncertain.value.execution_id == uncertain_execution_id
    finally:
        proxy.close()
    assert proxy.acknowledgement_dropped.is_set()

    sealer = (
        TENANT_PROVISIONING_SPEC
        .tenant_binding_selection_control_admission_sealer
    )
    assert sealer is not None
    with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
        assert admin.execute(
            "SELECT pg_catalog.count(*), pg_catalog.max(version), "
            "(SELECT execution_id FROM ofarm.schema_migration "
            "WHERE version = 5) "
            "FROM ofarm.schema_migration"
        ).fetchone() == (5, 5, uncertain_execution_id)
        assert admin.execute(
            "SELECT pg_catalog.to_regprocedure(%s) IS NULL",
            (sealer.qualified_function + "()",),
        ).fetchone() == (True,)
        assert admin.execute(
            """
            SELECT routine.proname::text,
                   pg_catalog.oidvectortypes(routine.proargtypes),
                   grantee.rolname::text,
                   pg_catalog.pg_get_userbyid(acl.grantor),
                   acl.privilege_type,
                   acl.is_grantable
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            CROSS JOIN LATERAL pg_catalog.aclexplode(routine.proacl) AS acl
            JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
            WHERE namespace.nspname = 'ofarm'
              AND grantee.rolname =
                    'ofarm_command_runtime_bundle_selection_controller'
            ORDER BY 1, 2, 3, 4, 5, 6
            """
        ).fetchall() == [
            (
                "bind_tenant_capability",
                "text",
                "ofarm_command_runtime_bundle_selection_controller",
                "ofarm_binder",
                "EXECUTE",
                False,
            ),
            (
                "create_tenant_challenge",
                "",
                "ofarm_command_runtime_bundle_selection_controller",
                "ofarm_binder",
                "EXECUTE",
                False,
            ),
        ]
    retry_execution_id = uuid4()
    recovered = migrate_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=v5_set,
        release_identity=RELEASE_IDENTITY + "-ack-loss-reconnect",
        execution_id=retry_execution_id,
    )
    assert recovered.previous_version == 5
    assert recovered.applied_versions == ()
    assert recovered.final_version == 5
    assert recovered.execution_id == retry_execution_id
    assert recovered.observed_head_execution_id == uncertain_execution_id
    assert recovered.verified_noop is True

    with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
        assert admin.execute(
            "SELECT pg_catalog.count(*), pg_catalog.max(version), "
            "(SELECT execution_id FROM ofarm.schema_migration "
            "WHERE version = 5) "
            "FROM ofarm.schema_migration"
        ).fetchone() == (5, 5, uncertain_execution_id)


def _advance_tenant_target_to_v5(
    tenant_target: _TenantTarget,
) -> MigrationSet:
    full_set = load_migration_set(
        Path(__file__).resolve().parents[2],
        TENANT_SERVICE,
    )
    v5_set = MigrationSet(
        service=TENANT_SERVICE,
        migrations=full_set.migrations[:5],
        digest=full_set.prefix_digest(5),
    )
    migrate_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=v5_set,
        release_identity=RELEASE_IDENTITY + "-v5-prefix",
        execution_id=uuid4(),
    )
    return MigrationSet(
        service=TENANT_SERVICE,
        migrations=full_set.migrations[:6],
        digest=full_set.prefix_digest(6),
    )


def _current_context_owner_admission_state(
    target_admin_dsn: str,
) -> tuple[tuple[int, int], bool, list[tuple[object, ...]]]:
    sealer = (
        TENANT_PROVISIONING_SPEC
        .tenant_current_context_selection_owner_admission_sealer
    )
    assert sealer is not None
    with psycopg.connect(target_admin_dsn, autocommit=True) as admin:
        ledger = admin.execute(
            "SELECT pg_catalog.count(*), pg_catalog.max(version) "
            "FROM ofarm.schema_migration"
        ).fetchone()
        capsule_present = admin.execute(
            "SELECT pg_catalog.to_regprocedure(%s) IS NOT NULL",
            (sealer.qualified_function + "()",),
        ).fetchone()[0]
        rows = admin.execute(
            """
            SELECT routine.proname::text,
                   pg_catalog.oidvectortypes(routine.proargtypes),
                   grantee.rolname::text,
                   pg_catalog.pg_get_userbyid(acl.grantor),
                   acl.privilege_type,
                   acl.is_grantable
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(
                    routine.proacl,
                    pg_catalog.acldefault('f', routine.proowner)
                )
            ) AS acl
            JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
            WHERE namespace.nspname = 'ofarm'
              AND routine.proname = ANY (%s::text[])
              AND pg_catalog.oidvectortypes(routine.proargtypes) = ''
              AND grantee.rolname = ANY (%s::text[])
            ORDER BY 1, 2, 3, 4, 5, 6
            """,
            (
                ["current_authenticated_principal_ref", "current_tenant_id"],
                [
                    "ofarm_owner",
                    "ofarm_command_runtime_bundle_selection_controller",
                    "ofarm_command_runtime_bundle_selection_control_login",
                    "ofarm_migrator",
                ],
            ),
        ).fetchall()
    return tuple(ledger), capsule_present, [tuple(row) for row in rows]


_EXPECTED_CURRENT_CONTEXT_OWNER_ADMISSION = [
    (
        "current_authenticated_principal_ref",
        "",
        "ofarm_owner",
        "ofarm_binder",
        "EXECUTE",
        False,
    ),
    (
        "current_tenant_id",
        "",
        "ofarm_owner",
        "ofarm_binder",
        "EXECUTE",
        False,
    ),
]


_V6_LEDGER_FIELDS = (
    "version",
    "filename",
    "source_sha256",
    "source_byte_length",
    "applied_prefix_digest",
    "service_identity",
    "provisioning_spec_digest",
    "release_identity",
    "execution_id",
)


@pytest.mark.parametrize("substituted_field", _V6_LEDGER_FIELDS)
def test_v6_live_ledger_substitution_refuses_before_capsule_use(
    tenant_target: _TenantTarget,
    substituted_field: str,
) -> None:
    _advance_tenant_target_to_v5(tenant_target)
    full_set = load_authoritative_migration_set(
        Path(__file__).resolve().parents[2],
        TENANT_SERVICE,
    )
    assert _current_context_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((5, 5), True, [])

    proxy = _V6LedgerBindSubstitutionProxy(
        tenant_target.migrator_dsn,
        substituted_field,
    )
    proxy.start()
    try:
        if substituted_field == "version":
            expected_error = pytest.raises(
                MigrationExecutionError,
                match="schema_migration_filename_check",
            )
        elif substituted_field == "service_identity":
            expected_error = pytest.raises(
                MigrationExecutionError,
                match="schema_migration_service_check",
            )
        elif substituted_field in {"release_identity", "execution_id"}:
            expected_error = pytest.raises(
                MigrationDirtyError,
                match=(
                    "tenant current-context selection-owner admission row "
                    "is not exact"
                ),
            )
        else:
            expected_error = pytest.raises(
                MigrationDirtyError,
                match="migration history is not the exact local prefix",
            )
        with expected_error:
            migrate_authoritative_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=proxy.dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=full_set,
                release_identity=RELEASE_IDENTITY + "-v6-substitution",
                execution_id=uuid4(),
            )
    finally:
        proxy.close()

    assert proxy.parameter_substituted.is_set()
    assert _current_context_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((5, 5), True, [])
    verified = verify_service_infrastructure(
        tenant_target.admin_dsn,
        TENANT_PROVISIONING_SPEC,
    )
    assert verified.provisioning_spec_digest == TENANT_PROVISIONING_SPEC.digest


def test_v7_capsule_refuses_an_absent_write_lock_target() -> None:
    migration_set = load_authoritative_migration_set(
        Path(__file__).resolve().parents[2],
        TENANT_SERVICE,
    )
    malformed_spec = replace(
        TENANT_PROVISIONING_SPEC,
        tenant_write_lock=None,
    )

    with pytest.raises(
        MigrationDirtyError,
        match="tenant write-lock selection-owner admission target is absent",
    ):
        migration_runner_module._consume_tenant_write_lock_selection_owner_admission_sealer(
            object(),  # type: ignore[arg-type]
            malformed_spec,
            migration_set.migrations[6],
        )


def test_v6_row_is_authenticated_before_and_after_capsule_consumption(
    tenant_target: _TenantTarget,
    monkeypatch,
) -> None:
    full_set = _advance_tenant_target_to_v5(tenant_target)
    sealer = (
        TENANT_PROVISIONING_SPEC
        .tenant_current_context_selection_owner_admission_sealer
    )
    assert sealer is not None
    events: list[object] = []
    authentication_count = 0
    transition_verified = False
    original_authenticate = (
        migration_runner_module
        ._authenticate_tenant_current_context_selection_owner_admission_row
    )
    original_consume = (
        migration_runner_module
        ._consume_tenant_current_context_selection_owner_admission_sealer
    )
    original_boundary = migration_runner_module._locked_boundary_differences

    def trace_authentication(connection, *args, **kwargs):
        nonlocal authentication_count
        original_authenticate(connection, *args, **kwargs)
        authentication_count += 1
        state = connection.execute(
            """
            SELECT CURRENT_USER::text,
                   EXISTS (
                       SELECT 1
                       FROM pg_catalog.pg_proc AS capsule
                       JOIN pg_catalog.pg_namespace AS capsule_namespace
                         ON capsule_namespace.oid = capsule.pronamespace
                       WHERE capsule_namespace.nspname = %s
                         AND capsule.proname = %s
                         AND pg_catalog.pg_get_function_identity_arguments(
                                 capsule.oid
                             ) = ''
                   ),
                   (
                       SELECT pg_catalog.count(*)
                       FROM pg_catalog.pg_proc AS routine
                       JOIN pg_catalog.pg_namespace AS namespace
                         ON namespace.oid = routine.pronamespace
                       CROSS JOIN LATERAL pg_catalog.aclexplode(
                           COALESCE(
                               routine.proacl,
                               pg_catalog.acldefault('f', routine.proowner)
                           )
                       ) AS acl
                       JOIN pg_catalog.pg_roles AS grantee
                         ON grantee.oid = acl.grantee
                       WHERE namespace.nspname = 'ofarm'
                         AND routine.proname = ANY (%s::text[])
                         AND pg_catalog.oidvectortypes(routine.proargtypes) = ''
                         AND grantee.rolname = 'ofarm_owner'
                   )
            """,
            (
                sealer.schema_name,
                sealer.function_name,
                ["current_authenticated_principal_ref", "current_tenant_id"],
            ),
        ).fetchone()
        events.append(("authenticate", *tuple(state or ())))

    def trace_consumption(*args, **kwargs):
        events.append("consume")
        return original_consume(*args, **kwargs)

    def trace_boundary(*args, **kwargs):
        nonlocal transition_verified
        if authentication_count and not transition_verified:
            events.append("boundary")
            transition_verified = True
        return original_boundary(*args, **kwargs)

    monkeypatch.setattr(
        migration_runner_module,
        "_authenticate_tenant_current_context_selection_owner_admission_row",
        trace_authentication,
    )
    monkeypatch.setattr(
        migration_runner_module,
        "_consume_tenant_current_context_selection_owner_admission_sealer",
        trace_consumption,
    )
    monkeypatch.setattr(
        migration_runner_module,
        "_locked_boundary_differences",
        trace_boundary,
    )

    migrated = migrate_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=full_set,
        release_identity=RELEASE_IDENTITY + "-v6-order",
        execution_id=uuid4(),
    )
    assert migrated.applied_versions == (6,)
    assert events == [
        ("authenticate", "ofarm_owner", True, 0),
        "consume",
        ("authenticate", "ofarm_owner", False, 2),
        "boundary",
    ]
    assert _current_context_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((6, 6), False, _EXPECTED_CURRENT_CONTEXT_OWNER_ADMISSION)


def test_v6_precommit_failure_restores_exact_v5_and_mixed_states_refuse(
    tenant_target: _TenantTarget,
    monkeypatch,
) -> None:
    full_set = _advance_tenant_target_to_v5(tenant_target)
    assert _current_context_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((5, 5), True, [])

    original_consume = (
        migration_runner_module
        ._consume_tenant_current_context_selection_owner_admission_sealer
    )

    def refuse_after_capsule(*args, **kwargs):
        original_consume(*args, **kwargs)
        raise MigrationDirtyError("injected V6 final verification refusal")

    monkeypatch.setattr(
        migration_runner_module,
        "_consume_tenant_current_context_selection_owner_admission_sealer",
        refuse_after_capsule,
    )
    with pytest.raises(
        MigrationDirtyError,
        match="injected V6 final verification refusal",
    ):
        migrate_service(
            admin_dsn=tenant_target.admin_dsn,
            migrator_dsn=tenant_target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=full_set,
            release_identity=RELEASE_IDENTITY + "-v6-refusal",
            execution_id=uuid4(),
        )
    monkeypatch.setattr(
        migration_runner_module,
        "_consume_tenant_current_context_selection_owner_admission_sealer",
        original_consume,
    )
    assert _current_context_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((5, 5), True, [])

    with psycopg.connect(
        tenant_target.target_admin_dsn,
        autocommit=True,
    ) as admin:
        admin.execute(
            "GRANT EXECUTE ON FUNCTION ofarm.current_tenant_id() "
            "TO ofarm_owner"
        )
    try:
        with pytest.raises(MigrationTargetError, match="admission ACL differs"):
            migrate_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=tenant_target.migrator_dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=full_set,
                release_identity=RELEASE_IDENTITY + "-v5-one-owner-grant",
                execution_id=uuid4(),
            )
    finally:
        with psycopg.connect(
            tenant_target.target_admin_dsn,
            autocommit=True,
        ) as admin:
            admin.execute(
                "REVOKE EXECUTE ON FUNCTION ofarm.current_tenant_id() "
                "FROM ofarm_owner"
            )

    sealer = (
        TENANT_PROVISIONING_SPEC
        .tenant_current_context_selection_owner_admission_sealer
    )
    assert sealer is not None
    with psycopg.connect(
        tenant_target.target_admin_dsn,
        autocommit=True,
    ) as admin:
        admin.execute(
            sql.SQL("DROP FUNCTION {}()").format(
                sql.Identifier(sealer.schema_name, sealer.function_name)
            )
        )
    with pytest.raises(MigrationTargetError, match="sealer differs"):
        migrate_service(
            admin_dsn=tenant_target.admin_dsn,
            migrator_dsn=tenant_target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=full_set,
            release_identity=RELEASE_IDENTITY + "-v5-missing-v6-capsule",
            execution_id=uuid4(),
        )


def test_v6_precommit_backend_loss_reconnects_from_exact_v5(
    tenant_target: _TenantTarget,
    monkeypatch,
) -> None:
    full_set = _advance_tenant_target_to_v5(tenant_target)
    original_commit = migration_runner_module._commit

    def terminate_backend_at_commit(connection, migration, execution_id):
        with psycopg.connect(
            tenant_target.target_admin_dsn,
            autocommit=True,
        ) as admin:
            terminated = admin.execute(
                "SELECT pg_catalog.pg_terminate_backend(%s)",
                (connection.info.backend_pid,),
            ).fetchone()
        assert terminated == (True,)
        original_commit(connection, migration, execution_id)

    monkeypatch.setattr(
        migration_runner_module,
        "_commit",
        terminate_backend_at_commit,
    )
    uncertain_execution_id = uuid4()
    with pytest.raises(MigrationOutcomeUnknown) as uncertain:
        migrate_service(
            admin_dsn=tenant_target.admin_dsn,
            migrator_dsn=tenant_target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=full_set,
            release_identity=RELEASE_IDENTITY + "-v6-disconnect-unknown",
            execution_id=uncertain_execution_id,
        )
    assert uncertain.value.version == 6
    assert uncertain.value.execution_id == uncertain_execution_id
    assert _current_context_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((5, 5), True, [])

    monkeypatch.setattr(migration_runner_module, "_commit", original_commit)
    recovered = migrate_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=full_set,
        release_identity=RELEASE_IDENTITY + "-v6-disconnect-recovered",
        execution_id=uuid4(),
    )
    assert recovered.previous_version == 5
    assert recovered.applied_versions == (6,)
    assert recovered.final_version == 6
    assert _current_context_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((6, 6), False, _EXPECTED_CURRENT_CONTEXT_OWNER_ADMISSION)


def test_v6_postcommit_acknowledgement_loss_recovers_as_verified_noop(
    tenant_target: _TenantTarget,
) -> None:
    full_set = _advance_tenant_target_to_v5(tenant_target)
    proxy = _CommitAcknowledgementDropProxy(tenant_target.migrator_dsn)
    proxy.start()
    uncertain_execution_id = uuid4()
    try:
        with pytest.raises(MigrationOutcomeUnknown) as uncertain:
            migrate_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=proxy.dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=full_set,
                release_identity=RELEASE_IDENTITY + "-v6-ack-loss-unknown",
                execution_id=uncertain_execution_id,
            )
        assert uncertain.value.version == 6
        assert uncertain.value.execution_id == uncertain_execution_id
    finally:
        proxy.close()
    assert proxy.acknowledgement_dropped.is_set()
    assert _current_context_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((6, 6), False, _EXPECTED_CURRENT_CONTEXT_OWNER_ADMISSION)

    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert admin.execute(
            "SELECT execution_id FROM ofarm.schema_migration WHERE version = 6"
        ).fetchone() == (uncertain_execution_id,)

    retry_execution_id = uuid4()
    recovered = migrate_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=full_set,
        release_identity=RELEASE_IDENTITY + "-v6-ack-loss-reconnect",
        execution_id=retry_execution_id,
    )
    assert recovered.previous_version == 6
    assert recovered.applied_versions == ()
    assert recovered.final_version == 6
    assert recovered.execution_id == retry_execution_id
    assert recovered.observed_head_execution_id == uncertain_execution_id
    assert recovered.verified_noop is True
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert admin.execute(
            "SELECT pg_catalog.count(*), pg_catalog.max(version), "
            "(SELECT execution_id FROM ofarm.schema_migration "
            "WHERE version = 6) FROM ofarm.schema_migration"
        ).fetchone() == (6, 6, uncertain_execution_id)


def _advance_tenant_target_to_v6(
    tenant_target: _TenantTarget,
) -> MigrationSet:
    full_set = load_migration_set(
        Path(__file__).resolve().parents[2],
        TENANT_SERVICE,
    )
    v6_set = MigrationSet(
        service=TENANT_SERVICE,
        migrations=full_set.migrations[:6],
        digest=full_set.prefix_digest(6),
    )
    migrate_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=v6_set,
        release_identity=RELEASE_IDENTITY + "-v6-prefix",
        execution_id=uuid4(),
    )
    return full_set


def _advance_tenant_target_to_v7(
    tenant_target: _TenantTarget,
) -> MigrationSet:
    full_set = _advance_tenant_target_to_v6(tenant_target)
    migrate_authoritative_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=full_set,
        release_identity=RELEASE_IDENTITY + "-v7",
        execution_id=uuid4(),
    )
    return full_set


def _create_selection_activation_routine(
    target_admin_dsn: str,
    *,
    schema_name: str = "ofarm",
    argument_type: str = "text",
    grantees: tuple[str, ...] = (),
) -> None:
    routine_name = (
        "activate_commit_operation_claim_draft_runtime_bundle_selection"
    )
    qualified_routine = sql.Identifier(schema_name, routine_name)
    qualified_argument = sql.Identifier("pg_catalog", argument_type)
    with psycopg.connect(target_admin_dsn, autocommit=True) as admin:
        admin.execute(
            sql.SQL(
                "CREATE FUNCTION {}({}) RETURNS pg_catalog.void "
                "LANGUAGE sql VOLATILE PARALLEL UNSAFE SECURITY INVOKER "
                "SET search_path = pg_catalog, pg_temp "
                "AS 'SELECT pg_catalog.pg_sleep(0)'"
            ).format(qualified_routine, qualified_argument)
        )
        admin.execute(
            sql.SQL("ALTER FUNCTION {}({}) OWNER TO ofarm_owner").format(
                qualified_routine,
                qualified_argument,
            )
        )
        admin.execute("SET ROLE ofarm_owner")
        admin.execute(
            sql.SQL(
                "REVOKE ALL PRIVILEGES ON FUNCTION {}({}) FROM PUBLIC"
            ).format(qualified_routine, qualified_argument)
        )
        for grantee in grantees:
            admin.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {}({}) TO {}").format(
                    qualified_routine,
                    qualified_argument,
                    sql.Identifier(grantee),
                )
            )
        admin.execute("RESET ROLE")


@pytest.mark.parametrize(
    ("schema_name", "argument_type", "grantees", "acl_must_fail"),
    (
        ("ofarm", "text", (), False),
        ("ofarm", "text", ("ofarm_app",), True),
        (
            "ofarm",
            "text",
            ("ofarm_command_runtime_bundle_selection_controller",),
            True,
        ),
        ("public", "text", (), False),
        ("ofarm", "int4", (), False),
    ),
    ids=(
        "owner-only",
        "unrelated-grantee",
        "premature-controller",
        "wrong-schema",
        "wrong-overload",
    ),
)
def test_stable_v7_refuses_every_selection_activation_routine_shape(
    tenant_target: _TenantTarget,
    schema_name: str,
    argument_type: str,
    grantees: tuple[str, ...],
    acl_must_fail: bool,
) -> None:
    full_set = _advance_tenant_target_to_v7(tenant_target)
    _create_selection_activation_routine(
        tenant_target.target_admin_dsn,
        schema_name=schema_name,
        argument_type=argument_type,
        grantees=grantees,
    )

    with pytest.raises(
        MigrationTargetError,
        match="tenant selection activation routine inventory differs",
    ) as refused:
        migrate_authoritative_service(
            admin_dsn=tenant_target.admin_dsn,
            migrator_dsn=tenant_target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=full_set,
            release_identity=RELEASE_IDENTITY + "-v7-activation-drift",
            execution_id=uuid4(),
        )

    if acl_must_fail:
        assert "tenant selection activation routine ACL differs" in str(
            refused.value
        )
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert admin.execute(
            "SELECT pg_catalog.count(*), pg_catalog.max(version) "
            "FROM ofarm.schema_migration"
        ).fetchone() == (7, 7)


def _controlled_selection_activation_authority() -> AuthoritativeMigration:
    return AuthoritativeMigration(
        version=8,
        filename="0008_tenant_command_runtime_bundle_selection.sql",
        source_sha256="sha256:" + "8" * 64,
        byte_length=808,
        applied_prefix_digest="sha256:" + "9" * 64,
    )


def _v8_post_source_differences(
    tenant_target: _TenantTarget,
) -> list[str]:
    with psycopg.connect(tenant_target.migrator_dsn, autocommit=True) as connection:
        migration_runner_module._begin_and_lock(
            connection,
            TENANT_PROVISIONING_SPEC,
        )
        try:
            migration_runner_module._set_owner_role(
                connection,
                TENANT_PROVISIONING_SPEC,
            )
            return (
                provisioning_module
                ._tenant_selection_v8_post_source_locked_differences(
                    connection,
                    TENANT_PROVISIONING_SPEC,
                )
            )
        finally:
            connection.rollback()


def test_v8_post_source_seam_accepts_exact_shape_and_observes_all_escape_rows(
    tenant_target: _TenantTarget,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _advance_tenant_target_to_v7(tenant_target)
    authority = _controlled_selection_activation_authority()
    monkeypatch.setattr(
        provisioning_module,
        "_authoritative_tenant_selection_activation_migration",
        lambda: authority,
    )
    controller = "ofarm_command_runtime_bundle_selection_controller"
    _create_selection_activation_routine(
        tenant_target.target_admin_dsn,
        grantees=(controller,),
    )

    assert _v8_post_source_differences(tenant_target) == []

    with psycopg.connect(
        tenant_target.target_admin_dsn,
        autocommit=True,
    ) as admin:
        admin.execute("SET ROLE ofarm_owner")
        admin.execute(
            "GRANT EXECUTE ON FUNCTION "
            "ofarm.activate_commit_operation_claim_draft_runtime_bundle_selection("
            "pg_catalog.text) TO ofarm_app"
        )
        admin.execute("RESET ROLE")
        admin.execute(
            "CREATE FUNCTION public.issue176_default_public() "
            "RETURNS pg_catalog.void LANGUAGE sql AS "
            "'SELECT pg_catalog.pg_sleep(0)'"
        )

    differences = _v8_post_source_differences(tenant_target)
    assert "tenant selection activation routine ACL differs" in differences
    assert "tenant binding selection-control admission ACL differs" in differences


_EXPECTED_WRITE_LOCK_ACL_A2 = [
    ("ofarm_app", "ofarm_tenant_lock_owner", "EXECUTE", False),
    (
        "ofarm_tenant_lock_owner",
        "ofarm_tenant_lock_owner",
        "EXECUTE",
        False,
    ),
    ("ofarm_worker", "ofarm_tenant_lock_owner", "EXECUTE", False),
]
_EXPECTED_WRITE_LOCK_ACL_A4 = sorted(
    _EXPECTED_WRITE_LOCK_ACL_A2
    + [("ofarm_owner", "ofarm_tenant_lock_owner", "EXECUTE", False)]
)


def _write_lock_owner_admission_state(
    target_admin_dsn: str,
) -> tuple[tuple[int, int], bool, list[tuple[object, ...]]]:
    sealer = (
        TENANT_PROVISIONING_SPEC
        .tenant_write_lock_selection_owner_admission_sealer
    )
    assert sealer is not None
    with psycopg.connect(target_admin_dsn, autocommit=True) as admin:
        ledger = admin.execute(
            "SELECT pg_catalog.count(*), pg_catalog.max(version) "
            "FROM ofarm.schema_migration"
        ).fetchone()
        capsule_present = admin.execute(
            "SELECT pg_catalog.to_regprocedure(%s) IS NOT NULL",
            (sealer.qualified_function + "()",),
        ).fetchone()[0]
        rows = admin.execute(
            """
            SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                        ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
                   pg_catalog.pg_get_userbyid(acl.grantor),
                   acl.privilege_type,
                   acl.is_grantable
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(
                    routine.proacl,
                    pg_catalog.acldefault('f', routine.proowner)
                )
            ) AS acl
            WHERE namespace.nspname = 'ofarm'
              AND routine.proname = 'take_tenant_write_lock'
              AND pg_catalog.pg_get_function_identity_arguments(
                      routine.oid
                  ) = ''
            ORDER BY 1, 2, 3, 4
            """
        ).fetchall()
    return tuple(ledger), capsule_present, [tuple(row) for row in rows]


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    (
        (
            "security_mode",
            "tenant write-lock selection-owner admission sealer differs",
        ),
        (
            "owner",
            "tenant write-lock selection-owner admission sealer differs",
        ),
        (
            "acl",
            "migration-lock infrastructure routine ACL differs",
        ),
    ),
    ids=("security-mode", "owner", "acl"),
)
def test_v7_hostile_capsule_drift_refuses_without_repair(
    tenant_target: _TenantTarget,
    mutation: str,
    expected_error: str,
) -> None:
    full_set = _advance_tenant_target_to_v6(tenant_target)
    sealer = (
        TENANT_PROVISIONING_SPEC
        .tenant_write_lock_selection_owner_admission_sealer
    )
    assert sealer is not None
    capsule = sql.Identifier(sealer.schema_name, sealer.function_name)
    with psycopg.connect(
        tenant_target.target_admin_dsn,
        autocommit=True,
    ) as admin:
        original_owner = admin.execute(
            """
            SELECT pg_catalog.pg_get_userbyid(routine.proowner)
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = routine.pronamespace
            WHERE namespace.nspname = %s
              AND routine.proname = %s
              AND pg_catalog.pg_get_function_identity_arguments(
                      routine.oid
                  ) = ''
            """,
            (sealer.schema_name, sealer.function_name),
        ).fetchone()[0]
        if mutation == "security_mode":
            admin.execute(
                sql.SQL("ALTER FUNCTION {}() SECURITY INVOKER").format(capsule)
            )
        elif mutation == "owner":
            admin.execute(
                sql.SQL("ALTER FUNCTION {}() OWNER TO {}").format(
                    capsule,
                    sql.Identifier(sealer.execute_role),
                )
            )
        else:
            admin.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION {}() TO PUBLIC").format(
                    capsule
                )
            )

    try:
        with pytest.raises(
            MigrationTargetError,
            match=expected_error,
        ) as refused:
            migrate_authoritative_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=tenant_target.migrator_dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=full_set,
                release_identity=RELEASE_IDENTITY + "-v7-capsule-drift",
                execution_id=uuid4(),
            )

        failure = str(refused.value)
        protected_values = (
            *tenant_target.passwords.values(),
            tenant_target.admin_dsn,
            tenant_target.target_admin_dsn,
            tenant_target.migrator_dsn,
        )
        assert all(value not in failure for value in protected_values)
        assert "advisory_lock_key" not in failure
        assert _write_lock_owner_admission_state(
            tenant_target.target_admin_dsn
        ) == ((6, 6), True, _EXPECTED_WRITE_LOCK_ACL_A2)
        with psycopg.connect(
            tenant_target.target_admin_dsn,
            autocommit=True,
        ) as admin:
            drifted = admin.execute(
                """
                SELECT pg_catalog.pg_get_userbyid(routine.proowner),
                       routine.prosecdef,
                       EXISTS (
                           SELECT 1
                           FROM pg_catalog.aclexplode(
                               COALESCE(
                                   routine.proacl,
                                   pg_catalog.acldefault(
                                       'f', routine.proowner
                                   )
                               )
                           ) AS acl
                           WHERE acl.grantee = 0
                             AND acl.privilege_type = 'EXECUTE'
                       )
                FROM pg_catalog.pg_proc AS routine
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = routine.pronamespace
                WHERE namespace.nspname = %s
                  AND routine.proname = %s
                  AND pg_catalog.pg_get_function_identity_arguments(
                          routine.oid
                      ) = ''
                """,
                (sealer.schema_name, sealer.function_name),
            ).fetchone()
        if mutation == "security_mode":
            assert drifted == (original_owner, False, False)
        elif mutation == "owner":
            assert drifted[0] == sealer.execute_role
        else:
            assert drifted == (original_owner, True, True)
    finally:
        with psycopg.connect(
            tenant_target.target_admin_dsn,
            autocommit=True,
        ) as admin:
            if mutation == "security_mode":
                admin.execute(
                    sql.SQL("ALTER FUNCTION {}() SECURITY DEFINER").format(
                        capsule
                    )
                )
            elif mutation == "owner":
                admin.execute(
                    sql.SQL("ALTER FUNCTION {}() OWNER TO {}").format(
                        capsule,
                        sql.Identifier(original_owner),
                    )
                )
                admin.execute(
                    sql.SQL(
                        "REVOKE ALL PRIVILEGES ON FUNCTION {}() FROM PUBLIC"
                    ).format(capsule)
                )
                admin.execute(
                    sql.SQL(
                        "REVOKE ALL PRIVILEGES ON FUNCTION {}() FROM {}"
                    ).format(capsule, sql.Identifier(sealer.execute_role))
                )
                admin.execute(
                    sql.SQL("GRANT EXECUTE ON FUNCTION {}() TO {}").format(
                        capsule,
                        sql.Identifier(sealer.execute_role),
                    )
                )
            else:
                admin.execute(
                    sql.SQL("REVOKE EXECUTE ON FUNCTION {}() FROM PUBLIC").format(
                        capsule
                    )
                )

    assert _write_lock_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((6, 6), True, _EXPECTED_WRITE_LOCK_ACL_A2)
    verified = verify_service_infrastructure(
        tenant_target.admin_dsn,
        TENANT_PROVISIONING_SPEC,
    )
    assert verified.provisioning_spec_digest == TENANT_PROVISIONING_SPEC.digest


_V7_LEDGER_FIELDS = (
    "version",
    "filename",
    "source_sha256",
    "source_byte_length",
    "applied_prefix_digest",
    "service_identity",
    "provisioning_spec_digest",
    "release_identity",
    "execution_id",
)


@pytest.mark.parametrize("substituted_field", _V7_LEDGER_FIELDS)
def test_v7_live_ledger_substitution_refuses_before_capsule_use(
    tenant_target: _TenantTarget,
    substituted_field: str,
) -> None:
    full_set = _advance_tenant_target_to_v6(tenant_target)
    assert _write_lock_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((6, 6), True, _EXPECTED_WRITE_LOCK_ACL_A2)

    proxy = _V7LedgerBindSubstitutionProxy(
        tenant_target.migrator_dsn,
        substituted_field,
    )
    proxy.start()
    try:
        if substituted_field == "version":
            expected_error = pytest.raises(
                MigrationExecutionError,
                match="schema_migration_filename_check",
            )
        elif substituted_field == "service_identity":
            expected_error = pytest.raises(
                MigrationExecutionError,
                match="schema_migration_service_check",
            )
        elif substituted_field in {"release_identity", "execution_id"}:
            expected_error = pytest.raises(
                MigrationDirtyError,
                match=(
                    "tenant write-lock selection-owner admission row "
                    "is not exact"
                ),
            )
        else:
            expected_error = pytest.raises(
                MigrationDirtyError,
                match="migration history is not the exact local prefix",
            )
        with expected_error:
            migrate_authoritative_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=proxy.dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=full_set,
                release_identity=RELEASE_IDENTITY + "-v7-substitution",
                execution_id=uuid4(),
            )
    finally:
        proxy.close()

    assert proxy.parameter_substituted.is_set()
    assert _write_lock_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((6, 6), True, _EXPECTED_WRITE_LOCK_ACL_A2)
    verified = verify_service_infrastructure(
        tenant_target.admin_dsn,
        TENANT_PROVISIONING_SPEC,
    )
    assert verified.provisioning_spec_digest == TENANT_PROVISIONING_SPEC.digest


def test_v7_row_is_authenticated_before_and_after_capsule_consumption(
    tenant_target: _TenantTarget,
    monkeypatch,
) -> None:
    full_set = _advance_tenant_target_to_v6(tenant_target)
    events: list[str] = []
    original_authenticate = (
        migration_runner_module
        ._authenticate_tenant_write_lock_selection_owner_admission_row
    )
    original_consume = (
        migration_runner_module
        ._consume_tenant_write_lock_selection_owner_admission_sealer
    )
    original_boundary = migration_runner_module._locked_boundary_differences
    original_final = migration_runner_module._verify_final_service_structure
    authentication_count = 0
    transition_verified = False

    def trace_authentication(*args, **kwargs):
        nonlocal authentication_count
        original_authenticate(*args, **kwargs)
        authentication_count += 1
        events.append("authenticate")

    def trace_consumption(*args, **kwargs):
        events.append("consume")
        return original_consume(*args, **kwargs)

    def trace_boundary(*args, **kwargs):
        if authentication_count and not transition_verified:
            events.append("boundary")
        return original_boundary(*args, **kwargs)

    def trace_final(*args, **kwargs):
        nonlocal transition_verified
        if not transition_verified:
            events.append("final")
            transition_verified = True
        return original_final(*args, **kwargs)

    monkeypatch.setattr(
        migration_runner_module,
        "_authenticate_tenant_write_lock_selection_owner_admission_row",
        trace_authentication,
    )
    monkeypatch.setattr(
        migration_runner_module,
        "_consume_tenant_write_lock_selection_owner_admission_sealer",
        trace_consumption,
    )
    monkeypatch.setattr(
        migration_runner_module,
        "_locked_boundary_differences",
        trace_boundary,
    )
    monkeypatch.setattr(
        migration_runner_module,
        "_verify_final_service_structure",
        trace_final,
    )

    migrated = migrate_authoritative_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=full_set,
        release_identity=RELEASE_IDENTITY + "-v7-order",
        execution_id=uuid4(),
    )
    assert migrated.applied_versions == (7,)
    assert events == [
        "authenticate",
        "consume",
        "authenticate",
        "boundary",
        "final",
    ]
    assert _write_lock_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((7, 7), False, _EXPECTED_WRITE_LOCK_ACL_A4)


def test_v7_precommit_failure_restores_exact_a2_and_mixed_states_refuse(
    tenant_target: _TenantTarget,
    monkeypatch,
) -> None:
    full_set = _advance_tenant_target_to_v6(tenant_target)
    original_consume = (
        migration_runner_module
        ._consume_tenant_write_lock_selection_owner_admission_sealer
    )

    def refuse_after_capsule(*args, **kwargs):
        original_consume(*args, **kwargs)
        raise MigrationDirtyError("injected V7 final verification refusal")

    monkeypatch.setattr(
        migration_runner_module,
        "_consume_tenant_write_lock_selection_owner_admission_sealer",
        refuse_after_capsule,
    )
    with pytest.raises(
        MigrationDirtyError,
        match="injected V7 final verification refusal",
    ):
        migrate_authoritative_service(
            admin_dsn=tenant_target.admin_dsn,
            migrator_dsn=tenant_target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=full_set,
            release_identity=RELEASE_IDENTITY + "-v7-refusal",
            execution_id=uuid4(),
        )
    monkeypatch.setattr(
        migration_runner_module,
        "_consume_tenant_write_lock_selection_owner_admission_sealer",
        original_consume,
    )
    assert _write_lock_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((6, 6), True, _EXPECTED_WRITE_LOCK_ACL_A2)

    with psycopg.connect(
        tenant_target.target_admin_dsn,
        autocommit=True,
    ) as admin:
        admin.execute(
            "GRANT EXECUTE ON FUNCTION ofarm.take_tenant_write_lock() "
            "TO ofarm_owner"
        )
    try:
        with pytest.raises(MigrationTargetError, match="admission ACL differs"):
            migrate_authoritative_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=tenant_target.migrator_dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=full_set,
                release_identity=RELEASE_IDENTITY + "-v7-mixed-grant",
                execution_id=uuid4(),
            )
    finally:
        with psycopg.connect(
            tenant_target.target_admin_dsn,
            autocommit=True,
        ) as admin:
            admin.execute(
                "REVOKE EXECUTE ON FUNCTION ofarm.take_tenant_write_lock() "
                "FROM ofarm_owner"
            )

    sealer = (
        TENANT_PROVISIONING_SPEC
        .tenant_write_lock_selection_owner_admission_sealer
    )
    assert sealer is not None
    with psycopg.connect(
        tenant_target.target_admin_dsn,
        autocommit=True,
    ) as admin:
        admin.execute(
            sql.SQL("DROP FUNCTION {}()").format(
                sql.Identifier(sealer.schema_name, sealer.function_name)
            )
        )
    with pytest.raises(MigrationTargetError, match="sealer differs"):
        migrate_authoritative_service(
            admin_dsn=tenant_target.admin_dsn,
            migrator_dsn=tenant_target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=full_set,
            release_identity=RELEASE_IDENTITY + "-v7-missing-capsule",
            execution_id=uuid4(),
        )


def test_v7_postcommit_acknowledgement_loss_recovers_as_verified_noop(
    tenant_target: _TenantTarget,
) -> None:
    full_set = _advance_tenant_target_to_v6(tenant_target)
    proxy = _CommitAcknowledgementDropProxy(tenant_target.migrator_dsn)
    proxy.start()
    uncertain_execution_id = uuid4()
    try:
        with pytest.raises(MigrationOutcomeUnknown) as uncertain:
            migrate_authoritative_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=proxy.dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=full_set,
                release_identity=RELEASE_IDENTITY + "-v7-ack-loss-unknown",
                execution_id=uncertain_execution_id,
            )
        assert uncertain.value.version == 7
        assert uncertain.value.execution_id == uncertain_execution_id
    finally:
        proxy.close()
    assert proxy.acknowledgement_dropped.is_set()
    assert _write_lock_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((7, 7), False, _EXPECTED_WRITE_LOCK_ACL_A4)

    retry_execution_id = uuid4()
    recovered = migrate_authoritative_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=full_set,
        release_identity=RELEASE_IDENTITY + "-v7-ack-loss-reconnect",
        execution_id=retry_execution_id,
    )
    assert recovered.previous_version == 7
    assert recovered.applied_versions == ()
    assert recovered.final_version == 7
    assert recovered.execution_id == retry_execution_id
    assert recovered.observed_head_execution_id == uncertain_execution_id
    assert recovered.verified_noop is True


def test_v7_precommit_backend_loss_reconnects_from_exact_a2(
    tenant_target: _TenantTarget,
    monkeypatch,
) -> None:
    full_set = _advance_tenant_target_to_v6(tenant_target)
    original_commit = migration_runner_module._commit

    def terminate_backend_at_commit(connection, migration, execution_id):
        with psycopg.connect(
            tenant_target.target_admin_dsn,
            autocommit=True,
        ) as admin:
            terminated = admin.execute(
                "SELECT pg_catalog.pg_terminate_backend(%s)",
                (connection.info.backend_pid,),
            ).fetchone()
        assert terminated == (True,)
        original_commit(connection, migration, execution_id)

    monkeypatch.setattr(
        migration_runner_module,
        "_commit",
        terminate_backend_at_commit,
    )
    uncertain_execution_id = uuid4()
    with pytest.raises(MigrationOutcomeUnknown) as uncertain:
        migrate_authoritative_service(
            admin_dsn=tenant_target.admin_dsn,
            migrator_dsn=tenant_target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=full_set,
            release_identity=RELEASE_IDENTITY + "-v7-disconnect-unknown",
            execution_id=uncertain_execution_id,
        )
    assert uncertain.value.version == 7
    assert uncertain.value.execution_id == uncertain_execution_id
    assert _write_lock_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((6, 6), True, _EXPECTED_WRITE_LOCK_ACL_A2)

    monkeypatch.setattr(migration_runner_module, "_commit", original_commit)
    recovered = migrate_authoritative_service(
        admin_dsn=tenant_target.admin_dsn,
        migrator_dsn=tenant_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=full_set,
        release_identity=RELEASE_IDENTITY + "-v7-disconnect-recovered",
        execution_id=uuid4(),
    )
    assert recovered.previous_version == 6
    assert recovered.applied_versions == (7,)
    assert recovered.final_version == 7
    assert _write_lock_owner_admission_state(
        tenant_target.target_admin_dsn
    ) == ((7, 7), False, _EXPECTED_WRITE_LOCK_ACL_A4)


def test_resumes_at_0002_and_preserves_the_stable_0001_prefix(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    initial_source = _initial_source()
    first_set = _load_synthetic_set(
        tmp_path / "first-release",
        {"0001_initial.sql": initial_source},
    )
    full_set = _load_synthetic_set(
        tmp_path / "second-release",
        {
            "0001_initial.sql": initial_source,
            "0002_add_resume_probe.sql": b"""
                CREATE TABLE ofarm.migration_resume_probe (
                    probe_id pg_catalog.int4 PRIMARY KEY
                );
            """,
        },
    )
    _run(tenant_target, first_set)

    report = _run(tenant_target, full_set)

    assert report.previous_version == 1
    assert report.final_version == 2
    assert report.applied_versions == (2,)
    assert _relation_exists(tenant_target, "ofarm.migration_resume_probe")
    rows = _ledger_rows(tenant_target)
    assert [row[0] for row in rows] == [1, 2]
    assert rows[0][4] == first_set.digest == full_set.prefix_digest(1)
    assert rows[1][4] == full_set.digest


def test_failed_ddl_and_ledger_append_roll_back_together(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    initial_source = _initial_source()
    first_set = _load_synthetic_set(
        tmp_path / "initial",
        {"0001_initial.sql": initial_source},
    )
    failing_set = _load_synthetic_set(
        tmp_path / "failing",
        {
            "0001_initial.sql": initial_source,
            "0002_fail_after_ddl.sql": b"""
                CREATE TABLE ofarm.must_roll_back (
                    probe_id pg_catalog.int4 PRIMARY KEY
                );
                SELECT 1 / 0;
            """,
        },
    )
    _run(tenant_target, first_set)

    with pytest.raises(MigrationExecutionError) as raised:
        _run(tenant_target, failing_set)

    assert raised.value.version == 2
    assert raised.value.filename == "0002_fail_after_ddl.sql"
    assert _relation_exists(tenant_target, "ofarm.must_roll_back") is False
    assert [row[0] for row in _ledger_rows(tenant_target)] == [1]


def test_missing_tenant_sealer_targets_roll_back_ledger_and_keep_capsule(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {
            "0001_initial.sql": initial_ledger_sql(
                TENANT_PROVISIONING_SPEC
            ).encode("utf-8")
        },
    )

    with pytest.raises(MigrationExecutionError, match="does not exist"):
        _run(tenant_target, migration_set)

    assert _relation_exists(tenant_target, "ofarm.schema_migration") is False
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        assert connection.execute(
            "SELECT pg_catalog.to_regprocedure("
            "'ofarm_infrastructure.seal_tenant_routine_owners()') IS NOT NULL"
        ).fetchone() == (True,)
        assert connection.execute(
            "SELECT pg_catalog.has_schema_privilege("
            "'ofarm_binder', 'ofarm', 'CREATE'), "
            "pg_catalog.has_schema_privilege("
            "'ofarm_tenant_lock_owner', 'ofarm', 'CREATE'), "
            "pg_catalog.has_schema_privilege("
            "'ofarm_migrator', 'ofarm_infrastructure', 'CREATE')"
        ).fetchone() == (False, False, False)


def test_post_sealer_boundary_failure_rolls_every_owner_change_back(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {
            "0001_initial.sql": _initial_source()
            + b"\nGRANT CREATE ON SCHEMA ofarm TO ofarm_app;\n"
        },
    )

    with pytest.raises(MigrationDirtyError, match="widened"):
        _run(tenant_target, migration_set)

    assert _relation_exists(tenant_target, "ofarm.schema_migration") is False
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        assert connection.execute(
            "SELECT pg_catalog.to_regprocedure("
            "'ofarm.create_tenant_challenge()') IS NULL, "
            "pg_catalog.to_regprocedure("
            "'ofarm.current_tenant_id()') IS NULL, "
            "pg_catalog.to_regprocedure("
            "'ofarm.take_tenant_write_lock()') IS NULL"
        ).fetchone() == (True, True, True)
        assert connection.execute(
            """
            SELECT owner.rolsuper,
                   routine.prosecdef
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
            WHERE namespace.nspname = 'ofarm_infrastructure'
              AND routine.proname = 'seal_tenant_routine_owners'
              AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = ''
            """
        ).fetchone() == (True, True)
        assert connection.execute(
            "SELECT pg_catalog.has_schema_privilege("
            "'ofarm_app', 'ofarm', 'CREATE'), "
            "pg_catalog.has_schema_privilege("
            "'ofarm_binder', 'ofarm', 'CREATE'), "
            "pg_catalog.has_schema_privilege("
            "'ofarm_tenant_lock_owner', 'ofarm', 'CREATE'), "
            "pg_catalog.has_schema_privilege("
            "'ofarm_migrator', 'ofarm_infrastructure', 'CREATE')"
        ).fetchone() == (False, False, False, False)


def test_migration_cannot_change_runner_transaction_posture(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {
            "0001_initial.sql": _initial_source()
            + b"\nSELECT pg_catalog.set_config("
            + b"'synchronous_commit', 'off', true);\n"
        },
    )

    with pytest.raises(MigrationDirtyError, match="widened"):
        _run(tenant_target, migration_set)

    assert _relation_exists(tenant_target, TENANT_SERVICE.qualified_ledger) is False
    assert _relation_exists(tenant_target, "ofarm.migration_runner_probe") is False


def test_fresh_target_with_a_rogue_object_refuses_without_adoption(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        connection.execute(
            "CREATE TABLE ofarm.rogue_before_ledger "
            "(probe_id pg_catalog.int4 PRIMARY KEY)"
        )

    with pytest.raises(MigrationDirtyError):
        _run(tenant_target, migration_set)

    assert _relation_exists(tenant_target, "ofarm.rogue_before_ledger")
    assert _relation_exists(tenant_target, TENANT_SERVICE.qualified_ledger) is False


def test_fake_ledger_cannot_become_migration_phase_evidence(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        connection.execute(
            "CREATE TABLE ofarm.schema_migration "
            "(version pg_catalog.int4 PRIMARY KEY)"
        )

    with pytest.raises(ProvisioningDriftError, match="infrastructure"):
        verify_service_infrastructure(
            tenant_target.admin_dsn,
            TENANT_PROVISIONING_SPEC,
        )
    with pytest.raises(MigrationTargetError, match="infrastructure"):
        _run(tenant_target, migration_set)

    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        columns = connection.execute(
            """
            SELECT attribute.attname::text
            FROM pg_catalog.pg_attribute AS attribute
            WHERE attribute.attrelid =
                  'ofarm.schema_migration'::pg_catalog.regclass
              AND attribute.attnum > 0
              AND NOT attribute.attisdropped
            ORDER BY attribute.attnum
            """
        ).fetchall()
    assert columns == [("version",)]


@pytest.mark.parametrize(
    "drift_sql",
    (
        "ALTER ROLE ofarm_app IN DATABASE ofarm_tenant "
        "SET statement_timeout = '31000'",
        "ALTER DEFAULT PRIVILEGES FOR ROLE ofarm_owner "
        "GRANT EXECUTE ON FUNCTIONS TO PUBLIC",
        "GRANT EXECUTE ON FUNCTION "
        "pg_catalog.pg_advisory_xact_lock(pg_catalog.int8) TO ofarm_app",
    ),
)
def test_locked_runner_discards_clean_but_stale_admin_observation(
    tenant_target: _TenantTarget,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift_sql: str,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    real_observer = migration_runner_module.verify_service_infrastructure

    def observe_then_drift(admin_dsn: str, spec: ProvisioningSpec):
        report = real_observer(admin_dsn, spec)
        with psycopg.connect(
            tenant_target.target_admin_dsn,
            autocommit=True,
        ) as connection:
            connection.execute(drift_sql)
        return report

    monkeypatch.setattr(
        migration_runner_module,
        "verify_service_infrastructure",
        observe_then_drift,
    )

    with pytest.raises(MigrationDirtyError, match="locked provisioning"):
        _run(tenant_target, migration_set)

    assert _relation_exists(tenant_target, TENANT_SERVICE.qualified_ledger) is False
    assert _relation_exists(tenant_target, "ofarm.migration_runner_probe") is False


@pytest.mark.parametrize(
    ("column", "tampered_value", "drop_fixed_constraint"),
    (
        ("source_sha256", "sha256:" + "0" * 64, False),
        ("applied_prefix_digest", "sha256:" + "1" * 64, False),
        ("service_identity", "ofarm.crossed-postgresql.v1", True),
        ("provisioning_spec_digest", "sha256:" + "2" * 64, True),
    ),
)
def test_tampered_history_refuses_without_repair(
    tenant_target: _TenantTarget,
    tmp_path: Path,
    column: str,
    tampered_value: str,
    drop_fixed_constraint: bool,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    _run(tenant_target, migration_set)
    _tamper_ledger_value(
        tenant_target,
        column,
        tampered_value,
        drop_fixed_constraint=drop_fixed_constraint,
    )

    with pytest.raises(MigrationDirtyError):
        _run(tenant_target, migration_set)

    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        observed = connection.execute(
            sql.SQL(
                "SELECT {}::text FROM ofarm.schema_migration WHERE version = 1"
            ).format(sql.Identifier(column))
        ).fetchone()[0]
    assert observed == tampered_value


@pytest.mark.parametrize(
    "constraint_name",
    (
        "schema_migration_version_check",
        "schema_migration_filename_check",
        "schema_migration_source_sha256_check",
        "schema_migration_source_length_check",
        "schema_migration_prefix_digest_check",
        "schema_migration_service_check",
        "schema_migration_provisioning_digest_check",
        "schema_migration_release_check",
        "schema_migration_execution_id_check",
        "schema_migration_applied_at_check",
    ),
)
def test_same_named_weakened_ledger_check_refuses(
    tenant_target: _TenantTarget,
    tmp_path: Path,
    constraint_name: str,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    _run(tenant_target, migration_set)
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        connection.execute(
            sql.SQL(
                "ALTER TABLE ofarm.schema_migration DROP CONSTRAINT {}"
            ).format(sql.Identifier(constraint_name))
        )
        connection.execute(
            sql.SQL(
                "ALTER TABLE ofarm.schema_migration "
                "ADD CONSTRAINT {} CHECK (true)"
            ).format(sql.Identifier(constraint_name))
        )

    with pytest.raises(MigrationDirtyError, match="constraints differ"):
        _run(tenant_target, migration_set)


def test_same_named_ledger_trigger_with_false_predicate_refuses(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    _run(tenant_target, migration_set)
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        connection.execute(
            "DROP TRIGGER schema_migration_reject_update_delete "
            "ON ofarm.schema_migration"
        )
        connection.execute(
            "UPDATE ofarm.schema_migration "
            "SET release_identity = 'hostile-but-valid' WHERE version = 1"
        )
        connection.execute(
            """
            CREATE TRIGGER schema_migration_reject_update_delete
            BEFORE UPDATE OR DELETE ON ofarm.schema_migration
            FOR EACH ROW WHEN (false)
            EXECUTE FUNCTION ofarm.reject_schema_migration_mutation()
            """
        )

    with pytest.raises(MigrationDirtyError, match="triggers differ"):
        _run(tenant_target, migration_set)


def test_create_then_drop_ledger_rule_restores_verified_noop(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    first = _run(tenant_target, migration_set)
    with psycopg.connect(
        tenant_target.target_admin_dsn,
        autocommit=True,
    ) as connection:
        connection.execute(
            "CREATE RULE migration_rule_probe AS ON INSERT "
            "TO ofarm.schema_migration DO ALSO NOTHING"
        )

    with pytest.raises(MigrationDirtyError, match="relation posture differs"):
        _run(tenant_target, migration_set)

    with psycopg.connect(
        tenant_target.target_admin_dsn,
        autocommit=True,
    ) as connection:
        connection.execute(
            "DROP RULE migration_rule_probe ON ofarm.schema_migration"
        )
        assert connection.execute(
            """
            SELECT relation.relhasrules,
                   EXISTS (
                       SELECT 1
                       FROM pg_catalog.pg_rewrite AS relation_rule
                       WHERE relation_rule.ev_class = relation.oid
                   )
            FROM pg_catalog.pg_class AS relation
            WHERE relation.oid = 'ofarm.schema_migration'::pg_catalog.regclass
            """
        ).fetchone() == (True, False)

    report = _run(tenant_target, migration_set)
    assert report.applied_versions == ()
    assert report.verified_noop is True
    assert report.observed_head_execution_id == first.observed_head_execution_id


@pytest.mark.parametrize(
    ("statements", "expected"),
    (
        (
            (
                "ALTER TABLE ofarm.schema_migration "
                "ADD COLUMN discarded pg_catalog.int4",
                "ALTER TABLE ofarm.schema_migration DROP COLUMN discarded",
            ),
            "relation posture differs",
        ),
        (
            (
                "ALTER TABLE ofarm.schema_migration SET (fillfactor = 70)",
            ),
            "relation posture differs",
        ),
        (
            ("ALTER TABLE ofarm.schema_migration REPLICA IDENTITY FULL",),
            "relation posture differs",
        ),
        (
            (
                "ALTER INDEX ofarm.schema_migration_filename_key "
                "SET (fillfactor = 70)",
            ),
            "indexes differ",
        ),
    ),
)
def test_ledger_relation_or_index_storage_drift_refuses(
    tenant_target: _TenantTarget,
    tmp_path: Path,
    statements: tuple[str, ...],
    expected: str,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    _run(tenant_target, migration_set)
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        for statement in statements:
            connection.execute(statement)

    with pytest.raises(MigrationDirtyError, match=expected):
        _run(tenant_target, migration_set)


@pytest.mark.parametrize(
    "trigger_clause",
    (
        "BEFORE UPDATE OF release_identity",
        "BEFORE UPDATE OR DELETE",
    ),
)
def test_ledger_trigger_columns_or_arguments_refuse(
    tenant_target: _TenantTarget,
    tmp_path: Path,
    trigger_clause: str,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    _run(tenant_target, migration_set)
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        connection.execute(
            "DROP TRIGGER schema_migration_reject_update_delete "
            "ON ofarm.schema_migration"
        )
        arguments = "" if "UPDATE OF" in trigger_clause else "'ignored'"
        connection.execute(
            f"CREATE TRIGGER schema_migration_reject_update_delete "
            f"{trigger_clause} ON ofarm.schema_migration "
            "FOR EACH ROW EXECUTE FUNCTION "
            f"ofarm.reject_schema_migration_mutation({arguments})"
        )

    with pytest.raises(MigrationDirtyError, match="triggers differ"):
        _run(tenant_target, migration_set)


def test_cross_service_set_is_rejected_before_target_writes(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    crossed_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": b"SELECT 1;"},
        service=SECURITY_AUDIT_SERVICE,
    )

    with pytest.raises(MigrationInputError):
        _run(tenant_target, crossed_set)

    assert _relation_exists(tenant_target, TENANT_SERVICE.qualified_ledger) is False
    assert _relation_exists(tenant_target, "ofarm.migration_runner_probe") is False


def test_audit_service_applies_and_verifies_its_own_independent_history(
    audit_target: _TenantTarget,
    tmp_path: Path,
):
    source = initial_ledger_sql(SECURITY_AUDIT_PROVISIONING_SPEC).encode(
        "utf-8"
    ) + b"""
CREATE TABLE ofarm_security.audit_runner_probe (
    probe_id pg_catalog.int4 PRIMARY KEY
);
"""
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": source},
        service=SECURITY_AUDIT_SERVICE,
    )

    report = _run(
        audit_target,
        migration_set,
        spec=SECURITY_AUDIT_PROVISIONING_SPEC,
    )
    noop = _run(
        audit_target,
        migration_set,
        spec=SECURITY_AUDIT_PROVISIONING_SPEC,
    )

    assert report.service_identity == SECURITY_AUDIT_SERVICE.identity
    assert report.provisioning_spec_digest == \
        SECURITY_AUDIT_PROVISIONING_SPEC.digest
    assert report.previous_version == 0
    assert report.applied_versions == (1,)
    assert noop.previous_version == noop.final_version == 1
    assert noop.verified_noop is True
    assert _relation_exists(
        audit_target,
        "ofarm_security.audit_runner_probe",
    )
    with psycopg.connect(audit_target.target_admin_dsn) as connection:
        row = connection.execute(
            """
            SELECT service_identity, provisioning_spec_digest
            FROM ofarm_security.schema_migration
            WHERE version = 1
            """
        ).fetchone()
    assert row == (
        SECURITY_AUDIT_SERVICE.identity,
        SECURITY_AUDIT_PROVISIONING_SPEC.digest,
    )


def test_admin_and_migrator_routes_cannot_be_crossed_between_services(
    tenant_target: _TenantTarget,
    audit_target: _TenantTarget,
    tmp_path: Path,
):
    tenant_set = _load_synthetic_set(
        tmp_path / "tenant",
        {"0001_initial.sql": _initial_source()},
    )
    audit_source = initial_ledger_sql(
        SECURITY_AUDIT_PROVISIONING_SPEC
    ).encode("utf-8") + b"\nSELECT 1;\n"
    audit_set = _load_synthetic_set(
        tmp_path / "audit",
        {"0001_initial.sql": audit_source},
        service=SECURITY_AUDIT_SERVICE,
    )

    with pytest.raises(MigrationTargetError):
        migrate_service(
            admin_dsn=tenant_target.admin_dsn,
            migrator_dsn=audit_target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=tenant_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )
    with pytest.raises(MigrationTargetError):
        migrate_service(
            admin_dsn=audit_target.admin_dsn,
            migrator_dsn=tenant_target.migrator_dsn,
            spec=SECURITY_AUDIT_PROVISIONING_SPEC,
            migration_set=audit_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )

    assert _relation_exists(
        tenant_target,
        TENANT_SERVICE.qualified_ledger,
    ) is False
    assert _relation_exists(
        audit_target,
        SECURITY_AUDIT_SERVICE.qualified_ledger,
    ) is False


def test_post_migration_infrastructure_verifies_but_fresh_verification_refuses(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    _run(tenant_target, migration_set)

    infrastructure = verify_service_infrastructure(
        tenant_target.admin_dsn,
        TENANT_PROVISIONING_SPEC,
    )
    assert not hasattr(infrastructure, "migration_ledger_present")
    assert infrastructure.manifest()["migrationPhaseVerified"] is False
    with pytest.raises(ProvisioningDriftError):
        verify_service(tenant_target.admin_dsn, TENANT_PROVISIONING_SPEC)


def test_concurrent_runners_serialize_and_observe_one_committed_history(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source(delay_seconds=0.35)},
    )

    def run_once() -> MigrationRunReport:
        return _run(tenant_target, migration_set)

    with ThreadPoolExecutor(max_workers=2) as executor:
        reports = list(executor.map(lambda _index: run_once(), range(2)))

    assert sorted(report.applied_versions for report in reports) == [(), (1,)]
    assert sorted(report.previous_version for report in reports) == [0, 1]
    assert all(report.final_version == 1 for report in reports)
    assert len(_ledger_rows(tenant_target)) == 1
