"""Gate stages (issue #3): the EnforcementChain as small named stages with
narrow contracts, sharing ONE transaction-scoped GateContext.

The stages deliberately do NOT become independent middleware: one commit is
one transaction (D3), and every stage writes through the same cursor so the
reachability link, the gate log, and every emitted record land — or roll
back — together. The decomposition changes who OWNS each decision, never
WHEN anything commits.

Typed results: a stage returns GatePass, GateRefusal (stop the chain, write
the refusal trace), or GateReplay (idempotent short-circuit). Review-routing
is accumulated on the context (routes divert the outcome at the review gate;
they never stop the chain) — exactly the semantics the conformance fixtures
pin.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import policy, sufficiency
from .context import mint, parse_ts
from .contracts import ContractViolation
from .emission import PromotionEmitter, ReplayWriter
from .problems import runtime_problem


# ---------------------------------------------------------------------------
# typed stage results
# ---------------------------------------------------------------------------

@dataclass
class GatePass:
    """The stage passed; anything worth recording is already in the gate
    log / trace via ctx.log — the result carries no payload."""


@dataclass
class GateRefusal:
    gate: str
    outcome: str
    final_outcome: str
    problems: list[dict]


@dataclass
class GateReplay:
    """Idempotent short-circuit: the CommitIngressResult to return as-is."""
    result: dict


# ---------------------------------------------------------------------------
# the transaction-scoped context every stage shares
# ---------------------------------------------------------------------------

@dataclass
class GateContext:
    # services (one transaction, one cursor — D3)
    cur: Any
    store: Any
    authority: Any
    context_assembler: Any
    materializer: Any
    products: Any
    # the submission and its normalized identity
    sub: dict
    request_id: str
    ingested_at: str
    source_digest: str
    commit_class: str = ""
    family: str = ""
    farm_ref: str = ""
    acting_party: str = ""
    idem_key: str = ""
    event_id: str = ""
    assertion_id: str = ""
    envelope: dict | None = None
    envelope_stored: bool = False
    event_time: str | None = None
    captured_at: str = ""
    temporal_problem: dict | None = None
    requested_target: str | None = None
    acceptance_target: str | None = None
    acceptance_payload: dict | None = None   # the target assertion, fetched once
    # stage products
    authz_decision: Any = None
    erp_id: str | None = None
    attribution_ref: str | None = None
    case_payload: dict | None = None
    invalidation_sources: list[str] = field(default_factory=list)
    trigger_source: str | None = None
    # accumulators (ride into the PromotionTrace and CommitIngressResult)
    gate_sequence: list[dict] = field(default_factory=list)
    problems: list[dict] = field(default_factory=list)
    review_route_reasons: list[dict] = field(default_factory=list)
    emitted: dict = field(default_factory=lambda: {
        "assertions": [], "reviews": [], "consequences": []})
    trace_refs: dict = field(default_factory=dict)
    final_outcome: str = "RETAIN_DRAFT"
    in_force_category: str | None = None
    in_force_refs: list[str] = field(default_factory=list)
    materialization_triggered: bool = False

    def log(self, gate: str, outcome: str, *, reason_code=None, rationale=None,
            refs=None) -> None:
        """Every gate outcome lands in BOTH the gate log and the trace's
        gateSequence (PLATFORM.md: zero silent anything)."""
        self.gate_sequence.append({k: v for k, v in {
            "gate": gate, "outcome": outcome, "rationale": rationale,
            "relatedArtifactRefs": refs}.items() if v})
        self.store.log_gate(self.cur, self.request_id, gate, outcome,
                            reason_code=reason_code, rationale=rationale,
                            related_refs=refs)

    def record_authority_decision(self, decision) -> None:
        """Every authority evaluation persists its request/trace/result —
        one helper so no call site can store a partial decision."""
        self.store.insert_record(self.cur, decision.request_payload)
        self.store.insert_record(self.cur, decision.trace_payload)
        self.store.insert_record(self.cur, decision.result_payload)

    def ensure_envelope_stored(self) -> None:
        """Refusals are traceable history, not silence: the normalized draft
        event is recorded even when the chain refuses."""
        if self.envelope and not self.envelope_stored \
                and not self.store.record_exists(self.event_id):
            self.store.insert_record(self.cur, self.envelope)
            self.envelope_stored = True


# ---------------------------------------------------------------------------
# stage: ingress normalization
# ---------------------------------------------------------------------------

class IngressNormalizer:
    """Builds the normalized SemanticEventEnvelope + CommitIngressRequest,
    pre-parses times (junk never enters the envelope), detects idempotent
    replays. Capture is not commitment (Kernel rule 3): this is where a
    device draft becomes a governed submission."""

    def run(self, ctx: GateContext) -> GatePass | GateReplay:
        sub = ctx.sub
        prior = ctx.store.idempotency_lookup(ctx.cur, ctx.idem_key)
        if prior is not None:
            return GateReplay(ReplayWriter().write(ctx, prior))

        if ctx.commit_class not in policy.COMMIT_CLASS_TO_FAMILY:
            raise ContractViolation(f"unknown commit class {ctx.commit_class!r}")
        ctx.family = policy.COMMIT_CLASS_TO_FAMILY[ctx.commit_class]

        event_time = sub.get("eventTime")
        captured_at = sub.get("capturedAt") or ctx.ingested_at
        # only verified-parseable times enter the normalized envelope; junk
        # input is refused at the temporal sub-gate, never stored as if true
        if event_time is not None and parse_ts(event_time) is None:
            ctx.temporal_problem = runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Unparseable event time",
                f"event time {event_time!r} is not a valid timestamp; the claim "
                "stays a draft (note: the reason-code registry has no temporal-"
                "conformance code — see ERRATA E-001)")
            event_time = None
        if parse_ts(captured_at) is None:
            captured_at = ctx.ingested_at
        ctx.event_time, ctx.captured_at = event_time, captured_at

        scopes = sub.get("targetScopes") or [
            {"scopeType": "FARM", "scopeRef": ctx.farm_ref}]
        envelope = {
            "schemaVersion": "ofarm.semanticeventenvelope.v0.1",
            "semanticEventId": ctx.event_id,
            "primaryEventFamily": ctx.family,
            "dominantSemanticConsequence": sub.get(
                "dominantSemanticConsequence",
                f"{ctx.commit_class.lower().replace('_', ' ')} captured"),
            "anchorScopes": scopes,
            "subjectRefs": [sub.get("subjectRef") or ctx.farm_ref],
            # Kernel rule 6: event time (field entry) and record time (server
            # commit) are distinct fields and never collapse.
            "timeSemantics": {k: v for k, v in {
                "eventTime": event_time,
                "observationTime": sub.get("observationTime"),
                "decisionTime": sub.get("decisionTime"),
                "recordTime": ctx.ingested_at}.items() if v},
        }
        if not any(k in envelope["timeSemantics"]
                   for k in ("eventTime", "observationTime", "decisionTime")):
            envelope["timeSemantics"]["eventTime"] = captured_at
        if sub.get("evidenceRefs"):
            envelope["evidenceRefs"] = sub["evidenceRefs"]
        if sub.get("noteText") is not None:
            envelope["notes"] = sub["noteText"]
        ctx.envelope = envelope

        ingress_request = {
            "schemaVersion": "ofarm.commitingressrequest.v0.1",
            "requestId": ctx.request_id,
            "ingestedAt": ctx.ingested_at,
            "ingressChannel": sub.get("ingressChannel", "MANUAL_UI"),
            "commitClass": ctx.commit_class,
            "semanticEventRef": ctx.event_id,
            "actingPartyRef": ctx.acting_party,
            "targetScopes": scopes,
            "idempotencyKey": ctx.idem_key,
            "sourcePayloadDigest": ctx.source_digest,
        }
        for key in ("actingAgentRef", "originatingOfflineQueueRef", "evidenceRefs"):
            if sub.get(key):
                ingress_request[key] = sub[key]
        ctx.requested_target = sub.get("requestedPromotionTarget")
        if ctx.requested_target:
            ingress_request["requestedPromotionTarget"] = ctx.requested_target
        ctx.acceptance_target = (sub.get("reviewTargetAssertionRef")
                                 if ctx.commit_class == "GOVERNANCE_DECISION" else None)
        ctx.store.insert_record(ctx.cur, ingress_request)
        ctx.log("INGRESS_NORMALIZATION", "NORMALIZED_DRAFT")
        return GatePass()


# ---------------------------------------------------------------------------
# stage: authority (default deny; revocation re-check)
# ---------------------------------------------------------------------------

class AuthorityGate:
    def run(self, ctx: GateContext) -> GatePass | GateRefusal:
        sub = ctx.sub
        decision = ctx.authority.evaluate(
            acting_party_ref=ctx.acting_party,
            action_class=policy.COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS[ctx.commit_class],
            action_stage="PROMOTION",
            scope={"scopeType": "FARM", "scopeRef": ctx.farm_ref},
            acting_agent_ref=sub.get("actingAgentRef"),
            ai_assistance=sub.get("aiAssistance"),
            revocation_check_required=True,
            revocation_disposition=policy.revocation_disposition(
                ctx.commit_class, sub.get("ingressChannel", "MANUAL_UI")),
        )
        ctx.record_authority_decision(decision)
        ctx.authz_decision = decision
        ctx.trace_refs["authorizationDecisionResultRef"] = \
            decision.result_payload["resultId"]
        authz_refs = [decision.request_payload["requestId"],
                      decision.result_payload["resultId"],
                      decision.trace_payload["traceId"]]
        if decision.outcome == "ALLOW":
            ctx.log("AUTHORITY", "ALLOW", refs=authz_refs)
            return GatePass()
        if decision.outcome == "REQUIRE_REVIEW":
            ctx.log("AUTHORITY", "REQUIRE_REVIEW",
                    reason_code=decision.problems[0]["reasonCode"]
                                if decision.problems else None,
                    rationale=decision.result_payload["reasonSummary"],
                    refs=authz_refs)
            return GateRefusal("AUTHORITY", "REQUIRE_REVIEW", "REQUIRE_REVIEW",
                               decision.problems)
        # DENY | REQUIRE_HUMAN_APPROVAL
        ctx.log("AUTHORITY", decision.outcome,
                reason_code=decision.problems[0]["reasonCode"]
                            if decision.problems else "AUTHORITY_DENIED",
                rationale=decision.result_payload["reasonSummary"],
                refs=authz_refs)
        final = "DENY" if decision.outcome == "DENY" else "REQUIRE_REVIEW"
        return GateRefusal("AUTHORITY", decision.outcome, final,
                           decision.problems)


# ---------------------------------------------------------------------------
# stage: envelope persistence (after validation confirmed the carrier)
# ---------------------------------------------------------------------------

class EnvelopePersist:
    """The normalized envelope becomes authoritative once validation has
    confirmed the carrier; the carrier ref rides the envelope. Its
    reachability edge lands with the trace (same transaction, D3)."""

    def run(self, ctx: GateContext) -> GatePass:
        if ctx.erp_id:
            ctx.envelope["executionRecordPayloadRefs"] = [ctx.erp_id]
        ctx.store.insert_record(ctx.cur, ctx.envelope)
        ctx.envelope_stored = True
        if ctx.commit_class == "COMPLIANCE_ASSERTION":
            # the validated claim fields become a durable ComplianceClaim
            # carrier record (candidate contract, whose closed shape IS the
            # lawful claim) linked to the event, so a later review act
            # re-evaluates exactly what was claimed — never tunneled through
            # the envelope's narrative notes (steward review of PR #4,
            # finding 3). Validation has already confirmed shape and subject
            # containment; like the ExecutionRecordPayload, the carrier is
            # stored where it is confirmed, not promotion-emitted.
            claim = ctx.sub["payload"]["complianceClaim"]
            claim_record = {
                "schemaVersion": "ofarm.complianceclaim.v0.1",
                "complianceClaimId": mint("compclaim"),
                "statement": claim["statement"],
                "assertedStatus": claim["assertedStatus"],
                "governingRuleRefs": claim["governingRuleRefs"],
                "subjectScopeRef": claim["subjectScopeRef"],
                "anchorScopes": [
                    {"scopeType": "FARM", "scopeRef": ctx.farm_ref}],
                "sourceEventRef": ctx.event_id,
            }
            ctx.store.insert_record(ctx.cur, claim_record)
            ctx.store.add_edge(ctx.cur, "COMPLIANCE_CLAIM", ctx.event_id,
                               claim_record["complianceClaimId"])
        return GatePass()


# ---------------------------------------------------------------------------
# stage: static profile applicability (ContextSnapshot assembly)
# ---------------------------------------------------------------------------

class ProfileApplicabilityGate:
    def run(self, ctx: GateContext) -> GatePass:
        snapshot = ctx.context_assembler.assemble(ctx.cur, ctx.farm_ref)
        ctx.log("PACK_PROFILE_APPLICABILITY", "APPLICABLE",
                refs=[snapshot["contextSnapshotId"]])
        return GatePass()


# ---------------------------------------------------------------------------
# stage: evidence sufficiency (auto-generated cases, never hand-authored)
# ---------------------------------------------------------------------------

class EvidenceSufficiencyGate:
    def run(self, ctx: GateContext) -> GatePass | GateRefusal:
        if ctx.acceptance_target:
            case = sufficiency.build_acceptance_case(
                ctx.store, ctx.sub, ctx.farm_ref, ctx.acceptance_payload)
            if case["outcome"]["decision"] == "REFUSE":
                ctx.log("EVIDENCE_SUFFICIENCY", "INSUFFICIENT",
                        reason_code="EVIDENCE_INSUFFICIENT",
                        rationale=case["outcome"]["rationale"])
                return GateRefusal(
                    "EVIDENCE_SUFFICIENCY", "INSUFFICIENT", "RETAIN_DRAFT",
                    [runtime_problem(
                        "EVIDENCE_INSUFFICIENT", "Acceptance floor unmet",
                        case["outcome"]["rationale"],
                        suggested_remediation="the target claim stays queued; it "
                        "cannot be accepted without its durable evidence floor")])
            ctx.store.insert_record(ctx.cur, case)
            ctx.trace_refs["evidenceSufficiencyCaseRef"] = case["sufficiencyCaseId"]
            ctx.case_payload = case
            ctx.log("EVIDENCE_SUFFICIENCY",
                    "SATISFIED" if case["outcome"]["decision"] == "ALLOW"
                    else "SATISFIED_WITH_EXCEPTIONS",
                    rationale=case["outcome"]["rationale"])
            return GatePass()

        if ctx.commit_class in ("OPERATION_CLAIM", "COMPLIANCE_ASSERTION"):
            case, floor_failures = sufficiency.build_floor_case(
                ctx.store, ctx.sub, ctx.commit_class, ctx.farm_ref,
                ctx.assertion_id, ctx.erp_id)
            if case["outcome"]["decision"] == "REFUSE":
                ctx.log("EVIDENCE_SUFFICIENCY", "INSUFFICIENT",
                        reason_code="EVIDENCE_INSUFFICIENT",
                        rationale=case["outcome"]["rationale"])
                return GateRefusal(
                    "EVIDENCE_SUFFICIENCY", "INSUFFICIENT", "RETAIN_DRAFT",
                    [runtime_problem(
                        "EVIDENCE_INSUFFICIENT", "Evidence floor unmet",
                        case["outcome"]["rationale"],
                        suggested_remediation="attach the missing floor items and "
                        "resubmit; the claim stays a draft")])
            ctx.case_payload = case
            ctx.review_route_reasons.extend(floor_failures)
            ctx.log("EVIDENCE_SUFFICIENCY", "SATISFIED")
            return GatePass()

        ctx.log("EVIDENCE_SUFFICIENCY", "NOT_REQUIRED",
                rationale="sufficiency cases are generated only at operation-claim "
                          "promotion and DocumentAssembly freeze (PROFILE.md)")
        return GatePass()


# ---------------------------------------------------------------------------
# stage: review / promotion (D8 self-review; queue acceptance; routing)
# ---------------------------------------------------------------------------

class ReviewPromotionGate:
    def run(self, ctx: GateContext) -> GatePass | GateRefusal:
        emitter = PromotionEmitter(ctx)
        sub = ctx.sub

        # D8 scopes self-review to ROUTINE OPERATION CLAIMS. A compliance
        # assertion reviewed by its own asserter is outside that scope and
        # outside the pilot's claim limits — it routes to the advisor queue.
        if (ctx.commit_class == "COMPLIANCE_ASSERTION" and sub.get("confirmAccept")
                and sub.get("reviewerPartyRef", ctx.acting_party) == ctx.acting_party):
            ctx.review_route_reasons.append(runtime_problem(
                "HUMAN_APPROVAL_REQUIRED", "Self-review out of scope",
                "self-review covers routine operation claims only (D8); a "
                "compliance assertion requires a distinct reviewer and routes "
                "to the advisor queue", severity="WARNING"))

        # A body-named DISTINCT reviewer is a forgeable review act: the claim
        # lands in the queue; the reviewer accepts under their OWN principal
        # via a GOVERNANCE_DECISION commit.
        if (sub.get("confirmAccept")
                and sub.get("reviewerPartyRef") not in (None, ctx.acting_party)):
            ctx.review_route_reasons.append(runtime_problem(
                "HUMAN_APPROVAL_REQUIRED", "Distinct reviewer requires own act",
                f"reviewer {sub['reviewerPartyRef']} must accept under their own "
                "transport principal (GOVERNANCE_DECISION commit / review "
                "acceptance); a reviewer named inside the submitter's request "
                "is forgeable and never promotes", severity="WARNING"))

        promotes = ctx.commit_class in policy.COMMIT_CLASS_TO_PROMOTION_TARGET

        if ctx.acceptance_target:
            emitter.emit_queue_acceptance()
            return GatePass()

        if not promotes:
            reason = policy.NON_PROMOTING_RETAIN_REASONS.get(
                ctx.commit_class, policy.NON_PROMOTING_DEFAULT_REASON)
            ctx.log("REVIEW_PROMOTION", "RETAIN_DRAFT", rationale=reason)
            ctx.final_outcome = "RETAIN_DRAFT"
            return GatePass()

        if ctx.review_route_reasons:
            # exceptions route to the advisor queue (D8) — never silent accept
            emitter.emit_pending_assertion(amend_case_for_routing=True)
            ctx.problems.extend(ctx.review_route_reasons)
            ctx.log("REVIEW_PROMOTION", "REQUIRE_REVIEW",
                    reason_code=ctx.review_route_reasons[0]["reasonCode"],
                    rationale="exception routes to the advisor review queue "
                              "(self-review policy covers routine claims only)")
            ctx.final_outcome = "REQUIRE_REVIEW"
            return GatePass()

        if not sub.get("confirmAccept"):
            emitter.emit_pending_assertion(amend_case_for_routing=False)
            ctx.log("REVIEW_PROMOTION", "RETAIN_DRAFT",
                    rationale="no review act: capture is not commitment (Kernel rule 3)")
            ctx.final_outcome = "RETAIN_DRAFT"
            return GatePass()

        # the deliberate confirm-accept step IS the review act (D8) —
        # SELF-review only: the reviewer is the transport-bound acting party.
        # REVIEW_ACCEPT authority is checked mechanically; self-review cannot
        # bypass the gates above.
        review_auth = ctx.authority.evaluate(
            acting_party_ref=ctx.acting_party, action_class="REVIEW_ACCEPT",
            action_stage="PROMOTION",
            scope={"scopeType": "FARM", "scopeRef": ctx.farm_ref})
        ctx.record_authority_decision(review_auth)
        if not review_auth.allowed:
            ctx.log("REVIEW_PROMOTION", "REQUIRE_REVIEW",
                    reason_code="AUTHORITY_DENIED",
                    rationale=f"{ctx.acting_party} holds no REVIEW_ACCEPT for "
                              f"{ctx.farm_ref}")
            return GateRefusal("REVIEW_PROMOTION", "REQUIRE_REVIEW",
                               "REQUIRE_REVIEW", review_auth.problems)

        emitter.emit_self_review_promotion()
        return GatePass()


# ---------------------------------------------------------------------------
# stage: current-state materialization (after acceptance only)
# ---------------------------------------------------------------------------

class MaterializationGate:
    def run(self, ctx: GateContext) -> GatePass:
        ctx.materializer.invalidate_for_sources(
            ctx.cur, ctx.invalidation_sources or [ctx.trigger_source],
            trigger_family="BASIS_ADVANCED",
            trigger_source_ref=ctx.trigger_source,
            farm_scope_ref=ctx.farm_ref,
            reason_code="TRUTH_BASIS_ADVANCED")
        mat = ctx.materializer.recompute(ctx.cur, ctx.farm_ref)
        # NOTE: no materializationResultRef on the trace — the commit-time
        # recompute emits Basis+Snapshot, not a boundary Result; those
        # receipts ride the gateSequence entry below
        ctx.materialization_triggered = True
        ctx.log("CURRENT_STATE_MATERIALIZATION", "UPDATED",
                refs=[mat["basisRef"], mat["snapshotRef"]])
        return GatePass()
