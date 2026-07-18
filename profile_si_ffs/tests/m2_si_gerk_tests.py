"""M2 P2 — SI GERK open-data parcel-layer import (package content).

Engineering tests, NOT part of the named conformance suite. They pin the SI GERK
adapter riding the generic G2 import mechanism + the store-backed reference-data
cache: an OPSI .dbf/.csv attribute parse imports as a dated GERK ReferenceSnapshot
AND its parsed parcels persist to the store as an auditable candidate. Runtime
lookup loads only exact source bytes retained by the startup RuntimeBundle;
importing a new candidate never hot-activates it. GerkLayer's pure lookup resolves
an explicitly registered artifact's GERK-PID to its area / use code, while a
missing PID is surfaced honestly (None), never fabricated; failed / conflicting
and identical re-imports
behave; the tooling iterators are REUSED (no fork). Fixtures use unselected
far-future (2099) layer vintages. All PID / area / use values fictional and
format-true.
"""
from __future__ import annotations

import uuid

import pytest

from kernel.context import GERK_SNAPSHOT_PREFIX
from kernel.profiles.si_ffs import gerk_adapter as gerk
from kernel.profiles.si_ffs.gerk_adapter import GERK_DATA_FAMILY, GerkLayer
from kernel.store import RuntimeBundleBindingError


def uid():
    return uuid.uuid4().hex[:8]


def pid7():
    """A fictional, format-true 7-digit GERK-PID."""
    return str(uuid.uuid4().int)[:7]


def _fixture_layer(*, layer_date, features=None):
    """A small, fictional GERK layer parse artifact (the parser's output shape)."""
    feats = features if features is not None else [
        {"gerkPid": "1000001", "rabaId": "1300", "area": "1.2345",
         "opisRabe": "trajni travnik (fictional)"}]
    return {
        "snapshotKind": "SI_MKGP_GERK_LAYER_PARSE",
        "layerDate": layer_date,
        "canonicalVersionLabel": f"gerk-fixture-{layer_date}",
        "pidField": "GERK_PID",
        "attributesAvailable": ["GERK_PID", "RABA_ID", "AREA", "OPIS_RABE"],
        "featureCount": len(feats),
        "features": feats,
        "inputs": [{"file": "fixture-gerk.csv", "digest": f"sha256:{uid()}cafe"}],
    }


def _data_row(store, sid):
    return next((r for r in store.reference_data(GERK_DATA_FAMILY)
                 if r["snapshot_ref"] == sid), None)


def _governed_import_refusals(store):
    """Every GOVERNED_IMPORT/REFUSED gate-log row, oldest first — to prove a
    refused import leaves a governed audit trace (not a silent hand-built one)."""
    with store.conn.cursor() as cur:
        cur.execute(
            "SELECT outcome, reason_code, related_refs FROM kernel_gate_log "
            "WHERE gate = 'GOVERNED_IMPORT' AND outcome = 'REFUSED' ORDER BY entry_id")
        return cur.fetchall()


# ---------------------------------------------------------------------------
# (1) import writes a dated GERK ReferenceSnapshot + a store-backed data row
# ---------------------------------------------------------------------------

def test_p2_import_writes_snapshot_and_store_backed_data(store):
    pid = pid7()
    art = _fixture_layer(layer_date="2099-06-30",
                         features=[{"gerkPid": pid, "rabaId": "1300", "area": "0.5012",
                                    "opisRabe": "trajni travnik (fictional)"}])
    result = gerk.import_gerk_snapshot(store, art, source_artifact_ref="archive:fixture.gerk.zip")
    assert result["imported"] is True
    sid = result["snapshotRef"]
    assert sid == f"{GERK_SNAPSHOT_PREFIX}.2099-06-30"
    p = store.get_record(sid)["payload"]
    assert p["effectiveFrom"] == "2099-06-30T00:00:00Z"
    assert p["issuingAuthorityRef"] == "party:si.mkgp"
    assert p["referenceClass"] == "OTHER_REFERENCE"
    assert gerk.GERK_SOURCE_SURFACE in p["sourceArtifactRefs"]
    assert any(r.startswith("digest:") for r in p["sourceArtifactRefs"])
    # the parsed parcels are persisted store-backed (an index cache, not OFARM truth)
    row = _data_row(store, sid)
    assert row is not None and row["payload"]["features"][0]["gerkPid"] == pid


# ---------------------------------------------------------------------------
# (2) an imported candidate persists but does not enter runtime lookup under the
#     current bundle; the pure lookup still resolves explicitly registered data
# ---------------------------------------------------------------------------

def test_p2_unselected_candidate_is_not_loaded_but_lookup_unit_resolves(store):
    pid = pid7()
    art = _fixture_layer(layer_date="2099-06-29",
                         features=[{"gerkPid": pid, "rabaId": "1300", "area": "0.7531",
                                    "opisRabe": "trajni travnik (fictional)"}])
    sid = gerk.import_gerk_snapshot(store, art)["snapshotRef"]

    # The governed import persists an auditable candidate, but runtime authority
    # remains fixed by the startup RuntimeBundle. The selected metadata-only
    # GERK snapshot has no retained source bytes, so operational loading refuses.
    assert _data_row(store, sid) is not None
    layer = GerkLayer()
    with pytest.raises(RuntimeBundleBindingError, match="no exact operational source"):
        layer.load_from_store(store)

    # Adapter lookup itself is a pure unit law. Explicit registration represents
    # the data after a future RuntimeBundle has selected this snapshot.
    layer.register_artifact(sid, art)
    parcel = layer.lookup(sid, pid)
    assert parcel is not None
    assert parcel["area"] == "0.7531"
    assert parcel["rabaId"] == "1300"
    assert parcel["opisRabe"] == "trajni travnik (fictional)"


# ---------------------------------------------------------------------------
# (3) a missing PID (or missing snapshot) resolves to None — governable, never
#     a fabricated parcel
# ---------------------------------------------------------------------------

def test_p2_missing_pid_is_governable_none(store):
    art = _fixture_layer(layer_date="2099-06-24",
                         features=[{"gerkPid": pid7(), "rabaId": "1100", "area": "0.3000",
                                    "opisRabe": "njiva (fictional)"}])
    sid = gerk.import_gerk_snapshot(store, art)["snapshotRef"]
    layer = GerkLayer()
    layer.register_artifact(sid, art)
    assert layer.lookup(sid, "0000000") is None, "absent PID is None, never fabricated"
    assert layer.lookup(f"{GERK_SNAPSHOT_PREFIX}.2099-01-01", "0000000") is None, \
        "absent snapshot resolves to None, not a crash"


# ---------------------------------------------------------------------------
# (4) failed import is a GOVERNED refusal: full RuntimeProblem + REFUSED gate
#     log, no snapshot, no data row (PR #12 review lesson, applied proactively)
# ---------------------------------------------------------------------------

def test_p2_import_with_no_layer_date_refuses_no_snapshot_no_data(store):
    before = _governed_import_refusals(store)
    art = _fixture_layer(layer_date="2099-06-28")
    art["layerDate"] = None
    result = gerk.import_gerk_snapshot(store, art)
    assert result["imported"] is False
    assert result["snapshotRef"] is None
    assert result["disposition"] == "NO_LAYER_DATE"
    assert result["layerDate"] is None
    # a FULL RuntimeProblem (governed refusal path), not a hand-built mini dict
    p = result["problem"]
    assert p["schemaVersion"] == "ofarm.runtimeproblem.v0.1"
    assert p["problemId"].startswith("problem:")
    assert p["severity"] == "ERROR"
    assert p["reasonCode"] == "SOURCE_FIDELITY_LOSS"
    assert p["title"] and p["detail"]
    # exactly one new GOVERNED_IMPORT/REFUSED gate-log entry, no fabricated sid
    after = _governed_import_refusals(store)
    assert len(after) == len(before) + 1, "a refused import must leave a governed trace"
    assert after[-1]["reason_code"] == "SOURCE_FIDELITY_LOSS"
    assert after[-1]["related_refs"] is None
    assert store.get_record(f"{GERK_SNAPSHOT_PREFIX}.None") is None
    assert _data_row(store, f"{GERK_SNAPSHOT_PREFIX}.None") is None


# ---------------------------------------------------------------------------
# (4b) a layer with no recognizable GERK-PID column refuses governably (no
#      parcel resolvable) — never an unusable silent import
# ---------------------------------------------------------------------------

def test_p2_layer_without_pid_column_refuses_governed(store):
    before = _governed_import_refusals(store)
    art = _fixture_layer(layer_date="2099-06-23")
    art["pidField"] = None
    art["features"] = []
    result = gerk.import_gerk_snapshot(store, art)
    assert result["imported"] is False
    assert result["disposition"] == "NO_PID_FIELD"
    assert result["problem"]["reasonCode"] == "SOURCE_FIDELITY_LOSS"
    assert result["problem"]["schemaVersion"] == "ofarm.runtimeproblem.v0.1"
    after = _governed_import_refusals(store)
    assert len(after) == len(before) + 1
    assert store.get_record(f"{GERK_SNAPSHOT_PREFIX}.2099-06-23") is None
    assert _data_row(store, f"{GERK_SNAPSHOT_PREFIX}.2099-06-23") is None


# ---------------------------------------------------------------------------
# (5) a content change under the SAME vintage REFUSES as a conflict — the import
#     basis digests the whole layer artifact, never a silent replay (PR #12 B1)
# ---------------------------------------------------------------------------

def test_p2_changed_content_same_vintage_refuses_as_conflict(store):
    pid = pid7()
    shared_inputs = [{"file": "fixture-gerk.csv", "digest": f"sha256:{uid()}layer"}]
    a1 = _fixture_layer(layer_date="2099-06-27",
                        features=[{"gerkPid": pid, "rabaId": "1300", "area": "0.5000",
                                   "opisRabe": "trajni travnik"}])
    a1["inputs"] = shared_inputs
    a2 = _fixture_layer(layer_date="2099-06-27",   # same vintage / same sid
                        features=[{"gerkPid": pid, "rabaId": "1300", "area": "0.9999",
                                   "opisRabe": "trajni travnik"}])     # CHANGED area
    a2["inputs"] = list(shared_inputs)             # SAME input digest
    first = gerk.import_gerk_snapshot(store, a1)
    assert first["imported"] is True and first["disposition"] == "IMPORTED"
    second = gerk.import_gerk_snapshot(store, a2)
    assert second["imported"] is False
    assert second["disposition"] == "CONFLICT"
    assert second["problem"]["reasonCode"] == "DUPLICATE_IMPORT_AMBIGUOUS"
    # the original parcel data is intact, not overwritten by the changed area
    row = _data_row(store, first["snapshotRef"])
    assert row["payload"]["features"][0]["area"] == "0.5000"


# ---------------------------------------------------------------------------
# (6) identical re-import is idempotent (no duplicate snapshot / data)
# ---------------------------------------------------------------------------

def test_p2_identical_reimport_is_idempotent(store):
    art = _fixture_layer(layer_date="2099-06-26",
                         features=[{"gerkPid": pid7(), "rabaId": "1100", "area": "1.0000",
                                    "opisRabe": "njiva (fictional)"}])
    a = gerk.import_gerk_snapshot(store, art)
    b = gerk.import_gerk_snapshot(store, art)
    assert a["imported"] is True and b["imported"] is True
    assert b["disposition"] == "ALREADY_IMPORTED"
    sid = a["snapshotRef"]
    rows = [r for r in store.reference_data(GERK_DATA_FAMILY) if r["snapshot_ref"] == sid]
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# parser reuse (no fork) + cadence
# ---------------------------------------------------------------------------

def test_p2_parse_gerk_layer_reuses_tooling_iterators(tmp_path):
    csv_path = tmp_path / "fixture-gerk.csv"
    csv_path.write_text(
        "GERK_PID,RABA_ID,AREA,OPIS_RABE\n"
        "1000001,1300,1.2345,trajni travnik\n"
        "1000002,1100,0.6789,njiva\n",
        encoding="utf-8")
    art = gerk.parse_gerk_layer(csv_path, layer_date="2099-06-25")
    assert art["pidField"] == "GERK_PID"
    assert art["featureCount"] == 2
    assert art["features"][0]["gerkPid"] == "1000001"
    assert art["features"][0]["area"] == "1.2345"
    assert art["features"][1]["rabaId"] == "1100"
    assert art["features"][1]["opisRabe"] == "njiva"
    assert art["inputs"][0]["digest"].startswith("sha256:")
    assert art["layerDate"] == "2099-06-25"


def test_p2_annual_cadence_is_declared(store):
    assert gerk.GERK_CADENCE["period"] == "ANNUAL"
    assert gerk.GERK_CADENCE["liveIntegration"] is False


# ---------------------------------------------------------------------------
# parse robustness (review): a ragged/short row is SKIPPED with a surfaced
# problem, never an IndexError crash that escapes the governed import path; an
# empty / header-only layer refuses governably, never crashes or imports empty
# ---------------------------------------------------------------------------

def test_p2_parse_skips_ragged_rows_without_crashing(tmp_path):
    csv_path = tmp_path / "ragged.csv"
    csv_path.write_text(
        "GERK_PID,RABA_ID,AREA,OPIS_RABE\n"
        "1000001,1300,1.2345,trajni travnik\n"
        "1000002,1100\n"                      # short row — fewer columns than header
        "1000003,1100,0.4242,njiva\n",
        encoding="utf-8")
    art = gerk.parse_gerk_layer(csv_path, layer_date="2099-06-22")
    assert art["featureCount"] == 2, "the two well-formed rows parse"
    assert {f["gerkPid"] for f in art["features"]} == {"1000001", "1000003"}
    assert len(art["rowProblems"]) == 1 and art["rowProblems"][0]["row"] == 1


def test_p2_parse_empty_file_refuses_governed(store, tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_bytes(b"")
    art = gerk.parse_gerk_layer(csv_path, layer_date="2099-06-21")   # no crash
    assert art["pidField"] is None and art["features"] == []
    result = gerk.import_gerk_snapshot(store, art)
    assert result["imported"] is False and result["disposition"] == "NO_PID_FIELD"
    assert result["problem"]["reasonCode"] == "SOURCE_FIDELITY_LOSS"


def test_p2_header_only_layer_refuses_no_parcels(store, tmp_path):
    csv_path = tmp_path / "header-only.csv"
    csv_path.write_text("GERK_PID,RABA_ID,AREA,OPIS_RABE\n", encoding="utf-8")
    before = _governed_import_refusals(store)
    art = gerk.parse_gerk_layer(csv_path, layer_date="2099-06-20")
    assert art["pidField"] == "GERK_PID" and art["features"] == []
    result = gerk.import_gerk_snapshot(store, art)
    assert result["imported"] is False and result["disposition"] == "NO_PARCELS"
    assert result["problem"]["reasonCode"] == "SOURCE_FIDELITY_LOSS"
    after = _governed_import_refusals(store)
    assert len(after) == len(before) + 1
    assert store.get_record(f"{GERK_SNAPSHOT_PREFIX}.2099-06-20") is None


# ---------------------------------------------------------------------------
# (PR #13 B1) a duplicate GERK-PID with CONFLICTING attributes refuses import —
# never silent last-wins; an EXACT duplicate is benign and indexes as one parcel
# ---------------------------------------------------------------------------

def test_p2_conflicting_duplicate_pid_refuses_import(store):
    before = _governed_import_refusals(store)
    pid = pid7()
    art = _fixture_layer(layer_date="2099-05-01", features=[
        {"gerkPid": pid, "rabaId": "1300", "area": "0.5000", "opisRabe": "trajni travnik"},
        {"gerkPid": pid, "rabaId": "1100", "area": "0.9999", "opisRabe": "njiva"}])  # SAME pid, DIFFERENT
    result = gerk.import_gerk_snapshot(store, art)
    assert result["imported"] is False
    assert result["disposition"] == "CONFLICTING_DUPLICATE_PID"
    assert result["problem"]["reasonCode"] == "SOURCE_FIDELITY_LOSS"
    after = _governed_import_refusals(store)
    assert len(after) == len(before) + 1
    assert store.get_record(f"{GERK_SNAPSHOT_PREFIX}.2099-05-01") is None
    assert _data_row(store, f"{GERK_SNAPSHOT_PREFIX}.2099-05-01") is None


def test_p2_exact_duplicate_pid_imports_and_indexes_as_one_parcel(store):
    pid = pid7()
    feat = {"gerkPid": pid, "rabaId": "1300", "area": "0.5000", "opisRabe": "trajni travnik"}
    art = _fixture_layer(layer_date="2099-05-02", features=[dict(feat), dict(feat)])  # EXACT dup
    result = gerk.import_gerk_snapshot(store, art)
    assert result["imported"] is True, "an exact duplicate is benign, not a conflict"

    # The candidate remains inactive under the current RuntimeBundle.
    layer = GerkLayer()
    with pytest.raises(RuntimeBundleBindingError, match="no exact operational source"):
        layer.load_from_store(store)

    # Exact duplicate rows collapse to the same PID in the adapter's pure index.
    layer.register_artifact(result["snapshotRef"], art)
    parcel = layer.lookup(result["snapshotRef"], pid)
    assert parcel is not None and parcel["area"] == "0.5000"


def test_p2_register_artifact_refuses_conflicting_dup_loudly():
    # defense-in-depth: building a lookup directly from conflicting data raises,
    # never a silent last-wins (import would already have refused it)
    pid = pid7()
    art = _fixture_layer(layer_date="2099-05-03", features=[
        {"gerkPid": pid, "rabaId": "1300", "area": "0.5", "opisRabe": "a"},
        {"gerkPid": pid, "rabaId": "1300", "area": "0.6", "opisRabe": "a"}])
    layer = GerkLayer()
    with pytest.raises(ValueError):
        layer.register_artifact(f"{GERK_SNAPSHOT_PREFIX}.2099-05-03", art)


# ---------------------------------------------------------------------------
# (PR #13 B2) a partial parse (skipped ragged rows) REFUSES at import — a dropped
# real PID must not later read as 'absent'; refuse the lossy layer, fix the source
# ---------------------------------------------------------------------------

def test_p2_partial_parse_refuses_at_import(store, tmp_path):
    before = _governed_import_refusals(store)
    csv_path = tmp_path / "ragged-import.csv"
    csv_path.write_text(
        "GERK_PID,RABA_ID,AREA,OPIS_RABE\n"
        "1000001,1300,1.2345,trajni travnik\n"
        "1000002,1100\n",                       # short row -> rowProblems non-empty
        encoding="utf-8")
    art = gerk.parse_gerk_layer(csv_path, layer_date="2099-05-04")
    assert art["rowProblems"], "the parse records the skipped ragged row"
    result = gerk.import_gerk_snapshot(store, art)
    assert result["imported"] is False
    assert result["disposition"] == "PARTIAL_PARSE"
    assert result["problem"]["reasonCode"] == "SOURCE_FIDELITY_LOSS"
    after = _governed_import_refusals(store)
    assert len(after) == len(before) + 1
    assert store.get_record(f"{GERK_SNAPSHOT_PREFIX}.2099-05-04") is None
    assert _data_row(store, f"{GERK_SNAPSHOT_PREFIX}.2099-05-04") is None
