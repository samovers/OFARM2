"""Gate pipeline (M1 brief task 3): the EnforcementChain as literal middleware.

ingress normalization → authority (default deny; revocation re-check)
→ validation sub-gates (schema · semantic/carrier · reference-resolution ·
temporal-conformance · code-binding vs the SI profile · registry verification)
→ static profile applicability (ContextSnapshot assembly)
→ evidence sufficiency (auto-generated EvidenceSufficiencyCase)
→ review/promotion (self-review per D8) → materialization.

Every authoritative write crosses this chain inside ONE transaction; every
refusal emits a RuntimeProblem with a registry reason code (Kernel rule 7);
every outcome lands in the gate log and the PromotionTrace (zero silent
acceptances). Capture is not commitment (Kernel rule 3): drafts exist freely
on the device; this module is the governed front door.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from . import config
from .authority import AuthorityEvaluator
from .context import (REGSR_SNAPSHOT_PREFIX, ContextAssembler, ProductRegister,
                      current_reference_snapshot, now_iso)
from .contracts import ContractViolation, sha256_of
from .materializer import Materializer
from .problems import runtime_problem

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

COMMIT_CLASS_TO_ASSERTION_TYPE = {
    "OBSERVATION_ASSERTION": "OBSERVATION_ASSERTION",
    "STRUCTURE_ASSERTION": "STRUCTURE_ASSERTION",
    "OPERATION_CLAIM": "OPERATION_CLAIM_ASSERTION",
    "COMPLIANCE_ASSERTION": "COMPLIANCE_ASSERTION",
}

PROMOTION_TARGET_BY_CLASS = {
    "OPERATION_CLAIM": "ACCEPTED_EXECUTED_INTERVENTION_CONSEQUENCE",
    "STRUCTURE_ASSERTION": "ACCEPTED_STRUCTURAL_STATE",
    "OBSERVATION_ASSERTION": "ACCEPTED_OBSERVATION_OCCURRENCE_STATE",
    "COMPLIANCE_ASSERTION": "COMPLIANCE_FACT",
}

CONSEQUENCE_TYPE_BY_TARGET = {
    "ACCEPTED_EXECUTED_INTERVENTION_CONSEQUENCE": "EXECUTION_CONFIRMED",
    "ACCEPTED_STRUCTURAL_STATE": "STATE_CHANGE_ACCEPTED",
    "ACCEPTED_OBSERVATION_OCCURRENCE_STATE": "STATE_CHANGE_ACCEPTED",
    "COMPLIANCE_FACT": "COMPLIANCE_STATUS_ACCEPTED",
}

EVENT_TIME_PLAUSIBILITY_PAST_DAYS = 400
EVENT_TIME_PLAUSIBILITY_FUTURE_HOURS = 24
DOSE_SANITY_MAX = 10000.0


def _mint(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex[:16]}"


from .context import parse_ts as _parse_ts  # single temporal-parse discipline


# subject types an AcceptedEventConsequence may carry (narrower than
# AssertionRecord's — a claim about an unpromotable subject is refused at
# validation, not crashed mid-transaction at promotion)
CONSEQUENCE_SUBJECT_TYPES = {"FARM", "SITE", "FIELD", "ZONE", "CROP_CYCLE",
                             "LOT", "FACILITY", "OPERATION"}


class _Refused(Exception):
    """Internal: stop the chain with a recorded refusal/diversion."""

    def __init__(self, gate, outcome, final_outcome, problems, rationale=None):
        self.gate, self.outcome = gate, outcome
        self.final_outcome = final_outcome
        self.problems = problems
        self.rationale = rationale or (problems[0]["detail"] if problems else "")


class GatePipeline:
    def __init__(self, store, product_register: ProductRegister | None = None):
        self.store = store
        self.authority = AuthorityEvaluator(store)
        self.context = ContextAssembler(store)
        self.materializer = Materializer(store)
        self.products = product_register or ProductRegister()
        self.products.load_from_store(store)

    # ======================================================================
    # the governed front door
    # ======================================================================

    def commit(self, submission: dict) -> dict:
        """Run one capture through the full chain. Returns the
        CommitIngressResult payload. One call = one transaction (D3)."""
        import psycopg
        try:
            with self.store.tx() as cur:
                return self._commit_in_tx(cur, submission)
        except psycopg.errors.UniqueViolation:
            # a concurrent commit won the idempotency-key race; our transaction
            # rolled back completely — serve the replay path against the winner
            with self.store.tx() as cur:
                prior = self.store.idempotency_lookup(cur, submission["idempotencyKey"])
                if prior is None:
                    raise
                request_id = _mint("cir")
                def log(gate, outcome, *, reason_code=None, rationale=None, refs=None):
                    self.store.log_gate(cur, request_id, gate, outcome,
                                        reason_code=reason_code, rationale=rationale,
                                        related_refs=refs)
                return self._replay(cur, prior, submission["idempotencyKey"],
                                    self._source_digest(submission), request_id,
                                    log, submission)

    @staticmethod
    def _source_digest(sub: dict) -> str:
        """Digest of the WHOLE submission: payload-less classes (notes,
        observations) must not collapse to the digest of {} — different
        submissions under one idempotency key are conflicts, not replays."""
        return sub.get("sourcePayloadDigest") or sha256_of(
            {k: v for k, v in sub.items() if k != "sourcePayloadDigest"})

    def _commit_in_tx(self, cur, sub: dict) -> dict:
        commit_class = sub["commitClass"]
        farm_ref = sub["farmRef"]
        acting_party = sub["actingPartyRef"]
        idem_key = sub["idempotencyKey"]
        ingested_at = now_iso()
        request_id = _mint("cir")
        gate_sequence: list[dict] = []
        all_problems: list[dict] = []
        source_digest = self._source_digest(sub)

        def log(gate, outcome, *, reason_code=None, rationale=None, refs=None):
            gate_sequence.append({k: v for k, v in {
                "gate": gate, "outcome": outcome, "rationale": rationale,
                "relatedArtifactRefs": refs}.items() if v})
            self.store.log_gate(cur, request_id, gate, outcome,
                                reason_code=reason_code, rationale=rationale,
                                related_refs=refs)

        # ---------------- INGRESS_NORMALIZATION -------------------------------
        prior = self.store.idempotency_lookup(cur, idem_key)
        if prior is not None:
            return self._replay(cur, prior, idem_key, source_digest, request_id, log, sub)

        if commit_class not in COMMIT_CLASS_TO_FAMILY:
            raise ContractViolation(f"unknown commit class {commit_class!r}")
        family = COMMIT_CLASS_TO_FAMILY[commit_class]
        event_time = sub.get("eventTime")
        captured_at = sub.get("capturedAt") or ingested_at
        # only verified-parseable times enter the normalized envelope; junk
        # input is refused at the temporal sub-gate, never stored as if true
        temporal_problem = None
        if event_time is not None and _parse_ts(event_time) is None:
            temporal_problem = runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Unparseable event time",
                f"event time {event_time!r} is not a valid timestamp; the claim "
                "stays a draft (note: the reason-code registry has no temporal-"
                "conformance code — see ERRATA E-001)")
            event_time = None
        if _parse_ts(captured_at) is None:
            captured_at = ingested_at
        scopes = sub.get("targetScopes") or [{"scopeType": "FARM", "scopeRef": farm_ref}]
        subject_refs = [sub.get("subjectRef") or farm_ref]

        event_id = _mint("event")
        envelope = {
            "schemaVersion": "ofarm.semanticeventenvelope.v0.1",
            "semanticEventId": event_id,
            "primaryEventFamily": family,
            "dominantSemanticConsequence": sub.get(
                "dominantSemanticConsequence",
                f"{commit_class.lower().replace('_', ' ')} captured"),
            "anchorScopes": scopes,
            "subjectRefs": subject_refs,
            # Kernel rule 6: event time (field entry) and record time (server
            # commit) are distinct fields and never collapse.
            "timeSemantics": {k: v for k, v in {
                "eventTime": event_time,
                "observationTime": sub.get("observationTime"),
                "decisionTime": sub.get("decisionTime"),
                "recordTime": ingested_at}.items() if v},
        }
        if not any(k in envelope["timeSemantics"]
                   for k in ("eventTime", "observationTime", "decisionTime")):
            envelope["timeSemantics"]["eventTime"] = captured_at
        if sub.get("evidenceRefs"):
            envelope["evidenceRefs"] = sub["evidenceRefs"]
        if sub.get("noteText") is not None:
            envelope["notes"] = sub["noteText"]

        ingress_request = {
            "schemaVersion": "ofarm.commitingressrequest.v0.1",
            "requestId": request_id,
            "ingestedAt": ingested_at,
            "ingressChannel": sub.get("ingressChannel", "MANUAL_UI"),
            "commitClass": commit_class,
            "semanticEventRef": event_id,
            "actingPartyRef": acting_party,
            "targetScopes": scopes,
            "idempotencyKey": idem_key,
            "sourcePayloadDigest": source_digest,
        }
        for opt_in, opt_out in (("actingAgentRef", "actingAgentRef"),
                                ("originatingOfflineQueueRef", "originatingOfflineQueueRef"),
                                ("evidenceRefs", "evidenceRefs")):
            if sub.get(opt_in):
                ingress_request[opt_out] = sub[opt_in]
        requested_target = sub.get("requestedPromotionTarget")
        if requested_target:
            ingress_request["requestedPromotionTarget"] = requested_target
        self.store.insert_record(cur, ingress_request)
        log("INGRESS_NORMALIZATION", "NORMALIZED_DRAFT")

        erp_id = None
        emitted = {"assertions": [], "reviews": [], "consequences": []}
        trace_refs: dict[str, str] = {}
        final_outcome = "RETAIN_DRAFT"
        in_force_category = None
        in_force_refs: list[str] = []
        materialization_triggered = False

        try:
            # ---------------- AUTHORITY ---------------------------------------
            offline = sub.get("ingressChannel") == "OFFLINE_SYNC_REPLAY"
            decision = self.authority.evaluate(
                acting_party_ref=acting_party,
                action_class=f"COMMIT_{commit_class}",
                action_stage="PROMOTION",
                scope={"scopeType": "FARM", "scopeRef": farm_ref},
                acting_agent_ref=sub.get("actingAgentRef"),
                ai_assistance=sub.get("aiAssistance"),
                revocation_check_required=True,
                # offline-synced operation claims route to review on revocation
                # (CAPTURE_MAPPING sync rule 2); submission-stage re-auth denies
                revocation_disposition="REQUIRE_REVIEW" if offline and commit_class == "OPERATION_CLAIM" else "DENY",
            )
            self.store.insert_record(cur, decision.request_payload)
            self.store.insert_record(cur, decision.trace_payload)
            self.store.insert_record(cur, decision.result_payload)
            trace_refs["authorizationDecisionResultRef"] = decision.result_payload["resultId"]
            authz_refs = [decision.request_payload["requestId"],
                          decision.result_payload["resultId"],
                          decision.trace_payload["traceId"]]
            if decision.outcome == "ALLOW":
                log("AUTHORITY", "ALLOW", refs=authz_refs)
            elif decision.outcome == "REQUIRE_REVIEW":
                log("AUTHORITY", "REQUIRE_REVIEW",
                    reason_code=decision.problems[0]["reasonCode"] if decision.problems else None,
                    rationale=decision.result_payload["reasonSummary"], refs=authz_refs)
                raise _Refused("AUTHORITY", "REQUIRE_REVIEW", "REQUIRE_REVIEW",
                               decision.problems,
                               decision.result_payload["reasonSummary"])
            else:  # DENY | REQUIRE_HUMAN_APPROVAL
                log("AUTHORITY", decision.outcome,
                    reason_code=decision.problems[0]["reasonCode"] if decision.problems else "AUTHORITY_DENIED",
                    rationale=decision.result_payload["reasonSummary"], refs=authz_refs)
                final = "DENY" if decision.outcome == "DENY" else "REQUIRE_REVIEW"
                raise _Refused("AUTHORITY", decision.outcome, final, decision.problems,
                               decision.result_payload["reasonSummary"])

            # ---------------- VALIDATION (sub-gates) --------------------------
            review_route_reasons: list[dict] = []
            erp_id = self._validation_gate(cur, sub, commit_class, farm_ref,
                                           event_time or captured_at, ingested_at,
                                           review_route_reasons, log,
                                           temporal_problem=temporal_problem,
                                           requested_target=requested_target)
            if erp_id:
                envelope["executionRecordPayloadRefs"] = [erp_id]

            # the normalized envelope is authoritative — stored once validation
            # confirmed the carrier; reachability edge lands with the trace
            self.store.insert_record(cur, envelope)

            # ---------------- PACK_PROFILE_APPLICABILITY ----------------------
            ctx = self.context.assemble(cur, farm_ref)
            log("PACK_PROFILE_APPLICABILITY", "APPLICABLE",
                refs=[ctx["contextSnapshotId"]])

            # ---------------- EVIDENCE_SUFFICIENCY ----------------------------
            assertion_id = _mint("assert")
            case_payload = None
            if commit_class in ("OPERATION_CLAIM", "COMPLIANCE_ASSERTION"):
                case_payload, floor_failures = self._sufficiency_case(
                    sub, commit_class, farm_ref, assertion_id, erp_id)
                if case_payload["outcome"]["decision"] == "REFUSE":
                    log("EVIDENCE_SUFFICIENCY", "INSUFFICIENT",
                        reason_code="EVIDENCE_INSUFFICIENT",
                        rationale=case_payload["outcome"]["rationale"])
                    raise _Refused(
                        "EVIDENCE_SUFFICIENCY", "INSUFFICIENT", "RETAIN_DRAFT",
                        [runtime_problem(
                            "EVIDENCE_INSUFFICIENT", "Evidence floor unmet",
                            case_payload["outcome"]["rationale"],
                            suggested_remediation="attach the missing floor items and resubmit; the claim stays a draft")],
                        case_payload["outcome"]["rationale"])
                review_route_reasons += floor_failures
                log("EVIDENCE_SUFFICIENCY", "SATISFIED")
            else:
                log("EVIDENCE_SUFFICIENCY", "NOT_REQUIRED",
                    rationale="sufficiency cases are generated only at operation-claim "
                              "promotion and DocumentAssembly freeze (PROFILE.md)")

            # ---------------- REVIEW_PROMOTION --------------------------------
            # D8 scopes self-review to ROUTINE OPERATION CLAIMS. A compliance
            # assertion reviewed by its own asserter is outside that scope and
            # outside the pilot's claim limits — it routes to the advisor
            # queue; it is never self-promoted into a compliance fact.
            if (commit_class == "COMPLIANCE_ASSERTION" and sub.get("confirmAccept")
                    and sub.get("reviewerPartyRef", acting_party) == acting_party):
                review_route_reasons.append(runtime_problem(
                    "HUMAN_APPROVAL_REQUIRED", "Self-review out of scope",
                    "self-review covers routine operation claims only (D8); a "
                    "compliance assertion requires a distinct reviewer and routes "
                    "to the advisor queue", severity="WARNING"))

            promotes = commit_class in PROMOTION_TARGET_BY_CLASS
            if not promotes:
                reason = {
                    "NOTE": "No declared safe promotion path exists from note to compliance fact.",
                    "ADVISORY_OUTPUT": "Advisory output may raise review attention but may not directly create a compliance fact.",
                }.get(commit_class, "this commit class has no promotion path")
                log("REVIEW_PROMOTION", "RETAIN_DRAFT", rationale=reason)
                final_outcome = "RETAIN_DRAFT"
            elif review_route_reasons:
                # exceptions route to the advisor queue (D8) — never silent accept
                assertion = self._assertion(sub, commit_class, farm_ref, assertion_id,
                                            event_id, erp_id, "PENDING_REVIEW")
                self.store.insert_record(cur, assertion)
                emitted["assertions"].append(assertion_id)
                self._assertion_edges(cur, assertion_id, event_id, sub, decision)
                if case_payload:
                    # the stored case must explain the review routing coherently
                    # — never assert 'all floor items satisfied' while routing
                    _INSUFFICIENCY_MAP = {
                        "PRODUCT_BINDING_UNRESOLVED": "AMBIGUOUS_PRODUCT_ID",
                        "SUPERSEDED_RECORD_USED": "CONFLICTING_EVIDENCE",
                        "EVIDENCE_INSUFFICIENT": "TIMESTAMP_INCOMPLETE",
                        "IDENTITY_UNRESOLVED": "MISSING_REQUIRED_EVIDENCE",
                        "HUMAN_APPROVAL_REQUIRED": "ATTESTATION_AUTHORITY_MISSING",
                    }
                    case_payload["outcome"] = {
                        "decision": "REQUIRE_REVIEW",
                        "rationale": "routed to the advisor queue: " + "; ".join(
                            p["title"] for p in review_route_reasons),
                        "attestationAllowed": False,
                        "insufficiencyReasonCodes": sorted({
                            _INSUFFICIENCY_MAP.get(p["reasonCode"], "SOURCE_QUALITY_LOW")
                            for p in review_route_reasons}),
                    }
                    case_payload["evidenceBundles"][0]["bundleStatus"] = "PARTIAL"
                    self.store.insert_record(cur, case_payload)
                    trace_refs["evidenceSufficiencyCaseRef"] = case_payload["sufficiencyCaseId"]
                all_problems.extend(review_route_reasons)
                log("REVIEW_PROMOTION", "REQUIRE_REVIEW",
                    reason_code=review_route_reasons[0]["reasonCode"],
                    rationale="exception routes to the advisor review queue (self-review "
                              "policy covers routine claims only)")
                final_outcome = "REQUIRE_REVIEW"
            elif not sub.get("confirmAccept"):
                assertion = self._assertion(sub, commit_class, farm_ref, assertion_id,
                                            event_id, erp_id, "PENDING_REVIEW")
                self.store.insert_record(cur, assertion)
                emitted["assertions"].append(assertion_id)
                self._assertion_edges(cur, assertion_id, event_id, sub, decision)
                if case_payload:
                    self.store.insert_record(cur, case_payload)
                    trace_refs["evidenceSufficiencyCaseRef"] = case_payload["sufficiencyCaseId"]
                log("REVIEW_PROMOTION", "RETAIN_DRAFT",
                    rationale="no review act: capture is not commitment (Kernel rule 3)")
                final_outcome = "RETAIN_DRAFT"
            else:
                # the deliberate confirm-accept step IS the review act (D8) —
                # but only with REVIEW_ACCEPT authority on this farm, checked
                # mechanically; self-review cannot bypass the gates above.
                reviewer = sub.get("reviewerPartyRef", acting_party)
                review_auth = self.authority.evaluate(
                    acting_party_ref=reviewer, action_class="REVIEW_ACCEPT",
                    action_stage="PROMOTION",
                    scope={"scopeType": "FARM", "scopeRef": farm_ref})
                self.store.insert_record(cur, review_auth.request_payload)
                self.store.insert_record(cur, review_auth.trace_payload)
                self.store.insert_record(cur, review_auth.result_payload)
                if not review_auth.allowed:
                    log("REVIEW_PROMOTION", "REQUIRE_REVIEW",
                        reason_code="AUTHORITY_DENIED",
                        rationale=f"{reviewer} holds no REVIEW_ACCEPT for {farm_ref}")
                    raise _Refused("REVIEW_PROMOTION", "REQUIRE_REVIEW", "REQUIRE_REVIEW",
                                   review_auth.problems,
                                   "reviewer lacks REVIEW_ACCEPT authority")

                assertion = self._assertion(sub, commit_class, farm_ref, assertion_id,
                                            event_id, erp_id, "IN_FORCE")
                self.store.insert_record(cur, assertion)
                emitted["assertions"].append(assertion_id)
                self._assertion_edges(cur, assertion_id, event_id, sub, decision)

                if case_payload:
                    self.store.insert_record(cur, case_payload)
                    trace_refs["evidenceSufficiencyCaseRef"] = case_payload["sufficiencyCaseId"]

                review_id = _mint("review")
                review = {
                    "schemaVersion": "ofarm.reviewdecision.v0.1",
                    "reviewDecisionId": review_id,
                    "reviewedArtifactFamily": "ASSERTION_RECORD",
                    "reviewedArtifactRef": assertion_id,
                    "reviewAction": "REVIEW_ACCEPT",
                    "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
                    "decidedByPartyRef": reviewer,
                    "decidedAt": now_iso(),
                    "decisionOutcomeState": "ACCEPTED",
                    "notes": "self-review: the deliberate confirm-and-accept step is the "
                             "review act (D8); sufficient for record-keeping use, "
                             "insufficient for certification-grade claims",
                }
                self.store.insert_record(cur, review)
                emitted["reviews"].append(review_id)
                self.store.add_edge(cur, "REVIEW", assertion_id, review_id)

                target = requested_target or PROMOTION_TARGET_BY_CLASS[commit_class]
                consequence_id = _mint("conseq")
                consequence = {
                    "schemaVersion": "ofarm.acceptedeventconsequence.v0.1",
                    "acceptedEventConsequenceId": consequence_id,
                    "consequenceType": CONSEQUENCE_TYPE_BY_TARGET.get(
                        target, "OTHER_CONSEQUENCE"),
                    "sourceEventRef": event_id,
                    "acceptedByReviewDecisionRef": review_id,
                    "subject": {
                        "subjectType": sub.get("subjectType", "FARM"),
                        "subjectRef": sub.get("subjectRef", farm_ref)},
                    "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
                    "acceptedAt": now_iso(),
                    "inForceState": "IN_FORCE",
                }
                if event_time:
                    consequence["effectiveFrom"] = event_time
                if erp_id:
                    consequence["executionRecordPayloadRefs"] = [erp_id]
                if sub.get("supersedesConsequenceRef"):
                    old_ref = sub["supersedesConsequenceRef"]
                    consequence["notes"] = f"supersedes {old_ref} (correction is supersession)"
                self.store.insert_record(cur, consequence)
                emitted["consequences"].append(consequence_id)
                self.store.add_edge(cur, "REVIEW", consequence_id, review_id)
                self.store.add_edge(cur, "EVENT_SOURCE", consequence_id, event_id)
                if sub.get("supersedesConsequenceRef"):
                    self.store.add_edge(cur, "LINEAGE_SUPERSEDES",
                                        consequence_id, sub["supersedesConsequenceRef"])

                log("REVIEW_PROMOTION", "PROMOTE_ACCEPTED", refs=[review_id])
                final_outcome = "PROMOTE_ACCEPTED"
                in_force_category = target
                in_force_refs = [consequence_id]

                # ---------------- CURRENT_STATE_MATERIALIZATION ---------------
                superseded = ([sub["supersedesConsequenceRef"]]
                              if sub.get("supersedesConsequenceRef") else [])
                self.materializer.invalidate_for_sources(
                    cur, superseded or [consequence_id],
                    trigger_family="BASIS_ADVANCED",
                    trigger_source_ref=consequence_id,
                    farm_scope_ref=farm_ref,
                    reason_code="TRUTH_BASIS_ADVANCED")
                mat = self.materializer.recompute(cur, farm_ref)
                # NOTE: no materializationResultRef on the trace — the commit-
                # time recompute emits Basis+Snapshot, not a boundary Result;
                # those receipts ride the gateSequence entry below
                materialization_triggered = True
                log("CURRENT_STATE_MATERIALIZATION", "UPDATED",
                    refs=[mat["basisRef"], mat["snapshotRef"]])

        except _Refused as refusal:
            all_problems.extend(refusal.problems)
            final_outcome = refusal.final_outcome
            if envelope and not self.store.record_exists(event_id):
                # the normalized draft event is still recorded (refusals are
                # traceable history, not silence) — emitted under this trace
                self.store.insert_record(cur, envelope)

        # ---------------- PromotionTrace + reachability (same tx, D3) ---------
        trace_id = _mint("promtrace")
        trace = {
            "schemaVersion": "ofarm.promotiontrace.v0.1",
            "promotionTraceId": trace_id,
            "requestId": request_id,
            "evaluatedAt": now_iso(),
            "semanticEventRef": event_id,
            "commitClass": commit_class,
            "primaryEventFamily": family,
            "idempotencyKey": idem_key,
            "idempotencyDisposition": "NEW_REQUEST",
            "gateSequence": gate_sequence,
            "finalOutcome": final_outcome,
            "traceSummary": f"{commit_class} via {len(gate_sequence)} gates -> {final_outcome}",
            **trace_refs,
        }
        if in_force_category:
            trace["inForceResultCategory"] = in_force_category
        if emitted["assertions"]:
            trace["emittedAssertionRecordRefs"] = emitted["assertions"]
        if emitted["reviews"]:
            trace["emittedReviewDecisionRefs"] = emitted["reviews"]
        if emitted["consequences"]:
            trace["emittedAcceptedConsequenceRefs"] = emitted["consequences"]
        self.store.insert_record(cur, trace)
        for ref in ([event_id] + emitted["assertions"] + emitted["reviews"]
                    + emitted["consequences"]):
            if self.store.record_exists(ref) or ref == event_id:
                self.store.add_edge(cur, "PROMOTION_EMITS", trace_id, ref)

        result_id = _mint("cires")
        result = {
            "schemaVersion": "ofarm.commitingressresult.v0.1",
            "resultId": result_id,
            "requestId": request_id,
            "processedAt": now_iso(),
            "decisionOutcome": final_outcome,
            "commitClass": commit_class,
            "primaryEventFamily": family,
            "semanticEventRef": event_id,
            "idempotencyDisposition": "NEW_REQUEST",
            "promotionTraceRef": trace_id,
            "problems": all_problems,
            "reasonSummary": trace["traceSummary"],
        }
        if final_outcome == "PROMOTE_ACCEPTED":
            result["inForceResultCategory"] = in_force_category
            result["inForceArtifactRefs"] = in_force_refs
            result["currentStateMaterializationTriggered"] = materialization_triggered
        if emitted["assertions"]:
            result["emittedAssertionRecordRefs"] = emitted["assertions"]
        if emitted["reviews"]:
            result["emittedReviewDecisionRefs"] = emitted["reviews"]
        if emitted["consequences"]:
            result["emittedAcceptedConsequenceRefs"] = emitted["consequences"]
        self.store.insert_record(cur, result)
        self.store.idempotency_claim(cur, idem_key, request_id,
                                     source_digest, result_id)
        return result

    # ======================================================================
    # replay (ingress boundary RFC §2.4: explicit idempotency)
    # ======================================================================

    def _replay(self, cur, prior, idem_key, source_digest, request_id, log,
                sub: dict) -> dict:
        stored = self.store.get_payload(prior["result_record_id"])
        conflicting = (prior["source_payload_digest"] or "") != (source_digest or "")
        event_ref = stored["semanticEventRef"]

        # the replay attempt gets its own recorded request envelope — the
        # refusal/reuse must be reconstructible across the ingress seam,
        # including the conflicting attempt's digest and channel
        replay_request = {
            "schemaVersion": "ofarm.commitingressrequest.v0.1",
            "requestId": request_id,
            "ingestedAt": now_iso(),
            "ingressChannel": sub.get("ingressChannel", "MANUAL_UI"),
            "commitClass": stored["commitClass"],
            "semanticEventRef": event_ref,
            "actingPartyRef": sub["actingPartyRef"],
            "targetScopes": sub.get("targetScopes")
                            or [{"scopeType": "FARM", "scopeRef": sub["farmRef"]}],
            "idempotencyKey": idem_key,
            "sourcePayloadDigest": source_digest,
        }
        self.store.insert_record(cur, replay_request)
        if conflicting:
            disposition, outcome = "CONFLICTING_REPLAY_BLOCKED", "DENY"
            problem = runtime_problem(
                "IDEMPOTENCY_REPLAY_CONFLICT", "Conflicting replay blocked",
                f"idempotency key {idem_key} was already processed with a different "
                "source payload; blocked rather than silently duplicating truth")
            log("INGRESS_NORMALIZATION", "CONFLICTING_REPLAY_BLOCKED",
                reason_code="IDEMPOTENCY_REPLAY_CONFLICT")
        else:
            disposition, outcome = "REPLAY_MATCH_REUSED_RESULT", "REPLAY_REUSED_RESULT"
            problem = runtime_problem(
                "IDEMPOTENCY_REPLAY_REUSED", "Replay reused earlier result",
                f"idempotency key {idem_key} deterministically reuses the result of "
                f"request {prior['request_id']}; no new truth was created",
                severity="INFO")
            log("INGRESS_NORMALIZATION", "REPLAY_MATCH_REUSED_RESULT",
                reason_code="IDEMPOTENCY_REPLAY_REUSED")

        trace_id = _mint("promtrace")
        trace = {
            "schemaVersion": "ofarm.promotiontrace.v0.1",
            "promotionTraceId": trace_id,
            "requestId": request_id,
            "evaluatedAt": now_iso(),
            "semanticEventRef": event_ref,
            "commitClass": stored["commitClass"],
            "primaryEventFamily": stored["primaryEventFamily"],
            "idempotencyKey": idem_key,
            "idempotencyDisposition": disposition,
            "replayOfRequestId": prior["request_id"],
            "gateSequence": [{"gate": "INGRESS_NORMALIZATION", "outcome": disposition}],
            "finalOutcome": outcome,
            "traceSummary": f"replay of {prior['request_id']}: {disposition}",
        }
        self.store.insert_record(cur, trace)

        result = {
            "schemaVersion": "ofarm.commitingressresult.v0.1",
            "resultId": _mint("cires"),
            "requestId": request_id,
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
        self.store.insert_record(cur, result)
        return result

    # ======================================================================
    # validation sub-gates
    # ======================================================================

    def _validation_gate(self, cur, sub, commit_class, farm_ref, event_time,
                         ingested_at, review_route_reasons, log, *,
                         temporal_problem=None, requested_target=None) -> str | None:
        """Runs the six validation sub-gates. Returns the stored
        ExecutionRecordPayload id for operation claims. Every refusing
        outcome is logged before raising — refusals land in the gate log and
        the PromotionTrace, never only in the problems array (PLATFORM.md)."""
        payload = sub.get("payload")
        erp_id = None

        def refuse(outcome, problem, final="RETAIN_DRAFT"):
            log("VALIDATION", outcome, reason_code=problem["reasonCode"],
                rationale=problem["detail"])
            raise _Refused("VALIDATION", outcome, final, [problem])

        # --- temporal-conformance (all classes) ---
        if temporal_problem is not None:
            refuse("FAIL_TEMPORAL", temporal_problem)
        now = datetime.now(timezone.utc)
        et = _parse_ts(event_time)
        if et is None:
            refuse("FAIL_TEMPORAL", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Unparseable event time",
                f"event time {event_time!r} is not a valid timestamp (ERRATA E-001: "
                "no temporal-conformance reason code exists in the registry)"))
        if et > now + timedelta(hours=EVENT_TIME_PLAUSIBILITY_FUTURE_HOURS) or \
           et < now - timedelta(days=EVENT_TIME_PLAUSIBILITY_PAST_DAYS):
            review_route_reasons.append(runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Event time outside plausibility window",
                f"event time {event_time} is outside the plausibility window; "
                "routed to review, never silently accepted (ERRATA E-001)",
                severity="WARNING"))

        # --- semantic: a PROMOTING class may only request its own lawful
        # target (an observation cannot mint a COMPLIANCE_FACT — Kernel rule
        # 4). Non-promoting classes (note, advisory) pass validation and are
        # stopped at REVIEW_PROMOTION instead, exactly as the inherited
        # gate-sequencing fixtures pin it.
        if requested_target and commit_class in PROMOTION_TARGET_BY_CLASS:
            lawful = PROMOTION_TARGET_BY_CLASS[commit_class]
            if requested_target != lawful:
                refuse("FAIL_SEMANTIC", runtime_problem(
                    "HIGH_CONSEQUENCE_BLOCKED", "Unlawful promotion target",
                    f"commit class {commit_class} cannot request promotion target "
                    f"{requested_target}; its lawful target is {lawful} "
                    "(no shortcut to truth)"))

        # --- semantic: a promoting claim's subject must be a type the
        # AcceptedEventConsequence contract can carry
        if commit_class in PROMOTION_TARGET_BY_CLASS:
            subject_type = sub.get("subjectType", "FARM")
            if subject_type not in CONSEQUENCE_SUBJECT_TYPES:
                refuse("FAIL_SEMANTIC", runtime_problem(
                    "IDENTITY_UNRESOLVED", "Subject type cannot promote",
                    f"subjectType {subject_type} is not promotable to an accepted "
                    "consequence; the claim stays a draft"))

        # --- semantic: a correction must name a real, in-force consequence on
        # THIS farm (an unvalidated ref could knock another farm's truth out
        # of force or dangle)
        supersedes = sub.get("supersedesConsequenceRef")
        if supersedes:
            target_row = self.store.get_record(supersedes)
            if target_row is None:
                refuse("FAIL_REFERENCE_RESOLUTION", runtime_problem(
                    "EVIDENCE_REFERENCE_UNAVAILABLE", "Supersession target missing",
                    f"supersedesConsequenceRef {supersedes} does not resolve"))
            target = target_row["payload"]
            if target_row["record_kind"] != "ofarm.acceptedeventconsequence.v0.1":
                refuse("FAIL_SEMANTIC", runtime_problem(
                    "SUPERSEDED_RECORD_USED", "Supersession target wrong kind",
                    f"{supersedes} is {target_row['record_kind']}, not an accepted "
                    "consequence"))
            if {"scopeType": "FARM", "scopeRef": farm_ref} not in target["anchorScopes"]:
                refuse("FAIL_SEMANTIC", runtime_problem(
                    "SCOPE_NOT_AUTHORIZED", "Cross-farm supersession refused",
                    f"{supersedes} is not anchored on {farm_ref}; a correction may "
                    "only supersede this farm's own truth"))
            if self.store.is_superseded(supersedes):
                refuse("FAIL_SEMANTIC", runtime_problem(
                    "SUPERSEDED_RECORD_USED", "Target already superseded",
                    f"{supersedes} was already superseded; correct the current "
                    "in-force record instead"))

        if commit_class != "OPERATION_CLAIM":
            log("VALIDATION", "PASS")
            return None

        if not isinstance(payload, dict):
            refuse("FAIL_SCHEMA", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Missing carrier payload",
                "an operation claim requires an ExecutionRecordPayload carrier"))

        # --- schema sub-gate (the carrier contract validates on write) ---
        try:
            contract = self.store.registry.validate(payload)
        except ContractViolation as exc:
            refuse("FAIL_SCHEMA", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Carrier schema violation", str(exc)))
        if contract.kind != "ofarm.executionrecordpayload.v0.1":
            refuse("FAIL_SCHEMA", runtime_problem(
                "EVIDENCE_INSUFFICIENT", "Wrong carrier",
                f"operation claims carry ofarm.executionrecordpayload.v0.1, got {contract.kind}"))
        if payload.get("recordClass") not in ("OPERATION_CLAIM", "AS_APPLIED_EVIDENCE"):
            # accepted/corrected/disputed record classes are pipeline- or
            # supersession-produced, never self-declared at ingress (Kernel
            # rule 4: an operation claim is not an accepted execution)
            refuse("FAIL_CARRIER", runtime_problem(
                "HIGH_CONSEQUENCE_BLOCKED", "Self-declared record class refused",
                f"a commit-time carrier may declare recordClass OPERATION_CLAIM or "
                f"AS_APPLIED_EVIDENCE, not {payload.get('recordClass')!r}"))

        # --- semantic / carrier sub-gate ---
        profile = self.store.find_by_kind("ofarm.agronomiccodebindingprofile.v0.1")[-1]["payload"]
        params = payload.get("actualQuantityParameters", [])
        dose_params = [p for p in params if p["parameterRole"] in ("DOSE", "RATE")]
        if profile["quantityAndUnitPolicy"]["requireQuantityKindAndUnitCode"]:
            bad_units = [p for p in dose_params
                         if not p.get("unitRef", "").startswith("scheme:ucum")
                         or not p.get("quantityKindRef")]
            if not dose_params or bad_units:
                # UNIT_CODE unresolved behavior is BLOCK_PROMOTION in the SI profile
                log("VALIDATION", "FAIL_CARRIER", reason_code="UNIT_UNRESOLVED",
                    rationale="dose without resolved UCUM unit code")
                raise _Refused("VALIDATION", "FAIL_CARRIER", "RETAIN_DRAFT", [runtime_problem(
                    "UNIT_UNRESOLVED", "Dose unit unresolved",
                    "the SI profile requires a UCUM unit code and quantity kind on "
                    "every dose; unresolved units block promotion (BLOCK_PROMOTION)")])
        for p in dose_params:
            if not (0 < p["value"] <= DOSE_SANITY_MAX):
                review_route_reasons.append(runtime_problem(
                    "EVIDENCE_INSUFFICIENT", "Implausible dose",
                    f"dose value {p['value']} is implausible; advisory flag raised and "
                    "routed to advisor review, never a silent block", severity="WARNING"))

        # --- reference-resolution sub-gate ---
        dangling = []
        for ref in ([payload["actor"]["actorPartyRef"]]
                    + payload.get("agronomicIdentityBindingRefs", [])
                    + payload.get("evidenceRefs", [])):
            if not self.store.record_exists(ref):
                dangling.append(ref)
        field_scope = payload["executionExtent"]["targetScope"]
        field_identity = self.store.get_payload(field_scope["scopeRef"])
        if field_scope["scopeType"] == "FIELD" and field_identity is None:
            dangling.append(field_scope["scopeRef"])
        if dangling:
            log("VALIDATION", "FAIL_REFERENCE_RESOLUTION",
                reason_code="EVIDENCE_REFERENCE_UNAVAILABLE",
                rationale=f"dangling refs: {dangling}")
            raise _Refused("VALIDATION", "FAIL_REFERENCE_RESOLUTION", "RETAIN_DRAFT",
                           [runtime_problem(
                               "EVIDENCE_REFERENCE_UNAVAILABLE", "Dangling references",
                               f"these references do not resolve in the store: {dangling}")])

        # --- code-binding sub-gate (vs the SI profile instance) ---
        bindings = [self.store.get_payload(r)
                    for r in payload.get("agronomicIdentityBindingRefs", [])]
        product_bindings = [b for b in bindings
                            if b and b["bindingRole"] == "CROP_PROTECTION_PRODUCT"]
        crop_bindings = [b for b in bindings if b and b["bindingRole"] == "CROP_SPECIES"]
        product_binding = product_bindings[0] if product_bindings else None
        if product_binding is None or product_binding["bindingState"] != "VERIFIED":
            # SI profile: CROP_PROTECTION_PRODUCT unresolvedBehavior = REQUIRE_REVIEW;
            # free text never silently becomes compliance identity
            state = product_binding["bindingState"] if product_binding else "MISSING"
            review_route_reasons.append(runtime_problem(
                "PRODUCT_BINDING_UNRESOLVED", "Product binding unresolved",
                f"product binding state is {state}; the record stays committable as a "
                "claim, promotion requires review (UNRESOLVED is explicit, never silent)",
                severity="WARNING"))
        if not crop_bindings:
            review_route_reasons.append(runtime_problem(
                "IDENTITY_UNRESOLVED", "Crop binding missing",
                "no EPPO crop binding is linked; the SI profile routes this to review",
                severity="WARNING"))

        # --- external-registry verification sub-gate ---
        # D9: product identity is the decision number (stevilka odlocbe) +
        # validity dates; regsrCode is a page locator, NEVER identity. List
        # rows carry no decision numbers, so re-verification is identity-grade
        # only where the snapshot parsed the product's detail page; anything
        # weaker routes to review — never a silent locator-joined verdict.
        if product_binding and product_binding["bindingState"] == "VERIFIED":
            current = current_reference_snapshot(self.store, REGSR_SNAPSHOT_PREFIX)
            current_id = current["referenceSnapshotId"] if current else None
            captured_against = sub.get("capturedAgainstSnapshotRef") \
                or (product_binding.get("referenceSnapshotRefs") or [None])[0]
            if current_id and captured_against and captured_against != current_id:
                decision_number = product_binding["bindingValue"].get("registrationRef")
                confirmed = (self.products.lookup_by_decision(current_id, decision_number)
                             if decision_number else None)
                if confirmed is not None:
                    valid_until = (confirmed.get("decision", {}).get("validUntil")
                                   or confirmed.get("registrationValidUntil") or "")
                    if valid_until and valid_until < (event_time or "")[:10]:
                        review_route_reasons.append(runtime_problem(
                            "SUPERSEDED_RECORD_USED", "Registry snapshot discrepancy",
                            f"decision {decision_number} validity ended {valid_until} per "
                            f"current snapshot {current_id}, before the event time; "
                            "discrepancy recorded and routed to review, never silent "
                            "acceptance", severity="WARNING"))
                    else:
                        log("VALIDATION", "REGISTRY_REVERIFIED",
                            rationale=f"identity re-verified by decision number "
                                      f"{decision_number} against {current_id}")
                else:
                    review_route_reasons.append(runtime_problem(
                        "PRODUCT_BINDING_UNRESOLVED", "Re-verification not confirmable",
                        f"the current snapshot {current_id} carries no decision-number "
                        f"data for {decision_number or 'this binding'}; identity cannot "
                        "be re-confirmed on this surface (regsrCode is a locator, not "
                        "identity — D9), so the record routes to review",
                        severity="WARNING"))

        log("VALIDATION", "PASS")

        # the carrier is stored as part of the same transaction; a reused
        # carrier id with DIFFERENT content is a conflict, refused — promoted
        # truth must never silently diverge from the validated submission
        erp_id = payload["executionRecordPayloadId"]
        existing = self.store.get_record(erp_id)
        if existing is None:
            self.store.insert_record(cur, payload)
            for ev in payload.get("evidenceRefs", []):
                if self.store.record_exists(ev):
                    self.store.add_edge(cur, "EVIDENCE", erp_id, ev)
        elif existing["payload_sha256"] != sha256_of(payload):
            refuse("FAIL_CARRIER", runtime_problem(
                "RETRY_CONFLICT", "Carrier id conflict",
                f"executionRecordPayloadId {erp_id} already names a record with "
                "different content; mint a new carrier id (corrections supersede "
                "via supersedesConsequenceRef, they never overwrite)"))
        return erp_id

    # ======================================================================
    # evidence sufficiency (auto-generated from the SI policy template)
    # ======================================================================

    def _sufficiency_case(self, sub, commit_class, farm_ref, assertion_id,
                          erp_id) -> tuple[dict, list[dict]]:
        """EvidenceSufficiencyCase from policy:si.ffs.evidence-review.v0_1 —
        never hand-authored (CAPTURE_MAPPING). Returns (case, floor_failures
        that route to review rather than refuse)."""
        payload = sub.get("payload") or {}
        bindings = [self.store.get_payload(r)
                    for r in payload.get("agronomicIdentityBindingRefs", [])]
        bindings = [b for b in bindings if b]

        if commit_class == "COMPLIANCE_ASSERTION":
            # compliance claims are not spray carriers: the floor is a real
            # evidence bundle backing the asserted compliance state
            evidence_refs = sub.get("evidenceRefs", [])
            checks = {"evidence-bundle": bool(self._durable_evidence(evidence_refs))}
            hard, soft = ("evidence-bundle",), ()
            return self._case_from_checks(sub, farm_ref, assertion_id, erp_id,
                                          checks, hard, soft, evidence_refs)

        checks = {
            "product-binding": any(
                b["bindingRole"] == "CROP_PROTECTION_PRODUCT"
                and b["bindingState"] == "VERIFIED"
                and b.get("referenceSnapshotRefs") for b in bindings),
            "dose-unit": any(
                p["parameterRole"] in ("DOSE", "RATE")
                and p.get("unitRef", "").startswith("scheme:ucum")
                for p in payload.get("actualQuantityParameters", [])),
            "parcel": payload.get("executionExtent", {}).get("targetScope", {})
                            .get("scopeType") in ("FIELD", "ZONE"),
            "crop-binding": any(b["bindingRole"] == "CROP_SPECIES" for b in bindings),
            "operator": bool(payload.get("actor", {}).get("actorPartyRef")),
            "event-time": bool(payload.get("effectiveTimeInterval", {}).get("start")),
        }
        # hard floor: items whose absence means the proof bundle itself is missing
        hard = ("dose-unit", "operator", "event-time", "parcel")
        soft = ("product-binding", "crop-binding")   # unresolved → review (SI profile)
        evidence_refs = payload.get("evidenceRefs", []) or sub.get("evidenceRefs", [])
        return self._case_from_checks(sub, farm_ref, assertion_id, erp_id,
                                      checks, hard, soft, evidence_refs)

    def _durable_evidence(self, refs: list[str]) -> list[str]:
        """Refs that resolve to actual EvidenceRecords — the durable proof
        bundle. A ref to some other record is not evidence of execution."""
        out = []
        for ref in refs:
            rec = self.store.get_record(ref)
            if rec and rec["record_kind"] == "ofarm.evidencerecord.v0.1":
                out.append(ref)
        return out

    def _case_from_checks(self, sub, farm_ref, assertion_id, erp_id,
                          checks, hard, soft, evidence_refs) -> tuple[dict, list[dict]]:
        arguments = []
        for name, ok in checks.items():
            arguments.append({
                "argumentId": f"arg:{assertion_id.split(':')[-1]}:{name}",
                "supportsClaimIds": ["claim:floor"],
                "policyRef": config.EVIDENCE_POLICY_REF,
                "ruleRef": f"rule:si.ffs.floor.{name}",
                "conclusion": "SUPPORTED" if ok else (
                    "REVIEW_REQUIRED" if name in soft else "UNSUPPORTED"),
            })
        hard_missing = [n for n in hard if not checks[n]]
        soft_missing = [n for n in soft if not checks[n]]
        durable = self._durable_evidence(evidence_refs)
        if hard_missing or not durable:
            decision = "REFUSE"
            rationale = (f"evidence floor unmet: missing {hard_missing or ['durable proof bundle']}; "
                         "the claim lacks the required durable proof for governed promotion")
        elif soft_missing:
            decision = "REQUIRE_REVIEW"
            rationale = f"floor items need review: {soft_missing}"
        else:
            decision = "ALLOW"
            rationale = "all SI evidence-floor items satisfied"

        case = {
            "schemaVersion": "ofarm.evidencesufficiencycase.v0.2",
            "sufficiencyCaseId": _mint("suffcase"),
            "generatedAt": now_iso(),
            "caseClass": "COMPLIANCE_ASSERTION",
            "targetTwin": "COMPLIANCE",
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
            "subject": {"subjectType": "ASSERTION_RECORD", "subjectRef": assertion_id},
            "governingPolicyRefs": [config.EVIDENCE_POLICY_REF],
            "claims": [{
                "claimId": "claim:floor",
                "claimType": "COMPLIANCE_CLAIM",
                "claimRef": assertion_id,
                "statement": "this operation claim meets the SI record-keeping evidence floor",
            }],
            "arguments": arguments,
            "evidenceBundles": [{
                "bundleId": f"bundle:{assertion_id.split(':')[-1]}",
                "supportsArgumentIds": [a["argumentId"] for a in arguments],
                "bundleStatus": "COMPLETE" if decision == "ALLOW" else (
                    "PARTIAL" if decision == "REQUIRE_REVIEW" else "MISSING_REQUIRED_SUPPORT"),
                "rawSourceRefs": evidence_refs,
                "normalizedInterpretationRefs": [erp_id] if erp_id else [],
                "provenanceRefs": [],
                "chainOfCustodyStatus": "PRESERVED" if durable else "UNKNOWN",
            }],
            "outcome": {
                "decision": decision,
                "rationale": rationale,
                "attestationAllowed": decision == "ALLOW",
            },
        }
        if decision != "ALLOW":
            case["outcome"]["insufficiencyReasonCodes"] = (
                ["MISSING_REQUIRED_EVIDENCE"] +
                (["MISSING_PROVENANCE_LINK"] if not durable else []) +
                (["AMBIGUOUS_PRODUCT_ID"] if "product-binding" in soft_missing else []))

        failures = [runtime_problem(
            "PRODUCT_BINDING_UNRESOLVED" if "product-binding" in soft_missing
            else "IDENTITY_UNRESOLVED",
            "Floor item requires review", rationale, severity="WARNING")
        ] if decision == "REQUIRE_REVIEW" else []
        return case, failures

    # ======================================================================
    # helpers
    # ======================================================================

    def _assertion(self, sub, commit_class, farm_ref, assertion_id, event_id,
                   erp_id, claim_state) -> dict:
        a = {
            "schemaVersion": "ofarm.assertionrecord.v0.1",
            "assertionRecordId": assertion_id,
            "assertionType": COMMIT_CLASS_TO_ASSERTION_TYPE.get(
                commit_class, "OTHER_ASSERTION"),
            "subject": {"subjectType": sub.get("subjectType", "FARM"),
                        "subjectRef": sub.get("subjectRef", farm_ref)},
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
            "assertedByPartyRef": sub["actingPartyRef"],
            "assertedAt": now_iso(),
            "claimState": claim_state,
            "evidenceRefs": (sub.get("payload") or {}).get("evidenceRefs")
                            or sub.get("evidenceRefs") or [],
        }
        if sub.get("eventTime"):
            a["occurrenceTime"] = sub["eventTime"]
        if erp_id:
            a["executionRecordPayloadRefs"] = [erp_id]
        if not a["evidenceRefs"]:
            # AssertionRecord requires >=1 evidence ref; the semantic event
            # itself is the captured evidence basis for evidence-light classes
            a["evidenceRefs"] = [event_id]
        return a

    def _assertion_edges(self, cur, assertion_id, event_id, sub, authz_decision):
        self.store.add_edge(cur, "EVENT_SOURCE", assertion_id, event_id)
        self.store.add_edge(cur, "AUTHORITY_BASIS", assertion_id,
                            authz_decision.result_payload["resultId"])
        for ev in ((sub.get("payload") or {}).get("evidenceRefs")
                   or sub.get("evidenceRefs") or []):
            if self.store.record_exists(ev):
                self.store.add_edge(cur, "EVIDENCE", assertion_id, ev)
