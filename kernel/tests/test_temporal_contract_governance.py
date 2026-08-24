from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest

from conformance import temporal_contract_candidate_check as temporal


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_SELECTION_STORAGE_V7_CATALOG_DIGEST = (
    "sha256:026bb61026a9f752fc8dde84bca0e3cbbab374d0ac8f0ba942a72654e44f5f1a"
)
_SELECTION_STORAGE_V8_CATALOG_DIGEST = (
    "sha256:28aaa41651c1338fec9f8ca6aa7f252b7bef4ef2f3b1760d399306aba69c8719"
)
_SELECTION_STORAGE_V9_CATALOG_DIGEST = (
    "sha256:63439452af1358dcf717abf923e775f3d50f78fd8c8602b633b6dd4b838375c4"
)
_SELECTION_STORAGE_V8_CATALOG_SOURCE_SHA256 = (
    "sha256:130a96edc2b9f4ad92a640c1c34150fe6126bd3945a48704a96896bb88a0f1a7"
)
_SELECTION_STORAGE_V9_CATALOG_SOURCE_SHA256 = (
    "sha256:625935c7342205e1561ed5148826b4e6c866b13a1b4bff33fbc58c5c02f1420c"
)
_SECURITY_AUDIT_V3_CATALOG_DIGEST = (
    "sha256:d897f0a02f851b37f64d883d384e2fa01ee356160553ffb5061f24de4581c074"
)
_SECURITY_AUDIT_V4_CATALOG_DIGEST = (
    "sha256:c5129cccd8ce3e53f427f69963792b40b1d70181577a8d03b370a0a8af1272c8"
)
_GCRC_FORBIDDEN_V0_1 = (
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCoordinate_schema_v0_1.json",
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCarrierMatrix_schema_v0_1.json",
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCarrierMatrix_ADR0002_candidate_v0_1.json",
    "contracts/candidates/temporal_carrier_selection/"
    "OFARM_TemporalCarrierSelectionBinding_schema_v0_1.json",
    "contracts/candidates/temporal_carrier_selection/"
    "OFARM_InterventionValidTimeCarrierSelection_candidate_v0_1.json",
    "contracts/candidates/temporal_governed_command/"
    "OFARM_TemporalGovernedCommandBinding_schema_v0_1.json",
    "contracts/candidates/temporal_governed_command/"
    "OFARM_OperationClaimDraftTemporalCommand_candidate_v0_1.json",
    "contracts/candidates/temporal_runtime_bundle_carrier/"
    "OFARM_TemporalGovernanceRuntimeBundleCarrierBinding_schema_v0_1.json",
    "contracts/candidates/temporal_runtime_bundle_carrier/"
    "OFARM_TemporalGovernanceRuntimeBundleCarrier_candidate_v0_1.json",
    "contracts/candidates/temporal_runtime_bundle_selection/"
    "OFARM_TenantCommandRuntimeBundleSelectionBinding_schema_v0_1.json",
    "contracts/candidates/temporal_runtime_bundle_selection/"
    "OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json",
    "contracts/candidates/temporal_governance_promotion/"
    "OFARM_TemporalGovernancePromotionBinding_schema_v0_1.json",
    "contracts/candidates/temporal_governance_promotion/"
    "OFARM_TemporalGovernancePromotion_candidate_v0_1.json",
    "ofarm.temporal-coordinate.v0.1",
    "ofarm.temporal-carrier-matrix.adr0002.v0.1",
    "ofarm.temporal-carrier-selection.intervention.v0.1",
    "ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1",
    "ofarm.temporal-governance-runtime-bundle-carrier.v0.1",
    "TEMPORAL_GOVERNANCE_ARTIFACT",
    (
        "ofarm.tenant-command-runtime-bundle-selection."
        "commit-operation-claim-draft.v0.1"
    ),
    "ofarm.temporal-governance-promotion.issue176-foundation.v0.1",
    "STRUCTURE_EVENT",
    "OBSERVATION_EVENT",
    "OCCURRENCE_EVENT",
    "INTERVENTION_EVENT",
    "MATERIAL_EVENT",
    "EVIDENCE_EVENT",
    "GOVERNANCE_EVENT",
    "ASSERTION_RECORD",
    "ACCEPTED_EVENT_CONSEQUENCE",
    "REVIEW_AND_GOVERNANCE_RECORDS",
    "POINT_OBSERVATION_PAYLOADS",
    "PARTIAL_EXTENT_TEMPORAL_APPLICABILITY",
    "INTERVAL_STATE_OR_OBSERVATION",
    "PENDING_OR_DISPUTED_ANNEX_ENTRY",
    "EVIDENCE_SUFFICIENCY_CASE",
    "OPERATION_CLAIM",
    "sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f",
    "0008_tenant_command_runtime_bundle_selection.sql",
    "deployment/postgresql/tenant_command_runtime_bundle_selection.py",
    "tenant_command_runtime_bundle_selection",
    "activate_tenant_command_runtime_bundle_selection",
    "COMMIT_OPERATION_CLAIM_DRAFT",
    "kernel.api",
    "kernel.application_runtime",
    "kernel.profiles.si_ffs.outputs",
    "contracts/kernel/OFARM_RuntimeProblem_schema_v0_1.json",
    "kernel.legacy_m1.api",
    "#192",
    "ofarm.security-audit-postgresql.v1",
    "security_audit/",
)


def _coordinate_schema() -> dict:
    return json.loads(
        temporal.COORDINATE_SCHEMA_PATH.read_text(encoding="utf-8")
    )


def _coordinate_validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(
        _coordinate_schema(),
        format_checker=jsonschema.FormatChecker(),
    )


def _carrier_schema() -> dict:
    return json.loads(temporal.CARRIER_SCHEMA_PATH.read_text(encoding="utf-8"))


def _carrier_matrix() -> dict:
    return json.loads(temporal.CARRIER_MATRIX_PATH.read_text(encoding="utf-8"))


def _selection_schema() -> dict:
    return json.loads(
        temporal.SELECTION_SCHEMA_PATH.read_text(encoding="utf-8")
    )


def _selection_binding() -> dict:
    return json.loads(
        temporal.SELECTION_BINDING_PATH.read_text(encoding="utf-8")
    )


def _command_schema() -> dict:
    return json.loads(
        temporal.COMMAND_SCHEMA_PATH.read_text(encoding="utf-8")
    )


def _command_binding() -> dict:
    return json.loads(
        temporal.COMMAND_BINDING_PATH.read_text(encoding="utf-8")
    )


def _runtime_bundle_carrier_schema() -> dict:
    return json.loads(
        temporal.RUNTIME_BUNDLE_CARRIER_SCHEMA_PATH.read_text(
            encoding="utf-8"
        )
    )


def _runtime_bundle_carrier_binding() -> dict:
    return json.loads(
        temporal.RUNTIME_BUNDLE_CARRIER_BINDING_PATH.read_text(
            encoding="utf-8"
        )
    )


def _runtime_bundle_selection_schema() -> dict:
    return json.loads(
        temporal.RUNTIME_BUNDLE_SELECTION_SCHEMA_PATH.read_text(
            encoding="utf-8"
        )
    )


def _runtime_bundle_selection_binding() -> dict:
    return json.loads(
        temporal.RUNTIME_BUNDLE_SELECTION_BINDING_PATH.read_text(
            encoding="utf-8"
        )
    )


def _promotion_schema() -> dict:
    return json.loads(
        temporal.PROMOTION_SCHEMA_PATH.read_text(encoding="utf-8")
    )


def _promotion_binding() -> dict:
    return json.loads(
        temporal.PROMOTION_BINDING_PATH.read_text(encoding="utf-8")
    )


def _migration_authority_source() -> str:
    return temporal.MIGRATION_SET_AUTHORITY_PATH.read_text(encoding="utf-8")


def _role_snapshot(
    *migrations: tuple[str, bytes],
) -> temporal.TenantMigrationAuthoritySnapshot:
    entries = tuple(
        SimpleNamespace(filename=filename, source_bytes=source_bytes)
        for filename, source_bytes in migrations
    )
    return temporal.TenantMigrationAuthoritySnapshot(
        migration_set=SimpleNamespace(migrations=entries),
        version_3_prefix=temporal.KNOWLEDGE_STORAGE_MIGRATION_PREFIX_DIGEST,
    )


def _tenant_literal_source(
    *,
    version_3_entries: int = 1,
    field_overrides: dict[str, object] | None = None,
) -> str:
    fields = {
        "version": 3,
        "filename": temporal.KNOWLEDGE_STORAGE_MIGRATION_FILENAME,
        "source_sha256": (
            f"sha256:{temporal.KNOWLEDGE_STORAGE_MIGRATION_DIGEST}"
        ),
        "byte_length": temporal.KNOWLEDGE_STORAGE_MIGRATION_BYTE_LENGTH,
        "applied_prefix_digest": (
            temporal.KNOWLEDGE_STORAGE_MIGRATION_PREFIX_DIGEST
        ),
    }
    fields.update(field_overrides or {})
    entries = "\n".join(
        (
            "        AuthoritativeMigration(\n"
            f"            version={fields['version']!r},\n"
            f"            filename={fields['filename']!r},\n"
            f"            source_sha256={fields['source_sha256']!r},\n"
            f"            byte_length={fields['byte_length']!r},\n"
            "            applied_prefix_digest="
            f"{fields['applied_prefix_digest']!r},\n"
            "        ),"
        )
        for _ in range(version_3_entries)
    )
    return (
        "TENANT_AUTHORITATIVE_MIGRATION_SET = AuthoritativeMigrationSet(\n"
        "    service=TENANT_SERVICE,\n"
        "    migrations=(\n"
        f"{entries}\n"
        "    ),\n"
        f"    digest={temporal.KNOWLEDGE_STORAGE_MIGRATION_PREFIX_DIGEST!r},\n"
        ")\n"
    )


def _authoritative_tenant_assignment(
    migration_set: object,
    *,
    name: str = "TENANT_AUTHORITATIVE_MIGRATION_SET",
) -> str:
    migrations = getattr(migration_set, "migrations")
    entries = []
    for migration in migrations:
        prefix = migration_set.prefix_digest(migration.version)
        entries.append(
            "        AuthoritativeMigration(\n"
            f"            version={migration.version!r},\n"
            f"            filename={migration.filename!r},\n"
            f"            source_sha256={migration.source_sha256!r},\n"
            f"            byte_length={migration.byte_length!r},\n"
            f"            applied_prefix_digest={prefix!r},\n"
            "        ),"
        )
    return (
        f"{name} = AuthoritativeMigrationSet(\n"
        "    service=TENANT_SERVICE,\n"
        "    migrations=(\n"
        f"{'\n'.join(entries)}\n"
        "    ),\n"
        f"    digest={migration_set.digest!r},\n"
        ")\n"
    )


def _replace_tenant_authority(source: str, assignment: str) -> str:
    start = source.index("TENANT_AUTHORITATIVE_MIGRATION_SET =")
    end = source.index(
        "\n\nSECURITY_AUDIT_AUTHORITATIVE_MIGRATION_SET =",
        start,
    )
    return source[:start] + assignment + source[end:]


def _synthetic_tenant_authority(
    tmp_path: Path,
    extra_migrations: tuple[tuple[str, bytes], ...],
) -> tuple[Path, Path]:
    package_root = tmp_path / "package"
    migration_directory = package_root / "kernel/migrations"
    migration_directory.mkdir(parents=True)
    for version in range(1, 4):
        source_path = PACKAGE_ROOT / "kernel/migrations" / (
            f"{version:04d}_"
            + (
                "initial.sql"
                if version == 1
                else "authentication_read_api.sql"
                if version == 2
                else "tenant_knowledge_position.sql"
            )
        )
        (migration_directory / source_path.name).write_bytes(
            source_path.read_bytes()
        )
    for filename, source_bytes in extra_migrations:
        (migration_directory / filename).write_bytes(source_bytes)

    source = _migration_authority_source()
    module = temporal._execute_migration_authority_source(source)
    migration_set = module.load_migration_set(
        package_root,
        module.TENANT_SERVICE,
    )
    assignment = _authoritative_tenant_assignment(migration_set)
    authority_path = tmp_path / "migration_sets.py"
    authority_path.write_text(
        _replace_tenant_authority(source, assignment),
        encoding="utf-8",
    )
    return package_root, authority_path


def _selection_storage_catalog_source(*, classified: bool) -> bytes:
    relative_path, _module, byte_length, v7_sha256 = (
        temporal.SELECTION_STORAGE_ABSENT_CATALOG_PIN
    )
    current = (PACKAGE_ROOT / relative_path).read_bytes()
    audit_v3_digest = _SECURITY_AUDIT_V3_CATALOG_DIGEST.encode("utf-8")
    audit_v4_digest = _SECURITY_AUDIT_V4_CATALOG_DIGEST.encode("utf-8")
    audit_digest_counts = (
        current.count(audit_v3_digest),
        current.count(audit_v4_digest),
    )
    if audit_digest_counts == (0, 1):
        current = current.replace(audit_v4_digest, audit_v3_digest)
    elif audit_digest_counts != (1, 0):
        raise AssertionError(
            "current security-audit catalog source is not exact V3 or V4"
        )
    v7_digest = _SELECTION_STORAGE_V7_CATALOG_DIGEST.encode("utf-8")
    v8_digest = _SELECTION_STORAGE_V8_CATALOG_DIGEST.encode("utf-8")
    v9_digest = _SELECTION_STORAGE_V9_CATALOG_DIGEST.encode("utf-8")

    if (
        current.count(v7_digest) == 1
        and current.count(v8_digest) == 0
        and current.count(v9_digest) == 0
    ):
        v7_source = current
    elif (
        current.count(v7_digest) == 0
        and current.count(v8_digest) == 1
        and current.count(v9_digest) == 0
    ):
        v7_source = current.replace(v8_digest, v7_digest)
    elif (
        current.count(v7_digest) == 0
        and current.count(v8_digest) == 0
        and current.count(v9_digest) == 1
    ):
        if (
            len(current) != byte_length
            or "sha256:" + hashlib.sha256(current).hexdigest()
            != _SELECTION_STORAGE_V9_CATALOG_SOURCE_SHA256
        ):
            raise AssertionError("current V9 tenant catalog source differs")
        v7_source = current.replace(v9_digest, v7_digest)
    else:
        raise AssertionError(
            "current tenant catalog source is not exact V7, V8, or V9"
        )

    if (
        len(v7_source) != byte_length
        or "sha256:" + hashlib.sha256(v7_source).hexdigest() != v7_sha256
    ):
        raise AssertionError("derived V7 tenant catalog source differs")
    if not classified:
        return v7_source

    v8_source = v7_source.replace(v7_digest, v8_digest)
    if (
        len(v8_source) != byte_length
        or "sha256:" + hashlib.sha256(v8_source).hexdigest()
        != _SELECTION_STORAGE_V8_CATALOG_SOURCE_SHA256
    ):
        raise AssertionError("derived V8 tenant catalog source differs")
    return v8_source


def _selection_storage_source_snapshot(
    tmp_path: Path,
    overrides: dict[str, bytes] | None = None,
):
    selected_overrides = dict(overrides or {})
    package_root = tmp_path / "python-snapshot"
    sources: dict[str, bytes] = {
        "kernel/api.py": b"",
        "kernel/application_runtime.py": b"",
        "kernel/legacy_m1/api.py": b"",
        "kernel/legacy_m1/runtime.py": b"",
        temporal.POSTGRESQL_INITIALIZER_RELATIVE_PATH: b"",
        temporal.TEMPORAL_CANDIDATE_CHECK_RELATIVE_PATH: (
            PACKAGE_ROOT / temporal.TEMPORAL_CANDIDATE_CHECK_RELATIVE_PATH
        ).read_bytes(),
        temporal.TEMPORAL_DECISION_LOG_CHECK_RELATIVE_PATH: (
            PACKAGE_ROOT / temporal.TEMPORAL_DECISION_LOG_CHECK_RELATIVE_PATH
        ).read_bytes(),
    }
    for (
        relative_path,
        _module,
        _length,
        _digest,
    ) in temporal.SELECTION_STORAGE_SOURCE_PINS:
        sources[relative_path] = (PACKAGE_ROOT / relative_path).read_bytes()
    sources[temporal.SELECTION_STORAGE_ABSENT_CATALOG_PIN[0]] = (
        _selection_storage_catalog_source(
            classified=(
                temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH
                in selected_overrides
            )
        )
    )
    sources.update(selected_overrides)
    for relative_path, source_bytes in sources.items():
        path = package_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source_bytes)
    return temporal.architecture.build_python_source_snapshot(package_root)


def _selection_storage_v7_authority(
) -> temporal.TenantMigrationAuthoritySnapshot:
    current = temporal.load_tenant_migration_authority_snapshot()
    migrations = current.migration_set.migrations
    if (
        len(migrations) not in (7, 8, 9)
        or tuple(migration.version for migration in migrations[:7])
        != tuple(range(1, 8))
        or current.migration_set.prefix_digest(7)
        != temporal.SELECTION_STORAGE_V7_DIGEST
    ):
        raise AssertionError("current tenant authority lacks the exact V7 prefix")

    class V7MigrationSet:
        service = current.migration_set.service
        migrations = current.migration_set.migrations[:7]
        digest = temporal.SELECTION_STORAGE_V7_DIGEST

        def prefix_digest(self, version: int) -> str:
            if version == 7:
                return self.digest
            return current.migration_set.prefix_digest(version)

    return temporal.TenantMigrationAuthoritySnapshot(
        migration_set=V7MigrationSet(),
        version_3_prefix=current.version_3_prefix,
    )


def _selection_storage_v8_authority(
    source_bytes: bytes,
) -> temporal.TenantMigrationAuthoritySnapshot:
    v7 = _selection_storage_v7_authority()
    migration_8 = SimpleNamespace(
        version=8,
        filename=temporal.SELECTION_STORAGE_MIGRATION_FILENAME,
        source_bytes=source_bytes,
        source_sha256=(
            "sha256:" + hashlib.sha256(source_bytes).hexdigest()
        ),
        byte_length=len(source_bytes),
    )
    v8_digest = temporal.GLOBAL_CONTENT_RETENTION_V8_PREFIX_DIGEST

    class V8MigrationSet:
        service = v7.migration_set.service
        migrations = (*v7.migration_set.migrations, migration_8)
        digest = v8_digest

        def prefix_digest(self, version: int) -> str:
            if version == 8:
                return self.digest
            return v7.migration_set.prefix_digest(version)

    return temporal.TenantMigrationAuthoritySnapshot(
        migration_set=V8MigrationSet(),
        version_3_prefix=v7.version_3_prefix,
    )


def _global_content_retention_migration_source(
    *,
    extra: bytes = b"",
) -> bytes:
    return (
        "\n".join(
            f"-- {marker}" for marker in temporal._GCRC_REQUIRED_MARKERS
        ).encode("utf-8")
        + b"\n"
        + extra
    )


def _global_content_retention_v9_authority(
    selection_source: bytes,
    retention_source: bytes,
) -> temporal.TenantMigrationAuthoritySnapshot:
    v8 = _selection_storage_v8_authority(selection_source)
    migration_9 = SimpleNamespace(
        version=9,
        filename=temporal.GLOBAL_CONTENT_RETENTION_MIGRATION_FILENAME,
        source_bytes=retention_source,
        source_sha256=(
            "sha256:" + hashlib.sha256(retention_source).hexdigest()
        ),
        byte_length=len(retention_source),
    )
    v9_digest = "sha256:" + "9" * 64

    class V9MigrationSet:
        service = v8.migration_set.service
        migrations = (*v8.migration_set.migrations, migration_9)
        digest = v9_digest

        def prefix_digest(self, version: int) -> str:
            if version == 9:
                return self.digest
            return v8.migration_set.prefix_digest(version)

    return temporal.TenantMigrationAuthoritySnapshot(
        migration_set=V9MigrationSet(),
        version_3_prefix=v8.version_3_prefix,
    )


def _changed_global_content_retention_authority(
    authority: temporal.TenantMigrationAuthoritySnapshot,
    *,
    migrations: tuple[object, ...] | None = None,
    digest: object | None = None,
    prefix_overrides: dict[int, object] | None = None,
) -> temporal.TenantMigrationAuthoritySnapshot:
    selected_migrations = migrations or authority.migration_set.migrations
    selected_digest = digest if digest is not None else authority.migration_set.digest
    overrides = prefix_overrides or {}

    class ChangedMigrationSet:
        service = authority.migration_set.service
        migrations = selected_migrations
        digest = selected_digest

        def prefix_digest(self, version: int) -> str:
            override = overrides.get(version)
            if isinstance(override, Exception):
                raise override
            if override is not None:
                return override
            return authority.migration_set.prefix_digest(version)

    return temporal.TenantMigrationAuthoritySnapshot(
        migration_set=ChangedMigrationSet(),
        version_3_prefix=authority.version_3_prefix,
    )


def _selection_storage_python_markers() -> bytes:
    return (
        "\n".join(
            f"# {marker}" for marker in temporal.SELECTION_STORAGE_MARKERS
        )
        + "\n"
    ).encode("utf-8")


def _publication_adapter_python_markers(
    markers: tuple[str, ...] | None = None,
) -> bytes:
    selected = (
        temporal.PUBLICATION_ADAPTER_REQUIRED_MARKERS
        if markers is None
        else markers
    )
    return ("\n".join(f"# {marker}" for marker in selected) + "\n").encode(
        "utf-8"
    )


def _changed_migration(migration: object, **changes: object) -> SimpleNamespace:
    values = {
        "version": migration.version,
        "filename": migration.filename,
        "source_bytes": migration.source_bytes,
        "source_sha256": migration.source_sha256,
        "byte_length": migration.byte_length,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def _changed_selection_storage_authority(
    *,
    migrations: tuple[object, ...] | None = None,
    digest: object | None = None,
    service: object | None = None,
    prefix_overrides: dict[int, object] | None = None,
) -> temporal.TenantMigrationAuthoritySnapshot:
    current = _selection_storage_v7_authority()
    selected_migrations = migrations or current.migration_set.migrations
    selected_digest = digest if digest is not None else current.migration_set.digest
    selected_service = service or current.migration_set.service
    overrides = prefix_overrides or {}

    class ChangedMigrationSet:
        migrations = selected_migrations
        digest = selected_digest
        service = selected_service

        def prefix_digest(self, version: int) -> str:
            override = overrides.get(version)
            if isinstance(override, Exception):
                raise override
            if override is not None:
                return str(override)
            if version == 8:
                return self.digest
            return current.migration_set.prefix_digest(version)

    return temporal.TenantMigrationAuthoritySnapshot(
        migration_set=ChangedMigrationSet(),
        version_3_prefix=current.version_3_prefix,
    )


def _selection_storage_expected_current_state() -> str:
    authority = temporal.load_tenant_migration_authority_snapshot()
    migrations = authority.migration_set.migrations
    adapter_present = (
        PACKAGE_ROOT / temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH
    ).is_file()
    if len(migrations) == 7 and not adapter_present:
        return temporal.SELECTION_STORAGE_CONFORMANT_ABSENT
    if (
        len(migrations) in (8, 9)
        and migrations[7].version == 8
        and migrations[7].filename
        == temporal.SELECTION_STORAGE_MIGRATION_FILENAME
        and adapter_present
    ):
        if len(migrations) == 8:
            return temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED
        if (
            migrations[8].version == 9
            and migrations[8].filename
            == temporal.GLOBAL_CONTENT_RETENTION_MIGRATION_FILENAME
            and temporal._classify_global_content_retention_migration(
                authority,
                authority.migration_set.prefix_digest(8),
            )
            == temporal.GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED
        ):
            return temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED
    raise AssertionError(
        "current selection-storage pair is not exact V7, V8, or V9"
    )


def _selection_storage_snapshot_view(
    snapshot: object,
    **overrides: object,
) -> SimpleNamespace:
    values = {
        "contract_authority": snapshot.contract_authority,
        "descriptor": snapshot.descriptor,
        "modules_by_relative_path": snapshot.modules_by_relative_path,
        "import_graph": snapshot.import_graph,
        "production_reachability": snapshot.production_reachability,
        "legacy_reachability": snapshot.legacy_reachability,
        "ast_for": snapshot.ast_for,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _coordinate() -> dict:
    return {
        "schemaVersion": temporal.CONTRACT_VERSION,
        "validCut": {
            "cutType": "POINT",
            "validAt": "2026-07-28T10:30:00.123456Z",
        },
        "knowledgeCut": {
            "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
            "position": 42,
        },
    }


def test_temporal_candidate_governance_is_complete_and_inactive():
    temporal.validate_candidate_governance()


def test_temporal_card_errata_trace_is_pinned():
    errata = temporal.ERRATA_PATH.read_text(encoding="utf-8")
    temporal.validate_temporal_card_errata_trace(errata)


@pytest.mark.parametrize(
    "marker",
    temporal.TEMPORAL_CARD_ERRATA_REQUIRED_MARKERS,
)
def test_temporal_card_errata_trace_rejects_modified_marker(marker: str):
    errata = temporal.ERRATA_PATH.read_text(encoding="utf-8")
    assert marker in errata

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="temporal decision-card ERRATA trace markers differ",
    ):
        temporal.validate_temporal_card_errata_trace(
            errata.replace(marker, "tampered", 1)
        )


@pytest.mark.parametrize(
    "mutation",
    ("removed", "duplicate", "spaced_duplicate", "gutted"),
)
def test_temporal_card_errata_trace_rejects_structural_mutation(
    mutation: str,
):
    errata = temporal.ERRATA_PATH.read_text(encoding="utf-8")
    row = next(
        line
        for line in errata.splitlines()
        if temporal._markdown_table_row_identity(line)
        == temporal.TEMPORAL_CARD_ERRATA_ROW_ID
    )
    mutations = {
        "removed": errata.replace(f"{row}\n", "", 1),
        "duplicate": f"{errata}\n{row}\n",
        "spaced_duplicate": (
            f"{errata}\n"
            f"{row.replace('| E-009 |', '|  E-009  |', 1)}\n"
        ),
        "gutted": errata.replace(
            row,
            "| E-009 | x | x | x | x | "
            f"{temporal.TEMPORAL_CARD_ERRATA_CARD_DIGEST} "
            "withdrawn permanently |",
            1,
        ),
    }
    expected_error = (
        "trace markers differ"
        if mutation == "gutted"
        else "row identity differs"
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match=expected_error,
    ):
        temporal.validate_temporal_card_errata_trace(mutations[mutation])


def test_candidate_governance_wires_temporal_card_errata_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    errata = temporal.ERRATA_PATH.read_text(encoding="utf-8")
    row = next(
        line
        for line in errata.splitlines()
        if temporal._markdown_table_row_identity(line)
        == temporal.TEMPORAL_CARD_ERRATA_ROW_ID
    )
    tampered_errata_path = tmp_path / "ERRATA.md"
    tampered_errata_path.write_text(
        errata.replace(f"{row}\n", "", 1),
        encoding="utf-8",
    )

    with monkeypatch.context() as errata_patch:
        errata_patch.setattr(
            temporal,
            "ERRATA_PATH",
            tampered_errata_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="temporal decision-card ERRATA row identity differs",
        ):
            temporal.validate_candidate_governance()


def test_candidate_schemas_and_instances_are_full_draft_2020_12_valid():
    coordinate_schema = _coordinate_schema()
    carrier_schema = _carrier_schema()
    carrier_matrix = _carrier_matrix()
    selection_schema = _selection_schema()
    selection_binding = _selection_binding()
    command_schema = _command_schema()
    command_binding = _command_binding()
    runtime_bundle_carrier_schema = _runtime_bundle_carrier_schema()
    runtime_bundle_carrier_binding = _runtime_bundle_carrier_binding()
    runtime_bundle_selection_schema = _runtime_bundle_selection_schema()
    runtime_bundle_selection_binding = _runtime_bundle_selection_binding()
    promotion_schema = _promotion_schema()
    promotion_binding = _promotion_binding()

    jsonschema.Draft202012Validator.check_schema(coordinate_schema)
    jsonschema.Draft202012Validator.check_schema(carrier_schema)
    jsonschema.Draft202012Validator.check_schema(selection_schema)
    jsonschema.Draft202012Validator.check_schema(command_schema)
    jsonschema.Draft202012Validator.check_schema(
        runtime_bundle_carrier_schema
    )
    jsonschema.Draft202012Validator.check_schema(
        runtime_bundle_selection_schema
    )
    jsonschema.Draft202012Validator.check_schema(promotion_schema)
    jsonschema.Draft202012Validator(carrier_schema).validate(carrier_matrix)
    jsonschema.Draft202012Validator(selection_schema).validate(
        selection_binding
    )
    jsonschema.Draft202012Validator(command_schema).validate(command_binding)
    jsonschema.Draft202012Validator(
        runtime_bundle_carrier_schema
    ).validate(runtime_bundle_carrier_binding)
    jsonschema.Draft202012Validator(
        runtime_bundle_selection_schema
    ).validate(runtime_bundle_selection_binding)
    jsonschema.Draft202012Validator(promotion_schema).validate(
        promotion_binding
    )
    temporal.validate_carrier_matrix(carrier_matrix)
    temporal.validate_selection_schema_shape(selection_schema)
    temporal.validate_selection_binding(selection_binding)
    temporal.validate_command_schema_shape(command_schema, command_binding)
    temporal.validate_command_binding(
        command_binding,
        temporal.load_tenant_migration_authority_snapshot(),
    )
    temporal.validate_runtime_bundle_carrier_schema_shape(
        runtime_bundle_carrier_schema,
        runtime_bundle_carrier_binding,
    )
    temporal.validate_runtime_bundle_carrier_binding(
        runtime_bundle_carrier_binding
    )
    temporal.validate_runtime_bundle_selection_schema_shape(
        runtime_bundle_selection_schema,
        runtime_bundle_selection_binding,
    )
    temporal.validate_runtime_bundle_selection_binding(
        runtime_bundle_selection_binding
    )
    temporal.validate_promotion_schema_shape(
        promotion_schema,
        promotion_binding,
    )
    temporal.validate_promotion_binding(promotion_binding)
    temporal.validate_promotion_dependency_consistency()


def test_point_and_window_coordinates_validate_against_schema_and_semantics():
    point = _coordinate()
    window = copy.deepcopy(point)
    window["validCut"] = {
        "cutType": "WINDOW",
        "windowStart": "2026-01-01T00:00:00Z",
        "windowEnd": "2027-01-01T00:00:00Z",
    }
    window["knowledgeCut"]["position"] = temporal.MAX_KNOWLEDGE_POSITION

    for value in (point, window):
        _coordinate_validator().validate(value)
        temporal.validate_temporal_coordinate(value)


@pytest.mark.parametrize(
    "vector",
    temporal.REFUSAL_VECTORS,
    ids=lambda vector: vector.vector_id,
)
def test_shared_temporal_refusal_vectors(vector):
    value = copy.deepcopy(vector.value)
    with pytest.raises(
        temporal.TemporalCandidateError,
        match=vector.expected_error,
    ):
        vector.validator(value)
    if vector.schema_must_refuse:
        assert list(_coordinate_validator().iter_errors(value))


def test_load_bearing_coordinate_schema_definitions_are_pinned():
    mutations = (
        lambda schema: schema["$defs"]["pointValidCut"].update(
            {"additionalProperties": True}
        ),
        lambda schema: schema["$defs"]["windowValidCut"]["properties"][
            "cutType"
        ].update({"const": "Window"}),
        lambda schema: schema["$defs"]["validCut"]["oneOf"].pop(),
        lambda schema: schema["$defs"]["validInterval"]["required"].clear(),
    )

    for mutation in mutations:
        schema = _coordinate_schema()
        mutation(schema)
        with pytest.raises(temporal.TemporalCandidateError):
            temporal.validate_coordinate_schema_shape(schema)


def test_carrier_matrix_schema_and_adr_rows_are_pinned():
    carrier_schema = _carrier_schema()
    carrier_schema["$defs"]["carrierMatrixRow"]["properties"]["rowId"][
        "enum"
    ].pop()
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="carrierMatrixRow definition differs",
    ):
        temporal.validate_carrier_schema_shape(carrier_schema)

    carrier_matrix = _carrier_matrix()
    carrier_matrix["rows"][0]["rowId"] = carrier_matrix["rows"][1]["rowId"]
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="row identities differ",
    ):
        temporal.validate_carrier_matrix(carrier_matrix)

    carrier_matrix = _carrier_matrix()
    carrier_matrix["rows"][0][
        "authoritativeValidTimeCarrierRule"
    ] = "invented carrier"
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="differs from ADR 0002",
    ):
        temporal.validate_carrier_matrix(carrier_matrix)


def test_temporal_governed_command_is_exact_and_cannot_be_activated_by_mutation():
    schema = _command_schema()
    validator = jsonschema.Draft202012Validator(schema)

    mutations = (
        (
            lambda value: value["command"].update(
                {"routePosture": "OPEN"}
            ),
            "specialization differs",
        ),
        (
            lambda value: value["command"].update(
                {"promotionOutcome": "PROMOTE_ACCEPTED"}
            ),
            "specialization differs",
        ),
        (
            lambda value: value.update(
                {"identityAuthority": "CALLER_SELECTED"}
            ),
            "identity differs",
        ),
        (
            lambda value: value["durableBatch"][
                "newlyWrittenAllowedOutcomes"
            ].append("PROMOTE_ACCEPTED"),
            "batch policy differs",
        ),
        (
            lambda value: value["implementationStops"].clear(),
            "stop conditions differ",
        ),
    )
    for mutation, expected_error in mutations:
        binding = _command_binding()
        mutation(binding)
        assert list(validator.iter_errors(binding))
        with pytest.raises(
            temporal.TemporalCandidateError,
            match=expected_error,
        ):
            temporal.validate_command_binding(
                binding,
                temporal.load_tenant_migration_authority_snapshot(),
            )


def test_runtime_bundle_carrier_is_closed_eligibility_not_required_closure():
    schema = _runtime_bundle_carrier_schema()
    validator = jsonschema.Draft202012Validator(schema)
    mutations = (
        (
            lambda value: value["componentVocabulary"].update(
                {"role": "REFERENCE_SOURCE"}
            ),
            "component vocabulary differs",
        ),
        (
            lambda value: value["allowedIdentities"].append(
                copy.deepcopy(value["allowedIdentities"][0])
            ),
            "allowed identity set differs",
        ),
        (
            # The binding's allowed set is exact even though no RuntimeBundle
            # or role use is required to contain every allowed identity.
            lambda value: value["allowedIdentities"].pop(),
            "allowed identity set differs",
        ),
        (
            lambda value: value["allowedIdentities"][0].update(
                {
                    "canonicalInstanceDigest": value["allowedIdentities"][0][
                        "instanceFileDigest"
                    ]
                }
            ),
            "allowed identity set differs",
        ),
        (
            lambda value: value["closureAuthority"].update(
                {"everyRuntimeBundleRequiresAllAllowedIdentities": True}
            ),
            "component closure authority differs",
        ),
        (
            lambda value: value["closureAuthority"].update(
                {"everyRoleUseRequiresAllAllowedIdentities": True}
            ),
            "component closure authority differs",
        ),
        (
            lambda value: value["candidateIsolation"].update(
                {"runtimeBundleMembership": "SUPPORTED"}
            ),
            "carrier binding differs",
        ),
        (
            lambda value: value["schemaRelationship"].update(
                {"sameRuntimeBundleRequiredWhenInstanceIsUsed": False}
            ),
            "carrier binding differs",
        ),
        (
            lambda value: value["forbiddenContentClasses"].pop(),
            "carrier binding differs",
        ),
        (
            lambda value: value["implementationStops"].clear(),
            "carrier binding differs",
        ),
    )
    for mutation, expected_error in mutations:
        binding = _runtime_bundle_carrier_binding()
        mutation(binding)
        assert list(validator.iter_errors(binding))
        with pytest.raises(
            temporal.TemporalCandidateError,
            match=expected_error,
        ):
            temporal.validate_runtime_bundle_carrier_binding(binding)


def test_tenant_command_runtime_bundle_selection_is_exact_and_inactive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    schema = _runtime_bundle_selection_schema()
    binding = _runtime_bundle_selection_binding()
    validator = jsonschema.Draft202012Validator(schema)

    assert (
        binding["requiredComponentClosure"]["components"]
        == temporal._expected_runtime_bundle_selection_components()
    )
    mutations = (
        (
            lambda value: value["selectionSource"].update(
                {"callerSelectable": True}
            ),
            "source differs",
        ),
        (
            lambda value: value["selectionSource"].update(
                {"lookupKey": ["request.tenantId", "request.bindingId"]}
            ),
            "source differs",
        ),
        (
            lambda value: value["selectionRecord"][
                "authorityBearingFields"
            ].remove("selectionKnowledgePosition"),
            "record authority differs",
        ),
        (
            lambda value: value["selectionRecord"]["stateTransitions"][1].update(
                {"effect": "REPLACE"}
            ),
            "state transitions differ",
        ),
        (
            lambda value: value["resolution"].update(
                {"before": "AFTER_COMMAND_ADMISSION"}
            ),
            "resolution differs",
        ),
        (
            lambda value: value["resolution"].update(
                {"refusalWrites": "ONE_BATCH"}
            ),
            "resolution differs",
        ),
        (
            lambda value: value["governancePrerequisite"].update(
                {"relationship": "REQUIRED_ROLE_MEMBER"}
            ),
            "prerequisite differs",
        ),
        (
            lambda value: value["requiredComponentClosure"][
                "components"
            ].pop(),
            "closure differs",
        ),
        (
            lambda value: value["requiredComponentClosure"]["components"][
                0
            ].update({"role": "REFERENCE_SOURCE"}),
            "closure differs",
        ),
        (
            lambda value: value["requiredComponentClosure"]["components"][
                -1
            ].update({"contentDigest": "sha256:" + ("0" * 64)}),
            "closure differs",
        ),
        (
            lambda value: value["requiredComponentClosure"].update(
                {"unrelatedComponentAuthority": "COMMAND_ADMISSION"}
            ),
            "closure differs",
        ),
        (
            lambda value: value["trustedAuthorities"].pop(),
            "authority map differs",
        ),
        (
            lambda value: value["invariants"].remove(
                "TCRS-017_SELECTION_REFUSAL_IS_NO_WRITE"
            ),
            "invariants differ",
        ),
        (
            lambda value: value["negativeCases"].remove(
                "SELECTION_CHANGES_DURING_COMMAND"
            ),
            "stops differ",
        ),
        (
            lambda value: value["unsupported"].remove(
                "HOT_RELOAD_UPGRADE_SUPERSESSION_OR_ROLLBACK"
            ),
            "stops differ",
        ),
        (
            lambda value: value["implementationStops"].remove(
                "NO_REVIEWED_SELECTION_REFUSAL_PUBLIC_REASON_MAPPING"
            ),
            "stops differ",
        ),
        (
            lambda value: value["implementationStops"].clear(),
            "stops differ",
        ),
    )
    for mutation, expected_error in mutations:
        mutated = copy.deepcopy(binding)
        mutation(mutated)
        assert list(validator.iter_errors(mutated))
        with pytest.raises(
            temporal.TemporalCandidateError,
            match=expected_error,
        ):
            temporal.validate_runtime_bundle_selection_binding(mutated)

    tampered_binding = copy.deepcopy(binding)
    tampered_binding["trustedAuthorities"][1]["separateFrom"].remove(
        "AUTHORIZER"
    )
    tampered_binding_path = tmp_path / "selection-binding.json"
    tampered_binding_path.write_text(
        json.dumps(tampered_binding, indent=2) + "\n",
        encoding="utf-8",
    )
    with monkeypatch.context() as digest_patch:
        digest_patch.setattr(
            temporal,
            "RUNTIME_BUNDLE_SELECTION_BINDING_PATH",
            tampered_binding_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="binding digest differs",
        ):
            temporal.validate_runtime_bundle_selection_binding(
                tampered_binding
            )

    tampered_schema = copy.deepcopy(schema)
    tampered_schema["$comment"] = "tampered"
    tampered_schema_path = tmp_path / "selection-schema.json"
    tampered_schema_path.write_text(
        json.dumps(tampered_schema, indent=2) + "\n",
        encoding="utf-8",
    )
    with monkeypatch.context() as digest_patch:
        digest_patch.setattr(
            temporal,
            "RUNTIME_BUNDLE_SELECTION_SCHEMA_PATH",
            tampered_schema_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="schema digest differs",
        ):
            temporal.validate_runtime_bundle_selection_binding(binding)


def test_temporal_promotion_contract_is_atomic_exact_and_has_no_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    schema = _promotion_schema()
    binding = _promotion_binding()
    validator = jsonschema.Draft202012Validator(schema)

    assert (
        binding["subjectSet"]["subjects"]
        == temporal._expected_promotion_subjects()
    )
    assert binding["promotionMeaning"] == {
        "sourceLifecycleState": "CANDIDATE_INACTIVE",
        "targetLifecycleState": "GOVERNED_INACTIVE",
        "effect": "EXTERNAL_LIFECYCLE_CLASSIFICATION_ONLY",
        "embeddedStatusMeaning": "IMMUTABLE_CREATION_STATE_ATTESTATION",
        "effectiveLifecycleAuthority": (
            "REVIEWED_PROMOTION_DECISION_AND_CURRENTNESS_TRACE"
        ),
        "currentDefaultPromotion": False,
        "runtimeActivation": False,
        "productionReadiness": False,
    }
    mutations = (
        (
            lambda value: value.update({"status": "GOVERNED_INACTIVE"}),
            "identity differs",
        ),
        (
            lambda value: value["subjectSet"]["subjects"].pop(),
            "subject set differs",
        ),
        (
            lambda value: value["subjectSet"]["subjects"].append(
                copy.deepcopy(value["subjectSet"]["subjects"][0])
            ),
            "subject set differs",
        ),
        (
            lambda value: value["subjectSet"]["subjects"].reverse(),
            "subject set differs",
        ),
        (
            lambda value: value["subjectSet"]["subjects"][0].update(
                {"repositoryFileDigest": "sha256:" + ("0" * 64)}
            ),
            "subject set differs",
        ),
        (
            lambda value: value["subjectSet"].update(
                {"partialPromotion": "ALLOW_PARTIAL"}
            ),
            "subject set differs",
        ),
        (
            lambda value: value["decisionContract"]["allowedOutcomes"].append(
                "PROMOTE_ACTIVE"
            ),
            "decision authority differs",
        ),
        (
            lambda value: value["decisionContract"].update(
                {"humanGoverned": False}
            ),
            "decision authority differs",
        ),
        (
            lambda value: value["decisionContract"].update(
                {"contractApprovalIsPromotion": True}
            ),
            "decision authority differs",
        ),
        (
            lambda value: value["decisionContract"].update(
                {"callerSelectable": True}
            ),
            "decision authority differs",
        ),
        (
            lambda value: value["dependencyConsistency"].update(
                {"selectorMatrixRowId": "ASSERTION_RECORD"}
            ),
            "binding differs",
        ),
        (
            lambda value: value["authoritySeparation"].update(
                {"runtimeAuthoritiesUnchanged": False}
            ),
            "binding differs",
        ),
        (
            lambda value: value["invariants"].remove(
                "TGP-003_ATOMIC_DECISION"
            ),
            "invariants or negative cases differ",
        ),
        (
            lambda value: value["negativeCases"].remove(
                "POSITIVE_DECISION_STRONGER_THAN_GOVERNED_INACTIVE"
            ),
            "invariants or negative cases differ",
        ),
        (
            lambda value: value["promotionMeaning"].update(
                {"targetLifecycleState": "CURRENT_DEFAULT"}
            ),
            "binding differs",
        ),
        (
            lambda value: value["unsupported"].remove(
                "CURRENT_DEFAULT_PROMOTION"
            ),
            "binding differs",
        ),
        (
            lambda value: value["implementationStops"].clear(),
            "binding differs",
        ),
        (
            lambda value: value.update({"callerDecision": "PROMOTE"}),
            "unknown fields",
        ),
        (
            lambda value: value.pop("authoritySeparation"),
            "missing fields",
        ),
    )
    for mutation, expected_error in mutations:
        mutated = copy.deepcopy(binding)
        mutation(mutated)
        assert list(validator.iter_errors(mutated))
        with pytest.raises(
            temporal.TemporalCandidateError,
            match=expected_error,
        ):
            temporal.validate_promotion_binding(mutated)

    schema_mutations = (
        (
            lambda value: value.update(
                {"$id": "https://example.invalid/promotion"}
            ),
            "schema shape differs",
        ),
        (
            lambda value: value.update({"title": "Unreviewed promotion"}),
            "schema shape differs",
        ),
        (
            lambda value: value["const"].update(
                {"status": "GOVERNED_INACTIVE"}
            ),
            "schema shape differs",
        ),
        (
            lambda value: value.update({"$comment": "inactive"}),
            "schema posture differs",
        ),
    )
    for mutation, expected_error in schema_mutations:
        mutated_schema = copy.deepcopy(schema)
        mutation(mutated_schema)
        with pytest.raises(
            temporal.TemporalCandidateError,
            match=expected_error,
        ):
            temporal.validate_promotion_schema_shape(
                mutated_schema,
                binding,
            )

    promotion_rfc = temporal.PROMOTION_RFC_PATH.read_text(encoding="utf-8")
    rfc_mutations = (
        promotion_rfc.replace(
            "TGP-003 — Atomic decision.",
            "TGP-003 — Deleted atomic decision.",
            1,
        ),
        promotion_rfc.replace("9504", "9999", 1),
        promotion_rfc.replace("## Required negative cases", "", 1),
    )
    for index, mutated_rfc in enumerate(rfc_mutations):
        mutated_rfc_path = tmp_path / f"promotion-rfc-{index}.md"
        mutated_rfc_path.write_text(mutated_rfc, encoding="utf-8")
        with monkeypatch.context() as rfc_patch:
            rfc_patch.setattr(
                temporal,
                "PROMOTION_RFC_PATH",
                mutated_rfc_path,
            )
            with pytest.raises(
                temporal.TemporalCandidateError,
                match="RFC digest differs",
            ):
                temporal._assert_promotion_rfc_digest()

    tampered_selector = _selection_binding()
    tampered_selector["carrierMatrix"]["rowId"] = "ASSERTION_RECORD"
    tampered_selector_path = tmp_path / "tampered-selector.json"
    tampered_selector_path.write_text(
        json.dumps(tampered_selector, indent=2) + "\n",
        encoding="utf-8",
    )
    with monkeypatch.context() as dependency_patch:
        dependency_patch.setattr(
            temporal,
            "SELECTION_BINDING_PATH",
            tampered_selector_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="exact matrix dependency",
        ):
            temporal.validate_promotion_dependency_consistency()

    malformed_command = _command_binding()
    malformed_command["prerequisites"] = "caller-selected"
    malformed_command_path = tmp_path / "malformed-command.json"
    malformed_command_path.write_text(
        json.dumps(malformed_command, indent=2) + "\n",
        encoding="utf-8",
    )
    with monkeypatch.context() as dependency_patch:
        dependency_patch.setattr(
            temporal,
            "COMMAND_BINDING_PATH",
            malformed_command_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="prerequisites are malformed",
        ):
            temporal.validate_promotion_dependency_consistency()

    tampered_command = _command_binding()
    for prerequisite in tampered_command["prerequisites"]:
        if prerequisite["role"] == "INTERVENTION_VALID_TIME_SELECTION":
            prerequisite["identity"] = "caller-selected"
    tampered_command_path = tmp_path / "tampered-command.json"
    tampered_command_path.write_text(
        json.dumps(tampered_command, indent=2) + "\n",
        encoding="utf-8",
    )
    with monkeypatch.context() as dependency_patch:
        dependency_patch.setattr(
            temporal,
            "COMMAND_BINDING_PATH",
            tampered_command_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="exact selector dependency",
        ):
            temporal.validate_promotion_dependency_consistency()

    temporal.validate_promotion_dependency_consistency()


def test_persistence_admission_authority_is_exactly_pinned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    temporal.validate_persistence_admission_authority()
    authority_bytes = temporal.PERSISTENCE_ADMISSION_RFC_PATH.read_bytes()

    cases = (
        (tmp_path / "missing.md", "authority is missing"),
        (tmp_path / "wrong-length.md", "byte length differs"),
        (tmp_path / "wrong-digest.md", "digest differs"),
    )
    cases[1][0].write_bytes(authority_bytes + b"\n")
    changed_bytes = b"!" + authority_bytes[1:]
    assert len(changed_bytes) == len(authority_bytes)
    cases[2][0].write_bytes(changed_bytes)

    for path, expected_error in cases:
        with monkeypatch.context() as authority_patch:
            authority_patch.setattr(
                temporal,
                "PERSISTENCE_ADMISSION_RFC_PATH",
                path,
            )
            with pytest.raises(
                temporal.TemporalCandidateError,
                match=expected_error,
            ):
                temporal.validate_persistence_admission_authority()


def test_tenant_migration_authority_snapshot_authenticates_stable_v3():
    migration_authority = temporal.load_tenant_migration_authority_snapshot()
    version_3 = migration_authority.migration_set.migrations[2]

    assert version_3.version == 3
    assert version_3.filename == temporal.KNOWLEDGE_STORAGE_MIGRATION_FILENAME
    assert version_3.source_sha256 == (
        f"sha256:{temporal.KNOWLEDGE_STORAGE_MIGRATION_DIGEST}"
    )
    assert version_3.byte_length == (
        temporal.KNOWLEDGE_STORAGE_MIGRATION_BYTE_LENGTH
    )
    assert migration_authority.version_3_prefix == (
        temporal.KNOWLEDGE_STORAGE_MIGRATION_PREFIX_DIGEST
    )


@pytest.mark.parametrize(
    "source",
    (
        "",
        _tenant_literal_source(version_3_entries=0),
        _tenant_literal_source(version_3_entries=2),
        _tenant_literal_source() + _tenant_literal_source(),
        _tenant_literal_source(
            field_overrides={"filename": "0003_substituted.sql"}
        ),
        _tenant_literal_source(
            field_overrides={"source_sha256": "sha256:" + "0" * 64}
        ),
        _tenant_literal_source(field_overrides={"byte_length": 1}),
        _tenant_literal_source(
            field_overrides={"applied_prefix_digest": "sha256:" + "0" * 64}
        ),
    ),
    ids=(
        "missing-assignment",
        "missing-v3",
        "duplicate-v3",
        "duplicate-assignment",
        "filename",
        "source-digest",
        "byte-length",
        "prefix",
    ),
)
def test_tenant_v3_literal_refuses_ambiguous_or_changed_authority(
    source: str,
):
    with pytest.raises(temporal.TemporalCandidateError):
        temporal._parse_tenant_version_3_literal(ast.parse(source))


@pytest.mark.parametrize(
    ("extra_migrations", "should_pass"),
    (
        (
            (
                (
                    temporal.RUNTIME_BUNDLE_PERSISTENCE_MIGRATION_FILENAME,
                    b"-- governed migration without the role\n",
                ),
            ),
            True,
        ),
        (
            (
                (
                    temporal.RUNTIME_BUNDLE_PERSISTENCE_MIGRATION_FILENAME,
                    temporal.RUNTIME_BUNDLE_CARRIER_ROLE.encode("utf-8"),
                ),
            ),
            True,
        ),
        (
            (
                (
                    temporal.RUNTIME_BUNDLE_PERSISTENCE_MIGRATION_FILENAME,
                    b"-- role absent\n",
                ),
                (
                    "0005_later_role.sql",
                    temporal.RUNTIME_BUNDLE_CARRIER_ROLE.encode("utf-8"),
                ),
            ),
            False,
        ),
    ),
    ids=("v4-without-role", "role-only-in-v4", "role-in-v5"),
)
def test_authenticated_release_controls_migration_role_classification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra_migrations: tuple[tuple[str, bytes], ...],
    should_pass: bool,
):
    package_root, authority_path = _synthetic_tenant_authority(
        tmp_path,
        extra_migrations,
    )
    monkeypatch.setattr(temporal, "PACKAGE_ROOT", package_root)
    monkeypatch.setattr(
        temporal,
        "MIGRATION_SET_AUTHORITY_PATH",
        authority_path,
    )
    migration_authority = temporal.load_tenant_migration_authority_snapshot()
    if should_pass:
        temporal.validate_runtime_bundle_carrier_role_posture(
            migration_authority
        )
    else:
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="forbidden authenticated migration authority",
        ):
            temporal.validate_runtime_bundle_carrier_role_posture(
                migration_authority
            )


def test_unlisted_migration_0004_is_refused_by_production_authentication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    package_root, authority_path = _synthetic_tenant_authority(
        tmp_path,
        (
            (
                temporal.RUNTIME_BUNDLE_PERSISTENCE_MIGRATION_FILENAME,
                b"-- unlisted migration\n",
            ),
        ),
    )
    authority_path.write_text(_migration_authority_source(), encoding="utf-8")
    monkeypatch.setattr(temporal, "PACKAGE_ROOT", package_root)
    monkeypatch.setattr(
        temporal,
        "MIGRATION_SET_AUTHORITY_PATH",
        authority_path,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="refused the checked-in release",
    ):
        temporal.load_tenant_migration_authority_snapshot()


def test_named_v3_literal_cannot_mask_loader_selected_v3_substitution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    package_root, authority_path = _synthetic_tenant_authority(
        tmp_path,
        (),
    )
    version_3_path = (
        package_root
        / "kernel/migrations"
        / temporal.KNOWLEDGE_STORAGE_MIGRATION_FILENAME
    )
    version_3_path.write_bytes(version_3_path.read_bytes() + b"\n-- drift\n")

    source = _migration_authority_source()
    module = temporal._execute_migration_authority_source(source)
    substituted_set = module.load_migration_set(
        package_root,
        module.TENANT_SERVICE,
    )
    substituted_assignment = _authoritative_tenant_assignment(
        substituted_set,
        name="TENANT_CURRENT_RELEASE",
    )
    security_marker = "\n\nSECURITY_AUDIT_AUTHORITATIVE_MIGRATION_SET ="
    source = source.replace(
        security_marker,
        f"\n\n{substituted_assignment}{security_marker}",
        1,
    )
    source = source.replace(
        "AUTHORITATIVE_MIGRATION_SETS = (\n"
        "    TENANT_AUTHORITATIVE_MIGRATION_SET,",
        "AUTHORITATIVE_MIGRATION_SETS = (\n"
        "    TENANT_CURRENT_RELEASE,",
        1,
    )
    authority_path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(temporal, "PACKAGE_ROOT", package_root)
    monkeypatch.setattr(
        temporal,
        "MIGRATION_SET_AUTHORITY_PATH",
        authority_path,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="authenticated tenant migration-set version-3 entry differs",
    ):
        temporal.load_tenant_migration_authority_snapshot()


@pytest.mark.parametrize(
    ("source_mutation", "expected_error"),
    (
        (lambda _source: None, "authority is not parseable"),
        (lambda _source: "def malformed(", "authority is not parseable"),
        (
            lambda source: source.replace(
                "def load_authoritative_migration_set(",
                "def unavailable_authoritative_migration_set(",
                1,
            ),
            "authority exports differ",
        ),
        (
            lambda source: source
            + "\ndef load_authoritative_migration_set(package_root, service):\n"
            + "    raise MigrationSetError('synthetic refusal')\n",
            "refused the checked-in release",
        ),
    ),
    ids=(
        "missing-module",
        "malformed-module",
        "missing-loader",
        "migration-set-error",
    ),
)
def test_migration_authority_failures_become_temporal_refusals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_mutation,
    expected_error: str,
):
    authority_path = tmp_path / "migration_sets.py"
    mutated_source = source_mutation(_migration_authority_source())
    if mutated_source is not None:
        authority_path.write_text(mutated_source, encoding="utf-8")
    monkeypatch.setattr(
        temporal,
        "MIGRATION_SET_AUTHORITY_PATH",
        authority_path,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match=expected_error,
    ):
        temporal.load_tenant_migration_authority_snapshot()


def test_complete_check_reads_one_authority_source_and_one_migration_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = _migration_authority_source() + (
        "\n_original_temporal_loader = load_authoritative_migration_set\n"
        "_temporal_loader_calls = 0\n"
        "def load_authoritative_migration_set(package_root, service):\n"
        "    global _temporal_loader_calls\n"
        "    _temporal_loader_calls += 1\n"
        "    if _temporal_loader_calls != 1:\n"
        "        raise MigrationSetError('loader called more than once')\n"
        "    return _original_temporal_loader(package_root, service)\n"
    )
    authority_path = tmp_path / "migration_sets.py"
    authority_path.write_text(source, encoding="utf-8")

    class CountingAuthorityPath:
        def __init__(self, path: Path):
            self.path = path
            self.read_count = 0

        def read_bytes(self) -> bytes:
            self.read_count += 1
            return self.path.read_bytes()

        def __str__(self) -> str:
            return str(self.path)

    counting_path = CountingAuthorityPath(authority_path)
    original_sha256 = temporal._sha256
    original_glob = Path.glob

    def refuse_checker_sql_reread(path: Path) -> str:
        if path.suffix == ".sql":
            raise AssertionError("checker reread migration SQL")
        return original_sha256(path)

    def refuse_migration_glob(path: Path, pattern: str, **kwargs):
        if pattern.endswith(".sql"):
            raise AssertionError("checker performed a migration glob")
        return original_glob(path, pattern, **kwargs)

    monkeypatch.setattr(
        temporal,
        "MIGRATION_SET_AUTHORITY_PATH",
        counting_path,
    )
    monkeypatch.setattr(temporal, "_sha256", refuse_checker_sql_reread)
    monkeypatch.setattr(Path, "glob", refuse_migration_glob)

    temporal.validate_candidate_governance()
    assert counting_path.read_count == 1


@pytest.mark.parametrize(
    "model_text",
    ("# temporal role absent\n", temporal.RUNTIME_BUNDLE_CARRIER_ROLE),
    ids=("role-absent", "role-in-model"),
)
def test_runtime_bundle_role_posture_allows_absent_or_model_only_role(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_text: str,
):
    model_path = tmp_path / "runtime_bundle.py"
    model_path.write_text(model_text, encoding="utf-8")
    repository_path = tmp_path / "runtime_bundle_repository.py"
    repository_path.write_text("# role absent\n", encoding="utf-8")
    schema_path = tmp_path / "schema.sql"
    schema_path.write_text("-- role absent\n", encoding="utf-8")
    monkeypatch.setattr(temporal, "RUNTIME_BUNDLE_MODEL_PATH", model_path)
    monkeypatch.setattr(
        temporal,
        "RUNTIME_BUNDLE_ROLE_FORBIDDEN_AUTHORITY_PATHS",
        (repository_path, schema_path),
    )
    temporal.validate_runtime_bundle_carrier_role_posture(
        temporal.load_tenant_migration_authority_snapshot()
    )


def test_runtime_bundle_role_posture_pins_model_admission_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    migration_authority = temporal.load_tenant_migration_authority_snapshot()
    with monkeypatch.context() as candidate_patch:
        candidate_patch.setattr(
            temporal,
            "RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_PATH",
            tmp_path / "missing-model-admission-rfc.md",
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="model-admission authority is missing",
        ):
            temporal.validate_runtime_bundle_carrier_role_posture(
                migration_authority
            )

    authority_bytes = temporal.RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_PATH.read_bytes()
    wrong_length_path = tmp_path / "wrong-length-model-admission-rfc.md"
    wrong_length_path.write_bytes(authority_bytes + b"\n")
    with monkeypatch.context() as candidate_patch:
        candidate_patch.setattr(
            temporal,
            "RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_PATH",
            wrong_length_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="authority byte length differs",
        ):
            temporal.validate_runtime_bundle_carrier_role_posture(
                migration_authority
            )

    wrong_digest_path = tmp_path / "wrong-digest-model-admission-rfc.md"
    changed_bytes = b"!" + authority_bytes[1:]
    assert len(changed_bytes) == len(authority_bytes)
    wrong_digest_path.write_bytes(changed_bytes)
    with monkeypatch.context() as candidate_patch:
        candidate_patch.setattr(
            temporal,
            "RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_PATH",
            wrong_digest_path,
        )
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="authority digest differs",
        ):
            temporal.validate_runtime_bundle_carrier_role_posture(
                migration_authority
            )


@pytest.mark.parametrize(
    "forbidden_authority",
    ("repository", "schema"),
)
def test_runtime_bundle_role_posture_refuses_each_fixed_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    forbidden_authority: str,
):
    model_path = tmp_path / "runtime_bundle.py"
    model_path.write_text(
        temporal.RUNTIME_BUNDLE_CARRIER_ROLE,
        encoding="utf-8",
    )
    repository_path = tmp_path / "runtime_bundle_repository.py"
    schema_path = tmp_path / "schema.sql"
    for path, authority in (
        (repository_path, "repository"),
        (schema_path, "schema"),
    ):
        path.write_text(
            temporal.RUNTIME_BUNDLE_CARRIER_ROLE
            if authority == forbidden_authority
            else "role absent",
            encoding="utf-8",
        )
    monkeypatch.setattr(temporal, "RUNTIME_BUNDLE_MODEL_PATH", model_path)
    monkeypatch.setattr(
        temporal,
        "RUNTIME_BUNDLE_ROLE_FORBIDDEN_AUTHORITY_PATHS",
        (repository_path, schema_path),
    )
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="explicitly forbidden RuntimeBundle authority",
    ):
        temporal.validate_runtime_bundle_carrier_role_posture(
            temporal.load_tenant_migration_authority_snapshot()
        )


@pytest.mark.parametrize(
    ("filename", "should_pass"),
    (
        (temporal.RUNTIME_BUNDLE_PERSISTENCE_MIGRATION_FILENAME, True),
        ("0005_other.sql", False),
    ),
)
def test_runtime_bundle_role_posture_uses_exact_authenticated_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    should_pass: bool,
):
    model_path = tmp_path / "runtime_bundle.py"
    model_path.write_text(
        temporal.RUNTIME_BUNDLE_CARRIER_ROLE,
        encoding="utf-8",
    )
    repository_path = tmp_path / "runtime_bundle_repository.py"
    repository_path.write_text("# role absent\n", encoding="utf-8")
    schema_path = tmp_path / "schema.sql"
    schema_path.write_text("-- role absent\n", encoding="utf-8")
    monkeypatch.setattr(temporal, "RUNTIME_BUNDLE_MODEL_PATH", model_path)
    monkeypatch.setattr(
        temporal,
        "RUNTIME_BUNDLE_ROLE_FORBIDDEN_AUTHORITY_PATHS",
        (repository_path, schema_path),
    )

    migration_authority = _role_snapshot(
        (
            temporal.KNOWLEDGE_STORAGE_MIGRATION_FILENAME,
            b"-- role absent\n",
        ),
        (filename, temporal.RUNTIME_BUNDLE_CARRIER_ROLE.encode("utf-8")),
    )
    if should_pass:
        temporal.validate_runtime_bundle_carrier_role_posture(
            migration_authority
        )
    else:
        with pytest.raises(
            temporal.TemporalCandidateError,
            match="forbidden authenticated migration authority",
        ):
            temporal.validate_runtime_bundle_carrier_role_posture(
                migration_authority
            )


def test_temporal_candidates_and_role_do_not_enter_active_catalog():
    runtime_catalog = json.loads(
        temporal.RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")
    )
    temporal.validate_non_activation(runtime_catalog)
    assert all(
        path.startswith("contracts/candidates/")
        for path in temporal.CANDIDATE_RELATIVE_PATHS
    )

    contract_catalog = copy.deepcopy(runtime_catalog)
    contract_catalog["contractSchemas"].append(
        temporal.CARRIER_SCHEMA_RELATIVE_PATH
    )
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="RuntimeBundle contracts",
    ):
        temporal.validate_non_activation(contract_catalog)

    mutated_catalog = copy.deepcopy(runtime_catalog)
    mutated_catalog["components"].append(
        {
            "role": "REFERENCE_SOURCE",
            "logicalRef": "candidate:temporal-matrix",
            "path": temporal.CARRIER_MATRIX_RELATIVE_PATH,
            "canonicalization": "EXACT_BYTES_V1",
            "placement": "GLOBAL_IMMUTABLE_CONTENT",
        }
    )
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="runtime component",
    ):
        temporal.validate_non_activation(mutated_catalog)

    role_catalog = copy.deepcopy(runtime_catalog)
    role_catalog["components"].append(
        {
            "logicalRef": "untrusted:temporal-role",
            "relativePath": "kernel/untrusted-temporal-role.json",
            "role": temporal.RUNTIME_BUNDLE_CARRIER_ROLE,
        }
    )
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="active RuntimeBundle catalog",
    ):
        temporal.validate_non_activation(role_catalog)


@pytest.mark.parametrize(
    ("path_attribute", "label"),
    (
        ("ACTIVE_ARTIFACT_SET_PATH", "ActiveArtifactSet"),
        ("CAPABILITY_MANIFEST_PATH", "Capability Manifest"),
    ),
    ids=("active-artifact-set", "capability-manifest"),
)
def test_active_temporal_activation_inputs_refuse_each_exact_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path_attribute: str,
    label: str,
):
    active_path = tmp_path / f"{path_attribute}.json"
    active_path.write_text(
        temporal.RUNTIME_BUNDLE_CARRIER_ROLE,
        encoding="utf-8",
    )
    monkeypatch.setattr(temporal, path_attribute, active_path)

    with pytest.raises(temporal.TemporalCandidateError, match=label):
        temporal.validate_active_temporal_activation_inputs()


def test_active_temporal_activation_inputs_remain_clear():
    temporal.validate_active_temporal_activation_inputs()


def test_candidate_paths_are_not_frozen_or_active_contract_directories():
    for relative_path in temporal.CANDIDATE_RELATIVE_PATHS:
        path = PACKAGE_ROOT / relative_path
        assert path.is_file()
        assert not relative_path.startswith(
            ("contracts/kernel/", "contracts/core/", "contracts/platform/")
        )


def test_publication_conformance_authenticates_self_then_parent(
    monkeypatch: pytest.MonkeyPatch,
):
    observed: list[tuple[str, str]] = []

    def record(
        relative_path: str,
        _byte_length: int,
        _sha256: str,
        _contract_identity: str | None,
        *,
        authority_label: str = "selection-storage",
    ) -> bytes:
        observed.append((relative_path, authority_label))
        return b""

    monkeypatch.setattr(temporal, "_authenticate_authority", record)
    temporal.validate_temporal_runtime_bundle_publication_authorities()

    assert observed == [
        (
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_SELF_RELATIVE_PATH,
            "temporal-runtime-bundle-publication",
        ),
        (
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_PARENT_RELATIVE_PATH,
            "temporal-runtime-bundle-publication",
        ),
    ]


@pytest.mark.parametrize("authority_name", ("self", "parent"))
@pytest.mark.parametrize(
    ("failure", "message"),
    (
        ("missing", "authority is missing"),
        ("symlink", "authority is missing"),
        ("unreadable", "authority is unreadable"),
        ("length", "byte length differs"),
        ("digest", "digest differs"),
        ("identity", "contract identity differs"),
    ),
    ids=("missing", "symlink", "unreadable", "length", "digest", "identity"),
)
def test_publication_conformance_authority_refuses_inexact_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_name: str,
    failure: str,
    message: str,
):
    authorities = {
        "self": (
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_SELF_RELATIVE_PATH,
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_SELF_CONTRACT_IDENTITY,
            "TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_SELF_SHA256",
        ),
        "parent": (
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_PARENT_RELATIVE_PATH,
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_PARENT_CONTRACT_IDENTITY,
            "TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_PARENT_SHA256",
        ),
    }
    for relative_path, _identity, _sha_name in authorities.values():
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((PACKAGE_ROOT / relative_path).read_bytes())

    relative_path, identity, sha_name = authorities[authority_name]
    authority_path = tmp_path / relative_path
    if failure == "missing":
        authority_path.unlink()
    elif failure == "symlink":
        target = authority_path.with_suffix(".target")
        authority_path.replace(target)
        authority_path.symlink_to(target)
    elif failure == "length":
        authority_path.write_bytes(authority_path.read_bytes() + b"\n")
    elif failure == "digest":
        source = authority_path.read_bytes()
        authority_path.write_bytes(bytes((source[0] ^ 1,)) + source[1:])
    elif failure == "identity":
        source = authority_path.read_bytes().replace(
            identity.encode("utf-8"),
            b"x" * len(identity),
        )
        authority_path.write_bytes(source)
        monkeypatch.setattr(
            temporal,
            sha_name,
            "sha256:" + hashlib.sha256(source).hexdigest(),
        )

    if failure == "unreadable":
        original_read_bytes = Path.read_bytes

        def read_bytes(path: Path) -> bytes:
            if path == authority_path:
                raise OSError("unavailable")
            return original_read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", read_bytes)

    monkeypatch.setattr(temporal, "PACKAGE_ROOT", tmp_path)
    with pytest.raises(temporal.TemporalCandidateError, match=message):
        temporal.validate_temporal_runtime_bundle_publication_authorities()


def test_global_content_retention_authenticates_self_then_parent(
    monkeypatch: pytest.MonkeyPatch,
):
    observed: list[tuple[str, str]] = []

    def record(
        relative_path: str,
        _byte_length: int,
        _sha256: str,
        _contract_identity: str | None,
        *,
        authority_label: str = "selection-storage",
    ) -> bytes:
        observed.append((relative_path, authority_label))
        return b""

    monkeypatch.setattr(temporal, "_authenticate_authority", record)
    temporal.validate_global_content_retention_authorities()

    assert observed == [
        (
            temporal.GLOBAL_CONTENT_RETENTION_SELF_RELATIVE_PATH,
            "global-content-retention",
        ),
        (
            temporal.GLOBAL_CONTENT_RETENTION_PARENT_RELATIVE_PATH,
            "global-content-retention",
        ),
    ]


@pytest.mark.parametrize("authority_name", ("self", "parent"))
@pytest.mark.parametrize(
    ("failure", "message"),
    (
        ("missing", "authority is missing"),
        ("symlink", "authority is missing"),
        ("unreadable", "authority is unreadable"),
        ("length", "byte length differs"),
        ("digest", "digest differs"),
        ("identity", "contract identity differs"),
    ),
    ids=("missing", "symlink", "unreadable", "length", "digest", "identity"),
)
def test_global_content_retention_authority_refuses_inexact_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_name: str,
    failure: str,
    message: str,
):
    authorities = {
        "self": (
            temporal.GLOBAL_CONTENT_RETENTION_SELF_RELATIVE_PATH,
            temporal.GLOBAL_CONTENT_RETENTION_SELF_CONTRACT_IDENTITY,
            "GLOBAL_CONTENT_RETENTION_SELF_SHA256",
        ),
        "parent": (
            temporal.GLOBAL_CONTENT_RETENTION_PARENT_RELATIVE_PATH,
            temporal.GLOBAL_CONTENT_RETENTION_PARENT_CONTRACT_IDENTITY,
            "GLOBAL_CONTENT_RETENTION_PARENT_SHA256",
        ),
    }
    for relative_path, _identity, _sha_name in authorities.values():
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((PACKAGE_ROOT / relative_path).read_bytes())

    relative_path, identity, sha_name = authorities[authority_name]
    authority_path = tmp_path / relative_path
    if failure == "missing":
        authority_path.unlink()
    elif failure == "symlink":
        target = authority_path.with_suffix(".target")
        authority_path.replace(target)
        authority_path.symlink_to(target)
    elif failure == "length":
        authority_path.write_bytes(authority_path.read_bytes() + b"\n")
    elif failure == "digest":
        source = authority_path.read_bytes()
        authority_path.write_bytes(bytes((source[0] ^ 1,)) + source[1:])
    elif failure == "identity":
        source = authority_path.read_bytes().replace(
            identity.encode("utf-8"),
            b"x" * len(identity),
        )
        authority_path.write_bytes(source)
        monkeypatch.setattr(
            temporal,
            sha_name,
            "sha256:" + hashlib.sha256(source).hexdigest(),
        )

    if failure == "unreadable":
        original_read_bytes = Path.read_bytes

        def read_bytes(path: Path) -> bytes:
            if path == authority_path:
                raise OSError("unavailable")
            return original_read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", read_bytes)

    monkeypatch.setattr(temporal, "PACKAGE_ROOT", tmp_path)
    with pytest.raises(temporal.TemporalCandidateError, match=message):
        temporal.validate_global_content_retention_authorities()


def test_complete_check_authenticates_retention_before_selection(
    monkeypatch: pytest.MonkeyPatch,
):
    observed: list[str] = []

    class StopAfterSelectionAuthority(Exception):
        pass

    def publication_authority() -> None:
        observed.append("publication")

    def retention_authority() -> None:
        observed.append("retention")

    def selection_authority() -> None:
        observed.append("selection")
        raise StopAfterSelectionAuthority

    monkeypatch.setattr(
        temporal,
        "validate_temporal_runtime_bundle_publication_authorities",
        publication_authority,
    )
    monkeypatch.setattr(
        temporal,
        "validate_global_content_retention_authorities",
        retention_authority,
    )
    monkeypatch.setattr(
        temporal,
        "validate_selection_storage_authorities",
        selection_authority,
    )

    with pytest.raises(StopAfterSelectionAuthority):
        temporal.validate_candidate_governance()
    assert observed == ["publication", "retention", "selection"]


def test_selection_storage_authenticates_amendment_first(
    monkeypatch: pytest.MonkeyPatch,
):
    observed: list[str] = []

    def record(
        relative_path: str,
        _byte_length: int,
        _sha256: str,
        _contract_identity: str | None,
    ) -> bytes:
        observed.append(relative_path)
        if relative_path == temporal.SELECTION_STORAGE_V0_1_RELATIVE_PATH:
            return temporal.SELECTION_STORAGE_PROVISIONING_DIGEST.encode(
                "utf-8"
            )
        return b""

    monkeypatch.setattr(temporal, "_authenticate_authority", record)
    temporal.validate_selection_storage_authorities()

    assert observed[0] == temporal.SELECTION_STORAGE_AMENDMENT_RELATIVE_PATH
    assert observed[1:] == [
        authority[0]
        for authority in temporal.SELECTION_STORAGE_REQUIRED_AUTHORITIES
    ]


def test_selection_storage_provisioning_constant_is_bound_to_v0_1_rfc(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        temporal,
        "SELECTION_STORAGE_PROVISIONING_DIGEST",
        "sha256:" + "0" * 64,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="provisioning contract value differs",
    ):
        temporal.validate_selection_storage_authorities()


@pytest.mark.parametrize(
    ("source_bytes", "byte_length", "sha256", "identity", "message"),
    (
        (b"contract: exact", 16, "sha256:" + "0" * 64, "exact", "byte length"),
        (b"contract: exact", 15, "sha256:" + "0" * 64, "exact", "digest"),
        (
            b"contract: other",
            15,
            "sha256:" + hashlib.sha256(b"contract: other").hexdigest(),
            "exact",
            "contract identity",
        ),
    ),
    ids=("wrong-length", "wrong-digest", "wrong-identity"),
)
def test_selection_storage_authority_refuses_inexact_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_bytes: bytes,
    byte_length: int,
    sha256: str,
    identity: str,
    message: str,
):
    authority = tmp_path / "authority.md"
    authority.write_bytes(source_bytes)
    monkeypatch.setattr(temporal, "PACKAGE_ROOT", tmp_path)

    with pytest.raises(temporal.TemporalCandidateError, match=message):
        temporal._authenticate_authority(
            authority.name,
            byte_length,
            sha256,
            identity,
        )


@pytest.mark.parametrize("posture", ("missing", "symlink"))
def test_selection_storage_authority_refuses_missing_or_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    posture: str,
):
    authority = tmp_path / "authority.md"
    if posture == "symlink":
        target = tmp_path / "target.md"
        target.write_text("exact", encoding="utf-8")
        authority.symlink_to(target)
    monkeypatch.setattr(temporal, "PACKAGE_ROOT", tmp_path)

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="selection-storage authority is missing",
    ):
        temporal._authenticate_authority(
            authority.name,
            5,
            "sha256:" + hashlib.sha256(b"exact").hexdigest(),
            None,
        )


def test_selection_storage_authority_refuses_read_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    authority = tmp_path / "authority.md"
    authority.write_text("exact", encoding="utf-8")
    original_read_bytes = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path == authority:
            raise OSError("unavailable")
        return original_read_bytes(path)

    monkeypatch.setattr(temporal, "PACKAGE_ROOT", tmp_path)
    monkeypatch.setattr(Path, "read_bytes", read_bytes)

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="selection-storage authority is unreadable",
    ):
        temporal._authenticate_authority(
            authority.name,
            5,
            "sha256:" + hashlib.sha256(b"exact").hexdigest(),
            None,
        )


def test_complete_check_uses_one_public_snapshot_and_one_initializer_ast(
    monkeypatch: pytest.MonkeyPatch,
):
    builder_calls: list[Path] = []
    ast_calls: list[str] = []
    original_builder = temporal.architecture.build_python_source_snapshot
    original_ast_for = temporal.architecture.PythonSourceSnapshotV1.ast_for

    def counted_builder(root: Path):
        builder_calls.append(root)
        return original_builder(root)

    def counted_ast_for(snapshot, module_name: str):
        ast_calls.append(module_name)
        return original_ast_for(snapshot, module_name)

    monkeypatch.setattr(
        temporal.architecture,
        "build_python_source_snapshot",
        counted_builder,
    )
    monkeypatch.setattr(
        temporal.architecture.PythonSourceSnapshotV1,
        "ast_for",
        counted_ast_for,
    )

    assert (
        temporal.validate_candidate_governance()
        == _selection_storage_expected_current_state()
    )

    assert builder_calls == [temporal.PACKAGE_ROOT]
    assert ast_calls == [temporal.POSTGRESQL_INITIALIZER_MODULE]


def test_complete_check_propagates_classified_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source_bytes = _selection_storage_python_markers()
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: source_bytes},
    )
    authority = _selection_storage_v8_authority(source_bytes)
    monkeypatch.setattr(
        temporal,
        "load_tenant_migration_authority_snapshot",
        lambda: authority,
    )
    monkeypatch.setattr(
        temporal.architecture,
        "build_python_source_snapshot",
        lambda _root: snapshot,
    )

    assert temporal.validate_candidate_governance() == (
        temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED
    )


def test_complete_check_preserves_classified_output_for_exact_v9(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    selection_source = _selection_storage_python_markers()
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source},
    )
    authority = _global_content_retention_v9_authority(
        selection_source,
        _global_content_retention_migration_source(),
    )
    monkeypatch.setattr(
        temporal,
        "load_tenant_migration_authority_snapshot",
        lambda: authority,
    )
    monkeypatch.setattr(
        temporal.architecture,
        "build_python_source_snapshot",
        lambda _root: snapshot,
    )

    assert temporal.validate_candidate_governance() == (
        temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    (
        (
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            "TEMPORAL CANDIDATE PASS: CONFORMANT_ABSENT",
        ),
        (
            temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED,
            "TEMPORAL CANDIDATE PASS: CONFORMANT_CLASSIFIED",
        ),
    ),
    ids=("absent", "classified"),
)
def test_supported_entrypoint_prints_exact_conformance_state(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    state: str,
    expected: str,
):
    monkeypatch.setattr(temporal, "validate_candidate_governance", lambda: state)
    monkeypatch.setattr(temporal, "validate_semantic_vectors", lambda: None)

    assert temporal.main() == 0
    assert capsys.readouterr().out.strip() == expected


def test_supported_entrypoint_refusal_emits_no_conformant_state(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    def refuse() -> str:
        raise temporal.TemporalCandidateError("refused evidence")

    monkeypatch.setattr(temporal, "validate_candidate_governance", refuse)

    assert temporal.main() == 1
    output = capsys.readouterr().out
    assert output == "TEMPORAL CANDIDATE FAIL: refused evidence\n"
    assert "CONFORMANT_" not in output


def test_selection_storage_current_state_is_exact_absent(tmp_path: Path):
    snapshot = temporal._build_selection_storage_snapshot()
    authority = temporal.load_tenant_migration_authority_snapshot()

    assert temporal._validate_selection_storage_conformance(
        authority,
        snapshot,
    ) == _selection_storage_expected_current_state()

    source_bytes = _selection_storage_python_markers()
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="implementation pair is incomplete",
    ):
        temporal._validate_selection_storage_conformance(
            _selection_storage_v8_authority(source_bytes),
            _selection_storage_source_snapshot(tmp_path),
        )


def test_selection_storage_propagates_public_builder_refusal(
    monkeypatch: pytest.MonkeyPatch,
):
    refusal = temporal.architecture.PythonSourceSnapshotRefusal(
        temporal.architecture.PythonSourceSnapshotRefusalCodeV1.INVALID_ROOT
    )
    monkeypatch.setattr(
        temporal.architecture,
        "build_python_source_snapshot",
        lambda _root: (_ for _ in ()).throw(refusal),
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="public Python source snapshot refused: INVALID_ROOT",
    ):
        temporal._build_selection_storage_snapshot()


def test_selection_storage_refuses_non_public_snapshot_type(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        temporal.architecture,
        "build_python_source_snapshot",
        lambda _root: SimpleNamespace(),
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="snapshot type differs",
    ):
        temporal._build_selection_storage_snapshot()


@pytest.mark.parametrize(
    "mismatch",
    ("authority", "interface", "production-roots", "legacy-roots"),
)
def test_selection_storage_refuses_snapshot_compatibility_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
):
    snapshot = _selection_storage_source_snapshot(tmp_path)
    # This guard requires the exact sealed public type, so a protocol stub
    # cannot reach its defensive authority and descriptor comparisons.
    if mismatch == "authority":
        object.__setattr__(
            snapshot,
            "_contract_authority",
            snapshot.contract_authority._replace(sha256="sha256:" + "0" * 64),
        )
        message = "snapshot authority differs"
    else:
        descriptor_changes = {
            "interface": {"interface_identity": "caller-selected"},
            "production-roots": {
                "production_import_roots": ("kernel.api",),
            },
            "legacy-roots": {
                "legacy_import_roots": ("kernel.legacy_m1.api",),
            },
        }
        object.__setattr__(
            snapshot,
            "_descriptor",
            snapshot.descriptor._replace(**descriptor_changes[mismatch]),
        )
        message = "snapshot descriptor differs"
    monkeypatch.setattr(
        temporal.architecture,
        "build_python_source_snapshot",
        lambda _root: snapshot,
    )

    with pytest.raises(temporal.TemporalCandidateError, match=message):
        temporal._build_selection_storage_snapshot()


def test_selection_storage_exact_synthetic_pair_is_classified(tmp_path: Path):
    source_bytes = _selection_storage_python_markers()
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: source_bytes},
    )
    authority = _selection_storage_v8_authority(source_bytes)

    assert temporal._validate_selection_storage_conformance(
        authority,
        snapshot,
    ) == temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED


def test_global_content_retention_forbidden_vocabulary_is_exact():
    assert temporal._GCRC_FORBIDDEN_MIGRATION_MARKERS == _GCRC_FORBIDDEN_V0_1


def test_global_content_retention_exact_v7_does_not_select_classifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    def unexpected_classifier(*_args: object) -> str:
        raise AssertionError("retention classifier was selected for exact V7")

    monkeypatch.setattr(
        temporal,
        "_classify_global_content_retention_migration",
        unexpected_classifier,
    )

    assert temporal._validate_selection_storage_conformance(
        _selection_storage_v7_authority(),
        _selection_storage_source_snapshot(tmp_path),
    ) == temporal.SELECTION_STORAGE_CONFORMANT_ABSENT


def test_global_content_retention_exact_v8_is_internally_absent():
    selection_source = _selection_storage_python_markers()
    authority = _selection_storage_v8_authority(selection_source)

    assert temporal._classify_global_content_retention_migration(
        authority,
        authority.migration_set.prefix_digest(8),
    ) == temporal.GLOBAL_CONTENT_RETENTION_MIGRATION_ABSENT


def test_global_content_retention_exact_v9_preserves_public_state(
    tmp_path: Path,
):
    selection_source = _selection_storage_python_markers()
    retention_source = _global_content_retention_migration_source()
    authority = _global_content_retention_v9_authority(
        selection_source,
        retention_source,
    )
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source},
    )

    assert temporal._classify_global_content_retention_migration(
        authority,
        authority.migration_set.prefix_digest(8),
    ) == temporal.GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED
    assert temporal._validate_selection_storage_conformance(
        authority,
        snapshot,
    ) == temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED


def test_publication_classifier_constants_are_exact():
    assert temporal.PUBLICATION_ADAPTER_REQUIRED_MARKERS == (
        "ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1",
        "sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f",
        "sha256:ed48914f77bedacdfce32fb621819da7df7701b54d7862477db0a49ceee5cdc6",
        "sha256:c774100b13ad7d3f353148eeceeabd319167846825c7392ebbaca1f4ba62faea",
        "ofarm.retain_runtime_content",
        "ofarm.publish_runtime_bundle",
    )
    assert temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH == (
        "deployment/postgresql/temporal_runtime_bundle_publication.py"
    )
    assert temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_MODULE == (
        "deployment.postgresql.temporal_runtime_bundle_publication"
    )
    assert temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT == (
        "TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT"
    )
    assert temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_CLASSIFIED == (
        "TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_CLASSIFIED"
    )


def test_publication_adapter_is_absent_from_real_conformance_phase_b_tree():
    assert not (
        PACKAGE_ROOT
        / temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH
    ).exists()


def test_publication_classifier_accepts_all_four_lawful_compositions(
    tmp_path: Path,
):
    selection_source = _selection_storage_python_markers()
    retention_source = _global_content_retention_migration_source()
    publication_source = _publication_adapter_python_markers()
    v9 = _global_content_retention_v9_authority(
        selection_source,
        retention_source,
    )
    cases = (
        (
            _selection_storage_v7_authority(),
            _selection_storage_source_snapshot(tmp_path / "v7"),
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
        ),
        (
            _selection_storage_v8_authority(selection_source),
            _selection_storage_source_snapshot(
                tmp_path / "v8",
                {
                    temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: (
                        selection_source
                    )
                },
            ),
            temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED,
        ),
        (
            v9,
            _selection_storage_source_snapshot(
                tmp_path / "v9-absent",
                {
                    temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: (
                        selection_source
                    )
                },
            ),
            temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED,
        ),
        (
            v9,
            _selection_storage_source_snapshot(
                tmp_path / "v9-present",
                {
                    temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: (
                        selection_source
                    ),
                    temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH: (
                        publication_source
                    ),
                },
            ),
            temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED,
        ),
    )

    for authority, snapshot, public_state in cases:
        assert temporal._validate_selection_storage_conformance(
            authority,
            snapshot,
        ) == public_state

    assert temporal._classify_temporal_runtime_bundle_publication_adapter(
        cases[-1][1],
        temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED,
        temporal.GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED,
    ) == temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_CLASSIFIED


@pytest.mark.parametrize("migration_state", ("v7", "v8"))
def test_publication_classifier_refuses_target_before_v9_foundation(
    tmp_path: Path,
    migration_state: str,
):
    selection_source = _selection_storage_python_markers()
    overrides = {
        temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH: (
            _publication_adapter_python_markers()
        )
    }
    if migration_state == "v8":
        overrides[temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH] = (
            selection_source
        )
        authority = _selection_storage_v8_authority(selection_source)
    else:
        authority = _selection_storage_v7_authority()

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="publication foundation state differs",
    ):
        temporal._validate_selection_storage_conformance(
            authority,
            _selection_storage_source_snapshot(tmp_path, overrides),
        )


@pytest.mark.parametrize(
    ("selection_state", "retention_state"),
    (
        (
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            temporal.GLOBAL_CONTENT_RETENTION_MIGRATION_ABSENT,
        ),
        (
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            temporal.GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED,
        ),
        (temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED, None),
    ),
    ids=("v7-with-v8-evidence", "v7-with-v9-evidence", "classified-without-retention"),
)
def test_publication_classifier_refuses_unlawful_internal_composition(
    tmp_path: Path,
    selection_state: str,
    retention_state: str | None,
):
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="publication foundation state differs",
    ):
        temporal._classify_temporal_runtime_bundle_publication_adapter(
            _selection_storage_source_snapshot(tmp_path),
            selection_state,
            retention_state,
        )


@pytest.mark.parametrize(
    ("selection_state", "retention_state", "message"),
    (
        (
            "CALLER_SELECTED",
            None,
            "publication selection state differs",
        ),
        (
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            "CALLER_SELECTED",
            "publication retention state differs",
        ),
    ),
    ids=("selection", "retention"),
)
def test_publication_classifier_refuses_unknown_internal_state(
    tmp_path: Path,
    selection_state: str,
    retention_state: str | None,
    message: str,
):
    with pytest.raises(temporal.TemporalCandidateError, match=message):
        temporal._classify_temporal_runtime_bundle_publication_adapter(
            _selection_storage_source_snapshot(tmp_path),
            selection_state,
            retention_state,
        )


@pytest.mark.parametrize(
    "missing_marker",
    temporal.PUBLICATION_ADAPTER_REQUIRED_MARKERS,
)
def test_publication_classifier_refuses_incomplete_target_conjunction(
    tmp_path: Path,
    missing_marker: str,
):
    selection_source = _selection_storage_python_markers()
    authority = _global_content_retention_v9_authority(
        selection_source,
        _global_content_retention_migration_source(),
    )
    publication_source = _publication_adapter_python_markers(
        tuple(
            marker
            for marker in temporal.PUBLICATION_ADAPTER_REQUIRED_MARKERS
            if marker != missing_marker
        )
    )
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source,
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH: (
                publication_source
            ),
        },
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="publication marker conjunction differs",
    ):
        temporal._validate_selection_storage_conformance(authority, snapshot)


def test_publication_classifier_refuses_exact_path_with_wrong_module(
    tmp_path: Path,
):
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH: (
                _publication_adapter_python_markers()
            )
        },
    )
    units = dict(snapshot.modules_by_relative_path)
    target = units[
        temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH
    ]
    units[
        temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH
    ] = target._replace(module_name="deployment.postgresql.publisher_alias")
    snapshot_view = _selection_storage_snapshot_view(
        snapshot,
        modules_by_relative_path=units,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="publication adapter module differs",
    ):
        temporal._classify_temporal_runtime_bundle_publication_adapter(
            snapshot_view,
            temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED,
            temporal.GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED,
        )


@pytest.mark.parametrize(
    ("legacy_module", "legacy_path"),
    (
        ("kernel.legacy_m1.runtime", "kernel/legacy_m1/runtime.py"),
        ("kernel.store", "kernel/store.py"),
        (
            "kernel.runtime_bundle_repository",
            "kernel/runtime_bundle_repository.py",
        ),
    ),
    ids=(
        "legacy-prefix",
        "exact-legacy-module",
        "runtime-bundle-repository",
    ),
)
def test_publication_classifier_refuses_direct_legacy_dependency(
    tmp_path: Path,
    legacy_module: str,
    legacy_path: str,
):
    selection_source = _selection_storage_python_markers()
    authority = _global_content_retention_v9_authority(
        selection_source,
        _global_content_retention_migration_source(),
    )
    publication_source = (
        _publication_adapter_python_markers()
        + f"import {legacy_module}\n".encode("utf-8")
    )
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source,
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH: (
                publication_source
            ),
            legacy_path: b"",
        },
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="publication adapter imports legacy authority",
    ):
        temporal._validate_selection_storage_conformance(authority, snapshot)


def test_publication_classifier_refuses_alias_path_with_complete_markers(
    tmp_path: Path,
):
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            "deployment/postgresql/publication_alias.py": (
                _publication_adapter_python_markers()
            )
        },
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="publication marker entered an unapproved Python source",
    ):
        temporal._classify_temporal_runtime_bundle_publication_adapter(
            snapshot,
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            None,
        )


@pytest.mark.parametrize(
    "extra_marker",
    temporal.PUBLICATION_ADAPTER_REQUIRED_MARKERS[2:],
)
def test_publication_classifier_refuses_expanded_selection_adapter_owner(
    tmp_path: Path,
    extra_marker: str,
):
    selection_source = (
        _selection_storage_python_markers()
        + f"# {extra_marker}\n".encode("utf-8")
    )
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source},
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="selection adapter publication-marker ownership differs",
    ):
        temporal._classify_temporal_runtime_bundle_publication_adapter(
            snapshot,
            temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED,
            temporal.GLOBAL_CONTENT_RETENTION_MIGRATION_ABSENT,
        )


def test_publication_classifier_accepts_exact_decision_log_owner(
    tmp_path: Path,
):
    lifecycle_marker = temporal.PUBLICATION_ADAPTER_REQUIRED_MARKERS[2]
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.TEMPORAL_DECISION_LOG_CHECK_RELATIVE_PATH: (
                f"# {lifecycle_marker}\n".encode("utf-8")
            )
        },
    )

    assert temporal._classify_temporal_runtime_bundle_publication_adapter(
        snapshot,
        temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
        None,
    ) == temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT


@pytest.mark.parametrize(
    "changed_marker",
    (None,)
    + tuple(
        marker
        for index, marker in enumerate(
            temporal.PUBLICATION_ADAPTER_REQUIRED_MARKERS
        )
        if index != 2
    ),
    ids=("missing-lifecycle", "binding-identity", "binding-digest", "bundle-digest", "retention", "publish"),
)
def test_publication_classifier_refuses_changed_decision_log_owner(
    tmp_path: Path,
    changed_marker: str | None,
):
    lifecycle_marker = temporal.PUBLICATION_ADAPTER_REQUIRED_MARKERS[2]
    markers = () if changed_marker is None else (lifecycle_marker, changed_marker)
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.TEMPORAL_DECISION_LOG_CHECK_RELATIVE_PATH: (
                _publication_adapter_python_markers(markers)
            )
        },
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="decision-log checker publication-marker ownership differs",
    ):
        temporal._classify_temporal_runtime_bundle_publication_adapter(
            snapshot,
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            None,
        )


def test_publication_classifier_checker_constants_never_satisfy_target(
    tmp_path: Path,
):
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.TEMPORAL_CANDIDATE_CHECK_RELATIVE_PATH: (
                _publication_adapter_python_markers()
            )
        },
    )

    assert temporal._classify_temporal_runtime_bundle_publication_adapter(
        snapshot,
        temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
        None,
    ) == temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT


def test_publication_classifier_refuses_incomplete_checker_constants(
    tmp_path: Path,
):
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.TEMPORAL_CANDIDATE_CHECK_RELATIVE_PATH: (
                _publication_adapter_python_markers(
                    temporal.PUBLICATION_ADAPTER_REQUIRED_MARKERS[:-1]
                )
            )
        },
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="temporal checker publication-marker ownership differs",
    ):
        temporal._classify_temporal_runtime_bundle_publication_adapter(
            snapshot,
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            None,
        )


@pytest.mark.parametrize(
    "missing_path",
    (
        temporal.TEMPORAL_CANDIDATE_CHECK_RELATIVE_PATH,
        temporal.TEMPORAL_DECISION_LOG_CHECK_RELATIVE_PATH,
    ),
    ids=("temporal-checker", "decision-log-checker"),
)
def test_publication_classifier_refuses_missing_marker_owner_evidence(
    tmp_path: Path,
    missing_path: str,
):
    snapshot = _selection_storage_source_snapshot(tmp_path)
    units = dict(snapshot.modules_by_relative_path)
    units.pop(missing_path)
    snapshot_view = _selection_storage_snapshot_view(
        snapshot,
        modules_by_relative_path=units,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="publication marker-owner evidence is missing",
    ):
        temporal._classify_temporal_runtime_bundle_publication_adapter(
            snapshot_view,
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            None,
        )


def test_publication_classifier_kernel_test_markers_never_satisfy_target(
    tmp_path: Path,
):
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            "kernel/tests/publication_fixture.py": (
                _publication_adapter_python_markers()
            )
        },
    )

    assert temporal._classify_temporal_runtime_bundle_publication_adapter(
        snapshot,
        temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
        None,
    ) == temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT


@pytest.mark.parametrize(
    "marker",
    temporal.PUBLICATION_ADAPTER_REQUIRED_MARKERS,
)
def test_publication_classifier_refuses_marker_in_every_other_source_class(
    tmp_path: Path,
    marker: str,
):
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            "profile_si_ffs/tests/publication_fixture.py": (
                f"# {marker}\n".encode("utf-8")
            )
        },
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="publication marker entered an unapproved Python source",
    ):
        temporal._classify_temporal_runtime_bundle_publication_adapter(
            snapshot,
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            None,
        )


def test_publication_classifier_refuses_malformed_snapshot_unit(
    tmp_path: Path,
):
    snapshot = _selection_storage_source_snapshot(tmp_path)
    units = dict(snapshot.modules_by_relative_path)
    path = temporal.POSTGRESQL_INITIALIZER_RELATIVE_PATH
    units[path] = units[path]._replace(source_text=object())
    snapshot_view = _selection_storage_snapshot_view(
        snapshot,
        modules_by_relative_path=units,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="publication source unit differs",
    ):
        temporal._classify_temporal_runtime_bundle_publication_adapter(
            snapshot_view,
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            None,
        )


def test_publication_classifier_reuses_one_retention_result_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    selection_source = _selection_storage_python_markers()
    authority = _global_content_retention_v9_authority(
        selection_source,
        _global_content_retention_migration_source(),
    )
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source},
    )
    retention_calls: list[tuple[object, str]] = []
    publication_calls: list[tuple[object, str, str | None]] = []
    original_retention = temporal._classify_global_content_retention_migration
    original_publication = (
        temporal._classify_temporal_runtime_bundle_publication_adapter
    )

    def retention_classifier(
        selected_authority: object,
        prefix: str,
    ) -> str:
        retention_calls.append((selected_authority, prefix))
        return original_retention(selected_authority, prefix)

    def publication_classifier(
        selected_snapshot: object,
        selection_state: str,
        retention_state: str | None,
    ) -> str:
        publication_calls.append(
            (selected_snapshot, selection_state, retention_state)
        )
        return original_publication(
            selected_snapshot,
            selection_state,
            retention_state,
        )

    monkeypatch.setattr(
        temporal,
        "_classify_global_content_retention_migration",
        retention_classifier,
    )
    monkeypatch.setattr(
        temporal,
        "_classify_temporal_runtime_bundle_publication_adapter",
        publication_classifier,
    )

    assert temporal._validate_selection_storage_conformance(
        authority,
        snapshot,
    ) == temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED
    assert retention_calls == [
        (authority, temporal.GLOBAL_CONTENT_RETENTION_V8_PREFIX_DIGEST)
    ]
    assert publication_calls == [
        (
            snapshot,
            temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED,
            temporal.GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED,
        )
    ]


@pytest.mark.parametrize("missing_marker", temporal._GCRC_REQUIRED_MARKERS)
def test_global_content_retention_refuses_incomplete_required_markers(
    tmp_path: Path,
    missing_marker: str,
):
    selection_source = _selection_storage_python_markers()
    retention_source = (
        "\n".join(
            f"-- {marker}"
            for marker in temporal._GCRC_REQUIRED_MARKERS
            if marker != missing_marker
        )
        + "\n"
    ).encode("utf-8")
    authority = _global_content_retention_v9_authority(
        selection_source,
        retention_source,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="required marker pair differs",
    ):
        temporal._validate_selection_storage_conformance(
            authority,
            _selection_storage_source_snapshot(
                tmp_path,
                {
                    temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: (
                        selection_source
                    )
                },
            ),
        )


def test_global_content_retention_refuses_marker_in_earlier_migration(
    tmp_path: Path,
):
    selection_source = _selection_storage_python_markers()
    authority = _global_content_retention_v9_authority(
        selection_source,
        _global_content_retention_migration_source(),
    )
    migrations = authority.migration_set.migrations
    source = (
        migrations[0].source_bytes
        + b"\n-- "
        + temporal._GCRC_REQUIRED_MARKERS[0].encode("utf-8")
        + b"\n"
    )
    changed = _changed_migration(
        migrations[0],
        source_bytes=source,
        source_sha256="sha256:" + hashlib.sha256(source).hexdigest(),
        byte_length=len(source),
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="marker entered an earlier migration",
    ):
        temporal._validate_selection_storage_conformance(
            _changed_global_content_retention_authority(
                authority,
                migrations=(changed, *migrations[1:]),
            ),
            _selection_storage_source_snapshot(
                tmp_path,
                {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source},
            ),
        )


@pytest.mark.parametrize("forbidden_marker", _GCRC_FORBIDDEN_V0_1)
def test_global_content_retention_refuses_every_forbidden_marker(
    tmp_path: Path,
    forbidden_marker: str,
):
    selection_source = _selection_storage_python_markers()
    authority = _global_content_retention_v9_authority(
        selection_source,
        _global_content_retention_migration_source(
            extra=f"-- {forbidden_marker}\n".encode("utf-8")
        ),
    )
    message = (
        "selection-storage marker entered another authenticated migration"
        if forbidden_marker in temporal.SELECTION_STORAGE_MARKERS
        else "contains a forbidden marker"
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match=message,
    ):
        temporal._validate_selection_storage_conformance(
            authority,
            _selection_storage_source_snapshot(
                tmp_path,
                {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source},
            ),
        )


def test_global_content_retention_refuses_wrong_v9_filename(tmp_path: Path):
    selection_source = _selection_storage_python_markers()
    authority = _global_content_retention_v9_authority(
        selection_source,
        _global_content_retention_migration_source(),
    )
    migrations = authority.migration_set.migrations
    changed = _changed_migration(
        migrations[8],
        filename="0009_other.sql",
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="version 0009 identity differs",
    ):
        temporal._validate_selection_storage_conformance(
            _changed_global_content_retention_authority(
                authority,
                migrations=(*migrations[:8], changed),
            ),
            _selection_storage_source_snapshot(
                tmp_path,
                {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source},
            ),
        )


@pytest.mark.parametrize(
    ("failure", "digest", "prefix_overrides", "message"),
    (
        (
            "v8-drift",
            None,
            {8: "sha256:" + "0" * 64},
            "fixed V8 prefix differs",
        ),
        (
            "v9-error",
            None,
            {9: ValueError("unavailable")},
            "version-9 prefix authentication failed",
        ),
        (
            "v9-non-string",
            None,
            {9: 9},
            "version-9 migration-set identity differs",
        ),
        (
            "digest-mismatch",
            "sha256:" + "7" * 64,
            {},
            "version-9 migration-set identity differs",
        ),
        (
            "digest-equals-v8",
            temporal.GLOBAL_CONTENT_RETENTION_V8_PREFIX_DIGEST,
            {9: temporal.GLOBAL_CONTENT_RETENTION_V8_PREFIX_DIGEST},
            "version-9 migration-set identity differs",
        ),
    ),
    ids=(
        "v8-drift",
        "v9-prefix-error",
        "v9-prefix-non-string",
        "v9-digest-mismatch",
        "v9-digest-equals-v8",
    ),
)
def test_global_content_retention_refuses_prefix_or_digest_drift(
    tmp_path: Path,
    failure: str,
    digest: object | None,
    prefix_overrides: dict[int, object],
    message: str,
):
    del failure
    selection_source = _selection_storage_python_markers()
    authority = _global_content_retention_v9_authority(
        selection_source,
        _global_content_retention_migration_source(),
    )

    with pytest.raises(temporal.TemporalCandidateError, match=message):
        temporal._validate_selection_storage_conformance(
            _changed_global_content_retention_authority(
                authority,
                digest=digest,
                prefix_overrides=prefix_overrides,
            ),
            _selection_storage_source_snapshot(
                tmp_path,
                {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source},
            ),
        )


def test_global_content_retention_refuses_nondeterministic_v9_prefix(
    tmp_path: Path,
):
    selection_source = _selection_storage_python_markers()
    authority = _global_content_retention_v9_authority(
        selection_source,
        _global_content_retention_migration_source(),
    )
    calls = 0

    class DivergentMigrationSet:
        service = authority.migration_set.service
        migrations = authority.migration_set.migrations
        digest = authority.migration_set.digest

        def prefix_digest(self, version: int) -> str:
            nonlocal calls
            if version == 9:
                calls += 1
                if calls == 2:
                    return "sha256:" + "0" * 64
            return authority.migration_set.prefix_digest(version)

    changed = temporal.TenantMigrationAuthoritySnapshot(
        migration_set=DivergentMigrationSet(),
        version_3_prefix=authority.version_3_prefix,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="version-9 migration-set identity differs",
    ):
        temporal._validate_selection_storage_conformance(
            changed,
            _selection_storage_source_snapshot(
                tmp_path,
                {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source},
            ),
        )


def test_global_content_retention_refuses_production_python_marker(
    tmp_path: Path,
):
    selection_source = _selection_storage_python_markers()
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source,
            "profile_si_ffs/retention_publisher.py": (
                f"# {temporal._GCRC_REQUIRED_MARKERS[0]}\n".encode("utf-8")
            ),
        },
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="marker entered production Python source",
    ):
        temporal._validate_selection_storage_conformance(
            _selection_storage_v8_authority(selection_source),
            snapshot,
        )


def test_selection_storage_classified_state_still_checks_initializer_ast(
    tmp_path: Path,
):
    source_bytes = _selection_storage_python_markers()
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: source_bytes,
            temporal.POSTGRESQL_INITIALIZER_RELATIVE_PATH: (
                b"from . import tenant_command_runtime_bundle_selection\n"
            ),
        },
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="initializer imports",
    ):
        temporal._validate_selection_storage_conformance(
            _selection_storage_v8_authority(source_bytes),
            snapshot,
        )


@pytest.mark.parametrize(
    ("root_path", "label"),
    (
        ("kernel/api.py", "production"),
        ("kernel/legacy_m1/api.py", "legacy"),
    ),
    ids=("production", "legacy"),
)
def test_selection_storage_refuses_adapter_in_fixed_reachability(
    tmp_path: Path,
    root_path: str,
    label: str,
):
    source_bytes = _selection_storage_python_markers()
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: source_bytes,
            root_path: (
                b"import deployment.postgresql."
                b"tenant_command_runtime_bundle_selection\n"
            ),
        },
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match=f"{label} import closure",
    ):
        temporal._validate_selection_storage_conformance(
            _selection_storage_v8_authority(source_bytes),
            snapshot,
        )


@pytest.mark.parametrize(
    ("root_path", "label"),
    (
        ("kernel/api.py", "production"),
        ("kernel/legacy_m1/api.py", "legacy"),
    ),
    ids=("production", "legacy"),
)
def test_publication_classifier_refuses_adapter_in_fixed_reachability(
    tmp_path: Path,
    root_path: str,
    label: str,
):
    selection_source = _selection_storage_python_markers()
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: selection_source,
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH: (
                _publication_adapter_python_markers()
            ),
            root_path: (
                b"import deployment.postgresql."
                b"temporal_runtime_bundle_publication\n"
            ),
        },
    )
    authority = _global_content_retention_v9_authority(
        selection_source,
        _global_content_retention_migration_source(),
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match=f"publication adapter entered the {label} import closure",
    ):
        temporal._validate_selection_storage_conformance(authority, snapshot)


@pytest.mark.parametrize(
    ("root_path", "verification_path", "label"),
    (
        ("kernel/api.py", "kernel/tests/selection_fixture.py", "production"),
        (
            "kernel/legacy_m1/api.py",
            "kernel/tests/selection_fixture.py",
            "legacy",
        ),
    ),
    ids=("production", "legacy"),
)
def test_selection_storage_refuses_verification_source_in_fixed_reachability(
    tmp_path: Path,
    root_path: str,
    verification_path: str,
    label: str,
):
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            root_path: b"import kernel.tests.selection_fixture\n",
            verification_path: b"",
        },
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match=f"verification source entered the {label} import closure",
    ):
        temporal._validate_selection_storage_conformance(
            _selection_storage_v7_authority(),
            snapshot,
        )


@pytest.mark.parametrize(
    ("reachability", "message"),
    (
        (object(), "reachability map differs"),
        ({}, "reachability root entry differs"),
        ({"root": ()}, "reachability root entry differs"),
        (
            {"root": ("root",), "module": ("outside", "module")},
            "reachability path structure differs",
        ),
        (
            {"root": ("root",), "module": ("root", "other")},
            "reachability path structure differs",
        ),
    ),
    ids=(
        "not-a-map",
        "missing-root",
        "empty-root-path",
        "wrong-path-start",
        "wrong-path-end",
    ),
)
def test_selection_storage_refuses_inexact_reachability_structure(
    reachability: object,
    message: str,
):
    with pytest.raises(temporal.TemporalCandidateError, match=message):
        temporal._validate_reachability_map(reachability, ("root",), "fixed")


@pytest.mark.parametrize("present_half", ("adapter", "migration"))
def test_selection_storage_refuses_partial_implementation_pair(
    tmp_path: Path,
    present_half: str,
):
    source_bytes = _selection_storage_python_markers()
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: source_bytes,
        }
        if present_half == "adapter"
        else None,
    )
    authority = (
        _selection_storage_v7_authority()
        if present_half == "adapter"
        else _selection_storage_v8_authority(source_bytes)
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="implementation pair is incomplete",
    ):
        temporal._validate_selection_storage_conformance(authority, snapshot)


def test_selection_storage_refuses_wrong_v8_filename(tmp_path: Path):
    source_bytes = _selection_storage_python_markers()
    authority = _selection_storage_v8_authority(source_bytes)
    migrations = authority.migration_set.migrations
    changed_v8 = _changed_migration(
        migrations[7],
        filename="0008_other.sql",
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="version 0008 filename differs",
    ):
        temporal._validate_selection_storage_conformance(
            _changed_selection_storage_authority(
                migrations=(*migrations[:7], changed_v8),
                digest=authority.migration_set.digest,
            ),
            _selection_storage_source_snapshot(
                tmp_path,
                {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: source_bytes},
            ),
        )


@pytest.mark.parametrize("incomplete_side", ("migration", "adapter"))
def test_selection_storage_refuses_incomplete_marker_pair(
    tmp_path: Path,
    incomplete_side: str,
):
    complete = _selection_storage_python_markers()
    incomplete = f"# {temporal.SELECTION_STORAGE_MARKERS[0]}\n".encode()
    migration_source = incomplete if incomplete_side == "migration" else complete
    adapter_source = incomplete if incomplete_side == "adapter" else complete

    with pytest.raises(
        temporal.TemporalCandidateError,
        match=f"{incomplete_side} marker pair differs",
    ):
        temporal._validate_selection_storage_conformance(
            _selection_storage_v8_authority(migration_source),
            _selection_storage_source_snapshot(
                tmp_path,
                {
                    temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: (
                        adapter_source
                    )
                },
            ),
        )


def test_selection_storage_refuses_marker_in_other_migration(tmp_path: Path):
    current = _selection_storage_v7_authority()
    source_bytes = (
        current.migration_set.migrations[0].source_bytes
        + b"\n-- "
        + temporal.SELECTION_STORAGE_MARKERS[0].encode()
        + b"\n"
    )
    changed = _changed_migration(
        current.migration_set.migrations[0],
        source_bytes=source_bytes,
        source_sha256="sha256:" + hashlib.sha256(source_bytes).hexdigest(),
        byte_length=len(source_bytes),
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="marker entered another authenticated migration",
    ):
        temporal._validate_selection_storage_conformance(
            _changed_selection_storage_authority(
                migrations=(changed, *current.migration_set.migrations[1:]),
            ),
            _selection_storage_source_snapshot(tmp_path),
        )


@pytest.mark.parametrize("state", ("too-short", "too-long", "noncontiguous"))
def test_selection_storage_refuses_invalid_migration_state(
    tmp_path: Path,
    state: str,
):
    current = _selection_storage_v7_authority()
    migrations = current.migration_set.migrations
    if state == "too-short":
        changed = migrations[:6]
        message = "not exact V7, V8, or V9"
    elif state == "too-long":
        changed = (
            *migrations,
            migrations[-1],
            migrations[-1],
            migrations[-1],
        )
        message = "not exact V7, V8, or V9"
    else:
        changed = (
            _changed_migration(migrations[0], version=2),
            *migrations[1:],
        )
        message = "versions are not contiguous"

    with pytest.raises(temporal.TemporalCandidateError, match=message):
        temporal._validate_selection_storage_conformance(
            _changed_selection_storage_authority(migrations=changed),
            _selection_storage_source_snapshot(tmp_path),
        )


@pytest.mark.parametrize("field", ("byte_length", "source_sha256"))
def test_selection_storage_refuses_migration_byte_identity_drift(
    tmp_path: Path,
    field: str,
):
    current = _selection_storage_v7_authority()
    migration = current.migration_set.migrations[0]
    change = {
        "byte_length": migration.byte_length + 1,
        "source_sha256": "sha256:" + "0" * 64,
    }[field]
    changed = _changed_migration(migration, **{field: change})

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="authenticated migration bytes differ",
    ):
        temporal._validate_selection_storage_conformance(
            _changed_selection_storage_authority(
                migrations=(changed, *current.migration_set.migrations[1:]),
            ),
            _selection_storage_source_snapshot(tmp_path),
        )


@pytest.mark.parametrize("version", (3, 7))
def test_selection_storage_refuses_migration_prefix_drift(
    tmp_path: Path,
    version: int,
):
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="stable migration prefix differs",
    ):
        temporal._validate_selection_storage_conformance(
            _changed_selection_storage_authority(
                prefix_overrides={version: "sha256:" + "0" * 64},
            ),
            _selection_storage_source_snapshot(tmp_path),
        )


def test_selection_storage_refuses_retained_v3_authority_drift(tmp_path: Path):
    current = _changed_selection_storage_authority()
    changed = temporal.TenantMigrationAuthoritySnapshot(
        migration_set=current.migration_set,
        version_3_prefix="sha256:" + "0" * 64,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="stable migration prefix differs",
    ):
        temporal._validate_selection_storage_conformance(
            changed,
            _selection_storage_source_snapshot(tmp_path),
        )


def test_selection_storage_refuses_prefix_authentication_failure(tmp_path: Path):
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="prefix authentication failed",
    ):
        temporal._validate_selection_storage_conformance(
            _changed_selection_storage_authority(
                prefix_overrides={3: ValueError("unavailable")},
            ),
            _selection_storage_source_snapshot(tmp_path),
        )


def test_selection_storage_refuses_absent_migration_set_identity_drift(
    tmp_path: Path,
):
    with pytest.raises(
        temporal.TemporalCandidateError,
        match="exact V7 absent authority differs",
    ):
        temporal._validate_selection_storage_conformance(
            _changed_selection_storage_authority(digest="sha256:" + "0" * 64),
            _selection_storage_source_snapshot(tmp_path),
        )


def test_selection_storage_refuses_absent_structural_digest_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        temporal,
        "SELECTION_STORAGE_V7_STRUCTURAL_DIGEST",
        "sha256:" + "0" * 64,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="exact V7 absent authority differs",
    ):
        temporal._validate_selection_storage_conformance(
            _selection_storage_v7_authority(),
            _selection_storage_source_snapshot(tmp_path),
        )


def test_selection_storage_refuses_marker_in_other_production_source(
    tmp_path: Path,
):
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            "profile_si_ffs/tests/selection_leak.py": (
                f"# {temporal.SELECTION_STORAGE_MARKERS[0]}\n".encode(
                    "utf-8"
                )
            )
        },
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="another production Python source",
    ):
        temporal._validate_selection_storage_conformance(
            _selection_storage_v7_authority(),
            snapshot,
        )


def test_selection_storage_verification_marker_never_satisfies_pair(
    tmp_path: Path,
):
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            "kernel/tests/selection_fixture.py": (
                _selection_storage_python_markers()
            )
        },
    )

    assert temporal._validate_selection_storage_conformance(
        _selection_storage_v7_authority(),
        snapshot,
    ) == temporal.SELECTION_STORAGE_CONFORMANT_ABSENT


@pytest.mark.parametrize(
    "initializer_source",
    (
        "import deployment.postgresql.tenant_command_runtime_bundle_selection\n",
        (
            "from deployment.postgresql import "
            "tenant_command_runtime_bundle_selection\n"
        ),
        "from . import tenant_command_runtime_bundle_selection\n",
        (
            "from .tenant_command_runtime_bundle_selection "
            "import selected_binding\n"
        ),
        "from ..postgresql import tenant_command_runtime_bundle_selection\n",
        (
            "from ..postgresql.tenant_command_runtime_bundle_selection "
            "import selected_binding\n"
        ),
        (
            "def nested():\n"
            "    from . import tenant_command_runtime_bundle_selection as selected\n"
        ),
        (
            "class Nested:\n"
            "    from . import tenant_command_runtime_bundle_selection\n"
        ),
        (
            "if TYPE_CHECKING:\n"
            "    from .tenant_command_runtime_bundle_selection import *\n"
        ),
    ),
    ids=(
        "absolute-import",
        "absolute-from",
        "relative-from-package",
        "relative-from-adapter",
        "parent-relative-from-package",
        "parent-relative-from-adapter",
        "nested-alias",
        "class-scope",
        "type-checking-star",
    ),
)
@pytest.mark.parametrize(
    "state",
    (
        temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
        temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED,
    ),
)
def test_selection_storage_refuses_every_initializer_import_form(
    tmp_path: Path,
    initializer_source: str,
    state: str,
):
    source_bytes = _selection_storage_python_markers()
    overrides = {
        temporal.POSTGRESQL_INITIALIZER_RELATIVE_PATH: (
            initializer_source.encode("utf-8")
        )
    }
    if state == temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED:
        overrides[temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH] = source_bytes
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        overrides,
    )
    authority = (
        _selection_storage_v8_authority(source_bytes)
        if state == temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED
        else _selection_storage_v7_authority()
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="initializer imports",
    ):
        temporal._validate_selection_storage_conformance(
            authority,
            snapshot,
        )


@pytest.mark.parametrize(
    "initializer_source",
    (
        "import deployment.postgresql.temporal_runtime_bundle_publication\n",
        (
            "from deployment.postgresql import "
            "temporal_runtime_bundle_publication\n"
        ),
        "from . import temporal_runtime_bundle_publication\n",
        (
            "from .temporal_runtime_bundle_publication "
            "import publish_runtime_bundle\n"
        ),
        "from ..postgresql import temporal_runtime_bundle_publication\n",
        (
            "from ..postgresql.temporal_runtime_bundle_publication "
            "import publish_runtime_bundle\n"
        ),
        (
            "def nested():\n"
            "    from . import temporal_runtime_bundle_publication as publisher\n"
        ),
        (
            "class Nested:\n"
            "    from . import temporal_runtime_bundle_publication\n"
        ),
        (
            "if TYPE_CHECKING:\n"
            "    from .temporal_runtime_bundle_publication import *\n"
        ),
    ),
    ids=(
        "absolute-import",
        "absolute-from",
        "relative-from-package",
        "relative-from-adapter",
        "parent-relative-from-package",
        "parent-relative-from-adapter",
        "nested-alias",
        "class-scope",
        "type-checking-star",
    ),
)
@pytest.mark.parametrize(
    "target_present",
    (False, True),
    ids=("absent", "present"),
)
def test_publication_classifier_refuses_every_initializer_import_form(
    tmp_path: Path,
    initializer_source: str,
    target_present: bool,
):
    overrides = {
        temporal.POSTGRESQL_INITIALIZER_RELATIVE_PATH: (
            initializer_source.encode("utf-8")
        )
    }
    if target_present:
        selection_source = _selection_storage_python_markers()
        overrides.update(
            {
                temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: (
                    selection_source
                ),
                temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH: (
                    _publication_adapter_python_markers()
                ),
            }
        )
        authority = _global_content_retention_v9_authority(
            selection_source,
            _global_content_retention_migration_source(),
        )
    else:
        authority = _selection_storage_v7_authority()
    snapshot = _selection_storage_source_snapshot(tmp_path, overrides)

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="initializer imports",
    ):
        temporal._validate_selection_storage_conformance(
            authority,
            snapshot,
        )


@pytest.mark.parametrize("missing", ("path", "graph"))
def test_selection_storage_refuses_missing_initializer_evidence(
    tmp_path: Path,
    missing: str,
):
    snapshot = _selection_storage_source_snapshot(tmp_path)
    if missing == "path":
        units = dict(snapshot.modules_by_relative_path)
        units.pop(temporal.POSTGRESQL_INITIALIZER_RELATIVE_PATH)
        snapshot_view = _selection_storage_snapshot_view(
            snapshot,
            modules_by_relative_path=units,
        )
    else:
        graph = dict(snapshot.import_graph)
        graph.pop(temporal.POSTGRESQL_INITIALIZER_MODULE)
        snapshot_view = _selection_storage_snapshot_view(
            snapshot,
            import_graph=graph,
        )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="initializer snapshot evidence differs",
    ):
        temporal._validate_initializer_import_prohibition(
            snapshot_view,
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT,
        )


def test_selection_storage_refuses_initializer_module_identity_drift(
    tmp_path: Path,
):
    snapshot = _selection_storage_source_snapshot(tmp_path)
    units = dict(snapshot.modules_by_relative_path)
    unit = units[temporal.POSTGRESQL_INITIALIZER_RELATIVE_PATH]
    units[temporal.POSTGRESQL_INITIALIZER_RELATIVE_PATH] = unit._replace(
        module_name="deployment.other"
    )
    snapshot_view = _selection_storage_snapshot_view(
        snapshot,
        modules_by_relative_path=units,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="initializer snapshot evidence differs",
    ):
        temporal._validate_initializer_import_prohibition(
            snapshot_view,
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT,
        )


@pytest.mark.parametrize("failure", ("refusal", "wrong-type"))
def test_selection_storage_refuses_initializer_ast_custody_failure(
    tmp_path: Path,
    failure: str,
):
    snapshot = _selection_storage_source_snapshot(tmp_path)
    if failure == "refusal":
        refusal = temporal.architecture.PythonSourceSnapshotRefusal(
            temporal.architecture.PythonSourceSnapshotRefusalCodeV1.AST_COPY_LIMIT_EXCEEDED
        )

        def ast_for(_module: str) -> ast.Module:
            raise refusal

        message = "initializer AST custody failed"
    else:
        def ast_for(_module: str) -> ast.Module:
            return ast.Constant(value=None)  # type: ignore[return-value]

        message = "initializer AST type differs"
    snapshot_view = _selection_storage_snapshot_view(
        snapshot,
        ast_for=ast_for,
    )

    with pytest.raises(temporal.TemporalCandidateError, match=message):
        temporal._validate_initializer_import_prohibition(
            snapshot_view,
            temporal.SELECTION_STORAGE_CONFORMANT_ABSENT,
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT,
        )


def test_selection_storage_refuses_classified_initializer_graph_edge(
    tmp_path: Path,
):
    source_bytes = _selection_storage_python_markers()
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: source_bytes},
    )
    graph = dict(snapshot.import_graph)
    graph[temporal.POSTGRESQL_INITIALIZER_MODULE] = (
        temporal.architecture.PythonImportEdgeV1(
            1,
            temporal.SELECTION_STORAGE_ADAPTER_MODULE,
        ),
    )
    snapshot_view = _selection_storage_snapshot_view(
        snapshot,
        import_graph=graph,
        ast_for=lambda _module: ast.parse(""),
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="initializer graph reaches",
    ):
        temporal._validate_initializer_import_prohibition(
            snapshot_view,
            temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED,
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT,
        )


def test_publication_classifier_refuses_classified_initializer_graph_edge(
    tmp_path: Path,
):
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH: (
                _publication_adapter_python_markers()
            )
        },
    )
    graph = dict(snapshot.import_graph)
    graph[temporal.POSTGRESQL_INITIALIZER_MODULE] = (
        temporal.architecture.PythonImportEdgeV1(
            1,
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_MODULE,
        ),
    )
    snapshot_view = _selection_storage_snapshot_view(
        snapshot,
        import_graph=graph,
        ast_for=lambda _module: ast.parse(""),
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="initializer graph reaches the publication adapter",
    ):
        temporal._validate_initializer_import_prohibition(
            snapshot_view,
            temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED,
            temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_CLASSIFIED,
        )


@pytest.mark.parametrize(
    "pin",
    temporal.SELECTION_STORAGE_SOURCE_PINS,
    ids=("provisioning-specs", "native-release-source", "tenant-contract"),
)
def test_selection_storage_source_pin_refuses_drift(
    tmp_path: Path,
    pin: tuple[str, str, int, str],
):
    relative_path = pin[0]
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {relative_path: (PACKAGE_ROOT / relative_path).read_bytes() + b"\n"},
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="Python source pin differs",
    ):
        temporal._validate_selection_storage_conformance(
            _selection_storage_v7_authority(),
            snapshot,
        )


def test_selection_storage_absent_catalog_pin_refuses_drift(tmp_path: Path):
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {temporal.SELECTION_STORAGE_ABSENT_CATALOG_PIN[0]: b"# drift\n"},
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="Python source pin differs",
    ):
        temporal._validate_selection_storage_conformance(
            _selection_storage_v7_authority(),
            snapshot,
        )


def test_selection_storage_absent_catalog_digest_refuses_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        temporal,
        "SELECTION_STORAGE_V7_CATALOG_DIGEST",
        "sha256:" + "0" * 64,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="V7 catalog authority differs",
    ):
        temporal._validate_selection_storage_conformance(
            _selection_storage_v7_authority(),
            _selection_storage_source_snapshot(tmp_path),
        )


@pytest.mark.parametrize("version", range(3, 8))
def test_selection_storage_v7_source_pin_refuses_drift(
    tmp_path: Path,
    version: int,
):
    current = _selection_storage_v7_authority()
    migrations = list(current.migration_set.migrations)
    migrations[version - 1] = _changed_migration(
        migrations[version - 1],
        filename=f"{version:04d}_other.sql",
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match=f"migration {version:04d} differs",
    ):
        temporal._validate_selection_storage_conformance(
            _changed_selection_storage_authority(migrations=tuple(migrations)),
            _selection_storage_source_snapshot(tmp_path),
        )


def test_selection_storage_classified_migration_set_identity_refuses_drift(
    tmp_path: Path,
):
    source_bytes = _selection_storage_python_markers()
    v8 = _selection_storage_v8_authority(source_bytes)

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="V8 migration-set identity differs",
    ):
        temporal._validate_selection_storage_conformance(
            _changed_selection_storage_authority(
                migrations=v8.migration_set.migrations,
                digest=temporal.SELECTION_STORAGE_V7_DIGEST,
                prefix_overrides={
                    8: temporal.GLOBAL_CONTENT_RETENTION_V8_PREFIX_DIGEST
                },
            ),
            _selection_storage_source_snapshot(
                tmp_path,
                {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: source_bytes},
            ),
        )


@pytest.mark.parametrize(
    ("failure", "message"),
    (
        ("prefix-error", "V8 migration authentication failed"),
        ("non-string-digest", "V8 migration-set identity differs"),
        ("digest-mismatch", "V8 migration-set identity differs"),
    ),
)
def test_selection_storage_refuses_classified_v8_identity_failure(
    tmp_path: Path,
    failure: str,
    message: str,
):
    source_bytes = _selection_storage_python_markers()
    v8 = _selection_storage_v8_authority(source_bytes)
    digest: object = v8.migration_set.digest
    prefix_overrides: dict[int, object] = {}
    if failure == "prefix-error":
        prefix_overrides[8] = ValueError("unavailable")
    elif failure == "non-string-digest":
        digest = 8
        prefix_overrides[8] = temporal.GLOBAL_CONTENT_RETENTION_V8_PREFIX_DIGEST
    else:
        digest = "sha256:" + "9" * 64
        prefix_overrides[8] = temporal.GLOBAL_CONTENT_RETENTION_V8_PREFIX_DIGEST

    with pytest.raises(temporal.TemporalCandidateError, match=message):
        temporal._validate_selection_storage_conformance(
            _changed_selection_storage_authority(
                migrations=v8.migration_set.migrations,
                digest=digest,
                prefix_overrides=prefix_overrides,
            ),
            _selection_storage_source_snapshot(
                tmp_path,
                {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: source_bytes},
            ),
        )


def test_selection_storage_classified_adapter_module_refuses_drift(
    tmp_path: Path,
):
    source_bytes = _selection_storage_python_markers()
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: source_bytes},
    )
    units = dict(snapshot.modules_by_relative_path)
    unit = units[temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH]
    units[temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH] = unit._replace(
        module_name="deployment.postgresql.other"
    )
    snapshot_view = _selection_storage_snapshot_view(
        snapshot,
        modules_by_relative_path=units,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="adapter module identity differs",
    ):
        temporal._classify_selection_storage_pair(
            _selection_storage_v8_authority(source_bytes),
            snapshot_view,
        )


@pytest.mark.parametrize(
    "field",
    (
        "identity",
        "relative_directory",
        "schema_name",
        "ledger_name",
        "qualified_ledger",
    ),
)
def test_selection_storage_refuses_inexact_tenant_service(
    tmp_path: Path,
    field: str,
):
    service_values = {
        "identity": "ofarm.tenant-postgresql.v1",
        "relative_directory": "kernel/migrations",
        "schema_name": "ofarm",
        "ledger_name": "schema_migration",
        "qualified_ledger": "ofarm.schema_migration",
    }
    service_values[field] = "caller-selected"
    changed = _changed_selection_storage_authority(
        service=SimpleNamespace(**service_values)
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="migration service differs",
    ):
        temporal._validate_selection_storage_conformance(
            changed,
            _selection_storage_source_snapshot(tmp_path),
        )


def test_selection_storage_lexical_root_is_not_normalized(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        temporal,
        "PACKAGE_ROOT",
        PACKAGE_ROOT / "kernel" / "..",
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="public Python source snapshot refused",
    ):
        temporal._build_selection_storage_snapshot()


def test_selection_storage_ordinary_lexical_root_matches_builder_custody(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    expected = _selection_storage_source_snapshot(tmp_path)
    monkeypatch.setattr(temporal, "PACKAGE_ROOT", expected.root_path)

    snapshot = temporal._build_selection_storage_snapshot()

    assert snapshot.root_path == expected.root_path


def test_selection_storage_symlinked_root_refuses_custody_divergence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    expected = _selection_storage_source_snapshot(tmp_path)
    symlinked_root = tmp_path / "symlinked-python-snapshot"
    symlinked_root.symlink_to(expected.root_path, target_is_directory=True)
    monkeypatch.setattr(temporal, "PACKAGE_ROOT", symlinked_root)

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="public Python source snapshot refused: SYMLINK_COMPONENT",
    ):
        temporal._build_selection_storage_snapshot()


def test_classified_state_does_not_evaluate_obsolete_v7_catalog_pin(
    tmp_path: Path,
):
    source_bytes = _selection_storage_python_markers()
    snapshot = _selection_storage_source_snapshot(
        tmp_path,
        {
            temporal.SELECTION_STORAGE_ADAPTER_RELATIVE_PATH: source_bytes,
            temporal.SELECTION_STORAGE_ABSENT_CATALOG_PIN[0]: b"# V8 owner\n",
        },
    )

    assert temporal._validate_selection_storage_conformance(
        _selection_storage_v8_authority(source_bytes),
        snapshot,
    ) == temporal.SELECTION_STORAGE_CONFORMANT_CLASSIFIED


@pytest.mark.parametrize(
    "changed_index",
    range(3),
    ids=("runtime-catalog", "active-set", "capability-manifest"),
)
@pytest.mark.parametrize(
    "marker",
    (
        temporal.SELECTION_STORAGE_MARKERS[1],
        temporal._GCRC_REQUIRED_MARKERS[0],
        temporal.PUBLICATION_ADAPTER_REQUIRED_MARKERS[0],
        *temporal.PUBLICATION_ADAPTER_REQUIRED_MARKERS[2:],
        temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH,
        temporal.TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_MODULE,
    ),
    ids=(
        "selection",
        "global-content-retention",
        "binding-identity",
        "lifecycle-digest",
        "bundle-digest",
        "retention",
        "publish",
        "publication-path",
        "publication-module",
    ),
)
def test_selection_storage_active_authority_refuses_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_index: int,
    marker: str,
):
    active_paths = tuple(tmp_path / f"active-{index}.json" for index in range(3))
    for index, active_path in enumerate(active_paths):
        active_path.write_text(
            marker if index == changed_index else "{}",
            encoding="utf-8",
        )
    monkeypatch.setattr(
        temporal,
        "SELECTION_STORAGE_ACTIVE_NON_PYTHON_PATHS",
        active_paths,
    )

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="entered active path",
    ):
        temporal._validate_selection_storage_active_authorities()


@pytest.mark.parametrize(
    "changed_index",
    range(3),
    ids=("runtime-catalog", "active-set", "capability-manifest"),
)
@pytest.mark.parametrize(
    "failure",
    ("missing", "read-error", "invalid-utf8"),
)
def test_selection_storage_active_authority_refuses_unreadable_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_index: int,
    failure: str,
):
    active_paths = tuple(tmp_path / f"active-{index}.json" for index in range(3))
    for index, active_path in enumerate(active_paths):
        if index != changed_index or failure != "missing":
            active_path.write_bytes(
                b"\xff" if index == changed_index and failure == "invalid-utf8"
                else b"{}"
            )
    monkeypatch.setattr(
        temporal,
        "SELECTION_STORAGE_ACTIVE_NON_PYTHON_PATHS",
        active_paths,
    )
    if failure == "read-error":
        refused_path = active_paths[changed_index]
        original_read_text = Path.read_text

        def read_text(
            path: Path,
            *args: object,
            **kwargs: object,
        ) -> str:
            if path == refused_path:
                raise OSError("unavailable")
            return original_read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)

    with pytest.raises(
        temporal.TemporalCandidateError,
        match="active selection-storage authority is unreadable",
    ):
        temporal._validate_selection_storage_active_authorities()


def test_selection_storage_evidence_uses_retained_sources_only():
    evidence_source = "\n".join(
        inspect.getsource(function)
        for function in (
            temporal._validate_source_pin,
            temporal._classify_selection_storage_pair,
            temporal._classify_global_content_retention_migration,
            temporal._classify_temporal_runtime_bundle_publication_adapter,
            temporal._validate_global_content_retention_python_isolation,
            temporal._validate_selection_storage_isolation,
            temporal._validate_selection_storage_conformance,
        )
    )
    checker_source = (
        PACKAGE_ROOT / "conformance/temporal_contract_candidate_check.py"
    ).read_text(encoding="utf-8")
    carrier_source = (
        PACKAGE_ROOT / "kernel/tests/test_temporal_carriers.py"
    ).read_text(encoding="utf-8")

    assert "importlib" not in evidence_source
    assert "exec(" not in evidence_source
    assert "native_release_identity.json" not in evidence_source
    assert "native_evidence_receipt.json" not in evidence_source
    assert ".resolve()" not in checker_source
    assert ".resolve()" not in carrier_source
    assert "modules_by_name" not in inspect.getsource(
        temporal._classify_selection_storage_pair
    )
    publication_classifier_source = inspect.getsource(
        temporal._classify_temporal_runtime_bundle_publication_adapter
    )
    for forbidden_operation in (
        "ast_for(",
        "ast.parse(",
        "importlib",
        ".read_bytes(",
        ".read_text(",
        ".glob(",
        ".rglob(",
        "open(",
    ):
        assert forbidden_operation not in publication_classifier_source
    assert (
        "TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH"
        not in inspect.getsource(temporal._is_python_marker_exemption)
    )
    assert inspect.getsource(
        temporal._validate_selection_storage_conformance
    ).count("_classify_temporal_runtime_bundle_publication_adapter(") == 1
    for private_name in (
        "_module_sources",
        "_import_graph",
        "_reachable_paths",
        "PRODUCTION_IMPORT_ROOTS",
        "LEGACY_IMPORT_ROOTS",
        "_from_import_base",
        "FIXED_PRODUCTION_ROOTS",
        "FIXED_LEGACY_ROOTS",
    ):
        assert private_name not in checker_source
        assert private_name not in carrier_source

    root_families = {
        ("kernel.api", "kernel.application_runtime"),
        ("kernel.legacy_m1.api", "kernel.legacy_m1.runtime"),
    }
    checker_tree = ast.parse(checker_source)
    assigned_tuple_values = {
        tuple(element.value for element in node.value.elts)
        for node in ast.walk(checker_tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and isinstance(node.value, ast.Tuple)
        and all(
            isinstance(element, ast.Constant) and type(element.value) is str
            for element in node.value.elts
        )
    }
    assert assigned_tuple_values.isdisjoint(root_families)

    retained_snapshot_consumers = "\n".join(
        inspect.getsource(function)
        for function in (
            temporal._validate_source_pin,
            temporal._classify_selection_storage_pair,
            temporal._classify_global_content_retention_migration,
            temporal._classify_temporal_runtime_bundle_publication_adapter,
            temporal._validate_global_content_retention_python_isolation,
            temporal._validate_initializer_import_prohibition,
            temporal._validate_selection_storage_isolation,
        )
    )
    for second_authority in (
        "build_python_source_snapshot",
        "_authenticate_authority",
        ".read_bytes(",
        ".read_text(",
        ".glob(",
        ".rglob(",
        "os.walk(",
        "ast.parse(",
    ):
        assert second_authority not in retained_snapshot_consumers
