"""Immutable PostgreSQL migration-set discovery and identity.

This module deliberately does not execute SQL.  Issue #174 requires exact
provisioning verification before either migration runner may touch a target.
Keeping discovery and identity separate lets the runner consume one closed,
already-validated migration set whose complete release identity is literal in
this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


MIGRATION_SET_DIGEST_POLICY = "OFARM_POSTGRESQL_MIGRATION_SET_V1"
MIGRATION_SOURCE_MAX_BYTES = 1024 * 1024
_DIGEST_DOMAIN = MIGRATION_SET_DIGEST_POLICY.encode("ascii") + b"\x00"
_MIGRATION_FILENAME = re.compile(r"(?P<version>[0-9]{4})_(?P<name>[a-z][a-z0-9_]*)\.sql")
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]


class MigrationSetError(ValueError):
    """A migration directory is absent, ambiguous, mutable, or malformed."""


@dataclass(frozen=True, slots=True)
class MigrationService:
    """One fixed migration lane and its protected ledger identity."""

    identity: str
    relative_directory: str
    schema_name: str
    ledger_name: str

    @property
    def qualified_ledger(self) -> str:
        return f"{self.schema_name}.{self.ledger_name}"


TENANT_SERVICE = MigrationService(
    identity="ofarm.tenant-postgresql.v1",
    relative_directory="kernel/migrations",
    schema_name="ofarm",
    ledger_name="schema_migration",
)

SECURITY_AUDIT_SERVICE = MigrationService(
    identity="ofarm.security-audit-postgresql.v1",
    relative_directory="security_audit/migrations",
    schema_name="ofarm_security",
    ledger_name="schema_migration",
)


@dataclass(frozen=True, slots=True)
class Migration:
    """Exact source bytes and content identity for one numbered migration."""

    version: int
    filename: str
    source_bytes: bytes
    source_sha256: str
    byte_length: int

    def manifest(self) -> dict[str, object]:
        return {
            "version": self.version,
            "filename": self.filename,
            "sourceSha256": self.source_sha256,
            "byteLength": self.byte_length,
        }


@dataclass(frozen=True, slots=True)
class MigrationSet:
    """One gap-free, content-addressed migration history."""

    service: MigrationService
    migrations: tuple[Migration, ...]
    digest: str

    def manifest(self) -> dict[str, object]:
        return {
            "schemaVersion": "ofarm.postgresql-migration-set.v1",
            "digestPolicy": MIGRATION_SET_DIGEST_POLICY,
            "service": {
                "identity": self.service.identity,
                "directory": self.service.relative_directory,
                "schema": self.service.schema_name,
                "ledger": self.service.qualified_ledger,
            },
            "migrationSetDigest": self.digest,
            "migrationCount": len(self.migrations),
            "migrations": [migration.manifest() for migration in self.migrations],
        }

    def canonical_manifest_bytes(self) -> bytes:
        return (
            json.dumps(
                self.manifest(),
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("ascii")

    def prefix_digest(self, version: int) -> str:
        """Return the stable digest of the exact history through ``version``.

        Ledger rows use a prefix digest instead of the digest of the release
        that happened to apply them.  A prefix identity therefore remains
        independently verifiable after later migration files are appended.
        """

        revalidate_migration_set(self)
        if not isinstance(version, int) or isinstance(version, bool):
            raise MigrationSetError("migration prefix version must be an integer")
        if version < 1 or version > len(self.migrations):
            raise MigrationSetError("migration prefix version is outside the set")
        return _set_digest(self.service, self.migrations[:version])


@dataclass(frozen=True, slots=True)
class AuthoritativeMigration:
    """Literal release identity for one checked-in migration source."""

    version: int
    filename: str
    source_sha256: str
    byte_length: int
    applied_prefix_digest: str


@dataclass(frozen=True, slots=True)
class AuthoritativeMigrationSet:
    """The only migration history accepted by an operator-facing runner."""

    service: MigrationService
    migrations: tuple[AuthoritativeMigration, ...]
    digest: str


# These values are deliberately literal. Adding, renaming, or editing a
# migration is a release-contract change and must update this reviewed identity
# in the same commit. A directory scan by itself is never release authority.
TENANT_AUTHORITATIVE_MIGRATION_SET = AuthoritativeMigrationSet(
    service=TENANT_SERVICE,
    migrations=(
        AuthoritativeMigration(
            version=1,
            filename="0001_initial.sql",
            source_sha256=(
                "sha256:a51e8144cf1f6c6f553755062ed618c02e23d3749e8355cf33bdb8db4cea633d"
            ),
            byte_length=417694,
            applied_prefix_digest=(
                "sha256:ccb03db015e3260d53bb0ef2c7e5e6707ad0eec26390c9f3918bf37144fbac64"
            ),
        ),
        AuthoritativeMigration(
            version=2,
            filename="0002_authentication_read_api.sql",
            source_sha256=(
                "sha256:dd7db775673e651f0eff4bc67c4c640e5ad4477697c78f9339bd79471056c2e2"
            ),
            byte_length=21408,
            applied_prefix_digest=(
                "sha256:096395d502b789825544640bf0250c14cf71e0eb7656b9cb892c25845c6ae056"
            ),
        ),
    ),
    digest="sha256:096395d502b789825544640bf0250c14cf71e0eb7656b9cb892c25845c6ae056",
)

SECURITY_AUDIT_AUTHORITATIVE_MIGRATION_SET = AuthoritativeMigrationSet(
    service=SECURITY_AUDIT_SERVICE,
    migrations=(
        AuthoritativeMigration(
            version=1,
            filename="0001_initial.sql",
            source_sha256=(
                "sha256:5e648e0127ca386363c3a1d979a5718cbd5b4846b3ad98ceaee5e7684b278517"
            ),
            byte_length=169237,
            applied_prefix_digest=(
                "sha256:e3752c1f7d54dff7b749367a29a53b48b5ca3258e51b1a8388dacdcd830392b6"
            ),
        ),
        AuthoritativeMigration(
            version=2,
            filename="0002_hmac_v2_operations.sql",
            source_sha256=(
                "sha256:99b5bc1016a2544dab54ebd9359d6cedd697e2adf3c749ef3634485103544133"
            ),
            byte_length=12471,
            applied_prefix_digest=(
                "sha256:c1fb1dd7348dadacb234e85dad8c943024d820543c7d5cb06f309e526cdac5ac"
            ),
        ),
        AuthoritativeMigration(
            version=3,
            filename="0003_outcome_reason_vocabulary.sql",
            source_sha256=(
                "sha256:e97ecbb325553af672ce5626c8674ce9f4b8159dd646ad608dff47b8883ed38a"
            ),
            byte_length=8078,
            applied_prefix_digest=(
                "sha256:f057490417dacdcda8a2d79c2326c6ba5117a5241572ad02ccfb881cd1345b96"
            ),
        ),
    ),
    digest="sha256:f057490417dacdcda8a2d79c2326c6ba5117a5241572ad02ccfb881cd1345b96",
)

AUTHORITATIVE_MIGRATION_SETS = (
    TENANT_AUTHORITATIVE_MIGRATION_SET,
    SECURITY_AUDIT_AUTHORITATIVE_MIGRATION_SET,
)


def _lp32(value: bytes) -> bytes:
    if len(value) >= 2**32:
        raise MigrationSetError("migration identity field exceeds the lp32 bound")
    return len(value).to_bytes(4, "big", signed=False) + value


def _ascii(value: str, label: str) -> bytes:
    try:
        return value.encode("ascii", errors="strict")
    except UnicodeEncodeError as exc:
        raise MigrationSetError(f"{label} must contain only ASCII") from exc


def _set_digest(service: MigrationService, migrations: Sequence[Migration]) -> str:
    framed = bytearray(_DIGEST_DOMAIN)
    framed.extend(_lp32(_ascii(service.identity, "service identity")))
    framed.extend(_lp32(_ascii(service.relative_directory, "migration directory")))
    framed.extend(_lp32(_ascii(service.schema_name, "schema name")))
    framed.extend(_lp32(_ascii(service.qualified_ledger, "ledger name")))
    framed.extend(len(migrations).to_bytes(4, "big", signed=False))
    for migration in migrations:
        framed.extend(migration.version.to_bytes(4, "big", signed=False))
        framed.extend(_lp32(_ascii(migration.filename, "migration filename")))
        framed.extend(_lp32(bytes.fromhex(migration.source_sha256.removeprefix("sha256:"))))
        framed.extend(migration.byte_length.to_bytes(8, "big", signed=False))
    return "sha256:" + hashlib.sha256(framed).hexdigest()


def _read_migration(filename: str, source_bytes: bytes, version: int) -> Migration:
    if not source_bytes:
        raise MigrationSetError(f"migration {filename} is empty")
    if source_bytes.startswith(b"\xef\xbb\xbf"):
        raise MigrationSetError(f"migration {filename} must not contain a UTF-8 BOM")
    if b"\x00" in source_bytes:
        raise MigrationSetError(f"migration {filename} contains a NUL byte")
    try:
        source_text = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise MigrationSetError(
            f"migration {filename} is not strict UTF-8"
        ) from exc
    if not source_text.strip():
        raise MigrationSetError(f"migration {filename} contains no SQL text")
    return Migration(
        version=version,
        filename=filename,
        source_bytes=source_bytes,
        source_sha256="sha256:" + hashlib.sha256(source_bytes).hexdigest(),
        byte_length=len(source_bytes),
    )


def revalidate_migration_set(migration_set: MigrationSet) -> None:
    """Recompute every identity before an executor trusts an in-memory set.

    ``MigrationSet`` is frozen, but callers can still construct one directly.
    Execution therefore cannot treat the dataclass itself as provenance from
    :func:`load_migration_set`.
    """

    if not isinstance(migration_set, MigrationSet):
        raise MigrationSetError("migration_set must be a MigrationSet")
    if migration_set.service not in (TENANT_SERVICE, SECURITY_AUDIT_SERVICE):
        raise MigrationSetError("migration set has an unknown service")
    if not isinstance(migration_set.migrations, tuple) or not migration_set.migrations:
        raise MigrationSetError("migration set must contain an exact non-empty tuple")

    rebuilt: list[Migration] = []
    for expected_version, migration in enumerate(migration_set.migrations, start=1):
        if not isinstance(migration, Migration):
            raise MigrationSetError("migration set contains an unknown entry")
        if not isinstance(migration.version, int) or isinstance(migration.version, bool):
            raise MigrationSetError("migration version must be an integer")
        if migration.version != expected_version or migration.version > 9999:
            raise MigrationSetError(
                "migration versions must start at 0001 and remain gap-free"
            )
        match = _MIGRATION_FILENAME.fullmatch(migration.filename)
        if match is None or int(match.group("version")) != migration.version:
            raise MigrationSetError(
                f"migration {migration.version:04d} filename is not exact"
            )
        if expected_version == 1 and migration.filename != "0001_initial.sql":
            raise MigrationSetError("the first migration must be exactly 0001_initial.sql")
        if type(migration.source_bytes) is not bytes:
            raise MigrationSetError(
                f"migration {migration.filename} source must be exact bytes"
            )
        rebuilt_migration = _read_migration(
            migration.filename, migration.source_bytes, migration.version
        )
        if rebuilt_migration != migration:
            raise MigrationSetError(
                f"migration {migration.filename} content identity differs"
            )
        rebuilt.append(rebuilt_migration)

    expected_digest = _set_digest(migration_set.service, rebuilt)
    if migration_set.digest != expected_digest:
        raise MigrationSetError("migration set digest differs from its exact contents")


def _directory_open_flags() -> int:
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise MigrationSetError(
            "migration preflight requires O_DIRECTORY and O_NOFOLLOW support"
        )
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _file_open_flags() -> int:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_NONBLOCK"):
        raise MigrationSetError(
            "migration preflight requires O_NOFOLLOW and O_NONBLOCK support"
        )
    return (
        os.O_RDONLY
        | os.O_NOFOLLOW
        | os.O_NONBLOCK
        | getattr(os, "O_CLOEXEC", 0)
    )


def _descriptor_read_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
    )


def _close_descriptor(file_descriptor: int, label: str) -> None:
    """Close one preflight descriptor without exposing an operating-system error."""

    try:
        os.close(file_descriptor)
    except OSError as exc:
        raise MigrationSetError(f"{label} could not be closed safely") from exc


def _list_migration_directory(directory_fd: int) -> list[str]:
    """List the already-opened directory with one closed diagnostic."""

    try:
        return sorted(os.listdir(directory_fd))
    except OSError as exc:
        raise MigrationSetError(
            "migration directory could not be listed safely"
        ) from exc


def _open_migration_directory(
    package_root: Path, service: MigrationService
) -> int:
    """Open every relative component without following a symlink."""

    try:
        absolute_root = package_root.absolute()
        resolved_root = package_root.resolve(strict=True)
    except OSError as exc:
        raise MigrationSetError("package_root must be an existing directory") from exc
    if absolute_root != resolved_root:
        raise MigrationSetError("package_root must not contain a symlink component")
    if not resolved_root.is_dir():
        raise MigrationSetError("package_root must be an existing directory")

    flags = _directory_open_flags()
    try:
        current_fd = os.open(resolved_root, flags)
    except OSError as exc:
        raise MigrationSetError("package_root could not be opened safely") from exc
    try:
        for component in service.relative_directory.split("/"):
            try:
                next_fd = os.open(component, flags, dir_fd=current_fd)
            except FileNotFoundError as exc:
                raise MigrationSetError(
                    f"migration directory {service.relative_directory} is absent"
                ) from exc
            except OSError as exc:
                raise MigrationSetError(
                    "migration directory contains a symlink or non-directory "
                    f"component: {component}"
                ) from exc
            previous_fd = current_fd
            current_fd = next_fd
            _close_descriptor(previous_fd, "migration directory descriptor")
        result_fd = current_fd
        current_fd = None
        return result_fd
    except BaseException:
        if current_fd is not None:
            _close_descriptor(current_fd, "migration directory descriptor")
        raise


def _read_opened_migration(
    directory_fd: int, filename: str, version: int
) -> Migration:
    """Open once without following links, verify the descriptor, then read it."""

    try:
        source_fd = os.open(filename, _file_open_flags(), dir_fd=directory_fd)
    except OSError as exc:
        raise MigrationSetError(
            f"migration directory contains a non-regular entry: {filename}"
        ) from exc
    try:
        try:
            initial_stat = os.fstat(source_fd)
            if not stat.S_ISREG(initial_stat.st_mode):
                raise MigrationSetError(
                    f"migration directory contains a non-regular entry: {filename}"
                )
            if initial_stat.st_size > MIGRATION_SOURCE_MAX_BYTES:
                raise MigrationSetError(
                    f"migration {filename} exceeds the fixed source byte limit"
                )
            chunks: list[bytes] = []
            remaining = MIGRATION_SOURCE_MAX_BYTES + 1
            while remaining:
                chunk = os.read(source_fd, min(1024 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            source_bytes = b"".join(chunks)
            final_stat = os.fstat(source_fd)
        except OSError as exc:
            raise MigrationSetError(
                f"migration {filename} could not be read safely"
            ) from exc
        if (
            _descriptor_read_identity(final_stat)
            != _descriptor_read_identity(initial_stat)
            or len(source_bytes) != initial_stat.st_size
        ):
            raise MigrationSetError(f"migration {filename} changed while it was read")
        if len(source_bytes) > MIGRATION_SOURCE_MAX_BYTES:
            raise MigrationSetError(
                f"migration {filename} exceeds the fixed source byte limit"
            )
        return _read_migration(filename, source_bytes, version)
    finally:
        _close_descriptor(source_fd, f"migration {filename} descriptor")


def load_migration_set(package_root: Path, service: MigrationService) -> MigrationSet:
    """Load one fixed service directory without adopting untracked entries."""

    if not isinstance(package_root, Path):
        raise MigrationSetError("package_root must be a pathlib.Path")
    if service not in (TENANT_SERVICE, SECURITY_AUDIT_SERVICE):
        raise MigrationSetError("service must be one of the two fixed migration services")

    directory_fd = _open_migration_directory(package_root, service)
    try:
        entry_names = _list_migration_directory(directory_fd)
        numbered: list[tuple[int, str]] = []
        for entry_name in entry_names:
            match = _MIGRATION_FILENAME.fullmatch(entry_name)
            if match is None:
                raise MigrationSetError(
                    f"migration filename is not governed: {entry_name}"
                )
            numbered.append((int(match.group("version")), entry_name))

        if not numbered:
            raise MigrationSetError(
                f"migration directory {service.relative_directory} is empty"
            )
        versions = [version for version, _filename in numbered]
        for version in sorted(set(versions)):
            if versions.count(version) != 1:
                raise MigrationSetError(
                    f"migration version {version:04d} appears more than once"
                )
        numbered.sort(key=lambda item: item[0])
        if numbered[0][1] != "0001_initial.sql":
            raise MigrationSetError(
                "the first migration must be exactly 0001_initial.sql"
            )

        migrations: list[Migration] = []
        for expected_version, (observed_version, filename) in enumerate(
            numbered, start=1
        ):
            if observed_version != expected_version:
                raise MigrationSetError(
                    "migration versions must start at 0001 and remain gap-free: "
                    f"expected {expected_version:04d}, "
                    f"observed {observed_version:04d}"
                )
            migrations.append(
                _read_opened_migration(directory_fd, filename, observed_version)
            )
        if _list_migration_directory(directory_fd) != entry_names:
            raise MigrationSetError("migration directory changed during preflight")
    finally:
        _close_descriptor(directory_fd, "migration directory descriptor")

    exact = tuple(migrations)
    return MigrationSet(
        service=service,
        migrations=exact,
        digest=_set_digest(service, exact),
    )


def _authoritative_set_for(
    service: MigrationService,
) -> AuthoritativeMigrationSet:
    for expected in AUTHORITATIVE_MIGRATION_SETS:
        if service == expected.service:
            return expected
    raise MigrationSetError("service has no authoritative migration release")


def require_authoritative_migration_set(
    migration_set: MigrationSet,
) -> MigrationSet:
    """Refuse any history that is not the literal checked-in release set."""

    revalidate_migration_set(migration_set)
    expected = _authoritative_set_for(migration_set.service)
    observed = tuple(
        AuthoritativeMigration(
            version=migration.version,
            filename=migration.filename,
            source_sha256=migration.source_sha256,
            byte_length=migration.byte_length,
            applied_prefix_digest=migration_set.prefix_digest(migration.version),
        )
        for migration in migration_set.migrations
    )
    if observed != expected.migrations or migration_set.digest != expected.digest:
        raise MigrationSetError(
            "migration set is not the literal authoritative release history"
        )
    return migration_set


def load_authoritative_migration_set(
    package_root: Path,
    service: MigrationService,
) -> MigrationSet:
    """Load and authenticate one operator-facing repository migration set."""

    return require_authoritative_migration_set(
        load_migration_set(package_root, service)
    )


def preflight_main(service: MigrationService, argv: Sequence[str] | None = None) -> int:
    """Emit the canonical manifest for one repository-fixed migration lane."""

    parser = argparse.ArgumentParser(
        description=(
            f"Validate the immutable {service.identity} migration set. "
            "This preflight never connects to PostgreSQL or executes DDL."
        )
    )
    parser.parse_args(argv)
    if service == TENANT_SERVICE:
        # Keep this import local: provisioning specs depend on migration-set
        # identities, while only the operator-facing tenant preflight needs
        # the final native release gate.
        from deployment.postgresql.provisioning_specs import (
            ProvisioningSpecError,
            require_frozen_tenant_native_verifier_authority,
        )

        try:
            require_frozen_tenant_native_verifier_authority()
        except ProvisioningSpecError as exc:
            parser.exit(1, f"migration preflight refused: {exc}\n")
    try:
        migration_set = load_authoritative_migration_set(_PACKAGE_ROOT, service)
    except MigrationSetError as exc:
        parser.exit(2, f"migration preflight refused: {exc}\n")
    print(migration_set.canonical_manifest_bytes().decode("ascii"), end="")
    return 0
