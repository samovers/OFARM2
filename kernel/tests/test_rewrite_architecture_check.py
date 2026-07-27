"""Regression tests for the rewrite architecture gate."""

import ast
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


def _firewall_tree(tmp_path: Path, api_source: str) -> None:
    _write_module(tmp_path, "kernel/__init__.py")
    _write_module(tmp_path, "kernel/api.py", api_source)
    _write_module(tmp_path, "kernel/application_runtime.py")
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
    _write_module(tmp_path, "kernel/__init__.py")
    _write_module(tmp_path, "kernel/profile_runtime_provider.py")

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
