"""Google Cloud KMS custody for pre-tenant correlation HMACs."""

from __future__ import annotations

import re
import secrets
from typing import Protocol

from google.api_core import exceptions as google_exceptions
from google.cloud import kms_v1

from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT

from .security_audit import CorrelationHmac, SecurityAuditError


_POLICY = SECURITY_AUDIT_CONTRACT.correlation_hmac
_POLICY_SUPPORTED = (
    _POLICY.algorithm == "HMAC-SHA-256"
    and _POLICY.length_bytes == 32
    and _POLICY.domain == "OFARM_PRETENANT_CORRELATION_V1"
    and _POLICY.key_version == 2
)
_ENTROPY_BYTES = 32
_PREIMAGE_PREFIX = _POLICY.domain.encode("ascii") + b"\x00"
_PREFLIGHT = b"\x00OFARM_PRETENANT_CORRELATION_HMAC_PREFLIGHT_V1\x00"
_RESOURCE = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/"
    r"locations/[a-z0-9](?:[a-z0-9-]*[a-z0-9])?/"
    r"keyRings/[A-Za-z0-9_-]{1,63}/"
    r"cryptoKeys/[A-Za-z0-9_-]{1,63}/"
    r"cryptoKeyVersions/([1-9][0-9]*)$"
)


class KmsCorrelationClient(Protocol):
    def get_crypto_key_version(
        self,
        *,
        request: kms_v1.GetCryptoKeyVersionRequest,
        retry: None,
        timeout: float,
    ) -> kms_v1.CryptoKeyVersion: ...

    def mac_sign(
        self,
        *,
        request: kms_v1.MacSignRequest,
        retry: None,
        timeout: float,
    ) -> kms_v1.MacSignResponse: ...


class CorrelationHmacUnavailable(SecurityAuditError):
    def __init__(self) -> None:
        super().__init__("correlation HMAC is unavailable")


def _crc32c(value: bytes) -> int:
    checksum = 0xFFFFFFFF
    for octet in value:
        checksum ^= octet
        for _ in range(8):
            checksum = (checksum >> 1) ^ (0x82F63B78 if checksum & 1 else 0)
    return checksum ^ 0xFFFFFFFF


def _observe_version(
    client: KmsCorrelationClient,
    resource: str,
    timeout: float,
) -> kms_v1.CryptoKeyVersion | None:
    try:
        return client.get_crypto_key_version(
            request=kms_v1.GetCryptoKeyVersionRequest(name=resource),
            retry=None,
            timeout=timeout,
        )
    except (
        google_exceptions.GoogleAPICallError,
        google_exceptions.RetryError,
        TimeoutError,
    ):
        return None


def _mac(
    client: KmsCorrelationClient,
    resource: str,
    data: bytes,
    timeout: float,
) -> bytes | None:
    request = kms_v1.MacSignRequest(
        name=resource,
        data=data,
        data_crc32c=_crc32c(data),
    )
    try:
        response = client.mac_sign(
            request=request,
            retry=None,
            timeout=timeout,
        )
    except (
        google_exceptions.GoogleAPICallError,
        google_exceptions.RetryError,
        TimeoutError,
    ):
        return None
    mac = response.mac
    if (
        response.name != resource
        or response.protection_level != kms_v1.ProtectionLevel.HSM
        or response.verified_data_crc32c is not True
        or type(mac) is not bytes
        or len(mac) != _POLICY.length_bytes
        or response.mac_crc32c != _crc32c(mac)
    ):
        return None
    return mac


class GoogleKmsCorrelationHmac:
    def __init__(
        self,
        client: KmsCorrelationClient,
        key_version_resource: str,
        *,
        rpc_timeout_seconds: float = 5,
    ) -> None:
        match = (
            _RESOURCE.fullmatch(key_version_resource)
            if type(key_version_resource) is str
            else None
        )
        if (
            not _POLICY_SUPPORTED
            or match is None
            or int(match.group(1)) != _POLICY.key_version
            or type(rpc_timeout_seconds) not in (int, float)
            or isinstance(rpc_timeout_seconds, bool)
            or not 0 < rpc_timeout_seconds <= 30
        ):
            raise CorrelationHmacUnavailable()
        self._client = client
        self._resource = key_version_resource
        self._timeout = float(rpc_timeout_seconds)
        self._ready = False

    def initialize(self) -> None:
        if self._ready:
            return
        version = _observe_version(
            self._client,
            self._resource,
            self._timeout,
        )
        if (
            version is None
            or version.name != self._resource
            or version.state != kms_v1.CryptoKeyVersion.CryptoKeyVersionState.ENABLED
            or version.algorithm
            != kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm.HMAC_SHA256
            or version.protection_level != kms_v1.ProtectionLevel.HSM
            or _mac(
                self._client,
                self._resource,
                _PREFLIGHT,
                self._timeout,
            )
            is None
        ):
            raise CorrelationHmacUnavailable()
        self._ready = True

    def create(self) -> CorrelationHmac:
        if not self._ready:
            raise CorrelationHmacUnavailable()
        try:
            random_value = secrets.token_bytes(_ENTROPY_BYTES)
        except OSError:
            raise CorrelationHmacUnavailable() from None
        if type(random_value) is not bytes or len(random_value) != _ENTROPY_BYTES:
            random_value = b""
            raise CorrelationHmacUnavailable()
        mac = _mac(
            self._client,
            self._resource,
            _PREIMAGE_PREFIX + random_value,
            self._timeout,
        )
        random_value = b""
        if mac is None:
            raise CorrelationHmacUnavailable()
        return CorrelationHmac(mac, _POLICY.key_version)
