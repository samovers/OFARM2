"""Hostile tests for bounded native verifier CI evidence."""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path

import pytest

from deployment.postgresql import native_evidence, native_release_identity
from deployment.postgresql.native_evidence import (
    CURRENT_NATIVE_BUILD_PINS,
    CURRENT_NATIVE_REPRODUCER_ACTION_PINS,
    FROZEN_NATIVE_RELEASE_ACTION_PINS,
    LIBSODIUM_SOURCE_SHA256,
    LIBSODIUM_SOURCE_URL,
    NativeEvidenceError,
    SERVER_DEV_SOURCES,
    collect_oci_evidence,
    compare_builds,
    conformance_environment,
    compose_multi_platform_index,
    direct_oci_child_identity,
    docker_transport_child_identity,
    finalize_evidence_receipt,
    prepare_release_identity,
    verify_frozen_evidence_receipt,
)
from deployment.postgresql.native_release_identity import (
    EVIDENCE_AUTHORITY_PATHS,
    EVIDENCE_RECEIPT_PATH,
    NATIVE_SOURCE_PATHS,
    NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT,
    NATIVE_RELEASE_OWNER_ID,
    NATIVE_RELEASE_REPOSITORY,
    NATIVE_RELEASE_REPOSITORY_API_URL,
    NATIVE_RELEASE_REPOSITORY_ID,
    NATIVE_RELEASE_REPOSITORY_NODE_ID,
    NATIVE_RELEASE_REPOSITORY_URL,
    PACKAGE_ROOT as RELEASE_PACKAGE_ROOT,
    SOURCE_DIRECTORY,
    NativeEvidenceReceipt,
    NativeReleaseIdentity,
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


def _candidate_digest_from_frozen(document: dict[str, object]) -> str:
    candidate = json.loads(release_canonical_json_bytes(document))
    candidate.pop("candidateReceiptDigest")
    candidate.pop("verificationAuthorityInput")
    candidate["schemaVersion"] = native_release_identity.EVIDENCE_RECEIPT_SCHEMA_V1
    candidate["status"] = "candidate"
    candidate["preservation"]["status"] = "pending"
    candidate["preservation"]["providerVerification"] = None
    return _digest(release_canonical_json_bytes(candidate))


def _different_authority_snapshot(value: dict[str, object]) -> dict[str, object]:
    authority = json.loads(release_canonical_json_bytes(value))
    authority["files"][0]["sha256"] = "sha256:" + "0" * 64
    authority_body = {
        "algorithm": authority["algorithm"],
        "files": authority["files"],
    }
    authority["digest"] = _digest(release_canonical_json_bytes(authority_body))
    return authority


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def test_authority_file_read_is_descriptor_pinned_during_path_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority_path = tmp_path / "authority.json"
    authority_path.write_bytes(b"original")
    replacement_path = tmp_path / "replacement.json"
    replacement_path.write_bytes(b"replacement")
    real_open = os.open

    def open_then_replace(path, flags):
        descriptor = real_open(path, flags)
        os.replace(replacement_path, authority_path)
        return descriptor

    monkeypatch.setattr(native_release_identity.os, "open", open_then_replace)

    assert native_release_identity._read_regular(
        authority_path, 64, "authority"
    ) == b"original"
    assert authority_path.read_bytes() == b"replacement"


def test_authority_file_read_refuses_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(b"original")
    symlink = tmp_path / "authority.json"
    symlink.symlink_to(target)

    with pytest.raises(NativeReleaseIdentityError, match="unavailable"):
        native_release_identity._read_regular(symlink, 64, "authority")


@pytest.mark.parametrize("mutation", ("grow", "truncate"))
def test_authority_file_read_refuses_in_place_size_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(b"original")
    real_read = os.read
    changed = False

    def change_before_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        if not changed:
            changed = True
            if mutation == "grow":
                with target.open("ab") as stream:
                    stream.write(b"-grew")
            else:
                with target.open("r+b") as stream:
                    stream.truncate(1)
        return real_read(descriptor, size)

    monkeypatch.setattr(native_release_identity.os, "read", change_before_read)
    with pytest.raises(NativeReleaseIdentityError, match="changed while reading"):
        native_release_identity._read_regular(target, 64, "authority")


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


def _direct_oci_fixture(
    tmp_path: Path,
    *,
    name: str = "direct",
    platform: str = PLATFORM,
    runtime_octet: str = "stable",
    descriptor_platform: dict[str, str] | None = None,
    omit_descriptor_platform: bool = False,
    config_os: str = "linux",
    config_architecture: str | None = None,
    root_media_type: str = "application/vnd.oci.image.manifest.v1+json",
    manifest_media_type: str = "application/vnd.oci.image.manifest.v1+json",
    config_media_type: str = "application/vnd.oci.image.config.v1+json",
    layer_media_type: str = "application/vnd.oci.image.layer.v1.tar+gzip",
    extra_root: bool = False,
    nested_root: bool = False,
    unreferenced_blob: bool = False,
    root_annotations: dict[str, str] | None = None,
    root_artifact_type: bool = False,
    root_subject: bool = False,
    manifest_artifact_type: bool = False,
    manifest_subject: bool = False,
    corrupt_blob: str | None = None,
    missing_blob: str | None = None,
    wrong_size: str | None = None,
    duplicate_json: str | None = None,
    duplicate_directory: bool = False,
    docker_image_name: str | None = None,
    docker_manifest_mutation: str | None = None,
) -> tuple[Path, str, str]:
    manifest_type = "application/vnd.oci.image.manifest.v1+json"
    index_type = "application/vnd.oci.image.index.v1+json"
    architecture = platform.split("/", 1)[1]
    if config_architecture is None:
        config_architecture = architecture
    blobs: dict[str, bytes] = {}

    def content_descriptor(data: bytes, media_type: str, kind: str) -> dict[str, object]:
        digest = _digest(data)
        stored_digest = digest
        if corrupt_blob == kind:
            stored_digest = "sha256:" + {"config": "7", "layer": "8", "manifest": "9"}[kind] * 64
        if missing_blob != kind:
            blobs[stored_digest] = data
        size = len(data) + (1 if wrong_size == kind else 0)
        return {"mediaType": media_type, "digest": stored_digest, "size": size}

    config_document = _json_bytes(
        {
            "architecture": config_architecture,
            "os": config_os,
            "runtimeFixture": runtime_octet,
        }
    )
    if duplicate_json == "config":
        config_document = config_document.replace(
            b'"architecture":',
            b'"architecture":"hostile","architecture":',
            1,
        )
    config_descriptor = content_descriptor(
        config_document,
        config_media_type,
        "config",
    )
    layers = (b"runtime layer",)
    if docker_manifest_mutation == "reordered-layers":
        layers += (b"runtime metadata layer",)
    layer_descriptors = [
        content_descriptor(layer, layer_media_type, "layer") for layer in layers
    ]
    manifest_document: dict[str, object] = {
        "schemaVersion": 2,
        "mediaType": manifest_media_type,
        "config": config_descriptor,
        "layers": layer_descriptors,
    }
    if manifest_artifact_type:
        manifest_document["artifactType"] = "application/example"
    if manifest_subject:
        manifest_document["subject"] = {
            "mediaType": manifest_type,
            "digest": _digest(config_document),
            "size": len(config_document),
        }
    manifest = _json_bytes(manifest_document)
    if duplicate_json == "manifest":
        manifest = manifest.replace(
            b'"schemaVersion":2',
            b'"schemaVersion":2,"schemaVersion":1',
            1,
        )
    runtime_descriptor = content_descriptor(manifest, root_media_type, "manifest")
    runtime_descriptor["annotations"] = root_annotations or {
        "org.opencontainers.image.ref.name": "fixture"
    }
    if not omit_descriptor_platform:
        runtime_descriptor["platform"] = descriptor_platform or {
            "os": "linux",
            "architecture": architecture,
        }
    if root_artifact_type:
        runtime_descriptor["artifactType"] = "application/example"
    if root_subject:
        runtime_descriptor["subject"] = {
            "mediaType": manifest_type,
            "digest": _digest(manifest),
            "size": len(manifest),
        }
    root_descriptor = runtime_descriptor
    if nested_root:
        nested_index = _json_bytes(
            {
                "schemaVersion": 2,
                "mediaType": index_type,
                "manifests": [runtime_descriptor],
            }
        )
        root_descriptor = content_descriptor(nested_index, index_type, "manifest")
        root_descriptor["annotations"] = {
            "org.opencontainers.image.ref.name": "fixture"
        }
    roots = [root_descriptor]
    if extra_root:
        roots.append(dict(root_descriptor))
    index = _json_bytes(
        {"schemaVersion": 2, "mediaType": index_type, "manifests": roots}
    )
    if duplicate_json == "index":
        index = index.replace(
            b'"schemaVersion":2',
            b'"schemaVersion":2,"schemaVersion":1',
            1,
        )
    if unreferenced_blob:
        hostile = b"unreferenced hostile blob"
        blobs[_digest(hostile)] = hostile
    layout = _json_bytes({"imageLayoutVersion": "1.0.0"})
    archive = tmp_path / (
        f"{name}.docker.tar" if docker_image_name is not None else f"{name}.oci.tar"
    )
    with tarfile.open(archive, "w") as output:
        for directory in (
            "blobs",
            "blobs" if duplicate_directory else None,
            "blobs/sha256",
        ):
            if directory is None:
                continue
            member = tarfile.TarInfo(directory)
            member.type = tarfile.DIRTYPE
            output.addfile(member)
        files = {"oci-layout": layout, "index.json": index}
        files.update(
            {
                "blobs/sha256/" + digest.removeprefix("sha256:"): data
                for digest, data in blobs.items()
            }
        )
        if docker_image_name is not None and docker_manifest_mutation != "missing":
            docker_entry: dict[str, object] = {
                "Config": "blobs/sha256/"
                + str(config_descriptor["digest"]).removeprefix("sha256:"),
                "RepoTags": [docker_image_name],
                "Layers": [
                    "blobs/sha256/"
                    + str(descriptor["digest"]).removeprefix("sha256:")
                    for descriptor in layer_descriptors
                ],
            }
            docker_document: object = [docker_entry]
            if docker_manifest_mutation == "extra-entry":
                docker_document = [docker_entry, dict(docker_entry)]
            elif docker_manifest_mutation == "extra-key":
                docker_entry["Parent"] = ""
            elif docker_manifest_mutation == "missing-key":
                docker_entry.pop("Layers")
            elif docker_manifest_mutation == "wrong-config":
                docker_entry["Config"] = "blobs/sha256/" + "0" * 64
            elif docker_manifest_mutation == "reordered-layers":
                docker_entry["Layers"] = list(reversed(docker_entry["Layers"]))
            elif docker_manifest_mutation == "wrong-layer":
                docker_entry["Layers"] = ["blobs/sha256/" + "0" * 64]
            elif docker_manifest_mutation == "wrong-tag":
                docker_entry["RepoTags"] = ["ofarm-ed25519-amd64:second"]
            elif docker_manifest_mutation == "extra-tag":
                docker_entry["RepoTags"] = [docker_image_name, "hostile:latest"]
            elif docker_manifest_mutation == "nonobject-entry":
                docker_document = [[]]
            elif docker_manifest_mutation == "top-object":
                docker_document = docker_entry
            docker_bytes = _json_bytes(docker_document)
            if docker_manifest_mutation == "duplicate-json":
                docker_bytes = docker_bytes.replace(
                    b'"Config":',
                    b'"Config":"hostile","Config":',
                    1,
                )
            elif docker_manifest_mutation == "malformed":
                docker_bytes = b"{"
            elif docker_manifest_mutation == "oversize":
                docker_bytes = b" " * (64 * 1024 + 1)
            if docker_manifest_mutation != "symlink":
                files["manifest.json"] = docker_bytes
        if docker_manifest_mutation == "extra-file":
            files["repositories"] = b"{}"
        for member_name, data in files.items():
            member = tarfile.TarInfo(member_name)
            member.size = len(data)
            output.addfile(member, io.BytesIO(data))
        if docker_image_name is not None and docker_manifest_mutation == "symlink":
            member = tarfile.TarInfo("manifest.json")
            member.type = tarfile.SYMTYPE
            member.linkname = "index.json"
            output.addfile(member)
    return archive, _digest(manifest), _digest(config_document)


def _reproducibility_fixture(
    tmp_path: Path,
    child_digest: str,
    config_digest: str,
    *,
    platform: str = PLATFORM,
    runtime_octet: str = "stable",
) -> Path:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_artifacts(first)
    _write_artifacts(second)
    architecture = platform.split("/", 1)[1]
    first_archive, observed_child, observed_config = _direct_oci_fixture(
        tmp_path,
        name="first-clean",
        platform=platform,
        runtime_octet=runtime_octet,
        docker_image_name=f"ofarm-ed25519-{architecture}:first",
    )
    second_archive, second_child, second_config = _direct_oci_fixture(
        tmp_path,
        name="second-clean",
        platform=platform,
        runtime_octet=runtime_octet,
        docker_image_name=f"ofarm-ed25519-{architecture}:second",
    )
    assert (observed_child, observed_config) == (child_digest, config_digest)
    assert (second_child, second_config) == (child_digest, config_digest)
    output = tmp_path / "reproducibility.json"
    compare_builds(
        first_archive=first_archive,
        second_archive=second_archive,
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
            runtime_octet=runtime_octet,
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
        "predicateType": "https://in-toto.io/attestation/release/v0.2",
        "predicate": {
            "databaseId": str(release_id),
            "ownerId": NATIVE_RELEASE_OWNER_ID,
            "packageId": str(NATIVE_RELEASE_REPOSITORY_ID),
            "purl": purl,
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
            "bundle_url": "",
            "initiator": "",
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


def _prepare_frozen_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[NativeReleaseIdentity, NativeEvidenceReceipt, Path]:
    candidate_identity_path, candidate_receipt_path, _, _, _ = _prepare_candidate(
        tmp_path
    )
    _install_github_release_fixture(monkeypatch, candidate_receipt_path)
    frozen_path = tmp_path / "frozen-receipt.json"
    finalize_evidence_receipt(
        release_identity_path=candidate_identity_path,
        candidate_receipt_path=candidate_receipt_path,
        source_directory=SOURCE_DIRECTORY,
        repository_root=RELEASE_PACKAGE_ROOT,
        output=frozen_path,
    )
    identity = load_native_release_identity(
        candidate_identity_path,
        verify_current_sources=True,
        source_directory=SOURCE_DIRECTORY,
    )
    receipt = load_native_evidence_receipt(
        frozen_path,
        release_identity=identity,
        verify_current_authority=True,
        repository_root=RELEASE_PACKAGE_ROOT,
    )
    return identity, receipt, frozen_path


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


def _replace_release_predicate_version(statement: dict[str, object]) -> None:
    statement["predicateType"] = "https://in-toto.io/attestation/release/v0.1"
    predicate = statement["predicate"]
    assert isinstance(predicate, dict)
    predicate["releaseId"] = predicate.pop("packageId")
    predicate.pop("databaseId")


def _replace_release_database_id(statement: dict[str, object]) -> None:
    predicate = statement["predicate"]
    assert isinstance(predicate, dict)
    predicate["databaseId"] = "1"


def _replace_release_package_id(statement: dict[str, object]) -> None:
    predicate = statement["predicate"]
    assert isinstance(predicate, dict)
    predicate["packageId"] = "1"


def _replace_release_owner_id(statement: dict[str, object]) -> None:
    predicate = statement["predicate"]
    assert isinstance(predicate, dict)
    predicate["ownerId"] = "1"


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
    document["attestation"]["bundle_url"] = "https://attacker.example.test"


def _replace_initiator(document: dict[str, object]) -> None:
    document["attestation"]["initiator"] = "github"


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


def _write_python_command(tmp_path: Path, source: str) -> Path:
    executable = tmp_path / "gh"
    executable.write_text(
        f"#!{sys.executable}\n{source}",
        encoding="ascii",
    )
    executable.chmod(0o755)
    return executable


def test_github_cli_uses_one_bounded_direct_argv(tmp_path: Path) -> None:
    executable = _write_python_command(
        tmp_path,
        """
import json
import os
import sys

document = {
    "arguments": sys.argv[1:],
    "environment": {
        name: os.environ.get(name)
        for name in ("GH_HOST", "GH_REPO", "GH_PROMPT_DISABLED")
    },
}
sys.stdout.write(json.dumps(document, sort_keys=True, separators=(",", ":")))
""",
    )
    arguments = (
        "api",
        "--hostname",
        "github.com",
        "repos/samovers/OFARM2",
        "literal;exit 99",
    )

    observed = json.loads(
        native_evidence._run_github_cli(
            arguments,
            label="fixture",
            github_cli=executable,
        )
    )
    assert observed == {
        "arguments": list(arguments),
        "environment": {
            "GH_HOST": "github.com",
            "GH_REPO": NATIVE_RELEASE_REPOSITORY,
            "GH_PROMPT_DISABLED": "1",
        },
    }

    with pytest.raises(NativeEvidenceError, match="arguments are not exact"):
        native_evidence._run_github_cli(
            ("api", "repos/samovers/OFARM2\n--method=DELETE"),
            label="hostile fixture",
            github_cli=executable,
        )


@pytest.mark.parametrize(
    ("mode", "message"),
    (
        ("oversized-stdout", "output exceeds"),
        ("oversized-stderr", "output exceeds"),
        ("warning", "wrote to standard error"),
        ("refusal", "refused"),
    ),
)
def test_github_cli_refuses_failure_and_oversized_output(
    tmp_path: Path,
    mode: str,
    message: str,
) -> None:
    executable = _write_python_command(
        tmp_path,
        """
import os
import sys

mode = sys.argv[1]
limit = int(sys.argv[2])
if mode == "oversized-stdout":
    os.write(1, b"x" * (limit + 1))
elif mode == "oversized-stderr":
    os.write(2, b"x" * (limit + 1))
elif mode == "warning":
    os.write(1, b"{}\\n")
    os.write(2, b"warning")
elif mode == "refusal":
    os.write(2, b"provider refusal")
    raise SystemExit(1)
""",
    )

    with pytest.raises(NativeEvidenceError, match=message):
        native_evidence._run_github_cli(
            (mode, str(native_evidence.MAX_GITHUB_COMMAND_OUTPUT_BYTES)),
            label="fixture",
            github_cli=executable,
        )


@pytest.mark.parametrize(
    ("stream_name", "descriptor"),
    (("stdout", 1), ("stderr", 2)),
)
def test_github_cli_stops_and_reaps_endless_output_floods(
    tmp_path: Path,
    stream_name: str,
    descriptor: int,
) -> None:
    executable = _write_python_command(
        tmp_path,
        """
import os
import pathlib
import sys

descriptor = int(sys.argv[1])
pathlib.Path(sys.argv[2]).write_text(str(os.getpid()), encoding="ascii")
block = b"x" * 65536
while True:
    os.write(descriptor, block)
""",
    )
    pid_path = tmp_path / f"{stream_name}.pid"

    with pytest.raises(NativeEvidenceError, match="output exceeds"):
        native_evidence._run_github_cli(
            (str(descriptor), str(pid_path)),
            label=f"endless {stream_name}",
            timeout_seconds=10,
            github_cli=executable,
        )

    child_pid = int(pid_path.read_text(encoding="ascii"))
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


def test_github_cli_timeout_stops_and_reaps_the_child(tmp_path: Path) -> None:
    executable = _write_python_command(
        tmp_path,
        """
import os
import pathlib
import sys
import time

pathlib.Path(sys.argv[1]).write_text(str(os.getpid()), encoding="ascii")
time.sleep(30)
""",
    )
    pid_path = tmp_path / "timeout.pid"

    with pytest.raises(NativeEvidenceError, match="could not execute"):
        native_evidence._run_github_cli(
            (str(pid_path),),
            label="sleeping fixture",
            timeout_seconds=1,
            github_cli=executable,
        )

    child_pid = int(pid_path.read_text(encoding="ascii"))
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


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


@pytest.mark.parametrize("platform", ("linux/amd64", "linux/arm64"))
def test_direct_oci_archive_authenticates_exact_runtime_child(
    tmp_path: Path,
    platform: str,
) -> None:
    archive, child_digest, config_digest = _direct_oci_fixture(
        tmp_path,
        platform=platform,
    )

    assert direct_oci_child_identity(
        archive,
        "clean build",
        platform=platform,
    ) == (child_digest, config_digest)


@pytest.mark.parametrize(
    ("platform", "image_name"),
    (
        ("linux/amd64", "ofarm-ed25519-amd64:first"),
        ("linux/arm64", "ofarm-ed25519-arm64:second"),
        ("linux/amd64", "ofarm-postgresql-conformance:local"),
    ),
)
def test_docker_transport_archive_binds_the_exact_loadable_image(
    tmp_path: Path,
    platform: str,
    image_name: str,
) -> None:
    archive, child_digest, config_digest = _direct_oci_fixture(
        tmp_path,
        platform=platform,
        docker_image_name=image_name,
    )

    assert docker_transport_child_identity(
        archive,
        "loadable image",
        platform=platform,
        image_name=image_name,
    ) == (child_digest, config_digest)

    with pytest.raises(NativeEvidenceError, match="unexpected file"):
        direct_oci_child_identity(archive, "release OCI", platform=platform)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("missing", "is absent"),
        ("extra-entry", "must contain one entry"),
        ("extra-key", "fields are not exact"),
        ("missing-key", "fields are not exact"),
        ("wrong-config", "does not bind"),
        ("reordered-layers", "does not bind"),
        ("wrong-layer", "does not bind"),
        ("wrong-tag", "does not bind"),
        ("extra-tag", "does not bind"),
        ("duplicate-json", "duplicate object key"),
        ("malformed", "not valid JSON"),
        ("nonobject-entry", "must be a JSON object"),
        ("top-object", "must contain one entry"),
        ("symlink", "non-regular member"),
        ("oversize", "exceeds its byte limit"),
        ("extra-file", "unexpected file"),
    ),
)
def test_docker_transport_archive_refuses_an_ambiguous_wrapper(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    image_name = "ofarm-ed25519-amd64:first"
    archive, _, _ = _direct_oci_fixture(
        tmp_path,
        docker_image_name=image_name,
        docker_manifest_mutation=mutation,
    )

    with pytest.raises(NativeEvidenceError, match=message):
        docker_transport_child_identity(
            archive,
            "loadable image",
            platform=PLATFORM,
            image_name=image_name,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ({"corrupt_blob": "config"}, "does not authenticate"),
        ({"corrupt_blob": "layer"}, "does not authenticate"),
        ({"unreferenced_blob": True}, "unreferenced blob"),
        (
            {
                "root_annotations": {
                    "vnd.docker.reference.type": "attestation-manifest"
                }
            },
            "attestation",
        ),
    ),
)
def test_docker_transport_archive_keeps_the_hostile_oci_dag_checks(
    tmp_path: Path,
    mutation: dict[str, object],
    message: str,
) -> None:
    image_name = "ofarm-ed25519-amd64:first"
    archive, _, _ = _direct_oci_fixture(
        tmp_path,
        docker_image_name=image_name,
        **mutation,
    )

    with pytest.raises(NativeEvidenceError, match=message):
        docker_transport_child_identity(
            archive,
            "loadable image",
            platform=PLATFORM,
            image_name=image_name,
        )


def test_docker_transport_archive_requires_oci_media_types_and_a_known_tag(
    tmp_path: Path,
) -> None:
    image_name = "ofarm-ed25519-amd64:first"
    docker_media_type = "application/vnd.docker.distribution.manifest.v2+json"
    archive, _, _ = _direct_oci_fixture(
        tmp_path,
        docker_image_name=image_name,
        root_media_type=docker_media_type,
        manifest_media_type=docker_media_type,
    )

    with pytest.raises(NativeEvidenceError, match="directly reference"):
        docker_transport_child_identity(
            archive,
            "loadable image",
            platform=PLATFORM,
            image_name=image_name,
        )
    with pytest.raises(NativeEvidenceError, match="image name is not allowed"):
        docker_transport_child_identity(
            archive,
            "loadable image",
            platform=PLATFORM,
            image_name="hostile:latest",
        )

    mismatched_archive, _, _ = _direct_oci_fixture(
        tmp_path,
        name="mismatched-platform-tag",
        platform="linux/arm64",
        docker_image_name="ofarm-ed25519-amd64:first",
    )
    with pytest.raises(NativeEvidenceError, match="image name is not allowed"):
        docker_transport_child_identity(
            mismatched_archive,
            "loadable image",
            platform="linux/arm64",
            image_name="ofarm-ed25519-amd64:first",
        )


def test_two_clean_builds_require_exact_child_and_installed_artifacts(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_artifacts(first)
    _write_artifacts(second)
    first_archive, digest, config_digest = _direct_oci_fixture(
        tmp_path,
        name="first",
        docker_image_name="ofarm-ed25519-amd64:first",
    )
    second_archive, second_digest, second_config = _direct_oci_fixture(
        tmp_path,
        name="second",
        docker_image_name="ofarm-ed25519-amd64:second",
    )
    assert (second_digest, second_config) == (digest, config_digest)
    output = tmp_path / "report.json"

    report = compare_builds(
        first_archive=first_archive,
        second_archive=second_archive,
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
            first_archive=first_archive,
            second_archive=second_archive,
            first_artifacts=first,
            second_artifacts=second,
            platform=PLATFORM,
            source_commit=SOURCE_COMMIT,
            output=output,
        )


def test_two_clean_builds_refuse_different_runtime_dags(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_artifacts(first)
    _write_artifacts(second)
    first_archive, _, _ = _direct_oci_fixture(
        tmp_path,
        name="first",
        docker_image_name="ofarm-ed25519-amd64:first",
    )
    second_archive, _, _ = _direct_oci_fixture(
        tmp_path,
        name="second",
        runtime_octet="different",
        docker_image_name="ofarm-ed25519-amd64:second",
    )

    with pytest.raises(NativeEvidenceError, match="different child digests"):
        compare_builds(
            first_archive=first_archive,
            second_archive=second_archive,
            first_artifacts=first,
            second_artifacts=second,
            platform=PLATFORM,
            source_commit=SOURCE_COMMIT,
            output=tmp_path / "report.json",
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
    if mutation.get("hostile_layer_media_type"):
        _, child_digest, config_digest = _direct_oci_fixture(
            tmp_path,
            name="valid-clean-reference",
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


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ({"extra_root": True}, "one direct runtime child"),
        ({"nested_root": True}, "does not directly reference"),
        ({"omit_descriptor_platform": True}, "descriptor platform"),
        (
            {
                "descriptor_platform": {
                    "os": "linux",
                    "architecture": "amd64",
                    "variant": "hostile",
                }
            },
            "descriptor platform",
        ),
        ({"config_architecture": "arm64"}, "config platform"),
        (
            {"root_media_type": "application/vnd.oci.image.index.v1+json"},
            "does not directly reference",
        ),
        ({"manifest_media_type": "application/example"}, "plain image"),
        ({"config_media_type": "application/example"}, "config media type"),
        ({"layer_media_type": "application/example"}, "layer media type"),
        (
            {
                "root_annotations": {
                    "vnd.docker.reference.type": "attestation-manifest"
                }
            },
            "attestation",
        ),
        (
            {
                "root_annotations": {
                    "vnd.docker.reference.digest": "sha256:" + "0" * 64
                }
            },
            "attestation",
        ),
        ({"root_artifact_type": True}, "plain image"),
        ({"root_subject": True}, "plain image"),
        ({"manifest_artifact_type": True}, "plain image"),
        ({"manifest_subject": True}, "plain image"),
        ({"corrupt_blob": "manifest"}, "does not authenticate"),
        ({"corrupt_blob": "config"}, "does not authenticate"),
        ({"corrupt_blob": "layer"}, "does not authenticate"),
        ({"missing_blob": "manifest"}, "absent"),
        ({"missing_blob": "config"}, "absent"),
        ({"missing_blob": "layer"}, "absent"),
        ({"wrong_size": "manifest"}, "does not authenticate"),
        ({"wrong_size": "config"}, "does not authenticate"),
        ({"wrong_size": "layer"}, "does not authenticate"),
        ({"unreferenced_blob": True}, "unreferenced blob"),
        ({"duplicate_json": "index"}, "duplicate object key"),
        ({"duplicate_json": "manifest"}, "duplicate object key"),
        ({"duplicate_json": "config"}, "duplicate object key"),
        ({"duplicate_directory": True}, "unsafe member name"),
    ),
)
def test_direct_oci_archive_refuses_ambiguous_or_unauthenticated_inputs(
    tmp_path: Path,
    mutation: dict[str, object],
    message: str,
) -> None:
    archive, _, _ = _direct_oci_fixture(tmp_path, **mutation)

    with pytest.raises(NativeEvidenceError, match=message):
        direct_oci_child_identity(archive, "clean build", platform=PLATFORM)


def test_installed_artifact_mode_is_absolute_not_merely_equal(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_artifacts(first)
    _write_artifacts(second)
    first.joinpath("ofarm_ed25519.so").chmod(0o700)
    second.joinpath("ofarm_ed25519.so").chmod(0o700)
    first_archive, _, _ = _direct_oci_fixture(
        tmp_path,
        name="first",
        docker_image_name="ofarm-ed25519-amd64:first",
    )
    second_archive, _, _ = _direct_oci_fixture(
        tmp_path,
        name="second",
        docker_image_name="ofarm-ed25519-amd64:second",
    )

    with pytest.raises(NativeEvidenceError, match="mode is not 0755"):
        compare_builds(
            first_archive=first_archive,
            second_archive=second_archive,
            first_artifacts=first,
            second_artifacts=second,
            platform=PLATFORM,
            source_commit=SOURCE_COMMIT,
            output=tmp_path / "report.json",
        )


def test_symlinked_clean_build_archive_refuses(tmp_path):
    archive, _, _ = _direct_oci_fixture(tmp_path)
    symlink = tmp_path / "archive-link.oci.tar"
    symlink.symlink_to(archive)

    with pytest.raises(NativeEvidenceError, match="must be one regular file"):
        direct_oci_child_identity(symlink, "clean build", platform=PLATFORM)


def test_compressed_oci_archive_refuses_before_member_traversal(
    tmp_path: Path,
) -> None:
    member = tarfile.TarInfo("blobs/sha256/" + "0" * 64)
    member.size = native_evidence.MAX_OCI_EXPANDED_BYTES + 1
    archive = tmp_path / "compressed-oversized.oci.tar.gz"
    archive.write_bytes(
        gzip.compress(member.tobuf() + tarfile.NUL * tarfile.BLOCKSIZE * 2)
    )
    assert archive.stat().st_size < 4096

    with pytest.raises(NativeEvidenceError, match="uncompressed tar archive"):
        direct_oci_child_identity(archive, "compressed OCI", platform=PLATFORM)


def test_oci_member_limit_is_enforced_without_materializing_the_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = tmp_path / "header-heavy.oci.tar"
    with tarfile.open(archive, "w") as output:
        for index in range(native_evidence.MAX_OCI_MEMBER_COUNT + 1):
            output.addfile(
                tarfile.TarInfo("blobs/sha256/" + f"{index:064x}")
            )

    def forbid_general_tar_parser(*_args: object, **_kwargs: object) -> None:
        pytest.fail("the OCI verifier invoked the general tar parser")

    monkeypatch.setattr(tarfile, "open", forbid_general_tar_parser)
    with pytest.raises(NativeEvidenceError, match="too many members"):
        native_evidence._OciArchive(archive)


def test_oci_extended_header_refuses_before_its_body_is_processed(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "pax-extension.oci.tar"
    with tarfile.open(archive, "w", format=tarfile.PAX_FORMAT) as output:
        member = tarfile.TarInfo("blobs/sha256/" + "0" * 64)
        member.pax_headers = {"comment": "untrusted extension body"}
        output.addfile(member)

    with pytest.raises(NativeEvidenceError, match="non-regular member"):
        native_evidence._OciArchive(archive)


def test_archive_path_replacement_cannot_separate_hashed_and_parsed_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive, child_digest, config_digest = _direct_oci_fixture(
        tmp_path,
        name="path-authority-a",
        runtime_octet="a",
    )
    replacement, replacement_child, replacement_config = _direct_oci_fixture(
        tmp_path,
        name="path-authority-b",
        runtime_octet="b",
    )
    assert (replacement_child, replacement_config) != (
        child_digest,
        config_digest,
    )

    real_open = native_evidence.os.open
    replaced = False

    def open_then_replace(
        path,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal replaced
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        if Path(path) == archive and not replaced:
            assert flags & native_evidence.os.O_NOFOLLOW
            replaced = True
            replacement.replace(archive)
        return descriptor

    monkeypatch.setattr(native_evidence.os, "open", open_then_replace)

    assert direct_oci_child_identity(
        archive,
        "path replacement",
        platform=PLATFORM,
    ) == (child_digest, config_digest)
    assert replaced is True


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
    assert (
        evidence["release_workflow_action_pins"]
        == FROZEN_NATIVE_RELEASE_ACTION_PINS
    )
    assert (
        evidence["reproducer_workflow_action_pins"]
        == CURRENT_NATIVE_REPRODUCER_ACTION_PINS
    )
    assert evidence["build_pins"] == CURRENT_NATIVE_BUILD_PINS
    assert evidence["schema"] == "ofarm.native-multi-platform-index-evidence.v3"
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
    assert (
        identity.document["workflowActionPins"]
        == FROZEN_NATIVE_RELEASE_ACTION_PINS
    )


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
    if receipt.status == "provisional":
        assert receipt.document["evidenceAuthorityInput"] == (
            evidence_authority_input_manifest(RELEASE_PACKAGE_ROOT)
        )
        assert receipt.document["buildRun"] is None
        assert receipt.document["platforms"] == []
        assert receipt.document["preservation"] is None
    else:
        assert receipt.status == "frozen"
        assert receipt.document["verificationAuthorityInput"] == (
            evidence_authority_input_manifest(RELEASE_PACKAGE_ROOT)
        )


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


def test_finalizer_refuses_an_unapproved_historical_candidate_before_github(
    tmp_path: Path,
) -> None:
    candidate_identity_path, candidate_receipt_path, _, _, _ = _prepare_candidate(
        tmp_path
    )
    candidate = json.loads(candidate_receipt_path.read_bytes())
    authority = candidate["evidenceAuthorityInput"]
    authority["files"][0]["sha256"] = "sha256:" + "0" * 64
    authority_body = {
        "algorithm": authority["algorithm"],
        "files": authority["files"],
    }
    authority["digest"] = _digest(release_canonical_json_bytes(authority_body))
    candidate_receipt_path.write_bytes(release_canonical_json_bytes(candidate))
    output = tmp_path / "must-not-exist.json"

    with pytest.raises(
        NativeEvidenceError,
        match="historical candidate evidence authority is not the exact v1 migration",
    ):
        finalize_evidence_receipt(
            release_identity_path=candidate_identity_path,
            candidate_receipt_path=candidate_receipt_path,
            source_directory=SOURCE_DIRECTORY,
            repository_root=RELEASE_PACKAGE_ROOT,
            output=output,
        )

    assert not output.exists()


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
    assert frozen_receipt.document["schemaVersion"] == (
        "ofarm.native-verifier-evidence-receipt.v2"
    )
    assert frozen_receipt.document["candidateReceiptDigest"] == _digest(
        candidate_receipt_path.read_bytes()
    )
    assert frozen_receipt.document["verificationAuthorityInput"] == (
        evidence_authority_input_manifest(RELEASE_PACKAGE_ROOT)
    )
    assert frozen_receipt.document["evidenceAuthorityInput"] == (
        frozen_receipt.document["verificationAuthorityInput"]
    )
    assert frozen_receipt.document["preservation"]["status"] == "verified"
    provider = frozen_receipt.document["preservation"]["providerVerification"]
    assert provider["schemaVersion"] == (
        "ofarm.github-release-provider-verification.v2"
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

    mutated = frozen_receipt.manifest()
    mutated["candidateReceiptDigest"] = "sha256:" + "0" * 64
    mutated_path = tmp_path / "mutated-candidate-link.json"
    mutated_path.write_bytes(release_canonical_json_bytes(mutated))
    with pytest.raises(
        NativeReleaseIdentityError,
        match="does not bind its candidate",
    ):
        load_native_evidence_receipt(
            mutated_path,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=RELEASE_PACKAGE_ROOT,
        )

    mutated_candidate_content = frozen_receipt.manifest()
    mutated_candidate_content["evidenceAuthorityInput"] = (
        _different_authority_snapshot(
            mutated_candidate_content["evidenceAuthorityInput"]
        )
    )
    mutated_candidate_path = tmp_path / "mutated-candidate-content.json"
    mutated_candidate_path.write_bytes(
        release_canonical_json_bytes(mutated_candidate_content)
    )
    with pytest.raises(
        NativeReleaseIdentityError,
        match="does not bind its candidate",
    ):
        load_native_evidence_receipt(
            mutated_candidate_path,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=RELEASE_PACKAGE_ROOT,
        )

    downgraded = frozen_receipt.manifest()
    downgraded.pop("candidateReceiptDigest")
    downgraded.pop("verificationAuthorityInput")
    downgraded["schemaVersion"] = "ofarm.native-verifier-evidence-receipt.v1"
    downgraded_path = tmp_path / "downgraded-frozen.json"
    downgraded_path.write_bytes(release_canonical_json_bytes(downgraded))
    with pytest.raises(NativeReleaseIdentityError, match="fields are not exact"):
        load_native_evidence_receipt(
            downgraded_path,
            release_identity=identity,
        )

    candidate_v1 = frozen_receipt.manifest()
    candidate_v1.pop("candidateReceiptDigest")
    candidate_v1.pop("verificationAuthorityInput")
    candidate_v1["schemaVersion"] = (
        native_release_identity.EVIDENCE_RECEIPT_SCHEMA_V1
    )
    candidate_v1["status"] = "candidate"
    candidate_v1["preservation"]["status"] = "pending"
    candidate_v1["preservation"]["providerVerification"] = None
    candidate_v1_path = tmp_path / "valid-candidate-v1.json"
    candidate_v1_path.write_bytes(release_canonical_json_bytes(candidate_v1))
    with pytest.raises(
        NativeReleaseIdentityError,
        match="candidate evidence receipt cannot be checked as frozen authority",
    ):
        load_native_evidence_receipt(
            candidate_v1_path,
            release_identity=identity,
        )
    explicit_candidate = load_native_evidence_receipt(
        candidate_v1_path,
        release_identity=identity,
        allow_candidate=True,
    )
    assert explicit_candidate.status == "candidate"

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


def test_frozen_receipt_refuses_nonhistorical_authority_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity, receipt, _ = _prepare_frozen_receipt(tmp_path, monkeypatch)
    mutated = receipt.manifest()
    mutated["evidenceAuthorityInput"] = _different_authority_snapshot(
        mutated["evidenceAuthorityInput"]
    )
    mutated["candidateReceiptDigest"] = _candidate_digest_from_frozen(mutated)
    mutated_path = tmp_path / "nonhistorical-authority-mismatch.json"
    mutated_path.write_bytes(release_canonical_json_bytes(mutated))

    with pytest.raises(
        NativeReleaseIdentityError,
        match="build and verification authority snapshots differ",
    ):
        load_native_evidence_receipt(
            mutated_path,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=RELEASE_PACKAGE_ROOT,
        )


@pytest.mark.parametrize(
    ("identity_marker", "source_marker", "run_marker"),
    [
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, False),
        (True, False, True),
        (False, True, True),
    ],
)
def test_frozen_receipt_refuses_every_partial_historical_marker_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity_marker: bool,
    source_marker: bool,
    run_marker: bool,
) -> None:
    identity, receipt, frozen_path = _prepare_frozen_receipt(tmp_path, monkeypatch)
    monkeypatch.setattr(
        native_release_identity,
        "HISTORICAL_V1_RELEASE_IDENTITY_DIGEST",
        identity.digest if identity_marker else "sha256:" + "f" * 64,
    )
    monkeypatch.setattr(
        native_release_identity,
        "HISTORICAL_V1_SOURCE_COMMIT",
        SOURCE_COMMIT if source_marker else "2" * 40,
    )
    monkeypatch.setattr(
        native_release_identity,
        "HISTORICAL_V1_RUN_ID",
        1 if run_marker else 2,
    )
    monkeypatch.setattr(
        native_release_identity,
        "HISTORICAL_V1_CANDIDATE_RECEIPT_DIGEST",
        receipt.document["candidateReceiptDigest"],
    )
    monkeypatch.setattr(
        native_release_identity,
        "HISTORICAL_V1_RUN_ATTEMPT",
        1,
    )

    with pytest.raises(
        NativeReleaseIdentityError,
        match="historical candidate authority is not the exact v1 migration",
    ):
        load_native_evidence_receipt(
            frozen_path,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=RELEASE_PACKAGE_ROOT,
        )


@pytest.mark.parametrize("fault", ["candidate-digest", "run-attempt"])
def test_frozen_receipt_refuses_inexact_complete_historical_tuple(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    identity, receipt, frozen_path = _prepare_frozen_receipt(tmp_path, monkeypatch)
    monkeypatch.setattr(
        native_release_identity,
        "HISTORICAL_V1_RELEASE_IDENTITY_DIGEST",
        identity.digest,
    )
    monkeypatch.setattr(
        native_release_identity,
        "HISTORICAL_V1_SOURCE_COMMIT",
        SOURCE_COMMIT,
    )
    monkeypatch.setattr(native_release_identity, "HISTORICAL_V1_RUN_ID", 1)
    monkeypatch.setattr(
        native_release_identity,
        "HISTORICAL_V1_CANDIDATE_RECEIPT_DIGEST",
        (
            "sha256:" + "f" * 64
            if fault == "candidate-digest"
            else receipt.document["candidateReceiptDigest"]
        ),
    )
    monkeypatch.setattr(
        native_release_identity,
        "HISTORICAL_V1_RUN_ATTEMPT",
        2 if fault == "run-attempt" else 1,
    )

    with pytest.raises(
        NativeReleaseIdentityError,
        match="historical candidate authority is not the exact v1 migration",
    ):
        load_native_evidence_receipt(
            frozen_path,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=RELEASE_PACKAGE_ROOT,
        )


def test_historical_receipt_refuses_snapshot_swap_even_with_recomputed_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity, receipt, _ = _prepare_frozen_receipt(tmp_path, monkeypatch)
    historical = receipt.manifest()
    historical["evidenceAuthorityInput"] = _different_authority_snapshot(
        historical["evidenceAuthorityInput"]
    )
    historical["candidateReceiptDigest"] = _candidate_digest_from_frozen(historical)
    historical_path = tmp_path / "approved-historical-receipt.json"
    historical_path.write_bytes(release_canonical_json_bytes(historical))

    monkeypatch.setattr(
        native_release_identity,
        "HISTORICAL_V1_RELEASE_IDENTITY_DIGEST",
        identity.digest,
    )
    monkeypatch.setattr(
        native_release_identity,
        "HISTORICAL_V1_SOURCE_COMMIT",
        SOURCE_COMMIT,
    )
    monkeypatch.setattr(native_release_identity, "HISTORICAL_V1_RUN_ID", 1)
    monkeypatch.setattr(native_release_identity, "HISTORICAL_V1_RUN_ATTEMPT", 1)
    monkeypatch.setattr(
        native_release_identity,
        "HISTORICAL_V1_CANDIDATE_RECEIPT_DIGEST",
        historical["candidateReceiptDigest"],
    )

    accepted = load_native_evidence_receipt(
        historical_path,
        release_identity=identity,
        verify_current_authority=True,
        repository_root=RELEASE_PACKAGE_ROOT,
    )
    assert accepted.document["evidenceAuthorityInput"] != (
        accepted.document["verificationAuthorityInput"]
    )

    swapped = accepted.manifest()
    swapped["evidenceAuthorityInput"] = swapped["verificationAuthorityInput"]
    swapped["candidateReceiptDigest"] = _candidate_digest_from_frozen(swapped)
    swapped_path = tmp_path / "swapped-historical-receipt.json"
    swapped_path.write_bytes(release_canonical_json_bytes(swapped))
    with pytest.raises(
        NativeReleaseIdentityError,
        match="historical candidate authority is not the exact v1 migration",
    ):
        load_native_evidence_receipt(
            swapped_path,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=RELEASE_PACKAGE_ROOT,
        )


def test_frozen_receipt_refuses_v2_candidate_downgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity, receipt, _ = _prepare_frozen_receipt(tmp_path, monkeypatch)
    downgraded = receipt.manifest()
    downgraded["status"] = "candidate"
    downgraded_path = tmp_path / "v2-candidate.json"
    downgraded_path.write_bytes(release_canonical_json_bytes(downgraded))

    with pytest.raises(NativeReleaseIdentityError, match="fields are not exact"):
        load_native_evidence_receipt(
            downgraded_path,
            release_identity=identity,
            allow_candidate=True,
        )


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
            lambda provider: _rewrite_provider_verified_statements(
                provider, _replace_release_predicate_version
            ),
            "statement type is not exact",
        ),
        (
            lambda provider: _rewrite_provider_verified_statements(
                provider, _replace_release_database_id
            ),
            "repository/tag predicate is inconsistent",
        ),
        (
            lambda provider: _rewrite_provider_verified_statements(
                provider, _replace_release_package_id
            ),
            "repository/tag predicate is inconsistent",
        ),
        (
            lambda provider: _rewrite_provider_verified_statements(
                provider, _replace_release_owner_id
            ),
            "owner identity is not exact",
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
            "pinned-CLI transport metadata is not exact",
        ),
        (
            lambda provider: _rewrite_provider_documents(
                provider, _replace_initiator
            ),
            "pinned-CLI transport metadata is not exact",
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


def test_frozen_receipt_refuses_recomputed_fake_dsse_signatures(
    tmp_path: Path,
) -> None:
    document = json.loads(EVIDENCE_RECEIPT_PATH.read_bytes())
    provider = document["preservation"]["providerVerification"]
    metadata = provider["metadata"]
    commands = [metadata["releaseAttestation"]]
    commands.extend(
        entry["verification"] for entry in metadata["assetAttestations"]
    )
    fake_signature = base64.b64encode(b"fake").decode("ascii")
    for command in commands:
        command["document"]["attestation"]["bundle"]["dsseEnvelope"][
            "signatures"
        ][0]["sig"] = fake_signature
        canonical = release_canonical_json_bytes(command["document"])
        command["canonicalDigest"] = _digest(canonical)
        command["size"] = len(canonical)
    provider["canonicalDigest"] = _digest(
        release_canonical_json_bytes(metadata)
    )
    hostile_receipt = tmp_path / "hostile-receipt.json"
    hostile_receipt.write_bytes(release_canonical_json_bytes(document))
    identity = load_native_release_identity(
        verify_current_sources=True,
        source_directory=SOURCE_DIRECTORY,
    )

    with pytest.raises(
        NativeReleaseIdentityError,
        match="retained provider-verification digest differs",
    ):
        load_native_evidence_receipt(
            hostile_receipt,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=RELEASE_PACKAGE_ROOT,
        )


def test_frozen_receipt_is_reverified_by_the_maintained_provider_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = json.loads(EVIDENCE_RECEIPT_PATH.read_bytes())
    retained = document["preservation"]["providerVerification"]
    observed: dict[str, object] = {}

    def authenticate(**values):
        observed.update(values)
        return retained

    monkeypatch.setattr(native_evidence, "_authenticate_github_release", authenticate)

    result = verify_frozen_evidence_receipt(
        release_identity_path=native_release_identity.IDENTITY_PATH,
        evidence_receipt_path=EVIDENCE_RECEIPT_PATH,
        source_directory=SOURCE_DIRECTORY,
        repository_root=RELEASE_PACKAGE_ROOT,
    )

    assert result["status"] == "cryptographically-verified"
    assert result["providerVerificationDigest"] == retained["canonicalDigest"]
    assert observed["candidate"].status == "frozen"
    assert observed["retained_immutable_releases"] == retained["metadata"][
        "immutableReleases"
    ]


def test_conformance_environment_carries_release_status_and_exact_archive(
    tmp_path: Path,
) -> None:
    identity_path, receipt_path = _write_provisional_checked_authority(tmp_path)
    identity = load_native_release_identity(
        identity_path,
        verify_current_sources=True,
        source_directory=SOURCE_DIRECTORY,
    )
    archive, child, config = _direct_oci_fixture(
        tmp_path,
        docker_image_name="ofarm-postgresql-conformance:local",
    )

    environment = conformance_environment(
        checked_identity_path=identity_path,
        checked_receipt_path=receipt_path,
        archive_path=archive,
        source_directory=SOURCE_DIRECTORY,
        repository_root=RELEASE_PACKAGE_ROOT,
        image_name="ofarm-postgresql-conformance:local",
        archive_reference=str(archive),
    )

    assert f"ISSUE174_DERIVED_POSTGRES_ARCHIVE={archive}\n" in environment
    assert f"ISSUE174_DERIVED_POSTGRES_CHILD_DIGEST={child}\n" in environment
    assert f"ISSUE174_DERIVED_POSTGRES_CONFIG_DIGEST={config}\n" in environment
    assert (
        f"ISSUE174_DERIVED_POSTGRES_IDENTITY_STATUS={identity.status}\n"
        in environment
    )
    receipt = load_native_evidence_receipt(
        receipt_path,
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
    with pytest.raises(NativeEvidenceError, match="archive reference is invalid"):
        conformance_environment(
            checked_identity_path=identity_path,
            checked_receipt_path=receipt_path,
            archive_path=archive,
            source_directory=SOURCE_DIRECTORY,
            repository_root=RELEASE_PACKAGE_ROOT,
            image_name="ofarm-postgresql-conformance:local",
            archive_reference=str(tmp_path / "different.oci.tar"),
        )


def test_frozen_conformance_environment_refuses_a_different_valid_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_identity, candidate_receipt, _, _, _ = _prepare_candidate(
        tmp_path,
        runtime_octet="stable",
    )
    _install_github_release_fixture(monkeypatch, candidate_receipt)
    frozen_receipt = tmp_path / "frozen-conformance-receipt.json"
    finalize_evidence_receipt(
        release_identity_path=candidate_identity,
        candidate_receipt_path=candidate_receipt,
        source_directory=SOURCE_DIRECTORY,
        repository_root=RELEASE_PACKAGE_ROOT,
        output=frozen_receipt,
    )
    identity = load_native_release_identity(
        candidate_identity,
        verify_current_sources=True,
        source_directory=SOURCE_DIRECTORY,
    )
    expected = identity.document["platforms"][0]
    matching_archive, child_digest, config_digest = _direct_oci_fixture(
        tmp_path,
        name="matching-frozen",
        runtime_octet="stable",
        docker_image_name="ofarm-postgresql-conformance:local",
    )
    assert (child_digest, config_digest) == (
        expected["runtimeChildDigest"],
        expected["runtimeConfigDigest"],
    )

    environment = conformance_environment(
        checked_identity_path=candidate_identity,
        checked_receipt_path=frozen_receipt,
        archive_path=matching_archive,
        source_directory=SOURCE_DIRECTORY,
        repository_root=RELEASE_PACKAGE_ROOT,
        image_name="ofarm-postgresql-conformance:local",
        archive_reference=str(matching_archive),
    )
    assert "ISSUE174_DERIVED_POSTGRES_IDENTITY_STATUS=frozen\n" in environment
    assert (
        "ISSUE174_DERIVED_POSTGRES_EVIDENCE_RECEIPT_STATUS=frozen\n"
        in environment
    )

    different_archive, _, _ = _direct_oci_fixture(
        tmp_path,
        name="different-frozen",
        runtime_octet="different",
        docker_image_name="ofarm-postgresql-conformance:local",
    )
    with pytest.raises(
        NativeEvidenceError,
        match="derived PostgreSQL build differs from frozen amd64 identity",
    ):
        conformance_environment(
            checked_identity_path=candidate_identity,
            checked_receipt_path=frozen_receipt,
            archive_path=different_archive,
            source_directory=SOURCE_DIRECTORY,
            repository_root=RELEASE_PACKAGE_ROOT,
            image_name="ofarm-postgresql-conformance:local",
            archive_reference=str(different_archive),
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
    assert observed_action_pins == CURRENT_NATIVE_REPRODUCER_ACTION_PINS
    assert CURRENT_NATIVE_BUILD_PINS["buildxClient"] == {
        "version": "v0.34.1",
        "sourceCommit": "e0b0e77d18d3379bc1e0d55f3b37de288d36fe47",
    }
    assert "services:" not in workflow
    assert "ubuntu-24.04-arm" in workflow
    assert "ubuntu-24.04" in workflow
    assert "setup-qemu" not in workflow
    assert "docker/setup-buildx-action" not in workflow
    assert "docker buildx" not in workflow
    assert "version: v0.34.1" not in workflow
    authenticated_install_steps = workflow.split(
        "- name: Authenticate and install the exact Buildx client"
    )
    assert len(authenticated_install_steps) == 3
    for install_step in authenticated_install_steps[1:]:
        install_step = install_step.split(
            "- name: Create pinned native image builder", 1
        )[0]
        assert "curl --fail --location" in install_step
        assert "sha256sum --check --strict" in install_step
        assert install_step.index("sha256sum --check --strict") < (
            install_step.index("install -m 0755")
        )
        assert install_step.index("install -m 0755") < install_step.index(
            'test "$("${buildx_binary}" version)" ='
        )
        assert install_step.index(
            'test "$("${buildx_binary}" version)" ='
        ) < install_step.index("ISSUE174_BUILDX=%s")
        assert ".docker/cli-plugins" not in install_step
    assert workflow.count(
        "f1332ddb9010bd0b72628266c3a906d9a6979848033df4c8d9bd2cd113bae12b"
    ) == 2
    assert workflow.count(
        "c34e32dd6ea2653d960d6c099c9f09b9077e4a37504d2d31e5066eccc3904231"
    ) == 1
    assert workflow.count(
        "e0b0e77d18d3379bc1e0d55f3b37de288d36fe47"
    ) == 3
    assert workflow.count('"${ISSUE174_BUILDX}" create') == 2
    assert workflow.count('"${ISSUE174_BUILDX}" inspect') == 2
    assert workflow.count('"${ISSUE174_BUILDX}" build') == 7
    assert workflow.count('"${ISSUE174_BUILDX}" rm') == 2
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
    assert clean_build_step.count(
        '"type=docker,dest=.artifacts/native/${{ matrix.architecture }}/'
        '${build}-image.docker.tar,oci-mediatypes=true"'
    ) == 1
    assert "--load" not in clean_build_step
    assert "--metadata-file" not in clean_build_step
    assert '--tag "ofarm-ed25519-${{ matrix.architecture }}:${build}"' in (
        clean_build_step
    )
    assert '--platform "linux/${{ matrix.architecture }}"' in clean_build_step
    compare_step = workflow.split(
        "- name: Prove child and installed-artifact reproducibility", 1
    )[1].split("- name: Load and verify the authenticated clean native child", 1)[0]
    assert "--first-archive" in compare_step
    assert "first-image.docker.tar" in compare_step
    assert "--second-archive" in compare_step
    assert "second-image.docker.tar" in compare_step
    assert "metadata" not in compare_step
    native_load_step = workflow.split(
        "- name: Load and verify the authenticated clean native child", 1
    )[1].split("- name: Run the exact live PostgreSQL verifier smoke", 1)[0]
    assert "docker image inspect" in native_load_step
    assert native_load_step.count("docker load --input") == 1
    assert "second-image.docker.tar" in native_load_step
    assert "docker tag" not in native_load_step
    assert "child_digest" in native_load_step
    assert "config_digest" in native_load_step
    assert "{{.Os}}/{{.Architecture}}" in native_load_step
    assert native_load_step.count("rm --") == 1
    assert native_load_step.count("test ! -e") == 2
    first_archive_path = (
        '".artifacts/native/${{ matrix.architecture }}/first-image.docker.tar"'
    )
    second_archive_path = (
        '".artifacts/native/${{ matrix.architecture }}/second-image.docker.tar"'
    )
    assert native_load_step.count(first_archive_path) == 2
    assert native_load_step.count(second_archive_path) == 3
    native_load_markers = (
        'if docker image inspect "$image"',
        "docker load --input",
        'observed_id="$(docker image inspect',
        "{{.Os}}/{{.Architecture}}",
        "rm --",
        "test ! -e",
    )
    assert [native_load_step.index(marker) for marker in native_load_markers] == sorted(
        native_load_step.index(marker) for marker in native_load_markers
    )
    native_step_names = (
        "- name: Prove child and installed-artifact reproducibility",
        "- name: Load and verify the authenticated clean native child",
        "- name: Run the exact live PostgreSQL verifier smoke",
        "- name: Produce bounded OCI, SBOM, and max-provenance evidence",
    )
    assert [workflow.index(name) for name in native_step_names] == sorted(
        workflow.index(name) for name in native_step_names
    )
    derived_build_step = workflow.split(
        "- name: Build the derived PostgreSQL image", 1
    )[1].split("- name: Authenticate the derived PostgreSQL release identity", 1)[0]
    assert (
        "type=docker,dest=.artifacts/derived-postgresql/"
        "ofarm-postgresql-conformance.docker.tar,oci-mediatypes=true"
    ) in derived_build_step
    assert "--metadata-file" not in derived_build_step
    assert "--load" not in derived_build_step
    derived_auth_step = workflow.split(
        "- name: Authenticate the derived PostgreSQL release identity", 1
    )[1].split("- name: Load the exact authenticated derived PostgreSQL image", 1)[0]
    assert "--archive" in derived_auth_step
    assert "--archive-reference" in derived_auth_step
    assert "ofarm-postgresql-conformance.docker.tar" in derived_auth_step
    assert "metadata" not in derived_auth_step
    derived_load_step = workflow.split(
        "- name: Load the exact authenticated derived PostgreSQL image", 1
    )[1].split("- name: Start three independent derived PostgreSQL clusters", 1)[0]
    assert "docker image inspect" in derived_load_step
    assert derived_load_step.count("docker load --input") == 1
    assert "ISSUE174_DERIVED_POSTGRES_CHILD_DIGEST" in derived_load_step
    assert "ISSUE174_DERIVED_POSTGRES_CONFIG_DIGEST" in derived_load_step
    assert "{{.Os}}/{{.Architecture}}" in derived_load_step
    assert "docker tag" not in derived_load_step
    derived_load_markers = (
        "if docker image inspect ofarm-postgresql-conformance:local",
        "docker load --input",
        'observed_id="$(docker image inspect',
        "{{.Os}}/{{.Architecture}}",
    )
    assert [
        derived_load_step.index(marker) for marker in derived_load_markers
    ] == sorted(derived_load_step.index(marker) for marker in derived_load_markers)
    derived_archive_path = (
        ".artifacts/derived-postgresql/"
        "ofarm-postgresql-conformance.docker.tar"
    )
    assert workflow.count(derived_archive_path) == 4
    assert derived_auth_step.count(derived_archive_path) == 2
    assert derived_load_step.count(derived_archive_path) == 1
    derived_step_names = (
        "- name: Build the derived PostgreSQL image",
        "- name: Authenticate the derived PostgreSQL release identity",
        "- name: Load the exact authenticated derived PostgreSQL image",
        "- name: Start three independent derived PostgreSQL clusters",
    )
    assert [workflow.index(name) for name in derived_step_names] == sorted(
        workflow.index(name) for name in derived_step_names
    )
    attested_step = workflow.split(
        "- name: Produce bounded OCI, SBOM, and max-provenance evidence", 1
    )[1].split("- name: Upload bounded native verifier evidence", 1)[0]
    assert (
        '"type=oci,dest=.artifacts/native/${{ matrix.architecture }}/'
        'ofarm-ed25519.oci.tar,oci-mediatypes=true"'
    ) in attested_step
    assert "type=docker" not in attested_step
    assert "first-image.docker.tar" not in attested_step
    assert "second-image.docker.tar" not in attested_step
    assert attested_step.count("ofarm-ed25519.oci.tar") == 2
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


def test_native_workflow_has_no_buildx_discovery_or_download_fallback():
    workflow = PACKAGE_ROOT.joinpath(".github/workflows/conformance.yml").read_text()

    assert "docker/setup-buildx-action" not in workflow
    assert "docker buildx" not in workflow
    assert ".docker/cli-plugins" not in workflow
    assert workflow.count("buildx/releases/download/v0.34.1/") == 2

    install_sections = workflow.split(
        "- name: Authenticate and install the exact Buildx client"
    )[1:]
    assert len(install_sections) == 2
    for section in install_sections:
        install_step, remainder = section.split(
            "- name: Create pinned native image builder", 1
        )
        builder_step = remainder.split("      - name:", 1)[0]
        assert "buildx/releases/download/v0.34.1/" in install_step
        assert install_step.index("sha256sum --check --strict") < (
            install_step.index("install -m 0755")
        )
        assert install_step.index("install -m 0755") < install_step.index(
            'test "$("${buildx_binary}" version)" ='
        )
        assert install_step.index(
            'test "$("${buildx_binary}" version)" ='
        ) < install_step.index("ISSUE174_BUILDX=%s")

        assert builder_step.index('test -x "${ISSUE174_BUILDX}"') < (
            builder_step.index('"${ISSUE174_BUILDX}" create')
        )
        assert '"${ISSUE174_BUILDX}" inspect' in builder_step
        assert "curl" not in builder_step
        assert "download" not in builder_step.lower()
        assert "install" not in builder_step.lower()


def test_conformance_workflow_authenticates_and_selects_exact_github_cli():
    workflow = PACKAGE_ROOT.joinpath(".github/workflows/conformance.yml").read_text()
    conformance_job = workflow.split("  conformance:\n", 1)[1].split(
        "\n  native-verifier:", 1
    )[0]
    checkout_step = conformance_job.split(
        "actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5",
        1,
    )[1].split("      - name:", 1)[0]
    assert "fetch-depth: 0" in checkout_step
    assert "persist-credentials: false" in checkout_step

    install_step = conformance_job.split(
        "- name: Authenticate and install the exact GitHub CLI", 1
    )[1].split(
        "- name: Cryptographically reverify retained native release evidence", 1
    )[0]
    assert "shell: bash" in install_step
    assert "GH_TOKEN:" not in install_step
    assert "GITHUB_TOKEN:" not in install_step
    assert 'test "${GH_TOKEN+x}" = x' in install_step
    assert 'test "${GITHUB_TOKEN+x}" = x' in install_step
    assert "git config --local --name-only --get-regexp" in install_step
    assert "'^http\\..*\\.extraheader$' >/dev/null" in install_step
    assert 'test "${credential_status}" -eq 1' in install_step
    assert "mktemp --directory" in install_step
    assert "${RUNNER_TEMP}/ofarm-gh-v2.96.0.XXXXXX" in install_step
    assert (
        "https://github.com/cli/cli/releases/download/v2.96.0/"
        "gh_2.96.0_linux_amd64.tar.gz"
    ) in install_step
    assert (
        "83d5c2ccad5498f58bf6368acb1ab325"
        "88cf43ab3a4b1c301bf36328b1c8bd60"
    ) in install_step
    assert "sha256sum --check --strict" in install_step
    assert "tar --extract --gzip" in install_step
    assert "--strip-components=2" in install_step
    assert "gh_2.96.0_linux_amd64/bin/gh" in install_step
    assert "resolve(strict=True)" in install_step
    assert "stat.S_ISREG" in install_step
    assert "os.access(candidate, os.X_OK)" in install_step
    assert '"${gh_binary}" version >"${gh_stdout}" 2>"${gh_stderr}"' in (
        install_step
    )
    assert 'test "${gh_status}" -eq 0' in install_step
    assert 'test ! -s "${gh_stderr}"' in install_step
    assert "NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT" in install_step
    assert "read_bytes()" in install_step
    assert "OFARM_NATIVE_EVIDENCE_GITHUB_CLI=%s" in install_step
    assert '"${gh_binary}" >> "${GITHUB_ENV}"' in install_step
    assert '"${gh_binary%/*}" >> "${GITHUB_PATH}"' in install_step
    install_markers = (
        "git config --local --name-only --get-regexp",
        "curl --fail --location",
        "sha256sum --check --strict",
        "tar --extract --gzip",
        "resolve(strict=True)",
        '"${gh_binary}" version',
        "NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT",
        "OFARM_NATIVE_EVIDENCE_GITHUB_CLI=%s",
        '"${gh_binary%/*}" >> "${GITHUB_PATH}"',
    )
    assert [install_step.index(marker) for marker in install_markers] == sorted(
        install_step.index(marker) for marker in install_markers
    )
    forbidden_install_fragments = (
        "gh auth",
        "apt-get",
        "brew ",
        "setup-gh",
        "which gh",
        "command -v gh",
    )
    for fragment in forbidden_install_fragments:
        assert fragment not in install_step

    verification_step = conformance_job.split(
        "- name: Cryptographically reverify retained native release evidence", 1
    )[1].split("- name: Reject whitespace errors", 1)[0]
    assert verification_step.count("GH_TOKEN: ${{ github.token }}") == 1
    assert "GITHUB_TOKEN:" not in verification_step
    verification_markers = (
        'os.environ.get("OFARM_NATIVE_EVIDENCE_GITHUB_CLI")',
        'shutil.which("gh")',
        "resolve(strict=True)",
        "selected != recorded",
        "stat.S_ISREG",
        "os.access(selected, os.X_OK)",
        "deployment/postgresql/native_evidence.py",
        "verify-frozen-evidence-receipt",
    )
    assert [
        verification_step.index(marker) for marker in verification_markers
    ] == sorted(verification_step.index(marker) for marker in verification_markers)
    assert conformance_job.count("GH_TOKEN: ${{ github.token }}") == 1
    assert "GITHUB_TOKEN:" not in conformance_job


def test_native_build_sources_match_evidence_material_authority():
    containerfile = PACKAGE_ROOT.joinpath(
        "deployment/postgresql/ofarm_ed25519/Containerfile"
    ).read_text()

    assert LIBSODIUM_SOURCE_URL in containerfile
    assert LIBSODIUM_SOURCE_SHA256 in containerfile
    for source_url, digest in SERVER_DEV_SOURCES.values():
        assert source_url in containerfile
        assert digest in containerfile
