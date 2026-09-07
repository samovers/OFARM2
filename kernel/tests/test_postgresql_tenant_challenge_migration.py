"""Challenge observation migration through the public, exact-release runner."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

import deployment.postgresql.migration_runner as migration_runner
from deployment.postgresql.migration_runner import (
    MigrationDirtyError,
    MigrationExecutionError,
    MigrationRunReport,
)
from deployment.postgresql.migration_sets import (
    TENANT_SERVICE,
    MigrationSet,
    load_authoritative_migration_set,
)
from deployment.postgresql.provisioning_specs import TENANT_PROVISIONING_SPEC
from kernel.tests.test_postgresql_migration_runner import (
    _TenantTarget,
    _ledger_rows,
    tenant_target,  # noqa: F401 - existing fresh provision/password/cleanup fixture
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_RELEASE = "ofarm-tests/issue-375-challenge-observation"
_V10_PREFIX = (
    "sha256:bd80785f567e593edea9f88898c18cc8b8269bc8d71eb5aa385c595abc9d7b95"
)
_V10_VERIFIER_SOURCE = (
    "8af1cd56b249145440eca1d68b6f1d3da105e697f1dec5c6d324b7a8b709fc22"
)


def _run(target: _TenantTarget, migration_set: MigrationSet) -> MigrationRunReport:
    return migration_runner.migrate_service(
        admin_dsn=target.admin_dsn,
        migrator_dsn=target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=migration_set,
        release_identity=_RELEASE,
        execution_id=uuid4(),
    )


def _state(target: _TenantTarget) -> tuple[object, ...]:
    with psycopg.connect(target.migrator_dsn) as migrator:
        migrator.execute("SET LOCAL ROLE ofarm_owner")
        return migrator.execute(
            """
            SELECT observation.structurally_compatible,
                   observation.difference_count,
                   observation.migration_head_version,
                   observation.applied_prefix_digest,
                   observation.migration_row_count,
                   pg_catalog.to_regprocedure(
                       'ofarm.current_tenant_challenge()'
                   ) IS NOT NULL,
                   pg_catalog.encode(
                       pg_catalog.sha256(
                           pg_catalog.convert_to(routine.prosrc, 'UTF8')
                       ), 'hex'
                   )
            FROM ofarm.verify_tenant_structure() AS observation
            JOIN pg_catalog.pg_proc AS routine
              ON routine.oid =
                 'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure
            """
        ).fetchone()


def _execute_admin(target: _TenantTarget, statement: str) -> None:
    # All statements are fixed test literals against the disposable service.
    with psycopg.connect(target.target_admin_dsn) as admin:
        admin.execute(statement)


def test_challenge_migration_rollback_upgrade_replay_and_drift_refusal(
    tenant_target: _TenantTarget,  # noqa: F811 - imported pytest fixture
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration_set = load_authoritative_migration_set(_PACKAGE_ROOT, TENANT_SERVICE)
    assert len(migration_set.migrations) == 11
    original_insert = migration_runner._insert_ledger_row
    reached_version_11: list[int] = []

    def refuse_version_11_ledger(
        connection, spec, current_set, migration, release_identity, execution_id
    ) -> None:
        if migration.version == 11:
            # The genuine migration DDL has completed, but its ledger row has
            # not been appended. A database error must roll both back together.
            assert connection.execute(
                "SELECT pg_catalog.to_regprocedure("
                "'ofarm.current_tenant_challenge()') IS NOT NULL, "
                "(SELECT pg_catalog.max(version) FROM ofarm.schema_migration)"
            ).fetchone() == (True, 10)
            reached_version_11.append(migration.version)
            connection.execute("SELECT 1 / 0")
            raise AssertionError("the database must reject division by zero")
        original_insert(
            connection, spec, current_set, migration, release_identity, execution_id
        )

    # Use the complete current release from a fresh target. The only injection
    # is a database failure at the existing pre-ledger seam; no historical set
    # is declared authoritative and no test-only runner admission is widened.
    with monkeypatch.context() as patch:
        patch.setattr(migration_runner, "_insert_ledger_row", refuse_version_11_ledger)
        with pytest.raises(MigrationExecutionError) as refused:
            _run(tenant_target, migration_set)
    assert refused.value.version == 11
    assert refused.value.filename == "0011_tenant_challenge_observation.sql"
    assert isinstance(refused.value.__cause__, psycopg.errors.DivisionByZero)
    assert reached_version_11 == [11]
    assert _state(tenant_target) == (
        True, 0, 10, _V10_PREFIX, 10, False, _V10_VERIFIER_SOURCE
    )
    v10_history = _ledger_rows(tenant_target)
    assert [row[0] for row in v10_history] == list(range(1, 11))

    # A privileged configuration change is fixture-controlled drift, not a
    # runtime attacker capability. The release must refuse it without repair.
    _execute_admin(
        tenant_target, "ALTER FUNCTION ofarm.current_tenant_id() COST 101"
    )
    try:
        with pytest.raises((MigrationDirtyError, MigrationExecutionError)):
            _run(tenant_target, migration_set)
        drifted = _state(tenant_target)
        assert drifted[0] is False
        assert drifted[1] > 0
        assert drifted[2:6] == (10, _V10_PREFIX, 10, False)
        assert _ledger_rows(tenant_target) == v10_history
    finally:
        _execute_admin(
            tenant_target, "ALTER FUNCTION ofarm.current_tenant_id() COST 100"
        )
    assert _state(tenant_target) == (
        True, 0, 10, _V10_PREFIX, 10, False, _V10_VERIFIER_SOURCE
    )

    upgraded = _run(tenant_target, migration_set)
    assert upgraded.previous_version == 10
    assert upgraded.applied_versions == (11,)
    assert upgraded.final_version == 11
    assert upgraded.verified_noop is False
    assert _state(tenant_target)[:6] == (
        True, 0, 11, migration_set.digest, 11, True
    )
    v11_history = _ledger_rows(tenant_target)
    assert v11_history[:10] == v10_history

    replay = _run(tenant_target, migration_set)
    assert replay.previous_version == replay.final_version == 11
    assert replay.applied_versions == ()
    assert replay.verified_noop is True
    assert replay.observed_head_execution_id == upgraded.execution_id
    assert _ledger_rows(tenant_target) == v11_history

    for change, restore in (
        (
            "ALTER FUNCTION ofarm.current_tenant_challenge() VOLATILE",
            "ALTER FUNCTION ofarm.current_tenant_challenge() STABLE",
        ),
        (
            "GRANT EXECUTE ON FUNCTION ofarm.current_tenant_challenge() "
            "TO ofarm_readiness",
            "REVOKE EXECUTE ON FUNCTION ofarm.current_tenant_challenge() "
            "FROM ofarm_readiness",
        ),
    ):
        _execute_admin(tenant_target, change)
        try:
            with pytest.raises(MigrationDirtyError):
                _run(tenant_target, migration_set)
            drifted = _state(tenant_target)
            assert drifted[0] is False
            assert drifted[1] > 0
            assert drifted[2:6] == (11, migration_set.digest, 11, True)
            assert _ledger_rows(tenant_target) == v11_history
        finally:
            _execute_admin(tenant_target, restore)
        assert _state(tenant_target)[:6] == (
            True, 0, 11, migration_set.digest, 11, True
        )
