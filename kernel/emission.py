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


class PromotionEmitter:
    """Owns AssertionRecord / ReviewDecision / AcceptedEventConsequence
    creation and the edges required for traceability."""

    def __init__(self, ctx: "GateContext"):
        self.ctx = ctx

    # ---------------------------------------------------------------- build --

    def _submission_evidence_refs(self) -> list:
        sub = self.ctx.sub
        return ((sub.get("payload") or {}).get("evidenceRefs")
                or sub.get("evidenceRefs") or [])

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
        if not assertion["evidenceRefs"]:
            # AssertionRecord requires >=1 evidence ref; the semantic event
            # itself is the captured evidence basis for evidence-light classes
            assertion["evidenceRefs"] = [ctx.event_id]
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

    # ------------------------------------------------------- emission flows --

    def emit_pending_assertion(self, *, amend_case_for_routing: bool) -> None:
        """The claim lands in the queue (or stays a captured draft)."""
        self._emit_assertion("PENDING_REVIEW")
        self._store_case(amend_for_routing=amend_case_for_routing)

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
        ctx.store.insert_record(ctx.cur, consequence)
        ctx.emitted["consequences"].append(consequence_id)
        ctx.store.add_edge(ctx.cur, "REVIEW", consequence_id, review_id)
        ctx.store.add_edge(ctx.cur, "EVENT_SOURCE", consequence_id, orig_event)

        ctx.log("REVIEW_PROMOTION", "PROMOTE_ACCEPTED", refs=[review_id])
        ctx.final_outcome = "PROMOTE_ACCEPTED"
        ctx.in_force_category = category
        ctx.in_force_refs = [consequence_id]
        ctx.trigger_source = consequence_id
        ctx.invalidation_sources = [consequence_id]


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
        stored = ctx.store.get_payload(prior["result_record_id"])
        conflicting = (prior["source_payload_digest"] or "") != (ctx.source_digest or "")
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
        if conflicting:
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
            "problems": [problem],
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
