"""Fictional complete pipeline reaches actual external and historical verifiers.

The selected T is a real isolated Git checkout, and the journal uses its actual
durable format. Local provider responses and authority messages are fictional.
No substantive validator, closure result or journal decision is substituted.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
import importlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
from unittest import mock

import pytest

from conformance import ci_policy_transition as transition
from conformance import ci_policy_transition_operator as operator
from conformance import ci_policy_transition_prepare as preparation
from conformance import ci_policy_transition_publication as publication
from conformance import ci_policy_transition_workflows as workflows
from conformance import test_ci_policy_transition as core_fixture
from conformance import test_ci_policy_transition_integration as pipeline
from conformance import test_ci_policy_transition_publication as artifacts

ROOT = Path(__file__).resolve().parents[1]


def selected_root(directory):
    repository = directory / "selected-T"
    repository.mkdir(parents=True)
    archive = operator._git(ROOT, "archive", workflows.TRUSTED_BASE)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(repository, filter="data")
    # Build a fictional B before adding T. The real provisional identity
    # factories allow tiny genuine OCI fixtures through unchanged validators.
    # These fixture identities are never written to the production checkout.
    fixture_authority = artifacts._trusted_fixture_authority(directory / "fictional-native-authority")
    for name in ("native_release_identity.json", "native_evidence_receipt.json"):
        relative = Path("deployment/postgresql/ofarm_ed25519") / name
        shutil.copyfile(fixture_authority / relative, repository / relative)
    operator._git(repository, "init", "--quiet")
    operator._git(repository, "config", "user.name", "Fictional transition fixture")
    operator._git(repository, "config", "user.email", "fixture@example.invalid")
    operator._git(repository, "add", "--all")
    operator._git(repository, "commit", "--quiet", "-m", "Fictional trusted B")
    base = operator._git(repository, "rev-parse", "HEAD").decode().strip()
    files = sorted((ROOT / "conformance").glob("ci_policy_transition*"))
    files += sorted((ROOT / "conformance").glob("test_ci_policy_transition*.py"))
    files.append(ROOT / "kernel/tests/test_ci_policy_transition.py")
    for source in files:
        if source.is_file():
            target = repository / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    generated = workflows.generate((repository / workflows.SOURCE_INPUT).read_bytes(),
        (repository / workflows.PUBLICATION_INPUT).read_bytes(), consumer_pr=413,
        policy_root=repository)
    for path, content in ((workflows.SOURCE_OUTPUT, generated.source),
                          (workflows.PUBLICATION_OUTPUT, generated.publication)):
        (repository / path).write_bytes(content)
    policy, grant = core_fixture.policy_and_grant()
    policy["repository"]["name"] = artifacts.baseline_fixture.REPOSITORY
    policy["baseSha"] = base
    policy["closure"] = preparation.closure_spec(repository)
    (repository / transition.ROOT_FILE).write_bytes(transition.canonical_json(policy))
    operator._git(repository, "add", "--all")
    operator._git(repository, "commit", "--quiet", "-m", "Fictional complete selected T")
    root = operator._git(repository, "rev-parse", "HEAD").decode().strip()
    closure = operator.create_policy_closure(repository, root, base, policy["closure"])
    grant.update(repository=policy["repository"]["name"], baseSha=base,
        rootSha=root, rootTree=closure["rootTree"], closureDigest=operator.policy_closure_digest(closure))
    return repository, policy, grant, closure


def original_projection(grant):
    result = {"schemaVersion": "ofarm.ci-policy-transition-original-authority.v1",
              "threadId": grant["decision"]["threadId"]}
    for index, prefix in enumerate(("decision", "consumer")):
        decision = grant["decision" if prefix == "decision" else "consumerDecision"]
        result[prefix+"Card"] = {"id": decision["cardRef"], "order": index*2,
            "role": "assistant", "text": f"Fictional card {decision['id']} version {decision['version']} for #{417 if prefix == 'decision' else 413}."}
        result[prefix+"Approval"] = {"id": decision["approvalRef"], "order": index*2+1,
            "role": "user", "text": f"I approve OFARM2 decision {decision['id']} version {decision['version']}."}
    packet = "Fictional local exact-root packet " + json.dumps(grant, sort_keys=True) + " " + transition.digest(grant)
    result["activationPacket"] = {"id": "fictional-packet", "order": 4, "role": "assistant", "text": packet}
    result["activationApproval"] = {"id": "fictional-activation", "order": 5, "role": "user",
        "text": transition.activation_approval_text(grant, transition.digest(packet.encode()))}
    return result


def sealed_pipeline(directory, *, selected=None):
    repository, policy, grant, closure = selected if selected is not None else selected_root(directory)
    journal_path, checkpoint = directory / "journal/grant.jsonl", directory / "checkpoint/tail.json"
    journal_path.parent.mkdir()
    checkpoint.parent.mkdir()
    coordinates = {key: grant[key] for key in operator._COORDINATES}
    coordinates["repository"] = grant["repository"]
    genesis = operator.TransitionJournal.create(journal_path, checkpoint, grant["grantId"],
        coordinates, candidate_roots=(repository,))
    grant["journal"]["genesisDigest"] = genesis
    provider = pipeline.PipelineProvider(policy=policy, grant=grant)
    provider, chain, operations = pipeline.run_pipeline(directory / "pipeline", provider=provider,
        policy_root=repository)
    projection = original_projection(grant)
    journal = operator.TransitionJournal(journal_path, checkpoint, genesis, candidate_roots=(repository,))
    with journal:
        journal.approve(transition.digest(grant), {key: "fictional-"+key
            for key in ("task", "card", "approval", "packet", "grant")})
        for role, index in (("admission", 0), ("source", 1), ("publisher", 2)):
            if role != "admission":
                push = {"ref": grant[role+"Ref"], "sha": grant["rootSha"], "previous": None}
                journal.intent(role+"_push", push)
                journal.reconcile(role+"_push", [push])
                journal.bind_run(role, {"runId": 201 if role == "source" else 202, "runAttempt": 1})
            identity = provider.identity(provider.comments[index])
            action = "admission" if role == "admission" else role+"_binding"
            intent = {"bodyDigest": identity["digest"]}
            journal.intent(action, intent)
            journal.reconcile(action, [{**intent, "commentId": identity["id"]}])
            if role == "source":
                ref = chain["source_refs"][-1]
                journal.source_passed({"artifactId": ref["artifactId"], "digest": ref["digest"]})
        journal.seal({"artifactId": chain["receipt_ref"]["artifactId"], "digest": chain["receipt_ref"]["digest"]})
    return dict(repository=repository, policy=policy, grant=grant, closure=closure,
        provider=provider, chain=chain, operations=operations, projection=projection,
        journal=journal, directory=directory)


def verify(fixture):
    f = fixture
    with mock.patch.object(transition, "utcnow", lambda: f["provider"].now):
        return publication.verify_for_acceptance(policy=f["policy"], grant=f["grant"],
            reader=f["provider"].reader("external-acceptance"), checkout=f["repository"],
            closure=f["closure"], expected_root=f["grant"]["rootSha"],
            expected_closure=f["grant"]["closureDigest"], authority_projection=f["projection"],
            journal=f["journal"], output=f["directory"] / "accepted-archive")


@contextmanager
def selected_modules(repository):
    """Import actual selected-T code with an isolated repository module cache."""
    def owned(name, module):
        if name.split(".")[0] in {"conformance", "kernel", "deployment", "tooling"}:
            return True
        source = getattr(module, "__file__", None)
        return source is not None and any(Path(source).resolve().is_relative_to(root)
            for root in (ROOT, repository.resolve()))

    prior = {name: module for name, module in tuple(sys.modules.items()) if owned(name, module)}
    prior_path = list(sys.path)
    try:
        for name in prior:
            del sys.modules[name]
        sys.path.insert(0, str(repository))
        importlib.invalidate_caches()
        from conformance import test_ci_policy_transition_acceptance as selected
        assert Path(selected.publication.__file__).resolve().is_relative_to(repository.resolve())
        yield selected
    finally:
        for name, module in tuple(sys.modules.items()):
            if owned(name, module):
                del sys.modules[name]
        sys.modules.update(prior)
        sys.path[:] = prior_path
        importlib.invalidate_caches()


@pytest.fixture
def selected_pipeline(tmp_path):
    coordinates = selected_root(tmp_path)
    with selected_modules(coordinates[0]) as selected:
        yield selected, selected.sealed_pipeline(tmp_path, selected=coordinates)


def test_complete_selected_root_pipeline_external_acceptance_and_retired_audit(tmp_path, selected_pipeline):
    selected, f = selected_pipeline
    with f["journal"]:
        report = selected.verify(f)
        assert report["newlyAccepted"] is True
        assert report["substantiveValidation"] == "passed"
        assert report["receipt"]["coverage"] == transition.coverage.declaration()
        assert report["nativeMergeAuthorized"] is False
        measurements = {job: {"used": reader.budget.used, "transport": reader.budget._snapshot("transport")}
            for job, reader in f["provider"].readers.items()}
        (tmp_path / "measured-api.json").write_bytes(transition.canonical_json({
            "purpose": "fictional-provider real-validator measurement; no hosted authority",
            "root": f["grant"]["rootSha"], "coverageDigest": f["grant"]["coverageDigest"],
            "jobs": measurements, "observations": f["provider"].observations,
            "replayedToolPrimary": f["provider"].tool_replays,
            "replayedToolTransport": f["provider"].tool_replay_transports}))
        f["journal"].retire({"consumerPr": 413, "headSha": f["grant"]["headSha"], "mergeCommit": "a"*40})
        roots = tmp_path / "roots"
        roots.mkdir()
        manifest = selected.operator.archive_policy_roots(f["repository"], [{"rootSha": f["grant"]["rootSha"],
            "rootTree": f["grant"]["rootTree"], "baseSha": f["grant"]["baseSha"]}], roots,
            candidate_roots=(f["repository"],))
        audit = selected.publication.audit_consumed(journal=f["journal"], archive_directory=tmp_path / "accepted-archive",
            roots_directory=roots, root_manifest=manifest)
        assert audit["archiveIntegrity"] is True
        assert not any(audit[key] for key in ("liveAcceptanceAuthority", "executionAuthority", "mergeAuthority"))
    reader = f["provider"].readers["external-acceptance"]
    assert sum(value[0] for value in reader.budget.used.values()) <= 56


@pytest.mark.parametrize("fault", ["low-quota", "coverage", "original-approval", "journal-receipt"])
def test_external_acceptance_refuses_without_consuming_a_false_positive(tmp_path, selected_pipeline, fault):
    selected, f = selected_pipeline
    if fault == "low-quota":
        # Background consumption is a fresh provider fact, not attributed here.
        real_window = f["provider"]._window
        real_window()
        background = f["provider"].rest_remaining-f["provider"].rest-100
        assert background > 0
        def low_window():
            real_window()
            f["provider"].rest_remaining -= background
        f["provider"]._window = low_window
    elif fault == "coverage":
        f["grant"] = copy.deepcopy(f["grant"])
        f["grant"]["coverageDigest"] = "sha256:" + "0"*64
    elif fault == "original-approval":
        f["projection"]["decisionApproval"]["text"] = "Go"
    else:
        f["chain"]["receipt_ref"]["digest"] = "sha256:" + "0"*64
    with f["journal"]:
        expected = {"low-quota": "insufficient current-window primary quota", "coverage": "coverage",
            "original-approval": "approval", "journal-receipt": "journal ticket or receipt"}[fault]
        with pytest.raises((selected.transition.TransitionError, selected.publication.TransitionPublicationError,
                            selected.operator.OperatorError), match=expected):
            selected.verify(f)
        assert f["journal"].snapshot()["state"] == "FAILED"
        assert not (tmp_path / "accepted-archive/acceptance.json").exists()


def test_external_acceptance_refuses_a_verifier_running_from_another_root(tmp_path, selected_pipeline):
    selected, f = selected_pipeline
    before = copy.deepcopy(f["provider"].observations)
    with f["journal"]:
        with pytest.raises(publication.TransitionPublicationError, match="execute from the selected policy checkout"):
            verify(f)
        assert f["journal"].snapshot()["state"] == "FAILED"
    assert f["provider"].observations == before
    assert not (tmp_path / "accepted-archive").exists()


@pytest.mark.parametrize("fault", ["foreign-import", "changed-source"])
def test_selected_verifier_binds_its_actual_imports_and_bytes(tmp_path, fault):
    repository, _, _, closure = selected_root(tmp_path)
    with selected_modules(repository) as selected:
        if fault == "foreign-import":
            with mock.patch.object(selected.publication, "evidence", publication.evidence):
                with pytest.raises(selected.publication.TransitionPublicationError, match="outside the selected"):
                    selected.publication._require_selected_execution(repository, closure)
        else:
            path = repository / "conformance/ci_policy_transition_publication.py"
            path.write_bytes(path.read_bytes() + b"\n# Stale executing source fixture.\n")
            with pytest.raises(selected.publication.TransitionPublicationError, match="bytes differ"):
                selected.publication._require_selected_execution(repository, closure)
