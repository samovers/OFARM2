"""Real signing adapters with explicitly simulated external KMS and observer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import psycopg
from google.cloud import kms_v1
from psycopg.conninfo import make_conninfo

from deployment.postgresql.tenant_contract import crc32c
from kernel.google_kms_signer import GoogleKmsSigner
from kernel.signing_authority import SigningAuthority, SigningAuthorityReader
from kernel.signing_receipt import SigningEvidenceVerifier
from kernel.signing_authority_io import prepare_signing_conninfo
from kernel.tenant_capability_issuer import TenantCapabilityIssuer
from kernel.tests._signing_support import (
    OBSERVER_PRIVATE_KEY,
    connected_test_dsn,
    raw_public_key,
    receipt_payload,
    signed_receipt,
)
from kernel.tests.tenant_capability_fixture import RFC8032_TEST_SEED, sign
from kernel.tests.test_postgresql_tenant_migration import TenantTarget


class FixtureKmsClient:
    """No cloud call or HSM claim: sign only with the public RFC test seed."""

    def __init__(self, resource: str, seed: bytes) -> None:
        self.resource = resource
        self.seed = seed
        self.calls: list[bytes] = []

    def asymmetric_sign(self, *, request, retry, timeout):
        assert request.name == self.resource
        assert request.data_crc32c == crc32c(request.data)
        assert retry is None
        assert 0 < timeout <= 30
        self.calls.append(request.data)
        signature = sign(self.seed, request.data)
        return kms_v1.AsymmetricSignResponse(
            name=self.resource,
            signature=signature,
            signature_crc32c=crc32c(signature),
            verified_data_crc32c=True,
            verified_digest_crc32c=False,
            protection_level=kms_v1.ProtectionLevel.HSM,
        )


@dataclass(frozen=True)
class LiveSigning:
    issuer: TenantCapabilityIssuer
    reader: SigningAuthorityReader
    client: FixtureKmsClient


def live_signing(
    target: TenantTarget, kid: str, receipt_directory: Path, *, seed: bytes = RFC8032_TEST_SEED
) -> LiveSigning:
    """Fresh signed fixture receipt; production reader still rereads authority."""
    app_dsn = target.role_dsn("ofarm_app")
    with psycopg.connect(app_dsn) as connection:
        app_dsn = connected_test_dsn(app_dsn, connection)
        row = connection.execute(
            "SELECT * FROM ofarm.observe_signing_authority(%s)", (kid,)
        ).fetchone()
    assert row is not None
    observed = SigningAuthority.from_database_row(row, kid)
    receipt = signed_receipt(receipt_payload(
        observed,
        observedAtUnixMicroseconds=observed.observed_at_us,
        expiresAtUnixMicroseconds=observed.observed_at_us + 30_000_000,
    ))
    receipt_path = receipt_directory / f"{kid}.json"
    receipt_path.write_bytes(receipt)
    conninfo = prepare_signing_conninfo(make_conninfo(
        app_dsn, sslcertmode="disable", gssencmode="disable",
    ))
    reader = SigningAuthorityReader(
        conninfo,
        receipt_path,
        SigningEvidenceVerifier(raw_public_key(OBSERVER_PRIVATE_KEY)),
    )
    client = FixtureKmsClient(observed.kms_key_version_resource, seed)
    return LiveSigning(
        TenantCapabilityIssuer(reader, GoogleKmsSigner(client), kid=kid),
        reader,
        client,
    )
