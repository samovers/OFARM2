#!/usr/bin/env python3
"""Run and compare deterministic, evidence-only Kernel review baselines."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "conformance" / "review_baseline_config.json"
EVIDENCE_SCHEMA = "ofarm.review-baseline-evidence.v1"
COMPARISON_SCHEMA = "ofarm.review-baseline-comparison.v1"
NORMALIZATION_POLICY = "ofarm.review-baseline-normalization.v1"
VOLATILE_POINTERS = (
    "/run/startedAt",
    "/run/finishedAt",
    "/environment/ci/runId",
    "/environment/ci/runAttempt",
)
ALLOWED_OFARM_ENV = {"OFARM_PG_DSN", "OFARM_PG_ADMIN_DSN"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _controlled_output(path: Path, *, must_be_empty: bool) -> Path:
    resolved = path.expanduser().resolve()
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError:
        relative = None
    if relative is not None and (not relative.parts or relative.parts[0] != ".artifacts"):
        raise ValueError("repository-local output must stay under ignored .artifacts/")
    if must_be_empty and resolved.exists() and any(resolved.iterdir()):
        raise ValueError(f"output directory is not empty: {resolved}")
    return resolved


def _run_capture(args: list[str]) -> str:
    result = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def _git_state() -> dict[str, Any]:
    sha = _run_capture(["git", "rev-parse", "HEAD"])
    tree_sha = _run_capture(["git", "rev-parse", "HEAD^{tree}"])
    status = _run_capture([
        "git", "status", "--porcelain=v1", "--untracked-files=all",
    ])
    entries = status.splitlines() if status else []
    return {
        "sha": sha,
        "treeSha": tree_sha,
        "dirty": bool(entries),
        "dirtyEntryCount": len(entries),
        "statusDigest": _sha256_bytes((status + "\n").encode()),
    }


def _sanitized_environment(config: dict[str, Any]) -> dict[str, str]:
    original = os.environ
    env = dict(original)
    for name in list(env):
        if name.startswith("OFARM_") or name in {
            "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONPATH", "PYTHONWARNINGS",
        }:
            env.pop(name, None)
    for name in ALLOWED_OFARM_ENV:
        if original.get(name):
            env[name] = original[name]
    required = config["requiredEnvironment"]
    env.update({
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": required["pythonHashSeed"],
        "TZ": required["timezone"],
        "LANG": required["locale"],
        "LC_ALL": required["locale"],
        "OFARM_DISABLE_PLATFORM_MVP_EVIDENCE": "1",
    })
    return env


def _normalise_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_lock(path: Path) -> dict[str, str]:
    packages: dict[str, str] = {}
    pattern = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        name, version = match.groups()
        normalised = _normalise_name(name)
        if normalised in packages:
            raise ValueError(f"duplicate locked distribution {normalised}")
        packages[normalised] = version
    if not packages:
        raise ValueError(f"no locked distributions in {path}")
    return packages


def _installed_distributions() -> dict[str, str]:
    installed: dict[str, str] = {}
    for distribution in metadata.distributions():
        raw_name = distribution.metadata.get("Name")
        if not raw_name:
            continue
        name = _normalise_name(raw_name)
        if name in installed and installed[name] != distribution.version:
            raise ValueError(f"multiple installed versions of {name}")
        installed[name] = distribution.version
    return installed


def _admin_dsn(env: dict[str, str]) -> str:
    if env.get("OFARM_PG_ADMIN_DSN"):
        return env["OFARM_PG_ADMIN_DSN"]
    return (
        f"host={ROOT / '.pgrun'} port=54317 dbname=postgres user=ofarm"
    )


def _postgres_version(env: dict[str, str]) -> tuple[str | None, str | None]:
    try:
        import psycopg
        with psycopg.connect(_admin_dsn(env)) as connection:
            raw = connection.execute("SHOW server_version").fetchone()[0]
        match = re.match(r"(\d+\.\d+)", raw)
        return (match.group(1) if match else None), raw
    except Exception as exc:  # evidence must still be emitted when DB is unavailable
        return None, f"{type(exc).__name__}: {exc}"


def _execute(args: list[str], env: dict[str, str]) -> int:
    print("+", " ".join(args), flush=True)
    return subprocess.run(args, cwd=ROOT, env=env, check=False).returncode


def _step(name: str, command: list[str], exit_code: int | None, reason: str | None = None):
    if exit_code is None:
        outcome = "unavailable"
    else:
        outcome = "passed" if exit_code == 0 else "failed"
    value: dict[str, Any] = {
        "name": name,
        "command": command,
        "outcome": outcome,
        "exitCode": exit_code,
    }
    if reason:
        value["reason"] = reason
    return value


def _preflight(config: dict[str, Any], env: dict[str, str], pip_check_code: int):
    dependency_lock = ROOT / config["paths"]["dependencyLock"]
    pip_lock = ROOT / config["paths"]["packageManagerLock"]
    expected = _parse_lock(dependency_lock)
    expected.update(_parse_lock(pip_lock))
    actual = _installed_distributions()
    missing = {name: version for name, version in expected.items() if actual.get(name) != version}
    unexpected = {name: version for name, version in actual.items() if name not in expected}
    python_actual = ".".join(map(str, sys.version_info[:3]))
    operating_system = platform.system()
    machine = platform.machine()
    implementation = platform.python_implementation()
    postgres_actual, postgres_raw = _postgres_version(env)
    required = config["requiredEnvironment"]
    reasons: list[str] = []
    if operating_system != required["operatingSystem"]:
        reasons.append(f"operating system {operating_system} != {required['operatingSystem']}")
    if machine != required["machine"]:
        reasons.append(f"machine {machine} != {required['machine']}")
    if implementation != required["pythonImplementation"]:
        reasons.append(
            f"Python implementation {implementation} != {required['pythonImplementation']}"
        )
    if python_actual != required["pythonVersion"]:
        reasons.append(f"Python {python_actual} != {required['pythonVersion']}")
    if actual.get("pip") != required["pipVersion"]:
        reasons.append(f"pip {actual.get('pip')} != {required['pipVersion']}")
    if pip_check_code != 0:
        reasons.append("pip check failed")
    if missing:
        reasons.append("locked distributions missing or mismatched")
    if unexpected:
        reasons.append("unexpected installed distributions")
    if postgres_actual != required["postgresqlVersion"]:
        reasons.append(f"PostgreSQL {postgres_actual} != {required['postgresqlVersion']}")

    distributions = [
        {"name": name, "version": actual[name]}
        for name in sorted(actual)
    ]
    environment = {
        "platform": {
            "operatingSystem": {"required": required["operatingSystem"],
                                "actual": operating_system},
            "machine": {"required": required["machine"], "actual": machine},
        },
        "python": {
            "implementation": {"required": required["pythonImplementation"],
                               "actual": implementation},
            "version": {"required": required["pythonVersion"], "actual": python_actual},
        },
        "pip": {"required": required["pipVersion"], "actual": actual.get("pip")},
        "postgresql": {
            "required": required["postgresqlVersion"],
            "actual": postgres_actual,
            "serverVersionSql": postgres_raw,
        },
        "dependencies": {
            "installed": distributions,
            "installedSetDigest": _sha256_bytes(_canonical_bytes(distributions)),
            "missingOrMismatched": missing,
            "unexpected": unexpected,
            "pipCheckPassed": pip_check_code == 0,
        },
        "determinism": {
            "pythonHashSeed": env["PYTHONHASHSEED"],
            "timezone": env["TZ"],
            "locale": env["LC_ALL"],
            "pytestPluginAutoloadDisabled": True,
            "pythonNoUserSite": True,
            "pythonDontWriteBytecode": True,
            "scrubbedAmbientVariables": [
                "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONPATH",
                "PYTHONWARNINGS", "OFARM_*",
            ],
            "allowedOfarmVariables": sorted(ALLOWED_OFARM_ENV),
        },
        "ci": {
            "configuredRunnerLabel": required["runner"],
            "observedImageOs": os.environ.get("ImageOS"),
            "observedImageVersion": os.environ.get("ImageVersion"),
            "runId": os.environ.get("GITHUB_RUN_ID"),
            "runAttempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "configuredActionPins": config["knownGreenBaseline"]["observedInRun"]["actions"],
            "configuredPostgresqlImageDigest": config["knownGreenBaseline"]["observedInRun"]["postgresqlImageDigest"],
        },
    }
    return environment, reasons


def _empty_results(reason: str) -> dict[str, Any]:
    return {
        "schemaVersion": "ofarm.review-baseline-pytest-results.v1",
        "collection": {"collected": [], "selected": [], "deselected": [],
                       "errors": [{"collector": "pytest", "outcome": reason}]},
        "execution": {"outcomes": [], "skipped": [], "unavailable": []},
        "warnings": [],
        "summary": {"collected": 0, "selected": 0, "passed": 0, "failed": 0,
                    "error": 0, "xfailed": 0, "xpassed": 0, "skipped": 0,
                    "deselected": 0, "unavailable": 0, "collectionErrors": 1,
                    "warnings": 0, "pytestExitStatus": 3},
    }


def _mark_unavailable(results: dict[str, Any], reason: str) -> None:
    selected = results["collection"]["selected"]
    results["execution"]["outcomes"] = [
        {**entry, "outcome": "unavailable", "phases": []}
        for entry in selected
    ]
    results["execution"]["skipped"] = []
    results["execution"]["unavailable"] = [
        {**entry, "reason": reason} for entry in selected
    ]
    summary = results["summary"]
    for field in ("passed", "failed", "error", "xfailed", "xpassed", "skipped"):
        summary[field] = 0
    summary["unavailable"] = len(selected)


def _test_result_is_complete(results: dict[str, Any]) -> bool:
    summary = results["summary"]
    return (
        summary["collected"] > 0
        and summary["selected"] == summary["collected"]
        and summary["passed"] == summary["selected"]
        and all(summary[field] == 0 for field in (
            "failed", "error", "xfailed", "xpassed", "skipped", "deselected",
            "unavailable", "collectionErrors",
        ))
        and summary["pytestExitStatus"] == 0
    )


def _git_preflight_reasons(git: dict[str, Any]) -> list[str]:
    if git.get("dirty") is not False:
        return ["Git worktree is dirty"]
    return []


def run_baseline(output_arg: str) -> int:
    git = _git_state()  # must happen before the ignored output directory exists
    output = _controlled_output(Path(output_arg), must_be_empty=True)
    output.mkdir(parents=True, exist_ok=True)
    config = _read_json(CONFIG_PATH)
    env = _sanitized_environment(config)
    started = _utc_now()
    python_display = "python"

    package_command = [python_display, "conformance/ofarm_pkg_contract_check.py"]
    package_code = _execute([sys.executable, package_command[1]], env)
    pip_command = [python_display, "-m", "pip", "check"]
    pip_code = _execute([sys.executable, "-m", "pip", "check"], env)
    environment, preflight_reasons = _preflight(config, env, pip_code)
    preflight_reasons = _git_preflight_reasons(git) + preflight_reasons

    results_path = output / "kernel-test-results.json"
    pytest_command = [
        python_display, "-m", "pytest", config["paths"]["testRoot"], "-q",
        "-p", "no:cacheprovider",
        "-p", "conformance.review_baseline_pytest",
        "--review-baseline-results", "kernel-test-results.json",
    ]
    actual_pytest_command = [
        sys.executable, "-m", "pytest", config["paths"]["testRoot"], "-q",
        "-p", "no:cacheprovider",
        "-p", "conformance.review_baseline_pytest",
        "--review-baseline-results", str(results_path),
    ]
    if preflight_reasons:
        collection_command = actual_pytest_command + ["--collect-only"]
        pytest_code = _execute(collection_command, env)
    else:
        pytest_code = _execute(actual_pytest_command, env)

    if results_path.exists():
        test_results = _read_json(results_path)
    else:
        test_results = _empty_results("pytest did not produce an inventory")
    if preflight_reasons:
        _mark_unavailable(test_results, "; ".join(preflight_reasons))
        _write_json(results_path, test_results)

    manifest_command = [python_display, "-m", "kernel.manifest", "--verify-generated"]
    if preflight_reasons:
        manifest_code = None
    else:
        manifest_code = _execute(
            [sys.executable, "-m", "kernel.manifest", "--verify-generated"], env,
        )

    dependency_lock = ROOT / config["paths"]["dependencyLock"]
    pip_lock = ROOT / config["paths"]["packageManagerLock"]
    schema = ROOT / config["paths"]["schema"]
    verified_artifacts = [
        {"path": path, "sha256": _sha256_file(ROOT / path)}
        for path in config["verifiedArtifacts"]
    ]
    steps = [
        _step("package-self-check", package_command, package_code),
        _step("pip-check", pip_command, pip_code),
        _step(
            "environment-preflight", ["internal:exact-environment-preflight"],
            0 if not preflight_reasons else 1,
            "; ".join(preflight_reasons) if preflight_reasons else None,
        ),
        _step(
            "complete-kernel-tests", pytest_command,
            None if preflight_reasons else pytest_code,
            "; ".join(preflight_reasons) if preflight_reasons else None,
        ),
        _step(
            "verify-generated-manifest", manifest_command, manifest_code,
            "environment preflight failed" if manifest_code is None else None,
        ),
    ]
    complete = _test_result_is_complete(test_results)
    passed = (
        not preflight_reasons and package_code == pip_code == pytest_code == 0
        and manifest_code == 0 and complete
    )
    evidence = {
        "schemaVersion": EVIDENCE_SCHEMA,
        "normalizationPolicy": _normalization_policy(),
        "run": {
            "startedAt": started,
            "finishedAt": _utc_now(),
            "canonicalCommand": config["canonicalCommand"],
            "outcome": "passed" if passed else "failed",
        },
        "git": git,
        "inputs": {
            "config": {"path": str(CONFIG_PATH.relative_to(ROOT)),
                       "sha256": _sha256_file(CONFIG_PATH)},
            "dependencyLock": {"path": str(dependency_lock.relative_to(ROOT)),
                               "sha256": _sha256_file(dependency_lock)},
            "packageManagerLock": {"path": str(pip_lock.relative_to(ROOT)),
                                   "sha256": _sha256_file(pip_lock)},
            "schema": {"path": str(schema.relative_to(ROOT)),
                       "sha256": _sha256_file(schema)},
        },
        "environment": environment,
        "tests": test_results,
        "steps": steps,
        "producedArtifacts": [{
            "path": results_path.name,
            "sha256": _sha256_file(results_path),
            "bytes": results_path.stat().st_size,
        }],
        "producedArtifactsNote": (
            "The evidence envelope excludes its own digest to avoid recursive "
            "self-reference. Its raw digest is recorded by the comparison proof."
        ),
        "verifiedArtifacts": verified_artifacts,
    }
    evidence_path = output / "review-baseline-evidence.json"
    _write_json(evidence_path, evidence)
    print(f"review baseline {'PASS' if passed else 'FAIL'}: {evidence_path}")
    return 0 if passed else 1


def _remove_pointer(document: dict[str, Any], pointer: str) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~")
             for part in pointer.split("/")[1:]]
    target: Any = document
    for part in parts[:-1]:
        if not isinstance(target, dict) or part not in target:
            raise ValueError(f"normalization pointer missing: {pointer}")
        target = target[part]
    if not isinstance(target, dict) or parts[-1] not in target:
        raise ValueError(f"normalization pointer missing: {pointer}")
    del target[parts[-1]]


def _normalization_policy() -> dict[str, Any]:
    body = {
        "id": NORMALIZATION_POLICY,
        "volatileJsonPointers": list(VOLATILE_POINTERS),
    }
    return {**body, "sha256": _sha256_bytes(_canonical_bytes(body))}


def _normalised_evidence(evidence: dict[str, Any]) -> bytes:
    policy = evidence.get("normalizationPolicy")
    expected = _normalization_policy()
    if policy != expected:
        raise ValueError("evidence normalization policy is not the fixed v1 policy")
    value = copy.deepcopy(evidence)
    for pointer in VOLATILE_POINTERS:
        _remove_pointer(value, pointer)
    return _canonical_bytes(value)


def _difference_paths(left: Any, right: Any, pointer: str = "") -> list[str]:
    if type(left) is not type(right):
        return [pointer or "/"]
    if isinstance(left, dict):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            child = f"{pointer}/{escaped}"
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(_difference_paths(left[key], right[key], child))
        return paths
    if isinstance(left, list):
        if len(left) != len(right):
            return [f"{pointer}/length"]
        paths = []
        for index, (left_value, right_value) in enumerate(zip(left, right)):
            paths.extend(_difference_paths(
                left_value, right_value, f"{pointer}/{index}",
            ))
        return paths
    return [] if left == right else [pointer or "/"]


def compare_evidence(left_arg: str, right_arg: str, output_arg: str) -> int:
    left_path = Path(left_arg).resolve()
    right_path = Path(right_arg).resolve()
    output = _controlled_output(Path(output_arg).parent, must_be_empty=False) / Path(output_arg).name
    if output.exists():
        raise ValueError(f"comparison output already exists: {output}")
    left = _read_json(left_path)
    right = _read_json(right_path)
    for label, evidence in (("left", left), ("right", right)):
        if evidence.get("schemaVersion") != EVIDENCE_SCHEMA:
            raise ValueError(f"{label} evidence has the wrong schemaVersion")
        if evidence.get("git", {}).get("dirty") is not False:
            raise ValueError(f"{label} evidence is not from a clean worktree")
        if evidence.get("run", {}).get("outcome") != "passed":
            raise ValueError(f"{label} evidence did not pass")
    left_normal = _normalised_evidence(left)
    right_normal = _normalised_evidence(right)
    equivalent = left_normal == right_normal
    left_value = json.loads(left_normal)
    right_value = json.loads(right_normal)
    proof = {
        "schemaVersion": COMPARISON_SCHEMA,
        "normalizationPolicy": _normalization_policy(),
        "left": {
            "rawSha256": _sha256_file(left_path),
            "normalizedSha256": _sha256_bytes(left_normal),
        },
        "right": {
            "rawSha256": _sha256_file(right_path),
            "normalizedSha256": _sha256_bytes(right_normal),
        },
        "equivalent": equivalent,
        "differenceJsonPointers": _difference_paths(left_value, right_value),
    }
    _write_json(output, proof)
    print(f"review baseline equivalence {'PASS' if equivalent else 'FAIL'}: {output}")
    return 0 if equivalent else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run one complete Kernel baseline")
    run.add_argument("--output-dir", required=True)
    compare = commands.add_parser("compare", help="compare two clean baseline envelopes")
    compare.add_argument("left")
    compare.add_argument("right")
    compare.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return run_baseline(args.output_dir)
        return compare_evidence(args.left, args.right, args.output)
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"review baseline ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
