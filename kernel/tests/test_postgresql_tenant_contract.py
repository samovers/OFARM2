"""Pure cross-layer tests for the accepted #174 TenantCapability contract."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import replace
from uuid import UUID

import pytest

from deployment.postgresql.tenant_contract import (
    BINDER_AUDIENCE_INVALID_VECTORS,
    BINDER_AUDIENCE_VALID_VECTORS,
    GOOGLE_KMS_ED25519_VECTOR,
    GOOGLE_KMS_KEY_ALGORITHM,
    GOOGLE_KMS_PROTECTION_LEVEL,
    GOOGLE_KMS_PUBLIC_KEY_FORMAT,
    GOOGLE_KMS_KEY_VERSION_RESOURCE_INVALID_VECTORS,
    GOOGLE_KMS_KEY_VERSION_RESOURCE_PATTERN,
    GOOGLE_KMS_KEY_VERSION_RESOURCE_VALID_VECTORS,
    OIDC_ISSUER_EQUALITY_POLICY,
    OIDC_ISSUER_GRAMMAR_POLICY,
    OIDC_ISSUER_INVALID_VECTORS,
    OIDC_ISSUER_MAX_BYTES,
    OIDC_ISSUER_VALID_VECTORS,
    OIDC_SUBJECT_INVALID_VECTORS,
    OIDC_SUBJECT_VALID_VECTORS,
    TENANT_CAPABILITY_ALGORITHM,
    TENANT_CAPABILITY_CONTRACT,
    TENANT_CAPABILITY_CONTRACT_MANIFEST_PATH,
    TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS,
    TENANT_CAPABILITY_MAX_TTL_MICROSECONDS,
    TENANT_CAPABILITY_PREFLIGHT_PROBE,
    TENANT_CAPABILITY_RFC8410_PREFIX,
    TENANT_CAPABILITY_TYPE,
    TENANT_CONTEXT_ROUTINE_SIGNATURES,
    TenantCapability,
    TenantCapabilityContractError,
    canonical_jws_signing_input,
    canonical_tenant_capability_payload,
    decode_tenant_capability_jws,
    derive_binder_audience,
    derive_ed25519_key_id,
    extract_rfc8410_ed25519_public_key,
    extract_google_kms_rest_ed25519_public_key,
    protected_header_bytes,
    raw_public_key_digest,
    valid_google_kms_key_version_resource,
    valid_oidc_issuer,
    validate_google_kms_key_version_resource,
    validate_oidc_issuer,
    validate_binder_audience,
    validate_tenant_capability,
)
from kernel.tests.tenant_capability_fixture import (
    RFC8032_TEST_PUBLIC_KEY,
    RFC8032_TEST_SEED,
    sign,
    sign_capability,
)


INSTANCE_ID = UUID("a58b7238-5019-49e2-9aaf-530287e5a6ee")
KEY_ID = "kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k"


def _capability(**changes: object) -> TenantCapability:
    value = TenantCapability(
        contract_digest=TENANT_CAPABILITY_CONTRACT.raw_digest,
        challenge_id=UUID("b93845ee-939f-4ea7-83cc-e7ee37f758d8"),
        audience=derive_binder_audience(INSTANCE_ID),
        key_id=KEY_ID,
        equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
        issuer="https://issuer.example.test/tenant",
        subject="subject-tenant-01",
        binding_version_id=UUID("ea269d4b-ce32-4632-9ce8-76ea6e093723"),
        binding_version_digest=bytes.fromhex("11" * 32),
        lifecycle_head_id=UUID("58271eed-0667-49b2-8420-578fa6d46765"),
        lifecycle_head_digest=bytes.fromhex("22" * 32),
        tenant_id=UUID("a6b16899-faca-4d90-9a6f-d5a8e609d08f"),
        tenant_registration_digest=bytes.fromhex("33" * 32),
        party_ref="party-01",
        party_record_kind="ofarm.party.v0.1",
        party_record_id="party-01",
        party_schema_digest=bytes.fromhex("44" * 32),
        party_payload_digest=bytes.fromhex("55" * 32),
        issued_at_unix_microseconds=1_750_000_000_000_000,
        not_before_unix_microseconds=1_750_000_000_000_000,
        expires_at_unix_microseconds=1_750_000_060_000_000,
        nonce=UUID("c913ee18-55c8-4a42-a2f4-71e01d23389f"),
    )
    return replace(value, **changes)


def test_manifest_freezes_the_accepted_asymmetric_boundary() -> None:
    manifest = TENANT_CAPABILITY_CONTRACT.manifest()
    assert TENANT_CAPABILITY_CONTRACT.digest == (
        "sha256:39e979fa296122cb66d42eae5e2d7c6dc797ac77ef4324515ae1ab6020088d83"
    )
    assert manifest["envelope"]["algorithm"] == TENANT_CAPABILITY_ALGORITHM
    assert manifest["envelope"]["type"] == TENANT_CAPABILITY_TYPE
    assert manifest["publicKey"]["privateMaterialInDatabase"] is False
    assert manifest["ownership"] == {
        "databaseVerifierAndBinder": 174,
        "productionKmsSignerAndMinting": 172,
        "transactionIntegration": 173,
    }
    canonical = TENANT_CAPABILITY_CONTRACT.canonical_manifest_bytes().lower()
    assert b"hmac" not in canonical
    assert b"secret" not in canonical


def test_manifest_digest_is_over_the_exact_checked_in_bytes_only() -> None:
    source = TENANT_CAPABILITY_CONTRACT_MANIFEST_PATH.read_bytes()
    assert source == TENANT_CAPABILITY_CONTRACT.canonical_manifest_without_digest_bytes()
    assert json.dumps(
        json.loads(source),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    ).encode("ascii") + b"\n" == source
    assert TENANT_CAPABILITY_CONTRACT.digest == (
        "sha256:" + hashlib.sha256(source).hexdigest()
    )
    assert "tenantCapabilityContractDigest" not in json.loads(source)


def test_entry_points_have_one_argument_binder_and_current_context() -> None:
    assert tuple(routine.identity for routine in TENANT_CONTEXT_ROUTINE_SIGNATURES) == (
        "ofarm.create_tenant_challenge()",
        "ofarm.bind_tenant_capability(text)",
        "ofarm.current_tenant_context()",
        "ofarm.current_tenant_id()",
        "ofarm.take_tenant_write_lock()",
    )


@pytest.mark.parametrize("issuer", OIDC_ISSUER_VALID_VECTORS)
def test_shared_valid_issuer_vectors_accept_exactly(issuer: str) -> None:
    assert valid_oidc_issuer(issuer) is True
    assert validate_oidc_issuer(issuer) == issuer


@pytest.mark.parametrize("issuer", OIDC_ISSUER_INVALID_VECTORS)
def test_shared_invalid_issuer_vectors_refuse_exactly(issuer: str) -> None:
    assert valid_oidc_issuer(issuer) is False
    with pytest.raises(TenantCapabilityContractError, match=OIDC_ISSUER_GRAMMAR_POLICY):
        validate_oidc_issuer(issuer)


def test_issuer_octet_label_and_port_boundaries_are_exact() -> None:
    maximum = "https://i.test/" + "a" * (
        OIDC_ISSUER_MAX_BYTES - len("https://i.test/")
    )
    assert len(maximum) == OIDC_ISSUER_MAX_BYTES
    assert valid_oidc_issuer(maximum)
    assert not valid_oidc_issuer(maximum + "a")
    assert valid_oidc_issuer("https://" + "a" * 63 + ".test")
    assert not valid_oidc_issuer("https://" + "a" * 64 + ".test")
    assert valid_oidc_issuer("https://issuer.test:1")
    assert valid_oidc_issuer("https://issuer.test:65535")
    assert not valid_oidc_issuer("https://issuer.test:01")


@pytest.mark.parametrize("audience", BINDER_AUDIENCE_VALID_VECTORS)
def test_shared_valid_audience_vectors_accept_exactly(audience: str) -> None:
    assert validate_binder_audience(audience) == audience


@pytest.mark.parametrize("audience", BINDER_AUDIENCE_INVALID_VECTORS)
def test_shared_invalid_audience_vectors_refuse_exactly(audience: str) -> None:
    with pytest.raises(TenantCapabilityContractError):
        validate_binder_audience(audience)


@pytest.mark.parametrize("subject", OIDC_SUBJECT_VALID_VECTORS)
def test_shared_valid_subject_vectors_accept_exactly(subject: str) -> None:
    validate_tenant_capability(_capability(subject=subject))


@pytest.mark.parametrize("subject", OIDC_SUBJECT_INVALID_VECTORS)
def test_shared_invalid_subject_vectors_refuse_exactly(subject: str) -> None:
    with pytest.raises(TenantCapabilityContractError):
        validate_tenant_capability(_capability(subject=subject))


def test_rfc8410_raw_key_digest_x_and_kid_are_one_exact_vector() -> None:
    der = TENANT_CAPABILITY_RFC8410_PREFIX + RFC8032_TEST_PUBLIC_KEY
    assert der.hex() == (
        "302a300506032b6570032100"
        "d75a980182b10ab7d54bfed3c964073a"
        "0ee172f3daa62325af021a68f707511a"
    )
    assert base64.b64encode(der).decode("ascii") == (
        "MCowBQYDK2VwAyEA11qYAYKxCrfVS/7TyWQHOg7hcvPapiMlrwIaaPcHURo="
    )
    assert extract_rfc8410_ed25519_public_key(der) == RFC8032_TEST_PUBLIC_KEY
    assert raw_public_key_digest(RFC8032_TEST_PUBLIC_KEY).hex() == (
        "21fe31dfa154a261626bf854046fd2271b7bed4b6abe45aa58877ef47f9721b9"
    )
    assert derive_ed25519_key_id(RFC8032_TEST_PUBLIC_KEY) == KEY_ID


def _kms_response(**changes: object) -> bytes:
    response: dict[str, object] = {
        "name": GOOGLE_KMS_ED25519_VECTOR["name"],
        "algorithm": GOOGLE_KMS_KEY_ALGORITHM,
        "protectionLevel": GOOGLE_KMS_PROTECTION_LEVEL,
        "publicKeyFormat": GOOGLE_KMS_PUBLIC_KEY_FORMAT,
        "publicKey": {
            "data": GOOGLE_KMS_ED25519_VECTOR["transportBase64"],
            "crc32cChecksum": str(GOOGLE_KMS_ED25519_VECTOR["crc32c"]),
        },
    }
    response.update(changes)
    return json.dumps(response, separators=(",", ":")).encode("ascii")


def _crc32c(value: bytes) -> int:
    checksum = 0xFFFFFFFF
    for octet in value:
        checksum ^= octet
        for _ in range(8):
            checksum = (checksum >> 1) ^ (
                0x82F63B78 if checksum & 1 else 0
            )
    return checksum ^ 0xFFFFFFFF


def test_complete_google_kms_rest_response_maps_to_one_raw_key() -> None:
    observed = extract_google_kms_rest_ed25519_public_key(
        _kms_response(),
        expected_key_version_resource=str(GOOGLE_KMS_ED25519_VECTOR["name"]),
    )
    assert observed.der.hex() == GOOGLE_KMS_ED25519_VECTOR["derHex"]
    assert observed.public_key.hex() == GOOGLE_KMS_ED25519_VECTOR["rawKeyHex"]
    assert (
        observed.public_key_digest.hex()
        == GOOGLE_KMS_ED25519_VECTOR["rawKeySha256"]
    )
    assert observed.x == GOOGLE_KMS_ED25519_VECTOR["x"]
    assert observed.kid == GOOGLE_KMS_ED25519_VECTOR["kid"]


@pytest.mark.parametrize(
    "resource", GOOGLE_KMS_KEY_VERSION_RESOURCE_VALID_VECTORS
)
def test_google_kms_resource_shared_valid_vectors_accept(resource: str) -> None:
    assert valid_google_kms_key_version_resource(resource)
    assert validate_google_kms_key_version_resource(resource) == resource


@pytest.mark.parametrize(
    "resource", GOOGLE_KMS_KEY_VERSION_RESOURCE_INVALID_VECTORS
)
def test_google_kms_resource_shared_invalid_vectors_refuse(resource: str) -> None:
    assert not valid_google_kms_key_version_resource(resource)
    with pytest.raises(TenantCapabilityContractError):
        validate_google_kms_key_version_resource(resource)
    with pytest.raises(TenantCapabilityContractError):
        extract_google_kms_rest_ed25519_public_key(
            _kms_response(name=resource),
            expected_key_version_resource=resource,
        )


def test_database_candidate_and_registration_use_the_same_kms_resource_grammar() -> None:
    migration = (
        TENANT_CAPABILITY_CONTRACT_MANIFEST_PATH.parents[2]
        / "kernel"
        / "migrations"
        / "0001_initial.sql"
    ).read_text("utf-8")
    assert migration.count(GOOGLE_KMS_KEY_VERSION_RESOURCE_PATTERN) == 2


@pytest.mark.parametrize(
    "response",
    (
        b"{}",
        _kms_response(pem="forbidden"),
        _kms_response(algorithm="EDDSA"),
        _kms_response(protectionLevel="SOFTWARE"),
        _kms_response(publicKeyFormat="PEM"),
        _kms_response(name="projects/other/cryptoKeyVersions/2"),
        (
            b'{"name":"a","name":"b","algorithm":"EC_SIGN_ED25519",'
            b'"protectionLevel":"HSM","publicKeyFormat":"DER",'
            b'"publicKey":{"data":"AA==","crc32cChecksum":"0"}}'
        ),
    ),
)
def test_google_kms_response_shape_and_identity_refuse(response: bytes) -> None:
    with pytest.raises(TenantCapabilityContractError):
        extract_google_kms_rest_ed25519_public_key(
            response,
            expected_key_version_resource=str(GOOGLE_KMS_ED25519_VECTOR["name"]),
        )


@pytest.mark.parametrize(
    "data",
    (
        str(GOOGLE_KMS_ED25519_VECTOR["transportBase64"]).rstrip("="),
        str(GOOGLE_KMS_ED25519_VECTOR["transportBase64"]) + "=",
        str(GOOGLE_KMS_ED25519_VECTOR["transportBase64"]).replace("/", "_"),
        str(GOOGLE_KMS_ED25519_VECTOR["transportBase64"]) + "\n",
    ),
)
def test_google_kms_rest_base64_transport_must_be_canonical(data: str) -> None:
    with pytest.raises(TenantCapabilityContractError):
        extract_google_kms_rest_ed25519_public_key(
            _kms_response(
                publicKey={
                    "data": data,
                    "crc32cChecksum": str(GOOGLE_KMS_ED25519_VECTOR["crc32c"]),
                }
            ),
            expected_key_version_resource=str(GOOGLE_KMS_ED25519_VECTOR["name"]),
        )


@pytest.mark.parametrize(
    "checksum",
    (-1, 0, 3_927_069_631, "", "03927069631", "-1", "4294967296"),
)
def test_google_kms_rest_crc32c_transport_and_value_are_exact(
    checksum: object,
) -> None:
    with pytest.raises(TenantCapabilityContractError):
        extract_google_kms_rest_ed25519_public_key(
            _kms_response(
                publicKey={
                    "data": GOOGLE_KMS_ED25519_VECTOR["transportBase64"],
                    "crc32cChecksum": checksum,
                }
            ),
            expected_key_version_resource=str(GOOGLE_KMS_ED25519_VECTOR["name"]),
        )


def test_google_kms_mutation_requires_crc_then_changes_identity_or_refuses_shape() -> None:
    der = bytearray(bytes.fromhex(str(GOOGLE_KMS_ED25519_VECTOR["derHex"])))
    der[-1] ^= 1
    transport = base64.b64encode(der).decode("ascii")
    with pytest.raises(TenantCapabilityContractError, match="CRC32C"):
        extract_google_kms_rest_ed25519_public_key(
            _kms_response(
                publicKey={
                    "data": transport,
                    "crc32cChecksum": str(
                        GOOGLE_KMS_ED25519_VECTOR["crc32c"]
                    ),
                }
            ),
            expected_key_version_resource=str(GOOGLE_KMS_ED25519_VECTOR["name"]),
        )
    changed = extract_google_kms_rest_ed25519_public_key(
        _kms_response(
            publicKey={
                "data": transport,
                "crc32cChecksum": str(_crc32c(bytes(der))),
            }
        ),
        expected_key_version_resource=str(GOOGLE_KMS_ED25519_VECTOR["name"]),
    )
    assert changed.public_key_digest.hex() != GOOGLE_KMS_ED25519_VECTOR[
        "rawKeySha256"
    ]
    assert changed.kid != GOOGLE_KMS_ED25519_VECTOR["kid"]

    malformed = bytearray(bytes.fromhex(str(GOOGLE_KMS_ED25519_VECTOR["derHex"])))
    malformed[6] ^= 1
    with pytest.raises(TenantCapabilityContractError, match="prefix"):
        extract_google_kms_rest_ed25519_public_key(
            _kms_response(
                publicKey={
                    "data": base64.b64encode(malformed).decode("ascii"),
                    "crc32cChecksum": str(_crc32c(bytes(malformed))),
                }
            ),
            expected_key_version_resource=str(GOOGLE_KMS_ED25519_VECTOR["name"]),
        )


@pytest.mark.parametrize(
    "mutated",
    (
        b"",
        TENANT_CAPABILITY_RFC8410_PREFIX[:-1] + RFC8032_TEST_PUBLIC_KEY,
        bytes.fromhex("302c300706032b65700500032100") + RFC8032_TEST_PUBLIC_KEY,
        TENANT_CAPABILITY_RFC8410_PREFIX + RFC8032_TEST_PUBLIC_KEY + b"\x00",
        bytes.fromhex("302a300506032b656e032100") + RFC8032_TEST_PUBLIC_KEY,
    ),
)
def test_every_non_exact_spki_shape_refuses(mutated: bytes) -> None:
    with pytest.raises(TenantCapabilityContractError):
        extract_rfc8410_ed25519_public_key(mutated)


def test_preflight_probe_is_fixed_and_not_a_jws_or_capability() -> None:
    assert len(TENANT_CAPABILITY_PREFLIGHT_PROBE) == 43
    assert TENANT_CAPABILITY_PREFLIGHT_PROBE.hex() == (
        "004f4641524d322d54454e414e542d4341504142494c4954592d4b4d532d"
        "505245464c494748542d563100"
    )
    assert b"." not in TENANT_CAPABILITY_PREFLIGHT_PROBE
    with pytest.raises(TenantCapabilityContractError):
        decode_tenant_capability_jws(
            TENANT_CAPABILITY_PREFLIGHT_PROBE.decode("ascii")
        )


def test_payload_and_compact_jws_round_trip_byte_exactly() -> None:
    capability = _capability()
    payload = canonical_tenant_capability_payload(capability)
    assert payload.startswith(b"OFARM_TENANT_CAPABILITY_V1\x00")
    assert payload[27:31] == (32).to_bytes(4, "big")
    assert protected_header_bytes(KEY_ID) == (
        b'{"alg":"Ed25519","kid":"kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k",'
        b'"typ":"ofarm-tenant-capability+jws"}'
    )
    token = sign_capability(capability)
    decoded = decode_tenant_capability_jws(token)
    assert decoded.capability == capability
    assert decoded.payload == payload
    assert decoded.signing_input == canonical_jws_signing_input(capability)
    assert len(decoded.signature) == 64


def test_fixture_signer_matches_rfc8032_empty_message_vector() -> None:
    assert sign(RFC8032_TEST_SEED, b"").hex() == (
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("contract_digest", b"\x00" * 32),
        ("audience", "urn:other"),
        ("key_id", "a" * 42),
        ("equality_policy", "OTHER"),
        ("issuer", "https://issuer.example.test:70000"),
        ("subject", "subject with space"),
        ("party_record_kind", "other"),
        ("party_record_id", "other-party"),
        ("binding_version_digest", b"short"),
        ("issued_at_unix_microseconds", -(2**63) - 1),
    ),
)
def test_each_closed_field_class_refuses(field: str, value: object) -> None:
    with pytest.raises(TenantCapabilityContractError):
        validate_tenant_capability(_capability(**{field: value}))


def test_time_boundaries_match_the_accepted_rule() -> None:
    capability = _capability()
    now = capability.issued_at_unix_microseconds - (
        TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS
    )
    created = capability.issued_at_unix_microseconds
    validate_tenant_capability(
        capability,
        now_unix_microseconds=now,
        challenge_created_at_unix_microseconds=created,
    )
    assert (
        capability.expires_at_unix_microseconds
        - capability.issued_at_unix_microseconds
        == TENANT_CAPABILITY_MAX_TTL_MICROSECONDS
    )
    with pytest.raises(TenantCapabilityContractError, match="expired"):
        validate_tenant_capability(
            capability,
            now_unix_microseconds=capability.expires_at_unix_microseconds,
        )
    with pytest.raises(TenantCapabilityContractError, match="lifetime"):
        validate_tenant_capability(
            replace(
                capability,
                expires_at_unix_microseconds=(
                    capability.issued_at_unix_microseconds
                    + TENANT_CAPABILITY_MAX_TTL_MICROSECONDS
                    + 1
                ),
            )
        )


def test_shared_time_vectors_match_the_reference_validator() -> None:
    cases = TENANT_CAPABILITY_CONTRACT.manifest_without_digest()[
        "sharedVectors"
    ]["time"]
    for case in cases:
        capability = _capability(
            issued_at_unix_microseconds=case["issuedAt"],
            not_before_unix_microseconds=case["notBefore"],
            expires_at_unix_microseconds=case["expiresAt"],
        )
        if case["result"] == "accept":
            validate_tenant_capability(
                capability,
                now_unix_microseconds=case["now"],
                challenge_created_at_unix_microseconds=case[
                    "challengeCreatedAt"
                ],
            )
        else:
            with pytest.raises(TenantCapabilityContractError):
                validate_tenant_capability(
                    capability,
                    now_unix_microseconds=case["now"],
                    challenge_created_at_unix_microseconds=case[
                        "challengeCreatedAt"
                    ],
                )


@pytest.mark.parametrize(
    "nonce",
    (
        UUID("00000000-0000-0000-0000-000000000000"),
        UUID("c913ee18-55c8-5a42-a2f4-71e01d23389f"),
        UUID("c913ee18-55c8-4a42-72f4-71e01d23389f"),
    ),
)
def test_nonce_must_be_rfc4122_variant_uuidv4(nonce: UUID) -> None:
    with pytest.raises(TenantCapabilityContractError, match="UUIDv4|non-nil"):
        validate_tenant_capability(_capability(nonce=nonce))


def test_noncanonical_base64_header_and_digest_substitution_refuse() -> None:
    capability = _capability()
    token = sign_capability(capability)
    header, payload, signature = token.split(".")
    with pytest.raises(TenantCapabilityContractError):
        decode_tenant_capability_jws(header + "=" + "." + payload + "." + signature)
    der_digest = hashlib.sha256(
        TENANT_CAPABILITY_RFC8410_PREFIX + RFC8032_TEST_PUBLIC_KEY
    ).digest()
    with pytest.raises(TenantCapabilityContractError, match="contract digest"):
        canonical_tenant_capability_payload(
            replace(capability, contract_digest=der_digest)
        )
