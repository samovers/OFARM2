"""Complete fictional artifacts reach the unchanged substantive validators."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import shutil
import tarfile
import zipfile
from pathlib import Path
from unittest import mock

import pytest

from conformance import ci_policy_transition_publication as publication
from conformance import evidence_publication_policy as evidence
from conformance import test_review_baseline_admission as baseline_fixture
from deployment.postgresql import native_release_identity
from kernel.tests import test_postgresql_native_evidence as native_fixture

ROOT = Path(__file__).resolve().parents[1]


def _live():
    source = {"runId": baseline_fixture.SOURCE_RUN_ID, "runAttempt": 1,
        "workflowRef": "samovers/OFARM2/.github/workflows/ci-policy-transition-source.yml@refs/heads/ofarm-ci-transition/source/test-grant",
        "workflowSha": "e" * 40, "eventName": "push",
        "workflowPath": ".github/workflows/ci-policy-transition-source.yml", "workflowName": "CI policy transition source"}
    publisher = {**source, "runId": baseline_fixture.PUBLISHER_RUN_ID,
        "workflowRef": source["workflowRef"].replace("source", "publisher"),
        "workflowPath": source["workflowPath"].replace("source", "publisher"),
        "workflowName": "CI policy transition publisher"}
    return {"rootSha": "e" * 40, "rootTree": "f" * 40, "closureDigest": "sha256:" + "1" * 64,
        "coverageDigest": publication.coverage.coverage_digest(),
        "baseSha": "c" * 40, "headSha": "b" * 40, "mergeSha": baseline_fixture.HEAD_SHA,
        "consumerPr": 413, "grantId": "test-grant", "grantDigest": "sha256:" + "2" * 64,
        "admission": {"id": 10, "digest": "sha256:" + "3" * 64},
        "sourceBinding": {"id": 11, "digest": "sha256:" + "4" * 64},
        "publisherBinding": {"id": 12, "digest": "sha256:" + "5" * 64},
        "source": source, "publisher": publisher,
        "admissionEvidence": {"event_class": "CI_POLICY_TRANSITION", "execution_merge_sha": baseline_fixture.HEAD_SHA}}


def _zip(root: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(evidence._regular_file_inventory(root)):
            archive.writestr(name, (root / name).read_bytes())
    return buffer.getvalue()


def _reference(name: str, artifact_id: int, payload: bytes, run_id: int, root_sha="e" * 40) -> dict:
    return {"name": name, "artifactId": artifact_id,
        "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "size": len(payload), "runId": run_id, "headSha": root_sha}


def _provider(ref):
    return {"name": ref["name"], "id": ref["artifactId"], "digest": ref["digest"],
        "size_in_bytes": ref["size"], "expired": False,
        "workflow_run": {"id": ref["runId"], "head_sha": ref["headSha"]}}


def _native_provisional(directory: Path, architecture: str) -> Path:
    directory.mkdir(parents=True)
    platform = "linux/" + architecture
    builder = f"https://github.com/{baseline_fixture.REPOSITORY}/actions/runs/{baseline_fixture.SOURCE_RUN_ID}/attempts/1"
    # Only fictional fixture coordinates change. No substantive validator is replaced.
    with mock.patch.object(native_fixture, "SOURCE_COMMIT", baseline_fixture.HEAD_SHA), \
            mock.patch.object(native_fixture, "BUILDER_ID", builder):
        archive, child, config, containerfile = native_fixture._oci_fixture(directory, platform=platform)
        repro = native_fixture._reproducibility_fixture(directory, child, config, platform=platform)
    provisional = directory / "provisional"
    provisional.mkdir()
    for source, name in ((archive, "ofarm-ed25519.oci.tar"), (repro, "reproducibility.json"),
        (directory / "first-clean.docker.tar", "first-image.docker.tar"),
        (directory / "second-clean.docker.tar", "second-image.docker.tar")):
        shutil.copyfile(source, provisional / name)
    for build in ("first", "second"):
        with tarfile.open(provisional / f"{build}-artifacts.tar", "w", format=tarfile.USTAR_FORMAT) as installed:
            for name, payload in native_fixture.ARTIFACTS.items():
                member = tarfile.TarInfo(name)
                member.size = len(payload)
                member.mode = 0o755 if name == "ofarm_ed25519.so" else 0o644
                member.uid = member.gid = member.mtime = 0
                installed.addfile(member, io.BytesIO(payload))
    evidence._native_policy_module().collect_oci_evidence(
        archive_path=provisional / "ofarm-ed25519.oci.tar",
        reproducibility_path=provisional / "reproducibility.json", platform=platform,
        source_commit=baseline_fixture.HEAD_SHA, containerfile_path=containerfile,
        builder_id=builder, output_directory=provisional / "attestations")
    for name in ("address.log", "attested-metadata.json", "buildx-version.txt",
                 "invalid-sanitizer.log", "undefined.log"):
        (provisional / name).write_text(f"fictional diagnostic {name}\n")
    return provisional


def _trusted_fixture_authority(directory: Path) -> Path:
    """A complete fictional provisional root uses the actual authority validators."""
    native_root = directory / "deployment/postgresql/ofarm_ed25519"
    native_root.mkdir(parents=True)
    for name in native_release_identity.NATIVE_SOURCE_PATHS:
        shutil.copyfile(native_release_identity.SOURCE_DIRECTORY / name, native_root / name)
    for name in native_release_identity.EVIDENCE_AUTHORITY_PATHS:
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    document = native_release_identity.provisional_identity_document(native_root)
    payload = native_release_identity.canonical_json_bytes(document)
    identity = native_release_identity.validate_native_release_identity(
        document, canonical_bytes=payload, source_directory=native_root)
    (native_root / "native_release_identity.json").write_bytes(payload)
    receipt = native_release_identity.provisional_evidence_receipt_document(
        release_identity=identity, repository_root=directory)
    (native_root / "native_evidence_receipt.json").write_bytes(
        native_release_identity.canonical_json_bytes(receipt))
    return directory


def _complete_chain(tmp_path: Path, *, live=None, policy_root=None, ticket_created=None):
    fixture = baseline_fixture.EvidencePublicationPolicyTests()
    _, conformance, graph = fixture._complete_conformance_fixture(tmp_path)
    inputs = {"conformance-provisional": conformance}
    for architecture in ("amd64", "arm64"):
        inputs[f"native-verifier-{architecture}-provisional"] = _native_provisional(
            tmp_path / architecture, architecture)
    live = live or _live()
    payloads = {}
    source_refs = []
    for artifact_id, name in enumerate(publication.PROVISIONAL_NAMES, start=100):
        payload = _zip(inputs[name])
        payloads[artifact_id] = payload
        source_refs.append(_reference(name, artifact_id, payload, live["source"]["runId"], live["rootSha"]))
    ticket = publication.ticket_document(live, source_refs)
    ticket_root = tmp_path / "ticket"
    ticket_root.mkdir()
    (ticket_root / publication.TICKET_FILE).write_bytes(publication._canonical(ticket))
    payloads[103] = _zip(ticket_root)
    source_refs.append(_reference(publication.TICKET_NAME, 103, payloads[103], live["source"]["runId"], live["rootSha"]))
    if ticket_created is not None:
        live = ticket_created(source_refs, ticket)
    policy = policy_root or _trusted_fixture_authority(tmp_path / "trusted")
    staged = publication.reconstruct_source(inputs=inputs, output=tmp_path / "staged",
        repository=baseline_fixture.REPOSITORY, merge_sha=live["mergeSha"],
        source_run_id=live["source"]["runId"], token="fictional-token",
        source_response_factory=graph.response, policy_root=policy)
    assert len(graph.requests) == 12  # The original authenticated Git reader, no cache assumption.
    context = publication.publication_context(source=live["source"], publisher=live["publisher"],
                                              source_artifacts=source_refs)
    published = {}
    published_refs = []
    for artifact_id, name in enumerate(publication.PUBLISHED_NAMES[:-1], start=200):
        root = tmp_path / "published" / name
        shutil.copytree(staged[name], root)
        for filename, value in (("evidence-publication-context.json", context),
                                ("review-baseline-admission.json", live["admissionEvidence"])):
            (root / filename).write_bytes(publication._canonical(value))
        payloads[artifact_id] = _zip(root)
        published_refs.append(_reference(name, artifact_id, payloads[artifact_id], live["publisher"]["runId"], live["rootSha"]))
        published[name] = root
    index = tmp_path / "published/native-verifier-index"
    index.mkdir()
    native = evidence._native_policy_module()
    native.compose_multi_platform_index(
        amd64_evidence_path=staged["native-verifier-amd64"] / "attestations/oci-evidence.json",
        arm64_evidence_path=staged["native-verifier-arm64"] / "attestations/oci-evidence.json",
        source_commit=live["mergeSha"], index_output=index / "ofarm-ed25519.index.json",
        evidence_output=index / "ofarm-ed25519.index-evidence.json")
    native_root = policy / "deployment/postgresql/ofarm_ed25519"
    native.prepare_release_identity(
        checked_identity_path=native_root / "native_release_identity.json",
        checked_receipt_path=native_root / "native_evidence_receipt.json",
        verification_currentness_path=native_root / "native_evidence_verification_currentness.json",
        index_evidence_path=index / "ofarm-ed25519.index-evidence.json",
        index_path=index / "ofarm-ed25519.index.json", source_directory=native_root,
        repository_root=policy, candidate_output=index / "native_release_identity.candidate.json",
        candidate_receipt_output=index / "native_evidence_receipt.candidate.json")
    index_context = {**context, "authoritativeInputs": [
        {key: ref[key] for key in ("artifactId", "digest", "name")}
        for ref in published_refs if ref["name"].startswith("native-verifier-")]}
    (index / "evidence-publication-context.json").write_bytes(publication._canonical(index_context))
    (index / "review-baseline-admission.json").write_bytes(publication._canonical(live["admissionEvidence"]))
    payloads[204] = _zip(index)
    published_refs.append(_reference("native-verifier-index", 204, payloads[204], live["publisher"]["runId"], live["rootSha"]))
    published["native-verifier-index"] = index
    receipt = publication.receipt_document(live, source_refs, published_refs)
    receipt_root = tmp_path / "receipt"
    receipt_root.mkdir()
    (receipt_root / publication.RECEIPT_FILE).write_bytes(publication._canonical(receipt))
    payloads[205] = _zip(receipt_root)
    receipt_ref = _reference(publication.RECEIPT_NAME, 205, payloads[205], live["publisher"]["runId"], live["rootSha"])
    return dict(live=live, inputs=inputs, source_refs=source_refs, published_refs=published_refs,
        receipt=receipt, receipt_ref=receipt_ref, published=published, staged=staged,
        context=context, graph=graph, policy=policy, payloads=payloads, ticket=ticket)


def _validate_chain(chain, scratch):
    publication.validate_ticket(chain["ticket"], chain["live"], chain["source_refs"])
    publication.validate_published(published=chain["published"], reconstructed=chain["staged"],
        admission=chain["live"]["admissionEvidence"], context=chain["context"],
        published_artifacts=chain["published_refs"], scratch=scratch,
        repository=baseline_fixture.REPOSITORY, merge_sha=chain["live"]["mergeSha"],
        source_run_id=chain["live"]["source"]["runId"], policy_root=chain["policy"])


def test_complete_source_ticket_native_publication_and_independent_reconstruction(tmp_path):
    chain = _complete_chain(tmp_path)
    _validate_chain(chain, tmp_path / "verified")
    assert chain["receipt"]["schemaVersion"] == publication.RECEIPT_SCHEMA
    assert chain["receipt"]["source"]["eventName"] == "push"
    assert chain["receipt"]["admission"]["event_class"] == "CI_POLICY_TRANSITION"
    for ref in [*chain["source_refs"], *chain["published_refs"], chain["receipt_ref"]]:
        publication.download_artifact(reference=ref, repository=baseline_fixture.REPOSITORY,
            api_url="https://api.github.com", token="fictional-token",
            output_directory=tmp_path / "downloaded" / ref["name"],
            archive_path=tmp_path / "raw" / f"{ref['artifactId']}.zip",
            response_factory=lambda request, payload=chain["payloads"][ref["artifactId"]]:
                baseline_fixture.FakeArtifactResponse(payload))
    assert publication._single_document(tmp_path / "downloaded" / publication.RECEIPT_NAME,
                                        publication.RECEIPT_FILE) == chain["receipt"]


@pytest.mark.parametrize("mutate,reason", [
    (lambda c: (c["published"]["review-baseline"] / "equivalence.json").write_text("{}\n"), "independently reconstructed"),
    (lambda c: (c["published"]["native-verifier-index"] / "ofarm-ed25519.index.json").write_text("{}\n"), "independently reconstructed"),
    (lambda c: (c["published"]["native-verifier-arm64"] / "unexpected").write_text("extra"), "inventory is not exact"),
    (lambda c: (c["published"]["native-verifier-amd64"] / "evidence-publication-context.json").write_text("{}\n"), "context differs"),
])
def test_complete_chain_rejects_targeted_published_substitution(tmp_path, mutate, reason):
    chain = _complete_chain(tmp_path)
    mutate(chain)
    with pytest.raises(publication.TransitionPublicationError, match=reason):
        _validate_chain(chain, tmp_path / "verified")


def test_source_comparison_is_recomputed_by_the_real_validator(tmp_path):
    chain = _complete_chain(tmp_path)
    comparison = chain["inputs"]["conformance-provisional"] / "review-baseline/equivalence.json"
    document = json.loads(comparison.read_text())
    document["equivalent"] = False
    comparison.write_text(json.dumps(document))
    with pytest.raises(evidence.PublicationPolicyError, match="producer comparison"):
        publication.reconstruct_source(inputs=chain["inputs"], output=tmp_path / "second-staging",
            repository=baseline_fixture.REPOSITORY, merge_sha=chain["live"]["mergeSha"],
            source_run_id=chain["live"]["source"]["runId"], token="fictional-token",
            source_response_factory=chain["graph"].response, policy_root=chain["policy"])


@pytest.mark.parametrize("fault", ["extra", "missing", "duplicate", "other-run", "expired", "incomplete"])
def test_exact_transition_artifact_inventory_rejects_single_fault(fault):
    refs = [_reference(name, i, b"fictional", 10) for i, name in enumerate(publication.SOURCE_NAMES, 1)]
    values = [_provider(ref) for ref in refs]
    total = len(values)
    if fault == "extra":
        values.append({**values[0], "id": 99, "name": "debug"})
        total += 1
    if fault == "missing":
        values.pop()
        total -= 1
    if fault == "duplicate":
        values[-1] = copy.deepcopy(values[0])
    if fault == "other-run":
        values[0]["workflow_run"]["id"] = 11
    if fault == "expired":
        values[0]["expired"] = True
    if fault == "incomplete":
        total += 1
    with pytest.raises(publication.TransitionPublicationError):
        publication.artifact_inventory(fetch_json=lambda _: {"total_count": total, "artifacts": values},
            repository=baseline_fixture.REPOSITORY, run_id=10, root_sha="e" * 40,
            names=publication.SOURCE_NAMES)


def test_download_refuses_bad_digest_before_extraction(tmp_path):
    payload = baseline_fixture.artifact_zip({"../outside": b"hostile"})
    ref = _reference(publication.TICKET_NAME, 1, payload, 10)
    ref["digest"] = "sha256:" + "0" * 64
    with pytest.raises(publication.TransitionPublicationError, match="digest differs"):
        publication.download_artifact(reference=ref, repository=baseline_fixture.REPOSITORY,
            api_url="https://api.github.com", token="fictional-token", output_directory=tmp_path / "out",
            archive_path=tmp_path / "raw.zip",
            response_factory=lambda _: baseline_fixture.FakeArtifactResponse(payload))
    assert not (tmp_path / "outside").exists()


def test_transition_receipt_cannot_be_an_ordinary_main_receipt():
    live = _live()
    source = [_reference(name, i, b"x", live["source"]["runId"])
              for i, name in enumerate(publication.SOURCE_NAMES, 1)]
    published = [_reference(name, i, b"x", live["publisher"]["runId"])
                 for i, name in enumerate(publication.PUBLISHED_NAMES, 10)]
    receipt = publication.receipt_document(live, source, published)
    assert receipt["schemaVersion"] != baseline_fixture.PUBLICATION_RECEIPT_SCHEMA
    ordinary_source = baseline_fixture.source_run("push")
    ordinary_source["path"] = live["source"]["workflowPath"]
    event = {"repository": {"full_name": baseline_fixture.REPOSITORY}, "workflow_run": ordinary_source}
    with pytest.raises(baseline_fixture.AdmissionError, match="workflow_run event"):
        baseline_fixture._publication_source_from_event(
            event_name="push", event=event, repository=baseline_fixture.REPOSITORY,
            github_sha=live["rootSha"], workflow_sha=live["rootSha"],
            workflow_ref=live["publisher"]["workflowRef"], policy_sha=live["rootSha"],
            fetch_json=lambda _: pytest.fail("ordinary gate must reject transition before reads"))


def test_ordinary_main_publication_still_resolves_its_original_positive_chain():
    ordinary = publication.ordinary
    f = baseline_fixture
    event = f.workflow_run_event("push")
    event["workflow_run"].update(name="conformance", path=".github/workflows/conformance.yml")
    original_reader = f.publication_reader(source_event="push")
    def reader(path):
        if path == f"/repos/{f.REPOSITORY}/actions/runs/{f.SOURCE_RUN_ID}":
            return event["workflow_run"]
        return original_reader(path)
    plan = ordinary._publication_plan(event_name="workflow_run", event=event,
        github_sha=f.POLICY_SHA, workflow_sha=f.POLICY_SHA,
        workflow_ref=f.PUBLICATION_WORKFLOW_REF, repository=f.REPOSITORY,
        policy_sha=f.POLICY_SHA, fetch_json=reader)
    assert plan.publish
    assert plan.source.workflow_path == ".github/workflows/conformance.yml"
    assert plan.source.workflow_ref.endswith("@refs/heads/main")
    admission = ordinary.decide("push", {"repository": {"full_name": f.REPOSITORY},
        "ref": "refs/heads/main", "after": f.POLICY_SHA}, f.POLICY_SHA, f.POLICY_SHA,
        f.CONFORMANCE_WORKFLOW_REF, f.REPOSITORY, f.POLICY_SHA)
    ticket = ordinary._publication_ticket_document(admission=admission,
        source_run_id=f.SOURCE_RUN_ID, source_run_attempt=1,
        source_workflow_ref=f.CONFORMANCE_WORKFLOW_REF, source_workflow_sha=f.POLICY_SHA,
        provisional_artifacts={name: plan.artifacts[name] for name in publication.PROVISIONAL_NAMES})
    assert ordinary._validate_publication_ticket(ticket=ticket, source=plan.source,
        artifacts=plan.artifacts, fetch_json=reader).event_class == "MAIN_PUSH"


@pytest.mark.parametrize("error_kind", ["transport", "validation"])
def test_publication_cli_refuses_without_printing_provider_exception_context(tmp_path, capsys, error_kind):
    from conformance import ci_policy_transition as transition
    exception = transition.TransitionError if error_kind == "transport" else ValueError
    detail = "https://fictional.blob.core.windows.net/object?sig=fictional-private-signature"
    with mock.patch.object(transition, "make_reader", side_effect=exception(detail)):
        result = publication.main(["--operation", "download", "--repository", "fictional-farm/fixture",
            "--artifact-name", publication.TICKET_NAME, "--artifact-id", "1",
            "--artifact-digest", "sha256:"+"0"*64, "--output-directory", str(tmp_path / "output")])
    captured = capsys.readouterr()
    assert result == 2 and captured.out == ""
    assert captured.err == "CI transition publication refused; no authority output accepted\n"
    assert "fictional-private-signature" not in captured.err
    assert not (tmp_path / "output").exists()
