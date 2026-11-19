"""Verify the Submit permission without installing a production migration."""

from __future__ import annotations

import os
from dataclasses import replace
from uuid import uuid4

import psycopg
import pytest

from deployment.postgresql import migration_runner as runner
from deployment.postgresql import migration_sets, provisioning
from deployment.postgresql.provisioning_specs import SECURITY_AUDIT_PROVISIONING_SPEC
from deployment.postgresql.provisioning_specs import TENANT_PROVISIONING_SPEC as SPEC
from kernel.tests.postgresql_tenant_support import ADMIN_ENV, PACKAGE_ROOT, fresh_tenant_service
from kernel.tests.test_postgresql_migration_runner import _load_synthetic_set


NAME = "activate_submit_operation_claim_runtime_bundle_selection"
FUNCTION = f"ofarm.{NAME}(text)"
DRAFT_NAME = "activate_commit_operation_claim_draft_runtime_bundle_selection"
DRAFT = f"ofarm.{DRAFT_NAME}(text)"
CONTROLLER = "ofarm_command_runtime_bundle_selection_controller"
LOGIN = "ofarm_command_runtime_bundle_selection_control_login"
FILENAME = "0013_tenant_submit_operation_claim_runtime_bundle_selection.sql"
LABEL = "ofarm-tests/submit-provisioning"
INVENTORY = "tenant Submit selection activation routine inventory differs"
ACL = "tenant Submit selection activation routine ACL differs"
FAMILY = "tenant binding selection-control admission ACL differs"
TRANSITION = "tenant Submit selection activation transition differs"

# Inert test input. No selection data, writes, or call to an activation function.
CREATE = (
    f"CREATE FUNCTION {FUNCTION} RETURNS text LANGUAGE sql SECURITY DEFINER "
    "SET search_path = pg_catalog, pg_temp AS 'SELECT NULL::pg_catalog.text'"
)
GRANT = f"GRANT EXECUTE ON FUNCTION {FUNCTION} TO {CONTROLLER}"
REVOKE = f"REVOKE EXECUTE ON FUNCTION {FUNCTION} FROM {CONTROLLER}"
SOURCE = f"{CREATE}; REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC; {GRANT};"


def _admin_dsn():
    if dsn := os.environ.get(ADMIN_ENV):
        return dsn
    pytest.skip(f"{ADMIN_ENV} is required for real PostgreSQL tests")


def _run(target, release, execution_id=None):
    return runner.migrate_service(
        admin_dsn=target.admin_dsn, migrator_dsn=target.migrator_dsn, spec=SPEC,
        migration_set=release, release_identity=LABEL, execution_id=execution_id or uuid4(),
    )


def _run_through_predecessor(service, observe_head=None):
    """Apply the real release through its twelfth commit, including after #430 lands."""
    class ReachedPredecessor(Exception):
        pass

    commit = runner._commit

    def through_twelve(conn, migration, execution_id):
        commit(conn, migration, execution_id)
        if observe_head is not None:
            observe_head(migration.version)
        if migration.version == 12:
            raise ReachedPredecessor

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(runner, "_commit", through_twelve)
        with pytest.raises(ReachedPredecessor):
            _run(service, service.migration_set)


@pytest.fixture(scope="class")
def target():
    with fresh_tenant_service(_admin_dsn()) as service:
        _run_through_predecessor(service)
        yield service


@pytest.fixture(scope="module")
def release(tmp_path_factory):
    previous = migration_sets.load_migration_set(PACKAGE_ROOT, migration_sets.TENANT_SERVICE)
    sources = {migration.filename: migration.source_bytes for migration in previous.migrations[:12]}
    return _load_synthetic_set(tmp_path_factory.mktemp("submit"), {**sources, FILENAME: SOURCE.encode()})


@pytest.fixture
def binding(release, monkeypatch):
    entry = release.migrations[-1]
    literal = migration_sets.AuthoritativeMigration(
        entry.version, entry.filename, entry.source_sha256, entry.byte_length, release.digest,
    )
    original = migration_sets.TENANT_AUTHORITATIVE_MIGRATION_SET
    bound = replace(original, migrations=(*original.migrations[:12], literal), digest=release.digest)
    monkeypatch.setattr(provisioning, "TENANT_AUTHORITATIVE_MIGRATION_SET", bound)
    monkeypatch.setattr(migration_sets, "AUTHORITATIVE_MIGRATION_SETS", (
        bound, migration_sets.SECURITY_AUDIT_AUTHORITATIVE_MIGRATION_SET,
    ))
    return bound


def _snapshot(connection):
    history = connection.execute("SELECT * FROM ofarm.schema_migration ORDER BY version").fetchall()
    grants = connection.execute("""
        SELECT n.nspname::text, p.proname::text, pg_catalog.oidvectortypes(p.proargtypes),
               a.grantor::regrole::text, a.privilege_type, a.is_grantable
        FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(p.proacl) a
        WHERE a.grantee = %s::regrole ORDER BY 1, 2, 3
    """, (CONTROLLER,)).fetchall()
    inventory = connection.execute("""
        SELECT n.nspname::text, p.proname::text, pg_catalog.oidvectortypes(p.proargtypes),
               p.prokind, p.prosecdef, p.proowner::regrole::text, p.proacl::text
        FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        WHERE p.proname = ANY (%s) ORDER BY 1, 2, 3
    """, ([NAME, DRAFT_NAME],)).fetchall()
    return history, grants, inventory


def _observe(target):
    with psycopg.connect(target.target_admin_dsn) as observer:
        observer.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        return _snapshot(observer)


def test_unreleased_and_synthetic_sources_refuse_before_connecting(release):
    arguments = dict(
        admin_dsn="", migrator_dsn="", spec=SPEC, migration_set=release,
        release_identity=LABEL, execution_id=uuid4(),
    )
    with pytest.raises(runner.MigrationInputError, match="literal authoritative release"):
        runner.migrate_service(**arguments)
    with pytest.raises(runner.MigrationInputError, match="test migration executor.*Submit"):
        runner._migrate_service_for_testing(**arguments)
    with pytest.raises(runner.MigrationInputError, match="service"):
        runner.migrate_service(**{**arguments, "spec": SECURITY_AUDIT_PROVISIONING_SPEC})


def test_substituted_bytes_refuse_before_connecting(binding, release):
    last = release.migrations[-1]
    changed = replace(last, source_bytes=last.source_bytes.replace(b"NULL", b"null"))
    with pytest.raises(runner.MigrationInputError, match="sha256|digest|identity"):
        runner.migrate_service(
            admin_dsn="", migrator_dsn="", spec=SPEC, release_identity=LABEL, execution_id=uuid4(),
            migration_set=replace(release, migrations=(*release.migrations[:-1], changed)),
        )


@pytest.mark.parametrize("change", ["other-file", "other-prefix", "next-head", "other-service"])
def test_release_slot_stays_closed(binding, monkeypatch, change):
    entries = list(binding.migrations)
    service = binding.service
    if change == "other-file":
        entries[-1] = replace(entries[-1], filename="0013_other.sql")
    elif change == "other-prefix":
        entries[-2] = replace(entries[-2], applied_prefix_digest=entries[-1].applied_prefix_digest)
    elif change == "next-head":
        entries.append(replace(entries[-1], version=14))
    else:
        service = migration_sets.SECURITY_AUDIT_SERVICE
    monkeypatch.setattr(provisioning, "TENANT_AUTHORITATIVE_MIGRATION_SET",
                        replace(binding, service=service, migrations=tuple(entries)))
    assert provisioning._authoritative_tenant_selection_activation_migration() is None


_ALTER_CATALOG = [
    ("missing", f"DROP FUNCTION {FUNCTION}", INVENTORY),
    ("schema", f"ALTER FUNCTION {FUNCTION} SET SCHEMA public", INVENTORY),
    ("signature", f"DROP FUNCTION {FUNCTION}; " + CREATE.replace("(text)", "(integer)"), INVENTORY),
    ("overload", CREATE.replace("(text)", "(integer)"), INVENTORY),
    ("second-schema", CREATE.replace("ofarm.", "public."), INVENTORY),
    ("procedure", f"DROP FUNCTION {FUNCTION}; CREATE PROCEDURE {FUNCTION} "
     "LANGUAGE sql SECURITY DEFINER AS 'SELECT NULL::text'", INVENTORY),
    ("invoker", f"ALTER FUNCTION {FUNCTION} SECURITY INVOKER", INVENTORY),
    ("owner", f"ALTER FUNCTION {FUNCTION} OWNER TO ofarm_binder", INVENTORY),
    ("missing-grant", REVOKE, ACL),
    ("other-grantee", f"{REVOKE}; GRANT EXECUTE ON FUNCTION {FUNCTION} TO ofarm_app", ACL),
    ("grant-option", f"{GRANT} WITH GRANT OPTION", ACL),
    ("grantor", f"{REVOKE}; GRANT EXECUTE ON FUNCTION {FUNCTION} TO ofarm_app WITH GRANT OPTION; "
     f"SET LOCAL ROLE ofarm_app; {GRANT}; RESET ROLE", ACL),
    ("default-public", f"DROP FUNCTION {FUNCTION}; "
     "ALTER DEFAULT PRIVILEGES FOR ROLE ofarm_owner GRANT EXECUTE ON FUNCTIONS TO PUBLIC; "
     f"SET LOCAL ROLE ofarm_owner; {CREATE}; RESET ROLE", ACL),
    *((role, f"GRANT EXECUTE ON FUNCTION {FUNCTION} TO {role}", ACL)
      for role in ("PUBLIC", LOGIN, "ofarm_app", "ofarm_worker", "ofarm_binder")),
    ("binder-grant", f"REVOKE EXECUTE ON FUNCTION ofarm.create_tenant_challenge() FROM {CONTROLLER}", FAMILY),
    ("draft-grant", f"REVOKE EXECUTE ON FUNCTION {DRAFT} FROM {CONTROLLER}",
     "tenant selection activation routine ACL differs"),
    ("extra-draft-grant", f"GRANT EXECUTE ON FUNCTION {DRAFT} TO ofarm_worker",
     "tenant selection activation routine ACL differs"),
    ("unrelated-family-grant", f"GRANT EXECUTE ON FUNCTION ofarm.verify_tenant_structure() TO {CONTROLLER}", FAMILY),
    ("membership", f"GRANT {CONTROLLER} TO {LOGIN} WITH SET TRUE",
     f"membership {CONTROLLER} -> {LOGIN} is missing or differs"),
    ("login-limit", f"ALTER ROLE {LOGIN} CONNECTION LIMIT 2", f"role {LOGIN} attributes differ"),
]


class TestSubmitRefusals:
    @pytest.mark.parametrize(("case", "alteration", "expected"), _ALTER_CATALOG,
                             ids=[case[0] for case in _ALTER_CATALOG])
    def test_catalog_on_both_postures(self, target, binding, release, case, alteration, expected):
        # Administrative fixture changes live only in this rolled-back test transaction.
        with psycopg.connect(target.target_admin_dsn, autocommit=True) as conn, (
            conn.transaction(force_rollback=True)
        ):
            conn.execute("SET LOCAL ROLE ofarm_owner")
            conn.execute(SOURCE)
            conn.execute("RESET ROLE")
            conn.execute(alteration)
            if case == "grantor":
                assert conn.execute("""
                    SELECT a.grantor::regrole::text FROM pg_catalog.pg_proc p,
                    LATERAL pg_catalog.aclexplode(p.proacl) a
                    WHERE p.oid = %s::regprocedure AND a.grantee = %s::regrole
                """, (FUNCTION, CONTROLLER)).fetchall() == [("ofarm_app",)]
            if case == "default-public":
                assert conn.execute("SELECT proacl IS NULL FROM pg_proc WHERE oid = %s::regprocedure",
                                    (FUNCTION,)).fetchone() == (True,)
            assert expected in provisioning._tenant_submit_post_source_locked_differences(conn, SPEC)
            runner._insert_ledger_row(conn, SPEC, release, release.migrations[-1], LABEL, uuid4())
            assert expected in provisioning.migration_locked_differences(conn, SPEC)

    def test_reauthentication_rolls_back_before_append(self, target, binding, release, monkeypatch):
        before = _observe(target)
        calls = []
        require = runner.require_authoritative_migration_set

        def check(candidate):
            require(candidate)
            calls.append(candidate)
            if len(calls) == 2:
                raise migration_sets.MigrationSetError("test release withdrawn after source")
            return candidate

        monkeypatch.setattr(runner, "require_authoritative_migration_set", check)
        monkeypatch.setattr(runner, "_tenant_submit_post_source_locked_differences",
                            lambda *_: pytest.fail("verification entered after failed authentication"))
        monkeypatch.setattr(runner, "_insert_ledger_row", lambda *_: pytest.fail("unexpected append"))
        with pytest.raises(runner.MigrationInputError, match="test release withdrawn"):
            _run(target, release)
        assert calls == [release, release]
        assert _observe(target) == before
        provisioning.verify_service_infrastructure(target.admin_dsn, SPEC)

    def test_post_source_drift_refuses_before_append(self, target, binding, release, monkeypatch):
        before = _observe(target)
        verify = runner._tenant_submit_post_source_locked_differences

        def observe_missing_grant(conn, spec):
            conn.execute(REVOKE)
            return verify(conn, spec)

        monkeypatch.setattr(runner, "_tenant_submit_post_source_locked_differences", observe_missing_grant)
        monkeypatch.setattr(runner, "_insert_ledger_row", lambda *_: pytest.fail("unexpected append"))
        with pytest.raises(runner.MigrationDirtyError, match=ACL):
            _run(target, release)
        assert _observe(target) == before
        provisioning.verify_service_infrastructure(target.admin_dsn, SPEC)

    @pytest.mark.parametrize("change", ["release", "execution", "post-append-grant"])
    def test_bad_append_rolls_back(self, target, binding, release, monkeypatch, change):
        before = _observe(target)
        append = runner._insert_ledger_row

        def substitute(conn, spec, candidate, migration, label, execution_id):
            append(conn, spec, candidate, migration,
                   "ofarm-tests/substitute" if change == "release" else label,
                   uuid4() if change == "execution" else execution_id)
            if change == "post-append-grant":
                conn.execute(REVOKE)

        monkeypatch.setattr(runner, "_insert_ledger_row", substitute)
        diagnostic = ACL if change == "post-append-grant" else "append identity differs"
        with pytest.raises(runner.MigrationDirtyError, match=diagnostic):
            _run(target, release)
        assert _observe(target) == before
        provisioning.verify_service_infrastructure(target.admin_dsn, SPEC)

    def test_unmodified_structural_verifier_refuses_inert_source(self, target, binding, release):
        before = _observe(target)
        with pytest.raises(runner.MigrationDirtyError, match="structural verifier"):
            _run(target, release)
        assert _observe(target) == before
        provisioning.verify_service_infrastructure(target.admin_dsn, SPEC)


@pytest.mark.parametrize("head", [12, 13])
def test_every_ledger_row_and_field_is_required(binding, head):
    # An unprotected fixture table in the disposable control database. The
    # real tenant ledger, its append-only guard and its grants are untouched.
    with psycopg.connect(_admin_dsn(), autocommit=True) as conn, conn.transaction(force_rollback=True):
        conn.execute("CREATE SCHEMA ofarm")
        conn.execute("""
            CREATE TABLE ofarm.schema_migration (
                version integer, filename text, source_sha256 text, source_byte_length bigint,
                applied_prefix_digest text, service_identity text, provisioning_spec_digest text
            )
        """)
        digest = SPEC.digest
        with conn.cursor() as cursor:
            cursor.executemany("INSERT INTO ofarm.schema_migration VALUES (%s,%s,%s,%s,%s,%s,%s)", [
                (r.version, r.filename, r.source_sha256, r.byte_length, r.applied_prefix_digest,
                 binding.service.identity, digest) for r in binding.migrations[:head]
            ])
        classify = provisioning._tenant_binding_admission_classification
        assert provisioning._submit_ledger_matches(conn, SPEC, head)
        classification, differences = classify(conn, SPEC)
        assert not differences
        assert classification.selection_acl_substate.name == ("STABLE_V8" if head == 12 else "STABLE_SUBMIT")
        changes = {
            "missing": f"DELETE FROM ofarm.schema_migration WHERE version = {head}",
            "gap": "DELETE FROM ofarm.schema_migration WHERE version = 4",
            "duplicate": "INSERT INTO ofarm.schema_migration SELECT * FROM ofarm.schema_migration WHERE version = 5",
            "gap-and-duplicate": "UPDATE ofarm.schema_migration SET version = 2 WHERE version = 3",
            "newer": f"UPDATE ofarm.schema_migration SET version = {head + 1} WHERE version = {head}",
            "earlier-row": "UPDATE ofarm.schema_migration SET source_sha256 = '' WHERE version = 1",
            "wrong-type": "ALTER TABLE ofarm.schema_migration ALTER COLUMN version TYPE bigint",
        }
        for column in ("filename", "source_sha256", "source_byte_length", "applied_prefix_digest",
                       "service_identity", "provisioning_spec_digest"):
            changes[column] = f"UPDATE ofarm.schema_migration SET {column} = NULL WHERE version = {head}"
        for case, change in changes.items():
            with conn.transaction(force_rollback=True):
                conn.execute(change)
                observed, _ = classify(conn, SPEC)
                if head == 13 or case == "wrong-type":
                    assert observed is None or observed.selection_acl_substate.name != "STABLE_SUBMIT", case
                if case == "wrong-type":
                    assert observed is None, case
                else:
                    assert not provisioning._submit_ledger_matches(conn, SPEC, head), case


def test_migration_heads_before_submit_refuse_an_early_name(monkeypatch):
    # Sample the genuine historical transactions, including the V8-only
    # window. All candidate Submit objects roll back to a savepoint.
    original_v8 = runner._locked_tenant_v8_post_source_boundary_differences
    heads = []
    v8_observations = []

    def check_early(conn, verify):
        assert verify(conn, SPEC) == []
        with conn.transaction(force_rollback=True):
            conn.execute(CREATE)
            conn.execute(f"REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC")
            assert INVENTORY in verify(conn, SPEC)
            conn.execute(GRANT)
            assert {INVENTORY, ACL, FAMILY} <= set(verify(conn, SPEC))

    def check_v8(conn, spec):
        check_early(conn, original_v8)
        v8_observations.append(8)
        return original_v8(conn, spec)

    with fresh_tenant_service(_admin_dsn()) as service:
        def check_stable(head):
            with psycopg.connect(service.migrator_dsn, autocommit=True) as observer:
                runner._begin_and_lock(observer, SPEC)
                try:
                    runner._set_owner_role(observer, SPEC)
                    check_early(observer, provisioning.migration_locked_differences)
                    heads.append(head)
                finally:
                    observer.rollback()

        monkeypatch.setattr(runner, "_locked_tenant_v8_post_source_boundary_differences", check_v8)
        monkeypatch.setattr(runner, "_tenant_submit_post_source_locked_differences",
                            lambda *_: pytest.fail("early Submit transition"))
        check_stable(0)
        _run_through_predecessor(service, check_stable)
        assert heads == list(range(13))
        assert v8_observations == [8]


def test_transaction_visibility_rollback_and_lost_acknowledgement(target, binding, release, monkeypatch):
    before = _observe(target)
    history, grants, inventory = before
    assert (len(history), len(grants), len(inventory)) == (12, 3, 1)
    submit_grant = ("ofarm", NAME, "text", "ofarm_owner", "EXECUTE", False)
    expected_grants = sorted([*grants, submit_grant])
    observe_transition = runner._tenant_submit_post_source_locked_differences
    transition_checks = []
    committed_shape_checks = []

    def after_source(conn, spec):
        inside_history, inside_grants, inside_inventory = _snapshot(conn)
        assert inside_history == history
        assert inside_grants == expected_grants
        assert [row for row in inside_inventory if row[1] != NAME] == inventory
        assert len(inside_inventory) == 2
        assert set(provisioning.migration_locked_differences(conn, spec)) == {INVENTORY, ACL, FAMILY}
        assert _observe(target) == before
        transition_checks.append(True)
        return observe_transition(conn, spec)

    def check_test_structure(conn, spec, candidate):
        # Only #430 can supply the production structural check for version 13.
        # Its genuine R12 check is separately exercised and refuses this fixture.
        assert candidate is release
        assert provisioning.migration_locked_differences(conn, spec) == []
        assert TRANSITION in observe_transition(conn, spec)
        inside_history, inside_grants, inside_inventory = _snapshot(conn)
        assert inside_history[:-1] == history
        assert inside_grants == expected_grants
        assert len(inside_inventory) == 2
        committed_shape_checks.append(True)

    monkeypatch.setattr(runner, "_tenant_submit_post_source_locked_differences", after_source)
    monkeypatch.setattr(runner, "_verify_final_service_structure", check_test_structure)
    with psycopg.connect(target.migrator_dsn, autocommit=True) as conn:
        runner._begin_and_lock(conn, SPEC)
        runner._set_owner_role(conn, SPEC)
        assert {INVENTORY, ACL} <= set(observe_transition(conn, SPEC))
        conn.rollback()

    def disconnect_before_commit(conn, migration, execution_id):
        conn.close()
        raise runner.MigrationExecutionError(migration.version, migration.filename, "test before commit")

    with monkeypatch.context() as failure:
        failure.setattr(runner, "_commit", disconnect_before_commit)
        with pytest.raises(runner.MigrationExecutionError, match="test before commit"):
            _run(target, release)
    assert _observe(target) == before
    provisioning.verify_service_infrastructure(target.admin_dsn, SPEC)

    commit = runner._commit
    original_id = uuid4()

    def lose_ack(conn, migration, execution_id):
        commit(conn, migration, execution_id)
        raise runner.MigrationOutcomeUnknown(migration.version, migration.filename, execution_id)

    with monkeypatch.context() as failure:
        failure.setattr(runner, "_commit", lose_ack)
        with pytest.raises(runner.MigrationOutcomeUnknown):
            _run(target, release, original_id)
    after = _observe(target)
    assert after[0][:-1] == history and after[1] == expected_grants
    assert len(after[0]) == 13 and len(after[2]) == 2
    provisioning.verify_service_infrastructure(target.admin_dsn, SPEC)
    retry = _run(target, release)
    assert retry.verified_noop and retry.applied_versions == ()
    assert retry.previous_version == retry.final_version == 13
    assert retry.execution_id != retry.observed_head_execution_id == original_id
    assert _observe(target) == after
    assert len(transition_checks) == 2 and len(committed_shape_checks) == 3

    with psycopg.connect(target.target_admin_dsn) as admin:
        admin.execute(REVOKE)
    with pytest.raises(provisioning.ProvisioningDriftError, match=ACL):
        provisioning.verify_service_infrastructure(target.admin_dsn, SPEC)
    with pytest.raises(runner.MigrationTargetError, match=ACL):
        _run(target, release)
    with psycopg.connect(target.target_admin_dsn) as admin:
        admin.execute(GRANT)
    assert _observe(target) == after
    provisioning.verify_service_infrastructure(target.admin_dsn, SPEC)
