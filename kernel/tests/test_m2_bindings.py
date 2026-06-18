"""M2 G3 — reference resolution & verification-trace support.

Engineering tests, NOT part of the named conformance suite. They pin the generic
mechanism: resolving a candidate against an in-force ReferenceSnapshot produces
an ExternalRegistryVerificationTrace and a verdict — identity-grade confirms,
locator-only / not-found routes to review, an absent snapshot refuses governably.
A generic FIXTURE scheme only — no REGSR/GERK/FFSNaprave literals (P4 injects the
real lookups). All data fictional and format-true (privacy rule 1).
"""
from __future__ import annotations

import uuid

from kernel.adapters import ImportRunner, ParseResult
from kernel.verification import (CONFIRM, IDENTITY, LOCATOR, NONE, REFUSE,
                                 REVIEW, LookupResult, ReferenceResolver)

TRACE_KIND = "ofarm.externalregistryverificationtrace.v0.1"


def uid():
    return uuid.uuid4().hex[:10]


def _import_fixture_snapshot(store, prefix, *, effective="2026-05-01T00:00:00Z",
                             until=None):
    """A dated fixture ReferenceSnapshot under `prefix`, via the G2 importer."""
    sid = f"{prefix}.{uid()}"
    meta = {"referenceSnapshotId": sid, "referenceClass": "CODE_LIST",
            "domain": "fixture reference source (test)",
            "issuingAuthorityRef": "party:fixture.authority",
            "jurisdictionRef": "jurisdiction:FIXTURE",
            "canonicalVersionLabel": "fixture.parse.v1",
            "effectiveFrom": effective,
            "sourceArtifactRefs": ["surface:fixture.test.source"]}
    if until:
        meta["effectiveUntil"] = until
    result = ImportRunner(store).run_import(
        ParseResult(ok=True, sourceDigest=f"sha256-{uid()}"), meta)
    assert result["imported"]
    return sid


def _verify(store, *, prefix, query, lookup, scheme="fixture-register",
            key_field="fixture-key", **kw):
    resolver = ReferenceResolver(store)
    with store.serialized_tx() as cur:
        return resolver.verify(
            cur, query_value=query, snapshot_prefix=prefix, lookup=lookup,
            profile_ref="profile:fixture", authority_ref="party:fixture.authority",
            jurisdiction_ref="jurisdiction:FIXTURE", scheme=scheme,
            key_field=key_field, **kw)


def _identity(sid, q):
    return LookupResult(grade=IDENTITY, candidate_count=1,
                        external_id=f"{q}-KEY", status_observed="AUTHORISED")


def _locator(sid, q):
    return LookupResult(grade=LOCATOR, candidate_count=2,
                        status_observed="MULTIPLE_CANDIDATES")


def _not_found(sid, q):
    return LookupResult(grade=NONE, candidate_count=0, status_observed="NOT_FOUND")


def _identity_no_key(sid, q):
    # claims identity-grade but carries NO stable key — must NOT confirm
    return LookupResult(grade=IDENTITY, candidate_count=1, external_id=None,
                        status_observed="UNKNOWN")


# ---------------------------------------------------------------------------

def test_g3_identity_grade_confirms(store):
    prefix = f"referencesnapshot:fixture.reg.{uid()}"
    sid = _import_fixture_snapshot(store, prefix)
    r = _verify(store, prefix=prefix, query="ACME-42", lookup=_identity,
                external_id_role="OTHER")
    assert r["verdict"] == CONFIRM and r["problem"] is None
    assert r["snapshotRef"] == sid
    t = r["trace"]
    assert t["finalOutcome"] == "PASS"
    assert t["registryAvailability"] == "AVAILABLE"
    assert t["selectedExternalId"]["externalId"] == "ACME-42-KEY"
    assert t["snapshotRefs"] == [sid]
    assert t["highConsequenceUse"] == "ALLOWED_WHEN_PASS"
    # stored == contract-validated
    assert store.get_record(t["externalRegistryVerificationTraceId"]) is not None


def test_g3_locator_only_routes_to_review(store):
    prefix = f"referencesnapshot:fixture.reg.{uid()}"
    _import_fixture_snapshot(store, prefix)
    r = _verify(store, prefix=prefix, query="ambiguous-name", lookup=_locator,
                review_reason_code="PRODUCT_BINDING_UNRESOLVED")
    assert r["verdict"] == REVIEW and r["grade"] == LOCATOR
    assert r["problem"]["reasonCode"] == "PRODUCT_BINDING_UNRESOLVED"
    t = r["trace"]
    assert t["finalOutcome"] == "REVIEW_REQUIRED"
    assert t["selectedExternalId"]["externalIdRole"] == "NONE"
    assert t["downstreamOutputDisposition"] == "PASSPORTVIEW_REQUIRE_REVIEW"
    assert t["discrepancies"] and t["discrepancies"][0]["severity"] == "REVIEW_REQUIRED"


def test_g3_not_found_routes_to_review(store):
    prefix = f"referencesnapshot:fixture.reg.{uid()}"
    _import_fixture_snapshot(store, prefix)
    r = _verify(store, prefix=prefix, query="nope", lookup=_not_found)
    assert r["verdict"] == REVIEW and r["grade"] == NONE
    assert r["problem"]["reasonCode"] == "IDENTITY_UNRESOLVED"   # default
    assert r["trace"]["statusObserved"] == "NOT_FOUND"


def test_g3_identity_grade_without_key_routes_to_review(store):
    # PR #11 review: identity-grade REQUIRES a stable external key. A lookup that
    # claims IDENTITY but carries none must route to review, never CONFIRM/PASS.
    prefix = f"referencesnapshot:fixture.reg.{uid()}"
    _import_fixture_snapshot(store, prefix)
    r = _verify(store, prefix=prefix, query="claims-id-no-key", lookup=_identity_no_key)
    assert r["verdict"] == REVIEW and r["grade"] == IDENTITY
    assert r["problem"]["reasonCode"] == "IDENTITY_UNRESOLVED"
    t = r["trace"]
    assert t["finalOutcome"] == "REVIEW_REQUIRED"
    assert t["highConsequenceUse"] != "ALLOWED_WHEN_PASS"
    assert t["selectedExternalId"]["externalIdRole"] == "NONE"
    assert "externalId" not in t["selectedExternalId"]


def test_g3_future_effective_snapshot_is_not_current(store):
    # PR #11 review: a future-effective snapshot is never "current" for NOW.
    prefix = f"referencesnapshot:fixture.future.{uid()}"
    _import_fixture_snapshot(store, prefix, effective="2099-01-01T00:00:00Z")
    r = _verify(store, prefix=prefix, query="x", lookup=_identity)
    assert r["verdict"] == REFUSE, "a future-effective snapshot must not be current for NOW"
    # but AS_OF a time after it becomes effective, it IS in force
    r2 = _verify(store, prefix=prefix, query="x", lookup=_identity,
                 as_of="2099-06-01T00:00:00Z")
    assert r2["verdict"] == CONFIRM


def test_g3_expired_snapshot_is_not_current(store):
    # PR #11 review: an expired snapshot (effectiveUntil <= now) is not in force.
    prefix = f"referencesnapshot:fixture.expired.{uid()}"
    _import_fixture_snapshot(store, prefix, effective="2020-01-01T00:00:00Z",
                             until="2021-01-01T00:00:00Z")
    r = _verify(store, prefix=prefix, query="x", lookup=_identity)
    assert r["verdict"] == REFUSE, "an expired snapshot is no longer in force"


def test_g3_missing_snapshot_refuses(store):
    # a prefix with no in-force snapshot -> governed refusal. No trace is emitted:
    # an ExternalRegistryVerificationTrace is inherently a record AGAINST a
    # snapshot (snapshotRefs required non-empty), so the refusal is the
    # RuntimeProblem the caller records — never a fabricated trace.
    prefix = f"referencesnapshot:fixture.absent.{uid()}"
    r = _verify(store, prefix=prefix, query="ACME-42", lookup=_identity)
    assert r["verdict"] == REFUSE and r["snapshotRef"] is None and r["trace"] is None
    assert r["problem"]["reasonCode"] == "EVIDENCE_REFERENCE_UNAVAILABLE"


def test_g3_trace_carries_all_required_fields(store):
    prefix = f"referencesnapshot:fixture.reg.{uid()}"
    _import_fixture_snapshot(store, prefix)
    r = _verify(store, prefix=prefix, query="ACME-7", lookup=_identity)
    required = store.registry.get(TRACE_KIND).schema["required"]
    missing = [k for k in required if k not in r["trace"]]
    assert not missing, f"verification trace missing required fields: {missing}"


def test_g3_mechanism_is_generic_over_scheme(store):
    # the SAME code path verifies two UNRELATED schemes with no hardcoding —
    # scheme/key_field/enums are parameters, so verification.py couples to none.
    # Each trace RECORDS its caller-supplied scheme as audit provenance (the
    # trace's purpose, like the shipped demo trace's rationale) — that is the
    # caller's value flowing through a generic template, never a hardcoded literal.
    pa = f"referencesnapshot:fixture.alpha.{uid()}"
    pb = f"referencesnapshot:fixture.beta.{uid()}"
    _import_fixture_snapshot(store, pa)
    _import_fixture_snapshot(store, pb)
    ra = _verify(store, prefix=pa, query="x", lookup=_identity,
                 scheme="ALPHA:SCHEME-ONE", key_field="alpha-key")
    rb = _verify(store, prefix=pb, query="y", lookup=_identity,
                 scheme="BETA:OTHER-SCHEME", key_field="beta-id")
    assert ra["verdict"] == CONFIRM and rb["verdict"] == CONFIRM
    assert "ALPHA:SCHEME-ONE" in ra["trace"]["selectionRationale"]
    assert "BETA:OTHER-SCHEME" in rb["trace"]["selectionRationale"]
    # neither scheme bleeds into the other's trace -> no shared/hardcoded state
    assert "ALPHA:SCHEME-ONE" not in rb["trace"]["selectionRationale"]
    assert "BETA:OTHER-SCHEME" not in ra["trace"]["selectionRationale"]


def test_g3_as_of_selects_vintage_in_force_at_that_time(store):
    # an AS_OF before the snapshot's effectiveFrom sees no in-force snapshot ->
    # refusal (the resolver is as-of-aware; it never applies a future vintage)
    prefix = f"referencesnapshot:fixture.reg.{uid()}"
    _import_fixture_snapshot(store, prefix)   # effectiveFrom 2026-05-01
    r = _verify(store, prefix=prefix, query="ACME-42", lookup=_identity,
                as_of="2026-01-01T00:00:00Z")
    assert r["verdict"] == REFUSE, "no snapshot was in force before its effectiveFrom"
