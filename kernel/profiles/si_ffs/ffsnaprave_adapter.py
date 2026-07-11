"""SI FFSNaprave adapter (M2 P3) — package content for the UVHVVR sprayer-
inspection register (`SI:FFS-NAPRAVE`, `spletni2.furs.gov.si/FFS/FFSNaprave/`).

Wires the official yearly inspection download to the GENERIC mechanisms: it
parses the delimited file (the official TXT, semicolon-delimited, 20-field
dictionary), imports it as a dated FFSNaprave `ReferenceSnapshot` through the
generic G2 `ImportRunner`, persists the parsed inspections store-backed, and lets
a farm sprayer MATCH by its inspection-sticker number — the D9-style composite
key `StevilkaZnaka` (sticker number) + `VeljavnostZnaka` (sticker validity). A
match captures a `REGISTRY_EXTRACT` `EvidenceRecord` (capture != commitment,
Kernel rule 3) whose id populates `EquipmentIdentityPayload.inspectionEvidenceRefs`
on the Equipment identity committed through G1. ALL FFSNaprave specifics live
HERE; kernel/adapters.py and the generic kernel stay scheme-agnostic.

Posture / claim limits: FFSNaprave is the one strong-currentness surface in the
SI profile (official machine-readable yearly downloads). A sticker MATCH records
that an inspection exists in the dated register — advisory inspection evidence,
NEVER a current-compliance claim for the equipment or the pilot (D7). NO match
records the equipment WITHOUT inspection evidence (surfaced honestly, never a
silent pass-as-compliant). No live integration; scheduled-import invalidation
rides context-key drift (D19), as P1/P2. All repo fixtures are fictional and
format-true; owner-residence / inspection-location municipality fields are NOT
cached (not needed for the match; privacy-conservative, D14).
"""
from __future__ import annotations

import copy
import csv
import hashlib

from pathlib import Path

from ...adapters import ImportRunner, ParseResult
from ...authority import AuthorityEvaluator
from ...context import now_iso
from ...runtime_bundle import (
    RuntimeBundleError,
    _copy_runtime_cache_value,
    _freeze_runtime_cache,
    require_store_runtime_bundle,
)
from ...contracts import canonical_json, sha256_of
from ...problems import runtime_problem

# FFSNaprave scheme constants (SI-specific). Mirror the shipped example shape.
FFSNAPRAVE_AUTHORITY_REF = "party:si.uvhvvr"
FFSNAPRAVE_JURISDICTION_REF = "jurisdiction:SI"
FFSNAPRAVE_SCHEME = "SI:FFS-NAPRAVE"
FFSNAPRAVE_KEY_FIELD = "stevilka-znaka"          # the inspection-sticker number
FFSNAPRAVE_DOMAIN = "SI sprayer-inspection register (UVHVVR FFSNaprave)"
FFSNAPRAVE_SOURCE_SURFACE = "surface:spletni2.furs.gov.si.FFS.FFSNaprave"
FFSNAPRAVE_SNAPSHOT_PREFIX = "referencesnapshot:si.uvhvvr.ffs-naprave"
FFSNAPRAVE_DATA_FAMILY = "si.uvhvvr.ffs-naprave"

# The official yearly machine-readable download — the one strong-currentness
# surface (D7). Declared, not scheduled here (an injectable trigger imports).
FFSNAPRAVE_CADENCE = {
    "period": "ANNUAL",
    "posture": "official yearly TXT/XLS/XML download (strong-currentness surface, D7)",
    "liveIntegration": False,
}

# the D9-style composite identity key: sticker number + sticker validity
STICKER_FIELD = "StevilkaZnaka"
VALIDITY_FIELD = "VeljavnostZnaka"
# inspection / machine-identity fields retained in the store-backed index. The
# owner-residence and inspection-location municipality/region fields of the
# 20-field dictionary are intentionally NOT cached — not needed for the sticker
# match, and the most person-locating (privacy-conservative, D14).
RETAINED_FIELDS = (
    "NapravaID", "StatusNaprave", "SkladnostNaprave", "ZadnjaStevilkaZnaka",
    "VeljavnostZnaka", "ZadnjiPregled", "VrstaNaprave", "Izdelovalec",
    "LetoIzdelave", "TipNaprave", "SerijskaStevilka", "LetoNakupa", "PregledID",
    "LetoPregleda", "DatumPregleda", "StevilkaZnaka", "SkladnostObPregledu")

def _conflicting_inspection(inspections):
    """The first (StevilkaZnaka, VeljavnostZnaka) composite that appears with
    DIFFERING other attributes, or None. Exact duplicates are not a conflict; a
    sticker appearing with *different* validity windows is NOT a conflict either
    (separate inspection cycles) — only the same composite key carrying different
    inspection detail is hidden last-wins truth, governed at import."""
    seen: dict = {}
    for r in inspections:
        key = (r.get(STICKER_FIELD), r.get(VALIDITY_FIELD))
        rest = tuple(sorted((k, v) for k, v in r.items()
                            if k not in (STICKER_FIELD, VALIDITY_FIELD)))
        if key in seen:
            if seen[key] != rest:
                return key
        else:
            seen[key] = rest
    return None


def parse_ffsnaprave_file(path, *, file_date=None, version_label=None) -> dict:
    """Parse a saved FFSNaprave delimited download (the official TXT) into an
    inspection artifact. The file vintage (`file_date`) is NOT in the rows — it
    dates the yearly snapshot and the caller supplies it (a parse without it is
    refused at import). Ragged/short rows are skipped into `rowProblems`, never an
    IndexError; an empty file yields no header (refused at import)."""
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig", errors="replace")
    sample = text[:4096]
    # the official TXT is semicolon-delimited; detect among ; \t , defensively
    delim = max((";", "\t", ","), key=sample.count)
    rows = [r for r in csv.reader(text.splitlines(), delimiter=delim)]
    header = rows[0] if rows else []
    has_key = STICKER_FIELD in header and VALIDITY_FIELD in header
    inspections, row_problems = [], []
    if has_key:
        idx = {name: header.index(name) for name in RETAINED_FIELDS if name in header}
        for n, row in enumerate(rows[1:]):
            if not row or all(not c.strip() for c in row):
                continue                       # blank line — not a row problem
            if len(row) != len(header):
                # a row whose column count differs from the header is RAGGED. We
                # must check the TRUE header width, not just the widest RETAINED
                # index: the composite key (StevilkaZnaka) sits interior in the
                # official 20-field schema, with non-retained fields on both sides,
                # so a dropped INTERIOR field shifts every later column and the key
                # would read the wrong cell. Never read a misaligned row at fixed
                # offsets — route it to rowProblems -> PARTIAL_PARSE refusal.
                row_problems.append({"row": n, "problem":
                                     f"ragged row: {len(row)} columns, header has {len(header)}"})
                continue
            rec = {name: row[i].strip() for name, i in idx.items()}
            if not rec.get(STICKER_FIELD) or not rec.get(VALIDITY_FIELD):
                # the D9-style identity is the COMPOSITE key (sticker + validity).
                # A row missing EITHER component cannot be a complete identity and
                # must NOT be indexed as sticker-only — flag it so the import refuses
                # (PARTIAL_PARSE), never a composite-key-collapsed capture (PR #14 B3).
                row_problems.append({"row": n, "problem":
                                     "missing composite key component "
                                     "(StevilkaZnaka and/or VeljavnostZnaka)"})
                continue
            inspections.append(rec)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    return {
        "snapshotKind": "SI_UVHVVR_FFS_NAPRAVE_PARSE",
        "fileDate": file_date,
        "canonicalVersionLabel": version_label,
        "keyFieldsPresent": has_key,
        "attributesAvailable": list(header),
        "inspectionCount": len(inspections),
        "inspections": inspections,
        "rowProblems": row_problems,
        "inputs": [{"file": p.name, "digest": f"sha256:{digest}"}],
    }


def import_ffsnaprave_snapshot(store, artifact, *, file_date=None, version_label=None,
                               source_artifact_ref=None) -> dict:
    """Import a parsed FFSNaprave file as a dated FFSNaprave `ReferenceSnapshot`
    via the generic G2 ImportRunner. The effective date is the yearly vintage; the
    source digest + surface ride sourceArtifactRefs; the parsed inspections are
    persisted store-backed (an index cache, NOT OFARM truth). Every parse/fidelity
    failure is a governed refusal (no snapshot, no data)."""
    file_date = file_date or artifact.get("fileDate")

    def _refuse(error: str, disposition: str) -> dict:
        # Route every failure through the GENERIC governed refusal path — a real
        # RuntimeProblem AND a GOVERNED_IMPORT/REFUSED gate-log entry, no snapshot/
        # data — never a hand-built mini problem (PR #12 review). No snapshot id to
        # reference (the vintage dates it), so the refusal carries no related ref.
        result = ImportRunner(store).run_import(
            ParseResult(ok=False, error=error),
            {"referenceSnapshotId": None}, data_family=FFSNAPRAVE_DATA_FAMILY)
        return {**result, "disposition": disposition, "fileDate": file_date}

    if not file_date:
        return _refuse("FFSNaprave parse carries no file vintage date; cannot date "
                       "a snapshot", "NO_FILE_DATE")
    if not artifact.get("keyFieldsPresent"):
        return _refuse("FFSNaprave parse found no StevilkaZnaka/VeljavnostZnaka "
                       "columns; no sticker is resolvable", "NO_STICKER_FIELD")
    if artifact.get("rowProblems"):
        return _refuse(
            f"FFSNaprave parse skipped {len(artifact['rowProblems'])} malformed "
            "row(s); a partial file is a source-fidelity loss (a dropped sticker "
            "would later read as un-inspected) — refuse rather than import a "
            "partial register", "PARTIAL_PARSE")
    if not artifact.get("inspections"):
        return _refuse("FFSNaprave parse yielded no inspections; nothing to import",
                       "NO_INSPECTIONS")
    conflict = _conflicting_inspection(artifact["inspections"])
    if conflict is not None:
        return _refuse(
            f"sticker {conflict[0]} / validity {conflict[1]} appears with conflicting "
            "inspection detail; the register cannot be reduced to one inspection per "
            "(sticker, validity) — refuse rather than silently pick last-wins",
            "CONFLICTING_INSPECTION")
    sid = f"{FFSNAPRAVE_SNAPSHOT_PREFIX}.{file_date}"
    # Digest the WHOLE parsed artifact (every inspection + attribute), never just
    # the input file digest, so any content change re-imports as a CONFLICT, never
    # a silent ALREADY_IMPORTED replay that leaves stale inspections (PR #12 B1).
    digest = sha256_of(artifact)
    meta = {
        "referenceSnapshotId": sid,
        "referenceClass": "OTHER_REFERENCE",
        "domain": FFSNAPRAVE_DOMAIN,
        "issuingAuthorityRef": FFSNAPRAVE_AUTHORITY_REF,
        "jurisdictionRef": FFSNAPRAVE_JURISDICTION_REF,
        "canonicalVersionLabel": (version_label or artifact.get("canonicalVersionLabel")
                                  or f"ffs-naprave-{file_date}"),
        "effectiveFrom": f"{file_date}T00:00:00Z",
        "sourceArtifactRefs": [FFSNAPRAVE_SOURCE_SURFACE],
        "notes": "FFSNaprave official yearly inspection download (the strong-"
                 "currentness surface, D7). A sticker match is advisory inspection "
                 "evidence, never a current-compliance claim.",
    }
    result = ImportRunner(store).run_import(
        ParseResult(ok=True, sourceDigest=digest, artifactRef=source_artifact_ref,
                    recordCount=artifact.get("inspectionCount"), records=artifact),
        meta, data_family=FFSNAPRAVE_DATA_FAMILY)
    return {**result, "fileDate": file_date}


class FFSNapraveRegister:
    """Offline FFSNaprave inspection lookup for the in-force snapshots (package
    content). A farm sprayer matches by the inspection-sticker number on the
    machine — the composite key `StevilkaZnaka` + `VeljavnostZnaka`. A missing or
    ambiguous match is surfaced as None, never a fabricated inspection."""

    def __setattr__(self, name, value):
        if (getattr(self, "_frozen", False)
                and name in {"runtime_bundle", "_by_snapshot", "_frozen"}):
            raise AttributeError(
                "FFSNapraveRegister runtime composition is immutable")
        object.__setattr__(self, name, value)

    def __init__(self, *, runtime_bundle=None):
        self.runtime_bundle = runtime_bundle
        self._by_snapshot: dict[str, dict] = {}
        self._frozen = False
        if runtime_bundle is not None:
            self._load_runtime_bundle_bytes()
            self.freeze()

    def _load_runtime_bundle_bytes(self) -> None:
        for reference in self.runtime_bundle.selected_references:
            if reference.data_family != FFSNAPRAVE_DATA_FAMILY:
                continue
            self.register_artifact(
                reference.snapshot_ref,
                self.runtime_bundle.reference_data_payload(
                    reference.snapshot_ref, FFSNAPRAVE_DATA_FAMILY),
            )

    def register_artifact(self, snapshot_id: str, artifact: dict) -> None:
        if self._frozen:
            raise RuntimeError(
                "FFSNapraveRegister is immutable for the RuntimeBundle lifetime")
        inspections = copy.deepcopy(artifact.get("inspections", []))
        # defense-in-depth: import already refuses a conflicting composite key, so
        # store-loaded data is conflict-free — but never build a last-wins index
        # from a direct/raw call either.
        conflict = _conflicting_inspection(inspections)
        if conflict is not None:
            raise ValueError(
                f"sticker {conflict[0]}/validity {conflict[1]} carries conflicting "
                "inspection detail; refusing to build a last-wins index")
        by_key, by_sticker = {}, {}
        for r in inspections:
            sticker = r.get(STICKER_FIELD)
            if not sticker:
                continue
            by_key[(sticker, r.get(VALIDITY_FIELD))] = r
            by_sticker.setdefault(sticker, []).append(r)
        self._by_snapshot[snapshot_id] = {"byKey": by_key, "bySticker": by_sticker}

    def freeze(self) -> None:
        """End construction and recursively freeze retained lookup state."""
        if self._frozen:
            return
        object.__setattr__(self, "_by_snapshot", _freeze_runtime_cache(
            self._by_snapshot))
        object.__setattr__(self, "_frozen", True)

    def load_from_store(self, store) -> None:
        """Load store-backed inspections persisted by a governed import (M2 P3),
        so a scheduled-import file's inspections resolve from the store."""
        if self.runtime_bundle is not None:
            require_store_runtime_bundle(
                store, self.runtime_bundle, "FFSNaprave register load")
            if not self._frozen:
                raise RuntimeBundleError(
                    "bundle-backed FFSNaprave cache was not frozen at construction")
            return
        for row in store.reference_data(FFSNAPRAVE_DATA_FAMILY):
            sid = row["snapshot_ref"]
            if sid not in self._by_snapshot:
                self.register_artifact(sid, row["payload"])

    def validity_windows(self, snapshot_id: str, sticker_number: str) -> list:
        """The distinct VeljavnostZnaka windows recorded for a sticker in a snapshot.
        Empty = the sticker is absent; more than one = the composite key is ambiguous
        without a supplied validity (a caller must disambiguate, never collapse)."""
        data = self._by_snapshot.get(snapshot_id)
        if self.runtime_bundle is not None and data is None:
            raise RuntimeBundleError(
                f"FFSNaprave snapshot {snapshot_id!r} is not selected with retained "
                "bytes in this RuntimeBundle")
        if not data:
            return []
        return sorted({r.get(VALIDITY_FIELD) for r in data["bySticker"].get(sticker_number, [])
                       if r.get(VALIDITY_FIELD)})

    def match(self, snapshot_id: str, sticker_number: str, validity: str | None = None) -> dict | None:
        """The inspection record for a sticker in a dated snapshot. With `validity`
        the composite key resolves exactly; without it, a sticker that resolves to
        ONE validity window matches, but multiple windows are ambiguous → None (the
        farmer reads both off the sticker; the runtime never guesses which)."""
        data = self._by_snapshot.get(snapshot_id)
        if self.runtime_bundle is not None and data is None:
            raise RuntimeBundleError(
                f"FFSNaprave snapshot {snapshot_id!r} is not selected with retained "
                "bytes in this RuntimeBundle")
        if not data:
            return None
        if validity is not None:
            return _copy_runtime_cache_value(
                data["byKey"].get((sticker_number, validity)))
        candidates = data["bySticker"].get(sticker_number, [])
        distinct = {r.get(VALIDITY_FIELD): r for r in candidates}
        return _copy_runtime_cache_value(
            next(iter(distinct.values())) if len(distinct) == 1 else None)


def attach_inspection_evidence(store, register, snapshot_id, sticker_number, *,
                               captured_by, farm_ref, validity=None) -> dict:
    """Match a farm sprayer's inspection sticker against a dated FFSNaprave snapshot
    and, on an AUTHORISED match, CAPTURE a `REGISTRY_EXTRACT` `EvidenceRecord`
    recording that the inspection exists in the register. Returns
    `{attached, evidenceRef, disposition, problem}`:

      * NO match                      -> attached False, NO_MATCH (advisory: the
                                         equipment is recorded WITHOUT inspection
                                         evidence, never a silent pass-as-compliant);
      * `captured_by` is unknown / not
        ACTIVE / lacks OBSERVE_ATTACH_
        EVIDENCE on the farm scope     -> attached False, UNAUTHORIZED + a governed
                                         problem (the authorization trace is recorded);
      * authorised match              -> attached True, CAPTURED (or ALREADY_CAPTURED).

    Capture is GOVERNED, not a raw side-channel insert (PR #14 hostile B1): the
    GENERIC `AuthorityEvaluator` evaluates `OBSERVE_ATTACH_EVIDENCE` for
    `captured_by` over the FARM scope (the same evaluator + action the gate uses),
    the decision (request/trace/result) is recorded, and the EvidenceRecord anchors
    to that farm scope. (The generic EVIDENCE_RECORD commit class has no emitter in
    M1 — it retains as draft — so capture is gated here via the evaluator directly
    rather than the commit pipeline; flagged as a kernel gap.) The evidence id is
    SNAPSHOT-SCOPED (vintage + sticker + validity) so a later vintage never reuses an
    older one's evidence (B1); the existence re-check is UNDER the single-writer lock
    so concurrent captures are idempotent (B2)."""
    require_store_runtime_bundle(
        store, register.runtime_bundle, "FFSNaprave evidence attachment")
    inspection = register.match(snapshot_id, sticker_number, validity)
    if inspection is None:
        return {"attached": False, "evidenceRef": None, "disposition": "NO_MATCH",
                "problem": None}

    scope = {"scopeType": "FARM", "scopeRef": farm_ref}
    decision = AuthorityEvaluator(store).evaluate(
        acting_party_ref=captured_by, action_class="OBSERVE_ATTACH_EVIDENCE",
        action_stage="PROMOTION", scope=scope)

    v = inspection.get(VALIDITY_FIELD)
    identity_basis = {
        "identityVersion": "ofarm.ffs-naprave-evidence-identity.local.v1",
        "runtimeBundleDigest": store.runtime_bundle_digest,
        "snapshotRef": snapshot_id,
        "stickerNumber": sticker_number,
        "validity": v,
        "inspectionDigest": sha256_of(inspection),
        "capturedByPartyRef": captured_by,
        "farmRef": farm_ref,
    }
    identity_digest = sha256_of(identity_basis).split(":", 1)[1]
    eid = f"evidence:si.ffs-naprave.sha256.{identity_digest}"
    # capturedAt = the register vintage the extract was taken from (the snapshot's
    # effectiveFrom); recordedAt = now (mirrors the demo's REGISTRY_EXTRACT split).
    # the snapshot record exists: the register only matched because the import wrote
    # the snapshot AND its reference data in one transaction.
    snap_payload = store.get_record(snapshot_id)["payload"]
    captured_at = snap_payload.get("effectiveFrom") or now_iso()
    # rawAssetRef NAMES the snapshot, and rawAssetDigest verifies THAT asset — the
    # snapshot payload — so an auditor recomputes it from rawAssetRef alone (PR #14
    # hostile B2): sha256_of(get_record(rawAssetRef).payload) == rawAssetDigest. The
    # specific inspection is pinned by the snapshot-scoped eid plus the snapshot's
    # import-time conflict protection (same-sid-different-content is refused); the
    # sticker/validity ride the notes. No inconsistent row-digest fallback.
    raw_digest = sha256_of(snap_payload)
    evidence = {
        "schemaVersion": "ofarm.evidencerecord.v0.1",
        "evidenceRecordId": eid,
        "evidenceClass": "REGISTRY_EXTRACT",
        "capturedAt": captured_at,
        "recordedAt": now_iso(),
        "capturedByPartyRef": captured_by,
        "anchorScopes": [scope],
        "rawAssetRef": snapshot_id,
        "rawAssetDigest": raw_digest,
        "evidenceState": "CAPTURED",
        "provenanceRefs": [snapshot_id, FFSNAPRAVE_SOURCE_SURFACE],
        "notes": f"FFSNaprave inspection registry extract; sticker {sticker_number}, "
                 f"validity {v}, conformance-at-inspection "
                 f"{inspection.get('SkladnostObPregledu')}. Advisory: records an "
                 "inspection match in the dated register, not a current-compliance "
                 "claim (D7).",
    }
    with store.serialized_tx() as cur:
        # record the authorization decision (request/trace/result) regardless of
        # outcome — a governed, auditable authority trace, exactly as the gate does.
        store.insert_record(cur, decision.request_payload)
        store.insert_record(cur, decision.trace_payload)
        store.insert_record(cur, decision.result_payload)
        if not decision.allowed:
            problem = decision.problems[0] if decision.problems else runtime_problem(
                "AUTHORITY_DENIED", "Evidence capture not authorised",
                f"{captured_by} may not attach inspection evidence on {farm_ref}")
            return {"attached": False, "evidenceRef": None,
                    "disposition": "UNAUTHORIZED", "problem": problem}
        # idempotent re-check UNDER the advisory lock (B2)
        existing = store.get_record(eid)
        if existing is not None:
            existing_payload = existing["payload"]
            stable_existing = {
                key: value for key, value in existing_payload.items()
                if key != "recordedAt"
            }
            stable_expected = {
                key: value for key, value in evidence.items()
                if key != "recordedAt"
            }
            contract = store.registry.get("ofarm.evidencerecord.v0.1")
            if (existing["record_kind"] != "ofarm.evidencerecord.v0.1"
                    or existing["schema_hash"] != contract.schema_hash
                    or existing["payload_sha256"] != sha256_of(existing_payload)
                    or existing["runtime_bundle_digest"] != store.runtime_bundle_digest
                    or canonical_json(stable_existing) != canonical_json(stable_expected)):
                raise RuntimeBundleError(
                    f"inspection evidence identity {eid!r} was reused for unequal "
                    "content or a different RuntimeBundle")
            return {"attached": True, "evidenceRef": eid,
                    "disposition": "ALREADY_CAPTURED", "problem": None}
        store.insert_record(cur, evidence)
    return {"attached": True, "evidenceRef": eid, "disposition": "CAPTURED", "problem": None}
