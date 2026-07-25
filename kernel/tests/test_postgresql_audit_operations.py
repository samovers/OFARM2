"""Focused PostgreSQL tests for the additive audit operations migration."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest

from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    load_migration_set,
)
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn as _role_dsn,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _insert_historical_v1(
    state: dict[str, object],
) -> tuple[UUID, bytes, tuple[object, object]]:
    event_id = uuid4()
    correlation_hmac = bytes.fromhex("71" * 32)
    with psycopg.connect(
        str(state["target_admin_dsn"]), autocommit=True
    ) as admin:
        outcome = admin.execute(
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
                'AUTHENTICATION', 'CREDENTIAL_MISSING',
                'OFARM_PRETENANT_CORRELATION_V1', 1, %s,
                'OFARM_PRETENANT_SECURITY_EVENT_V1',
                'CORRELATION_HMAC_ONLY_V1', 'SECURITY_DIAGNOSTIC_30D_V1',
                ofarm_security._pretenant_event_fingerprint(
                    %s, 'AUTHENTICATION_BOUNDARY_V1', 'AUTHENTICATION',
                    'CREDENTIAL_MISSING',
                    'OFARM_PRETENANT_CORRELATION_V1', 1, %s
                )
            FROM timing
            RETURNING observed_at, purge_after
            """,
            (event_id, correlation_hmac, event_id, correlation_hmac),
        ).fetchone()
    return event_id, correlation_hmac, outcome


def test_operations_migration_is_bounded_and_keeps_0001_immutable():
    migration_set = load_migration_set(PACKAGE_ROOT, SECURITY_AUDIT_SERVICE)
    initial, operations, *_later = migration_set.migrations
    initial_source = initial.source_bytes.decode("utf-8")
    source = operations.source_bytes.decode("utf-8")

    assert initial.source_sha256 == \
        "sha256:5e648e0127ca386363c3a1d979a5718cbd5b4846b3ad98ceaee5e7684b278517"
    assert source.count(
        "CREATE INDEX operational_security_event_hmac_retention_idx"
    ) == 1
    assert (
        "(correlation_hmac_key_version, purge_after DESC)" in source
    )
    assert "WHERE event_kind = 'PRE_TENANT_FAILURE'" in source
    assert source.count("RETURNS TABLE (") == 2
    assert source.count(
        "session_user <> 'ofarm_security_audit_control_login'"
    ) == 2
    assert "p_key_version IS NULL OR p_key_version NOT IN (1, 2)" in source
    append_source = initial_source.split(
        "CREATE FUNCTION ofarm_security.append_pretenant_failure(", 1
    )[1].split(
        "REVOKE ALL PRIVILEGES ON FUNCTION "
        "ofarm_security.append_pretenant_failure(",
        1,
    )[0]
    assert append_source.index("SELECT * INTO v_existing") < \
        append_source.index("SELECT * INTO v_receipt") < \
        append_source.index("p_correlation_hmac_key_version <> 1")


def test_v1_requires_exact_committed_retry_identity(
    migrated_audit_service,
):
    state = migrated_audit_service
    event_id, correlation_hmac, original = _insert_historical_v1(state)
    arguments = (
        event_id,
        "CREDENTIAL_MISSING",
        correlation_hmac,
        "OFARM_PRETENANT_CORRELATION_V1",
        1,
    )
    with psycopg.connect(
        _role_dsn(
            state, "ofarm_security_authentication_producer_login"
        ),
        autocommit=True,
    ) as producer:
        retry = producer.execute(
            """
            SELECT * FROM ofarm_security.append_pretenant_failure(
                %s, %s, %s, %s, %s
            )
            """,
            arguments,
        ).fetchone()
        with pytest.raises(psycopg.Error) as mismatched:
            producer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, 'VERIFIER_UNAVAILABLE', %s, %s, %s
                )
                """,
                (
                    event_id,
                    correlation_hmac,
                    arguments[3],
                    arguments[4],
                ),
            )
        with pytest.raises(psycopg.Error) as fresh:
            producer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, %s, %s, %s, %s
                )
                """,
                (uuid4(), *arguments[1:]),
            )
        with pytest.raises(psycopg.Error) as null_version:
            producer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, %s, %s, %s, NULL
                )
                """,
                (uuid4(), *arguments[1:4]),
            )

    assert retry == (
        event_id,
        original[0],
        original[1],
        True,
        None,
        False,
    )
    assert mismatched.value.sqlstate == "22000"
    assert fresh.value.sqlstate == "22023"
    assert null_version.value.sqlstate == "22023"
    assert "correlation HMAC policy is not active" in str(null_version.value)


@pytest.mark.parametrize("unknown_version", (None, 0, 3))
def test_unknown_hmac_key_version_is_an_explicit_refusal(
    migrated_audit_service,
    unknown_version,
):
    state = migrated_audit_service
    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        with pytest.raises(psycopg.Error) as refusal:
            control.execute(
                """
                SELECT * FROM
                    ofarm_security.observe_correlation_hmac_key_retention(%s)
                """,
                (unknown_version,),
            ).fetchall()

    assert refusal.value.sqlstate == "22023"
    assert "key version is unknown" in str(refusal.value)


def test_key_retention_observation_is_one_closed_control_row(
    migrated_audit_service,
):
    state = migrated_audit_service
    _insert_historical_v1(state)
    with psycopg.connect(
        _role_dsn(
            state, "ofarm_security_authentication_producer_login"
        ),
        autocommit=True,
    ) as producer:
        producer.execute(
            """
            SELECT * FROM ofarm_security.append_pretenant_failure(
                %s, 'CREDENTIAL_MISSING', %s,
                'OFARM_PRETENANT_CORRELATION_V1', 2
            )
            """,
            (uuid4(), bytes.fromhex("72" * 32)),
        ).fetchone()

    with psycopg.connect(
        str(state["target_admin_dsn"]), autocommit=True
    ) as admin:
        expected = dict(
            admin.execute(
                """
                SELECT correlation_hmac_key_version,
                       pg_catalog.max(purge_after)
                FROM ofarm_security.operational_security_event
                WHERE event_kind = 'PRE_TENANT_FAILURE'
                  AND correlation_hmac_key_version IN (1, 2)
                GROUP BY correlation_hmac_key_version
                """
            ).fetchall()
        )

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        v1 = control.execute(
            """
            SELECT * FROM
                ofarm_security.observe_correlation_hmac_key_retention(1)
            """
        ).fetchall()
        v2 = control.execute(
            """
            SELECT * FROM
                ofarm_security.observe_correlation_hmac_key_retention(2)
            """
        ).fetchall()

    assert v1 == [(1, False, expected[1])]
    assert v2 == [(2, True, expected[2])]

    with psycopg.connect(
        _role_dsn(
            state, "ofarm_security_authentication_producer_login"
        ),
        autocommit=True,
    ) as producer:
        with pytest.raises(psycopg.Error) as unauthorized:
            producer.execute(
                """
                SELECT * FROM
                    ofarm_security.observe_correlation_hmac_key_retention(2)
                """
            ).fetchall()
    assert unauthorized.value.sqlstate == "42501"


def test_overflow_observation_refuses_wrong_role(
    migrated_audit_service,
):
    state = migrated_audit_service
    with psycopg.connect(
        _role_dsn(
            state, "ofarm_security_authentication_producer_login"
        ),
        autocommit=True,
    ) as producer:
        with pytest.raises(psycopg.Error) as refusal:
            producer.execute(
                """
                SELECT * FROM
                    ofarm_security.observe_next_closeable_overflow_bucket()
                """
            ).fetchall()

    assert refusal.value.sqlstate == "42501"


def test_overflow_observation_returns_one_oldest_closeable_bucket(
    migrated_audit_service,
):
    state = migrated_audit_service
    with psycopg.connect(
        str(state["target_admin_dsn"]), autocommit=True
    ) as admin:
        current_bucket = admin.execute(
            """
            SELECT pg_catalog.date_bin(
                pg_catalog.make_interval(secs => 60),
                pg_catalog.clock_timestamp(),
                '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
            )
            """
        ).fetchone()[0]
        oldest = current_bucket - timedelta(minutes=3)
        newer = current_bucket - timedelta(minutes=2)
        never_overflowed = current_bucket - timedelta(minutes=1)
        admin.execute(
            """
            INSERT INTO ofarm_security.operational_security_quota_bucket (
                producer, component, bucket_start, accepted_event_count,
                overflow_started_at
            ) VALUES
                ('AUTHENTICATION_BOUNDARY_V1', 'AUTHENTICATION',
                 %s, 1024, %s),
                ('REQUEST_ROUTER_BOUNDARY_V1', 'REQUEST_ROUTER',
                 %s, 1024, %s),
                ('AUTHENTICATION_BOUNDARY_V1', 'AUTHENTICATION',
                 %s, 0, NULL),
                ('REQUEST_ROUTER_BOUNDARY_V1', 'REQUEST_ROUTER',
                 %s, 1024, %s)
            """,
            (
                oldest,
                oldest + timedelta(seconds=1),
                newer,
                newer + timedelta(seconds=1),
                never_overflowed,
                current_bucket,
                current_bucket + timedelta(seconds=1),
            ),
        )

    with psycopg.connect(
        _role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        assert control.execute(
            """
            SELECT * FROM
                ofarm_security.observe_next_closeable_overflow_bucket()
            """
        ).fetchall() == [
            ("AUTHENTICATION_BOUNDARY_V1", "AUTHENTICATION", oldest)
        ]
        control.execute(
            """
            SELECT * FROM ofarm_security.close_overflow_bucket(
                'AUTHENTICATION_BOUNDARY_V1', 'AUTHENTICATION', %s
            )
            """,
            (oldest,),
        ).fetchone()
        assert control.execute(
            """
            SELECT * FROM
                ofarm_security.observe_next_closeable_overflow_bucket()
            """
        ).fetchall() == [
            ("REQUEST_ROUTER_BOUNDARY_V1", "REQUEST_ROUTER", newer)
        ]
        control.execute(
            """
            SELECT * FROM ofarm_security.close_overflow_bucket(
                'REQUEST_ROUTER_BOUNDARY_V1', 'REQUEST_ROUTER', %s
            )
            """,
            (newer,),
        ).fetchone()
        assert control.execute(
            """
            SELECT * FROM
                ofarm_security.observe_next_closeable_overflow_bucket()
            """
        ).fetchall() == []
