"""Governed adapter / import mechanism (M2 G2).

A generic, SERIALIZED, GOVERNED import runner: it turns a parser's output into a
dated `ReferenceSnapshot` (the governed import record) plus a gate-log entry, in
a single serialized transaction shared with user commits (`store.serialized_tx`
— the single-writer invariant, `M2_BRIEF.md` "Adapter discipline"). A failed or
partial parse writes a refusal trace and **no** snapshot — never a silent or
half-applied state change (Kernel rule 7).

Scheme-agnostic: this module knows nothing about REGSR / GERK / FFSNaprave. The
SI adapters (P1–P3) reuse the `tooling/` parsers as libraries, wrap their output
in a `ParseResult`, and pass scheme-specific snapshot metadata in `snapshot_meta`.
The `ReferenceSnapshot` IS the governed import record: the source digest and the
retained-artifact ref ride `sourceArtifactRefs`, the effective date is
`effectiveFrom`, and the parser/version label is `canonicalVersionLabel`.

Audit posture: each import attempt is recorded as an append-only `kernel_gate_log`
row (IMPORTED / REFUSED / REPLAY_REUSED). A refusal also returns a `RuntimeProblem`
as data — it is NOT persisted as a standalone `RuntimeProblem` record (contracts
are frozen; the gate log is the enforcement trace). A first-class import-result
contract is out of scope for G2.
"""
from __future__ import annotations

from dataclasses import dataclass

from .context import mint
from .contracts import ContractViolation, UnknownContract, sha256_of
from .problems import runtime_problem


@dataclass
class ParseResult:
    """A parser's output, normalized for the generic runner. `ok=False` (or a
    missing `sourceDigest`) is a failed/partial parse and imports nothing. The
    scheme-specific content lives in `records` and is opaque to the runner."""
    ok: bool
    sourceDigest: str | None = None     # digest of the parsed source artifact
    artifactRef: str | None = None      # where the artifact is retained, e.g. "artifact:..."
    recordCount: int | None = None
    error: str | None = None
    records: object = None              # opaque scheme-specific payload (unused here)


class ImportRunner:
    """Runs governed reference-source imports through the single serialized
    write path. No scheme literals live here."""

    GATE = "GOVERNED_IMPORT"

    def __init__(self, store):
        store.require_startup_complete("ImportRunner")
        self.store = store

    def _refuse(self, request_id: str, snapshot_id: str | None, reason_code: str,
                title: str, detail: str, *, remediation: str | None = None) -> dict:
        problem = runtime_problem(reason_code, title, detail,
                                  suggested_remediation=remediation)
        with self.store.serialized_tx() as cur:
            self.store.log_gate(cur, request_id, self.GATE, "REFUSED",
                                reason_code=reason_code, rationale=detail,
                                related_refs=[snapshot_id] if snapshot_id else None)
        return {"imported": False, "snapshotRef": None, "problem": problem}

    def run_import(self, parse_result: ParseResult, snapshot_meta: dict,
                   *, data_family: str | None = None) -> dict:
        """Import a parsed reference source as a dated `ReferenceSnapshot`.

        Returns `{imported, snapshotRef, disposition, problem}`. One serialized
        transaction; on any failure only a gate-log refusal is written and NO
        snapshot (refuse over pretend — the prior in-force snapshot stays current).

        If `data_family` is given AND the parse carries `records`, the parsed
        DATA is persisted as store-backed candidate/audit data keyed by
        (snapshot id, data_family), in the SAME serialized transaction as the
        snapshot + gate-log entry. It is never runtime-selection authority;
        operational use requires a later RuntimeBundle retaining the exact
        source bytes. Generic: `records`/`data_family` are opaque here; no scheme
        literals (M2 P1).
        """
        request_id = mint("import")
        snapshot_id = snapshot_meta.get("referenceSnapshotId")

        # 1. a failed / partial parse imports nothing
        if not parse_result.ok or not parse_result.sourceDigest:
            return {**self._refuse(
                request_id, snapshot_id, "SOURCE_FIDELITY_LOSS", "Import parse failed",
                parse_result.error or "the parser did not produce a complete, "
                "digestible source; no snapshot was written",
                remediation="fix the source/parse and re-run; the prior in-force "
                "snapshot remains current"), "disposition": "PARSE_FAILED"}

        # 2. assemble the ReferenceSnapshot (the governed import record): the
        #    source digest + retained-artifact ref ride sourceArtifactRefs
        snapshot = dict(snapshot_meta)
        snapshot["schemaVersion"] = "ofarm.referencesnapshot.v0.1"
        refs = list(snapshot.get("sourceArtifactRefs", []))
        digest_ref = f"digest:{parse_result.sourceDigest}"
        if parse_result.artifactRef and parse_result.artifactRef not in refs:
            refs.insert(0, parse_result.artifactRef)
        if digest_ref not in refs:
            refs.append(digest_ref)
        snapshot["sourceArtifactRefs"] = refs

        # 3. a malformed import record is a governed refusal, never a late
        #    ContractViolation that aborts the transaction ungoverned
        try:
            self.store.registry.validate(snapshot)
        except (ContractViolation, UnknownContract) as exc:
            return {**self._refuse(
                request_id, snapshot_id, "SOURCE_FIDELITY_LOSS", "Import record malformed",
                f"the assembled ReferenceSnapshot is not contract-valid: {exc}"),
                "disposition": "INVALID_SNAPSHOT"}

        # 4. import inside the single serialized write transaction
        with self.store.serialized_tx() as cur:
            existing = self.store.get_record(snapshot_id)
            if existing is not None:
                if (
                    existing["payload_sha256"] == sha256_of(snapshot)
                    and existing["payload"] == snapshot
                ):
                    # Canonical truth is reused. Parsed candidate/audit data is
                    # bundle-scoped provenance only; operational readers never
                    # activate it or another bundle's parser output.
                    if data_family and parse_result.records is not None:
                        cur.execute(
                            "SELECT snapshot_ref, data_family, artifact_ref, source_digest, "
                            "parser_label, record_count, payload, payload_sha256, tenant_ref, "
                            "runtime_bundle_digest FROM reference_snapshot_data "
                            "WHERE snapshot_ref = %s AND data_family = %s "
                            "AND tenant_ref = %s AND runtime_bundle_digest = %s",
                            (snapshot_id, data_family, self.store.tenant_ref,
                             self.store.runtime_bundle_digest),
                        )
                        cached = cur.fetchone()
                        parsed_digest = sha256_of(parse_result.records)
                        expected_cache = {
                            "snapshot_ref": snapshot_id,
                            "data_family": data_family,
                            "artifact_ref": parse_result.artifactRef,
                            "source_digest": parse_result.sourceDigest,
                            "parser_label": snapshot.get("canonicalVersionLabel"),
                            "record_count": parse_result.recordCount,
                            "payload": parse_result.records,
                            "payload_sha256": parsed_digest,
                            "tenant_ref": self.store.tenant_ref,
                            "runtime_bundle_digest": self.store.runtime_bundle_digest,
                        }
                        if cached is None:
                            self.store.insert_reference_data(
                                cur, snapshot_id, data_family, parse_result.records,
                                artifact_ref=parse_result.artifactRef,
                                source_digest=parse_result.sourceDigest,
                                parser_label=snapshot.get("canonicalVersionLabel"),
                                record_count=parse_result.recordCount)
                        elif cached != expected_cache:
                            problem = runtime_problem(
                                "DUPLICATE_IMPORT_AMBIGUOUS",
                                "Conflicting parsed cache",
                                f"referenceSnapshotId {snapshot_id} already has "
                                "different parsed data under the active RuntimeBundle; "
                                "refused rather than replacing audit data silently")
                            self.store.log_gate(
                                cur, request_id, self.GATE, "REFUSED",
                                reason_code="DUPLICATE_IMPORT_AMBIGUOUS",
                                rationale=problem["detail"],
                                related_refs=[snapshot_id])
                            return {"imported": False, "snapshotRef": None,
                                    "disposition": "CONFLICT", "problem": problem}
                    # Idempotent canonical re-import, with this bundle-qualified
                    # candidate/audit row now verified or recorded.
                    self.store.log_gate(cur, request_id, self.GATE, "REPLAY_REUSED",
                                        rationale="identical snapshot already imported; "
                                                  "bundle-qualified audit data verified",
                                        related_refs=[snapshot_id])
                    return {"imported": True, "snapshotRef": snapshot_id,
                            "disposition": "ALREADY_IMPORTED", "problem": None}
                problem = runtime_problem(
                    "DUPLICATE_IMPORT_AMBIGUOUS", "Conflicting re-import",
                    f"referenceSnapshotId {snapshot_id} already names a snapshot with "
                    "different content; mint a new dated snapshot id rather than "
                    "overwriting (append-only)")
                self.store.log_gate(cur, request_id, self.GATE, "REFUSED",
                                    reason_code="DUPLICATE_IMPORT_AMBIGUOUS",
                                    rationale=problem["detail"], related_refs=[snapshot_id])
                return {"imported": False, "snapshotRef": None,
                        "disposition": "CONFLICT", "problem": problem}

            # A governed import retains a candidate ReferenceSnapshot and its
            # parsed data, but does not hot-activate it. Runtime selection stays
            # frozen to the active RuntimeBundle; selecting a newer snapshot
            # requires a new bundle (issue #171, no automatic migration).
            self.store.insert_record(cur, snapshot)
            # Store-backed candidate/audit DATA, not OFARM truth and never
            # runtime-selection authority; same serialized transaction as the
            # snapshot + gate-log (M2 P1). Opaque here — `records` and
            # `data_family` are passed through.
            if data_family and parse_result.records is not None:
                self.store.insert_reference_data(
                    cur, snapshot_id, data_family, parse_result.records,
                    artifact_ref=parse_result.artifactRef,
                    source_digest=parse_result.sourceDigest,
                    parser_label=snapshot.get("canonicalVersionLabel"),
                    record_count=parse_result.recordCount)
            self.store.log_gate(
                cur, request_id, self.GATE, "IMPORTED",
                rationale=f"{snapshot.get('referenceClass')} snapshot effective "
                          f"{snapshot.get('effectiveFrom')}"
                          + (f"; {parse_result.recordCount} records"
                             if parse_result.recordCount is not None else ""),
                related_refs=[snapshot_id, digest_ref])
        return {"imported": True, "snapshotRef": snapshot_id,
                "disposition": "IMPORTED", "problem": None}
