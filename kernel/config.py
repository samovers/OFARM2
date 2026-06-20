"""Kernel runtime configuration.

Deliberately boring (PLATFORM.md technology recommendation): everything is a
path or a DSN, overridable by environment variables, defaulting to the
package-local development cluster created for M1.
"""
from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent

CONTRACTS_ROOT = PACKAGE_ROOT / "contracts"
DRAFTS_ROOT = CONTRACTS_ROOT / "drafts_reference" / "explainable_current_state_evidence"
PROFILE_ROOT = PACKAGE_ROOT / "profile_si_ffs"

TENANT_REF = "tenant:si.ffs.pilot.demo"

RUNTIME_VERSION = "ofarm2-kernel-m1.0"

# the first real REGSR snapshot shipped with the package (M0)
SHIPPED_REGSR_SNAPSHOT_REF = "referencesnapshot:si.uvhvvr.ffs-reg.2026-06-11"

# Reserved identifiers (profile_si_ffs/PROFILE.md)
PROFILE_REF = "profile:si.ffs.recordkeeping.v0_1"
PACK_REF = "pack:si.ffs.pilot.v0_1"
EVIDENCE_POLICY_REF = "policy:si.ffs.evidence-review.v0_1"
CODE_BINDING_PROFILE_REF = "codebindingprofile:si.ffs.v0_1"


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


def oidc_config_from_env():
    """The OIDC verifier config for the HTTP surface (M2 G4), or None when OIDC is
    disabled — in which case the development/conformance X-Acting-Party principal
    shim applies (NOT production auth; see profile_si_ffs/UNSUPPORTED_SURFACES.md).

    Enabled only when OFARM_OIDC_ISSUER and OFARM_OIDC_AUDIENCE are set. The
    algorithm defaults to HS256 (the only path implemented in this build); setting
    OFARM_OIDC_ALG=RS256 selects the deliberate NotImplemented production path
    (the verifier fails closed, never falling back to HS256)."""
    issuer = os.environ.get("OFARM_OIDC_ISSUER")
    audience = os.environ.get("OFARM_OIDC_AUDIENCE")
    if not (issuer and audience):
        return None
    from .auth_oidc import OidcConfig
    return OidcConfig(
        issuer=issuer, audience=audience,
        algorithm=os.environ.get("OFARM_OIDC_ALG", "HS256"),
        hs256_secret=os.environ.get("OFARM_OIDC_HS256_SECRET"),
        subject_claim=os.environ.get("OFARM_OIDC_SUBJECT_CLAIM", "sub"),
        roles_claim=os.environ.get("OFARM_OIDC_ROLES_CLAIM") or None)
