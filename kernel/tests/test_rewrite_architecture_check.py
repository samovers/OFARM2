"""Regression tests for the rewrite architecture gate."""

import ast
import inspect
import os
import types
from pathlib import Path

import pytest

from conformance import rewrite_architecture_check


@pytest.mark.parametrize(
    "source,expected_line",
    [
        ("import os\nos.getenv('SETTING')\n", 2),
        ("import os\nos.environ.get('SETTING')\n", 2),
        ("import os as environment\nenvironment.environ['SETTING']\n", 2),
        ("from os import getenv\ngetenv('SETTING')\n", 2),
        (
            "from os import environ as environment\nenvironment.get('SETTING')\n",
            2,
        ),
    ],
)
def test_environment_reads_detect_import_styles(source, expected_line):
    tree = ast.parse(source)

    assert rewrite_architecture_check._environment_reads(tree) == [expected_line]


def test_environment_reads_ignore_environment_free_modules():
    tree = ast.parse("def value():\n    return 'static'\n")

    assert rewrite_architecture_check._environment_reads(tree) == []


@pytest.mark.parametrize(
    "source",
    [
        "import importlib as loader\n",
        "import importlib.util\n",
        "from importlib import import_module as load\n",
        "from builtins import __import__ as load\n",
        "load = __import__\n",
        "builtins.__import__('kernel.store')\n",
        "getattr(builtins, '__import__')('kernel.store')\n",
        "builtins.__dict__['__import__']('kernel.store')\n",
        (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    class Loader:\n"
            "        def load(self):\n"
            "            return __import__('kernel.store')\n"
        ),
    ],
    ids=[
        "importlib-alias",
        "importlib-submodule",
        "importlib-from-alias",
        "builtins-from-alias",
        "builtin-reference",
        "builtins-attribute",
        "getattr-literal",
        "subscript-literal",
        "nested-type-checking",
    ],
)
def test_dynamic_import_direct_forms_are_rejected(source):
    violations = rewrite_architecture_check._dynamic_import_violations(
        ast.parse(source)
    )

    assert violations


def test_dynamic_import_check_does_not_track_general_function_flow():
    tree = ast.parse(
        "loader = allowed_loader\n"
        "loader('kernel.store')\n"
    )

    assert rewrite_architecture_check._dynamic_import_violations(tree) == []


@pytest.mark.parametrize(
    "source",
    [
        "import importlib\n",
        "factory = compile(source, path, 'exec')\n",
        "builtins.exec(code)\n",
        "sys.modules['provider'] = module\n",
        "sys.modules['provider'], other = module, value\n",
        "del sys.modules['provider']\n",
        "sys.modules.update({'provider': module})\n",
    ],
    ids=[
        "importlib",
        "compile",
        "exec",
        "module-assignment",
        "module-unpack-assignment",
        "module-deletion",
        "module-update",
    ],
)
def test_provider_import_policy_rejects_direct_loader_bypasses(source):
    violations = (
        rewrite_architecture_check._provider_import_policy_violations(
            ast.parse(source)
        )
    )

    assert violations


def test_provider_import_policy_allows_read_only_module_attestation():
    tree = ast.parse("module = sys.modules.get(module_name)\n")

    assert (
        rewrite_architecture_check._provider_import_policy_violations(tree)
        == []
    )


@pytest.mark.parametrize(
    "source",
    [
        "from kernel.profiles.si_ffs.outputs import SIOutputAssembler\n",
        "from .profiles import si_ffs\n",
        "binding = SIReferenceBindings()\n",
        "specification = SI_OUTPUT_SPECIFICATION\n",
        "specification = SI_MATERIALIZATION_SPECIFICATION\n",
        (
            "from . import profiles\n"
            "specification = profiles.si_ffs.outputs.SI_OUTPUT_SPECIFICATION\n"
        ),
        "PROFILE = 'PROFILE:SI.FFS.RECORDKEEPING.V0_1'\n",
        (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    PROFILE = 'profile:si.ffs.recordkeeping.v0_1'\n"
        ),
    ],
)
def test_profile_neutral_modules_reject_si_dependencies_and_literals(source):
    assert rewrite_architecture_check._profile_neutrality_violations(
        ast.parse(source)
    )


@pytest.mark.parametrize(
    "source",
    [
        "SIZE_LIMIT = 10\n",
        "SIGNATURE = 'sha256'\n",
        "SIGNAL = object()\n",
    ],
)
def test_profile_neutral_modules_allow_ordinary_si_prefix_names(source):
    assert (
        rewrite_architecture_check._profile_neutrality_violations(
            ast.parse(source)
        )
        == []
    )


@pytest.mark.parametrize(
    "source",
    [
        "import importlib\n",
        "from importlib.util import spec_from_file_location\n",
        "code = compile(source, path, 'exec')\n",
        "exec(code, namespace)\n",
        "sys.modules[name] = module\n",
        "factory = __import__('kernel.profiles.si_ffs.runtime_provider')\n",
    ],
)
def test_profile_loader_rejects_second_module_execution_primitives(source):
    assert rewrite_architecture_check._profile_loader_violations(
        ast.parse(source)
    )


def test_profile_loader_allows_one_literal_normal_import():
    tree = ast.parse(
        "def resolve():\n"
        "    from kernel.profiles.si_ffs.runtime_provider import build\n"
        "    return build\n"
    )

    assert rewrite_architecture_check._profile_loader_violations(tree) == []


def _write_module(root: Path, relative: str, source: str = "") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _required_snapshot_roots(root: Path) -> None:
    descriptor = rewrite_architecture_check._FIXED_DESCRIPTOR_V1
    for module in (
        *descriptor.production_import_roots,
        *descriptor.legacy_import_roots,
    ):
        _write_module(root, f"{module.replace('.', '/')}.py")


def _firewall_tree(tmp_path: Path, api_source: str) -> None:
    _write_module(tmp_path, "kernel/__init__.py")
    _required_snapshot_roots(tmp_path)
    _write_module(tmp_path, "kernel/api.py", api_source)
    for module in (
        *rewrite_architecture_check.PROFILE_NEUTRAL_MODULES,
        rewrite_architecture_check.PROFILE_LOADER_MODULE,
    ):
        _write_module(tmp_path, f"{module.replace('.', '/')}.py")


@pytest.mark.parametrize(
    "module",
    [
        *rewrite_architecture_check.PROFILE_NEUTRAL_MODULES,
        rewrite_architecture_check.PROFILE_LOADER_MODULE,
    ],
)
def test_firewall_rejects_missing_required_profile_modules(tmp_path, module):
    _firewall_tree(tmp_path, "")
    (tmp_path / f"{module.replace('.', '/')}.py").unlink()

    descriptor = rewrite_architecture_check._FIXED_DESCRIPTOR_V1
    if module in descriptor.legacy_import_roots:
        with pytest.raises(
            rewrite_architecture_check.PythonSourceSnapshotRefusal,
        ) as refused:
            rewrite_architecture_check._check_import_firewall(tmp_path)
        assert refused.value.code is (
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .MISSING_REQUIRED_IMPORT_ROOT
        )
        return

    if module == rewrite_architecture_check.PROFILE_LOADER_MODULE:
        expected = (
            f"required profile provider loader module {module!r} is missing"
        )
    else:
        expected = f"required profile-neutral module {module!r} is missing"

    assert rewrite_architecture_check._check_import_firewall(tmp_path) == [
        expected
    ]


def _provider_policy_tree(
    tmp_path: Path,
    *,
    loader_source: str = "",
    policy_source: str = "",
) -> None:
    _write_module(tmp_path, "kernel/__init__.py")
    _required_snapshot_roots(tmp_path)
    _write_module(
        tmp_path,
        "kernel/profile_runtime_provider.py",
        loader_source,
    )
    _write_module(
        tmp_path,
        "kernel/provider_import_policy.py",
        policy_source,
    )


def test_provider_import_policy_reports_file_and_line(tmp_path):
    _provider_policy_tree(
        tmp_path,
        loader_source="value = 1\nbuiltins.exec(code)\n",
    )

    assert rewrite_architecture_check._check_provider_import_policy(
        tmp_path
    ) == [
        "kernel/profile_runtime_provider.py:2: forbidden provider import "
        "mechanism (attribute reference to 'exec')"
    ]


def test_provider_import_policy_requires_both_modules(tmp_path):
    _provider_policy_tree(tmp_path)
    (tmp_path / "kernel/provider_import_policy.py").unlink()

    assert rewrite_architecture_check._check_provider_import_policy(
        tmp_path
    ) == [
        "required provider import policy module "
        "'kernel.provider_import_policy' is missing"
    ]


def test_firewall_reports_indirect_dynamic_import_path(tmp_path):
    _firewall_tree(tmp_path, "from .helper import value\n")
    _write_module(tmp_path, "kernel/helper.py", "import importlib\nvalue = 1\n")

    assert rewrite_architecture_check._check_import_firewall(tmp_path) == [
        "kernel/helper.py:1: forbidden dynamic import mechanism "
        "(import of 'importlib'); production import path "
        "kernel.api -> kernel.helper"
    ]


def test_firewall_reports_indirect_legacy_import_path(tmp_path):
    _firewall_tree(tmp_path, "from .helper import value\n")
    _write_module(tmp_path, "kernel/helper.py", "from .store import Store\n")
    _write_module(tmp_path, "kernel/store.py", "class Store:\n    pass\n")

    assert rewrite_architecture_check._check_import_firewall(tmp_path) == [
        "kernel/helper.py:1: production import path "
        "kernel.api -> kernel.helper -> kernel.store reaches legacy module "
        "'kernel.store'"
    ]


def test_firewall_rejects_exact_runtime_bundle_repository_import(tmp_path):
    assert "kernel.runtime_bundle_repository" in (
        rewrite_architecture_check.LEGACY_MODULES
    )
    assert rewrite_architecture_check._is_legacy_module(
        "kernel.runtime_bundle_repository"
    )
    assert not rewrite_architecture_check._is_legacy_module(
        "kernel.runtime_bundle"
    )

    _firewall_tree(
        tmp_path,
        "from .runtime_bundle_repository import RuntimeBundleRepository\n",
    )
    _write_module(
        tmp_path,
        "kernel/runtime_bundle_repository.py",
        "class RuntimeBundleRepository:\n    pass\n",
    )

    assert rewrite_architecture_check._check_import_firewall(tmp_path) == [
        "kernel/api.py:1: production import path kernel.api -> "
        "kernel.runtime_bundle_repository reaches legacy module "
        "'kernel.runtime_bundle_repository'"
    ]


def test_firewall_rejects_prototype_schema_reference(tmp_path):
    _firewall_tree(tmp_path, "from .helper import SCHEMA\n")
    _write_module(tmp_path, "kernel/helper.py", "SCHEMA = 'schema.sql'\n")

    assert rewrite_architecture_check._check_import_firewall(tmp_path) == [
        "kernel/helper.py:1: production references legacy resource "
        "'schema.sql'; production import path kernel.api -> kernel.helper"
    ]


def test_firewall_rejects_legacy_reverse_import(tmp_path):
    _firewall_tree(tmp_path, "")
    _write_module(tmp_path, "kernel/legacy_m1/__init__.py")
    _write_module(
        tmp_path,
        "kernel/legacy_m1/api.py",
        "from kernel.application_runtime import ApplicationRuntime\n",
    )
    _write_module(tmp_path, "kernel/legacy_m1/runtime.py")

    assert rewrite_architecture_check._check_import_firewall(tmp_path) == [
        "kernel/legacy_m1/api.py:1: legacy import path "
        "kernel.legacy_m1.api -> kernel.application_runtime reaches "
        "production composition module 'kernel.application_runtime'"
    ]


def test_dynamic_import_in_legacy_only_module_is_outside_production_rule(
    tmp_path,
):
    _firewall_tree(tmp_path, "")
    _write_module(tmp_path, "kernel/legacy_m1/__init__.py")
    _write_module(
        tmp_path,
        "kernel/legacy_m1/api.py",
        "import importlib\n",
    )
    _write_module(tmp_path, "kernel/legacy_m1/runtime.py")

    assert rewrite_architecture_check._check_import_firewall(tmp_path) == []


def _snapshot_tree(
    tmp_path: Path,
    sources: dict[str, str] | None = None,
) -> Path:
    _required_snapshot_roots(tmp_path)
    for relative, source in (sources or {}).items():
        _write_module(tmp_path, relative, source)
    return tmp_path


def _assert_refusal(
    expected: rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1,
    build,
) -> rewrite_architecture_check.PythonSourceSnapshotRefusal:
    with pytest.raises(
        rewrite_architecture_check.PythonSourceSnapshotRefusal,
    ) as refused:
        build()
    assert refused.value.code is expected
    return refused.value


_BOOTSTRAP_CAPABILITY_CASES = (
    *(('callable', name) for name in (
        "close", "fstat", "open", "read", "scandir", "stat"
    )),
    *(('flag', name) for name in (
        "O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW", "O_RDONLY"
    )),
    ("supports_dir_fd", "open"),
    ("supports_dir_fd", "stat"),
    ("supports_follow_symlinks", "stat"),
    ("supports_fd", "scandir"),
)


def _remove_bootstrap_capability(monkeypatch, kind, name):
    operation = getattr(rewrite_architecture_check.os, name)
    if kind == "callable":
        monkeypatch.setattr(rewrite_architecture_check.os, name, None)
    elif kind == "flag":
        monkeypatch.delattr(rewrite_architecture_check.os, name)
    else:
        supported = getattr(rewrite_architecture_check.os, kind)
        monkeypatch.setattr(
            rewrite_architecture_check.os,
            kind,
            supported - {operation},
        )


def test_snapshot_public_contract_is_exact_and_immutable(tmp_path):
    root = _snapshot_tree(tmp_path)
    snapshot = rewrite_architecture_check.build_python_source_snapshot(root)

    assert list(inspect.signature(
        rewrite_architecture_check.build_python_source_snapshot
    ).parameters) == ["root"]
    with pytest.raises(TypeError):
        rewrite_architecture_check.build_python_source_snapshot(
            root,
            descriptor=object(),
        )
    assert set(rewrite_architecture_check.PythonSourceSnapshotV1.__slots__) == {
        "_ast_copy_calls",
        "_builder_seal",
        "_contract_authority",
        "_content_sha256",
        "_descriptor",
        "_import_graph",
        "_legacy_reachability",
        "_modules_by_name",
        "_modules_by_relative_path",
        "_private_asts",
        "_production_reachability",
        "_root_path",
        "_source_file_count",
        "_total_ast_nodes",
        "_total_import_edges",
        "_total_source_bytes",
    }
    assert snapshot.contract_authority == (
        rewrite_architecture_check.PythonSourceContractAuthorityV1(
            "ofarm.architecture-python-source-snapshot-admission.issue176.v0.1",
            "docs/rfcs/"
            "OFARM_Architecture_Python_Source_Snapshot_Admission_RFC_v0_1.md",
            82_758,
            "sha256:6e4307077525f2bbb48992fa4c652ab75d279875063bd715c"
            "f21dc1f1d3216d5",
        )
    )
    assert snapshot.descriptor.production_import_roots == (
        "kernel.api",
        "kernel.application_runtime",
    )
    assert snapshot.descriptor.legacy_import_roots == (
        "kernel.legacy_m1.api",
        "kernel.legacy_m1.runtime",
    )
    assert snapshot.descriptor._fields == (
        "interface_identity",
        "python_implementation",
        "python_version",
        "ast_feature_version",
        "filesystem_profile",
        "filesystem_encoding",
        "filesystem_errors",
        "encoding",
        "included_suffix",
        "excluded_component_exact",
        "excluded_component_prefix",
        "module_naming",
        "source_acquisition",
        "graph_semantics",
        "production_import_roots",
        "legacy_import_roots",
        "maximum_source_files",
        "maximum_source_bytes_per_file",
        "maximum_total_source_bytes",
        "maximum_root_path_bytes",
        "maximum_root_components",
        "maximum_inventory_directories",
        "maximum_inventory_entries",
        "maximum_inventory_depth",
        "maximum_relative_path_bytes",
        "maximum_ast_nodes_per_file",
        "maximum_total_ast_nodes",
        "maximum_ast_depth",
        "maximum_import_edges_per_module",
        "maximum_total_import_edges",
        "maximum_ast_copy_calls",
    )
    assert snapshot.contract_authority._fields == (
        "contract_identity",
        "rfc_relative_path",
        "byte_length",
        "sha256",
    )
    assert next(iter(snapshot.modules_by_name.values()))._fields == (
        "module_name",
        "relative_path",
        "source_bytes",
        "source_text",
        "byte_length",
        "sha256",
        "ast_node_count",
        "ast_depth",
    )
    assert rewrite_architecture_check.PythonImportEdgeV1._fields == (
        "line",
        "target",
    )
    assert snapshot.source_file_count == 4
    assert type(snapshot.modules_by_name) is types.MappingProxyType
    assert type(snapshot.import_graph) is types.MappingProxyType
    assert snapshot.content_sha256.startswith("sha256:")
    assert len(snapshot.content_sha256) == 71
    with pytest.raises(TypeError):
        rewrite_architecture_check.PythonSourceSnapshotV1()
    with pytest.raises(AttributeError):
        snapshot.source_file_count = 0
    with pytest.raises(TypeError):
        snapshot.modules_by_name["caller"] = object()
    for record in (
        snapshot.descriptor,
        snapshot.contract_authority,
        next(iter(snapshot.modules_by_name.values())),
        rewrite_architecture_check.PythonImportEdgeV1(1, "kernel.api"),
    ):
        with pytest.raises(AttributeError):
            record.interface_identity = "caller"  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            object.__setattr__(record, record._fields[0], "caller")


def test_only_builder_seals_snapshot_evidence(tmp_path):
    snapshot = rewrite_architecture_check.build_python_source_snapshot(
        _snapshot_tree(tmp_path)
    )
    assert not hasattr(snapshot, "_initialize")

    shell = object.__new__(
        rewrite_architecture_check.PythonSourceSnapshotV1
    )
    object.__setattr__(shell, "_builder_seal", True)
    with pytest.raises(TypeError):
        shell.ast_for("kernel.api")

    copied_seal_shell = object.__new__(
        rewrite_architecture_check.PythonSourceSnapshotV1
    )
    object.__setattr__(
        copied_seal_shell,
        "_builder_seal",
        object.__getattribute__(snapshot, "_builder_seal"),
    )
    with pytest.raises(TypeError):
        copied_seal_shell.ast_for("kernel.api")

    original_count = snapshot.source_file_count
    object.__setattr__(snapshot, "_source_file_count", original_count + 1)
    with pytest.raises(TypeError):
        snapshot.ast_for("kernel.api")
    assert not any(
        name in {"_initialize", "initialize", "seal", "reinitialize"}
        for name, _member in inspect.getmembers(
            rewrite_architecture_check.PythonSourceSnapshotV1
        )
    )


def test_refusal_vocabulary_is_closed():
    assert [
        member.value
        for member in rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
    ] == [
        "CONTRACT_AUTHORITY_MISMATCH",
        "UNSUPPORTED_PYTHON_IMPLEMENTATION",
        "UNSUPPORTED_PYTHON_VERSION",
        "UNSUPPORTED_AST_FEATURE_VERSION",
        "UNSUPPORTED_FILESYSTEM_PROFILE",
        "INVALID_ROOT",
        "SYMLINK_COMPONENT",
        "NON_DIRECTORY_COMPONENT",
        "NON_REGULAR_SOURCE",
        "DUPLICATE_FILE_IDENTITY",
        "EMPTY_MODULE_NAME",
        "DUPLICATE_MODULE_NAME",
        "SOURCE_ACQUISITION_FAILED",
        "SOURCE_CHANGED",
        "INVENTORY_CHANGED",
        "INVALID_PATH_ENCODING",
        "INVALID_UTF8",
        "INVALID_PYTHON_SYNTAX",
        "MISSING_REQUIRED_IMPORT_ROOT",
        "RESOURCE_LIMIT_EXCEEDED",
        "AST_COPY_LIMIT_EXCEEDED",
        "UNSUPPORTED_REACHABILITY_ROOTS",
    ]


def test_complete_contract_mismatch_precedes_caller_root(
    tmp_path,
    monkeypatch,
):
    _snapshot_tree(tmp_path)
    observed = []
    real_open = rewrite_architecture_check._open_absolute_directory
    real_digest = rewrite_architecture_check._PYTHON_SOURCE_SNAPSHOT_RFC_SHA256
    real_length = rewrite_architecture_check._PYTHON_SOURCE_SNAPSHOT_RFC_BYTE_LENGTH
    real_root = rewrite_architecture_check.ROOT

    def tracking_open(root, *, authority_path):
        observed.append((root, authority_path))
        return real_open(root, authority_path=authority_path)

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_PYTHON_SOURCE_SNAPSHOT_RFC_SHA256",
        "sha256:" + "0" * 64,
    )
    monkeypatch.setattr(
        rewrite_architecture_check,
        "_open_absolute_directory",
        tracking_open,
    )

    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .CONTRACT_AUTHORITY_MISMATCH,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            tmp_path
        ),
    )
    assert observed
    assert all(authority_path for _root, authority_path in observed)

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_PYTHON_SOURCE_SNAPSHOT_RFC_SHA256",
        real_digest,
    )
    monkeypatch.setattr(
        rewrite_architecture_check,
        "_PYTHON_SOURCE_SNAPSHOT_RFC_BYTE_LENGTH",
        real_length + 1,
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .CONTRACT_AUTHORITY_MISMATCH,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            tmp_path
        ),
    )

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_PYTHON_SOURCE_SNAPSHOT_RFC_BYTE_LENGTH",
        real_length,
    )
    missing_root = tmp_path / "missing-authority"
    missing_root.mkdir()
    monkeypatch.setattr(rewrite_architecture_check, "ROOT", missing_root)
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .CONTRACT_AUTHORITY_MISMATCH,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            tmp_path
        ),
    )

    linked_root = tmp_path / "linked-authority"
    linked_rfc = (
        linked_root
        / rewrite_architecture_check._PYTHON_SOURCE_SNAPSHOT_RFC_RELATIVE_PATH
    )
    linked_rfc.parent.mkdir(parents=True)
    linked_rfc.symlink_to(
        real_root
        / rewrite_architecture_check._PYTHON_SOURCE_SNAPSHOT_RFC_RELATIVE_PATH
    )
    monkeypatch.setattr(rewrite_architecture_check, "ROOT", linked_root)
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .CONTRACT_AUTHORITY_MISMATCH,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            tmp_path
        ),
    )
    assert all(authority_path for _root, authority_path in observed)


def test_bootstrap_failure_precedes_contract_and_caller(
    tmp_path,
    monkeypatch,
):
    _snapshot_tree(tmp_path)
    contract_called = False

    def forbidden_contract():
        nonlocal contract_called
        contract_called = True

    monkeypatch.setattr(rewrite_architecture_check.os, "scandir", None)
    monkeypatch.setattr(
        rewrite_architecture_check,
        "_authenticate_complete_contract",
        forbidden_contract,
    )

    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .UNSUPPORTED_FILESYSTEM_PROFILE,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            tmp_path
        ),
    )
    assert contract_called is False


@pytest.mark.parametrize(
    ("kind", "name"),
    _BOOTSTRAP_CAPABILITY_CASES,
    ids=lambda value: str(value).lower(),
)
def test_each_bootstrap_capability_refuses_independently(
    monkeypatch,
    kind,
    name,
):
    contract_called = False

    def forbidden_contract():
        nonlocal contract_called
        contract_called = True

    _remove_bootstrap_capability(monkeypatch, kind, name)
    monkeypatch.setattr(
        rewrite_architecture_check,
        "_authenticate_complete_contract",
        forbidden_contract,
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .UNSUPPORTED_FILESYSTEM_PROFILE,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            Path("/caller-must-not-be-inspected")
        ),
    )
    assert contract_called is False


@pytest.mark.parametrize(
    ("kind", "name"),
    _BOOTSTRAP_CAPABILITY_CASES,
    ids=lambda value: str(value).lower(),
)
def test_each_full_profile_capability_refuses_after_contract(
    tmp_path,
    monkeypatch,
    kind,
    name,
):
    root = _snapshot_tree(tmp_path)
    contract_called = False

    def contract_then_remove():
        nonlocal contract_called
        contract_called = True
        _remove_bootstrap_capability(monkeypatch, kind, name)

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_authenticate_complete_contract",
        contract_then_remove,
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .UNSUPPORTED_FILESYSTEM_PROFILE,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )
    assert contract_called is True


@pytest.mark.parametrize(
    "field",
    ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns"),
)
def test_each_required_stat_field_refuses_independently(
    tmp_path,
    monkeypatch,
    field,
):
    root = _snapshot_tree(tmp_path)
    fields = {
        name: None
        for name in (
            "st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns"
        )
        if name != field
    }
    monkeypatch.setattr(
        rewrite_architecture_check.os,
        "stat_result",
        type("IncompleteStatResult", (), fields),
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .UNSUPPORTED_FILESYSTEM_PROFILE,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )


@pytest.mark.parametrize(
    ("target", "replacement", "expected"),
    [
        (
            "python_implementation",
            lambda: "PyPy",
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .UNSUPPORTED_PYTHON_IMPLEMENTATION,
        ),
        (
            "ast_feature",
            lambda: (3, 11),
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .UNSUPPORTED_AST_FEATURE_VERSION,
        ),
        (
            "filesystem_encoding",
            lambda: "ascii",
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .UNSUPPORTED_FILESYSTEM_PROFILE,
        ),
        (
            "filesystem_errors",
            lambda: "strict",
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .UNSUPPORTED_FILESYSTEM_PROFILE,
        ),
        (
            "os_name",
            lambda: "nt",
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .UNSUPPORTED_FILESYSTEM_PROFILE,
        ),
    ],
    ids=[
        "python-implementation",
        "ast-feature",
        "filesystem-encoding",
        "filesystem-errors",
        "os-name",
    ],
)
def test_full_profile_refuses_before_caller_root(
    tmp_path,
    monkeypatch,
    target,
    replacement,
    expected,
):
    _snapshot_tree(tmp_path)
    if target == "python_implementation":
        monkeypatch.setattr(
            rewrite_architecture_check.platform,
            "python_implementation",
            replacement,
        )
    elif target == "ast_feature":
        monkeypatch.setattr(
            rewrite_architecture_check,
            "_runtime_ast_feature_version",
            replacement,
        )
    elif target == "filesystem_encoding":
        monkeypatch.setattr(
            rewrite_architecture_check.sys,
            "getfilesystemencoding",
            replacement,
        )
    elif target == "filesystem_errors":
        monkeypatch.setattr(
            rewrite_architecture_check.sys,
            "getfilesystemencodeerrors",
            replacement,
        )
    else:
        monkeypatch.setattr(
            rewrite_architecture_check.os,
            "name",
            replacement(),
        )
    observed_caller = False
    real_open = rewrite_architecture_check._open_absolute_directory

    def tracking_open(root, *, authority_path):
        nonlocal observed_caller
        if not authority_path:
            observed_caller = True
        return real_open(root, authority_path=authority_path)

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_open_absolute_directory",
        tracking_open,
    )

    _assert_refusal(
        expected,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            tmp_path
        ),
    )
    assert observed_caller is False


def test_wrong_python_patch_refuses_before_caller_root(tmp_path, monkeypatch):
    _snapshot_tree(tmp_path)
    monkeypatch.setattr(
        rewrite_architecture_check.sys,
        "version_info",
        (3, 12, 12),
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .UNSUPPORTED_PYTHON_VERSION,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            tmp_path
        ),
    )


def test_invalid_and_symlink_roots_refuse(tmp_path):
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1.INVALID_ROOT,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            Path("relative")
        ),
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1.INVALID_ROOT,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            tmp_path / "absent"
        ),
    )
    non_directory = tmp_path / "file"
    non_directory.write_text("not a directory", encoding="utf-8")
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1.INVALID_ROOT,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            non_directory
        ),
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .NON_DIRECTORY_COMPONENT,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            non_directory / "child"
        ),
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .INVALID_PATH_ENCODING,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            Path("/\udcff")
        ),
    )
    real_root = _snapshot_tree(tmp_path / "real")
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real_root, target_is_directory=True)
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .SYMLINK_COMPONENT,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            linked_root
        ),
    )


@pytest.mark.parametrize(
    "root",
    (
        Path("/" + "a" * 1_025),
        Path("/" + "é" * 600),
        Path("/" + "/".join("part" for _ in range(65))),
    ),
    ids=("lexical-code-points", "encoded-bytes", "components"),
)
def test_each_caller_root_bound_refuses_before_ancestor_custody(
    root,
    monkeypatch,
):
    opened = False

    def forbidden_open(*_args, **_kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("caller-root custody must not start")

    def contract_then_forbid_open():
        monkeypatch.setattr(
            rewrite_architecture_check.os,
            "open",
            forbidden_open,
        )

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_authenticate_complete_contract",
        contract_then_forbid_open,
    )
    monkeypatch.setattr(
        rewrite_architecture_check,
        "_authenticate_full_execution_profile",
        lambda: None,
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )
    assert opened is False


def test_inventory_refuses_links_kinds_and_duplicate_identity(tmp_path):
    root = _snapshot_tree(tmp_path)
    (root / "linked.py").symlink_to(root / "kernel/api.py")
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .SYMLINK_COMPONENT,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )
    (root / "linked.py").unlink()
    os.mkfifo(root / "pipe.py")
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .NON_REGULAR_SOURCE,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )
    (root / "pipe.py").unlink()
    os.link(root / "kernel/api.py", root / "duplicate.py")
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .DUPLICATE_FILE_IDENTITY,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )


def test_inventory_refuses_module_collisions_empty_names_and_missing_roots(
    tmp_path,
):
    collision = _snapshot_tree(tmp_path / "collision")
    _write_module(collision, "package.py")
    _write_module(collision, "package/__init__.py")
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .DUPLICATE_MODULE_NAME,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            collision
        ),
    )
    empty = _snapshot_tree(tmp_path / "empty")
    _write_module(empty, "__init__.py")
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .EMPTY_MODULE_NAME,
        lambda: rewrite_architecture_check.build_python_source_snapshot(empty),
    )
    descriptor = rewrite_architecture_check._FIXED_DESCRIPTOR_V1
    roots = (
        *descriptor.production_import_roots,
        *descriptor.legacy_import_roots,
    )
    for index, module in enumerate(roots):
        missing = _snapshot_tree(tmp_path / f"missing-{index}")
        (missing / f"{module.replace('.', '/')}.py").unlink()
        _assert_refusal(
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .MISSING_REQUIRED_IMPORT_ROOT,
            lambda missing=missing: (
                rewrite_architecture_check.build_python_source_snapshot(
                    missing
                )
            ),
        )


def test_hidden_and_cache_sources_are_excluded(tmp_path):
    root = _snapshot_tree(tmp_path)
    _write_module(root, ".hidden.py", "this is not syntax")
    _write_module(root, "kernel/__pycache__/ignored.py", "this is not syntax")
    snapshot = rewrite_architecture_check.build_python_source_snapshot(root)

    assert ".hidden" not in snapshot.modules_by_name
    assert "kernel.__pycache__.ignored" not in snapshot.modules_by_name


def test_test_family_sources_are_included_without_exception(tmp_path):
    root = _snapshot_tree(tmp_path)
    _write_module(root, "kernel/tests/test_example.py", "value = 1\n")
    _write_module(root, "profile_si_ffs/tests/test_example.py", "value = 2\n")
    snapshot = rewrite_architecture_check.build_python_source_snapshot(root)

    assert "kernel.tests.test_example" in snapshot.modules_by_name
    assert "profile_si_ffs.tests.test_example" in snapshot.modules_by_name


def test_invalid_raw_path_bytes_refuse_through_public_builder(tmp_path):
    root = _snapshot_tree(tmp_path)
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    invalid_fd = -1
    try:
        try:
            invalid_fd = os.open(
                b"\xff.py",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=root_fd,
            )
        except OSError as exc:
            pytest.skip(
                f"filesystem cannot create undecodable POSIX name: {exc}"
            )
        os.write(invalid_fd, b"value = 1\n")
    finally:
        if invalid_fd >= 0:
            os.close(invalid_fd)
        os.close(root_fd)

    refused = _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .INVALID_PATH_ENCODING,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )
    assert refused.relative_path is None


@pytest.mark.parametrize(
    ("relative", "source", "expected"),
    [
        (
            "invalid_utf8.py",
            b"\xff",
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .INVALID_UTF8,
        ),
        (
            "invalid_syntax.py",
            b"def broken(:\n",
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .INVALID_PYTHON_SYNTAX,
        ),
        (
            "too_large.py",
            b"#" * 524_289,
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .RESOURCE_LIMIT_EXCEEDED,
        ),
    ],
    ids=["invalid-utf8", "invalid-syntax", "source-size"],
)
def test_source_text_and_size_refusals(tmp_path, relative, source, expected):
    root = _snapshot_tree(tmp_path)
    (root / relative).write_bytes(source)
    _assert_refusal(
        expected,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )


def test_path_depth_and_relative_byte_limits_refuse(tmp_path):
    deep = _snapshot_tree(tmp_path / "deep")
    _write_module(deep, "/".join(["part"] * 17) + "/source.py")
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(deep),
    )
    long_path = _snapshot_tree(tmp_path / "long")
    _write_module(
        long_path,
        f"{'a' * 100}/{'b' * 100}/{'c' * 60}.py",
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            long_path
        ),
    )


def test_file_and_entry_count_limits_refuse_before_source_reads(
    tmp_path,
    monkeypatch,
):
    files = _snapshot_tree(tmp_path / "files")
    for index in range(509):
        _write_module(files, f"extra_{index:03d}.py")
    acquired = False
    real_acquire = rewrite_architecture_check._acquire_source

    def tracking_acquire(root_fd, candidate):
        nonlocal acquired
        acquired = True
        return real_acquire(root_fd, candidate)

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_acquire_source",
        tracking_acquire,
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(files),
    )
    assert acquired is False

    entries = _snapshot_tree(tmp_path / "entries")
    for index in range(2_045):
        (entries / f"ignored_{index:04d}.txt").touch()
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            entries
        ),
    )


def test_directory_257_refuses_before_source_reads(tmp_path, monkeypatch):
    root = _snapshot_tree(tmp_path)
    for index in range(254):
        (root / f"directory_{index:03d}").mkdir()
    acquired = False

    def forbidden_acquire(*_args, **_kwargs):
        nonlocal acquired
        acquired = True
        raise AssertionError("pre-inventory breach must precede reads")

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_acquire_source",
        forbidden_acquire,
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )
    assert acquired is False


def test_declared_total_source_byte_limit_refuses_before_reads(
    tmp_path,
    monkeypatch,
):
    root = _snapshot_tree(tmp_path)
    for index in range(17):
        path = root / f"large_{index:02d}.py"
        path.touch()
        path.write_bytes(b"")
        os.truncate(path, 524_288)
    acquired = False

    def forbidden_acquire(*_args, **_kwargs):
        nonlocal acquired
        acquired = True
        raise AssertionError("declared-size breach must precede reads")

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_acquire_source",
        forbidden_acquire,
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )
    assert acquired is False


def test_post_inventory_limit_retains_resource_limit_meaning(
    tmp_path,
    monkeypatch,
):
    root = _snapshot_tree(tmp_path)
    real_inventory = rewrite_architecture_check._bounded_inventory
    calls = 0

    def second_inventory_is_tightly_bounded(root_fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            monkeypatch.setattr(
                rewrite_architecture_check,
                "_FIXED_DESCRIPTOR_V1",
                rewrite_architecture_check._FIXED_DESCRIPTOR_V1._replace(
                    maximum_inventory_entries=3,
                ),
            )
        return real_inventory(root_fd)

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_bounded_inventory",
        second_inventory_is_tightly_bounded,
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )
    assert calls == 2


def test_ast_and_import_edge_limits_refuse(tmp_path):
    ast_root = _snapshot_tree(tmp_path / "ast")
    constants = ",".join("1" for _ in range(65_533))
    _write_module(ast_root, "large_ast.py", f"value = ({constants})\n")
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            ast_root
        ),
    )

    edge_root = _snapshot_tree(tmp_path / "edges")
    names = [f"edge_{index:03d}" for index in range(129)]
    for name in names:
        _write_module(edge_root, f"{name}.py")
    _write_module(
        edge_root,
        "kernel/api.py",
        "".join(f"import {name}\n" for name in names),
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            edge_root
        ),
    )


def test_ast_depth_limit_refuses(tmp_path):
    root = _snapshot_tree(tmp_path)
    _write_module(root, "deep_ast.py", "value = " + "[" * 65 + "0" + "]" * 65)
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )


def test_total_ast_node_limit_refuses(tmp_path):
    root = _snapshot_tree(tmp_path)
    constants = ",".join("1" for _ in range(58_300))
    for index in range(18):
        _write_module(
            root,
            f"ast_total_{index:02d}.py",
            f"values = ({constants})\n",
        )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )


def test_total_import_edge_limit_refuses(tmp_path):
    root = _snapshot_tree(tmp_path)
    targets = [f"target_{index:03d}" for index in range(128)]
    for target in targets:
        _write_module(root, f"{target}.py")
    source = "".join(f"import {target}\n" for target in targets)
    for index in range(33):
        _write_module(root, f"importer_{index:02d}.py", source)
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )


def test_source_and_inventory_changes_refuse_without_partial_snapshot(
    tmp_path,
    monkeypatch,
):
    source_root = _snapshot_tree(tmp_path / "source")
    real_acquire = rewrite_architecture_check._acquire_source
    changed = False

    def changing_acquire(root_fd, candidate):
        nonlocal changed
        retained = real_acquire(root_fd, candidate)
        if not changed:
            changed = True
            path = source_root / candidate[0]
            path.write_bytes(path.read_bytes() + b"\n")
        return retained

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_acquire_source",
        changing_acquire,
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .INVENTORY_CHANGED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            source_root
        ),
    )

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_acquire_source",
        real_acquire,
    )
    inventory_root = _snapshot_tree(tmp_path / "inventory")
    added = False

    def adding_acquire(root_fd, candidate):
        nonlocal added
        retained = real_acquire(root_fd, candidate)
        if not added:
            added = True
            _write_module(inventory_root, "added.py")
        return retained

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_acquire_source",
        adding_acquire,
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .INVENTORY_CHANGED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(
            inventory_root
        ),
    )


def test_stable_eof_size_change_refuses_as_source_changed(
    tmp_path,
    monkeypatch,
):
    root = _snapshot_tree(
        tmp_path,
        {"kernel/api.py": "value = 1\n"},
    )
    real_read = rewrite_architecture_check._read_descriptor_once

    def shortened_source(fd, maximum_bytes):
        retained = real_read(fd, maximum_bytes)
        if maximum_bytes != 82_758 and retained:
            return retained[:-1]
        return retained

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_read_descriptor_once",
        shortened_source,
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .SOURCE_CHANGED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )


@pytest.mark.parametrize(
    ("transition", "expected"),
    (
        (
            "deleted",
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .INVENTORY_CHANGED,
        ),
        (
            "renamed",
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .INVENTORY_CHANGED,
        ),
        (
            "replaced-inode",
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .SOURCE_CHANGED,
        ),
        (
            "relinked",
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .SOURCE_CHANGED,
        ),
        (
            "symlink-kind",
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .SOURCE_CHANGED,
        ),
        (
            "fifo-kind",
            rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
            .SOURCE_CHANGED,
        ),
    ),
)
def test_candidate_transitions_during_acquisition_refuse(
    tmp_path,
    monkeypatch,
    transition,
    expected,
):
    root = _snapshot_tree(tmp_path)
    real_acquire = rewrite_architecture_check._acquire_source
    changed = False

    def transition_then_acquire(root_fd, candidate):
        nonlocal changed
        if not changed:
            changed = True
            path = root / candidate[0]
            other = root / "kernel/application_runtime.py"
            if transition == "deleted":
                path.unlink()
            elif transition == "renamed":
                path.rename(path.with_name("renamed.py"))
            elif transition == "replaced-inode":
                path.unlink()
                path.write_text("replacement = True\n", encoding="utf-8")
            elif transition == "relinked":
                path.unlink()
                os.link(other, path)
            elif transition == "symlink-kind":
                path.unlink()
                path.symlink_to(other)
            else:
                path.unlink()
                os.mkfifo(path)
        return real_acquire(root_fd, candidate)

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_acquire_source",
        transition_then_acquire,
    )
    refused = _assert_refusal(
        expected,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )
    assert refused.relative_path is not None


def test_parent_component_replacement_during_acquisition_refuses(
    tmp_path,
    monkeypatch,
):
    root = _snapshot_tree(tmp_path)
    real_acquire = rewrite_architecture_check._acquire_source
    changed = False

    def replace_parent_then_acquire(root_fd, candidate):
        nonlocal changed
        if not changed:
            changed = True
            (root / "kernel").rename(root / "kernel-before")
            (root / "kernel").mkdir()
        return real_acquire(root_fd, candidate)

    monkeypatch.setattr(
        rewrite_architecture_check,
        "_acquire_source",
        replace_parent_then_acquire,
    )
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .INVENTORY_CHANGED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )


def test_snapshot_is_detached_from_source_and_ast_mutation(tmp_path):
    root = _snapshot_tree(
        tmp_path,
        {"kernel/helper.py": "value = 1\n"},
    )
    snapshot = rewrite_architecture_check.build_python_source_snapshot(root)
    unit = snapshot.modules_by_name["kernel.helper"]
    first = snapshot.ast_for("kernel.helper")
    first.body.clear()
    second = snapshot.ast_for("kernel.helper")
    (root / unit.relative_path).write_text("value = 2\n", encoding="utf-8")

    assert second.body
    assert snapshot.modules_by_name["kernel.helper"] == unit
    assert unit.source_text == "value = 1\n"
    with pytest.raises(KeyError) as unknown:
        snapshot.ast_for("unknown")
    assert unknown.value.args == ("unknown",)


@pytest.mark.parametrize("failure", (MemoryError, RecursionError))
def test_bounded_parse_failures_refuse_without_partial_state(
    tmp_path,
    monkeypatch,
    failure,
):
    root = _snapshot_tree(tmp_path)

    def fail_parse(*_args, **_kwargs):
        raise failure()

    monkeypatch.setattr(rewrite_architecture_check.ast, "parse", fail_parse)
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: rewrite_architecture_check.build_python_source_snapshot(root),
    )


@pytest.mark.parametrize("failure", (MemoryError, RecursionError))
def test_bounded_ast_copy_failures_refuse_without_authority_change(
    tmp_path,
    monkeypatch,
    failure,
):
    snapshot = rewrite_architecture_check.build_python_source_snapshot(
        _snapshot_tree(tmp_path)
    )
    digest = snapshot.content_sha256

    def fail_copy(*_args, **_kwargs):
        raise failure()

    monkeypatch.setattr(rewrite_architecture_check.copy, "deepcopy", fail_copy)
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .RESOURCE_LIMIT_EXCEEDED,
        lambda: snapshot.ast_for("kernel.api"),
    )
    assert snapshot.content_sha256 == digest


def test_ast_copy_budget_refuses_at_fixed_limit(tmp_path):
    snapshot = rewrite_architecture_check.build_python_source_snapshot(
        _snapshot_tree(tmp_path)
    )

    for _ in range(512):
        snapshot.ast_for("kernel.api")
    _assert_refusal(
        rewrite_architecture_check.PythonSourceSnapshotRefusalCodeV1
        .AST_COPY_LIMIT_EXCEEDED,
        lambda: snapshot.ast_for("kernel.api"),
    )


@pytest.mark.parametrize(
    "name",
    (
        "_module_sources",
        "_import_graph",
        "_reachable_paths",
        "PRODUCTION_IMPORT_ROOTS",
        "LEGACY_IMPORT_ROOTS",
    ),
)
def test_temporary_snapshot_compatibility_names_are_removed(name):
    assert not hasattr(rewrite_architecture_check, name)


def test_static_graph_and_ordered_reachability_are_deterministic(tmp_path):
    sentinel = tmp_path / "executed"
    root = _snapshot_tree(
        tmp_path / "tree",
        {
            "kernel/api.py": (
                "from . import helper\n"
                "from kernel.helper import value\n"
            ),
            "kernel/application_runtime.py": "import kernel.helper\n",
            "kernel/helper.py": "from .sub import value\n",
            "kernel/sub.py": (
                "import importlib\n"
                f"open({str(sentinel)!r}, 'w').write('executed')\n"
                "value = 1\n"
            ),
        },
    )
    first = rewrite_architecture_check.build_python_source_snapshot(root)
    second = rewrite_architecture_check.build_python_source_snapshot(root)

    assert sentinel.exists() is False
    assert first == second
    assert first.content_sha256 == second.content_sha256
    assert first.import_graph["kernel.sub"] == ()
    assert first.import_graph["kernel.api"] == (
        rewrite_architecture_check.PythonImportEdgeV1(1, "kernel.helper"),
        rewrite_architecture_check.PythonImportEdgeV1(2, "kernel.helper"),
    )
    assert first.production_reachability["kernel.sub"] == (
        "kernel.api",
        "kernel.helper",
        "kernel.sub",
    )


def test_inventory_order_and_import_state_do_not_change_snapshot(
    tmp_path,
    monkeypatch,
):
    root = _snapshot_tree(
        tmp_path,
        {"kernel/api.py": "import kernel.helper\n", "kernel/helper.py": ""},
    )
    expected = rewrite_architecture_check.build_python_source_snapshot(root)
    real_scandir = rewrite_architecture_check.os.scandir

    class ReversedScandir:
        def __init__(self, fd):
            self._entries = list(real_scandir(fd))
            self._entries.reverse()

        def __enter__(self):
            return iter(self._entries)

        def __exit__(self, *_args):
            return False

    def reversed_scandir(fd):
        return ReversedScandir(fd)

    monkeypatch.setattr(
        rewrite_architecture_check.os,
        "scandir",
        reversed_scandir,
    )
    monkeypatch.setattr(
        rewrite_architecture_check.os,
        "supports_fd",
        rewrite_architecture_check.os.supports_fd | {reversed_scandir},
    )
    monkeypatch.setitem(
        rewrite_architecture_check.sys.modules,
        "kernel.api",
        object(),
    )
    monkeypatch.syspath_prepend(str(tmp_path / "competing-import-root"))

    observed = rewrite_architecture_check.build_python_source_snapshot(root)
    assert observed == expected


def test_main_builds_one_snapshot_and_uses_no_path_text_reads(monkeypatch):
    real_builder = rewrite_architecture_check.build_python_source_snapshot
    calls = 0

    def tracking_builder(root):
        nonlocal calls
        calls += 1
        return real_builder(root)

    def forbidden_read(*_args, **_kwargs):
        raise AssertionError("architecture observation reread a Python path")

    monkeypatch.setattr(
        rewrite_architecture_check,
        "build_python_source_snapshot",
        tracking_builder,
    )
    monkeypatch.setattr(Path, "read_text", forbidden_read)
    monkeypatch.setattr(Path, "read_bytes", forbidden_read)

    assert rewrite_architecture_check.main() == 0
    assert calls == 1
