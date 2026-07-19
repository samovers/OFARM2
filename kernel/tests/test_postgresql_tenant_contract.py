"""Pure contract tests for the tenant capability and binder boundary."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace

import pytest

from deployment.postgresql.tenant_contract import (
    TENANT_BINDER_AUDIENCE,
    TENANT_BINDER_ROUTINE_SIGNATURES,
    TENANT_CAPABILITY_BOUNDS_POLICY,
    TENANT_CAPABILITY_CONTRACT,
    TENANT_CAPABILITY_CONTRACT_DIGEST_POLICY,
    TENANT_CAPABILITY_DOMAIN,
    TENANT_CAPABILITY_DOMAIN_IDENTIFIER,
    TENANT_CAPABILITY_EQUALITY_POLICY,
    TENANT_CAPABILITY_KEY_ROW_POLICY,
    TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS,
    TENANT_CAPABILITY_MAX_TTL_MICROSECONDS,
    BinderRoutineSignature,
    TenantCapability,
    TenantCapabilityContractError,
    canonical_tenant_capability_bytes,
    tenant_capability_hmac,
    validate_tenant_capability,
    validate_tenant_capability_key_row,
    validate_tenant_capability_mac,
)


_ISSUED_AT = 1_800_000_000_000_000
_SECRET = bytes(range(32))


def _capability(**changes: object) -> TenantCapability:
    value = TenantCapability(
        challenge_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        audience=TENANT_BINDER_AUDIENCE,
        key_id="key-2026-01",
        equality_policy=TENANT_CAPABILITY_EQUALITY_POLICY,
        issuer="https://issuer.example.test/tenant",
        subject="subject-01",
        binding_version_id=uuid.UUID(
            "22222222-2222-4222-8222-222222222222"
        ),
        binding_version_digest=bytes.fromhex("11" * 32),
        lifecycle_head_id=uuid.UUID(
            "33333333-3333-4333-8333-333333333333"
        ),
        lifecycle_head_digest=bytes.fromhex("22" * 32),
        tenant_id=uuid.UUID("44444444-4444-4444-8444-444444444444"),
        tenant_registration_digest=bytes.fromhex("33" * 32),
        party_ref="party-01",
        party_record_kind="ofarm.party.v0.1",
        party_record_id="party-01",
        party_schema_digest=bytes.fromhex("44" * 32),
        party_payload_digest=bytes.fromhex("55" * 32),
        issued_at_unix_microseconds=_ISSUED_AT,
        not_before_unix_microseconds=_ISSUED_AT,
        expires_at_unix_microseconds=(
            _ISSUED_AT + TENANT_CAPABILITY_MAX_TTL_MICROSECONDS
        ),
        nonce=uuid.UUID("55555555-5555-4555-8555-555555555555"),
    )
    return replace(value, **changes)


def test_contract_manifest_is_canonical_ascii_non_secret_and_content_addressed():
    contract = TENANT_CAPABILITY_CONTRACT
    encoded = contract.canonical_manifest_bytes()
    manifest = contract.manifest()

    assert TENANT_CAPABILITY_CONTRACT_DIGEST_POLICY == (
        "OFARM_POSTGRESQL_TENANT_CAPABILITY_CONTRACT_V1"
    )
    assert TENANT_CAPABILITY_DOMAIN == b"OFARM_TENANT_CAPABILITY_V1\x00"
    assert TENANT_CAPABILITY_DOMAIN_IDENTIFIER == "OFARM_TENANT_CAPABILITY_V1"
    assert json.loads(encoded) == manifest
    assert encoded.decode("ascii").endswith("\n")
    assert manifest["capability"]["versionCarriedAsField"] is False
    assert manifest["capability"]["boundsPolicy"] == (
        TENANT_CAPABILITY_BOUNDS_POLICY
    )
    assert manifest["capability"]["timeOrder"] == (
        "issuedAt <= notBefore < expiresAt"
    )
    assert manifest["verificationKeyRows"]["validityBounds"] == {
        "from": "signed-unix-microseconds-inclusive",
        "until": "signed-unix-microseconds-exclusive",
        "rule": "validFromUnixMicroseconds < validUntilUnixMicroseconds",
        "unboundedEndpointsAllowed": False,
    }
    assert manifest["verificationKeyRows"]["policy"] == (
        TENANT_CAPABILITY_KEY_ROW_POLICY
    )
    assert contract.digest == (
        "sha256:a4d104f8ad7c5eab11a5b8d17293e82a6d4ac5f224ba0307c4e2cc07fa928e55"
    )
    assert _SECRET.hex() not in encoded.decode("ascii")


def test_exact_core_type_binder_signatures_are_frozen():
    assert tuple(routine.identity for routine in TENANT_BINDER_ROUTINE_SIGNATURES) == (
        "ofarm.create_tenant_challenge()",
        (
            "ofarm.bind_tenant_capability(uuid,text,text,text,text,text,uuid,"
            "bytea,uuid,bytea,uuid,bytea,text,text,text,bytea,bytea,bigint,"
            "bigint,bigint,uuid,bytea)"
        ),
        "ofarm.current_tenant_id()",
        "ofarm.take_tenant_write_lock()",
    )


def test_manifest_field_order_and_sql_types_match_binder_arguments_before_mac():
    capability_manifest = TENANT_CAPABILITY_CONTRACT.manifest()["capability"]
    framing = capability_manifest["framing"]
    assert [field["field"] for field in framing] == [
        "challengeId",
        "audience",
        "keyId",
        "equalityPolicy",
        "issuer",
        "subject",
        "bindingVersionId",
        "bindingVersionDigest",
        "lifecycleHeadId",
        "lifecycleHeadDigest",
        "tenantId",
        "tenantRegistrationDigest",
        "partyRef",
        "partyRecordKind",
        "partyRecordId",
        "partySchemaDigest",
        "partyPayloadDigest",
        "issuedAtUnixMicroseconds",
        "notBeforeUnixMicroseconds",
        "expiresAtUnixMicroseconds",
        "nonce",
    ]
    assert all(field["frame"].startswith("lp32(") for field in framing)
    binder = TENANT_BINDER_ROUTINE_SIGNATURES[1]
    assert tuple(field["sqlType"] for field in framing) == (
        binder.argument_types[:-1]
    )
    assert binder.argument_types[-1] == "bytea"


def test_signature_change_changes_contract_digest():
    original = TENANT_CAPABILITY_CONTRACT
    changed = replace(
        original,
        routines=original.routines[:-1]
        + (BinderRoutineSignature("take_tenant_write_lock", ("bigint",)),),
    )
    assert changed.digest != original.digest


def test_capability_golden_bytes_hmac_and_all_field_lp32_are_frozen():
    framed = canonical_tenant_capability_bytes(_capability())
    cursor = len(TENANT_CAPABILITY_DOMAIN)
    field_lengths: list[int] = []
    while cursor < len(framed):
        length = int.from_bytes(framed[cursor : cursor + 4], "big")
        cursor += 4
        field_lengths.append(length)
        cursor += length

    assert cursor == len(framed)
    assert len(field_lengths) == 21
    assert field_lengths == [
        16,
        len(TENANT_BINDER_AUDIENCE),
        len("key-2026-01"),
        len(TENANT_CAPABILITY_EQUALITY_POLICY),
        len("https://issuer.example.test/tenant"),
        len("subject-01"),
        16,
        32,
        16,
        32,
        16,
        32,
        len("party-01"),
        len("ofarm.party.v0.1"),
        len("party-01"),
        32,
        32,
        8,
        8,
        8,
        16,
    ]
    assert len(framed) == 502
    assert hashlib.sha256(framed).hexdigest() == (
        "b8cf399fc84251d58e699f58c853345c71dc2a56e3da3f17344aaf1208fbb012"
    )
    assert tenant_capability_hmac(_SECRET, _capability()).hex() == (
        "0ff2c776ce7dfb5d1ab2419d7aa18df4fe55c39e7b85bb4dbd0b19c3be6ab466"
    )


def test_lp32_principal_framing_prevents_delimiter_free_collision():
    first = _capability(issuer="https://a", subject="bc")
    second = _capability(issuer="https://ab", subject="c")
    assert first.issuer + first.subject == second.issuer + second.subject
    assert canonical_tenant_capability_bytes(first) != (
        canonical_tenant_capability_bytes(second)
    )


@pytest.mark.parametrize(
    "field",
    (
        "challenge_id",
        "binding_version_id",
        "lifecycle_head_id",
        "tenant_id",
        "nonce",
    ),
)
def test_every_capability_uuid_refuses_nil(field: str):
    with pytest.raises(TenantCapabilityContractError, match="nil UUID"):
        validate_tenant_capability(_capability(**{field: uuid.UUID(int=0)}))


def test_exact_text_and_raw_digest_forms_refuse_variants():
    invalid = (
        {"audience": TENANT_BINDER_AUDIENCE + "-other"},
        {"equality_policy": "oidc_exact_utf8_v1"},
        {"party_record_kind": "ofarm.party.v0.2"},
        {"party_record_id": "different-party"},
        {"binding_version_digest": "sha256:" + "11" * 32},
        {"lifecycle_head_digest": b"x" * 31},
        {"party_payload_digest": bytearray(b"x" * 32)},
    )
    for change in invalid:
        with pytest.raises(TenantCapabilityContractError):
            validate_tenant_capability(_capability(**change))


def test_text_bounds_accept_exact_maxima_and_refuse_one_byte_over():
    exact_issuer = "https://i/" + "a" * 2038
    exact_party = "p" * 255
    validate_tenant_capability(
        _capability(
            key_id="k" * 255,
            issuer=exact_issuer,
            subject="s" * 255,
            party_ref=exact_party,
            party_record_id=exact_party,
        )
    )
    invalid = (
        {"key_id": "k" * 256},
        {"issuer": exact_issuer + "a"},
        {"subject": "s" * 256},
        {"subject": "contains space"},
        {"party_ref": "party/01", "party_record_id": "party/01"},
    )
    for change in invalid:
        with pytest.raises(TenantCapabilityContractError):
            validate_tenant_capability(_capability(**change))


@pytest.mark.parametrize(
    "issuer",
    (
        "http://issuer.example.test",
        "https://issuer.example.test?query=1",
        "https://issuer.example.test#fragment",
        "https://user@issuer.example.test",
        "https://issuer.example.test:70000",
        "https://[invalid",
        "https://issuer.example.test/white space",
    ),
)
def test_issuer_grammar_refuses_widening(issuer: str):
    with pytest.raises(TenantCapabilityContractError):
        validate_tenant_capability(_capability(issuer=issuer))


@pytest.mark.parametrize("ttl", (1, TENANT_CAPABILITY_MAX_TTL_MICROSECONDS))
def test_positive_ttl_boundary_is_accepted(ttl: int):
    validate_tenant_capability(
        _capability(expires_at_unix_microseconds=_ISSUED_AT + ttl)
    )


@pytest.mark.parametrize(
    "changes",
    (
        {"expires_at_unix_microseconds": _ISSUED_AT},
        {
            "expires_at_unix_microseconds": (
                _ISSUED_AT + TENANT_CAPABILITY_MAX_TTL_MICROSECONDS + 1
            )
        },
        {"not_before_unix_microseconds": _ISSUED_AT - 1},
        {
            "issued_at_unix_microseconds": _ISSUED_AT + 2,
            "not_before_unix_microseconds": _ISSUED_AT + 1,
        },
    ),
)
def test_invalid_time_order_or_ttl_refuses(changes: dict[str, int]):
    with pytest.raises(TenantCapabilityContractError):
        validate_tenant_capability(_capability(**changes))


def test_future_skew_and_expiry_are_exact():
    now = _ISSUED_AT
    future = now + TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS
    validate_tenant_capability(
        _capability(
            issued_at_unix_microseconds=future,
            not_before_unix_microseconds=future,
            expires_at_unix_microseconds=future + 1,
        ),
        now_unix_microseconds=now,
    )
    with pytest.raises(TenantCapabilityContractError, match="future-skew"):
        validate_tenant_capability(
            _capability(
                issued_at_unix_microseconds=future + 1,
                not_before_unix_microseconds=future + 1,
                expires_at_unix_microseconds=future + 2,
            ),
            now_unix_microseconds=now,
        )
    with pytest.raises(TenantCapabilityContractError, match="expired"):
        validate_tenant_capability(
            _capability(
                issued_at_unix_microseconds=now - 2,
                not_before_unix_microseconds=now - 1,
                expires_at_unix_microseconds=now,
            ),
            now_unix_microseconds=now,
        )


def test_signed_int64_and_exact_runtime_types_are_required():
    invalid = (
        {"issued_at_unix_microseconds": True},
        {"issued_at_unix_microseconds": -(2**63) - 1},
        {"expires_at_unix_microseconds": 2**63},
        {"challenge_id": "11111111-1111-4111-8111-111111111111"},
    )
    for change in invalid:
        with pytest.raises(TenantCapabilityContractError):
            validate_tenant_capability(_capability(**change))


def test_key_rows_and_mac_wire_form_are_exact_and_bounded():
    validate_tenant_capability_key_row(
        key_id="key-2026-01",
        secret=_SECRET,
        valid_from_unix_microseconds=_ISSUED_AT,
        valid_until_unix_microseconds=_ISSUED_AT + 1,
    )
    validate_tenant_capability_mac(b"m" * 32)
    with pytest.raises(TenantCapabilityContractError, match="increasing"):
        validate_tenant_capability_key_row(
            key_id="key-2026-01",
            secret=_SECRET,
            valid_from_unix_microseconds=_ISSUED_AT,
            valid_until_unix_microseconds=_ISSUED_AT,
        )
    for value in (b"m" * 31, b"m" * 33, bytearray(b"m" * 32)):
        with pytest.raises(TenantCapabilityContractError, match="32 bytes"):
            validate_tenant_capability_mac(value)  # type: ignore[arg-type]


def test_each_mutable_signed_group_changes_the_mac():
    original = _capability()
    original_mac = tenant_capability_hmac(_SECRET, original)
    changes = (
        {"key_id": "key-2026-02"},
        {"challenge_id": uuid.UUID("61111111-1111-4111-8111-111111111111")},
        {"issuer": "https://other.example.test/tenant"},
        {"subject": "subject-02"},
        {"binding_version_digest": b"a" * 32},
        {"lifecycle_head_digest": b"b" * 32},
        {"tenant_registration_digest": b"c" * 32},
        {"party_ref": "party-02", "party_record_id": "party-02"},
        {"party_schema_digest": b"d" * 32},
        {"party_payload_digest": b"e" * 32},
        {
            "not_before_unix_microseconds": _ISSUED_AT + 1,
            "expires_at_unix_microseconds": (
                _ISSUED_AT + TENANT_CAPABILITY_MAX_TTL_MICROSECONDS
            ),
        },
        {
            "expires_at_unix_microseconds": (
                _ISSUED_AT + TENANT_CAPABILITY_MAX_TTL_MICROSECONDS - 1
            )
        },
        {"nonce": uuid.UUID("65555555-5555-4555-8555-555555555555")},
    )
    for change in changes:
        assert tenant_capability_hmac(
            _SECRET, _capability(**change)
        ) != original_mac
