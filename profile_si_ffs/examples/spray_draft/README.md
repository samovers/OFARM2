# Local spray draft example

Enter a fictional spray record, save it offline, sync it to a local inbox,
inspect its checks, make a corrected copy and mark the draft as reviewed.
Originals are preserved. Temporary connection failures retry while the page
is running, including when the local server restarts.

This example belongs to the Slovenian plant protection record-keeping
profile. Review acknowledges a draft. The amounts and notes are fictional.
Live C4 stays unevaluated. Real approval and publication stay blocked.

## Separate execution prerequisite

The example uses a separate Python and verifier bundle for Apple silicon Macs.
The hashes below identify the existing local rehearsal bundle. They support
development checks while the Python package is under review. The final
connection and fresh-checkout test require the interface and hashes from
merged [PR #448](https://github.com/samovers/OFARM2/pull/448).

If you have the local rehearsal archive, verify it before unpacking or
running it. The SHA-256 of
`ofarm-draft-execution-darwin-arm64-20261119.tar.gz` must match the following value.

```text
bba90884d28e4ef6f15835d204fd68be5cd57a7fd06a6322e20d94af53970971
```

Unpack it in a directory you control and set its absolute location. Run these
commands from `profile_si_ffs/examples/spray_draft/`.

```sh
tar -xzf /absolute/path/to/ofarm-draft-execution-darwin-arm64-20261119.tar.gz -C /absolute/path/to/install-directory
export SPRAY_BUNDLE=/absolute/path/to/install-directory/ofarm-draft-execution-darwin-arm64-20261119
export SPRAY_DRAFT_VERIFIER="$SPRAY_BUNDLE/verifier"
export SPRAY_DRAFT_PYTHON="$SPRAY_BUNDLE/python/bin/python3.12"
PYTHONDONTWRITEBYTECODE=1 "$SPRAY_DRAFT_PYTHON" -B -I -S app.py --port 8766
```

The app pins candidate manifest
`d4325b754615e937a0f2d0f6ab5187e9e9f822e9299905cb796b3cd3870d76dc`
and execution selection
`aa28df23b8e1972e1a167abb3bcfa3e1132585a0fc7b21bf85c63d44ef75d23a`.
The location variable can find only those selected bytes. The execution bundle
owns path resolution and all dependency checks. Missing or changed setup fails;
there is no replacement checker or sample successful response.

Open `http://127.0.0.1:8766`. This separate port avoids sharing the original
rehearsal's browser storage. Keep the server and page open for automatic sync.
The browser must load the page online once before offline use. The server
listens only on loopback. Its local database and diagnostic reports are under
`.local/` and must not be committed. No saved user records are included here.

The five files under `fixtures/` are the fictional rehearsals for the original
form, operator details, water volume, job and amount rules. Each record selects
its own catalog by hash. The two job-format records use different catalogs.
Keep each old reader and catalog while a saved original or test fixture needs
the pair, unless a reviewed replacement reads the same bytes with the same
result.

## Checks

Use the same separate execution environment to run the checks.

```sh
PYTHONDONTWRITEBYTECODE=1 "$SPRAY_DRAFT_PYTHON" -B -I -S run_checks.py
npm ci --ignore-scripts
npx --no-install playwright install chromium
npm test
```

The browser checks require Node 20 or later. The Python runner executes all 70
existing checks and returns failure for a
skipped verifier check. The 45-case browser journey requires real verifier
reports where asserted and uses a disposable inbox and fresh browser storage.
It includes two distinct records, correction retention, offline recovery,
server restart, lost replies, storage failures and blocked approval routes.
Test output goes under ignored `.local/test-evidence/`. The Playwright version
is locked to the version used by the completed rehearsal.

The pre-merge rehearsal exercised the historical bundle on one Apple silicon
Mac. Final verification reruns these checks on the spray PR head with the
merged execution package and the old workstation paths inaccessible.

## PR boundary

The primary boundary is **draft capture and diagnostic presentation**. The PR
packages the existing behavior with mechanical source/test path changes. It
adds no feature, production handler, authentication, governed storage,
approval path, deployment, CI activation or generic C3 completion. Existing
repository schemas and the fictional builder are reused at their pinned
bytes. The external verifier implementation and its execution guard are
supplied by the separate execution bundle and are not copied into this example.

Next, verify this example against the merged execution package before
completing the spray draft delivery.
