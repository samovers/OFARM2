"""Cheap refusal, report-integrity and disposal controls for tenant fixtures."""

from __future__ import annotations

from dataclasses import fields, replace
from importlib import import_module
from types import SimpleNamespace
from uuid import UUID

import psycopg
import pytest

from deployment.postgresql.migration_runner import MigrationRunReport
from kernel.tests import postgresql_tenant_support as support
from kernel.tests import test_postgresql_tenant_migration as staged

ADMIN_DSN = (
    "host=localhost port=64321 dbname=postgres user=fixture_admin sslmode=require"
)


@pytest.fixture
def service(monkeypatch):
    """Replace only database effects; keep real routes, source loading and reports."""

    state = SimpleNamespace(events=[], calls=[], version=0, head=None, owned=False)
    monkeypatch.setenv(support.ADMIN_ENV, ADMIN_DSN)

    def clean(admin_dsn, spec):
        state.events.append(("clean", admin_dsn))
        assert spec is support.TENANT_PROVISIONING_SPEC

    def provision(admin_dsn, spec, *, login_passwords):
        state.events.append(("provision", admin_dsn))
        state.owned = True
        assert set(login_passwords) == set(spec.required_password_role_names)

    def destroy(admin_dsn, spec):
        state.events.append(("destroy", admin_dsn))
        state.owned = False
        assert spec is support.TENANT_PROVISIONING_SPEC

    def migrate(**kwargs):
        state.calls.append(kwargs)
        final = kwargs["migration_set"].migrations[-1].version
        applied = tuple(range(state.version + 1, final + 1))
        if applied:
            state.head = kwargs["execution_id"]
        report = MigrationRunReport(
            service_identity=kwargs["migration_set"].service.identity,
            provisioning_spec_digest=kwargs["spec"].digest,
            migration_set_digest=kwargs["migration_set"].digest,
            database_name=kwargs["spec"].database_name,
            system_identifier="fixture-control",
            server_version_num=170010,
            previous_version=state.version,
            final_version=final,
            applied_versions=applied,
            execution_id=kwargs["execution_id"],
            observed_head_execution_id=state.head,
        )
        state.version = final
        state.events.append(("migrate", applied))
        return report

    monkeypatch.setattr(support, "_assert_clean_service", clean)
    monkeypatch.setattr(support, "provision_service", provision)
    monkeypatch.setattr(support, "_destroy_test_service", destroy)
    monkeypatch.setattr(support, "migrate_service", migrate)
    state.migrate = migrate
    return state


def test_runtime_uses_full_source_public_migration_and_distinct_verified_noop(service):
    fixture = support.tenant_target.__wrapped__()
    target = next(fixture)
    try:
        assert tuple(field.name for field in fields(target)) == (
            "admin_dsn",
            "target_admin_dsn",
            "migrator_dsn",
            "passwords",
            "migration_set",
        )
        assert len(service.calls) == 2
        first, noop = service.calls
        assert first["migration_set"] is noop["migration_set"] is target.migration_set
        assert tuple(item.version for item in target.migration_set.migrations) == tuple(
            range(1, 12)
        )
        assert first["execution_id"] != noop["execution_id"]
        assert {
            key: value for key, value in first.items() if key != "execution_id"
        } == {key: value for key, value in noop.items() if key != "execution_id"}
        route = psycopg.conninfo.conninfo_to_dict(target.role_dsn("ofarm_app"))
        assert route == {
            "host": "localhost",
            "port": "64321",
            "dbname": "ofarm_tenant",
            "user": "ofarm_app",
            "password": target.passwords["ofarm_app"],
            "sslmode": "require",
        }
        assert service.events == [
            ("clean", ADMIN_DSN),
            ("provision", ADMIN_DSN),
            ("migrate", tuple(range(1, 12))),
            ("migrate", ()),
        ]
    finally:
        fixture.close()
    assert service.events[-1] == ("destroy", ADMIN_DSN)


def test_dirty_service_is_refused_before_provisioning_or_cleanup(service, monkeypatch):
    refusal = RuntimeError("unowned dirty service")

    def refuse(*args):
        raise refusal

    monkeypatch.setattr(support, "_assert_clean_service", refuse)
    with pytest.raises(RuntimeError) as observed:
        next(support.tenant_target.__wrapped__())
    assert observed.value is refusal
    assert service.events == []
    assert service.calls == []


@pytest.mark.parametrize("stage", ["provision", "target", "full-migration", "noop"])
def test_owned_setup_failure_propagates_and_disposes(service, monkeypatch, stage):
    failure = RuntimeError(stage)

    def fail(*args, **kwargs):
        if stage == "provision":
            state_marker = ("partial-provision", ADMIN_DSN)
            service.events.append(state_marker)
            service.owned = True
        raise failure

    if stage == "provision":
        monkeypatch.setattr(support, "provision_service", fail)
    elif stage == "target":
        monkeypatch.setattr(support, "TenantTarget", fail)
    else:

        def migrate(**kwargs):
            if stage == "full-migration" or service.calls:
                raise failure
            return service.migrate(**kwargs)

        monkeypatch.setattr(support, "migrate_service", migrate)
    with pytest.raises(RuntimeError) as observed:
        next(support.tenant_target.__wrapped__())
    assert observed.value is failure
    assert service.events[0] == ("clean", ADMIN_DSN)
    assert service.events[-1] == ("destroy", ADMIN_DSN)
    assert sum(event[0] == "destroy" for event in service.events) == 1
    assert not service.owned


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_body_failure_stays_visible_and_owned_cleanup_follows_dependents(
    service,
    monkeypatch,
    cleanup_fails,
):
    body_failure = RuntimeError("dependent body failed")
    cleanup_failure = RuntimeError("owned cleanup failed")

    if cleanup_fails:

        def destroy(*args):
            service.events.append(("destroy", ADMIN_DSN))
            raise cleanup_failure

        monkeypatch.setattr(support, "_destroy_test_service", destroy)
    fixture = support.tenant_target.__wrapped__()
    next(fixture)
    service.events.append(("dependent-teardown", ADMIN_DSN))
    with pytest.raises(RuntimeError) as observed:
        fixture.throw(body_failure)
    assert observed.value is (cleanup_failure if cleanup_fails else body_failure)
    if cleanup_fails:
        assert observed.value.__context__ is body_failure
    assert service.events[-2:] == [
        ("dependent-teardown", ADMIN_DSN),
        ("destroy", ADMIN_DSN),
    ]


@pytest.mark.parametrize(
    "changes",
    [
        {"previous_version": 7},
        {"applied_versions": tuple(range(1, 8)), "final_version": 7},
        {"applied_versions": tuple(range(1, 8))},
        {"final_version": 7},
        {"observed_head_execution_id": UUID(int=0)},
    ],
    ids=["not-fresh", "v7-only", "missing-tail", "wrong-final", "wrong-head"],
)
def test_partial_or_inconsistent_fresh_report_refuses_before_yield(
    service, monkeypatch, changes
):
    def migrate(**kwargs):
        return replace(service.migrate(**kwargs), **changes)

    monkeypatch.setattr(support, "migrate_service", migrate)
    with pytest.raises(AssertionError):
        next(support.tenant_target.__wrapped__())
    assert len(service.calls) == 1
    assert service.events[-1] == ("destroy", ADMIN_DSN)


@pytest.mark.parametrize(
    "defect",
    ["previous", "final", "applied", "head", "execution"],
)
def test_false_noop_or_wrong_lineage_refuses_before_yield(service, monkeypatch, defect):
    def migrate(**kwargs):
        report = service.migrate(**kwargs)
        if len(service.calls) == 1:
            return report
        changes = {
            "previous": {"previous_version": 7},
            "final": {"final_version": 7},
            "applied": {"applied_versions": (11,)},
            "head": {"observed_head_execution_id": UUID(int=0)},
            "execution": {"execution_id": service.calls[0]["execution_id"]},
        }
        return replace(report, **changes[defect])

    monkeypatch.setattr(support, "migrate_service", migrate)
    with pytest.raises(AssertionError):
        next(support.tenant_target.__wrapped__())
    assert len(service.calls) == 2
    assert service.events[-1] == ("destroy", ADMIN_DSN)


def test_staged_manual_route_keeps_patched_admin_and_every_schedule_step(
    service, monkeypatch
):
    explicit_route = ADMIN_DSN.replace("64321", "64322")
    monkeypatch.setattr(staged, "_admin_dsn", lambda: explicit_route)
    monkeypatch.setattr(staged, "_migrate_service_for_testing", service.migrate)
    monkeypatch.setattr(staged, "migrate_service", service.migrate)
    probes = {
        "_assert_v4_guards_refuse_before_catalog_change": "v4_guard_evidence",
        "_assert_v4_admission_capsules_are_inert": "v4_admission_evidence",
        "_assert_v5_context_admission_is_inert": "v5_admission_evidence",
        "_assert_v6_write_lock_admission_is_inert": "v6_admission_evidence",
    }
    for name, field in probes.items():

        def probe(*, _field=field, **kwargs):
            service.events.append(("probe", _field))
            return (_field,)

        monkeypatch.setattr(staged, name, probe)
    fixture = staged.tenant_target.__wrapped__()
    target = next(fixture)
    try:
        assert isinstance(target, support.TenantTarget)
        assert target.admin_dsn == explicit_route
        for field in probes.values():
            assert getattr(target, field) == (field,)
        reports = [
            getattr(target, name)
            for name in (
                "v3_report",
                "v4_report",
                "v5_report",
                "v6_report",
                "v7_report",
                "first_report",
                "noop_report",
            )
        ]
        assert [report.applied_versions for report in reports] == [
            (1, 2, 3),
            (4,),
            (5,),
            (6,),
            (7,),
            (8, 9, 10, 11),
            (),
        ]
        assert reports[-1].observed_head_execution_id == reports[-2].execution_id
        assert all(call["admin_dsn"] == explicit_route for call in service.calls)
        assert [
            event for event in service.events if event[0] in {"migrate", "probe"}
        ] == [
            ("migrate", (1, 2, 3)),
            ("probe", "v4_guard_evidence"),
            ("migrate", (4,)),
            ("probe", "v4_admission_evidence"),
            ("migrate", (5,)),
            ("probe", "v5_admission_evidence"),
            ("migrate", (6,)),
            ("probe", "v6_admission_evidence"),
            ("migrate", (7,)),
            ("migrate", (8, 9, 10, 11)),
            ("migrate", ()),
        ]
    finally:
        fixture.close()
    assert service.events[-1] == ("destroy", explicit_route)


def test_runtime_registrations_share_operational_target_and_keep_staged_owner():
    consumers = (
        "authentication_read_api",
        "physical_outcome_fixture",
        "physical_outcome_health",
        "physical_outcome_runtime",
        "physical_outcome_transport",
        "postgresql_tenant_capability_retirement",
        "postgresql_tenant_capability_signing",
        "postgresql_tenant_challenge_observation",
        "postgresql_tenant_command_runtime_bundle_selector",
        "postgresql_tenant_uow",
        "postgresql_tenant_uow_concurrency",
        "security_audit_runtime_cross_slice",
        "signing_observation_acquisition",
        "signing_observation_database",
    )
    for name in consumers:
        module = import_module(f"kernel.tests.test_{name}")
        assert module.tenant_target is support.tenant_target
        if hasattr(module, "TenantTarget"):
            assert module.TenantTarget is support.TenantTarget
    assert staged.tenant_target is not support.tenant_target
    assert support.tenant_target._fixture_function_marker.scope == "module"
    assert staged.tenant_target._fixture_function_marker.scope == "module"
