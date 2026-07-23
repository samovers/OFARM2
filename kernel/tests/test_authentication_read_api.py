"""Live PostgreSQL tests for the read-only authentication authority."""

from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TENANT_CAPABILITY_CONTRACT,
)
from kernel.authentication import VerifiedIdentity
from kernel.principal_resolver import PrincipalBindingResolver
from kernel.tests import test_postgresql_tenant_migration as baseline

tenant_target = baseline.tenant_target
authority = baseline.authority
capability_key = baseline.capability_key


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


@pytest.mark.parametrize(
    "query,parameters",
    [
        ("SELECT * FROM ofarm.observe_authentication_runtime_contract()", ()),
        (
            "SELECT * FROM ofarm.resolve_principal_binding_authority(%s, %s, %s)",
            (OIDC_ISSUER_EQUALITY_POLICY, baseline.ISSUER, baseline.SUBJECT),
        ),
        ("SELECT * FROM ofarm.observe_signing_authority(%s)", ("a" * 43,)),
    ],
    ids=("contract", "principal", "signing"),
)
def test_authority_observers_reject_non_application_session(
    tenant_target, query, parameters
):
    with psycopg.connect(tenant_target.target_admin_dsn, autocommit=True) as admin:
        admin.execute("SET SESSION AUTHORIZATION ofarm_owner")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            admin.execute(query, parameters)


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


def test_python_resolver_consumes_the_exact_read_api(tenant_target, authority):
    with psycopg.connect(
        tenant_target.role_dsn("ofarm_app")
    ) as application:
        audience = application.execute(
            "SELECT audience FROM "
            "ofarm.observe_authentication_runtime_contract()"
        ).fetchone()[0]
    resolver = PrincipalBindingResolver(
        lambda: psycopg.connect(tenant_target.role_dsn("ofarm_app")),
        expected_audience=audience,
    )
    resolver.initialize()

    principal = resolver.resolve(
        VerifiedIdentity(
            equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
            issuer=baseline.ISSUER,
            subject=authority.subject,
        )
    )

    assert principal.authority.binding_version_id == (
        authority.binding_version_id
    )
    assert principal.authority.lifecycle_head_id == authority.lifecycle_head_id
    assert principal.authority.tenant_id == authority.tenant_id


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


@pytest.mark.parametrize("act_kind", ("REVOKE", "EXPIRE"))
def test_resolver_returns_no_row_for_inactive_authority(
    tenant_target, authority, act_kind
):
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute(
            "SET SESSION AUTHORIZATION ofarm_identity_control_login"
        )
        effective_at, decided_at = admin.execute(
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
        act_digest = baseline._compute_act_digest(
            admin,
            subject=authority.subject,
            stream_sequence=2,
            act_id=act_id,
            act_kind=act_kind,
            binding_version_id=authority.binding_version_id,
            binding_version_digest=authority.binding_version_digest,
            prior_act_id=authority.lifecycle_head_id,
            prior_act_digest=authority.lifecycle_head_digest,
            successor_version_id=None,
            successor_version_digest=None,
            effective_at=effective_at,
            decided_at=decided_at,
            reason=f"read-api-{act_kind.lower()}",
        )
        baseline._transition(
            admin,
            subject=authority.subject,
            expected_head_id=authority.lifecycle_head_id,
            expected_head_digest=authority.lifecycle_head_digest,
            act_id=act_id,
            act_digest=act_digest,
            act_kind=act_kind,
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
            reason=f"read-api-{act_kind.lower()}",
        )
        admin.execute("RESET SESSION AUTHORIZATION")
        admin.execute("SET SESSION AUTHORIZATION ofarm_app")
        assert admin.execute(
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
        ).fetchone() is None
        admin.rollback()


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


@pytest.mark.parametrize(
    "kid", ("not-a-kid", "a" * 43), ids=("malformed", "unknown")
)
def test_signing_observer_returns_no_row_for_non_authority(
    tenant_target, capability_key, kid
):
    assert kid != capability_key.kid
    with psycopg.connect(tenant_target.role_dsn("ofarm_app")) as application:
        assert application.execute(
            "SELECT * FROM ofarm.observe_signing_authority(%s)",
            (kid,),
        ).fetchone() is None


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


def test_tampered_principal_binding_digest_raises_pt001(
    tenant_target, authority
):
    with psycopg.connect(tenant_target.target_admin_dsn) as admin:
        admin.execute(
            "ALTER TABLE ofarm.principal_binding DISABLE TRIGGER USER"
        )
        admin.execute(
            "ALTER TABLE ofarm.principal_binding "
            "DROP CONSTRAINT principal_binding_digest_check"
        )
        admin.execute(
            """
            UPDATE ofarm.principal_binding
               SET valid_until = valid_until + INTERVAL '1 second'
             WHERE binding_version_id = %s
            """,
            (authority.binding_version_id,),
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
