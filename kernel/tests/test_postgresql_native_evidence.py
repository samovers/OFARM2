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

from deployment.postgresql.native_evidence import (
    CURRENT_NATIVE_ACTION_PINS,
    LIBSODIUM_SOURCE_SHA256,
    LIBSODIUM_SOURCE_URL,
    NativeEvidenceError,
    SERVER_DEV_SOURCES,
    collect_oci_evidence,
    compare_builds,
    conformance_environment,
    compose_multi_platform_index,
    prepare_release_identity,
)
from deployment.postgresql.native_release_identity import (
    IDENTITY_PATH,
    NATIVE_SOURCE_PATHS,
    SOURCE_DIRECTORY,
    NativeReleaseIdentityError,
    canonical_json_bytes as release_canonical_json_bytes,
    load_native_release_identity,
    provisional_identity_document,
)


SOURCE_COMMIT = "1" * 40
PLATFORM = "linux/amd64"
BUILDER_ID = "https://github.com/samovers/OFARM2/actions/runs/1/attempts/1"
CONTAINERFILE_BYTES = b"FROM postgres@sha256:fixture\n"
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
    tmp_path: Path, child_digest: str, config_digest: str
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
        platform=PLATFORM,
        source_commit=SOURCE_COMMIT,
        output=output,
    )
    return output


def _native_oci_report(platform: str, digest_octet: str) -> dict[str, object]:
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
        "image_index_digest": "sha256:" + "c" * 64,
        "attestation_manifest_digest": "sha256:" + "d" * 64,
        "oci_archive": {"sha256": "sha256:" + "e" * 64, "size": 12345},
        "sbom": {
            "predicate_type": "https://spdx.dev/Document",
            "sha256": "sha256:" + "a" * 64,
            "size": 321,
        },
        "provenance": {
            "predicate_type": "https://slsa.dev/provenance/v0.2",
            "sha256": "sha256:" + "b" * 64,
            "size": 654,
        },
    }


def _oci_fixture(
    tmp_path: Path,
    *,
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

    runtime_config = remember(b"{}")
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
                    "pkg:docker/ofarm-ed25519-evidence@amd64?"
                    "platform=linux%2Famd64"
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
                    "documentNamespace": "https://example.test/spdx/ofarm-ed25519",
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
                            "https://apt.postgresql.org/pub/repos/apt/pool/main/p/"
                            "postgresql-17/postgresql-server-dev-17_17.10-1.pgdg13+1_"
                            "amd64.deb"
                        ),
                        "digest": {
                            "sha256": (
                                "adc91a999ec840f8db8c8df5ac2473fe1deeaed0e76bd5a6391afa7"
                                "c74bceac3"
                            )
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
                    "environment": {"platform": PLATFORM},
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
        platform={"os": "linux", "architecture": "amd64"},
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
    provisional_path = tmp_path / "provisional.json"
    provisional_path.write_bytes(
        release_canonical_json_bytes(provisional_identity_document(SOURCE_DIRECTORY))
    )
    candidate_path = tmp_path / "candidate.json"

    result = prepare_release_identity(
        checked_identity_path=provisional_path,
        index_evidence_path=evidence_path,
        index_path=index_path,
        source_directory=SOURCE_DIRECTORY,
        candidate_output=candidate_path,
    )
    candidate = load_native_release_identity(
        candidate_path,
        verify_current_sources=True,
        source_directory=SOURCE_DIRECTORY,
    )

    assert result == {
        "checked_status": "provisional",
        "candidate_digest": candidate.digest,
        "candidate_index_digest": candidate.index_digest,
    }
    assert candidate.status == "frozen"
    assert candidate.document["index"]["canonicalBytesBase64"] == (
        base64.b64encode(index_path.read_bytes()).decode("ascii")
    )
    assert [item["platform"] for item in candidate.document["platforms"]] == [
        "linux/amd64",
        "linux/arm64",
    ]


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
        metadata_path=metadata,
        source_directory=SOURCE_DIRECTORY,
        image_name="ofarm-postgresql-conformance:local",
        metadata_reference=".artifacts/derived-postgresql/metadata.json",
    )

    assert f"ISSUE174_DERIVED_POSTGRES_CHILD_DIGEST={child}\n" in environment
    assert f"ISSUE174_DERIVED_POSTGRES_CONFIG_DIGEST={config}\n" in environment
    assert (
        f"ISSUE174_DERIVED_POSTGRES_IDENTITY_STATUS={identity.status}\n"
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
    assert "services:" not in workflow
    assert "ubuntu-24.04-arm" in workflow
    assert "ubuntu-24.04" in workflow
    assert "setup-qemu" not in workflow
    assert workflow.count("version: v0.34.1") == 2
    assert workflow.count(
        "test \"$(docker buildx version | awk '{print $2}')\" = v0.34.1"
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
