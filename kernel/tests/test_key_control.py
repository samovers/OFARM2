"""Thin key-control parameter mapping and ambiguity handling."""
from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from kernel.key_control import (
    KeyControlError,
    KeyControlOutcomeUnknown,
    KeyEvidence,
    KeyLifecycleHead,
    TenantCapabilityKeyController,
)
from kernel.tests._signing_support import (
    DIGEST_A,
    DIGEST_B,
    DIGEST_C,
    KID,
    KMS_PUBLIC_KEY,
    RESOURCE,
    Connection,
    Factory,
)


def _head() -> KeyLifecycleHead:
    return KeyLifecycleHead(uuid4(), DIGEST_A)


def _evidence() -> KeyEvidence:
    return KeyEvidence(DIGEST_B, DIGEST_C)


def test_registration_and_preflight_map_exact_parameters():
    candidate_id = uuid4()
    connection = Connection(
        [[(candidate_id, KID, DIGEST_A)], [(True,)]]
    )
    controller = TenantCapabilityKeyController(Factory(connection))

    candidate = controller.register(KMS_PUBLIC_KEY, RESOURCE, DIGEST_B)
    verified = controller.verify_candidate_preflight(KID, b"x" * 64)

    assert candidate.candidate_id == candidate_id
    assert candidate.kid == KID
    assert candidate.candidate_digest == DIGEST_A
    assert verified is True
    assert connection.executions[0][1] == (
        KMS_PUBLIC_KEY,
        RESOURCE,
        DIGEST_B,
    )
    assert connection.executions[1][1] == (KID, b"x" * 64)


def test_activation_and_rotation_delegate_complete_receipt_fields():
    activated_id = uuid4()
    rotated_id = uuid4()
    head = _head()
    evidence = _evidence()
    connection = Connection(
        [
            [(activated_id, DIGEST_B, 101)],
            [(rotated_id, DIGEST_C, 202, 303)],
        ]
    )
    controller = TenantCapabilityKeyController(Factory(connection))

    activated = controller.activate(
        KID,
        None,
        DIGEST_A,
        evidence,
        "INITIAL_ACTIVATION",
    )
    rotated = controller.rotate(
        KID,
        KID[::-1],
        head,
        DIGEST_A,
        evidence,
        "PLANNED_ROTATION",
    )

    assert activated.head.act_id == activated_id
    assert activated.decided_at_us == 101
    assert rotated.head.act_id == rotated_id
    assert rotated.old_verification_end_us == 303
    assert connection.executions[0][1] == (
        KID,
        None,
        None,
        DIGEST_A,
        DIGEST_B,
        DIGEST_C,
        "INITIAL_ACTIVATION",
    )
    assert connection.executions[1][1] == (
        KID,
        KID[::-1],
        head.act_id,
        head.act_digest,
        DIGEST_A,
        DIGEST_B,
        DIGEST_C,
        "PLANNED_ROTATION",
    )


def test_close_revoke_and_resume_keep_database_incident_identity():
    close_head_id = uuid4()
    revoke_head_id = uuid4()
    resume_head_id = uuid4()
    incident_id = uuid4()
    close_receipt_id = uuid4()
    expected = _head()
    evidence = _evidence()
    connection = Connection(
        [
            [
                (
                    close_head_id,
                    DIGEST_A,
                    incident_id,
                    close_receipt_id,
                    101,
                )
            ],
            [(revoke_head_id, DIGEST_B, 202)],
            [(resume_head_id, DIGEST_C, 303)],
        ]
    )
    controller = TenantCapabilityKeyController(Factory(connection))

    closed = controller.close_admission(
        expected,
        KID,
        evidence,
        "ROTATION_HANDOFF",
    )
    revoked = controller.revoke(
        KID,
        closed.head,
        incident_id,
        close_receipt_id,
        evidence,
        "ROTATION_HANDOFF",
    )
    resumed = controller.resume(
        revoked.head,
        incident_id,
        close_receipt_id,
        evidence,
        "ROTATION_HANDOFF",
    )

    assert closed.incident_id == incident_id
    assert closed.close_receipt_id == close_receipt_id
    assert revoked.head.act_id == revoke_head_id
    assert resumed.head.act_id == resume_head_id
    assert connection.executions[1][1][3:5] == (
        incident_id,
        close_receipt_id,
    )
    assert connection.executions[2][1][2:4] == (
        incident_id,
        close_receipt_id,
    )


def test_projection_rebuild_maps_counts_without_lifecycle_logic():
    connection = Connection([[(2, 1)]])
    result = TenantCapabilityKeyController(
        Factory(connection)
    ).rebuild_projection()

    assert result.deleted_projection_rows == 2
    assert result.upserted_projection_rows == 1
    assert connection.executions[0][1] == ()


def test_autocommit_is_refused_before_key_control_statement():
    connection = Connection([], autocommit=True)

    with pytest.raises(KeyControlError):
        TenantCapabilityKeyController(Factory(connection)).rebuild_projection()

    assert connection.executions == []


@pytest.mark.parametrize(
    "exit_error",
    [None, psycopg.OperationalError("commit result lost")],
)
def test_connection_or_commit_failure_after_submission_is_unknown(exit_error):
    connection = Connection(
        [],
        fail_at=1 if exit_error is None else None,
        failure=psycopg.OperationalError("connection lost"),
        exit_error=exit_error,
    )

    with pytest.raises(KeyControlOutcomeUnknown) as raised:
        TenantCapabilityKeyController(
            Factory(connection)
        ).rebuild_projection()

    assert raised.value.operation == "REBUILD"


def test_deterministic_database_refusal_is_not_unknown():
    connection = Connection(
        [],
        fail_at=1,
        failure=psycopg.errors.CheckViolation("refused"),
    )

    with pytest.raises(KeyControlError) as raised:
        TenantCapabilityKeyController(
            Factory(connection)
        ).rebuild_projection()

    assert not isinstance(raised.value, KeyControlOutcomeUnknown)
