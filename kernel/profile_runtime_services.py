"""Private, profile-neutral contracts for executable runtime services."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, TypedDict, runtime_checkable

from .profile_runtime import ProfileRuntimeDescriptor, ReferenceFamily
from .runtime_bundle import RuntimeBundle, RuntimeComponent


def _require_ref(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class MaterializationSpecification:
    """Profile-owned identities used by the generic materializer."""

    policy_ref: str
    default_result_shape_family: str
    identity_registry_result_shape_family: str

    def __post_init__(self) -> None:
        _require_ref(self.policy_ref, "materialization policy ref")
        _require_ref(
            self.default_result_shape_family,
            "default materialization result-shape family",
        )
        _require_ref(
            self.identity_registry_result_shape_family,
            "identity-registry result-shape family",
        )
        if (
            self.default_result_shape_family
            == self.identity_registry_result_shape_family
        ):
            raise ValueError(
                "materialization result-shape families must be distinct"
            )


@dataclass(frozen=True, slots=True)
class GovernedViewBinding:
    """One profile-owned view and its exact query identities."""

    view_ref: str
    query_specification_ref: str
    query_plan_ref: str

    def __post_init__(self) -> None:
        _require_ref(self.view_ref, "view ref")
        _require_ref(self.query_specification_ref, "query specification ref")
        _require_ref(self.query_plan_ref, "query plan ref")


@dataclass(frozen=True, slots=True)
class OutputSpecification:
    """Profile-owned identities and claims for the two current output surfaces."""

    passport_view: GovernedViewBinding
    document_assembly: GovernedViewBinding
    claim_statement: str
    freeze_rule_ref: str
    durable_artifact_prefix: str
    version_label_prefix: str

    def __post_init__(self) -> None:
        if type(self.passport_view) is not GovernedViewBinding:
            raise ValueError("passport view binding must use the trusted type")
        if type(self.document_assembly) is not GovernedViewBinding:
            raise ValueError(
                "document-assembly binding must use the trusted type"
            )
        if self.passport_view.view_ref == self.document_assembly.view_ref:
            raise ValueError("profile output view refs must be distinct")
        _require_ref(self.claim_statement, "output claim statement")
        _require_ref(self.freeze_rule_ref, "freeze rule ref")
        _require_ref(self.durable_artifact_prefix, "durable artifact prefix")
        _require_ref(self.version_label_prefix, "version label prefix")


@dataclass(frozen=True, slots=True)
class ProfileManifestEvidenceSpecification:
    """Profile-owned inputs for neutral manifest and readiness assembly."""

    manifest_id: str
    manifest_filename: str
    active_artifact_set_filename: str
    source_component_ref: str
    supported_import_bindings: tuple[tuple[str, str, str], ...]
    artifact_set_notes: str
    profile_executed_evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_ref(self.manifest_id, "capability manifest id")
        _require_filename(self.manifest_filename, "capability manifest filename")
        _require_filename(
            self.active_artifact_set_filename,
            "active artifact set filename",
        )
        _require_ref(self.source_component_ref, "manifest input source component")
        if (
            type(self.supported_import_bindings) is not tuple
            or any(
                type(binding) is not tuple
                or len(binding) != 3
                or any(type(value) is not str or not value for value in binding)
                for binding in self.supported_import_bindings
            )
        ):
            raise ValueError(
                "supported import bindings must be exact string triples"
            )
        targets = tuple(binding[0] for binding in self.supported_import_bindings)
        if len(targets) != len(set(targets)):
            raise ValueError("supported import targets must be unique")
        _require_ref(self.artifact_set_notes, "active artifact set notes")
        if type(self.profile_executed_evidence_refs) is not tuple:
            raise ValueError("profile executed evidence refs must be a tuple")
        if self.profile_executed_evidence_refs:
            raise ValueError(
                "profile executed evidence is not admitted by this runtime"
            )


def _require_filename(value: object, label: str) -> str:
    _require_ref(value, label)
    if "/" in value or "\\" in value or not value.endswith(".json"):
        raise ValueError(f"{label} must be one JSON basename")
    return value


class ProfileApplicabilityResult(TypedDict):
    contextSnapshotId: str

class ProfileMaterializationUpdate(TypedDict):
    basisRef: str
    snapshotRef: str

@dataclass(frozen=True, slots=True)
class RegistryReverificationRequest:
    claim_canonical_bytes: bytes
    resolved_binding_canonical_bytes: tuple[bytes, ...]
    current_reference_snapshot_ref: str | None
    event_time: str
    def __post_init__(self) -> None:
        if type(self.claim_canonical_bytes) is not bytes or not self.claim_canonical_bytes:
            raise ValueError("registry claim bytes must be non-empty built-in bytes")
        if (
            type(self.resolved_binding_canonical_bytes) is not tuple
            or any(type(value) is not bytes or not value
                   for value in self.resolved_binding_canonical_bytes)
        ):
            raise ValueError("registry binding bytes must be an exact tuple of bytes")
        if self.current_reference_snapshot_ref is not None:
            _require_ref(self.current_reference_snapshot_ref, "registry snapshot ref")
        _require_ref(self.event_time, "registry event time")

class RegistryReverificationDisposition(Enum):
    NO_EFFECT = "NO_EFFECT"
    REVERIFIED = "REVERIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REFUSED = "REFUSED"

@dataclass(frozen=True, slots=True)
class RegistryReverificationOutcome:
    disposition: RegistryReverificationDisposition
    problem: dict | None = None
    rationale: str | None = None


@runtime_checkable
class ProfilePolicyService(Protocol):
    descriptor: ProfileRuntimeDescriptor
    policy_ref: str
    recognized_rule_refs: frozenset[str]
    runtime_component: RuntimeComponent | None

    def evidence_policy(self, supported_checks=None) -> dict: ...

    def validation_policy(self) -> dict: ...


@runtime_checkable
class ProfileContextAssembler(Protocol):
    store: object
    active_profile: ProfileRuntimeDescriptor

    def assemble(
        self,
        cur,
        farm_ref: str,
        *,
        target_twin: str = "COMPLIANCE",
        evaluation_time_policy: dict | None = None,
    ) -> ProfileApplicabilityResult: ...


@runtime_checkable
class ProfileMaterializer(Protocol):
    store: object
    active_profile: ProfileRuntimeDescriptor
    specification: MaterializationSpecification
    context: ProfileContextAssembler

    def invalidate_for_sources(
        self,
        cur,
        source_refs: list[str],
        *,
        trigger_family: str,
        trigger_source_ref: str,
        farm_scope_ref: str | None = None,
        reason_code: str = "BASIS_ADVANCED",
    ) -> int: ...

    def recompute(
        self,
        cur,
        farm_ref: str,
        *,
        twin: str = "COMPLIANCE",
        use_class: str = "OPERATIONAL_DASHBOARD",
        time_policy: dict | None = None,
    ) -> ProfileMaterializationUpdate: ...

    def resolve_for_use(
        self,
        cur,
        farm_ref: str,
        *,
        twin: str = "COMPLIANCE",
        use_class: str,
        time_policy: dict | None = None,
        required_freshness: str | None = None,
        high_consequence: bool = False,
        recompute_if_needed: bool = True,
    ) -> dict: ...


@runtime_checkable
class ProfileRegistryReverification(Protocol):
    active_profile: ProfileRuntimeDescriptor
    reference_family: ReferenceFamily | None
    runtime_bundle: RuntimeBundle | None
    selected_input_bindings: tuple[tuple[str, str, str], ...]

    def run(self, request: RegistryReverificationRequest
            ) -> RegistryReverificationOutcome: ...


@runtime_checkable
class ProfileOutputAssembler(Protocol):
    store: object
    active_profile: ProfileRuntimeDescriptor
    specification: OutputSpecification
    materializer: ProfileMaterializer

    def passport_view(
        self,
        farm_ref: str,
        requesting_party_ref: str,
        *,
        allow_recompute: bool = True,
    ) -> dict: ...

    def freeze_document_assembly(
        self,
        farm_ref: str,
        requesting_party_ref: str,
        window_start: str,
        window_end: str,
        *,
        as_submission: bool = False,
    ) -> dict: ...


@dataclass(frozen=True, slots=True)
class ProfileRuntimeServices:
    """Complete executable binding for one exact runtime descriptor."""

    descriptor: ProfileRuntimeDescriptor
    policy_provider: ProfilePolicyService
    context_assembler: ProfileContextAssembler
    materialization_specification: MaterializationSpecification
    materializer: ProfileMaterializer
    registry_reverification: ProfileRegistryReverification
    registry_reference_family: ReferenceFamily | None
    output_specification: OutputSpecification
    output_assembler: ProfileOutputAssembler
    manifest_evidence_specification: ProfileManifestEvidenceSpecification
