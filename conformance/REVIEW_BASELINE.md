# Deterministic Kernel review baseline

This is the evidence-only baseline for issue #168. It changes no Kernel
runtime behavior, contract, law, manifest content, activation input, or
capability claim.

## Pinned environment

The authoritative baseline target is GitHub Actions on `ubuntu-24.04`, x86_64,
with CPython 3.12.13 and PostgreSQL 17.10. The service image and every action
are pinned by digest or commit SHA in `.github/workflows/conformance.yml`.
The prior hosted-runner image build number is recorded for provenance, but
GitHub does not expose a selector for that hosted image build; the workflow
pins the available `ubuntu-24.04` runner label and records the actual image
version in every new envelope.
`requirements-review-baseline.lock` contains the 30 direct and transitive
Linux wheel versions observed in green run 28176813292, with the exact selected
wheel hashes. It does not upgrade that resolution.

The old run did not record its pip patch version. `pip==26.1` is therefore a
new, explicit first-rerun pin in `requirements-review-pip.lock`, not a claim
about the historical run. Every new envelope records the exact observed pip
version. CI creates a dedicated `.review-venv`, installs both locks with
`--require-hashes --only-binary=:all: --no-deps`, runs `pip check`, and rejects
any installed distribution that is missing, mismatched, or extra.

## One complete command

In the pinned environment, with `OFARM_PG_DSN` and `OFARM_PG_ADMIN_DSN` set,
one complete Kernel run is:

```bash
.review-venv/bin/python conformance/run_review_baseline.py run \
  --output-dir .artifacts/review-baseline/run
```

The command always uses the full unfiltered `kernel/tests` root. It therefore
includes the database integration suites, concurrent-writer/race checks,
hostile regression cases, malformed-input and fail-closed cases, profile
engineering bridges, and unit tests. No `-k`, marker, or ambient pytest option
can narrow the selection. `PYTEST_ADDOPTS`, `PYTEST_PLUGINS`, `PYTHONPATH`, and
ambient `OFARM_*` values are scrubbed; only the two explicit database DSNs are
carried forward. Plugin autoload is disabled, and hash seed, time zone, and
locale are fixed.

The runner emits `kernel-test-results.json` and
`review-baseline-evidence.json`. The pytest report records:

- every collected and selected node ID;
- every deselected test;
- each callable's real source module and source path, including tests collected
  through root star-import bridges;
- setup, call, and teardown outcomes;
- pass, fail, error, skip, xfail, xpass, collection-error, and unavailable
  counts and inventories; and
- warnings without absolute environment paths or durations.

If the database or an exact tool/dependency pin is unavailable, the command
still performs collection and emits an honest inventory. It marks the selected
tests unavailable and exits non-zero. CI accepts only a full run: no skips,
deselections, unavailable tests, xfails, xpasses, errors, or collection errors.

The envelope also records Git SHA and full dirty-state detection, config and
lock digests, the SQL-observed PostgreSQL server version, Python and pip
versions, the exact installed-set digest, schema digest, all test outcomes, step
outcomes, and produced/verified artifact digests.

## Clean-run equivalence

CI runs the complete command twice in fresh subprocesses and compares the two
envelopes:

```bash
.review-venv/bin/python conformance/run_review_baseline.py compare \
  .artifacts/review-baseline/run-1/review-baseline-evidence.json \
  .artifacts/review-baseline/run-2/review-baseline-evidence.json \
  --output .artifacts/review-baseline/equivalence.json
```

The comparator refuses dirty or failing runs. Its fixed v1 policy removes only
these four volatile JSON pointers:

- `/run/startedAt`
- `/run/finishedAt`
- `/environment/ci/runId`
- `/environment/ci/runAttempt`

The policy cannot be broadened by an input envelope. Test inventories,
outcomes, warnings, Git state, versions, schema and lock digests, installed-set
digest, and produced artifact digests all remain comparison inputs. The proof
records raw and normalized envelope SHA-256 digests.

## Existing platform evidence lane

The historical platform-MVP writer remains narrower and duration-bearing: it
records 23 root conformance call phases and structured runtime details. It is
not used for deterministic equivalence. After the two complete baseline runs,
CI runs `kernel/tests/test_conformance.py` separately and redirects that legacy
JSON into `.artifacts/platform-evidence/`, so no timestamped evidence pollutes
the worktree and no historical evidence directory is uploaded by accident.
