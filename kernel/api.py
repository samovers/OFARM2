"""FastAPI surface — the platform's governed front door over HTTP.

Refusals are data, not transport errors: a processed commit always returns
its CommitIngressResult envelope (problems inside, reason codes from the
registry); malformed requests are 422s. Read surfaces enforce default deny
per request — there is no unauthenticated path to farm-scoped truth.
"""
from __future__ import annotations

import json
import math
import types
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import auth_oidc, config, context
from .authority import AuthorityEvaluator, authority_decision_allowed
from .contracts import ContractViolation, canonical_json
from .problems import runtime_problem
from .gates import GatePipeline
from .runtime_bundle import (
    JSON_CANONICALIZATION,
    RAW_CANONICALIZATION,
    RuntimeBundle,
    sha256_bytes,
)
from .store import Store
from .views import OutputGenerator

# create_app default: resolve the OIDC verifier from the environment (the uvicorn
# --factory entrypoint takes no args). Pass oidc=None to FORCE the development/
# conformance X-Acting-Party shim; pass an OidcConfig to verify tokens.
_FROM_ENV = object()

# The HTTP boundary must never redispatch governed work through mutable class
# attributes.  Retain the exact implementation selected at import time and its
# code identity; ``create_app`` closes over these anchors so replacing either a
# class method or a module global after startup cannot redirect a request.
_FUNCTION_TYPE = types.FunctionType
_STORE_TYPE = Store
_GATE_PIPELINE_TYPE = GatePipeline
_OUTPUT_GENERATOR_TYPE = OutputGenerator
_AUTHORITY_EVALUATOR_TYPE = AuthorityEvaluator
_OIDC_CONFIG_TYPE = auth_oidc.OidcConfig

_GATE_COMMIT = GatePipeline.commit
_GATE_COMMIT_CODE = _GATE_COMMIT.__code__
_OUTPUT_ASSERT_RUNTIME_COMPOSITION = OutputGenerator._assert_runtime_composition
_OUTPUT_ASSERT_RUNTIME_COMPOSITION_CODE = \
    _OUTPUT_ASSERT_RUNTIME_COMPOSITION.__code__
_OUTPUT_PASSPORT_VIEW = OutputGenerator.passport_view
_OUTPUT_PASSPORT_VIEW_CODE = _OUTPUT_PASSPORT_VIEW.__code__
_OUTPUT_FREEZE_INSPECTION_REGISTER = OutputGenerator.freeze_inspection_register
_OUTPUT_FREEZE_INSPECTION_REGISTER_CODE = \
    _OUTPUT_FREEZE_INSPECTION_REGISTER.__code__
_AUTHORITY_EVALUATE_READ = AuthorityEvaluator.evaluate_read
_AUTHORITY_EVALUATE_READ_CODE = _AUTHORITY_EVALUATE_READ.__code__
_AUTHORITY_DECISION_ALLOWED = authority_decision_allowed
_AUTHORITY_DECISION_ALLOWED_CODE = authority_decision_allowed.__code__
_OIDC_VERIFY = auth_oidc.OidcConfig.verify
_OIDC_VERIFY_CODE = _OIDC_VERIFY.__code__
_OIDC_RUNTIME_GUARD = auth_oidc._require_oidc_runtime
_OIDC_RUNTIME_GUARD_CODE = _OIDC_RUNTIME_GUARD.__code__
_STORE_REQUIRE_TRANSACTION_POSTURE = Store._require_transaction_python_posture
_STORE_REQUIRE_TRANSACTION_POSTURE_CODE = \
    _STORE_REQUIRE_TRANSACTION_POSTURE.__code__
_STORE_REQUIRE_DISPATCH = Store._require_runtime_dispatch_integrity
_STORE_REQUIRE_DISPATCH_CODE = _STORE_REQUIRE_DISPATCH.__code__
_STORE_RUNTIME_BUNDLE = Store.runtime_bundle.fget
_STORE_RUNTIME_BUNDLE_CODE = _STORE_RUNTIME_BUNDLE.__code__
_STORE_GET_RECORD = Store.get_record
_STORE_GET_RECORD_CODE = _STORE_GET_RECORD.__code__
_STORE_INSERT_RECORD = Store.insert_record
_STORE_INSERT_RECORD_CODE = _STORE_INSERT_RECORD.__code__
_STORE_UNREACHABLE_RECORDS = Store.unreachable_authoritative_records
_STORE_UNREACHABLE_RECORDS_CODE = _STORE_UNREACHABLE_RECORDS.__code__
_STORE_TX = Store.tx
_STORE_TX_CODE = _STORE_TX.__code__
_STORE_SERIALIZED_TX = Store.serialized_tx
_STORE_SERIALIZED_TX_CODE = _STORE_SERIALIZED_TX.__code__
_RUNTIME_BUNDLE_JSON_COMPONENT = RuntimeBundle.json_component
_RUNTIME_BUNDLE_JSON_COMPONENT_CODE = \
    _RUNTIME_BUNDLE_JSON_COMPONENT.__code__
_RECEIPT_CANONICAL_JSON = canonical_json
_RECEIPT_CANONICAL_JSON_CODE = _RECEIPT_CANONICAL_JSON.__code__
_RECEIPT_SHA256_BYTES = sha256_bytes
_RECEIPT_SHA256_BYTES_CODE = _RECEIPT_SHA256_BYTES.__code__
_RECEIPT_RESPONSE_TYPE = Response
_RECEIPT_RESPONSE_CALL = Response.__call__
_RECEIPT_RESPONSE_CALL_CODE = _RECEIPT_RESPONSE_CALL.__code__
_RETAINED_RUNTIME_PROBLEM = runtime_problem
_RETAINED_RUNTIME_PROBLEM_CODE = _RETAINED_RUNTIME_PROBLEM.__code__
_RETAINED_HTTP_EXCEPTION_TYPE = HTTPException
_RETAINED_OIDC_ERROR_TYPE = auth_oidc.OidcError
_RECEIPT_JSON_LOADS = json.loads
_RECEIPT_JSON_LOADS_CODE = _RECEIPT_JSON_LOADS.__code__
_RECEIPT_JSON_DECODE_ERROR = json.JSONDecodeError


def _normalize_receipt_json(value):
    """Copy only closed JSON data; tuple locations become JSON arrays."""
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("receipt JSON contains a non-finite number")
        return value
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError("receipt JSON object keys must be exact strings")
        return {
            key: _RETAINED_RECEIPT_NORMALIZER(item)
            for key, item in value.items()
        }
    if type(value) in {list, tuple}:
        return [_RETAINED_RECEIPT_NORMALIZER(item) for item in value]
    if isinstance(value, BaseException):
        return str(value)
    raise TypeError(
        f"receipt payload contains unsupported {type(value).__name__}")


_RETAINED_RECEIPT_NORMALIZER = _normalize_receipt_json
_RETAINED_RECEIPT_NORMALIZER_CODE = _normalize_receipt_json.__code__


def _exact_oidc_config_state(value) -> tuple:
    """Return only exact immutable OIDC primitives; reject equal subclasses."""
    if type(value) is not _OIDC_CONFIG_TYPE:
        raise TypeError("OIDC application binding requires exact OidcConfig")
    string_fields = (
        value.issuer, value.audience, value.algorithm, value.subject_claim,
    )
    if (any(type(item) is not str for item in string_fields)
            or (value.hs256_secret is not None
                and type(value.hs256_secret) is not str)
            or (value.roles_claim is not None
                and type(value.roles_claim) is not str)
            or type(value.leeway_seconds) is not int):
        raise TypeError("OIDC application binding contains non-exact field types")
    return (
        value.issuer, value.audience, value.algorithm, value.hs256_secret,
        value.subject_claim, value.roles_claim, value.leeway_seconds,
    )


_EXACT_OIDC_CONFIG_STATE = _exact_oidc_config_state
_EXACT_OIDC_CONFIG_STATE_CODE = _EXACT_OIDC_CONFIG_STATE.__code__


def _application_callables(app: FastAPI) -> tuple[types.FunctionType, ...]:
    """Collect exact local endpoints, handlers, dependencies, and closures."""
    selected: dict[int, types.FunctionType] = {}

    def add(value) -> None:
        if type(value) is types.FunctionType and value.__module__ == __name__:
            selected[id(value)] = value

    def add_dependant(dependant) -> None:
        if dependant is None:
            return
        add(getattr(dependant, "call", None))
        for child in getattr(dependant, "dependencies", ()):
            add_dependant(child)

    for route in app.routes:
        add(getattr(route, "endpoint", None))
        add_dependant(getattr(route, "dependant", None))
    for handler in app.exception_handlers.values():
        add(handler)
    return tuple(selected[key] for key in sorted(selected))


def _graph_value_state(value, active: set[int] | None = None):
    """Snapshot mutable ASGI graph data without invoking behavioral equality."""
    recurse = _RETAINED_API_GRAPH_VALUE_STATE
    active = set() if active is None else active
    if value is None or type(value) in {bool, int, float, str, bytes}:
        return ("SCALAR", type(value), value)
    if type(value) is types.FunctionType:
        marker = id(value)
        if marker in active:
            return ("FUNCTION_CYCLE", value, value.__code__)
        active.add(marker)
        try:
            closure = tuple(
                (id(cell), recurse(cell.cell_contents, active))
                for cell in (value.__closure__ or ()))
            return (
                "FUNCTION", value, value.__code__,
                recurse(value.__defaults__, active),
                recurse(value.__kwdefaults__, active),
                closure,
            )
        finally:
            active.remove(marker)
    if type(value) is types.MethodType:
        return (
            "METHOD", value, value.__self__, value.__func__,
            getattr(value.__func__, "__code__", None),
        )
    if isinstance(value, type):
        return ("CLASS", value)
    marker = id(value)
    if marker in active:
        return ("CYCLE", type(value), marker)
    if isinstance(value, dict) or type(value) is types.MappingProxyType:
        active.add(marker)
        try:
            entries = tuple(
                (recurse(key, active), recurse(item, active))
                for key, item in sorted(
                    value.items(),
                    key=lambda pair: (
                        type(pair[0]).__module__,
                        type(pair[0]).__qualname__,
                        repr(pair[0]),
                    ),
                )
            )
            return ("MAPPING", type(value), marker, entries)
        finally:
            active.remove(marker)
    if type(value) in {list, tuple}:
        active.add(marker)
        try:
            return (
                "SEQUENCE", type(value), marker,
                tuple(recurse(item, active) for item in value),
            )
        finally:
            active.remove(marker)
    if type(value) in {set, frozenset}:
        active.add(marker)
        try:
            states = [recurse(item, active) for item in value]
            states.sort(key=repr)
            return ("SET", type(value), marker, tuple(states))
        finally:
            active.remove(marker)
    return ("IDENTITY", type(value), marker)


def _dependant_graph_state(dependant, active: set[int] | None = None):
    if dependant is None:
        return None
    active = set() if active is None else active
    marker = id(dependant)
    if marker in active:
        return ("DEPENDANT_CYCLE", type(dependant), marker)
    active.add(marker)
    try:
        graph_value = _RETAINED_API_GRAPH_VALUE_STATE
        dependant_state = _RETAINED_API_DEPENDANT_GRAPH_STATE
        return (
            type(dependant), marker,
            graph_value(getattr(dependant, "call", None)),
            graph_value(getattr(dependant, "name", None)),
            graph_value(getattr(dependant, "path", None)),
            graph_value(getattr(dependant, "use_cache", None)),
            graph_value(getattr(dependant, "cache_key", None)),
            tuple(
                dependant_state(child, active)
                for child in getattr(dependant, "dependencies", ())
            ),
        )
    finally:
        active.remove(marker)


def _route_graph_state(route):
    route_type = type(route)
    route_call = getattr(route_type, "__call__", None)
    route_matches = getattr(route_type, "matches", None)
    route_handle = getattr(route_type, "handle", None)
    path_regex = getattr(route, "path_regex", None)
    graph_value = _RETAINED_API_GRAPH_VALUE_STATE
    dependant_state = _RETAINED_API_DEPENDANT_GRAPH_STATE
    return (
        route_type, id(route), route_call,
        getattr(route_call, "__code__", None),
        route_matches, getattr(route_matches, "__code__", None),
        route_handle, getattr(route_handle, "__code__", None),
        graph_value(getattr(route, "path", None)),
        graph_value(getattr(route, "name", None)),
        graph_value(getattr(route, "methods", None)),
        graph_value(getattr(route, "status_code", None)),
        type(path_regex), id(path_regex),
        graph_value(getattr(path_regex, "pattern", None)),
        graph_value(getattr(path_regex, "flags", None)),
        graph_value(getattr(route, "endpoint", None)),
        graph_value(getattr(route, "app", None)),
        dependant_state(getattr(route, "dependant", None)),
        graph_value(getattr(route, "response_class", None)),
    )


def _middleware_graph_state(root, router):
    graph_value = _RETAINED_API_GRAPH_VALUE_STATE
    layers = []
    current = root
    seen = set()
    while current is not None:
        marker = id(current)
        if marker in seen:
            layers.append(("CYCLE", type(current), marker))
            break
        seen.add(marker)
        if current is router:
            layers.append(("ROUTER", type(router), marker))
            break
        current_type = type(current)
        call = getattr(current_type, "__call__", None)
        fields = tuple(
            (name, graph_value(value))
            for name, value in sorted(vars(current).items())
            if name != "app"
        )
        layers.append((
            current_type, marker, call, getattr(call, "__code__", None), fields,
        ))
        current = getattr(current, "app", None)
    return tuple(layers)


def _application_graph_state(app: FastAPI):
    graph_value = _RETAINED_API_GRAPH_VALUE_STATE
    route_state = _RETAINED_API_ROUTE_GRAPH_STATE
    middleware_state = _RETAINED_API_MIDDLEWARE_GRAPH_STATE
    app_call = getattr(type(app), "__call__", None)
    router = app.router
    router_call = getattr(type(router), "__call__", None)
    return (
        type(app), id(app), app_call, getattr(app_call, "__code__", None),
        type(router), id(router), router_call,
        getattr(router_call, "__code__", None),
        graph_value(router.redirect_slashes),
        graph_value(router.middleware_stack),
        graph_value(router.default),
        graph_value(app.user_middleware),
        graph_value(app.exception_handlers),
        graph_value(app.dependency_overrides),
        graph_value(vars(app.state)),
        tuple(route_state(route) for route in router.routes),
        middleware_state(app.middleware_stack, router),
    )


def _validate_receipted_messages(
        messages: tuple[dict, ...], bundle_digest: str, method: str) -> bool:
    message_types = tuple(message.get("type") for message in messages)
    if (not messages
            or type(message_types[0]) is not str
            or message_types[0] != "http.response.start"
            or any(type(value) is not str or value != "http.response.body"
                   for value in message_types[1:])):
        return False
    starts = messages[:1]
    bodies = messages[1:]
    if not bodies:
        return False
    status = starts[0].get("status")
    if type(status) is not int or not 100 <= status <= 599:
        return False
    more_body = tuple(message.get("more_body", False) for message in bodies)
    if (any(type(value) is not bool for value in more_body)
            or more_body[-1] is not False
            or any(value is False for value in more_body[:-1])):
        return False
    try:
        body = b"".join(bytes(message.get("body", b"")) for message in bodies)
        header_pairs = tuple(starts[0].get("headers", ()))
        headers: dict[bytes, list[bytes]] = {}
        for name, value in header_pairs:
            headers.setdefault(bytes(name).lower(), []).append(bytes(value))
        protected = (
            b"content-type",
            b"x-ofarm-runtime-bundle-digest",
            b"x-ofarm-receipt-payload-digest",
            b"x-ofarm-receipt-canonicalization",
        )
        if any(len(headers.get(name, ())) != 1 for name in protected):
            return False
        is_head = method == "HEAD"
        if is_head:
            if body or headers.get(b"content-length"):
                return False
        elif (len(headers.get(b"content-length", ())) != 1
              or headers[b"content-length"][0] != str(len(body)).encode("ascii")):
            return False
        if (headers[b"content-type"][0] != b"application/json; charset=utf-8"
                or headers[b"x-ofarm-runtime-bundle-digest"][0] !=
                bundle_digest.encode("ascii")
                or headers[b"x-ofarm-receipt-payload-digest"][0] !=
                _RECEIPT_SHA256_BYTES(body).encode("ascii")
                or headers[b"x-ofarm-receipt-canonicalization"][0] !=
                (RAW_CANONICALIZATION if is_head else JSON_CANONICALIZATION).encode(
                    "ascii")):
            return False
        if not is_head:
            decoded = _RECEIPT_JSON_LOADS(body)
            if _RECEIPT_CANONICAL_JSON(decoded).encode("utf-8") != body:
                return False
        return True
    except (KeyError, TypeError, ValueError, UnicodeError,
            _RECEIPT_JSON_DECODE_ERROR):
        return False


_RETAINED_API_GRAPH_VALUE_STATE = _graph_value_state
_RETAINED_API_DEPENDANT_GRAPH_STATE = _dependant_graph_state
_RETAINED_API_ROUTE_GRAPH_STATE = _route_graph_state
_RETAINED_API_MIDDLEWARE_GRAPH_STATE = _middleware_graph_state
_RETAINED_API_APPLICATION_GRAPH_STATE = _application_graph_state
_RETAINED_API_WIRE_VALIDATOR = _validate_receipted_messages
_API_GRAPH_HELPER_ANCHORS = (
    (("_graph_value_state", "_RETAINED_API_GRAPH_VALUE_STATE"),
     _RETAINED_API_GRAPH_VALUE_STATE,
     _RETAINED_API_GRAPH_VALUE_STATE.__code__),
    (("_dependant_graph_state", "_RETAINED_API_DEPENDANT_GRAPH_STATE"),
     _RETAINED_API_DEPENDANT_GRAPH_STATE,
     _RETAINED_API_DEPENDANT_GRAPH_STATE.__code__),
    (("_route_graph_state", "_RETAINED_API_ROUTE_GRAPH_STATE"),
     _RETAINED_API_ROUTE_GRAPH_STATE,
     _RETAINED_API_ROUTE_GRAPH_STATE.__code__),
    (("_middleware_graph_state", "_RETAINED_API_MIDDLEWARE_GRAPH_STATE"),
     _RETAINED_API_MIDDLEWARE_GRAPH_STATE,
     _RETAINED_API_MIDDLEWARE_GRAPH_STATE.__code__),
    (("_application_graph_state", "_RETAINED_API_APPLICATION_GRAPH_STATE"),
     _RETAINED_API_APPLICATION_GRAPH_STATE,
     _RETAINED_API_APPLICATION_GRAPH_STATE.__code__),
    (("_validate_receipted_messages", "_RETAINED_API_WIRE_VALIDATOR"),
     _RETAINED_API_WIRE_VALIDATOR,
     _RETAINED_API_WIRE_VALIDATOR.__code__),
    (("_RECEIPT_CANONICAL_JSON",), _RECEIPT_CANONICAL_JSON,
     _RECEIPT_CANONICAL_JSON_CODE),
    (("_RECEIPT_SHA256_BYTES",), _RECEIPT_SHA256_BYTES,
     _RECEIPT_SHA256_BYTES_CODE),
    (("_RECEIPT_JSON_LOADS",), _RECEIPT_JSON_LOADS,
     _RECEIPT_JSON_LOADS_CODE),
)


def _require_api_graph_helpers(
        anchors, expected_guard, expected_guard_code) -> None:
    """Reject changes to any helper used by the outer ASGI receipt boundary."""
    if (globals().get("_require_api_graph_helpers") is not expected_guard
            or globals().get("_RETAINED_API_GRAPH_HELPER_GUARD") is not
            expected_guard
            or expected_guard.__code__ is not expected_guard_code
            or any(
                function.__code__ is not code
                or any(globals().get(name) is not function for name in names)
                for names, function, code in anchors)):
        raise RuntimeError("HTTP receipt graph helpers changed after startup")


_RETAINED_API_GRAPH_HELPER_GUARD = _require_api_graph_helpers
_RETAINED_API_GRAPH_HELPER_GUARD_CODE = _require_api_graph_helpers.__code__


class _FrozenApplicationType(type):
    def __setattr__(cls, name, value):
        del cls, name, value
        raise TypeError("receipted ASGI boundary class is immutable")

    def __delattr__(cls, name):
        del cls, name
        raise TypeError("receipted ASGI boundary class is immutable")


class _ReceiptedApplication(metaclass=_FrozenApplicationType):
    __slots__ = (
        "__app", "__bundle_digest", "__capture_graph", "__validate_wire",
        "__route_state", "__graph_value", "__helper_anchors",
        "__guard_helpers", "__guard_helpers_code",
        "__build_middleware_stack", "__build_middleware_stack_code",
        "__initial_routes", "__initial_handlers", "__graph_state",
        "__sealed", "__error_body", "__error_headers",
        "__head_error_headers",
    )

    def __init__(self, app: FastAPI, bundle_digest: str):
        helper_anchors = _API_GRAPH_HELPER_ANCHORS
        guard_helpers = _RETAINED_API_GRAPH_HELPER_GUARD
        guard_helpers_code = _RETAINED_API_GRAPH_HELPER_GUARD_CODE
        guard_helpers(helper_anchors, guard_helpers, guard_helpers_code)
        capture_graph = _RETAINED_API_APPLICATION_GRAPH_STATE
        validate_wire = _RETAINED_API_WIRE_VALIDATOR
        route_state = _RETAINED_API_ROUTE_GRAPH_STATE
        graph_value = _RETAINED_API_GRAPH_VALUE_STATE
        build_middleware_stack = type(app).build_middleware_stack
        object.__setattr__(self, "_ReceiptedApplication__app", app)
        object.__setattr__(
            self, "_ReceiptedApplication__bundle_digest", bundle_digest)
        object.__setattr__(
            self, "_ReceiptedApplication__capture_graph",
            capture_graph)
        object.__setattr__(
            self, "_ReceiptedApplication__validate_wire",
            validate_wire)
        object.__setattr__(
            self, "_ReceiptedApplication__route_state", route_state)
        object.__setattr__(
            self, "_ReceiptedApplication__graph_value", graph_value)
        object.__setattr__(
            self, "_ReceiptedApplication__helper_anchors", helper_anchors)
        object.__setattr__(
            self, "_ReceiptedApplication__guard_helpers", guard_helpers)
        object.__setattr__(
            self, "_ReceiptedApplication__guard_helpers_code",
            guard_helpers_code)
        object.__setattr__(
            self, "_ReceiptedApplication__build_middleware_stack",
            build_middleware_stack)
        object.__setattr__(
            self, "_ReceiptedApplication__build_middleware_stack_code",
            build_middleware_stack.__code__)
        object.__setattr__(
            self, "_ReceiptedApplication__initial_routes",
            tuple(route_state(route) for route in app.router.routes))
        object.__setattr__(
            self, "_ReceiptedApplication__initial_handlers",
            graph_value(app.exception_handlers))
        object.__setattr__(self, "_ReceiptedApplication__graph_state", None)
        object.__setattr__(self, "_ReceiptedApplication__sealed", False)
        error_body = _RECEIPT_CANONICAL_JSON(
            {"detail": "Internal Server Error"}).encode("utf-8")
        common = (
            (b"content-type", b"application/json; charset=utf-8"),
            (b"x-ofarm-runtime-bundle-digest", bundle_digest.encode("ascii")),
        )
        object.__setattr__(
            self, "_ReceiptedApplication__error_body", error_body)
        object.__setattr__(
            self, "_ReceiptedApplication__error_headers",
            (*common,
             (b"content-length", str(len(error_body)).encode("ascii")),
             (b"x-ofarm-receipt-payload-digest",
              _RECEIPT_SHA256_BYTES(error_body).encode("ascii")),
             (b"x-ofarm-receipt-canonicalization",
              JSON_CANONICALIZATION.encode("ascii"))),
        )
        object.__setattr__(
            self, "_ReceiptedApplication__head_error_headers",
            (*common,
             (b"x-ofarm-receipt-payload-digest",
              _RECEIPT_SHA256_BYTES(b"").encode("ascii")),
             (b"x-ofarm-receipt-canonicalization",
              RAW_CANONICALIZATION.encode("ascii"))),
        )

    def __setattr__(self, name, value):
        del self, name, value
        raise AttributeError("receipted ASGI boundary is immutable")

    def __delattr__(self, name):
        del self, name
        raise AttributeError("receipted ASGI boundary is immutable")

    def __getattr__(self, name):
        app = object.__getattribute__(self, "_ReceiptedApplication__app")
        return getattr(app, name)

    def _seal(self) -> None:
        guard = object.__getattribute__(
            self, "_ReceiptedApplication__guard_helpers")
        anchors = object.__getattribute__(
            self, "_ReceiptedApplication__helper_anchors")
        guard_code = object.__getattribute__(
            self, "_ReceiptedApplication__guard_helpers_code")
        guard(anchors, guard, guard_code)
        if object.__getattribute__(self, "_ReceiptedApplication__sealed"):
            return
        app = object.__getattribute__(self, "_ReceiptedApplication__app")
        route_state = object.__getattribute__(
            self, "_ReceiptedApplication__route_state")
        graph_value = object.__getattribute__(
            self, "_ReceiptedApplication__graph_value")
        initial_routes = object.__getattribute__(
            self, "_ReceiptedApplication__initial_routes")
        current_routes = tuple(app.router.routes)
        if (len(current_routes) < len(initial_routes)
                or tuple(route_state(route)
                         for route in current_routes[:len(initial_routes)]) !=
                initial_routes
                or app.user_middleware
                or app.dependency_overrides
                or graph_value(app.exception_handlers) !=
                object.__getattribute__(
                    self, "_ReceiptedApplication__initial_handlers")):
            raise RuntimeError("HTTP application graph changed before sealing")
        if app.middleware_stack is None:
            build = object.__getattribute__(
                self, "_ReceiptedApplication__build_middleware_stack")
            build_code = object.__getattribute__(
                self, "_ReceiptedApplication__build_middleware_stack_code")
            if (type(app).build_middleware_stack is not build
                    or build.__code__ is not build_code):
                raise RuntimeError(
                    "HTTP middleware builder changed before sealing")
            app.middleware_stack = build(app)
        app.router.redirect_slashes = False
        app.router.routes = tuple(current_routes)
        app.user_middleware = ()
        app.dependency_overrides = types.MappingProxyType({})
        app.exception_handlers = types.MappingProxyType(
            dict(app.exception_handlers))
        capture = object.__getattribute__(
            self, "_ReceiptedApplication__capture_graph")
        object.__setattr__(
            self, "_ReceiptedApplication__graph_state", capture(app))
        guard(anchors, guard, guard_code)
        object.__setattr__(self, "_ReceiptedApplication__sealed", True)

    def _require_graph(self) -> None:
        guard = object.__getattribute__(
            self, "_ReceiptedApplication__guard_helpers")
        anchors = object.__getattribute__(
            self, "_ReceiptedApplication__helper_anchors")
        guard_code = object.__getattribute__(
            self, "_ReceiptedApplication__guard_helpers_code")
        guard(anchors, guard, guard_code)
        app = object.__getattribute__(self, "_ReceiptedApplication__app")
        capture = object.__getattribute__(
            self, "_ReceiptedApplication__capture_graph")
        current = capture(app)
        guard(anchors, guard, guard_code)
        if current != object.__getattribute__(
                self, "_ReceiptedApplication__graph_state"):
            raise RuntimeError("HTTP application graph changed after sealing")

    async def _send_emergency(self, send, *, head: bool) -> None:
        headers = object.__getattribute__(
            self,
            ("_ReceiptedApplication__head_error_headers" if head
             else "_ReceiptedApplication__error_headers"),
        )
        body = b"" if head else object.__getattribute__(
            self, "_ReceiptedApplication__error_body")
        await send({
            "type": "http.response.start", "status": 500,
            "headers": list(headers),
        })
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") == "lifespan":
            self._seal()
            app = object.__getattribute__(self, "_ReceiptedApplication__app")
            await app(scope, receive, send)
            return
        if scope.get("type") != "http":
            await self._send_emergency(send, head=False)
            return
        head = scope.get("method") == "HEAD"
        try:
            self._seal()
            self._require_graph()
            messages = []

            async def capture_send(message):
                copied = dict(message)
                if "headers" in copied:
                    copied["headers"] = [
                        (bytes(name), bytes(value))
                        for name, value in copied["headers"]
                    ]
                if "body" in copied:
                    copied["body"] = bytes(copied["body"])
                messages.append(copied)

            app = object.__getattribute__(self, "_ReceiptedApplication__app")
            await app(scope, receive, capture_send)
            self._require_graph()
            selected = tuple(messages)
            validator = object.__getattribute__(
                self, "_ReceiptedApplication__validate_wire")
            guard = object.__getattribute__(
                self, "_ReceiptedApplication__guard_helpers")
            anchors = object.__getattribute__(
                self, "_ReceiptedApplication__helper_anchors")
            guard_code = object.__getattribute__(
                self, "_ReceiptedApplication__guard_helpers_code")
            guard(anchors, guard, guard_code)
            if not validator(
                    selected,
                    object.__getattribute__(
                        self, "_ReceiptedApplication__bundle_digest"),
                    scope.get("method", "")):
                raise RuntimeError("HTTP response is not exactly receipted")
            guard(anchors, guard, guard_code)
        except Exception:
            await self._send_emergency(send, head=head)
            return
        for message in selected:
            await send(message)


_RECEIPTED_APPLICATION_CALLABLES = tuple(
    value for value in vars(_ReceiptedApplication).values()
    if type(value) is types.FunctionType
)


class CommitBody(BaseModel):
    submission: dict


class FreezeBody(BaseModel):
    farmRef: str
    windowStart: str
    windowEnd: str


class ReviewContestBody(BaseModel):
    farmRef: str
    # the in-force AcceptedEventConsequence being disputed (not an assertion)
    consequenceRef: str
    rationale: str
    evidenceRefs: list[str] = []
    idempotencyKey: str | None = None


class ReviewAcceptBody(BaseModel):
    farmRef: str
    assertionRef: str
    # acceptance is a governed RESOLUTION, never a bare pointer: the
    # rationale is mandatory, and routed insufficiencies additionally
    # require reviewer-attached durable evidence (gate-enforced)
    rationale: str
    evidenceRefs: list[str] = []
    idempotencyKey: str | None = None


def create_app(
        store: Store | None = None, *, oidc=_FROM_ENV) -> _ReceiptedApplication:
    app = FastAPI(
        title="OFARM2 Kernel (M1)",
        description="Implementation and conformance packaging profile — not OFARM "
                    "law. Claims record-keeping completeness only; never "
                    "current-compliance, certification, or production readiness.",
        version="m1.0",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
        redirect_slashes=False,
    )
    bound_store = store if store is not None else _STORE_TYPE()
    if type(bound_store) is not _STORE_TYPE:
        raise TypeError("create_app requires an exact Store instance")
    bound_store.migrate()
    context.bootstrap(bound_store)
    bound_runtime_bundle = _STORE_RUNTIME_BUNDLE(bound_store)
    bound_runtime_bundle_digest = bound_runtime_bundle.digest
    bound_pipeline = _GATE_PIPELINE_TYPE(bound_store)
    bound_outputs = _OUTPUT_GENERATOR_TYPE(bound_store)
    bound_oidc = config.oidc_config_from_env() if oidc is _FROM_ENV else oidc
    if bound_oidc is not None and type(bound_oidc) is not _OIDC_CONFIG_TYPE:
        raise TypeError("oidc must be None or an exact OidcConfig instance")
    bound_oidc_state = (
        None if bound_oidc is None else _EXACT_OIDC_CONFIG_STATE(bound_oidc))

    app.state.store = bound_store
    app.state.pipeline = bound_pipeline
    app.state.outputs = bound_outputs
    app.state.oidc = bound_oidc

    # Capture the retained dispatch and type anchors in application closures.
    # Store.bind_application_callables() seals those closure bindings after all
    # routes have been registered.
    function_type = _FUNCTION_TYPE
    store_type = _STORE_TYPE
    pipeline_type = _GATE_PIPELINE_TYPE
    output_type = _OUTPUT_GENERATOR_TYPE
    authority_type = _AUTHORITY_EVALUATOR_TYPE
    oidc_type = _OIDC_CONFIG_TYPE
    exact_oidc_config_state = _EXACT_OIDC_CONFIG_STATE
    exact_oidc_config_state_code = _EXACT_OIDC_CONFIG_STATE_CODE
    runtime_bundle_type = RuntimeBundle
    gate_commit = _GATE_COMMIT
    gate_commit_code = _GATE_COMMIT_CODE
    output_assert_runtime_composition = _OUTPUT_ASSERT_RUNTIME_COMPOSITION
    output_assert_runtime_composition_code = \
        _OUTPUT_ASSERT_RUNTIME_COMPOSITION_CODE
    output_passport_view = _OUTPUT_PASSPORT_VIEW
    output_passport_view_code = _OUTPUT_PASSPORT_VIEW_CODE
    output_freeze_inspection_register = _OUTPUT_FREEZE_INSPECTION_REGISTER
    output_freeze_inspection_register_code = \
        _OUTPUT_FREEZE_INSPECTION_REGISTER_CODE
    authority_evaluate_read = _AUTHORITY_EVALUATE_READ
    authority_evaluate_read_code = _AUTHORITY_EVALUATE_READ_CODE
    authority_decision_allowed_fn = _AUTHORITY_DECISION_ALLOWED
    authority_decision_allowed_code = _AUTHORITY_DECISION_ALLOWED_CODE
    oidc_verify = _OIDC_VERIFY
    oidc_verify_code = _OIDC_VERIFY_CODE
    oidc_runtime_guard = _OIDC_RUNTIME_GUARD
    oidc_runtime_guard_code = _OIDC_RUNTIME_GUARD_CODE
    store_require_transaction_posture = _STORE_REQUIRE_TRANSACTION_POSTURE
    store_require_transaction_posture_code = \
        _STORE_REQUIRE_TRANSACTION_POSTURE_CODE
    store_require_dispatch = _STORE_REQUIRE_DISPATCH
    store_require_dispatch_code = _STORE_REQUIRE_DISPATCH_CODE
    store_runtime_bundle = _STORE_RUNTIME_BUNDLE
    store_runtime_bundle_code = _STORE_RUNTIME_BUNDLE_CODE
    store_get_record = _STORE_GET_RECORD
    store_get_record_code = _STORE_GET_RECORD_CODE
    store_insert_record = _STORE_INSERT_RECORD
    store_insert_record_code = _STORE_INSERT_RECORD_CODE
    store_unreachable_records = _STORE_UNREACHABLE_RECORDS
    store_unreachable_records_code = _STORE_UNREACHABLE_RECORDS_CODE
    store_tx = _STORE_TX
    store_tx_code = _STORE_TX_CODE
    store_serialized_tx = _STORE_SERIALIZED_TX
    store_serialized_tx_code = _STORE_SERIALIZED_TX_CODE
    runtime_bundle_json_component = _RUNTIME_BUNDLE_JSON_COMPONENT
    runtime_bundle_json_component_code = \
        _RUNTIME_BUNDLE_JSON_COMPONENT_CODE
    receipt_normalizer = _RETAINED_RECEIPT_NORMALIZER
    receipt_normalizer_code = _RETAINED_RECEIPT_NORMALIZER_CODE
    receipt_canonical_json = _RECEIPT_CANONICAL_JSON
    receipt_canonical_json_code = _RECEIPT_CANONICAL_JSON_CODE
    receipt_sha256_bytes = _RECEIPT_SHA256_BYTES
    receipt_sha256_bytes_code = _RECEIPT_SHA256_BYTES_CODE
    receipt_response_type = _RECEIPT_RESPONSE_TYPE
    receipt_response_call = _RECEIPT_RESPONSE_CALL
    receipt_response_call_code = _RECEIPT_RESPONSE_CALL_CODE
    retained_runtime_problem = _RETAINED_RUNTIME_PROBLEM
    retained_runtime_problem_code = _RETAINED_RUNTIME_PROBLEM_CODE
    retained_http_exception_type = _RETAINED_HTTP_EXCEPTION_TYPE
    retained_oidc_error_type = _RETAINED_OIDC_ERROR_TYPE
    receipt_json_canonicalization = JSON_CANONICALIZATION
    receipt_raw_canonicalization = RAW_CANONICALIZATION

    def _require_application_bindings() -> None:
        """Reject mutable application-state or service-composition swaps."""
        store_callables = (
            (store_require_dispatch, store_require_dispatch_code),
            (store_require_transaction_posture,
             store_require_transaction_posture_code),
            (store_runtime_bundle, store_runtime_bundle_code),
            (store_get_record, store_get_record_code),
            (store_insert_record, store_insert_record_code),
            (store_unreachable_records, store_unreachable_records_code),
            (store_tx, store_tx_code),
            (store_serialized_tx, store_serialized_tx_code),
            (runtime_bundle_json_component,
             runtime_bundle_json_component_code),
            (exact_oidc_config_state, exact_oidc_config_state_code),
            (oidc_runtime_guard, oidc_runtime_guard_code),
            (authority_decision_allowed_fn,
             authority_decision_allowed_code),
            (receipt_normalizer, receipt_normalizer_code),
            (receipt_canonical_json, receipt_canonical_json_code),
            (receipt_sha256_bytes, receipt_sha256_bytes_code),
            (receipt_response_call, receipt_response_call_code),
            (retained_runtime_problem, retained_runtime_problem_code),
        )
        if (any(type(function) is not function_type
                or function.__code__ is not code
                for function, code in store_callables)
                or type(bound_store) is not store_type
                or type(bound_pipeline) is not pipeline_type
                or type(bound_outputs) is not output_type
                or receipt_response_type is not _RECEIPT_RESPONSE_TYPE
                or receipt_response_type.__call__ is not receipt_response_call
                or receipt_response_call.__code__ is not
                receipt_response_call_code
                or receipt_json_canonicalization != JSON_CANONICALIZATION
                or receipt_raw_canonicalization != RAW_CANONICALIZATION
                or (bound_oidc is not None and type(bound_oidc) is not oidc_type)
                or (None if bound_oidc is None else
                    exact_oidc_config_state(bound_oidc)) != bound_oidc_state
                or app.state.store is not bound_store
                or app.state.pipeline is not bound_pipeline
                or app.state.outputs is not bound_outputs
                or app.state.oidc is not bound_oidc
                or bound_pipeline.store is not bound_store
                or bound_outputs.store is not bound_store
                or type(bound_pipeline.authority) is not authority_type
                or bound_pipeline.authority.store is not bound_store
                or type(bound_outputs.authority) is not authority_type
                or bound_outputs.authority.store is not bound_store):
            raise RuntimeError(
                "HTTP application runtime composition changed after startup")
        if (store_runtime_bundle(bound_store) is not bound_runtime_bundle
                or bound_runtime_bundle.digest !=
                bound_runtime_bundle_digest):
            raise RuntimeError(
                "HTTP application RuntimeBundle changed after startup")
        if bound_oidc is not None:
            oidc_runtime_guard(bound_oidc)
        store_require_dispatch(bound_store)
        store_require_transaction_posture(bound_store)
        if any(function.__code__ is not code
               for function, code in store_callables):
            raise RuntimeError(
                "HTTP Store runtime dispatch changed during posture check")

    def _invoke_retained_method(
            function, code, receiver, receiver_type, /, *args, **kwargs):
        """Invoke one exact startup-selected method with adjacent guards."""
        _require_application_bindings()
        if (type(receiver) is not receiver_type
                or type(function) is not function_type
                or function.__code__ is not code):
            raise RuntimeError(
                "HTTP application runtime dispatch changed after startup")
        try:
            return function(receiver, *args, **kwargs)
        finally:
            if (type(function) is not function_type
                    or function.__code__ is not code):
                raise RuntimeError(
                    "HTTP application runtime dispatch changed during request")
            _require_application_bindings()

    def _deny(title: str, detail: str, pid: str):
        raise retained_http_exception_type(
            status_code=401, detail=retained_runtime_problem(
            "AUTHORITY_DENIED", title, detail, problem_id=pid))

    def get_principal(authorization: str | None = Header(None),
                      x_acting_party: str | None = Header(None)) -> str:
        """The transport principal (a recorded, ACTIVE Party ref). With OIDC
        configured (M2 G4) it comes ONLY from a verified bearer token; otherwise the
        development/conformance X-Acting-Party header IS the principal (NOT production
        auth — profile_si_ffs/UNSUPPORTED_SURFACES.md). Either way the binding
        contract is identical, an absent/invalid principal is a default-deny refusal,
        and the principal must resolve to a recorded active Party — an issuer subject
        that is not a known active party never becomes a principal (no public-artifact
        read by an arbitrary token subject, PR #16 hostile B3)."""
        _require_application_bindings()
        if bound_oidc is None:
            if not x_acting_party:
                _deny("No transport principal",
                      "no X-Acting-Party principal presented; default deny",
                      "problem:api-no-principal")
            principal = x_acting_party
        else:
            if not authorization or not authorization.lower().startswith("bearer "):
                _deny("No bearer token",
                      "no Authorization: Bearer token presented; default deny (the "
                      "X-Acting-Party header does not authenticate when OIDC is enabled)",
                      "problem:api-no-token")
            try:
                principal = _invoke_retained_method(
                    oidc_verify,
                    oidc_verify_code,
                    bound_oidc,
                    oidc_type,
                    authorization.split(" ", 1)[1].strip(),
                )["partyRef"]
            except retained_oidc_error_type as exc:
                _deny("Token verification failed", str(exc), "problem:api-token-invalid")
        rec = _invoke_retained_method(
            store_get_record, store_get_record_code,
            bound_store, store_type, principal)
        if (rec is None or rec["record_kind"] != "ofarm.party.v0.1"
                or rec["payload"].get("partyState") != "ACTIVE"):
            _deny("Principal is not an active Party",
                  f"the transport principal {principal} is not a recorded active Party; "
                  "default deny", "problem:api-principal-not-party")
        return principal

    app.state.get_principal = get_principal

    def _receipt(
            payload: object, *, status_code: int = 200,
            headers: dict[str, str] | None = None,
            head_request: bool = False) -> Response:
        """Emit, hash, and return one exact canonical JSON byte sequence.

        Returning a Response (rather than a Python object) is intentional:
        FastAPI must not perform a second Pydantic/JSON encoding pass after the
        receipt digest has been calculated. HTTP never delivers a response body
        for HEAD, so a handled HEAD error explicitly emits and hashes empty
        exact bytes instead of hashing the suppressed JSON representation.
        """
        _require_application_bindings()
        encoded_payload = receipt_normalizer(payload)
        canonical_bytes = receipt_canonical_json(encoded_payload).encode("utf-8")
        delivered_bytes = b"" if head_request else canonical_bytes
        protected_headers = {
            "content-length",
            "content-type",
            "x-ofarm-runtime-bundle-digest",
            "x-ofarm-receipt-payload-digest",
            "x-ofarm-receipt-canonicalization",
        }
        raw_headers = []
        for name, value in (headers or {}).items():
            if type(name) is not str or type(value) is not str:
                raise TypeError("receipt response headers must be exact strings")
            lowered = name.lower()
            if lowered not in protected_headers:
                raw_headers.append((
                    lowered.encode("latin-1"), value.encode("latin-1")))
        if not head_request:
            raw_headers.append((b"content-length", str(len(delivered_bytes)).encode()))
        raw_headers.extend((
            (b"content-type", b"application/json; charset=utf-8"),
            (b"x-ofarm-runtime-bundle-digest",
             bound_runtime_bundle_digest.encode("ascii")),
            (b"x-ofarm-receipt-payload-digest",
             receipt_sha256_bytes(delivered_bytes).encode("ascii")),
            (b"x-ofarm-receipt-canonicalization",
             (receipt_raw_canonicalization if head_request
              else receipt_json_canonicalization).encode("ascii")),
        ))
        # Build the exact Starlette carrier state directly. Response.__init__,
        # render(), init_headers(), and MutableHeaders are not part of the
        # integrity boundary; only the retained ASGI sender is used.
        response = object.__new__(receipt_response_type)
        object.__setattr__(response, "status_code", status_code)
        object.__setattr__(response, "body", delivered_bytes)
        object.__setattr__(response, "raw_headers", raw_headers)
        object.__setattr__(response, "background", None)
        _require_application_bindings()
        return response

    @app.exception_handler(StarletteHTTPException)
    async def receipted_http_exception(
            request: Request, exc: StarletteHTTPException):
        return _receipt(
            {"detail": exc.detail},
            status_code=exc.status_code,
            headers=dict(exc.headers or {}),
            head_request=request.method == "HEAD",
        )

    @app.exception_handler(RequestValidationError)
    async def receipted_validation_exception(
            request: Request, exc: RequestValidationError):
        return _receipt(
            {"detail": exc.errors()},
            status_code=422,
            head_request=request.method == "HEAD",
        )

    @app.exception_handler(Exception)
    async def receipted_unhandled_exception(
            request: Request, exc: Exception):
        # Unexpected implementation failures still cross the governed HTTP
        # boundary as exact receipted bytes.  Never expose exception text or a
        # traceback to the caller; operational logging remains the server's
        # responsibility.
        del exc
        return _receipt(
            {"detail": "Internal Server Error"},
            status_code=500,
            head_request=request.method == "HEAD",
        )

    @app.get("/health")
    def health():
        _require_application_bindings()
        return _receipt({
            "status": "ok",
            "unreachableAuthoritativeRecords":
                _invoke_retained_method(
                    store_unreachable_records,
                    store_unreachable_records_code,
                    bound_store,
                    store_type,
                ),
        })

    @app.post("/commit")
    def commit(body: CommitBody, principal: str = Depends(get_principal)):
        # The transport principal binds to the submitted actor BEFORE the
        # pipeline runs: a body-supplied actingPartyRef is never trusted on its
        # own (hostile review blocker 1). The principal is the OIDC-verified Party
        # when OIDC is configured (M2 G4), else the development/conformance
        # X-Acting-Party header (UNSUPPORTED_SURFACES.md) — the binding contract is
        # identical: the gate's actor is the transport's actor, or it is refused.
        if body.submission.get("actingPartyRef") != principal:
            # full RuntimeProblem shape even at the transport edge; the fixed
            # problemId keeps these pre-pipeline refusals off the in-pipeline
            # problem counter
            raise HTTPException(status_code=403, detail=runtime_problem(
                "ACTOR_BINDING_UNRESOLVED", "Transport principal mismatch",
                "submission.actingPartyRef does not match the transport "
                "principal; body-level actor spoofing is refused",
                problem_id="problem:api-principal-mismatch"))
        try:
            return _receipt(_invoke_retained_method(
                gate_commit,
                gate_commit_code,
                bound_pipeline,
                pipeline_type,
                body.submission,
            ))
        except (ContractViolation, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    # Package-published, non-personal artifacts: readable by any recorded
    # party. Everything else needs an affirmative farm-scoped read path.
    PUBLIC_ARTIFACT_KINDS = frozenset({
        "ofarm.referencesnapshot.v0.1",
        "ofarm.agronomiccodebindingprofile.v0.1",
        "ofarm.packactivationset.v0.1",
        "ofarm.activeartifactset.v0.1",
    })

    def _read_farm_scopes(store, row) -> list[str] | None:
        """Farm scopes governing a record's readability; None = unresolvable.
        Governance/trace records resolve through their declared scope fields
        or their linked records — never default-open."""
        payload = row["payload"]
        farms = [s["scopeRef"] for s in payload.get("anchorScopes", [])
                 if isinstance(s, dict) and s.get("scopeType") == "FARM"]
        for field in ("targetScopes",):
            farms += [s["scopeRef"] for s in payload.get(field, [])
                      if isinstance(s, dict) and s.get("scopeType") == "FARM"]
        ts = payload.get("targetScope")
        if isinstance(ts, dict) and ts.get("scopeType") == "FARM":
            farms.append(ts["scopeRef"])
        tgt = payload.get("target", {})
        if isinstance(tgt, dict):
            sc = tgt.get("scope", {})
            if isinstance(sc, dict) and sc.get("scopeType") == "FARM":
                farms.append(sc["scopeRef"])
        if farms:
            return sorted(set(farms))
        # follow one link hop for boundary records
        for ref_field in ("semanticEventRef", "requestId"):
            ref = payload.get(ref_field)
            if isinstance(ref, str):
                linked = _invoke_retained_method(
                    store_get_record, store_get_record_code,
                    store, store_type, ref)
                if linked is not None and linked["record_id"] != row["record_id"]:
                    resolved = _read_farm_scopes(store, linked)
                    if resolved:
                        return resolved
        return None

    @app.post("/review/accept")
    def review_accept(body: ReviewAcceptBody,
                      principal: str = Depends(get_principal)):
        # the review act is the REVIEWER'S own governed commit: the reviewer
        # IS the transport principal — there is no body-named reviewer field
        # to forge (hostile review blocker 1, second pass)
        submission = {
            "commitClass": "GOVERNANCE_DECISION",
            "ingressChannel": "MANUAL_UI",
            "actingPartyRef": principal,
            "farmRef": body.farmRef,
            "idempotencyKey": body.idempotencyKey
                              or f"review-accept:{uuid.uuid4().hex}",
            "decisionTime": context.now_iso(),
            "reviewTargetAssertionRef": body.assertionRef,
            "reviewRationale": body.rationale,
            "reviewEvidenceRefs": body.evidenceRefs,
            "dominantSemanticConsequence": "review acceptance of a queued claim",
        }
        try:
            return _receipt(_invoke_retained_method(
                gate_commit,
                gate_commit_code,
                bound_pipeline,
                pipeline_type,
                submission,
            ))
        except (ContractViolation, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.post("/review/reject")
    def review_reject(body: ReviewAcceptBody,
                      principal: str = Depends(get_principal)):
        # the reject act is the REVIEWER'S own governed decline under their own
        # transport principal (M2 G5-2). The endpoint supplies the normalized
        # review-decision pair (REVIEW_REJECT_OR_CONTEST / REJECTED) so the client
        # never passes raw outcome values (docs/REVIEW_DISPUTE_SEMANTICS.md §3.1).
        # Authority is the DISTINCT REVIEW_REJECT_OR_CONTEST action — a principal
        # holding only REVIEW_ACCEPT is denied. The rationale is mandatory;
        # supplied evidence is validated like acceptance's.
        submission = {
            "commitClass": "GOVERNANCE_DECISION",
            "ingressChannel": "MANUAL_UI",
            "actingPartyRef": principal,
            "farmRef": body.farmRef,
            "idempotencyKey": body.idempotencyKey
                              or f"review-reject:{uuid.uuid4().hex}",
            "decisionTime": context.now_iso(),
            "reviewTargetAssertionRef": body.assertionRef,
            "reviewAction": "REVIEW_REJECT_OR_CONTEST",
            "decisionOutcomeState": "REJECTED",
            "reviewRationale": body.rationale,
            "reviewEvidenceRefs": body.evidenceRefs,
            "dominantSemanticConsequence": "review rejection of a queued claim",
        }
        try:
            return _receipt(_invoke_retained_method(
                gate_commit,
                gate_commit_code,
                bound_pipeline,
                pipeline_type,
                submission,
            ))
        except (ContractViolation, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.post("/review/contest")
    def review_contest(body: ReviewContestBody,
                       principal: str = Depends(get_principal)):
        # a CONTEST opens an append-only dispute against an ALREADY IN-FORCE
        # consequence under the reviewer's own principal (M2 G5-4). The endpoint
        # supplies the normalized pair (REVIEW_REJECT_OR_CONTEST / CONTESTED) and
        # the target consequence ref; authority is the distinct
        # REVIEW_REJECT_OR_CONTEST action; the consequence is flagged (DISPUTE
        # edge) but never edited, and dependent materializations stale (spec §6).
        submission = {
            "commitClass": "GOVERNANCE_DECISION",
            "ingressChannel": "MANUAL_UI",
            "actingPartyRef": principal,
            "farmRef": body.farmRef,
            "idempotencyKey": body.idempotencyKey
                              or f"review-contest:{uuid.uuid4().hex}",
            "decisionTime": context.now_iso(),
            "reviewTargetConsequenceRef": body.consequenceRef,
            "reviewAction": "REVIEW_REJECT_OR_CONTEST",
            "decisionOutcomeState": "CONTESTED",
            "reviewRationale": body.rationale,
            "reviewEvidenceRefs": body.evidenceRefs,
            "dominantSemanticConsequence": "dispute against an in-force consequence",
        }
        try:
            return _receipt(_invoke_retained_method(
                gate_commit,
                gate_commit_code,
                bound_pipeline,
                pipeline_type,
                submission,
            ))
        except (ContractViolation, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.get("/records/{record_id}")
    def get_record(record_id: str, principal: str = Depends(get_principal)):
        _require_application_bindings()
        not_found = False
        denied = False
        response = None
        with _invoke_retained_method(
                store_serialized_tx, store_serialized_tx_code,
                bound_store, store_type) as cur:
            # The protected row, its farm scope, the revocation-sensitive
            # authority decision, its audit records, and the response receipt
            # all share one serialized snapshot. A revocation cannot commit in
            # the gap between selection and use.
            row = _invoke_retained_method(
                store_get_record, store_get_record_code,
                bound_store, store_type, record_id)
            if row is None:
                not_found = True
            else:
                payload, kind = row["payload"], row["record_kind"]
                if kind == "ofarm.party.v0.1":
                    # A party record is readable by that party alone at this surface.
                    denied = payload["partyId"] != principal
                elif kind not in PUBLIC_ARTIFACT_KINDS:
                    farm_scopes = _read_farm_scopes(bound_store, row)
                    if not farm_scopes:
                        denied = True
                    for farm_ref in farm_scopes:
                        _invoke_retained_method(
                            output_assert_runtime_composition,
                            output_assert_runtime_composition_code,
                            bound_outputs,
                            output_type,
                        )
                        access = _invoke_retained_method(
                            authority_evaluate_read,
                            authority_evaluate_read_code,
                            bound_outputs.authority,
                            authority_type,
                            cur=cur,
                            requesting_party_ref=principal,
                            farm_ref=farm_ref,
                            artifact_family="OTHER",
                        )
                        access_allowed = authority_decision_allowed_fn(access)
                        _invoke_retained_method(
                            store_insert_record, store_insert_record_code,
                            bound_store, store_type, cur, access.request_payload)
                        _invoke_retained_method(
                            store_insert_record, store_insert_record_code,
                            bound_store, store_type, cur, access.trace_payload)
                        _invoke_retained_method(
                            store_insert_record, store_insert_record_code,
                            bound_store, store_type, cur, access.result_payload)
                        if not access_allowed:
                            denied = True
                            break
                if not denied:
                    response = _receipt({
                        "recordId": row["record_id"],
                        "recordKind": row["record_kind"],
                        "schemaHash": row["schema_hash"],
                        "payloadSha256": row["payload_sha256"],
                        "runtimeBundleDigest": row["runtime_bundle_digest"],
                        "recordTime": row["record_time"].isoformat(),
                        "payload": payload,
                    })

        if not_found:
            raise retained_http_exception_type(
                status_code=404, detail="no such record")
        if denied:
            # Default deny; distinguish "exists but permission-limited" from
            # "does not exist" while preserving the committed audit decision.
            raise retained_http_exception_type(
                status_code=403,
                detail=retained_runtime_problem(
                    "PERMISSION_REDACTED", "Read not authorized",
                    "the record exists but you are not authorized to read it",
                    problem_id="problem:api-read-denied",
                ),
            )
        return response

    @app.get("/views/passport/{farm_ref}")
    def passport(farm_ref: str, principal: str = Depends(get_principal)):
        _invoke_retained_method(
            output_assert_runtime_composition,
            output_assert_runtime_composition_code,
            bound_outputs,
            output_type,
        )
        return _receipt(_invoke_retained_method(
            output_passport_view,
            output_passport_view_code,
            bound_outputs,
            output_type,
            farm_ref,
            principal,
        ))

    @app.post("/views/inspection-register/freeze")
    def freeze(body: FreezeBody, principal: str = Depends(get_principal)):
        _invoke_retained_method(
            output_assert_runtime_composition,
            output_assert_runtime_composition_code,
            bound_outputs,
            output_type,
        )
        return _receipt(_invoke_retained_method(
            output_freeze_inspection_register,
            output_freeze_inspection_register_code,
            bound_outputs,
            output_type,
            body.farmRef,
            principal,
            body.windowStart,
            body.windowEnd,
        ))

    @app.get("/manifest")
    def get_manifest():
        _require_application_bindings()
        manifests = [component for component in
                     bound_runtime_bundle.components
                     if component.role == "ACTIVE_MANIFEST"]
        if len(manifests) != 1:
            raise HTTPException(
                status_code=503,
                detail="RuntimeBundle does not contain exactly one active manifest",
            )
        return _receipt(
            _invoke_retained_method(
                runtime_bundle_json_component,
                runtime_bundle_json_component_code,
                bound_runtime_bundle,
                runtime_bundle_type,
                "ACTIVE_MANIFEST",
                manifests[0].logical_ref,
            ),
        )

    wrapped = _ReceiptedApplication(app, bound_runtime_bundle_digest)
    store_type.bind_application_callables(
        bound_store,
        (*_application_callables(app), *_RECEIPTED_APPLICATION_CALLABLES),
    )
    # The returned application is already a complete governed artifact.  Seal
    # its route/dependency/middleware graph before it escapes create_app(); a
    # caller must never be able to append an unbound route in the interval
    # between construction and the first lifespan or HTTP event.
    wrapped._seal()
    return wrapped
