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
`requirements-review-baseline.lock` contains 48 direct and transitive Linux
wheel versions with exact selected wheel hashes. Thirty were observed in green
run 28176813292. #172 adds the maintained PyJWT verifier, Google Cloud KMS
client, and their complete explicitly selected, hash-verified dependency set;
the next clean CI run will be their first baseline observation.

The old run did not record its pip patch version. `pip==26.1` is therefore a
new, explicit first-rerun pin in `requirements-review-pip.lock`, not a claim
about the historical run. Every new envelope records the exact observed pip
version. CI creates a dedicated `.review-venv`, installs both locks with
`--require-hashes --only-binary=:all: --no-deps`, runs `pip check`, and rejects
any installed distribution that is missing, mismatched, or extra.
The interpreter optimization level is pinned to zero. An optimized parent
process fails preflight, and `PYTHONOPTIMIZE` is removed from every child
environment so imported profile-test assertions cannot be stripped.

## One complete command

In the pinned environment, set `OFARM_PG_ADMIN_DSN`,
`OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN`, and
`OFARM_SECURITY_AUDIT_PG_ADMIN_DSN` to three independent PostgreSQL 17
clusters. The runner derives the fixed `ofarm_kernel_test` Store DSN from the
primary verified connection route, so an independently supplied test DSN
cannot point tests at another server. One complete Kernel run is:

```bash
.review-venv/bin/python conformance/run_review_baseline.py run \
  --output-dir .artifacts/review-baseline/run
```

The command always uses the full unfiltered `kernel/tests` root. It therefore
includes the database integration suites, concurrent-writer/race checks,
hostile regression cases, malformed-input and fail-closed cases, profile
engineering bridges, and unit tests. No `-k`, marker, or ambient pytest option
can narrow the selection. `PYTEST_ADDOPTS`, `PYTEST_PLUGINS`,
`PYTHONOPTIMIZE`, `PYTHONPATH`, and ambient `OFARM_*` values are scrubbed;
only the three explicit admin DSNs are accepted, and the Store DSN is derived
from the primary one.
Plugin autoload is disabled, and hash seed, time zone, locale, and optimization
level are fixed.

The runner emits `kernel-test-results.json` and
`review-baseline-evidence.json`. The pytest report records:

- every collected and selected node ID;
- every deselected test;
- every module-level collection skip, including collector and reason;
- each callable's real source module and source path, including tests collected
  through root star-import bridges;
- setup, call, and teardown outcomes;
- pass, fail, error, skip, xfail, xpass, collection-error, and unavailable
  counts and inventories; and
- a multiplicity-preserving warning inventory without absolute environment
  paths or durations.

If the database or an exact tool/dependency pin is unavailable, the command
still performs collection and emits an honest inventory. It marks the selected
tests unavailable and exits non-zero. CI accepts only a full run: no item or
module-level collection skips, deselections, unavailable tests, xfails,
xpasses, errors, or collection errors. The warning list must exactly match the
committed four-field warning inventory.

`conformance/review_baseline_test_inventory.json` pins every expected
`nodeid`, original `sourceModule`, and original `sourcePath`. Every run must
match that full inventory. Deleting, ignoring, adding, renaming, or changing
the source attribution of a test fails even when two current runs drift in the
same way. Intentional suite changes require the explicit maintenance command:

```bash
.review-venv/bin/python conformance/run_review_baseline.py update-inventory
```

The generated inventory diff must be reviewed and committed with the test
change. CI never updates this file automatically.

The envelope records complete Git state both before and after executable
steps; both samples must be clean and byte-identical in commit, tree, and
status digest. It also records config, lock and pinned-test-inventory digests,
the SQL-observed admin and derived test-store PostgreSQL identities, Python,
pip and optimization levels, the exact installed-set digest, schema digest,
all test outcomes, step outcomes, and produced/verified artifact digests.

## Clean-run equivalence

CI runs the complete command twice in fresh subprocesses and compares the two
envelopes:

```bash
.review-venv/bin/python conformance/run_review_baseline.py compare \
  .artifacts/review-baseline/run-1/review-baseline-evidence.json \
  .artifacts/review-baseline/run-2/review-baseline-evidence.json \
  --output .artifacts/review-baseline/equivalence.json
```

The comparator refuses dirty, mutated, or failing runs. Its fixed v2 policy
removes only these four volatile JSON pointers:

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
