"""Output generator (M1 brief task 6): the two governed outputs.

View 1 — PassportView `view:si.ffs.spray-register.passportview.v0_1`:
live register, freshness and gaps always visible; STALE renders only with a
banner and is barred from export; missing basis refuses (views/VIEWS.md).

View 2 — DocumentAssembly `view:si.ffs.inspection-register.documentassembly.v0_1`:
frozen exportable register; assembles only accepted consequences within the
window from a fresh materialization; gaps are content — the annex never
promotes (Constitution §10.12); refuses rather than emitting a degraded
document silently.

Both carry ResultQualificationEnvelopes; both honor the claim limit: this is
record-keeping completeness, never current-compliance (PILOT_SI.md).
"""
from __future__ import annotations

import hashlib

from psycopg.types.json import Jsonb

from . import config
from .authority import AuthorityEvaluator
from .contracts import canonical_json
from .materializer import Materializer
from .problems import runtime_problem
from .context import mint as _mint, now_iso, parse_ts

PASSPORT_VIEW_REF = "view:si.ffs.spray-register.passportview.v0_1"
DOCASM_VIEW_REF = "view:si.ffs.inspection-register.documentassembly.v0_1"
PASSPORT_QUERYSPEC = "queryspec:si.ffs.spray-register.passportview.v0_1"
PASSPORT_QUERYPLAN = "queryplan:si.ffs.spray-register.passportview.v0_1"
DOCASM_QUERYSPEC = "queryspec:si.ffs.inspection-register.documentassembly.v0_1"
DOCASM_QUERYPLAN = "queryplan:si.ffs.inspection-register.documentassembly.v0_1"

CLAIM_STATEMENT = ("This register faithfully and traceably reflects what the farm "
                   "recorded, with gaps, disputes, and unresolved bindings visible. "
                   "It claims record-keeping completeness only — never current-"
                   "compliance against the authorisation register, certification, "
                   "or legal advice.")


def _qualification(*, surface_class: str, staleness: str, sufficiency: str,
                   high_consequence_allowed: bool, trace_refs: list[str],
                   allowed: list[str], blocked: list[str],
                   safe_label: str, user_message: str,
                   mat_result_ref: str | None = None) -> dict:
    env = {
        "schemaVersion": "ofarm.resultqualificationenvelope.v0.1",
        "qualificationId": _mint("qual"),
        "qualifiedAt": now_iso(),
        "asOf": now_iso(),
        "surfaceClass": surface_class,
        "twinScope": "COMPLIANCE",
        "truthPosture": "GOVERNED_MATERIALIZATION",
        "authorityLevel": "FULL",
        "candidateStatus": "NOT_CANDIDATE",
        "disputeStatus": "NONE",
        "stalenessClass": staleness,
        "evidenceSufficiency": sufficiency,
        "permissionClass": "FULL_DETAIL",
        "dataAbsentReason": "NOT_ABSENT",
        "highConsequenceUseAllowed": high_consequence_allowed,
        "allowedUseClasses": allowed,
        "blockedUseClasses": blocked,
        "traceRefs": trace_refs,
        "displayHints": {
            "safeLabel": safe_label,
            "userMessage": user_message,
            "forbiddenLabels": [
                "compliant", "certified", "authorisation-current",
                "production-ready", "legally approved",
            ],
        },
    }
    if mat_result_ref:
        env["materializationResultRef"] = mat_result_ref
    return env


def _refusal_response(problem: dict, qualification: dict | None = None) -> dict:
    return {"refused": True, "problem": problem, "qualification": qualification}


class OutputGenerator:
    def __init__(self, store):
        self.store = store
        self.authority = AuthorityEvaluator(store)
        self.materializer = Materializer(store)

    # ---------------------------------------------------------------- shared --

    def _pending_claims(self, farm_ref: str) -> list[dict]:
        rows = self.store.find_by_kind("ofarm.assertionrecord.v0.1")
        out = []
        for r in rows:
            a = r["payload"]
            if {"scopeType": "FARM", "scopeRef": farm_ref} not in a["anchorScopes"]:
                continue
            # an assertion accepted via a separate review act keeps its
            # captured claimState (append-only) — the REVIEW edge is what
            # says it left the queue
            if self.store.edges_from(a["assertionRecordId"], "REVIEW"):
                continue
            if a["claimState"] in ("PENDING_REVIEW", "CONTESTED"):
                out.append({
                    "kind": "PENDING_CLAIM" if a["claimState"] == "PENDING_REVIEW" else "DISPUTED",
                    "accepted": False,
                    "assertionRef": a["assertionRecordId"],
                    "claimState": a["claimState"],
                    "assertedAt": a["assertedAt"],
                    "occurrenceTime": a.get("occurrenceTime"),
                    "note": "recorded but NOT accepted — shown as an exception row, "
                            "never silently omitted, never silently promoted",
                })
        return out

    def _advisory_flags(self, farm_ref: str) -> list[dict]:
        rows = self.store.find_by_kind("ofarm.semanticeventenvelope.v0.1")
        out = []
        for r in rows:
            e = r["payload"]
            if {"scopeType": "FARM", "scopeRef": farm_ref} not in e["anchorScopes"]:
                continue
            if e["primaryEventFamily"] == "GovernanceEvent" and "advisory" in \
               e.get("dominantSemanticConsequence", "").lower():
                out.append({
                    "kind": "ADVISORY_FLAG",
                    "twin": "ADVISORY",
                    "eventRef": e["semanticEventId"],
                    "summary": e.get("notes") or e["dominantSemanticConsequence"],
                    "note": "advisory context from a dated snapshot — visible help, "
                            "never a block, never a compliance fact",
                })
        return out

    # ----------------------------------------------------------- PassportView --

    def passport_view(self, farm_ref: str, requesting_party_ref: str, *,
                      allow_recompute: bool = True) -> dict:
        """allow_recompute=False is a real render mode (cheap/offline serve):
        a STALE materialization renders only with the banner and is barred
        from export; a missing basis refuses (views/VIEWS.md)."""
        # sharing/authority re-evaluated per request (D12) — a revoked
        # inspector loses access on this call, not at next recompute
        access = self.authority.evaluate_read(
            requesting_party_ref=requesting_party_ref, farm_ref=farm_ref,
            artifact_family="PASSPORT_VIEW")
        # serialized write path (M2 G2): this render can recompute a
        # materialization, so it must hold the single-writer lock — a scheduled
        # import must not commit a newer ReferenceSnapshot mid-render and leave
        # the output reflecting a pre-import context (PR #10 review).
        with self.store.serialized_tx() as cur:
            self.store.insert_record(cur, access.request_payload)
            self.store.insert_record(cur, access.trace_payload)
            self.store.insert_record(cur, access.result_payload)
            if not access.allowed:
                return _refusal_response(
                    access.problems[0] if access.problems else runtime_problem(
                        "AUTHORITY_DENIED", "Read denied", "no read path to this farm"))

            # the no-recompute render is an exploratory serve: STALE is
            # honored as ALLOW_STALE_EXPLORATORY semantics (banner + export
            # bar below), never silently treated as FRESH
            resolution = self.materializer.resolve_for_use(
                cur, farm_ref, use_class="OPERATIONAL_DASHBOARD",
                required_freshness=("REQUIRE_FRESH" if allow_recompute
                                    else "ALLOW_STALE_EXPLORATORY"),
                high_consequence=False,
                recompute_if_needed=allow_recompute)
            mat = resolution["materialization"]
            if mat is None:
                return _refusal_response(runtime_problem(
                    "MATERIALIZATION_BASIS_MISSING", "View refuses",
                    "the materialization basis cannot be produced; the view refuses "
                    "rather than rendering unreceipted state (views/VIEWS.md)"))

            stale = resolution["freshness"] != "FRESH"
            trace_refs = [mat["basis_record_id"], mat["snapshot_record_id"],
                          mat["context_snapshot_ref"], PASSPORT_QUERYSPEC, PASSPORT_QUERYPLAN]
            qualification = _qualification(
                surface_class="PASSPORT_VIEW_PREVIEW",
                staleness="FRESH" if not stale else "STALE_BLOCKING",
                sufficiency="SUFFICIENT",
                high_consequence_allowed=False,
                trace_refs=trace_refs,
                allowed=["ADVISORY_DISPLAY", "INFORMATIONAL_DASHBOARD", "COMPLIANCE_REVIEW"],
                blocked=(["EXPORT_API_PAYLOAD", "HIGH_CONSEQUENCE_DECISION"] if stale
                         else ["HIGH_CONSEQUENCE_DECISION"]),
                safe_label="Spray register (record-keeping view)",
                user_message=CLAIM_STATEMENT,
                mat_result_ref=resolution["materializationResult"]["resultId"])

            metadata = {
                "schemaVersion": "ofarm.passportviewmetadata.v0.1",
                "passportViewId": _mint("passport"),
                "passportFamily": "FARM",
                "anchorScope": {"scopeType": "FARM", "scopeRef": farm_ref},
                "generatedAt": now_iso(),
                "twin": "COMPLIANCE",
                "freezeState": "LIVE_RECOMPUTABLE",
                "querySpecificationRef": PASSPORT_QUERYSPEC,
                "queryPlanRef": PASSPORT_QUERYPLAN,
                "contextSnapshotRef": mat["context_snapshot_ref"],
                "materializationResultRef": resolution["materializationResult"]["resultId"],
                "representationModes": ["HUMAN_READABLE", "MACHINE_READABLE"],
                "publicationState": "SERVABLE",
                "profileRefs": [config.PROFILE_REF],
                "recipientPartyRef": requesting_party_ref,
            }

            body = {
                "viewRef": PASSPORT_VIEW_REF,
                "register": mat["current_state"]["entries"],
                "exceptions": self._pending_claims(farm_ref),
                "advisoryFlags": self._advisory_flags(farm_ref),
                "freshness": resolution["freshness"],
                "staleBanner": ("STALE — recompute before any reliance; export barred"
                                if stale else None),
                "exportAllowed": not stale,
                "completeness": CLAIM_STATEMENT,
            }
            # outputs validate against their contracts before leaving the gate
            self.store.registry.validate(metadata)
            self.store.registry.validate(qualification)
            return {"refused": False, "metadata": metadata, "body": body,
                    "qualification": qualification}

    # ------------------------------------------------------- DocumentAssembly --

    def freeze_inspection_register(self, farm_ref: str, requesting_party_ref: str,
                                   window_start: str, window_end: str, *,
                                   as_submission: bool = False) -> dict:
        """Freeze the exportable inspection register for a period.

        as_submission=True files it as a SUBMISSION_ASSEMBLY export artifact.
        No external transmission is claimed: the IS Evidenca FFS interface
        does not exist until the state publishes it (D13); "filed" means the
        frozen submission artifact left the publication gate complete.
        """
        publication_action = ("FILE_SUBMISSION_ASSEMBLY" if as_submission
                              else "FREEZE_DOCUMENT_ASSEMBLY")
        output_kind = "SUBMISSION_ASSEMBLY" if as_submission else "REPORT_ASSEMBLY"
        final_outcome = "FILED" if as_submission else "FROZEN"
        # accepted Action Matrix names: approval-before-freeze vs formal filing
        decision = self.authority.evaluate(
            acting_party_ref=requesting_party_ref,
            action_class=("OUTPUT_FILE_SUBMISSION_ASSEMBLY" if as_submission
                          else "OUTPUT_APPROVE_DOCUMENT_ASSEMBLY"),
            action_stage="PUBLICATION",
            scope={"scopeType": "FARM", "scopeRef": farm_ref})
        # serialized write path (M2 G2): freezing high-consequence ATTESTED_OUTPUT
        # resolves a fresh materialization, so it must hold the single-writer lock
        # — a scheduled import must not commit a newer ReferenceSnapshot mid-freeze
        # and let the frozen document claim FRESH over a pre-import context (PR #10 review).
        with self.store.serialized_tx() as cur:
            self.store.insert_record(cur, decision.request_payload)
            self.store.insert_record(cur, decision.trace_payload)
            self.store.insert_record(cur, decision.result_payload)

            request_id = _mint("pubreq")
            doc_id = _mint("docasm")
            pub_request = {
                "schemaVersion": "ofarm.publicationassemblyrequest.v0.1",
                "requestId": request_id,
                "requestedAt": now_iso(),
                "requestedByPartyRef": requesting_party_ref,
                "publicationAction": publication_action,
                "outputKind": output_kind,
                "outputMetadataRef": doc_id,
                "targetScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
                "requiresFrozenOutput": True,
                "attestationRequested": False,
                "authorizationDecisionTraceRef": decision.trace_payload["traceId"],
            }
            self.store.insert_record(cur, pub_request)

            def publication_result(outcome, problems, reason, case_ref=None):
                payload = {
                    "schemaVersion": "ofarm.publicationassemblyresult.v0.1",
                    "resultId": _mint("pubres"),
                    "requestId": request_id,
                    "evaluatedAt": now_iso(),
                    "publicationAction": publication_action,
                    "outcome": outcome,
                    "outputKind": output_kind,
                    "outputMetadataRef": doc_id,
                    "authorizationDecisionTraceRef": decision.trace_payload["traceId"],
                    "problems": problems,
                    "reasonSummary": reason,
                }
                if case_ref:
                    payload["evidenceSufficiencyCaseRef"] = case_ref
                self.store.insert_record(cur, payload)
                return payload

            if not decision.allowed:
                problem = decision.problems[0] if decision.problems else runtime_problem(
                    "AUTHORITY_DENIED", "Export denied", "no export authority")
                publication_result("DENIED", [problem], "export authority denied")
                return _refusal_response(problem)

            # an invalid window must never freeze a valid-looking empty
            # register: refuse before any materialization, with no durable
            # artifact (hostile review finding 6, second pass)
            ws, we = parse_ts(window_start), parse_ts(window_end)
            if ws is None or we is None or ws > we:
                problem = runtime_problem(
                    "HIGH_CONSEQUENCE_BLOCKED", "Invalid window refused",
                    f"window [{window_start!r}, {window_end!r}] is unparseable or "
                    "inverted; a frozen register over an invalid period would be a "
                    "valid-looking lie (no temporal reason code exists — ERRATA E-001)")
                publication_result("DENIED", [problem], "invalid window")
                return _refusal_response(problem)

            # high-consequence: freeze only from a demonstrably FRESH window
            # materialization — recompute, refuse, or review; never silently
            # degrade (explainable-evidence RFC §15.3)
            window_policy = {"policyType": "WINDOW",
                             "windowStart": window_start, "windowEnd": window_end}
            resolution = self.materializer.resolve_for_use(
                cur, farm_ref, use_class="ATTESTED_OUTPUT", time_policy=window_policy,
                required_freshness="REQUIRE_FRESH", high_consequence=True)
            mat = resolution["materialization"]
            if mat is None or resolution["freshness"] != "FRESH":
                problem = runtime_problem(
                    "HIGH_CONSEQUENCE_BLOCKED", "Freeze refused",
                    "the inspection register could not be made FRESH for the requested "
                    "window; generation refuses rather than emitting a degraded "
                    "document silently (views/VIEWS.md)")
                publication_result("DENIED", [problem], "not demonstrably FRESH")
                return _refusal_response(problem)

            entries = mat["current_state"]["entries"]
            annex = self._pending_claims(farm_ref)
            gaps = [e["assertionRef"] for e in annex]

            # auto-generated sufficiency case at DocumentAssembly freeze — the
            # second of exactly two generation points (PROFILE.md)
            case_id = _mint("suffcase")
            case = {
                "schemaVersion": "ofarm.evidencesufficiencycase.v0.2",
                "sufficiencyCaseId": case_id,
                "generatedAt": now_iso(),
                "caseClass": ("SUBMISSION_ASSEMBLY" if as_submission
                              else "DOCUMENT_ATTESTATION"),
                "targetTwin": "COMPLIANCE",
                "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
                "subject": {"subjectType": ("SUBMISSION_ASSEMBLY" if as_submission
                                            else "DOCUMENT_ASSEMBLY"),
                            "subjectRef": doc_id},
                "governingPolicyRefs": [config.EVIDENCE_POLICY_REF],
                "materializationBasisRef": mat["basis_record_id"],
                "materializationSnapshotRef": mat["snapshot_record_id"],
                "claims": [{
                    "claimId": "claim:freeze",
                    "claimType": "OUTPUT_INTEGRITY_CLAIM",
                    "claimRef": doc_id,
                    "statement": "this frozen register reflects exactly the accepted "
                                 "consequences in the window plus a non-promoting annex "
                                 "of known gaps",
                }],
                "arguments": [{
                    "argumentId": "arg:freeze:basis",
                    "supportsClaimIds": ["claim:freeze"],
                    "policyRef": config.EVIDENCE_POLICY_REF,
                    "ruleRef": "rule:si.ffs.freeze.fresh-basis",
                    "conclusion": "SUPPORTED",
                }],
                "evidenceBundles": [{
                    "bundleId": "bundle:freeze",
                    "supportsArgumentIds": ["arg:freeze:basis"],
                    "bundleStatus": "COMPLETE",
                    "rawSourceRefs": [mat["basis_record_id"]],
                    "normalizedInterpretationRefs": [mat["snapshot_record_id"]],
                    "provenanceRefs": [mat["context_snapshot_ref"]],
                    "chainOfCustodyStatus": "PRESERVED",
                }],
                "attestationPlan": {
                    "attestationRequired": False,
                    "attestationActionFamily": ("OUTPUT_FILE_SUBMISSION_ASSEMBLY"
                                                if as_submission else
                                                "OUTPUT_APPROVE_DOCUMENT_ASSEMBLY"),
                    "portableEnvelopeMode": "NONE",
                    "notes": "freeze without portable attestation; certification-grade "
                             "attestation is exactly what a future pack adds (D8)",
                },
                "outcome": {
                    "decision": "ALLOW",
                    "rationale": "frozen from a FRESH window materialization with a "
                                 "complete basis; known gaps enumerated in the annex",
                    "attestationAllowed": False,
                },
            }
            self.store.insert_record(cur, case)

            frozen_at = now_iso()
            document = {
                "viewRef": DOCASM_VIEW_REF,
                "claimStatement": CLAIM_STATEMENT,
                "window": {"start": window_start, "end": window_end},
                "acceptedEntries": entries,
                "annex": {
                    "title": "Annex: records that did not reach accepted state "
                             "(annexing never makes truth — Constitution §10.12)",
                    "rows": annex,
                },
                "completenessStatement": {
                    "acceptedCount": len(entries),
                    "knownGaps": gaps,
                    "statement": ("complete for accepted records in the window; "
                                  f"{len(gaps)} known gap(s) enumerated, not hidden"),
                },
                "receipts": {
                    "materializationBasisRef": mat["basis_record_id"],
                    "materializationSnapshotRef": mat["snapshot_record_id"],
                    "contextSnapshotRef": mat["context_snapshot_ref"],
                    "referenceSnapshotRefs": (self.store.get_payload(
                        mat["context_snapshot_ref"]) or {}).get("referenceSnapshotRefs", []),
                    "evidenceSufficiencyCaseRef": case_id,
                },
                "frozenAt": frozen_at,
            }
            digest = "sha256:" + hashlib.sha256(
                canonical_json(document).encode()).hexdigest()
            durable_ref = f"document:si.ffs.inspection-register.{digest[7:19]}"
            version_label = f"si.ffs.inspection-register.{window_start[:10]}.{window_end[:10]}"

            metadata = {
                "schemaVersion": "ofarm.documentassemblymetadata.v0.1",
                "documentAssemblyId": doc_id,
                "documentFamily": ("SUBMISSION_ASSEMBLY" if as_submission
                                   else "REPORT_ASSEMBLY"),
                "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
                "generatedAt": frozen_at,
                "frozenAt": frozen_at,
                "twin": "COMPLIANCE",
                "querySpecificationRefs": [DOCASM_QUERYSPEC],
                "queryPlanRefs": [DOCASM_QUERYPLAN],
                "contextSnapshotRef": mat["context_snapshot_ref"],
                "materializationBasisRef": mat["basis_record_id"],
                "materializationSnapshotRef": mat["snapshot_record_id"],
                "freezeReason": ("submission assembly filed as export artifact; no "
                                 "external transmission claimed (D13)" if as_submission
                                 else "exportable inspection register requested by the farmer"),
                "reviewState": "FILED" if as_submission else "APPROVED",
                "durableArtifactRef": durable_ref,
                "versionLabel": version_label,
                "evidenceSufficiencyCaseRef": case_id,
                "authorizationDecisionTraceRef": decision.trace_payload["traceId"],
            }

            qualification = _qualification(
                surface_class="DOCUMENT_ASSEMBLY_PREVIEW",
                staleness="FRESH", sufficiency="SUFFICIENT",
                high_consequence_allowed=True,
                trace_refs=[mat["basis_record_id"], mat["snapshot_record_id"],
                            mat["context_snapshot_ref"], case_id,
                            DOCASM_QUERYSPEC, DOCASM_QUERYPLAN],
                allowed=["COMPLIANCE_REVIEW", "COMPLIANCE_OUTPUT_INPUT",
                         "EXPORT_API_PAYLOAD"],
                blocked=["HIGH_CONSEQUENCE_DECISION"],
                safe_label="Frozen inspection register (record-keeping)",
                user_message=CLAIM_STATEMENT,
                mat_result_ref=resolution["materializationResult"]["resultId"])

            # the frozen output is persisted, not just returned: the metadata
            # record makes outputMetadataRef resolve, and the digest-addressed
            # artifact lets a later inspection verify the handed-over document
            # against the store (views/VIEWS.md "Identification")
            self.store.insert_record(cur, metadata)
            self.store.registry.validate(qualification)
            cur.execute(
                "INSERT INTO export_artifact (artifact_ref, digest, metadata_record_id, document) "
                "VALUES (%s, %s, %s, %s)",
                (durable_ref, digest, doc_id, Jsonb(document)))

            publication_result(final_outcome, [],
                               (f"filed locally as {durable_ref}; the state registry "
                                "interface does not exist yet (D13), no external "
                                "transmission is claimed" if as_submission else
                                f"frozen as {durable_ref} ({version_label})"), case_id)
            return {"refused": False, "metadata": metadata, "document": document,
                    "digest": digest, "qualification": qualification}
