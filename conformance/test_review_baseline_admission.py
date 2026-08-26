#!/usr/bin/env python3
"""Zero-dependency tests for trusted expensive-baseline admission."""

from __future__ import annotations

import hashlib
import io
import json
import re
import stat
import tarfile
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

from conformance import run_review_baseline as review_policy
from conformance.evidence_publication_policy import (
    NATIVE_AUTHORITATIVE_FILES,
    NATIVE_EVIDENCE_FILES,
    PLATFORM_PUBLICATION_FILE,
    PROVISIONAL_ARTIFACT_LIMITS,
    REVIEW_BASELINE_FILES,
    TRUSTED_METADATA_FILES,
    PublicationPolicyError,
    _HttpsOnlyRedirectHandler,
    _extract_installed_artifacts,
    _native_policy_module,
    _validate_produced_artifact_binding,
    _validate_test_results,
    download_and_extract_artifact,
    stage_conformance_evidence,
    validate_conformance_inventory,
    validate_native_claims,
    validate_native_inventory,
)
from conformance.review_baseline_admission import (
    ADMISSION_MARKER,
    EVIDENCE_SCHEMA,
    GRAPHQL_COMMENT_PREFIX,
    GATE_WORKFLOW_PATH,
    PROVISIONAL_ARTIFACT_NAMES,
    PUBLICATION_ARTIFACT_NAMES,
    PUBLICATION_RECEIPT_SCHEMA,
    PUBLICATION_TICKET_NAME,
    PUBLICATION_WORKFLOW_PATH,
    REVOCATION_MARKER,
    SOURCE_ARTIFACT_MAX_BYTES,
    ArtifactReference,
    AdmissionError,
    _artifact_references,
    _publication_plan,
    _publication_receipt_document,
    _publication_source_from_event,
    _publication_ticket_document,
    _validate_publication_ticket,
    decide,
    gate_decision,
)


HEAD_SHA = "a" * 40
NEXT_SHA = "b" * 40
BASE_SHA = "c" * 40
MERGE_SHA = "d" * 40
POLICY_SHA = "e" * 40
REPOSITORY = "samovers/OFARM2"
PR_NUMBER = 336
COMMENT_ID = 12345
COMMENT_NODE_ID = "IC_kwDOExample"
CREATED_AT = "2026-08-26T08:00:00Z"
REVOCATION_AT = "2026-08-26T09:00:00Z"
SOURCE_RUN_ID = 987654321
SOURCE_RUN_ATTEMPT = 1
PUBLISHER_RUN_ID = 123456789
PUBLISHER_RUN_ATTEMPT = 1
GATE_WORKFLOW_REF = (
    f"{REPOSITORY}/.github/workflows/review-baseline-gate.yml@refs/heads/main"
)
CONFORMANCE_WORKFLOW_REF = (
    f"{REPOSITORY}/.github/workflows/conformance.yml@refs/heads/main"
)
PUBLICATION_WORKFLOW_REF = (
    f"{REPOSITORY}/{PUBLICATION_WORKFLOW_PATH}@refs/heads/main"
)


class FakeArtifactResponse(io.BytesIO):
    status = 200

    def geturl(self) -> str:
        return "https://artifact-results.example.test/immutable.zip"


def artifact_zip(
    entries: dict[str, bytes],
    *,
    duplicate: str | None = None,
    symlink: str | None = None,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
        if duplicate is not None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr(duplicate, "first")
                archive.writestr(duplicate, "second")
        if symlink is not None:
            entry = zipfile.ZipInfo(symlink)
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(entry, "target")
    return output.getvalue()


def write_inventory(root: Path, names: set[str] | frozenset[str]) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"evidence")


def passing_test_results_fixture():
    entry = {
        "nodeid": "kernel/tests/test_example.py::test_passes",
        "sourceModule": "kernel.tests.test_example",
        "sourcePath": "kernel/tests/test_example.py",
    }
    entries_digest = hashlib.sha256(
        (
            json.dumps([entry], sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
    ).hexdigest()
    inventory = {
        "schemaVersion": "ofarm.review-baseline-test-inventory.v1",
        "testRoot": "kernel/tests",
        "entryCount": 1,
        "entriesSha256": entries_digest,
        "entries": [entry],
    }
    warning_policy = {"mode": "exact-inventory", "expected": []}
    results = {
        "schemaVersion": "ofarm.review-baseline-pytest-results.v2",
        "collection": {
            "collected": [entry],
            "selected": [entry],
            "deselected": [],
            "skippedCollectors": [],
            "errors": [],
        },
        "execution": {
            "outcomes": [
                {
                    **entry,
                    "outcome": "passed",
                    "phases": [
                        {"phase": "setup", "outcome": "passed"},
                        {"phase": "call", "outcome": "passed"},
                        {"phase": "teardown", "outcome": "passed"},
                    ],
                }
            ],
            "skipped": [],
            "unavailable": [],
        },
        "warnings": [],
        "summary": {
            "collected": 1,
            "selected": 1,
            "passed": 1,
            "failed": 0,
            "error": 0,
            "xfailed": 0,
            "xpassed": 0,
            "skipped": 0,
            "deselected": 0,
            "collectionSkipped": 0,
            "unavailable": 0,
            "collectionErrors": 0,
            "warnings": 0,
            "pytestExitStatus": 0,
        },
    }
    return results, inventory, warning_policy


def complete_test_results_fixture(config, inventory):
    entries = inventory["entries"]
    phases = [
        {"phase": "setup", "outcome": "passed"},
        {"phase": "call", "outcome": "passed"},
        {"phase": "teardown", "outcome": "passed"},
    ]
    warnings_inventory = config["warningPolicy"]["expected"]
    count = len(entries)
    return {
        "schemaVersion": "ofarm.review-baseline-pytest-results.v2",
        "collection": {
            "collected": entries,
            "selected": entries,
            "deselected": [],
            "skippedCollectors": [],
            "errors": [],
        },
        "execution": {
            "outcomes": [
                {**entry, "outcome": "passed", "phases": phases}
                for entry in entries
            ],
            "skipped": [],
            "unavailable": [],
        },
        "warnings": warnings_inventory,
        "summary": {
            "collected": count,
            "selected": count,
            "passed": count,
            "failed": 0,
            "error": 0,
            "xfailed": 0,
            "xpassed": 0,
            "skipped": 0,
            "deselected": 0,
            "collectionSkipped": 0,
            "unavailable": 0,
            "collectionErrors": 0,
            "warnings": len(warnings_inventory),
            "pytestExitStatus": 0,
        },
    }


def complete_environment_fixture(config):
    required = config["requiredEnvironment"]
    locked = review_policy._parse_lock(
        review_policy.ROOT / config["paths"]["dependencyLock"]
    )
    locked.update(
        review_policy._parse_lock(
            review_policy.ROOT / config["paths"]["packageManagerLock"]
        )
    )
    installed = [
        {"name": name, "version": locked[name]} for name in sorted(locked)
    ]

    def postgres(system_identifier, database):
        return {
            "available": True,
            "version": required["postgresqlVersion"],
            "rawVersion": "17.10 fixture",
            "systemIdentifier": system_identifier,
            "database": database,
        }

    return {
        "platform": {
            "operatingSystem": {
                "required": required["operatingSystem"],
                "actual": required["operatingSystem"],
            },
            "machine": {
                "required": required["machine"],
                "actual": required["machine"],
            },
        },
        "python": {
            "implementation": {
                "required": required["pythonImplementation"],
                "actual": required["pythonImplementation"],
            },
            "version": {
                "required": required["pythonVersion"],
                "actual": required["pythonVersion"],
            },
            "optimizationLevel": {
                "required": required["pythonOptimizationLevel"],
                "actual": required["pythonOptimizationLevel"],
            },
        },
        "pip": {
            "required": required["pipVersion"],
            "actual": required["pipVersion"],
        },
        "postgresql": {
            "requiredVersion": required["postgresqlVersion"],
            "testConnectionSource": "derived-from-verified-admin-connection",
            "testDatabase": required["testDatabaseName"],
            "admin": postgres("1", "postgres"),
            "tenantProvisioningAdmin": postgres("2", "postgres"),
            "securityAuditAdmin": postgres("3", "postgres"),
            "testStore": postgres("1", required["testDatabaseName"]),
            "sameServer": True,
            "tenantAuditSystemIdentifiersDistinct": True,
            "testAndProvisioningSystemIdentifiersPairwiseDistinct": True,
            "testAndProvisioningPostgresqlVersionsEqual": True,
            "testAndProvisioningPostgresqlBuildsEqual": True,
        },
        "dependencies": {
            "installed": installed,
            "installedSetDigest": review_policy._sha256_bytes(
                review_policy._canonical_bytes(installed)
            ),
            "missingOrMismatched": {},
            "unexpected": {},
            "pipCheckPassed": True,
        },
        "determinism": {
            "pythonHashSeed": required["pythonHashSeed"],
            "timezone": required["timezone"],
            "locale": required["locale"],
            "pytestPluginAutoloadDisabled": True,
            "pythonNoUserSite": True,
            "pythonDontWriteBytecode": True,
            "scrubbedAmbientVariables": [
                "PYTEST_ADDOPTS",
                "PYTEST_PLUGINS",
                "PYTHONOPTIMIZE",
                "PYTHONPATH",
                "PYTHONWARNINGS",
                "OFARM_*",
            ],
            "allowedOfarmVariables": sorted(review_policy.ALLOWED_OFARM_ENV),
            "derivedOfarmVariables": ["OFARM_PG_DSN"],
        },
        "ci": {
            "configuredRunnerLabel": required["runner"],
            "observedImageOs": "ubuntu24",
            "observedImageVersion": "fixture",
            "runId": str(SOURCE_RUN_ID),
            "runAttempt": str(SOURCE_RUN_ATTEMPT),
            "configuredActionPins": config["knownGreenBaseline"]["observedInRun"]["actions"],
            "configuredPostgresqlImageDigest": config["knownGreenBaseline"]["observedInRun"]["postgresqlImageDigest"],
        },
    }


def workflow_job_section(workflow: str, job_name: str) -> str:
    marker = f"\n  {job_name}:\n"
    if marker not in workflow:
        raise AssertionError(f"workflow job is missing: {job_name}")
    section = workflow.split(marker, 1)[1]
    next_job = re.search(r"\n  [a-zA-Z0-9_-]+:\n", section)
    return section if next_job is None else section[: next_job.start()]


def admission_body(head_sha: str = HEAD_SHA) -> str:
    return (
        "Exact-head review complete.\n\n"
        f"{ADMISSION_MARKER}\n"
        f"head={head_sha}\n"
        "blockers=0\n"
    )


def revocation_body(head_sha: str = HEAD_SHA) -> str:
    return f"Admission withdrawn.\n\n{REVOCATION_MARKER}\nhead={head_sha}\n"


def issue_comment_event(
    *,
    action: str = "created",
    body: str | None = None,
    association: str = "OWNER",
    prior_body: str | None = None,
    pull_request: bool = True,
) -> dict[str, object]:
    event: dict[str, object] = {
        "action": action,
        "repository": {"full_name": REPOSITORY},
        "issue": {
            "number": PR_NUMBER,
            **({"pull_request": {"url": "unused"}} if pull_request else {}),
        },
        "comment": {
            "id": COMMENT_ID,
            "body": admission_body() if body is None else body,
            "author_association": association,
        },
    }
    if prior_body is not None:
        event["changes"] = {"body": {"from": prior_body}}
    return event


def pull_request_target_event(action: str = "synchronize") -> dict[str, object]:
    return {
        "action": action,
        "repository": {"full_name": REPOSITORY},
        "pull_request": {"number": PR_NUMBER},
    }


def live_reader(
    *,
    body: str | None = None,
    head_sha: str = HEAD_SHA,
    base_sha: str = BASE_SHA,
    merge_sha: object = MERGE_SHA,
    merge_parents: list[str] | None = None,
    association: str = "OWNER",
    created_at: str = CREATED_AT,
    updated_at: str = CREATED_AT,
    last_edited_at: str | None = None,
    minimized: bool = False,
):
    comment_body = admission_body() if body is None else body
    parent_shas = merge_parents or [base_sha, head_sha]
    responses = {
        f"/repos/{REPOSITORY}/pulls/{PR_NUMBER}": {
            "number": PR_NUMBER,
            "state": "open",
            "head": {"sha": head_sha},
            "base": {"sha": base_sha},
            "merge_commit_sha": merge_sha,
        },
        f"/repos/{REPOSITORY}/issues/comments/{COMMENT_ID}": {
            "id": COMMENT_ID,
            "node_id": COMMENT_NODE_ID,
            "issue_url": (
                f"https://api.github.com/repos/{REPOSITORY}/issues/{PR_NUMBER}"
            ),
            "body": comment_body,
            "author_association": association,
            "created_at": created_at,
            "updated_at": updated_at,
        },
        f"{GRAPHQL_COMMENT_PREFIX}{COMMENT_NODE_ID}": {
            "databaseId": COMMENT_ID,
            "body": comment_body,
            "authorAssociation": association,
            "createdAt": created_at,
            "updatedAt": updated_at,
            "lastEditedAt": last_edited_at,
            "isMinimized": minimized,
            "issue": {
                "number": PR_NUMBER,
                "repository": {"nameWithOwner": REPOSITORY},
            },
        },
        f"/repos/{REPOSITORY}/git/commits/{MERGE_SHA}": {
            "sha": MERGE_SHA,
            "parents": [{"sha": value} for value in parent_shas],
        },
    }
    return responses.__getitem__


def source_run(event_name: str = "issue_comment") -> dict[str, object]:
    return {
        "id": SOURCE_RUN_ID,
        "run_attempt": SOURCE_RUN_ATTEMPT,
        "event": event_name,
        "name": "reviewed-head baseline gate",
        "path": GATE_WORKFLOW_PATH,
        "head_branch": "main",
        "head_sha": POLICY_SHA,
        "status": "completed",
        "conclusion": "success",
        "workflow_id": 123456,
        "repository": {"full_name": REPOSITORY},
        "head_repository": {"full_name": REPOSITORY},
    }


def workflow_run_event(event_name: str = "issue_comment") -> dict[str, object]:
    return {
        "action": "completed",
        "repository": {"full_name": REPOSITORY},
        "workflow_run": source_run(event_name),
    }


def artifact_document(
    name: str,
    artifact_id: int,
    digest_character: str,
    *,
    head_sha: str = POLICY_SHA,
) -> dict[str, object]:
    return {
        "id": artifact_id,
        "name": name,
        "size_in_bytes": 1000 + artifact_id,
        "expired": False,
        "digest": "sha256:" + digest_character * 64,
        "workflow_run": {"id": SOURCE_RUN_ID, "head_sha": head_sha},
    }


def published_artifact_document(
    name: str,
    artifact_id: int,
    digest_character: str,
    *,
    publisher_run_id: int = PUBLISHER_RUN_ID,
) -> dict[str, object]:
    return {
        "id": artifact_id,
        "name": name,
        "size_in_bytes": 2000 + artifact_id,
        "expired": False,
        "digest": "sha256:" + digest_character * 64,
        "workflow_run": {
            "id": publisher_run_id,
            "head_sha": POLICY_SHA,
        },
    }


def publisher_run() -> dict[str, object]:
    return {
        "id": PUBLISHER_RUN_ID,
        "run_attempt": PUBLISHER_RUN_ATTEMPT,
        "event": "workflow_run",
        "name": "evidence-publication",
        "path": PUBLICATION_WORKFLOW_PATH,
        "head_branch": "main",
        "head_sha": POLICY_SHA,
        "status": "in_progress",
        "conclusion": None,
        "workflow_id": 654321,
        "repository": {"full_name": REPOSITORY},
        "head_repository": {"full_name": REPOSITORY},
    }


def source_artifact_documents(
    *,
    extra_name: str | None = None,
    head_sha: str = POLICY_SHA,
) -> list[dict[str, object]]:
    names = [*PROVISIONAL_ARTIFACT_NAMES, PUBLICATION_TICKET_NAME]
    if extra_name is not None:
        names.append(extra_name)
    return [
        artifact_document(
            name,
            index + 1,
            format(index + 1, "x"),
            head_sha=head_sha,
        )
        for index, name in enumerate(names)
    ]


def publication_reader(
    *,
    artifacts: list[dict[str, object]] | None = None,
    revocation: bool = False,
    live_run_mutation: tuple[str, object] | None = None,
    source_event: str = "issue_comment",
    source_branch: str = "main",
    source_sha: str = POLICY_SHA,
):
    base_reader = live_reader()
    run = source_run(source_event)
    run["head_branch"] = source_branch
    run["head_sha"] = source_sha
    if live_run_mutation is not None:
        run[live_run_mutation[0]] = live_run_mutation[1]
    source_artifacts = (
        source_artifact_documents() if artifacts is None else artifacts
    )
    comments: list[dict[str, object]] = []
    if revocation:
        comments.append(
            {
                "id": COMMENT_ID + 1,
                "body": revocation_body(),
                "author_association": "OWNER",
                "created_at": REVOCATION_AT,
            }
        )
    responses: dict[str, object] = {
        f"/repos/{REPOSITORY}/actions/runs/{SOURCE_RUN_ID}": run,
        (
            f"/repos/{REPOSITORY}/actions/runs/{SOURCE_RUN_ID}/artifacts"
            "?per_page=100"
        ): {
            "total_count": len(source_artifacts),
            "artifacts": source_artifacts,
        },
        (
            f"/repos/{REPOSITORY}/issues/{PR_NUMBER}/comments"
            "?per_page=100&page=1"
        ): comments,
    }

    def read(path: str):
        if path in responses:
            return responses[path]
        return base_reader(path)

    return read


def publication_receipt_reader(
    *,
    publisher_run_mutation: tuple[str, object] | None = None,
    artifact_run_id: int = PUBLISHER_RUN_ID,
):
    base_reader = publication_reader()
    live_publisher_run = publisher_run()
    if publisher_run_mutation is not None:
        live_publisher_run[publisher_run_mutation[0]] = publisher_run_mutation[1]
    documents = [
        published_artifact_document(
            name,
            101 + index,
            format(10 + index, "x"),
            publisher_run_id=artifact_run_id,
        )
        for index, name in enumerate(PUBLICATION_ARTIFACT_NAMES)
    ]
    responses: dict[str, object] = {
        f"/repos/{REPOSITORY}/actions/runs/{PUBLISHER_RUN_ID}": (
            live_publisher_run
        ),
        **{
            f"/repos/{REPOSITORY}/actions/artifacts/{document['id']}": document
            for document in documents
        },
    }

    def read(path: str):
        if path in responses:
            return responses[path]
        return base_reader(path)

    return read, documents


def admitted_gate(**reader_options: object):
    return gate_decision(
        "issue_comment",
        issue_comment_event(),
        REPOSITORY,
        POLICY_SHA,
        live_reader(**reader_options),
    )


def decide_call(
    inputs: dict[str, str],
    reader=None,
    workflow_sha=POLICY_SHA,
    workflow_ref=GATE_WORKFLOW_REF,
    event_payload=None,
):
    return decide(
        "issue_comment",
        issue_comment_event() if event_payload is None else event_payload,
        POLICY_SHA,
        workflow_sha,
        workflow_ref,
        REPOSITORY,
        POLICY_SHA,
        inputs,
        live_reader() if reader is None else reader,
    )


class GateDecisionTests(unittest.TestCase):
    def test_created_standing_admission_dispatches_exact_coordinates(self) -> None:
        decision = admitted_gate()
        self.assertTrue(decision.dispatch)
        self.assertEqual(decision.mode, "admit")
        self.assertEqual(decision.pull_request_number, PR_NUMBER)
        self.assertEqual(decision.admission_comment_id, COMMENT_ID)
        self.assertEqual(decision.inputs["reviewed_head_sha"], HEAD_SHA)
        self.assertEqual(decision.inputs["base_sha"], BASE_SHA)
        self.assertEqual(decision.inputs["execution_merge_sha"], MERGE_SHA)
        self.assertEqual(decision.inputs["policy_sha"], POLICY_SHA)

    def test_public_commenter_cannot_enter_shared_dispatch(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(association="CONTRIBUTOR"),
            REPOSITORY,
            POLICY_SHA,
            lambda _: self.fail("public comments must not cause live reads"),
        )
        self.assertFalse(decision.dispatch)
        self.assertEqual(decision.mode, "ignore")

    def test_ordinary_standing_comment_is_ignored(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(body="Looks good, but this is not admission."),
            REPOSITORY,
            POLICY_SHA,
        )
        self.assertFalse(decision.dispatch)

    def test_created_explicit_revocation_dispatches_revocation(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(body=revocation_body()),
            REPOSITORY,
            POLICY_SHA,
            live_reader(),
        )
        self.assertTrue(decision.dispatch)
        self.assertEqual(decision.mode, "revoke")
        self.assertEqual(
            decision.inputs["revocation_reason"],
            "explicit-standing-reviewer-revocation",
        )

    def test_edit_of_admission_is_revocation_only(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(
                action="edited",
                body="Admission text changed.",
                prior_body=admission_body(),
            ),
            REPOSITORY,
            POLICY_SHA,
            live_reader(),
        )
        self.assertTrue(decision.dispatch)
        self.assertEqual(decision.mode, "revoke")
        self.assertEqual(
            decision.inputs["revocation_reason"], "admission-comment-edited"
        )

    def test_deletion_of_admission_is_revocation_only(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(action="deleted", body=admission_body()),
            REPOSITORY,
            POLICY_SHA,
            live_reader(),
        )
        self.assertTrue(decision.dispatch)
        self.assertEqual(decision.mode, "revoke")

    def test_ordinary_edit_is_ignored(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(
                action="edited",
                body="New ordinary text.",
                prior_body="Old ordinary text.",
            ),
            REPOSITORY,
            POLICY_SHA,
            live_reader(),
        )
        self.assertFalse(decision.dispatch)

    def test_old_head_admission_edit_cannot_cancel_newer_work(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(
                action="edited",
                body="Admission text changed.",
                prior_body=admission_body(),
            ),
            REPOSITORY,
            POLICY_SHA,
            live_reader(head_sha=NEXT_SHA),
        )
        self.assertFalse(decision.dispatch)
        self.assertIn("older head", decision.reason)

    def test_pull_request_state_transition_uses_revocation_concurrency(self) -> None:
        decision = gate_decision(
            "pull_request_target",
            pull_request_target_event(),
            REPOSITORY,
            POLICY_SHA,
        )
        self.assertFalse(decision.dispatch)
        self.assertEqual(decision.mode, "state-revocation")
        self.assertEqual(decision.pull_request_number, PR_NUMBER)

    def test_non_pull_request_issue_comment_is_ignored(self) -> None:
        decision = gate_decision(
            "issue_comment",
            issue_comment_event(pull_request=False),
            REPOSITORY,
            POLICY_SHA,
        )
        self.assertFalse(decision.dispatch)


class ExecutorAdmissionTests(unittest.TestCase):
    def test_main_push_is_bound_to_workflow_and_policy_sha(self) -> None:
        event = {
            "ref": "refs/heads/main",
            "after": HEAD_SHA,
            "repository": {"full_name": REPOSITORY},
        }
        admission = decide(
            "push",
            event,
            HEAD_SHA,
            HEAD_SHA,
            CONFORMANCE_WORKFLOW_REF,
            REPOSITORY,
            HEAD_SHA,
        )
        self.assertTrue(admission.eligible)
        self.assertEqual(admission.event_class, "MAIN_PUSH")
        self.assertEqual(admission.execution_merge_sha, HEAD_SHA)

    def test_dispatch_revalidates_live_admission(self) -> None:
        admission = decide_call(admitted_gate().inputs)
        self.assertTrue(admission.eligible)
        self.assertEqual(admission.pull_request_number, PR_NUMBER)
        self.assertEqual(admission.admission_comment_id, COMMENT_ID)
        self.assertEqual(admission.reviewed_head_sha, HEAD_SHA)
        self.assertEqual(admission.execution_merge_sha, MERGE_SHA)

    def test_evidence_binds_body_digest_state_and_update_time(self) -> None:
        evidence = decide_call(admitted_gate().inputs).evidence()
        expected_digest = "sha256:" + hashlib.sha256(
            admission_body().encode("utf-8")
        ).hexdigest()
        self.assertEqual(evidence["schemaVersion"], EVIDENCE_SCHEMA)
        self.assertEqual(evidence["review_body_sha256"], expected_digest)
        self.assertEqual(evidence["review_state"], "ACTIVE_UNEDITED")
        self.assertEqual(evidence["review_updated_at"], CREATED_AT)
        self.assertEqual(evidence["reviewer_association"], "OWNER")

    def test_edited_live_comment_cannot_admit(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "edited comment cannot admit"):
            admitted_gate(last_edited_at="2026-08-26T08:00:00Z")

    def test_closed_pull_request_cannot_admit(self) -> None:
        responses = live_reader()

        def reader(path: str):
            value = responses(path)
            if path == f"/repos/{REPOSITORY}/pulls/{PR_NUMBER}":
                return {**value, "state": "closed"}
            return value

        with self.assertRaisesRegex(AdmissionError, "not open"):
            gate_decision(
                "issue_comment",
                issue_comment_event(),
                REPOSITORY,
                POLICY_SHA,
                reader,
            )

    def test_minimized_live_comment_cannot_admit(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "minimized comment"):
            admitted_gate(minimized=True)

    def test_admission_footer_is_byte_exact(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "gate footer is malformed"):
            gate_decision(
                "issue_comment",
                issue_comment_event(body=admission_body().rstrip() + " "),
                REPOSITORY,
                POLICY_SHA,
                live_reader(body=admission_body().rstrip() + " "),
            )

    def test_new_live_head_invalidates_dispatch(self) -> None:
        inputs = admitted_gate().inputs
        reader = live_reader(head_sha=NEXT_SHA, body=admission_body())
        with self.assertRaisesRegex(AdmissionError, "does not equal the live"):
            decide_call(inputs, reader)

    def test_coordinate_mismatch_invalidates_dispatch(self) -> None:
        inputs = dict(admitted_gate().inputs)
        inputs["execution_merge_sha"] = NEXT_SHA
        with self.assertRaisesRegex(AdmissionError, "differs from the live gate"):
            decide_call(inputs)

    def test_metadata_mismatch_invalidates_dispatch(self) -> None:
        inputs = dict(admitted_gate().inputs)
        inputs["review_metadata"] = (
            '{"association":"OWNER","state":"ACTIVE_UNEDITED",'
            '"updated_at":"2026-08-26T08:00:01Z"}'
        )
        with self.assertRaisesRegex(AdmissionError, "differs from the live gate"):
            decide_call(inputs)

    def test_workflow_sha_must_equal_trusted_policy_sha(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "workflow does not equal"):
            decide_call(admitted_gate().inputs, workflow_sha=NEXT_SHA)

    def test_caller_must_be_the_main_branch_gate(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "trusted main-branch gate"):
            decide_call(admitted_gate().inputs, workflow_ref="untrusted/workflow")

    def test_null_execution_merge_refuses_admission(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "full lowercase commit SHA"):
            admitted_gate(merge_sha=None)

    def test_execution_merge_parents_bind_live_base_and_head(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "parents do not bind"):
            admitted_gate(merge_parents=[BASE_SHA, NEXT_SHA])

    def test_revocation_dispatch_is_cleanly_ineligible(self) -> None:
        revocation = gate_decision(
            "issue_comment",
            issue_comment_event(body=revocation_body()),
            REPOSITORY,
            POLICY_SHA,
            live_reader(),
        )
        admission = decide_call(
            revocation.inputs,
            reader=live_reader(),
            event_payload=issue_comment_event(body=revocation_body()),
        )
        self.assertFalse(admission.eligible)
        self.assertEqual(admission.event_class, "TRUSTED_REVOCATION")
        self.assertEqual(admission.review_state, "REVOKED")

    def test_admission_edit_call_is_cleanly_ineligible(self) -> None:
        event = issue_comment_event(
            action="edited",
            body="Admission text changed.",
            prior_body=admission_body(),
        )
        revocation = gate_decision(
            "issue_comment",
            event,
            REPOSITORY,
            POLICY_SHA,
            live_reader(),
        )
        admission = decide_call(
            revocation.inputs,
            reader=live_reader(),
            event_payload=event,
        )
        self.assertFalse(admission.eligible)
        self.assertEqual(admission.reason, "admission-comment-edited")


class PublicationAdmissionTests(unittest.TestCase):
    def plan(self, *, source_event="issue_comment", artifacts=None):
        lifecycle = source_event == "pull_request_target"
        source_branch = "feature/lifecycle" if lifecycle else "main"
        source_sha = HEAD_SHA if lifecycle else POLICY_SHA
        reader = publication_reader(
            artifacts=artifacts,
            source_event=source_event,
            source_branch=source_branch,
            source_sha=source_sha,
        )
        event = workflow_run_event(source_event)
        event_run = event["workflow_run"]
        assert isinstance(event_run, dict)
        event_run["head_branch"] = source_branch
        event_run["head_sha"] = source_sha
        return _publication_plan(
            event_name="workflow_run",
            event=event,
            github_sha=POLICY_SHA,
            workflow_sha=POLICY_SHA,
            workflow_ref=PUBLICATION_WORKFLOW_REF,
            repository=REPOSITORY,
            policy_sha=POLICY_SHA,
            fetch_json=reader,
        )

    def resolve(self, reader=None):
        live = publication_reader() if reader is None else reader
        source = _publication_source_from_event(
            event_name="workflow_run",
            event=workflow_run_event(),
            github_sha=POLICY_SHA,
            workflow_sha=POLICY_SHA,
            workflow_ref=PUBLICATION_WORKFLOW_REF,
            repository=REPOSITORY,
            policy_sha=POLICY_SHA,
            fetch_json=live,
        )
        artifacts = _artifact_references(
            repository=REPOSITORY,
            source_run_id=SOURCE_RUN_ID,
            source_head_sha=POLICY_SHA,
            expected_names=(*PROVISIONAL_ARTIFACT_NAMES, PUBLICATION_TICKET_NAME),
            fetch_json=live,
        )
        return live, source, artifacts

    def ticket(self, artifacts: dict[str, ArtifactReference]):
        admission = decide_call(admitted_gate().inputs)
        return _publication_ticket_document(
            admission=admission,
            source_run_id=SOURCE_RUN_ID,
            source_run_attempt=SOURCE_RUN_ATTEMPT,
            source_workflow_ref=GATE_WORKFLOW_REF,
            source_workflow_sha=POLICY_SHA,
            provisional_artifacts={
                name: artifacts[name] for name in PROVISIONAL_ARTIFACT_NAMES
            },
        )

    def test_exact_source_run_and_artifact_identities_revalidate_live(self) -> None:
        reader, source, artifacts = self.resolve()
        admission = _validate_publication_ticket(
            ticket=self.ticket(artifacts),
            source=source,
            artifacts=artifacts,
            fetch_json=reader,
        )

        self.assertTrue(admission.eligible)
        self.assertEqual(admission.reviewed_head_sha, HEAD_SHA)
        self.assertEqual(admission.execution_merge_sha, MERGE_SHA)

    def test_ordinary_and_revocation_comments_are_clean_non_publications(self) -> None:
        for comment_kind in ("ordinary", "explicit-revocation"):
            with self.subTest(comment_kind=comment_kind):
                plan = self.plan(artifacts=[])
                self.assertFalse(plan.publish)
                self.assertEqual(plan.artifacts, {})
                self.assertEqual(plan.reason, "gate comment produced no publication")

    def test_pull_request_lifecycle_run_is_a_clean_non_publication(self) -> None:
        plan = self.plan(source_event="pull_request_target", artifacts=[])

        self.assertFalse(plan.publish)
        self.assertEqual(plan.artifacts, {})
        self.assertIn("lifecycle", plan.reason)

    def test_exact_admitted_inventory_is_the_only_gate_publication(self) -> None:
        plan = self.plan(artifacts=source_artifact_documents())

        self.assertTrue(plan.publish)
        self.assertEqual(
            set(plan.artifacts),
            {*PROVISIONAL_ARTIFACT_NAMES, PUBLICATION_TICKET_NAME},
        )

    def test_partial_gate_inventory_still_fails_closed(self) -> None:
        partial = source_artifact_documents()[:-1]

        with self.assertRaisesRegex(AdmissionError, "names are not the exact"):
            self.plan(artifacts=partial)

    def test_pull_request_lifecycle_artifact_is_never_publishable(self) -> None:
        with self.assertRaisesRegex(AdmissionError, "lifecycle.*unexpectedly"):
            self.plan(
                source_event="pull_request_target",
                artifacts=source_artifact_documents(head_sha=HEAD_SHA),
            )

    def test_source_run_rejects_live_identity_change(self) -> None:
        reader = publication_reader(live_run_mutation=("run_attempt", 2))

        with self.assertRaisesRegex(AdmissionError, "run_attempt changed"):
            self.resolve(reader)

    def test_source_run_refuses_attempt_ambiguous_rerun(self) -> None:
        event = workflow_run_event()
        event_run = event["workflow_run"]
        assert isinstance(event_run, dict)
        event_run["run_attempt"] = 2
        reader = publication_reader(live_run_mutation=("run_attempt", 2))

        with self.assertRaisesRegex(AdmissionError, "rerun attempts are ambiguous"):
            _publication_source_from_event(
                event_name="workflow_run",
                event=event,
                github_sha=POLICY_SHA,
                workflow_sha=POLICY_SHA,
                workflow_ref=PUBLICATION_WORKFLOW_REF,
                repository=REPOSITORY,
                policy_sha=POLICY_SHA,
                fetch_json=reader,
            )

    def test_source_inventory_rejects_established_name_pre_squat(self) -> None:
        reader = publication_reader(
            artifacts=source_artifact_documents(extra_name="review-baseline")
        )

        with self.assertRaisesRegex(AdmissionError, "names are not the exact"):
            self.resolve(reader)

    def test_source_inventory_rejects_admitted_index_fabrication(self) -> None:
        reader = publication_reader(
            artifacts=source_artifact_documents(
                extra_name="native-verifier-index-provisional"
            )
        )

        with self.assertRaisesRegex(AdmissionError, "names are not the exact"):
            self.resolve(reader)

    def test_source_inventory_rejects_oversized_untrusted_artifact(self) -> None:
        artifacts = source_artifact_documents()
        artifacts[0]["size_in_bytes"] = 512_000_001
        reader = publication_reader(artifacts=artifacts)

        with self.assertRaisesRegex(AdmissionError, "exceeds its size limit"):
            self.resolve(reader)

    def test_ticket_rejects_changed_provisional_artifact_digest(self) -> None:
        reader, source, artifacts = self.resolve()
        ticket = self.ticket(artifacts)
        ticket_artifacts = ticket["provisionalArtifacts"]
        assert isinstance(ticket_artifacts, list)
        first = ticket_artifacts[0]
        assert isinstance(first, dict)
        first["digest"] = "sha256:" + "f" * 64

        with self.assertRaisesRegex(AdmissionError, "artifact identities differ"):
            _validate_publication_ticket(
                ticket=ticket,
                source=source,
                artifacts=artifacts,
                fetch_json=reader,
            )

    def test_live_standing_revocation_refuses_publication(self) -> None:
        initial_reader, _, initial_artifacts = self.resolve()
        ticket = self.ticket(initial_artifacts)
        reader, source, artifacts = self.resolve(
            publication_reader(revocation=True)
        )
        del initial_reader

        with self.assertRaisesRegex(AdmissionError, "revocation is active"):
            _validate_publication_ticket(
                ticket=ticket,
                source=source,
                artifacts=artifacts,
                fetch_json=reader,
            )

    def test_receipt_binds_source_publisher_and_exact_artifact_identities(
        self,
    ) -> None:
        reader, published = publication_receipt_reader()
        _, source, source_artifacts = self.resolve(reader)
        ticket = self.ticket(source_artifacts)
        admission = _validate_publication_ticket(
            ticket=ticket,
            source=source,
            artifacts=source_artifacts,
            fetch_json=reader,
        )
        candidate = [
            {
                "artifactId": item["id"],
                "digest": str(item["digest"]).removeprefix("sha256:"),
                "name": item["name"],
            }
            for item in published
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(candidate), encoding="utf-8")
            receipt = _publication_receipt_document(
                path=path,
                ticket=ticket,
                admission=admission,
                source=source,
                source_artifacts=source_artifacts,
                publisher_workflow_ref=PUBLICATION_WORKFLOW_REF,
                publisher_workflow_sha=POLICY_SHA,
                publisher_run_id=PUBLISHER_RUN_ID,
                publisher_run_attempt=PUBLISHER_RUN_ATTEMPT,
                fetch_json=reader,
            )

        self.assertEqual(receipt["schemaVersion"], PUBLICATION_RECEIPT_SCHEMA)
        self.assertEqual(receipt["publisher"]["runId"], PUBLISHER_RUN_ID)
        self.assertEqual(
            [item["name"] for item in receipt["artifacts"]],
            list(PUBLICATION_ARTIFACT_NAMES),
        )
        self.assertEqual(
            [item["name"] for item in receipt["source"]["artifacts"]],
            [*PROVISIONAL_ARTIFACT_NAMES, PUBLICATION_TICKET_NAME],
        )

    def test_receipt_rejects_artifact_from_another_publisher_run(self) -> None:
        reader, published = publication_receipt_reader(
            artifact_run_id=PUBLISHER_RUN_ID + 1
        )
        _, source, source_artifacts = self.resolve(reader)
        ticket = self.ticket(source_artifacts)
        admission = _validate_publication_ticket(
            ticket=ticket,
            source=source,
            artifacts=source_artifacts,
            fetch_json=reader,
        )
        candidate = [
            {
                "artifactId": item["id"],
                "digest": item["digest"],
                "name": item["name"],
            }
            for item in published
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(candidate), encoding="utf-8")
            with self.assertRaisesRegex(
                AdmissionError,
                "published artifact live identity differs",
            ):
                _publication_receipt_document(
                    path=path,
                    ticket=ticket,
                    admission=admission,
                    source=source,
                    source_artifacts=source_artifacts,
                    publisher_workflow_ref=PUBLICATION_WORKFLOW_REF,
                    publisher_workflow_sha=POLICY_SHA,
                    publisher_run_id=PUBLISHER_RUN_ID,
                    publisher_run_attempt=PUBLISHER_RUN_ATTEMPT,
                    fetch_json=reader,
                )

    def test_receipt_refuses_attempt_ambiguous_publisher_rerun(self) -> None:
        reader, _ = publication_receipt_reader()
        _, source, source_artifacts = self.resolve(reader)
        ticket = self.ticket(source_artifacts)
        admission = _validate_publication_ticket(
            ticket=ticket,
            source=source,
            artifacts=source_artifacts,
            fetch_json=reader,
        )

        with self.assertRaisesRegex(AdmissionError, "rerun attempts are ambiguous"):
            _publication_receipt_document(
                path=Path("unused-after-attempt-refusal.json"),
                ticket=ticket,
                admission=admission,
                source=source,
                source_artifacts=source_artifacts,
                publisher_workflow_ref=PUBLICATION_WORKFLOW_REF,
                publisher_workflow_sha=POLICY_SHA,
                publisher_run_id=PUBLISHER_RUN_ID,
                publisher_run_attempt=2,
                fetch_json=reader,
            )


class EvidencePublicationPolicyTests(unittest.TestCase):
    def test_trusted_conformance_stage_rebuilds_comparison_and_platform_claims(
        self,
    ) -> None:
        config = review_policy._read_json(review_policy.CONFIG_PATH)
        inventory = review_policy._load_test_inventory(config)
        results = complete_test_results_fixture(config, inventory)
        inventory_check = review_policy._test_inventory_check(
            inventory,
            results["collection"]["collected"],
        )
        warning_check = review_policy._warning_policy_check(
            config["warningPolicy"],
            results["warnings"],
        )
        paths = config["paths"]
        clean_state = {
            "sha": HEAD_SHA,
            "treeSha": "f" * 40,
            "dirty": False,
            "dirtyEntryCount": 0,
            "statusDigest": hashlib.sha256(b"\n").hexdigest(),
        }
        step_names = (
            "package-self-check",
            "pip-check",
            "environment-preflight",
            "verify-pinned-test-inventory",
            "verify-warning-inventory",
            "complete-kernel-tests",
            "verify-generated-manifest",
            "verify-test-store-postgresql",
            "verify-post-run-git-state",
        )

        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            input_root = temporary / "input"
            for index, run in enumerate(("run-1", "run-2"), start=1):
                run_root = input_root / "review-baseline" / run
                run_root.mkdir(parents=True)
                results_path = run_root / "kernel-test-results.json"
                results_path.write_text(
                    json.dumps(results, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                evidence = {
                    "schemaVersion": review_policy.EVIDENCE_SCHEMA,
                    "normalizationPolicy": review_policy._normalization_policy(),
                    "run": {
                        "startedAt": f"2026-08-26T17:00:0{index}Z",
                        "finishedAt": f"2026-08-26T17:01:0{index}Z",
                        "canonicalCommand": config["canonicalCommand"],
                        "outcome": "passed",
                    },
                    "git": {
                        "start": clean_state,
                        "end": clean_state,
                        "unchanged": True,
                    },
                    "inputs": {
                        "config": {
                            "path": "conformance/review_baseline_config.json",
                            "sha256": review_policy._sha256_file(
                                review_policy.CONFIG_PATH
                            ),
                        },
                        "dependencyLock": {
                            "path": paths["dependencyLock"],
                            "sha256": review_policy._sha256_file(
                                review_policy.ROOT / paths["dependencyLock"]
                            ),
                        },
                        "packageManagerLock": {
                            "path": paths["packageManagerLock"],
                            "sha256": review_policy._sha256_file(
                                review_policy.ROOT / paths["packageManagerLock"]
                            ),
                        },
                        "testInventory": {
                            "path": paths["testInventory"],
                            "sha256": review_policy._sha256_file(
                                review_policy.ROOT / paths["testInventory"]
                            ),
                            "entriesSha256": inventory["entriesSha256"],
                            "entryCount": inventory["entryCount"],
                        },
                        "schema": {
                            "path": paths["schema"],
                            "sha256": review_policy._sha256_file(
                                review_policy.ROOT / paths["schema"]
                            ),
                        },
                    },
                    "environment": complete_environment_fixture(config),
                    "tests": results,
                    "testAcceptance": {
                        "inventory": inventory_check,
                        "warnings": warning_check,
                    },
                    "steps": [
                        {
                            "name": name,
                            "command": [f"internal:{name}"],
                            "outcome": "passed",
                            "exitCode": 0,
                        }
                        for name in step_names
                    ],
                    "producedArtifacts": [
                        {
                            "path": results_path.name,
                            "sha256": hashlib.sha256(
                                results_path.read_bytes()
                            ).hexdigest(),
                            "bytes": results_path.stat().st_size,
                        }
                    ],
                    "producedArtifactsNote": (
                        "The evidence envelope excludes its own digest to avoid "
                        "recursive self-reference. Its raw digest is recorded by "
                        "the comparison proof."
                    ),
                    "verifiedArtifacts": [
                        {
                            "path": path,
                            "sha256": review_policy._sha256_file(
                                review_policy.ROOT / path
                            ),
                        }
                        for path in config["verifiedArtifacts"]
                    ],
                }
                (run_root / "review-baseline-evidence.json").write_text(
                    json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            comparison = input_root / "review-baseline/equivalence.json"
            self.assertEqual(
                review_policy.compare_evidence(
                    str(
                        input_root
                        / "review-baseline/run-1/review-baseline-evidence.json"
                    ),
                    str(
                        input_root
                        / "review-baseline/run-2/review-baseline-evidence.json"
                    ),
                    str(comparison),
                ),
                0,
            )
            platform_results = [
                {
                    "test": entry["nodeid"],
                    "outcome": "passed",
                    "durationSeconds": 0.0,
                }
                for entry in inventory["entries"]
                if entry["sourcePath"] == "kernel/tests/test_conformance.py"
            ]
            platform_root = input_root / "platform-evidence"
            platform_root.mkdir()
            (platform_root / "platform_mvp_results_2026-08-26T170000Z.json").write_text(
                json.dumps(
                    {
                        "suite": (
                            "conformance:ofarm2.platform-mvp."
                            "tests-1-15-plus-regressions.v0_2"
                        ),
                        "executed": True,
                        "executedAt": "2026-08-26T17:00:00Z",
                        "runtimeVersion": "fixture",
                        "exitStatus": 0,
                        "allPassed": True,
                        "results": platform_results,
                        "details": {"producerOnly": True},
                        "honestyNote": "fixture",
                    }
                ),
                encoding="utf-8",
            )

            output_root = temporary / "authoritative"
            stage_conformance_evidence(
                input_root=input_root,
                output_root=output_root,
                source_commit=HEAD_SHA,
                source_run_id=SOURCE_RUN_ID,
                source_run_attempt=SOURCE_RUN_ATTEMPT,
            )

            published_platform = json.loads(
                (
                    output_root
                    / "platform-evidence"
                    / PLATFORM_PUBLICATION_FILE
                ).read_text(encoding="utf-8")
            )
            self.assertNotIn("details", published_platform)
            self.assertNotIn("durationSeconds", published_platform["results"][0])
            self.assertEqual(published_platform["source"]["commit"], HEAD_SHA)

    def test_installed_artifact_tar_preserves_exact_files_and_modes(self) -> None:
        native_policy = _native_policy_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "installed.tar"
            with tarfile.open(archive_path, "w", format=tarfile.USTAR_FORMAT) as archive:
                for name, (_maximum, mode) in native_policy.ARTIFACT_CONTRACTS.items():
                    data = f"artifact-{name}\n".encode()
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    member.mode = int(mode, 8)
                    member.uid = member.gid = member.mtime = 0
                    archive.addfile(member, io.BytesIO(data))

            output = root / "installed"
            _extract_installed_artifacts(archive_path, output, native_policy)

            self.assertEqual(
                {path.name for path in output.iterdir()},
                set(native_policy.ARTIFACT_CONTRACTS),
            )
            self.assertEqual(stat.S_IMODE((output / "ofarm_ed25519.so").stat().st_mode), 0o755)

    def test_installed_artifact_tar_refuses_path_and_mode_tampering(self) -> None:
        native_policy = _native_policy_module()
        cases = (("../libsodium.a", "0644"), ("libsodium.a", "0777"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (hostile_name, hostile_mode) in enumerate(cases):
                archive_path = root / f"hostile-{index}.tar"
                with tarfile.open(
                    archive_path,
                    "w",
                    format=tarfile.USTAR_FORMAT,
                ) as archive:
                    for name, (_maximum, mode) in native_policy.ARTIFACT_CONTRACTS.items():
                        data = b"artifact\n"
                        member = tarfile.TarInfo(
                            hostile_name if name == "libsodium.a" else name
                        )
                        member.size = len(data)
                        member.mode = int(
                            hostile_mode if name == "libsodium.a" else mode,
                            8,
                        )
                        member.uid = member.gid = member.mtime = 0
                        archive.addfile(member, io.BytesIO(data))
                with self.subTest(hostile_name=hostile_name, mode=hostile_mode):
                    with self.assertRaises(PublicationPolicyError):
                        _extract_installed_artifacts(
                            archive_path,
                            root / f"output-{index}",
                            native_policy,
                        )

    def test_produced_artifact_digest_and_size_bind_actual_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / "kernel-test-results.json"
            results.write_bytes(b'{"schemaVersion":"example"}\n')
            binding = [
                {
                    "path": results.name,
                    "sha256": hashlib.sha256(results.read_bytes()).hexdigest(),
                    "bytes": results.stat().st_size,
                }
            ]
            _validate_produced_artifact_binding(binding, results)
            binding[0]["sha256"] = "0" * 64
            with self.assertRaisesRegex(PublicationPolicyError, "binding differs"):
                _validate_produced_artifact_binding(binding, results)

    def test_trusted_result_validator_requires_complete_pinned_passes(self) -> None:
        results, inventory, warning_policy = passing_test_results_fixture()

        inventory_check, warning_check = _validate_test_results(
            results,
            expected_inventory=inventory,
            warning_policy=warning_policy,
        )

        self.assertTrue(inventory_check["matches"])
        self.assertTrue(warning_check["matches"])

    def test_trusted_result_validator_refuses_claim_tampering(self) -> None:
        mutations = {
            "missing-outcome": lambda value: value["execution"]["outcomes"].clear(),
            "changed-inventory": lambda value: value["collection"]["selected"][0].update(
                nodeid="kernel/tests/test_example.py::test_fabricated"
            ),
            "warning": lambda value: value["warnings"].append(
                {"nodeid": "", "when": "collect", "category": "Warning", "message": "hidden"}
            ),
            "extra-field": lambda value: value.update(fabricated=True),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                results, inventory, warning_policy = passing_test_results_fixture()
                mutate(results)
                with self.assertRaises(PublicationPolicyError):
                    _validate_test_results(
                        results,
                        expected_inventory=inventory,
                        warning_policy=warning_policy,
                    )

    def test_secure_download_verifies_digest_and_extracts_inside_fresh_root(
        self,
    ) -> None:
        payload = artifact_zip({"nested/evidence.json": b'{"ok":true}\n'})
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        captured: list[object] = []

        def response_factory(request):
            captured.append(request)
            return FakeArtifactResponse(payload)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fresh-artifact"
            download_and_extract_artifact(
                api_url="https://api.github.com",
                repository=REPOSITORY,
                artifact_name="conformance-provisional",
                artifact_id=123,
                expected_digest=digest,
                output_directory=root,
                token="test-token",
                response_factory=response_factory,
            )
            self.assertEqual(
                (root / "nested/evidence.json").read_bytes(),
                b'{"ok":true}\n',
            )
            self.assertFalse((root / ".ofarm-artifact.zip").exists())
            self.assertEqual(len(captured), 1)
            request = captured[0]
            self.assertEqual(
                request.full_url,
                "https://api.github.com/repos/samovers/OFARM2/"
                "actions/artifacts/123/zip",
            )
            self.assertEqual(
                request.get_header("Authorization"),
                "Bearer test-token",
            )
            redirected = _HttpsOnlyRedirectHandler().redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://artifact-results.example.test/signed.zip",
            )
            self.assertIsNotNone(redirected)
            self.assertIsNone(redirected.get_header("Authorization"))
            with self.assertRaisesRegex(PublicationPolicyError, "not HTTPS"):
                _HttpsOnlyRedirectHandler().redirect_request(
                    request,
                    None,
                    302,
                    "Found",
                    {},
                    "http://artifact-results.example.test/unsafe.zip",
                )

    def test_secure_download_refuses_digest_mismatch_and_unsafe_entries(self) -> None:
        clean = artifact_zip({"evidence.json": b"evidence"})
        cases = {
            "digest": (clean, "sha256:" + "0" * 64),
            "traversal": (
                artifact_zip({"../escaped.json": b"hostile"}),
                None,
            ),
            "absolute": (
                artifact_zip({"/absolute.json": b"hostile"}),
                None,
            ),
            "duplicate": (
                artifact_zip({}, duplicate="evidence.json"),
                None,
            ),
            "symlink": (
                artifact_zip({}, symlink="evidence-link"),
                None,
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for name, (payload, expected) in cases.items():
                with self.subTest(name=name):
                    digest = expected or (
                        "sha256:" + hashlib.sha256(payload).hexdigest()
                    )
                    with self.assertRaises(PublicationPolicyError):
                        download_and_extract_artifact(
                            api_url="https://api.github.com",
                            repository=REPOSITORY,
                            artifact_name="conformance-provisional",
                            artifact_id=123,
                            expected_digest=digest,
                            output_directory=temporary / name,
                            token="test-token",
                            response_factory=lambda _request, body=payload: (
                                FakeArtifactResponse(body)
                            ),
                        )
                    self.assertFalse((temporary / "escaped.json").exists())

    def test_conformance_inventory_is_exact_before_and_after_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "provisional"
            write_inventory(
                root / "review-baseline",
                REVIEW_BASELINE_FILES,
            )
            platform_name = "platform_mvp_results_2026-08-26T170000Z.json"
            write_inventory(root / "platform-evidence", {platform_name})
            self.assertEqual(
                validate_conformance_inventory(root, authoritative=False),
                platform_name,
            )

            extra = root / "review-baseline/run-3/attacker.json"
            extra.parent.mkdir()
            extra.write_bytes(b"hostile")
            with self.assertRaisesRegex(PublicationPolicyError, "not exact"):
                validate_conformance_inventory(root, authoritative=False)
            extra.unlink()
            authoritative = Path(directory) / "authoritative"
            write_inventory(
                authoritative / "review-baseline",
                REVIEW_BASELINE_FILES | TRUSTED_METADATA_FILES,
            )
            write_inventory(
                authoritative / "platform-evidence",
                {PLATFORM_PUBLICATION_FILE} | TRUSTED_METADATA_FILES,
            )
            self.assertEqual(
                validate_conformance_inventory(authoritative, authoritative=True),
                PLATFORM_PUBLICATION_FILE,
            )

    def test_native_inventory_is_exact_before_and_after_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "provisional"
            write_inventory(root, NATIVE_EVIDENCE_FILES)
            validate_native_inventory(root, authoritative=False)
            extra = root / "native_evidence_receipt.json"
            extra.write_bytes(b"hostile")
            with self.assertRaisesRegex(PublicationPolicyError, "not exact"):
                validate_native_inventory(root, authoritative=False)
            extra.unlink()
            authoritative = Path(directory) / "authoritative"
            write_inventory(
                authoritative,
                NATIVE_AUTHORITATIVE_FILES | TRUSTED_METADATA_FILES,
            )
            validate_native_inventory(authoritative, authoritative=True)

    def test_native_claims_bind_both_installed_file_sets(self) -> None:
        contracts = (
            ("libsodium.a", "0644"),
            ("ofarm_ed25519.so", "0755"),
            ("ofarm_ed25519.control", "0644"),
            ("ofarm_ed25519--1.0.sql", "0644"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identities = []
            for name, mode in contracts:
                data = f"trusted-{name}\n".encode()
                for build in ("first", "second"):
                    path = root / build / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    path.chmod(int(mode, 8))
                identities.append(
                    {
                        "name": name,
                        "mode": mode,
                        "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
                        "size": len(data),
                    }
                )
            (root / "reproducibility.json").write_text(
                json.dumps(
                    {
                        "schema": "ofarm.native-reproducibility-evidence.v1",
                        "platform": "linux/amd64",
                        "source_commit": HEAD_SHA,
                        "child_digest": "sha256:" + "1" * 64,
                        "config_digest": "sha256:" + "2" * 64,
                        "artifacts": identities,
                    }
                ),
                encoding="utf-8",
            )

            validate_native_claims(
                root,
                platform="linux/amd64",
                source_commit=HEAD_SHA,
            )
            (root / "second/ofarm_ed25519.so").write_bytes(b"fabricated")
            (root / "second/ofarm_ed25519.so").chmod(0o755)
            with self.assertRaisesRegex(PublicationPolicyError, "files differ"):
                validate_native_claims(
                    root,
                    platform="linux/amd64",
                    source_commit=HEAD_SHA,
                )

    def test_admission_and_extraction_size_limits_are_one_contract(self) -> None:
        self.assertEqual(
            {
                name: SOURCE_ARTIFACT_MAX_BYTES[name]
                for name in PROVISIONAL_ARTIFACT_LIMITS
            },
            PROVISIONAL_ARTIFACT_LIMITS,
        )


class WorkflowPolicyTests(unittest.TestCase):
    def test_default_branch_gate_never_checks_out_pull_request_code(self) -> None:
        workflow = Path(".github/workflows/review-baseline-gate.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("  issue_comment:\n", workflow)
        self.assertIn("  pull_request_target:\n", workflow)
        self.assertIn("ref: ${{ github.workflow_sha }}", workflow)
        self.assertIn("uses: ./.github/workflows/conformance.yml", workflow)
        execute = workflow.split("\n  execute:\n", 1)[1]
        self.assertIn(
            "group: ofarm-pr-${{ needs.gate.outputs.pull_request_number }}",
            execute,
        )
        self.assertIn("cancel-in-progress: true", execute)
        self.assertIn("ofarm-gate-comment-", workflow)
        self.assertIn("ofarm-pr-{0}", workflow)
        self.assertNotIn("actions: write", workflow)
        self.assertNotIn("/dispatches", workflow)
        self.assertNotIn("github.event.pull_request.head", workflow)
        self.assertNotIn("github.head_ref", workflow)

    def test_executor_has_only_trusted_dispatch_and_main_triggers(self) -> None:
        workflow = Path(".github/workflows/conformance.yml").read_text(
            encoding="utf-8"
        )
        trigger = workflow.split("permissions: {}", 1)[0]
        self.assertIn("  push:\n", trigger)
        self.assertIn("  workflow_call:\n", trigger)
        self.assertNotIn("pull_request_target", trigger)
        self.assertNotIn("pull_request_review", trigger)
        self.assertNotIn("workflow_dispatch", trigger)
        inputs = trigger.split("    inputs:\n", 1)[1]
        names = re.findall(r"^      ([a-z0-9_]+):$", inputs, re.MULTILINE)
        self.assertEqual(len(names), 10)
        self.assertIn("review_metadata", names)
        self.assertIn(
            "OFARM_BASELINE_ADMISSION_POLICY_SHA: ${{ github.workflow_sha }}",
            workflow,
        )

    def test_untrusted_jobs_upload_only_provisional_artifacts(self) -> None:
        source_workflow = Path(".github/workflows/conformance.yml").read_text(
            encoding="utf-8"
        )
        producers = {
            "conformance": "name: conformance-provisional\n",
            "native-verifier": (
                "name: native-verifier-${{ matrix.architecture }}-provisional\n"
            ),
        }
        authoritative_names = (
            "name: review-baseline\n",
            "name: platform-mvp-evidence\n",
            "name: native-verifier-amd64\n",
            "name: native-verifier-arm64\n",
            "name: native-verifier-index\n",
            "name: evidence-publication-receipt\n",
        )
        for job_name, provisional_name in producers.items():
            section = workflow_job_section(source_workflow, job_name)
            self.assertIn(provisional_name, section)
            for authoritative_name in authoritative_names:
                self.assertNotIn(authoritative_name, section)

        self.assertNotIn("\n  native-verifier-index:\n", source_workflow)
        self.assertNotIn("compose-index", source_workflow)
        self.assertNotIn("prepare-release-identity", source_workflow)
        handoff = workflow_job_section(source_workflow, "publication-handoff")
        self.assertIn(
            "needs: [baseline-admission, conformance, native-verifier]",
            handoff,
        )
        self.assertIn("--operation handoff", handoff)
        self.assertIn("name: evidence-publication-ticket\n", handoff)
        self.assertNotIn(
            "ref: ${{ needs.baseline-admission.outputs.execution_merge_sha }}",
            handoff,
        )
        self.assertIn("git -C .publication-policy diff --exit-code", handoff)
        self.assertIn("--porcelain=v1 --untracked-files=all", handoff)
        self.assertEqual(handoff.count("actions/upload-artifact@"), 1)
        native = workflow_job_section(source_workflow, "native-verifier")
        for archive in ("first-image.docker.tar", "second-image.docker.tar"):
            self.assertIn(archive, native)
        self.assertNotIn(
            'rm -- \\\n+            ".artifacts/native/${{ matrix.architecture }}/first-image.docker.tar"',
            native,
        )

    def test_cross_run_publisher_never_executes_admitted_code(self) -> None:
        workflow = Path(".github/workflows/evidence-publication.yml").read_text(
            encoding="utf-8"
        )
        trigger = workflow.split("permissions: {}", 1)[0]
        self.assertIn("  workflow_run:\n", trigger)
        self.assertIn("      - conformance\n", trigger)
        self.assertIn("      - reviewed-head baseline gate\n", trigger)
        self.assertNotIn("workflow_dispatch", trigger)
        self.assertNotIn("pull_request", trigger)
        self.assertNotIn("push:", trigger)
        self.assertEqual(
            workflow.count("Refuse attempt-ambiguous publisher reruns"),
            2,
        )
        self.assertEqual(workflow.count('test "$GITHUB_RUN_ATTEMPT" = 1'), 2)
        for variable, value in (
            ("GIT_CONFIG_GLOBAL", "/dev/null"),
            ("GIT_CONFIG_SYSTEM", "/dev/null"),
            ("GIT_CONFIG_NOSYSTEM", '"1"'),
            ("GIT_CONFIG_KEY_0", "core.hooksPath"),
            ("GIT_CONFIG_KEY_1", "core.fsmonitor"),
        ):
            self.assertIn(f"  {variable}: {value}\n", workflow)

        source_admission = workflow_job_section(workflow, "source-admission")
        publisher = workflow_job_section(workflow, "publish")
        self.assertIn("publish: ${{ steps.resolve-source.outputs.publish }}", source_admission)
        self.assertEqual(
            source_admission.count("if: steps.resolve-source.outputs.publish == 'true'"),
            4,
        )
        self.assertIn("needs.source-admission.outputs.publish == 'true'", publisher)
        for section in (source_admission, publisher):
            self.assertIn("runs-on: ubuntu-24.04", section)
            self.assertIn(
                "ref: ${{ env.OFARM_PUBLICATION_POLICY_SHA }}",
                section,
            )
            self.assertNotIn("actions/setup-python", section)
            self.assertNotIn("GITHUB_PATH", section)
            self.assertNotIn("GITHUB_ENV", section)
            self.assertNotIn("uses: ./", section)
            self.assertNotIn(
                "ref: ${{ steps.publisher-start.outputs.execution_merge_sha }}",
                section,
            )
            self.assertIn("set-safe-directory: false", section)
            self.assertIn("git -C .publication-policy diff --exit-code", section)
            self.assertIn("--porcelain=v1 --untracked-files=all", section)

        downloads = workflow.split("uses: actions/download-artifact@")[1:]
        self.assertEqual(len(downloads), 4)
        for download in downloads:
            step = download.split("\n      - ", 1)[0]
            self.assertIn("artifact-ids:", step)
            self.assertIn("github-token:", step)
            self.assertIn("repository:", step)
            self.assertIn("run-id:", step)
            self.assertNotIn("ofarm-publication-input", step)

        self.assertEqual(
            publisher.count(
                ".publication-policy/conformance/"
                "evidence_publication_policy.py\n          download"
            ),
            3,
        )
        for artifact_name in PROVISIONAL_ARTIFACT_NAMES:
            self.assertIn(f"--artifact-name {artifact_name}", publisher)
        self.assertIn("--artifact-digest", publisher)
        self.assertIn("validate-conformance", publisher)
        self.assertIn("validate-native", publisher)
        self.assertIn("stage-conformance", publisher)
        self.assertIn("stage-native", publisher)
        self.assertIn("validate-native-claims", publisher)
        self.assertIn("ofarm-publication-stage", publisher)
        self.assertIn("Require exact authoritative file inventories", publisher)
        self.assertIn("--authoritative", publisher)

        self.assertEqual(publisher.count("collect-oci"), 1)
        self.assertIn("compose-index", publisher)
        self.assertIn("prepare-release-identity", publisher)
        self.assertIn(
            "steps.upload-native-amd64.outputs.artifact-id",
            publisher,
        )
        self.assertIn(
            "steps.upload-native-arm64.outputs.artifact-id",
            publisher,
        )
        self.assertIn("--published-artifacts-input", publisher)
        self.assertIn("--publication-receipt-output", publisher)
        self.assertIn("--publisher-run-id", publisher)
        self.assertIn("--publisher-run-attempt", publisher)
        self.assertIn(
            "group: ${{ needs.source-admission.outputs."
            "publication_concurrency_group }}",
            publisher,
        )

    def test_authoritative_names_belong_only_to_cross_run_publisher(self) -> None:
        source_workflow = Path(".github/workflows/conformance.yml").read_text(
            encoding="utf-8"
        )
        publication_workflow = Path(
            ".github/workflows/evidence-publication.yml"
        ).read_text(
            encoding="utf-8"
        )
        authoritative_names = (
            "review-baseline",
            "platform-mvp-evidence",
            "native-verifier-amd64",
            "native-verifier-arm64",
            "native-verifier-index",
            "evidence-publication-receipt",
        )
        for artifact_name in authoritative_names:
            source_matches = re.findall(
                rf"^\s+name: {re.escape(artifact_name)}$",
                source_workflow,
                re.MULTILINE,
            )
            publisher_matches = re.findall(
                rf"^\s+name: {re.escape(artifact_name)}$",
                publication_workflow,
                re.MULTILINE,
            )
            self.assertEqual(source_matches, [])
            self.assertEqual(len(publisher_matches), 1)

        self.assertEqual(
            source_workflow.count("name: conformance-provisional\n"),
            1,
        )
        self.assertEqual(
            source_workflow.count(
                "name: native-verifier-${{ matrix.architecture }}-provisional\n"
            ),
            1,
        )
        self.assertEqual(
            source_workflow.count("name: evidence-publication-ticket\n"),
            1,
        )
        receipt_position = publication_workflow.index(
            "name: evidence-publication-receipt\n"
        )
        for name in authoritative_names[:-1]:
            self.assertLess(
                publication_workflow.index(f"name: {name}\n"),
                receipt_position,
            )


if __name__ == "__main__":
    unittest.main()
