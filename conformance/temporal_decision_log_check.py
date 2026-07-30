#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = PACKAGE_ROOT / "governance/temporal-decision-log"
ENTRY_DIGEST = "sha256:ed48914f77bedacdfce32fb621819da7df7701b54d7862477db0a49ceee5cdc6"
ENTRY_FILE_DIGEST = (
    "sha256:72a2319430eb1a74c2e99f9ef68aab5c17081b37390b4488b8187bb698ebde80"
)
ENTRY_PATH = LOG_PATH / f"{ENTRY_DIGEST.removeprefix('sha256:')}.json"
FINAL_ENTRY_CANONICAL_BYTE_LENGTH = 4880

CONTRACT_IDENTITY = "ofarm.temporal-governance-decision-log.issue176-predeployment.v0.2"
BASE_CONTRACT_IDENTITY = (
    "ofarm.temporal-governance-decision-log.issue176-predeployment.v0.1"
)
BASE_CONTRACT_DIGEST = (
    "sha256:958c4a3c2377515022bc1dd6483136e923b9bfa110b507f102a9ec623a0e5d89"
)
AMENDMENT_CONTRACT_DIGEST = (
    "sha256:bfcfeb1858ec6bc08242e208221148b5fb77d5052b4571a3c8564983a81de5f6"
)
PROMOTION_CONTRACT_IDENTITY = (
    "ofarm.temporal-governance-promotion.issue176-foundation.v0.1"
)
PROMOTION_CONTRACT_DIGEST = (
    "sha256:10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0"
)
PINNED_FILES = (
    (
        PACKAGE_ROOT / "docs/rfcs/OFARM_Temporal_Governance_Decision_Log_RFC_v0_1.md",
        BASE_CONTRACT_DIGEST,
    ),
    (
        PACKAGE_ROOT / "docs/rfcs/"
        "OFARM_Temporal_Governance_Decision_Log_Evidence_Amendment_RFC_v0_2.md",
        AMENDMENT_CONTRACT_DIGEST,
    ),
    (
        PACKAGE_ROOT / "contracts/candidates/temporal_governance_promotion/"
        "OFARM_TemporalGovernancePromotion_candidate_v0_1.json",
        PROMOTION_CONTRACT_DIGEST,
    ),
)

CODEX_TASK_ID = "019fa821-93c9-7ef1-8c94-1c0e92ea46b9"
APPROVAL_USER_MESSAGE_REF = "019fb31e-a55e-7683-a2f5-142369fd9335"
DECIDED_AT = "2026-07-30T13:02:37.932Z"
DECISION_CARD_DIGEST = (
    "sha256:aef1d628bb1b54c03f020aef5cec05c7ca7d1f00556004f89204ae13d416fa03"
)
APPROVAL_SENTENCE = (
    "I explicitly approve decision card "
    f"{DECISION_CARD_DIGEST} in Codex task {CODEX_TASK_ID} and authorize one "
    "matching repository decision-log entry as the current pre-deployment "
    "OFARM2 decision, with exactly the decision-evidence mapping, effects, "
    "and non-effects stated in that card."
)
APPROVAL_SENTENCE_DIGEST = (
    "sha256:e52c091c33000db36714d87d6d88162eb6e783fbb9bb33860dd4794fc55549e2"
)
CARD_CANONICAL_BYTE_LENGTH = 2557

DECISION_EVIDENCE_MAPPING = {
    "currentnessTraceRef": "CONTAINING_ENTRY_AND_EXPLICIT_PREDECESSOR_CHAIN",
    "decidedAt": "APPROVAL_USER_MESSAGE_TURN_STARTED_AT_UTC_MILLISECONDS",
    "humanPromotionAuthorityRef": ("CODEX_TASK_AND_APPROVAL_USER_MESSAGE_STABLE_REF"),
    "promotionDecisionRef": "DECISION_LOG_CONTRACT_IDENTITY_AND_CARD_DIGEST",
    "reviewEvidenceRefs": "PINNED_PROMOTION_BASE_AND_AMENDMENT_CONTRACTS",
}
SUBJECT_IDENTITIES = [
    "ofarm.temporal-carrier-matrix.adr0002.v0.1",
    "ofarm.temporal-carrier-selection.intervention.v0.1",
    "ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1",
]
NON_EFFECTS = [
    "RUNTIME_ACTIVATION",
    "CURRENT_DEFAULT_ARTIFACT_STATUS",
    "DEPLOYMENT_OR_PRODUCTION_EFFECT",
    "RUNTIME_BUNDLE_CHANGE",
    "PROFILE_OR_MANIFEST_ACTIVATION",
    "ROUTE_OR_COMMAND_INTEGRATION",
    "DATABASE_OR_MIGRATION_EFFECT",
    "READ_HISTORICAL_WINDOW_MATERIALIZATION_QUALIFICATION_OR_OUTPUT_EFFECT",
    "LEGACY_SEMANTIC_OR_OUTPUT_EFFECT",
    "ISSUE_192_EFFECT",
]


class TemporalDecisionLogError(ValueError):
    pass


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _exact_dict(value: object, keys: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise TemporalDecisionLogError(f"{label} fields differ")
    return value


def validate_entry(value: object, *, filename: str, raw: bytes) -> None:
    entry = _exact_dict(
        value,
        {
            "approvalEvidence",
            "contractIdentity",
            "currentnessTraceRef",
            "decidedAt",
            "decisionCardDigest",
            "decisionCardPayload",
            "entryDigest",
            "humanPromotionAuthorityRef",
            "promotionDecisionRef",
            "reviewEvidenceRefs",
            "supersedesEntryDigest",
        },
        "decision-log entry",
    )
    if raw != canonical_json(entry):
        raise TemporalDecisionLogError("decision-log entry is not exact canonical JSON")

    entry_digest = entry["entryDigest"]
    if (
        type(entry_digest) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", entry_digest) is None
        or entry_digest != ENTRY_DIGEST
    ):
        raise TemporalDecisionLogError("decision-log entry digest differs")
    digest_input = dict(entry)
    del digest_input["entryDigest"]
    if digest_bytes(canonical_json(digest_input)) != entry_digest:
        raise TemporalDecisionLogError("decision-log entry digest differs")
    if filename != f"{entry_digest.removeprefix('sha256:')}.json":
        raise TemporalDecisionLogError("decision-log entry filename differs")

    expected_approval = {
        "approvalMessageOrder": ("AI_ATTESTED_CARD_PRECEDES_APPROVAL_IN_SAME_TASK"),
        "approvalMessageRole": "user",
        "approvalSentence": APPROVAL_SENTENCE,
        "approvalSentenceDigest": APPROVAL_SENTENCE_DIGEST,
        "approvalUserMessageIdOrStableRef": APPROVAL_USER_MESSAGE_REF,
        "codexTaskId": CODEX_TASK_ID,
        "evidencePosture": ("AI_ATTESTED_INDEPENDENTLY_UNVERIFIABLE_PREDEPLOYMENT"),
    }
    expected_reviews = [
        {
            "contractIdentity": PROMOTION_CONTRACT_IDENTITY,
            "repositoryFileDigest": PROMOTION_CONTRACT_DIGEST,
        },
        {
            "contractIdentity": BASE_CONTRACT_IDENTITY,
            "repositoryFileDigest": BASE_CONTRACT_DIGEST,
        },
        {
            "contractIdentity": CONTRACT_IDENTITY,
            "repositoryFileDigest": AMENDMENT_CONTRACT_DIGEST,
        },
    ]
    if {
        "approvalEvidence": entry["approvalEvidence"],
        "contractIdentity": entry["contractIdentity"],
        "currentnessTraceRef": entry["currentnessTraceRef"],
        "decidedAt": entry["decidedAt"],
        "decisionCardDigest": entry["decisionCardDigest"],
        "humanPromotionAuthorityRef": entry["humanPromotionAuthorityRef"],
        "promotionDecisionRef": entry["promotionDecisionRef"],
        "reviewEvidenceRefs": entry["reviewEvidenceRefs"],
        "supersedesEntryDigest": entry["supersedesEntryDigest"],
    } != {
        "approvalEvidence": expected_approval,
        "contractIdentity": CONTRACT_IDENTITY,
        "currentnessTraceRef": {
            "decisionCardDigest": DECISION_CARD_DIGEST,
            "mechanism": "CONTAINING_ENTRY_AND_EXPLICIT_PREDECESSOR_CHAIN",
            "supersedesEntryDigest": None,
        },
        "decidedAt": DECIDED_AT,
        "decisionCardDigest": DECISION_CARD_DIGEST,
        "humanPromotionAuthorityRef": {
            "approvalUserMessageIdOrStableRef": APPROVAL_USER_MESSAGE_REF,
            "codexTaskId": CODEX_TASK_ID,
        },
        "promotionDecisionRef": {
            "decisionCardDigest": DECISION_CARD_DIGEST,
            "decisionLogContractIdentity": CONTRACT_IDENTITY,
        },
        "reviewEvidenceRefs": expected_reviews,
        "supersedesEntryDigest": None,
    }:
        raise TemporalDecisionLogError(
            "decision-log evidence differs from approved decision"
        )
    if digest_bytes(APPROVAL_SENTENCE.encode("utf-8")) != (APPROVAL_SENTENCE_DIGEST):
        raise TemporalDecisionLogError("approval sentence digest differs")

    card = _exact_dict(
        entry["decisionCardPayload"],
        {
            "codexTaskId",
            "contractIdentity",
            "contractRepositoryFileDigest",
            "decision",
            "decisionEffect",
            "decisionEvidenceMapping",
            "nonEffects",
            "promotionContractIdentity",
            "promotionContractRepositoryFileDigest",
            "subjects",
            "supersedesEntryDigest",
        },
        "decision-card",
    )
    if (
        card["codexTaskId"] != CODEX_TASK_ID
        or card["contractIdentity"] != CONTRACT_IDENTITY
        or card["contractRepositoryFileDigest"] != AMENDMENT_CONTRACT_DIGEST
        or card["decision"] != "PROMOTE_GOVERNED_INACTIVE"
        or card["decisionEffect"]
        != (
            "ALL_THREE_EXACT_SUBJECTS_ARE_CURRENT_"
            "PREDEPLOYMENT_GOVERNED_INACTIVE_DECISION"
        )
        or card["decisionEvidenceMapping"] != DECISION_EVIDENCE_MAPPING
        or card["nonEffects"] != NON_EFFECTS
        or card["promotionContractIdentity"] != PROMOTION_CONTRACT_IDENTITY
        or card["promotionContractRepositoryFileDigest"] != PROMOTION_CONTRACT_DIGEST
        or [subject.get("identity") for subject in card["subjects"]]
        != SUBJECT_IDENTITIES
        or card["supersedesEntryDigest"] is not None
    ):
        raise TemporalDecisionLogError("decision-card differs from approved decision")
    card_bytes = canonical_json(card)
    if (
        len(card_bytes) != CARD_CANONICAL_BYTE_LENGTH
        or digest_bytes(card_bytes) != DECISION_CARD_DIGEST
    ):
        raise TemporalDecisionLogError("approved decision-card digest differs")

    if (
        len(raw) != FINAL_ENTRY_CANONICAL_BYTE_LENGTH
        or digest_bytes(raw) != ENTRY_FILE_DIGEST
    ):
        raise TemporalDecisionLogError("decision-log entry file pin differs")


def validate_decision_log(log_path: Path = LOG_PATH) -> None:
    for path, expected_digest in PINNED_FILES:
        if digest_bytes(path.read_bytes()) != expected_digest:
            raise TemporalDecisionLogError(f"pinned authority differs: {path.name}")
    paths = sorted(log_path.iterdir())
    if (
        len(paths) != 1
        or paths[0].name != ENTRY_PATH.name
        or not paths[0].is_file()
        or paths[0].is_symlink()
    ):
        raise TemporalDecisionLogError(
            "decision-log must contain exactly one first entry"
        )
    raw = paths[0].read_bytes()
    validate_entry(json.loads(raw), filename=paths[0].name, raw=raw)


def main() -> int:
    try:
        validate_decision_log()
    except (OSError, json.JSONDecodeError, TemporalDecisionLogError) as exc:
        print(f"TEMPORAL DECISION LOG FAIL: {exc}")
        return 1
    print("TEMPORAL DECISION LOG PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
