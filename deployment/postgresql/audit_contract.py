"""Immutable PostgreSQL security-audit database contract for issue #174.

This module performs no I/O.  It gives the first audit migration and later
structural verification one checked-in source for every closed V1 reason,
event kind, policy, resource bound, callable identity, and break-glass posture.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass


SECURITY_AUDIT_CONTRACT_DIGEST_POLICY = \
    "OFARM_POSTGRESQL_SECURITY_AUDIT_CONTRACT_V1"
_CONTRACT_DIGEST_DOMAIN = \
    SECURITY_AUDIT_CONTRACT_DIGEST_POLICY.encode("ascii") + b"\x00"

EVENT_FORMAT_IDENTITY = "OFARM_PRETENANT_SECURITY_EVENT_V1"
CORRELATION_HMAC_ALGORITHM = "HMAC-SHA-256"
CORRELATION_HMAC_LENGTH_BYTES = 32
CORRELATION_HMAC_DOMAIN = "OFARM_PRETENANT_CORRELATION_V1"
CORRELATION_HMAC_KEY_VERSION = 2
CORRELATION_HMAC_KNOWN_KEY_VERSIONS = (1, 2)
APPEND_INPUT_FINGERPRINT_ALGORITHM = "SHA-256"
APPEND_INPUT_FINGERPRINT_LENGTH_BYTES = 32
APPEND_INPUT_FINGERPRINT_FRAMING = "PRESENCE_U8_LP32_BE"
APPEND_INPUT_FINGERPRINT_DOMAIN = \
    "OFARM_PRETENANT_APPEND_INPUT_FINGERPRINT_V1"
EVENT_IDENTITY_SERIALIZATION_IDENTITY = \
    "SHA256_UUID_SEND_FIRST_OCTET_FIXED_ROW_MUTEX_V1"
EVENT_IDENTITY_LOCK_STRIPES = 256
APPEND_TRANSACTION_ISOLATION = "READ_COMMITTED"
OVERFLOW_IDENTITY_OUTCOME_IDENTITY = \
    "FIXED_RECEIPT_OR_COUNT_UNKNOWN_V1"
OVERFLOW_EXACT_RECEIPT_SLOTS_PER_PRODUCER = 256
REDACTION_POLICY_IDENTITY = "CORRELATION_HMAC_ONLY_V1"
RETENTION_POLICY_IDENTITY = "SECURITY_DIAGNOSTIC_30D_V1"

AUTHENTICATION_REASONS = (
    "CREDENTIAL_MISSING",
    "CREDENTIAL_MALFORMED",
    "VERIFIER_UNAVAILABLE",
    "VERIFICATION_REFUSED",
    "PRINCIPAL_BINDING_REFUSED",
    "TENANT_PARTY_PIN_REFUSED",
    "CAPABILITY_REFUSED",
)
REQUEST_ROUTER_REASONS = (
    "SECURITY_ROUTE_REFUSED",
    "CAPABILITY_REFUSED",
    "BINDER_REFUSED",
    "ACTOR_BINDING_REFUSED",
)
EVENT_KINDS = (
    "PRE_TENANT_FAILURE",
    "AUDIT_ACCESS",
    "AUDIT_RETENTION",
    "AUDIT_GAP",
    "OVERFLOW_STARTED",
    "OVERFLOW_ENDED",
)

RETENTION_DAYS = 30
RETENTION_SECONDS = 2_592_000
QUOTA_BUCKET_SECONDS = 60
QUOTA_ACCEPTED_EVENT_THRESHOLD = 1_024
EVENT_MAX_INPUT_BYTES = 4_096
PURGE_BATCH_ROWS = 1_024
ACCESS_INTENT_EXPIRY_SECONDS = 300
QUERY_ACCESS_PURPOSE_IDENTITY = "OPERATIONAL_DIAGNOSTIC_QUERY_V1"
QUERY_FUNCTION_IDENTITY = (
    "ofarm_security.query_operational_security_events"
    "(uuid, timestamptz, uuid, integer, bigint)"
)
QUERY_MAX_ROWS = 256
QUERY_MAX_BYTES = 1_048_576
EXPORT_ACCESS_PURPOSE_IDENTITY = "DUAL_APPROVED_BREAK_GLASS_EXPORT_V1"
EXPORT_FUNCTION_IDENTITY = (
    "ofarm_security.export_operational_security_events"
    "(uuid, timestamptz, uuid, integer, bigint)"
)
EXPORT_MAX_ROWS = 2_048
EXPORT_MAX_BYTES = 8_388_608

STRUCTURAL_COMPATIBILITY_OWNER = "ISSUE_174"

_POSTGRES_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,62}")
_CLOSED_TOKEN = re.compile(r"[A-Z][A-Z0-9_]*")
_ALLOWED_ARGUMENT_TYPES = frozenset(
    {"bigint", "boolean", "bytea", "integer", "text", "timestamptz", "uuid"}
)


class SecurityAuditContractError(ValueError):
    """The checked-in security-audit contract is incomplete or changed."""


@dataclass(frozen=True, slots=True)
class ProducerReasonSpec:
    """One provisioned producer and its complete pre-tenant reason allowlist."""

    session_user: str
    producer: str
    component: str
    reasons: tuple[str, ...]

    def manifest(self) -> dict[str, object]:
        return {
            "sessionUser": self.session_user,
            "producer": self.producer,
            "component": self.component,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class DigestSpec:
    """One exact fixed-length digest policy."""

    algorithm: str
    length_bytes: int
    domain: str
    framing: str | None = None
    key_version: int | None = None

    def manifest(self) -> dict[str, object]:
        value: dict[str, object] = {
            "algorithm": self.algorithm,
            "lengthBytes": self.length_bytes,
            "domain": self.domain,
        }
        if self.framing is not None:
            value["framing"] = self.framing
        if self.key_version is not None:
            value["keyVersion"] = self.key_version
        return value


@dataclass(frozen=True, slots=True)
class ResultLimitSpec:
    """One database-enforced row and encoded-byte result ceiling."""

    max_rows: int
    max_bytes: int

    def manifest(self) -> dict[str, int]:
        return {"maxRows": self.max_rows, "maxBytes": self.max_bytes}


@dataclass(frozen=True, slots=True)
class AccessProtocolSpec:
    """One exact precommitted access purpose, function, and result ceiling."""

    purpose_identity: str
    function_identity: str
    result_limit: ResultLimitSpec

    def manifest(self) -> dict[str, object]:
        return {
            "purposeIdentity": self.purpose_identity,
            "functionIdentity": self.function_identity,
            "resultLimit": self.result_limit.manifest(),
        }


@dataclass(frozen=True, slots=True)
class PublicFunctionSpec:
    """One schema-qualified callable identity and its sole capability grant."""

    schema_name: str
    function_name: str
    argument_types: tuple[str, ...]
    result_shape: str
    capability_role: str

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.function_name}"

    @property
    def identity_arguments(self) -> str:
        return ", ".join(self.argument_types)

    @property
    def identity(self) -> str:
        return f"{self.qualified_name}({self.identity_arguments})"

    def manifest(self) -> dict[str, object]:
        return {
            "schema": self.schema_name,
            "name": self.function_name,
            "argumentTypes": list(self.argument_types),
            "identity": self.identity,
            "resultShape": self.result_shape,
            "executeCapabilityRole": self.capability_role,
            "publicRoleExecute": False,
        }


@dataclass(frozen=True, slots=True)
class BreakGlassSpec:
    """Normal and temporary posture for the separately created export login."""

    capability_role: str
    login_role: str
    normal_state: str
    temporary_state: str
    normal_login_present: bool
    structurally_compatible_while_temporary_login_present: bool
    dual_approval_required: bool
    time_bounded_login_required: bool

    def manifest(self) -> dict[str, object]:
        return {
            "capabilityRole": self.capability_role,
            "loginRole": self.login_role,
            "normalState": self.normal_state,
            "temporaryState": self.temporary_state,
            "normalLoginPresent": self.normal_login_present,
            "structurallyCompatibleWhileTemporaryLoginPresent": (
                self.structurally_compatible_while_temporary_login_present
            ),
            "dualApprovalRequired": self.dual_approval_required,
            "timeBoundedLoginRequired": self.time_bounded_login_required,
        }


@dataclass(frozen=True, slots=True)
class SecurityAuditContract:
    """The complete migration-owned, non-I/O V1 security-audit contract."""

    identity: str
    schema_name: str
    owner_role: str
    reason_matrix: tuple[ProducerReasonSpec, ...]
    event_kinds: tuple[str, ...]
    event_format_identity: str
    correlation_hmac: DigestSpec
    correlation_hmac_known_key_versions: tuple[int, ...]
    append_input_fingerprint: DigestSpec
    event_identity_serialization_identity: str
    event_identity_lock_stripes: int
    append_transaction_isolation: str
    overflow_identity_outcome_identity: str
    overflow_exact_receipt_slots_per_producer: int
    redaction_policy_identity: str
    retention_policy_identity: str
    retention_days: int
    retention_seconds: int
    quota_bucket_seconds: int
    quota_accepted_event_threshold: int
    event_max_input_bytes: int
    purge_batch_rows: int
    access_intent_expiry_seconds: int
    query_limit: ResultLimitSpec
    export_limit: ResultLimitSpec
    access_protocols: tuple[AccessProtocolSpec, ...]
    public_functions: tuple[PublicFunctionSpec, ...]
    break_glass: BreakGlassSpec

    def manifest_without_digest(self) -> dict[str, object]:
        capability_roles = tuple(
            dict.fromkeys(
                function.capability_role for function in self.public_functions
            )
        )
        return {
            "schemaVersion": "ofarm.postgresql-security-audit-contract.v1",
            "digestPolicy": SECURITY_AUDIT_CONTRACT_DIGEST_POLICY,
            "identity": self.identity,
            "schema": {"name": self.schema_name, "owner": self.owner_role},
            "reasonMatrix": [entry.manifest() for entry in self.reason_matrix],
            "eventKinds": list(self.event_kinds),
            "eventFormatIdentity": self.event_format_identity,
            "correlationHmac": self.correlation_hmac.manifest(),
            "correlationHmacKnownKeyVersions": list(
                self.correlation_hmac_known_key_versions
            ),
            "appendInputFingerprint": self.append_input_fingerprint.manifest(),
            "eventIdentitySerialization": {
                "identity": self.event_identity_serialization_identity,
                "lockStripes": self.event_identity_lock_stripes,
                "transactionIsolation": self.append_transaction_isolation,
                "overflowOutcomeIdentity": (
                    self.overflow_identity_outcome_identity
                ),
                "exactReceiptSlotsPerProducer": (
                    self.overflow_exact_receipt_slots_per_producer
                ),
            },
            "policies": {
                "redaction": self.redaction_policy_identity,
                "retention": self.retention_policy_identity,
            },
            "derivationPosture": {
                "producerAndComponent": "EXACT_SESSION_USER_MAP",
                "observedAt": (
                    "EVENT_WRITER_LOCK_THEN_DATABASE_CLOCK"
                ),
                "purgeAfter": "OBSERVED_AT_PLUS_RETENTION",
                "accessDataCut": (
                    "DATABASE_CLOCK_AND_TOP_LEVEL_XID8_PG_SNAPSHOT"
                ),
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
                "overflowClosure": (
                    "EVENT_WRITER_BARRIER_THROUGH_CLOSE_COMMIT"
                ),
            },
            "limits": {
                "retention": {
                    "days": self.retention_days,
                    "seconds": self.retention_seconds,
                },
                "quota": {
                    "bucketSeconds": self.quota_bucket_seconds,
                    "acceptedEventThreshold": (
                        self.quota_accepted_event_threshold
                    ),
                },
                "eventMaxInputBytes": self.event_max_input_bytes,
                "purgeBatchRows": self.purge_batch_rows,
                "accessIntentExpirySeconds": self.access_intent_expiry_seconds,
                "query": self.query_limit.manifest(),
                "export": self.export_limit.manifest(),
            },
            "accessProtocols": [
                protocol.manifest() for protocol in self.access_protocols
            ],
            "publicFunctions": [
                function.manifest() for function in self.public_functions
            ],
            "capabilityGrants": [
                {
                    "role": role,
                    "executeFunctionIdentities": [
                        function.identity
                        for function in self.public_functions
                        if function.capability_role == role
                    ],
                    "relationPrivileges": [],
                }
                for role in capability_roles
            ],
            "structuralCompatibility": {
                "owner": STRUCTURAL_COMPATIBILITY_OWNER,
            },
            "breakGlassExport": self.break_glass.manifest(),
        }

    def canonical_manifest_without_digest_bytes(self) -> bytes:
        return _canonical_json(self.manifest_without_digest())

    @property
    def digest(self) -> str:
        source = (
            _CONTRACT_DIGEST_DOMAIN
            + self.canonical_manifest_without_digest_bytes()
        )
        return "sha256:" + hashlib.sha256(source).hexdigest()

    def manifest(self) -> dict[str, object]:
        value = self.manifest_without_digest()
        value["securityAuditContractDigest"] = self.digest
        return value

    def canonical_manifest_bytes(self) -> bytes:
        return _canonical_json(self.manifest())


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def _public_function(
    name: str,
    argument_types: tuple[str, ...],
    result_shape: str,
    capability_role: str,
) -> PublicFunctionSpec:
    return PublicFunctionSpec(
        schema_name="ofarm_security",
        function_name=name,
        argument_types=argument_types,
        result_shape=result_shape,
        capability_role=capability_role,
    )


def _expected_contract() -> SecurityAuditContract:
    return SecurityAuditContract(
        identity="ofarm.security-audit-database-contract.v1",
        schema_name="ofarm_security",
        owner_role="ofarm_security_audit_owner",
        reason_matrix=(
            ProducerReasonSpec(
                session_user="ofarm_security_authentication_producer_login",
                producer="AUTHENTICATION_BOUNDARY_V1",
                component="AUTHENTICATION",
                reasons=AUTHENTICATION_REASONS,
            ),
            ProducerReasonSpec(
                session_user="ofarm_security_request_router_producer_login",
                producer="REQUEST_ROUTER_BOUNDARY_V1",
                component="REQUEST_ROUTER",
                reasons=REQUEST_ROUTER_REASONS,
            ),
        ),
        event_kinds=EVENT_KINDS,
        event_format_identity=EVENT_FORMAT_IDENTITY,
        correlation_hmac=DigestSpec(
            algorithm=CORRELATION_HMAC_ALGORITHM,
            length_bytes=CORRELATION_HMAC_LENGTH_BYTES,
            domain=CORRELATION_HMAC_DOMAIN,
            key_version=CORRELATION_HMAC_KEY_VERSION,
        ),
        correlation_hmac_known_key_versions=(
            CORRELATION_HMAC_KNOWN_KEY_VERSIONS
        ),
        append_input_fingerprint=DigestSpec(
            algorithm=APPEND_INPUT_FINGERPRINT_ALGORITHM,
            length_bytes=APPEND_INPUT_FINGERPRINT_LENGTH_BYTES,
            domain=APPEND_INPUT_FINGERPRINT_DOMAIN,
            framing=APPEND_INPUT_FINGERPRINT_FRAMING,
        ),
        event_identity_serialization_identity=(
            EVENT_IDENTITY_SERIALIZATION_IDENTITY
        ),
        event_identity_lock_stripes=EVENT_IDENTITY_LOCK_STRIPES,
        append_transaction_isolation=APPEND_TRANSACTION_ISOLATION,
        overflow_identity_outcome_identity=(
            OVERFLOW_IDENTITY_OUTCOME_IDENTITY
        ),
        overflow_exact_receipt_slots_per_producer=(
            OVERFLOW_EXACT_RECEIPT_SLOTS_PER_PRODUCER
        ),
        redaction_policy_identity=REDACTION_POLICY_IDENTITY,
        retention_policy_identity=RETENTION_POLICY_IDENTITY,
        retention_days=RETENTION_DAYS,
        retention_seconds=RETENTION_SECONDS,
        quota_bucket_seconds=QUOTA_BUCKET_SECONDS,
        quota_accepted_event_threshold=QUOTA_ACCEPTED_EVENT_THRESHOLD,
        event_max_input_bytes=EVENT_MAX_INPUT_BYTES,
        purge_batch_rows=PURGE_BATCH_ROWS,
        access_intent_expiry_seconds=ACCESS_INTENT_EXPIRY_SECONDS,
        query_limit=ResultLimitSpec(QUERY_MAX_ROWS, QUERY_MAX_BYTES),
        export_limit=ResultLimitSpec(EXPORT_MAX_ROWS, EXPORT_MAX_BYTES),
        access_protocols=(
            AccessProtocolSpec(
                QUERY_ACCESS_PURPOSE_IDENTITY,
                QUERY_FUNCTION_IDENTITY,
                ResultLimitSpec(QUERY_MAX_ROWS, QUERY_MAX_BYTES),
            ),
            AccessProtocolSpec(
                EXPORT_ACCESS_PURPOSE_IDENTITY,
                EXPORT_FUNCTION_IDENTITY,
                ResultLimitSpec(EXPORT_MAX_ROWS, EXPORT_MAX_BYTES),
            ),
        ),
        public_functions=(
            _public_function(
                "append_pretenant_failure",
                ("uuid", "text", "bytea", "text", "integer"),
                "ofarm_security.append_pretenant_failure_result",
                "ofarm_security_audit_ingest",
            ),
            _public_function(
                "commit_audit_access_intent",
                ("text", "text", "timestamptz", "uuid", "integer", "bigint"),
                "ofarm_security.audit_access_intent_result",
                "ofarm_security_audit_control",
            ),
            _public_function(
                "append_audit_gap",
                ("timestamptz", "timestamptz", "bigint", "boolean"),
                "ofarm_security.operational_security_event_identity",
                "ofarm_security_audit_control",
            ),
            _public_function(
                "mark_overflow_count_unknown",
                ("text", "text", "timestamptz"),
                "pg_catalog.void",
                "ofarm_security_audit_control",
            ),
            _public_function(
                "close_overflow_bucket",
                ("text", "text", "timestamptz"),
                "ofarm_security.operational_security_event_identity",
                "ofarm_security_audit_control",
            ),
            _public_function(
                "query_operational_security_events",
                ("uuid", "timestamptz", "uuid", "integer", "bigint"),
                "SETOF ofarm_security.operational_security_event_report",
                "ofarm_security_audit_reader",
            ),
            _public_function(
                "export_operational_security_events",
                ("uuid", "timestamptz", "uuid", "integer", "bigint"),
                "SETOF ofarm_security.operational_security_event_report",
                "ofarm_security_audit_export",
            ),
            _public_function(
                "purge_expired_operational_security_events",
                (),
                "ofarm_security.audit_retention_result",
                "ofarm_security_audit_retention",
            ),
            _public_function(
                "observe_correlation_hmac_key_retention",
                ("integer",),
                (
                    "TABLE(key_version integer, active boolean, "
                    "greatest_purge_after timestamptz)"
                ),
                "ofarm_security_audit_control",
            ),
            _public_function(
                "observe_next_closeable_overflow_bucket",
                (),
                "TABLE(producer text, component text, bucket_start timestamptz)",
                "ofarm_security_audit_control",
            ),
            _public_function(
                "observe_security_audit_contract",
                (),
                "ofarm_security.security_audit_contract_observation",
                "ofarm_security_audit_readiness",
            ),
            _public_function(
                "verify_security_audit_structure",
                (),
                "ofarm_security.security_audit_structure_report",
                "ofarm_security_audit_readiness",
            ),
        ),
        break_glass=BreakGlassSpec(
            capability_role="ofarm_security_audit_export",
            login_role="ofarm_security_audit_export_login",
            normal_state="LOGIN_ABSENT",
            temporary_state="STRUCTURALLY_INCOMPATIBLE",
            normal_login_present=False,
            structurally_compatible_while_temporary_login_present=False,
            dual_approval_required=True,
            time_bounded_login_required=True,
        ),
    )


def _require_exact_int(value: object, label: str) -> None:
    if type(value) is not int or value <= 0:
        raise SecurityAuditContractError(f"{label} must be a positive integer")


def _validate_identifier(value: object, label: str) -> None:
    if not isinstance(value, str) or _POSTGRES_IDENTIFIER.fullmatch(value) is None:
        raise SecurityAuditContractError(
            f"{label} must be one closed PostgreSQL identifier"
        )


def validate_security_audit_contract(contract: SecurityAuditContract) -> None:
    """Refuse every incomplete, internally inconsistent, or changed contract."""

    if type(contract) is not SecurityAuditContract:
        raise SecurityAuditContractError("audit contract has the wrong type")
    if contract != _expected_contract():
        raise SecurityAuditContractError(
            "audit contract differs from the closed checked-in V1 contract"
        )

    _validate_identifier(contract.schema_name, "schema name")
    _validate_identifier(contract.owner_role, "owner role")
    if not contract.identity or not contract.identity.isascii():
        raise SecurityAuditContractError("contract identity must be non-empty ASCII")

    for label, value in (
        ("retention days", contract.retention_days),
        ("retention seconds", contract.retention_seconds),
        ("quota bucket seconds", contract.quota_bucket_seconds),
        ("quota threshold", contract.quota_accepted_event_threshold),
        ("event identity lock stripes", contract.event_identity_lock_stripes),
        (
            "overflow exact receipt slots per producer",
            contract.overflow_exact_receipt_slots_per_producer,
        ),
        ("event input bound", contract.event_max_input_bytes),
        ("purge batch", contract.purge_batch_rows),
        ("access expiry", contract.access_intent_expiry_seconds),
        ("query row bound", contract.query_limit.max_rows),
        ("query byte bound", contract.query_limit.max_bytes),
        ("export row bound", contract.export_limit.max_rows),
        ("export byte bound", contract.export_limit.max_bytes),
    ):
        _require_exact_int(value, label)
    if contract.retention_seconds != contract.retention_days * 24 * 60 * 60:
        raise SecurityAuditContractError("retention day and second bounds differ")
    if contract.event_identity_lock_stripes != 256 or \
            contract.overflow_exact_receipt_slots_per_producer != 256:
        raise SecurityAuditContractError(
            "event identity serialization bounds differ"
        )
    for label, value in (
        (
            "event identity serialization identity",
            contract.event_identity_serialization_identity,
        ),
        ("append transaction isolation", contract.append_transaction_isolation),
        (
            "overflow identity outcome identity",
            contract.overflow_identity_outcome_identity,
        ),
    ):
        if type(value) is not str or _CLOSED_TOKEN.fullmatch(value) is None:
            raise SecurityAuditContractError(f"{label} differs")
    if contract.query_limit.max_rows > contract.export_limit.max_rows or \
            contract.query_limit.max_bytes > contract.export_limit.max_bytes:
        raise SecurityAuditContractError("query limits must not exceed export limits")

    if len(contract.event_kinds) != len(set(contract.event_kinds)):
        raise SecurityAuditContractError("event kinds must be unique")
    if any(_CLOSED_TOKEN.fullmatch(value) is None for value in contract.event_kinds):
        raise SecurityAuditContractError("event kinds must be closed ASCII tokens")

    reason_components: set[str] = set()
    session_users: set[str] = set()
    for entry in contract.reason_matrix:
        _validate_identifier(entry.session_user, "producer session user")
        if entry.component in reason_components:
            raise SecurityAuditContractError("reason components must be unique")
        if entry.session_user in session_users:
            raise SecurityAuditContractError("producer session users must be unique")
        reason_components.add(entry.component)
        session_users.add(entry.session_user)
        if not entry.reasons or len(entry.reasons) != len(set(entry.reasons)):
            raise SecurityAuditContractError(
                "each producer must have a non-empty unique reason allowlist"
            )
        if _CLOSED_TOKEN.fullmatch(entry.producer) is None or \
                _CLOSED_TOKEN.fullmatch(entry.component) is None or any(
                    _CLOSED_TOKEN.fullmatch(reason) is None
                    for reason in entry.reasons
                ):
            raise SecurityAuditContractError(
                "producer, component, and reason values must be closed ASCII tokens"
            )

    for label, digest_spec in (
        ("correlation HMAC", contract.correlation_hmac),
        ("append fingerprint", contract.append_input_fingerprint),
    ):
        _require_exact_int(digest_spec.length_bytes, f"{label} byte length")
        if not digest_spec.algorithm or not digest_spec.algorithm.isascii() or \
                not digest_spec.domain or not digest_spec.domain.isascii():
            raise SecurityAuditContractError(
                f"{label} algorithm and domain must be non-empty ASCII"
            )
        if digest_spec.key_version is not None:
            _require_exact_int(digest_spec.key_version, f"{label} key version")
        if digest_spec.framing is not None and (
            not digest_spec.framing or not digest_spec.framing.isascii()
        ):
            raise SecurityAuditContractError(f"{label} framing must be ASCII")
    known_key_versions = contract.correlation_hmac_known_key_versions
    if not known_key_versions or len(known_key_versions) != len(
        set(known_key_versions)
    ):
        raise SecurityAuditContractError(
            "correlation HMAC key versions must be non-empty and unique"
        )
    for key_version in known_key_versions:
        _require_exact_int(key_version, "correlation HMAC known key version")
    if contract.correlation_hmac.key_version not in known_key_versions:
        raise SecurityAuditContractError(
            "active correlation HMAC key version must be known"
        )

    function_identities: set[str] = set()
    for function in contract.public_functions:
        _validate_identifier(function.schema_name, "function schema")
        _validate_identifier(function.function_name, "function name")
        _validate_identifier(function.capability_role, "function capability role")
        if function.schema_name != contract.schema_name:
            raise SecurityAuditContractError("public function uses another schema")
        if function.identity in function_identities:
            raise SecurityAuditContractError(
                "public function identities must be unique"
            )
        function_identities.add(function.identity)
        if any(
            argument_type not in _ALLOWED_ARGUMENT_TYPES
            for argument_type in function.argument_types
        ):
            raise SecurityAuditContractError("function uses an unclosed argument type")
        if not function.result_shape or not function.result_shape.isascii():
            raise SecurityAuditContractError("function result shape must be ASCII")

    for protocol in contract.access_protocols:
        if _CLOSED_TOKEN.fullmatch(protocol.purpose_identity) is None:
            raise SecurityAuditContractError(
                "access purpose identity must be a closed ASCII token"
            )
        if protocol.function_identity not in function_identities:
            raise SecurityAuditContractError(
                "access protocol must name one closed public function"
            )
        _require_exact_int(protocol.result_limit.max_rows, "access protocol rows")
        _require_exact_int(protocol.result_limit.max_bytes, "access protocol bytes")

    if _CLOSED_TOKEN.fullmatch(STRUCTURAL_COMPATIBILITY_OWNER) is None:
        raise SecurityAuditContractError(
            "structural compatibility owner must be a closed ASCII token"
        )

    _validate_identifier(contract.break_glass.capability_role, "break-glass role")
    _validate_identifier(contract.break_glass.login_role, "break-glass login")
    boolean_posture = (
        contract.break_glass.normal_login_present,
        contract.break_glass.structurally_compatible_while_temporary_login_present,
        contract.break_glass.dual_approval_required,
        contract.break_glass.time_bounded_login_required,
    )
    if any(type(value) is not bool for value in boolean_posture):
        raise SecurityAuditContractError("break-glass posture values must be boolean")

SECURITY_AUDIT_CONTRACT = _expected_contract()
validate_security_audit_contract(SECURITY_AUDIT_CONTRACT)


__all__ = (
    "ACCESS_INTENT_EXPIRY_SECONDS",
    "AccessProtocolSpec",
    "APPEND_INPUT_FINGERPRINT_ALGORITHM",
    "APPEND_INPUT_FINGERPRINT_DOMAIN",
    "APPEND_INPUT_FINGERPRINT_FRAMING",
    "APPEND_INPUT_FINGERPRINT_LENGTH_BYTES",
    "AUTHENTICATION_REASONS",
    "BreakGlassSpec",
    "CORRELATION_HMAC_ALGORITHM",
    "CORRELATION_HMAC_DOMAIN",
    "CORRELATION_HMAC_KEY_VERSION",
    "CORRELATION_HMAC_KNOWN_KEY_VERSIONS",
    "CORRELATION_HMAC_LENGTH_BYTES",
    "DigestSpec",
    "EVENT_FORMAT_IDENTITY",
    "EVENT_IDENTITY_LOCK_STRIPES",
    "EVENT_IDENTITY_SERIALIZATION_IDENTITY",
    "EVENT_KINDS",
    "EVENT_MAX_INPUT_BYTES",
    "EXPORT_MAX_BYTES",
    "EXPORT_MAX_ROWS",
    "EXPORT_ACCESS_PURPOSE_IDENTITY",
    "EXPORT_FUNCTION_IDENTITY",
    "ProducerReasonSpec",
    "PublicFunctionSpec",
    "PURGE_BATCH_ROWS",
    "QUERY_MAX_BYTES",
    "QUERY_MAX_ROWS",
    "QUERY_ACCESS_PURPOSE_IDENTITY",
    "QUERY_FUNCTION_IDENTITY",
    "QUOTA_ACCEPTED_EVENT_THRESHOLD",
    "QUOTA_BUCKET_SECONDS",
    "OVERFLOW_EXACT_RECEIPT_SLOTS_PER_PRODUCER",
    "OVERFLOW_IDENTITY_OUTCOME_IDENTITY",
    "REDACTION_POLICY_IDENTITY",
    "REQUEST_ROUTER_REASONS",
    "RETENTION_DAYS",
    "RETENTION_POLICY_IDENTITY",
    "RETENTION_SECONDS",
    "ResultLimitSpec",
    "SECURITY_AUDIT_CONTRACT",
    "SECURITY_AUDIT_CONTRACT_DIGEST_POLICY",
    "SecurityAuditContract",
    "SecurityAuditContractError",
    "STRUCTURAL_COMPATIBILITY_OWNER",
    "validate_security_audit_contract",
)
