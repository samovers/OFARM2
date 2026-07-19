"""Static confinement tests for the content-addressed native verifier source."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTENSION = ROOT / "deployment" / "postgresql" / "ofarm_ed25519"
MIGRATION = ROOT / "kernel" / "migrations" / "0001_initial.sql"


def test_native_verifier_has_one_callable_surface_and_no_signer() -> None:
    source = (EXTENSION / "ofarm_ed25519.c").read_text("utf-8")
    core = (EXTENSION / "ofarm_ed25519_core.c").read_text("utf-8")
    sql = (EXTENSION / "ofarm_ed25519--1.0.sql").read_text("utf-8")
    exports = (EXTENSION / "ofarm_ed25519.exports").read_text("utf-8")
    assert source.count("PG_FUNCTION_INFO_V1(") == 1
    assert "PG_FUNCTION_INFO_V1(ofarm_ed25519_verify)" in source
    assert "crypto_core_ed25519_is_valid_point(public_key)" in core
    assert "crypto_core_ed25519_is_valid_point(signature)" in core
    assert "crypto_sign_verify_detached" in core
    for forbidden in (
        "crypto_sign_detached",
        "crypto_sign_keypair",
        "crypto_sign_seed_keypair",
        "crypto_box_",
        "crypto_secretbox_",
    ):
        assert forbidden not in source + core
    assert sql.count("CREATE FUNCTION") == 1
    assert "IMMUTABLE STRICT PARALLEL UNSAFE SECURITY INVOKER" in sql
    assert exports.split("global:", 1)[1].split("local:", 1)[0].count(";") == 4


def test_extension_control_and_build_inputs_are_exactly_pinned() -> None:
    control = (EXTENSION / "ofarm_ed25519.control").read_text("utf-8")
    makefile = (EXTENSION / "Makefile").read_text("utf-8")
    container = (EXTENSION / "Containerfile").read_text("utf-8")
    assert "default_version = '1.0'" in control
    assert "module_pathname = '$libdir/ofarm_ed25519'" in control
    assert "superuser = true" in control
    assert "trusted = false" in control
    assert "relocatable = false" in control
    assert "schema = 'ofarm_crypto'" in control
    assert "libsodium.a" in makefile
    assert "--version-script" in makefile
    assert container.count(
        "postgres@sha256:5f050f770b427fbd477d1c272473d9cfc3e654"
    ) == 0
    assert container.count(
        "postgres@sha256:5f050f770b427fbd477edee6c3968a72e5c6be97e050a7e368b2b74a9494a285"
    ) == 2
    assert (
        "adbdd8f16149e81ac6078a03aca6fc03b592b89ef7b5ed83841c086191be3349"
        in container
    )
    assert "--disable-shared" in container
    assert "--enable-static" in container


def test_binder_requires_exact_native_verification_success() -> None:
    source = MIGRATION.read_text("utf-8")
    binder = source.split(
        "CREATE FUNCTION ofarm.bind_tenant_capability(", 1
    )[1].split("CREATE FUNCTION ofarm.current_tenant_context(", 1)[0]
    assert "IF NOT ofarm_crypto.ed25519_verify(" not in binder
    assert "ofarm_crypto.ed25519_verify(" in binder
    assert ") IS DISTINCT FROM true THEN" in binder
    registration = source.split(
        "CREATE FUNCTION ofarm.register_tenant_capability_key(", 1
    )[1].split(
        "CREATE FUNCTION ofarm.verify_tenant_capability_candidate_preflight(",
        1,
    )[0]
    preflight = source.split(
        "CREATE FUNCTION ofarm.verify_tenant_capability_candidate_preflight(",
        1,
    )[1].split("CREATE FUNCTION ofarm.activate_tenant_capability_key(", 1)[0]
    assert "verify_tenant_capability_preflight" not in registration
    assert "ofarm.verify_tenant_capability_preflight(" in preflight
    assert ") IS NOT DISTINCT FROM true;" in preflight
    assert "LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER" in preflight
    assert "pg_advisory_xact_lock(1330004306, 1413694001)" in preflight
    assert "FROM ofarm.tenant_capability_keyring AS ring" in preflight
    assert "FROM ofarm.tenant_capability_verification_key AS key" in preflight
    assert preflight.count("FOR UPDATE;") == 2
    assert "FROM ofarm.tenant_capability_key_lifecycle AS act" in preflight


def test_revocation_keeps_only_the_exact_expired_rotation_handoff_exception() -> None:
    source = MIGRATION.read_text("utf-8")
    fold = source.split(
        "CREATE FUNCTION ofarm.fold_tenant_capability_key_lifecycle(", 1
    )[1].split("CREATE FUNCTION ofarm.verify_tenant_capability_preflight(", 1)[0]
    revoke = source.split(
        "CREATE FUNCTION ofarm.revoke_tenant_capability_key(", 1
    )[1].split(
        "CREATE FUNCTION ofarm.resume_tenant_capability_admission(", 1
    )[0]
    assert "known_verification_end_us[target_key_index]" in fold
    assert "close_reason = ''ROTATION_HANDOFF''" in fold
    assert "last_rotated_old_kid" in fold
    assert "last_rotated_old_digest" in fold
    assert "authority.selected_verification_end_us IS NULL" in revoke
    assert "key revocation target is not eligible" in revoke
    assert "authority.close_reason IS DISTINCT FROM" in revoke


def test_revoking_the_exact_rotated_old_key_resolves_that_obligation() -> None:
    source = MIGRATION.read_text("utf-8")
    fold = source.split(
        "CREATE FUNCTION ofarm.fold_tenant_capability_key_lifecycle(", 1
    )[1].split("CREATE FUNCTION ofarm.verify_tenant_capability_preflight(", 1)[0]
    clear = fold.split(
        "IF act_row.old_kid IS NOT DISTINCT FROM\n"
        "                        last_rotated_old_kid THEN",
        1,
    )[1].split("END IF;", 1)[0]
    assert "close_reason" not in clear
    assert "last_rotated_old_kid := NULL" in clear
    assert "last_rotated_old_digest := NULL" in clear
