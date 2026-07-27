"""Focused tests for bounded pre-tenant security-audit ingest."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import psycopg
import pytest

from deployment.postgresql.audit_contract import (
    SECURITY_AUDIT_CONTRACT,
    ProducerReasonSpec,
)
from kernel import security_audit_runtime
from kernel.security_audit import (
    CorrelationHmac,
    OverflowAuditAppend,
    SecurityAuditOutcomeUnknown,
    SecurityAuditRefused,
    SecurityAuditUnavailable,
    StoredAuditAppend,
)
from kernel.security_audit_client import PreTenantAuditClient
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn,
)


NOW = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
PURGE_AFTER = NOW + timedelta(days=30)
BUCKET_START = NOW.replace(second=0, microsecond=0)
HMAC_POLICY = SECURITY_AUDIT_CONTRACT.correlation_hmac


def _producer(session_user: str) -> ProducerReasonSpec:
    return next(
        producer
        for producer in SECURITY_AUDIT_CONTRACT.reason_matrix
        if producer.session_user == session_user
    )


AUTHENTICATION = _producer("ofarm_security_authentication_producer_login")
ROUTER = _producer("ofarm_security_request_router_producer_login")


def _hmac(value: bytes = b"h" * 32) -> CorrelationHmac:
    assert HMAC_POLICY.key_version is not None
    return CorrelationHmac(value, HMAC_POLICY.key_version)


def _individual(parameters):
    return [(parameters[0], NOW, PURGE_AFTER, True, None, False)]


def _overflow(parameters):
    return [(None, None, None, False, BUCKET_START, False)]


class _Cursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows.pop(0)


class _Transaction:
    def __init__(self, connection):
        self._connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None and self._connection.commit_error is not None:
            raise self._connection.commit_error
        return False


class _Connection:
    def __init__(
        self,
        outputs,
        *,
        autocommit=False,
        commit_error=None,
    ):
        self.autocommit = autocommit
        self.outputs = list(outputs)
        self.commit_error = commit_error
        self.executions = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.closed = True
        return False

    def transaction(self):
        return _Transaction(self)

    def execute(self, statement, parameters=()):
        self.executions.append((" ".join(statement.split()), parameters))
        if not self.outputs:
            raise AssertionError("unexpected database statement")
        outcome = self.outputs.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            outcome = outcome(parameters)
        return _Cursor(outcome)


class _Factory:
    def __init__(self, *connections):
        self.connections = list(connections)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if not self.connections:
            raise AssertionError("unexpected connection")
        connection = self.connections.pop(0)
        if isinstance(connection, BaseException):
            raise connection
        return connection


def _connection(
    append_outcome,
    *,
    producer=AUTHENTICATION,
    autocommit=False,
    commit_error=None,
):
    return _Connection(
        [[], [(producer.session_user,)], append_outcome],
        autocommit=autocommit,
        commit_error=commit_error,
    )


def _append_parameters(connection):
    return next(
        parameters
        for statement, parameters in connection.executions
        if "append_pretenant_failure" in statement
    )


def test_pre_submission_unavailability_is_not_retried():
    unavailable = psycopg.OperationalError("endpoint unavailable")
    factory = _Factory(
        unavailable,
        _connection(_individual),
    )

    with pytest.raises(SecurityAuditUnavailable) as raised:
        PreTenantAuditClient(
            factory,
            AUTHENTICATION,
        ).append("CREDENTIAL_MISSING", _hmac())

    assert raised.value.__cause__ is unavailable
    assert factory.calls == 1


@pytest.mark.parametrize(
    ("value", "version"),
    [
        (b"x" * 31, HMAC_POLICY.key_version),
        (bytearray(b"x" * 32), HMAC_POLICY.key_version),
        (b"x" * 32, 1),
        (b"x" * 32, 3),
        (b"x" * 32, None),
    ],
    ids=("length", "type", "v1", "v3", "missing-version"),
)
def test_correlation_hmac_accepts_only_active_v2(value, version):
    with pytest.raises(ValueError, match="correlation HMAC is invalid"):
        CorrelationHmac(value, version)


def test_correlation_hmac_hides_value_from_repr():
    correlation_hmac = _hmac(b"secret-canary".ljust(32, b"!"))

    assert "secret-canary" not in repr(correlation_hmac)


def test_append_requires_the_validated_correlation_hmac_type():
    class UncheckedCorrelationHmac(CorrelationHmac):
        def __post_init__(self):
            pass

    factory = _Factory(_connection(_individual))
    unchecked = UncheckedCorrelationHmac(b"short", 1)

    with pytest.raises(ValueError, match="append input is invalid"):
        PreTenantAuditClient(factory, AUTHENTICATION).append(
            "CREDENTIAL_MISSING",
            unchecked,
        )

    assert factory.calls == 0


def test_individual_append_generates_identity_and_maps_exact_parameters():
    connection = _connection(_individual)
    result = PreTenantAuditClient(
        _Factory(connection),
        AUTHENTICATION,
    ).append("CREDENTIAL_MISSING", _hmac())

    assert isinstance(result, StoredAuditAppend)
    assert result.event_id.version == 4
    assert result.observed_at == NOW
    assert result.purge_after == PURGE_AFTER
    parameters = _append_parameters(connection)
    assert parameters == (
        result.event_id,
        "CREDENTIAL_MISSING",
        b"h" * 32,
        HMAC_POLICY.domain,
        HMAC_POLICY.key_version,
    )
    assert connection.executions[0][0] == (
        "SET TRANSACTION ISOLATION LEVEL READ COMMITTED"
    )


def test_overflow_result_is_bound_to_verified_producer():
    result = PreTenantAuditClient(
        _Factory(_connection(_overflow, producer=ROUTER)),
        ROUTER,
    ).append("BINDER_REFUSED", _hmac())

    assert isinstance(result, OverflowAuditAppend)
    assert result.bucket.producer == ROUTER.producer
    assert result.bucket.component == ROUTER.component
    assert result.bucket.bucket_start == BUCKET_START
    assert result.count_unknown is False


def test_wrong_session_user_refuses_before_append():
    connection = _Connection(
        [[], [(ROUTER.session_user,)]],
    )

    with pytest.raises(SecurityAuditUnavailable):
        PreTenantAuditClient(
            _Factory(connection),
            AUTHENTICATION,
        ).append("CREDENTIAL_MISSING", _hmac())

    assert all(
        "append_pretenant_failure" not in statement
        for statement, _ in connection.executions
    )


def test_autocommit_and_unregistered_reason_refuse_before_append():
    connection = _Connection([], autocommit=True)
    factory = _Factory(connection)
    client = PreTenantAuditClient(factory, AUTHENTICATION)

    with pytest.raises(SecurityAuditUnavailable):
        client.append("CREDENTIAL_MISSING", _hmac())
    with pytest.raises(ValueError, match="append input is invalid"):
        client.append("BINDER_REFUSED", _hmac())

    assert factory.calls == 1
    assert connection.executions == []


def test_ambiguous_commit_retries_once_with_identical_parameters():
    first = _connection(
        _individual,
        commit_error=psycopg.OperationalError("commit result lost"),
    )
    second = _connection(_individual)
    factory = _Factory(first, second)

    result = PreTenantAuditClient(
        factory,
        AUTHENTICATION,
    ).append("CREDENTIAL_MISSING", _hmac())

    assert isinstance(result, StoredAuditAppend)
    assert factory.calls == 2
    assert first.closed is True
    assert second.closed is True
    assert _append_parameters(first) == _append_parameters(second)
    assert _append_parameters(first)[0] == result.event_id


def test_second_ambiguity_preserves_possible_overflow_bucket():
    first = _connection(
        _overflow,
        commit_error=psycopg.OperationalError("commit result lost"),
    )
    second = _connection(psycopg.OperationalError("connection lost"))

    factory = _Factory(first, second)

    with pytest.raises(SecurityAuditOutcomeUnknown) as raised:
        PreTenantAuditClient(
            factory,
            AUTHENTICATION,
        ).append("CREDENTIAL_MISSING", _hmac())

    assert factory.calls == 2
    assert first.closed is True
    assert second.closed is True
    assert raised.value.event_id == _append_parameters(first)[0]
    assert raised.value.possible_overflow_bucket is not None
    assert raised.value.possible_overflow_bucket.bucket_start == BUCKET_START
    assert str(raised.value) == "security audit append outcome is unknown"


def test_retry_unavailability_preserves_first_ambiguous_outcome():
    first = _connection(
        _individual,
        commit_error=psycopg.OperationalError("commit result lost"),
    )
    second = _Connection([psycopg.OperationalError("unavailable")])

    with pytest.raises(SecurityAuditOutcomeUnknown):
        PreTenantAuditClient(
            _Factory(first, second),
            AUTHENTICATION,
        ).append("CREDENTIAL_MISSING", _hmac())


def test_retry_refusal_preserves_first_ambiguous_outcome():
    first = _connection(
        _individual,
        commit_error=psycopg.OperationalError("commit result lost"),
    )
    second = _connection(
        psycopg.errors.InvalidParameterValue("refused"),
    )

    with pytest.raises(SecurityAuditOutcomeUnknown):
        PreTenantAuditClient(
            _Factory(first, second),
            AUTHENTICATION,
        ).append("CREDENTIAL_MISSING", _hmac())


@pytest.mark.parametrize(
    "timeout",
    (
        psycopg.errors.QueryCanceled("statement timed out"),
        psycopg.errors.LockNotAvailable("lock timed out"),
    ),
    ids=("statement", "lock"),
)
def test_pre_submission_postgresql_timeout_is_unavailable_and_not_retried(
    timeout,
):
    first = _Connection([timeout])
    factory = _Factory(
        first,
        _connection(_individual),
    )

    with pytest.raises(SecurityAuditUnavailable):
        PreTenantAuditClient(
            factory,
            AUTHENTICATION,
        ).append("CREDENTIAL_MISSING", _hmac())

    assert factory.calls == 1
    assert first.closed is True


@pytest.mark.parametrize(
    "timeout",
    (
        psycopg.errors.QueryCanceled("statement timed out"),
        psycopg.errors.LockNotAvailable("lock timed out"),
    ),
    ids=("statement", "lock"),
)
def test_submitted_postgresql_timeout_retries_once_with_identical_parameters(
    timeout,
):
    first = _connection(timeout)
    second = _connection(_individual)
    factory = _Factory(first, second)

    result = PreTenantAuditClient(
        factory,
        AUTHENTICATION,
    ).append("CREDENTIAL_MISSING", _hmac())

    assert isinstance(result, StoredAuditAppend)
    assert factory.calls == 2
    assert first.closed is True
    assert second.closed is True
    assert _append_parameters(first) == _append_parameters(second)
    assert result.event_id == _append_parameters(first)[0]


def test_second_submitted_postgresql_timeout_is_unknown_without_third_attempt():
    first = _connection(psycopg.errors.QueryCanceled("statement timed out"))
    second = _connection(psycopg.errors.LockNotAvailable("lock timed out"))
    factory = _Factory(first, second)

    with pytest.raises(SecurityAuditOutcomeUnknown) as raised:
        PreTenantAuditClient(
            factory,
            AUTHENTICATION,
        ).append("CREDENTIAL_MISSING", _hmac())

    assert factory.calls == 2
    assert first.closed is True
    assert second.closed is True
    assert _append_parameters(first) == _append_parameters(second)
    assert raised.value.event_id == _append_parameters(first)[0]


def test_deterministic_database_refusal_is_not_retried():
    factory = _Factory(
        _connection(psycopg.errors.InvalidParameterValue("refused")),
        _connection(_individual),
    )

    with pytest.raises(SecurityAuditRefused):
        PreTenantAuditClient(
            factory,
            AUTHENTICATION,
        ).append("CREDENTIAL_MISSING", _hmac())

    assert factory.calls == 1


@pytest.mark.parametrize(
    "append_rows",
    [
        [],
        [
            (uuid4(), NOW, PURGE_AFTER, True, None, False),
            (uuid4(), NOW, PURGE_AFTER, True, None, False),
        ],
        [(None, NOW, PURGE_AFTER, True, None, False)],
        [(None, None, None, False, BUCKET_START, None)],
    ],
)
def test_malformed_database_results_are_unavailable(append_rows):
    with pytest.raises(SecurityAuditUnavailable):
        PreTenantAuditClient(
            _Factory(_connection(append_rows)),
            AUTHENTICATION,
        ).append("CREDENTIAL_MISSING", _hmac())


def test_live_postgresql_append_maps_real_role_and_result(
    migrated_audit_service,
):
    def connect():
        return psycopg.connect(
            role_dsn(
                migrated_audit_service,
                AUTHENTICATION.session_user,
            ),
            autocommit=False,
        )

    result = PreTenantAuditClient(
        connect,
        AUTHENTICATION,
    ).append("CREDENTIAL_MISSING", _hmac())

    assert isinstance(result, StoredAuditAppend)
    assert type(result.event_id) is UUID
    assert result.observed_at.tzinfo is not None
    assert result.purge_after - result.observed_at == timedelta(days=30)


def test_live_postgresql_request_policy_enforces_statement_timeout(
    migrated_audit_service,
):
    factory = security_audit_runtime._audit_producer_connection_factory(
        role_dsn(
            migrated_audit_service,
            AUTHENTICATION.session_user,
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
    factory = security_audit_runtime._audit_producer_connection_factory(
        role_dsn(
            migrated_audit_service,
            AUTHENTICATION.session_user,
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
                AUTHENTICATION,
            ).append("CREDENTIAL_MISSING", _hmac())

    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert isinstance(raised.value.__cause__, psycopg.errors.LockNotAvailable)
