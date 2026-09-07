"""Retirement/admission issuer evidence with its own module-scoped DB fixture."""

from __future__ import annotations

import hashlib

import psycopg
import pytest

from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome
from kernel.tests._tenant_signing_support import live_signing
from kernel.tests.test_postgresql_tenant_capability_signing import _manager
from kernel.tests.test_postgresql_tenant_migration import (
    _register_capability_key_candidate,
    _sha256_id,
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


def _refused(manager, principal):
    with pytest.raises(TenantBoundaryError) as raised:
        with manager.unit_of_work(principal):
            pytest.fail("ineligible key exposed a unit of work")
    assert raised.value.outcome is TenantBoundaryOutcome.CAPABILITY_REFUSED


def test_real_issuer_refuses_retired_pinned_key_and_closed_admission(
    target, tenant_authority, key_authority
):
    principal = _principal(target, tenant_authority)
    old_signing = live_signing(target, key_authority.kid)
    old_manager = _manager(target, old_signing.issuer)
    new_manager = None
    kms = _sha256_id(b"issuer-retirement-kms-fixture")
    iam = _sha256_id(b"issuer-retirement-iam-fixture")
    try:
        with psycopg.connect(
            target.role_dsn("ofarm_capability_key_control_login")
        ) as controller:
            replacement = _register_capability_key_candidate(
                controller,
                seed=hashlib.sha256(b"issuer-retirement-replacement").digest(),
                label="issuer-retirement-replacement",
            )
            rotated = controller.execute(
                """
                SELECT * FROM ofarm.rotate_tenant_capability_key(
                    %s, %s, %s, %s, %s, %s, %s, 'GRACEFUL_ROTATION'
                )
                """,
                (key_authority.kid, replacement.kid, key_authority.head_id,
                 key_authority.head_digest, replacement.preflight_receipt_digest,
                 kms, iam),
            ).fetchone()
            controller.commit()
            _refused(old_manager, principal)
            assert old_signing.client.calls == []
            new_signing = live_signing(
                target, replacement.kid, seed=replacement.seed
            )
            new_manager = _manager(target, new_signing.issuer)
            controller.execute(
                """
                SELECT * FROM ofarm.close_tenant_capability_admission(
                    %s, %s, %s, %s, %s, 'COMPROMISE'
                )
                """,
                (rotated[0], rotated[1], replacement.kid, kms, iam),
            )
            controller.commit()
            _refused(new_manager, principal)
            assert new_signing.client.calls == []
    finally:
        old_manager.close()
        if new_manager is not None:
            new_manager.close()
