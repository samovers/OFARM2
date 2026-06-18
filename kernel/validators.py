"""Named validation units (issue #3): each validator is one concern with one
contract — it inspects the GateContext, appends review-route reasons for
exceptions, and returns a GateRefusal (already logged) to stop the chain or
None to pass. The ValidationGate runs them in the law-pinned order; the
sequence IS the policy and reads as one list.

Refusal vs review-route is each validator's declared posture, mirroring the
SI profile's unresolved-binding behaviors: hard floor breaks refuse
(RETAIN_DRAFT), exceptions route to the advisor queue.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import config, policy, sufficiency
from .context import REGSR_SNAPSHOT_PREFIX, current_reference_snapshot, parse_ts
from .contracts import ContractViolation, UnknownContract, sha256_of
from .problems import runtime_problem
from .stages import GateContext, GatePass, GateRefusal


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


def _verified_product_binding(ctx: GateContext) -> dict | None:
    """The carrier's first CROP_PROTECTION_PRODUCT binding, if any. Resolves
    binding refs kind-checked (a wrong-kind ref is not a binding and never a
    KeyError); CodeBindingValidator refuses wrong-kind refs governably first."""
    bindings = sufficiency.resolved_bindings(
        ctx.store, ctx.sub["payload"].get("agronomicIdentityBindingRefs", []))
    product_bindings = [b for b in bindings
                        if b.get("bindingRole") == "CROP_PROTECTION_PRODUCT"]
    return product_bindings[0] if product_bindings else None


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
        target_ref = ctx.sub.get("reviewTargetAssertionRef")
        if not target_ref:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Acceptance without target",
                "a governance-decision commit requires reviewTargetAssertionRef"))
        row = ctx.store.get_record(target_ref)
        if row is None or row["record_kind"] != "ofarm.assertionrecord.v0.1":
            return _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", runtime_problem(
                "EVIDENCE_REFERENCE_UNAVAILABLE", "Acceptance target unresolved",
                f"{target_ref} does not resolve to a stored AssertionRecord"))
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
        if target["assertionType"] not in policy.ACCEPTANCE_BY_ASSERTION_TYPE:
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "IDENTITY_UNRESOLVED", "Assertion type not acceptable",
                f"{target['assertionType']} has no acceptance path"))
        # D8 holds at the queue door too: self-acceptance covers ROUTINE
        # OPERATION CLAIMS only
        if (target["assertedByPartyRef"] == ctx.acting_party
                and target["assertionType"]
                not in policy.SELF_ACCEPTABLE_ASSERTION_TYPES):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "HUMAN_APPROVAL_REQUIRED", "Self-acceptance out of scope",
                f"self-review covers routine operation claims only (D8); "
                f"{target['assertionType']} asserted by the accepting party "
                "requires a DISTINCT reviewer principal"))
        # a review act is governed, never a bare pointer
        rationale_text = ctx.sub.get("reviewRationale")
        if not (isinstance(rationale_text, str) and rationale_text.strip()):
            return _refusal(ctx, "FAIL_SEMANTIC", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Acceptance without rationale",
                "a review acceptance must state its resolution rationale"))
        for ref in ctx.sub.get("reviewEvidenceRefs") or []:
            ev_row = ctx.store.get_record(ref)
            if ev_row is None or ev_row["record_kind"] != "ofarm.evidencerecord.v0.1":
                return _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", runtime_problem(
                    "EVIDENCE_REFERENCE_UNAVAILABLE", "Review evidence unresolved",
                    f"review evidence {ref} does not resolve to a durable "
                    "EvidenceRecord"))
        ctx.log("VALIDATION", "PASS")
        return None


class ComplianceClaimValidator:
    """A compliance assertion carries a minimal STRUCTURED claim — statement,
    asserted status, recognized governing rules, resolvable farm-contained
    subject — before the sufficiency case even evaluates it."""

    RECOGNIZED_RULE_REFS = frozenset({
        config.EVIDENCE_POLICY_REF, config.PROFILE_REF,
        config.PACK_REF, config.CODE_BINDING_PROFILE_REF})

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
                         if r not in self.RECOGNIZED_RULE_REFS
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
        # and to the promotion emitter (IdentityRecord creation)
        ctx.structure_payload_id = payload[contract.id_field]
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

    def run(self, ctx: GateContext) -> GateRefusal | None:
        payload = ctx.sub["payload"]
        # latest profile instance: the single-profile pilot ships exactly one
        # (the spine guard in context.py refuses ambiguous AS_OF histories)
        profile = ctx.store.find_by_kind(
            "ofarm.agronomiccodebindingprofile.v0.1")[-1]["payload"]
        params = payload.get("actualQuantityParameters", [])
        dose_params = [p for p in params if p["parameterRole"] in ("DOSE", "RATE")]
        if profile["quantityAndUnitPolicy"]["requireQuantityKindAndUnitCode"]:
            bad_units = [p for p in dose_params
                         if not policy.is_resolved_ucum_unit(p.get("unitRef"))
                         or not p.get("quantityKindRef")]
            if not dose_params or bad_units:
                return _refusal(ctx, "FAIL_CARRIER", runtime_problem(
                    "UNIT_UNRESOLVED", "Dose unit unresolved",
                    "the SI profile requires a UCUM unit code and quantity kind on "
                    "every dose; unresolved units block promotion (BLOCK_PROMOTION)"),
                    rationale="dose without resolved UCUM unit code")
        for p in dose_params:
            if not (0 < p["value"] <= policy.DOSE_SANITY_MAX):
                ctx.review_route_reasons.append(runtime_problem(
                    "EVIDENCE_INSUFFICIENT", "Implausible dose",
                    f"dose value {p['value']} is implausible; advisory flag raised "
                    "and routed to advisor review, never a silent block",
                    severity="WARNING"))
        return None


class ExecutionExtentValidator:
    """A non-whole extent must quantify what was treated, and the bound must be
    REAL. A PARTIAL_TARGET_SCOPE / FAILED_PASS / RETREATMENT_AREA / DISPUTED_AREA
    / EXTERNAL_GEOMETRY_REFERENCE claim must carry an inline `area` (value+unit)
    or an extent ref (geometryRef / extentRef / scopeExtentBasisRef) that
    RESOLVES in the store. No bound at all, or a bound whose only ref is
    dangling/fake, is an incomplete carrier — "size treated" is a required SI
    record field — so the claim stays a draft, never silently materialized as
    whole-scope (corrected and resubmitted, like a dose missing its unit).
    M1 has no geometry/extent ingestion path, so a ref bound resolves only once
    such a record exists; the inline `area` is the always-available bound."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        extent = ctx.sub["payload"].get("executionExtent", {})
        if extent.get("extentClass") not in policy.NON_WHOLE_EXTENT_CLASSES:
            return None
        present_refs = [r for r in (extent.get("geometryRef"),
                                    extent.get("extentRef"),
                                    extent.get("scopeExtentBasisRef")) if r]
        if not extent.get("area") and not present_refs:
            return _refusal(ctx, "FAIL_CARRIER", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Partial extent unquantified",
                f"executionExtent.extentClass is {extent.get('extentClass')} but the "
                "carrier states no area, geometryRef, extentRef, or scopeExtentBasisRef; "
                "'size treated' is a required SI record field, so the claim stays a "
                "draft rather than silently materializing as whole-scope (the reason-"
                "code registry has no extent-completeness code — see ERRATA E-004)"),
                rationale="non-whole extent carries no quantified bound")
        # a ref bound must resolve to a RECOGNIZED extent-bound carrier kind —
        # "resolves to something" is not "resolves to the right kind of thing".
        # policy.M1_ALLOWED_EXTENT_BOUND_KINDS is empty in M1 (no extent
        # ingestion surface), so both a dangling ref and a wrong-kind existing
        # record are invalid bounds; inline `area` is the only M1 bound.
        invalid = []
        for ref in present_refs:
            row = ctx.store.get_record(ref)
            if row is None or row["record_kind"] not in policy.M1_ALLOWED_EXTENT_BOUND_KINDS:
                invalid.append(ref)
        if invalid:
            return _refusal(ctx, "FAIL_REFERENCE_RESOLUTION", runtime_problem(
                "EVIDENCE_REFERENCE_UNAVAILABLE", "Partial extent bound unresolved",
                f"executionExtent names extent bound(s) {invalid} that do not "
                "resolve to a recognized extent-bound carrier; M1 accepts only an "
                "inline `area` bound (ref bounds need an extent ingestion surface — "
                "M2; see UNSUPPORTED_SURFACES.md), so the claim stays a draft"),
                rationale=f"unrecognized extent bound refs: {invalid}")
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

    def run(self, ctx: GateContext) -> GateRefusal | None:
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
                "PRODUCT_BINDING_UNRESOLVED", "Binding ref is not a binding",
                f"agronomicIdentityBindingRefs names {wrong_kind}, which do not "
                "resolve to AgronomicIdentityBinding records; a binding ref must "
                "be a governed binding, never another record kind"))
        bindings = sufficiency.resolved_bindings(ctx.store, refs)
        crop_bindings = [b for b in bindings if b.get("bindingRole") == "CROP_SPECIES"]
        product_binding = _verified_product_binding(ctx)
        if product_binding is None or product_binding["bindingState"] != "VERIFIED":
            state = product_binding["bindingState"] if product_binding else "MISSING"
            ctx.review_route_reasons.append(runtime_problem(
                "PRODUCT_BINDING_UNRESOLVED", "Product binding unresolved",
                f"product binding state is {state}; the record stays committable as "
                "a claim, promotion requires review (UNRESOLVED is explicit, never "
                "silent)", severity="WARNING"))
        if not crop_bindings:
            ctx.review_route_reasons.append(runtime_problem(
                "IDENTITY_UNRESOLVED", "Crop binding missing",
                "no EPPO crop binding is linked; the SI profile routes this to review",
                severity="WARNING"))
        return None


class RegistryReverificationValidator:
    """D9: product identity is the decision number + validity dates;
    regsrCode is a page locator, NEVER identity. Re-verification across a
    snapshot advance is identity-grade only where the snapshot carries
    decision-number data; anything weaker routes to review."""

    def run(self, ctx: GateContext) -> GateRefusal | None:
        product_binding = _verified_product_binding(ctx)
        if not (product_binding and product_binding["bindingState"] == "VERIFIED"):
            return None
        current = current_reference_snapshot(ctx.store, REGSR_SNAPSHOT_PREFIX)
        current_id = current["referenceSnapshotId"] if current else None
        captured_against = ctx.sub.get("capturedAgainstSnapshotRef") \
            or (product_binding.get("referenceSnapshotRefs") or [None])[0]
        if not (current_id and captured_against and captured_against != current_id):
            return None
        event_time = ctx.event_time or ctx.captured_at
        decision_number = product_binding["bindingValue"].get("registrationRef")
        confirmed = (ctx.products.lookup_by_decision(current_id, decision_number)
                     if decision_number else None)
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
    CarrierSemanticsValidator(),
    ExecutionExtentValidator(),
    ReferenceResolutionValidator(),
    ActorAttributionValidator(),
    CodeBindingValidator(),
    RegistryReverificationValidator(),
)


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
            return ComplianceClaimValidator().run(ctx) or GatePass()
        if ctx.commit_class == "STRUCTURE_ASSERTION":
            return StructureCarrierValidator().run(ctx) or GatePass()
        if ctx.commit_class != "OPERATION_CLAIM":
            ctx.log("VALIDATION", "PASS")
            return GatePass()

        for validator in OPERATION_SEQUENCE:
            refusal = validator.run(ctx)
            if refusal:
                return refusal
        # the trace's VALIDATION entry surfaces the attribution decision so
        # both authority decisions are visible on the promotion path
        ctx.log("VALIDATION", "PASS",
                refs=[ctx.attribution_ref] if ctx.attribution_ref else None)
        return CarrierStore().run(ctx) or GatePass()
