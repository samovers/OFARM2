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
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "conformance" / "review_baseline_config.json"
ISOLATED_LAUNCHER = ROOT / "tooling" / "ofarm_isolated.py"
EVIDENCE_SCHEMA = "ofarm.review-baseline-evidence.v2"
COMPARISON_SCHEMA = "ofarm.review-baseline-comparison.v2"
NORMALIZATION_POLICY = "ofarm.review-baseline-normalization.v2"
INVENTORY_SCHEMA = "ofarm.review-baseline-test-inventory.v1"
VOLATILE_POINTERS = (
    "/run/startedAt",
    "/run/finishedAt",
    "/environment/ci/runId",
    "/environment/ci/runAttempt",
)
ALLOWED_OFARM_ENV = {"OFARM_PG_ADMIN_DSN"}


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


def _run_capture(args: list[str], *, cwd: Path = ROOT) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def _git_state(root: Path = ROOT) -> dict[str, Any]:
    sha = _run_capture(["git", "rev-parse", "HEAD"], cwd=root)
    tree_sha = _run_capture(["git", "rev-parse", "HEAD^{tree}"], cwd=root)
    status = _run_capture([
        "git", "status", "--porcelain=v1", "--untracked-files=all",
    ], cwd=root)
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
            "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONOPTIMIZE",
            "PYTHONCASEOK", "PYTHONEXECUTABLE", "PYTHONHASHSEED",
            "PYTHONHOME", "PYTHONINSPECT",
            "PYTHONMALLOC", "PYTHONPATH", "PYTHONPLATLIBDIR",
            "PYTHONPYCACHEPREFIX", "PYTHONSAFEPATH", "PYTHONSTARTUP",
            "PYTHONWARNINGS", "GLIBC_TUNABLES", "GCONV_PATH",
        } or name.startswith(("LD_", "DYLD_")):
            env.pop(name, None)
    for name in ALLOWED_OFARM_ENV:
        if original.get(name):
            env[name] = original[name]
    required = config["requiredEnvironment"]
    if env.get("OFARM_PG_ADMIN_DSN"):
        try:
            env["OFARM_PG_DSN"] = _derive_test_dsn(
                env["OFARM_PG_ADMIN_DSN"], required["testDatabaseName"])
        except ValueError:
            # Preflight records the unavailable derived route. Keep collection
            # and evidence emission alive without exposing the malformed DSN.
            env.pop("OFARM_PG_DSN", None)
    env.update({
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TZ": required["timezone"],
        "LANG": required["locale"],
        "LC_ALL": required["locale"],
        "OFARM_DISABLE_PLATFORM_MVP_EVIDENCE": "1",
    })
    return env


def _derive_test_dsn(admin_dsn: str, test_database_name: str) -> str:
    if not isinstance(test_database_name, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]{0,62}", test_database_name):
        raise ValueError("review baseline test database name is unsafe")
    try:
        from psycopg.conninfo import make_conninfo
        return make_conninfo(admin_dsn, dbname=test_database_name)
    except Exception as exc:
        raise ValueError("review baseline admin DSN cannot derive the test route") from exc


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


def _postgres_identity(dsn: str) -> dict[str, Any]:
    """Return a safe SQL-observed server identity without exposing the DSN."""
    try:
        import psycopg
        with psycopg.connect(dsn) as connection:
            raw = connection.execute("SHOW server_version").fetchone()[0]
            database = connection.execute("SELECT current_database()").fetchone()[0]
            system_identifier = connection.execute(
                "SELECT system_identifier::text FROM pg_control_system()"
            ).fetchone()[0]
        match = re.match(r"(\d+\.\d+)", raw)
        return {
            "available": True,
            "version": match.group(1) if match else None,
            "rawVersion": raw,
            "systemIdentifier": system_identifier,
            "database": database,
        }
    except Exception as exc:  # evidence must still be emitted when DB is unavailable
        return {
            "available": False,
            "errorType": type(exc).__name__,
            "version": None,
            "rawVersion": None,
            "systemIdentifier": None,
            "database": None,
        }


def _postgres_identity_reasons(
    admin: dict[str, Any],
    test_store: dict[str, Any],
    expected_test_database: str,
) -> list[str]:
    reasons: list[str] = []
    if test_store.get("available") is not True:
        reasons.append("test-store PostgreSQL identity is unavailable")
    if admin.get("available") is not True:
        reasons.append("admin PostgreSQL identity is unavailable")
    if reasons:
        return reasons
    if admin.get("version") != test_store.get("version"):
        reasons.append("admin and test-store PostgreSQL versions differ")
    if admin.get("rawVersion") != test_store.get("rawVersion"):
        reasons.append("admin and test-store PostgreSQL build versions differ")
    if admin.get("systemIdentifier") != test_store.get("systemIdentifier"):
        reasons.append("admin and test-store PostgreSQL servers differ")
    if test_store.get("database") != expected_test_database:
        reasons.append("test-store PostgreSQL database name differs from the pinned target")
    return reasons


def _execute(args: list[str], env: dict[str, str]) -> int:
    print("+", " ".join(args), flush=True)
    return subprocess.run(args, cwd=ROOT, env=env, check=False).returncode


def _isolated_python(module: str, *arguments: str) -> list[str]:
    """Use the same closed import posture for every baseline subprocess."""
    venv_root = Path(sys.executable).absolute().parent.parent
    return [
        sys.executable, "-I", "-B", "-S", str(ISOLATED_LAUNCHER),
        "--venv-root", str(venv_root), "-m", module, *arguments,
    ]


def _isolated_display(module: str, *arguments: str) -> list[str]:
    return [
        ".review-venv/bin/python", "-I", "-B", "-S",
        "tooling/ofarm_isolated.py", "--venv-root", ".review-venv",
        "-m", module, *arguments,
    ]


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


def _python_optimization_reasons(
    required: int,
    actual: int | None = None,
) -> list[str]:
    effective = sys.flags.optimize if actual is None else actual
    if effective != required:
        return [f"Python optimization level {effective} != {required}"]
    return []


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
    optimization_actual = sys.flags.optimize
    admin_postgres = _postgres_identity(_admin_dsn(env))
    required = config["requiredEnvironment"]
    reasons: list[str] = []
    for name in sorted(ALLOWED_OFARM_ENV):
        if not env.get(name):
            reasons.append(f"required database environment variable {name} is absent")
    if not env.get("OFARM_PG_DSN"):
        reasons.append("derived test-store database route is absent")
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
    reasons.extend(_python_optimization_reasons(
        required["pythonOptimizationLevel"], optimization_actual))
    if actual.get("pip") != required["pipVersion"]:
        reasons.append(f"pip {actual.get('pip')} != {required['pipVersion']}")
    if pip_check_code != 0:
        reasons.append("pip check failed")
    if missing:
        reasons.append("locked distributions missing or mismatched")
    if unexpected:
        reasons.append("unexpected installed distributions")
    if admin_postgres["version"] != required["postgresqlVersion"]:
        reasons.append(
            f"PostgreSQL {admin_postgres['version']} != "
            f"{required['postgresqlVersion']}"
        )

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
            "optimizationLevel": {
                "required": required["pythonOptimizationLevel"],
                "actual": optimization_actual,
            },
        },
        "pip": {"required": required["pipVersion"], "actual": actual.get("pip")},
        "postgresql": {
            "requiredVersion": required["postgresqlVersion"],
            "testConnectionSource": "derived-from-verified-admin-connection",
            "testDatabase": required["testDatabaseName"],
            "admin": admin_postgres,
            "testStore": None,
            "sameServer": None,
        },
        "dependencies": {
            "installed": distributions,
            "installedSetDigest": _sha256_bytes(_canonical_bytes(distributions)),
            "missingOrMismatched": missing,
            "unexpected": unexpected,
            "pipCheckPassed": pip_check_code == 0,
        },
        "determinism": {
            "pythonHashSeed": None,
            "pythonHashRandomization": bool(sys.flags.hash_randomization),
            "timezone": env["TZ"],
            "locale": env["LC_ALL"],
            "pytestPluginAutoloadDisabled": True,
            "pythonNoUserSite": True,
            "pythonDontWriteBytecode": True,
            "scrubbedAmbientVariables": [
                "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONOPTIMIZE",
                "PYTHONCASEOK", "PYTHONEXECUTABLE", "PYTHONHASHSEED",
                "PYTHONHOME", "PYTHONINSPECT", "PYTHONMALLOC", "PYTHONPATH",
                "PYTHONPLATLIBDIR", "PYTHONPYCACHEPREFIX", "PYTHONSAFEPATH",
                "PYTHONSTARTUP", "PYTHONWARNINGS", "LD_*", "DYLD_*",
                "GLIBC_TUNABLES", "GCONV_PATH", "OFARM_*",
            ],
            "allowedOfarmVariables": sorted(ALLOWED_OFARM_ENV),
            "derivedOfarmVariables": ["OFARM_PG_DSN"],
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


_INVENTORY_ENTRY_KEYS = {"nodeid", "sourceModule", "sourcePath"}
_WARNING_KEYS = {"nodeid", "when", "category", "message"}


def _normalised_inventory_entries(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ValueError("review baseline test inventory entries must be non-empty")
    entries: list[dict[str, str]] = []
    seen_nodeids: set[str] = set()
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != _INVENTORY_ENTRY_KEYS:
            raise ValueError("review baseline test inventory entry is malformed")
        if any(not isinstance(entry[key], str) or not entry[key]
               for key in _INVENTORY_ENTRY_KEYS):
            raise ValueError("review baseline test inventory fields must be non-empty strings")
        nodeid = entry["nodeid"]
        source_path = entry["sourcePath"]
        if "\\" in nodeid or "\\" in source_path:
            raise ValueError("review baseline test inventory paths must use POSIX separators")
        parsed_path = PurePosixPath(source_path)
        if parsed_path.is_absolute() or ".." in parsed_path.parts:
            raise ValueError("review baseline source paths must stay repository-relative")
        if nodeid in seen_nodeids:
            raise ValueError(f"duplicate review baseline nodeid {nodeid!r}")
        seen_nodeids.add(nodeid)
        entries.append({key: entry[key] for key in sorted(_INVENTORY_ENTRY_KEYS)})
    return sorted(entries, key=lambda entry: (
        entry["nodeid"], entry["sourceModule"], entry["sourcePath"],
    ))


def _inventory_document(test_root: str, entries: Any) -> dict[str, Any]:
    normalised = _normalised_inventory_entries(entries)
    return {
        "schemaVersion": INVENTORY_SCHEMA,
        "testRoot": test_root,
        "entryCount": len(normalised),
        "entriesSha256": _sha256_bytes(_canonical_bytes(normalised)),
        "entries": normalised,
    }


def _load_test_inventory(config: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / config["paths"]["testInventory"]
    document = _read_json(path)
    if set(document) != {
        "schemaVersion", "testRoot", "entryCount", "entriesSha256", "entries",
    }:
        raise ValueError("review baseline test inventory has unknown or missing fields")
    expected = _inventory_document(config["paths"]["testRoot"], document["entries"])
    if document != expected:
        raise ValueError("review baseline test inventory is stale or non-canonical")
    return document


def _test_inventory_check(
    expected_document: dict[str, Any],
    actual_entries: Any,
) -> dict[str, Any]:
    actual = _normalised_inventory_entries(actual_entries)
    expected = expected_document["entries"]
    expected_keys = {
        (entry["nodeid"], entry["sourceModule"], entry["sourcePath"]): entry
        for entry in expected
    }
    actual_keys = {
        (entry["nodeid"], entry["sourceModule"], entry["sourcePath"]): entry
        for entry in actual
    }
    missing = [expected_keys[key] for key in sorted(expected_keys.keys() - actual_keys.keys())]
    unexpected = [actual_keys[key] for key in sorted(actual_keys.keys() - expected_keys.keys())]
    actual_digest = _sha256_bytes(_canonical_bytes(actual))
    return {
        "matches": not missing and not unexpected,
        "expectedCount": expected_document["entryCount"],
        "actualCount": len(actual),
        "expectedEntriesSha256": expected_document["entriesSha256"],
        "actualEntriesSha256": actual_digest,
        "missing": missing,
        "unexpected": unexpected,
    }


def _normalised_warning_inventory(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("review baseline warning inventory must be a list")
    warnings: list[dict[str, str]] = []
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != _WARNING_KEYS:
            raise ValueError("review baseline warning entry is malformed")
        if any(not isinstance(entry[key], str) for key in _WARNING_KEYS):
            raise ValueError("review baseline warning fields must be strings")
        warnings.append({key: entry[key] for key in sorted(_WARNING_KEYS)})
    return sorted(warnings, key=lambda entry: (
        entry["nodeid"], entry["when"], entry["category"], entry["message"],
    ))


def _warning_policy_check(
    policy: dict[str, Any],
    actual_warnings: Any,
) -> dict[str, Any]:
    if not isinstance(policy, dict) or set(policy) != {"mode", "expected"}:
        raise ValueError("review baseline warning policy is malformed")
    if policy["mode"] != "exact-inventory":
        raise ValueError("review baseline warning policy mode is unsupported")
    expected = _normalised_warning_inventory(policy["expected"])
    actual = _normalised_warning_inventory(actual_warnings)
    return {
        "mode": policy["mode"],
        "matches": actual == expected,
        "expected": expected,
        "actual": actual,
    }


def _empty_results(reason: str) -> dict[str, Any]:
    return {
        "schemaVersion": "ofarm.review-baseline-pytest-results.v2",
        "collection": {"collected": [], "selected": [], "deselected": [],
                       "skippedCollectors": [],
                       "errors": [{"collector": "pytest", "outcome": reason}]},
        "execution": {"outcomes": [], "skipped": [], "unavailable": []},
        "warnings": [],
        "summary": {"collected": 0, "selected": 0, "passed": 0, "failed": 0,
                    "error": 0, "xfailed": 0, "xpassed": 0, "skipped": 0,
                    "deselected": 0, "collectionSkipped": 0,
                    "unavailable": 0, "collectionErrors": 1,
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


def _test_result_is_complete(
    results: dict[str, Any],
    *,
    inventory_matches: bool = True,
    warning_inventory_matches: bool = True,
) -> bool:
    summary = results["summary"]
    return (
        results.get("schemaVersion") == "ofarm.review-baseline-pytest-results.v2"
        and summary["collected"] > 0
        and summary["selected"] == summary["collected"]
        and summary["passed"] == summary["selected"]
        and all(summary[field] == 0 for field in (
            "failed", "error", "xfailed", "xpassed", "skipped", "deselected",
            "collectionSkipped", "unavailable", "collectionErrors",
        ))
        and summary["warnings"] == len(results["warnings"])
        and inventory_matches
        and warning_inventory_matches
        and summary["pytestExitStatus"] == 0
    )


def _git_integrity_reasons(
    start: dict[str, Any],
    end: dict[str, Any] | None = None,
) -> list[str]:
    reasons: list[str] = []
    if start.get("dirty") is not False:
        reasons.append("Git worktree is dirty before execution")
    if end is None:
        return reasons
    if end.get("dirty") is not False:
        reasons.append("Git worktree is dirty after execution")
    if start != end:
        reasons.append("Git worktree state changed during execution")
    return reasons


def run_baseline(output_arg: str) -> int:
    git_start = _git_state()  # must happen before the ignored output directory exists
    output = _controlled_output(Path(output_arg), must_be_empty=True)
    output.mkdir(parents=True, exist_ok=True)
    config = _read_json(CONFIG_PATH)
    inventory_path = ROOT / config["paths"]["testInventory"]
    test_inventory = _load_test_inventory(config)
    inventory_file_digest = _sha256_file(inventory_path)
    env = _sanitized_environment(config)
    started = _utc_now()
    package_command = _isolated_display("conformance.ofarm_pkg_contract_check")
    package_code = _execute(_isolated_python(
        "conformance.ofarm_pkg_contract_check"), env)
    pip_command = _isolated_display("pip", "check")
    pip_code = _execute(_isolated_python("pip", "check"), env)
    environment, preflight_reasons = _preflight(config, env, pip_code)
    preflight_reasons = _git_integrity_reasons(git_start) + preflight_reasons

    results_path = output / "kernel-test-results.json"
    pytest_command = _isolated_display(
        "pytest", config["paths"]["testRoot"], "-q",
        "--assert=plain",
        "--import-mode=importlib",
        "-p", "no:cacheprovider",
        "-p", "conformance.review_baseline_pytest",
        "--review-baseline-results", "kernel-test-results.json",
    )
    actual_pytest_command = _isolated_python(
        "pytest", config["paths"]["testRoot"], "-q",
        "--assert=plain",
        "--import-mode=importlib",
        "-p", "no:cacheprovider",
        "-p", "conformance.review_baseline_pytest",
        "--review-baseline-results", str(results_path),
    )
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

    inventory_check = _test_inventory_check(
        test_inventory, test_results["collection"]["collected"])
    warning_check = _warning_policy_check(
        config["warningPolicy"], test_results["warnings"])

    manifest_command = _isolated_display(
        "kernel.manifest", "--verify-generated")
    if preflight_reasons:
        manifest_code = None
    else:
        manifest_code = _execute(_isolated_python(
            "kernel.manifest", "--verify-generated"), env)

    if preflight_reasons:
        test_store_postgres = {
            "available": False,
            "errorType": "EnvironmentPreflightFailed",
            "version": None,
            "rawVersion": None,
            "systemIdentifier": None,
            "database": None,
        }
    elif not env.get("OFARM_PG_DSN"):
        test_store_postgres = {
            "available": False,
            "errorType": "DerivedTestDsnAbsent",
            "version": None,
            "rawVersion": None,
            "systemIdentifier": None,
            "database": None,
        }
    else:
        test_store_postgres = _postgres_identity(env["OFARM_PG_DSN"])
    environment["postgresql"]["testStore"] = test_store_postgres
    postgres_identity_reasons = _postgres_identity_reasons(
        environment["postgresql"]["admin"], test_store_postgres,
        config["requiredEnvironment"]["testDatabaseName"])
    environment["postgresql"]["sameServer"] = not postgres_identity_reasons

    git_end = _git_state()
    git_integrity_reasons = _git_integrity_reasons(git_start, git_end)

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
            "verify-pinned-test-inventory", ["internal:pinned-test-inventory"],
            0 if inventory_check["matches"] else 1,
            None if inventory_check["matches"] else "test inventory drifted",
        ),
        _step(
            "verify-warning-inventory", ["internal:exact-warning-inventory"],
            0 if warning_check["matches"] else 1,
            None if warning_check["matches"] else "warning inventory drifted",
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
        _step(
            "verify-test-store-postgresql", ["internal:postgresql-server-identity"],
            0 if not postgres_identity_reasons else 1,
            "; ".join(postgres_identity_reasons)
            if postgres_identity_reasons else None,
        ),
        _step(
            "verify-post-run-git-state", ["internal:post-run-git-integrity"],
            0 if not git_integrity_reasons else 1,
            "; ".join(git_integrity_reasons) if git_integrity_reasons else None,
        ),
    ]
    complete = _test_result_is_complete(
        test_results,
        inventory_matches=inventory_check["matches"],
        warning_inventory_matches=warning_check["matches"],
    )
    passed = (
        not preflight_reasons and package_code == pip_code == pytest_code == 0
        and manifest_code == 0 and not postgres_identity_reasons
        and not git_integrity_reasons and complete
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
        "git": {
            "start": git_start,
            "end": git_end,
            "unchanged": git_start == git_end,
        },
        "inputs": {
            "config": {"path": str(CONFIG_PATH.relative_to(ROOT)),
                       "sha256": _sha256_file(CONFIG_PATH)},
            "dependencyLock": {"path": str(dependency_lock.relative_to(ROOT)),
                               "sha256": _sha256_file(dependency_lock)},
            "packageManagerLock": {"path": str(pip_lock.relative_to(ROOT)),
                                   "sha256": _sha256_file(pip_lock)},
            "testInventory": {
                "path": str(inventory_path.relative_to(ROOT)),
                "sha256": inventory_file_digest,
                "entriesSha256": test_inventory["entriesSha256"],
                "entryCount": test_inventory["entryCount"],
            },
            "schema": {"path": str(schema.relative_to(ROOT)),
                       "sha256": _sha256_file(schema)},
        },
        "environment": environment,
        "tests": test_results,
        "testAcceptance": {
            "inventory": inventory_check,
            "warnings": warning_check,
        },
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
        raise ValueError("evidence normalization policy is not the fixed policy")
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
        git = evidence.get("git", {})
        git_reasons = _git_integrity_reasons(
            git.get("start", {}), git.get("end", {}))
        computed_unchanged = git.get("start", {}) == git.get("end", {})
        if git_reasons or git.get("unchanged") != computed_unchanged:
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


def update_test_inventory() -> int:
    config = _read_json(CONFIG_PATH)
    optimization_reasons = _python_optimization_reasons(
        config["requiredEnvironment"]["pythonOptimizationLevel"])
    if optimization_reasons:
        raise ValueError("; ".join(optimization_reasons))
    env = _sanitized_environment(config)
    with tempfile.TemporaryDirectory(prefix="ofarm-review-inventory-") as temporary:
        results_path = Path(temporary) / "kernel-test-results.json"
        command = _isolated_python(
            "pytest", config["paths"]["testRoot"],
            "--collect-only", "-q", "--assert=plain",
            "--import-mode=importlib", "-p", "no:cacheprovider",
            "-p", "conformance.review_baseline_pytest",
            "--review-baseline-results", str(results_path),
        )
        process = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if process.returncode != 0 or not results_path.exists():
            raise ValueError("review baseline inventory collection failed")
        results = _read_json(results_path)
    summary = results.get("summary", {})
    if (results.get("schemaVersion") != "ofarm.review-baseline-pytest-results.v2"
            or summary.get("collected", 0) <= 0
            or summary.get("selected") != summary.get("collected")
            or any(summary.get(field) != 0 for field in (
                "collectionErrors", "collectionSkipped", "deselected",
            ))):
        raise ValueError(
            "review baseline inventory collection was incomplete or ambiguous")
    document = _inventory_document(
        config["paths"]["testRoot"], results["collection"]["collected"])
    path = ROOT / config["paths"]["testInventory"]
    _write_json(path, document)
    print(
        f"wrote {path.relative_to(ROOT)} with {document['entryCount']} pinned tests"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run one complete Kernel baseline")
    run.add_argument("--output-dir", required=True)
    compare = commands.add_parser("compare", help="compare two clean baseline envelopes")
    compare.add_argument("left")
    compare.add_argument("right")
    compare.add_argument("--output", required=True)
    commands.add_parser(
        "update-inventory",
        help="explicitly regenerate the committed Kernel test inventory",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return run_baseline(args.output_dir)
        if args.command == "update-inventory":
            return update_test_inventory()
        return compare_evidence(args.left, args.right, args.output)
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"review baseline ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
