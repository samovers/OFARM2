"""Regression tests for the kernel review fixes (H1/H2/H3/M2).

Engineering tests, NOT part of the named conformance suite (conftest only
records test_conformance.py into the evidence file). Each test pins a defect
the review found and the gate behavior that now closes it. All data is
fictional and format-true (privacy rule 1).
"""
from __future__ import annotations

import uuid

import pytest

from kernel import demo, policy
from kernel.store import Store


def uid() -> str:
    return uuid.uuid4().hex[:10]


# ---------------------------------------------------------------------------
# H2 — the UCUM unit gate is a real unit check, not a namespace-prefix check
# ---------------------------------------------------------------------------

def test_h2_unit_helper_rejects_bare_and_lookalike_codes():
    assert policy.is_resolved_ucum_unit("scheme:ucum:L/har")
    assert policy.is_resolved_ucum_unit("scheme:ucum:%")
    # bare namespace, empty code, and substring look-alikes are NOT units
    assert not policy.is_resolved_ucum_unit("scheme:ucum")
    assert not policy.is_resolved_ucum_unit("scheme:ucum:")
    assert not policy.is_resolved_ucum_unit("scheme:ucum:   ")
    assert not policy.is_resolved_ucum_unit("scheme:ucumbersome:L/har")
    assert not policy.is_resolved_ucum_unit("")
    assert not policy.is_resolved_ucum_unit(None)


def test_h2_bogus_ucum_dose_unit_blocks_promotion(pipeline):
    # a dose carrying a meaningless UCUM unit must refuse (BLOCK_PROMOTION),
    # never promote to an AcceptedEventConsequence (Kernel rule 4).
    for bad in ("scheme:ucum", "scheme:ucum:", "scheme:ucumbersome"):
        r = pipeline.commit(demo.spray_submission(
            f"h2:{uid()}", erp_id=f"erp:h2.{uid()}", unit_ref=bad))
        assert r["decisionOutcome"] == "RETAIN_DRAFT", f"{bad!r} must not promote"
        assert any(p["reasonCode"] == "UNIT_UNRESOLVED" for p in r["problems"]), bad


# ---------------------------------------------------------------------------
# H3 — a promoting assertion is never its own evidence
# ---------------------------------------------------------------------------

def test_h3_promoting_observation_without_evidence_stays_draft(pipeline):
    # OBSERVATION_ASSERTION promotes; with no evidence it must RETAIN_DRAFT
    # rather than backfill evidenceRefs with the captured event id.
    r = pipeline.commit({
        "commitClass": "OBSERVATION_ASSERTION",
        "actingPartyRef": demo.FARMER, "farmRef": demo.FARM,
        "idempotencyKey": f"h3-no-ev:{uid()}",
        "eventTime": "2026-06-10T09:00:00Z",
        "confirmAccept": True})
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert any(p["reasonCode"] == "EVIDENCE_INSUFFICIENT" for p in r["problems"])
    # refused before emission: no assertion and no consequence were manufactured
    assert not r.get("emittedAssertionRecordRefs")
    assert not r.get("emittedAcceptedConsequenceRefs")


@pytest.mark.parametrize("bad_refs, why", [
    (["evidence:does.not.exist"], "dangling ref resolves to nothing"),
    ([demo.FARMER], "wrong-kind ref resolves to a Party, not an EvidenceRecord"),
])
def test_h3_promoting_observation_with_unresolvable_evidence_stays_draft(
        pipeline, bad_refs, why):
    # PR #5 review follow-up: observation/structure skip
    # ReferenceResolutionValidator, so the evidence-sufficiency gate must
    # reject evidence that does not resolve to a durable EvidenceRecord —
    # a dangling or wrong-kind ref is fake evidence, as bad as the old
    # self-evidence backfill (Kernel rule 4 / rule 7).
    r = pipeline.commit({
        "commitClass": "OBSERVATION_ASSERTION",
        "actingPartyRef": demo.FARMER, "farmRef": demo.FARM,
        "idempotencyKey": f"h3-bad-ev:{uid()}",
        "eventTime": "2026-06-10T09:00:00Z",
        "evidenceRefs": bad_refs,
        "confirmAccept": True})
    assert r["decisionOutcome"] == "RETAIN_DRAFT", why
    assert any(p["reasonCode"] == "EVIDENCE_INSUFFICIENT" for p in r["problems"]), why
    assert not r.get("emittedAcceptedConsequenceRefs"), why


def test_h3_promoting_observation_with_evidence_promotes(pipeline):
    # positive control: the same observation WITH a real, resolving durable
    # EvidenceRecord promotes (evidenceRefs are the submitted evidence).
    r = pipeline.commit({
        "commitClass": "OBSERVATION_ASSERTION",
        "actingPartyRef": demo.FARMER, "farmRef": demo.FARM,
        "idempotencyKey": f"h3-ev:{uid()}",
        "eventTime": "2026-06-10T09:00:00Z",
        "evidenceRefs": [demo.PHOTO_EVIDENCE],
        "confirmAccept": True})
    assert r["decisionOutcome"] == "PROMOTE_ACCEPTED"


# ---------------------------------------------------------------------------
# M2 — a wrong-kind binding ref refuses governably (never a bare KeyError)
# ---------------------------------------------------------------------------

def test_m2_wrong_kind_binding_ref_is_governed_refusal(pipeline):
    # a binding ref pointing at a non-binding record (here an EvidenceRecord)
    # used to dereference b["bindingRole"] into an uncaught KeyError; it must
    # now produce a governed refusal recorded as a RuntimeProblem (rule 7).
    r = pipeline.commit(demo.spray_submission(
        f"m2:{uid()}", erp_id=f"erp:m2.{uid()}",
        binding_refs=[demo.PHOTO_EVIDENCE]))
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert any(p["reasonCode"] == "PRODUCT_BINDING_UNRESOLVED"
               for p in r["problems"])


# ---------------------------------------------------------------------------
# M3 — a non-whole extent must quantify what was treated
# ---------------------------------------------------------------------------

def test_m3_partial_extent_without_bound_stays_draft(pipeline):
    # a PARTIAL_TARGET_SCOPE spray carrying no area / geometryRef / extentRef /
    # scopeExtentBasisRef is an incomplete carrier ("size treated" is a required
    # SI field); it must not silently promote as if whole-scope (Kernel rule 4/7).
    sub = demo.spray_submission(f"m3:{uid()}", erp_id=f"erp:m3.{uid()}")
    sub["payload"]["executionExtent"] = {
        "extentClass": "PARTIAL_TARGET_SCOPE",
        "targetScope": {"scopeType": "FIELD", "scopeRef": demo.FIELD},
        "extentBasisStatus": "OPERATOR_SKETCH"}
    r = pipeline.commit(sub)
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert any(p["reasonCode"] == "EVIDENCE_INSUFFICIENT" for p in r["problems"])
    assert not r.get("emittedAcceptedConsequenceRefs")


@pytest.mark.parametrize("ref_field, ref_value, why", [
    # dangling: the ref resolves to nothing
    ("geometryRef", "geometry:missing", "dangling geometryRef"),
    ("extentRef", "extent:missing", "dangling extentRef"),
    ("scopeExtentBasisRef", "basis:missing", "dangling scopeExtentBasisRef"),
    # wrong-kind: the ref resolves, but not to an extent-bound carrier
    ("geometryRef", demo.FARMER, "wrong-kind geometryRef -> Party"),
    ("extentRef", demo.PHOTO_EVIDENCE, "wrong-kind extentRef -> EvidenceRecord"),
    ("scopeExtentBasisRef", demo.FIELD, "wrong-kind scopeExtentBasisRef -> Identity"),
])
def test_m3_partial_extent_with_invalid_bound_ref_stays_draft(
        pipeline, ref_field, ref_value, why):
    # PR #6 re-reviews: a non-whole extent whose only "bound" is a ref that does
    # not resolve to a recognized extent-bound carrier is a fake bound. M1 has
    # no extent ingestion surface (policy.M1_ALLOWED_EXTENT_BOUND_KINDS empty),
    # so both dangling AND wrong-kind existing refs must refuse — "resolves to
    # something" is not "resolves to the right kind of thing".
    sub = demo.spray_submission(f"m3-bad:{uid()}", erp_id=f"erp:m3b.{uid()}")
    sub["payload"]["executionExtent"] = {
        "extentClass": "PARTIAL_TARGET_SCOPE",
        "targetScope": {"scopeType": "FIELD", "scopeRef": demo.FIELD},
        "extentBasisStatus": "OPERATOR_SKETCH",
        ref_field: ref_value}
    r = pipeline.commit(sub)
    assert r["decisionOutcome"] == "RETAIN_DRAFT", why
    assert any(p["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"
               for p in r["problems"]), why
    assert not r.get("emittedAcceptedConsequenceRefs"), why


def test_m3_partial_extent_with_area_promotes(pipeline):
    # positive control: the same partial spray WITH a quantified area promotes.
    sub = demo.spray_submission(f"m3-ok:{uid()}", erp_id=f"erp:m3ok.{uid()}")
    sub["payload"]["executionExtent"] = {
        "extentClass": "PARTIAL_TARGET_SCOPE",
        "targetScope": {"scopeType": "FIELD", "scopeRef": demo.FIELD},
        "extentBasisStatus": "OPERATOR_SKETCH",
        "area": {"quantityKindRef": "scheme:qudt:Area",
                 "unitRef": "scheme:ucum:har", "value": 0.5}}
    r = pipeline.commit(sub)
    assert r["decisionOutcome"] == "PROMOTE_ACCEPTED"


# ---------------------------------------------------------------------------
# H1 — AS_OF in-force reconstruction runs on the single server-commit axis
# ---------------------------------------------------------------------------

def test_h1_as_of_reconstruction_is_coherent_across_supersession(pipeline, store):
    # commit a spray, then correct (supersede) it; AS_OF state taken AFTER the
    # correction must show exactly the correction in force for the field —
    # never a hole (both gone) or a duplicate (both present) at the boundary.
    from kernel import context, materializer as mat_mod
    materializer = mat_mod.Materializer(store)

    first = pipeline.commit(demo.spray_submission(
        f"h1a:{uid()}", erp_id=f"erp:h1.{uid()}"))
    assert first["decisionOutcome"] == "PROMOTE_ACCEPTED"
    c1 = first["emittedAcceptedConsequenceRefs"][0]

    correction = demo.spray_submission(
        f"h1b:{uid()}", erp_id=f"erp:h1.{uid()}", dose_value=0.25)
    correction["supersedesConsequenceRef"] = c1
    second = pipeline.commit(correction)
    assert second["decisionOutcome"] == "PROMOTE_ACCEPTED"
    c2 = second["emittedAcceptedConsequenceRefs"][0]

    as_of = context.now_iso()
    in_force = {row["record_id"]
                for row in store.in_force_consequences(demo.FARM, as_of=as_of)}
    # exactly one of the pair is in force as-of now: the correction, not the
    # superseded original, and never both / neither
    assert c2 in in_force
    assert c1 not in in_force
