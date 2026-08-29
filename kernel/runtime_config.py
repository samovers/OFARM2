"""One immutable snapshot of production runtime configuration."""
from __future__ import annotations

import base64
import binascii
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Self, cast

from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict

from deployment.postgresql.tenant_contract import validate_oidc_issuer

_KID = re.compile(r"[A-Za-z0-9_-]{43}")
_AUDIENCE = re.compile(r"[!-~]{1,255}")
_KMS_KEY = re.compile(
    r"projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/"
    r"locations/[a-z0-9](?:[a-z0-9-]*[a-z0-9])?/"
    r"keyRings/[A-Za-z0-9_-]{1,63}/cryptoKeys/[A-Za-z0-9_-]{1,63}"
)
_INVALID_STATIC = "production static configuration is invalid"
_INVALID_OBSERVER_KEY = "observer public key is not canonical base64"
_OBSERVER_KEY_SETTING = "OFARM_SIGNING_EVIDENCE_OBSERVER_PUBLIC_KEY_B64"


class RuntimeMode(str, Enum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    TEST = "test"


class RuntimeConfigurationError(RuntimeError):
    pass


def _required(values: dict[str, str], name: str) -> str:
    value = values.get(name)
    if type(value) is not str or not value:
        raise RuntimeConfigurationError(f"{name} is required")
    return value


def _observer_public_key(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeConfigurationError(_INVALID_OBSERVER_KEY) from exc
    canonical = base64.b64encode(decoded).decode("ascii")
    if len(decoded) != 32 or canonical != value:
        raise RuntimeConfigurationError("observer public key is invalid")
    return decoded


def _dsn(values: dict[str, str], name: str) -> str:
    value = _required(values, name)
    try:
        conninfo_to_dict(value)
    except (TypeError, ValueError, ProgrammingError) as exc:
        raise RuntimeConfigurationError(f"{name} is invalid") from exc
    return value


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeConfig:
    mode: RuntimeMode
    deployment_image_digest: str
    oidc_issuer: str
    oidc_audience: str
    oidc_jwks_url: str
    pg_dsn: str
    tenant_readiness_pg_dsn: str
    security_audit_readiness_pg_dsn: str
    security_audit_authentication_pg_dsn: str
    security_audit_request_router_pg_dsn: str
    security_audit_control_pg_dsn: str
    correlation_hmac_kms_key_resource: str
    tenant_capability_kid: str
    signing_evidence_receipt_path: Path
    signing_evidence_observer_public_key: bytes

    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return NotImplemented
        other_carrier = cast(Self, other)
        return (
            self.mode,
            self.deployment_image_digest,
            self.oidc_issuer,
            self.oidc_audience,
            self.oidc_jwks_url,
            self.pg_dsn,
            self.tenant_readiness_pg_dsn,
            self.security_audit_readiness_pg_dsn,
            self.security_audit_authentication_pg_dsn,
            self.security_audit_request_router_pg_dsn,
            self.security_audit_control_pg_dsn,
            self.correlation_hmac_kms_key_resource,
            self.tenant_capability_kid,
            self.signing_evidence_receipt_path,
            self.signing_evidence_observer_public_key,
        ) == (
            other_carrier.mode,
            other_carrier.deployment_image_digest,
            other_carrier.oidc_issuer,
            other_carrier.oidc_audience,
            other_carrier.oidc_jwks_url,
            other_carrier.pg_dsn,
            other_carrier.tenant_readiness_pg_dsn,
            other_carrier.security_audit_readiness_pg_dsn,
            other_carrier.security_audit_authentication_pg_dsn,
            other_carrier.security_audit_request_router_pg_dsn,
            other_carrier.security_audit_control_pg_dsn,
            other_carrier.correlation_hmac_kms_key_resource,
            other_carrier.tenant_capability_kid,
            other_carrier.signing_evidence_receipt_path,
            other_carrier.signing_evidence_observer_public_key,
        )

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        values = dict(os.environ)
        if _required(values, "OFARM_AUTH_MODE") != RuntimeMode.PRODUCTION.value:
            raise RuntimeConfigurationError(
                "create_app requires OFARM_AUTH_MODE=production"
            )
        issuer = _required(values, "OFARM_OIDC_ISSUER")
        audience = _required(values, "OFARM_OIDC_AUDIENCE")
        jwks_url = _required(values, "OFARM_OIDC_JWKS_URL")
        pg_dsn = _dsn(values, "OFARM_PG_DSN")
        kid = _required(values, "OFARM_TENANT_CAPABILITY_KID")
        receipt_path = Path(_required(values, "OFARM_SIGNING_EVIDENCE_RECEIPT_PATH"))
        try:
            validate_oidc_issuer(issuer)
        except (TypeError, ValueError, ProgrammingError) as exc:
            raise RuntimeConfigurationError(_INVALID_STATIC) from exc
        kms_key = _required(values, "OFARM_CORRELATION_HMAC_KMS_KEY_RESOURCE")
        if (
            _AUDIENCE.fullmatch(audience) is None
            or not jwks_url.startswith("https://")
            or _KID.fullmatch(kid) is None
            or not receipt_path.is_absolute()
            or _KMS_KEY.fullmatch(kms_key) is None
        ):
            raise RuntimeConfigurationError(_INVALID_STATIC)
        image = _required(values, "OFARM_DEPLOYMENT_IMAGE_DIGEST")
        observer_key = _observer_public_key(
            _required(values, _OBSERVER_KEY_SETTING)
        )
        return cls(
            mode=RuntimeMode.PRODUCTION,
            deployment_image_digest=image,
            oidc_issuer=issuer,
            oidc_audience=audience,
            oidc_jwks_url=jwks_url,
            pg_dsn=pg_dsn,
            tenant_readiness_pg_dsn=_dsn(
                values, "OFARM_TENANT_READINESS_PG_DSN"
            ),
            security_audit_readiness_pg_dsn=_dsn(
                values, "OFARM_SECURITY_AUDIT_READINESS_PG_DSN"
            ),
            security_audit_authentication_pg_dsn=_dsn(
                values, "OFARM_SECURITY_AUDIT_AUTHENTICATION_PG_DSN"
            ),
            security_audit_request_router_pg_dsn=_dsn(
                values, "OFARM_SECURITY_AUDIT_REQUEST_ROUTER_PG_DSN"
            ),
            security_audit_control_pg_dsn=_dsn(
                values, "OFARM_SECURITY_AUDIT_CONTROL_PG_DSN"
            ),
            correlation_hmac_kms_key_resource=kms_key,
            tenant_capability_kid=kid,
            signing_evidence_receipt_path=receipt_path,
            signing_evidence_observer_public_key=observer_key,
        )
