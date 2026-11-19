"""Compare original ingress sources with independently established bindings."""
from __future__ import annotations

from hashlib import sha256

from ._pending_claim_schemas import validate_document
from .runtime_bundle import RuntimeBundleError, strict_json_document


def _original_document(raw: bytes, expected_sha256: str, kind: str) -> dict:
    if type(raw) is not bytes or type(expected_sha256) is not str:
        raise ValueError("original ingress bytes and their SHA-256 are required")
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("original ingress byte digest differs")
    try:
        document, _ = strict_json_document(raw, kind)
    except (RuntimeBundleError, RecursionError):
        raise ValueError("invalid original ingress JSON") from None
    validate_document(kind, document)
    return document


def verify_original_ingress_sources(
    request_bytes: bytes,
    envelope_bytes: bytes,
    *,
    request_bytes_sha256: str,
    envelope_bytes_sha256: str,
    batch_request_id: str,
    admitted_idempotency_key: str,
    classified_family: str,
) -> str:
    """Return the matching event ID. Event Ingress owns the classification."""
    request = _original_document(
        request_bytes, request_bytes_sha256, "ofarm.commitingressrequest.v0.1"
    )
    envelope = _original_document(
        envelope_bytes, envelope_bytes_sha256, "ofarm.semanticeventenvelope.v0.1"
    )
    if any(type(value) is not str for value in (
        batch_request_id, admitted_idempotency_key, classified_family,
    )):
        raise ValueError("expected ingress bindings must be strings")
    if request["requestId"] != batch_request_id:
        raise ValueError("ingress request differs from the batch request")
    if request["idempotencyKey"] != admitted_idempotency_key:
        raise ValueError("ingress key differs from the admitted request key")
    if request["commitClass"] != "OPERATION_CLAIM":
        raise ValueError("ingress request must be an operation claim")
    if request["semanticEventRef"] != envelope["semanticEventId"]:
        raise ValueError("ingress request names a different event")
    if envelope["primaryEventFamily"] != classified_family:
        raise ValueError("event family differs from its classification")
    return envelope["semanticEventId"]
