"""Fixed command for one surviving-store process-crash reconciliation."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NoReturn, Protocol

from deployment.postgresql.security_audit_process_crash import (
    ProcessCrashReconciliationReport,
    ProcessCrashReconciliationRequest,
    ProcessCrashReconciliationSecrets,
    SecurityAuditProcessCrashInputError,
    SecurityAuditProcessCrashInterrupted,
    SecurityAuditProcessCrashOutcomeUnknown,
    SecurityAuditProcessCrashReconciliationRunner,
    SecurityAuditProcessCrashRefused,
    SecurityAuditProcessCrashReportingFailed,
    reconstruct_process_crash_conninfo,
)


PROCESS_CRASH_CONTROL_DSN_ENVIRONMENT = (
    "OFARM_SECURITY_AUDIT_PROCESS_CRASH_CONTROL_PG_DSN"
)

_CANONICAL_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{6}Z"
)
_INVALID = b"security-audit process-crash reconciliation command is invalid\n"
_REFUSED = (
    b"security-audit process-crash reconciliation was refused; "
    b"no commit succeeded\n"
)
_INTERRUPTED = (
    b"security-audit process-crash reconciliation was interrupted; "
    b"no commit was sent; do not retry automatically\n"
)
_UNKNOWN = (
    b"security-audit process-crash reconciliation outcome is unknown; "
    b"do not retry automatically\n"
)
_REPORT_FAILED = (
    b"security-audit process-crash reconciliation committed but "
    b"reporting failed; do not retry automatically\n"
)
_CONTROLLED_STATUSES = frozenset({0, 2, 3, 4, 5})


class _Runner(Protocol):
    def run(
        self,
        request: ProcessCrashReconciliationRequest,
        secret_carrier: ProcessCrashReconciliationSecrets,
    ) -> ProcessCrashReconciliationReport: ...


class _RunnerFactory(Protocol):
    def __call__(self) -> _Runner: ...


class _BinaryOutput(Protocol):
    def write(self, value: bytes) -> int: ...

    def flush(self) -> None: ...


@dataclass(slots=True)
class _TerminalState:
    controlled_status: int | None = None
    reported: bool = False


def _finish(state: _TerminalState | None, status: int) -> int:
    if state is not None:
        state.controlled_status = status
        if status == 0:
            state.reported = True
    return status


def _fail(
    stderr: _BinaryOutput,
    status: int,
    line: bytes,
    state: _TerminalState | None,
) -> int:
    try:
        written = stderr.write(line)
        if type(written) is int and written == len(line):
            stderr.flush()
    except BaseException:
        pass
    return _finish(state, status)


def _parse_request(argv: Sequence[str]) -> ProcessCrashReconciliationRequest:
    if (
        len(argv) != 2
        or type(argv[0]) is not str
        or type(argv[1]) is not str
        or argv[0] != "--interval-start"
    ):
        raise ValueError("process-crash command shape differs")
    value = argv[1]
    if len(value) != 27:
        raise ValueError("process-crash interval-start length differs")
    try:
        encoded = value.encode("ascii")
    except UnicodeError as error:
        raise ValueError("process-crash interval-start encoding differs") from error
    if len(encoded) != 27 or _CANONICAL_TIMESTAMP.fullmatch(value) is None:
        raise ValueError("process-crash interval-start is not canonical")
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=timezone.utc
    )
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != value:
        raise ValueError("process-crash interval-start is not canonical")
    return ProcessCrashReconciliationRequest(parsed)


def _secret_carrier(
    environ: Mapping[str, str],
) -> ProcessCrashReconciliationSecrets:
    for name in environ:
        if type(name) is not str or name.startswith("PG"):
            raise ValueError("process-crash ambient PostgreSQL authority exists")
    value = environ.get(PROCESS_CRASH_CONTROL_DSN_ENVIRONMENT)
    if type(value) is not str or not value:
        raise ValueError("process-crash control route is missing")
    reconstructed = reconstruct_process_crash_conninfo(value)
    return ProcessCrashReconciliationSecrets(reconstructed)


def run_fixed_security_audit_process_crash_cli(
    *,
    argv: Sequence[str],
    environ: Mapping[str, str],
    stdout: _BinaryOutput,
    stderr: _BinaryOutput,
    runner_factory: _RunnerFactory = SecurityAuditProcessCrashReconciliationRunner,
    terminal_state: _TerminalState | None = None,
) -> int:
    """Execute the closed command through explicit inputs and binary sinks."""

    try:
        request = _parse_request(argv)
        secret_carrier = _secret_carrier(environ)
        runner = runner_factory()
    except Exception:
        return _fail(stderr, 2, _INVALID, terminal_state)
    except BaseException:
        return _fail(stderr, 3, _INTERRUPTED, terminal_state)
    try:
        report = runner.run(request, secret_carrier)
    except SecurityAuditProcessCrashInputError:
        return _fail(stderr, 2, _INVALID, terminal_state)
    except SecurityAuditProcessCrashRefused:
        return _fail(stderr, 3, _REFUSED, terminal_state)
    except SecurityAuditProcessCrashInterrupted:
        return _fail(stderr, 3, _INTERRUPTED, terminal_state)
    except SecurityAuditProcessCrashOutcomeUnknown:
        return _fail(stderr, 4, _UNKNOWN, terminal_state)
    except SecurityAuditProcessCrashReportingFailed:
        return _fail(stderr, 5, _REPORT_FAILED, terminal_state)
    except Exception:
        return _fail(stderr, 3, _REFUSED, terminal_state)
    except BaseException:
        return _fail(stderr, 3, _INTERRUPTED, terminal_state)
    try:
        report_bytes = report.report_bytes
        written = stdout.write(report_bytes)
        if type(written) is not int or written != len(report_bytes):
            raise OSError("process-crash report write was incomplete")
        stdout.flush()
    except BaseException:
        return _fail(stderr, 5, _REPORT_FAILED, terminal_state)
    return _finish(terminal_state, 0)


def main(
    argv: Sequence[str] | None = None,
    *,
    _terminal_state: _TerminalState | None = None,
) -> int:
    actual_argv = tuple(sys.argv[1:] if argv is None else argv)
    return run_fixed_security_audit_process_crash_cli(
        argv=actual_argv,
        environ=os.environ,
        stdout=sys.stdout.buffer,
        stderr=sys.stderr.buffer,
        terminal_state=_terminal_state,
    )


def _freeze_module_status(
    invoke: Callable[[_TerminalState], int],
    state: _TerminalState,
) -> int:
    """Freeze one controlled status without propagating caller-selected exits."""

    try:
        returned = invoke(state)
        if state.controlled_status is None:
            if type(returned) is int and returned in _CONTROLLED_STATUSES:
                state.controlled_status = returned
            else:
                state.controlled_status = 3
    except BaseException:
        if state.reported:
            state.controlled_status = 0
        elif state.controlled_status is None:
            state.controlled_status = 3
    status = state.controlled_status
    if type(status) is not int or status not in _CONTROLLED_STATUSES:
        return 3
    return status


def _invoke_main(state: _TerminalState) -> int:
    return main(_terminal_state=state)


def _module_entry() -> NoReturn:
    state = _TerminalState()
    controlled_status = 3
    evaluated = False
    while True:
        try:
            if not evaluated:
                controlled_status = _freeze_module_status(_invoke_main, state)
                evaluated = True
            os._exit(controlled_status)
        except BaseException:
            if state.reported:
                controlled_status = 0
            elif (
                type(state.controlled_status) is int
                and state.controlled_status in _CONTROLLED_STATUSES
            ):
                controlled_status = state.controlled_status
            else:
                controlled_status = 3
            evaluated = True


if __name__ == "__main__":
    _module_entry()


__all__ = (
    "PROCESS_CRASH_CONTROL_DSN_ENVIRONMENT",
    "main",
    "run_fixed_security_audit_process_crash_cli",
)
