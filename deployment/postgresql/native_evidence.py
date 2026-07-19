"""Bounded CI evidence checks for the confined ``ofarm_ed25519`` image.

This module does not build or deploy an image.  It authenticates the narrow
reproducibility and OCI evidence emitted by the pinned GitHub Actions builder.
Every input is size-bounded before it is parsed or copied.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import stat
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from deployment.postgresql.native_release_identity import (
        CURRENT_NATIVE_ACTION_PINS,
        CURRENT_NATIVE_BUILD_PINS,
        NativeReleaseIdentityError,
        candidate_evidence_receipt_document,
        canonical_json_bytes as release_canonical_json_bytes,
        frozen_evidence_receipt_document,
        frozen_identity_document,
        load_native_evidence_receipt,
        load_native_release_identity,
        validate_native_release_identity,
    )
except ModuleNotFoundError:  # Direct execution from this source directory.
    from native_release_identity import (  # type: ignore[no-redef]
        CURRENT_NATIVE_ACTION_PINS,
        CURRENT_NATIVE_BUILD_PINS,
        NativeReleaseIdentityError,
        candidate_evidence_receipt_document,
        canonical_json_bytes as release_canonical_json_bytes,
        frozen_evidence_receipt_document,
        frozen_identity_document,
        load_native_evidence_receipt,
        load_native_release_identity,
        validate_native_release_identity,
    )


MAX_METADATA_BYTES = 64 * 1024
MAX_REPRODUCIBILITY_REPORT_BYTES = 64 * 1024
MAX_OCI_EVIDENCE_REPORT_BYTES = 64 * 1024
MAX_OCI_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_OCI_MEMBER_COUNT = 2_048
MAX_OCI_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_SBOM_BYTES = 8 * 1024 * 1024
MAX_PROVENANCE_BYTES = 2 * 1024 * 1024
MAX_CONTAINERFILE_BYTES = 128 * 1024

SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
PLATFORM_PATTERN = re.compile(r"linux/(amd64|arm64)\Z")
OCI_BLOB_PATTERN = re.compile(r"blobs/sha256/([0-9a-f]{64})\Z")

OCI_MANIFEST_MEDIA_TYPES = frozenset(
    {"application/vnd.oci.image.manifest.v1+json"}
)
OCI_INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
OCI_CONFIG_MEDIA_TYPE = "application/vnd.oci.image.config.v1+json"
OCI_LAYER_MEDIA_TYPE = "application/vnd.oci.image.layer.v1.tar+gzip"
ATTESTATION_REFERENCE_TYPE = "attestation-manifest"
ATTESTATION_REFERENCE_ANNOTATION = "vnd.docker.reference.digest"
ATTESTATION_TYPE_ANNOTATION = "vnd.docker.reference.type"
IN_TOTO_MEDIA_TYPE = "application/vnd.in-toto+json"
IN_TOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v0.1"
SBOM_PREDICATE_TYPE = "https://spdx.dev/Document"
PROVENANCE_PREDICATE_TYPE = "https://slsa.dev/provenance/v0.2"
BUILDKIT_BUILD_TYPE = "https://mobyproject.org/buildkit@v1"
BUILDKIT_METADATA_KEY = "https://mobyproject.org/buildkit@v1#metadata"
POSTGRESQL_PACKAGE_VERSION = "17.10-1.pgdg13+1"
LIBSODIUM_SOURCE_URL = (
    "https://download.libsodium.org/libsodium/releases/libsodium-1.0.22.tar.gz"
)
LIBSODIUM_SOURCE_SHA256 = (
    "adbdd8f16149e81ac6078a03aca6fc03b592b89ef7b5ed83841c086191be3349"
)
SERVER_DEV_SOURCES = {
    "linux/amd64": (
        "https://apt.postgresql.org/pub/repos/apt/pool/main/p/postgresql-17/"
        "postgresql-server-dev-17_17.10-1.pgdg13+1_amd64.deb",
        "adc91a999ec840f8db8c8df5ac2473fe1deeaed0e76bd5a6391afa7c74bceac3",
    ),
    "linux/arm64": (
        "https://apt.postgresql.org/pub/repos/apt/pool/main/p/postgresql-17/"
        "postgresql-server-dev-17_17.10-1.pgdg13+1_arm64.deb",
        "372c8eb77604bc9cba61689661701e65a336b14a43e8f9be850088bb8c4428b6",
    ),
}

ARTIFACT_CONTRACTS = {
    "libsodium.a": (8 * 1024 * 1024, "0644"),
    "ofarm_ed25519.so": (8 * 1024 * 1024, "0755"),
    "ofarm_ed25519.control": (16 * 1024, "0644"),
    "ofarm_ed25519--1.0.sql": (128 * 1024, "0644"),
}


class NativeEvidenceError(RuntimeError):
    """Raised when native CI evidence is absent, ambiguous, or malformed."""


def _read_bounded(path: Path, maximum: int, label: str) -> bytes:
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise NativeEvidenceError(f"{label} is unavailable") from exc
    if not stat.S_ISREG(file_stat.st_mode) or path.is_symlink():
        raise NativeEvidenceError(f"{label} must be one regular file")
    if file_stat.st_size > maximum:
        raise NativeEvidenceError(f"{label} exceeds its byte limit")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise NativeEvidenceError(f"{label} cannot be read") from exc


def _load_json_bytes(data: bytes, label: str) -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NativeEvidenceError(f"{label} is not UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_non_finite_json_number,
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise NativeEvidenceError(f"{label} is not valid JSON") from exc


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise NativeEvidenceError("JSON contains a duplicate object key")
        result[key] = value
    return result


def _reject_non_finite_json_number(value: str) -> None:
    raise NativeEvidenceError(f"JSON contains forbidden number {value}")


def _load_json_file(path: Path, maximum: int, label: str) -> Any:
    return _load_json_bytes(_read_bounded(path, maximum, label), label)


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise NativeEvidenceError(f"{label} must be a JSON object")
    return value


def _require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise NativeEvidenceError(f"{label} is not one canonical SHA-256 digest")
    return value


def _require_platform(value: str) -> str:
    if PLATFORM_PATTERN.fullmatch(value) is None:
        raise NativeEvidenceError("platform must be exactly linux/amd64 or linux/arm64")
    return value


def _require_source_commit(value: str) -> str:
    if COMMIT_PATTERN.fullmatch(value) is None:
        raise NativeEvidenceError("source commit must be one lowercase 40-hex commit")
    return value


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _write_regular(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise NativeEvidenceError("evidence output path is not a regular file")
    path.write_bytes(data)


def metadata_child_identity(path: Path, label: str) -> tuple[str, str]:
    """Read one direct runtime-child identity from bounded Buildx metadata."""

    metadata = _require_object(
        _load_json_file(path, MAX_METADATA_BYTES, label),
        label,
    )
    digest = _require_digest(metadata.get("containerimage.digest"), f"{label} digest")
    config_digest = _require_digest(
        metadata.get("containerimage.config.digest"), f"{label} config digest"
    )
    descriptor = _require_object(
        metadata.get("containerimage.descriptor"), f"{label} descriptor"
    )
    if descriptor.get("mediaType") not in OCI_MANIFEST_MEDIA_TYPES:
        raise NativeEvidenceError(
            f"{label} describes an index instead of one runtime child"
        )
    if _require_digest(descriptor.get("digest"), f"{label} descriptor digest") != digest:
        raise NativeEvidenceError(f"{label} descriptor digest is inconsistent")
    size = descriptor.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise NativeEvidenceError(f"{label} descriptor size is invalid")
    annotations = descriptor.get("annotations")
    if not isinstance(annotations, dict) or annotations.get("config.digest") != config_digest:
        raise NativeEvidenceError(f"{label} config annotation is inconsistent")
    return digest, config_digest


def _artifact_identity(
    directory: Path,
    name: str,
    maximum: int,
    expected_mode: str,
) -> dict[str, Any]:
    path = directory / name
    data = _read_bounded(path, maximum, f"native artifact {name}")
    file_stat = path.stat()
    observed_mode = format(stat.S_IMODE(file_stat.st_mode), "04o")
    if observed_mode != expected_mode:
        raise NativeEvidenceError(f"native artifact {name} mode is not {expected_mode}")
    return {
        "name": name,
        "mode": observed_mode,
        "sha256": _sha256(data),
        "size": len(data),
    }


def compare_builds(
    *,
    first_metadata: Path,
    second_metadata: Path,
    first_artifacts: Path,
    second_artifacts: Path,
    platform: str,
    source_commit: str,
    output: Path,
) -> dict[str, Any]:
    """Require two clean builds to have the same child and installed bytes."""

    platform = _require_platform(platform)
    source_commit = _require_source_commit(source_commit)
    first_digest, first_config_digest = metadata_child_identity(
        first_metadata, "first build metadata"
    )
    second_digest, second_config_digest = metadata_child_identity(
        second_metadata, "second build metadata"
    )
    if (first_digest, first_config_digest) != (
        second_digest,
        second_config_digest,
    ):
        raise NativeEvidenceError("clean builds produced different child digests")

    first_identities = [
        _artifact_identity(first_artifacts, name, maximum, expected_mode)
        for name, (maximum, expected_mode) in ARTIFACT_CONTRACTS.items()
    ]
    second_identities = [
        _artifact_identity(second_artifacts, name, maximum, expected_mode)
        for name, (maximum, expected_mode) in ARTIFACT_CONTRACTS.items()
    ]
    if first_identities != second_identities:
        raise NativeEvidenceError("clean builds produced different installed artifacts")

    report = {
        "schema": "ofarm.native-reproducibility-evidence.v1",
        "platform": platform,
        "source_commit": source_commit,
        "child_digest": first_digest,
        "config_digest": first_config_digest,
        "artifacts": first_identities,
    }
    _write_regular(output, _canonical_json_bytes(report))
    return report


class _OciArchive:
    def __init__(self, path: Path):
        archive_bytes = _read_bounded(path, MAX_OCI_ARCHIVE_BYTES, "OCI archive")
        self.path = path
        self.sha256 = _sha256(archive_bytes)
        self.size = len(archive_bytes)
        try:
            self._tar = tarfile.open(path, mode="r:*")
        except (OSError, tarfile.TarError) as exc:
            raise NativeEvidenceError("OCI archive is not a readable tar archive") from exc
        self._members: dict[str, tarfile.TarInfo] = {}
        self._referenced_blobs: set[str] = set()
        self._index_members()

    def close(self) -> None:
        self._tar.close()

    def _index_members(self) -> None:
        try:
            members = self._tar.getmembers()
        except (OSError, tarfile.TarError) as exc:
            raise NativeEvidenceError("OCI archive member table is unreadable") from exc
        if len(members) > MAX_OCI_MEMBER_COUNT:
            raise NativeEvidenceError("OCI archive contains too many members")
        expanded_size = 0
        for member in members:
            name = member.name.removeprefix("./")
            pure_name = PurePosixPath(name)
            if (
                not name
                or pure_name.is_absolute()
                or ".." in pure_name.parts
                or name in self._members
            ):
                raise NativeEvidenceError("OCI archive contains an unsafe member name")
            if member.isdir():
                if name not in {"blobs", "blobs/sha256"}:
                    raise NativeEvidenceError("OCI archive contains an unexpected directory")
                continue
            if not member.isreg():
                raise NativeEvidenceError("OCI archive contains a non-regular member")
            if name not in {"oci-layout", "index.json"} and OCI_BLOB_PATTERN.fullmatch(
                name
            ) is None:
                raise NativeEvidenceError("OCI archive contains an unexpected file")
            expanded_size += member.size
            if expanded_size > MAX_OCI_EXPANDED_BYTES:
                raise NativeEvidenceError("OCI archive expands beyond its byte limit")
            self._members[name] = member

    def read_member(self, name: str, maximum: int, label: str) -> bytes:
        member = self._members.get(name)
        if member is None:
            raise NativeEvidenceError(f"{label} is absent from the OCI archive")
        if member.size > maximum:
            raise NativeEvidenceError(f"{label} exceeds its byte limit")
        try:
            extracted = self._tar.extractfile(member)
            if extracted is None:
                raise NativeEvidenceError(f"{label} is unreadable")
            data = extracted.read(maximum + 1)
        except (OSError, tarfile.TarError) as exc:
            raise NativeEvidenceError(f"{label} is unreadable") from exc
        if len(data) != member.size or len(data) > maximum:
            raise NativeEvidenceError(f"{label} has an invalid size")
        return data

    def descriptor_bytes(
        self,
        descriptor: Any,
        maximum: int,
        label: str,
    ) -> bytes:
        descriptor_object = _require_object(descriptor, f"{label} descriptor")
        digest = _require_digest(descriptor_object.get("digest"), f"{label} digest")
        size = descriptor_object.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise NativeEvidenceError(f"{label} size is invalid")
        member_name = "blobs/sha256/" + digest.removeprefix("sha256:")
        data = self.read_member(
            member_name,
            maximum,
            label,
        )
        if len(data) != size or _sha256(data) != digest:
            raise NativeEvidenceError(f"{label} descriptor does not authenticate its blob")
        self._referenced_blobs.add(member_name)
        return data

    def require_no_unreferenced_blobs(self) -> None:
        all_blobs = {
            name for name in self._members if OCI_BLOB_PATTERN.fullmatch(name) is not None
        }
        if all_blobs != self._referenced_blobs:
            raise NativeEvidenceError("OCI archive contains an unreferenced blob")


def _manifest_descriptors(index: dict[str, Any]) -> list[dict[str, Any]]:
    if index.get("schemaVersion") != 2:
        raise NativeEvidenceError("OCI index schema version is not 2")
    if index.get("mediaType") != OCI_INDEX_MEDIA_TYPE:
        raise NativeEvidenceError("OCI index media type is not exact")
    manifests = index.get("manifests")
    if not isinstance(manifests, list) or not 1 <= len(manifests) <= 8:
        raise NativeEvidenceError("OCI index manifest set is absent or unbounded")
    return [_require_object(item, "OCI index descriptor") for item in manifests]


def _resolve_attested_image_index(
    archive: _OciArchive,
    layout_index: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    roots = _manifest_descriptors(layout_index)
    if len(roots) != 1:
        raise NativeEvidenceError("OCI layout must reference one image index")
    root = roots[0]
    if root.get("mediaType") != OCI_INDEX_MEDIA_TYPE or "platform" in root:
        raise NativeEvidenceError("OCI layout root is not one platform-neutral image index")
    root_digest = _require_digest(root.get("digest"), "image index digest")
    image_index = _require_object(
        _load_json_bytes(
            archive.descriptor_bytes(root, MAX_MANIFEST_BYTES, "image index"),
            "image index",
        ),
        "image index",
    )
    return _manifest_descriptors(image_index), root_digest


def _select_oci_descriptors(
    descriptors: list[dict[str, Any]], platform: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    os_name, architecture = platform.split("/", 1)
    runtime: list[dict[str, Any]] = []
    attestations: list[dict[str, Any]] = []
    for descriptor in descriptors:
        media_type = descriptor.get("mediaType")
        descriptor_platform = descriptor.get("platform")
        annotations = descriptor.get("annotations", {})
        if not isinstance(descriptor_platform, dict) or not isinstance(annotations, dict):
            raise NativeEvidenceError("OCI descriptor platform or annotations are malformed")
        if (
            descriptor_platform.get("os") == os_name
            and descriptor_platform.get("architecture") == architecture
            and media_type in OCI_MANIFEST_MEDIA_TYPES
            and ATTESTATION_TYPE_ANNOTATION not in annotations
        ):
            runtime.append(descriptor)
        elif annotations.get(ATTESTATION_TYPE_ANNOTATION) == ATTESTATION_REFERENCE_TYPE:
            attestations.append(descriptor)
        else:
            raise NativeEvidenceError("OCI index contains an unexpected descriptor")
    if len(runtime) != 1 or len(attestations) != 1:
        raise NativeEvidenceError("OCI index must contain one runtime and one attestation")
    runtime_digest = _require_digest(runtime[0].get("digest"), "runtime child digest")
    if attestations[0]["annotations"].get(ATTESTATION_REFERENCE_ANNOTATION) != runtime_digest:
        raise NativeEvidenceError("attestation does not reference the runtime child")
    return runtime[0], attestations[0]


def _load_manifest(
    archive: _OciArchive,
    descriptor: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    if descriptor.get("mediaType") not in OCI_MANIFEST_MEDIA_TYPES:
        raise NativeEvidenceError(f"{label} media type is not an OCI image manifest")
    data = archive.descriptor_bytes(descriptor, MAX_MANIFEST_BYTES, label)
    manifest = _require_object(_load_json_bytes(data, label), label)
    if manifest.get("schemaVersion") != 2:
        raise NativeEvidenceError(f"{label} schema version is not 2")
    return manifest


def _authenticate_runtime_manifest(
    archive: _OciArchive, manifest: dict[str, Any]
) -> str:
    config = _require_object(manifest.get("config"), "runtime config descriptor")
    if config.get("mediaType") != OCI_CONFIG_MEDIA_TYPE:
        raise NativeEvidenceError("runtime config media type is not exact")
    config_digest = _require_digest(config.get("digest"), "runtime config digest")
    archive.descriptor_bytes(config, MAX_MANIFEST_BYTES, "runtime config")
    layers = manifest.get("layers")
    if not isinstance(layers, list) or not 1 <= len(layers) <= 64:
        raise NativeEvidenceError("runtime layer set is absent or unbounded")
    for index, layer in enumerate(layers):
        layer_object = _require_object(layer, f"runtime layer {index} descriptor")
        if layer_object.get("mediaType") != OCI_LAYER_MEDIA_TYPE:
            raise NativeEvidenceError("runtime layer media type is not exact")
        archive.descriptor_bytes(
            layer_object,
            MAX_OCI_ARCHIVE_BYTES,
            f"runtime layer {index}",
        )
    return config_digest


def _require_exact_runtime_subject(
    statement: dict[str, Any],
    runtime_digest: str,
    platform: str,
) -> None:
    subjects = statement.get("subject")
    if not isinstance(subjects, list) or len(subjects) != 1:
        raise NativeEvidenceError("attestation must name exactly one subject")
    subject = _require_object(subjects[0], "attestation subject")
    architecture = platform.split("/", 1)[1]
    expected_name = (
        "pkg:docker/ofarm-ed25519-evidence@"
        f"{architecture}?platform=linux%2F{architecture}"
    )
    if set(subject) != {"name", "digest"} or subject.get("name") != expected_name:
        raise NativeEvidenceError("attestation subject shape is not exact")
    digest = subject.get("digest")
    if digest != {"sha256": runtime_digest.removeprefix("sha256:")}:
        raise NativeEvidenceError("attestation does not authenticate the runtime child")


def _require_spdx_predicate(predicate: Any) -> None:
    document = _require_object(predicate, "SPDX predicate")
    if (
        document.get("spdxVersion") != "SPDX-2.3"
        or document.get("dataLicense") != "CC0-1.0"
        or document.get("SPDXID") != "SPDXRef-DOCUMENT"
    ):
        raise NativeEvidenceError("SBOM is not an SPDX 2.3 document")
    if not isinstance(document.get("name"), str) or not document["name"]:
        raise NativeEvidenceError("SPDX document name is absent")
    namespace = document.get("documentNamespace")
    if not isinstance(namespace, str) or not namespace.startswith("https://"):
        raise NativeEvidenceError("SPDX document namespace is absent")
    creation_info = document.get("creationInfo")
    if (
        not isinstance(creation_info, dict)
        or not isinstance(creation_info.get("created"), str)
        or not isinstance(creation_info.get("creators"), list)
        or not creation_info["creators"]
        or not all(isinstance(creator, str) and creator for creator in creation_info["creators"])
    ):
        raise NativeEvidenceError("SPDX creation information is incomplete")
    packages = document.get("packages")
    if not isinstance(packages, list) or not packages:
        raise NativeEvidenceError("SPDX package inventory is absent")
    for package in packages:
        package_object = _require_object(package, "SPDX package")
        if (
            not isinstance(package_object.get("SPDXID"), str)
            or not package_object["SPDXID"].startswith("SPDXRef-")
            or not isinstance(package_object.get("name"), str)
            or not package_object["name"]
        ):
            raise NativeEvidenceError("SPDX package identity is incomplete")
    postgresql_packages = [
        package
        for package in packages
        if isinstance(package, dict) and package.get("name") == "postgresql-17"
    ]
    if (
        len(postgresql_packages) != 1
        or postgresql_packages[0].get("versionInfo")
        != POSTGRESQL_PACKAGE_VERSION
    ):
        raise NativeEvidenceError(
            "SBOM PostgreSQL runtime package identity is ambiguous"
        )


def _require_max_provenance_predicate(
    predicate: Any,
    platform: str,
    containerfile_bytes: bytes,
    builder_id: str,
) -> None:
    provenance = _require_object(predicate, "provenance predicate")
    builder = provenance.get("builder")
    if not isinstance(builder, dict) or builder.get("id") != builder_id:
        raise NativeEvidenceError("provenance builder identity is absent")
    if provenance.get("buildType") != BUILDKIT_BUILD_TYPE:
        raise NativeEvidenceError("provenance build type is not BuildKit v1")
    materials = provenance.get("materials")
    if not isinstance(materials, list) or not materials:
        raise NativeEvidenceError("provenance materials are absent")
    for material in materials:
        material_object = _require_object(material, "provenance material")
        if (
            not isinstance(material_object.get("uri"), str)
            or not material_object["uri"]
            or not isinstance(material_object.get("digest"), dict)
            or not material_object["digest"]
        ):
            raise NativeEvidenceError("provenance material identity is incomplete")
    expected_materials = (
        (LIBSODIUM_SOURCE_URL, LIBSODIUM_SOURCE_SHA256),
        SERVER_DEV_SOURCES[platform],
    )
    for expected_uri, expected_digest in expected_materials:
        matching_materials = [
            material
            for material in materials
            if isinstance(material, dict) and material.get("uri") == expected_uri
        ]
        if (
            len(matching_materials) != 1
            or matching_materials[0].get("digest")
            != {"sha256": expected_digest}
        ):
            raise NativeEvidenceError(
                "provenance archive source identity is ambiguous"
            )
    invocation = _require_object(provenance.get("invocation"), "provenance invocation")
    config_source = _require_object(
        invocation.get("configSource"), "provenance config source"
    )
    if config_source.get("entryPoint") != "Containerfile":
        raise NativeEvidenceError("provenance entry point is not the Containerfile")
    parameters = _require_object(
        invocation.get("parameters"), "provenance parameters"
    )
    if (
        not isinstance(parameters.get("frontend"), str)
        or not isinstance(parameters.get("args"), dict)
        or not isinstance(parameters.get("locals"), list)
    ):
        raise NativeEvidenceError("provenance parameters are incomplete")
    environment = _require_object(
        invocation.get("environment"), "provenance environment"
    )
    if environment.get("platform") != platform:
        raise NativeEvidenceError("provenance build platform is inconsistent")
    build_config = _require_object(
        provenance.get("buildConfig"), "max provenance build configuration"
    )
    if not isinstance(build_config.get("llbDefinition"), list) or not build_config[
        "llbDefinition"
    ]:
        raise NativeEvidenceError("max provenance LLB definition is absent")
    metadata = _require_object(provenance.get("metadata"), "provenance metadata")
    if (
        not isinstance(metadata.get("buildInvocationID"), str)
        or not metadata["buildInvocationID"]
        or not isinstance(metadata.get("buildStartedOn"), str)
        or not isinstance(metadata.get("buildFinishedOn"), str)
        or not isinstance(metadata.get("reproducible"), bool)
    ):
        raise NativeEvidenceError("provenance build metadata is incomplete")
    completeness = metadata.get("completeness")
    if (
        not isinstance(completeness, dict)
        or completeness.get("parameters") is not True
        or completeness.get("environment") is not True
        or not isinstance(completeness.get("materials"), bool)
    ):
        raise NativeEvidenceError("provenance completeness flags are incomplete")
    buildkit_metadata = _require_object(
        metadata.get(BUILDKIT_METADATA_KEY), "max BuildKit metadata"
    )
    source = _require_object(buildkit_metadata.get("source"), "max provenance source")
    source_infos = source.get("infos")
    locations = source.get("locations")
    if not isinstance(source_infos, list) or not source_infos:
        raise NativeEvidenceError("max provenance source map is absent")
    containerfile_sources = [
        info
        for info in source_infos
        if isinstance(info, dict)
        and info.get("filename") == "Containerfile"
        and isinstance(info.get("data"), str)
    ]
    if (
        len(containerfile_sources) != 1
        or not isinstance(locations, dict)
        or not locations
    ):
        raise NativeEvidenceError("max provenance source map is absent")
    try:
        attested_containerfile = base64.b64decode(
            containerfile_sources[0]["data"], validate=True
        )
    except (ValueError, binascii.Error) as exc:
        raise NativeEvidenceError("attested Containerfile is not canonical base64") from exc
    if attested_containerfile != containerfile_bytes:
        raise NativeEvidenceError("attested Containerfile differs from reviewed source")


def _authenticate_attestations(
    archive: _OciArchive,
    manifest: dict[str, Any],
    runtime_digest: str,
    platform: str,
    containerfile_bytes: bytes,
    builder_id: str,
) -> dict[str, bytes]:
    config = _require_object(manifest.get("config"), "attestation config descriptor")
    if config.get("mediaType") != OCI_CONFIG_MEDIA_TYPE:
        raise NativeEvidenceError("attestation config media type is not exact")
    archive.descriptor_bytes(config, MAX_MANIFEST_BYTES, "attestation config")
    layers = manifest.get("layers")
    if not isinstance(layers, list) or len(layers) != 2:
        raise NativeEvidenceError("attestation must contain exactly SBOM and provenance")
    evidence: dict[str, bytes] = {}
    limits = {
        SBOM_PREDICATE_TYPE: MAX_SBOM_BYTES,
        PROVENANCE_PREDICATE_TYPE: MAX_PROVENANCE_BYTES,
    }
    for layer in layers:
        layer_object = _require_object(layer, "attestation layer descriptor")
        if layer_object.get("mediaType") != IN_TOTO_MEDIA_TYPE:
            raise NativeEvidenceError("attestation layer media type is not in-toto JSON")
        annotations = layer_object.get("annotations")
        if not isinstance(annotations, dict):
            raise NativeEvidenceError("attestation layer annotations are malformed")
        predicate_type = annotations.get("in-toto.io/predicate-type")
        if predicate_type not in limits or predicate_type in evidence:
            raise NativeEvidenceError("attestation predicate set is unexpected")
        data = archive.descriptor_bytes(
            layer_object,
            limits[predicate_type],
            f"{predicate_type} attestation",
        )
        statement = _require_object(
            _load_json_bytes(data, f"{predicate_type} attestation"),
            f"{predicate_type} attestation",
        )
        if (
            statement.get("_type") != IN_TOTO_STATEMENT_TYPE
            or statement.get("predicateType") != predicate_type
        ):
            raise NativeEvidenceError("attestation statement type is unexpected")
        _require_exact_runtime_subject(statement, runtime_digest, platform)
        if predicate_type == SBOM_PREDICATE_TYPE:
            _require_spdx_predicate(statement.get("predicate"))
        else:
            _require_max_provenance_predicate(
                statement.get("predicate"),
                platform,
                containerfile_bytes,
                builder_id,
            )
        evidence[predicate_type] = data
    if set(evidence) != set(limits):
        raise NativeEvidenceError("attestation predicate set is incomplete")
    return evidence


def collect_oci_evidence(
    *,
    archive_path: Path,
    reproducibility_path: Path,
    platform: str,
    source_commit: str,
    containerfile_path: Path,
    builder_id: str,
    output_directory: Path,
) -> dict[str, Any]:
    """Authenticate one native OCI archive and extract its two attestations."""

    platform = _require_platform(platform)
    source_commit = _require_source_commit(source_commit)
    if not builder_id.startswith("https://github.com/") or len(builder_id) > 512:
        raise NativeEvidenceError("builder id must be one bounded GitHub HTTPS identity")
    containerfile_bytes = _read_bounded(
        containerfile_path, MAX_CONTAINERFILE_BYTES, "reviewed Containerfile"
    )
    reproducibility = _require_object(
        _load_json_file(
            reproducibility_path,
            MAX_REPRODUCIBILITY_REPORT_BYTES,
            "reproducibility report",
        ),
        "reproducibility report",
    )
    if (
        reproducibility.get("schema") != "ofarm.native-reproducibility-evidence.v1"
        or reproducibility.get("platform") != platform
        or reproducibility.get("source_commit") != source_commit
    ):
        raise NativeEvidenceError("reproducibility report identity is inconsistent")
    reproducible_digest = _require_digest(
        reproducibility.get("child_digest"),
        "reproducibility child digest",
    )
    reproducible_config_digest = _require_digest(
        reproducibility.get("config_digest"),
        "reproducibility config digest",
    )
    reproducible_artifacts = reproducibility.get("artifacts")
    if not isinstance(reproducible_artifacts, list) or len(
        reproducible_artifacts
    ) != len(ARTIFACT_CONTRACTS):
        raise NativeEvidenceError("reproducibility artifact set is incomplete")
    for artifact, (expected_name, (maximum, expected_mode)) in zip(
        reproducible_artifacts,
        ARTIFACT_CONTRACTS.items(),
        strict=True,
    ):
        artifact_object = _require_object(artifact, "reproducibility artifact")
        size = artifact_object.get("size")
        if (
            set(artifact_object) != {"name", "mode", "sha256", "size"}
            or artifact_object.get("name") != expected_name
            or artifact_object.get("mode") != expected_mode
            or not isinstance(size, int)
            or isinstance(size, bool)
            or not 0 < size <= maximum
        ):
            raise NativeEvidenceError("reproducibility artifact identity is invalid")
        _require_digest(
            artifact_object.get("sha256"),
            f"reproducibility artifact {expected_name} digest",
        )

    archive = _OciArchive(archive_path)
    try:
        layout = _require_object(
            _load_json_bytes(
                archive.read_member("oci-layout", 4 * 1024, "OCI layout"),
                "OCI layout",
            ),
            "OCI layout",
        )
        if layout != {"imageLayoutVersion": "1.0.0"}:
            raise NativeEvidenceError("OCI layout version is not exactly 1.0.0")
        index = _require_object(
            _load_json_bytes(
                archive.read_member("index.json", MAX_MANIFEST_BYTES, "OCI index"),
                "OCI index",
            ),
            "OCI index",
        )
        image_descriptors, image_index_digest = _resolve_attested_image_index(
            archive, index
        )
        runtime_descriptor, attestation_descriptor = _select_oci_descriptors(
            image_descriptors, platform
        )
        runtime_digest = _require_digest(
            runtime_descriptor.get("digest"), "runtime child digest"
        )
        runtime_size = runtime_descriptor.get("size")
        if (
            not isinstance(runtime_size, int)
            or isinstance(runtime_size, bool)
            or not 0 < runtime_size <= MAX_MANIFEST_BYTES
        ):
            raise NativeEvidenceError("runtime child descriptor size is invalid")
        if runtime_digest != reproducible_digest:
            raise NativeEvidenceError(
                "attested runtime child differs from the two clean builds"
            )
        runtime_manifest = _load_manifest(
            archive, runtime_descriptor, "runtime manifest"
        )
        runtime_config_digest = _authenticate_runtime_manifest(
            archive, runtime_manifest
        )
        if runtime_config_digest != reproducible_config_digest:
            raise NativeEvidenceError(
                "attested runtime config differs from the two clean builds"
            )
        attestation_manifest = _load_manifest(
            archive, attestation_descriptor, "attestation manifest"
        )
        attestations = _authenticate_attestations(
            archive,
            attestation_manifest,
            runtime_digest,
            platform,
            containerfile_bytes,
            builder_id,
        )
        attestation_digest = _require_digest(
            attestation_descriptor.get("digest"), "attestation manifest digest"
        )
        attestation_size = attestation_descriptor.get("size")
        if (
            not isinstance(attestation_size, int)
            or isinstance(attestation_size, bool)
            or not 0 < attestation_size <= MAX_MANIFEST_BYTES
        ):
            raise NativeEvidenceError("attestation manifest size is invalid")
        archive.require_no_unreferenced_blobs()
    finally:
        archive.close()

    output_directory.mkdir(parents=True, exist_ok=True)
    sbom_path = output_directory / "sbom.spdx.in-toto.json"
    provenance_path = output_directory / "provenance.slsa-v0.2.in-toto.json"
    _write_regular(sbom_path, attestations[SBOM_PREDICATE_TYPE])
    _write_regular(provenance_path, attestations[PROVENANCE_PREDICATE_TYPE])
    report = {
        "schema": "ofarm.native-oci-evidence.v1",
        "platform": platform,
        "source_commit": source_commit,
        "builder_id": builder_id,
        "runtime_child_digest": runtime_digest,
        "runtime_child_size": runtime_size,
        "runtime_config_digest": runtime_config_digest,
        "artifacts": reproducible_artifacts,
        "image_index_digest": image_index_digest,
        "attestation_manifest_digest": attestation_digest,
        "attestation_manifest_size": attestation_size,
        "oci_archive": {
            "sha256": archive.sha256,
            "size": archive.size,
        },
        "sbom": {
            "predicate_type": SBOM_PREDICATE_TYPE,
            "sha256": _sha256(attestations[SBOM_PREDICATE_TYPE]),
            "size": len(attestations[SBOM_PREDICATE_TYPE]),
        },
        "provenance": {
            "predicate_type": PROVENANCE_PREDICATE_TYPE,
            "sha256": _sha256(attestations[PROVENANCE_PREDICATE_TYPE]),
            "size": len(attestations[PROVENANCE_PREDICATE_TYPE]),
        },
    }
    _write_regular(output_directory / "oci-evidence.json", _canonical_json_bytes(report))
    return report


def _load_oci_evidence_report(
    path: Path,
    *,
    expected_platform: str,
    source_commit: str,
) -> dict[str, Any]:
    report = _require_object(
        _load_json_file(
            path,
            MAX_OCI_EVIDENCE_REPORT_BYTES,
            f"{expected_platform} OCI evidence report",
        ),
        f"{expected_platform} OCI evidence report",
    )
    if (
        report.get("schema") != "ofarm.native-oci-evidence.v1"
        or report.get("platform") != expected_platform
        or report.get("source_commit") != source_commit
    ):
        raise NativeEvidenceError(
            f"{expected_platform} OCI evidence identity is inconsistent"
        )
    required_keys = {
        "schema",
        "platform",
        "source_commit",
        "builder_id",
        "runtime_child_digest",
        "runtime_child_size",
        "runtime_config_digest",
        "artifacts",
        "image_index_digest",
        "attestation_manifest_digest",
        "attestation_manifest_size",
        "oci_archive",
        "sbom",
        "provenance",
    }
    if set(report) != required_keys:
        raise NativeEvidenceError(
            f"{expected_platform} OCI evidence fields are not exact"
        )
    _require_digest(
        report.get("runtime_child_digest"),
        f"{expected_platform} runtime child digest",
    )
    _require_digest(
        report.get("runtime_config_digest"),
        f"{expected_platform} runtime config digest",
    )
    runtime_size = report.get("runtime_child_size")
    if (
        not isinstance(runtime_size, int)
        or isinstance(runtime_size, bool)
        or not 0 < runtime_size <= MAX_MANIFEST_BYTES
    ):
        raise NativeEvidenceError(
            f"{expected_platform} runtime child descriptor size is invalid"
        )
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != len(ARTIFACT_CONTRACTS):
        raise NativeEvidenceError(
            f"{expected_platform} native artifact inventory is incomplete"
        )
    for artifact, (name, (maximum, expected_mode)) in zip(
        artifacts,
        ARTIFACT_CONTRACTS.items(),
        strict=True,
    ):
        artifact_object = _require_object(
            artifact,
            f"{expected_platform} native artifact",
        )
        size = artifact_object.get("size")
        if (
            set(artifact_object) != {"name", "mode", "sha256", "size"}
            or artifact_object.get("name") != name
            or artifact_object.get("mode") != expected_mode
            or not isinstance(size, int)
            or isinstance(size, bool)
            or not 0 < size <= maximum
        ):
            raise NativeEvidenceError(
                f"{expected_platform} native artifact identity is invalid"
            )
        _require_digest(
            artifact_object.get("sha256"),
            f"{expected_platform} native artifact {name} digest",
        )
    builder_id = report.get("builder_id")
    if (
        not isinstance(builder_id, str)
        or not builder_id.startswith("https://github.com/")
        or len(builder_id) > 512
    ):
        raise NativeEvidenceError(
            f"{expected_platform} builder identity is invalid"
        )
    _require_digest(
        report.get("image_index_digest"),
        f"{expected_platform} source image-index digest",
    )
    _require_digest(
        report.get("attestation_manifest_digest"),
        f"{expected_platform} attestation manifest digest",
    )
    attestation_size = report.get("attestation_manifest_size")
    if (
        not isinstance(attestation_size, int)
        or isinstance(attestation_size, bool)
        or not 0 < attestation_size <= MAX_MANIFEST_BYTES
    ):
        raise NativeEvidenceError(
            f"{expected_platform} attestation manifest size is invalid"
        )
    for name, maximum, predicate in (
        ("oci_archive", MAX_OCI_ARCHIVE_BYTES, None),
        ("sbom", MAX_SBOM_BYTES, SBOM_PREDICATE_TYPE),
        ("provenance", MAX_PROVENANCE_BYTES, PROVENANCE_PREDICATE_TYPE),
    ):
        evidence = _require_object(
            report.get(name), f"{expected_platform} {name} evidence"
        )
        expected_fields = {"sha256", "size"}
        if predicate is not None:
            expected_fields.add("predicate_type")
        if set(evidence) != expected_fields:
            raise NativeEvidenceError(
                f"{expected_platform} {name} evidence fields are not exact"
            )
        _require_digest(
            evidence.get("sha256"), f"{expected_platform} {name} digest"
        )
        size = evidence.get("size")
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or not 0 < size <= maximum
        ):
            raise NativeEvidenceError(
                f"{expected_platform} {name} evidence size is invalid"
            )
        if predicate is not None and evidence.get("predicate_type") != predicate:
            raise NativeEvidenceError(
                f"{expected_platform} {name} predicate is not exact"
            )
    return report


def compose_multi_platform_index(
    *,
    amd64_evidence_path: Path,
    arm64_evidence_path: Path,
    source_commit: str,
    index_output: Path,
    evidence_output: Path,
) -> dict[str, Any]:
    """Compose one canonical OCI index from authenticated native reports."""

    source_commit = _require_source_commit(source_commit)
    reports = [
        _load_oci_evidence_report(
            amd64_evidence_path,
            expected_platform="linux/amd64",
            source_commit=source_commit,
        ),
        _load_oci_evidence_report(
            arm64_evidence_path,
            expected_platform="linux/arm64",
            source_commit=source_commit,
        ),
    ]
    builder_ids = {report["builder_id"] for report in reports}
    if len(builder_ids) != 1:
        raise NativeEvidenceError("native reports name different builder identities")

    manifests: list[dict[str, Any]] = []
    platform_evidence: list[dict[str, Any]] = []
    for report in reports:
        os_name, architecture = report["platform"].split("/", 1)
        manifests.append(
            {
                "mediaType": next(iter(OCI_MANIFEST_MEDIA_TYPES)),
                "digest": report["runtime_child_digest"],
                "size": report["runtime_child_size"],
                "platform": {
                    "architecture": architecture,
                    "os": os_name,
                },
            }
        )
        platform_evidence.append(
            {
                "platform": report["platform"],
                "runtime_child_digest": report["runtime_child_digest"],
                "runtime_child_size": report["runtime_child_size"],
                "runtime_config_digest": report["runtime_config_digest"],
                "artifacts": report["artifacts"],
                "oci_archive": report["oci_archive"],
                "image_index_digest": report["image_index_digest"],
                "attestation_manifest": {
                    "sha256": report["attestation_manifest_digest"],
                    "size": report["attestation_manifest_size"],
                },
                "sbom": report["sbom"],
                "provenance": report["provenance"],
            }
        )

    index = {
        "schemaVersion": 2,
        "mediaType": OCI_INDEX_MEDIA_TYPE,
        "manifests": manifests,
    }
    index_bytes = _canonical_json_bytes(index)
    _write_regular(index_output, index_bytes)
    evidence = {
        "schema": "ofarm.native-multi-platform-index-evidence.v2",
        "source_commit": source_commit,
        "builder_id": reports[0]["builder_id"],
        "workflow_action_pins": CURRENT_NATIVE_ACTION_PINS,
        "build_pins": CURRENT_NATIVE_BUILD_PINS,
        "index": {
            "media_type": OCI_INDEX_MEDIA_TYPE,
            "sha256": _sha256(index_bytes),
            "size": len(index_bytes),
        },
        "platforms": platform_evidence,
    }
    _write_regular(evidence_output, _canonical_json_bytes(evidence))
    return evidence


def prepare_release_identity(
    *,
    checked_identity_path: Path,
    checked_receipt_path: Path,
    index_evidence_path: Path,
    index_path: Path,
    source_directory: Path,
    repository_root: Path,
    candidate_output: Path,
    candidate_receipt_output: Path,
) -> dict[str, Any]:
    """Emit identity/receipt candidates and enforce checked authority linkage."""

    try:
        checked = load_native_release_identity(
            checked_identity_path,
            verify_current_sources=True,
            source_directory=source_directory,
        )
        checked_receipt = load_native_evidence_receipt(
            checked_receipt_path,
            release_identity=checked,
            verify_current_authority=True,
            repository_root=repository_root,
        )
        index_evidence = _require_object(
            _load_json_file(
                index_evidence_path,
                MAX_OCI_EVIDENCE_REPORT_BYTES,
                "multi-platform index evidence",
            ),
            "multi-platform index evidence",
        )
        index_bytes = _read_bounded(
            index_path,
            MAX_METADATA_BYTES,
            "canonical multi-platform index",
        )
        candidate = frozen_identity_document(
            index_evidence=index_evidence,
            index_bytes=index_bytes,
            source_directory=source_directory,
        )
    except NativeReleaseIdentityError as exc:
        raise NativeEvidenceError(str(exc)) from exc
    candidate_bytes = release_canonical_json_bytes(candidate)
    if checked.status == "frozen" and checked.canonical_bytes != candidate_bytes:
        raise NativeEvidenceError(
            "hosted native result differs from the frozen release identity"
        )
    try:
        candidate_identity = validate_native_release_identity(
            candidate,
            canonical_bytes=candidate_bytes,
            source_directory=source_directory,
        )
        candidate_receipt = candidate_evidence_receipt_document(
            release_identity=candidate_identity,
            index_evidence=index_evidence,
            index_bytes=index_bytes,
            repository_root=repository_root,
        )
    except NativeReleaseIdentityError as exc:
        raise NativeEvidenceError(str(exc)) from exc
    candidate_receipt_bytes = release_canonical_json_bytes(candidate_receipt)
    _write_regular(candidate_output, candidate_bytes)
    _write_regular(candidate_receipt_output, candidate_receipt_bytes)
    return {
        "checked_status": checked.status,
        "checked_receipt_status": checked_receipt.status,
        "candidate_digest": _sha256(candidate_bytes),
        "candidate_index_digest": candidate["index"]["sha256"],
        "candidate_receipt_digest": _sha256(candidate_receipt_bytes),
    }


def _bounded_file_identity(path: Path, maximum: int, label: str) -> dict[str, Any]:
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise NativeEvidenceError(f"{label} is unavailable") from exc
    if path.is_symlink() or not stat.S_ISREG(file_stat.st_mode):
        raise NativeEvidenceError(f"{label} must be one regular file")
    if not 0 < file_stat.st_size <= maximum:
        raise NativeEvidenceError(f"{label} has an invalid size")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as input_file:
            while chunk := input_file.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise NativeEvidenceError(f"{label} cannot be read") from exc
    return {"sha256": "sha256:" + digest.hexdigest(), "size": file_stat.st_size}


def finalize_evidence_receipt(
    *,
    release_identity_path: Path,
    candidate_receipt_path: Path,
    source_directory: Path,
    repository_root: Path,
    amd64_download: Path,
    arm64_download: Path,
    output: Path,
) -> dict[str, Any]:
    """Freeze a receipt after independently downloaded Release assets verify."""

    try:
        identity = load_native_release_identity(
            release_identity_path,
            verify_current_sources=True,
            source_directory=source_directory,
        )
        candidate = load_native_evidence_receipt(
            candidate_receipt_path,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=repository_root,
            allow_candidate=True,
        )
    except NativeReleaseIdentityError as exc:
        raise NativeEvidenceError(str(exc)) from exc
    if identity.status != "frozen" or candidate.status != "candidate":
        raise NativeEvidenceError(
            "receipt finalization requires frozen identity and candidate receipt"
        )
    downloads = [amd64_download, arm64_download]
    for path, platform, asset in zip(
        downloads,
        candidate.document["platforms"],
        candidate.document["preservation"]["assets"],
        strict=True,
    ):
        if path.name != asset["name"]:
            raise NativeEvidenceError(
                f"{platform['platform']} Release download name is not exact"
            )
        observed = _bounded_file_identity(
            path,
            MAX_OCI_ARCHIVE_BYTES,
            f"{platform['platform']} Release download",
        )
        if observed != platform["ociArchive"] or observed != {
            "sha256": asset["sha256"],
            "size": asset["size"],
        }:
            raise NativeEvidenceError(
                f"{platform['platform']} Release download differs from candidate receipt"
            )
    try:
        frozen = frozen_evidence_receipt_document(
            candidate_receipt=candidate,
            release_identity=identity,
            repository_root=repository_root,
        )
    except NativeReleaseIdentityError as exc:
        raise NativeEvidenceError(str(exc)) from exc
    frozen_bytes = release_canonical_json_bytes(frozen)
    _write_regular(output, frozen_bytes)
    return {
        "status": "frozen",
        "release_identity_digest": identity.digest,
        "receipt_digest": _sha256(frozen_bytes),
    }


def conformance_environment(
    *,
    checked_identity_path: Path,
    checked_receipt_path: Path,
    metadata_path: Path,
    source_directory: Path,
    repository_root: Path,
    image_name: str,
    metadata_reference: str,
) -> str:
    """Resolve exact derived-image test inputs without a frozen bootstrap claim."""

    if image_name != "ofarm-postgresql-conformance:local":
        raise NativeEvidenceError("conformance image name is not the exact local tag")
    if (
        not metadata_reference
        or len(metadata_reference) > 1024
        or "\n" in metadata_reference
        or "\r" in metadata_reference
    ):
        raise NativeEvidenceError("conformance metadata reference is invalid")
    try:
        identity = load_native_release_identity(
            checked_identity_path,
            verify_current_sources=True,
            source_directory=source_directory,
        )
        receipt = load_native_evidence_receipt(
            checked_receipt_path,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=repository_root,
        )
    except NativeReleaseIdentityError as exc:
        raise NativeEvidenceError(str(exc)) from exc
    observed_child, observed_config = metadata_child_identity(
        metadata_path,
        "derived PostgreSQL build metadata",
    )
    if identity.status == "frozen":
        amd64 = identity.document["platforms"][0]
        expected_child = amd64["runtimeChildDigest"]
        expected_config = amd64["runtimeConfigDigest"]
        if (observed_child, observed_config) != (expected_child, expected_config):
            raise NativeEvidenceError(
                "derived PostgreSQL build differs from frozen amd64 identity"
            )
    else:
        expected_child = observed_child
        expected_config = observed_config
    values = {
        "ISSUE174_DERIVED_POSTGRES_IMAGE": image_name,
        "ISSUE174_DERIVED_POSTGRES_METADATA": metadata_reference,
        "ISSUE174_DERIVED_POSTGRES_CHILD_DIGEST": expected_child,
        "ISSUE174_DERIVED_POSTGRES_CONFIG_DIGEST": expected_config,
        "ISSUE174_DERIVED_POSTGRES_IDENTITY_STATUS": identity.status,
        "ISSUE174_DERIVED_POSTGRES_EVIDENCE_RECEIPT_DIGEST": receipt.digest,
        "ISSUE174_DERIVED_POSTGRES_EVIDENCE_RECEIPT_STATUS": receipt.status,
    }
    return "".join(f"{name}={value}\n" for name, value in values.items())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare = subparsers.add_parser("compare-builds")
    compare.add_argument("--first-metadata", type=Path, required=True)
    compare.add_argument("--second-metadata", type=Path, required=True)
    compare.add_argument("--first-artifacts", type=Path, required=True)
    compare.add_argument("--second-artifacts", type=Path, required=True)
    compare.add_argument("--platform", required=True)
    compare.add_argument("--source-commit", required=True)
    compare.add_argument("--output", type=Path, required=True)

    collect = subparsers.add_parser("collect-oci")
    collect.add_argument("--archive", type=Path, required=True)
    collect.add_argument("--reproducibility", type=Path, required=True)
    collect.add_argument("--platform", required=True)
    collect.add_argument("--source-commit", required=True)
    collect.add_argument("--containerfile", type=Path, required=True)
    collect.add_argument("--builder-id", required=True)
    collect.add_argument("--output-directory", type=Path, required=True)

    compose = subparsers.add_parser("compose-index")
    compose.add_argument("--amd64-evidence", type=Path, required=True)
    compose.add_argument("--arm64-evidence", type=Path, required=True)
    compose.add_argument("--source-commit", required=True)
    compose.add_argument("--index-output", type=Path, required=True)
    compose.add_argument("--evidence-output", type=Path, required=True)

    release = subparsers.add_parser("prepare-release-identity")
    release.add_argument("--checked-identity", type=Path, required=True)
    release.add_argument("--checked-receipt", type=Path, required=True)
    release.add_argument("--index-evidence", type=Path, required=True)
    release.add_argument("--index", type=Path, required=True)
    release.add_argument("--source-directory", type=Path, required=True)
    release.add_argument("--repository-root", type=Path, required=True)
    release.add_argument("--candidate-output", type=Path, required=True)
    release.add_argument("--candidate-receipt-output", type=Path, required=True)

    finalize = subparsers.add_parser("finalize-evidence-receipt")
    finalize.add_argument("--release-identity", type=Path, required=True)
    finalize.add_argument("--candidate-receipt", type=Path, required=True)
    finalize.add_argument("--source-directory", type=Path, required=True)
    finalize.add_argument("--repository-root", type=Path, required=True)
    finalize.add_argument("--amd64-download", type=Path, required=True)
    finalize.add_argument("--arm64-download", type=Path, required=True)
    finalize.add_argument("--output", type=Path, required=True)

    environment = subparsers.add_parser("conformance-environment")
    environment.add_argument("--checked-identity", type=Path, required=True)
    environment.add_argument("--checked-receipt", type=Path, required=True)
    environment.add_argument("--metadata", type=Path, required=True)
    environment.add_argument("--source-directory", type=Path, required=True)
    environment.add_argument("--repository-root", type=Path, required=True)
    environment.add_argument("--image-name", required=True)
    environment.add_argument("--metadata-reference", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "compare-builds":
            compare_builds(
                first_metadata=args.first_metadata,
                second_metadata=args.second_metadata,
                first_artifacts=args.first_artifacts,
                second_artifacts=args.second_artifacts,
                platform=args.platform,
                source_commit=args.source_commit,
                output=args.output,
            )
        elif args.command == "collect-oci":
            collect_oci_evidence(
                archive_path=args.archive,
                reproducibility_path=args.reproducibility,
                platform=args.platform,
                source_commit=args.source_commit,
                containerfile_path=args.containerfile,
                builder_id=args.builder_id,
                output_directory=args.output_directory,
            )
        elif args.command == "compose-index":
            compose_multi_platform_index(
                amd64_evidence_path=args.amd64_evidence,
                arm64_evidence_path=args.arm64_evidence,
                source_commit=args.source_commit,
                index_output=args.index_output,
                evidence_output=args.evidence_output,
            )
        elif args.command == "prepare-release-identity":
            prepare_release_identity(
                checked_identity_path=args.checked_identity,
                checked_receipt_path=args.checked_receipt,
                index_evidence_path=args.index_evidence,
                index_path=args.index,
                source_directory=args.source_directory,
                repository_root=args.repository_root,
                candidate_output=args.candidate_output,
                candidate_receipt_output=args.candidate_receipt_output,
            )
        elif args.command == "finalize-evidence-receipt":
            finalize_evidence_receipt(
                release_identity_path=args.release_identity,
                candidate_receipt_path=args.candidate_receipt,
                source_directory=args.source_directory,
                repository_root=args.repository_root,
                amd64_download=args.amd64_download,
                arm64_download=args.arm64_download,
                output=args.output,
            )
        else:
            print(
                conformance_environment(
                    checked_identity_path=args.checked_identity,
                    checked_receipt_path=args.checked_receipt,
                    metadata_path=args.metadata,
                    source_directory=args.source_directory,
                    repository_root=args.repository_root,
                    image_name=args.image_name,
                    metadata_reference=args.metadata_reference,
                ),
                end="",
            )
    except NativeEvidenceError as exc:
        raise SystemExit(f"native evidence refused: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
