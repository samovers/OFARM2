"""Bounded CI evidence checks for the confined ``ofarm_ed25519`` image.

This module does not build or deploy an image.  It authenticates the narrow
reproducibility and OCI evidence emitted by the pinned GitHub Actions builder.
Every input is size-bounded before it is parsed or copied.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import errno
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from deployment.postgresql.native_release_identity import (
        CURRENT_NATIVE_BUILD_PINS,
        CURRENT_NATIVE_REPRODUCER_ACTION_PINS,
        FROZEN_NATIVE_RELEASE_ACTION_PINS,
        GITHUB_PROVIDER_VERIFICATION_SCHEMA,
        HISTORICAL_V1_CANDIDATE_RECEIPT_DIGEST,
        NATIVE_RELEASE_GITHUB_API_VERSION,
        NATIVE_RELEASE_GITHUB_CLI_VERSION,
        NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT,
        NATIVE_RELEASE_REPOSITORY,
        NATIVE_RELEASE_REPOSITORY_API_URL,
        NATIVE_RELEASE_REPOSITORY_ID,
        NATIVE_RELEASE_REPOSITORY_NODE_ID,
        NATIVE_RELEASE_REPOSITORY_URL,
        NativeReleaseIdentityError,
        candidate_evidence_receipt_document,
        canonical_json_bytes as release_canonical_json_bytes,
        evidence_authority_input_manifest,
        frozen_evidence_receipt_document,
        frozen_identity_document,
        load_native_evidence_receipt,
        load_native_release_identity,
        validate_github_release_command_document,
        validate_native_release_identity,
    )
except ModuleNotFoundError:  # Direct execution from this source directory.
    from native_release_identity import (  # type: ignore[no-redef]
        CURRENT_NATIVE_BUILD_PINS,
        CURRENT_NATIVE_REPRODUCER_ACTION_PINS,
        FROZEN_NATIVE_RELEASE_ACTION_PINS,
        GITHUB_PROVIDER_VERIFICATION_SCHEMA,
        HISTORICAL_V1_CANDIDATE_RECEIPT_DIGEST,
        NATIVE_RELEASE_GITHUB_API_VERSION,
        NATIVE_RELEASE_GITHUB_CLI_VERSION,
        NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT,
        NATIVE_RELEASE_REPOSITORY,
        NATIVE_RELEASE_REPOSITORY_API_URL,
        NATIVE_RELEASE_REPOSITORY_ID,
        NATIVE_RELEASE_REPOSITORY_NODE_ID,
        NATIVE_RELEASE_REPOSITORY_URL,
        NativeReleaseIdentityError,
        candidate_evidence_receipt_document,
        canonical_json_bytes as release_canonical_json_bytes,
        evidence_authority_input_manifest,
        frozen_evidence_receipt_document,
        frozen_identity_document,
        load_native_evidence_receipt,
        load_native_release_identity,
        validate_github_release_command_document,
        validate_native_release_identity,
    )


MAX_REPRODUCIBILITY_REPORT_BYTES = 64 * 1024
MAX_OCI_EVIDENCE_REPORT_BYTES = 64 * 1024
MAX_CANONICAL_INDEX_BYTES = 64 * 1024
MAX_OCI_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_OCI_MEMBER_COUNT = 2_048
MAX_OCI_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_DOCKER_TRANSPORT_MANIFEST_BYTES = 64 * 1024
MAX_SBOM_BYTES = 8 * 1024 * 1024
MAX_PROVENANCE_BYTES = 2 * 1024 * 1024
MAX_CONTAINERFILE_BYTES = 128 * 1024
MAX_GITHUB_JSON_BYTES = 64 * 1024
MAX_GITHUB_COMMAND_OUTPUT_BYTES = 128 * 1024
MAX_GITHUB_ARGUMENT_BYTES = 8 * 1024
MAX_GITHUB_ARGUMENTS = 32
MAX_GITHUB_COMMAND_BYTES = 32 * 1024
GITHUB_API_TIMEOUT_SECONDS = 60
GITHUB_DOWNLOAD_TIMEOUT_SECONDS = 15 * 60

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


def _native_file_open_flags() -> int:
    if not hasattr(os, "O_NOFOLLOW"):
        raise NativeEvidenceError("native evidence requires O_NOFOLLOW support")
    return (
        os.O_RDONLY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )


def _open_bounded_regular(
    path: Path,
    maximum: int,
    label: str,
) -> tuple[int, os.stat_result]:
    try:
        descriptor = os.open(path, _native_file_open_flags())
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise NativeEvidenceError(f"{label} must be one regular file") from exc
        raise NativeEvidenceError(f"{label} is unavailable") from exc
    try:
        try:
            file_stat = os.fstat(descriptor)
        except OSError as exc:
            raise NativeEvidenceError(f"{label} cannot be inspected") from exc
        if not stat.S_ISREG(file_stat.st_mode):
            raise NativeEvidenceError(f"{label} must be one regular file")
        if file_stat.st_size > maximum:
            raise NativeEvidenceError(f"{label} exceeds its byte limit")
        return descriptor, file_stat
    except BaseException:
        os.close(descriptor)
        raise


def _read_bounded_with_stat(
    path: Path,
    maximum: int,
    label: str,
) -> tuple[bytes, os.stat_result]:
    descriptor, file_stat = _open_bounded_regular(path, maximum, label)
    chunks: list[bytes] = []
    observed_size = 0
    try:
        try:
            while True:
                read_size = min(1024 * 1024, maximum - observed_size + 1)
                chunk = os.read(descriptor, read_size)
                if not chunk:
                    break
                chunks.append(chunk)
                observed_size += len(chunk)
                if observed_size > maximum:
                    raise NativeEvidenceError(f"{label} exceeds its byte limit")
        except OSError as exc:
            raise NativeEvidenceError(f"{label} cannot be read") from exc
        if observed_size != file_stat.st_size:
            raise NativeEvidenceError(f"{label} has an invalid size")
        return b"".join(chunks), file_stat
    finally:
        os.close(descriptor)


def _read_bounded(path: Path, maximum: int, label: str) -> bytes:
    return _read_bounded_with_stat(path, maximum, label)[0]


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


def _github_cli_path() -> Path:
    executable = shutil.which("gh")
    if executable is None:
        raise NativeEvidenceError("the trusted GitHub CLI is unavailable")
    try:
        resolved = Path(executable).resolve(strict=True)
        file_stat = resolved.stat()
    except OSError as exc:
        raise NativeEvidenceError("the trusted GitHub CLI is unavailable") from exc
    if not stat.S_ISREG(file_stat.st_mode) or not os.access(resolved, os.X_OK):
        raise NativeEvidenceError("the trusted GitHub CLI is not executable")
    return resolved


def _github_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "CLICOLOR": "0",
            "GH_HOST": "github.com",
            "GH_PAGER": "cat",
            "GH_PROMPT_DISABLED": "1",
            "GH_REPO": NATIVE_RELEASE_REPOSITORY,
            "NO_COLOR": "1",
            "PAGER": "cat",
        }
    )
    return environment


def _run_github_cli(
    arguments: tuple[str, ...],
    *,
    label: str,
    timeout_seconds: int = GITHUB_API_TIMEOUT_SECONDS,
    github_cli: Path | None = None,
) -> bytes:
    if not arguments or len(arguments) > MAX_GITHUB_ARGUMENTS:
        raise NativeEvidenceError("GitHub CLI arguments are not exact")
    if (
        any(
            type(argument) is not str
            or not argument
            or len(argument) > MAX_GITHUB_ARGUMENT_BYTES
            or not argument.isascii()
            or any(
                ord(character) < 0x20 or ord(character) > 0x7E
                for character in argument
            )
            for argument in arguments
        )
        or sum(len(argument) for argument in arguments) > MAX_GITHUB_COMMAND_BYTES
    ):
        raise NativeEvidenceError("GitHub CLI arguments are not exact")
    executable = _github_cli_path() if github_cli is None else github_cli
    if not isinstance(executable, Path) or not executable.is_absolute():
        raise NativeEvidenceError("GitHub CLI path is not exact")
    command = (str(executable), *arguments)
    try:
        completed = subprocess.run(
            command,
            check=False,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            env=_github_environment(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise NativeEvidenceError(f"{label} could not execute") from exc
    if (
        len(completed.stdout) > MAX_GITHUB_COMMAND_OUTPUT_BYTES
        or len(completed.stderr) > MAX_GITHUB_COMMAND_OUTPUT_BYTES
    ):
        raise NativeEvidenceError(f"{label} output exceeds its byte limit")
    if completed.returncode != 0:
        raise NativeEvidenceError(f"{label} refused")
    if completed.stderr:
        raise NativeEvidenceError(f"{label} wrote to standard error")
    return completed.stdout


def _run_github_json(
    arguments: tuple[str, ...],
    *,
    label: str,
    github_cli: Path | None = None,
) -> Any:
    data = _run_github_cli(arguments, label=label, github_cli=github_cli)
    if not data or len(data) > MAX_GITHUB_JSON_BYTES:
        raise NativeEvidenceError(f"{label} JSON has an invalid size")
    return _load_json_bytes(data, f"{label} JSON")


def _provider_command_result(
    document: Any,
    label: str,
    *,
    tag: str,
    source_commit: str,
    release_id: int,
    platforms: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        validate_github_release_command_document(
            document,
            tag=tag,
            source_commit=source_commit,
            release_id=release_id,
            platforms=platforms,
            label=label,
        )
    except NativeReleaseIdentityError as exc:
        raise NativeEvidenceError(str(exc)) from exc
    canonical = release_canonical_json_bytes(document)
    if not canonical or len(canonical) > MAX_GITHUB_JSON_BYTES:
        raise NativeEvidenceError(f"{label} canonical JSON has an invalid size")
    return {
        "canonicalDigest": _sha256(canonical),
        "document": document,
        "size": len(canonical),
    }


def _write_regular(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise NativeEvidenceError("evidence output path is not a regular file")
    path.write_bytes(data)


def _publish_regular_no_clobber(path: Path, data: bytes, label: str) -> None:
    """Atomically publish one complete file, or accept identical existing bytes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
        )
    except OSError as exc:
        raise NativeEvidenceError(f"{label} cannot be staged") from exc
    temporary_path = Path(temporary_name)
    try:
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise NativeEvidenceError(f"{label} cannot be staged") from exc
        try:
            os.link(temporary_path, path, follow_symlinks=False)
        except FileExistsError:
            try:
                existing = _read_bounded(path, len(data), f"existing {label}")
            except NativeEvidenceError as exc:
                raise NativeEvidenceError(f"existing {label} differs") from exc
            if existing != data:
                raise NativeEvidenceError(f"existing {label} differs")
        except OSError as exc:
            raise NativeEvidenceError(f"{label} cannot be published") from exc
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def _artifact_identity(
    directory: Path,
    name: str,
    maximum: int,
    expected_mode: str,
) -> dict[str, Any]:
    path = directory / name
    data, file_stat = _read_bounded_with_stat(
        path,
        maximum,
        f"native artifact {name}",
    )
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
    first_archive: Path,
    second_archive: Path,
    first_artifacts: Path,
    second_artifacts: Path,
    platform: str,
    source_commit: str,
    output: Path,
) -> dict[str, Any]:
    """Require two clean builds to have the same child and installed bytes."""

    platform = _require_platform(platform)
    source_commit = _require_source_commit(source_commit)
    architecture = platform.split("/", 1)[1]
    first_digest, first_config_digest = docker_transport_child_identity(
        first_archive,
        "first clean build Docker transport archive",
        platform=platform,
        image_name=f"ofarm-ed25519-{architecture}:first",
    )
    second_digest, second_config_digest = docker_transport_child_identity(
        second_archive,
        "second clean build Docker transport archive",
        platform=platform,
        image_name=f"ofarm-ed25519-{architecture}:second",
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
    def __init__(self, path: Path, *, docker_transport: bool = False):
        archive_bytes = _read_bounded(path, MAX_OCI_ARCHIVE_BYTES, "OCI archive")
        self.sha256 = _sha256(archive_bytes)
        self.size = len(archive_bytes)
        self._stream = io.BytesIO(archive_bytes)
        try:
            self._tar = tarfile.open(fileobj=self._stream, mode="r:*")
        except (EOFError, OSError, tarfile.TarError) as exc:
            self._stream.close()
            raise NativeEvidenceError("OCI archive is not a readable tar archive") from exc
        self._members: dict[str, tarfile.TarInfo] = {}
        self._referenced_blobs: set[str] = set()
        self._docker_transport = docker_transport
        try:
            self._index_members()
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        self._tar.close()
        self._stream.close()

    def _index_members(self) -> None:
        try:
            members = self._tar.getmembers()
        except (EOFError, OSError, tarfile.TarError) as exc:
            raise NativeEvidenceError("OCI archive member table is unreadable") from exc
        if len(members) > MAX_OCI_MEMBER_COUNT:
            raise NativeEvidenceError("OCI archive contains too many members")
        expanded_size = 0
        seen_names: set[str] = set()
        for member in members:
            name = member.name.removeprefix("./")
            pure_name = PurePosixPath(name)
            if (
                not name
                or pure_name.is_absolute()
                or ".." in pure_name.parts
                or name in seen_names
            ):
                raise NativeEvidenceError("OCI archive contains an unsafe member name")
            seen_names.add(name)
            if member.isdir():
                if name not in {"blobs", "blobs/sha256"}:
                    raise NativeEvidenceError("OCI archive contains an unexpected directory")
                continue
            if not member.isreg():
                raise NativeEvidenceError("OCI archive contains a non-regular member")
            allowed_files = {"oci-layout", "index.json"}
            if self._docker_transport:
                allowed_files.add("manifest.json")
            if name not in allowed_files and OCI_BLOB_PATTERN.fullmatch(name) is None:
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
        except (EOFError, OSError, tarfile.TarError) as exc:
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
    archive: _OciArchive,
    manifest: dict[str, Any],
    platform: str,
) -> tuple[str, tuple[str, ...]]:
    platform = _require_platform(platform)
    config = _require_object(manifest.get("config"), "runtime config descriptor")
    if config.get("mediaType") != OCI_CONFIG_MEDIA_TYPE:
        raise NativeEvidenceError("runtime config media type is not exact")
    config_digest = _require_digest(config.get("digest"), "runtime config digest")
    config_document = _require_object(
        _load_json_bytes(
            archive.descriptor_bytes(config, MAX_MANIFEST_BYTES, "runtime config"),
            "runtime config",
        ),
        "runtime config",
    )
    expected_os, expected_architecture = platform.split("/", 1)
    if (
        config_document.get("os") != expected_os
        or config_document.get("architecture") != expected_architecture
    ):
        raise NativeEvidenceError("runtime config platform is inconsistent")
    layers = manifest.get("layers")
    if not isinstance(layers, list) or not 1 <= len(layers) <= 64:
        raise NativeEvidenceError("runtime layer set is absent or unbounded")
    layer_paths: list[str] = []
    for index, layer in enumerate(layers):
        layer_object = _require_object(layer, f"runtime layer {index} descriptor")
        if layer_object.get("mediaType") != OCI_LAYER_MEDIA_TYPE:
            raise NativeEvidenceError("runtime layer media type is not exact")
        layer_digest = _require_digest(
            layer_object.get("digest"), f"runtime layer {index} digest"
        )
        archive.descriptor_bytes(
            layer_object,
            MAX_OCI_ARCHIVE_BYTES,
            f"runtime layer {index}",
        )
        layer_paths.append("blobs/sha256/" + layer_digest.removeprefix("sha256:"))
    return config_digest, tuple(layer_paths)


def _require_docker_transport_image_name(image_name: str, platform: str) -> str:
    architecture = platform.split("/", 1)[1]
    allowed_names = {
        f"ofarm-ed25519-{architecture}:first",
        f"ofarm-ed25519-{architecture}:second",
    }
    if platform == "linux/amd64":
        allowed_names.add("ofarm-postgresql-conformance:local")
    if image_name not in allowed_names:
        raise NativeEvidenceError("Docker transport image name is not allowed")
    return image_name


def _authenticate_docker_transport_manifest(
    archive: _OciArchive,
    *,
    label: str,
    image_name: str,
    config_digest: str,
    layer_paths: tuple[str, ...],
) -> None:
    document = _load_json_bytes(
        archive.read_member(
            "manifest.json",
            MAX_DOCKER_TRANSPORT_MANIFEST_BYTES,
            f"{label} Docker transport manifest",
        ),
        f"{label} Docker transport manifest",
    )
    if not isinstance(document, list) or len(document) != 1:
        raise NativeEvidenceError(
            f"{label} Docker transport manifest must contain one entry"
        )
    entry = _require_object(document[0], f"{label} Docker transport entry")
    if set(entry) != {"Config", "RepoTags", "Layers"}:
        raise NativeEvidenceError(
            f"{label} Docker transport entry fields are not exact"
        )
    expected = {
        "Config": "blobs/sha256/" + config_digest.removeprefix("sha256:"),
        "RepoTags": [image_name],
        "Layers": list(layer_paths),
    }
    if entry != expected:
        raise NativeEvidenceError(
            f"{label} Docker transport entry does not bind the authenticated image"
        )


def _direct_oci_child_identity(
    path: Path,
    label: str,
    *,
    platform: str,
    docker_image_name: str | None,
) -> tuple[str, str]:
    platform = _require_platform(platform)
    expected_os, expected_architecture = platform.split("/", 1)
    if docker_image_name is not None:
        docker_image_name = _require_docker_transport_image_name(
            docker_image_name, platform
        )
    archive = _OciArchive(path, docker_transport=docker_image_name is not None)
    try:
        layout = _require_object(
            _load_json_bytes(
                archive.read_member("oci-layout", 4 * 1024, f"{label} OCI layout"),
                f"{label} OCI layout",
            ),
            f"{label} OCI layout",
        )
        if layout != {"imageLayoutVersion": "1.0.0"}:
            raise NativeEvidenceError(
                f"{label} OCI layout version is not exactly 1.0.0"
            )
        index = _require_object(
            _load_json_bytes(
                archive.read_member(
                    "index.json",
                    MAX_MANIFEST_BYTES,
                    f"{label} OCI index",
                ),
                f"{label} OCI index",
            ),
            f"{label} OCI index",
        )
        descriptors = _manifest_descriptors(index)
        if len(descriptors) != 1:
            raise NativeEvidenceError(
                f"{label} OCI index must contain one direct runtime child"
            )
        descriptor = descriptors[0]
        if descriptor.get("mediaType") not in OCI_MANIFEST_MEDIA_TYPES:
            raise NativeEvidenceError(
                f"{label} OCI index does not directly reference one runtime child"
            )
        if "artifactType" in descriptor or "subject" in descriptor:
            raise NativeEvidenceError(f"{label} runtime descriptor is not a plain image")
        if descriptor.get("platform") != {
            "os": expected_os,
            "architecture": expected_architecture,
        }:
            raise NativeEvidenceError(f"{label} runtime descriptor platform is inconsistent")
        annotations = descriptor.get("annotations", {})
        if not isinstance(annotations, dict):
            raise NativeEvidenceError(f"{label} runtime descriptor annotations are malformed")
        if any(
            key in annotations
            for key in (
                ATTESTATION_REFERENCE_ANNOTATION,
                ATTESTATION_TYPE_ANNOTATION,
            )
        ):
            raise NativeEvidenceError(f"{label} runtime descriptor is an attestation")
        child_digest = _require_digest(
            descriptor.get("digest"), f"{label} runtime child digest"
        )
        manifest = _load_manifest(archive, descriptor, f"{label} runtime manifest")
        if (
            manifest.get("mediaType") not in OCI_MANIFEST_MEDIA_TYPES
            or "artifactType" in manifest
            or "subject" in manifest
        ):
            raise NativeEvidenceError(f"{label} runtime manifest is not a plain image")
        config_digest, layer_paths = _authenticate_runtime_manifest(
            archive, manifest, platform
        )
        if docker_image_name is not None:
            _authenticate_docker_transport_manifest(
                archive,
                label=label,
                image_name=docker_image_name,
                config_digest=config_digest,
                layer_paths=layer_paths,
            )
        archive.require_no_unreferenced_blobs()
    finally:
        archive.close()
    return child_digest, config_digest


def direct_oci_child_identity(
    path: Path,
    label: str,
    *,
    platform: str,
) -> tuple[str, str]:
    """Authenticate one direct single-platform OCI runtime child."""

    return _direct_oci_child_identity(
        path,
        label,
        platform=platform,
        docker_image_name=None,
    )


def docker_transport_child_identity(
    path: Path,
    label: str,
    *,
    platform: str,
    image_name: str,
) -> tuple[str, str]:
    """Authenticate one loadable Docker archive containing an exact OCI child."""

    return _direct_oci_child_identity(
        path,
        label,
        platform=platform,
        docker_image_name=image_name,
    )


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


def _inspect_oci_archive(
    *,
    archive_path: Path,
    platform: str,
    source_commit: str,
    containerfile_path: Path,
    builder_id: str,
    label: str,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Authenticate one bounded archive without trusting a prior CI report."""

    platform = _require_platform(platform)
    source_commit = _require_source_commit(source_commit)
    if not builder_id.startswith("https://github.com/") or len(builder_id) > 512:
        raise NativeEvidenceError("builder id must be one bounded GitHub HTTPS identity")
    containerfile_bytes = _read_bounded(
        containerfile_path,
        MAX_CONTAINERFILE_BYTES,
        f"{label} reviewed Containerfile",
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
        runtime_manifest = _load_manifest(
            archive, runtime_descriptor, "runtime manifest"
        )
        runtime_config_digest, _ = _authenticate_runtime_manifest(
            archive, runtime_manifest, platform
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

    report = {
        "platform": platform,
        "source_commit": source_commit,
        "builder_id": builder_id,
        "runtime_child_digest": runtime_digest,
        "runtime_child_size": runtime_size,
        "runtime_config_digest": runtime_config_digest,
        "image_index_digest": image_index_digest,
        "attestation_manifest_digest": attestation_digest,
        "attestation_manifest_size": attestation_size,
        "oci_archive": {"sha256": archive.sha256, "size": archive.size},
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
    return report, attestations


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

    observed, attestations = _inspect_oci_archive(
        archive_path=archive_path,
        platform=platform,
        source_commit=source_commit,
        containerfile_path=containerfile_path,
        builder_id=builder_id,
        label="hosted OCI evidence",
    )
    if observed["runtime_child_digest"] != reproducible_digest:
        raise NativeEvidenceError(
            "attested runtime child differs from the two clean builds"
        )
    if observed["runtime_config_digest"] != reproducible_config_digest:
        raise NativeEvidenceError(
            "attested runtime config differs from the two clean builds"
        )

    output_directory.mkdir(parents=True, exist_ok=True)
    sbom_path = output_directory / "sbom.spdx.in-toto.json"
    provenance_path = output_directory / "provenance.slsa-v0.2.in-toto.json"
    _write_regular(sbom_path, attestations[SBOM_PREDICATE_TYPE])
    _write_regular(provenance_path, attestations[PROVENANCE_PREDICATE_TYPE])
    report = {
        "schema": "ofarm.native-oci-evidence.v1",
        **observed,
        "artifacts": reproducible_artifacts,
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
        "schema": "ofarm.native-multi-platform-index-evidence.v3",
        "source_commit": source_commit,
        "builder_id": reports[0]["builder_id"],
        "release_workflow_action_pins": FROZEN_NATIVE_RELEASE_ACTION_PINS,
        "reproducer_workflow_action_pins": CURRENT_NATIVE_REPRODUCER_ACTION_PINS,
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
            MAX_CANONICAL_INDEX_BYTES,
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
    if checked.status == "frozen":
        if checked_receipt.status != "frozen":
            raise NativeEvidenceError(
                "frozen native identity has no frozen evidence receipt"
            )
        _write_regular(candidate_output, checked.canonical_bytes)
        _write_regular(candidate_receipt_output, checked_receipt.canonical_bytes)
        return {
            "checked_status": checked.status,
            "checked_receipt_status": checked_receipt.status,
            "candidate_digest": checked.digest,
            "candidate_index_digest": checked.index_digest,
            "candidate_receipt_digest": checked_receipt.digest,
        }
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
    descriptor, file_stat = _open_bounded_regular(path, maximum, label)
    if not 0 < file_stat.st_size <= maximum:
        os.close(descriptor)
        raise NativeEvidenceError(f"{label} has an invalid size")
    digest = hashlib.sha256()
    observed_size = 0
    try:
        try:
            while True:
                read_size = min(1024 * 1024, maximum - observed_size + 1)
                chunk = os.read(descriptor, read_size)
                if not chunk:
                    break
                digest.update(chunk)
                observed_size += len(chunk)
                if observed_size > maximum:
                    raise NativeEvidenceError(f"{label} has an invalid size")
        except OSError as exc:
            raise NativeEvidenceError(f"{label} cannot be read") from exc
        if observed_size != file_stat.st_size:
            raise NativeEvidenceError(f"{label} has an invalid size")
        return {"sha256": "sha256:" + digest.hexdigest(), "size": observed_size}
    finally:
        os.close(descriptor)


def _github_api_arguments(endpoint: str, projection: str) -> tuple[str, ...]:
    if endpoint != "repos/samovers/OFARM2" and not endpoint.startswith(
        "repos/samovers/OFARM2/"
    ):
        raise NativeEvidenceError("GitHub API endpoint is outside the fixed repository")
    return (
        "api",
        "--hostname",
        "github.com",
        "--method",
        "GET",
        "--header",
        "Accept: application/vnd.github+json",
        "--header",
        f"X-GitHub-Api-Version: {NATIVE_RELEASE_GITHUB_API_VERSION}",
        endpoint,
        "--jq",
        projection,
    )


def _positive_integer(value: Any, label: str) -> int:
    if (
        type(value) is not int
        or value <= 0
        or value > 2**63 - 1
    ):
        raise NativeEvidenceError(f"{label} is invalid")
    return value


def _bounded_ascii(value: Any, maximum: int, label: str) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > maximum
        or not value.isascii()
        or any(ord(character) < 0x20 or ord(character) > 0x7E for character in value)
    ):
        raise NativeEvidenceError(f"{label} is invalid")
    return value


def _authenticate_github_release(
    *,
    candidate: Any,
    identity: Any,
    source_directory: Path,
    download_directory: Path,
    retained_immutable_releases: dict[str, Any] | None = None,
) -> dict[str, Any]:
    github_cli = _github_cli_path()
    version_output = _run_github_cli(
        ("version",),
        label="GitHub CLI version",
        github_cli=github_cli,
    )
    if version_output != NATIVE_RELEASE_GITHUB_CLI_VERSION_OUTPUT:
        raise NativeEvidenceError("GitHub CLI version is not exact")

    repository = _run_github_json(
        _github_api_arguments(
            "repos/samovers/OFARM2",
            (
                "{apiUrl:.url,id:.id,nodeId:.node_id,"
                "name:.full_name,url:.html_url}"
            ),
        ),
        label="GitHub repository identity",
        github_cli=github_cli,
    )
    if repository != {
        "apiUrl": NATIVE_RELEASE_REPOSITORY_API_URL,
        "id": NATIVE_RELEASE_REPOSITORY_ID,
        "name": NATIVE_RELEASE_REPOSITORY,
        "nodeId": NATIVE_RELEASE_REPOSITORY_NODE_ID,
        "url": NATIVE_RELEASE_REPOSITORY_URL,
    }:
        raise NativeEvidenceError("GitHub repository identity is not exact")

    # Actions cannot read the repository-administration setting. Replay may
    # retain that frozen observation; release state and attestations are fresh.
    if retained_immutable_releases is not None:
        if (
            set(retained_immutable_releases) != {"enabled", "enforcedByOwner"}
            or retained_immutable_releases.get("enabled") is not True
            or type(retained_immutable_releases.get("enforcedByOwner")) is not bool
        ):
            raise NativeEvidenceError(
                "retained GitHub immutable-release setting is invalid"
            )
        retained_immutable_releases = dict(retained_immutable_releases)

    def observe_immutable_releases() -> Any:
        if retained_immutable_releases is not None:
            return dict(retained_immutable_releases)
        return _run_github_json(
            _github_api_arguments(
                "repos/samovers/OFARM2/immutable-releases",
                "{enabled:.enabled,enforcedByOwner:.enforced_by_owner}",
            ),
            label="GitHub immutable-release setting",
            github_cli=github_cli,
        )

    immutable_releases = observe_immutable_releases()
    if (
        not isinstance(immutable_releases, dict)
        or set(immutable_releases) != {"enabled", "enforcedByOwner"}
        or immutable_releases.get("enabled") is not True
        or type(immutable_releases.get("enforcedByOwner")) is not bool
    ):
        raise NativeEvidenceError("GitHub immutable releases are not enabled")

    identity_digest = candidate.document["releaseIdentityDigest"]
    tag = "native-verifier-" + identity_digest.removeprefix("sha256:")
    source_commit = candidate.document["buildRun"]["sourceCommit"]
    expected_release_url = f"{NATIVE_RELEASE_REPOSITORY_URL}/releases/tag/{tag}"

    def observe_release() -> Any:
        return _run_github_json(
            _github_api_arguments(
                f"repos/samovers/OFARM2/releases/tags/{tag}",
                (
                    "{apiUrl:.url,id:.id,nodeId:.node_id,tagName:.tag_name,"
                    "targetCommitish:.target_commitish,htmlUrl:.html_url,"
                    "draft:.draft,prerelease:.prerelease,immutable:.immutable,"
                    "assets:[.assets[]|{apiUrl:.url,id:.id,nodeId:.node_id,"
                    "name:.name,state:.state,size:.size,sha256:.digest,"
                    "url:.browser_download_url}]}"
                ),
            ),
            label="GitHub immutable prerelease",
            github_cli=github_cli,
        )

    release = observe_release()
    if not isinstance(release, dict) or set(release) != {
        "apiUrl",
        "assets",
        "draft",
        "htmlUrl",
        "id",
        "immutable",
        "nodeId",
        "prerelease",
        "tagName",
        "targetCommitish",
    }:
        raise NativeEvidenceError("GitHub release fields are not exact")
    release_id = _positive_integer(release.get("id"), "GitHub release id")
    release_node_id = _bounded_ascii(
        release.get("nodeId"), 256, "GitHub release node id"
    )
    if release != {
        **release,
        "apiUrl": f"{NATIVE_RELEASE_REPOSITORY_API_URL}/releases/{release_id}",
        "draft": False,
        "htmlUrl": expected_release_url,
        "immutable": True,
        "nodeId": release_node_id,
        "prerelease": True,
        "tagName": tag,
        "targetCommitish": source_commit,
    }:
        raise NativeEvidenceError("GitHub release identity is inconsistent")

    def observe_peeled_tag() -> Any:
        return _run_github_json(
            _github_api_arguments(
                f"repos/samovers/OFARM2/commits/{tag}",
                "{sha:.sha}",
            ),
            label="GitHub release tag commit",
            github_cli=github_cli,
        )

    peeled = observe_peeled_tag()
    if peeled != {"sha": source_commit}:
        raise NativeEvidenceError("GitHub release tag target is inconsistent")

    raw_assets = release.get("assets")
    if not isinstance(raw_assets, list) or len(raw_assets) != 2:
        raise NativeEvidenceError("GitHub release asset set is not exact")
    expected_platforms = candidate.document["platforms"]
    expected_assets = candidate.document["preservation"]["assets"]
    assets_by_name: dict[str, dict[str, Any]] = {}
    for raw_asset in raw_assets:
        if not isinstance(raw_asset, dict) or set(raw_asset) != {
            "apiUrl",
            "id",
            "name",
            "nodeId",
            "sha256",
            "size",
            "state",
            "url",
        }:
            raise NativeEvidenceError("GitHub release asset fields are not exact")
        name = raw_asset.get("name")
        if type(name) is not str or name in assets_by_name:
            raise NativeEvidenceError("GitHub release asset names are not unique")
        assets_by_name[name] = raw_asset

    normalized_assets: list[dict[str, Any]] = []
    asset_names: list[str] = []
    for platform_value, expected_asset in zip(
        expected_platforms, expected_assets, strict=True
    ):
        platform = platform_value["platform"]
        name = expected_asset["name"]
        raw_asset = assets_by_name.get(name)
        if raw_asset is None:
            raise NativeEvidenceError(f"{platform} GitHub release asset is absent")
        asset_id = _positive_integer(raw_asset.get("id"), f"{platform} GitHub asset id")
        asset_node_id = _bounded_ascii(
            raw_asset.get("nodeId"), 256, f"{platform} GitHub asset node id"
        )
        normalized = {
            "apiUrl": (
                f"{NATIVE_RELEASE_REPOSITORY_API_URL}/releases/assets/{asset_id}"
            ),
            "id": asset_id,
            "name": name,
            "nodeId": asset_node_id,
            "platform": platform,
            "sha256": expected_asset["sha256"],
            "size": expected_asset["size"],
            "state": "uploaded",
            "url": expected_asset["url"],
        }
        if raw_asset != {key: value for key, value in normalized.items() if key != "platform"}:
            raise NativeEvidenceError(
                f"{platform} GitHub release asset identity is inconsistent"
            )
        normalized_assets.append(normalized)
        asset_names.append(name)
    if set(assets_by_name) != set(asset_names) or len(
        {asset["id"] for asset in normalized_assets}
    ) != 2 or len({asset["nodeId"] for asset in normalized_assets}) != 2:
        raise NativeEvidenceError("GitHub release asset identities are not exact")

    release_attestation = _provider_command_result(
        _run_github_json(
            (
                "release",
                "verify",
                tag,
                "--repo",
                NATIVE_RELEASE_REPOSITORY,
                "--format",
                "json",
            ),
            label="GitHub release attestation",
            github_cli=github_cli,
        ),
        "GitHub release attestation",
        tag=tag,
        source_commit=source_commit,
        release_id=release_id,
        platforms=expected_platforms,
    )

    try:
        if (
            download_directory.is_symlink()
            or not download_directory.is_dir()
            or any(download_directory.iterdir())
        ):
            raise NativeEvidenceError(
                "GitHub release download directory is not one fresh directory"
            )
    except OSError as exc:
        raise NativeEvidenceError(
            "GitHub release download directory is unreadable"
        ) from exc
    _run_github_cli(
        (
            "release",
            "download",
            tag,
            "--repo",
            NATIVE_RELEASE_REPOSITORY,
            "--dir",
            str(download_directory),
            "--pattern",
            asset_names[0],
            "--pattern",
            asset_names[1],
        ),
        label="GitHub release asset download",
        timeout_seconds=GITHUB_DOWNLOAD_TIMEOUT_SECONDS,
        github_cli=github_cli,
    )
    try:
        downloaded_names = sorted(path.name for path in download_directory.iterdir())
    except OSError as exc:
        raise NativeEvidenceError("GitHub release download directory is unreadable") from exc
    if downloaded_names != sorted(asset_names):
        raise NativeEvidenceError("GitHub release download set is not exact")

    asset_attestations: list[dict[str, Any]] = []
    identity_platforms = identity.document["platforms"]
    builder_id = candidate.document["buildRun"]["builderId"]
    for platform_value, identity_platform, expected_asset in zip(
        expected_platforms,
        identity_platforms,
        expected_assets,
        strict=True,
    ):
        platform = platform_value["platform"]
        path = download_directory / expected_asset["name"]
        observed = _bounded_file_identity(
            path,
            MAX_OCI_ARCHIVE_BYTES,
            f"{platform} immutable GitHub Release download",
        )
        if observed != platform_value["ociArchive"] or observed != {
            "sha256": expected_asset["sha256"],
            "size": expected_asset["size"],
        }:
            raise NativeEvidenceError(
                f"{platform} immutable GitHub Release download differs"
            )
        archive_observation, _attestations = _inspect_oci_archive(
            archive_path=path,
            platform=platform,
            source_commit=source_commit,
            containerfile_path=source_directory / "Containerfile",
            builder_id=builder_id,
            label=f"{platform} immutable GitHub Release",
        )
        expected_observation = {
            "platform": platform,
            "source_commit": source_commit,
            "builder_id": builder_id,
            "runtime_child_digest": identity_platform["runtimeChildDigest"],
            "runtime_child_size": identity_platform["runtimeChildSize"],
            "runtime_config_digest": identity_platform["runtimeConfigDigest"],
            "image_index_digest": platform_value["sourceImageIndexDigest"],
            "attestation_manifest_digest": platform_value[
                "attestationManifest"
            ]["sha256"],
            "attestation_manifest_size": platform_value[
                "attestationManifest"
            ]["size"],
            "oci_archive": platform_value["ociArchive"],
            "sbom": {
                "predicate_type": platform_value["sbom"]["predicateType"],
                "sha256": platform_value["sbom"]["sha256"],
                "size": platform_value["sbom"]["size"],
            },
            "provenance": {
                "predicate_type": platform_value["provenance"][
                    "predicateType"
                ],
                "sha256": platform_value["provenance"]["sha256"],
                "size": platform_value["provenance"]["size"],
            },
        }
        if archive_observation != expected_observation or (
            platform_value["runtimeChildDigest"]
            != identity_platform["runtimeChildDigest"]
            or platform_value["runtimeChildSize"]
            != identity_platform["runtimeChildSize"]
            or platform_value["runtimeConfigDigest"]
            != identity_platform["runtimeConfigDigest"]
            or platform_value["artifacts"] != identity_platform["artifacts"]
        ):
            raise NativeEvidenceError(
                f"{platform} immutable GitHub Release OCI evidence differs "
                "from the candidate receipt or frozen identity"
            )
        verification = _provider_command_result(
            _run_github_json(
                (
                    "release",
                    "verify-asset",
                    tag,
                    str(path),
                    "--repo",
                    NATIVE_RELEASE_REPOSITORY,
                    "--format",
                    "json",
                ),
                label=f"{platform} GitHub release asset attestation",
                github_cli=github_cli,
            ),
            f"{platform} GitHub release asset attestation",
            tag=tag,
            source_commit=source_commit,
            release_id=release_id,
            platforms=expected_platforms,
        )
        if verification["document"] != release_attestation["document"]:
            raise NativeEvidenceError(
                f"{platform} GitHub asset attestation differs from the "
                "verified release attestation"
            )
        asset_attestations.append(
            {"platform": platform, "verification": verification}
        )

    final_immutable_releases = observe_immutable_releases()
    final_release = observe_release()
    final_peeled = observe_peeled_tag()
    if (
        final_immutable_releases != immutable_releases
        or final_release != release
        or final_peeled != peeled
    ):
        raise NativeEvidenceError(
            "GitHub immutable release state changed during verification"
        )

    metadata = {
        "repository": repository,
        "githubCli": {
            "version": NATIVE_RELEASE_GITHUB_CLI_VERSION,
            "versionOutputSha256": _sha256(version_output),
        },
        "immutableReleases": immutable_releases,
        "release": {
            "apiUrl": release["apiUrl"],
            "assets": normalized_assets,
            "draft": False,
            "htmlUrl": expected_release_url,
            "id": release_id,
            "immutable": True,
            "nodeId": release_node_id,
            "peeledTagCommit": source_commit,
            "prerelease": True,
            "tagName": tag,
            "targetCommitish": source_commit,
        },
        "releaseAttestation": release_attestation,
        "assetAttestations": asset_attestations,
    }
    return {
        "schemaVersion": GITHUB_PROVIDER_VERIFICATION_SCHEMA,
        "canonicalDigest": _sha256(release_canonical_json_bytes(metadata)),
        "metadata": metadata,
    }


def finalize_evidence_receipt(
    *,
    release_identity_path: Path,
    candidate_receipt_path: Path,
    source_directory: Path,
    repository_root: Path,
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
            allow_candidate=True,
        )
    except NativeReleaseIdentityError as exc:
        raise NativeEvidenceError(str(exc)) from exc
    if identity.status != "frozen" or candidate.status != "candidate":
        raise NativeEvidenceError(
            "receipt finalization requires frozen identity and candidate receipt"
        )
    current_authority = evidence_authority_input_manifest(repository_root)
    if (
        candidate.document["evidenceAuthorityInput"] != current_authority
        and candidate.digest != HISTORICAL_V1_CANDIDATE_RECEIPT_DIGEST
    ):
        raise NativeEvidenceError(
            "historical candidate evidence authority is not the exact v1 migration"
        )
    with tempfile.TemporaryDirectory(prefix="ofarm-native-release-") as temporary:
        provider_verification = _authenticate_github_release(
            candidate=candidate,
            identity=identity,
            source_directory=source_directory,
            download_directory=Path(temporary),
        )
    try:
        frozen = frozen_evidence_receipt_document(
            candidate_receipt=candidate,
            release_identity=identity,
            provider_verification=provider_verification,
            repository_root=repository_root,
        )
    except NativeReleaseIdentityError as exc:
        raise NativeEvidenceError(str(exc)) from exc
    frozen_bytes = release_canonical_json_bytes(frozen)
    _publish_regular_no_clobber(
        output,
        frozen_bytes,
        "frozen native evidence receipt",
    )
    return {
        "status": "frozen",
        "release_identity_digest": identity.digest,
        "receipt_digest": _sha256(frozen_bytes),
    }


def verify_frozen_evidence_receipt(
    *,
    release_identity_path: Path,
    evidence_receipt_path: Path,
    source_directory: Path,
    repository_root: Path,
) -> dict[str, Any]:
    """Re-run maintained GitHub/Sigstore verification for retained evidence."""

    try:
        identity = load_native_release_identity(
            release_identity_path,
            verify_current_sources=True,
            source_directory=source_directory,
        )
        receipt = load_native_evidence_receipt(
            evidence_receipt_path,
            release_identity=identity,
            verify_current_authority=True,
            repository_root=repository_root,
        )
    except NativeReleaseIdentityError as exc:
        raise NativeEvidenceError(str(exc)) from exc
    if identity.status != "frozen" or receipt.status != "frozen":
        raise NativeEvidenceError("native release evidence is not frozen")
    with tempfile.TemporaryDirectory(
        prefix="ofarm-native-release-reverify-"
    ) as directory:
        observed = _authenticate_github_release(
            candidate=receipt,
            identity=identity,
            source_directory=source_directory,
            download_directory=Path(directory),
            retained_immutable_releases=receipt.document["preservation"][
                "providerVerification"
            ]["metadata"]["immutableReleases"],
        )
    retained = receipt.document["preservation"]["providerVerification"]
    if observed != retained:
        raise NativeEvidenceError(
            "retained provider verification differs from fresh cryptographic "
            "verification"
        )
    return {
        "evidenceReceiptDigest": receipt.digest,
        "providerVerificationDigest": observed["canonicalDigest"],
        "releaseIdentityDigest": identity.digest,
        "status": "cryptographically-verified",
    }


def conformance_environment(
    *,
    checked_identity_path: Path,
    checked_receipt_path: Path,
    archive_path: Path,
    source_directory: Path,
    repository_root: Path,
    image_name: str,
    archive_reference: str,
) -> str:
    """Resolve exact derived-image test inputs without a frozen bootstrap claim."""

    if image_name != "ofarm-postgresql-conformance:local":
        raise NativeEvidenceError("conformance image name is not the exact local tag")
    if (
        not archive_reference
        or len(archive_reference) > 1024
        or "\n" in archive_reference
        or "\r" in archive_reference
        or str(archive_path) != archive_reference
    ):
        raise NativeEvidenceError("conformance OCI archive reference is invalid")
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
    observed_child, observed_config = docker_transport_child_identity(
        archive_path,
        "derived PostgreSQL Docker transport archive",
        platform="linux/amd64",
        image_name=image_name,
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
        "ISSUE174_DERIVED_POSTGRES_ARCHIVE": archive_reference,
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
    compare.add_argument("--first-archive", type=Path, required=True)
    compare.add_argument("--second-archive", type=Path, required=True)
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
    finalize.add_argument("--output", type=Path, required=True)

    reverify = subparsers.add_parser("verify-frozen-evidence-receipt")
    reverify.add_argument("--release-identity", type=Path, required=True)
    reverify.add_argument("--evidence-receipt", type=Path, required=True)
    reverify.add_argument("--source-directory", type=Path, required=True)
    reverify.add_argument("--repository-root", type=Path, required=True)

    environment = subparsers.add_parser("conformance-environment")
    environment.add_argument("--checked-identity", type=Path, required=True)
    environment.add_argument("--checked-receipt", type=Path, required=True)
    environment.add_argument("--archive", type=Path, required=True)
    environment.add_argument("--source-directory", type=Path, required=True)
    environment.add_argument("--repository-root", type=Path, required=True)
    environment.add_argument("--image-name", required=True)
    environment.add_argument("--archive-reference", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "compare-builds":
            compare_builds(
                first_archive=args.first_archive,
                second_archive=args.second_archive,
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
                output=args.output,
            )
        elif args.command == "verify-frozen-evidence-receipt":
            print(
                json.dumps(
                    verify_frozen_evidence_receipt(
                        release_identity_path=args.release_identity,
                        evidence_receipt_path=args.evidence_receipt,
                        source_directory=args.source_directory,
                        repository_root=args.repository_root,
                    ),
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        else:
            print(
                conformance_environment(
                    checked_identity_path=args.checked_identity,
                    checked_receipt_path=args.checked_receipt,
                    archive_path=args.archive,
                    source_directory=args.source_directory,
                    repository_root=args.repository_root,
                    image_name=args.image_name,
                    archive_reference=args.archive_reference,
                ),
                end="",
            )
    except NativeEvidenceError as exc:
        raise SystemExit(f"native evidence refused: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
