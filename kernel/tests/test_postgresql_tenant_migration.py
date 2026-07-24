"""Real-role PostgreSQL 17 tests for the authoritative tenant baseline."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
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
    MigrationTargetError,
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
    TENANT_CAPABILITY_CONTRACT,
    TENANT_CAPABILITY_PREFLIGHT_PROBE,
    TENANT_CONTEXT_CONTRACT,
    TenantCapability,
    TenantCapabilityContractError,
    derive_ed25519_key_id,
    valid_oidc_issuer,
    validate_tenant_capability,
)
from kernel.tests.tenant_capability_fixture import (
    RFC8032_TEST_PUBLIC_KEY,
    RFC8032_TEST_SEED,
    public_key_from_seed,
    sign,
    sign_capability,
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


@dataclass(frozen=True, slots=True)
class CapabilityKeyAuthority:
    kid: str
    candidate_id: UUID
    candidate_digest: str
    head_id: UUID
    head_digest: str
    activated_at_unix_microseconds: int


@dataclass(frozen=True, slots=True)
class CapabilityKeyCandidate:
    seed: bytes
    public_key: bytes
    kid: str
    candidate_id: UUID
    candidate_digest: str
    preflight_receipt_digest: str


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


def _raw_sha256(value: str) -> bytes:
    assert value.startswith("sha256:")
    return bytes.fromhex(value.removeprefix("sha256:"))


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _runtime_component_identity(
    *,
    role: str,
    logical_ref: str,
    canonicalization: str,
    placement: str,
    content_digest: str,
    byte_length: int,
) -> dict[str, object]:
    return {
        "role": role,
        "logicalRef": logical_ref,
        "canonicalization": canonicalization,
        "placement": placement,
        "contentDigest": content_digest,
        "byteLength": byte_length,
    }


def _publish_runtime_bundle(
    connection: psycopg.Connection,
    tenant_id: UUID,
    components: list[dict[str, object]],
) -> str:
    ordered = sorted(
        components,
        key=lambda item: (str(item["role"]), str(item["logicalRef"])),
    )
    document = {
        "schemaVersion": "ofarm.runtime-bundle.local.v1",
        "canonicalization": "OFARM_CANONICAL_JSON_V1",
        "components": ordered,
    }
    digest = _sha256_id(_canonical_json(document))
    assert connection.execute(
        "SELECT ofarm.publish_runtime_bundle(%s, %s, %s)",
        (tenant_id, digest, Jsonb(document)),
    ).fetchone() == (digest,)
    return digest


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

    bundle_content = b"tenant-alpha-runtime-reference-source-v1"
    bundle_content_digest = _sha256_id(bundle_content)
    batch_id = "batch-authority-01"
    party_payload = {"partyId": PARTY_REF, "partyState": "ACTIVE"}
    party_schema_digest = _sha256_id(b"ofarm.party.v0.1.schema")
    party_payload_digest = _sha256_id(_canonical_json(party_payload))
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute(
            """
            INSERT INTO ofarm.runtime_content_blob (
                content_digest, canonical_bytes, byte_length
            ) VALUES (%s, %s, %s)
            """,
            (
                bundle_content_digest,
                bundle_content,
                len(bundle_content),
            ),
        )
        bundle_digest = _publish_runtime_bundle(
            admin,
            tenant_id,
            [
                _runtime_component_identity(
                    role="REFERENCE_SOURCE",
                    logical_ref=RUNTIME_LOGICAL_REF_MAX,
                    canonicalization="EXACT_BYTES_V1",
                    placement="GLOBAL_IMMUTABLE_CONTENT",
                    content_digest=bundle_content_digest,
                    byte_length=len(bundle_content),
                )
            ],
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


def _register_capability_key_candidate(
    controller: psycopg.Connection,
    *,
    seed: bytes,
    label: str,
) -> CapabilityKeyCandidate:
    public_key = public_key_from_seed(seed)
    kms_attestation_digest = _sha256_id(
        f"{label}-hsm-attestation-v1".encode("ascii")
    )
    probe_signature = sign(seed, TENANT_CAPABILITY_PREFLIGHT_PROBE)
    candidate_id, kid, candidate_digest = controller.execute(
        """
        SELECT *
        FROM ofarm.register_tenant_capability_key(%s, %s, %s)
        """,
        (
            public_key,
            (
                "projects/example/locations/europe-west1/keyRings/ofarm/"
                f"cryptoKeys/{label}/cryptoKeyVersions/1"
            ),
            kms_attestation_digest,
        ),
    ).fetchone()
    controller.commit()
    assert controller.execute(
        """
        SELECT ofarm.verify_tenant_capability_candidate_preflight(%s, %s)
        """,
        (kid, probe_signature),
    ).fetchone() == (True,)
    controller.commit()
    preflight_receipt_digest = _sha256_id(
        f"{label}-preflight-removal-receipt-v1".encode("ascii")
    )
    return CapabilityKeyCandidate(
        seed=seed,
        public_key=public_key,
        kid=kid,
        candidate_id=candidate_id,
        candidate_digest=candidate_digest,
        preflight_receipt_digest=preflight_receipt_digest,
    )


@pytest.fixture(scope="module")
def capability_key(
    tenant_target: TenantTarget,
) -> CapabilityKeyAuthority:
    """Install and activate the RFC-vector key through the real controller."""

    kms_evidence_digest = _sha256_id(b"rfc8032-kms-enable-evidence-v1")
    iam_evidence_digest = _sha256_id(b"rfc8032-iam-removal-evidence-v1")
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_capability_key_control_login")
    ) as controller:
        candidate = _register_capability_key_candidate(
            controller,
            seed=RFC8032_TEST_SEED,
            label="tenant-capability",
        )
        head_id, head_digest, activated_at = controller.execute(
            """
            SELECT *
            FROM ofarm.activate_tenant_capability_key(
                %s, NULL, NULL, %s, %s, %s, 'INITIAL_ACTIVATION'
            )
            """,
            (
                candidate.kid,
                candidate.preflight_receipt_digest,
                kms_evidence_digest,
                iam_evidence_digest,
            ),
        ).fetchone()
    assert candidate.public_key == RFC8032_TEST_PUBLIC_KEY
    assert candidate.kid == derive_ed25519_key_id(RFC8032_TEST_PUBLIC_KEY)
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_capability_key_control_login")
    ) as controller:
        with pytest.raises(psycopg.errors.InvalidAuthorizationSpecification):
            controller.execute(
                """
                SELECT ofarm.verify_tenant_capability_candidate_preflight(
                    %s, %s
                )
                """,
                (
                    candidate.kid,
                    sign(candidate.seed, TENANT_CAPABILITY_PREFLIGHT_PROBE),
                ),
            )
    return CapabilityKeyAuthority(
        kid=candidate.kid,
        candidate_id=candidate.candidate_id,
        candidate_digest=candidate.candidate_digest,
        head_id=head_id,
        head_digest=head_digest,
        activated_at_unix_microseconds=activated_at,
    )


def _tenant_capability(
    *,
    authority: TenantAuthority,
    key: CapabilityKeyAuthority,
    challenge_id: UUID,
    audience: str,
    now_unix_microseconds: int,
) -> TenantCapability:
    return TenantCapability(
        contract_digest=TENANT_CAPABILITY_CONTRACT.raw_digest,
        challenge_id=challenge_id,
        audience=audience,
        key_id=key.kid,
        equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
        issuer=ISSUER,
        subject=authority.subject,
        binding_version_id=authority.binding_version_id,
        binding_version_digest=_raw_sha256(authority.binding_version_digest),
        lifecycle_head_id=authority.lifecycle_head_id,
        lifecycle_head_digest=_raw_sha256(authority.lifecycle_head_digest),
        tenant_id=authority.tenant_id,
        tenant_registration_digest=_raw_sha256(
            authority.tenant_registration_digest
        ),
        party_ref=authority.party_ref,
        party_record_kind=PARTY_KIND,
        party_record_id=authority.party_ref,
        party_schema_digest=_raw_sha256(authority.party_schema_digest),
        party_payload_digest=_raw_sha256(authority.party_payload_digest),
        issued_at_unix_microseconds=now_unix_microseconds,
        not_before_unix_microseconds=now_unix_microseconds,
        expires_at_unix_microseconds=now_unix_microseconds + 30_000_000,
        nonce=uuid4(),
    )


ADMISSION_LOCK_CLASS_ID = 1330004306
ADMISSION_LOCK_OBJECT_ID = 1413694001


def _signed_capability_for_new_challenge(
    connection: psycopg.Connection,
    *,
    authority: TenantAuthority,
    key: CapabilityKeyAuthority,
) -> str:
    challenge_id, audience = connection.execute(
        "SELECT * FROM ofarm.create_tenant_challenge()"
    ).fetchone()
    now_us = connection.execute(
        """
        SELECT (extract(epoch FROM pg_catalog.clock_timestamp()) *
                1000000)::pg_catalog.int8
        """
    ).fetchone()[0]
    return sign_capability(
        _tenant_capability(
            authority=authority,
            key=key,
            challenge_id=challenge_id,
            audience=audience,
            now_unix_microseconds=now_us,
        )
    )


def _admission_locks(
    admin: psycopg.Connection,
    *backend_pids: int,
) -> set[tuple[int, str, bool]]:
    return set(
        admin.execute(
            """
            SELECT lock.pid, lock.mode, lock.granted
            FROM pg_catalog.pg_locks AS lock
            WHERE lock.pid = ANY(%s::pg_catalog.int4[])
              AND lock.locktype = 'advisory'
              AND lock.classid = %s
              AND lock.objid = %s
            """,
            (
                list(backend_pids),
                ADMISSION_LOCK_CLASS_ID,
                ADMISSION_LOCK_OBJECT_ID,
            ),
        ).fetchall()
    )


def _wait_for_admission_locks(
    admin: psycopg.Connection,
    expected: set[tuple[int, str, bool]],
) -> None:
    observed: set[tuple[int, str, bool]] = set()
    backend_pids = tuple(pid for pid, _mode, _granted in expected)
    for _attempt in range(500):
        observed = _admission_locks(admin, *backend_pids)
        if expected <= observed:
            return
        threading.Event().wait(0.01)
    assert expected <= observed, (expected, observed)


@pytest.fixture(scope="module")
def other_authority(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> TenantAuthority:
    tenant_id = authority.other_tenant_id
    registration_digest = authority.other_tenant_registration_digest
    subject = "subject-tenant-02"
    party_ref = "party-02"
    bundle_content = b"tenant-beta-runtime-reference-source-v1"
    bundle_content_digest = _sha256_id(bundle_content)
    batch_id = "batch-authority-02"
    party_payload = {"partyId": party_ref, "partyState": "ACTIVE"}
    party_schema_digest = _sha256_id(b"ofarm.party.v0.1.schema")
    party_payload_digest = _sha256_id(_canonical_json(party_payload))
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute(
            """
            INSERT INTO ofarm.runtime_content_blob (
                content_digest, canonical_bytes, byte_length
            ) VALUES (%s, %s, %s)
            """,
            (
                bundle_content_digest,
                bundle_content,
                len(bundle_content),
            ),
        )
        bundle_digest = _publish_runtime_bundle(
            admin,
            tenant_id,
            [
                _runtime_component_identity(
                    role="REFERENCE_SOURCE",
                    logical_ref="runtime:tenant-beta-reference-source-v1",
                    canonicalization="EXACT_BYTES_V1",
                    placement="GLOBAL_IMMUTABLE_CONTENT",
                    content_digest=bundle_content_digest,
                    byte_length=len(bundle_content),
                )
            ],
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

    The production binder is covered separately with exact signed capabilities.
    These storage-focused tests avoid coupling every RLS/graph assertion to a
    signer fixture, so a target administrator installs the equivalent verified
    transaction context directly.
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
                capability_key_id, capability_key_lifecycle_head_id,
                capability_key_lifecycle_head_digest,
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
                %s, %s, %s,
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
                derive_ed25519_key_id(RFC8032_TEST_PUBLIC_KEY),
                uuid4(),
                SHA256_ZERO,
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
        "sha256:39e979fa296122cb66d42eae5e2d7c6dc797ac77ef4324515ae1ab6020088d83"
    )
    assert tenant_target.first_report.applied_versions == (1, 2)
    assert tenant_target.noop_report.applied_versions == ()
    assert tenant_target.noop_report.final_version == 2


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
    assert fingerprint.count("''rewrite-rule''") == 1
    assert "FROM pg_catalog.pg_rewrite AS rewrite_rule" in fingerprint
    assert "pg_get_ruledef(rewrite_rule.oid, false)" in fingerprint
    assert "rewrite_rule.ev_qual" not in fingerprint
    assert "rewrite_rule.ev_action" not in fingerprint
    assert fingerprint.count("relation_rule.ev_class = class.oid") == 2
    assert fingerprint.count("relation_trigger.tgrelid = class.oid") == 1
    assert fingerprint.count("relation_child.inhparent = class.oid") == 1
    assert fingerprint.count("relation_index.indrelid = class.oid") == 1
    for lazy_hint in (
        "class.relhasrules",
        "class.relhastriggers",
        "class.relhassubclass",
        "class.relhasindex",
    ):
        assert lazy_hint not in fingerprint
    assert "''ofarm'', ''ofarm_infrastructure'', ''public''" not in fingerprint
    assert "''ofarm_crypto''" in fingerprint
    assert fingerprint.count("''extension-dependency''") == 1
    assert "FROM pg_catalog.pg_depend AS dependency" in fingerprint
    assert "pg_catalog.pg_identify_object(" in fingerprint
    assert "dependency.classid::pg_catalog.regclass" in fingerprint
    assert "dependency.objsubid" in fingerprint
    assert "dependency.refobjsubid" in fingerprint
    assert "dependency.deptype = ''e''" not in fingerprint
    assert "extension.extname = ''ofarm_ed25519''" in fingerprint
    assert "OR identified.schema IN (" in fingerprint


def test_native_verifier_preflight_checks_complete_extension_dependency_set() -> None:
    source = (
        PACKAGE_ROOT / "deployment" / "postgresql" / "provisioning.py"
    ).read_text(encoding="utf-8")
    preflight = source.split("def _native_verifier_differences(", 1)[1].split(
        "\ndef _cluster_database_access_differences(", 1
    )[0]

    assert "dependency.objsubid," in preflight
    assert "dependency.refobjsubid," in preflight
    assert "dependency.deptype," in preflight
    assert "dependency.refclassid =" in preflight
    assert "'pg_catalog.pg_extension'::pg_catalog.regclass" in preflight
    assert "AND dependency.deptype = 'e'" not in preflight


def test_tenant_observer_requires_zero_prepared_transaction_capacity() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    marker = "-- PREPARED_TRANSACTION_STARTUP_POSTURE_V1"
    gate = (
        "pg_catalog.current_setting(\n"
        "                ''max_prepared_transactions''\n"
        "           )::pg_catalog.int4 <> 0"
    )

    assert source.count(marker) == 1
    assert source.count(gate) == 1
    assert source.count("FROM pg_catalog.pg_prepared_xacts") == 1
    assert "''prepared transaction capacity differs''" in source


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
            "SELECT * FROM ofarm.create_tenant_challenge()"
        ).fetchone()[0]
        assert isinstance(challenge_id, UUID)
        attacker.rollback()
    finally:
        victim.close()
        attacker.close()


def test_key_registration_refuses_null_candidate_evidence(
    tenant_target: TenantTarget,
) -> None:
    resource = (
        "projects/example/locations/europe-west1/keyRings/ofarm/"
        "cryptoKeys/null-refusal/cryptoKeyVersions/1"
    )
    attestation = _sha256_id(b"null-refusal-attestation")
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_capability_key_control_login")
    ) as controller:
        for arguments in (
            (None, resource, attestation),
            (RFC8032_TEST_PUBLIC_KEY, None, attestation),
            (RFC8032_TEST_PUBLIC_KEY, resource, None),
        ):
            with pytest.raises(psycopg.errors.InvalidParameterValue):
                with controller.transaction():
                    controller.execute(
                        """
                        SELECT *
                        FROM ofarm.register_tenant_capability_key(
                            %s, %s, %s
                        )
                        """,
                        arguments,
                    )


def test_candidate_preflight_refuses_unknown_wrong_or_malformed_input(
    tenant_target: TenantTarget,
) -> None:
    unknown_kid = derive_ed25519_key_id(bytes(range(32)))
    valid_signature = sign(
        RFC8032_TEST_SEED, TENANT_CAPABILITY_PREFLIGHT_PROBE
    )
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_capability_key_control_login")
    ) as controller:
        candidate = _register_capability_key_candidate(
            controller,
            seed=hashlib.sha256(b"ofarm-preflight-refusal").digest(),
            label="preflight-refusal",
        )
        wrong_signature = bytearray(
            sign(candidate.seed, TENANT_CAPABILITY_PREFLIGHT_PROBE)
        )
        wrong_signature[-1] ^= 1
        assert controller.execute(
            """
            SELECT ofarm.verify_tenant_capability_candidate_preflight(%s, %s)
            """,
            (candidate.kid, bytes(wrong_signature)),
        ).fetchone() == (False,)
        controller.commit()
        with pytest.raises(psycopg.errors.InvalidAuthorizationSpecification):
            controller.execute(
                """
                SELECT ofarm.verify_tenant_capability_candidate_preflight(
                    %s, %s
                )
                """,
                (unknown_kid, valid_signature),
            )
        controller.rollback()
        for arguments in ((None, valid_signature), (unknown_kid, None)):
            with pytest.raises(psycopg.errors.InvalidParameterValue):
                controller.execute(
                    """
                    SELECT ofarm.verify_tenant_capability_candidate_preflight(
                        %s, %s
                    )
                    """,
                    arguments,
                )
            controller.rollback()


def test_candidate_preflight_serializes_with_lifecycle_mutation_lock(
    tenant_target: TenantTarget,
) -> None:
    seed = hashlib.sha256(b"ofarm-preflight-lock-order").digest()
    probe_signature = sign(seed, TENANT_CAPABILITY_PREFLIGHT_PROBE)
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_capability_key_control_login")
    ) as controller:
        candidate = _register_capability_key_candidate(
            controller,
            seed=seed,
            label="preflight-lock-order",
        )

    preflight_pid: list[int] = []
    preflight_connected = threading.Event()

    def attempt_preflight() -> tuple[bool]:
        with psycopg.connect(
            tenant_target.role_dsn("ofarm_capability_key_control_login")
        ) as controller:
            preflight_pid.append(controller.info.backend_pid)
            preflight_connected.set()
            return controller.execute(
                """
                SELECT ofarm.verify_tenant_capability_candidate_preflight(
                    %s, %s
                )
                """,
                (candidate.kid, probe_signature),
            ).fetchone()

    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute(
            "SELECT pg_catalog.pg_advisory_xact_lock(%s, %s)",
            (1330004306, 1413694001),
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            preflight_future = executor.submit(attempt_preflight)
            try:
                assert preflight_connected.wait(timeout=5)
                waiting_for_exclusive_lock = False
                for _attempt in range(100):
                    waiting_for_exclusive_lock = admin.execute(
                        """
                        SELECT pg_catalog.count(*) = 1
                        FROM pg_catalog.pg_locks AS lock
                        WHERE lock.pid = %s
                          AND lock.locktype = 'advisory'
                          AND lock.classid = 1330004306
                          AND lock.objid = 1413694001
                          AND lock.mode = 'ExclusiveLock'
                          AND NOT lock.granted
                        """,
                        (preflight_pid[0],),
                    ).fetchone()[0]
                    if waiting_for_exclusive_lock:
                        break
                    threading.Event().wait(0.01)
                assert waiting_for_exclusive_lock
                assert not preflight_future.done()
            finally:
                admin.rollback()
            assert preflight_future.result(timeout=5) == (True,)


def test_key_controller_refuses_every_missing_lifecycle_evidence_field(
    tenant_target: TenantTarget,
    capability_key: CapabilityKeyAuthority,
) -> None:
    preflight = _sha256_id(b"null-lifecycle-preflight")
    kms = _sha256_id(b"null-lifecycle-kms")
    iam = _sha256_id(b"null-lifecycle-iam")
    incident_id = uuid4()
    close_receipt_id = uuid4()
    calls: list[tuple[str, tuple[object, ...]]] = []
    for missing in range(3):
        evidence: list[str | None] = [preflight, kms, iam]
        evidence[missing] = None
        calls.append(
            (
                """
                SELECT * FROM ofarm.activate_tenant_capability_key(
                    %s, %s, %s, %s, %s, %s, 'COMPROMISE_REPLACEMENT'
                )
                """,
                (
                    capability_key.kid,
                    capability_key.head_id,
                    capability_key.head_digest,
                    *evidence,
                ),
            )
        )
        calls.append(
            (
                """
                SELECT * FROM ofarm.rotate_tenant_capability_key(
                    %s, %s, %s, %s, %s, %s, %s, 'GRACEFUL_ROTATION'
                )
                """,
                (
                    capability_key.kid,
                    capability_key.kid,
                    capability_key.head_id,
                    capability_key.head_digest,
                    *evidence,
                ),
            )
        )
    for missing in range(2):
        evidence = [kms, iam]
        evidence[missing] = None
        calls.extend(
            (
                (
                    """
                    SELECT * FROM ofarm.close_tenant_capability_admission(
                        %s, %s, %s, %s, %s, 'COMPROMISE'
                    )
                    """,
                    (
                        capability_key.head_id,
                        capability_key.head_digest,
                        capability_key.kid,
                        *evidence,
                    ),
                ),
                (
                    """
                    SELECT * FROM ofarm.revoke_tenant_capability_key(
                        %s, %s, %s, %s, %s, %s, %s, 'COMPROMISE'
                    )
                    """,
                    (
                        capability_key.kid,
                        capability_key.head_id,
                        capability_key.head_digest,
                        incident_id,
                        close_receipt_id,
                        *evidence,
                    ),
                ),
                (
                    """
                    SELECT * FROM ofarm.resume_tenant_capability_admission(
                        %s, %s, %s, %s, %s, %s, 'COMPROMISE_RESOLVED'
                    )
                    """,
                    (
                        capability_key.head_id,
                        capability_key.head_digest,
                        incident_id,
                        close_receipt_id,
                        *evidence,
                    ),
                ),
            )
        )

    with psycopg.connect(
        tenant_target.role_dsn("ofarm_capability_key_control_login")
    ) as controller:
        for statement, parameters in calls:
            with pytest.raises(psycopg.errors.InvalidParameterValue):
                with controller.transaction():
                    controller.execute(statement, parameters)

        with pytest.raises(psycopg.errors.InvalidParameterValue) as refused:
            with controller.transaction():
                controller.execute(
                    """
                    SELECT * FROM ofarm.revoke_tenant_capability_key(
                        NULL, %s, %s, %s, %s, %s, %s, 'COMPROMISE'
                    )
                    """,
                    (
                        capability_key.head_id,
                        capability_key.head_digest,
                        incident_id,
                        close_receipt_id,
                        kms,
                        iam,
                    ),
                )
        assert refused.value.diag.message_primary == (
            "key revocation arguments differ"
        )


def test_capability_crypto_and_control_role_matrix_is_exact(
    tenant_target: TenantTarget,
) -> None:
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert admin.execute(
            """
            SELECT role_name,
                   pg_catalog.has_function_privilege(
                       role_name,
                       'ofarm_crypto.ed25519_verify(bytea,bytea,bytea)',
                       'EXECUTE'
                   ),
                   pg_catalog.has_function_privilege(
                       role_name,
                       'ofarm.verify_tenant_capability_preflight(bytea,bytea)',
                       'EXECUTE'
                   ),
                   pg_catalog.has_function_privilege(
                       role_name,
                       'ofarm.verify_tenant_capability_candidate_preflight(text,bytea)',
                       'EXECUTE'
                   )
            FROM pg_catalog.unnest(%s::pg_catalog.text[]) AS roles(role_name)
            ORDER BY role_name
            """,
            (
                [
                    "ofarm_admission_lock_owner",
                    "ofarm_binder",
                    "ofarm_capability_key_control_login",
                ],
            ),
        ).fetchall() == [
            ("ofarm_admission_lock_owner", False, True, True),
            ("ofarm_binder", True, True, False),
            ("ofarm_capability_key_control_login", False, False, True),
        ]
        assert admin.execute(
            """
            SELECT login_role, target_role,
                   pg_catalog.pg_has_role(login_role, target_role, 'SET'),
                   pg_catalog.has_function_privilege(
                       login_role,
                       'pg_catalog.pg_advisory_xact_lock(integer,integer)',
                       'EXECUTE'
                   ),
                   pg_catalog.has_function_privilege(
                       login_role,
                       'pg_catalog.pg_advisory_xact_lock_shared(integer,integer)',
                       'EXECUTE'
                   )
            FROM pg_catalog.unnest(%s::pg_catalog.text[]) AS logins(login_role)
            CROSS JOIN pg_catalog.unnest(%s::pg_catalog.text[])
                AS targets(target_role)
            ORDER BY login_role, target_role
            """,
            (
                list(TENANT_PROVISIONING_SPEC.login_role_names),
                ["ofarm_admission_lock_owner", "ofarm_binder"],
            ),
        ).fetchall() == [
            (login_role, target_role, False, False, False)
            for login_role in sorted(TENANT_PROVISIONING_SPEC.login_role_names)
            for target_role in (
                "ofarm_admission_lock_owner",
                "ofarm_binder",
            )
        ]


def test_production_binding_accepts_only_the_exact_signed_capability(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    capability_key: CapabilityKeyAuthority,
) -> None:
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        challenge_id, audience = application.execute(
            "SELECT * FROM ofarm.create_tenant_challenge()"
        ).fetchone()
        assert isinstance(challenge_id, UUID)
        now_us = application.execute(
            """
            SELECT (extract(epoch FROM pg_catalog.clock_timestamp()) *
                    1000000)::pg_catalog.int8
            """
        ).fetchone()[0]
        capability = _tenant_capability(
            authority=authority,
            key=capability_key,
            challenge_id=challenge_id,
            audience=audience,
            now_unix_microseconds=now_us,
        )
        token = sign_capability(capability)
        application.execute(
            "SELECT ofarm.bind_tenant_capability(%s)",
            (token,),
        )
        context = application.execute(
            "SELECT * FROM ofarm.current_tenant_context()"
        ).fetchone()
        assert context[0:3] == (
            OIDC_ISSUER_EQUALITY_POLICY,
            ISSUER,
            authority.subject,
        )
        assert context[7] == authority.tenant_id
        assert context[9] == authority.party_ref
        assert context[14] == capability_key.kid
        assert context[17] == capability.nonce
        assert application.execute(
            "SELECT ofarm.current_tenant_id()"
        ).fetchone() == (authority.tenant_id,)

    with psycopg.connect(tenant_target.role_dsn("ofarm_worker")) as worker:
        stale_challenge_id, _ = worker.execute(
            "SELECT * FROM ofarm.create_tenant_challenge()"
        ).fetchone()
        assert stale_challenge_id != challenge_id
        with pytest.raises(psycopg.errors.InvalidAuthorizationSpecification):
            worker.execute(
                "SELECT ofarm.bind_tenant_capability(%s)",
                (token,),
            )

    with psycopg.connect(tenant_target.role_dsn("ofarm_worker")) as worker:
        challenge_id, audience = worker.execute(
            "SELECT * FROM ofarm.create_tenant_challenge()"
        ).fetchone()
        now_us = worker.execute(
            """
            SELECT (extract(epoch FROM pg_catalog.clock_timestamp()) *
                    1000000)::pg_catalog.int8
            """
        ).fetchone()[0]
        token = sign_capability(
            _tenant_capability(
                authority=authority,
                key=capability_key,
                challenge_id=challenge_id,
                audience=audience,
                now_unix_microseconds=now_us,
            )
        )
        header, payload, signature = token.split(".")
        corrupt_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        with pytest.raises(psycopg.errors.InvalidAuthorizationSpecification):
            worker.execute(
                "SELECT ofarm.bind_tenant_capability(%s)",
                (f"{header}.{payload}.{corrupt_signature}",),
            )


def test_capability_revoke_cancellation_disconnect_and_anti_barging(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    capability_key: CapabilityKeyAuthority,
) -> None:
    kms = _sha256_id(b"close-lock-kms-evidence")
    iam = _sha256_id(b"close-lock-iam-evidence")
    original_ring: tuple[object, ...]
    close_result: tuple[object, ...] | None = None
    revoke_result: tuple[object, ...] | None = None
    successful_revoke = None

    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        original_ring = admin.execute(
            """
            SELECT audience, projected_head_sequence, projected_head_id,
                   projected_head_digest::pg_catalog.text,
                   projected_admission_state, projected_issuing_kid,
                   projected_issuing_candidate_digest::pg_catalog.text,
                   unresolved_incident_id, close_act_id, close_receipt_id,
                   rebuilt_at
            FROM ofarm.tenant_capability_keyring
            """
        ).fetchone()
    assert original_ring[2:5] == (
        capability_key.head_id,
        capability_key.head_digest,
        "OPEN",
    )
    application = psycopg.connect(tenant_target.role_dsn("ofarm_app"))
    executor = ThreadPoolExecutor(max_workers=2)

    def attempt_revoke(
        connected: threading.Event,
        backend_pid: list[int],
    ) -> tuple[str, object]:
        controller = psycopg.connect(
            tenant_target.role_dsn("ofarm_capability_key_control_login"),
            connect_timeout=5,
        )
        try:
            controller.execute("SET LOCAL statement_timeout = '10s'")
            controller.execute("SET LOCAL lock_timeout = '8s'")
            backend_pid.append(controller.info.backend_pid)
            connected.set()
            assert close_result is not None
            try:
                row = controller.execute(
                    """
                    SELECT * FROM ofarm.revoke_tenant_capability_key(
                        %s, %s, %s, %s, %s, %s, %s, 'COMPROMISE'
                    )
                    """,
                    (
                        capability_key.kid,
                        close_result[0],
                        close_result[1],
                        close_result[2],
                        close_result[3],
                        kms,
                        iam,
                    ),
                ).fetchone()
            except psycopg.Error as exc:
                return "error", exc.sqlstate or type(exc).__name__
            controller.commit()
            return "committed", row
        finally:
            controller.close()

    def assert_close_survives_without_revoke() -> None:
        assert close_result is not None
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            assert admin.execute(
                """
                SELECT pg_catalog.count(*)
                FROM ofarm.tenant_capability_key_lifecycle
                WHERE prior_act_id = %s AND act_kind = 'REVOKE'
                """,
                (close_result[0],),
            ).fetchone() == (0,)
            authority_state = admin.execute(
                """
                SELECT head_id, head_digest, admission_state,
                       unresolved_incident_id, close_act_id, close_receipt_id
                FROM ofarm.fold_tenant_capability_key_lifecycle(%s)
                """,
                (capability_key.kid,),
            ).fetchone()
            projection_state = admin.execute(
                """
                SELECT projected_head_id,
                       projected_head_digest::pg_catalog.text,
                       projected_admission_state, unresolved_incident_id,
                       close_act_id, close_receipt_id
                FROM ofarm.tenant_capability_keyring
                """
            ).fetchone()
        expected = (
            close_result[0],
            close_result[1],
            "CLOSED",
            close_result[2],
            close_result[0],
            close_result[3],
        )
        assert authority_state == expected
        assert projection_state == expected

    try:
        application.execute("SET LOCAL statement_timeout = '10s'")
        application.execute("SET LOCAL lock_timeout = '8s'")
        application_pid = application.info.backend_pid
        application.execute(
            "SELECT ofarm.bind_tenant_capability(%s)",
            (
                _signed_capability_for_new_challenge(
                    application,
                    authority=authority,
                    key=capability_key,
                ),
            ),
        )
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            _wait_for_admission_locks(
                admin,
                {(application_pid, "ShareLock", True)},
            )

        # CLOSE_ADMISSION is deliberately durable and lock-free.  It closes
        # admission without waiting for an already-bound transaction.
        with psycopg.connect(
            tenant_target.role_dsn("ofarm_capability_key_control_login")
        ) as controller:
            controller.execute("SET LOCAL statement_timeout = '5s'")
            close_result = controller.execute(
                """
                SELECT * FROM ofarm.close_tenant_capability_admission(
                    %s, %s, %s, %s, %s, 'COMPROMISE'
                )
                """,
                (
                    capability_key.head_id,
                    capability_key.head_digest,
                    capability_key.kid,
                    kms,
                    iam,
                ),
            ).fetchone()
            controller.commit()
        assert len(close_result) == 5
        assert application.execute(
            "SELECT ofarm.current_tenant_id()"
        ).fetchone() == (authority.tenant_id,)

        # A bind that begins after the close, but before any revocation waiter,
        # observes the durable close and refuses immediately.
        with psycopg.connect(
            tenant_target.role_dsn("ofarm_worker")
        ) as later_worker:
            later_worker.execute("SET LOCAL statement_timeout = '5s'")
            later_token = _signed_capability_for_new_challenge(
                later_worker,
                authority=authority,
                key=capability_key,
            )
            with pytest.raises(
                psycopg.errors.InvalidAuthorizationSpecification
            ):
                later_worker.execute(
                    "SELECT ofarm.bind_tenant_capability(%s)",
                    (later_token,),
                )

        # A canceled exclusive waiter never becomes lifecycle authority.
        cancel_connected = threading.Event()
        cancel_pid: list[int] = []
        cancel_future = executor.submit(
            attempt_revoke, cancel_connected, cancel_pid
        )
        assert cancel_connected.wait(timeout=5)
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            _wait_for_admission_locks(
                admin,
                {
                    (application_pid, "ShareLock", True),
                    (cancel_pid[0], "ExclusiveLock", False),
                },
            )
            assert admin.execute(
                "SELECT pg_catalog.pg_cancel_backend(%s)",
                (cancel_pid[0],),
            ).fetchone() == (True,)
        assert cancel_future.result(timeout=5) == ("error", "57014")
        assert_close_survives_without_revoke()

        # A killed controller is also only a failed attempt: its transaction
        # disappears and the committed close remains the exact head.
        terminate_connected = threading.Event()
        terminate_pid: list[int] = []
        terminate_future = executor.submit(
            attempt_revoke, terminate_connected, terminate_pid
        )
        assert terminate_connected.wait(timeout=5)
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            _wait_for_admission_locks(
                admin,
                {
                    (application_pid, "ShareLock", True),
                    (terminate_pid[0], "ExclusiveLock", False),
                },
            )
            assert admin.execute(
                "SELECT pg_catalog.pg_terminate_backend(%s)",
                (terminate_pid[0],),
            ).fetchone() == (True,)
        terminate_outcome = terminate_future.result(timeout=5)
        assert terminate_outcome[0] == "error"
        assert terminate_outcome[1] in {"57P01", "OperationalError"}
        assert_close_survives_without_revoke()

        # Once an exclusive revoke is queued, a later shared binder cannot
        # barge ahead of it and join the earlier bound application.
        revoke_connected = threading.Event()
        revoke_pid: list[int] = []
        successful_revoke = executor.submit(
            attempt_revoke, revoke_connected, revoke_pid
        )
        assert revoke_connected.wait(timeout=5)
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            _wait_for_admission_locks(
                admin,
                {
                    (application_pid, "ShareLock", True),
                    (revoke_pid[0], "ExclusiveLock", False),
                },
            )

        binder_connected = threading.Event()
        binder_pid: list[int] = []

        def attempt_later_bind() -> tuple[str, str | None]:
            worker = psycopg.connect(
                tenant_target.role_dsn("ofarm_worker"),
                connect_timeout=5,
            )
            try:
                worker.execute("SET LOCAL statement_timeout = '10s'")
                worker.execute("SET LOCAL lock_timeout = '8s'")
                token = _signed_capability_for_new_challenge(
                    worker,
                    authority=authority,
                    key=capability_key,
                )
                binder_pid.append(worker.info.backend_pid)
                binder_connected.set()
                try:
                    worker.execute(
                        "SELECT ofarm.bind_tenant_capability(%s)",
                        (token,),
                    )
                except psycopg.Error as exc:
                    return "error", exc.sqlstate or type(exc).__name__
                worker.commit()
                return "bound", None
            finally:
                worker.close()

        binder_future = executor.submit(attempt_later_bind)
        assert binder_connected.wait(timeout=5)
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            _wait_for_admission_locks(
                admin,
                {
                    (application_pid, "ShareLock", True),
                    (revoke_pid[0], "ExclusiveLock", False),
                    (binder_pid[0], "ShareLock", False),
                },
            )

        application.commit()
        revoke_outcome = successful_revoke.result(timeout=5)
        assert revoke_outcome[0] == "committed"
        assert isinstance(revoke_outcome[1], tuple)
        revoke_result = revoke_outcome[1]
        assert len(revoke_result) == 3
        assert binder_future.result(timeout=5) == ("error", "28000")

        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            assert admin.execute(
                """
                SELECT prior_act_id, act_kind, incident_id, close_receipt_id
                FROM ofarm.tenant_capability_key_lifecycle
                WHERE act_id = %s
                """,
                (revoke_result[0],),
            ).fetchone() == (
                close_result[0],
                "REVOKE",
                close_result[2],
                close_result[3],
            )
            assert admin.execute(
                """
                SELECT projected_head_id,
                       projected_head_digest::pg_catalog.text,
                       projected_admission_state, projected_issuing_kid
                FROM ofarm.tenant_capability_keyring
                """
            ).fetchone() == (
                revoke_result[0],
                revoke_result[1],
                "CLOSED",
                None,
            )
    finally:
        active_error = sys.exc_info()[1]
        cleanup_failures: list[BaseException] = []
        try:
            if not application.closed:
                application.rollback()
        except BaseException as exc:
            cleanup_failures.append(exc)
        finally:
            try:
                application.close()
            except BaseException as exc:
                cleanup_failures.append(exc)
        try:
            # Every submitted database call has a statement and lock timeout.
            # Releasing the application first lets any queued future finish.
            executor.shutdown(wait=True)
        except BaseException as exc:
            cleanup_failures.append(exc)

        close_rows: list[tuple[object, ...]] = []
        descendants: list[tuple[object, ...]] = []
        try:
            with psycopg.connect(tenant_target.target_admin_dsn) as admin:
                close_rows = admin.execute(
                    """
                    SELECT act_id
                    FROM ofarm.tenant_capability_key_lifecycle
                    WHERE prior_act_id = %s
                      AND prior_act_digest::pg_catalog.text = %s
                      AND act_kind = 'CLOSE_ADMISSION'
                      AND old_kid = %s
                      AND old_candidate_digest::pg_catalog.text = %s
                      AND kms_evidence_digest::pg_catalog.text = %s
                      AND iam_evidence_digest::pg_catalog.text = %s
                      AND reason = 'COMPROMISE'
                    """,
                    (
                        original_ring[2],
                        original_ring[3],
                        capability_key.kid,
                        capability_key.candidate_digest,
                        kms,
                        iam,
                    ),
                ).fetchall()
                if close_rows:
                    descendants = admin.execute(
                        """
                        WITH RECURSIVE owned AS (
                            SELECT lifecycle.*
                            FROM ofarm.tenant_capability_key_lifecycle
                                AS lifecycle
                            WHERE lifecycle.act_id = ANY(
                                %s::pg_catalog.uuid[]
                            )
                            UNION ALL
                            SELECT child.*
                            FROM ofarm.tenant_capability_key_lifecycle AS child
                            JOIN owned AS parent
                              ON child.prior_act_id = parent.act_id
                        )
                        SELECT stream_sequence, act_id,
                               act_digest::pg_catalog.text, prior_act_id,
                               prior_act_digest::pg_catalog.text, act_kind,
                               old_kid,
                               old_candidate_digest::pg_catalog.text,
                               incident_id, close_receipt_id,
                               kms_evidence_digest::pg_catalog.text,
                               iam_evidence_digest::pg_catalog.text, reason
                        FROM owned
                        ORDER BY stream_sequence
                        """,
                        ([row[0] for row in close_rows],),
                    ).fetchall()
                    projected = admin.execute(
                        """
                        SELECT projected_head_sequence, projected_head_id,
                               projected_head_digest::pg_catalog.text,
                               projected_admission_state
                        FROM ofarm.tenant_capability_keyring
                        WHERE audience = %s
                        """,
                        (original_ring[0],),
                    ).fetchone()
                    try:
                        assert len(close_rows) == 1
                        assert 1 <= len(descendants) <= 2
                        assert descendants[0][3:13] == (
                            original_ring[2],
                            original_ring[3],
                            "CLOSE_ADMISSION",
                            capability_key.kid,
                            capability_key.candidate_digest,
                            descendants[0][8],
                            descendants[0][9],
                            kms,
                            iam,
                            "COMPROMISE",
                        )
                        if close_result is not None:
                            assert descendants[0][1:3] == close_result[0:2]
                            assert descendants[0][8:10] == close_result[2:4]
                        if len(descendants) == 2:
                            assert descendants[1][3:13] == (
                                descendants[0][1],
                                descendants[0][2],
                                "REVOKE",
                                capability_key.kid,
                                capability_key.candidate_digest,
                                descendants[0][8],
                                descendants[0][9],
                                kms,
                                iam,
                                "COMPROMISE",
                            )
                            if revoke_result is not None:
                                assert descendants[1][1:3] == revoke_result[0:2]
                        assert projected == (
                            descendants[-1][0],
                            descendants[-1][1],
                            descendants[-1][2],
                            "CLOSED",
                        )
                    except AssertionError as exc:
                        cleanup_failures.append(exc)
        except BaseException as exc:
            cleanup_failures.append(exc)

        restored_count: int | None = None
        removed_count: int | None = None
        try:
            with psycopg.connect(tenant_target.target_admin_dsn) as admin:
                exact_roots = admin.execute(
                    """
                    SELECT act_id
                    FROM ofarm.tenant_capability_key_lifecycle
                    WHERE prior_act_id = %s
                      AND prior_act_digest::pg_catalog.text = %s
                      AND act_kind = 'CLOSE_ADMISSION'
                      AND old_kid = %s
                      AND old_candidate_digest::pg_catalog.text = %s
                      AND kms_evidence_digest::pg_catalog.text = %s
                      AND iam_evidence_digest::pg_catalog.text = %s
                      AND reason = 'COMPROMISE'
                    """,
                    (
                        original_ring[2],
                        original_ring[3],
                        capability_key.kid,
                        capability_key.candidate_digest,
                        kms,
                        iam,
                    ),
                ).fetchall()
                if exact_roots:
                    admin.execute(
                        "SET LOCAL session_replication_role = 'replica'"
                    )
                    restored = admin.execute(
                        """
                        UPDATE ofarm.tenant_capability_keyring
                        SET projected_head_sequence = %s,
                            projected_head_id = %s,
                            projected_head_digest = %s,
                            projected_admission_state = %s,
                            projected_issuing_kid = %s,
                            projected_issuing_candidate_digest = %s,
                            unresolved_incident_id = %s,
                            close_act_id = %s,
                            close_receipt_id = %s,
                            rebuilt_at = %s
                        WHERE audience = %s
                        """,
                        (
                            original_ring[1],
                            original_ring[2],
                            original_ring[3],
                            original_ring[4],
                            original_ring[5],
                            original_ring[6],
                            original_ring[7],
                            original_ring[8],
                            original_ring[9],
                            original_ring[10],
                            original_ring[0],
                        ),
                    )
                    removed = admin.execute(
                        """
                        WITH RECURSIVE owned AS (
                            SELECT lifecycle.act_id
                            FROM ofarm.tenant_capability_key_lifecycle
                                AS lifecycle
                            WHERE lifecycle.act_id = ANY(
                                %s::pg_catalog.uuid[]
                            )
                            UNION ALL
                            SELECT child.act_id
                            FROM ofarm.tenant_capability_key_lifecycle AS child
                            JOIN owned AS parent
                              ON child.prior_act_id = parent.act_id
                        )
                        DELETE FROM ofarm.tenant_capability_key_lifecycle
                        WHERE act_id IN (SELECT act_id FROM owned)
                        """,
                        ([row[0] for row in exact_roots],),
                    )
                    restored_count = restored.rowcount
                    removed_count = removed.rowcount
            if exact_roots:
                assert restored_count == 1
                if descendants:
                    assert removed_count == len(descendants)
                else:
                    assert removed_count is not None and removed_count >= 1
        except BaseException as exc:
            cleanup_failures.append(exc)

        try:
            with psycopg.connect(tenant_target.target_admin_dsn) as admin:
                restored_ring = admin.execute(
                    """
                    SELECT audience, projected_head_sequence,
                           projected_head_id,
                           projected_head_digest::pg_catalog.text,
                           projected_admission_state, projected_issuing_kid,
                           projected_issuing_candidate_digest::pg_catalog.text,
                           unresolved_incident_id, close_act_id,
                           close_receipt_id, rebuilt_at
                    FROM ofarm.tenant_capability_keyring
                    """
                ).fetchone()
                remaining = admin.execute(
                    """
                    SELECT pg_catalog.count(*)
                    FROM ofarm.tenant_capability_key_lifecycle
                    WHERE prior_act_id = %s
                      AND prior_act_digest::pg_catalog.text = %s
                      AND act_kind = 'CLOSE_ADMISSION'
                      AND old_kid = %s
                      AND old_candidate_digest::pg_catalog.text = %s
                      AND kms_evidence_digest::pg_catalog.text = %s
                      AND iam_evidence_digest::pg_catalog.text = %s
                      AND reason = 'COMPROMISE'
                    """,
                    (
                        original_ring[2],
                        original_ring[3],
                        capability_key.kid,
                        capability_key.candidate_digest,
                        kms,
                        iam,
                    ),
                ).fetchone()
            assert restored_ring == original_ring
            assert remaining == (0,)
        except BaseException as exc:
            cleanup_failures.append(exc)

        if cleanup_failures:
            details = "; ".join(
                f"{type(exc).__name__}: {exc}" for exc in cleanup_failures
            )
            if active_error is not None:
                active_error.add_note(f"cleanup failures: {details}")
            else:
                failure = cleanup_failures[0]
                for extra in cleanup_failures[1:]:
                    failure.add_note(
                        f"additional cleanup failure: "
                        f"{type(extra).__name__}: {extra}"
                    )
                raise failure


def test_principal_revoke_anti_barging_after_savepoint_retry(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    capability_key: CapabilityKeyAuthority,
) -> None:
    subject = "subject-principal-savepoint-race"
    activation_reason = "savepoint-race-activation"
    revoke_reason = "savepoint-race-revoke"

    with psycopg.connect(
        tenant_target.role_dsn("ofarm_identity_control_login")
    ) as identity:
        initial = _initial_transition_values(
            identity,
            authority,
            subject=subject,
            reason=activation_reason,
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
            party_ref=authority.party_ref,
            party_schema_digest=authority.party_schema_digest,
            party_payload_digest=authority.party_payload_digest,
            valid_from=initial["valid_from"],
            valid_until=initial["valid_until"],
            predecessor_version_id=None,
            effective_at=initial["effective_at"],
            decided_at=initial["decided_at"],
            reason=activation_reason,
        )

    principal_authority = replace(
        authority,
        subject=subject,
        binding_version_id=initial["binding_version_id"],
        binding_version_digest=initial["binding_digest"],
        lifecycle_head_id=initial["act_id"],
        lifecycle_head_digest=initial["act_digest"],
    )

    revoke_act_id = uuid4()
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_identity_control_login")
    ) as identity:
        revoke_effective_at, revoke_decided_at = identity.execute(
            """
            SELECT
                pg_catalog.date_trunc(
                    'microseconds',
                    pg_catalog.clock_timestamp() - INTERVAL '2 seconds'
                ),
                pg_catalog.date_trunc(
                    'microseconds',
                    pg_catalog.clock_timestamp() - INTERVAL '1 second'
                )
            """
        ).fetchone()
        revoke_act_digest = _compute_act_digest(
            identity,
            subject=subject,
            stream_sequence=2,
            act_id=revoke_act_id,
            act_kind="REVOKE",
            binding_version_id=principal_authority.binding_version_id,
            binding_version_digest=principal_authority.binding_version_digest,
            prior_act_id=principal_authority.lifecycle_head_id,
            prior_act_digest=principal_authority.lifecycle_head_digest,
            successor_version_id=None,
            successor_version_digest=None,
            effective_at=revoke_effective_at,
            decided_at=revoke_decided_at,
            reason=revoke_reason,
        )

    holder = psycopg.connect(tenant_target.role_dsn("ofarm_app"))
    retrying = psycopg.connect(tenant_target.role_dsn("ofarm_worker"))
    executor = ThreadPoolExecutor(max_workers=2)
    transition_future = None
    retry_future = None
    try:
        holder.execute("SET LOCAL statement_timeout = '10s'")
        holder.execute("SET LOCAL lock_timeout = '8s'")
        holder.execute(
            "SELECT ofarm.bind_tenant_capability(%s)",
            (
                _signed_capability_for_new_challenge(
                    holder,
                    authority=principal_authority,
                    key=capability_key,
                ),
            ),
        )
        holder_pid = holder.info.backend_pid

        retrying.execute("SET LOCAL statement_timeout = '10s'")
        retrying.execute("SET LOCAL lock_timeout = '8s'")
        retry_challenge, retry_audience = retrying.execute(
            "SELECT * FROM ofarm.create_tenant_challenge()"
        ).fetchone()
        retry_now_us = retrying.execute(
            """
            SELECT (extract(epoch FROM pg_catalog.clock_timestamp()) *
                    1000000)::pg_catalog.int8
            """
        ).fetchone()[0]
        retry_capability = _tenant_capability(
            authority=principal_authority,
            key=capability_key,
            challenge_id=retry_challenge,
            audience=retry_audience,
            now_unix_microseconds=retry_now_us,
        )
        valid_retry_token = sign_capability(retry_capability)
        invalid_retry_token = sign_capability(
            replace(retry_capability, lifecycle_head_digest=bytes(32))
        )
        retry_pid = retrying.info.backend_pid

        # This correctly signed token fails only after the shared admission
        # lock is taken and principal authority is folded.  Rolling back its
        # savepoint must release that shared lock while preserving CHALLENGE.
        with pytest.raises(
            psycopg.errors.InvalidAuthorizationSpecification
        ):
            with retrying.transaction():
                retrying.execute(
                    "SELECT ofarm.bind_tenant_capability(%s)",
                    (invalid_retry_token,),
                )
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            assert _admission_locks(admin, retry_pid) == set()

        # A successful bind performed inside a savepoint is also completely
        # undone by rollback: BOUND disappears, CHALLENGE returns, and its
        # transaction-level shared lock is gone.
        with pytest.raises(RuntimeError, match="rollback bound savepoint"):
            with retrying.transaction():
                retrying.execute(
                    "SELECT ofarm.bind_tenant_capability(%s)",
                    (valid_retry_token,),
                )
                assert retrying.execute(
                    "SELECT ofarm.current_tenant_id()"
                ).fetchone() == (authority.tenant_id,)
                with psycopg.connect(
                    tenant_target.target_admin_dsn
                ) as admin:
                    _wait_for_admission_locks(
                        admin,
                        {(retry_pid, "ShareLock", True)},
                    )
                raise RuntimeError("rollback bound savepoint")
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            assert _admission_locks(admin, retry_pid) == set()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with retrying.transaction():
                retrying.execute("SELECT ofarm.current_tenant_id()")
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            with retrying.transaction():
                retrying.execute(
                    "SELECT * FROM ofarm.create_tenant_challenge()"
                )

        transition_connected = threading.Event()
        transition_pid: list[int] = []

        def commit_principal_revoke() -> UUID:
            identity = psycopg.connect(
                tenant_target.role_dsn("ofarm_identity_control_login"),
                connect_timeout=5,
            )
            try:
                identity.execute("SET LOCAL statement_timeout = '10s'")
                identity.execute("SET LOCAL lock_timeout = '8s'")
                transition_pid.append(identity.info.backend_pid)
                transition_connected.set()
                _transition(
                    identity,
                    subject=subject,
                    expected_head_id=principal_authority.lifecycle_head_id,
                    expected_head_digest=(
                        principal_authority.lifecycle_head_digest
                    ),
                    act_id=revoke_act_id,
                    act_digest=revoke_act_digest,
                    act_kind="REVOKE",
                    binding_version_id=(
                        principal_authority.binding_version_id
                    ),
                    binding_version_digest=(
                        principal_authority.binding_version_digest
                    ),
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
                    effective_at=revoke_effective_at,
                    decided_at=revoke_decided_at,
                    reason=revoke_reason,
                )
                identity.commit()
                return revoke_act_id
            finally:
                identity.close()

        transition_future = executor.submit(commit_principal_revoke)
        assert transition_connected.wait(timeout=5)
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            _wait_for_admission_locks(
                admin,
                {
                    (holder_pid, "ShareLock", True),
                    (transition_pid[0], "ExclusiveLock", False),
                },
            )

        retry_started = threading.Event()

        def retry_after_exclusive_waiter() -> tuple[str, str | None]:
            retry_started.set()
            try:
                with retrying.transaction():
                    retrying.execute(
                        "SELECT ofarm.bind_tenant_capability(%s)",
                        (valid_retry_token,),
                    )
            except psycopg.Error as exc:
                return "error", exc.sqlstate or type(exc).__name__
            return "bound", None

        retry_future = executor.submit(retry_after_exclusive_waiter)
        assert retry_started.wait(timeout=5)
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            _wait_for_admission_locks(
                admin,
                {
                    (holder_pid, "ShareLock", True),
                    (transition_pid[0], "ExclusiveLock", False),
                    (retry_pid, "ShareLock", False),
                },
            )

        holder.commit()
        assert transition_future.result(timeout=5) == revoke_act_id
        assert retry_future.result(timeout=5) == ("error", "28000")

        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            assert admin.execute(
                """
                SELECT current_state, binding_version_id,
                       lifecycle_head_id, lifecycle_head_digest
                FROM ofarm.principal_binding_current
                WHERE equality_policy = %s AND issuer = %s AND subject = %s
                """,
                (OIDC_ISSUER_EQUALITY_POLICY, ISSUER, subject),
            ).fetchone() == (
                "INACTIVE",
                None,
                revoke_act_id,
                revoke_act_digest,
            )
    finally:
        active_error = sys.exc_info()[1]
        cleanup_failures: list[BaseException] = []
        try:
            if not holder.closed:
                holder.rollback()
        except BaseException as exc:
            cleanup_failures.append(exc)
        finally:
            try:
                holder.close()
            except BaseException as exc:
                cleanup_failures.append(exc)
        try:
            # Closing the holder releases the shared lock.  Both submitted
            # statements are timeout-bounded, so joining cannot retain it.
            executor.shutdown(wait=True)
        except BaseException as exc:
            cleanup_failures.append(exc)
        try:
            if not retrying.closed:
                retrying.rollback()
        except BaseException as exc:
            cleanup_failures.append(exc)
        finally:
            try:
                retrying.close()
            except BaseException as exc:
                cleanup_failures.append(exc)
        if cleanup_failures:
            details = "; ".join(
                f"{type(exc).__name__}: {exc}" for exc in cleanup_failures
            )
            if active_error is not None:
                active_error.add_note(f"cleanup failures: {details}")
            else:
                failure = cleanup_failures[0]
                for extra in cleanup_failures[1:]:
                    failure.add_note(
                        f"additional cleanup failure: "
                        f"{type(extra).__name__}: {extra}"
                    )
                raise failure


def test_keyring_projection_tamper_refuses_then_rebuilds_exactly(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    capability_key: CapabilityKeyAuthority,
) -> None:
    def assert_bind_refuses() -> None:
        with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
            challenge_id, audience = application.execute(
                "SELECT * FROM ofarm.create_tenant_challenge()"
            ).fetchone()
            now_us = application.execute(
                """
                SELECT (extract(epoch FROM pg_catalog.clock_timestamp()) *
                        1000000)::pg_catalog.int8
                """
            ).fetchone()[0]
            token = sign_capability(
                _tenant_capability(
                    authority=authority,
                    key=capability_key,
                    challenge_id=challenge_id,
                    audience=audience,
                    now_unix_microseconds=now_us,
                )
            )
            with pytest.raises(psycopg.Error):
                application.execute(
                    "SELECT ofarm.bind_tenant_capability(%s)", (token,)
                )

    def assert_projection_matches_authority() -> None:
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            projection = admin.execute(
                """
                SELECT projected_head_sequence, projected_head_id,
                       projected_head_digest::pg_catalog.text,
                       projected_admission_state, projected_issuing_kid,
                       projected_issuing_candidate_digest::pg_catalog.text,
                       unresolved_incident_id, close_act_id, close_receipt_id
                FROM ofarm.tenant_capability_keyring
                WHERE audience = (
                    SELECT audience FROM ofarm.tenant_binder_instance
                    WHERE singleton
                )
                """
            ).fetchone()
            authority_row = admin.execute(
                """
                SELECT head_sequence, head_id, head_digest, admission_state,
                       issuing_kid, issuing_candidate_digest,
                       unresolved_incident_id, close_act_id, close_receipt_id
                FROM ofarm.fold_tenant_capability_key_lifecycle(NULL)
                """
            ).fetchone()
        assert projection == authority_row

    controller_dsn = tenant_target.role_dsn(
        "ofarm_capability_key_control_login"
    )
    try:
        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            admin.execute(
                """
                UPDATE ofarm.tenant_capability_keyring
                SET audience = 'https://extra.invalid/ofarm'
                """
            )
        assert_bind_refuses()
        with psycopg.connect(controller_dsn) as controller:
            with pytest.raises(psycopg.Error):
                _register_capability_key_candidate(
                    controller,
                    seed=hashlib.sha256(b"projection-missing-key").digest(),
                    label="projection-missing",
                )
            controller.rollback()
            assert controller.execute(
                "SELECT * FROM ofarm.rebuild_tenant_capability_keyring()"
            ).fetchone() == (1, 1)
        assert_projection_matches_authority()

        with psycopg.connect(tenant_target.target_admin_dsn) as admin:
            admin.execute(
                """
                UPDATE ofarm.tenant_capability_keyring
                SET projected_admission_state = 'CLOSED'
                """
            )
        assert_bind_refuses()
        with psycopg.connect(controller_dsn) as controller:
            with pytest.raises(psycopg.Error):
                _register_capability_key_candidate(
                    controller,
                    seed=hashlib.sha256(b"projection-corrupt-key").digest(),
                    label="projection-corrupt",
                )
            controller.rollback()
            assert controller.execute(
                "SELECT * FROM ofarm.rebuild_tenant_capability_keyring()"
            ).fetchone() == (0, 1)
        assert_projection_matches_authority()
    finally:
        with psycopg.connect(controller_dsn) as controller:
            controller.execute(
                "SELECT * FROM ofarm.rebuild_tenant_capability_keyring()"
            )


def test_capability_key_lifecycle_handoff_and_compromise_are_fail_closed(
    tenant_target: TenantTarget,
    capability_key: CapabilityKeyAuthority,
) -> None:
    controller_dsn = tenant_target.role_dsn(
        "ofarm_capability_key_control_login"
    )
    kms = _sha256_id(b"lifecycle-kms-evidence")
    iam = _sha256_id(b"lifecycle-iam-evidence")

    def committed(
        controller: psycopg.Connection,
        statement: str,
        parameters: tuple[object, ...],
    ) -> tuple[object, ...]:
        row = controller.execute(statement, parameters).fetchone()
        controller.commit()
        return row

    def refused(
        controller: psycopg.Connection,
        statement: str,
        parameters: tuple[object, ...],
    ) -> None:
        with pytest.raises(psycopg.Error):
            controller.execute(statement, parameters)
        controller.rollback()

    with psycopg.connect(controller_dsn) as controller:
        candidates = []
        for suffix in ("b", "c", "d"):
            candidate = _register_capability_key_candidate(
                controller,
                seed=hashlib.sha256(
                    f"ofarm-lifecycle-{suffix}".encode("ascii")
                ).digest(),
                label=f"lifecycle-{suffix}",
            )
            controller.commit()
            candidates.append(candidate)
        key_b, key_c, key_d = candidates

        refused(
            controller,
            """
            SELECT * FROM ofarm.close_tenant_capability_admission(
                %s, %s, %s, %s, %s, 'ROTATION_HANDOFF'
            )
            """,
            (
                capability_key.head_id,
                capability_key.head_digest,
                capability_key.kid,
                kms,
                iam,
            ),
        )
        rotate_ab = committed(
            controller,
            """
            SELECT * FROM ofarm.rotate_tenant_capability_key(
                %s, %s, %s, %s, %s, %s, %s, 'GRACEFUL_ROTATION'
            )
            """,
            (
                capability_key.kid,
                key_b.kid,
                capability_key.head_id,
                capability_key.head_digest,
                key_b.preflight_receipt_digest,
                kms,
                iam,
            ),
        )
        refused(
            controller,
            """
            SELECT * FROM ofarm.rotate_tenant_capability_key(
                %s, %s, %s, %s, %s, %s, %s, 'GRACEFUL_ROTATION'
            )
            """,
            (
                key_b.kid,
                key_c.kid,
                rotate_ab[0],
                rotate_ab[1],
                key_c.preflight_receipt_digest,
                kms,
                iam,
            ),
        )
        assert controller.execute(
            """
            SELECT head_id, head_kind, admission_state
            FROM ofarm.observe_tenant_capability_key(%s)
            """,
            (key_b.kid,),
        ).fetchone() == (rotate_ab[0], "ROTATE", "OPEN")
        controller.commit()

        close_a = committed(
            controller,
            """
            SELECT * FROM ofarm.close_tenant_capability_admission(
                %s, %s, %s, %s, %s, 'COMPROMISE'
            )
            """,
            (rotate_ab[0], rotate_ab[1], capability_key.kid, kms, iam),
        )
        revoke_a = committed(
            controller,
            """
            SELECT * FROM ofarm.revoke_tenant_capability_key(
                %s, %s, %s, %s, %s, %s, %s, 'COMPROMISE'
            )
            """,
            (
                capability_key.kid,
                close_a[0],
                close_a[1],
                close_a[2],
                close_a[3],
                kms,
                iam,
            ),
        )
        resume_b = committed(
            controller,
            """
            SELECT * FROM ofarm.resume_tenant_capability_admission(
                %s, %s, %s, %s, %s, %s, 'COMPROMISE_RESOLVED'
            )
            """,
            (
                revoke_a[0],
                revoke_a[1],
                close_a[2],
                close_a[3],
                kms,
                iam,
            ),
        )
        rotate_bc = committed(
            controller,
            """
            SELECT * FROM ofarm.rotate_tenant_capability_key(
                %s, %s, %s, %s, %s, %s, %s, 'GRACEFUL_ROTATION'
            )
            """,
            (
                key_b.kid,
                key_c.kid,
                resume_b[0],
                resume_b[1],
                key_c.preflight_receipt_digest,
                kms,
                iam,
            ),
        )
        close_c = committed(
            controller,
            """
            SELECT * FROM ofarm.close_tenant_capability_admission(
                %s, %s, %s, %s, %s, 'COMPROMISE'
            )
            """,
            (rotate_bc[0], rotate_bc[1], key_c.kid, kms, iam),
        )
        refused(
            controller,
            """
            SELECT * FROM ofarm.resume_tenant_capability_admission(
                %s, %s, %s, %s, %s, %s, 'COMPROMISE_RESOLVED'
            )
            """,
            (close_c[0], close_c[1], close_c[2], close_c[3], kms, iam),
        )
        revoke_c = committed(
            controller,
            """
            SELECT * FROM ofarm.revoke_tenant_capability_key(
                %s, %s, %s, %s, %s, %s, %s, 'COMPROMISE'
            )
            """,
            (
                key_c.kid,
                close_c[0],
                close_c[1],
                close_c[2],
                close_c[3],
                kms,
                iam,
            ),
        )
        activate_d = committed(
            controller,
            """
            SELECT * FROM ofarm.activate_tenant_capability_key(
                %s, %s, %s, %s, %s, %s, 'COMPROMISE_REPLACEMENT'
            )
            """,
            (
                key_d.kid,
                revoke_c[0],
                revoke_c[1],
                key_d.preflight_receipt_digest,
                kms,
                iam,
            ),
        )
        refused(
            controller,
            """
            SELECT * FROM ofarm.resume_tenant_capability_admission(
                %s, %s, %s, %s, %s, %s, 'COMPROMISE_RESOLVED'
            )
            """,
            (
                activate_d[0],
                activate_d[1],
                close_c[2],
                close_c[3],
                kms,
                iam,
            ),
        )
        assert controller.execute(
            """
            SELECT head_id, head_kind, admission_state, issuing_kid,
                   close_target_kid, close_target_revoked
            FROM ofarm.observe_tenant_capability_key(%s)
            """,
            (key_d.kid,),
        ).fetchone() == (
            activate_d[0],
            "ACTIVATE",
            "CLOSED",
            key_d.kid,
            key_c.kid,
            True,
        )


def test_live_postgresql_and_python_share_exact_contract_vectors(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    capability_key: CapabilityKeyAuthority,
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

        audience = admin.execute(
            """
            SELECT audience
            FROM ofarm.tenant_binder_instance
            WHERE singleton
            """
        ).fetchone()[0]
        time_cases = TENANT_CAPABILITY_CONTRACT.manifest_without_digest()[
            "sharedVectors"
        ]["time"]
        for case in time_cases:
            database_result = admin.execute(
                """
                SELECT ofarm.valid_tenant_capability_time_window(
                    %s, %s, %s, %s, %s
                )
                """,
                (
                    case["issuedAt"],
                    case["notBefore"],
                    case["expiresAt"],
                    case["now"],
                    case["challengeCreatedAt"],
                ),
            ).fetchone()[0]
            capability = replace(
                _tenant_capability(
                    authority=authority,
                    key=capability_key,
                    challenge_id=uuid4(),
                    audience=audience,
                    now_unix_microseconds=case["issuedAt"],
                ),
                issued_at_unix_microseconds=case["issuedAt"],
                not_before_unix_microseconds=case["notBefore"],
                expires_at_unix_microseconds=case["expiresAt"],
            )
            try:
                validate_tenant_capability(
                    capability,
                    now_unix_microseconds=case["now"],
                    challenge_created_at_unix_microseconds=case[
                        "challengeCreatedAt"
                    ],
                )
                python_result = True
            except TenantCapabilityContractError:
                python_result = False
            expected = case["result"] == "accept"
            assert database_result is expected, case["id"]
            assert python_result is expected, case["id"]


def test_runtime_component_logical_ref_has_exact_ascii_octet_bound(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    content = b"runtime-component-logical-ref-boundary"
    content_digest = _sha256_id(content)
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
            bundle_digest = _publish_runtime_bundle(
                admin,
                authority.tenant_id,
                [
                    _runtime_component_identity(
                        role="REFERENCE_SOURCE",
                        logical_ref=maximum_ref,
                        canonicalization="EXACT_BYTES_V1",
                        placement="GLOBAL_IMMUTABLE_CONTENT",
                        content_digest=content_digest,
                        byte_length=len(content),
                    )
                ],
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
                    bundle_digest,
                    maximum_ref,
                ),
            ).fetchone() == (1024,)

            for invalid_ref in (
                RUNTIME_LOGICAL_REF_MAX + "a",
                RUNTIME_LOGICAL_REF_PREFIX + "ž",
            ):
                with pytest.raises(psycopg.errors.CheckViolation):
                    with admin.transaction():
                        _publish_runtime_bundle(
                            admin,
                            authority.tenant_id,
                            [
                                _runtime_component_identity(
                                    role="REFERENCE_SOURCE",
                                    logical_ref=invalid_ref,
                                    canonicalization="EXACT_BYTES_V1",
                                    placement="GLOBAL_IMMUTABLE_CONTENT",
                                    content_digest=content_digest,
                                    byte_length=len(content),
                                )
                            ],
                        )
        finally:
            admin.rollback()


@pytest.mark.parametrize("role_name", ("ofarm_app", "ofarm_worker"))
def test_runtime_roles_cannot_bypass_atomic_bundle_publication(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    role_name: str,
) -> None:
    arbitrary_bytes = b'{"bundle":"caller-selected-bytes"}'
    arbitrary_digest = _sha256_id(arbitrary_bytes)
    with psycopg.connect(tenant_target.role_dsn(role_name)) as runtime:
        _install_test_bound_context(runtime, authority)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with runtime.transaction():
                _publish_runtime_bundle(
                    runtime,
                    authority.tenant_id,
                    [
                        _runtime_component_identity(
                            role="REFERENCE_SOURCE",
                            logical_ref="runtime:unauthorized-publication",
                            canonicalization="EXACT_BYTES_V1",
                            placement="GLOBAL_IMMUTABLE_CONTENT",
                            content_digest=_sha256_id(b"unauthorized-content"),
                            byte_length=len(b"unauthorized-content"),
                        )
                    ],
                )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with runtime.transaction():
                runtime.execute(
                    """
                    INSERT INTO ofarm.runtime_bundle (
                        tenant_id, bundle_digest, bundle_ref,
                        canonical_bytes, byte_length
                    ) VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        authority.tenant_id,
                        arbitrary_digest,
                        "runtimebundle:" + arbitrary_digest,
                        arbitrary_bytes,
                        len(arbitrary_bytes),
                    ),
                )

        component = runtime.execute(
            """
            SELECT canonicalization, content_placement,
                   global_content_digest, tenant_content_digest, byte_length
            FROM ofarm.runtime_bundle_component
            WHERE tenant_id = %s AND bundle_digest = %s
            """,
            (authority.tenant_id, authority.runtime_bundle_digest),
        ).fetchone()
        assert component is not None
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with runtime.transaction():
                runtime.execute(
                    """
                    INSERT INTO ofarm.runtime_bundle_component (
                        tenant_id, bundle_digest, component_role, logical_ref,
                        canonicalization, content_placement,
                        global_content_digest, tenant_content_digest, byte_length
                    ) VALUES (%s, %s, 'REFERENCE_SOURCE', %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        authority.tenant_id,
                        authority.runtime_bundle_digest,
                        "runtime:post-seal-append",
                        *component,
                    ),
                )


def test_runtime_bundle_publication_is_exact_and_idempotent(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        _install_test_bound_context(application, authority)
        components = [
            {
                "role": row[0],
                "logicalRef": row[1],
                "canonicalization": row[2],
                "placement": row[3],
                "contentDigest": row[4],
                "byteLength": row[5],
            }
            for row in application.execute(
                """
                SELECT component_role, logical_ref, canonicalization,
                       content_placement,
                       COALESCE(global_content_digest, tenant_content_digest),
                       byte_length
                FROM ofarm.runtime_bundle_component
                WHERE tenant_id = %s AND bundle_digest = %s
                ORDER BY component_role COLLATE "C", logical_ref COLLATE "C"
                """,
                (authority.tenant_id, authority.runtime_bundle_digest),
            ).fetchall()
        ]
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_runtime_bundle_control_login")
    ) as publisher:
        assert _publish_runtime_bundle(
            publisher, authority.tenant_id, components
        ) == authority.runtime_bundle_digest

        with pytest.raises(psycopg.errors.InvalidParameterValue):
            with publisher.transaction():
                _publish_runtime_bundle(publisher, authority.tenant_id, [])
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            with publisher.transaction():
                _publish_runtime_bundle(
                    publisher,
                    authority.tenant_id,
                    components + components,
                )

        for null_field in ("schemaVersion", "canonicalization"):
            null_identity_document = {
                "schemaVersion": "ofarm.runtime-bundle.local.v1",
                "canonicalization": "OFARM_CANONICAL_JSON_V1",
                "components": components,
            }
            null_identity_document[null_field] = None
            with pytest.raises(psycopg.errors.InvalidParameterValue):
                with publisher.transaction():
                    publisher.execute(
                        "SELECT ofarm.publish_runtime_bundle(%s, %s, %s)",
                        (
                            authority.tenant_id,
                            authority.runtime_bundle_digest,
                            Jsonb(null_identity_document),
                        ),
                    )

        digest_mismatch_components = [
            {
                **components[0],
                "logicalRef": "runtime:digest-mismatch",
            }
        ]
        digest_mismatch_document = {
            "schemaVersion": "ofarm.runtime-bundle.local.v1",
            "canonicalization": "OFARM_CANONICAL_JSON_V1",
            "components": digest_mismatch_components,
        }
        digest_mismatch_candidate = _sha256_id(
            _canonical_json(digest_mismatch_document)
        )
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            with publisher.transaction():
                publisher.execute(
                    "SELECT ofarm.publish_runtime_bundle(%s, %s, %s)",
                    (
                        authority.tenant_id,
                        SHA256_ZERO,
                        Jsonb(digest_mismatch_document),
                    ),
                )

        unsorted_document = {
            "schemaVersion": "ofarm.runtime-bundle.local.v1",
            "canonicalization": "OFARM_CANONICAL_JSON_V1",
            "components": [
                {
                    **components[0],
                    "logicalRef": "runtime:unsorted-z",
                },
                {
                    **components[0],
                    "role": "ACTIVE_MANIFEST",
                    "logicalRef": "runtime:unsorted-a",
                },
            ],
        }
        unsorted_candidate = _sha256_id(_canonical_json(unsorted_document))
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            with publisher.transaction():
                publisher.execute(
                    "SELECT ofarm.publish_runtime_bundle(%s, %s, %s)",
                    (
                        authority.tenant_id,
                        unsorted_candidate,
                        Jsonb(unsorted_document),
                    ),
                )

    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        _install_test_bound_context(application, authority)
        assert application.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm.runtime_bundle_component
            WHERE tenant_id = %s AND bundle_digest = %s
            """,
            (authority.tenant_id, authority.runtime_bundle_digest),
        ).fetchone() == (len(components),)

    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm.runtime_bundle
            WHERE tenant_id = %s AND bundle_digest = ANY (%s::text[])
            """,
            (
                authority.tenant_id,
                [digest_mismatch_candidate, unsorted_candidate],
            ),
        ).fetchone() == (0,)


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
                application.execute(
                    "SELECT * FROM ofarm.create_tenant_challenge()"
                )

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
            "SELECT * FROM ofarm.create_tenant_challenge()"
        ).fetchone()[0]
        challenge_pid = challenge_peer.execute(
            "SELECT pg_catalog.pg_backend_pid()"
        ).fetchone()[0]
        challenge_peer.commit()

        observer_peer.execute("SELECT * FROM ofarm.create_tenant_challenge()")
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
        purger_peer.execute("SELECT * FROM ofarm.create_tenant_challenge()")
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


@pytest.mark.parametrize("act_kind", ("ACTIVATE", "SUPERSEDE"))
def test_nil_principal_lifecycle_act_refuses_before_transition(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    act_kind: str,
) -> None:
    subject = f"subject-nil-{act_kind.lower()}"
    nil_act_id = UUID(int=0)
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_identity_control_login")
    ) as identity:
        values = _initial_transition_values(
            identity,
            authority,
            subject=subject,
            reason="nil-lifecycle-act",
        )
        nil_act_digest = _compute_act_digest(
            identity,
            subject=subject,
            stream_sequence=1,
            act_id=nil_act_id,
            act_kind=act_kind,
            binding_version_id=values["binding_version_id"],
            binding_version_digest=values["binding_digest"],
            prior_act_id=None,
            prior_act_digest=None,
            successor_version_id=(
                values["binding_version_id"] if act_kind == "SUPERSEDE" else None
            ),
            successor_version_digest=(
                values["binding_digest"] if act_kind == "SUPERSEDE" else None
            ),
            effective_at=values["effective_at"],
            decided_at=values["decided_at"],
            reason="nil-lifecycle-act",
        )
        with pytest.raises(
            psycopg.errors.InvalidParameterValue,
            match="lifecycle act id is nil",
        ):
            with identity.transaction():
                _transition(
                    identity,
                    subject=subject,
                    expected_head_id=None,
                    expected_head_digest=None,
                    act_id=nil_act_id,
                    act_digest=nil_act_digest,
                    act_kind=act_kind,
                    binding_version_id=values["binding_version_id"],
                    binding_version_digest=values["binding_digest"],
                    candidate_version_id=values["binding_version_id"],
                    candidate_version_digest=values["binding_digest"],
                    tenant_id=authority.tenant_id,
                    tenant_registration_digest=(
                        authority.tenant_registration_digest
                    ),
                    party_ref=authority.party_ref,
                    party_schema_digest=authority.party_schema_digest,
                    party_payload_digest=authority.party_payload_digest,
                    valid_from=values["valid_from"],
                    valid_until=values["valid_until"],
                    predecessor_version_id=None,
                    effective_at=values["effective_at"],
                    decided_at=values["decided_at"],
                    reason="nil-lifecycle-act",
                )

    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert admin.execute(
            "SELECT count(*) FROM ofarm.principal_binding WHERE subject = %s",
            (subject,),
        ).fetchone() == (0,)


@pytest.mark.parametrize(
    ("table_name", "column_name", "constraint_name"),
    (
        (
            "principal_binding_lifecycle",
            "act_id",
            "principal_binding_lifecycle_act_id_check",
        ),
        (
            "principal_binding_current",
            "lifecycle_head_id",
            "principal_binding_current_head_id_check",
        ),
    ),
)
def test_nil_principal_lifecycle_ids_are_schema_invalid(
    tenant_target: TenantTarget,
    table_name: str,
    column_name: str,
    constraint_name: str,
) -> None:
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        row = admin.execute(
            """
            SELECT governed_constraint.convalidated,
                   pg_catalog.pg_get_constraintdef(governed_constraint.oid)
            FROM pg_catalog.pg_constraint AS governed_constraint
            JOIN pg_catalog.pg_class AS governed_table
              ON governed_table.oid = governed_constraint.conrelid
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = governed_table.relnamespace
            WHERE namespace.nspname = 'ofarm'
              AND governed_table.relname = %s
              AND governed_constraint.conname = %s
            """,
            (table_name, constraint_name),
        ).fetchone()
    assert row is not None and row[0] is True
    assert column_name in row[1]
    assert "00000000-0000-0000-0000-000000000000" in row[1]


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
    runtime_bundle_digest: str | None = None,
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
            (
                authority.runtime_bundle_digest
                if runtime_bundle_digest is None
                else runtime_bundle_digest
            ),
        ),
    )


def _insert_test_materialization(
    connection: psycopg.Connection,
    authority: TenantAuthority,
    *,
    batch_id: str,
    materialization_id: str,
    materialization_key: Mapping[str, object],
    basis_record_id: str,
    snapshot_record_id: str,
    context_snapshot_ref: str,
    current_state: Mapping[str, object],
    expected_live_materialization_id: str | None = None,
) -> str:
    key_digest = connection.execute(
        "SELECT ofarm.compute_materialization_key_digest(%s)",
        (Jsonb(materialization_key),),
    ).fetchone()[0]
    connection.execute(
        """
        SELECT ofarm.publish_materialization_generation(
            %s, %s, %s, 'OPERATIONAL_DASHBOARD', %s,
            %s, %s, %s, %s, %s
        )
        """,
        (
            expected_live_materialization_id,
            materialization_id,
            Jsonb(materialization_key),
            Jsonb(current_state),
            basis_record_id,
            snapshot_record_id,
            context_snapshot_ref,
            Jsonb({"basis": [basis_record_id]}),
            batch_id,
        ),
    )
    return key_digest


def _publish_test_materialization_generation(
    connection: psycopg.Connection,
    authority: TenantAuthority,
    *,
    id_prefix: str,
    generation_suffix: str,
    materialization_key: Mapping[str, object],
    expected_live_materialization_id: str | None = None,
) -> str:
    batch_id = f"batch-{id_prefix}-{generation_suffix}"
    materialization_id = f"{id_prefix}-{generation_suffix}"
    record_ids = tuple(
        f"{id_prefix}-{kind}-{generation_suffix}"
        for kind in ("basis", "snapshot", "context")
    )
    _insert_batch(connection, authority, batch_id)
    for record_id in record_ids:
        _insert_record(
            connection,
            authority,
            batch_id=batch_id,
            record_id=record_id,
            record_kind="ofarm.derivedtest.v0.1",
            payload={"recordId": record_id},
        )
    _insert_test_materialization(
        connection,
        authority,
        batch_id=batch_id,
        materialization_id=materialization_id,
        materialization_key=materialization_key,
        basis_record_id=record_ids[0],
        snapshot_record_id=record_ids[1],
        context_snapshot_ref=record_ids[2],
        current_state={"generation": generation_suffix},
        expected_live_materialization_id=expected_live_materialization_id,
    )
    return materialization_id


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

    batch_a = "batch-hostile-edge-a"
    batch_b = "batch-hostile-edge-b"
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        _install_test_bound_context(application, authority)
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

    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
            _install_test_bound_context(application, authority)
            _insert_batch(application, authority, batch_a)
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


def test_one_tenant_transaction_cannot_create_two_governed_batches(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    with pytest.raises(psycopg.errors.UniqueViolation) as raised:
        with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
            _install_test_bound_context(application, authority)
            _insert_batch(application, authority, "batch-one-transaction-a")
            _insert_batch(application, authority, "batch-one-transaction-b")

    assert raised.value.diag.constraint_name == (
        "governed_write_batch_transaction_key"
    )


@pytest.mark.parametrize("runtime_role", ("ofarm_app", "ofarm_worker"))
def test_governed_batch_principal_must_match_verified_binding(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    runtime_role: str,
) -> None:
    batch_id = "batch-forged-principal-" + runtime_role.removeprefix("ofarm_")
    with psycopg.connect(tenant_target.role_dsn(runtime_role)) as runtime:
        _install_test_bound_context(runtime, authority)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with runtime.transaction():
                runtime.execute(
                    """
                    INSERT INTO ofarm.governed_write_batch (
                        tenant_id, batch_id, authenticated_principal_ref,
                        governed_operation, request_id, runtime_bundle_digest
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        authority.tenant_id,
                        batch_id,
                        "forged-principal",
                        "TENANT_TEST_WRITE",
                        "request-" + batch_id,
                        authority.runtime_bundle_digest,
                    ),
                )

    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        assert admin.execute(
            """
            SELECT count(*)
            FROM ofarm.governed_write_batch
            WHERE tenant_id = %s AND batch_id = %s
            """,
            (authority.tenant_id, batch_id),
        ).fetchone() == (0,)


def test_gate_log_request_must_belong_to_its_governed_batch(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    batch_id = "batch-gate-command-binding"
    with pytest.raises(psycopg.errors.ForeignKeyViolation) as raised:
        with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
            _install_test_bound_context(application, authority)
            _insert_batch(application, authority, batch_id)
            application.execute(
                """
                INSERT INTO ofarm.kernel_gate_log (
                    tenant_id, batch_id, request_id, gate, outcome
                ) VALUES (%s, %s, %s, 'TEST_GATE', 'REFUSED')
                """,
                (
                    authority.tenant_id,
                    batch_id,
                    "request-not-owned-by-batch",
                ),
            )
            application.execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert raised.value.diag.constraint_name == "kernel_gate_log_command_fkey"


@pytest.mark.parametrize(
    ("case_name", "principal_ref", "governed_operation"),
    (
        ("principal", "wrong-principal", "TENANT_TEST_WRITE"),
        ("operation", None, "WRONG_OPERATION"),
    ),
)
def test_idempotency_identity_must_match_its_governed_batch(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    case_name: str,
    principal_ref: str | None,
    governed_operation: str,
) -> None:
    batch_id = "batch-idempotency-command-" + case_name
    result_record_id = "result-idempotency-command-" + case_name
    with pytest.raises(psycopg.errors.ForeignKeyViolation) as raised:
        with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
            _install_test_bound_context(application, authority)
            _insert_batch(application, authority, batch_id)
            _insert_record(
                application,
                authority,
                batch_id=batch_id,
                record_id=result_record_id,
                record_kind="ofarm.commandresult.v0.1",
                payload={"case": case_name},
            )
            application.execute(
                """
                INSERT INTO ofarm.kernel_idempotency (
                    tenant_id, authenticated_principal_ref,
                    governed_operation, caller_key, request_digest,
                    request_id, batch_id, result_record_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    authority.tenant_id,
                    (
                        authority.party_ref
                        if principal_ref is None
                        else principal_ref
                    ),
                    governed_operation,
                    "caller-key-" + case_name,
                    _sha256_id(("request-" + case_name).encode("ascii")),
                    "request-" + batch_id,
                    batch_id,
                    result_record_id,
                ),
            )
            application.execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert raised.value.diag.constraint_name == "kernel_idempotency_command_fkey"


def test_record_runtime_bundle_must_match_its_governed_batch(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    other_bundle_content = b"record-provenance-hostile-reference-source"
    other_content_digest = _sha256_id(other_bundle_content)
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute(
            """
            INSERT INTO ofarm.runtime_content_blob (
                content_digest, canonical_bytes, byte_length
            ) VALUES (%s, %s, %s)
            """,
            (
                other_content_digest,
                other_bundle_content,
                len(other_bundle_content),
            ),
        )
        other_bundle_digest = _publish_runtime_bundle(
            admin,
            authority.tenant_id,
            [
                _runtime_component_identity(
                    role="REFERENCE_SOURCE",
                    logical_ref="runtime:record-provenance-hostile-v1",
                    canonicalization="EXACT_BYTES_V1",
                    placement="GLOBAL_IMMUTABLE_CONTENT",
                    content_digest=other_content_digest,
                    byte_length=len(other_bundle_content),
                )
            ],
        )

    with pytest.raises(psycopg.errors.ForeignKeyViolation) as raised:
        with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
            _install_test_bound_context(application, authority)
            batch_id = "batch-record-bundle-binding"
            _insert_batch(application, authority, batch_id)
            _insert_record(
                application,
                authority,
                batch_id=batch_id,
                record_id="record-wrong-runtime-bundle",
                record_kind="ofarm.provenancetest.v0.1",
                payload={"hostile": True},
                runtime_bundle_digest=other_bundle_digest,
            )
            application.execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert raised.value.diag.constraint_name == (
        "kernel_record_batch_provenance_fkey"
    )


def test_component_length_must_match_the_selected_content_blob(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
) -> None:
    global_bytes = b"global-runtime-length-authority"
    global_digest = _sha256_id(global_bytes)
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute(
            """
            INSERT INTO ofarm.runtime_content_blob (
                content_digest, canonical_bytes, byte_length
            ) VALUES (%s, %s, %s)
            """,
            (global_digest, global_bytes, len(global_bytes)),
        )

    with pytest.raises(psycopg.errors.ForeignKeyViolation) as raised:
        with psycopg.connect(
            tenant_target.role_dsn("ofarm_runtime_bundle_control_login")
        ) as publisher:
            _publish_runtime_bundle(
                publisher,
                authority.tenant_id,
                [
                    _runtime_component_identity(
                        role="REFERENCE_SOURCE",
                        logical_ref="test:global-length-mismatch",
                        canonicalization="EXACT_BYTES_V1",
                        placement="GLOBAL_IMMUTABLE_CONTENT",
                        content_digest=global_digest,
                        byte_length=len(global_bytes) + 1,
                    )
                ],
            )
    assert raised.value.diag.constraint_name == (
        "runtime_bundle_component_global_fkey"
    )

    tenant_bytes = b"tenant-runtime-length-authority"
    tenant_digest = _sha256_id(tenant_bytes)
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        _install_test_bound_context(application, authority)
        application.execute(
            """
            INSERT INTO ofarm.runtime_tenant_content_blob (
                tenant_id, content_digest, canonical_bytes, byte_length
            ) VALUES (%s, %s, %s, %s)
            """,
            (
                authority.tenant_id,
                tenant_digest,
                tenant_bytes,
                len(tenant_bytes),
            ),
        )
    with pytest.raises(psycopg.errors.ForeignKeyViolation) as raised:
        with psycopg.connect(
            tenant_target.role_dsn("ofarm_runtime_bundle_control_login")
        ) as publisher:
            _publish_runtime_bundle(
                publisher,
                authority.tenant_id,
                [
                    _runtime_component_identity(
                        role="REFERENCE_SOURCE",
                        logical_ref="test:tenant-length-mismatch",
                        canonicalization="EXACT_BYTES_V1",
                        placement="TENANT_RUNTIME_SELECTION",
                        content_digest=tenant_digest,
                        byte_length=len(tenant_bytes) + 1,
                    )
                ],
            )
    assert raised.value.diag.constraint_name == (
        "runtime_bundle_component_tenant_fkey"
    )


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
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        _install_test_bound_context(application, authority)
        _insert_batch(application, authority, batch_id)
        for record_id in (basis_id, snapshot_id, context_id):
            _insert_record(
                application,
                authority,
                batch_id=batch_id,
                record_id=record_id,
                record_kind="ofarm.derivedtest.v0.1",
                payload={"recordId": record_id},
            )
        key_digest = _insert_test_materialization(
            application,
            authority,
            batch_id=batch_id,
            materialization_id=materialization_id,
            materialization_key=materialization_key,
            basis_record_id=basis_id,
            snapshot_record_id=snapshot_id,
            context_snapshot_ref=context_id,
            current_state={"status": "ready"},
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
                    'derived_dependency_index_materialization_fkey',
                    'derived_materialization_key_digest_check',
                    'derived_materialization_superseded_fkey'
                  )
                """
            ).fetchall()
        )
        index_definitions = dict(
            admin.execute(
                """
                SELECT index.relname,
                       pg_catalog.pg_get_indexdef(index.oid)
                FROM pg_catalog.pg_class AS index
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = index.relnamespace
                WHERE namespace.nspname = 'ofarm'
                  AND index.relname = 'derived_materialization_live_key_key'
                """
            ).fetchall()
        )
    assert (
        "materialization_key"
        in (definitions["derived_dependency_index_materialization_fkey"])
    )
    assert all(
        field in definitions["derived_materialization_superseded_fkey"]
        for field in (
            "superseded_by",
            "key_digest",
            "materialization_key",
            "DEFERRABLE INITIALLY DEFERRED",
        )
    )
    assert "compute_materialization_key_digest" in (
        definitions["derived_materialization_key_digest_check"]
    )
    live_key_index = index_definitions["derived_materialization_live_key_key"]
    assert "UNIQUE INDEX" in live_key_index
    assert "key_digest" in live_key_index
    assert "materialization_key" in live_key_index
    assert "WHERE (superseded_by IS NULL)" in live_key_index


@pytest.mark.parametrize("role_name", ("ofarm_app", "ofarm_worker"))
def test_materialization_generations_preserve_provenance_and_monotone_freshness(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    role_name: str,
) -> None:
    role_suffix = role_name.removeprefix("ofarm_")
    batch_a = f"batch-materialization-provenance-{role_suffix}-a"
    batch_b = f"batch-materialization-provenance-{role_suffix}-b"
    generation_a_id = f"materialization-provenance-{role_suffix}-a"
    generation_b_id = f"materialization-provenance-{role_suffix}-b"
    unrelated_generation_id = (
        f"materialization-provenance-{role_suffix}-unrelated"
    )
    materialization_key = {
        "anchorScopeRef": f"farm-provenance-{role_suffix}",
        "targetTwin": f"twin-provenance-{role_suffix}",
        "timePolicy": {"policyType": "NOW"},
    }
    records_a = tuple(
        f"materialization-provenance-{role_suffix}-{kind}-a"
        for kind in ("basis", "snapshot", "context")
    )
    records_b = tuple(
        f"materialization-provenance-{role_suffix}-{kind}-b"
        for kind in ("basis", "snapshot", "context")
    )

    with psycopg.connect(tenant_target.role_dsn(role_name)) as application:
        _install_test_bound_context(application, authority)
        _insert_batch(application, authority, batch_a)
        for record_id in records_a:
            _insert_record(
                application,
                authority,
                batch_id=batch_a,
                record_id=record_id,
                record_kind="ofarm.derivedtest.v0.1",
                payload={"recordId": record_id},
            )
        key_digest = _insert_test_materialization(
            application,
            authority,
            batch_id=batch_a,
            materialization_id=generation_a_id,
            materialization_key=materialization_key,
            basis_record_id=records_a[0],
            snapshot_record_id=records_a[1],
            context_snapshot_ref=records_a[2],
            current_state={"generation": "a"},
        )
        original_generation = application.execute(
            """
            SELECT
                current_state, basis_record_id, snapshot_record_id,
                context_snapshot_ref, freshness_vector, batch_id,
                batch_full_xid::pg_catalog.text, generated_at
            FROM ofarm.derived_materialization
            WHERE tenant_id = %s AND materialization_id = %s
            """,
            (authority.tenant_id, generation_a_id),
        ).fetchone()

    with psycopg.connect(tenant_target.role_dsn(role_name)) as application:
        _install_test_bound_context(application, authority)
        assert application.execute(
            """
            SELECT pg_catalog.has_table_privilege(
                current_user,
                'ofarm.derived_materialization',
                'UPDATE'
            )
            """
        ).fetchone() == (False,)
        update_columns = {
            column_name
            for column_name, permitted in application.execute(
                """
                SELECT attribute.attname,
                       pg_catalog.has_column_privilege(
                           current_user,
                           'ofarm.derived_materialization',
                           attribute.attname,
                           'UPDATE'
                       )
                FROM pg_catalog.pg_attribute AS attribute
                JOIN pg_catalog.pg_class AS class
                  ON class.oid = attribute.attrelid
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = class.relnamespace
                WHERE namespace.nspname = 'ofarm'
                  AND class.relname = 'derived_materialization'
                  AND attribute.attnum > 0
                  AND NOT attribute.attisdropped
                ORDER BY attribute.attnum
                """
            ).fetchall()
            if permitted
        }
        assert update_columns == {"freshness"}

        _insert_batch(application, authority, batch_b)
        for record_id in records_b:
            _insert_record(
                application,
                authority,
                batch_id=batch_b,
                record_id=record_id,
                record_kind="ofarm.derivedtest.v0.1",
                payload={"recordId": record_id},
            )
        _insert_test_materialization(
            application,
            authority,
            batch_id=batch_b,
            materialization_id=unrelated_generation_id,
            materialization_key={
                **materialization_key,
                "targetTwin": f"twin-provenance-{role_suffix}-unrelated",
            },
            basis_record_id=records_b[0],
            snapshot_record_id=records_b[1],
            context_snapshot_ref=records_b[2],
            current_state={"generation": "unrelated"},
        )

        application.execute(
            """
            UPDATE ofarm.derived_materialization
            SET freshness = 'STALE'
            WHERE tenant_id = %s AND materialization_id = %s
            """,
            (authority.tenant_id, unrelated_generation_id),
        )
        application.execute(
            """
            UPDATE ofarm.derived_materialization
            SET freshness = 'INVALID'
            WHERE tenant_id = %s AND materialization_id = %s
            """,
            (authority.tenant_id, unrelated_generation_id),
        )
        for forbidden_freshness in ("STALE", "FRESH"):
            with pytest.raises(
                psycopg.errors.CheckViolation,
                match="freshness may only degrade",
            ):
                with application.transaction():
                    application.execute(
                        """
                        UPDATE ofarm.derived_materialization
                        SET freshness = %s
                        WHERE tenant_id = %s AND materialization_id = %s
                        """,
                        (
                            forbidden_freshness,
                            authority.tenant_id,
                            unrelated_generation_id,
                        ),
                    )
        assert application.execute(
            """
            SELECT freshness
            FROM ofarm.derived_materialization
            WHERE tenant_id = %s AND materialization_id = %s
            """,
            (authority.tenant_id, unrelated_generation_id),
        ).fetchone() == ("INVALID",)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with application.transaction():
                application.execute(
                    """
                    UPDATE ofarm.derived_materialization
                    SET superseded_by = %s
                    WHERE tenant_id = %s AND materialization_id = %s
                    """,
                    (
                        unrelated_generation_id,
                        authority.tenant_id,
                        generation_a_id,
                    ),
                )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with application.transaction():
                application.execute(
                    """
                    UPDATE ofarm.derived_materialization
                    SET current_state = %s,
                        generated_at = TIMESTAMPTZ '2000-01-01 00:00:00+00',
                        batch_id = %s,
                        batch_full_xid = pg_catalog.pg_current_xact_id()
                    WHERE tenant_id = %s AND materialization_id = %s
                    """,
                    (
                        Jsonb({"generation": "forged"}),
                        batch_b,
                        authority.tenant_id,
                        generation_a_id,
                    ),
                )

        _insert_test_materialization(
            application,
            authority,
            batch_id=batch_b,
            materialization_id=generation_b_id,
            materialization_key=materialization_key,
            basis_record_id=records_b[0],
            snapshot_record_id=records_b[1],
            context_snapshot_ref=records_b[2],
            current_state={"generation": "b"},
            expected_live_materialization_id=generation_a_id,
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with application.transaction():
                application.execute(
                    """
                    UPDATE ofarm.derived_materialization
                    SET superseded_by = NULL
                    WHERE tenant_id = %s AND materialization_id = %s
                    """,
                    (authority.tenant_id, generation_a_id),
                )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with application.transaction():
                application.execute(
                    """
                    DELETE FROM ofarm.derived_materialization
                    WHERE tenant_id = %s AND materialization_id = %s
                    """,
                    (authority.tenant_id, generation_a_id),
                )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
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
                        %s, %s, %s, %s, %s, %s, %s,
                        'OPERATIONAL_DASHBOARD', 'FRESH', %s,
                        %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        authority.tenant_id,
                        f"materialization-provenance-{role_suffix}-direct",
                        key_digest,
                        Jsonb(materialization_key),
                        materialization_key["targetTwin"],
                        materialization_key["anchorScopeRef"],
                        Jsonb(materialization_key["timePolicy"]),
                        Jsonb({"generation": "direct"}),
                        records_b[0],
                        records_b[1],
                        records_b[2],
                        Jsonb({"basis": [records_b[0]]}),
                        batch_b,
                    ),
                )

        with pytest.raises(psycopg.errors.InvalidParameterValue):
            with application.transaction():
                _insert_test_materialization(
                    application,
                    authority,
                    batch_id=batch_b,
                    materialization_id=generation_b_id,
                    materialization_key=materialization_key,
                    basis_record_id=records_b[0],
                    snapshot_record_id=records_b[1],
                    context_snapshot_ref=records_b[2],
                    current_state={"generation": "self"},
                    expected_live_materialization_id=generation_b_id,
                )

        with pytest.raises(psycopg.errors.SerializationFailure):
            with application.transaction():
                _insert_test_materialization(
                    application,
                    authority,
                    batch_id=batch_b,
                    materialization_id=(
                        f"materialization-provenance-{role_suffix}-rewire"
                    ),
                    materialization_key=materialization_key,
                    basis_record_id=records_b[0],
                    snapshot_record_id=records_b[1],
                    context_snapshot_ref=records_b[2],
                    current_state={"generation": "rewire"},
                    expected_live_materialization_id=generation_a_id,
                )

        with pytest.raises(psycopg.errors.UniqueViolation) as cycle:
            with application.transaction():
                _insert_test_materialization(
                    application,
                    authority,
                    batch_id=batch_b,
                    materialization_id=generation_a_id,
                    materialization_key=materialization_key,
                    basis_record_id=records_b[0],
                    snapshot_record_id=records_b[1],
                    context_snapshot_ref=records_b[2],
                    current_state={"generation": "cycle"},
                    expected_live_materialization_id=generation_b_id,
                )
        assert cycle.value.diag.constraint_name == (
            "derived_materialization_pkey"
        )

        observed_generation_a = application.execute(
            """
            SELECT
                current_state, basis_record_id, snapshot_record_id,
                context_snapshot_ref, freshness_vector, batch_id,
                batch_full_xid::pg_catalog.text, generated_at,
                freshness, superseded_by
            FROM ofarm.derived_materialization
            WHERE tenant_id = %s AND materialization_id = %s
            """,
            (authority.tenant_id, generation_a_id),
        ).fetchone()
        observed_generation_b = application.execute(
            """
            SELECT
                batch_id, batch_full_xid::pg_catalog.text,
                freshness, superseded_by, current_state
            FROM ofarm.derived_materialization
            WHERE tenant_id = %s AND materialization_id = %s
            """,
            (authority.tenant_id, generation_b_id),
        ).fetchone()
        live_generations = application.execute(
            """
            SELECT materialization_id
            FROM ofarm.derived_materialization
            WHERE tenant_id = %s
              AND key_digest = %s
              AND materialization_key = %s
              AND superseded_by IS NULL
            """,
            (authority.tenant_id, key_digest, Jsonb(materialization_key)),
        ).fetchall()

    assert observed_generation_a[:-2] == original_generation
    assert observed_generation_a[-2:] == ("STALE", generation_b_id)
    assert observed_generation_b[0] == batch_b
    assert observed_generation_b[1] != original_generation[6]
    assert observed_generation_b[2:] == (
        "FRESH",
        None,
        {"generation": "b"},
    )
    assert live_generations == [(generation_b_id,)]


@pytest.mark.parametrize("role_name", ("ofarm_app", "ofarm_worker"))
@pytest.mark.parametrize(
    ("starting_freshness", "superseded_freshness"),
    (
        ("FRESH", "STALE"),
        ("STALE", "STALE"),
        ("INVALID", "INVALID"),
    ),
)
def test_materialization_publication_preserves_superseded_freshness(
    tenant_target: TenantTarget,
    authority: TenantAuthority,
    role_name: str,
    starting_freshness: str,
    superseded_freshness: str,
) -> None:
    case_suffix = (
        f"{role_name.removeprefix('ofarm_')}-{starting_freshness.lower()}"
    )
    materialization_key = {
        "anchorScopeRef": f"farm-publication-{case_suffix}",
        "targetTwin": f"twin-publication-{case_suffix}",
        "timePolicy": {"policyType": "NOW"},
    }
    id_prefix = f"materialization-publication-{case_suffix}"

    with psycopg.connect(tenant_target.role_dsn(role_name)) as runtime:
        _install_test_bound_context(runtime, authority)
        generation_a_id = _publish_test_materialization_generation(
            runtime,
            authority,
            id_prefix=id_prefix,
            generation_suffix="a",
            materialization_key=materialization_key,
        )
        if starting_freshness != "FRESH":
            runtime.execute(
                """
                UPDATE ofarm.derived_materialization
                SET freshness = %s
                WHERE tenant_id = %s AND materialization_id = %s
                """,
                (starting_freshness, authority.tenant_id, generation_a_id),
            )

    with psycopg.connect(tenant_target.role_dsn(role_name)) as runtime:
        _install_test_bound_context(runtime, authority)
        generation_b_id = _publish_test_materialization_generation(
            runtime,
            authority,
            id_prefix=id_prefix,
            generation_suffix="b",
            materialization_key=materialization_key,
            expected_live_materialization_id=generation_a_id,
        )
        observed_generations = runtime.execute(
            """
            SELECT materialization_id, freshness, superseded_by
            FROM ofarm.derived_materialization
            WHERE tenant_id = %s
              AND materialization_id IN (%s, %s)
            ORDER BY materialization_id
            """,
            (authority.tenant_id, generation_a_id, generation_b_id),
        ).fetchall()

    assert observed_generations == [
        (generation_a_id, superseded_freshness, generation_b_id),
        (generation_b_id, "FRESH", None),
    ]


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
        CREATE OR REPLACE FUNCTION ofarm.valid_ascii_id(
            value pg_catalog.text DEFAULT ''::pg_catalog.text
        )
        RETURNS pg_catalog.bool
        LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS 'SELECT pg_catalog.octet_length(value) BETWEEN 1 AND 255
                   AND value OPERATOR(pg_catalog.~) ''^[A-Za-z0-9._:-]+$'''
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
        """
        GRANT UPDATE (current_state)
        ON ofarm.derived_materialization TO ofarm_app
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
                "sha256:897001ea090224da95746e9de94a6f0098c8a2eae01abab68ac1f32b6509e950"
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


@pytest.mark.parametrize(
    ("tamper_statement", "cleanup_statement", "runner_error"),
    (
        (
            "CREATE COLLATION ofarm_crypto.rogue "
            "(provider = builtin, locale = 'C')",
            "DROP COLLATION ofarm_crypto.rogue",
            "native-verifier schema object inventory differs",
        ),
        (
            "GRANT CREATE ON SCHEMA ofarm_crypto TO ofarm_app",
            "REVOKE CREATE ON SCHEMA ofarm_crypto FROM ofarm_app",
            "native-verifier schema ACL differs",
        ),
    ),
    ids=("crypto-object", "crypto-acl"),
)
def test_post_migration_crypto_schema_tamper_refuses_every_gate(
    tenant_target: TenantTarget,
    tamper_statement: str,
    cleanup_statement: str,
    runner_error: str,
) -> None:
    with psycopg.connect(
        tenant_target.target_admin_dsn, autocommit=True
    ) as admin:
        admin.execute("SET ROLE ofarm_crypto_installer")
        admin.execute(tamper_statement)
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

        with pytest.raises(MigrationTargetError, match=runner_error):
            migrate_service(
                admin_dsn=tenant_target.admin_dsn,
                migrator_dsn=tenant_target.migrator_dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=tenant_target.migration_set,
                release_identity=RELEASE_IDENTITY,
                execution_id=uuid4(),
            )
    finally:
        with psycopg.connect(
            tenant_target.target_admin_dsn, autocommit=True
        ) as admin:
            admin.execute("SET ROLE ofarm_crypto_installer")
            admin.execute(cleanup_statement)

    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        assert _verify(migrator)[0] is True


def test_post_migration_native_extension_membership_tamper_refuses_every_gate(
    tenant_target: TenantTarget,
) -> None:
    function_identity = (
        "ofarm_crypto.ed25519_verify(bytea, bytea, bytea)"
    )
    with psycopg.connect(
        tenant_target.target_admin_dsn, autocommit=True
    ) as admin:
        admin.execute("SET ROLE ofarm_crypto_installer")
        admin.execute(
            "ALTER EXTENSION ofarm_ed25519 DROP FUNCTION "
            + function_identity
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

        with pytest.raises(
            MigrationTargetError,
            match=(
                "native-verifier SQL function identity differs; "
                "native-verifier extension membership differs"
            ),
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
        with psycopg.connect(
            tenant_target.target_admin_dsn, autocommit=True
        ) as admin:
            admin.execute("SET ROLE ofarm_crypto_installer")
            admin.execute(
                "ALTER EXTENSION ofarm_ed25519 ADD FUNCTION "
                + function_identity
            )

    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        assert _verify(migrator)[0] is True


def test_post_migration_native_extension_dependency_tamper_refuses_every_gate(
    tenant_target: TenantTarget,
) -> None:
    function_identity = (
        "ofarm_crypto.ed25519_verify(bytea, bytea, bytea)"
    )
    with psycopg.connect(
        tenant_target.target_admin_dsn, autocommit=True
    ) as admin:
        admin.execute("SET ROLE ofarm_crypto_installer")
        admin.execute(
            "ALTER FUNCTION "
            + function_identity
            + " DEPENDS ON EXTENSION plpgsql"
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

        with pytest.raises(
            MigrationTargetError,
            match="native-verifier SQL function identity differs",
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
        with psycopg.connect(
            tenant_target.target_admin_dsn, autocommit=True
        ) as admin:
            admin.execute("SET ROLE ofarm_crypto_installer")
            admin.execute(
                "ALTER FUNCTION "
                + function_identity
                + " NO DEPENDS ON EXTENSION plpgsql"
            )

    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        assert _verify(migrator)[0] is True


def test_post_migration_rewrite_rule_tamper_refuses_every_gate(
    tenant_target: TenantTarget,
) -> None:
    with psycopg.connect(
        tenant_target.target_admin_dsn, autocommit=True
    ) as admin:
        admin.execute("SET ROLE ofarm_owner")
        admin.execute(
            "CREATE RULE rogue AS ON INSERT TO ofarm.kernel_record "
            "DO INSTEAD NOTHING"
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
        with psycopg.connect(
            tenant_target.target_admin_dsn, autocommit=True
        ) as admin:
            admin.execute("SET ROLE ofarm_owner")
            admin.execute("DROP RULE rogue ON ofarm.kernel_record")

    with psycopg.connect(tenant_target.migrator_dsn) as migrator:
        assert _verify(migrator)[0] is True


def test_post_migration_database_wide_setting_refuses_every_gate(
    tenant_target: TenantTarget,
) -> None:
    with psycopg.connect(
        tenant_target.target_admin_dsn, autocommit=True
    ) as admin:
        admin.execute("SET ROLE ofarm_owner")
        admin.execute(
            "ALTER DATABASE ofarm_tenant "
            "SET default_transaction_read_only = on"
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

        with pytest.raises(
            MigrationTargetError,
            match="target route is not a writable primary",
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
        with psycopg.connect(
            tenant_target.target_admin_dsn, autocommit=True
        ) as admin:
            admin.execute("SET default_transaction_read_only = off")
            admin.execute(
                "ALTER DATABASE ofarm_tenant "
                "RESET default_transaction_read_only"
            )

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
        "sha256:897001ea090224da95746e9de94a6f0098c8a2eae01abab68ac1f32b6509e950"
    )
    assert row[5] == TENANT_PROVISIONING_SPEC.digest
    assert row[6] == TENANT_SERVICE.identity
    assert row[7] == 2
    assert row[9] == 2
    assert row[10] is False
