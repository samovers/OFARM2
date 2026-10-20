"""Read-only custody checks for consumed CI transition history.

This module replays existing journals and verifies archived Git objects. It
contains no grant creation, journal append, workflow or live-acceptance path.
Original task-user messages remain independently retrieved human authority.
"""
from __future__ import annotations
import ast
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any


class OperatorError(ValueError):
    """Missing or inconsistent operator evidence refuses continuation."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise OperatorError("expected a full Git commit/tree identity")
    return value


def _hash(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
        raise OperatorError("expected a SHA-256 digest")
    return value


def _positive(value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise OperatorError("identity must be a positive integer")
    return value


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise OperatorError("invalid repository path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in (".", "..", ".git") for part in path.parts) or str(path) != value:
        raise OperatorError("noncanonical repository path")
    return value


def _regular(path: Path) -> bytes:
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise OperatorError("operator record is not a regular file")
            return stream.read()
    except OSError as exc:
        raise OperatorError(f"operator record unavailable: {path.name}") from exc


def _outside(path: Path, roots: tuple[Path, ...]) -> Path:
    # Neither the current policy checkout nor any caller-declared candidate is
    # allowed to carry the operator journal or its independent checkpoint.
    absolute = path.absolute()
    if absolute.is_symlink():
        raise OperatorError("operator storage contains a symbolic link")
    resolved = absolute.resolve()
    for root in (*roots, Path(__file__).resolve().parents[1]):
        if resolved.is_relative_to(root.resolve()):
            raise OperatorError("operator storage must be outside candidate/policy workspaces")
    if not resolved.parent.is_dir():
        raise OperatorError("operator storage directory must already exist")
    return resolved


_COORDINATES = {"rootSha", "rootTree", "closureDigest", "coverageDigest", "baseSha", "consumerPr", "headSha", "mergeSha"}


_ACTION_STATES = {
    "admission": "APPROVED", "source_push": "APPROVED",
    "source_binding": "SOURCE_RESERVED", "publisher_push": "SOURCE_PASSED",
    "publisher_binding": "PUBLISHER_RESERVED",
}


_TERMINAL = {"FAILED", "RETIRED"}


def _artifact(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"artifactId", "digest"}:
        raise OperatorError("artifact requires its exact ID and digest")
    _positive(value["artifactId"])
    _hash(value["digest"])
    return copy.deepcopy(value)


def _run(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or type(value.get("runAttempt")) is not int or value.get("runAttempt") != 1:
        raise OperatorError("only the first run attempt may be bound")
    _positive(value.get("runId"))
    return copy.deepcopy(value)


def _expected_tuple(state: dict[str, Any]) -> dict[str, Any]:
    c = state["coordinates"]
    if not all(state.get(k) for k in ("sourceRun", "publisherRun", "ticket", "receipt")):
        raise OperatorError("journal has no complete sealed tuple")
    return {"grantId": state["grantId"], **{key: c[key] for key in sorted(_COORDINATES)},
            "sourceRunId": state["sourceRun"]["runId"], "sourceRunAttempt": 1,
            "publisherRunId": state["publisherRun"]["runId"], "publisherRunAttempt": 1,
            "ticketArtifactId": state["ticket"]["artifactId"], "ticketDigest": state["ticket"]["digest"],
            "receiptArtifactId": state["receipt"]["artifactId"], "receiptDigest": state["receipt"]["digest"]}


def _apply(state: dict[str, Any], event: str, data: dict[str, Any]) -> None:
    current = state["state"]
    if current in _TERMINAL:
        raise OperatorError("terminal journal cannot be advanced")
    if event == "FAILED":
        if not isinstance(data.get("reason"), str) or not data["reason"].strip():
            raise OperatorError("failure requires a reason")
        state.update(state="FAILED", failure=data)
        return
    if event == "APPROVED":
        if current != "GENESIS":
            raise OperatorError("approval projection may be recorded only once")
        _hash(data.get("grantDigest"))
        refs = data.get("authorityRefs")
        if not isinstance(refs, dict) or set(refs) != {"task", "card", "approval", "packet", "grant"} or any(not isinstance(v, str) or not v for v in refs.values()):
            raise OperatorError("original authority references are required; references do not prove approval")
        state.update(state="APPROVED", approval=data)
        return
    if event == "INTENT":
        action = data.get("action")
        expected = data.get("expected")
        if action not in _ACTION_STATES or current != _ACTION_STATES[action] or state.get("pending"):
            raise OperatorError("public write is out of order or an outcome is unresolved")
        if action in state["writes"] or not isinstance(expected, dict) or not expected:
            raise OperatorError("public write is already consumed or has no exact identity")
        if action == "source_push" and "admission" not in state["writes"]:
            raise OperatorError("source reservation requires reconciled admission")
        if action == "source_binding" and not state.get("sourceRun"):
            raise OperatorError("bind the first source run before its public binding")
        if action == "publisher_binding" and not state.get("publisherRun"):
            raise OperatorError("bind the first publisher run before its public binding")
        if action in ("source_push", "publisher_push"):
            stage = action.split("_")[0]
            ref = expected.get("ref")
            required = f"refs/heads/ofarm-ci-transition/{stage}/{state['grantId']}"
            if ref != required or expected.get("sha") != state["coordinates"]["rootSha"] or expected.get("previous") is not None:
                raise OperatorError("push must target the exact absent activation ref at T")
            state["state"] = "SOURCE_RESERVED" if stage == "source" else "PUBLISHER_RESERVED"
        else:
            _hash(expected.get("bodyDigest"))
        state["pending"] = data
        return
    if event == "RECONCILED":
        pending = state.get("pending")
        identity = data.get("identity")
        if not pending or data.get("action") != pending["action"] or not isinstance(identity, dict):
            raise OperatorError("no matching public intent to reconcile")
        if any(identity.get(k) != v for k, v in pending["expected"].items()):
            raise OperatorError("observed public identity differs from the durable intent")
        action = pending["action"]
        if not action.endswith("push"):
            _positive(identity.get("commentId"))
            if any(record.get("commentId") == identity["commentId"] for record in state["writes"].values()):
                raise OperatorError("public comment identity is already used")
        state["writes"][action] = identity
        state["pending"] = None
        if action == "source_binding":
            state["state"] = "SOURCE_BOUND"
        elif action == "publisher_binding":
            state["state"] = "PUBLISHER_BOUND"
        return
    if state.get("pending"):
        raise OperatorError("unresolved public outcome prevents continuation")
    if event == "RUN_BOUND":
        stage = data.get("stage")
        if stage not in ("source", "publisher") or current != ("SOURCE_RESERVED" if stage == "source" else "PUBLISHER_RESERVED"):
            raise OperatorError("run binding is out of order")
        key = stage + "Run"
        if state.get(key) or stage + "_push" not in state["writes"]:
            raise OperatorError("run slot is consumed or push was not reconciled")
        run = _run(data.get("identity"))
        if stage == "publisher" and run["runId"] == state["sourceRun"]["runId"]:
            raise OperatorError("publisher must be a separate run")
        state[key] = run
    elif event == "SOURCE_PASSED":
        if current != "SOURCE_BOUND":
            raise OperatorError("source success is out of order")
        state.update(state=event, ticket=_artifact(data))
    elif event == "SEALED":
        if current != "PUBLISHER_BOUND":
            raise OperatorError("publisher sealing is out of order")
        state.update(state=event, receipt=_artifact(data))
    elif event == "ACCEPTED":
        if current != "SEALED" or data != _expected_tuple(state):
            raise OperatorError("acceptance differs from the first sealed journal tuple")
        state.update(state=event, consumedTuple=data)
    elif event == "RETIRED":
        if current != "ACCEPTED" or not isinstance(data.get("nativeMerge"), dict):
            raise OperatorError("retirement requires recorded acceptance and native merge")
        merge = data["nativeMerge"]
        _sha(merge.get("mergeCommit"))
        if merge.get("headSha") != state["coordinates"]["headSha"] or merge.get("consumerPr") != state["coordinates"]["consumerPr"]:
            raise OperatorError("native merge differs from the consumed consumer")
        state.update(state=event, nativeMerge=merge)
    else:
        raise OperatorError("unknown journal event")


class ConsumedJournal:
    """Read an existing hash-chained journal under its retained lock."""

    def __init__(self, path: Path, checkpoint_path: Path, expected_genesis: str,
                 *, candidate_roots: tuple[Path, ...] = ()):
        self.path = _outside(Path(path), candidate_roots)
        self.checkpoint_path = _outside(Path(checkpoint_path), candidate_roots)
        if self.path.parent == self.checkpoint_path.parent:
            raise OperatorError("checkpoint must be retained in a separate directory")
        self.expected_genesis = _hash(expected_genesis)
        self._lock = None

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(self.path.name + ".lock")

    def _checkpoint(self, sequence: int, tail: str) -> dict[str, Any]:
        return {"schemaVersion": "ofarm.ci-transition-checkpoint.v1", "genesis": self.expected_genesis,
                "sequence": sequence, "tail": tail}

    def __enter__(self) -> "ConsumedJournal":
        try:
            self._lock = os.open(self.lock_path, os.O_RDONLY | os.O_NOFOLLOW)
            fcntl.flock(self._lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            self._load()
        except (OSError, OperatorError, ValueError, KeyError, TypeError) as exc:
            self.__exit__(None, None, None)
            raise OperatorError("journal unavailable, locked, or inconsistent") from exc
        return self

    def __exit__(self, *_: Any) -> None:
        if self._lock is not None:
            os.close(self._lock)
            self._lock = None

    def _load(self) -> None:
        raw = _regular(self.path)
        if not raw.endswith(b"\n") or len(raw) > 8_000_000:
            raise OperatorError("journal has a torn or oversized append")
        records = []
        previous = None
        for sequence, line in enumerate(raw.splitlines()):
            record = json.loads(line)
            if _canonical(record) != line or set(record) != {"sequence", "previous", "event", "data", "digest"}:
                raise OperatorError("journal record is not canonical")
            digest = record["digest"]
            body = {k: v for k, v in record.items() if k != "digest"}
            if type(record["sequence"]) is not int or record["sequence"] != sequence or record["previous"] != previous or _digest(_canonical(body)) != digest:
                raise OperatorError("journal hash chain is broken")
            if sequence == 0:
                if digest != self.expected_genesis or record["event"] != "GENESIS":
                    raise OperatorError("journal genesis differs from the external pin")
                data = record["data"]
                self._state = {"state": "GENESIS", "grantId": data["grantId"],
                               "coordinates": data["coordinates"], "writes": {}, "pending": None}
            else:
                _apply(self._state, record["event"], record["data"])
            records.append(record)
            previous = digest
        if not records or _regular(self.checkpoint_path) != _canonical(self._checkpoint(len(records) - 1, previous)) + b"\n":
            raise OperatorError("independent checkpoint is missing, stale, or rolled back")
        self._records = records

    def snapshot(self) -> dict[str, Any]:
        self._ready()
        self._load()  # Never return a stale in-memory authority after disk drift.
        return copy.deepcopy({**self._state, "records": self._records,
                              "genesisDigest": self.expected_genesis})

    def _ready(self) -> None:
        if self._lock is None:
            raise OperatorError("historical journal must be locked")


def _git(repo: Path, *arguments: str) -> bytes:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_NO_REPLACE_OBJECTS="1", GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
                             "-c", "protocol.file.allow=always", "-C", str(repo), *arguments],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise OperatorError("Git verification failed: " + result.stderr.decode("utf-8", "replace")[:500])
    return result.stdout


def _tree(repo: Path, commit: str) -> dict[str, dict[str, Any]]:
    _sha(commit)
    if _git(repo, "rev-parse", commit + "^{commit}").decode().strip() != commit:
        raise OperatorError("root is not the exact commit")
    files = {}
    for entry in _git(repo, "ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split(" ")
        path = _path(name.decode("utf-8"))
        # The full tree can describe non-executable symlinks, but declared
        # policy dependencies below must always resolve to regular blobs.
        files[path] = {"mode": mode, "kind": kind, "object": oid}
    return files


def _blob(repo: Path, tree: dict[str, dict[str, Any]], path: str) -> bytes:
    _path(path)
    entry = tree.get(path)
    if not entry or entry["kind"] != "blob" or entry["mode"] not in ("100644", "100755"):
        raise OperatorError(f"policy dependency is not a regular Git blob: {path}")
    return _git(repo, "cat-file", "blob", entry["object"])


def _static_imports(path: str, payload: bytes, tree: dict[str, Any]) -> tuple[set[str], set[str], bool]:
    try:
        module = ast.parse(payload, filename=path)
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise OperatorError(f"unparseable policy Python dependency: {path}") from exc
    local: set[str] = set()
    external: set[str] = set()
    runtime_import = False
    parent = PurePosixPath(path).parent

    def resolve(parts: list[str], relative: bool = False) -> None:
        if not parts:
            return
        stem = "/".join(parts)
        bases = [parent] if relative else [PurePosixPath("."), parent]
        found = False
        for base in bases:
            for size in range(len(parts), 0, -1):
                candidate_stem = str(base / "/".join(parts[:size]))
                for candidate in (candidate_stem + ".py", candidate_stem + "/__init__.py"):
                    if candidate in tree:
                        local.add(candidate)
                        found = True
                        # Include package initialization along the whole route.
                        ancestors = PurePosixPath(candidate).parents
                        local.update(str(p / "__init__.py") for p in ancestors if str(p / "__init__.py") in tree)
                        break
        if not found:
            external.add(stem.split("/")[0])

    for node in ast.walk(module):
        if isinstance(node, ast.Call):
            function = node.func
            name = function.id if isinstance(function, ast.Name) else function.attr if isinstance(function, ast.Attribute) else ""
            if name in ("__import__", "import_module", "spec_from_file_location", "run_path", "run_module"):
                literal = (node.args[0].value if node.args and isinstance(node.args[0], ast.Constant)
                           and isinstance(node.args[0].value, str) else None)
                if name in ("__import__", "import_module") and literal in sys.stdlib_module_names:
                    external.add(literal)
                else:
                    runtime_import = True
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Literal repository inputs are verifiable edges even when a script
            # opens them as data or invokes them in a subprocess.
            for candidate in (node.value, str(parent / node.value)):
                if candidate in tree:
                    local.add(candidate)
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolve(alias.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = parent
                for _ in range(node.level - 1):
                    base = base.parent
                prefix = [] if str(base) == "." else list(base.parts)
                prefix += node.module.split(".") if node.module else []
                resolve(prefix)
                for alias in node.names:
                    if alias.name != "*":
                        resolve([*prefix, alias.name])
            else:
                prefix = node.module.split(".") if node.module else []
                resolve(prefix)
                for alias in node.names:
                    if alias.name != "*":
                        resolve([*prefix, alias.name])
    local.discard(path)
    external = {name for name in external if not any(
        dependency.startswith(name + "/") or PurePosixPath(dependency).stem == name
        for dependency in local
    )}
    return local, external, runtime_import


_INPUT_ROLES = {"configuration", "pins", "generatedInputs", "generatedWorkflows", "tests"}


_NATIVE_CURRENTNESS = "deployment/postgresql/ofarm_ed25519/native_evidence_verification_currentness.json"


_PRESERVED = {
    "conformance/review_baseline_config.json", "requirements-review-baseline.lock", "requirements-review-pip.lock",
    "deployment/postgresql/ofarm_ed25519/native_evidence_receipt.json",
    "deployment/postgresql/ofarm_ed25519/native_release_identity.json", _NATIVE_CURRENTNESS,
}


_ALLOWED_EXISTING_CHANGES = {
    "conformance/review_baseline_test_inventory.json",
    "docs/development/DELIVERY_PROTOCOL.md",
    "docs/rfcs/OFARM2_CI_Policy_Transition_RFC_v0_1.md",
    "docs/rfcs/OFARM2_CI_Policy_Transition_Installation_Runbook_v0_1.md",
    "docs/rfcs/OFARM2_CI_Policy_Transition_Guarantee_Matrix_v0_1.md",
}


_ROOT_MANIFEST = "conformance/ci_policy_transition_root.json"


def _reconstruct_policy_closure(repo: Path, T: str, B: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct a recorded closure from old Git objects without executing them.

    ``spec`` is the root manifest's committed ``closure`` subobject. Explicit
    dependencies declare runtime-loaded data/modules; static repository imports
    are independently added. This comparison verifies historical bytes, never live acceptance.
    """
    repo = Path(repo)
    current, base = _tree(repo, T), _tree(repo, B)
    if set(spec) != {"entrypoints", "inputs", "dependencies", "allowedChangedPaths"} or not isinstance(spec["inputs"], dict) or set(spec["inputs"]) != _INPUT_ROLES:
        raise OperatorError("closure declarations have an unknown or missing field")
    groups = {"entrypoints": spec["entrypoints"], **spec["inputs"]}
    for role, paths in groups.items():
        if not isinstance(paths, list) or not paths or len(paths) != len(set(paths)):
            raise OperatorError(f"closure role is empty or duplicated: {role}")
        for path in paths:
            _path(path)
    if not isinstance(spec["dependencies"], dict):
        raise OperatorError("explicit dependency map is required")
    for owner, dependencies in spec["dependencies"].items():
        _path(owner)
        if not isinstance(dependencies, list) or len(dependencies) != len(set(dependencies)):
            raise OperatorError("explicit dependencies must be unique paths")
        for path in dependencies:
            _path(path)
    allowed = spec["allowedChangedPaths"]
    if not isinstance(allowed, list) or len(allowed) != len(set(allowed)):
        raise OperatorError("changed-path declaration is invalid")
    for path in allowed:
        _path(path)
    # All pre-existing Python and workflow implementations, config/lock/schema
    # files, and native identity/currentness inputs are outside this amendment.
    preserved = _PRESERVED & base.keys()
    preserved |= {p for p in base if p.endswith((".py", ".lock")) or p.startswith(".github/workflows/") or ("schema" in p and p.endswith(".json"))}
    if set(allowed) & preserved:
        raise OperatorError("changed-path declaration attempts to widen preserved policy")
    if set(allowed) - _ALLOWED_EXISTING_CHANGES:
        raise OperatorError("existing-path amendments exceed the closed documentation/inventory set")
    for path in sorted(preserved):
        if current.get(path) != base[path]:
            raise OperatorError(f"ordinary/native/source policy was changed: {path}")
    changed = []
    for path in sorted(current.keys() | base.keys()):
        if current.get(path) != base.get(path):
            if path in base and path not in allowed:
                raise OperatorError(f"undeclared existing-path change: {path}")
            versions = {}
            for label, tree in (("before", base), ("after", current)):
                entry = tree.get(path)
                versions[label] = entry
                if entry and entry["kind"] == "blob":
                    raw = _git(repo, "cat-file", "blob", entry["object"])
                    versions[label] = {**entry, "sha256": _digest(raw), "size": len(raw)}
            changed.append({"path": path, **versions})
    message = _git(repo, "show", "-s", "--format=%B", T).decode("utf-8")
    if re.search(r"\[(?:skip ci|ci skip|no ci|skip actions|actions skip)\]|(?im:^skip-checks\s*:\s*true\s*$)", message, re.IGNORECASE):
        raise OperatorError("frozen root commit suppresses push CI")
    pending = set().union(*map(set, groups.values()))
    visited: set[str] = set()
    edges: dict[str, list[str]] = {}
    external: dict[str, list[str]] = {}
    runtime_dependencies: dict[str, list[str]] = {}
    records = {}
    while pending:
        path = min(pending)
        pending.remove(path)
        if path in visited:
            continue
        visited.add(path)
        payload = _blob(repo, current, path)
        local, imports, runtime_import = _static_imports(path, payload, current) if path.endswith(".py") else (set(), set(), False)
        if runtime_import:
            if not spec["dependencies"].get(path):
                raise OperatorError(f"runtime import requires declared dependency targets: {path}")
            runtime_dependencies[path] = sorted(spec["dependencies"][path])
        local |= set(spec["dependencies"].get(path, []))
        edges[path] = sorted(local)
        if imports:
            external[path] = sorted(imports)
        pending |= local - visited
        records[path] = {**current[path], "size": len(payload), "sha256": _digest(payload)}
    if _ROOT_MANIFEST in current:
        manifest = json.loads(_blob(repo, current, _ROOT_MANIFEST))
        if manifest.get("closure") != spec or manifest.get("baseSha") != B or _ROOT_MANIFEST not in visited:
            raise OperatorError("closure declarations differ from the committed root manifest")
    if set(spec["dependencies"]) - visited:
        raise OperatorError("explicit dependency owner is outside the reachable closure")
    for path in current.keys() - base.keys():
        if path.endswith((".py", ".yml", ".yaml", ".json", ".lock")) and path not in visited:
            raise OperatorError(f"new executable/config/test input missing from closure: {path}")
    native = None
    if _NATIVE_CURRENTNESS in base:
        native = json.loads(_blob(repo, base, _NATIVE_CURRENTNESS))
        authority = native.get("verificationAuthorityInput", {}).get("files", [])
        if len(authority) != 6:
            raise OperatorError("native currentness does not retain its six authority files")
        for item in authority:
            path = _path(item["path"])
            raw = _blob(repo, current, path)
            if current.get(path) != base.get(path) or _digest(raw) != item["sha256"] or len(raw) != item["size"]:
                raise OperatorError("native authority/currentness differs from trusted B")
    return {"schemaVersion": "ofarm.ci-transition-policy-closure.v1", "rootSha": T,
            "rootTree": _git(repo, "rev-parse", T + "^{tree}").decode().strip(), "baseSha": B,
            "fullTreeDigest": _digest(_canonical(current)), "spec": copy.deepcopy(spec),
            "files": records, "dependencies": edges, "externalImports": external,
            "runtimeDependencies": runtime_dependencies,
            "changes": changed, "preservedFiles": sorted(preserved), "nativeCurrentness": native}


def policy_closure_digest(closure: dict[str, Any]) -> str:
    return _digest(_canonical(closure))


def _verify_archived_policy_closure(repo: Path, closure: dict[str, Any], expected_T: str, expected_B: str,
                          expected_digest: str, *, expected_tree: str | None = None) -> dict[str, Any]:
    """Reconstruct old Git objects using the independently consumed tuple."""
    _sha(expected_T)
    _sha(expected_B)
    _hash(expected_digest)
    if closure.get("rootSha") != expected_T or closure.get("baseSha") != expected_B or policy_closure_digest(closure) != expected_digest:
        raise OperatorError("closure differs from externally selected root/base/digest")
    if expected_tree is not None and closure.get("rootTree") != _sha(expected_tree):
        raise OperatorError("closure tree differs from the external pin")
    if _reconstruct_policy_closure(Path(repo), expected_T, expected_B, closure["spec"]) != closure:
        raise OperatorError("declared dependency closure differs from exact Git objects")
    return {"purpose": "policy-integrity", "rootSha": expected_T, "rootTree": closure["rootTree"],
            "closureDigest": expected_digest, "humanAuthorityVerified": False}


@contextmanager
def _verified_archive_repository(archive_directory: Path, manifest: dict[str, Any]):
    if (set(manifest) != {"schemaVersion", "purpose", "bundle", "bundleDigest", "roots"}
            or manifest.get("schemaVersion") != "ofarm.ci-transition-root-archive.v1"
            or manifest.get("purpose") != "audit-consumed"
            or manifest.get("bundle") != "policy-roots.bundle"
            or not isinstance(manifest.get("roots"), list) or not manifest["roots"]):
        raise OperatorError("unsupported historical root archive")
    bundle = Path(archive_directory) / "policy-roots.bundle"
    if _digest(_regular(bundle)) != manifest.get("bundleDigest"):
        raise OperatorError("historical root bundle digest differs")
    with tempfile.TemporaryDirectory(prefix="ofarm-root-verify-") as name:
        empty = Path(name)
        _git(empty, "init", "--bare", "--quiet")
        _git(empty, "bundle", "verify", str(bundle.resolve()))
        _git(empty, "fetch", "--quiet", str(bundle.resolve()), "refs/heads/*:refs/heads/*")
        for root in manifest["roots"]:
            if not isinstance(root, dict) or set(root) != {"rootSha", "rootTree", "baseSha"}:
                raise OperatorError("historical archive root is not exact")
            if _git(empty, "rev-parse", _sha(root["rootSha"]) + "^{tree}").decode().strip() != _sha(root["rootTree"]):
                raise OperatorError("archived root has a different tree")
            _git(empty, "cat-file", "-e", _sha(root["baseSha"]) + "^{commit}")
        yield empty


def verify_archived_roots(archive_directory: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    with _verified_archive_repository(archive_directory, manifest):
        pass
    return {"purpose": "audit-consumed", "archiveIntegrity": True,
            "liveAcceptanceAuthority": False, "providerFacts": "unavailable-offline"}


def verify_archived_closure(archive_directory: Path, manifest: dict[str, Any],
                            closure: dict[str, Any], expected_tuple: dict[str, Any]) -> dict[str, Any]:
    """Verify archived policy against the separately consumed journal tuple."""
    selected = {key: expected_tuple[key] for key in ("rootSha", "rootTree", "baseSha")}
    if selected not in manifest.get("roots", []):
        raise OperatorError("consumed root is absent from the historical archive")
    with _verified_archive_repository(archive_directory, manifest) as empty:
        _verify_archived_policy_closure(empty, closure, expected_tuple["rootSha"], expected_tuple["baseSha"],
                              expected_tuple["closureDigest"], expected_tree=expected_tuple["rootTree"])
    return {"purpose": "audit-consumed", "archiveIntegrity": True,
            "closureIntegrity": True, "liveAcceptanceAuthority": False,
            "providerFacts": "unavailable-offline"}
