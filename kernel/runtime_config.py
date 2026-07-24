"""One immutable snapshot of production runtime configuration."""
from __future__ import annotations

import base64
import binascii
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict

from deployment.postgresql.tenant_contract import validate_oidc_issuer

_KID = re.compile(r"[A-Za-z0-9_-]{43}")
_AUDIENCE = re.compile(r"[!-~]{1,255}")


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
        encoded = value.encode("ascii", errors="strict")
        decoded = base64.b64decode(encoded, validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise RuntimeConfigurationError(
            "observer public key is not canonical base64"
        ) from exc
    if len(decoded) != 32 or base64.b64encode(decoded) != encoded:
        raise RuntimeConfigurationError("observer public key is invalid")
    return decoded


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    mode: RuntimeMode
    deployment_image_digest: str
    oidc_issuer: str
    oidc_audience: str
    oidc_jwks_url: str
    pg_dsn: str
    tenant_capability_kid: str
    signing_evidence_receipt_path: Path
    signing_evidence_observer_public_key: bytes

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        values = dict(os.environ)
        mode = _required(values, "OFARM_AUTH_MODE")
        if mode != RuntimeMode.PRODUCTION.value:
            raise RuntimeConfigurationError(
                "create_app requires OFARM_AUTH_MODE=production"
            )
        issuer = _required(values, "OFARM_OIDC_ISSUER")
        audience = _required(values, "OFARM_OIDC_AUDIENCE")
        jwks_url = _required(values, "OFARM_OIDC_JWKS_URL")
        pg_dsn = _required(values, "OFARM_PG_DSN")
        kid = _required(values, "OFARM_TENANT_CAPABILITY_KID")
        receipt_path = Path(
            _required(values, "OFARM_SIGNING_EVIDENCE_RECEIPT_PATH")
        )
        try:
            validate_oidc_issuer(issuer)
            conninfo_to_dict(pg_dsn)
        except (TypeError, ValueError, ProgrammingError) as exc:
            raise RuntimeConfigurationError(
                "production static configuration is invalid"
            ) from exc
        if (
            _AUDIENCE.fullmatch(audience) is None
            or not jwks_url.startswith("https://")
            or _KID.fullmatch(kid) is None
            or not receipt_path.is_absolute()
        ):
            raise RuntimeConfigurationError(
                "production static configuration is invalid"
            )
        return cls(
            mode=RuntimeMode.PRODUCTION,
            deployment_image_digest=_required(
                values, "OFARM_DEPLOYMENT_IMAGE_DIGEST"
            ),
            oidc_issuer=issuer,
            oidc_audience=audience,
            oidc_jwks_url=jwks_url,
            pg_dsn=pg_dsn,
            tenant_capability_kid=kid,
            signing_evidence_receipt_path=receipt_path,
            signing_evidence_observer_public_key=_observer_public_key(
                _required(
                    values,
                    "OFARM_SIGNING_EVIDENCE_OBSERVER_PUBLIC_KEY_B64",
                )
            ),
        )
