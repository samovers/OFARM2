#!/usr/bin/env python3
"""Generate the retained Python image file manifest from verified OCI inputs.

The command is an explicit maintenance tool.  It never contacts a registry:
callers supply an already applied root filesystem plus the exact OCI index,
platform manifest, configuration, and compressed layers.  Every supplied OCI
object is content-address verified before any repository output is written.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "conformance" / "python_runtime_image_manifest.json"
SCHEMA_VERSION = "ofarm.python-runtime-image-manifest.local.v1"
IMAGE_REFERENCE = "docker.io/library/python:3.12.13-bookworm"
IMAGE_INDEX_DIGEST = (
    "sha256:c36262cd12ed3eb4c32146f5268ea5037e04c688ccf32cdb04b6084671845541"
)
PLATFORM_MANIFEST_DIGEST = (
    "sha256:bf530f921d806e9a604ae776d1c578e7465befc4d88a3b9d6cf9ee1db7d527ca"
)
PYTHON_VERSION = "3.12.13"
PLATFORM = {"architecture": "amd64", "os": "linux"}
STANDARD_ROOTS = (Path("usr/local/lib/python3.12"),)
PYTHON_EXECUTABLE = Path("usr/local/bin/python3.12")
SHARED_LIBRARY = Path("usr/local/lib/libpython3.12.so.1.0")
REQUIRED_EXECUTABLES = (Path("usr/bin/git"),)
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ManifestError(RuntimeError):
    """OCI input or extracted runtime state is not the pinned image."""


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _json_object(path: Path) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ManifestError(f"OCI JSON must be an object: {path}")
    return raw, value


def _file_entry(rootfs: Path, relative: Path) -> dict:
    path = rootfs / relative
    if path.is_symlink() or not path.is_file():
        raise ManifestError(f"runtime manifest path is not a regular file: /{relative}")
    raw = path.read_bytes()
    return {
        "path": "/" + relative.as_posix(),
        "contentDigest": _sha256(raw),
        "byteLength": len(raw),
    }


def _standard_tree(rootfs: Path, relative_root: Path) -> tuple[list[dict], list[str]]:
    root = rootfs / relative_root
    if root.is_symlink() or not root.is_dir():
        raise ManifestError(f"standard-library root is absent: /{relative_root}")
    files: list[dict] = []
    directories: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in {"__pycache__", "site-packages", "dist-packages"}
               for part in relative.parts):
            continue
        if path.is_symlink():
            raise ManifestError(f"standard-library symlink is forbidden: /{path.relative_to(rootfs)}")
        if path.is_dir():
            directories.append(relative.as_posix())
            continue
        if not path.is_file():
            continue
        entry = _file_entry(rootfs, path.relative_to(rootfs))
        entry["relativePath"] = relative.as_posix()
        files.append(entry)
    if not files:
        raise ManifestError(f"standard-library root is empty: /{relative_root}")
    return files, directories


def _native_files(rootfs: Path) -> list[dict]:
    files = []
    for path in sorted(rootfs.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        name = path.name
        if not (name.endswith(".so") or ".so." in name):
            continue
        files.append(_file_entry(rootfs, path.relative_to(rootfs)))
    if not files:
        raise ManifestError("pinned image has no native shared-library files")
    return files


def _loader_configuration(rootfs: Path) -> tuple[list[dict], list[str]]:
    candidates = [Path("etc/ld.so.cache"), Path("etc/ld.so.conf")]
    directory = rootfs / "etc" / "ld.so.conf.d"
    if directory.is_dir() and not directory.is_symlink():
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ManifestError(
                    f"native loader configuration symlink is forbidden: {path}")
            if path.is_file():
                candidates.append(path.relative_to(rootfs))
    files = [_file_entry(rootfs, path) for path in candidates]
    absent = ["/etc/ld.so.preload"]
    if any((rootfs / path.lstrip("/")).exists() for path in absent):
        raise ManifestError("pinned image unexpectedly enables ld.so.preload")
    return files, absent


def _uncompressed_layer_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _safe_member_path(name: str) -> Path:
    while name.startswith("./"):
        name = name[2:]
    path = Path(name)
    if (not name or path.is_absolute() or "\\" in name
            or any(part in {"", ".", ".."} for part in path.parts)):
        raise ManifestError(f"OCI layer contains an unsafe path: {name!r}")
    return path


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _normalise_virtual_parts(base: list[str], additions: tuple[str, ...]) -> list[str]:
    result = list(base)
    for part in additions:
        if part in {"", "."}:
            continue
        if part == "..":
            if not result:
                raise ManifestError("OCI link escapes the image root")
            result.pop()
        else:
            result.append(part)
    return result


def _overlay_path(
    rootfs: Path,
    relative: Path,
    *,
    follow_final: bool,
) -> Path:
    pending = list(relative.parts)
    resolved: list[str] = []
    followed = 0
    while pending:
        part = pending.pop(0)
        if part in {"", "."}:
            continue
        if part == "..":
            if not resolved:
                raise ManifestError("OCI link escapes the image root")
            resolved.pop()
            continue
        candidate = rootfs.joinpath(*resolved, part)
        if candidate.is_symlink() and (follow_final or pending):
            followed += 1
            if followed > 40:
                raise ManifestError("OCI layer contains a symlink loop")
            target = Path(candidate.readlink())
            base = [] if target.is_absolute() else resolved
            target_parts = target.parts[1:] if target.is_absolute() else target.parts
            _normalise_virtual_parts(base, target_parts)
            resolved = list(base)
            pending = [*target_parts, *pending]
            continue
        resolved.append(part)
    target = rootfs.joinpath(*resolved)
    try:
        target.relative_to(rootfs)
    except ValueError as exc:
        raise ManifestError("OCI member escapes the image root") from exc
    return target


def _ensure_overlay_parent(rootfs: Path, relative: Path) -> Path:
    current = Path()
    for part in relative.parts:
        current /= part
        target = _overlay_path(rootfs, current, follow_final=True)
        if target.is_symlink():
            target = _overlay_path(rootfs, current, follow_final=True)
        if target.exists() and not target.is_dir():
            _remove_path(target)
        target.mkdir(parents=True, exist_ok=True)
    return _overlay_path(rootfs, relative, follow_final=True)


def _validate_symlink_target(parent: Path, raw_target: str) -> None:
    target = Path(raw_target)
    base = [] if target.is_absolute() else list(parent.parts)
    parts = target.parts[1:] if target.is_absolute() else target.parts
    _normalise_virtual_parts(base, parts)


def _apply_layer(rootfs: Path, layer_path: Path) -> None:
    # OCI whiteouts describe lower-layer removal and are applied before the
    # current layer's ordinary members.  The archive itself is already fixed
    # by both its compressed digest and uncompressed diff_id.
    with tarfile.open(layer_path, "r:gz") as archive:
        members = archive.getmembers()
    for member in members:
        relative = _safe_member_path(member.name)
        name = relative.name
        if name == ".wh..wh..opq":
            directory = _overlay_path(
                rootfs, relative.parent, follow_final=True)
            if directory.is_dir() and not directory.is_symlink():
                for child in directory.iterdir():
                    _remove_path(child)
        elif name.startswith(".wh."):
            target_name = name.removeprefix(".wh.")
            if target_name in {"", ".", ".."}:
                raise ManifestError("OCI layer contains an unsafe whiteout")
            _ensure_overlay_parent(rootfs, relative.parent)
            target = _overlay_path(
                rootfs, relative.parent / target_name, follow_final=False)
            _remove_path(target)
    hardlinks = []
    with tarfile.open(layer_path, "r:gz") as archive:
        for member in archive:
            relative = _safe_member_path(member.name)
            if relative.name.startswith(".wh."):
                continue
            parent = _ensure_overlay_parent(rootfs, relative.parent)
            target = _overlay_path(rootfs, relative, follow_final=False)
            if member.isdir():
                if target.is_symlink() or target.is_file():
                    _remove_path(target)
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                _remove_path(target)
                source = archive.extractfile(member)
                if source is None:
                    raise ManifestError(f"OCI regular file has no bytes: {member.name}")
                target.write_bytes(source.read())
            elif member.issym():
                _validate_symlink_target(relative.parent, member.linkname)
                _remove_path(target)
                target.symlink_to(member.linkname)
            elif member.islnk():
                hardlinks.append((relative, _safe_member_path(member.linkname)))
            else:
                raise ManifestError(
                    f"OCI layer contains an unsupported member type: {member.name}")
            del parent
    pending = hardlinks
    while pending:
        remaining = []
        progressed = False
        for target_relative, source_relative in pending:
            source = _overlay_path(rootfs, source_relative, follow_final=True)
            if source.is_file() and not source.is_symlink():
                _ensure_overlay_parent(rootfs, target_relative.parent)
                target = _overlay_path(
                    rootfs, target_relative, follow_final=False)
                _remove_path(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.hardlink_to(source)
                progressed = True
            else:
                remaining.append((target_relative, source_relative))
        if not progressed:
            raise ManifestError("OCI layer contains an unresolved hardlink")
        pending = remaining


def build_manifest(
    index_path: Path,
    platform_manifest_path: Path,
    config_path: Path,
    layer_paths: list[Path],
) -> dict:
    index_raw, index = _json_object(index_path)
    manifest_raw, platform_manifest = _json_object(platform_manifest_path)
    config_raw, config = _json_object(config_path)
    if _sha256(index_raw) != IMAGE_INDEX_DIGEST:
        raise ManifestError("OCI index bytes do not equal the retained image digest")
    if _sha256(manifest_raw) != PLATFORM_MANIFEST_DIGEST:
        raise ManifestError("OCI platform manifest bytes are not retained")
    if (index.get("mediaType") != "application/vnd.oci.image.index.v1+json"
            or platform_manifest.get("mediaType") !=
            "application/vnd.oci.image.manifest.v1+json"):
        raise ManifestError("OCI image uses an unsupported manifest media type")
    selected = [
        item for item in index.get("manifests", [])
        if item.get("platform") == PLATFORM
    ]
    if len(selected) != 1 or selected[0].get("digest") != PLATFORM_MANIFEST_DIGEST:
        raise ManifestError("OCI index does not select the retained linux/amd64 manifest")
    config_descriptor = platform_manifest.get("config") or {}
    if (config_descriptor.get("mediaType") !=
                "application/vnd.oci.image.config.v1+json"
            or not _DIGEST_RE.fullmatch(config_descriptor.get("digest", ""))
            or config_descriptor.get("size") != len(config_raw)
            or _sha256(config_raw) != config_descriptor["digest"]
            or config.get("architecture") != PLATFORM["architecture"]
            or config.get("os") != PLATFORM["os"]):
        raise ManifestError("OCI image configuration is not the selected platform config")
    environment = config.get("config", {}).get("Env", [])
    if f"PYTHON_VERSION={PYTHON_VERSION}" not in environment:
        raise ManifestError("OCI image configuration has another Python version")

    expected_layers = platform_manifest.get("layers")
    diff_ids = (config.get("rootfs") or {}).get("diff_ids")
    if (not isinstance(expected_layers, list)
            or not isinstance(diff_ids, list)
            or len(layer_paths) != len(expected_layers)
            or len(layer_paths) != len(diff_ids)):
        raise ManifestError("supplied OCI layer set is not exact")
    layers = []
    for path, descriptor in zip(layer_paths, expected_layers):
        raw = path.read_bytes()
        if (descriptor.get("mediaType") !=
                "application/vnd.oci.image.layer.v1.tar+gzip"
                or descriptor.get("digest") != _sha256(raw)
                or descriptor.get("size") != len(raw)
                or _uncompressed_layer_digest(path) != diff_ids[len(layers)]):
            raise ManifestError(f"OCI layer does not match its descriptor: {path}")
        layers.append({
            "digest": descriptor["digest"],
            "byteLength": descriptor["size"],
        })

    with tempfile.TemporaryDirectory(prefix="ofarm-runtime-image-") as temporary:
        rootfs = Path(temporary)
        for path in layer_paths:
            _apply_layer(rootfs, path)
        roots = []
        for relative in STANDARD_ROOTS:
            files, directories = _standard_tree(rootfs, relative)
            roots.append({
                "path": "/" + relative.as_posix(),
                "directories": directories,
                "files": files,
            })
        loader_files, absent_paths = _loader_configuration(rootfs)
        python = {
            "version": PYTHON_VERSION,
            "executable": _file_entry(rootfs, PYTHON_EXECUTABLE),
            "sharedLibrary": _file_entry(rootfs, SHARED_LIBRARY),
            "standardLibraryRoots": roots,
            "nativeFiles": _native_files(rootfs),
            "loaderConfigurationFiles": loader_files,
            "requiredAbsentPaths": absent_paths,
            "requiredExecutables": [
                _file_entry(rootfs, path) for path in REQUIRED_EXECUTABLES
            ],
        }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "image": {
            "reference": IMAGE_REFERENCE,
            "indexDigest": IMAGE_INDEX_DIGEST,
            "platform": "linux/amd64",
            "platformManifestDigest": PLATFORM_MANIFEST_DIGEST,
            "configDigest": config_descriptor["digest"],
            "layers": layers,
        },
        "python": python,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--platform-manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--layer", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    document = build_manifest(
        args.index, args.platform_manifest, args.config, args.layer)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output} with "
          f"{sum(len(root['files']) for root in document['python']['standardLibraryRoots'])} "
          f"standard files and {len(document['python']['nativeFiles'])} native files")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, ManifestError) as exc:
        raise SystemExit(f"runtime image manifest generation failed: {exc}") from exc
