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

from datetime import datetime, timedelta, timezone

from . import config, policy, profile_policy, sufficiency
from .context import REGSR_SNAPSHOT_PREFIX, current_reference_snapshot, parse_ts
from .contracts import ContractViolation, UnknownContract, sha256_of
from .problems import runtime_problem
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


def _in_force_structural_consequences_for(ctx: GateContext,
                                          identity_ref: str) -> list[str]:
    """In-force structural consequence ids whose carried identity payload
    targets this identity (in-force consequence -> sourceEvent ->
    STRUCTURE_PAYLOAD -> payload.identityRecordRef)."""
    out = []
    for row in ctx.store.in_force_consequences(ctx.farm_ref):
        c = row["payload"]
        edges = ctx.store.edges_from(c["sourceEventRef"], "STRUCTURE_PAYLOAD")
        if not edges:
            continue
        p = ctx.store.get_payload(edges[0]["dst_record_id"])
        if p and p.get("identityRecordRef") == identity_ref:
            out.append(c["acceptedEventConsequenceId"])
    return out


def _structure_target_identity(ctx: GateContext, assertion_ref: str) -> str | None:
    """The identity a queued STRUCTURE_ASSERTION targets, resolved from its
    carrier: assertion -> EVENT_SOURCE -> event -> STRUCTURE_PAYLOAD -> payload."""
    ev = ctx.store.edges_from(assertion_ref, "EVENT_SOURCE")
    if not ev:
        return None
    sp = ctx.store.edges_from(ev[0]["dst_record_id"], "STRUCTURE_PAYLOAD")
    if not sp:
        return None
    payload = ctx.store.get_payload(sp[0]["dst_record_id"])
    return payload.get("identityRecordRef") if payload else None


def _verified_product_binding(ctx: GateContext) -> dict | None:
    """The carrier's first CROP_PROTECTION_PRODUCT binding, if any. Resolves
    binding refs kind-checked (a wrong-kind ref is not a binding and never a
    KeyError); CodeBindingValidator refuses wrong-kind refs governably first."""
    bindings = sufficiency.resolved_bindings(
        ctx.store, ctx.sub["payload"].get("agronomicIdentityBindingRefs", []))
    product_bindings = [b for b in bindings
                        if b.get("bindingRole") == "CROP_PROTECTION_PRODUCT"]
    return product_bindings[0] if product_bindings else None


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
    """A correction must name a real, in-force consequence on THIS farm —
    an unvalidated ref could knock another farm's truth out of force."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        supersedes = ctx.sub.get("supersedesConsequenceRef")
        if not supersedes:
            return None
        target_row = ctx.store.get_record(supersedes)
        if target_row is None:
            return _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", runtime_problem(
                "EVIDENCE_REFERENCE_UNAVAILABLE", "Supersession target missing",
                f"supersedesConsequenceRef {supersedes} does not resolve"))
        if target_row["record_kind"] != "ofarm.acceptedeventconsequence.v0.1":
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "SUPERSEDED_RECORD_USED", "Supersession target wrong kind",
                f"{supersedes} is {target_row['record_kind']}, not an accepted "
                "consequence"))
        if {"scopeType": "FARM", "scopeRef": ctx.farm_ref} \
                not in target_row["payload"]["anchorScopes"]:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "SCOPE_NOT_AUTHORIZED", "Cross-farm supersession refused",
                f"{supersedes} is not anchored on {ctx.farm_ref}; a correction may "
                "only supersede this farm's own truth"))
        if ctx.store.is_superseded(supersedes):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "SUPERSEDED_RECORD_USED", "Target already superseded",
                f"{supersedes} was already superseded; correct the current "
                "in-force record instead"))
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
        # Acceptance-time re-validation (TOCTOU): the world can change between a
        # claim being queued and a reviewer accepting it, so supersession/D18 is
        # re-checked against CURRENT in-force state, not the state at submission
        # (PR #9 re-review blockers). The queued correction's supersession target
        # is the LINEAGE_SUPERSEDES_INTENT edge recorded at queue time. This is a
        # PROMOTION guard: a reject retires nothing (the prior consequence stays
        # in force, the supersession intent is abandoned — G5 §3.4), so REJECT
        # skips it entirely.
        if not is_reject:
            intent_edges = ctx.store.edges_from(target_ref, "LINEAGE_SUPERSEDES_INTENT")
            intent = intent_edges[0]["dst_record_id"] if intent_edges else None
            if target["assertionType"] == "STRUCTURE_ASSERTION":
                identity_ref = _structure_target_identity(ctx, target_ref)
                in_force = (_in_force_structural_consequences_for(ctx, identity_ref)
                            if identity_ref else [])
                if len(in_force) > 1:
                    return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                        "CORRECTION_REQUIRED", "Ambiguous structural state",
                        f"{identity_ref} has multiple in-force structural consequences "
                        f"{in_force}; refusing rather than silently choosing one"))
                if in_force and not intent:
                    return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                        "CORRECTION_REQUIRED", "Existing identity requires supersession",
                        f"{identity_ref} now has current structural state ({in_force[0]}) that "
                        "was not in force when this was queued; it must explicitly supersede "
                        "that consequence (D18) — resubmit as a revision or a new identity"))
                if intent and intent not in in_force:
                    return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                        "SUPERSEDED_RECORD_USED", "Queued supersession target not current",
                        f"the consequence this queued correction would supersede ({intent}) is "
                        f"no longer {identity_ref}'s current structural state; resubmit against "
                        "the current consequence"))
            elif intent and ctx.store.is_superseded(intent):
                # a non-structure queued correction whose target was superseded since
                # it was queued must not silently re-supersede it
                return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                    "SUPERSEDED_RECORD_USED", "Queued supersession target already superseded",
                    f"the consequence this queued correction would supersede ({intent}) has "
                    "itself been superseded since it was queued; resubmit against current state"))
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

        # D18: explicit supersession for an identity that already has state.
        # NOTE (PR #9 H1): this is read-before-write. In the single-writer pilot
        # (D13) the serial path is fully governed; under TRUE concurrency two
        # first assertions for one identityRecordRef could both pass here before
        # either commits. G2's serialized write path closes that race (see the
        # G2 ticket's folded-in hardening) — it is not a single-writer hole.
        in_force = _in_force_structural_consequences_for(ctx, identity_ref)
        supersedes = ctx.sub.get("supersedesConsequenceRef")
        if len(in_force) > 1:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "CORRECTION_REQUIRED", "Ambiguous structural state",
                f"{identity_ref} has multiple in-force structural consequences "
                f"{in_force}; refusing rather than silently choosing one"))
        if in_force:
            if not supersedes:
                return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                    "CORRECTION_REQUIRED", "Existing identity requires supersession",
                    f"{identity_ref} already has current structural state; submit this "
                    "either as a revision that explicitly supersedes the current "
                    f"structural consequence ({in_force[0]}) or as a new identity with "
                    "a different identityRecordRef"))
            if supersedes != in_force[0]:
                return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                    "SUPERSEDED_RECORD_USED", "Supersession target mismatch",
                    f"supersedesConsequenceRef {supersedes} does not name {identity_ref}'s "
                    f"current structural consequence ({in_force[0]})"))
        elif supersedes:
            # superseding something, but THIS identity has no structural state:
            # the ref belongs to another identity or a non-structural consequence
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "SUPERSEDED_RECORD_USED", "Supersession target not this identity",
                f"supersedesConsequenceRef {supersedes} is not a current structural "
                f"consequence of {identity_ref}"))

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

    This is a provider-owned capability. Its snapshot family and lookup
    implementation are fixed when the provider composes its service bundle;
    the generic validation path never discovers SI services or defaults.
    """

    def __init__(self, *, snapshot_prefix: str, product_lookup):
        self.snapshot_prefix = snapshot_prefix
        self.product_lookup = product_lookup

    def run(self, ctx: GateContext) -> GateRefusal | None:
        product_binding = _verified_product_binding(ctx)
        if not (product_binding and product_binding["bindingState"] == "VERIFIED"):
            return None
        current = current_reference_snapshot(ctx.store, self.snapshot_prefix)
        current_id = current["referenceSnapshotId"] if current else None
        captured_against = ctx.sub.get("capturedAgainstSnapshotRef") \
            or (product_binding.get("referenceSnapshotRefs") or [None])[0]
        if not (current_id and captured_against and captured_against != current_id):
            return None
        event_time = ctx.event_time or ctx.captured_at
        decision_number = product_binding["bindingValue"].get("registrationRef")
        confirmed = (
            self.product_lookup.lookup_by_decision(current_id, decision_number)
            if decision_number else None
        )
        if confirmed is not None:
            valid_until = (confirmed.get("decision", {}).get("validUntil")
                           or confirmed.get("registrationValidUntil") or "")
            if valid_until and valid_until < (event_time or "")[:10]:
                ctx.review_route_reasons.append(runtime_problem(
                    "SUPERSEDED_RECORD_USED", "Registry snapshot discrepancy",
                    f"decision {decision_number} validity ended {valid_until} per "
                    f"current snapshot {current_id}, before the event time; "
                    "discrepancy recorded and routed to review, never silent "
                    "acceptance", severity="WARNING"))
            else:
                ctx.log("VALIDATION", "REGISTRY_REVERIFIED",
                        rationale=f"identity re-verified by decision number "
                                  f"{decision_number} against {current_id}")
        else:
            ctx.review_route_reasons.append(runtime_problem(
                "PRODUCT_BINDING_UNRESOLVED", "Re-verification not confirmable",
                f"the current snapshot {current_id} carries no decision-number "
                f"data for {decision_number or 'this binding'}; identity cannot "
                "be re-confirmed on this surface (regsrCode is a locator, not "
                "identity — D9), so the record routes to review",
                severity="WARNING"))
        return None


class LegacyRegistryReverificationValidator:
    """Explicit config-backed SI compatibility path for legacy tests only."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        return RegistryReverificationValidator(
            snapshot_prefix=REGSR_SNAPSHOT_PREFIX,
            product_lookup=ctx.products,
        ).run(ctx)


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
OPERATION_SEQUENCE = (
    CarrierSchemaValidator(),
    CarrierSemanticsValidator.from_config_for_legacy_tests(),
    ExecutionExtentValidator.from_config_for_legacy_tests(),
    ReferenceResolutionValidator(),
    ActorAttributionValidator(),
    CodeBindingValidator.from_config_for_legacy_tests(),
    LegacyRegistryReverificationValidator(),
)


def _descriptor_recognized_rule_refs(active_profile) -> frozenset[str]:
    return frozenset({
        active_profile.evidence_policy_ref,
        active_profile.profile_ref,
        active_profile.pack_ref,
        active_profile.code_binding_profile_ref,
    })


def _operation_sequence_for_validation_policy(
    validation_policy: dict,
    registry_reverification=None,
) -> tuple:
    sequence = (
        CarrierSchemaValidator(),
        CarrierSemanticsValidator(validation_policy),
        ExecutionExtentValidator(validation_policy),
        ReferenceResolutionValidator(),
        ActorAttributionValidator(),
        CodeBindingValidator(validation_policy),
    )
    if registry_reverification is not None:
        sequence += (registry_reverification,)
    return sequence


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
            if ctx.policy_provider is not None:
                recognized_refs = ctx.policy_provider.recognized_rule_refs
            else:
                recognized_refs = (
                    _descriptor_recognized_rule_refs(ctx.active_profile)
                    if ctx.active_profile is not None else None)
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

        if ctx.policy_provider is None:
            if ctx.active_profile is not None:
                return _validation_policy_refusal(
                    ctx,
                    "descriptor-backed runtime provider services are unavailable",
                )
            operation_sequence = OPERATION_SEQUENCE
        else:
            try:
                validation_policy = ctx.policy_provider.validation_policy()
            except profile_policy.ProfilePolicyError as exc:
                return _validation_policy_refusal(ctx, exc)
            registry_reverification = (
                ctx.runtime_services.registry_reverification
                if ctx.runtime_services is not None else None
            )
            operation_sequence = _operation_sequence_for_validation_policy(
                validation_policy,
                registry_reverification,
            )

        for validator in operation_sequence:
            refusal = validator.run(ctx)
            if refusal:
                return refusal
        # the trace's VALIDATION entry surfaces the attribution decision so
        # both authority decisions are visible on the promotion path
        ctx.log("VALIDATION", "PASS",
                refs=[ctx.attribution_ref] if ctx.attribution_ref else None)
        return CarrierStore().run(ctx) or GatePass()
