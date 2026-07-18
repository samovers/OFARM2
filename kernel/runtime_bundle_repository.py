"""Immutable persistence and audit loading for RuntimeBundles.
The caller owns the transaction; the repository never commits. Cold loading
returns inert audit data and never consults the filesystem.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from psycopg.pq import TransactionStatus

from .runtime_bundle import (
    Canonicalization,
    ContentPlacement,
    RuntimeBundle,
    RuntimeBundleError as RuntimeBundleModelError,
    RuntimeComponent,
    RuntimeComponentRole,
    require_tenant_ref as require_model_tenant_ref,
    sha256_bytes,
)

_GLOBAL_PLACEMENT = ContentPlacement.GLOBAL.value
_TENANT_PLACEMENT = ContentPlacement.TENANT.value
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")

# One startup transaction lock makes cross-table identity checks race-free.
_PERSIST_LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"ofarm.runtime-bundle-repository.v1").digest()[:8],
    "big", signed=True,
)


class RuntimeBundleRepositoryError(RuntimeError):
    """Persisted RuntimeBundle content is incomplete, unequal, or malformed."""


@dataclass(frozen=True)
class AuditRuntimeComponent:
    """Retained component data with no activation or execution interface."""
    role: str
    logical_ref: str
    canonicalization: str
    placement: str
    canonical_bytes: bytes
    byte_length: int
    content_digest: str


@dataclass(frozen=True)
class AuditRuntimeBundle:
    """A verified persisted bundle for inspection only."""
    tenant_ref: str
    digest: str
    bundle_ref: str
    canonical_document_bytes: bytes
    components: tuple[AuditRuntimeComponent, ...]


@dataclass(frozen=True)
class _ComponentRecord:
    role: str
    logical_ref: str
    canonicalization: str
    placement: str
    canonical_bytes: bytes
    byte_length: int
    content_digest: str


def _require_digest(value: Any, label: str) -> str:
    if type(value) is not str or _DIGEST_RE.fullmatch(value) is None:
        raise RuntimeBundleRepositoryError(
            f"{label} must be sha256 followed by 64 lowercase hexadecimal digits")
    return value


def _require_tenant_ref(value: object, label: str) -> str:
    try:
        return require_model_tenant_ref(value, label)
    except RuntimeBundleModelError as exc:
        raise RuntimeBundleRepositoryError(str(exc)) from exc


def _require_selected_tenant(
    bundle: RuntimeBundle,
    tenant_ref: str,
    label: str,
) -> None:
    selected_tenant_ref = bundle.selected_tenant_ref
    if selected_tenant_ref is not None and tenant_ref != selected_tenant_ref:
        raise RuntimeBundleRepositoryError(
            f"{label} tenant_ref {tenant_ref!r} does not match "
            f"bundle-selected tenant {selected_tenant_ref!r}"
        )


def _component_record(component: Any) -> _ComponentRecord:
    """Project an already-verified RuntimeComponent into persistence values."""
    return _ComponentRecord(
        role=component.role.value,
        logical_ref=component.logical_ref,
        canonicalization=component.canonicalization.value,
        placement=component.placement.value,
        canonical_bytes=component.canonical_bytes,
        byte_length=component.byte_length,
        content_digest=component.content_digest,
    )


def _validate_model_bundle(
    canonical_bytes: bytes,
    digest: str,
    components: tuple[_ComponentRecord, ...],
) -> RuntimeBundle:
    try:
        model_components = tuple(
            RuntimeComponent(
                role=RuntimeComponentRole(component.role),
                logical_ref=component.logical_ref,
                canonicalization=Canonicalization(component.canonicalization),
                placement=ContentPlacement(component.placement),
                canonical_bytes=component.canonical_bytes,
                content_digest=component.content_digest,
            )
            for component in components
        )
        return RuntimeBundle(
            components=model_components,
            canonical_document_bytes=canonical_bytes,
            digest=digest,
        )
    except (RuntimeBundleModelError, ValueError) as exc:
        raise RuntimeBundleRepositoryError(
            f"persisted RuntimeBundle model is invalid: {exc}"
        ) from exc


def _row_values(row: Any, names: tuple[str, ...]) -> tuple[Any, ...]:
    if isinstance(row, dict):
        return tuple(row[name] for name in names)
    return tuple(row[index] for index in range(len(names)))


def _component_values(component: Any) -> tuple[Any, ...]:
    return (
        component.role, component.logical_ref, component.canonicalization,
        component.placement, component.canonical_bytes, component.byte_length,
        component.content_digest,
    )


def _require_exact_bundle_digest(cur: Any, digest: str, canonical_bytes: bytes) -> None:
    cur.execute(
        "SELECT canonical_bytes, byte_length FROM runtime_bundle "
        "WHERE bundle_digest = %s", (digest,),
    )
    expected = (canonical_bytes, len(canonical_bytes))
    for row in cur.fetchall():
        prior = _row_values(row, ("canonical_bytes", "byte_length"))
        if (bytes(prior[0]), prior[1]) != expected:
            raise RuntimeBundleRepositoryError(
                f"RuntimeBundle digest {digest} was reused with unequal bytes")


def _require_exact_content_digest(
    cur: Any, digest: str, canonical_bytes: bytes
) -> None:
    cur.execute(
        """
        SELECT canonical_bytes, byte_length FROM runtime_content_blob
        WHERE content_digest = %s
        UNION ALL
        SELECT canonical_bytes, byte_length FROM runtime_tenant_content_blob
        WHERE content_digest = %s
        """,
        (digest, digest),
    )
    rows = cur.fetchall()
    if not rows:
        raise RuntimeBundleRepositoryError(f"content digest {digest} was not retained")
    expected = (canonical_bytes, len(canonical_bytes))
    for row in rows:
        prior = _row_values(row, ("canonical_bytes", "byte_length"))
        if (bytes(prior[0]), prior[1]) != expected:
            raise RuntimeBundleRepositoryError(
                f"content digest {digest} was reused with unequal bytes or metadata")


def _require_caller_transaction(cur: Any) -> None:
    try:
        status = cur.connection.info.transaction_status
    except AttributeError as exc:
        raise RuntimeBundleRepositoryError(
            "RuntimeBundle persistence requires a PostgreSQL transaction cursor") from exc
    if status != TransactionStatus.INTRANS:
        raise RuntimeBundleRepositoryError(
            "RuntimeBundle persistence requires an active caller transaction")


class RuntimeBundleRepository:
    """Persist immutable bundles and reconstruct inert audit representations."""

    def persist(self, cur: Any, tenant_ref: str, bundle: RuntimeBundle) -> None:
        """Install atomically; a savepoint removes partial rows on failure."""
        _require_caller_transaction(cur)
        with cur.connection.transaction():
            self._persist(cur, tenant_ref, bundle)

    def _persist(self, cur: Any, tenant_ref: str, bundle: RuntimeBundle) -> None:
        if type(bundle) is not RuntimeBundle:
            raise RuntimeBundleRepositoryError(
                "RuntimeBundle persistence requires a verified RuntimeBundle")
        tenant_ref = _require_tenant_ref(tenant_ref, "persistence tenant_ref")
        _require_selected_tenant(bundle, tenant_ref, "persistence")
        digest = bundle.digest
        bundle_ref = bundle.bundle_ref
        canonical_bytes = bundle.canonical_document_bytes
        components = tuple(_component_record(component) for component in bundle.components)

        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_PERSIST_LOCK_KEY,))
        _require_exact_bundle_digest(cur, digest, canonical_bytes)
        cur.execute(
            "SELECT bundle_ref, canonical_bytes, byte_length FROM runtime_bundle "
            "WHERE tenant_ref = %s AND bundle_digest = %s",
            (tenant_ref, digest),
        )
        row = cur.fetchone()
        if row is not None:
            prior_bundle = _row_values(
                row, ("bundle_ref", "canonical_bytes", "byte_length"))
            expected_bundle = (bundle_ref, canonical_bytes, len(canonical_bytes))
            if (
                prior_bundle[0], bytes(prior_bundle[1]), prior_bundle[2]
            ) != expected_bundle:
                raise RuntimeBundleRepositoryError(
                    f"RuntimeBundle digest {digest} was reused with unequal bytes or metadata")
            audit = self.load_for_audit(cur, tenant_ref, digest)
            if audit is None:
                raise RuntimeBundleRepositoryError(
                    f"RuntimeBundle {digest} disappeared during exact reuse verification")
            if tuple(map(_component_values, audit.components)) != tuple(
                map(_component_values, components)
            ):
                raise RuntimeBundleRepositoryError(
                    f"RuntimeBundle {digest} was reused with unequal component bytes")
            return

        cur.execute(
            "SELECT bundle_digest FROM runtime_bundle "
            "WHERE tenant_ref = %s AND bundle_ref = %s",
            (tenant_ref, bundle_ref),
        )
        if cur.fetchone() is not None:
            raise RuntimeBundleRepositoryError(
                f"RuntimeBundle ref {bundle_ref!r} was reused for another digest")

        for component in components:
            self._persist_content(cur, tenant_ref, component)

        cur.execute(
            """
            INSERT INTO runtime_bundle
              (tenant_ref, bundle_digest, bundle_ref, canonical_bytes, byte_length)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (tenant_ref, digest, bundle_ref, canonical_bytes, len(canonical_bytes)),
        )
        for component in components:
            global_digest = (
                component.content_digest
                if component.placement == _GLOBAL_PLACEMENT else None
            )
            tenant_digest = (
                component.content_digest
                if component.placement == _TENANT_PLACEMENT else None
            )
            cur.execute(
                """
                INSERT INTO runtime_bundle_component
                  (tenant_ref, bundle_digest, component_role, logical_ref,
                   canonicalization, content_placement, global_content_digest,
                   tenant_content_digest, byte_length)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_ref, digest, component.role, component.logical_ref,
                    component.canonicalization, component.placement,
                    global_digest, tenant_digest, component.byte_length,
                ),
            )
        self._require_exact_component_set(cur, tenant_ref, digest, components)

    @staticmethod
    def _persist_content(cur: Any, tenant_ref: str, component: _ComponentRecord) -> None:
        if component.placement == _GLOBAL_PLACEMENT:
            cur.execute(
                """
                INSERT INTO runtime_content_blob
                  (content_digest, canonical_bytes, byte_length)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    component.content_digest, component.canonical_bytes,
                    component.byte_length,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO runtime_tenant_content_blob
                  (tenant_ref, content_digest, canonical_bytes, byte_length)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    tenant_ref, component.content_digest, component.canonical_bytes,
                    component.byte_length,
                ),
            )
        _require_exact_content_digest(
            cur, component.content_digest, component.canonical_bytes)

    @staticmethod
    def _require_exact_component_set(
        cur: Any,
        tenant_ref: str,
        digest: str,
        components: tuple[_ComponentRecord, ...],
    ) -> None:
        cur.execute(
            """
            SELECT component_role, logical_ref, canonicalization,
                   content_placement, global_content_digest,
                   tenant_content_digest, byte_length
            FROM runtime_bundle_component
            WHERE tenant_ref = %s AND bundle_digest = %s
            ORDER BY component_role COLLATE "C", logical_ref COLLATE "C"
            """,
            (tenant_ref, digest),
        )
        names = (
            "component_role", "logical_ref", "canonicalization",
            "content_placement", "global_content_digest",
            "tenant_content_digest", "byte_length",
        )
        prior = tuple(_row_values(row, names) for row in cur.fetchall())
        expected = tuple((
            component.role,
            component.logical_ref,
            component.canonicalization,
            component.placement,
            component.content_digest
            if component.placement == _GLOBAL_PLACEMENT else None,
            component.content_digest
            if component.placement == _TENANT_PLACEMENT else None,
            component.byte_length,
        ) for component in components)
        if prior != expected:
            raise RuntimeBundleRepositoryError(
                f"RuntimeBundle {digest} persisted component set is not exact")

    def load_for_audit(
        self,
        cur: Any,
        tenant_ref: str,
        bundle_digest: str,
    ) -> AuditRuntimeBundle | None:
        """Verify retained bytes and return inert audit data, or ``None``."""
        tenant_ref = _require_tenant_ref(tenant_ref, "audit tenant_ref")
        digest = _require_digest(bundle_digest, "audit RuntimeBundle digest")
        cur.execute(
            "SELECT bundle_ref, canonical_bytes, byte_length FROM runtime_bundle "
            "WHERE tenant_ref = %s AND bundle_digest = %s",
            (tenant_ref, digest),
        )
        row = cur.fetchone()
        if row is None:
            return None
        bundle_ref, stored_bytes, stored_length = _row_values(
            row, ("bundle_ref", "canonical_bytes", "byte_length"))
        canonical_bytes = bytes(stored_bytes)
        if bundle_ref != f"runtimebundle:{digest}":
            raise RuntimeBundleRepositoryError(
                "persisted RuntimeBundle ref does not match its digest")
        if stored_length != len(canonical_bytes):
            raise RuntimeBundleRepositoryError(
                "persisted RuntimeBundle document length is not exact")
        if sha256_bytes(canonical_bytes) != digest:
            raise RuntimeBundleRepositoryError(
                "persisted RuntimeBundle digest does not match its bytes")
        _require_exact_bundle_digest(cur, digest, canonical_bytes)

        components = self._load_audit_components(cur, tenant_ref, digest)
        records = tuple(_ComponentRecord(
            role=component.role,
            logical_ref=component.logical_ref,
            canonicalization=component.canonicalization,
            placement=component.placement,
            canonical_bytes=component.canonical_bytes,
            byte_length=component.byte_length,
            content_digest=component.content_digest,
        ) for component in components)
        model_bundle = _validate_model_bundle(canonical_bytes, digest, records)
        _require_selected_tenant(model_bundle, tenant_ref, "audit")
        return AuditRuntimeBundle(
            tenant_ref=tenant_ref,
            digest=digest,
            bundle_ref=bundle_ref,
            canonical_document_bytes=canonical_bytes,
            components=components,
        )

    @staticmethod
    def _load_audit_components(
        cur: Any,
        tenant_ref: str,
        digest: str,
    ) -> tuple[AuditRuntimeComponent, ...]:
        cur.execute(
            """
            SELECT c.component_role, c.logical_ref,
                   c.canonicalization AS link_canonicalization,
                   c.content_placement, c.global_content_digest,
                   c.tenant_content_digest, c.byte_length AS link_byte_length,
                   g.content_digest AS global_blob_digest,
                   g.canonical_bytes AS global_canonical_bytes,
                   g.byte_length AS global_byte_length,
                   t.content_digest AS tenant_blob_digest,
                   t.canonical_bytes AS tenant_canonical_bytes,
                   t.byte_length AS tenant_byte_length
            FROM runtime_bundle_component c
            LEFT JOIN runtime_content_blob g
              ON g.content_digest = c.global_content_digest
            LEFT JOIN runtime_tenant_content_blob t
              ON t.tenant_ref = c.tenant_ref
             AND t.content_digest = c.tenant_content_digest
            WHERE c.tenant_ref = %s AND c.bundle_digest = %s
            ORDER BY c.component_role COLLATE "C", c.logical_ref COLLATE "C"
            """,
            (tenant_ref, digest),
        )
        names = (
            "component_role", "logical_ref", "link_canonicalization",
            "content_placement", "global_content_digest",
            "tenant_content_digest", "link_byte_length",
            "global_blob_digest", "global_canonical_bytes", "global_byte_length",
            "tenant_blob_digest", "tenant_canonical_bytes", "tenant_byte_length",
        )
        result: list[AuditRuntimeComponent] = []
        for row in cur.fetchall():
            values = _row_values(row, names)
            (
                role, logical_ref, canonicalization, placement,
                global_digest, tenant_digest, link_length,
                global_blob_digest, global_bytes, global_length,
                tenant_blob_digest, tenant_bytes, tenant_length,
            ) = values
            if placement == _GLOBAL_PLACEMENT:
                if tenant_digest is not None:
                    raise RuntimeBundleRepositoryError(
                        f"persisted component {role}/{logical_ref} has mixed placement")
                content_digest = global_digest
                blob_digest = global_blob_digest
                canonical = global_bytes
                blob_length = global_length
            elif placement == _TENANT_PLACEMENT:
                if global_digest is not None:
                    raise RuntimeBundleRepositoryError(
                        f"persisted component {role}/{logical_ref} has mixed placement")
                content_digest = tenant_digest
                blob_digest = tenant_blob_digest
                canonical = tenant_bytes
                blob_length = tenant_length
            else:
                raise RuntimeBundleRepositoryError(
                    "persisted RuntimeBundle has unknown component placement")
            if canonical is None or content_digest is None:
                raise RuntimeBundleRepositoryError(
                    f"persisted component {role}/{logical_ref} has no retained bytes")
            canonical_bytes = bytes(canonical)
            _require_digest(content_digest, "persisted component digest")
            if (
                blob_digest != content_digest
                or blob_length != link_length
                or link_length != len(canonical_bytes)
            ):
                raise RuntimeBundleRepositoryError(
                    f"persisted component {role}/{logical_ref} metadata is not exact")
            if sha256_bytes(canonical_bytes) != content_digest:
                raise RuntimeBundleRepositoryError(
                    f"persisted component {role}/{logical_ref} digest does not match bytes")
            _require_exact_content_digest(cur, content_digest, canonical_bytes)
            result.append(AuditRuntimeComponent(
                role=role,
                logical_ref=logical_ref,
                canonicalization=canonicalization,
                placement=placement,
                canonical_bytes=canonical_bytes,
                byte_length=link_length,
                content_digest=content_digest,
            ))
        return tuple(result)


__all__ = ["AuditRuntimeBundle", "AuditRuntimeComponent",
           "RuntimeBundleRepository", "RuntimeBundleRepositoryError"]
