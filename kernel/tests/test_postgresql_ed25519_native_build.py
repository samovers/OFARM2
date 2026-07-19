"""Static closure checks for the #174 native Ed25519 build boundary."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXTENSION_ROOT = REPOSITORY_ROOT / "deployment/postgresql/ofarm_ed25519"
CONTAINERFILE = (EXTENSION_ROOT / "Containerfile").read_text(encoding="ascii")


def test_native_build_uses_only_the_accepted_pinned_images() -> None:
    assert CONTAINERFILE.splitlines()[0] == (
        "# syntax=docker/dockerfile:1.7@sha256:"
        "a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e"
    )
    assert CONTAINERFILE.count(
        "postgres@sha256:"
        "5f050f770b427fbd477edee6c3968a72e5c6be97e050a7e368b2b74a9494a285"
    ) == 2
    assert CONTAINERFILE.count(
        "gcc@sha256:"
        "1ea81e094f614fd2ed066316651dbac8eecb4d36add2ddd8a26151374c85c52c"
    ) == 2
    assert "FROM postgres:" not in CONTAINERFILE
    assert "FROM gcc:" not in CONTAINERFILE


def test_server_development_packages_are_arch_closed_and_verified() -> None:
    expected = {
        "amd64": (
            "adc91a999ec840f8db8c8df5ac2473fe1deeaed0e76bd5a6391afa7c74bceac3",
            "1338208",
        ),
        "arm64": (
            "372c8eb77604bc9cba61689661701e65a336b14a43e8f9be850088bb8c4428b6",
            "1327764",
        ),
    }
    for architecture, (digest, size) in expected.items():
        assert (
            "https://apt.postgresql.org/pub/repos/apt/pool/main/p/"
            "postgresql-17/postgresql-server-dev-17_"
            f"17.10-1.pgdg13+1_{architecture}.deb"
        ) in CONTAINERFILE
        assert CONTAINERFILE.count(digest) == 2
        assert f"= '{size}'" in CONTAINERFILE

    assert "dpkg-deb --field" in CONTAINERFILE
    assert "dpkg-deb --extract" in CONTAINERFILE
    assert "17.10-1.pgdg13+1" in CONTAINERFILE
    assert "/usr/lib/postgresql/17/bin/pg_config" in CONTAINERFILE
    assert "/usr/lib/postgresql/17/lib/pgxs" in CONTAINERFILE
    assert "apt-get" not in CONTAINERFILE
    assert "apt " not in CONTAINERFILE


def test_libsodium_source_and_reproducibility_controls_are_exact() -> None:
    assert CONTAINERFILE.count(
        "adbdd8f16149e81ac6078a03aca6fc03b592b89ef7b5ed83841c086191be3349"
    ) == 2
    assert "libsodium-1.0.22.tar.gz" in CONTAINERFILE
    assert "= '2008529'" in CONTAINERFILE
    assert "LC_ALL=C" in CONTAINERFILE
    assert "TZ=UTC" in CONTAINERFILE
    assert "SOURCE_DATE_EPOCH=0" in CONTAINERFILE
    assert "make -j1" in CONTAINERFILE
    assert "with_llvm=no" in CONTAINERFILE
    assert CONTAINERFILE.count("-Wextra -Werror") >= 3
    assert "touch --date='@0'" in CONTAINERFILE
    assert "--disable-shared" in CONTAINERFILE
    assert "--enable-static" in CONTAINERFILE
    assert "readelf --dynamic" in CONTAINERFILE
    assert "grep --extended-regexp 'lib(asan|ubsan)'" in CONTAINERFILE
    assert "grep --fixed-strings 'OFARM test-only'" in CONTAINERFILE


def test_docker_context_copy_is_an_exact_source_allowlist() -> None:
    forbidden_copy_patterns = (
        "COPY . ",
        "COPY .\n",
        "COPY *",
        "COPY deployment/",
    )
    assert all(pattern not in CONTAINERFILE for pattern in forbidden_copy_patterns)
    for filename in (
        "Makefile",
        "ofarm_ed25519--1.0.sql",
        "ofarm_ed25519.c",
        "ofarm_ed25519.control",
        "ofarm_ed25519.exports",
        "ofarm_ed25519_core.c",
        "ofarm_ed25519_core.h",
        "ofarm_ed25519_fault_test.sql",
        "ofarm_ed25519_fuzz.c",
        "ofarm_ed25519_harness.c",
        "ofarm_ed25519_live_test.sql",
        "ofarm_ed25519_vectors.h",
        "ofarm_ed25519_vectors.json",
        "ofarm_ed25519_vectors.sha256",
        "ofarm_ed25519_vectors.sql",
    ):
        assert filename in CONTAINERFILE


def test_every_container_build_step_is_offline_after_pinned_downloads() -> None:
    run_instructions = re.findall(r"^RUN(?:\s+.*)?$", CONTAINERFILE, re.MULTILINE)

    assert run_instructions
    assert all(instruction.startswith("RUN --network=none") for instruction in run_instructions)


def test_sanitizer_target_is_closed_and_runs_both_suites() -> None:
    assert "FROM build-inputs AS sanitizer-build" in CONTAINERFILE
    assert "FROM postgres-runtime AS sanitizer" in CONTAINERFILE
    assert re.search(r"address\|undefined\) ;;", CONTAINERFILE)
    assert "SANITIZER must be exactly address or undefined" in CONTAINERFILE
    sanitizer_section = CONTAINERFILE.split(
        "FROM build-inputs AS sanitizer-build", maxsplit=1
    )[1].split("FROM --platform=$TARGETPLATFORM postgres@", maxsplit=1)[0]
    assert "make -j1 check" in sanitizer_section
    assert "--disable-asm" in sanitizer_section
    assert "arm64) SANITIZER_ARCH_FLAGS='-mgeneral-regs-only'" in sanitizer_section
    assert "-fsanitize=${SANITIZER}" in sanitizer_section
    assert "ofarm_ed25519_core.c ofarm_ed25519_harness.c" in sanitizer_section
    assert "/build/ofarm_ed25519_harness_sanitized" in sanitizer_section
    assert (
        'OFARM_EXTRA_CFLAGS="-Wextra -Werror ${SANITIZER_FLAGS}"'
        in sanitizer_section
    )
    assert "OFARM_EXTRA_LDFLAGS=\"${SANITIZER_FLAGS}\"" in sanitizer_section
    sanitizer_live = CONTAINERFILE.split(
        "FROM postgres-runtime AS sanitizer", maxsplit=1
    )[1].split("FROM --platform=$TARGETPLATFORM postgres@", maxsplit=1)[0]
    assert "LD_PRELOAD=/opt/ofarm-sanitizer/lib/libasan.so" in sanitizer_live
    assert "--file=/tmp/ofarm_ed25519_live_test.sql" in sanitizer_live
    assert "pg_ctl" in sanitizer_live


def test_shared_core_and_harness_cover_the_hostile_contract() -> None:
    core = (EXTENSION_ROOT / "ofarm_ed25519_core.c").read_text(encoding="ascii")
    wrapper = (EXTENSION_ROOT / "ofarm_ed25519.c").read_text(encoding="ascii")
    harness = (EXTENSION_ROOT / "ofarm_ed25519_harness.c").read_text(
        encoding="ascii"
    )
    corpus_bytes = (EXTENSION_ROOT / "ofarm_ed25519_vectors.json").read_bytes()
    corpus = json.loads(corpus_bytes)
    generated_header = (EXTENSION_ROOT / "ofarm_ed25519_vectors.h").read_text(
        encoding="ascii"
    )
    generated_sql = (EXTENSION_ROOT / "ofarm_ed25519_vectors.sql").read_text(
        encoding="ascii"
    )
    corpus_digest = hashlib.sha256(corpus_bytes).hexdigest()

    assert "ofarm_ed25519_verify_bytes" in core
    assert "ofarm_ed25519_verify_bytes" in wrapper
    assert "crypto_sign_verify_detached" in core
    assert "crypto_sign_verify_detached" not in wrapper
    assert "crypto_core_ed25519_is_valid_point(public_key)" in core
    assert "crypto_core_ed25519_is_valid_point(signature)" in core
    assert "OFARM_ED25519_MAX_SIGNED_BYTES 8192U" in (
        EXTENSION_ROOT / "ofarm_ed25519_core.h"
    ).read_text(encoding="ascii")

    assert '#include "ofarm_ed25519_vectors.h"' in harness
    assert "OFARM_ED25519_VECTOR_CASES" in harness
    assert "OFARM_ED25519_VECTOR_CORPUS_SHA256" in generated_header
    assert corpus["schemaVersion"] == "ofarm.ed25519-adversarial-vectors.v1"
    assert len(corpus["cases"]) == 16
    assert set(corpus["requiredCategories"]) == {
        category
        for case in corpus["cases"]
        for category in case["categories"]
    } | {"bit-flips", "boundaries"}
    assert (EXTENSION_ROOT / "ofarm_ed25519_vectors.sha256").read_text(
        encoding="ascii"
    ) == f"{corpus_digest}  ofarm_ed25519_vectors.json\n"
    assert f"sha256:{corpus_digest}" in generated_header
    assert f"sha256:{corpus_digest}" in generated_sql

    corpus_text = corpus_bytes.decode("ascii")
    for vector in (
        "e5564300c360ac729086e2cc806e828a",
        "004f4641524d322d54454e414e542d43",
        "95999999999999999999999999999999",
        "f5ffffffffffffffffffffffffffffff",
        "f6ffffffffffffffffffffffffffffff",
        "edd3f55c1a631258d69cf7a2def9de14",
        "eed3f55c1a631258d69cf7a2def9de14",
    ):
        assert vector in corpus_text
    assert "length <= OFARM_ED25519_MAX_SIGNED_BYTES" in harness
    assert "OFARM_ED25519_VECTOR_SIGNED_BYTES_LENGTHS" in harness
    assert 8193 in corpus["families"]["boundaries"]["signedBytesLengths"]
    assert "clone_exact" in harness
    assert "bit < sizeof changed_public_key * 8U" in harness
    assert "bit < sizeof changed_preflight * 8U" in harness
    assert "bit < sizeof changed_signature * 8U" in harness


def test_wrapper_refuses_raw_oversize_before_any_detoast() -> None:
    wrapper = (EXTENSION_ROOT / "ofarm_ed25519.c").read_text(encoding="ascii")
    live_test = (EXTENSION_ROOT / "ofarm_ed25519_live_test.sql").read_text(
        encoding="ascii"
    )

    raw_gate = wrapper.index("raw_bytea_length_may_fit(public_key_datum")
    first_detoast = wrapper.index("detoast_bytea(public_key_datum, 0)")
    assert "toast_raw_datum_size(datum)" in wrapper
    assert "maximum_payload_length + VARHDRSZ" in wrapper
    assert raw_gate < first_detoast
    assert wrapper.count("PG_FREE_IF_COPY") == 3
    assert "FROM postgres-runtime AS live-test" in CONTAINERFILE
    assert "--file=/tmp/ofarm_ed25519_live_test.sql" in CONTAINERFILE
    assert r"\ir /tmp/ofarm_ed25519_vectors.sql" in live_test
    assert "toast_tuple_target = 128" in live_test
    assert live_test.count("oversized ") == 3
    assert "admitted input did not exercise compressed detoast" in live_test
    assert live_test.count("ordinary four-byte ") >= 4
    assert live_test.count("external uncompressed ") >= 4


def test_failure_mapping_is_selective_and_live_exercised() -> None:
    wrapper = (EXTENSION_ROOT / "ofarm_ed25519.c").read_text(encoding="ascii")
    core = (EXTENSION_ROOT / "ofarm_ed25519_core.c").read_text(encoding="ascii")
    fault_test = (EXTENSION_ROOT / "ofarm_ed25519_fault_test.sql").read_text(
        encoding="ascii"
    )

    assert wrapper.count("PG_CATCH") == 1
    assert "geterrcode() != ERRCODE_OUT_OF_MEMORY" in wrapper
    assert "PG_RE_THROW()" in wrapper
    assert "CopyErrorData" not in wrapper
    assert wrapper.count("ERRCODE_SYSTEM_ERROR") == 1
    assert (
        wrapper.count("OFARM Ed25519 verifier infrastructure failure") == 1
    )
    assert "public_key_valid != 1" in core
    assert "signature_r_valid != 1" in core
    assert "verified = 7" in core

    assert "FROM extension-build AS failure-semantics-build" in CONTAINERFILE
    assert "FROM postgres-runtime AS failure-semantics" in CONTAINERFILE
    for fault in (
        "SODIUM_INIT",
        "UNEXPECTED_VERIFY_RESULT",
        "DETOAST_OOM",
        "DETOAST_CANCEL",
        "DETOAST_TIMEOUT",
        "DETOAST_TRANSACTION",
        "DETOAST_STORAGE",
    ):
        assert f"OFARM_ED25519_TEST_FAULT_{fault}" in CONTAINERFILE
    assert "= '7'" in CONTAINERFILE

    for state, message in (
        ("58000", "OFARM Ed25519 verifier infrastructure failure"),
        ("57014", "OFARM test-only cancellation"),
        ("57014", "OFARM test-only statement timeout"),
        ("40001", "OFARM test-only transaction failure"),
        ("58030", "OFARM test-only storage failure"),
    ):
        assert f"'{state}'" in fault_test
        assert message in fault_test
    for diagnostic in (
        "PG_EXCEPTION_DETAIL",
        "PG_EXCEPTION_HINT",
        "SCHEMA_NAME",
        "TABLE_NAME",
        "COLUMN_NAME",
        "CONSTRAINT_NAME",
    ):
        assert diagnostic in fault_test


def test_test_only_objects_cannot_reach_the_default_runtime_stage() -> None:
    final_stage = CONTAINERFILE.rsplit(
        "FROM --platform=$TARGETPLATFORM postgres@", maxsplit=1
    )[1]
    assert "COPY --from=live-test /opt/ofarm-final-root/ /" in final_stage
    assert "ofarm-test-only" not in final_stage
    assert "ofarm-sanitizer" not in final_stage
    assert "OFARM_ED25519_TEST_" not in final_stage


def test_sql_and_elf_surfaces_remain_exact() -> None:
    exports = (EXTENSION_ROOT / "ofarm_ed25519.exports").read_text(
        encoding="ascii"
    )
    global_block = exports.split("global:", maxsplit=1)[1].split(
        "local:", maxsplit=1
    )[0]
    assert set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", global_block)) == {
        "Pg_magic_func",
        "_PG_init",
        "pg_finfo_ofarm_ed25519_verify",
        "ofarm_ed25519_verify",
    }
    sql = (EXTENSION_ROOT / "ofarm_ed25519--1.0.sql").read_text(
        encoding="ascii"
    )
    assert sql.count("CREATE FUNCTION") == 1
    assert "LANGUAGE C" in sql
    assert "IMMUTABLE STRICT PARALLEL UNSAFE SECURITY INVOKER" in sql
