#!/usr/bin/env python3
"""Trusted download, extraction, and inventory policy for published evidence."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath


SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
PLATFORM_EVIDENCE_NAME = re.compile(
    r"platform_mvp_results_[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z[.]json"
)
GITHUB_API_VERSION = "2026-03-10"
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
MAX_ZIP_ENTRIES = 256
PROVISIONAL_ARTIFACT_LIMITS = {
    "conformance-provisional": 512_000_000,
    "native-verifier-amd64-provisional": 700_000_000,
    "native-verifier-arm64-provisional": 700_000_000,
}
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
NATIVE_EVIDENCE_FILES = frozenset(
    {
        "address.log",
        "attestations/oci-evidence.json",
        "attestations/provenance.slsa-v0.2.in-toto.json",
        "attestations/sbom.spdx.in-toto.json",
        "attested-metadata.json",
        "buildx-version.txt",
        "first/libsodium.a",
        "first/ofarm_ed25519--1.0.sql",
        "first/ofarm_ed25519.control",
        "first/ofarm_ed25519.so",
        "invalid-sanitizer.log",
        "ofarm-ed25519.oci.tar",
        "reproducibility.json",
        "second/libsodium.a",
        "second/ofarm_ed25519--1.0.sql",
        "second/ofarm_ed25519.control",
        "second/ofarm_ed25519.so",
        "undefined.log",
    }
)
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


def validate_conformance_inventory(root: Path, *, authoritative: bool) -> str:
    """Require the exact review-baseline and single platform evidence file set."""

    metadata = TRUSTED_METADATA_FILES if authoritative else frozenset()
    platform_root = root / "platform-evidence"
    platform_files = _regular_file_inventory(platform_root)
    variable = [name for name in platform_files if PLATFORM_EVIDENCE_NAME.fullmatch(name)]
    if len(variable) != 1:
        raise PublicationPolicyError("platform evidence variable file is not exact")
    expected = {
        *(f"review-baseline/{name}" for name in REVIEW_BASELINE_FILES | metadata),
        *(f"platform-evidence/{name}" for name in metadata),
        f"platform-evidence/{variable[0]}",
    }
    observed = _regular_file_inventory(root)
    if observed != frozenset(expected):
        raise PublicationPolicyError("conformance evidence file inventory is not exact")
    return variable[0]


def validate_native_inventory(root: Path, *, authoritative: bool) -> None:
    """Require the exact native evidence file set for one architecture."""

    expected = NATIVE_EVIDENCE_FILES | (
        TRUSTED_METADATA_FILES if authoritative else frozenset()
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
        else:
            validate_native_inventory(
                args.root,
                authoritative=args.authoritative,
            )
    except PublicationPolicyError as exc:
        print(f"evidence publication policy refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
