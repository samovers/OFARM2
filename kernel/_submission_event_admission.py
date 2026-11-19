"""Check retained source bindings inside the guarded claim adapter, before domain staging."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from typing import Never
from uuid import UUID

from .runtime_bundle import RuntimeBundleError, strict_json_document
from .tenant_claim_write_guard import ClaimWriteAttempt


@dataclass(frozen=True, slots=True)
class _ProofSelection:
    """Independent owner selection for a retained proof, prior to the claim transaction."""

    tenant_id: UUID
    producer_ref: str
    request_sha256: str
    intent_sha256: str
    event_kind: str
    event_ref: str
    event_revision: str | None
    envelope_sha256: str
    proof_ref: str
    profile_sha256: str
    context_sha256: str
    contract_sha256: str
    proof_digest: str
    event_digest: str | None = None


@dataclass(frozen=True, slots=True)
class _Submission:
    """Originals and authorized request fields independently selected by the coordinator."""

    attempt: ClaimWriteAttempt
    request_bytes: bytes
    request_id: str
    idempotency_key: str
    acting_party_ref: str | None
    acting_agent_ref: str | None
    target_scopes: tuple[tuple[str, str], ...]
    selection: _ProofSelection


@dataclass(frozen=True, slots=True)
class _RetainedProof:
    """Facts retrieved by the bound custodian, including its own immutable selection."""

    selection: _ProofSelection
    production_mode: str
    envelope_bytes: bytes
    proof_bytes: bytes
    context_bytes: bytes
    profile_bytes: bytes


def _check_depth(value: object, depth: int = 1) -> None:
    if isinstance(value, (dict, list)):
        if depth > 64:
            raise ValueError("event admission JSON nesting exceeds 64 levels")
        for child in value.values() if isinstance(value, dict) else value:
            _check_depth(child, depth + 1)


def _parse_original(raw: bytes, label: str) -> dict:
    try:
        document, _ = strict_json_document(raw, label)
    except (RuntimeBundleError, RecursionError) as exc:
        raise ValueError(f"invalid original {label}") from exc
    return document


def _document(raw: bytes, label: str) -> dict:
    if type(raw) is not bytes or len(raw) > 2 * 1024 * 1024:
        raise ValueError(f"invalid {label} bytes or size")
    document = _parse_original(raw, label)
    _check_depth(document)
    return document


def _pinned_document(raw: bytes, label: str, expected_sha256: str) -> dict:
    document = _document(raw, label)
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError(f"{label} bytes differ from the independent selection")
    return document


def _check_submission(submission: _Submission, attempt: ClaimWriteAttempt) -> None:
    if type(submission) is not _Submission or type(submission.selection) is not _ProofSelection:
        raise ValueError("missing independent submission or proof selection")
    selected = submission.selection
    if (
        type(attempt) is not ClaimWriteAttempt or attempt != submission.attempt
        or attempt.command.action != "ASSERT_OPERATION_CLAIM"
        or attempt.command.tenant_id != selected.tenant_id
    ):
        raise ValueError("event admission differs from the guarded attempt")
    if any(type(ref) is not str or not ref.strip() for ref in (
        selected.producer_ref, selected.event_ref, selected.proof_ref,
        submission.request_id, submission.idempotency_key,
    )):
        raise ValueError("event admission lacks a governed source or request identity")
    for digest in (
        selected.request_sha256, selected.intent_sha256, selected.envelope_sha256,
        selected.profile_sha256, selected.context_sha256, selected.contract_sha256,
    ):
        if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("missing independent raw source digest")
    if type(selected.proof_digest) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", selected.proof_digest):
        raise ValueError("invalid independently selected proof digest")
    if (selected.event_revision is None) == (selected.event_digest is None):
        raise ValueError("event source requires one immutable revision or digest")
    if selected.event_revision is not None and (
        type(selected.event_revision) is not str or not selected.event_revision.strip()
    ):
        raise ValueError("event source lacks a revision")
    if selected.event_digest is not None and (
        type(selected.event_digest) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", selected.event_digest)
    ):
        raise ValueError("invalid selected event digest")
    if type(attempt.intent_bytes) is not bytes or sha256(attempt.intent_bytes).hexdigest() != selected.intent_sha256:
        raise ValueError("intent bytes differ from the independent selection")
    intent = _parse_original(attempt.intent_bytes, "intent")
    if selected.event_kind == "ASSOCIATED_WORLD_EVENT":
        selector = {"revisionRef": selected.event_revision} if selected.event_revision is not None else {
            "digest": selected.event_digest,
        }
        if intent.get("associatedSemanticEventBinding") != {"ref": selected.event_ref, **selector}:
            raise ValueError("associated event differs from the selected intent binding")
    elif selected.event_kind != "SUBMISSION_ACT" or "associatedSemanticEventBinding" in intent:
        raise ValueError("submission act requires an intent without a world-event association")

    request = _pinned_document(submission.request_bytes, "request", selected.request_sha256)
    if (
        request.get("schemaVersion") != "ofarm.commitingressrequest.v0.1"
        or request.get("commitClass") != "OPERATION_CLAIM"
        or request.get("requestId") != submission.request_id
        or request.get("idempotencyKey") != submission.idempotency_key
        or request.get("semanticEventRef") != selected.event_ref
    ):
        raise ValueError("original request differs from the admitted submission")
    actors = {"actingPartyRef": submission.acting_party_ref, "actingAgentRef": submission.acting_agent_ref}
    expected_actors = {key: ref for key, ref in actors.items() if ref is not None}
    if (
        not expected_actors or any(type(ref) is not str or not ref for ref in expected_actors.values())
        or {key: request[key] for key in actors if key in request} != expected_actors
    ):
        raise ValueError("original request differs from the admitted actor")
    if type(submission.target_scopes) is not tuple or not submission.target_scopes or any(
        type(scope) is not tuple or len(scope) != 2 or any(type(item) is not str or not item for item in scope)
        for scope in submission.target_scopes
    ):
        raise ValueError("missing independently admitted scopes")
    scopes = [{"scopeType": kind, "scopeRef": ref} for kind, ref in submission.target_scopes]
    if request.get("targetScopes") != scopes:
        raise ValueError("original request differs from the admitted scopes")


class _EventAdmission:
    """Bound by the private claim adapter. A missing source or canonical checker refuses."""

    def __init__(
        self, submission: _Submission, reader: Callable[[str], _RetainedProof | None] | None = None,
    ) -> None:
        self._submission = submission
        self._reader = reader

    def admit(self, attempt: ClaimWriteAttempt) -> Never:
        _check_submission(self._submission, attempt)
        selected = self._submission.selection
        if self._reader is None:
            raise ValueError("retained proof reader unavailable")
        source = self._reader(selected.proof_ref)
        if (
            type(source) is not _RetainedProof
            or type(source.selection) is not _ProofSelection or source.selection != selected
        ):
            raise ValueError("missing retained proof or different governed source")
        if source.production_mode != "PREEXISTING_PROOF":
            raise ValueError("event admission requires a pre-existing proof")
        envelope = _pinned_document(source.envelope_bytes, "envelope", selected.envelope_sha256)
        if (
            envelope.get("schemaVersion") != "ofarm.semanticeventenvelope.v0.1"
            or envelope.get("semanticEventId") != selected.event_ref
        ):
            raise ValueError("original event envelope differs from the admitted submission")
        _pinned_document(source.profile_bytes, "profile", selected.profile_sha256)
        context = _pinned_document(source.context_bytes, "context", selected.context_sha256)
        proof = _document(source.proof_bytes, "proof")
        if (
            proof.get("productionMode") != source.production_mode
            or context.get("productionMode") != source.production_mode
            or proof.get("proofId") != selected.proof_ref
            or context.get("expectedProofId") != selected.proof_ref
        ):
            raise ValueError("proof or independent context differs from the retained source")
        # OFARM #49 has no accepted main revision. Raw source integrity cannot establish classification.
        raise RuntimeError("accepted Event Ingress checker unavailable")
