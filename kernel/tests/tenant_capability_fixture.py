"""Test-only RFC 8032 reference signer for the #174 golden vectors.

This module lives under ``kernel/tests`` so production packaging cannot import
or ship it accidentally.  The fixed seed is RFC 8032 test-vector material, not
a production or production-like credential.
"""

from __future__ import annotations

import hashlib

from deployment.postgresql.tenant_contract import (
    TenantCapability,
    canonical_jws_signing_input,
    serialize_tenant_capability_jws,
)


RFC8032_TEST_SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc4"
    "4449c5697b326919703bac031cae7f60"
)
RFC8032_TEST_PUBLIC_KEY = bytes.fromhex(
    "d75a980182b10ab7d54bfed3c964073a"
    "0ee172f3daa62325af021a68f707511a"
)

_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = x * _I % _Q
    if x & 1:
        x = _Q - x
    return x


_BY = 4 * pow(5, _Q - 2, _Q) % _Q
_B = (_xrecover(_BY), _BY)


def _point_add(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = left
    x2, y2 = right
    denominator_x = pow(1 + _D * x1 * x2 * y1 * y2, _Q - 2, _Q)
    denominator_y = pow(1 - _D * x1 * x2 * y1 * y2, _Q - 2, _Q)
    return (
        (x1 * y2 + x2 * y1) * denominator_x % _Q,
        (y1 * y2 + x1 * x2) * denominator_y % _Q,
    )


def _scalar_mult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = (0, 1)
    addend = point
    while scalar:
        if scalar & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        scalar >>= 1
    return result


def _encode_point(point: tuple[int, int]) -> bytes:
    x, y = point
    encoded = y | ((x & 1) << 255)
    return encoded.to_bytes(32, "little")


def _clamped_scalar(seed: bytes) -> tuple[int, bytes]:
    digest = hashlib.sha512(seed).digest()
    scalar_bytes = bytearray(digest[:32])
    scalar_bytes[0] &= 248
    scalar_bytes[31] &= 63
    scalar_bytes[31] |= 64
    return int.from_bytes(scalar_bytes, "little"), digest[32:]


def public_key_from_seed(seed: bytes) -> bytes:
    if type(seed) is not bytes or len(seed) != 32:
        raise ValueError("test Ed25519 seed must be exactly 32 bytes")
    scalar, _ = _clamped_scalar(seed)
    return _encode_point(_scalar_mult(_B, scalar))


def sign(seed: bytes, message: bytes) -> bytes:
    """Return a deterministic PureEd25519 signature for test evidence only."""

    if type(message) is not bytes:
        raise ValueError("test Ed25519 message must be bytes")
    scalar, prefix = _clamped_scalar(seed)
    public_key = public_key_from_seed(seed)
    nonce = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % _L
    encoded_r = _encode_point(_scalar_mult(_B, nonce))
    challenge = int.from_bytes(
        hashlib.sha512(encoded_r + public_key + message).digest(), "little"
    ) % _L
    signature_scalar = (nonce + challenge * scalar) % _L
    return encoded_r + signature_scalar.to_bytes(32, "little")


def sign_capability(
    capability: TenantCapability, *, seed: bytes = RFC8032_TEST_SEED
) -> str:
    signature = sign(seed, canonical_jws_signing_input(capability))
    return serialize_tenant_capability_jws(capability, signature)


assert public_key_from_seed(RFC8032_TEST_SEED) == RFC8032_TEST_PUBLIC_KEY
