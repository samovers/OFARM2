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
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from . import config
from .contracts import ContractRegistry, ContractViolation, sha256_of
from .profile_runtime import load_profile_runtime_descriptor
from .runtime_bundle import (
    RuntimeBundle,
    RuntimeBundleError,
    RuntimeComponentRole,
    require_tenant_ref,
    strict_json_document,
)
from .runtime_bundle_repository import RuntimeBundleRepository
from .schema_posture import (
    DatabaseObservation,
    configure_session,
    install_or_verify_schema,
    verify_transaction_posture,
)

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

_SCHEMA_SQL_BYTES = (config.PACKAGE_ROOT / "kernel" / "schema.sql").read_bytes()


class RuntimeBundleBindingError(RuntimeError):
    """The Store has no single verified RuntimeBundle for receipted work."""


class Store:
    def __init__(
        self,
        dsn: str | None = None,
        *,
        tenant_ref: str | None = None,
        runtime_bundle: RuntimeBundle | None = None,
        active_descriptor=None,
    ):
        self.dsn = dsn or config.database_dsn()
        self.registry = ContractRegistry()
        binding_values = (tenant_ref, runtime_bundle, active_descriptor)
        if any(value is not None for value in binding_values) and not all(
            value is not None for value in binding_values
        ):
            raise RuntimeBundleBindingError(
                "Store tenant_ref, runtime_bundle, and active_descriptor "
                "must be supplied together")
        if tenant_ref is not None:
            try:
                tenant_ref = require_tenant_ref(tenant_ref, "Store tenant_ref")
            except RuntimeBundleError as exc:
                raise RuntimeBundleBindingError(str(exc)) from exc
            selected_tenant_ref = runtime_bundle.selected_tenant_ref
            if (
                selected_tenant_ref is not None
                and tenant_ref != selected_tenant_ref
            ):
                raise RuntimeBundleBindingError(
                    f"Store tenant_ref {tenant_ref!r} does not match "
                    f"bundle-selected tenant {selected_tenant_ref!r}"
                )
        self._tenant_ref = tenant_ref
        self._runtime_bundle = runtime_bundle
        self._active_descriptor = active_descriptor
        self._selected_reference_snapshot_refs = frozenset(
            component.logical_ref
            for component in runtime_bundle.components
            if component.role is RuntimeComponentRole.REFERENCE_SNAPSHOT
        ) if runtime_bundle is not None else frozenset()
        if runtime_bundle is not None:
            self._verify_active_descriptor_binding()
        self._conn: psycopg.Connection | None = None
        self._startup_complete = False

    # -- connection / lifecycle ------------------------------------------------

    @property
    def conn(self) -> psycopg.Connection:
        if self._conn is None:
            self._conn = psycopg.connect(self.dsn, row_factory=dict_row, autocommit=True)
            configure_session(self._conn)
        elif self._conn.closed:
            raise RuntimeBundleBindingError(
                "this Store's database connection is closed; a fresh Store and "
                "completed process startup are required before further use"
            )
        return self._conn

    @property
    def runtime_bundle(self) -> RuntimeBundle:
        if self._runtime_bundle is None:
            raise RuntimeBundleBindingError(
                "this Store is intentionally unbound and cannot perform receipted work")
        return self._runtime_bundle

    @property
    def runtime_bundle_digest(self) -> str:
        return self.runtime_bundle.digest

    @property
    def selected_reference_snapshot_refs(self) -> frozenset[str]:
        self.runtime_bundle
        return self._selected_reference_snapshot_refs

    @property
    def active_descriptor(self):
        if self._active_descriptor is None:
            raise RuntimeBundleBindingError(
                "this Store is intentionally unbound and has no active descriptor")
        return self._active_descriptor

    def _verify_active_descriptor_binding(self) -> None:
        descriptor = self._active_descriptor
        component = self.runtime_bundle.component(
            RuntimeComponentRole.PROFILE_DESCRIPTOR,
            descriptor.profile_ref,
        )
        observed = load_profile_runtime_descriptor(
            descriptor.profile_root,
            descriptor_path=descriptor.descriptor_path,
        )
        _document, canonical_bytes = strict_json_document(
            descriptor.descriptor_path.read_bytes(),
            "active profile descriptor",
        )
        if observed != descriptor or canonical_bytes != component.canonical_bytes:
            raise RuntimeBundleBindingError(
                "active descriptor is not the exact descriptor selected by the "
                "Store RuntimeBundle"
            )

    @property
    def tenant_ref(self) -> str:
        if self._tenant_ref is None:
            raise RuntimeBundleBindingError(
                "this Store is intentionally unbound and has no tenant observation")
        return self._tenant_ref

    def _receipt(self) -> tuple[str, str]:
        return self.tenant_ref, self.runtime_bundle_digest

    def migrate(self) -> DatabaseObservation:
        """Apply the schema and install this Store's exact bundle atomically.

        ``runtime_bundle=None`` is reserved for the isolated RuntimeBundle
        repository tests, which need an empty persistence surface and may not
        write operational receipts.
        """
        with self.conn.transaction():
            with self.conn.cursor() as cur:
                posture = verify_transaction_posture(cur)
                schema_digest = install_or_verify_schema(cur, _SCHEMA_SQL_BYTES)
                if self._runtime_bundle is not None:
                    RuntimeBundleRepository().persist(
                        cur, self.tenant_ref, self.runtime_bundle)
                observation = DatabaseObservation(
                    schema_digest=schema_digest,
                    **posture,
                )
        return observation

    @contextmanager
    def _startup_transaction(self):
        """Publish readiness only after the complete startup unit commits."""
        prior_readiness = self._startup_complete
        self._startup_complete = False
        try:
            with self.conn.transaction():
                yield
        except BaseException:
            self._startup_complete = prior_readiness
            raise
        else:
            self._startup_complete = True

    def require_startup_complete(self, consumer: str) -> None:
        """Refuse high-level runtime services before verified startup commits."""
        if not self._startup_complete:
            raise RuntimeBundleBindingError(
                f"{consumer} requires completed schema, bundle, and profile startup"
            )

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()

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

    def insert_record(
        self, cur, payload: dict, *, tenant_ref: str | None = None
    ) -> str:
        """Validate against the package contract and append. Returns record id."""
        bound_tenant, bundle_digest = self._receipt()
        tenant_ref = bound_tenant if tenant_ref is None else tenant_ref
        if tenant_ref != bound_tenant:
            raise RuntimeBundleBindingError(
                f"record tenant {tenant_ref!r} is not the Store bundle tenant "
                f"{bound_tenant!r}")
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
             sha256_of(payload), tenant_ref, bundle_digest),
        )
        return record_id

    def runtime_trace_exists(self, trace_id: str) -> bool:
        tenant_ref, bundle_digest = self._receipt()
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM runtime_trace WHERE trace_id = %s "
                "AND tenant_ref = %s AND runtime_bundle_digest = %s",
                (trace_id, tenant_ref, bundle_digest),
            )
            return cur.fetchone() is not None

    def insert_runtime_trace(self, cur, payload: dict) -> str:
        """Append a draft-lane runtime evidence record (D16)."""
        tenant_ref, bundle_digest = self._receipt()
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
               tenant_ref, runtime_bundle_digest)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (trace_id, contract.kind, contract.schema_hash, Jsonb(payload),
             sha256_of(payload), tenant_ref, bundle_digest),
        )
        return trace_id

    def insert_reference_data(self, cur, snapshot_ref: str, data_family: str,
                              payload: dict, *, artifact_ref: str | None = None,
                              source_digest: str | None = None,
                              parser_label: str | None = None,
                              record_count: int | None = None) -> None:
        """Persist store-backed external reference-data for a snapshot (M2 P1) —
        candidate/audit data, NOT OFARM truth or runtime-selection authority.
        The payload is opaque here; one row per (snapshot_ref, data_family)."""
        tenant_ref, bundle_digest = self._receipt()
        cur.execute(
            """
            INSERT INTO reference_snapshot_data
              (snapshot_ref, data_family, artifact_ref, source_digest,
               parser_label, record_count, payload, payload_sha256,
               tenant_ref, runtime_bundle_digest)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (snapshot_ref, data_family, artifact_ref, source_digest, parser_label,
             record_count, Jsonb(payload), sha256_of(payload), tenant_ref,
             bundle_digest),
        )

    def reference_data(self, data_family: str) -> list[dict]:
        """Candidate/audit reference-data rows for one family.

        These rows are bundle-qualified and self-digest-checked, but they are not
        runtime-selection authority. Operational readers must use
        ``selected_reference_source_data`` so a cache fill cannot change lookup
        behavior under an already-selected RuntimeBundle.
        """
        tenant_ref, bundle_digest = self._receipt()
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT snapshot_ref, payload, payload_sha256 "
                "FROM reference_snapshot_data "
                "WHERE data_family = %s AND tenant_ref = %s "
                "AND runtime_bundle_digest = %s ORDER BY snapshot_ref",
                (data_family, tenant_ref, bundle_digest),
            )
            rows = cur.fetchall()
        for row in rows:
            if row["payload_sha256"] != sha256_of(row["payload"]):
                raise RuntimeBundleBindingError(
                    f"reference cache {row['snapshot_ref']!r} failed payload "
                    "digest verification"
                )
        return [
            {"snapshot_ref": row["snapshot_ref"], "payload": row["payload"]}
            for row in rows
        ]

    def selected_reference_source_data(self, snapshot_family: str) -> list[dict]:
        """Return exact bundle-selected JSON inputs for one snapshot family.

        A selected ReferenceSnapshot is operational only when it names exactly
        one retained ``REFERENCE_SOURCE`` artifact in this RuntimeBundle. The
        database reference cache is deliberately not consulted here: imports
        remain auditable candidates until a later bundle selects their exact
        source bytes.
        """
        selected = []
        for snapshot_component in self.runtime_bundle.components:
            if snapshot_component.role is not RuntimeComponentRole.REFERENCE_SNAPSHOT:
                continue
            snapshot_ref = snapshot_component.logical_ref
            if not (
                snapshot_ref == snapshot_family
                or snapshot_ref.startswith(snapshot_family + ".")
            ):
                continue
            try:
                snapshot, _canonical = strict_json_document(
                    snapshot_component.canonical_bytes,
                    f"selected reference snapshot {snapshot_ref!r}",
                )
                artifact_refs = [
                    ref for ref in snapshot.get("sourceArtifactRefs", [])
                    if isinstance(ref, str) and ref.startswith("artifact:")
                ]
                if len(artifact_refs) != 1:
                    raise RuntimeBundleError(
                        "operational reference snapshots must retain exactly one "
                        "artifact source"
                    )
                source = self.runtime_bundle.component(
                    RuntimeComponentRole.REFERENCE_SOURCE,
                    artifact_refs[0],
                )
                payload, _canonical = strict_json_document(
                    source.canonical_bytes,
                    f"selected reference source {artifact_refs[0]!r}",
                )
            except RuntimeBundleError as exc:
                raise RuntimeBundleBindingError(
                    f"selected reference snapshot {snapshot_ref!r} has no exact "
                    f"operational source: {exc}"
                ) from exc
            selected.append({
                "snapshot_ref": snapshot_ref,
                "artifact_ref": artifact_refs[0],
                "source_digest": source.content_digest,
                "payload": payload,
            })
        return sorted(selected, key=lambda row: row["snapshot_ref"])

    def add_edge(self, cur, edge_type: str, src_record_id: str, dst_record_id: str) -> None:
        tenant_ref, bundle_digest = self._receipt()
        endpoint_refs = {src_record_id, dst_record_id}
        cur.execute(
            "SELECT record_id FROM kernel_record "
            "WHERE tenant_ref = %s AND record_id = ANY(%s)",
            (tenant_ref, list(endpoint_refs)),
        )
        if {row["record_id"] for row in cur.fetchall()} != endpoint_refs:
            raise RuntimeBundleBindingError(
                "edge endpoints must both resolve inside the Store tenant"
            )
        cur.execute(
            "INSERT INTO kernel_edge "
            "(edge_type, src_record_id, dst_record_id, tenant_ref, runtime_bundle_digest) "
            "VALUES (%s, %s, %s, %s, %s)",
            (edge_type, src_record_id, dst_record_id, tenant_ref, bundle_digest),
        )

    def log_gate(
        self, cur, request_id: str, gate: str, outcome: str,
        *, reason_code: str | None = None, rationale: str | None = None,
        related_refs: list[str] | None = None,
    ) -> None:
        tenant_ref, bundle_digest = self._receipt()
        cur.execute(
            """
            INSERT INTO kernel_gate_log
              (request_id, gate, outcome, reason_code, rationale, related_refs,
               tenant_ref, runtime_bundle_digest)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (request_id, gate, outcome, reason_code, rationale,
             Jsonb(related_refs) if related_refs is not None else None,
             tenant_ref, bundle_digest),
        )

    # -- idempotency (ingress boundary RFC §2.4) -------------------------------

    def idempotency_lookup(self, cur, key: str) -> dict | None:
        cur.execute(
            "SELECT * FROM kernel_idempotency "
            "WHERE tenant_ref = %s AND idempotency_key = %s",
            (self.tenant_ref, key),
        )
        return cur.fetchone()

    def idempotency_claim(
        self, cur, key: str, request_id: str, source_payload_digest: str | None,
        result_record_id: str,
    ) -> None:
        tenant_ref, bundle_digest = self._receipt()
        cur.execute(
            """
            INSERT INTO kernel_idempotency
              (idempotency_key, request_id, source_payload_digest, result_record_id,
               tenant_ref, runtime_bundle_digest)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (key, request_id, source_payload_digest, result_record_id,
             tenant_ref, bundle_digest),
        )

    # -- reads -----------------------------------------------------------------
    # Canonical truth is tenant-scoped, not bundle-scoped: a new bundle must
    # still see the same tenant's immutable history and apply continuation law.

    def get_record(self, record_id: str) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM kernel_record "
                "WHERE record_id = %s AND tenant_ref = %s",
                (record_id, self.tenant_ref),
            )
            return cur.fetchone()

    def get_payload(self, record_id: str) -> dict | None:
        row = self.get_record(record_id)
        return row["payload"] if row else None

    def record_exists(self, record_id: str) -> bool:
        return self.get_record(record_id) is not None

    def find_by_kind(self, kind: str) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM kernel_record "
                "WHERE record_kind = %s AND tenant_ref = %s "
                "ORDER BY record_time, record_id",
                (kind, self.tenant_ref),
            )
            return cur.fetchall()

    def edges_from(self, record_id: str, edge_type: str | None = None) -> list[dict]:
        q = "SELECT * FROM kernel_edge WHERE src_record_id = %s AND tenant_ref = %s"
        args: list = [record_id, self.tenant_ref]
        if edge_type:
            q += " AND edge_type = %s"
            args.append(edge_type)
        with self.conn.cursor() as cur:
            cur.execute(q + " ORDER BY edge_id", args)
            return cur.fetchall()

    def edges_to(self, record_id: str, edge_type: str | None = None) -> list[dict]:
        q = "SELECT * FROM kernel_edge WHERE dst_record_id = %s AND tenant_ref = %s"
        args: list = [record_id, self.tenant_ref]
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
                      AND r.tenant_ref = %s
                      AND r.payload ->> 'inForceState' = 'IN_FORCE'
                      AND r.payload -> 'anchorScopes' @> %s
                      AND NOT EXISTS (
                        SELECT 1 FROM kernel_edge e
                         WHERE e.dst_record_id = r.record_id
                           AND e.edge_type = 'LINEAGE_SUPERSEDES'
                           AND e.tenant_ref = r.tenant_ref)
                    ORDER BY r.record_time, r.record_id
                    """,
                    (self.tenant_ref,
                     Jsonb([{"scopeType": "FARM", "scopeRef": farm_scope_ref}]),),
                )
            else:
                cur.execute(
                    """
                    SELECT r.* FROM kernel_record r
                    WHERE r.record_kind = 'ofarm.acceptedeventconsequence.v0.1'
                      AND r.tenant_ref = %s
                      AND r.payload ->> 'inForceState' = 'IN_FORCE'
                      AND r.payload -> 'anchorScopes' @> %s
                      AND r.record_time <= %s::timestamptz
                      AND NOT EXISTS (
                        SELECT 1 FROM kernel_edge e
                         WHERE e.dst_record_id = r.record_id
                           AND e.edge_type = 'LINEAGE_SUPERSEDES'
                           AND e.tenant_ref = r.tenant_ref
                           AND e.record_time <= %s::timestamptz)
                    ORDER BY r.record_time, r.record_id
                    """,
                    (self.tenant_ref,
                     Jsonb([{"scopeType": "FARM", "scopeRef": farm_scope_ref}]),
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
                  AND r.tenant_ref = %s
                  AND NOT EXISTS (
                    SELECT 1 FROM kernel_edge e
                     WHERE e.edge_type = 'PROMOTION_EMITS'
                       AND e.dst_record_id = r.record_id
                       AND e.tenant_ref = r.tenant_ref)
                ORDER BY r.record_id
                """,
                (list(AUTHORITATIVE_KINDS), self.tenant_ref),
            )
            return [row["record_id"] for row in cur.fetchall()]
