"""Live PostgreSQL tests for the read-only authentication authority."""

from __future__ import annotations

import psycopg
import pytest

from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TENANT_CAPABILITY_CONTRACT,
)
from kernel.tests import test_postgresql_tenant_migration as baseline


@pytest.fixture(scope="module")
def tenant_target():
    yield from baseline.tenant_target.__wrapped__()


@pytest.fixture(scope="module")
def authority(tenant_target):
    return baseline.authority.__wrapped__(tenant_target)


@pytest.fixture(scope="module")
def capability_key(tenant_target):
    return baseline.capability_key.__wrapped__(tenant_target)


def test_runtime_contract_is_exact_and_execute_only(tenant_target):
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        assert application.execute(
            "SELECT * FROM ofarm.observe_authentication_runtime_contract()"
        ).fetchone() == (
            application.execute(
                "SELECT audience FROM ofarm.create_tenant_challenge()"
            ).fetchone()[0],
            TENANT_CAPABILITY_CONTRACT.digest,
            "ofarm.authentication-runtime.v1",
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            application.execute("SELECT * FROM ofarm.principal_binding")


def test_resolver_returns_one_exact_active_authority(tenant_target, authority):
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        row = application.execute(
            """
            SELECT * FROM ofarm.resolve_principal_binding_authority(
                %s, %s, %s
            )
            """,
            (OIDC_ISSUER_EQUALITY_POLICY, baseline.ISSUER, authority.subject),
        ).fetchone()
        assert row is not None
        assert row[0:3] == (
            OIDC_ISSUER_EQUALITY_POLICY,
            baseline.ISSUER,
            authority.subject,
        )
        assert row[3:9] == (
            authority.binding_version_id,
            authority.binding_version_digest,
            authority.lifecycle_head_id,
            authority.lifecycle_head_digest,
            authority.tenant_id,
            authority.tenant_registration_digest,
        )
        assert row[9:15] == (
            authority.party_ref,
            baseline.PARTY_KIND,
            authority.party_ref,
            authority.party_schema_digest,
            authority.party_payload_digest,
            "ACTIVE",
        )


@pytest.mark.parametrize(
    "policy,issuer,subject",
    [
        ("OTHER", baseline.ISSUER, baseline.SUBJECT),
        (OIDC_ISSUER_EQUALITY_POLICY, baseline.ISSUER, "unknown"),
        (OIDC_ISSUER_EQUALITY_POLICY, baseline.ISSUER.upper(), baseline.SUBJECT),
    ],
)
def test_resolver_returns_no_row_for_non_authority(
    tenant_target, authority, policy, issuer, subject
):
    del authority
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        assert application.execute(
            """
            SELECT * FROM ofarm.resolve_principal_binding_authority(
                %s, %s, %s
            )
            """,
            (policy, issuer, subject),
        ).fetchone() is None


def test_signing_observer_returns_the_current_database_head(
    tenant_target, capability_key
):
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        row = application.execute(
            "SELECT * FROM ofarm.observe_signing_authority(%s)",
            (capability_key.kid,),
        ).fetchone()
        assert row is not None
        assert row[1] == application.execute(
            "SELECT audience FROM ofarm.create_tenant_challenge()"
        ).fetchone()[0]
        assert row[2] == TENANT_CAPABILITY_CONTRACT.digest
        assert row[3:6] == (
            capability_key.candidate_id,
            capability_key.kid,
            capability_key.candidate_digest,
        )
        assert len(row[6]) == 32
        assert row[10] == "OPEN"
        assert row[12:14] == (
            capability_key.head_id,
            capability_key.head_digest,
        )
        assert row[14] == capability_key.activated_at_unix_microseconds
        assert row[14] < row[15]
        assert row[16].startswith("sha256:")
        assert row[17].startswith("sha256:")
        assert row[18] >= row[14]


def test_broken_lifecycle_head_raises_pt001(
    tenant_target, authority, capability_key
):
    del authority
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute(
            "ALTER TABLE ofarm.tenant_capability_keyring "
            "DISABLE TRIGGER USER"
        )
        admin.execute(
            "ALTER TABLE ofarm.tenant_capability_keyring "
            "DROP CONSTRAINT tenant_capability_keyring_head_fkey"
        )
        admin.execute(
            """
            UPDATE ofarm.tenant_capability_keyring
               SET projected_head_digest = %s
            """,
            ("sha256:" + "11" * 32,),
        )
        admin.execute("SET SESSION AUTHORIZATION ofarm_app")
        with pytest.raises(psycopg.Error) as failure:
            admin.execute(
                "SELECT * FROM ofarm.observe_signing_authority(%s)",
                (capability_key.kid,),
            )
        assert failure.value.sqlstate == "PT001"
        admin.rollback()
        admin.execute("RESET SESSION AUTHORIZATION")


def test_missing_immutable_party_reference_guard_raises_pt001(
    tenant_target, authority
):
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute(
            "ALTER TABLE ofarm.principal_binding "
            "DROP CONSTRAINT principal_binding_party_fkey"
        )
        admin.execute("SET SESSION AUTHORIZATION ofarm_app")
        with pytest.raises(psycopg.Error) as failure:
            admin.execute(
                """
                SELECT * FROM ofarm.resolve_principal_binding_authority(
                    %s, %s, %s
                )
                """,
                (
                    OIDC_ISSUER_EQUALITY_POLICY,
                    baseline.ISSUER,
                    authority.subject,
                ),
            )
        assert failure.value.sqlstate == "PT001"
        admin.rollback()
        admin.execute("RESET SESSION AUTHORIZATION")
