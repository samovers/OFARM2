"""Authority gate: default deny, explicit grants, revocation re-check.

Kernel rule 2: no valid path through role, grant, scope, time, delegation,
and revocation state means DENY — recorded as an AuthorizationDecisionTrace.
Every allow/deny emits AuthorizationDecisionRequest/Result/Trace records.

Revocation is prospective and erases nothing: revoked grants stay in the
store; the evaluator simply stops finding a valid path through them.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .context import now_iso
from .problems import runtime_problem

# Scope types a FARM-scoped grant covers under DESCENDANT_SCOPES
_FARM_DESCENDANTS = {"FARM", "SITE", "FIELD", "ZONE", "CROP_CYCLE", "LOT", "FACILITY", "OPERATION"}


@dataclass
class AuthorityDecision:
    outcome: str                     # ALLOW | DENY | REQUIRE_REVIEW | REQUIRE_HUMAN_APPROVAL
    request_payload: dict
    result_payload: dict
    trace_payload: dict
    problems: list[dict] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.outcome == "ALLOW"


def _mint(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex[:16]}"


def _parse_dt(value: str) -> datetime | None:
    """Timezone-aware parse; returns None (never a guess) on bad input."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _time_valid(grant: dict, at: str) -> bool:
    """Fail closed: an unparseable validity bound never widens authority
    (lexicographic string comparison is fail-open across timezone formats)."""
    now = _parse_dt(at)
    if now is None:
        return False
    if grant.get("validFrom"):
        start = _parse_dt(grant["validFrom"])
        if start is None or now < start:
            return False
    if grant.get("validUntil"):
        end = _parse_dt(grant["validUntil"])
        if end is None or now >= end:
            return False
    return True


def _revocation_effective(revocation: dict, at: str) -> bool:
    """Fail closed: an unparseable effectiveFrom counts as effective."""
    now = _parse_dt(at)
    eff = _parse_dt(revocation.get("effectiveFrom", ""))
    if now is None or eff is None:
        return True
    return eff <= now


class AuthorityEvaluator:
    def __init__(self, store):
        self.store = store

    # -- record gathering (all reads; default deny means absence = DENY) ------

    def _role_assignments(self, party_ref: str, at: str) -> list[dict]:
        return [
            r["payload"] for r in self.store.find_by_kind("ofarm.roleassignment.v0.1")
            if r["payload"]["partyRef"] == party_ref and _time_valid(r["payload"], at)
        ]

    def _revocations_for(self, artifact_ref: str, at: str) -> list[dict]:
        return [
            r["payload"] for r in self.store.find_by_kind("ofarm.revocationdecision.v0.1")
            if r["payload"]["revokesArtifactRef"] == artifact_ref
            and _revocation_effective(r["payload"], at)
        ]

    def _scope_covers(self, grant_scope: dict, inheritance_mode: str, target: dict) -> bool:
        if grant_scope == target:
            return True
        if inheritance_mode in ("DESCENDANT_SCOPES", "DERIVED_LINEAGE_SCOPES"):
            if grant_scope["scopeType"] == "TENANT":
                return True
            if grant_scope["scopeType"] == "FARM" and target["scopeType"] in _FARM_DESCENDANTS:
                if target["scopeType"] == "FARM":
                    return target["scopeRef"] == grant_scope["scopeRef"]
                # descendant containment is real, not assumed: the target
                # identity must be anchored on the granting farm
                identity = self.store.get_payload(target["scopeRef"])
                if identity is None:
                    return False
                return {"scopeType": "FARM", "scopeRef": grant_scope["scopeRef"]} \
                    in identity.get("anchorScopes", [])
        return False

    def _matching_grants(self, party_ref: str, action_class: str, scope: dict, at: str):
        """(grant, revocations) pairs for direct AuthorityGrants."""
        roles = {r["roleAssignmentId"] for r in self._role_assignments(party_ref, at)}
        out = []
        for row in self.store.find_by_kind("ofarm.authoritygrant.v0.1"):
            g = row["payload"]
            target = g["grantTarget"]
            targets_party = target["targetKind"] == "PARTY" and target["targetRef"] == party_ref
            targets_role = target["targetKind"] == "ROLE_ASSIGNMENT" and target["targetRef"] in roles
            if not (targets_party or targets_role):
                continue
            if g["grantState"] != "ACTIVE" or not _time_valid(g, at):
                continue
            if action_class not in g["authorityActionClasses"]:
                continue
            if not self._scope_covers(g["targetScope"], g["inheritanceMode"], scope):
                continue
            out.append((g, self._revocations_for(g["authorityGrantId"], at)))
        return out

    def _live_source_authority(self, delegation: dict, action_class: str,
                               scope: dict, at: str) -> tuple[bool, list[dict]]:
        """A delegation is only as alive as the authority it was derived from:
        the delegator must STILL hold a live, unrevoked source grant covering
        the delegated action and scope — delegation may not outlive or exceed
        its source (authority law; hostile review blocker 3). Fail closed:
        a delegation with no provable source path grants nothing.

        Returns (live, source_revocations_found)."""
        source_refs = delegation.get("sourceAuthorityGrantRefs") or []
        if not source_refs:
            return False, []
        delegator = delegation["delegatingPartyRef"]
        source_revocations: list[dict] = []
        for ref in source_refs:
            row = self.store.get_record(ref)
            if row is None or row["record_kind"] != "ofarm.authoritygrant.v0.1":
                continue
            g = row["payload"]
            target = g["grantTarget"]
            delegator_roles = {r["roleAssignmentId"]
                               for r in self._role_assignments(delegator, at)}
            controls = ((target["targetKind"] == "PARTY"
                         and target["targetRef"] == delegator)
                        or (target["targetKind"] == "ROLE_ASSIGNMENT"
                            and target["targetRef"] in delegator_roles))
            if not controls:
                continue
            if g["grantState"] != "ACTIVE" or not _time_valid(g, at):
                continue
            if action_class not in g["authorityActionClasses"]:
                continue
            # no widening: the source must cover both the delegation's own
            # scope and the scope being requested right now
            if not self._scope_covers(g["targetScope"], g["inheritanceMode"],
                                      delegation["targetScope"]):
                continue
            if not self._scope_covers(g["targetScope"], g["inheritanceMode"], scope):
                continue
            revs = self._revocations_for(g["authorityGrantId"], at)
            if revs:
                source_revocations.extend(revs)
                continue
            return True, []
        return False, source_revocations

    def _matching_delegations(self, party_ref: str, action_class: str, scope: dict, at: str):
        out = []
        for row in self.store.find_by_kind("ofarm.delegationgrant.v0.1"):
            d = row["payload"]
            if d["delegatePartyRef"] != party_ref:
                continue
            if d["delegationState"] != "ACTIVE" or not _time_valid(d, at):
                continue
            if action_class not in d["authorityActionClasses"]:
                continue
            if not self._scope_covers(d["targetScope"], d["inheritanceMode"], scope):
                continue
            revocations = self._revocations_for(d["delegationGrantId"], at)
            source_live, source_revocations = self._live_source_authority(
                d, action_class, scope, at)
            if not source_live:
                if source_revocations:
                    # the delegation chain is broken by a revoked source —
                    # surfaces as ACTIVE_REVOCATION_FOUND, never silence
                    revocations = revocations + source_revocations
                else:
                    # no provable source path at all: the delegation is not
                    # a candidate (default deny), not a revocation case
                    continue
            out.append((d, revocations))
        return out

    def _party(self, party_ref: str) -> dict | None:
        return self.store.get_payload(party_ref)

    # -- the decision -----------------------------------------------------------

    def evaluate(
        self,
        *,
        acting_party_ref: str,
        action_class: str,
        action_stage: str,
        scope: dict,
        acting_agent_ref: str | None = None,
        ai_assistance: dict | None = None,
        revocation_check_required: bool = True,
        revocation_disposition: str = "DENY",   # DENY | REQUIRE_REVIEW (both lawful per schema)
        use_purpose: str | None = None,
    ) -> AuthorityDecision:
        at = now_iso()
        request_id = _mint("authzreq")
        trace_id = _mint("authztrace")
        result_id = _mint("authzres")
        problems: list[dict] = []

        request = {
            "schemaVersion": "ofarm.authorizationdecisionrequest.v0.1",
            "requestId": request_id,
            "requestedAt": at,
            "actionClass": action_class,
            "actionStage": action_stage,
            "actingPartyRef": acting_party_ref,
            "target": {"scope": scope, "targetTime": at},
            "revocationCheckRequired": revocation_check_required,
            "nonHumanActor": False,
        }
        if acting_agent_ref:
            request["actingAgentRef"] = acting_agent_ref
        if ai_assistance:
            request["aiAssistance"] = ai_assistance
        if use_purpose:
            request["usePurpose"] = use_purpose

        party = self._party(acting_party_ref)
        non_human = bool(acting_agent_ref) or (
            party is not None and party.get("partyClass") == "SOFTWARE_AGENT"
        )
        request["nonHumanActor"] = non_human

        role_basis = [r["roleAssignmentId"] for r in self._role_assignments(acting_party_ref, at)]
        grants = self._matching_grants(acting_party_ref, action_class, scope, at)
        delegations = self._matching_delegations(acting_party_ref, action_class, scope, at)

        live_grants = [g for g, rev in grants if not rev]
        live_delegations = [d for d, rev in delegations if not rev]
        revoked_grants = [(g, rev) for g, rev in grants if rev]
        revoked_delegations = [(d, rev) for d, rev in delegations if rev]
        revocation_refs = [
            r["revocationDecisionId"]
            for _, revs in revoked_grants + revoked_delegations for r in revs
        ]

        inheritance = "EXACT_ONLY"
        for g in live_grants + live_delegations:
            inheritance = g["inheritanceMode"]
            break

        # ---- outcome ladder (default deny) ----
        # Revoked-only basis dominates everything below it: human approval
        # cannot resurrect revoked authority, and the contract forbids
        # ACTIVE_REVOCATION_FOUND with any outcome other than DENY or
        # REQUIRE_REVIEW (AuthorizationDecisionResult allOf 4).
        revoked_only = (revoked_grants or revoked_delegations) and not (
            live_grants or live_delegations)
        if party is None:
            outcome = "DENY"
            revocation_result = "NONE_APPLICABLE"
            reason = f"acting party {acting_party_ref} is not a recorded Party"
            problems.append(runtime_problem(
                "ACTOR_BINDING_UNRESOLVED", "Unknown acting party", reason))
        elif party.get("partyState") != "ACTIVE":
            # party lifecycle fails closed: an INACTIVE party with otherwise
            # live grants still acts as nobody (hostile review finding 7)
            outcome = "DENY"
            revocation_result = "NONE_APPLICABLE"
            reason = (f"acting party {acting_party_ref} is "
                      f"{party.get('partyState')}, not ACTIVE — no authority path "
                      "is evaluated for a non-active party")
            problems.append(runtime_problem(
                "AUTHORITY_DENIED", "Party not active", reason))
        elif revoked_only:
            outcome = revocation_disposition  # DENY or REQUIRE_REVIEW (schema allOf 4)
            revocation_result = "ACTIVE_REVOCATION_FOUND"
            reason = "the only matching authority basis is revoked; revocation re-check failed"
            problems.append(runtime_problem(
                "DELEGATION_REVOKED" if revoked_delegations else "AUTHORITY_DENIED",
                "Authority basis revoked",
                reason, related_refs=revocation_refs or None,
                suggested_remediation="the record routes to review; it is never silently accepted"))
        elif non_human and action_stage in ("PROMOTION", "PUBLICATION", "ATTESTATION"):
            # AI assistance never substitutes for the accountable human
            # (fixture: ai_assisted_submission_requires_human; software-agent
            # review is Phase 2, unsupported in this deployment).
            outcome = "REQUIRE_HUMAN_APPROVAL"
            revocation_result = "NO_ACTIVE_REVOCATION"
            reason = ("a non-human actor may prepare but not finalize promotion-stage "
                      "actions; explicit human approval is required")
            problems.append(runtime_problem(
                "HUMAN_APPROVAL_REQUIRED", "Human approval required", reason,
                suggested_remediation="route to the accountable human's review queue"))
        elif live_grants or live_delegations:
            outcome = "ALLOW"
            revocation_result = "NO_ACTIVE_REVOCATION"
            reason = "valid authority path found"
        else:
            outcome = "DENY"
            revocation_result = "NONE_APPLICABLE"
            reason = (f"no grant or delegation gives {acting_party_ref} action "
                      f"{action_class} on {scope['scopeType']} {scope['scopeRef']} (default deny)")
            problems.append(runtime_problem(
                "AUTHORITY_DENIED", "No authority path", reason,
                suggested_remediation="request a grant or delegation from the holding farmer"))

        trace = {
            "schemaVersion": "ofarm.authorizationdecisiontrace.v0.1",
            "traceId": trace_id,
            "evaluatedAt": at,
            "actingPartyRef": acting_party_ref,
            "requestedActionClass": action_class,
            "target": {"scope": scope, "targetTime": at},
            "roleBasisUsed": role_basis,
            "grantBasisUsed": [g["authorityGrantId"] for g in live_grants],
            "delegationBasisUsed": [d["delegationGrantId"] for d in live_delegations],
            "sharingBasisUsed": [],
            "revocationResult": revocation_result,
            "inheritanceModeApplied": inheritance,
            "decisionOutcome": outcome,
            "reason": reason,
            "isAIActor": non_human,
        }
        if acting_agent_ref:
            trace["actingAgentRef"] = acting_agent_ref
        if revocation_refs:
            trace["revocationDecisionRefs"] = revocation_refs

        result = {
            "schemaVersion": "ofarm.authorizationdecisionresult.v0.1",
            "resultId": result_id,
            "requestId": request_id,
            "evaluatedAt": at,
            "requestedActionClass": action_class,
            "actionStage": action_stage,
            "decisionOutcome": outcome,
            "revocationResult": revocation_result,
            "inheritanceModeApplied": inheritance,
            "roleBasisUsed": role_basis,
            "grantBasisUsed": [g["authorityGrantId"] for g in live_grants],
            "delegationBasisUsed": [d["delegationGrantId"] for d in live_delegations],
            "sharingBasisUsed": [],
            "authorizationDecisionTraceRef": trace_id,
            "humanApprovalRequired": outcome == "REQUIRE_HUMAN_APPROVAL",
            "finalActionPermitted": outcome == "ALLOW",
            "problems": problems,
            "reasonSummary": reason,
        }
        return AuthorityDecision(outcome, request, result, trace, problems)

    # -- read access (sharing gate; re-evaluated per request — D12) -------------

    def evaluate_read(self, *, requesting_party_ref: str, farm_ref: str,
                      artifact_family: str) -> AuthorityDecision:
        """Read access via ownership, grant, or SharingGrant. Authority and
        sharing are re-evaluated per request at the sharing gate, never via
        materialization staleness (PLATFORM.md invalidation posture)."""
        at = now_iso()
        scope = {"scopeType": "FARM", "scopeRef": farm_ref}
        # RECEIVE_READ_DATA per the accepted Authority Action Matrix
        direct = self.evaluate(
            acting_party_ref=requesting_party_ref,
            action_class="RECEIVE_READ_DATA",
            action_stage="QUERY_READ",
            scope=scope,
        )
        if direct.allowed:
            return direct

        # sharing never resurrects a non-active party: the inactive-party
        # denial applies to SharingGrant reads exactly as to direct grants
        # (hostile review finding 5, second pass)
        party = self._party(requesting_party_ref)
        if party is None or party.get("partyState") != "ACTIVE":
            return direct   # already a fail-closed DENY

        sharing_basis, revocation_refs = [], []
        for row in self.store.find_by_kind("ofarm.sharinggrant.v0.1"):
            g = row["payload"]
            if g["granteePartyRef"] != requesting_party_ref:
                continue
            if g["targetScope"] != scope or g["sharedArtifactFamily"] != artifact_family:
                continue
            if g["sharingState"] != "ACTIVE" or not _time_valid(g, at):
                continue
            revs = self._revocations_for(g["sharingGrantId"], at)
            if revs:
                revocation_refs += [r["revocationDecisionId"] for r in revs]
                continue
            sharing_basis.append(g["sharingGrantId"])

        decision = direct
        if sharing_basis:
            decision.outcome = "ALLOW"
            decision.result_payload.update(
                decisionOutcome="ALLOW", finalActionPermitted=True,
                humanApprovalRequired=False, sharingBasisUsed=sharing_basis,
                problems=[], reasonSummary="read allowed via active SharingGrant",
                revocationResult="NO_ACTIVE_REVOCATION",
            )
            decision.trace_payload.update(
                decisionOutcome="ALLOW", sharingBasisUsed=sharing_basis,
                reason="read allowed via active SharingGrant",
                revocationResult="NO_ACTIVE_REVOCATION",
            )
            decision.problems = []
        elif revocation_refs:
            decision.result_payload.update(
                revocationResult="ACTIVE_REVOCATION_FOUND",
                reasonSummary="sharing grant revoked; access cut on this request",
            )
            decision.trace_payload.update(
                revocationResult="ACTIVE_REVOCATION_FOUND",
                revocationDecisionRefs=revocation_refs,
                reason="sharing grant revoked; access cut on this request",
            )
            decision.problems = [runtime_problem(
                "PERMISSION_REDACTED", "Sharing revoked",
                "the sharing grant backing this read was revoked; revocation cuts "
                "access on the next request, it erases nothing")]
            decision.result_payload["problems"] = decision.problems
        return decision
