"""Read-only correlation-HMAC lifecycle posture regressions."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import psycopg
import pytest
from google.api_core import exceptions as google_exceptions
from google.cloud import kms_v1

from kernel.security_audit_hmac_posture import (
    CorrelationHmacLifecycleObserver,
    CorrelationHmacLifecycleUnavailable,
    CorrelationHmacVersionDisposition,
    KmsLifecycleClient,
)


PARENT = (
    "projects/example/locations/europe-west1/keyRings/ofarm/"
    "cryptoKeys/pretenant-correlation"
)
DEADLINE = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
STATES = kms_v1.CryptoKeyVersion.CryptoKeyVersionState
ALGORITHMS = kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm


def _version(number, **changes):
    values = {
        "name": f"{PARENT}/cryptoKeyVersions/{number}",
        "state": STATES.ENABLED,
        "algorithm": ALGORITHMS.HMAC_SHA256,
        "protection_level": kms_v1.ProtectionLevel.HSM,
        **changes,
    }
    return kms_v1.CryptoKeyVersion(**values)


def _database_rows():
    return {
        1: [(1, False, DEADLINE)],
        2: [(2, True, None)],
    }


class _Cursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None


class _Transaction:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class _Connection:
    def __init__(self, rows=None, *, autocommit=False, error=None):
        self.autocommit = autocommit
        self.rows = rows or _database_rows()
        self.error = error
        self.executions = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.closed = True
        return False

    def transaction(self):
        return _Transaction()

    def execute(self, statement, parameters=()):
        normalized = " ".join(statement.split())
        self.executions.append((normalized, parameters))
        if self.error is not None:
            raise self.error
        if normalized.startswith("SET TRANSACTION"):
            return _Cursor([])
        return _Cursor(self.rows.get(parameters[0], []))


class _Factory:
    def __init__(self, connection):
        self.connection = connection
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.connection


class _Pager:
    def __init__(self, response):
        self._response = response
        self.page_reads = 0

    @property
    def pages(self):
        self.page_reads += 1
        return iter((self._response,))


class _KmsClient:
    def __init__(
        self,
        connection,
        *,
        listed=None,
        token="",
        changes=None,
        list_error=None,
        get_error=None,
        expect_connection_closed=True,
    ):
        self.connection = connection
        self.listed = listed if listed is not None else [_version(1), _version(2)]
        self.token = token
        self.changes = changes or {}
        self.list_error = list_error
        self.get_error = get_error
        self.expect_connection_closed = expect_connection_closed
        self.list_calls = []
        self.get_calls = []
        self.pager = None

    def list_crypto_key_versions(self, *, request, retry, timeout):
        assert self.connection.closed is self.expect_connection_closed
        self.list_calls.append((request, retry, timeout))
        if self.list_error is not None:
            raise self.list_error
        response = kms_v1.ListCryptoKeyVersionsResponse(
            crypto_key_versions=self.listed,
            next_page_token=self.token,
        )
        self.pager = _Pager(response)
        return self.pager

    def get_crypto_key_version(self, *, request, retry, timeout):
        self.get_calls.append((request, retry, timeout))
        if self.get_error is not None:
            raise self.get_error
        number = int(request.name.rsplit("/", 1)[1])
        return _version(number, **self.changes.get(number, {}))


def _observer(*, rows=None, autocommit=False, kms_options=None, timeout=5):
    connection = _Connection(rows, autocommit=autocommit)
    client = _KmsClient(connection, **(kms_options or {}))
    observer = CorrelationHmacLifecycleObserver(
        _Factory(connection),
        client,
        PARENT,
        rpc_timeout_seconds=timeout,
    )
    return observer, connection, client


def test_current_returns_one_frozen_exact_posture_after_database_closes():
    observer, connection, client = _observer(timeout=4)

    posture = observer.current()

    assert tuple(
        (
            value.key_version,
            value.kms_state,
            value.disposition,
            value.greatest_purge_after,
        )
        for value in posture.versions
    ) == (
        (
            1,
            "ENABLED",
            CorrelationHmacVersionDisposition.RETIREMENT_REQUIRED,
            DEADLINE,
        ),
        (2, "ENABLED", CorrelationHmacVersionDisposition.ACTIVE, None),
    )
    assert connection.closed
    assert connection.executions == [
        ("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", ()),
        (
            "SELECT * FROM "
            "ofarm_security.observe_correlation_hmac_key_retention(%s)",
            (1,),
        ),
        (
            "SELECT * FROM "
            "ofarm_security.observe_correlation_hmac_key_retention(%s)",
            (2,),
        ),
    ]
    list_request, retry, timeout = client.list_calls[0]
    assert (list_request.parent, list_request.page_size, retry, timeout) == (
        PARENT,
        3,
        None,
        4,
    )
    assert client.pager.page_reads == 1
    assert [
        (call[0].name, call[1], call[2]) for call in client.get_calls
    ] == [
        (f"{PARENT}/cryptoKeyVersions/1", None, 4),
        (f"{PARENT}/cryptoKeyVersions/2", None, 4),
    ]
    with pytest.raises(FrozenInstanceError):
        posture.versions = ()


def test_current_uses_runtime_borrowed_open_control_connection():
    connection = _Connection()
    borrowed = []

    def borrow():
        borrowed.append(connection)
        return nullcontext(connection)

    client = _KmsClient(connection, expect_connection_closed=False)
    observer = CorrelationHmacLifecycleObserver(borrow, client, PARENT)

    posture = observer.current()

    assert borrowed == [connection]
    assert not connection.closed
    assert [value.key_version for value in posture.versions] == [1, 2]


@pytest.mark.parametrize(
    "resource,timeout",
    [
        (PARENT + "/cryptoKeyVersions/2", 5),
        (PARENT.replace("projects/example", "projects/EXAMPLE"), 5),
        (PARENT, True),
        (PARENT, 0),
        (PARENT, 31),
        (PARENT, "5"),
    ],
)
def test_constructor_refuses_invalid_static_configuration(resource, timeout):
    connection = _Connection()
    with pytest.raises(CorrelationHmacLifecycleUnavailable):
        CorrelationHmacLifecycleObserver(
            _Factory(connection),
            _KmsClient(connection),
            resource,
            rpc_timeout_seconds=timeout,
        )


@pytest.mark.parametrize(
    "rows",
    [
        {1: [], 2: [(2, True, None)]},
        {1: [(1, False, DEADLINE)] * 2, 2: [(2, True, None)]},
        {1: [(3, False, DEADLINE)], 2: [(2, True, None)]},
        {1: [(1, 0, DEADLINE)], 2: [(2, True, None)]},
        {1: [(1, False, datetime(2026, 8, 24))], 2: [(2, True, None)]},
        {1: [(1, True, DEADLINE)], 2: [(2, True, None)]},
        {1: [(1, False, DEADLINE)], 2: [(2, False, None)]},
        {1: [(1, True, DEADLINE)], 2: [(2, False, None)]},
    ],
)
def test_database_shape_or_active_version_conflicts_fail_before_kms(rows):
    observer, _, client = _observer(rows=rows)

    with pytest.raises(CorrelationHmacLifecycleUnavailable):
        observer.current()

    assert client.list_calls == []


def test_database_autocommit_or_failure_is_closed_before_kms():
    observer, _, client = _observer(autocommit=True)
    with pytest.raises(CorrelationHmacLifecycleUnavailable):
        observer.current()
    assert client.list_calls == []

    connection = _Connection(error=psycopg.OperationalError("down"))
    client = _KmsClient(connection)
    observer = CorrelationHmacLifecycleObserver(_Factory(connection), client, PARENT)
    with pytest.raises(CorrelationHmacLifecycleUnavailable):
        observer.current()
    assert client.list_calls == []


@pytest.mark.parametrize(
    "listed,token",
    [
        ([_version(1)], ""),
        ([_version(1), _version(2), _version(3)], ""),
        ([_version(1), _version(1), _version(2)], ""),
        ([_version(1), _version(2, name=PARENT + "/bad/2")], ""),
        ([_version(1), _version(2)], "another-page"),
    ],
)
def test_kms_list_must_be_one_exact_nonduplicated_version_set(listed, token):
    observer, _, client = _observer(
        kms_options={"listed": listed, "token": token},
    )

    with pytest.raises(CorrelationHmacLifecycleUnavailable):
        observer.current()

    assert client.get_calls == []


@pytest.mark.parametrize(
    "target,changes",
    [
        (2, {"state": STATES.DISABLED}),
        (2, {"algorithm": ALGORITHMS.HMAC_SHA512}),
        (2, {"protection_level": kms_v1.ProtectionLevel.SOFTWARE}),
        (2, {"name": f"{PARENT}/cryptoKeyVersions/1"}),
        (1, {"state": STATES.PENDING_GENERATION}),
        (1, {"state": STATES.IMPORT_FAILED}),
        (1, {"state": STATES.CRYPTO_KEY_VERSION_STATE_UNSPECIFIED}),
        (1, {"algorithm": ALGORITHMS.HMAC_SHA512}),
        (1, {"protection_level": kms_v1.ProtectionLevel.SOFTWARE}),
    ],
)
def test_malformed_or_inconsistent_kms_version_fails_closed(target, changes):
    observer, _, _ = _observer(kms_options={"changes": {target: changes}})

    with pytest.raises(CorrelationHmacLifecycleUnavailable):
        observer.current()


@pytest.mark.parametrize(
    "state,expected",
    [
        (STATES.ENABLED, CorrelationHmacVersionDisposition.RETIREMENT_REQUIRED),
        (STATES.DISABLED, CorrelationHmacVersionDisposition.RETIREMENT_REQUIRED),
        (
            STATES.DESTROY_SCHEDULED,
            CorrelationHmacVersionDisposition.DESTROY_SCHEDULED_OBSERVED,
        ),
        (STATES.DESTROYED, CorrelationHmacVersionDisposition.DESTROYED_OBSERVED),
    ],
)
def test_inactive_state_is_reported_without_mutation(state, expected):
    observer, _, client = _observer(kms_options={"changes": {1: {"state": state}}})

    posture = observer.current()

    assert posture.versions[0].disposition is expected
    assert posture.versions[0].greatest_purge_after == DEADLINE
    assert len(client.get_calls) == 2


def test_absent_retention_deadline_is_reported_explicitly():
    rows = _database_rows()
    rows[1] = [(1, False, None)]
    observer, _, _ = _observer(rows=rows)

    assert observer.current().versions[0].greatest_purge_after is None


@pytest.mark.parametrize("operation", ["list", "get"])
def test_kms_unavailability_is_closed_without_retry(operation):
    error = google_exceptions.ServiceUnavailable("down")
    options = {f"{operation}_error": error}
    observer, _, client = _observer(kms_options=options)

    with pytest.raises(CorrelationHmacLifecycleUnavailable) as raised:
        observer.current()

    assert str(raised.value) == "correlation HMAC lifecycle posture is unavailable"
    calls = client.list_calls if operation == "list" else client.get_calls
    assert len(calls) == 1
    assert calls[0][1] is None


def test_public_kms_protocol_has_read_methods_only():
    methods = {
        name
        for name, value in vars(KmsLifecycleClient).items()
        if callable(value) and not name.startswith("_")
    }

    assert methods == {"list_crypto_key_versions", "get_crypto_key_version"}
