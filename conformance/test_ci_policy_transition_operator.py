"""Fictional, local controls for transition journal and frozen policy custody."""
from __future__ import annotations

import copy
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from conformance import ci_policy_transition_operator as operator


def _competing_writer(path, checkpoint, genesis, output):
    try:
        with operator.TransitionJournal(Path(path), Path(checkpoint), genesis):
            output.put("unexpected writer")
    except operator.OperatorError:
        output.put("refused")


def _coordinates():
    return {"rootSha": "1" * 40, "rootTree": "2" * 40, "closureDigest": "sha256:" + "3" * 64, "coverageDigest": "sha256:" + "8" * 64,
            "baseSha": "4" * 40, "consumerPr": 413, "headSha": "5" * 40, "mergeSha": "6" * 40}


def _refs():
    return {key: "fictional-" + key for key in ("task", "card", "approval", "packet", "grant")}


class TransitionOperatorJournalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fictional-transition-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "journal").mkdir()
        (self.root / "independent").mkdir()
        self.path = self.root / "journal" / "grant.jsonl"
        self.checkpoint = self.root / "independent" / "checkpoint.json"
        self.genesis = operator.TransitionJournal.create(self.path, self.checkpoint, "fictional-grant", _coordinates())

    def journal(self):
        return operator.TransitionJournal(self.path, self.checkpoint, self.genesis)

    def approve(self, journal):
        journal.approve("sha256:" + "7" * 64, _refs())

    def admission(self, journal):
        expected = {"bodyDigest": "sha256:" + "8" * 64}
        journal.intent("admission", expected)
        journal.reconcile("admission", [{**expected, "commentId": 101}])

    def push(self, journal, stage):
        expected = {"ref": f"refs/heads/ofarm-ci-transition/{stage}/fictional-grant", "sha": "1" * 40, "previous": None}
        journal.intent(stage + "_push", expected)
        journal.reconcile(stage + "_push", [expected])

    def binding(self, journal, stage):
        expected = {"bodyDigest": "sha256:" + ("a" if stage == "source" else "b") * 64}
        journal.intent(stage + "_binding", expected)
        journal.reconcile(stage + "_binding", [{**expected, "commentId": 102 if stage == "source" else 103}])

    def sealed(self, journal):
        self.approve(journal)
        self.admission(journal)
        self.push(journal, "source")
        journal.bind_run("source", {"runId": 201, "runAttempt": 1})
        self.binding(journal, "source")
        journal.source_passed({"artifactId": 301, "digest": "sha256:" + "c" * 64})
        self.push(journal, "publisher")
        journal.bind_run("publisher", {"runId": 202, "runAttempt": 1})
        self.binding(journal, "publisher")
        journal.seal({"artifactId": 302, "digest": "sha256:" + "d" * 64})
        return {"grantId": "fictional-grant", **_coordinates(), "sourceRunId": 201,
                "sourceRunAttempt": 1, "publisherRunId": 202, "publisherRunAttempt": 1,
                "ticketArtifactId": 301, "ticketDigest": "sha256:" + "c" * 64,
                "receiptArtifactId": 302, "receiptDigest": "sha256:" + "d" * 64}

    def before_action(self, journal, action):
        self.approve(journal)
        if action != "admission":
            self.admission(journal)
        if action in ("source_binding", "publisher_push", "publisher_binding"):
            self.push(journal, "source")
            journal.bind_run("source", {"runId": 201, "runAttempt": 1})
        if action in ("publisher_push", "publisher_binding"):
            self.binding(journal, "source")
            journal.source_passed({"artifactId": 301, "digest": "sha256:" + "c" * 64})
        if action == "publisher_binding":
            self.push(journal, "publisher")
            journal.bind_run("publisher", {"runId": 202, "runAttempt": 1})
        if action.endswith("push"):
            return {"ref": f"refs/heads/ofarm-ci-transition/{action.split('_')[0]}/fictional-grant",
                    "sha": "1" * 40, "previous": None}
        return {"bodyDigest": "sha256:" + "f" * 64}

    def test_complete_chain_consumes_once_and_only_same_tuple_is_inspection(self):
        genesis_bytes = self.path.read_bytes().splitlines()[0]
        with self.journal() as journal:
            accepted = self.sealed(journal)
            self.assertTrue(journal.accept(accepted)["newlyAccepted"])
            self.assertEqual(journal.accept(accepted)["purpose"], "inspect-consumed")
            with self.assertRaisesRegex(operator.OperatorError, "different tuple"):
                journal.accept({**accepted, "sourceRunId": 999})
            journal.retire({"consumerPr": 413, "headSha": "5" * 40, "mergeCommit": "e" * 40})
            self.assertEqual(journal.accept(accepted)["purpose"], "inspect-consumed")
            with self.assertRaises(operator.OperatorError):
                journal.intent("source_push", {})
        with self.journal() as journal:
            self.assertEqual(journal.snapshot()["state"], "RETIRED")
            self.assertEqual(journal.snapshot()["consumedTuple"], accepted)
        self.assertEqual(self.path.read_bytes().splitlines()[0], genesis_bytes)

    def test_genesis_cannot_embed_final_grant_or_authority(self):
        for extra in ("grantDigest", "approval", "authorityRefs", "packetDigest"):
            with self.subTest(extra=extra), self.assertRaisesRegex(operator.OperatorError, "technical coordinates"):
                operator.TransitionJournal.create(self.root / "journal" / "other", self.root / "independent" / "other", "new", {**_coordinates(), extra: "forbidden"})

    def test_missing_original_authority_references_cannot_be_projected(self):
        with self.journal() as journal:
            with self.assertRaisesRegex(operator.OperatorError, "original authority"):
                journal.approve("sha256:" + "7" * 64, {})
            self.assertEqual(journal.snapshot()["state"], "GENESIS")

    def test_live_projection_is_not_an_original_approval_claim(self):
        with self.journal() as journal:
            self.approve(journal)
            self.assertNotIn("humanAuthorityVerified", journal.snapshot())
            self.assertEqual(journal.snapshot()["approval"]["authorityRefs"], _refs())

    def test_concurrent_gate_instances_cannot_reserve_one_grant(self):
        context = multiprocessing.get_context("spawn")
        output = context.Queue()
        with self.journal() as journal:
            self.approve(journal)
            process = context.Process(target=_competing_writer, args=(str(self.path), str(self.checkpoint), self.genesis, output))
            process.start()
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join()
                self.fail("competing writer did not finish")
            self.assertEqual(process.exitcode, 0)
            self.assertEqual(output.get(timeout=2), "refused")
            self.assertEqual(journal.snapshot()["state"], "APPROVED")

    def test_source_intent_is_durable_before_public_write(self):
        with self.journal() as journal:
            self.approve(journal)
            self.admission(journal)
            expected = {"ref": "refs/heads/ofarm-ci-transition/source/fictional-grant", "sha": "1" * 40, "previous": None}
            journal.intent("source_push", expected)
            self.assertEqual(journal.snapshot()["state"], "SOURCE_RESERVED")
        with self.journal() as journal:
            self.assertEqual(journal.snapshot()["pending"]["expected"], expected)
            with self.assertRaisesRegex(operator.OperatorError, "unresolved"):
                journal.intent("source_push", expected)
            with self.assertRaisesRegex(operator.OperatorError, "unresolved"):
                journal.bind_run("source", {"runId": 202, "runAttempt": 1})
            journal.reconcile("source_push", [expected])
            journal.bind_run("source", {"runId": 201, "runAttempt": 1})
            with self.assertRaisesRegex(operator.OperatorError, "consumed"):
                journal.bind_run("source", {"runId": 202, "runAttempt": 1})

    def test_unknown_public_outcome_consumes_grant_without_second_write(self):
        for matches in ([], [{}, {}]):
            with self.subTest(matches=matches):
                # Each subtest gets a distinct grant journal.
                directory = self.root / str(len(matches))
                directory.mkdir()
                checkpoint_dir = self.root / (str(len(matches)) + "-cp")
                checkpoint_dir.mkdir()
                path, checkpoint = directory / "journal", checkpoint_dir / "tail"
                genesis = operator.TransitionJournal.create(path, checkpoint, "fictional-grant", _coordinates())
                with operator.TransitionJournal(path, checkpoint, genesis) as journal:
                    self.approve(journal)
                    journal.intent("admission", {"bodyDigest": "sha256:" + "8" * 64})
                    with self.assertRaisesRegex(operator.OperatorError, "grant consumed"):
                        journal.reconcile("admission", matches)
                    self.assertEqual(journal.snapshot()["state"], "FAILED")
                    with self.assertRaisesRegex(operator.OperatorError, "terminal"):
                        self.admission(journal)

    def test_wrong_identity_and_attempt_two_cannot_rebind(self):
        with self.journal() as journal:
            self.approve(journal)
            self.admission(journal)
            self.push(journal, "source")
            with self.assertRaisesRegex(operator.OperatorError, "first run attempt"):
                journal.bind_run("source", {"runId": 201, "runAttempt": 2})
            journal.bind_run("source", {"runId": 201, "runAttempt": 1})
            with self.assertRaisesRegex(operator.OperatorError, "consumed"):
                journal.bind_run("source", {"runId": 202, "runAttempt": 1})

    def test_out_of_order_publication_or_acceptance_refuses(self):
        with self.journal() as journal:
            self.approve(journal)
            with self.assertRaisesRegex(operator.OperatorError, "out of order"):
                journal.seal({"artifactId": 1, "digest": "sha256:" + "f" * 64})
            with self.assertRaisesRegex(operator.OperatorError, "first sealed"):
                journal.accept({})
            with self.assertRaisesRegex(operator.OperatorError, "out of order"):
                self.push(journal, "publisher")

    def test_observed_contradictory_comment_identity_is_terminal(self):
        with self.journal() as journal:
            self.approve(journal)
            journal.intent("admission", {"bodyDigest": "sha256:" + "8" * 64})
            with self.assertRaisesRegex(operator.OperatorError, "differs from the durable intent"):
                journal.reconcile("admission", [{"bodyDigest": "sha256:" + "9" * 64, "commentId": 101}])
            self.assertEqual(journal.snapshot()["state"], "FAILED")
            with self.assertRaises(operator.OperatorError):
                journal.reconcile("admission", [{"bodyDigest": "sha256:" + "8" * 64, "commentId": 101}])

    def test_only_exact_absent_nonmain_ref_can_be_reserved(self):
        with self.journal() as journal:
            self.approve(journal)
            self.admission(journal)
            intended = {"ref": "refs/heads/ofarm-ci-transition/source/fictional-grant", "sha": "1" * 40, "previous": None}
            for changed in ({"ref": "refs/heads/main"}, {"ref": "refs/heads/ofarm-ci-transition/source/another"},
                            {"sha": "9" * 40}, {"previous": "1" * 40}):
                with self.subTest(changed=changed), self.assertRaisesRegex(operator.OperatorError, "exact absent"):
                    journal.intent("source_push", {**intended, **changed})

    def test_returning_ref_does_not_allow_another_run_or_attempt(self):
        with self.journal() as journal:
            accepted = self.sealed(journal)
            # An unseen ref round trip cannot be claimed detected. Even if the
            # ref is back at T, a replacement run cannot consume this tuple.
            with self.assertRaisesRegex(operator.OperatorError, "first sealed"):
                journal.accept({**accepted, "sourceRunId": 999})
            journal.accept(accepted)
            journal.fail("observed activation ref deletion")
            with self.assertRaisesRegex(operator.OperatorError, "terminal"):
                journal.accept(accepted)

    def test_torn_append_and_checkpoint_rollback_refuse(self):
        original_journal, original_checkpoint = self.path.read_bytes(), self.checkpoint.read_bytes()
        with self.journal() as journal:
            self.approve(journal)
        advanced_journal, advanced_checkpoint = self.path.read_bytes(), self.checkpoint.read_bytes()
        for raw, checkpoint in ((advanced_journal[:-1], advanced_checkpoint),
                                (advanced_journal, original_checkpoint),
                                (original_journal, advanced_checkpoint),
                                (advanced_journal.replace(b'"APPROVED"', b'"RETIRED"'), advanced_checkpoint)):
            with self.subTest(raw=len(raw), cp=len(checkpoint)):
                self.path.write_bytes(raw)
                self.checkpoint.write_bytes(checkpoint)
                with self.assertRaisesRegex(operator.OperatorError, "inconsistent"):
                    with self.journal():
                        self.fail("corrupt journal accepted")

    def test_missing_journal_checkpoint_or_lock_refuses_no_rebuild(self):
        for path in (self.path, self.checkpoint, self.path.with_name(self.path.name + ".lock")):
            with self.subTest(path=path.name):
                saved = path.read_bytes()
                path.unlink()
                with self.assertRaises(operator.OperatorError):
                    with self.journal():
                        self.fail("missing record accepted")
                with self.assertRaisesRegex(operator.OperatorError, "never rebuild"):
                    operator.TransitionJournal.create(self.path, self.checkpoint, "fictional-grant", _coordinates())
                path.write_bytes(saved)

    def test_append_fsync_and_checkpoint_boundaries_poison_handle(self):
        for fault_at in (1, 2, 3):
            with self.subTest(fault_at=fault_at):
                # Restore the valid original genesis for each independent fault.
                if fault_at == 1:
                    original_journal, original_checkpoint = self.path.read_bytes(), self.checkpoint.read_bytes()
                self.path.write_bytes(original_journal)
                self.checkpoint.write_bytes(original_checkpoint)
                original_fsync = os.fsync
                calls = 0
                def failure(fd):
                    nonlocal calls
                    calls += 1
                    if calls == fault_at:
                        raise OSError("fictional durable write failure")
                    return original_fsync(fd)
                with self.journal() as journal:
                    with patch.object(operator.os, "fsync", side_effect=failure):
                        with self.assertRaisesRegex(operator.OperatorError, "no public write"):
                            self.approve(journal)
                    with self.assertRaisesRegex(operator.OperatorError, "uncertain append"):
                        journal.snapshot()
                if fault_at < 3:
                    with self.assertRaises(operator.OperatorError):
                        with self.journal():
                            self.fail("unacknowledged append accepted")

    def test_every_public_intent_boundary_is_preserved_on_checkpoint_failure(self):
        stages = ("admission", "source_push", "source_binding", "publisher_push", "publisher_binding")
        for action in stages:
            with self.subTest(action=action):
                directory = self.root / action
                directory.mkdir()
                cpdir = self.root / (action + "-checkpoint")
                cpdir.mkdir()
                path, cp = directory / "journal", cpdir / "tail"
                genesis = operator.TransitionJournal.create(path, cp, "fictional-grant", _coordinates())
                with operator.TransitionJournal(path, cp, genesis) as journal:
                    expected = self.before_action(journal, action)
                    with patch.object(operator.os, "replace", side_effect=OSError("checkpoint failure")):
                        with self.assertRaisesRegex(operator.OperatorError, "no public write"):
                            journal.intent(action, expected)
                with self.assertRaises(operator.OperatorError):
                    with operator.TransitionJournal(path, cp, genesis):
                        self.fail("public-write intent survived without checkpoint acknowledgment")

    def test_post_public_write_checkpoint_failure_cannot_reconcile_or_reissue(self):
        for action in ("admission", "source_push", "source_binding", "publisher_push", "publisher_binding"):
            with self.subTest(action=action):
                directory = self.root / action
                directory.mkdir()
                cpdir = self.root / (action + "-checkpoint")
                cpdir.mkdir()
                path, checkpoint = directory / "journal", cpdir / "tail"
                genesis = operator.TransitionJournal.create(path, checkpoint, "fictional-grant", _coordinates())
                with operator.TransitionJournal(path, checkpoint, genesis) as journal:
                    expected = self.before_action(journal, action)
                    journal.intent(action, expected)
                    # The public write has happened; acknowledging the returned
                    # immutable identity fails at the independent checkpoint.
                    observed = expected if action.endswith("push") else {**expected, "commentId": 999}
                    with patch.object(operator.os, "replace", side_effect=OSError("fictional checkpoint failure")):
                        with self.assertRaisesRegex(operator.OperatorError, "no public write"):
                            journal.reconcile(action, [observed])
                    with self.assertRaisesRegex(operator.OperatorError, "uncertain append"):
                        journal.intent(action, expected)
                with self.assertRaises(operator.OperatorError):
                    with operator.TransitionJournal(path, checkpoint, genesis):
                        self.fail("uncertain post-write reconciliation was accepted")

    def test_durable_read_failure_never_returns_cached_authority(self):
        with self.journal() as journal:
            self.approve(journal)
            with patch.object(operator, "_regular", side_effect=operator.OperatorError("fictional read failure")):
                with self.assertRaisesRegex(operator.OperatorError, "read failure"):
                    journal.snapshot()

    def test_candidate_storage_and_colocated_checkpoint_refuse(self):
        with self.assertRaisesRegex(operator.OperatorError, "outside candidate"):
            operator.TransitionJournal(self.path, self.checkpoint, self.genesis, candidate_roots=(self.root,))
        with self.assertRaisesRegex(operator.OperatorError, "separate directory"):
            operator.TransitionJournal(self.path, self.path.with_name("tail"), self.genesis)


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
        return operator.create_policy_closure(self.repo, self.head, self.base, self.spec)

    def test_closure_covers_static_imports_inputs_tests_and_exact_tree(self):
        closure = self.closure()
        self.assertIn("helper.py", closure["files"])
        self.assertIn("ordinary.py", closure["dependencies"]["policy.py"])
        self.assertEqual(closure["rootTree"], self.git("rev-parse", "HEAD^{tree}"))
        result = operator.verify_policy_closure(self.repo, closure, self.head, self.base,
                                               operator.policy_closure_digest(closure), expected_tree=closure["rootTree"])
        self.assertEqual(result["purpose"], "policy-integrity")
        self.assertFalse(result["humanAuthorityVerified"])
        self.assertNotIn("rootSha", self.spec)

    def test_static_import_or_explicit_dependency_mutation_invalidates_frozen_closure(self):
        closure = self.closure()
        self.write("helper.py", "VALUE = 3\n")
        with self.assertRaisesRegex(operator.OperatorError, "dirty"):
            operator.verify_policy_closure(self.repo, closure, self.head, self.base, operator.policy_closure_digest(closure))
        self.git("update-index", "--assume-unchanged", "helper.py")
        with self.assertRaisesRegex(operator.OperatorError, "checkout bytes"):
            operator.verify_policy_closure(self.repo, closure, self.head, self.base, operator.policy_closure_digest(closure))

    def test_receipt_selected_root_base_digest_or_tree_is_rejected(self):
        closure = self.closure()
        arguments = (self.repo, closure, self.head, self.base, operator.policy_closure_digest(closure))
        for index, wrong in ((2, self.base), (3, self.head), (4, "sha256:" + "0" * 64)):
            changed = list(arguments)
            changed[index] = wrong
            with self.subTest(index=index), self.assertRaisesRegex(operator.OperatorError, "externally selected"):
                operator.verify_policy_closure(*changed)
        with self.assertRaisesRegex(operator.OperatorError, "external pin"):
            operator.verify_policy_closure(*arguments, expected_tree="0" * 40)

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
            operator.create_policy_closure(self.repo, self.head, self.base, different)

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
        manifest = operator.archive_policy_roots(self.repo, roots, archive)
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
        with self.assertRaisesRegex(operator.OperatorError, "already exists"):
            operator.archive_policy_roots(self.repo, roots, archive)
        with (archive / "policy-roots.bundle").open("ab") as stream:
            stream.write(b"corrupt")
        with self.assertRaisesRegex(operator.OperatorError, "digest differs"):
            operator.verify_archived_roots(archive, manifest)


if __name__ == "__main__":
    unittest.main()
