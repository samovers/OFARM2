"""Unit tests for the external PostgreSQL catalog-verifier trust anchor."""

from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError

import pytest

import deployment.postgresql.catalog_identity as catalog
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    MigrationService,
)


class _Cursor:
    def __init__(self, rows: object):
        self.rows = rows

    def fetchall(self) -> object:
        return self.rows


class _Connection:
    def __init__(self, rows: object):
        self.rows = rows
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def execute(self, statement: str, parameters: tuple[str, ...]) -> _Cursor:
        self.calls.append((statement, parameters))
        return _Cursor(self.rows)


def _tenant_rows() -> list[tuple[str, str, str]]:
    return [
        (
            "routine",
            "ofarm.observe_tenant_contract()",
            '{"definition": "observer", "source": "BEGIN observer END"}',
        ),
        (
            "routine",
            "ofarm.verify_tenant_structure()",
            '{"definition": "verifier", "source": "BEGIN verifier END"}',
        ),
    ]


def _audit_rows() -> list[tuple[str, str, str]]:
    return [
        (
            "routine",
            "ofarm_security.observe_security_audit_contract()",
            '{"definition": "observer", "source": "BEGIN observer END"}',
        ),
        (
            "routine",
            "ofarm_security.verify_security_audit_structure()",
            '{"definition": "verifier", "source": "BEGIN verifier END"}',
        ),
    ]


def _lp32(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def _expected_digest(
    service: MigrationService,
    rows: list[tuple[str, str, str]],
) -> str:
    framed = bytearray(
        catalog.CATALOG_VERIFIER_IDENTITY_POLICY.encode("ascii") + b"\x00"
    )
    framed.extend(_lp32(service.identity.encode("ascii")))
    framed.extend(len(rows).to_bytes(4, "big"))
    for row in rows:
        for value in row:
            framed.extend(_lp32(value.encode("utf-8")))
    return "sha256:" + hashlib.sha256(framed).hexdigest()


@pytest.mark.parametrize(
    ("service", "rows", "parameters"),
    (
        (
            TENANT_SERVICE,
            _tenant_rows(),
            (
                "ofarm",
                "verify_tenant_structure",
                "ofarm",
                "observe_tenant_contract",
            ),
        ),
        (
            SECURITY_AUDIT_SERVICE,
            _audit_rows(),
            (
                "ofarm_security",
                "verify_security_audit_structure",
                "ofarm_security",
                "observe_security_audit_contract",
            ),
        ),
    ),
)
def test_one_caller_independent_statement_produces_exact_framed_identity(
    service: MigrationService,
    rows: list[tuple[str, str, str]],
    parameters: tuple[str, ...],
) -> None:
    connection = _Connection(rows)

    observed = catalog.observe_catalog_identity(connection, service)

    assert observed.policy == catalog.CATALOG_VERIFIER_IDENTITY_POLICY
    assert observed.service_identity == service.identity
    assert observed.row_count == 2
    assert observed.digest == _expected_digest(service, rows)
    assert len(connection.calls) == 1
    statement, actual_parameters = connection.calls[0]
    assert actual_parameters == parameters
    assert "SESSION_USER" not in statement
    assert "CURRENT_USER" not in statement
    assert "pg_stat" not in statement
    assert "pg_get_functiondef" in statement
    assert "aclexplode" in statement
    with pytest.raises(FrozenInstanceError):
        observed.digest = "sha256:" + "0" * 64


def test_exact_injected_trust_anchor_accepts_and_one_byte_change_refuses() -> None:
    rows = _tenant_rows()
    expected = _expected_digest(TENANT_SERVICE, rows)

    accepted = catalog.verify_catalog_identity(
        _Connection(rows),
        TENANT_SERVICE,
        expected_digest=expected,
    )
    changed = list(rows)
    changed[1] = (changed[1][0], changed[1][1], changed[1][2] + " ")

    assert accepted.digest == expected
    with pytest.raises(catalog.CatalogIdentityError, match="identity differs"):
        catalog.verify_catalog_identity(
            _Connection(changed),
            TENANT_SERVICE,
            expected_digest=expected,
        )


def test_tenant_v8_external_catalog_anchor_is_literal() -> None:
    assert catalog.TENANT_CATALOG_VERIFIER_DIGEST == (
        "sha256:28aaa41651c1338fec9f8ca6aa7f252b7bef4ef2f3b1760d399306aba69c8719"
    )


def test_unset_production_anchor_refuses_before_catalog_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _Connection(_tenant_rows())
    monkeypatch.setattr(catalog, "TENANT_CATALOG_VERIFIER_DIGEST", None)

    with pytest.raises(catalog.CatalogIdentityError, match="anchor is unavailable"):
        catalog.verify_catalog_identity(connection, TENANT_SERVICE)

    assert connection.calls == []


@pytest.mark.parametrize(
    "rows",
    (
        (),
        [],
        _tenant_rows()[:1],
        _tenant_rows() + [_tenant_rows()[0]],
        [list(_tenant_rows()[0]), _tenant_rows()[1]],
        [("routine", "ofarm.observe_tenant_contract()", ""), _tenant_rows()[1]],
        list(reversed(_tenant_rows())),
        [
            ("routine", "ofarm.observe_tenant_contract()", "{}"),
            ("routine", "ofarm.observe_tenant_contract()", "{}"),
        ],
        [
            ("wrong", "ofarm.observe_tenant_contract()", "{}"),
            _tenant_rows()[1],
        ],
        [
            ("routine", "ofarm.observe_tenant_contract(integer)", "{}"),
            _tenant_rows()[1],
        ],
    ),
)
def test_malformed_missing_extra_reordered_or_repeated_rows_refuse(
    rows: object,
) -> None:
    with pytest.raises(catalog.CatalogIdentityError):
        catalog.observe_catalog_identity(_Connection(rows), TENANT_SERVICE)


def test_unknown_service_and_malformed_expected_digest_refuse() -> None:
    unknown = MigrationService("unknown", "x", "x", "x")

    with pytest.raises(catalog.CatalogIdentityError, match="not fixed"):
        catalog.observe_catalog_identity(_Connection([]), unknown)
    with pytest.raises(catalog.CatalogIdentityError, match="anchor is unavailable"):
        catalog.verify_catalog_identity(
            _Connection(_audit_rows()),
            SECURITY_AUDIT_SERVICE,
            expected_digest="not-a-digest",
        )


def test_catalog_failure_uses_closed_diagnostic() -> None:
    class _FailingConnection:
        def execute(self, _statement: str, _parameters: tuple[str, ...]):
            raise RuntimeError("password=secret system=7411111111111111111")

    with pytest.raises(catalog.CatalogIdentityError) as raised:
        catalog.observe_catalog_identity(_FailingConnection(), TENANT_SERVICE)

    assert str(raised.value) == "catalog verifier routines are unreadable"
    assert "password" not in str(raised.value)
