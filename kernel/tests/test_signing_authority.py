"""Signed-observer receipt and database composition regressions."""
from __future__ import annotations

import base64
import json

import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from kernel.signing_authority import (
    SigningAuthorityReader,
    SigningAuthorityUnavailable,
)
from kernel.signing_receipt import (
    SIGNING_EVIDENCE_MAX_BYTES,
    SigningEvidenceError,
    SigningEvidenceVerifier,
)
from kernel.tests._signing_support import (
    AUDIENCE,
    DIGEST_C,
    KID,
    NOW_US,
    OBSERVER_PRIVATE_KEY,
    Connection,
    Factory,
    authority_database_row,
    authority_row,
    raw_public_key,
    receipt_payload,
    signed_receipt,
    signing_authority,
)


def _verifier() -> SigningEvidenceVerifier:
    return SigningEvidenceVerifier(raw_public_key(OBSERVER_PRIVATE_KEY))


def test_signed_receipt_is_canonical_and_fresh():
    authority = signing_authority()
    receipt = _verifier().verify(
        signed_receipt(receipt_payload(authority)),
        now_us=NOW_US,
    )

    assert receipt.audience == AUDIENCE
    assert receipt.kid == KID
    assert receipt.lifecycle_head_id == authority.lifecycle_head_id
    assert receipt.kms_evidence_digest == authority.kms_evidence_digest


@pytest.mark.parametrize(
    "receipt",
    [
        b'{"payload":"eA","payload":"eA","signature":"eA"}',
        b"x" * (SIGNING_EVIDENCE_MAX_BYTES + 1),
    ],
)
def test_duplicate_or_oversized_receipt_is_refused(receipt):
    with pytest.raises(SigningEvidenceError):
        _verifier().verify(receipt, now_us=NOW_US)


def test_receipt_signed_by_another_observer_is_refused():
    authority = signing_authority()
    receipt = signed_receipt(
        receipt_payload(authority),
        private_key=Ed25519PrivateKey.generate(),
    )

    with pytest.raises(SigningEvidenceError):
        _verifier().verify(receipt, now_us=NOW_US)


def test_stale_receipt_is_refused():
    authority = signing_authority()
    payload = receipt_payload(
        authority,
        observedAtUnixMicroseconds=NOW_US - 20_000_000,
        expiresAtUnixMicroseconds=NOW_US,
    )

    with pytest.raises(SigningEvidenceError):
        _verifier().verify(signed_receipt(payload), now_us=NOW_US)


def test_signed_but_noncanonical_payload_is_refused():
    authority = signing_authority()
    payload = receipt_payload(authority)
    payload_bytes = json.dumps(payload, separators=(", ", ": ")).encode()
    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    envelope = json.dumps(
        {
            "payload": encode(payload_bytes),
            "signature": encode(OBSERVER_PRIVATE_KEY.sign(payload_bytes)),
        },
        separators=(",", ":"),
    ).encode()

    with pytest.raises(SigningEvidenceError):
        _verifier().verify(envelope, now_us=NOW_US)


def test_reader_composes_one_database_row_and_matching_receipt():
    authority = signing_authority()
    connection = Connection([[authority_database_row(authority)]])
    reader = SigningAuthorityReader(
        Factory(connection),
        lambda: signed_receipt(receipt_payload(authority)),
        _verifier(),
    )

    result = reader.current(KID)

    assert result == authority
    statement, parameters = connection.executions[0]
    assert statement.startswith("SELECT binder_instance_id, audience, ")
    assert statement.endswith(" FROM ofarm.observe_signing_authority(%s)")
    assert parameters == (KID,)


@pytest.mark.parametrize(
    ("member", "value"),
    [
        ("audience", AUDIENCE.replace("a58b", "b58b")),
        ("candidateDigest", DIGEST_C),
        ("kmsEvidenceDigest", DIGEST_C),
        ("iamEvidenceDigest", DIGEST_C),
        ("lifecycleHeadDigest", "sha256:" + "d" * 64),
    ],
)
def test_fresh_but_conflicting_receipt_is_refused(member, value):
    authority = signing_authority()
    payload = receipt_payload(authority, **{member: value})
    reader = SigningAuthorityReader(
        Factory(Connection([[authority_database_row(authority)]])),
        lambda: signed_receipt(payload),
        _verifier(),
    )

    with pytest.raises(SigningAuthorityUnavailable):
        reader.current(KID)


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [authority_row(), authority_row()],
        [authority_row(admission_state="CLOSED")],
        [authority_row(public_key_digest="sha256:" + "0" * 64)],
        [authority_row(issuance_end_us=NOW_US)],
    ],
)
def test_database_authority_absence_or_malformed_shape_is_closed(rows):
    authority = signing_authority()
    reader = SigningAuthorityReader(
        Factory(Connection([rows])),
        lambda: signed_receipt(receipt_payload(authority)),
        _verifier(),
    )

    with pytest.raises(SigningAuthorityUnavailable):
        reader.current(KID)


def test_database_authority_failure_is_closed():
    authority = signing_authority()
    connection = Connection(
        [],
        fail_at=1,
        failure=psycopg.OperationalError("database unavailable"),
    )
    reader = SigningAuthorityReader(
        Factory(connection),
        lambda: signed_receipt(receipt_payload(authority)),
        _verifier(),
    )

    with pytest.raises(SigningAuthorityUnavailable):
        reader.current(KID)
