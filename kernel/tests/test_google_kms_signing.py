"""Raw KMS response and TenantCapability construction regressions."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import pytest
from google.cloud import kms_v1

from deployment.postgresql.tenant_contract import (
    crc32c,
    decode_tenant_capability_jws,
)
from kernel.google_kms_signer import (
    GoogleKmsSigner,
    KmsSigningError,
)
from kernel.signing_authority import SigningAuthorityReader
from kernel.signing_receipt import SigningEvidenceVerifier
from kernel.tenant_capability_issuer import (
    CapabilityMintError,
    TenantCapabilityIssuer,
    TenantChallenge,
)
from kernel.tests._signing_support import (
    AUDIENCE,
    IDENTITY,
    KID,
    KMS_PRIVATE_KEY,
    NOW_US,
    OBSERVER_PRIVATE_KEY,
    RESOURCE,
    Connection,
    Factory,
    authority_database_row,
    principal_authority,
    raw_public_key,
    receipt_payload,
    signed_receipt,
    signing_authority,
)


class _KmsClient:
    def __init__(self, **changes):
        self.changes = changes
        self.calls = []

    def asymmetric_sign(self, *, request, retry, timeout):
        self.calls.append((request, retry, timeout))
        signature = self.changes.get(
            "signature",
            KMS_PRIVATE_KEY.sign(request.data),
        )
        values = {
            "name": RESOURCE,
            "signature": signature,
            "signature_crc32c": crc32c(signature),
            "verified_data_crc32c": True,
            "verified_digest_crc32c": False,
            "protection_level": kms_v1.ProtectionLevel.HSM,
            **self.changes,
        }
        return kms_v1.AsymmetricSignResponse(**values)


def test_kms_signer_uses_raw_data_crc_no_retry_and_bounded_timeout():
    authority = signing_authority()
    client = _KmsClient()
    signer = GoogleKmsSigner(client, rpc_timeout_seconds=4)
    data = b"exact-jws-signing-input"

    signature = signer.sign(data, authority)

    assert signature == KMS_PRIVATE_KEY.sign(data)
    request, retry, timeout = client.calls[0]
    assert request.name == RESOURCE
    assert request.data == data
    assert request.data_crc32c == crc32c(data)
    assert not request.digest.sha256
    assert retry is None
    assert timeout == 4


@pytest.mark.parametrize(
    "changes",
    [
        {"name": RESOURCE.replace("/1", "/2")},
        {"protection_level": kms_v1.ProtectionLevel.SOFTWARE},
        {"verified_data_crc32c": False},
        {"verified_digest_crc32c": True},
        {"signature_crc32c": 0},
        {"signature": b"x" * 64},
    ],
)
def test_kms_response_substitution_is_refused(changes):
    with pytest.raises(KmsSigningError):
        GoogleKmsSigner(_KmsClient(**changes)).sign(
            b"exact-jws-signing-input",
            signing_authority(),
        )


class _Reader:
    def __init__(self, authority):
        self.authority = authority
        self.calls = []

    def current(self, kid):
        self.calls.append(kid)
        return self.authority


def test_issuer_builds_the_frozen_capability_and_reads_each_mint():
    signing = signing_authority()
    reader = _Reader(signing)
    client = _KmsClient()
    nonces = [uuid4(), uuid4()]
    first_nonce = nonces[0]
    issuer = TenantCapabilityIssuer(
        reader,
        GoogleKmsSigner(client),
        kid=KID,
        nonce_factory=lambda: nonces.pop(0),
    )
    authority = principal_authority()
    challenge = TenantChallenge(
        challenge_id=uuid4(),
        audience=AUDIENCE,
        created_at_us=NOW_US,
    )

    first = issuer.mint(IDENTITY, authority, challenge)
    second = issuer.mint(IDENTITY, authority, challenge)
    decoded = decode_tenant_capability_jws(first)

    assert first != second
    assert reader.calls == [KID, KID]
    assert len(client.calls) == 2
    assert decoded.capability.challenge_id == challenge.challenge_id
    assert decoded.capability.audience == AUDIENCE
    assert decoded.capability.key_id == KID
    assert decoded.capability.issuer == IDENTITY.issuer
    assert decoded.capability.subject == IDENTITY.subject
    assert decoded.capability.binding_version_id == (
        authority.binding_version_id
    )
    assert decoded.capability.lifecycle_head_id == authority.lifecycle_head_id
    assert decoded.capability.tenant_id == authority.tenant_id
    assert len(nonces) == 0
    assert decoded.capability.nonce == first_nonce
    assert decoded.capability.issued_at_unix_microseconds == NOW_US
    assert decoded.capability.expires_at_unix_microseconds == (
        NOW_US + 60_000_000
    )


def test_issuer_refuses_cross_audience_challenge_before_kms():
    client = _KmsClient()
    issuer = TenantCapabilityIssuer(
        _Reader(signing_authority()),
        GoogleKmsSigner(client),
        kid=KID,
    )
    challenge = TenantChallenge(
        uuid4(),
        AUDIENCE.replace("a58b", "b58b"),
        NOW_US,
    )

    with pytest.raises(CapabilityMintError):
        issuer.mint(IDENTITY, principal_authority(), challenge)

    assert client.calls == []


def test_issuer_refuses_identity_authority_mismatch_without_reading_key():
    reader = _Reader(signing_authority())
    issuer = TenantCapabilityIssuer(
        reader,
        GoogleKmsSigner(_KmsClient()),
        kid=KID,
    )
    authority = replace(principal_authority(), subject="subject:Other")
    challenge = TenantChallenge(uuid4(), AUDIENCE, NOW_US)

    with pytest.raises(CapabilityMintError):
        issuer.mint(IDENTITY, authority, challenge)

    assert reader.calls == []


def test_issuer_refuses_when_database_issuance_window_is_exhausted():
    signing = replace(signing_authority(), issuance_end_us=NOW_US)
    connection = Connection([[authority_database_row(signing)]])
    reader = SigningAuthorityReader(
        Factory(connection), lambda: signed_receipt(receipt_payload(signing)),
        SigningEvidenceVerifier(raw_public_key(OBSERVER_PRIVATE_KEY)),
    )
    client = _KmsClient()
    issuer = TenantCapabilityIssuer(
        reader,
        GoogleKmsSigner(client),
        kid=KID,
    )

    with pytest.raises(CapabilityMintError):
        issuer.mint(
            IDENTITY,
            principal_authority(),
            TenantChallenge(uuid4(), AUDIENCE, NOW_US),
        )

    assert len(connection.executions) == 1
    assert client.calls == []


@pytest.mark.parametrize(
    ("created_offset", "key_end_offset", "expected_expiry_offset"),
    [
        pytest.param(0, 120_000_000, 60_000_000, id="created-equality"),
        pytest.param(-1, 120_000_000, 59_999_999, id="one-us-delay"),
        pytest.param(-1_000, 120_000_000, 59_999_000, id="one-ms-delay"),
        pytest.param(-1_000_000, 120_000_000, 59_000_000, id="one-second-delay"),
        pytest.param(-30_000_000, 120_000_000, 30_000_000, id="half-window"),
        pytest.param(-59_999_999, 120_000_000, 1, id="last-microsecond"),
        pytest.param(1, 120_000_000, 60_000_000, id="lifetime-bound-wins"),
        pytest.param(4_999_999, 120_000_000, 60_000_000, id="inside-backward-skew"),
        pytest.param(5_000_000, 120_000_000, 60_000_000, id="backward-skew-equality"),
        pytest.param(-1_000_000, 10_000_000, 10_000_000, id="key-end-wins"),
        pytest.param(-1, 1, 1, id="last-key-microsecond"),
        pytest.param(0, 60_000_000, 60_000_000, id="three-equal-bounds"),
    ],
)
def test_issuer_signed_times_obey_each_deadline(
    created_offset, key_end_offset, expected_expiry_offset,
):
    reader = _Reader(signing_authority(issuance_end_us=NOW_US + key_end_offset))
    client = _KmsClient()
    issuer = TenantCapabilityIssuer(reader, GoogleKmsSigner(client), kid=KID)
    challenge = TenantChallenge(uuid4(), AUDIENCE, NOW_US + created_offset)

    token = issuer.mint(IDENTITY, principal_authority(), challenge)
    capability = decode_tenant_capability_jws(token).capability

    assert capability.challenge_id == challenge.challenge_id
    assert capability.issued_at_unix_microseconds == NOW_US
    assert capability.not_before_unix_microseconds == NOW_US
    assert capability.expires_at_unix_microseconds == NOW_US + expected_expiry_offset
    assert reader.calls == [KID]
    assert len(client.calls) == 1
    assert client.calls[0][1] is None


@pytest.mark.parametrize(
    ("created_offset", "key_end_offset"),
    [
        pytest.param(-60_000_000, 120_000_000, id="challenge-expiry-equality"),
        pytest.param(-60_000_001, 120_000_000, id="challenge-expired"),
        pytest.param(5_000_001, 120_000_000, id="backward-skew-plus-one"),
        pytest.param(0, 0, id="key-expiry-equality"),
        pytest.param(0, -1, id="key-expired"),
    ],
)
def test_issuer_refuses_closed_time_windows_without_signing(
    created_offset, key_end_offset,
):
    # Deliberately injected observations exercise mint's validator, not live key admission.
    signing = replace(signing_authority(), issuance_end_us=NOW_US + key_end_offset)
    reader = _Reader(signing)
    client = _KmsClient()
    issuer = TenantCapabilityIssuer(reader, GoogleKmsSigner(client), kid=KID)

    with pytest.raises(CapabilityMintError):
        issuer.mint(
            IDENTITY, principal_authority(),
            TenantChallenge(uuid4(), AUDIENCE, NOW_US + created_offset),
        )

    assert reader.calls == [KID]
    assert client.calls == []


class _IntSubclass(int):
    pass


@pytest.mark.parametrize(
    "created",
    [
        pytest.param(None, id="none"),
        pytest.param(True, id="true"),
        pytest.param(False, id="false"),
        pytest.param(str(NOW_US), id="text"),
        pytest.param(float(NOW_US), id="float"),
        pytest.param(_IntSubclass(NOW_US), id="int-subclass"),
    ],
)
def test_issuer_requires_exact_integer_creation_before_key_read(created):
    reader = _Reader(signing_authority())
    client = _KmsClient()
    issuer = TenantCapabilityIssuer(reader, GoogleKmsSigner(client), kid=KID)

    with pytest.raises(CapabilityMintError):
        issuer.mint(
            IDENTITY, principal_authority(), TenantChallenge(uuid4(), AUDIENCE, created),
        )

    assert reader.calls == []
    assert client.calls == []


@pytest.mark.parametrize(
    ("created", "observed", "key_end"),
    [
        pytest.param(2**63, NOW_US, NOW_US + 1, id="above-int64-masked-by-key-end"),
        pytest.param(2**63 - 1, NOW_US, NOW_US + 1, id="maximum-masked-by-key-end"),
        pytest.param(-(2**63) - 1, NOW_US, NOW_US + 1, id="below-int64"),
        pytest.param(-(2**63), -(2**63), -(2**63) + 60_000_000, id="minimum"),
        pytest.param(
            -(2**63) + 4_999_999, -(2**63), -(2**63) + 60_000_000,
            id="challenge-subtract-skew-underflow",
        ),
        pytest.param(
            2**63 - 60_000_000, 2**63 - 60_000_000, 2**63 - 1,
            id="challenge-add-age-overflow-masked-by-key-end",
        ),
        pytest.param(
            2**63 - 60_000_001, 2**63 - 5_000_000, 2**63 - 1,
            id="database-add-skew-overflow",
        ),
    ],
)
def test_issuer_refuses_integer_extremes_even_when_minimum_masks_them(
    created, observed, key_end,
):
    signing = replace(
        signing_authority(), observed_at_us=observed, issuance_end_us=key_end,
    )
    reader = _Reader(signing)
    client = _KmsClient()
    issuer = TenantCapabilityIssuer(reader, GoogleKmsSigner(client), kid=KID)

    with pytest.raises(CapabilityMintError):
        issuer.mint(
            IDENTITY, principal_authority(), TenantChallenge(uuid4(), AUDIENCE, created),
        )

    assert reader.calls == [KID]
    assert client.calls == []


@pytest.mark.parametrize(
    ("created", "observed", "expected_expiry"),
    [
        pytest.param(
            -(2**63) + 5_000_000, -(2**63), -(2**63) + 60_000_000,
            id="minimum-safe-challenge",
        ),
        pytest.param(
            2**63 - 60_000_001, 2**63 - 60_000_001, 2**63 - 1,
            id="maximum-safe-challenge",
        ),
        pytest.param(
            2**63 - 60_000_001, 2**63 - 5_000_001, 2**63 - 1,
            id="maximum-safe-database-observation",
        ),
    ],
)
def test_issuer_accepts_safe_int64_edges(created, observed, expected_expiry):
    signing = replace(
        signing_authority(), observed_at_us=observed, issuance_end_us=expected_expiry,
    )
    client = _KmsClient()
    issuer = TenantCapabilityIssuer(_Reader(signing), GoogleKmsSigner(client), kid=KID)

    token = issuer.mint(
        IDENTITY, principal_authority(), TenantChallenge(uuid4(), AUDIENCE, created),
    )
    capability = decode_tenant_capability_jws(token).capability

    assert capability.issued_at_unix_microseconds == observed
    assert capability.not_before_unix_microseconds == observed
    assert capability.expires_at_unix_microseconds == expected_expiry
    assert len(client.calls) == 1


@pytest.mark.parametrize("field", ["challenge_id", "audience", "created_at_us"])
def test_challenge_fields_are_immutable(field):
    challenge = TenantChallenge(uuid4(), AUDIENCE, NOW_US)

    with pytest.raises(FrozenInstanceError):
        setattr(challenge, field, None)


def test_challenge_requires_creation_time_without_compatibility_default():
    with pytest.raises(TypeError):
        TenantChallenge(uuid4(), AUDIENCE)


def test_nonce_is_evaluated_once_before_invalid_authority_digest_refuses():
    nonces = []
    def nonce_factory():
        value = uuid4()
        nonces.append(value)
        return value

    reader = _Reader(signing_authority())
    client = _KmsClient()
    issuer = TenantCapabilityIssuer(
        reader, GoogleKmsSigner(client), kid=KID, nonce_factory=nonce_factory,
    )
    authority = replace(principal_authority(), binding_version_digest="invalid")

    with pytest.raises(CapabilityMintError):
        issuer.mint(IDENTITY, authority, TenantChallenge(uuid4(), AUDIENCE, NOW_US))

    assert len(nonces) == 1
    assert reader.calls == [KID]
    assert client.calls == []


def test_receipt_time_is_freshness_evidence_not_issuance_clock():
    signing = signing_authority()
    connection = Connection([[authority_database_row(signing)]] * 2)
    receipts = [
        signed_receipt(receipt_payload(
            signing, observedAtUnixMicroseconds=observed,
            expiresAtUnixMicroseconds=NOW_US + 1,
        ))
        for observed in (NOW_US, NOW_US - 59_999_999)
    ]
    reader = SigningAuthorityReader(
        Factory(connection), lambda: receipts.pop(0),
        SigningEvidenceVerifier(raw_public_key(OBSERVER_PRIVATE_KEY)),
    )
    client = _KmsClient()
    nonce = uuid4()
    issuer = TenantCapabilityIssuer(
        reader, GoogleKmsSigner(client), kid=KID, nonce_factory=lambda: nonce,
    )
    authority = principal_authority()
    challenge = TenantChallenge(uuid4(), AUDIENCE, NOW_US - 1_000_000)

    first = issuer.mint(IDENTITY, authority, challenge)
    second = issuer.mint(IDENTITY, authority, challenge)
    capability = decode_tenant_capability_jws(first).capability

    assert first == second
    assert capability.issued_at_unix_microseconds == NOW_US
    assert capability.not_before_unix_microseconds == NOW_US
    assert capability.expires_at_unix_microseconds == NOW_US + 59_000_000
    assert len(connection.executions) == 2
    assert all(parameters == (KID,) for _, parameters in connection.executions)
    assert receipts == []
    assert len(client.calls) == 2
    assert all(retry is None for _, retry, _ in client.calls)


@pytest.mark.parametrize(
    ("receipt_observed", "receipt_expires"),
    [
        pytest.param(NOW_US - 1, NOW_US, id="expiry-equality"),
        pytest.param(NOW_US + 1, NOW_US + 10_000_000, id="future-receipt"),
    ],
)
def test_issuer_refuses_invalid_receipt_freshness_before_kms(
    receipt_observed, receipt_expires,
):
    signing = signing_authority()
    connection = Connection([[authority_database_row(signing)]])
    receipt = signed_receipt(receipt_payload(
        signing, observedAtUnixMicroseconds=receipt_observed,
        expiresAtUnixMicroseconds=receipt_expires,
    ))
    reader = SigningAuthorityReader(
        Factory(connection), lambda: receipt,
        SigningEvidenceVerifier(raw_public_key(OBSERVER_PRIVATE_KEY)),
    )
    client = _KmsClient()
    issuer = TenantCapabilityIssuer(reader, GoogleKmsSigner(client), kid=KID)

    with pytest.raises(CapabilityMintError):
        issuer.mint(
            IDENTITY, principal_authority(), TenantChallenge(uuid4(), AUDIENCE, NOW_US),
        )

    assert len(connection.executions) == 1
    assert client.calls == []
