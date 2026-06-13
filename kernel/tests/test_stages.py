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
from contextlib import contextmanager

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
        with store.tx() as cur:
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


def test_promotion_target_validator_contract(store):
    with scratch_tx(store) as cur:
        ctx = _ctx(store, cur, {"commitClass": "OBSERVATION_ASSERTION",
                                "eventTime": "2026-06-10T09:00:00Z"})
        ctx.requested_target = "COMPLIANCE_FACT"   # unlawful for observations
        refusal = PromotionTargetValidator().run(ctx)
        assert isinstance(refusal, GateRefusal)
        assert refusal.problems[0]["reasonCode"] == "HIGH_CONSEQUENCE_BLOCKED"

        ctx2 = _ctx(store, cur, {"commitClass": "OPERATION_CLAIM",
                                 "subjectType": "OTHER", "subjectRef": "x:y"})
        refusal2 = PromotionTargetValidator().run(ctx2)
        assert isinstance(refusal2, GateRefusal)
        assert refusal2.problems[0]["reasonCode"] == "IDENTITY_UNRESOLVED"


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
