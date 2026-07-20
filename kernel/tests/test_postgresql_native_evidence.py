"""Hostile tests for bounded native verifier CI evidence."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import shutil
import tarfile
from pathlib import Path

import pytest

from deployment.postgresql import native_evidence
from deployment.postgresql.native_evidence import (
    CURRENT_NATIVE_ACTION_PINS,
    CURRENT_NATIVE_BUILD_PINS,
    LIBSODIUM_SOURCE_SHA256,
    LIBSODIUM_SOURCE_URL,
    NativeEvidenceError,
    SERVER_DEV_SOURCES,
    collect_oci_evidence,
    compare_builds,
    conformance_environment,
    compose_multi_platform_index,
    finalize_evidence_receipt,
    prepare_release_identity,
)
from deployment.postgresql.native_release_identity import (
    EVIDENCE_AUTHORITY_PATHS,
    EVIDENCE_RECEIPT_PATH,
    IDENTITY_PATH,
    NATIVE_SOURCE_PATHS,
    NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT,
    NATIVE_RELEASE_REPOSITORY,
    NATIVE_RELEASE_REPOSITORY_API_URL,
    NATIVE_RELEASE_REPOSITORY_ID,
    NATIVE_RELEASE_REPOSITORY_NODE_ID,
    NATIVE_RELEASE_REPOSITORY_URL,
    PACKAGE_ROOT as RELEASE_PACKAGE_ROOT,
    SOURCE_DIRECTORY,
    NativeReleaseIdentityError,
    canonical_json_bytes as release_canonical_json_bytes,
    evidence_authority_input_manifest,
    load_native_release_identity,
    load_native_evidence_receipt,
    provisional_evidence_receipt_document,
    provisional_identity_document,
    validate_native_release_identity,
)


SOURCE_COMMIT = "1" * 40
PLATFORM = "linux/amd64"
BUILDER_ID = "https://github.com/samovers/OFARM2/actions/runs/1/attempts/1"
CONTAINERFILE_BYTES = (SOURCE_DIRECTORY / "Containerfile").read_bytes()
ARTIFACTS = {
    "libsodium.a": b"static libsodium archive\x00",
    "ofarm_ed25519.so": b"native verifier\x00",
    "ofarm_ed25519.control": b"default_version = '1.0'\n",
    "ofarm_ed25519--1.0.sql": b"CREATE FUNCTION ed25519_verify();\n",
}
PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _descriptor(data: bytes, media_type: str, **additional):
    return {
        "mediaType": media_type,
        "digest": _digest(data),
        "size": len(data),
        **additional,
    }


def _write_artifacts(directory: Path) -> None:
    directory.mkdir()
    for name, data in ARTIFACTS.items():
        path = directory / name
        path.write_bytes(data)
        path.chmod(0o755 if name == "ofarm_ed25519.so" else 0o644)


def _write_metadata(path: Path, digest: str, config_digest: str) -> None:
    path.write_text(
        json.dumps(
            {
                "containerimage.digest": digest,
                "containerimage.config.digest": config_digest,
                "containerimage.descriptor": {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "digest": digest,
                    "size": 123,
                    "annotations": {"config.digest": config_digest},
                },
            }
        )
    )


def _reproducibility_fixture(
    tmp_path: Path,
    child_digest: str,
    config_digest: str,
    *,
    platform: str = PLATFORM,
) -> Path:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_artifacts(first)
    _write_artifacts(second)
    first_metadata = tmp_path / "first.json"
    second_metadata = tmp_path / "second.json"
    _write_metadata(first_metadata, child_digest, config_digest)
    _write_metadata(second_metadata, child_digest, config_digest)
    output = tmp_path / "reproducibility.json"
    compare_builds(
        first_metadata=first_metadata,
        second_metadata=second_metadata,
        first_artifacts=first,
        second_artifacts=second,
        platform=platform,
        source_commit=SOURCE_COMMIT,
        output=output,
    )
    return output


def _archive_bytes(platform: str, evidence_octet: str) -> bytes:
    return f"native OCI archive {platform} {evidence_octet}\n".encode()


def _native_oci_report(
    platform: str,
    digest_octet: str,
    evidence_octet: str = "a",
) -> dict[str, object]:
    artifacts = [
        {
            "name": name,
            "mode": "0755" if name == "ofarm_ed25519.so" else "0644",
            "sha256": _digest(data),
            "size": len(data),
        }
        for name, data in ARTIFACTS.items()
    ]
    return {
        "schema": "ofarm.native-oci-evidence.v1",
        "platform": platform,
        "source_commit": SOURCE_COMMIT,
        "builder_id": BUILDER_ID,
        "runtime_child_digest": "sha256:" + digest_octet * 64,
        "runtime_child_size": 1234,
        "runtime_config_digest": "sha256:" + digest_octet.upper().lower() * 64,
        "artifacts": artifacts,
        "image_index_digest": "sha256:" + evidence_octet * 64,
        "attestation_manifest_digest": "sha256:" + evidence_octet * 64,
        "attestation_manifest_size": 456,
        "oci_archive": {
            "sha256": _digest(_archive_bytes(platform, evidence_octet)),
            "size": len(_archive_bytes(platform, evidence_octet)),
        },
        "sbom": {
            "predicate_type": "https://spdx.dev/Document",
            "sha256": "sha256:" + evidence_octet * 64,
            "size": 321,
        },
        "provenance": {
            "predicate_type": "https://slsa.dev/provenance/v0.2",
            "sha256": "sha256:" + evidence_octet * 64,
            "size": 654,
        },
    }


def _write_provisional_checked_authority(tmp_path: Path) -> tuple[Path, Path]:
    identity_document = provisional_identity_document(SOURCE_DIRECTORY)
    identity_bytes = release_canonical_json_bytes(identity_document)
    identity = validate_native_release_identity(
        identity_document,
        canonical_bytes=identity_bytes,
        source_directory=SOURCE_DIRECTORY,
    )
    identity_path = tmp_path / "provisional.json"
    identity_path.write_bytes(identity_bytes)
    receipt_path = tmp_path / "provisional-receipt.json"
    receipt_path.write_bytes(
        release_canonical_json_bytes(
            provisional_evidence_receipt_document(
                release_identity=identity,
                repository_root=RELEASE_PACKAGE_ROOT,
            )
        )
    )
    return identity_path, receipt_path


def _prepare_candidate(
    tmp_path: Path,
    *,
    evidence_octet: str = "a",
    runtime_octet: str = "stable",
    checked_identity_path: Path | None = None,
    checked_receipt_path: Path | None = None,
) -> tuple[Path, Path, Path, Path, dict[str, object]]:
    reports: dict[str, dict[str, object]] = {}
    for architecture in ("amd64", "arm64"):
        platform = f"linux/{architecture}"
        fixture_directory = tmp_path / f"oci-{architecture}-{evidence_octet}"
        fixture_directory.mkdir()
        archive, child_digest, config_digest, containerfile = _oci_fixture(
            fixture_directory,
            platform=platform,
            evidence_octet=evidence_octet,
            runtime_octet=runtime_octet,
        )
        reproducibility = _reproducibility_fixture(
            fixture_directory,
            child_digest,
            config_digest,
            platform=platform,
        )
        report = collect_oci_evidence(
            archive_path=archive,
            reproducibility_path=reproducibility,
            platform=platform,
            source_commit=SOURCE_COMMIT,
            containerfile_path=containerfile,
            builder_id=BUILDER_ID,
            output_directory=fixture_directory / "evidence",
        )
        reports[architecture] = report
        tmp_path.joinpath(
            f"release-{architecture}-{evidence_octet}.oci.tar"
        ).write_bytes(archive.read_bytes())
    amd64_report = reports["amd64"]
    arm64_report = reports["arm64"]
    amd64_path = tmp_path / f"amd64-{evidence_octet}.json"
    arm64_path = tmp_path / f"arm64-{evidence_octet}.json"
    amd64_path.write_text(json.dumps(amd64_report))
    arm64_path.write_text(json.dumps(arm64_report))
    index_path = tmp_path / f"index-{evidence_octet}.json"
    evidence_path = tmp_path / f"index-evidence-{evidence_octet}.json"
    compose_multi_platform_index(
        amd64_evidence_path=amd64_path,
        arm64_evidence_path=arm64_path,
        source_commit=SOURCE_COMMIT,
        index_output=index_path,
        evidence_output=evidence_path,
    )
    if checked_identity_path is None or checked_receipt_path is None:
        checked_identity_path, checked_receipt_path = (
            _write_provisional_checked_authority(tmp_path)
        )
    candidate_identity = tmp_path / f"candidate-identity-{evidence_octet}.json"
    candidate_receipt = tmp_path / f"candidate-receipt-{evidence_octet}.json"
    prepare_release_identity(
        checked_identity_path=checked_identity_path,
        checked_receipt_path=checked_receipt_path,
        index_evidence_path=evidence_path,
        index_path=index_path,
        source_directory=SOURCE_DIRECTORY,
        repository_root=RELEASE_PACKAGE_ROOT,
        candidate_output=candidate_identity,
        candidate_receipt_output=candidate_receipt,
    )
    return (
        candidate_identity,
        candidate_receipt,
        index_path,
        evidence_path,
        reports,
    )


def _github_release_verification_document(
    candidate: dict[str, object],
    *,
    release_id: int,
) -> dict[str, object]:
    preservation = candidate["preservation"]
    build_run = candidate["buildRun"]
    platforms = candidate["platforms"]
    assert isinstance(preservation, dict)
    assert isinstance(build_run, dict)
    assert isinstance(platforms, list)
    tag = preservation["releaseTag"]
    source_commit = build_run["sourceCommit"]
    purl = f"pkg:github/{NATIVE_RELEASE_REPOSITORY}@{tag}"
    subjects = [{"digest": {"sha1": source_commit}, "uri": purl}]
    for platform in platforms:
        assert isinstance(platform, dict)
        architecture = platform["platform"].split("/", 1)[1]
        subjects.append(
            {
                "digest": {
                    "sha256": platform["ociArchive"]["sha256"].removeprefix(
                        "sha256:"
                    )
                },
                "name": f"ofarm-ed25519-linux-{architecture}.oci.tar",
            }
        )
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subjects,
        "predicateType": "https://in-toto.io/attestation/release/v0.1",
        "predicate": {
            "ownerId": "12345",
            "purl": purl,
            "releaseId": str(release_id),
            "repository": NATIVE_RELEASE_REPOSITORY,
            "repositoryId": str(NATIVE_RELEASE_REPOSITORY_ID),
            "tag": tag,
        },
    }
    return {
        "attestation": {
            "bundle": {
                "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
                "verificationMaterial": {
                    "timestampVerificationData": {
                        "rfc3161Timestamps": [
                            {
                                "signedTimestamp": base64.b64encode(
                                    b"fixture timestamp"
                                ).decode()
                            }
                        ]
                    },
                    "certificate": {
                        "rawBytes": base64.b64encode(
                            b"fixture certificate"
                        ).decode()
                    },
                },
                "dsseEnvelope": {
                    "payload": base64.b64encode(_json_bytes(statement)).decode(),
                    "payloadType": "application/vnd.in-toto+json",
                    "signatures": [
                        {
                            "sig": base64.b64encode(
                                b"fixture signature"
                            ).decode()
                        }
                    ],
                },
            },
            "bundle_url": (
                "https://tmaproduction.blob.core.windows.net/attestations/"
                f"{NATIVE_RELEASE_REPOSITORY_ID}/2026/07/19/12345.json.sn?"
                "se=2026-07-20T00%3A00%3A00Z&sig=Zml4dHVyZQ%3D%3D&"
                "ske=2026-07-20T00%3A00%3A00Z&"
                "skoid=11111111-1111-4111-8111-111111111111&sks=b&"
                "skt=2026-07-19T00%3A00%3A00Z&"
                "sktid=22222222-2222-4222-8222-222222222222&"
                "skv=2026-06-06&sp=r&spr=https&sr=b&"
                "st=2026-07-19T00%3A00%3A00Z&sv=2026-06-06"
            ),
            "initiator": "github",
        },
        "verificationResult": {
            "mediaType": (
                "application/vnd.dev.sigstore.verificationresult+json;version=0.1"
            ),
            "statement": statement,
            "signature": {
                "certificate": {
                    "certificateIssuer": (
                        "CN=Fulcio Intermediate l1,O=GitHub\\, Inc."
                    ),
                    "subjectAlternativeName": (
                        "https://dotcom.releases.github.com"
                    ),
                }
            },
            "verifiedTimestamps": [
                {
                    "type": "TimestampAuthority",
                    "uri": "timestamp.githubapp.com",
                    "timestamp": "2026-07-19T00:00:00Z",
                }
            ],
            "verifiedIdentity": {
                "issuer": {"issuer": "", "regexp": ".*"},
                "subjectAlternativeName": {
                    "regexp": r"^https://dotcom\.releases\.github\.com$",
                    "subjectAlternativeName": "",
                },
            },
        },
    }


def _install_github_release_fixture(
    monkeypatch: pytest.MonkeyPatch,
    candidate_receipt_path: Path,
    *,
    evidence_octet: str = "a",
    mutation=None,
) -> tuple[dict[str, object], list[tuple[str, ...]]]:
    candidate = json.loads(candidate_receipt_path.read_bytes())
    tag = candidate["preservation"]["releaseTag"]
    source_commit = candidate["buildRun"]["sourceCommit"]
    release_id = 101
    raw_assets = []
    archives: dict[str, bytes] = {}
    for asset_id, (platform, asset) in enumerate(
        zip(candidate["platforms"], candidate["preservation"]["assets"], strict=True),
        start=201,
    ):
        raw_assets.append(
            {
                "apiUrl": (
                    f"{NATIVE_RELEASE_REPOSITORY_API_URL}/releases/assets/{asset_id}"
                ),
                "id": asset_id,
                "name": asset["name"],
                "nodeId": f"ASSET_{asset_id}",
                "sha256": asset["sha256"],
                "size": asset["size"],
                "state": "uploaded",
                "url": asset["url"],
            }
        )
        architecture = platform["platform"].split("/", 1)[1]
        archives[asset["name"]] = candidate_receipt_path.parent.joinpath(
            f"release-{architecture}-{evidence_octet}.oci.tar"
        ).read_bytes()
    release_attestation = _github_release_verification_document(
        candidate,
        release_id=release_id,
    )
    state: dict[str, object] = {
        "repository": {
            "apiUrl": NATIVE_RELEASE_REPOSITORY_API_URL,
            "id": NATIVE_RELEASE_REPOSITORY_ID,
            "name": NATIVE_RELEASE_REPOSITORY,
            "nodeId": NATIVE_RELEASE_REPOSITORY_NODE_ID,
            "url": NATIVE_RELEASE_REPOSITORY_URL,
        },
        "immutableReleases": {"enabled": True, "enforcedByOwner": False},
        "release": {
            "apiUrl": f"{NATIVE_RELEASE_REPOSITORY_API_URL}/releases/{release_id}",
            "assets": raw_assets,
            "draft": False,
            "htmlUrl": f"{NATIVE_RELEASE_REPOSITORY_URL}/releases/tag/{tag}",
            "id": release_id,
            "immutable": True,
            "nodeId": "RELEASE_101",
            "prerelease": True,
            "tagName": tag,
            "targetCommitish": source_commit,
        },
        "peeled": {"sha": source_commit},
        "archives": archives,
        "releaseAttestation": release_attestation,
        "githubCliPathResolutions": 0,
        "githubCliPaths": [],
    }
    if mutation is not None:
        mutation(state)
    calls: list[tuple[str, ...]] = []

    def fake_run(
        arguments: tuple[str, ...],
        *,
        label: str,
        timeout_seconds: int = native_evidence.GITHUB_API_TIMEOUT_SECONDS,
        github_cli: Path | None = None,
    ) -> bytes:
        del label, timeout_seconds
        assert github_cli is not None
        state["githubCliPaths"].append(github_cli)
        calls.append(arguments)
        if arguments == ("version",):
            return state.get(
                "versionOutput", NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT
            )
        if arguments[0] == "api":
            endpoint = next(
                argument
                for argument in arguments
                if argument == "repos/samovers/OFARM2"
                or argument.startswith("repos/samovers/OFARM2/")
            )
            if endpoint == "repos/samovers/OFARM2":
                value = state["repository"]
            elif endpoint.endswith("/immutable-releases"):
                value = state["immutableReleases"]
            elif "/releases/tags/" in endpoint:
                value = state["release"]
            elif "/commits/" in endpoint:
                value = state["peeled"]
            else:  # pragma: no cover - fixed command inventory guard
                raise AssertionError(endpoint)
            return _json_bytes(value)
        if arguments[0:2] == ("release", "verify"):
            if state.get("failVerification"):
                raise NativeEvidenceError("GitHub release attestation refused")
            return _json_bytes(state["releaseAttestation"])
        if arguments[0:2] == ("release", "download"):
            directory = Path(arguments[arguments.index("--dir") + 1])
            state["downloadDirectory"] = directory
            state["downloadDirectoryWasEmpty"] = not any(directory.iterdir())
            for name, data in state["archives"].items():
                directory.joinpath(name).write_bytes(data)
            return b""
        if arguments[0:2] == ("release", "verify-asset"):
            if state.get("failAssetVerification"):
                raise NativeEvidenceError("GitHub asset attestation refused")
            state["verifiedAssetCount"] = state.get("verifiedAssetCount", 0) + 1
            if (
                state.get("changeAfterAssetVerification")
                and state["verifiedAssetCount"] == 2
            ):
                release = state["release"]
                release["assets"][0]["size"] += 1
            return _json_bytes(state["releaseAttestation"])
        raise AssertionError(arguments)

    def fake_github_cli_path() -> Path:
        state["githubCliPathResolutions"] += 1
        if state["githubCliPathResolutions"] == 1:
            return Path("/fixture/gh-2.96.0")
        return Path("/fixture/hostile-replacement-gh")

    monkeypatch.setattr(native_evidence, "_github_cli_path", fake_github_cli_path)
    monkeypatch.setattr(native_evidence, "_run_github_cli", fake_run)
    return state, calls


def _fixture_section(
    state: dict[str, object], section: str
) -> dict[str, object]:
    value = state[section]
    assert isinstance(value, dict)
    return value


def _fixture_assets(state: dict[str, object]) -> list[dict[str, object]]:
    value = _fixture_section(state, "release")["assets"]
    assert isinstance(value, list)
    assert all(isinstance(item, dict) for item in value)
    return value


def _duplicate_second_github_asset_identity(state: dict[str, object]) -> None:
    assets = _fixture_assets(state)
    assets[1].update(
        apiUrl=assets[0]["apiUrl"],
        id=assets[0]["id"],
        nodeId=assets[0]["nodeId"],
    )


def _rewrite_provider_verified_statements(
    provider: dict[str, object],
    mutation,
) -> None:
    metadata = provider["metadata"]
    assert isinstance(metadata, dict)
    command_results = [metadata["releaseAttestation"]]
    asset_attestations = metadata["assetAttestations"]
    assert isinstance(asset_attestations, list)
    command_results.extend(
        attestation["verification"] for attestation in asset_attestations
    )
    for command_result in command_results:
        assert isinstance(command_result, dict)
        document = command_result["document"]
        assert isinstance(document, dict)
        verification_result = document["verificationResult"]
        attestation = document["attestation"]
        assert isinstance(verification_result, dict)
        assert isinstance(attestation, dict)
        statement = verification_result["statement"]
        assert isinstance(statement, dict)
        mutation(statement)
        bundle = attestation["bundle"]
        assert isinstance(bundle, dict)
        envelope = bundle["dsseEnvelope"]
        assert isinstance(envelope, dict)
        envelope["payload"] = base64.b64encode(_json_bytes(statement)).decode()
        canonical = release_canonical_json_bytes(document)
        command_result["canonicalDigest"] = _digest(canonical)
        command_result["size"] = len(canonical)


def _replace_release_subject(statement: dict[str, object]) -> None:
    subjects = statement["subject"]
    assert isinstance(subjects, list)
    subjects[0]["digest"]["sha1"] = "0" * 40


def _replace_asset_subject(statement: dict[str, object]) -> None:
    subjects = statement["subject"]
    assert isinstance(subjects, list)
    subjects[1]["digest"]["sha256"] = "0" * 64


def _replace_release_predicate(statement: dict[str, object]) -> None:
    predicate = statement["predicate"]
    assert isinstance(predicate, dict)
    predicate["repository"] = "attacker/OFARM2"


def _rewrite_provider_verified_results(
    provider: dict[str, object],
    mutation,
) -> None:
    metadata = provider["metadata"]
    assert isinstance(metadata, dict)
    command_results = [metadata["releaseAttestation"]]
    asset_attestations = metadata["assetAttestations"]
    assert isinstance(asset_attestations, list)
    command_results.extend(
        attestation["verification"] for attestation in asset_attestations
    )
    for command_result in command_results:
        assert isinstance(command_result, dict)
        document = command_result["document"]
        assert isinstance(document, dict)
        verification_result = document["verificationResult"]
        assert isinstance(verification_result, dict)
        mutation(verification_result)
        canonical = release_canonical_json_bytes(document)
        command_result["canonicalDigest"] = _digest(canonical)
        command_result["size"] = len(canonical)


def _rewrite_provider_documents(
    provider: dict[str, object],
    mutation,
) -> None:
    metadata = provider["metadata"]
    assert isinstance(metadata, dict)
    command_results = [metadata["releaseAttestation"]]
    asset_attestations = metadata["assetAttestations"]
    assert isinstance(asset_attestations, list)
    command_results.extend(
        attestation["verification"] for attestation in asset_attestations
    )
    for command_result in command_results:
        assert isinstance(command_result, dict)
        document = command_result["document"]
        assert isinstance(document, dict)
        mutation(document)
        canonical = release_canonical_json_bytes(document)
        command_result["canonicalDigest"] = _digest(canonical)
        command_result["size"] = len(canonical)


def _replace_verified_certificate_san(
    verification_result: dict[str, object],
) -> None:
    certificate = verification_result["signature"]["certificate"]
    certificate["subjectAlternativeName"] = "https://attacker.example.test"


def _replace_verified_identity_policy(
    verification_result: dict[str, object],
) -> None:
    identity = verification_result["verifiedIdentity"]
    identity["issuer"]["regexp"] = "^attacker$"


def _replace_verified_timestamp_uri(
    verification_result: dict[str, object],
) -> None:
    verification_result["verifiedTimestamps"][0]["uri"] = (
        "https://timestamp.githubapp.com"
    )


def _replace_verified_timestamp_encoding(
    verification_result: dict[str, object],
) -> None:
    verification_result["verifiedTimestamps"][0]["timestamp"] = (
        "2026-07-19T00:00:00.000Z"
    )


def _replace_bundle_url(document: dict[str, object]) -> None:
    document["attestation"]["bundle_url"] = (
        "https://attacker.example.test/attestations/fixture?sig=hostile"
    )


def _replace_one_asset_command_bundle(provider: dict[str, object]) -> None:
    metadata = provider["metadata"]
    assert isinstance(metadata, dict)
    asset_attestations = metadata["assetAttestations"]
    assert isinstance(asset_attestations, list)
    verification = asset_attestations[0]["verification"]
    document = verification["document"]
    certificate = document["attestation"]["bundle"]["verificationMaterial"][
        "certificate"
    ]
    certificate["rawBytes"] = base64.b64encode(
        b"different valid fixture certificate"
    ).decode()
    canonical = release_canonical_json_bytes(document)
    verification["canonicalDigest"] = _digest(canonical)
    verification["size"] = len(canonical)


def test_github_cli_uses_one_bounded_direct_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "gh"
    executable.write_bytes(b"trusted fixture\n")
    executable.chmod(0o755)
    calls = []

    def fake_subprocess_run(command, **kwargs):
        calls.append((command, kwargs))
        return native_evidence.subprocess.CompletedProcess(
            command,
            0,
            stdout=b'{"ok":true}\n',
            stderr=b"",
        )

    monkeypatch.setattr(native_evidence, "_github_cli_path", lambda: executable)
    monkeypatch.setattr(native_evidence.subprocess, "run", fake_subprocess_run)
    arguments = (
        "api",
        "--hostname",
        "github.com",
        "repos/samovers/OFARM2",
    )

    assert native_evidence._run_github_cli(arguments, label="fixture") == (
        b'{"ok":true}\n'
    )
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command == (str(executable), *arguments)
    assert isinstance(command, tuple)
    assert kwargs["shell"] is False
    assert kwargs["check"] is False
    assert kwargs["stdout"] is native_evidence.subprocess.PIPE
    assert kwargs["stderr"] is native_evidence.subprocess.PIPE
    assert kwargs["env"]["GH_HOST"] == "github.com"
    assert kwargs["env"]["GH_REPO"] == NATIVE_RELEASE_REPOSITORY
    assert kwargs["env"]["GH_PROMPT_DISABLED"] == "1"

    with pytest.raises(NativeEvidenceError, match="arguments are not exact"):
        native_evidence._run_github_cli(
            ("api", "repos/samovers/OFARM2\n--method=DELETE"),
            label="hostile fixture",
        )
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("stdout", "stderr", "returncode", "message"),
    (
        (
            b"x" * (native_evidence.MAX_GITHUB_COMMAND_OUTPUT_BYTES + 1),
            b"",
            0,
            "output exceeds",
        ),
        (
            b"",
            b"x" * (native_evidence.MAX_GITHUB_COMMAND_OUTPUT_BYTES + 1),
            0,
            "output exceeds",
        ),
        (b"{}\n", b"warning", 0, "wrote to standard error"),
        (b"", b"provider refusal", 1, "refused"),
    ),
)
def test_github_cli_refuses_failure_and_oversized_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout: bytes,
    stderr: bytes,
    returncode: int,
    message: str,
) -> None:
    executable = tmp_path / "gh"
    executable.write_bytes(b"trusted fixture\n")
    executable.chmod(0o755)
    monkeypatch.setattr(native_evidence, "_github_cli_path", lambda: executable)
    monkeypatch.setattr(
        native_evidence.subprocess,
        "run",
        lambda command, **_kwargs: native_evidence.subprocess.CompletedProcess(
            command,
            returncode,
            stdout=stdout,
            stderr=stderr,
        ),
    )

    with pytest.raises(NativeEvidenceError, match=message):
        native_evidence._run_github_cli(("version",), label="fixture")


@pytest.mark.parametrize(
    ("data", "message"),
    (
        (b"", "invalid size"),
        (
            b"x" * (native_evidence.MAX_GITHUB_JSON_BYTES + 1),
            "invalid size",
        ),
        (b'{"value":1,"value":2}', "duplicate object key"),
        (b'{"value":NaN}', "forbidden number"),
        (b"\xff", "not UTF-8"),
    ),
)
def test_github_json_is_bounded_and_exact(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    message: str,
) -> None:
    monkeypatch.setattr(
        native_evidence,
        "_run_github_cli",
        lambda *_args, **_kwargs: data,
    )

    with pytest.raises(NativeEvidenceError, match=message):
        native_evidence._run_github_json(("api",), label="fixture")


def test_github_api_command_is_fixed_to_the_release_repository() -> None:
    arguments = native_evidence._github_api_arguments(
        "repos/samovers/OFARM2",
        "{id:.id}",
    )

    assert arguments[0:5] == (
        "api",
        "--hostname",
        "github.com",
        "--method",
        "GET",
    )
    assert "Accept: application/vnd.github+json" in arguments
    assert (
        f"X-GitHub-Api-Version: {native_evidence.NATIVE_RELEASE_GITHUB_API_VERSION}"
        in arguments
    )
    assert "repos/samovers/OFARM2" in arguments
    with pytest.raises(NativeEvidenceError, match="fixed repository"):
        native_evidence._github_api_arguments(
            "repos/attacker/OFARM2/releases",
            "{id:.id}",
        )


def _oci_fixture(
    tmp_path: Path,
    *,
    platform: str = PLATFORM,
    evidence_octet: str = "a",
    runtime_octet: str = "stable",
    hostile_subject: bool = False,
    extra_subject: bool = False,
    unreferenced_blob: bool = False,
    hostile_layer_media_type: bool = False,
    incomplete_spdx: bool = False,
    duplicate_spdx_conflict: bool = False,
    minimal_provenance: bool = False,
    duplicate_material_conflict: str | None = None,
    empty_builder: bool = False,
):
    manifest_media_type = "application/vnd.oci.image.manifest.v1+json"
    config_media_type = "application/vnd.oci.image.config.v1+json"
    layer_media_type = "application/vnd.oci.image.layer.v1.tar+gzip"
    attestation_media_type = "application/vnd.in-toto+json"

    blobs: dict[str, bytes] = {}

    def remember(data: bytes) -> bytes:
        blobs[_digest(data)] = data
        return data

    architecture = platform.split("/", 1)[1]
    runtime_config = remember(
        _json_bytes(
            {
                "architecture": architecture,
                "os": "linux",
                "runtimeFixture": runtime_octet,
            }
        )
    )
    runtime_layer = remember(b"runtime layer")
    runtime_manifest = remember(
        _json_bytes(
            {
                "schemaVersion": 2,
                "mediaType": manifest_media_type,
                "config": _descriptor(runtime_config, config_media_type),
                "layers": [
                    _descriptor(
                        runtime_layer,
                        "application/example" if hostile_layer_media_type else layer_media_type,
                    )
                ],
            }
        )
    )
    runtime_digest = _digest(runtime_manifest)
    subject_digest = "0" * 64 if hostile_subject else runtime_digest.removeprefix(
        "sha256:"
    )

    def statement(predicate_type: str) -> bytes:
        subjects = [
            {
                "name": (
                    f"pkg:docker/ofarm-ed25519-evidence@{architecture}?"
                    f"platform=linux%2F{architecture}"
                ),
                "digest": {"sha256": subject_digest},
            }
        ]
        if extra_subject:
            subjects.append(
                {"name": "unrelated", "digest": {"sha256": runtime_digest[7:]}}
            )
        if predicate_type == "https://spdx.dev/Document":
            predicate = (
                {}
                if incomplete_spdx
                else {
                    "spdxVersion": "SPDX-2.3",
                    "dataLicense": "CC0-1.0",
                    "SPDXID": "SPDXRef-DOCUMENT",
                    "name": "ofarm-ed25519",
                    "documentNamespace": (
                        "https://example.test/spdx/ofarm-ed25519/"
                        + evidence_octet
                    ),
                    "creationInfo": {
                        "created": "1970-01-01T00:00:00Z",
                        "creators": ["Tool: buildkit-test"],
                    },
                    "packages": [
                        {
                            "SPDXID": "SPDXRef-Package-postgresql",
                            "name": "postgresql-17",
                            "versionInfo": "17.10-1.pgdg13+1",
                        }
                    ],
                }
            )
            if duplicate_spdx_conflict and not incomplete_spdx:
                predicate["packages"].append(
                    {
                        "SPDXID": "SPDXRef-Package-postgresql-conflict",
                        "name": "postgresql-17",
                        "versionInfo": "17.9-conflict",
                    }
                )
        else:
            predicate = {
                "builder": {"id": "" if empty_builder else BUILDER_ID},
                "buildType": "https://mobyproject.org/buildkit@v1",
                "materials": [
                    {
                        "uri": "pkg:docker/postgres@17",
                        "digest": {"sha256": "3" * 64},
                    },
                    {
                        "uri": (
                            "https://download.libsodium.org/libsodium/releases/"
                            "libsodium-1.0.22.tar.gz"
                        ),
                        "digest": {
                            "sha256": (
                                "adbdd8f16149e81ac6078a03aca6fc03b592b89ef7b5ed83841c086"
                                "191be3349"
                            )
                        },
                    },
                    {
                        "uri": (
                            SERVER_DEV_SOURCES[platform][0]
                        ),
                        "digest": {
                            "sha256": SERVER_DEV_SOURCES[platform][1]
                        },
                    },
                ],
                "invocation": {
                    "configSource": {"entryPoint": "Containerfile"},
                    "parameters": {
                        "frontend": "gateway.v0",
                        "args": {},
                        "locals": [{"name": "context"}],
                    },
                    "environment": {"platform": platform},
                },
                "metadata": {
                    "buildInvocationID": "fixture-build",
                    "buildStartedOn": "1970-01-01T00:00:00Z",
                    "buildFinishedOn": "1970-01-01T00:00:01Z",
                    "reproducible": True,
                    "completeness": {
                        "parameters": True,
                        "environment": True,
                        "materials": False,
                    },
                    "https://mobyproject.org/buildkit@v1#metadata": (
                        {}
                        if minimal_provenance
                        else {
                            "source": {
                                "infos": [
                                    {
                                        "filename": "Containerfile",
                                        "data": base64.b64encode(
                                            CONTAINERFILE_BYTES
                                        ).decode(),
                                    }
                                ],
                                "locations": {"step0": {"locations": []}},
                            }
                        }
                    ),
                },
            }
            if duplicate_material_conflict is not None:
                material_by_kind = {
                    "libsodium": predicate["materials"][1],
                    "server-dev": predicate["materials"][2],
                }
                conflicting = dict(material_by_kind[duplicate_material_conflict])
                conflicting["digest"] = {"sha256": "f" * 64}
                predicate["materials"].append(conflicting)
            if not minimal_provenance:
                predicate["buildConfig"] = {"llbDefinition": [{"id": "step0"}]}
        return remember(
            _json_bytes(
                {
                    "_type": "https://in-toto.io/Statement/v0.1",
                    "subject": subjects,
                    "predicateType": predicate_type,
                    "predicate": predicate,
                }
            )
        )

    sbom = statement("https://spdx.dev/Document")
    provenance = statement("https://slsa.dev/provenance/v0.2")
    attestation_config = remember(b"{}")
    attestation_manifest = remember(
        _json_bytes(
            {
                "schemaVersion": 2,
                "mediaType": manifest_media_type,
                "config": _descriptor(attestation_config, config_media_type),
                "layers": [
                    _descriptor(
                        sbom,
                        attestation_media_type,
                        annotations={
                            "in-toto.io/predicate-type": "https://spdx.dev/Document"
                        },
                    ),
                    _descriptor(
                        provenance,
                        attestation_media_type,
                        annotations={
                            "in-toto.io/predicate-type": (
                                "https://slsa.dev/provenance/v0.2"
                            )
                        },
                    ),
                ],
            }
        )
    )
    if unreferenced_blob:
        remember(b"unreferenced hostile blob")
    runtime_descriptor = _descriptor(
        runtime_manifest,
        manifest_media_type,
        platform={"os": "linux", "architecture": architecture},
    )
    attestation_descriptor = _descriptor(
        attestation_manifest,
        manifest_media_type,
        platform={"os": "unknown", "architecture": "unknown"},
        annotations={
            "vnd.docker.reference.digest": runtime_digest,
            "vnd.docker.reference.type": "attestation-manifest",
        },
    )
    image_index = remember(
        _json_bytes(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.index.v1+json",
                "manifests": [runtime_descriptor, attestation_descriptor],
            }
        )
    )
    index = _json_bytes(
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [
                _descriptor(
                    image_index,
                    "application/vnd.oci.image.index.v1+json",
                    annotations={
                        "org.opencontainers.image.created": "1970-01-01T00:00:00Z"
                    },
                )
            ],
        }
    )
    layout = _json_bytes({"imageLayoutVersion": "1.0.0"})
    archive = tmp_path / "native.oci.tar"
    with tarfile.open(archive, "w") as output:
        for name in ("blobs", "blobs/sha256"):
            member = tarfile.TarInfo(name)
            member.type = tarfile.DIRTYPE
            output.addfile(member)
        files = {"oci-layout": layout, "index.json": index}
        files.update(
            {
                "blobs/sha256/" + digest.removeprefix("sha256:"): data
                for digest, data in blobs.items()
            }
        )
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            output.addfile(member, io.BytesIO(data))
    containerfile = tmp_path / "Containerfile"
    containerfile.write_bytes(CONTAINERFILE_BYTES)
    return archive, runtime_digest, _digest(runtime_config), containerfile


def test_two_clean_builds_require_exact_child_and_installed_artifacts(tmp_path):
    digest = "sha256:" + "a" * 64
    config_digest = "sha256:" + "b" * 64
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_artifacts(first)
    _write_artifacts(second)
    first_metadata = tmp_path / "first.json"
    second_metadata = tmp_path / "second.json"
    _write_metadata(first_metadata, digest, config_digest)
    _write_metadata(second_metadata, digest, config_digest)
    output = tmp_path / "report.json"

    report = compare_builds(
        first_metadata=first_metadata,
        second_metadata=second_metadata,
        first_artifacts=first,
        second_artifacts=second,
        platform=PLATFORM,
        source_commit=SOURCE_COMMIT,
        output=output,
    )

    assert report["child_digest"] == digest
    assert json.loads(output.read_bytes()) == report
    (second / "ofarm_ed25519.so").write_bytes(b"different")
    with pytest.raises(NativeEvidenceError, match="different installed artifacts"):
        compare_builds(
            first_metadata=first_metadata,
            second_metadata=second_metadata,
            first_artifacts=first,
            second_artifacts=second,
            platform=PLATFORM,
            source_commit=SOURCE_COMMIT,
            output=output,
        )


def test_attested_oci_child_must_equal_both_clean_builds(tmp_path):
    archive, child_digest, config_digest, containerfile = _oci_fixture(tmp_path)
    reproducibility = _reproducibility_fixture(
        tmp_path, child_digest, config_digest
    )
    output_directory = tmp_path / "evidence"

    report = collect_oci_evidence(
        archive_path=archive,
        reproducibility_path=reproducibility,
        platform=PLATFORM,
        source_commit=SOURCE_COMMIT,
        containerfile_path=containerfile,
        builder_id=BUILDER_ID,
        output_directory=output_directory,
    )

    assert report["runtime_child_digest"] == child_digest
    assert report["runtime_child_size"] > 0
    assert report["attestation_manifest_size"] > 0
    assert [artifact["name"] for artifact in report["artifacts"]] == list(ARTIFACTS)
    assert (output_directory / "sbom.spdx.in-toto.json").is_file()
    assert (output_directory / "provenance.slsa-v0.2.in-toto.json").is_file()
    assert json.loads(output_directory.joinpath("oci-evidence.json").read_bytes()) == report


def test_attestation_with_unrelated_subject_refuses(tmp_path):
    archive, child_digest, config_digest, containerfile = _oci_fixture(
        tmp_path, hostile_subject=True
    )
    reproducibility = _reproducibility_fixture(
        tmp_path, child_digest, config_digest
    )

    with pytest.raises(NativeEvidenceError, match="authenticate the runtime child"):
        collect_oci_evidence(
            archive_path=archive,
            reproducibility_path=reproducibility,
            platform=PLATFORM,
            source_commit=SOURCE_COMMIT,
            containerfile_path=containerfile,
            builder_id=BUILDER_ID,
            output_directory=tmp_path / "evidence",
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ({"extra_subject": True}, "exactly one subject"),
        ({"unreferenced_blob": True}, "unreferenced blob"),
        ({"hostile_layer_media_type": True}, "layer media type is not exact"),
        ({"incomplete_spdx": True}, "SPDX 2.3 document"),
        (
            {"duplicate_spdx_conflict": True},
            "PostgreSQL runtime package identity is ambiguous",
        ),
        ({"minimal_provenance": True}, "build configuration"),
        (
            {"duplicate_material_conflict": "libsodium"},
            "archive source identity is ambiguous",
        ),
        (
            {"duplicate_material_conflict": "server-dev"},
            "archive source identity is ambiguous",
        ),
        ({"empty_builder": True}, "builder identity"),
    ),
)
def test_oci_evidence_refuses_ambiguous_or_label_only_claims(
    tmp_path, mutation, message
):
    archive, child_digest, config_digest, containerfile = _oci_fixture(
        tmp_path, **mutation
    )
    reproducibility = _reproducibility_fixture(
        tmp_path, child_digest, config_digest
    )

    with pytest.raises(NativeEvidenceError, match=message):
        collect_oci_evidence(
            archive_path=archive,
            reproducibility_path=reproducibility,
            platform=PLATFORM,
            source_commit=SOURCE_COMMIT,
            containerfile_path=containerfile,
            builder_id=BUILDER_ID,
            output_directory=tmp_path / "evidence",
        )


def test_duplicate_metadata_key_refuses(tmp_path):
    digest = "sha256:" + "a" * 64
    config_digest = "sha256:" + "b" * 64
    duplicate_metadata = tmp_path / "duplicate.json"
    duplicate_metadata.write_text(
        "{"
        f'"containerimage.digest":"{digest}",'
        f'"containerimage.digest":"{digest}",'
        f'"containerimage.config.digest":"{config_digest}"'
        "}"
    )
    valid_metadata = tmp_path / "valid.json"
    _write_metadata(valid_metadata, digest, config_digest)
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_artifacts(first)
    _write_artifacts(second)

    with pytest.raises(NativeEvidenceError, match="duplicate object key"):
        compare_builds(
            first_metadata=duplicate_metadata,
            second_metadata=valid_metadata,
            first_artifacts=first,
            second_artifacts=second,
            platform=PLATFORM,
            source_commit=SOURCE_COMMIT,
            output=tmp_path / "report.json",
        )


def test_metadata_index_digest_cannot_pose_as_runtime_child(tmp_path):
    digest = "sha256:" + "a" * 64
    config_digest = "sha256:" + "b" * 64
    metadata = tmp_path / "index.json"
    _write_metadata(metadata, digest, config_digest)
    value = json.loads(metadata.read_bytes())
    value["containerimage.descriptor"]["mediaType"] = (
        "application/vnd.oci.image.index.v1+json"
    )
    metadata.write_text(json.dumps(value))
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_artifacts(first)
    _write_artifacts(second)

    with pytest.raises(NativeEvidenceError, match="index instead of one runtime child"):
        compare_builds(
            first_metadata=metadata,
            second_metadata=metadata,
            first_artifacts=first,
            second_artifacts=second,
            platform=PLATFORM,
            source_commit=SOURCE_COMMIT,
            output=tmp_path / "report.json",
        )


def test_installed_artifact_mode_is_absolute_not_merely_equal(tmp_path):
    digest = "sha256:" + "a" * 64
    config_digest = "sha256:" + "b" * 64
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_artifacts(first)
    _write_artifacts(second)
    first.joinpath("ofarm_ed25519.so").chmod(0o700)
    second.joinpath("ofarm_ed25519.so").chmod(0o700)
    first_metadata = tmp_path / "first.json"
    second_metadata = tmp_path / "second.json"
    _write_metadata(first_metadata, digest, config_digest)
    _write_metadata(second_metadata, digest, config_digest)

    with pytest.raises(NativeEvidenceError, match="mode is not 0755"):
        compare_builds(
            first_metadata=first_metadata,
            second_metadata=second_metadata,
            first_artifacts=first,
            second_artifacts=second,
            platform=PLATFORM,
            source_commit=SOURCE_COMMIT,
            output=tmp_path / "report.json",
        )


def test_symlinked_build_metadata_refuses(tmp_path):
    metadata = tmp_path / "metadata.json"
    digest = "sha256:" + "a" * 64
    config_digest = "sha256:" + "b" * 64
    _write_metadata(metadata, digest, config_digest)
    symlink = tmp_path / "metadata-link.json"
    symlink.symlink_to(metadata)
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_artifacts(first)
    _write_artifacts(second)

    with pytest.raises(NativeEvidenceError, match="must be one regular file"):
        compare_builds(
            first_metadata=symlink,
            second_metadata=metadata,
            first_artifacts=first,
            second_artifacts=second,
            platform=PLATFORM,
            source_commit=SOURCE_COMMIT,
            output=tmp_path / "report.json",
        )


def test_two_native_reports_compose_one_canonical_platform_index(tmp_path):
    amd64_report = _native_oci_report("linux/amd64", "1")
    arm64_report = _native_oci_report("linux/arm64", "2")
    amd64_path = tmp_path / "amd64.json"
    arm64_path = tmp_path / "arm64.json"
    amd64_path.write_text(json.dumps(amd64_report))
    arm64_path.write_text(json.dumps(arm64_report))
    index_path = tmp_path / "index.json"
    evidence_path = tmp_path / "index-evidence.json"

    evidence = compose_multi_platform_index(
        amd64_evidence_path=amd64_path,
        arm64_evidence_path=arm64_path,
        source_commit=SOURCE_COMMIT,
        index_output=index_path,
        evidence_output=evidence_path,
    )

    index_bytes = index_path.read_bytes()
    index = json.loads(index_bytes)
    assert index_bytes.endswith(b"\n")
    assert [descriptor["platform"] for descriptor in index["manifests"]] == [
        {"architecture": "amd64", "os": "linux"},
        {"architecture": "arm64", "os": "linux"},
    ]
    assert evidence["index"] == {
        "media_type": "application/vnd.oci.image.index.v1+json",
        "sha256": _digest(index_bytes),
        "size": len(index_bytes),
    }
    assert evidence["workflow_action_pins"] == CURRENT_NATIVE_ACTION_PINS
    assert evidence["build_pins"] == CURRENT_NATIVE_BUILD_PINS
    assert evidence["schema"] == "ofarm.native-multi-platform-index-evidence.v2"
    assert evidence["platforms"][0]["oci_archive"] == amd64_report["oci_archive"]
    assert evidence["platforms"][0]["attestation_manifest"] == {
        "sha256": amd64_report["attestation_manifest_digest"],
        "size": amd64_report["attestation_manifest_size"],
    }
    assert evidence["platforms"][0]["sbom"] == amd64_report["sbom"]
    assert evidence["platforms"][0]["provenance"] == amd64_report["provenance"]
    assert json.loads(evidence_path.read_bytes()) == evidence


def test_checked_native_release_identity_matches_every_current_source() -> None:
    identity = load_native_release_identity(verify_current_sources=True)

    assert identity.status in {"provisional", "frozen"}
    assert identity.digest == _digest(identity.canonical_bytes)
    assert identity.manifest() == json.loads(identity.canonical_bytes)
    source_paths = [
        item["path"] for item in identity.document["sourceInput"]["files"]
    ]
    assert source_paths == list(NATIVE_SOURCE_PATHS)
    assert "ofarm_ed25519_fault_test.sql" in source_paths
    assert "ofarm_ed25519_vectors.json" in source_paths
    assert identity.document["workflowActionPins"] == CURRENT_NATIVE_ACTION_PINS


def test_checked_native_evidence_receipt_matches_current_authority() -> None:
    identity = load_native_release_identity(verify_current_sources=True)
    receipt = load_native_evidence_receipt(
        EVIDENCE_RECEIPT_PATH,
        release_identity=identity,
        verify_current_authority=True,
        repository_root=RELEASE_PACKAGE_ROOT,
    )

    assert receipt.status == identity.status
    assert receipt.document["releaseIdentityDigest"] == identity.digest
    assert receipt.document["buildPins"] == CURRENT_NATIVE_BUILD_PINS
    assert [
        item["path"]
        for item in receipt.document["evidenceAuthorityInput"]["files"]
    ] == list(EVIDENCE_AUTHORITY_PATHS)
    assert receipt.document["evidenceAuthorityInput"] == (
        evidence_authority_input_manifest(RELEASE_PACKAGE_ROOT)
    )
    if receipt.status == "provisional":
        assert receipt.document["buildRun"] is None
        assert receipt.document["platforms"] == []
        assert receipt.document["preservation"] is None


def test_native_release_identity_refuses_source_drift(tmp_path: Path) -> None:
    source_copy = tmp_path / "source"
    shutil.copytree(SOURCE_DIRECTORY, source_copy)
    identity_path = tmp_path / "identity.json"
    identity_path.write_bytes(
        release_canonical_json_bytes(provisional_identity_document(source_copy))
    )
    source_copy.joinpath("ofarm_ed25519_fault_test.sql").write_bytes(
        b"-- hostile replacement\n"
    )

    with pytest.raises(NativeReleaseIdentityError, match="current files"):
        load_native_release_identity(
            identity_path,
            verify_current_sources=True,
            source_directory=source_copy,
        )


def test_native_evidence_receipt_refuses_authority_source_drift(
    tmp_path: Path,
) -> None:
    authority_root = tmp_path / "authority"
    for relative_path in EVIDENCE_AUTHORITY_PATHS:
        destination = authority_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RELEASE_PACKAGE_ROOT / relative_path, destination)
    identity_document = provisional_identity_document(SOURCE_DIRECTORY)
    identity_bytes = release_canonical_json_bytes(identity_document)
    identity = validate_native_release_identity(
        identity_document,
        canonical_bytes=identity_bytes,
        source_directory=SOURCE_DIRECTORY,
    )
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_bytes(
        release_canonical_json_bytes(
            provisional_evidence_receipt_document(
                release_identity=identity,
                repository_root=authority_root,
            )
        )
    )
    drift_path = authority_root / "deployment/postgresql/native_evidence.py"
    drift_path.write_bytes(drift_path.read_bytes() + b"\n# hostile drift\n")

    with pytest.raises(NativeReleaseIdentityError, match="current files"):
        load_native_evidence_receipt(
            receipt_path,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=authority_root,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda receipt: receipt.update(unexpected=True),
            "fields are not exact",
        ),
        (
            lambda receipt: receipt.update(
                releaseIdentityDigest="sha256:" + "0" * 64
            ),
            "not linked",
        ),
        (
            lambda receipt: receipt["platforms"][0]["sbom"].update(
                predicateType="https://example.test/not-spdx"
            ),
            "predicate is not exact",
        ),
        (
            lambda receipt: receipt["platforms"][0]["ociArchive"].update(
                size=True
            ),
            "OCI archive size is invalid",
        ),
        (
            lambda receipt: receipt["platforms"][0].update(
                runtimeChildDigest="sha256:" + "0" * 64
            ),
            "receipt runtime identity differs",
        ),
        (
            lambda receipt: receipt["platforms"][0]["artifacts"][0].update(
                sha256="sha256:" + "0" * 64
            ),
            "receipt runtime identity differs",
        ),
        (
            lambda receipt: receipt["preservation"].update(
                releaseUrl="https://example.test/hostile"
            ),
            "preservation reference is inconsistent",
        ),
        (
            lambda receipt: receipt["preservation"].update(
                providerVerification={}
            ),
            "candidate evidence receipt contains provider verification",
        ),
        (
            lambda receipt: receipt["buildRun"]["actionsEvidence"].update(
                retentionDays=90
            ),
            "temporary Actions evidence reference is inconsistent",
        ),
    ),
)
def test_candidate_evidence_receipt_refuses_schema_and_claim_mutation(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    candidate_identity_path, candidate_receipt_path, _, _, _ = _prepare_candidate(
        tmp_path
    )
    identity = load_native_release_identity(
        candidate_identity_path,
        verify_current_sources=True,
        source_directory=SOURCE_DIRECTORY,
    )
    receipt_document = json.loads(candidate_receipt_path.read_bytes())
    mutation(receipt_document)
    candidate_receipt_path.write_bytes(
        release_canonical_json_bytes(receipt_document)
    )

    with pytest.raises(NativeReleaseIdentityError, match=message):
        load_native_evidence_receipt(
            candidate_receipt_path,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=RELEASE_PACKAGE_ROOT,
            allow_candidate=True,
        )


def test_hosted_fan_in_emits_one_frozen_candidate_identity(tmp_path: Path) -> None:
    amd64_path = tmp_path / "amd64.json"
    arm64_path = tmp_path / "arm64.json"
    amd64_path.write_text(json.dumps(_native_oci_report("linux/amd64", "1")))
    arm64_path.write_text(json.dumps(_native_oci_report("linux/arm64", "2")))
    index_path = tmp_path / "index.json"
    evidence_path = tmp_path / "index-evidence.json"
    compose_multi_platform_index(
        amd64_evidence_path=amd64_path,
        arm64_evidence_path=arm64_path,
        source_commit=SOURCE_COMMIT,
        index_output=index_path,
        evidence_output=evidence_path,
    )
    provisional_path, provisional_receipt_path = (
        _write_provisional_checked_authority(tmp_path)
    )
    candidate_path = tmp_path / "candidate.json"
    candidate_receipt_path = tmp_path / "candidate-receipt.json"

    result = prepare_release_identity(
        checked_identity_path=provisional_path,
        checked_receipt_path=provisional_receipt_path,
        index_evidence_path=evidence_path,
        index_path=index_path,
        source_directory=SOURCE_DIRECTORY,
        repository_root=RELEASE_PACKAGE_ROOT,
        candidate_output=candidate_path,
        candidate_receipt_output=candidate_receipt_path,
    )
    candidate = load_native_release_identity(
        candidate_path,
        verify_current_sources=True,
        source_directory=SOURCE_DIRECTORY,
    )

    assert result == {
        "checked_status": "provisional",
        "checked_receipt_status": "provisional",
        "candidate_digest": candidate.digest,
        "candidate_index_digest": candidate.index_digest,
        "candidate_receipt_digest": _digest(candidate_receipt_path.read_bytes()),
    }
    assert candidate.status == "frozen"
    assert candidate.document["index"]["canonicalBytesBase64"] == (
        base64.b64encode(index_path.read_bytes()).decode("ascii")
    )
    assert [item["platform"] for item in candidate.document["platforms"]] == [
        "linux/amd64",
        "linux/arm64",
    ]
    receipt = load_native_evidence_receipt(
        candidate_receipt_path,
        release_identity=candidate,
        verify_current_authority=True,
        repository_root=RELEASE_PACKAGE_ROOT,
        allow_candidate=True,
    )
    assert receipt.status == "candidate"
    assert receipt.document["releaseIdentityDigest"] == candidate.digest
    for receipt_platform, identity_platform in zip(
        receipt.document["platforms"],
        candidate.document["platforms"],
        strict=True,
    ):
        assert receipt_platform["runtimeChildDigest"] == identity_platform[
            "runtimeChildDigest"
        ]
        assert receipt_platform["runtimeChildSize"] == identity_platform[
            "runtimeChildSize"
        ]
        assert receipt_platform["runtimeConfigDigest"] == identity_platform[
            "runtimeConfigDigest"
        ]
        assert receipt_platform["artifacts"] == identity_platform["artifacts"]
    assert receipt.document["preservation"]["status"] == "pending"
    assert receipt.document["preservation"]["providerVerification"] is None
    assert receipt.document["preservation"]["releaseKind"] == "prerelease"
    assert receipt.document["preservation"]["releaseTag"] == (
        "native-verifier-" + candidate.digest.removeprefix("sha256:")
    )
    assert [
        asset["url"] for asset in receipt.document["preservation"]["assets"]
    ] == [
        (
            "https://github.com/samovers/OFARM2/releases/download/"
            f"native-verifier-{candidate.digest.removeprefix('sha256:')}/"
            "ofarm-ed25519-linux-amd64.oci.tar"
        ),
        (
            "https://github.com/samovers/OFARM2/releases/download/"
            f"native-verifier-{candidate.digest.removeprefix('sha256:')}/"
            "ofarm-ed25519-linux-arm64.oci.tar"
        ),
    ]


def test_immutable_github_release_freezes_durable_receipt_and_blocks_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        candidate_identity_path,
        candidate_receipt_path,
        _,
        _,
        reports,
    ) = _prepare_candidate(tmp_path, evidence_octet="a")
    _state, calls = _install_github_release_fixture(
        monkeypatch,
        candidate_receipt_path,
        evidence_octet="a",
    )
    frozen_receipt_path = tmp_path / "frozen-receipt.json"

    result = finalize_evidence_receipt(
        release_identity_path=candidate_identity_path,
        candidate_receipt_path=candidate_receipt_path,
        source_directory=SOURCE_DIRECTORY,
        repository_root=RELEASE_PACKAGE_ROOT,
        output=frozen_receipt_path,
    )
    identity = load_native_release_identity(
        candidate_identity_path,
        verify_current_sources=True,
        source_directory=SOURCE_DIRECTORY,
    )
    frozen_receipt = load_native_evidence_receipt(
        frozen_receipt_path,
        release_identity=identity,
        verify_current_authority=True,
        repository_root=RELEASE_PACKAGE_ROOT,
    )

    assert result["status"] == "frozen"
    assert result["release_identity_digest"] == identity.digest
    assert frozen_receipt.status == "frozen"
    assert frozen_receipt.document["preservation"]["status"] == "verified"
    provider = frozen_receipt.document["preservation"]["providerVerification"]
    assert provider["schemaVersion"] == (
        "ofarm.github-release-provider-verification.v1"
    )
    assert provider["canonicalDigest"] == _digest(
        release_canonical_json_bytes(provider["metadata"])
    )
    assert provider["metadata"]["immutableReleases"]["enabled"] is True
    assert provider["metadata"]["repository"]["id"] == (
        NATIVE_RELEASE_REPOSITORY_ID
    )
    assert provider["metadata"]["repository"]["nodeId"] == (
        NATIVE_RELEASE_REPOSITORY_NODE_ID
    )
    assert provider["metadata"]["release"]["immutable"] is True
    assert provider["metadata"]["release"]["targetCommitish"] == SOURCE_COMMIT
    assert provider["metadata"]["release"]["peeledTagCommit"] == SOURCE_COMMIT
    assert [
        asset["id"] for asset in provider["metadata"]["release"]["assets"]
    ] == [201, 202]
    assert frozen_receipt.document["platforms"][0]["ociArchive"] == reports[
        "amd64"
    ]["oci_archive"]
    assert calls[0] == ("version",)
    assert any(call[0:2] == ("release", "download") for call in calls)
    assert sum(call[0:2] == ("release", "verify-asset") for call in calls) == 2
    assert _state["githubCliPathResolutions"] == 1
    assert set(_state["githubCliPaths"]) == {Path("/fixture/gh-2.96.0")}
    assert _state["downloadDirectoryWasEmpty"] is True
    assert not _state["downloadDirectory"].exists()
    download_call = next(
        call for call in calls if call[0:2] == ("release", "download")
    )
    assert "--clobber" not in download_call
    for call in calls:
        if call[0] == "release":
            assert call[call.index("--repo") + 1] == NATIVE_RELEASE_REPOSITORY

    fresh_directory = tmp_path / "fresh-rerun"
    fresh_directory.mkdir()
    fresh_identity_path, fresh_receipt_path, _, _, _ = _prepare_candidate(
        fresh_directory,
        evidence_octet="b",
        checked_identity_path=candidate_identity_path,
        checked_receipt_path=frozen_receipt_path,
    )
    assert fresh_identity_path.read_bytes() == candidate_identity_path.read_bytes()
    fresh_receipt = load_native_evidence_receipt(
        fresh_receipt_path,
        release_identity=identity,
        verify_current_authority=True,
        repository_root=RELEASE_PACKAGE_ROOT,
        allow_candidate=True,
    )
    assert fresh_receipt.status == "frozen"
    assert fresh_receipt_path.read_bytes() == frozen_receipt_path.read_bytes()
    assert fresh_receipt.document["releaseIdentityDigest"] == identity.digest


def test_receipt_finalization_refuses_mutated_release_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_identity, candidate_receipt, _, _, _ = _prepare_candidate(tmp_path)
    _install_github_release_fixture(
        monkeypatch,
        candidate_receipt,
        mutation=lambda state: state["archives"].update(
            {"ofarm-ed25519-linux-amd64.oci.tar": b"mutated archive"}
        ),
    )

    with pytest.raises(NativeEvidenceError, match="Release download differs"):
        finalize_evidence_receipt(
            release_identity_path=candidate_identity,
            candidate_receipt_path=candidate_receipt,
            source_directory=SOURCE_DIRECTORY,
            repository_root=RELEASE_PACKAGE_ROOT,
            output=tmp_path / "must-not-exist.json",
        )


def test_receipt_finalization_reauthenticates_a_self_consistent_alternate_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first"
    alternate = tmp_path / "alternate"
    first.mkdir()
    alternate.mkdir()
    candidate_identity, candidate_receipt, _, _, _ = _prepare_candidate(
        first,
        evidence_octet="a",
    )
    _, alternate_receipt, _, _, _ = _prepare_candidate(
        alternate,
        evidence_octet="b",
        runtime_octet="different-runtime",
    )
    candidate_document = json.loads(candidate_receipt.read_bytes())
    alternate_document = json.loads(alternate_receipt.read_bytes())
    for candidate_platform, alternate_platform, preserved_asset in zip(
        candidate_document["platforms"],
        alternate_document["platforms"],
        candidate_document["preservation"]["assets"],
        strict=True,
    ):
        for field in (
            "attestationManifest",
            "ociArchive",
            "provenance",
            "sbom",
            "sourceImageIndexDigest",
        ):
            candidate_platform[field] = alternate_platform[field]
        preserved_asset["sha256"] = alternate_platform["ociArchive"]["sha256"]
        preserved_asset["size"] = alternate_platform["ociArchive"]["size"]
        architecture = candidate_platform["platform"].split("/", 1)[1]
        shutil.copyfile(
            alternate / f"release-{architecture}-b.oci.tar",
            first / f"release-{architecture}-b.oci.tar",
        )
    candidate_receipt.write_bytes(
        release_canonical_json_bytes(candidate_document)
    )
    _install_github_release_fixture(
        monkeypatch,
        candidate_receipt,
        evidence_octet="b",
    )

    with pytest.raises(NativeEvidenceError, match="OCI evidence differs"):
        finalize_evidence_receipt(
            release_identity_path=candidate_identity,
            candidate_receipt_path=candidate_receipt,
            source_directory=SOURCE_DIRECTORY,
            repository_root=RELEASE_PACKAGE_ROOT,
            output=tmp_path / "must-not-exist.json",
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda state: state.update(versionOutput=b"gh version 2.87.2\n"),
            "CLI version is not exact",
        ),
        (
            lambda state: _fixture_section(state, "repository").update(id=1),
            "repository identity is not exact",
        ),
        (
            lambda state: _fixture_section(state, "repository").update(
                nodeId="R_hostile"
            ),
            "repository identity is not exact",
        ),
        (
            lambda state: _fixture_section(state, "immutableReleases").update(
                enabled=False
            ),
            "immutable releases are not enabled",
        ),
        (
            lambda state: _fixture_section(state, "release").update(
                immutable=False
            ),
            "release identity is inconsistent",
        ),
        (
            lambda state: _fixture_section(state, "release").update(draft=True),
            "release identity is inconsistent",
        ),
        (
            lambda state: _fixture_section(state, "release").update(
                prerelease=False
            ),
            "release identity is inconsistent",
        ),
        (
            lambda state: _fixture_section(state, "release").update(
                targetCommitish="0" * 40
            ),
            "release identity is inconsistent",
        ),
        (
            lambda state: _fixture_section(state, "release").update(
                tagName="native-verifier-" + "0" * 64
            ),
            "release identity is inconsistent",
        ),
        (
            lambda state: _fixture_section(state, "release").update(
                htmlUrl="https://github.com/samovers/OFARM2/releases/tag/hostile"
            ),
            "release identity is inconsistent",
        ),
        (
            lambda state: _fixture_section(state, "peeled").update(sha="0" * 40),
            "tag target is inconsistent",
        ),
        (
            lambda state: _fixture_assets(state).append(
                dict(_fixture_assets(state)[0])
            ),
            "asset set is not exact",
        ),
        (
            _duplicate_second_github_asset_identity,
            "asset identities are not exact",
        ),
        (
            lambda state: _fixture_assets(state)[0].update(id=999),
            "asset identity is inconsistent",
        ),
        (
            lambda state: _fixture_assets(state)[0].update(name="hostile.oci.tar"),
            "asset is absent",
        ),
        (
            lambda state: _fixture_assets(state)[0].update(size=999),
            "asset identity is inconsistent",
        ),
        (
            lambda state: _fixture_assets(state)[0].update(
                sha256="sha256:" + "0" * 64
            ),
            "asset identity is inconsistent",
        ),
        (
            lambda state: _fixture_assets(state)[0].update(
                url="https://example.test/hostile.oci.tar"
            ),
            "asset identity is inconsistent",
        ),
        (
            lambda state: state.update(failVerification=True),
            "release attestation refused",
        ),
        (
            lambda state: state.update(failAssetVerification=True),
            "asset attestation refused",
        ),
        (
            lambda state: state.update(changeAfterAssetVerification=True),
            "release state changed during verification",
        ),
    ),
)
def test_receipt_finalization_refuses_hostile_github_release_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation,
    message: str,
) -> None:
    candidate_identity, candidate_receipt, _, _, _ = _prepare_candidate(tmp_path)
    _install_github_release_fixture(
        monkeypatch,
        candidate_receipt,
        mutation=mutation,
    )
    output = tmp_path / "must-not-exist.json"

    with pytest.raises(NativeEvidenceError, match=message):
        finalize_evidence_receipt(
            release_identity_path=candidate_identity,
            candidate_receipt_path=candidate_receipt,
            source_directory=SOURCE_DIRECTORY,
            repository_root=RELEASE_PACKAGE_ROOT,
            output=output,
        )
    assert not output.exists()


def test_receipt_finalization_refuses_differing_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_identity, candidate_receipt, _, _, _ = _prepare_candidate(tmp_path)
    _install_github_release_fixture(monkeypatch, candidate_receipt)
    output = tmp_path / "frozen-receipt.json"
    finalize_evidence_receipt(
        release_identity_path=candidate_identity,
        candidate_receipt_path=candidate_receipt,
        source_directory=SOURCE_DIRECTORY,
        repository_root=RELEASE_PACKAGE_ROOT,
        output=output,
    )
    output.write_bytes(b"{}\n")

    with pytest.raises(NativeEvidenceError, match="existing.*differs"):
        finalize_evidence_receipt(
            release_identity_path=candidate_identity,
            candidate_receipt_path=candidate_receipt,
            source_directory=SOURCE_DIRECTORY,
            repository_root=RELEASE_PACKAGE_ROOT,
            output=output,
        )
    assert output.read_bytes() == b"{}\n"


def test_receipt_finalization_never_clobbers_a_concurrent_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_identity, candidate_receipt, _, _, _ = _prepare_candidate(tmp_path)
    _install_github_release_fixture(monkeypatch, candidate_receipt)
    output = tmp_path / "frozen-receipt.json"
    concurrent_bytes = b'{"concurrent":"authority"}\n'
    real_link = native_evidence.os.link
    raced = False

    def publish_after_concurrent_writer(source, destination, *args, **kwargs):
        nonlocal raced
        if Path(destination) == output and not raced:
            output.write_bytes(concurrent_bytes)
            raced = True
        return real_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(
        native_evidence.os,
        "link",
        publish_after_concurrent_writer,
    )

    with pytest.raises(NativeEvidenceError, match="existing.*differs"):
        finalize_evidence_receipt(
            release_identity_path=candidate_identity,
            candidate_receipt_path=candidate_receipt,
            source_directory=SOURCE_DIRECTORY,
            repository_root=RELEASE_PACKAGE_ROOT,
            output=output,
        )
    assert raced is True
    assert output.read_bytes() == concurrent_bytes


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda provider: provider.update(unexpected=True),
            "provider-verification fields are not exact",
        ),
        (
            lambda provider: provider["metadata"]["repository"].update(id=1),
            "repository is not exact",
        ),
        (
            lambda provider: provider["metadata"]["githubCli"].update(
                version="2.87.2"
            ),
            "CLI identity is not exact",
        ),
        (
            lambda provider: provider["metadata"]["immutableReleases"].update(
                enabled=False
            ),
            "immutable releases were not enabled",
        ),
        (
            lambda provider: provider["metadata"]["release"].update(
                immutable=False
            ),
            "verified-release identity is inconsistent",
        ),
        (
            lambda provider: provider["metadata"]["release"]["assets"][0].update(
                id=999
            ),
            "verified-release asset identity is inconsistent",
        ),
        (
            lambda provider: provider["metadata"]["assetAttestations"].reverse(),
            "asset-attestation order is not exact",
        ),
        (
            lambda provider: provider["metadata"]["releaseAttestation"][
                "document"
            ].update(hostile=True),
            "result fields are not exact",
        ),
        (
            lambda provider: _rewrite_provider_verified_statements(
                provider, _replace_release_subject
            ),
            "repository/tag/asset subjects are inconsistent",
        ),
        (
            lambda provider: _rewrite_provider_verified_statements(
                provider, _replace_asset_subject
            ),
            "repository/tag/asset subjects are inconsistent",
        ),
        (
            lambda provider: _rewrite_provider_verified_statements(
                provider, _replace_release_predicate
            ),
            "repository/tag predicate is inconsistent",
        ),
        (
            lambda provider: _rewrite_provider_verified_results(
                provider, _replace_verified_certificate_san
            ),
            "verified certificate identity is not exact",
        ),
        (
            lambda provider: _rewrite_provider_verified_results(
                provider, _replace_verified_identity_policy
            ),
            "verified identity shape is not exact",
        ),
        (
            lambda provider: _rewrite_provider_verified_results(
                provider, _replace_verified_timestamp_uri
            ),
            "verified timestamp URI is not exact",
        ),
        (
            lambda provider: _rewrite_provider_verified_results(
                provider, _replace_verified_timestamp_encoding
            ),
            "verified timestamp is not canonical UTC RFC3339Nano",
        ),
        (
            lambda provider: _rewrite_provider_documents(
                provider, _replace_bundle_url
            ),
            "bundle URL is not exact",
        ),
        (
            _replace_one_asset_command_bundle,
            "differs from the verified release attestation",
        ),
    ),
)
def test_frozen_receipt_refuses_provider_verification_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation,
    message: str,
) -> None:
    candidate_identity, candidate_receipt, _, _, _ = _prepare_candidate(tmp_path)
    _install_github_release_fixture(monkeypatch, candidate_receipt)
    output = tmp_path / "frozen-receipt.json"
    finalize_evidence_receipt(
        release_identity_path=candidate_identity,
        candidate_receipt_path=candidate_receipt,
        source_directory=SOURCE_DIRECTORY,
        repository_root=RELEASE_PACKAGE_ROOT,
        output=output,
    )
    document = json.loads(output.read_bytes())
    provider = document["preservation"]["providerVerification"]
    mutation(provider)
    provider["canonicalDigest"] = _digest(
        release_canonical_json_bytes(provider["metadata"])
    )
    output.write_bytes(release_canonical_json_bytes(document))
    identity = load_native_release_identity(
        candidate_identity,
        verify_current_sources=True,
        source_directory=SOURCE_DIRECTORY,
    )

    with pytest.raises(NativeReleaseIdentityError, match=message):
        load_native_evidence_receipt(
            output,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=RELEASE_PACKAGE_ROOT,
        )


def test_conformance_environment_carries_release_status_and_exact_metadata(
    tmp_path: Path,
) -> None:
    identity = load_native_release_identity(verify_current_sources=True)
    if identity.status == "frozen":
        child = identity.document["platforms"][0]["runtimeChildDigest"]
        config = identity.document["platforms"][0]["runtimeConfigDigest"]
    else:
        child = "sha256:" + "1" * 64
        config = "sha256:" + "2" * 64
    metadata = tmp_path / "metadata.json"
    _write_metadata(metadata, child, config)

    environment = conformance_environment(
        checked_identity_path=IDENTITY_PATH,
        checked_receipt_path=EVIDENCE_RECEIPT_PATH,
        metadata_path=metadata,
        source_directory=SOURCE_DIRECTORY,
        repository_root=RELEASE_PACKAGE_ROOT,
        image_name="ofarm-postgresql-conformance:local",
        metadata_reference=".artifacts/derived-postgresql/metadata.json",
    )

    assert f"ISSUE174_DERIVED_POSTGRES_CHILD_DIGEST={child}\n" in environment
    assert f"ISSUE174_DERIVED_POSTGRES_CONFIG_DIGEST={config}\n" in environment
    assert (
        f"ISSUE174_DERIVED_POSTGRES_IDENTITY_STATUS={identity.status}\n"
        in environment
    )
    receipt = load_native_evidence_receipt(
        release_identity=identity,
        verify_current_authority=True,
        repository_root=RELEASE_PACKAGE_ROOT,
    )
    assert (
        f"ISSUE174_DERIVED_POSTGRES_EVIDENCE_RECEIPT_DIGEST={receipt.digest}\n"
        in environment
    )
    assert (
        f"ISSUE174_DERIVED_POSTGRES_EVIDENCE_RECEIPT_STATUS={receipt.status}\n"
        in environment
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda report: report.update(platform="linux/amd64"), "identity"),
        (lambda report: report.update(builder_id=BUILDER_ID + "/other"), "builder"),
        (lambda report: report.pop("artifacts"), "fields are not exact"),
        (
            lambda report: report.update(runtime_child_size=True),
            "descriptor size",
        ),
        (
            lambda report: report.update(attestation_manifest_size=False),
            "attestation manifest size",
        ),
        (
            lambda report: report["oci_archive"].pop("size"),
            "fields are not exact",
        ),
        (
            lambda report: report["sbom"].update(
                predicate_type="https://example.test/not-spdx"
            ),
            "predicate is not exact",
        ),
        (
            lambda report: report.update(image_index_digest="not-a-digest"),
            "source image-index digest",
        ),
    ),
)
def test_multi_platform_index_refuses_ambiguous_reports(
    tmp_path, mutation, message
):
    amd64_report = _native_oci_report("linux/amd64", "1")
    arm64_report = _native_oci_report("linux/arm64", "2")
    mutation(arm64_report)
    amd64_path = tmp_path / "amd64.json"
    arm64_path = tmp_path / "arm64.json"
    amd64_path.write_text(json.dumps(amd64_report))
    arm64_path.write_text(json.dumps(arm64_report))

    with pytest.raises(NativeEvidenceError, match=message):
        compose_multi_platform_index(
            amd64_evidence_path=amd64_path,
            arm64_evidence_path=arm64_path,
            source_commit=SOURCE_COMMIT,
            index_output=tmp_path / "index.json",
            evidence_output=tmp_path / "evidence.json",
        )


def test_native_workflow_closes_both_native_platform_evidence_lanes():
    workflow = PACKAGE_ROOT.joinpath(".github/workflows/conformance.yml").read_text()
    action_lines = re.findall(
        r"^\s*(?:-\s*)?uses:\s*(.+)$", workflow, re.MULTILINE
    )
    observed_action_pins: dict[str, str] = {}
    for action_line in action_lines:
        match = re.fullmatch(
            r"([^@\s]+)@([0-9a-f]{40})\s+#\s+(v[0-9]+)",
            action_line,
        )
        assert match is not None
        action_name, commit, version = match.groups()
        logical_name = f"{action_name}@{version}"
        assert observed_action_pins.setdefault(logical_name, commit) == commit

    assert action_lines
    assert observed_action_pins == CURRENT_NATIVE_ACTION_PINS
    assert CURRENT_NATIVE_BUILD_PINS["buildxClient"] == {
        "version": "v0.34.1",
        "sourceCommit": "e0b0e77d18d3379bc1e0d55f3b37de288d36fe47",
    }
    assert "services:" not in workflow
    assert "ubuntu-24.04-arm" in workflow
    assert "ubuntu-24.04" in workflow
    assert "setup-qemu" not in workflow
    assert workflow.count("version: v0.34.1") == 2
    assert "docker buildx version | awk" not in workflow
    assert workflow.count('test "$(docker buildx version)" =') == 2
    assert workflow.count(
        "e0b0e77d18d3379bc1e0d55f3b37de288d36fe47"
    ) == 2
    assert "test \"$(uname -m)\"" in workflow
    assert workflow.count("--no-cache") >= 4
    assert "SANITIZER=memory" in workflow
    assert 'for sanitizer in address undefined' in workflow
    sanitizer_step = workflow.split(
        "- name: Run AddressSanitizer and UndefinedBehaviorSanitizer", 1
    )[1].split("- name: Exercise every verifier failure mapping", 1)[0]
    assert "shell: bash" in sanitizer_step
    assert sanitizer_step.index("set -o pipefail") < sanitizer_step.index("| tee")
    failure_step = workflow.split(
        "- name: Exercise every verifier failure mapping", 1
    )[1].split("- name: Produce two clean native child builds", 1)[0]
    assert "--target failure-semantics" in failure_step
    assert "--no-cache" in failure_step
    clean_build_step = workflow.split(
        "- name: Produce two clean native child builds", 1
    )[1].split("- name: Prove child and installed-artifact reproducibility", 1)[0]
    assert clean_build_step.count('--output "type=docker,oci-mediatypes=true"') == 1
    assert "--load" not in clean_build_step
    assert "--metadata-file" in clean_build_step
    assert '--tag "ofarm-ed25519-${{ matrix.architecture }}:${build}"' in (
        clean_build_step
    )
    assert '--platform "linux/${{ matrix.architecture }}"' in clean_build_step
    vector_step = workflow.split(
        "- name: Authenticate generated native verifier vectors", 1
    )[1].split("- name: Require a native runner", 1)[0]
    assert "generate_ofarm_ed25519_vectors.py" in vector_step
    assert "--check" in vector_step
    assert "ofarm_ed25519_live_test.sql" in workflow
    assert "compare-builds" in workflow
    assert "type=provenance,mode=max,version=v0.2,builder-id=" in workflow
    assert "timeout-minutes: 120" in workflow
    assert "ofarm-ed25519-evidence:${{ matrix.architecture }}" in workflow
    assert (
        "docker/buildkit-syft-scanner@sha256:"
        "79e7b013cbec16bbb436f312819a49a4a57752b2270c1a9332ae1a10fcc82a68"
    ) in workflow
    assert "collect-oci" in workflow
    assert "compose-index" in workflow
    assert "prepare-release-identity" in workflow
    assert "native_release_identity.candidate.json" in workflow
    assert "native_evidence_receipt.json" in workflow
    assert "native_evidence_receipt.candidate.json" in workflow
    assert "conformance-environment" in workflow
    assert 'cat .artifacts/derived-postgresql/environment >> "$GITHUB_ENV"' in workflow
    assert "REPLACE_WITH_FROZEN" not in workflow
    assert "SOURCE_DATE_EPOCH=0" in workflow
    assert "--image-name ofarm-postgresql-conformance:local" in workflow


def test_native_build_sources_match_evidence_material_authority():
    containerfile = PACKAGE_ROOT.joinpath(
        "deployment/postgresql/ofarm_ed25519/Containerfile"
    ).read_text()

    assert LIBSODIUM_SOURCE_URL in containerfile
    assert LIBSODIUM_SOURCE_SHA256 in containerfile
    for source_url, digest in SERVER_DEV_SOURCES.values():
        assert source_url in containerfile
        assert digest in containerfile
