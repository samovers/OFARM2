"""Exact current/provisional identity for the confined native verifier image."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_PATH = (
    PACKAGE_ROOT
    / "deployment"
    / "postgresql"
    / "ofarm_ed25519"
    / "native_release_identity.json"
)
SOURCE_DIRECTORY = IDENTITY_PATH.parent
MAX_IDENTITY_BYTES = 256 * 1024
MAX_INDEX_BYTES = 64 * 1024
SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
OCI_INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"

CURRENT_NATIVE_ACTION_PINS = {
    "actions/checkout@v5": "93cb6efe18208431cddfb8368fd83d5badbf9bfd",
    "actions/download-artifact@v7": "37930b1c2abaa49bbe596cd826c3c89aef350131",
    "actions/setup-python@v6": "ece7cb06caefa5fff74198d8649806c4678c61a1",
    "actions/upload-artifact@v6": "b7c566a772e6b6bfb58ed0dc250532a479d7789f",
    "docker/setup-buildx-action@v3": (
        "8d2750c68a42422c14e847fe6c8ac0403b4cbd6f"
    ),
}
CURRENT_NATIVE_BUILD_PINS = {
    "buildkitImage": (
        "moby/buildkit@sha256:"
        "c457984bd29f04d6acc90c8d9e717afe3922ae14665f3187e0096976fe37b1c8"
    ),
    "containerfileFrontend": (
        "docker/dockerfile:1.7@sha256:"
        "a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e"
    ),
    "gccBuilder": (
        "gcc@sha256:"
        "1ea81e094f614fd2ed066316651dbac8eecb4d36add2ddd8a26151374c85c52c"
    ),
    "postgresqlRuntime": (
        "postgres@sha256:"
        "5f050f770b427fbd477edee6c3968a72e5c6be97e050a7e368b2b74a9494a285"
    ),
    "sbomGenerator": (
        "docker/buildkit-syft-scanner@sha256:"
        "79e7b013cbec16bbb436f312819a49a4a57752b2270c1a9332ae1a10fcc82a68"
    ),
    "libsodiumSource": {
        "url": (
            "https://download.libsodium.org/libsodium/releases/"
            "libsodium-1.0.22.tar.gz"
        ),
        "sha256": (
            "sha256:"
            "adbdd8f16149e81ac6078a03aca6fc03b592b89ef7b5ed83841c086191be3349"
        ),
        "size": 2008529,
    },
    "postgresqlServerDevelopment": [
        {
            "platform": "linux/amd64",
            "url": (
                "https://apt.postgresql.org/pub/repos/apt/pool/main/p/"
                "postgresql-17/"
                "postgresql-server-dev-17_17.10-1.pgdg13+1_amd64.deb"
            ),
            "sha256": (
                "sha256:"
                "adc91a999ec840f8db8c8df5ac2473fe1deeaed0e76bd5a6391afa7c74bceac3"
            ),
            "size": 1338208,
        },
        {
            "platform": "linux/arm64",
            "url": (
                "https://apt.postgresql.org/pub/repos/apt/pool/main/p/"
                "postgresql-17/"
                "postgresql-server-dev-17_17.10-1.pgdg13+1_arm64.deb"
            ),
            "sha256": (
                "sha256:"
                "372c8eb77604bc9cba61689661701e65a336b14a43e8f9be850088bb8c4428b6"
            ),
            "size": 1327764,
        },
    ],
}
NATIVE_SOURCE_PATHS = (
    "Containerfile",
    "Makefile",
    "generate_ofarm_ed25519_vectors.py",
    "ofarm_ed25519--1.0.sql",
    "ofarm_ed25519.c",
    "ofarm_ed25519.control",
    "ofarm_ed25519.exports",
    "ofarm_ed25519_core.c",
    "ofarm_ed25519_core.h",
    "ofarm_ed25519_fault_test.sql",
    "ofarm_ed25519_fuzz.c",
    "ofarm_ed25519_harness.c",
    "ofarm_ed25519_live_test.sql",
    "ofarm_ed25519_vectors.h",
    "ofarm_ed25519_vectors.json",
    "ofarm_ed25519_vectors.sha256",
    "ofarm_ed25519_vectors.sql",
)
ARTIFACT_NAMES_AND_MODES = (
    ("libsodium.a", "0644"),
    ("ofarm_ed25519.so", "0755"),
    ("ofarm_ed25519.control", "0644"),
    ("ofarm_ed25519--1.0.sql", "0644"),
)


class NativeReleaseIdentityError(RuntimeError):
    """Raised when the checked native release identity is ambiguous or stale."""


def _duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise NativeReleaseIdentityError("identity JSON contains a duplicate key")
        result[key] = value
    return result


def _load_json_bytes(data: bytes, label: str) -> Any:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                NativeReleaseIdentityError(f"{label} contains forbidden {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise NativeReleaseIdentityError(f"{label} is not valid UTF-8 JSON") from exc


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("ascii")


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise NativeReleaseIdentityError(f"{label} is not one canonical SHA-256")
    return value


def _read_regular(path: Path, maximum: int, label: str) -> bytes:
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise NativeReleaseIdentityError(f"{label} is unavailable") from exc
    if path.is_symlink() or not stat.S_ISREG(file_stat.st_mode):
        raise NativeReleaseIdentityError(f"{label} must be one regular file")
    if not 0 < file_stat.st_size <= maximum:
        raise NativeReleaseIdentityError(f"{label} has an invalid size")
    return path.read_bytes()


def source_input_manifest(source_directory: Path = SOURCE_DIRECTORY) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for name in NATIVE_SOURCE_PATHS:
        data = _read_regular(source_directory / name, 1024 * 1024, f"source {name}")
        files.append({"path": name, "sha256": _digest(data), "size": len(data)})
    body = {"algorithm": "sha256", "files": files}
    return {**body, "digest": _digest(canonical_json_bytes(body))}


def _validate_source_input(
    value: Any,
    *,
    source_directory: Path | None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"algorithm", "digest", "files"}:
        raise NativeReleaseIdentityError("source-input identity fields are not exact")
    if value.get("algorithm") != "sha256":
        raise NativeReleaseIdentityError("source-input algorithm is not SHA-256")
    files = value.get("files")
    if not isinstance(files, list) or len(files) != len(NATIVE_SOURCE_PATHS):
        raise NativeReleaseIdentityError("source-input file inventory is incomplete")
    for item, expected_path in zip(files, NATIVE_SOURCE_PATHS, strict=True):
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "sha256", "size"}
            or item.get("path") != expected_path
            or not isinstance(item.get("size"), int)
            or isinstance(item.get("size"), bool)
            or not 0 < item["size"] <= 1024 * 1024
        ):
            raise NativeReleaseIdentityError("source-input file identity is invalid")
        _require_digest(item.get("sha256"), f"source {expected_path} digest")
    body = {"algorithm": "sha256", "files": files}
    if _require_digest(value.get("digest"), "source-input digest") != _digest(
        canonical_json_bytes(body)
    ):
        raise NativeReleaseIdentityError("source-input manifest digest is inconsistent")
    if source_directory is not None and value != source_input_manifest(source_directory):
        raise NativeReleaseIdentityError("source-input identity differs from current files")
    return value


def _validate_artifacts(value: Any, platform: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(ARTIFACT_NAMES_AND_MODES):
        raise NativeReleaseIdentityError(f"{platform} artifact inventory is incomplete")
    for artifact, (name, mode) in zip(value, ARTIFACT_NAMES_AND_MODES, strict=True):
        if (
            not isinstance(artifact, dict)
            or set(artifact) != {"mode", "name", "sha256", "size"}
            or artifact.get("name") != name
            or artifact.get("mode") != mode
            or not isinstance(artifact.get("size"), int)
            or isinstance(artifact.get("size"), bool)
            or not 0 < artifact["size"] <= 8 * 1024 * 1024
        ):
            raise NativeReleaseIdentityError(f"{platform} artifact identity is invalid")
        _require_digest(artifact.get("sha256"), f"{platform} {name} digest")
    return value


def _validate_platforms(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != 2:
        raise NativeReleaseIdentityError("frozen platform inventory is not exact")
    for platform_value, expected_platform in zip(
        value, ("linux/amd64", "linux/arm64"), strict=True
    ):
        if not isinstance(platform_value, dict) or set(platform_value) != {
            "artifacts",
            "platform",
            "runtimeChildDigest",
            "runtimeChildSize",
            "runtimeConfigDigest",
        }:
            raise NativeReleaseIdentityError("platform identity fields are not exact")
        if platform_value.get("platform") != expected_platform:
            raise NativeReleaseIdentityError("platform identity order is not exact")
        _require_digest(
            platform_value.get("runtimeChildDigest"),
            f"{expected_platform} child digest",
        )
        _require_digest(
            platform_value.get("runtimeConfigDigest"),
            f"{expected_platform} config digest",
        )
        if (
            not isinstance(platform_value.get("runtimeChildSize"), int)
            or isinstance(platform_value.get("runtimeChildSize"), bool)
            or not 0 < platform_value["runtimeChildSize"] <= MAX_INDEX_BYTES
        ):
            raise NativeReleaseIdentityError(
                f"{expected_platform} child descriptor size is invalid"
            )
        _validate_artifacts(platform_value.get("artifacts"), expected_platform)
    return value


def _validate_index(value: Any, platforms: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "canonicalBytesBase64",
        "mediaType",
        "sha256",
        "size",
    }:
        raise NativeReleaseIdentityError("canonical index identity fields are not exact")
    encoded = value.get("canonicalBytesBase64")
    if not isinstance(encoded, str) or len(encoded) > MAX_INDEX_BYTES * 2:
        raise NativeReleaseIdentityError("canonical index base64 is invalid")
    try:
        index_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise NativeReleaseIdentityError("canonical index base64 is invalid") from exc
    if (
        not index_bytes
        or len(index_bytes) > MAX_INDEX_BYTES
        or value.get("size") != len(index_bytes)
        or value.get("mediaType") != OCI_INDEX_MEDIA_TYPE
        or _require_digest(value.get("sha256"), "canonical index digest")
        != _digest(index_bytes)
    ):
        raise NativeReleaseIdentityError("canonical index identity is inconsistent")
    index = _load_json_bytes(index_bytes, "canonical index")
    if canonical_json_bytes(index) != index_bytes or not isinstance(index, dict):
        raise NativeReleaseIdentityError("canonical index bytes are not canonical JSON")
    if set(index) != {"manifests", "mediaType", "schemaVersion"} or (
        index.get("schemaVersion") != 2
        or index.get("mediaType") != OCI_INDEX_MEDIA_TYPE
    ):
        raise NativeReleaseIdentityError("canonical index structure is not exact")
    manifests = index.get("manifests")
    if not isinstance(manifests, list) or len(manifests) != 2:
        raise NativeReleaseIdentityError("canonical index platform set is not exact")
    for descriptor, platform_value in zip(manifests, platforms, strict=True):
        os_name, architecture = platform_value["platform"].split("/", 1)
        if descriptor != {
            "digest": platform_value["runtimeChildDigest"],
            "mediaType": OCI_MANIFEST_MEDIA_TYPE,
            "platform": {"architecture": architecture, "os": os_name},
            "size": platform_value["runtimeChildSize"],
        }:
            raise NativeReleaseIdentityError(
                "canonical index descriptor differs from platform identity"
            )
    return value


@dataclass(frozen=True)
class NativeReleaseIdentity:
    """Validated native identity exposed to binder and deployment manifests."""

    document: dict[str, Any]
    canonical_bytes: bytes
    digest: str

    @property
    def status(self) -> str:
        return self.document["status"]

    @property
    def index_digest(self) -> str | None:
        index = self.document["index"]
        return None if index is None else index["sha256"]

    def manifest(self) -> dict[str, Any]:
        return json.loads(self.canonical_bytes)


def validate_native_release_identity(
    document: Any,
    *,
    canonical_bytes: bytes,
    source_directory: Path | None,
) -> NativeReleaseIdentity:
    if not isinstance(document, dict) or set(document) != {
        "buildPins",
        "index",
        "platforms",
        "schemaVersion",
        "sourceInput",
        "status",
        "workflowActionPins",
    }:
        raise NativeReleaseIdentityError("native identity fields are not exact")
    if canonical_json_bytes(document) != canonical_bytes:
        raise NativeReleaseIdentityError("native identity JSON is not canonical")
    if document.get("schemaVersion") != "ofarm.native-verifier-release-identity.v1":
        raise NativeReleaseIdentityError("native identity schema is not exact")
    if document.get("workflowActionPins") != CURRENT_NATIVE_ACTION_PINS:
        raise NativeReleaseIdentityError("native workflow action pins differ")
    if document.get("buildPins") != CURRENT_NATIVE_BUILD_PINS:
        raise NativeReleaseIdentityError("native build pins differ")
    _validate_source_input(document.get("sourceInput"), source_directory=source_directory)
    status_value = document.get("status")
    if status_value == "provisional":
        if document.get("platforms") != [] or document.get("index") is not None:
            raise NativeReleaseIdentityError(
                "provisional native identity contains frozen result claims"
            )
    elif status_value == "frozen":
        platforms = _validate_platforms(document.get("platforms"))
        _validate_index(document.get("index"), platforms)
    else:
        raise NativeReleaseIdentityError("native identity status is not exact")
    return NativeReleaseIdentity(document, canonical_bytes, _digest(canonical_bytes))


def load_native_release_identity(
    path: Path = IDENTITY_PATH,
    *,
    verify_current_sources: bool = False,
    source_directory: Path | None = None,
) -> NativeReleaseIdentity:
    data = _read_regular(path, MAX_IDENTITY_BYTES, "native release identity")
    document = _load_json_bytes(data, "native release identity")
    return validate_native_release_identity(
        document,
        canonical_bytes=data,
        source_directory=(
            source_directory or SOURCE_DIRECTORY
            if verify_current_sources
            else None
        ),
    )


def provisional_identity_document(
    source_directory: Path = SOURCE_DIRECTORY,
) -> dict[str, Any]:
    return {
        "schemaVersion": "ofarm.native-verifier-release-identity.v1",
        "status": "provisional",
        "sourceInput": source_input_manifest(source_directory),
        "buildPins": CURRENT_NATIVE_BUILD_PINS,
        "workflowActionPins": CURRENT_NATIVE_ACTION_PINS,
        "platforms": [],
        "index": None,
    }


def frozen_identity_document(
    *,
    index_evidence: dict[str, Any],
    index_bytes: bytes,
    source_directory: Path = SOURCE_DIRECTORY,
) -> dict[str, Any]:
    """Build and fully validate the stable identity from hosted fan-in evidence."""

    if not isinstance(index_evidence, dict) or set(index_evidence) != {
        "builder_id",
        "index",
        "platforms",
        "schema",
        "source_commit",
        "workflow_action_pins",
    }:
        raise NativeReleaseIdentityError("native index evidence fields are not exact")
    if (
        index_evidence.get("schema")
        != "ofarm.native-multi-platform-index-evidence.v1"
        or index_evidence.get("workflow_action_pins") != CURRENT_NATIVE_ACTION_PINS
    ):
        raise NativeReleaseIdentityError("native index evidence identity differs")
    evidence_index = index_evidence.get("index")
    if not isinstance(evidence_index, dict) or evidence_index != {
        "media_type": OCI_INDEX_MEDIA_TYPE,
        "sha256": _digest(index_bytes),
        "size": len(index_bytes),
    }:
        raise NativeReleaseIdentityError("native index bytes differ from fan-in evidence")
    evidence_platforms = index_evidence.get("platforms")
    if not isinstance(evidence_platforms, list) or len(evidence_platforms) != 2:
        raise NativeReleaseIdentityError("native fan-in platform set is not exact")
    platforms: list[dict[str, Any]] = []
    for item, expected_platform in zip(
        evidence_platforms, ("linux/amd64", "linux/arm64"), strict=True
    ):
        if not isinstance(item, dict) or set(item) != {
            "artifacts",
            "attestation_manifest_digest",
            "oci_archive_sha256",
            "platform",
            "runtime_child_digest",
            "runtime_child_size",
            "runtime_config_digest",
        }:
            raise NativeReleaseIdentityError("native fan-in platform fields are not exact")
        if item.get("platform") != expected_platform:
            raise NativeReleaseIdentityError("native fan-in platform order differs")
        platforms.append(
            {
                "platform": expected_platform,
                "runtimeChildDigest": item.get("runtime_child_digest"),
                "runtimeChildSize": item.get("runtime_child_size"),
                "runtimeConfigDigest": item.get("runtime_config_digest"),
                "artifacts": item.get("artifacts"),
            }
        )
    document = {
        "schemaVersion": "ofarm.native-verifier-release-identity.v1",
        "status": "frozen",
        "sourceInput": source_input_manifest(source_directory),
        "buildPins": CURRENT_NATIVE_BUILD_PINS,
        "workflowActionPins": CURRENT_NATIVE_ACTION_PINS,
        "platforms": platforms,
        "index": {
            "mediaType": OCI_INDEX_MEDIA_TYPE,
            "sha256": _digest(index_bytes),
            "size": len(index_bytes),
            "canonicalBytesBase64": base64.b64encode(index_bytes).decode("ascii"),
        },
    }
    validate_native_release_identity(
        document,
        canonical_bytes=canonical_json_bytes(document),
        source_directory=source_directory,
    )
    return document
