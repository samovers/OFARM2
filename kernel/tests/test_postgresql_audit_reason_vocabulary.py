"""Focused live tests for the pre-tenant audit reason vocabulary."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql

from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    load_migration_set,
)
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn as _role_dsn,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
AUTH_ROLE = "ofarm_security_authentication_producer_login"
ROUTER_ROLE = "ofarm_security_request_router_producer_login"
HMAC_DOMAIN = "OFARM_PRETENANT_CORRELATION_V1"
ACTIVE_REASONS = (
    (AUTH_ROLE, "CREDENTIAL_MISSING"),
    (AUTH_ROLE, "CREDENTIAL_MALFORMED"),
    (AUTH_ROLE, "VERIFIER_UNAVAILABLE"),
    (AUTH_ROLE, "VERIFICATION_REFUSED"),
    (AUTH_ROLE, "PRINCIPAL_BINDING_REFUSED"),
    (AUTH_ROLE, "AUTHORITY_INTEGRITY_REFUSED"),
    (AUTH_ROLE, "AUTHORITY_UNAVAILABLE"),
    (ROUTER_ROLE, "TENANT_BOUNDARY_UNAVAILABLE"),
    (ROUTER_ROLE, "CAPABILITY_REFUSED"),
    (ROUTER_ROLE, "BINDER_REFUSED"),
)
RETIRED_REASONS = (
    (AUTH_ROLE, "TENANT_PARTY_PIN_REFUSED"),
    (AUTH_ROLE, "CAPABILITY_REFUSED"),
    (ROUTER_ROLE, "SECURITY_ROUTE_REFUSED"),
    (ROUTER_ROLE, "ACTOR_BINDING_REFUSED"),
)
CROSS_PRODUCER_REASONS = (
    (AUTH_ROLE, "TENANT_BOUNDARY_UNAVAILABLE"),
    (AUTH_ROLE, "BINDER_REFUSED"),
    (ROUTER_ROLE, "CREDENTIAL_MISSING"),
    (ROUTER_ROLE, "CREDENTIAL_MALFORMED"),
    (ROUTER_ROLE, "VERIFIER_UNAVAILABLE"),
    (ROUTER_ROLE, "VERIFICATION_REFUSED"),
    (ROUTER_ROLE, "PRINCIPAL_BINDING_REFUSED"),
    (ROUTER_ROLE, "AUTHORITY_INTEGRITY_REFUSED"),
    (ROUTER_ROLE, "AUTHORITY_UNAVAILABLE"),
)
APPEND_SQL = """
    SELECT * FROM ofarm_security.append_pretenant_failure(
        %s, %s, %s, %s, 2
    )
"""


def _append(
    state: dict[str, object],
    role: str,
    event_id: UUID,
    reason: str,
    correlation_hmac: bytes = bytes.fromhex("41" * 32),
) -> tuple[object, ...]:
    with psycopg.connect(
        _role_dsn(state, role), autocommit=True
    ) as producer:
        row = producer.execute(
            APPEND_SQL,
            (event_id, reason, correlation_hmac, HMAC_DOMAIN),
        ).fetchone()
    assert row is not None
    return row


def _assert_refused(
    state: dict[str, object],
    role: str,
    reason: str,
) -> None:
    with psycopg.connect(
        _role_dsn(state, role), autocommit=True
    ) as producer:
        with pytest.raises(psycopg.Error) as refusal:
            producer.execute(
                APPEND_SQL,
                (uuid4(), reason, bytes.fromhex("42" * 32), HMAC_DOMAIN),
            ).fetchone()
    assert refusal.value.sqlstate == "22023"
    assert "reason is not allowed for this producer" in str(refusal.value)


def _seed_historical_event(
    admin,
    event_id: UUID,
    reason: str,
    correlation_hmac: bytes,
) -> tuple[tuple[object, ...], tuple[object, ...]]:
    original = admin.execute(
        """
        WITH timing AS (
            SELECT pg_catalog.clock_timestamp() AS observed_at
        )
        INSERT INTO ofarm_security.operational_security_event (
            event_id, event_insert_xid, observed_at, purge_after,
            event_kind, producer, component, reason,
            correlation_hmac_domain, correlation_hmac_key_version,
            correlation_hmac_value, event_format_identity,
            redaction_policy_identity, retention_policy_identity,
            append_input_fingerprint
        )
        SELECT
            %s, pg_catalog.pg_current_xact_id(), timing.observed_at,
            timing.observed_at + pg_catalog.make_interval(secs => 2592000),
            'PRE_TENANT_FAILURE', 'AUTHENTICATION_BOUNDARY_V1',
            'AUTHENTICATION', %s, %s, 2, %s,
            'OFARM_PRETENANT_SECURITY_EVENT_V1',
            'CORRELATION_HMAC_ONLY_V1', 'SECURITY_DIAGNOSTIC_30D_V1',
            ofarm_security._pretenant_event_fingerprint(
                %s, 'AUTHENTICATION_BOUNDARY_V1', 'AUTHENTICATION',
                %s, %s, 2, %s
            )
        FROM timing
        RETURNING event_id, observed_at, purge_after
        """,
        (
            event_id, reason, HMAC_DOMAIN, correlation_hmac,
            event_id, reason, HMAC_DOMAIN, correlation_hmac,
        ),
    ).fetchone()
    assert original is not None
    snapshot = admin.execute(
        """
        SELECT * FROM ofarm_security.operational_security_event
        WHERE event_id = %s
        """,
        (event_id,),
    ).fetchone()
    assert snapshot is not None
    expected = (event_id, original[1], original[2], True, None, False)
    return expected, snapshot


def _seed_historical_receipt(
    admin,
    event_id: UUID,
    reason: str,
    correlation_hmac: bytes,
) -> tuple[tuple[object, ...], tuple[object, ...]]:
    original = admin.execute(
        """
        WITH timing AS (
            SELECT pg_catalog.date_bin(
                pg_catalog.make_interval(secs => 60),
                pg_catalog.clock_timestamp(),
                '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
            ) AS bucket_start
        )
        UPDATE ofarm_security.
            operational_security_overflow_identity_receipt AS receipt
        SET event_id = %s,
            append_input_fingerprint =
                ofarm_security._pretenant_event_fingerprint(
                    %s, receipt.producer, receipt.component, %s, %s, 2, %s
                ),
            bucket_start = timing.bucket_start,
            purge_after = timing.bucket_start
                + pg_catalog.make_interval(secs => 2592000)
        FROM timing
        WHERE receipt.producer = 'AUTHENTICATION_BOUNDARY_V1'
          AND receipt.component = 'AUTHENTICATION'
          AND receipt.lock_slot = 0
        RETURNING receipt.bucket_start
        """,
        (event_id, event_id, reason, HMAC_DOMAIN, correlation_hmac),
    ).fetchone()
    assert original is not None
    snapshot = admin.execute(
        """
        SELECT * FROM ofarm_security.
            operational_security_overflow_identity_receipt
        WHERE event_id = %s
        """,
        (event_id,),
    ).fetchone()
    assert snapshot is not None
    expected = (None, None, None, False, original[0], False)
    return expected, snapshot


def _seed_historical_reason(
    state: dict[str, object],
    storage: str,
) -> tuple[UUID, bytes, tuple[object, ...], tuple[object, ...]]:
    event_id = uuid4()
    correlation_hmac = bytes.fromhex("43" * 32)
    reason = "TENANT_PARTY_PIN_REFUSED"
    seed = (
        _seed_historical_event
        if storage == "event"
        else _seed_historical_receipt
    )
    with psycopg.connect(
        str(state["target_admin_dsn"]), autocommit=True
    ) as admin:
        expected, snapshot = seed(
            admin, event_id, reason, correlation_hmac
        )
    return event_id, correlation_hmac, expected, snapshot


def test_vocabulary_migration_is_additive_and_bounded():
    migration_set = load_migration_set(PACKAGE_ROOT, SECURITY_AUDIT_SERVICE)
    initial, operations, vocabulary = migration_set.migrations
    source = vocabulary.source_bytes.decode("utf-8")

    assert initial.source_sha256 == \
        "sha256:5e648e0127ca386363c3a1d979a5718cbd5b4846b3ad98ceaee5e7684b278517"
    assert operations.source_sha256 == \
        "sha256:99b5bc1016a2544dab54ebd9359d6cedd697e2adf3c749ef3634485103544133"
    assert vocabulary.filename == "0003_outcome_reason_vocabulary.sql"
    assert len(source.splitlines()) <= 325
    assert "CREATE FUNCTION" not in source
    assert "CREATE ROLE" not in source
    assert "CREATE TABLE" not in source
    assert "DELETE FROM ofarm_security.operational_security_event" not in source
    assert "UPDATE ofarm_security.operational_security_event" not in source
    assert (
        "UPDATE ofarm_security."
        "operational_security_overflow_identity_receipt"
    ) not in source


@pytest.mark.parametrize(("role", "reason"), ACTIVE_REASONS)
def test_every_active_reason_is_accepted_fresh(
    migrated_audit_service,
    role,
    reason,
):
    event_id = uuid4()
    result = _append(migrated_audit_service, role, event_id, reason)
    assert result[0] == event_id
    assert result[3:] == (True, None, False)


@pytest.mark.parametrize(("role", "reason"), RETIRED_REASONS)
def test_retired_reasons_are_refused_for_fresh_appends(
    migrated_audit_service,
    role,
    reason,
):
    _assert_refused(migrated_audit_service, role, reason)


@pytest.mark.parametrize(("role", "reason"), CROSS_PRODUCER_REASONS)
def test_cross_producer_reasons_are_refused(
    migrated_audit_service,
    role,
    reason,
):
    _assert_refused(migrated_audit_service, role, reason)


@pytest.mark.parametrize("storage", ("event", "receipt"))
def test_retired_historical_exact_retries_preserve_original_outcome(
    migrated_audit_service,
    storage,
):
    state = migrated_audit_service
    event_id, correlation_hmac, expected, before = _seed_historical_reason(
        state, storage
    )
    retry = _append(
        state,
        AUTH_ROLE,
        event_id,
        "TENANT_PARTY_PIN_REFUSED",
        correlation_hmac,
    )
    with psycopg.connect(
        _role_dsn(state, AUTH_ROLE), autocommit=True
    ) as producer:
        with pytest.raises(psycopg.Error) as changed:
            producer.execute(
                APPEND_SQL,
                (
                    event_id,
                    "TENANT_PARTY_PIN_REFUSED",
                    bytes.fromhex("44" * 32),
                    HMAC_DOMAIN,
                ),
            ).fetchone()
    with psycopg.connect(
        str(state["target_admin_dsn"]), autocommit=True
    ) as admin:
        table = (
            "operational_security_event"
            if storage == "event"
            else "operational_security_overflow_identity_receipt"
        )
        after = admin.execute(
            sql.SQL(
                "SELECT * FROM ofarm_security.{} WHERE event_id = %s"
            ).format(sql.Identifier(table)),
            (event_id,),
        ).fetchone()

    assert retry == expected
    assert changed.value.sqlstate == "22000"
    assert after == before


def test_contract_observer_reports_v3_vocabulary(
    migrated_audit_service,
):
    state = migrated_audit_service
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_readiness_login"),
        autocommit=True,
    ) as readiness:
        row = readiness.execute(
            "SELECT * FROM ofarm_security.observe_security_audit_contract()"
        ).fetchone()

    assert row is not None
    assert row[1] == SECURITY_AUDIT_CONTRACT.digest
    assert row[9] == 3
    assert row[10] == state["migration_set"].digest
    assert row[11:] == (True, False)
