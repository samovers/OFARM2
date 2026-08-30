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


def _execution_state(root: Path):
    snapshot = rewrite_architecture_check.build_python_source_snapshot(root)
    trees = rewrite_architecture_check._snapshot_trees(snapshot)
    closures = rewrite_architecture_check._derive_import_execution_closures(
        snapshot,
        trees,
    )
    return snapshot, trees, closures


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


def test_execution_closure_adds_root_initializer_and_firewall_scans_it(
    tmp_path,
):
    _firewall_tree(tmp_path, "")
    _write_module(tmp_path, "kernel/__init__.py", "import importlib\n")

    snapshot, _trees, closures = _execution_state(tmp_path)

    assert "kernel" not in snapshot.production_reachability
    assert "kernel" in closures.production
    assert type(closures.production) is types.MappingProxyType
    assert closures.production["kernel"][-1] == (
        rewrite_architecture_check._ImportExecutionTransitionV1(
            rewrite_architecture_check._ImportExecutionTransitionKindV1.REQUIRED_INITIALIZER,
            "kernel.api",
            "kernel",
            None,
        )
    )
    assert rewrite_architecture_check._check_import_firewall(tmp_path) == [
        "kernel/__init__.py:1: forbidden dynamic import mechanism "
        "(import of 'importlib'); production import path kernel.api -> "
        "[required initializer kernel/__init__.py]"
    ]


def test_initializer_imports_expand_to_fixed_point_with_provenance(tmp_path):
    _firewall_tree(tmp_path, "")
    _write_module(tmp_path, "kernel/__init__.py", "from . import helper\n")
    _write_module(tmp_path, "kernel/helper.py", "from .deep import VALUE\n")
    _write_module(tmp_path, "kernel/deep.py", "VALUE = 'schema.sql'\n")

    _snapshot, _trees, closures = _execution_state(tmp_path)

    assert {"kernel", "kernel.helper", "kernel.deep"} <= set(closures.production)
    assert rewrite_architecture_check._check_import_firewall(tmp_path) == [
        "kernel/deep.py:1: production references legacy resource "
        "'schema.sql'; production import path kernel.api -> "
        "[required initializer kernel/__init__.py] -> kernel.helper -> "
        "kernel.deep"
    ]


def test_namespace_prefix_adds_only_retained_regular_ancestors(tmp_path):
    root = _snapshot_tree(
        tmp_path,
        {
            "kernel/__init__.py": "",
            "kernel/api.py": "import deployment.namespace.worker\n",
            "deployment/__init__.py": "",
            "deployment/namespace/worker.py": "VALUE = 1\n",
        },
    )

    snapshot, _trees, closures = _execution_state(root)

    assert "deployment.namespace" not in snapshot.modules_by_name
    assert "deployment.namespace" not in closures.production
    assert "deployment" in closures.production
    assert "deployment.namespace.worker" in closures.production


def test_namespace_star_import_adds_no_guessed_member(tmp_path):
    root = _snapshot_tree(
        tmp_path,
        {
            "kernel/__init__.py": "",
            "kernel/api.py": "from deployment.namespace import *\n",
            "deployment/__init__.py": "",
            "deployment/namespace/worker.py": "",
        },
    )

    _snapshot, _trees, closures = _execution_state(root)

    assert "deployment" in closures.production
    assert "deployment.namespace" not in closures.production
    assert "deployment.namespace.worker" not in closures.production


@pytest.mark.parametrize(
    ("api_source", "extra_sources", "kind", "operand"),
    (
        (
            "import deployment.missing\n",
            {"deployment/__init__.py": ""},
            "UNRESOLVED_INTERNAL_IMPORT",
            "deployment.missing",
        ),
        (
            "import package.submodule\n",
            {"package.py": "", "package/submodule.py": ""},
            "PLAIN_MODULE_PACKAGE_CONFLICT",
            "package.submodule via package",
        ),
        (
            "from .. import missing\n",
            {},
            "INVALID_ABOVE_ROOT_RELATIVE",
            "",
        ),
        (
            "from deployment.namespace import missing\n",
            {
                "deployment/__init__.py": "",
                "deployment/namespace/worker.py": "",
            },
            "UNRESOLVED_INTERNAL_IMPORT",
            "deployment.namespace.missing",
        ),
    ),
    ids=(
        "missing-internal",
        "plain-module-conflict",
        "above-root-relative",
        "namespace-missing-member",
    ),
)
def test_reached_internal_resolution_fails_closed(
    tmp_path,
    api_source,
    extra_sources,
    kind,
    operand,
):
    root = _snapshot_tree(
        tmp_path,
        {
            "kernel/__init__.py": "",
            "kernel/api.py": api_source,
            **extra_sources,
        },
    )
    snapshot = rewrite_architecture_check.build_python_source_snapshot(root)
    trees = rewrite_architecture_check._snapshot_trees(snapshot)

    with pytest.raises(rewrite_architecture_check._ImportExecutionFailure) as refused:
        rewrite_architecture_check._derive_import_execution_closures(
            snapshot,
            trees,
        )

    assert refused.value.kind.value == kind
    assert refused.value.relative_path == "kernel/api.py"
    assert refused.value.line == 1
    assert refused.value.operand == operand


def test_external_import_remains_outside_resolution_claim(tmp_path):
    root = _snapshot_tree(
        tmp_path,
        {
            "kernel/__init__.py": "",
            "kernel/api.py": "import external_dependency.missing\n",
        },
    )

    _snapshot, _trees, closures = _execution_state(root)

    assert all(
        not module.startswith("external_dependency") for module in closures.production
    )


@pytest.mark.parametrize(
    ("api_source", "extra_sources", "expected_module"),
    (
        (
            "from deployment import configured_value\n",
            {"deployment/__init__.py": "configured_value = 1\n"},
            "deployment",
        ),
        (
            "from helper import configured_value\n",
            {"helper.py": "configured_value = 1\n"},
            "helper",
        ),
    ),
    ids=("regular-package-attribute", "plain-module-attribute"),
)
def test_absent_from_member_is_allowed_for_retained_base(
    tmp_path,
    api_source,
    extra_sources,
    expected_module,
):
    root = _snapshot_tree(
        tmp_path,
        {
            "kernel/__init__.py": "",
            "kernel/api.py": api_source,
            **extra_sources,
        },
    )

    _snapshot, _trees, closures = _execution_state(root)

    assert expected_module in closures.production


def test_public_graph_is_the_only_exact_import_transition_authority(tmp_path):
    root = _snapshot_tree(
        tmp_path,
        {
            "kernel/__init__.py": "",
            "kernel/api.py": (
                "import kernel.helper\n"
                "from . import helper\n"
                "import deployment.namespace\n"
            ),
            "kernel/helper.py": "",
            "deployment/__init__.py": "",
            "deployment/namespace/worker.py": "",
        },
    )

    snapshot, trees, closures = _execution_state(root)
    helper_path = closures.production["kernel.helper"]
    normalized = rewrite_architecture_check._normalized_imports(
        "kernel.api",
        "kernel/api.py",
        trees["kernel.api"],
    )
    exact_transitions = [
        transition
        for path in closures.production.values()
        for transition in path
        if transition.kind
        is rewrite_architecture_check._ImportExecutionTransitionKindV1.EXPLICIT_IMPORT
    ]

    assert helper_path[-1].line == 1
    assert {
        (record.source_module, record.source_relative_path) for record in normalized
    } == {("kernel.api", "kernel/api.py")}
    assert {target for record in normalized for target in record.candidates} == {
        "kernel.helper"
    }
    assert "deployment.namespace" not in closures.production
    for transition in exact_transitions:
        assert transition.predecessor is not None
        assert (
            rewrite_architecture_check.PythonImportEdgeV1(
                transition.line,
                transition.target,
            )
            in snapshot.import_graph[transition.predecessor]
        )


def test_execution_closure_provenance_is_deterministic(tmp_path):
    sources = {
        "kernel/__init__.py": "",
        "kernel/api.py": "import kernel.helper\n",
        "kernel/application_runtime.py": "import kernel.helper\n",
        "kernel/helper.py": "import kernel.api\n",
    }
    first_root = _snapshot_tree(tmp_path / "first", sources)
    second_root = _snapshot_tree(
        tmp_path / "second",
        dict(reversed(tuple(sources.items()))),
    )

    _first, _first_trees, first = _execution_state(first_root)
    _second, _second_trees, second = _execution_state(second_root)

    assert dict(first.production) == dict(second.production)
    assert dict(first.legacy) == dict(second.legacy)
    assert first.production["kernel.helper"][-1].predecessor == "kernel.api"


def test_initializer_analysis_does_not_execute_retained_source(tmp_path):
    sentinel = tmp_path / "initializer-executed"
    root = _snapshot_tree(
        tmp_path / "tree",
        {
            "kernel/__init__.py": (f"open({str(sentinel)!r}, 'w').write('executed')\n"),
        },
    )

    _execution_state(root)

    assert sentinel.exists() is False


def test_closure_failure_prevents_every_policy_and_partial_fallback(
    tmp_path,
    monkeypatch,
    capsys,
):
    root = _snapshot_tree(
        tmp_path,
        {
            "kernel/__init__.py": "from . import helper\n",
            "kernel/helper.py": "import deployment.missing\n",
            "deployment/__init__.py": "",
        },
    )
    snapshot = rewrite_architecture_check.build_python_source_snapshot(root)
    trees = rewrite_architecture_check._snapshot_trees(snapshot)

    def forbidden_policy(*_args, **_kwargs):
        raise AssertionError("policy ran with a partial closure")

    monkeypatch.setattr(
        rewrite_architecture_check,
        "build_python_source_snapshot",
        lambda _root: snapshot,
    )
    monkeypatch.setattr(
        rewrite_architecture_check,
        "_snapshot_trees",
        lambda _snapshot: trees,
    )
    monkeypatch.setattr(
        rewrite_architecture_check,
        "_check_import_firewall",
        forbidden_policy,
    )
    monkeypatch.setattr(
        rewrite_architecture_check,
        "_check_tenant_uow_architecture",
        forbidden_policy,
    )

    assert rewrite_architecture_check.main() == 1
    assert "kernel/helper.py:1: UNRESOLVED_INTERNAL_IMPORT" in (capsys.readouterr().out)


def test_deployment_initializer_is_scanned_by_production_firewall(tmp_path):
    _firewall_tree(tmp_path, "import deployment.postgresql.worker\n")
    _write_module(tmp_path, "deployment/__init__.py", "import importlib\n")
    _write_module(tmp_path, "deployment/postgresql/__init__.py")
    _write_module(tmp_path, "deployment/postgresql/worker.py")

    assert rewrite_architecture_check._check_import_firewall(tmp_path) == [
        "deployment/__init__.py:1: forbidden dynamic import mechanism "
        "(import of 'importlib'); production import path kernel.api -> "
        "deployment.postgresql.worker -> "
        "[required initializer deployment/__init__.py]"
    ]


def test_initializer_transition_diagnostic_has_no_fabricated_line(tmp_path):
    _firewall_tree(tmp_path, "import kernel.legacy_m1.worker\n")
    _write_module(tmp_path, "kernel/legacy_m1/__init__.py")
    _write_module(tmp_path, "kernel/legacy_m1/worker.py")

    failures = rewrite_architecture_check._check_import_firewall(tmp_path)

    assert failures[0] == (
        "kernel/legacy_m1/__init__.py: production import path kernel.api -> "
        "kernel.legacy_m1.worker -> "
        "[required initializer kernel/legacy_m1/__init__.py] reaches legacy "
        "module 'kernel.legacy_m1'"
    )
    assert "__init__.py:0:" not in failures[0]


def test_legacy_initializer_reverse_import_uses_initializer_provenance(
    tmp_path,
):
    _firewall_tree(tmp_path, "")
    _write_module(
        tmp_path,
        "kernel/legacy_m1/__init__.py",
        "import kernel.application_runtime\n",
    )

    assert rewrite_architecture_check._check_import_firewall(tmp_path) == [
        "kernel/legacy_m1/__init__.py:1: legacy import path "
        "kernel.legacy_m1.api -> "
        "[required initializer kernel/legacy_m1/__init__.py] -> "
        "kernel.application_runtime reaches production composition module "
        "'kernel.application_runtime'"
    ]


_VALID_TENANT_UOW_SOURCE = """\
class TenantUnitOfWork:
    __slots__ = ("__binding", "__active", "__allocate_batch", "__batch")

    def __init__(self, binding, allocate_batch):
        self.__binding = binding
        self.__active = False
        self.__allocate_batch = allocate_batch
        self.__batch = None

    @property
    def binding(self):
        return self.__binding

    @property
    def batch(self):
        return self.__batch

    def begin_batch(self):
        self.__batch = self.__allocate_batch()
        return self.__batch
"""


@pytest.mark.parametrize(
    ("initializer", "api_source", "extra_sources"),
    (
        ("kernel/__init__.py", "", {}),
        (
            "kernel/features/__init__.py",
            "import kernel.features.worker\n",
            {"kernel/features/worker.py": ""},
        ),
    ),
    ids=("exact-kernel", "nested-kernel"),
)
def test_tenant_policy_scans_reached_kernel_initializers(
    tmp_path,
    initializer,
    api_source,
    extra_sources,
):
    sources = {
        "kernel/__init__.py": "",
        "kernel/api.py": api_source,
        "kernel/tenant_uow.py": _VALID_TENANT_UOW_SOURCE,
        **extra_sources,
    }
    sources[initializer] = "probe = holder._TenantUnitOfWork__connection\n"
    root = _snapshot_tree(tmp_path, sources)
    snapshot, trees, closures = _execution_state(root)

    assert rewrite_architecture_check._check_tenant_uow_architecture(
        snapshot,
        trees,
        closures,
    ) == [
        f"{initializer}:1: tenant UnitOfWork private-state access "
        "'_TenantUnitOfWork__connection'"
    ]


def test_public_snapshot_golden_fixture_is_unchanged(tmp_path):
    sources = {
        "kernel/__init__.py": "PACKAGE = 'kernel'\n",
        "kernel/api.py": "from .helper import VALUE\n",
        "kernel/application_runtime.py": "RUNTIME = True\n",
        "kernel/helper.py": "VALUE = 1\n",
        "kernel/legacy_m1/__init__.py": "PACKAGE = 'legacy'\n",
        "kernel/legacy_m1/api.py": "from . import runtime\n",
        "kernel/legacy_m1/runtime.py": "LEGACY = True\n",
    }
    root = _snapshot_tree(tmp_path, sources)
    snapshot = rewrite_architecture_check.build_python_source_snapshot(root)
    second = rewrite_architecture_check.build_python_source_snapshot(root)
    units = {
        module: (
            unit.module_name,
            unit.relative_path,
            unit.source_bytes,
            unit.source_text,
            unit.byte_length,
            unit.sha256,
            unit.ast_node_count,
            unit.ast_depth,
        )
        for module, unit in snapshot.modules_by_name.items()
    }
    expected_unit_values = {
        "kernel": (
            19,
            "ea7f7742220b4b0ef86f74d17fcd3e328e6f8438ee1066c62ff75428a161d2c4",
            5,
            4,
        ),
        "kernel.api": (
            26,
            "0899608dd32394baea0627f0556cd5ed7b430e9066df055e3f4ab674bc5b8bb9",
            3,
            3,
        ),
        "kernel.application_runtime": (
            15,
            "2081fb99765b1df11601111c4e906dbd807ed9167f6ccb9ee1215679730de2db",
            5,
            4,
        ),
        "kernel.helper": (
            10,
            "e13df8c44af5dea1e412403910b99cc5a48f2ccbf68a66b3374d6ab9cef9fc65",
            5,
            4,
        ),
        "kernel.legacy_m1": (
            19,
            "1af47a9f016c20c23c4475b8feef56d8def1ac8c2994733753faa9ed824e042e",
            5,
            4,
        ),
        "kernel.legacy_m1.api": (
            22,
            "d93e2f5b314700e236049b9d1ba8087fc6239d70ee10038546bc7ad5a59d9e98",
            3,
            3,
        ),
        "kernel.legacy_m1.runtime": (
            14,
            "2ef230c53a5ec069e39d8d320638b0cb7814a6ad31074f68e22a0ee93adc6565",
            5,
            4,
        ),
    }

    assert snapshot == second
    assert set(units) == set(expected_unit_values)
    for module, value in units.items():
        byte_length, digest, node_count, depth = expected_unit_values[module]
        relative = module.replace(".", "/") + ".py"
        if module in {"kernel", "kernel.legacy_m1"}:
            relative = module.replace(".", "/") + "/__init__.py"
        assert value == (
            module,
            relative,
            sources[relative].encode("utf-8"),
            sources[relative],
            byte_length,
            f"sha256:{digest}",
            node_count,
            depth,
        )
    assert dict(snapshot.import_graph) == {
        "kernel": (),
        "kernel.api": (
            rewrite_architecture_check.PythonImportEdgeV1(
                1,
                "kernel.helper",
            ),
        ),
        "kernel.application_runtime": (),
        "kernel.helper": (),
        "kernel.legacy_m1": (),
        "kernel.legacy_m1.api": (
            rewrite_architecture_check.PythonImportEdgeV1(
                1,
                "kernel.legacy_m1",
            ),
            rewrite_architecture_check.PythonImportEdgeV1(
                1,
                "kernel.legacy_m1.runtime",
            ),
        ),
        "kernel.legacy_m1.runtime": (),
    }
    assert dict(snapshot.production_reachability) == {
        "kernel.api": ("kernel.api",),
        "kernel.application_runtime": ("kernel.application_runtime",),
        "kernel.helper": ("kernel.api", "kernel.helper"),
    }
    assert dict(snapshot.legacy_reachability) == {
        "kernel.legacy_m1.api": ("kernel.legacy_m1.api",),
        "kernel.legacy_m1.runtime": ("kernel.legacy_m1.runtime",),
        "kernel.legacy_m1": (
            "kernel.legacy_m1.api",
            "kernel.legacy_m1",
        ),
    }
    assert (
        snapshot.source_file_count,
        snapshot.total_source_bytes,
        snapshot.total_ast_nodes,
        snapshot.total_import_edges,
        snapshot.content_sha256,
    ) == (
        7,
        125,
        31,
        3,
        "sha256:b230d73cdfb094c35c0cd15817215fe959bcc9a1a0aa5333b9954976e9f8937c",
    )


def test_unreached_internal_error_remains_outside_fixed_root_claim(tmp_path):
    root = _snapshot_tree(
        tmp_path,
        {
            "kernel/__init__.py": "",
            "deployment/__init__.py": "",
            "operator_entry.py": "import deployment.missing\n",
        },
    )

    _snapshot, _trees, closures = _execution_state(root)

    assert "operator_entry" not in closures.production
    assert "operator_entry" not in closures.legacy


_VALID_CREDENTIAL_DIAGNOSTIC_SOURCE = """\
from dataclasses import dataclass
from typing import Self, cast

@dataclass(frozen=True, slots=True, repr=False)
class SecretCarrier:
    first: str
    second: str

    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return NotImplemented
        other_carrier = cast(Self, other)
        return (
            self.first,
            self.second,
        ) == (
            other_carrier.first,
            other_carrier.second,
        )
"""


def _credential_test_expression_shape(source):
    expression = ast.parse(source, mode="eval", feature_version=(3, 12))
    return ast.dump(expression.body, include_attributes=False)


_TEST_CREDENTIAL_DECLARATIONS = (
    ("first", _credential_test_expression_shape("str")),
    ("second", _credential_test_expression_shape("str")),
)
_TEST_CREDENTIAL_METHODS = (
    rewrite_architecture_check._CredentialMethodHeader(
        "__eq__",
        (),
        (
            ("self", None),
            ("other", _credential_test_expression_shape("object")),
        ),
        _credential_test_expression_shape("bool"),
        "exact-equality",
    ),
)

_VALID_RUNTIME_CONFIG_DIAGNOSTIC_SOURCE = """\
from __future__ import annotations
from dataclasses import dataclass
from typing import Self, cast

@dataclass(frozen=True, slots=True, repr=False)
class RuntimeConfig:
    first: str
    second: str

    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return NotImplemented
        other_carrier = cast(Self, other)
        return (
            self.first,
            self.second,
        ) == (
            other_carrier.first,
            other_carrier.second,
        )

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        return cls(first="fictional", second="fictional")
"""

_TEST_RUNTIME_CONFIG_METHODS = (
    *_TEST_CREDENTIAL_METHODS,
    rewrite_architecture_check._CredentialMethodHeader(
        "from_env",
        (_credential_test_expression_shape("classmethod"),),
        (("cls", None),),
        _credential_test_expression_shape("RuntimeConfig"),
        "opaque-deferred",
    ),
)


def _credential_violations(
    source,
    protected_fields=("first",),
    declarations=_TEST_CREDENTIAL_DECLARATIONS,
    methods=_TEST_CREDENTIAL_METHODS,
):
    return rewrite_architecture_check._credential_diagnostic_carrier_violations(
        ast.parse(source),
        "SecretCarrier",
        protected_fields,
        declarations,
        methods,
    )


def _runtime_config_credential_violations(source):
    return rewrite_architecture_check._credential_diagnostic_carrier_violations(
        ast.parse(source),
        "RuntimeConfig",
        ("first",),
        _TEST_CREDENTIAL_DECLARATIONS,
        _TEST_RUNTIME_CONFIG_METHODS,
    )


def _credential_source_with(statement, *, future_annotations=False):
    source = _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE.replace(
        "    def __eq__",
        statement.rstrip() + "\n\n    def __eq__",
        1,
    )
    if future_annotations:
        source = "from __future__ import annotations\n" + source
    return source


def _credential_events(source, annotation_resolution_symbols=frozenset()):
    tree = ast.parse(source)
    target = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SecretCarrier"
    )
    return rewrite_architecture_check._credential_class_namespace_events(
        tree,
        target,
        annotation_resolution_symbols,
    )


def test_credential_diagnostic_authority_map_is_exact():
    shape = _credential_test_expression_shape
    eq_header = rewrite_architecture_check._CredentialMethodHeader(
        "__eq__",
        (),
        (("self", None), ("other", shape("object"))),
        shape("bool"),
        "exact-equality",
    )
    assert rewrite_architecture_check._CREDENTIAL_DIAGNOSTIC_CARRIERS == (
        rewrite_architecture_check._CredentialCarrierDescriptor(
            "kernel/runtime_config.py",
            "RuntimeConfig",
            (
                "pg_dsn",
                "tenant_readiness_pg_dsn",
                "security_audit_readiness_pg_dsn",
                "security_audit_authentication_pg_dsn",
                "security_audit_request_router_pg_dsn",
                "security_audit_control_pg_dsn",
            ),
            (
                ("mode", shape("RuntimeMode")),
                ("deployment_image_digest", shape("str")),
                ("oidc_issuer", shape("str")),
                ("oidc_audience", shape("str")),
                ("oidc_jwks_url", shape("str")),
                ("pg_dsn", shape("str")),
                ("tenant_readiness_pg_dsn", shape("str")),
                ("security_audit_readiness_pg_dsn", shape("str")),
                ("security_audit_authentication_pg_dsn", shape("str")),
                ("security_audit_request_router_pg_dsn", shape("str")),
                ("security_audit_control_pg_dsn", shape("str")),
                ("correlation_hmac_kms_key_resource", shape("str")),
                ("tenant_capability_kid", shape("str")),
                ("signing_evidence_receipt_path", shape("Path")),
                ("signing_evidence_observer_public_key", shape("bytes")),
            ),
            (
                eq_header,
                rewrite_architecture_check._CredentialMethodHeader(
                    "from_env",
                    (shape("classmethod"),),
                    (("cls", None),),
                    shape("RuntimeConfig"),
                    "opaque-deferred",
                ),
            ),
        ),
        rewrite_architecture_check._CredentialCarrierDescriptor(
            "deployment/postgresql/security_audit_process_crash.py",
            "ProcessCrashReconciliationSecrets",
            ("control_conninfo",),
            (("control_conninfo", shape("str")),),
            (eq_header,),
        ),
        rewrite_architecture_check._CredentialCarrierDescriptor(
            "deployment/postgresql/security_audit_store_loss.py",
            "StoreLossRecoverySecrets",
            ("admin_dsn", "migrator_dsn", "control_dsn", "login_passwords"),
            (
                ("admin_dsn", shape("str")),
                ("migrator_dsn", shape("str")),
                ("control_dsn", shape("str")),
                ("login_passwords", shape("tuple[tuple[str, str], ...]")),
            ),
            (eq_header,),
        ),
        rewrite_architecture_check._CredentialCarrierDescriptor(
            "deployment/postgresql/security_audit_store_loss.py",
            "_Routes",
            (
                "admin_long",
                "admin_short",
                "admin_target_short",
                "migrator_long",
                "control_short",
            ),
            (
                ("admin_long", shape("str")),
                ("admin_short", shape("str")),
                ("admin_target_short", shape("str")),
                ("migrator_long", shape("str")),
                ("control_short", shape("str")),
            ),
            (eq_header,),
        ),
        rewrite_architecture_check._CredentialCarrierDescriptor(
            "deployment/postgresql/security_audit_store_loss.py",
            "_ValidatedInvocation",
            ("routes", "login_passwords"),
            (
                ("request", shape("StoreLossRecoveryRequest")),
                ("routes", shape("_Routes")),
                ("login_passwords", shape("tuple[tuple[str, str], ...]")),
            ),
            (eq_header,),
        ),
    )


@pytest.mark.parametrize("explicit_eq", (False, True), ids=("default", "explicit"))
def test_credential_diagnostic_rule_accepts_exact_shape(explicit_eq):
    source = _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE
    if explicit_eq:
        source = source.replace("repr=False)", "repr=False, eq=True)", 1)

    assert _credential_violations(source) == []


@pytest.mark.parametrize(
    "replacement",
    (
        "(first): str",
        "first: bytes",
        "first: ClassVar[str]",
        "first: InitVar[str]",
        "first: KW_ONLY",
        'first: str = "fictional"',
        "first: str = field(init=False)",
        "first: str = field(hash=False)",
        "first: str = field(kw_only=True)",
    ),
    ids=(
        "parenthesized",
        "alternate-annotation",
        "class-var",
        "init-var",
        "keyword-only-sentinel",
        "plain-default",
        "field-init",
        "field-hash",
        "field-keyword-only",
    ),
)
def test_credential_diagnostic_rule_rejects_alternate_declaration_shapes(
    replacement,
):
    source = _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE.replace(
        "first: str",
        replacement,
        1,
    )

    assert (
        "SecretCarrier: direct class-body shape differs from the exact contract"
        in _credential_violations(source)
    )


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ("    first: str\n", ""),
        (
            "    first: str\n    second: str",
            "    second: str\n    first: str",
        ),
        (
            "    first: str",
            "    first: str\n    first: str",
        ),
        (
            "    first: str",
            "    if True:\n        first: str",
        ),
        (
            "    first: str",
            '    first: str\n    "unexpected direct statement"',
        ),
    ),
    ids=("missing", "reordered", "duplicated", "wrapped", "extra"),
)
def test_credential_diagnostic_rule_rejects_alternate_direct_sequences(
    old,
    new,
):
    source = _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE.replace(old, new, 1)

    assert (
        "SecretCarrier: direct class-body shape differs from the exact contract"
        in _credential_violations(source)
    )


@pytest.mark.parametrize(
    "header",
    (
        "def __eq__(self, other) -> bool:",
        "def __eq__(self: object, other: object) -> bool:",
        "def __eq__(self, other: object) -> object:",
        "def __eq__(self, other: object = object()) -> bool:",
        "def __eq__(self, /, other: object) -> bool:",
        "def __eq__(self, *other: object) -> bool:",
        "def __eq__(self, *, other: object) -> bool:",
        "def __eq__[T](self, other: object) -> bool:",
    ),
    ids=(
        "missing-argument-annotation",
        "self-annotation",
        "return-annotation",
        "default",
        "positional-only",
        "variadic",
        "keyword-only",
        "type-parameter",
    ),
)
def test_credential_diagnostic_rule_rejects_alternate_equality_headers(header):
    source = _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE.replace(
        "def __eq__(self, other: object) -> bool:",
        header,
        1,
    )

    assert (
        "SecretCarrier: direct class-body shape differs from the exact contract"
        in _credential_violations(source)
    )


@pytest.mark.parametrize(
    "header",
    (
        (
            "def from_env(\n"
            "        cls, value=(lambda: globals().__setitem__(\n"
            '            "str", object\n'
            "        ))()\n"
            "    ) -> RuntimeConfig:"
        ),
        "def from_env(cls: object) -> RuntimeConfig:",
        "def from_env(cls) -> object:",
        "async def from_env(cls) -> RuntimeConfig:",
        "def from_env[T](cls) -> RuntimeConfig:",
    ),
    ids=(
        "hostile-default",
        "argument-annotation",
        "return-annotation",
        "asynchronous",
        "type-parameter",
    ),
)
def test_runtime_config_credential_rule_rejects_alternate_from_env_headers(
    header,
):
    source = _VALID_RUNTIME_CONFIG_DIAGNOSTIC_SOURCE.replace(
        "def from_env(cls) -> RuntimeConfig:",
        header,
        1,
    )

    assert (
        "RuntimeConfig: direct class-body shape differs from the exact contract"
        in _runtime_config_credential_violations(source)
    )


@pytest.mark.parametrize(
    "decorator",
    ("", "    @staticmethod\n", "    @caller\n    @classmethod\n"),
    ids=("missing", "alternate", "additional"),
)
def test_runtime_config_credential_rule_rejects_alternate_from_env_decorators(
    decorator,
):
    source = _VALID_RUNTIME_CONFIG_DIAGNOSTIC_SOURCE.replace(
        "    @classmethod\n",
        decorator,
        1,
    )

    assert (
        "RuntimeConfig: direct class-body shape differs from the exact contract"
        in _runtime_config_credential_violations(source)
    )


def test_runtime_config_credential_rule_keeps_from_env_body_opaque():
    source = _VALID_RUNTIME_CONFIG_DIAGNOSTIC_SOURCE.replace(
        '        return cls(first="fictional", second="fictional")',
        (
            "        def deferred_helper():\n"
            '            globals().__setitem__("str", object)\n'
            "        values = [item for item in ()]\n"
            "        return cls(first=str(values), second=str(deferred_helper))"
        ),
        1,
    )

    assert _runtime_config_credential_violations(source) == []


def test_credential_method_header_refuses_detached_type_comment():
    tree = ast.parse(_VALID_CREDENTIAL_DIAGNOSTIC_SOURCE)
    target = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SecretCarrier"
    )
    method = next(
        statement for statement in target.body if isinstance(statement, ast.FunctionDef)
    )
    method.type_comment = "(object, object) -> bool"

    assert (
        rewrite_architecture_check._credential_direct_class_projection(
            target,
            _TEST_CREDENTIAL_DECLARATIONS,
            _TEST_CREDENTIAL_METHODS,
        )
        is None
    )


def test_credential_diagnostic_rule_rejects_generic_carrier_header():
    source = _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE.replace(
        "class SecretCarrier:",
        "class SecretCarrier[T]:",
        1,
    )

    assert (
        "SecretCarrier: class must inherit directly from object"
        in _credential_violations(source)
    )


def test_credential_diagnostic_rule_rejects_type_parameter_shadowing_cast():
    source = _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE.replace(
        "class SecretCarrier:",
        "class SecretCarrier[cast]:",
        1,
    )
    valid_tree = ast.parse(_VALID_CREDENTIAL_DIAGNOSTIC_SOURCE)
    mutated_tree = ast.parse(source)
    valid_target = next(
        node
        for node in valid_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SecretCarrier"
    )
    mutated_target = next(
        node
        for node in mutated_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SecretCarrier"
    )

    assert [parameter.name for parameter in mutated_target.type_params] == ["cast"]
    assert ast.dump(
        mutated_target.body[-1], include_attributes=False
    ) == ast.dump(valid_target.body[-1], include_attributes=False)
    assert (
        rewrite_architecture_check._credential_direct_class_projection(
            mutated_target,
            _TEST_CREDENTIAL_DECLARATIONS,
            _TEST_CREDENTIAL_METHODS,
        )
        is not None
    )
    assert (
        "SecretCarrier: class must inherit directly from object"
        in _credential_violations(source)
    )


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ("class SecretCarrier:", "class DifferentCarrier:"),
        ("class SecretCarrier:", "class SecretCarrier(BaseCarrier):"),
        ("second: str", "different: str"),
        (", repr=False", ""),
        ("repr=False", "repr=True"),
        ("repr=False", "repr=False, eq=False"),
        ("repr=False", "repr=False, unsafe_hash=True"),
        (
            "@dataclass(frozen=True, slots=True, repr=False)",
            "@caller\n@dataclass(frozen=True, slots=True, repr=False)",
        ),
        ("def __eq__", "async def __eq__"),
        (
            "if other.__class__ is not self.__class__:",
            "if type(other) is not type(self):",
        ),
        ("return NotImplemented", "return False"),
        ("other_carrier = cast(Self, other)", "other_carrier = other"),
        ("            self.second,\n", ""),
        ("            other_carrier.second,\n", ""),
        (
            "            self.first,\n            self.second,",
            "            self.second,\n            self.first,",
        ),
        (
            "        ) == (",
            "        ) != (",
        ),
        (
            "        return (\n            self.first,",
            "        return fields(self) == fields(other_carrier)\n"
            "        return (\n            self.first,",
        ),
        (
            "    def __eq__(self, other: object) -> bool:",
            "    @staticmethod\n"
            "    def __eq__(self, other: object) -> bool:",
        ),
        (
            "    def __eq__(self, other: object) -> bool:",
            "    __repr__, harmless = caller, object()\n\n"
            "    def __eq__(self, other: object) -> bool:",
        ),
        (
            "    def __eq__(self, other: object) -> bool:",
            "    __eq__ = caller\n\n"
            "    def __eq__(self, other: object) -> bool:",
        ),
        (
            "            other_carrier.second,\n        )\n",
            "            other_carrier.second,\n        )\n"
            "    del __eq__\n",
        ),
    ),
    ids=(
        "class-name",
        "class-base",
        "field-inventory",
        "generated-repr",
        "repr-true",
        "eq-false",
        "unsafe-hash",
        "extra-class-decorator",
        "async-equality",
        "alternate-type-branch",
        "false-type-result",
        "missing-cast",
        "left-field-omitted",
        "right-field-omitted",
        "left-fields-reordered",
        "non-equality-comparison",
        "helper-selected-fields",
        "decorated-equality",
        "tuple-display-binding",
        "equality-rebinding",
        "equality-deletion",
    ),
)
def test_credential_diagnostic_rule_rejects_hostile_shapes(old, new):
    mutated = _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE.replace(old, new, 1)

    assert mutated != _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE
    assert _credential_violations(mutated)


@pytest.mark.parametrize(
    "member",
    ("__hash__", "__repr__", "__str__", "__format__"),
)
def test_credential_diagnostic_rule_rejects_display_and_hash_members(member):
    added = f"    def {member}(self):\n        return 'forbidden'\n\n"
    mutated = _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE.replace(
        "    def __eq__",
        added + "    def __eq__",
        1,
    )

    assert _credential_violations(mutated)


@pytest.mark.parametrize(
    "statement",
    (
        "    import helper as __repr__",
        "    from helper import value as __repr__",
        "    __repr__ = object()",
        "    __repr__, harmless = object(), object()",
        "    __repr__: object",
        "    __repr__ += object()",
        "    del __repr__",
        "    if False:\n        __repr__ = object()",
        "    while False:\n        __repr__ = object()",
        "    for __repr__ in ():\n        pass",
        "    async for __repr__ in source():\n        pass",
        "    with manager() as __repr__:\n        pass",
        "    async with manager() as __repr__:\n        pass",
        (
            "    try:\n"
            "        pass\n"
            "    except Exception as __repr__:\n"
            "        pass"
        ),
        (
            "    try:\n"
            "        pass\n"
            "    except* Exception as __repr__:\n"
            "        pass"
        ),
        "    helper = (__repr__ := object())",
        "    type __repr__ = object",
        "    class __repr__:\n        pass",
        "    if False:\n        def __repr__(self):\n            return ''",
    ),
    ids=(
        "import",
        "from-import",
        "assign",
        "unpack",
        "annotated-assign",
        "augmented-assign",
        "delete",
        "if-suite",
        "while-suite",
        "for-target",
        "async-for-target",
        "with-target",
        "async-with-target",
        "exception-name",
        "exception-group-name",
        "assignment-expression",
        "type-alias",
        "nested-class-name",
        "conditional-function-name",
    ),
)
def test_credential_diagnostic_rule_rejects_every_binding_form(statement):
    violations = _credential_violations(_credential_source_with(statement))

    assert (
        "SecretCarrier: class defines forbidden display or hash members"
        in violations
    )


@pytest.mark.parametrize(
    "statement",
    (
        "    match object():\n        case __repr__:\n            pass",
        "    match []:\n        case [*__repr__]:\n            pass",
        (
            "    match {}:\n"
            "        case {'value': _, **__repr__}:\n"
            "            pass"
        ),
        (
            "    match object():\n"
            "        case object() as __repr__:\n"
            "            pass"
        ),
        (
            "    match 0:\n"
            "        case (0 as __repr__) | (1 as __repr__):\n"
            "            pass"
        ),
    ),
    ids=("capture", "star", "mapping-rest", "class-as", "or-pattern"),
)
def test_credential_diagnostic_rule_rejects_every_match_capture(statement):
    violations = _credential_violations(_credential_source_with(statement))

    assert (
        "SecretCarrier: class defines forbidden display or hash members"
        in violations
    )


@pytest.mark.parametrize(
    "statement",
    (
        "    from helper import *",
        "    global __repr__",
        "    nonlocal __repr__",
        "    def helper[T](self):\n        pass",
        "    async def helper[T](self):\n        pass",
        "    class Nested[T]:\n        pass",
        "    helper = [(captured := item) for item in (0,)]",
    ),
    ids=(
        "wildcard-import",
        "global",
        "nonlocal",
        "generic-function",
        "generic-async-function",
        "generic-class",
        "comprehension-assignment-expression",
    ),
)
def test_credential_diagnostic_rule_rejects_unbounded_forms(statement):
    violations = _credential_violations(_credential_source_with(statement))

    assert (
        "SecretCarrier: class namespace binding analysis is unbounded"
        in violations
    )


@pytest.mark.parametrize(
    "expression",
    (
        "[item for item in (exec('__repr__ = object()') or ())]",
        "{item for item in (exec('__repr__ = object()') or ())}",
        "{item: item for item in (exec('__repr__ = object()') or ())}",
        "(item for item in (exec('__repr__ = object()') or ()))",
    ),
    ids=("list", "set", "dict", "generator"),
)
@pytest.mark.parametrize(
    "future_annotations",
    (False, True),
    ids=("eager", "postponed"),
)
def test_credential_diagnostic_rule_refuses_every_reached_comprehension(
    expression,
    future_annotations,
):
    source = _credential_source_with(
        f"    helper = {expression}",
        future_annotations=future_annotations,
    )

    unbounded = [
        event for event in _credential_events(source) if event.kind == "unbounded"
    ]

    assert len(unbounded) == 1
    assert isinstance(
        unbounded[0].node,
        (
            ast.ListComp,
            ast.SetComp,
            ast.DictComp,
            ast.GeneratorExp,
        ),
    )


@pytest.mark.parametrize(
    "expression",
    (
        "[exec('__repr__ = object()') for item in (0,)]",
        "[item for item in (0,) if exec('__repr__ = object()')]",
        (
            "[nested for item in (0,) "
            "for nested in (exec('__repr__ = object()') or ())]"
        ),
        "[__repr__ for __repr__ in (0,)]",
    ),
    ids=("result", "filter", "later-iterable", "target"),
)
def test_credential_diagnostic_rule_does_not_traverse_comprehension_body(
    expression,
):
    source = _credential_source_with(f"    helper = {expression}")

    unbounded = [
        event for event in _credential_events(source) if event.kind == "unbounded"
    ]

    assert len(unbounded) == 1
    assert isinstance(unbounded[0].node, ast.ListComp)


@pytest.mark.parametrize("name", ("__repr__", "__eq__"))
@pytest.mark.parametrize(
    "value",
    (None, '"fictional"'),
    ids=("without-value", "with-value"),
)
def test_credential_parenthesized_annotation_follows_assignment_semantics(
    name,
    value,
):
    statement = f"    ({name}): object"
    if value is not None:
        statement += f" = {value}"
    events = _credential_events(_credential_source_with(statement))
    annotated_events = [
        event
        for event in events
        if event.name == name and isinstance(event.node, ast.AnnAssign)
    ]

    if value is None:
        assert annotated_events == []
    else:
        assert [event.kind for event in annotated_events] == ["bind"]


@pytest.mark.parametrize(
    "target",
    (
        "(exec('__repr__ = object()') or holder).value",
        "holder[exec('__repr__ = object()') or 0]",
    ),
    ids=("attribute", "subscript"),
)
@pytest.mark.parametrize(
    "value",
    (None, "object()"),
    ids=("without-value", "with-value"),
)
def test_credential_non_simple_annotation_inspects_evaluated_target_components(
    target,
    value,
):
    statement = f"    {target}: object"
    if value is not None:
        statement += f" = {value}"

    assert any(
        event.kind == "unbounded"
        for event in _credential_events(_credential_source_with(statement))
    )


def test_credential_annotation_dispatch_refuses_unsupported_simple_value():
    tree = ast.parse(_VALID_CREDENTIAL_DIAGNOSTIC_SOURCE)
    target = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SecretCarrier"
    )
    declaration = next(
        statement for statement in target.body if isinstance(statement, ast.AnnAssign)
    )
    declaration.simple = 2

    events = rewrite_architecture_check._credential_class_namespace_events(
        tree,
        target,
    )

    assert [event.node for event in events if event.kind == "unbounded"] == [
        declaration
    ]


def test_credential_direct_declarations_own_resolution_symbols_and_identity():
    tree = ast.parse(_VALID_CREDENTIAL_DIAGNOSTIC_SOURCE)
    target = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SecretCarrier"
    )
    projection = rewrite_architecture_check._credential_direct_class_projection(
        target,
        _TEST_CREDENTIAL_DECLARATIONS,
        _TEST_CREDENTIAL_METHODS,
    )

    assert projection is not None
    symbols = rewrite_architecture_check._credential_annotation_resolution_symbols(
        projection.declarations
    )
    events = rewrite_architecture_check._credential_class_namespace_events(
        tree,
        target,
        symbols,
    )
    collected = (
        rewrite_architecture_check._credential_collected_simple_declaration_nodes(
            events
        )
    )

    assert symbols == frozenset({"str"})
    assert len(collected) == len(projection.declarations)
    assert all(
        observed is approved
        for observed, approved in zip(
            collected,
            projection.declarations,
            strict=True,
        )
    )


def test_credential_collected_declaration_identity_exposes_nested_extra_node():
    source = _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE.replace(
        "    def __eq__",
        "    if True:\n        third: str\n\n    def __eq__",
        1,
    )
    tree = ast.parse(source)
    target = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SecretCarrier"
    )
    direct = tuple(
        statement for statement in target.body if isinstance(statement, ast.AnnAssign)
    )
    events = rewrite_architecture_check._credential_class_namespace_events(
        tree,
        target,
    )
    collected = (
        rewrite_architecture_check._credential_collected_simple_declaration_nodes(
            events
        )
    )

    assert len(direct) == 2
    assert len(collected) == 3
    assert all(
        observed is approved
        for observed, approved in zip(collected[:2], direct, strict=True)
    )


@pytest.mark.parametrize(
    "statement",
    (
        "    namespace = globals",
        "    namespace = __annotations__",
        '    globals()["str"] = ClassVar',
        '    __annotations__["first"] = str',
    ),
    ids=(
        "globals-capture",
        "annotation-map-capture",
        "globals-mutation",
        "annotation-map-mutation",
    ),
)
def test_credential_namespace_collector_refuses_reserved_evaluated_names(
    statement,
):
    events = _credential_events(_credential_source_with(statement))

    assert any(event.kind == "unbounded" for event in events)


@pytest.mark.parametrize("scope", ("global", "nonlocal"))
def test_credential_namespace_collector_refuses_resolution_symbol_redirection(
    scope,
):
    source = _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE.replace(
        "    first: str",
        f"    {scope} str\n    first: str",
        1,
    )
    events = _credential_events(source, frozenset({"str"}))

    assert any(event.kind == "unbounded" and event.name == "str" for event in events)


@pytest.mark.parametrize(
    "statement",
    ("    str = object()", "    del str"),
    ids=("bind", "delete"),
)
def test_credential_namespace_collector_exposes_resolution_symbol_changes(
    statement,
):
    events = _credential_events(
        _credential_source_with(statement),
        frozenset({"str"}),
    )

    assert any(
        event.kind in {"bind", "delete"} and event.name == "str" for event in events
    )


def test_credential_diagnostic_rule_rejects_annotation_map_binding():
    source = _credential_source_with("    __annotations__ = {}")

    assert (
        "SecretCarrier: class defines explicit annotation-map authority"
        in _credential_violations(source)
    )


@pytest.mark.parametrize(
    "future_annotations",
    (False, True),
    ids=("eager", "postponed"),
)
def test_credential_diagnostic_rule_rejects_nested_class_construction(
    future_annotations,
):
    source = _credential_source_with(
        "    class Nested:\n        global str\n        str = ClassVar",
        future_annotations=future_annotations,
    )

    assert (
        "SecretCarrier: nested class construction is prohibited"
        in _credential_violations(source)
    )


@pytest.mark.parametrize(
    "statement",
    (
        (
            '    type Mutation = globals().__setitem__("str", ClassVar)\n'
            "    Mutation.__value__"
        ),
        '    (lambda: globals().__setitem__("str", ClassVar))()',
        (
            "    def mutate():\n"
            '        globals().__setitem__("str", ClassVar)\n\n'
            "    mutate()"
        ),
        ('    [*(globals().__setitem__("str", marker) for marker in (ClassVar,))]'),
    ),
    ids=("forced-type-alias", "invoked-lambda", "local-call", "consumed-generator"),
)
@pytest.mark.parametrize(
    "future_annotations",
    (False, True),
    ids=("eager", "postponed"),
)
def test_credential_diagnostic_rule_rejects_pre_decoration_activation(
    statement,
    future_annotations,
):
    source = _credential_source_with(
        statement,
        future_annotations=future_annotations,
    )

    assert (
        "SecretCarrier: direct class-body shape differs from the exact contract"
        in _credential_violations(source)
    )


@pytest.mark.parametrize(
    "statement",
    (
        (
            "    def helper(\n"
            "        self, value=(exec('__repr__ = object()') or None)\n"
            "    ):\n"
            "        pass"
        ),
        (
            "    async def helper(\n"
            "        self, value=(exec('__repr__ = object()') or None)\n"
            "    ):\n"
            "        pass"
        ),
        (
            "    @(exec('__repr__ = object()') or decorator)\n"
            "    def helper(self):\n"
            "        pass"
        ),
        (
            "    def helper(\n"
            "        self, value: (exec('__repr__ = object()') or object)\n"
            "    ):\n"
            "        pass"
        ),
        (
            "    helper = lambda value=(\n"
            "        exec('__repr__ = object()') or None\n"
            "    ): value"
        ),
        (
            "    class Nested(exec('__repr__ = object()') or object):\n"
            "        pass"
        ),
        (
            "    @(exec('__repr__ = object()') or decorator)\n"
            "    class Nested:\n"
            "        pass"
        ),
        (
            "    class Nested(\n"
            "        metaclass=exec('__repr__ = object()') or type\n"
            "    ):\n"
            "        pass"
        ),
    ),
    ids=(
        "function-default",
        "async-function-default",
        "function-decorator",
        "eager-annotation",
        "lambda-default",
        "nested-class-base",
        "nested-class-decorator",
        "nested-class-keyword",
    ),
)
def test_credential_diagnostic_rule_inspects_definition_time_scope(statement):
    violations = _credential_violations(_credential_source_with(statement))

    assert (
        "SecretCarrier: class namespace binding analysis is unbounded"
        in violations
    )


@pytest.mark.parametrize(
    ("statement", "future_annotations"),
    (
        (
            "    def helper(self):\n"
            "        exec('__repr__ = object()')",
            False,
        ),
        (
            "    async def helper(self):\n"
            "        exec('__repr__ = object()')",
            False,
        ),
        ("    helper = lambda: exec('__repr__ = object()')", False),
        (
            "    class Nested:\n"
            "        exec('__repr__ = object()')",
            False,
        ),
        (
            "    def helper(\n"
            "        self, value: (exec('__repr__ = object()') or object)\n"
            "    ):\n"
            "        pass",
            True,
        ),
        ("    type Alias = exec('__repr__ = object()') or object", False),
    ),
    ids=(
        "function-body",
        "async-function-body",
        "lambda-body",
        "nested-class-body",
        "future-annotation",
        "lazy-type-alias",
    ),
)
def test_credential_diagnostic_rule_rejects_unapproved_deferred_statements(
    statement,
    future_annotations,
):
    source = _credential_source_with(
        statement,
        future_annotations=future_annotations,
    )

    assert (
        "SecretCarrier: direct class-body shape differs from the exact contract"
        in _credential_violations(source)
    )


@pytest.mark.parametrize(
    "statement",
    (
        "    helper = exec('__repr__ = object()')",
        "    locals().helper = object()",
        "    locals()['helper'] = object()",
        "    target[exec('__repr__ = object()') or 0] = object()",
        "    del locals().helper",
        "    del target[exec('__repr__ = object()') or 0]",
        "    target[exec('__repr__ = object()') or 0] += 1",
        "    for locals().helper in ():\n        pass",
        (
            "    with manager() as target[\n"
            "        exec('__repr__ = object()') or 0\n"
            "    ]:\n"
            "        pass"
        ),
    ),
    ids=(
        "right-hand-side",
        "attribute-assignment-base",
        "subscript-assignment-base",
        "subscript-assignment-index",
        "attribute-delete-base",
        "subscript-delete-index",
        "augmented-target-index",
        "loop-target-base",
        "context-target-index",
    ),
)
def test_credential_diagnostic_rule_inspects_ordinary_evaluated_expressions(
    statement,
):
    violations = _credential_violations(_credential_source_with(statement))

    assert (
        "SecretCarrier: class namespace binding analysis is unbounded"
        in violations
    )


@pytest.mark.parametrize(
    "statement",
    (
        "    holder.__repr__ = object()",
        "    del holder.__repr__",
    ),
    ids=("attribute-assignment", "attribute-deletion"),
)
def test_credential_namespace_collector_does_not_treat_attributes_as_names(
    statement,
):
    events = _credential_events(_credential_source_with(statement))

    assert not any(event.name == "__repr__" for event in events)


def test_credential_namespace_events_preserve_order_origin_and_identity():
    source = _credential_source_with(
        "    __eq__ = object()\n    del __eq__"
    )
    tree = ast.parse(source)
    target = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SecretCarrier"
    )

    events = rewrite_architecture_check._credential_class_namespace_events(
        tree,
        target,
    )
    equality_events = [event for event in events if event.name == "__eq__"]

    assert [
        (event.kind, event.origin, event.direct)
        for event in equality_events
    ] == [
        ("bind", "Assign", False),
        ("delete", "Delete", False),
        ("bind", "FunctionDef", True),
    ]


@pytest.mark.parametrize(
    "protected_fields",
    ((), ("first", "first"), ("missing",)),
    ids=("empty", "duplicate", "outside-declared-inventory"),
)
def test_credential_diagnostic_rule_rejects_invalid_protected_authority(
    protected_fields,
):
    assert _credential_violations(
        _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE,
        protected_fields=protected_fields,
    )


def test_credential_diagnostic_rule_rejects_duplicate_target_class():
    assert _credential_violations(
        _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE
        + _VALID_CREDENTIAL_DIAGNOSTIC_SOURCE
    )


def test_credential_checker_uses_authenticated_module_and_detached_ast(
    monkeypatch,
):
    descriptor = (
        "governed/carrier.py",
        "SecretCarrier",
        ("first",),
        _TEST_CREDENTIAL_DECLARATIONS,
        _TEST_CREDENTIAL_METHODS,
    )
    monkeypatch.setattr(
        rewrite_architecture_check,
        "_CREDENTIAL_DIAGNOSTIC_CARRIERS",
        (descriptor,),
    )
    missing = types.SimpleNamespace(modules_by_relative_path={})
    assert rewrite_architecture_check._check_credential_diagnostic_carriers(
        missing,
        {},
    ) == [
        "governed/carrier.py:SecretCarrier: authenticated module is missing"
    ]

    unit = types.SimpleNamespace(module_name="governed.carrier")
    snapshot = types.SimpleNamespace(
        modules_by_relative_path={"governed/carrier.py": unit}
    )
    assert rewrite_architecture_check._check_credential_diagnostic_carriers(
        snapshot,
        {},
    ) == ["governed/carrier.py:SecretCarrier: detached AST is missing"]
    assert rewrite_architecture_check._check_credential_diagnostic_carriers(
        snapshot,
        {"governed.carrier": ast.parse(_VALID_CREDENTIAL_DIAGNOSTIC_SOURCE)},
    ) == []
