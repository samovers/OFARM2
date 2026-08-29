"""Focused evidence for credential-carrier diagnostic opacity."""

import dataclasses
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from deployment.postgresql import security_audit_store_loss as store_loss
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
)
from deployment.postgresql.security_audit_process_crash import (
    ProcessCrashReconciliationSecrets,
)
from kernel.runtime_config import RuntimeConfig, RuntimeMode


_FIELD_INVENTORIES = {
    RuntimeConfig: (
        "mode",
        "deployment_image_digest",
        "oidc_issuer",
        "oidc_audience",
        "oidc_jwks_url",
        "pg_dsn",
        "tenant_readiness_pg_dsn",
        "security_audit_readiness_pg_dsn",
        "security_audit_authentication_pg_dsn",
        "security_audit_request_router_pg_dsn",
        "security_audit_control_pg_dsn",
        "correlation_hmac_kms_key_resource",
        "tenant_capability_kid",
        "signing_evidence_receipt_path",
        "signing_evidence_observer_public_key",
    ),
    ProcessCrashReconciliationSecrets: ("control_conninfo",),
    store_loss.StoreLossRecoverySecrets: (
        "admin_dsn",
        "migrator_dsn",
        "control_dsn",
        "login_passwords",
    ),
    store_loss._Routes: (
        "admin_long",
        "admin_short",
        "admin_target_short",
        "migrator_long",
        "control_short",
    ),
    store_loss._ValidatedInvocation: (
        "request",
        "routes",
        "login_passwords",
    ),
}

_PROTECTED_FIELDS = {
    RuntimeConfig: (
        "pg_dsn",
        "tenant_readiness_pg_dsn",
        "security_audit_readiness_pg_dsn",
        "security_audit_authentication_pg_dsn",
        "security_audit_request_router_pg_dsn",
        "security_audit_control_pg_dsn",
    ),
    ProcessCrashReconciliationSecrets: ("control_conninfo",),
    store_loss.StoreLossRecoverySecrets: (
        "admin_dsn",
        "migrator_dsn",
        "control_dsn",
        "login_passwords",
    ),
    store_loss._Routes: (
        "admin_long",
        "admin_short",
        "admin_target_short",
        "migrator_long",
        "control_short",
    ),
    store_loss._ValidatedInvocation: ("routes", "login_passwords"),
}


def _runtime_config_case():
    routes = (
        "postgresql://runtime:RTCFG01@runtime.invalid/ofarm",
        "postgresql://tenant:RTCFG02@tenant.invalid/ofarm",
        "postgresql://readiness:RTCFG03@readiness.invalid/ofarm",
        "postgresql://authentication:RTCFG04@auth.invalid/ofarm",
        "postgresql://router:RTCFG05@router.invalid/ofarm",
        "postgresql://control:RTCFG06@control.invalid/ofarm",
    )
    carrier = RuntimeConfig(
        mode=RuntimeMode.PRODUCTION,
        deployment_image_digest="sha256:" + "a" * 64,
        oidc_issuer="https://issuer.invalid",
        oidc_audience="ofarm-audience",
        oidc_jwks_url="https://issuer.invalid/jwks",
        pg_dsn=routes[0],
        tenant_readiness_pg_dsn=routes[1],
        security_audit_readiness_pg_dsn=routes[2],
        security_audit_authentication_pg_dsn=routes[3],
        security_audit_request_router_pg_dsn=routes[4],
        security_audit_control_pg_dsn=routes[5],
        correlation_hmac_kms_key_resource=(
            "projects/ofarm-project/locations/global/keyRings/audit/"
            "cryptoKeys/correlation"
        ),
        tenant_capability_kid="A" * 43,
        signing_evidence_receipt_path=Path("/tmp/ofarm-receipt.json"),
        signing_evidence_observer_public_key=bytes(range(32)),
    )
    return carrier, routes


def _process_crash_case():
    conninfo = "host=process.invalid user=control password=PROCESS01"
    return ProcessCrashReconciliationSecrets(conninfo), (conninfo,)


def _store_loss_material():
    input_routes = (
        "host=admin.invalid user=admin password=STOREADMIN01",
        "host=migrator.invalid user=migrator password=STOREMIGRATOR01",
        "host=control.invalid user=control password=STORECONTROL01",
    )
    passwords = tuple(
        (role, f"STORELOGIN{index:02d}")
        for index, role in enumerate(
            SECURITY_AUDIT_PROVISIONING_SPEC.required_password_role_names,
            start=1,
        )
    )
    secret_carrier = store_loss.StoreLossRecoverySecrets(
        admin_dsn=input_routes[0],
        migrator_dsn=input_routes[1],
        control_dsn=input_routes[2],
        login_passwords=passwords,
    )
    request = store_loss.StoreLossRecoveryRequest(
        loss_start=datetime(2026, 1, 2, tzinfo=timezone.utc),
        release_identity="credential-diagnostic-test",
        execution_id=UUID(int=1),
    )
    invocation = store_loss._validated_invocation(request, secret_carrier)
    password_values = tuple(password for _role, password in passwords)
    return secret_carrier, invocation, input_routes, password_values


def _store_loss_secrets_case():
    carrier, _invocation, routes, passwords = _store_loss_material()
    return carrier, routes + passwords


def _store_loss_routes_case():
    _carrier, invocation, _routes, passwords = _store_loss_material()
    route_values = tuple(
        getattr(invocation.routes, field)
        for field in _FIELD_INVENTORIES[store_loss._Routes]
    )
    return invocation.routes, route_values + passwords


def _store_loss_invocation_case():
    _carrier, invocation, _routes, passwords = _store_loss_material()
    route_values = tuple(
        getattr(invocation.routes, field)
        for field in _FIELD_INVENTORIES[store_loss._Routes]
    )
    return invocation, route_values + passwords


_CARRIER_FACTORIES = (
    pytest.param(_runtime_config_case, id="runtime-config"),
    pytest.param(_process_crash_case, id="process-crash-secrets"),
    pytest.param(_store_loss_secrets_case, id="store-loss-secrets"),
    pytest.param(_store_loss_routes_case, id="store-loss-routes"),
    pytest.param(_store_loss_invocation_case, id="store-loss-invocation"),
)


def _different(value):
    if type(value) is RuntimeMode:
        return RuntimeMode.TEST
    if type(value) is str:
        return value + "-different"
    if type(value) is bytes:
        return value + b"-different"
    if isinstance(value, Path):
        return Path(str(value) + "-different")
    if type(value) is tuple:
        first = value[0]
        return ((first[0], first[1] + "-different"), *value[1:])
    if type(value) is store_loss.StoreLossRecoveryRequest:
        return dataclasses.replace(
            value,
            release_identity=value.release_identity + "-different",
        )
    if type(value) is store_loss._Routes:
        return dataclasses.replace(
            value,
            admin_long=value.admin_long + "-different",
        )
    raise AssertionError(f"unsupported diagnostic test value type {type(value)}")


def _raise_carrier_only(carrier):
    raise Exception(carrier)


def _traceback_projection(carrier):
    try:
        _raise_carrier_only(carrier)
    except Exception as error:
        inner_traceback = error.__traceback__.tb_next
        normal = "".join(
            traceback.format_exception(type(error), error, inner_traceback)
        )
        captured = "".join(
            traceback.TracebackException(
                type(error),
                error,
                inner_traceback,
                capture_locals=True,
            ).format()
        )
        return normal, captured
    raise AssertionError("carrier-only failure did not raise")


def _pytest_assertion_projection(left, right):
    try:
        assert left == right
    except AssertionError as error:
        return str(error)
    raise AssertionError("unequal credential carriers compared equal")


def _closed_projection(carrier, unequal):
    normal_traceback, captured_traceback = _traceback_projection(carrier)
    return {
        "repr": repr(carrier),
        "str": str(carrier),
        "format": format(carrier),
        "f-repr": f"{carrier!r}",
        "percent-s": "%s" % carrier,
        "percent-r": "%r" % carrier,
        "tuple": repr((carrier,)),
        "list": repr([carrier]),
        "mapping": repr({"carrier": carrier}),
        "exception-str": str(Exception(carrier)),
        "exception-repr": repr(Exception(carrier)),
        "traceback": normal_traceback,
        "captured-locals-traceback": captured_traceback,
        "pytest-assertion": _pytest_assertion_projection(carrier, unequal),
    }


@pytest.mark.parametrize("carrier_factory", _CARRIER_FACTORIES)
def test_closed_diagnostic_projection_omits_every_protected_value(
    carrier_factory,
):
    carrier, protected_values = carrier_factory()
    carrier_type = type(carrier)
    protected_field = _PROTECTED_FIELDS[carrier_type][0]
    unequal = dataclasses.replace(
        carrier,
        **{
            protected_field: _different(getattr(carrier, protected_field)),
        },
    )

    assert carrier_type.__repr__ is object.__repr__
    assert carrier_type.__str__ is object.__str__
    assert carrier_type.__format__ is object.__format__
    projection = _closed_projection(carrier, unequal)
    assert projection["pytest-assertion"]
    for label, rendered in projection.items():
        rendered_bytes = rendered.encode("utf-8")
        for protected in protected_values:
            if (
                protected in rendered
                or protected.encode("utf-8") in rendered_bytes
            ):
                pytest.fail(
                    f"{carrier_type.__name__} exposed a protected value in {label}"
                )


@pytest.mark.parametrize("carrier_factory", _CARRIER_FACTORIES)
def test_exact_value_equality_and_generated_frozen_hash_cover_every_field(
    carrier_factory,
):
    carrier, _protected_values = carrier_factory()
    carrier_type = type(carrier)
    declared_fields = tuple(field.name for field in dataclasses.fields(carrier))

    assert declared_fields == _FIELD_INVENTORIES[carrier_type]
    assert carrier_type.__eq__.__code__.co_filename != "<string>"
    assert carrier_type.__hash__ not in (None, object.__hash__)
    equal = dataclasses.replace(carrier)
    assert carrier == equal
    assert hash(carrier) == hash(equal)
    assert carrier_type.__eq__(carrier, object()) is NotImplemented
    for field in declared_fields:
        unequal = dataclasses.replace(
            carrier,
            **{field: _different(getattr(carrier, field))},
        )
        assert carrier != unequal


def test_supported_store_loss_derivation_reaches_both_opaque_carriers():
    _secrets, invocation, _input_routes, passwords = _store_loss_material()

    assert type(invocation.routes) is store_loss._Routes
    assert type(invocation) is store_loss._ValidatedInvocation
    for carrier in (invocation.routes, invocation):
        rendered = repr(carrier)
        for password in passwords:
            if password in rendered:
                pytest.fail(
                    f"{type(carrier).__name__} derivation representation "
                    "exposed a password"
                )
