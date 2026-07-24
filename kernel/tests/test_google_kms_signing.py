"""Raw KMS response and TenantCapability construction regressions."""
from __future__ import annotations

from dataclasses import replace
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
    RESOURCE,
    principal_authority,
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
        created_at_us=NOW_US - 1_000_000,
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
        challenge.created_at_us + 60_000_000
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
    issuer = TenantCapabilityIssuer(
        _Reader(signing),
        GoogleKmsSigner(_KmsClient()),
        kid=KID,
    )

    with pytest.raises(CapabilityMintError):
        issuer.mint(
            IDENTITY,
            principal_authority(),
            TenantChallenge(uuid4(), AUDIENCE, NOW_US),
        )
