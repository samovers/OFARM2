"""Production pre-tenant audit composition and startup authority checks."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

from kernel import security_audit_runtime
from kernel.runtime_config import RuntimeConfig, RuntimeMode
from kernel.security_audit_hmac_posture import (
    CorrelationHmacLifecyclePosture,
    CorrelationHmacVersionDisposition,
    CorrelationHmacVersionPosture,
)


_AUTHORITIES = {
    "tenant_readiness_pg_dsn": "ofarm_readiness",
    "security_audit_readiness_pg_dsn":
        "ofarm_security_audit_readiness_login",
    "security_audit_authentication_pg_dsn":
        "ofarm_security_authentication_producer_login",
    "security_audit_request_router_pg_dsn":
        "ofarm_security_request_router_producer_login",
    "security_audit_control_pg_dsn":
        "ofarm_security_audit_control_login",
}
_DSNS = {field: f"dbname={index}" for index, field in enumerate(_AUTHORITIES)}
_ROLE_CASES = tuple(
    (field, role)
    for field, expected in _AUTHORITIES.items()
    for role in (*_AUTHORITIES.values(), "unexpected_startup_login")
    if role != expected
)
_HMAC_KEY = (
    "projects/ofarm2/locations/europe-west1/"
    "keyRings/security-audit/cryptoKeys/correlation"
)


def _config() -> RuntimeConfig:
    return RuntimeConfig(
        mode=RuntimeMode.PRODUCTION,
        deployment_image_digest="sha256:" + "1" * 64,
        oidc_issuer="https://issuer.example/tenant",
        oidc_audience="external-api",
        oidc_jwks_url="https://issuer.example/jwks",
        pg_dsn="dbname=tenant user=ofarm_app",
        tenant_readiness_pg_dsn=_DSNS["tenant_readiness_pg_dsn"],
        security_audit_readiness_pg_dsn=(
            _DSNS["security_audit_readiness_pg_dsn"]
        ),
        security_audit_authentication_pg_dsn=(
            _DSNS["security_audit_authentication_pg_dsn"]
        ),
        security_audit_request_router_pg_dsn=(
            _DSNS["security_audit_request_router_pg_dsn"]
        ),
        security_audit_control_pg_dsn=(
            _DSNS["security_audit_control_pg_dsn"]
        ),
        correlation_hmac_kms_key_resource=_HMAC_KEY,
        tenant_capability_kid="k" * 43,
        signing_evidence_receipt_path=Path("/run/ofarm/receipt"),
        signing_evidence_observer_public_key=b"o" * 32,
    )


class _Cursor:
    def __init__(self, rows):
        self._rows = iter(rows)

    def fetchone(self):
        return next(self._rows, None)


class _Transaction:
    def __init__(self, events):
        self._events = events

    def __enter__(self):
        self._events.append("transaction.begin")
        return self

    def __exit__(self, *_args):
        self._events.append("transaction.end")


class _Connection:
    autocommit = False

    def __init__(self, rows, events):
        self._rows = rows
        self._events = events

    def __enter__(self):
        self._events.append("connection.open")
        return self

    def __exit__(self, *_args):
        self._events.append("connection.close")

    def transaction(self):
        return _Transaction(self._events)

    def execute(self, statement):
        self._events.append(statement)
        rows = self._rows if statement == "SELECT SESSION_USER::text" else ()
        return _Cursor(rows)


def _install_connections(monkeypatch, roles, events):
    dsn_to_field = {dsn: field for field, dsn in _DSNS.items()}

    def connect(dsn):
        field = dsn_to_field[dsn]
        return _Connection(((roles[field],),), events)

    monkeypatch.setattr(security_audit_runtime.psycopg, "connect", connect)


def test_database_authority_map_is_fixed_in_production_code():
    assert dict(security_audit_runtime._DATABASE_SESSION_USERS) == _AUTHORITIES


def test_startup_accepts_the_exact_code_owned_database_authorities(monkeypatch):
    events = []
    _install_connections(monkeypatch, dict(_AUTHORITIES), events)

    security_audit_runtime._verify_database_authorities(_config())

    assert events.count("SELECT SESSION_USER::text") == 5
    assert events.count(security_audit_runtime._READ_ONLY) == 5
    assert events.count("connection.close") == 5


@pytest.mark.parametrize(("field", "observed_role"), _ROLE_CASES)
def test_startup_refuses_every_swapped_or_unexpected_database_role(
    monkeypatch,
    field,
    observed_role,
):
    roles = dict(_AUTHORITIES)
    roles[field] = observed_role
    _install_connections(monkeypatch, roles, [])

    with pytest.raises(
        security_audit_runtime.PreTenantAuditRuntimeUnavailable
    ):
        security_audit_runtime._verify_database_authorities(_config())


@pytest.mark.parametrize(
    "rows",
    [
        (),
        (("ofarm_readiness", "extra"),),
        (("ofarm_readiness",), ("duplicate",)),
    ],
)
def test_startup_refuses_malformed_session_user_observations(rows):
    connection = _Connection(rows, [])

    with pytest.raises(
        security_audit_runtime.PreTenantAuditRuntimeUnavailable
    ):
        security_audit_runtime._require_session_user(
            lambda: connection,
            "ofarm_readiness",
        )


def test_pretenant_audit_graph_has_one_fixed_startup_order(monkeypatch):
    events = []
    producer_specs = []
    posture = CorrelationHmacLifecyclePosture(
        (
            CorrelationHmacVersionPosture(
                2,
                "ENABLED",
                CorrelationHmacVersionDisposition.ACTIVE,
                None,
            ),
        )
    )

    monkeypatch.setattr(
        security_audit_runtime,
        "verify_tenant_structural_compatibility",
        lambda **_kwargs: events.append("tenant-structure"),
    )
    monkeypatch.setattr(
        security_audit_runtime,
        "verify_security_audit_structural_compatibility",
        lambda **_kwargs: events.append("audit-structure"),
    )
    monkeypatch.setattr(
        security_audit_runtime,
        "verify_postgresql_service_separation",
        lambda **_kwargs: events.append("service-separation"),
    )
    monkeypatch.setattr(
        security_audit_runtime,
        "_verify_database_authorities",
        lambda _config: events.append("database-authorities"),
    )

    class Observer:
        def __init__(self, _factory, _client, parent):
            assert parent == _HMAC_KEY
            events.append("lifecycle.build")

        def current(self):
            events.append("lifecycle.current")
            return posture

    class Hmac:
        def __init__(self, _client, resource):
            assert resource == f"{_HMAC_KEY}/cryptoKeyVersions/2"
            events.append("hmac.build")

        def initialize(self):
            events.append("hmac.initialize")

    class AuditClient:
        def __init__(self, _factory, producer):
            producer_specs.append(producer)
            events.append(f"client.{producer.component}")

        def append(self, *_args):
            events.append("append")

    monkeypatch.setattr(
        security_audit_runtime,
        "CorrelationHmacLifecycleObserver",
        Observer,
    )
    monkeypatch.setattr(
        security_audit_runtime,
        "GoogleKmsCorrelationHmac",
        Hmac,
    )
    monkeypatch.setattr(
        security_audit_runtime,
        "PreTenantAuditClient",
        AuditClient,
    )

    class Verifier:
        def verify(self, token):
            events.append(("verify", token))
            return "identity"

    class Resolver:
        def resolve(self, identity):
            events.append(("resolve", identity))
            return "principal"

    class TenantBoundary:
        def unit_of_work(self, principal):
            events.append(("tenant", principal))
            return nullcontext("unit")

    runtime = security_audit_runtime.build_pretenant_audit_runtime(
        _config(),
        Verifier(),
        Resolver(),
        TenantBoundary(),
        object(),
    )

    assert events == [
        "tenant-structure",
        "audit-structure",
        "service-separation",
        "database-authorities",
        "lifecycle.build",
        "lifecycle.current",
        "hmac.build",
        "hmac.initialize",
        "client.AUTHENTICATION",
        "client.REQUEST_ROUTER",
    ]
    assert [spec.session_user for spec in producer_specs] == [
        "ofarm_security_authentication_producer_login",
        "ofarm_security_request_router_producer_login",
    ]
    assert runtime.authenticate("token") == "principal"
    with runtime.unit_of_work("principal") as unit:
        assert unit == "unit"
    assert "append" not in events


def test_active_hmac_resource_requires_one_observed_active_version():
    posture = CorrelationHmacLifecyclePosture(())

    with pytest.raises(
        security_audit_runtime.PreTenantAuditRuntimeUnavailable
    ):
        security_audit_runtime._active_resource(_config(), posture)
