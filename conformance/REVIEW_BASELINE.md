# Deterministic Kernel review baseline

This is the evidence-only baseline for issue #168. It changes no Kernel
runtime behavior, contract, law, manifest content, activation input, or
capability claim.

## Pinned environment

The authoritative baseline target is GitHub Actions on `ubuntu-24.04`, x86_64,
with CPython 3.12.13 and PostgreSQL 17.10. The complete Python Bookworm image,
PostgreSQL service image, and every action are pinned by digest or commit SHA
in `.github/workflows/conformance.yml`. The Python image root is read-only and
`/tmp` is a writable `noexec` tmpfs. The retained OCI index selects one exact
linux/amd64 manifest; `conformance/python_runtime_image_manifest.json` is
generated directly from its verified compressed layers and uncompressed diff
IDs, including OCI whiteout semantics.
The manifest closes the standard/native runtime set: exact executable, complete
stdlib tree and directories, libpython and image DSOs, loader configuration,
required absence of `/etc/ld.so.preload`, and the Git executable used by the
evidence runner. The launcher compares the live tree with those bytes and
requires the image paths to be on a read-only filesystem before it exposes
locked wheels or project code. Every actually executable file mapping is then
attributed to that image manifest or a retained locked wheel.

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
`--no-compile --require-hashes --only-binary=:all: --no-deps`, removes seed
bytecode, and runs `pip check`. The exact locked wheel archives remain under
`.review-venv/.ofarm-wheelhouse`; the isolated launcher verifies each archive
against the reviewed requirement hash and compares every installed import-root
file directly with its wheel member. Mutable installed `RECORD` metadata is not
an integrity authority. Extra wheels, distributions, files, directories, data,
startup customization, or importable content are refused.

The following environment commands are valid only inside that pinned image.
A host Python with the same version string is not a live-runtime substitute:

```bash
python -m venv .review-venv
mkdir -p .review-venv/.ofarm-wheelhouse
.review-venv/bin/python -m pip download --require-hashes --only-binary=:all: \
  --no-deps --dest .review-venv/.ofarm-wheelhouse \
  --requirement requirements-review-pip.lock
.review-venv/bin/python -m pip install --no-compile --no-index \
  --find-links .review-venv/.ofarm-wheelhouse --require-hashes \
  --only-binary=:all: --no-deps --requirement requirements-review-pip.lock
.review-venv/bin/python -m pip download --require-hashes --only-binary=:all: \
  --no-deps --dest .review-venv/.ofarm-wheelhouse \
  --requirement requirements-review-baseline.lock
.review-venv/bin/python -m pip install --no-compile --no-index \
  --find-links .review-venv/.ofarm-wheelhouse --require-hashes \
  --only-binary=:all: --no-deps --requirement requirements-review-baseline.lock
.review-venv/bin/python -m pip check
find .review-venv -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
find .review-venv -depth -type d -name __pycache__ -empty -delete
```
The interpreter optimization level is pinned to zero. An optimized parent
process fails preflight, and `PYTHONOPTIMIZE` is removed from every child
environment so imported profile-test assertions cannot be stripped.

## One complete command

In the pinned environment, set only `OFARM_PG_ADMIN_DSN`. The runner derives
the fixed `ofarm_kernel_test` Store DSN from that verified connection route,
so an independently supplied test DSN cannot point tests at another server.
One complete Kernel run is:

```bash
.review-venv/bin/python -I -B -S tooling/ofarm_isolated.py \
  --venv-root .review-venv -m conformance.run_review_baseline run \
  --output-dir .artifacts/review-baseline/run
```

The command always uses the full unfiltered `kernel/tests` root. It therefore
includes the database integration suites, concurrent-writer/race checks,
hostile regression cases, malformed-input and fail-closed cases, profile
engineering bridges, and unit tests. No `-k`, marker, or ambient pytest option
can narrow the selection. `PYTEST_ADDOPTS`, `PYTEST_PLUGINS`,
`PYTHONOPTIMIZE`, `PYTHONPATH`, native `LD_*`/`DYLD_*` controls, and ambient
`OFARM_*` values are scrubbed;
only the explicit admin DSN is accepted, and the Store DSN is derived from it.
Plugin autoload is disabled, and time zone, locale, and optimization level are
fixed. Isolated mode intentionally ignores `PYTHONHASHSEED`; hash randomization
remains enabled and deterministic outputs use explicitly sorted canonical
encodings instead of relying on hash-table iteration order.
Pytest uses `--import-mode=importlib`, so collection does not reorder or add
entries to the launcher's verified `sys.path`.

`-I -B -S` is an executable trust boundary, not documentation shorthand. The
retained launcher refuses non-isolated flags, ambient Python path/home/startup
customization, native loader controls (even when empty),
`sitecustomize`/`usercustomize`, `.pth` files, and stale or unchecked bytecode
before it exposes project or dependency roots to imports. The normal absent
`python312.zip` candidate is removed rather than trusted as a future path, and
the pre-closure importer cache is cleared before the retained roots are used.
Runtime selection then seals the exact module/import-container and importer-
cache identities; activation and every governed transaction require zero
module, path, finder, loader, or mutable finder-state drift.

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
.review-venv/bin/python -I -B -S tooling/ofarm_isolated.py \
  --venv-root .review-venv -m conformance.run_review_baseline update-inventory
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

CI runs the complete command in a two-entry matrix. Each entry gets its own
hosted runner, checkout, locked virtual environment, and pinned PostgreSQL
service, so the two complete Kernel baselines run concurrently and neither
shares process or database state with the other. Each job uploads a separate
`review-baseline-run-1` or `review-baseline-run-2` artifact.

After both matrix entries pass, a separate equivalence job downloads those two
artifacts with the pinned `actions/download-artifact` action and compares the
envelopes:

```bash
.review-venv/bin/python -I -B -S tooling/ofarm_isolated.py \
  --venv-root .review-venv -m conformance.run_review_baseline compare \
  .artifacts/review-baseline/run-1/review-baseline-evidence.json \
  .artifacts/review-baseline/run-2/review-baseline-evidence.json \
  --output .artifacts/review-baseline/equivalence.json
```

The comparator refuses dirty, mutated, or failing runs. Its fixed v3 policy
removes only these six volatile JSON pointers:

- `/run/startedAt`
- `/run/finishedAt`
- `/environment/ci/runId`
- `/environment/ci/runAttempt`
- `/environment/postgresql/admin/systemIdentifier`
- `/environment/postgresql/testStore/systemIdentifier`

The last two values identify the independently created PostgreSQL service
clusters. They are removed only after the comparator proves, separately for
each raw envelope, that `sameServer` is exactly `true` and that the admin and
test-store identifiers are nonempty strings with the same value. A false
claim, missing identifier, or intra-envelope mismatch is refused before
normalization. The policy cannot be broadened by an input envelope.

Test inventories, outcomes, warnings, Git state, versions, schema and lock
digests, installed-set digest, and produced artifact digests all remain
comparison inputs. The separate run artifacts retain both raw PostgreSQL
identifiers, and the proof records each raw and normalized envelope SHA-256
digest. The equivalence job uploads the two raw run directories and proof
together under the established `review-baseline` artifact name.

## Existing platform evidence lane

The historical platform-MVP writer remains narrower and duration-bearing: it
records 23 root conformance call phases and structured runtime details. It is
not used for deterministic equivalence. CI runs
`kernel/tests/test_conformance.py` in an independent pinned job alongside the
two baseline matrix entries and redirects that legacy JSON into
`.artifacts/platform-evidence/`, so no timestamped evidence pollutes the
worktree and no historical evidence directory is uploaded by accident. A
small final `conformance` job preserves the established required-check name and
succeeds only when both the equivalence and platform-evidence jobs succeed.
