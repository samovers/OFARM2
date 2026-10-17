#!/usr/bin/env python3
"""Transition provenance around the unchanged substantive evidence validators.

This module never treats a push as ordinary main admission. The external root,
grant and operator journal supply authority; downloaded objects supply data.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import stat
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Callable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conformance import evidence_publication_policy as evidence
from conformance import ci_policy_transition_coverage as coverage
from conformance import review_baseline_admission as ordinary

TICKET_NAME = "ci-policy-transition-ticket-v1"
TICKET_FILE = "ci-policy-transition-ticket.json"
TICKET_SCHEMA = "ofarm.ci-policy-transition-ticket.v1"
RECEIPT_NAME = "ci-policy-transition-publication-receipt-v1"
RECEIPT_FILE = "ci-policy-transition-publication-receipt.json"
RECEIPT_SCHEMA = "ofarm.ci-policy-transition-publication.v1"
PROVISIONAL_NAMES = ordinary.PROVISIONAL_ARTIFACT_NAMES
PUBLISHED_NAMES = ordinary.PUBLICATION_ARTIFACT_NAMES
SOURCE_NAMES = (*PROVISIONAL_NAMES, TICKET_NAME)
SEALED_NAMES = (*PUBLISHED_NAMES, RECEIPT_NAME)
LIMITS = {
    **evidence.PROVISIONAL_ARTIFACT_LIMITS,
    TICKET_NAME: 1_000_000,
    RECEIPT_NAME: 1_000_000,
    "review-baseline": 512_000_000,
    "platform-mvp-evidence": 32_000_000,
    "native-verifier-amd64": 1_650_000_000,
    "native-verifier-arm64": 1_650_000_000,
    "native-verifier-index": 32_000_000,
}
INDEX_FILES = frozenset({
    "ofarm-ed25519.index.json", "ofarm-ed25519.index-evidence.json",
    "native_release_identity.candidate.json", "native_evidence_receipt.candidate.json",
})
Json = dict[str, Any]


class TransitionPublicationError(ValueError):
    """Transition publication cannot establish the complete evidence chain."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TransitionPublicationError(message)


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def artifact_reference(document: Json, *, run_id: int, root_sha: str) -> Json:
    """Validate one provider artifact; provenance is the actual transition run."""
    name = document.get("name")
    _require(name in LIMITS, "artifact name is outside the transition inventory")
    artifact_id = ordinary._positive_int(document.get("id"), "artifact id")
    size = ordinary._positive_int(document.get("size_in_bytes"), "artifact size")
    digest = ordinary._sha256(document.get("digest"), "artifact digest")
    run = evidence._object(document.get("workflow_run"), "artifact workflow run")
    _require(run.get("id") == run_id and run.get("head_sha") == root_sha,
             "artifact belongs to a different transition run or root")
    _require(document.get("expired") is False, "artifact has expired")
    _require(size <= LIMITS[name], "artifact exceeds its size limit")
    return {"name": name, "artifactId": artifact_id, "digest": digest,
            "size": size, "runId": run_id, "headSha": root_sha}


def artifact_inventory(*, fetch_json: Callable[[str], Any], repository: str,
                       run_id: int, root_sha: str, names: tuple[str, ...]) -> list[Json]:
    response = evidence._object(fetch_json(
        f"/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100"),
        "transition artifacts")
    values = evidence._array(response.get("artifacts"), "transition artifacts")
    _require(response.get("total_count") == len(values) and len(values) <= 100,
             "artifact inventory is incomplete")
    refs = [artifact_reference(evidence._object(value, "artifact"),
                               run_id=run_id, root_sha=root_sha) for value in values]
    _require(len({item["artifactId"] for item in refs}) == len(refs),
             "artifact ID is duplicated")
    _require(len(refs) == len(names) and {item["name"] for item in refs} == set(names),
             "artifact names are not the exact transition inventory")
    by_name = {item["name"]: item for item in refs}
    return [by_name[name] for name in names]


def download_artifact(*, reference: Json, repository: str, api_url: str,
                      token: str, output_directory: Path, archive_path: Path,
                      response_factory: evidence.ResponseFactory | None) -> None:
    """Reuse the trusted downloader/extractor and retain the exact raw archive.

    The response factory is mandatory at live entry points: its owner accounts
    for requests and rejects unexpected redirects before these unchanged helpers.
    """
    name = reference.get("name")
    _require(name in LIMITS, "artifact name is outside the transition inventory")
    artifact_id = ordinary._positive_int(reference.get("artifactId"), "artifact id")
    expected = evidence._checked_digest(reference.get("digest"))
    _require(bool(token) and "\n" not in token and "\r" not in token,
             "artifact credential is absent or malformed")
    repository = evidence._checked_repository(repository)
    api_url = evidence._checked_api_url(api_url)
    root = evidence._fresh_output_root(output_directory)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        f"{api_url}/repos/{repository}/actions/artifacts/{artifact_id}/zip",
        headers={"Accept": "application/vnd.github+json", "Accept-Encoding": "identity",
                 "X-GitHub-Api-Version": evidence.GITHUB_API_VERSION,
                 "User-Agent": "ofarm-ci-policy-transition"})
    request.add_unredirected_header("Authorization", f"Bearer {token}")
    observed = evidence._download_archive(request=request, archive_path=archive_path,
        limit=LIMITS[name], response_factory=response_factory)
    _require(observed == expected, "downloaded artifact digest differs from its bound identity")
    # The REST metadata size is also bound; a digest alone is not a size proof.
    if "size" in reference:
        _require(archive_path.stat().st_size == reference["size"],
                 "downloaded artifact size differs from its bound identity")
    evidence._extract_verified_zip(archive_path, root, LIMITS[name])
    evidence._regular_file_inventory(root)


def _single_document(root: Path, filename: str) -> Json:
    _require(evidence._regular_file_inventory(root) == frozenset({filename}),
             "ticket or receipt archive inventory is not exact")
    return evidence._read_json_object(root / filename, filename)


def _matching_files(expected: Path, actual: Path, names: frozenset[str]) -> None:
    for name in names:
        _require(evidence._sha256_hex_file(expected / name) ==
                 evidence._sha256_hex_file(actual / name),
                 f"published {name} differs from independently reconstructed evidence")


def reconstruct_source(*, inputs: dict[str, Path], output: Path, repository: str,
                       merge_sha: str, source_run_id: int, token: str,
                       source_response_factory: evidence.ResponseFactory,
                       policy_root: Path = evidence.POLICY_ROOT) -> dict[str, Path]:
    """Run actual baseline, comparison, platform and both native validators."""
    _require(set(inputs) == set(PROVISIONAL_NAMES), "provisional inputs are incomplete")
    conformance = output / "conformance"
    evidence.stage_conformance_evidence(input_root=inputs["conformance-provisional"],
        output_root=conformance, source_api_url="https://api.github.com",
        source_repository=repository, source_token=token, source_commit=merge_sha,
        source_run_id=source_run_id, source_run_attempt=1,
        source_response_factory=source_response_factory)
    result = {"review-baseline": conformance / "review-baseline",
              "platform-mvp-evidence": conformance / "platform-evidence"}
    for architecture in ("amd64", "arm64"):
        name = f"native-verifier-{architecture}"
        result[name] = output / name
        evidence.stage_native_evidence(input_root=inputs[name + "-provisional"],
            output_root=result[name], platform=f"linux/{architecture}",
            source_commit=merge_sha,
            containerfile=policy_root / "deployment/postgresql/ofarm_ed25519/Containerfile",
            builder_id=f"https://github.com/{repository}/actions/runs/{source_run_id}/attempts/1")
    return result


def publication_context(*, source: Json, publisher: Json, source_artifacts: list[Json]) -> Json:
    """Keep the existing content contract with truthful transition provenance."""
    return {
        "schemaVersion": "ofarm.evidence-publication-context.v1",
        "provisionalArtifacts": [{key: ref[key] for key in ("artifactId", "digest", "name")}
                                 for ref in source_artifacts],
        "source": {key: source[key] for key in
                   ("eventName", "runAttempt", "runId", "workflowRef", "workflowSha")},
        "publisher": {key: publisher[key] for key in
                      ("runAttempt", "runId", "workflowRef", "workflowSha")},
    }


def validate_published(*, published: dict[str, Path], reconstructed: dict[str, Path],
                       admission: Json, context: Json, published_artifacts: list[Json],
                       scratch: Path, repository: str, merge_sha: str,
                       source_run_id: int, policy_root: Path = evidence.POLICY_ROOT) -> None:
    """Re-authenticate published native inputs before deriving the expected index."""
    _require(set(published) == set(PUBLISHED_NAMES), "published inputs are incomplete")
    expected_files = {
        "review-baseline": evidence.REVIEW_BASELINE_FILES,
        "platform-mvp-evidence": frozenset({evidence.PLATFORM_PUBLICATION_FILE}),
        "native-verifier-amd64": evidence.NATIVE_AUTHORITATIVE_FILES,
        "native-verifier-arm64": evidence.NATIVE_AUTHORITATIVE_FILES,
        "native-verifier-index": INDEX_FILES,
    }
    for name in PUBLISHED_NAMES:
        root = published[name]
        _require(evidence._regular_file_inventory(root) ==
                 expected_files[name] | evidence.TRUSTED_METADATA_FILES,
                 f"published {name} file inventory is not exact")
        _require(evidence._read_json_object(root / "review-baseline-admission.json", "admission")
                 == admission, "published transition admission differs")
        expected_context = dict(context)
        if name == "native-verifier-index":
            expected_context["authoritativeInputs"] = [
                {key: ref[key] for key in ("artifactId", "digest", "name")}
                for ref in published_artifacts
                if ref["name"] in {"native-verifier-amd64", "native-verifier-arm64"}]
        _require(evidence._read_json_object(root / "evidence-publication-context.json", "context")
                 == expected_context, "published transition context differs")
        if name != "native-verifier-index":
            _matching_files(reconstructed[name], root, expected_files[name])
    native = evidence._native_policy_module()
    for architecture in ("amd64", "arm64"):
        root = published[f"native-verifier-{architecture}"]
        evidence.validate_native_claims(root, platform=f"linux/{architecture}",
                                        source_commit=merge_sha)
        verified = scratch / architecture
        native.collect_oci_evidence(archive_path=root / "ofarm-ed25519.oci.tar",
            reproducibility_path=root / "reproducibility.json", platform=f"linux/{architecture}",
            source_commit=merge_sha,
            containerfile_path=policy_root / "deployment/postgresql/ofarm_ed25519/Containerfile",
            builder_id=f"https://github.com/{repository}/actions/runs/{source_run_id}/attempts/1",
            output_directory=verified)
        _matching_files(verified, root / "attestations", frozenset({
            "oci-evidence.json", "sbom.spdx.in-toto.json", "provenance.slsa-v0.2.in-toto.json"}))
    index = scratch / "index"
    index.mkdir(parents=True, exist_ok=False)
    native.compose_multi_platform_index(
        amd64_evidence_path=scratch / "amd64/oci-evidence.json",
        arm64_evidence_path=scratch / "arm64/oci-evidence.json", source_commit=merge_sha,
        index_output=index / "ofarm-ed25519.index.json",
        evidence_output=index / "ofarm-ed25519.index-evidence.json")
    native_root = policy_root / "deployment/postgresql/ofarm_ed25519"
    native.prepare_release_identity(
        checked_identity_path=native_root / "native_release_identity.json",
        checked_receipt_path=native_root / "native_evidence_receipt.json",
        verification_currentness_path=native_root / "native_evidence_verification_currentness.json",
        index_evidence_path=index / "ofarm-ed25519.index-evidence.json",
        index_path=index / "ofarm-ed25519.index.json", source_directory=native_root,
        repository_root=policy_root,
        candidate_output=index / "native_release_identity.candidate.json",
        candidate_receipt_output=index / "native_evidence_receipt.candidate.json")
    _matching_files(index, published["native-verifier-index"], INDEX_FILES)


def _authority(live: Json, *, publisher: bool = False) -> Json:
    keys = ("rootSha", "rootTree", "closureDigest", "coverageDigest", "baseSha", "headSha", "mergeSha",
            "consumerPr", "grantId", "grantDigest", "admission", "sourceBinding")
    result = {key: live[key] for key in keys}
    if publisher:
        _require(live.get("publisherBinding") is not None, "publisher binding is missing")
        result["publisherBinding"] = live["publisherBinding"]
    return result


def ticket_document(live: Json, artifacts: list[Json]) -> Json:
    _require([item["name"] for item in artifacts] == list(PROVISIONAL_NAMES),
             "ticket provisional inventory is not exact")
    return copy.deepcopy({"schemaVersion": TICKET_SCHEMA, "authority": _authority(live),
            "source": live["source"], "provisionalArtifacts": artifacts,
            "coverage": coverage.declaration()})


def validate_ticket(ticket: Json, live: Json, artifacts: list[Json]) -> None:
    _require([item["name"] for item in artifacts] == list(SOURCE_NAMES),
             "ticket source inventory is not exact")
    _require(ticket == ticket_document(live, artifacts[:-1]),
             "transition ticket differs from independently authenticated source")


def receipt_document(live: Json, source_artifacts: list[Json],
                     published_artifacts: list[Json]) -> Json:
    _require([item["name"] for item in source_artifacts] == list(SOURCE_NAMES),
             "receipt source inventory is not exact")
    _require([item["name"] for item in published_artifacts] == list(PUBLISHED_NAMES),
             "receipt published inventory is not exact")
    _require(live.get("publisher") is not None and
             live["publisher"]["runId"] != live["source"]["runId"],
             "publisher must be a separate bound run")
    return copy.deepcopy({"schemaVersion": RECEIPT_SCHEMA,
            "authority": _authority(live, publisher=True),
            "source": {**live["source"], "artifacts": source_artifacts},
            "publisher": live["publisher"], "artifacts": published_artifacts,
            "admission": live["admissionEvidence"], "coverage": coverage.declaration()})


def _source_artifacts(live: Json, grant: Json, reader: Any,
                      names: tuple[str, ...] = SOURCE_NAMES) -> list[Json]:
    references = artifact_inventory(fetch_json=reader, repository=grant["repository"],
        run_id=live["source"]["runId"], root_sha=live["rootSha"], names=names)
    if "ticket" in live:
        ticket = next((ref for ref in references if ref["name"] == TICKET_NAME), None)
        _require(ticket is not None and live["ticket"] == {
            "id": ticket["artifactId"], "digest": ticket["digest"]},
            "source ticket differs from the immutable publisher binding")
    return references


def _bindings(live: Json | None) -> Json | None:
    return ({key: live[key] for key in ("admission", "sourceBinding", "publisherBinding")}
            if live is not None else None)


def _outputs(live: Json, artifacts: list[Json]) -> Json:
    source = live["source"]
    result = {
        "publish": "true", "eligible": "true", "source_run_id": source["runId"],
        "source_run_attempt": 1, "source_workflow_sha": source["workflowSha"],
        "source_workflow_ref": source["workflowRef"], "source_event_name": "push",
        "execution_merge_sha": live["mergeSha"], "reviewed_head_sha": live["headSha"],
        "base_sha": live["baseSha"], "policy_sha": live["rootSha"],
        "publication_concurrency_group": f"ofarm-pr-{live['consumerPr']}",
    }
    prefixes = dict(zip(SOURCE_NAMES, ("conformance", "native_amd64", "native_arm64", "ticket")))
    for ref in artifacts:
        prefix = prefixes[ref["name"]]
        result[prefix + "_artifact_id"] = ref["artifactId"]
        result[prefix + "_artifact_digest"] = ref["digest"]
    return result


def require_completed_jobs(reader: Any, repository: str, run_id: int,
                           required_names: tuple[str, ...]) -> None:
    document = evidence._object(reader(
        f"/repos/{repository}/actions/runs/{run_id}/attempts/1/jobs?per_page=100"),
        "transition jobs")
    jobs = evidence._array(document.get("jobs"), "transition jobs")
    _require(document.get("total_count") == len(jobs) and len(jobs) <= 100,
             "job inventory is incomplete")
    for name in required_names:
        matches = [job for job in jobs if isinstance(job, dict) and job.get("name") == name]
        _require(len(matches) == 1, f"required job {name} is absent or duplicated")
        job = matches[0]
        _require(job.get("run_id") == run_id and job.get("run_attempt") == 1 and
                 job.get("status") == "completed" and job.get("conclusion") == "success",
                 f"required job {name} did not finish successfully in attempt 1")


def run_operation(args: argparse.Namespace, *, policy: Json, grant: Json, reader: Any) -> Json:
    """Called by the core CLI with the same accounted reader as its live checks."""
    from conformance import ci_policy_transition as transition

    def recheck(phase: str, previous: Json | None = None) -> Json:
        return transition.validate_live(policy, grant, reader, phase=phase,
            expected_bindings=_bindings(previous) if previous else getattr(args, "transition_bindings", None),
            event=getattr(args, "event", None),
            job_context=getattr(args, "job_context", None))

    operation = args.operation
    if operation == "resolve":
        # Resolve only immutable inputs needed to download the ticket. This is
        # preparation, never a fourth admission sweep or permission to publish.
        # The next operation must independently perform its full live recheck.
        bindings = transition._typed_bindings(getattr(args, "transition_bindings", None), publisher=True)
        bound = bindings["publisherBinding"]
        comment = reader(f"/repos/{grant['repository']}/issues/comments/{bound['id']}")
        _require(transition._comment_identity(comment, grant, now=transition.utcnow()) == bound,
                 "preparation publisher binding changed")
        payload = transition.parse_record(comment.get("body"), "publisher")
        transition._keys(payload, {"grantId", "grantDigest", "rootSha", "admission", "publisher", "source", "sourceBinding", "ticket"}, "preparation binding")
        _require(payload["grantId"] == grant["grantId"] and payload["grantDigest"] == transition.digest(grant)
                 and payload["rootSha"] == grant["rootSha"] and payload["admission"] == bindings["admission"]
                 and payload["sourceBinding"] == bindings["sourceBinding"], "preparation grant binding differs")
        source = transition._keys(payload["source"], {"runId", "runAttempt"}, "preparation source")
        transition._integer(source["runId"], "preparation source run")
        _require(type(source["runAttempt"]) is int and source["runAttempt"] == 1,
                 "preparation source is a rerun")
        transition._keys(payload["ticket"], {"id", "digest"}, "preparation ticket")
        transition._integer(payload["ticket"]["id"], "preparation ticket ID")
        transition._digest(payload["ticket"]["digest"], "preparation ticket digest")
        path, name = transition.WORKFLOWS["source"]
        prepared = {**{key: grant[key] for key in ("rootSha", "mergeSha", "headSha", "baseSha", "consumerPr")},
                    "source": {**source, "workflowSha": grant["rootSha"],
                        "workflowRef": f"{grant['repository']}/{path}@{grant['sourceRef']}",
                        "eventName": "push", "workflowPath": path, "workflowName": name},
                    "ticket": payload["ticket"]}
        artifacts = _source_artifacts(prepared, grant, reader)
        outputs = _outputs(prepared, artifacts)
        outputs.pop("publish")
        outputs.pop("eligible")
        if getattr(args, "github_output", None) is not None:
            ordinary._write_output(args.github_output, outputs)
        _require(getattr(args, "evidence_output", None) is None,
                 "preparation cannot produce admission evidence")
        return {"prepared": True, "source": prepared["source"], "artifacts": artifacts}
    live = recheck(getattr(args, "phase", None) or operation)
    if operation == "handoff":
        _require(args.ticket_output is not None, "handoff ticket output is missing")
        require_completed_jobs(reader, grant["repository"], live["source"]["runId"],
            ("conformance", "native verifier (amd64)", "native verifier (arm64)", "source guard"))
        artifacts = _source_artifacts(live, grant, reader, PROVISIONAL_NAMES)
        final = recheck("handoff-preupload", live)
        _require(_authority(live) == _authority(final) and live["source"] == final["source"],
                 "handoff authority changed before ticket upload")
        _require(artifacts == _source_artifacts(final, grant, reader, PROVISIONAL_NAMES),
                 "provisional inventory changed before ticket upload")
        document = ticket_document(final, artifacts)
        evidence._write_canonical_json(args.ticket_output, document)
    else:
        artifacts = _source_artifacts(live, grant, reader)
        document = live
        if operation in {"publish", "seal"}:
            _require(args.ticket is not None, "publication requires the exact transition ticket")
            ticket = evidence._read_json_object(args.ticket, "transition ticket")
            validate_ticket(ticket, live, artifacts)
        if operation == "seal":
            _require(args.publication_receipt_output is not None,
                     "seal receipt output is missing")
            require_completed_jobs(reader, grant["repository"], live["source"]["runId"],
                ("conformance", "native verifier (amd64)", "native verifier (arm64)",
                 "source guard", "seal exact provisional publication handoff"))
            publisher_id = live["publisher"]["runId"]
            require_completed_jobs(reader, grant["repository"], publisher_id,
                ("derive and publish authoritative evidence", "publisher guard"))
            published = artifact_inventory(fetch_json=reader, repository=grant["repository"],
                run_id=publisher_id, root_sha=live["rootSha"], names=PUBLISHED_NAMES)
            _require(args.published_artifacts_input is not None,
                     "seal must bind upload output identities")
            raw = args.published_artifacts_input.read_bytes()
            try:
                candidate = json.loads(raw, object_pairs_hook=evidence._reject_duplicate_json_keys,
                                       parse_constant=evidence._reject_non_finite_json_number)
            except (ValueError, UnicodeDecodeError) as exc:
                raise TransitionPublicationError("published upload outputs are invalid JSON") from exc
            expected_candidate = [{key: ref[key] for key in ("artifactId", "digest", "name")}
                                  for ref in published]
            _require(isinstance(candidate, list), "published upload outputs must be an array")
            normalized = []
            for item in candidate:
                item = evidence._object(item, "published upload output")
                evidence._exact_keys(item, {"artifactId", "digest", "name"}, "published upload output")
                normalized.append({"artifactId": ordinary._positive_int(item["artifactId"], "upload ID"),
                                   "digest": ordinary._normalized_sha256(item["digest"], "upload digest"),
                                   "name": item["name"]})
            _require(normalized == expected_candidate,
                     "published upload outputs differ from the exact live inventory")
            for ref in published:
                actual = artifact_reference(evidence._object(reader(
                    f"/repos/{grant['repository']}/actions/artifacts/{ref['artifactId']}"),
                    "published artifact identity"), run_id=publisher_id, root_sha=live["rootSha"])
                _require(actual == ref, "published artifact individual identity changed")
            final = recheck("seal-preupload", live)
            _require(_authority(final, publisher=True) == _authority(live, publisher=True),
                     "seal authority changed before receipt upload")
            _require(artifacts == _source_artifacts(final, grant, reader),
                     "source inventory changed before receipt upload")
            document = receipt_document(final, artifacts, published)
            evidence._write_canonical_json(args.publication_receipt_output, document)
    if getattr(args, "github_output", None) is not None:
        ordinary._write_output(args.github_output, _outputs(live, artifacts))
    if getattr(args, "evidence_output", None) is not None:
        evidence._write_canonical_json(args.evidence_output, live["admissionEvidence"])
    return document


def acceptance_tuple(live: Json, source_artifacts: list[Json], receipt: Json) -> Json:
    ticket = next(item for item in source_artifacts if item["name"] == TICKET_NAME)
    return {**{key: live[key] for key in (
        "grantId", "rootSha", "rootTree", "closureDigest", "coverageDigest", "baseSha", "consumerPr", "headSha", "mergeSha")},
        "sourceRunId": live["source"]["runId"], "sourceRunAttempt": 1,
        "publisherRunId": live["publisher"]["runId"], "publisherRunAttempt": 1,
        "ticketArtifactId": ticket["artifactId"], "ticketDigest": ticket["digest"],
        "receiptArtifactId": receipt["artifactId"], "receiptDigest": receipt["digest"]}


def _require_selected_execution(checkout: Path, closure: Json) -> None:
    """Bind the running verifier and its validators to the selected checkout."""
    from conformance import ci_policy_transition as transition
    from conformance import ci_policy_transition_operator as operator
    from conformance import ci_policy_transition_workflows as workflows

    selected = checkout.resolve()
    _require(Path(__file__).resolve() == selected / "conformance/ci_policy_transition_publication.py",
             "external verifier must execute from the selected policy checkout")
    modules = {
        "conformance/ci_policy_transition_publication.py": __file__,
        "conformance/ci_policy_transition.py": transition.__file__,
        "conformance/ci_policy_transition_operator.py": operator.__file__,
        "conformance/ci_policy_transition_workflows.py": workflows.__file__,
        "conformance/ci_policy_transition_tools.py": transition.tool_policy.__file__,
        "conformance/ci_policy_transition_coverage.py": coverage.__file__,
        "conformance/evidence_publication_policy.py": evidence.__file__,
        "conformance/review_baseline_admission.py": ordinary.__file__,
    }
    for relative, source in modules.items():
        _require(Path(source).resolve() == selected / relative,
                 "executing authority module is outside the selected policy checkout")
    # The unchanged evidence owner loads these validators lazily. Authenticate
    # the real module objects it will use, including any existing import cache.
    review = evidence._review_policy_module()
    native = evidence._native_policy_module()
    identity = sys.modules[native.load_native_release_identity.__module__]
    modules.update({
        "conformance/run_review_baseline.py": review.__file__,
        "deployment/postgresql/native_evidence.py": native.__file__,
        "deployment/postgresql/native_release_identity.py": identity.__file__,
    })
    for relative, source in modules.items():
        path = Path(source).resolve()
        _require(path == selected / relative,
                 "executing authority module is outside the selected policy checkout")
        entry = closure.get("files", {}).get(relative, {})
        _require(stat.S_ISREG(path.stat(follow_symlinks=False).st_mode) and
                 transition.digest(path.read_bytes()) == entry.get("sha256"),
                 "executing authority module bytes differ from the selected closure")


def verify_for_acceptance(*, policy: Json, grant: Json, reader: Any,
                          checkout: Path, closure: Json, expected_root: str,
                          expected_closure: str, authority_projection: Json,
                          journal: Any, output: Path) -> Json:
    """Consume the one use on failure as well as on completed acceptance."""
    try:
        return _verify_for_acceptance(policy=policy, grant=grant, reader=reader,
            checkout=checkout, closure=closure, expected_root=expected_root,
            expected_closure=expected_closure, authority_projection=authority_projection,
            journal=journal, output=output)
    except Exception:
        reader.budget.fail("external verification refused")
        state = journal.snapshot()
        if state["state"] not in {"FAILED", "RETIRED"}:
            journal.fail("external verification refused; no renewed use")
        raise


def _verify_for_acceptance(*, policy: Json, grant: Json, reader: Any,
                           checkout: Path, closure: Json, expected_root: str,
                           expected_closure: str, authority_projection: Json,
                           journal: Any, output: Path) -> Json:
    """Accept only an externally anchored, freshly revalidated complete chain."""
    from conformance import ci_policy_transition as transition
    from conformance import ci_policy_transition_operator as operator

    _require_selected_execution(checkout, closure)
    _require(expected_root == grant["rootSha"] and expected_closure == grant["closureDigest"],
             "external root and closure do not match the separately supplied grant")
    _require(policy == evidence._read_json_object(checkout / transition.ROOT_FILE, "selected root policy"),
             "external policy manifest differs from selected checkout")
    transition.validate_grant(policy, grant)
    _require(not output.resolve().is_relative_to(checkout.resolve()),
             "external evidence archive must be outside the policy checkout")
    operator.verify_policy_closure(checkout, closure, expected_root,
                                   grant["baseSha"], expected_closure, expected_tree=grant["rootTree"])
    transition.authenticate_policy_checkout(checkout, policy, grant)
    transition.verify_original_authority(authority_projection, grant)
    snapshot = journal.snapshot()
    _require(snapshot["state"] in {"SEALED", "ACCEPTED"},
             "external journal has no sealed or identically consumed tuple")
    _require(snapshot["genesisDigest"] == grant["journal"]["genesisDigest"] and
             snapshot["approval"]["grantDigest"] == transition.digest(grant),
             "external journal genesis or approval grant digest differs")
    live = transition.validate_live(policy, grant, reader, phase="external-acceptance")
    transition.require_quota_headroom(reader, grant, "external-acceptance")
    require_completed_jobs(reader, grant["repository"], live["source"]["runId"],
        ("conformance", "native verifier (amd64)", "native verifier (arm64)", "source guard",
         "seal exact provisional publication handoff"))
    require_completed_jobs(reader, grant["repository"], live["publisher"]["runId"],
        ("derive and publish authoritative evidence", "publisher guard",
         "seal transition publication on a fresh trusted runner"))
    for role, key in (("admission", "admission"), ("source_binding", "sourceBinding"),
                      ("publisher_binding", "publisherBinding")):
        recorded = snapshot["writes"][role]
        _require(live[key] == {"id": recorded["commentId"], "digest": recorded["bodyDigest"]},
                 "external journal immutable comment binding differs")
    source_refs = _source_artifacts(live, grant, reader)
    sealed_refs = artifact_inventory(fetch_json=reader, repository=grant["repository"],
        run_id=live["publisher"]["runId"], root_sha=expected_root, names=SEALED_NAMES)
    exact_tuple = acceptance_tuple(live, source_refs, sealed_refs[-1])
    _require(snapshot["ticket"] == {"artifactId": exact_tuple["ticketArtifactId"],
                                   "digest": exact_tuple["ticketDigest"]} and
             snapshot["receipt"] == {"artifactId": exact_tuple["receiptArtifactId"],
                                    "digest": exact_tuple["receiptDigest"]},
             "external journal ticket or receipt differs from the live chain")
    root = evidence._fresh_output_root(output)
    downloaded: dict[str, Path] = {}
    for ref in [*source_refs, *sealed_refs]:
        destination = root / "extracted" / ref["name"]
        download_artifact(reference=ref, repository=grant["repository"],
            api_url="https://api.github.com", token=reader.token,
            output_directory=destination,
            archive_path=root / "archives" / f"{ref['artifactId']}.zip",
            response_factory=reader.artifact_response)
        downloaded[ref["name"]] = destination
    ticket = _single_document(downloaded[TICKET_NAME], TICKET_FILE)
    validate_ticket(ticket, live, source_refs)
    receipt = _single_document(downloaded[RECEIPT_NAME], RECEIPT_FILE)
    _require(receipt == receipt_document(live, source_refs, sealed_refs[:-1]),
             "transition receipt differs from independently authenticated identities")
    with reader.pool("shared-tools"):
        reconstructed = reconstruct_source(
            inputs={name: downloaded[name] for name in PROVISIONAL_NAMES},
            output=root / "reconstructed", repository=grant["repository"],
            merge_sha=live["mergeSha"], source_run_id=live["source"]["runId"],
            token=reader.token, source_response_factory=reader.response,
            policy_root=checkout)
    context = publication_context(source=live["source"], publisher=live["publisher"],
                                  source_artifacts=source_refs)
    validate_published(published={name: downloaded[name] for name in PUBLISHED_NAMES},
        reconstructed=reconstructed, admission=live["admissionEvidence"], context=context,
        published_artifacts=sealed_refs[:-1], scratch=root / "reverified-native",
        repository=grant["repository"], merge_sha=live["mergeSha"],
        source_run_id=live["source"]["runId"], policy_root=checkout)
    # Bytes, original authority, closure and all live facts stay decisive at use.
    _require_selected_execution(checkout, closure)
    operator.verify_policy_closure(checkout, closure, expected_root,
                                   grant["baseSha"], expected_closure, expected_tree=grant["rootTree"])
    transition.authenticate_policy_checkout(checkout, policy, grant)
    transition.verify_original_authority(authority_projection, grant)
    final = transition.validate_live(policy, grant, reader, phase="external-acceptance",
                                     expected_bindings=_bindings(live))
    _require(final == live, "live transition authority changed during external verification")
    _require(source_refs == _source_artifacts(final, grant, reader),
             "source inventory changed during external verification")
    _require(sealed_refs == artifact_inventory(fetch_json=reader, repository=grant["repository"],
        run_id=live["publisher"]["runId"], root_sha=expected_root, names=SEALED_NAMES),
        "publisher inventory changed during external verification")
    transition.require_quota_headroom(reader, grant, "external-acceptance")
    reader.budget.assert_healthy()
    result = journal.accept(exact_tuple)
    report = {**result, "schemaVersion": "ofarm.ci-policy-transition-acceptance.v1",
        "root": expected_root, "closureDigest": expected_closure,
        "archives": [{**ref, "path": f"archives/{ref['artifactId']}.zip"}
                     for ref in [*source_refs, *sealed_refs]],
        "originalAuthority": authority_projection, "receipt": receipt, "closure": closure, "grant": grant,
        "substantiveValidation": "passed", "nativeMergeAuthorized": False}
    evidence._write_canonical_json(root / "acceptance.json", report)
    return report


def audit_consumed(*, journal: Any, archive_directory: Path, roots_directory: Path,
                   root_manifest: Json, provider_reader: Any | None = None) -> Json:
    """Report historical byte integrity; this path has no live acceptance output."""
    from conformance import ci_policy_transition_operator as operator
    from conformance import ci_policy_transition as transition

    state = journal.snapshot()
    _require(state["state"] == "RETIRED" and state.get("nativeMerge") is not None,
             "historical audit requires consumed acceptance and recorded native merge")
    consumed = state["consumedTuple"]
    report = evidence._read_json_object(archive_directory / "acceptance.json", "archived acceptance")
    _require(report.get("tuple") == consumed, "archived acceptance differs from the consumed tuple")
    _require(operator.policy_closure_digest(report["closure"]) == consumed["closureDigest"],
             "archived closure differs from the consumed closure digest")
    root_result = operator.verify_archived_closure(roots_directory, root_manifest,
                                                   report["closure"], consumed)
    _require(any(item == {"rootSha": consumed["rootSha"], "rootTree": consumed["rootTree"],
                          "baseSha": consumed["baseSha"]} for item in root_manifest["roots"]),
             "archived roots omit the consumed root/tree/base")
    # Receipt ZIP digest comes from the independent consumed journal, not this report.
    receipt_archive = archive_directory / "archives" / f"{consumed['receiptArtifactId']}.zip"
    _require(stat.S_ISREG(receipt_archive.stat(follow_symlinks=False).st_mode) and
             receipt_archive.stat().st_size <= LIMITS[RECEIPT_NAME],
             "historical receipt archive is not a bounded regular file")
    _require("sha256:" + evidence._sha256_hex_file(receipt_archive) == consumed["receiptDigest"],
             "historical receipt archive digest differs")
    with tempfile.TemporaryDirectory(prefix="ofarm-transition-audit-") as directory:
        extracted = Path(directory).resolve()
        evidence._extract_verified_zip(receipt_archive, extracted, LIMITS[RECEIPT_NAME])
        receipt = _single_document(extracted, RECEIPT_FILE)
    _require(receipt.get("schemaVersion") == RECEIPT_SCHEMA,
             "historical archive does not contain a transition receipt")
    authority = receipt["authority"]
    _require(all(authority.get(key) == consumed[key] for key in (
        "grantId", "rootSha", "rootTree", "closureDigest", "coverageDigest", "baseSha", "consumerPr", "headSha", "mergeSha")),
        "historical receipt authority differs from the consumed tuple")
    _require(receipt["source"]["runId"] == consumed["sourceRunId"] and
             receipt["publisher"]["runId"] == consumed["publisherRunId"] and
             receipt["source"]["runAttempt"] == receipt["publisher"]["runAttempt"] == 1,
             "historical receipt run tuple differs")
    refs = [*receipt["source"]["artifacts"], *receipt["artifacts"]]
    _require([item["name"] for item in refs] == [*SOURCE_NAMES, *PUBLISHED_NAMES],
             "historical receipt inventories are incomplete")
    ticket = refs[len(SOURCE_NAMES) - 1]
    _require(ticket["artifactId"] == consumed["ticketArtifactId"] and
             ticket["digest"] == consumed["ticketDigest"],
             "historical ticket differs from the consumed journal")
    _require(transition.digest(report["grant"]) == authority["grantDigest"],
             "archived grant differs from the receipt-bound grant")
    transition.verify_original_authority(report["originalAuthority"], report["grant"])
    expected_names = {f"{item['artifactId']}.zip" for item in refs} | {receipt_archive.name}
    _require(evidence._regular_file_inventory(archive_directory / "archives") == expected_names,
             "historical raw archive inventory is not exact")
    provider_facts = []
    for ref in refs:
        path = archive_directory / "archives" / f"{ref['artifactId']}.zip"
        _require(path.stat().st_size == ref["size"] and path.stat().st_size <= LIMITS[ref["name"]],
                 "historical artifact size differs")
        _require("sha256:" + evidence._sha256_hex_file(path) == ref["digest"],
                 "historical artifact digest differs")
        fact = {"artifactId": ref["artifactId"], "status": "unavailable",
                "reason": "no fresh provider reader supplied; archive bytes only"}
        if provider_reader is not None:
            try:
                observed = artifact_reference(evidence._object(provider_reader(
                    f"/repos/{state['coordinates']['repository']}/actions/artifacts/{ref['artifactId']}"),
                    "historical provider artifact"), run_id=ref["runId"], root_sha=ref["headSha"])
                _require(observed == ref, "historical provider artifact differs from archive")
                fact = {"artifactId": ref["artifactId"], "status": "reauthenticated"}
            except TransitionPublicationError as exc:
                fact["status"] = "mismatch"
                fact["reason"] = str(exc)
            except (OSError, ValueError, KeyError) as exc:
                fact["reason"] = str(exc)
        provider_facts.append(fact)
    return {"schemaVersion": "ofarm.ci-policy-transition-audit.v1", "purpose": "audit-consumed",
            "archiveIntegrity": True, "rootArchive": root_result,
            "tuple": consumed, "recordedNativeMerge": state["nativeMerge"],
            "originalAuthorityReferences": report["originalAuthority"],
            "providerFacts": provider_facts, "liveAcceptanceAuthority": False,
            "executionAuthority": False, "mergeAuthority": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", required=True,
                        choices=("download", "stage-conformance", "verify-for-acceptance", "audit-consumed"))
    parser.add_argument("--api-url", default="https://api.github.com")
    parser.add_argument("--repository")
    parser.add_argument("--artifact-name", choices=tuple(LIMITS))
    parser.add_argument("--artifact-id", type=int)
    parser.add_argument("--artifact-digest")
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--archive-path", type=Path)
    parser.add_argument("--budget-path", type=Path)
    parser.add_argument("--phase", default="publisher-start")
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--source-api-url", default="https://api.github.com")
    parser.add_argument("--source-repository")
    parser.add_argument("--source-commit")
    parser.add_argument("--source-run-id", type=int)
    parser.add_argument("--source-run-attempt", type=int)
    parser.add_argument("--policy-root", type=Path, default=evidence.POLICY_ROOT)
    parser.add_argument("--root-manifest", type=Path)
    parser.add_argument("--grant-file", type=Path)
    parser.add_argument("--closure", type=Path)
    parser.add_argument("--expected-root")
    parser.add_argument("--expected-closure")
    parser.add_argument("--authority-projection", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--journal-genesis")
    parser.add_argument("--roots-directory", type=Path)
    parser.add_argument("--roots-manifest", type=Path)
    args = parser.parse_args(argv)
    from conformance import ci_policy_transition as transition
    from conformance import ci_policy_transition_operator as operator
    try:
        if args.operation == "download":
            _require(all(value is not None for value in (args.repository, args.artifact_name,
                args.artifact_id, args.artifact_digest, args.output_directory)),
                "download coordinates are incomplete")
            reader = transition.make_reader(args.phase, token=os.environ.get("OFARM_ARTIFACT_TOKEN", ""),
                api_url=args.api_url, budget_path=args.budget_path)
            archive_path = args.archive_path or args.output_directory.with_name(
                args.output_directory.name + f"-{args.artifact_id}.zip")
            with reader.pool("shared-tools"):
                download_artifact(reference={"name": args.artifact_name, "artifactId": args.artifact_id,
                    "digest": ordinary._normalized_sha256(args.artifact_digest, "artifact digest")},
                    repository=args.repository, api_url=args.api_url, token=reader.token,
                    output_directory=args.output_directory, archive_path=archive_path,
                    response_factory=reader.artifact_response)
            if args.artifact_name == TICKET_NAME:
                _single_document(args.output_directory, TICKET_FILE)
            elif args.artifact_name in {"native-verifier-amd64", "native-verifier-arm64"}:
                evidence.validate_native_inventory(args.output_directory, authoritative=True)
        elif args.operation == "stage-conformance":
            reader = transition.make_reader(args.phase,
                token=os.environ.get("OFARM_SOURCE_INPUT_TOKEN", ""),
                api_url=args.source_api_url, budget_path=args.budget_path)
            with reader.pool("source-reader"):
                evidence.stage_conformance_evidence(input_root=args.input_root, output_root=args.output_root,
                    source_api_url=args.source_api_url, source_repository=args.source_repository,
                    source_token=reader.token, source_commit=args.source_commit,
                    source_run_id=args.source_run_id, source_run_attempt=args.source_run_attempt,
                    source_response_factory=reader.response)
        else:
            closure = None
            if args.operation == "verify-for-acceptance":
                closure = evidence._read_json_object(args.closure, "external closure")
                _require_selected_execution(args.policy_root, closure)
            _require(args.journal is not None and args.checkpoint is not None and args.journal_genesis is not None,
                     "independent journal coordinates are required")
            with operator.TransitionJournal(args.journal, args.checkpoint, args.journal_genesis,
                    candidate_roots=(args.policy_root,)) as journal:
                if args.operation == "audit-consumed":
                    report = audit_consumed(journal=journal, archive_directory=args.output_directory,
                        roots_directory=args.roots_directory,
                        root_manifest=evidence._read_json_object(args.roots_manifest, "root archive manifest"))
                else:
                    grant = evidence._read_json_object(args.grant_file, "external grant")
                    policy = evidence._read_json_object(args.root_manifest, "external root manifest")
                    reader = transition.make_reader("external-acceptance", policy=policy,
                        token=os.environ.get("OFARM_ADMISSION_TOKEN", ""), budget_path=args.budget_path)
                    report = verify_for_acceptance(policy=policy, grant=grant, reader=reader,
                        checkout=args.policy_root,
                        closure=closure,
                        expected_root=args.expected_root, expected_closure=args.expected_closure,
                        authority_projection=evidence._read_json_object(args.authority_projection, "original authority"),
                        journal=journal, output=args.output_directory)
                print(json.dumps(report, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, transition.TransitionError):
        # Exception context may contain a signed redirect URL or hostile input.
        # The trusted disposition never publishes provider-controlled details.
        print("CI transition publication refused; no authority output accepted", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
