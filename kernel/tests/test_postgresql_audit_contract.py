"""Golden tests for the non-I/O PostgreSQL security-audit contract."""

from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError, replace

import pytest

from deployment.postgresql.audit_contract import (
    ACCESS_INTENT_EXPIRY_SECONDS,
    APPEND_TRANSACTION_ISOLATION,
    APPEND_INPUT_FINGERPRINT_ALGORITHM,
    APPEND_INPUT_FINGERPRINT_DOMAIN,
    APPEND_INPUT_FINGERPRINT_FRAMING,
    APPEND_INPUT_FINGERPRINT_LENGTH_BYTES,
    AUTHENTICATION_REASONS,
    CORRELATION_HMAC_ALGORITHM,
    CORRELATION_HMAC_DOMAIN,
    CORRELATION_HMAC_KEY_VERSION,
    CORRELATION_HMAC_LENGTH_BYTES,
    EVENT_FORMAT_IDENTITY,
    EVENT_IDENTITY_LOCK_STRIPES,
    EVENT_IDENTITY_SERIALIZATION_IDENTITY,
    EVENT_KINDS,
    EVENT_MAX_INPUT_BYTES,
    EXPORT_ACCESS_PURPOSE_IDENTITY,
    EXPORT_FUNCTION_IDENTITY,
    EXPORT_MAX_BYTES,
    EXPORT_MAX_ROWS,
    OVERFLOW_EXACT_RECEIPT_SLOTS_PER_PRODUCER,
    OVERFLOW_IDENTITY_OUTCOME_IDENTITY,
    PURGE_BATCH_ROWS,
    QUERY_ACCESS_PURPOSE_IDENTITY,
    QUERY_FUNCTION_IDENTITY,
    QUERY_MAX_BYTES,
    QUERY_MAX_ROWS,
    QUOTA_ACCEPTED_EVENT_THRESHOLD,
    QUOTA_BUCKET_SECONDS,
    REDACTION_POLICY_IDENTITY,
    REQUEST_ROUTER_REASONS,
    RETENTION_DAYS,
    RETENTION_POLICY_IDENTITY,
    RETENTION_SECONDS,
    SECURITY_AUDIT_CONTRACT,
    SECURITY_AUDIT_CONTRACT_DIGEST_POLICY,
    STRUCTURAL_COMPATIBILITY_OWNER,
    SecurityAuditContractError,
    validate_security_audit_contract,
)


def test_reason_matrix_event_kinds_and_policy_identities_are_exact():
    assert AUTHENTICATION_REASONS == (
        "CREDENTIAL_MISSING",
        "CREDENTIAL_MALFORMED",
        "VERIFIER_UNAVAILABLE",
        "VERIFICATION_REFUSED",
        "PRINCIPAL_BINDING_REFUSED",
        "TENANT_PARTY_PIN_REFUSED",
        "CAPABILITY_REFUSED",
    )
    assert REQUEST_ROUTER_REASONS == (
        "SECURITY_ROUTE_REFUSED",
        "CAPABILITY_REFUSED",
        "BINDER_REFUSED",
        "ACTOR_BINDING_REFUSED",
    )
    assert EVENT_KINDS == (
        "PRE_TENANT_FAILURE",
        "AUDIT_ACCESS",
        "AUDIT_RETENTION",
        "AUDIT_GAP",
        "OVERFLOW_STARTED",
        "OVERFLOW_ENDED",
    )
    assert EVENT_FORMAT_IDENTITY == "OFARM_PRETENANT_SECURITY_EVENT_V1"
    assert REDACTION_POLICY_IDENTITY == "CORRELATION_HMAC_ONLY_V1"
    assert RETENTION_POLICY_IDENTITY == "SECURITY_DIAGNOSTIC_30D_V1"

    assert [entry.manifest() for entry in SECURITY_AUDIT_CONTRACT.reason_matrix] == [
        {
            "sessionUser": "ofarm_security_authentication_producer_login",
            "producer": "AUTHENTICATION_BOUNDARY_V1",
            "component": "AUTHENTICATION",
            "reasons": list(AUTHENTICATION_REASONS),
        },
        {
            "sessionUser": "ofarm_security_request_router_producer_login",
            "producer": "REQUEST_ROUTER_BOUNDARY_V1",
            "component": "REQUEST_ROUTER",
            "reasons": list(REQUEST_ROUTER_REASONS),
        },
    ]


def test_digest_and_resource_bounds_are_exact():
    assert (
        CORRELATION_HMAC_ALGORITHM,
        CORRELATION_HMAC_LENGTH_BYTES,
        CORRELATION_HMAC_DOMAIN,
        CORRELATION_HMAC_KEY_VERSION,
    ) == (
        "HMAC-SHA-256",
        32,
        "OFARM_PRETENANT_CORRELATION_V1",
        1,
    )
    assert (
        APPEND_INPUT_FINGERPRINT_ALGORITHM,
        APPEND_INPUT_FINGERPRINT_LENGTH_BYTES,
        APPEND_INPUT_FINGERPRINT_FRAMING,
        APPEND_INPUT_FINGERPRINT_DOMAIN,
    ) == (
        "SHA-256",
        32,
        "PRESENCE_U8_LP32_BE",
        "OFARM_PRETENANT_APPEND_INPUT_FINGERPRINT_V1",
    )
    assert (RETENTION_DAYS, RETENTION_SECONDS) == (30, 2_592_000)
    assert (QUOTA_BUCKET_SECONDS, QUOTA_ACCEPTED_EVENT_THRESHOLD) == (60, 1_024)
    assert (
        EVENT_IDENTITY_SERIALIZATION_IDENTITY,
        EVENT_IDENTITY_LOCK_STRIPES,
        APPEND_TRANSACTION_ISOLATION,
        OVERFLOW_IDENTITY_OUTCOME_IDENTITY,
        OVERFLOW_EXACT_RECEIPT_SLOTS_PER_PRODUCER,
    ) == (
        "SHA256_UUID_SEND_FIRST_OCTET_FIXED_ROW_MUTEX_V1",
        256,
        "READ_COMMITTED",
        "FIXED_RECEIPT_OR_COUNT_UNKNOWN_V1",
        256,
    )
    assert EVENT_MAX_INPUT_BYTES == 4_096
    assert PURGE_BATCH_ROWS == 1_024
    assert ACCESS_INTENT_EXPIRY_SECONDS == 300
    assert (QUERY_MAX_ROWS, QUERY_MAX_BYTES) == (256, 1_048_576)
    assert (EXPORT_MAX_ROWS, EXPORT_MAX_BYTES) == (2_048, 8_388_608)
    assert [
        protocol.manifest()
        for protocol in SECURITY_AUDIT_CONTRACT.access_protocols
    ] == [
        {
            "purposeIdentity": QUERY_ACCESS_PURPOSE_IDENTITY,
            "functionIdentity": QUERY_FUNCTION_IDENTITY,
            "resultLimit": {"maxRows": 256, "maxBytes": 1_048_576},
        },
        {
            "purposeIdentity": EXPORT_ACCESS_PURPOSE_IDENTITY,
            "functionIdentity": EXPORT_FUNCTION_IDENTITY,
            "resultLimit": {"maxRows": 2_048, "maxBytes": 8_388_608},
        },
    ]


def test_public_function_identities_and_capability_grants_are_exact():
    functions = SECURITY_AUDIT_CONTRACT.public_functions
    expected = {
        "ofarm_security.append_pretenant_failure(uuid, text, bytea, text, integer)":
            "ofarm_security_audit_ingest",
        (
            "ofarm_security.commit_audit_access_intent(text, text, "
            "timestamptz, uuid, integer, bigint)"
        ):
            "ofarm_security_audit_control",
        "ofarm_security.append_audit_gap(timestamptz, timestamptz, bigint, boolean)":
            "ofarm_security_audit_control",
        "ofarm_security.mark_overflow_count_unknown(text, text, timestamptz)":
            "ofarm_security_audit_control",
        "ofarm_security.close_overflow_bucket(text, text, timestamptz)":
            "ofarm_security_audit_control",
        (
            "ofarm_security.query_operational_security_events("
            "uuid, timestamptz, uuid, integer, bigint)"
        ):
            "ofarm_security_audit_reader",
        (
            "ofarm_security.export_operational_security_events("
            "uuid, timestamptz, uuid, integer, bigint)"
        ):
            "ofarm_security_audit_export",
        "ofarm_security.purge_expired_operational_security_events()":
            "ofarm_security_audit_retention",
        "ofarm_security.observe_security_audit_contract()":
            "ofarm_security_audit_readiness",
        "ofarm_security.verify_security_audit_structure()":
            "ofarm_security_audit_readiness",
    }
    assert {function.identity: function.capability_role for function in functions} == \
        expected
    assert all(function.schema_name == "ofarm_security" for function in functions)

    manifest = SECURITY_AUDIT_CONTRACT.manifest_without_digest()
    grants = {
        grant["role"]: tuple(grant["executeFunctionIdentities"])
        for grant in manifest["capabilityGrants"]
    }
    assert set(grants) == set(expected.values())
    assert {
        identity for identities in grants.values() for identity in identities
    } == set(expected)
    assert all(
        grant["relationPrivileges"] == []
        for grant in manifest["capabilityGrants"]
    )
    assert all(
        function["publicRoleExecute"] is False
        for function in manifest["publicFunctions"]
    )
    assert manifest["derivationPosture"] == {
        "producerAndComponent": "EXACT_SESSION_USER_MAP",
        "observedAt": "EVENT_WRITER_LOCK_THEN_DATABASE_CLOCK",
        "purgeAfter": "OBSERVED_AT_PLUS_RETENTION",
        "accessDataCut": "DATABASE_CLOCK_AND_TOP_LEVEL_XID8_PG_SNAPSHOT",
        "accessVisibility": "PERSISTED_PG_SNAPSHOT",
        "accessClock": (
            "FUNCTION_SCOPED_SESSION_ADVISORY_LOCKED_"
            "NONTRANSACTIONAL_SEQUENCE_HIGH_WATER_V2"
        ),
        "accessExpiresAt": (
            "ACCESS_DATA_CUT_PLUS_EXPIRY_COMPARED_TO_CLOCK_HIGH_WATER"
        ),
        "accessClockRollback": "FAIL_CLOSED_AFTER_OBSERVATION",
        "accessClockTrustedPrerequisite": (
            "DATABASE_WALL_CLOCK_MONOTONIC_BETWEEN_"
            "ACCESS_PROTOCOL_OBSERVATIONS"
        ),
        "overflowClosure": "EVENT_WRITER_BARRIER_THROUGH_CLOSE_COMMIT",
    }
    assert manifest["eventIdentitySerialization"] == {
        "identity": "SHA256_UUID_SEND_FIRST_OCTET_FIXED_ROW_MUTEX_V1",
        "lockStripes": 256,
        "transactionIsolation": "READ_COMMITTED",
        "overflowOutcomeIdentity": "FIXED_RECEIPT_OR_COUNT_UNKNOWN_V1",
        "exactReceiptSlotsPerProducer": 256,
    }


def test_break_glass_login_is_absent_in_normal_structural_state():
    posture = SECURITY_AUDIT_CONTRACT.break_glass

    assert posture.capability_role == "ofarm_security_audit_export"
    assert posture.login_role == "ofarm_security_audit_export_login"
    assert posture.normal_state == "LOGIN_ABSENT"
    assert posture.normal_login_present is False
    assert posture.temporary_state == "STRUCTURALLY_INCOMPATIBLE"
    assert posture.structurally_compatible_while_temporary_login_present is False
    assert posture.dual_approval_required is True
    assert posture.time_bounded_login_required is True


def test_contract_exposes_only_issue_174_structural_compatibility():
    manifest = SECURITY_AUDIT_CONTRACT.manifest_without_digest()

    assert STRUCTURAL_COMPATIBILITY_OWNER == "ISSUE_174"
    assert manifest["structuralCompatibility"] == {"owner": "ISSUE_174"}
    canonical = SECURITY_AUDIT_CONTRACT.canonical_manifest_bytes().decode("ascii")
    assert "runtime_ready" not in canonical
    assert "runtimeReady" not in canonical
    assert "runtimeOwner" not in canonical


def test_manifest_is_canonical_ascii_and_has_domain_separated_golden_digest():
    contract = SECURITY_AUDIT_CONTRACT
    without_digest = contract.canonical_manifest_without_digest_bytes()
    canonical = contract.canonical_manifest_bytes()

    assert without_digest.endswith(b"\n")
    assert canonical.endswith(b"\n")
    without_digest.decode("ascii")
    canonical.decode("ascii")
    assert json.loads(without_digest) == contract.manifest_without_digest()
    assert json.loads(canonical) == contract.manifest()
    assert contract.digest == \
        "sha256:013b5e00232c86f6ef9824c98184c18b899a412305151ee31eb9991a633dc8db"
    assert contract.digest == "sha256:" + hashlib.sha256(
        SECURITY_AUDIT_CONTRACT_DIGEST_POLICY.encode("ascii")
        + b"\x00"
        + without_digest
    ).hexdigest()
    assert contract.digest != "sha256:" + hashlib.sha256(without_digest).hexdigest()


def test_contract_dataclasses_are_frozen():
    with pytest.raises(FrozenInstanceError):
        SECURITY_AUDIT_CONTRACT.retention_days = 31
    with pytest.raises(FrozenInstanceError):
        SECURITY_AUDIT_CONTRACT.public_functions[0].function_name = "changed"


def _replace_reason(**changes):
    contract = SECURITY_AUDIT_CONTRACT
    return replace(
        contract,
        reason_matrix=(replace(contract.reason_matrix[0], **changes),)
        + contract.reason_matrix[1:],
    )


def _replace_hmac(**changes):
    contract = SECURITY_AUDIT_CONTRACT
    return replace(
        contract,
        correlation_hmac=replace(contract.correlation_hmac, **changes),
    )


def _replace_fingerprint(**changes):
    contract = SECURITY_AUDIT_CONTRACT
    return replace(
        contract,
        append_input_fingerprint=replace(contract.append_input_fingerprint, **changes),
    )


def _replace_function(**changes):
    contract = SECURITY_AUDIT_CONTRACT
    return replace(
        contract,
        public_functions=(replace(contract.public_functions[0], **changes),)
        + contract.public_functions[1:],
    )


def _replace_access_protocol(**changes):
    contract = SECURITY_AUDIT_CONTRACT
    return replace(
        contract,
        access_protocols=(replace(contract.access_protocols[0], **changes),)
        + contract.access_protocols[1:],
    )


def _replace_break_glass(**changes):
    contract = SECURITY_AUDIT_CONTRACT
    return replace(contract, break_glass=replace(contract.break_glass, **changes))


@pytest.mark.parametrize(
    "mutate",
    (
        lambda value: replace(value, identity="ofarm.changed.v1"),
        lambda value: replace(value, schema_name="other_schema"),
        lambda value: replace(value, owner_role="other_owner"),
        lambda value: _replace_reason(session_user="other_login"),
        lambda value: _replace_reason(producer="OTHER_PRODUCER_V1"),
        lambda value: _replace_reason(component="OTHER_COMPONENT"),
        lambda value: _replace_reason(reasons=("CREDENTIAL_MISSING",)),
        lambda value: replace(value, reason_matrix=value.reason_matrix[:1]),
        lambda value: replace(value, event_kinds=value.event_kinds[:-1]),
        lambda value: replace(value, event_format_identity="OTHER_EVENT_V1"),
        lambda value: _replace_hmac(algorithm="HMAC-SHA-512"),
        lambda value: _replace_hmac(length_bytes=64),
        lambda value: _replace_hmac(domain="OTHER_HMAC_DOMAIN_V1"),
        lambda value: _replace_hmac(key_version=2),
        lambda value: _replace_hmac(framing="LP32_BE"),
        lambda value: _replace_fingerprint(algorithm="SHA-512"),
        lambda value: _replace_fingerprint(length_bytes=64),
        lambda value: _replace_fingerprint(domain="OTHER_FINGERPRINT_DOMAIN_V1"),
        lambda value: _replace_fingerprint(framing="LP64_BE"),
        lambda value: _replace_fingerprint(key_version=1),
        lambda value: replace(
            value,
            event_identity_serialization_identity="OTHER_MUTEX_V1",
        ),
        lambda value: replace(value, event_identity_lock_stripes=255),
        lambda value: replace(
            value, append_transaction_isolation="SERIALIZABLE"
        ),
        lambda value: replace(
            value,
            overflow_identity_outcome_identity="OTHER_OUTCOME_V1",
        ),
        lambda value: replace(
            value,
            overflow_exact_receipt_slots_per_producer=255,
        ),
        lambda value: replace(value, redaction_policy_identity="OTHER_REDACTION_V1"),
        lambda value: replace(value, retention_policy_identity="OTHER_RETENTION_V1"),
        lambda value: replace(value, retention_days=31),
        lambda value: replace(value, retention_seconds=1),
        lambda value: replace(value, quota_bucket_seconds=61),
        lambda value: replace(value, quota_accepted_event_threshold=1_025),
        lambda value: replace(value, event_max_input_bytes=4_097),
        lambda value: replace(value, purge_batch_rows=1_025),
        lambda value: replace(value, access_intent_expiry_seconds=301),
        lambda value: replace(
            value, query_limit=replace(value.query_limit, max_rows=257)
        ),
        lambda value: replace(
            value, query_limit=replace(value.query_limit, max_bytes=1)
        ),
        lambda value: replace(
            value, export_limit=replace(value.export_limit, max_rows=2_049)
        ),
        lambda value: replace(
            value, export_limit=replace(value.export_limit, max_bytes=1)
        ),
        lambda value: _replace_access_protocol(purpose_identity="OTHER_PURPOSE_V1"),
        lambda value: _replace_access_protocol(function_identity=EXPORT_FUNCTION_IDENTITY),
        lambda value: _replace_access_protocol(
            result_limit=replace(value.access_protocols[0].result_limit, max_rows=1)
        ),
        lambda value: replace(value, access_protocols=value.access_protocols[::-1]),
        lambda value: _replace_function(schema_name="other_schema"),
        lambda value: _replace_function(function_name="other_function"),
        lambda value: _replace_function(argument_types=("uuid",)),
        lambda value: _replace_function(result_shape="pg_catalog.void"),
        lambda value: _replace_function(capability_role="other_role"),
        lambda value: replace(value, public_functions=value.public_functions[::-1]),
        lambda value: _replace_break_glass(capability_role="other_role"),
        lambda value: _replace_break_glass(login_role="other_login"),
        lambda value: _replace_break_glass(normal_state="LOGIN_PRESENT"),
        lambda value: _replace_break_glass(temporary_state="COMPATIBLE"),
        lambda value: _replace_break_glass(normal_login_present=True),
        lambda value: _replace_break_glass(
            structurally_compatible_while_temporary_login_present=True
        ),
        lambda value: _replace_break_glass(dual_approval_required=False),
        lambda value: _replace_break_glass(time_bounded_login_required=False),
        lambda value: replace(value, reason_matrix=(None,)),
        lambda value: replace(value, event_kinds=(None,)),
        lambda value: replace(value, correlation_hmac=None),
        lambda value: replace(value, append_input_fingerprint=None),
        lambda value: replace(value, query_limit=None),
        lambda value: replace(value, export_limit=None),
        lambda value: replace(value, access_protocols=(None,)),
        lambda value: replace(value, public_functions=(None,)),
        lambda value: replace(value, break_glass=None),
    ),
)
def test_exhaustive_validation_refuses_every_contract_change(mutate):
    with pytest.raises(SecurityAuditContractError):
        validate_security_audit_contract(mutate(SECURITY_AUDIT_CONTRACT))


@pytest.mark.parametrize(
    "invalid",
    (None, object(), {}, "ofarm.security-audit-database-contract.v1"),
)
def test_validation_refuses_non_contract_values(invalid):
    with pytest.raises(SecurityAuditContractError, match="wrong type"):
        validate_security_audit_contract(invalid)
