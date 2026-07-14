"""Stage-contract tests (issue #3): the policy tables, the freshness
semantics, and a sample of validator contracts are tested at their OWN
boundaries — typed input, typed result. Coverage is honest: five of the
validators are exercised here; the rest are pinned end to end by the
conformance suite (test_conformance.py), which remains the only arbiter
of law. These tests exist so a future edit that bends a table or a tested
validator's disposition fails HERE, before it can look law-consistent
end to end.
"""
from __future__ import annotations

import re
import uuid
from contextlib import contextmanager
from types import MappingProxyType, SimpleNamespace

import pytest

from kernel import config, policy, sufficiency
from kernel.stages import GateContext, GateRefusal
from kernel.validators import (CarrierSchemaValidator, PromotionTargetValidator,
                               ScopeContainmentValidator, SupersessionValidator,
                               TemporalConformanceValidator)
from kernel import demo


# =========================================================================
# policy tables: internally consistent and bound to the ACCEPTED law
# =========================================================================

def test_policy_action_classes_are_accepted_matrix_vocabulary():
    """Every action class the runtime evaluates must appear verbatim in the
    accepted Authority Action Matrix — parsed from the law file itself, so
    a parallel runtime dialect can never silently reappear."""
    matrix_md = (config.PACKAGE_ROOT / "reference" / "rfcs"
                 / "OFARM_Authority_Action_Matrix_v0_1.md").read_text()
    accepted = set(re.findall(r"^\| ([A-Z][A-Z_]+) \|", matrix_md, re.MULTILINE))
    assert accepted, "could not parse the Action Matrix vocabulary"
    runtime_classes = (set(policy.COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS.values())
                       | policy.NON_COMMIT_ACTION_CLASSES)
    drift = runtime_classes - accepted
    assert not drift, f"runtime action classes outside the accepted matrix: {drift}"


def test_policy_tables_are_closed_and_consistent():
    # every commit class has a family and an authority action
    assert set(policy.COMMIT_CLASS_TO_FAMILY) == \
        set(policy.COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS)
    # every promotion target has a consequence type
    for target in policy.COMMIT_CLASS_TO_PROMOTION_TARGET.values():
        assert target in policy.PROMOTION_TARGET_TO_CONSEQUENCE_TYPE
    # promoting classes are a subset of commit classes
    assert set(policy.COMMIT_CLASS_TO_PROMOTION_TARGET) <= \
        set(policy.COMMIT_CLASS_TO_FAMILY)
    # the acceptance table agrees with the promotion tables, assertion-type-wise
    for assertion_type, (target, ctype) in policy.ACCEPTANCE_BY_ASSERTION_TYPE.items():
        assert policy.PROMOTION_TARGET_TO_CONSEQUENCE_TYPE[target] == ctype
        commit_class = next(
            (c for c, t in policy.COMMIT_CLASS_TO_ASSERTION_TYPE.items()
             if t == assertion_type), None)
        assert commit_class is not None, \
            f"acceptance table names unmapped assertion type {assertion_type}"
        assert policy.COMMIT_CLASS_TO_PROMOTION_TARGET[commit_class] == target
    # D8: self-acceptance scope is exactly routine operation claims
    assert policy.SELF_ACCEPTABLE_ASSERTION_TYPES == {"OPERATION_CLAIM_ASSERTION"}


def test_decision_policy_tables_are_deeply_immutable():
    tables = (
        policy.COMMIT_CLASS_TO_FAMILY,
        policy.COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS,
        policy.COMMIT_CLASS_TO_ASSERTION_TYPE,
        policy.COMMIT_CLASS_TO_PROMOTION_TARGET,
        policy.PROMOTION_TARGET_TO_CONSEQUENCE_TYPE,
        policy.ACCEPTANCE_BY_ASSERTION_TYPE,
        policy.REVIEW_ACTION_AUTHORITY,
        policy.STRUCTURE_PAYLOAD_IDENTITY_TYPE,
        policy.STRUCTURE_PAYLOAD_REF_FIELDS,
        policy.STRUCTURE_REF_CATEGORY_KIND,
        policy.NON_PROMOTING_RETAIN_REASONS,
        policy.ROUTE_REASON_TO_INSUFFICIENCY,
        policy.USE_CLASS_TO_CANONICAL,
        policy.FRESHNESS_USE_POLICY,
    )

    def require_frozen(value):
        assert type(value) not in {dict, list, set}
        if type(value) is MappingProxyType:
            for nested in value.values():
                require_frozen(nested)
        elif type(value) in {tuple, frozenset}:
            for nested in value:
                require_frozen(nested)

    for table in tables:
        assert type(table) is MappingProxyType
        require_frozen(table)
        with pytest.raises(TypeError):
            table["__mutation_probe__"] = "forbidden"


def test_freshness_use_policy_truth_table():
    """The requirement-mode truth table. ALLOW_STALE_EXPLORATORY and
    NO_CURRENT_STATE_DEPENDENCY intentionally share a satisfaction set:
    the latter is kernel-narrowed to stale-allowed because the candidate
    contracts leave it undescribed (defined nowhere in reference/ — see
    profile_si_ffs/UNSUPPORTED_SURFACES.md and ERRATA E-003). INVALID
    never satisfies anything; high consequence escalates to REQUIRE_FRESH."""
    cases = {
        # (required, high_consequence, state) -> satisfied
        ("REQUIRE_FRESH", False, "FRESH"): True,
        ("REQUIRE_FRESH", False, "STALE"): False,
        ("REQUIRE_FRESH", False, "INVALID"): False,
        ("ALLOW_STALE_EXPLORATORY", False, "FRESH"): True,
        ("ALLOW_STALE_EXPLORATORY", False, "STALE"): True,
        ("ALLOW_STALE_EXPLORATORY", False, "INVALID"): False,
        ("ALLOW_STALE_EXPLORATORY", True, "STALE"): False,   # escalated
        ("NO_CURRENT_STATE_DEPENDENCY", False, "STALE"): True,
        ("NO_CURRENT_STATE_DEPENDENCY", False, "INVALID"): False,
        ("NO_CURRENT_STATE_DEPENDENCY", True, "STALE"): False,  # escalated
    }
    for (required, high, state), expected in cases.items():
        assert policy.freshness_satisfied(required, high, state) is expected, \
            (required, high, state)
    # honest reuse wording
    assert policy.reuse_reason_summary("FRESH", "REQUIRE_FRESH", False) == \
        "reused FRESH materialization"
    stale_text = policy.reuse_reason_summary("STALE", "ALLOW_STALE_EXPLORATORY", False)
    assert "STALE" in stale_text and "high-consequence use barred" in stale_text


# =========================================================================
# validator contracts: typed input -> typed result, dispositions pinned
# =========================================================================

class _Rollback(Exception):
    """Roll the stage-test transaction back: contract tests must leave no
    rows behind (their gate-log writes are scratch, not evidence)."""


@contextmanager
def scratch_tx(store):
    try:
        with store.serialized_tx() as cur:
            yield cur
            raise _Rollback
    except _Rollback:
        pass


def _ctx(store, cur, sub: dict) -> GateContext:
    return GateContext(
        cur=cur, store=store, authority=None, context_assembler=None,
        materializer=None, products=None, sub=sub,
        request_id="cir:stage-test", ingested_at="2026-06-12T00:00:00Z",
        source_digest="sha256:stage-test",
        commit_class=sub.get("commitClass", "OPERATION_CLAIM"),
        farm_ref=sub.get("farmRef", demo.FARM),
        acting_party=sub.get("actingPartyRef", demo.FARMER),
        idem_key="stage-test", event_id="event:stage-test",
        assertion_id="assert:stage-test",
        event_time=sub.get("eventTime"),
        captured_at=sub.get("capturedAt", "2026-06-12T00:00:00Z"))


def test_temporal_validator_contract(store):
    with scratch_tx(store) as cur:
        # junk pre-parse problem -> refusal, FAIL_TEMPORAL, RETAIN_DRAFT
        ctx = _ctx(store, cur, {"eventTime": None})
        ctx.temporal_problem = {"schemaVersion": "ofarm.runtimeproblem.v0.1",
                                "problemId": "problem:stage-test",
                                "severity": "ERROR",
                                "reasonCode": "EVIDENCE_INSUFFICIENT",
                                "title": "t", "detail": "junk time"}
        refusal = TemporalConformanceValidator().run(ctx)
        assert isinstance(refusal, GateRefusal)
        assert (refusal.gate, refusal.outcome, refusal.final_outcome) == \
            ("VALIDATION", "FAIL_TEMPORAL", "RETAIN_DRAFT")

        # implausible-but-parseable time -> review route, NOT a refusal
        ctx2 = _ctx(store, cur, {"eventTime": "2020-01-01T00:00:00Z"})
        assert TemporalConformanceValidator().run(ctx2) is None
        assert ctx2.review_route_reasons, "implausible time must route to review"
        assert ctx2.review_route_reasons[0]["severity"] == "WARNING"


def test_promotion_target_validator_contract():
    from kernel import validators as validators_module

    def context(commit_class, requested_target=None, subject_type="FARM"):
        return SimpleNamespace(
            commit_class=commit_class,
            requested_target=requested_target,
            sub={"subjectType": subject_type},
            log=lambda *_args, **_kwargs: None,
        )

    ctx = context("OBSERVATION_ASSERTION", "COMPLIANCE_FACT")
    refusal = PromotionTargetValidator().run(ctx)
    assert isinstance(refusal, GateRefusal)
    assert refusal.problems[0]["reasonCode"] == "HIGH_CONSEQUENCE_BLOCKED"

    ctx2 = context("OPERATION_CLAIM", subject_type="OTHER")
    refusal2 = PromotionTargetValidator().run(ctx2)
    assert isinstance(refusal2, GateRefusal)
    assert refusal2.problems[0]["reasonCode"] == "IDENTITY_UNRESOLVED"

    # A one-shot, self-restoring module replacement after preflight must
    # never intercept the validator's refusal decision.
    original_refusal = validators_module._refusal
    hostile_called = False

    def hostile_refusal(*args, **kwargs):
        nonlocal hostile_called
        hostile_called = True
        validators_module._refusal = original_refusal
        return original_refusal(*args, **kwargs)

    validators_module._refusal = hostile_refusal
    try:
        refusal3 = PromotionTargetValidator().run(
            context("OBSERVATION_ASSERTION", "COMPLIANCE_FACT"))
    finally:
        validators_module._refusal = original_refusal

    assert isinstance(refusal3, GateRefusal)
    assert refusal3.problems[0]["reasonCode"] == "HIGH_CONSEQUENCE_BLOCKED"
    assert hostile_called is False

    # Governance contest dispatch likewise retains the standalone helper;
    # replacing its module name cannot steer the branch through hostile code.
    original_contest = validators_module._validate_governance_contest
    hostile_contest_called = False

    def hostile_contest(_ctx):
        nonlocal hostile_contest_called
        hostile_contest_called = True
        validators_module._validate_governance_contest = original_contest
        return None

    contest_ctx = SimpleNamespace(
        commit_class="GOVERNANCE_DECISION",
        review_action="CONTEST",
        review_outcome="CONTESTED",
        review_branch=None,
        acceptance_target=None,
        log=lambda *_args, **_kwargs: None,
    )
    validators_module._validate_governance_contest = hostile_contest
    try:
        contest_refusal = validators_module.GovernanceAcceptanceValidator().run(
            contest_ctx,
            _invoke_policy=lambda _ctx, _entry, *_args: "CONTEST",
        )
    finally:
        validators_module._validate_governance_contest = original_contest

    assert isinstance(contest_refusal, GateRefusal)
    assert contest_refusal.problems[0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"
    assert hostile_contest_called is False


def test_scope_containment_validator_contract(store):
    with scratch_tx(store) as cur:
        # TENANT is never a commitable claim scope
        ctx = _ctx(store, cur, {
            "commitClass": "OPERATION_CLAIM",
            "targetScopes": [{"scopeType": "TENANT", "scopeRef": config.TENANT_REF}]})
        refusal = ScopeContainmentValidator().run(ctx)
        assert isinstance(refusal, GateRefusal)
        assert refusal.problems[0]["reasonCode"] == "SCOPE_NOT_AUTHORIZED"

        # the demo field is anchored on the demo farm -> pass
        ctx2 = _ctx(store, cur, {
            "commitClass": "OPERATION_CLAIM",
            "subjectType": "FIELD", "subjectRef": demo.FIELD})
        assert ScopeContainmentValidator().run(ctx2) is None


def test_supersession_validator_contract(store):
    with scratch_tx(store) as cur:
        ctx = _ctx(store, cur, {
            "commitClass": "OPERATION_CLAIM",
            "supersedesConsequenceRef": "conseq:does.not.exist"})
        refusal = SupersessionValidator().run(ctx)
        assert isinstance(refusal, GateRefusal)
        assert refusal.problems[0]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"

        # a non-consequence target is the wrong kind
        ctx2 = _ctx(store, cur, {
            "commitClass": "OPERATION_CLAIM",
            "supersedesConsequenceRef": demo.FARMER})   # a Party record
        refusal2 = SupersessionValidator().run(ctx2)
        assert isinstance(refusal2, GateRefusal)
        assert refusal2.problems[0]["reasonCode"] == "SUPERSEDED_RECORD_USED"


def test_carrier_schema_validator_refuses_unknown_contract(store):
    """An unknown carrier schemaVersion is a governed FAIL_SCHEMA refusal,
    never an uncaught crash (pride review: UnknownContract escaped the
    except clause as a 500)."""
    with scratch_tx(store) as cur:
        ctx = _ctx(store, cur, {
            "commitClass": "OPERATION_CLAIM",
            "payload": {"schemaVersion": "ofarm.no-such-contract.v9.9"}})
        refusal = CarrierSchemaValidator().run(ctx)
        assert isinstance(refusal, GateRefusal)
        assert (refusal.gate, refusal.outcome) == ("VALIDATION", "FAIL_SCHEMA")
        assert refusal.problems[0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"


def test_compliance_claim_validator_refuses_non_identity_subject(store):
    """A complianceClaim.subjectScopeRef resolving to a NON-IDENTITY record
    (here: the demo farmer's Party record) is a governed FAIL_SEMANTIC
    refusal, never a silent pass (steward review of PR #4, finding 1)."""
    from kernel.validators import ComplianceClaimValidator
    with scratch_tx(store) as cur:
        ctx = _ctx(store, cur, {
            "commitClass": "COMPLIANCE_ASSERTION",
            "payload": {"complianceClaim": {
                "statement": "fictional demo: stage-test claim",
                "assertedStatus": "CLAIMED_COMPLIANT",
                "governingRuleRefs": [config.EVIDENCE_POLICY_REF],
                "subjectScopeRef": demo.FARMER}}})
        refusal = ComplianceClaimValidator().run(ctx)
        assert isinstance(refusal, GateRefusal)
        assert (refusal.gate, refusal.outcome, refusal.final_outcome) == \
            ("VALIDATION", "FAIL_SEMANTIC", "RETAIN_DRAFT")
        assert refusal.problems[0]["reasonCode"] == "IDENTITY_UNRESOLVED"

        # type-confused claim fields are governed refusals, never crashes
        for bad in ({"assertedStatus": ["CLAIMED_COMPLIANT"]},
                    {"governingRuleRefs": {config.EVIDENCE_POLICY_REF: True}},
                    {"governingRuleRefs": True}):
            sub = {"commitClass": "COMPLIANCE_ASSERTION",
                   "payload": {"complianceClaim": {
                       "statement": "fictional demo: stage-test claim",
                       "assertedStatus": "CLAIMED_COMPLIANT",
                       "governingRuleRefs": [config.EVIDENCE_POLICY_REF],
                       "subjectScopeRef": demo.FARM, **bad}}}
            r = ComplianceClaimValidator().run(_ctx(store, cur, sub))
            assert isinstance(r, GateRefusal), f"must refuse, not crash: {bad}"
            assert r.problems[0]["reasonCode"] == "EVIDENCE_INSUFFICIENT"


def test_compliance_claim_recovery_fails_closed(store):
    """recover_compliance_claim returns None (never a guess) when no durable
    ComplianceClaim record is linked — acceptance's claim-recoverable check
    then fails closed."""
    assert sufficiency.recover_compliance_claim(
        store, "assert:does.not.exist") is None


# =========================================================================
# retained decision semantics: hostile post-preflight mutation is inert
# =========================================================================

def test_review_branch_default_mutation_is_rejected_before_equality_executes(
        fresh_store):
    from kernel import validators as validators_module
    from kernel.runtime_bundle import RuntimeBundleError

    original_defaults = policy.review_branch.__defaults__
    equality_called = False

    class OneShotAbsent:
        def __eq__(self, _other):
            nonlocal equality_called
            equality_called = True
            policy.review_branch.__defaults__ = original_defaults
            return True

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with fresh_store.serialized_tx() as cur:
            ctx = _ctx(fresh_store, cur, {
                "commitClass": "GOVERNANCE_DECISION",
            })
            policy.review_branch.__defaults__ = (OneShotAbsent(),)
            try:
                with pytest.raises(RuntimeBundleError, match="review_branch"):
                    validators_module._invoke_retained_policy_function(
                        ctx,
                        validators_module._RETAINED_POLICY_FUNCTIONS[0],
                        "REVIEW_ACCEPT",
                        None,
                    )
            finally:
                policy.review_branch.__defaults__ = original_defaults

    assert equality_called is False


def test_store_outer_contract_validation_swap_is_rejected_and_rolls_back(
        fresh_store):
    from kernel import context as context_module
    from kernel.runtime_bundle import RuntimeBundleError
    from kernel.store import Store

    original = Store._validate_contract
    original_integrity_marker = Store._mark_transaction_integrity_violation
    hostile_called = False
    hostile_integrity_marker_called = False
    retained_party_id = (
        f"party:issue171.store-outer-retained.{uuid.uuid4().hex}")
    hostile_party_id = (
        f"party:issue171.store-outer-hostile.{uuid.uuid4().hex}")

    def party_payload(party_id: str) -> dict:
        return {
            "schemaVersion": "ofarm.party.v0.1",
            "partyId": party_id,
            "partyClass": "NATURAL_PERSON",
            "displayName": "Issue 171 Store dispatch test (fictional)",
            "partyState": "ACTIVE",
            "recordedAt": context_module.now_iso(),
        }

    def hostile_validate(self, payload):
        nonlocal hostile_called
        hostile_called = True
        Store._validate_contract = original
        return original(self, payload)

    def hostile_integrity_marker(_self):
        nonlocal hostile_integrity_marker_called
        hostile_integrity_marker_called = True
        Store._mark_transaction_integrity_violation = \
            original_integrity_marker

    with pytest.raises(RuntimeBundleError, match="rollback-only"):
        with fresh_store.serialized_tx() as cur:
            fresh_store.insert_record(cur, party_payload(retained_party_id))
            Store._validate_contract = hostile_validate
            Store._mark_transaction_integrity_violation = \
                hostile_integrity_marker
            try:
                with pytest.raises(RuntimeBundleError):
                    fresh_store.insert_record(
                        cur, party_payload(hostile_party_id))
                assert hostile_integrity_marker_called is False
                assert fresh_store._active_transaction_integrity.poisoned is True
            finally:
                Store._validate_contract = original
                Store._mark_transaction_integrity_violation = \
                    original_integrity_marker

    assert hostile_called is False
    assert hostile_integrity_marker_called is False
    assert fresh_store.get_record(retained_party_id) is None
    assert fresh_store.get_record(hostile_party_id) is None


def test_authority_stage_uses_retained_action_map_after_gate_preflight(
        fresh_store, fresh_pipeline):
    from kernel import stages as stages_module
    from kernel.gates import GatePipeline
    from kernel.stages import AuthorityGate, GatePass

    original = stages_module._COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS
    hostile_consumed = False
    selected_actions = []
    recorded_decisions = []

    class OneShotAuthorityMap(dict):
        def __getitem__(self, key):
            nonlocal hostile_consumed
            hostile_consumed = True
            stages_module._COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS = original
            return "OBSERVE_CREATE_OBSERVATION"

    def invoke_context_service(_ctx, _entry, _service, **kwargs):
        action_class = kwargs["action_class"]
        selected_actions.append(action_class)
        return SimpleNamespace(
            outcome="ALLOW",
            request_payload={
                "requestId": "authzreq:stage-retained-map",
                "actionClass": action_class,
            },
            result_payload={
                "resultId": "authzres:stage-retained-map",
                "reasonSummary": "retained map test",
            },
            trace_payload={"traceId": "authztrace:stage-retained-map"},
            problems=[],
        )

    def invoke_decision(_ctx, _entry, *args):
        return "DENY" if len(args) == 2 else True

    sub = demo.spray_submission(
        f"issue171-stage-retained-map:{uuid.uuid4().hex}",
        erp_id=f"erp:issue171.stage-retained-map.{uuid.uuid4().hex}",
        confirm=False,
    )
    with fresh_store.serialized_tx() as cur:
        GatePipeline._assert_runtime_composition(fresh_pipeline)
        ctx = _ctx(fresh_store, cur, sub)
        ctx.authority = object()
        ctx.record_authority_decision = recorded_decisions.append
        ctx.log = lambda *_args, **_kwargs: None
        stage, stage_type, retained_run, _code, _state = \
            fresh_pipeline._stage_dispatch[0]
        assert stage_type is AuthorityGate

        hostile = OneShotAuthorityMap(original)
        stages_module._COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS = hostile
        try:
            outcome = retained_run(
                stage,
                ctx,
                _invoke_context_service=invoke_context_service,
                _invoke_decision=invoke_decision,
            )
            assert isinstance(outcome, GatePass)
            assert selected_actions == ["ASSERT_OPERATION_CLAIM"]
            assert recorded_decisions == [ctx.authz_decision]
            assert ctx.authz_decision.request_payload["actionClass"] == \
                "ASSERT_OPERATION_CLAIM"
            assert hostile_consumed is False
            assert stages_module._COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS is hostile
        finally:
            stages_module._COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS = original


def test_actor_attribution_uses_retained_authority_predicate():
    from kernel import authority as authority_module
    from kernel.runtime_bundle import RuntimeBundleError
    from kernel.store import Store
    from kernel.validators import ActorAttributionValidator

    original = authority_module.authority_decision_allowed
    hostile_called = False
    store = object.__new__(Store)
    object.__setattr__(store, "_active_transaction_integrity", None)
    basis = SimpleNamespace(
        result_payload={"resultId": "authzres:retained-attribution"},
    )
    ctx = SimpleNamespace(
        store=store,
        sub={"payload": {"actor": {"actorPartyRef": "party:named-actor"}}},
        acting_party="party:submitter",
        authority=object(),
        cur=object(),
        farm_ref=demo.FARM,
        review_route_reasons=[],
        record_authority_decision=lambda _basis: None,
    )

    def hostile_predicate(_basis):
        nonlocal hostile_called
        hostile_called = True
        authority_module.authority_decision_allowed = original
        return True

    def invoke_context(_ctx, _entry, _service, **_kwargs):
        return basis

    authority_module.authority_decision_allowed = hostile_predicate
    try:
        with pytest.raises(
                RuntimeBundleError,
                match="authority_decision_allowed changed"):
            ActorAttributionValidator().run(
                ctx, _invoke_context=invoke_context)
    finally:
        authority_module.authority_decision_allowed = original

    assert hostile_called is False
    assert ctx.review_route_reasons == []
