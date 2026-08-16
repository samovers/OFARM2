"""Fixed correlation-HMAC retirement execution regressions."""

from __future__ import annotations

import inspect
import io
import math
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import psycopg
import pytest
from google.cloud import kms_v1
from google.protobuf import duration_pb2, timestamp_pb2

from deployment.postgresql.run_security_audit_hmac_retirement import (
    RETIREMENT_DSN_ENVIRONMENT,
    RETIREMENT_KMS_PARENT_ENVIRONMENT,
    run_fixed_security_audit_hmac_retirement_cli,
)
from deployment.postgresql.security_audit_hmac_retirement import (
    ADMISSION_BUDGET_NS,
    KMS_READ_TIMEOUT_SECONDS,
    KmsHmacRetirementClient,
    POSTGRES_CONNECTION_OPTIONS,
    POSTGRES_CONNECT_TIMEOUT_SECONDS,
    PostgresConnectionFactory,
    SecurityAuditHmacRetirementOutcome,
    SecurityAuditHmacRetirementOutcomeUnknown,
    SecurityAuditHmacRetirementPhase,
    SecurityAuditHmacRetirementPhaseCarrier,
    SecurityAuditHmacRetirementRefused,
    SecurityAuditHmacRetirementResult,
    SecurityAuditHmacRetirementRunner,
    SecurityAuditHmacRetirementUnavailable,
    render_security_audit_hmac_retirement_report,
)
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn,
)

ROOT = Path(__file__).resolve().parents[2]
PARENT = (
    "projects/example/locations/europe-west1/keyRings/ofarm/"
    "cryptoKeys/pretenant-correlation"
)
RESOURCE = f"{PARENT}/cryptoKeyVersions/1"
CONNINFO = "dbname=ofarm_security_audit"
DATABASE_TIME = datetime(2030, 1, 1, tzinfo=timezone.utc)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
NANOSECONDS = 1_000_000_000
DESTROY_DURATION_NS = 86_400 * NANOSECONDS
CLOCK_SKEW_NS = NANOSECONDS
STATES = kms_v1.CryptoKeyVersion.CryptoKeyVersionState
ALGORITHMS = kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm

def _datetime_ns(value: datetime) -> int:
    delta = value.astimezone(timezone.utc) - EPOCH
    return (
        (delta.days * 86_400 + delta.seconds) * NANOSECONDS
        + delta.microseconds * 1_000
    )

DATABASE_NS = _datetime_ns(DATABASE_TIME)

def _timestamp(value_ns: int) -> timestamp_pb2.Timestamp:
    seconds, nanos = divmod(value_ns, NANOSECONDS)
    return timestamp_pb2.Timestamp(seconds=seconds, nanos=nanos)

def _version(
    number: int,
    *,
    state=STATES.ENABLED,
    destroy_ns: int | None = None,
    event_ns: int | None = None,
    **changes,
) -> kms_v1.CryptoKeyVersion:
    values = {
        "name": f"{PARENT}/cryptoKeyVersions/{number}",
        "state": state,
        "algorithm": ALGORITHMS.HMAC_SHA256,
        "protection_level": kms_v1.ProtectionLevel.HSM,
        **changes,
    }
    if destroy_ns is not None:
        values["destroy_time"] = _timestamp(destroy_ns)
    if event_ns is not None:
        values["destroy_event_time"] = _timestamp(event_ns)
    return kms_v1.CryptoKeyVersion(**values)

def _parent_key(**changes) -> kms_v1.CryptoKey:
    values = {
        "name": PARENT,
        "purpose": kms_v1.CryptoKey.CryptoKeyPurpose.MAC,
        "version_template": kms_v1.CryptoKeyVersionTemplate(
            algorithm=ALGORITHMS.HMAC_SHA256,
            protection_level=kms_v1.ProtectionLevel.HSM,
        ),
        "destroy_scheduled_duration": duration_pb2.Duration(seconds=86_400),
        "import_only": False,
        **changes,
    }
    return kms_v1.CryptoKey(**values)
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
    def __init__(self, mode, deadline, database_time, session_user):
        self.mode = mode
        self.deadline = deadline
        self.database_time = database_time
        self.session_user = session_user
        self.autocommit = False
        self.closed = False
        self.executions = []
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
        if normalized.startswith("SET TRANSACTION"):
            return _Cursor([])
        if normalized.startswith("SELECT * FROM ofarm_security.observe_"):
            version = parameters[0]
            deadline = self.deadline if version == 1 else None
            return _Cursor([(version, version == 2, deadline)])
        if normalized == "SELECT session_user, clock_timestamp()":
            return _Cursor([(self.session_user, self.database_time)])
        raise AssertionError(normalized)
class _ConnectionFactory:
    def __init__(
        self,
        deadline,
        *,
        database_time=DATABASE_TIME,
        session_user="ofarm_security_audit_control_login",
    ):
        self.deadline = deadline
        self.database_time = database_time
        self.session_user = session_user
        self.calls = []
        self.connections = []
    def __call__(self, conninfo, **options):
        self.calls.append((conninfo, options))
        mode = "posture" if not self.connections else "clock"
        connection = _Connection(
            mode,
            self.deadline,
            self.database_time,
            self.session_user,
        )
        self.connections.append(connection)
        return connection
class _Pager:
    def __init__(self, response):
        self._response = response
    @property
    def pages(self):
        return iter((self._response,))
class _KmsClient:
    def __init__(
        self,
        factory=None,
        *,
        observer_target=None,
        fresh_target=None,
        key=None,
        response=None,
        destroy_error=None,
    ):
        self.factory = factory
        self.observer_target = observer_target or _version(1)
        self.fresh_target = fresh_target or self.observer_target
        self.key = _parent_key() if key is None else key
        self.response = response or _version(
            1,
            state=STATES.DESTROY_SCHEDULED,
            destroy_ns=DATABASE_NS + DESTROY_DURATION_NS + 7,
        )
        self.destroy_error = destroy_error
        self.calls = []
        self.version_one_reads = 0
    def list_crypto_key_versions(self, *, request, retry, timeout):
        if self.factory is not None:
            assert self.factory.connections[0].closed
        self.calls.append(("list", request, retry, timeout))
        return _Pager(
            kms_v1.ListCryptoKeyVersionsResponse(
                crypto_key_versions=[self.observer_target, _version(2)]
            )
        )
    def get_crypto_key_version(self, *, request, retry, timeout):
        self.calls.append(("get-version", request, retry, timeout))
        number = int(request.name.rsplit("/", 1)[1])
        if number == 2:
            return _version(2)
        self.version_one_reads += 1
        return (
            self.observer_target
            if self.version_one_reads == 1
            else self.fresh_target
        )
    def get_crypto_key(self, *, request, retry, timeout):
        self.calls.append(("get-key", request, retry, timeout))
        return self.key
    def destroy_crypto_key_version(self, *, request, retry, timeout):
        if self.factory is not None:
            assert self.factory.connections[-1].closed
        self.calls.append(("destroy", request, retry, timeout))
        if self.destroy_error is not None:
            raise self.destroy_error
        return self.response

def _runner(
    *,
    deadline=DATABASE_TIME + timedelta(days=2),
    target=None,
    observer_target=None,
    response=None,
    key=None,
    monotonic=(10_000_000_000, 10_100_000_000),
    database_time=DATABASE_TIME,
    session_user="ofarm_security_audit_control_login",
    destroy_error=None,
):
    factory = _ConnectionFactory(
        deadline,
        database_time=database_time,
        session_user=session_user,
    )
    client = _KmsClient(
        factory,
        observer_target=observer_target,
        fresh_target=target,
        response=response,
        key=key,
        destroy_error=destroy_error,
    )
    phase = SecurityAuditHmacRetirementPhaseCarrier()
    clock = iter(monotonic)
    runner = SecurityAuditHmacRetirementRunner(
        cast(PostgresConnectionFactory, factory),
        cast(KmsHmacRetirementClient, client),
        PARENT,
        phase,
        monotonic_ns=lambda: next(clock),
    )
    return runner, phase, factory, client
@pytest.mark.parametrize("state", [STATES.ENABLED, STATES.DISABLED])
def test_exact_lead_schedules_one_fixed_target_with_conservative_timeout(state):
    runner, phase, factory, client = _runner(target=_version(1, state=state))
    result = runner.run(CONNINFO)
    assert result == SecurityAuditHmacRetirementResult(
        SecurityAuditHmacRetirementOutcome.SCHEDULED,
        DATABASE_NS + DESTROY_DURATION_NS + 7,
        DATABASE_NS + 2 * DESTROY_DURATION_NS,
    )
    assert phase.phase is SecurityAuditHmacRetirementPhase.RESULT_KNOWN
    assert all(connection.closed for connection in factory.connections)
    assert factory.calls == [
        (
            CONNINFO,
            {
                "autocommit": False,
                "connect_timeout": POSTGRES_CONNECT_TIMEOUT_SECONDS,
                "options": POSTGRES_CONNECTION_OPTIONS,
            },
        ),
    ] * 2
    destroy = [call for call in client.calls if call[0] == "destroy"]
    assert len(destroy) == 1
    assert destroy[0][1].name == RESOURCE
    assert destroy[0][2] is None
    assert destroy[0][3] == math.nextafter(4.9, 0.0)
    assert 0 < destroy[0][3] <= 4.9
    assert render_security_audit_hmac_retirement_report(result) == (
        b'{"destructionTime":"2030-01-02T00:00:00.000000007Z",'
        b'"greatestPurgeAfter":"2030-01-03T00:00:00.000000000Z",'
        b'"outcome":"SCHEDULED",'
        b'"schema":"ofarm.security-audit-hmac-retirement-report.v2",'
        b'"targetKeyVersion":1}\n'
    )
def test_deadline_one_microsecond_inside_fixed_lead_refuses_without_mutation():
    runner, phase, _, client = _runner(
        deadline=DATABASE_TIME + timedelta(days=2, microseconds=-1)
    )
    with pytest.raises(SecurityAuditHmacRetirementRefused):
        runner.run(CONNINFO)
    assert phase.phase is SecurityAuditHmacRetirementPhase.PRE_SUBMISSION
    assert not [call for call in client.calls if call[0] == "destroy"]
def test_elapsed_exactly_five_seconds_refuses_before_destroy_method():
    runner, phase, _, client = _runner(
        deadline=None,
        monotonic=(1_000_000_000, 1_000_000_000 + ADMISSION_BUDGET_NS),
    )
    with pytest.raises(SecurityAuditHmacRetirementRefused):
        runner.run(CONNINFO)
    assert phase.phase is SecurityAuditHmacRetirementPhase.PRE_SUBMISSION
    assert not [call for call in client.calls if call[0] == "destroy"]
@pytest.mark.parametrize(
    ("state", "destruction_ns", "outcome"),
    [
        (
            STATES.DESTROY_SCHEDULED,
            DATABASE_NS + CLOCK_SKEW_NS + 1,
            SecurityAuditHmacRetirementOutcome.ALREADY_SCHEDULED,
        ),
        (
            STATES.DESTROY_SCHEDULED,
            DATABASE_NS + DESTROY_DURATION_NS + CLOCK_SKEW_NS,
            SecurityAuditHmacRetirementOutcome.ALREADY_SCHEDULED,
        ),
        (
            STATES.DESTROYED,
            DATABASE_NS + CLOCK_SKEW_NS,
            SecurityAuditHmacRetirementOutcome.ALREADY_DESTROYED,
        ),
    ],
)
def test_conforming_terminal_observation_is_a_mutation_free_result(
    state, destruction_ns, outcome
):
    target = (
        _version(1, state=state, destroy_ns=destruction_ns)
        if state == STATES.DESTROY_SCHEDULED
        else _version(1, state=state, event_ns=destruction_ns)
    )
    runner, phase, _, client = _runner(
        deadline=DATABASE_TIME + timedelta(days=3),
        target=target,
        monotonic=(10_000_000_000,),
    )
    result = runner.run(CONNINFO)
    assert result.outcome is outcome
    assert result.destruction_time_ns == destruction_ns
    assert phase.phase is SecurityAuditHmacRetirementPhase.RESULT_KNOWN
    assert not [call for call in client.calls if call[0] == "destroy"]
@pytest.mark.parametrize(
    ("state", "destroy_ns", "event_ns"),
    [
        (STATES.DESTROY_SCHEDULED, DATABASE_NS + CLOCK_SKEW_NS, None),
        (
            STATES.DESTROY_SCHEDULED,
            DATABASE_NS + DESTROY_DURATION_NS + CLOCK_SKEW_NS + 1,
            None,
        ),
        (STATES.DESTROYED, None, DATABASE_NS + CLOCK_SKEW_NS + 1),
    ],
)
def test_impossible_terminal_provider_time_is_unavailable_without_mutation(
    state, destroy_ns, event_ns
):
    target = _version(
        1,
        state=state,
        destroy_ns=destroy_ns,
        event_ns=event_ns,
    )
    runner, phase, _, client = _runner(
        deadline=DATABASE_TIME + timedelta(days=3),
        target=target,
        monotonic=(10_000_000_000,),
    )
    with pytest.raises(SecurityAuditHmacRetirementUnavailable):
        runner.run(CONNINFO)
    assert phase.phase is SecurityAuditHmacRetirementPhase.PRE_SUBMISSION
    assert not [call for call in client.calls if call[0] == "destroy"]
def test_valid_terminal_provider_time_after_live_deadline_is_refused():
    target = _version(
        1,
        state=STATES.DESTROY_SCHEDULED,
        destroy_ns=DATABASE_NS + 2 * NANOSECONDS,
    )
    runner, _, _, client = _runner(
        deadline=DATABASE_TIME + timedelta(seconds=1),
        target=target,
        monotonic=(10_000_000_000,),
    )
    with pytest.raises(SecurityAuditHmacRetirementRefused):
        runner.run(CONNINFO)
    assert not [call for call in client.calls if call[0] == "destroy"]
@pytest.mark.parametrize(
    "destruction_ns",
    [
        DATABASE_NS + DESTROY_DURATION_NS - CLOCK_SKEW_NS,
        DATABASE_NS + DESTROY_DURATION_NS + ADMISSION_BUDGET_NS + CLOCK_SKEW_NS,
    ],
)
def test_new_response_exact_two_sided_boundaries_are_admitted(destruction_ns):
    response = _version(
        1,
        state=STATES.DESTROY_SCHEDULED,
        destroy_ns=destruction_ns,
    )
    runner, phase, _, _ = _runner(deadline=None, response=response)
    result = runner.run(CONNINFO)
    assert result.destruction_time_ns == destruction_ns
    assert phase.phase is SecurityAuditHmacRetirementPhase.RESULT_KNOWN
@pytest.mark.parametrize(
    "destruction_ns",
    [
        DATABASE_NS + DESTROY_DURATION_NS - CLOCK_SKEW_NS - 1,
        DATABASE_NS + DESTROY_DURATION_NS + ADMISSION_BUDGET_NS
        + CLOCK_SKEW_NS
        + 1,
    ],
)
def test_new_response_one_nanosecond_outside_window_is_outcome_unknown(
    destruction_ns,
):
    response = _version(
        1,
        state=STATES.DESTROY_SCHEDULED,
        destroy_ns=destruction_ns,
    )
    runner, phase, _, client = _runner(deadline=None, response=response)
    with pytest.raises(SecurityAuditHmacRetirementOutcomeUnknown):
        runner.run(CONNINFO)
    assert phase.phase is SecurityAuditHmacRetirementPhase.SUBMITTED
    assert len([call for call in client.calls if call[0] == "destroy"]) == 1
@pytest.mark.parametrize(
    "response",
    [
        _version(
            2,
            state=STATES.DESTROY_SCHEDULED,
            destroy_ns=DATABASE_NS + DESTROY_DURATION_NS,
        ),
        _version(1, state=STATES.DESTROY_SCHEDULED),
        _version(
            1,
            state=STATES.DESTROY_SCHEDULED,
            destroy_ns=DATABASE_NS + DESTROY_DURATION_NS,
            event_ns=DATABASE_NS,
        ),
        _version(
            1,
            state=STATES.DESTROY_SCHEDULED,
            destroy_ns=DATABASE_NS + DESTROY_DURATION_NS,
            algorithm=ALGORITHMS.RSA_SIGN_PSS_2048_SHA256,
        ),
    ],
)
def test_malformed_destroy_response_is_unknown_and_never_retried(response):
    runner, phase, _, client = _runner(deadline=None, response=response)
    with pytest.raises(SecurityAuditHmacRetirementOutcomeUnknown):
        runner.run(CONNINFO)
    assert phase.phase is SecurityAuditHmacRetirementPhase.SUBMITTED
    assert len([call for call in client.calls if call[0] == "destroy"]) == 1
def test_destroy_exception_is_unknown_without_retry():
    runner, phase, _, client = _runner(deadline=None, destroy_error=RuntimeError())
    with pytest.raises(SecurityAuditHmacRetirementOutcomeUnknown):
        runner.run(CONNINFO)
    assert phase.phase is SecurityAuditHmacRetirementPhase.SUBMITTED
    assert len([call for call in client.calls if call[0] == "destroy"]) == 1
@pytest.mark.parametrize(
    "key",
    [
        _parent_key(purpose=kms_v1.CryptoKey.CryptoKeyPurpose.ENCRYPT_DECRYPT),
        _parent_key(destroy_scheduled_duration=duration_pb2.Duration(seconds=30)),
        _parent_key(
            version_template=kms_v1.CryptoKeyVersionTemplate(
                algorithm=ALGORITHMS.HMAC_SHA256,
                protection_level=kms_v1.ProtectionLevel.SOFTWARE,
            )
        ),
        _parent_key(import_only=True),
    ],
)
def test_wrong_parent_policy_refuses_before_fresh_target_or_mutation(key):
    runner, phase, _, client = _runner(key=key)
    with pytest.raises(SecurityAuditHmacRetirementRefused):
        runner.run(CONNINFO)
    assert phase.phase is SecurityAuditHmacRetirementPhase.PRE_SUBMISSION
    assert client.version_one_reads == 1
    assert not [call for call in client.calls if call[0] == "destroy"]
@pytest.mark.parametrize(
    ("session_user", "database_time", "error"),
    [
        (
            "ofarm_security_audit_reader_login",
            DATABASE_TIME,
            SecurityAuditHmacRetirementRefused,
        ),
        (
            "ofarm_security_audit_control_login",
            DATABASE_TIME.replace(tzinfo=None),
            SecurityAuditHmacRetirementUnavailable,
        ),
    ],
)
def test_database_clock_requires_exact_control_role_and_aware_time(
    session_user, database_time, error
):
    runner, phase, factory, client = _runner(
        session_user=session_user,
        database_time=database_time,
    )
    with pytest.raises(error):
        runner.run(CONNINFO)
    assert factory.connections[-1].closed
    assert phase.phase is SecurityAuditHmacRetirementPhase.PRE_SUBMISSION
    assert not [call for call in client.calls if call[0] == "destroy"]
def test_kms_protocol_exposes_only_fixed_reads_and_destroy():
    methods = {
        name
        for name, value in inspect.getmembers(
            KmsHmacRetirementClient, inspect.isfunction
        )
        if not name.startswith("_")
    }
    assert methods == {
        "destroy_crypto_key_version",
        "get_crypto_key",
        "get_crypto_key_version",
        "list_crypto_key_versions",
    }
    assert KMS_READ_TIMEOUT_SECONDS == 5.0
class _CliRunner:
    def __init__(self, phase, mode):
        self.phase = phase
        self.mode = mode
    def run(self, conninfo):
        assert conninfo == CONNINFO
        if self.mode == "refused":
            raise SecurityAuditHmacRetirementRefused
        if self.mode == "submitted":
            self.phase._advance(
                SecurityAuditHmacRetirementPhase.PRE_SUBMISSION,
                SecurityAuditHmacRetirementPhase.SUBMITTED,
            )
            raise RuntimeError("CANARY_RETIREMENT_CREDENTIAL")
        if self.mode != "unphased":
            self.phase._advance(
                SecurityAuditHmacRetirementPhase.PRE_SUBMISSION,
                SecurityAuditHmacRetirementPhase.RESULT_KNOWN,
            )
        return SecurityAuditHmacRetirementResult(
            SecurityAuditHmacRetirementOutcome.ALREADY_DESTROYED,
            DATABASE_NS,
            None,
        )

def _cli(mode, *, argv=(), environ=None, stdout=None, stderr=None):
    output = io.BytesIO() if stdout is None else stdout
    errors = io.BytesIO() if stderr is None else stderr
    def factory(parent, phase):
        assert parent == PARENT
        if mode == "unexpected":
            raise RuntimeError("CANARY_RETIREMENT_CREDENTIAL")
        return _CliRunner(phase, mode)
    code = run_fixed_security_audit_hmac_retirement_cli(
        argv=argv,
        environ=environ
        or {
            RETIREMENT_DSN_ENVIRONMENT: CONNINFO,
            RETIREMENT_KMS_PARENT_ENVIRONMENT: PARENT,
        },
        stdout=output,
        stderr=errors,
        runner_factory=factory,
    )
    return code, output, errors
@pytest.mark.parametrize(
    ("mode", "exit_code", "diagnostic"),
    [
        ("refused", 1, b"security-audit HMAC retirement refused\n"),
        (
            "unexpected",
            3,
            b"security-audit HMAC retirement unavailable before submission\n",
        ),
        (
            "unphased",
            3,
            b"security-audit HMAC retirement unavailable before submission\n",
        ),
        (
            "submitted",
            4,
            b"security-audit HMAC retirement outcome unknown; "
            b"do not retry automatically\n",
        ),
    ],
)
def test_cli_sanitizes_failure_by_phase_without_canary(mode, exit_code, diagnostic):
    code, output, errors = _cli(mode)
    assert code == exit_code
    assert output.getvalue() == b""
    assert errors.getvalue() == diagnostic
    assert b"CANARY" not in errors.getvalue()
def test_cli_success_is_one_canonical_line_and_zero_stderr():
    code, output, errors = _cli("known")
    assert code == 0
    assert errors.getvalue() == b""
    assert output.getvalue() == (
        b'{"destructionTime":"2030-01-01T00:00:00.000000000Z",'
        b'"greatestPurgeAfter":null,"outcome":"ALREADY_DESTROYED",'
        b'"schema":"ofarm.security-audit-hmac-retirement-report.v2",'
        b'"targetKeyVersion":1}\n'
    )
@pytest.mark.parametrize(
    ("argv", "environ"),
    [
        (("--help",), {}),
        ((), {}),
        (
            (),
            {
                RETIREMENT_DSN_ENVIRONMENT: "not=valid=conninfo",
                RETIREMENT_KMS_PARENT_ENVIRONMENT: PARENT,
            },
        ),
        (
            (),
            {
                RETIREMENT_DSN_ENVIRONMENT: CONNINFO,
                RETIREMENT_KMS_PARENT_ENVIRONMENT: PARENT + "/cryptoKeyVersions/1",
            },
        ),
    ],
)
def test_cli_static_invalid_never_constructs_runner(argv, environ):
    called = False
    def factory(parent, phase):
        nonlocal called
        called = True
        raise AssertionError
    output = io.BytesIO()
    errors = io.BytesIO()
    code = run_fixed_security_audit_hmac_retirement_cli(
        argv=argv,
        environ=environ,
        stdout=output,
        stderr=errors,
        runner_factory=factory,
    )
    assert code == 2
    assert not called
    assert output.getvalue() == b""
    assert errors.getvalue() == (
        b"security-audit HMAC retirement command invalid\n"
    )
class _BrokenOutput:
    def __init__(self, mode):
        self.mode = mode
        self.value = b""
    def write(self, value):
        self.value += value[:3]
        if self.mode == "write":
            raise OSError("CANARY_RETIREMENT_CREDENTIAL")
        return 3
    def flush(self):
        if self.mode == "flush":
            raise OSError("CANARY_RETIREMENT_CREDENTIAL")
@pytest.mark.parametrize("mode", ["write", "short", "flush"])
def test_known_result_reporting_failure_is_exit_five(mode):
    stdout = _BrokenOutput(mode)
    code, _, errors = _cli("known", stdout=stdout)
    assert code == 5
    assert stdout.value
    assert errors.getvalue() == (
        b"security-audit HMAC retirement report delivery failed; "
        b"do not retry automatically\n"
    )
    assert b"CANARY" not in errors.getvalue()
def test_stderr_failure_is_swallowed_after_numeric_exit_is_fixed():
    broken = _BrokenOutput("write")
    code, output, _ = _cli("unexpected", stderr=broken)
    assert code == 3
    assert output.getvalue() == b""
    assert broken.value == b"sec"
@pytest.mark.parametrize(
    ("mode", "exit_code", "diagnostic"),
    [
        (
            "pre",
            3,
            "security-audit HMAC retirement unavailable before submission\n",
        ),
        (
            "submitted",
            4,
            "security-audit HMAC retirement outcome unknown; "
            "do not retry automatically\n",
        ),
        (
            "result",
            5,
            "security-audit HMAC retirement report delivery failed; "
            "do not retry automatically\n",
        ),
    ],
)
def test_subprocess_unexpected_canary_never_reaches_excepthook(
    mode, exit_code, diagnostic
):
    program = textwrap.dedent(
        f"""
        import io
        import sys
        from deployment.postgresql.run_security_audit_hmac_retirement import run_fixed_security_audit_hmac_retirement_cli
        from deployment.postgresql.security_audit_hmac_retirement import SecurityAuditHmacRetirementPhase
        mode = {mode!r}
        class Runner:
            def __init__(self, phase): self.phase = phase
            def run(self, conninfo):
                if mode == "submitted":
                    self.phase._advance(SecurityAuditHmacRetirementPhase.PRE_SUBMISSION, SecurityAuditHmacRetirementPhase.SUBMITTED)
                    raise RuntimeError("CANARY_RETIREMENT_CREDENTIAL")
                self.phase._advance(SecurityAuditHmacRetirementPhase.PRE_SUBMISSION, SecurityAuditHmacRetirementPhase.RESULT_KNOWN)
                return object()
        def factory(parent, phase):
            if mode == "pre": raise RuntimeError("CANARY_RETIREMENT_CREDENTIAL")
            return Runner(phase)
        out, err = io.BytesIO(), io.BytesIO()
        code = run_fixed_security_audit_hmac_retirement_cli(
            argv=(),
            environ={{"OFARM_SECURITY_AUDIT_CONTROL_PG_DSN": "dbname=ofarm", "OFARM_CORRELATION_HMAC_KMS_KEY_RESOURCE": {PARENT!r}}},
            stdout=out,
            stderr=err,
            runner_factory=factory,
        )
        sys.stdout.buffer.write(out.getvalue())
        sys.stderr.buffer.write(err.getvalue())
        raise SystemExit(code)
        """
    )
    process = subprocess.run(
        [sys.executable, "-c", program],
        cwd=ROOT,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert process.returncode == exit_code
    assert process.stdout == b""
    assert process.stderr == diagnostic.encode("ascii")
    assert b"CANARY" not in process.stderr
    assert b"Traceback" not in process.stderr
def test_operator_contract_keeps_iam_and_timing_evidence_external():
    documentation = (ROOT / "deployment/postgresql/README.md").read_text()
    normalized = " ".join(documentation.split()).lower()
    required = {
        "cloudkms.cryptoKeys.get",
        "cloudkms.cryptoKeyVersions.get",
        "cloudkms.cryptoKeyVersions.list",
        "cloudkms.cryptoKeyVersions.destroy",
    }
    assert required <= set(documentation.split("`"))
    assert (
        "production audit runtime identity must never receive `destroy`"
        in normalized
    )
    assert "no state change can be accepted more than five seconds" in normalized
    assert "intentionally non-deployable" in normalized
    assert "does not authorize deployment" in normalized
def test_live_control_route_clock_is_observed_without_real_kms_mutation(
    migrated_audit_service,
):
    target = _version(
        1,
        state=STATES.DESTROYED,
        event_ns=_datetime_ns(datetime(2020, 1, 1, tzinfo=timezone.utc)),
    )
    client = _KmsClient(observer_target=target, fresh_target=target)
    phase = SecurityAuditHmacRetirementPhaseCarrier()
    runner = SecurityAuditHmacRetirementRunner(
        cast(PostgresConnectionFactory, psycopg.connect),
        cast(KmsHmacRetirementClient, client),
        PARENT,
        phase,
        monotonic_ns=lambda: 1,
    )
    result = runner.run(
        role_dsn(migrated_audit_service, "ofarm_security_audit_control_login")
    )
    assert result.outcome is SecurityAuditHmacRetirementOutcome.ALREADY_DESTROYED
    assert phase.phase is SecurityAuditHmacRetirementPhase.RESULT_KNOWN
    assert not [call for call in client.calls if call[0] == "destroy"]
