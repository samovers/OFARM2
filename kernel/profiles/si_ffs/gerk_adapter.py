"""SI GERK adapter (M2 P2) — package content for the national GERK parcel layer
(Identifikacijski sistem za zemljišča Blok/GERK, MKGP open data; scheme SI:GERK).

Wires the open GERK layer to the GENERIC mechanisms: it parses the OPSI
`.dbf`/`.csv` attribute table (reusing tooling/gerk_roundtrip/gerk_roundtrip.py
as a library — never forked), imports the parse as a dated GERK
`ReferenceSnapshot` through the generic G2 `ImportRunner`, persists the parsed
parcels store-backed, and resolves a GERK-PID to its layer attributes (area +
use code) — the existence/area/use-code source that backs Field identities (G1)
and partial-extent bounds (G7). ALL GERK specifics live HERE; kernel/adapters.py
and the generic kernel stay scheme-agnostic.

Claim limits / posture: the open layer reflects GERK state at the last collective
subsidy application; it carries existence, geometry (as a shapefile), area, and
use code only — NO domače ime, BLOK-ID, or NUP (those come from the farmer/izpis,
ONBOARDING_RKG_IZPIS.md). The zero-dependency tooling reads `.dbf`/`.csv`
ATTRIBUTES, not geometry coordinates (geometry usability is implied by the layer
being a shapefile). A layer vintage may lag a fresher izpis; a missing PID is
surfaced honestly, never fabricated. No live integration, no current-compliance
claim (D7). Scheduled-import invalidation rides context-key drift (D19), as P1.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

from ... import config
from ...adapters import ImportRunner, ParseResult
from ...context import GERK_SNAPSHOT_PREFIX
from ...contracts import sha256_of

# GERK scheme constants (SI-specific). The parcel identity is the GERK-PID; the
# layer supplies area + use code (RABA_ID / OPIS_RABE). Values mirror the shipped
# example (OFARM_ReferenceSnapshot_example_si_gerk_layer_2025-06-30.json).
GERK_AUTHORITY_REF = "party:si.mkgp"
GERK_JURISDICTION_REF = "jurisdiction:SI"
GERK_SCHEME = "SI:GERK"
GERK_KEY_FIELD = "gerk-pid"
GERK_DOMAIN = ("SI national GERK parcel layer (Identifikacijski sistem za "
               "zemljisca Blok/GERK, open data)")
GERK_SOURCE_SURFACE = "surface:podatki.gov.si.blok-gerk-dataset"
GERK_PARSER_REF = "tooling/gerk_roundtrip/gerk_roundtrip.py"
# store-backed reference-data family for the parsed GERK layer (M2 P2). GERK is
# package content (GerkLayer below) and no generic kernel consumes it, so this
# constant lives WITH the adapter — unlike REGSR_DATA_FAMILY, which sits in
# context.py beside ProductRegister (a register the generic validators reach).
GERK_DATA_FAMILY = "si.mkgp.gerk-layer"

# Yearly open-data vintage (reflects GERK state at the last collective subsidy
# application). Declared, not scheduled here (an injectable trigger imports).
GERK_CADENCE = {
    "period": "ANNUAL",
    "posture": "open-data layer snapshot per sync; farmer izpis is fallback only",
    "liveIntegration": False,
}

# attribute-name candidates (mirror the tooling parser's own detection lists)
GERK_PID_FIELDS = ("GERK_PID", "GERKPID", "GERK_PID_", "PID", "ID_GERK")
GERK_AREA_FIELDS = ("AREA", "POVRSINA", "POV_HA", "GRPOV")
GERK_RABA_FIELDS = ("RABA_ID", "RABA", "VRSTA_RABE")
GERK_OPIS_FIELDS = ("OPIS_RABE", "OPIS")


def _parser():
    """Load tooling/gerk_roundtrip/gerk_roundtrip.py as a library (reuse, no fork)."""
    path = config.PACKAGE_ROOT / "tooling" / "gerk_roundtrip" / "gerk_roundtrip.py"
    spec = importlib.util.spec_from_file_location("ofarm_gerk_parser", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pick(header, candidates):
    return next((c for c in candidates if c in header), None)


def parse_gerk_layer(path, *, layer_date=None, version_label=None) -> dict:
    """Parse a saved GERK layer attribute table (`.dbf` or `.csv`) into a layer
    artifact, reusing the tooling iterators. No geometry coordinates are read (a
    zero-dependency attribute round-trip; geometry usability is implied by the
    shapefile). `layer_date` is the layer VINTAGE — it is NOT in the attributes,
    it dates the snapshot, and the caller supplies it (a parse without it is
    refused at import). Returns the artifact (per-parcel attributes + input
    digest) the importer wraps."""
    p = Path(path)
    parser = _parser()
    rows = parser.iter_dbf(p) if p.suffix.lower() == ".dbf" else parser.iter_csv(p)
    try:
        header = next(rows)
    except StopIteration:
        header = []   # empty file -> no header -> no PID column -> refused at import
    pid_field = _pick(header, GERK_PID_FIELDS)
    area_field = _pick(header, GERK_AREA_FIELDS)
    raba_field = _pick(header, GERK_RABA_FIELDS)
    opis_field = _pick(header, GERK_OPIS_FIELDS)
    features, row_problems = [], []
    if pid_field:
        pi = header.index(pid_field)
        ai = header.index(area_field) if area_field else None
        ri = header.index(raba_field) if raba_field else None
        oi = header.index(opis_field) if opis_field else None
        widest = max(i for i in (pi, ai, ri, oi) if i is not None)
        for n, row in enumerate(rows):
            if len(row) <= widest:
                # a ragged/short row cannot be read at the parsed offsets — skip
                # it with a SURFACED problem, never an IndexError crash that would
                # escape the governed import path (mirrors tooling parse_regsr.py)
                row_problems.append({"row": n, "problem": "short row: fewer columns than header"})
                continue
            pid = row[pi].split(".")[0].strip()
            if not pid:
                continue
            features.append({
                "gerkPid": pid,
                "rabaId": row[ri].strip() if ri is not None else None,
                "area": row[ai].strip() if ai is not None else None,
                "opisRabe": row[oi].strip() if oi is not None else None,
            })
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    return {
        "snapshotKind": "SI_MKGP_GERK_LAYER_PARSE",
        "layerDate": layer_date,
        "canonicalVersionLabel": version_label,
        "pidField": pid_field,
        "attributesAvailable": list(header),
        "featureCount": len(features),
        "features": features,
        "rowProblems": row_problems,
        "inputs": [{"file": p.name, "digest": f"sha256:{digest}"}],
    }


def import_gerk_snapshot(store, artifact, *, layer_date=None, version_label=None,
                         source_artifact_ref=None) -> dict:
    """Import a parsed GERK layer as a dated GERK `ReferenceSnapshot` via the
    generic G2 ImportRunner. The effective date is the layer vintage; the source
    digest + surface ride sourceArtifactRefs; the parsed parcels are persisted
    store-backed (an index cache, NOT OFARM truth) so `GerkLayer` can resolve a
    PID from the store. A parse with no datable vintage is REFUSED through the
    governed path (no snapshot, no data)."""
    layer_date = layer_date or artifact.get("layerDate")
    if not layer_date:
        # No datable layer vintage is a source-fidelity loss. Route through the
        # GENERIC governed refusal path (ImportRunner) — a real RuntimeProblem AND
        # a GOVERNED_IMPORT/REFUSED gate-log entry, no snapshot/data — never a
        # hand-built mini problem that bypasses the audit trail (PR #12 review).
        # There is no snapshot id to reference (the vintage dates it).
        result = ImportRunner(store).run_import(
            ParseResult(ok=False, error="GERK layer parse carries no vintage date; "
                        "cannot date a snapshot"),
            {"referenceSnapshotId": None}, data_family=GERK_DATA_FAMILY)
        return {**result, "disposition": "NO_LAYER_DATE", "layerDate": None}
    if not artifact.get("pidField"):
        # the attribute table carries no recognizable GERK-PID column, so NO
        # parcel is resolvable — a source-fidelity loss. Refuse through the same
        # governed path (no snapshot, no data), never import an unusable layer.
        result = ImportRunner(store).run_import(
            ParseResult(ok=False, error="GERK layer parse found no GERK-PID column; "
                        "no parcel is resolvable"),
            {"referenceSnapshotId": None}, data_family=GERK_DATA_FAMILY)
        return {**result, "disposition": "NO_PID_FIELD", "layerDate": layer_date}
    if not artifact.get("features"):
        # a PID column was found but the parse yielded NO parcels (empty file, or
        # every row malformed/skipped) — nothing is resolvable, a fidelity loss.
        # Refuse governably rather than import a useless empty layer.
        result = ImportRunner(store).run_import(
            ParseResult(ok=False, error="GERK layer parse yielded no parcels; "
                        "nothing to import"),
            {"referenceSnapshotId": None}, data_family=GERK_DATA_FAMILY)
        return {**result, "disposition": "NO_PARCELS", "layerDate": layer_date}
    sid = f"{GERK_SNAPSHOT_PREFIX}.{layer_date}"
    # Digest the WHOLE parsed artifact (every parcel + attribute), never just the
    # input file digest, so any content change re-imports as a CONFLICT and never
    # a silent ALREADY_IMPORTED replay that leaves stale parcels (PR #12 B1).
    digest = sha256_of(artifact)
    meta = {
        "referenceSnapshotId": sid,
        "referenceClass": "OTHER_REFERENCE",
        "domain": GERK_DOMAIN,
        "issuingAuthorityRef": GERK_AUTHORITY_REF,
        "jurisdictionRef": GERK_JURISDICTION_REF,
        "canonicalVersionLabel": (version_label or artifact.get("canonicalVersionLabel")
                                  or f"gerk-layer-{layer_date}"),
        "effectiveFrom": f"{layer_date}T00:00:00Z",
        "sourceArtifactRefs": [GERK_SOURCE_SURFACE],
        "notes": "GERK open-data layer parse; the layer reflects GERK state at the "
                 "last collective subsidy application and may lag a fresher izpis "
                 "(discrepancies route to review). Attributes only (no domace ime / "
                 "BLOK-ID / NUP). Parser: " + GERK_PARSER_REF,
    }
    result = ImportRunner(store).run_import(
        ParseResult(ok=True, sourceDigest=digest, artifactRef=source_artifact_ref,
                    recordCount=artifact.get("featureCount"), records=artifact),
        meta, data_family=GERK_DATA_FAMILY)
    return {**result, "layerDate": layer_date}


class GerkLayer:
    """Offline GERK parcel-layer lookup for the in-force GERK snapshots (package
    content). Resolves a GERK-PID to its parsed layer attributes — existence,
    area, use code (RABA_ID / OPIS_RABE) — within a dated layer vintage. Geometry
    coordinates are not parsed (the tooling reads attributes; geometry usability
    is implied by the shapefile). Backs Field identities (G1) and partial-extent
    bounds (G7); a missing PID is surfaced as None, never a fabricated parcel."""

    def __init__(self):
        self._by_snapshot: dict[str, dict] = {}

    def register_artifact(self, snapshot_id: str, artifact: dict) -> None:
        by_pid = {f["gerkPid"]: f for f in artifact.get("features", []) if f.get("gerkPid")}
        self._by_snapshot[snapshot_id] = by_pid

    def load_from_store(self, store) -> None:
        """Load store-backed GERK parcels persisted by a governed import (M2 P2),
        so a scheduled-import layer's parcels are resolvable from the store, not
        only from committed package files. The runtime never guesses."""
        for row in store.reference_data(GERK_DATA_FAMILY):
            sid = row["snapshot_ref"]
            if sid not in self._by_snapshot:
                self.register_artifact(sid, row["payload"])

    def lookup(self, snapshot_id: str, gerk_pid: str) -> dict | None:
        """The parcel record (gerkPid / rabaId / area / opisRabe) for a GERK-PID
        in a layer vintage, or None when the PID is absent from that layer — which
        is NOT 'not a parcel' (the layer vintage may lag the farmer's izpis)."""
        return self._by_snapshot.get(snapshot_id, {}).get(gerk_pid)
