"""Focused evidence for the closed temporary audit-export lifecycle."""

from __future__ import annotations

import ast
import base64
import hashlib
import hmac
import json
import socket
import struct
import time
from inspect import signature
from uuid import UUID, uuid4

import psycopg
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from psycopg import sql

from conformance import rewrite_architecture_check as architecture
from deployment.postgresql import security_audit_break_glass as break_glass
from deployment.postgresql.audit_contract import (
    EXPORT_ACCESS_PURPOSE_IDENTITY,
    EXPORT_FUNCTION_IDENTITY,
    EXPORT_MAX_BYTES,
    EXPORT_MAX_ROWS,
)
from deployment.postgresql.catalog_identity import verify_catalog_identity
from deployment.postgresql.security_audit_approval import SecurityAuditDualApprovalVerifier
from deployment.postgresql.security_audit_break_glass import (
    SecurityAuditBreakGlassFailed,
    SecurityAuditBreakGlassOutcomeUnknown,
    SecurityAuditBreakGlassQuarantined,
    SecurityAuditBreakGlassRefused,
    SecurityAuditBreakGlassRunner,
    SecurityAuditBreakGlassSecrets,
)
from deployment.postgresql.security_audit_export import SecurityAuditExportRunner
from deployment.postgresql.version_policy import SUPPORTED_POSTGRESQL_SERVER_VERSION, SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM
from kernel.tests.postgresql_audit_support import audit_service_fixture, role_dsn as _role_dsn  # noqa: F401


AUTHORITY_SCHEMA = "ofarm.security-audit-break-glass-authority-receipt.v1"
REQUEST_SCHEMA = "ofarm.security-audit-break-glass-export-request.v2"
STATEMENT_SCHEMA = "ofarm.security-audit-break-glass-export-approval.v1"
BUNDLE_SCHEMA = "ofarm.security-audit-break-glass-approval-bundle.v1"
AUDIENCE = "ofarm.security-audit-break-glass-export.v1"
AUTHORITY_DOMAIN = b"OFARM_SECURITY_AUDIT_BREAK_GLASS_AUTHORITY_RECEIPT_V1\x00"
APPROVAL_DOMAIN = b"OFARM_SECURITY_AUDIT_BREAK_GLASS_EXPORT_APPROVAL_V1\x00"
OPERATION_ID = UUID("123e4567-e89b-42d3-a456-426614174000")


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def _b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _public_key(key):
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _key_id(public_key):
    value = {"crv": "Ed25519", "kty": "OKP", "x": _b64(public_key)}
    return _b64(hashlib.sha256(_canonical(value)).digest())


def _material(store_id, now_us, *, operation_id=OPERATION_ID):
    observer = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    approvers = tuple(
        (
            Ed25519PrivateKey.from_private_bytes(bytes(range(start, start + 32))),
            f"APPROVER_{name}",
            f"DOMAIN_{name}",
        )
        for start, name in ((1, "A"), (2, "B"))
    )
    entries = [
        {
            "approverId": approver,
            "independenceDomain": domain,
            "keyId": _key_id(_public_key(key)),
            "publicKey": _b64(_public_key(key)),
        }
        for key, approver, domain in approvers
    ]
    payload = _canonical(
        {
            "approvers": entries,
            "audience": AUDIENCE,
            "expiresAtUnixMicroseconds": now_us + 240_000_000,
            "observedAtUnixMicroseconds": now_us - 1_000_000,
            "schemaVersion": AUTHORITY_SCHEMA,
        }
    )
    authority = _canonical(
        {
            "payload": _b64(payload),
            "signature": _b64(observer.sign(AUTHORITY_DOMAIN + payload)),
        }
    )
    request = _canonical(
        {
            "audience": AUDIENCE,
            "authorityReceiptDigest": _digest(authority),
            "cursor": None,
            "expiresAtUnixMicroseconds": now_us + 120_000_000,
            "functionIdentity": EXPORT_FUNCTION_IDENTITY,
            "maxBytes": EXPORT_MAX_BYTES,
            "maxPages": 1,
            "maxRows": EXPORT_MAX_ROWS,
            "notBeforeUnixMicroseconds": now_us - 500_000,
            "operationId": str(operation_id),
            "purpose": EXPORT_ACCESS_PURPOSE_IDENTITY,
            "schemaVersion": REQUEST_SCHEMA,
            "storeMigrationExecutionId": str(store_id),
        }
    )
    approvals = []
    for key, approver, domain in approvers:
        statement = _canonical(
            {
                "approverId": approver,
                "audience": AUDIENCE,
                "authorityReceiptDigest": _digest(authority),
                "independenceDomain": domain,
                "keyId": _key_id(_public_key(key)),
                "operationId": str(operation_id),
                "requestDigest": _digest(request),
                "schemaVersion": STATEMENT_SCHEMA,
            }
        )
        approvals.append(
            {
                "signature": _b64(key.sign(APPROVAL_DOMAIN + statement)),
                "statement": _b64(statement),
            }
        )
    bundle = _canonical(
        {
            "approvals": approvals,
            "request": _b64(request),
            "schemaVersion": BUNDLE_SCHEMA,
        }
    )
    return _public_key(observer), authority, bundle


def _fixed_error(error_type, call):
    with pytest.raises(error_type) as caught:
        call()
    assert (caught.value.args, caught.value.__cause__, caught.value.__context__, str(caught.value)) == ((), None, None, "")
    return caught.value


def _store_id(state):
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        return admin.execute(
            "SELECT execution_id FROM ofarm_security.schema_migration "
            "WHERE version = 1"
        ).fetchone()[0]


def _random_bytes(length):
    return bytes((index % 251) + 1 for index in range(length))


def _dependencies(
    observer, *, factory=psycopg.connect, exporter=None, clock=time.time_ns
):
    return break_glass._Dependencies(
        connection_factory=factory,
        time_ns=clock,
        random_bytes=_random_bytes,
        approval_verifier=SecurityAuditDualApprovalVerifier(observer),
        export_runner=exporter or SecurityAuditExportRunner(),
        catalog_verifier=verify_catalog_identity,
    )


def _case(state, operation_id=None, now_us=None):
    operation_id = operation_id or uuid4()
    now_us = now_us or time.time_ns() // 1_000
    observer, authority, bundle = _material(
        _store_id(state), now_us, operation_id=operation_id
    )
    secret = SecurityAuditBreakGlassSecrets(
        state["target_admin_dsn"],
        _role_dsn(state, "ofarm_security_audit_control_login"),
    )
    return operation_id, now_us, observer, authority, bundle, secret


def _count(state, operation_id):
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        return admin.execute(
            "SELECT count(*) FROM "
            "ofarm_security.temporary_export_approval_consumption "
            "WHERE operation_id = %s",
            (operation_id,),
        ).fetchone()[0]


def _role_exists(state):
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        return admin.execute(
            "SELECT to_regrole('ofarm_security_audit_export_login') IS NOT NULL"
        ).fetchone()[0]


def _create_exact(state, expected):
    with psycopg.connect(state["target_admin_dsn"]) as admin:
        break_glass._configure_login(admin, expected)
        admin.commit()


class _TimeSequence:
    def __init__(self, *values):
        self.values = values
        self.calls = 0

    def __call__(self):
        if self.calls >= len(self.values):
            raise AssertionError("unexpected authority-time observation")
        value = self.values[self.calls]
        self.calls += 1
        return value * 1_000


class _FailingExport:
    def __init__(self, canary):
        self.canary = canary
        self.calls = 0

    def run(self, _control, _export, _cursor):
        self.calls += 1
        raise RuntimeError(self.canary)


class _Proxy:
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return getattr(self.connection, name)


class _CommitRaise(_Proxy):
    def __init__(self, connection, canary):
        super().__init__(connection)
        self.canary = canary

    def commit(self):
        self.connection.commit()
        raise RuntimeError(self.canary)


class _CommitFactory:
    def __init__(self, user, occurrence, canary, failure=None):
        self.user = user
        self.occurrence = occurrence
        self.canary = canary
        self.failure = failure
        self.count = 0

    def __call__(self, conninfo, **kwargs):
        connection = psycopg.connect(conninfo, **kwargs)
        user = psycopg.conninfo.conninfo_to_dict(conninfo).get("user")
        if user == self.user:
            self.count += 1
            if self.count == self.failure:
                connection.close()
                raise RuntimeError(self.canary)
            if self.count == self.occurrence:
                return _CommitRaise(connection, self.canary)
        return connection


class _HookCommit(_Proxy):
    def __init__(self, connection, owner):
        super().__init__(connection)
        self.owner = owner

    def commit(self):
        self.connection.commit()
        if not self.owner.triggered:
            self.owner.triggered = True
            self.owner.callback()


class _AfterControlCommit:
    def __init__(self, callback):
        self.callback = callback
        self.triggered = False

    def __call__(self, conninfo, **kwargs):
        connection = psycopg.connect(conninfo, **kwargs)
        user = psycopg.conninfo.conninfo_to_dict(conninfo).get("user")
        if user == "ofarm_security_audit_control_login":
            return _HookCommit(connection, self)
        return connection


class _BeforeNoLogin(_Proxy):
    def __init__(self, connection, owner):
        super().__init__(connection)
        self.owner = owner

    def execute(self, query, parameters=None):
        render = getattr(query, "as_string", None)
        statement = render(self.connection) if callable(render) else query
        if statement == (
            'ALTER ROLE "ofarm_security_audit_export_login" NOLOGIN'
        ) and not self.owner.triggered:
            self.owner.triggered = True
            self.owner.callback()
        return self.connection.execute(query, parameters)


class _BeforeNoLoginFactory:
    def __init__(self, callback):
        self.callback = callback
        self.triggered = False

    def __call__(self, conninfo, **kwargs):
        return _BeforeNoLogin(psycopg.connect(conninfo, **kwargs), self)


class _ClockCursor(_Proxy):
    def __init__(self, cursor, observations):
        super().__init__(cursor)
        self.observations = observations
        self.recorded = False

    def fetchone(self):
        row = self.connection.fetchone()
        if not self.recorded and type(row) is tuple:
            self.observations.append(row[0])
            self.recorded = True
        return row


class _ClockConnection(_Proxy):
    def __init__(self, connection, owner):
        super().__init__(connection)
        self.owner = owner

    def execute(self, query, parameters=None):
        cursor = self.connection.execute(query, parameters)
        if query == break_glass._CLOCK_SQL:
            return _ClockCursor(cursor, self.owner.observations)
        return cursor


class _ClockFactory:
    def __init__(self):
        self.observations = []

    def __call__(self, conninfo, **kwargs):
        return _ClockConnection(psycopg.connect(conninfo, **kwargs), self)


class _InspectingExport:
    def __init__(self, admin_dsn):
        self.admin_dsn = admin_dsn
        self.valid_until = None

    def run(self, control, export, cursor):
        with psycopg.connect(self.admin_dsn, autocommit=True) as admin:
            self.valid_until = admin.execute(
                "SELECT rolvaliduntil FROM pg_roles WHERE rolname = "
                "'ofarm_security_audit_export_login'"
            ).fetchone()[0]
        return SecurityAuditExportRunner().run(control, export, cursor)


def _approval(expiry):
    return break_glass._VerifiedSecurityAuditApproval(
        REQUEST_SCHEMA, OPERATION_ID, UUID(int=1), "a", "r", "p", 0, expiry,
        None, ("A", "B"), ("K1", "K2"), ("D1", "D2"),
    )


def _deadline(database, authority_now, expiry):
    current = break_glass._CurrentApprovalCarrier(_approval(expiry), authority_now)
    role = break_glass._derived_expected_role(database, current, "verifier")
    delta = role.valid_until - break_glass._EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds


def _excursion(values):
    low, maximum = values[0], 0
    for value in values[1:]:
        maximum, low = max(maximum, value - low), min(low, value)
    return maximum


def _source():
    return architecture.ROOT.joinpath(
        "deployment/postgresql/security_audit_break_glass.py"
    ).read_text(encoding="utf-8")


def _violations(source):
    return architecture._security_audit_break_glass_violations(ast.parse(source))


def _before_close(source):
    start = source.index("def _export_and_close(")
    end = source.index("\ndef _execute(")
    block = source[start:end].replace(
        "    _close_login(\n",
        "    closed = _ClosedSecurityAuditBreakGlassExport(None, b'')\n"
        "    _close_login(\n",
        1,
    )
    old = (
        "    return _ClosedSecurityAuditBreakGlassExport(\n"
        "        operation_id=approval.operation_id,\n"
        "        page_bytes=exported.page_bytes,\n    )"
    )
    return source[:start] + block.replace(old, "    return closed", 1) + source[end:]


def test_public_surface_and_secret_carrier_are_closed():
    assert tuple(signature(SecurityAuditBreakGlassRunner).parameters) == ("observer_public_key",)
    assert tuple(signature(SecurityAuditBreakGlassRunner.run).parameters) == (
        "self", "secret_carrier", "authority_receipt_bytes", "approval_bundle_bytes",
    )
    assert tuple(signature(SecurityAuditBreakGlassRunner.close_expired).parameters) == ("self", "secret_carrier")
    carrier = SecurityAuditBreakGlassSecrets("postgresql://admin-canary", "postgresql://control-canary")
    assert "admin-canary" not in repr(carrier) and "control-canary" not in repr(carrier)


def test_invalid_carriers_refuse_before_database_work():
    runner = SecurityAuditBreakGlassRunner(bytes(range(32)))
    secret = SecurityAuditBreakGlassSecrets("postgresql://a", "postgresql://c")
    _fixed_error(SecurityAuditBreakGlassRefused, lambda: runner.run(secret, b"", b"{}"))
    _fixed_error(SecurityAuditBreakGlassRefused, lambda: runner.run(secret, b"{}", bytearray(b"{}")))


@pytest.mark.parametrize(("database", "authority_now", "expiry", "expected"), (
    (61_000_000, 80_000_000, 200_000_000, 118_999_999),
    (80_000_000, 61_000_000, 200_000_000, 137_999_999),
    (80_000_000, 80_000_000, 200_000_000, 137_999_999),
))
def test_deadline_translation_is_exact(database, authority_now, expiry, expected):
    assert _deadline(database, authority_now, expiry) == expected


def test_deadline_floor_quantum_delay_and_unrepresentable_value():
    with pytest.raises(ValueError):
        _deadline(10, 10, 62_000_011)
    assert _deadline(10, 10, 62_000_012) == 11
    with pytest.raises((OverflowError, ValueError)):
        _deadline(0, 0, break_glass._MAX_UNIX_MICROSECONDS)
    initial = _deadline(0, 60_000_000, 125_000_000)
    delayed = _deadline(0, 61_000_000, 125_000_000)
    assert (initial, delayed, initial - delayed) == (2_999_999, 1_999_999, 1_000_000)
    assert initial - (delayed - 1_000_000) == 2_000_000


@pytest.mark.parametrize(("values", "eligible"), (
    ([0, 999_999], True), ([0, 1_000_000], True), ([0, 1_000_001], False),
    ([300_000, 100_000, 1_100_000], True), ([300_000, 100_000, 1_100_001], False),
))
def test_complete_interval_ordered_excursion_bound(values, eligible):
    assert (_excursion(values) <= 1_000_000) is eligible


def test_oscillation_slow_clocks_and_complete_authentication_bounds():
    assert _excursion([-600_000, 600_000]) == 1_200_000
    slow = [round(62_200_000 * second / 19_000) for second in range(19_001)]
    assert max(slow[index + 300] - slow[index] for index in range(18_701)) <= 1_000_000
    assert _excursion(slow) == 62_200_000
    assert 60_999_999 <= 61_000_000 and 61_000_001 > 61_000_000
    assert _deadline(0, 0, 300_000_000) == 237_999_999


def test_architecture_result_surface_and_external_reference_rules():
    source = _source()
    assert _violations(source) == []
    public = source.replace("class _ClosedSecurityAuditBreakGlassExport:", "class ClosedSecurityAuditBreakGlassExport:", 1)
    duplicate = source + "\nClosedAlias = _ClosedSecurityAuditBreakGlassExport\n_FORGED = _ClosedSecurityAuditBreakGlassExport(None, b'')\n"
    assert "public closed-result class remains" in _violations(public)
    assert "private closed-result construction inventory differs" in _violations(duplicate)
    assert "private closed-result direct reference inventory differs" in _violations(duplicate)
    assert "private result is not constructed after closure and validation" in _violations(_before_close(source))
    life = ast.parse(source)
    external = ast.parse("from deployment.postgresql.security_audit_break_glass import _ClosedSecurityAuditBreakGlassExport\nimport deployment.postgresql.security_audit_break_glass as bg\nx = bg._ClosedSecurityAuditBreakGlassExport")
    assert architecture._private_result_reference_violations({"life": life, "other": external}, "life")
    unrelated = ast.parse("LABEL = '_ClosedSecurityAuditBreakGlassExport'\nclass _ClosedSecurityAuditBreakGlassExport: pass")
    assert architecture._private_result_reference_violations({"life": life, "other": unrelated}, "life") == []


def test_architecture_deadline_and_recovery_mutations_fail():
    source = _source()
    mutations = (
        source.replace("_MAX_AUTHORITY_DATABASE_DIVERGENCE_GROWTH_US = 1_000_000", "_MAX_AUTHORITY_DATABASE_DIVERGENCE_GROWTH_US = 1_000_001", 1),
        source.replace("_MAX_PASSWORD_AUTHORITY_ADVANCE_US = 61_000_000", "_MAX_PASSWORD_AUTHORITY_ADVANCE_US = 60_000_000", 1),
        source.replace("_POSTGRES_TIMESTAMP_QUANTUM_US = 1", "_POSTGRES_TIMESTAMP_QUANTUM_US = 0", 1),
        source.replace("- max(current.authority_now_us, database_now_us)", "- current.authority_now_us", 1),
        source.replace("        database_now_us = _clock_high_water(connection)", "        database_now_us = 1", 1),
        source.replace("or row[1] is not False", "or row[1] is not True", 1),
        source.replace("    expected_role = outcome.expected_role", "    expected_role = outcome.expected_role\n    _derived_expected_role(0, current, password)", 1),
    )
    assert all(_violations(value) for value in mutations)
    reversed_order = source.replace(
        "        database_now_us = _clock_high_water(connection)\n        current = _advance_current_approval(dependencies, current)",
        "        current = _advance_current_approval(dependencies, current)\n        database_now_us = _clock_high_water(connection)", 1,
    )
    assert "LOGIN deadline order is not H3 then A3 then derive then SQL" in _violations(reversed_order)


def test_live_one_page_closes_role_and_replay_refuses(migrated_audit_service):
    state = migrated_audit_service
    operation, _, observer, authority, bundle, secret = _case(state, OPERATION_ID)
    runner = SecurityAuditBreakGlassRunner(observer)
    result = runner.run(secret, authority, bundle)
    assert type(result).__name__ == "_ClosedSecurityAuditBreakGlassExport"
    assert "operation_id" not in repr(result) and result.operation_id == operation
    page = json.loads(result.page_bytes)
    assert (page["maxRows"], page["maxBytes"]) == (EXPORT_MAX_ROWS, EXPORT_MAX_BYTES)
    assert not _role_exists(state) and _count(state, operation) == 1
    _fixed_error(SecurityAuditBreakGlassRefused, lambda: runner.run(secret, authority, bundle))


def test_live_store_substitution_and_preexisting_role_refuse(migrated_audit_service):
    state = migrated_audit_service
    operation, _, observer, authority, bundle, secret = _case(state)
    wrong = _material(uuid4(), time.time_ns() // 1_000, operation_id=operation)
    _fixed_error(SecurityAuditBreakGlassRefused, lambda: SecurityAuditBreakGlassRunner(wrong[0]).run(secret, wrong[1], wrong[2]))
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute("CREATE ROLE ofarm_security_audit_export_login WITH LOGIN")
    try:
        _fixed_error(SecurityAuditBreakGlassRefused, lambda: SecurityAuditBreakGlassRunner(observer).run(secret, authority, bundle))
        assert _count(state, operation) == 0
    finally:
        with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
            admin.execute("DROP ROLE ofarm_security_audit_export_login")


@pytest.mark.parametrize(("times", "error", "consumed"), (
    ((0, -1), SecurityAuditBreakGlassRefused, 0),
    ((0, 1_000_000, 999_999), SecurityAuditBreakGlassFailed, 1),
))
def test_live_raw_authority_regressions(migrated_audit_service, times, error, consumed):
    state = migrated_audit_service
    operation, now, observer, authority, bundle, secret = _case(state)
    clock = _TimeSequence(*(now + offset for offset in times))
    exporter = _FailingExport("must-not-run")
    dependencies = _dependencies(observer, exporter=exporter, clock=clock)
    _fixed_error(error, lambda: break_glass._run_security_audit_break_glass_for_testing(secret, authority, bundle, dependencies))
    assert clock.calls == len(times) and exporter.calls == 0
    assert _count(state, operation) == consumed and not _role_exists(state)


def test_live_role_uses_exact_translated_deadline_and_closes(migrated_audit_service):
    state = migrated_audit_service
    operation, now, observer, authority, bundle, secret = _case(state)
    clock, factory = _TimeSequence(now, now + 1, now + 2), _ClockFactory()
    exporter = _InspectingExport(state["target_admin_dsn"])
    dependencies = _dependencies(observer, factory=factory, exporter=exporter, clock=clock)
    result = break_glass._run_security_audit_break_glass_for_testing(secret, authority, bundle, dependencies)
    expected = _deadline(factory.observations[1], now + 2, now + 120_000_000)
    assert result.operation_id == operation and clock.calls == 3
    assert exporter.valid_until == break_glass._expiry(expected) and not _role_exists(state)


def test_live_held_access_clock_lock_rolls_back(migrated_audit_service):
    state = migrated_audit_service
    operation, now, observer, authority, bundle, secret = _case(state)
    clock = _TimeSequence(now, now + 1)
    with psycopg.connect(state["target_admin_dsn"]) as blocker:
        factory = _AfterControlCommit(lambda: blocker.execute("SELECT ofarm_infrastructure.take_audit_access_clock_lock()").fetchone())
        try:
            dependencies = _dependencies(observer, factory=factory, clock=clock)
            _fixed_error(SecurityAuditBreakGlassFailed, lambda: break_glass._run_security_audit_break_glass_for_testing(secret, authority, bundle, dependencies))
            assert factory.triggered and clock.calls == 2 and _count(state, operation) == 1
            assert blocker.execute("SELECT to_regrole('ofarm_security_audit_export_login')").fetchone() == (None,)
        finally:
            blocker.execute("SELECT ofarm_infrastructure.release_audit_access_clock_lock()").fetchone()


def test_live_failure_and_commit_ambiguity_outcomes(migrated_audit_service):
    state = migrated_audit_service
    _, _, observer, authority, bundle, secret = _case(state)
    exporter = _FailingExport("PAGE-CANARY")
    error = _fixed_error(SecurityAuditBreakGlassFailed, lambda: break_glass._run_security_audit_break_glass_for_testing(secret, authority, bundle, _dependencies(observer, exporter=exporter)))
    assert exporter.calls == 1 and "PAGE-CANARY" not in repr(error) and not _role_exists(state)
    operation, _, observer, authority, bundle, secret = _case(state)
    factory, exporter = _CommitFactory("ofarm_security_audit_control_login", 2, "canary"), _FailingExport("no")
    _fixed_error(SecurityAuditBreakGlassOutcomeUnknown, lambda: break_glass._run_security_audit_break_glass_for_testing(secret, authority, bundle, _dependencies(observer, factory=factory, exporter=exporter)))
    assert _count(state, operation) == 1 and exporter.calls == 0 and not _role_exists(state)


def test_live_login_commit_ambiguity_retains_exact_role(migrated_audit_service):
    state = migrated_audit_service
    _, now, observer, authority, bundle, secret = _case(state)
    user = psycopg.conninfo.conninfo_to_dict(state["target_admin_dsn"])["user"]
    factory, clock = _CommitFactory(user, 3, "canary"), _TimeSequence(now, now + 1, now + 2)
    dependencies = _dependencies(observer, factory=factory, exporter=_FailingExport("no"), clock=clock)
    _fixed_error(SecurityAuditBreakGlassFailed, lambda: break_glass._run_security_audit_break_glass_for_testing(secret, authority, bundle, dependencies))
    assert clock.calls == 3 and not _role_exists(state)


def test_live_failed_login_resolution_quarantines(migrated_audit_service):
    state = migrated_audit_service
    operation, _, observer, authority, bundle, secret = _case(state)
    user = psycopg.conninfo.conninfo_to_dict(state["target_admin_dsn"])["user"]
    factory = _CommitFactory(user, 3, "canary", failure=4)
    try:
        dependencies = _dependencies(observer, factory=factory, exporter=_FailingExport("no"))
        _fixed_error(SecurityAuditBreakGlassQuarantined, lambda: break_glass._run_security_audit_break_glass_for_testing(secret, authority, bundle, dependencies))
        assert _role_exists(state)
    finally:
        with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
            if _role_exists(state):
                admin.execute("REVOKE ofarm_security_audit_export FROM ofarm_security_audit_export_login")
                admin.execute("DROP ROLE ofarm_security_audit_export_login")
            admin.execute("DELETE FROM ofarm_security.temporary_export_approval_consumption WHERE operation_id = %s", (operation,))


def test_live_closure_only_refuses_future_and_closes_expired(migrated_audit_service):
    state = migrated_audit_service
    _, _, observer, _, _, secret = _case(state)
    dependencies = _dependencies(observer)
    _, verifier = break_glass._password_material(dependencies)
    future = break_glass._ExpectedRole(break_glass._expiry(time.time_ns() // 1_000 + 120_000_000), verifier)
    _create_exact(state, future)
    runner = SecurityAuditBreakGlassRunner(observer)
    try:
        _fixed_error(SecurityAuditBreakGlassRefused, lambda: runner.close_expired(secret))
    finally:
        break_glass._close_login(dependencies, state["target_admin_dsn"], _store_id(state), future)
    expired = break_glass._ExpectedRole(break_glass._expiry(time.time_ns() // 1_000 - 1_000_000), verifier)
    _create_exact(state, expired)
    runner.close_expired(secret)
    runner.close_expired(secret)
    assert not _role_exists(state)


def test_live_closure_does_not_close_concurrent_replacement(migrated_audit_service, monkeypatch):
    state = migrated_audit_service
    _, _, observer, _, _, secret = _case(state)
    dependencies, store = _dependencies(observer), _store_id(state)
    _, verifier = break_glass._password_material(dependencies)
    expired = break_glass._ExpectedRole(break_glass._expiry(time.time_ns() // 1_000 - 1_000_000), verifier)
    replacement = break_glass._ExpectedRole(break_glass._expiry(time.time_ns() // 1_000 + 120_000_000), verifier)
    _create_exact(state, expired)

    def replace():
        break_glass._close_login(dependencies, state["target_admin_dsn"], store, expired)
        _create_exact(state, replacement)

    factory = _BeforeNoLoginFactory(replace)
    monkeypatch.setattr(break_glass.psycopg, "connect", factory)
    try:
        _fixed_error(SecurityAuditBreakGlassQuarantined, lambda: SecurityAuditBreakGlassRunner(observer).close_expired(secret))
        assert factory.triggered
    finally:
        observed = break_glass._role_observation(dependencies, state["target_admin_dsn"], store, replacement, allow_disabled=True)
        if observed == "EXPECTED":
            break_glass._close_login(dependencies, state["target_admin_dsn"], store, replacement)


def _receive(connection, length):
    value = b""
    while len(value) < length:
        chunk = connection.recv(length - len(value))
        if not chunk:
            raise EOFError
        value += chunk
    return value


def _message(connection):
    header = _receive(connection, 5)
    return header[:1], _receive(connection, struct.unpack("!I", header[1:])[0] - 4)


def _start_scram(conninfo):
    values = psycopg.conninfo.conninfo_to_dict(conninfo)
    host = values.get("hostaddr") or values.get("host")
    if not host or host.startswith("/"):
        pytest.skip("TCP is required for raw SCRAM evidence")
    connection = socket.create_connection((host, int(values.get("port", "5432"))), timeout=5)
    startup = b"user\0" + values["user"].encode() + b"\0database\0" + values["dbname"].encode() + b"\0\0"
    connection.sendall(struct.pack("!II", len(startup) + 8, 196608) + startup)
    while True:
        kind, payload = _message(connection)
        if kind == b"R" and struct.unpack("!I", payload[:4])[0] == 10:
            break
        if kind == b"E":
            raise RuntimeError
    first = f"n={values['user']},r={uuid4().hex}"
    initial = ("n,," + first).encode()
    payload = b"SCRAM-SHA-256\0" + struct.pack("!I", len(initial)) + initial
    connection.sendall(b"p" + struct.pack("!I", len(payload) + 4) + payload)
    kind, payload = _message(connection)
    assert kind == b"R" and struct.unpack("!I", payload[:4])[0] == 11
    return connection, values["password"], first, payload[4:].decode()


def _finish_scram(session):
    connection, password, first, server = session
    members = dict(item.split("=", 1) for item in server.split(","))
    final = f"c=biws,r={members['r']}"
    message = (first + "," + server + "," + final).encode()
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(members["s"]), int(members["i"]))
    key = hmac.digest(salted, b"Client Key", "sha256")
    signature = hmac.digest(hashlib.sha256(key).digest(), message, "sha256")
    proof = bytes(left ^ right for left, right in zip(key, signature))
    payload = (final + ",p=" + base64.b64encode(proof).decode()).encode()
    connection.sendall(b"p" + struct.pack("!I", len(payload) + 4) + payload)
    authenticated = False
    while True:
        kind, payload = _message(connection)
        if kind == b"E":
            raise RuntimeError
        if kind == b"R" and struct.unpack("!I", payload[:4])[0] == 0:
            authenticated = True
        if kind == b"Z":
            assert authenticated
            return


def _reload_timeout(admin, expected):
    assert admin.execute("SELECT pg_reload_conf()").fetchone() == (True,)
    for _attempt in range(100):
        if admin.execute("SHOW authentication_timeout").fetchone() == (expected,):
            return
        time.sleep(0.05)
    raise AssertionError("authentication_timeout did not reload")


def test_live_pgdg_scram_timer_and_timestamp_quantum(migrated_audit_service):
    state = migrated_audit_service
    _, _, observer, _, _, _ = _case(state)
    dependencies = _dependencies(observer)
    password, verifier = break_glass._password_material(dependencies)
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        identity = admin.execute("SELECT current_setting('server_version_num')::int, current_setting('server_version')").fetchone()
        assert identity == (SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM, SUPPORTED_POSTGRESQL_SERVER_VERSION)
        now = admin.execute("SELECT floor(extract(epoch FROM clock_timestamp()) * 1000000)::bigint").fetchone()[0]
        setting, sourcefile = admin.execute("SELECT current_setting('authentication_timeout'), sourcefile FROM pg_settings WHERE name = 'authentication_timeout'").fetchone()
    future, store = break_glass._expiry(now + 30_000_000), _store_id(state)
    expected = break_glass._ExpectedRole(future, verifier)
    _create_exact(state, expected)
    route, sessions = break_glass._export_route(state["target_admin_dsn"], password), []
    try:
        with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
            admin.execute("ALTER SYSTEM SET authentication_timeout = '2s'")
            _reload_timeout(admin, "2s")
            with psycopg.connect(route) as export:
                assert export.execute("SHOW statement_timeout").fetchone() == ("5s",)
            delayed = _start_scram(route)
            sessions.append(delayed)
            cutoff = admin.execute("SELECT clock_timestamp()").fetchone()[0]
            admin.execute(sql.SQL("ALTER ROLE {} VALID UNTIL {}").format(sql.Identifier(break_glass.TEMPORARY_EXPORT_LOGIN), sql.Literal(cutoff.isoformat(timespec="microseconds"))))
            expected = break_glass._ExpectedRole(cutoff, verifier)
            time.sleep(1)
            _finish_scram(delayed)
            delayed[0].close()
            assert time.time_ns() // 1_000 < int(cutoff.timestamp() * 1_000_000) + 62_000_001
            admin.execute(sql.SQL("ALTER ROLE {} VALID UNTIL {}").format(sql.Identifier(break_glass.TEMPORARY_EXPORT_LOGIN), sql.Literal(future.isoformat(timespec="microseconds"))))
            expected = break_glass._ExpectedRole(future, verifier)
            timed_out = _start_scram(route)
            sessions.append(timed_out)
            time.sleep(2.25)
            with pytest.raises((EOFError, OSError, RuntimeError)):
                _finish_scram(timed_out)
            crashed = _start_scram(route)
            sessions.append(crashed)
            crashed[0].close()
            time.sleep(0.1)
            assert admin.execute(break_glass._SESSION_COUNT_SQL).fetchone() == (0,)
            former = admin.execute("SELECT floor(extract(epoch FROM clock_timestamp()) * 1000000)::bigint + 1000000").fetchone()[0]
            expected = break_glass._ExpectedRole(break_glass._expiry(former - 1), verifier)
            admin.execute(sql.SQL("ALTER ROLE {} VALID UNTIL {}").format(sql.Identifier(break_glass.TEMPORARY_EXPORT_LOGIN), sql.Literal(expected.valid_until.isoformat(timespec="microseconds"))))
            while admin.execute("SELECT floor(extract(epoch FROM clock_timestamp()) * 1000000)::bigint").fetchone()[0] < former:
                pass
            with pytest.raises(psycopg.OperationalError):
                psycopg.connect(route, connect_timeout=5)
    finally:
        for session in sessions:
            session[0].close()
        with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
            command = sql.SQL("ALTER SYSTEM SET authentication_timeout = {}").format(sql.Literal(setting)) if sourcefile and sourcefile.endswith("postgresql.auto.conf") else sql.SQL("ALTER SYSTEM RESET authentication_timeout")
            admin.execute(command)
            _reload_timeout(admin, setting)
        break_glass._close_login(dependencies, state["target_admin_dsn"], store, expected)
