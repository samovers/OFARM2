#!/usr/bin/env python3
"""Launch OFARM Python commands with a closed, source-only import posture.

This file must itself be invoked as a script with ``python -I -B -S``.  It
verifies the reviewed repository catalog and the exact locked virtual
environment before adding either root to ``sys.path``.  It never processes
``.pth`` files and never imports ``site``.
"""
# ruff: noqa: E402 -- sys.pycache_prefix must be sealed before stdlib imports.
from __future__ import annotations

# Keep the first operation limited to the built-in ``sys`` module.  Redirect
# bytecode lookup before importing any source-backed standard-library module;
# -B prevents writes and the deliberately absent prefix prevents reads of
# normal or unchecked ``__pycache__`` entries.
import sys


class LaunchError(RuntimeError):
    """The process is not safe to expose to project or dependency imports."""


_NATIVE_LOADER_PREFIXES_BYTES = (b"LD_", b"DYLD_")
_NATIVE_LOADER_EXACT_BYTES = {b"GLIBC_TUNABLES", b"GCONV_PATH"}


def _early_native_loader_gate() -> None:
    # ``posix`` is built in on the retained platform.  Check before importing
    # source-backed stdlib modules: a loader variable has already influenced
    # process startup even when its value is empty.
    import posix
    present = sorted(
        name.decode("ascii", errors="backslashreplace")
        for name in posix.environ
        if name in _NATIVE_LOADER_EXACT_BYTES
        or name.startswith(_NATIVE_LOADER_PREFIXES_BYTES)
    )
    if present:
        raise LaunchError(
            "ambient native loader customization is forbidden: "
            + ", ".join(present))


try:
    _early_native_loader_gate()
except LaunchError as exc:
    print(f"OFARM isolated launch refused: {exc}", file=sys.stderr)
    raise SystemExit(78) from None

_EMPTY_CACHE_PREFIX = sys.executable + ".ofarm-source-only-cache-must-not-exist"
sys.pycache_prefix = _EMPTY_CACHE_PREFIX

import hashlib
import importlib.machinery
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import runpy
from urllib.parse import unquote, urlparse
import zipfile


_FORBIDDEN_ENVIRONMENT = {
    "PYTHONCASEOK",
    "PYTHONEXECUTABLE",
    "PYTHONHASHSEED",
    "PYTHONHOME",
    "PYTHONINSPECT",
    "PYTHONMALLOC",
    "PYTHONPATH",
    "PYTHONPLATLIBDIR",
    "PYTHONPYCACHEPREFIX",
    "PYTHONSAFEPATH",
    "PYTHONSTARTUP",
    "PYTHONWARNINGS",
}
_NATIVE_LOADER_PREFIXES = ("LD_", "DYLD_")
_NATIVE_LOADER_EXACT = {"GLIBC_TUNABLES", "GCONV_PATH"}
_LOADABLE_SUFFIXES = {".py", ".pyw", ".pyc", ".pyo", ".pth"}
_WHEELHOUSE_NAME = ".ofarm-wheelhouse"


def _normalise_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _require_interpreter_flags() -> None:
    required = {
        "isolated": 1,
        "ignore_environment": 1,
        "no_site": 1,
        "no_user_site": 1,
        "safe_path": True,
        "dont_write_bytecode": 1,
    }
    actual = {name: getattr(sys.flags, name, None) for name in required}
    if actual != required:
        raise LaunchError(
            "OFARM must be launched with actual python -I -B -S semantics; "
            f"required={required!r}, actual={actual!r}")
    present = sorted(name for name in _FORBIDDEN_ENVIRONMENT if name in os.environ)
    if present:
        raise LaunchError(
            "ambient Python import customization is forbidden: " + ", ".join(present))
    native_present = sorted(
        name for name in os.environ
        if name in _NATIVE_LOADER_EXACT
        or name.startswith(_NATIVE_LOADER_PREFIXES)
    )
    if native_present:
        raise LaunchError(
            "ambient native loader customization is forbidden: "
            + ", ".join(native_present))
    if any(name in sys.modules for name in ("sitecustomize", "usercustomize")):
        raise LaunchError("Python startup customization was already imported")
    if Path(_EMPTY_CACHE_PREFIX).exists():
        raise LaunchError("the isolated bytecode cache sentinel unexpectedly exists")


def _arguments(argv: list[str]) -> tuple[Path, bool, str | None, list[str]]:
    if len(argv) < 2 or argv[0] != "--venv-root":
        raise LaunchError(
            "usage: ofarm_isolated.py --venv-root VENV "
            "[-m MODULE [ARG ...] | --check-import-posture-only]")
    venv_root = Path(argv[1]).expanduser().resolve(strict=True)
    remainder = argv[2:]
    if remainder == ["--check-import-posture-only"]:
        return venv_root, True, None, []
    if len(remainder) < 2 or remainder[0] != "-m" or not remainder[1]:
        raise LaunchError("the isolated launcher accepts only an explicit -m module")
    return venv_root, False, remainder[1], remainder[2:]


def _dependency_roots(venv_root: Path) -> list[Path]:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    candidates = [
        venv_root / "lib" / version / "site-packages",
        venv_root / "lib64" / version / "site-packages",
    ]
    roots: list[Path] = []
    for candidate in candidates:
        if not candidate.exists():
            continue
        resolved = candidate.resolve(strict=True)
        if resolved not in roots:
            roots.append(resolved)
    if not roots:
        raise LaunchError("the selected virtual environment has no site-packages root")
    executable = Path(os.path.abspath(sys.executable))
    try:
        executable.relative_to(venv_root)
    except ValueError as exc:
        raise LaunchError(
            "the isolated interpreter was not invoked through the selected virtual "
            "environment") from exc
    return roots


def _verify_static_catalog(project_root: Path) -> dict:
    verifier_path = project_root / "tooling" / "runtime_bundle_lock.py"
    spec = importlib.util.spec_from_file_location(
        "_ofarm_runtime_bundle_lock_verifier", verifier_path)
    if spec is None or spec.loader is None:
        raise LaunchError("the RuntimeBundle catalog verifier cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = module.build_catalog()
    try:
        actual = module.LOCK_PATH.read_bytes()
        module.verify_lock_bytes(actual, expected)
    except (OSError, module.CatalogError) as exc:
        raise LaunchError(f"the reviewed RuntimeBundle catalog is not exact: {exc}") from exc
    return expected


def _manifest_file_identity(path: Path) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise LaunchError(f"pinned runtime path is not a regular file: {path}")
    raw = path.read_bytes()
    return "sha256:" + hashlib.sha256(raw).hexdigest(), len(raw)


def _verify_manifest_entry(entry: object) -> Path:
    if (not isinstance(entry, dict)
            or set(entry) != {"path", "contentDigest", "byteLength"}
            or not isinstance(entry.get("path"), str)
            or not entry["path"].startswith("/")
            or not re.fullmatch(r"sha256:[0-9a-f]{64}",
                                entry.get("contentDigest", ""))
            or not isinstance(entry.get("byteLength"), int)
            or entry["byteLength"] < 0):
        raise LaunchError("pinned runtime image file entry is malformed")
    path = Path(entry["path"])
    if _manifest_file_identity(path) != (
            entry["contentDigest"], entry["byteLength"]):
        raise LaunchError(f"runtime image file differs from retained bytes: {path}")
    return path


def _standard_tree_identity(root: Path) -> tuple[list[dict], list[str]]:
    files: list[dict] = []
    directories: list[str] = []
    for directory, child_directories, filenames in os.walk(root):
        base = Path(directory)
        relative_base = base.relative_to(root)
        retained_children = []
        for name in sorted(child_directories):
            path = base / name
            relative = relative_base / name
            if name == "__pycache__":
                raise LaunchError(
                    f"standard runtime bytecode directory is forbidden: {path}")
            if name in {"site-packages", "dist-packages"}:
                continue
            if path.is_symlink() or not path.is_dir():
                raise LaunchError(f"standard runtime directory is unsafe: {path}")
            retained_children.append(name)
            directories.append(relative.as_posix())
        child_directories[:] = retained_children
        for name in sorted(filenames):
            path = base / name
            relative = relative_base / name
            if path.is_symlink() or not path.is_file():
                raise LaunchError(f"standard runtime file is unsafe: {path}")
            digest, length = _manifest_file_identity(path)
            files.append({
                "path": str(path),
                "relativePath": relative.as_posix(),
                "contentDigest": digest,
                "byteLength": length,
            })
    files.sort(key=lambda item: item["relativePath"])
    directories.sort()
    return files, directories


def _workflow_container(workflow: str) -> tuple[str, str]:
    lines = workflow.splitlines()

    def unique_index(pattern: str, start: int, end: int) -> int:
        matches = [
            index for index in range(start, end)
            if re.fullmatch(pattern, lines[index])
        ]
        if len(matches) != 1:
            raise LaunchError("workflow has no unique conformance container structure")
        return matches[0]

    jobs = unique_index(r"jobs:\s*", 0, len(lines))
    jobs_end = next((
        index for index in range(jobs + 1, len(lines))
        if lines[index] and not lines[index].startswith((" ", "#"))
    ), len(lines))
    conformance = unique_index(r"  conformance:\s*", jobs + 1, jobs_end)
    conformance_end = next((
        index for index in range(conformance + 1, jobs_end)
        if re.match(r"  \S", lines[index])
    ), jobs_end)
    container = unique_index(
        r"    container:\s*", conformance + 1, conformance_end)
    container_end = next((
        index for index in range(container + 1, conformance_end)
        if re.match(r"    \S", lines[index])
    ), conformance_end)
    image_lines = [
        re.fullmatch(r"      image:\s*(\S+)\s*", lines[index])
        for index in range(container + 1, container_end)
    ]
    option_lines = [
        re.fullmatch(r"      options:\s*(.+?)\s*", lines[index])
        for index in range(container + 1, container_end)
    ]
    images = [match.group(1) for match in image_lines if match]
    options = [match.group(1) for match in option_lines if match]
    if len(images) != 1 or len(options) != 1:
        raise LaunchError("workflow conformance container declaration is ambiguous")
    return images[0], options[0]


def _load_and_verify_runtime_image_manifest(
    project_root: Path,
    standard_path: list[str],
) -> dict:
    config_path = project_root / "conformance" / "review_baseline_config.json"
    manifest_path = project_root / "conformance" / "python_runtime_image_manifest.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LaunchError("retained Python runtime image metadata is malformed") from exc
    required = (config.get("requiredEnvironment") or {}).get(
        "pythonRuntimeImage")
    paths = config.get("paths") or {}
    if (not isinstance(required, dict)
            or set(required) != {
                "reference", "indexDigest", "platform",
                "platformManifestDigest", "rootFilesystem",
            }
            or required.get("rootFilesystem") != "READ_ONLY"
            or paths.get("pythonRuntimeImageManifest") !=
            "conformance/python_runtime_image_manifest.json"
            or not isinstance(manifest, dict)
            or set(manifest) != {"schemaVersion", "image", "python"}
            or manifest.get("schemaVersion") !=
            "ofarm.python-runtime-image-manifest.local.v1"):
        raise LaunchError("retained Python runtime image declaration is malformed")
    image = manifest.get("image")
    if (not isinstance(image, dict)
            or image.get("reference") != required.get("reference")
            or image.get("indexDigest") != required.get("indexDigest")
            or image.get("platform") != required.get("platform")
            or image.get("platformManifestDigest") !=
            required.get("platformManifestDigest")):
        raise LaunchError("runtime image config and retained manifest disagree")
    workflow = (project_root / ".github" / "workflows" /
                "conformance.yml").read_text(encoding="utf-8")
    short_reference = required["reference"].removeprefix("docker.io/library/")
    workflow_image, workflow_options = _workflow_container(workflow)
    if (workflow_image != f"{short_reference}@{required['indexDigest']}"
            or not workflow_options.startswith("--read-only ")):
        raise LaunchError("workflow does not select the retained read-only runtime image")

    # Host-side fixtures exercise launcher mechanics on macOS, but no live
    # RuntimeBundle is authorized there.  The authoritative Linux path below
    # must prove the exact read-only image before it exposes dependency code.
    if sys.platform != "linux":
        return manifest
    if not Path("/.dockerenv").exists():
        raise LaunchError("live Python runtime is not inside the retained container boundary")

    python = manifest.get("python")
    if (not isinstance(python, dict)
            or set(python) != {
                "version", "executable", "sharedLibrary",
                "standardLibraryRoots", "nativeFiles",
                "loaderConfigurationFiles", "requiredAbsentPaths",
                "requiredExecutables",
            }
            or python.get("version") != platform.python_version()):
        raise LaunchError("retained Python runtime manifest is malformed")
    executable = _verify_manifest_entry(python["executable"])
    if Path(sys.executable).resolve(strict=True) != executable:
        raise LaunchError("isolated interpreter is not the retained image executable")
    read_only_paths = [executable, _verify_manifest_entry(python["sharedLibrary"])]
    for field in ("loaderConfigurationFiles", "requiredExecutables"):
        entries = python[field]
        if not isinstance(entries, list) or not entries:
            raise LaunchError(f"runtime image {field} inventory is malformed")
        read_only_paths.extend(_verify_manifest_entry(entry) for entry in entries)
    absent = python["requiredAbsentPaths"]
    if (not isinstance(absent, list) or absent != sorted(set(absent))
            or any(not isinstance(path, str) or not path.startswith("/")
                   or Path(path).exists() for path in absent)):
        raise LaunchError("runtime image required-absence inventory is violated")

    roots = python["standardLibraryRoots"]
    if not isinstance(roots, list) or not roots:
        raise LaunchError("runtime image standard-library inventory is empty")
    expected_path_roots = []
    for root_entry in roots:
        if (not isinstance(root_entry, dict)
                or set(root_entry) != {"path", "directories", "files"}
                or not isinstance(root_entry.get("path"), str)):
            raise LaunchError("runtime image standard-library root is malformed")
        root = Path(root_entry["path"])
        if root.is_symlink() or not root.is_dir():
            raise LaunchError(f"runtime image standard-library root is unsafe: {root}")
        actual_files, actual_directories = _standard_tree_identity(root)
        if (actual_files != root_entry["files"]
                or actual_directories != root_entry["directories"]):
            raise LaunchError(
                f"standard runtime tree differs from retained image: {root}")
        expected_path_roots.append(root.resolve(strict=True))
        read_only_paths.append(root)
    for raw in standard_path:
        path = Path(raw).resolve(strict=True)
        if not any(path == root or path.is_relative_to(root)
                   for root in expected_path_roots):
            raise LaunchError(f"isolated standard path is not retained: {path}")
    if not standard_path or Path(standard_path[0]) != expected_path_roots[0]:
        raise LaunchError("isolated standard path order differs from retained image")
    if any(not os.statvfs(path).f_flag & os.ST_RDONLY for path in read_only_paths):
        raise LaunchError("retained runtime image path is not on a read-only filesystem")
    return manifest


def _parse_requirement_locks(project_root: Path) -> dict[str, dict[str, object]]:
    packages: dict[str, dict[str, object]] = {}
    pattern = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)")
    for name in ("requirements-review-baseline.lock", "requirements-review-pip.lock"):
        logical_lines: list[str] = []
        pending = ""
        for physical in (project_root / name).read_text(encoding="utf-8").splitlines():
            stripped = physical.strip()
            if not pending and (not stripped or stripped.startswith("#")):
                continue
            continued = stripped.endswith("\\")
            pending += stripped[:-1].strip() + " " if continued else stripped
            if continued:
                continue
            logical_lines.append(pending.strip())
            pending = ""
        if pending:
            raise LaunchError(f"unterminated requirement in {name}")
        for line in logical_lines:
            match = pattern.match(line)
            if match is None:
                raise LaunchError(f"unsupported retained requirement in {name}: {line!r}")
            package, version = match.groups()
            normalized = _normalise_name(package)
            if normalized in packages:
                raise LaunchError(f"duplicate locked distribution {normalized!r}")
            hashes = tuple(sorted(set(re.findall(
                r"(?:^|\s)--hash=sha256:([0-9a-f]{64})(?=\s|$)", line))))
            if not hashes:
                raise LaunchError(
                    f"retained distribution {normalized!r} has no SHA-256 wheel hash")
            packages[normalized] = {"version": version, "hashes": hashes}
    if not packages:
        raise LaunchError("the retained dependency locks are empty")
    return packages


def _wheel_member_destination(member: str, data_prefix: str) -> PurePosixPath | None:
    path = PurePosixPath(member)
    if (not member or member.startswith(("/", "\\")) or "\\" in member
            or any(part in {"", ".", ".."} for part in path.parts)):
        raise LaunchError(f"wheel contains an unsafe member path: {member!r}")
    if path.parts[0] != data_prefix:
        return path
    if len(path.parts) < 3 or path.parts[1] not in {"purelib", "platlib"}:
        return None
    return PurePosixPath(*path.parts[2:])


def _wheel_metadata(
    archive: Path,
    archive_bytes: bytes,
) -> tuple[str, str, str, dict[PurePosixPath, bytes]]:
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as wheel:
            members = [item for item in wheel.infolist() if not item.is_dir()]
            metadata_names = [
                item.filename for item in members
                if item.filename.count("/") == 1
                and item.filename.endswith(".dist-info/METADATA")
            ]
            if len(metadata_names) != 1:
                raise LaunchError(
                    f"wheel must contain exactly one dist-info/METADATA: {archive.name}")
            dist_info = metadata_names[0].split("/", 1)[0]
            data_prefix = dist_info.removesuffix(".dist-info") + ".data"
            metadata = wheel.read(metadata_names[0]).decode("utf-8", errors="strict")
            name_match = re.search(r"(?m)^Name:\s*([^\r\n]+)\s*$", metadata)
            version_match = re.search(r"(?m)^Version:\s*([^\r\n]+)\s*$", metadata)
            if name_match is None or version_match is None:
                raise LaunchError(f"wheel METADATA has no exact name/version: {archive.name}")
            installed: dict[PurePosixPath, bytes] = {}
            for item in members:
                destination = _wheel_member_destination(item.filename, data_prefix)
                if destination is None:
                    continue
                if destination in installed:
                    raise LaunchError(
                        f"wheel maps multiple members to {destination}: {archive.name}")
                if (destination.suffix.lower() in {".pyc", ".pyo", ".pth"}
                        or "__pycache__" in destination.parts
                        or destination.name in {"sitecustomize.py", "usercustomize.py"}):
                    raise LaunchError(
                        f"wheel contains forbidden Python customization/bytecode: "
                        f"{archive.name}/{destination}")
                installed[destination] = wheel.read(item)
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, KeyError) as exc:
        raise LaunchError(f"locked wheel cannot be read: {archive}") from exc
    return (
        _normalise_name(name_match.group(1).strip()),
        version_match.group(1).strip(),
        dist_info,
        installed,
    )


def _verified_wheel_manifests(
    venv_root: Path,
    expected: dict[str, dict[str, object]],
) -> dict[str, tuple[str, Path, int, dict[PurePosixPath, bytes]]]:
    wheelhouse = venv_root / _WHEELHOUSE_NAME
    if not wheelhouse.is_dir() or wheelhouse.is_symlink():
        raise LaunchError(
            f"the selected virtual environment has no retained {_WHEELHOUSE_NAME}")
    manifests: dict[
        str, tuple[str, Path, int, dict[PurePosixPath, bytes]]
    ] = {}
    archives = sorted(wheelhouse.iterdir(), key=lambda path: path.name)
    if not archives or any(path.is_symlink() or not path.is_file()
                           or path.suffix != ".whl" for path in archives):
        raise LaunchError("the retained wheelhouse must contain only wheel archives")
    for archive in archives:
        archive_bytes = archive.read_bytes()
        digest = hashlib.sha256(archive_bytes).hexdigest()
        name, version, dist_info, files = _wheel_metadata(archive, archive_bytes)
        requirement = expected.get(name)
        if requirement is None:
            raise LaunchError(f"wheelhouse contains unlocked distribution {name!r}")
        if (version != requirement["version"]
                or digest not in requirement["hashes"]):
            raise LaunchError(
                f"wheel archive differs from retained lock: {name}=={version}")
        if name in manifests:
            raise LaunchError(f"wheelhouse contains multiple wheels for {name!r}")
        manifests[name] = (dist_info, archive, len(archive_bytes), files)
    if set(manifests) != set(expected):
        raise LaunchError(
            "wheelhouse distribution set differs from retained locks: "
            f"missing={sorted(set(expected) - set(manifests))!r}")
    return manifests


def _verify_generated_direct_url(path: Path, archive: Path, expected_hashes) -> None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        parsed = urlparse(value["url"])
        hashes = value["archive_info"]["hashes"]
        resolved = Path(unquote(parsed.path)).resolve(strict=True)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LaunchError(f"pip-generated direct_url.json is malformed: {path}") from exc
    if (parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}
            or resolved != archive.resolve(strict=True)
            or hashes.get("sha256") not in expected_hashes):
        raise LaunchError(f"pip-generated direct_url.json does not name its locked wheel: {path}")


def _verify_locked_environment(
    project_root: Path,
    venv_root: Path,
    dependency_roots: list[Path],
) -> None:
    expected = _parse_requirement_locks(project_root)
    wheel_manifests = _verified_wheel_manifests(venv_root, expected)
    installed: dict[str, str] = {}
    owned_files: set[Path] = set()
    for distribution in importlib.metadata.distributions(
            path=[str(path) for path in dependency_roots]):
        raw_name = distribution.metadata.get("Name")
        if not raw_name:
            raise LaunchError("an installed distribution has no canonical name")
        name = _normalise_name(raw_name)
        if name in installed:
            raise LaunchError(f"multiple installed distributions normalize to {name!r}")
        installed[name] = distribution.version
        manifest = wheel_manifests.get(name)
        if manifest is None:
            raise LaunchError(f"installed distribution has no locked wheel: {name!r}")
        dist_info, archive, _archive_byte_length, wheel_files = manifest
        if distribution.version != expected[name]["version"]:
            raise LaunchError(
                f"installed distribution version differs from locked wheel: {name!r}")
        root = Path(distribution.locate_file("")).resolve(strict=True)
        if root not in dependency_roots:
            raise LaunchError(f"installed distribution escaped dependency roots: {name!r}")
        for relative, exact in wheel_files.items():
            path = root.joinpath(*relative.parts)
            if relative == PurePosixPath(dist_info, "RECORD"):
                # pip rewrites RECORD during installation. It is metadata only;
                # archive bytes, not this mutable copy, are the trust root.
                if not path.is_file() or path.is_symlink():
                    raise LaunchError(f"installed RECORD is missing: {name!r}")
                owned_files.add(path.resolve(strict=True))
                continue
            if path.is_symlink() or not path.is_file() or path.read_bytes() != exact:
                raise LaunchError(
                    f"installed bytes differ from locked wheel: {name}/{relative}")
            owned_files.add(path.resolve(strict=True))

        generated = {
            "INSTALLER": b"pip\n",
            "REQUESTED": b"",
        }
        dist_info_root = root / dist_info
        for filename, exact in generated.items():
            path = dist_info_root / filename
            if path.exists():
                if path.is_symlink() or not path.is_file() or path.read_bytes() != exact:
                    raise LaunchError(f"pip-generated metadata is not exact: {path}")
                owned_files.add(path.resolve(strict=True))
        direct_url = dist_info_root / "direct_url.json"
        if direct_url.exists():
            if direct_url.is_symlink() or not direct_url.is_file():
                raise LaunchError(f"pip-generated metadata is unsafe: {direct_url}")
            _verify_generated_direct_url(
                direct_url, archive, expected[name]["hashes"])
            owned_files.add(direct_url.resolve(strict=True))
    expected_versions = {
        name: requirement["version"] for name, requirement in expected.items()
    }
    if installed != expected_versions:
        raise LaunchError(
            "installed distribution set/versions differ from retained locks: "
            f"expected={expected_versions!r}, actual={installed!r}")

    # ``-S`` prevents .pth execution, but the closed environment rejects those
    # files and every unowned file/directory instead of silently ignoring it.
    owned_directories: set[Path] = set()
    for root in dependency_roots:
        for path in owned_files:
            try:
                relative = path.relative_to(root)
            except ValueError:
                continue
            parent = root
            owned_directories.add(root)
            for part in relative.parts[:-1]:
                parent = parent / part
                owned_directories.add(parent)
    for root in dependency_roots:
        for directory, directories, filenames in os.walk(root):
            for child in list(directories):
                child_path = Path(directory) / child
                if child_path.is_symlink():
                    raise LaunchError(
                        f"symlinked dependency directory is forbidden: "
                        f"{child_path}")
                if (child != "__pycache__"
                        and child_path.resolve(strict=True) not in owned_directories):
                    raise LaunchError(
                        f"unowned dependency directory is forbidden: {child_path}")
            if "__pycache__" in directories:
                raise LaunchError(
                    f"bytecode cache directory is forbidden: "
                    f"{Path(directory) / '__pycache__'}")
            for filename in filenames:
                unresolved = Path(directory) / filename
                if unresolved.is_symlink():
                    raise LaunchError(f"symlinked dependency file is forbidden: {unresolved}")
                path = unresolved.resolve(strict=True)
                suffix = path.suffix.lower()
                is_native = any(filename.endswith(item)
                                for item in importlib.machinery.EXTENSION_SUFFIXES)
                if suffix in {".pyc", ".pyo"}:
                    raise LaunchError(f"installed bytecode is forbidden: {path}")
                if suffix == ".pth" or filename in {"sitecustomize.py", "usercustomize.py"}:
                    raise LaunchError(f"Python startup customization is forbidden: {path}")
                if path not in owned_files:
                    kind = "importable " if suffix in _LOADABLE_SUFFIXES or is_native else ""
                    raise LaunchError(f"unowned {kind}dependency file is forbidden: {path}")


def _verify_project_bytecode(project_root: Path, catalog: dict) -> None:
    for entry in catalog["components"]:
        if entry["role"] not in {
                "RUNTIME_CODE", "RUNTIME_CATALOG_CODE", "PARSER_CODE"}:
            continue
        path = project_root / entry["path"]
        direct = path.with_suffix(".pyc")
        if direct.exists():
            raise LaunchError(f"project bytecode is forbidden: {direct}")
        cache = path.parent / "__pycache__"
        if cache.is_dir() and any(cache.glob(path.stem + ".*.pyc")):
            raise LaunchError(f"project bytecode cache is forbidden for {path}")
    for name in ("sitecustomize.py", "usercustomize.py"):
        if (project_root / name).exists():
            raise LaunchError(f"project startup customization is forbidden: {name}")


def _closed_standard_path() -> list[str]:
    entries: list[str] = []
    for raw in sys.path:
        if not isinstance(raw, str) or not raw or not os.path.isabs(raw):
            raise LaunchError(f"isolated standard-library sys.path entry is unsafe: {raw!r}")
        path = Path(raw)
        if "site-packages" in path.parts or "dist-packages" in path.parts:
            raise LaunchError(
                f"site packages appeared before locked environment verification: {path}")
        if not path.exists():
            # CPython normally advertises a nonexistent pythonXY.zip entry.
            # Removing it closes the path; a later archive cannot appear ahead
            # of the retained stdlib and locked wheels.
            continue
        if not path.is_dir() and not path.is_file():
            raise LaunchError(f"isolated standard-library path is unsafe: {path}")
        normalized = str(path.resolve(strict=False))
        if normalized in entries:
            raise LaunchError(f"duplicate isolated standard-library path: {normalized}")
        entries.append(normalized)
    return entries


def _configure_path(
    standard_path: list[str], dependency_roots: list[Path], project_root: Path,
) -> None:
    ordered = [
        *standard_path,
        *(str(path) for path in dependency_roots),
        str(project_root),
    ]
    if len(ordered) != len(set(ordered)):
        raise LaunchError("the closed OFARM sys.path contains duplicate roots")
    sys.path[:] = ordered
    # Importer instances created while the launcher itself was verifying the
    # host must not become runtime authority after the path is replaced. The
    # standard retained hooks recreate FileFinder instances for only the
    # closed roots above; live activation then seals their exact identities.
    sys.path_importer_cache.clear()


def main(argv: list[str] | None = None) -> int:
    _require_interpreter_flags()
    venv_root, posture_only, module, arguments = _arguments(
        list(sys.argv[1:] if argv is None else argv))
    project_root = Path(__file__).resolve(strict=True).parents[1]
    dependency_roots = _dependency_roots(venv_root)
    standard_path = _closed_standard_path()

    if posture_only:
        # Test-only inspection executes no caller-provided module and therefore
        # cannot bypass the full catalog/environment checks below.
        for root in dependency_roots:
            for directory, directories, filenames in os.walk(root):
                if "__pycache__" in directories:
                    raise LaunchError("bytecode cache directory is forbidden")
                if any(Path(name).suffix.lower() in {".pyc", ".pyo", ".pth"}
                       or name in {"sitecustomize.py", "usercustomize.py"}
                       for name in filenames):
                    raise LaunchError("bytecode or startup customization is forbidden")
        _configure_path(standard_path, dependency_roots, project_root)
        print(json.dumps({
            "flags": {
                "isolated": sys.flags.isolated,
                "noSite": sys.flags.no_site,
                "noUserSite": sys.flags.no_user_site,
                "safePath": sys.flags.safe_path,
                "dontWriteBytecode": sys.flags.dont_write_bytecode,
            },
            "sysPath": sys.path,
        }, sort_keys=True))
        return 0

    catalog = _verify_static_catalog(project_root)
    _load_and_verify_runtime_image_manifest(project_root, standard_path)
    _verify_project_bytecode(project_root, catalog)
    _verify_locked_environment(project_root, venv_root, dependency_roots)
    _configure_path(standard_path, dependency_roots, project_root)
    sys.argv = [module, *arguments]
    runpy.run_module(module, run_name="__main__", alter_sys=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LaunchError as exc:
        print(f"OFARM isolated launch refused: {exc}", file=sys.stderr)
        raise SystemExit(78) from exc
