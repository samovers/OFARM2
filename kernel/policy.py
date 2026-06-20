"""Runtime policy as data (issue #3): every commit-class, promotion, freshness,
and routing rule the gates enforce lives HERE as a declarative table or a
small pure function — never embedded in a procedural branch. The gate stages
consume these; changing runtime policy means changing a table in this file,
in one reviewable place.

None of this is OFARM law: these tables BIND the implementation to the
accepted law (Authority Action Matrix, commit matrix, D-decisions, the
Current-State RFC's freshness semantics). The law itself stays in
reference/ and DECISIONS.md.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# commit-class vocabulary bindings
# ---------------------------------------------------------------------------

COMMIT_CLASS_TO_FAMILY = {
    "NOTE": "ObservationEvent",
    "OBSERVATION_ASSERTION": "ObservationEvent",
    "HYPOTHESIS_ASSERTION": "ObservationEvent",
    "STRUCTURE_ASSERTION": "StructureEvent",
    "OPERATION_CLAIM": "InterventionEvent",
    "EVIDENCE_RECORD": "EvidenceEvent",
    "COMPLIANCE_ASSERTION": "GovernanceEvent",
    "GOVERNANCE_DECISION": "GovernanceEvent",
    "ADVISORY_OUTPUT": "GovernanceEvent",
}

# commitClass is ingress vocabulary; authority is evaluated in the accepted
# Authority Action Matrix vocabulary (reference/rfcs/OFARM_Authority_Action_
# Matrix_v0_1.md) — grants, traces, manifests, and evidence all speak the
# accepted names, never a parallel runtime dialect. ADVISORY_OUTPUT maps to
# the observe/report capture class: the matrix defines no advisory-output
# action, and advisory outputs never promote (least-authority fit).
COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS = {
    "NOTE": "OBSERVE_CREATE_OBSERVATION",
    "OBSERVATION_ASSERTION": "OBSERVE_CREATE_OBSERVATION",
    "HYPOTHESIS_ASSERTION": "OBSERVE_CREATE_OBSERVATION",
    "STRUCTURE_ASSERTION": "ASSERT_STRUCTURE",
    "OPERATION_CLAIM": "ASSERT_OPERATION_CLAIM",
    "EVIDENCE_RECORD": "OBSERVE_ATTACH_EVIDENCE",
    "COMPLIANCE_ASSERTION": "ASSERT_COMPLIANCE",
    # GOVERNANCE_DECISION's effective authority action is selected per-commit by
    # the review verb (REVIEW_ACTION_AUTHORITY, G5) at the AuthorityGate; this
    # entry is the table-closure default + manifest/grounding anchor for the class.
    "GOVERNANCE_DECISION": "REVIEW_ACCEPT",
    "ADVISORY_OUTPUT": "OBSERVE_CREATE_OBSERVATION",
}

COMMIT_CLASS_TO_ASSERTION_TYPE = {
    "OBSERVATION_ASSERTION": "OBSERVATION_ASSERTION",
    "STRUCTURE_ASSERTION": "STRUCTURE_ASSERTION",
    "OPERATION_CLAIM": "OPERATION_CLAIM_ASSERTION",
    "COMPLIANCE_ASSERTION": "COMPLIANCE_ASSERTION",
}

COMMIT_CLASS_TO_PROMOTION_TARGET = {
    "OPERATION_CLAIM": "ACCEPTED_EXECUTED_INTERVENTION_CONSEQUENCE",
    "STRUCTURE_ASSERTION": "ACCEPTED_STRUCTURAL_STATE",
    "OBSERVATION_ASSERTION": "ACCEPTED_OBSERVATION_OCCURRENCE_STATE",
    "COMPLIANCE_ASSERTION": "COMPLIANCE_FACT",
}

PROMOTION_TARGET_TO_CONSEQUENCE_TYPE = {
    "ACCEPTED_EXECUTED_INTERVENTION_CONSEQUENCE": "EXECUTION_CONFIRMED",
    "ACCEPTED_STRUCTURAL_STATE": "STATE_CHANGE_ACCEPTED",
    "ACCEPTED_OBSERVATION_OCCURRENCE_STATE": "STATE_CHANGE_ACCEPTED",
    "COMPLIANCE_FACT": "COMPLIANCE_STATUS_ACCEPTED",
}

# what a queued assertion promotes to when a reviewer accepts it via a
# GOVERNANCE_DECISION commit (the reviewer's own governed act)
ACCEPTANCE_BY_ASSERTION_TYPE = {
    "OPERATION_CLAIM_ASSERTION": ("ACCEPTED_EXECUTED_INTERVENTION_CONSEQUENCE",
                                  "EXECUTION_CONFIRMED"),
    "COMPLIANCE_ASSERTION": ("COMPLIANCE_FACT", "COMPLIANCE_STATUS_ACCEPTED"),
    "STRUCTURE_ASSERTION": ("ACCEPTED_STRUCTURAL_STATE", "STATE_CHANGE_ACCEPTED"),
    "OBSERVATION_ASSERTION": ("ACCEPTED_OBSERVATION_OCCURRENCE_STATE",
                              "STATE_CHANGE_ACCEPTED"),
}

# action classes the runtime evaluates OUTSIDE the commit-class map:
# review acceptance, publication approval/filing, and read access. One
# home consumed by the manifest builder, its grounding check, and the
# law-binding test — never re-typed per call site. (The literals at the
# evaluate() call sites themselves are the things these ground.)
NON_COMMIT_ACTION_CLASSES = frozenset({
    "REVIEW_ACCEPT",
    "REVIEW_REJECT_OR_CONTEST",
    "OUTPUT_APPROVE_DOCUMENT_ASSEMBLY",
    "OUTPUT_FILE_SUBMISSION_ASSEMBLY",
    "RECEIVE_READ_DATA",
})

# A review decision (M2 G5) is the normalized (reviewAction, decisionOutcomeState)
# pair (D20 / docs/REVIEW_DISPUTE_SEMANTICS.md §3.1). reviewAction selects the
# AUTHORITY action — REJECT/CONTEST share REVIEW_REJECT_OR_CONTEST, distinct from
# REVIEW_ACCEPT (Authority Action Matrix; NO_INHERIT, so holding one never confers
# the other). An unrecognized verb maps to no action and the AuthorityGate
# default-denies (Kernel rule 2). REVIEW_SUPERSEDE / REVIEW_REQUEST are not wired
# in G5 and so are absent here (they refuse the same way).
REVIEW_ACTION_AUTHORITY = {
    "REVIEW_ACCEPT": "REVIEW_ACCEPT",
    "REVIEW_REJECT_OR_CONTEST": "REVIEW_REJECT_OR_CONTEST",
}


class _Absent:
    """Sentinel: a review-decision field was NOT present in the submission, as
    distinct from present-but-null. Absence carries the legacy default; a present
    value (even null) is taken verbatim and the fail-closed matrix judges it."""
    __slots__ = ()
    def __repr__(self):  # noqa: E301 - clean repr for refusal detail text
        return "<absent>"


ABSENT = _Absent()


def review_branch(review_action, decision_outcome) -> str | None:
    """The emission branch for a normalized review-decision pair, or None to
    refuse FAIL-CLOSED (docs/REVIEW_DISPUTE_SEMANTICS.md §3.1). Returns 'ACCEPT'
    or 'REJECT'. There is NO truthiness default: an *absent* field arrives as the
    ABSENT sentinel (IngressNormalizer), distinct from present-null. So a present
    falsey / non-string / unrecognized reviewAction OR decisionOutcomeState
    matches no arm and returns None (refuse), never coerced to accept
    (PR #18 review B1 + decisionOutcomeState blocker). REVIEW_ACCEPT accepts only
    when the outcome is ABSENT or the exact string 'ACCEPTED'; present null / ''
    / false / number / list / unsupported string refuse. REVIEW_REJECT_OR_CONTEST
    splits on the outcome: 'REJECTED' -> 'REJECT' (G5-2), 'CONTESTED' -> 'CONTEST'
    (G5-4)."""
    if review_action == "REVIEW_ACCEPT" and decision_outcome in (ABSENT, "ACCEPTED"):
        return "ACCEPT"
    if review_action == "REVIEW_REJECT_OR_CONTEST" and decision_outcome == "REJECTED":
        return "REJECT"
    if review_action == "REVIEW_REJECT_OR_CONTEST" and decision_outcome == "CONTESTED":
        return "CONTEST"
    return None

# D8: self-acceptance from the review queue is lawful ONLY for routine
# operation claims; everything else needs a distinct reviewer principal
SELF_ACCEPTABLE_ASSERTION_TYPES = frozenset({"OPERATION_CLAIM_ASSERTION"})

# subject types an AcceptedEventConsequence may carry (narrower than
# AssertionRecord's — refused at validation, never crashed at promotion)
CONSEQUENCE_SUBJECT_TYPES = frozenset({
    "FARM", "SITE", "FIELD", "ZONE", "CROP_CYCLE", "LOT", "FACILITY", "OPERATION"})

# Which typed identity-payload contract introduces which IdentityRecord type
# (M2 G1). Generic Core structural data — the durable identity types are
# Constitution vocabulary (RC2.1 §7), NOT jurisdiction schemes (KMG-MID/GERK
# are SI bindings, P4). A structure-assertion commit carries one of these
# payloads; the promotion emitter creates/locates the IdentityRecord of the
# mapped type, and the identity registry materializes the current payload per
# identity. Adding an identity type here is the ONLY change needed to support
# committing it — the gate chain stays generic (no per-type branches).
STRUCTURE_PAYLOAD_IDENTITY_TYPE = {
    "ofarm.farmidentitypayload.v0.1": "FARM",
    "ofarm.fieldidentitypayload.v0.1": "FIELD",
    "ofarm.cropcycleidentitypayload.v0.1": "CROP_CYCLE",
    "ofarm.equipmentidentitypayload.v0.1": "EQUIPMENT",
    "ofarm.appliedresourceidentitypayload.v0.1": "APPLIED_RESOURCE",
}

# Payload-internal references the structure semantic validator governs (D17):
# because a structure assertion's subject is always the farm, the payload's own
# refs are where cross-farm / dangling / wrong-kind injection would hide, so
# each is checked. Declarative per kind: (fieldName, category, isList). Generic
# data, no per-type procedural branch.
#   PARENT_FARM   -> must be the authorized farm itself
#   PARENT_SCOPE  -> must resolve to a farm-contained IdentityRecord
#   PARTY/EVIDENCE/BINDING/REFERENCE_SNAPSHOT -> must resolve to that kind
STRUCTURE_PAYLOAD_REF_FIELDS = {
    "ofarm.farmidentitypayload.v0.1": [
        ("operatorPartyRef", "PARTY", False)],
    "ofarm.fieldidentitypayload.v0.1": [
        ("parentFarmIdentityRef", "PARENT_FARM", False),
        ("geometryEvidenceRef", "EVIDENCE", False)],
    "ofarm.cropcycleidentitypayload.v0.1": [
        ("parentScopeRefs", "PARENT_SCOPE", True),
        ("cropBindingRefs", "BINDING", True)],
    "ofarm.equipmentidentitypayload.v0.1": [
        ("ownerPartyRef", "PARTY", False),
        ("inspectionEvidenceRefs", "EVIDENCE", True),
        ("identityBindingRefs", "BINDING", True)],
    "ofarm.appliedresourceidentitypayload.v0.1": [
        ("identityBindingRefs", "BINDING", True),
        ("referenceSnapshotRefs", "REFERENCE_SNAPSHOT", True)],
}

# ref category -> the record kind a resolvable ref of that category must be
STRUCTURE_REF_CATEGORY_KIND = {
    "PARTY": "ofarm.party.v0.1",
    "EVIDENCE": "ofarm.evidencerecord.v0.1",
    "BINDING": "ofarm.agronomicidentitybinding.v0.1",
    "REFERENCE_SNAPSHOT": "ofarm.referencesnapshot.v0.1",
}


def structure_self_acceptable(payload_kind: str) -> bool:
    """D17 (bounded self-acceptance): a STRUCTURE_ASSERTION may take the
    self-review (confirm-accept) promotion path ONLY when it carries one of the
    recognized G1 farm-owned identity payloads. Anything else (a future
    structure payload kind, etc.) must route to queued review with a distinct
    reviewer — never "all STRUCTURE_ASSERTIONs self-review". The actor's
    ASSERT_STRUCTURE + REVIEW_ACCEPT authority, the semantic validation, and the
    explicit-supersession rule (D18) are enforced by the gates; this function is
    the named bounded-class gate the review stage consults."""
    return payload_kind in STRUCTURE_PAYLOAD_IDENTITY_TYPE

# scope types that are never commitable claim targets on the farm-anchored
# commit path (hostile review: no tenant/deployment escape hatch)
NON_COMMITABLE_SCOPE_TYPES = frozenset({"TENANT", "DEPLOYMENT"})

# execution-extent classes that claim LESS than the whole target scope and so
# must quantify what was treated ("size treated" is a required SI record
# field). WHOLE_TARGET_SCOPE needs no bound — it is the whole scope.
NON_WHOLE_EXTENT_CLASSES = frozenset({
    "PARTIAL_TARGET_SCOPE", "FAILED_PASS", "RETREATMENT_AREA",
    "DISPUTED_AREA", "EXTERNAL_GEOMETRY_REFERENCE"})

# record kinds an extent ref (geometryRef / extentRef / scopeExtentBasisRef)
# may resolve to as a real bound. "Resolves to something" is not "resolves to
# the right kind of thing" — an existing record of the wrong kind is not an
# extent bound, and a dangling ref is no bound at all. M2 (G7) introduces the
# generic extent-carrier kind: the PartialExtent (`ofarm.partialextent.v0.1`),
# the minimal event-bound carrier for treatment/failed-pass/replant/damage/
# disputed geometries — a ref resolving to one is an acceptable bound alongside
# an inline `area`. The SI geometry that *populates* such carriers is package
# content (P2/GERK), never literals here. (profile_si_ffs/UNSUPPORTED_SURFACES.md.)
ALLOWED_EXTENT_BOUND_KINDS = frozenset({"ofarm.partialextent.v0.1"})

# resolving to the right KIND is not the same as being a USABLE bound: an
# extent carrier is acceptable as the bound of a promoting operation-claim only
# if it declares ITSELF usable for an accepted, materializing execution. Refuse
# over pretend (Kernel rule 4/7) rather than bound an accepted execution on a
# draft / disputed / superseded carrier, or one whose own promotionBoundary
# forbids it. (G7 hostile-review guard; honors the carrier's declared boundary,
# never overrides it.) The carrier states usable as such a bound:
EXTENT_CARRIER_USABLE_STATES = frozenset({"ACCEPTED_FOR_DECLARED_USE"})
# promotionBoundary.mustNotPromoteTo targets that an accepted, materialized
# operation-claim would drive — a carrier forbidding any of these is not a bound:
EXTENT_CARRIER_DRIVEN_PROMOTIONS = frozenset({"ACCEPTED_EXECUTION", "WHOLE_FIELD_TRUTH"})

# why a non-promoting commit class retains its draft at REVIEW_PROMOTION —
# wording pinned by the inherited gate-sequencing fixtures
NON_PROMOTING_RETAIN_REASONS = {
    "NOTE": "No declared safe promotion path exists from note to compliance fact.",
    "ADVISORY_OUTPUT": "Advisory output may raise review attention but may not "
                       "directly create a compliance fact.",
}
NON_PROMOTING_DEFAULT_REASON = "this commit class has no promotion path"

# ---------------------------------------------------------------------------
# temporal / carrier sanity bounds (SI floor support)
# ---------------------------------------------------------------------------

EVENT_TIME_PLAUSIBILITY_PAST_DAYS = 400
EVENT_TIME_PLAUSIBILITY_FUTURE_HOURS = 24
DOSE_SANITY_MAX = 10000.0

# the UCUM unit scheme: a resolved dose unit is this EXACT prefix followed by
# a non-empty code token. A bare "scheme:ucum", an empty code, or a substring
# look-alike ("scheme:ucumbersome") is a namespace label, not a unit — and a
# namespace label is not a resolved unit (Kernel rule 4: no shortcut to truth).
UCUM_SCHEME_PREFIX = "scheme:ucum:"


def is_resolved_ucum_unit(unit_ref: str | None) -> bool:
    """True only for a well-formed scheme:ucum:<code> reference with a
    non-empty code. (Code-level validation against a profile-pinned UCUM
    allow-list is a further hardening; this closes the bare/empty/substring
    holes that let a meaningless unit promote.)"""
    if not unit_ref or not unit_ref.startswith(UCUM_SCHEME_PREFIX):
        return False
    return bool(unit_ref[len(UCUM_SCHEME_PREFIX):].strip())

# The SI evidence floor (which named checks are hard vs soft) MOVED to package
# content in M2 P5: it is policy:si.ffs.evidence-review.v0_1, read generically by
# kernel.profile_policy.operation_floor(). No SI-specific floor VALUE lives in the
# generic kernel any more (mechanism-boundary stop rule); kernel/sufficiency.py
# provides the generic, Core-payload-shaped check logic and reads the hard/soft
# composition from the active profile.

COMPLIANCE_ASSERTED_STATUSES = frozenset({
    "CLAIMED_COMPLIANT", "CLAIMED_NON_COMPLIANT", "CLAIMED_PARTIALLY_COMPLIANT"})

# ---------------------------------------------------------------------------
# review-routing resolution policy (formal hostile re-review finding 2)
# ---------------------------------------------------------------------------

# route-reason codes whose resolution requires NEW durable evidence (or a
# corrected carrier) at acceptance — a bare "approve anyway" is refused
NEEDS_EVIDENCE_CODES = frozenset({
    "ACTOR_BINDING_UNRESOLVED", "PRODUCT_BINDING_UNRESOLVED",
    "IDENTITY_UNRESOLVED", "EVIDENCE_INSUFFICIENT", "SUPERSEDED_RECORD_USED",
})

# review-route reason code -> EvidenceSufficiencyCase insufficiency code,
# so the stored case explains the routing in the case schema's vocabulary
ROUTE_REASON_TO_INSUFFICIENCY = {
    "PRODUCT_BINDING_UNRESOLVED": "AMBIGUOUS_PRODUCT_ID",
    "SUPERSEDED_RECORD_USED": "CONFLICTING_EVIDENCE",
    "EVIDENCE_INSUFFICIENT": "TIMESTAMP_INCOMPLETE",
    "IDENTITY_UNRESOLVED": "MISSING_REQUIRED_EVIDENCE",
    "HUMAN_APPROVAL_REQUIRED": "ATTESTATION_AUTHORITY_MISSING",
}
ROUTE_REASON_INSUFFICIENCY_DEFAULT = "SOURCE_QUALITY_LOW"


def revocation_disposition(commit_class: str, ingress_channel: str) -> str:
    """Offline-synced operation claims route to review on revocation
    (CAPTURE_MAPPING sync rule 2); everything else denies. Both are lawful
    per AuthorizationDecisionResult allOf 4."""
    if ingress_channel == "OFFLINE_SYNC_REPLAY" and commit_class == "OPERATION_CLAIM":
        return "REQUIRE_REVIEW"
    return "DENY"


# ---------------------------------------------------------------------------
# freshness-use policy (Current-State RFC §6.4/§8: purpose-sensitive
# freshness; high-consequence use escalates to REQUIRE_FRESH)
# ---------------------------------------------------------------------------

# draft MaterializationKey useClass -> canonical MaterializationRequest useClass
USE_CLASS_TO_CANONICAL = {
    "OPERATIONAL_DASHBOARD": "EXPLORATORY",
    "EXPLORATORY_VIEW": "EXPLORATORY",
    "COMPLIANCE_DECISION_SUPPORT": "HIGH_CONSEQUENCE",
    "ATTESTED_OUTPUT": "ATTESTED_OUTPUT",
    "FORMAL_SUBMISSION": "ATTESTED_OUTPUT",
    "FORENSIC_AUDIT": "AUDIT_EXPLANATION",
}

# requirement -> freshness states that satisfy it. INVALID never satisfies
# anything (the MaterializationResult contract forbids satisfied=true on an
# INVALID state — allOf 2).
# NO_CURRENT_STATE_DEPENDENCY is deliberately narrowed to stale-allowed
# inside resolve_for_use: the mode is an undescribed enum value in the
# candidate contracts (defined nowhere in reference/ — ERRATA E-003), and
# its no-current-state intent is honored at the QueryPlanIR step layer
# instead (declared in profile_si_ffs/UNSUPPORTED_SURFACES.md).
FRESHNESS_USE_POLICY = {
    "REQUIRE_FRESH": frozenset({"FRESH"}),
    "ALLOW_STALE_EXPLORATORY": frozenset({"FRESH", "STALE"}),
    "NO_CURRENT_STATE_DEPENDENCY": frozenset({"FRESH", "STALE"}),
}


def effective_freshness_requirement(required: str, high_consequence: bool) -> str:
    """High-consequence use always escalates to REQUIRE_FRESH (RFC §8/§9)."""
    return "REQUIRE_FRESH" if high_consequence else required


def freshness_satisfied(required: str, high_consequence: bool,
                        freshness_state: str) -> bool:
    effective = effective_freshness_requirement(required, high_consequence)
    return freshness_state in FRESHNESS_USE_POLICY.get(effective, frozenset())


def reuse_reason_summary(freshness_state: str, required: str,
                         high_consequence: bool) -> str:
    """The reason never overstates freshness: a stale reuse says so."""
    if freshness_state == "FRESH":
        return "reused FRESH materialization"
    effective = effective_freshness_requirement(required, high_consequence)
    return (f"reused STALE materialization under {effective}; "
            "high-consequence use barred")
