"""Retired-history checks using fictional recorded artifacts and real Git bundles.

The tiny artifacts are historical-integrity fixtures, not executed conformance
or provider evidence. No deleted live path or archived executable runs here.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
import zipfile

import pytest

from conformance import ci_policy_transition_audit as audit
from conformance import ci_policy_transition_operator as operator
from conformance.test_ci_policy_transition_operator import _write_root_archive

ROOT = Path(__file__).resolve().parents[1]


def _write_zip(path, files):
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def _chain(f, events):
    records = []
    previous = None
    for sequence, (event, data) in enumerate(events):
        body = dict(
            sequence=sequence, previous=previous, event=event, data=copy.deepcopy(data)
        )
        previous = operator._digest(operator._canonical(body))
        records.append({**body, "digest": previous})
    f["journal"].write_bytes(b"".join(operator._canonical(r) + b"\n" for r in records))
    f["checkpoint"].write_bytes(
        operator._canonical(
            {
                "schemaVersion": "ofarm.ci-transition-checkpoint.v1",
                "genesis": records[0]["digest"],
                "sequence": len(records) - 1,
                "tail": previous,
            }
        )
        + b"\n"
    )
    f["events"] = copy.deepcopy(events)
    f["genesis"] = records[0]["digest"]


def _projection(grant):
    p = {
        "schemaVersion": "ofarm.ci-policy-transition-original-authority.v1",
        "threadId": grant["decision"]["threadId"],
    }
    for index, (prefix, key, pr) in enumerate(
        [
            ("decision", "decision", 417),
            ("consumer", "consumerDecision", grant["consumerPr"]),
        ]
    ):
        d = grant[key]
        p[prefix + "Card"] = {
            "id": d["cardRef"],
            "order": index * 2,
            "role": "assistant",
            "text": f"Fictional {d['id']} version {d['version']} card for #{pr}.",
        }
        p[prefix + "Approval"] = {
            "id": d["approvalRef"],
            "order": index * 2 + 1,
            "role": "user",
            "text": f"I approve OFARM2 decision {d['id']} version {d['version']}.",
        }
    packet = (
        "Fictional historical packet "
        + json.dumps(grant, sort_keys=True)
        + " "
        + audit.digest(grant)
    )
    p["activationPacket"] = {
        "id": "fictional-packet",
        "order": 4,
        "role": "assistant",
        "text": packet,
    }
    p["activationApproval"] = {
        "id": "fictional-grant-message",
        "order": 5,
        "role": "user",
        "text": f"I authorize OFARM2 CI transition grant {grant['grantId']} under packet {audit.digest(packet.encode())} "
        f"using root {grant['rootSha']} for PR #{grant['consumerPr']} at head {grant['headSha']}, "
        f"base {grant['baseSha']} and merge {grant['mergeSha']}, until {grant['expiresAt']}, "
        "for one source and one publisher, attempt 1 only. Merge remains separate.",
    }
    return p


@pytest.fixture
def history(tmp_path):
    repo = tmp_path / "fictional-old-root"
    repo.mkdir()

    def git(*args):
        return operator._git(repo, *args).decode().strip()

    git("init", "--quiet")
    git("config", "user.name", "Fictional history fixture")
    git("config", "user.email", "fixture@example.invalid")
    for name, text in {
        "ordinary.py": "VALUE = 1\n",
        "config.json": "{}\n",
        "pins.lock": "fixture\n",
        "ordinary.yml": "name: ordinary\n",
    }.items():
        (repo / name).write_text(text)
    git("add", "--all")
    git("commit", "--quiet", "-m", "Fictional historical base")
    base = git("rev-parse", "HEAD")
    (repo / "history.py").write_text(
        'raise AssertionError("archived code must never execute")\n'
    )
    (repo / "test_history.py").write_text("import history\n")
    (repo / "generated.yml").write_text("name: fictional old transition\n")
    git("add", "--all")
    git("commit", "--quiet", "-m", "Fictional historical root")
    root = git("rev-parse", "HEAD")
    spec = {
        "entrypoints": ["history.py"],
        "inputs": {
            "configuration": ["config.json"],
            "pins": ["pins.lock"],
            "generatedInputs": ["ordinary.yml"],
            "generatedWorkflows": ["generated.yml"],
            "tests": ["test_history.py"],
        },
        "dependencies": {},
        "allowedChangedPaths": [],
    }
    closure = operator._reconstruct_policy_closure(repo, root, base, spec)
    coordinates = dict(
        rootSha=root,
        rootTree=closure["rootTree"],
        closureDigest=operator.policy_closure_digest(closure),
        coverageDigest="sha256:" + "8" * 64,
        baseSha=base,
        consumerPr=411,
        headSha="5" * 40,
        mergeSha="6" * 40,
    )
    f = {
        "repo": repo,
        "archive": tmp_path / "accepted",
        "roots": tmp_path / "roots",
        "journal": tmp_path / "journal/grant.jsonl",
        "checkpoint": tmp_path / "checkpoint/tail.json",
    }
    for p in (
        f["archive"] / "archives",
        f["roots"],
        f["journal"].parent,
        f["checkpoint"].parent,
    ):
        p.mkdir(parents=True)
    f["journal"].with_name("grant.jsonl.lock").touch()
    genesis = (
        "GENESIS",
        {
            "schemaVersion": "ofarm.ci-transition-journal.v1",
            "grantId": "fictional-consumed",
            "coordinates": {**coordinates, "repository": "fictional/history"},
        },
    )
    _chain(f, [genesis])
    grant = {
        **coordinates,
        "grantId": "fictional-consumed",
        "repository": "fictional/history",
        "expiresAt": "2026-10-20T00:00:00Z",
        "journal": {"genesisDigest": f["genesis"]},
        "decision": {
            "id": "FICTIONAL-TRANSITION",
            "version": 4,
            "threadId": "fictional-task",
            "cardRef": "fictional-root-card",
            "approvalRef": "fictional-root-approval",
        },
        "consumerDecision": {
            "id": "FICTIONAL-CONSUMER",
            "version": 2,
            "cardRef": "fictional-consumer-card",
            "approvalRef": "fictional-consumer-approval",
        },
    }
    source, published = [], []
    for index, name in enumerate([*audit.SOURCE_NAMES, *audit.PUBLISHED_NAMES], 101):
        path = f["archive"] / "archives" / f"{index}.zip"
        _write_zip(path, {"fictional-history.txt": name.encode()})
        ref = {
            "name": name,
            "artifactId": index,
            "digest": operator._digest(path.read_bytes()),
            "size": path.stat().st_size,
            "runId": 201 if name in audit.SOURCE_NAMES else 202,
            "headSha": root,
        }
        (source if name in audit.SOURCE_NAMES else published).append(ref)
    receipt = {
        "schemaVersion": audit.RECEIPT_SCHEMA,
        "authority": {
            "grantId": grant["grantId"],
            **coordinates,
            "grantDigest": audit.digest(grant),
        },
        "source": {"runId": 201, "runAttempt": 1, "artifacts": source},
        "publisher": {"runId": 202, "runAttempt": 1},
        "artifacts": published,
    }
    receipt_path = f["archive"] / "archives/110.zip"
    _write_zip(receipt_path, {audit.RECEIPT_FILE: json.dumps(receipt)})
    consumed = {
        "grantId": grant["grantId"],
        **coordinates,
        "sourceRunId": 201,
        "sourceRunAttempt": 1,
        "publisherRunId": 202,
        "publisherRunAttempt": 1,
        "ticketArtifactId": source[-1]["artifactId"],
        "ticketDigest": source[-1]["digest"],
        "receiptArtifactId": 110,
        "receiptDigest": operator._digest(receipt_path.read_bytes()),
    }
    events = [
        genesis,
        (
            "APPROVED",
            {
                "grantDigest": audit.digest(grant),
                "authorityRefs": {
                    k: "fictional-" + k
                    for k in ("task", "card", "approval", "packet", "grant")
                },
            },
        ),
    ]
    for index, role in enumerate(("admission", "source", "publisher")):
        if role != "admission":
            push = {
                "ref": f"refs/heads/ofarm-ci-transition/{role}/{grant['grantId']}",
                "sha": root,
                "previous": None,
            }
            events += [
                ("INTENT", {"action": role + "_push", "expected": push}),
                ("RECONCILED", {"action": role + "_push", "identity": push}),
                (
                    "RUN_BOUND",
                    {
                        "stage": role,
                        "identity": {
                            "runId": 201 if role == "source" else 202,
                            "runAttempt": 1,
                        },
                    },
                ),
            ]
        action = "admission" if role == "admission" else role + "_binding"
        body = {"bodyDigest": "sha256:" + str(index + 1) * 64}
        events += [
            ("INTENT", {"action": action, "expected": body}),
            (
                "RECONCILED",
                {"action": action, "identity": {**body, "commentId": 301 + index}},
            ),
        ]
        if role == "source":
            events.append(
                (
                    "SOURCE_PASSED",
                    {
                        "artifactId": consumed["ticketArtifactId"],
                        "digest": consumed["ticketDigest"],
                    },
                )
            )
    events += [
        ("SEALED", {"artifactId": 110, "digest": consumed["receiptDigest"]}),
        ("ACCEPTED", consumed),
        (
            "RETIRED",
            {
                "nativeMerge": {
                    "consumerPr": 411,
                    "headSha": coordinates["headSha"],
                    "mergeCommit": "e" * 40,
                }
            },
        ),
    ]
    _chain(f, events)
    report = {
        "purpose": "fictional recorded acceptance",
        "tuple": consumed,
        "closure": closure,
        "grant": grant,
        "originalAuthority": _projection(grant),
    }
    (f["archive"] / "acceptance.json").write_text(json.dumps(report))
    manifest = _write_root_archive(
        repo,
        [{k: coordinates[k] for k in ("rootSha", "rootTree", "baseSha")}],
        f["roots"],
    )
    f.update(report=report, receipt=receipt, manifest=manifest, consumed=consumed)
    return f


def _audit(f, **kwargs):
    with operator.ConsumedJournal(
        f["journal"], f["checkpoint"], f["genesis"]
    ) as journal:
        return audit.audit_consumed(
            journal=journal,
            archive_directory=f["archive"],
            roots_directory=f["roots"],
            root_manifest=f["manifest"],
            **kwargs,
        )


def _rebind_receipt(f):
    path = f["archive"] / "archives/110.zip"
    _write_zip(path, {audit.RECEIPT_FILE: json.dumps(f["receipt"])})
    _rebind_receipt_archive(f)


def _rebind_receipt_archive(f):
    path = f["archive"] / "archives/110.zip"
    digest = operator._digest(path.read_bytes())
    for event, value in f["events"]:
        if event == "SEALED":
            value["digest"] = digest
        elif event == "ACCEPTED":
            value["receiptDigest"] = digest
    f["report"]["tuple"]["receiptDigest"] = digest
    (f["archive"] / "acceptance.json").write_text(json.dumps(f["report"]))
    _chain(f, f["events"])


def test_complete_historical_audit_never_grants_authority_or_executes_archived_code(
    history,
):
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for root in (
            history["journal"].parent,
            history["checkpoint"].parent,
            history["archive"],
            history["roots"],
        )
        for p in root.rglob("*")
        if p.is_file()
    }
    result = _audit(history)
    assert result["archiveIntegrity"] and result["rootArchive"]["closureIntegrity"]
    assert result["tuple"] == history["consumed"]
    assert result["purpose"] == "audit-consumed"
    assert all(
        result[k] is False
        for k in ("executionAuthority", "liveAcceptanceAuthority", "mergeAuthority")
    )
    assert all(x["status"] == "unavailable" for x in result["providerFacts"])
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}
    assert not any("history" == name for name in sys.modules)


@pytest.mark.parametrize(
    "state",
    [
        "GENESIS",
        "APPROVED",
        "SOURCE_RESERVED",
        "SOURCE_BOUND",
        "SOURCE_PASSED",
        "PUBLISHER_RESERVED",
        "PUBLISHER_BOUND",
        "SEALED",
        "ACCEPTED",
        "FAILED",
    ],
)
def test_unconsumed_or_failed_history_cannot_audit_as_accepted(history, state):
    events = history["events"]
    if state == "FAILED":
        events = events[:2] + [("FAILED", {"reason": "fictional failed grant"})]
    else:
        event_names = {
            "SOURCE_RESERVED": ("INTENT", "source_push"),
            "PUBLISHER_RESERVED": ("INTENT", "publisher_push"),
            "SOURCE_BOUND": ("RECONCILED", "source_binding"),
            "PUBLISHER_BOUND": ("RECONCILED", "publisher_binding"),
        }
        if state in event_names:
            name, action = event_names[state]
            index = next(
                i
                for i, (event, data) in enumerate(events)
                if event == name and data.get("action") == action
            )
        else:
            index = next(i for i, (event, _) in enumerate(events) if event == state)
        events = events[: index + 1]
    _chain(history, events)
    with pytest.raises(
        audit.TransitionAuditError, match="requires consumed acceptance"
    ):
        _audit(history)


@pytest.mark.parametrize(
    "fault",
    [
        "torn",
        "hash",
        "checkpoint",
        "missing-journal",
        "missing-checkpoint",
        "missing-lock",
        "symlink",
    ],
)
def test_damaged_or_missing_independent_journal_refuses(history, fault):
    if fault == "torn":
        history["journal"].write_bytes(history["journal"].read_bytes()[:-1])
    elif fault == "hash":
        history["journal"].write_bytes(
            history["journal"]
            .read_bytes()
            .replace(b"fictional-card", b"fictional-care")
        )
    elif fault == "checkpoint":
        history["checkpoint"].write_bytes(b"{}\n")
    elif fault.startswith("missing-"):
        p = {
            "missing-journal": history["journal"],
            "missing-checkpoint": history["checkpoint"],
            "missing-lock": history["journal"].with_name("grant.jsonl.lock"),
        }[fault]
        p.unlink()
    else:
        original = history["journal"].with_name("original")
        history["journal"].rename(original)
        history["journal"].symlink_to(original)
    with pytest.raises(operator.OperatorError):
        _audit(history)


@pytest.mark.parametrize(
    "fault,match",
    [
        ("run-attempt", "first run attempt"),
        ("order", "acceptance differs"),
        ("native-merge", "differs from the consumed consumer"),
        ("after-retired", "terminal journal"),
    ],
)
def test_rechained_semantically_invalid_history_refuses(history, fault, match):
    events = history["events"]
    if fault == "run-attempt":
        next(data for event, data in events if event == "RUN_BOUND")["identity"][
            "runAttempt"
        ] = 2
    elif fault == "order":
        events[-3], events[-2] = events[-2], events[-3]
    elif fault == "native-merge":
        events[-1][1]["nativeMerge"]["headSha"] = "f" * 40
    else:
        events.append(("APPROVED", events[1][1]))
    _chain(history, events)
    with pytest.raises(operator.OperatorError, match="journal unavailable") as raised:
        _audit(history)
    assert match in str(raised.value.__cause__)


@pytest.mark.parametrize(
    "fault,match",
    [
        ("tuple", "acceptance differs"),
        ("closure", "closure differs"),
        ("grant", "grant differs"),
        ("original-message", "original exact-root activation approval differs"),
    ],
)
def test_changed_acceptance_record_refuses(history, fault, match):
    report = history["report"]
    if fault == "tuple":
        report["tuple"]["headSha"] = "f" * 40
    elif fault == "closure":
        report["closure"]["fullTreeDigest"] = "sha256:" + "f" * 64
    elif fault == "grant":
        report["grant"]["expiresAt"] = "2099-01-01T00:00:00Z"
    else:
        report["originalAuthority"]["activationApproval"]["text"] += " altered"
    (history["archive"] / "acceptance.json").write_text(json.dumps(report))
    with pytest.raises(audit.TransitionAuditError, match=match):
        _audit(history)


@pytest.mark.parametrize(
    "fault,match",
    [
        ("authority", "receipt authority differs"),
        ("run", "run tuple differs"),
        ("attempt", "run tuple differs"),
        ("inventory", "inventories are incomplete"),
        ("ticket", "ticket differs"),
    ],
)
def test_receipt_semantics_are_checked_even_with_matching_archive_digest(
    history, fault, match
):
    receipt = history["receipt"]
    if fault == "authority":
        receipt["authority"]["rootSha"] = "f" * 40
    elif fault == "run":
        receipt["publisher"]["runId"] = 999
    elif fault == "attempt":
        receipt["publisher"]["runAttempt"] = 2
    elif fault == "inventory":
        receipt["artifacts"].pop()
    else:
        receipt["source"]["artifacts"][-1]["digest"] = "sha256:" + "f" * 64
    _rebind_receipt(history)
    with pytest.raises(audit.TransitionAuditError, match=match):
        _audit(history)


@pytest.mark.parametrize(
    "fault,match",
    [
        ("corrupt-artifact", "historical artifact digest differs"),
        ("missing-artifact", "raw archive inventory is not exact"),
        ("extra-artifact", "raw archive inventory is not exact"),
        ("symlink-artifact", "inventory contains a symlink"),
        ("corrupt-receipt", "receipt archive digest differs"),
        ("corrupt-bundle", "root bundle digest differs"),
        ("wrong-bundle-root", "consumed root is absent"),
    ],
)
def test_raw_archive_inventory_digests_and_root_bundle_refuse_corruption(
    history, fault, match
):
    archives = history["archive"] / "archives"
    if fault == "corrupt-artifact":
        payload = (archives / "101.zip").read_bytes()
        (archives / "101.zip").write_bytes(bytes([payload[0] ^ 1]) + payload[1:])
    elif fault == "missing-artifact":
        (archives / "101.zip").unlink()
    elif fault == "extra-artifact":
        (archives / "999.zip").write_bytes(b"extra")
    elif fault == "symlink-artifact":
        (archives / "101.zip").unlink()
        (archives / "101.zip").symlink_to(archives / "102.zip")
    elif fault == "corrupt-receipt":
        (archives / "110.zip").write_bytes(b"corrupt")
    elif fault == "corrupt-bundle":
        with (history["roots"] / "policy-roots.bundle").open("ab") as f:
            f.write(b"corrupt")
    else:
        history["manifest"]["roots"][0]["rootTree"] = "f" * 40
    with pytest.raises(
        (
            audit.TransitionAuditError,
            operator.OperatorError,
            audit.evidence.PublicationPolicyError,
        ),
        match=match,
    ):
        _audit(history)


@pytest.mark.parametrize("provider", ["valid", "missing", "mismatch"])
def test_optional_provider_observation_is_separate_from_historical_integrity(
    history, provider
):
    refs = {
        r["artifactId"]: r
        for r in [
            *history["receipt"]["source"]["artifacts"],
            *history["receipt"]["artifacts"],
        ]
    }

    def reader(path):
        if provider == "missing":
            raise OSError("fictional unavailable provider")
        ref = refs[int(path.rsplit("/", 1)[1])]
        return {
            "id": ref["artifactId"],
            "name": ref["name"],
            "digest": ref["digest"],
            "size_in_bytes": ref["size"],
            "expired": False,
            "workflow_run": {
                "id": ref["runId"] if provider == "valid" else 999,
                "head_sha": ref["headSha"],
            },
        }

    result = _audit(history, provider_reader=reader)
    expected = {
        "valid": "reauthenticated",
        "missing": "unavailable",
        "mismatch": "mismatch",
    }[provider]
    assert all(x["status"] == expected for x in result["providerFacts"])
    assert result["archiveIntegrity"] and not result["liveAcceptanceAuthority"]


def test_journal_reader_has_no_creation_or_mutation_api(history):
    with operator.ConsumedJournal(
        history["journal"], history["checkpoint"], history["genesis"]
    ) as journal:
        for name in (
            "create",
            "approve",
            "intent",
            "reconcile",
            "bind_run",
            "source_passed",
            "seal",
            "accept",
            "retire",
            "fail",
            "_append",
        ):
            assert not hasattr(journal, name)
        journal.snapshot()
        history["checkpoint"].unlink()
        with pytest.raises(operator.OperatorError):
            journal.snapshot()


@pytest.mark.parametrize(
    "operation",
    [
        "download",
        "stage-conformance",
        "verify-for-acceptance",
        "source-gate",
        "publisher-gate",
        "prepare",
    ],
)
def test_deleted_live_cli_operations_refuse_without_credentials_or_provider_work(
    operation,
):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "conformance/ci_policy_transition_audit.py"),
            "--operation",
            operation,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert (
        result.returncode == 2
        and "invalid choice" in result.stderr
        and not result.stdout
    )


def test_cli_historical_audit_works_offline_and_is_read_only(history):
    args = [
        "--operation",
        "audit-consumed",
        "--journal",
        str(history["journal"]),
        "--checkpoint",
        str(history["checkpoint"]),
        "--journal-genesis",
        history["genesis"],
        "--archive-directory",
        str(history["archive"]),
        "--roots-directory",
        str(history["roots"]),
        "--roots-manifest",
        str(history["roots"] / "policy-roots.json"),
    ]
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "conformance/ci_policy_transition_audit.py"),
            *args,
        ],
        text=True,
        capture_output=True,
        check=False,
        env={k: v for k, v in os.environ.items() if "TOKEN" not in k},
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert (
        report["purpose"] == "audit-consumed"
        and not report["mergeAuthority"]
        and not report["executionAuthority"]
    )


def test_current_tree_contains_only_historical_transition_entrypoints():
    assert {
        p.name
        for p in (ROOT / "conformance").glob("ci_policy_transition*")
        if p.is_file()
    } == {"ci_policy_transition_audit.py", "ci_policy_transition_operator.py"}
    assert not list((ROOT / ".github/workflows").glob("ci-policy-transition-*.yml"))


def test_recorded_campaign_contains_only_terminal_named_consumers():
    campaign = json.loads(
        (
            ROOT / "conformance/fixtures/ci_policy_transition/retired_campaign.json"
        ).read_text()
    )
    assert campaign["purpose"] == "historical-navigation-only"
    assert campaign["installedMain"] == "bf85f9721302ef74a33a92280ae8d498950510bf"
    assert campaign["fixedSunset"] == "2026-10-24T00:00:00Z"
    assert [x["consumerPr"] for x in campaign["consumers"]] == [413, 411]
    assert len(campaign["failedGrants"]) == 8
    grants = campaign["consumers"] + campaign["failedGrants"]
    assert len({x["grantId"] for x in grants}) == 10
    assert all(x["state"] in ("FAILED", "RETIRED") for x in grants)
    for consumer in campaign["consumers"]:
        consumed = consumer["consumedTuple"]
        assert consumer["state"] == "RETIRED"
        assert consumed["consumerPr"] == consumer["consumerPr"]
        assert consumed["grantId"] == consumer["grantId"]
        assert consumed["headSha"] == consumer["nativeMerge"]["headSha"]
        assert consumed["sourceRunAttempt"] == consumed["publisherRunAttempt"] == 1
        assert consumed["sourceRunId"] != consumed["publisherRunId"]
    assert (
        campaign["consumers"][1]["consumedTuple"]["baseSha"]
        == campaign["consumers"][0]["nativeMerge"]["mergeCommit"]
    )
    assert all(
        campaign[k] is False
        for k in ("executionAuthority", "liveAcceptanceAuthority", "mergeAuthority")
    )


@pytest.mark.parametrize(
    "fault,match",
    [
        ("traversal", "archive entry path is unsafe"),
        ("symlink", "not a regular file or directory"),
        ("duplicate", "entry is duplicated"),
        ("extra", "archive inventory is not exact"),
        ("expanded", "expanded size exceeds"),
    ],
)
def test_receipt_extraction_refuses_hostile_zip_even_with_recorded_digest(
    history, fault, match
):
    path = history["archive"] / "archives/110.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if fault == "traversal":
            archive.writestr("../escape", "fictional")
        elif fault == "symlink":
            entry = zipfile.ZipInfo(audit.RECEIPT_FILE)
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(entry, "../escape")
        elif fault == "expanded":
            archive.writestr(
                audit.RECEIPT_FILE, b"x" * (audit.LIMITS[audit.RECEIPT_NAME] + 1)
            )
        else:
            archive.writestr(audit.RECEIPT_FILE, json.dumps(history["receipt"]))
            if fault == "duplicate":
                with pytest.warns(UserWarning, match="Duplicate name"):
                    archive.writestr(audit.RECEIPT_FILE, "{}")
            else:
                archive.writestr("extra", "fictional")
    _rebind_receipt_archive(history)
    with pytest.raises(
        (audit.TransitionAuditError, audit.evidence.PublicationPolicyError), match=match
    ):
        _audit(history)
