"""Exact schema identity and startup-only database posture tests."""
from __future__ import annotations

import uuid

import psycopg
import psycopg.conninfo
import pytest
from psycopg import sql

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
from kernel.tests.conftest import _admin_dsn


def _counts(store) -> dict[str, int]:
    return {
        table: store.conn.execute(
            f"SELECT count(*) AS count FROM {table}"
        ).fetchone()["count"]
        for table in ("runtime_bundle", "runtime_bundle_component", "kernel_record")
    }


def _prospective_restart(store, suffix: str) -> tuple[Store, RuntimeBundle]:
    marker = RuntimeComponent.from_selected_bytes(
        role=RuntimeComponentRole.ADAPTER_SOURCE,
        logical_ref=f"python:test.schema-posture:{suffix}",
        canonicalization=Canonicalization.EXACT_BYTES,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=f"# schema-drift marker {suffix}\n".encode(),
    )
    bundle = RuntimeBundle.create((*store.runtime_bundle.components, marker))
    return Store(
        dsn=store.dsn,
        tenant_ref=store.tenant_ref,
        runtime_bundle=bundle,
        active_descriptor=store.active_descriptor,
    ), bundle


def _assert_startup_refuses_without_mutation(store, restarted, bundle) -> None:
    before_counts = _counts(store)
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
            (bundle.digest,),
        ).fetchone()["count"] == 0
    finally:
        restarted.close()


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


def test_schema_catalog_is_stable_across_independent_oid_allocations(fresh_env):
    store, _, _ = fresh_env
    first = store.conn.execute(
        "SELECT catalog_manifest, catalog_digest FROM runtime_schema_identity"
    ).fetchone()
    params = psycopg.conninfo.conninfo_to_dict(_admin_dsn())
    dbname = f"ofarm_schema_catalog_{uuid.uuid4().hex[:10]}"
    admin_params = dict(params)
    admin_params["dbname"] = "postgres"
    admin_dsn = psycopg.conninfo.make_conninfo(**admin_params)
    params["dbname"] = dbname
    second_dsn = psycopg.conninfo.make_conninfo(**params)

    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    second = None
    try:
        # Consume relation/type OIDs, then restore an empty public schema before
        # installation. Stable catalog bytes must not depend on those OIDs.
        with psycopg.connect(second_dsn, autocommit=True) as connection:
            connection.execute("CREATE TABLE public.oid_perturbation (id integer)")
            connection.execute("DROP TABLE public.oid_perturbation")
        second = Store(
            dsn=second_dsn,
            tenant_ref=store.tenant_ref,
            runtime_bundle=store.runtime_bundle,
            active_descriptor=store.active_descriptor,
        )
        second.migrate()
        observed = second.conn.execute(
            "SELECT catalog_manifest, catalog_digest FROM runtime_schema_identity"
        ).fetchone()
        assert canonical_json_bytes(observed["catalog_manifest"]) == \
            canonical_json_bytes(first["catalog_manifest"])
        assert observed["catalog_digest"] == first["catalog_digest"]
    finally:
        if second is not None:
            second.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))


def test_live_schema_drift_refuses_before_bundle_or_profile_mutation(fresh_env):
    store, _, _ = fresh_env
    restarted, replacement_bundle = _prospective_restart(store, "user-trigger")
    store.conn.execute(
        "DROP TRIGGER trg_kernel_record_append_only ON kernel_record"
    )
    _assert_startup_refuses_without_mutation(
        store, restarted, replacement_bundle)


def test_disabled_internal_foreign_key_trigger_refuses_before_mutation(fresh_env):
    store, _, _ = fresh_env
    trigger = store.conn.execute(
        """
        SELECT trigger_relation.relname AS relation_name,
               t.tgname AS trigger_name
          FROM pg_catalog.pg_trigger AS t
          JOIN pg_catalog.pg_constraint AS con ON con.oid = t.tgconstraint
          JOIN pg_catalog.pg_class AS constraint_relation
            ON constraint_relation.oid = con.conrelid
          JOIN pg_catalog.pg_class AS trigger_relation
            ON trigger_relation.oid = t.tgrelid
         WHERE t.tgisinternal
           AND con.contype = 'f'
           AND con.confrelid = 'runtime_bundle'::regclass
           AND constraint_relation.relname = 'kernel_record'
         ORDER BY trigger_relation.relname, t.tgname
         LIMIT 1
        """
    ).fetchone()
    assert trigger is not None
    restarted, replacement_bundle = _prospective_restart(store, "internal-fk")
    store.conn.execute(
        sql.SQL("ALTER TABLE {} DISABLE TRIGGER {}").format(
            sql.Identifier("public", trigger["relation_name"]),
            sql.Identifier(trigger["trigger_name"]),
        )
    )
    _assert_startup_refuses_without_mutation(
        store, restarted, replacement_bundle)


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
