"""Real-role PostgreSQL 17 tests for the authoritative tenant baseline."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from deployment.postgresql.catalog_classifier import (
    SCHEMA_LOCAL_CATALOG_CLASSES,
)
from deployment.postgresql.migration_runner import (
    MigrationDirtyError,
    initial_ledger_sql,
    migrate_service,
)
from deployment.postgresql.migration_sets import (
    TENANT_SERVICE,
    MigrationSet,
    load_migration_set,
)
from deployment.postgresql.provisioning import provision_service
from deployment.postgresql.provisioning_specs import TENANT_PROVISIONING_SPEC
from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    OIDC_ISSUER_INVALID_VECTORS,
    OIDC_ISSUER_VALID_VECTORS,
    TENANT_CONTEXT_CONTRACT,
    valid_oidc_issuer,
)
from kernel.tests.test_postgresql_migration_runner import (
    _assert_clean_service,
    _database_dsn,
    _destroy_test_service,
    _passwords,
)


ADMIN_ENV = "OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN"
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = PACKAGE_ROOT / "kernel" / "migrations" / "0001_initial.sql"
RELEASE_IDENTITY = "ofarm-tests/issue-174-tenant-baseline"
ISSUER = "https://issuer.example.test/tenant"
SUBJECT = "subject-tenant-01"
PARTY_REF = "party-01"
PARTY_KIND = "ofarm.party.v0.1"
ACCOUNTABLE_CONTROL = "identity-control-01"
INITIAL_REASON = "initial-activation"
SHA256_ZERO = "sha256:" + "00" * 32
RUNTIME_LOGICAL_REF_PREFIX = "rules/reference#v1/"
RUNTIME_LOGICAL_REF_MAX = RUNTIME_LOGICAL_REF_PREFIX + "a" * (
    1024 - len(RUNTIME_LOGICAL_REF_PREFIX)
)


@dataclass(frozen=True, slots=True)
class TenantTarget:
    admin_dsn: str
    target_admin_dsn: str
    migrator_dsn: str
    passwords: Mapping[str, str]
    migration_set: MigrationSet
    first_report: object
    noop_report: object

    def role_dsn(self, role_name: str) -> str:
        return _database_dsn(
            self.admin_dsn,
            TENANT_PROVISIONING_SPEC.database_name,
            user=role_name,
            password=self.passwords[role_name],
        )


@dataclass(frozen=True, slots=True)
class TenantAuthority:
    target_admin_dsn: str
    tenant_id: UUID
    tenant_registration_digest: str
    subject: str
    party_ref: str
    other_tenant_id: UUID
    other_tenant_registration_digest: str
    party_schema_digest: str
    party_payload_digest: str
    binding_version_id: UUID
    binding_version_digest: str
    lifecycle_head_id: UUID
    lifecycle_head_digest: str
    runtime_bundle_digest: str
    batch_id: str


def _admin_dsn() -> str:
    value = os.environ.get(ADMIN_ENV)
    if not value:
        pytest.skip(f"{ADMIN_ENV} is required for real PostgreSQL tests")
    return value


@pytest.fixture(scope="module")
def tenant_target() -> TenantTarget:
    admin_dsn = _admin_dsn()
    spec = TENANT_PROVISIONING_SPEC
    _assert_clean_service(admin_dsn, spec)
    passwords = _passwords(spec, "tenant-baseline")
    migration_set = load_migration_set(PACKAGE_ROOT, TENANT_SERVICE)
    try:
        provision_service(admin_dsn, spec, login_passwords=passwords)
        migrator_dsn = _database_dsn(
            admin_dsn,
            spec.database_name,
            user="ofarm_migrator",
            password=passwords["ofarm_migrator"],
        )
        first_report = migrate_service(
            admin_dsn=admin_dsn,
            migrator_dsn=migrator_dsn,
            spec=spec,
            migration_set=migration_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )
        noop_report = migrate_service(
            admin_dsn=admin_dsn,
            migrator_dsn=migrator_dsn,
            spec=spec,
            migration_set=migration_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )
        yield TenantTarget(
            admin_dsn=admin_dsn,
            target_admin_dsn=_database_dsn(admin_dsn, spec.database_name),
            migrator_dsn=migrator_dsn,
            passwords=passwords,
            migration_set=migration_set,
            first_report=first_report,
            noop_report=noop_report,
        )
    finally:
        _destroy_test_service(admin_dsn, spec)


def _sha256_id(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _compute_binding_digest(
    connection: psycopg.Connection,
    *,
    subject: str,
    binding_version_id: UUID,
    authority: TenantAuthority | None,
    tenant_id: UUID,
    tenant_registration_digest: str,
    party_ref: str,
    party_schema_digest: str,
    party_payload_digest: str,
    valid_from: object,
    valid_until: object,
    predecessor_version_id: UUID | None = None,
) -> str:
    return connection.execute(
        """
        SELECT ofarm.compute_principal_binding_version_digest(
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s
        )
        """,
        (
            OIDC_ISSUER_EQUALITY_POLICY,
            ISSUER,
            subject,
            binding_version_id,
            tenant_id,
            tenant_registration_digest,
            party_ref,
            PARTY_KIND,
            party_ref,
            party_schema_digest,
            party_payload_digest,
            "ACTIVE",
            valid_from,
            valid_until,
            predecessor_version_id,
        ),
    ).fetchone()[0]


def _compute_act_digest(
    connection: psycopg.Connection,
    *,
    subject: str,
    stream_sequence: int,
    act_id: UUID,
    act_kind: str,
    binding_version_id: UUID,
    binding_version_digest: str,
    prior_act_id: UUID | None,
    prior_act_digest: str | None,
    successor_version_id: UUID | None,
    successor_version_digest: str | None,
    effective_at: object,
    decided_at: object,
    reason: str,
) -> str:
    return connection.execute(
        """
        SELECT ofarm.compute_principal_lifecycle_act_digest(
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            OIDC_ISSUER_EQUALITY_POLICY,
            ISSUER,
            subject,
            stream_sequence,
            act_id,
            act_kind,
            binding_version_id,
            binding_version_digest,
            prior_act_id,
            prior_act_digest,
            successor_version_id,
            successor_version_digest,
            effective_at,
            decided_at,
            ACCOUNTABLE_CONTROL,
            reason,
        ),
    ).fetchone()[0]


def _transition(
    connection: psycopg.Connection,
    *,
    subject: str,
    expected_head_id: UUID | None,
    expected_head_digest: str | None,
    act_id: UUID,
    act_digest: str,
    act_kind: str,
    binding_version_id: UUID,
    binding_version_digest: str,
    candidate_version_id: UUID | None,
    candidate_version_digest: str | None,
    tenant_id: UUID | None,
    tenant_registration_digest: str | None,
    party_ref: str | None,
    party_schema_digest: str | None,
    party_payload_digest: str | None,
    valid_from: object | None,
    valid_until: object | None,
    predecessor_version_id: UUID | None,
    effective_at: object,
    decided_at: object,
    reason: str,
) -> None:
    connection.execute(
        """
        SELECT ofarm.transition_principal_binding(
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            OIDC_ISSUER_EQUALITY_POLICY,
            ISSUER,
            subject,
            expected_head_id,
            expected_head_digest,
            act_id,
            act_digest,
            act_kind,
            binding_version_id,
            binding_version_digest,
            candidate_version_id,
            candidate_version_digest,
            tenant_id,
            tenant_registration_digest,
            party_ref,
            PARTY_KIND if party_ref is not None else None,
            party_ref,
            party_schema_digest,
            party_payload_digest,
            "ACTIVE" if party_ref is not None else None,
            valid_from,
            valid_until,
            predecessor_version_id,
            effective_at,
            decided_at,
            ACCOUNTABLE_CONTROL,
            reason,
        ),
    )


@pytest.fixture(scope="module")
def authority(
    tenant_target: TenantTarget,
) -> TenantAuthority:
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_tenant_control_login")
    ) as control:
        tenant_id, _, registration_digest = control.execute(
            "SELECT * FROM ofarm.register_tenant(%s)", ("tenant-alpha",)
        ).fetchone()
        other_tenant_id, other_registration_digest = control.execute(
            "SELECT tenant_id, registration_digest FROM ofarm.register_tenant(%s)",
            ("tenant-beta",),
        ).fetchone()

    bundle_bytes = b'{"bundle":"tenant-integration-v1"}'
    bundle_digest = _sha256_id(bundle_bytes)
    bundle_ref = "runtimebundle:" + bundle_digest
    batch_id = "batch-authority-01"
    party_payload = {"partyId": PARTY_REF, "partyState": "ACTIVE"}
    party_schema_digest = _sha256_id(b"ofarm.party.v0.1.schema")
    party_payload_digest = _sha256_id(_canonical_json(party_payload))
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute(
            """
            INSERT INTO ofarm.runtime_bundle (
                tenant_id, bundle_digest, bundle_ref, canonical_bytes, byte_length
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (tenant_id, bundle_digest, bundle_ref, bundle_bytes, len(bundle_bytes)),
        )
        admin.execute(
            """
            INSERT INTO ofarm.governed_write_batch (
                tenant_id, batch_id, authenticated_principal_ref,
                governed_operation, request_id, runtime_bundle_digest
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_id,
                batch_id,
                PARTY_REF,
                "AUTHORITY_BOOTSTRAP",
                "request-authority-01",
                bundle_digest,
            ),
        )
        admin.execute(
            """
            INSERT INTO ofarm.kernel_record (
                tenant_id, record_id, record_kind, lane, schema_digest,
                payload, payload_digest, batch_id, runtime_bundle_digest
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_id,
                PARTY_REF,
                PARTY_KIND,
                "canonical",
                party_schema_digest,
                Jsonb(party_payload),
                party_payload_digest,
                batch_id,
                bundle_digest,
            ),
        )

    binding_version_id = uuid4()
    lifecycle_head_id = uuid4()
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_identity_control_login")
    ) as identity:
        valid_from, valid_until, effective_at, decided_at = identity.execute(
            """
            SELECT
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '1 day'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() + INTERVAL '1 day'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '2 seconds'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '1 second'
                )
            """
        ).fetchone()
        binding_digest = _compute_binding_digest(
            identity,
            subject=SUBJECT,
            binding_version_id=binding_version_id,
            authority=None,
            tenant_id=tenant_id,
            tenant_registration_digest=registration_digest,
            party_ref=PARTY_REF,
            party_schema_digest=party_schema_digest,
            party_payload_digest=party_payload_digest,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        act_digest = _compute_act_digest(
            identity,
            subject=SUBJECT,
            stream_sequence=1,
            act_id=lifecycle_head_id,
            act_kind="ACTIVATE",
            binding_version_id=binding_version_id,
            binding_version_digest=binding_digest,
            prior_act_id=None,
            prior_act_digest=None,
            successor_version_id=None,
            successor_version_digest=None,
            effective_at=effective_at,
            decided_at=decided_at,
            reason=INITIAL_REASON,
        )
        _transition(
            identity,
            subject=SUBJECT,
            expected_head_id=None,
            expected_head_digest=None,
            act_id=lifecycle_head_id,
            act_digest=act_digest,
            act_kind="ACTIVATE",
            binding_version_id=binding_version_id,
            binding_version_digest=binding_digest,
            candidate_version_id=binding_version_id,
            candidate_version_digest=binding_digest,
            tenant_id=tenant_id,
            tenant_registration_digest=registration_digest,
            party_ref=PARTY_REF,
            party_schema_digest=party_schema_digest,
            party_payload_digest=party_payload_digest,
            valid_from=valid_from,
            valid_until=valid_until,
            predecessor_version_id=None,
            effective_at=effective_at,
            decided_at=decided_at,
            reason=INITIAL_REASON,
        )

    return TenantAuthority(
        target_admin_dsn=tenant_target.target_admin_dsn,
        tenant_id=tenant_id,
        tenant_registration_digest=registration_digest,
        subject=SUBJECT,
        party_ref=PARTY_REF,
        other_tenant_id=other_tenant_id,
        other_tenant_registration_digest=other_registration_digest,
        party_schema_digest=party_schema_digest,
        party_payload_digest=party_payload_digest,
        binding_version_id=binding_version_id,
        binding_version_digest=binding_digest,
        lifecycle_head_id=lifecycle_head_id,
        lifecycle_head_digest=act_digest,
        runtime_bundle_digest=bundle_digest,
        batch_id=batch_id,
    )


@pytest.fixture(scope="module")
def other_authority(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> TenantAuthority:
    tenant_id = authority.other_tenant_id
    registration_digest = authority.other_tenant_registration_digest
    subject = "subject-tenant-02"
    party_ref = "party-02"
    bundle_bytes = b'{"bundle":"tenant-beta-integration-v1"}'
    bundle_digest = _sha256_id(bundle_bytes)
    bundle_ref = "runtimebundle:" + bundle_digest
    batch_id = "batch-authority-02"
    party_payload = {"partyId": party_ref, "partyState": "ACTIVE"}
    party_schema_digest = _sha256_id(b"ofarm.party.v0.1.schema")
    party_payload_digest = _sha256_id(_canonical_json(party_payload))
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute(
            """
            INSERT INTO ofarm.runtime_bundle (
                tenant_id, bundle_digest, bundle_ref, canonical_bytes, byte_length
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (tenant_id, bundle_digest, bundle_ref, bundle_bytes, len(bundle_bytes)),
        )
        admin.execute(
            """
            INSERT INTO ofarm.governed_write_batch (
                tenant_id, batch_id, authenticated_principal_ref,
                governed_operation, request_id, runtime_bundle_digest
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_id,
                batch_id,
                party_ref,
                "AUTHORITY_BOOTSTRAP",
                "request-authority-02",
                bundle_digest,
            ),
        )
        admin.execute(
            """
            INSERT INTO ofarm.kernel_record (
                tenant_id, record_id, record_kind, lane, schema_digest,
                payload, payload_digest, batch_id, runtime_bundle_digest
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_id,
                party_ref,
                PARTY_KIND,
                "canonical",
                party_schema_digest,
                Jsonb(party_payload),
                party_payload_digest,
                batch_id,
                bundle_digest,
            ),
        )

    binding_version_id = uuid4()
    lifecycle_head_id = uuid4()
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_identity_control_login")
    ) as identity:
        valid_from, valid_until, effective_at, decided_at = identity.execute(
            """
            SELECT
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '1 day'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() + INTERVAL '1 day'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '2 seconds'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '1 second'
                )
            """
        ).fetchone()
        binding_digest = _compute_binding_digest(
            identity,
            subject=subject,
            binding_version_id=binding_version_id,
            authority=None,
            tenant_id=tenant_id,
            tenant_registration_digest=registration_digest,
            party_ref=party_ref,
            party_schema_digest=party_schema_digest,
            party_payload_digest=party_payload_digest,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        act_digest = _compute_act_digest(
            identity,
            subject=subject,
            stream_sequence=1,
            act_id=lifecycle_head_id,
            act_kind="ACTIVATE",
            binding_version_id=binding_version_id,
            binding_version_digest=binding_digest,
            prior_act_id=None,
            prior_act_digest=None,
            successor_version_id=None,
            successor_version_digest=None,
            effective_at=effective_at,
            decided_at=decided_at,
            reason=INITIAL_REASON,
        )
        _transition(
            identity,
            subject=subject,
            expected_head_id=None,
            expected_head_digest=None,
            act_id=lifecycle_head_id,
            act_digest=act_digest,
            act_kind="ACTIVATE",
            binding_version_id=binding_version_id,
            binding_version_digest=binding_digest,
            candidate_version_id=binding_version_id,
            candidate_version_digest=binding_digest,
            tenant_id=tenant_id,
            tenant_registration_digest=registration_digest,
            party_ref=party_ref,
            party_schema_digest=party_schema_digest,
            party_payload_digest=party_payload_digest,
            valid_from=valid_from,
            valid_until=valid_until,
            predecessor_version_id=None,
            effective_at=effective_at,
            decided_at=decided_at,
            reason=INITIAL_REASON,
        )
    return TenantAuthority(
        target_admin_dsn=tenant_target.target_admin_dsn,
        tenant_id=tenant_id,
        tenant_registration_digest=registration_digest,
        subject=subject,
        party_ref=party_ref,
        other_tenant_id=authority.tenant_id,
        other_tenant_registration_digest=authority.tenant_registration_digest,
        party_schema_digest=party_schema_digest,
        party_payload_digest=party_payload_digest,
        binding_version_id=binding_version_id,
        binding_version_digest=binding_digest,
        lifecycle_head_id=lifecycle_head_id,
        lifecycle_head_digest=act_digest,
        runtime_bundle_digest=bundle_digest,
        batch_id=batch_id,
    )


def _install_test_bound_context(
    connection: psycopg.Connection,
    authority: TenantAuthority,
) -> None:
    """Install a privileged test-only context for RLS/graph tests.

    Production binding is deliberately absent until issue #172.  These #174
    tests still need to exercise the protected storage primitives, so a target
    administrator supplies the already-verified transaction context directly.
    """

    backend_pid, full_xid = connection.execute(
        """
        SELECT pg_catalog.pg_backend_pid(),
               pg_catalog.pg_current_xact_id()::pg_catalog.text
        """
    ).fetchone()
    with psycopg.connect(authority.target_admin_dsn) as admin:
        backend_start = admin.execute(
            """
            SELECT backend_start
            FROM pg_catalog.pg_stat_activity
            WHERE pid = %s
            """,
            (backend_pid,),
        ).fetchone()[0]
        admin.execute(
            """
            DELETE FROM ofarm.tenant_binding_context
            WHERE backend_pid = %s AND backend_start = %s
            """,
            (backend_pid, backend_start),
        )
        admin.execute(
            """
            INSERT INTO ofarm.tenant_binding_context (
                backend_pid, backend_start, full_xid,
                challenge_id, context_state,
                equality_policy, issuer, subject,
                binding_version_id, binding_version_digest,
                lifecycle_head_id, lifecycle_head_digest,
                tenant_id, tenant_registration_digest,
                party_ref, party_record_kind, party_record_id,
                party_schema_digest, party_payload_digest,
                capability_nonce, bound_at
            ) VALUES (
                %s, %s, %s::pg_catalog.xid8,
                %s, 'BOUND',
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, pg_catalog.clock_timestamp()
            )
            """,
            (
                backend_pid,
                backend_start,
                full_xid,
                uuid4(),
                OIDC_ISSUER_EQUALITY_POLICY,
                ISSUER,
                authority.subject,
                authority.binding_version_id,
                authority.binding_version_digest,
                authority.lifecycle_head_id,
                authority.lifecycle_head_digest,
                authority.tenant_id,
                authority.tenant_registration_digest,
                authority.party_ref,
                PARTY_KIND,
                authority.party_ref,
                authority.party_schema_digest,
                authority.party_payload_digest,
                uuid4(),
            ),
        )


def _verify(connection: psycopg.Connection) -> tuple[object, ...]:
    connection.execute("SET LOCAL ROLE ofarm_owner")
    return connection.execute(
        "SELECT * FROM ofarm.verify_tenant_structure()"
    ).fetchone()


def test_authoritative_source_ledger_contract_and_apply_noop(
    tenant_target: TenantTarget,
) -> None:
    source = MIGRATION_PATH.read_bytes()
    ledger = initial_ledger_sql(TENANT_PROVISIONING_SPEC).encode("utf-8")
    assert source.count(ledger) == 1
    assert b"CREATE EXTENSION" not in source
    assert b"CREATE TABLE IF NOT EXISTS" not in source
    assert b"CREATE FUNCTION IF NOT EXISTS" not in source
    assert b"DROP TABLE IF EXISTS" not in source
    assert b"DROP FUNCTION IF EXISTS" not in source
    assert b"FROM pg_catalog.pg_stat_get_wal_senders()" in source
    assert b"FROM pg_catalog.pg_stat_get_wal_receiver() AS receiver" in source
    assert source.count(b"SET quote_all_identifiers = off") == 1
    assert b"FROM pg_catalog.pg_largeobject_metadata" in source
    assert TENANT_CONTEXT_CONTRACT.digest == (
        "sha256:4e0acd383a1c44142043c51f2bca26fbddc0f191dcf511c2aa97d212d3a6cb62"
    )
    assert tenant_target.first_report.applied_versions == (1,)
    assert tenant_target.noop_report.applied_versions == ()
    assert tenant_target.noop_report.final_version == 1


def test_tenant_catalog_fingerprint_has_exact_shared_schema_class_parity() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    marker = "-- SCHEMA_LOCAL_CATALOG_CLASSIFIER_V1"
    assert source.count(marker) == 1
    classifier = source.split(marker, 1)[1].split(
        "        WITH catalog_entry(category, object_identity, definition) AS (",
        1,
    )
    registry_lines, fingerprint = classifier
    observed_registry = tuple(
        tuple(line.strip().removeprefix("-- ").split("|"))
        for line in registry_lines.splitlines()
        if line.strip().startswith("-- ")
    )
    expected_registry = tuple(
        (
            item.category,
            item.catalog_name,
            item.namespace_column,
            item.name_column,
        )
        for item in SCHEMA_LOCAL_CATALOG_CLASSES
    )
    assert observed_registry == expected_registry
    fingerprint = fingerprint.split(
        "        SELECT ''sha256:'' || pg_catalog.encode(", 1
    )[0]
    for item in SCHEMA_LOCAL_CATALOG_CLASSES:
        assert fingerprint.count(f"''{item.category}''") == 1
        assert f"FROM pg_catalog.{item.catalog_name} AS" in fingerprint
        assert f".{item.namespace_column}" in fingerprint
        assert f".{item.name_column}" in fingerprint


def test_shared_application_role_cannot_observe_peer_backend_statistics(
    tenant_target: TenantTarget,
) -> None:
    secret_application_name = "ofarm-stat-victim-" + uuid4().hex
    secret_query_marker = "ofarm-stat-query-" + uuid4().hex
    routine_calls = (
        "SELECT * FROM pg_catalog.pg_stat_get_activity(NULL::pg_catalog.int4)",
        "SELECT pg_catalog.pg_stat_get_backend_activity(1)",
        "SELECT pg_catalog.pg_stat_get_backend_activity_start(1)",
        "SELECT pg_catalog.pg_stat_get_backend_client_addr(1)",
        "SELECT pg_catalog.pg_stat_get_backend_client_port(1)",
        "SELECT pg_catalog.pg_stat_get_backend_dbid(1)",
        "SELECT * FROM pg_catalog.pg_stat_get_backend_idset()",
        "SELECT pg_catalog.pg_stat_get_backend_pid(1)",
        "SELECT pg_catalog.pg_stat_get_backend_start(1)",
        "SELECT * FROM pg_catalog.pg_stat_get_backend_subxact(1)",
        "SELECT pg_catalog.pg_stat_get_backend_userid(1)",
        "SELECT pg_catalog.pg_stat_get_backend_wait_event(1)",
        "SELECT pg_catalog.pg_stat_get_backend_wait_event_type(1)",
        "SELECT pg_catalog.pg_stat_get_backend_xact_start(1)",
    )

    victim = psycopg.connect(
        tenant_target.role_dsn("ofarm_app"),
        application_name=secret_application_name,
    )
    attacker = psycopg.connect(tenant_target.role_dsn("ofarm_app"))
    try:
        victim_pid = victim.execute(
            f"SELECT pg_catalog.pg_backend_pid() /* {secret_query_marker} */"
        ).fetchone()[0]

        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            observed_secret = admin.execute(
                """
                SELECT application_name, query
                FROM pg_catalog.pg_stat_activity
                WHERE pid = %s
                """,
                (victim_pid,),
            ).fetchone()
            assert observed_secret is not None
            assert observed_secret[0] == secret_application_name
            assert secret_query_marker in observed_secret[1]

            privilege_matrix = admin.execute(
                """
                WITH role_inventory(role_name) AS (
                    VALUES
                        ('ofarm_app'::pg_catalog.text),
                        ('ofarm_worker'::pg_catalog.text),
                        ('ofarm_binder'::pg_catalog.text),
                        ('ofarm_backend_observer'::pg_catalog.text)
                )
                SELECT
                    role_inventory.role_name,
                    pg_catalog.has_table_privilege(
                        role_inventory.role_name,
                        'pg_catalog.pg_stat_activity',
                        'SELECT'
                    ),
                    (
                        SELECT pg_catalog.count(*)
                        FROM pg_catalog.pg_proc AS routine
                        JOIN pg_catalog.pg_namespace AS namespace
                          ON namespace.oid = routine.pronamespace
                        WHERE namespace.nspname = 'pg_catalog'
                          AND pg_catalog.left(
                                  routine.proname::pg_catalog.text, 20
                              ) IN (
                                  'pg_stat_get_activity',
                                  'pg_stat_get_backend_'
                              )
                          AND pg_catalog.has_function_privilege(
                                  role_inventory.role_name,
                                  routine.oid,
                                  'EXECUTE'
                              )
                    )
                FROM role_inventory
                ORDER BY role_inventory.role_name
                """
            ).fetchall()
            assert privilege_matrix == [
                ("ofarm_app", False, 0),
                ("ofarm_backend_observer", True, 1),
                ("ofarm_binder", False, 0),
                ("ofarm_worker", False, 0),
            ]

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            attacker.execute(
                """
                SELECT application_name, query
                FROM pg_catalog.pg_stat_activity
                WHERE pid = %s
                """,
                (victim_pid,),
            )
        attacker.rollback()

        for statement in routine_calls:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                attacker.execute(statement)
            attacker.rollback()

        challenge_id = attacker.execute(
            "SELECT ofarm.create_tenant_challenge()"
        ).fetchone()[0]
        assert isinstance(challenge_id, UUID)
        attacker.rollback()
    finally:
        victim.close()
        attacker.close()


def test_production_binding_is_fail_closed_pending_issue_172(
    tenant_target: TenantTarget,
) -> None:
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        forbidden_relations = admin.execute(
            """
            SELECT pg_catalog.to_regclass('ofarm.tenant_capability_key_schedule')
            """
        ).fetchone()
        forbidden_routines = admin.execute(
            """
            SELECT routine.proname
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = routine.pronamespace
            WHERE namespace.nspname = 'ofarm'
              AND routine.proname IN (
                  'bind_tenant_capability',
                  'frame_tenant_capability',
                  'hmac_sha256',
                  'secure_bytea_equal',
                  'install_tenant_capability_key'
              )
            """
        ).fetchall()
    assert forbidden_relations == (None,)
    assert forbidden_routines == []

    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        challenge_id = application.execute(
            "SELECT ofarm.create_tenant_challenge()"
        ).fetchone()[0]
        assert isinstance(challenge_id, UUID)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            application.execute("SELECT ofarm.current_tenant_id()")


def test_live_postgresql_and_python_share_exact_issuer_vectors(
    tenant_target: TenantTarget,
) -> None:
    vectors = tuple((value, True) for value in OIDC_ISSUER_VALID_VECTORS) + tuple(
        (value, False) for value in OIDC_ISSUER_INVALID_VECTORS
    )
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        for issuer, expected in vectors:
            database_result = admin.execute(
                "SELECT ofarm.valid_oidc_issuer(%s)", (issuer,)
            ).fetchone()[0]
            assert database_result is expected
            assert valid_oidc_issuer(issuer) is expected


def test_runtime_component_logical_ref_has_exact_ascii_octet_bound(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    content = b"runtime-component-logical-ref-boundary"
    content_digest = _sha256_id(content)
    insert_sql = """
        INSERT INTO ofarm.runtime_bundle_component (
            tenant_id, bundle_digest, component_role, logical_ref,
            canonicalization, content_placement, global_content_digest,
            byte_length
        ) VALUES (
            %s, %s, 'REFERENCE_SOURCE', %s,
            'EXACT_BYTES_V1', 'GLOBAL_IMMUTABLE_CONTENT', %s, %s
        )
    """
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        try:
            admin.execute(
                """
                INSERT INTO ofarm.runtime_content_blob (
                    content_digest, canonical_bytes, byte_length
                ) VALUES (%s, %s, %s)
                """,
                (content_digest, content, len(content)),
            )
            maximum_ref = RUNTIME_LOGICAL_REF_MAX
            admin.execute(
                insert_sql,
                (
                    authority.tenant_id,
                    authority.runtime_bundle_digest,
                    maximum_ref,
                    content_digest,
                    len(content),
                ),
            )
            assert admin.execute(
                """
                SELECT pg_catalog.octet_length(logical_ref)
                FROM ofarm.runtime_bundle_component
                WHERE tenant_id = %s
                  AND bundle_digest = %s
                  AND component_role = 'REFERENCE_SOURCE'
                  AND logical_ref = %s
                """,
                (
                    authority.tenant_id,
                    authority.runtime_bundle_digest,
                    maximum_ref,
                ),
            ).fetchone() == (1024,)

            for invalid_ref in (
                RUNTIME_LOGICAL_REF_MAX + "a",
                RUNTIME_LOGICAL_REF_PREFIX + "ž",
            ):
                with pytest.raises(psycopg.errors.CheckViolation):
                    with admin.transaction():
                        admin.execute(
                            insert_sql,
                            (
                                authority.tenant_id,
                                authority.runtime_bundle_digest,
                                invalid_ref,
                                content_digest,
                                len(content),
                            ),
                        )
        finally:
            admin.rollback()


@pytest.mark.parametrize("role_name", ("ofarm_app", "ofarm_worker"))
def test_runtime_roles_cannot_directly_access_context_or_control_tables(
    tenant_target: TenantTarget,
    role_name: str,
) -> None:
    with psycopg.connect(tenant_target.role_dsn(role_name)) as runtime:
        statements = (
            "SELECT * FROM ofarm.tenant_binding_context",
            "INSERT INTO ofarm.tenant_binding_context DEFAULT VALUES",
            "UPDATE ofarm.tenant_binding_context SET context_state = 'BOUND'",
            "DELETE FROM ofarm.tenant_binding_context",
        )
        for statement in statements:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with runtime.transaction():
                    runtime.execute(statement)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with runtime.transaction():
                with runtime.cursor().copy(
                    "COPY ofarm.tenant_binding_context TO STDOUT"
                ) as copied:
                    tuple(copied)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with runtime.transaction():
                with runtime.cursor().copy(
                    "COPY ofarm.tenant_binding_context (challenge_id) FROM STDIN"
                ) as copied:
                    copied.write_row((uuid4(),))

        for relation_name, update_expression in (
            ("tenant_registry", "tenant_ref = tenant_ref"),
            (
                "principal_binding_current",
                "current_state = current_state",
            ),
        ):
            for statement in (
                f"SELECT * FROM ofarm.{relation_name}",
                f"INSERT INTO ofarm.{relation_name} DEFAULT VALUES",
                f"UPDATE ofarm.{relation_name} SET {update_expression}",
                f"DELETE FROM ofarm.{relation_name}",
            ):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with runtime.transaction():
                        runtime.execute(statement)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with runtime.transaction():
                    with runtime.cursor().copy(
                        f"COPY ofarm.{relation_name} TO STDOUT"
                    ) as copied:
                        tuple(copied)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with runtime.transaction():
                    with runtime.cursor().copy(
                        f"COPY ofarm.{relation_name} FROM STDIN"
                    ):
                        pass

        for routine_name in (
            "validate_promotion_edge",
            "require_promotion_reachability",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with runtime.transaction():
                    runtime.execute(f"SELECT ofarm.{routine_name}()")

        for statement in (
            "SELECT ofarm.current_backend_start()",
            """
            SELECT ofarm.backend_incarnation_is_live(
                pg_catalog.pg_backend_pid(), pg_catalog.clock_timestamp()
            )
            """,
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with runtime.transaction():
                    runtime.execute(statement)


@pytest.mark.parametrize("role_name", ("ofarm_app", "ofarm_worker"))
def test_runtime_roles_cannot_use_any_postgresql_large_object_path(
    tenant_target: TenantTarget,
    role_name: str,
) -> None:
    statements = (
        "SELECT pg_catalog.lo_close(0)",
        "SELECT pg_catalog.lo_creat(0)",
        "SELECT pg_catalog.lo_create(0::pg_catalog.oid)",
        "SELECT pg_catalog.lo_export(0::pg_catalog.oid, '/tmp/ofarm-lo-export')",
        "SELECT pg_catalog.lo_from_bytea(0::pg_catalog.oid, ''::pg_catalog.bytea)",
        "SELECT pg_catalog.lo_get(0::pg_catalog.oid)",
        "SELECT pg_catalog.lo_get(0::pg_catalog.oid, 0::pg_catalog.int8, 1)",
        "SELECT pg_catalog.lo_import('/tmp/ofarm-lo-import')",
        "SELECT pg_catalog.lo_import('/tmp/ofarm-lo-import', 0::pg_catalog.oid)",
        "SELECT pg_catalog.lo_lseek(0, 0, 0)",
        "SELECT pg_catalog.lo_lseek64(0, 0::pg_catalog.int8, 0)",
        "SELECT pg_catalog.lo_open(0::pg_catalog.oid, 0)",
        "SELECT pg_catalog.lo_put(0::pg_catalog.oid, 0::pg_catalog.int8, ''::pg_catalog.bytea)",
        "SELECT pg_catalog.lo_tell(0)",
        "SELECT pg_catalog.lo_tell64(0)",
        "SELECT pg_catalog.lo_truncate(0, 0)",
        "SELECT pg_catalog.lo_truncate64(0, 0::pg_catalog.int8)",
        "SELECT pg_catalog.lo_unlink(0::pg_catalog.oid)",
        "SELECT pg_catalog.loread(0, 1)",
        "SELECT pg_catalog.lowrite(0, ''::pg_catalog.bytea)",
    )
    with psycopg.connect(tenant_target.role_dsn(role_name)) as runtime:
        for statement in statements:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with runtime.transaction():
                    runtime.execute(statement)


def test_context_storage_rls_copy_search_path_and_lock_namespace(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        _install_test_bound_context(application, authority)
        assert (
            application.execute("SELECT ofarm.current_tenant_id()").fetchone()[0]
            == authority.tenant_id
        )
        assert application.execute(
            "SELECT record_id FROM ofarm.kernel_record ORDER BY record_id"
        ).fetchall() == [(PARTY_REF,)]
        application.execute("SET LOCAL search_path = pg_temp, public")
        assert (
            application.execute("SELECT ofarm.current_tenant_id()").fetchone()[0]
            == authority.tenant_id
        )

        with application.cursor().copy(
            "COPY (SELECT tenant_id, record_id FROM ofarm.kernel_record) TO STDOUT"
        ) as copied:
            copy_bytes = b"".join(bytes(chunk) for chunk in copied)
        assert str(authority.tenant_id).encode("ascii") in copy_bytes
        assert str(authority.other_tenant_id).encode("ascii") not in copy_bytes

        with pytest.raises(psycopg.Error):
            with application.transaction():
                application.execute("SET LOCAL ROLE ofarm_binder")

        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            with application.transaction():
                application.execute("SELECT ofarm.create_tenant_challenge()")

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with application.transaction():
                application.execute(
                    """
                    INSERT INTO ofarm.governed_write_batch (
                        tenant_id, batch_id, authenticated_principal_ref,
                        governed_operation, request_id, runtime_bundle_digest
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        authority.other_tenant_id,
                        "batch-other-tenant",
                        PARTY_REF,
                        "HOSTILE_WRITE",
                        "request-other-tenant",
                        authority.runtime_bundle_digest,
                    ),
                )

        application.execute("SELECT ofarm.take_tenant_write_lock()")
        advisory_locks = application.execute(
            """
            SELECT lock.objsubid
            FROM pg_catalog.pg_locks AS lock
            WHERE lock.pid = pg_catalog.pg_backend_pid()
              AND lock.locktype = 'advisory'
              AND lock.granted
            """
        ).fetchall()
        assert advisory_locks == [(1,)]


def test_tenant_write_lock_serializes_same_tenant_but_not_different_tenant(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    other_authority: TenantAuthority,
) -> None:
    first = psycopg.connect(tenant_target.role_dsn("ofarm_app"))
    same = psycopg.connect(tenant_target.role_dsn("ofarm_app"))
    different = psycopg.connect(tenant_target.role_dsn("ofarm_app"))
    attempting = threading.Event()
    same_acquired = threading.Event()
    try:
        _install_test_bound_context(first, authority)
        _install_test_bound_context(same, authority)
        _install_test_bound_context(different, other_authority)
        first.execute("SELECT ofarm.take_tenant_write_lock()")

        def acquire_same() -> bool:
            attempting.set()
            same.execute("SELECT ofarm.take_tenant_write_lock()")
            same_acquired.set()
            return True

        def acquire_different() -> bool:
            different.execute("SELECT ofarm.take_tenant_write_lock()")
            return True

        with ThreadPoolExecutor(max_workers=2) as executor:
            same_future = executor.submit(acquire_same)
            assert attempting.wait(timeout=2)
            assert not same_acquired.wait(timeout=0.25)
            different_future = executor.submit(acquire_different)
            assert different_future.result(timeout=2) is True
            first.commit()
            assert same_future.result(timeout=2) is True
    finally:
        if not first.closed:
            first.close()
        same.close()
        different.close()


@pytest.mark.parametrize("role_name", ("ofarm_app", "ofarm_worker"))
def test_runtime_role_rls_refuses_query_shape_and_cross_tenant_write_bypasses(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    other_authority: TenantAuthority,
    role_name: str,
) -> None:
    with psycopg.connect(tenant_target.role_dsn(role_name)) as runtime:
        _install_test_bound_context(runtime, authority)
        assert runtime.execute(
            """
            SELECT pg_catalog.count(*) > 0,
                   pg_catalog.count(*) FILTER (
                       WHERE tenant_id <> ofarm.current_tenant_id()
                   )
            FROM ofarm.kernel_record
            """
        ).fetchone() == (True, 0)
        assert runtime.execute(
            """
            SELECT pg_catalog.count(*) FILTER (
                       WHERE record.tenant_id <> ofarm.current_tenant_id()
                          OR bundle.tenant_id <> ofarm.current_tenant_id()
                   )
            FROM ofarm.kernel_record AS record
            JOIN ofarm.runtime_bundle AS bundle
              ON bundle.tenant_id = record.tenant_id
            """
        ).fetchone() == (0,)
        assert runtime.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM ofarm.kernel_record AS hidden
                WHERE hidden.tenant_id = %s
            )
            """,
            (other_authority.tenant_id,),
        ).fetchone() == (False,)

        runtime.execute(
            """
            PREPARE ofarm_cross_tenant_probe (uuid) AS
            SELECT pg_catalog.count(*)
            FROM ofarm.kernel_record
            WHERE tenant_id = $1
            """
        )
        try:
            assert runtime.execute(
                sql.SQL("EXECUTE ofarm_cross_tenant_probe ({})").format(
                    sql.Literal(other_authority.tenant_id)
                ),
            ).fetchone() == (0,)
        finally:
            runtime.execute("DEALLOCATE ofarm_cross_tenant_probe")

        with runtime.cursor().copy(
            "COPY (SELECT tenant_id FROM ofarm.kernel_record) TO STDOUT"
        ) as copied:
            copied_bytes = b"".join(bytes(chunk) for chunk in copied)
        assert str(authority.tenant_id).encode("ascii") in copied_bytes
        assert str(other_authority.tenant_id).encode("ascii") not in copied_bytes

        for statement in (
            "UPDATE ofarm.kernel_record SET lane = lane WHERE tenant_id = %s",
            "DELETE FROM ofarm.kernel_record WHERE tenant_id = %s",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with runtime.transaction():
                    runtime.execute(statement, (other_authority.tenant_id,))

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with runtime.transaction():
                runtime.execute(
                    """
                    INSERT INTO ofarm.governed_write_batch (
                        tenant_id, batch_id, authenticated_principal_ref,
                        governed_operation, request_id, runtime_bundle_digest
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id, batch_id) DO UPDATE
                    SET request_id = EXCLUDED.request_id
                    """,
                    (
                        other_authority.tenant_id,
                        other_authority.batch_id,
                        other_authority.party_ref,
                        "HOSTILE_UPSERT",
                        "request-hostile-upsert",
                        other_authority.runtime_bundle_digest,
                    ),
                )


def test_oidc_issuer_domain_enforces_shared_invalid_vectors(
    tenant_target: TenantTarget,
) -> None:
    with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
        for issuer in OIDC_ISSUER_VALID_VECTORS:
            assert admin.execute(
                "SELECT %s::ofarm.oidc_issuer::pg_catalog.text", (issuer,)
            ).fetchone() == (issuer,)
        for issuer in OIDC_ISSUER_INVALID_VECTORS:
            with pytest.raises(psycopg.errors.CheckViolation):
                admin.execute("SELECT %s::ofarm.oidc_issuer", (issuer,))


def test_stale_purge_preserves_two_live_backend_incarnations(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    bound_peer = psycopg.connect(tenant_target.role_dsn("ofarm_app"))
    challenge_peer = psycopg.connect(tenant_target.role_dsn("ofarm_app"))
    observer_peer = psycopg.connect(tenant_target.role_dsn("ofarm_app"))
    purger_peer: psycopg.Connection | None = None
    try:
        _install_test_bound_context(bound_peer, authority)
        bound_pid = bound_peer.execute("SELECT pg_catalog.pg_backend_pid()").fetchone()[
            0
        ]
        bound_peer.commit()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            bound_peer.execute("SELECT ofarm.current_tenant_id()")
        bound_peer.rollback()

        challenge_id = challenge_peer.execute(
            "SELECT ofarm.create_tenant_challenge()"
        ).fetchone()[0]
        challenge_pid = challenge_peer.execute(
            "SELECT pg_catalog.pg_backend_pid()"
        ).fetchone()[0]
        challenge_peer.commit()

        observer_peer.execute("SELECT ofarm.create_tenant_challenge()")
        observer_peer.commit()
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            live_rows = admin.execute(
                """
                SELECT backend_pid, context_state
                FROM ofarm.tenant_binding_context
                WHERE backend_pid = ANY(%s::integer[])
                ORDER BY backend_pid
                """,
                ([bound_pid, challenge_pid],),
            ).fetchall()
        assert set(live_rows) == {(bound_pid, "BOUND"), (challenge_pid, "CHALLENGE")}

        bound_peer.close()
        purger_peer = psycopg.connect(tenant_target.role_dsn("ofarm_app"))
        purger_peer.execute("SELECT ofarm.create_tenant_challenge()")
        purger_peer.commit()
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            assert admin.execute(
                """
                SELECT context_state
                FROM ofarm.tenant_binding_context
                WHERE backend_pid = %s AND challenge_id = %s
                """,
                (challenge_pid, challenge_id),
            ).fetchone() == ("CHALLENGE",)
            assert (
                admin.execute(
                    "SELECT count(*) FROM ofarm.tenant_binding_context WHERE backend_pid = %s",
                    (bound_pid,),
                ).fetchone()[0]
                == 0
            )
    finally:
        if not bound_peer.closed:
            bound_peer.close()
        challenge_peer.close()
        observer_peer.close()
        if purger_peer is not None:
            purger_peer.close()


def _initial_transition_values(
    identity: psycopg.Connection,
    authority: TenantAuthority,
    *,
    subject: str,
    expired_now: bool = False,
    reason: str = "hostile-attempt",
) -> dict[str, object]:
    if expired_now:
        valid_from, valid_until, effective_at, decided_at = identity.execute(
            """
            SELECT
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '2 days'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '1 hour'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '1 day'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '2 seconds'
                )
            """
        ).fetchone()
    else:
        valid_from, valid_until, effective_at, decided_at = identity.execute(
            """
            SELECT
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '1 day'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() + INTERVAL '1 day'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '2 seconds'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '1 second'
                )
            """
        ).fetchone()
    binding_version_id = uuid4()
    act_id = uuid4()
    binding_digest = _compute_binding_digest(
        identity,
        subject=subject,
        binding_version_id=binding_version_id,
        authority=authority,
        tenant_id=authority.tenant_id,
        tenant_registration_digest=authority.tenant_registration_digest,
        party_ref=PARTY_REF,
        party_schema_digest=authority.party_schema_digest,
        party_payload_digest=authority.party_payload_digest,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    act_digest = _compute_act_digest(
        identity,
        subject=subject,
        stream_sequence=1,
        act_id=act_id,
        act_kind="ACTIVATE",
        binding_version_id=binding_version_id,
        binding_version_digest=binding_digest,
        prior_act_id=None,
        prior_act_digest=None,
        successor_version_id=None,
        successor_version_digest=None,
        effective_at=effective_at,
        decided_at=decided_at,
        reason=reason,
    )
    return {
        "binding_version_id": binding_version_id,
        "binding_digest": binding_digest,
        "act_id": act_id,
        "act_digest": act_digest,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "effective_at": effective_at,
        "decided_at": decided_at,
    }


@pytest.mark.parametrize("failure_mode", ("version-digest", "act-digest", "expired"))
def test_transition_digest_and_currentness_failures_roll_back_atomically(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    failure_mode: str,
) -> None:
    subject = f"subject-hostile-{failure_mode}"
    with pytest.raises(psycopg.Error):
        with psycopg.connect(
            tenant_target.role_dsn("ofarm_identity_control_login")
        ) as identity:
            values = _initial_transition_values(
                identity,
                authority,
                subject=subject,
                expired_now=failure_mode == "expired",
            )
            supplied_binding_digest = (
                SHA256_ZERO
                if failure_mode == "version-digest"
                else values["binding_digest"]
            )
            supplied_act_digest = values["act_digest"]
            if failure_mode == "version-digest":
                supplied_act_digest = _compute_act_digest(
                    identity,
                    subject=subject,
                    stream_sequence=1,
                    act_id=values["act_id"],
                    act_kind="ACTIVATE",
                    binding_version_id=values["binding_version_id"],
                    binding_version_digest=SHA256_ZERO,
                    prior_act_id=None,
                    prior_act_digest=None,
                    successor_version_id=None,
                    successor_version_digest=None,
                    effective_at=values["effective_at"],
                    decided_at=values["decided_at"],
                    reason="hostile-attempt",
                )
            elif failure_mode == "act-digest":
                supplied_act_digest = SHA256_ZERO
            _transition(
                identity,
                subject=subject,
                expected_head_id=None,
                expected_head_digest=None,
                act_id=values["act_id"],
                act_digest=supplied_act_digest,
                act_kind="ACTIVATE",
                binding_version_id=values["binding_version_id"],
                binding_version_digest=supplied_binding_digest,
                candidate_version_id=values["binding_version_id"],
                candidate_version_digest=supplied_binding_digest,
                tenant_id=authority.tenant_id,
                tenant_registration_digest=authority.tenant_registration_digest,
                party_ref=PARTY_REF,
                party_schema_digest=authority.party_schema_digest,
                party_payload_digest=authority.party_payload_digest,
                valid_from=values["valid_from"],
                valid_until=values["valid_until"],
                predecessor_version_id=None,
                effective_at=values["effective_at"],
                decided_at=values["decided_at"],
                reason="hostile-attempt",
            )

    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert admin.execute(
            """
            SELECT
                (SELECT count(*) FROM ofarm.principal_binding
                  WHERE subject = %s),
                (SELECT count(*) FROM ofarm.principal_binding_lifecycle
                  WHERE subject = %s),
                (SELECT count(*) FROM ofarm.principal_binding_current
                  WHERE subject = %s)
            """,
            (subject, subject, subject),
        ).fetchone() == (0, 0, 0)


@pytest.mark.parametrize("party_defect", ("inactive-state", "mismatched-party-id"))
def test_transition_refuses_ineligible_party_state_and_payload_id(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    party_defect: str,
) -> None:
    party_ref = "party-" + party_defect
    batch_id = "batch-" + party_defect
    payload = {
        "partyId": (
            "different-party-id" if party_defect == "mismatched-party-id" else party_ref
        ),
        "partyState": "INACTIVE" if party_defect == "inactive-state" else "ACTIVE",
    }
    party_schema_digest = _sha256_id(b"ofarm.party.v0.1.schema")
    party_payload_digest = _sha256_id(_canonical_json(payload))
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        _insert_batch(admin, authority, batch_id)
        _insert_record(
            admin,
            authority,
            batch_id=batch_id,
            record_id=party_ref,
            record_kind=PARTY_KIND,
            payload=payload,
            lane="canonical",
        )

    subject = "subject-" + party_defect
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with psycopg.connect(
            tenant_target.role_dsn("ofarm_identity_control_login")
        ) as identity:
            valid_from, valid_until, effective_at, decided_at = identity.execute(
                """
                SELECT
                    pg_catalog.date_trunc(
                        'microseconds', pg_catalog.clock_timestamp() - INTERVAL '1 day'
                    ),
                    pg_catalog.date_trunc(
                        'microseconds', pg_catalog.clock_timestamp() + INTERVAL '1 day'
                    ),
                    pg_catalog.date_trunc(
                        'microseconds', pg_catalog.clock_timestamp() - INTERVAL '2 seconds'
                    ),
                    pg_catalog.date_trunc(
                        'microseconds', pg_catalog.clock_timestamp() - INTERVAL '1 second'
                    )
                """
            ).fetchone()
            binding_version_id = uuid4()
            act_id = uuid4()
            binding_digest = _compute_binding_digest(
                identity,
                subject=subject,
                binding_version_id=binding_version_id,
                authority=authority,
                tenant_id=authority.tenant_id,
                tenant_registration_digest=authority.tenant_registration_digest,
                party_ref=party_ref,
                party_schema_digest=party_schema_digest,
                party_payload_digest=party_payload_digest,
                valid_from=valid_from,
                valid_until=valid_until,
            )
            act_digest = _compute_act_digest(
                identity,
                subject=subject,
                stream_sequence=1,
                act_id=act_id,
                act_kind="ACTIVATE",
                binding_version_id=binding_version_id,
                binding_version_digest=binding_digest,
                prior_act_id=None,
                prior_act_digest=None,
                successor_version_id=None,
                successor_version_digest=None,
                effective_at=effective_at,
                decided_at=decided_at,
                reason="ineligible-party-attempt",
            )
            _transition(
                identity,
                subject=subject,
                expected_head_id=None,
                expected_head_digest=None,
                act_id=act_id,
                act_digest=act_digest,
                act_kind="ACTIVATE",
                binding_version_id=binding_version_id,
                binding_version_digest=binding_digest,
                candidate_version_id=binding_version_id,
                candidate_version_digest=binding_digest,
                tenant_id=authority.tenant_id,
                tenant_registration_digest=authority.tenant_registration_digest,
                party_ref=party_ref,
                party_schema_digest=party_schema_digest,
                party_payload_digest=party_payload_digest,
                valid_from=valid_from,
                valid_until=valid_until,
                predecessor_version_id=None,
                effective_at=effective_at,
                decided_at=decided_at,
                reason="ineligible-party-attempt",
            )
            identity.execute("SET CONSTRAINTS ALL IMMEDIATE")

    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert (
            admin.execute(
                "SELECT count(*) FROM ofarm.principal_binding WHERE subject = %s",
                (subject,),
            ).fetchone()[0]
            == 0
        )


def test_future_transition_and_corrupt_same_head_projection_refuse_then_rebuild(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_identity_control_login")
    ) as identity:
        future_effective, future_decided = identity.execute(
            """
            SELECT
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() + INTERVAL '1 minute'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() + INTERVAL '2 minutes'
                )
            """
        ).fetchone()
        future_act_id = uuid4()
        future_digest = _compute_act_digest(
            identity,
            subject=SUBJECT,
            stream_sequence=2,
            act_id=future_act_id,
            act_kind="REVOKE",
            binding_version_id=authority.binding_version_id,
            binding_version_digest=authority.binding_version_digest,
            prior_act_id=authority.lifecycle_head_id,
            prior_act_digest=authority.lifecycle_head_digest,
            successor_version_id=None,
            successor_version_digest=None,
            effective_at=future_effective,
            decided_at=future_decided,
            reason="future-revoke",
        )
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            with identity.transaction():
                _transition(
                    identity,
                    subject=SUBJECT,
                    expected_head_id=authority.lifecycle_head_id,
                    expected_head_digest=authority.lifecycle_head_digest,
                    act_id=future_act_id,
                    act_digest=future_digest,
                    act_kind="REVOKE",
                    binding_version_id=authority.binding_version_id,
                    binding_version_digest=authority.binding_version_digest,
                    candidate_version_id=None,
                    candidate_version_digest=None,
                    tenant_id=None,
                    tenant_registration_digest=None,
                    party_ref=None,
                    party_schema_digest=None,
                    party_payload_digest=None,
                    valid_from=None,
                    valid_until=None,
                    predecessor_version_id=None,
                    effective_at=future_effective,
                    decided_at=future_decided,
                    reason="future-revoke",
                )

    try:
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            admin.execute(
                """
                UPDATE ofarm.principal_binding_current
                SET current_state = 'INACTIVE',
                    binding_version_id = NULL,
                    binding_version_digest = NULL
                WHERE equality_policy = %s AND issuer = %s AND subject = %s
                """,
                (OIDC_ISSUER_EQUALITY_POLICY, ISSUER, SUBJECT),
            )
        with psycopg.connect(
            tenant_target.role_dsn("ofarm_identity_control_login")
        ) as identity:
            effective_at, decided_at = identity.execute(
                """
                SELECT
                    pg_catalog.date_trunc(
                        'microseconds', pg_catalog.clock_timestamp() - INTERVAL '2 seconds'
                    ),
                    pg_catalog.date_trunc(
                        'microseconds', pg_catalog.clock_timestamp() - INTERVAL '1 second'
                    )
                """
            ).fetchone()
            act_id = uuid4()
            act_digest = _compute_act_digest(
                identity,
                subject=SUBJECT,
                stream_sequence=2,
                act_id=act_id,
                act_kind="REVOKE",
                binding_version_id=authority.binding_version_id,
                binding_version_digest=authority.binding_version_digest,
                prior_act_id=authority.lifecycle_head_id,
                prior_act_digest=authority.lifecycle_head_digest,
                successor_version_id=None,
                successor_version_digest=None,
                effective_at=effective_at,
                decided_at=decided_at,
                reason="corrupt-projection-attempt",
            )
            with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
                with identity.transaction():
                    _transition(
                        identity,
                        subject=SUBJECT,
                        expected_head_id=authority.lifecycle_head_id,
                        expected_head_digest=authority.lifecycle_head_digest,
                        act_id=act_id,
                        act_digest=act_digest,
                        act_kind="REVOKE",
                        binding_version_id=authority.binding_version_id,
                        binding_version_digest=authority.binding_version_digest,
                        candidate_version_id=None,
                        candidate_version_digest=None,
                        tenant_id=None,
                        tenant_registration_digest=None,
                        party_ref=None,
                        party_schema_digest=None,
                        party_payload_digest=None,
                        valid_from=None,
                        valid_until=None,
                        predecessor_version_id=None,
                        effective_at=effective_at,
                        decided_at=decided_at,
                        reason="corrupt-projection-attempt",
                    )
    finally:
        with psycopg.connect(
            tenant_target.role_dsn("ofarm_identity_control_login")
        ) as identity:
            assert (
                identity.execute(
                    "SELECT ofarm.rebuild_principal_binding_current()"
                ).fetchone()[0]
                >= 1
            )

    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert admin.execute(
            """
            SELECT current_state, binding_version_id, binding_version_digest,
                   lifecycle_head_id, lifecycle_head_digest
            FROM ofarm.principal_binding_current
            WHERE equality_policy = %s AND issuer = %s AND subject = %s
            """,
            (OIDC_ISSUER_EQUALITY_POLICY, ISSUER, SUBJECT),
        ).fetchone() == (
            "ACTIVE",
            authority.binding_version_id,
            authority.binding_version_digest,
            authority.lifecycle_head_id,
            authority.lifecycle_head_digest,
        )


def test_missing_projection_rebuilds_from_authority(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    try:
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            admin.execute(
                "DELETE FROM ofarm.principal_binding_current WHERE subject = %s",
                (SUBJECT,),
            )
        with psycopg.connect(
            tenant_target.role_dsn("ofarm_identity_control_login")
        ) as identity:
            assert (
                identity.execute(
                    "SELECT ofarm.rebuild_principal_binding_current()"
                ).fetchone()[0]
                >= 1
            )
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            assert admin.execute(
                """
                SELECT binding_version_id, lifecycle_head_id
                FROM ofarm.principal_binding_current
                WHERE equality_policy = %s AND issuer = %s AND subject = %s
                """,
                (OIDC_ISSUER_EQUALITY_POLICY, ISSUER, SUBJECT),
            ).fetchone() == (
                authority.binding_version_id,
                authority.lifecycle_head_id,
            )
    finally:
        with psycopg.connect(
            tenant_target.role_dsn("ofarm_identity_control_login")
        ) as identity:
            assert (
                identity.execute(
                    "SELECT ofarm.rebuild_principal_binding_current()"
                ).fetchone()[0]
                >= 1
            )


def test_concurrent_same_head_principal_transition_allows_exactly_one_commit(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    subject = "subject-transition-race"
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_identity_control_login")
    ) as identity:
        initial = _initial_transition_values(
            identity, authority, subject=subject, reason="race-activation"
        )
        _transition(
            identity,
            subject=subject,
            expected_head_id=None,
            expected_head_digest=None,
            act_id=initial["act_id"],
            act_digest=initial["act_digest"],
            act_kind="ACTIVATE",
            binding_version_id=initial["binding_version_id"],
            binding_version_digest=initial["binding_digest"],
            candidate_version_id=initial["binding_version_id"],
            candidate_version_digest=initial["binding_digest"],
            tenant_id=authority.tenant_id,
            tenant_registration_digest=authority.tenant_registration_digest,
            party_ref=PARTY_REF,
            party_schema_digest=authority.party_schema_digest,
            party_payload_digest=authority.party_payload_digest,
            valid_from=initial["valid_from"],
            valid_until=initial["valid_until"],
            predecessor_version_id=None,
            effective_at=initial["effective_at"],
            decided_at=initial["decided_at"],
            reason="race-activation",
        )

    with psycopg.connect(
        tenant_target.role_dsn("ofarm_identity_control_login")
    ) as identity:
        effective_at, decided_at = identity.execute(
            """
            SELECT
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '2 seconds'
                ),
                pg_catalog.date_trunc(
                    'microseconds', pg_catalog.clock_timestamp() - INTERVAL '1 second'
                )
            """
        ).fetchone()
        candidates: list[tuple[UUID, str]] = []
        for reason in ("race-revoke-a", "race-revoke-b"):
            act_id = uuid4()
            candidates.append(
                (
                    act_id,
                    _compute_act_digest(
                        identity,
                        subject=subject,
                        stream_sequence=2,
                        act_id=act_id,
                        act_kind="REVOKE",
                        binding_version_id=initial["binding_version_id"],
                        binding_version_digest=initial["binding_digest"],
                        prior_act_id=initial["act_id"],
                        prior_act_digest=initial["act_digest"],
                        successor_version_id=None,
                        successor_version_digest=None,
                        effective_at=effective_at,
                        decided_at=decided_at,
                        reason=reason,
                    ),
                )
            )

    start = threading.Barrier(2)

    def compete(index: int) -> str:
        act_id, act_digest = candidates[index]
        reason = ("race-revoke-a", "race-revoke-b")[index]
        try:
            # The provisioned identity-control LOGIN is independently bounded to
            # one connection.  These privileged fixture sessions intentionally
            # exercise the transition function's database race invariant beneath
            # that outer operational bound; normal tests use the real LOGIN path.
            with psycopg.connect(tenant_target.target_admin_dsn) as identity:
                identity.execute("SET LOCAL ROLE ofarm_identity_writer")
                start.wait(timeout=5)
                _transition(
                    identity,
                    subject=subject,
                    expected_head_id=initial["act_id"],
                    expected_head_digest=initial["act_digest"],
                    act_id=act_id,
                    act_digest=act_digest,
                    act_kind="REVOKE",
                    binding_version_id=initial["binding_version_id"],
                    binding_version_digest=initial["binding_digest"],
                    candidate_version_id=None,
                    candidate_version_digest=None,
                    tenant_id=None,
                    tenant_registration_digest=None,
                    party_ref=None,
                    party_schema_digest=None,
                    party_payload_digest=None,
                    valid_from=None,
                    valid_until=None,
                    predecessor_version_id=None,
                    effective_at=effective_at,
                    decided_at=decided_at,
                    reason=reason,
                )
            return "committed"
        except psycopg.Error as exc:
            return exc.sqlstate or type(exc).__name__

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(compete, (0, 1)))
    assert outcomes.count("committed") == 1
    assert len([outcome for outcome in outcomes if outcome != "committed"]) == 1
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert admin.execute(
            """
            SELECT count(*), max(stream_sequence)
            FROM ofarm.principal_binding_lifecycle
            WHERE subject = %s
            """,
            (subject,),
        ).fetchone() == (2, 2)
        assert admin.execute(
            """
            SELECT current_state, binding_version_id
            FROM ofarm.principal_binding_current
            WHERE subject = %s
            """,
            (subject,),
        ).fetchone() == ("INACTIVE", None)


def _insert_batch(
    connection: psycopg.Connection,
    authority: TenantAuthority,
    batch_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO ofarm.governed_write_batch (
            tenant_id, batch_id, authenticated_principal_ref,
            governed_operation, request_id, runtime_bundle_digest
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            authority.tenant_id,
            batch_id,
            authority.party_ref,
            "TENANT_TEST_WRITE",
            "request-" + batch_id,
            authority.runtime_bundle_digest,
        ),
    )


def _insert_record(
    connection: psycopg.Connection,
    authority: TenantAuthority,
    *,
    batch_id: str,
    record_id: str,
    record_kind: str,
    payload: object,
    lane: str = "draft",
) -> None:
    payload_bytes = _canonical_json(payload)
    connection.execute(
        """
        INSERT INTO ofarm.kernel_record (
            tenant_id, record_id, record_kind, lane, schema_digest,
            payload, payload_digest, batch_id, runtime_bundle_digest
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            authority.tenant_id,
            record_id,
            record_kind,
            lane,
            _sha256_id((record_kind + ".schema").encode("ascii")),
            Jsonb(payload),
            _sha256_id(payload_bytes),
            batch_id,
            authority.runtime_bundle_digest,
        ),
    )


def test_deferred_graph_accepts_future_ids_only_with_same_batch_reachability(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    batch_id = "batch-future-graph"
    trace_id = "promotion-trace-future"
    assertion_id = "assertion-future"
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        _install_test_bound_context(application, authority)
        _insert_batch(application, authority, batch_id)
        application.execute(
            """
            INSERT INTO ofarm.kernel_edge (
                tenant_id, edge_kind, src_record_id, dst_record_id, batch_id
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                authority.tenant_id,
                "PROMOTION_EMITS",
                trace_id,
                assertion_id,
                batch_id,
            ),
        )
        _insert_record(
            application,
            authority,
            batch_id=batch_id,
            record_id=assertion_id,
            record_kind="ofarm.assertionrecord.v0.1",
            payload={"assertionId": assertion_id},
            lane="canonical",
        )
        _insert_record(
            application,
            authority,
            batch_id=batch_id,
            record_id=trace_id,
            record_kind="ofarm.promotiontrace.v0.1",
            payload={"emittedAssertionRecordRefs": [assertion_id]},
            lane="canonical",
        )

    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert admin.execute(
            """
            SELECT edge_kind, src_record_id, dst_record_id, batch_id
            FROM ofarm.kernel_edge
            WHERE tenant_id = %s AND dst_record_id = %s
            """,
            (authority.tenant_id, assertion_id),
        ).fetchone() == (
            "PROMOTION_EMITS",
            trace_id,
            assertion_id,
            batch_id,
        )

    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        _install_test_bound_context(application, authority)
        with pytest.raises(psycopg.errors.CheckViolation):
            with application.transaction():
                application.execute(
                    """
                    INSERT INTO ofarm.kernel_edge (
                        tenant_id, edge_kind, src_record_id,
                        dst_record_id, batch_id
                    ) VALUES (%s, 'UNKNOWN_EDGE', %s, %s, %s)
                    """,
                    (
                        authority.tenant_id,
                        trace_id,
                        assertion_id,
                        batch_id,
                    ),
                )

    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
            _install_test_bound_context(application, authority)
            batch_a = "batch-hostile-edge-a"
            batch_b = "batch-hostile-edge-b"
            _insert_batch(application, authority, batch_a)
            _insert_batch(application, authority, batch_b)
            _insert_record(
                application,
                authority,
                batch_id=batch_b,
                record_id="promotion-trace-wrong-batch",
                record_kind="ofarm.promotiontrace.v0.1",
                payload={"emittedAssertionRecordRefs": ["assertion-wrong-batch"]},
                lane="canonical",
            )
            _insert_record(
                application,
                authority,
                batch_id=batch_a,
                record_id="assertion-wrong-batch",
                record_kind="ofarm.assertionrecord.v0.1",
                payload={"assertionId": "assertion-wrong-batch"},
                lane="canonical",
            )
            application.execute(
                """
                INSERT INTO ofarm.kernel_edge (
                    tenant_id, edge_kind, src_record_id, dst_record_id, batch_id
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    authority.tenant_id,
                    "PROMOTION_EMITS",
                    "promotion-trace-wrong-batch",
                    "assertion-wrong-batch",
                    batch_a,
                ),
            )
            application.execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.mark.parametrize(
    ("case_name", "trace_payload"),
    (
        ("missing", {}),
        ("null", {"semanticEventRef": None}),
        ("malformed", {"emittedAssertionRecordRefs": {"unexpected": True}}),
    ),
)
def test_promotion_edge_refuses_missing_null_and_malformed_trace_references(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    case_name: str,
    trace_payload: object,
) -> None:
    batch_id = "batch-unreferenced-" + case_name
    trace_id = "promotion-trace-unreferenced-" + case_name
    assertion_id = "assertion-unreferenced-" + case_name
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
            _install_test_bound_context(application, authority)
            _insert_batch(application, authority, batch_id)
            _insert_record(
                application,
                authority,
                batch_id=batch_id,
                record_id=trace_id,
                record_kind="ofarm.promotiontrace.v0.1",
                payload=trace_payload,
                lane="canonical",
            )
            _insert_record(
                application,
                authority,
                batch_id=batch_id,
                record_id=assertion_id,
                record_kind="ofarm.assertionrecord.v0.1",
                payload={"assertionId": assertion_id},
                lane="canonical",
            )
            application.execute(
                """
                INSERT INTO ofarm.kernel_edge (
                    tenant_id, edge_kind, src_record_id, dst_record_id, batch_id
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    authority.tenant_id,
                    "PROMOTION_EMITS",
                    trace_id,
                    assertion_id,
                    batch_id,
                ),
            )
            application.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_full_xid_binding_refuses_two_transaction_future_id_completion(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    old_batch_id = "batch-old-cross-transaction"
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as creator:
        _install_test_bound_context(creator, authority)
        _insert_batch(creator, authority, old_batch_id)
        old_full_xid = creator.execute(
            """
            SELECT full_xid
            FROM ofarm.governed_write_batch
            WHERE tenant_id = %s AND batch_id = %s
            """,
            (authority.tenant_id, old_batch_id),
        ).fetchone()[0]

    edge_session = psycopg.connect(tenant_target.role_dsn("ofarm_app"))
    record_session = psycopg.connect(tenant_target.role_dsn("ofarm_app"))
    try:
        _install_test_bound_context(edge_session, authority)
        _install_test_bound_context(record_session, authority)
        edge_session.execute(
            """
            INSERT INTO ofarm.kernel_edge (
                tenant_id, edge_kind, src_record_id, dst_record_id,
                batch_id, batch_full_xid
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                authority.tenant_id,
                "PROMOTION_EMITS",
                "promotion-trace-cross-transaction",
                "assertion-cross-transaction",
                old_batch_id,
                old_full_xid,
            ),
        )
        _insert_record(
            record_session,
            authority,
            batch_id=old_batch_id,
            record_id="promotion-trace-cross-transaction",
            record_kind="ofarm.promotiontrace.v0.1",
            payload={"emittedAssertionRecordRefs": ["assertion-cross-transaction"]},
            lane="canonical",
        )
        _insert_record(
            record_session,
            authority,
            batch_id=old_batch_id,
            record_id="assertion-cross-transaction",
            record_kind="ofarm.assertionrecord.v0.1",
            payload={"assertionId": "assertion-cross-transaction"},
            lane="canonical",
        )
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            record_session.commit()
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            edge_session.commit()
    finally:
        edge_session.close()
        record_session.close()

    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert (
            admin.execute(
                """
            SELECT count(*)
            FROM ofarm.kernel_record
            WHERE record_id IN (
                'promotion-trace-cross-transaction',
                'assertion-cross-transaction'
            )
            """
            ).fetchone()[0]
            == 0
        )
        trigger_rows = admin.execute(
            """
            SELECT trigger.tgname
            FROM pg_catalog.pg_trigger AS trigger
            JOIN pg_catalog.pg_class AS class ON class.oid = trigger.tgrelid
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = class.relnamespace
            WHERE namespace.nspname = 'ofarm'
              AND trigger.tgname IN (
                'governed_write_batch_stamp_full_xid',
                'kernel_record_stamp_batch_full_xid',
                'kernel_edge_stamp_batch_full_xid'
              )
              AND trigger.tgenabled = 'O'
              AND NOT trigger.tgisinternal
            ORDER BY trigger.tgname
            """
        ).fetchall()
    assert trigger_rows == [
        ("governed_write_batch_stamp_full_xid",),
        ("kernel_edge_stamp_batch_full_xid",),
        ("kernel_record_stamp_batch_full_xid",),
    ]


def test_derived_key_identity_and_typed_source_lanes_are_database_enforced(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    batch_id = "batch-derived-identity"
    basis_id = ":record"
    snapshot_id = "derived-snapshot-01"
    context_id = "derived-context-01"
    materialization_id = "materialization-01"
    materialization_key = {
        "anchorScopeRef": "farm-01",
        "targetTwin": "compliance",
        "timePolicy": {"policyType": "NOW"},
    }
    runtime_content = b"derived-runtime-logical-ref-boundary"
    runtime_content_digest = _sha256_id(runtime_content)
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        _install_test_bound_context(application, authority)
        _insert_batch(application, authority, batch_id)
        application.execute(
            """
            INSERT INTO ofarm.runtime_tenant_content_blob (
                tenant_id, content_digest, canonical_bytes, byte_length
            ) VALUES (%s, %s, %s, %s)
            """,
            (
                authority.tenant_id,
                runtime_content_digest,
                runtime_content,
                len(runtime_content),
            ),
        )
        application.execute(
            """
            INSERT INTO ofarm.runtime_bundle_component (
                tenant_id, bundle_digest, component_role, logical_ref,
                canonicalization, content_placement, tenant_content_digest,
                byte_length
            ) VALUES (
                %s, %s, 'REFERENCE_SOURCE', %s,
                'EXACT_BYTES_V1', 'TENANT_RUNTIME_SELECTION', %s, %s
            )
            """,
            (
                authority.tenant_id,
                authority.runtime_bundle_digest,
                RUNTIME_LOGICAL_REF_MAX,
                runtime_content_digest,
                len(runtime_content),
            ),
        )
        for record_id in (basis_id, snapshot_id, context_id):
            _insert_record(
                application,
                authority,
                batch_id=batch_id,
                record_id=record_id,
                record_kind="ofarm.derivedtest.v0.1",
                payload={"recordId": record_id},
            )
        key_digest = application.execute(
            "SELECT ofarm.compute_materialization_key_digest(%s)",
            (Jsonb(materialization_key),),
        ).fetchone()[0]
        application.execute(
            """
            INSERT INTO ofarm.derived_materialization (
                tenant_id, materialization_id, key_digest, materialization_key,
                target_twin, anchor_scope_ref, time_policy, use_class,
                freshness, current_state, basis_record_id, snapshot_record_id,
                context_snapshot_ref, freshness_vector, batch_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                authority.tenant_id,
                materialization_id,
                key_digest,
                Jsonb(materialization_key),
                "compliance",
                "farm-01",
                Jsonb({"policyType": "NOW"}),
                "OPERATIONAL_DASHBOARD",
                "FRESH",
                Jsonb({"status": "ready"}),
                basis_id,
                snapshot_id,
                context_id,
                Jsonb({"basis": [basis_id]}),
                batch_id,
            ),
        )
        application.execute(
            """
            INSERT INTO ofarm.derived_dependency_index (
                tenant_id, dependency_source_ref, dependency_source_family,
                dependency_source_lane, dependency_runtime_bundle_digest,
                dependency_runtime_component_role, materialization_id,
                key_digest, materialization_key, entry
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                authority.tenant_id,
                RUNTIME_LOGICAL_REF_MAX,
                "RULE_EVIDENCE_POLICY",
                "RUNTIME_BUNDLE_COMPONENT",
                authority.runtime_bundle_digest,
                "REFERENCE_SOURCE",
                materialization_id,
                key_digest,
                Jsonb(materialization_key),
                Jsonb({"dependencySourceRef": RUNTIME_LOGICAL_REF_MAX}),
            ),
        )
        assert application.execute(
            """
            SELECT
                pg_catalog.octet_length(dependency_source_ref),
                dependency_runtime_logical_ref::pg_catalog.text
            FROM ofarm.derived_dependency_index
            WHERE tenant_id = %s
              AND dependency_source_lane = 'RUNTIME_BUNDLE_COMPONENT'
              AND dependency_source_ref = %s
            """,
            (authority.tenant_id, RUNTIME_LOGICAL_REF_MAX),
        ).fetchone() == (1024, RUNTIME_LOGICAL_REF_MAX)
        application.execute(
            """
            INSERT INTO ofarm.derived_dependency_index (
                tenant_id, dependency_source_ref, dependency_source_family,
                dependency_source_lane, materialization_id, key_digest,
                materialization_key, entry
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                authority.tenant_id,
                basis_id,
                "TRUTH_BASIS",
                "KERNEL_RECORD",
                materialization_id,
                key_digest,
                Jsonb(materialization_key),
                Jsonb({"dependencySourceRef": basis_id}),
            ),
        )
        assert application.execute(
            """
            SELECT dependency_kernel_record_ref::pg_catalog.text
            FROM ofarm.derived_dependency_index
            WHERE tenant_id = %s
              AND dependency_source_lane = 'KERNEL_RECORD'
              AND dependency_source_ref = %s
            """,
            (authority.tenant_id, basis_id),
        ).fetchone() == (basis_id,)

        different_key = {**materialization_key, "targetTwin": "operations"}
        different_digest = application.execute(
            "SELECT ofarm.compute_materialization_key_digest(%s)",
            (Jsonb(different_key),),
        ).fetchone()[0]
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with application.transaction():
                application.execute(
                    """
                    INSERT INTO ofarm.derived_dependency_index (
                        tenant_id, dependency_source_ref,
                        dependency_source_family, dependency_source_lane,
                        materialization_id, key_digest, materialization_key, entry
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        authority.tenant_id,
                        basis_id,
                        "TRUTH_BASIS",
                        "KERNEL_RECORD",
                        materialization_id,
                        different_digest,
                        Jsonb(different_key),
                        Jsonb({}),
                    ),
                )

        with pytest.raises(psycopg.errors.CheckViolation):
            with application.transaction():
                application.execute(
                    """
                    INSERT INTO ofarm.derived_dependency_index (
                        tenant_id, dependency_source_ref,
                        dependency_source_family, dependency_source_lane,
                        materialization_id, key_digest, materialization_key, entry
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        authority.tenant_id,
                        "missing-runtime-component",
                        "RULE_EVIDENCE_POLICY",
                        "RUNTIME_BUNDLE_COMPONENT",
                        materialization_id,
                        key_digest,
                        Jsonb(materialization_key),
                        Jsonb({}),
                    ),
                )

        with pytest.raises(psycopg.errors.CheckViolation):
            with application.transaction():
                application.execute(
                    """
                    INSERT INTO ofarm.derived_materialization (
                        tenant_id, materialization_id, key_digest,
                        materialization_key, target_twin, anchor_scope_ref,
                        time_policy, use_class, freshness, current_state,
                        basis_record_id, snapshot_record_id,
                        context_snapshot_ref, freshness_vector, batch_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        authority.tenant_id,
                        "materialization-collision",
                        key_digest,
                        Jsonb(different_key),
                        "operations",
                        "farm-01",
                        Jsonb({"policyType": "NOW"}),
                        "OPERATIONAL_DASHBOARD",
                        "FRESH",
                        Jsonb({}),
                        basis_id,
                        snapshot_id,
                        context_id,
                        Jsonb({}),
                        batch_id,
                    ),
                )

    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        definitions = dict(
            admin.execute(
                """
                SELECT governed_constraint.conname,
                       pg_catalog.pg_get_constraintdef(governed_constraint.oid)
                FROM pg_catalog.pg_constraint AS governed_constraint
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = governed_constraint.connamespace
                WHERE namespace.nspname = 'ofarm'
                  AND governed_constraint.conname IN (
                    'derived_materialization_key_key',
                    'derived_dependency_index_materialization_fkey'
                  )
                """
            ).fetchall()
        )
    assert "materialization_key" in definitions["derived_materialization_key_key"]
    assert (
        "materialization_key"
        in (definitions["derived_dependency_index_materialization_fkey"])
    )


def test_complete_catalog_fingerprint_refuses_function_constraint_index_policy_and_acl_tamper(
    tenant_target: TenantTarget,
) -> None:
    tamper_statements = (
        """
        CREATE OR REPLACE FUNCTION ofarm.valid_ascii_id(value pg_catalog.text)
        RETURNS pg_catalog.bool
        LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS 'SELECT true'
        """,
        """
        ALTER TABLE ofarm.kernel_record
        DROP CONSTRAINT kernel_record_lane_check
        """,
        """
        ALTER TABLE ofarm.kernel_edge
        DROP CONSTRAINT kernel_edge_kind_check
        """,
        "DROP INDEX ofarm.kernel_record_kind_idx",
        """
        ALTER POLICY tenant_isolation ON ofarm.kernel_record
        USING (true)
        """,
        "GRANT SELECT (payload) ON ofarm.kernel_record TO ofarm_binder",
        "GRANT CREATE ON SCHEMA public TO ofarm_app",
        "CREATE TABLE public.ofarm_rogue_catalog_object (id pg_catalog.int4)",
        "GRANT USAGE ON TYPE ofarm.sha256_id TO ofarm_binder",
    )
    with psycopg.connect(tenant_target.migrator_dsn, autocommit=True) as migrator:
        migrator.execute("BEGIN")
        try:
            pristine = _verify(migrator)
            assert pristine[0] is True
            assert pristine[2] == 0
            assert pristine[3] == (
                "sha256:19c387e9677811047679d349349895cf3213637fe462b2257a2408775469f26e"
            )
        finally:
            migrator.rollback()

        for statement in tamper_statements:
            migrator.execute("BEGIN")
            try:
                migrator.execute("SET LOCAL ROLE ofarm_owner")
                migrator.execute(statement)
                row = migrator.execute(
                    "SELECT * FROM ofarm.verify_tenant_structure()"
                ).fetchone()
                assert row[0] is False, statement
                assert row[2] >= 1
                assert row[3] != pristine[3]
            finally:
                migrator.rollback()


def test_tenant_verifier_is_invariant_to_hostile_quote_all_identifiers(
    tenant_target: TenantTarget,
) -> None:
    with psycopg.connect(tenant_target.migrator_dsn, autocommit=True) as migrator:
        migrator.execute("BEGIN")
        try:
            pristine = _verify(migrator)
        finally:
            migrator.rollback()

        migrator.execute("BEGIN")
        try:
            migrator.execute("SET LOCAL quote_all_identifiers = on")
            hostile = _verify(migrator)
            assert migrator.execute("SHOW quote_all_identifiers").fetchone() == ("on",)
        finally:
            migrator.rollback()

    assert hostile == pristine
    assert hostile[0] is True
    assert hostile[2] == 0


def test_database_role_setting_tamper_changes_fingerprint_and_restores(
    tenant_target: TenantTarget,
) -> None:
    try:
        with psycopg.connect(tenant_target.admin_dsn, autocommit=True) as admin:
            admin.execute(
                "ALTER ROLE ofarm_app IN DATABASE ofarm_tenant SET work_mem = '8192kB'"
            )
        with psycopg.connect(tenant_target.migrator_dsn) as migrator:
            assert _verify(migrator)[0] is False
    finally:
        with psycopg.connect(tenant_target.admin_dsn, autocommit=True) as admin:
            admin.execute(
                "ALTER ROLE ofarm_app IN DATABASE ofarm_tenant SET work_mem = '4096'"
            )
    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        assert _verify(migrator)[0] is True


@pytest.mark.parametrize(
    ("tamper_statement", "restore_statement"),
    (
        (
            "ALTER FUNCTION ofarm_infrastructure.take_migration_lock() COST 101",
            "ALTER FUNCTION ofarm_infrastructure.take_migration_lock() COST 100",
        ),
        (
            "GRANT EXECUTE ON FUNCTION ofarm.current_backend_start() TO ofarm_app",
            "REVOKE EXECUTE ON FUNCTION ofarm.current_backend_start() FROM ofarm_app",
        ),
        (
            "GRANT SET ON PARAMETER session_replication_role TO ofarm_app",
            "REVOKE SET ON PARAMETER session_replication_role FROM ofarm_app",
        ),
        (
            "GRANT EXECUTE ON FUNCTION pg_catalog.lo_create(pg_catalog.oid) TO PUBLIC",
            "REVOKE EXECUTE ON FUNCTION pg_catalog.lo_create(pg_catalog.oid) "
            "FROM PUBLIC",
        ),
        (
            "ALTER FUNCTION pg_catalog.lo_create(pg_catalog.oid) COST 2",
            "ALTER FUNCTION pg_catalog.lo_create(pg_catalog.oid) COST 1",
        ),
        (
            "CREATE FUNCTION pg_catalog.lo_backdoor() RETURNS pg_catalog.int4 "
            "LANGUAGE sql IMMUTABLE AS 'SELECT 1'",
            "DROP FUNCTION pg_catalog.lo_backdoor()",
        ),
        (
            "GRANT SELECT ON pg_catalog.pg_stat_activity TO ofarm_app",
            "REVOKE SELECT ON pg_catalog.pg_stat_activity FROM ofarm_app",
        ),
        (
            "GRANT EXECUTE ON FUNCTION "
            "pg_catalog.pg_stat_get_backend_activity(pg_catalog.int4) "
            "TO ofarm_app",
            "REVOKE EXECUTE ON FUNCTION "
            "pg_catalog.pg_stat_get_backend_activity(pg_catalog.int4) "
            "FROM ofarm_app",
        ),
        (
            "ALTER FUNCTION "
            "pg_catalog.pg_stat_get_backend_activity(pg_catalog.int4) COST 2",
            "ALTER FUNCTION "
            "pg_catalog.pg_stat_get_backend_activity(pg_catalog.int4) COST 1",
        ),
        (
            "CREATE FUNCTION pg_catalog.pg_stat_get_activity_backdoor() "
            "RETURNS pg_catalog.int4 LANGUAGE sql IMMUTABLE AS 'SELECT 1'",
            "DROP FUNCTION pg_catalog.pg_stat_get_activity_backdoor()",
        ),
        (
            "CREATE FUNCTION pg_catalog.pg_stat_get_backend_backdoor() "
            "RETURNS pg_catalog.int4 LANGUAGE sql IMMUTABLE AS 'SELECT 1'",
            "DROP FUNCTION pg_catalog.pg_stat_get_backend_backdoor()",
        ),
        (
            "GRANT pg_signal_backend TO pg_read_all_stats",
            "REVOKE pg_signal_backend FROM pg_read_all_stats",
        ),
        (
            "CREATE PUBLICATION ofarm_hostile_publication",
            "DROP PUBLICATION ofarm_hostile_publication",
        ),
    ),
)
def test_global_and_infrastructure_catalog_drift_refuses_and_restores(
    tenant_target: TenantTarget,
    tamper_statement: str,
    restore_statement: str,
) -> None:
    try:
        with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
            admin.execute(tamper_statement)
        with psycopg.connect(tenant_target.migrator_dsn) as migrator:
            assert _verify(migrator)[0] is False
    finally:
        with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
            admin.execute(restore_statement)
    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        assert _verify(migrator)[0] is True


def test_backend_statistics_view_definition_tamper_preserves_acl_and_refuses(
    tenant_target: TenantTarget,
) -> None:
    original_definition: str | None = None
    original_acl: str | None = None
    try:
        with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
            original_definition, original_acl = admin.execute(
                """
                SELECT
                    pg_catalog.pg_get_viewdef(class.oid, false),
                    class.relacl::pg_catalog.text
                FROM pg_catalog.pg_class AS class
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = class.relnamespace
                WHERE namespace.nspname = 'pg_catalog'
                  AND class.relname = 'pg_stat_activity'
                  AND class.relkind = 'v'
                """
            ).fetchone()
            assert original_definition is not None
            original_definition = original_definition.rstrip().removesuffix(";")
            admin.execute(
                sql.SQL(
                    "CREATE OR REPLACE VIEW pg_catalog.pg_stat_activity AS "
                    "SELECT original_activity.* FROM ({}) AS original_activity "
                    "WHERE false"
                ).format(sql.SQL(original_definition))
            )
            tampered_acl = admin.execute(
                """
                SELECT class.relacl::pg_catalog.text
                FROM pg_catalog.pg_class AS class
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = class.relnamespace
                WHERE namespace.nspname = 'pg_catalog'
                  AND class.relname = 'pg_stat_activity'
                """
            ).fetchone()[0]
            assert tampered_acl == original_acl

        with psycopg.connect(tenant_target.migrator_dsn) as migrator:
            observed = _verify(migrator)
            assert observed[0] is False
            assert observed[2] >= 1
    finally:
        if original_definition is not None:
            with psycopg.connect(
                tenant_target.target_admin_dsn, autocommit=True
            ) as admin:
                admin.execute(
                    sql.SQL(
                        "CREATE OR REPLACE VIEW pg_catalog.pg_stat_activity AS {}"
                    ).format(sql.SQL(original_definition))
                )
                restored_acl = admin.execute(
                    """
                    SELECT class.relacl::pg_catalog.text
                    FROM pg_catalog.pg_class AS class
                    JOIN pg_catalog.pg_namespace AS namespace
                      ON namespace.oid = class.relnamespace
                    WHERE namespace.nspname = 'pg_catalog'
                      AND class.relname = 'pg_stat_activity'
                    """
                ).fetchone()[0]
                assert restored_acl == original_acl

    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        assert _verify(migrator)[0] is True


def test_large_object_state_is_fingerprinted_refused_and_removable(
    tenant_target: TenantTarget,
) -> None:
    large_object_oid: int | None = None
    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        pristine = _verify(migrator)
        assert pristine[0] is True
    try:
        with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
            large_object_oid = admin.execute(
                "SELECT pg_catalog.lo_from_bytea(0::pg_catalog.oid, %s)",
                (b"hostile-cross-tenant-large-object",),
            ).fetchone()[0]
        with psycopg.connect(tenant_target.migrator_dsn) as migrator:
            observed = _verify(migrator)
            assert observed[0] is False
            assert observed[2] >= 1
            assert observed[3] != pristine[3]
    finally:
        if large_object_oid is not None:
            with psycopg.connect(
                tenant_target.target_admin_dsn, autocommit=True
            ) as admin:
                admin.execute(
                    "SELECT pg_catalog.lo_unlink(%s)",
                    (large_object_oid,),
                )

    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        assert _verify(migrator)[0] is True


def test_superuser_advisory_acl_tamper_is_name_portable_and_refused(
    tenant_target: TenantTarget,
) -> None:
    role_names = (
        "tenant_catalog_portability_" + uuid4().hex + "_a",
        "tenant_catalog_portability_" + uuid4().hex + "_b",
    )
    try:
        with psycopg.connect(tenant_target.admin_dsn, autocommit=True) as admin:
            for role_name in role_names:
                admin.execute(
                    f'CREATE ROLE "{role_name}" NOLOGIN SUPERUSER '
                    "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                )

        fingerprints: list[str] = []
        with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
            for role_name in role_names:
                try:
                    admin.execute(
                        "GRANT EXECUTE ON FUNCTION "
                        "pg_catalog.pg_advisory_lock(pg_catalog.int8) "
                        f'TO "{role_name}"'
                    )
                    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
                        observed = _verify(migrator)
                    assert observed[0] is False
                    assert observed[2] >= 1
                    fingerprints.append(observed[3])
                finally:
                    admin.execute(
                        "REVOKE EXECUTE ON FUNCTION "
                        "pg_catalog.pg_advisory_lock(pg_catalog.int8) "
                        f'FROM "{role_name}"'
                    )

        assert fingerprints[0] == fingerprints[1]
    finally:
        with psycopg.connect(tenant_target.admin_dsn, autocommit=True) as admin:
            for role_name in reversed(role_names):
                admin.execute(f'DROP ROLE IF EXISTS "{role_name}"')

    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        assert _verify(migrator)[0] is True


def test_public_runner_refuses_catalog_observer_acl_tamper_before_trust(
    tenant_target: TenantTarget,
) -> None:
    try:
        with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
            admin.execute(
                """
                GRANT EXECUTE ON FUNCTION ofarm.observe_tenant_contract()
                TO ofarm_app
                """
            )
        with pytest.raises(
            MigrationDirtyError,
            match="catalog verifier identity differs",
        ):
            migrate_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=tenant_target.migrator_dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=tenant_target.migration_set,
                release_identity=RELEASE_IDENTITY,
                execution_id=uuid4(),
            )
    finally:
        with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
            admin.execute(
                """
                REVOKE EXECUTE ON FUNCTION ofarm.observe_tenant_contract()
                FROM ofarm_app
                """
            )
    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        assert _verify(migrator)[0] is True


def test_public_runner_noop_refuses_non_provisioning_application_index_tamper(
    tenant_target: TenantTarget,
) -> None:
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute("SET LOCAL ROLE ofarm_owner")
        admin.execute("DROP INDEX ofarm.kernel_record_kind_idx")
    try:
        with pytest.raises(MigrationDirtyError):
            migrate_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=tenant_target.migrator_dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=tenant_target.migration_set,
                release_identity=RELEASE_IDENTITY,
                execution_id=uuid4(),
            )
    finally:
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            admin.execute("SET LOCAL ROLE ofarm_owner")
            admin.execute(
                """
                CREATE INDEX kernel_record_kind_idx
                ON ofarm.kernel_record (
                    tenant_id, record_kind COLLATE pg_catalog."C"
                )
                """
            )
    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        assert _verify(migrator)[0] is True


def test_post_migration_schema_local_collation_tamper_refuses_every_gate(
    tenant_target: TenantTarget,
) -> None:
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute("SET LOCAL ROLE ofarm_owner")
        admin.execute(
            "CREATE COLLATION ofarm.rogue (provider = builtin, locale = 'C')"
        )
    try:
        with psycopg.connect(tenant_target.migrator_dsn) as migrator:
            verifier_row = _verify(migrator)
        assert verifier_row[0] is False
        assert verifier_row[2] >= 1

        with psycopg.connect(
            tenant_target.role_dsn("ofarm_readiness")
        ) as readiness:
            observer_row = readiness.execute(
                "SELECT * FROM ofarm.observe_tenant_contract()"
            ).fetchone()
        assert observer_row[0] is False
        assert observer_row[2] >= 1

        with pytest.raises(MigrationDirtyError):
            migrate_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=tenant_target.migrator_dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=tenant_target.migration_set,
                release_identity=RELEASE_IDENTITY,
                execution_id=uuid4(),
            )
    finally:
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            admin.execute("SET LOCAL ROLE ofarm_owner")
            admin.execute("DROP COLLATION ofarm.rogue")

    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        assert _verify(migrator)[0] is True


def test_readiness_observation_is_complete_after_commit(
    tenant_target: TenantTarget,
) -> None:
    with psycopg.connect(tenant_target.role_dsn("ofarm_readiness")) as readiness:
        row = readiness.execute(
            "SELECT * FROM ofarm.observe_tenant_contract()"
        ).fetchone()
    assert row[0] is True
    assert row[1] == TENANT_CONTEXT_CONTRACT.digest
    assert row[2] == 0
    assert row[3] == (
        "sha256:19c387e9677811047679d349349895cf3213637fe462b2257a2408775469f26e"
    )
    assert row[5] == TENANT_PROVISIONING_SPEC.digest
    assert row[6] == TENANT_SERVICE.identity
    assert row[7] == 1
    assert row[9] == 1
    assert row[10] is False
