"""Process-local activation observations for issue #171."""
from __future__ import annotations

import json

import psycopg
import pytest
from fastapi.testclient import TestClient

from kernel import config
from kernel.adapters import ImportRunner
from kernel.api import create_test_app
from kernel.gates import GatePipeline
from kernel.runtime_activation import (
    DEPLOYMENT_IMAGE_DIGEST_ENV,
    RuntimeActivationError,
    complete_store_startup,
)
from kernel.runtime_bundle import RuntimeComponentRole, sha256_bytes
from kernel.store import RuntimeBundleBindingError, Store
from kernel.tests.conftest import TEST_DEPLOYMENT_IMAGE_DIGEST
from kernel.views import OutputGenerator


class _NoDatabaseAccess:
    @property
    def conn(self):
        raise AssertionError("invalid deployment identity reached the database")


@pytest.mark.parametrize(
    "value",
    [None, "", "sha256:abc", "sha256:" + "A" * 64, "sha512:" + "a" * 64],
)
def test_invalid_deployment_identity_refuses_before_database_access(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(DEPLOYMENT_IMAGE_DIGEST_ENV, raising=False)
    else:
        monkeypatch.setenv(DEPLOYMENT_IMAGE_DIGEST_ENV, value)

    with pytest.raises(RuntimeActivationError, match="required|deployment image digest"):
        create_test_app(_NoDatabaseAccess(), oidc=None)


def test_deployment_observation_does_not_change_runtime_bundle_identity(fresh_env):
    store, _, _ = fresh_env
    first = create_test_app(
        store, oidc=None, deployment_image_digest="sha256:" + "1" * 64
    )
    second = create_test_app(
        store, oidc=None, deployment_image_digest="sha256:" + "2" * 64
    )

    assert first.state.runtime_activation.runtime_bundle_digest == \
        second.state.runtime_activation.runtime_bundle_digest
    assert first.state.runtime_activation.deployment_image_digest != \
        second.state.runtime_activation.deployment_image_digest
    assert store.runtime_bundle.digest == \
        first.state.runtime_activation.runtime_bundle_digest


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
        for service in (GatePipeline, ImportRunner, OutputGenerator):
            with pytest.raises(
                RuntimeBundleBindingError,
                match="requires completed schema, bundle, and profile startup",
            ):
                service(store)

        complete_store_startup(store)
        GatePipeline(store)
        ImportRunner(store)
        OutputGenerator(store)
    finally:
        store.close()


def test_failed_store_startup_does_not_publish_service_readiness(
    fresh_env, monkeypatch
):
    ready, _, _ = fresh_env
    store = Store(
        dsn=ready.dsn,
        tenant_ref=ready.tenant_ref,
        runtime_bundle=ready.runtime_bundle,
        active_descriptor=ready.active_descriptor,
    )

    def refuse_bootstrap(_store):
        raise RuntimeError("fictional startup refusal")

    monkeypatch.setattr("kernel.context.bootstrap", refuse_bootstrap)
    try:
        with pytest.raises(RuntimeError, match="fictional startup refusal"):
            complete_store_startup(store)
        for service in (GatePipeline, ImportRunner, OutputGenerator):
            with pytest.raises(RuntimeBundleBindingError):
                service(store)
    finally:
        store.close()


def test_failed_repeat_startup_preserves_prior_committed_readiness(
    fresh_env, monkeypatch
):
    store, _, _ = fresh_env

    def refuse_bootstrap(_store):
        raise RuntimeError("fictional repeat startup refusal")

    monkeypatch.setattr("kernel.context.bootstrap", refuse_bootstrap)
    with pytest.raises(RuntimeError, match="fictional repeat startup refusal"):
        complete_store_startup(store)

    GatePipeline(store)
    ImportRunner(store)
    OutputGenerator(store)


def test_closed_verified_connection_refuses_before_governed_mutation(fresh_env):
    store, _, _ = fresh_env
    app = create_test_app(
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
            with app.state.store.serialized_tx() as cur:
                app.state.store.log_gate(
                    cur,
                    marker,
                    "CONNECTION_LIFECYCLE",
                    "REFUSE",
                )

        assert observer.execute(
            "SELECT count(*) FROM kernel_gate_log WHERE request_id = %s",
            (marker,),
        ).fetchone()[0] == 0
