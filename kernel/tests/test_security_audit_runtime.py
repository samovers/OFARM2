"""Production pre-tenant audit composition and startup authority checks."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT
from kernel import security_audit_runtime
from kernel.runtime_config import RuntimeConfig, RuntimeMode
from kernel.security_audit import CorrelationHmac, SecurityAuditOutcomeUnknown
from kernel.security_audit_client import PreTenantAuditClient
from kernel.security_audit_hmac_posture import (
    CorrelationHmacLifecyclePosture,
    CorrelationHmacVersionDisposition,
    CorrelationHmacVersionPosture,
)
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn,
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
_HMAC_POLICY = SECURITY_AUDIT_CONTRACT.correlation_hmac


def _hmac() -> CorrelationHmac:
    assert _HMAC_POLICY.key_version is not None
    return CorrelationHmac(b"h" * 32, _HMAC_POLICY.key_version)


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


def _posture() -> CorrelationHmacLifecyclePosture:
    return CorrelationHmacLifecyclePosture(
        (
            CorrelationHmacVersionPosture(
                2,
                "ENABLED",
                CorrelationHmacVersionDisposition.ACTIVE,
                None,
            ),
        )
    )


class _Cursor:
    def __init__(self, rows):
        self._rows = iter(rows)

    def fetchone(self):
        return next(self._rows, None)


class _Transaction:
    def __init__(self, field, events):
        self._field = field
        self._events = events

    def __enter__(self):
        self._events.append(("transaction.begin", self._field))
        return self

    def __exit__(self, *_args):
        self._events.append(("transaction.end", self._field))


class _Connection:
    autocommit = False

    def __init__(self, field, rows, events):
        self.field = field
        self._rows = rows
        self._events = events

    def __enter__(self):
        self._events.append(("connection.open", self.field))
        return self

    def __exit__(self, *_args):
        self._events.append(("connection.close", self.field))

    def transaction(self):
        return _Transaction(self.field, self._events)

    def execute(self, statement):
        self._events.append(("execute", self.field, statement))
        rows = self._rows if statement == "SELECT SESSION_USER::text" else ()
        return _Cursor(rows)


def _install_connections(monkeypatch, roles, events):
    dsn_to_field = {dsn: field for field, dsn in _DSNS.items()}
    calls = []
    connections = {}

    def connect(dsn, **kwargs):
        field = dsn_to_field[dsn]
        calls.append((field, dsn, kwargs))
        events.append(("connect", field, kwargs))
        connection = _Connection(field, ((roles[field],),), events)
        connections[field] = connection
        return connection

    monkeypatch.setattr(security_audit_runtime.psycopg, "connect", connect)
    return calls, connections


def _install_observer(monkeypatch, observed_connections):
    class Observer:
        def __init__(self, factory, _client, parent):
            assert parent == _HMAC_KEY
            self._factory = factory

        def current(self):
            with self._factory() as connection:
                observed_connections.append(connection)
            return _posture()

    monkeypatch.setattr(
        security_audit_runtime.hmac_posture,
        "CorrelationHmacLifecycleObserver",
        Observer,
    )


def test_database_authority_map_is_fixed_in_production_code():
    assert dict(security_audit_runtime._DATABASE_SESSION_USERS) == _AUTHORITIES
    assert len(_AUTHORITIES) == 5
    assert "security_audit_control_pg_dsn" in _AUTHORITIES


def test_five_bounded_connections_reuse_control_for_observation(monkeypatch):
    events = []
    observed_connections = []
    calls, connections = _install_connections(
        monkeypatch,
        dict(_AUTHORITIES),
        events,
    )
    _install_observer(monkeypatch, observed_connections)

    posture = security_audit_runtime._verify_database_authorities(
        _config(),
        object(),
    )

    expected_options = {
        "connect_timeout": 5,
        "options": "-c statement_timeout=2000",
    }
    assert len(calls) == 5
    assert [field for field, _dsn, _kwargs in calls] == list(_AUTHORITIES)
    assert all(kwargs == expected_options for _field, _dsn, kwargs in calls)
    assert observed_connections == [
        connections["security_audit_control_pg_dsn"]
    ]
    assert posture == _posture()
    assert sum(event[0] == "execute" for event in events) == 10
    assert sum(event[0] == "connection.close" for event in events) == 5
    for field in _AUTHORITIES:
        field_events = [event for event in events if event[1] == field]
        assert field_events[0] == ("connect", field, expected_options)
        assert ("execute", field, security_audit_runtime._READ_ONLY) in field_events
        assert ("execute", field, "SELECT SESSION_USER::text") in field_events
        assert field_events[-1] == ("connection.close", field)


def test_code_owned_startup_timeouts_override_conflicting_dsn_values(
    monkeypatch,
):
    dsn = (
        "dbname=audit connect_timeout=999 "
        "options='-c statement_timeout=999999'"
    )
    merged = []

    def connect(value, **kwargs):
        merged.append(conninfo_to_dict(make_conninfo(value, **kwargs)))
        return object()

    monkeypatch.setattr(
        security_audit_runtime.psycopg,
        "connect",
        connect,
    )

    security_audit_runtime._startup_connection_factory(dsn)()

    assert merged == [
        {
            "connect_timeout": "5",
            "dbname": "audit",
            "options": "-c statement_timeout=2000",
        }
    ]


def test_production_connection_policy_overrides_conflicting_dsn_values(
    monkeypatch,
):
    dsn = (
        "dbname=audit connect_timeout=999 "
        "options='-c statement_timeout=999999 -c lock_timeout=999999'"
    )
    merged = []

    def connect(value, **kwargs):
        merged.append(conninfo_to_dict(make_conninfo(value, **kwargs)))
        return object()

    monkeypatch.setattr(security_audit_runtime.psycopg, "connect", connect)

    security_audit_runtime._audit_producer_connection_factory(dsn)()

    assert merged == [
        {
            "connect_timeout": "5",
            "dbname": "audit",
            "options": "-c statement_timeout=2000 -c lock_timeout=250",
        }
    ]


def test_startup_connection_timeout_is_a_closed_refusal(monkeypatch):
    timeout = TimeoutError("connect timed out")
    monkeypatch.setattr(
        security_audit_runtime.psycopg,
        "connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(timeout),
    )

    with pytest.raises(
        security_audit_runtime.PreTenantAuditRuntimeUnavailable
    ) as raised:
        security_audit_runtime._verify_database_authorities(
            _config(),
            object(),
        )

    assert raised.value.__cause__ is timeout


def test_first_statement_timeout_closes_the_connection(monkeypatch):
    events = []
    timeout = TimeoutError("statement timed out")

    class Connection(_Connection):
        def execute(self, statement):
            if statement == security_audit_runtime._READ_ONLY:
                raise timeout
            return super().execute(statement)

    monkeypatch.setattr(
        security_audit_runtime.psycopg,
        "connect",
        lambda *_args, **_kwargs: Connection(
            "tenant_readiness_pg_dsn",
            (),
            events,
        ),
    )

    with pytest.raises(
        security_audit_runtime.PreTenantAuditRuntimeUnavailable
    ) as raised:
        security_audit_runtime._verify_database_authorities(
            _config(),
            object(),
        )

    assert raised.value.__cause__ is timeout
    assert events[-1] == ("connection.close", "tenant_readiness_pg_dsn")


def test_control_observation_timeout_closes_the_same_fifth_connection(
    monkeypatch,
):
    events = []
    observed_connections = []
    timeout = TimeoutError("control observation timed out")
    calls, connections = _install_connections(
        monkeypatch,
        dict(_AUTHORITIES),
        events,
    )

    class Observer:
        def __init__(self, factory, _client, _parent):
            self._factory = factory

        def current(self):
            with self._factory() as connection:
                observed_connections.append(connection)
                raise timeout

    monkeypatch.setattr(
        security_audit_runtime.hmac_posture,
        "CorrelationHmacLifecycleObserver",
        Observer,
    )

    with pytest.raises(
        security_audit_runtime.PreTenantAuditRuntimeUnavailable
    ) as raised:
        security_audit_runtime._verify_database_authorities(
            _config(),
            object(),
        )

    assert raised.value.__cause__ is timeout
    assert len(calls) == 5
    assert observed_connections == [
        connections["security_audit_control_pg_dsn"]
    ]
    assert events[-1] == (
        "connection.close",
        "security_audit_control_pg_dsn",
    )


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
        security_audit_runtime._verify_database_authorities(
            _config(),
            object(),
        )


@pytest.mark.parametrize(
    "rows",
    [
        (),
        (("ofarm_readiness", "extra"),),
        (("ofarm_readiness",), ("duplicate",)),
    ],
)
def test_startup_refuses_malformed_session_user_observations(rows):
    connection = _Connection("tenant_readiness_pg_dsn", rows, [])

    with pytest.raises(
        security_audit_runtime.PreTenantAuditRuntimeUnavailable
    ):
        with security_audit_runtime._require_session_user(
            lambda: connection,
            "ofarm_readiness",
        ):
            pass


def test_pretenant_audit_graph_has_one_fixed_startup_order(monkeypatch):
    events = []
    producer_factories = []
    producer_specs = []
    posture = _posture()

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
        lambda _config, _kms: events.append("database-authorities") or posture,
    )

    class Hmac:
        def __init__(self, _client, resource):
            assert resource == f"{_HMAC_KEY}/cryptoKeyVersions/2"
            events.append("hmac.build")

        def initialize(self):
            events.append("hmac.initialize")

    class AuditClient:
        def __init__(self, factory, producer):
            producer_factories.append(factory)
            producer_specs.append(producer)
            events.append(f"client.{producer.component}")

        def append(self, *_args):
            events.append("append")

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
        "hmac.build",
        "hmac.initialize",
        "client.AUTHENTICATION",
        "client.REQUEST_ROUTER",
    ]
    assert [spec.session_user for spec in producer_specs] == [
        "ofarm_security_authentication_producer_login",
        "ofarm_security_request_router_producer_login",
    ]
    connections = []
    monkeypatch.setattr(
        security_audit_runtime.psycopg,
        "connect",
        lambda dsn, **kwargs: connections.append((dsn, kwargs)) or object(),
    )
    for factory in producer_factories:
        factory()
    expected_parameters = {
        "connect_timeout": 5,
        "options": "-c statement_timeout=2000 -c lock_timeout=250",
    }
    assert connections == [
        (
            _DSNS["security_audit_authentication_pg_dsn"],
            expected_parameters,
        ),
        (
            _DSNS["security_audit_request_router_pg_dsn"],
            expected_parameters,
        ),
    ]
    assert runtime.authenticate("token") == "principal"
    with runtime.unit_of_work("principal") as unit:
        assert unit == "unit"
    assert "append" not in events


def test_live_postgresql_request_policy_enforces_statement_timeout(
    migrated_audit_service,
):
    producer = security_audit_runtime._producer("AUTHENTICATION")
    factory = security_audit_runtime._audit_producer_connection_factory(
        role_dsn(
            migrated_audit_service,
            producer.session_user,
        )
    )
    connection = factory()

    with pytest.raises(psycopg.errors.QueryCanceled):
        with connection:
            connection.execute("SELECT pg_catalog.pg_sleep(3)")

    assert connection.closed is True


def test_live_postgresql_request_policy_enforces_lock_timeout(
    migrated_audit_service,
):
    producer = security_audit_runtime._producer("AUTHENTICATION")
    factory = security_audit_runtime._audit_producer_connection_factory(
        role_dsn(
            migrated_audit_service,
            producer.session_user,
        )
    )
    connections = []

    def connect():
        connection = factory()
        connections.append(connection)
        return connection

    with psycopg.connect(
        migrated_audit_service["target_admin_dsn"]
    ) as blocker:
        blocker.execute(
            "LOCK TABLE ofarm_security.operational_security_event "
            "IN ACCESS EXCLUSIVE MODE"
        )
        with pytest.raises(SecurityAuditOutcomeUnknown) as raised:
            PreTenantAuditClient(
                connect,
                producer,
            ).append("CREDENTIAL_MISSING", _hmac())

    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert isinstance(raised.value.__cause__, psycopg.errors.LockNotAvailable)


def test_active_hmac_resource_requires_one_observed_active_version():
    posture = CorrelationHmacLifecyclePosture(())

    with pytest.raises(
        security_audit_runtime.PreTenantAuditRuntimeUnavailable
    ):
        security_audit_runtime._active_resource(_config(), posture)
