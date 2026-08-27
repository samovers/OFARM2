#!/usr/bin/env python3
"""Trusted download, extraction, and inventory policy for published evidence."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
import re
import stat
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any


SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
PLATFORM_EVIDENCE_NAME = re.compile(
    r"platform_mvp_results_[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z[.]json"
)
TIMESTAMP = re.compile(
    r"[0-9]{4}-(?:0[1-9]|1[0-2])-"
    r"(?:0[1-9]|[12][0-9]|3[01])T"
    r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"(?:\.[0-9]{6})?Z"
)
GITHUB_API_VERSION = "2026-03-10"
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
MAX_ZIP_ENTRIES = 256
PROVISIONAL_ARTIFACT_LIMITS = {
    "conformance-provisional": 512_000_000,
    "native-verifier-amd64-provisional": 1_650_000_000,
    "native-verifier-arm64-provisional": 1_650_000_000,
}
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_INSTALLED_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_SOURCE_INPUT_BYTES = 8 * 1024 * 1024
POLICY_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_PUBLICATION_FILE = "platform-mvp-evidence.json"
PLATFORM_PUBLICATION_SCHEMA = "ofarm.platform-mvp-publication-evidence.v1"
PLATFORM_TEST_SUITE = (
    "conformance:ofarm2.platform-mvp.tests-1-15-plus-regressions.v0_2"
)
TRUSTED_METADATA_FILES = frozenset(
    {
        "evidence-publication-context.json",
        "review-baseline-admission.json",
    }
)
REVIEW_BASELINE_FILES = frozenset(
    {
        "equivalence.json",
        "run-1/kernel-test-results.json",
        "run-1/review-baseline-evidence.json",
        "run-2/kernel-test-results.json",
        "run-2/review-baseline-evidence.json",
    }
)
NATIVE_PROVISIONAL_FILES = frozenset(
    {
        "address.log",
        "attestations/oci-evidence.json",
        "attestations/provenance.slsa-v0.2.in-toto.json",
        "attestations/sbom.spdx.in-toto.json",
        "attested-metadata.json",
        "buildx-version.txt",
        "first-image.docker.tar",
        "first-artifacts.tar",
        "invalid-sanitizer.log",
        "ofarm-ed25519.oci.tar",
        "reproducibility.json",
        "second-artifacts.tar",
        "second-image.docker.tar",
        "undefined.log",
    }
)
NATIVE_AUTHORITATIVE_FILES = frozenset(
    {
        "attestations/oci-evidence.json",
        "attestations/provenance.slsa-v0.2.in-toto.json",
        "attestations/sbom.spdx.in-toto.json",
        "first-artifacts.tar",
        "ofarm-ed25519.oci.tar",
        "reproducibility.json",
        "second-artifacts.tar",
    }
)
# Compatibility name for callers that inspect the provisional producer contract.
NATIVE_EVIDENCE_FILES = NATIVE_PROVISIONAL_FILES
ResponseFactory = Callable[[urllib.request.Request], object]


class PublicationPolicyError(ValueError):
    """Untrusted artifact bytes violated publication policy."""


class _HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise PublicationPolicyError("artifact download redirect is not HTTPS")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _checked_digest(value: str) -> str:
    if SHA256.fullmatch(value) is None:
        raise PublicationPolicyError("artifact digest is not canonical SHA-256")
    return value


def _checked_repository(value: str) -> str:
    if REPOSITORY.fullmatch(value) is None:
        raise PublicationPolicyError("artifact repository identity is malformed")
    return value


def _checked_api_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise PublicationPolicyError("GitHub API URL is not canonical HTTPS")
    return value.rstrip("/")


def _checked_source_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise PublicationPolicyError("source input path is not canonical")
    raw_parts = value.split("/")
    parts = PurePosixPath(value).parts
    if (
        value.startswith("/")
        or parts != tuple(raw_parts)
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        raise PublicationPolicyError("source input path is not canonical")
    return value


def _fresh_output_root(path: Path) -> Path:
    if path.exists() or path.is_symlink():
        raise PublicationPolicyError("artifact extraction root is not fresh")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(mode=0o700)
    root = path.resolve(strict=True)
    if not root.is_dir():
        raise PublicationPolicyError("artifact extraction root is not a directory")
    return root


def _inside(root: Path, target: Path) -> None:
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise PublicationPolicyError(
            "artifact archive entry escapes its extraction root"
        ) from exc


def _archive_parts(name: str, *, directory: bool) -> tuple[str, ...]:
    if "\\" in name or "\x00" in name or name.startswith("/"):
        raise PublicationPolicyError("artifact archive entry path is unsafe")
    normalized = name[:-1] if directory and name.endswith("/") else name
    raw_parts = normalized.split("/")
    if not normalized or any(part in {"", ".", ".."} for part in raw_parts):
        raise PublicationPolicyError("artifact archive entry path is unsafe")
    parts = PurePosixPath(normalized).parts
    if not parts or parts != tuple(raw_parts):
        raise PublicationPolicyError("artifact archive entry path is not canonical")
    return parts


def _extract_verified_zip(archive_path: Path, root: Path, limit: int) -> None:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_ZIP_ENTRIES:
                raise PublicationPolicyError("artifact ZIP entry count is invalid")
            if sum(entry.file_size for entry in entries) > limit:
                raise PublicationPolicyError("artifact expanded size exceeds its limit")
            observed: set[tuple[str, ...]] = set()
            for entry in entries:
                if entry.flag_bits & 0x1:
                    raise PublicationPolicyError("artifact ZIP entry is encrypted")
                parts = _archive_parts(entry.filename, directory=entry.is_dir())
                if parts in observed:
                    raise PublicationPolicyError("artifact ZIP entry is duplicated")
                observed.add(parts)
                mode = (entry.external_attr >> 16) & 0xFFFF
                kind = stat.S_IFMT(mode)
                allowed_kind = stat.S_IFDIR if entry.is_dir() else stat.S_IFREG
                if kind not in {0, allowed_kind}:
                    raise PublicationPolicyError(
                        "artifact ZIP entry is not a regular file or directory"
                    )
                target = root.joinpath(*parts)
                _inside(root, target.resolve(strict=False))
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=False)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                _inside(root, target.parent.resolve(strict=True))
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                flags |= getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(target, flags, 0o600)
                written = 0
                try:
                    with os.fdopen(descriptor, "wb") as output:
                        descriptor = -1
                        with archive.open(entry, "r") as source:
                            while True:
                                chunk = source.read(DOWNLOAD_CHUNK_BYTES)
                                if not chunk:
                                    break
                                written += len(chunk)
                                if written > entry.file_size:
                                    raise PublicationPolicyError(
                                        "artifact ZIP entry expanded unexpectedly"
                                    )
                                output.write(chunk)
                finally:
                    if descriptor >= 0:
                        os.close(descriptor)
                if written != entry.file_size:
                    raise PublicationPolicyError(
                        "artifact ZIP entry size differs from its declaration"
                    )
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise PublicationPolicyError("artifact ZIP extraction failed") from exc


def _download_archive(
    *,
    request: urllib.request.Request,
    archive_path: Path,
    limit: int,
    response_factory: ResponseFactory | None,
) -> str:
    try:
        response_context = (
            response_factory(request)
            if response_factory is not None
            else urllib.request.build_opener(_HttpsOnlyRedirectHandler()).open(
                request,
                timeout=60,
            )
        )
        digest = hashlib.sha256()
        size = 0
        with response_context as response:  # type: ignore[attr-defined]
            if getattr(response, "status", 200) != 200:
                raise PublicationPolicyError("artifact download did not return HTTP 200")
            final_url = getattr(response, "geturl", lambda: request.full_url)()
            if urllib.parse.urlsplit(final_url).scheme != "https":
                raise PublicationPolicyError("artifact download response is not HTTPS")
            with archive_path.open("xb") as output:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit:
                        raise PublicationPolicyError(
                            "artifact archive size exceeds its limit"
                        )
                    digest.update(chunk)
                    output.write(chunk)
    except (OSError, urllib.error.URLError) as exc:
        raise PublicationPolicyError("artifact download failed") from exc
    if size == 0:
        raise PublicationPolicyError("artifact archive is empty")
    return "sha256:" + digest.hexdigest()


def download_and_extract_artifact(
    *,
    api_url: str,
    repository: str,
    artifact_name: str,
    artifact_id: int,
    expected_digest: str,
    output_directory: Path,
    token: str,
    response_factory: ResponseFactory | None = None,
) -> None:
    """Download one immutable artifact ZIP and extract only contained files."""

    if artifact_name not in PROVISIONAL_ARTIFACT_LIMITS:
        raise PublicationPolicyError("artifact name is not provisional and allowlisted")
    if not isinstance(artifact_id, int) or isinstance(artifact_id, bool) or artifact_id <= 0:
        raise PublicationPolicyError("artifact ID is not a positive integer")
    if not token or "\n" in token or "\r" in token:
        raise PublicationPolicyError("artifact download token is absent or malformed")
    expected = _checked_digest(expected_digest)
    repository = _checked_repository(repository)
    api_url = _checked_api_url(api_url)
    root = _fresh_output_root(output_directory)
    archive_path = root / ".ofarm-artifact.zip"
    request = urllib.request.Request(
        f"{api_url}/repos/{repository}/actions/artifacts/{artifact_id}/zip",
        headers={
            "Accept": "application/vnd.github+json",
            "Accept-Encoding": "identity",
            "User-Agent": "ofarm-evidence-publication",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
    )
    request.add_unredirected_header("Authorization", f"Bearer {token}")
    observed = _download_archive(
        request=request,
        archive_path=archive_path,
        limit=PROVISIONAL_ARTIFACT_LIMITS[artifact_name],
        response_factory=response_factory,
    )
    if observed != expected:
        raise PublicationPolicyError("downloaded artifact digest differs from admission")
    _extract_verified_zip(
        archive_path,
        root,
        PROVISIONAL_ARTIFACT_LIMITS[artifact_name],
    )
    archive_path.unlink()
    _regular_file_inventory(root)


def _download_authenticated_source_file(
    *,
    api_url: str,
    repository: str,
    source_commit: str,
    source_path: object,
    token: str,
    response_factory: ResponseFactory | None = None,
) -> bytes:
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise PublicationPolicyError("source commit is not a full lowercase SHA")
    if not token or "\n" in token or "\r" in token:
        raise PublicationPolicyError("source input token is absent or malformed")
    api_url = _checked_api_url(api_url)
    repository = _checked_repository(repository)
    checked_path = _checked_source_path(source_path)
    encoded_path = urllib.parse.quote(checked_path, safe="/")
    query = urllib.parse.urlencode({"ref": source_commit})
    request = urllib.request.Request(
        f"{api_url}/repos/{repository}/contents/{encoded_path}?{query}",
        headers={
            "Accept": "application/vnd.github.raw+json",
            "Accept-Encoding": "identity",
            "User-Agent": "ofarm-evidence-publication",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
    )
    request.add_unredirected_header("Authorization", f"Bearer {token}")
    try:
        response_context = (
            response_factory(request)
            if response_factory is not None
            else urllib.request.build_opener(_HttpsOnlyRedirectHandler()).open(
                request,
                timeout=30,
            )
        )
        payload = bytearray()
        with response_context as response:  # type: ignore[attr-defined]
            if getattr(response, "status", 200) != 200:
                raise PublicationPolicyError("source input read did not return HTTP 200")
            final_url = getattr(response, "geturl", lambda: request.full_url)()
            if final_url != request.full_url:
                raise PublicationPolicyError("source input read was redirected")
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                payload.extend(chunk)
                if len(payload) > MAX_SOURCE_INPUT_BYTES:
                    raise PublicationPolicyError("source input exceeds its size limit")
    except (OSError, urllib.error.URLError) as exc:
        raise PublicationPolicyError("source input read failed") from exc
    if not payload:
        raise PublicationPolicyError("source input is empty")
    return bytes(payload)


def _regular_file_inventory(root: Path) -> frozenset[str]:
    if not root.is_dir() or root.is_symlink():
        raise PublicationPolicyError("evidence inventory root is not a directory")
    resolved_root = root.resolve(strict=True)
    files: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PublicationPolicyError("evidence inventory contains a symlink")
        resolved = path.resolve(strict=True)
        _inside(resolved_root, resolved)
        if path.is_file():
            files.add(path.relative_to(root).as_posix())
        elif not path.is_dir():
            raise PublicationPolicyError("evidence inventory contains a special file")
    return frozenset(files)


def _review_policy_module():
    root = str(POLICY_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from conformance import run_review_baseline as review_policy

    return review_policy


def _load_source_test_inventory(
    payload: bytes,
    *,
    config: dict[str, Any],
) -> dict[str, Any]:
    review_policy = _review_policy_module()
    document = _decode_json_object(payload, "authenticated source test inventory")
    try:
        expected = review_policy._inventory_document(
            config["paths"]["testRoot"],
            document.get("entries"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PublicationPolicyError(
            "authenticated source test inventory is invalid"
        ) from exc
    if document != expected:
        raise PublicationPolicyError(
            "authenticated source test inventory is stale or non-canonical"
        )
    return document


def _native_policy_module():
    module_name = "_ofarm_publication_native_evidence"
    loaded = sys.modules.get(module_name)
    if loaded is not None:
        return loaded
    source_directory = POLICY_ROOT / "deployment/postgresql"
    source_path = source_directory / "native_evidence.py"
    source_text = str(source_directory)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    if spec is None or spec.loader is None:
        raise PublicationPolicyError("trusted native policy cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise PublicationPolicyError("trusted native policy cannot be loaded") from exc
    return module


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PublicationPolicyError(f"{label} must be an object")
    return value


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PublicationPolicyError(f"{label} must be an array")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise PublicationPolicyError(f"{label} fields are not exact")


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise PublicationPolicyError("JSON contains a duplicate object key")
        value[key] = item
    return value


def _reject_non_finite_json_number(value: str) -> None:
    raise PublicationPolicyError(f"JSON contains forbidden number {value}")


def _parse_finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise PublicationPolicyError(f"JSON contains forbidden number {value}")
    return parsed


def _decode_json_object(payload: bytes, label: str) -> dict[str, Any]:
    if not 0 < len(payload) <= MAX_JSON_BYTES:
        raise PublicationPolicyError(f"{label} is not bounded JSON")
    try:
        text = payload.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_non_finite_json_number,
            parse_float=_parse_finite_json_float,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PublicationPolicyError(f"{label} is not readable JSON") from exc
    return _object(value, label)


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        file_stat = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(file_stat.st_mode) or not 0 < file_stat.st_size <= MAX_JSON_BYTES:
            raise PublicationPolicyError(f"{label} is not one bounded regular file")
        payload = path.read_bytes()
    except OSError as exc:
        raise PublicationPolicyError(f"{label} is not readable JSON") from exc
    return _decode_json_object(payload, label)


def _sha256_hex_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(DOWNLOAD_CHUNK_BYTES), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PublicationPolicyError("evidence file cannot be hashed") from exc
    return digest.hexdigest()


def _copy_regular_file(
    source: Path,
    destination: Path,
    *,
    maximum: int,
    mode: int = 0o600,
    required_source_mode: int | None = None,
) -> None:
    try:
        source_stat = source.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(source_stat.st_mode)
            or source_stat.st_size <= 0
            or source_stat.st_size > maximum
            or (
                required_source_mode is not None
                and stat.S_IMODE(source_stat.st_mode) != required_source_mode
            )
        ):
            raise PublicationPolicyError("publication source file is not bounded regular data")
        destination.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(destination, flags, mode)
        os.fchmod(descriptor, mode)
        written = 0
        try:
            with source.open("rb") as input_file, os.fdopen(descriptor, "wb") as output:
                descriptor = -1
                while True:
                    chunk = input_file.read(DOWNLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > maximum:
                        raise PublicationPolicyError("publication copy exceeded its limit")
                    output.write(chunk)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if written != source_stat.st_size:
            raise PublicationPolicyError("publication source changed while being copied")
    except OSError as exc:
        raise PublicationPolicyError("publication source file cannot be copied") from exc


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
    except (TypeError, ValueError) as exc:
        raise PublicationPolicyError(
            "trusted publication JSON is not canonicalizable"
        ) from exc


def _write_canonical_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _canonical_json_bytes(value)
    try:
        with path.open("xb") as output:
            output.write(data)
    except OSError as exc:
        raise PublicationPolicyError("trusted publication JSON cannot be written") from exc


def _validate_test_results(
    results: dict[str, Any],
    *,
    expected_inventory: dict[str, Any],
    warning_policy: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    review_policy = _review_policy_module()
    _exact_keys(
        results,
        {"schemaVersion", "collection", "execution", "warnings", "summary"},
        "review baseline result",
    )
    if results.get("schemaVersion") != "ofarm.review-baseline-pytest-results.v2":
        raise PublicationPolicyError("review baseline result schema is not exact")
    collection = _object(results.get("collection"), "review baseline collection")
    _exact_keys(
        collection,
        {"collected", "selected", "deselected", "skippedCollectors", "errors"},
        "review baseline collection",
    )
    try:
        collected = review_policy._normalised_inventory_entries(collection["collected"])
        selected = review_policy._normalised_inventory_entries(collection["selected"])
    except ValueError as exc:
        raise PublicationPolicyError("review baseline test inventory is malformed") from exc
    expected = expected_inventory["entries"]
    if collected != expected or selected != expected:
        raise PublicationPolicyError("review baseline pinned test inventory differs")
    if collection["collected"] != collected or collection["selected"] != selected:
        raise PublicationPolicyError("review baseline test inventory is not canonical")
    if any(collection[name] != [] for name in ("deselected", "skippedCollectors", "errors")):
        raise PublicationPolicyError("review baseline collection is incomplete")

    execution = _object(results.get("execution"), "review baseline execution")
    _exact_keys(execution, {"outcomes", "skipped", "unavailable"}, "review baseline execution")
    if execution["skipped"] != [] or execution["unavailable"] != []:
        raise PublicationPolicyError("review baseline execution contains non-passing tests")
    outcomes = _array(execution.get("outcomes"), "review baseline outcomes")
    if len(outcomes) != len(expected):
        raise PublicationPolicyError("review baseline outcome inventory is incomplete")
    expected_phases = [
        {"phase": "setup", "outcome": "passed"},
        {"phase": "call", "outcome": "passed"},
        {"phase": "teardown", "outcome": "passed"},
    ]
    for observed, inventory_entry in zip(outcomes, expected, strict=True):
        outcome = _object(observed, "review baseline outcome")
        _exact_keys(
            outcome,
            {"nodeid", "sourceModule", "sourcePath", "outcome", "phases"},
            "review baseline outcome",
        )
        if (
            {key: outcome[key] for key in ("nodeid", "sourceModule", "sourcePath")}
            != inventory_entry
            or outcome.get("outcome") != "passed"
            or outcome.get("phases") != expected_phases
        ):
            raise PublicationPolicyError("review baseline outcome is not one complete pass")

    try:
        warnings = review_policy._normalised_warning_inventory(results.get("warnings"))
        warning_check = review_policy._warning_policy_check(warning_policy, warnings)
    except ValueError as exc:
        raise PublicationPolicyError("review baseline warning inventory is malformed") from exc
    if results.get("warnings") != warnings or warning_check.get("matches") is not True:
        raise PublicationPolicyError("review baseline warning inventory differs")
    count = len(expected)
    expected_summary = {
        "collected": count,
        "selected": count,
        "passed": count,
        "failed": 0,
        "error": 0,
        "xfailed": 0,
        "xpassed": 0,
        "skipped": 0,
        "deselected": 0,
        "collectionSkipped": 0,
        "unavailable": 0,
        "collectionErrors": 0,
        "warnings": len(warnings),
        "pytestExitStatus": 0,
    }
    if results.get("summary") != expected_summary:
        raise PublicationPolicyError("review baseline result summary is inconsistent")
    inventory_check = review_policy._test_inventory_check(expected_inventory, collected)
    if inventory_check.get("matches") is not True:
        raise PublicationPolicyError("review baseline inventory acceptance differs")
    return inventory_check, warning_check


def _validate_environment(
    environment: dict[str, Any],
    *,
    config: dict[str, Any],
    source_run_id: int,
    source_run_attempt: int,
) -> None:
    review_policy = _review_policy_module()
    _exact_keys(
        environment,
        {"platform", "python", "pip", "postgresql", "dependencies", "determinism", "ci"},
        "review baseline environment",
    )
    required = _object(config.get("requiredEnvironment"), "required environment")

    platform = _object(environment.get("platform"), "platform environment")
    _exact_keys(platform, {"operatingSystem", "machine"}, "platform environment")
    for field, config_name in (("operatingSystem", "operatingSystem"), ("machine", "machine")):
        value = _object(platform.get(field), f"platform {field}")
        if value != {"actual": required[config_name], "required": required[config_name]}:
            raise PublicationPolicyError(f"platform {field} differs from its pin")

    python = _object(environment.get("python"), "Python environment")
    _exact_keys(python, {"implementation", "version", "optimizationLevel"}, "Python environment")
    for field, config_name in (
        ("implementation", "pythonImplementation"),
        ("version", "pythonVersion"),
        ("optimizationLevel", "pythonOptimizationLevel"),
    ):
        value = _object(python.get(field), f"Python {field}")
        if value != {"actual": required[config_name], "required": required[config_name]}:
            raise PublicationPolicyError(f"Python {field} differs from its pin")
    if environment.get("pip") != {
        "actual": required["pipVersion"],
        "required": required["pipVersion"],
    }:
        raise PublicationPolicyError("pip environment differs from its pin")

    postgresql = _object(environment.get("postgresql"), "PostgreSQL environment")
    _exact_keys(
        postgresql,
        {
            "requiredVersion",
            "testConnectionSource",
            "testDatabase",
            "admin",
            "tenantProvisioningAdmin",
            "securityAuditAdmin",
            "testStore",
            "sameServer",
            "tenantAuditSystemIdentifiersDistinct",
            "testAndProvisioningSystemIdentifiersPairwiseDistinct",
            "testAndProvisioningPostgresqlVersionsEqual",
            "testAndProvisioningPostgresqlBuildsEqual",
        },
        "PostgreSQL environment",
    )
    if (
        postgresql.get("requiredVersion") != required["postgresqlVersion"]
        or postgresql.get("testConnectionSource")
        != "derived-from-verified-admin-connection"
        or postgresql.get("testDatabase") != required["testDatabaseName"]
        or any(
            postgresql.get(field) is not True
            for field in (
                "sameServer",
                "tenantAuditSystemIdentifiersDistinct",
                "testAndProvisioningSystemIdentifiersPairwiseDistinct",
                "testAndProvisioningPostgresqlVersionsEqual",
                "testAndProvisioningPostgresqlBuildsEqual",
            )
        )
    ):
        raise PublicationPolicyError("PostgreSQL environment claims are inconsistent")
    identities: dict[str, dict[str, Any]] = {}
    for name in ("admin", "tenantProvisioningAdmin", "securityAuditAdmin", "testStore"):
        identity = _object(postgresql.get(name), f"PostgreSQL {name} identity")
        _exact_keys(
            identity,
            {"available", "version", "rawVersion", "systemIdentifier", "database"},
            f"PostgreSQL {name} identity",
        )
        if (
            identity.get("available") is not True
            or identity.get("version") != required["postgresqlVersion"]
            or not isinstance(identity.get("rawVersion"), str)
            or not identity.get("rawVersion")
            or not isinstance(identity.get("systemIdentifier"), str)
            or not identity.get("systemIdentifier")
        ):
            raise PublicationPolicyError(f"PostgreSQL {name} identity is incomplete")
        identities[name] = identity
    if (
        identities["admin"]["database"] != "postgres"
        or identities["tenantProvisioningAdmin"]["database"] != "postgres"
        or identities["securityAuditAdmin"]["database"] != "postgres"
        or identities["testStore"]["database"] != required["testDatabaseName"]
        or identities["admin"]["systemIdentifier"]
        != identities["testStore"]["systemIdentifier"]
        or len(
            {
                identities[name]["systemIdentifier"]
                for name in ("admin", "tenantProvisioningAdmin", "securityAuditAdmin")
            }
        )
        != 3
        or len({identity["rawVersion"] for identity in identities.values()}) != 1
    ):
        raise PublicationPolicyError("PostgreSQL server identities are inconsistent")

    dependencies = _object(environment.get("dependencies"), "dependency environment")
    _exact_keys(
        dependencies,
        {"installed", "installedSetDigest", "missingOrMismatched", "unexpected", "pipCheckPassed"},
        "dependency environment",
    )
    paths = _object(config.get("paths"), "review baseline paths")
    locked = review_policy._parse_lock(POLICY_ROOT / paths["dependencyLock"])
    locked.update(review_policy._parse_lock(POLICY_ROOT / paths["packageManagerLock"]))
    expected_installed = [
        {"name": name, "version": locked[name]} for name in sorted(locked)
    ]
    expected_installed_digest = review_policy._sha256_bytes(
        review_policy._canonical_bytes(expected_installed)
    )
    if (
        dependencies.get("installed") != expected_installed
        or dependencies.get("installedSetDigest") != expected_installed_digest
        or dependencies.get("missingOrMismatched") != {}
        or dependencies.get("unexpected") != {}
        or dependencies.get("pipCheckPassed") is not True
    ):
        raise PublicationPolicyError("dependency environment differs from locked inputs")

    determinism = _object(environment.get("determinism"), "determinism environment")
    expected_determinism = {
        "pythonHashSeed": required["pythonHashSeed"],
        "timezone": required["timezone"],
        "locale": required["locale"],
        "pytestPluginAutoloadDisabled": True,
        "pythonNoUserSite": True,
        "pythonDontWriteBytecode": True,
        "scrubbedAmbientVariables": [
            "PYTEST_ADDOPTS",
            "PYTEST_PLUGINS",
            "PYTHONOPTIMIZE",
            "PYTHONPATH",
            "PYTHONWARNINGS",
            "OFARM_*",
        ],
        "allowedOfarmVariables": sorted(review_policy.ALLOWED_OFARM_ENV),
        "derivedOfarmVariables": ["OFARM_PG_DSN"],
    }
    if determinism != expected_determinism:
        raise PublicationPolicyError("determinism environment differs from policy")

    ci = _object(environment.get("ci"), "CI environment")
    _exact_keys(
        ci,
        {
            "configuredRunnerLabel",
            "observedImageOs",
            "observedImageVersion",
            "runId",
            "runAttempt",
            "configuredActionPins",
            "configuredPostgresqlImageDigest",
        },
        "CI environment",
    )
    observed_image = (ci.get("observedImageOs"), ci.get("observedImageVersion"))
    known = _object(config.get("knownGreenBaseline"), "known green baseline")
    configured = _object(known.get("observedInRun"), "known baseline run")
    if (
        ci.get("configuredRunnerLabel") != required["runner"]
        or ci.get("runId") != str(source_run_id)
        or ci.get("runAttempt") != str(source_run_attempt)
        or ci.get("configuredActionPins") != configured["actions"]
        or ci.get("configuredPostgresqlImageDigest")
        != configured["postgresqlImageDigest"]
        or any(not isinstance(value, str) or not value for value in observed_image)
    ):
        raise PublicationPolicyError("CI environment differs from source coordinates")


def _validate_produced_artifact_binding(
    produced_artifacts: object,
    results_path: Path,
) -> None:
    if produced_artifacts != _produced_artifact_binding(results_path):
        raise PublicationPolicyError("review baseline producedArtifacts binding differs")


def _produced_artifact_binding(results_path: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": "kernel-test-results.json",
            "sha256": _sha256_hex_file(results_path),
            "bytes": results_path.stat().st_size,
        }
    ]


def _canonical_utc_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or TIMESTAMP.fullmatch(value) is None:
        raise PublicationPolicyError(f"{label} is not a canonical UTC timestamp")
    try:
        parsed = datetime.strptime(
            value,
            "%Y-%m-%dT%H:%M:%S.%fZ" if "." in value else "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise PublicationPolicyError(
            f"{label} is not a canonical UTC timestamp"
        ) from exc
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise PublicationPolicyError(f"{label} is not a canonical UTC timestamp")
    return parsed


def _expected_review_steps(config: dict[str, Any]) -> list[dict[str, Any]]:
    paths = _object(config.get("paths"), "review baseline paths")

    def passed(name: str, command: list[str]) -> dict[str, Any]:
        return {
            "name": name,
            "command": command,
            "outcome": "passed",
            "exitCode": 0,
        }

    return [
        passed(
            "package-self-check",
            ["python", "conformance/ofarm_pkg_contract_check.py"],
        ),
        passed("pip-check", ["python", "-m", "pip", "check"]),
        passed(
            "environment-preflight",
            ["internal:exact-environment-preflight"],
        ),
        passed(
            "verify-pinned-test-inventory",
            ["internal:pinned-test-inventory"],
        ),
        passed(
            "verify-warning-inventory",
            ["internal:exact-warning-inventory"],
        ),
        passed(
            "complete-kernel-tests",
            [
                "python",
                "-m",
                "pytest",
                paths["testRoot"],
                "-q",
                "-p",
                "no:cacheprovider",
                "-p",
                "conformance.review_baseline_pytest",
                "--review-baseline-results",
                "kernel-test-results.json",
            ],
        ),
        passed(
            "verify-generated-manifest",
            ["python", "-m", "kernel.manifest", "--verify-generated"],
        ),
        passed(
            "verify-test-store-postgresql",
            ["internal:postgresql-server-identity"],
        ),
        passed(
            "verify-post-run-git-state",
            ["internal:post-run-git-integrity"],
        ),
    ]


def _validate_baseline_evidence(
    evidence: dict[str, Any],
    *,
    results: dict[str, Any],
    results_path: Path,
    config: dict[str, Any],
    expected_inventory: dict[str, Any],
    source_inventory_sha256: str,
    source_commit: str,
    source_run_id: int,
    source_run_attempt: int,
) -> None:
    review_policy = _review_policy_module()
    _exact_keys(
        evidence,
        {
            "schemaVersion",
            "normalizationPolicy",
            "run",
            "git",
            "inputs",
            "environment",
            "tests",
            "testAcceptance",
            "steps",
            "producedArtifacts",
            "producedArtifactsNote",
            "verifiedArtifacts",
        },
        "review baseline evidence",
    )
    if (
        evidence.get("schemaVersion") != review_policy.EVIDENCE_SCHEMA
        or evidence.get("normalizationPolicy") != review_policy._normalization_policy()
    ):
        raise PublicationPolicyError("review baseline evidence schema is not exact")
    run = _object(evidence.get("run"), "review baseline run")
    _exact_keys(run, {"startedAt", "finishedAt", "canonicalCommand", "outcome"}, "review baseline run")
    started_at = _canonical_utc_timestamp(
        run.get("startedAt"),
        "review baseline startedAt",
    )
    finished_at = _canonical_utc_timestamp(
        run.get("finishedAt"),
        "review baseline finishedAt",
    )
    if (
        run.get("canonicalCommand") != config["canonicalCommand"]
        or run.get("outcome") != "passed"
        or finished_at < started_at
    ):
        raise PublicationPolicyError("review baseline run claim is inconsistent")

    git = _object(evidence.get("git"), "review baseline Git state")
    _exact_keys(git, {"start", "end", "unchanged"}, "review baseline Git state")
    expected_clean_digest = hashlib.sha256(b"\n").hexdigest()
    start = _object(git.get("start"), "review baseline starting Git state")
    end = _object(git.get("end"), "review baseline ending Git state")
    for state in (start, end):
        _exact_keys(
            state,
            {"sha", "treeSha", "dirty", "dirtyEntryCount", "statusDigest"},
            "review baseline Git state item",
        )
        if (
            state.get("sha") != source_commit
            or not isinstance(state.get("treeSha"), str)
            or re.fullmatch(r"[0-9a-f]{40}", state["treeSha"]) is None
            or state.get("dirty") is not False
            or state.get("dirtyEntryCount") != 0
            or state.get("statusDigest") != expected_clean_digest
        ):
            raise PublicationPolicyError("review baseline Git state is not clean and exact")
    if start != end or git.get("unchanged") is not True:
        raise PublicationPolicyError("review baseline Git state changed")

    paths = _object(config.get("paths"), "review baseline paths")
    inputs = _object(evidence.get("inputs"), "review baseline inputs")
    _exact_keys(inputs, {"config", "dependencyLock", "packageManagerLock", "testInventory", "schema"}, "review baseline inputs")
    expected_inputs = {
        "config": {
            "path": "conformance/review_baseline_config.json",
            "sha256": _sha256_hex_file(POLICY_ROOT / "conformance/review_baseline_config.json"),
        },
        "dependencyLock": {
            "path": paths["dependencyLock"],
            "sha256": _sha256_hex_file(POLICY_ROOT / paths["dependencyLock"]),
        },
        "packageManagerLock": {
            "path": paths["packageManagerLock"],
            "sha256": _sha256_hex_file(POLICY_ROOT / paths["packageManagerLock"]),
        },
        "testInventory": {
            "path": paths["testInventory"],
            "sha256": source_inventory_sha256,
            "entriesSha256": expected_inventory["entriesSha256"],
            "entryCount": expected_inventory["entryCount"],
        },
        "schema": {
            "path": paths["schema"],
            "sha256": _sha256_hex_file(POLICY_ROOT / paths["schema"]),
        },
    }
    if inputs != expected_inputs:
        raise PublicationPolicyError("review baseline inputs differ from trusted policy")

    inventory_check, warning_check = _validate_test_results(
        results,
        expected_inventory=expected_inventory,
        warning_policy=config["warningPolicy"],
    )
    if evidence.get("tests") != results:
        raise PublicationPolicyError("review baseline embedded results differ from their file")
    if evidence.get("testAcceptance") != {
        "inventory": inventory_check,
        "warnings": warning_check,
    }:
        raise PublicationPolicyError("review baseline acceptance claims are inconsistent")
    _validate_environment(
        _object(evidence.get("environment"), "review baseline environment"),
        config=config,
        source_run_id=source_run_id,
        source_run_attempt=source_run_attempt,
    )

    steps = _array(evidence.get("steps"), "review baseline steps")
    if steps != _expected_review_steps(config):
        raise PublicationPolicyError("review baseline steps differ from trusted policy")

    _validate_produced_artifact_binding(evidence.get("producedArtifacts"), results_path)
    if evidence.get("producedArtifactsNote") != (
        "The evidence envelope excludes its own digest to avoid recursive "
        "self-reference. Its raw digest is recorded by the comparison proof."
    ):
        raise PublicationPolicyError("review baseline produced-artifact note differs")
    expected_verified = [
        {"path": path, "sha256": _sha256_hex_file(POLICY_ROOT / path)}
        for path in config["verifiedArtifacts"]
    ]
    if evidence.get("verifiedArtifacts") != expected_verified:
        raise PublicationPolicyError("review baseline verified artifacts differ")


def _validate_producer_comparison(
    comparison: dict[str, Any],
    *,
    input_root: Path,
    loaded: dict[str, tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    review_policy = _review_policy_module()
    normalized: dict[str, bytes] = {}
    for run in ("run-1", "run-2"):
        try:
            normalized[run] = review_policy._normalised_evidence(loaded[run][1])
        except ValueError as exc:
            raise PublicationPolicyError(
                "producer comparison input cannot be normalized"
            ) from exc
    expected = {
        "schemaVersion": review_policy.COMPARISON_SCHEMA,
        "normalizationPolicy": review_policy._normalization_policy(),
        "left": {
            "rawSha256": _sha256_hex_file(
                input_root
                / "review-baseline/run-1/review-baseline-evidence.json"
            ),
            "normalizedSha256": review_policy._sha256_bytes(
                normalized["run-1"]
            ),
        },
        "right": {
            "rawSha256": _sha256_hex_file(
                input_root
                / "review-baseline/run-2/review-baseline-evidence.json"
            ),
            "normalizedSha256": review_policy._sha256_bytes(
                normalized["run-2"]
            ),
        },
        "equivalent": True,
        "differenceJsonPointers": [],
    }
    if normalized["run-1"] != normalized["run-2"] or comparison != expected:
        raise PublicationPolicyError(
            "producer comparison differs from validated source evidence"
        )


def stage_conformance_evidence(
    *,
    input_root: Path,
    output_root: Path,
    source_api_url: str,
    source_repository: str,
    source_token: str,
    source_commit: str,
    source_run_id: int,
    source_run_attempt: int,
    source_response_factory: ResponseFactory | None = None,
) -> None:
    """Rebuild authoritative conformance claims with trusted policy code."""

    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise PublicationPolicyError("source commit is not a full lowercase SHA")
    if source_run_id <= 0 or source_run_attempt != 1:
        raise PublicationPolicyError("source run coordinates are not exact")
    platform_source_name = validate_conformance_inventory(
        input_root,
        authoritative=False,
    )
    review_policy = _review_policy_module()
    config = _read_json_object(
        POLICY_ROOT / "conformance/review_baseline_config.json",
        "trusted review baseline config",
    )
    paths = _object(config.get("paths"), "trusted review baseline paths")
    source_inventory_payload = _download_authenticated_source_file(
        api_url=source_api_url,
        repository=source_repository,
        source_commit=source_commit,
        source_path=paths.get("testInventory"),
        token=source_token,
        response_factory=source_response_factory,
    )
    expected_inventory = _load_source_test_inventory(
        source_inventory_payload,
        config=config,
    )
    source_inventory_sha256 = hashlib.sha256(source_inventory_payload).hexdigest()
    loaded: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for run in ("run-1", "run-2"):
        run_root = input_root / "review-baseline" / run
        results_path = run_root / "kernel-test-results.json"
        evidence_path = run_root / "review-baseline-evidence.json"
        results = _read_json_object(results_path, f"{run} kernel test results")
        evidence = _read_json_object(evidence_path, f"{run} review baseline evidence")
        _validate_baseline_evidence(
            evidence,
            results=results,
            results_path=results_path,
            config=config,
            expected_inventory=expected_inventory,
            source_inventory_sha256=source_inventory_sha256,
            source_commit=source_commit,
            source_run_id=source_run_id,
            source_run_attempt=source_run_attempt,
        )
        loaded[run] = (results, evidence)

    producer_comparison = _read_json_object(
        input_root / "review-baseline/equivalence.json",
        "producer review baseline comparison",
    )
    _validate_producer_comparison(
        producer_comparison,
        input_root=input_root,
        loaded=loaded,
    )

    root = _fresh_output_root(output_root)
    for run in ("run-1", "run-2"):
        target = root / "review-baseline" / run
        results, source_evidence = loaded[run]
        staged_results = target / "kernel-test-results.json"
        _write_canonical_json(staged_results, results)
        staged_evidence = copy.deepcopy(source_evidence)
        staged_evidence["producedArtifacts"] = _produced_artifact_binding(
            staged_results
        )
        staged_evidence_path = target / "review-baseline-evidence.json"
        _write_canonical_json(staged_evidence_path, staged_evidence)
        _validate_baseline_evidence(
            staged_evidence,
            results=results,
            results_path=staged_results,
            config=config,
            expected_inventory=expected_inventory,
            source_inventory_sha256=source_inventory_sha256,
            source_commit=source_commit,
            source_run_id=source_run_id,
            source_run_attempt=source_run_attempt,
        )
    comparison_path = root / "review-baseline" / "equivalence.json"
    try:
        comparison_result = review_policy.compare_evidence(
            str(root / "review-baseline/run-1/review-baseline-evidence.json"),
            str(root / "review-baseline/run-2/review-baseline-evidence.json"),
            str(comparison_path),
        )
    except (OSError, ValueError) as exc:
        raise PublicationPolicyError("trusted review baseline comparison failed") from exc
    if comparison_result != 0:
        raise PublicationPolicyError("trusted review baseline comparison is not equivalent")
    comparison_document = _read_json_object(
        comparison_path,
        "trusted review baseline comparison",
    )
    try:
        comparison_path.unlink()
    except OSError as exc:
        raise PublicationPolicyError(
            "trusted review baseline comparison cannot be finalized"
        ) from exc
    _write_canonical_json(comparison_path, comparison_document)

    first_results = loaded["run-1"][0]
    outcomes = _array(
        _object(first_results["execution"], "trusted review execution")["outcomes"],
        "trusted review outcomes",
    )
    platform_results = [
        {"test": item["nodeid"], "outcome": "passed"}
        for item in outcomes
        if item["sourcePath"] == "kernel/tests/test_conformance.py"
    ]
    if not platform_results:
        raise PublicationPolicyError("platform test inventory is empty")
    platform_source = _read_json_object(
        input_root / "platform-evidence" / platform_source_name,
        "provisional platform evidence",
    )
    _exact_keys(
        platform_source,
        {"suite", "executed", "executedAt", "runtimeVersion", "exitStatus", "allPassed", "results", "details", "honestyNote"},
        "provisional platform evidence",
    )
    provisional_results = _array(platform_source.get("results"), "provisional platform results")
    observed_platform: list[dict[str, str]] = []
    for result in provisional_results:
        item = _object(result, "provisional platform result")
        _exact_keys(item, {"test", "outcome", "durationSeconds"}, "provisional platform result")
        duration = item.get("durationSeconds")
        if (
            item.get("outcome") != "passed"
            or not isinstance(duration, (int, float))
            or isinstance(duration, bool)
            or duration < 0
        ):
            raise PublicationPolicyError("provisional platform result did not pass")
        observed_platform.append({"test": item["test"], "outcome": "passed"})
    if (
        platform_source.get("suite") != PLATFORM_TEST_SUITE
        or platform_source.get("executed") is not True
        or platform_source.get("exitStatus") != 0
        or platform_source.get("allPassed") is not True
        or not isinstance(platform_source.get("details"), dict)
        or not isinstance(platform_source.get("honestyNote"), str)
        or not platform_source.get("honestyNote")
        or observed_platform != platform_results
    ):
        raise PublicationPolicyError("provisional platform evidence is inconsistent")
    _write_canonical_json(
        root / "platform-evidence" / PLATFORM_PUBLICATION_FILE,
        {
            "allPassed": True,
            "results": platform_results,
            "schemaVersion": PLATFORM_PUBLICATION_SCHEMA,
            "source": {
                "commit": source_commit,
                "runAttempt": source_run_attempt,
                "runId": source_run_id,
            },
            "suite": PLATFORM_TEST_SUITE,
        },
    )
    expected = {
        *(f"review-baseline/{name}" for name in REVIEW_BASELINE_FILES),
        f"platform-evidence/{PLATFORM_PUBLICATION_FILE}",
    }
    if _regular_file_inventory(root) != frozenset(expected):
        raise PublicationPolicyError("trusted conformance staging inventory is not exact")


def validate_native_claims(
    root: Path,
    *,
    platform: str,
    source_commit: str,
) -> None:
    """Bind the published reproducibility report to both installed file sets."""

    native_policy = _native_policy_module()
    report = _read_json_object(root / "reproducibility.json", "native reproducibility")
    _exact_keys(
        report,
        {"schema", "platform", "source_commit", "child_digest", "config_digest", "artifacts"},
        "native reproducibility",
    )
    if (
        report.get("schema") != "ofarm.native-reproducibility-evidence.v1"
        or report.get("platform") != platform
        or report.get("source_commit") != source_commit
        or SHA256.fullmatch(str(report.get("child_digest"))) is None
        or SHA256.fullmatch(str(report.get("config_digest"))) is None
    ):
        raise PublicationPolicyError("native reproducibility identity is inconsistent")
    expected_artifacts = _array(report.get("artifacts"), "native reproducibility artifacts")
    observed_sets: list[list[dict[str, Any]]] = []
    with tempfile.TemporaryDirectory(prefix="ofarm-native-claims-") as directory:
        scratch = Path(directory)
        for build in ("first", "second"):
            _extract_installed_artifacts(
                root / f"{build}-artifacts.tar",
                scratch / build,
                native_policy,
            )
            identities: list[dict[str, Any]] = []
            for name, (maximum, expected_mode) in (
                native_policy.ARTIFACT_CONTRACTS.items()
            ):
                path = scratch / build / name
                try:
                    file_stat = path.stat(follow_symlinks=False)
                    if (
                        not stat.S_ISREG(file_stat.st_mode)
                        or not 0 < file_stat.st_size <= maximum
                        or format(stat.S_IMODE(file_stat.st_mode), "04o")
                        != expected_mode
                    ):
                        raise PublicationPolicyError(
                            "published native artifact "
                            f"{build}/{name} violates its contract"
                        )
                    data = path.read_bytes()
                except OSError as exc:
                    raise PublicationPolicyError(
                        f"published native artifact {build}/{name} is unreadable"
                    ) from exc
                identities.append(
                    {
                        "name": name,
                        "mode": expected_mode,
                        "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
                        "size": len(data),
                    }
                )
            observed_sets.append(identities)
    if observed_sets[0] != expected_artifacts or observed_sets[1] != expected_artifacts:
        raise PublicationPolicyError(
            "published native files differ from trusted reproducibility"
        )


def _extract_installed_artifacts(
    archive_path: Path,
    output_directory: Path,
    native_policy: Any,
) -> None:
    expected = native_policy.ARTIFACT_CONTRACTS
    output_directory.mkdir(parents=True, exist_ok=False)
    try:
        archive_stat = archive_path.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(archive_stat.st_mode)
            or not 0 < archive_stat.st_size <= MAX_INSTALLED_ARCHIVE_BYTES
        ):
            raise PublicationPolicyError(
                "installed-artifact archive is not bounded regular data"
            )
        with tarfile.open(archive_path, mode="r:") as archive:
            observed: set[str] = set()
            for member in archive:
                if len(observed) >= len(expected):
                    raise PublicationPolicyError(
                        "installed-artifact archive inventory is not exact"
                    )
                if member.name in observed or member.name not in expected:
                    raise PublicationPolicyError(
                        "installed-artifact archive names are not exact"
                    )
                observed.add(member.name)
                maximum, expected_mode = expected[member.name]
                if (
                    not member.isreg()
                    or not 0 < member.size <= maximum
                    or format(member.mode, "04o") != expected_mode
                    or member.uid != 0
                    or member.gid != 0
                    or member.mtime != 0
                    or member.pax_headers
                ):
                    raise PublicationPolicyError(
                        f"installed-artifact archive entry violates policy: {member.name}"
                    )
                source = archive.extractfile(member)
                if source is None:
                    raise PublicationPolicyError(
                        "installed-artifact archive entry is unreadable"
                    )
                destination = output_directory / member.name
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                flags |= getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(destination, flags, int(expected_mode, 8))
                os.fchmod(descriptor, int(expected_mode, 8))
                written = 0
                try:
                    with source, os.fdopen(descriptor, "wb") as output:
                        descriptor = -1
                        while True:
                            chunk = source.read(DOWNLOAD_CHUNK_BYTES)
                            if not chunk:
                                break
                            written += len(chunk)
                            if written > maximum:
                                raise PublicationPolicyError(
                                    "installed-artifact archive entry exceeds its limit"
                                )
                            output.write(chunk)
                finally:
                    if descriptor >= 0:
                        os.close(descriptor)
                if written != member.size:
                    raise PublicationPolicyError(
                        "installed-artifact archive entry size differs"
                    )
            if observed != set(expected):
                raise PublicationPolicyError(
                    "installed-artifact archive names are not exact"
                )
    except (OSError, tarfile.TarError) as exc:
        raise PublicationPolicyError("installed-artifact archive is malformed") from exc


def _write_installed_artifacts_archive(
    source_directory: Path,
    archive_path: Path,
    native_policy: Any,
) -> None:
    """Write a deterministic mode-bearing archive from trusted extracted files."""

    contracts = native_policy.ARTIFACT_CONTRACTS
    if _regular_file_inventory(source_directory) != frozenset(contracts):
        raise PublicationPolicyError(
            "trusted installed-artifact source inventory is not exact"
        )
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(archive_path, flags, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as raw_archive:
            descriptor = -1
            with tarfile.open(
                fileobj=raw_archive,
                mode="w:",
                format=tarfile.USTAR_FORMAT,
            ) as archive:
                for name in sorted(contracts):
                    maximum, expected_mode = contracts[name]
                    source_path = source_directory / name
                    source_stat = source_path.stat(follow_symlinks=False)
                    if (
                        not stat.S_ISREG(source_stat.st_mode)
                        or not 0 < source_stat.st_size <= maximum
                        or format(stat.S_IMODE(source_stat.st_mode), "04o")
                        != expected_mode
                    ):
                        raise PublicationPolicyError(
                            "trusted installed-artifact source violates its contract"
                        )
                    member = tarfile.TarInfo(name)
                    member.size = source_stat.st_size
                    member.mode = int(expected_mode, 8)
                    member.uid = 0
                    member.gid = 0
                    member.uname = ""
                    member.gname = ""
                    member.mtime = 0
                    with source_path.open("rb") as source:
                        archive.addfile(member, source)
        archive_stat = archive_path.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(archive_stat.st_mode)
            or not 0 < archive_stat.st_size <= MAX_INSTALLED_ARCHIVE_BYTES
        ):
            raise PublicationPolicyError(
                "trusted installed-artifact archive is not bounded regular data"
            )
    except (OSError, tarfile.TarError) as exc:
        raise PublicationPolicyError(
            "trusted installed-artifact archive cannot be written"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _remove_installed_artifact_directory(
    directory: Path,
    native_policy: Any,
) -> None:
    try:
        for name in native_policy.ARTIFACT_CONTRACTS:
            (directory / name).unlink()
        directory.rmdir()
    except OSError as exc:
        raise PublicationPolicyError(
            "trusted installed-artifact staging cannot be finalized"
        ) from exc


def stage_native_evidence(
    *,
    input_root: Path,
    output_root: Path,
    platform: str,
    source_commit: str,
    containerfile: Path,
    builder_id: str,
) -> None:
    """Recompute native reproducibility and attestations into a clean root."""

    validate_native_inventory(input_root, authoritative=False)
    native_policy = _native_policy_module()
    root = _fresh_output_root(output_root)
    for build in ("first", "second"):
        _extract_installed_artifacts(
            input_root / f"{build}-artifacts.tar",
            root / build,
            native_policy,
        )
    _copy_regular_file(
        input_root / "ofarm-ed25519.oci.tar",
        root / "ofarm-ed25519.oci.tar",
        maximum=native_policy.MAX_OCI_ARCHIVE_BYTES,
    )
    try:
        native_policy.compare_builds(
            first_archive=input_root / "first-image.docker.tar",
            second_archive=input_root / "second-image.docker.tar",
            first_artifacts=root / "first",
            second_artifacts=root / "second",
            platform=platform,
            source_commit=source_commit,
            output=root / "reproducibility.json",
        )
        native_policy.collect_oci_evidence(
            archive_path=root / "ofarm-ed25519.oci.tar",
            reproducibility_path=root / "reproducibility.json",
            platform=platform,
            source_commit=source_commit,
            containerfile_path=containerfile,
            builder_id=builder_id,
            output_directory=root / "attestations",
        )
    except (OSError, native_policy.NativeEvidenceError) as exc:
        raise PublicationPolicyError("trusted native claim reconstruction failed") from exc
    if _sha256_hex_file(input_root / "reproducibility.json") != _sha256_hex_file(
        root / "reproducibility.json"
    ):
        raise PublicationPolicyError(
            "producer reproducibility differs from trusted comparison"
        )
    for name in (
        "oci-evidence.json",
        "sbom.spdx.in-toto.json",
        "provenance.slsa-v0.2.in-toto.json",
    ):
        if _sha256_hex_file(input_root / "attestations" / name) != _sha256_hex_file(
            root / "attestations" / name
        ):
            raise PublicationPolicyError(
                f"producer native {name} differs from trusted reconstruction"
            )
    for build in ("first", "second"):
        _write_installed_artifacts_archive(
            root / build,
            root / f"{build}-artifacts.tar",
            native_policy,
        )
    for build in ("first", "second"):
        _remove_installed_artifact_directory(root / build, native_policy)
    validate_native_claims(root, platform=platform, source_commit=source_commit)
    if _regular_file_inventory(root) != NATIVE_AUTHORITATIVE_FILES:
        raise PublicationPolicyError("trusted native staging inventory is not exact")


def validate_conformance_inventory(root: Path, *, authoritative: bool) -> str:
    """Require the exact review-baseline and single platform evidence file set."""

    metadata = TRUSTED_METADATA_FILES if authoritative else frozenset()
    if authoritative:
        platform_name = PLATFORM_PUBLICATION_FILE
    else:
        platform_root = root / "platform-evidence"
        platform_files = _regular_file_inventory(platform_root)
        variable = [
            name for name in platform_files if PLATFORM_EVIDENCE_NAME.fullmatch(name)
        ]
        if len(variable) != 1:
            raise PublicationPolicyError("platform evidence variable file is not exact")
        platform_name = variable[0]
    expected = {
        *(f"review-baseline/{name}" for name in REVIEW_BASELINE_FILES | metadata),
        *(f"platform-evidence/{name}" for name in metadata),
        f"platform-evidence/{platform_name}",
    }
    observed = _regular_file_inventory(root)
    if observed != frozenset(expected):
        raise PublicationPolicyError("conformance evidence file inventory is not exact")
    return platform_name


def validate_native_inventory(root: Path, *, authoritative: bool) -> None:
    """Require the exact native evidence file set for one architecture."""

    expected = (
        NATIVE_AUTHORITATIVE_FILES | TRUSTED_METADATA_FILES
        if authoritative
        else NATIVE_PROVISIONAL_FILES
    )
    if _regular_file_inventory(root) != expected:
        raise PublicationPolicyError("native evidence file inventory is not exact")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download")
    download.add_argument("--api-url", required=True)
    download.add_argument("--repository", required=True)
    download.add_argument(
        "--artifact-name",
        choices=tuple(PROVISIONAL_ARTIFACT_LIMITS),
        required=True,
    )
    download.add_argument("--artifact-id", type=int, required=True)
    download.add_argument("--artifact-digest", required=True)
    download.add_argument("--output-directory", type=Path, required=True)
    conformance = commands.add_parser("validate-conformance")
    conformance.add_argument("--root", type=Path, required=True)
    conformance.add_argument("--authoritative", action="store_true")
    native = commands.add_parser("validate-native")
    native.add_argument("--root", type=Path, required=True)
    native.add_argument("--authoritative", action="store_true")
    native_claims = commands.add_parser("validate-native-claims")
    native_claims.add_argument("--root", type=Path, required=True)
    native_claims.add_argument("--platform", required=True)
    native_claims.add_argument("--source-commit", required=True)
    stage_conformance = commands.add_parser("stage-conformance")
    stage_conformance.add_argument("--input-root", type=Path, required=True)
    stage_conformance.add_argument("--output-root", type=Path, required=True)
    stage_conformance.add_argument("--source-api-url", required=True)
    stage_conformance.add_argument("--source-repository", required=True)
    stage_conformance.add_argument("--source-commit", required=True)
    stage_conformance.add_argument("--source-run-id", type=int, required=True)
    stage_conformance.add_argument("--source-run-attempt", type=int, required=True)
    stage_native = commands.add_parser("stage-native")
    stage_native.add_argument("--input-root", type=Path, required=True)
    stage_native.add_argument("--output-root", type=Path, required=True)
    stage_native.add_argument("--platform", required=True)
    stage_native.add_argument("--source-commit", required=True)
    stage_native.add_argument("--containerfile", type=Path, required=True)
    stage_native.add_argument("--builder-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "download":
            download_and_extract_artifact(
                api_url=args.api_url,
                repository=args.repository,
                artifact_name=args.artifact_name,
                artifact_id=args.artifact_id,
                expected_digest=args.artifact_digest,
                output_directory=args.output_directory,
                token=os.environ.get("OFARM_ARTIFACT_TOKEN", ""),
            )
        elif args.command == "validate-conformance":
            validate_conformance_inventory(
                args.root,
                authoritative=args.authoritative,
            )
        elif args.command == "validate-native":
            validate_native_inventory(
                args.root,
                authoritative=args.authoritative,
            )
        elif args.command == "validate-native-claims":
            validate_native_claims(
                args.root,
                platform=args.platform,
                source_commit=args.source_commit,
            )
        elif args.command == "stage-conformance":
            stage_conformance_evidence(
                input_root=args.input_root,
                output_root=args.output_root,
                source_api_url=args.source_api_url,
                source_repository=args.source_repository,
                source_token=os.environ.get("OFARM_SOURCE_INPUT_TOKEN", ""),
                source_commit=args.source_commit,
                source_run_id=args.source_run_id,
                source_run_attempt=args.source_run_attempt,
            )
        else:
            stage_native_evidence(
                input_root=args.input_root,
                output_root=args.output_root,
                platform=args.platform,
                source_commit=args.source_commit,
                containerfile=args.containerfile,
                builder_id=args.builder_id,
            )
    except PublicationPolicyError as exc:
        print(f"evidence publication policy refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
