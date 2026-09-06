"""Immutable migration-set identity tests for issue #174."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_AUTHORITATIVE_MIGRATION_SET,
    MIGRATION_SET_DIGEST_POLICY,
    MIGRATION_SOURCE_MAX_BYTES,
    SECURITY_AUDIT_SERVICE,
    TENANT_AUTHORITATIVE_MIGRATION_SET,
    TENANT_SERVICE,
    MigrationSet,
    MigrationSetError,
    load_authoritative_migration_set,
    load_migration_set,
    preflight_main,
    require_authoritative_migration_set,
    revalidate_migration_set,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
TENANT_BINDING_SELECTION_CONTROL_ADMISSION_RFC = (
    PACKAGE_ROOT
    / "docs/rfcs/OFARM_Tenant_Binding_Selection_Control_Admission_RFC_v0_1.md"
)
TENANT_CURRENT_CONTEXT_SELECTION_OWNER_ADMISSION_RFC = (
    PACKAGE_ROOT
    / "docs/rfcs/OFARM_Tenant_Current_Context_Selection_Owner_Admission_RFC_v0_1.md"
)
TENANT_WRITE_LOCK_SELECTION_OWNER_ADMISSION_RFC = (
    PACKAGE_ROOT
    / "docs/rfcs/OFARM_Tenant_Write_Lock_Selection_Owner_Admission_RFC_v0_1.md"
)


def _write_migration(root: Path, relative_directory: str, name: str, data: bytes) -> None:
    directory = root / relative_directory
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(data)


def test_services_have_distinct_fixed_migration_and_ledger_identities():
    assert TENANT_SERVICE.identity == "ofarm.tenant-postgresql.v1"
    assert TENANT_SERVICE.relative_directory == "kernel/migrations"
    assert TENANT_SERVICE.qualified_ledger == "ofarm.schema_migration"
    assert SECURITY_AUDIT_SERVICE.identity == "ofarm.security-audit-postgresql.v1"
    assert SECURITY_AUDIT_SERVICE.relative_directory == "security_audit/migrations"
    assert SECURITY_AUDIT_SERVICE.qualified_ledger == \
        "ofarm_security.schema_migration"
    assert TENANT_SERVICE != SECURITY_AUDIT_SERVICE


def test_v5_admission_pins_the_complete_merged_child_contract():
    source = TENANT_BINDING_SELECTION_CONTROL_ADMISSION_RFC.read_bytes()

    assert len(source) == 32_169
    assert hashlib.sha256(source).hexdigest() == (
        "c1d02969811be0d5b02bdae158cb48e5d8148356ca9d4bac956c8861d529c37a"
    )


def test_v6_admission_pins_the_complete_merged_child_contract():
    source = TENANT_CURRENT_CONTEXT_SELECTION_OWNER_ADMISSION_RFC.read_bytes()

    assert len(source) == 50_383
    assert hashlib.sha256(source).hexdigest() == (
        "af85e259230b69edeba80ddc2eea2f070a601fd3888fd463ce595f9cc446b13d"
    )


def test_v7_admission_pins_the_complete_merged_child_contract():
    source = TENANT_WRITE_LOCK_SELECTION_OWNER_ADMISSION_RFC.read_bytes()
    text = source.decode("utf-8")

    assert len(source) == 45_758
    assert hashlib.sha256(source).hexdigest() == (
        "5745ad4b8b588be2b5a1b64b4b84aa757b23f8d2de00ca59e71de8ea304f51b0"
    )
    assert text.startswith(
        "# OFARM2 Tenant Write-Lock Selection-Owner Admission — "
        "Phase A Contract v0.1\n"
    )
    assert (
        "**Contract identity:** "
        "ofarm.tenant-write-lock-selection-owner-admission.issue176.v0.1"
    ) in text
    assert (
        "**Status:** architect-approved Phase A contract; documentation-only"
    ) in text


@pytest.mark.parametrize(
    ("service", "expected"),
    (
        (TENANT_SERVICE, TENANT_AUTHORITATIVE_MIGRATION_SET),
        (SECURITY_AUDIT_SERVICE, SECURITY_AUDIT_AUTHORITATIVE_MIGRATION_SET),
    ),
)
def test_checked_in_migration_release_has_one_literal_authority(service, expected):
    migration_set = load_authoritative_migration_set(PACKAGE_ROOT, service)

    assert migration_set.service == expected.service
    assert migration_set.digest == expected.digest
    assert tuple(
        (
            migration.version,
            migration.filename,
            migration.source_sha256,
            migration.byte_length,
            migration_set.prefix_digest(migration.version),
        )
        for migration in migration_set.migrations
    ) == tuple(
        (
            migration.version,
            migration.filename,
            migration.source_sha256,
            migration.byte_length,
            migration.applied_prefix_digest,
        )
        for migration in expected.migrations
    )


def test_security_audit_v4_pins_temporary_export_consumption_release():
    migration_set = load_authoritative_migration_set(
        PACKAGE_ROOT,
        SECURITY_AUDIT_SERVICE,
    )
    migration = migration_set.migrations[3]

    assert migration.filename == "0004_temporary_export_lifecycle.sql"
    assert migration.source_sha256 == \
        "sha256:390fd96d498ab3d392a57135fb336a266350b3c6330eec749b7d07cbd3e77650"
    assert migration.byte_length == 17_122
    assert migration_set.prefix_digest(4) == \
        "sha256:ac9c85a5766a072fa516ee15d607511fc0b5cf2b0651eb3d9087a5c086eb5b2c"
    assert migration_set.digest == migration_set.prefix_digest(4)
    assert b"LOCK TABLE" in migration.source_bytes
    assert b"IN EXCLUSIVE MODE" in migration.source_bytes
    assert b"advisory" not in migration.source_bytes
    assert b"CREATE ROLE" not in migration.source_bytes
    assert b"store_migration_execution_id" in migration.source_bytes
    assert b"v_live_count >= 1024" in migration.source_bytes


def test_tenant_v5_is_verifier_only_and_pins_the_closed_admission_transition():
    migration_set = load_authoritative_migration_set(
        PACKAGE_ROOT,
        TENANT_SERVICE,
    )
    migration = migration_set.migrations[4]

    assert migration.filename == \
        "0005_tenant_binding_selection_control_admission.sql"
    assert migration.source_sha256 == \
        "sha256:fde66e835f8c4456d7404eb00b99292e267f573f8b126f781f3ed55bd5e8df9a"
    assert migration.byte_length == 8545
    assert migration_set.prefix_digest(5) == \
        "sha256:ef2e85c150d7c445ae33d4c1cc63a06bbcf17c79f1e7bdaf070ae4819ed38288"
    assert b"observed_migration_count <> 5" in migration.source_bytes
    assert b"tenant binding selection-control admission ACL differs" in (
        migration.source_bytes
    )
    assert b"GRANT EXECUTE ON FUNCTION ofarm.create_tenant_challenge" not in (
        migration.source_bytes
    )
    assert b"GRANT EXECUTE ON FUNCTION ofarm.bind_tenant_capability" not in (
        migration.source_bytes
    )


def test_tenant_v6_is_verifier_only_and_pins_the_closed_owner_admission():
    migration_set = load_authoritative_migration_set(
        PACKAGE_ROOT,
        TENANT_SERVICE,
    )
    migration = migration_set.migrations[5]

    assert migration.filename == \
        "0006_tenant_current_context_selection_owner_admission.sql"
    assert migration.source_sha256 == \
        "sha256:a61c668a2bae04026b8413385f8bc1b5fd43f08f8d5281501ff766a57d552b48"
    assert migration.byte_length == 8655
    assert migration_set.prefix_digest(6) == \
        "sha256:209990a8a9ac60ab096b11d418051127b7c891e4bfc6cefdf282d72f3875d0de"
    assert b"observed_migration_count <> 6" in migration.source_bytes
    assert b"tenant current-context selection-owner admission ACL differs" in (
        migration.source_bytes
    )
    assert b"GRANT EXECUTE ON FUNCTION" not in migration.source_bytes
    assert b"ALTER FUNCTION ofarm.current_" not in migration.source_bytes
    assert b"CREATE ROLE" not in migration.source_bytes


def test_tenant_v7_is_verifier_only_and_pins_write_lock_owner_admission():
    migration_set = load_authoritative_migration_set(
        PACKAGE_ROOT,
        TENANT_SERVICE,
    )
    migration = migration_set.migrations[6]

    assert migration.filename == \
        "0007_tenant_write_lock_selection_owner_admission.sql"
    assert migration.source_sha256 == \
        "sha256:cf8594b6c456953004912722b168d6bdda7c6dbfc903ba8099b018e2f270dff7"
    assert migration.byte_length == 7936
    assert migration_set.prefix_digest(7) == \
        "sha256:5616797d1362c55c78175126edab29cc3e88c021ba0709e3766d3196d2b0126b"
    assert b"observed_migration_count <> 7" in migration.source_bytes
    assert b"tenant write-lock selection-owner admission ACL differs" in (
        migration.source_bytes
    )
    for forbidden_statement in (
        b"GRANT ",
        b"REVOKE ",
        b"CREATE ROLE",
        b"ALTER ROLE",
        b"ALTER FUNCTION",
        b"ALTER PROCEDURE",
    ):
        assert forbidden_statement not in migration.source_bytes
    assert migration.source_bytes.count(
        b"pg_catalog.length(verifier_definition) - pg_catalog.length("
    ) == 7
    assert b"routine_inventory_marker" in migration.source_bytes
    assert b"write_lock_acl_check" in migration.source_bytes
    assert b"old_migration_count" in migration.source_bytes
    assert b"old_head_version" in migration.source_bytes
    assert b"old_prefix_expression" in migration.source_bytes
    assert b"old_catalog_digest" in migration.source_bytes
    assert b"old_provisioning_digest" in migration.source_bytes


def test_tenant_v8_pins_selection_storage_and_complete_release_identity():
    migration_set = load_authoritative_migration_set(
        PACKAGE_ROOT,
        TENANT_SERVICE,
    )
    migration = migration_set.migrations[7]

    assert migration.filename == \
        "0008_tenant_command_runtime_bundle_selection.sql"
    assert migration.source_sha256 == \
        "sha256:635e476fb4eb93073ed353397a977ea887c42e1be11b42f9a4782a76f88ab765"
    assert migration.byte_length == 37933
    assert migration_set.prefix_digest(8) == \
        "sha256:7231c869066c56f7c642460d33391bab00456daecdb04530b34da7210e8e8a54"
    assert migration_set.digest == \
        "sha256:bd80785f567e593edea9f88898c18cc8b8269bc8d71eb5aa385c595abc9d7b95"
    assert b"observed_migration_count <> 8" in migration.source_bytes
    assert b"version-8 selection policy inventory differs" in migration.source_bytes
    assert b"activate_commit_operation_claim_draft_runtime_bundle_selection" in (
        migration.source_bytes
    )


def test_tenant_v9_pins_inert_runtime_content_retention_and_release_identity():
    migration_set = load_authoritative_migration_set(
        PACKAGE_ROOT,
        TENANT_SERVICE,
    )
    migration = migration_set.migrations[8]

    assert migration.filename == \
        "0009_runtime_bundle_global_content_retention.sql"
    assert migration.source_sha256 == \
        "sha256:10e1966f8a2f25ccc8be077b1484807f03230aae116b352d23c9167e15e45c8c"
    assert migration.byte_length == 14567
    assert migration_set.prefix_digest(9) == \
        "sha256:cef599a81bda42f84c6c9718845b245ecfa7d97564f5c132b0f12dda526d1293"
    assert migration_set.digest == \
        "sha256:bd80785f567e593edea9f88898c18cc8b8269bc8d71eb5aa385c595abc9d7b95"
    assert b"observed_migration_count <> 9" in migration.source_bytes
    assert b"CREATE FUNCTION ofarm.retain_runtime_content(" in (
        migration.source_bytes
    )
    assert b"ofarm.publish_runtime_bundle(uuid,text,jsonb)" in (
        migration.source_bytes
    )
    assert b"INSERT INTO ofarm.runtime_content_blob" in migration.source_bytes
    assert b"INSERT INTO ofarm.runtime_bundle" not in migration.source_bytes
    assert b"tenant_command_runtime_bundle_selection" not in (
        migration.source_bytes
    )


def test_tenant_v10_pins_fixed_read_only_selector_and_release_identity():
    migration_set = load_authoritative_migration_set(
        PACKAGE_ROOT,
        TENANT_SERVICE,
    )
    migration = migration_set.migrations[9]

    assert migration.filename == \
        "0010_tenant_command_runtime_bundle_selector.sql"
    assert migration.source_sha256 == \
        "sha256:695e38aa0d91ae6a56b8563a6285faf7b2837203e9de378437bc18a6e47da213"
    assert migration.byte_length == 24_684
    assert migration_set.prefix_digest(10) == \
        "sha256:bd80785f567e593edea9f88898c18cc8b8269bc8d71eb5aa385c595abc9d7b95"
    assert migration_set.digest == migration_set.prefix_digest(10)
    assert b"observed_migration_count <> 10" in migration.source_bytes
    assert migration.source_bytes.count(
        b"CREATE POLICY tenant_command_runtime_bundle_"
    ) == 2
    assert b"FOR SELECT TO ofarm_owner" in migration.source_bytes
    assert b"resolve_commit_operation_claim_draft_runtime_bundle_selection()" in (
        migration.source_bytes
    )
    assert b"TO ofarm_app, ofarm_worker" in migration.source_bytes
    assert b"INSERT INTO ofarm.governed_write_batch" not in migration.source_bytes
    assert b"take_tenant_write_lock" not in migration.source_bytes
    assert b"pg_advisory" not in migration.source_bytes


@pytest.mark.parametrize("mutation", ("edited", "renamed", "future", "missing"))
def test_operator_loader_refuses_any_non_authoritative_history(tmp_path, mutation):
    authoritative = load_migration_set(PACKAGE_ROOT, TENANT_SERVICE)
    migration = authoritative.migrations[0]
    filename = migration.filename
    source = migration.source_bytes
    if mutation == "edited":
        source += b"\n-- edited\n"
    elif mutation == "renamed":
        filename = "0001_replacement.sql"
    elif mutation == "future":
        _write_migration(
            tmp_path,
            TENANT_SERVICE.relative_directory,
            "0002_future.sql",
            b"SELECT 2;\n",
        )
    elif mutation == "missing":
        (tmp_path / TENANT_SERVICE.relative_directory).mkdir(parents=True)
    if mutation != "missing":
        _write_migration(
            tmp_path,
            TENANT_SERVICE.relative_directory,
            filename,
            source,
        )

    with pytest.raises(MigrationSetError):
        load_authoritative_migration_set(tmp_path, TENANT_SERVICE)


def test_in_memory_non_authoritative_history_refuses():
    checked_in = load_migration_set(PACKAGE_ROOT, TENANT_SERVICE)
    altered = replace(checked_in, digest="sha256:" + "0" * 64)

    with pytest.raises(MigrationSetError):
        require_authoritative_migration_set(altered)


def test_absent_migration_directory_refuses(tmp_path):
    with pytest.raises(MigrationSetError, match="is absent"):
        load_migration_set(tmp_path, TENANT_SERVICE)


def test_empty_migration_directory_refuses(tmp_path):
    (tmp_path / TENANT_SERVICE.relative_directory).mkdir(parents=True)
    with pytest.raises(MigrationSetError, match="is empty"):
        load_migration_set(tmp_path, TENANT_SERVICE)


@pytest.mark.parametrize(
    "entry_name",
    ["README.md", "0001_INITIAL.sql", "1_initial.sql", "0001-initial.sql"],
)
def test_ungoverned_migration_filename_refuses(tmp_path, entry_name):
    _write_migration(
        tmp_path, TENANT_SERVICE.relative_directory, entry_name, b"SELECT 1;\n"
    )
    with pytest.raises(MigrationSetError, match="filename is not governed"):
        load_migration_set(tmp_path, TENANT_SERVICE)


def test_first_migration_name_is_exact(tmp_path):
    _write_migration(
        tmp_path,
        TENANT_SERVICE.relative_directory,
        "0001_bootstrap.sql",
        b"SELECT 1;\n",
    )
    with pytest.raises(MigrationSetError, match="exactly 0001_initial.sql"):
        load_migration_set(tmp_path, TENANT_SERVICE)


@pytest.mark.parametrize(
    "additional_name, expected",
    [
        ("0003_late.sql", "expected 0002, observed 0003"),
        ("0001_duplicate.sql", "version 0001 appears more than once"),
    ],
)
def test_migration_versions_are_gap_free_and_unique(
    tmp_path, additional_name, expected
):
    _write_migration(
        tmp_path,
        TENANT_SERVICE.relative_directory,
        "0001_initial.sql",
        b"SELECT 1;\n",
    )
    _write_migration(
        tmp_path,
        TENANT_SERVICE.relative_directory,
        additional_name,
        b"SELECT 2;\n",
    )
    with pytest.raises(MigrationSetError, match=expected):
        load_migration_set(tmp_path, TENANT_SERVICE)


@pytest.mark.parametrize(
    "source, expected",
    [
        (b"", "is empty"),
        (b"  \n", "contains no SQL text"),
        (b"\xef\xbb\xbfSELECT 1;\n", "must not contain a UTF-8 BOM"),
        (b"SELECT '\x00';\n", "contains a NUL byte"),
        (b"SELECT '\xff';\n", "is not strict UTF-8"),
    ],
)
def test_migration_source_bytes_are_closed(tmp_path, source, expected):
    _write_migration(
        tmp_path,
        TENANT_SERVICE.relative_directory,
        "0001_initial.sql",
        source,
    )
    with pytest.raises(MigrationSetError, match=expected):
        load_migration_set(tmp_path, TENANT_SERVICE)


def test_migration_directory_rejects_symlinked_entries(tmp_path):
    directory = tmp_path / TENANT_SERVICE.relative_directory
    directory.mkdir(parents=True)
    source = tmp_path / "source.sql"
    source.write_bytes(b"SELECT 1;\n")
    (directory / "0001_initial.sql").symlink_to(source)

    with pytest.raises(MigrationSetError, match="non-regular entry"):
        load_migration_set(tmp_path, TENANT_SERVICE)


def test_migration_directory_rejects_fifo_without_blocking(tmp_path, monkeypatch):
    directory = tmp_path / TENANT_SERVICE.relative_directory
    directory.mkdir(parents=True)
    os.mkfifo(directory / "0001_initial.sql")
    real_open = os.open
    observed_migration_open = False

    def require_nonblocking_open(path, flags, *args, **kwargs):
        nonlocal observed_migration_open
        if path == "0001_initial.sql":
            observed_migration_open = True
            assert flags & os.O_NONBLOCK
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", require_nonblocking_open)

    with pytest.raises(MigrationSetError, match="non-regular entry"):
        load_migration_set(tmp_path, TENANT_SERVICE)
    assert observed_migration_open


def test_migration_source_rejects_oversized_regular_file(tmp_path):
    _write_migration(
        tmp_path,
        TENANT_SERVICE.relative_directory,
        "0001_initial.sql",
        b"x" * (MIGRATION_SOURCE_MAX_BYTES + 1),
    )

    with pytest.raises(MigrationSetError, match="fixed source byte limit"):
        load_migration_set(tmp_path, TENANT_SERVICE)


def test_migration_source_rejects_growth_during_descriptor_read(
    tmp_path, monkeypatch
):
    _write_migration(
        tmp_path,
        TENANT_SERVICE.relative_directory,
        "0001_initial.sql",
        b"SELECT 1;\n",
    )
    migration_path = (
        tmp_path / TENANT_SERVICE.relative_directory / "0001_initial.sql"
    )
    real_read = os.read
    grew = False

    def grow_before_read(file_descriptor, byte_count):
        nonlocal grew
        if not grew:
            grew = True
            with migration_path.open("ab") as migration_file:
                migration_file.write(b"-- concurrent growth\n")
        return real_read(file_descriptor, byte_count)

    monkeypatch.setattr(os, "read", grow_before_read)

    with pytest.raises(MigrationSetError, match="changed while it was read"):
        load_migration_set(tmp_path, TENANT_SERVICE)


def test_preflight_sanitizes_descriptor_read_failure(monkeypatch, capsys):
    sentinel = "SECRET-MIGRATION-READ-SENTINEL"

    def refuse_read(_file_descriptor, _byte_count):
        raise OSError(sentinel)

    monkeypatch.setattr(os, "read", refuse_read)

    with pytest.raises(SystemExit) as raised:
        preflight_main(SECURITY_AUDIT_SERVICE, [])

    assert raised.value.code == 2
    stderr = capsys.readouterr().err
    assert stderr == (
        "migration preflight refused: migration 0001_initial.sql "
        "could not be read safely\n"
    )
    assert sentinel not in stderr
    assert "Traceback" not in stderr


def test_migration_directory_rejects_symlinked_parent(tmp_path):
    outside = tmp_path / "outside"
    _write_migration(
        outside, "migrations", "0001_initial.sql", b"SELECT 1;\n"
    )
    (tmp_path / "kernel").symlink_to(outside, target_is_directory=True)

    with pytest.raises(MigrationSetError, match="symlink or non-directory"):
        load_migration_set(tmp_path, TENANT_SERVICE)


def test_opened_migration_bytes_survive_path_replacement(tmp_path, monkeypatch):
    original = b"SELECT 'original';\n"
    replacement = tmp_path / "replacement.sql"
    replacement.write_bytes(b"SELECT 'replacement';\n")
    _write_migration(
        tmp_path,
        TENANT_SERVICE.relative_directory,
        "0001_initial.sql",
        original,
    )
    migration_path = (
        tmp_path / TENANT_SERVICE.relative_directory / "0001_initial.sql"
    )
    held_path = tmp_path / "held-original.sql"
    real_read = os.read
    replaced = False

    def replace_after_open(file_descriptor, byte_count):
        nonlocal replaced
        if not replaced:
            replaced = True
            migration_path.rename(held_path)
            migration_path.symlink_to(replacement)
        return real_read(file_descriptor, byte_count)

    monkeypatch.setattr(os, "read", replace_after_open)

    migration_set = load_migration_set(tmp_path, TENANT_SERVICE)

    assert migration_set.migrations[0].source_bytes == original


def test_manifest_retains_exact_source_identities(tmp_path):
    first = b"CREATE TABLE example (id bigint PRIMARY KEY);\n"
    second = b"ALTER TABLE example ADD COLUMN note text;\n"
    _write_migration(
        tmp_path, TENANT_SERVICE.relative_directory, "0001_initial.sql", first
    )
    _write_migration(
        tmp_path, TENANT_SERVICE.relative_directory, "0002_add_note.sql", second
    )

    migration_set = load_migration_set(tmp_path, TENANT_SERVICE)
    manifest = migration_set.manifest()

    assert MIGRATION_SET_DIGEST_POLICY == "OFARM_POSTGRESQL_MIGRATION_SET_V1"
    assert [migration.version for migration in migration_set.migrations] == [1, 2]
    assert [migration.source_bytes for migration in migration_set.migrations] == [
        first,
        second,
    ]
    assert manifest["digestPolicy"] == MIGRATION_SET_DIGEST_POLICY
    assert manifest["service"] == {
        "identity": "ofarm.tenant-postgresql.v1",
        "directory": "kernel/migrations",
        "schema": "ofarm",
        "ledger": "ofarm.schema_migration",
    }
    assert manifest["migrations"] == [
        {
            "version": 1,
            "filename": "0001_initial.sql",
            "sourceSha256": "sha256:" + hashlib.sha256(first).hexdigest(),
            "byteLength": len(first),
        },
        {
            "version": 2,
            "filename": "0002_add_note.sql",
            "sourceSha256": "sha256:" + hashlib.sha256(second).hexdigest(),
            "byteLength": len(second),
        },
    ]
    assert json.loads(migration_set.canonical_manifest_bytes()) == manifest
    assert migration_set.canonical_manifest_bytes().endswith(b"\n")


def test_migration_set_digest_has_an_exact_golden_vector(tmp_path):
    _write_migration(
        tmp_path,
        TENANT_SERVICE.relative_directory,
        "0001_initial.sql",
        b"SELECT 1;\n",
    )
    _write_migration(
        tmp_path,
        TENANT_SERVICE.relative_directory,
        "0002_second.sql",
        b"SELECT 2;\n",
    )

    migration_set = load_migration_set(tmp_path, TENANT_SERVICE)

    assert migration_set.digest == \
        "sha256:37a3f1441243b616b7c3265e29975ef22ba716f53b76264bee72d5ad5b27a50f"
    assert migration_set.prefix_digest(1) == \
        "sha256:2e751e4714239ebdd23459a41eec95984129fdad54cb969c329c7352a470a612"
    assert migration_set.prefix_digest(2) == migration_set.digest


def test_executor_revalidates_manually_constructed_migration_sets(tmp_path):
    _write_migration(
        tmp_path,
        TENANT_SERVICE.relative_directory,
        "0001_initial.sql",
        b"SELECT 1;\n",
    )
    migration_set = load_migration_set(tmp_path, TENANT_SERVICE)
    migration = migration_set.migrations[0]

    revalidate_migration_set(migration_set)
    with pytest.raises(MigrationSetError, match="content identity differs"):
        revalidate_migration_set(
            MigrationSet(
                service=migration_set.service,
                migrations=(replace(migration, byte_length=migration.byte_length + 1),),
                digest=migration_set.digest,
            )
        )
    with pytest.raises(MigrationSetError, match="digest differs"):
        revalidate_migration_set(replace(migration_set, digest="sha256:" + "0" * 64))
    with pytest.raises(MigrationSetError, match="outside the set"):
        migration_set.prefix_digest(0)


def test_same_migration_bytes_do_not_cross_service_identity(tmp_path):
    source = b"SELECT 1;\n"
    _write_migration(
        tmp_path, TENANT_SERVICE.relative_directory, "0001_initial.sql", source
    )
    _write_migration(
        tmp_path,
        SECURITY_AUDIT_SERVICE.relative_directory,
        "0001_initial.sql",
        source,
    )

    tenant = load_migration_set(tmp_path, TENANT_SERVICE)
    audit = load_migration_set(tmp_path, SECURITY_AUDIT_SERVICE)

    assert tenant.migrations[0].source_sha256 == audit.migrations[0].source_sha256
    assert tenant.digest != audit.digest
