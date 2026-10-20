"""EC01–EC05: real native certificate refusal and completed proxy evidence."""
from __future__ import annotations

import select
import socket
import ssl
import sys
from threading import Event, Thread, current_thread
from types import SimpleNamespace

import pytest

from kernel.tests import test_signing_observation_database as credential_consumer
from kernel.tests._signing_observation_proxy import WireFaultProxy
from kernel.tests._signing_support import KID
from kernel.tests.test_signing_observation_proxy import QUERY, TLS_VERSIONS, _leaves


@pytest.fixture
def certificate_case(tmp_path, monkeypatch):
    """Run the real consumer; the upstream trap never supplies database results."""
    from psycopg.conninfo import make_conninfo

    proxies = []
    enter = WireFaultProxy.__enter__
    context = credential_consumer.tls_context
    is_alive = Thread.is_alive

    def entered(proxy):
        proxies.append(proxy)
        return enter(proxy)

    monkeypatch.setattr(WireFaultProxy, "__enter__", entered)
    with socket.socket() as upstream:
        upstream.bind(("127.0.0.1", 0))
        upstream.listen()
        dsn = make_conninfo(
            host="127.0.0.1", port=upstream.getsockname()[1],
            dbname="fixture", user="fixture", password="fixture-password",
        )

        def run(version):
            def pinned_context(directory):
                tls, certificate = context(directory)
                tls.minimum_version = tls.maximum_version = version
                return tls, certificate
            monkeypatch.setattr(credential_consumer, "tls_context", pinned_context)
            credential_consumer.test_actual_tls_credential_failure_does_not_downgrade_or_expose_driver(
                (dsn, SimpleNamespace(kid=KID), tmp_path / "unused-receipt"),
                monkeypatch, tmp_path, "certificate",
            )

        try:
            yield SimpleNamespace(run=run, proxies=proxies)
        finally:
            assert not select.select([upstream], [], [], 0)[0]
            for proxy in proxies:
                assert not is_alive(proxy.thread)
                assert proxy.listener.fileno() == -1
                assert all(connection.fileno() == -1 for connection in proxy.sockets)


def _certificate_schedule(monkeypatch, case, schedule):
    """Control real EOF observation at the existing disposal and join seams."""
    waiting, release, retained = Event(), Event(), Event()
    retain = WireFaultProxy._retain_failure
    disposed = credential_consumer._assert_native_handles_disposed
    startup = sys.modules[WireFaultProxy.__module__]._startup
    enter = WireFaultProxy.__enter__

    def record(proxy, error):
        waiting.set()
        if schedule == "client-first-late-retain":
            assert release.wait(2)
        retain(proxy, error)
        retained.set()

    def read(connection):
        if isinstance(connection, ssl.SSLSocket) and schedule == "client-first-stop":
            waiting.set()
            assert release.wait(2)
        return startup(connection)

    def entered(proxy):
        join = proxy.thread.join
        def completed(timeout):
            assert proxy.stop.is_set()
            release.set()
            return join(timeout)
        monkeypatch.setattr(proxy.thread, "join", completed)
        return enter(proxy)

    def client_disposed(handles):
        disposed(handles)
        if schedule == "worker-first":
            assert retained.wait(2)
        else:
            assert waiting.wait(2)
            assert case.proxies[0].failure is None

    monkeypatch.setattr(WireFaultProxy, "_retain_failure", record)
    monkeypatch.setattr(WireFaultProxy, "__enter__", entered)
    monkeypatch.setattr(sys.modules[WireFaultProxy.__module__], "_startup", read)
    monkeypatch.setattr(credential_consumer, "_assert_native_handles_disposed", client_disposed)
    return release


@pytest.mark.parametrize("version", TLS_VERSIONS)
@pytest.mark.parametrize("schedule", (
    "worker-first", "client-first-late-retain", "client-first-stop",
))
def test_ec02_certificate_refusal_is_independent_of_worker_schedule(
    certificate_case, monkeypatch, version, schedule,
):
    release = _certificate_schedule(monkeypatch, certificate_case, schedule)
    try:
        certificate_case.run(version)
    finally:
        release.set()
    proxy, = certificate_case.proxies
    assert proxy.accepted == 1 and proxy.tls_version == version.name.replace("_", ".")
    assert proxy.frontend_types == proxy.backend_types == proxy.statements == []
    assert len(proxy.sockets) == 2
    if schedule == "client-first-stop":
        assert proxy.failure is None
    else:
        assert isinstance(proxy.failure, EOFError)
        assert proxy.failure.__traceback__ is not None


def _capture_proxy_exit(monkeypatch):
    exit_proxy = WireFaultProxy.__exit__
    groups = []
    def exited(proxy, *body):
        try:
            return exit_proxy(proxy, *body)
        except BaseExceptionGroup as error:
            groups.append((error, error.__traceback__))
            raise
    monkeypatch.setattr(WireFaultProxy, "__exit__", exited)
    return groups


def _assert_original_group(caught, groups):
    original, original_trace = groups[0]
    assert caught.value is original
    trace = caught.value.__traceback__
    while trace is not None and trace is not original_trace:
        trace = trace.tb_next
    assert trace is original_trace


@pytest.mark.parametrize("missing", (
    "hostname", "native-handle", "single-client", "no-query", "no-frontend",
    "no-backend", "no-statement", "no-upstream-owner", "closed-listener",
    "closed-socket", "terminated-worker", "completed-stop",
))
def test_ec01_ec05_incomplete_refusal_proof_preserves_original_group(
    certificate_case, monkeypatch, missing,
):
    release = _certificate_schedule(monkeypatch, certificate_case, "worker-first")
    groups = _capture_proxy_exit(monkeypatch)
    complete = credential_consumer._certificate_refusal_complete
    # Invalid evidence is injected after real TLS/native refusal and disposal.
    # The borrowed socket is test-owned and always closed, even if the guard fails.
    with socket.socket() as borrowed:
        def incomplete(proxy, handles, hostname):
            if missing == "hostname":
                hostname = [False]
            elif missing == "native-handle":
                handles = []
            elif missing == "single-client":
                proxy.accepted = 2
            elif missing == "no-query":
                proxy.query_seen.set()
            elif missing == "no-frontend":
                proxy.frontend_types.append(b"Q")
            elif missing == "no-backend":
                proxy.backend_types.append(b"R")
            elif missing == "no-statement":
                proxy.statements.append(QUERY)
            elif missing == "no-upstream-owner":
                proxy.sockets.append(borrowed)
            elif missing == "closed-listener":
                proxy.listener = borrowed
            elif missing == "closed-socket":
                proxy.sockets[0] = borrowed
            elif missing == "terminated-worker":
                monkeypatch.setattr(proxy.thread, "is_alive", lambda: True)
            elif missing == "completed-stop":
                proxy.stop.clear()
            return complete(proxy, handles, hostname)
        monkeypatch.setattr(credential_consumer, "_certificate_refusal_complete", incomplete)
        try:
            with pytest.raises(BaseExceptionGroup) as caught:
                certificate_case.run(TLS_VERSIONS[1])
        finally:
            release.set()
        _assert_original_group(caught, groups)
        proxy, = certificate_case.proxies
        assert caught.value.exceptions == (proxy.failure,)
        assert isinstance(proxy.failure, EOFError)


@pytest.mark.parametrize("shape", (
    "pre-tls-eof", "different-object", "nested", "body", "worker-cleanup",
    "teardown-cleanup", "unrelated-worker",
))
def test_ec03_ec04_unexpected_or_combined_failure_is_never_filtered(
    certificate_case, monkeypatch, shape,
):
    release = _certificate_schedule(monkeypatch, certificate_case, "worker-first")
    groups = _capture_proxy_exit(monkeypatch)
    extra = KeyboardInterrupt("fixture failure must remain visible")
    if shape == "body":
        disposed = credential_consumer._assert_native_handles_disposed
        def failed_body(handles):
            disposed(handles)
            raise extra
        monkeypatch.setattr(credential_consumer, "_assert_native_handles_disposed", failed_body)
    elif shape in ("worker-cleanup", "teardown-cleanup"):
        close = WireFaultProxy._close
        injected = []
        def failed_close(connection):
            close(connection)
            worker = current_thread().name == "signing-test-proxy"
            if worker == (shape == "worker-cleanup") and not injected:
                injected.append(connection)
                raise extra
        monkeypatch.setattr(WireFaultProxy, "_close", staticmethod(failed_close))
    else:
        retain = WireFaultProxy._retain_failure
        def different_failure(proxy, failure):
            if shape == "pre-tls-eof":
                proxy.tls_version = None
            elif shape == "nested":
                failure = BaseExceptionGroup("nested worker failure", [failure])
            elif shape == "unrelated-worker":
                failure = extra
            retain(proxy, failure)
        monkeypatch.setattr(WireFaultProxy, "_retain_failure", different_failure)
        if shape == "different-object":
            exit_proxy = WireFaultProxy.__exit__
            def different_group(proxy, *body):
                try:
                    return exit_proxy(proxy, *body)
                except BaseExceptionGroup:
                    error = ExceptionGroup("different EOF", [EOFError("test peer closed")])
                    groups.clear()
                    try:
                        raise error
                    except BaseExceptionGroup as error:
                        groups.append((error, error.__traceback__))
                        raise
            monkeypatch.setattr(WireFaultProxy, "__exit__", different_group)
    try:
        with pytest.raises(BaseExceptionGroup) as caught:
            certificate_case.run(TLS_VERSIONS[1])
    finally:
        release.set()
    _assert_original_group(caught, groups)
    if shape in ("body", "worker-cleanup", "teardown-cleanup"):
        assert extra in _leaves(caught.value)
        assert any(isinstance(leaf, EOFError) for leaf in _leaves(caught.value))
    elif shape == "unrelated-worker":
        assert _leaves(caught.value) == [extra]


def test_ec03_tls_alert_still_requires_real_native_hostname_refusal(
    certificate_case, monkeypatch,
):
    release = _certificate_schedule(monkeypatch, certificate_case, "worker-first")
    retain = WireFaultProxy._retain_failure
    alert = ssl.SSLError("fixture peer alert")
    def peer_alert(proxy, error):
        assert isinstance(error, EOFError)
        retain(proxy, alert)
    monkeypatch.setattr(WireFaultProxy, "_retain_failure", peer_alert)
    try:
        certificate_case.run(TLS_VERSIONS[0])
    finally:
        release.set()
    assert certificate_case.proxies[0].failure is alert


def test_ec01_normal_teardown_cannot_replace_native_refusal_proof(
    certificate_case, monkeypatch,
):
    release = _certificate_schedule(monkeypatch, certificate_case, "client-first-stop")
    complete = credential_consumer._certificate_refusal_complete
    monkeypatch.setattr(
        credential_consumer, "_certificate_refusal_complete",
        lambda proxy, handles, _proof: complete(proxy, handles, [False]),
    )
    try:
        with pytest.raises(AssertionError):
            certificate_case.run(TLS_VERSIONS[1])
    finally:
        release.set()
    assert certificate_case.proxies[0].failure is None


def test_ec05_failed_native_diagnostic_observation_still_disposes_real_handle(
    certificate_case, monkeypatch,
):
    from kernel import signing_authority_io as transport
    start = transport.pq.PGconn.connect_start
    handles, finished = [], []
    class UnreadableDiagnostic:
        def __init__(self, native):
            self.native = native
        def __getattr__(self, name):
            return getattr(self.native, name)
        @property
        def error_message(self):
            raise RuntimeError("diagnostic observation failed")
        def finish(self):
            try:
                return self.native.finish()
            finally:
                finished.append(self.native)
    def connect(conninfo):
        native = start(conninfo)
        handles.append((native, native.socket))
        return UnreadableDiagnostic(native)
    monkeypatch.setattr(transport.pq, "PGconn", SimpleNamespace(connect_start=connect))
    with pytest.raises((AssertionError, BaseExceptionGroup)):
        certificate_case.run(TLS_VERSIONS[1])
    credential_consumer._assert_native_handles_disposed(handles)
    assert finished == [native for native, _descriptor in handles]
