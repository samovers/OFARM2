"""Exact schema identity and startup-only database posture tests."""
from __future__ import annotations

import psycopg
import pytest

from kernel import config
from kernel.api import create_app
from kernel.runtime_bundle import (
    Canonicalization,
    ContentPlacement,
    RuntimeBundle,
    RuntimeComponent,
    RuntimeComponentRole,
    canonical_json_bytes,
    sha256_bytes,
)
from kernel.schema_posture import SchemaPostureError, install_or_verify_schema
from kernel.store import Store


def _counts(store) -> dict[str, int]:
    return {
        table: store.conn.execute(
            f"SELECT count(*) AS count FROM {table}"
        ).fetchone()["count"]
        for table in ("runtime_bundle", "runtime_bundle_component", "kernel_record")
    }


def test_schema_identity_is_the_digest_of_exact_schema_sql_bytes(fresh_env):
    store, _, _ = fresh_env
    schema_bytes = (config.PACKAGE_ROOT / "kernel" / "schema.sql").read_bytes()
    expected = sha256_bytes(schema_bytes)

    observation = store.migrate()
    identity = store.conn.execute(
        "SELECT identity_key, schema_digest, catalog_manifest, catalog_digest "
        "FROM runtime_schema_identity"
    ).fetchone()

    assert identity["identity_key"] == "ofarm-kernel-schema"
    assert identity["schema_digest"] == expected
    assert identity["catalog_manifest"]["manifestVersion"] == \
        "ofarm.postgresql-schema-catalog.local.v1"
    assert identity["catalog_digest"] == sha256_bytes(
        canonical_json_bytes(identity["catalog_manifest"])
    )
    assert observation.schema_digest == expected
    assert observation.current_schema == "public"
    assert observation.transaction_isolation == "read committed"
    assert observation.transaction_read_only == "off"
    assert observation.transaction_deferrable == "off"


def test_healthy_restart_exactly_reuses_the_installed_schema_catalog(fresh_env):
    store, _, _ = fresh_env
    before_identity = store.conn.execute(
        "SELECT to_jsonb(i) AS identity FROM runtime_schema_identity AS i"
    ).fetchone()["identity"]
    before_counts = _counts(store)
    restarted = Store(
        dsn=store.dsn,
        tenant_ref=store.tenant_ref,
        runtime_bundle=store.runtime_bundle,
        active_descriptor=store.active_descriptor,
    )
    try:
        observation = restarted.migrate()
        after_identity = restarted.conn.execute(
            "SELECT to_jsonb(i) AS identity FROM runtime_schema_identity AS i"
        ).fetchone()["identity"]
        assert after_identity == before_identity
        assert observation.schema_digest == before_identity["schema_digest"]
        assert _counts(restarted) == before_counts
    finally:
        restarted.close()


def test_live_schema_drift_refuses_before_bundle_or_profile_mutation(fresh_env):
    store, _, _ = fresh_env
    marker = RuntimeComponent.from_selected_bytes(
        role=RuntimeComponentRole.ADAPTER_SOURCE,
        logical_ref="python:test.schema-posture:restart-marker",
        canonicalization=Canonicalization.EXACT_BYTES,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=b"# schema-drift restart marker\n",
    )
    replacement_bundle = RuntimeBundle.create(
        (*store.runtime_bundle.components, marker)
    )
    restarted = Store(
        dsn=store.dsn,
        tenant_ref=store.tenant_ref,
        runtime_bundle=replacement_bundle,
        active_descriptor=store.active_descriptor,
    )
    before_counts = _counts(store)
    store.conn.execute(
        "DROP TRIGGER trg_kernel_record_append_only ON kernel_record"
    )
    try:
        with pytest.raises(
            SchemaPostureError,
            match="live database schema catalog does not match",
        ):
            create_app(restarted, oidc=None)

        assert _counts(store) == before_counts
        assert store.conn.execute(
            "SELECT count(*) AS count FROM runtime_bundle "
            "WHERE bundle_digest = %s",
            (replacement_bundle.digest,),
        ).fetchone()["count"] == 0
    finally:
        restarted.close()


def test_different_schema_bytes_refuse_before_bundle_or_record_mutation(fresh_env):
    store, _, _ = fresh_env
    schema_bytes = (config.PACKAGE_ROOT / "kernel" / "schema.sql").read_bytes()
    before = _counts(store)

    with pytest.raises(SchemaPostureError, match="digest does not match"):
        with store.tx() as cur:
            install_or_verify_schema(cur, schema_bytes + b"\n")

    assert _counts(store) == before


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE runtime_schema_identity SET schema_digest = schema_digest",
        "DELETE FROM runtime_schema_identity",
        "TRUNCATE runtime_schema_identity",
    ],
)
def test_schema_identity_is_append_only(fresh_env, statement):
    store, _, _ = fresh_env
    with pytest.raises(psycopg.errors.RaiseException):
        with store.tx() as cur:
            cur.execute(statement)
