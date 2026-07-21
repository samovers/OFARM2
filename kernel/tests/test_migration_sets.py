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
    require_authoritative_migration_set,
    revalidate_migration_set,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]


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
