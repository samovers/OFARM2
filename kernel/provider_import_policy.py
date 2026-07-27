"""Code-owned admission for RuntimeBundle-governed provider imports."""
from __future__ import annotations

import hashlib
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable


class ProviderImportError(RuntimeError):
    """A provider import did not preserve exact source authority."""


@dataclass(frozen=True, slots=True)
class _BytecodePosture:
    cache_owner: tempfile.TemporaryDirectory[str]
    cache_root: Path


@dataclass(frozen=True, slots=True)
class _ProviderAttestation:
    module_name: str
    component_ref: str
    source_path: Path
    source_digest: str
    factory_name: str
    module: ModuleType
    factory: Callable[..., object]


_POSTURE: _BytecodePosture | None = None
_ATTESTATIONS: dict[str, _ProviderAttestation] = {}


def _install_bytecode_posture() -> _BytecodePosture:
    global _POSTURE
    if _POSTURE is None:
        owner = tempfile.TemporaryDirectory(
            prefix="ofarm-provider-bytecode-",
        )
        cache_root = Path(owner.name).resolve(strict=True)
        sys.pycache_prefix = str(cache_root)
        sys.dont_write_bytecode = True
        _POSTURE = _BytecodePosture(owner, cache_root)
    return _require_bytecode_posture()


def _require_bytecode_posture() -> _BytecodePosture:
    posture = _POSTURE
    if posture is None:
        raise ProviderImportError(
            "trusted provider bytecode posture is not installed"
        )
    if (
        sys.pycache_prefix != str(posture.cache_root)
        or sys.dont_write_bytecode is not True
    ):
        raise ProviderImportError(
            "trusted provider bytecode posture changed"
        )
    try:
        populated = next(posture.cache_root.iterdir(), None)
    except OSError as exc:
        raise ProviderImportError(
            "trusted provider bytecode cache is unavailable"
        ) from exc
    if populated is not None:
        raise ProviderImportError(
            "trusted provider bytecode cache is not empty"
        )
    return posture


def _source_digest(source_bytes: bytes) -> str:
    return f"sha256:{hashlib.sha256(source_bytes).hexdigest()}"


def _verify_source(path: Path, expected_bytes: bytes) -> Path:
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file() or resolved.read_bytes() != expected_bytes:
            raise ProviderImportError(
                "registered provider source differs from its verified bytes"
            )
    except ProviderImportError:
        raise
    except OSError as exc:
        raise ProviderImportError(
            "registered provider source is unavailable"
        ) from exc
    return resolved


def _resolved_origin(value: object, label: str) -> Path:
    if type(value) is not str or not value:
        raise ProviderImportError(f"registered provider {label} is unavailable")
    try:
        return Path(value).resolve(strict=True)
    except OSError as exc:
        raise ProviderImportError(
            f"registered provider {label} is unavailable"
        ) from exc


def _verify_loaded_factory(
    module_name: str,
    source_path: Path,
    factory_name: str,
    module: object,
    factory: object,
    posture: _BytecodePosture,
) -> tuple[ModuleType, Callable[..., object]]:
    if type(module) is not ModuleType or module.__name__ != module_name:
        raise ProviderImportError(
            "registered provider module identity differs"
        )
    spec = getattr(module, "__spec__", None)
    loader = getattr(spec, "loader", None)
    if (
        spec is None
        or getattr(spec, "has_location", False) is not True
        or type(loader).__name__ != "SourceFileLoader"
        or _resolved_origin(getattr(spec, "origin", None), "origin")
        != source_path
        or _resolved_origin(getattr(module, "__file__", None), "file")
        != source_path
    ):
        raise ProviderImportError(
            "registered provider module does not use its verified source"
        )
    cached = getattr(module, "__cached__", None)
    if type(cached) is not str:
        raise ProviderImportError(
            "registered provider bytecode location is unavailable"
        )
    cached_path = Path(cached).resolve()
    try:
        cached_path.relative_to(posture.cache_root)
    except ValueError as exc:
        raise ProviderImportError(
            "registered provider bytecode location is outside policy"
        ) from exc
    if cached_path.exists():
        raise ProviderImportError(
            "registered provider import created bytecode"
        )
    if (
        not callable(factory)
        or getattr(factory, "__name__", None) != factory_name
        or getattr(factory, "__module__", None) != module_name
        or getattr(module, factory_name, None) is not factory
    ):
        raise ProviderImportError(
            "registered provider factory identity differs"
        )
    try:
        code_origin = Path(factory.__code__.co_filename).resolve(strict=True)
    except (AttributeError, OSError, TypeError) as exc:
        raise ProviderImportError(
            "registered provider factory source is unavailable"
        ) from exc
    if code_origin != source_path:
        raise ProviderImportError(
            "registered provider factory does not originate from verified source"
        )
    return module, factory


def load_provider_factory(
    *,
    module_name: str,
    component_ref: str,
    source_path: Path,
    source_bytes: bytes,
    factory_name: str,
    factory_resolver: Callable[[], object],
) -> Callable[..., object]:
    """Admit one literal import, then allow only its exact attested reuse."""
    if (
        type(module_name) is not str
        or not module_name
        or type(component_ref) is not str
        or not component_ref
        or not isinstance(source_path, Path)
        or type(source_bytes) is not bytes
        or type(factory_name) is not str
        or not factory_name
        or not callable(factory_resolver)
    ):
        raise ProviderImportError("registered provider import request is invalid")
    posture = _install_bytecode_posture()
    resolved_source = _verify_source(source_path, source_bytes)
    digest = _source_digest(source_bytes)
    existing = sys.modules.get(module_name)
    attestation = _ATTESTATIONS.get(module_name)
    if existing is not None:
        if (
            attestation is None
            or existing is not attestation.module
            or attestation.component_ref != component_ref
            or attestation.source_path != resolved_source
            or attestation.source_digest != digest
            or attestation.factory_name != factory_name
        ):
            raise ProviderImportError(
                "registered provider was imported before trusted admission"
            )
        _verify_loaded_factory(
            module_name,
            resolved_source,
            factory_name,
            existing,
            attestation.factory,
            posture,
        )
        _verify_source(resolved_source, source_bytes)
        _require_bytecode_posture()
        return attestation.factory
    if attestation is not None:
        raise ProviderImportError(
            "attested provider module is no longer loaded"
        )
    try:
        factory = factory_resolver()
    except Exception as exc:
        raise ProviderImportError(
            "registered provider literal import failed"
        ) from exc
    module, admitted_factory = _verify_loaded_factory(
        module_name,
        resolved_source,
        factory_name,
        sys.modules.get(module_name),
        factory,
        posture,
    )
    _verify_source(resolved_source, source_bytes)
    _require_bytecode_posture()
    _ATTESTATIONS[module_name] = _ProviderAttestation(
        module_name=module_name,
        component_ref=component_ref,
        source_path=resolved_source,
        source_digest=digest,
        factory_name=factory_name,
        module=module,
        factory=admitted_factory,
    )
    return admitted_factory
