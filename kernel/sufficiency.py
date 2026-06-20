"""EvidenceSufficiencyCase builders — auto-generated from the SI policy
template (policy:si.ffs.evidence-review.v0_1), never hand-authored
(CAPTURE_MAPPING). The runtime generates cases at three points: claim
promotion, DocumentAssembly freeze, and queue acceptance (whose case
evaluates the resolution of the original route-to-review reasons —
PROFILE.md names the first two; the third is the acceptance leg of the
first, demanded by the formal hostile re-review).
"""
from __future__ import annotations

from . import config, policy, profile_policy
from .context import mint as _mint, now_iso
from .problems import runtime_problem


BINDING_KIND = "ofarm.agronomicidentitybinding.v0.1"


def durable_evidence(store, refs: list[str]) -> list[str]:
    """Refs that resolve to actual EvidenceRecords — the durable proof
    bundle. A ref to some other record is not evidence of execution."""
    out = []
    for ref in refs or []:
        rec = store.get_record(ref)
        if rec and rec["record_kind"] == "ofarm.evidencerecord.v0.1":
            out.append(ref)
    return out


def resolved_bindings(store, refs: list[str]) -> list[dict]:
    """Payloads of refs that resolve to actual AgronomicIdentityBinding
    records. A ref to any other kind is NOT a binding (wrong-kind refs are
    refused at validation); kind-filtering here keeps every downstream
    b['bindingRole'] dereference crash-free — a malformed ref refuses, it
    never raises a bare KeyError past the gate (Kernel rule 7)."""
    out = []
    for ref in refs or []:
        row = store.get_record(ref)
        if row and row["record_kind"] == BINDING_KIND:
            out.append(row["payload"])
    return out


def recover_compliance_claim(store, assertion_id: str) -> dict | None:
    """The structured claim captured verbatim with the original event, as a
    durable ComplianceClaim record reached via the COMPLIANCE_CLAIM edge
    (steward review of PR #4 finding 3 — references are edges, never a
    string-prefix parse of narrative notes)."""
    for edge in store.edges_from(assertion_id, "EVENT_SOURCE"):
        for claim_edge in store.edges_from(edge["dst_record_id"],
                                           "COMPLIANCE_CLAIM"):
            payload = store.get_payload(claim_edge["dst_record_id"])
            if payload and payload.get(
                    "schemaVersion") == "ofarm.complianceclaim.v0.1":
                return payload
    return None


def route_reasons_for(store, assertion_ref: str) -> list[dict]:
    """The recorded problems of the original commit that queued this
    assertion — what a review act must actually resolve."""
    for row in store.find_by_kind("ofarm.commitingressresult.v0.1"):
        p = row["payload"]
        if (p.get("idempotencyDisposition") == "NEW_REQUEST"
                and assertion_ref in p.get("emittedAssertionRecordRefs", [])):
            return [pr for pr in p.get("problems", [])
                    if pr.get("severity") in ("WARNING", "ERROR")]
    return []


def build_case_from_checks(store, farm_ref, assertion_id, erp_id,
                           checks, hard, soft, evidence_refs, *,
                           claim_statement: str | None = None) -> tuple[dict, list[dict]]:
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
    durable = durable_evidence(store, evidence_refs)
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
            "statement": claim_statement or
                "this operation claim meets the SI record-keeping evidence floor",
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


def build_floor_case(store, sub, commit_class, farm_ref, assertion_id,
                     erp_id) -> tuple[dict, list[dict]]:
    """Floor case for an OPERATION_CLAIM or COMPLIANCE_ASSERTION commit."""
    payload = sub.get("payload") or {}

    if commit_class == "COMPLIANCE_ASSERTION":
        # the case evaluates the ACTUAL structured claim and provenance,
        # not mere presence of a durable evidence record
        claim = payload.get("complianceClaim") or {}
        evidence_refs = sub.get("evidenceRefs", [])
        recognized = {config.EVIDENCE_POLICY_REF, config.PROFILE_REF,
                      config.PACK_REF, config.CODE_BINDING_PROFILE_REF}
        checks = {
            "claim-statement": bool(isinstance(claim.get("statement"), str)
                                    and claim.get("statement", "").strip()),
            "asserted-status": claim.get("assertedStatus")
                               in policy.COMPLIANCE_ASSERTED_STATUSES,
            "governing-rules": bool(claim.get("governingRuleRefs")) and all(
                r in recognized or store.record_exists(r)
                for r in claim.get("governingRuleRefs", [])),
            "subject-resolves": bool(claim.get("subjectScopeRef"))
                and store.record_exists(claim.get("subjectScopeRef", "")),
            "evidence-bundle": bool(durable_evidence(store, evidence_refs)),
        }
        return build_case_from_checks(
            store, farm_ref, assertion_id, erp_id, checks, tuple(checks),
            (), evidence_refs,
            claim_statement=claim.get("statement")
            or "compliance assertion (no statement supplied)")

    # OPERATION_CLAIM: the SI floor (policy.OPERATION_FLOOR_*)
    bindings = resolved_bindings(store, payload.get("agronomicIdentityBindingRefs", []))
    checks = {
        "product-binding": any(
            b.get("bindingRole") == "CROP_PROTECTION_PRODUCT"
            and b.get("bindingState") == "VERIFIED"
            and b.get("referenceSnapshotRefs") for b in bindings),
        "dose-unit": any(
            p["parameterRole"] in ("DOSE", "RATE")
            and policy.is_resolved_ucum_unit(p.get("unitRef"))
            for p in payload.get("actualQuantityParameters", [])),
        "parcel": payload.get("executionExtent", {}).get("targetScope", {})
                        .get("scopeType") in ("FIELD", "ZONE"),
        "crop-binding": any(b.get("bindingRole") == "CROP_SPECIES" for b in bindings),
        "operator": bool(payload.get("actor", {}).get("actorPartyRef")),
        "event-time": bool(payload.get("effectiveTimeInterval", {}).get("start")),
    }
    evidence_refs = payload.get("evidenceRefs", []) or sub.get("evidenceRefs", [])
    # the hard/soft floor COMPOSITION is package content (P5): read it from the
    # active profile, never a kernel constant. A missing/malformed policy raises
    # ProfilePolicyError -> the gate fails closed with a governed RuntimeProblem.
    hard, soft = profile_policy.operation_floor()
    return build_case_from_checks(
        store, farm_ref, assertion_id, erp_id, checks, hard, soft, evidence_refs)


def operation_advisories(store, sub) -> list[dict]:
    """Non-blocking advisory-twin warnings for an OPERATION_CLAIM (M2 P5),
    computed from the active profile's advisory rules (policy:si.ffs.evidence-
    review.v0_1 'advisories'): authorisation-mismatch (a resolved product binding
    that maps non-EXACTly) and dose-range (a DOSE/RATE value outside the advisory
    plausibility range). These are surfaced as WARNING-severity problems on the
    commit result — visible, NEVER blocking, never routed to review, never a
    compliance fact and never an accepted consequence (PROFILE.md 'Advisory rule';
    Kernel rule 4). Reason codes reuse the closest registry family pending a
    dedicated advisory family (ERRATA E-006); the advisory posture is in the title
    and detail. Returns [] on a malformed policy (the floor path fails closed)."""
    try:
        rules = profile_policy.advisory_rules()
    except profile_policy.ProfilePolicyError:
        return []
    payload = sub.get("payload") or {}
    out: list[dict] = []

    auth = rules.get("authorisationMismatch", {})
    if auth.get("enabled") and auth.get("exactMappingRequired"):
        for b in resolved_bindings(store, payload.get("agronomicIdentityBindingRefs", [])):
            mapping = b.get("bindingValue", {}).get("mappingRelation")
            # only a RESOLVED (VERIFIED) product binding that maps non-EXACTly: an
            # unresolved/unverified binding is already a soft-floor route to the
            # advisor (sufficiency floor), so it needs no separate advisory here
            if (b.get("bindingRole") == "CROP_PROTECTION_PRODUCT"
                    and b.get("bindingState") == "VERIFIED"
                    and b.get("referenceSnapshotRefs")
                    and mapping not in (None, "EXACT")):
                bid = b.get("agronomicIdentityBindingId", "?")
                out.append(runtime_problem(
                    "PRODUCT_BINDING_UNRESOLVED", "Authorisation-mismatch advisory",
                    f"ADVISORY (non-blocking): product binding {bid} resolves with a non-exact "
                    f"mapping ({mapping}); the recorded product may not exactly "
                    "match the authorised product. The operation outcome is UNCHANGED; this is "
                    "advisory-twin material, not a compliance fact and not legal advice (no "
                    "advisory reason-code family exists — ERRATA E-006).",
                    severity="WARNING",
                    related_refs=[r for r in [bid, *(b.get("referenceSnapshotRefs") or [])]
                                  if r and r != "?"],
                    problem_id="problem:advisory-authorisation-mismatch"))

    dose = rules.get("doseRange", {})
    if dose.get("enabled"):
        lo, hi = dose.get("min"), dose.get("max")
        for p in payload.get("actualQuantityParameters", []):
            if p.get("parameterRole") not in ("DOSE", "RATE"):
                continue
            v = p.get("value")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                out.append(runtime_problem(
                    "EVIDENCE_INSUFFICIENT", "Dose-range advisory",
                    f"ADVISORY (non-blocking): dose {v} {p.get('unitRef', '')} is outside the "
                    f"advisory plausibility range [{lo}, {hi}]. The operation outcome is "
                    "UNCHANGED; this is advisory-twin material, not a compliance fact and not "
                    "legal advice (implausible-value advisory; no dedicated dose-range code — "
                    "ERRATA E-006, same gap class as E-001).",
                    severity="WARNING",
                    problem_id="problem:advisory-dose-range"))
    return out


def build_acceptance_case(store, sub, farm_ref, target) -> dict:
    """Case for a queue acceptance: evaluates the TARGET assertion's durable
    evidence (and, for compliance claims, the claim captured with its event)
    AND the resolution of the original route-to-review reasons — acceptance
    is a governed resolution, never a thin 'approve anyway'."""
    target_id = target["assertionRecordId"]
    evidence_refs = target.get("evidenceRefs", [])
    checks = {"durable-evidence": bool(durable_evidence(store, evidence_refs))}
    route_reasons = route_reasons_for(store, target_id)
    needs_new_evidence = [r for r in route_reasons
                          if r.get("reasonCode") in policy.NEEDS_EVIDENCE_CODES]
    review_evidence = durable_evidence(store, sub.get("reviewEvidenceRefs") or [])
    # routed insufficiencies are resolved by NEW reviewer-attached durable
    # evidence; the distinct review act itself resolves only the routing
    # reasons that demanded a distinct human
    checks["route-reasons-resolved"] = (not needs_new_evidence
                                        or bool(review_evidence))
    claim_statement = None
    if target["assertionType"] == "COMPLIANCE_ASSERTION":
        claim = recover_compliance_claim(store, target_id)
        checks["claim-recoverable"] = claim is not None
        checks["claim-statement"] = bool(
            claim and isinstance(claim.get("statement"), str)
            and claim["statement"].strip())
        checks["asserted-status"] = bool(claim) and claim.get("assertedStatus") \
            in policy.COMPLIANCE_ASSERTED_STATUSES
        claim_statement = (claim or {}).get("statement")
    erp_ref = (target.get("executionRecordPayloadRefs") or [None])[0]
    case, _ = build_case_from_checks(
        store, farm_ref, target_id, erp_ref, checks, tuple(checks), (),
        evidence_refs, claim_statement=claim_statement)
    return case


def amend_case_for_routing(case: dict, route_reasons: list[dict]) -> dict:
    """The stored case must explain the review routing coherently — never
    assert 'all floor items satisfied' while routing to the queue."""
    case["outcome"] = {
        "decision": "REQUIRE_REVIEW",
        "rationale": "routed to the advisor queue: " + "; ".join(
            p["title"] for p in route_reasons),
        "attestationAllowed": False,
        "insufficiencyReasonCodes": sorted({
            policy.ROUTE_REASON_TO_INSUFFICIENCY.get(
                p["reasonCode"], policy.ROUTE_REASON_INSUFFICIENCY_DEFAULT)
            for p in route_reasons}),
    }
    case["evidenceBundles"][0]["bundleStatus"] = "PARTIAL"
    return case
