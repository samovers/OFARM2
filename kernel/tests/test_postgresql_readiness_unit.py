"""Filesystem-only unit tests for the two-database startup gate."""

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
from deployment.postgresql.tenant_contract import TENANT_CAPABILITY_CONTRACT


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
                raise AssertionError("readiness setting fixed outside transaction")
            return _Cursor([])
        if not self.transaction_started:
            raise AssertionError("readiness read outside transaction")
        if "SESSION_USER::text" in normalized:
            return _Cursor(self.identity_rows)
        if "schema_migration" in normalized:
            return _Cursor(self.history_rows)
        if "observe_tenant_contract" in normalized:
            return _Cursor(self.observer_rows)
        if "observe_security_audit_contract" in normalized:
            return _Cursor(self.observer_rows)
        raise AssertionError(f"unexpected readiness SQL: {normalized}")

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
        TENANT_CAPABILITY_CONTRACT.digest,
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
    catalog_failure: str | None = None
    loader_failure: bool = False


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
                170009,
                _TENANT_SYSTEM_IDENTIFIER,
                False,
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
                170009,
                _AUDIT_SYSTEM_IDENTIFIER,
                False,
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
        if result.loader_failure:
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


def _verify() -> readiness.PostgreSQLStartupReadinessReport:
    return readiness.verify_startup_readiness(
        tenant_readiness_dsn=_TENANT_DSN,
        audit_readiness_dsn=_AUDIT_DSN,
        package_root=_PACKAGE_ROOT,
    )


def _replace_row_value(
    rows: list[tuple[object, ...]], index: int, value: object
) -> None:
    changed = list(rows[0])
    changed[index] = value
    rows[0] = tuple(changed)


def _assert_closed(harness: _Harness) -> None:
    assert harness.tenant.rollback_calls == 1
    assert harness.tenant.close_calls == 1
    assert harness.audit.rollback_calls == 1
    assert harness.audit.close_calls == 1


def test_exact_pair_returns_only_immutable_version_state(
    harness: _Harness,
):
    report = _verify()

    assert report.ready is True
    assert report.manifest() == {
        "schemaVersion": "ofarm.postgresql-startup-readiness.v1",
        "ready": True,
        "tenant": {"supportedVersion": 1, "observedVersion": 1},
        "securityAudit": {"supportedVersion": 1, "observedVersion": 1},
    }
    with pytest.raises(FrozenInstanceError):
        report.tenant_observed_version = 2

    serialized = json.dumps(report.manifest(), sort_keys=True)
    for prohibited in (
        _TENANT_DSN,
        _AUDIT_DSN,
        _TENANT_SYSTEM_IDENTIFIER,
        _AUDIT_SYSTEM_IDENTIFIER,
        "tenant-password",
        "audit-password",
        SECURITY_AUDIT_CONTRACT.event_format_identity,
    ):
        assert prohibited not in serialized

    assert harness.loader_calls == [
        (_PACKAGE_ROOT, TENANT_SERVICE),
        (_PACKAGE_ROOT, SECURITY_AUDIT_SERVICE),
    ]
    assert harness.connect_calls == [
        (
            _TENANT_DSN,
            {"autocommit": True, "connect_timeout": 5},
        ),
        (
            _AUDIT_DSN,
            {"autocommit": True, "connect_timeout": 5},
        ),
    ]
    assert harness.catalog_calls == [
        ("tenant", TENANT_SERVICE),
        ("security-audit", SECURITY_AUDIT_SERVICE),
    ]
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
    for connection in (harness.tenant, harness.audit):
        history_event = next(
            index
            for index, (label, statement) in enumerate(harness.events)
            if label == connection.label and "schema_migration" in statement
        )
        catalog_event = harness.events.index(
            (connection.label, "VERIFY CATALOG IDENTITY")
        )
        observer_event = next(
            index
            for index, (label, statement) in enumerate(harness.events)
            if label == connection.label and "observe_" in statement
        )
        assert history_event < catalog_event < observer_event

    governed_sql = " ".join(
        harness.tenant.statements + harness.audit.statements
    )
    assert re.search(
        r"\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE)\b",
        governed_sql,
        re.IGNORECASE,
    ) is None
    history_sql = [
        statement
        for statement in harness.tenant.statements + harness.audit.statements
        if "schema_migration" in statement
    ]
    assert len(history_sql) == 2
    for statement in history_sql:
        assert "release_identity" not in statement
        assert "execution_id" not in statement
        assert "applied_at" not in statement
        for column in (
            "version",
            "filename",
            "source_sha256",
            "source_byte_length",
            "applied_prefix_digest",
            "service_identity",
            "provisioning_spec_digest",
        ):
            assert column in statement
    _assert_closed(harness)


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
def test_every_readiness_ledger_column_is_exact(
    harness: _Harness,
    index: int,
    changed: object,
):
    _replace_row_value(harness.tenant.history_rows, index, changed)

    with pytest.raises(
        readiness.PostgreSQLReadinessError,
        match="tenant migration history differs",
    ):
        _verify()
    _assert_closed(harness)


def test_extra_or_missing_history_rows_refuse(
    harness: _Harness,
):
    harness.tenant.history_rows.append(harness.tenant.history_rows[0])

    with pytest.raises(
        readiness.PostgreSQLReadinessError,
        match="tenant migration history differs",
    ):
        _verify()
    _assert_closed(harness)


@pytest.mark.parametrize(
    ("lane", "index", "changed"),
    (
        ("tenant", 0, "ofarm_app"),
        ("tenant", 1, "ofarm_app"),
        ("tenant", 2, "crossed_database"),
        ("tenant", 3, 180000),
        ("tenant", 4, "not-a-system-id"),
        ("tenant", 5, True),
        ("tenant", 6, "read committed"),
        ("tenant", 7, "off"),
        ("tenant", 8, "off"),
        ("tenant", 9, "Europe/Ljubljana"),
        ("tenant", 10, "SQL, DMY"),
        ("tenant", 11, "on"),
        ("security-audit", 0, "ofarm_security_audit_readiness"),
        ("security-audit", 1, "ofarm_security_audit_readiness"),
        ("security-audit", 2, "ofarm_tenant"),
    ),
)
def test_route_transaction_and_primary_identity_are_exact(
    harness: _Harness,
    lane: str,
    index: int,
    changed: object,
):
    connection = harness.tenant if lane == "tenant" else harness.audit
    _replace_row_value(connection.identity_rows, index, changed)

    with pytest.raises(readiness.PostgreSQLReadinessError):
        _verify()
    _assert_closed(harness)


def test_pair_requires_same_postgresql_patch_and_distinct_lineages(
    harness: _Harness,
):
    _replace_row_value(harness.audit.identity_rows, 3, 170010)
    with pytest.raises(
        readiness.PostgreSQLReadinessError,
        match="PostgreSQL versions differ",
    ):
        _verify()
    _assert_closed(harness)


def test_pair_refuses_one_cluster_lineage(harness: _Harness):
    _replace_row_value(
        harness.audit.identity_rows,
        4,
        _TENANT_SYSTEM_IDENTIFIER,
    )
    with pytest.raises(
        readiness.PostgreSQLReadinessError,
        match="database lineages are not distinct",
    ):
        _verify()
    _assert_closed(harness)


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
def test_all_eleven_tenant_observer_fields_are_validated(
    harness: _Harness,
    index: int,
    changed: object,
):
    _replace_row_value(harness.tenant.observer_rows, index, changed)

    with pytest.raises(
        readiness.PostgreSQLReadinessError,
        match="tenant contract observation differs",
    ):
        _verify()
    _assert_closed(harness)


@pytest.mark.parametrize("index", range(14))
def test_all_fourteen_audit_observer_fields_are_exact(
    harness: _Harness,
    index: int,
):
    row = harness.audit.observer_rows[0]
    changed = list(row)
    if index in (6, 9):
        changed[index] = True
    elif index == 11:
        changed[index] = False
    elif index == 12:
        changed[index] = True
    elif index == 13:
        changed[index] = True
    else:
        changed[index] = "wrong"
    harness.audit.observer_rows[0] = tuple(changed)

    with pytest.raises(
        readiness.PostgreSQLReadinessError,
        match="security-audit contract observation differs",
    ):
        _verify()
    _assert_closed(harness)


@pytest.mark.parametrize("lane", ("tenant", "security-audit"))
@pytest.mark.parametrize("row_count", (0, 2))
def test_observers_must_return_exactly_one_row(
    harness: _Harness,
    lane: str,
    row_count: int,
):
    connection = harness.tenant if lane == "tenant" else harness.audit
    row = connection.observer_rows[0]
    connection.observer_rows[:] = [row] * row_count

    with pytest.raises(readiness.PostgreSQLReadinessError):
        _verify()
    _assert_closed(harness)


def test_authoritative_loader_failure_is_sanitized_before_connect(
    harness: _Harness,
):
    harness.loader_failure = True

    with pytest.raises(readiness.PostgreSQLReadinessError) as raised:
        _verify()
    rendered = str(raised.value)
    assert "authoritative migration identity is unavailable" in rendered
    assert "tenant-event-id" not in rendered
    assert str(_PACKAGE_ROOT) not in rendered
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert harness.connect_calls == []
    assert harness.tenant.close_calls == 0
    assert harness.audit.close_calls == 0


def test_audit_connection_failure_sanitizes_and_closes_tenant_snapshot(
    harness: _Harness,
):
    harness.connect_failures.add(_AUDIT_DSN)

    with pytest.raises(readiness.PostgreSQLReadinessError) as raised:
        _verify()
    rendered = str(raised.value)
    for prohibited in (
        _AUDIT_DSN,
        "audit-password",
        _AUDIT_SYSTEM_IDENTIFIER,
    ):
        assert prohibited not in rendered
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert harness.tenant.rollback_calls == 1
    assert harness.tenant.close_calls == 1
    assert harness.audit.rollback_calls == 0
    assert harness.audit.close_calls == 0


def test_cleanup_failure_refuses_without_leaking_cleanup_diagnostic(
    harness: _Harness,
):
    harness.audit.fail_rollback = True

    with pytest.raises(readiness.PostgreSQLReadinessError) as raised:
        _verify()
    assert "readiness transaction cleanup failed" in str(raised.value)
    assert "password" not in str(raised.value)
    assert "system identifier" not in str(raised.value)
    _assert_closed(harness)


def test_catalog_identity_failure_is_sanitized_and_closes_both_snapshots(
    harness: _Harness,
):
    harness.catalog_failure = "security-audit"

    with pytest.raises(readiness.PostgreSQLReadinessError) as raised:
        _verify()

    assert str(raised.value).endswith(
        "security-audit catalog verifier identity differs"
    )
    assert "password" not in str(raised.value)
    assert "system identifier" not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    _assert_closed(harness)


def test_process_interruption_still_rolls_back_and_closes_both_snapshots(
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
        _verify()
    _assert_closed(harness)
