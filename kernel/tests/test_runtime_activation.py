"""Process-local activation observations for issue #171."""
from __future__ import annotations

import json

import psycopg
import pytest
from fastapi.testclient import TestClient

from kernel import config
from kernel.adapters import ImportRunner
from kernel.deployment_identity import RuntimeActivationError
from kernel.legacy_m1.api import create_test_app
from kernel.gates import GatePipeline
from kernel.profile_runtime_provider import load_profile_runtime_services
from kernel.runtime_activation import complete_store_startup
from kernel.runtime_bundle import RuntimeComponentRole, sha256_bytes
from kernel.schema_posture import SchemaPostureError
from kernel.store import RuntimeBundleBindingError, Store
from kernel.tests.conftest import TEST_DEPLOYMENT_IMAGE_DIGEST


def _output_assembler(store):
    return load_profile_runtime_services(
        store,
        store.active_profile_package_name,
        store.active_descriptor,
    ).output_assembler


class _NoDatabaseAccess:
    @property
    def conn(self):
        raise AssertionError("invalid deployment identity reached the database")


@pytest.mark.parametrize(
    "value",
    [None, "", "sha256:abc", "sha256:" + "A" * 64, "sha512:" + "a" * 64],
)
def test_invalid_deployment_identity_refuses_before_database_access(value):
    with pytest.raises(RuntimeActivationError, match="deployment image digest"):
        create_test_app(
            _NoDatabaseAccess(),
            oidc=None,
            deployment_image_digest=value,
        )


def test_deployment_observation_does_not_change_runtime_bundle_identity(fresh_env):
    store, _, _ = fresh_env
    first = create_test_app(
        store, oidc=None, deployment_image_digest="sha256:" + "1" * 64
    )
    second = create_test_app(
        store, oidc=None, deployment_image_digest="sha256:" + "2" * 64
    )

    assert first.state.runtime_metadata.runtime_bundle_digest == \
        second.state.runtime_metadata.runtime_bundle_digest
    assert first.state.runtime_metadata.deployment_image_digest != \
        second.state.runtime_metadata.deployment_image_digest
    assert store.runtime_bundle.digest == \
        first.state.runtime_metadata.runtime_bundle_digest


def test_health_reports_committed_bundle_deployment_and_schema_observations(fresh_env):
    store, _, _ = fresh_env
    app = create_test_app(
        store,
        oidc=None,
        deployment_image_digest=TEST_DEPLOYMENT_IMAGE_DIGEST,
    )
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    activation = response.json()["runtimeActivation"]
    assert activation["tenantRef"] == store.tenant_ref
    assert activation["activeProfileRef"] == store.active_descriptor.profile_ref
    assert activation["runtimeBundleDigest"] == store.runtime_bundle_digest
    assert activation["deploymentImageDigest"] == TEST_DEPLOYMENT_IMAGE_DIGEST
    assert activation["database"] == {
        "schemaDigest": sha256_bytes(
            (config.PACKAGE_ROOT / "kernel" / "schema.sql").read_bytes()
        ),
        "currentSchema": "public",
        "transactionIsolation": "read committed",
        "transactionReadOnly": "off",
        "transactionDeferrable": "off",
        "timezone": "UTC",
        "searchPath": "public, pg_catalog",
        "synchronousCommit": "on",
    }


def test_manifest_endpoint_matches_the_selected_bundle_bytes(fresh_env):
    store, _, _ = fresh_env
    component = next(
        item for item in store.runtime_bundle.components
        if item.role is RuntimeComponentRole.ACTIVE_MANIFEST
    )
    with TestClient(create_test_app(store, oidc=None)) as client:
        response = client.get("/manifest")

    assert response.status_code == 200
    assert response.json() == json.loads(component.canonical_bytes)


def test_high_level_services_require_committed_store_startup(fresh_env):
    ready, _, _ = fresh_env
    store = Store(
        dsn=ready.dsn,
        tenant_ref=ready.tenant_ref,
        runtime_bundle=ready.runtime_bundle,
        active_descriptor=ready.active_descriptor,
    )
    try:
        store.conn
        for service in (GatePipeline, ImportRunner, _output_assembler):
            with pytest.raises(
                RuntimeBundleBindingError,
                match="requires completed schema, bundle, and profile startup",
            ):
                service(store)

        complete_store_startup(store)
        GatePipeline(store)
        ImportRunner(store)
        _output_assembler(store)
    finally:
        store.close()


def test_unstarted_store_refuses_receipted_writes_against_initialized_database(
    fresh_env,
):
    ready, _, _ = fresh_env
    store = Store(
        dsn=ready.dsn,
        tenant_ref=ready.tenant_ref,
        runtime_bundle=ready.runtime_bundle,
        active_descriptor=ready.active_descriptor,
    )
    record_marker = "record:test-unstarted-store"
    gate_marker = "request:test-unstarted-store"
    try:
        with pytest.raises(
            RuntimeBundleBindingError,
            match="requires completed schema, bundle, and profile startup",
        ):
            with store.serialized_tx() as cur:
                store.log_gate(
                    cur,
                    gate_marker,
                    "STARTUP_BOUNDARY",
                    "REFUSE",
                )

        with store.tx() as cur:
            with pytest.raises(
                RuntimeBundleBindingError,
                match="requires completed schema, bundle, and profile startup",
            ):
                store.insert_record(cur, {"assertionId": record_marker})

        assert ready.conn.execute(
            "SELECT count(*) AS count FROM kernel_gate_log "
            "WHERE request_id = %s",
            (gate_marker,),
        ).fetchone()["count"] == 0
        assert ready.conn.execute(
            "SELECT count(*) AS count FROM kernel_record WHERE record_id = %s",
            (record_marker,),
        ).fetchone()["count"] == 0
    finally:
        store.close()


def test_failed_store_startup_poisoned_after_closed_connection(fresh_env):
    ready, _, _ = fresh_env
    store = Store(
        dsn=ready.dsn,
        tenant_ref=ready.tenant_ref,
        runtime_bundle=ready.runtime_bundle,
        active_descriptor=ready.active_descriptor,
    )
    try:
        store.conn
        store.close()
        with pytest.raises(
            RuntimeBundleBindingError,
            match="database connection is closed",
        ):
            complete_store_startup(store)
        for service in (GatePipeline, ImportRunner, _output_assembler):
            with pytest.raises(RuntimeBundleBindingError, match="poisoned"):
                service(store)
        with pytest.raises(RuntimeBundleBindingError, match="poisoned"):
            complete_store_startup(store)
    finally:
        store.close()


def test_nested_startup_cannot_publish_readiness_before_outer_rollback(
    fresh_env,
):
    ready, _, _ = fresh_env
    store = Store(
        dsn=ready.dsn,
        tenant_ref=ready.tenant_ref,
        runtime_bundle=ready.runtime_bundle,
        active_descriptor=ready.active_descriptor,
    )
    tables = ("runtime_bundle", "runtime_bundle_component", "kernel_record")
    before = {
        table: ready.conn.execute(
            f"SELECT count(*) AS count FROM {table}"
        ).fetchone()["count"]
        for table in tables
    }
    startup_error = None

    class OuterRollback(Exception):
        pass

    try:
        with pytest.raises(OuterRollback):
            with store.tx():
                try:
                    complete_store_startup(store)
                except RuntimeBundleBindingError as exc:
                    startup_error = exc
                raise OuterRollback

        assert startup_error is not None
        assert "must own the outermost database transaction" in str(startup_error)
        with pytest.raises(RuntimeBundleBindingError, match="poisoned"):
            complete_store_startup(store)
        with pytest.raises(RuntimeBundleBindingError, match="poisoned"):
            with store.serialized_tx():
                pytest.fail("nested startup published readiness before outer rollback")

        after = {
            table: ready.conn.execute(
                f"SELECT count(*) AS count FROM {table}"
            ).fetchone()["count"]
            for table in tables
        }
        assert after == before
    finally:
        store.close()


def test_failed_repeat_startup_poisoned_after_live_schema_drift(fresh_env):
    store, _, _ = fresh_env
    store.conn.execute(
        "DROP TRIGGER trg_kernel_record_append_only ON kernel_record"
    )
    tables = ("runtime_bundle", "runtime_bundle_component", "kernel_record")
    before = {
        table: store.conn.execute(
            f"SELECT count(*) AS count FROM {table}"
        ).fetchone()["count"]
        for table in tables
    }

    with pytest.raises(
        SchemaPostureError,
        match="live database schema catalog does not match",
    ):
        complete_store_startup(store)

    after = {
        table: store.conn.execute(
            f"SELECT count(*) AS count FROM {table}"
        ).fetchone()["count"]
        for table in tables
    }
    assert after == before
    for service in (GatePipeline, ImportRunner, _output_assembler):
        with pytest.raises(RuntimeBundleBindingError, match="poisoned"):
            service(store)
    with pytest.raises(RuntimeBundleBindingError, match="poisoned"):
        complete_store_startup(store)
    with pytest.raises(RuntimeBundleBindingError, match="poisoned"):
        with store.serialized_tx():
            pytest.fail("poisoned Store opened a governed transaction")


def test_schema_and_bundle_migration_is_kernel_startup_only(fresh_env):
    store, _, _ = fresh_env

    assert not hasattr(Store, "migrate")
    with pytest.raises(
        RuntimeBundleBindingError,
        match="requires an active Store startup transaction",
    ):
        store._migrate_during_startup()


def test_startup_record_writer_refuses_outside_active_startup(fresh_env):
    store, _, _ = fresh_env
    marker = "record:test-startup-writer-outside-startup"

    with store.tx() as cur:
        with pytest.raises(
            RuntimeBundleBindingError,
            match="requires an active Store startup transaction",
        ):
            store._insert_startup_record(cur, {"assertionId": marker})

    assert store.conn.execute(
        "SELECT count(*) AS count FROM kernel_record WHERE record_id = %s",
        (marker,),
    ).fetchone()["count"] == 0


def test_closed_verified_connection_refuses_before_governed_mutation(fresh_env):
    store, _, _ = fresh_env
    create_test_app(
        store,
        oidc=None,
        deployment_image_digest=TEST_DEPLOYMENT_IMAGE_DIGEST,
    )
    marker = "request:test-closed-verified-connection"

    with psycopg.connect(store.dsn, autocommit=True) as observer:
        assert observer.execute(
            "SELECT count(*) FROM kernel_gate_log WHERE request_id = %s",
            (marker,),
        ).fetchone()[0] == 0

        store.close()
        with pytest.raises(
            RuntimeBundleBindingError,
            match="database connection is closed",
        ):
            with store.serialized_tx() as cur:
                store.log_gate(
                    cur,
                    marker,
                    "CONNECTION_LIFECYCLE",
                    "REFUSE",
                )

        assert observer.execute(
            "SELECT count(*) FROM kernel_gate_log WHERE request_id = %s",
            (marker,),
        ).fetchone()[0] == 0
