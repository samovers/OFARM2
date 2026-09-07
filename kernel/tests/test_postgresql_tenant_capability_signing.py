"""Production issuer/UOW/native binder; external KMS and observer are fixtures."""

from __future__ import annotations

import asyncio
import time
from dataclasses import FrozenInstanceError
from uuid import uuid4

import psycopg
import pytest

from deployment.postgresql.tenant_contract import (
    TENANT_CAPABILITY_MAX_TTL_MICROSECONDS,
    TENANT_CHALLENGE_MAX_AGE_MICROSECONDS,
    decode_tenant_capability_jws,
)
from kernel.tenant_uow import (
    GovernedBatchRequest,
    TenantBoundaryError,
    TenantBoundaryOutcome,
    TenantUnitOfWorkManager,
    create_tenant_connection_pool,
)
from kernel.tests._tenant_signing_support import live_signing
from kernel.tests.test_postgresql_tenant_migration import (
    authority,  # noqa: F401 - imported fixture
    capability_key,  # noqa: F401 - imported fixture
    tenant_target,  # noqa: F401 - imported fixture
)
from kernel.tests.test_postgresql_tenant_uow import _principal


@pytest.fixture(scope="module")
def target(request):
    return request.getfixturevalue("tenant_target")


@pytest.fixture(scope="module")
def tenant_authority(request):
    return request.getfixturevalue("authority")


@pytest.fixture(scope="module")
def key_authority(request):
    return request.getfixturevalue("capability_key")


def _manager(target, issuer):
    manager = TenantUnitOfWorkManager(
        create_tenant_connection_pool(target.role_dsn("ofarm_app")), issuer
    )
    manager.initialize()
    return manager


def _stored_contexts(target, challenges):
    with psycopg.connect(target.target_admin_dsn) as admin:
        return admin.execute(
            """
            SELECT challenge_id, context_state FROM ofarm.tenant_binding_context
            WHERE challenge_id = ANY(%s) ORDER BY challenge_id
            """,
            ([challenge.challenge_id for challenge in challenges],),
        ).fetchall()


def test_real_delayed_issuer_binds_exact_protected_challenge_deadline(
    target, tenant_authority, key_authority, monkeypatch
):
    principal = _principal(target, tenant_authority)
    signing = live_signing(target, key_authority.kid)
    minted = []
    original_mint = signing.issuer.mint

    def delayed_mint(identity, principal_authority, challenge):
        # Real elapsed delay, with no DB clock or protected timestamp mutation.
        time.sleep(0.02)
        token = original_mint(identity, principal_authority, challenge)
        minted.append((challenge, decode_tenant_capability_jws(token).capability))
        return token

    monkeypatch.setattr(signing.issuer, "mint", delayed_mint)
    manager = _manager(target, signing.issuer)
    try:
        with manager.unit_of_work(principal) as unit:
            assert unit.binding.tenant_id == tenant_authority.tenant_id
            assert unit.binding.subject == principal.identity.subject
            challenge, capability = minted[0]
            assert unit.binding.capability_nonce == capability.nonce
            assert capability.challenge_id == challenge.challenge_id
            assert capability.issued_at_unix_microseconds > challenge.created_at_us
            assert capability.not_before_unix_microseconds == (
                capability.issued_at_unix_microseconds
            )
            assert capability.expires_at_unix_microseconds == (
                challenge.created_at_us + TENANT_CHALLENGE_MAX_AGE_MICROSECONDS
            )
            assert capability.expires_at_unix_microseconds < (
                capability.issued_at_unix_microseconds
                + TENANT_CAPABILITY_MAX_TTL_MICROSECONDS
            )
            with pytest.raises(FrozenInstanceError):
                challenge.created_at_us = capability.issued_at_unix_microseconds
        assert _stored_contexts(target, [challenge]) == [
            (challenge.challenge_id, "BOUND")
        ]
        assert len(signing.client.calls) == 1
    finally:
        manager.close()


@pytest.mark.parametrize("failure_stage", ("before-bind", "after-bind"))
def test_real_issuer_cancellation_rolls_back_and_next_transaction_is_fresh(
    target, tenant_authority, key_authority, monkeypatch, failure_stage
):
    principal = _principal(target, tenant_authority)
    signing = live_signing(target, key_authority.kid)
    challenges = []
    original_mint = signing.issuer.mint

    def capture_mint(identity, principal_authority, challenge):
        challenges.append(challenge)
        token = original_mint(identity, principal_authority, challenge)
        if failure_stage == "before-bind" and len(challenges) == 1:
            raise asyncio.CancelledError
        return token

    monkeypatch.setattr(signing.issuer, "mint", capture_mint)
    manager = _manager(target, signing.issuer)
    batch_id = f"cancelled-issuer-{uuid4().hex}"
    try:
        with pytest.raises(asyncio.CancelledError):
            with manager.unit_of_work(principal) as unit:
                assert failure_stage == "after-bind"
                unit.begin_batch(GovernedBatchRequest(
                    batch_id, "ISSUER_ROLLBACK", f"request-{uuid4().hex}",
                    tenant_authority.runtime_bundle_digest,
                ))
                raise asyncio.CancelledError
        assert _stored_contexts(target, challenges) == []
        with psycopg.connect(target.target_admin_dsn) as admin:
            assert admin.execute(
                "SELECT count(*) FROM ofarm.governed_write_batch WHERE batch_id = %s",
                (batch_id,),
            ).fetchone() == (0,)
        with manager.unit_of_work(principal) as unit:
            assert unit.binding.tenant_id == tenant_authority.tenant_id
        assert len(challenges) == 2
        assert challenges[0].challenge_id != challenges[1].challenge_id
        assert _stored_contexts(target, challenges) == [
            (challenges[1].challenge_id, "BOUND")
        ]
        # Cancellation is after signing; a dispatched signature is not undone.
        assert len(signing.client.calls) == 2
    finally:
        manager.close()


def test_real_observation_uuid_substitution_refuses_before_signing(
    target, tenant_authority, key_authority, monkeypatch
):
    principal = _principal(target, tenant_authority)
    signing = live_signing(target, key_authority.kid)
    observed = []
    original_execute = psycopg.Connection.execute

    class SubstitutedObservation:
        def fetchone(self):
            return (uuid4(), observed[0][1])

    def substitute_observer(connection, query, *args, **kwargs):
        cursor = original_execute(connection, query, *args, **kwargs)
        if query == "SELECT * FROM ofarm.current_tenant_challenge()":
            observed.append(cursor.fetchone())
            return SubstitutedObservation()
        return cursor

    monkeypatch.setattr(psycopg.Connection, "execute", substitute_observer)
    manager = _manager(target, signing.issuer)
    try:
        with pytest.raises(TenantBoundaryError) as raised:
            with manager.unit_of_work(principal):
                pytest.fail("substituted observation exposed a unit of work")
        assert raised.value.outcome is TenantBoundaryOutcome.BINDING_REFUSED
        assert signing.client.calls == []
        with psycopg.connect(target.target_admin_dsn) as admin:
            assert admin.execute(
                "SELECT count(*) FROM ofarm.tenant_binding_context WHERE challenge_id = %s",
                (observed[0][0],),
            ).fetchone() == (0,)
    finally:
        manager.close()
