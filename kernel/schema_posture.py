"""Startup-only verification of the operational PostgreSQL schema."""
from __future__ import annotations

from dataclasses import dataclass

from psycopg.types.json import Jsonb

from .runtime_bundle import (
    RuntimeBundleError,
    canonical_json_bytes,
    sha256_bytes,
)


SCHEMA_IDENTITY_KEY = "ofarm-kernel-schema"
SCHEMA_CATALOG_VERSION = "ofarm.postgresql-schema-catalog.local.v1"
_EXPECTED_POSTURE = {
    "current_schema": "public",
    "transaction_isolation": "read committed",
    "transaction_read_only": "off",
    "transaction_deferrable": "off",
    "timezone": "UTC",
    "search_path": "public, pg_catalog",
    "synchronous_commit": "on",
}


class SchemaPostureError(RuntimeError):
    """The database is not the schema and transaction posture selected at startup."""


@dataclass(frozen=True, slots=True)
class DatabaseObservation:
    """Process-local observation; none of these values enter RuntimeBundle identity."""

    schema_digest: str
    current_schema: str
    transaction_isolation: str
    transaction_read_only: str
    transaction_deferrable: str
    timezone: str
    search_path: str
    synchronous_commit: str

    def as_dict(self) -> dict[str, str]:
        return {
            "schemaDigest": self.schema_digest,
            "currentSchema": self.current_schema,
            "transactionIsolation": self.transaction_isolation,
            "transactionReadOnly": self.transaction_read_only,
            "transactionDeferrable": self.transaction_deferrable,
            "timezone": self.timezone,
            "searchPath": self.search_path,
            "synchronousCommit": self.synchronous_commit,
        }


def configure_session(conn) -> None:
    """Establish the deterministic session posture before the first transaction."""

    conn.execute(
        "SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL "
        "READ COMMITTED, READ WRITE, NOT DEFERRABLE"
    )
    conn.execute("SET TIME ZONE 'UTC'")
    conn.execute("SET search_path TO public, pg_catalog")
    conn.execute("SET synchronous_commit TO on")


def _catalog_rows(cur, query: str) -> list[dict]:
    cur.execute(query)
    return [dict(row) for row in cur.fetchall()]


def live_schema_catalog(cur) -> dict:
    """Describe the invariant-bearing public schema without host-local values."""

    return {
        "manifestVersion": SCHEMA_CATALOG_VERSION,
        "schemaName": "public",
        "relations": _catalog_rows(
            cur,
            """
            SELECT c.relname AS relation_name,
                   c.relkind AS relation_kind,
                   c.relpersistence AS persistence,
                   c.relrowsecurity AS row_security,
                   c.relforcerowsecurity AS force_row_security
              FROM pg_catalog.pg_class AS c
              JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
             ORDER BY c.relname
            """,
        ),
        "columns": _catalog_rows(
            cur,
            """
            SELECT c.relname AS relation_name,
                   a.attnum AS ordinal_position,
                   a.attname AS column_name,
                   pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                   cn.nspname AS collation_schema,
                   co.collname AS collation_name,
                   a.attnotnull AS not_null,
                   a.attidentity AS identity_kind,
                   a.attgenerated AS generated_kind,
                   pg_catalog.pg_get_expr(d.adbin, d.adrelid, false)
                     AS default_expression
              FROM pg_catalog.pg_attribute AS a
              JOIN pg_catalog.pg_class AS c ON c.oid = a.attrelid
              JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
              LEFT JOIN pg_catalog.pg_attrdef AS d
                     ON d.adrelid = a.attrelid AND d.adnum = a.attnum
              LEFT JOIN pg_catalog.pg_collation AS co ON co.oid = a.attcollation
              LEFT JOIN pg_catalog.pg_namespace AS cn ON cn.oid = co.collnamespace
             WHERE n.nspname = 'public'
               AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
               AND a.attnum > 0
               AND NOT a.attisdropped
             ORDER BY c.relname, a.attnum
            """,
        ),
        "sequences": _catalog_rows(
            cur,
            """
            SELECT c.relname AS sequence_name,
                   pg_catalog.format_type(s.seqtypid, NULL) AS data_type,
                   s.seqstart AS start_value,
                   s.seqincrement AS increment_by,
                   s.seqmin AS minimum_value,
                   s.seqmax AS maximum_value,
                   s.seqcache AS cache_size,
                   s.seqcycle AS cycles
              FROM pg_catalog.pg_sequence AS s
              JOIN pg_catalog.pg_class AS c ON c.oid = s.seqrelid
              JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
             ORDER BY c.relname
            """,
        ),
        "constraints": _catalog_rows(
            cur,
            """
            SELECT c.relname AS relation_name,
                   con.conname AS constraint_name,
                   con.contype AS constraint_type,
                   con.condeferrable AS deferrable,
                   con.condeferred AS initially_deferred,
                   con.convalidated AS validated,
                   pg_catalog.pg_get_constraintdef(con.oid, false) AS definition
              FROM pg_catalog.pg_constraint AS con
              JOIN pg_catalog.pg_class AS c ON c.oid = con.conrelid
              JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
             ORDER BY c.relname, con.conname
            """,
        ),
        "indexes": _catalog_rows(
            cur,
            """
            SELECT t.relname AS relation_name,
                   i.relname AS index_name,
                   x.indisunique AS is_unique,
                   x.indisprimary AS is_primary,
                   x.indisexclusion AS is_exclusion,
                   x.indisvalid AS is_valid,
                   pg_catalog.pg_get_indexdef(i.oid, 0, false) AS definition
              FROM pg_catalog.pg_index AS x
              JOIN pg_catalog.pg_class AS i ON i.oid = x.indexrelid
              JOIN pg_catalog.pg_class AS t ON t.oid = x.indrelid
              JOIN pg_catalog.pg_namespace AS n ON n.oid = t.relnamespace
             WHERE n.nspname = 'public'
             ORDER BY t.relname, i.relname
            """,
        ),
        "functions": _catalog_rows(
            cur,
            """
            SELECT p.proname AS function_name,
                   pg_catalog.pg_get_function_identity_arguments(p.oid)
                     AS identity_arguments,
                   pg_catalog.pg_get_functiondef(p.oid) AS definition
              FROM pg_catalog.pg_proc AS p
              JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
             WHERE n.nspname = 'public'
             ORDER BY p.proname,
                      pg_catalog.pg_get_function_identity_arguments(p.oid)
            """,
        ),
        "triggers": _catalog_rows(
            cur,
            """
            SELECT c.relname AS relation_name,
                   t.tgname AS trigger_name,
                   t.tgenabled AS enabled,
                   pg_catalog.pg_get_triggerdef(t.oid, false) AS definition
              FROM pg_catalog.pg_trigger AS t
              JOIN pg_catalog.pg_class AS c ON c.oid = t.tgrelid
              JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND NOT t.tgisinternal
             ORDER BY c.relname, t.tgname
            """,
        ),
    }


def _canonical_catalog_bytes(manifest: object) -> bytes:
    try:
        return canonical_json_bytes(manifest)
    except RuntimeBundleError as exc:
        raise SchemaPostureError(
            "runtime schema catalog manifest is not canonical JSON"
        ) from exc


def _read_schema_identity(cur) -> dict | None:
    cur.execute("SELECT to_regclass('public.runtime_schema_identity') AS relation")
    if cur.fetchone()["relation"] is None:
        return None
    cur.execute("SELECT to_jsonb(i) AS identity FROM runtime_schema_identity AS i")
    rows = cur.fetchall()
    if len(rows) != 1 or type(rows[0]["identity"]) is not dict:
        raise SchemaPostureError(
            "runtime_schema_identity must contain one exact schema identity"
        )
    identity = rows[0]["identity"]
    if set(identity) != {
        "identity_key", "schema_digest", "catalog_manifest", "catalog_digest"
    } or identity["identity_key"] != SCHEMA_IDENTITY_KEY:
        raise SchemaPostureError(
            "runtime_schema_identity must contain one exact schema identity"
        )
    return identity


def _require_empty_application_schema(cur) -> None:
    cur.execute(
        "SELECT ("
        "EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n "
        "ON n.oid = c.relnamespace WHERE n.nspname = 'public') OR "
        "EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n "
        "ON n.oid = p.pronamespace WHERE n.nspname = 'public')"
        ") AS occupied"
    )
    if cur.fetchone()["occupied"]:
        raise SchemaPostureError(
            "schema identity is absent but the public application schema is not empty"
        )


def install_or_verify_schema(cur, schema_bytes: bytes) -> str:
    """Install a fresh schema, or verify an existing exact-byte identity.

    The caller owns the transaction. A pre-ledger or differently addressed
    schema is refused rather than repaired or blessed.
    """

    schema_digest = sha256_bytes(schema_bytes)
    identity = _read_schema_identity(cur)
    if identity is None:
        _require_empty_application_schema(cur)
        try:
            schema_sql = schema_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise SchemaPostureError("schema.sql is not strict UTF-8") from exc
        cur.execute(schema_sql)
        catalog_manifest = live_schema_catalog(cur)
        catalog_digest = sha256_bytes(
            _canonical_catalog_bytes(catalog_manifest)
        )
        cur.execute(
            "INSERT INTO runtime_schema_identity "
            "(identity_key, schema_digest, catalog_manifest, catalog_digest) "
            "VALUES (%s, %s, %s, %s)",
            (
                SCHEMA_IDENTITY_KEY,
                schema_digest,
                Jsonb(catalog_manifest),
                catalog_digest,
            ),
        )
        identity = {
            "identity_key": SCHEMA_IDENTITY_KEY,
            "schema_digest": schema_digest,
            "catalog_manifest": catalog_manifest,
            "catalog_digest": catalog_digest,
        }
    if identity["schema_digest"] != schema_digest:
        raise SchemaPostureError(
            "installed schema digest does not match the selected schema.sql bytes"
        )
    expected_catalog_bytes = _canonical_catalog_bytes(
        identity["catalog_manifest"]
    )
    if sha256_bytes(expected_catalog_bytes) != identity["catalog_digest"]:
        raise SchemaPostureError(
            "installed schema catalog digest does not match its canonical manifest"
        )
    live_catalog_bytes = _canonical_catalog_bytes(live_schema_catalog(cur))
    if live_catalog_bytes != expected_catalog_bytes:
        raise SchemaPostureError(
            "live database schema catalog does not match the installed manifest"
        )
    return schema_digest


def verify_transaction_posture(cur) -> dict[str, str]:
    """Verify the configured transaction posture once during startup."""

    cur.execute(
        "SELECT current_schema() AS current_schema, "
        "current_setting('transaction_isolation') AS transaction_isolation, "
        "current_setting('transaction_read_only') AS transaction_read_only, "
        "current_setting('transaction_deferrable') AS transaction_deferrable, "
        "current_setting('TimeZone') AS timezone, "
        "current_setting('search_path') AS search_path, "
        "current_setting('synchronous_commit') AS synchronous_commit"
    )
    observed = dict(cur.fetchone())
    if observed != _EXPECTED_POSTURE:
        raise SchemaPostureError(
            f"database startup posture mismatch: expected {_EXPECTED_POSTURE!r}, "
            f"observed {observed!r}"
        )
    return observed
