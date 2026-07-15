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

import json

from dataclasses import dataclass, field
from typing import Any

from . import authority as authority_module
from . import policy, profile_policy, sufficiency
from .authority import AuthorityEvaluator, authority_decision_allowed
from .callable_state import capture_callable_state, callable_state_matches
from .context import ContextAssembler, ContextNotReconstructible, mint, parse_ts
from .contracts import ContractViolation, canonical_json, copy_exact_json
from .emission import PromotionEmitter, ReplayWriter, submission_evidence_refs
from .materializer import Materializer
from .problems import runtime_problem
from .runtime_bundle import RuntimeBundle, RuntimeBundleError, RuntimeComponent
from .store import Store


_AUTHORITY_EVALUATE = (
    AuthorityEvaluator,
    "evaluate",
    AuthorityEvaluator.evaluate,
    AuthorityEvaluator.evaluate.__code__,
    capture_callable_state(AuthorityEvaluator.evaluate),
)
_AUTHORITY_DECISION_ALLOWED = authority_decision_allowed
_AUTHORITY_DECISION_ALLOWED_CODE = authority_decision_allowed.__code__
_CONTEXT_ASSEMBLE = (
    ContextAssembler,
    "assemble",
    ContextAssembler.assemble,
    ContextAssembler.assemble.__code__,
    capture_callable_state(ContextAssembler.assemble),
)
_MATERIALIZER_INVALIDATE_FOR_SOURCES = (
    Materializer,
    "invalidate_for_sources",
    Materializer.invalidate_for_sources,
    Materializer.invalidate_for_sources.__code__,
    capture_callable_state(Materializer.invalidate_for_sources),
)
_MATERIALIZER_RECOMPUTE = (
    Materializer,
    "recompute",
    Materializer.recompute,
    Materializer.recompute.__code__,
    capture_callable_state(Materializer.recompute),
)
_REPLAY_WRITE = (
    ReplayWriter,
    "write",
    ReplayWriter.write,
    ReplayWriter.write.__code__,
    capture_callable_state(ReplayWriter.write),
)
_DESCRIPTOR_POLICY_EVIDENCE = (
    profile_policy.DescriptorPolicyProvider,
    "evidence_policy",
    profile_policy.DescriptorPolicyProvider.evidence_policy,
    profile_policy.DescriptorPolicyProvider.evidence_policy.__code__,
    capture_callable_state(
        profile_policy.DescriptorPolicyProvider.evidence_policy),
)
_DESCRIPTOR_POLICY_VALIDATION = (
    profile_policy.DescriptorPolicyProvider,
    "validation_policy",
    profile_policy.DescriptorPolicyProvider.validation_policy,
    profile_policy.DescriptorPolicyProvider.validation_policy.__code__,
    capture_callable_state(
        profile_policy.DescriptorPolicyProvider.validation_policy),
)
_DESCRIPTOR_POLICY_CALLABLES = (
    _DESCRIPTOR_POLICY_EVIDENCE,
    _DESCRIPTOR_POLICY_VALIDATION,
)
_DESCRIPTOR_POLICY_MISSING_CLASS_MEMBER = object()
_DESCRIPTOR_POLICY_DATA_SURFACE = tuple(
    (
        name,
        vars(profile_policy.DescriptorPolicyProvider).get(
            name, _DESCRIPTOR_POLICY_MISSING_CLASS_MEMBER),
    )
    for name in (
        "descriptor", "runtime_bundle", "policy_ref",
        "_policy_document_bytes", "_validation_policy_bytes",
        "__getattribute__", "__getattr__", "__setattr__", "__delattr__",
    )
)
_PROMOTION_EMITTER_INIT = (
    PromotionEmitter,
    "__init__",
    PromotionEmitter.__init__,
    PromotionEmitter.__init__.__code__,
    capture_callable_state(PromotionEmitter.__init__),
)
_PROMOTION_EMITTER_SUBMISSION_REFS = (
    PromotionEmitter,
    "_submission_evidence_refs",
    PromotionEmitter._submission_evidence_refs,
    PromotionEmitter._submission_evidence_refs.__code__,
    capture_callable_state(PromotionEmitter._submission_evidence_refs),
)
_PROMOTION_EMITTER_BUILD_ASSERTION = (
    PromotionEmitter,
    "_build_assertion",
    PromotionEmitter._build_assertion,
    PromotionEmitter._build_assertion.__code__,
    capture_callable_state(PromotionEmitter._build_assertion),
)
_PROMOTION_EMITTER_LINK_ASSERTION = (
    PromotionEmitter,
    "_link_assertion",
    PromotionEmitter._link_assertion,
    PromotionEmitter._link_assertion.__code__,
    capture_callable_state(PromotionEmitter._link_assertion),
)
_PROMOTION_EMITTER_EMIT_ASSERTION = (
    PromotionEmitter,
    "_emit_assertion",
    PromotionEmitter._emit_assertion,
    PromotionEmitter._emit_assertion.__code__,
    capture_callable_state(PromotionEmitter._emit_assertion),
)
_PROMOTION_EMITTER_STORE_CASE = (
    PromotionEmitter,
    "_store_case",
    PromotionEmitter._store_case,
    PromotionEmitter._store_case.__code__,
    capture_callable_state(PromotionEmitter._store_case),
)
_PROMOTION_EMITTER_ENSURE_IDENTITY = (
    PromotionEmitter,
    "_ensure_identity_record",
    PromotionEmitter._ensure_identity_record,
    PromotionEmitter._ensure_identity_record.__code__,
    capture_callable_state(PromotionEmitter._ensure_identity_record),
)
_PROMOTION_EMITTER_PENDING_ASSERTION = (
    PromotionEmitter,
    "emit_pending_assertion",
    PromotionEmitter.emit_pending_assertion,
    PromotionEmitter.emit_pending_assertion.__code__,
    capture_callable_state(PromotionEmitter.emit_pending_assertion),
)
_PROMOTION_EMITTER_SELF_REVIEW = (
    PromotionEmitter,
    "emit_self_review_promotion",
    PromotionEmitter.emit_self_review_promotion,
    PromotionEmitter.emit_self_review_promotion.__code__,
    capture_callable_state(PromotionEmitter.emit_self_review_promotion),
)
_PROMOTION_EMITTER_QUEUE_ACCEPTANCE = (
    PromotionEmitter,
    "emit_queue_acceptance",
    PromotionEmitter.emit_queue_acceptance,
    PromotionEmitter.emit_queue_acceptance.__code__,
    capture_callable_state(PromotionEmitter.emit_queue_acceptance),
)
_PROMOTION_EMITTER_QUEUE_REJECTION = (
    PromotionEmitter,
    "emit_queue_rejection",
    PromotionEmitter.emit_queue_rejection,
    PromotionEmitter.emit_queue_rejection.__code__,
    capture_callable_state(PromotionEmitter.emit_queue_rejection),
)
_PROMOTION_EMITTER_QUEUE_CONTEST = (
    PromotionEmitter,
    "emit_queue_contest",
    PromotionEmitter.emit_queue_contest,
    PromotionEmitter.emit_queue_contest.__code__,
    capture_callable_state(PromotionEmitter.emit_queue_contest),
)
_PROMOTION_EMITTER_CALLABLES = (
    _PROMOTION_EMITTER_INIT,
    _PROMOTION_EMITTER_SUBMISSION_REFS,
    _PROMOTION_EMITTER_BUILD_ASSERTION,
    _PROMOTION_EMITTER_LINK_ASSERTION,
    _PROMOTION_EMITTER_EMIT_ASSERTION,
    _PROMOTION_EMITTER_STORE_CASE,
    _PROMOTION_EMITTER_ENSURE_IDENTITY,
    _PROMOTION_EMITTER_PENDING_ASSERTION,
    _PROMOTION_EMITTER_SELF_REVIEW,
    _PROMOTION_EMITTER_QUEUE_ACCEPTANCE,
    _PROMOTION_EMITTER_QUEUE_REJECTION,
    _PROMOTION_EMITTER_QUEUE_CONTEST,
)
_PROMOTION_EMITTER_MISSING_CLASS_MEMBER = object()
_PROMOTION_EMITTER_DISPATCH_SURFACE = tuple(
    (
        name,
        vars(PromotionEmitter).get(
            name, _PROMOTION_EMITTER_MISSING_CLASS_MEMBER),
    )
    for name in (
        "ctx", "__getattribute__", "__getattr__", "__setattr__", "__delattr__")
)
_RETAINED_CONTEXT_SERVICE_CALLABLES = (
    _AUTHORITY_EVALUATE,
    _CONTEXT_ASSEMBLE,
    _MATERIALIZER_INVALIDATE_FOR_SOURCES,
    _MATERIALIZER_RECOMPUTE,
    _REPLAY_WRITE,
    *_DESCRIPTOR_POLICY_CALLABLES,
    *_PROMOTION_EMITTER_CALLABLES,
)

# Decision policy is selected once with the reviewed stage code.  The tables
# are deeply immutable; point-of-use code never reloads a public module binding
# after the transaction preflight.
_COMMIT_CLASS_TO_FAMILY = policy.COMMIT_CLASS_TO_FAMILY
_COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS = \
    policy.COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS
_COMMIT_CLASS_TO_PROMOTION_TARGET = policy.COMMIT_CLASS_TO_PROMOTION_TARGET
_REVIEW_ACTION_AUTHORITY = policy.REVIEW_ACTION_AUTHORITY
_NON_PROMOTING_RETAIN_REASONS = policy.NON_PROMOTING_RETAIN_REASONS
_NON_PROMOTING_DEFAULT_REASON = policy.NON_PROMOTING_DEFAULT_REASON
_ABSENT = policy.ABSENT
_OPERATION_FLOOR_CHECKS = sufficiency.OPERATION_FLOOR_CHECKS

_REVOCATION_DISPOSITION = (
    policy, "revocation_disposition", policy.revocation_disposition,
    policy.revocation_disposition.__code__,
    capture_callable_state(policy.revocation_disposition),
)
_AUTHORITY_DECISION_ALLOWED_FUNCTION = (
    authority_module, "authority_decision_allowed",
    _AUTHORITY_DECISION_ALLOWED, _AUTHORITY_DECISION_ALLOWED_CODE,
    capture_callable_state(_AUTHORITY_DECISION_ALLOWED),
)
_STRUCTURE_SELF_ACCEPTABLE = (
    policy, "structure_self_acceptable", policy.structure_self_acceptable,
    policy.structure_self_acceptable.__code__,
    capture_callable_state(policy.structure_self_acceptable),
)
_BUILD_ACCEPTANCE_CASE = (
    sufficiency, "build_acceptance_case", sufficiency.build_acceptance_case,
    sufficiency.build_acceptance_case.__code__,
    capture_callable_state(sufficiency.build_acceptance_case),
)
_BUILD_FLOOR_CASE = (
    sufficiency, "build_floor_case", sufficiency.build_floor_case,
    sufficiency.build_floor_case.__code__,
    capture_callable_state(sufficiency.build_floor_case),
)
_BUILD_FLOOR_CASE_WITH_POLICY = (
    sufficiency, "build_floor_case_with_policy",
    sufficiency.build_floor_case_with_policy,
    sufficiency.build_floor_case_with_policy.__code__,
    capture_callable_state(sufficiency.build_floor_case_with_policy),
)
_OPERATION_ADVISORIES = (
    sufficiency, "operation_advisories", sufficiency.operation_advisories,
    sufficiency.operation_advisories.__code__,
    capture_callable_state(sufficiency.operation_advisories),
)
_OPERATION_ADVISORIES_WITH_POLICY = (
    sufficiency, "operation_advisories_with_policy",
    sufficiency.operation_advisories_with_policy,
    sufficiency.operation_advisories_with_policy.__code__,
    capture_callable_state(sufficiency.operation_advisories_with_policy),
)
_DURABLE_EVIDENCE = (
    sufficiency, "durable_evidence", sufficiency.durable_evidence,
    sufficiency.durable_evidence.__code__,
    capture_callable_state(sufficiency.durable_evidence),
)
_RETAINED_DECISION_FUNCTIONS = (
    _AUTHORITY_DECISION_ALLOWED_FUNCTION,
    _REVOCATION_DISPOSITION,
    _STRUCTURE_SELF_ACCEPTABLE,
    _BUILD_ACCEPTANCE_CASE,
    _BUILD_FLOOR_CASE,
    _BUILD_FLOOR_CASE_WITH_POLICY,
    _OPERATION_ADVISORIES,
    _OPERATION_ADVISORIES_WITH_POLICY,
    _DURABLE_EVIDENCE,
)


def _raise_context_service_dispatch_error(
        ctx, message: str,
        _mark_integrity=Store._mark_transaction_integrity_violation,
) -> None:
    """Poison the active transaction before reporting service-code drift."""
    if type(ctx.store) is Store:
        _mark_integrity(ctx.store)
    raise RuntimeBundleError(message)


def _require_retained_context_service(
        ctx, entry, service,
        _retained=_RETAINED_CONTEXT_SERVICE_CALLABLES,
        _raise=_raise_context_service_dispatch_error,
        _state_matches=callable_state_matches,
) -> None:
    """Require the exact retained service method immediately around a call."""
    if (type(entry) is not tuple
            or len(entry) != 5
            or entry not in _retained):
        _raise(
            ctx, "retained context-service dispatch entry is malformed")
    owner, name, function, code, callable_state = entry
    namespace_missing = False
    try:
        namespace = object.__getattribute__(service, "__dict__")
    except AttributeError:
        namespace_missing = True
        namespace = None
    if (type(service) is not owner
            or (not namespace_missing
                and (type(namespace) is not dict or name in namespace))
            or vars(owner).get(name) is not function
            or getattr(function, "__code__", None) is not code
            or not _state_matches(function, callable_state)):
        _raise(
            ctx, f"retained {owner.__name__}.{name} callable changed")


def _invoke_retained_context_service(
        ctx, entry, service, *args,
        _require=_require_retained_context_service,
        **kwargs,
):
    """Call retained service code with adjacent pre/post integrity checks."""
    _require(ctx, entry, service)
    function = entry[2]
    try:
        result = function(service, *args, **kwargs)
    except BaseException:
        _require(ctx, entry, service)
        raise
    _require(ctx, entry, service)
    return result


def _descriptor_policy_expected_bytes(
        ctx, provider,
        _loads=json.loads,
        _canonical=canonical_json,
        _copy=copy_exact_json,
        _getattribute=object.__getattribute__,
        _getitem=dict.__getitem__,
        _raise=_raise_context_service_dispatch_error,
) -> tuple[bytes, bytes]:
    """Derive exact policy outputs from immutable RuntimeBundle bytes."""
    try:
        provider_namespace = _getattribute(provider, "__dict__")
        ctx_namespace = _getattribute(ctx, "__dict__")
        if type(provider_namespace) is not dict or type(ctx_namespace) is not dict:
            _raise(ctx, "retained descriptor policy namespace is malformed")
        runtime_bundle = _getitem(provider_namespace, "runtime_bundle")
        policy_ref = _getitem(provider_namespace, "policy_ref")
        retained_runtime_bundle = _getitem(ctx_namespace, "runtime_bundle")
        if (type(runtime_bundle) is not RuntimeBundle
                or runtime_bundle is not retained_runtime_bundle
                or type(policy_ref) is not str):
            _raise(ctx, "retained descriptor policy bundle identity changed")
        bundle_namespace = _getattribute(runtime_bundle, "__dict__")
        if type(bundle_namespace) is not dict:
            _raise(ctx, "retained RuntimeBundle namespace is malformed")
        components = _getitem(bundle_namespace, "components")
        if type(components) is not tuple:
            _raise(ctx, "retained RuntimeBundle components are malformed")
        matches = [
            component for component in components
            if (type(component) is RuntimeComponent
                and type(_getattribute(component, "__dict__")) is dict
                and _getitem(
                    _getattribute(component, "__dict__"), "role") ==
                "PROFILE_POLICY"
                and _getitem(
                    _getattribute(component, "__dict__"), "logical_ref") ==
                policy_ref)
        ]
        if len(matches) != 1:
            _raise(
                ctx, "retained descriptor policy component is not unique")
        component_namespace = _getattribute(matches[0], "__dict__")
        policy_bytes = _getitem(component_namespace, "canonical_bytes")
        document = _loads(policy_bytes)
        validation_bytes = _canonical(
            _copy(document["validation"])).encode("utf-8")
        provider_policy_bytes = _getitem(
            provider_namespace, "_policy_document_bytes")
        provider_validation_bytes = _getitem(
            provider_namespace, "_validation_policy_bytes")
    except RuntimeBundleError:
        raise
    except (AttributeError, ContractViolation, KeyError, TypeError, ValueError,
            UnicodeError, RecursionError) as exc:
        _raise(ctx, f"retained descriptor policy snapshot is malformed: {exc}")
    if (type(policy_bytes) is not bytes
            or type(validation_bytes) is not bytes
            or provider_policy_bytes != policy_bytes
            or provider_validation_bytes != validation_bytes):
        _raise(
            ctx, "retained descriptor policy snapshot changed before invocation")
    return policy_bytes, validation_bytes


def _invoke_retained_descriptor_policy(
        ctx, entry, provider, *args,
        _callables=_DESCRIPTOR_POLICY_CALLABLES,
        _data_surface=_DESCRIPTOR_POLICY_DATA_SURFACE,
        _missing=_DESCRIPTOR_POLICY_MISSING_CLASS_MEMBER,
        _require=_require_retained_context_service,
        _expected_bytes=_descriptor_policy_expected_bytes,
        _copy=copy_exact_json,
        _canonical=canonical_json,
        _raise=_raise_context_service_dispatch_error,
        **kwargs,
):
    """Invoke policy access while guarding the complete provider surface.

    ``validation_policy`` retains the evidence-policy implementation it
    delegates to.  Requiring both public bindings immediately before and after
    either call prevents a transient replacement of one method from steering a
    decision while the other method remains unchanged.
    """
    if (type(entry) is not tuple
            or not any(entry is retained for retained in _callables)):
        _raise(
            ctx, "retained descriptor-policy dispatch entry is malformed")

    def require_all() -> None:
        for retained in _callables:
            _require(ctx, retained, provider)

    def require_data_surface() -> None:
        namespace = vars(profile_policy.DescriptorPolicyProvider)
        if any(namespace.get(name, _missing) is not expected
               for name, expected in _data_surface):
            _raise(
                ctx, "DescriptorPolicyProvider data surface changed")

    require_all()
    require_data_surface()
    expected_before = _expected_bytes(ctx, provider)
    function = entry[2]
    try:
        result = function(provider, *args, **kwargs)
    except BaseException:
        require_all()
        require_data_surface()
        _expected_bytes(ctx, provider)
        raise
    try:
        verified_result = _copy(result)
        actual_bytes = _canonical(verified_result).encode("utf-8")
    except (ContractViolation, TypeError, ValueError, UnicodeError,
            RecursionError) as exc:
        _raise(
            ctx, f"descriptor policy returned non-exact decision data: {exc}")
    expected_index = 0 if entry is _callables[0] else 1
    expected_after = _expected_bytes(ctx, provider)
    if (expected_after != expected_before
            or actual_bytes != expected_before[expected_index]):
        _raise(
            ctx, "descriptor policy returned data outside retained RuntimeBundle bytes")
    require_all()
    require_data_surface()
    return verified_result


def _invoke_retained_promotion_emitter(
        ctx, entry, emitter, *args,
        _callables=_PROMOTION_EMITTER_CALLABLES,
        _dispatch_surface=_PROMOTION_EMITTER_DISPATCH_SURFACE,
        _missing=_PROMOTION_EMITTER_MISSING_CLASS_MEMBER,
        _require=_require_retained_context_service,
        _getattribute=object.__getattribute__,
        **kwargs,
):
    """Invoke one emitter endpoint while guarding its complete method graph."""
    if (type(entry) is not tuple
            or not any(entry is retained for retained in _callables)):
        _raise_context_service_dispatch_error(
            ctx, "retained PromotionEmitter dispatch entry is malformed")

    def require_all() -> None:
        for retained in _callables:
            _require(ctx, retained, emitter)

    def require_dispatch_surface() -> None:
        namespace = vars(PromotionEmitter)
        if any(namespace.get(name, _missing) is not expected
               for name, expected in _dispatch_surface):
            _raise_context_service_dispatch_error(
                ctx, "PromotionEmitter dispatch surface changed")

    def require_instance_namespace(*, before_init: bool) -> None:
        try:
            namespace = _getattribute(emitter, "__dict__")
        except AttributeError:
            namespace = None
        if before_init:
            valid = type(namespace) is dict and dict.__len__(namespace) == 0
        else:
            valid = (
                type(namespace) is dict
                and dict.__len__(namespace) == 1
                and dict.__contains__(namespace, "ctx")
                and dict.__getitem__(namespace, "ctx") is ctx
            )
        if not valid:
            _raise_context_service_dispatch_error(
                ctx, "PromotionEmitter instance context changed")

    is_constructor = entry is _callables[0]
    require_all()
    require_dispatch_surface()
    require_instance_namespace(before_init=is_constructor)
    function = entry[2]
    try:
        result = function(emitter, *args, **kwargs)
    except BaseException:
        require_all()
        require_dispatch_surface()
        require_instance_namespace(before_init=False)
        raise
    require_all()
    require_dispatch_surface()
    require_instance_namespace(before_init=False)
    return result


def _invoke_retained_decision_function(
        ctx, entry, *args,
        _retained=_RETAINED_DECISION_FUNCTIONS,
        _raise=_raise_context_service_dispatch_error,
        _state_matches=callable_state_matches,
        **kwargs,
):
    """Invoke retained pure decision code with adjacent integrity checks."""
    if (type(entry) is not tuple
            or len(entry) != 5
            or entry not in _retained):
        _raise(
            ctx, "retained decision-function dispatch entry is malformed")
    module, name, function, code, callable_state = entry

    def require() -> None:
        if (vars(module).get(name) is not function
                or getattr(function, "__code__", None) is not code
                or not _state_matches(function, callable_state)):
            _raise(
                ctx, f"retained decision function {name} changed")

    require()
    try:
        result = function(*args, **kwargs)
    except BaseException:
        require()
        raise
    require()
    return result


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
    runtime_bundle: Any = None
    active_profile: Any = None
    profile_route_resolution: Any = None
    policy_provider: Any = None
    si_reference_bindings: Any = None
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
    # the normalized review-decision verb (M2 G5): reviewAction selects the
    # authority action, decisionOutcomeState selects the emission branch
    review_action: Any = "REVIEW_ACCEPT"     # kept verbatim from the submission
    review_outcome: Any = None               # value, or policy.ABSENT if omitted
    review_branch: str = "ACCEPT"            # resolved by policy.review_branch
    # stage products
    authz_decision: Any = None
    erp_id: str | None = None
    structure_payload_id: str | None = None   # typed identity-payload carrier (G1)
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

    def run(
            self, ctx: GateContext,
            _commit_class_to_family=_COMMIT_CLASS_TO_FAMILY,
            _absent=_ABSENT,
            _invoke_context_service=_invoke_retained_context_service,
            _replay_write=_REPLAY_WRITE,
            _replay_writer_type=ReplayWriter,
    ) -> GatePass | GateReplay:
        sub = ctx.sub
        prior = ctx.store.idempotency_lookup(ctx.cur, ctx.idem_key)
        if prior is not None:
            return GateReplay(_invoke_context_service(
                ctx, _replay_write, _replay_writer_type(), ctx, prior))

        if ctx.commit_class not in _commit_class_to_family:
            raise ContractViolation(f"unknown commit class {ctx.commit_class!r}")
        ctx.family = _commit_class_to_family[ctx.commit_class]

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
        decision_time = sub.get("decisionTime")
        if decision_time is not None and parse_ts(decision_time) is None:
            decision_time = None

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
                "decisionTime": decision_time,
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
        # the review-decision target ref: an assertion for accept/reject, an
        # in-force consequence for contest (G5-4). One ctx field, the validator
        # branch interprets it per the resolved review verb.
        ctx.acceptance_target = (
            (sub.get("reviewTargetAssertionRef") or sub.get("reviewTargetConsequenceRef"))
            if ctx.commit_class == "GOVERNANCE_DECISION" else None)
        if ctx.commit_class == "GOVERNANCE_DECISION":
            # the review-decision verb is the (reviewAction, decisionOutcomeState)
            # pair (G5-1 §3.1). ABSENT reviewAction is legacy REVIEW_ACCEPT; a
            # PRESENT value is kept VERBATIM (even falsey / non-string) so the
            # fail-closed matrix refuses it rather than truthiness-coercing it to
            # accept (PR #18 review B1). The pair is validated downstream:
            # authority by verb (AuthorityGate), outcome/branch by the
            # GovernanceAcceptanceValidator — never silently accepted.
            ctx.review_action = (sub["reviewAction"] if "reviewAction" in sub
                                 else "REVIEW_ACCEPT")
            # decisionOutcomeState gets the same absent-vs-present treatment: a
            # present null must NOT read as absent and route to legacy accept —
            # ABSENT (sentinel) is the only outcome that defaults to accept
            # (PR #18 decisionOutcomeState blocker)
            ctx.review_outcome = (sub["decisionOutcomeState"]
                                  if "decisionOutcomeState" in sub else _absent)
        ctx.store.insert_record(ctx.cur, ingress_request)
        ctx.log("INGRESS_NORMALIZATION", "NORMALIZED_DRAFT")
        return GatePass()


# ---------------------------------------------------------------------------
# stage: authority (default deny; revocation re-check)
# ---------------------------------------------------------------------------

class AuthorityGate:
    def run(
            self, ctx: GateContext,
            _review_action_authority=_REVIEW_ACTION_AUTHORITY,
            _commit_class_authority=_COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS,
            _invoke_context_service=_invoke_retained_context_service,
            _authority_evaluate=_AUTHORITY_EVALUATE,
            _invoke_decision=_invoke_retained_decision_function,
            _revocation_disposition=_REVOCATION_DISPOSITION,
            _authority_allowed=_AUTHORITY_DECISION_ALLOWED_FUNCTION,
    ) -> GatePass | GateRefusal:
        sub = ctx.sub
        # A GOVERNANCE_DECISION's authority action is selected by the review verb
        # (G5): REVIEW_ACCEPT vs the distinct REVIEW_REJECT_OR_CONTEST. An
        # unrecognized/unwired verb maps to no action — default-deny (Kernel rule
        # 2), never a silent fall-through to accept.
        if ctx.commit_class == "GOVERNANCE_DECISION":
            # a present non-string verb (null / false / list / number) is
            # unrecognized, not accept — isinstance keeps the lookup from
            # raising on an unhashable value and routes it to default-deny (B1)
            ra = ctx.review_action
            action_class = (_review_action_authority.get(ra)
                            if isinstance(ra, str) else None)
            if action_class is None:
                problem = runtime_problem(
                    "AUTHORITY_DENIED", "Unrecognized review action",
                    f"reviewAction {ctx.review_action!r} resolves to no authority "
                    "action; default deny", problem_id="problem:review-action-unknown")
                ctx.log("AUTHORITY", "DENY", reason_code="AUTHORITY_DENIED",
                        rationale="unrecognized review verb resolves to no action")
                ctx.final_outcome = "DENY"
                return GateRefusal("AUTHORITY", "DENY", "DENY", [problem])
        else:
            action_class = _commit_class_authority[ctx.commit_class]
        decision = _invoke_context_service(
            ctx, _authority_evaluate, ctx.authority,
            cur=ctx.cur,
            acting_party_ref=ctx.acting_party,
            action_class=action_class,
            action_stage="PROMOTION",
            scope={"scopeType": "FARM", "scopeRef": ctx.farm_ref},
            acting_agent_ref=sub.get("actingAgentRef"),
            ai_assistance=sub.get("aiAssistance"),
            revocation_check_required=True,
            revocation_disposition=_invoke_decision(
                ctx, _revocation_disposition,
                ctx.commit_class, sub.get("ingressChannel", "MANUAL_UI")),
        )
        allowed = _invoke_decision(ctx, _authority_allowed, decision)
        outcome = object.__getattribute__(decision, "outcome")
        ctx.record_authority_decision(decision)
        ctx.authz_decision = decision
        ctx.trace_refs["authorizationDecisionResultRef"] = \
            decision.result_payload["resultId"]
        authz_refs = [decision.request_payload["requestId"],
                      decision.result_payload["resultId"],
                      decision.trace_payload["traceId"]]
        if allowed:
            ctx.log("AUTHORITY", "ALLOW", refs=authz_refs)
            return GatePass()
        if outcome == "REQUIRE_REVIEW":
            ctx.log("AUTHORITY", "REQUIRE_REVIEW",
                    reason_code=decision.problems[0]["reasonCode"]
                                if decision.problems else None,
                    rationale=decision.result_payload["reasonSummary"],
                    refs=authz_refs)
            return GateRefusal("AUTHORITY", "REQUIRE_REVIEW", "REQUIRE_REVIEW",
                               decision.problems)
        # DENY | REQUIRE_HUMAN_APPROVAL
        ctx.log("AUTHORITY", outcome,
                reason_code=decision.problems[0]["reasonCode"]
                            if decision.problems else "AUTHORITY_DENIED",
                rationale=decision.result_payload["reasonSummary"],
                refs=authz_refs)
        final = "DENY" if outcome == "DENY" else "REQUIRE_REVIEW"
        return GateRefusal("AUTHORITY", outcome, final,
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
        elif ctx.commit_class == "STRUCTURE_ASSERTION" and ctx.structure_payload_id:
            # the validated typed identity payload becomes a durable carrier
            # record linked to the event (generic over identity type — the
            # payload IS its own contract). Stored here like the ComplianceClaim
            # carrier: a refused commit retains the captured carrier as history,
            # but the IdentityRecord is created only at promotion, so a refused
            # structure assertion never leaves a phantom identity. The identity
            # registry reaches the payload via this edge: in-force structural
            # consequence -> sourceEvent -> STRUCTURE_PAYLOAD edge -> payload.
            ctx.store.insert_record(ctx.cur, ctx.sub["payload"])
            ctx.store.add_edge(ctx.cur, "STRUCTURE_PAYLOAD", ctx.event_id,
                               ctx.structure_payload_id)
        return GatePass()


# ---------------------------------------------------------------------------
# stage: static profile applicability (ContextSnapshot assembly)
# ---------------------------------------------------------------------------

class ProfileApplicabilityGate:
    def run(
            self, ctx: GateContext,
            _invoke_context_service=_invoke_retained_context_service,
            _context_assemble=_CONTEXT_ASSEMBLE,
    ) -> GatePass | GateRefusal:
        try:
            snapshot = _invoke_context_service(
                ctx, _context_assemble, ctx.context_assembler,
                ctx.cur, ctx.farm_ref)
        except ContextNotReconstructible as exc:
            ctx.log("PACK_PROFILE_APPLICABILITY", "NOT_APPLICABLE",
                    reason_code="PROFILE_NOT_ACTIVE", rationale=str(exc))
            return GateRefusal(
                "PACK_PROFILE_APPLICABILITY", "NOT_APPLICABLE", "RETAIN_DRAFT",
                [runtime_problem(
                    "PROFILE_NOT_ACTIVE", "Active profile context unavailable",
                    "the active profile context could not be assembled "
                    f"({exc}); the claim stays a draft (fail closed)",
                    suggested_remediation="restore the active profile spine and "
                    "required reference snapshots before resubmitting")])
        ctx.log("PACK_PROFILE_APPLICABILITY", "APPLICABLE",
                refs=[snapshot["contextSnapshotId"]])
        return GatePass()


# ---------------------------------------------------------------------------
# stage: evidence sufficiency (auto-generated cases, never hand-authored)
# ---------------------------------------------------------------------------

class EvidenceSufficiencyGate:
    def run(
            self, ctx: GateContext,
            _invoke_decision=_invoke_retained_decision_function,
            _invoke_descriptor_policy=_invoke_retained_descriptor_policy,
            _evidence_policy=_DESCRIPTOR_POLICY_EVIDENCE,
            _build_acceptance_case=_BUILD_ACCEPTANCE_CASE,
            _build_floor_case=_BUILD_FLOOR_CASE,
            _build_floor_case_with_policy=_BUILD_FLOOR_CASE_WITH_POLICY,
            _operation_advisories=_OPERATION_ADVISORIES,
            _operation_advisories_with_policy=
            _OPERATION_ADVISORIES_WITH_POLICY,
            _durable_evidence=_DURABLE_EVIDENCE,
            _operation_floor_checks=_OPERATION_FLOOR_CHECKS,
            _commit_class_to_promotion_target=
            _COMMIT_CLASS_TO_PROMOTION_TARGET,
            _submission_evidence_refs=submission_evidence_refs,
    ) -> GatePass | GateRefusal:
        # The acceptance sufficiency case is an ACCEPT-only promotion guard: it
        # demands NEW reviewer evidence to overcome a NEEDS_EVIDENCE routing and
        # records a fresh acceptance-oriented case. A REJECT inherits neither
        # (G5 §3.3): reviewer evidence is optional, declining for missing evidence
        # needs no new evidence, and the decline is recorded solely in the
        # ReviewDecision — any existing sufficiency case is left unchanged
        # (PR #18 review B2). The branch was resolved by the prior ValidationGate.
        if ctx.acceptance_target and ctx.review_branch == "ACCEPT":
            kwargs = {}
            if ctx.policy_provider is not None:
                kwargs["policy_ref"] = ctx.policy_provider.policy_ref
            elif ctx.active_profile is not None:
                kwargs["policy_ref"] = ctx.active_profile.evidence_policy_ref
            case = _invoke_decision(
                ctx, _build_acceptance_case,
                ctx.store, ctx.sub, ctx.farm_ref, ctx.acceptance_payload,
                **kwargs)
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
            try:
                if ctx.policy_provider is None:
                    case, floor_failures = _invoke_decision(
                        ctx, _build_floor_case,
                        ctx.store, ctx.sub, ctx.commit_class, ctx.farm_ref,
                        ctx.assertion_id, ctx.erp_id)
                    evidence_policy = None
                else:
                    evidence_policy = _invoke_descriptor_policy(
                        ctx, _evidence_policy, ctx.policy_provider,
                        supported_checks=(
                            _operation_floor_checks
                            if ctx.commit_class == "OPERATION_CLAIM"
                            else None),
                    )
                    case, floor_failures = _invoke_decision(
                        ctx, _build_floor_case_with_policy,
                        ctx.store, ctx.sub, ctx.commit_class, ctx.farm_ref,
                        ctx.assertion_id, ctx.erp_id,
                        evidence_policy=evidence_policy,
                        policy_ref=ctx.policy_provider.policy_ref,
                        recognized_rule_refs=ctx.policy_provider.recognized_rule_refs)
            except profile_policy.ProfilePolicyError as exc:
                # P5: the floor composition is package content; a missing/malformed
                # policy fails CLOSED with a governed RuntimeProblem (never a silent
                # permissive default, never a crash)
                ctx.log("EVIDENCE_SUFFICIENCY", "INSUFFICIENT",
                        reason_code="PROFILE_NOT_ACTIVE", rationale=str(exc))
                return GateRefusal(
                    "EVIDENCE_SUFFICIENCY", "INSUFFICIENT", "RETAIN_DRAFT",
                    [runtime_problem(
                        "PROFILE_NOT_ACTIVE", "Evidence floor policy unavailable",
                        f"the active profile's evidence-review floor policy could not be "
                        f"loaded ({exc}); the claim stays a draft (fail closed)")])
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
            # P5 advisories: authorisation-mismatch / dose-range are NON-BLOCKING
            # advisory-twin warnings — surfaced in the result (ctx.problems), never
            # routed to review (not review_route_reasons) and never changing the
            # outcome. A clean claim still promotes even when an advisory is raised.
            if ctx.commit_class == "OPERATION_CLAIM":
                if ctx.policy_provider is None:
                    advisories = _invoke_decision(
                        ctx, _operation_advisories, ctx.store, ctx.sub)
                else:
                    advisories = _invoke_decision(
                        ctx, _operation_advisories_with_policy,
                        ctx.store, ctx.sub, evidence_policy)
                ctx.problems.extend(advisories)
            ctx.log("EVIDENCE_SUFFICIENCY", "SATISFIED")
            return GatePass()

        # A promoting class with no class-specific durable-evidence floor here
        # (operation / compliance are handled above) still owes the
        # AssertionRecord evidence floor (minItems:1) — and that floor is met
        # ONLY by evidence that resolves to durable EvidenceRecords. These
        # classes do not run ReferenceResolutionValidator, so the resolution
        # check lives here: a self-reference to the captured event, a dangling
        # ref, or a wrong-kind ref is fake evidence, not proof. Any of them
        # keeps the claim a draft (Kernel rule 4 / rule 7).
        if ctx.commit_class in _commit_class_to_promotion_target:
            refs = _submission_evidence_refs(ctx.sub)
            durable = _invoke_decision(
                ctx, _durable_evidence, ctx.store, refs)
            if not refs or len(durable) != len(refs):
                ctx.log("EVIDENCE_SUFFICIENCY", "INSUFFICIENT",
                        reason_code="EVIDENCE_INSUFFICIENT",
                        rationale="a promoting assertion must carry evidence that "
                                  "resolves to durable EvidenceRecords; absent, "
                                  "dangling, or wrong-kind refs are not proof")
                return GateRefusal(
                    "EVIDENCE_SUFFICIENCY", "INSUFFICIENT", "RETAIN_DRAFT",
                    [runtime_problem(
                        "EVIDENCE_INSUFFICIENT", "Evidence floor unmet",
                        "this commit class promotes to accepted state and must carry "
                        "evidence resolving to durable EvidenceRecords; the captured "
                        "event cannot be its own evidence, and a dangling or "
                        "wrong-kind ref is not evidence",
                        suggested_remediation="attach durable evidence and resubmit; "
                        "the claim stays a draft")])

        ctx.log("EVIDENCE_SUFFICIENCY", "NOT_REQUIRED",
                rationale="sufficiency cases are generated only at operation-claim "
                          "promotion and DocumentAssembly freeze (PROFILE.md)")
        return GatePass()


# ---------------------------------------------------------------------------
# stage: review / promotion (D8 self-review; queue acceptance; routing)
# ---------------------------------------------------------------------------

class ReviewPromotionGate:
    def run(
            self, ctx: GateContext,
            _invoke_decision=_invoke_retained_decision_function,
            _structure_self_acceptable=_STRUCTURE_SELF_ACCEPTABLE,
            _commit_class_to_promotion_target=
            _COMMIT_CLASS_TO_PROMOTION_TARGET,
            _non_promoting_retain_reasons=_NON_PROMOTING_RETAIN_REASONS,
            _non_promoting_default_reason=_NON_PROMOTING_DEFAULT_REASON,
            _invoke_context_service=_invoke_retained_context_service,
            _authority_evaluate=_AUTHORITY_EVALUATE,
            _authority_allowed=_AUTHORITY_DECISION_ALLOWED_FUNCTION,
            _emitter_type=PromotionEmitter,
            _allocate_emitter=object.__new__,
            _invoke_emitter=_invoke_retained_promotion_emitter,
            _emitter_init=_PROMOTION_EMITTER_INIT,
            _emit_pending_assertion=_PROMOTION_EMITTER_PENDING_ASSERTION,
            _emit_self_review=_PROMOTION_EMITTER_SELF_REVIEW,
            _emit_queue_acceptance=_PROMOTION_EMITTER_QUEUE_ACCEPTANCE,
            _emit_queue_rejection=_PROMOTION_EMITTER_QUEUE_REJECTION,
            _emit_queue_contest=_PROMOTION_EMITTER_QUEUE_CONTEST,
    ) -> GatePass | GateRefusal:
        emitter = _allocate_emitter(_emitter_type)
        _invoke_emitter(ctx, _emitter_init, emitter, ctx)
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

        # D17 bounded self-acceptance: a STRUCTURE_ASSERTION may take the
        # self-review (confirm-accept) path ONLY when it carries a recognized
        # farm-owned identity payload (StructureSelfAcceptancePolicy). Anything
        # else routes to a distinct reviewer — never "all STRUCTURE_ASSERTIONs
        # self-review". The actor's ASSERT_STRUCTURE (AuthorityGate) +
        # REVIEW_ACCEPT (below) authority and semantic validation (ValidationGate)
        # are the other D17 conditions, enforced by those gates.
        if (ctx.commit_class == "STRUCTURE_ASSERTION" and sub.get("confirmAccept")
                and sub.get("reviewerPartyRef", ctx.acting_party) == ctx.acting_party
                and not _invoke_decision(
                    ctx, _structure_self_acceptable,
                    (sub.get("payload") or {}).get("schemaVersion", ""))):
            ctx.review_route_reasons.append(runtime_problem(
                "HUMAN_APPROVAL_REQUIRED", "Structure self-review out of bounded class",
                "self-acceptance of structure assertions is limited to the farm's own "
                "setup identities (D17); this assertion routes to a distinct reviewer",
                severity="WARNING"))

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

        promotes = ctx.commit_class in _commit_class_to_promotion_target

        if ctx.acceptance_target:
            # the GovernanceAcceptanceValidator already resolved + validated the
            # (reviewAction, decisionOutcomeState) pair fail-closed and stashed the
            # branch; accept promotes a consequence, reject appends a terminal
            # decline with none (G5; docs/REVIEW_DISPUTE_SEMANTICS.md §3).
            if ctx.review_branch == "REJECT":
                _invoke_emitter(
                    ctx, _emit_queue_rejection, emitter)
            elif ctx.review_branch == "CONTEST":
                _invoke_emitter(
                    ctx, _emit_queue_contest, emitter)
            else:
                _invoke_emitter(
                    ctx, _emit_queue_acceptance, emitter)
            return GatePass()

        if not promotes:
            reason = _non_promoting_retain_reasons.get(
                ctx.commit_class, _non_promoting_default_reason)
            ctx.log("REVIEW_PROMOTION", "RETAIN_DRAFT", rationale=reason)
            ctx.final_outcome = "RETAIN_DRAFT"
            return GatePass()

        if ctx.review_route_reasons:
            # exceptions route to the advisor queue (D8) — never silent accept
            _invoke_emitter(
                ctx, _emit_pending_assertion, emitter,
                amend_case_for_routing=True)
            ctx.problems.extend(ctx.review_route_reasons)
            ctx.log("REVIEW_PROMOTION", "REQUIRE_REVIEW",
                    reason_code=ctx.review_route_reasons[0]["reasonCode"],
                    rationale="exception routes to the advisor review queue "
                              "(self-review policy covers routine claims only)")
            ctx.final_outcome = "REQUIRE_REVIEW"
            return GatePass()

        if not sub.get("confirmAccept"):
            _invoke_emitter(
                ctx, _emit_pending_assertion, emitter,
                amend_case_for_routing=False)
            ctx.log("REVIEW_PROMOTION", "RETAIN_DRAFT",
                    rationale="no review act: capture is not commitment (Kernel rule 3)")
            ctx.final_outcome = "RETAIN_DRAFT"
            return GatePass()

        # the deliberate confirm-accept step IS the review act (D8) —
        # SELF-review only: the reviewer is the transport-bound acting party.
        # REVIEW_ACCEPT authority is checked mechanically; self-review cannot
        # bypass the gates above.
        review_auth = _invoke_context_service(
            ctx, _authority_evaluate, ctx.authority,
            cur=ctx.cur,
            acting_party_ref=ctx.acting_party, action_class="REVIEW_ACCEPT",
            action_stage="PROMOTION",
            scope={"scopeType": "FARM", "scopeRef": ctx.farm_ref})
        review_allowed = _invoke_decision(
            ctx, _authority_allowed, review_auth)
        ctx.record_authority_decision(review_auth)
        if not review_allowed:
            ctx.log("REVIEW_PROMOTION", "REQUIRE_REVIEW",
                    reason_code="AUTHORITY_DENIED",
                    rationale=f"{ctx.acting_party} holds no REVIEW_ACCEPT for "
                              f"{ctx.farm_ref}")
            return GateRefusal("REVIEW_PROMOTION", "REQUIRE_REVIEW",
                               "REQUIRE_REVIEW", review_auth.problems)

        _invoke_emitter(
            ctx, _emit_self_review, emitter)
        return GatePass()


# ---------------------------------------------------------------------------
# stage: current-state materialization (after acceptance only)
# ---------------------------------------------------------------------------

class MaterializationGate:
    def run(
            self, ctx: GateContext,
            _invoke_context_service=_invoke_retained_context_service,
            _invalidate_for_sources=_MATERIALIZER_INVALIDATE_FOR_SOURCES,
            _recompute=_MATERIALIZER_RECOMPUTE,
    ) -> GatePass:
        _invoke_context_service(
            ctx, _invalidate_for_sources, ctx.materializer,
            ctx.cur, ctx.invalidation_sources or [ctx.trigger_source],
            trigger_family="BASIS_ADVANCED",
            trigger_source_ref=ctx.trigger_source,
            farm_scope_ref=ctx.farm_ref,
            reason_code="TRUTH_BASIS_ADVANCED")
        mat = _invoke_context_service(
            ctx, _recompute, ctx.materializer,
            ctx.cur, ctx.farm_ref)
        # NOTE: no materializationResultRef on the trace — the commit-time
        # recompute emits Basis+Snapshot, not a boundary Result; those
        # receipts ride the gateSequence entry below
        ctx.materialization_triggered = True
        ctx.log("CURRENT_STATE_MATERIALIZATION", "UPDATED",
                refs=[mat["basisRef"], mat["snapshotRef"]])
        return GatePass()
