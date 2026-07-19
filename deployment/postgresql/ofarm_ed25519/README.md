# `ofarm_ed25519` verification-only PostgreSQL extension

This directory is the reviewed source boundary for ADR 0003. It exposes one
verification function and contains no signer, key generator, secret storage,
file/network selector, or generic cryptographic API.

The production image must be built from `Containerfile` and pinned by its
resulting OCI manifest and child digests. Merely compiling this directory, or
passing its unit tests, is not deployment or production evidence. The live HSM
known-answer vector and multi-platform artifact evidence are collected by the
separate deployment/#172 process.

