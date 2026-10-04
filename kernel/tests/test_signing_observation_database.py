"""S1 real-role, binary-driver, result-drain and TLS fault acceptance."""
from __future__ import annotations

import dataclasses
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import psycopg
import pytest

from kernel.google_kms_signer import GoogleKmsSigner
from kernel.signing_authority import SigningAuthorityUnavailable
from kernel.tenant_capability_issuer import TenantCapabilityIssuer
from kernel.tenant_uow import TenantUnitOfWorkManager, create_tenant_connection_pool
from kernel.tests._signing_observation_proxy import (
    WireFaultProxy, saturate_client_send_queue, tls_context,
)
from kernel.tests._signing_observation_support import (
    admitted_dsn, assert_disposed, assert_safe_refusal, observe, reader,
    retained_connections, write_receipt,
)
from kernel.tests._tenant_signing_support import FixtureKmsClient
from kernel.tests.tenant_capability_fixture import RFC8032_TEST_SEED
from kernel.tests.test_postgresql_tenant_migration import (
    authority, capability_key, tenant_target,  # noqa: F401 - real fixtures
)
from kernel.tests.test_postgresql_tenant_uow import _principal


@pytest.fixture
def observation(tenant_target, capability_key, tmp_path):
    observed = observe(tenant_target, capability_key.kid)
    path = tmp_path / "receipt.json"
    write_receipt(path, observed)
    return admitted_dsn(tenant_target.role_dsn("ofarm_app")), observed, path


def test_real_function_signed_receipt_and_psycopg_types(observation, monkeypatch):
    dsn, expected, path = observation
    retained = retained_connections(monkeypatch)
    actual = reader(dsn, path).current(expected.kid)
    assert dataclasses.replace(actual, observed_at_us=expected.observed_at_us) == expected
    assert actual.observed_at_us >= expected.observed_at_us
    assert type(actual.binder_instance_id) is UUID
    assert type(actual.public_key) is bytes
    assert type(actual.lifecycle_head_sequence) is int
    assert type(actual.audience) is str
    with pytest.raises(dataclasses.FrozenInstanceError):
        actual.kid = "changed"
    assert_disposed(retained)


@pytest.mark.parametrize("budget", (None, 0.15))
def test_lost_real_authority_reply_obeys_one_total_budget(observation, monkeypatch, budget):
    dsn, authority_value, path = observation
    retained = retained_connections(monkeypatch)
    with WireFaultProxy(dsn, "reply") as proxy:
        bounded = reader(proxy.dsn, path)
        def no_reader_worker(*_args, **_kwargs):
            pytest.fail("reader created a worker thread")
        monkeypatch.setattr(threading.Thread, "start", no_reader_worker)
        started = time.monotonic()
        kwargs = {} if budget is None else {"deadline_monotonic": started + budget}
        with pytest.raises(SigningAuthorityUnavailable) as raised:
            bounded.current(authority_value.kid, **kwargs)
        elapsed = time.monotonic() - started
        expected = 5.0 if budget is None else budget
        assert expected <= elapsed < expected + 0.5
        assert proxy.query_seen.is_set() and proxy.withheld.is_set()
        assert proxy.accepted == 1
        assert len(proxy.statements) == 1
        assert b"observe_signing_authority" in proxy.statements[0]
        assert_safe_refusal(raised.value)
        assert_disposed(retained)


@pytest.mark.parametrize("tls", (False, True))
def test_real_row_without_ready_is_incomplete_and_tls_finish_is_local(
    observation, monkeypatch, tmp_path, tls,
):
    dsn, authority_value, path = observation
    context, certificate = tls_context(tmp_path) if tls else (None, None)
    retained = retained_connections(monkeypatch)
    pressure = []
    if tls:
        from kernel import signing_authority_io as transport
        actual_close = transport._BoundedConnection.close
        def close_under_backpressure(connection):
            try:
                pressure.append(saturate_client_send_queue(connection.pgconn.socket))
            finally:
                started = time.monotonic()
                actual_close(connection)
                pressure.append(time.monotonic() - started)
        monkeypatch.setattr(transport._BoundedConnection, "close", close_under_backpressure)
    with WireFaultProxy(dsn, "ready", tls=context, certificate=certificate) as proxy:
        started = time.monotonic()
        with pytest.raises(SigningAuthorityUnavailable) as raised:
            reader(proxy.dsn, path).current(
                authority_value.kid, deadline_monotonic=started + 0.25,
            )
        assert time.monotonic() - started < 0.75
        assert b"D" in proxy.backend_types and b"C" in proxy.backend_types
        assert proxy.withheld.is_set()
        assert proxy.accepted == 1 and len(proxy.statements) == 1
        assert all(b"COMMIT" not in query and b"ROLLBACK" not in query for query in proxy.statements)
        if tls:
            assert proxy.tls_version in ("TLSv1.2", "TLSv1.3")
            assert pressure[0] > 0 and pressure[1] < 0.1
        assert_safe_refusal(raised.value)
        assert_disposed(retained)


@pytest.mark.parametrize("mode", ("duplicate", "columns", "null", "malformed", "extra-result", "nonidle", "fatal"))
def test_mutated_real_result_never_publishes_authority(observation, monkeypatch, mode):
    dsn, authority_value, path = observation
    retained = retained_connections(monkeypatch)
    with WireFaultProxy(dsn, mode) as proxy:
        with pytest.raises(SigningAuthorityUnavailable) as raised:
            reader(proxy.dsn, path).current(authority_value.kid)
        assert proxy.query_seen.is_set()
        assert_safe_refusal(raised.value)
        assert_disposed(retained)


def test_cancellation_after_dispatch_is_seen_without_remote_ack(observation, monkeypatch):
    dsn, authority_value, path = observation
    retained = retained_connections(monkeypatch)
    stop = threading.Event()
    with WireFaultProxy(dsn, "reply") as proxy:
        bounded = reader(proxy.dsn, path)
        def cancel_after_reply_is_lost():
            assert proxy.withheld.wait(2)
            stop.set()
        canceller = threading.Thread(target=cancel_after_reply_is_lost)
        canceller.start()
        started = time.monotonic()
        with pytest.raises(SigningAuthorityUnavailable) as raised:
            bounded.current(authority_value.kid, cancel_event=stop)
        canceller.join(1)
        assert not canceller.is_alive()
        assert time.monotonic() - started < 0.5
        assert_safe_refusal(raised.value)
        assert_disposed(retained)


def test_eight_real_tenant_lease_owners_use_the_production_issuer(
    tenant_target, authority, capability_key, observation, monkeypatch,
):
    dsn, authority_value, path = observation
    bounded = reader(dsn, path)
    client = FixtureKmsClient(authority_value.kms_key_version_resource, RFC8032_TEST_SEED)
    issuer = TenantCapabilityIssuer(bounded, GoogleKmsSigner(client), kid=capability_key.kid)
    principal = _principal(tenant_target, authority)
    manager = TenantUnitOfWorkManager(
        create_tenant_connection_pool(tenant_target.role_dsn("ofarm_app")), issuer,
    )
    manager.initialize()
    barrier = threading.Barrier(8, timeout=5)
    original = bounded.current
    active, peak = 0, 0
    lock = threading.Lock()

    def concurrent_current(*args, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            barrier.wait()
            return original(*args, **kwargs)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(bounded, "current", concurrent_current)
    def tenant_call():
        with manager.unit_of_work(principal) as unit:
            return unit.binding.tenant_id
    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: tenant_call(), range(8)))
        assert results == [authority.tenant_id] * 8
        assert peak == 8 and active == 0 and len(client.calls) == 8
    finally:
        manager.close()


def test_repeated_real_failures_retain_errors_but_not_client_connections(observation, monkeypatch):
    dsn, authority_value, path = observation
    retained = retained_connections(monkeypatch)
    errors = []
    for _ in range(4):
        with WireFaultProxy(dsn, "ready") as proxy:
            with pytest.raises(SigningAuthorityUnavailable) as raised:
                reader(proxy.dsn, path).current(
                    authority_value.kid, deadline_monotonic=time.monotonic() + 0.1,
                )
            errors.append(raised.value)
            assert_disposed(retained)
    assert len(retained) == len(errors) == 4
    assert all(error.__traceback__ is not None for error in errors)


@pytest.mark.parametrize("change", (
    "missing", "corrupt", "oversized", "expired", "conflicting", "wrong-signature",
    "duplicate-member", "noncanonical",
))
def test_fresh_receipt_replacement_cannot_fall_back_to_cached_good(
    observation, change,
):
    import base64
    import json
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from kernel.signing_receipt import SIGNING_EVIDENCE_MAX_BYTES
    from kernel.tests._signing_support import OBSERVER_PRIVATE_KEY, receipt_payload, signed_receipt
    dsn, authority_value, path = observation
    bounded = reader(dsn, path)
    assert bounded.current(authority_value.kid).kid == authority_value.kid
    if change == "missing":
        path.unlink()
    elif change == "corrupt":
        path.write_bytes(b"not a receipt")
    elif change == "oversized":
        path.write_bytes(b"x" * (SIGNING_EVIDENCE_MAX_BYTES + 1))
    elif change == "expired":
        write_receipt(path, authority_value, expiresAtUnixMicroseconds=authority_value.observed_at_us)
    elif change == "conflicting":
        write_receipt(path, authority_value, candidateDigest="sha256:" + "0" * 64)
    elif change == "duplicate-member":
        path.write_bytes(b'{"payload":"x","payload":"x","signature":"x"}')
    else:
        payload = receipt_payload(
            authority_value,
            observedAtUnixMicroseconds=authority_value.observed_at_us,
            expiresAtUnixMicroseconds=authority_value.observed_at_us + 30_000_000,
        )
        if change == "wrong-signature":
            path.write_bytes(signed_receipt(payload, private_key=Ed25519PrivateKey.generate()))
        else:
            raw = json.dumps(payload, separators=(", ", ": ")).encode()
            encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode()
            path.write_text(json.dumps({
                "payload": encode(raw), "signature": encode(OBSERVER_PRIVATE_KEY.sign(raw)),
            }))
    with pytest.raises(SigningAuthorityUnavailable) as raised:
        bounded.current(authority_value.kid)
    assert_safe_refusal(raised.value)


@pytest.mark.parametrize("stop_kind", ("event", "deadline"))
def test_valid_receipt_then_final_stop_never_publishes_authority(
    observation, monkeypatch, stop_kind,
):
    from kernel.signing_receipt import SigningEvidenceVerifier
    dsn, authority_value, path = observation
    retained = retained_connections(monkeypatch)
    original = SigningEvidenceVerifier.verify
    stop = threading.Event()
    validated = []
    deadline = time.monotonic() + 1
    def validate_then_stop(verifier, *args, **kwargs):
        result = original(verifier, *args, **kwargs)
        assert kwargs["now_us"] >= authority_value.observed_at_us
        assert_disposed(retained)  # Database disposal precedes receipt verification.
        validated.append(result)
        if stop_kind == "event":
            stop.set()
        else:
            time.sleep(max(0, deadline - time.monotonic()) + 0.01)
        return result
    monkeypatch.setattr(SigningEvidenceVerifier, "verify", validate_then_stop)
    with pytest.raises(SigningAuthorityUnavailable) as raised:
        reader(dsn, path).current(
            authority_value.kid, cancel_event=stop,
            deadline_monotonic=deadline,
        )
    assert len(validated) == 1, "the final-stop control never reached successful receipt verification"
    assert_safe_refusal(raised.value)
    assert_disposed(retained)


def test_retained_binary_query_generators_and_cursor_close_failure_dispose_connection(
    observation, monkeypatch,
):
    from kernel import signing_authority_io as transport
    dsn, authority_value, path = observation
    retained = retained_connections(monkeypatch)
    generators = []
    from kernel import postgres_wait as mechanical
    import os
    selectors = []
    original_selector = mechanical.selectors.DefaultSelector
    def retain_selector():
        selector = original_selector()
        selectors.append((selector, selector.fileno()))
        return selector
    monkeypatch.setattr(mechanical.selectors, "DefaultSelector", retain_selector)
    original_wait = transport.wait
    def hold_generator(generator, *args, **kwargs):
        generators.append(generator)
        return original_wait(generator, *args, **kwargs)
    monkeypatch.setattr(transport, "wait", hold_generator)
    original_cursor = transport._BoundedConnection.cursor
    class CursorCloseFault:
        def __init__(self, actual):
            self.actual = actual
        def __getattr__(self, name):
            return getattr(self.actual, name)
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            self.close()
        def close(self):
            self.actual.close()
            raise OSError("fixture cursor disposal failure")
    monkeypatch.setattr(transport._BoundedConnection, "cursor", lambda *a, **k: CursorCloseFault(original_cursor(*a, **k)))
    with pytest.raises(SigningAuthorityUnavailable) as raised:
        reader(dsn, path).current(authority_value.kid)
    assert_safe_refusal(raised.value)
    assert_disposed(retained)
    assert len(generators) >= 2 and len(selectors) >= 2
    for selector, descriptor in selectors:
        assert selector.get_map() is None
        with pytest.raises(OSError):
            os.fstat(descriptor)
    for generator in generators:
        with pytest.raises(StopIteration):
            generator.send(0)


@pytest.mark.parametrize("stage", ("before-connect", "before-kms", "after-dispatch"))
def test_real_issuer_final_stop_and_dispatched_kms_timeout_are_distinct(
    tenant_target, authority, capability_key, observation, stage,
):
    from uuid import uuid4
    from kernel.tenant_capability_issuer import CapabilityMintError, TenantChallenge
    dsn, authority_value, path = observation
    bounded = reader(dsn, path)
    stop = threading.Event()
    principal = _principal(tenant_target, authority)
    client = FixtureKmsClient(authority_value.kms_key_version_resource, RFC8032_TEST_SEED)
    dispatch = client.asymmetric_sign
    timeouts = []
    def sign_and_cancel(**kwargs):
        timeouts.append(kwargs["timeout"])
        if stage == "after-dispatch":
            stop.set()
        return dispatch(**kwargs)
    client.asymmetric_sign = sign_and_cancel
    def nonce():
        if stage == "before-kms":
            stop.set()
        return uuid4()
    issuer = TenantCapabilityIssuer(
        bounded, GoogleKmsSigner(client), kid=capability_key.kid, nonce_factory=nonce,
    )
    challenge = TenantChallenge(
        uuid4(), authority_value.audience, authority_value.observed_at_us,
    )
    if stage == "before-connect":
        stop.set()
    if stage == "after-dispatch":
        result = issuer.mint(principal.identity, principal.authority, challenge, cancel_event=stop)
        assert result and len(client.calls) == 1 and timeouts == [5.0]
    else:
        with pytest.raises(CapabilityMintError):
            issuer.mint(principal.identity, principal.authority, challenge, cancel_event=stop)
        assert client.calls == [] and timeouts == []


def test_real_runtime_builder_uses_reader_signer_and_shared_dsn(
    tenant_target, authority, capability_key, observation, monkeypatch,
):
    from types import SimpleNamespace
    from kernel import application_runtime
    from kernel.tests.test_application_runtime import _config
    from kernel.tests._signing_support import OBSERVER_PRIVATE_KEY, raw_public_key
    dsn, authority_value, path = observation
    config = dataclasses.replace(
        _config(), pg_dsn=dsn, tenant_capability_kid=capability_key.kid,
        signing_evidence_receipt_path=path,
        signing_evidence_observer_public_key=raw_public_key(OBSERVER_PRIVATE_KEY),
    )
    closed = []
    client = FixtureKmsClient(authority_value.kms_key_version_resource, RFC8032_TEST_SEED)
    client.transport = SimpleNamespace(close=lambda: closed.append("kms"))
    monkeypatch.setattr(application_runtime.kms_v1, "KeyManagementServiceClient", lambda: client)
    monkeypatch.setattr(application_runtime.httpx, "Client", lambda **_: SimpleNamespace(close=lambda: closed.append("http")))
    class OidcFixture:
        def __init__(self, *_args):
            pass
        def initialize(self):
            pass
    monkeypatch.setattr(application_runtime, "ProductionOidcVerifier", OidcFixture)
    monkeypatch.setattr(application_runtime, "build_pretenant_audit_runtime", lambda *_: SimpleNamespace())
    seen_dsns = []
    factory = application_runtime._connection_factory
    pool = application_runtime.create_tenant_connection_pool
    def record_factory(value):
        seen_dsns.append(("principal", value))
        return factory(value)
    def record_pool(value):
        seen_dsns.append(("tenant", value))
        return pool(value)
    monkeypatch.setattr(application_runtime, "_connection_factory", record_factory)
    monkeypatch.setattr(application_runtime, "create_tenant_connection_pool", record_pool)
    runtime = application_runtime.build_application_runtime(config)
    try:
        assert runtime.metadata.binder_audience == authority_value.audience
        assert len(client.calls) == 1  # Existing real KMS verification of startup probe.
        assert seen_dsns == [("principal", dsn), ("tenant", dsn)]
    finally:
        runtime.close()
    assert closed == ["http", "kms"]


def _retain_native_handles(monkeypatch):
    from types import SimpleNamespace
    from kernel import signing_authority_io as transport
    original = psycopg.pq.PGconn.connect_start
    retained = []
    def start(conninfo):
        handle = original(conninfo)
        retained.append((handle, handle.socket))
        return handle
    monkeypatch.setattr(transport.pq, "PGconn", SimpleNamespace(connect_start=start))
    return retained


def _assert_native_handles_disposed(retained):
    import os
    assert retained
    for handle, descriptor in retained:
        assert handle.status == psycopg.pq.ConnStatus.BAD
        with pytest.raises(OSError):
            os.fstat(descriptor)


@pytest.mark.parametrize("stage", ("startup", "tls-handshake", "tls-startup"))
def test_actual_partial_connect_is_owned_during_startup_and_tls(
    observation, monkeypatch, tmp_path, stage,
):
    dsn, authority_value, path = observation
    context, certificate = tls_context(tmp_path) if stage.startswith("tls") else (None, None)
    retained = _retain_native_handles(monkeypatch)
    mode = "startup" if stage == "tls-startup" else stage
    with WireFaultProxy(dsn, mode, tls=context, certificate=certificate) as proxy:
        with pytest.raises(SigningAuthorityUnavailable) as raised:
            reader(proxy.dsn, path).current(
                authority_value.kid, deadline_monotonic=time.monotonic() + 0.15,
            )
        assert proxy.withheld.is_set() and proxy.accepted == 1
        assert proxy.statements == []
        assert_safe_refusal(raised.value)
        _assert_native_handles_disposed(retained)


@pytest.mark.parametrize("failure_type", (psycopg.OperationalError, KeyboardInterrupt, SystemExit))
def test_actual_partial_handle_retained_by_poll_exception_is_finished(
    observation, monkeypatch, failure_type,
):
    from kernel import signing_authority_io as transport
    dsn, authority_value, path = observation
    retained = _retain_native_handles(monkeypatch)
    failures = []
    generators = []
    def broken_poll(handle):
        failure = (
            failure_type("raw driver failure password=fixture", pgconn=handle)
            if failure_type is psycopg.OperationalError else failure_type()
        )
        failures.append(failure)
        raise failure
        yield  # This is the actual wait protocol, interrupted before first yield.
    def capture(handle):
        generator = broken_poll(handle)
        generators.append(generator)
        return generator
    monkeypatch.setattr(transport, "_connect_existing", capture)
    expected = SigningAuthorityUnavailable if failure_type is psycopg.OperationalError else failure_type
    with pytest.raises(expected) as public:
        reader(dsn, path).current(authority_value.kid)
    if failure_type is psycopg.OperationalError:
        assert_safe_refusal(public.value)
        assert failures[0].pgconn is retained[0][0]
    else:
        assert public.value is failures[0]
    assert failures[0].__traceback__ is not None
    _assert_native_handles_disposed(retained)
    with pytest.raises(StopIteration):
        next(generators[0])


@pytest.mark.parametrize("stage", ("construction", "transfer"))
def test_real_connect_completion_is_disposed_if_wrapper_creation_or_transfer_stops(
    observation, monkeypatch, stage,
):
    from kernel import signing_authority_io as transport
    dsn, authority_value, path = observation
    retained = _retain_native_handles(monkeypatch)
    actual = transport._BoundedConnection
    stop = threading.Event()
    wrappers = []
    class InterruptedConnection(actual):
        def __init__(self, handle):
            super().__init__(handle)
            wrappers.append(self)
            if stage == "construction":
                raise OSError("wrapper construction failed")
            stop.set()
    monkeypatch.setattr(transport, "_BoundedConnection", InterruptedConnection)
    with pytest.raises(SigningAuthorityUnavailable) as raised:
        reader(dsn, path).current(authority_value.kid, cancel_event=stop)
    assert_safe_refusal(raised.value)
    assert len(wrappers) == 1 and wrappers[0].closed
    _assert_native_handles_disposed(retained)


@pytest.mark.parametrize("failure", ("certificate", "password"))
def test_actual_tls_credential_failure_does_not_downgrade_or_expose_driver(
    observation, monkeypatch, tmp_path, failure,
):
    from psycopg.conninfo import make_conninfo
    dsn, authority_value, path = observation
    context, certificate = tls_context(tmp_path)
    retained = _retain_native_handles(monkeypatch)
    with WireFaultProxy(dsn, "forward", tls=context, certificate=certificate) as proxy:
        supplied = make_conninfo(proxy.dsn, **(
            {"host": "wrong-identity.test"} if failure == "certificate" else {"password": "wrong-fixture-password"}
        ))
        with pytest.raises(SigningAuthorityUnavailable) as raised:
            reader(supplied, path).current(authority_value.kid)
        assert_safe_refusal(raised.value)
        assert proxy.accepted == 1 and len(retained) == 1
        assert proxy.statements == []
        _assert_native_handles_disposed(retained)
        # Certificate mismatch is an expected TLS peer alert, not a proxy defect.
        if failure == "certificate":
            import ssl
            assert proxy.failure is None or isinstance(proxy.failure, ssl.SSLError)
            proxy.failure = None
        else:
            assert proxy.tls_version in ("TLSv1.2", "TLSv1.3")


def test_eight_real_tenant_callers_cancel_before_signing_and_release_their_leases(
    tenant_target, authority, capability_key, observation, monkeypatch,
):
    from kernel import signing_authority as signing_module
    from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome
    dsn, authority_value, path = observation
    bounded = reader(dsn, path)
    client = FixtureKmsClient(authority_value.kms_key_version_resource, RFC8032_TEST_SEED)
    issuer = TenantCapabilityIssuer(bounded, GoogleKmsSigner(client), kid=capability_key.kid)
    principal = _principal(tenant_target, authority)
    manager = TenantUnitOfWorkManager(
        create_tenant_connection_pool(tenant_target.role_dsn("ofarm_app")), issuer,
    )
    manager.initialize()
    stop = threading.Event()
    barrier = threading.Barrier(8, action=stop.set, timeout=5)
    original_read = signing_module.read_signing_receipt
    original_mint = issuer.mint
    def receipt_boundary(*args, **kwargs):
        receipt = original_read(*args, **kwargs)
        barrier.wait()
        return receipt
    def cancelled_mint(*args):
        # Exercise the PR407 producer keywords. PR405 owns forwarding them from
        # the future observer; this test does not claim that downstream control.
        return original_mint(*args, cancel_event=stop)
    monkeypatch.setattr(signing_module, "read_signing_receipt", receipt_boundary)
    monkeypatch.setattr(issuer, "mint", cancelled_mint)
    retained = retained_connections(monkeypatch)
    def tenant_call():
        with pytest.raises(TenantBoundaryError) as refused:
            with manager.unit_of_work(principal):
                pytest.fail("cancelled signing published a tenant unit of work")
        return refused.value
    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            refused = list(executor.map(lambda _: tenant_call(), range(8)))
        assert len(refused) == 8
        assert all(error.outcome is TenantBoundaryOutcome.CAPABILITY_REFUSED for error in refused)
        assert len(retained) == 8 and all(connection.closed for connection, _ in retained)
        assert client.calls == []
        monkeypatch.setattr(signing_module, "read_signing_receipt", original_read)
        monkeypatch.setattr(issuer, "mint", original_mint)
        with manager.unit_of_work(principal) as unit:
            assert unit.binding.tenant_id == authority.tenant_id
        assert len(client.calls) == 1
    finally:
        manager.close()


@pytest.mark.parametrize("cleanup", ("cursor", "connection"))
def test_process_control_survives_real_query_cleanup_failures(
    observation, monkeypatch, cleanup,
):
    from kernel import signing_authority_io as transport
    dsn, authority_value, path = observation
    retained = retained_connections(monkeypatch)
    original_cursor = transport._BoundedConnection.cursor
    control = KeyboardInterrupt()
    class InterruptedCursor:
        def __init__(self, actual):
            self.actual = actual
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            self.close()
        def close(self):
            self.actual.close()
            if cleanup == "cursor":
                raise OSError("cursor close failed after disposal")
        def execute(self, *args, **kwargs):
            self.actual.execute(*args, **kwargs)
            raise control
    monkeypatch.setattr(transport._BoundedConnection, "cursor", lambda *a, **k: InterruptedCursor(original_cursor(*a, **k)))
    if cleanup == "connection":
        close = transport._BoundedConnection.close
        def close_then_fail(connection):
            close(connection)
            raise OSError("connection close failed after disposal")
        monkeypatch.setattr(transport._BoundedConnection, "close", close_then_fail)
    with pytest.raises(KeyboardInterrupt) as raised:
        reader(dsn, path).current(authority_value.kid)
    assert raised.value is control
    assert_disposed(retained)
