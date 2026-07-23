"""test profile runtime routes."""
# ruff: noqa: F403, F405

from kernel.tests._profile_runtime_test_support import *


def test_route_backed_gate_pipeline_refuses_tenant_mismatch_before_writes(
        fresh_env):
    store, _, _ = fresh_env
    receipt_tables = (
        "kernel_record",
        "kernel_edge",
        "kernel_gate_log",
        "kernel_idempotency",
        "derived_materialization",
        "derived_dependency_index",
        "reference_snapshot_data",
        "runtime_trace",
        "export_artifact",
    )

    def receipt_row_counts():
        counts = {}
        with store.conn.cursor() as cur:
            for table in receipt_tables:
                cur.execute(
                    psycopg.sql.SQL("SELECT count(*) AS row_count FROM {}")
                    .format(psycopg.sql.Identifier(table))
                )
                counts[table] = cur.fetchone()["row_count"]
        return counts

    tenant_b = "tenant:route.other"
    route_b = _si_route(tenant_ref=tenant_b)
    before = receipt_row_counts()

    with pytest.raises(ProfileRuntimeError, match="tenant"):
        _route_pipeline(store, routes=[route_b], tenant=tenant_b)

    assert receipt_row_counts() == before


def test_route_backed_gate_pipeline_accepts_clean_si_operation(fresh_env):
    store, default_pipeline, _ = fresh_env
    routed_pipeline = _route_pipeline(store)

    default = default_pipeline.commit(demo.spray_submission(
        f"mp7-default-clean:{_uid()}",
        erp_id=f"erp:mp7.default.clean.{_uid()}",
        confirm=True,
    ))
    routed = routed_pipeline.commit(demo.spray_submission(
        f"mp7-routed-clean:{_uid()}",
        erp_id=f"erp:mp7.routed.clean.{_uid()}",
        confirm=True,
    ))

    assert default["decisionOutcome"] == routed["decisionOutcome"] == \
        "PROMOTE_ACCEPTED"
    assert default.get("problems", []) == routed.get("problems", []) == []
    trace = _trace_payload(store, routed)
    assert [entry["gate"] for entry in trace["gateSequence"]][:3] == [
        "INGRESS_NORMALIZATION",
        "PACK_PROFILE_APPLICABILITY",
        "AUTHORITY",
    ]
    assert trace["gateSequence"][1]["outcome"] == "PROFILE_ROUTE_PASS"


@pytest.mark.parametrize("routes,match", [
    ([], "no active profile route"),
    ([_si_route(), _si_route()], "multiple active overlapping"),
    (
        [_si_route(
            descriptor_identity="profile_si_ffs/runtime_profile_descriptor.json#bad",
        )],
        "descriptor identity",
    ),
])
def test_route_backed_gate_pipeline_refuses_route_resolution_failures(
        fresh_env, routes, match):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store, routes=routes)

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-fail:{_uid()}",
        erp_id=f"erp:mp7.route.fail.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert match in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_missing_farm_context(fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-no-farm:{_uid()}",
        erp_id=f"erp:mp7.route.no-farm.{_uid()}",
        confirm=True,
    )
    sub["targetScopes"] = [{"scopeType": "FIELD", "scopeRef": "field:demo.no-farm"}]

    result = pipeline.commit(sub)

    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_farm_ref_scope_mismatch(fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-farm-mismatch:{_uid()}",
        erp_id=f"erp:mp7.route.farm-mismatch.{_uid()}",
        confirm=True,
    )
    sub["farmRef"] = "farm:demo.other"
    sub["targetScopes"] = [{"scopeType": "FARM", "scopeRef": demo.FARM}]

    result = pipeline.commit(sub)

    assert "must match the top-level submission farmRef" in \
        result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


@pytest.mark.parametrize("scopes", [
    [
        {"scopeType": "FARM", "scopeRef": demo.FARM},
        {"scopeType": "FARM", "scopeRef": demo.FARM},
    ],
    [
        {"scopeType": "FARM", "scopeRef": demo.FARM},
        {"scopeType": "FARM", "scopeRef": "farm:demo.other"},
    ],
])
def test_route_backed_gate_pipeline_refuses_multiple_farm_scope_entries(
        fresh_env, scopes):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-multiple-farm:{_uid()}",
        erp_id=f"erp:mp7.route.multiple-farm.{_uid()}",
        confirm=True,
    )
    sub["targetScopes"] = scopes

    result = pipeline.commit(sub)

    assert "exactly one FARM anchor scope entry" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


@pytest.mark.parametrize("malformed_farm_scope", [
    {"scopeType": "FARM"},
    {"scopeType": "FARM", "scopeRef": ""},
])
def test_route_backed_gate_pipeline_counts_malformed_farm_scope_entries(
        fresh_env, malformed_farm_scope):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-malformed-farm:{_uid()}",
        erp_id=f"erp:mp7.route.malformed-farm.{_uid()}",
        confirm=True,
    )

    with store.tx() as cur:
        ctx = pipeline._new_context(cur, sub)
        ctx.envelope = {
            "anchorScopes": [
                {"scopeType": "FARM", "scopeRef": demo.FARM},
                malformed_farm_scope,
            ],
        }
        outcome = pipeline._resolve_profile_route(ctx)

    assert outcome.final_outcome == "RETAIN_DRAFT"
    assert outcome.problems[0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    assert "exactly one FARM anchor scope entry" in outcome.problems[0]["detail"]
    assert ctx.gate_sequence[-1]["gate"] == "PACK_PROFILE_APPLICABILITY"
    assert ctx.gate_sequence[-1]["outcome"] == "PROFILE_ROUTE_REFUSE"


def test_route_backed_gate_pipeline_refuses_same_context_time_bounded_route(
        fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(
        store,
        routes=[
            _route_interval("06"),
            _si_route(route_id=f"profileroute:test.si.timeless.{_uid()}"),
        ],
    )

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-time-bound:{_uid()}",
        erp_id=f"erp:mp7.route.time-bound.{_uid()}",
        confirm=True,
    ))

    assert "multiple active overlapping" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_accepts_time_bounded_operation_route(
        fresh_env):
    store, _, _ = fresh_env
    route = _route_interval("06")
    pipeline = _route_pipeline(store, routes=[route])

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-june:{_uid()}",
        erp_id=f"erp:mp7.route.june.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    trace = _trace_payload(store, result)
    assert trace["gateSequence"][1]["outcome"] == "PROFILE_ROUTE_PASS"
    assert route.route_id in trace["gateSequence"][1]["relatedArtifactRefs"]


def test_route_backed_gate_pipeline_refuses_operation_outside_route_interval(
        fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store, routes=[_route_interval("05")])

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-outside:{_uid()}",
        erp_id=f"erp:mp7.route.outside.{_uid()}",
        confirm=True,
    ))

    assert "no active profile route" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_missing_event_time_no_captured_fallback(
        fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])
    sub = demo.spray_submission(
        f"mp7-route-no-event:{_uid()}",
        erp_id=f"erp:mp7.route.no-event.{_uid()}",
        confirm=True,
    )
    del sub["eventTime"]
    sub["capturedAt"] = "2026-06-10T07:45:00Z"

    result = pipeline.commit(sub)

    assert "eventTime" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_unparseable_event_time_no_fallback(
        fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])
    sub = demo.spray_submission(
        f"mp7-route-bad-event:{_uid()}",
        erp_id=f"erp:mp7.route.bad-event.{_uid()}",
        confirm=True,
    )
    sub["eventTime"] = "not-a-time"

    result = pipeline.commit(sub)

    assert "eventTime is unparseable" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_operation_decision_time_fallback(
        fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])
    sub = demo.spray_submission(
        f"mp7-route-no-decision-fallback:{_uid()}",
        erp_id=f"erp:mp7.route.no-decision-fallback.{_uid()}",
        confirm=True,
    )
    del sub["eventTime"]
    sub["decisionTime"] = "2026-06-10T10:00:00Z"

    result = pipeline.commit(sub)

    assert "eventTime" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_refuses_unsupported_route_time_source(
        fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])

    result = pipeline.commit(_note_submission(
        f"mp7-route-note-unsupported:{_uid()}"))

    assert "unsupported" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_operation_event_time_selects_half_open_route(
        fresh_env):
    store, _, _ = fresh_env
    may = _route_interval("05", route_id=f"profileroute:test.si.may.{_uid()}")
    june = _route_interval("06", route_id=f"profileroute:test.si.june.{_uid()}")
    pipeline = _route_pipeline(store, routes=[may, june])

    may_result = pipeline.commit(demo.spray_submission(
        f"mp7-route-may:{_uid()}",
        erp_id=f"erp:mp7.route.may.{_uid()}",
        confirm=True,
        event_start="2026-05-15T07:30:00Z",
        event_end="2026-05-15T08:15:00Z",
    ))
    june_result = pipeline.commit(demo.spray_submission(
        f"mp7-route-june-boundary:{_uid()}",
        erp_id=f"erp:mp7.route.june-boundary.{_uid()}",
        confirm=True,
        event_start="2026-06-01T00:00:00Z",
        event_end="2026-06-01T01:00:00Z",
    ))

    assert may.route_id in _trace_payload(store, may_result)["gateSequence"][1][
        "relatedArtifactRefs"]
    assert june.route_id in _trace_payload(store, june_result)["gateSequence"][1][
        "relatedArtifactRefs"]


def test_route_backed_gate_pipeline_ignores_other_farm_time_bounded_route(
        fresh_env):
    store, _, _ = fresh_env
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pipeline = _route_pipeline(
        store,
        routes=[
            _si_route(farm_ref="farm:demo.other", effective_from=t0),
            _si_route(route_id=f"profileroute:test.si.timeless.{_uid()}"),
        ],
    )

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-other-farm-time:{_uid()}",
        erp_id=f"erp:mp7.route.other-farm-time.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_route_backed_gate_pipeline_ignores_other_tenant_time_bounded_route(
        fresh_env):
    store, _, _ = fresh_env
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pipeline = _route_pipeline(
        store,
        routes=[
            _si_route(tenant_ref="tenant:demo.other", effective_from=t0),
            _si_route(route_id=f"profileroute:test.si.timeless.{_uid()}"),
        ],
    )

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-other-tenant-time:{_uid()}",
        erp_id=f"erp:mp7.route.other-tenant-time.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_route_backed_gate_pipeline_ignores_inactive_time_bounded_route(
        fresh_env):
    store, _, _ = fresh_env
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pipeline = _route_pipeline(
        store,
        routes=[
            _si_route(status="DRAFT", effective_from=t0),
            _si_route(route_id=f"profileroute:test.si.timeless.{_uid()}"),
        ],
    )

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-inactive-time:{_uid()}",
        erp_id=f"erp:mp7.route.inactive-time.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_route_backed_gate_pipeline_governance_uses_decision_time(fresh_env):
    store, default_pipeline, _ = fresh_env
    queued = default_pipeline.commit(demo.spray_submission(
        f"mp7-governance-queued:{_uid()}",
        erp_id=f"erp:mp7.governance.queued.{_uid()}",
        confirm=False,
    ))
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])

    result = pipeline.commit(_governance_submission(
        f"mp7-governance-accept:{_uid()}",
        decision_time="2026-06-10T10:00:00Z",
        event_time="2026-05-10T10:00:00Z",
        target=queued["emittedAssertionRecordRefs"][0],
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"
    trace = _trace_payload(store, result)
    assert trace["gateSequence"][1]["outcome"] == "PROFILE_ROUTE_PASS"


@pytest.mark.parametrize("decision_time,match", [
    (None, "decisionTime"),
    ("not-a-time", "decisionTime"),
])
def test_route_backed_gate_pipeline_governance_requires_decision_time(
        fresh_env, decision_time, match):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])

    result = pipeline.commit(_governance_submission(
        f"mp7-governance-no-decision:{_uid()}",
        decision_time=decision_time,
        event_time="2026-06-10T10:00:00Z",
    ))

    assert match in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


def test_route_backed_gate_pipeline_governance_does_not_use_event_time_fallback(
        fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store, routes=[_route_interval("06")])

    result = pipeline.commit(_governance_submission(
        f"mp7-governance-event-fallback:{_uid()}",
        decision_time="2026-05-10T10:00:00Z",
        event_time="2026-06-10T10:00:00Z",
    ))

    assert "no active profile route" in result["problems"][0]["detail"]
    _assert_profile_route_refusal(store, result)


@pytest.mark.parametrize("package_name", [
    "profile_nl_go_glmc7_2026",
    "profile_rs_organic_crop",
])
def test_route_backed_gate_pipeline_refuses_design_only_route_target(
        fresh_env, package_name):
    if not (config.PACKAGE_ROOT / package_name).exists():
        pytest.skip(f"{package_name} is not present in this checkout")
    store, _, _ = fresh_env
    pipeline = _route_pipeline(
        store,
        routes=[_si_route(profile_package_name=package_name)],
        registry=_route_registry(enabled=("profile_si_ffs", package_name)),
        selected=("profile_si_ffs", package_name),
    )

    result = pipeline.commit(demo.spray_submission(
        f"mp7-route-design-only:{_uid()}",
        erp_id=f"erp:mp7.route.design-only.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == "PROFILE_NOT_ACTIVE"
    trace = _trace_payload(store, result)
    assert trace["gateSequence"][-1]["gate"] == "PACK_PROFILE_APPLICABILITY"
    assert trace["gateSequence"][-1]["outcome"] == "PROFILE_ROUTE_REFUSE"


def test_route_backed_gate_pipeline_uses_descriptor_backed_policy_paths(
        fresh_env, monkeypatch):
    store, _, _ = fresh_env

    def fail_config_policy(*_args, **_kwargs):
        raise AssertionError("config-backed policy path was called")

    monkeypatch.setattr(profile_policy, "validation_policy", fail_config_policy)
    monkeypatch.setattr(profile_policy, "load_evidence_review_policy",
                        fail_config_policy)
    monkeypatch.setattr(profile_policy, "operation_floor_with_display",
                        fail_config_policy)
    monkeypatch.setattr(profile_policy, "operation_floor_display",
                        fail_config_policy)
    monkeypatch.setattr(profile_policy, "advisory_rules", fail_config_policy)
    monkeypatch.setattr(sufficiency, "build_floor_case", fail_config_policy)
    monkeypatch.setattr(sufficiency, "operation_advisories", fail_config_policy)

    result = _route_pipeline(store).commit(demo.spray_submission(
        f"mp7-route-provider:{_uid()}",
        erp_id=f"erp:mp7.route.provider.{_uid()}",
        confirm=True,
    ))

    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED"


def test_route_backed_handoff_binds_materializer_to_resolved_descriptor(fresh_env):
    store, _, _ = fresh_env
    pipeline = _route_pipeline(store)
    sub = demo.spray_submission(
        f"mp7-route-bind:{_uid()}",
        erp_id=f"erp:mp7.route.bind.{_uid()}",
        confirm=True,
    )

    with store.tx() as cur:
        ctx = pipeline._new_context(cur, sub)
        ingress = IngressNormalizer().run(ctx)
        assert not hasattr(ingress, "result")
        assert pipeline._resolve_profile_route(ctx) is None

    assert ctx.profile_route_resolution.descriptor == config.ACTIVE_PROFILE
    services = ctx.runtime_services
    assert services.descriptor == ctx.profile_route_resolution.descriptor
    assert services.materializer.active_profile == ctx.profile_route_resolution.descriptor
    assert services.materializer.context.active_profile == \
        ctx.profile_route_resolution.descriptor
    assert services.context_assembler.active_profile == \
        ctx.profile_route_resolution.descriptor
    assert services.policy_provider.descriptor == \
        ctx.profile_route_resolution.descriptor
    assert services.reference_bindings.regsr_shipped_snapshot_ref == \
        context.SI_REFERENCE_BINDINGS.regsr_shipped_snapshot_ref


def test_output_generator_explicit_descriptor_matches_default_profile_refs(fresh_env):
    store, _, outputs = fresh_env
    explicit = OutputGenerator(store, active_descriptor=config.ACTIVE_PROFILE)

    default_view = outputs.passport_view(demo.FARM, demo.FARMER)
    explicit_view = explicit.passport_view(demo.FARM, demo.FARMER)

    assert default_view["refused"] is False
    assert explicit_view["refused"] is False
    assert default_view["metadata"]["profileRefs"] == \
        explicit_view["metadata"]["profileRefs"] == [config.ACTIVE_PROFILE.profile_ref]
    assert explicit.materializer.active_profile == config.ACTIVE_PROFILE
