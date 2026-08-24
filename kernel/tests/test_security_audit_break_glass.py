"""Focused evidence for the closed temporary audit-export lifecycle."""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import time
from inspect import signature
from uuid import UUID, uuid4

import psycopg
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from conformance import rewrite_architecture_check
from deployment.postgresql import security_audit_break_glass as break_glass
from deployment.postgresql.audit_contract import (
    EXPORT_ACCESS_PURPOSE_IDENTITY,
    EXPORT_FUNCTION_IDENTITY,
    EXPORT_MAX_BYTES,
    EXPORT_MAX_ROWS,
)
from deployment.postgresql.security_audit_break_glass import (
    ClosedSecurityAuditBreakGlassExport,
    SecurityAuditBreakGlassFailed,
    SecurityAuditBreakGlassOutcomeUnknown,
    SecurityAuditBreakGlassQuarantined,
    SecurityAuditBreakGlassRefused,
    SecurityAuditBreakGlassRunner,
    SecurityAuditBreakGlassSecrets,
)
from deployment.postgresql.catalog_identity import verify_catalog_identity
from deployment.postgresql.security_audit_approval import (
    SecurityAuditDualApprovalVerifier,
)
from deployment.postgresql.security_audit_export import SecurityAuditExportRunner
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn as _role_dsn,
)


AUTHORITY_SCHEMA = "ofarm.security-audit-break-glass-authority-receipt.v1"
REQUEST_SCHEMA = "ofarm.security-audit-break-glass-export-request.v2"
STATEMENT_SCHEMA = "ofarm.security-audit-break-glass-export-approval.v1"
BUNDLE_SCHEMA = "ofarm.security-audit-break-glass-approval-bundle.v1"
AUDIENCE = "ofarm.security-audit-break-glass-export.v1"
AUTHORITY_DOMAIN = b"OFARM_SECURITY_AUDIT_BREAK_GLASS_AUTHORITY_RECEIPT_V1\x00"
APPROVAL_DOMAIN = b"OFARM_SECURITY_AUDIT_BREAK_GLASS_EXPORT_APPROVAL_V1\x00"
OPERATION_ID = UUID("123e4567-e89b-42d3-a456-426614174000")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _public_key(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )


def _key_id(public_key: bytes) -> str:
    thumbprint = _canonical(
        {"crv": "Ed25519", "kty": "OKP", "x": _b64(public_key)}
    )
    return _b64(hashlib.sha256(thumbprint).digest())


def _material(
    store_id: UUID,
    now_us: int,
    *,
    operation_id: UUID = OPERATION_ID,
) -> tuple[bytes, bytes, bytes]:
    observer = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    approvers = (
        (
            Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33))),
            "APPROVER_A",
            "DOMAIN_A",
        ),
        (
            Ed25519PrivateKey.from_private_bytes(bytes(range(2, 34))),
            "APPROVER_B",
            "DOMAIN_B",
        ),
    )
    authority_entries = []
    for key, approver_id, domain in approvers:
        public_key = _public_key(key)
        authority_entries.append(
            {
                "approverId": approver_id,
                "independenceDomain": domain,
                "keyId": _key_id(public_key),
                "publicKey": _b64(public_key),
            }
        )
    authority_payload = _canonical(
        {
            "approvers": authority_entries,
            "audience": AUDIENCE,
            "expiresAtUnixMicroseconds": now_us + 240_000_000,
            "observedAtUnixMicroseconds": now_us - 1_000_000,
            "schemaVersion": AUTHORITY_SCHEMA,
        }
    )
    authority_receipt = _canonical(
        {
            "payload": _b64(authority_payload),
            "signature": _b64(
                observer.sign(AUTHORITY_DOMAIN + authority_payload)
            ),
        }
    )
    request = _canonical(
        {
            "audience": AUDIENCE,
            "authorityReceiptDigest": _digest(authority_receipt),
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
    for key, approver_id, domain in approvers:
        public_key = _public_key(key)
        statement = _canonical(
            {
                "approverId": approver_id,
                "audience": AUDIENCE,
                "authorityReceiptDigest": _digest(authority_receipt),
                "independenceDomain": domain,
                "keyId": _key_id(public_key),
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
    return _public_key(observer), authority_receipt, bundle


def _assert_fixed_refusal(call) -> None:
    with pytest.raises(SecurityAuditBreakGlassRefused) as caught:
        call()
    error = caught.value
    assert error.args == ()
    assert error.__cause__ is None
    assert error.__context__ is None
    assert str(error) == ""


def _assert_fixed_error(error_type, call):
    with pytest.raises(error_type) as caught:
        call()
    error = caught.value
    assert error.args == ()
    assert error.__cause__ is None
    assert error.__context__ is None
    assert str(error) == ""
    return error


def _store_id(state) -> UUID:
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        return admin.execute(
            "SELECT execution_id FROM ofarm_security.schema_migration "
            "WHERE version = 1"
        ).fetchone()[0]


def _random_bytes(length: int) -> bytes:
    return bytes((index % 251) + 1 for index in range(length))


def _dependencies(observer_key, *, connection_factory=psycopg.connect, exporter=None):
    return break_glass._Dependencies(
        connection_factory=connection_factory,
        time_ns=time.time_ns,
        random_bytes=_random_bytes,
        approval_verifier=SecurityAuditDualApprovalVerifier(observer_key),
        export_runner=exporter or SecurityAuditExportRunner(),
        catalog_verifier=verify_catalog_identity,
    )


class _FailingExport:
    def __init__(self, canary: str):
        self.canary = canary
        self.calls = 0

    def run(self, _control, _export, _cursor):
        self.calls += 1
        raise RuntimeError(self.canary)


class _CommitThenRaiseConnection:
    def __init__(self, connection, canary: str):
        self.connection = connection
        self.canary = canary

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.connection.commit()
        raise RuntimeError(self.canary)


class _NthRoleCommitFactory:
    def __init__(
        self,
        user: str,
        occurrence: int,
        canary: str,
        *,
        failure_occurrence: int | None = None,
    ):
        self.user = user
        self.occurrence = occurrence
        self.canary = canary
        self.failure_occurrence = failure_occurrence
        self.count = 0

    def __call__(self, conninfo, **kwargs):
        connection = psycopg.connect(conninfo, **kwargs)
        user = psycopg.conninfo.conninfo_to_dict(conninfo).get("user")
        if user == self.user:
            self.count += 1
            if self.count == self.occurrence:
                return _CommitThenRaiseConnection(connection, self.canary)
            if self.count == self.failure_occurrence:
                connection.close()
                raise RuntimeError(self.canary)
        return connection


class _BeforeNoLoginConnection:
    def __init__(self, connection, factory):
        self.connection = connection
        self.factory = factory

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, query, parameters=None):
        render = getattr(query, "as_string", None)
        statement = render(self.connection) if callable(render) else query
        if statement == (
            'ALTER ROLE "ofarm_security_audit_export_login" NOLOGIN'
        ):
            self.factory.before_no_login()
        return self.connection.execute(query, parameters)


class _BeforeNoLoginFactory:
    def __init__(self, callback):
        self.callback = callback
        self.connect = psycopg.connect
        self.triggered = False

    def before_no_login(self):
        if not self.triggered:
            self.triggered = True
            self.callback()

    def __call__(self, conninfo, **kwargs):
        return _BeforeNoLoginConnection(
            self.connect(conninfo, **kwargs), self
        )


def test_public_surface_has_no_dependency_time_random_or_export_injection():
    assert tuple(signature(SecurityAuditBreakGlassRunner).parameters) == (
        "observer_public_key",
    )
    assert tuple(signature(SecurityAuditBreakGlassRunner.run).parameters) == (
        "self",
        "secret_carrier",
        "authority_receipt_bytes",
        "approval_bundle_bytes",
    )
    assert tuple(
        signature(SecurityAuditBreakGlassRunner.close_expired).parameters
    ) == ("self", "secret_carrier")


def test_secret_and_closed_page_carriers_do_not_render_contents():
    secrets = SecurityAuditBreakGlassSecrets(
        "postgresql://admin-canary", "postgresql://control-canary"
    )
    result = ClosedSecurityAuditBreakGlassExport(
        OPERATION_ID, b"PAGE-CANARY"
    )

    assert "admin-canary" not in repr(secrets)
    assert "control-canary" not in repr(secrets)
    assert "PAGE-CANARY" not in repr(result)


def test_invalid_carriers_refuse_before_database_work():
    runner = SecurityAuditBreakGlassRunner(bytes(range(32)))
    secret = SecurityAuditBreakGlassSecrets(
        "postgresql://admin-canary", "postgresql://control-canary"
    )

    _assert_fixed_refusal(lambda: runner.run(secret, b"", b"{}"))
    _assert_fixed_refusal(lambda: runner.run(secret, b"{}", bytearray(b"{}")))


def test_architecture_surface_rejects_public_injection_and_caller_time():
    source = rewrite_architecture_check.ROOT.joinpath(
        "deployment/postgresql/security_audit_break_glass.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert (
        rewrite_architecture_check._security_audit_break_glass_violations(
            tree
        )
        == []
    )


def test_live_one_page_is_released_only_after_role_drop_and_replay_refuses(
    migrated_audit_service,
):
    state = migrated_audit_service
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        store_id = admin.execute(
            "SELECT execution_id FROM ofarm_security.schema_migration "
            "WHERE version = 1"
        ).fetchone()[0]
    observer_key, authority, bundle = _material(
        store_id, time.time_ns() // 1_000
    )
    secrets = SecurityAuditBreakGlassSecrets(
        admin_dsn=state["target_admin_dsn"],
        control_dsn=_role_dsn(
            state, "ofarm_security_audit_control_login"
        ),
    )
    runner = SecurityAuditBreakGlassRunner(observer_key)

    result = runner.run(secrets, authority, bundle)

    assert result.operation_id == OPERATION_ID
    page = json.loads(result.page_bytes)
    assert page["schemaVersion"] == \
        "ofarm.security-audit-bounded-export-page.v1"
    assert page["maxRows"] == EXPORT_MAX_ROWS
    assert page["maxBytes"] == EXPORT_MAX_BYTES
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        assert admin.execute(
            "SELECT pg_catalog.to_regrole("
            "'ofarm_security_audit_export_login')"
        ).fetchone() == (None,)
        assert admin.execute(
            "SELECT pg_catalog.count(*) FROM "
            "ofarm_security.temporary_export_approval_consumption"
        ).fetchone() == (1,)

    _assert_fixed_refusal(lambda: runner.run(secrets, authority, bundle))
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        assert admin.execute(
            "SELECT pg_catalog.to_regrole("
            "'ofarm_security_audit_export_login')"
        ).fetchone() == (None,)


def test_live_store_substitution_and_preexisting_role_refuse_before_consumption(
    migrated_audit_service,
):
    state = migrated_audit_service
    store_id = _store_id(state)
    secret = SecurityAuditBreakGlassSecrets(
        state["target_admin_dsn"],
        _role_dsn(state, "ofarm_security_audit_control_login"),
    )
    wrong_key, wrong_authority, wrong_bundle = _material(
        uuid4(), time.time_ns() // 1_000, operation_id=uuid4()
    )
    before = None
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        before = admin.execute(
            "SELECT pg_catalog.count(*) FROM "
            "ofarm_security.temporary_export_approval_consumption"
        ).fetchone()[0]
    _assert_fixed_refusal(
        lambda: SecurityAuditBreakGlassRunner(wrong_key).run(
            secret, wrong_authority, wrong_bundle
        )
    )

    key, authority, bundle = _material(
        store_id, time.time_ns() // 1_000, operation_id=uuid4()
    )
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        admin.execute(
            "CREATE ROLE ofarm_security_audit_export_login "
            "WITH LOGIN NOINHERIT CONNECTION LIMIT 1"
        )
    try:
        _assert_fixed_refusal(
            lambda: SecurityAuditBreakGlassRunner(key).run(
                secret, authority, bundle
            )
        )
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            admin.execute("DROP ROLE ofarm_security_audit_export_login")
            assert admin.execute(
                "SELECT pg_catalog.count(*) FROM "
                "ofarm_security.temporary_export_approval_consumption"
            ).fetchone() == (before,)


def test_live_export_failure_closes_role_and_never_exposes_canary_page(
    migrated_audit_service,
):
    state = migrated_audit_service
    store_id = _store_id(state)
    observer, authority, bundle = _material(
        store_id, time.time_ns() // 1_000, operation_id=uuid4()
    )
    secret = SecurityAuditBreakGlassSecrets(
        state["target_admin_dsn"],
        _role_dsn(state, "ofarm_security_audit_control_login"),
    )
    exporter = _FailingExport("EXPORT-PAGE-CANARY")
    dependencies = _dependencies(observer, exporter=exporter)

    error = _assert_fixed_error(
        SecurityAuditBreakGlassFailed,
        lambda: break_glass._run_security_audit_break_glass_for_testing(
            secret, authority, bundle, dependencies
        ),
    )

    assert exporter.calls == 1
    assert "EXPORT-PAGE-CANARY" not in repr(error)
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        assert admin.execute(
            "SELECT pg_catalog.to_regrole("
            "'ofarm_security_audit_export_login')"
        ).fetchone() == (None,)


def test_live_consume_commit_ambiguity_is_terminal_and_creates_no_role(
    migrated_audit_service,
):
    state = migrated_audit_service
    operation_id = uuid4()
    observer, authority, bundle = _material(
        _store_id(state),
        time.time_ns() // 1_000,
        operation_id=operation_id,
    )
    secret = SecurityAuditBreakGlassSecrets(
        state["target_admin_dsn"],
        _role_dsn(state, "ofarm_security_audit_control_login"),
    )
    factory = _NthRoleCommitFactory(
        "ofarm_security_audit_control_login",
        2,
        "CONSUME-COMMIT-CANARY",
    )
    exporter = _FailingExport("EXPORT-MUST-NOT-RUN")
    dependencies = _dependencies(
        observer, connection_factory=factory, exporter=exporter
    )

    error = _assert_fixed_error(
        SecurityAuditBreakGlassOutcomeUnknown,
        lambda: break_glass._run_security_audit_break_glass_for_testing(
            secret, authority, bundle, dependencies
        ),
    )

    assert factory.count == 2
    assert exporter.calls == 0
    assert "CONSUME-COMMIT-CANARY" not in repr(error)
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        assert admin.execute(
            "SELECT pg_catalog.count(*) FROM "
            "ofarm_security.temporary_export_approval_consumption "
            "WHERE operation_id = %s",
            (operation_id,),
        ).fetchone() == (1,)
        assert admin.execute(
            "SELECT pg_catalog.to_regrole("
            "'ofarm_security_audit_export_login')"
        ).fetchone() == (None,)


def test_live_ambiguous_login_commit_is_inspected_closed_and_returns_no_page(
    migrated_audit_service,
):
    state = migrated_audit_service
    observer, authority, bundle = _material(
        _store_id(state), time.time_ns() // 1_000, operation_id=uuid4()
    )
    secret = SecurityAuditBreakGlassSecrets(
        state["target_admin_dsn"],
        _role_dsn(state, "ofarm_security_audit_control_login"),
    )
    admin_user = psycopg.conninfo.conninfo_to_dict(
        state["target_admin_dsn"]
    )["user"]
    factory = _NthRoleCommitFactory(
        admin_user, 3, "LOGIN-COMMIT-CANARY"
    )
    exporter = _FailingExport("EXPORT-MUST-NOT-RUN")
    dependencies = _dependencies(
        observer, connection_factory=factory, exporter=exporter
    )

    error = _assert_fixed_error(
        SecurityAuditBreakGlassFailed,
        lambda: break_glass._run_security_audit_break_glass_for_testing(
            secret, authority, bundle, dependencies
        ),
    )

    assert exporter.calls == 0
    assert "LOGIN-COMMIT-CANARY" not in repr(error)
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        assert admin.execute(
            "SELECT pg_catalog.to_regrole("
            "'ofarm_security_audit_export_login')"
        ).fetchone() == (None,)


def test_live_ambiguous_login_commit_with_failed_resolution_quarantines(
    migrated_audit_service,
):
    state = migrated_audit_service
    operation_id = uuid4()
    observer, authority, bundle = _material(
        _store_id(state), time.time_ns() // 1_000, operation_id=operation_id
    )
    secret = SecurityAuditBreakGlassSecrets(
        state["target_admin_dsn"],
        _role_dsn(state, "ofarm_security_audit_control_login"),
    )
    admin_user = psycopg.conninfo.conninfo_to_dict(
        state["target_admin_dsn"]
    )["user"]
    factory = _NthRoleCommitFactory(
        admin_user,
        3,
        "LOGIN-RESOLUTION-CANARY",
        failure_occurrence=4,
    )
    exporter = _FailingExport("EXPORT-MUST-NOT-RUN")
    dependencies = _dependencies(
        observer, connection_factory=factory, exporter=exporter
    )

    try:
        error = _assert_fixed_error(
            SecurityAuditBreakGlassQuarantined,
            lambda: break_glass._run_security_audit_break_glass_for_testing(
                secret, authority, bundle, dependencies
            ),
        )

        assert factory.count == 4
        assert exporter.calls == 0
        assert "LOGIN-RESOLUTION-CANARY" not in repr(error)
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            assert admin.execute(
                "SELECT pg_catalog.to_regrole("
                "'ofarm_security_audit_export_login') IS NOT NULL"
            ).fetchone() == (True,)
    finally:
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            role_exists = admin.execute(
                "SELECT pg_catalog.to_regrole("
                "'ofarm_security_audit_export_login') IS NOT NULL"
            ).fetchone() == (True,)
            if role_exists:
                admin.execute(
                    "REVOKE ofarm_security_audit_export FROM "
                    "ofarm_security_audit_export_login"
                )
                admin.execute("DROP ROLE ofarm_security_audit_export_login")
            admin.execute(
                "DELETE FROM "
                "ofarm_security.temporary_export_approval_consumption "
                "WHERE operation_id = %s",
                (operation_id,),
            )


def test_live_closure_only_refuses_unexpired_and_closes_expired_exact_role(
    migrated_audit_service,
):
    state = migrated_audit_service
    store_id = _store_id(state)
    observer, _authority, _bundle = _material(
        store_id, time.time_ns() // 1_000, operation_id=uuid4()
    )
    secret = SecurityAuditBreakGlassSecrets(
        state["target_admin_dsn"],
        _role_dsn(state, "ofarm_security_audit_control_login"),
    )
    dependencies = _dependencies(observer)
    _password, verifier = break_glass._password_material(dependencies)
    future = break_glass._ExpectedRole(
        break_glass._expiry(time.time_ns() // 1_000 + 120_000_000),
        verifier,
    )
    break_glass._create_login(
        dependencies, state["target_admin_dsn"], store_id, future
    )
    runner = SecurityAuditBreakGlassRunner(observer)
    try:
        _assert_fixed_refusal(lambda: runner.close_expired(secret))
        with psycopg.connect(
            state["target_admin_dsn"], autocommit=True
        ) as admin:
            assert admin.execute(
                "SELECT pg_catalog.to_regrole("
                "'ofarm_security_audit_export_login') IS NOT NULL"
            ).fetchone() == (True,)
    finally:
        break_glass._close_login(
            dependencies, state["target_admin_dsn"], store_id, future
        )

    _password, verifier = break_glass._password_material(dependencies)
    expired = break_glass._ExpectedRole(
        break_glass._expiry(time.time_ns() // 1_000 - 1_000_000),
        verifier,
    )
    break_glass._create_login(
        dependencies, state["target_admin_dsn"], store_id, expired
    )
    runner.close_expired(secret)
    runner.close_expired(secret)
    with psycopg.connect(state["target_admin_dsn"], autocommit=True) as admin:
        assert admin.execute(
            "SELECT pg_catalog.to_regrole("
            "'ofarm_security_audit_export_login')"
        ).fetchone() == (None,)


def test_live_closure_only_does_not_close_concurrent_replacement(
    migrated_audit_service,
    monkeypatch,
):
    state = migrated_audit_service
    store_id = _store_id(state)
    observer, _authority, _bundle = _material(
        store_id, time.time_ns() // 1_000, operation_id=uuid4()
    )
    secret = SecurityAuditBreakGlassSecrets(
        state["target_admin_dsn"],
        _role_dsn(state, "ofarm_security_audit_control_login"),
    )
    dependencies = _dependencies(observer)
    _password, verifier = break_glass._password_material(dependencies)
    expired = break_glass._ExpectedRole(
        break_glass._expiry(time.time_ns() // 1_000 - 1_000_000),
        verifier,
    )
    replacement = break_glass._ExpectedRole(
        break_glass._expiry(time.time_ns() // 1_000 + 120_000_000),
        verifier,
    )
    break_glass._create_login(
        dependencies, state["target_admin_dsn"], store_id, expired
    )
    def replace_before_disable():
        break_glass._close_login(
            dependencies,
            state["target_admin_dsn"],
            store_id,
            expired,
        )
        break_glass._create_login(
            dependencies,
            state["target_admin_dsn"],
            store_id,
            replacement,
        )

    factory = _BeforeNoLoginFactory(replace_before_disable)
    monkeypatch.setattr(
        break_glass.psycopg, "connect", factory
    )
    runner = SecurityAuditBreakGlassRunner(observer)
    try:
        _assert_fixed_error(
            SecurityAuditBreakGlassQuarantined,
            lambda: runner.close_expired(secret),
        )
        assert factory.triggered is True
        assert break_glass._role_observation(
            dependencies,
            state["target_admin_dsn"],
            store_id,
            replacement,
            allow_disabled=True,
        ) == "EXPECTED"
    finally:
        observed = break_glass._role_observation(
            dependencies,
            state["target_admin_dsn"],
            store_id,
            replacement,
            allow_disabled=True,
        )
        if observed == "EXPECTED":
            break_glass._close_login(
                dependencies,
                state["target_admin_dsn"],
                store_id,
                replacement,
            )
