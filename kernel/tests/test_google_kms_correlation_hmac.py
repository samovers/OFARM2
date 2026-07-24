"""Google KMS correlation-HMAC custody regressions."""

from __future__ import annotations

import inspect
from unittest.mock import patch

import pytest
from google.api_core import exceptions as google_exceptions
from google.cloud import kms_v1

from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT
from deployment.postgresql.tenant_contract import crc32c
from kernel.google_kms_correlation_hmac import (
    CorrelationHmacUnavailable,
    GoogleKmsCorrelationHmac,
)


POLICY = SECURITY_AUDIT_CONTRACT.correlation_hmac
RESOURCE = (
    "projects/example/locations/europe-west1/keyRings/ofarm/"
    "cryptoKeys/pretenant-correlation/cryptoKeyVersions/2"
)
PREFLIGHT = b"\x00OFARM_PRETENANT_CORRELATION_HMAC_PREFLIGHT_V1\x00"
RANDOM = b"r" * 32
MAC = b"m" * 32


class _KmsClient:
    def __init__(
        self,
        *,
        version_changes=None,
        mac_changes=None,
        version_error=None,
        mac_error=None,
    ):
        self.version_changes = version_changes or {}
        self.mac_changes = mac_changes or {}
        self.version_error = version_error
        self.mac_error = mac_error
        self.version_calls = []
        self.mac_calls = []

    def get_crypto_key_version(self, *, request, retry, timeout):
        self.version_calls.append((request, retry, timeout))
        if self.version_error is not None:
            raise self.version_error
        values = {
            "name": RESOURCE,
            "state": (kms_v1.CryptoKeyVersion.CryptoKeyVersionState.ENABLED),
            "algorithm": (
                kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm.HMAC_SHA256
            ),
            "protection_level": kms_v1.ProtectionLevel.HSM,
            **self.version_changes,
        }
        return kms_v1.CryptoKeyVersion(**values)

    def mac_sign(self, *, request, retry, timeout):
        self.mac_calls.append((request, retry, timeout))
        if self.mac_error is not None:
            raise self.mac_error
        values = {
            "name": RESOURCE,
            "mac": MAC,
            "mac_crc32c": crc32c(MAC),
            "verified_data_crc32c": True,
            "protection_level": kms_v1.ProtectionLevel.HSM,
            **self.mac_changes,
        }
        return kms_v1.MacSignResponse(**values)


def _ready(client=None, *, timeout=5):
    client = client or _KmsClient()
    generator = GoogleKmsCorrelationHmac(
        client,
        RESOURCE,
        rpc_timeout_seconds=timeout,
    )
    generator.initialize()
    return generator, client


def test_component_pins_the_exact_v2_policy():
    assert POLICY.algorithm == "HMAC-SHA-256"
    assert POLICY.length_bytes == 32
    assert POLICY.domain == "OFARM_PRETENANT_CORRELATION_V1"
    assert POLICY.key_version == 2


@pytest.mark.parametrize(
    "resource",
    [
        RESOURCE.replace("/2", "/1"),
        RESOURCE.rsplit("/", 1)[0],
        RESOURCE.replace("projects/example", "projects/EXAMPLE"),
        RESOURCE + "/extra",
        7,
    ],
)
def test_constructor_refuses_non_v2_or_malformed_resource(resource):
    with pytest.raises(CorrelationHmacUnavailable):
        GoogleKmsCorrelationHmac(_KmsClient(), resource)


@pytest.mark.parametrize(
    "timeout",
    [True, 0, -1, 31, "5"],
)
def test_constructor_refuses_invalid_timeout(timeout):
    with pytest.raises(CorrelationHmacUnavailable):
        GoogleKmsCorrelationHmac(
            _KmsClient(),
            RESOURCE,
            rpc_timeout_seconds=timeout,
        )


def test_initialize_checks_exact_version_and_preflights_once():
    generator, client = _ready(timeout=4)

    assert generator is not None
    version_request, retry, timeout = client.version_calls[0]
    assert version_request.name == RESOURCE
    assert retry is None
    assert timeout == 4
    mac_request, retry, timeout = client.mac_calls[0]
    assert mac_request.name == RESOURCE
    assert mac_request.data == PREFLIGHT
    assert mac_request.data_crc32c == crc32c(PREFLIGHT)
    assert retry is None
    assert timeout == 4

    generator.initialize()
    assert len(client.version_calls) == 1
    assert len(client.mac_calls) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"name": RESOURCE.replace("/2", "/3")},
        {"state": (kms_v1.CryptoKeyVersion.CryptoKeyVersionState.DISABLED)},
        {"algorithm": (kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm.HMAC_SHA512)},
        {"protection_level": kms_v1.ProtectionLevel.SOFTWARE},
    ],
)
def test_initialize_refuses_wrong_key_version_posture(changes):
    client = _KmsClient(version_changes=changes)
    generator = GoogleKmsCorrelationHmac(client, RESOURCE)

    with pytest.raises(CorrelationHmacUnavailable):
        generator.initialize()
    with pytest.raises(CorrelationHmacUnavailable):
        generator.create()

    assert client.mac_calls == []


@pytest.mark.parametrize(
    "changes",
    [
        {"name": RESOURCE.replace("/2", "/3")},
        {"verified_data_crc32c": False},
        {"protection_level": kms_v1.ProtectionLevel.SOFTWARE},
        {"mac": b"x" * 31},
        {"mac_crc32c": 0},
    ],
)
def test_initialize_refuses_preflight_response_substitution(changes):
    client = _KmsClient(mac_changes=changes)
    generator = GoogleKmsCorrelationHmac(client, RESOURCE)

    with pytest.raises(CorrelationHmacUnavailable):
        generator.initialize()

    assert len(client.mac_calls) == 1


def test_create_has_no_caller_data_and_uses_exact_framing():
    generator, client = _ready()

    assert tuple(inspect.signature(generator.create).parameters) == ()
    with patch(
        "kernel.google_kms_correlation_hmac.secrets.token_bytes",
        return_value=RANDOM,
    ) as entropy:
        result = generator.create()

    request, retry, timeout = client.mac_calls[1]
    expected = POLICY.domain.encode("ascii") + b"\x00" + RANDOM
    assert request.name == RESOURCE
    assert request.data == expected
    assert request.data_crc32c == crc32c(expected)
    assert retry is None
    assert timeout == 5
    assert result.value == MAC
    assert result.key_version == POLICY.key_version
    assert repr(MAC) not in repr(result)
    entropy.assert_called_once_with(32)


def test_each_create_samples_fresh_entropy_and_makes_one_kms_call():
    generator, client = _ready()
    samples = [b"a" * 32, b"b" * 32]

    with patch(
        "kernel.google_kms_correlation_hmac.secrets.token_bytes",
        side_effect=samples,
    ):
        generator.create()
        generator.create()

    assert len(client.mac_calls) == 3
    assert client.mac_calls[1][0].data.endswith(b"a" * 32)
    assert client.mac_calls[2][0].data.endswith(b"b" * 32)


@pytest.mark.parametrize("value", [b"short", bytearray(b"x" * 32)])
def test_invalid_entropy_refuses_before_kms(value):
    generator, client = _ready()

    with (
        patch(
            "kernel.google_kms_correlation_hmac.secrets.token_bytes",
            return_value=value,
        ),
        pytest.raises(CorrelationHmacUnavailable),
    ):
        generator.create()

    assert len(client.mac_calls) == 1


def test_create_before_initialize_performs_no_work():
    client = _KmsClient()
    generator = GoogleKmsCorrelationHmac(client, RESOURCE)

    with (
        patch(
            "kernel.google_kms_correlation_hmac.secrets.token_bytes",
        ) as entropy,
        pytest.raises(CorrelationHmacUnavailable),
    ):
        generator.create()

    entropy.assert_not_called()
    assert client.version_calls == []
    assert client.mac_calls == []


def test_kms_unavailability_is_closed_without_retry():
    client = _KmsClient(
        version_error=google_exceptions.ServiceUnavailable("down"),
    )
    generator = GoogleKmsCorrelationHmac(client, RESOURCE)

    with pytest.raises(CorrelationHmacUnavailable) as raised:
        generator.initialize()

    assert str(raised.value) == "correlation HMAC is unavailable"
    assert len(client.version_calls) == 1
    assert client.mac_calls == []


def test_raw_correlation_is_absent_from_public_failure_traceback():
    generator, client = _ready()
    client.mac_error = google_exceptions.ServiceUnavailable("down")
    canary = b"RAW-CORRELATION-CANARY-123456789"
    assert len(canary) == 32

    with (
        patch(
            "kernel.google_kms_correlation_hmac.secrets.token_bytes",
            return_value=canary,
        ),
        pytest.raises(CorrelationHmacUnavailable) as raised,
    ):
        generator.create()

    assert len(client.mac_calls) == 2
    assert canary not in str(raised.value).encode()
    traceback = raised.value.__traceback__
    while traceback is not None:
        frame = traceback.tb_frame
        if frame.f_code.co_filename.endswith("/kernel/google_kms_correlation_hmac.py"):
            assert all(
                canary not in repr(value).encode() for value in frame.f_locals.values()
            )
        traceback = traceback.tb_next
