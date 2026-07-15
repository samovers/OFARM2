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

import re
from dataclasses import dataclass
from types import FunctionType

from .callable_state import capture_callable_state, callable_state_matches
from .context import mint
from .contracts import (
    ContractDispatchError,
    ContractViolation,
    UnknownContract,
    copy_exact_json,
    sha256_of,
)
from .problems import runtime_problem
from .store import (
    Store,
    _RETAINED_GOVERNED_CURSOR_EXECUTE_READ as _CURSOR_EXECUTE_READ,
    invoke_store_contract_validation as _VALIDATE_CONTRACT,
)

_FULL_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_PARSE_RESULT_FIELDS = frozenset({
    "ok", "sourceDigest", "artifactRef", "recordCount", "error", "records",
})
_RETAINED_EXACT_JSON_COPY = copy_exact_json
_RETAINED_EXACT_JSON_COPY_CODE = copy_exact_json.__code__
_RETAINED_EXACT_JSON_COPY_STATE = capture_callable_state(copy_exact_json)


def _capture_import_input(
        parse_result: ParseResult, snapshot_meta: dict,
        data_family: str | None,
        _copy=_RETAINED_EXACT_JSON_COPY,
        _copy_code=_RETAINED_EXACT_JSON_COPY_CODE,
        _copy_state=_RETAINED_EXACT_JSON_COPY_STATE,
        _state_matches=callable_state_matches,
        _getattribute=object.__getattribute__,
) -> dict:
    """Capture one private exact-JSON import envelope before any derivation."""
    if (type(_copy) is not FunctionType
            or _copy.__code__ is not _copy_code
            or not _state_matches(_copy, _copy_state)):
        raise ContractDispatchError("retained import snapshot helper changed")
    parse_fields = _getattribute(parse_result, "__dict__")
    if type(parse_fields) is not dict:
        raise RuntimeError("ParseResult storage identity is not exact")
    captured = _copy({
        "parseResult": parse_fields,
        "snapshotMeta": snapshot_meta,
        "dataFamily": data_family,
    })
    if (type(_copy) is not FunctionType
            or _copy.__code__ is not _copy_code
            or not _state_matches(_copy, _copy_state)):
        raise ContractDispatchError("retained import snapshot helper changed")
    parsed = captured["parseResult"]
    if set(parsed) != _PARSE_RESULT_FIELDS:
        raise RuntimeError("ParseResult field identity is not exact")
    if (type(parsed["ok"]) is not bool
            or (parsed["sourceDigest"] is not None
                and type(parsed["sourceDigest"]) is not str)
            or (parsed["artifactRef"] is not None
                and type(parsed["artifactRef"]) is not str)
            or (parsed["recordCount"] is not None
                and type(parsed["recordCount"]) is not int)
            or (parsed["error"] is not None
                and type(parsed["error"]) is not str)
            or (captured["dataFamily"] is not None
                and type(captured["dataFamily"]) is not str)):
        raise ContractViolation(
            "ImportRunner fields must use exact built-in JSON primitives")
    return captured


_RETAINED_CAPTURE_IMPORT_INPUT = _capture_import_input
_RETAINED_CAPTURE_IMPORT_INPUT_CODE = _capture_import_input.__code__
_RETAINED_CAPTURE_IMPORT_INPUT_STATE = capture_callable_state(
    _capture_import_input)
_RETAINED_SHA256_OF = sha256_of
_RETAINED_SHA256_OF_CODE = sha256_of.__code__
_RETAINED_SHA256_OF_STATE = capture_callable_state(sha256_of)
_RETAINED_VALIDATE_CONTRACT = _VALIDATE_CONTRACT
_RETAINED_VALIDATE_CONTRACT_CODE = _VALIDATE_CONTRACT.__code__
_RETAINED_VALIDATE_CONTRACT_STATE = capture_callable_state(
    _VALIDATE_CONTRACT)


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

    def _assert_runtime_composition(self) -> tuple[FunctionType, ...]:
        capture_input = _RETAINED_CAPTURE_IMPORT_INPUT
        digest = _RETAINED_SHA256_OF
        validate_contract = _RETAINED_VALIDATE_CONTRACT
        if (type(self) is not ImportRunner
                or type(self.store) is not Store
                or capture_input is not _capture_import_input
                or type(capture_input) is not FunctionType
                or capture_input.__code__ is not
                _RETAINED_CAPTURE_IMPORT_INPUT_CODE
                or not callable_state_matches(
                    capture_input,
                    _RETAINED_CAPTURE_IMPORT_INPUT_STATE)
                or digest is not sha256_of
                or type(digest) is not FunctionType
                or digest.__code__ is not _RETAINED_SHA256_OF_CODE
                or not callable_state_matches(
                    digest, _RETAINED_SHA256_OF_STATE)
                or validate_contract is not _VALIDATE_CONTRACT
                or type(validate_contract) is not FunctionType
                or validate_contract.__code__ is not
                _RETAINED_VALIDATE_CONTRACT_CODE
                or not callable_state_matches(
                    validate_contract,
                    _RETAINED_VALIDATE_CONTRACT_STATE)
                or any(callable(getattr(ImportRunner, name, None))
                       for name in vars(self))):
            if type(self.store) is Store:
                Store._mark_transaction_integrity_violation(self.store)
            raise RuntimeError(
                "ImportRunner runtime composition changed after construction")
        Store._require_runtime_dispatch_integrity(self.store)
        Store._require_transaction_python_posture(self.store)
        return capture_input, digest, validate_contract

    def _refuse(self, request_id: str, snapshot_id: str | None, reason_code: str,
                title: str, detail: str, *, remediation: str | None = None) -> dict:
        ImportRunner._assert_runtime_composition(self)
        problem = runtime_problem(reason_code, title, detail,
                                  suggested_remediation=remediation)
        with Store.serialized_tx(self.store) as cur:
            self.store.log_gate(cur, request_id, self.GATE, "REFUSED",
                                reason_code=reason_code, rationale=detail,
                                related_refs=[snapshot_id] if snapshot_id else None)
        return {"imported": False, "snapshotRef": None, "problem": problem}

    def run_import(
            self, parse_result: ParseResult, snapshot_meta: dict,
            *, data_family: str | None = None,
    ) -> dict:
        """Import a parsed reference source as a dated `ReferenceSnapshot`.

        Returns `{imported, snapshotRef, disposition, problem}`. One serialized
        transaction; on any failure only a gate-log refusal is written and NO
        snapshot (refuse over pretend — the prior in-force snapshot stays current).

        If `data_family` is given AND the parse carries `records`, the parsed
        DATA is persisted as store-backed reference-data (an index cache, NOT
        OFARM truth) keyed by (snapshot id, data_family), in the SAME serialized
        transaction as the snapshot + gate-log entry — so a scheme reader can
        later resolve the imported snapshot's content from the store. Generic:
        `records`/`data_family` are opaque here; no scheme literals (M2 P1).
        """
        capture_input, digest, validate_contract = \
            ImportRunner._assert_runtime_composition(self)
        if type(parse_result) is not ParseResult or type(snapshot_meta) is not dict:
            raise RuntimeError("ImportRunner input identity is not exact")
        captured = capture_input(
            parse_result, snapshot_meta, data_family)
        ImportRunner._assert_runtime_composition(self)
        parsed = captured["parseResult"]
        parse_ok = parsed["ok"]
        source_digest = parsed["sourceDigest"]
        artifact_ref = parsed["artifactRef"]
        record_count = parsed["recordCount"]
        parse_error = parsed["error"]
        records = parsed["records"]
        snapshot_meta = captured["snapshotMeta"]
        data_family = captured["dataFamily"]
        request_id = mint("import")
        snapshot_id = snapshot_meta.get("referenceSnapshotId")

        # 1. a failed / partial parse imports nothing
        if not parse_ok or not source_digest:
            return {**ImportRunner._refuse(self,
                request_id, snapshot_id, "SOURCE_FIDELITY_LOSS", "Import parse failed",
                parse_error or "the parser did not produce a complete, "
                "digestible source; no snapshot was written",
                remediation="fix the source/parse and re-run; the prior in-force "
                "snapshot remains current"), "disposition": "PARSE_FAILED"}

        matching_families = [
            family for family in self.store.runtime_bundle.descriptor.reference_families
            if isinstance(snapshot_id, str)
            and (snapshot_id == family.snapshot_prefix
                 or snapshot_id.startswith(family.snapshot_prefix + "."))
        ]
        if (len(matching_families) > 1
                or (len(matching_families) == 1
                    and data_family != matching_families[0].data_family)):
            return {**ImportRunner._refuse(self,
                request_id, snapshot_id, "SOURCE_FIDELITY_LOSS",
                "Import data family does not match runtime selection",
                "the snapshot identity maps to a RuntimeBundle reference family "
                "with a different exact data family; no restart-unsafe snapshot "
                "was written"), "disposition": "WRONG_DATA_FAMILY"}

        global_snapshot_ids = {
            component.logical_ref
            for component in self.store.runtime_bundle.components
            if (component.role == "REFERENCE_SNAPSHOT"
                and component.placement == "GLOBAL_IMMUTABLE_CONTENT")
        }
        if snapshot_id in global_snapshot_ids:
            return {**ImportRunner._refuse(self,
                request_id, snapshot_id, "DUPLICATE_IMPORT_AMBIGUOUS",
                "Import identifier collides with package reference",
                "a tenant import cannot reuse a globally authored ReferenceSnapshot "
                "identity, even for byte-equal content; mint a new dated identity"),
                "disposition": "GLOBAL_IDENTITY_COLLISION"}

        # A successful import must be restart-safe. This build retains the
        # canonical parsed data bytes, not arbitrary raw archives. Therefore a
        # source digest is acceptable only when it is a full SHA-256 of those
        # exact retained bytes. An `artifact:` ref without supplied/retained raw
        # bytes would be provenance theatre and would poison the next bundle.
        records_digest = (
            digest(records) if records is not None else None)
        metadata_artifact_refs = [
            ref for ref in snapshot_meta.get("sourceArtifactRefs", [])
            if isinstance(ref, str) and ref.startswith("artifact:")
        ]
        expected_digest_ref = f"digest:{source_digest}"
        metadata_digest_refs = [
            ref for ref in snapshot_meta.get("sourceArtifactRefs", [])
            if isinstance(ref, str) and ref.startswith("digest:")
        ]
        if (not _FULL_SHA256.fullmatch(source_digest)
                or (artifact_ref is not None
                    and (not artifact_ref
                         or artifact_ref.startswith(
                             ("artifact:", "digest:"))))
                or metadata_artifact_refs
                or any(ref != expected_digest_ref for ref in metadata_digest_refs)
                or not data_family
                or records is None
                or records_digest != source_digest):
            return {**ImportRunner._refuse(self,
                request_id, snapshot_id, "SOURCE_FIDELITY_LOSS",
                "Import source bytes are not retained",
                "the import does not provide a full SHA-256 over exact retained "
                "canonical data bytes, or names an artifact whose raw bytes are "
                "not retained; no restart-unsafe snapshot was written",
                remediation="retain exact source/data bytes with their full digest "
                "and retry"), "disposition": "SOURCE_NOT_RETAINED"}

        # 2. assemble the ReferenceSnapshot (the governed import record): the
        #    source digest + retained-artifact ref ride sourceArtifactRefs
        snapshot = dict(snapshot_meta)
        snapshot["schemaVersion"] = "ofarm.referencesnapshot.v0.1"
        refs = list(snapshot.get("sourceArtifactRefs", []))
        digest_ref = f"digest:{source_digest}"
        if artifact_ref and artifact_ref not in refs:
            refs.insert(0, artifact_ref)
        if digest_ref not in refs:
            refs.append(digest_ref)
        snapshot["sourceArtifactRefs"] = refs

        # 3. a malformed import record is a governed refusal, never a late
        #    ContractViolation that aborts the transaction ungoverned
        try:
            validate_contract(self.store, snapshot)
        except (ContractViolation, UnknownContract) as exc:
            return {**ImportRunner._refuse(self,
                request_id, snapshot_id, "SOURCE_FIDELITY_LOSS", "Import record malformed",
                f"the assembled ReferenceSnapshot is not contract-valid: {exc}"),
                "disposition": "INVALID_SNAPSHOT"}

        # 4. import inside the single serialized write transaction
        with Store.serialized_tx(self.store) as cur:
            existing = self.store.get_record(snapshot_id)
            if existing is not None:
                snapshot_contract = self.store.registry.get(
                    "ofarm.referencesnapshot.v0.1")
                expected_snapshot_digest = digest(snapshot)
                exact_snapshot = (
                    existing["record_kind"] == "ofarm.referencesnapshot.v0.1"
                    and existing["tenant_ref"] ==
                    self.store.runtime_bundle.tenant_ref
                    and existing["schema_hash"] == snapshot_contract.schema_hash
                    and existing["payload_sha256"] == expected_snapshot_digest
                    and digest(existing["payload"]) ==
                    expected_snapshot_digest
                    and existing["payload"] == snapshot
                )
                if exact_snapshot:
                    # The parsed-data table is recomputable, but it is part of a
                    # restartable bundle. Exact-verify it before calling this a
                    # replay; restore a missing row from the supplied retained
                    # bytes, and refuse an unequal identity reuse.
                    _CURSOR_EXECUTE_READ(cur,
                        "SELECT d.data_family, d.artifact_ref, d.source_digest, "
                        "d.parser_label, d.record_count, d.payload, d.payload_sha256 "
                        "FROM ONLY reference_snapshot_data d "
                        "JOIN ONLY runtime_bundle b "
                        "ON b.bundle_digest = d.runtime_bundle_digest "
                        "WHERE d.snapshot_ref = %s AND b.tenant_ref = %s",
                        (snapshot_id, self.store.runtime_bundle.tenant_ref),
                    )
                    data_rows = cur.fetchall()
                    data_row = next((row for row in data_rows
                                     if row["data_family"] == data_family), None)
                    expected_data = (
                        artifact_ref,
                        source_digest,
                        snapshot.get("canonicalVersionLabel"),
                        record_count,
                        records,
                        records_digest,
                    )
                    if any(row["data_family"] != data_family for row in data_rows):
                        problem = runtime_problem(
                            "DUPLICATE_IMPORT_AMBIGUOUS",
                            "Conflicting retained reference-data family",
                            f"reference data for {snapshot_id} already exists under "
                            "a different data family")
                        self.store.log_gate(
                            cur, request_id, self.GATE, "REFUSED",
                            reason_code="DUPLICATE_IMPORT_AMBIGUOUS",
                            rationale=problem["detail"], related_refs=[snapshot_id])
                        return {
                            "imported": False, "snapshotRef": None,
                            "disposition": "CONFLICT", "problem": problem,
                        }
                    if data_row is None:
                        self.store.insert_reference_data(
                            cur, snapshot_id, data_family, records,
                            artifact_ref=artifact_ref,
                            source_digest=source_digest,
                            parser_label=snapshot.get("canonicalVersionLabel"),
                            record_count=record_count)
                    else:
                        actual_data = (
                            data_row["artifact_ref"], data_row["source_digest"],
                            data_row["parser_label"], data_row["record_count"],
                            data_row["payload"], data_row["payload_sha256"],
                        )
                        if actual_data != expected_data:
                            problem = runtime_problem(
                                "DUPLICATE_IMPORT_AMBIGUOUS",
                                "Conflicting retained reference data",
                                f"reference data for {snapshot_id} already uses the "
                                "same identity with unequal bytes or provenance")
                            self.store.log_gate(
                                cur, request_id, self.GATE, "REFUSED",
                                reason_code="DUPLICATE_IMPORT_AMBIGUOUS",
                                rationale=problem["detail"],
                                related_refs=[snapshot_id])
                            return {
                                "imported": False, "snapshotRef": None,
                                "disposition": "CONFLICT", "problem": problem,
                            }
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

            # Invalidation posture (M2 G2, PR #10 review H2): the runner does NOT
            # broad-stale existing materializations on import. It relies on
            # context-key DRIFT — a new in-force ReferenceSnapshot changes the
            # ContextSnapshot (ContextAssembler folds the current reference
            # snapshots into the context basis), hence the MaterializationKey,
            # so a post-import NOW materialization never reuses a pre-import row
            # (D12). For G2's fixture scheme there is no SI context to stale at
            # all. P1/P2 (real scheduled REGSR/GERK imports) must confirm this
            # suffices or add an explicit broad-stale (invalidate_for_sources with
            # a farm/reference-family scope) — see the P1/P2 tickets.
            self.store.insert_record(cur, snapshot)
            # store-backed reference DATA (index cache, not OFARM truth) so a
            # scheme reader can resolve this snapshot's content from the store;
            # same serialized transaction as the snapshot + gate-log (M2 P1).
            # Opaque here — `records` and `data_family` are passed through.
            if data_family and records is not None:
                self.store.insert_reference_data(
                    cur, snapshot_id, data_family, records,
                    artifact_ref=artifact_ref,
                    source_digest=source_digest,
                    parser_label=snapshot.get("canonicalVersionLabel"),
                    record_count=record_count)
            self.store.log_gate(
                cur, request_id, self.GATE, "IMPORTED",
                rationale=f"{snapshot.get('referenceClass')} snapshot effective "
                          f"{snapshot.get('effectiveFrom')}"
                          + (f"; {record_count} records"
                             if record_count is not None else ""),
                related_refs=[snapshot_id, digest_ref])
        return {"imported": True, "snapshotRef": snapshot_id,
                "disposition": "IMPORTED", "problem": None}
