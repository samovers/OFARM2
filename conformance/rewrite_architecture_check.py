#!/usr/bin/env python3
"""Keep rewritten trust-boundary modules small and dependency-explicit."""
from __future__ import annotations

import ast
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MAX_FUNCTION_LINES = 80
MAX_TEST_LINES = 800
MODULE_BUDGETS = {
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
    "kernel/api.py": 120,
    "kernel/deployment_identity.py": 50,
    "kernel/runtime_config.py": 140,
    "kernel/application_runtime.py": 220,
    "kernel/legacy_m1/api.py": 370,
    "kernel/legacy_m1/runtime.py": 100,
    "kernel/security_audit.py": 130,
    "kernel/security_audit_client.py": 220,
    "kernel/authentication_audit.py": 140,
    "kernel/request_router_audit.py": 120,
    "kernel/google_kms_correlation_hmac.py": 220,
    "kernel/security_audit_hmac_posture.py": 260,
    "kernel/security_audit_runtime.py": 210,
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
            "kernel/deployment_identity.py",
        ),
    ),
    "legacy M1 composition": (
        450,
        (
            "kernel/legacy_m1/api.py",
            "kernel/legacy_m1/runtime.py",
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
        210,
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
PRODUCTION_IMPORT_ROOTS = ("kernel.api", "kernel.application_runtime")
LEGACY_IMPORT_ROOTS = ("kernel.legacy_m1.api", "kernel.legacy_m1.runtime")
LEGACY_MODULE_PREFIXES = ("kernel.legacy_m1", "kernel.profiles.si_ffs")
LEGACY_MODULES = frozenset(
    {
        "kernel.adapters",
        "kernel.auth_oidc",
        "kernel.authority",
        "kernel.config",
        "kernel.context",
        "kernel.contracts",
        "kernel.demo",
        "kernel.emission",
        "kernel.gates",
        "kernel.manifest",
        "kernel.materializer",
        "kernel.policy",
        "kernel.profile_policy",
        "kernel.runtime_activation",
        "kernel.schema_posture",
        "kernel.stages",
        "kernel.store",
        "kernel.sufficiency",
        "kernel.validators",
        "kernel.verification",
        "kernel.views",
    }
)
PRODUCTION_COMPOSITION_MODULES = frozenset(
    {
        "kernel.api",
        "kernel.application_runtime",
        "kernel.authentication_audit",
        "kernel.google_kms_correlation_hmac",
        "kernel.google_kms_signer",
        "kernel.key_control",
        "kernel.principal",
        "kernel.principal_control",
        "kernel.principal_resolver",
        "kernel.production_oidc",
        "kernel.request_router_audit",
        "kernel.runtime_config",
        "kernel.security_audit",
        "kernel.security_audit_client",
        "kernel.security_audit_hmac_posture",
        "kernel.security_audit_runtime",
        "kernel.signing_authority",
        "kernel.signing_receipt",
        "kernel.tenant_capability_issuer",
        "kernel.tenant_uow",
    }
)
LEGACY_RESOURCE_NAMES = frozenset({"schema.sql"})


@dataclass(frozen=True, slots=True)
class _ImportEdge:
    target: str
    line: int


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _module_name(root: Path, path: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _module_sources(root: Path) -> dict[str, Path]:
    sources = {}
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or any(
            part.startswith(".") for part in relative.parts
        ):
            continue
        sources[_module_name(root, path)] = path
    return sources


def _from_import_base(
    module: str,
    path: Path,
    node: ast.ImportFrom,
) -> str:
    if node.level == 0:
        return node.module or ""
    package = module.split(".")
    if path.name != "__init__.py":
        package.pop()
    keep = len(package) - node.level + 1
    if keep < 0:
        return ""
    base = package[:keep]
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def _import_edges(
    module: str,
    path: Path,
    tree: ast.Module,
    known_modules: set[str],
) -> tuple[_ImportEdge, ...]:
    edges = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in known_modules:
                    edges.add(_ImportEdge(alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            base = _from_import_base(module, path, node)
            if base in known_modules:
                edges.add(_ImportEdge(base, node.lineno))
            for alias in node.names:
                candidate = f"{base}.{alias.name}" if base else alias.name
                if candidate in known_modules:
                    edges.add(_ImportEdge(candidate, node.lineno))
    return tuple(sorted(edges, key=lambda edge: (edge.line, edge.target)))


def _import_graph(
    sources: dict[str, Path],
) -> tuple[dict[str, tuple[_ImportEdge, ...]], dict[str, ast.Module]]:
    known_modules = set(sources)
    trees = {}
    graph = {}
    for module, path in sorted(sources.items()):
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=path.as_posix(),
        )
        trees[module] = tree
        graph[module] = _import_edges(module, path, tree, known_modules)
    return graph, trees


def _reachable_paths(
    graph: dict[str, tuple[_ImportEdge, ...]],
    roots: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    paths = {}
    pending = deque()
    for root in roots:
        if root in graph:
            paths[root] = (root,)
            pending.append(root)
    while pending:
        module = pending.popleft()
        for edge in graph[module]:
            if edge.target not in paths:
                paths[edge.target] = (*paths[module], edge.target)
                pending.append(edge.target)
    return paths


def _is_legacy_module(module: str) -> bool:
    return module in LEGACY_MODULES or any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in LEGACY_MODULE_PREFIXES
    )


def _incoming_edge(
    graph: dict[str, tuple[_ImportEdge, ...]],
    path: tuple[str, ...],
) -> tuple[str, _ImportEdge] | None:
    if len(path) < 2:
        return None
    source, target = path[-2:]
    edge = next(edge for edge in graph[source] if edge.target == target)
    return source, edge


def _dynamic_import_violations(
    tree: ast.Module,
) -> list[tuple[int, str]]:
    violations = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib" or alias.name.startswith(
                    "importlib."
                ):
                    violations.add(
                        (node.lineno, f"import of {alias.name!r}")
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module and (
                node.module == "importlib"
                or node.module.startswith("importlib.")
            ):
                violations.add(
                    (node.lineno, f"import from {node.module!r}")
                )
            if any(alias.name == "__import__" for alias in node.names):
                violations.add(
                    (node.lineno, "import of built-in '__import__'")
                )
        elif isinstance(node, ast.Name) and node.id == "__import__":
            violations.add(
                (node.lineno, "reference to built-in '__import__'")
            )
        elif isinstance(node, ast.Attribute) and node.attr == "__import__":
            violations.add(
                (node.lineno, "attribute reference to '__import__'")
            )
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
            and (
                (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "getattr"
                )
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "getattr"
                )
            )
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "__import__"
        ):
            violations.add(
                (node.lineno, "literal reflective access to '__import__'")
            )
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == "__import__"
        ):
            violations.add(
                (node.lineno, "literal subscript access to '__import__'")
            )
    return sorted(violations)


def _legacy_resource_violations(
    tree: ast.Module,
) -> list[tuple[int, str]]:
    violations = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        normalized = node.value.replace("\\", "/")
        if normalized in LEGACY_RESOURCE_NAMES or any(
            normalized.endswith(f"/kernel/{name}")
            for name in LEGACY_RESOURCE_NAMES
        ):
            violations.add((node.lineno, normalized))
    return sorted(violations)


def _check_import_firewall(root: Path = ROOT) -> list[str]:
    sources = _module_sources(root)
    graph, trees = _import_graph(sources)
    failures = []

    production_paths = _reachable_paths(graph, PRODUCTION_IMPORT_ROOTS)
    for module, path in sorted(production_paths.items()):
        rendered_path = " -> ".join(path)
        if _is_legacy_module(module):
            incoming = _incoming_edge(graph, path)
            if incoming is not None:
                source, edge = incoming
                relative = sources[source].relative_to(root).as_posix()
                failures.append(
                    f"{relative}:{edge.line}: production import path "
                    f"{rendered_path} reaches legacy module {module!r}"
                )
        for line, reason in _dynamic_import_violations(trees[module]):
            relative = sources[module].relative_to(root).as_posix()
            failures.append(
                f"{relative}:{line}: forbidden dynamic import mechanism "
                f"({reason}); production import path {rendered_path}"
            )
        for line, resource in _legacy_resource_violations(trees[module]):
            relative = sources[module].relative_to(root).as_posix()
            failures.append(
                f"{relative}:{line}: production references legacy resource "
                f"{resource!r}; production import path {rendered_path}"
            )

    legacy_paths = _reachable_paths(graph, LEGACY_IMPORT_ROOTS)
    for module, path in sorted(legacy_paths.items()):
        if module not in PRODUCTION_COMPOSITION_MODULES:
            continue
        incoming = _incoming_edge(graph, path)
        if incoming is None:
            continue
        source, edge = incoming
        relative = sources[source].relative_to(root).as_posix()
        failures.append(
            f"{relative}:{edge.line}: legacy import path "
            f"{' -> '.join(path)} reaches production composition "
            f"module {module!r}"
        )
    return failures


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
    failures = _check_import_firewall()
    for relative, budget in MODULE_BUDGETS.items():
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
    print("rewrite architecture constraints: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
