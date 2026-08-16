"""Keep the clean trust-boundary stack inside its structural budgets."""

import ast

from conformance import rewrite_architecture_check
from conformance.rewrite_architecture_check import main


def test_rewrite_architecture_budgets():
    assert main() == 0


def test_runtime_config_from_env_is_the_only_environment_reader():
    source = """
import os as environment
class RuntimeConfig:
    @classmethod
    def from_env(cls):
        return environment.environ["SETTING"]
"""

    assert rewrite_architecture_check._environment_reads(
        ast.parse(source)
    ) == []


def _tenant_uow_source(*, initializer="binding, allocate_batch", extra=""):
    return f"""
class TenantUnitOfWork:
    __slots__ = ("__binding", "__active", "__allocate_batch", "__batch")
    def __init__(self, {initializer}):
        self.__binding = binding
        self.__active = True
        self.__allocate_batch = allocate_batch
        self.__batch = None
    @property
    def binding(self):
        return self.__binding
    @property
    def batch(self):
        return self.__batch
    def begin_batch(self, request):
        return self.__allocate_batch(request)
    {extra}
"""


def test_tenant_uow_architecture_allows_only_the_narrow_facade():
    tree = ast.parse(_tenant_uow_source())

    assert rewrite_architecture_check._tenant_uow_class_violations(tree) == []


def test_tenant_uow_architecture_rejects_raw_handle_and_surface_expansion():
    source = _tenant_uow_source(
        initializer="binding, connection",
        extra="def execute(self, query): return self._connection.execute(query)",
    )

    reasons = {
        reason
        for _line, reason in (
            rewrite_architecture_check._tenant_uow_class_violations(ast.parse(source))
        )
    }

    assert "TenantUnitOfWork accepts a non-facade dependency" in reasons
    assert "TenantUnitOfWork stores a raw handle" in reasons
    assert any("public surface" in reason for reason in reasons)


def test_tenant_uow_architecture_flags_only_direct_private_facade_access():
    tree = ast.parse(
        "unit.connection.execute('COMMIT')\n"
        "unit.cursor.execute('ROLLBACK')\n"
        "unit._TenantUnitOfWork__allocate_batch(request)\n"
        "manager._pool.getconn()\n"
    )

    assert rewrite_architecture_check._tenant_handle_escape_accesses(tree) == [
        (3, "_TenantUnitOfWork__allocate_batch"),
    ]
