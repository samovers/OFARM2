"""Render #51's four storage originals from this test source's measured observations."""

from datetime import timedelta, timezone

from kernel.tests._operation_claim_specimen import (
    binding,
    json_bytes,
    original,
    raw_hash,
    STATE_CONTRACT_HASH,
)


def artifact_ref(attempt, role):
    return f"fixture:storage:{attempt.tenant}:{attempt.id}:{role}"


def guard_policy(attempt):
    return {
        "schemaVersion": "ofarm.preVerdictGuardPolicy.v0.1",
        "policyId": artifact_ref(attempt, "policy"),
        "storageOwnerRef": "fixture:operation-claim-storage",
        "atomicPersistenceBoundaryRef": artifact_ref(attempt, "boundary"),
        "proofMode": "OPTIMISTIC_COMPARE_COMMIT",
        "observationPhase": "AFTER_PROPOSED_WRITES_BEFORE_DOMAIN_VERDICT",
        "writeBoundary": "ONE_ASSERTION_INSERT_ONLY",
        "guardContinuity": "RECHECK_ALL_READ_NEGATIVE_SET_AND_WRITE_GUARDS_THROUGH_COMMIT",
        "reuse": "IDENTICAL_INPUTS_SAME_ATTEMPT_REEVALUATION_ONLY",
        "domainInputCompletenessOwner": "CONSUMING_DOMAIN_CONTRACT",
    }


def utc(value):
    stamp = value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
    return stamp.rstrip("0").rstrip(".") + "Z"


def storage_originals(case, attempt, start, read, snapshot_token, started):
    policy = guard_policy(attempt)
    names = {role: artifact_ref(attempt, role) for role in ("snapshot", "context", "proof")}
    specs = {}
    reads, positives, read_guards = [], [], []
    for use in case["uses"]:
        key, ref, role = use["key"], use["ref"], use["role"]
        revision, raw, version = read.rows[ref]
        content = {
            "binding": {"ref": ref, "digest": case["sources"][ref]["digest"]},
            "rawSha256": raw_hash(raw),
        }
        specs[key] = content
        if role == "PROPOSED_WRITE":
            continue
        source = {**content, "key": key, "revisionRef": revision}
        availability = "COMMITTED_AT_TRANSACTION_START"
        reads.append({**source, "role": role, "availability": availability})
        positives.append({**source, "rowVersion": start.rows[ref][2], "visibility": availability})
        read_guards.append(
            {
                **source,
                "availability": availability,
                "snapshotVersion": start.rows[ref][2],
                "observedVersion": version,
            }
        )
    assertion_id = case["assertionId"]
    negative = {
        "key": assertion_id,
        "purpose": "ASSERTION_ID_ABSENCE",
        "predicateDigest": binding(
            "predicate", {"recordType": "AssertionRecord", "id": assertion_id, "predicate": "ABSENT"}
        )["digest"],
    }
    set_key = case["set"]["key"]
    members = [{"ref": ref, "digest": case["sources"][ref]["digest"]} for ref in read.members]
    set_read = {
        "key": set_key,
        "members": members,
        "predicateDigest": binding(
            "predicate",
            {
                "tenant": str(attempt.tenant),
                "setKey": set_key,
                "table": "claim_evidence.member",
                "orderBy": "position",
            },
        )["digest"],
    }
    absent_key, members_key = "absence:" + assertion_id, "set:" + set_key
    snapshot = {
        "schemaVersion": "ofarm.transactionStartSnapshotEvidence.v0.1",
        "snapshotId": names["snapshot"],
        "transactionAttemptId": str(attempt.id),
        "storageOwnerRef": policy["storageOwnerRef"],
        "atomicPersistenceBoundaryRef": policy["atomicPersistenceBoundaryRef"],
        "snapshotToken": snapshot_token,
        "capturePhase": "TRANSACTION_START",
        "positiveRecords": positives,
        "negativeRecords": [
            {
                **negative,
                "guardVersion": start.guards[absent_key],
                "observation": "ABSENT_AT_TRANSACTION_START",
            }
        ],
        "setRecords": [{**set_read, "guardVersion": start.guards[members_key]}],
    }
    snapshot_binding = binding(names["snapshot"], snapshot)
    policy_binding = binding(policy["policyId"], policy)
    context = {
        "schemaVersion": "ofarm.preVerdictProtectedStateContext.v0.1",
        "contextId": names["context"],
        "storageOwnerRef": policy["storageOwnerRef"],
        "actionClass": case["action"],
        "attempt": {
            "transactionAttemptId": str(attempt.id),
            "attemptSequence": 1,
            "transactionStartedAt": utc(started),
            "transactionDeadline": utc(started + timedelta(seconds=60)),
            "transactionSnapshot": snapshot_binding,
            "atomicPersistenceBoundaryRef": policy["atomicPersistenceBoundaryRef"],
            "guardPolicyBinding": policy_binding,
            "transactionStatusLookupKey": artifact_ref(attempt, "status"),
            "transactionTimePolicyBinding": specs["transactionTimePolicy"]["binding"],
        },
        "effectIntent": specs["intent"],
        "proposedAssertion": specs["proposed"],
        "proposedAssertionId": assertion_id,
        "transactionProfile": specs["transactionProfile"],
        "transactionTimePolicy": specs["transactionTimePolicy"],
        "requiredReads": reads,
        "requiredNegativeReads": [negative],
        "requiredSetReads": [set_read],
        "governanceContext": {
            "boundaryKind": "TENANT",
            "boundaryRef": str(attempt.tenant),
            "twin": {"posture": "NOT_APPLICABLE"},
        },
        "proofId": names["proof"],
    }
    write = {
        "operation": "INSERT",
        "recordType": "AssertionRecord",
        "key": assertion_id,
        **specs["proposed"],
    }
    proof = {
        "schemaVersion": "ofarm.preVerdictProtectedStateProof.v0.1",
        "proofId": names["proof"],
        "storageOwnerRef": policy["storageOwnerRef"],
        "transactionAttemptId": str(attempt.id),
        "context": binding(names["context"], context),
        "snapshot": snapshot_binding,
        "guardPolicy": policy_binding,
        "phase": policy["observationPhase"],
        "readGuards": read_guards,
        "negativeGuards": [
            {
                **negative,
                "snapshotVersion": start.guards[absent_key],
                "observedVersion": read.guards[absent_key],
                "observation": "ABSENT",
            }
        ],
        "setGuards": [
            {
                **set_read,
                "snapshotVersion": start.guards[members_key],
                "observedVersion": read.guards[members_key],
            }
        ],
        "proposedDomainWrites": [write],
    }
    return {
        role: json_bytes(doc)
        for role, doc in (
            ("context", context),
            ("policy", policy),
            ("snapshot", snapshot),
            ("proof", proof),
        )
    }


def state_arguments(artifacts, records, selected_proof):
    return {
        **{role + "_bytes": original(raw) for role, raw in artifacts.items()},
        "selected": {
            "contractRawSha256": STATE_CONTRACT_HASH,
            "contextRawSha256": raw_hash(artifacts["context"]),
            "policyRawSha256": raw_hash(artifacts["policy"]),
            "proofBinding": selected_proof,
        },
        "records": {ref: original(raw) for ref, raw in records.items()},
    }
