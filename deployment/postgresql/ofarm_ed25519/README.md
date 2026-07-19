# `ofarm_ed25519` verification-only PostgreSQL extension

This directory is the reviewed source boundary for ADR 0003. It exposes one
verification function and contains no signer, key generator, secret storage,
file/network selector, or generic cryptographic API.

The production image must be built from `Containerfile` and pinned by its
resulting OCI manifest and child digests. Merely compiling this directory, or
passing its unit tests, is not deployment or production evidence. The live HSM
known-answer vector and multi-platform artifact evidence are collected by the
separate deployment/#172 process.

The build has a closed `linux/amd64`/`linux/arm64` input set. It uses pinned
Dockerfile-frontend, GCC-builder, and PostgreSQL-runtime manifest digests. The
matching PostgreSQL 17.10 server-development package is downloaded by exact
architecture-specific URL, size, and SHA-256; its package, version, and
architecture metadata are checked before it is extracted without installing a
package or updating a package index. Libsodium 1.0.22 is likewise selected by
one exact source-archive digest, built one job at a time, and linked privately.

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
libsodium's own test suite, then compiles and runs the shared verifier core and
standalone hostile-input harness:

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

The harness covers the RFC 8032 empty-message vector, the fixed ADR 0003
preflight bytes, every accepted message length, all length boundaries, bit
flips, noncanonical scalars, and zero, identity, small-order, non-main-subgroup,
and noncanonical point encodings. It allocates the exact length passed to the
shared core so a sanitizer observes the same byte-access boundary used by the
PostgreSQL wrapper. The harness contains deterministic test-only signing
material; neither it nor any signing function is copied into the runtime image
or exported by the extension.

The standard image build also starts its pinned PostgreSQL runtime, installs
the extension, forces a one-megabyte hostile value into compressed TOAST
storage, and passes that value in each SQL argument position. The wrapper asks
PostgreSQL for each datum's raw size before any detoast operation, refuses an
oversized value, and then retains exact post-detoast length checks for admitted
values. This bounds extension-triggered detoast allocation without catching or
rewriting PostgreSQL errors and interrupts.
