"""PostgreSQL persistence tests for issue #171 RuntimeBundles."""
from __future__ import annotations

import json
import os
import queue
import threading
import time
import uuid
from pathlib import Path

import psycopg
import psycopg.conninfo
import pytest
from psycopg import sql

from kernel.runtime_bundle import (
    BUNDLE_SCHEMA_VERSION,
    Canonicalization,
    ContentPlacement,
    RuntimeBundle,
    RuntimeBundleBuilder,
    RuntimeComponent,
    RuntimeComponentRole,
    canonical_json_bytes,
    sha256_bytes,
)
from kernel.runtime_bundle_repository import (
    AuditRuntimeBundle,
    AuditRuntimeComponent,
    RuntimeBundleRepository,
    RuntimeBundleRepositoryError,
)
from kernel.store import Store
from kernel.tests.conftest import _admin_dsn


TENANT_REF = "tenant:test.runtime-bundle-repository"
SELECTED_TENANT_REF = "tenant:si.ffs.pilot.demo"
WRONG_TENANT_REF = "tenant:other"
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_TABLE_KEYS = {
    "runtime_content_blob": "content_digest",
    "runtime_tenant_content_blob": "tenant_ref, content_digest",
    "runtime_bundle": "tenant_ref, bundle_digest",
    "runtime_bundle_component": (
        "tenant_ref, bundle_digest, component_role, logical_ref"
    ),
}


@pytest.fixture
def migrated_store():
    """One migrated, unbootstrapped database for immutable-receipt tests."""
    base = os.environ.get("OFARM_PG_DBNAME", "ofarm_kernel_test")
    dbname = f"{base[:38]}_bundle_{uuid.uuid4().hex[:10]}"
    admin_dsn = _admin_dsn()
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    params = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    params["dbname"] = dbname
    store = Store(dsn=psycopg.conninfo.make_conninfo(**params))
    try:
        store.migrate()
        yield store
    finally:
        store.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (dbname,),
            )
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname))
            )


def _component(
    role: RuntimeComponentRole,
    logical_ref: str,
    selected_bytes: bytes,
    *,
    canonicalization: Canonicalization = Canonicalization.EXACT_BYTES,
    placement: ContentPlacement = ContentPlacement.GLOBAL,
) -> RuntimeComponent:
    return RuntimeComponent.from_selected_bytes(
        role=role,
        logical_ref=logical_ref,
        canonicalization=canonicalization,
        placement=placement,
        selected_bytes=selected_bytes,
    )


def _bundle(*components: RuntimeComponent) -> RuntimeBundle:
    return RuntimeBundle.create(components)


def _persist(
    store: Store,
    bundle: RuntimeBundle,
    tenant_ref: str = TENANT_REF,
) -> None:
    repository = RuntimeBundleRepository()
    with store.tx() as cur:
        repository.persist(cur, tenant_ref, bundle)


def _seed_raw_persisted_bundle(
    store: Store,
    *,
    role: RuntimeComponentRole,
    logical_ref: str,
    canonicalization: Canonicalization,
    placement: ContentPlacement,
    selected_bytes: bytes,
) -> str:
    content_digest = sha256_bytes(selected_bytes)
    identity = {
        "role": role.value,
        "logicalRef": logical_ref,
        "canonicalization": canonicalization.value,
        "placement": placement.value,
        "contentDigest": content_digest,
        "byteLength": len(selected_bytes),
    }
    canonical_document_bytes = canonical_json_bytes({
        "schemaVersion": BUNDLE_SCHEMA_VERSION,
        "canonicalization": Canonicalization.CANONICAL_JSON.value,
        "components": [identity],
    })
    bundle_digest = sha256_bytes(canonical_document_bytes)

    with store.tx() as cur:
        if placement is ContentPlacement.GLOBAL:
            cur.execute(
                """
                INSERT INTO runtime_content_blob
                  (content_digest, canonical_bytes, byte_length)
                VALUES (%s, %s, %s)
                """,
                (content_digest, selected_bytes, len(selected_bytes)),
            )
            global_digest, tenant_digest = content_digest, None
        else:
            cur.execute(
                """
                INSERT INTO runtime_tenant_content_blob
                  (tenant_ref, content_digest, canonical_bytes, byte_length)
                VALUES (%s, %s, %s, %s)
                """,
                (TENANT_REF, content_digest, selected_bytes, len(selected_bytes)),
            )
            global_digest, tenant_digest = None, content_digest
        cur.execute(
            """
            INSERT INTO runtime_bundle
              (tenant_ref, bundle_digest, bundle_ref, canonical_bytes, byte_length)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                TENANT_REF,
                bundle_digest,
                f"runtimebundle:{bundle_digest}",
                canonical_document_bytes,
                len(canonical_document_bytes),
            ),
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
                TENANT_REF,
                bundle_digest,
                identity["role"],
                identity["logicalRef"],
                identity["canonicalization"],
                identity["placement"],
                global_digest,
                tenant_digest,
                identity["byteLength"],
            ),
        )
    return bundle_digest


def _seed_raw_bundle_with_replaced_tenant_component(
    store: Store,
    bundle: RuntimeBundle,
    component: RuntimeComponent,
    replacement_bytes: bytes,
) -> str:
    """Retain one malformed tenant component without invoking the model."""
    replacement_digest = sha256_bytes(replacement_bytes)
    identity_document = json.loads(bundle.canonical_document_bytes)
    identity = next(
        item for item in identity_document["components"]
        if (
            item["role"] == component.role.value
            and item["logicalRef"] == component.logical_ref
        )
    )
    identity["contentDigest"] = replacement_digest
    identity["byteLength"] = len(replacement_bytes)
    canonical_document_bytes = canonical_json_bytes(identity_document)
    bundle_digest = sha256_bytes(canonical_document_bytes)

    with store.tx() as cur:
        cur.execute(
            """
            INSERT INTO runtime_tenant_content_blob
              (tenant_ref, content_digest, canonical_bytes, byte_length)
            VALUES (%s, %s, %s, %s)
            """,
            (
                SELECTED_TENANT_REF,
                replacement_digest,
                replacement_bytes,
                len(replacement_bytes),
            ),
        )
        cur.execute(
            """
            INSERT INTO runtime_bundle
              (tenant_ref, bundle_digest, bundle_ref, canonical_bytes, byte_length)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                SELECTED_TENANT_REF,
                bundle_digest,
                f"runtimebundle:{bundle_digest}",
                canonical_document_bytes,
                len(canonical_document_bytes),
            ),
        )
        cur.execute(
            """
            INSERT INTO runtime_bundle_component
              (tenant_ref, bundle_digest, component_role, logical_ref,
               canonicalization, content_placement, global_content_digest,
               tenant_content_digest, byte_length)
            SELECT tenant_ref, %s, component_role, logical_ref,
                   canonicalization, content_placement, global_content_digest,
                   CASE WHEN component_role = %s AND logical_ref = %s
                        THEN %s ELSE tenant_content_digest END,
                   CASE WHEN component_role = %s AND logical_ref = %s
                        THEN %s ELSE byte_length END
            FROM runtime_bundle_component
            WHERE tenant_ref = %s AND bundle_digest = %s
            """,
            (
                bundle_digest,
                component.role.value,
                component.logical_ref,
                replacement_digest,
                component.role.value,
                component.logical_ref,
                len(replacement_bytes),
                SELECTED_TENANT_REF,
                bundle.digest,
            ),
        )
    return bundle_digest


def _snapshot_runtime_tables(store: Store) -> dict[str, tuple[dict, ...]]:
    snapshot: dict[str, tuple[dict, ...]] = {}
    with store.conn.cursor() as cur:
        for table, keys in RUNTIME_TABLE_KEYS.items():
            cur.execute(f"SELECT * FROM {table} ORDER BY {keys}")
            snapshot[table] = tuple(dict(row) for row in cur.fetchall())
    return snapshot


def _count(store: Store, table: str) -> int:
    row = store.conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()
    return row["n"]


def test_persist_and_cold_audit_load_use_only_retained_bytes_and_are_inert(
    migrated_store,
    monkeypatch,
):
    store = migrated_store
    repository = RuntimeBundleRepository()
    bundle = _bundle(
        _component(
            RuntimeComponentRole.ADAPTER_SOURCE,
            "python:test.runtime-bundle-repository:adapter",
            b"def decide():\n    return True\n",
        ),
    )
    _persist(store, bundle)

    def refuse_filesystem_read(_path):
        raise AssertionError("cold RuntimeBundle audit consulted the filesystem")

    monkeypatch.setattr(Path, "read_bytes", refuse_filesystem_read)
    with store.tx() as cur:
        audit = repository.load_for_audit(cur, TENANT_REF, bundle.digest)

    assert type(audit) is AuditRuntimeBundle
    assert not isinstance(audit, RuntimeBundle)
    assert audit.tenant_ref == TENANT_REF
    assert audit.digest == bundle.digest
    assert audit.bundle_ref == bundle.bundle_ref
    assert audit.canonical_document_bytes == bundle.canonical_document_bytes
    assert tuple(
        (
            component.role,
            component.logical_ref,
            component.canonicalization,
            component.placement,
            component.canonical_bytes,
            component.byte_length,
            component.content_digest,
        )
        for component in audit.components
    ) == tuple(
        (
            component.role.value,
            component.logical_ref,
            component.canonicalization.value,
            component.placement.value,
            component.canonical_bytes,
            component.byte_length,
            component.content_digest,
        )
        for component in bundle.components
    )
    assert all(type(component) is AuditRuntimeComponent for component in audit.components)


def test_exact_reinstall_is_idempotent_and_blobs_are_reused_across_roles(
    migrated_store,
):
    store = migrated_store
    shared_bytes = b"shared exact decision-bearing bytes\n"
    adapter = _component(
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:test.runtime-bundle-repository:shared-adapter",
        shared_bytes,
    )
    validator = _component(
        RuntimeComponentRole.VALIDATOR_SOURCE,
        "python:test.runtime-bundle-repository:shared-validator",
        shared_bytes,
    )
    first = _bundle(adapter)
    second = _bundle(adapter, validator)

    _persist(store, first)
    _persist(store, second)
    before_reinstall = _snapshot_runtime_tables(store)

    _persist(store, first)
    _persist(store, second)

    assert _snapshot_runtime_tables(store) == before_reinstall
    assert _count(store, "runtime_content_blob") == 1
    assert _count(store, "runtime_tenant_content_blob") == 0
    assert _count(store, "runtime_bundle") == 2
    assert _count(store, "runtime_bundle_component") == 3


def test_concurrent_exact_persist_waits_for_repository_lock_and_is_idempotent(
    migrated_store,
):
    store = migrated_store
    repository = RuntimeBundleRepository()
    component = _component(
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:test.runtime-bundle-repository:concurrent-exact-reinstall",
        b"one exact retained component\n",
    )
    bundle = _bundle(component)
    second_backend_pids: queue.Queue[int] = queue.Queue()
    second_errors: queue.Queue[BaseException] = queue.Queue()
    second_finished = threading.Event()
    first_install_snapshot = None

    def install_on_second_connection() -> None:
        try:
            with psycopg.connect(
                store.dsn,
                row_factory=psycopg.rows.dict_row,
                autocommit=True,
            ) as connection:
                second_backend_pids.put(connection.info.backend_pid)
                with connection.transaction():
                    with connection.cursor() as cur:
                        repository.persist(cur, TENANT_REF, bundle)
        except BaseException as exc:
            second_errors.put(exc)
        finally:
            second_finished.set()

    second_thread = None
    try:
        with store.tx() as first_cur:
            repository.persist(first_cur, TENANT_REF, bundle)

            second_thread = threading.Thread(target=install_on_second_connection)
            second_thread.start()
            second_pid = second_backend_pids.get(timeout=5)

            expected_lock_state = {
                "holder_mode": "ExclusiveLock",
                "waiter_mode": "ExclusiveLock",
                "wait_event_type": "Lock",
                "wait_event": "advisory",
            }
            lock_state = None
            deadline = time.monotonic() + 5
            while lock_state != expected_lock_state and time.monotonic() < deadline:
                first_cur.execute(
                    """
                    SELECT holder.mode AS holder_mode,
                           waiter.mode AS waiter_mode,
                           activity.wait_event_type,
                           activity.wait_event
                    FROM pg_locks AS holder
                    JOIN pg_locks AS waiter
                      ON waiter.locktype = holder.locktype
                     AND waiter.database IS NOT DISTINCT FROM holder.database
                     AND waiter.classid IS NOT DISTINCT FROM holder.classid
                     AND waiter.objid IS NOT DISTINCT FROM holder.objid
                     AND waiter.objsubid IS NOT DISTINCT FROM holder.objsubid
                    JOIN pg_stat_activity AS activity ON activity.pid = waiter.pid
                    WHERE holder.pid = pg_backend_pid()
                      AND holder.locktype = 'advisory'
                      AND holder.granted
                      AND waiter.pid = %s
                      AND NOT waiter.granted
                    """,
                    (second_pid,),
                )
                lock_state = first_cur.fetchone()

            assert lock_state == expected_lock_state
            assert not second_finished.is_set()
            first_install_snapshot = _snapshot_runtime_tables(store)
    finally:
        if second_thread is not None:
            assert second_finished.wait(timeout=5)
            second_thread.join(timeout=5)
            assert not second_thread.is_alive()

    try:
        second_error = second_errors.get_nowait()
    except queue.Empty:
        pass
    else:
        raise second_error

    with store.tx() as cur:
        audit = repository.load_for_audit(cur, TENANT_REF, bundle.digest)

    assert first_install_snapshot is not None
    assert _snapshot_runtime_tables(store) == first_install_snapshot
    assert audit is not None
    assert audit.tenant_ref == TENANT_REF
    assert audit.digest == bundle.digest
    assert audit.bundle_ref == bundle.bundle_ref
    assert audit.canonical_document_bytes == bundle.canonical_document_bytes
    assert audit.components == (
        AuditRuntimeComponent(
            role=component.role.value,
            logical_ref=component.logical_ref,
            canonicalization=component.canonicalization.value,
            placement=component.placement.value,
            canonical_bytes=component.canonical_bytes,
            byte_length=component.byte_length,
            content_digest=component.content_digest,
        ),
    )
    assert _count(store, "runtime_content_blob") == 1
    assert _count(store, "runtime_tenant_content_blob") == 0
    assert _count(store, "runtime_bundle") == 1
    assert _count(store, "runtime_bundle_component") == 1


def test_changed_bytes_behind_a_stable_ref_create_a_new_auditable_bundle(
    migrated_store,
):
    store = migrated_store
    repository = RuntimeBundleRepository()
    validator_ref = "python:test.runtime-bundle-repository:fixed-validator"
    first = _bundle(
        _component(
            RuntimeComponentRole.VALIDATOR_SOURCE,
            validator_ref,
            b"validator version one\n",
        )
    )
    second = _bundle(
        _component(
            RuntimeComponentRole.VALIDATOR_SOURCE,
            validator_ref,
            b"validator version two\n",
        ),
    )

    _persist(store, first)
    _persist(store, second)

    with store.tx() as cur:
        first_audit = repository.load_for_audit(cur, TENANT_REF, first.digest)
        second_audit = repository.load_for_audit(cur, TENANT_REF, second.digest)

    assert first_audit is not None
    assert second_audit is not None
    assert first_audit.components[0].canonical_bytes == b"validator version one\n"
    assert second_audit.components[0].canonical_bytes == b"validator version two\n"
    assert first.digest != second.digest


def test_content_conflict_rolls_back_partial_rows_but_not_the_caller_transaction(
    migrated_store,
):
    store = migrated_store
    repository = RuntimeBundleRepository()
    earlier = _component(
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:test.runtime-bundle-repository:new-before-conflict",
        b"new component that must roll back\n",
    )
    conflicting = _component(
        RuntimeComponentRole.VALIDATOR_SOURCE,
        "python:test.runtime-bundle-repository:colliding-content-id",
        b"the bytes selected by the new bundle\n",
    )
    bundle = _bundle(earlier, conflicting)
    with store.tx() as cur:
        cur.execute(
            """
            INSERT INTO runtime_content_blob
              (content_digest, canonical_bytes, byte_length)
            VALUES (%s, %s, %s)
            """,
            (conflicting.content_digest, b"unequal retained bytes", 22),
        )
    before_conflict = _snapshot_runtime_tables(store)

    with store.tx() as cur:
        with pytest.raises(RuntimeBundleRepositoryError, match="reused with unequal bytes"):
            repository.persist(cur, TENANT_REF, bundle)
        cur.execute("SELECT 1")

    assert _snapshot_runtime_tables(store) == before_conflict
    with store.tx() as cur:
        assert repository.load_for_audit(cur, TENANT_REF, bundle.digest) is None


def test_cold_audit_refuses_an_incomplete_persisted_component_set(migrated_store):
    store = migrated_store
    repository = RuntimeBundleRepository()
    bundle = _bundle(
        _component(
            RuntimeComponentRole.QUERY_OUTPUT_SOURCE,
            "python:test.runtime-bundle-repository:incomplete",
            b"retained bytes were never linked\n",
        )
    )
    with store.tx() as cur:
        cur.execute(
            """
            INSERT INTO runtime_bundle
              (tenant_ref, bundle_digest, bundle_ref, canonical_bytes, byte_length)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                TENANT_REF,
                bundle.digest,
                bundle.bundle_ref,
                bundle.canonical_document_bytes,
                len(bundle.canonical_document_bytes),
            ),
        )

    with pytest.raises(
        RuntimeBundleRepositoryError,
        match="persisted RuntimeBundle model is invalid",
    ):
        with store.tx() as cur:
            repository.load_for_audit(cur, TENANT_REF, bundle.digest)


def test_cold_audit_refuses_structurally_valid_semantically_invalid_component(
    migrated_store,
):
    store = migrated_store
    repository = RuntimeBundleRepository()
    bundle_digest = _seed_raw_persisted_bundle(
        store,
        role=RuntimeComponentRole.ACTIVE_MANIFEST,
        logical_ref="manifest:test.invalid-cold.v1",
        canonicalization=Canonicalization.EXACT_BYTES,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=b"not-json",
    )

    with pytest.raises(
        RuntimeBundleRepositoryError,
        match=(
            "persisted RuntimeBundle model is invalid: "
            "ACTIVE_MANIFEST must use canonical JSON"
        ),
    ):
        with store.tx() as cur:
            repository.load_for_audit(cur, TENANT_REF, bundle_digest)


def test_cold_audit_refuses_semantically_incomplete_persisted_bundle(
    migrated_store,
):
    store = migrated_store
    repository = RuntimeBundleRepository()
    manifest_ref = "manifest:test.incomplete-cold.v1"
    bundle_digest = _seed_raw_persisted_bundle(
        store,
        role=RuntimeComponentRole.ACTIVE_MANIFEST,
        logical_ref=manifest_ref,
        canonicalization=Canonicalization.CANONICAL_JSON,
        placement=ContentPlacement.TENANT,
        selected_bytes=canonical_json_bytes({
            "schemaVersion": "ofarm.capabilitymanifest.v0.1",
            "manifestId": manifest_ref,
        }),
    )

    with pytest.raises(
        RuntimeBundleRepositoryError,
        match=(
            "persisted RuntimeBundle model is invalid: "
            "active profile components require one profile descriptor"
        ),
    ):
        with store.tx() as cur:
            repository.load_for_audit(cur, TENANT_REF, bundle_digest)


def test_cold_audit_refuses_malformed_context_anchor_scope_members(
    migrated_store,
):
    store = migrated_store
    repository = RuntimeBundleRepository()
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()
    _persist(store, bundle, SELECTED_TENANT_REF)
    context = next(
        component for component in bundle.components
        if (
            component.role is RuntimeComponentRole.PROFILE_INSTANCE
            and component.logical_ref.startswith("contextsnapshot:")
        )
    )
    context_document = json.loads(context.canonical_bytes)
    context_document["anchorScopes"] = [
        17,
        {
            "scopeType": "TENANT",
            "scopeRef": SELECTED_TENANT_REF,
        },
    ]
    malformed_digest = _seed_raw_bundle_with_replaced_tenant_component(
        store,
        bundle,
        context,
        canonical_json_bytes(context_document),
    )
    before_audit = _snapshot_runtime_tables(store)

    with store.tx() as cur:
        with pytest.raises(
            RuntimeBundleRepositoryError,
            match=(
                "persisted RuntimeBundle model is invalid: "
                "ContextSnapshot anchorScopes are malformed"
            ),
        ):
            repository.load_for_audit(
                cur,
                SELECTED_TENANT_REF,
                malformed_digest,
            )
        cur.execute("SELECT 1")

    assert _snapshot_runtime_tables(store) == before_audit


def test_persist_requires_an_active_caller_transaction(migrated_store):
    store = migrated_store
    bundle = _bundle(
        _component(
            RuntimeComponentRole.ADAPTER_SOURCE,
            "python:test.runtime-bundle-repository:transaction-required",
            b"selected bytes\n",
        )
    )

    with store.conn.cursor() as cur:
        with pytest.raises(RuntimeBundleRepositoryError, match="active caller transaction"):
            RuntimeBundleRepository().persist(cur, TENANT_REF, bundle)

    assert _snapshot_runtime_tables(store) == {
        table: () for table in RUNTIME_TABLE_KEYS
    }


def test_repository_and_sql_refuse_non_tenant_storage_keys(migrated_store):
    store = migrated_store
    repository = RuntimeBundleRepository()
    bundle = _bundle(_component(
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:test.runtime-bundle-repository:tenant-ref",
        b"selected bytes\n",
    ))
    invalid_refs = ("x", "farm:x", "tenant:", "tenant:" + "a" * 249)
    before = _snapshot_runtime_tables(store)

    with store.tx() as cur:
        for invalid_ref in invalid_refs:
            with pytest.raises(RuntimeBundleRepositoryError, match="must be tenant:"):
                repository.persist(cur, invalid_ref, bundle)
            with pytest.raises(RuntimeBundleRepositoryError, match="must be tenant:"):
                repository.load_for_audit(cur, invalid_ref, bundle.digest)
        cur.execute("SELECT 1")

    digest = sha256_bytes(b"{}")
    for invalid_ref in invalid_refs:
        with pytest.raises(psycopg.errors.CheckViolation):
            with store.tx() as cur:
                cur.execute(
                    """
                    INSERT INTO runtime_tenant_content_blob
                      (tenant_ref, content_digest, canonical_bytes, byte_length)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (invalid_ref, digest, b"{}", 2),
                )
        with pytest.raises(psycopg.errors.CheckViolation):
            with store.tx() as cur:
                cur.execute(
                    """
                    INSERT INTO runtime_bundle
                      (tenant_ref, bundle_digest, bundle_ref,
                       canonical_bytes, byte_length)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (invalid_ref, digest, f"runtimebundle:{digest}", b"{}", 2),
                )

    assert _snapshot_runtime_tables(store) == before


def test_persist_refuses_a_bundle_under_another_tenant_without_writes(
    migrated_store,
):
    store = migrated_store
    repository = RuntimeBundleRepository()
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()
    before = _snapshot_runtime_tables(store)

    with store.tx() as cur:
        with pytest.raises(
            RuntimeBundleRepositoryError,
            match="does not match bundle-selected tenant",
        ):
            repository.persist(cur, WRONG_TENANT_REF, bundle)
        cur.execute("SELECT 1")

    assert _snapshot_runtime_tables(store) == before


def test_checked_in_bundle_persists_every_selected_role(migrated_store):
    store = migrated_store
    repository = RuntimeBundleRepository()
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()

    with store.tx() as cur:
        repository.persist(cur, SELECTED_TENANT_REF, bundle)
        audit = repository.load_for_audit(
            cur, SELECTED_TENANT_REF, bundle.digest
        )

    assert audit is not None
    assert len(audit.components) == len(bundle.components) == 90
    assert sum(
        component.role == RuntimeComponentRole.VIEW_BINDING.value
        for component in audit.components
    ) == 2


def test_cold_audit_refuses_a_raw_bundle_stored_under_another_tenant(
    migrated_store,
):
    store = migrated_store
    repository = RuntimeBundleRepository()
    bundle = RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build()
    _persist(store, bundle, SELECTED_TENANT_REF)

    with store.tx() as cur:
        cur.execute(
            """
            INSERT INTO runtime_tenant_content_blob
              (tenant_ref, content_digest, canonical_bytes, byte_length)
            SELECT %s, content_digest, canonical_bytes, byte_length
            FROM runtime_tenant_content_blob
            WHERE tenant_ref = %s
            """,
            (WRONG_TENANT_REF, SELECTED_TENANT_REF),
        )
        cur.execute(
            """
            INSERT INTO runtime_bundle
              (tenant_ref, bundle_digest, bundle_ref, canonical_bytes, byte_length)
            SELECT %s, bundle_digest, bundle_ref, canonical_bytes, byte_length
            FROM runtime_bundle
            WHERE tenant_ref = %s AND bundle_digest = %s
            """,
            (WRONG_TENANT_REF, SELECTED_TENANT_REF, bundle.digest),
        )
        cur.execute(
            """
            INSERT INTO runtime_bundle_component
              (tenant_ref, bundle_digest, component_role, logical_ref,
               canonicalization, content_placement, global_content_digest,
               tenant_content_digest, byte_length)
            SELECT %s, bundle_digest, component_role, logical_ref,
                   canonicalization, content_placement, global_content_digest,
                   tenant_content_digest, byte_length
            FROM runtime_bundle_component
            WHERE tenant_ref = %s AND bundle_digest = %s
            """,
            (WRONG_TENANT_REF, SELECTED_TENANT_REF, bundle.digest),
        )
    before_audit = _snapshot_runtime_tables(store)

    with store.tx() as cur:
        with pytest.raises(
            RuntimeBundleRepositoryError,
            match="does not match bundle-selected tenant",
        ):
            repository.load_for_audit(cur, WRONG_TENANT_REF, bundle.digest)
        cur.execute("SELECT 1")

    assert _snapshot_runtime_tables(store) == before_audit


def test_cold_audit_refuses_cross_tenant_bundle_digest_byte_reuse(migrated_store):
    store = migrated_store
    repository = RuntimeBundleRepository()
    bundle = _bundle(
        _component(
            RuntimeComponentRole.ADAPTER_SOURCE,
            "python:test.runtime-bundle-repository:cross-tenant-digest",
            b"the valid retained component\n",
        )
    )
    _persist(store, bundle)
    with store.tx() as cur:
        cur.execute(
            """
            INSERT INTO runtime_bundle
              (tenant_ref, bundle_digest, bundle_ref, canonical_bytes, byte_length)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                "tenant:test.runtime-bundle-repository.other",
                bundle.digest,
                bundle.bundle_ref,
                b"{}",
                2,
            ),
        )

    with store.tx() as cur:
        with pytest.raises(RuntimeBundleRepositoryError, match="reused with unequal bytes"):
            repository.load_for_audit(cur, TENANT_REF, bundle.digest)


def test_cold_audit_refuses_cross_carrier_component_digest_byte_reuse(
    migrated_store,
):
    store = migrated_store
    repository = RuntimeBundleRepository()
    component = _component(
        RuntimeComponentRole.ADAPTER_SOURCE,
        "python:test.runtime-bundle-repository:cross-carrier-digest",
        b"the valid globally retained bytes\n",
    )
    bundle = _bundle(component)
    _persist(store, bundle)
    with store.tx() as cur:
        cur.execute(
            """
            INSERT INTO runtime_tenant_content_blob
              (tenant_ref, content_digest, canonical_bytes, byte_length)
            VALUES (%s, %s, %s, %s)
            """,
            (
                "tenant:test.runtime-bundle-repository.other",
                component.content_digest,
                b"unequal bytes",
                len(b"unequal bytes"),
            ),
        )

    with store.tx() as cur:
        with pytest.raises(RuntimeBundleRepositoryError, match="reused with unequal bytes"):
            repository.load_for_audit(cur, TENANT_REF, bundle.digest)


@pytest.mark.parametrize("table", tuple(RUNTIME_TABLE_KEYS))
def test_runtime_bundle_tables_refuse_update_delete_and_truncate(
    migrated_store,
    table,
):
    store = migrated_store
    _persist(
        store,
        RuntimeBundleBuilder.from_manifest(PACKAGE_ROOT).build(),
        SELECTED_TENANT_REF,
    )
    before = _snapshot_runtime_tables(store)
    mutations = (
        ("UPDATE", sql.SQL("UPDATE {} SET byte_length = byte_length")),
        ("DELETE", sql.SQL("DELETE FROM {}")),
        ("TRUNCATE", sql.SQL("TRUNCATE TABLE {} CASCADE")),
    )

    for operation, template in mutations:
        statement = template.format(sql.Identifier(table))
        with pytest.raises(psycopg.errors.RaiseException, match="append-only") as exc_info:
            with store.tx() as cur:
                cur.execute(statement)
        message = str(exc_info.value)
        assert operation in message
        assert table in message
        assert _snapshot_runtime_tables(store) == before
