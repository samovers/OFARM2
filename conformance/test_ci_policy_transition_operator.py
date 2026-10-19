"""Historical closure controls; fixtures never execute archived policy."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from conformance import ci_policy_transition_operator as operator


def _write_root_archive(repo, roots, archive):
    """Test-only fixture authoring; the production verifier only reads bundles."""
    with tempfile.TemporaryDirectory(prefix="fictional-archive-author-") as name:
        staging = Path(name)
        operator._git(staging, "init", "--bare", "--quiet")
        for index, root in enumerate(roots):
            for key, label in (("rootSha", "root"), ("baseSha", "base")):
                operator._git(staging, "fetch", "--quiet", "--no-tags", str(repo), root[key])
                operator._git(staging, "update-ref", f"refs/heads/archive-{index}-{label}", root[key])
        operator._git(staging, "bundle", "create", str(archive / "policy-roots.bundle"), "--all")
    manifest = {"schemaVersion": "ofarm.ci-transition-root-archive.v1", "purpose": "audit-consumed",
        "bundle": "policy-roots.bundle", "bundleDigest": operator._digest((archive / "policy-roots.bundle").read_bytes()),
        "roots": copy.deepcopy(roots)}
    (archive / "policy-roots.json").write_text(json.dumps(manifest))
    return manifest


class TransitionPolicyClosureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fictional-policy-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repository"
        self.repo.mkdir()
        self.git("init", "--quiet")
        self.git("config", "user.name", "Fictional Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("ordinary.py", "VALUE = 1\n")
        self.write("config.json", "{}\n")
        self.write("pins.lock", "fictional-pin\n")
        self.write(".github/workflows/ordinary.yml", "name: ordinary\n")
        self.write("conformance/review_baseline_test_inventory.json", "[]\n")
        self.base = self.commit("Fictional trusted base")
        self.write("policy.py", "import ordinary\nfrom helper import VALUE\n")
        self.write("helper.py", "VALUE = 2\n")
        self.write("test_policy.py", "import policy\n")
        self.write("generated.yml", "name: transition\n")
        self.spec = {"entrypoints": ["policy.py"], "inputs": {"configuration": ["config.json"],
                     "pins": ["pins.lock"], "generatedInputs": [".github/workflows/ordinary.yml"],
                     "generatedWorkflows": ["generated.yml"], "tests": ["test_policy.py"]},
                     "dependencies": {}, "allowedChangedPaths": ["conformance/review_baseline_test_inventory.json"]}
        self.head = self.commit("Fictional complete policy")

    def git(self, *args):
        return operator._git(self.repo, *args).decode().strip()

    def write(self, path, value):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)

    def commit(self, message):
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", message)
        return self.git("rev-parse", "HEAD")

    def closure(self):
        return operator._reconstruct_policy_closure(self.repo, self.head, self.base, self.spec)

    def test_closure_covers_static_imports_inputs_tests_and_exact_tree(self):
        closure = self.closure()
        self.assertIn("helper.py", closure["files"])
        self.assertIn("ordinary.py", closure["dependencies"]["policy.py"])
        self.assertEqual(closure["rootTree"], self.git("rev-parse", "HEAD^{tree}"))
        result = operator._verify_archived_policy_closure(self.repo, closure, self.head, self.base,
                                               operator.policy_closure_digest(closure), expected_tree=closure["rootTree"])
        self.assertEqual(result["purpose"], "policy-integrity")
        self.assertFalse(result["humanAuthorityVerified"])
        self.assertNotIn("rootSha", self.spec)

    def test_modified_closure_cannot_hide_a_changed_dependency(self):
        closure = self.closure()
        closure["files"]["helper.py"]["sha256"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(operator.OperatorError, "differs from exact Git objects"):
            operator._verify_archived_policy_closure(self.repo, closure, self.head, self.base,
                                                    operator.policy_closure_digest(closure))

    def test_receipt_selected_root_base_digest_or_tree_is_rejected(self):
        closure = self.closure()
        arguments = (self.repo, closure, self.head, self.base, operator.policy_closure_digest(closure))
        for index, wrong in ((2, self.base), (3, self.head), (4, "sha256:" + "0" * 64)):
            changed = list(arguments)
            changed[index] = wrong
            with self.subTest(index=index), self.assertRaisesRegex(operator.OperatorError, "externally selected"):
                operator._verify_archived_policy_closure(*changed)
        with self.assertRaisesRegex(operator.OperatorError, "external pin"):
            operator._verify_archived_policy_closure(*arguments, expected_tree="0" * 40)

    def test_preserved_ordinary_source_cannot_be_allowlisted_for_changes(self):
        self.write("ordinary.py", "VALUE = 99\n")
        self.head = self.commit("Fictional unauthorized source change")
        with self.assertRaisesRegex(operator.OperatorError, "ordinary/native/source"):
            self.closure()
        self.spec["allowedChangedPaths"].append("ordinary.py")
        with self.assertRaisesRegex(operator.OperatorError, "widen preserved"):
            self.closure()

    def test_undeclared_new_module_or_config_is_not_hidden_by_full_tree_digest(self):
        self.write("hidden.py", "VALUE = 99\n")
        self.head = self.commit("Fictional hidden input")
        with self.assertRaisesRegex(operator.OperatorError, "missing from closure"):
            self.closure()
        self.spec["dependencies"]["policy.py"] = ["hidden.py"]
        self.assertIn("hidden.py", self.closure()["files"])

    def test_runtime_loaded_module_must_have_an_explicit_dependency_edge(self):
        self.write("policy.py", "import importlib\nmodule = importlib.import_module('helper')\n")
        self.head = self.commit("Fictional runtime import")
        with self.assertRaisesRegex(operator.OperatorError, "runtime import requires declared"):
            self.closure()
        self.spec["dependencies"]["policy.py"] = ["helper.py", "ordinary.py"]
        closure = self.closure()
        self.assertEqual(closure["runtimeDependencies"]["policy.py"], ["helper.py", "ordinary.py"])

    def test_closure_must_match_the_committed_manifest_declarations(self):
        path = "conformance/ci_policy_transition_root.json"
        self.spec["inputs"]["configuration"].append(path)
        self.write(path, json.dumps({"baseSha": self.base, "closure": self.spec}))
        self.head = self.commit("Fictional declared root")
        self.assertIn(path, self.closure()["files"])
        different = copy.deepcopy(self.spec)
        different["dependencies"]["policy.py"] = ["ordinary.py"]
        with self.assertRaisesRegex(operator.OperatorError, "committed root manifest"):
            operator._reconstruct_policy_closure(self.repo, self.head, self.base, different)

    def test_native_currentness_retains_exact_six_ordinary_authority_files(self):
        files = []
        for index in range(6):
            path = f"native/authority_{index}.py"
            payload = f"FICTIONAL_VALUE = {index}\n"
            self.write(path, payload)
            files.append({"path": path, "sha256": operator._digest(payload.encode()), "size": len(payload)})
        path = operator._NATIVE_CURRENTNESS
        self.write(path, json.dumps({"verificationAuthorityInput": {"files": files}}))
        self.base = self.head = self.commit("Fictional native authority baseline")
        closure = self.closure()
        self.assertEqual(closure["nativeCurrentness"]["verificationAuthorityInput"]["files"], files)
        # A record that no longer authenticates its own preserved source must
        # refuse even when both T and B contain identical stale claims.
        files[0]["sha256"] = "sha256:" + "0" * 64
        self.write(path, json.dumps({"verificationAuthorityInput": {"files": files}}))
        self.base = self.head = self.commit("Fictional stale native authority baseline")
        with self.assertRaisesRegex(operator.OperatorError, "native authority/currentness"):
            self.closure()

    def test_missing_dependency_symlink_unknown_declaration_and_skip_ci_refuse(self):
        with self.subTest(case="missing"):
            self.spec["dependencies"]["policy.py"] = ["missing.py"]
            with self.assertRaisesRegex(operator.OperatorError, "not a regular"):
                self.closure()
        self.spec["dependencies"] = {}
        self.write("policy-link", "fixture")
        (self.repo / "policy-link").unlink()
        (self.repo / "policy-link").symlink_to("helper.py")
        self.head = self.commit("Fictional link")
        self.spec["dependencies"]["policy.py"] = ["policy-link"]
        with self.assertRaisesRegex(operator.OperatorError, "not a regular"):
            self.closure()
        self.spec["dependencies"] = {}
        self.spec["unexpected"] = True
        with self.assertRaisesRegex(operator.OperatorError, "unknown or missing"):
            self.closure()
        self.spec.pop("unexpected")
        self.write("conformance/review_baseline_test_inventory.json", "[1]\n")
        self.head = self.commit("Fictional policy [skip ci]")
        with self.assertRaisesRegex(operator.OperatorError, "suppresses push CI"):
            self.closure()

    def test_exact_root_bundle_verifies_in_empty_repository_and_stays_historical(self):
        archive = self.root / "archive"
        archive.mkdir()
        roots = [{"rootSha": self.head, "rootTree": self.git("rev-parse", "HEAD^{tree}"), "baseSha": self.base}]
        manifest = _write_root_archive(self.repo, roots, archive)
        result = operator.verify_archived_roots(archive, manifest)
        closure = self.closure()
        consumed = {**roots[0], "closureDigest": operator.policy_closure_digest(closure)}
        self.assertTrue(operator.verify_archived_closure(archive, manifest, closure, consumed)["closureIntegrity"])
        with self.assertRaisesRegex(operator.OperatorError, "externally selected"):
            operator.verify_archived_closure(archive, manifest, closure, {**consumed, "closureDigest": "sha256:" + "0" * 64})
        self.assertTrue(result["archiveIntegrity"])
        self.assertFalse(result["liveAcceptanceAuthority"])
        self.assertEqual(result["providerFacts"], "unavailable-offline")
        self.assertEqual(json.loads((archive / "policy-roots.json").read_text()), manifest)
        with (archive / "policy-roots.bundle").open("ab") as stream:
            stream.write(b"corrupt")
        with self.assertRaisesRegex(operator.OperatorError, "digest differs"):
            operator.verify_archived_roots(archive, manifest)
