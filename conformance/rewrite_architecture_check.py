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
}
GROUP_BUDGETS = {
    "profile runtime": (
        350,
        tuple(PRODUCTION_BUDGETS),
    ),
}
TEST_GLOBS = ("kernel/tests/*profile_runtime*.py",)
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


def _environment_reads(tree: ast.Module) -> list[int]:
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Call, ast.Subscript)):
            continue
        target = node.func if isinstance(node, ast.Call) else node.value
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "os"
            and target.attr in {"getenv", "environ"}
        ):
            lines.append(node.lineno)
    return lines


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
