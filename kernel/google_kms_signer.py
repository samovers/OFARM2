"""Stateless Google Cloud KMS Ed25519 raw-data signing."""
from __future__ import annotations

from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from google.api_core import exceptions as google_exceptions
from google.cloud import kms_v1

from deployment.postgresql.tenant_contract import crc32c

from .signing_authority import SigningAuthority


class KmsSigningClient(Protocol):
    def asymmetric_sign(
        self,
        *,
        request: kms_v1.AsymmetricSignRequest,
        retry: None,
        timeout: float,
    ) -> kms_v1.AsymmetricSignResponse: ...


class KmsSigningError(RuntimeError):
    pass


class GoogleKmsSigner:
    def __init__(
        self,
        client: KmsSigningClient,
        *,
        rpc_timeout_seconds: float = 5,
    ) -> None:
        if (
            type(rpc_timeout_seconds) not in (int, float)
            or isinstance(rpc_timeout_seconds, bool)
            or not 0 < rpc_timeout_seconds <= 30
        ):
            raise KmsSigningError("KMS RPC timeout is invalid")
        self._client = client
        self._rpc_timeout_seconds = float(rpc_timeout_seconds)

    def sign(
        self,
        data: bytes,
        signing_authority: SigningAuthority,
    ) -> bytes:
        if type(data) is not bytes or not 1 <= len(data) <= 16_384:
            raise KmsSigningError("KMS signing data is invalid")
        request = kms_v1.AsymmetricSignRequest(
            name=signing_authority.kms_key_version_resource,
            data=data,
            data_crc32c=crc32c(data),
        )
        try:
            response = self._client.asymmetric_sign(
                request=request,
                retry=None,
                timeout=self._rpc_timeout_seconds,
            )
        except (
            google_exceptions.GoogleAPICallError,
            google_exceptions.RetryError,
            TimeoutError,
        ) as exc:
            raise KmsSigningError("KMS signing is unavailable") from exc
        signature = response.signature
        if (
            response.name != signing_authority.kms_key_version_resource
            or response.protection_level != kms_v1.ProtectionLevel.HSM
            or response.verified_data_crc32c is not True
            or response.verified_digest_crc32c is not False
            or type(signature) is not bytes
            or len(signature) != 64
            or response.signature_crc32c != crc32c(signature)
        ):
            raise KmsSigningError("KMS signing response differs")
        try:
            Ed25519PublicKey.from_public_bytes(
                signing_authority.public_key
            ).verify(signature, data)
        except (InvalidSignature, ValueError) as exc:
            raise KmsSigningError(
                "KMS signature does not verify independently"
            ) from exc
        return signature
