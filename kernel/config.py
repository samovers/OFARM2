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


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        from .auth_oidc import AuthenticationStartupError

        raise AuthenticationStartupError(f"{name} is required")
    return value


def _bounded_environment_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        from .auth_oidc import AuthenticationStartupError

        raise AuthenticationStartupError(f"{name} must be an integer") from exc


def authentication_runtime_from_env(*, principal_binding_resolver=None):
    """Build exactly the authentication mode named by ``OFARM_AUTH_MODE``.

    No other variable selects a mode and an absent mode is a startup refusal.
    Production never imports the local header or HS256 fixture into its runtime
    shape and also requires an initialized immutable-binding resolver.
    """

    from .auth_oidc import (
        AuthenticationMode,
        AuthenticationRuntime,
        AuthenticationStartupError,
        OidcConfig,
        ProductionOidcConfig,
        ProductionOidcVerifier,
    )

    raw_mode = os.environ.get("OFARM_AUTH_MODE")
    try:
        mode = AuthenticationMode(raw_mode) if raw_mode is not None else None
    except ValueError as exc:
        raise AuthenticationStartupError("OFARM_AUTH_MODE is invalid") from exc
    if mode is None:
        raise AuthenticationStartupError("OFARM_AUTH_MODE is required")

    if mode is AuthenticationMode.DEVELOPMENT:
        return AuthenticationRuntime.development()

    issuer = _required_environment("OFARM_OIDC_ISSUER")
    audience = _required_environment("OFARM_OIDC_AUDIENCE")
    if mode is AuthenticationMode.TEST:
        algorithm = os.environ.get("OFARM_OIDC_ALG", "HS256")
        if algorithm != "HS256":
            raise AuthenticationStartupError(
                "test mode accepts only the local HS256 verifier"
            )
        verifier = OidcConfig(
            issuer=issuer,
            audience=audience,
            algorithm=algorithm,
            hs256_secret=_required_environment("OFARM_OIDC_HS256_SECRET"),
            subject_claim=os.environ.get("OFARM_OIDC_SUBJECT_CLAIM", "sub"),
            roles_claim=os.environ.get("OFARM_OIDC_ROLES_CLAIM") or None,
            leeway_seconds=_bounded_environment_int("OFARM_OIDC_LEEWAY_SECONDS", 0),
        )
        return AuthenticationRuntime.test(verifier)

    if os.environ.get("OFARM_OIDC_HS256_SECRET") is not None:
        raise AuthenticationStartupError(
            "OFARM_OIDC_HS256_SECRET is forbidden in production mode"
        )
    if principal_binding_resolver is None:
        raise AuthenticationStartupError(
            "production principal-binding resolver is required"
        )
    algorithms = tuple(
        os.environ.get("OFARM_OIDC_ALGORITHMS", "RS256").split(",")
    )
    verifier = ProductionOidcVerifier(
        ProductionOidcConfig(
            issuer=issuer,
            audience=audience,
            jwks_url=_required_environment("OFARM_OIDC_JWKS_URL"),
            algorithms=algorithms,
            leeway_seconds=_bounded_environment_int(
                "OFARM_OIDC_LEEWAY_SECONDS", 0
            ),
            jwks_lifespan_seconds=_bounded_environment_int(
                "OFARM_OIDC_JWKS_LIFESPAN_SECONDS", 300
            ),
            timeout_seconds=_bounded_environment_int(
                "OFARM_OIDC_JWKS_TIMEOUT_SECONDS", 5
            ),
        )
    )
    return AuthenticationRuntime.production(verifier, principal_binding_resolver)


def oidc_config_from_env():
    """Compatibility accessor for explicit test mode only."""

    runtime = authentication_runtime_from_env()
    return runtime.verifier
