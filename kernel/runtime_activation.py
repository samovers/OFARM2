"""Process-local observations for one verified runtime activation."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .schema_posture import DatabaseObservation


_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class RuntimeActivationError(RuntimeError):
    """A required startup observation is missing or malformed."""


def require_deployment_image_digest(value: object) -> str:
    if type(value) is not str or _DIGEST_RE.fullmatch(value) is None:
        raise RuntimeActivationError(
            "deployment image digest must be sha256 followed by 64 lowercase "
            "hexadecimal digits"
        )
    return value


def complete_store_startup(store) -> DatabaseObservation:
    """Verify and install one Store startup unit, then publish readiness.

    Schema posture, RuntimeBundle persistence, and canonical profile bootstrap
    share one outer transaction. The Store becomes usable by high-level runtime
    services only after that transaction commits.
    """
    from . import context

    with store._startup_transaction():
        observation = store.migrate()
        context.bootstrap(store)
    return observation


@dataclass(frozen=True, slots=True)
class RuntimeActivationObservation:
    """Non-digested activation facts, separate from stable RuntimeBundle identity."""

    tenant_ref: str
    active_profile_ref: str
    runtime_bundle_digest: str
    deployment_image_digest: str
    database: DatabaseObservation

    def as_dict(self) -> dict:
        return {
            "tenantRef": self.tenant_ref,
            "activeProfileRef": self.active_profile_ref,
            "runtimeBundleDigest": self.runtime_bundle_digest,
            "deploymentImageDigest": self.deployment_image_digest,
            "database": self.database.as_dict(),
        }
