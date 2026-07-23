"""Record emission (issue #3): every authoritative record the pipeline mints
— assertions, review decisions, accepted consequences, traces, results — is
created HERE, in one obvious home, with its traceability edges. The
self-review path and the queue-acceptance path share the same emitter, so
the two promotion flavors can never drift apart.

The PromotionTraceWriter owns reachability accounting: the PromotionTrace,
its PROMOTION_EMITS edges, the CommitIngressResult, and the idempotency
claim land together in the SAME transaction as everything they prove (D3).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from . import policy, sufficiency
from .context import mint, now_iso
from .problems import runtime_problem

if TYPE_CHECKING:   # type-only: keeps stages -> emission imports acyclic
    from .stages import GateContext


def submission_evidence_refs(sub: dict) -> list:
    """Evidence refs the submission actually carries — the carrier payload's,
    else the top-level submission's, else none. The single source of truth for
    'did this submission bring evidence', shared by the emitter and the
    evidence-sufficiency gate so the floor it enforces and the refs it writes
    can never diverge."""
    return ((sub.get("payload") or {}).get("evidenceRefs")
            or sub.get("evidenceRefs") or [])


class PromotionEmitter:
    """Owns AssertionRecord / ReviewDecision / AcceptedEventConsequence
    creation and the edges required for traceability."""

    def __init__(self, ctx: "GateContext"):
        self.ctx = ctx

    # ---------------------------------------------------------------- build --

    def _submission_evidence_refs(self) -> list:
        return submission_evidence_refs(self.ctx.sub)

    def _build_assertion(self, claim_state: str) -> dict:
        ctx, sub = self.ctx, self.ctx.sub
        assertion = {
            "schemaVersion": "ofarm.assertionrecord.v0.1",
            "assertionRecordId": ctx.assertion_id,
            "assertionType": policy.COMMIT_CLASS_TO_ASSERTION_TYPE.get(
                ctx.commit_class, "OTHER_ASSERTION"),
            "subject": {"subjectType": sub.get("subjectType", "FARM"),
                        "subjectRef": sub.get("subjectRef", ctx.farm_ref)},
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": ctx.farm_ref}],
            "assertedByPartyRef": ctx.acting_party,
            "assertedAt": now_iso(),
            "claimState": claim_state,
            "evidenceRefs": self._submission_evidence_refs(),
        }
        if sub.get("eventTime"):
            assertion["occurrenceTime"] = sub["eventTime"]
        if ctx.erp_id:
            assertion["executionRecordPayloadRefs"] = [ctx.erp_id]
        # No evidence backfill: the AssertionRecord evidence floor (minItems:1)
        # is met by real submitted evidence, never by self-referencing the
        # captured event (Kernel rule 4: a claim is not its own proof). A
        # promoting class with no evidence is refused at the evidence-
        # sufficiency gate before emission, so evidenceRefs is non-empty here.
        return assertion

    def _link_assertion(self) -> None:
        ctx = self.ctx
        ctx.store.add_edge(ctx.cur, "EVENT_SOURCE", ctx.assertion_id, ctx.event_id)
        ctx.store.add_edge(ctx.cur, "AUTHORITY_BASIS", ctx.assertion_id,
                           ctx.authz_decision.result_payload["resultId"])
        if ctx.attribution_ref:
            # second authority decision: the named-actor attribution basis is
            # reachable from the assertion exactly like submitter authority
            ctx.store.add_edge(ctx.cur, "AUTHORITY_BASIS", ctx.assertion_id,
                               ctx.attribution_ref)
        for ev in self._submission_evidence_refs():
            if ctx.store.record_exists(ev):
                ctx.store.add_edge(ctx.cur, "EVIDENCE", ctx.assertion_id, ev)

    def _emit_assertion(self, claim_state: str) -> None:
        ctx = self.ctx
        assertion = self._build_assertion(claim_state)
        ctx.store.insert_record(ctx.cur, assertion)
        ctx.emitted["assertions"].append(ctx.assertion_id)
        self._link_assertion()

    def _store_case(self, amend_for_routing: bool) -> None:
        ctx = self.ctx
        if not ctx.case_payload:
            return
        if amend_for_routing:
            sufficiency.amend_case_for_routing(ctx.case_payload,
                                               ctx.review_route_reasons)
        ctx.store.insert_record(ctx.cur, ctx.case_payload)
        ctx.trace_refs["evidenceSufficiencyCaseRef"] = \
            ctx.case_payload["sufficiencyCaseId"]

    def _ensure_identity_record(self, event_ref: str) -> None:
        """At promotion, materialize the durable IdentityRecord for a structure
        assertion from its typed payload carrier (event -> STRUCTURE_PAYLOAD ->
        payload, linked at EnvelopePersist). Created only on acceptance, so a
        refused or still-queued structure assertion never leaves a phantom
        identity. A superseding assertion about an EXISTING identity does not
        recreate it — the identity registry derives the current payload from
        in-force structural consequences, never editing the prior record
        (Kernel rule 1). Generic over identity type (policy map); no scheme
        logic. A no-op for any non-structure promotion (no such edge)."""
        ctx = self.ctx
        edges = ctx.store.edges_from(event_ref, "STRUCTURE_PAYLOAD")
        if not edges:
            return
        payload_ref = edges[0]["dst_record_id"]
        payload = ctx.store.get_payload(payload_ref)
        if payload is None:
            return
        identity_ref = payload["identityRecordRef"]
        if ctx.store.record_exists(identity_ref):
            return   # revision/supersession: the identity is already durable
        identity_type = policy.STRUCTURE_PAYLOAD_IDENTITY_TYPE[payload["schemaVersion"]]
        # the structure AssertionRecord that introduced the identity, via the
        # event's EVENT_SOURCE edge (resolves on both promotion flavors)
        creators = [e["src_record_id"]
                    for e in ctx.store.edges_to(event_ref, "EVENT_SOURCE")
                    if (r := ctx.store.get_record(e["src_record_id"])) is not None
                    and r["record_kind"] == "ofarm.assertionrecord.v0.1"]
        t = now_iso()
        # NOTE: currentPayloadRef is deliberately NOT set. The IdentityRecord is
        # append-only, so it cannot track the current payload after a later
        # supersession — the identity registry derives "current payload" from
        # in-force structural consequences (Kernel rule 5). createdByAssertionRecordRef
        # records the creating commit; the creation payload is reachable through
        # that assertion's event -> STRUCTURE_PAYLOAD edge (PR #9 review, minor 4).
        identity = {
            "schemaVersion": "ofarm.identityrecord.v0.1",
            "identityRecordId": identity_ref,
            "identityType": identity_type,
            "lifecycleState": "ACTIVE",
            "createdAt": t,
            "recordedAt": t,
        }
        if creators:
            identity["createdByAssertionRecordRef"] = creators[0]
        # anchorScopes minItems is 1: the farm is the top scope (no self-anchor),
        # every other identity anchors on the authorized farm (matches the M1
        # demo's field/equipment/crop-cycle anchoring)
        if identity_type != "FARM":
            identity["anchorScopes"] = [{"scopeType": "FARM", "scopeRef": ctx.farm_ref}]
        ctx.store.insert_record(ctx.cur, identity)

    # ------------------------------------------------------- emission flows --

    def emit_pending_assertion(self, *, amend_case_for_routing: bool) -> None:
        """The claim lands in the queue (or stays a captured draft)."""
        self._emit_assertion("PENDING_REVIEW")
        self._store_case(amend_for_routing=amend_case_for_routing)
        # a queued CORRECTION remembers its supersession target so the eventual
        # reviewer acceptance can retire the prior consequence — supersession
        # takes effect on acceptance, never while the claim is only pending
        superseded = self.ctx.sub.get("supersedesConsequenceRef")
        if superseded:
            self.ctx.store.add_edge(self.ctx.cur, "LINEAGE_SUPERSEDES_INTENT",
                                    self.ctx.assertion_id, superseded)

    def emit_self_review_promotion(self) -> None:
        """The deliberate confirm-accept step is the review act (D8):
        assertion IN_FORCE, ReviewDecision by the transport-bound submitter,
        AcceptedEventConsequence, supersession lineage, all edge-linked."""
        ctx, sub = self.ctx, self.ctx.sub
        self._emit_assertion("IN_FORCE")
        self._store_case(amend_for_routing=False)

        review_id = mint("review")
        review = {
            "schemaVersion": "ofarm.reviewdecision.v0.1",
            "reviewDecisionId": review_id,
            "reviewedArtifactFamily": "ASSERTION_RECORD",
            "reviewedArtifactRef": ctx.assertion_id,
            "reviewAction": "REVIEW_ACCEPT",
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": ctx.farm_ref}],
            "decidedByPartyRef": ctx.acting_party,
            "decidedAt": now_iso(),
            "decisionOutcomeState": "ACCEPTED",
            "notes": "self-review: the deliberate confirm-and-accept step is the "
                     "review act (D8); sufficient for record-keeping use, "
                     "insufficient for certification-grade claims",
        }
        ctx.store.insert_record(ctx.cur, review)
        ctx.emitted["reviews"].append(review_id)
        ctx.store.add_edge(ctx.cur, "REVIEW", ctx.assertion_id, review_id)

        target = ctx.requested_target or \
            policy.COMMIT_CLASS_TO_PROMOTION_TARGET[ctx.commit_class]
        consequence_id = mint("conseq")
        consequence = {
            "schemaVersion": "ofarm.acceptedeventconsequence.v0.1",
            "acceptedEventConsequenceId": consequence_id,
            "consequenceType": policy.PROMOTION_TARGET_TO_CONSEQUENCE_TYPE.get(
                target, "OTHER_CONSEQUENCE"),
            "sourceEventRef": ctx.event_id,
            "acceptedByReviewDecisionRef": review_id,
            "subject": {"subjectType": sub.get("subjectType", "FARM"),
                        "subjectRef": sub.get("subjectRef", ctx.farm_ref)},
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": ctx.farm_ref}],
            "acceptedAt": now_iso(),
            "inForceState": "IN_FORCE",
        }
        if ctx.event_time:
            consequence["effectiveFrom"] = ctx.event_time
        if ctx.erp_id:
            consequence["executionRecordPayloadRefs"] = [ctx.erp_id]
        superseded = sub.get("supersedesConsequenceRef")
        if superseded:
            consequence["notes"] = f"supersedes {superseded} (correction is supersession)"
        ctx.store.insert_record(ctx.cur, consequence)
        ctx.emitted["consequences"].append(consequence_id)
        ctx.store.add_edge(ctx.cur, "REVIEW", consequence_id, review_id)
        ctx.store.add_edge(ctx.cur, "EVENT_SOURCE", consequence_id, ctx.event_id)
        if superseded:
            ctx.store.add_edge(ctx.cur, "LINEAGE_SUPERSEDES",
                               consequence_id, superseded)

        # a structure assertion materializes its durable IdentityRecord here —
        # only on acceptance, never for a refused or queued capture (G1)
        self._ensure_identity_record(ctx.event_id)

        ctx.log("REVIEW_PROMOTION", "PROMOTE_ACCEPTED", refs=[review_id])
        ctx.final_outcome = "PROMOTE_ACCEPTED"
        ctx.in_force_category = target
        ctx.in_force_refs = [consequence_id]
        ctx.trigger_source = consequence_id
        ctx.invalidation_sources = [superseded] if superseded else [consequence_id]

    def emit_queue_acceptance(self) -> None:
        """Queue acceptance: the reviewer's OWN governed act. REVIEW_ACCEPT
        was already evaluated for the transport-bound acting party at the
        AUTHORITY gate; this promotes the TARGET assertion's consequence
        carrying the reviewer's resolution rationale and evidence."""
        ctx, sub = self.ctx, self.ctx.sub
        target_payload = ctx.acceptance_payload
        review_id = mint("review")
        review = {
            "schemaVersion": "ofarm.reviewdecision.v0.1",
            "reviewDecisionId": review_id,
            "reviewedArtifactFamily": "ASSERTION_RECORD",
            "reviewedArtifactRef": ctx.acceptance_target,
            "reviewAction": "REVIEW_ACCEPT",
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": ctx.farm_ref}],
            "decidedByPartyRef": ctx.acting_party,
            "decidedAt": now_iso(),
            "decisionOutcomeState": "ACCEPTED",
            # the review act carries its own resolution rationale —
            # validated non-empty at the validation gate
            "notes": "resolution: " + sub["reviewRationale"].strip(),
        }
        if sub.get("reviewEvidenceRefs"):
            review["evidenceRefs"] = sub["reviewEvidenceRefs"]
        ctx.store.insert_record(ctx.cur, review)
        ctx.emitted["reviews"].append(review_id)
        ctx.store.add_edge(ctx.cur, "REVIEW", ctx.acceptance_target, review_id)
        for ev in sub.get("reviewEvidenceRefs") or []:
            ctx.store.add_edge(ctx.cur, "EVIDENCE", review_id, ev)

        event_edges = ctx.store.edges_from(ctx.acceptance_target, "EVENT_SOURCE")
        orig_event = (event_edges[0]["dst_record_id"] if event_edges
                      else ctx.event_id)
        category, ctype = policy.ACCEPTANCE_BY_ASSERTION_TYPE[
            target_payload["assertionType"]]
        consequence_id = mint("conseq")
        consequence = {
            "schemaVersion": "ofarm.acceptedeventconsequence.v0.1",
            "acceptedEventConsequenceId": consequence_id,
            "consequenceType": ctype,
            "sourceEventRef": orig_event,
            "acceptedByReviewDecisionRef": review_id,
            "subject": target_payload["subject"],
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": ctx.farm_ref}],
            "acceptedAt": now_iso(),
            "inForceState": "IN_FORCE",
        }
        if target_payload.get("occurrenceTime"):
            consequence["effectiveFrom"] = target_payload["occurrenceTime"]
        if target_payload.get("executionRecordPayloadRefs"):
            consequence["executionRecordPayloadRefs"] = \
                target_payload["executionRecordPayloadRefs"]
        # a queued CORRECTION carries its supersession to acceptance: retire
        # the prior consequence (LINEAGE_SUPERSEDES) so it leaves force, exactly
        # as the self-review path does — a queued correction must not become a
        # second in-force consequence (PR #9 review, blocker 3)
        intent = ctx.store.edges_from(ctx.acceptance_target, "LINEAGE_SUPERSEDES_INTENT")
        superseded = intent[0]["dst_record_id"] if intent else None

        ctx.store.insert_record(ctx.cur, consequence)
        ctx.emitted["consequences"].append(consequence_id)
        ctx.store.add_edge(ctx.cur, "REVIEW", consequence_id, review_id)
        ctx.store.add_edge(ctx.cur, "EVENT_SOURCE", consequence_id, orig_event)
        if superseded:
            ctx.store.add_edge(ctx.cur, "LINEAGE_SUPERSEDES", consequence_id, superseded)

        # a queued structure assertion materializes its IdentityRecord at the
        # reviewer's acceptance, from the ORIGINAL event's payload carrier (G1)
        self._ensure_identity_record(orig_event)

        ctx.log("REVIEW_PROMOTION", "PROMOTE_ACCEPTED", refs=[review_id])
        ctx.final_outcome = "PROMOTE_ACCEPTED"
        ctx.in_force_category = category
        ctx.in_force_refs = [consequence_id]
        ctx.trigger_source = consequence_id
        ctx.invalidation_sources = [superseded] if superseded else [consequence_id]

    def emit_queue_rejection(self) -> None:
        """Queue rejection (M2 G5-2): the reviewer's OWN governed decline. The
        append-only mirror of emit_queue_acceptance MINUS the consequence —
        appends a ReviewDecision (REVIEW_REJECT_OR_CONTEST / REJECTED) + a REVIEW
        edge, and emits NO AcceptedEventConsequence and resolves NO supersession:
        a declined claim promotes nothing and retires nothing, so the prior
        in-force consequence (if the rejected claim was a correction) stays in
        force and its supersession intent is abandoned (docs/REVIEW_DISPUTE_
        SEMANTICS.md §3). The decision registers in ctx.emitted['reviews'] so the
        generic PromotionTraceWriter carries it as a receipt (D3); the queued
        assertion is never edited — its terminal REJECTED disposition is derived
        from this REVIEW edge. Commit outcome is RETAIN_DRAFT (nothing promoted)."""
        ctx, sub = self.ctx, self.ctx.sub
        review_id = mint("review")
        review = {
            "schemaVersion": "ofarm.reviewdecision.v0.1",
            "reviewDecisionId": review_id,
            "reviewedArtifactFamily": "ASSERTION_RECORD",
            "reviewedArtifactRef": ctx.acceptance_target,
            "reviewAction": "REVIEW_REJECT_OR_CONTEST",
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": ctx.farm_ref}],
            "decidedByPartyRef": ctx.acting_party,
            "decidedAt": now_iso(),
            "decisionOutcomeState": "REJECTED",
            # the decline carries its own rationale — validated non-empty at the
            # validation gate; no resultingAcceptedConsequenceRefs (nothing promoted)
            "notes": "rejection: " + sub["reviewRationale"].strip(),
        }
        if sub.get("reviewEvidenceRefs"):
            review["evidenceRefs"] = sub["reviewEvidenceRefs"]
        ctx.store.insert_record(ctx.cur, review)
        ctx.emitted["reviews"].append(review_id)
        ctx.store.add_edge(ctx.cur, "REVIEW", ctx.acceptance_target, review_id)
        for ev in sub.get("reviewEvidenceRefs") or []:
            ctx.store.add_edge(ctx.cur, "EVIDENCE", review_id, ev)

        ctx.log("REVIEW_PROMOTION", "RETAIN_DRAFT", refs=[review_id])
        ctx.final_outcome = "RETAIN_DRAFT"

    def emit_queue_contest(self) -> None:
        """Queue contest (M2 G5-4): a reviewer's append-only dispute against an
        ALREADY IN-FORCE consequence. Appends a ReviewDecision (CONTESTED) + a
        DISPUTE edge (consequence -> decision); emits NO consequence and NO
        LINEAGE_SUPERSEDES — a contest promotes and retires nothing, so the
        disputed consequence is never edited and STAYS in force, flagged. It then
        stales every dependent materialization (D12) so the next read re-qualifies
        disputeStatus. Resolution is later, by a CORRECTION that supersedes the
        consequence (spec §6). Commit outcome RETAIN_DRAFT; the decision registers
        in ctx.emitted['reviews'] for the generic PromotionTrace receipt (D3)."""
        ctx, sub = self.ctx, self.ctx.sub
        target = ctx.acceptance_target   # the in-force consequence
        review_id = mint("review")
        review = {
            "schemaVersion": "ofarm.reviewdecision.v0.1",
            "reviewDecisionId": review_id,
            "reviewedArtifactFamily": "ACCEPTED_EVENT_CONSEQUENCE",
            "reviewedArtifactRef": target,
            "reviewAction": "REVIEW_REJECT_OR_CONTEST",
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": ctx.farm_ref}],
            "decidedByPartyRef": ctx.acting_party,
            "decidedAt": now_iso(),
            "decisionOutcomeState": "CONTESTED",
            "notes": "dispute: " + sub["reviewRationale"].strip(),
        }
        if sub.get("reviewEvidenceRefs"):
            review["evidenceRefs"] = sub["reviewEvidenceRefs"]
        ctx.store.insert_record(ctx.cur, review)
        ctx.emitted["reviews"].append(review_id)
        ctx.store.add_edge(ctx.cur, "DISPUTE", target, review_id)
        for ev in sub.get("reviewEvidenceRefs") or []:
            ctx.store.add_edge(ctx.cur, "EVIDENCE", review_id, ev)

        # D12 basis-set staleness: the disputed consequence is a basis member
        # whose truth state changed — stale dependent materializations so they
        # recompute and re-qualify disputed on the next read (spec §6.6). The
        # dispute is recorded authoritatively on the DISPUTE edge; this trace only
        # propagates staleness (BASIS_ADVANCED family, dispute-specific reason).
        ctx.runtime_services.materializer.invalidate_for_sources(
            ctx.cur, [target],
            trigger_family="BASIS_ADVANCED",
            trigger_source_ref=review_id,
            farm_scope_ref=ctx.farm_ref,
            reason_code="TRUTH_BASIS_DISPUTED")

        ctx.log("REVIEW_PROMOTION", "RETAIN_DRAFT", refs=[review_id])
        ctx.final_outcome = "RETAIN_DRAFT"


class PromotionTraceWriter:
    """One obvious home for reachability and emitted-ref accounting: the
    PromotionTrace, its PROMOTION_EMITS edges, the CommitIngressResult, and
    the idempotency claim — same transaction as the commit (D3)."""

    def write(self, ctx: "GateContext") -> dict:
        trace_id = mint("promtrace")
        trace = {
            "schemaVersion": "ofarm.promotiontrace.v0.1",
            "promotionTraceId": trace_id,
            "requestId": ctx.request_id,
            "evaluatedAt": now_iso(),
            "semanticEventRef": ctx.event_id,
            "commitClass": ctx.commit_class,
            "primaryEventFamily": ctx.family,
            "idempotencyKey": ctx.idem_key,
            "idempotencyDisposition": "NEW_REQUEST",
            "gateSequence": ctx.gate_sequence,
            "finalOutcome": ctx.final_outcome,
            "traceSummary": f"{ctx.commit_class} via {len(ctx.gate_sequence)} "
                            f"gates -> {ctx.final_outcome}",
            **ctx.trace_refs,
        }
        if ctx.in_force_category:
            trace["inForceResultCategory"] = ctx.in_force_category
        for key, refs in (("emittedAssertionRecordRefs", ctx.emitted["assertions"]),
                          ("emittedReviewDecisionRefs", ctx.emitted["reviews"]),
                          ("emittedAcceptedConsequenceRefs", ctx.emitted["consequences"])):
            if refs:
                trace[key] = refs
        ctx.store.insert_record(ctx.cur, trace)
        # every listed ref was inserted earlier in THIS transaction (the
        # envelope by the shell, the rest by the emitter), so each gets its
        # reachability edge unconditionally
        for ref in ([ctx.event_id] + ctx.emitted["assertions"]
                    + ctx.emitted["reviews"] + ctx.emitted["consequences"]):
            ctx.store.add_edge(ctx.cur, "PROMOTION_EMITS", trace_id, ref)

        result = {
            "schemaVersion": "ofarm.commitingressresult.v0.1",
            "resultId": mint("cires"),
            "requestId": ctx.request_id,
            "processedAt": now_iso(),
            "decisionOutcome": ctx.final_outcome,
            "commitClass": ctx.commit_class,
            "primaryEventFamily": ctx.family,
            "semanticEventRef": ctx.event_id,
            "idempotencyDisposition": "NEW_REQUEST",
            "promotionTraceRef": trace_id,
            "problems": ctx.problems,
            "reasonSummary": trace["traceSummary"],
        }
        if ctx.final_outcome == "PROMOTE_ACCEPTED":
            result["inForceResultCategory"] = ctx.in_force_category
            result["inForceArtifactRefs"] = ctx.in_force_refs
            result["currentStateMaterializationTriggered"] = \
                ctx.materialization_triggered
        for key, refs in (("emittedAssertionRecordRefs", ctx.emitted["assertions"]),
                          ("emittedReviewDecisionRefs", ctx.emitted["reviews"]),
                          ("emittedAcceptedConsequenceRefs", ctx.emitted["consequences"])):
            if refs:
                result[key] = refs
        ctx.store.insert_record(ctx.cur, result)
        ctx.store.idempotency_claim(ctx.cur, ctx.idem_key, ctx.request_id,
                                    ctx.source_digest, result["resultId"])
        return result


class ReplayWriter:
    """Explicit idempotency (ingress boundary RFC §2.4): a matching replay
    deterministically reuses the earlier result; a conflicting replay is
    blocked rather than silently duplicating truth. The replay attempt gets
    its own recorded request envelope so the reuse/refusal is reconstructible
    across the ingress seam."""

    def write(self, ctx: GateContext, prior: dict) -> dict:
        stored_row = ctx.store.get_record(prior["result_record_id"])
        if stored_row is None:
            raise RuntimeError(
                f"idempotency result {prior['result_record_id']} is missing")
        stored = stored_row["payload"]
        bundle_conflict = (
            prior["tenant_ref"] != ctx.store.tenant_ref
            or stored_row["tenant_ref"] != ctx.store.tenant_ref
            or prior["runtime_bundle_digest"] != ctx.store.runtime_bundle_digest
            or stored_row["runtime_bundle_digest"] != ctx.store.runtime_bundle_digest
        )
        conflicting = bundle_conflict or (
            (prior["source_payload_digest"] or "") != (ctx.source_digest or "")
        )
        event_ref = stored["semanticEventRef"]

        replay_request = {
            "schemaVersion": "ofarm.commitingressrequest.v0.1",
            "requestId": ctx.request_id,
            "ingestedAt": now_iso(),
            "ingressChannel": ctx.sub.get("ingressChannel", "MANUAL_UI"),
            "commitClass": stored["commitClass"],
            "semanticEventRef": event_ref,
            "actingPartyRef": ctx.sub["actingPartyRef"],
            "targetScopes": ctx.sub.get("targetScopes")
                            or [{"scopeType": "FARM",
                                 "scopeRef": ctx.sub["farmRef"]}],
            "idempotencyKey": ctx.idem_key,
            "sourcePayloadDigest": ctx.source_digest,
        }
        ctx.store.insert_record(ctx.cur, replay_request)
        if bundle_conflict:
            disposition, outcome = "CONFLICTING_REPLAY_BLOCKED", "DENY"
            problem = runtime_problem(
                "PACK_CONFLICT", "Cross-bundle replay blocked",
                f"idempotency key {ctx.idem_key} belongs to tenant/bundle "
                f"{prior['tenant_ref']}/{prior['runtime_bundle_digest']}, while this "
                f"process is bound to {ctx.store.tenant_ref}/"
                f"{ctx.store.runtime_bundle_digest}; an earlier runtime's result "
                "cannot be reused as a decision by the active runtime")
            ctx.log("INGRESS_NORMALIZATION", "CONFLICTING_REPLAY_BLOCKED",
                    reason_code="PACK_CONFLICT")
        elif conflicting:
            disposition, outcome = "CONFLICTING_REPLAY_BLOCKED", "DENY"
            problem = runtime_problem(
                "IDEMPOTENCY_REPLAY_CONFLICT", "Conflicting replay blocked",
                f"idempotency key {ctx.idem_key} was already processed with a "
                "different source payload; blocked rather than silently "
                "duplicating truth")
            ctx.log("INGRESS_NORMALIZATION", "CONFLICTING_REPLAY_BLOCKED",
                    reason_code="IDEMPOTENCY_REPLAY_CONFLICT")
        else:
            disposition, outcome = "REPLAY_MATCH_REUSED_RESULT", "REPLAY_REUSED_RESULT"
            problem = runtime_problem(
                "IDEMPOTENCY_REPLAY_REUSED", "Replay reused earlier result",
                f"idempotency key {ctx.idem_key} deterministically reuses the "
                f"result of request {prior['request_id']}; no new truth was created",
                severity="INFO")
            ctx.log("INGRESS_NORMALIZATION", "REPLAY_MATCH_REUSED_RESULT",
                    reason_code="IDEMPOTENCY_REPLAY_REUSED")

        trace_id = mint("promtrace")
        trace = {
            "schemaVersion": "ofarm.promotiontrace.v0.1",
            "promotionTraceId": trace_id,
            "requestId": ctx.request_id,
            "evaluatedAt": now_iso(),
            "semanticEventRef": event_ref,
            "commitClass": stored["commitClass"],
            "primaryEventFamily": stored["primaryEventFamily"],
            "idempotencyKey": ctx.idem_key,
            "idempotencyDisposition": disposition,
            "replayOfRequestId": prior["request_id"],
            "gateSequence": ctx.gate_sequence,   # exactly the one logged entry
            "finalOutcome": outcome,
            "traceSummary": f"replay of {prior['request_id']}: {disposition}",
        }
        ctx.store.insert_record(ctx.cur, trace)

        problems = [problem]
        if outcome == "REPLAY_REUSED_RESULT":
            # a matching replay REUSES the earlier result, so carry forward that
            # result's own problems as replayed context — never silently drop them.
            # This matters especially for advisory WARNINGs (authorisation-mismatch
            # / dose-range): the result warning is the only implemented advisory
            # surface (durable Advisory-twin records are deferred, ERRATA E-006), so
            # dropping them on replay would silently lose the advisory.
            problems = [problem, *stored.get("problems", [])]

        result = {
            "schemaVersion": "ofarm.commitingressresult.v0.1",
            "resultId": mint("cires"),
            "requestId": ctx.request_id,
            "processedAt": now_iso(),
            "decisionOutcome": outcome,
            "commitClass": stored["commitClass"],
            "primaryEventFamily": stored["primaryEventFamily"],
            "semanticEventRef": event_ref,
            "idempotencyDisposition": disposition,
            "replayOfRequestId": prior["request_id"],
            "promotionTraceRef": trace_id,
            "problems": problems,
            "reasonSummary": trace["traceSummary"],
        }
        if outcome == "REPLAY_REUSED_RESULT":
            # surface the original emissions without re-emitting anything
            for k in ("emittedAssertionRecordRefs", "emittedReviewDecisionRefs",
                      "emittedAcceptedConsequenceRefs"):
                if stored.get(k):
                    result[k] = stored[k]
        ctx.store.insert_record(ctx.cur, result)
        return result
