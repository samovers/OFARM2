"""Reference resolution & verification-trace support (M2 G3).

A generic mechanism to resolve a candidate binding against an in-force
`ReferenceSnapshot` and emit an `ExternalRegistryVerificationTrace` (the
machine-generated 19-field record CAPTURE_MAPPING describes). It surfaces the
**identity-grade vs locator-only** distinction generically (CORE.md "code
binding discipline"; profile_si_ffs/UNSUPPORTED_SURFACES.md "No live registry
integration"):

  * identity-grade — the snapshot row carries a stable key -> CONFIRM (PASS);
  * locator-only / not-found — resolves only by a page locator, or not at all ->
    REVIEW (routes to review rather than pretending to verify);
  * absent / unavailable snapshot -> REFUSE (a governed refusal — never silent).

Scheme-agnostic: this module knows nothing about REGSR / GERK / FFSNaprave. The
scheme, key role, lookup surface, and the per-snapshot DATA lookup are all
parameters/injected — the SI bindings (P4) wrap their scheme-specific lookup
(e.g. ProductRegister decision-number lookup, D9) and pass it in. No scheme
literals are hardcoded here.

Note: the emitted trace DOES record the caller-supplied `scheme`/`key_field`
(in `selectionRationale`) and `profileRef`/`traceAuthorityRef`/
`traceJurisdictionRef` — that is the trace's purpose (auditable external-
verification provenance; a scheme-blind trace would be meaningless), and it is
the caller's value flowing through a generic template, not a hardcoded literal.
This mirrors the shipped demo `ExternalRegistryVerificationTrace`, whose
`selectionRationale` likewise names the register-specific key.
"""
from __future__ import annotations

from dataclasses import dataclass

from .context import current_reference_snapshot, mint, now_iso
from .problems import runtime_problem

# verdicts (the caller routes/refuses on these; not contract enums)
CONFIRM = "CONFIRM"   # identity-grade match — the binding is confirmable
REVIEW = "REVIEW"     # locator-only / not-found — route to review, never pretend
REFUSE = "REFUSE"     # snapshot unavailable — governed refusal

# lookup grades the injected scheme-specific lookup returns
IDENTITY = "IDENTITY"
LOCATOR = "LOCATOR"
NONE = "NONE"


@dataclass
class LookupResult:
    """The outcome of a scheme-specific lookup of a candidate in one snapshot's
    data. The resolver turns this into a verdict + trace; it never does the
    scheme-specific data access itself.

    grade: IDENTITY (a stable key was found), LOCATOR (matched only by a page
    locator — no stable key), or NONE (not found in an available snapshot).
    """
    grade: str
    candidate_count: int = 0
    external_id: str | None = None          # the stable key, when grade == IDENTITY
    status_observed: str = "UNKNOWN"        # ExternalRegistryVerificationTrace statusObserved enum
    dates_observed: dict | None = None      # extra datesObserved fields (accessedAt is added)
    discrepancies: list | None = None       # extra discrepancy entries


class ReferenceResolver:
    """Resolves a candidate against an in-force ReferenceSnapshot and emits an
    ExternalRegistryVerificationTrace. The trace is stored through the caller's
    transaction cursor (a governed write — the caller supplies a serialized_tx
    cursor per the G2 single-writer convention)."""

    def __init__(self, store):
        self.store = store

    def verify(self, cur, *, query_value: str, snapshot_prefix: str, lookup,
               profile_ref: str, authority_ref: str, jurisdiction_ref: str,
               scheme: str = "reference", key_field: str = "external-id",
               purpose: str = "OTHER", lookup_surface: str = "OTHER",
               external_id_role: str = "OTHER",
               review_reason_code: str = "IDENTITY_UNRESOLVED",
               high_consequence_use: str = "REQUIRE_REVIEW",
               as_of: str | None = None,
               created_by: str | None = None) -> dict:
        """Resolve `query_value` against the in-force snapshot of `snapshot_prefix`
        using the injected `lookup(snapshot_id, query_value) -> LookupResult`.

        Returns `{verdict, grade, trace, snapshotRef, problem}`. `verdict` is
        CONFIRM / REVIEW / REFUSE; `problem` is a registry-coded `RuntimeProblem`
        for REVIEW/REFUSE (None for CONFIRM) so the caller can route or refuse.
        The trace is always built and stored — a refusal is traceable, not silent.
        """
        accessed = now_iso()
        snapshot = current_reference_snapshot(self.store, snapshot_prefix, as_of=as_of)

        if snapshot is None:
            # No in-force snapshot at all -> a governed refusal. An
            # ExternalRegistryVerificationTrace is inherently a record AGAINST a
            # snapshot (snapshotRefs is required non-empty), so there is no trace
            # to emit here — the refusal is the RuntimeProblem the caller records
            # (gate log / review routing). We refuse rather than pretend to verify.
            return {"verdict": REFUSE, "grade": NONE, "trace": None, "snapshotRef": None,
                    "problem": runtime_problem(
                        "EVIDENCE_REFERENCE_UNAVAILABLE", "Reference snapshot unavailable",
                        f"no in-force {scheme} snapshot to verify {key_field} "
                        f"{query_value!r}; refusing rather than pretending to verify")}

        snapshot_id = snapshot["referenceSnapshotId"]
        result = lookup(snapshot_id, query_value)

        if result.grade == IDENTITY:
            verdict, final, downstream = CONFIRM, "PASS", "PASSPORTVIEW_ALLOWED"
            selected = {"externalIdRole": external_id_role}
            if result.external_id:
                selected["externalId"] = result.external_id
            rationale = (f"identity-grade match: {scheme} {key_field} "
                         f"{result.external_id or query_value!r} confirmed against {snapshot_id}")
            discrepancies = result.discrepancies or []
            problem = None
            hcu = "ALLOWED_WHEN_PASS"
        else:
            verdict, final, downstream = REVIEW, "REVIEW_REQUIRED", "PASSPORTVIEW_REQUIRE_REVIEW"
            selected = {"externalIdRole": "NONE"}
            locator = result.grade == LOCATOR
            rationale = (
                f"{scheme} candidate {query_value!r} "
                + ("matched only by page locator (no stable key)" if locator
                   else "was not found")
                + f" against {snapshot_id}; routes to review — a locator is not identity (D9)")
            discrepancies = result.discrepancies or [{
                "discrepancyType": "NAME_COLLISION" if locator else "OTHER",
                "severity": "REVIEW_REQUIRED",
                "note": "locator-only match — no stable key" if locator
                        else "candidate not found in the in-force snapshot"}]
            problem = runtime_problem(
                review_reason_code, "Reference identity not confirmable", rationale,
                severity="WARNING")
            hcu = high_consequence_use

        dates = {"accessedAt": accessed, **(result.dates_observed or {})}
        trace = self._build_trace(
            profile_ref=profile_ref, purpose=purpose, authority_ref=authority_ref,
            jurisdiction_ref=jurisdiction_ref, lookup_surface=lookup_surface,
            query_value=query_value, candidate_count=result.candidate_count,
            selected=selected, rationale=rationale,
            status_observed=result.status_observed, dates_observed=dates,
            snapshot_refs=[snapshot_id], registry_availability="AVAILABLE",
            discrepancies=discrepancies, final_outcome=final,
            high_consequence_use=hcu, downstream=downstream, created_by=created_by)
        self.store.insert_record(cur, trace)
        return {"verdict": verdict, "grade": result.grade, "trace": trace,
                "snapshotRef": snapshot_id, "problem": problem}

    def _build_trace(self, *, profile_ref, purpose, authority_ref, jurisdiction_ref,
                     lookup_surface, query_value, candidate_count, selected, rationale,
                     status_observed, dates_observed, snapshot_refs, registry_availability,
                     discrepancies, final_outcome, high_consequence_use, downstream,
                     created_by) -> dict:
        trace = {
            "schemaVersion": "ofarm.externalregistryverificationtrace.v0.1",
            "externalRegistryVerificationTraceId": mint("trace"),
            "profileRef": profile_ref,
            "verificationPurpose": purpose,
            "createdAt": dates_observed.get("accessedAt", now_iso()),
            "traceAuthorityRef": authority_ref,
            "traceJurisdictionRef": jurisdiction_ref,
            "lookupSurface": lookup_surface,
            "queryInputs": {"freeTextInput": query_value,
                            "sourceQueryRef": f"surface:{lookup_surface.lower()}"},
            "candidateCount": candidate_count,
            "selectedExternalId": selected,
            "selectionRationale": rationale,
            "statusObserved": status_observed,
            "datesObserved": dates_observed,
            "snapshotRefs": snapshot_refs,
            "registryAvailability": registry_availability,
            "discrepancies": discrepancies,
            "finalOutcome": final_outcome,
            "highConsequenceUse": high_consequence_use,
            "downstreamOutputDisposition": downstream,
        }
        if created_by:
            trace["createdByPartyRef"] = created_by
        return trace
