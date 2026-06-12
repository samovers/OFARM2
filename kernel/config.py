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
