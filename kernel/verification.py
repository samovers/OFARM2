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

import types
from dataclasses import dataclass

from .context import current_reference_snapshot, mint, now_iso
from .problems import runtime_problem
from .runtime_bundle import RuntimeBundleError, require_store_runtime_bundle
from .store import Store

# verdicts (the caller routes/refuses on these; not contract enums)
CONFIRM = "CONFIRM"   # identity-grade match — the binding is confirmable
REVIEW = "REVIEW"     # locator-only / not-found — route to review, never pretend
REFUSE = "REFUSE"     # snapshot unavailable — governed refusal

# lookup grades the injected scheme-specific lookup returns
IDENTITY = "IDENTITY"
LOCATOR = "LOCATOR"
NONE = "NONE"


@dataclass(frozen=True, slots=True)
class LookupResult:
    """The outcome of a scheme-specific lookup of a candidate in one snapshot's
    data. The resolver turns this into a verdict + trace; it never does the
    scheme-specific data access itself.

    grade: IDENTITY (a stable key was found), LOCATOR (matched only by a page
    locator — no stable key), or NONE (not found in an available snapshot).

    Trust boundary (PR #11 review): the injected lookup is responsible for
    returning contract-valid enum values (`status_observed`, etc.) and a
    non-negative `candidate_count`. A P4 wrapper must normalise/validate its
    parser output here — it must NOT pass raw parser values straight through —
    or the trace insert will raise a ContractViolation rather than a governed
    refusal. This generic mechanism trusts the wrapper's output shape.
    """
    grade: str
    candidate_count: int = 0
    external_id: str | None = None          # the stable key, when grade == IDENTITY
    status_observed: str = "UNKNOWN"        # ExternalRegistryVerificationTrace statusObserved enum
    dates_observed: dict | None = None      # extra datesObserved fields (accessedAt is added)
    discrepancies: list | None = None       # extra discrepancy entries


def _exact_lookup_value(value):
    """Snapshot one exact JSON-shaped lookup value without behavioral subclasses."""
    if type(value) is dict:
        result = {}
        for key, item in value.items():
            if type(key) is not str:
                raise RuntimeBundleError(
                    "reference lookup mapping keys must be exact strings")
            result[key] = _exact_lookup_value(item)
        return result
    if type(value) is list:
        return [_exact_lookup_value(item) for item in value]
    if type(value) in {type(None), bool, int, float, str}:
        return value
    raise RuntimeBundleError(
        f"reference lookup returned behavioral value {type(value)!r}")


def _snapshot_lookup_result(value) -> LookupResult:
    if type(value) is not LookupResult:
        raise RuntimeBundleError(
            "reference lookup must return exact immutable LookupResult")
    if (type(value.grade) is not str
            or value.grade not in {IDENTITY, LOCATOR, NONE}
            or type(value.candidate_count) is not int
            or value.candidate_count < 0
            or (value.external_id is not None
                and type(value.external_id) is not str)
            or type(value.status_observed) is not str
            or (value.dates_observed is not None
                and type(value.dates_observed) is not dict)
            or (value.discrepancies is not None
                and type(value.discrepancies) is not list)):
        raise RuntimeBundleError(
            "reference lookup result has malformed exact field types")
    return LookupResult(
        grade=value.grade,
        candidate_count=value.candidate_count,
        external_id=value.external_id,
        status_observed=value.status_observed,
        dates_observed=(None if value.dates_observed is None
                        else _exact_lookup_value(value.dates_observed)),
        discrepancies=(None if value.discrepancies is None
                       else _exact_lookup_value(value.discrepancies)),
    )


class ReferenceResolver:
    """Resolves a candidate against an in-force ReferenceSnapshot and emits an
    ExternalRegistryVerificationTrace. The trace is stored through the caller's
    transaction cursor (a governed write — the caller supplies a serialized_tx
    cursor per the G2 single-writer convention)."""

    __slots__ = ("store",)

    def __setattr__(self, name, value):
        if name in self.__slots__ and hasattr(self, name):
            raise AttributeError(
                "ReferenceResolver runtime composition is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if name in self.__slots__:
            raise AttributeError(
                "ReferenceResolver runtime composition cannot be deleted")
        object.__delattr__(self, name)

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
               created_by: str | None = None,
               lookup_runtime_bundle=None) -> dict:
        """Resolve `query_value` against the in-force snapshot of `snapshot_prefix`
        using the injected `lookup(snapshot_id, query_value) -> LookupResult`.

        Returns `{verdict, grade, trace, snapshotRef, problem}`. `verdict` is
        CONFIRM / REVIEW / REFUSE; `problem` is a registry-coded `RuntimeProblem`
        for REVIEW/REFUSE (None for CONFIRM) so the caller can route or refuse.
        A trace is built and stored whenever a snapshot IS in force (CONFIRM and
        REVIEW); the absent-snapshot REFUSE emits no trace (the trace contract
        requires a real snapshot ref) — its refusal lives in the returned problem.
        """
        _RETAINED_REFERENCE_DISPATCH_GUARD(self, cur)
        string_inputs = (
            query_value, snapshot_prefix, profile_ref, authority_ref,
            jurisdiction_ref, scheme, key_field, purpose, lookup_surface,
            external_id_role, review_reason_code, high_consequence_use,
        )
        if (any(type(value) is not str for value in string_inputs)
                or type(lookup) is not types.FunctionType
                or (as_of is not None and type(as_of) is not str)
                or (created_by is not None and type(created_by) is not str)):
            Store._mark_transaction_integrity_violation(self.store)
            raise RuntimeBundleError(
                "ReferenceResolver inputs must be exact retained primitives")
        require_store_runtime_bundle(
            self.store, lookup_runtime_bundle, "ReferenceResolver lookup")
        accessed = now_iso()
        snapshot = current_reference_snapshot(self.store, snapshot_prefix, as_of=as_of)

        if snapshot is None:
            # No in-force snapshot at all -> a governed refusal. An
            # ExternalRegistryVerificationTrace is inherently a record AGAINST a
            # snapshot (snapshotRefs is required non-empty), so there is no trace
            # to emit here — the refusal is the RuntimeProblem the caller records
            # (gate log / review routing). We refuse rather than pretend to verify.
            response = {
                "verdict": REFUSE, "grade": NONE, "trace": None,
                "snapshotRef": None,
                "problem": runtime_problem(
                    "EVIDENCE_REFERENCE_UNAVAILABLE",
                    "Reference snapshot unavailable",
                    f"no in-force {scheme} snapshot to verify {key_field} "
                    f"{query_value!r}; refusing rather than pretending to verify"),
            }
            _RETAINED_REFERENCE_DISPATCH_GUARD(self, cur)
            return response

        snapshot_id = snapshot["referenceSnapshotId"]
        selected_reference = self.store.runtime_bundle.selected_reference(snapshot_id)
        if selected_reference.source_byte_status != "LOCKED":
            response = {
                "verdict": REFUSE,
                "grade": NONE,
                "trace": None,
                "snapshotRef": snapshot_id,
                "problem": runtime_problem(
                    "EVIDENCE_REFERENCE_UNAVAILABLE",
                    "Reference source bytes unavailable",
                    f"{scheme} snapshot {snapshot_id} is provenance metadata only; "
                    f"retained source/data bytes are unavailable, so {key_field} "
                    f"{query_value!r} cannot be resolved"),
            }
            _RETAINED_REFERENCE_DISPATCH_GUARD(self, cur)
            return response
        try:
            raw_result = lookup(snapshot_id, query_value)
        finally:
            _RETAINED_REFERENCE_DISPATCH_GUARD(self, cur)
        try:
            result = _RETAINED_SNAPSHOT_LOOKUP_RESULT(raw_result)
        except BaseException:
            Store._mark_transaction_integrity_violation(self.store)
            raise
        _RETAINED_REFERENCE_DISPATCH_GUARD(self, cur)

        # Identity-grade REQUIRES a stable external key. A lookup that claims
        # grade IDENTITY but carries no externalId is not identity-grade — it
        # must not CONFIRM/PASS (PR #11 review). It routes to review alongside
        # locator-only and not-found: only a present stable key confirms.
        has_key = bool(result.external_id and result.external_id.strip())

        if result.grade == IDENTITY and has_key:
            verdict, final, downstream = CONFIRM, "PASS", "PASSPORTVIEW_ALLOWED"
            selected = {"externalId": result.external_id, "externalIdRole": external_id_role}
            rationale = (f"identity-grade match: {scheme} {key_field} "
                         f"{result.external_id!r} confirmed against {snapshot_id}")
            discrepancies = result.discrepancies or []
            problem = None
            hcu = "ALLOWED_WHEN_PASS"
        else:
            verdict, final, downstream = REVIEW, "REVIEW_REQUIRED", "PASSPORTVIEW_REQUIRE_REVIEW"
            selected = {"externalIdRole": "NONE"}
            if result.grade == IDENTITY:      # claimed identity-grade but no stable key
                detail, disc_type = "claimed identity-grade but carried no stable key", "OTHER"
            elif result.grade == LOCATOR:
                detail, disc_type = "matched only by a page locator (no stable key)", "NAME_COLLISION"
            else:
                detail, disc_type = "was not found in the in-force snapshot", "OTHER"
            rationale = (f"{scheme} candidate {query_value!r} {detail} against "
                         f"{snapshot_id}; routes to review — not identity-grade (D9)")
            discrepancies = result.discrepancies or [{
                "discrepancyType": disc_type, "severity": "REVIEW_REQUIRED", "note": detail}]
            problem = runtime_problem(
                review_reason_code, "Reference identity not confirmable", rationale,
                severity="WARNING")
            hcu = high_consequence_use

        dates = {"accessedAt": accessed, **(result.dates_observed or {})}
        try:
            trace = _RETAINED_REFERENCE_BUILD_TRACE(
                self,
                profile_ref=profile_ref, purpose=purpose,
                authority_ref=authority_ref,
                jurisdiction_ref=jurisdiction_ref,
                lookup_surface=lookup_surface,
                query_value=query_value,
                candidate_count=result.candidate_count,
                selected=selected, rationale=rationale,
                status_observed=result.status_observed,
                dates_observed=dates,
                snapshot_refs=[snapshot_id],
                registry_availability="AVAILABLE",
                discrepancies=discrepancies, final_outcome=final,
                high_consequence_use=hcu, downstream=downstream,
                created_by=created_by)
            _RETAINED_REFERENCE_DISPATCH_GUARD(self, cur)
            _RETAINED_REFERENCE_STORE_INSERT(self.store, cur, trace)
        except BaseException:
            Store._mark_transaction_integrity_violation(self.store)
            raise
        _RETAINED_REFERENCE_DISPATCH_GUARD(self, cur)
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


_RETAINED_REFERENCE_VERIFY = ReferenceResolver.verify
_RETAINED_REFERENCE_VERIFY_CODE = _RETAINED_REFERENCE_VERIFY.__code__
_RETAINED_REFERENCE_BUILD_TRACE = ReferenceResolver._build_trace
_RETAINED_REFERENCE_BUILD_TRACE_CODE = \
    _RETAINED_REFERENCE_BUILD_TRACE.__code__
_RETAINED_SNAPSHOT_LOOKUP_RESULT = _snapshot_lookup_result
_RETAINED_SNAPSHOT_LOOKUP_RESULT_CODE = \
    _RETAINED_SNAPSHOT_LOOKUP_RESULT.__code__
_RETAINED_EXACT_LOOKUP_VALUE = _exact_lookup_value
_RETAINED_EXACT_LOOKUP_VALUE_CODE = _RETAINED_EXACT_LOOKUP_VALUE.__code__
_RETAINED_REFERENCE_STORE_INSERT = Store.insert_record
_RETAINED_REFERENCE_STORE_INSERT_CODE = \
    _RETAINED_REFERENCE_STORE_INSERT.__code__
_RETAINED_REFERENCE_STORE_POSTURE = Store._require_transaction_python_posture
_RETAINED_REFERENCE_STORE_POSTURE_CODE = \
    _RETAINED_REFERENCE_STORE_POSTURE.__code__


def _require_reference_resolver_dispatch(resolver, cur) -> None:
    store = getattr(resolver, "store", None)
    try:
        if (type(resolver) is not ReferenceResolver
                or type(store) is not Store
                or globals().get("_require_reference_resolver_dispatch") is not
                _RETAINED_REFERENCE_DISPATCH_GUARD
                or _RETAINED_REFERENCE_DISPATCH_GUARD.__code__ is not
                _RETAINED_REFERENCE_DISPATCH_GUARD_CODE
                or vars(ReferenceResolver).get("verify") is not
                _RETAINED_REFERENCE_VERIFY
                or _RETAINED_REFERENCE_VERIFY.__code__ is not
                _RETAINED_REFERENCE_VERIFY_CODE
                or vars(ReferenceResolver).get("_build_trace") is not
                _RETAINED_REFERENCE_BUILD_TRACE
                or _RETAINED_REFERENCE_BUILD_TRACE.__code__ is not
                _RETAINED_REFERENCE_BUILD_TRACE_CODE
                or globals().get("_snapshot_lookup_result") is not
                _RETAINED_SNAPSHOT_LOOKUP_RESULT
                or _RETAINED_SNAPSHOT_LOOKUP_RESULT.__code__ is not
                _RETAINED_SNAPSHOT_LOOKUP_RESULT_CODE
                or globals().get("_exact_lookup_value") is not
                _RETAINED_EXACT_LOOKUP_VALUE
                or _RETAINED_EXACT_LOOKUP_VALUE.__code__ is not
                _RETAINED_EXACT_LOOKUP_VALUE_CODE
                or vars(Store).get("insert_record") is not
                _RETAINED_REFERENCE_STORE_INSERT
                or _RETAINED_REFERENCE_STORE_INSERT.__code__ is not
                _RETAINED_REFERENCE_STORE_INSERT_CODE
                or vars(Store).get("_require_transaction_python_posture") is not
                _RETAINED_REFERENCE_STORE_POSTURE
                or _RETAINED_REFERENCE_STORE_POSTURE.__code__ is not
                _RETAINED_REFERENCE_STORE_POSTURE_CODE):
            raise RuntimeBundleError(
                "ReferenceResolver retained dispatch changed")
        _RETAINED_REFERENCE_STORE_POSTURE(store)
        Store._require_active_governed_cursor(store, cur)
    except BaseException:
        if type(store) is Store:
            Store._mark_transaction_integrity_violation(store)
        raise


_RETAINED_REFERENCE_DISPATCH_GUARD = _require_reference_resolver_dispatch
_RETAINED_REFERENCE_DISPATCH_GUARD_CODE = \
    _RETAINED_REFERENCE_DISPATCH_GUARD.__code__
