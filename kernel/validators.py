"""Named validation units (issue #3): each validator is one concern with one
contract — it inspects the GateContext, appends review-route reasons for
exceptions, and returns a GateRefusal (already logged) to stop the chain or
None to pass. The ValidationGate runs them in the law-pinned order; the
sequence IS the policy and reads as one list.

Refusal vs review-route is each validator's declared posture, with
profile-owned validation policy supplying the active SI pilot values and text:
hard floor breaks refuse (RETAIN_DRAFT), exceptions route to the advisor queue.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone

from . import config, policy, profile_policy, sufficiency
from .context import SI_REGSR_FAMILY_ID, current_reference_snapshot, parse_ts
from .contracts import ContractViolation, UnknownContract, canonical_json, sha256_of
from .problems import REGISTERED_REASON_CODES, runtime_problem
from .profile_runtime import ProfileRuntimeDescriptor, ProfileRuntimeError, ReferenceFamily
from .profile_runtime_services import (
    RegistryReverificationDisposition,
    RegistryReverificationOutcome,
    RegistryReverificationRequest,
)
from .stages import GateContext, GatePass, GateRefusal


_CONFIG_BACKED_POLICY = object()


def _refusal(ctx: GateContext, outcome: str, problem: dict,
             final: str = "RETAIN_DRAFT",
             rationale: str | None = None) -> GateRefusal:
    """Log-and-build: every refusing outcome lands in the gate log and the
    PromotionTrace, never only in the problems array (PLATFORM.md). The
    logged rationale defaults to the problem detail; a caller may pass the
    shorter operator-facing form where that is the established text."""
    ctx.log("VALIDATION", outcome, reason_code=problem["reasonCode"],
            rationale=rationale or problem["detail"])
    return GateRefusal("VALIDATION", outcome, final, [problem])


def _validation_policy_refusal(ctx: GateContext, detail) -> GateRefusal:
    return _refusal(ctx, "FAIL_PROFILE_POLICY", runtime_problem(
        "PROFILE_NOT_ACTIVE", "Validation policy unavailable",
        f"the active profile's validation policy could not be loaded ({detail}); "
        "the claim stays a draft (fail closed)"))


def _review_record_or_refusal(
    ctx: GateContext,
    record_ref: str,
    expected_kind: str,
) -> tuple[dict | None, GateRefusal | None]:
    """Resolve review inputs inside the active tenant without an existence oracle."""
    row = ctx.store.get_record(record_ref)
    if row is not None and row["record_kind"] == expected_kind:
        return row, None
    return None, _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", runtime_problem(
        "EVIDENCE_REFERENCE_UNAVAILABLE", "Review reference unavailable",
        f"{record_ref} is not available to this review"))


def _review_evidence_refusal(ctx: GateContext) -> GateRefusal | None:
    for evidence_ref in ctx.sub.get("reviewEvidenceRefs") or []:
        _, refusal = _review_record_or_refusal(
            ctx,
            evidence_ref,
            "ofarm.evidencerecord.v0.1",
        )
        if refusal is not None:
            return refusal
    return None


def _validation_policy_or_refusal(
    ctx: GateContext,
    validation_policy=_CONFIG_BACKED_POLICY,
    *,
    required_path: tuple[str, ...] = (),
) -> tuple[dict | None, GateRefusal | None]:
    if validation_policy is _CONFIG_BACKED_POLICY:
        try:
            validation = profile_policy.validation_policy()
        except profile_policy.ProfilePolicyError as exc:
            return None, _validation_policy_refusal(ctx, exc)
    elif isinstance(validation_policy, dict):
        validation = validation_policy
    else:
        return None, _validation_policy_refusal(
            ctx, "explicit validation policy must be a JSON object")

    cursor = validation
    for key in required_path:
        if not isinstance(cursor, dict) or key not in cursor:
            dotted = ".".join(required_path)
            return None, _validation_policy_refusal(
                ctx, f"validation policy lacks required section {dotted}")
        cursor = cursor[key]
    if required_path and not isinstance(cursor, dict):
        dotted = ".".join(required_path)
        return None, _validation_policy_refusal(
            ctx, f"validation policy section {dotted} must be a JSON object")
    return validation, None


def _assert_contained(ctx: GateContext, scope_type: str, scope_ref: str,
                      where: str) -> GateRefusal | None:
    """Farm containment with no escape hatches: a FARM-typed ref must BE the
    authorized farm; TENANT/DEPLOYMENT are not commitable claim scopes; any
    other governed scope ref must RESOLVE, BE an IdentityRecord, and be
    anchored on the authorized farm."""
    if scope_type in policy.NON_COMMITABLE_SCOPE_TYPES:
        return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
            "SCOPE_NOT_AUTHORIZED", "Non-farm claim scope refused",
            f"{where} uses scope type {scope_type}; commit-path claims are "
            "farm-anchored — tenant/deployment scopes are not commitable "
            "targets in this pilot"))
    if scope_type == "FARM":
        if scope_ref != ctx.farm_ref:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "SCOPE_NOT_AUTHORIZED", "Cross-farm scope refused",
                f"{where} names farm {scope_ref}; this commit is "
                f"authorized on {ctx.farm_ref} only"))
        return None
    row = ctx.store.get_record(scope_ref)
    if row is None:
        return _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", runtime_problem(
            "IDENTITY_UNRESOLVED", "Scope ref unresolved",
            f"{where} names {scope_ref}, which does not resolve to any "
            "stored record"))
    if row["record_kind"] != "ofarm.identityrecord.v0.1":
        return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
            "IDENTITY_UNRESOLVED", "Scope ref is not a governed identity",
            f"{where} names {scope_ref} ({row['record_kind']}); governed "
            "claim scopes must be IdentityRecords"))
    anchors = row["payload"].get("anchorScopes", [])
    if {"scopeType": "FARM", "scopeRef": ctx.farm_ref} not in anchors:
        return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
            "SCOPE_NOT_AUTHORIZED", "Cross-farm scope refused",
            f"{where} names {scope_ref}, which is not anchored on "
            f"{ctx.farm_ref}; authority on one farm never reaches "
            "another farm's identities"))
    return None


def _assert_parent_scope_contained(ctx: GateContext, ref: str,
                                   where: str) -> GateRefusal | None:
    """A structure payload's parent scope ref must resolve to a farm-contained
    IdentityRecord (or be the authorized farm itself)."""
    if ref == ctx.farm_ref:
        return None
    row = ctx.store.get_record(ref)
    if row is None:
        return _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", runtime_problem(
            "IDENTITY_UNRESOLVED", "Parent scope unresolved",
            f"{where} names {ref}, which does not resolve to any stored record"))
    if row["record_kind"] != "ofarm.identityrecord.v0.1":
        return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
            "IDENTITY_UNRESOLVED", "Parent scope is not a governed identity",
            f"{where} names {ref} ({row['record_kind']}); a parent scope must be "
            "an IdentityRecord"))
    if {"scopeType": "FARM", "scopeRef": ctx.farm_ref} \
            not in row["payload"].get("anchorScopes", []):
        return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
            "SCOPE_NOT_AUTHORIZED", "Cross-farm parent scope refused",
            f"{where} names {ref}, which is not anchored on {ctx.farm_ref}"))
    return None


class _CorrectionProofError(ValueError):
    def __init__(self, detail: str, reason: str = "CORRECTION_REQUIRED", *,
                 refusal: GateRefusal | None = None):
        super().__init__(detail)
        self.reason = reason
        self.refusal = refusal


def _correction_record(ctx: GateContext, ref, kind: str | None = None, *,
                       wrong_kind_reason: str = "EVIDENCE_REFERENCE_UNAVAILABLE") -> dict:
    """Resolve one correction-proof record through the tenant-visible store."""
    row = ctx.store.get_record(ref) if isinstance(ref, str) and ref.strip() else None
    if row is None:
        raise _CorrectionProofError("Correction provenance is unavailable",
                                    "EVIDENCE_REFERENCE_UNAVAILABLE")
    if kind is not None and row["record_kind"] != kind:
        raise _CorrectionProofError("Correction provenance has the wrong kind", wrong_kind_reason)
    payload = row["payload"]
    try:
        contract = ctx.store.registry.get(row["record_kind"])
    except UnknownContract as exc:
        raise _CorrectionProofError("Correction provenance has an unknown record kind") from exc
    if (payload.get("schemaVersion") != row["record_kind"]
            or payload.get(contract.id_field) != ref):
        raise _CorrectionProofError("Correction record references disagree")
    return payload


def _correction_edge(ctx: GateContext, source: str, edge_type: str) -> str:
    edges = ctx.store.edges_from(source, edge_type)
    if len(edges) != 1 or edges[0]["src_record_id"] != source:
        raise _CorrectionProofError(f"Correction proof requires exactly one {edge_type} edge")
    return edges[0]["dst_record_id"]


def _correction_farm(ctx: GateContext, payload: dict) -> None:
    if {"scopeType": "FARM", "scopeRef": ctx.farm_ref} not in payload.get("anchorScopes", []):
        raise _CorrectionProofError("Correction provenance is not anchored on this farm",
                                    "SCOPE_NOT_AUTHORIZED")


def _assertion_event(ctx: GateContext, assertion: dict) -> dict:
    """The accepting emitter uses this exact source, including for queued history."""
    _correction_farm(ctx, assertion)
    event_ref = _correction_edge(ctx, assertion["assertionRecordId"], "EVENT_SOURCE")
    event = _correction_record(ctx, event_ref, "ofarm.semanticeventenvelope.v0.1")
    anchors = event.get("anchorScopes")
    if not isinstance(anchors, list) or not anchors:
        raise _CorrectionProofError("Source event requires governed anchor scopes",
                                    "SCOPE_NOT_AUTHORIZED")
    for anchor in anchors:
        if (not isinstance(anchor, dict)
                or not isinstance(anchor.get("scopeType"), str)
                or not isinstance(anchor.get("scopeRef"), str)):
            raise _CorrectionProofError("Source event anchor scope is malformed",
                                        "SCOPE_NOT_AUTHORIZED")
        refusal = _assert_contained(ctx, anchor["scopeType"], anchor["scopeRef"],
                                    "Source event anchorScopes")
        if refusal is not None:
            # Containment already logged the governed refusal; preserve it once.
            raise _CorrectionProofError("Source event scope is not contained", refusal=refusal)
    commit_class = next((name for name, family in policy.COMMIT_CLASS_TO_ASSERTION_TYPE.items()
                         if family == assertion.get("assertionType")), None)
    if (commit_class is None
            or event.get("primaryEventFamily") != policy.COMMIT_CLASS_TO_FAMILY[commit_class]
            or event.get("subjectRefs") != [assertion.get("subject", {}).get("subjectRef")]):
        raise _CorrectionProofError("Assertion and source event disagree")
    return event


def _structure_identity(ctx: GateContext, payload: dict) -> tuple[str, str]:
    schema_version = payload.get("schemaVersion")
    identity_type = (policy.STRUCTURE_PAYLOAD_IDENTITY_TYPE.get(schema_version)
                     if isinstance(schema_version, str) else None)
    identity_ref = payload.get("identityRecordRef")
    if identity_type is None or not isinstance(identity_ref, str) or not identity_ref.strip():
        raise _CorrectionProofError("Correction requires an exact typed structural identity")
    existing = ctx.store.get_record(identity_ref)
    if existing is not None:
        identity = _correction_record(ctx, identity_ref, "ofarm.identityrecord.v0.1")
        if identity.get("identityType") != identity_type:
            raise _CorrectionProofError("Structural identity types disagree")
        if identity_type != "FARM":
            _correction_farm(ctx, identity)
    if identity_type == "FARM" and identity_ref != ctx.farm_ref:
        raise _CorrectionProofError("Structural identity belongs to another farm",
                                    "SCOPE_NOT_AUTHORIZED")
    return identity_type, identity_ref


def _correction_subject(ctx: GateContext, assertion: dict, event: dict | None,
                        incoming_payload: dict | None = None) -> tuple[str, str]:
    """Compare only the relationship the existing source family can establish."""
    family = assertion.get("assertionType")
    if family not in policy.ACCEPTANCE_BY_ASSERTION_TYPE:
        raise _CorrectionProofError("This assertion family has no correction path")
    subject = assertion.get("subject") or {}
    subject_type, subject_ref = subject.get("subjectType"), subject.get("subjectRef")
    if not isinstance(subject_type, str) or not isinstance(subject_ref, str) or not subject_ref:
        raise _CorrectionProofError("Correction requires an exact subject")
    if family == "STRUCTURE_ASSERTION":
        payload = incoming_payload
        if event is not None:
            ref = _correction_edge(ctx, event["semanticEventId"], "STRUCTURE_PAYLOAD")
            payload = _correction_record(ctx, ref)
        if not isinstance(payload, dict):
            raise _CorrectionProofError("Correction structure payload is unavailable")
        return _structure_identity(ctx, payload)
    if family == "OPERATION_CLAIM_ASSERTION":
        payload = incoming_payload
        if event is not None:
            refs = assertion.get("executionRecordPayloadRefs")
            if not isinstance(refs, list) or len(refs) != 1 \
                    or event.get("executionRecordPayloadRefs") != refs:
                raise _CorrectionProofError("Operation source and carrier references disagree")
            payload = _correction_record(ctx, refs[0], "ofarm.executionrecordpayload.v0.1")
        if not isinstance(payload, dict) or payload.get("subject") != subject:
            raise _CorrectionProofError("Operation carrier and assertion subjects disagree")
    elif family == "COMPLIANCE_ASSERTION":
        claim = (incoming_payload.get("complianceClaim")
                 if isinstance(incoming_payload, dict) else None)
        if event is not None:
            ref = _correction_edge(ctx, event["semanticEventId"], "COMPLIANCE_CLAIM")
            claim = _correction_record(ctx, ref, "ofarm.complianceclaim.v0.1")
            _correction_farm(ctx, claim)
            if claim.get("sourceEventRef") != event["semanticEventId"]:
                raise _CorrectionProofError("Compliance carrier and source event disagree")
        if not isinstance(claim, dict) or claim.get("subjectScopeRef") != subject_ref:
            raise _CorrectionProofError("Compliance carrier and assertion subjects disagree")
        identity = _correction_record(ctx, subject_ref, "ofarm.identityrecord.v0.1")
        if identity.get("identityType") != subject_type:
            raise _CorrectionProofError("Compliance subject identity types disagree")
        if subject_type != "FARM":
            _correction_farm(ctx, identity)
        elif subject_ref != ctx.farm_ref:
            raise _CorrectionProofError("Compliance subject belongs to another farm")
    return subject_type, subject_ref


def _validate_correction(ctx: GateContext, predecessor, assertion: dict,
                         event: dict | None = None) -> None:
    """One proof for submitted intent and acceptance; only success publishes a target."""
    old = _correction_record(ctx, predecessor, "ofarm.acceptedeventconsequence.v0.1",
                             wrong_kind_reason="SUPERSEDED_RECORD_USED")
    _correction_farm(ctx, old)
    if old.get("inForceState") != "IN_FORCE" or ctx.store.is_superseded(predecessor):
        raise _CorrectionProofError("Correction predecessor is no longer in force",
                                    "SUPERSEDED_RECORD_USED")
    review_ref = old.get("acceptedByReviewDecisionRef")
    review = _correction_record(ctx, review_ref, "ofarm.reviewdecision.v0.1")
    _correction_farm(ctx, review)
    if (review.get("reviewedArtifactFamily"), review.get("reviewAction"),
            review.get("decisionOutcomeState")) != ("ASSERTION_RECORD", "REVIEW_ACCEPT", "ACCEPTED"):
        raise _CorrectionProofError("Correction predecessor has no accepting assertion review")
    origin = _correction_record(ctx, review.get("reviewedArtifactRef"), "ofarm.assertionrecord.v0.1")
    if (_correction_edge(ctx, predecessor, "REVIEW") != review_ref
            or _correction_edge(ctx, origin["assertionRecordId"], "REVIEW") != review_ref):
        raise _CorrectionProofError("Correction review edges and scalar references disagree")
    original_event = _assertion_event(ctx, origin)
    if (old.get("sourceEventRef") != original_event["semanticEventId"]
            or _correction_edge(ctx, predecessor, "EVENT_SOURCE") != original_event["semanticEventId"]
            or old.get("subject") != origin.get("subject")
            or old.get("executionRecordPayloadRefs") != origin.get("executionRecordPayloadRefs")):
        raise _CorrectionProofError("Correction consequence and accepted origin disagree")
    family = origin.get("assertionType")
    acceptance = policy.ACCEPTANCE_BY_ASSERTION_TYPE.get(family)
    if (acceptance is None or old.get("consequenceType") != acceptance[1]
            or assertion.get("assertionType") != family):
        raise _CorrectionProofError("Correction must preserve the accepted source family and consequence type")
    old_subject = _correction_subject(ctx, origin, original_event)
    new_subject = _correction_subject(ctx, assertion, event, ctx.sub.get("payload"))
    if old_subject != new_subject:
        raise _CorrectionProofError(
            "Correction must preserve the exact subject or typed structural identity",
            "SUPERSEDED_RECORD_USED" if family == "STRUCTURE_ASSERTION" else "CORRECTION_REQUIRED")
    if family == "STRUCTURE_ASSERTION":
        _correction_record(ctx, old_subject[1], "ofarm.identityrecord.v0.1")
        _check_structure_current(ctx, old_subject[1], predecessor)
    ctx.correction_predecessor_ref = predecessor


def _correction_refusal(ctx: GateContext, exc: _CorrectionProofError) -> GateRefusal:
    if exc.refusal is not None:
        return exc.refusal
    return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
        exc.reason, "Correction relationship refused", str(exc)))


def _in_force_structural_consequences_for(ctx: GateContext,
                                          identity_ref: str) -> list[str]:
    """In-force structural consequence ids whose carried identity payload
    targets this identity (in-force consequence -> sourceEvent ->
    STRUCTURE_PAYLOAD -> payload.identityRecordRef)."""
    out = []
    for row in ctx.store.in_force_consequences(ctx.farm_ref):
        c = row["payload"]
        edges = ctx.store.edges_from(c["sourceEventRef"], "STRUCTURE_PAYLOAD")
        # Examine every candidate; malformed/duplicate proof is refused by the
        # relationship validator, never hidden by choosing a first payload.
        if any((p := ctx.store.get_payload(edge["dst_record_id"]))
               and p.get("identityRecordRef") == identity_ref for edge in edges):
            out.append(c["acceptedEventConsequenceId"])
    return out


def _check_structure_current(ctx: GateContext, identity_ref: str, predecessor) -> None:
    in_force = _in_force_structural_consequences_for(ctx, identity_ref)
    if len(in_force) > 1:
        raise _CorrectionProofError("Structural identity has ambiguous current consequences")
    if in_force and predecessor is None:
        raise _CorrectionProofError("Existing identity requires explicit supersession of its current state")
    if predecessor is not None and in_force != [predecessor]:
        raise _CorrectionProofError("Correction does not name the identity's sole current structural predecessor",
                                    "SUPERSEDED_RECORD_USED")


def _carrier_admits_bound(payload: dict) -> bool:
    """Whether a resolved extent-carrier (PartialExtent) admits being the bound of
    a promoting, materializing operation-claim. Honors the carrier's OWN declared
    boundary (Kernel rule 4), never overrides it: the carrier must be in a usable
    state (policy.EXTENT_CARRIER_USABLE_STATES) and its promotionBoundary must
    permit driving a materialized accepted execution — not have
    mayDriveMaterialization false, and not name in mustNotPromoteTo any promotion
    target this commit path actually drives or feeds
    (policy.EXTENT_CARRIER_DRIVEN_PROMOTIONS: the accepted consequence, the
    materialized extent, the derived current state, and the PassportView it backs).
    A draft / disputed / superseded or self-forbidding carrier is not a bound."""
    if payload.get("extentState") not in policy.EXTENT_CARRIER_USABLE_STATES:
        return False
    boundary = payload.get("promotionBoundary", {})
    if not boundary.get("mayDriveMaterialization", False):
        return False
    if set(boundary.get("mustNotPromoteTo", [])) & policy.EXTENT_CARRIER_DRIVEN_PROMOTIONS:
        return False
    return True


# ---------------------------------------------------------------------------
# the named validators, in law-pinned order
# ---------------------------------------------------------------------------

class TemporalConformanceValidator:
    """Junk event times refuse; implausible windows route to review
    (no temporal reason code exists in the registry — ERRATA E-001)."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        if ctx.temporal_problem is not None:
            return _refusal(ctx, "FAIL_TEMPORAL", ctx.temporal_problem)
        event_time = ctx.event_time or ctx.captured_at
        et = parse_ts(event_time)
        if et is None:
            # defensive double-check: the ingress normalizer pre-cleans junk
            # times, so through the pipeline this branch is unreachable — it
            # guards direct stage use (and future normalizer changes)
            return _refusal(ctx, "FAIL_TEMPORAL", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Unparseable event time",
                f"event time {event_time!r} is not a valid timestamp (ERRATA "
                "E-001: no temporal-conformance reason code exists in the registry)"))
        now = datetime.now(timezone.utc)
        if et > now + timedelta(hours=policy.EVENT_TIME_PLAUSIBILITY_FUTURE_HOURS) or \
           et < now - timedelta(days=policy.EVENT_TIME_PLAUSIBILITY_PAST_DAYS):
            ctx.review_route_reasons.append(runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Event time outside plausibility window",
                f"event time {event_time} is outside the plausibility window; "
                "routed to review, never silently accepted (ERRATA E-001)",
                severity="WARNING"))
        return None


class PromotionTargetValidator:
    """A PROMOTING class may only request its own lawful target, and its
    subject must be a type the consequence contract can carry. Non-promoting
    classes pass and are stopped at REVIEW_PROMOTION instead, exactly as the
    inherited gate-sequencing fixtures pin it."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        promoting = ctx.commit_class in policy.COMMIT_CLASS_TO_PROMOTION_TARGET
        if ctx.requested_target and promoting:
            lawful = policy.COMMIT_CLASS_TO_PROMOTION_TARGET[ctx.commit_class]
            if ctx.requested_target != lawful:
                return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                    "HIGH_CONSEQUENCE_BLOCKED", "Unlawful promotion target",
                    f"commit class {ctx.commit_class} cannot request promotion "
                    f"target {ctx.requested_target}; its lawful target is {lawful} "
                    "(no shortcut to truth)"))
        if promoting:
            subject_type = ctx.sub.get("subjectType", "FARM")
            if subject_type not in policy.CONSEQUENCE_SUBJECT_TYPES:
                return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                    "IDENTITY_UNRESOLVED", "Subject type cannot promote",
                    f"subjectType {subject_type} is not promotable to an accepted "
                    "consequence; the claim stays a draft"))
        return None


class ScopeContainmentValidator:
    """Farm containment over the submission's own scope-bearing fields."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        if ctx.commit_class in policy.COMMIT_CLASS_TO_PROMOTION_TARGET:
            refusal = _assert_contained(
                ctx, ctx.sub.get("subjectType", "FARM"),
                ctx.sub.get("subjectRef", ctx.farm_ref), "subject")
            if refusal:
                return refusal
        for s in ctx.sub.get("targetScopes") or []:
            refusal = _assert_contained(ctx, s["scopeType"], s["scopeRef"],
                                        "targetScopes")
            if refusal:
                return refusal
        return None


class SupersessionValidator:
    """Only a checked relationship may become inert intent or retirement."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        if "supersedesConsequenceRef" not in ctx.sub:
            return None
        assertion = {
            "assertionType": policy.COMMIT_CLASS_TO_ASSERTION_TYPE.get(ctx.commit_class),
            "subject": {"subjectType": ctx.sub.get("subjectType", "FARM"),
                        "subjectRef": ctx.sub.get("subjectRef", ctx.farm_ref)},
        }
        try:
            if assertion["assertionType"] not in policy.ACCEPTANCE_BY_ASSERTION_TYPE:
                raise _CorrectionProofError("This submission cannot supply a correction target")
            _validate_correction(ctx, ctx.sub["supersedesConsequenceRef"], assertion)
        except _CorrectionProofError as exc:
            return _correction_refusal(ctx, exc)
        return None


class GovernanceAcceptanceValidator:
    """A review acceptance names a real, queued, farm-contained, unreviewed
    assertion; D8 holds at the queue door; the act carries its rationale and
    durable review evidence."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        if ctx.commit_class != "GOVERNANCE_DECISION":
            return None
        # Resolve the review-decision verb fail-closed (G5 §3.1): the
        # (reviewAction, decisionOutcomeState) pair must name a supported branch.
        # CONTESTED (deferred to G5-3), a mismatched outcome, or any unsupported
        # combination refuses here — never silently treated as accept or reject.
        branch = policy.review_branch(ctx.review_action, ctx.review_outcome)
        if branch is None:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Unsupported review decision",
                f"reviewAction {ctx.review_action!r} with decisionOutcomeState "
                f"{ctx.review_outcome!r} is not a supported review decision "
                "(CONTEST is deferred to G5-3); refused rather than guessed"))
        ctx.review_branch = branch
        if branch == "CONTEST":
            # CONTEST targets an in-force CONSEQUENCE, not a queued assertion
            # (G5-4 / spec §6.3) — wholly separate validity guards
            return self._validate_contest(ctx)
        is_reject = branch == "REJECT"
        target_ref = ctx.sub.get("reviewTargetAssertionRef")
        if not target_ref:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Acceptance without target",
                "a governance-decision commit requires reviewTargetAssertionRef"))
        row, refusal = _review_record_or_refusal(
            ctx,
            target_ref,
            "ofarm.assertionrecord.v0.1",
        )
        if refusal is not None:
            return refusal
        if not is_reject and (
            row["runtime_bundle_digest"] != ctx.store.runtime_bundle_digest
        ):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "PACK_CONFLICT", "Cross-bundle acceptance refused",
                f"{target_ref} was evaluated under bundle "
                f"{row['runtime_bundle_digest']}, while this process is bound to "
                f"{ctx.store.runtime_bundle_digest}; resubmit the claim for a new "
                "evaluation under the active bundle rather than promoting prepared "
                "state across runtimes",
                related_refs=[target_ref]))
        target = row["payload"]
        ctx.acceptance_payload = target   # fetched once; later stages reuse it
        if {"scopeType": "FARM", "scopeRef": ctx.farm_ref} \
                not in target["anchorScopes"]:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "SCOPE_NOT_AUTHORIZED", "Cross-farm acceptance refused",
                f"{target_ref} is not anchored on {ctx.farm_ref}"))
        if target["claimState"] != "PENDING_REVIEW":
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "SUPERSEDED_RECORD_USED", "Target not pending review",
                f"{target_ref} has claimState {target['claimState']}"))
        if ctx.store.edges_from(target_ref, "REVIEW"):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "SUPERSEDED_RECORD_USED", "Target already reviewed",
                f"{target_ref} already carries a review decision"))
        # the acceptance-path type gate is a PROMOTION guard — a reject promotes
        # nothing, so REJECT is NOT type-gated (G5 §3.3): a reviewer may decline a
        # queued claim of any kind, including one with no acceptance path.
        if not is_reject \
                and target["assertionType"] not in policy.ACCEPTANCE_BY_ASSERTION_TYPE:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "IDENTITY_UNRESOLVED", "Assertion type not acceptable",
                f"{target['assertionType']} has no acceptance path"))
        # D8 holds at the queue door for BOTH verbs: a party self-deciding its
        # own queued claim (accept OR reject) covers ROUTINE OPERATION CLAIMS only
        # (G5 §3.2 reuses the distinct-reviewer bound for reject)
        if (target["assertedByPartyRef"] == ctx.acting_party
                and target["assertionType"]
                not in policy.SELF_ACCEPTABLE_ASSERTION_TYPES):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "HUMAN_APPROVAL_REQUIRED", "Self-review out of scope",
                f"self-review covers routine operation claims only (D8); "
                f"{target['assertionType']} asserted by the acting party requires a "
                "DISTINCT reviewer principal — for either acceptance or rejection"))
        # Rejection abandons inert intent. Only acceptance resolves its exact
        # source and rechecks the relationship against current accepted state.
        if not is_reject:
            try:
                if target.get("assertionRecordId") != target_ref:
                    raise _CorrectionProofError("Queued assertion reference disagrees with its record")
                event = _assertion_event(ctx, target)
                intent_edges = ctx.store.edges_from(target_ref, "LINEAGE_SUPERSEDES_INTENT")
                if len(intent_edges) > 1:
                    raise _CorrectionProofError("Queued correction has ambiguous predecessor intent")
                if intent_edges:
                    _validate_correction(ctx, intent_edges[0]["dst_record_id"], target, event)
                elif target["assertionType"] == "STRUCTURE_ASSERTION":
                    identity = _correction_subject(ctx, target, event)
                    _check_structure_current(ctx, identity[1], None)
                ctx.acceptance_event_ref = event["semanticEventId"]
            except _CorrectionProofError as exc:
                return _correction_refusal(ctx, exc)
        # a review decision (accept OR reject) is governed, never a bare pointer:
        # both must state a non-empty rationale (G5 §3.3; Kernel rule 7)
        rationale_text = ctx.sub.get("reviewRationale")
        if not (isinstance(rationale_text, str) and rationale_text.strip()):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Review decision without rationale",
                "a review decision must state its rationale"))
        evidence_refusal = _review_evidence_refusal(ctx)
        if evidence_refusal is not None:
            return evidence_refusal
        ctx.log("VALIDATION", "PASS")
        return None

    def _validate_contest(self, ctx: GateContext) -> GateRefusal | None:
        """A CONTEST names a real, in-force, farm-contained, not-already-disputed
        AcceptedEventConsequence; the act carries its rationale and (optional)
        validated evidence (spec §6.3). Inherits no acceptance promotion guard —
        a dispute promotes and retires nothing."""
        target_ref = ctx.acceptance_target   # the in-force consequence ref
        if not target_ref:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Contest without target",
                "a contest requires reviewTargetConsequenceRef"))
        row, refusal = _review_record_or_refusal(
            ctx,
            target_ref,
            "ofarm.acceptedeventconsequence.v0.1",
        )
        if refusal is not None:
            return refusal
        conseq = row["payload"]
        ctx.acceptance_payload = conseq   # fetched once; emission reuses it
        if {"scopeType": "FARM", "scopeRef": ctx.farm_ref} not in conseq["anchorScopes"]:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "SCOPE_NOT_AUTHORIZED", "Cross-farm contest refused",
                f"{target_ref} is not anchored on {ctx.farm_ref}"))
        if conseq.get("inForceState") != "IN_FORCE" or ctx.store.is_superseded(target_ref):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "SUPERSEDED_RECORD_USED", "Contest target not in force",
                f"{target_ref} is not an in-force consequence; only current state "
                "can be disputed (a superseded/withdrawn record is already out of force)"))
        if ctx.store.edges_from(target_ref, "DISPUTE"):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "SUPERSEDED_RECORD_USED", "Target already disputed",
                f"{target_ref} already carries an open dispute"))
        rationale_text = ctx.sub.get("reviewRationale")
        if not (isinstance(rationale_text, str) and rationale_text.strip()):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Contest without rationale",
                "a contest must state its dispute rationale"))
        evidence_refusal = _review_evidence_refusal(ctx)
        if evidence_refusal is not None:
            return evidence_refusal
        ctx.log("VALIDATION", "PASS")
        return None


class ComplianceClaimValidator:
    """A compliance assertion carries a minimal STRUCTURED claim — statement,
    asserted status, recognized governing rules, resolvable farm-contained
    subject — before the sufficiency case even evaluates it."""

    RECOGNIZED_RULE_REFS = frozenset({
        config.EVIDENCE_POLICY_REF, config.PROFILE_REF,
        config.PACK_REF, config.CODE_BINDING_PROFILE_REF})

    def __init__(self, recognized_rule_refs=None):
        self.recognized_rule_refs = (
            self.RECOGNIZED_RULE_REFS if recognized_rule_refs is None
            else frozenset(recognized_rule_refs)
        )

    def run(self, ctx: GateContext) -> GateRefusal | None:
        if ctx.commit_class != "COMPLIANCE_ASSERTION":
            return None
        payload = ctx.sub.get("payload")
        claim = payload.get("complianceClaim") if isinstance(payload, dict) else None
        if not isinstance(claim, dict):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Unstructured compliance claim",
                "a compliance assertion requires a structured complianceClaim "
                "payload (statement, assertedStatus, governingRuleRefs, "
                "subjectScopeRef); a bare claim cannot become a compliance fact"))
        if not (isinstance(claim.get("statement"), str) and claim["statement"].strip()):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Compliance claim without statement",
                "complianceClaim.statement must state what is being claimed"))
        status = claim.get("assertedStatus")
        if not isinstance(status, str) \
                or status not in policy.COMPLIANCE_ASSERTED_STATUSES:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Compliance claim without asserted status",
                "complianceClaim.assertedStatus must be one of CLAIMED_COMPLIANT, "
                "CLAIMED_NON_COMPLIANT, CLAIMED_PARTIALLY_COMPLIANT"))
        rule_refs = claim.get("governingRuleRefs") or []
        # type-checked, not just truthy: a non-list shape must be a governed
        # refusal here, never a late ContractViolation or an uncaught
        # TypeError at the carrier write (own verification of PR #4 fixes)
        if not isinstance(rule_refs, list) \
                or not all(isinstance(r, str) for r in rule_refs):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Governing rules unresolved",
                "complianceClaim.governingRuleRefs must be a list of governed "
                "rule/policy refs"))
        unknown_rules = [r for r in rule_refs
                         if r not in self.recognized_rule_refs
                         and not ctx.store.record_exists(r)]
        if not rule_refs or unknown_rules:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Governing rules unresolved",
                f"complianceClaim.governingRuleRefs must name recognized governed "
                f"rules/policies; missing or unknown: {unknown_rules or 'none given'}"))
        subject_ref = claim.get("subjectScopeRef")
        subject_row = ctx.store.get_record(subject_ref) if subject_ref else None
        if subject_row is None:
            return _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", runtime_problem(
                "EVIDENCE_REFERENCE_UNAVAILABLE", "Compliance subject unresolved",
                f"complianceClaim.subjectScopeRef {subject_ref!r} does not resolve"))
        if subject_row["record_kind"] != "ofarm.identityrecord.v0.1":
            # steward review (PR #4): a resolvable-but-non-identity subject is
            # refused, never silently passed — same taxonomy as the scope path
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "IDENTITY_UNRESOLVED", "Scope ref is not a governed identity",
                f"complianceClaim.subjectScopeRef names {subject_ref} "
                f"({subject_row['record_kind']}); governed claim scopes must "
                "be IdentityRecords"))
        # a FARM identity's record id IS the farm ref, so the FARM branch
        # of _assert_contained compares it directly against ctx.farm_ref
        refusal = _assert_contained(
            ctx, subject_row["payload"]["identityType"],
            subject_ref, "complianceClaim.subjectScopeRef")
        if refusal:
            return refusal
        ctx.log("VALIDATION", "PASS")
        return None


class StructureCarrierValidator:
    """The structure-assertion carrier is a typed identity payload — Farm,
    Field, CropCycle, Equipment, or AppliedResource (contracts/core/). It
    validates against its own contract and must be a recognized identity-payload
    kind; a missing, malformed, or wrong-kind payload keeps the claim a draft
    (Kernel rule 4: no shortcut to truth; rule 7: refuse over pretend). Generic
    over identity type — no scheme logic, no per-type branch."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        payload = ctx.sub.get("payload")
        if not isinstance(payload, dict):
            return _refusal(ctx, "FAIL_CARRIER", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Missing structure payload",
                "a structure assertion requires a typed identity payload carrier "
                "(Farm/Field/CropCycle/Equipment/AppliedResource); the claim stays "
                "a draft"))
        try:
            contract = ctx.store.registry.validate(payload)
        except (ContractViolation, UnknownContract) as exc:
            # an unknown or malformed carrier schema is a governed refusal,
            # never an unrecorded crash (mirrors CarrierSchemaValidator)
            return _refusal(ctx, "FAIL_SCHEMA", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Structure payload schema violation", str(exc)))
        if contract.kind not in policy.STRUCTURE_PAYLOAD_IDENTITY_TYPE:
            return _refusal(ctx, "FAIL_CARRIER", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Wrong structure carrier",
                f"structure assertions carry a typed identity payload "
                f"(one of {sorted(policy.STRUCTURE_PAYLOAD_IDENTITY_TYPE)}), got "
                f"{contract.kind}; the claim stays a draft"))
        # validated; the carrier id rides to EnvelopePersist (storage + edge)
        # and to the promotion emitter (IdentityRecord creation). PASS is logged
        # by StructureSemanticsValidator, the branch-terminal validator.
        ctx.structure_payload_id = payload[contract.id_field]
        return None


class StructureSemanticsValidator:
    """Beyond schema (StructureCarrierValidator), the structure carrier's
    INTERNAL references are governed (D17): because the assertion subject is
    always the farm, the payload's own refs are where cross-farm / dangling /
    wrong-kind injection would hide. Each is checked against the policy
    ref-field spec. Also enforces D18: a re-assertion of an identity that
    already has in-force structural state must explicitly supersede that
    identity's current structural consequence — never a silent latest-wins.
    Generic over identity type; no scheme logic."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        payload = ctx.sub["payload"]
        kind = payload["schemaVersion"]
        identity_type = policy.STRUCTURE_PAYLOAD_IDENTITY_TYPE[kind]
        identity_ref = payload["identityRecordRef"]

        # a Farm identity payload may only assert the authorized farm itself
        if identity_type == "FARM" and identity_ref != ctx.farm_ref:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "SCOPE_NOT_AUTHORIZED", "Farm identity must be the authorized farm",
                f"a Farm identity payload may only assert {ctx.farm_ref}, "
                f"not {identity_ref}"))

        # an existing identity must be the same type and farm-contained (a
        # revision never changes an identity's type or steals another farm's)
        existing = ctx.store.get_record(identity_ref)
        if existing is not None:
            if existing["record_kind"] != "ofarm.identityrecord.v0.1":
                return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                    "IDENTITY_UNRESOLVED", "Identity ref is not an identity",
                    f"identityRecordRef {identity_ref} names a "
                    f"{existing['record_kind']}, not an IdentityRecord"))
            if existing["payload"]["identityType"] != identity_type:
                return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                    "IDENTITY_UNRESOLVED", "Identity type mismatch",
                    f"identityRecordRef {identity_ref} already names a "
                    f"{existing['payload']['identityType']} identity, not {identity_type}"))
            if identity_type != "FARM" and {"scopeType": "FARM", "scopeRef": ctx.farm_ref} \
                    not in existing["payload"].get("anchorScopes", []):
                return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                    "SCOPE_NOT_AUTHORIZED", "Cross-farm identity refused",
                    f"identityRecordRef {identity_ref} is not anchored on {ctx.farm_ref}"))

        # payload-internal refs resolve to the right kinds / are farm-contained
        for field, category, is_list in policy.STRUCTURE_PAYLOAD_REF_FIELDS.get(kind, []):
            val = payload.get(field)
            if val is None:
                continue
            for ref in (val if is_list else [val]):
                if category == "PARENT_FARM":
                    if ref != ctx.farm_ref:
                        return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                            "SCOPE_NOT_AUTHORIZED", "Parent farm mismatch",
                            f"{field} must be the authorized farm {ctx.farm_ref}, not {ref}"))
                elif category == "PARENT_SCOPE":
                    refusal = _assert_parent_scope_contained(ctx, ref, field)
                    if refusal:
                        return refusal
                else:
                    expected = policy.STRUCTURE_REF_CATEGORY_KIND[category]
                    row = ctx.store.get_record(ref)
                    if row is None or row["record_kind"] != expected:
                        return _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", runtime_problem(
                            "EVIDENCE_REFERENCE_UNAVAILABLE", "Structure payload ref unresolved",
                            f"{field} ref {ref} does not resolve to a {expected}"))
                    # An identity's OWN binding must bind THIS identity, never another
                    # subject's binding attached to a different committed identity (PR #15
                    # B1: G1 previously checked only that the ref resolved to a binding,
                    # not that its subject matched). Scoped to identityBindingRefs;
                    # cropBindingRefs bind a crop species, not the identity, so are exempt.
                    if field == "identityBindingRefs":
                        bound = (row["payload"].get("localSubject") or {}).get("subjectRef")
                        if bound != identity_ref:
                            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                                "CORRECTION_REQUIRED", "Identity binding subject mismatch",
                                f"{field} ref {ref} binds {bound!r}, not the committed identity "
                                f"{identity_ref!r}; a binding must bind the identity it is attached to"))

        # Corrections already passed the shared relationship proof. D18 also
        # forbids silent replacement when a new assertion omits a predecessor.
        if ctx.correction_predecessor_ref is None:
            try:
                _check_structure_current(ctx, identity_ref, None)
            except _CorrectionProofError as exc:
                return _correction_refusal(ctx, exc)

        ctx.log("VALIDATION", "PASS")
        return None


class CarrierSchemaValidator:
    """The operation carrier validates against its contract, and a caller
    may never self-declare an accepted/corrected/disputed record class
    (an operation claim is not an accepted execution — Kernel rule 4)."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        payload = ctx.sub.get("payload")
        if not isinstance(payload, dict):
            return _refusal(ctx, "FAIL_SCHEMA", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Missing carrier payload",
                "an operation claim requires an ExecutionRecordPayload carrier"))
        try:
            contract = ctx.store.registry.validate(payload)
        except (ContractViolation, UnknownContract) as exc:
            # UnknownContract too: an unknown carrier schemaVersion is a
            # governed refusal, never an unrecorded crash (pride review)
            return _refusal(ctx, "FAIL_SCHEMA", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Carrier schema violation", str(exc)))
        if contract.kind != "ofarm.executionrecordpayload.v0.1":
            return _refusal(ctx, "FAIL_SCHEMA", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Wrong carrier",
                f"operation claims carry ofarm.executionrecordpayload.v0.1, "
                f"got {contract.kind}"))
        if payload.get("recordClass") not in ("OPERATION_CLAIM", "AS_APPLIED_EVIDENCE"):
            return _refusal(ctx, "FAIL_CARRIER", runtime_problem(
                "HIGH_CONSEQUENCE_BLOCKED", "Self-declared record class refused",
                f"a commit-time carrier may declare recordClass OPERATION_CLAIM or "
                f"AS_APPLIED_EVIDENCE, not {payload.get('recordClass')!r}"))
        return None


class CarrierSemanticsValidator:
    """The SI quantity/unit policy: every dose carries a UCUM unit code and
    quantity kind (BLOCK_PROMOTION when unresolved); implausible doses route
    to the advisor, never silently block."""

    def __init__(self, validation_policy):
        self.validation_policy = validation_policy

    @classmethod
    def from_config_for_legacy_tests(cls):
        return cls(_CONFIG_BACKED_POLICY)

    def run(self, ctx: GateContext) -> GateRefusal | None:
        payload = ctx.sub["payload"]
        validation, refusal = _validation_policy_or_refusal(
            ctx, self.validation_policy, required_path=("quantityAndUnit",))
        if refusal:
            return refusal
        quantity_policy = validation["quantityAndUnit"]
        try:
            require_quantity = quantity_policy["requireQuantityKindAndUnitCode"]
            unresolved_reason = quantity_policy["unresolvedReasonCode"]
            unresolved_title = quantity_policy["unresolvedTitle"]
            unresolved_detail = quantity_policy["unresolvedDetail"]
            unresolved_rationale = quantity_policy["unresolvedRationale"]
            implausible_reason = quantity_policy["implausibleDoseReviewReasonCode"]
            implausible_title = quantity_policy["implausibleDoseTitle"]
            implausible_template = quantity_policy["implausibleDoseDetailTemplate"]
        except (KeyError, TypeError) as exc:
            return _validation_policy_refusal(
                ctx, f"validation policy malformed: {exc}")
        params = payload.get("actualQuantityParameters", [])
        dose_params = [p for p in params if p["parameterRole"] in ("DOSE", "RATE")]
        if require_quantity:
            bad_units = [p for p in dose_params
                         if not policy.is_resolved_ucum_unit(p.get("unitRef"))
                         or not p.get("quantityKindRef")]
            if not dose_params or bad_units:
                return _refusal(ctx, "FAIL_CARRIER", runtime_problem(
                    unresolved_reason, unresolved_title, unresolved_detail),
                    rationale=unresolved_rationale)
        for p in dose_params:
            if not (0 < p["value"] <= policy.DOSE_SANITY_MAX):
                ctx.review_route_reasons.append(runtime_problem(
                    implausible_reason,
                    implausible_title,
                    profile_policy.format_validation_template(
                        implausible_template,
                        value=p["value"]),
                    severity="WARNING"))
        return None


class ExecutionExtentValidator:
    """A non-whole extent must quantify what was treated, and the bound must be
    REAL. A PARTIAL_TARGET_SCOPE / FAILED_PASS / RETREATMENT_AREA / DISPUTED_AREA
    / EXTERNAL_GEOMETRY_REFERENCE claim must carry an inline `area` (value+unit)
    or an extent ref (geometryRef / extentRef / scopeExtentBasisRef) that
    resolves to a recognized extent-carrier kind (policy.ALLOWED_EXTENT_BOUND_KINDS
    — the PartialExtent, G7) AND whose carrier declares itself usable as such a
    bound (see _carrier_admits_bound). No bound at all, a bound whose only ref is
    dangling or of the wrong kind, or a carrier that does not admit the promotion,
    is an incomplete or impermissible bound — "size treated" is a required SI
    record field — so the claim stays a draft, never silently materialized as
    whole-scope (corrected and resubmitted, like a dose missing its unit). The
    inline `area` remains an always-available bound."""

    def __init__(self, validation_policy):
        self.validation_policy = validation_policy

    @classmethod
    def from_config_for_legacy_tests(cls):
        return cls(_CONFIG_BACKED_POLICY)

    def run(self, ctx: GateContext) -> GateRefusal | None:
        validation, refusal = _validation_policy_or_refusal(
            ctx, self.validation_policy,
            required_path=("recordFields", "nonWholeExtentBound"))
        if refusal:
            return refusal
        extent_policy = validation["recordFields"]["nonWholeExtentBound"]
        try:
            required_label = extent_policy["requiredLabel"]
            missing_reason = extent_policy["missingReasonCode"]
            missing_title = extent_policy["missingTitle"]
            missing_template = extent_policy["missingDetailTemplate"]
            missing_rationale = extent_policy["missingRationale"]
        except (KeyError, TypeError) as exc:
            return _validation_policy_refusal(
                ctx, f"validation policy malformed: {exc}")
        extent = ctx.sub["payload"].get("executionExtent", {})
        if extent.get("extentClass") not in policy.NON_WHOLE_EXTENT_CLASSES:
            return None
        present_refs = [r for r in (extent.get("geometryRef"),
                                    extent.get("extentRef"),
                                    extent.get("scopeExtentBasisRef")) if r]
        if not extent.get("area") and not present_refs:
            return _refusal(ctx, "FAIL_CARRIER", runtime_problem(
                missing_reason,
                missing_title,
                profile_policy.format_validation_template(
                    missing_template,
                    extentClass=extent.get("extentClass"),
                    requiredLabel=required_label)),
                rationale=missing_rationale)
        # a ref bound must resolve to a RECOGNIZED extent-bound carrier kind —
        # "resolves to something" is not "resolves to the right kind of thing".
        # policy.ALLOWED_EXTENT_BOUND_KINDS recognizes the generic extent-carrier
        # (PartialExtent, G7); a dangling ref or a wrong-kind existing record is
        # no bound. Then "right kind" is not "usable as a bound": the carrier must
        # declare ITSELF usable for a promoting accepted execution, or refuse over
        # pretend (rule 4/7). The inline `area` remains an always-available bound.
        invalid, unusable = [], []
        for ref in present_refs:
            row = ctx.store.get_record(ref)
            if row is None or row["record_kind"] not in policy.ALLOWED_EXTENT_BOUND_KINDS:
                invalid.append(ref)
            elif not _carrier_admits_bound(row["payload"]):
                unusable.append(ref)
        if invalid:
            return _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", runtime_problem(
                "EVIDENCE_REFERENCE_UNAVAILABLE", "Partial extent bound unresolved",
                f"executionExtent names extent bound(s) {invalid} that do not resolve "
                "to a recognized extent-bound carrier (the recognized kind is the "
                "PartialExtent, policy.ALLOWED_EXTENT_BOUND_KINDS): a dangling ref or a "
                "wrong-kind record is no bound, so the claim stays a draft (inline "
                "`area` is the always-available bound)"),
                rationale=f"unrecognized extent bound refs: {invalid}")
        if unusable:
            return _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", runtime_problem(
                "EVIDENCE_REFERENCE_UNAVAILABLE", "Partial extent bound not usable",
                f"executionExtent names extent carrier(s) {unusable} that resolve to a "
                "PartialExtent but do not admit being a bound for an accepted, "
                "materializing execution — the carrier's own extentState is not "
                "ACCEPTED_FOR_DECLARED_USE, or its promotionBoundary forbids it "
                "(mayDriveMaterialization=false, or mustNotPromoteTo names a target this "
                "accepted operation drives/feeds: ACCEPTED_EXECUTION / WHOLE_FIELD_TRUTH / "
                "CURRENT_STATE_DIRECTLY / PASSPORT_VIEW_DEFAULT); the claim stays a draft "
                "rather than bound an accepted execution on a non-accepted or self-"
                "forbidding carrier"),
                rationale=f"extent carriers not usable as a bound: {unusable}")
        return None


class ReferenceResolutionValidator:
    """Every package-local ref in the carrier resolves, and every scope-
    bearing carrier field is contained in the authorized farm."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        payload = ctx.sub["payload"]
        dangling = []
        for ref in ([payload["actor"]["actorPartyRef"]]
                    + payload.get("agronomicIdentityBindingRefs", [])
                    + payload.get("evidenceRefs", [])):
            if not ctx.store.record_exists(ref):
                dangling.append(ref)
        field_scope = payload["executionExtent"]["targetScope"]
        field_identity = ctx.store.get_payload(field_scope["scopeRef"])
        if field_scope["scopeType"] == "FIELD" and field_identity is None:
            dangling.append(field_scope["scopeRef"])
        if dangling:
            return _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", runtime_problem(
                "EVIDENCE_REFERENCE_UNAVAILABLE", "Dangling references",
                f"these references do not resolve in the store: {dangling}"),
                rationale=f"dangling refs: {dangling}")

        for scope_type, scope_ref, where in (
                [(payload["subject"]["subjectType"],
                  payload["subject"]["subjectRef"], "carrier subject"),
                 (field_scope["scopeType"], field_scope["scopeRef"],
                  "executionExtent.targetScope")]
                + [(s["scopeType"], s["scopeRef"], "carrier anchorScopes")
                   for s in payload.get("anchorScopes", [])]):
            refusal = _assert_contained(ctx, scope_type, scope_ref, where)
            if refusal:
                return refusal
        return None


class ActorAttributionValidator:
    """Actor attribution is governed, never free text with a party id: a
    named actor differing from the submitter must hold their own live
    authority path for this operation on this farm; anything weaker routes
    to the advisor queue. The attribution decision is stored and linked
    (second AUTHORITY_BASIS edge; surfaced on the trace)."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        payload = ctx.sub["payload"]
        named_actor = payload["actor"]["actorPartyRef"]
        if named_actor == ctx.acting_party:
            return None
        basis = ctx.authority.evaluate(
            acting_party_ref=named_actor,
            action_class="ASSERT_OPERATION_CLAIM",
            action_stage="DRAFT_PREPARATION",
            scope={"scopeType": "FARM", "scopeRef": ctx.farm_ref})
        ctx.record_authority_decision(basis)
        ctx.attribution_ref = basis.result_payload["resultId"]
        if not basis.allowed:
            ctx.review_route_reasons.append(runtime_problem(
                "ACTOR_BINDING_UNRESOLVED", "Actor attribution unverified",
                f"the carrier names {named_actor} as the operator, but that "
                "party holds no live grant or delegation for this operation "
                f"on {ctx.farm_ref}; the attribution claim routes to review",
                severity="WARNING",
                related_refs=[basis.result_payload["resultId"]]))
        return None


class CodeBindingValidator:
    """Bindings against the SI code-binding profile: unresolved product or
    crop bindings are explicit and route to review — free text never
    silently becomes compliance identity."""

    def __init__(self, validation_policy):
        self.validation_policy = validation_policy

    @classmethod
    def from_config_for_legacy_tests(cls):
        return cls(_CONFIG_BACKED_POLICY)

    def run(self, ctx: GateContext) -> GateRefusal | None:
        validation, refusal = _validation_policy_or_refusal(
            ctx, self.validation_policy, required_path=("bindings",))
        if refusal:
            return refusal
        binding_policy = validation["bindings"]
        try:
            wrong_policy = binding_policy["wrongKindRef"]
            wrong_reason = wrong_policy["reasonCode"]
            wrong_title = wrong_policy["title"]
            wrong_template = wrong_policy["detailTemplate"]
            product_policy = binding_policy["product"]
            product_role = product_policy["bindingRole"]
            product_disposition = product_policy["missingOrUnverifiedDisposition"]
            product_reason = product_policy["reasonCode"]
            product_title = product_policy["title"]
            product_template = product_policy["detailTemplate"]
            crop_policy = binding_policy["crop"]
            crop_role = crop_policy["bindingRole"]
            crop_disposition = crop_policy["missingDisposition"]
            crop_reason = crop_policy["reasonCode"]
            crop_title = crop_policy["title"]
            crop_detail = crop_policy["detail"]
        except (KeyError, TypeError) as exc:
            return _validation_policy_refusal(
                ctx, f"validation policy malformed: {exc}")
        payload = ctx.sub["payload"]
        refs = payload.get("agronomicIdentityBindingRefs", [])
        # A binding ref must name a governed AgronomicIdentityBinding. A ref to
        # any other (already-resolving) record kind is malformed input: refuse
        # governably (Kernel rule 7) instead of dereferencing it into a bare
        # KeyError that escapes the pipeline as an untraced 500. (Dangling
        # refs are already caught by ReferenceResolutionValidator upstream.)
        wrong_kind = [r for r in refs
                      if (row := ctx.store.get_record(r)) is not None
                      and row["record_kind"] != sufficiency.BINDING_KIND]
        if wrong_kind:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                wrong_reason, wrong_title,
                profile_policy.format_validation_template(
                    wrong_template, refs=wrong_kind)))
        bindings = sufficiency.resolved_bindings(ctx.store, refs)
        crop_bindings = [b for b in bindings
                         if b.get("bindingRole") == crop_role]
        product_bindings = [b for b in bindings
                            if b.get("bindingRole") == product_role]
        product_binding = product_bindings[0] if product_bindings else None
        if product_binding is None or product_binding["bindingState"] != "VERIFIED":
            state = product_binding["bindingState"] if product_binding else "MISSING"
            problem = runtime_problem(
                product_reason, product_title,
                profile_policy.format_validation_template(
                    product_template, state=state),
                severity="WARNING"
                if product_disposition == "REVIEW"
                else "ERROR")
            if product_disposition == "REVIEW":
                ctx.review_route_reasons.append(problem)
            else:
                return _refusal(ctx, "FAIL_SEMANTIC", problem)
        if not crop_bindings:
            problem = runtime_problem(
                crop_reason, crop_title, crop_detail,
                severity="WARNING"
                if crop_disposition == "REVIEW" else "ERROR")
            if crop_disposition == "REVIEW":
                ctx.review_route_reasons.append(problem)
            else:
                return _refusal(ctx, "FAIL_SEMANTIC", problem)
        return None


class RegistryReverificationValidator:
    """D9: product identity is the decision number + validity dates;
    regsrCode is a page locator, NEVER identity. Re-verification across a
    snapshot advance is identity-grade only where the snapshot carries
    decision-number data; anything weaker routes to review.

    A selected profile provider supplies the exact REGSR family and lookup.
    """

    def __init__(self, *, active_profile, reference_family, product_lookup):
        if type(active_profile) is not ProfileRuntimeDescriptor:
            raise ProfileRuntimeError(
                "SI registry service requires a trusted profile descriptor"
            )
        expected_family = active_profile.reference_family(SI_REGSR_FAMILY_ID)
        if type(reference_family) is not ReferenceFamily \
                or reference_family is not expected_family:
            raise ProfileRuntimeError(
                "SI registry service requires the descriptor's exact REGSR family"
            )
        if (
            getattr(product_lookup, "runtime_bundle", None) is None
            or product_lookup.bindings.regsr_snapshot_prefix
            != reference_family.snapshot_prefix
        ):
            raise ProfileRuntimeError(
                "SI registry lookup lacks exact REGSR runtime provenance"
            )
        self.active_profile = active_profile
        self.reference_family = reference_family
        self.runtime_bundle = product_lookup.runtime_bundle
        self.selected_input_bindings = product_lookup.selected_input_bindings
        self.snapshot_prefix = reference_family.snapshot_prefix
        self.product_lookup = product_lookup

    def run(
        self,
        request: RegistryReverificationRequest,
    ) -> RegistryReverificationOutcome:
        if type(request) is not RegistryReverificationRequest:
            raise ProfileRuntimeError(
                "SI registry service requires the exact detached request type"
            )
        try:
            claim = json.loads(request.claim_canonical_bytes)
            bindings = tuple(
                json.loads(value)
                for value in request.resolved_binding_canonical_bytes
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProfileRuntimeError("SI registry request bytes are invalid") from exc
        if type(claim) is not dict or any(type(value) is not dict for value in bindings):
            raise ProfileRuntimeError("SI registry request payloads must be objects")
        product_bindings = [
            binding for binding in bindings
            if binding.get("bindingRole") == "CROP_PROTECTION_PRODUCT"
        ]
        product_binding = product_bindings[0] if product_bindings else None
        if not (product_binding and product_binding["bindingState"] == "VERIFIED"):
            return RegistryReverificationOutcome(
                RegistryReverificationDisposition.NO_EFFECT
            )
        current_id = request.current_reference_snapshot_ref
        captured_against = claim.get("capturedAgainstSnapshotRef") \
            or (product_binding.get("referenceSnapshotRefs") or [None])[0]
        if not (current_id and captured_against and captured_against != current_id):
            return RegistryReverificationOutcome(
                RegistryReverificationDisposition.NO_EFFECT
            )
        family_root = self.reference_family.snapshot_prefix
        if not (current_id == family_root or current_id.startswith(family_root + ".")):
            raise ProfileRuntimeError("current registry snapshot is outside REGSR")
        decision_number = product_binding["bindingValue"].get("registrationRef")
        if not (
            captured_against == family_root
            or captured_against.startswith(family_root + ".")
        ):
            return RegistryReverificationOutcome(
                RegistryReverificationDisposition.REVIEW_REQUIRED,
                problem=runtime_problem(
                    "PRODUCT_BINDING_UNRESOLVED",
                    "Re-verification not confirmable",
                    f"captured snapshot {captured_against} is outside the active "
                    f"registry family {family_root}; identity cannot be "
                    "re-confirmed, so the record routes to review",
                    severity="WARNING",
                ),
            )
        confirmed = (
            self.product_lookup.lookup_by_decision(current_id, decision_number)
            if decision_number else None
        )
        if confirmed is not None:
            valid_until = (confirmed.get("decision", {}).get("validUntil")
                           or confirmed.get("registrationValidUntil") or "")
            if valid_until and valid_until < request.event_time[:10]:
                return RegistryReverificationOutcome(
                    RegistryReverificationDisposition.REVIEW_REQUIRED,
                    problem=runtime_problem(
                        "SUPERSEDED_RECORD_USED", "Registry snapshot discrepancy",
                        f"decision {decision_number} validity ended {valid_until} per "
                        f"current snapshot {current_id}, before the event time; "
                        "discrepancy recorded and routed to review, never silent "
                        "acceptance", severity="WARNING"),
                )
            return RegistryReverificationOutcome(
                RegistryReverificationDisposition.REVERIFIED,
                rationale=f"identity re-verified by decision number "
                          f"{decision_number} against {current_id}",
            )
        return RegistryReverificationOutcome(
            RegistryReverificationDisposition.REVIEW_REQUIRED,
            problem=runtime_problem(
                "PRODUCT_BINDING_UNRESOLVED", "Re-verification not confirmable",
                f"the current snapshot {current_id} carries no decision-number "
                f"data for {decision_number or 'this binding'}; identity cannot "
                "be re-confirmed on this surface (regsrCode is a locator, not "
                "identity — D9), so the record routes to review",
                severity="WARNING"),
        )


class CarrierStore:
    """Stores the validated carrier in the same transaction. A reused
    carrier id with DIFFERENT content is a refused conflict — promoted truth
    never silently diverges from the validated submission."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        payload = ctx.sub["payload"]
        erp_id = payload["executionRecordPayloadId"]
        existing = ctx.store.get_record(erp_id)
        if existing is None:
            ctx.store.insert_record(ctx.cur, payload)
            for ev in payload.get("evidenceRefs", []):
                if ctx.store.record_exists(ev):
                    ctx.store.add_edge(ctx.cur, "EVIDENCE", erp_id, ev)
        elif existing["payload_sha256"] != sha256_of(payload):
            return _refusal(ctx, "FAIL_CARRIER", runtime_problem(
                "RETRY_CONFLICT", "Carrier id conflict",
                f"executionRecordPayloadId {erp_id} already names a record with "
                "different content; mint a new carrier id (corrections supersede "
                "via supersedesConsequenceRef, they never overwrite)"))
        ctx.erp_id = erp_id
        return None


# ---------------------------------------------------------------------------
# the validation gate: the law-pinned sequence, readable as one list
# ---------------------------------------------------------------------------

# every commit class runs these
COMMON_SEQUENCE = (
    TemporalConformanceValidator(),
    PromotionTargetValidator(),
    ScopeContainmentValidator(),
    SupersessionValidator(),
)

# operation claims additionally run these, in this order; CarrierStore runs
# AFTER the PASS log (a carrier-id conflict surfaces as PASS-then-FAIL on the
# trace — the validation checks passed, the storage step refused)
def _operation_sequence_for_validation_policy(
    validation_policy: dict,
) -> tuple:
    return (
        CarrierSchemaValidator(),
        CarrierSemanticsValidator(validation_policy),
        ExecutionExtentValidator(validation_policy),
        ReferenceResolutionValidator(),
        ActorAttributionValidator(),
        CodeBindingValidator(validation_policy),
    )


def _registry_request(ctx: GateContext) -> RegistryReverificationRequest:
    try:
        family = ctx.runtime_services.registry_reference_family
        current = (
            current_reference_snapshot(ctx.store, family.snapshot_prefix)
            if family is not None else None
        )
        binding_refs = ctx.sub["payload"].get(
            "agronomicIdentityBindingRefs", []
        )
        bindings = sufficiency.resolved_bindings(ctx.store, binding_refs)
        return RegistryReverificationRequest(
            claim_canonical_bytes=canonical_json(ctx.sub).encode("utf-8"),
            resolved_binding_canonical_bytes=tuple(
                canonical_json(binding).encode("utf-8") for binding in bindings
            ),
            current_reference_snapshot_ref=(
                current["referenceSnapshotId"] if current else None
            ),
            event_time=ctx.event_time or ctx.captured_at,
        )
    except Exception as exc:
        raise ProfileRuntimeError(
            "registry reverification request could not be constructed"
        ) from exc


def _validated_registry_problem(
    ctx: GateContext,
    problem: object,
    severity: str,
) -> dict:
    if type(problem) is not dict:
        raise ProfileRuntimeError("registry outcome requires a RuntimeProblem")
    try:
        contract = ctx.store.registry.validate(problem)
        accepted = copy.deepcopy(problem)
    except Exception as exc:
        raise ProfileRuntimeError("registry outcome problem is invalid") from exc
    if (
        contract.kind != "ofarm.runtimeproblem.v0.1"
        or accepted.get("reasonCode") not in REGISTERED_REASON_CODES
        or accepted.get("severity") != severity
    ):
        raise ProfileRuntimeError("registry outcome problem is not admissible")
    return accepted


def _run_registry_reverification(ctx: GateContext) -> GateRefusal | None:
    request = _registry_request(ctx)
    try:
        outcome = ctx.runtime_services.registry_reverification.run(request)
    except Exception as exc:
        raise ProfileRuntimeError("registry reverification service failed") from exc
    if (
        type(outcome) is not RegistryReverificationOutcome
        or type(outcome.disposition) is not RegistryReverificationDisposition
    ):
        raise ProfileRuntimeError("registry reverification returned an invalid outcome")
    disposition = outcome.disposition
    if disposition is RegistryReverificationDisposition.NO_EFFECT:
        if outcome.problem is not None or outcome.rationale is not None:
            raise ProfileRuntimeError("NO_EFFECT registry outcome has extra fields")
        return None
    if disposition is RegistryReverificationDisposition.REVERIFIED:
        if (outcome.problem is not None or type(outcome.rationale) is not str
                or not outcome.rationale):
            raise ProfileRuntimeError("REVERIFIED registry outcome is malformed")
        ctx.log("VALIDATION", "REGISTRY_REVERIFIED", rationale=outcome.rationale)
        return None
    if outcome.rationale is not None:
        raise ProfileRuntimeError("registry problem outcome has a rationale")
    severity = (
        "WARNING"
        if disposition is RegistryReverificationDisposition.REVIEW_REQUIRED
        else "ERROR"
    )
    problem = _validated_registry_problem(ctx, outcome.problem, severity)
    if disposition is RegistryReverificationDisposition.REVIEW_REQUIRED:
        ctx.review_route_reasons.append(problem)
        return None
    if disposition is RegistryReverificationDisposition.REFUSED:
        return _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", problem)
    raise ProfileRuntimeError("registry reverification disposition is unknown")


class ValidationGate:
    """Runs the named validators in law-pinned order; first refusal stops
    the chain (already logged); review-route reasons accumulate on the
    context for the REVIEW_PROMOTION gate to honor. Individual validators
    return GateRefusal | None; the gate itself speaks the chain's typed
    contract (GatePass | GateRefusal)."""

    def run(self, ctx: GateContext) -> GatePass | GateRefusal:
        for validator in COMMON_SEQUENCE:
            refusal = validator.run(ctx)
            if refusal:
                return refusal

        # PASS-logging convention: branch-terminal validators (governance,
        # compliance) log their own PASS because they end the sequence; the
        # operation sequence logs one PASS here so the attribution ref can
        # ride the single VALIDATION entry
        if ctx.commit_class == "GOVERNANCE_DECISION":
            return GovernanceAcceptanceValidator().run(ctx) or GatePass()
        if ctx.commit_class == "COMPLIANCE_ASSERTION":
            recognized_refs = (
                ctx.runtime_services.policy_provider.recognized_rule_refs
            )
            return ComplianceClaimValidator(
                recognized_rule_refs=recognized_refs).run(ctx) or GatePass()
        if ctx.commit_class == "STRUCTURE_ASSERTION":
            refusal = StructureCarrierValidator().run(ctx)
            if refusal:
                return refusal
            return StructureSemanticsValidator().run(ctx) or GatePass()
        if ctx.commit_class != "OPERATION_CLAIM":
            ctx.log("VALIDATION", "PASS")
            return GatePass()

        try:
            validation_policy = (
                ctx.runtime_services.policy_provider.validation_policy()
            )
        except profile_policy.ProfilePolicyError as exc:
            return _validation_policy_refusal(ctx, exc)
        operation_sequence = _operation_sequence_for_validation_policy(
            validation_policy,
        )

        for validator in operation_sequence:
            refusal = validator.run(ctx)
            if refusal:
                return refusal
        refusal = _run_registry_reverification(ctx)
        if refusal:
            return refusal
        # the trace's VALIDATION entry surfaces the attribution decision so
        # both authority decisions are visible on the promotion path
        ctx.log("VALIDATION", "PASS",
                refs=[ctx.attribution_ref] if ctx.attribution_ref else None)
        return CarrierStore().run(ctx) or GatePass()
