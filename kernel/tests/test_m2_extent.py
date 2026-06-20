"""M2 G7 — extent-carrier acceptance mechanism.

Engineering tests, NOT part of the named conformance suite. They pin G7: a
non-whole executionExtent may now carry, instead of an inline `area`, a
geometryRef / extentRef / scopeExtentBasisRef that RESOLVES to a recognized
extent-carrier kind — the generic PartialExtent (`ofarm.partialextent.v0.1`,
policy.ALLOWED_EXTENT_BOUND_KINDS) — and is accepted as a real bound. A dangling
ref or a ref to the wrong kind is still refused (EVIDENCE_REFERENCE_UNAVAILABLE),
no bound at all is still refused (EVIDENCE_INSUFFICIENT), and an inline `area` is
still accepted. Every outcome is governed (a decisionOutcome, never a crash).

The SI geometry that POPULATES such carriers is package content (P2/GERK); this
ticket carries no SI geometry literals — the PartialExtent built here is a generic,
format-true fixture. All identifiers fictional and format-true (privacy rule 1).
"""
from __future__ import annotations

import uuid

import pytest

from kernel import demo
from kernel.context import now_iso


def uid():
    return uuid.uuid4().hex[:8]


def _partial_extent(store, pe_id: str, *, extent_state: str = "ACCEPTED_FOR_DECLARED_USE",
                    may_drive: bool = True, must_not_promote: list | None = None) -> str:
    """Insert a minimal, schema-valid generic PartialExtent (the extent-carrier
    kind) and return its id. Defaults to a usable carrier (ACCEPTED, drives
    materialization, forbids nothing); the kwargs flip it to a non-usable one.
    No SI geometry literals — a format-true fixture."""
    pe = {
        "schemaVersion": "ofarm.partialextent.v0.1",
        "partialExtentId": pe_id,
        "extentRole": "TREATMENT_AREA",
        "extentState": extent_state,
        "createdAt": now_iso(),
        "anchorScope": {"scopeType": "FIELD", "scopeRef": demo.FIELD},
        "parentScope": {"scopeType": "FIELD", "scopeRef": demo.FIELD},
        "temporalApplicability": {
            "timeType": "INSTANT", "timeBasis": "EXECUTION_INTERVAL",
            "instant": now_iso()},
        "geometryBasis": {
            "geometryBasisKind": "MACHINE_POLYGON",
            "geometrySource": "MACHINE_LOG",
            "geometryMethod": "task-controller as-applied polygon",
            "coordinateReferenceSystem": "EPSG:4326",
            "representation": "EXTERNAL_REFERENCE",
            "geometryQualityClass": "MACHINE_REPORTED"},
        "qualityStatement": {"basisStatus": "ACCEPTED", "qualityClass": "MACHINE_REPORTED"},
        "durableIdentityPolicy": {
            "createsDurableIdentity": False,
            "durableIdentityDecision": "EVENT_BOUND_ONLY"},
        "evidenceRefs": [demo.PHOTO_EVIDENCE],
        "promotionBoundary": {
            "highConsequenceUse": "USE_ALLOWED_FOR_DECLARED_PURPOSE",
            "mayDriveMaterialization": may_drive,
            "mustNotPromoteTo": must_not_promote or []},
    }
    with store.tx() as cur:
        store.insert_record(cur, pe)
    return pe_id


def _partial_spray(ref_field: str | None = None, ref_value: str | None = None,
                   *, area: dict | None = None) -> dict:
    sub = demo.spray_submission(f"g7:{uid()}", erp_id=f"erp:g7.{uid()}")
    extent = {
        "extentClass": "PARTIAL_TARGET_SCOPE",
        "targetScope": {"scopeType": "FIELD", "scopeRef": demo.FIELD},
        "extentBasisStatus": "OPERATOR_SKETCH"}
    if ref_field:
        extent[ref_field] = ref_value
    if area:
        extent["area"] = area
    sub["payload"]["executionExtent"] = extent
    return sub


# ---------------------------------------------------------------------------
# accepted: a ref bound resolving to the extent-carrier kind is a real bound
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ref_field", ["geometryRef", "extentRef", "scopeExtentBasisRef"])
def test_partial_extent_ref_to_carrier_promotes(store, pipeline, ref_field):
    # a partial extent whose bound is a {geometryRef|extentRef|scopeExtentBasisRef}
    # resolving to a PartialExtent (the recognized extent-carrier kind) is accepted.
    pe_id = _partial_extent(store, f"partialextent:treat.{uid()}")
    r = pipeline.commit(_partial_spray(ref_field, pe_id))
    assert r["decisionOutcome"] == "PROMOTE_ACCEPTED"
    assert r.get("emittedAcceptedConsequenceRefs")


def test_partial_extent_inline_area_still_promotes(store, pipeline):
    # regression: the always-available inline `area` bound is unchanged by G7.
    r = pipeline.commit(_partial_spray(
        area={"quantityKindRef": "scheme:qudt:Area", "unitRef": "scheme:ucum:har", "value": 0.5}))
    assert r["decisionOutcome"] == "PROMOTE_ACCEPTED"


# ---------------------------------------------------------------------------
# refused (governed): wrong-kind ref, dangling ref, no bound at all
# ---------------------------------------------------------------------------

def test_partial_extent_wrong_kind_ref_refused(store, pipeline):
    # the ref resolves, but to a Party — not an extent-carrier kind. "Resolves to
    # something" is not "resolves to the right kind of thing": refuse, stay draft.
    r = pipeline.commit(_partial_spray("extentRef", demo.FARMER))
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert any(p["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE" for p in r["problems"])
    assert not r.get("emittedAcceptedConsequenceRefs")


def test_partial_extent_dangling_ref_refused(store, pipeline):
    # the ref resolves to nothing: a fake bound, refuse, stay draft.
    r = pipeline.commit(_partial_spray("extentRef", f"partialextent:missing.{uid()}"))
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert any(p["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE" for p in r["problems"])
    assert not r.get("emittedAcceptedConsequenceRefs")


@pytest.mark.parametrize("kwargs, why", [
    ({"extent_state": "DRAFT"}, "carrier is a DRAFT, not accepted for use"),
    ({"extent_state": "DISPUTED"}, "carrier is DISPUTED"),
    ({"extent_state": "SUPERSEDED"}, "carrier is SUPERSEDED"),
    ({"may_drive": False}, "carrier's promotionBoundary forbids driving materialization"),
    ({"must_not_promote": ["ACCEPTED_EXECUTION"]}, "carrier forbids promotion to ACCEPTED_EXECUTION"),
    ({"must_not_promote": ["WHOLE_FIELD_TRUTH"]}, "carrier forbids promotion to WHOLE_FIELD_TRUTH"),
])
def test_partial_extent_carrier_not_usable_refused(store, pipeline, kwargs, why):
    # the ref resolves to a PartialExtent of the RIGHT KIND, but the carrier's own
    # state / promotionBoundary says it must not bound a promoting accepted
    # execution. "Right kind" is not "usable as a bound": refuse over pretend
    # (rule 4/7) rather than silently materialize on a non-accepted / self-
    # forbidding carrier. Honors the carrier's declared boundary, never overrides.
    pe_id = _partial_extent(store, f"partialextent:bad.{uid()}", **kwargs)
    r = pipeline.commit(_partial_spray("extentRef", pe_id))
    assert r["decisionOutcome"] == "RETAIN_DRAFT", why
    assert any(p["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE" for p in r["problems"]), why
    assert not r.get("emittedAcceptedConsequenceRefs"), why


def test_partial_extent_no_bound_refused(store, pipeline):
    # no area and no ref at all: "size treated" is unquantified -> refuse with
    # EVIDENCE_INSUFFICIENT (distinct from the unresolved-ref reason), stay draft.
    r = pipeline.commit(_partial_spray())
    assert r["decisionOutcome"] == "RETAIN_DRAFT"
    assert any(p["reasonCode"] == "EVIDENCE_INSUFFICIENT" for p in r["problems"])
    assert not r.get("emittedAcceptedConsequenceRefs")
