#!/usr/bin/env python3
"""Closed, byte-preserving workflow transform for decision TRANSITION-001 v4.

This is a preparation-time generator, never a candidate-controlled CI loader.
The two exact ordinary workflows are its only workload source. Their Git blob
IDs and SHA-256 digests must both match before any rewrite is attempted. Each
rewrite has a unique anchor; output parity compares every byte, not selected
command names. Rebase requires a separately reviewed input-pin update.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
import zlib


TRUSTED_BASE = "301bf4aa3196b503ec114ebfa0f455be818627a4"
SOURCE_INPUT = ".github/workflows/conformance.yml"
PUBLICATION_INPUT = ".github/workflows/evidence-publication.yml"
SOURCE_OUTPUT = ".github/workflows/ci-policy-transition-source.yml"
PUBLICATION_OUTPUT = ".github/workflows/ci-policy-transition-publication.yml"
INPUT_PINS = {
    SOURCE_INPUT: (
        "f79977d1d7524a2ccc3ed3b18c5e29be94671e3d",
        "bc32f0b6e947fe7c6b228c9c76e0d2a01509d5461ff1d2e8be5831a5c5efd8e3",
    ),
    PUBLICATION_INPUT: (
        "a48abc385d7615d36b5520ef00498ce161c92aeb",
        "fa52c97e7273dd91adbcc9fb623085ea9a87f95058f7e1baf45c9fb640638f7c",
    ),
}
CHECKOUT = "actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5"
DOWNLOAD = "actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131 # v7"
CORE = "conformance/ci_policy_transition.py"
PUBLICATION = "conformance/ci_policy_transition_publication.py"
TICKET_FILE = "ci-policy-transition-ticket.json"
TICKET_NAME = "ci-policy-transition-ticket-v1"
RECEIPT_FILE = "ci-policy-transition-publication-receipt.json"
RECEIPT_NAME = "ci-policy-transition-publication-receipt-v1"
_JOB = re.compile(r"^  ([a-z][a-z0-9-]*):\n", re.MULTILINE)
_STEP = re.compile(r"^      - (?:name:|uses:)", re.MULTILINE)
CONTROL = "${{ runner.temp }}/ofarm-ci-transition-control"
LOCAL_ACTION = "./../../_temp/ofarm-ci-transition-action"
TOOLS_JOBS = {
    "baseline-admission": "source-gate", "conformance": "conformance",
    "native-verifier": "native-${{ matrix.architecture }}", "source-guard": "source-guard",
    "publication-handoff": "handoff", "publisher-binding": "publisher-gate",
    "source-admission": "source-admission", "publish": "publish",
    "publisher-guard": "publisher-guard", "publication-seal": "seal",
}
GH_ENVIRONMENT = ("GH_CONFIG_DIR", "GH_CACHE_DIR", "GH_HOST", "GH_PROMPT_DISABLED",
                  "GH_NO_UPDATE_NOTIFIER", "GH_NO_EXTENSION_UPDATE_NOTIFIER", "NO_COLOR", "CLICOLOR")
CURL_STEPS = {
    ("conformance", "Authenticate and install the exact Buildx client"): ("buildx-amd64", "transition-curl-buildx"),
    ("conformance", "Authenticate and install the exact GitHub CLI"): ("gh-amd64", "transition-curl-gh"),
    ("native-verifier", "Authenticate and install the exact Buildx client"): ("buildx-${{ matrix.architecture }}", "transition-curl-buildx"),
}
GH_STEP = "Cryptographically reverify retained native release evidence"


class WorkflowParityError(ValueError):
    """The canonical input, closed rewrite, or generated output differs."""


@dataclass(frozen=True)
class GeneratedWorkflows:
    source: bytes
    publication: bytes
    rewrites: tuple[str, ...]


def _replace(text: str, old: str, new: str, label: str, count: int = 1) -> str:
    observed = text.count(old)
    if observed != count:
        raise WorkflowParityError(
            f"{label}: expected {count} exact anchors, observed {observed}"
        )
    return text.replace(old, new)


def _authenticate_input(path: str, content: bytes) -> str:
    if not isinstance(content, bytes):
        raise WorkflowParityError(f"{path}: canonical input must be bytes")
    blob, digest = INPUT_PINS[path]
    prefix = b"blob " + str(len(content)).encode("ascii") + b"\0"
    if (
        hashlib.sha1(prefix + content).hexdigest() != blob
        or hashlib.sha256(content).hexdigest() != digest
    ):
        raise WorkflowParityError(f"{path}: pinned canonical input differs")
    return content.decode("utf-8", errors="strict")


def _jobs(text: str, expected: tuple[str, ...]) -> tuple[str, dict[str, str]]:
    if text.count("\njobs:\n") != 1:
        raise WorkflowParityError("expected one exact jobs anchor")
    prefix, body = text.split("\njobs:\n")
    matches = list(_JOB.finditer(body))
    if tuple(match.group(1) for match in matches) != expected:
        raise WorkflowParityError("canonical job inventory/order differs")
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        result[match.group(1)] = body[match.start():end]
    return prefix + "\njobs:\n", result


def _steps(job: str) -> tuple[str, list[str]]:
    matches = list(_STEP.finditer(job))
    if not matches:
        raise WorkflowParityError("job has no exact step anchors")
    return job[:matches[0].start()], [
        job[match.start():matches[index + 1].start()]
        if index + 1 < len(matches) else job[match.start():]
        for index, match in enumerate(matches)
    ]


def _named_step(steps: list[str], name: str) -> int:
    matches = [
        index for index, step in enumerate(steps)
        if step.startswith(f"      - name: {name}\n")
    ]
    if len(matches) != 1:
        raise WorkflowParityError(f"step {name!r}: missing or duplicate anchor")
    return matches[0]


def _bound_inputs(step: str, job: str) -> str:
    step = _replace(
        step, "          OFARM_ADMISSION_TOKEN: ${{ github.token }}\n",
        "          OFARM_ADMISSION_TOKEN: ${{ github.token }}\n"
        f"          TRANSITION_GRANT: ${{{{ needs.{job}.outputs.transition_grant }}}}\n"
        f"          TRANSITION_BINDINGS: ${{{{ needs.{job}.outputs.transition_bindings }}}}\n",
        "bind immutable grant inputs through environment",
    )
    return _replace(
        step, "          --phase ",
        '          --grant-json "$TRANSITION_GRANT"\n'
        '          --bindings-json "$TRANSITION_BINDINGS"\n'
        "          --phase ", "bind frozen gate projection",
    )


def _rewrite_admission(step: str, phase: str, grant_job: str | None) -> str:
    step = _replace(
        step, "conformance/review_baseline_admission.py", CORE,
        f"{phase} adapter",
    )
    matches = list(re.finditer(r"^          --operation [a-z]+\n", step, re.MULTILINE))
    if len(matches) != 1:
        raise WorkflowParityError(f"{phase}: expected one operation")
    operation = matches[0].group(0)
    step = _replace(
        step, operation, operation + f"          --phase {phase}\n",
        f"{phase} pool ownership",
    )
    return _bound_inputs(step, grant_job) if grant_job else step


def _transition_step(phase: str, operation: str, policy_path: str,
                     grant_job: str | None = None) -> str:
    step = f'''      - name: Check live transition authority ({phase})
        id: transition-check
        env:
          OFARM_ADMISSION_TOKEN: ${{{{ github.token }}}}
        run: >-
          /usr/bin/python3
          {policy_path}/{CORE}
          --operation {operation}
          --phase {phase}
          --event-name "$GITHUB_EVENT_NAME"
          --event-path "$GITHUB_EVENT_PATH"
          --github-sha "$GITHUB_SHA"
          --workflow-sha "$GITHUB_WORKFLOW_SHA"
          --workflow-ref "$GITHUB_WORKFLOW_REF"
          --repository "$GITHUB_REPOSITORY"
          --policy-sha "$GITHUB_WORKFLOW_SHA"
          --github-output "$GITHUB_OUTPUT"
'''
    return _bound_inputs(step, grant_job) if grant_job else step


def _isolated_prefix(job_id: str, name: str, needs: str, condition: str,
                     minutes: int, *, guard: bool = False) -> str:
    return f'''  {job_id}:
    name: {name}
    needs: {needs}
    if: {condition}
    runs-on: ubuntu-24.04
    timeout-minutes: {minutes}
    permissions:
      actions: {"write" if guard else "read"}
      contents: read
      issues: read
      pull-requests: read
    steps:
      - uses: {CHECKOUT}
        with:
          ref: ${{{{ github.workflow_sha }}}}
          path: .transition-policy
          persist-credentials: false
          set-safe-directory: false
      - name: Authenticate the isolated transition policy
        run: |
          test "$(git -C .transition-policy rev-parse HEAD)" = "$GITHUB_WORKFLOW_SHA"
          git -C .transition-policy diff --exit-code --no-ext-diff
          test -z "$(git -C .transition-policy status --porcelain=v1 --untracked-files=all)"
'''


def _guard(phase: str, needs: str, condition: str, minutes: int) -> str:
    return (
        _isolated_prefix(phase, phase.replace("-", " "), needs, condition,
                         minutes, guard=True)
        + _transition_step(phase, "guard", ".transition-policy", needs) + "\n"
    )


def _source_header(prefix: str, consumer: int, publisher_digest: str) -> str:
    # Only event/name/ref/provenance changes. Existing workflow-level env keys
    # are retained apart from obsolete workflow_call inputs and publisher pin.
    env = prefix.split("\nenv:\n", 1)[1].split("\njobs:\n", 1)[0]
    env = _replace(
        env, "  OFARM_BASELINE_ADMISSION_INPUTS: ${{ toJSON(inputs) }}\n", "",
        "remove ordinary workflow_call inputs",
    )
    env = _replace(env, INPUT_PINS[PUBLICATION_INPUT][1], publisher_digest,
                   "pin generated transition publisher")
    return f'''# Generated by conformance/ci_policy_transition_workflows.py; do not hand edit.
# Canonical source: {TRUSTED_BASE}:{SOURCE_INPUT}
# Source blob {INPUT_PINS[SOURCE_INPUT][0]}; sha256 {INPUT_PINS[SOURCE_INPUT][1]}
name: OFARM2 temporary policy source v1

on:
  push:
    branches: ["ofarm-ci-transition/source/*"]

permissions: {{}}

concurrency:
  group: ofarm-pr-{consumer}
  cancel-in-progress: false

env:
{env}
jobs:
'''


def _source(source: str, consumer: int, publisher_digest: str) -> str:
    prefix, jobs = _jobs(source, (
        "baseline-admission", "conformance", "publication-handoff", "native-verifier",
    ))
    for job_id, phase in (
        ("baseline-admission", "source-gate"),
        ("conformance", "conformance"),
        ("native-verifier", "native-${{ matrix.architecture }}"),
    ):
        head, steps = _steps(jobs[job_id])
        head = _replace(head, "    permissions:\n", "    permissions:\n      actions: read\n",
                        f"{job_id} authenticated run reads")
        if job_id == "conformance":
            head = _replace(head, "    timeout-minutes: 45\n", "    timeout-minutes: 60\n",
                            "finite conformance60 ceiling")
        if job_id == "baseline-admission":
            head = _replace(
                head, "    outputs:\n", "    outputs:\n"
                "      transition_grant: ${{ steps.admission.outputs.transition_grant }}\n"
                "      transition_bindings: ${{ steps.admission.outputs.transition_bindings }}\n",
                "source gate freezes transition records",
            )
        admission = [i for i, step in enumerate(steps)
                     if "conformance/review_baseline_admission.py" in step]
        if len(admission) != 1:
            raise WorkflowParityError(f"{job_id}: expected one admission step")
        steps[admission[0]] = _rewrite_admission(
            steps[admission[0]], phase,
            None if job_id == "baseline-admission" else "baseline-admission",
        )
        jobs[job_id] = head + "".join(steps)

    head, steps = _steps(jobs["publication-handoff"])
    head = _replace(head, "needs: [baseline-admission, conformance, native-verifier]",
                    "needs: [baseline-admission, conformance, native-verifier, source-guard]",
                    "handoff guarded dependencies")
    head = _replace(head, "needs.native-verifier.result == 'success'\n",
                    "needs.native-verifier.result == 'success' &&\n"
                    "      needs.source-guard.result == 'success'\n",
                    "handoff requires successful guard")
    auth_index = _named_step(steps, "Authenticate the immutable publication handoff policy")
    steps[auth_index] = _replace(
        steps[auth_index], ".github/workflows/evidence-publication.yml",
        PUBLICATION_OUTPUT, "handoff authenticates transition publisher",
    )
    index = _named_step(steps, "Recheck admission and seal the exact provisional inventory")
    steps[index] = _rewrite_admission(steps[index], "handoff", "baseline-admission")
    steps[index] = _replace(steps[index], "evidence-publication-ticket.json", TICKET_FILE,
                            "transition handoff filename")
    upload = _named_step(steps, "Upload immutable evidence publication ticket last")
    steps[upload] = _replace(steps[upload], "name: evidence-publication-ticket\n",
                             f"name: {TICKET_NAME}\n", "transition ticket artifact")
    steps[upload] = _replace(steps[upload], "evidence-publication-ticket.json", TICKET_FILE,
                             "transition ticket upload filename")
    steps.insert(index, _transition_step("handoff-start", "admit", ".publication-policy",
                                         "baseline-admission"))
    jobs["publication-handoff"] = head + "".join(steps)
    guard = _guard("source-guard", "baseline-admission",
                   "needs.baseline-admission.outputs.eligible == 'true'", 135)
    return (
        _source_header(prefix, consumer, publisher_digest)
        + jobs["baseline-admission"] + jobs["conformance"]
        + jobs["native-verifier"].rstrip() + "\n\n" + guard
        + jobs["publication-handoff"].rstrip() + "\n"
    )


def _publication_header(prefix: str, consumer: int) -> str:
    env = prefix.split("\nenv:\n", 1)[1].split("\njobs:\n", 1)[0]
    return f'''# Generated by conformance/ci_policy_transition_workflows.py; do not hand edit.
# Canonical source: {TRUSTED_BASE}:{PUBLICATION_INPUT}
# Source blob {INPUT_PINS[PUBLICATION_INPUT][0]}; sha256 {INPUT_PINS[PUBLICATION_INPUT][1]}
name: OFARM2 temporary policy publication v1

on:
  push:
    branches: ["ofarm-ci-transition/publisher/*"]

permissions: {{}}

concurrency:
  group: ofarm-pr-{consumer}
  cancel-in-progress: false

env:
{env}
jobs:
'''


def _publication_steps(job: str, phases: tuple[str, ...],
                       grant_job: str) -> tuple[str, list[str]]:
    head, steps = _steps(job)
    adapters = [i for i, step in enumerate(steps)
                if "conformance/review_baseline_admission.py\n" in step]
    if len(adapters) != len(phases):
        raise WorkflowParityError("publisher admission step inventory differs")
    for index, phase in zip(adapters, phases):
        steps[index] = _rewrite_admission(steps[index], phase, grant_job)
    # Ticket identity is the only metadata-content rewrite; substantive
    # validation, archived evidence, and native-index operations remain exact.
    for index, step in enumerate(steps):
        if "evidence-publication-ticket" in step:
            steps[index] = step.replace("evidence-publication-ticket.json", TICKET_FILE).replace(
                '"evidence-publication-ticket",', f'"{TICKET_NAME}",'
            )
    for name in (
        "Download the trusted final handoff by artifact ID",
        "Download the trusted handoff by exact artifact ID",
    ):
        matches = [index for index, step in enumerate(steps)
                   if step.startswith(f"      - name: {name}\n")]
        if matches:
            if len(matches) != 1:
                raise WorkflowParityError("ticket download step is duplicated")
            index = matches[0]
            steps[index] = _download_step(
                steps[index], TICKET_NAME,
                "${{ steps.resolve-source.outputs.ticket_artifact_id }}",
                "${{ steps.resolve-source.outputs.ticket_artifact_digest }}",
                "${{ runner.temp }}/ofarm-publication-ticket",
                "source-admission" if grant_job == "publisher-binding" else "publisher-start",
            )
    return head, steps


def _download_step(step: str, artifact_name: str, artifact_id: str,
                   artifact_digest: str, output_directory: str, phase: str) -> str:
    # This is the approved transition ticket/receipt adapter: preserve exact
    # archive identity and destination, but authenticate its digest before the
    # existing safe extractor sees it. The former Action is explicitly listed
    # as replaced; subsequent substantive native commands are unchanged.
    if step.count(f"        uses: {DOWNLOAD}\n") != 1:
        raise WorkflowParityError("expected the exact pinned download Action")
    prefix = step[:step.index("        uses:")]
    return prefix + f'''        env:
          OFARM_ARTIFACT_TOKEN: ${{{{ github.token }}}}
          ARTIFACT_ID: {artifact_id}
          ARTIFACT_DIGEST: {artifact_digest}
          OUTPUT_DIRECTORY: {output_directory}
        run: >-
          /usr/bin/python3
          .publication-policy/{PUBLICATION}
          --operation download
          --phase {phase}
          --api-url "$GITHUB_API_URL"
          --repository "$GITHUB_REPOSITORY"
          --artifact-name {artifact_name}
          --artifact-id "$ARTIFACT_ID"
          --artifact-digest "$ARTIFACT_DIGEST"
          --output-directory "$OUTPUT_DIRECTORY"
'''


def _publication(publication: str, consumer: int) -> str:
    prefix, jobs = _jobs(publication, ("source-admission", "publish"))
    admission_head, admission_steps = _publication_steps(
        jobs["source-admission"], ("source-admission-resolve", "source-admission"),
        "publisher-binding",
    )
    admission_head = _replace(
        admission_head, "    if: github.event.workflow_run.conclusion == 'success'\n",
        "    needs: publisher-binding\n"
        "    if: needs.publisher-binding.outputs.eligible == 'true'\n",
        "publisher admitted after binding gate",
    )
    admission_head = _replace(
        admission_head, "    outputs:\n", "    outputs:\n"
        "      transition_grant: ${{ needs.publisher-binding.outputs.transition_grant }}\n"
        "      transition_bindings: ${{ needs.publisher-binding.outputs.transition_bindings }}\n",
        "publisher source admission retains frozen binding",
    )
    publish_head, publish_steps = _publication_steps(
        jobs["publish"], ("publisher-resolve", "publisher-start", "prepublish", "preindex", "seal"),
        "source-admission",
    )
    # Account for the original validators' network operations through the
    # transition reader. These adapters call the unchanged implementations;
    # only the Python entry point and operation selector differ.
    for name, operation in (
        ("Securely download and extract provisional conformance evidence", "download"),
        ("Securely download and extract provisional amd64 evidence", "download"),
        ("Securely download and extract provisional arm64 evidence", "download"),
        ("Rebuild authoritative conformance claims with trusted policy", "stage-conformance"),
    ):
        index = _named_step(publish_steps, name)
        publish_steps[index] = _replace(
            publish_steps[index],
            "          .publication-policy/conformance/evidence_publication_policy.py\n"
            f"          {operation}\n",
            f"          .publication-policy/{PUBLICATION}\n"
            f"          --operation {operation}\n"
            "          --phase publisher-start\n", "count unchanged substantive validator requests",
        )
    for architecture in ("amd64", "arm64"):
        index = _named_step(
            publish_steps,
            f"Download authoritative {architecture} evidence by publisher artifact ID",
        )
        publish_steps[index] = _download_step(
            publish_steps[index], f"native-verifier-{architecture}",
            f"${{{{ steps.upload-native-{architecture}.outputs.artifact-id }}}}",
            f"${{{{ steps.upload-native-{architecture}.outputs.artifact-digest }}}}",
            f"${{{{ runner.temp }}}}/ofarm-authoritative-input/{architecture}",
            "publisher-start",
        )
    publish_head = _replace(
        publish_head,
        "    concurrency:\n"
        "      group: ${{ needs.source-admission.outputs.publication_concurrency_group }}\n"
        "      cancel-in-progress: true\n", "",
        "use one fixed PR concurrency group without self-cancellation",
    )
    artifact_steps = (
        "upload-review-baseline", "upload-platform-evidence", "upload-native-amd64",
        "upload-native-arm64", "upload-native-index",
    )
    outputs = "    outputs:\n" + "".join(
        f"      {step}-{field}: ${{{{ steps.{step}.outputs.artifact-{field} }}}}\n"
        for step in artifact_steps for field in ("id", "digest")
    )
    publish_head = _replace(publish_head, "    steps:\n", outputs + "    steps:\n",
                            "typed artifact outputs for fresh seal")
    seal_index = _named_step(publish_steps, "Create the exact authoritative artifact candidate")
    seal_steps = publish_steps[seal_index:]
    publish_steps = publish_steps[:seal_index]
    for step in artifact_steps:
        for field in ("id", "digest"):
            seal_steps[0] = _replace(
                seal_steps[0], f"steps.{step}.outputs.artifact-{field}",
                f"needs.publish.outputs.{step}-{field}",
                "fresh seal consumes typed artifact identity",
            )
    receipt_index = _named_step(seal_steps, "Seal live source and publisher artifact identities")
    seal_steps[receipt_index] = _replace(seal_steps[receipt_index], "--operation publish\n",
                                         "--operation seal\n", "distinct receipt sealing")
    seal_steps[receipt_index] = _replace(
        seal_steps[receipt_index], "evidence-publication-receipt.json", RECEIPT_FILE,
        "transition receipt filename",
    )
    upload_index = _named_step(seal_steps, "Upload authoritative evidence publication receipt last")
    seal_steps[upload_index] = _replace(
        seal_steps[upload_index], "name: evidence-publication-receipt\n",
        f"name: {RECEIPT_NAME}\n", "distinct receipt artifact",
    )
    seal_steps[upload_index] = _replace(
        seal_steps[upload_index], "evidence-publication-receipt.json", RECEIPT_FILE,
        "transition receipt upload filename",
    )
    # Copy only T setup, source resolution and the digest-first ticket download.
    # The seal operation owns fresh live/source-job proof at entry and again
    # before writing the receipt. Copied publisher comparisons are neither
    # authority nor a third live check in the bounded seal pool.
    setup_end = _named_step(publish_steps, "Securely download and extract provisional conformance evidence")
    setup_steps = publish_steps[:setup_end]
    for name in ("Recheck live admission before validation",
                 "Bind the publisher to the authenticated source job"):
        setup_steps.pop(_named_step(setup_steps, name))
    seal_steps.pop(_named_step(seal_steps, "Bind successful publication to unchanged live admission"))
    seal_setup = "".join(setup_steps)
    seal_setup = _replace(seal_setup, "--phase publisher-resolve\n",
                          "--phase seal-resolve\n", "fresh seal source resolution")
    seal_setup = _replace(seal_setup, "--phase publisher-start\n",
                          "--phase seal-start\n", "fresh seal digest-first ticket download")
    seal_head = '''  publication-seal:
    name: seal transition publication on a fresh trusted runner
    needs: [source-admission, publish, publisher-guard]
    if: >-
      always() &&
      needs.source-admission.result == 'success' &&
      needs.publish.result == 'success' &&
      needs.publisher-guard.result == 'success'
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    permissions:
      actions: read
      contents: read
      issues: read
      pull-requests: read
    steps:
'''
    binding = _isolated_prefix(
        "publisher-binding", "bind the one publisher attempt", "[]", "true", 5,
    )
    binding = _replace(
        binding, "    steps:\n",
        "    outputs:\n"
        "      eligible: ${{ steps.transition-check.outputs.eligible }}\n"
        "      transition_grant: ${{ steps.transition-check.outputs.transition_grant }}\n"
        "      transition_bindings: ${{ steps.transition-check.outputs.transition_bindings }}\n"
        "    steps:\n", "publisher binding output",
    )
    binding += _transition_step("publisher-gate", "admit", ".transition-policy") + "\n"
    guard = _guard("publisher-guard", "source-admission",
                   "needs.source-admission.outputs.publish == 'true'", 60)
    return (
        _publication_header(prefix, consumer) + binding
        + admission_head + "".join(admission_steps)
        + publish_head + "".join(publish_steps).rstrip() + "\n\n"
        + guard + seal_head + seal_setup + "".join(seal_steps)
    )


def _tool_assets(policy_root: Path | None = None) -> dict[str, bytes]:
    # An external inspector may already have authenticated a distinct immutable
    # T checkout. Its exact files must supply the literal bootstrap, rather
    # than mutable bytes beside the inspector's imported Python module.
    directory = Path(__file__).resolve().parent if policy_root is None else policy_root / "conformance"
    return {
        "tools.py": (directory / "ci_policy_transition_tools.py").read_bytes(),
        "node.cjs": (directory / "ci_policy_transition_node.cjs").read_bytes(),
        "execution.py": (directory / "ci_policy_transition_execution.py").read_bytes(),
        "gh_relay.py": (directory / "ci_policy_transition_gh_relay.py").read_bytes(),
        "curl.py": (directory / "ci_policy_transition_curl.py").read_bytes(),
    }


def _tool_environment(job: str, assets: dict[str, bytes], *, node: bool) -> str:
    result = (
        f"          OFARM_TRANSITION_TOOLS_DIRECTORY: {CONTROL}\n"
        f"          OFARM_TRANSITION_TOOLS_SUPERVISOR: {CONTROL}/tools.py\n"
        f"          OFARM_TRANSITION_TOOLS_JOB: {TOOLS_JOBS[job]}\n"
    )
    if node:
        result += (
            f"          NODE_OPTIONS: --require={CONTROL}/node.cjs\n"
            "          OFARM_TRANSITION_NODE_SHA256: "
            + hashlib.sha256(assets["node.cjs"]).hexdigest() + "\n"
            "          OFARM_TRANSITION_TOOLS_SHA256: "
            + hashlib.sha256(assets["tools.py"]).hexdigest() + "\n"
        )
    else:
        result += '          NODE_OPTIONS: ""\n'
    # Workflow mapping keys are case-insensitive. The literal bootstrap clears
    # the four lowercase proxy names through the runner's environment file.
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'NODE_PATH',
                'NODE_EXTRA_CA_CERTS', 'NODE_TLS_REJECT_UNAUTHORIZED', 'SSL_CERT_FILE', 'SSL_CERT_DIR',
                'GIT_SSL_CAINFO', 'GIT_SSL_CAPATH', 'GIT_SSL_NO_VERIFY'):
        result += f'          {key}: ""\n'
    return result


def _bootstrap(job: str, assets: dict[str, bytes]) -> str:
    # The workflow contains the full trusted source before any checkout. The
    # local Action lives outside GITHUB_WORKSPACE because checkout cleans it;
    # runner post execution reloads action.yml, then runs posts in reverse order.
    encoded = {name: base64.b64encode(zlib.compress(value, 9)).decode("ascii")
               for name, value in assets.items()}
    if any(len(value) > 32768 for value in encoded.values()):
        raise WorkflowParityError("literal bootstrap environment exceeds bounded size")
    asset_keys = {"tools.py": "OFARM_BOOTSTRAP_TOOLS", "node.cjs": "OFARM_BOOTSTRAP_NODE",
                  "execution.py": "OFARM_BOOTSTRAP_EXECUTION", "gh_relay.py": "OFARM_BOOTSTRAP_GH_RELAY",
                  "curl.py": "OFARM_BOOTSTRAP_CURL"}
    asset_env = {name: key.replace("BOOTSTRAP", "TRANSITION") + "_SHA256"
                 for name, key in asset_keys.items()}
    digests = {name: hashlib.sha256(value).hexdigest() for name, value in assets.items()}
    local_script = """'use strict';
const cp = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const crypto = require('node:crypto');
const directory = path.resolve(__dirname, '../ofarm-ci-transition-control');
const helper = path.join(directory, 'tools.py');
const expected = TOOLS_DIGEST;
const env = {PATH:'/usr/bin:/bin', HOME:directory, LANG:'C.UTF-8',
  OFARM_TRANSITION_TOOLS_DIRECTORY:directory,
  OFARM_TRANSITION_TOOLS_SUPERVISOR:helper,
  OFARM_TRANSITION_TOOLS_NONCE:process.env.OFARM_TRANSITION_TOOLS_NONCE,
  OFARM_TRANSITION_TOOLS_JOB:process.env.OFARM_TRANSITION_TOOLS_JOB};
let success = false;
try {
  if (fs.realpathSync(directory) !== directory ||
      crypto.createHash('sha256').update(fs.readFileSync(helper)).digest('hex') !== expected) throw new Error();
  const result = cp.spawnSync('/usr/bin/python3', ['-I', '-S', helper, OPERATION],
    {env, stdio:'inherit', timeout:OPERATION === 'finish' ? 60000 : 30000});
  success = result.status === 0 && !result.error && !result.signal;
} catch {}
let cleanup = true;
if (OPERATION === 'finish') {
  try {
    const stat = fs.lstatSync(__dirname);
    const names = ['action.yml', 'main.cjs', 'post.cjs'];
    if (fs.realpathSync(__dirname) !== __dirname || !stat.isDirectory() ||
        stat.uid !== process.getuid() || (stat.mode & 0o777) !== 0o700 ||
        JSON.stringify(fs.readdirSync(__dirname).sort()) !== JSON.stringify(names)) throw new Error();
    for (const name of names) {
      const item = fs.lstatSync(path.join(__dirname, name));
      if (!item.isFile() || item.isSymbolicLink() || item.nlink !== 1 ||
          item.uid !== process.getuid() || (item.mode & 0o777) !== 0o600) throw new Error();
    }
    for (const name of names) fs.unlinkSync(path.join(__dirname, name));
    fs.rmdirSync(__dirname);
  } catch { cleanup = false; }
}
process.exit(success && cleanup ? 0 : 86);
""".replace("TOOLS_DIGEST", json.dumps(digests["tools.py"]))
    action_files = {
        "action.yml": "name: T-owned transition tool disposition\n"
        "description: Register authenticated final cleanup after all Action posts\n"
        "runs:\n  using: node24\n  main: main.cjs\n  post: post.cjs\n  post-if: always()\n",
        "main.cjs": local_script.replace("OPERATION", "'check'"),
        "post.cjs": local_script.replace("OPERATION", "'finish'"),
    }
    script = f'''import base64, hashlib, os, pathlib, shutil, subprocess, zlib
root = pathlib.Path(os.environ["RUNNER_TEMP"])
workspace = pathlib.Path(os.environ["GITHUB_WORKSPACE"])
assert root.is_absolute() and str(root.resolve()) == str(root)
action = root / "ofarm-ci-transition-action"
control = root / "ofarm-ci-transition-control"
assert (workspace / "../../_temp/ofarm-ci-transition-action").resolve() == action
created = []
start_attempted = False
try:
    for directory in (control, action):
        directory.mkdir(mode=0o700)
        created.append(directory)
    assets = {{name: os.environ[key] for name, key in {asset_keys!r}.items()}}
    digests = {digests!r}
    for name, encoded in assets.items():
        data = zlib.decompress(base64.b64decode(encoded, validate=True))
        assert hashlib.sha256(data).hexdigest() == digests[name]
        target = control / name
        target.write_bytes(data)
        target.chmod(0o600)
    for name, content in {action_files!r}.items():
        target = action / name
        target.write_text(content)
        target.chmod(0o600)
    environment = {{"PATH": "/usr/bin:/bin", "HOME": str(control), "LANG": "C.UTF-8"}}
    environment.update({{key: digests[name] for name, key in {asset_env!r}.items()}})
    # Linux environment keys are case-sensitive, unlike workflow YAML keys.
    # Publish fixed empty values before starting any process or Action posts.
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as output:
        output.write("http_proxy=\\nhttps_proxy=\\nall_proxy=\\nno_proxy=\\n")
        output.flush()
    start_attempted = True
    subprocess.run(["/usr/bin/python3", "-I", "-S", str(control / "tools.py"), "start",
        "--directory", str(control), "--job", os.environ["TRANSITION_TOOLS_JOB"],
        "--run-id", os.environ["GITHUB_RUN_ID"], "--run-attempt", os.environ["GITHUB_RUN_ATTEMPT"],
        "--root-sha", os.environ["GITHUB_WORKFLOW_SHA"], "--github-env", os.environ["GITHUB_ENV"]],
        env=environment, check=True, timeout=30)
except BaseException:
    cleanup_safe = not start_attempted
    if start_attempted:
        try:
            subprocess.run(["/usr/bin/python3", "-I", "-S", str(control / "tools.py"),
                "cleanup-start", "--directory", str(control)], env=environment,
                check=True, timeout=15)
            cleanup_safe = True
        except BaseException:
            pass
    for directory in reversed(created):
        if directory != control or cleanup_safe:
            shutil.rmtree(directory)
    raise
'''
    # One literal Python script: no checkout, candidate path, loader or artifact
    # participates in selecting these trusted bytes.
    body = "\n".join("          " + line for line in script.splitlines())
    if len(body) > 20000:
        raise WorkflowParityError("bootstrap exceeds GitHub run command limit")
    literal_environment = "".join(f"          {asset_keys[name]}: {value}\n"
                                  for name, value in encoded.items())
    return (
        "      - name: Start trusted transition tool observation before checkout\n"
        "        env:\n"
        f"          TRANSITION_TOOLS_JOB: {TOOLS_JOBS[job]}\n"
        + literal_environment
        + "        run: |\n"
        "          /usr/bin/python3 -I -S - <<'OFARM_TRANSITION_BOOTSTRAP'\n"
        + body + "\n          OFARM_TRANSITION_BOOTSTRAP\n"
        "      - name: Register final transition cleanup after Action posts\n"
        f"        uses: {LOCAL_ACTION}\n"
        "        env:\n" + _tool_environment(job, assets, node=False)
    )


def _observe_tools(text: str, assets: dict[str, bytes]) -> str:
    body = text.split("\njobs:\n", 1)[1]
    names = tuple(match.group(1) for match in _JOB.finditer(body))
    prefix, jobs = _jobs(text, names)
    for job, value in jobs.items():
        head, steps = _steps(value)
        observed = []
        for step in steps:
            name = step.splitlines()[0].removeprefix("      - name: ")
            if (job, name) in CURL_STEPS:
                download, identifier = CURL_STEPS[(job, name)]
                observed.append(_lifecycle(job, assets, f"Start protected curl observation for {download}",
                                           f'curl-start --name "{download}" --github-output "$GITHUB_OUTPUT"',
                                           identifier=identifier))
                step = _step_environment(step, _tool_environment(job, assets, node=False)
                                         + f"          CURL_HOME: ${{{{ steps.{identifier}.outputs.CURL_HOME }}}}\n")
            if job == "conformance" and name == GH_STEP:
                selected = "".join(f"          {key}: ${{{{ steps.transition-gh.outputs.{key} }}}}\n"
                                   for key in GH_ENVIRONMENT)
                step = _step_environment(step, _tool_environment(job, assets, node=False) + selected)
            if re.search(r"^        uses: |^      - uses: ", step, re.MULTILINE):
                if "        env:\n" in step:
                    step = _replace(step, "        env:\n", "        env:\n"
                                    + _tool_environment(job, assets, node=True), "typed Action observer selection")
                else:
                    first, rest = step.split("\n", 1)
                    if first.startswith("      - uses:"):
                        step = first + "\n        env:\n" + _tool_environment(job, assets, node=True) + rest
                    else:
                        step = _replace(step, "        uses: ", "        env:\n"
                                        + _tool_environment(job, assets, node=True) + "        uses: ",
                                        "typed named Action observer selection")
                if CHECKOUT in step and "execution_merge_sha" not in step and "fetch-depth:" not in step:
                    step = _replace(step, "        with:\n", "        with:\n          fetch-depth: 0\n",
                                    "T policy closure requires base tree")
            observed.append(step)
            if (job, name) in CURL_STEPS:
                download, _ = CURL_STEPS[(job, name)]
                observed.append(_lifecycle(job, assets, f"Finish protected curl observation for {download}",
                                           "curl-finish", always=True))
            if job == "conformance" and name == "Recheck live admission before conformance":
                observed.append(_lifecycle(job, assets, "Freeze protected gh policy from authenticated T",
                                           'gh-start --policy-root "$GITHUB_WORKSPACE/.baseline-admission-policy" '
                                           '--github-output "$GITHUB_OUTPUT"', identifier="transition-gh", token=True))
            if job == "conformance" and name == GH_STEP:
                observed.append(_lifecycle(job, assets, "Finish protected gh observation", "gh-finish", always=True))
        final = (
            "      - name: Require decisive transition tool completion\n"
            "        if: always()\n"
            "        env:\n" + _tool_environment(job, assets, node=False)
            + "        run: >-\n"
            "          /usr/bin/python3 -I -S \"${RUNNER_TEMP}/ofarm-ci-transition-control/tools.py\" check\n"
        )
        jobs[job] = head + _bootstrap(job, assets) + "".join(observed).rstrip() + "\n" + final + "\n"
    return (prefix + "".join(jobs.values())).rstrip("\n") + "\n"


def _step_environment(step: str, environment: str) -> str:
    if "        env:\n" in step:
        return _replace(step, "        env:\n", "        env:\n" + environment,
                        "typed protected tool environment")
    if "        run:" not in step:
        raise WorkflowParityError("protected tool step lacks canonical command")
    return _replace(step, "        run:", "        env:\n" + environment + "        run:",
                    "typed protected tool environment")


def _lifecycle(job: str, assets: dict[str, bytes], name: str, command: str, *,
               identifier: str | None = None, always: bool = False, token: bool = False) -> str:
    result = f"      - name: {name}\n"
    if identifier:
        result += f"        id: {identifier}\n"
    if always:
        result += "        if: always()\n"
    result += "        env:\n" + _tool_environment(job, assets, node=False)
    if token:
        result += "          GH_TOKEN: ${{ github.token }}\n"
    return result + "        run: >-\n" + (
        f'          /usr/bin/python3 -I -S "${{RUNNER_TEMP}}/ofarm-ci-transition-control/tools.py" {command}\n'
    )


def generate(source: bytes, publication: bytes, *, consumer_pr: int,
             policy_root: Path | None = None) -> GeneratedWorkflows:
    if type(consumer_pr) is not int or consumer_pr not in (413, 411):
        raise WorkflowParityError("consumer must be exactly PR 413 or PR 411")
    source_text = _authenticate_input(SOURCE_INPUT, source)
    publication_text = _authenticate_input(PUBLICATION_INPUT, publication)
    assets = _tool_assets(policy_root)
    generated_publication = _observe_tools(_publication(publication_text, consumer_pr), assets).encode("utf-8")
    source_output = _source(
        source_text, consumer_pr, hashlib.sha256(generated_publication).hexdigest(),
    )
    source_output = _replace(source_output, "--tlsv1.2 --retry 3 --output", "--tlsv1.2 --retry 0 --output",
                             "four downloads: conformance two plus native matrix two", count=3)
    generated_source = _observe_tools(source_output, assets).encode("utf-8")
    return GeneratedWorkflows(generated_source, generated_publication, (
        "exact transition workflow names, push ref filters, and fixed consumer concurrency",
        "T-only policy checkout and transition admission/recheck invocations",
        "conformance timeout 45 to 60; native120 and publisher45 unchanged",
        "isolated source135 and publisher60 guards; only guards receive actions:write",
        "fresh guarded handoff10 and distinct versioned transition ticket",
        "fresh guarded seal10 and distinct versioned transition receipt",
        "typed published artifact identities passed to the fresh seal",
        "ticket and two published native downloads use the unchanged digest-first safe extractor",
        "three provisional downloads and source-reader CLI use counted unchanged substantive validators",
        "literal T-owned tools and Node bootstrap before every first checkout; local Action post cleanup last",
        "typed observer environment on every retained pinned Action; decisive always completion check",
        "T-only policy checkouts use depth0 for authenticated B/T closure; candidate checkout unchanged",
        "exactly four curl dependency invocations retry3 to retry0 (three textual anchors, native matrix twice)",
        "private curl and gh lifecycles with typed output environment selected only on protected canonical steps",
        "seal operation owns entry and preupload proof; three redundant copied publisher steps removed",
    ))


def check_parity(source: bytes, publication: bytes, generated_source: bytes,
                 generated_publication: bytes, *, consumer_pr: int,
                 policy_root: Path | None = None) -> GeneratedWorkflows:
    expected = generate(source, publication, consumer_pr=consumer_pr, policy_root=policy_root)
    for name, actual, wanted in (
        (SOURCE_OUTPUT, generated_source, expected.source),
        (PUBLICATION_OUTPUT, generated_publication, expected.publication),
    ):
        if actual != wanted:
            raise WorkflowParityError(f"{name}: generated workflow parity differs")
    return expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("generate", "check"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--consumer-pr", type=int, required=True, choices=(413, 411))
    args = parser.parse_args(argv)
    try:
        source = (args.root / SOURCE_INPUT).read_bytes()
        publication = (args.root / PUBLICATION_INPUT).read_bytes()
        result = generate(source, publication, consumer_pr=args.consumer_pr)
        if args.operation == "generate":
            (args.root / SOURCE_OUTPUT).write_bytes(result.source)
            (args.root / PUBLICATION_OUTPUT).write_bytes(result.publication)
        else:
            check_parity(source, publication, (args.root / SOURCE_OUTPUT).read_bytes(),
                         (args.root / PUBLICATION_OUTPUT).read_bytes(),
                         consumer_pr=args.consumer_pr)
        print(f"transition workflow {args.operation}: exact parity for PR {args.consumer_pr}")
        return 0
    except (OSError, UnicodeError, WorkflowParityError) as exc:
        print(f"transition workflow refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
