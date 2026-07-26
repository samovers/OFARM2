#!/usr/bin/env python3
"""Keep rewritten trust-boundary modules small and dependency-explicit."""
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MAX_FUNCTION_LINES = 80
MAX_TEST_LINES = 800
PRODUCTION_BUDGETS = {
    "kernel/profile_runtime_provider.py": 350,
    "kernel/profiles/si_ffs/runtime_provider.py": 350,
    "kernel/authentication.py": 100,
    "kernel/auth_oidc.py": 200,
    "kernel/production_oidc.py": 450,
    "kernel/principal.py": 170,
    "kernel/principal_resolver.py": 110,
    "kernel/principal_control.py": 350,
    "kernel/signing_receipt.py": 250,
    "kernel/signing_authority.py": 250,
    "kernel/google_kms_signer.py": 120,
    "kernel/tenant_capability_issuer.py": 180,
    "kernel/key_control.py": 350,
    "kernel/tenant_uow.py": 450,
    "kernel/api.py": 450,
    "kernel/runtime_config.py": 140,
    "kernel/application_runtime.py": 220,
    "kernel/legacy_runtime.py": 100,
    "kernel/security_audit.py": 130,
    "kernel/security_audit_client.py": 220,
    "kernel/authentication_audit.py": 140,
    "kernel/request_router_audit.py": 120,
    "kernel/google_kms_correlation_hmac.py": 220,
    "kernel/security_audit_hmac_posture.py": 260,
    "kernel/security_audit_runtime.py": 180,
}
GROUP_BUDGETS = {
    "profile runtime": (
        350,
        (
            "kernel/profile_runtime_provider.py",
            "kernel/profiles/si_ffs/runtime_provider.py",
        ),
    ),
    "OIDC verification": (
        650,
        (
            "kernel/authentication.py",
            "kernel/auth_oidc.py",
            "kernel/production_oidc.py",
        ),
    ),
    "principal authority": (
        600,
        (
            "kernel/principal.py",
            "kernel/principal_resolver.py",
            "kernel/principal_control.py",
        ),
    ),
    "capability signing": (
        1_000,
        (
            "kernel/signing_receipt.py",
            "kernel/signing_authority.py",
            "kernel/google_kms_signer.py",
            "kernel/tenant_capability_issuer.py",
            "kernel/key_control.py",
        ),
    ),
    "application runtime": (
        500,
        (
            "kernel/runtime_config.py",
            "kernel/application_runtime.py",
            "kernel/legacy_runtime.py",
        ),
    ),
    "tenant transaction": (
        450,
        ("kernel/tenant_uow.py",),
    ),
    "security audit ingest": (
        350,
        (
            "kernel/security_audit.py",
            "kernel/security_audit_client.py",
        ),
    ),
    "authentication audit producer": (
        140,
        ("kernel/authentication_audit.py",),
    ),
    "request-router audit producer": (
        120,
        ("kernel/request_router_audit.py",),
    ),
    "security audit HMAC": (
        220,
        ("kernel/google_kms_correlation_hmac.py",),
    ),
    "security audit HMAC posture": (
        260,
        ("kernel/security_audit_hmac_posture.py",),
    ),
    "security audit runtime": (
        180,
        ("kernel/security_audit_runtime.py",),
    ),
}
TEST_GLOBS = (
    "kernel/tests/*profile_runtime*.py",
    "kernel/tests/*oidc*.py",
    "kernel/tests/*principal*.py",
    "kernel/tests/*signing*.py",
    "kernel/tests/*key_control*.py",
    "kernel/tests/*application_runtime*.py",
    "kernel/tests/*runtime_config*.py",
    "kernel/tests/*tenant_uow*.py",
    "kernel/tests/*security_audit_client*.py",
    "kernel/tests/*authentication_audit*.py",
    "kernel/tests/*request_router_audit*.py",
    "kernel/tests/*google_kms_correlation_hmac*.py",
    "kernel/tests/*security_audit_hmac_posture*.py",
    "kernel/tests/*security_audit_runtime*.py",
)
PROHIBITED_NAMES = {"for_test", "production_eligible"}


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _annotation_uses_any(annotation: ast.expr | None) -> bool:
    return annotation is not None and any(
        isinstance(node, ast.Name) and node.id == "Any"
        for node in ast.walk(annotation)
    )


def _trust_interface_uses_any(tree: ast.Module) -> list[int]:
    lines = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annotations = [
                *(argument.annotation for argument in node.args.args),
                *(argument.annotation for argument in node.args.kwonlyargs),
                node.returns,
            ]
            if any(_annotation_uses_any(value) for value in annotations):
                lines.append(node.lineno)
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if (
                    isinstance(member, ast.AnnAssign)
                    and _annotation_uses_any(member.annotation)
                ):
                    lines.append(member.lineno)
    return lines


class _EnvironmentReadVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = []
        self.lines: list[int] = []
        self.os_modules = {"os"}
        self.direct_readers: set[str] = set()

    def _visit_scope(self, node) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_ClassDef = _visit_scope
    visit_FunctionDef = _visit_scope
    visit_AsyncFunctionDef = _visit_scope

    def visit_Import(self, node: ast.Import) -> None:
        self.os_modules.update(
            alias.asname or alias.name
            for alias in node.names
            if alias.name == "os"
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "os":
            self.direct_readers.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name in {"getenv", "environ"}
            )

    def _is_environment_reference(self, target) -> bool:
        if isinstance(target, ast.Name):
            return target.id in self.direct_readers
        if not isinstance(target, ast.Attribute):
            return False
        if (
            isinstance(target.value, ast.Name)
            and target.value.id in self.os_modules
            and target.attr in {"getenv", "environ"}
        ):
            return True
        return self._is_environment_reference(target.value)

    def _check(self, node, target) -> None:
        if self._is_environment_reference(target) and self.scope[-2:] != [
            "RuntimeConfig",
            "from_env",
        ]:
            self.lines.append(node.lineno)

    def visit_Call(self, node: ast.Call) -> None:
        self._check(node, node.func)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self._check(node, node.value)
        self.generic_visit(node)


def _environment_reads(tree: ast.Module) -> list[int]:
    visitor = _EnvironmentReadVisitor()
    visitor.visit(tree)
    return visitor.lines


def _check_production(path: Path, budget: int) -> list[str]:
    relative = path.relative_to(ROOT).as_posix()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=relative)
    failures = []
    line_count = len(source.splitlines())
    if line_count > budget:
        failures.append(f"{relative}: {line_count} lines exceeds {budget}")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = node.end_lineno - node.lineno + 1
            if length > MAX_FUNCTION_LINES:
                failures.append(
                    f"{relative}:{node.lineno}: {node.name} is {length} lines; "
                    f"maximum is {MAX_FUNCTION_LINES}"
                )
        if isinstance(node, ast.Name) and node.id in PROHIBITED_NAMES:
            failures.append(
                f"{relative}:{node.lineno}: prohibited name {node.id!r}"
            )
        if isinstance(node, ast.Attribute) and node.attr in PROHIBITED_NAMES:
            failures.append(
                f"{relative}:{node.lineno}: prohibited attribute {node.attr!r}"
            )
    for line in _trust_interface_uses_any(tree):
        failures.append(f"{relative}:{line}: Any appears at a trust interface")
    for line in _environment_reads(tree):
        failures.append(f"{relative}:{line}: domain module reads the environment")
    return failures


def main() -> int:
    failures = []
    for relative, budget in PRODUCTION_BUDGETS.items():
        failures.extend(_check_production(ROOT / relative, budget))
    for name, (budget, relatives) in GROUP_BUDGETS.items():
        total = sum(_line_count(ROOT / relative) for relative in relatives)
        if total > budget:
            failures.append(
                f"{name}: {total} production lines exceeds group budget {budget}"
            )
    test_paths = {
        path
        for pattern in TEST_GLOBS
        for path in ROOT.glob(pattern)
    }
    for path in sorted(test_paths):
        line_count = _line_count(path)
        if line_count > MAX_TEST_LINES:
            failures.append(
                f"{path.relative_to(ROOT)}: {line_count} test lines exceeds "
                f"{MAX_TEST_LINES}"
            )
    if failures:
        print("\n".join(f"FAIL {failure}" for failure in failures))
        return 1
    print("rewrite architecture budgets: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
