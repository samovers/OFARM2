"""Fixed command adapter for one correlation-HMAC retirement attempt."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from typing import Protocol, cast

import psycopg
from google.cloud import kms_v1

from deployment.postgresql.security_audit_hmac_retirement import (
    KmsHmacRetirementClient,
    PostgresConnectionFactory,
    SecurityAuditHmacRetirementPhase,
    SecurityAuditHmacRetirementPhaseCarrier,
    SecurityAuditHmacRetirementRefused,
    SecurityAuditHmacRetirementResult,
    SecurityAuditHmacRetirementRunner,
    render_security_audit_hmac_retirement_report,
    validated_hmac_retirement_parent,
)

RETIREMENT_DSN_ENVIRONMENT = "OFARM_SECURITY_AUDIT_CONTROL_PG_DSN"
RETIREMENT_KMS_PARENT_ENVIRONMENT = "OFARM_CORRELATION_HMAC_KMS_KEY_RESOURCE"

_DIAGNOSTICS = {
    1: b"security-audit HMAC retirement refused\n",
    2: b"security-audit HMAC retirement command invalid\n",
    3: b"security-audit HMAC retirement unavailable before submission\n",
    4: (
        b"security-audit HMAC retirement outcome unknown; "
        b"do not retry automatically\n"
    ),
    5: (
        b"security-audit HMAC retirement report delivery failed; "
        b"do not retry automatically\n"
    ),
}

class _InvalidCommand(ValueError):
    pass

class _Runner(Protocol):
    def run(self, conninfo: str) -> SecurityAuditHmacRetirementResult: ...

class _RunnerFactory(Protocol):
    def __call__(
        self,
        parent: str,
        phase: SecurityAuditHmacRetirementPhaseCarrier,
    ) -> _Runner: ...

class _BinaryOutput(Protocol):
    def write(self, value: bytes) -> int: ...

    def flush(self) -> None: ...

def _inputs(
    argv: Sequence[str], environ: Mapping[str, str]
) -> tuple[str, str]:
    if len(argv) != 0:
        raise _InvalidCommand
    conninfo = environ.get(RETIREMENT_DSN_ENVIRONMENT)
    parent = environ.get(RETIREMENT_KMS_PARENT_ENVIRONMENT)
    if (
        type(conninfo) is not str
        or not conninfo.strip()
        or type(parent) is not str
    ):
        raise _InvalidCommand
    try:
        psycopg.conninfo.conninfo_to_dict(conninfo)
        validated_parent = validated_hmac_retirement_parent(parent)
    except (psycopg.Error, TypeError, ValueError):
        raise _InvalidCommand from None
    return conninfo, validated_parent


def _new_runner(
    parent: str,
    phase: SecurityAuditHmacRetirementPhaseCarrier,
) -> SecurityAuditHmacRetirementRunner:
    client = kms_v1.KeyManagementServiceClient()
    return SecurityAuditHmacRetirementRunner(
        cast(PostgresConnectionFactory, psycopg.connect),
        cast(KmsHmacRetirementClient, client),
        parent,
        phase,
    )


def _phase_exit(
    phase: SecurityAuditHmacRetirementPhase,
    pre_submission_exit: int,
) -> int:
    if phase is SecurityAuditHmacRetirementPhase.RESULT_KNOWN:
        return 5
    if phase is SecurityAuditHmacRetirementPhase.SUBMITTED:
        return 4
    return pre_submission_exit


def _fail(stderr: _BinaryOutput, exit_code: int) -> int:
    line = _DIAGNOSTICS[exit_code]
    try:
        written = stderr.write(line)
        if type(written) is not int or written != len(line):
            raise OSError
        stderr.flush()
    except Exception:
        pass
    return exit_code


def run_fixed_security_audit_hmac_retirement_cli(
    *,
    argv: Sequence[str],
    environ: Mapping[str, str],
    stdout: _BinaryOutput,
    stderr: _BinaryOutput,
    runner_factory: _RunnerFactory = _new_runner,
) -> int:
    """Run the closed binary protocol through explicit dependency seams."""

    phase = SecurityAuditHmacRetirementPhaseCarrier()
    try:
        conninfo, parent = _inputs(argv, environ)
        runner = runner_factory(parent, phase)
        result = runner.run(conninfo)
        if phase.phase is not SecurityAuditHmacRetirementPhase.RESULT_KNOWN:
            raise RuntimeError
        report = render_security_audit_hmac_retirement_report(result)
        written = stdout.write(report)
        if type(written) is not int or written != len(report):
            raise OSError
        stdout.flush()
        return 0
    except _InvalidCommand:
        exit_code = _phase_exit(phase.phase, 2)
    except SecurityAuditHmacRetirementRefused:
        exit_code = _phase_exit(phase.phase, 1)
    except Exception:
        exit_code = _phase_exit(phase.phase, 3)
    return _fail(stderr, exit_code)


def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = tuple(sys.argv[1:] if argv is None else argv)
    return run_fixed_security_audit_hmac_retirement_cli(
        argv=actual_argv,
        environ=os.environ,
        stdout=sys.stdout.buffer,
        stderr=sys.stderr.buffer,
    )


if __name__ == "__main__":
    raise SystemExit(main())
