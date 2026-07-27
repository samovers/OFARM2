"""Hostile subprocess tests for exact provider-source import authority."""
from __future__ import annotations

import os
import py_compile
import subprocess
import sys
import textwrap
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
MODULE_NAME = "provider_fixture.provider"
COMPONENT_REF = "python:test-profile:runtime-provider"
MALICIOUS_SOURCE = "def build():\n    return 'malicious'\n"
VERIFIED_SOURCE = "def build():\n    return 'verified!'\n"


def _provider_fixture(tmp_path: Path, *, hostile_cache: bool = False) -> Path:
    package = tmp_path / "provider_fixture"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = package / "provider.py"
    if hostile_cache:
        assert len(MALICIOUS_SOURCE) == len(VERIFIED_SOURCE)
        source.write_text(MALICIOUS_SOURCE, encoding="utf-8")
        original = source.stat()
        cache_directory = source.parent / "__pycache__"
        cache_directory.mkdir()
        cache = (
            cache_directory
            / f"provider.{sys.implementation.cache_tag}.pyc"
        )
        py_compile.compile(str(source), cfile=str(cache), doraise=True)
        source.write_text(VERIFIED_SOURCE, encoding="utf-8")
        os.utime(
            source,
            ns=(original.st_atime_ns, original.st_mtime_ns),
        )
    else:
        source.write_text(VERIFIED_SOURCE, encoding="utf-8")
    return source


def _run_child(tmp_path: Path, source: Path, body: str):
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(PACKAGE_ROOT)!r})\n"
        f"sys.path.insert(0, {str(tmp_path)!r})\n"
        "from kernel.provider_import_policy import (\n"
        "    ProviderImportError,\n"
        "    load_provider_factory,\n"
        ")\n"
        f"module_name = {MODULE_NAME!r}\n"
        f"component_ref = {COMPONENT_REF!r}\n"
        f"source_path = Path({str(source)!r})\n"
        f"source_bytes = {VERIFIED_SOURCE.encode()!r}\n"
        + textwrap.dedent(body)
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=PACKAGE_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )


def _assert_child_passed(result) -> None:
    assert result.returncode == 0, (
        f"child stdout:\n{result.stdout}\nchild stderr:\n{result.stderr}"
    )


def test_code_owned_posture_ignores_timestamp_valid_provider_bytecode(
    tmp_path,
):
    source = _provider_fixture(tmp_path, hostile_cache=True)
    cache = next((source.parent / "__pycache__").glob("provider.*.pyc"))
    hostile_cache_bytes = cache.read_bytes()
    normal = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys\n"
                f"sys.path.insert(0, {str(tmp_path)!r})\n"
                "from provider_fixture.provider import build\n"
                "print(build())\n"
            ),
        ],
        cwd=PACKAGE_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert normal.returncode == 0
    assert normal.stdout.strip() == "malicious"

    admitted = _run_child(
        tmp_path,
        source,
        """
        def resolve():
            from provider_fixture.provider import build
            return build

        factory = load_provider_factory(
            module_name=module_name,
            component_ref=component_ref,
            source_path=source_path,
            source_bytes=source_bytes,
            factory_name="build",
            factory_resolver=resolve,
        )
        assert factory() == "verified!"
        assert sys.dont_write_bytecode is True
        assert Path(sys.pycache_prefix) != source_path.parent / "__pycache__"
        """,
    )

    _assert_child_passed(admitted)
    assert cache.read_bytes() == hostile_cache_bytes


def test_provider_import_refuses_unattested_preloaded_module(tmp_path):
    source = _provider_fixture(tmp_path)
    result = _run_child(
        tmp_path,
        source,
        """
        from provider_fixture.provider import build as early_build

        def resolve():
            return early_build

        try:
            load_provider_factory(
                module_name=module_name,
                component_ref=component_ref,
                source_path=source_path,
                source_bytes=source_bytes,
                factory_name="build",
                factory_resolver=resolve,
            )
        except ProviderImportError as exc:
            assert "before trusted admission" in str(exc)
        else:
            raise AssertionError("preloaded provider was admitted")
        """,
    )

    _assert_child_passed(result)


def test_provider_import_reuses_only_one_attested_literal_import(tmp_path):
    source = _provider_fixture(tmp_path)
    result = _run_child(
        tmp_path,
        source,
        """
        calls = 0

        def resolve():
            global calls
            calls += 1
            from provider_fixture.provider import build
            return build

        arguments = dict(
            module_name=module_name,
            component_ref=component_ref,
            source_path=source_path,
            source_bytes=source_bytes,
            factory_name="build",
            factory_resolver=resolve,
        )
        first = load_provider_factory(**arguments)
        second = load_provider_factory(**arguments)
        assert first is second
        assert calls == 1
        assert second() == "verified!"
        """,
    )

    _assert_child_passed(result)


def test_provider_import_refuses_replaced_attested_module(tmp_path):
    source = _provider_fixture(tmp_path)
    result = _run_child(
        tmp_path,
        source,
        """
        from types import ModuleType

        def resolve():
            from provider_fixture.provider import build
            return build

        arguments = dict(
            module_name=module_name,
            component_ref=component_ref,
            source_path=source_path,
            source_bytes=source_bytes,
            factory_name="build",
            factory_resolver=resolve,
        )
        load_provider_factory(**arguments)
        sys.modules[module_name] = ModuleType(module_name)
        try:
            load_provider_factory(**arguments)
        except ProviderImportError as exc:
            assert "before trusted admission" in str(exc)
        else:
            raise AssertionError("replaced provider module was admitted")
        """,
    )

    _assert_child_passed(result)


def test_provider_import_refuses_changed_posture_on_reuse(tmp_path):
    source = _provider_fixture(tmp_path)
    result = _run_child(
        tmp_path,
        source,
        """
        def resolve():
            from provider_fixture.provider import build
            return build

        arguments = dict(
            module_name=module_name,
            component_ref=component_ref,
            source_path=source_path,
            source_bytes=source_bytes,
            factory_name="build",
            factory_resolver=resolve,
        )
        load_provider_factory(**arguments)
        sys.dont_write_bytecode = False
        try:
            load_provider_factory(**arguments)
        except ProviderImportError as exc:
            assert "bytecode posture changed" in str(exc)
        else:
            raise AssertionError("changed bytecode posture was admitted")
        """,
    )

    _assert_child_passed(result)


def test_provider_import_refuses_factory_from_another_module(tmp_path):
    source = _provider_fixture(tmp_path)
    helper = source.parent / "helper.py"
    helper.write_text(VERIFIED_SOURCE, encoding="utf-8")
    result = _run_child(
        tmp_path,
        source,
        """
        def resolve():
            from provider_fixture.provider import build as provider_build
            from provider_fixture.helper import build
            assert provider_build() == "verified!"
            return build

        try:
            load_provider_factory(
                module_name=module_name,
                component_ref=component_ref,
                source_path=source_path,
                source_bytes=source_bytes,
                factory_name="build",
                factory_resolver=resolve,
            )
        except ProviderImportError as exc:
            assert "factory identity differs" in str(exc)
        else:
            raise AssertionError("foreign provider factory was admitted")
        """,
    )

    _assert_child_passed(result)


def test_provider_import_refuses_source_changed_after_attestation(tmp_path):
    source = _provider_fixture(tmp_path)
    result = _run_child(
        tmp_path,
        source,
        """
        def resolve():
            from provider_fixture.provider import build
            return build

        arguments = dict(
            module_name=module_name,
            component_ref=component_ref,
            source_path=source_path,
            source_bytes=source_bytes,
            factory_name="build",
            factory_resolver=resolve,
        )
        load_provider_factory(**arguments)
        source_path.write_text(
            "def build():\\n    return 'changed!!'\\n",
            encoding="utf-8",
        )
        try:
            load_provider_factory(**arguments)
        except ProviderImportError as exc:
            assert "differs from its verified bytes" in str(exc)
        else:
            raise AssertionError("changed provider source was admitted")
        """,
    )

    _assert_child_passed(result)
