"""Gate pipeline (M1 brief task 3): the EnforcementChain as a
transaction-scoped orchestration chain.

ingress normalization → authority (default deny; revocation re-check)
→ validation (named validator units, kernel/validators.py)
→ static profile applicability (ContextSnapshot assembly)
→ evidence sufficiency (auto-generated EvidenceSufficiencyCase)
→ review/promotion (self-review per D8; queue acceptance)
→ materialization → trace/result writing.

This module is the ORCHESTRATION SHELL only (issue #3): runtime policy lives
in kernel/policy.py as declarative tables, each gate is a named stage in
kernel/stages.py with a narrow typed contract (GatePass / GateRefusal /
GateReplay), validation is decomposed into named units in
kernel/validators.py, and every PROMOTION-flavor emission (assertions,
reviews, consequences, traces, results, replays) lives in
kernel/emission.py — stages and validators store their own gate records
(authority decisions, sufficiency cases, carriers) where they decide them.

The invariants are unchanged: every authoritative write crosses the chain
inside ONE transaction (D3); every refusal is a registry-coded RuntimeProblem
(Kernel rule 7); every outcome lands in the gate log and the PromotionTrace;
capture is not commitment (Kernel rule 3).
"""
from __future__ import annotations

import json
from datetime import datetime

import psycopg

from . import profile_policy, profile_runtime
from .authority import AuthorityEvaluator
from .callable_state import capture_callable_state, callable_state_matches
from .context import (ContextAssembler, ProductRegister, SIReferenceBindings,
                      mint, now_iso, parse_ts)
from .contracts import (
    ContractViolation,
    canonical_json,
    copy_exact_json as _copy_exact_json,
    sha256_of,
)
from .emission import PromotionTraceWriter, ReplayWriter
from .materializer import Materializer
from .problems import runtime_problem
from .runtime_bundle import (
    RuntimeBundle, RuntimeBundleError, RuntimeComponent,
    require_store_runtime_bundle,
)
from .store import Store
from .profile_runtime import (ProfileRuntimeError, resolve_active_descriptor,
                              profile_route_selection_document,
                              resolve_profile_route)
from .stages import (AuthorityGate, EnvelopePersist, EvidenceSufficiencyGate,
                     _DESCRIPTOR_POLICY_CALLABLES,
                     _DESCRIPTOR_POLICY_DATA_SURFACE,
                     _DESCRIPTOR_POLICY_MISSING_CLASS_MEMBER,
                     GateContext, GateRefusal, GateReplay, IngressNormalizer,
                     MaterializationGate, ProfileApplicabilityGate,
                     _PROMOTION_EMITTER_CALLABLES,
                     ReviewPromotionGate)
from .validators import ValidationGate

# law-pinned stage order (PLATFORM.md gate pipeline); validation's internal
# order lives in kernel/validators.py (the common sequence, then the
# class-specific branch: governance acceptance, compliance claim, or the
# operation sequence)
CHAIN = (
    AuthorityGate(),
    ValidationGate(),
    EnvelopePersist(),
    ProfileApplicabilityGate(),
    EvidenceSufficiencyGate(),
    ReviewPromotionGate(),
)

_GATE_ENTRY_CALLABLES = (
    (IngressNormalizer, "run", IngressNormalizer.run,
     IngressNormalizer.run.__code__,
     capture_callable_state(IngressNormalizer.run)),
    (MaterializationGate, "run", MaterializationGate.run,
     MaterializationGate.run.__code__,
     capture_callable_state(MaterializationGate.run)),
    (PromotionTraceWriter, "write", PromotionTraceWriter.write,
     PromotionTraceWriter.write.__code__,
     capture_callable_state(PromotionTraceWriter.write)),
    (ReplayWriter, "write", ReplayWriter.write, ReplayWriter.write.__code__,
     capture_callable_state(ReplayWriter.write)),
)
_RETAINED_GATE_ENTRY_CALLABLES = _GATE_ENTRY_CALLABLES


def _snapshot_submission(submission) -> tuple[str, str]:
    """Return immutable canonical bytes-as-text and the semantic source digest."""
    if type(submission) is not dict:
        raise ContractViolation(
            "submission must be an exact built-in JSON object")
    try:
        copied = _RETAINED_COPY_EXACT_JSON(submission)
    except RecursionError as exc:
        raise ContractViolation("submission JSON nesting is too deep") from exc
    semantic = {
        key: value for key, value in dict.items(copied)
        if key != "sourcePayloadDigest"
    }
    return _RETAINED_CANONICAL_JSON(copied), _RETAINED_SHA256_OF(semantic)


def _materialize_submission_snapshot(canonical: str) -> dict:
    """Create one private exact-built-in tree from the immutable snapshot."""
    materialized = _RETAINED_JSON_LOADS(canonical)
    if type(materialized) is not dict:
        raise ContractViolation("submission snapshot is not a JSON object")
    return materialized


_RETAINED_COPY_EXACT_JSON = _copy_exact_json
_RETAINED_COPY_EXACT_JSON_CODE = _copy_exact_json.__code__
_RETAINED_JSON_LOADS = json.loads
_RETAINED_JSON_LOADS_CODE = json.loads.__code__
_RETAINED_CANONICAL_JSON = canonical_json
_RETAINED_CANONICAL_JSON_CODE = canonical_json.__code__
_RETAINED_SHA256_OF = sha256_of
_RETAINED_SHA256_OF_CODE = sha256_of.__code__
_RETAINED_SNAPSHOT_SUBMISSION = _snapshot_submission
_RETAINED_SNAPSHOT_SUBMISSION_CODE = _snapshot_submission.__code__
_RETAINED_MATERIALIZE_SUBMISSION = _materialize_submission_snapshot
_RETAINED_MATERIALIZE_SUBMISSION_CODE = \
    _materialize_submission_snapshot.__code__


def _has_instance_dispatch_override(instance) -> bool:
    """Reject an instance attribute that shadows executable class behavior."""
    try:
        namespace = object.__getattribute__(instance, "__dict__")
    except AttributeError:
        return False
    if type(namespace) is not dict:
        return True
    return any(
        callable(getattr(type(instance), name, None))
        for name in namespace
    )


def _raise_retained_gate_dispatch_error(
        store, message: str,
        _mark_integrity=Store._mark_transaction_integrity_violation,
) -> None:
    """Poison an active write transaction before reporting dispatch drift."""
    if type(store) is Store:
        _mark_integrity(store)
    raise RuntimeBundleError(message)


def _require_retained_gate_callable(
        store, entry, instance,
        _has_override=_has_instance_dispatch_override,
        _raise=_raise_retained_gate_dispatch_error,
        _state_matches=callable_state_matches,
) -> None:
    if type(entry) is not tuple or len(entry) != 5:
        _raise(
            store, "retained gate dispatch entry is malformed")
    owner, name, function, code, callable_state = entry
    if (type(instance) is not owner
            or _has_override(instance)
            or vars(owner).get(name) is not function
            or getattr(function, "__code__", None) is not code
            or not _state_matches(function, callable_state)):
        _raise(
            store, "retained gate callable changed before invocation")


def _invoke_retained_gate_callable(
        store, entry, instance, *args,
        _require=_require_retained_gate_callable,
        **kwargs,
):
    """Invoke one retained function with immediate pre/post code checks."""
    _require(store, entry, instance)
    function = entry[2]
    try:
        result = function(instance, *args, **kwargs)
    except BaseException:
        _require(store, entry, instance)
        raise
    _require(store, entry, instance)
    return result


def _invoke_gate_entry(
        store, index: int, *args,
        _entries=_GATE_ENTRY_CALLABLES,
        _invoke=_invoke_retained_gate_callable,
):
    entry = _entries[index]
    return _invoke(
        store, entry, object.__new__(entry[0]), *args)


def _invoke_retained_stage(
        store, stage_dispatch, ctx,
        _raise=_raise_retained_gate_dispatch_error,
        _invoke=_invoke_retained_gate_callable,
):
    if type(stage_dispatch) is not tuple or len(stage_dispatch) != 5:
        _raise(
            store, "retained stage dispatch entry is malformed")
    stage, owner, function, code, callable_state = stage_dispatch
    return _invoke(
        store, (owner, "run", function, code, callable_state), stage, ctx)


_PROFILE_ROUTE_RESOLVER = (
    profile_runtime,
    "resolve_profile_route",
    resolve_profile_route,
    resolve_profile_route.__code__,
    capture_callable_state(resolve_profile_route),
)
_PROFILE_ROUTE_MODEL_BINDINGS = (
    ("ProfileRuntimeDescriptor", profile_runtime.ProfileRuntimeDescriptor),
    ("ProfileDescriptorCandidate", profile_runtime.ProfileDescriptorCandidate),
    ("ProfileDescriptorRegistry", profile_runtime.ProfileDescriptorRegistry),
    ("ProfileRouteRecord", profile_runtime.ProfileRouteRecord),
    ("ProfileRouteResolution", profile_runtime.ProfileRouteResolution),
)
_PROFILE_ROUTE_STATUS_ACTIVE = profile_runtime.ROUTE_STATUS_ACTIVE
_RETAINED_PROFILE_ROUTE_MODEL_BINDINGS = _PROFILE_ROUTE_MODEL_BINDINGS
_RETAINED_PROFILE_ROUTE_STATUS_ACTIVE = _PROFILE_ROUTE_STATUS_ACTIVE
_PROFILE_ROUTE_MODEL_CLASS_NAMESPACES = tuple(
    (owner, tuple(vars(owner).items()))
    for _name, owner in _PROFILE_ROUTE_MODEL_BINDINGS
)
_RETAINED_PROFILE_ROUTE_MODEL_CLASS_NAMESPACES = \
    _PROFILE_ROUTE_MODEL_CLASS_NAMESPACES


def _profile_route_model_surfaces_match(
        _namespaces=_PROFILE_ROUTE_MODEL_CLASS_NAMESPACES,
) -> bool:
    return all(
        len(vars(owner)) == len(expected_items)
        and all(name in vars(owner) and vars(owner)[name] is expected
                for name, expected in expected_items)
        for owner, expected_items in _namespaces
    )


def _exact_instance_field(
        instance, name: str,
        _getattribute=object.__getattribute__,
        _getitem=dict.__getitem__,
):
    """Read one instance-dictionary field without class descriptor dispatch."""
    return _getitem(_getattribute(instance, "__dict__"), name)


def _retained_route_selection_document(
        runtime_bundle,
        _field=_exact_instance_field,
        _loads=json.loads,
) -> dict:
    """Reparse the authenticated route-selection bytes without method dispatch."""
    if type(runtime_bundle) is not RuntimeBundle:
        raise RuntimeBundleError("retained route RuntimeBundle has the wrong type")
    components = _field(runtime_bundle, "components")
    if type(components) is not tuple:
        raise RuntimeBundleError("retained route components are malformed")
    matches = [
        component for component in components
        if (type(component) is RuntimeComponent
            and _field(component, "role") == "PROFILE_ROUTE_SELECTION"
            and _field(component, "logical_ref") ==
            "profile-route-selection:active")
    ]
    if len(matches) != 1:
        raise RuntimeBundleError(
            "retained route selection component is not unique")
    document = _loads(_field(matches[0], "canonical_bytes"))
    if type(document) is not dict:
        raise RuntimeBundleError("retained route selection is malformed")
    return document


def _authenticated_profile_route(
        store, registry, selected_profile_package_names, route_records, *,
        tenant_ref: str, farm_ref: str, effective_time, runtime_bundle,
        active_profile,
        _model_bindings=_PROFILE_ROUTE_MODEL_BINDINGS,
        _active_status=_PROFILE_ROUTE_STATUS_ACTIVE,
        _datetime_type=datetime,
        _field=_exact_instance_field,
        _selection=_retained_route_selection_document,
        _parse_ts=parse_ts,
        _sorted=sorted,
        _raise=_raise_retained_gate_dispatch_error,
):
    """Select a route only from authenticated bytes and exact object fields."""

    def integrity(message: str):
        _raise(store, message)

    try:
        if (type(registry) is not _model_bindings[2][1]
                or type(selected_profile_package_names) is not tuple
                or type(route_records) is not tuple
                or type(tenant_ref) is not str
                or type(farm_ref) is not str
                or (effective_time is not None
                    and (type(effective_time) is not _datetime_type
                         or effective_time.tzinfo is None
                         or effective_time.utcoffset() is None))
                or type(runtime_bundle) is not RuntimeBundle):
            integrity("profile route runtime inputs changed type")
        document = _selection(runtime_bundle)
        registry_document = dict.__getitem__(document, "registry")
        route_documents = dict.__getitem__(document, "routes")
        candidate_documents = dict.__getitem__(
            registry_document, "candidates")
        if (type(registry_document) is not dict
                or type(route_documents) is not list
                or type(candidate_documents) is not list
                or dict.__getitem__(document, "tenantRef") != tenant_ref
                or tuple(dict.__getitem__(
                    document, "selectedProfilePackageNames")) !=
                selected_profile_package_names):
            integrity("live profile route selection differs from retained bytes")

        registry_candidates = _field(registry, "descriptor_candidates")
        registry_discoverable = _field(
            registry, "discoverable_package_names")
        registry_enabled = _field(registry, "enabled_package_names")
        if (type(registry_candidates) is not tuple
                or type(registry_discoverable) is not tuple
                or type(registry_enabled) is not tuple
                or any(type(name) is not str for name in (
                    *registry_discoverable, *registry_enabled))
                or list(_sorted(registry_discoverable)) !=
                dict.__getitem__(registry_document, "discoverablePackageNames")
                or list(_sorted(registry_enabled)) !=
                dict.__getitem__(registry_document, "enabledPackageNames")
                or len(registry_candidates) != len(candidate_documents)
                or len(route_records) != len(route_documents)):
            integrity("live profile registry differs from retained route bytes")

        def descriptor_matches_document(descriptor, candidate_document) -> bool:
            if type(descriptor) is not _model_bindings[0][1]:
                return False
            return all(
                _field(descriptor, field_name) ==
                dict.__getitem__(candidate_document, document_name)
                for field_name, document_name in (
                    ("profile_ref", "profileRef"),
                    ("pack_ref", "packRef"),
                    ("pack_activation_set_ref", "packActivationSetRef"),
                    ("active_artifact_set_ref", "activeArtifactSetRef"),
                )
            )

        def candidate_matches_document(candidate, candidate_document) -> bool:
            return (
                type(candidate) is _model_bindings[1][1]
                and _field(candidate, "package_name") ==
                dict.__getitem__(candidate_document, "packageName")
                and _field(candidate, "enabled") is
                dict.__getitem__(candidate_document, "enabled")
                and descriptor_matches_document(
                    _field(candidate, "descriptor"), candidate_document)
            )

        if any(
                sum(candidate_matches_document(candidate, candidate_document)
                    for candidate in registry_candidates) != 1
                for candidate_document in candidate_documents):
            integrity("live profile candidates differ from retained route bytes")

        def route_time(document_value):
            if document_value is None:
                return None
            parsed = _parse_ts(document_value)
            if parsed is None:
                integrity("retained profile route time is malformed")
            return parsed

        def route_matches_document(route, route_document) -> bool:
            if type(route) is not _model_bindings[3][1]:
                return False
            exact_fields = (
                ("route_id", "routeId"),
                ("tenant_ref", "tenantRef"),
                ("farm_ref", "farmRef"),
                ("profile_package_name", "profilePackageName"),
                ("profile_ref", "profileRef"),
                ("pack_ref", "packRef"),
                ("pack_activation_set_ref", "packActivationSetRef"),
                ("active_artifact_set_ref", "activeArtifactSetRef"),
                ("status", "status"),
            )
            return (
                all(_field(route, field_name) ==
                    dict.__getitem__(route_document, document_name)
                    for field_name, document_name in exact_fields)
                and _field(route, "effective_from") == route_time(
                    dict.__getitem__(route_document, "effectiveFrom"))
                and _field(route, "effective_until") == route_time(
                    dict.__getitem__(route_document, "effectiveUntil"))
                and _field(route, "runtime_bundle_digest") ==
                _field(runtime_bundle, "digest")
            )

        if any(
                sum(route_matches_document(route, route_document)
                    for route in route_records) != 1
                for route_document in route_documents):
            integrity("live profile routes differ from retained route bytes")

        applicable_documents = []
        for route_document in route_documents:
            effective_from = route_time(
                dict.__getitem__(route_document, "effectiveFrom"))
            effective_until = route_time(
                dict.__getitem__(route_document, "effectiveUntil"))
            if (dict.__getitem__(route_document, "status") !=
                    _active_status
                    or dict.__getitem__(route_document, "tenantRef") != tenant_ref
                    or dict.__getitem__(route_document, "farmRef") != farm_ref):
                continue
            if effective_time is None:
                active_at_time = effective_from is None and effective_until is None
            else:
                active_at_time = (
                    (effective_from is None or effective_from <= effective_time)
                    and (effective_until is None
                         or effective_time < effective_until)
                )
            if active_at_time:
                applicable_documents.append(route_document)
        if not applicable_documents:
            raise ProfileRuntimeError(
                "no active profile route for tenant/farm/effective-time context")
        if len(applicable_documents) != 1:
            raise ProfileRuntimeError(
                "multiple active overlapping profile routes for "
                "tenant/farm/effective-time context")
        selected_route_document = applicable_documents[0]
        selected_routes = [
            route for route in route_records
            if route_matches_document(route, selected_route_document)
        ]
        if len(selected_routes) != 1:
            integrity("resolved profile route identity is not retained")
        route = selected_routes[0]
        package_name = dict.__getitem__(
            selected_route_document, "profilePackageName")
        bundle_descriptor = _field(runtime_bundle, "descriptor")
        if (type(bundle_descriptor) is not _model_bindings[0][1]
                or bundle_descriptor is not active_profile):
            integrity("resolved profile authority differs from retained runtime")
        selected_candidate_documents = [
            candidate_document for candidate_document in candidate_documents
            if dict.__getitem__(candidate_document, "packageName") == package_name
        ]
        route_id = dict.__getitem__(selected_route_document, "routeId")
        if not selected_candidate_documents:
            raise ProfileRuntimeError(
                f"profile route {route_id!r} targets package "
                f"{package_name!r} with no runtime_profile_descriptor.json; "
                "design-only profile slices are not active runtime profiles")
        if len(selected_candidate_documents) > 1:
            integrity("resolved profile candidate is not unique")
        selected_candidate_document = selected_candidate_documents[0]
        selected_candidates = [
            candidate for candidate in registry_candidates
            if candidate_matches_document(candidate, selected_candidate_document)
        ]
        if len(selected_candidates) != 1:
            integrity("resolved profile candidate identity is not retained")
        candidate = selected_candidates[0]
        candidate_enabled = dict.__getitem__(
            selected_candidate_document, "enabled")
        if type(candidate_enabled) is not bool:
            integrity("retained profile candidate enabled state is malformed")
        if candidate_enabled is not True:
            raise ProfileRuntimeError(
                f"profile route {route_id!r} targets package "
                f"{package_name!r} that is not enabled for this runtime")
        if package_name not in selected_profile_package_names:
            raise ProfileRuntimeError(
                f"profile route {route_id!r} targets package "
                f"{package_name!r} that is not selected for this runtime")
        if (not descriptor_matches_document(
                    bundle_descriptor, selected_candidate_document)
                or any(
                    _field(route, route_field) !=
                    _field(bundle_descriptor, descriptor_field)
                    for route_field, descriptor_field in (
                        ("profile_ref", "profile_ref"),
                        ("pack_ref", "pack_ref"),
                        ("pack_activation_set_ref", "pack_activation_set_ref"),
                        ("active_artifact_set_ref", "active_artifact_set_ref"),
                    ))):
            integrity("resolved profile descriptor differs from retained runtime")
        return route, candidate, bundle_descriptor
    except RuntimeBundleError:
        raise
    except ProfileRuntimeError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, UnicodeError,
            RecursionError) as exc:
        integrity(f"retained profile route data is malformed: {exc}")


def _build_exact_route_resolution(
        route, candidate, descriptor, effective_time,
        _resolution_type=_RETAINED_PROFILE_ROUTE_MODEL_BINDINGS[4][1],
        _getattribute=object.__getattribute__,
        _setitem=dict.__setitem__,
):
    resolution = object.__new__(_resolution_type)
    namespace = _getattribute(resolution, "__dict__")
    for name, value in (
        ("route", route),
        ("candidate", candidate),
        ("descriptor", descriptor),
        ("effective_time", effective_time),
    ):
        _setitem(namespace, name, value)
    return resolution


def _require_retained_profile_route_resolver(
        store,
        entry=_PROFILE_ROUTE_RESOLVER,
        _expected=_PROFILE_ROUTE_RESOLVER,
        _raise=_raise_retained_gate_dispatch_error,
        _state_matches=callable_state_matches,
) -> None:
    """Require both imported and defining-module route-resolver bindings."""
    if type(entry) is not tuple or entry is not _expected or len(entry) != 5:
        _raise(store, "retained profile route resolver entry is malformed")
    module, name, function, code, callable_state = entry
    if (globals().get(name) is not function
            or vars(module).get(name) is not function
            or getattr(function, "__code__", None) is not code
            or not _state_matches(function, callable_state)):
        _raise(store, "retained profile route resolver changed before invocation")


def _invoke_retained_profile_route_resolver(
        store, *args,
        _entry=_PROFILE_ROUTE_RESOLVER,
        _require=_require_retained_profile_route_resolver,
        **kwargs,
):
    """Resolve a route with adjacent checks and rollback-only drift handling."""
    _require(store, _entry)
    function = _entry[2]
    try:
        result = function(*args, **kwargs)
    except BaseException:
        _require(store, _entry)
        raise
    _require(store, _entry)
    return result


_RETAINED_HAS_INSTANCE_DISPATCH_OVERRIDE = _has_instance_dispatch_override
_RETAINED_HAS_INSTANCE_DISPATCH_OVERRIDE_CODE = \
    _RETAINED_HAS_INSTANCE_DISPATCH_OVERRIDE.__code__
_RETAINED_RAISE_GATE_DISPATCH_ERROR = _raise_retained_gate_dispatch_error
_RETAINED_RAISE_GATE_DISPATCH_ERROR_CODE = \
    _RETAINED_RAISE_GATE_DISPATCH_ERROR.__code__
_RETAINED_REQUIRE_GATE_CALLABLE = _require_retained_gate_callable
_RETAINED_REQUIRE_GATE_CALLABLE_CODE = \
    _RETAINED_REQUIRE_GATE_CALLABLE.__code__
_RETAINED_INVOKE_GATE_CALLABLE = _invoke_retained_gate_callable
_RETAINED_INVOKE_GATE_CALLABLE_CODE = \
    _RETAINED_INVOKE_GATE_CALLABLE.__code__
_RETAINED_INVOKE_GATE_ENTRY = _invoke_gate_entry
_RETAINED_INVOKE_GATE_ENTRY_CODE = _RETAINED_INVOKE_GATE_ENTRY.__code__
_RETAINED_INVOKE_STAGE = _invoke_retained_stage
_RETAINED_INVOKE_STAGE_CODE = _RETAINED_INVOKE_STAGE.__code__
_RETAINED_REQUIRE_PROFILE_ROUTE_RESOLVER = \
    _require_retained_profile_route_resolver
_RETAINED_REQUIRE_PROFILE_ROUTE_RESOLVER_CODE = \
    _RETAINED_REQUIRE_PROFILE_ROUTE_RESOLVER.__code__
_RETAINED_INVOKE_PROFILE_ROUTE_RESOLVER = \
    _invoke_retained_profile_route_resolver
_RETAINED_INVOKE_PROFILE_ROUTE_RESOLVER_CODE = \
    _RETAINED_INVOKE_PROFILE_ROUTE_RESOLVER.__code__
_GATE_HELPER_ANCHORS = (
    ("_copy_exact_json", _RETAINED_COPY_EXACT_JSON,
     _RETAINED_COPY_EXACT_JSON_CODE,
     capture_callable_state(_RETAINED_COPY_EXACT_JSON)),
    ("_snapshot_submission", _RETAINED_SNAPSHOT_SUBMISSION,
     _RETAINED_SNAPSHOT_SUBMISSION_CODE,
     capture_callable_state(_RETAINED_SNAPSHOT_SUBMISSION)),
    ("_materialize_submission_snapshot", _RETAINED_MATERIALIZE_SUBMISSION,
     _RETAINED_MATERIALIZE_SUBMISSION_CODE,
     capture_callable_state(_RETAINED_MATERIALIZE_SUBMISSION)),
    ("_has_instance_dispatch_override",
     _RETAINED_HAS_INSTANCE_DISPATCH_OVERRIDE,
     _RETAINED_HAS_INSTANCE_DISPATCH_OVERRIDE_CODE,
     capture_callable_state(_RETAINED_HAS_INSTANCE_DISPATCH_OVERRIDE)),
    ("_raise_retained_gate_dispatch_error",
     _RETAINED_RAISE_GATE_DISPATCH_ERROR,
     _RETAINED_RAISE_GATE_DISPATCH_ERROR_CODE,
     capture_callable_state(_RETAINED_RAISE_GATE_DISPATCH_ERROR)),
    ("_require_retained_gate_callable", _RETAINED_REQUIRE_GATE_CALLABLE,
     _RETAINED_REQUIRE_GATE_CALLABLE_CODE,
     capture_callable_state(_RETAINED_REQUIRE_GATE_CALLABLE)),
    ("_invoke_retained_gate_callable", _RETAINED_INVOKE_GATE_CALLABLE,
     _RETAINED_INVOKE_GATE_CALLABLE_CODE,
     capture_callable_state(_RETAINED_INVOKE_GATE_CALLABLE)),
    ("_invoke_gate_entry", _RETAINED_INVOKE_GATE_ENTRY,
     _RETAINED_INVOKE_GATE_ENTRY_CODE,
     capture_callable_state(_RETAINED_INVOKE_GATE_ENTRY)),
    ("_invoke_retained_stage", _RETAINED_INVOKE_STAGE,
     _RETAINED_INVOKE_STAGE_CODE,
     capture_callable_state(_RETAINED_INVOKE_STAGE)),
    ("resolve_profile_route", _PROFILE_ROUTE_RESOLVER[2],
     _PROFILE_ROUTE_RESOLVER[3], _PROFILE_ROUTE_RESOLVER[4]),
    ("_require_retained_profile_route_resolver",
     _RETAINED_REQUIRE_PROFILE_ROUTE_RESOLVER,
     _RETAINED_REQUIRE_PROFILE_ROUTE_RESOLVER_CODE,
     capture_callable_state(_RETAINED_REQUIRE_PROFILE_ROUTE_RESOLVER)),
    ("_invoke_retained_profile_route_resolver",
     _RETAINED_INVOKE_PROFILE_ROUTE_RESOLVER,
     _RETAINED_INVOKE_PROFILE_ROUTE_RESOLVER_CODE,
     capture_callable_state(_RETAINED_INVOKE_PROFILE_ROUTE_RESOLVER)),
    ("_exact_instance_field", _exact_instance_field,
     _exact_instance_field.__code__,
     capture_callable_state(_exact_instance_field)),
    ("_profile_route_model_surfaces_match",
     _profile_route_model_surfaces_match,
     _profile_route_model_surfaces_match.__code__,
     capture_callable_state(_profile_route_model_surfaces_match)),
    ("_retained_route_selection_document",
     _retained_route_selection_document,
     _retained_route_selection_document.__code__,
     capture_callable_state(_retained_route_selection_document)),
    ("_authenticated_profile_route", _authenticated_profile_route,
     _authenticated_profile_route.__code__,
     capture_callable_state(_authenticated_profile_route)),
    ("_build_exact_route_resolution", _build_exact_route_resolution,
     _build_exact_route_resolution.__code__,
     capture_callable_state(_build_exact_route_resolution)),
)


class GatePipeline:
    _SEALED_FIELDS = {
        "store", "route_backed", "profile_route_records",
        "profile_route_registry", "selected_profile_package_names", "tenant_ref",
        "active_profile", "runtime_bundle", "policy_provider",
        "si_reference_bindings", "si_reference_bindings_descriptor", "authority",
        "context", "materializer", "products", "chain",
        "_stage_dispatch", "_runtime_composition_sealed",
        "_route_dispatch",
    }

    def __setattr__(self, name, value):
        if getattr(self, "_runtime_composition_sealed", False):
            if name in self._SEALED_FIELDS:
                raise AttributeError(
                    "GatePipeline runtime composition is immutable")
            if callable(getattr(type(self), name, None)):
                raise AttributeError("GatePipeline runtime dispatch is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if (getattr(self, "_runtime_composition_sealed", False)
                and (name in self._SEALED_FIELDS
                     or callable(getattr(type(self), name, None)))):
            raise AttributeError(
                "GatePipeline sealed runtime state cannot be deleted")
        object.__delattr__(self, name)

    def __init__(
        self,
        store,
        product_register: ProductRegister | None = None,
        *,
        active_descriptor=None,
        active_profile=None,
        profile_route_records=None,
        profile_route_registry=None,
        selected_profile_package_names=None,
        tenant_ref=None,
        runtime_bundle=None,
    ):
        if product_register is not None:
            raise ProfileRuntimeError(
                "caller-supplied ProductRegister is forbidden for governed runtime")
        self.store = store
        route_inputs = (
            profile_route_records,
            profile_route_registry,
            selected_profile_package_names,
            tenant_ref,
        )
        self.route_backed = any(value is not None for value in route_inputs)
        if self.route_backed and any(value is None for value in route_inputs):
            raise ProfileRuntimeError(
                "route-backed GatePipeline requires profile_route_records, "
                "profile_route_registry, selected_profile_package_names, and "
                "tenant_ref")
        self.profile_route_records = (
            tuple(profile_route_records) if profile_route_records is not None else None)
        self.profile_route_registry = profile_route_registry
        self.selected_profile_package_names = (
            tuple(sorted(selected_profile_package_names))
            if selected_profile_package_names is not None else None)
        self.tenant_ref = tenant_ref
        if (active_descriptor is not None and active_profile is not None
                and active_descriptor != active_profile):
            raise ProfileRuntimeError(
                "active_descriptor and active_profile refer to different descriptors")
        self.active_profile = resolve_active_descriptor(
            active_descriptor if active_descriptor is not None else active_profile,
            allow_config_default=True,
        )
        self.runtime_bundle = runtime_bundle or store.runtime_bundle
        require_store_runtime_bundle(store, self.runtime_bundle, "GatePipeline")
        if self.route_backed and self.tenant_ref != self.runtime_bundle.tenant_ref:
            raise ProfileRuntimeError(
                "profile route tenant must exactly match the RuntimeBundle tenant")
        if self.route_backed:
            if any(route.runtime_bundle_digest != self.runtime_bundle.digest
                   for route in self.profile_route_records):
                raise ProfileRuntimeError(
                    "every profile route must receipt the exact RuntimeBundle digest")
            route_selection = profile_route_selection_document(
                self.profile_route_registry,
                self.selected_profile_package_names,
                self.profile_route_records,
                tenant_ref=self.tenant_ref,
            )
            try:
                retained_route_selection = self.runtime_bundle.json_component(
                    "PROFILE_ROUTE_SELECTION", "profile-route-selection:active")
            except RuntimeBundleError as exc:
                raise ProfileRuntimeError(
                    "route-backed runtime lacks a retained profile route selection") \
                    from exc
            if route_selection != retained_route_selection:
                raise ProfileRuntimeError(
                    "caller profile route selection differs from the RuntimeBundle")
        if _exact_instance_field(
                self.runtime_bundle, "descriptor") is not self.active_profile:
            raise ProfileRuntimeError(
                "GatePipeline descriptor and RuntimeBundle do not match exactly")
        self.policy_provider = profile_policy.DescriptorPolicyProvider(
            self.active_profile, runtime_bundle=self.runtime_bundle)
        self.si_reference_bindings = SIReferenceBindings.from_descriptor(
            self.active_profile, runtime_bundle=self.runtime_bundle)
        self.si_reference_bindings_descriptor = self.active_profile
        self.authority = AuthorityEvaluator(store)
        self.context = ContextAssembler(
            store, active_descriptor=self.active_profile,
            runtime_bundle=self.runtime_bundle)
        self.materializer = Materializer(
            store, active_descriptor=self.active_profile,
            runtime_bundle=self.runtime_bundle)
        self.products = ProductRegister(
            self.si_reference_bindings, runtime_bundle=self.runtime_bundle)
        self.products.load_from_store(store)
        self.products.freeze()
        self.chain = CHAIN
        self._stage_dispatch = tuple(
            (stage, type(stage), type(stage).run, type(stage).run.__code__,
             capture_callable_state(type(stage).run))
            for stage in self.chain)
        self._route_dispatch = tuple(
            (GatePipeline, name, vars(GatePipeline)[name],
             vars(GatePipeline)[name].__code__,
             capture_callable_state(vars(GatePipeline)[name]))
            for name in ("_resolve_profile_route", "_bind_route_resolution")
        )
        self._runtime_composition_sealed = True

    def _assert_runtime_composition(
            self,
            _route_surfaces=_profile_route_model_surfaces_match,
            _policy_surface=_DESCRIPTOR_POLICY_DATA_SURFACE,
            _policy_missing=_DESCRIPTOR_POLICY_MISSING_CLASS_MEMBER,
    ) -> None:
        if not _route_surfaces():
            _raise_retained_gate_dispatch_error(
                _exact_instance_field(self, "store"),
                "profile route model surface changed before runtime check",
            )
        policy_namespace = vars(profile_policy.DescriptorPolicyProvider)
        if any(policy_namespace.get(name, _policy_missing) is not expected
               for name, expected in _policy_surface):
            _raise_retained_gate_dispatch_error(
                _exact_instance_field(self, "store"),
                "DescriptorPolicyProvider data surface changed before runtime check",
            )
        require_store_runtime_bundle(
            self.store, self.runtime_bundle, "GatePipeline decision")
        policy_components = [
            component for component in self.runtime_bundle.components
            if (component.role == "PROFILE_POLICY"
                and component.logical_ref == self.active_profile.evidence_policy_ref)
        ]
        expected_policy_bytes = None
        expected_validation_policy_bytes = None
        if len(policy_components) == 1:
            expected_policy_bytes = policy_components[0].canonical_bytes
            try:
                expected_validation_policy_bytes = _RETAINED_CANONICAL_JSON(
                    _RETAINED_JSON_LOADS(expected_policy_bytes)["validation"]
                ).encode("utf-8")
            except (KeyError, TypeError, ValueError, UnicodeError):
                pass
        expected_policy_refs = \
            profile_policy.DescriptorPolicyProvider.expected_recognized_rule_refs(
                self.active_profile)
        expected_bindings = SIReferenceBindings.from_descriptor(
            self.active_profile, runtime_bundle=self.runtime_bundle)
        expected_products = ProductRegister(
            expected_bindings, runtime_bundle=self.runtime_bundle)
        route_selection_matches = not self.route_backed
        if self.route_backed:
            try:
                route_selection_matches = profile_route_selection_document(
                    self.profile_route_registry,
                    self.selected_profile_package_names,
                    self.profile_route_records,
                    tenant_ref=self.tenant_ref,
                ) == self.runtime_bundle.json_component(
                    "PROFILE_ROUTE_SELECTION", "profile-route-selection:active")
            except (ProfileRuntimeError, RuntimeBundleError, TypeError, ValueError):
                route_selection_matches = False
        if not _route_surfaces():
            _raise_retained_gate_dispatch_error(
                _exact_instance_field(self, "store"),
                "profile route model surface changed during runtime check",
            )
        services = (
            self.policy_provider, self.authority, self.context,
            self.materializer, self.materializer.context, self.products,
        )
        if (type(self) is not GatePipeline
                or self._runtime_composition_sealed is not True
                or _exact_instance_field(
                    self.runtime_bundle, "descriptor") is not self.active_profile
                or not route_selection_matches
                or _RETAINED_HAS_INSTANCE_DISPATCH_OVERRIDE(self)
                or _RETAINED_HAS_INSTANCE_DISPATCH_OVERRIDE(self.store)
                or type(self.store) is not Store
                or type(self.policy_provider) is not
                profile_policy.DescriptorPolicyProvider
                or type(self.authority) is not AuthorityEvaluator
                or type(self.context) is not ContextAssembler
                or type(self.materializer) is not Materializer
                or type(self.materializer.context) is not ContextAssembler
                or type(self.products) is not ProductRegister
                or self.context._runtime_composition_sealed is not True
                or self.materializer._runtime_composition_sealed is not True
                or self.materializer.context._runtime_composition_sealed is not True
                or any(_RETAINED_HAS_INSTANCE_DISPATCH_OVERRIDE(service)
                       for service in services)
                or self.chain is not CHAIN
                or len(self._stage_dispatch) != len(self.chain)
                or len(self._route_dispatch) != 2
                or tuple(entry[1] for entry in self._route_dispatch) != (
                    "_resolve_profile_route", "_bind_route_resolution")
                or _PROFILE_ROUTE_MODEL_BINDINGS is not
                _RETAINED_PROFILE_ROUTE_MODEL_BINDINGS
                or _PROFILE_ROUTE_MODEL_CLASS_NAMESPACES is not
                _RETAINED_PROFILE_ROUTE_MODEL_CLASS_NAMESPACES
                or not _route_surfaces()
                or _PROFILE_ROUTE_STATUS_ACTIVE is not
                _RETAINED_PROFILE_ROUTE_STATUS_ACTIVE
                or any(vars(profile_runtime).get(name) is not retained
                       for name, retained in
                       _RETAINED_PROFILE_ROUTE_MODEL_BINDINGS)
                or profile_runtime.ROUTE_STATUS_ACTIVE is not
                _RETAINED_PROFILE_ROUTE_STATUS_ACTIVE
                or _RETAINED_COPY_EXACT_JSON is not _copy_exact_json
                or _RETAINED_SNAPSHOT_SUBMISSION is not _snapshot_submission
                or _RETAINED_MATERIALIZE_SUBMISSION is not
                _materialize_submission_snapshot
                or _RETAINED_JSON_LOADS is not json.loads
                or _RETAINED_JSON_LOADS.__code__ is not
                _RETAINED_JSON_LOADS_CODE
                or _RETAINED_CANONICAL_JSON is not canonical_json
                or _RETAINED_CANONICAL_JSON.__code__ is not
                _RETAINED_CANONICAL_JSON_CODE
                or _RETAINED_SHA256_OF is not sha256_of
                or _RETAINED_SHA256_OF.__code__ is not
                _RETAINED_SHA256_OF_CODE
                or _GATE_ENTRY_CALLABLES is not
                _RETAINED_GATE_ENTRY_CALLABLES
                or any(
                    globals().get(name) is not function
                    or function.__code__ is not code
                    or not callable_state_matches(function, callable_state)
                    for name, function, code, callable_state
                    in _GATE_HELPER_ANCHORS)
                or any(
                    selected_stage is not stage
                    or selected_type is not type(stage)
                    or selected_function is not vars(selected_type).get("run")
                    or getattr(selected_function, "__code__", None) is not
                    selected_code
                    or not callable_state_matches(
                        selected_function, selected_callable_state)
                    for stage, (selected_stage, selected_type,
                                selected_function, selected_code,
                                selected_callable_state)
                    in zip(self.chain, self._stage_dispatch))
                or any(
                    owner is not GatePipeline
                    or vars(owner).get(name) is not function
                    or getattr(function, "__code__", None) is not code
                    or not callable_state_matches(function, callable_state)
                    for owner, name, function, code, callable_state
                    in self._route_dispatch)
                or any(
                    vars(owner).get(name) is not function
                    or getattr(function, "__code__", None) is not code
                    or not callable_state_matches(function, callable_state)
                    for owner, name, function, code, callable_state
                    in _GATE_ENTRY_CALLABLES)
                or any(
                    vars(owner).get(name) is not function
                    or getattr(function, "__code__", None) is not code
                    or not callable_state_matches(function, callable_state)
                    for owner, name, function, code, callable_state
                    in (*_DESCRIPTOR_POLICY_CALLABLES,
                        *_PROMOTION_EMITTER_CALLABLES))
                or any(_RETAINED_HAS_INSTANCE_DISPATCH_OVERRIDE(stage)
                       for stage in self.chain)
                or _exact_instance_field(
                    self.policy_provider, "descriptor") is not self.active_profile
                or self.policy_provider.runtime_bundle is not self.runtime_bundle
                or self.policy_provider._policy_document_bytes !=
                expected_policy_bytes
                or self.policy_provider._validation_policy_bytes !=
                expected_validation_policy_bytes
                or self.policy_provider.policy_ref !=
                self.active_profile.evidence_policy_ref
                or self.policy_provider.recognized_rule_refs != expected_policy_refs
                or self.si_reference_bindings_descriptor is not self.active_profile
                or self.si_reference_bindings != expected_bindings
                or self.context.store is not self.store
                or self.context.runtime_bundle is not self.runtime_bundle
                or self.context.active_profile is not self.active_profile
                or self.materializer.store is not self.store
                or self.materializer.runtime_bundle is not self.runtime_bundle
                or self.materializer.active_profile is not self.active_profile
                or self.materializer.context.store is not self.store
                or self.materializer.context.runtime_bundle is not self.runtime_bundle
                or self.materializer.context.active_profile is not self.active_profile
                or self.products.runtime_bundle is not self.runtime_bundle
                or self.products.bindings != self.si_reference_bindings
                or self.products._frozen is not True
                or self.products._by_snapshot != expected_products._by_snapshot
                or self.authority.store is not self.store):
            _raise_retained_gate_dispatch_error(
                self.store,
                "GatePipeline runtime composition changed after construction",
            )

    # ======================================================================
    # the governed front door
    # ======================================================================

    def commit(self, submission: dict) -> dict:
        """Run one capture through the full chain. Returns the
        CommitIngressResult payload. One call = one transaction (D3)."""
        if type(submission) is not dict:
            raise ContractViolation(
                "submission must be an exact built-in JSON object")
        GatePipeline._assert_runtime_composition(self)
        canonical_submission, source_digest = \
            _RETAINED_SNAPSHOT_SUBMISSION(submission)
        GatePipeline._assert_runtime_composition(self)
        try:
            with Store.serialized_tx(self.store) as cur:
                result = GatePipeline._commit_in_tx(
                    self, cur,
                    _RETAINED_MATERIALIZE_SUBMISSION(canonical_submission),
                    source_digest=source_digest,
                )
                return result
        except psycopg.errors.UniqueViolation:
            # a concurrent commit won the idempotency-key race; our transaction
            # rolled back completely — serve the replay path against the winner.
            # (Under the single-writer lock — M2 G2 — writers serialize, so this
            # backstop is now reached only across connections that bypass it.)
            with Store.serialized_tx(self.store) as cur:
                retry_submission = \
                    _RETAINED_MATERIALIZE_SUBMISSION(canonical_submission)
                prior = Store.idempotency_lookup(
                    self.store,
                    cur, retry_submission["idempotencyKey"])
                if prior is None:
                    raise
                ctx = GatePipeline._new_context(
                    self, cur, retry_submission,
                    source_digest=source_digest)
                result = _RETAINED_INVOKE_GATE_ENTRY(
                    self.store, 3, ctx, prior)
                GatePipeline._assert_runtime_composition(self)
                return result

    @staticmethod
    def _source_digest(sub: dict) -> str:
        """ALWAYS the server-computed canonical digest of the whole semantic
        submission. A caller-supplied sourcePayloadDigest is evidence metadata
        at most — it never participates in idempotency decisions. Payload-less
        classes digest their full submission, never the constant digest of {}."""
        return _RETAINED_SNAPSHOT_SUBMISSION(sub)[1]

    def _new_context(
            self, cur, sub: dict, *, source_digest: str | None = None,
    ) -> GateContext:
        policy_provider = (
            self.policy_provider
            if self.active_profile is self.policy_provider.descriptor
            else None
        )
        si_reference_bindings = (
            self.si_reference_bindings
            if self.active_profile == self.si_reference_bindings_descriptor
            else None
        )
        return GateContext(
            cur=cur, store=self.store, authority=self.authority,
            context_assembler=self.context, materializer=self.materializer,
            products=self.products, active_profile=self.active_profile,
            runtime_bundle=self.runtime_bundle,
            policy_provider=policy_provider,
            si_reference_bindings=si_reference_bindings,
            sub=sub,
            request_id=mint("cir"), ingested_at=now_iso(),
            source_digest=(source_digest if source_digest is not None
                           else GatePipeline._source_digest(sub)),
            commit_class=sub["commitClass"], farm_ref=sub["farmRef"],
            acting_party=sub["actingPartyRef"], idem_key=sub["idempotencyKey"],
            event_id=mint("event"), assertion_id=mint("assert"))

    @staticmethod
    def _route_farm_ref(
            ctx: GateContext,
            _field=_exact_instance_field,
    ) -> str:
        envelope = _field(ctx, "envelope")
        scopes = ((envelope or {}).get("anchorScopes") or [])
        farm_scopes = [
            scope for scope in scopes
            if isinstance(scope, dict) and scope.get("scopeType") == "FARM"
        ]
        if len(farm_scopes) != 1:
            raise ProfileRuntimeError(
                "profile route resolution requires exactly one FARM anchor "
                "scope entry in the normalized submission envelope")
        farm_ref = farm_scopes[0].get("scopeRef")
        if not farm_ref:
            raise ProfileRuntimeError(
                "profile route FARM anchor scope must include scopeRef")
        if farm_ref != _field(ctx, "farm_ref"):
            raise ProfileRuntimeError(
                "profile route FARM anchor scope must match the top-level "
                "submission farmRef")
        return farm_ref

    @staticmethod
    def _route_effective_time(
            ctx: GateContext,
            _field=_exact_instance_field,
            _parse_ts=parse_ts,
    ):
        commit_class = _field(ctx, "commit_class")
        if commit_class == "GOVERNANCE_DECISION":
            raw = _field(ctx, "sub").get("decisionTime")
            field = "decisionTime"
        elif commit_class in {
            "OPERATION_CLAIM",
            "COMPLIANCE_ASSERTION",
            "STRUCTURE_ASSERTION",
        }:
            if _field(ctx, "temporal_problem"):
                raise ProfileRuntimeError(
                    "profile route eventTime is unparseable")
            raw = _field(ctx, "event_time")
            field = "eventTime"
        else:
            raise ProfileRuntimeError(
                f"profile route time source is unsupported for "
                f"{commit_class!r}")
        if not raw:
            raise ProfileRuntimeError(
                f"profile route requires normalized claim-time field {field}")
        parsed = _parse_ts(raw)
        if parsed is None:
            raise ProfileRuntimeError(
                f"profile route claim-time field {field} is not parseable")
        return parsed

    def _bind_route_resolution(
            self, ctx: GateContext, resolution, *,
            farm_ref: str, effective_time,
            _field=_exact_instance_field,
            _select=_authenticated_profile_route,
            _setitem=dict.__setitem__,
            _resolution_type=_RETAINED_PROFILE_ROUTE_MODEL_BINDINGS[4][1],
    ):
        """Bind only a resolution that exactly matches every retained input.

        Descriptor equality alone is insufficient: a forged resolution could
        carry the expected descriptor while changing tenant, farm, claim time,
        selected package, route status, or RuntimeBundle identity.  The retained
        resolver should make every condition below true; any mismatch therefore
        represents runtime-integrity drift and permanently poisons the active
        transaction.
        """
        store = _field(self, "store")
        runtime_bundle = _field(self, "runtime_bundle")
        active_profile = _field(self, "active_profile")
        if (type(store) is not Store
                or _field(store, "_runtime_bundle") is not runtime_bundle):
            _raise_retained_gate_dispatch_error(
                store, "profile route RuntimeBundle is not the Store authority")
        expected_route, expected_candidate, expected_descriptor = _select(
            store,
            _field(self, "profile_route_registry"),
            _field(self, "selected_profile_package_names"),
            _field(self, "profile_route_records"),
            tenant_ref=_field(self, "tenant_ref"),
            farm_ref=farm_ref,
            effective_time=effective_time,
            runtime_bundle=runtime_bundle,
            active_profile=active_profile,
        )
        if type(resolution) is not _resolution_type:
            _raise_retained_gate_dispatch_error(
                store, "resolved profile route has an unretained result type")
        try:
            resolution_namespace = object.__getattribute__(
                resolution, "__dict__")
            if (type(resolution_namespace) is not dict
                    or set(dict.keys(resolution_namespace)) != {
                        "route", "candidate", "descriptor", "effective_time"}):
                _raise_retained_gate_dispatch_error(
                    store, "resolved profile route namespace is malformed")
            route = _field(resolution, "route")
            candidate = _field(resolution, "candidate")
            descriptor = _field(resolution, "descriptor")
            resolved_effective_time = _field(resolution, "effective_time")
        except (AttributeError, KeyError, TypeError) as exc:
            _raise_retained_gate_dispatch_error(
                store, f"resolved profile route is malformed: {exc}")
        if (route is not expected_route
                or candidate is not expected_candidate
                or descriptor is not expected_descriptor
                or descriptor is not active_profile
                or descriptor is not _field(runtime_bundle, "descriptor")
                or resolved_effective_time is not effective_time):
            _raise_retained_gate_dispatch_error(
                store,
                "resolved profile route differs from retained runtime inputs",
            )
        context_namespace = object.__getattribute__(ctx, "__dict__")
        for name, value in (
            ("profile_route_resolution", resolution),
            ("active_profile", active_profile),
            ("runtime_bundle", runtime_bundle),
            ("policy_provider", _field(self, "policy_provider")),
            ("context_assembler", _field(self, "context")),
            ("materializer", _field(self, "materializer")),
            ("products", _field(self, "products")),
            ("si_reference_bindings", _field(
                self, "si_reference_bindings")),
        ):
            _setitem(context_namespace, name, value)
        return expected_route, active_profile

    def _resolve_profile_route(
            self, ctx: GateContext,
            _route_farm_ref=_route_farm_ref.__func__,
            _route_effective_time=_route_effective_time.__func__,
            _require_resolver=_require_retained_profile_route_resolver,
            _select=_authenticated_profile_route,
            _build_resolution=_build_exact_route_resolution,
            _invoke_route_callable=_invoke_retained_gate_callable,
            _field=_exact_instance_field,
            _setitem=dict.__setitem__,
    ):
        store = _field(self, "store")
        _require_resolver(store)
        try:
            farm_ref = _route_farm_ref(ctx)
            effective_time = _route_effective_time(ctx)
            route, candidate, descriptor = _select(
                store,
                _field(self, "profile_route_registry"),
                _field(self, "selected_profile_package_names"),
                _field(self, "profile_route_records"),
                tenant_ref=_field(self, "tenant_ref"),
                farm_ref=farm_ref,
                effective_time=effective_time,
                runtime_bundle=_field(self, "runtime_bundle"),
                active_profile=_field(self, "active_profile"),
            )
            resolution = _build_resolution(
                route, candidate, descriptor, effective_time)
        except ProfileRuntimeError as exc:
            ctx.log("PACK_PROFILE_APPLICABILITY", "PROFILE_ROUTE_REFUSE",
                    reason_code="PROFILE_NOT_ACTIVE",
                    rationale=f"PROFILE_ROUTE: {exc}")
            return GateRefusal(
                "PACK_PROFILE_APPLICABILITY", "PROFILE_ROUTE_REFUSE",
                "RETAIN_DRAFT",
                [runtime_problem(
                    "PROFILE_NOT_ACTIVE", "Profile route unavailable",
                    "the active profile route could not be resolved "
                    f"({exc}); the claim stays a draft (fail closed)",
                    suggested_remediation="restore an explicit active "
                    "tenant/farm profile route before resubmitting")])
        _setitem(object.__getattribute__(ctx, "__dict__"), "farm_ref", farm_ref)
        route_dispatch = _field(self, "_route_dispatch")
        bound_route, bound_descriptor = _invoke_route_callable(
            store, route_dispatch[1], self, ctx, resolution,
            farm_ref=farm_ref,
            effective_time=effective_time)
        ctx.log("PACK_PROFILE_APPLICABILITY", "PROFILE_ROUTE_PASS",
                rationale="PROFILE_ROUTE: resolved active profile route",
                refs=[_field(bound_route, "route_id"),
                      _field(bound_descriptor, "profile_ref")])
        return None

    def _commit_in_tx(
            self, cur, sub: dict, *, source_digest: str | None = None,
            _invoke_route_callable=_invoke_retained_gate_callable,
            _field=_exact_instance_field,
    ) -> dict:
        GatePipeline._assert_runtime_composition(self)
        ctx = GatePipeline._new_context(
            self, cur, sub, source_digest=source_digest)

        ingress = _RETAINED_INVOKE_GATE_ENTRY(self.store, 0, ctx)
        if isinstance(ingress, GateReplay):
            GatePipeline._assert_runtime_composition(self)
            return ingress.result

        if _field(self, "route_backed"):
            route_dispatch = _field(self, "_route_dispatch")
            route_outcome = _invoke_route_callable(
                _field(self, "store"), route_dispatch[0], self, ctx)
            if isinstance(route_outcome, GateRefusal):
                ctx.problems.extend(route_outcome.problems)
                ctx.final_outcome = route_outcome.final_outcome
                ctx.ensure_envelope_stored()
                result = _RETAINED_INVOKE_GATE_ENTRY(self.store, 2, ctx)
                GatePipeline._assert_runtime_composition(self)
                return result

        for stage_dispatch in self._stage_dispatch:
            outcome = _RETAINED_INVOKE_STAGE(
                self.store, stage_dispatch, ctx)
            if isinstance(outcome, GateRefusal):
                ctx.problems.extend(outcome.problems)
                ctx.final_outcome = outcome.final_outcome
                # the normalized draft event is still recorded (refusals are
                # traceable history, not silence) — emitted under this trace
                ctx.ensure_envelope_stored()
                result = _RETAINED_INVOKE_GATE_ENTRY(self.store, 2, ctx)
                GatePipeline._assert_runtime_composition(self)
                return result

        if ctx.final_outcome == "PROMOTE_ACCEPTED":
            _RETAINED_INVOKE_GATE_ENTRY(self.store, 1, ctx)

        result = _RETAINED_INVOKE_GATE_ENTRY(self.store, 2, ctx)
        GatePipeline._assert_runtime_composition(self)
        return result
