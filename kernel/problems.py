"""RuntimeProblem factory and the reason codes this runtime emits.

Every refusal is a RuntimeProblem with a registry reason code (Kernel rule 7;
PLATFORM.md gate pipeline). Codes below are drawn verbatim from the
RuntimeProblem Reason Code Registry RFC v0.1 (reference/rfcs/). Returning an
unregistered reason code is a conformance failure per that RFC §6, so the
factory refuses unknown codes loudly.
"""
from __future__ import annotations

import itertools

# Registry codes this runtime may emit (verbatim from the RFC).
REGISTERED_REASON_CODES = {
    # authority
    "AUTHORITY_DENIED",
    "HUMAN_APPROVAL_REQUIRED",
    "DELEGATION_REVOKED",
    "SCOPE_NOT_AUTHORIZED",
    # evidence
    "EVIDENCE_INSUFFICIENT",
    "EVIDENCE_REFERENCE_UNAVAILABLE",
    # identity
    "IDENTITY_UNRESOLVED",
    "PRODUCT_BINDING_UNRESOLVED",
    "ACTOR_BINDING_UNRESOLVED",
    # unit/calculation
    "UNIT_UNRESOLVED",
    # materialization
    "MATERIALIZATION_STALE",
    "MATERIALIZATION_INVALID",
    "MATERIALIZATION_BASIS_MISSING",
    # publication
    "HIGH_CONSEQUENCE_BLOCKED",
    "PUBLICATION_BASIS_INCOMPLETE",
    # pack/profile
    "PROFILE_NOT_ACTIVE",
    "PACK_CONFLICT",
    # retry/idempotency
    "RETRY_CONFLICT",
    "IDEMPOTENCY_REPLAY_REUSED",
    "IDEMPOTENCY_REPLAY_CONFLICT",
    # permission/redaction
    "PERMISSION_REDACTED",
    "TENANT_BOUNDARY_BLOCKED",
    # correction/dispute
    "DISPUTE_OPEN",
    "SUPERSEDED_RECORD_USED",
    "CORRECTION_REQUIRED",
    # import / source fidelity (M2 G2 governed import mechanism)
    "SOURCE_FIDELITY_LOSS",
    "DUPLICATE_IMPORT_AMBIGUOUS",
}

_counter = itertools.count(1)


def runtime_problem(
    reason_code: str,
    title: str,
    detail: str,
    *,
    severity: str = "ERROR",
    related_refs: list[str] | None = None,
    suggested_remediation: str | None = None,
    problem_id: str | None = None,
) -> dict:
    """Build a RuntimeProblem payload (ofarm.runtimeproblem.v0.1)."""
    if reason_code not in REGISTERED_REASON_CODES:
        raise ValueError(
            f"unregistered reason code {reason_code!r} — add it from the registry RFC, "
            "never invent codes (registry RFC §6)"
        )
    problem = {
        "schemaVersion": "ofarm.runtimeproblem.v0.1",
        "problemId": problem_id or f"problem:{next(_counter):06d}",
        "severity": severity,
        "reasonCode": reason_code,
        "title": title,
        "detail": detail,
    }
    if related_refs:
        problem["relatedRefs"] = related_refs
    if suggested_remediation:
        problem["suggestedRemediation"] = suggested_remediation
    return problem
