"""Filesystem-only tests for PostgreSQL structural observations."""

from __future__ import annotations

import json
import re
from dataclasses import FrozenInstanceError, dataclass, field
from pathlib import Path

import pytest

import deployment.postgresql.readiness as readiness
from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    MigrationSet,
    load_migration_set,
)
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC,
)
from deployment.postgresql.tenant_contract import TENANT_CONTEXT_CONTRACT
from deployment.postgresql.version_policy import (
    SUPPORTED_POSTGRESQL_SERVER_VERSION,
    SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_TENANT_DSN = "postgresql://ofarm_readiness:tenant-password@tenant.invalid/db"
_AUDIT_DSN = (
    "postgresql://ofarm_security_audit_readiness_login:"
    "audit-password@audit.invalid/db"
)
_TENANT_SYSTEM_IDENTIFIER = "7411111111111111111"
_AUDIT_SYSTEM_IDENTIFIER = "7422222222222222222"
_DERIVED_DIGEST_A = "sha256:" + "a" * 64
_DERIVED_DIGEST_B = "sha256:" + "b" * 64


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _FakeConnection:
    def __init__(
        self,
        *,
        label: str,
        events: list[tuple[str, str]],
        identity_rows: list[tuple[object, ...]],
        history_rows: list[tuple[object, ...]],
        observer_rows: list[tuple[object, ...]],
    ):
        self.label = label
        self.events = events
        self.identity_rows = identity_rows
        self.history_rows = history_rows
        self.observer_rows = observer_rows
        self.statements: list[str] = []
        self.transaction_started = False
        self.rollback_calls = 0
        self.close_calls = 0
        self.fail_rollback = False

    def execute(self, statement: str):
        normalized = " ".join(statement.split())
        self.statements.append(normalized)
        self.events.append((self.label, normalized))
        if normalized == (
            "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
        ):
            self.transaction_started = True
            return _Cursor([])
        if normalized.startswith("SET LOCAL"):
            if not self.transaction_started:
                raise AssertionError("setting fixed outside structural transaction")
            return _Cursor([])
        if not self.transaction_started:
            raise AssertionError("structural read outside transaction")
        if "SESSION_USER::text" in normalized:
            return _Cursor(self.identity_rows)
        if "schema_migration" in normalized:
            return _Cursor(self.history_rows)
        if "observe_tenant_contract" in normalized:
            return _Cursor(self.observer_rows)
        if "observe_security_audit_contract" in normalized:
            return _Cursor(self.observer_rows)
        raise AssertionError(f"unexpected structural SQL: {normalized}")

    def rollback(self) -> None:
        self.rollback_calls += 1
        self.events.append((self.label, "ROLLBACK"))
        self.transaction_started = False
        if self.fail_rollback:
            raise RuntimeError("rollback leaked password and system identifier")

    def close(self) -> None:
        self.close_calls += 1
        self.events.append((self.label, "CLOSE"))


def _history_rows(
    migration_set: MigrationSet,
    *,
    provisioning_digest: str,
) -> list[tuple[object, ...]]:
    return [
        (
            migration.version,
            migration.filename,
            migration.source_sha256,
            migration.byte_length,
            migration_set.prefix_digest(migration.version),
            migration_set.service.identity,
            provisioning_digest,
        )
        for migration in migration_set.migrations
    ]


def _tenant_observer_row(migration_set: MigrationSet) -> tuple[object, ...]:
    version = len(migration_set.migrations)
    return (
        True,
        TENANT_CONTEXT_CONTRACT.digest,
        0,
        _DERIVED_DIGEST_A,
        _DERIVED_DIGEST_B,
        TENANT_PROVISIONING_SPEC.digest,
        TENANT_SERVICE.identity,
        version,
        migration_set.prefix_digest(version),
        version,
        False,
    )


def _audit_observer_row(migration_set: MigrationSet) -> tuple[object, ...]:
    version = len(migration_set.migrations)
    return (
        SECURITY_AUDIT_CONTRACT.identity,
        SECURITY_AUDIT_CONTRACT.digest,
        SECURITY_AUDIT_CONTRACT.event_format_identity,
        SECURITY_AUDIT_CONTRACT.redaction_policy_identity,
        SECURITY_AUDIT_CONTRACT.retention_policy_identity,
        SECURITY_AUDIT_CONTRACT.correlation_hmac.domain,
        SECURITY_AUDIT_CONTRACT.correlation_hmac.key_version,
        SECURITY_AUDIT_SERVICE.identity,
        SECURITY_AUDIT_PROVISIONING_SPEC.digest,
        version,
        migration_set.prefix_digest(version),
        True,
        False,
    )


@dataclass
class _Harness:
    tenant_set: MigrationSet
    audit_set: MigrationSet
    tenant: _FakeConnection
    audit: _FakeConnection
    events: list[tuple[str, str]]
    loader_calls: list[tuple[Path, object]] = field(default_factory=list)
    connect_calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)
    catalog_calls: list[tuple[str, object]] = field(default_factory=list)
    connect_failures: set[str] = field(default_factory=set)
    loader_failures: set[object] = field(default_factory=set)
    catalog_failure: str | None = None


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> _Harness:
    tenant_set = load_migration_set(_PACKAGE_ROOT, TENANT_SERVICE)
    audit_set = load_migration_set(_PACKAGE_ROOT, SECURITY_AUDIT_SERVICE)
    events: list[tuple[str, str]] = []
    tenant = _FakeConnection(
        label="tenant",
        events=events,
        identity_rows=[
            (
                "ofarm_readiness",
                "ofarm_readiness",
                "ofarm_tenant",
                SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
                SUPPORTED_POSTGRESQL_SERVER_VERSION,
                _TENANT_SYSTEM_IDENTIFIER,
                "repeatable read",
                "on",
                "on",
                "UTC",
                "ISO, MDY",
                "off",
            )
        ],
        history_rows=_history_rows(
            tenant_set,
            provisioning_digest=TENANT_PROVISIONING_SPEC.digest,
        ),
        observer_rows=[_tenant_observer_row(tenant_set)],
    )
    audit = _FakeConnection(
        label="security-audit",
        events=events,
        identity_rows=[
            (
                "ofarm_security_audit_readiness_login",
                "ofarm_security_audit_readiness_login",
                "ofarm_security_audit",
                SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
                SUPPORTED_POSTGRESQL_SERVER_VERSION,
                _AUDIT_SYSTEM_IDENTIFIER,
                "repeatable read",
                "on",
                "on",
                "UTC",
                "ISO, MDY",
                "off",
            )
        ],
        history_rows=_history_rows(
            audit_set,
            provisioning_digest=SECURITY_AUDIT_PROVISIONING_SPEC.digest,
        ),
        observer_rows=[_audit_observer_row(audit_set)],
    )
    result = _Harness(tenant_set, audit_set, tenant, audit, events)

    def fake_loader(package_root: Path, service):
        result.loader_calls.append((package_root, service))
        if service in result.loader_failures:
            raise RuntimeError(
                "migration load leaked tenant-event-id and filesystem path"
            )
        if service is TENANT_SERVICE:
            return result.tenant_set
        if service is SECURITY_AUDIT_SERVICE:
            return result.audit_set
        raise AssertionError("unexpected service")

    def fake_connect(dsn: str, **kwargs):
        result.connect_calls.append((dsn, kwargs))
        if dsn in result.connect_failures:
            raise RuntimeError(
                f"could not connect to {dsn}; system={_AUDIT_SYSTEM_IDENTIFIER}"
            )
        if dsn == _TENANT_DSN:
            return result.tenant
        if dsn == _AUDIT_DSN:
            return result.audit
        raise AssertionError("unexpected DSN")

    def fake_catalog_verifier(connection: _FakeConnection, service):
        result.catalog_calls.append((connection.label, service))
        result.events.append((connection.label, "VERIFY CATALOG IDENTITY"))
        if result.catalog_failure == connection.label:
            raise readiness.CatalogIdentityError(
                "catalog identity leaked password and system identifier"
            )

    monkeypatch.setattr(readiness, "load_authoritative_migration_set", fake_loader)
    monkeypatch.setattr(readiness.psycopg, "connect", fake_connect)
    monkeypatch.setattr(readiness, "verify_catalog_identity", fake_catalog_verifier)
    return result


def _verify_tenant() -> readiness.PostgreSQLStructuralCompatibilityReport:
    return readiness.verify_tenant_structural_compatibility(
        tenant_structural_dsn=_TENANT_DSN,
        package_root=_PACKAGE_ROOT,
    )


def _verify_audit() -> readiness.PostgreSQLStructuralCompatibilityReport:
    return readiness.verify_security_audit_structural_compatibility(
        audit_structural_dsn=_AUDIT_DSN,
        package_root=_PACKAGE_ROOT,
    )


def _verify_separation() -> readiness.PostgreSQLServiceSeparationAttestation:
    return readiness.verify_postgresql_service_separation(
        tenant_structural_dsn=_TENANT_DSN,
        audit_structural_dsn=_AUDIT_DSN,
    )


def _replace_row_value(
    rows: list[tuple[object, ...]], index: int, value: object
) -> None:
    changed = list(rows[0])
    changed[index] = value
    rows[0] = tuple(changed)


def _assert_lane_closed(connection: _FakeConnection) -> None:
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1


def _assert_lane_untouched(connection: _FakeConnection) -> None:
    assert connection.rollback_calls == 0
    assert connection.close_calls == 0
    assert connection.statements == []


def test_public_api_contains_only_structural_and_separation_results():
    assert set(readiness.__all__) == {
        "PostgreSQLServiceSeparationAttestation",
        "PostgreSQLStructuralCompatibilityReport",
        "PostgreSQLVerificationError",
        "verify_postgresql_service_separation",
        "verify_security_audit_structural_compatibility",
        "verify_tenant_structural_compatibility",
    }
    for removed in (
        "PostgreSQLReadinessError",
        "PostgreSQLStartupReadinessReport",
        "verify_startup_readiness",
    ):
        assert not hasattr(readiness, removed)


def test_tenant_structural_report_is_independent_and_has_no_service_decision(
    harness: _Harness,
):
    harness.connect_failures.add(_AUDIT_DSN)
    harness.loader_failures.add(SECURITY_AUDIT_SERVICE)

    report = _verify_tenant()

    assert report.manifest() == {
        "schemaVersion": "ofarm.postgresql-structural-compatibility.v1",
        "serviceIdentity": TENANT_SERVICE.identity,
        "supportedVersion": 5,
        "observedVersion": 5,
    }
    assert not hasattr(report, "ready")
    assert not hasattr(report, "runtime_ready")
    assert not hasattr(report, "recovery_ready")
    serialized = json.dumps(report.manifest(), sort_keys=True)
    assert "ready" not in serialized.lower()
    assert "recovery" not in serialized.lower()
    assert harness.loader_calls == [(_PACKAGE_ROOT, TENANT_SERVICE)]
    assert harness.connect_calls == [
        (_TENANT_DSN, {"autocommit": True, "connect_timeout": 5})
    ]
    assert harness.catalog_calls == [("tenant", TENANT_SERVICE)]
    with pytest.raises(FrozenInstanceError):
        report.observed_version = 3
    _assert_lane_closed(harness.tenant)
    _assert_lane_untouched(harness.audit)


def test_audit_structural_report_is_independent_of_tenant_lane(
    harness: _Harness,
):
    harness.connect_failures.add(_TENANT_DSN)
    harness.loader_failures.add(TENANT_SERVICE)

    report = _verify_audit()

    assert report.manifest() == {
        "schemaVersion": "ofarm.postgresql-structural-compatibility.v1",
        "serviceIdentity": SECURITY_AUDIT_SERVICE.identity,
        "supportedVersion": 3,
        "observedVersion": 3,
    }
    assert harness.loader_calls == [(_PACKAGE_ROOT, SECURITY_AUDIT_SERVICE)]
    assert harness.connect_calls == [
        (_AUDIT_DSN, {"autocommit": True, "connect_timeout": 5})
    ]
    assert harness.catalog_calls == [
        ("security-audit", SECURITY_AUDIT_SERVICE)
    ]
    _assert_lane_untouched(harness.tenant)
    _assert_lane_closed(harness.audit)


def test_promoted_physical_clone_observation_has_no_promotion_result(
    harness: _Harness,
):
    """A promoted clone is structurally indistinguishable without #193."""

    promoted_clone_observation = {
        "sourceSystemIdentifier": _TENANT_SYSTEM_IDENTIFIER,
        "observedSystemIdentifier": harness.tenant.identity_rows[0][5],
        "pgIsInRecovery": False,
    }
    assert promoted_clone_observation == {
        "sourceSystemIdentifier": _TENANT_SYSTEM_IDENTIFIER,
        "observedSystemIdentifier": _TENANT_SYSTEM_IDENTIFIER,
        "pgIsInRecovery": False,
    }

    report = _verify_tenant()

    # A physical copy preserves the source system identifier.  After promotion
    # PostgreSQL reports a current non-recovery state, but this structural query
    # deliberately asks neither that question nor any historical-provenance one.
    identity_sql = next(
        statement
        for statement in harness.tenant.statements
        if "SESSION_USER::text" in statement
    )
    assert "pg_is_in_recovery" not in identity_sql
    assert report.manifest() == {
        "schemaVersion": "ofarm.postgresql-structural-compatibility.v1",
        "serviceIdentity": TENANT_SERVICE.identity,
        "supportedVersion": 5,
        "observedVersion": 5,
    }
    serialized = json.dumps(report.manifest(), sort_keys=True).lower()
    for prohibited in (
        "ready",
        "recovery",
        "primary",
        "continuity",
        "promotion",
        "provenance",
        "systemidentifier",
    ):
        assert prohibited not in serialized
    _assert_lane_closed(harness.tenant)
    _assert_lane_untouched(harness.audit)


def test_separation_is_narrow_and_opens_both_snapshots_before_observation(
    harness: _Harness,
):
    attestation = _verify_separation()

    assert attestation.manifest() == {
        "schemaVersion": "ofarm.postgresql-service-separation.v1",
        "tenantServiceIdentity": TENANT_SERVICE.identity,
        "securityAuditServiceIdentity": SECURITY_AUDIT_SERVICE.identity,
        "distinctPostgreSQLSystemIdentifiers": True,
    }
    serialized = json.dumps(attestation.manifest(), sort_keys=True).lower()
    for prohibited in ("ready", "recovery", "primary", "continuity", "promotion"):
        assert prohibited not in serialized
    assert harness.loader_calls == []
    assert harness.catalog_calls == []
    first_read = next(
        index
        for index, (_label, statement) in enumerate(harness.events)
        if statement.startswith("SELECT")
    )
    audit_begin = harness.events.index(
        (
            "security-audit",
            "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
        )
    )
    assert audit_begin < first_read
    assert all(
        "schema_migration" not in statement and "observe_" not in statement
        for statement in harness.tenant.statements + harness.audit.statements
    )
    _assert_lane_closed(harness.tenant)
    _assert_lane_closed(harness.audit)


def test_structural_observation_is_read_only_and_orders_exact_checks(
    harness: _Harness,
):
    _verify_tenant()

    history_event = next(
        index
        for index, (label, statement) in enumerate(harness.events)
        if label == "tenant" and "schema_migration" in statement
    )
    catalog_event = harness.events.index(("tenant", "VERIFY CATALOG IDENTITY"))
    observer_event = next(
        index
        for index, (label, statement) in enumerate(harness.events)
        if label == "tenant" and "observe_tenant_contract" in statement
    )
    assert history_event < catalog_event < observer_event
    governed_sql = " ".join(harness.tenant.statements)
    assert re.search(
        r"\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE)\b",
        governed_sql,
        re.IGNORECASE,
    ) is None
    _assert_lane_closed(harness.tenant)


@pytest.mark.parametrize("server_version", (170009, 170011, 170100, 180000))
def test_structural_observation_accepts_only_postgresql_17_10(
    harness: _Harness,
    server_version: int,
):
    _replace_row_value(harness.tenant.identity_rows, 3, server_version)

    with pytest.raises(
        readiness.PostgreSQLVerificationError,
        match="PostgreSQL version differs",
    ):
        _verify_tenant()
    _assert_lane_closed(harness.tenant)


@pytest.mark.parametrize(
    "server_version",
    (
        "17.10",
        "17.10 (Debian 17.10-1.pgdg13+2)",
        "17.10 (Ubuntu 17.10-1)",
    ),
)
def test_structural_observation_accepts_only_the_pinned_build_string(
    harness: _Harness,
    server_version: str,
):
    _replace_row_value(harness.tenant.identity_rows, 4, server_version)

    with pytest.raises(
        readiness.PostgreSQLVerificationError,
        match="PostgreSQL version differs",
    ):
        _verify_tenant()
    _assert_lane_closed(harness.tenant)


@pytest.mark.parametrize(
    ("index", "changed"),
    (
        (0, "ofarm_app"),
        (1, "ofarm_app"),
        (2, "crossed_database"),
        (5, "not-a-system-id"),
        (6, "read committed"),
        (7, "off"),
        (8, "off"),
        (9, "Europe/Ljubljana"),
        (10, "SQL, DMY"),
        (11, "on"),
    ),
)
def test_route_and_structural_transaction_identity_are_exact(
    harness: _Harness,
    index: int,
    changed: object,
):
    _replace_row_value(harness.tenant.identity_rows, index, changed)

    with pytest.raises(readiness.PostgreSQLVerificationError):
        _verify_tenant()
    _assert_lane_closed(harness.tenant)


def test_separation_refuses_one_system_identifier(harness: _Harness):
    _replace_row_value(
        harness.audit.identity_rows,
        5,
        _TENANT_SYSTEM_IDENTIFIER,
    )

    with pytest.raises(
        readiness.PostgreSQLVerificationError,
        match="use one PostgreSQL system identifier",
    ):
        _verify_separation()
    _assert_lane_closed(harness.tenant)
    _assert_lane_closed(harness.audit)


@pytest.mark.parametrize(
    ("index", "changed"),
    (
        (0, True),
        (1, "0001_changed.sql"),
        (2, "sha256:" + "c" * 64),
        (3, True),
        (4, "sha256:" + "d" * 64),
        (5, "wrong.service"),
        (6, "sha256:" + "e" * 64),
    ),
)
def test_every_tenant_ledger_column_is_exact(
    harness: _Harness,
    index: int,
    changed: object,
):
    _replace_row_value(harness.tenant.history_rows, index, changed)

    with pytest.raises(
        readiness.PostgreSQLVerificationError,
        match="tenant migration history differs",
    ):
        _verify_tenant()
    _assert_lane_closed(harness.tenant)


def test_extra_or_missing_history_rows_refuse(harness: _Harness):
    harness.tenant.history_rows.append(harness.tenant.history_rows[0])
    with pytest.raises(
        readiness.PostgreSQLVerificationError,
        match="tenant migration history differs",
    ):
        _verify_tenant()
    _assert_lane_closed(harness.tenant)


@pytest.mark.parametrize(
    ("index", "changed"),
    (
        (0, False),
        (1, "sha256:" + "1" * 64),
        (2, 1),
        (3, "not-a-digest"),
        (4, "not-a-digest"),
        (5, "sha256:" + "2" * 64),
        (6, "wrong.service"),
        (7, True),
        (8, "sha256:" + "3" * 64),
        (9, True),
        (10, True),
    ),
)
def test_all_tenant_observer_fields_are_validated(
    harness: _Harness,
    index: int,
    changed: object,
):
    _replace_row_value(harness.tenant.observer_rows, index, changed)

    with pytest.raises(
        readiness.PostgreSQLVerificationError,
        match="tenant contract observation differs",
    ):
        _verify_tenant()
    _assert_lane_closed(harness.tenant)


@pytest.mark.parametrize("index", range(13))
def test_every_structural_audit_observer_field_is_exact(
    harness: _Harness,
    index: int,
):
    changed = list(harness.audit.observer_rows[0])
    if index in (6, 9):
        changed[index] = True
    elif index == 11:
        changed[index] = False
    elif index == 12:
        changed[index] = True
    else:
        changed[index] = "wrong"
    harness.audit.observer_rows[0] = tuple(changed)

    with pytest.raises(
        readiness.PostgreSQLVerificationError,
        match="security-audit contract observation differs",
    ):
        _verify_audit()
    _assert_lane_closed(harness.audit)


@pytest.mark.parametrize("lane", ("tenant", "security-audit"))
@pytest.mark.parametrize("row_count", (0, 2))
def test_observer_must_return_exactly_one_row(
    harness: _Harness,
    lane: str,
    row_count: int,
):
    connection = harness.tenant if lane == "tenant" else harness.audit
    row = connection.observer_rows[0]
    connection.observer_rows[:] = [row] * row_count

    with pytest.raises(readiness.PostgreSQLVerificationError):
        _verify_tenant() if lane == "tenant" else _verify_audit()
    _assert_lane_closed(connection)


def test_authoritative_loader_failure_is_lane_local_and_sanitized(
    harness: _Harness,
):
    harness.loader_failures.add(TENANT_SERVICE)

    with pytest.raises(readiness.PostgreSQLVerificationError) as raised:
        _verify_tenant()
    rendered = str(raised.value)
    assert "tenant authoritative migration identity is unavailable" in rendered
    assert "tenant-event-id" not in rendered
    assert str(_PACKAGE_ROOT) not in rendered
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert harness.connect_calls == []
    _assert_lane_untouched(harness.tenant)
    _assert_lane_untouched(harness.audit)


def test_connection_failure_is_sanitized_and_does_not_touch_peer(
    harness: _Harness,
):
    harness.connect_failures.add(_AUDIT_DSN)

    with pytest.raises(readiness.PostgreSQLVerificationError) as raised:
        _verify_audit()
    rendered = str(raised.value)
    for prohibited in (_AUDIT_DSN, "audit-password", _AUDIT_SYSTEM_IDENTIFIER):
        assert prohibited not in rendered
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    _assert_lane_untouched(harness.tenant)
    _assert_lane_untouched(harness.audit)


def test_cleanup_failure_refuses_without_leaking_diagnostic(harness: _Harness):
    harness.audit.fail_rollback = True

    with pytest.raises(readiness.PostgreSQLVerificationError) as raised:
        _verify_audit()
    assert "security-audit structural observation cleanup failed" in str(
        raised.value
    )
    assert "password" not in str(raised.value)
    assert "system identifier" not in str(raised.value)
    _assert_lane_closed(harness.audit)


def test_catalog_identity_failure_is_lane_local_and_sanitized(
    harness: _Harness,
):
    harness.catalog_failure = "security-audit"

    with pytest.raises(readiness.PostgreSQLVerificationError) as raised:
        _verify_audit()
    assert str(raised.value).endswith(
        "security-audit catalog verifier identity differs"
    )
    assert "password" not in str(raised.value)
    assert "system identifier" not in str(raised.value)
    _assert_lane_untouched(harness.tenant)
    _assert_lane_closed(harness.audit)


def test_process_interruption_still_rolls_back_and_closes_one_snapshot(
    harness: _Harness,
):
    class ProcessInterrupted(BaseException):
        pass

    original_execute = harness.tenant.execute

    def interrupt_first_read(statement: str):
        if "SESSION_USER::text" in statement:
            raise ProcessInterrupted
        return original_execute(statement)

    harness.tenant.execute = interrupt_first_read

    with pytest.raises(ProcessInterrupted):
        _verify_tenant()
    _assert_lane_closed(harness.tenant)
    _assert_lane_untouched(harness.audit)
