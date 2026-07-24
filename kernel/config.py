"""Kernel runtime configuration.

Deliberately boring (PLATFORM.md technology recommendation): everything is a
path or a DSN, overridable by environment variables, defaulting to the
package-local development cluster created for M1.
"""
from __future__ import annotations

import os
from pathlib import Path

from .profile_runtime import ProfileRuntimeError, load_active_profile_selection

PACKAGE_ROOT = Path(__file__).resolve().parent.parent

CONTRACTS_ROOT = PACKAGE_ROOT / "contracts"
DRAFTS_ROOT = CONTRACTS_ROOT / "drafts_reference" / "explainable_current_state_evidence"
DEFAULT_ACTIVE_PROFILE_PACKAGE_NAMES = ("profile_si_ffs",)
ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES = DEFAULT_ACTIVE_PROFILE_PACKAGE_NAMES
ACTIVE_PROFILE_PACKAGE_NAMES_ENV = "OFARM_ACTIVE_PROFILE_PACKAGES"


def active_profile_package_names_from_env() -> tuple[str, ...]:
    raw = os.environ.get(ACTIVE_PROFILE_PACKAGE_NAMES_ENV)
    if raw is None:
        return DEFAULT_ACTIVE_PROFILE_PACKAGE_NAMES
    names = tuple(part.strip() for part in raw.split(","))
    if any(not name for name in names):
        raise ProfileRuntimeError(
            f"{ACTIVE_PROFILE_PACKAGE_NAMES_ENV} contains blank profile package token")
    return names


ACTIVE_PROFILE_PACKAGE_NAMES = active_profile_package_names_from_env()
ACTIVE_PROFILE_SELECTION = load_active_profile_selection(
    PACKAGE_ROOT,
    ACTIVE_PROFILE_PACKAGE_NAMES,
    allowed_profile_package_names=ALLOWED_ACTIVE_PROFILE_PACKAGE_NAMES,
)
ACTIVE_PROFILE_PACKAGE_NAME = (
    ACTIVE_PROFILE_SELECTION.active_profile_package_name
)
ACTIVE_PROFILE = ACTIVE_PROFILE_SELECTION.active_profile
ACTIVE_PROFILE_ROOTS = ACTIVE_PROFILE_SELECTION.profile_roots
PROFILE_ROOT = ACTIVE_PROFILE.profile_root

# Active deployment/demo binding. This is deliberately separate from the
# profile-local runtime descriptor: tenant identity is not inherent package
# content.
TENANT_REF = "tenant:si.ffs.pilot.demo"

RUNTIME_VERSION = "ofarm2-kernel-m1.0"

# the first real REGSR snapshot shipped with the package (M0)
_REGSR_FAMILY = ACTIVE_PROFILE.reference_family("si.uvhvvr.ffs-reg")
if _REGSR_FAMILY.shipped_snapshot_ref is None:
    raise RuntimeError("active SI profile descriptor must name the shipped REGSR snapshot")
SHIPPED_REGSR_SNAPSHOT_REF = _REGSR_FAMILY.shipped_snapshot_ref

# Reserved identifiers (profile_si_ffs/PROFILE.md)
PROFILE_REF = ACTIVE_PROFILE.profile_ref
PACK_REF = ACTIVE_PROFILE.pack_ref
EVIDENCE_POLICY_REF = ACTIVE_PROFILE.evidence_policy_ref
CODE_BINDING_PROFILE_REF = ACTIVE_PROFILE.code_binding_profile_ref
# the active profile's evidence-review policy CONTENT (M2 P5): the SI evidence
# floor (hard/soft items) and advisory rules live here as package content, read
# by the generic kernel.profile_policy loader — NOT as kernel constants. This is
# a profile-binding pointer (config's role), never a floor VALUE.
EVIDENCE_POLICY_PATH = ACTIVE_PROFILE.evidence_policy_path
def database_dsn() -> str:
    """DSN for the truth store.

    Default: the unix-socket scratch cluster under .pgrun (no TCP listener).
    """
    explicit = os.environ.get("OFARM_PG_DSN")
    if explicit:
        return explicit
    socket_dir = os.environ.get("OFARM_PG_SOCKET_DIR", str(PACKAGE_ROOT / ".pgrun"))
    port = os.environ.get("OFARM_PG_PORT", "54317")
    dbname = os.environ.get("OFARM_PG_DBNAME", "ofarm_kernel")
    user = os.environ.get("OFARM_PG_USER", "ofarm")
    return f"host={socket_dir} port={port} dbname={dbname} user={user}"
