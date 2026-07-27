"""Explicit development and test composition for the legacy HTTP surface."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..deployment_identity import require_deployment_image_digest
from ..gates import GatePipeline
from ..runtime_activation import (
    RuntimeActivationObservation,
    complete_store_startup,
)
from ..store import Store
from ..views import OutputGenerator

if TYPE_CHECKING:
    from ..auth_oidc import TestOidcVerifier


@dataclass(frozen=True, slots=True)
class DevelopmentRuntime:
    store: Store
    pipeline: GatePipeline
    outputs: OutputGenerator
    activation: RuntimeActivationObservation


@dataclass(frozen=True, slots=True)
class TestRuntime:
    store: Store
    pipeline: GatePipeline
    outputs: OutputGenerator
    activation: RuntimeActivationObservation
    oidc: TestOidcVerifier | None


def _components(
    store: Store,
    deployment_image_digest: str,
) -> tuple[GatePipeline, OutputGenerator, RuntimeActivationObservation]:
    image_digest = require_deployment_image_digest(deployment_image_digest)
    database = complete_store_startup(store)
    activation = RuntimeActivationObservation(
        tenant_ref=store.tenant_ref,
        active_profile_ref=store.active_descriptor.profile_ref,
        runtime_bundle_digest=store.runtime_bundle_digest,
        deployment_image_digest=image_digest,
        database=database,
    )
    return (
        GatePipeline(store, active_descriptor=store.active_descriptor),
        OutputGenerator(store, active_descriptor=store.active_descriptor),
        activation,
    )


def build_development_runtime(
    store: Store,
    deployment_image_digest: str,
) -> DevelopmentRuntime:
    pipeline, outputs, activation = _components(
        store, deployment_image_digest
    )
    return DevelopmentRuntime(store, pipeline, outputs, activation)


def build_test_runtime(
    store: Store,
    deployment_image_digest: str,
    oidc: TestOidcVerifier | None,
) -> TestRuntime:
    pipeline, outputs, activation = _components(
        store, deployment_image_digest
    )
    return TestRuntime(store, pipeline, outputs, activation, oidc)
