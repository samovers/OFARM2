"""Hostile subprocess checks for the closed OFARM Python import posture."""
from __future__ import annotations

import json
import os
from pathlib import Path
import py_compile
import pytest
import shutil
import subprocess
import sys
import types
import importlib.machinery
import base64
import hashlib
import zipfile

from kernel.runtime_bundle import (
    RuntimeBundleError,
    _decode_proc_maps_path,
    _import_infrastructure_observation,
    _mapped_file_content_identity,
    _module_loader_is_reviewed,
    _module_observation,
    _module_origin_stat_signature,
    _native_loader_environment_observation,
    _parse_executable_mappings,
    _require_reviewed_import_search_state,
    _standard_runtime_observation,
)
from tooling.runtime_bundle_lock import build_catalog


ROOT = Path(__file__).resolve().parents[2]


def _fake_venv(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "isolated-venv"
    binary = root / "bin" / "python"
    binary.parent.mkdir(parents=True)
    binary.symlink_to(Path(sys.executable).resolve())
    site_packages = (
        root / "lib" /
        f"python{sys.version_info.major}.{sys.version_info.minor}" /
        "site-packages"
    )
    site_packages.mkdir(parents=True)
    return root, binary, site_packages


def _record_hash(value: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(value).digest()).rstrip(b"=")
    return "sha256=" + encoded.decode("ascii")


def _full_launch_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Build a small exact catalog and one archive-attested wheel layout."""
    project = tmp_path / "project"
    catalog = build_catalog()
    for entry in catalog["components"]:
        source = ROOT / entry["path"]
        target = project / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    # Replace the two copied production locks with one minimal exact test
    # distribution, then generate the temporary project's own static lock.
    (project / "requirements-review-baseline.lock").write_text(
        "probe==1.0 --hash=sha256:" + "0" * 64 + "\n",
        encoding="utf-8")
    (project / "requirements-review-pip.lock").write_text(
        "# intentionally empty in the isolated launcher fixture\n", encoding="utf-8")

    venv, binary, site_packages = _fake_venv(tmp_path)
    module_bytes = (
        b"import json,sys\n"
        b"print(json.dumps({'isolated':sys.flags.isolated,"
        b"'noSite':sys.flags.no_site,'noUserSite':sys.flags.no_user_site,"
        b"'safePath':sys.flags.safe_path,"
        b"'dontWriteBytecode':sys.flags.dont_write_bytecode,"
        b"'importerCache':sorted(sys.path_importer_cache),"
        b"'noneImporters':sorted(k for k,v in "
        b"sys.path_importer_cache.items() if v is None),"
        b"'sysPath':sys.path},sort_keys=True))\n"
    )
    metadata_bytes = b"Metadata-Version: 2.1\nName: probe\nVersion: 1.0\n\n"
    wheel_bytes = (
        b"Wheel-Version: 1.0\nGenerator: ofarm-test\n"
        b"Root-Is-Purelib: true\nTag: py3-none-any\n"
    )
    dist_info = site_packages / "probe-1.0.dist-info"
    dist_info.mkdir()
    (site_packages / "probe.py").write_bytes(module_bytes)
    (dist_info / "METADATA").write_bytes(metadata_bytes)
    (dist_info / "WHEEL").write_bytes(wheel_bytes)
    record = (
        f"probe.py,{_record_hash(module_bytes)},{len(module_bytes)}\n"
        f"probe-1.0.dist-info/METADATA,{_record_hash(metadata_bytes)},"
        f"{len(metadata_bytes)}\n"
        f"probe-1.0.dist-info/WHEEL,{_record_hash(wheel_bytes)},"
        f"{len(wheel_bytes)}\n"
        "probe-1.0.dist-info/RECORD,,\n"
    )
    (dist_info / "RECORD").write_text(record, encoding="utf-8")
    (dist_info / "INSTALLER").write_bytes(b"pip\n")
    (dist_info / "REQUESTED").write_bytes(b"")

    wheelhouse = venv / ".ofarm-wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "probe-1.0-py3-none-any.whl"
    members = {
        "probe.py": module_bytes,
        "probe-1.0.dist-info/METADATA": metadata_bytes,
        "probe-1.0.dist-info/WHEEL": wheel_bytes,
        "probe-1.0.dist-info/RECORD": record.encode("utf-8"),
    }
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, value in members.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = 0o100644 << 16
            archive.writestr(info, value)
    wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (project / "requirements-review-baseline.lock").write_text(
        "probe==1.0 --hash=sha256:" + wheel_hash + "\n",
        encoding="utf-8")
    generator = project / "tooling" / "runtime_bundle_lock.py"
    generated = subprocess.run(
        [str(binary), "-I", "-B", "-S", str(generator), "--write"],
        cwd=project, env=_environment(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert generated.returncode == 0, generated.stderr
    return project, venv, binary, site_packages


def _environment(**updates: str) -> dict[str, str]:
    env = dict(os.environ)
    for name in (
        "PYTHONCASEOK", "PYTHONEXECUTABLE", "PYTHONHASHSEED", "PYTHONHOME",
        "PYTHONINSPECT", "PYTHONMALLOC", "PYTHONPATH", "PYTHONPLATLIBDIR",
        "PYTHONPYCACHEPREFIX", "PYTHONSAFEPATH", "PYTHONSTARTUP",
        "PYTHONWARNINGS", "GLIBC_TUNABLES", "GCONV_PATH",
    ):
        env.pop(name, None)
    for name in list(env):
        if name.startswith(("LD_", "DYLD_")):
            env.pop(name)
    env.update(updates)
    return env


def _full_command(project: Path, binary: Path, venv_root: Path) -> list[str]:
    return [
        str(binary), "-I", "-B", "-S",
        str(project / "tooling" / "ofarm_isolated.py"),
        "--venv-root", str(venv_root), "-m", "probe",
    ]


def test_isolated_launcher_accepts_only_the_closed_clean_path(tmp_path):
    project, venv, binary, site_packages = _full_launch_fixture(tmp_path)
    result = subprocess.run(
        _full_command(project, binary, venv), cwd=project, env=_environment(),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert {name: observed[name] for name in (
        "dontWriteBytecode", "isolated", "noSite", "noUserSite", "safePath",
    )} == {
        "dontWriteBytecode": 1, "isolated": 1, "noSite": 1,
        "noUserSite": 1, "safePath": True,
    }
    assert observed["sysPath"][-1] == str(project)
    assert str(site_packages) in observed["sysPath"]
    assert observed["noneImporters"] == []
    assert observed["importerCache"]
    assert all(Path(path).is_dir() for path in observed["importerCache"])


def test_isolated_launcher_rejects_nonisolated_interpreter_flags(tmp_path):
    venv, binary, _site_packages = _fake_venv(tmp_path)
    result = subprocess.run(
        [str(binary), str(ROOT / "tooling" / "ofarm_isolated.py"),
         "--venv-root", str(venv), "--check-import-posture-only"],
        cwd=ROOT, env=_environment(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 78
    assert "-I -B -S" in result.stderr


def test_isolated_launcher_rejects_shadow_dependency_on_pythonpath(tmp_path):
    project, venv, binary, _site_packages = _full_launch_fixture(tmp_path)
    shadow = tmp_path / "shadow"
    (shadow / "jsonschema").mkdir(parents=True)
    (shadow / "jsonschema" / "__init__.py").write_text(
        "class Draft202012Validator: pass\n", encoding="utf-8")
    result = subprocess.run(
        _full_command(project, binary, venv), cwd=project,
        env=_environment(PYTHONPATH=str(shadow)),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 78
    assert "PYTHONPATH" in result.stderr


def test_isolated_launcher_rejects_empty_native_loader_environment(tmp_path):
    project, venv, binary, _site_packages = _full_launch_fixture(tmp_path)
    result = subprocess.run(
        _full_command(project, binary, venv), cwd=project,
        env=_environment(LD_FUTURE=""), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 78
    assert "native loader customization" in result.stderr
    assert "LD_FUTURE" in result.stderr


def test_isolated_launcher_removes_nonexistent_standard_paths(tmp_path):
    venv, binary, _site_packages = _fake_venv(tmp_path)
    result = subprocess.run(
        [str(binary), "-I", "-B", "-S",
         str(ROOT / "tooling" / "ofarm_isolated.py"),
         "--venv-root", str(venv), "--check-import-posture-only"],
        cwd=ROOT, env=_environment(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 0, result.stderr
    assert all(Path(path).exists() for path in json.loads(result.stdout)["sysPath"])


def test_isolated_launcher_rejects_workflow_image_hidden_by_comment(tmp_path):
    project, venv, binary, _site_packages = _full_launch_fixture(tmp_path)
    workflow = project / ".github" / "workflows" / "conformance.yml"
    retained = workflow.read_text(encoding="utf-8")
    image_line = next(
        line for line in retained.splitlines()
        if line.startswith("      image: python:3.12.13-bookworm@sha256:"))
    changed = retained.replace(image_line, "      image: python:unretained")
    changed += f"\n# spoofed retained declaration: {image_line.strip()}\n"
    workflow.write_text(changed, encoding="utf-8")
    generator = project / "tooling" / "runtime_bundle_lock.py"
    generated = subprocess.run(
        [str(binary), "-I", "-B", "-S", str(generator), "--write"],
        cwd=project, env=_environment(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert generated.returncode == 0, generated.stderr

    result = subprocess.run(
        _full_command(project, binary, venv), cwd=project, env=_environment(),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 78
    assert "workflow" in result.stderr


def test_isolated_launcher_rejects_sitecustomize_injection(tmp_path):
    project, venv, binary, site_packages = _full_launch_fixture(tmp_path)
    (site_packages / "sitecustomize.py").write_text(
        "raise AssertionError('must never execute')\n", encoding="utf-8")
    result = subprocess.run(
        _full_command(project, binary, venv), cwd=project, env=_environment(),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 78
    assert "customization" in result.stderr
    assert "must never execute" not in result.stderr


def test_isolated_launcher_rejects_unchecked_stale_bytecode(tmp_path):
    project, venv, binary, site_packages = _full_launch_fixture(tmp_path)
    source = site_packages / "jsonschema.py"
    source.write_text("SAFE = True\n", encoding="utf-8")
    cache = site_packages / "__pycache__" / "jsonschema.cpython-test.pyc"
    cache.parent.mkdir()
    py_compile.compile(
        str(source), cfile=str(cache), doraise=True,
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
    source.write_text("SAFE = False\n", encoding="utf-8")
    result = subprocess.run(
        _full_command(project, binary, venv), cwd=project, env=_environment(),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 78
    assert "bytecode" in result.stderr


def test_isolated_launcher_uses_locked_wheel_not_mutable_record(tmp_path):
    project, venv, binary, site_packages = _full_launch_fixture(tmp_path)
    changed = b"raise AssertionError('changed after wheel install')\n"
    (site_packages / "probe.py").write_bytes(changed)
    record = site_packages / "probe-1.0.dist-info" / "RECORD"
    rows = record.read_text(encoding="utf-8").splitlines()
    rows[0] = f"probe.py,{_record_hash(changed)},{len(changed)}"
    record.write_text("\n".join(rows) + "\n", encoding="utf-8")

    result = subprocess.run(
        _full_command(project, binary, venv), cwd=project, env=_environment(),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    assert result.returncode == 78
    assert "locked wheel" in result.stderr
    assert "changed after wheel install" not in result.stderr


def test_isolated_launcher_rejects_unowned_dependency_data(tmp_path):
    project, venv, binary, site_packages = _full_launch_fixture(tmp_path)
    (site_packages / "runtime-policy.json").write_text(
        '{"decision":"changed"}\n', encoding="utf-8")

    result = subprocess.run(
        _full_command(project, binary, venv), cwd=project, env=_environment(),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    assert result.returncode == 78
    assert "unowned dependency file" in result.stderr


def test_actual_module_observation_classifies_unknown_origin(tmp_path):
    unknown = tmp_path / "hostile_loader.py"
    unknown.write_text("VALUE = 'unretained'\n", encoding="utf-8")
    module = types.ModuleType("_ofarm_unknown_origin_test")
    module.__spec__ = importlib.machinery.ModuleSpec(
        module.__name__, loader=None, origin=str(unknown))
    module.__file__ = str(unknown)
    sys.modules[module.__name__] = module
    try:
        observed = _module_observation(ROOT, {}, {}, (), {})
    finally:
        del sys.modules[module.__name__]
    entry = next(item for item in observed if item["name"] == module.__name__)
    assert entry["classification"] == "UNKNOWN"
    assert entry["contentDigest"].startswith("sha256:")


def test_trusted_pytest_does_not_allow_arbitrary_profile_module(tmp_path):
    project = tmp_path / "project"
    hostile = project / "profile_si_ffs" / "hostile.py"
    hostile.parent.mkdir(parents=True)
    hostile.write_text("VALUE = 'unretained'\n", encoding="utf-8")
    module = types.ModuleType("profile_si_ffs.hostile")
    module.__spec__ = importlib.machinery.ModuleSpec(
        module.__name__, loader=None, origin=str(hostile))
    module.__file__ = str(hostile)
    pytest_module = sys.modules["pytest"]
    pytest_origin = str(Path(pytest_module.__file__).resolve())
    sys.modules[module.__name__] = module
    try:
        observed = _module_observation(
            project, {}, {pytest_origin: ["pytest"]}, (), {})
    finally:
        del sys.modules[module.__name__]
    entry = next(item for item in observed if item["name"] == module.__name__)
    assert entry["classification"] == "UNKNOWN"


def test_same_module_object_detects_origin_change_before_reload(tmp_path):
    source = tmp_path / "reloadable.py"
    source.write_text("VALUE = 'retained'\n", encoding="utf-8")
    module = types.ModuleType("_ofarm_reload_stat_test")
    module.__spec__ = importlib.machinery.ModuleSpec(
        module.__name__, loader=None, origin=str(source))
    module.__file__ = str(source)
    before = _module_origin_stat_signature(module)
    source.write_text("VALUE = 'hostile and changed length'\n", encoding="utf-8")
    after = _module_origin_stat_signature(module)
    assert module is module
    assert after != before


def test_retained_origin_does_not_authorize_an_unknown_loader():
    assert not _module_loader_is_reviewed({
        "name": "jsonschema",
        "classification": "RETAINED_DISTRIBUTION_FILE",
        "origin": "/locked/site-packages/jsonschema/__init__.py",
        "loader": "hostile.Loader",
    })


def test_regular_package_search_path_cannot_escape_retained_origin(tmp_path):
    root = tmp_path / "site-packages"
    package = root / "retained_pkg"
    package.mkdir(parents=True)
    source = package / "__init__.py"
    source.write_text("VALUE = 'retained'\n", encoding="utf-8")
    hostile = tmp_path / "shadow" / "retained_pkg"
    hostile.mkdir(parents=True)
    module = types.ModuleType("_ofarm_package_path_test")
    loader = importlib.machinery.SourceFileLoader(module.__name__, str(source))
    module.__spec__ = importlib.machinery.ModuleSpec(
        module.__name__, loader=loader, origin=str(source), is_package=True)
    module.__file__ = str(source)
    module.__loader__ = loader
    module.__path__ = [str(hostile)]
    module.__spec__.submodule_search_locations = [str(hostile)]
    sys.modules[module.__name__] = module
    try:
        observed = _module_observation(
            ROOT, {}, {str(source.resolve()): ["retained-pkg"]},
            (str(root.resolve()),), {})
    finally:
        del sys.modules[module.__name__]
    entry = next(item for item in observed if item["name"] == module.__name__)
    with pytest.raises(RuntimeBundleError, match="search path"):
        _require_reviewed_import_search_state({
            "importPosture": {
                "actualModules": [entry], "metaPath": [], "pathHooks": [],
            },
        })


def test_import_infrastructure_observes_custom_meta_path_provider():
    class HostileFinder:
        pass

    finder = HostileFinder()
    sys.meta_path.insert(0, finder)
    try:
        meta_path, _path_hooks = _import_infrastructure_observation()
    finally:
        del sys.meta_path[0]
    assert meta_path[0] == {
        "objectKind": "INSTANCE",
        "providerModule": __name__,
        "providerQualname": (
            "test_import_infrastructure_observes_custom_meta_path_provider."
            "<locals>.HostileFinder"
        ),
        "typeModule": __name__,
        "typeQualname": (
            "test_import_infrastructure_observes_custom_meta_path_provider."
            "<locals>.HostileFinder"
        ),
    }
    with pytest.raises(RuntimeBundleError, match="provider is not retained"):
        _require_reviewed_import_search_state({
            "importPosture": {
                "actualModules": [{
                    "name": __name__,
                    "classification": "NON_RUNTIME_TEST_HARNESS",
                    "origin": str(Path(__file__).resolve()),
                    "packageSearchPaths": [],
                    "specSearchPaths": [],
                }],
                "metaPath": [meta_path[0]],
                "pathHooks": [],
            },
        })


def test_proc_maps_parser_receipts_files_and_kernel_mappings_exactly():
    raw = "\n".join((
        "00400000-00401000 r-xp 00000000 08:01 42 /opt/retained\\040lib.so",
        "00401000-00402000 r-xp 00001000 08:01 42 /opt/retained\\040lib.so",
        "7fff0000-7fff1000 r-xp 00000000 00:00 0 [vdso]",
        "ffff0000-ffff1000 --xp 00000000 00:00 0 [vsyscall]",
        "10000000-10001000 r--p 00000000 08:01 99 /ignored/nonexec.so",
    ))
    files, kernel = _parse_executable_mappings(raw)
    assert files == [("/opt/retained lib.so", 8, 1, 42)]
    assert kernel == ["[vdso]", "[vsyscall]"]
    assert _decode_proc_maps_path(r"/a\011b") == "/a\tb"


@pytest.mark.parametrize("mapping", [
    "1000-2000 r-xp 00000000 00:00 0",
    "1000-2000 r-xp 00000000 00:00 1 memfd:evil (deleted)",
    "1000-2000 r-xp 00000000 08:01 2 /tmp/evil.so (deleted)",
    "1000-2000 r-xp 00000000 00:00 3 [heap]",
])
def test_proc_maps_parser_rejects_unattributable_executable_mapping(mapping):
    with pytest.raises(RuntimeBundleError, match="executable mapping"):
        _parse_executable_mappings(mapping)


def test_native_loader_environment_observes_presence_even_when_empty(monkeypatch):
    monkeypatch.setenv("LD_FUTURE", "")
    monkeypatch.setenv("DYLD_FUTURE", "retained-refusal")
    monkeypatch.setenv("GLIBC_TUNABLES", "")
    monkeypatch.setenv("GCONV_PATH", "/tmp/hostile")
    assert _native_loader_environment_observation() == {
        "DYLD_FUTURE": "retained-refusal",
        "GCONV_PATH": "/tmp/hostile",
        "GLIBC_TUNABLES": "",
        "LD_FUTURE": "",
    }


def test_standard_runtime_observation_file_order_is_canonical():
    observation, _file_map = _standard_runtime_observation()
    for root in observation["roots"]:
        paths = [entry["path"] for entry in root["files"]]
        assert paths == sorted(paths)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux /proc fd identity")
def test_mapped_file_identity_uses_exact_open_descriptor(tmp_path):
    path = tmp_path / "retained-native.so"
    path.write_bytes(b"retained native bytes")
    observed = path.stat()
    assert _mapped_file_content_identity(
        path.resolve(), os.major(observed.st_dev), os.minor(observed.st_dev),
        observed.st_ino,
    ) == ("sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
          len(path.read_bytes()))
    with pytest.raises(RuntimeBundleError, match="open file"):
        _mapped_file_content_identity(
            path.resolve(), os.major(observed.st_dev), os.minor(observed.st_dev),
            observed.st_ino + 1,
        )
