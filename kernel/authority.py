"""Authority gate: default deny, explicit grants, revocation re-check.

Kernel rule 2: no valid path through role, grant, scope, time, delegation,
and revocation state means DENY — recorded as an AuthorizationDecisionTrace.
Every allow/deny emits AuthorizationDecisionRequest/Result/Trace records.

Revocation is prospective and erases nothing: revoked grants stay in the
store; the evaluator simply stops finding a valid path through them.
"""
from __future__ import annotations

import types
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .callable_state import capture_callable_state, callable_state_matches
from .context import mint as _mint, now_iso
from .contracts import canonical_json
from .problems import runtime_problem
from .store import Store

_RETAINED_AUTHORITY_STORE_TYPE = Store
_RETAINED_STORE_MARK_TRANSACTION_INTEGRITY_VIOLATION = \
    Store._mark_transaction_integrity_violation
_RETAINED_STORE_MARK_TRANSACTION_INTEGRITY_VIOLATION_CODE = \
    _RETAINED_STORE_MARK_TRANSACTION_INTEGRITY_VIOLATION.__code__
_RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR = \
    Store._require_active_serialized_cursor
_RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR_CODE = \
    _RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR.__code__
_RETAINED_STORE_FIND_BY_KIND = Store.find_by_kind
_RETAINED_STORE_FIND_BY_KIND_CODE = _RETAINED_STORE_FIND_BY_KIND.__code__
_RETAINED_STORE_GET_RECORD = Store.get_record
_RETAINED_STORE_GET_RECORD_CODE = _RETAINED_STORE_GET_RECORD.__code__
_RETAINED_STORE_GET_PAYLOAD = Store.get_payload
_RETAINED_STORE_GET_PAYLOAD_CODE = _RETAINED_STORE_GET_PAYLOAD.__code__
_RETAINED_AUTHORITY_DATETIME = datetime
_RETAINED_AUTHORITY_TIMEZONE = timezone
_RETAINED_AUTHORITY_UTC = timezone.utc
_RETAINED_AUTHORITY_BOOL = bool
_RETAINED_AUTHORITY_DICT = dict
_RETAINED_AUTHORITY_NOW_ISO = now_iso
_RETAINED_AUTHORITY_MINT = _mint
_RETAINED_AUTHORITY_RUNTIME_PROBLEM = runtime_problem
_RETAINED_AUTHORITY_CALLABLE_STATE_MATCHES = callable_state_matches
_RETAINED_AUTHORITY_CALLABLE_STATE_MATCHES_CODE = \
    callable_state_matches.__code__
_RETAINED_AUTHORITY_NOW_ISO_GLOBALS = now_iso.__globals__
_RETAINED_AUTHORITY_NOW_ISO_DATETIME = \
    _RETAINED_AUTHORITY_NOW_ISO_GLOBALS["datetime"]
_RETAINED_AUTHORITY_NOW_ISO_TIMEZONE = \
    _RETAINED_AUTHORITY_NOW_ISO_GLOBALS["timezone"]
_RETAINED_AUTHORITY_RUNTIME_PROBLEM_GLOBALS = runtime_problem.__globals__
_RETAINED_AUTHORITY_PROBLEM_REASON_CODES = \
    _RETAINED_AUTHORITY_RUNTIME_PROBLEM_GLOBALS["REGISTERED_REASON_CODES"]
_RETAINED_AUTHORITY_PROBLEM_COUNTER = \
    _RETAINED_AUTHORITY_RUNTIME_PROBLEM_GLOBALS["_counter"]

# Scope types a FARM-scoped grant covers under DESCENDANT_SCOPES
_FARM_DESCENDANTS = frozenset({
    "FARM", "SITE", "FIELD", "ZONE", "CROP_CYCLE", "LOT", "FACILITY",
    "OPERATION",
})
_RETAINED_AUTHORITY_FARM_DESCENDANTS = _FARM_DESCENDANTS

_ACTION_STAGE_VALUES = (
    "DRAFT_PREPARATION",
    "PROMOTION",
    "PUBLICATION",
    "ATTESTATION",
    "QUERY_READ",
    "CURRENT_STATE_USE",
    "CONTEXT_ACTIVATION",
)
_REVOCATION_DISPOSITION_VALUES = ("DENY", "REQUIRE_REVIEW")
_SCOPE_TYPE_VALUES = (
    "FARM",
    "SITE",
    "FIELD",
    "ZONE",
    "CROP_CYCLE",
    "LOT",
    "FACILITY",
    "OPERATION",
    "DEPLOYMENT",
    "TENANT",
)
_AI_ASSISTANT_ROLE_VALUES = (
    "INTERPRETATION_AI",
    "QUERY_AI",
    "AUTHORING_AI",
    "ADVISORY_AI",
    "SIMULATION_AI",
)
_AI_SUGGESTION_MODE_VALUES = (
    "PREPARE",
    "RECOMMEND",
    "AUTO_FILL",
    "AUTO_ROUTE",
)
_RETAINED_ACTION_STAGE_VALUES = _ACTION_STAGE_VALUES
_RETAINED_REVOCATION_DISPOSITION_VALUES = _REVOCATION_DISPOSITION_VALUES
_RETAINED_SCOPE_TYPE_VALUES = _SCOPE_TYPE_VALUES
_RETAINED_AI_ASSISTANT_ROLE_VALUES = _AI_ASSISTANT_ROLE_VALUES
_RETAINED_AI_SUGGESTION_MODE_VALUES = _AI_SUGGESTION_MODE_VALUES
_RETAINED_AUTHORITY_CANONICAL_JSON = canonical_json
_RETAINED_AUTHORITY_CANONICAL_JSON_CODE = canonical_json.__code__


def _canonical_authority_decision_state(
        outcome, request, result, trace, problems) -> str:
    return _RETAINED_AUTHORITY_CANONICAL_JSON({
        "outcome": outcome,
        "request": request,
        "result": result,
        "trace": trace,
        "problems": problems,
    })


_RETAINED_CANONICAL_AUTHORITY_DECISION_STATE = \
    _canonical_authority_decision_state
_RETAINED_CANONICAL_AUTHORITY_DECISION_STATE_CODE = \
    _canonical_authority_decision_state.__code__


class _ImmutableAuthorityDecisionType(type):
    """Block ordinary mutation of the decision class after construction."""

    def __setattr__(cls, name, value):
        if cls.__dict__.get("_authority_type_frozen", False):
            raise TypeError("AuthorityDecision runtime type is immutable")
        super().__setattr__(name, value)

    def __delattr__(cls, name):
        if cls.__dict__.get("_authority_type_frozen", False):
            raise TypeError("AuthorityDecision runtime type is immutable")
        super().__delattr__(name)


@dataclass(frozen=True, slots=True)
class AuthorityDecision(metaclass=_ImmutableAuthorityDecisionType):
    _authority_type_frozen = False

    outcome: str                     # ALLOW | DENY | REQUIRE_REVIEW | REQUIRE_HUMAN_APPROVAL
    request_payload: dict
    result_payload: dict
    trace_payload: dict
    problems: list[dict] = field(default_factory=list)
    _canonical_state: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_canonical_state",
            _RETAINED_CANONICAL_AUTHORITY_DECISION_STATE(
                object.__getattribute__(self, "outcome"),
                object.__getattribute__(self, "request_payload"),
                object.__getattribute__(self, "result_payload"),
                object.__getattribute__(self, "trace_payload"),
                object.__getattribute__(self, "problems"),
            ),
        )

    @property
    def allowed(self) -> bool:
        return object.__getattribute__(self, "outcome") == "ALLOW"


AuthorityDecision._authority_type_frozen = True

_RETAINED_AUTHORITY_DECISION_TYPE = AuthorityDecision
_RETAINED_AUTHORITY_DECISION_INIT = AuthorityDecision.__init__
_RETAINED_AUTHORITY_DECISION_INIT_CODE = \
    _RETAINED_AUTHORITY_DECISION_INIT.__code__
_RETAINED_AUTHORITY_DECISION_SETATTR = AuthorityDecision.__setattr__
_RETAINED_AUTHORITY_DECISION_SETATTR_CODE = \
    _RETAINED_AUTHORITY_DECISION_SETATTR.__code__
_RETAINED_AUTHORITY_DECISION_DELATTR = AuthorityDecision.__delattr__
_RETAINED_AUTHORITY_DECISION_DELATTR_CODE = \
    _RETAINED_AUTHORITY_DECISION_DELATTR.__code__
_RETAINED_AUTHORITY_DECISION_POST_INIT = AuthorityDecision.__post_init__
_RETAINED_AUTHORITY_DECISION_POST_INIT_CODE = \
    _RETAINED_AUTHORITY_DECISION_POST_INIT.__code__
_RETAINED_AUTHORITY_DECISION_ALLOWED_PROPERTY = \
    vars(AuthorityDecision)["allowed"]
_RETAINED_AUTHORITY_DECISION_ALLOWED_GETTER = \
    _RETAINED_AUTHORITY_DECISION_ALLOWED_PROPERTY.fget
_RETAINED_AUTHORITY_DECISION_ALLOWED_GETTER_CODE = \
    _RETAINED_AUTHORITY_DECISION_ALLOWED_GETTER.__code__
_RETAINED_AUTHORITY_DECISION_SLOT_STATE = tuple(
    (name, vars(AuthorityDecision)[name])
    for name in AuthorityDecision.__slots__
)


def _require_authority_decision_type() -> None:
    allowed = vars(_RETAINED_AUTHORITY_DECISION_TYPE).get("allowed")
    if (globals().get("AuthorityDecision") is not
            _RETAINED_AUTHORITY_DECISION_TYPE
            or type(_RETAINED_AUTHORITY_DECISION_TYPE) is not
            _ImmutableAuthorityDecisionType
            or vars(_RETAINED_AUTHORITY_DECISION_TYPE).get(
                "_authority_type_frozen") is not True
            or vars(_RETAINED_AUTHORITY_DECISION_TYPE).get("__init__") is not
            _RETAINED_AUTHORITY_DECISION_INIT
            or _RETAINED_AUTHORITY_DECISION_INIT.__code__ is not
            _RETAINED_AUTHORITY_DECISION_INIT_CODE
            or vars(_RETAINED_AUTHORITY_DECISION_TYPE).get("__setattr__") is not
            _RETAINED_AUTHORITY_DECISION_SETATTR
            or _RETAINED_AUTHORITY_DECISION_SETATTR.__code__ is not
            _RETAINED_AUTHORITY_DECISION_SETATTR_CODE
            or vars(_RETAINED_AUTHORITY_DECISION_TYPE).get("__delattr__") is not
            _RETAINED_AUTHORITY_DECISION_DELATTR
            or _RETAINED_AUTHORITY_DECISION_DELATTR.__code__ is not
            _RETAINED_AUTHORITY_DECISION_DELATTR_CODE
            or vars(_RETAINED_AUTHORITY_DECISION_TYPE).get("__post_init__") is not
            _RETAINED_AUTHORITY_DECISION_POST_INIT
            or _RETAINED_AUTHORITY_DECISION_POST_INIT.__code__ is not
            _RETAINED_AUTHORITY_DECISION_POST_INIT_CODE
            or allowed is not _RETAINED_AUTHORITY_DECISION_ALLOWED_PROPERTY
            or type(allowed) is not property
            or allowed.fget is not
            _RETAINED_AUTHORITY_DECISION_ALLOWED_GETTER
            or _RETAINED_AUTHORITY_DECISION_ALLOWED_GETTER.__code__ is not
            _RETAINED_AUTHORITY_DECISION_ALLOWED_GETTER_CODE
            or any(
                vars(_RETAINED_AUTHORITY_DECISION_TYPE).get(name) is not slot
                for name, slot in _RETAINED_AUTHORITY_DECISION_SLOT_STATE)):
        raise RuntimeError("AuthorityDecision runtime type changed")


def authority_decision_allowed(decision) -> bool:
    """Validate the exact frozen decision state before branching on it."""
    _RETAINED_REQUIRE_AUTHORITY_DECISION_TYPE()
    if type(decision) is not _RETAINED_AUTHORITY_DECISION_TYPE:
        raise RuntimeError("authority decision has a substituted runtime type")
    outcome = object.__getattribute__(decision, "outcome")
    request = object.__getattribute__(decision, "request_payload")
    result = object.__getattribute__(decision, "result_payload")
    trace = object.__getattribute__(decision, "trace_payload")
    problems = object.__getattribute__(decision, "problems")
    canonical_state = object.__getattribute__(decision, "_canonical_state")
    allowed = _RETAINED_AUTHORITY_DECISION_ALLOWED_GETTER(decision)
    if (type(outcome) is not str
            or outcome not in (
                "ALLOW", "DENY", "REQUIRE_REVIEW",
                "REQUIRE_HUMAN_APPROVAL",
            )
            or type(request) is not _RETAINED_AUTHORITY_DICT
            or type(result) is not _RETAINED_AUTHORITY_DICT
            or type(trace) is not _RETAINED_AUTHORITY_DICT
            or type(problems) is not list
            or type(canonical_state) is not str
            or canonical_state !=
            _RETAINED_CANONICAL_AUTHORITY_DECISION_STATE(
                outcome, request, result, trace, problems)
            or type(allowed) is not _RETAINED_AUTHORITY_BOOL
            or type(result.get("decisionOutcome")) is not str
            or result.get("decisionOutcome") != outcome
            or type(trace.get("decisionOutcome")) is not str
            or trace.get("decisionOutcome") != outcome
            or type(result.get("finalActionPermitted")) is not
            _RETAINED_AUTHORITY_BOOL
            or result.get("finalActionPermitted") is not allowed
            or type(result.get("humanApprovalRequired")) is not
            _RETAINED_AUTHORITY_BOOL
            or result.get("humanApprovalRequired") is not
            (outcome == "REQUIRE_HUMAN_APPROVAL")
            or result.get("problems") is not problems):
        raise RuntimeError("authority decision state changed or is inconsistent")
    return allowed


_RETAINED_AUTHORITY_DECISION_ALLOWED = authority_decision_allowed
_RETAINED_AUTHORITY_DECISION_ALLOWED_CODE = \
    authority_decision_allowed.__code__
_RETAINED_REQUIRE_AUTHORITY_DECISION_TYPE = _require_authority_decision_type
_RETAINED_REQUIRE_AUTHORITY_DECISION_TYPE_CODE = \
    _require_authority_decision_type.__code__


def _copy_evaluate_inputs(
    *,
    acting_party_ref,
    action_class,
    action_stage,
    scope,
    acting_agent_ref,
    ai_assistance,
    revocation_check_required,
    revocation_disposition,
    use_purpose,
):
    """Reject behavioral inputs and return closed exact primitive copies."""
    if (type(acting_party_ref) is not str
            or type(action_class) is not str
            or type(action_stage) is not str
            or type(revocation_check_required) is not _RETAINED_AUTHORITY_BOOL
            or type(revocation_disposition) is not str
            or (acting_agent_ref is not None
                and type(acting_agent_ref) is not str)
            or (use_purpose is not None and type(use_purpose) is not str)):
        raise TypeError(
            "AuthorityEvaluator inputs must use exact primitive types")
    if not acting_party_ref or not action_class:
        raise ValueError("AuthorityEvaluator party and action refs must be non-empty")
    if action_stage not in _RETAINED_ACTION_STAGE_VALUES:
        raise ValueError("AuthorityEvaluator action_stage is not closed")
    if revocation_disposition not in \
            _RETAINED_REVOCATION_DISPOSITION_VALUES:
        raise ValueError(
            "AuthorityEvaluator revocation_disposition is not closed")
    if (type(scope) is not _RETAINED_AUTHORITY_DICT
            or set(scope) != {"scopeType", "scopeRef"}
            or any(type(key) is not str for key in scope)
            or type(scope.get("scopeType")) is not str
            or scope.get("scopeType") not in _RETAINED_SCOPE_TYPE_VALUES
            or type(scope.get("scopeRef")) is not str
            or not scope.get("scopeRef")):
        raise TypeError(
            "AuthorityEvaluator scope must be an exact closed primitive map")
    scope_copy = {
        "scopeType": scope["scopeType"],
        "scopeRef": scope["scopeRef"],
    }

    ai_copy = None
    if ai_assistance is not None:
        allowed_keys = {
            "assisted", "assistantRef", "assistantRoleFamily", "suggestionMode",
        }
        if (type(ai_assistance) is not _RETAINED_AUTHORITY_DICT
                or any(type(key) is not str for key in ai_assistance)
                or not set(ai_assistance) <= allowed_keys
                or "assisted" not in ai_assistance
                or type(ai_assistance.get("assisted")) is not
                _RETAINED_AUTHORITY_BOOL
                or ("assistantRef" in ai_assistance
                    and type(ai_assistance["assistantRef"]) is not str)
                or ("assistantRoleFamily" in ai_assistance
                    and (type(ai_assistance["assistantRoleFamily"]) is not str
                         or ai_assistance["assistantRoleFamily"] not in
                         _RETAINED_AI_ASSISTANT_ROLE_VALUES))
                or ("suggestionMode" in ai_assistance
                    and (type(ai_assistance["suggestionMode"]) is not str
                         or ai_assistance["suggestionMode"] not in
                         _RETAINED_AI_SUGGESTION_MODE_VALUES))):
            raise TypeError(
                "AuthorityEvaluator ai_assistance must be an exact closed map")
        ai_copy = {
            key: ai_assistance[key]
            for key in (
                "assisted", "assistantRef", "assistantRoleFamily",
                "suggestionMode",
            )
            if key in ai_assistance
        }
    return (
        acting_party_ref,
        action_class,
        action_stage,
        scope_copy,
        acting_agent_ref,
        ai_copy,
        revocation_check_required,
        revocation_disposition,
        use_purpose,
    )


_RETAINED_COPY_EVALUATE_INPUTS = _copy_evaluate_inputs
_RETAINED_COPY_EVALUATE_INPUTS_CODE = _copy_evaluate_inputs.__code__


def _parse_dt(value: str) -> datetime | None:
    """Timezone-aware parse; returns None (never a guess) on bad input."""
    try:
        dt = _RETAINED_AUTHORITY_DATETIME.fromisoformat(
            value.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(
        tzinfo=_RETAINED_AUTHORITY_UTC)


_RETAINED_AUTHORITY_PARSE_DT = _parse_dt


def _time_valid(grant: dict, at: str) -> bool:
    """Fail closed: an unparseable validity bound never widens authority
    (lexicographic string comparison is fail-open across timezone formats)."""
    now = _RETAINED_AUTHORITY_PARSE_DT(at)
    if now is None:
        return False
    if grant.get("validFrom"):
        start = _RETAINED_AUTHORITY_PARSE_DT(grant["validFrom"])
        if start is None or now < start:
            return False
    if grant.get("validUntil"):
        end = _RETAINED_AUTHORITY_PARSE_DT(grant["validUntil"])
        if end is None or now >= end:
            return False
    return True


_RETAINED_AUTHORITY_TIME_VALID = _time_valid


def _revocation_effective(revocation: dict, at: str) -> bool:
    """Fail closed: an unparseable effectiveFrom counts as effective."""
    now = _RETAINED_AUTHORITY_PARSE_DT(at)
    eff = _RETAINED_AUTHORITY_PARSE_DT(
        revocation.get("effectiveFrom", ""))
    if now is None or eff is None:
        return True
    return eff <= now


_RETAINED_AUTHORITY_REVOCATION_EFFECTIVE = _revocation_effective


_AUTHORITY_SEMANTIC_FUNCTION_ANCHORS = (
    (("now_iso", "_RETAINED_AUTHORITY_NOW_ISO"),
     _RETAINED_AUTHORITY_NOW_ISO,
     _RETAINED_AUTHORITY_NOW_ISO.__code__,
     capture_callable_state(_RETAINED_AUTHORITY_NOW_ISO)),
    (("_mint", "_RETAINED_AUTHORITY_MINT"),
     _RETAINED_AUTHORITY_MINT,
     _RETAINED_AUTHORITY_MINT.__code__,
     capture_callable_state(_RETAINED_AUTHORITY_MINT)),
    (("runtime_problem", "_RETAINED_AUTHORITY_RUNTIME_PROBLEM"),
     _RETAINED_AUTHORITY_RUNTIME_PROBLEM,
     _RETAINED_AUTHORITY_RUNTIME_PROBLEM.__code__,
     capture_callable_state(_RETAINED_AUTHORITY_RUNTIME_PROBLEM)),
    (("_parse_dt", "_RETAINED_AUTHORITY_PARSE_DT"),
     _RETAINED_AUTHORITY_PARSE_DT,
     _RETAINED_AUTHORITY_PARSE_DT.__code__,
     capture_callable_state(_RETAINED_AUTHORITY_PARSE_DT)),
    (("_time_valid", "_RETAINED_AUTHORITY_TIME_VALID"),
     _RETAINED_AUTHORITY_TIME_VALID,
     _RETAINED_AUTHORITY_TIME_VALID.__code__,
     capture_callable_state(_RETAINED_AUTHORITY_TIME_VALID)),
    (("_revocation_effective",
      "_RETAINED_AUTHORITY_REVOCATION_EFFECTIVE"),
     _RETAINED_AUTHORITY_REVOCATION_EFFECTIVE,
     _RETAINED_AUTHORITY_REVOCATION_EFFECTIVE.__code__,
     capture_callable_state(_RETAINED_AUTHORITY_REVOCATION_EFFECTIVE)),
)
_RETAINED_AUTHORITY_SEMANTIC_FUNCTION_ANCHORS = \
    _AUTHORITY_SEMANTIC_FUNCTION_ANCHORS
_AUTHORITY_SEMANTIC_DATA_ANCHORS = (
    (("_RETAINED_AUTHORITY_BOOL",), _RETAINED_AUTHORITY_BOOL),
    (("_RETAINED_AUTHORITY_DICT",), _RETAINED_AUTHORITY_DICT),
    (("datetime", "_RETAINED_AUTHORITY_DATETIME"),
     _RETAINED_AUTHORITY_DATETIME),
    (("timezone", "_RETAINED_AUTHORITY_TIMEZONE"),
     _RETAINED_AUTHORITY_TIMEZONE),
    (("_RETAINED_AUTHORITY_UTC",), _RETAINED_AUTHORITY_UTC),
    (("_FARM_DESCENDANTS", "_RETAINED_AUTHORITY_FARM_DESCENDANTS"),
     _RETAINED_AUTHORITY_FARM_DESCENDANTS),
)
_RETAINED_AUTHORITY_SEMANTIC_DATA_ANCHORS = \
    _AUTHORITY_SEMANTIC_DATA_ANCHORS
_AUTHORITY_TRANSITIVE_DATA_ANCHORS = (
    (_RETAINED_AUTHORITY_NOW_ISO_GLOBALS, "datetime",
     _RETAINED_AUTHORITY_NOW_ISO_DATETIME),
    (_RETAINED_AUTHORITY_NOW_ISO_GLOBALS, "timezone",
     _RETAINED_AUTHORITY_NOW_ISO_TIMEZONE),
    (_RETAINED_AUTHORITY_RUNTIME_PROBLEM_GLOBALS,
     "REGISTERED_REASON_CODES", _RETAINED_AUTHORITY_PROBLEM_REASON_CODES),
    (_RETAINED_AUTHORITY_RUNTIME_PROBLEM_GLOBALS,
     "_counter", _RETAINED_AUTHORITY_PROBLEM_COUNTER),
)
_RETAINED_AUTHORITY_TRANSITIVE_DATA_ANCHORS = \
    _AUTHORITY_TRANSITIVE_DATA_ANCHORS


class AuthorityEvaluator:
    __slots__ = ("store",)

    def __init__(self, store):
        if type(store) is not _RETAINED_AUTHORITY_STORE_TYPE:
            raise TypeError("AuthorityEvaluator requires the exact Store runtime")
        object.__setattr__(self, "store", store)

    def __setattr__(self, name, value):
        del name, value
        raise AttributeError("AuthorityEvaluator runtime composition is immutable")

    def __delattr__(self, name):
        del name
        raise AttributeError("AuthorityEvaluator runtime composition cannot be deleted")

    # -- record gathering (all reads; default deny means absence = DENY) ------

    def _role_assignments(self, party_ref: str, at: str) -> list[dict]:
        return [
            r["payload"] for r in _RETAINED_STORE_FIND_BY_KIND(
                self.store, "ofarm.roleassignment.v0.1")
            if r["payload"]["partyRef"] == party_ref
            and _RETAINED_AUTHORITY_TIME_VALID(r["payload"], at)
        ]

    def _revocations_for(self, artifact_ref: str, at: str) -> list[dict]:
        return [
            r["payload"] for r in _RETAINED_STORE_FIND_BY_KIND(
                self.store, "ofarm.revocationdecision.v0.1")
            if r["payload"]["revokesArtifactRef"] == artifact_ref
            and _RETAINED_AUTHORITY_REVOCATION_EFFECTIVE(r["payload"], at)
        ]

    def _scope_covers(self, grant_scope: dict, inheritance_mode: str, target: dict) -> bool:
        if grant_scope == target:
            return True
        if inheritance_mode in ("DESCENDANT_SCOPES", "DERIVED_LINEAGE_SCOPES"):
            if grant_scope["scopeType"] == "TENANT":
                return True
            if (grant_scope["scopeType"] == "FARM"
                    and target["scopeType"] in
                    _RETAINED_AUTHORITY_FARM_DESCENDANTS):
                if target["scopeType"] == "FARM":
                    return target["scopeRef"] == grant_scope["scopeRef"]
                # descendant containment is real, not assumed: the target
                # identity must be anchored on the granting farm
                identity = _RETAINED_STORE_GET_PAYLOAD(
                    self.store, target["scopeRef"])
                if identity is None:
                    return False
                return {"scopeType": "FARM", "scopeRef": grant_scope["scopeRef"]} \
                    in identity.get("anchorScopes", [])
        return False

    def _matching_grants(self, party_ref: str, action_class: str, scope: dict, at: str):
        """(grant, revocations) pairs for direct AuthorityGrants."""
        roles = {
            r["roleAssignmentId"]
            for r in _RETAINED_AUTHORITY_ROLE_ASSIGNMENTS(self, party_ref, at)
        }
        out = []
        for row in _RETAINED_STORE_FIND_BY_KIND(
                self.store, "ofarm.authoritygrant.v0.1"):
            g = row["payload"]
            target = g["grantTarget"]
            targets_party = target["targetKind"] == "PARTY" and target["targetRef"] == party_ref
            targets_role = target["targetKind"] == "ROLE_ASSIGNMENT" and target["targetRef"] in roles
            if not (targets_party or targets_role):
                continue
            if (g["grantState"] != "ACTIVE"
                    or not _RETAINED_AUTHORITY_TIME_VALID(g, at)):
                continue
            if action_class not in g["authorityActionClasses"]:
                continue
            if not _RETAINED_AUTHORITY_SCOPE_COVERS(
                    self, g["targetScope"], g["inheritanceMode"], scope):
                continue
            out.append((g, _RETAINED_AUTHORITY_REVOCATIONS_FOR(
                self, g["authorityGrantId"], at)))
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
            row = _RETAINED_STORE_GET_RECORD(self.store, ref)
            if row is None or row["record_kind"] != "ofarm.authoritygrant.v0.1":
                continue
            g = row["payload"]
            target = g["grantTarget"]
            delegator_roles = {
                r["roleAssignmentId"]
                for r in _RETAINED_AUTHORITY_ROLE_ASSIGNMENTS(
                    self, delegator, at)
            }
            controls = ((target["targetKind"] == "PARTY"
                         and target["targetRef"] == delegator)
                        or (target["targetKind"] == "ROLE_ASSIGNMENT"
                            and target["targetRef"] in delegator_roles))
            if not controls:
                continue
            if (g["grantState"] != "ACTIVE"
                    or not _RETAINED_AUTHORITY_TIME_VALID(g, at)):
                continue
            if action_class not in g["authorityActionClasses"]:
                continue
            # no widening: the source must cover both the delegation's own
            # scope and the scope being requested right now
            if not _RETAINED_AUTHORITY_SCOPE_COVERS(
                    self, g["targetScope"], g["inheritanceMode"],
                    delegation["targetScope"]):
                continue
            if not _RETAINED_AUTHORITY_SCOPE_COVERS(
                    self, g["targetScope"], g["inheritanceMode"], scope):
                continue
            revs = _RETAINED_AUTHORITY_REVOCATIONS_FOR(
                self, g["authorityGrantId"], at)
            if revs:
                source_revocations.extend(revs)
                continue
            return True, []
        return False, source_revocations

    def _matching_delegations(self, party_ref: str, action_class: str, scope: dict, at: str):
        out = []
        for row in _RETAINED_STORE_FIND_BY_KIND(
                self.store, "ofarm.delegationgrant.v0.1"):
            d = row["payload"]
            if d["delegatePartyRef"] != party_ref:
                continue
            if (d["delegationState"] != "ACTIVE"
                    or not _RETAINED_AUTHORITY_TIME_VALID(d, at)):
                continue
            if action_class not in d["authorityActionClasses"]:
                continue
            if not _RETAINED_AUTHORITY_SCOPE_COVERS(
                    self, d["targetScope"], d["inheritanceMode"], scope):
                continue
            revocations = _RETAINED_AUTHORITY_REVOCATIONS_FOR(
                self, d["delegationGrantId"], at)
            source_live, source_revocations = \
                _RETAINED_AUTHORITY_LIVE_SOURCE(
                    self, d, action_class, scope, at)
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
        return _RETAINED_STORE_GET_PAYLOAD(self.store, party_ref)

    # -- the decision -----------------------------------------------------------

    def evaluate(
        self,
        *,
        cur,
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
        _RETAINED_AUTHORITY_RUNTIME_GUARD(self, cur)
        (
            acting_party_ref,
            action_class,
            action_stage,
            scope,
            acting_agent_ref,
            ai_assistance,
            revocation_check_required,
            revocation_disposition,
            use_purpose,
        ) = _RETAINED_COPY_EVALUATE_INPUTS(
            acting_party_ref=acting_party_ref,
            action_class=action_class,
            action_stage=action_stage,
            scope=scope,
            acting_agent_ref=acting_agent_ref,
            ai_assistance=ai_assistance,
            revocation_check_required=revocation_check_required,
            revocation_disposition=revocation_disposition,
            use_purpose=use_purpose,
        )
        _RETAINED_AUTHORITY_RUNTIME_GUARD(self, cur)
        at = _RETAINED_AUTHORITY_NOW_ISO()
        request_id = _RETAINED_AUTHORITY_MINT("authzreq")
        trace_id = _RETAINED_AUTHORITY_MINT("authztrace")
        result_id = _RETAINED_AUTHORITY_MINT("authzres")
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

        party = _RETAINED_AUTHORITY_PARTY(self, acting_party_ref)
        non_human = _RETAINED_AUTHORITY_BOOL(acting_agent_ref) or (
            party is not None and party.get("partyClass") == "SOFTWARE_AGENT"
        )
        request["nonHumanActor"] = non_human

        role_basis = [
            r["roleAssignmentId"]
            for r in _RETAINED_AUTHORITY_ROLE_ASSIGNMENTS(
                self, acting_party_ref, at)
        ]
        grants = _RETAINED_AUTHORITY_MATCHING_GRANTS(
            self, acting_party_ref, action_class, scope, at)
        delegations = _RETAINED_AUTHORITY_MATCHING_DELEGATIONS(
            self, acting_party_ref, action_class, scope, at)

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
            problems.append(_RETAINED_AUTHORITY_RUNTIME_PROBLEM(
                "ACTOR_BINDING_UNRESOLVED", "Unknown acting party", reason))
        elif party.get("partyState") != "ACTIVE":
            # party lifecycle fails closed: an INACTIVE party with otherwise
            # live grants still acts as nobody (hostile review finding 7)
            outcome = "DENY"
            revocation_result = "NONE_APPLICABLE"
            reason = (f"acting party {acting_party_ref} is "
                      f"{party.get('partyState')}, not ACTIVE — no authority path "
                      "is evaluated for a non-active party")
            problems.append(_RETAINED_AUTHORITY_RUNTIME_PROBLEM(
                "AUTHORITY_DENIED", "Party not active", reason))
        elif revoked_only:
            outcome = revocation_disposition  # DENY or REQUIRE_REVIEW (schema allOf 4)
            revocation_result = "ACTIVE_REVOCATION_FOUND"
            reason = "the only matching authority basis is revoked; revocation re-check failed"
            problems.append(_RETAINED_AUTHORITY_RUNTIME_PROBLEM(
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
            problems.append(_RETAINED_AUTHORITY_RUNTIME_PROBLEM(
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
            problems.append(_RETAINED_AUTHORITY_RUNTIME_PROBLEM(
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
        decision = _RETAINED_AUTHORITY_DECISION_TYPE(
            outcome, request, result, trace, problems)
        _RETAINED_AUTHORITY_DECISION_ALLOWED(decision)
        _RETAINED_AUTHORITY_RUNTIME_GUARD(self, cur)
        return decision

    # -- read access (sharing gate; re-evaluated per request — D12) -------------

    def evaluate_read(self, *, cur, requesting_party_ref: str, farm_ref: str,
                      artifact_family: str) -> AuthorityDecision:
        """Read access via ownership, grant, or SharingGrant. Authority and
        sharing are re-evaluated per request at the sharing gate, never via
        materialization staleness (PLATFORM.md invalidation posture)."""
        _RETAINED_AUTHORITY_RUNTIME_GUARD(self, cur)
        at = _RETAINED_AUTHORITY_NOW_ISO()
        scope = {"scopeType": "FARM", "scopeRef": farm_ref}
        # RECEIVE_READ_DATA per the accepted Authority Action Matrix
        direct = _RETAINED_AUTHORITY_EVALUATE(
            self,
            cur=cur,
            acting_party_ref=requesting_party_ref,
            action_class="RECEIVE_READ_DATA",
            action_stage="QUERY_READ",
            scope=scope,
        )
        if _RETAINED_AUTHORITY_DECISION_ALLOWED(direct):
            _RETAINED_AUTHORITY_RUNTIME_GUARD(self, cur)
            return direct

        # sharing never resurrects a non-active party: the inactive-party
        # denial applies to SharingGrant reads exactly as to direct grants
        # (hostile review finding 5, second pass)
        party = _RETAINED_AUTHORITY_PARTY(self, requesting_party_ref)
        if party is None or party.get("partyState") != "ACTIVE":
            _RETAINED_AUTHORITY_RUNTIME_GUARD(self, cur)
            return direct   # already a fail-closed DENY

        sharing_basis, revocation_refs = [], []
        for row in _RETAINED_STORE_FIND_BY_KIND(
                self.store, "ofarm.sharinggrant.v0.1"):
            g = row["payload"]
            if g["granteePartyRef"] != requesting_party_ref:
                continue
            if g["targetScope"] != scope or g["sharedArtifactFamily"] != artifact_family:
                continue
            if (g["sharingState"] != "ACTIVE"
                    or not _RETAINED_AUTHORITY_TIME_VALID(g, at)):
                continue
            revs = _RETAINED_AUTHORITY_REVOCATIONS_FOR(
                self, g["sharingGrantId"], at)
            if revs:
                revocation_refs += [r["revocationDecisionId"] for r in revs]
                continue
            sharing_basis.append(g["sharingGrantId"])

        decision = direct
        if sharing_basis:
            problems = []
            result = _RETAINED_AUTHORITY_DICT(direct.result_payload)
            trace = _RETAINED_AUTHORITY_DICT(direct.trace_payload)
            result.update(
                decisionOutcome="ALLOW", finalActionPermitted=True,
                humanApprovalRequired=False, sharingBasisUsed=sharing_basis,
                problems=problems,
                reasonSummary="read allowed via active SharingGrant",
                revocationResult="NO_ACTIVE_REVOCATION",
            )
            trace.update(
                decisionOutcome="ALLOW", sharingBasisUsed=sharing_basis,
                reason="read allowed via active SharingGrant",
                revocationResult="NO_ACTIVE_REVOCATION",
            )
            decision = _RETAINED_AUTHORITY_DECISION_TYPE(
                "ALLOW", direct.request_payload, result, trace, problems)
        elif revocation_refs:
            problems = [_RETAINED_AUTHORITY_RUNTIME_PROBLEM(
                "PERMISSION_REDACTED", "Sharing revoked",
                "the sharing grant backing this read was revoked; revocation "
                "cuts access on the next request, it erases nothing")]
            result = _RETAINED_AUTHORITY_DICT(direct.result_payload)
            trace = _RETAINED_AUTHORITY_DICT(direct.trace_payload)
            result.update(
                revocationResult="ACTIVE_REVOCATION_FOUND",
                reasonSummary="sharing grant revoked; access cut on this request",
                problems=problems,
            )
            trace.update(
                revocationResult="ACTIVE_REVOCATION_FOUND",
                revocationDecisionRefs=revocation_refs,
                reason="sharing grant revoked; access cut on this request",
            )
            decision = _RETAINED_AUTHORITY_DECISION_TYPE(
                direct.outcome, direct.request_payload, result, trace, problems)
        _RETAINED_AUTHORITY_DECISION_ALLOWED(decision)
        _RETAINED_AUTHORITY_RUNTIME_GUARD(self, cur)
        return decision


_RETAINED_AUTHORITY_EVALUATOR_TYPE = AuthorityEvaluator
_RETAINED_AUTHORITY_ROLE_ASSIGNMENTS = AuthorityEvaluator._role_assignments
_RETAINED_AUTHORITY_REVOCATIONS_FOR = AuthorityEvaluator._revocations_for
_RETAINED_AUTHORITY_SCOPE_COVERS = AuthorityEvaluator._scope_covers
_RETAINED_AUTHORITY_MATCHING_GRANTS = AuthorityEvaluator._matching_grants
_RETAINED_AUTHORITY_LIVE_SOURCE = AuthorityEvaluator._live_source_authority
_RETAINED_AUTHORITY_MATCHING_DELEGATIONS = \
    AuthorityEvaluator._matching_delegations
_RETAINED_AUTHORITY_PARTY = AuthorityEvaluator._party
_AUTHORITY_HELPER_ALIAS_ANCHORS = (
    ("_RETAINED_AUTHORITY_ROLE_ASSIGNMENTS",
     _RETAINED_AUTHORITY_ROLE_ASSIGNMENTS),
    ("_RETAINED_AUTHORITY_REVOCATIONS_FOR",
     _RETAINED_AUTHORITY_REVOCATIONS_FOR),
    ("_RETAINED_AUTHORITY_SCOPE_COVERS", _RETAINED_AUTHORITY_SCOPE_COVERS),
    ("_RETAINED_AUTHORITY_MATCHING_GRANTS",
     _RETAINED_AUTHORITY_MATCHING_GRANTS),
    ("_RETAINED_AUTHORITY_LIVE_SOURCE", _RETAINED_AUTHORITY_LIVE_SOURCE),
    ("_RETAINED_AUTHORITY_MATCHING_DELEGATIONS",
     _RETAINED_AUTHORITY_MATCHING_DELEGATIONS),
    ("_RETAINED_AUTHORITY_PARTY", _RETAINED_AUTHORITY_PARTY),
)
_RETAINED_AUTHORITY_HELPER_ALIAS_ANCHORS = \
    _AUTHORITY_HELPER_ALIAS_ANCHORS


_AUTHORITY_METHOD_ANCHORS = tuple(
    (name, value, value.__code__, capture_callable_state(value))
    for name, value in vars(AuthorityEvaluator).items()
    if type(value) is types.FunctionType
)
_RETAINED_AUTHORITY_METHOD_ANCHORS = _AUTHORITY_METHOD_ANCHORS
_RETAINED_AUTHORITY_EVALUATE = AuthorityEvaluator.evaluate
_RETAINED_AUTHORITY_EVALUATE_CODE = _RETAINED_AUTHORITY_EVALUATE.__code__
_RETAINED_AUTHORITY_EVALUATE_READ = AuthorityEvaluator.evaluate_read
_RETAINED_AUTHORITY_EVALUATE_READ_CODE = \
    _RETAINED_AUTHORITY_EVALUATE_READ.__code__


def _require_authority_runtime(evaluator, cur) -> None:
    store = object.__getattribute__(evaluator, "store") \
        if type(evaluator) is _RETAINED_AUTHORITY_EVALUATOR_TYPE else None
    if (globals().get("_require_authority_decision_type") is not
            _RETAINED_REQUIRE_AUTHORITY_DECISION_TYPE
            or _RETAINED_REQUIRE_AUTHORITY_DECISION_TYPE.__code__ is not
            _RETAINED_REQUIRE_AUTHORITY_DECISION_TYPE_CODE):
        if type(store) is _RETAINED_AUTHORITY_STORE_TYPE:
            _RETAINED_STORE_MARK_TRANSACTION_INTEGRITY_VIOLATION(store)
        raise RuntimeError("AuthorityEvaluator runtime composition changed")
    try:
        _RETAINED_REQUIRE_AUTHORITY_DECISION_TYPE()
    except BaseException:
        if type(store) is _RETAINED_AUTHORITY_STORE_TYPE:
            _RETAINED_STORE_MARK_TRANSACTION_INTEGRITY_VIOLATION(store)
        raise
    if (type(evaluator) is not _RETAINED_AUTHORITY_EVALUATOR_TYPE
            or globals().get("AuthorityEvaluator") is not
            _RETAINED_AUTHORITY_EVALUATOR_TYPE
            or globals().get("Store") is not _RETAINED_AUTHORITY_STORE_TYPE
            or type(store) is not _RETAINED_AUTHORITY_STORE_TYPE
            or globals().get("authority_decision_allowed") is not
            _RETAINED_AUTHORITY_DECISION_ALLOWED
            or _RETAINED_AUTHORITY_DECISION_ALLOWED.__code__ is not
            _RETAINED_AUTHORITY_DECISION_ALLOWED_CODE
            or globals().get("_copy_evaluate_inputs") is not
            _RETAINED_COPY_EVALUATE_INPUTS
            or _RETAINED_COPY_EVALUATE_INPUTS.__code__ is not
            _RETAINED_COPY_EVALUATE_INPUTS_CODE
            or globals().get("_canonical_authority_decision_state") is not
            _RETAINED_CANONICAL_AUTHORITY_DECISION_STATE
            or _RETAINED_CANONICAL_AUTHORITY_DECISION_STATE.__code__ is not
            _RETAINED_CANONICAL_AUTHORITY_DECISION_STATE_CODE
            or globals().get("canonical_json") is not
            _RETAINED_AUTHORITY_CANONICAL_JSON
            or _RETAINED_AUTHORITY_CANONICAL_JSON.__code__ is not
            _RETAINED_AUTHORITY_CANONICAL_JSON_CODE
            or _ACTION_STAGE_VALUES is not _RETAINED_ACTION_STAGE_VALUES
            or _REVOCATION_DISPOSITION_VALUES is not
            _RETAINED_REVOCATION_DISPOSITION_VALUES
            or _SCOPE_TYPE_VALUES is not _RETAINED_SCOPE_TYPE_VALUES
            or _AI_ASSISTANT_ROLE_VALUES is not
            _RETAINED_AI_ASSISTANT_ROLE_VALUES
            or _AI_SUGGESTION_MODE_VALUES is not
            _RETAINED_AI_SUGGESTION_MODE_VALUES
            or globals().get("callable_state_matches") is not
            _RETAINED_AUTHORITY_CALLABLE_STATE_MATCHES
            or _RETAINED_AUTHORITY_CALLABLE_STATE_MATCHES.__code__ is not
            _RETAINED_AUTHORITY_CALLABLE_STATE_MATCHES_CODE
            or vars(_RETAINED_AUTHORITY_STORE_TYPE).get(
                "_mark_transaction_integrity_violation") is not
            _RETAINED_STORE_MARK_TRANSACTION_INTEGRITY_VIOLATION
            or _RETAINED_STORE_MARK_TRANSACTION_INTEGRITY_VIOLATION.__code__
            is not _RETAINED_STORE_MARK_TRANSACTION_INTEGRITY_VIOLATION_CODE
            or vars(_RETAINED_AUTHORITY_STORE_TYPE).get(
                "_require_active_serialized_cursor") is not
            _RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR
            or _RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR.__code__ is not
            _RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR_CODE
            or vars(_RETAINED_AUTHORITY_STORE_TYPE).get("find_by_kind") is not
            _RETAINED_STORE_FIND_BY_KIND
            or _RETAINED_STORE_FIND_BY_KIND.__code__ is not
            _RETAINED_STORE_FIND_BY_KIND_CODE
            or vars(_RETAINED_AUTHORITY_STORE_TYPE).get("get_record") is not
            _RETAINED_STORE_GET_RECORD
            or _RETAINED_STORE_GET_RECORD.__code__ is not
            _RETAINED_STORE_GET_RECORD_CODE
            or vars(_RETAINED_AUTHORITY_STORE_TYPE).get("get_payload") is not
            _RETAINED_STORE_GET_PAYLOAD
            or _RETAINED_STORE_GET_PAYLOAD.__code__ is not
            _RETAINED_STORE_GET_PAYLOAD_CODE
            or _AUTHORITY_SEMANTIC_FUNCTION_ANCHORS is not
            _RETAINED_AUTHORITY_SEMANTIC_FUNCTION_ANCHORS
            or _AUTHORITY_SEMANTIC_DATA_ANCHORS is not
            _RETAINED_AUTHORITY_SEMANTIC_DATA_ANCHORS
            or _AUTHORITY_TRANSITIVE_DATA_ANCHORS is not
            _RETAINED_AUTHORITY_TRANSITIVE_DATA_ANCHORS
            or any(
                any(globals().get(name) is not function for name in names)
                or function.__code__ is not code
                or not _RETAINED_AUTHORITY_CALLABLE_STATE_MATCHES(
                    function, callable_state)
                for names, function, code, callable_state in
                _RETAINED_AUTHORITY_SEMANTIC_FUNCTION_ANCHORS)
            or any(
                any(globals().get(name) is not value for name in names)
                for names, value in
                _RETAINED_AUTHORITY_SEMANTIC_DATA_ANCHORS)
            or any(
                type(namespace) is not _RETAINED_AUTHORITY_DICT
                or namespace.get(name) is not value
                for namespace, name, value in
                _RETAINED_AUTHORITY_TRANSITIVE_DATA_ANCHORS)
            or globals().get("_require_authority_runtime") is not
            _RETAINED_AUTHORITY_RUNTIME_GUARD
            or _RETAINED_AUTHORITY_RUNTIME_GUARD.__code__ is not
            _RETAINED_AUTHORITY_RUNTIME_GUARD_CODE
            or vars(_RETAINED_AUTHORITY_EVALUATOR_TYPE).get("evaluate") is not
            _RETAINED_AUTHORITY_EVALUATE
            or _RETAINED_AUTHORITY_EVALUATE.__code__ is not
            _RETAINED_AUTHORITY_EVALUATE_CODE
            or vars(_RETAINED_AUTHORITY_EVALUATOR_TYPE).get(
                "evaluate_read") is not
            _RETAINED_AUTHORITY_EVALUATE_READ
            or _RETAINED_AUTHORITY_EVALUATE_READ.__code__ is not
            _RETAINED_AUTHORITY_EVALUATE_READ_CODE
            or _AUTHORITY_METHOD_ANCHORS is not
            _RETAINED_AUTHORITY_METHOD_ANCHORS
            or _AUTHORITY_HELPER_ALIAS_ANCHORS is not
            _RETAINED_AUTHORITY_HELPER_ALIAS_ANCHORS
            or any(
                vars(_RETAINED_AUTHORITY_EVALUATOR_TYPE).get(name) is not
                function
                or function.__code__ is not code
                or not _RETAINED_AUTHORITY_CALLABLE_STATE_MATCHES(
                    function, callable_state)
                for name, function, code, callable_state in
                _RETAINED_AUTHORITY_METHOD_ANCHORS)
            or any(
                globals().get(name) is not function
                for name, function in
                _RETAINED_AUTHORITY_HELPER_ALIAS_ANCHORS)):
        if type(store) is _RETAINED_AUTHORITY_STORE_TYPE:
            _RETAINED_STORE_MARK_TRANSACTION_INTEGRITY_VIOLATION(store)
        raise RuntimeError("AuthorityEvaluator runtime composition changed")
    _RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR(store, cur)


_RETAINED_AUTHORITY_RUNTIME_GUARD = _require_authority_runtime
_RETAINED_AUTHORITY_RUNTIME_GUARD_CODE = _require_authority_runtime.__code__
