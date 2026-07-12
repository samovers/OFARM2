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
from .authority import AuthorityEvaluator, authority_decision_allowed
from .contracts import canonical_json
from .materializer import Materializer
from .problems import runtime_problem
from .context import ContextAssembler, mint as _mint, now_iso, parse_ts
from .profile_runtime import ProfileRuntimeError, resolve_active_descriptor
from .runtime_bundle import (RuntimeBundleError, require_store_runtime_bundle,
                             sha256_bytes)
from .store import (
    Store,
    _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION as _CURSOR_EXECUTE_MUTATION,
    _RETAINED_GOVERNED_CURSOR_EXECUTE_READ as _CURSOR_EXECUTE_READ,
)

_RETAINED_AUTHORITY_EVALUATE = AuthorityEvaluator.evaluate
_RETAINED_AUTHORITY_EVALUATE_CODE = _RETAINED_AUTHORITY_EVALUATE.__code__
_RETAINED_AUTHORITY_EVALUATE_READ = AuthorityEvaluator.evaluate_read
_RETAINED_AUTHORITY_EVALUATE_READ_CODE = \
    _RETAINED_AUTHORITY_EVALUATE_READ.__code__
_RETAINED_AUTHORITY_DECISION_ALLOWED = authority_decision_allowed
_RETAINED_AUTHORITY_DECISION_ALLOWED_CODE = \
    authority_decision_allowed.__code__

PASSPORT_VIEW_REF = "view:si.ffs.spray-register.passportview.v0_1"
DOCASM_VIEW_REF = "view:si.ffs.inspection-register.documentassembly.v0_1"
PASSPORT_QUERYSPEC = "queryspec:si.ffs.spray-register.passportview.v0_1"
PASSPORT_QUERYPLAN = "queryplan:si.ffs.spray-register.passportview.v0_1"
DOCASM_QUERYSPEC = "queryspec:si.ffs.inspection-register.documentassembly.v0_1"
DOCASM_QUERYPLAN = "queryplan:si.ffs.inspection-register.documentassembly.v0_1"

_COMPILED_OUTPUT_COMPONENT_DIGESTS = {
    ("QUERY_PLAN", DOCASM_QUERYPLAN):
        "sha256:6abdfc7a88e8f129dce28898712771fc8825f1a60aafbd1a1eee16ecf13d0236",
    ("QUERY_PLAN", PASSPORT_QUERYPLAN):
        "sha256:e86a25b5366e970275ad0348118718a63f19acfade31e7aa601cc3b2b941c0b4",
    ("QUERY_SPECIFICATION", DOCASM_QUERYSPEC):
        "sha256:932473a3d62e5b3c2e7cc80f08d02187bb8f130f06852a79d61c8e92950e77ea",
    ("QUERY_SPECIFICATION", PASSPORT_QUERYSPEC):
        "sha256:ccf0a641800ce0b3381793aece5306957e9bca64b0f47c3dcec519dfef478157",
}


def _assert_compiled_output_contract(runtime_bundle) -> None:
    """Bind hard-coded output execution to every retained plan/spec byte."""
    for (role, logical_ref), expected_digest in \
            _COMPILED_OUTPUT_COMPONENT_DIGESTS.items():
        if runtime_bundle.component(role, logical_ref).content_digest != expected_digest:
            raise RuntimeBundleError(
                f"compiled output implementation does not match {role}/{logical_ref}")

CLAIM_STATEMENT = ("This register faithfully and traceably reflects what the farm "
                   "recorded, with gaps, disputes, and unresolved bindings visible. "
                   "It claims record-keeping completeness only — never current-"
                   "compliance against the authorisation register, certification, "
                   "or legal advice.")


def _qualification(*, surface_class: str, staleness: str, sufficiency: str,
                   high_consequence_allowed: bool, trace_refs: list[str],
                   allowed: list[str], blocked: list[str],
                   safe_label: str, user_message: str,
                   dispute: str = "NONE",
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
        "disputeStatus": dispute,
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


class OutputGenerator:
    _SEALED_FIELDS = {
        "store", "active_profile", "runtime_bundle", "authority", "materializer",
        "_runtime_composition_sealed"}

    def __setattr__(self, name, value):
        if getattr(self, "_runtime_composition_sealed", False):
            if name in self._SEALED_FIELDS:
                raise AttributeError(
                    "OutputGenerator runtime composition is immutable")
            if callable(getattr(type(self), name, None)):
                raise AttributeError(
                    "OutputGenerator runtime dispatch is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if (getattr(self, "_runtime_composition_sealed", False)
                and (name in self._SEALED_FIELDS
                     or callable(getattr(type(self), name, None)))):
            raise AttributeError(
                "OutputGenerator sealed runtime state cannot be deleted")
        object.__delattr__(self, name)

    def __init__(self, store, *, active_descriptor=None, active_profile=None,
                 runtime_bundle=None):
        self.store = store
        if (active_descriptor is not None and active_profile is not None
                and active_descriptor != active_profile):
            raise ProfileRuntimeError(
                "active_descriptor and active_profile refer to different descriptors")
        self.active_profile = resolve_active_descriptor(
            active_descriptor if active_descriptor is not None else active_profile,
            allow_config_default=True,
        )
        self.runtime_bundle = runtime_bundle or store.runtime_bundle
        require_store_runtime_bundle(store, self.runtime_bundle, "OutputGenerator")
        if self.runtime_bundle.descriptor != self.active_profile:
            raise ProfileRuntimeError(
                "OutputGenerator descriptor and RuntimeBundle do not match exactly")
        _assert_compiled_output_contract(self.runtime_bundle)
        self.authority = AuthorityEvaluator(store)
        self.materializer = Materializer(
            store, active_descriptor=self.active_profile,
            runtime_bundle=self.runtime_bundle)
        self._runtime_composition_sealed = True

    def _assert_runtime_composition(self) -> None:
        require_store_runtime_bundle(
            self.store, self.runtime_bundle, "OutputGenerator decision")
        authority_namespace_missing = False
        try:
            authority_namespace = object.__getattribute__(
                self.authority, "__dict__")
        except AttributeError:
            authority_namespace_missing = True
            authority_namespace = None
        if (type(self) is not OutputGenerator
                or type(self.store) is not Store
                or type(self.authority) is not AuthorityEvaluator
                or vars(AuthorityEvaluator).get("evaluate") is not
                _RETAINED_AUTHORITY_EVALUATE
                or _RETAINED_AUTHORITY_EVALUATE.__code__ is not
                _RETAINED_AUTHORITY_EVALUATE_CODE
                or vars(AuthorityEvaluator).get("evaluate_read") is not
                _RETAINED_AUTHORITY_EVALUATE_READ
                or _RETAINED_AUTHORITY_EVALUATE_READ.__code__ is not
                _RETAINED_AUTHORITY_EVALUATE_READ_CODE
                or authority_decision_allowed is not
                _RETAINED_AUTHORITY_DECISION_ALLOWED
                or _RETAINED_AUTHORITY_DECISION_ALLOWED.__code__ is not
                _RETAINED_AUTHORITY_DECISION_ALLOWED_CODE
                or type(self.materializer) is not Materializer
                or type(self.materializer.context) is not ContextAssembler
                or self._runtime_composition_sealed is not True
                or self.materializer._runtime_composition_sealed is not True
                or self.materializer.context._runtime_composition_sealed is not True
                or any(callable(getattr(OutputGenerator, name, None))
                       for name in vars(self))
                or (not authority_namespace_missing
                    and (type(authority_namespace) is not dict
                         or any(callable(getattr(
                             AuthorityEvaluator, name, None))
                                for name in authority_namespace)))
                or any(callable(getattr(Materializer, name, None))
                       for name in vars(self.materializer))
                or any(callable(getattr(ContextAssembler, name, None))
                       for name in vars(self.materializer.context))
                or self.runtime_bundle.descriptor != self.active_profile
                or self.authority.store is not self.store
                or self.materializer.store is not self.store
                or self.materializer.runtime_bundle is not self.runtime_bundle
                or self.materializer.active_profile != self.active_profile
                or self.materializer.context.store is not self.store
                or self.materializer.context.runtime_bundle is not self.runtime_bundle):
            Store._mark_transaction_integrity_violation(self.store)
            raise RuntimeBundleError(
                "OutputGenerator runtime composition changed after construction")
        _assert_compiled_output_contract(self.runtime_bundle)

    def _runtime_receipt(self, **payloads) -> dict:
        return {
            "runtimeBundleDigest": self.runtime_bundle.digest,
            "payloadDigests": {
                name: sha256_bytes(canonical_json(payload).encode("utf-8"))
                for name, payload in sorted(payloads.items())
            },
        }

    def _refusal_response(
            self, problem: dict, qualification: dict | None = None) -> dict:
        return {
            "refused": True,
            "problem": problem,
            "qualification": qualification,
            "runtimeReceipt": self._runtime_receipt(
                problem=problem, qualification=qualification),
        }

    # ---------------------------------------------------------------- shared --

    def _dispute_status(self, basis_record_id: str, presented_refs=()) -> str:
        """Derive disputeStatus (spec §6.5) from a materialization's basis members.
        A basis consequence with an open DISPUTE edge is OPEN_DISPUTE when it is
        DIRECTLY PRESENTED as an entry of the result, else DISPUTED_BASIS (the
        result only derives from it). A current member whose LINEAGE_SUPERSEDES
        predecessor carried a DISPUTE edge is CORRECTED (walk the supersession
        edge — the disputed predecessor has left force and is no longer in the
        basis). Two or more distinct non-NONE statuses -> MIXED; else NONE.
        (SUPERSEDED is for historical / AS_OF surfaces that reference an
        out-of-force disputed consequence — not the current NOW surfaces here;
        deferred to G6.)"""
        basis = self.store.get_record(basis_record_id)
        refs = (basis["payload"].get("contributingAcceptedConsequenceRefs", [])
                if basis else [])
        presented = set(presented_refs)
        statuses = set()
        for cid in refs:
            # is_superseded guards a STALE basis that still lists a now-superseded
            # member (an unresolved dispute is on an in-force consequence)
            if self.store.edges_from(cid, "DISPUTE") and not self.store.is_superseded(cid):
                statuses.add("OPEN_DISPUTE" if cid in presented else "DISPUTED_BASIS")
            if self._lineage_has_dispute(cid):
                statuses.add("CORRECTED")
        if len(statuses) >= 2:
            return "MIXED"
        return statuses.pop() if statuses else "NONE"

    def _lineage_has_dispute(self, cid: str) -> bool:
        """True if ANY superseded predecessor in cid's `LINEAGE_SUPERSEDES` chain
        carries a `DISPUTE` edge — walked TRANSITIVELY, because a correction may
        itself be corrected (C1 disputed ← C2 ← C3: C3's current basis member
        descends from C1's resolved dispute, two hops back). A visited set guards
        against cycles."""
        seen: set[str] = set()
        stack = [e["dst_record_id"] for e in self.store.edges_from(cid, "LINEAGE_SUPERSEDES")]
        while stack:
            pred = stack.pop()
            if pred in seen:
                continue
            seen.add(pred)
            if self.store.edges_from(pred, "DISPUTE"):
                return True
            stack.extend(e["dst_record_id"]
                         for e in self.store.edges_from(pred, "LINEAGE_SUPERSEDES"))
        return False

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
        OutputGenerator._assert_runtime_composition(self)
        # serialized write path (M2 G2): this render can recompute a
        # materialization, so it must hold the single-writer lock — a scheduled
        # import must not commit a newer ReferenceSnapshot mid-render and leave
        # the output reflecting a pre-import context (PR #10 review).
        with Store.serialized_tx(self.store) as cur:
            # Sharing/authority is selected only after the same writer lock
            # that protects its consumption. A revocation cannot land between
            # this decision and the rendered output.
            access = _RETAINED_AUTHORITY_EVALUATE_READ(
                self.authority,
                cur=cur,
                requesting_party_ref=requesting_party_ref,
                farm_ref=farm_ref,
                artifact_family="PASSPORT_VIEW",
            )
            access_allowed = _RETAINED_AUTHORITY_DECISION_ALLOWED(access)
            self.store.insert_record(cur, access.request_payload)
            self.store.insert_record(cur, access.trace_payload)
            self.store.insert_record(cur, access.result_payload)
            if not access_allowed:
                return self._refusal_response(
                    access.problems[0] if access.problems else runtime_problem(
                        "AUTHORITY_DENIED", "Read denied", "no read path to this farm"))

            # the no-recompute render is an exploratory serve: STALE is
            # honored as ALLOW_STALE_EXPLORATORY semantics (banner + export
            # bar below), never silently treated as FRESH
            resolution = Materializer.resolve_for_use(
                self.materializer, cur, farm_ref,
                use_class="OPERATIONAL_DASHBOARD",
                required_freshness=("REQUIRE_FRESH" if allow_recompute
                                    else "ALLOW_STALE_EXPLORATORY"),
                high_consequence=False,
                recompute_if_needed=allow_recompute)
            mat = resolution["materialization"]
            if mat is None:
                return self._refusal_response(runtime_problem(
                    "MATERIALIZATION_BASIS_MISSING", "View refuses",
                    "the materialization basis cannot be produced; the view refuses "
                    "rather than rendering unreceipted state (views/VIEWS.md)"))

            stale = resolution["freshness"] != "FRESH"
            trace_refs = [mat["basis_record_id"], mat["snapshot_record_id"],
                          mat["context_snapshot_ref"], PASSPORT_QUERYSPEC, PASSPORT_QUERYPLAN]
            # disputeStatus is DERIVED, never assumed NONE (spec §6.5, closes the
            # latent M4 over-claim); the passport SHOWS a disputed basis
            # (informational), never hides it (Kernel rule 7). The register
            # directly presents per-consequence entries, so a disputed presented
            # entry is OPEN_DISPUTE (not merely DISPUTED_BASIS).
            presented = {e.get("consequenceRef") for e in mat["current_state"]["entries"]}
            dispute = self._dispute_status(mat["basis_record_id"], presented)
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
                dispute=dispute,
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
                "profileRefs": [self.active_profile.profile_ref],
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
                    "qualification": qualification,
                    "runtimeReceipt": self._runtime_receipt(
                        metadata=metadata, body=body, qualification=qualification)}

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
        OutputGenerator._assert_runtime_composition(self)
        publication_action = ("FILE_SUBMISSION_ASSEMBLY" if as_submission
                              else "FREEZE_DOCUMENT_ASSEMBLY")
        output_kind = "SUBMISSION_ASSEMBLY" if as_submission else "REPORT_ASSEMBLY"
        final_outcome = "FILED" if as_submission else "FROZEN"
        # serialized write path (M2 G2): freezing high-consequence ATTESTED_OUTPUT
        # resolves a fresh materialization, so it must hold the single-writer lock
        # — a scheduled import must not commit a newer ReferenceSnapshot mid-freeze
        # and let the frozen document claim FRESH over a pre-import context (PR #10 review).
        with Store.serialized_tx(self.store) as cur:
            # Accepted Action Matrix names: approval-before-freeze vs formal
            # filing. Selection and use share this serialized transaction.
            decision = _RETAINED_AUTHORITY_EVALUATE(
                self.authority,
                cur=cur,
                acting_party_ref=requesting_party_ref,
                action_class=("OUTPUT_FILE_SUBMISSION_ASSEMBLY" if as_submission
                              else "OUTPUT_APPROVE_DOCUMENT_ASSEMBLY"),
                action_stage="PUBLICATION",
                scope={"scopeType": "FARM", "scopeRef": farm_ref},
            )
            decision_allowed = _RETAINED_AUTHORITY_DECISION_ALLOWED(decision)
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

            if not decision_allowed:
                problem = decision.problems[0] if decision.problems else runtime_problem(
                    "AUTHORITY_DENIED", "Export denied", "no export authority")
                publication_result("DENIED", [problem], "export authority denied")
                return self._refusal_response(problem)

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
                return self._refusal_response(problem)

            # high-consequence: freeze only from a demonstrably FRESH window
            # materialization — recompute, refuse, or review; never silently
            # degrade (explainable-evidence RFC §15.3)
            window_policy = {"policyType": "WINDOW",
                             "windowStart": window_start, "windowEnd": window_end}
            resolution = Materializer.resolve_for_use(
                self.materializer, cur, farm_ref,
                use_class="ATTESTED_OUTPUT", time_policy=window_policy,
                required_freshness="REQUIRE_FRESH", high_consequence=True)
            mat = resolution["materialization"]
            if mat is None or resolution["freshness"] != "FRESH":
                problem = runtime_problem(
                    "HIGH_CONSEQUENCE_BLOCKED", "Freeze refused",
                    "the inspection register could not be made FRESH for the requested "
                    "window; generation refuses rather than emitting a degraded "
                    "document silently (views/VIEWS.md)")
                publication_result("DENIED", [problem], "not demonstrably FRESH")
                return self._refusal_response(problem)

            # the freeze refuses on the DISPUTE axis, INDEPENDENT of freshness
            # (spec §6.6): the window materialization may be FRESH yet rest on a
            # disputed basis, and a disputed truth is never frozen into a
            # high-consequence output until corrected. NONE/CORRECTED pass; any
            # unresolved dispute (OPEN_DISPUTE / DISPUTED_BASIS / MIXED) refuses.
            window_presented = {e.get("consequenceRef")
                                for e in mat["current_state"]["entries"]}
            window_dispute = self._dispute_status(mat["basis_record_id"], window_presented)
            if window_dispute not in ("NONE", "CORRECTED"):
                problem = runtime_problem(
                    "DISPUTE_OPEN", "Freeze refused — disputed basis",
                    "the inspection register's window basis includes a disputed "
                    "accepted consequence; a disputed truth is never frozen into a "
                    "high-consequence output until the dispute is resolved by "
                    "correction (docs/REVIEW_DISPUTE_SEMANTICS.md §6.6)")
                publication_result("DENIED", [problem], "disputed basis")
                return self._refusal_response(problem)

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
                    "runtimeBundleDigest": self.runtime_bundle.digest,
                },
                "frozenAt": frozen_at,
            }
            digest = "sha256:" + hashlib.sha256(
                canonical_json(document).encode()).hexdigest()
            durable_ref = f"document:si.ffs.inspection-register.{digest}"
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
                dispute=window_dispute,   # NONE or CORRECTED here (any open dispute refused above)
                mat_result_ref=resolution["materializationResult"]["resultId"])

            # the frozen output is persisted, not just returned: the metadata
            # record makes outputMetadataRef resolve, and the digest-addressed
            # artifact lets a later inspection verify the handed-over document
            # against the store (views/VIEWS.md "Identification")
            self.store.insert_record(cur, metadata)
            self.store.registry.validate(qualification)
            _CURSOR_EXECUTE_READ(cur,
                "SELECT digest, metadata_record_id, document, runtime_bundle_digest "
                "FROM ONLY export_artifact WHERE artifact_ref = %s", (durable_ref,))
            prior_artifact = cur.fetchone()
            if prior_artifact is None:
                _CURSOR_EXECUTE_MUTATION(cur,
                    "INSERT INTO export_artifact "
                    "(artifact_ref, digest, metadata_record_id, document, "
                    "runtime_bundle_digest) VALUES (%s, %s, %s, %s, %s)",
                    (durable_ref, digest, doc_id, Jsonb(document),
                     self.runtime_bundle.digest))
            elif (prior_artifact["digest"] != digest
                  or prior_artifact["metadata_record_id"] != doc_id
                  or canonical_json(prior_artifact["document"]) != canonical_json(document)
                  or prior_artifact["runtime_bundle_digest"] != self.runtime_bundle.digest):
                raise RuntimeError(
                    "frozen output content identity was reused for unequal canonical bytes")

            publication_result(final_outcome, [],
                               (f"filed locally as {durable_ref}; the state registry "
                                "interface does not exist yet (D13), no external "
                                "transmission is claimed" if as_submission else
                                f"frozen as {durable_ref} ({version_label})"), case_id)
            return {"refused": False, "metadata": metadata, "document": document,
                    "digest": digest, "qualification": qualification,
                    "runtimeReceipt": self._runtime_receipt(
                        metadata=metadata, document=document,
                        qualification=qualification)}
