# `ofarm_ed25519` verification-only PostgreSQL extension

This directory is the reviewed source boundary for ADR 0003. It exposes one
verification function and contains no signer, key generator, secret storage,
file/network selector, or generic cryptographic API.

The production image must be built from `Containerfile` and pinned by its
resulting OCI manifest and child digests. Merely compiling this directory, or
passing its unit tests, is not deployment or production evidence. This package's
hosted workflow collects the multi-platform artifact evidence; the live HSM
known-answer remains part of the separate #172 signer/deployment process.

`native_release_identity.json` is the checked release authority for this
directory. Before the first hosted two-platform build it is explicitly
`provisional` and carries no child or index digest. The hosted fan-in produces a
candidate containing the canonical amd64/arm64 index bytes, both child and
configuration digests, the four installed-artifact identities per platform,
the exact source inventory, build pins, and workflow-action pins. A later
reviewed commit freezes those bytes. Conformance refuses to call the derived
image frozen unless its Buildx metadata matches that checked identity exactly.

`native_evidence_receipt.json` is the separate checked, durable evidence record.
Its provisional form contains no build, platform, attestation, archive, or
preservation claim. The fan-in emits a candidate linked to the exact frozen
release-identity digest. For both platforms it records the source image-index,
attestation-manifest, SBOM, provenance, and OCI-archive digest and size, together
with the exact builder, Actions run, source commit, build pins, and evidence
authority source inventory. Actions artifacts are explicitly temporary inputs.
The durable archive location is a deterministic GitHub Release tag derived from
the release-identity digest, with one exact asset name and URL per platform.
Only archives downloaded back from those URLs and independently checked against
the candidate may promote the receipt from `candidate` to `frozen`.

The final verification command accepts the two independently downloaded Release
assets and writes the canonical frozen receipt; it refuses a wrong filename,
size, or digest:

```sh
python3 ../native_evidence.py finalize-evidence-receipt \
  --release-identity native_release_identity.json \
  --candidate-receipt native_evidence_receipt.candidate.json \
  --source-directory . --repository-root ../../.. \
  --amd64-download ofarm-ed25519-linux-amd64.oci.tar \
  --arm64-download ofarm-ed25519-linux-arm64.oci.tar \
  --output native_evidence_receipt.json
```

The build has a closed `linux/amd64`/`linux/arm64` input set. It uses pinned
Dockerfile-frontend, GCC-builder, and PostgreSQL-runtime manifest digests. The
matching PostgreSQL 17.10 server-development package is downloaded by exact
architecture-specific URL, size, and SHA-256; its package, version, and
architecture metadata are checked before it is extracted without installing a
package or updating a package index. Libsodium 1.0.22 is likewise selected by
one exact source-archive digest, built one job at a time, and linked privately.
After the three checksum-selected remote inputs have been fetched, every
Containerfile `RUN` executes with `--network=none`.

The checked download receipts are:

- PostgreSQL server development `amd64`: 1,338,208 bytes,
  SHA-256 `adc91a999ec840f8db8c8df5ac2473fe1deeaed0e76bd5a6391afa7c74bceac3`.
- PostgreSQL server development `arm64`: 1,327,764 bytes,
  SHA-256 `372c8eb77604bc9cba61689661701e65a336b14a43e8f9be850088bb8c4428b6`.
- Libsodium 1.0.22 source: 2,008,529 bytes,
  SHA-256 `adbdd8f16149e81ac6078a03aca6fc03b592b89ef7b5ed83841c086191be3349`.

Build the current host architecture from this directory:

```sh
docker build --build-arg SOURCE_DATE_EPOCH=0 \
  --file Containerfile --tag ofarm-ed25519:local .
```

Passing `SOURCE_DATE_EPOCH=0` as a build argument is mandatory. The same value
is also present in the build environment, but BuildKit only rewrites exported
image timestamps when the caller supplies the argument. The extension build
stages exactly three runtime files in a dedicated root, normalizes every file
and directory timestamp, and copies that root as one final layer. A clean-build
reproducibility check runs the command twice with `--no-cache` and compares the
image configuration, root-filesystem layer digests, and SHA-256 values for the
shared object, control file, and SQL file. BuildKit provenance attestations are
separate evidence objects and are not part of that byte comparison.

The dedicated sanitizer target accepts only `address` or `undefined`. Each
selection rebuilds the same pinned libsodium source with that sanitizer, runs
libsodium's own test suite, compiles and runs the shared verifier core and
standalone hostile-input harness, then builds an instrumented test-only copy of
the extension and loads that copy into the pinned PostgreSQL runtime. The live
SQL calls the wrapper with inline, compressed, and TOAST-backed values, so the
argument-size and detoast paths execute under the selected sanitizer:

```sh
docker build --file Containerfile --target sanitizer \
  --build-arg SOURCE_DATE_EPOCH=0 --build-arg SANITIZER=address .
docker build --file Containerfile --target sanitizer \
  --build-arg SOURCE_DATE_EPOCH=0 --build-arg SANITIZER=undefined .
```

The sanitizer-only libsodium build uses `--disable-asm`, and arm64 adds
`-mgeneral-regs-only`. This keeps all 101 upstream tests under the selected
compiler sanitizer and excludes optional architecture backends. In particular,
GCC's arm64 UBSan otherwise stops in the unrelated AES-GCM NEON backend when
upstream tests exercise unaligned output, before the Ed25519 harness can run.
The production build does not disable architecture backends; the extension's
Ed25519 verifier uses the same ref10 C path in both builds.

The separate `failure-semantics` target compiles seven test-only shared objects
with one fault fixed at compile time in each object. It proves that module
initialization failure, an unexpected verifier result, and detoast allocation
failure produce only SQLSTATE `58000` and the constant infrastructure message.
It also proves that cancellation, statement-timeout, transaction, and storage
errors raised at the same detoast boundary retain their original SQLSTATE and
message. There is no runtime fault selector, SQL test API, or extra export:

```sh
docker build --file Containerfile --target failure-semantics \
  --build-arg SOURCE_DATE_EPOCH=0 .
```

Neither the fault objects nor the instrumented sanitizer object is in the
ancestry or copy set of the default runtime stage.

`ofarm_ed25519_vectors.json` is the single checked adversarial-vector authority.
The generator validates its closed categories and renders the C header and SQL
fragment consumed by the standalone harness, deterministic C fuzzer, ordinary
live PostgreSQL test, and sanitizer-loaded PostgreSQL test. The generated files
carry the authority's SHA-256 and are checked without rewriting them:

```sh
python3 generate_ofarm_ed25519_vectors.py --check
```

The corpus covers the RFC 8032 empty-message vector, the fixed ADR 0003
preflight bytes, negative-zero encodings, the intentionally refused
identity-`R` valid-equation case, scalar boundaries, bit flips, every accepted
message length, and zero, identity, small-order, non-main-subgroup, and
noncanonical point encodings. The deterministic fuzz lanes add 16,384 direct-C
cases and 4,096 live-SQL cases from the same checked seeds and boundary arrays.
The harness allocates the exact length passed to the shared core so a sanitizer
observes the same byte-access boundary used by the PostgreSQL wrapper. These
tests contain deterministic test-only signing material; neither a harness,
fuzzer, generator, signing function, fault object, nor sanitizer object is
copied into the runtime image or exported by the extension.

The standard image build also starts its pinned PostgreSQL runtime and runs the
generated corpus. It exercises an ordinary four-byte varlena in all argument
positions, an admitted 8,192-byte compressed value through the detoast path,
and oversized one-megabyte values in both compressed and external-uncompressed
TOAST storage in all three positions. The wrapper asks PostgreSQL for each
datum's raw size before any detoast operation, refuses an oversized value, and
then retains exact post-detoast length checks for admitted values. This bounds
extension-triggered detoast allocation. The wrapper catches only errors from
its three owned detoast calls, maps only PostgreSQL's out-of-memory SQLSTATE to
the fixed verifier infrastructure failure, and rethrows every other PostgreSQL
`ErrorData` unchanged. Cancellation, timeout, transaction, and storage failures
therefore keep their native semantics.

GitHub Actions repeats the native build without emulation on the declared
amd64 and arm64 runners, runs both compiler sanitizers and live PostgreSQL,
compares two clean child/configuration and installed-artifact results, and then
authenticates a bounded OCI archive with SPDX SBOM and max BuildKit provenance.
The fan-in re-authenticates both archives before composing the canonical
two-platform index. These are implementation and conformance facts only; they
do not establish HSM availability, deployment authority, recovery continuity,
service readiness, or production readiness.
