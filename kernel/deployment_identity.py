"""Pure validation for one immutable deployment image identity."""
from __future__ import annotations

import re


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
