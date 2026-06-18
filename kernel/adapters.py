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

    def run_import(self, parse_result: ParseResult, snapshot_meta: dict) -> dict:
        """Import a parsed reference source as a dated `ReferenceSnapshot`.

        Returns `{imported, snapshotRef, disposition, problem}`. One serialized
        transaction; on any failure only a gate-log refusal is written and NO
        snapshot (refuse over pretend — the prior in-force snapshot stays current).
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
                if existing["payload_sha256"] == sha256_of(snapshot):
                    # idempotent re-import of identical content: a governed no-op
                    self.store.log_gate(cur, request_id, self.GATE, "REPLAY_REUSED",
                                        rationale="identical snapshot already imported",
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

            self.store.insert_record(cur, snapshot)
            self.store.log_gate(
                cur, request_id, self.GATE, "IMPORTED",
                rationale=f"{snapshot.get('referenceClass')} snapshot effective "
                          f"{snapshot.get('effectiveFrom')}"
                          + (f"; {parse_result.recordCount} records"
                             if parse_result.recordCount is not None else ""),
                related_refs=[snapshot_id, digest_ref])
        return {"imported": True, "snapshotRef": snapshot_id,
                "disposition": "IMPORTED", "problem": None}
