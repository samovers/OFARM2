"""The append-only truth store (M1 brief task 2).

One uniform record table for governed contract records, an explicit edge
table, a gate log, idempotency bookkeeping, and derived (recomputable)
materialization tables. Semantic law lives in the gate pipeline; this module
enforces the storage posture:

  * contract validation on every write (KERNEL.md conformance condition 1)
  * append-only at the database level (Kernel rule 1 — triggers in schema.sql)
  * payload sha256 + schema version + schema hash per record
  * references as durable edges, not JSON-path conventions
  * reachability link written in the same transaction as the commit (D3) —
    the deferred constraint trigger makes a commit without it impossible
  * draft-lane shapes (D16) land in runtime_trace, never in kernel_record
"""
from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from . import config
from .contracts import ContractRegistry, ContractViolation, sha256_of

# Single-writer advisory-lock key (M2 G2): a stable signed-64-bit derived from
# the tenant ref. Every governed WRITE entry point (user commit + scheduled
# import) acquires this transaction-scoped lock, so a scheduled import can never
# interleave with a user commit, and concurrent structure-identity commits
# serialize (closing the D18 read-before-write race — PR #9 H1). The lock stays
# on until the freshness-vector snapshot-isolation/watermark fix (M5/L2).
_SINGLE_WRITER_LOCK_KEY = int.from_bytes(
    hashlib.sha256(config.TENANT_REF.encode()).digest()[:8], "big", signed=True)

AUTHORITATIVE_KINDS = (
    "ofarm.assertionrecord.v0.1",
    "ofarm.semanticeventenvelope.v0.1",
    "ofarm.reviewdecision.v0.1",
    "ofarm.acceptedeventconsequence.v0.1",
)

_SCHEMA_PATH = config.PACKAGE_ROOT / "kernel" / "schema.sql"
_SCHEMA_BYTES = _SCHEMA_PATH.read_bytes()
_SCHEMA_SQL = _SCHEMA_BYTES.decode("utf-8")


class Store:
    _SEALED_REGISTRY_FIELDS = {
        "_registry", "_registry_decision_identity", "_registry_sealed",
    }

    def __setattr__(self, name, value):
        if (getattr(self, "_registry_sealed", False)
                and name in self._SEALED_REGISTRY_FIELDS):
            raise AttributeError(
                "Store ContractRegistry binding is immutable after construction")
        object.__setattr__(self, name, value)

    def __init__(self, dsn: str | None = None, registry: ContractRegistry | None = None):
        self._registry_sealed = False
        self.dsn = dsn or config.database_dsn()
        self._registry = registry or ContractRegistry()
        self._registry_decision_identity = self._registry.decision_identity()
        self._conn: psycopg.Connection | None = None
        self._runtime_bundle = None
        self._bootstrap_bundle = None
        self._pending_runtime_bundle_activation = None
        self._registry_sealed = True

    @property
    def registry(self) -> ContractRegistry:
        registry = self._registry
        if (type(registry) is not ContractRegistry
                or registry.decision_identity() != self._registry_decision_identity):
            raise RuntimeError(
                "Store ContractRegistry decision semantics changed after construction")
        return registry

    # -- connection / lifecycle ------------------------------------------------

    @property
    def conn(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self.dsn, row_factory=dict_row, autocommit=True)
            self._conn.execute("SET TIME ZONE 'UTC'")
        return self._conn

    def migrate(self) -> None:
        if _SCHEMA_PATH.read_bytes() != _SCHEMA_BYTES:
            raise RuntimeError(
                "kernel schema bytes changed after process startup; refusing to "
                "migrate under an unreceipted schema")
        with self.conn.cursor() as cur:
            cur.execute(_SCHEMA_SQL)

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()

    @property
    def runtime_bundle(self):
        if self._runtime_bundle is None:
            raise RuntimeError("Store has no verified RuntimeBundle; bootstrap first")
        return self._runtime_bundle

    @property
    def runtime_bundle_digest(self) -> str:
        return self.runtime_bundle.digest

    def bind_runtime_bundle(self, bundle) -> None:
        """Reject direct binding; live activation belongs to atomic bootstrap."""
        if bundle.construction_mode != "LIVE_CURRENT":
            raise RuntimeError(
                "persisted-audit RuntimeBundles cannot be bound for live decisions")
        raise RuntimeError(
            "direct RuntimeBundle binding is forbidden; use atomic context bootstrap")

    @staticmethod
    def _observe_database_environment(cur) -> dict:
        """Capture decision-bearing PostgreSQL state in the bootstrap transaction."""
        cur.execute(
            "SELECT current_setting('server_version') AS version, "
            "current_setting('server_version_num') AS version_number, "
            "current_setting('server_encoding') AS encoding, "
            "current_setting('TimeZone') AS timezone, "
            "current_setting('DateStyle') AS date_style, "
            "current_setting('IntervalStyle') AS interval_style, "
            "current_setting('search_path') AS search_path, "
            "current_setting('standard_conforming_strings') AS standard_strings, "
            "current_setting('extra_float_digits') AS extra_float_digits, "
            "current_setting('bytea_output') AS bytea_output, "
            "current_user AS current_user_name, session_user AS session_user_name"
        )
        settings = cur.fetchone()
        normalized = re.match(r"^(\d+\.\d+)", settings["version"])
        if normalized is None:
            raise RuntimeError("observed PostgreSQL version is not parseable")
        cur.execute(
            "SELECT datlocprovider::text AS locale_provider, "
            "datcollate AS collation, datctype AS ctype, "
            "datlocale AS locale, daticurules AS icu_rules, "
            "datcollversion AS collation_version "
            "FROM pg_database WHERE datname = current_database()"
        )
        database = cur.fetchone()
        if database is None:
            raise RuntimeError("current PostgreSQL database identity is unavailable")
        cur.execute(
            "SELECT extname AS name, extversion AS version "
            "FROM pg_extension ORDER BY extname"
        )
        extensions = [dict(row) for row in cur.fetchall()]
        return {
            "schemaVersion": "ofarm.runtime-database-observation.local.v1",
            "server": {
                "version": settings["version"],
                "versionNumber": settings["version_number"],
                "normalizedVersion": normalized.group(1),
            },
            "database": {
                "encoding": settings["encoding"],
                "localeProvider": database["locale_provider"],
                "collation": database["collation"],
                "ctype": database["ctype"],
                "locale": database["locale"],
                "icuRules": database["icu_rules"],
                "collationVersion": database["collation_version"],
            },
            "session": {
                "currentUser": settings["current_user_name"],
                "sessionUser": settings["session_user_name"],
                "timezone": settings["timezone"],
                "dateStyle": settings["date_style"],
                "intervalStyle": settings["interval_style"],
                "searchPath": settings["search_path"],
                "standardConformingStrings": settings["standard_strings"],
                "extraFloatDigits": settings["extra_float_digits"],
                "byteaOutput": settings["bytea_output"],
            },
            "extensions": extensions,
        }

    def _prepare_runtime_bundle_binding(self, bundle):
        """Run every fallible live-binding check inside the bootstrap transaction."""
        if self._bootstrap_bundle is not bundle:
            raise RuntimeError(
                "RuntimeBundle binding preparation requires its verified bootstrap scope")
        from .runtime_bundle import (
            assert_runtime_environment_compatible,
            database_runtime_environment_component,
            require_current_runtime_catalog,
        )
        if bundle.tenant_ref != config.TENANT_REF:
            raise RuntimeError(
                "RuntimeBundle tenant does not match this Store runtime tenant")
        require_current_runtime_catalog(bundle, config.PACKAGE_ROOT)
        required_environment = assert_runtime_environment_compatible(bundle)
        with self.conn.cursor() as cur:
            database_environment = self._observe_database_environment(cur)
        selected_database = bundle.component(
            "RUNTIME_DATABASE_OBSERVED", "environment:observed-postgresql.v1")
        if selected_database != database_runtime_environment_component(
                database_environment):
            raise RuntimeError(
                "observed PostgreSQL environment changed after RuntimeBundle selection")
        if (database_environment["server"]["normalizedVersion"] !=
                required_environment.get("postgresqlVersion")
                or database_environment["session"]["timezone"] !=
                required_environment.get("timezone")
                or database_environment["database"]["encoding"] != "UTF8"
                or database_environment["database"]["localeProvider"] != "c"):
            raise RuntimeError(
                "observed PostgreSQL version, timezone, encoding, or deterministic "
                "locale provider differs from the retained runtime requirement")
        required_settings = {
            "dateStyle": "ISO, MDY",
            "intervalStyle": "postgres",
            "standardConformingStrings": "on",
            "byteaOutput": "hex",
        }
        if any(database_environment["session"].get(name) != value
               for name, value in required_settings.items()):
            raise RuntimeError(
                "observed PostgreSQL semantic settings are unsupported")
        if self._runtime_bundle is not None and self._runtime_bundle.digest != bundle.digest:
            raise RuntimeError(
                "RuntimeBundle hot switching is forbidden; create a new runtime instance")
        self.assert_runtime_bundle_compatible(bundle)
        cold = self.cold_load_runtime_bundle(bundle.descriptor, bundle.digest)
        if (cold.canonical_document_bytes != bundle.canonical_document_bytes
                or cold.components != bundle.components
                or cold.selected_references != bundle.selected_references):
            raise RuntimeError(
                "cannot bind an incomplete or byte-mismatched persisted RuntimeBundle")
        if self._pending_runtime_bundle_activation is not None:
            raise RuntimeError("a RuntimeBundle activation is already pending")
        token = object()
        self._pending_runtime_bundle_activation = (token, bundle)
        return token

    def _activate_prepared_runtime_bundle(self, activation_token) -> None:
        """Consume the exact one-use activation prepared by atomic bootstrap."""
        pending = self._pending_runtime_bundle_activation
        if pending is None or activation_token is not pending[0]:
            raise RuntimeError(
                "RuntimeBundle activation was not successfully prepared by this Store")
        if self.conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
            raise RuntimeError(
                "RuntimeBundle activation is allowed only after bootstrap commits")
        self._pending_runtime_bundle_activation = None
        self._runtime_bundle = pending[1]

    def _discard_prepared_runtime_bundle_binding(self) -> None:
        """Invalidate any one-use activation when bootstrap does not commit."""
        self._pending_runtime_bundle_activation = None

    def assert_runtime_bundle_compatible(self, bundle) -> None:
        """Check process-local registry/runtime compatibility before commit."""
        canonical_registry = ContractRegistry()
        if (type(self.registry) is not ContractRegistry
                or self.registry.decision_identity() !=
                canonical_registry.decision_identity()):
            raise RuntimeError(
                "Store ContractRegistry decision semantics differ from code-owned runtime")
        schema_component = bundle.component(
            "RUNTIME_SCHEMA", "sql:kernel/schema.sql")
        if schema_component.canonical_bytes != _SCHEMA_BYTES:
            raise RuntimeError(
                "RuntimeBundle schema bytes differ from the schema executed by Store")
        contract_components = {
            component.logical_ref: component for component in bundle.components
            if component.role == "CONTRACT_SCHEMA"
        }
        expected_contract_refs = {
            f"contract:{kind}" for kind in self.registry.kinds()
        }
        if set(contract_components) != expected_contract_refs:
            raise RuntimeError(
                "RuntimeBundle contract inventory does not equal ContractRegistry")
        for kind in self.registry.kinds():
            contract = self.registry.get(kind)
            component = contract_components[f"contract:{kind}"]
            if (component.canonicalization != "EXACT_BYTES_V1"
                    or component.content_digest != contract.schema_hash
                    or component.canonical_bytes != contract.schema_bytes):
                raise RuntimeError(
                    f"RuntimeBundle contract bytes do not match registry for {kind!r}")

    def _bundle_digest(self, explicit: str | None = None) -> str:
        if explicit is not None:
            if self._runtime_bundle is not None and explicit != self._runtime_bundle.digest:
                raise RuntimeError(
                    "a bound Store cannot write under a different RuntimeBundle")
            if (self._runtime_bundle is None
                    and (self._bootstrap_bundle is None
                         or explicit != self._bootstrap_bundle.digest)):
                raise RuntimeError(
                    "an unbound Store cannot attribute writes to a RuntimeBundle "
                    "outside verified atomic bootstrap")
            return explicit
        return self.runtime_bundle_digest

    def _bundle_tenant_ref(self) -> str:
        if self._runtime_bundle is not None:
            return self._runtime_bundle.tenant_ref
        if self._bootstrap_bundle is not None:
            return self._bootstrap_bundle.tenant_ref
        raise RuntimeError(
            "Store has no verified RuntimeBundle tenant; bootstrap first")

    @contextmanager
    def _bootstrap_bundle_writes(self, bundle):
        """Narrow pre-bind write authority to one verified bootstrap bundle."""
        if self._runtime_bundle is not None:
            raise RuntimeError("bootstrap bundle writes require an unbound Store")
        if self._bootstrap_bundle is not None:
            raise RuntimeError("nested RuntimeBundle bootstrap write scopes are forbidden")
        if bundle.construction_mode != "LIVE_CURRENT":
            raise RuntimeError(
                "bootstrap write authority requires a live-selected RuntimeBundle")
        if bundle.tenant_ref != config.TENANT_REF:
            raise RuntimeError(
                "bootstrap write authority tenant differs from this runtime tenant")
        if self.conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE:
            raise RuntimeError(
                "bootstrap write authority requires an active database transaction")
        self.assert_runtime_bundle_compatible(bundle)
        self._bootstrap_bundle = bundle
        try:
            yield
        finally:
            self._bootstrap_bundle = None

    def install_runtime_bundle(self, cur, bundle) -> None:
        """Persist exact bundle/component bytes, verifying every identity reuse."""
        from .runtime_bundle import (
            GLOBAL_CONTENT_PLACEMENT,
            TENANT_CONTENT_PLACEMENT,
        )
        if bundle.tenant_ref != config.TENANT_REF:
            raise RuntimeError(
                "cannot install a RuntimeBundle for a different runtime tenant")
        if bundle.construction_mode != "LIVE_CURRENT":
            raise RuntimeError(
                "only a live-selected RuntimeBundle may be installed")
        if cur.connection.info.transaction_status != psycopg.pq.TransactionStatus.INTRANS:
            raise RuntimeError(
                "RuntimeBundle installation requires one active database transaction")
        cur.execute(
            "SELECT tenant_ref, bundle_ref, canonical_document, canonical_bytes, "
            "byte_length FROM runtime_bundle "
            "WHERE tenant_ref = %s AND bundle_digest = %s",
            (bundle.tenant_ref, bundle.digest),
        )
        prior_bundle = cur.fetchone()
        document = json.loads(bundle.canonical_document_bytes)
        if prior_bundle is not None:
            if (prior_bundle["tenant_ref"] != bundle.tenant_ref
                    or prior_bundle["bundle_ref"] != bundle.bundle_ref
                    or prior_bundle["canonical_document"] != document
                    or bytes(prior_bundle["canonical_bytes"]) !=
                    bundle.canonical_document_bytes
                    or prior_bundle["byte_length"] !=
                    len(bundle.canonical_document_bytes)):
                raise RuntimeError(
                    f"RuntimeBundle digest {bundle.digest} was reused for unequal bytes")
            cur.execute(
                "SELECT component_role, logical_ref FROM runtime_bundle_component "
                "WHERE tenant_ref = %s AND bundle_digest = %s",
                (bundle.tenant_ref, bundle.digest),
            )
            persisted_identities = {
                (row["component_role"], row["logical_ref"])
                for row in cur.fetchall()
            }
            expected_identities = {
                (component.role, component.logical_ref)
                for component in bundle.components
            }
            if persisted_identities != expected_identities:
                raise RuntimeError(
                    f"existing RuntimeBundle {bundle.digest} component set is not exact; "
                    f"missing={sorted(expected_identities - persisted_identities)}, "
                    f"extra={sorted(persisted_identities - expected_identities)}")
        for component in bundle.components:
            if component.placement == GLOBAL_CONTENT_PLACEMENT:
                table = "runtime_content_blob"
                where = "content_digest = %s"
                params = (component.content_digest,)
                columns = (
                    "content_digest, content_class, canonicalization, "
                    "canonical_bytes, byte_length")
                values = (component.content_digest, component.role,
                          component.canonicalization, component.canonical_bytes,
                          len(component.canonical_bytes))
            elif component.placement == TENANT_CONTENT_PLACEMENT:
                table = "runtime_tenant_content_blob"
                where = "tenant_ref = %s AND content_digest = %s"
                params = (bundle.tenant_ref, component.content_digest)
                columns = (
                    "tenant_ref, content_digest, content_class, canonicalization, "
                    "canonical_bytes, byte_length")
                values = (bundle.tenant_ref, component.content_digest,
                          component.role, component.canonicalization,
                          component.canonical_bytes, len(component.canonical_bytes))
            else:
                raise RuntimeError(
                    f"unknown RuntimeBundle component placement {component.placement!r}")
            cur.execute(
                f"SELECT content_class, canonicalization, canonical_bytes, byte_length "
                f"FROM {table} WHERE {where}",
                params,
            )
            prior = cur.fetchone()
            if prior is None:
                if prior_bundle is not None:
                    raise RuntimeError(
                        f"existing RuntimeBundle {bundle.digest} is missing retained "
                        f"content for {component.role}/{component.logical_ref}")
                cur.execute(
                    f"INSERT INTO {table} ({columns}) VALUES (" +
                    ", ".join(["%s"] * len(values)) + ")",
                    values,
                )
            elif (prior["content_class"] != component.role
                  or prior["canonicalization"] != component.canonicalization
                  or bytes(prior["canonical_bytes"]) != component.canonical_bytes
                  or prior["byte_length"] != len(component.canonical_bytes)):
                raise RuntimeError(
                    f"content digest {component.content_digest} was reused for unequal bytes")

        if prior_bundle is None:
            cur.execute(
                "INSERT INTO runtime_bundle "
                "(tenant_ref, bundle_digest, bundle_ref, canonical_document, "
                "canonical_bytes, byte_length) VALUES (%s, %s, %s, %s, %s, %s)",
                (bundle.tenant_ref, bundle.digest, bundle.bundle_ref, Jsonb(document),
                 bundle.canonical_document_bytes, len(bundle.canonical_document_bytes)),
            )

        for component in bundle.components:
            cur.execute(
                "SELECT repository_path, canonicalization, content_placement, "
                "global_content_digest, tenant_content_digest, byte_length "
                "FROM runtime_bundle_component WHERE tenant_ref = %s "
                "AND bundle_digest = %s "
                "AND component_role = %s AND logical_ref = %s",
                (bundle.tenant_ref, bundle.digest,
                 component.role, component.logical_ref),
            )
            prior = cur.fetchone()
            global_digest = (
                component.content_digest
                if component.placement == GLOBAL_CONTENT_PLACEMENT else None)
            tenant_digest = (
                component.content_digest
                if component.placement == TENANT_CONTENT_PLACEMENT else None)
            expected = (
                component.repository_path, component.canonicalization,
                component.placement, global_digest, tenant_digest,
                len(component.canonical_bytes),
            )
            if prior is None:
                if prior_bundle is not None:
                    raise RuntimeError(
                        f"existing RuntimeBundle {bundle.digest} is missing component "
                        f"{component.role}/{component.logical_ref}")
                cur.execute(
                    "INSERT INTO runtime_bundle_component "
                    "(tenant_ref, bundle_digest, component_role, logical_ref, "
                    "repository_path, canonicalization, content_placement, "
                    "global_content_digest, tenant_content_digest, byte_length) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (bundle.tenant_ref, bundle.digest, component.role,
                     component.logical_ref, *expected),
                )
            elif (
                prior["repository_path"], prior["canonicalization"],
                prior["content_placement"], prior["global_content_digest"],
                prior["tenant_content_digest"], prior["byte_length"],
            ) != expected:
                raise RuntimeError(
                    f"RuntimeBundle component identity was reused with drift: "
                    f"{component.role}/{component.logical_ref}")

        cur.execute(
            "SELECT component_role, logical_ref FROM runtime_bundle_component "
            "WHERE tenant_ref = %s AND bundle_digest = %s",
            (bundle.tenant_ref, bundle.digest),
        )
        persisted_identities = {
            (row["component_role"], row["logical_ref"]) for row in cur.fetchall()
        }
        expected_identities = {
            (component.role, component.logical_ref) for component in bundle.components
        }
        if persisted_identities != expected_identities:
            raise RuntimeError(
                f"RuntimeBundle {bundle.digest} persisted component set is not exact; "
                f"missing={sorted(expected_identities - persisted_identities)}, "
                f"extra={sorted(persisted_identities - expected_identities)}")

    def persisted_runtime_bundle(self, digest: str) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT tenant_ref, bundle_digest, bundle_ref, canonical_document, "
                "canonical_bytes, byte_length FROM runtime_bundle "
                "WHERE tenant_ref = %s AND bundle_digest = %s",
                (config.TENANT_REF, digest),
            )
            bundle = cur.fetchone()
            if bundle is None:
                return None
            cur.execute(
                "SELECT c.component_role, c.logical_ref, c.repository_path, "
                "c.canonicalization, c.content_placement, "
                "CASE WHEN c.content_placement = 'GLOBAL_IMMUTABLE_CONTENT' "
                "THEN c.global_content_digest ELSE c.tenant_content_digest END "
                "AS content_digest, c.byte_length, "
                "CASE WHEN c.content_placement = 'GLOBAL_IMMUTABLE_CONTENT' "
                "THEN g.content_class ELSE t.content_class END AS blob_content_class, "
                "CASE WHEN c.content_placement = 'GLOBAL_IMMUTABLE_CONTENT' "
                "THEN g.canonicalization ELSE t.canonicalization END "
                "AS blob_canonicalization, "
                "CASE WHEN c.content_placement = 'GLOBAL_IMMUTABLE_CONTENT' "
                "THEN g.byte_length ELSE t.byte_length END AS blob_byte_length, "
                "CASE WHEN c.content_placement = 'GLOBAL_IMMUTABLE_CONTENT' "
                "THEN g.canonical_bytes ELSE t.canonical_bytes END AS canonical_bytes "
                "FROM runtime_bundle_component c "
                "LEFT JOIN runtime_content_blob g "
                "ON g.content_digest = c.global_content_digest "
                "LEFT JOIN runtime_tenant_content_blob t "
                "ON t.tenant_ref = c.tenant_ref "
                "AND t.content_digest = c.tenant_content_digest "
                "WHERE c.tenant_ref = %s AND c.bundle_digest = %s "
                "ORDER BY c.component_role, c.logical_ref",
                (config.TENANT_REF, digest),
            )
            components = cur.fetchall()
        return {
            "tenant_ref": bundle["tenant_ref"],
            "bundle_digest": bundle["bundle_digest"],
            "bundle_ref": bundle["bundle_ref"],
            "canonical_document": bundle["canonical_document"],
            "canonical_document_bytes": bytes(bundle["canonical_bytes"]),
            "byte_length": bundle["byte_length"],
            "components": components,
        }

    def cold_load_runtime_bundle(self, descriptor, digest: str):
        """Reconstruct and verify a bundle using only immutable persisted bytes."""
        from .runtime_bundle import RuntimeComponent, runtime_bundle_from_persisted
        persisted = self.persisted_runtime_bundle(digest)
        if persisted is None:
            raise RuntimeError(f"no persisted RuntimeBundle {digest}")
        canonical_document_bytes = persisted["canonical_document_bytes"]
        if persisted["bundle_digest"] != digest:
            raise RuntimeError("persisted RuntimeBundle key does not match requested digest")
        if persisted["tenant_ref"] != config.TENANT_REF:
            raise RuntimeError("persisted RuntimeBundle tenant does not match this Store")
        if persisted["bundle_ref"] != f"runtimebundle:{digest}":
            raise RuntimeError("persisted RuntimeBundle ref does not match requested digest")
        if persisted["byte_length"] != len(canonical_document_bytes):
            raise RuntimeError("persisted RuntimeBundle document length mismatch")
        try:
            canonical_document = json.loads(canonical_document_bytes)
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError("persisted RuntimeBundle document bytes are malformed") from exc
        if canonical_document != persisted["canonical_document"]:
            raise RuntimeError(
                "persisted RuntimeBundle canonical JSON and exact bytes disagree")
        if canonical_document.get("tenantRef") != persisted["tenant_ref"]:
            raise RuntimeError(
                "persisted RuntimeBundle document and relational tenant disagree")
        components = []
        for row in persisted["components"]:
            if row["canonical_bytes"] is None:
                raise RuntimeError(
                    "persisted RuntimeBundle component points to the wrong or "
                    "missing content carrier")
            canonical = bytes(row["canonical_bytes"])
            if (row["byte_length"] != len(canonical)
                    or row["blob_byte_length"] != len(canonical)
                    or row["blob_content_class"] != row["component_role"]
                    or row["blob_canonicalization"] != row["canonicalization"]):
                raise RuntimeError(
                    "persisted RuntimeBundle component/blob metadata mismatch")
            components.append(RuntimeComponent(
                role=row["component_role"],
                logical_ref=row["logical_ref"],
                repository_path=row["repository_path"],
                canonicalization=row["canonicalization"],
                content_digest=row["content_digest"],
                canonical_bytes=canonical,
                placement=row["content_placement"],
            ))
        return runtime_bundle_from_persisted(
            descriptor,
            expected_digest=digest,
            canonical_document_bytes=canonical_document_bytes,
            components=components,
            package_root=config.PACKAGE_ROOT,
        )

    @contextmanager
    def tx(self):
        """One transaction. The reachability constraint trigger fires at COMMIT
        of this block (D3).

        CONVENTION (M2 G2, PR #10 review H1): plain ``tx()`` does NOT hold the
        single-writer lock. During G2's single-writer phase (until M5/L2 lifts
        the lock), any governed write that can affect truth, context,
        materialization, imports, or outputs MUST use ``serialized_tx()``
        instead. ``tx()`` is for bootstrap/test setup and explicitly safe
        audit/read-decision traces only (e.g. recording a read-authorization
        decision). New write-capable paths default to ``serialized_tx()``."""
        with self.conn.transaction():
            with self.conn.cursor() as cur:
                yield cur

    @contextmanager
    def serialized_tx(self):
        """A governed WRITE transaction holding the single-writer advisory lock
        (M2 G2). User commits and scheduled imports share this lock, so they can
        never interleave (single-writer invariant by construction) and concurrent
        structure-identity commits serialize (D18 race, PR #9 H1). The lock is
        transaction-scoped — Postgres releases it at COMMIT/ROLLBACK — so it is
        held for exactly the life of the write and never leaks. Within a single
        connection it is granted immediately (no self-contention); it only blocks
        a *different* connection's write, which is the cross-writer race we mean
        to serialize."""
        with self.conn.transaction():
            with self.conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (_SINGLE_WRITER_LOCK_KEY,))
                yield cur

    # -- canonical record writes ----------------------------------------------

    def insert_record(self, cur, payload: dict, *, tenant_ref: str | None = None,
                      runtime_bundle_digest: str | None = None) -> str:
        """Validate against the package contract and append. Returns record id."""
        bundle_tenant_ref = self._bundle_tenant_ref()
        if tenant_ref is None:
            tenant_ref = bundle_tenant_ref
        elif tenant_ref != bundle_tenant_ref:
            raise RuntimeError(
                "kernel_record tenant must exactly match the verified RuntimeBundle tenant")
        contract = self.registry.validate(payload)
        if contract.lane != "canonical":
            raise ContractViolation(
                f"{contract.kind} is a draft-lane shape; draft records belong in "
                "runtime_trace (D16: implement, never promote)"
            )
        if contract.id_field is None:
            raise ContractViolation(
                f"{contract.kind} is an authored-artifact contract, not a store record"
            )
        record_id = payload[contract.id_field]
        cur.execute(
            """
            INSERT INTO kernel_record
              (record_id, record_kind, lane, schema_hash, payload, payload_sha256,
               tenant_ref, runtime_bundle_digest)
            VALUES (%s, %s, 'canonical', %s, %s, %s, %s, %s)
            """,
            (record_id, contract.kind, contract.schema_hash, Jsonb(payload),
             sha256_of(payload), tenant_ref, self._bundle_digest(runtime_bundle_digest)),
        )
        return record_id

    def runtime_trace_exists(self, trace_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM runtime_trace WHERE trace_id = %s", (trace_id,))
            return cur.fetchone() is not None

    def insert_runtime_trace(self, cur, payload: dict, *,
                             runtime_bundle_digest: str | None = None) -> str:
        """Append a draft-lane runtime evidence record (D16)."""
        contract = self.registry.validate(payload)
        if contract.lane != "draft":
            raise ContractViolation(
                f"{contract.kind} is canonical-lane; use insert_record"
            )
        trace_id = payload[contract.id_field]
        cur.execute(
            """
            INSERT INTO runtime_trace
              (trace_id, trace_kind, schema_hash, payload, payload_sha256,
               runtime_bundle_digest)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (trace_id, contract.kind, contract.schema_hash, Jsonb(payload), sha256_of(payload),
             self._bundle_digest(runtime_bundle_digest)),
        )
        return trace_id

    def insert_reference_data(self, cur, snapshot_ref: str, data_family: str,
                              payload: dict, *, artifact_ref: str | None = None,
                              source_digest: str | None = None,
                              parser_label: str | None = None,
                              record_count: int | None = None,
                              runtime_bundle_digest: str | None = None) -> None:
        """Persist store-backed external reference-data for a snapshot (M2 P1) —
        an index cache (NOT OFARM truth) so a scheme reader can resolve an
        imported snapshot's content from the store. The payload is opaque here;
        one row per (snapshot_ref, data_family)."""
        cur.execute(
            """
            INSERT INTO reference_snapshot_data
              (snapshot_ref, data_family, artifact_ref, source_digest,
               parser_label, record_count, payload, payload_sha256,
               runtime_bundle_digest)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (snapshot_ref, data_family, artifact_ref, source_digest, parser_label,
             record_count, Jsonb(payload), sha256_of(payload),
             self._bundle_digest(runtime_bundle_digest)),
        )

    def reference_data(self, data_family: str) -> list[dict]:
        """Store-backed reference-data rows of a family (snapshot_ref + payload),
        for a scheme reader to load into its lookup index."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT d.snapshot_ref, d.data_family, d.artifact_ref, "
                "d.source_digest, d.parser_label, d.record_count, d.payload, "
                "d.payload_sha256, d.runtime_bundle_digest "
                "FROM reference_snapshot_data d JOIN runtime_bundle b "
                "ON b.bundle_digest = d.runtime_bundle_digest "
                "WHERE d.data_family = %s AND b.tenant_ref = %s "
                "ORDER BY d.snapshot_ref",
                (data_family, self._bundle_tenant_ref()),
            )
            return cur.fetchall()

    def add_edge(self, cur, edge_type: str, src_record_id: str, dst_record_id: str,
                 *, runtime_bundle_digest: str | None = None) -> None:
        cur.execute(
            "INSERT INTO kernel_edge (edge_type, src_record_id, dst_record_id, "
            "runtime_bundle_digest) VALUES (%s, %s, %s, %s)",
            (edge_type, src_record_id, dst_record_id,
             self._bundle_digest(runtime_bundle_digest)),
        )

    def log_gate(
        self, cur, request_id: str, gate: str, outcome: str,
        *, reason_code: str | None = None, rationale: str | None = None,
        related_refs: list[str] | None = None,
        runtime_bundle_digest: str | None = None,
    ) -> None:
        cur.execute(
            """
            INSERT INTO kernel_gate_log
              (request_id, gate, outcome, reason_code, rationale, related_refs,
               runtime_bundle_digest)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (request_id, gate, outcome, reason_code, rationale,
             Jsonb(related_refs) if related_refs is not None else None,
             self._bundle_digest(runtime_bundle_digest)),
        )

    # -- idempotency (ingress boundary RFC §2.4) -------------------------------

    def idempotency_lookup(self, cur, key: str) -> dict | None:
        cur.execute("SELECT * FROM kernel_idempotency WHERE idempotency_key = %s", (key,))
        return cur.fetchone()

    def idempotency_claim(
        self, cur, key: str, request_id: str, source_payload_digest: str | None,
        result_record_id: str, *, runtime_bundle_digest: str | None = None,
    ) -> None:
        cur.execute(
            """
            INSERT INTO kernel_idempotency
              (idempotency_key, request_id, source_payload_digest, result_record_id,
               runtime_bundle_digest)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (key, request_id, source_payload_digest, result_record_id,
             self._bundle_digest(runtime_bundle_digest)),
        )

    # -- reads -----------------------------------------------------------------

    def get_record(self, record_id: str) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM kernel_record WHERE record_id = %s", (record_id,))
            return cur.fetchone()

    def get_payload(self, record_id: str) -> dict | None:
        row = self.get_record(record_id)
        return row["payload"] if row else None

    def record_exists(self, record_id: str) -> bool:
        return self.get_record(record_id) is not None

    def find_by_kind(self, kind: str) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM kernel_record WHERE record_kind = %s ORDER BY record_time, record_id",
                (kind,),
            )
            return cur.fetchall()

    def edges_from(self, record_id: str, edge_type: str | None = None) -> list[dict]:
        q = "SELECT * FROM kernel_edge WHERE src_record_id = %s"
        args: list = [record_id]
        if edge_type:
            q += " AND edge_type = %s"
            args.append(edge_type)
        with self.conn.cursor() as cur:
            cur.execute(q + " ORDER BY edge_id", args)
            return cur.fetchall()

    def edges_to(self, record_id: str, edge_type: str | None = None) -> list[dict]:
        q = "SELECT * FROM kernel_edge WHERE dst_record_id = %s"
        args: list = [record_id]
        if edge_type:
            q += " AND edge_type = %s"
            args.append(edge_type)
        with self.conn.cursor() as cur:
            cur.execute(q + " ORDER BY edge_id", args)
            return cur.fetchall()

    def is_superseded(self, record_id: str) -> bool:
        return bool(self.edges_to(record_id, "LINEAGE_SUPERSEDES"))

    def in_force_consequences(self, farm_scope_ref: str,
                              as_of: str | None = None) -> list[dict]:
        """Accepted event consequences in force for a farm scope.

        In force NOW = payload says IN_FORCE and no LINEAGE_SUPERSEDES edge
        points at the record. With `as_of` (an ISO timestamp) the answer is
        reconstructed from the append-only substrate AS OF that moment on a
        SINGLE time axis — the server commit clock (`record_time`): a
        consequence counts if its record was committed by then and no
        LINEAGE_SUPERSEDES edge against it was committed by then. The record
        row and its supersession edge are written in one transaction and
        share that clock, so the reconstruction can never show a self-
        contradictory hole (or duplicate) at a supersession boundary. The
        payload's `acceptedAt` is a receipt of when acceptance was claimed —
        never the as-of selection key, which would mix the app clock with the
        edge's server clock and collapse Kernel rule 6 (times stay distinct).
        """
        with self.conn.cursor() as cur:
            if as_of is None:
                cur.execute(
                    """
                    SELECT r.* FROM kernel_record r
                    WHERE r.record_kind = 'ofarm.acceptedeventconsequence.v0.1'
                      AND r.payload ->> 'inForceState' = 'IN_FORCE'
                      AND r.payload -> 'anchorScopes' @> %s
                      AND NOT EXISTS (
                        SELECT 1 FROM kernel_edge e
                         WHERE e.dst_record_id = r.record_id
                           AND e.edge_type = 'LINEAGE_SUPERSEDES')
                    ORDER BY r.record_time, r.record_id
                    """,
                    (Jsonb([{"scopeType": "FARM", "scopeRef": farm_scope_ref}]),),
                )
            else:
                cur.execute(
                    """
                    SELECT r.* FROM kernel_record r
                    WHERE r.record_kind = 'ofarm.acceptedeventconsequence.v0.1'
                      AND r.payload ->> 'inForceState' = 'IN_FORCE'
                      AND r.payload -> 'anchorScopes' @> %s
                      AND r.record_time <= %s::timestamptz
                      AND NOT EXISTS (
                        SELECT 1 FROM kernel_edge e
                         WHERE e.dst_record_id = r.record_id
                           AND e.edge_type = 'LINEAGE_SUPERSEDES'
                           AND e.record_time <= %s::timestamptz)
                    ORDER BY r.record_time, r.record_id
                    """,
                    (Jsonb([{"scopeType": "FARM", "scopeRef": farm_scope_ref}]),
                     as_of, as_of),
                )
            return cur.fetchall()

    # -- conformance helpers ----------------------------------------------------

    def unreachable_authoritative_records(self) -> list[str]:
        """Records violating the reachability invariant (must always be [])."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.record_id FROM kernel_record r
                WHERE r.record_kind = ANY(%s)
                  AND NOT EXISTS (
                    SELECT 1 FROM kernel_edge e
                     WHERE e.edge_type = 'PROMOTION_EMITS'
                       AND e.dst_record_id = r.record_id)
                ORDER BY r.record_id
                """,
                (list(AUTHORITATIVE_KINDS),),
            )
            return [row["record_id"] for row in cur.fetchall()]
