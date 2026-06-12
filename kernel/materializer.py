"""Materializer (M1 brief tasks 1 + 4).

Deterministic: in-force records in → current state + MaterializationBasis +
freshness out (Kernel rule 5). Implements the explainable-evidence draft
shapes — MaterializationKey, MaterializationFreshnessVector,
MaterializationDependencyIndex, InvalidationEvaluationTrace — behind Kernel
law without promoting them (D16): draft records land in runtime_trace, never
in the canonical record table, and every one carries the DRAFT_NON_DEFAULT
governance quintet its schema requires.

Invalidation is basis-set staleness (D12): a materialization goes STALE when
any member of its MaterializationBasis is superseded/revoked/version-bumped,
when its ContextSnapshot's components change, or when its time policy expires.
Authority/sharing changes never stale truth — they are re-evaluated per
request at the sharing gate. Per the RFC's dependency-broadening rule (§6.5),
an undeterminable dependency boundary broadens invalidation, never narrows it.
"""
from __future__ import annotations

import hashlib
import uuid

from . import config
from .context import ContextAssembler, now_iso, parse_ts
from .contracts import canonical_json
from psycopg.types.json import Jsonb

MATERIALIZATION_POLICY_REF = "policy:si.ffs.materialization.v0_1"
RESULT_SHAPE_FAMILY = "si.ffs.spray-register.v0_1"
RUNTIME_VERSION = "ofarm2-kernel-m1.0"

_USE_CLASS_MAP = {
    # draft MaterializationKey useClass -> canonical MaterializationRequest useClass
    "OPERATIONAL_DASHBOARD": "EXPLORATORY",
    "EXPLORATORY_VIEW": "EXPLORATORY",
    "COMPLIANCE_DECISION_SUPPORT": "HIGH_CONSEQUENCE",
    "ATTESTED_OUTPUT": "ATTESTED_OUTPUT",
    "FORMAL_SUBMISSION": "ATTESTED_OUTPUT",
    "FORENSIC_AUDIT": "AUDIT_EXPLANATION",
}


def _mint(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex[:16]}"


def _digest12(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode()).hexdigest()[:12]


class Materializer:
    def __init__(self, store):
        self.store = store
        self.context = ContextAssembler(store)

    # ------------------------------------------------------------------ key --

    def build_key(self, farm_ref: str, *, twin: str, use_class: str,
                  time_policy: dict, context_snapshot_ref: str) -> dict:
        key_core = {
            "deploymentScope": {"scopeType": "TENANT", "scopeRef": config.TENANT_REF},
            "twin": twin,
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
            "evaluationTimePolicy": time_policy,
            "contextSnapshotRef": context_snapshot_ref,
            "materializationPolicyRef": MATERIALIZATION_POLICY_REF,
            "useClass": use_class,
            "resultShapeFamily": RESULT_SHAPE_FAMILY,
            "policyVersionRef": MATERIALIZATION_POLICY_REF,
        }
        key_id = f"matkey:{_digest12(key_core)}"
        return {
            "schemaVersion": "ofarm.explainableCurrentStateEvidence.materializationKey.v0.1-draft",
            "artifactType": "MaterializationKey",
            "contractStatus": "DRAFT_NON_DEFAULT",
            "draftNonDefault": True,
            "promotedToCurrentDefault": False,
            "materializationKeyId": key_id,
            **key_core,
        }

    # ------------------------------------------------------- freshness vector --

    def _watermark(self, kind: str) -> str:
        with self.store.conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) AS n, coalesce(max(record_time)::text, 'none') AS t "
                "FROM kernel_record WHERE record_kind = %s", (kind,))
            row = cur.fetchone()
            return f"{row['n']}@{row['t']}"

    def build_freshness_vector(self, key: dict, basis_id: str,
                               context_snapshot_ref: str, reference_refs: list[str]) -> dict:
        dims = [
            {"dimensionFamily": "CANONICAL_ASSERTION_HISTORY",
             "sourceRef": "kernel_record/ofarm.assertionrecord.v0.1",
             "observedSequence": self._watermark("ofarm.assertionrecord.v0.1")},
            {"dimensionFamily": "ACCEPTED_EVENT_CONSEQUENCE",
             "sourceRef": "kernel_record/ofarm.acceptedeventconsequence.v0.1",
             "observedSequence": self._watermark("ofarm.acceptedeventconsequence.v0.1")},
            {"dimensionFamily": "REVIEW_DECISION",
             "sourceRef": "kernel_record/ofarm.reviewdecision.v0.1",
             "observedSequence": self._watermark("ofarm.reviewdecision.v0.1")},
            {"dimensionFamily": "IDENTITY_LIFECYCLE",
             "sourceRef": "kernel_record/ofarm.identityrecord.v0.1",
             "observedSequence": self._watermark("ofarm.identityrecord.v0.1")},
            {"dimensionFamily": "CONTEXT_SNAPSHOT",
             "sourceRef": context_snapshot_ref,
             "observedVersionRef": context_snapshot_ref},
            {"dimensionFamily": "RULE_EVIDENCE_POLICY",
             "sourceRef": config.EVIDENCE_POLICY_REF,
             "observedVersionRef": config.EVIDENCE_POLICY_REF},
            {"dimensionFamily": "QUERY_PLAN_OR_MATERIALIZATION_POLICY",
             "sourceRef": MATERIALIZATION_POLICY_REF,
             "observedVersionRef": MATERIALIZATION_POLICY_REF},
        ]
        for ref in reference_refs:
            dims.append({"dimensionFamily": "REFERENCE_SNAPSHOT",
                         "sourceRef": ref, "observedVersionRef": ref})
        return {
            "schemaVersion": "ofarm.explainableCurrentStateEvidence.materializationFreshnessVector.v0.1-draft",
            "artifactType": "MaterializationFreshnessVector",
            "contractStatus": "DRAFT_NON_DEFAULT",
            "draftNonDefault": True,
            "promotedToCurrentDefault": False,
            "freshnessVectorId": _mint("freshvec"),
            "materializationKeyRef": key["materializationKeyId"],
            "materializationBasisRef": basis_id,
            "observedAt": now_iso(),
            "versionDimensions": dims,
            "vectorIsNotMaterializationBasis": True,
            "wallClockIsNotSoleHighConsequenceBasis": True,
        }

    # ------------------------------------------------------------- recompute --

    def recompute(self, cur, farm_ref: str, *, twin: str = "COMPLIANCE",
                  use_class: str = "OPERATIONAL_DASHBOARD",
                  time_policy: dict | None = None) -> dict:
        """Deterministic recompute of one governed answer. Returns the
        derived_materialization row content (with record refs)."""
        time_policy = time_policy or {"policyType": "NOW"}
        ctx = self.context.assemble(cur, farm_ref, target_twin=twin,
                                    evaluation_time_policy=time_policy)
        ctx_ref = ctx["contextSnapshotId"]
        reference_refs = ctx.get("referenceSnapshotRefs", [])
        key = self.build_key(farm_ref, twin=twin, use_class=use_class,
                             time_policy=time_policy, context_snapshot_ref=ctx_ref)
        key_id = key["materializationKeyId"]

        # ---- gather in-force substrate (Compliance twin: hard truth only) ----
        # AS_OF reconstructs in-force-ness as of that moment from the append-
        # only substrate (acceptance and supersession-edge record times) —
        # never silently treated like NOW (hostile review finding 6)
        as_of = (time_policy.get("asOfTime")
                 if time_policy["policyType"] == "AS_OF" else None)
        consequences = self.store.in_force_consequences(farm_ref, as_of=as_of)
        window = time_policy if time_policy["policyType"] == "WINDOW" else None
        ws = parse_ts(window["windowStart"]) if window else None
        we = parse_ts(window["windowEnd"]) if window else None
        as_of_dt = parse_ts(as_of) if as_of else None
        entries, assertion_refs, consequence_refs, review_refs, identity_refs = [], [], [], [], []
        for row in consequences:
            c = row["payload"]
            event = self.store.get_payload(c["sourceEventRef"])
            # the spray register materializes accepted executed interventions;
            # other in-force consequence families (structural, compliance) are
            # not register rows and never silently inflate it
            if c["consequenceType"] != "EXECUTION_CONFIRMED":
                continue
            if event and event.get("primaryEventFamily") != "InterventionEvent":
                continue
            if window:
                eff = parse_ts(c.get("effectiveFrom")
                               or (event or {}).get("timeSemantics", {}).get("eventTime")
                               or c["acceptedAt"])
                # unparseable or out-of-window effective times exclude the row
                # only with a real datetime comparison, never a string compare
                if eff is None or ws is None or we is None or not (ws <= eff <= we):
                    continue
            if as_of_dt is not None:
                eff = parse_ts(c.get("effectiveFrom")
                               or (event or {}).get("timeSemantics", {}).get("eventTime")
                               or c["acceptedAt"])
                if eff is None or eff > as_of_dt:
                    continue   # the event had not (effectively) happened by asOfTime
            consequence_refs.append(c["acceptedEventConsequenceId"])
            review_refs.append(c["acceptedByReviewDecisionRef"])
            entry = {
                "consequenceRef": c["acceptedEventConsequenceId"],
                "eventRef": c["sourceEventRef"],
                "subject": c["subject"],
                "acceptedAt": c["acceptedAt"],
                "effectiveFrom": c.get("effectiveFrom"),
            }
            if event:
                entry["eventTime"] = event["timeSemantics"].get("eventTime")
                for payload_ref in event.get("executionRecordPayloadRefs", []):
                    erp = self.store.get_payload(payload_ref)
                    if erp:
                        entry["executionRecordPayloadRef"] = payload_ref
                        entry["actualAction"] = erp["actualAction"]
                        entry["actualQuantityParameters"] = erp.get("actualQuantityParameters", [])
                        entry["executionExtent"] = {
                            "extentClass": erp["executionExtent"]["extentClass"],
                            "targetScope": erp["executionExtent"]["targetScope"],
                        }
                        entry["actor"] = erp["actor"]
                        entry["equipment"] = erp.get("equipment", {})
                        entry["bindingRefs"] = erp.get("agronomicIdentityBindingRefs", [])
                        # identity basis: every governed identity whose revision
                        # or lifecycle change affects this entry's interpretation
                        # (extent target + carrier anchor scopes that resolve to
                        # identity records — fields, zones, crop cycles, sites)
                        for scope in ([erp["executionExtent"]["targetScope"]]
                                      + erp.get("anchorScopes", [])):
                            if scope["scopeType"] in ("FIELD", "ZONE", "CROP_CYCLE",
                                                      "SITE", "LOT", "FACILITY"):
                                ident = self.store.get_record(scope["scopeRef"])
                                if ident and ident["record_kind"] == "ofarm.identityrecord.v0.1":
                                    identity_refs.append(scope["scopeRef"])
            entries.append(entry)
            # assertions joined through the shared source event
            for edge in self.store.edges_to(c["sourceEventRef"], "EVENT_SOURCE"):
                src = self.store.get_record(edge["src_record_id"])
                if src and src["record_kind"] == "ofarm.assertionrecord.v0.1":
                    assertion_refs.append(src["record_id"])

        entries.sort(key=lambda e: e.get("eventTime") or e["acceptedAt"], reverse=True)
        generated_at = now_iso()
        current_state = {
            "stateKind": RESULT_SHAPE_FAMILY,
            "derived": True,
            "farmRef": farm_ref,
            "targetTwin": twin,
            "generatedAt": generated_at,
            "entries": entries,
            "entryCount": len(entries),
        }

        # ---- governed receipts (canonical records) ----
        basis_id = _mint("matbasis")
        basis = {
            "schemaVersion": "ofarm.materializationbasis.v0.1",
            "basisId": basis_id,
            "twin": twin,
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
            "contextSnapshotRefs": [ctx_ref],
            "evaluationTimePolicy": time_policy,
            "contributingAssertionRefs": sorted(set(assertion_refs)),
            "contributingAcceptedConsequenceRefs": consequence_refs,
            "contributingReviewDecisionRefs": sorted(set(review_refs)),
        }
        if identity_refs:
            basis["identityBasisRefs"] = sorted(set(identity_refs))
        self.store.insert_record(cur, basis)
        for ref in consequence_refs + basis["contributingAssertionRefs"] + basis["contributingReviewDecisionRefs"]:
            self.store.add_edge(cur, "MATERIALIZATION_BASIS", basis_id, ref)

        mat_id = _mint("mat")
        snapshot_id = _mint("matsnap")
        snapshot = {
            "schemaVersion": "ofarm.materializationsnapshot.v0.1",
            "snapshotId": snapshot_id,
            "generatedAt": generated_at,
            "twin": twin,
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
            "materializationBasisRef": basis_id,
            "freshnessState": "FRESH",
            "declaredUseClass": _USE_CLASS_MAP.get(use_class, "EXPLORATORY"),
            "retentionReason": "governed current-state answer retained with its receipts (Kernel rule 5)",
            "materializedStateRef": f"derivedstate:{mat_id}",
        }
        self.store.insert_record(cur, snapshot)

        # ---- draft-lane evidence (D16) ----
        vector = self.build_freshness_vector(key, basis_id, ctx_ref, reference_refs)
        if not self.store.runtime_trace_exists(key_id):
            self.store.insert_runtime_trace(cur, key)  # key id is content-stable
        self.store.insert_runtime_trace(cur, vector)
        dep_index = self._build_dependency_index(key_id, basis, ctx_ref, reference_refs, use_class)
        self.store.insert_runtime_trace(cur, dep_index)

        # ---- supersede prior live materialization for this key ----
        cur.execute(
            "SELECT materialization_id FROM derived_materialization "
            "WHERE key_digest = %s AND superseded_by IS NULL", (key_id,))
        for prior in cur.fetchall():
            cur.execute(
                "UPDATE derived_materialization SET superseded_by = %s "
                "WHERE materialization_id = %s", (mat_id, prior["materialization_id"]))

        cur.execute(
            """
            INSERT INTO derived_materialization
              (materialization_id, key_digest, materialization_key, target_twin,
               anchor_scope_ref, time_policy, use_class, freshness, current_state,
               basis_record_id, snapshot_record_id, context_snapshot_ref, freshness_vector)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'FRESH', %s, %s, %s, %s, %s)
            """,
            (mat_id, key_id, Jsonb(key), twin, farm_ref, Jsonb(time_policy), use_class,
             Jsonb(current_state), basis_id, snapshot_id, ctx_ref, Jsonb(vector)))
        # fast-lookup rows mirroring the dependency-index entries (derived only)
        for entry in dep_index["entries"]:
            cur.execute(
                "INSERT INTO derived_dependency_index "
                "(dependency_source_ref, dependency_source_family, key_digest, entry) "
                "VALUES (%s, %s, %s, %s)",
                (entry["dependencySourceRef"], entry["dependencySourceFamily"],
                 key_id, Jsonb(entry)))

        return {
            "materializationId": mat_id,
            "materializationKey": key,
            "basisRef": basis_id,
            "snapshotRef": snapshot_id,
            "contextSnapshotRef": ctx_ref,
            "freshness": "FRESH",
            "currentState": current_state,
            "freshnessVector": vector,
        }

    def _build_dependency_index(self, key_id: str, basis: dict, ctx_ref: str,
                                reference_refs: list[str], use_class: str) -> dict:
        use_classes = sorted({use_class, "COMPLIANCE_DECISION_SUPPORT", "ATTESTED_OUTPUT"})
        def entry(src, family, trigger, impact):
            return {
                "entryId": _mint("depent"),
                "dependencySourceRef": src,
                "dependencySourceFamily": family,
                "affectedMaterializationKeyRef": key_id,
                "impactScope": basis["anchorScopes"][0]["scopeRef"],
                "affectedUseClasses": use_classes,
                "invalidationTriggerClass": trigger,
                "expectedStatusImpactCandidate": impact,
                "derivationSource": "MATERIALIZATION_POLICY",
            }
        entries = [entry(ctx_ref, "CONTEXT_SNAPSHOT", "CONTEXT_CHANGED", "STALE"),
                   entry(config.EVIDENCE_POLICY_REF, "RULE_EVIDENCE_POLICY", "POLICY_CHANGED", "STALE"),
                   entry(basis["anchorScopes"][0]["scopeRef"], "IDENTITY_LIFECYCLE",
                         "IDENTITY_CHANGED", "STALE")]
        # every identity the basis names is an invalidation dependency — a
        # field revision or crop-cycle replant must stale exactly the keys
        # that depended on that identity (Current-State RFC trigger families)
        for ref in basis.get("identityBasisRefs", []):
            entries.append(entry(ref, "IDENTITY_LIFECYCLE", "IDENTITY_CHANGED", "STALE"))
        for ref in reference_refs:
            entries.append(entry(ref, "REFERENCE_SNAPSHOT", "REFERENCE_CHANGED", "STALE"))
        for ref in basis["contributingAcceptedConsequenceRefs"]:
            entries.append(entry(ref, "ACCEPTED_EVENT_CONSEQUENCE", "BASIS_ADVANCED", "STALE"))
        for ref in basis["contributingAssertionRefs"]:
            entries.append(entry(ref, "TRUTH_BASIS", "BASIS_ADVANCED", "STALE"))
        for ref in basis["contributingReviewDecisionRefs"]:
            entries.append(entry(ref, "REVIEW_DECISION", "BASIS_ADVANCED", "STALE"))
        if basis["evaluationTimePolicy"]["policyType"] != "NOW":
            entries.append(entry("evaluation-time-boundary", "EVALUATION_TIME_BOUNDARY",
                                 "TIME_BOUNDARY_REACHED", "STALE"))
        return {
            "schemaVersion": "ofarm.explainableCurrentStateEvidence.materializationDependencyIndex.v0.1-draft",
            "artifactType": "MaterializationDependencyIndex",
            "contractStatus": "DRAFT_NON_DEFAULT",
            "draftNonDefault": True,
            "promotedToCurrentDefault": False,
            "dependencyIndexId": _mint("depidx"),
            "generatedAt": now_iso(),
            "indexPolicyVersion": MATERIALIZATION_POLICY_REF,
            "derivedOnly": True,
            "doesNotCreateCanonicalFarmTruth": True,
            "derivationSources": ["MATERIALIZATION_POLICY"],
            "entries": entries,
            "corruptionHandling": {"highConsequenceFallbacks": ["RECOMPUTE", "REFUSE", "REVIEW"]},
        }

    # ----------------------------------------------------------- invalidation --

    def invalidate_for_sources(self, cur, source_refs: list[str], *,
                               trigger_family: str, trigger_source_ref: str,
                               farm_scope_ref: str | None = None,
                               reason_code: str = "BASIS_ADVANCED") -> int:
        """Basis-set invalidation (D12): mark every live materialization whose
        dependency index touches any source_ref STALE, with an
        InvalidationEvaluationTrace per affected key (draft lane, D16).

        If farm_scope_ref is given and no dependency entry matches, broaden to
        every live materialization anchored on that farm (RFC §6.5: broaden,
        never narrow unsafely).
        """
        cur.execute(
            "SELECT dependency_source_ref, key_digest FROM derived_dependency_index "
            "WHERE dependency_source_ref = ANY(%s)", (source_refs,))
        rows = cur.fetchall()
        key_ids = sorted({r["key_digest"] for r in rows})
        resolved_sources = {r["dependency_source_ref"] for r in rows}
        unresolved = [s for s in source_refs if s not in resolved_sources]
        broadened = ""
        if unresolved and farm_scope_ref:
            # RFC §6.5: when ANY trigger in the batch has no dependency entry,
            # broaden for it rather than narrow unsafely — mixed batches must
            # not under-invalidate just because some triggers resolved
            cur.execute(
                "SELECT DISTINCT key_digest FROM derived_materialization "
                "WHERE anchor_scope_ref = %s AND superseded_by IS NULL", (farm_scope_ref,))
            key_ids = sorted(set(key_ids) | {r["key_digest"] for r in cur.fetchall()})
            broadened = (f"farm-scope broadening applied for {len(unresolved)} "
                         "trigger(s) with no dependency entry (uncertain boundary)")

        cur.execute(
            "SELECT count(*) AS n FROM derived_materialization WHERE superseded_by IS NULL")
        considered = cur.fetchone()["n"]
        marked = 0
        for key_id in key_ids:
            cur.execute(
                "UPDATE derived_materialization SET freshness = 'STALE' "
                "WHERE key_digest = %s AND superseded_by IS NULL AND freshness = 'FRESH' "
                "RETURNING materialization_id", (key_id,))
            changed = cur.fetchall()
            if not changed:
                continue
            marked += len(changed)
            trace = {
                "schemaVersion": "ofarm.explainableCurrentStateEvidence.invalidationEvaluationTrace.v0.1-draft",
                "artifactType": "InvalidationEvaluationTrace",
                "contractStatus": "DRAFT_NON_DEFAULT",
                "draftNonDefault": True,
                "promotedToCurrentDefault": False,
                "traceId": _mint("invtrace"),
                "triggerId": _mint("trigger"),
                "triggerFamily": trigger_family,
                "triggerSourceRef": trigger_source_ref,
                "triggerScope": farm_scope_ref or "tenant",
                "evaluatedMaterializationKeyRef": key_id,
                "dependencyIndexEvidenceRefs": source_refs[:20],
                "statusBefore": "FRESH",
                "statusAfter": "STALE",
                "reasonCode": reason_code,
                "policyRef": MATERIALIZATION_POLICY_REF,
                "decisionTime": now_iso(),
                "evaluatorRuntimeVersion": RUNTIME_VERSION,
                "fanout": {
                    "keysConsidered": considered,
                    "markedStale": len(changed),
                    "markedInvalid": 0,
                    "markedRecomputeRequired": 0,
                    "unaffected": max(considered - len(changed), 0),
                    "maximumScopeExpansion": broadened,
                },
                "redaction": {"redactionApplied": False, "redactionDisclosed": True},
                "redactionDoesNotUpgradeFreshness": True,
            }
            self.store.insert_runtime_trace(cur, trace)
        return marked

    # -------------------------------------------------------- resolve for use --

    def resolve_for_use(self, cur, farm_ref: str, *, twin: str = "COMPLIANCE",
                        use_class: str = "OPERATIONAL_DASHBOARD",
                        time_policy: dict | None = None,
                        required_freshness: str = "REQUIRE_FRESH",
                        high_consequence: bool = False,
                        recompute_if_needed: bool = True) -> dict:
        """Current-state use evaluation: reuse, recompute, or refuse — never
        silently serve stale state for high-consequence use (RFC §8)."""
        time_policy = time_policy or {"policyType": "NOW"}
        request_id = _mint("matreq")
        request = {
            "schemaVersion": "ofarm.materializationrequest.v0.1",
            "requestId": request_id,
            "requestedAt": now_iso(),
            "operation": "RESOLVE_FOR_USE",
            "targetTwin": twin,
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
            "evaluationTimePolicy": time_policy,
            "useClass": _USE_CLASS_MAP.get(use_class, "EXPLORATORY"),
            "requiredFreshness": required_freshness,
            "highConsequenceUse": high_consequence,
        }
        self.store.insert_record(cur, request)

        ctx = self.context.assemble(cur, farm_ref, target_twin=twin,
                                    evaluation_time_policy=time_policy)
        key = self.build_key(farm_ref, twin=twin, use_class=use_class,
                             time_policy=time_policy,
                             context_snapshot_ref=ctx["contextSnapshotId"])
        cur.execute(
            "SELECT * FROM derived_materialization "
            "WHERE key_digest = %s AND superseded_by IS NULL "
            "ORDER BY generated_at DESC LIMIT 1", (key["materializationKeyId"],))
        live = cur.fetchone()

        # Freshness is purpose-sensitive (Current-State RFC §6.4): the three
        # requirement modes are distinct semantics, not synonyms for FRESH.
        # High-consequence use always escalates to REQUIRE_FRESH (§8/§9).
        effective_requirement = ("REQUIRE_FRESH" if high_consequence
                                 else required_freshness)

        def requirement_satisfied(freshness_state: str) -> bool:
            # INVALID never satisfies any requirement (the contract forbids
            # ALLOW_REUSE/satisfied on an INVALID state — allOf 2)
            if effective_requirement in ("NO_CURRENT_STATE_DEPENDENCY",
                                         "ALLOW_STALE_EXPLORATORY"):
                return freshness_state in ("FRESH", "STALE")
            return freshness_state == "FRESH"

        recomputed = False
        problems = []
        if live and requirement_satisfied(live["freshness"]):
            decision, mat = "ALLOW_REUSE", live
        elif recompute_if_needed:
            # STALE/INVALID/absent → recompute (allowed path; refusal and review
            # are the alternatives when recomputation is not permitted)
            result = self.recompute(cur, farm_ref, twin=twin, use_class=use_class,
                                    time_policy=time_policy)
            recomputed = True
            decision = "RECOMPUTE_REQUIRED"
            cur.execute("SELECT * FROM derived_materialization WHERE materialization_id = %s",
                        (result["materializationId"],))
            mat = cur.fetchone()
        else:
            from .problems import runtime_problem
            decision, mat = "REFUSE_USE", live
            problems.append(runtime_problem(
                "MATERIALIZATION_STALE" if live else "MATERIALIZATION_BASIS_MISSING",
                "Current state not demonstrably FRESH",
                "the materialization is not demonstrably FRESH for this use and "
                "recomputation was not permitted; refusing rather than pretending "
                "(Kernel rule 7)"))

        freshness = mat["freshness"] if mat else "INVALID"
        satisfied = mat is not None and requirement_satisfied(freshness)
        result_payload = {
            "schemaVersion": "ofarm.materializationresult.v0.1",
            "resultId": _mint("matres"),
            "requestId": request_id,
            "evaluatedAt": now_iso(),
            "decisionOutcome": decision,
            "targetTwin": twin,
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
            "requiredFreshness": required_freshness,
            "highConsequenceUse": high_consequence,
            "freshnessState": freshness,
            # computed from (requirement, useClass escalation, freshness) —
            # never the constant freshness == FRESH (RFC §6.4); the contract
            # forbids satisfied=true when freshnessState is INVALID, which
            # requirement_satisfied honors (INVALID never satisfies)
            "satisfiedFreshnessRequirement": satisfied and freshness != "INVALID",
            "materializationBasisRef": mat["basis_record_id"] if mat else "basis:none",
            "materializationSnapshotRef": mat["snapshot_record_id"] if mat else "snapshot:none",
            "contextSnapshotRef": ctx["contextSnapshotId"],
            # honest trigger reporting: absence of any materialization is not a
            # truth-basis trigger (the MATERIALIZATION_BASIS_MISSING problem
            # explains it); TRUTH_BASIS is the only trigger family the M1
            # wiring can actually fire (basis-advance via the commit gate)
            "invalidationTriggerFamilies": (
                [] if freshness == "FRESH" or mat is None else ["TRUTH_BASIS"]),
            "problems": problems,
            # the reason never overstates freshness: a stale reuse says so
            "reasonSummary": (
                ("reused FRESH materialization" if freshness == "FRESH" else
                 f"reused STALE materialization under {effective_requirement}; "
                 "high-consequence use barred") if decision == "ALLOW_REUSE"
                else "recomputed for this use" if recomputed
                else "refused: not demonstrably FRESH"),
        }
        self.store.insert_record(cur, result_payload)
        return {
            "decision": decision,
            "freshness": freshness,
            "materialization": dict(mat) if mat else None,
            "materializationResult": result_payload,
            "contextSnapshotRef": ctx["contextSnapshotId"],
            "recomputed": recomputed,
            "problems": problems,
        }
