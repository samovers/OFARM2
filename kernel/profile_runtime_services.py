"""Private, profile-neutral contracts for executable runtime services."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .profile_runtime import ProfileRuntimeDescriptor


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


@runtime_checkable
class ProfilePolicyService(Protocol):
    descriptor: ProfileRuntimeDescriptor
    policy_ref: str
    recognized_rule_refs: frozenset[str]

    def evidence_policy(self, supported_checks=None) -> dict: ...

    def validation_policy(self) -> dict: ...


@runtime_checkable
class ProfileContextAssembler(Protocol):
    active_profile: ProfileRuntimeDescriptor

    def assemble(
        self,
        cur,
        farm_ref: str,
        *,
        target_twin: str = "COMPLIANCE",
        evaluation_time_policy: dict | None = None,
    ) -> dict: ...


@runtime_checkable
class ProfileMaterializer(Protocol):
    active_profile: ProfileRuntimeDescriptor
    specification: MaterializationSpecification

    def invalidate_for_sources(
        self,
        cur,
        source_refs: list[str],
        *,
        trigger_family: str = "BASIS_ADVANCED",
    ) -> int: ...

    def recompute(
        self,
        cur,
        farm_ref: str,
        *,
        twin: str = "COMPLIANCE",
        time_policy: dict | None = None,
    ) -> dict: ...

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
    def run(self, context): ...


@runtime_checkable
class ProfileOutputAssembler(Protocol):
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
    output_specification: OutputSpecification
    output_assembler: ProfileOutputAssembler
