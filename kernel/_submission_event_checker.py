"""Qualify the explicitly adopted offline checker before running its exact source."""
from __future__ import annotations

import builtins
import json
from hashlib import sha256
from importlib.metadata import distribution
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType

from .runtime_bundle import RuntimeBundleError, strict_json_document


_REPO = Path(__file__).resolve().parents[1]
_PACKAGE_PATH = "contracts/drafts_reference/event_ingress_classification_proof/"
_PACKAGE = _REPO / _PACKAGE_PATH
_MERGE = "2f3187f7b33770dfde677477e79cb8202843edb5"
# SHA-256 of the compact JSON array of sorted (destination, source, raw SHA-256)
# triples for the 17 adopted files. Check it before following any manifest path.
_MEMBER_INDEX_SHA256 = "786a345d0715a35cedd6fd7eac4bf154e5310d320cdf968edec7578cdd992969"
_UNAVAILABLE = "accepted Event Ingress checker unavailable"


def _qualified_package(contract_sha256: str) -> dict[str, bytes]:
    """Verify the selected non-default package and local dependencies before import."""
    try:
        manifest, _ = strict_json_document((_REPO / "contracts/CONTRACTS_MANIFEST.json").read_bytes(), "manifest")
        members = []
        for entry in manifest["entries"]:
            destination = entry["packagePath"]
            if destination.startswith(_PACKAGE_PATH):
                if (
                    entry["sourceRepoCommit"] != _MERGE or entry["status"] != "EXTRACTED_VERBATIM"
                    or not entry["currentnessNote"].startswith("DRAFT_NON_DEFAULT")
                ):
                    raise ValueError("unqualified extraction")
                members.append((destination, entry["sourcePath"], entry["sha256"]))
        index = json.dumps(sorted(members), separators=(",", ":")).encode("ascii")
        if sha256(index).hexdigest() != _MEMBER_INDEX_SHA256:
            raise ValueError("changed extraction membership or provenance")

        contents = {}
        for destination, _, expected in members:
            name = destination.removeprefix(_PACKAGE_PATH)
            raw = (_PACKAGE / name).read_bytes()
            if sha256(raw).hexdigest() != expected:
                raise ValueError("changed extracted file")
            contents[name] = raw
        if sha256(contents["contract.json"]).hexdigest() != contract_sha256:
            raise ValueError("different independently selected contract")

        dependencies = json.loads(contents["dependency-manifest.json"])
        for requirement in dependencies["requirements"]:
            name, version = requirement.split("==")
            installed = distribution(name)
            spec = find_spec(name)
            location = Path(installed.locate_file(name)).resolve()
            if installed.version != version or spec is None or spec.origin is None or (
                Path(spec.origin).resolve() != location / "__init__.py"
            ):
                raise ValueError("unqualified installed dependency")
            if name == "rfc8785":
                for filename, expected in dependencies["requiredRfc8785Files"].items():
                    if sha256((location / filename).read_bytes()).hexdigest() != expected:
                        raise ValueError("different RFC 8785 implementation")
    except (ImportError, OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeBundleError, RecursionError) as exc:
        raise RuntimeError(_UNAVAILABLE) from exc
    return contents


def _run_checker(contents: dict[str, bytes], *inputs: bytes, **selectors: object) -> dict:
    # The canonical checker imports its adjacent helper by an unqualified name.
    # Resolve that one import privately using verified source bytes. Other threads'
    # import paths and module caches are independent of this checker.
    helper = ModuleType("report_contract")
    helper.__file__ = str(_PACKAGE / "report_contract.py")
    exec(compile(contents["report_contract.py"], helper.__file__, "exec"), vars(helper))

    def checker_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "report_contract" and level == 0:
            return helper
        return builtins.__import__(name, globals, locals, fromlist, level)

    checker = ModuleType("_ofarm_event_ingress_checker")
    checker.__file__ = str(_PACKAGE / "verify_event_proof.py")
    checker.__dict__["__builtins__"] = {**vars(builtins), "__import__": checker_import}
    exec(compile(contents["verify_event_proof.py"], checker.__file__, "exec"), vars(checker))
    return checker.verify(*inputs, **selectors, package_root=_PACKAGE, source_root=_PACKAGE)
