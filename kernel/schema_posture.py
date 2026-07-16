"""Startup-only verification of the operational PostgreSQL schema."""
from __future__ import annotations

from dataclasses import dataclass

from .runtime_bundle import sha256_bytes


SCHEMA_IDENTITY_KEY = "ofarm-kernel-schema"
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


def _read_schema_identity(cur) -> str | None:
    cur.execute("SELECT to_regclass('public.runtime_schema_identity') AS relation")
    if cur.fetchone()["relation"] is None:
        return None
    cur.execute(
        "SELECT identity_key, schema_digest FROM runtime_schema_identity"
    )
    rows = cur.fetchall()
    if (
        len(rows) != 1
        or rows[0]["identity_key"] != SCHEMA_IDENTITY_KEY
    ):
        raise SchemaPostureError(
            "runtime_schema_identity must contain one exact schema identity"
        )
    return rows[0]["schema_digest"]


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
    observed = _read_schema_identity(cur)
    if observed is None:
        _require_empty_application_schema(cur)
        try:
            schema_sql = schema_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise SchemaPostureError("schema.sql is not strict UTF-8") from exc
        cur.execute(schema_sql)
        cur.execute(
            "INSERT INTO runtime_schema_identity (identity_key, schema_digest) "
            "VALUES (%s, %s)",
            (SCHEMA_IDENTITY_KEY, schema_digest),
        )
        observed = schema_digest
    if observed != schema_digest:
        raise SchemaPostureError(
            "installed schema digest does not match the selected schema.sql bytes"
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
