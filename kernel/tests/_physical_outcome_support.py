"""Actual-role physical outcome fixtures; no alternate successful provider path.

The production issuer and reader are real. External KMS uses the repository's
explicit public RFC test seed. The narrow runtime graph exercises error delivery,
not OIDC verification, deployment admission, storage certification or readiness.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import astuple, dataclass
from threading import Lock
from uuid import uuid4

from kernel.application_runtime import ApplicationRuntime, RuntimeMetadata
from kernel.request_router_audit import RequestRouterAuditProducer
from kernel.runtime_config import RuntimeMode
from kernel.security_audit_health import SecurityAuditHealth
from kernel.security_audit_runtime import PreTenantAuditRuntime
from kernel.tenant_uow import (
    GovernedBatchRequest, TenantUnitOfWorkManager, create_tenant_connection_pool,
)
from kernel.tests._tenant_signing_support import live_signing
from kernel.tests.test_postgresql_tenant_migration import ISSUER
from kernel.tests.test_postgresql_tenant_uow import _principal


class _NativeConnections:
    """Fixture-local factory delegation; every result is the original native."""

    def __init__(self, connection_class):
        self.connection_class = connection_class
        self.connections = []
        self.disposed = False
        self._lock = Lock()

    def connect(self, *args, **kwargs):
        connection = self.connection_class.connect(*args, **kwargs)
        with self._lock:
            self.connections.append(connection)
            disposed = self.disposed
        # A native creation may finish after the pool's bounded worker join.
        # This is fixture disposal, never evidence of production pool disposal.
        if disposed and not connection.closed:
            connection.close()
        return connection

    def dispose(self):
        with self._lock:
            self.disposed = True
            connections = tuple(self.connections)
        failure = None
        for connection in connections:
            try:
                if not connection.closed:
                    connection.close()
            except BaseException as error:
                if failure is None:
                    failure = error
        if failure is not None:
            raise failure


class TrackingPool:
    """Measure actual leases without replacing the pool or its health callback."""

    def __init__(self, inner):
        self.inner = inner
        self.acquired = []
        self.returned = []
        self.events = []
        self.held = set()
        self.peak = 0
        self.on_get = None
        self.on_put = None
        self._lock = Lock()
        self.native = _NativeConnections(inner.connection_class)
        inner.connection_class = self.native

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def getconn(self, *, timeout):
        with self._lock:
            self.events.append(("REQUEST", timeout, len(self.held)))
        connection = self.inner.getconn(timeout=timeout)
        with self._lock:
            assert connection not in self.held
            self.held.add(connection)
            self.peak = max(self.peak, len(self.held))
            self.acquired.append(connection)
            ordinal = len(self.acquired)
            self.events.append(("ACQUIRE", ordinal, len(self.held)))
        if self.on_get:
            self.on_get(connection, ordinal)
        return connection

    def putconn(self, connection):
        with self._lock:
            assert connection in self.held, "duplicate/unowned pool return"
            ordinal = len(self.returned) + 1
        if self.on_put:
            self.on_put(connection, ordinal)
        self.inner.putconn(connection)
        with self._lock:
            self.held.remove(connection)
            self.returned.append(connection)
            self.events.append(("RETURN", ordinal, len(self.held)))

    def assert_released(self):
        assert not self.held
        assert len(self.acquired) == len(self.returned)
        assert sorted(map(id, self.acquired)) == sorted(map(id, self.returned))


class RecordingAuditSink:
    def __init__(self):
        self.reasons = []
        self.signing_failures = []

    def append(self, reason):
        self.reasons.append(reason)
        raise AssertionError(f"unexpected pre-tenant audit emission: {reason}") from (
            self.signing_failures[-1] if self.signing_failures else None
        )


@dataclass
class PhysicalHarness:
    runtime: ApplicationRuntime
    manager: TenantUnitOfWorkManager
    pool: TrackingPool
    principal: object
    signing: object
    audit: RecordingAuditSink


@contextmanager
def physical_harness(target, authority, key, tmp_path, role, *, dsn=None, configure=None):
    signing = live_signing(target, key.kid, tmp_path)
    pool = TrackingPool(create_tenant_connection_pool(dsn or target.role_dsn(role)))
    if configure is not None:
        pool.inner._configure = configure
    manager = TenantUnitOfWorkManager(pool, signing.issuer)
    audit = RecordingAuditSink()
    actual_mint = signing.issuer.mint
    def record_mint(identity, principal_authority, challenge, **kwargs):
        try:
            return actual_mint(identity, principal_authority, challenge, **kwargs)
        except Exception as failure:
            audit.signing_failures.append(failure)
            raise
    signing.issuer.mint = record_mint
    runtime = ApplicationRuntime(
        PreTenantAuditRuntime(
            None, RequestRouterAuditProducer(manager, audit), SecurityAuditHealth(),
        ),
        signing.issuer,
        RuntimeMetadata(
            RuntimeMode.PRODUCTION, "sha256:" + "1" * 64, ISSUER,
            "physical-fixture", "physical-fixture", key.kid,
        ),
        None, None, manager,
    )
    principal = _principal(target, authority)
    failure = None
    try:
        manager.initialize()
        yield PhysicalHarness(runtime, manager, pool, principal, signing, audit)
    except BaseException as error:
        failure = error
    finally:
        # Preserve the test/ownership failure; cleanup must never turn it green.
        for cleanup in (pool.assert_released, manager.close, pool.native.dispose):
            try:
                cleanup()
            except BaseException as error:
                if failure is None:
                    failure = error
                else:
                    failure.add_note(f"physical fixture cleanup also failed: {type(error).__name__}")
        if failure is not None:
            raise failure


def request(authority, prefix="physical"):
    return GovernedBatchRequest(
        f"{prefix}-{uuid4().hex}", "PHYSICAL_EVIDENCE", f"request-{uuid4().hex}",
        authority.runtime_bundle_digest,
    )


def batch_tuple(batch):
    return astuple(batch)


def lose_commit_reply(monkeypatch, harness, *, before=None, after=None):
    """Explicit synthetic reply-loss seam around a real original COMMIT.

    Network acceptance uses PhysicalWireProxy separately. This seam is only for
    schedules whose independent variable is savepoints, authority or allocator
    validation. It never returns a fabricated successful database result.
    """
    import psycopg

    original = psycopg.Connection.commit
    calls = []

    def commit(connection):
        if connection is harness.pool.acquired[0]:
            calls.append(connection)
            if before:
                before(connection)
            original(connection)
            if after:
                after(connection)
            raise OSError("fixture withheld original COMMIT completion")
        return original(connection)

    monkeypatch.setattr(psycopg.Connection, "commit", commit)
    return calls


def activate_subject(target, authority):
    """Create a fixture principal through the existing identity controller."""
    from dataclasses import replace
    import psycopg
    from kernel.tests.test_postgresql_tenant_migration import (
        _initial_transition_values, _transition,
    )

    subject = f"physical-subject-{uuid4().hex}"
    reason = "physical-fixture-activate"
    with psycopg.connect(target.role_dsn("ofarm_identity_control_login")) as connection:
        initial = _initial_transition_values(connection, authority, subject=subject, reason=reason)
        _transition(
            connection, subject=subject, expected_head_id=None, expected_head_digest=None,
            act_id=initial["act_id"], act_digest=initial["act_digest"], act_kind="ACTIVATE",
            binding_version_id=initial["binding_version_id"], binding_version_digest=initial["binding_digest"],
            candidate_version_id=initial["binding_version_id"], candidate_version_digest=initial["binding_digest"],
            tenant_id=authority.tenant_id, tenant_registration_digest=authority.tenant_registration_digest,
            party_ref=authority.party_ref, party_schema_digest=authority.party_schema_digest,
            party_payload_digest=authority.party_payload_digest,
            valid_from=initial["valid_from"], valid_until=initial["valid_until"],
            predecessor_version_id=None, effective_at=initial["effective_at"],
            decided_at=initial["decided_at"], reason=reason,
        )
    return replace(
        authority, subject=subject, binding_version_id=initial["binding_version_id"],
        binding_version_digest=initial["binding_digest"], lifecycle_head_id=initial["act_id"],
        lifecycle_head_digest=initial["act_digest"],
    )


def revoke_subject(target, authority):
    """Revoke only the unique test subject through its real controller."""
    import psycopg
    from kernel.tests.test_postgresql_tenant_migration import _compute_act_digest, _transition

    with psycopg.connect(target.role_dsn("ofarm_identity_control_login")) as connection:
        effective, decided = connection.execute(
            "SELECT clock_timestamp(), clock_timestamp()"
        ).fetchone()
        act_id, reason = uuid4(), "physical-fixture-revoke"
        digest = _compute_act_digest(
            connection, subject=authority.subject, stream_sequence=2, act_id=act_id,
            act_kind="REVOKE", binding_version_id=authority.binding_version_id,
            binding_version_digest=authority.binding_version_digest,
            prior_act_id=authority.lifecycle_head_id, prior_act_digest=authority.lifecycle_head_digest,
            successor_version_id=None, successor_version_digest=None,
            effective_at=effective, decided_at=decided, reason=reason,
        )
        _transition(
            connection, subject=authority.subject, expected_head_id=authority.lifecycle_head_id,
            expected_head_digest=authority.lifecycle_head_digest, act_id=act_id,
            act_digest=digest, act_kind="REVOKE", binding_version_id=authority.binding_version_id,
            binding_version_digest=authority.binding_version_digest, candidate_version_id=None,
            candidate_version_digest=None, tenant_id=None, tenant_registration_digest=None,
            party_ref=None, party_schema_digest=None, party_payload_digest=None,
            valid_from=None, valid_until=None, predecessor_version_id=None,
            effective_at=effective, decided_at=decided, reason=reason,
        )
