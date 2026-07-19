"""Pure tests for the #174 fail-closed tenant-context posture."""

from __future__ import annotations

from dataclasses import replace

import pytest

import deployment.postgresql.tenant_contract as tenant_contract
from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    OIDC_ISSUER_GRAMMAR_POLICY,
    OIDC_ISSUER_INVALID_VECTORS,
    OIDC_ISSUER_MAX_BYTES,
    OIDC_ISSUER_VALID_VECTORS,
    TENANT_CONTEXT_CONTRACT,
    TENANT_CONTEXT_CONTRACT_DIGEST_POLICY,
    TENANT_CONTEXT_ROUTINE_SIGNATURES,
    TenantContextContractError,
    valid_oidc_issuer,
    validate_oidc_issuer,
)


def test_context_posture_is_explicitly_fail_closed_and_crypto_free() -> None:
    manifest = TENANT_CONTEXT_CONTRACT.manifest()
    assert TENANT_CONTEXT_CONTRACT_DIGEST_POLICY == (
        "OFARM_POSTGRESQL_TENANT_CONTEXT_POSTURE_V1"
    )
    assert manifest["schemaVersion"] == (
        "ofarm.postgresql-tenant-context-posture.v1"
    )
    assert manifest["tenantContextContractDigest"] == (
        "sha256:4e0acd383a1c44142043c51f2bca26fbddc0f191dcf511c2aa97d212d3a6cb62"
    )
    assert manifest["productionBinding"] == {
        "available": False,
        "deferredIssue": 172,
        "forwardMigrationRequired": True,
        "cryptographicContract": None,
        "wireContract": None,
        "verificationKeyCustody": None,
        "reason": "issue #174 supplies no accepted production verifier or binder",
    }
    assert "algorithm" not in manifest
    assert "framing" not in manifest
    assert "keySchedule" not in manifest
    canonical_text = TENANT_CONTEXT_CONTRACT.canonical_manifest_bytes().decode(
        "ascii"
    )
    for forbidden_field in (
        '"notBefore"',
        '"notBeforeUnixMicroseconds"',
        '"validUntil"',
        '"issuedAt"',
        '"expiresAt"',
        '"algorithm"',
        '"hmac"',
        '"framing"',
        '"keySchedule"',
    ):
        assert forbidden_field not in canonical_text


def test_context_routines_freeze_no_production_binder_signature() -> None:
    assert tuple(routine.identity for routine in TENANT_CONTEXT_ROUTINE_SIGNATURES) == (
        "ofarm.create_tenant_challenge()",
        "ofarm.current_tenant_id()",
        "ofarm.take_tenant_write_lock()",
    )
    assert all(
        routine.name != "bind_tenant_capability"
        for routine in TENANT_CONTEXT_ROUTINE_SIGNATURES
    )


def test_removed_crypto_api_is_not_part_of_the_tenant_contract_module() -> None:
    removed_names = (
        "TENANT_BINDER_AUDIENCE",
        "TENANT_CAPABILITY_DOMAIN",
        "TENANT_CAPABILITY_KEY_ROW_POLICY",
        "TENANT_CAPABILITY_MAC_ALGORITHM",
        "TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS",
        "TENANT_CAPABILITY_MAX_TTL_MICROSECONDS",
        "TenantCapability",
        "canonical_tenant_capability_bytes",
        "tenant_capability_hmac",
        "validate_tenant_capability",
        "validate_tenant_capability_key_row",
        "validate_tenant_capability_mac",
    )
    assert all(not hasattr(tenant_contract, name) for name in removed_names)


def test_context_manifest_digest_changes_with_any_declared_posture() -> None:
    original = TENANT_CONTEXT_CONTRACT
    assert replace(original, identity=original.identity + "-other").digest != (
        original.digest
    )
    assert replace(
        original,
        issuer_grammar_policy=original.issuer_grammar_policy + "-other",
    ).digest != original.digest
    assert replace(original, context_routines=original.context_routines[:-1]).digest != (
        original.digest
    )


@pytest.mark.parametrize("issuer", OIDC_ISSUER_VALID_VECTORS)
def test_shared_valid_issuer_vectors_accept_exactly(issuer: str) -> None:
    assert valid_oidc_issuer(issuer) is True
    assert validate_oidc_issuer(issuer) == issuer


@pytest.mark.parametrize("issuer", OIDC_ISSUER_INVALID_VECTORS)
def test_shared_invalid_issuer_vectors_refuse_exactly(issuer: str) -> None:
    assert valid_oidc_issuer(issuer) is False
    with pytest.raises(TenantContextContractError, match=OIDC_ISSUER_GRAMMAR_POLICY):
        validate_oidc_issuer(issuer)


def test_issuer_octet_host_label_and_port_boundaries_are_exact() -> None:
    maximum = "https://i.test/" + "a" * (
        OIDC_ISSUER_MAX_BYTES - len("https://i.test/")
    )
    assert len(maximum.encode("ascii")) == OIDC_ISSUER_MAX_BYTES
    assert valid_oidc_issuer(maximum) is True
    assert valid_oidc_issuer(maximum + "a") is False

    assert valid_oidc_issuer("https://" + "a" * 63 + ".test") is True
    assert valid_oidc_issuer("https://" + "a" * 64 + ".test") is False
    assert valid_oidc_issuer("https://issuer.test:1") is True
    assert valid_oidc_issuer("https://issuer.test:65535") is True
    assert valid_oidc_issuer("https://issuer.test:0") is False
    assert valid_oidc_issuer("https://issuer.test:65536") is False
    # PostgreSQL text rejects NUL before a domain/function can observe it.
    assert valid_oidc_issuer("https://issuer.test/\x00") is False


@pytest.mark.parametrize("issuer", (None, 1, True, b"https://issuer.test"))
def test_issuer_policy_rejects_non_text_runtime_types(issuer: object) -> None:
    assert valid_oidc_issuer(issuer) is False


def test_issuer_policy_identity_is_exact() -> None:
    manifest = TENANT_CONTEXT_CONTRACT.manifest()["issuerPolicy"]
    assert manifest["equalityPolicy"] == OIDC_ISSUER_EQUALITY_POLICY
    assert manifest["grammarPolicy"] == OIDC_ISSUER_GRAMMAR_POLICY
    assert manifest["maximumBytes"] == OIDC_ISSUER_MAX_BYTES
    assert manifest["comparison"] == "exact case-sensitive bytes"
