"""Exact release identity and durable evidence receipt for the native verifier."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
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
EVIDENCE_RECEIPT_PATH = (
    PACKAGE_ROOT
    / "deployment"
    / "postgresql"
    / "ofarm_ed25519"
    / "native_evidence_receipt.json"
)
SOURCE_DIRECTORY = IDENTITY_PATH.parent
MAX_IDENTITY_BYTES = 256 * 1024
MAX_EVIDENCE_RECEIPT_BYTES = 768 * 1024
MAX_INDEX_BYTES = 64 * 1024
MAX_EVIDENCE_AUTHORITY_FILE_BYTES = 2 * 1024 * 1024
MAX_PROVIDER_VERIFICATION_BYTES = 64 * 1024
SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
OCI_INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
SBOM_PREDICATE_TYPE = "https://spdx.dev/Document"
PROVENANCE_PREDICATE_TYPE = "https://slsa.dev/provenance/v0.2"
NATIVE_RELEASE_REPOSITORY = "samovers/OFARM2"
NATIVE_RELEASE_REPOSITORY_ID = 1266697770
NATIVE_RELEASE_REPOSITORY_NODE_ID = "R_kgDOS4BGKg"
NATIVE_RELEASE_OWNER_ID = "263070375"
NATIVE_RELEASE_REPOSITORY_API_URL = (
    "https://api.github.com/repos/" + NATIVE_RELEASE_REPOSITORY
)
NATIVE_RELEASE_REPOSITORY_URL = (
    "https://github.com/" + NATIVE_RELEASE_REPOSITORY
)
NATIVE_RELEASE_GITHUB_API_VERSION = "2026-03-10"
NATIVE_RELEASE_GITHUB_CLI_VERSION = "2.96.0"
NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT = (
    "gh version 2.96.0 (2026-07-02)\n"
    "https://github.com/cli/cli/releases/tag/v2.96.0\n"
).encode("ascii")
GITHUB_PROVIDER_VERIFICATION_SCHEMA = (
    "ofarm.github-release-provider-verification.v2"
)
EVIDENCE_RECEIPT_SCHEMA_V1 = "ofarm.native-verifier-evidence-receipt.v1"
EVIDENCE_RECEIPT_SCHEMA_V2 = "ofarm.native-verifier-evidence-receipt.v2"
HISTORICAL_V1_CANDIDATE_RECEIPT_DIGEST = (
    "sha256:ddb70333297aeda15961fe4ab8d045e918a1f5d6e44645fe51940db1e4d13fa2"
)
HISTORICAL_V1_RELEASE_IDENTITY_DIGEST = (
    "sha256:7aae043c84013e8f05b1729e2de23358486e57e661c170074d15d0b135225775"
)
HISTORICAL_V1_SOURCE_COMMIT = "cb25339b859aadf7d38be2ca0452511284cc8438"
HISTORICAL_V1_RUN_ID = 29717583674
HISTORICAL_V1_RUN_ATTEMPT = 1
FROZEN_PROVIDER_VERIFICATION_DIGESTS = {
    "sha256:7aae043c84013e8f05b1729e2de23358486e57e661c170074d15d0b135225775": (
        "sha256:a3e2bd305a38ded067c7547781362f05792a1da7a017da8919adb9b21c36802b"
    )
}
GITHUB_RELEASE_PREDICATE_TYPE = (
    "https://in-toto.io/attestation/release/v0.2"
)
IN_TOTO_STATEMENT_V1 = "https://in-toto.io/Statement/v1"
SIGSTORE_BUNDLE_MEDIA_TYPE = "application/vnd.dev.sigstore.bundle.v0.3+json"
SIGSTORE_VERIFICATION_RESULT_MEDIA_TYPE = (
    "application/vnd.dev.sigstore.verificationresult+json;version=0.1"
)
GITHUB_RELEASE_CERTIFICATE_ISSUER = (
    "CN=Fulcio Intermediate l1,O=GitHub\\, Inc."
)
GITHUB_RELEASE_CERTIFICATE_SAN = "https://dotcom.releases.github.com"
GITHUB_RELEASE_TIMESTAMP_AUTHORITY_URI = "timestamp.githubapp.com"
GITHUB_RELEASE_VERIFIED_IDENTITY = {
    "issuer": {"issuer": "", "regexp": ".*"},
    "subjectAlternativeName": {
        "regexp": r"^https://dotcom\.releases\.github\.com$",
        "subjectAlternativeName": "",
    },
}
GITHUB_RELEASE_TIMESTAMP_PATTERN = re.compile(
    r"[0-9]{4}-(?:0[1-9]|1[0-2])-"
    r"(?:0[1-9]|[12][0-9]|3[01])T"
    r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"(?:\.[0-9]{0,8}[1-9])?Z\Z"
)
BUILDER_ID_PATTERN = re.compile(
    r"https://github\.com/samovers/OFARM2/actions/runs/"
    r"([1-9][0-9]*)/attempts/([1-9][0-9]*)\Z"
)
CHECKED_EVIDENCE_RECEIPT_PATH = (
    "deployment/postgresql/ofarm_ed25519/native_evidence_receipt.json"
)
EVIDENCE_AUTHORITY_PATHS = (
    ".github/workflows/conformance.yml",
    "deployment/postgresql/native_evidence.py",
    "deployment/postgresql/native_release_identity.py",
    "kernel/tests/test_postgresql_ed25519_native_build.py",
    "kernel/tests/test_postgresql_native_evidence.py",
    "kernel/tests/test_postgresql_physical_clone.py",
)
PLATFORM_ORDER = ("linux/amd64", "linux/arm64")

FROZEN_NATIVE_RELEASE_ACTION_PINS = {
    "actions/checkout@v5": "93cb6efe18208431cddfb8368fd83d5badbf9bfd",
    "actions/download-artifact@v7": "37930b1c2abaa49bbe596cd826c3c89aef350131",
    "actions/setup-python@v6": "ece7cb06caefa5fff74198d8649806c4678c61a1",
    "actions/upload-artifact@v6": "b7c566a772e6b6bfb58ed0dc250532a479d7789f",
    "docker/setup-buildx-action@v3": (
        "8d2750c68a42422c14e847fe6c8ac0403b4cbd6f"
    ),
}
CURRENT_NATIVE_REPRODUCER_ACTION_PINS = {
    key: value
    for key, value in FROZEN_NATIVE_RELEASE_ACTION_PINS.items()
    if key != "docker/setup-buildx-action@v3"
}
CURRENT_NATIVE_BUILD_PINS = {
    "buildxClient": {
        "version": "v0.34.1",
        "sourceCommit": "e0b0e77d18d3379bc1e0d55f3b37de288d36fe47",
    },
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
    flags = os.O_RDONLY
    for flag_name in ("O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK"):
        flags |= getattr(os, flag_name, 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise NativeReleaseIdentityError(f"{label} is unavailable") from exc
    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            raise NativeReleaseIdentityError(f"{label} must be one regular file")
        if not 0 < file_stat.st_size <= maximum:
            raise NativeReleaseIdentityError(f"{label} has an invalid size")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if not 0 < len(data) <= maximum or len(data) != file_stat.st_size:
            raise NativeReleaseIdentityError(f"{label} changed while reading")
        return data
    except NativeReleaseIdentityError:
        raise
    except OSError as exc:
        raise NativeReleaseIdentityError(f"{label} could not be read") from exc
    finally:
        os.close(descriptor)


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


def evidence_authority_input_manifest(
    repository_root: Path = PACKAGE_ROOT,
) -> dict[str, Any]:
    """Identify every checked file that decides whether evidence is accepted."""

    files: list[dict[str, Any]] = []
    for relative_path in EVIDENCE_AUTHORITY_PATHS:
        data = _read_regular(
            repository_root / relative_path,
            MAX_EVIDENCE_AUTHORITY_FILE_BYTES,
            f"evidence authority {relative_path}",
        )
        files.append(
            {
                "path": relative_path,
                "sha256": _digest(data),
                "size": len(data),
            }
        )
    body = {"algorithm": "sha256", "files": files}
    return {**body, "digest": _digest(canonical_json_bytes(body))}


def _validate_evidence_authority_input(
    value: Any,
    *,
    repository_root: Path | None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"algorithm", "digest", "files"}:
        raise NativeReleaseIdentityError(
            "evidence-authority input fields are not exact"
        )
    if value.get("algorithm") != "sha256":
        raise NativeReleaseIdentityError(
            "evidence-authority input algorithm is not SHA-256"
        )
    files = value.get("files")
    if not isinstance(files, list) or len(files) != len(EVIDENCE_AUTHORITY_PATHS):
        raise NativeReleaseIdentityError(
            "evidence-authority input file inventory is incomplete"
        )
    for item, expected_path in zip(files, EVIDENCE_AUTHORITY_PATHS, strict=True):
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "sha256", "size"}
            or item.get("path") != expected_path
            or not isinstance(item.get("size"), int)
            or isinstance(item.get("size"), bool)
            or not 0 < item["size"] <= MAX_EVIDENCE_AUTHORITY_FILE_BYTES
        ):
            raise NativeReleaseIdentityError(
                "evidence-authority input file identity is invalid"
            )
        _require_digest(
            item.get("sha256"), f"evidence authority {expected_path} digest"
        )
    body = {"algorithm": "sha256", "files": files}
    if _require_digest(
        value.get("digest"), "evidence-authority input digest"
    ) != _digest(canonical_json_bytes(body)):
        raise NativeReleaseIdentityError(
            "evidence-authority input manifest digest is inconsistent"
        )
    if (
        repository_root is not None
        and value != evidence_authority_input_manifest(repository_root)
    ):
        raise NativeReleaseIdentityError(
            "evidence-authority input differs from current files"
        )
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
    if document.get("workflowActionPins") != FROZEN_NATIVE_RELEASE_ACTION_PINS:
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


@dataclass(frozen=True)
class NativeEvidenceReceipt:
    """Validated durable evidence receipt linked to one release identity."""

    document: dict[str, Any]
    canonical_bytes: bytes
    digest: str

    @property
    def status(self) -> str:
        return self.document["status"]

    def manifest(self) -> dict[str, Any]:
        return json.loads(self.canonical_bytes)


def _require_positive_integer(value: Any, maximum: int, label: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 < value <= maximum
    ):
        raise NativeReleaseIdentityError(f"{label} is invalid")
    return value


def _validate_digest_size(
    value: Any,
    *,
    maximum: int,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"sha256", "size"}:
        raise NativeReleaseIdentityError(f"{label} fields are not exact")
    _require_digest(value.get("sha256"), f"{label} digest")
    _require_positive_integer(value.get("size"), maximum, f"{label} size")
    return value


def _validate_receipt_platforms(
    value: Any,
    *,
    identity_platforms: Any,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(PLATFORM_ORDER):
        raise NativeReleaseIdentityError("evidence receipt platform set is not exact")
    if not isinstance(identity_platforms, list) or len(identity_platforms) != len(
        PLATFORM_ORDER
    ):
        raise NativeReleaseIdentityError("release identity platform set is not exact")
    for platform_value, identity_platform, expected_platform in zip(
        value, identity_platforms, PLATFORM_ORDER, strict=True
    ):
        if not isinstance(platform_value, dict) or set(platform_value) != {
            "artifacts",
            "attestationManifest",
            "ociArchive",
            "platform",
            "provenance",
            "runtimeChildDigest",
            "runtimeChildSize",
            "runtimeConfigDigest",
            "sbom",
            "sourceImageIndexDigest",
        }:
            raise NativeReleaseIdentityError(
                "evidence receipt platform fields are not exact"
            )
        if platform_value.get("platform") != expected_platform:
            raise NativeReleaseIdentityError(
                "evidence receipt platform order is not exact"
            )
        if not isinstance(identity_platform, dict) or (
            platform_value.get("runtimeChildDigest")
            != identity_platform.get("runtimeChildDigest")
            or platform_value.get("runtimeChildSize")
            != identity_platform.get("runtimeChildSize")
            or platform_value.get("runtimeConfigDigest")
            != identity_platform.get("runtimeConfigDigest")
            or platform_value.get("artifacts") != identity_platform.get("artifacts")
        ):
            raise NativeReleaseIdentityError(
                f"{expected_platform} receipt runtime identity differs from "
                "the frozen release identity"
            )
        _require_digest(
            platform_value.get("runtimeChildDigest"),
            f"{expected_platform} runtime child digest",
        )
        _require_positive_integer(
            platform_value.get("runtimeChildSize"),
            MAX_INDEX_BYTES,
            f"{expected_platform} runtime child size",
        )
        _require_digest(
            platform_value.get("runtimeConfigDigest"),
            f"{expected_platform} runtime config digest",
        )
        _validate_artifacts(platform_value.get("artifacts"), expected_platform)
        _require_digest(
            platform_value.get("sourceImageIndexDigest"),
            f"{expected_platform} source image-index digest",
        )
        _validate_digest_size(
            platform_value.get("ociArchive"),
            maximum=512 * 1024 * 1024,
            label=f"{expected_platform} OCI archive",
        )
        _validate_digest_size(
            platform_value.get("attestationManifest"),
            maximum=8 * 1024 * 1024,
            label=f"{expected_platform} attestation manifest",
        )
        for name, predicate_type, maximum in (
            ("sbom", SBOM_PREDICATE_TYPE, 8 * 1024 * 1024),
            ("provenance", PROVENANCE_PREDICATE_TYPE, 2 * 1024 * 1024),
        ):
            evidence = platform_value.get(name)
            if not isinstance(evidence, dict) or set(evidence) != {
                "predicateType",
                "sha256",
                "size",
            }:
                raise NativeReleaseIdentityError(
                    f"{expected_platform} {name} fields are not exact"
                )
            if evidence.get("predicateType") != predicate_type:
                raise NativeReleaseIdentityError(
                    f"{expected_platform} {name} predicate is not exact"
                )
            _require_digest(
                evidence.get("sha256"), f"{expected_platform} {name} digest"
            )
            _require_positive_integer(
                evidence.get("size"), maximum, f"{expected_platform} {name} size"
            )
    return value


def _parse_build_run(value: Any) -> tuple[str, str, int, int]:
    if not isinstance(value, dict) or set(value) != {
        "actionsEvidence",
        "builderId",
        "repository",
        "runAttempt",
        "runId",
        "runUrl",
        "sourceCommit",
    }:
        raise NativeReleaseIdentityError("evidence receipt build-run fields are not exact")
    repository = value.get("repository")
    if repository != NATIVE_RELEASE_REPOSITORY:
        raise NativeReleaseIdentityError("evidence receipt repository is not exact")
    run_id = _require_positive_integer(
        value.get("runId"), 2**63 - 1, "evidence receipt run id"
    )
    run_attempt = _require_positive_integer(
        value.get("runAttempt"), 2**31 - 1, "evidence receipt run attempt"
    )
    source_commit = value.get("sourceCommit")
    if not isinstance(source_commit, str) or COMMIT_PATTERN.fullmatch(source_commit) is None:
        raise NativeReleaseIdentityError("evidence receipt source commit is not exact")
    run_url = f"https://github.com/{repository}/actions/runs/{run_id}"
    builder_id = f"{run_url}/attempts/{run_attempt}"
    if value.get("runUrl") != run_url or value.get("builderId") != builder_id:
        raise NativeReleaseIdentityError(
            "evidence receipt builder and run identities are inconsistent"
        )
    actions = value.get("actionsEvidence")
    if not isinstance(actions, dict) or set(actions) != {
        "artifacts",
        "retentionDays",
        "runArtifactsUrl",
    }:
        raise NativeReleaseIdentityError(
            "temporary Actions evidence fields are not exact"
        )
    if actions.get("retentionDays") != 14 or actions.get("runArtifactsUrl") != (
        run_url + "#artifacts"
    ):
        raise NativeReleaseIdentityError(
            "temporary Actions evidence reference is inconsistent"
        )
    expected_artifacts = [
        {
            "archivePath": "ofarm-ed25519.oci.tar",
            "name": "native-verifier-amd64",
            "platform": "linux/amd64",
        },
        {
            "archivePath": "ofarm-ed25519.oci.tar",
            "name": "native-verifier-arm64",
            "platform": "linux/arm64",
        },
        {
            "archivePath": "native_evidence_receipt.candidate.json",
            "name": "native-verifier-index",
            "platform": None,
        },
    ]
    if actions.get("artifacts") != expected_artifacts:
        raise NativeReleaseIdentityError(
            "temporary Actions artifact references are not exact"
        )
    return source_commit, builder_id, run_id, run_attempt


def _require_bounded_ascii(value: Any, maximum: int, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or not value.isascii()
        or any(ord(character) < 0x20 or ord(character) > 0x7E for character in value)
    ):
        raise NativeReleaseIdentityError(f"{label} is invalid")
    return value


def _require_base64_bytes(value: Any, maximum: int, label: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) > maximum * 2:
        raise NativeReleaseIdentityError(f"{label} is invalid")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise NativeReleaseIdentityError(f"{label} is invalid") from exc
    if not decoded or len(decoded) > maximum:
        raise NativeReleaseIdentityError(f"{label} is invalid")
    return decoded


def _release_attestation_statement(
    value: Any,
    *,
    tag: str,
    source_commit: str,
    release_id: int,
    platforms: list[dict[str, Any]],
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "_type",
        "predicate",
        "predicateType",
        "subject",
    }:
        raise NativeReleaseIdentityError(f"{label} statement fields are not exact")
    if (
        value.get("_type") != IN_TOTO_STATEMENT_V1
        or value.get("predicateType") != GITHUB_RELEASE_PREDICATE_TYPE
    ):
        raise NativeReleaseIdentityError(f"{label} statement type is not exact")
    purl = f"pkg:github/{NATIVE_RELEASE_REPOSITORY}@{tag}"
    subjects = [
        {"digest": {"sha1": source_commit}, "uri": purl},
        *[
            {
                "digest": {
                    "sha256": platform["ociArchive"]["sha256"].removeprefix(
                        "sha256:"
                    )
                },
                "name": (
                    "ofarm-ed25519-"
                    + platform["platform"].replace("/", "-")
                    + ".oci.tar"
                ),
            }
            for platform in platforms
        ],
    ]
    if value.get("subject") != subjects:
        raise NativeReleaseIdentityError(
            f"{label} repository/tag/asset subjects are inconsistent"
        )
    predicate = value.get("predicate")
    if not isinstance(predicate, dict) or set(predicate) != {
        "databaseId",
        "ownerId",
        "packageId",
        "purl",
        "repository",
        "repositoryId",
        "tag",
    }:
        raise NativeReleaseIdentityError(f"{label} predicate fields are not exact")
    owner_id = predicate.get("ownerId")
    if owner_id != NATIVE_RELEASE_OWNER_ID:
        raise NativeReleaseIdentityError(f"{label} owner identity is not exact")
    if predicate != {
        "databaseId": str(release_id),
        "ownerId": owner_id,
        "packageId": str(NATIVE_RELEASE_REPOSITORY_ID),
        "purl": purl,
        "repository": NATIVE_RELEASE_REPOSITORY,
        "repositoryId": str(NATIVE_RELEASE_REPOSITORY_ID),
        "tag": tag,
    }:
        raise NativeReleaseIdentityError(
            f"{label} repository/tag predicate is inconsistent"
        )
    return value


def validate_github_release_command_document(
    document: Any,
    *,
    tag: str,
    source_commit: str,
    release_id: int,
    platforms: list[dict[str, Any]],
    label: str,
) -> dict[str, Any]:
    """Validate the exact successful JSON contract emitted by the pinned CLI."""

    if not isinstance(document, dict) or set(document) != {
        "attestation",
        "verificationResult",
    }:
        raise NativeReleaseIdentityError(f"{label} result fields are not exact")
    attestation = document.get("attestation")
    if not isinstance(attestation, dict) or set(attestation) != {
        "bundle",
        "bundle_url",
        "initiator",
    }:
        raise NativeReleaseIdentityError(f"{label} attestation fields are not exact")
    if attestation.get("bundle_url") != "" or attestation.get("initiator") != "":
        raise NativeReleaseIdentityError(
            f"{label} pinned-CLI transport metadata is not exact"
        )
    bundle = attestation.get("bundle")
    if not isinstance(bundle, dict) or set(bundle) != {
        "dsseEnvelope",
        "mediaType",
        "verificationMaterial",
    }:
        raise NativeReleaseIdentityError(f"{label} bundle fields are not exact")
    if bundle.get("mediaType") != SIGSTORE_BUNDLE_MEDIA_TYPE:
        raise NativeReleaseIdentityError(f"{label} bundle media type is not exact")
    verification_material = bundle.get("verificationMaterial")
    if not isinstance(verification_material, dict) or set(
        verification_material
    ) != {"certificate", "timestampVerificationData"}:
        raise NativeReleaseIdentityError(
            f"{label} verification-material fields are not exact"
        )
    certificate = verification_material.get("certificate")
    if not isinstance(certificate, dict) or set(certificate) != {"rawBytes"}:
        raise NativeReleaseIdentityError(
            f"{label} verification certificate fields are not exact"
        )
    _require_base64_bytes(
        certificate.get("rawBytes"),
        MAX_PROVIDER_VERIFICATION_BYTES,
        f"{label} verification certificate",
    )
    timestamp_data = verification_material.get("timestampVerificationData")
    if not isinstance(timestamp_data, dict) or set(timestamp_data) != {
        "rfc3161Timestamps"
    }:
        raise NativeReleaseIdentityError(
            f"{label} timestamp-verification fields are not exact"
        )
    timestamps = timestamp_data.get("rfc3161Timestamps")
    if not isinstance(timestamps, list) or len(timestamps) != 1:
        raise NativeReleaseIdentityError(
            f"{label} signed-timestamp set is not exact"
        )
    timestamp = timestamps[0]
    if not isinstance(timestamp, dict) or set(timestamp) != {"signedTimestamp"}:
        raise NativeReleaseIdentityError(
            f"{label} signed-timestamp fields are not exact"
        )
    _require_base64_bytes(
        timestamp.get("signedTimestamp"),
        MAX_PROVIDER_VERIFICATION_BYTES,
        f"{label} signed timestamp",
    )
    envelope = bundle.get("dsseEnvelope")
    if not isinstance(envelope, dict) or set(envelope) != {
        "payload",
        "payloadType",
        "signatures",
    }:
        raise NativeReleaseIdentityError(f"{label} DSSE fields are not exact")
    if envelope.get("payloadType") != "application/vnd.in-toto+json":
        raise NativeReleaseIdentityError(f"{label} DSSE payload type is not exact")
    payload = _require_base64_bytes(
        envelope.get("payload"),
        MAX_PROVIDER_VERIFICATION_BYTES,
        f"{label} DSSE payload",
    )
    statement = _load_json_bytes(payload, f"{label} DSSE payload")
    statement = _release_attestation_statement(
        statement,
        tag=tag,
        source_commit=source_commit,
        release_id=release_id,
        platforms=platforms,
        label=label,
    )
    signatures = envelope.get("signatures")
    if not isinstance(signatures, list) or len(signatures) != 1:
        raise NativeReleaseIdentityError(f"{label} DSSE signature set is not exact")
    signature = signatures[0]
    if not isinstance(signature, dict) or set(signature) != {"sig"}:
        raise NativeReleaseIdentityError(f"{label} DSSE signature fields are not exact")
    _require_base64_bytes(
        signature.get("sig"),
        MAX_PROVIDER_VERIFICATION_BYTES,
        f"{label} DSSE signature",
    )

    verification_result = document.get("verificationResult")
    if not isinstance(verification_result, dict) or set(verification_result) != {
        "mediaType",
        "signature",
        "statement",
        "verifiedIdentity",
        "verifiedTimestamps",
    }:
        raise NativeReleaseIdentityError(
            f"{label} verification-result fields are not exact"
        )
    if (
        verification_result.get("mediaType")
        != SIGSTORE_VERIFICATION_RESULT_MEDIA_TYPE
        or verification_result.get("statement") != statement
    ):
        raise NativeReleaseIdentityError(
            f"{label} verified statement is inconsistent"
        )
    verified_signature = verification_result.get("signature")
    if (
        not isinstance(verified_signature, dict)
        or set(verified_signature) != {"certificate"}
    ):
        raise NativeReleaseIdentityError(
            f"{label} verified signature shape is not exact"
        )
    verified_certificate = verified_signature.get("certificate")
    if verified_certificate != {
        "certificateIssuer": GITHUB_RELEASE_CERTIFICATE_ISSUER,
        "subjectAlternativeName": GITHUB_RELEASE_CERTIFICATE_SAN,
    }:
        raise NativeReleaseIdentityError(
            f"{label} verified certificate identity is not exact"
        )
    verified_timestamps = verification_result.get("verifiedTimestamps")
    if not isinstance(verified_timestamps, list) or len(verified_timestamps) != 1:
        raise NativeReleaseIdentityError(
            f"{label} verified timestamp set is not exact"
        )
    verified_timestamp = verified_timestamps[0]
    if not isinstance(verified_timestamp, dict) or set(verified_timestamp) != {
        "timestamp",
        "type",
        "uri",
    }:
        raise NativeReleaseIdentityError(
            f"{label} verified timestamp fields are not exact"
        )
    if verified_timestamp.get("type") != "TimestampAuthority":
        raise NativeReleaseIdentityError(
            f"{label} verified timestamp type is not exact"
        )
    if verified_timestamp.get("uri") != GITHUB_RELEASE_TIMESTAMP_AUTHORITY_URI:
        raise NativeReleaseIdentityError(
            f"{label} verified timestamp URI is not exact"
        )
    timestamp_value = verified_timestamp.get("timestamp")
    if (
        not isinstance(timestamp_value, str)
        or GITHUB_RELEASE_TIMESTAMP_PATTERN.fullmatch(timestamp_value) is None
    ):
        raise NativeReleaseIdentityError(
            f"{label} verified timestamp is not canonical UTC RFC3339Nano"
        )
    try:
        datetime.strptime(timestamp_value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise NativeReleaseIdentityError(
            f"{label} verified timestamp is not canonical UTC RFC3339Nano"
        ) from exc
    verified_identity = verification_result.get("verifiedIdentity")
    if verified_identity != GITHUB_RELEASE_VERIFIED_IDENTITY:
        raise NativeReleaseIdentityError(
            f"{label} verified identity shape is not exact"
        )
    return document


def _validate_provider_command_result(
    value: Any,
    label: str,
    *,
    tag: str,
    source_commit: str,
    release_id: int,
    platforms: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "canonicalDigest",
        "document",
        "size",
    }:
        raise NativeReleaseIdentityError(
            f"{label} provider-verification fields are not exact"
        )
    document = value.get("document")
    validate_github_release_command_document(
        document,
        tag=tag,
        source_commit=source_commit,
        release_id=release_id,
        platforms=platforms,
        label=label,
    )
    canonical = canonical_json_bytes(document)
    if (
        not canonical
        or len(canonical) > MAX_PROVIDER_VERIFICATION_BYTES
        or value.get("size") != len(canonical)
        or _require_digest(
            value.get("canonicalDigest"),
            f"{label} provider-verification digest",
        )
        != _digest(canonical)
    ):
        raise NativeReleaseIdentityError(
            f"{label} provider-verification identity is inconsistent"
        )
    return value


def _validate_provider_verification(
    value: Any,
    *,
    identity_digest: str,
    source_commit: str,
    platforms: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "canonicalDigest",
        "metadata",
        "schemaVersion",
    }:
        raise NativeReleaseIdentityError(
            "GitHub provider-verification fields are not exact"
        )
    if value.get("schemaVersion") != GITHUB_PROVIDER_VERIFICATION_SCHEMA:
        raise NativeReleaseIdentityError(
            "GitHub provider-verification schema is not exact"
        )
    metadata = value.get("metadata")
    if not isinstance(metadata, dict) or set(metadata) != {
        "assetAttestations",
        "githubCli",
        "immutableReleases",
        "release",
        "releaseAttestation",
        "repository",
    }:
        raise NativeReleaseIdentityError(
            "GitHub provider-verification metadata fields are not exact"
        )
    provider_digest = _require_digest(
        value.get("canonicalDigest"),
        "GitHub provider-verification canonical digest",
    )
    if provider_digest != _digest(canonical_json_bytes(metadata)):
        raise NativeReleaseIdentityError(
            "GitHub provider-verification canonical digest is inconsistent"
        )
    frozen_provider_digest = FROZEN_PROVIDER_VERIFICATION_DIGESTS.get(
        identity_digest
    )
    if (
        frozen_provider_digest is not None
        and provider_digest != frozen_provider_digest
    ):
        raise NativeReleaseIdentityError(
            "retained provider-verification digest differs from frozen authority"
        )
    if metadata.get("repository") != {
        "apiUrl": NATIVE_RELEASE_REPOSITORY_API_URL,
        "id": NATIVE_RELEASE_REPOSITORY_ID,
        "name": NATIVE_RELEASE_REPOSITORY,
        "nodeId": NATIVE_RELEASE_REPOSITORY_NODE_ID,
        "url": NATIVE_RELEASE_REPOSITORY_URL,
    }:
        raise NativeReleaseIdentityError(
            "GitHub provider-verification repository is not exact"
        )
    if metadata.get("githubCli") != {
        "version": NATIVE_RELEASE_GITHUB_CLI_VERSION,
        "versionOutputSha256": _digest(NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT),
    }:
        raise NativeReleaseIdentityError(
            "GitHub provider-verification CLI identity is not exact"
        )
    immutable_releases = metadata.get("immutableReleases")
    if not isinstance(immutable_releases, dict) or set(immutable_releases) != {
        "enabled",
        "enforcedByOwner",
    }:
        raise NativeReleaseIdentityError(
            "GitHub immutable-release setting fields are not exact"
        )
    if immutable_releases.get("enabled") is not True or type(
        immutable_releases.get("enforcedByOwner")
    ) is not bool:
        raise NativeReleaseIdentityError(
            "GitHub immutable releases were not enabled"
        )

    release = metadata.get("release")
    if not isinstance(release, dict) or set(release) != {
        "apiUrl",
        "assets",
        "draft",
        "htmlUrl",
        "id",
        "immutable",
        "nodeId",
        "peeledTagCommit",
        "prerelease",
        "tagName",
        "targetCommitish",
    }:
        raise NativeReleaseIdentityError(
            "GitHub verified-release fields are not exact"
        )
    release_id = _require_positive_integer(
        release.get("id"), 2**63 - 1, "GitHub release id"
    )
    _require_bounded_ascii(release.get("nodeId"), 256, "GitHub release node id")
    tag = _release_tag(identity_digest)
    release_url = f"{NATIVE_RELEASE_REPOSITORY_URL}/releases/tag/{tag}"
    if release != {
        **release,
        "apiUrl": f"{NATIVE_RELEASE_REPOSITORY_API_URL}/releases/{release_id}",
        "draft": False,
        "htmlUrl": release_url,
        "immutable": True,
        "peeledTagCommit": source_commit,
        "prerelease": True,
        "tagName": tag,
        "targetCommitish": source_commit,
    }:
        raise NativeReleaseIdentityError(
            "GitHub verified-release identity is inconsistent"
        )
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) != len(PLATFORM_ORDER):
        raise NativeReleaseIdentityError(
            "GitHub verified-release asset set is not exact"
        )
    for asset, platform_value in zip(assets, platforms, strict=True):
        if not isinstance(asset, dict) or set(asset) != {
            "apiUrl",
            "id",
            "name",
            "nodeId",
            "platform",
            "sha256",
            "size",
            "state",
            "url",
        }:
            raise NativeReleaseIdentityError(
                "GitHub verified-release asset fields are not exact"
            )
        platform = platform_value["platform"]
        asset_id = _require_positive_integer(
            asset.get("id"), 2**63 - 1, f"{platform} GitHub asset id"
        )
        _require_bounded_ascii(
            asset.get("nodeId"), 256, f"{platform} GitHub asset node id"
        )
        asset_name = "ofarm-ed25519-" + platform.replace("/", "-") + ".oci.tar"
        if asset != {
            **asset,
            "apiUrl": (
                f"{NATIVE_RELEASE_REPOSITORY_API_URL}/releases/assets/{asset_id}"
            ),
            "name": asset_name,
            "platform": platform,
            "sha256": platform_value["ociArchive"]["sha256"],
            "size": platform_value["ociArchive"]["size"],
            "state": "uploaded",
            "url": (
                f"{NATIVE_RELEASE_REPOSITORY_URL}/releases/download/"
                f"{tag}/{asset_name}"
            ),
        }:
            raise NativeReleaseIdentityError(
                "GitHub verified-release asset identity is inconsistent"
            )
    if len({asset["id"] for asset in assets}) != len(assets) or len(
        {asset["nodeId"] for asset in assets}
    ) != len(assets):
        raise NativeReleaseIdentityError(
            "GitHub verified-release asset identities are not unique"
        )

    release_attestation = _validate_provider_command_result(
        metadata.get("releaseAttestation"),
        "GitHub release attestation",
        tag=tag,
        source_commit=source_commit,
        release_id=release_id,
        platforms=platforms,
    )
    asset_attestations = metadata.get("assetAttestations")
    if not isinstance(asset_attestations, list) or len(asset_attestations) != len(
        PLATFORM_ORDER
    ):
        raise NativeReleaseIdentityError(
            "GitHub asset-attestation set is not exact"
        )
    for attestation, expected_platform in zip(
        asset_attestations, PLATFORM_ORDER, strict=True
    ):
        if not isinstance(attestation, dict) or set(attestation) != {
            "platform",
            "verification",
        }:
            raise NativeReleaseIdentityError(
                "GitHub asset-attestation fields are not exact"
            )
        if attestation.get("platform") != expected_platform:
            raise NativeReleaseIdentityError(
                "GitHub asset-attestation order is not exact"
            )
        verified_asset = _validate_provider_command_result(
            attestation.get("verification"),
            f"{expected_platform} GitHub asset attestation",
            tag=tag,
            source_commit=source_commit,
            release_id=release_id,
            platforms=platforms,
        )
        if verified_asset["document"] != release_attestation["document"]:
            raise NativeReleaseIdentityError(
                f"{expected_platform} GitHub asset attestation differs from "
                "the verified release attestation"
            )
    return value


def _release_tag(identity_digest: str) -> str:
    return "native-verifier-" + identity_digest.removeprefix("sha256:")


def _validate_preservation(
    value: Any,
    *,
    identity_digest: str,
    source_commit: str,
    platforms: list[dict[str, Any]],
    expected_status: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "assets",
        "checkedReceiptPath",
        "provider",
        "providerVerification",
        "releaseKind",
        "releaseTag",
        "releaseUrl",
        "status",
    }:
        raise NativeReleaseIdentityError(
            "evidence receipt preservation fields are not exact"
        )
    tag = _release_tag(identity_digest)
    release_url = (
        f"https://github.com/{NATIVE_RELEASE_REPOSITORY}/releases/tag/{tag}"
    )
    if value != {
        **value,
        "checkedReceiptPath": CHECKED_EVIDENCE_RECEIPT_PATH,
        "provider": "github-release",
        "providerVerification": value.get("providerVerification"),
        "releaseKind": "prerelease",
        "releaseTag": tag,
        "releaseUrl": release_url,
        "status": expected_status,
    }:
        raise NativeReleaseIdentityError(
            "evidence receipt preservation reference is inconsistent"
        )
    assets = value.get("assets")
    if not isinstance(assets, list) or len(assets) != len(PLATFORM_ORDER):
        raise NativeReleaseIdentityError(
            "evidence receipt preservation asset set is not exact"
        )
    expected_assets: list[dict[str, Any]] = []
    for platform_value in platforms:
        platform = platform_value["platform"]
        asset_name = "ofarm-ed25519-" + platform.replace("/", "-") + ".oci.tar"
        expected_assets.append(
            {
                "name": asset_name,
                "platform": platform,
                "sha256": platform_value["ociArchive"]["sha256"],
                "size": platform_value["ociArchive"]["size"],
                "url": (
                    f"https://github.com/{NATIVE_RELEASE_REPOSITORY}/releases/"
                    f"download/{tag}/{asset_name}"
                ),
            }
        )
    if assets != expected_assets:
        raise NativeReleaseIdentityError(
            "evidence receipt preservation assets are inconsistent"
        )
    provider_verification = value.get("providerVerification")
    if expected_status == "pending":
        if provider_verification is not None:
            raise NativeReleaseIdentityError(
                "candidate evidence receipt contains provider verification"
            )
    else:
        _validate_provider_verification(
            provider_verification,
            identity_digest=identity_digest,
            source_commit=source_commit,
            platforms=platforms,
        )
    return value


def validate_native_evidence_receipt(
    document: Any,
    *,
    canonical_bytes: bytes,
    release_identity: NativeReleaseIdentity,
    repository_root: Path | None,
    allow_candidate: bool = False,
) -> NativeEvidenceReceipt:
    if not isinstance(document, dict):
        raise NativeReleaseIdentityError("native evidence receipt fields are not exact")
    status_value = document.get("status")
    expected_fields = {
        "buildPins",
        "buildRun",
        "evidenceAuthorityInput",
        "platforms",
        "preservation",
        "releaseIdentityDigest",
        "schemaVersion",
        "status",
    }
    expected_schema = EVIDENCE_RECEIPT_SCHEMA_V1
    if status_value == "frozen":
        expected_fields.add("candidateReceiptDigest")
        expected_fields.add("verificationAuthorityInput")
        expected_schema = EVIDENCE_RECEIPT_SCHEMA_V2
    if set(document) != expected_fields:
        raise NativeReleaseIdentityError("native evidence receipt fields are not exact")
    if canonical_json_bytes(document) != canonical_bytes:
        raise NativeReleaseIdentityError("native evidence receipt JSON is not canonical")
    if document.get("schemaVersion") != expected_schema:
        raise NativeReleaseIdentityError("native evidence receipt schema is not exact")
    if document.get("buildPins") != CURRENT_NATIVE_BUILD_PINS:
        raise NativeReleaseIdentityError("native evidence receipt build pins differ")
    if _require_digest(
        document.get("releaseIdentityDigest"), "release identity link"
    ) != release_identity.digest:
        raise NativeReleaseIdentityError(
            "native evidence receipt is not linked to the release identity"
        )
    _validate_evidence_authority_input(
        document.get("evidenceAuthorityInput"),
        repository_root=None if status_value == "frozen" else repository_root,
    )
    if status_value == "frozen":
        _validate_evidence_authority_input(
            document.get("verificationAuthorityInput"),
            repository_root=repository_root,
        )
    if status_value == "provisional":
        if release_identity.status != "provisional" or (
            document.get("buildRun") is not None
            or document.get("platforms") != []
            or document.get("preservation") is not None
        ):
            raise NativeReleaseIdentityError(
                "provisional evidence receipt contains frozen result claims"
            )
    elif status_value in {"candidate", "frozen"}:
        if status_value == "candidate" and not allow_candidate:
            raise NativeReleaseIdentityError(
                "a candidate evidence receipt cannot be checked as frozen authority"
            )
        if release_identity.status != "frozen":
            raise NativeReleaseIdentityError(
                "native evidence receipt claims results for a provisional identity"
            )
        source_commit, _builder_id, run_id, run_attempt = _parse_build_run(
            document.get("buildRun")
        )
        platforms = _validate_receipt_platforms(
            document.get("platforms"),
            identity_platforms=release_identity.document.get("platforms"),
        )
        _validate_preservation(
            document.get("preservation"),
            identity_digest=release_identity.digest,
            source_commit=source_commit,
            platforms=platforms,
            expected_status="pending" if status_value == "candidate" else "verified",
        )
        if status_value == "frozen":
            candidate_digest = _require_digest(
                document.get("candidateReceiptDigest"),
                "candidate evidence receipt digest",
            )
            candidate_document = _load_json_bytes(
                canonical_json_bytes(document),
                "frozen evidence receipt reconstruction",
            )
            candidate_document.pop("candidateReceiptDigest")
            candidate_document.pop("verificationAuthorityInput")
            candidate_document["schemaVersion"] = EVIDENCE_RECEIPT_SCHEMA_V1
            candidate_document["status"] = "candidate"
            candidate_document["preservation"]["status"] = "pending"
            candidate_document["preservation"]["providerVerification"] = None
            if _digest(canonical_json_bytes(candidate_document)) != candidate_digest:
                raise NativeReleaseIdentityError(
                    "frozen evidence receipt does not bind its candidate"
                )
            historical_markers = (
                release_identity.digest == HISTORICAL_V1_RELEASE_IDENTITY_DIGEST,
                source_commit == HISTORICAL_V1_SOURCE_COMMIT,
                run_id == HISTORICAL_V1_RUN_ID,
            )
            if any(historical_markers):
                if (
                    not all(historical_markers)
                    or candidate_digest != HISTORICAL_V1_CANDIDATE_RECEIPT_DIGEST
                    or run_attempt != HISTORICAL_V1_RUN_ATTEMPT
                ):
                    raise NativeReleaseIdentityError(
                        "historical candidate authority is not the exact v1 migration"
                    )
            elif (
                document["evidenceAuthorityInput"]
                != document["verificationAuthorityInput"]
            ):
                raise NativeReleaseIdentityError(
                    "build and verification authority snapshots differ"
                )
    else:
        raise NativeReleaseIdentityError("native evidence receipt status is not exact")
    return NativeEvidenceReceipt(document, canonical_bytes, _digest(canonical_bytes))


def load_native_evidence_receipt(
    path: Path = EVIDENCE_RECEIPT_PATH,
    *,
    release_identity: NativeReleaseIdentity,
    verify_current_authority: bool = False,
    repository_root: Path | None = None,
    allow_candidate: bool = False,
) -> NativeEvidenceReceipt:
    data = _read_regular(path, MAX_EVIDENCE_RECEIPT_BYTES, "native evidence receipt")
    document = _load_json_bytes(data, "native evidence receipt")
    return validate_native_evidence_receipt(
        document,
        canonical_bytes=data,
        release_identity=release_identity,
        repository_root=(
            repository_root or PACKAGE_ROOT if verify_current_authority else None
        ),
        allow_candidate=allow_candidate,
    )


def provisional_identity_document(
    source_directory: Path = SOURCE_DIRECTORY,
) -> dict[str, Any]:
    return {
        "schemaVersion": "ofarm.native-verifier-release-identity.v1",
        "status": "provisional",
        "sourceInput": source_input_manifest(source_directory),
        "buildPins": CURRENT_NATIVE_BUILD_PINS,
        "workflowActionPins": FROZEN_NATIVE_RELEASE_ACTION_PINS,
        "platforms": [],
        "index": None,
    }


def provisional_evidence_receipt_document(
    *,
    release_identity: NativeReleaseIdentity,
    repository_root: Path = PACKAGE_ROOT,
) -> dict[str, Any]:
    if release_identity.status != "provisional":
        raise NativeReleaseIdentityError(
            "a provisional receipt requires a provisional release identity"
        )
    document = {
        "schemaVersion": EVIDENCE_RECEIPT_SCHEMA_V1,
        "status": "provisional",
        "releaseIdentityDigest": release_identity.digest,
        "buildPins": CURRENT_NATIVE_BUILD_PINS,
        "evidenceAuthorityInput": evidence_authority_input_manifest(repository_root),
        "buildRun": None,
        "platforms": [],
        "preservation": None,
    }
    validate_native_evidence_receipt(
        document,
        canonical_bytes=canonical_json_bytes(document),
        release_identity=release_identity,
        repository_root=repository_root,
    )
    return document


def _validate_fan_in_evidence(
    index_evidence: Any,
    *,
    index_bytes: bytes,
) -> list[dict[str, Any]]:
    if not isinstance(index_evidence, dict) or set(index_evidence) != {
        "build_pins",
        "builder_id",
        "index",
        "platforms",
        "release_workflow_action_pins",
        "reproducer_workflow_action_pins",
        "schema",
        "source_commit",
    }:
        raise NativeReleaseIdentityError("native index evidence fields are not exact")
    if (
        index_evidence.get("schema")
        != "ofarm.native-multi-platform-index-evidence.v3"
        or index_evidence.get("release_workflow_action_pins")
        != FROZEN_NATIVE_RELEASE_ACTION_PINS
        or index_evidence.get("reproducer_workflow_action_pins")
        != CURRENT_NATIVE_REPRODUCER_ACTION_PINS
        or index_evidence.get("build_pins") != CURRENT_NATIVE_BUILD_PINS
    ):
        raise NativeReleaseIdentityError("native index evidence identity differs")
    source_commit = index_evidence.get("source_commit")
    if not isinstance(source_commit, str) or COMMIT_PATTERN.fullmatch(source_commit) is None:
        raise NativeReleaseIdentityError("native index source commit is not exact")
    builder_id = index_evidence.get("builder_id")
    if not isinstance(builder_id, str) or BUILDER_ID_PATTERN.fullmatch(builder_id) is None:
        raise NativeReleaseIdentityError("native index builder identity is not exact")
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
    for item, expected_platform in zip(
        evidence_platforms, PLATFORM_ORDER, strict=True
    ):
        if not isinstance(item, dict) or set(item) != {
            "artifacts",
            "attestation_manifest",
            "image_index_digest",
            "oci_archive",
            "platform",
            "provenance",
            "runtime_child_digest",
            "runtime_child_size",
            "runtime_config_digest",
            "sbom",
        }:
            raise NativeReleaseIdentityError("native fan-in platform fields are not exact")
        if item.get("platform") != expected_platform:
            raise NativeReleaseIdentityError("native fan-in platform order differs")
        _require_digest(
            item.get("runtime_child_digest"),
            f"{expected_platform} runtime child digest",
        )
        _require_digest(
            item.get("runtime_config_digest"),
            f"{expected_platform} runtime config digest",
        )
        _require_positive_integer(
            item.get("runtime_child_size"),
            MAX_INDEX_BYTES,
            f"{expected_platform} runtime child size",
        )
        _validate_artifacts(item.get("artifacts"), expected_platform)
        _require_digest(
            item.get("image_index_digest"),
            f"{expected_platform} source image-index digest",
        )
        _validate_digest_size(
            item.get("oci_archive"),
            maximum=512 * 1024 * 1024,
            label=f"{expected_platform} OCI archive",
        )
        _validate_digest_size(
            item.get("attestation_manifest"),
            maximum=8 * 1024 * 1024,
            label=f"{expected_platform} attestation manifest",
        )
        for name, predicate_type, maximum in (
            ("sbom", SBOM_PREDICATE_TYPE, 8 * 1024 * 1024),
            ("provenance", PROVENANCE_PREDICATE_TYPE, 2 * 1024 * 1024),
        ):
            evidence = item.get(name)
            if not isinstance(evidence, dict) or set(evidence) != {
                "predicate_type",
                "sha256",
                "size",
            }:
                raise NativeReleaseIdentityError(
                    f"{expected_platform} {name} fields are not exact"
                )
            if evidence.get("predicate_type") != predicate_type:
                raise NativeReleaseIdentityError(
                    f"{expected_platform} {name} predicate is not exact"
                )
            _require_digest(
                evidence.get("sha256"), f"{expected_platform} {name} digest"
            )
            _require_positive_integer(
                evidence.get("size"), maximum, f"{expected_platform} {name} size"
            )
    return evidence_platforms


def frozen_identity_document(
    *,
    index_evidence: dict[str, Any],
    index_bytes: bytes,
    source_directory: Path = SOURCE_DIRECTORY,
) -> dict[str, Any]:
    """Build and fully validate the stable identity from hosted fan-in evidence."""

    evidence_platforms = _validate_fan_in_evidence(
        index_evidence, index_bytes=index_bytes
    )
    platforms: list[dict[str, Any]] = []
    for item, expected_platform in zip(
        evidence_platforms, PLATFORM_ORDER, strict=True
    ):
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
        "workflowActionPins": FROZEN_NATIVE_RELEASE_ACTION_PINS,
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


def candidate_evidence_receipt_document(
    *,
    release_identity: NativeReleaseIdentity,
    index_evidence: dict[str, Any],
    index_bytes: bytes,
    repository_root: Path = PACKAGE_ROOT,
) -> dict[str, Any]:
    """Create a non-authoritative receipt pending durable Release preservation."""

    if release_identity.status != "frozen":
        raise NativeReleaseIdentityError(
            "a candidate receipt requires a frozen candidate release identity"
        )
    evidence_platforms = _validate_fan_in_evidence(
        index_evidence, index_bytes=index_bytes
    )
    builder_id = index_evidence["builder_id"]
    builder_match = BUILDER_ID_PATTERN.fullmatch(builder_id)
    if builder_match is None:  # Kept explicit for type narrowing after validation.
        raise NativeReleaseIdentityError("native index builder identity is not exact")
    run_id = int(builder_match.group(1))
    run_attempt = int(builder_match.group(2))
    run_url = (
        f"https://github.com/{NATIVE_RELEASE_REPOSITORY}/actions/runs/{run_id}"
    )
    platforms = [
        {
            "platform": item["platform"],
            "runtimeChildDigest": item["runtime_child_digest"],
            "runtimeChildSize": item["runtime_child_size"],
            "runtimeConfigDigest": item["runtime_config_digest"],
            "artifacts": item["artifacts"],
            "ociArchive": item["oci_archive"],
            "sourceImageIndexDigest": item["image_index_digest"],
            "attestationManifest": item["attestation_manifest"],
            "sbom": {
                "predicateType": item["sbom"]["predicate_type"],
                "sha256": item["sbom"]["sha256"],
                "size": item["sbom"]["size"],
            },
            "provenance": {
                "predicateType": item["provenance"]["predicate_type"],
                "sha256": item["provenance"]["sha256"],
                "size": item["provenance"]["size"],
            },
        }
        for item in evidence_platforms
    ]
    build_run = {
        "repository": NATIVE_RELEASE_REPOSITORY,
        "sourceCommit": index_evidence["source_commit"],
        "runId": run_id,
        "runAttempt": run_attempt,
        "runUrl": run_url,
        "builderId": builder_id,
        "actionsEvidence": {
            "retentionDays": 14,
            "runArtifactsUrl": run_url + "#artifacts",
            "artifacts": [
                {
                    "archivePath": "ofarm-ed25519.oci.tar",
                    "name": "native-verifier-amd64",
                    "platform": "linux/amd64",
                },
                {
                    "archivePath": "ofarm-ed25519.oci.tar",
                    "name": "native-verifier-arm64",
                    "platform": "linux/arm64",
                },
                {
                    "archivePath": "native_evidence_receipt.candidate.json",
                    "name": "native-verifier-index",
                    "platform": None,
                },
            ],
        },
    }
    tag = _release_tag(release_identity.digest)
    preservation = {
        "provider": "github-release",
        "providerVerification": None,
        "releaseKind": "prerelease",
        "status": "pending",
        "checkedReceiptPath": CHECKED_EVIDENCE_RECEIPT_PATH,
        "releaseTag": tag,
        "releaseUrl": (
            f"https://github.com/{NATIVE_RELEASE_REPOSITORY}/releases/tag/{tag}"
        ),
        "assets": [
            {
                "platform": item["platform"],
                "name": (
                    "ofarm-ed25519-"
                    + item["platform"].replace("/", "-")
                    + ".oci.tar"
                ),
                "sha256": item["ociArchive"]["sha256"],
                "size": item["ociArchive"]["size"],
                "url": (
                    f"https://github.com/{NATIVE_RELEASE_REPOSITORY}/releases/"
                    f"download/{tag}/ofarm-ed25519-"
                    f"{item['platform'].replace('/', '-')}.oci.tar"
                ),
            }
            for item in platforms
        ],
    }
    document = {
        "schemaVersion": EVIDENCE_RECEIPT_SCHEMA_V1,
        "status": "candidate",
        "releaseIdentityDigest": release_identity.digest,
        "buildPins": CURRENT_NATIVE_BUILD_PINS,
        "evidenceAuthorityInput": evidence_authority_input_manifest(repository_root),
        "buildRun": build_run,
        "platforms": platforms,
        "preservation": preservation,
    }
    validate_native_evidence_receipt(
        document,
        canonical_bytes=canonical_json_bytes(document),
        release_identity=release_identity,
        repository_root=repository_root,
        allow_candidate=True,
    )
    return document


def frozen_evidence_receipt_document(
    *,
    candidate_receipt: NativeEvidenceReceipt,
    release_identity: NativeReleaseIdentity,
    provider_verification: dict[str, Any],
    repository_root: Path = PACKAGE_ROOT,
) -> dict[str, Any]:
    """Promote a validated candidate after both Release downloads are verified."""

    if candidate_receipt.status != "candidate":
        raise NativeReleaseIdentityError(
            "only a candidate evidence receipt can be frozen"
        )
    document = candidate_receipt.manifest()
    document["schemaVersion"] = EVIDENCE_RECEIPT_SCHEMA_V2
    document["status"] = "frozen"
    document["candidateReceiptDigest"] = candidate_receipt.digest
    document["verificationAuthorityInput"] = evidence_authority_input_manifest(
        repository_root
    )
    document["preservation"]["status"] = "verified"
    document["preservation"]["providerVerification"] = provider_verification
    validate_native_evidence_receipt(
        document,
        canonical_bytes=canonical_json_bytes(document),
        release_identity=release_identity,
        repository_root=repository_root,
    )
    return document
