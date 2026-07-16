"""Exact schema identity and startup-only database posture tests."""
from __future__ import annotations

import psycopg
import pytest

from kernel import config
from kernel.runtime_bundle import sha256_bytes
from kernel.schema_posture import SchemaPostureError, install_or_verify_schema


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
        "SELECT identity_key, schema_digest FROM runtime_schema_identity"
    ).fetchone()

    assert identity == {
        "identity_key": "ofarm-kernel-schema",
        "schema_digest": expected,
    }
    assert observation.schema_digest == expected
    assert observation.current_schema == "public"
    assert observation.transaction_isolation == "read committed"
    assert observation.transaction_read_only == "off"
    assert observation.transaction_deferrable == "off"


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
