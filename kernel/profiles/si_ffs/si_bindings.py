"""SI bindings (M2 P4) — package content binding the five SI schemes to committed
identities via `AgronomicIdentityBinding`, resolved through the GENERIC G3
`ReferenceResolver`. Each role's resolver injects a NORMALISED lookup into
`verification.ReferenceResolver.verify` (contract-valid `status_observed` /
`external_id_role` / non-negative `candidate_count` — never raw parser values, or
the trace insert raises a ContractViolation instead of a governed refusal, PR #11
review) and maps the verdict to an `AgronomicIdentityBinding` state:

  * REGSR product authorisation (AppliedResource) — IDENTITY-grade: the stevilka
    odlocbe is a stable authorisation key (D9). CONFIRM -> VERIFIED / EXACT /
    maySupportPromotion; not-found / ambiguous -> REVIEW -> PROVISIONAL / UNRESOLVED.
  * GERK parcel (Field) and FFSNaprave sticker (Equipment) — LOCATOR-only: the
    layer / register confirms the code EXISTS but cannot verify the field<->parcel
    or equipment<->inspection BINDING (no owner link — the KMG<->GERK / sprayer<->
    owner relation is personal data, never in the open data). So they route to
    REVIEW -> PROVISIONAL / LOCAL_ONLY, never silently identity-grade.
  * KMG-MID holding (Farm) and FFS-IZKAZNICA operator card — NO register exists:
    the identifier is captured EVIDENCE, never verified identity (D6, CORE code-
    binding discipline). -> UNRESOLVED + advisory -> PROVISIONAL / UNRESOLVED.

A binding is NEVER VERIFIED without an identity-grade G3 CONFIRM; an unresolved /
locator binding is committable as a draft but its promotionBoundary requires review
(maySupportPromotion False, highConsequenceUse REVIEW_REQUIRED) — free text never
silently becomes compliance identity. The evidence FLOOR that routes such claims
(P5) and current-compliance are out of scope. ALL SI specifics live HERE; the
generic resolver / validators carry no per-scheme branch.
"""
from __future__ import annotations

from ... import config
from ...context import (
    GERK_SNAPSHOT_PREFIX,
    ProductRegister,
    SIReferenceBindings,
    mint,
    now_iso,
)
from ...problems import runtime_problem
from ...verification import (CONFIRM, LOCATOR, NONE, REVIEW, LookupResult,
                             ReferenceResolver)
from . import regsr_adapter as regsr
from .ffsnaprave_adapter import (FFSNAPRAVE_AUTHORITY_REF, FFSNAPRAVE_SCHEME,
                                 FFSNAPRAVE_SNAPSHOT_PREFIX, VALIDITY_FIELD)
from .gerk_adapter import GERK_AUTHORITY_REF, GERK_SCHEME

# the profile standardRefs (profile_si_ffs/OFARM_AgronomicCodeBindingProfile_si_ffs_v0_1.json)
REGSR_SCHEME_REF = "scheme:si.uvhvvr.ffs-reg"
GERK_SCHEME_REF = "scheme:si.gerk-pid"
FFSNAPRAVE_SCHEME_REF = "scheme:si.ffs-naprave"
KMG_MID_SCHEME_REF = "scheme:si.kmg-mid"
FFS_IZKAZNICA_SCHEME_REF = "scheme:si.ffs-izkaznica"
SI_JURISDICTION_REF = "jurisdiction:SI"
MKGP_REF = "party:si.mkgp"
UVHVVR_REF = "party:si.uvhvvr"


def _evidence_ok(store, ref) -> bool:
    """The caller-supplied evidence ref must resolve to an actual EvidenceRecord —
    a binding may not cite fabricated captured evidence (PR #15 hostile B2). A
    generated verification-trace ref is separately trustworthy (G3 inserted it)."""
    rec = store.get_record(ref)
    return rec is not None and rec["record_kind"] == "ofarm.evidencerecord.v0.1"


def _evidence_refused(scheme, evidence_ref) -> dict:
    return {"verdict": "REFUSE", "grade": NONE, "binding": None, "trace": None,
            "problem": runtime_problem(
                "EVIDENCE_REFERENCE_UNAVAILABLE", "Binding evidence unresolved",
                f"{scheme} binding evidence_ref {evidence_ref!r} is not an EvidenceRecord; "
                "a binding may not cite fabricated captured evidence"),
            "advisory": None}


def _scheme_version(store, snapshot_ref):
    """The reference-snapshot vintage a binding was resolved against — recorded as
    externalScheme.schemeVersion (the profile requires it for high-consequence
    bindings, PR #15 hostile B1). None when no snapshot is in force."""
    if not snapshot_ref:
        return None
    rec = store.get_record(snapshot_ref)
    return rec["payload"].get("canonicalVersionLabel") if rec else None


def _binding(*, role, subject_type, subject_ref, scheme_ref, scheme_name, scheme_role,
             issuer, captured_label, state, mapping, evidence_refs, created_by,
             value_extra=None, snapshot_refs=None, scheme_version=None, may_promote, hcu) -> dict:
    """Build a contract-valid `AgronomicIdentityBinding` reflecting a resolution
    outcome. `mustNotPromoteTo OFARM_CORE_MEANING` always — a profile binding never
    mutates Core meaning (D6, packs-constrain-bindings-only)."""
    binding_value = {"capturedLabel": captured_label, "mappingRelation": mapping}
    if value_extra:
        binding_value.update(value_extra)
    external_scheme = {"schemeRef": scheme_ref, "schemeName": scheme_name,
                       "schemeRole": scheme_role, "issuerRef": issuer, "jurisdiction": "SI"}
    if scheme_version:
        external_scheme["schemeVersion"] = scheme_version
    binding = {
        "schemaVersion": "ofarm.agronomicidentitybinding.v0.1",
        "agronomicIdentityBindingId": mint("binding"),
        "bindingRole": role,
        "bindingState": state,
        "createdAt": now_iso(),
        "createdByPartyRef": created_by,
        "localSubject": {"subjectType": subject_type, "subjectRef": subject_ref},
        "externalScheme": external_scheme,
        "bindingValue": binding_value,
        "evidenceRefs": list(evidence_refs),
        "promotionBoundary": {"highConsequenceUse": hcu,
                              "maySupportPromotion": may_promote,
                              "mustNotPromoteTo": ["OFARM_CORE_MEANING"]},
    }
    if snapshot_refs:
        binding["referenceSnapshotRefs"] = list(snapshot_refs)
    return binding


def _locator_lookup(find):
    """A G3 lookup that grades a hit as LOCATOR (the code EXISTS in the snapshot but
    the local-subject BINDING is not owner-verifiable) and a miss as NONE — both
    route to REVIEW. Normalises to contract-valid enums (status UNKNOWN for a found
    locator: the layer/register carries no authorisation status for the subject)."""
    def lookup(snapshot_id, query_value) -> LookupResult:
        if find(snapshot_id, query_value) is None:
            return LookupResult(grade=NONE, candidate_count=0, status_observed="NOT_FOUND")
        return LookupResult(grade=LOCATOR, candidate_count=1, status_observed="UNKNOWN")
    return lookup


# ---------------------------------------------------------------------------
# REGSR — AppliedResource product-authorisation identity (IDENTITY-grade, D9)
# ---------------------------------------------------------------------------

def resolve_product_authorisation(store, cur, decision_number, subject_ref, *,
                                  created_by, evidence_ref, issued=None,
                                  valid_until=None, as_of=None) -> dict:
    if not _evidence_ok(store, evidence_ref):
        return _evidence_refused(REGSR_SCHEME_REF, evidence_ref)
    product_register = ProductRegister(
        SIReferenceBindings.from_descriptor(store.active_descriptor)
    )
    product_register.load_from_store(store)
    res = regsr.verify_product_authorisation(
        store, cur, product_register, decision_number, issued=issued,
        valid_until=valid_until, as_of=as_of, created_by=created_by)
    confirmed = res["verdict"] == CONFIRM
    trace = res.get("trace")
    snapshot_ref = res.get("snapshotRef")
    # cite the verification trace when one was produced (CONFIRM / REVIEW), plus the
    # captured-identifier evidence — so a no-in-force-snapshot REFUSE still yields a
    # contract-valid UNRESOLVED binding (committable as draft), never an empty evidence set.
    evidence_refs = ([trace["externalRegistryVerificationTraceId"]] if trace else []) + [evidence_ref]
    binding = _binding(
        role="REGULATORY_AUTHORISATION", subject_type="PRODUCT_OR_INPUT",
        subject_ref=subject_ref, scheme_ref=REGSR_SCHEME_REF,
        scheme_name="UVHVVR Seznam registriranih FFS (REGSR)", scheme_role="CODE_BINDING",
        issuer=UVHVVR_REF, captured_label=decision_number,
        state="VERIFIED" if confirmed else "PROVISIONAL",
        mapping="EXACT" if confirmed else "UNRESOLVED",
        value_extra={"registrationRef": decision_number}, created_by=created_by,
        evidence_refs=evidence_refs, snapshot_refs=[snapshot_ref] if snapshot_ref else None,
        scheme_version=_scheme_version(store, snapshot_ref), may_promote=confirmed,
        hcu="ALLOWED_WHEN_PROFILE_AND_EVIDENCE_PASS" if confirmed else "REVIEW_REQUIRED")
    return {"verdict": res["verdict"], "grade": res["grade"], "binding": binding,
            "trace": trace, "problem": res.get("problem"), "advisory": None}


# ---------------------------------------------------------------------------
# GERK — Field parcel (LOCATOR-only: PID existence, not field<->parcel binding)
# ---------------------------------------------------------------------------

def resolve_parcel(store, cur, gerk_layer, gerk_pid, subject_ref, *, created_by,
                   evidence_ref, as_of=None) -> dict:
    if not _evidence_ok(store, evidence_ref):
        return _evidence_refused(GERK_SCHEME_REF, evidence_ref)
    res = ReferenceResolver(store).verify(
        cur, query_value=gerk_pid, snapshot_prefix=GERK_SNAPSHOT_PREFIX,
        lookup=_locator_lookup(gerk_layer.lookup),
        profile_ref=config.CODE_BINDING_PROFILE_REF, authority_ref=GERK_AUTHORITY_REF,
        jurisdiction_ref=SI_JURISDICTION_REF, scheme=GERK_SCHEME, key_field="gerk-pid",
        purpose="OTHER", lookup_surface="OTHER", external_id_role="OTHER",
        review_reason_code="IDENTITY_UNRESOLVED", as_of=as_of, created_by=created_by)
    found = res["grade"] == LOCATOR
    trace = res.get("trace")
    binding = _binding(
        role="OTHER", subject_type="OTHER", subject_ref=subject_ref,
        scheme_ref=GERK_SCHEME_REF, scheme_name="GERK-PID parcel identifier",
        scheme_role="LOCAL_PROFILE_SCHEME", issuer=MKGP_REF, captured_label=gerk_pid,
        state="PROVISIONAL", mapping="LOCAL_ONLY" if found else "UNRESOLVED",
        value_extra={"code": gerk_pid}, created_by=created_by,
        evidence_refs=([trace["externalRegistryVerificationTraceId"]] if trace else []) + [evidence_ref],
        snapshot_refs=[res["snapshotRef"]] if res.get("snapshotRef") else None,
        scheme_version=_scheme_version(store, res.get("snapshotRef")),
        may_promote=False, hcu="REVIEW_REQUIRED")
    return {"verdict": res["verdict"], "grade": res["grade"], "binding": binding,
            "trace": trace, "problem": res.get("problem"),
            "advisory": "GERK-PID existence is locator-only; the field<->parcel binding "
                        "is the farmer's claim (no owner link in the open layer) — review"}


# ---------------------------------------------------------------------------
# FFSNaprave — Equipment sticker (LOCATOR-only: inspection existence, not binding)
# ---------------------------------------------------------------------------

def _ffsnaprave_lookup(register, validity):
    """A G3 lookup that resolves the D9-style COMPOSITE key StevilkaZnaka +
    VeljavnostZnaka (never the sticker alone — same sticker, different validity is a
    different inspection cycle, P3). On a hit it records the matched record's
    VeljavnostZnaka in datesObserved.statusEffectiveUntil so the composite key is
    explicit in the trace (PR #15 B2). Locator-only (existence, not owner-binding)."""
    def lookup(snapshot_id, sticker) -> LookupResult:
        rec = register.match(snapshot_id, sticker, validity)
        if rec is not None:
            v = rec.get(VALIDITY_FIELD)
            return LookupResult(grade=LOCATOR, candidate_count=1, status_observed="UNKNOWN",
                                dates_observed={"statusEffectiveUntil": f"{v}T00:00:00Z"} if v else None)
        # no exact match: distinguish ABSENT from AMBIGUOUS (sticker present with
        # multiple validity windows and no validity supplied to disambiguate) — the
        # latter is "exists but supply VeljavnostZnaka", not "not in the snapshot"
        # (PR #15 hostile B3).
        windows = register.validity_windows(snapshot_id, sticker)
        if validity is None and len(windows) > 1:
            return LookupResult(
                grade=NONE, candidate_count=len(windows), status_observed="MULTIPLE_CANDIDATES",
                discrepancies=[{"discrepancyType": "OTHER", "severity": "REVIEW_REQUIRED",
                                "note": f"sticker {sticker} has {len(windows)} validity windows; "
                                        "supply VeljavnostZnaka to disambiguate the composite key"}])
        return LookupResult(grade=NONE, candidate_count=0, status_observed="NOT_FOUND")
    return lookup


def resolve_equipment(store, cur, ffsnaprave_register, sticker_number, subject_ref, *,
                      created_by, evidence_ref, validity=None, as_of=None) -> dict:
    if not _evidence_ok(store, evidence_ref):
        return _evidence_refused(FFSNAPRAVE_SCHEME_REF, evidence_ref)
    res = ReferenceResolver(store).verify(
        cur, query_value=sticker_number, snapshot_prefix=FFSNAPRAVE_SNAPSHOT_PREFIX,
        lookup=_ffsnaprave_lookup(ffsnaprave_register, validity),
        profile_ref=config.CODE_BINDING_PROFILE_REF, authority_ref=FFSNAPRAVE_AUTHORITY_REF,
        jurisdiction_ref=SI_JURISDICTION_REF, scheme=FFSNAPRAVE_SCHEME,
        key_field="stevilka-znaka", purpose="OTHER", lookup_surface="OTHER",
        external_id_role="OTHER", review_reason_code="IDENTITY_UNRESOLVED",
        as_of=as_of, created_by=created_by)
    found = res["grade"] == LOCATOR
    trace = res.get("trace")
    # the RESOLVED validity (the matched record's VeljavnostZnaka) rides the trace's
    # datesObserved; record the full composite key in the binding too (PR #15 B2) —
    # never just the sticker number.
    resolved_validity = ((trace or {}).get("datesObserved") or {}).get("statusEffectiveUntil")
    binding = _binding(
        role="OTHER", subject_type="OTHER", subject_ref=subject_ref,
        scheme_ref=FFSNAPRAVE_SCHEME_REF, scheme_name="UVHVVR sprayer-inspection register",
        scheme_role="CODE_BINDING", issuer=UVHVVR_REF, captured_label=sticker_number,
        state="PROVISIONAL", mapping="LOCAL_ONLY" if found else "UNRESOLVED",
        value_extra={"code": sticker_number, "notes":
                     f"D9-style composite key: StevilkaZnaka {sticker_number}" +
                     (f" + VeljavnostZnaka {validity or resolved_validity}"
                      if (validity or resolved_validity) else " (VeljavnostZnaka unresolved)")},
        created_by=created_by,
        evidence_refs=([trace["externalRegistryVerificationTraceId"]] if trace else []) + [evidence_ref],
        snapshot_refs=[res["snapshotRef"]] if res.get("snapshotRef") else None,
        scheme_version=_scheme_version(store, res.get("snapshotRef")),
        may_promote=False, hcu="REVIEW_REQUIRED")
    return {"verdict": res["verdict"], "grade": res["grade"], "binding": binding,
            "trace": trace, "problem": res.get("problem"), "resolvedValidity": resolved_validity,
            "advisory": "sprayer-inspection existence is locator-only; the equipment<->"
                        "inspection binding is the farmer's sticker claim — review"}


# ---------------------------------------------------------------------------
# KMG-MID (Farm holding) & FFS-IZKAZNICA (operator) — NO register: UNRESOLVED
# ---------------------------------------------------------------------------

def _unresolved(store, *, scheme, role_scheme_ref, scheme_name, issuer, subject_ref,
                captured_label, evidence_ref, created_by, advisory) -> dict:
    """A captured identifier with NO lookup register: held as evidence, never
    verified identity (D6). UNRESOLVED + advisory; committable as draft, promotion
    requires review. The captured evidence_ref MUST be a real EvidenceRecord — for
    these schemes it is the ONLY evidence, so a fabricated ref must yield no binding
    (PR #15 hostile B2)."""
    if not _evidence_ok(store, evidence_ref):
        return _evidence_refused(role_scheme_ref, evidence_ref)
    binding = _binding(
        role="OTHER", subject_type="OTHER", subject_ref=subject_ref,
        scheme_ref=role_scheme_ref, scheme_name=scheme_name,
        scheme_role="LOCAL_PROFILE_SCHEME", issuer=issuer, captured_label=captured_label,
        state="PROVISIONAL", mapping="UNRESOLVED", value_extra={"code": captured_label},
        created_by=created_by, evidence_refs=[evidence_ref], may_promote=False,
        hcu="REVIEW_REQUIRED")
    return {"verdict": "UNRESOLVED", "grade": NONE, "binding": binding, "trace": None,
            "problem": None, "advisory": advisory}


def resolve_holding(store, kmg_mid, subject_ref, *, evidence_ref, created_by) -> dict:
    """Farm holding identifier (SI:KMG-MID). No public KMG-MID lookup register
    exists; the holding number is captured at onboarding as evidence (D6)."""
    return _unresolved(
        store, scheme="KMG-MID", role_scheme_ref=KMG_MID_SCHEME_REF,
        scheme_name="KMG-MID holding number", issuer=MKGP_REF, subject_ref=subject_ref,
        captured_label=kmg_mid, evidence_ref=evidence_ref, created_by=created_by,
        advisory="no KMG-MID lookup register exists; the holding number is captured "
                 "evidence, not verified identity (D6) — UNRESOLVED, advisory")


def resolve_operator(store, izkaznica_number, subject_ref, *, evidence_ref, created_by) -> dict:
    """Operator training-card identifier (SI:FFS-IZKAZNICA). No public lookup
    register; the card number + card photo are captured evidence (D6)."""
    return _unresolved(
        store, scheme="FFS-IZKAZNICA", role_scheme_ref=FFS_IZKAZNICA_SCHEME_REF,
        scheme_name="FFS training-card number", issuer=UVHVVR_REF, subject_ref=subject_ref,
        captured_label=izkaznica_number, evidence_ref=evidence_ref, created_by=created_by,
        advisory="no FFS-IZKAZNICA lookup register exists; the card number is captured "
                 "evidence, not verified identity (D6) — UNRESOLVED, advisory")
