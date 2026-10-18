"""Reachable parity and isolation controls for the closed transition transform."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import tempfile
import unittest

from conformance import ci_policy_transition_workflows as workflows


ROOT = Path(__file__).resolve().parents[1]


def jobs(text: bytes) -> dict[str, str]:
    body = text.decode("utf-8").split("\njobs:\n", 1)[1]
    entries = re.split(r"(?m)^  ([a-z][a-z0-9-]*):\n", body)
    return {entries[i]: entries[i + 1] for i in range(1, len(entries), 2)}


def steps(job: str) -> dict[str, str]:
    entries = re.split(r"(?m)(?=^      - (?:name:|uses:))", job)[1:]
    result = {}
    for index, entry in enumerate(entries):
        first = entry.splitlines()[0]
        key = first.removeprefix("      - name: ") if first.startswith(
            "      - name: "
        ) else f"action-{index}"
        if key in result:
            raise AssertionError("duplicate workflow step name")
        result[key] = entry.rstrip() + "\n"
    return result


def environment_keys(text: bytes):
    """Read the generated block mappings without interpreting scalar values."""
    current = None
    for number, line in enumerate(text.decode().splitlines(), 1):
        indent = len(line) - len(line.lstrip())
        if current is not None and line.strip() and indent <= current[0]:
            yield current[1], current[2]
            current = None
        if re.fullmatch(r" *env:", line):
            current = (indent, number, [])
        elif current is not None and line.strip():
            if indent > current[0] + 2:
                # Retained multiline scalar values, such as pinned hashes.
                continue
            match = re.fullmatch(r" *([A-Za-z_][A-Za-z0-9_]*): .+", line)
            if not match or indent != current[0] + 2:
                raise AssertionError("unexpected generated environment mapping")
            current[2].append(match[1])
    if current is not None:
        yield current[1], current[2]


def without_observation(job: str, job_name: str) -> str:
    """Reverse only the exact declared v4 additions, never arbitrary step env."""
    assets = workflows._tool_assets()
    job = job.replace(workflows._bootstrap(job_name, assets), "", 1)
    final = "      - name: Require decisive transition tool completion\n"
    if job.count(final) != 1:
        raise AssertionError("missing or duplicate decisive completion")
    job = job[:job.index(final)]
    environment = workflows._tool_environment(job_name, assets, node=True)
    job = job.replace("        env:\n" + environment + "        with:\n", "        with:\n")
    job = job.replace("        env:\n" + environment + "        uses: ", "        uses: ")
    job = job.replace(environment, "")
    for (target_job, _), (download, identifier) in workflows.CURL_STEPS.items():
        if target_job != job_name:
            continue
        job = job.replace(workflows._lifecycle(job_name, assets, f"Start protected curl observation for {download}",
                                              f'curl-start --name "{download}" --github-output "$GITHUB_OUTPUT"',
                                              identifier=identifier), "", 1)
        job = job.replace(workflows._lifecycle(job_name, assets, f"Finish protected curl observation for {download}",
                                              "curl-finish", always=True), "", 1)
        job = job.replace(workflows._tool_environment(job_name, assets, node=False)
                          + f"          CURL_HOME: ${{{{ steps.{identifier}.outputs.CURL_HOME }}}}\n", "", 1)
    if job_name == "conformance":
        job = job.replace(workflows._lifecycle(job_name, assets, "Freeze protected gh policy from authenticated T",
                                              'gh-start --policy-root "$GITHUB_WORKSPACE/.baseline-admission-policy" '
                                              '--github-output "$GITHUB_OUTPUT"', identifier="transition-gh", token=True), "", 1)
        job = job.replace(workflows._lifecycle(job_name, assets, "Finish protected gh observation", "gh-finish", always=True), "", 1)
        selected = "".join(f"          {key}: ${{{{ steps.transition-gh.outputs.{key} }}}}\n"
                           for key in workflows.GH_ENVIRONMENT)
        job = job.replace(workflows._tool_environment(job_name, assets, node=False) + selected, "", 1)
    return job


class TransitionWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / workflows.SOURCE_INPUT).read_bytes()
        cls.publication = (ROOT / workflows.PUBLICATION_INPUT).read_bytes()
        cls.generated = workflows.generate(cls.source, cls.publication, consumer_pr=413)

    def assert_refused(self, source: bytes | None = None,
                       publication: bytes | None = None) -> None:
        with self.assertRaisesRegex(workflows.WorkflowParityError, "parity differs"):
            workflows.check_parity(
                self.source, self.publication,
                self.generated.source if source is None else source,
                self.generated.publication if publication is None else publication,
                consumer_pr=413,
            )

    def test_committed_generated_outputs_regenerate_byte_for_byte(self) -> None:
        result = workflows.check_parity(
            self.source, self.publication,
            (ROOT / workflows.SOURCE_OUTPUT).read_bytes(),
            (ROOT / workflows.PUBLICATION_OUTPUT).read_bytes(), consumer_pr=413,
        )
        self.assertEqual(result, self.generated)
        self.assertEqual(
            result, workflows.generate(self.source, self.publication, consumer_pr=413),
        )

    def test_only_two_named_consumers_and_fixed_concurrency(self) -> None:
        for consumer in (413, 411):
            with self.subTest(consumer=consumer):
                generated = workflows.generate(self.source, self.publication, consumer_pr=consumer)
                for output in (generated.source, generated.publication):
                    self.assertEqual(output.count(f"group: ofarm-pr-{consumer}\n".encode()), 1)
        for consumer in (417, 409, 0, -1, True, "413"):
            with self.subTest(consumer=consumer):
                with self.assertRaisesRegex(workflows.WorkflowParityError, "consumer"):
                    workflows.generate(self.source, self.publication, consumer_pr=consumer)

    def test_input_git_blobs_and_sha256_are_both_pinned(self) -> None:
        for name, content in (
            (workflows.SOURCE_INPUT, self.source),
            (workflows.PUBLICATION_INPUT, self.publication),
        ):
            blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
            self.assertEqual(workflows.INPUT_PINS[name], (blob, hashlib.sha256(content).hexdigest()))
        for field in ("source", "publication"):
            with self.subTest(field=field):
                args = {"source": self.source, "publication": self.publication}
                args[field] += b"# unsigned change\n"
                with self.assertRaisesRegex(workflows.WorkflowParityError, "pinned canonical input differs"):
                    workflows.generate(**args, consumer_pr=413)

    def test_external_parity_uses_assets_from_explicit_authenticated_policy_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "conformance"
            target.mkdir()
            for filename in ("ci_policy_transition_tools.py", "ci_policy_transition_node.cjs",
                             "ci_policy_transition_execution.py", "ci_policy_transition_gh_relay.py",
                             "ci_policy_transition_curl.py"):
                content = (ROOT / "conformance" / filename).read_bytes()
                if filename == "ci_policy_transition_tools.py":
                    content += b"\n# Fictional independently authenticated T bytes.\n"
                (target / filename).write_bytes(content)
            frozen = workflows.generate(self.source, self.publication, consumer_pr=413, policy_root=root)
            self.assertNotEqual(frozen, self.generated)
            self.assertEqual(workflows.check_parity(self.source, self.publication, frozen.source,
                             frozen.publication, consumer_pr=413, policy_root=root), frozen)
            with self.assertRaisesRegex(workflows.WorkflowParityError, "parity differs"):
                workflows.check_parity(self.source, self.publication, frozen.source,
                                       frozen.publication, consumer_pr=413)

    def test_workload_tampering_cannot_become_a_generator_input(self) -> None:
        mutations = (
            (b"timeout-minutes: 45", b"timeout-minutes: 90"),
            (b"kernel/tests/test_conformance.py -q", b"kernel/tests/test_conformance.py -q -k smoke"),
            (b"conformance/run_review_baseline.py run", b"conformance/run_review_baseline.py run --retry"),
            (b"--no-cache", b"--cache-from compromised"),
            (b"--build-arg SANITIZER=memory", b"--build-arg SANITIZER=undefined"),
            (b"postgresql/ofarm_ed25519/Containerfile", b"postgresql/other/Containerfile"),
            (b"c457984bd29f", b"ffffffffffff"),
            (b"93cb6efe1820", b"aaaaaaaaaaaa"),
            (b"--only-binary=:all:", b"--only-binary=:none:"),
        )
        for old, new in mutations:
            with self.subTest(old=old):
                self.assertIn(old, self.source)
                with self.assertRaisesRegex(workflows.WorkflowParityError, "pinned canonical input differs"):
                    workflows.generate(self.source.replace(old, new, 1), self.publication, consumer_pr=413)

    def test_all_producer_steps_after_candidate_checkout_are_unchanged(self) -> None:
        ordinary = jobs(self.source)
        generated = jobs(self.generated.source)
        for job in ("conformance", "native-verifier"):
            with self.subTest(job=job):
                transformed = without_observation(generated[job], job).replace(
                    "--tlsv1.2 --retry 0 --output", "--tlsv1.2 --retry 3 --output",
                )
                anchor = "      - uses: " + workflows.CHECKOUT + "\n        with:\n" + (
                    "          ref: ${{ needs.baseline-admission.outputs.execution_merge_sha }}\n"
                )
                self.assertEqual(ordinary[job].count(anchor), 1)
                self.assertEqual(transformed.count(anchor), 1)
                self.assertEqual(
                    ordinary[job][ordinary[job].index(anchor):].rstrip(),
                    transformed[transformed.index(anchor):].rstrip(),
                )

    def test_all_unlisted_publisher_steps_remain_byte_identical_and_ordered(self) -> None:
        before = steps(jobs(self.publication)["publish"])
        after = steps(without_observation(jobs(self.generated.publication)["publish"], "publish"))
        permitted = {
            "Resolve the exact source artifacts again",
            "Download the trusted handoff by exact artifact ID",
            "Recheck live admission before validation",
            "Recheck live admission immediately before established publication",
            "Create trusted cross-run publication context",
            "Download authoritative amd64 evidence by publisher artifact ID",
            "Download authoritative arm64 evidence by publisher artifact ID",
            "Recheck live admission immediately before index publication",
            "Securely download and extract provisional conformance evidence",
            "Securely download and extract provisional amd64 evidence",
            "Securely download and extract provisional arm64 evidence",
            "Rebuild authoritative conformance claims with trusted policy",
        }
        moved = list(before).index("Create the exact authoritative artifact candidate")
        self.assertEqual(list(after), list(before)[:moved])
        for name in after:
            with self.subTest(step=name):
                if name not in permitted:
                    expected = before[name]
                    if workflows.CHECKOUT in expected and "execution_merge_sha" not in expected and "fetch-depth:" not in expected:
                        expected = expected.replace("        with:\n", "        with:\n          fetch-depth: 0\n")
                    self.assertEqual(after[name], expected)
        # The context changes only the ticket's artifact label, never native
        # claim content or the existing metadata inventory contract.
        name = "Create trusted cross-run publication context"
        self.assertEqual(
            after[name], before[name].replace(
                '"evidence-publication-ticket",', f'"{workflows.TICKET_NAME}",',
            ),
        )
        for name, operation in (
            ("Securely download and extract provisional conformance evidence", "download"),
            ("Securely download and extract provisional amd64 evidence", "download"),
            ("Securely download and extract provisional arm64 evidence", "download"),
            ("Rebuild authoritative conformance claims with trusted policy", "stage-conformance"),
        ):
            with self.subTest(counted_wrapper=name):
                self.assertEqual(after[name], before[name].replace(
                    "          .publication-policy/conformance/evidence_publication_policy.py\n"
                    f"          {operation}\n",
                    f"          .publication-policy/{workflows.PUBLICATION}\n"
                    f"          --operation {operation}\n"
                    "          --phase publisher-start\n",
                ))

    def test_guards_are_fresh_read_only_policy_jobs_except_self_cancellation(self) -> None:
        source_jobs = jobs(self.generated.source)
        publication_jobs = jobs(self.generated.publication)
        for collection, guard_name, timeout in (
            (source_jobs, "source-guard", 135),
            (publication_jobs, "publisher-guard", 60),
        ):
            for name, job in collection.items():
                with self.subTest(job=name):
                    self.assertEqual("      actions: write\n" in job, name == guard_name)
                    self.assertNotIn("issues: write", job)
                    self.assertNotIn("contents: write", job)
                    self.assertNotIn("id-token: write", job)
                    self.assertNotIn("secrets.", job)
            guard = collection[guard_name]
            self.assertIn(f"timeout-minutes: {timeout}\n", guard)
            self.assertIn("ref: ${{ github.workflow_sha }}", guard)
            self.assertIn("path: .transition-policy", guard)
            self.assertNotIn("execution_merge_sha", guard)
            self.assertNotIn("upload-artifact", guard)
            self.assertNotIn("download-artifact", guard)
            self.assertNotIn("actions/cache", guard)
            self.assertIn("--operation guard", guard)

    def test_no_guard_dependency_cycle_and_all_producers_required(self) -> None:
        source_jobs = jobs(self.generated.source)
        publication_jobs = jobs(self.generated.publication)
        handoff = source_jobs["publication-handoff"]
        self.assertIn("needs: [baseline-admission, conformance, native-verifier, source-guard]", handoff)
        for job in ("baseline-admission", "conformance", "native-verifier", "source-guard"):
            self.assertIn(f"needs.{job}.result == 'success'", handoff)
        self.assertNotIn("publication-handoff", source_jobs["source-guard"])
        seal = publication_jobs["publication-seal"]
        self.assertIn("needs: [source-admission, publish, publisher-guard]", seal)
        for job in ("source-admission", "publish", "publisher-guard"):
            self.assertIn(f"needs.{job}.result == 'success'", seal)
        self.assertNotIn("publication-seal", publication_jobs["publisher-guard"])

    def test_publication_permission_requires_successful_full_source_admission(self) -> None:
        generated = jobs(self.generated.publication)
        admission = generated["source-admission"]
        self.assertIn("publish: ${{ steps.publication-start.outputs.publish }}", admission)
        self.assertNotIn("steps.resolve-source.outputs.publish", admission)
        entries = steps(admission)
        for name in (
            "Download the trusted final handoff by artifact ID",
            "Re-authenticate policy after the ticket download",
            "Recheck live admission and authenticate the handoff",
            "Bind both source resolutions byte for byte",
        ):
            # No explicit condition overrides GitHub's default success() gate.
            self.assertNotRegex(entries[name], r"(?m)^        (?:if|continue-on-error):")
        for name in ("publish", "publisher-guard"):
            self.assertIn("needs.source-admission.outputs.publish == 'true'", generated[name])
        self.assertIn("needs.source-admission.result == 'success'", generated["publish"])
        self.assertIn("needs.source-admission.result == 'success'", generated["publication-seal"])

    def test_only_conformance_substantive_timeout_increases(self) -> None:
        source_jobs = jobs(self.generated.source)
        publisher_jobs = jobs(self.generated.publication)
        expected = {
            "baseline-admission": 5, "conformance": 60, "native-verifier": 120,
            "source-guard": 135, "publication-handoff": 10,
            "publisher-binding": 5, "source-admission": 10, "publish": 45,
            "publisher-guard": 60, "publication-seal": 10,
        }
        for name, job in {**source_jobs, **publisher_jobs}.items():
            self.assertEqual(re.findall(r"timeout-minutes: (\d+)", job), [str(expected[name])])

    def test_activation_filters_exclude_preparation_main_dispatch_tags_and_prs(self) -> None:
        for phase, content in (("source", self.generated.source), ("publisher", self.generated.publication)):
            trigger = content.decode().split("\non:\n")[1].split("\npermissions:")[0]
            self.assertEqual(trigger, f'  push:\n    branches: ["ofarm-ci-transition/{phase}/*"]\n')
            self.assertNotIn("workflow_dispatch", content.decode())
            self.assertNotIn("workflow_call", content.decode())

    def test_generated_source_authenticates_exact_generated_publisher(self) -> None:
        digest = hashlib.sha256(self.generated.publication).hexdigest()
        self.assertIn(f"sha256:{digest}\n".encode(), self.generated.source)
        self.assertIn(f'".publication-policy/{workflows.PUBLICATION_OUTPUT}"'.encode(), self.generated.source)

    def test_ticket_and_receipt_exist_only_after_guarded_jobs(self) -> None:
        source_jobs = jobs(self.generated.source)
        publisher_jobs = jobs(self.generated.publication)
        for name, job in source_jobs.items():
            self.assertEqual(f"name: {workflows.TICKET_NAME}\n" in job, name == "publication-handoff")
        for name, job in publisher_jobs.items():
            self.assertEqual(f"name: {workflows.RECEIPT_NAME}\n" in job, name == "publication-seal")
        self.assertNotIn("name: evidence-publication-ticket\n", self.generated.source.decode())
        self.assertNotIn("name: evidence-publication-receipt\n", self.generated.publication.decode())
        handoff_steps = steps(without_observation(source_jobs["publication-handoff"], "publication-handoff"))
        self.assertIn("--phase handoff-start", "".join(handoff_steps.values()))
        self.assertEqual(list(handoff_steps)[-1], "Upload immutable evidence publication ticket last")
        seal_steps = steps(without_observation(publisher_jobs["publication-seal"], "publication-seal"))
        self.assertEqual(list(seal_steps)[-2], "Upload authoritative evidence publication receipt last")
        self.assertIn("--phase seal-start", "".join(seal_steps.values()))
        self.assertIn("--operation seal", "".join(seal_steps.values()))
        for duplicate in ("Recheck live admission before validation", "Bind the publisher to the authenticated source job",
                          "Bind successful publication to unchanged live admission"):
            self.assertNotIn(duplicate, seal_steps)
        self.assertEqual("".join(seal_steps.values()).count("--phase seal-start"), 1)
        self.assertIn("Re-authenticate policy after the ticket download", seal_steps)
        self.assertIn("Re-authenticate policy before sealing publication", seal_steps)

    def test_frozen_grants_use_environment_and_typed_outputs_only(self) -> None:
        for content in (self.generated.source, self.generated.publication):
            for job in jobs(content).values():
                for step in steps(job).values():
                    if "--grant-json" in step:
                        self.assertIn('--grant-json "$TRANSITION_GRANT"', step)
                        self.assertIn('--bindings-json "$TRANSITION_BINDINGS"', step)
                        run = step.split("        run:", 1)[1]
                        self.assertNotIn("outputs.transition_grant", run)
                        self.assertNotIn("outputs.transition_bindings", run)
        seal = jobs(self.generated.publication)["publication-seal"]
        self.assertNotIn("ref: ${{ needs.baseline-admission.outputs.execution_merge_sha }}", seal)
        candidate = steps(seal)["Create the exact authoritative artifact candidate"]
        self.assertEqual(candidate.count("needs.publish.outputs.upload-"), 10)
        self.assertNotIn("steps.upload-", candidate)

    def test_download_adapter_preserves_exact_ids_digests_destinations_and_validation(self) -> None:
        publish = steps(jobs(self.generated.publication)["publish"])
        for architecture in ("amd64", "arm64"):
            step = publish[f"Download authoritative {architecture} evidence by publisher artifact ID"]
            self.assertIn(f"steps.upload-native-{architecture}.outputs.artifact-id", step)
            self.assertIn(f"steps.upload-native-{architecture}.outputs.artifact-digest", step)
            self.assertIn(f"ofarm-authoritative-input/{architecture}", step)
            self.assertIn(f"--artifact-name native-verifier-{architecture}", step)
            self.assertIn("--operation download", step)
        ticket = publish["Download the trusted handoff by exact artifact ID"]
        self.assertIn("steps.resolve-source.outputs.ticket_artifact_digest", ticket)
        self.assertIn(f"--artifact-name {workflows.TICKET_NAME}", ticket)
        self.assertNotIn(workflows.DOWNLOAD, self.generated.publication.decode())

    def test_hostile_generated_transformations_are_refused(self) -> None:
        source_mutations = (
            (b"timeout-minutes: 60", b"timeout-minutes: 61"),
            (b"timeout-minutes: 120", b"timeout-minutes: 121"),
            (b"kernel/tests/test_conformance.py -q", b"kernel/tests/test_conformance.py -q -k smoke"),
            (b".artifacts/review-baseline/run-2", b".artifacts/review-baseline/run-1"),
            (b"needs.source-guard.result == 'success'", b"true"),
            (b"path: .transition-policy", b"path: ."),
            (b"      contents: read", b"      contents: write"),
            (b"    steps:\n", b"    continue-on-error: true\n    steps:\n"),
            (b'branches: ["ofarm-ci-transition/source/*"]', b'branches: ["**"]'),
            (b"--operation guard", b"--operation admit"),
            (b"--no-cache", b"--cache-from attacker"),
            (b"--build-arg SANITIZER=memory", b"--build-arg SANITIZER=undefined"),
            (b"OFARM_SECURITY_AUDIT_PG_ADMIN_DSN:", b"ANOTHER_DSN:"),
            (b"--output-dir .artifacts/review-baseline/run-1", b"--output-dir .artifacts/review-baseline/run-1 || true"),
        )
        for old, new in source_mutations:
            with self.subTest(source=old):
                self.assertIn(old, self.generated.source)
                self.assert_refused(source=self.generated.source.replace(old, new, 1))
        publication_mutations = (
            (b"timeout-minutes: 45", b"timeout-minutes: 60"),
            (b"needs.publisher-guard.result == 'success'", b"true"),
            (b"--operation seal", b"--operation publish"),
            (b"--artifact-digest", b"--ignore-digest"),
            (b"--authoritative", b""),
            (b"compose-index", b"copy-index"),
            (b"--source-commit", b"--source-branch"),
            (b"      actions: write", b"      actions: read"),
            (b"ci-policy-transition-publication-receipt-v1", b"evidence-publication-receipt"),
        )
        for old, new in publication_mutations:
            with self.subTest(publication=old):
                self.assertIn(old, self.generated.publication)
                self.assert_refused(publication=self.generated.publication.replace(old, new, 1))
        self.assert_refused(source=self.generated.source + b"  unauthorized:\n    runs-on: ubuntu-latest\n")

    def test_missing_duplicate_and_unexpected_structure_anchors_refuse(self) -> None:
        for text in ("", "anchoranchor"):
            with self.assertRaisesRegex(workflows.WorkflowParityError, "exact anchors"):
                workflows._replace(text, "anchor", "replacement", "hostile fixture")
        for body in ("jobs:\n", "\njobs:\n  fake:\n", "\njobs:\n\njobs:\n"):
            with self.assertRaises(workflows.WorkflowParityError):
                workflows._jobs(body, ("expected",))
        with self.assertRaisesRegex(workflows.WorkflowParityError, "missing or duplicate"):
            workflows._named_step(["      - name: duplicate\n"] * 2, "duplicate")

    def test_cli_regeneration_changes_only_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".github/workflows").mkdir(parents=True)
            for name, content in ((workflows.SOURCE_INPUT, self.source),
                                  (workflows.PUBLICATION_INPUT, self.publication)):
                (root / name).write_bytes(content)
            args = ["--root", str(root), "--consumer-pr", "413"]
            self.assertEqual(workflows.main(["generate", *args]), 0)
            self.assertEqual(workflows.main(["check", *args]), 0)
            self.assertEqual((root / workflows.SOURCE_INPUT).read_bytes(), self.source)
            self.assertEqual((root / workflows.PUBLICATION_INPUT).read_bytes(), self.publication)
            (root / workflows.SOURCE_OUTPUT).write_bytes(b"unauthorized")
            self.assertEqual(workflows.main(["check", *args]), 1)

    def test_every_action_and_post_has_literal_bootstrap_and_final_disposition(self) -> None:
        assets = workflows._tool_assets()
        for workflow in (self.generated.source, self.generated.publication):
            for job_name, body in jobs(workflow).items():
                with self.subTest(job=job_name):
                    entries = list(steps(body).values())
                    self.assertIn("Start trusted transition tool observation", entries[0])
                    self.assertIn("Register final transition cleanup", entries[1])
                    self.assertIn(workflows.LOCAL_ACTION, entries[1])
                    self.assertIn('NODE_OPTIONS: ""', entries[1])
                    self.assertIn("Require decisive transition tool completion", entries[-1])
                    self.assertIn("if: always()", entries[-1])
                    self.assertNotIn(" finish", entries[-1])
                    for step in entries[2:-1]:
                        if re.search(r"^        uses: |^      - uses: ", step, re.MULTILINE):
                            self.assertIn(workflows._tool_environment(job_name, assets, node=True), step)
                            if workflows.CHECKOUT in step and "execution_merge_sha" not in step:
                                self.assertIn("fetch-depth: 0", step)
                    bootstrap = entries[0].split("<<'OFARM_TRANSITION_BOOTSTRAP'\n", 1)[1]
                    bootstrap = bootstrap.rsplit("          OFARM_TRANSITION_BOOTSTRAP", 1)[0]
                    source = "\n".join(line.removeprefix("          ") for line in bootstrap.splitlines())
                    compile(source, "literal-bootstrap", "exec")
                    self.assertIn("post-if: always()", source)
                    self.assertIn("finish", source)
                    self.assertIn('workspace / "../../_temp/ofarm-ci-transition-action"', source)

    def test_generated_environment_keys_are_unique_ignoring_case(self) -> None:
        # GitHub TemplateReader compares mapping keys with OrdinalIgnoreCase,
        # even though the Linux runner's process environment is case-sensitive.
        # Keep this oracle independent of _tool_environment's expected text.
        for consumer in (413, 411):
            generated = workflows.generate(self.source, self.publication, consumer_pr=consumer)
            for workflow in (generated.source, generated.publication):
                mappings = list(environment_keys(workflow))
                self.assertGreater(len(mappings), 1)
                for line, keys in mappings:
                    with self.subTest(consumer=consumer, workflow=workflow.splitlines()[0], line=line):
                        folded = [key.upper() for key in keys]
                        self.assertEqual(len(folded), len(set(folded)), keys)

    def test_retry_rewrite_is_exactly_four_execution_invocations(self) -> None:
        generated = jobs(self.generated.source)
        self.assertEqual(generated["conformance"].count("--tlsv1.2 --retry 0 --output"), 2)
        self.assertEqual(generated["native-verifier"].count("--tlsv1.2 --retry 0 --output"), 1)
        self.assertEqual(re.findall(r"^            architecture: ([a-z0-9]+)$", generated["native-verifier"], re.MULTILINE), ["amd64", "arm64"])
        self.assertNotIn(b"--retry 3", self.generated.source)

    def test_only_canonical_curl_and_gh_steps_receive_typed_lifecycle_environment(self) -> None:
        source_jobs = jobs(self.generated.source)
        observed = set()
        for job_name, body in source_jobs.items():
            entries = steps(body)
            names = list(entries)
            for name, step in entries.items():
                if "          CURL_HOME:" in step:
                    observed.add((job_name, name))
                    download, identifier = workflows.CURL_STEPS[(job_name, name)]
                    self.assertIn(f"steps.{identifier}.outputs.CURL_HOME", step)
                    before, after = names[names.index(name) - 1], names[names.index(name) + 1]
                    self.assertEqual(before, f"Start protected curl observation for {download}")
                    self.assertEqual(after, f"Finish protected curl observation for {download}")
                    self.assertIn("if: always()", entries[after])
                    self.assertIn('--github-output "$GITHUB_OUTPUT"', entries[before])
                if "          GH_CONFIG_DIR:" in step:
                    self.assertEqual((job_name, name), ("conformance", workflows.GH_STEP))
                    for key in workflows.GH_ENVIRONMENT:
                        self.assertIn(f"{key}: ${{{{ steps.transition-gh.outputs.{key} }}}}", step)
            if job_name == "conformance":
                gh_start = "Freeze protected gh policy from authenticated T"
                self.assertEqual(names[names.index(gh_start) - 1], "Recheck live admission before conformance")
                self.assertEqual(names[names.index(gh_start) + 1], "Bind conformance to the admitted coordinates")
                self.assertIn('gh-start --policy-root "$GITHUB_WORKSPACE/.baseline-admission-policy"', entries[gh_start])
                self.assertIn("GH_TOKEN: ${{ github.token }}", entries[gh_start])
                self.assertEqual(names[names.index(workflows.GH_STEP) + 1], "Finish protected gh observation")
                self.assertIn("if: always()", entries["Finish protected gh observation"])
        self.assertEqual(observed, set(workflows.CURL_STEPS))

    def test_complete_generated_job_graph_has_no_missing_or_cyclic_dependencies(self) -> None:
        for content in (self.generated.source, self.generated.publication):
            collection = jobs(content)
            graph = {}
            for name, body in collection.items():
                dependencies = re.findall(r"^    needs: (.+)$", body, re.MULTILINE)
                self.assertLessEqual(len(dependencies), 1)
                graph[name] = set(dependencies[0].strip("[]").split(", ")) - {""} if dependencies else set()
                self.assertTrue(graph[name] <= collection.keys())
            reached = set()
            while len(reached) < len(graph):
                ready = {name for name, dependencies in graph.items() if dependencies <= reached} - reached
                self.assertTrue(ready, "generated job dependency cycle")
                reached.update(ready)

    def test_bootstrap_loader_cleanup_and_retry_mutations_are_closed(self) -> None:
        for old, new in (
            (b"--retry 0", b"--retry 3"),
            (b"--require=${{ runner.temp }}/ofarm-ci-transition-control/node.cjs", b"--require=./candidate.cjs"),
            (b"uses: ./../../_temp/ofarm-ci-transition-action", b"uses: ./candidate-action"),
            (b"Require decisive transition tool completion", b"Ignore transition tool completion"),
            (b"post-if: always()", b"post-if: success()"),
        ):
            with self.subTest(mutation=old):
                self.assertIn(old, self.generated.source)
                self.assert_refused(source=self.generated.source.replace(old, new, 1))


if __name__ == "__main__":
    unittest.main()
