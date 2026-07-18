"""M2 P1 — SI REGSR scheduled snapshot import (package content).

Engineering tests, NOT part of the named conformance suite. They pin the SI
REGSR adapter riding the generic G2 import + G3 verification mechanisms, with
the store-backed reference-data cache. A parsed artifact imports as a dated
REGSR ReferenceSnapshot and its parsed data is persisted as auditable candidate
data. That candidate cannot become verification authority until a new
RuntimeBundle selects it at startup. The tests also cover unknown decisions,
failed/conflicting/identical re-imports, D9 composite-key grading, the declared
weekly cadence, and reuse of the tooling parser. All product and decision values
are fictional and format-true.
"""
from __future__ import annotations

import uuid

from kernel.context import (ProductRegister, REGSR_DATA_FAMILY,
                            REGSR_SNAPSHOT_PREFIX, SIReferenceBindings,
                            current_reference_snapshot)
from kernel.profiles.si_ffs import regsr_adapter as regsr
from kernel.verification import IDENTITY, NONE, REVIEW


def uid():
    return uuid.uuid4().hex[:8]


def _fixture_artifact(*, register_day, decision="U99999-50/26/1"):
    """A small, fictional REGSR parse artifact (the parser's output shape)."""
    return {
        "snapshotKind": "SI_UVHVVR_FFS_REG_HTML_PARSE",
        "registerDay": register_day,
        "sourceUrl": regsr.REGSR_SOURCE_URL,
        "productCount": 1,
        "products": [{"regsrCode": "9001", "name": "FIKTIV ENA (fictional)",
                      "registrationValidUntil": "2028-08-15"}],
        "productDetails": [{"name": "FIKTIV ENA (fictional)",
                            "decisions": [{"decisionType": "Registracija",
                                           "decisionNumber": decision,
                                           "issued": "2026-01-01",
                                           "validUntil": "2028-08-15"}]}],
        "rowProblems": [],
        "inputs": [{"file": "fixture-list.html", "digest": f"sha256:{uid()}cafe"}],
    }


def _data_row(store, sid):
    return next((r for r in store.reference_data(REGSR_DATA_FAMILY)
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
# (1) import writes a dated REGSR ReferenceSnapshot + a store-backed data row
# ---------------------------------------------------------------------------

def test_p1_import_writes_snapshot_and_store_backed_data(store):
    decision = f"U9{uid()[:4]}-50/26/1"
    art = _fixture_artifact(register_day="2099-01-16", decision=decision)
    result = regsr.import_regsr_snapshot(store, art, source_artifact_ref="artifact:fixture.regsr")
    assert result["imported"] is True
    sid = result["snapshotRef"]
    assert sid == f"{REGSR_SNAPSHOT_PREFIX}.2099-01-16"
    p = store.get_record(sid)["payload"]
    assert p["effectiveFrom"] == "2099-01-16T00:00:00Z"
    assert p["issuingAuthorityRef"] == "party:si.uvhvvr"
    assert any(r.startswith("digest:") for r in p["sourceArtifactRefs"])
    assert regsr.REGSR_SOURCE_SURFACE in p["sourceArtifactRefs"]
    # the parsed DATA is persisted store-backed (not OFARM truth, an index cache)
    row = _data_row(store, sid)
    assert row is not None and row["payload"]["productDetails"][0]["decisions"][0][
        "decisionNumber"] == decision


# ---------------------------------------------------------------------------
# (2) imported candidate data stays outside the active ProductRegister
# ---------------------------------------------------------------------------

def test_p1_product_register_excludes_unselected_imported_data(store):
    decision = f"U9{uid()[:4]}-50/26/2"
    art = _fixture_artifact(register_day="2099-01-13", decision=decision)
    sid = regsr.import_regsr_snapshot(store, art)["snapshotRef"]
    assert _data_row(store, sid) is not None
    # The candidate carries no packaged fallback and is not selected by the
    # active RuntimeBundle. Loading a fresh register must not hot-activate it.
    assert not any(r.startswith("artifact:")
                   for r in store.get_record(sid)["payload"]["sourceArtifactRefs"])
    pr = ProductRegister()
    pr.load_from_store(store)
    assert pr.lookup_by_decision(sid, decision) is None


# ---------------------------------------------------------------------------
# (3) end-to-end: an imported candidate cannot change bundle-selected authority
# ---------------------------------------------------------------------------

def test_p1_imported_candidate_does_not_hot_activate_for_verification(store):
    selected_before = current_reference_snapshot(store, REGSR_SNAPSHOT_PREFIX)
    assert selected_before is not None
    decision = f"U9{uid()[:4]}-50/26/3"
    art = _fixture_artifact(register_day="2099-06-17", decision=decision)
    sid = regsr.import_regsr_snapshot(store, art)["snapshotRef"]
    pr = ProductRegister()
    pr.load_from_store(store)
    bindings = SIReferenceBindings.from_descriptor(store.active_descriptor)
    with store.serialized_tx() as cur:
        r = regsr.verify_product_authorisation(store, cur, pr, decision,
                                               as_of="2099-06-17T12:00:00Z",
                                               snapshot_prefix=bindings.regsr_snapshot_prefix,
                                               profile_ref=store.active_descriptor.code_binding_profile_ref)
    assert _data_row(store, sid) is not None
    assert sid not in store.selected_reference_snapshot_refs
    assert r["snapshotRef"] == selected_before["referenceSnapshotId"]
    assert r["verdict"] == REVIEW
    t = r["trace"]
    assert t["finalOutcome"] == "REVIEW_REQUIRED"
    assert t["verificationPurpose"] == "PRODUCT_AUTHORISATION_IDENTITY"
    assert t["candidateCount"] == 0
    assert t["snapshotRefs"] == [selected_before["referenceSnapshotId"]]
    assert sid not in t["snapshotRefs"]


def test_p1_unknown_decision_routes_to_review(store):
    pr = ProductRegister()
    pr.load_from_store(store)
    bindings = SIReferenceBindings.from_descriptor(store.active_descriptor)
    with store.serialized_tx() as cur:
        r = regsr.verify_product_authorisation(
            store, cur, pr, "U00000-00/00/0",
            snapshot_prefix=bindings.regsr_snapshot_prefix,
            profile_ref=store.active_descriptor.code_binding_profile_ref)
    assert r["verdict"] == REVIEW, "an unconfirmable decision routes to review, never confirms"
    assert r["problem"]["reasonCode"] == "PRODUCT_BINDING_UNRESOLVED"
    assert r["trace"]["finalOutcome"] == "REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# (4) failed import is a GOVERNED refusal: full RuntimeProblem + REFUSED gate
#     log, no snapshot, no data row (PR #12 review — never a hand-built bypass)
# ---------------------------------------------------------------------------

def test_p1_import_with_no_register_day_refuses_no_snapshot_no_data(store):
    before = _governed_import_refusals(store)
    art = _fixture_artifact(register_day="2099-01-12")
    art["registerDay"] = None
    result = regsr.import_regsr_snapshot(store, art)
    assert result["imported"] is False
    assert result["snapshotRef"] is None
    # the SI adapter's diagnostic envelope on top of the generic refusal is pinned
    assert result["disposition"] == "NO_REGISTER_DAY"
    assert result["registerDay"] is None
    # the problem is a FULL RuntimeProblem (governed refusal path), not a
    # hand-built mini dict missing schemaVersion/problemId/severity/title
    p = result["problem"]
    assert p["schemaVersion"] == "ofarm.runtimeproblem.v0.1"
    assert p["problemId"].startswith("problem:")
    assert p["severity"] == "ERROR"
    assert p["reasonCode"] == "SOURCE_FIDELITY_LOSS"
    assert p["title"] and p["detail"]
    # exactly one new GOVERNED_IMPORT/REFUSED gate-log entry was written, with no
    # fabricated snapshot id (there is none — the register day is what dates it)
    after = _governed_import_refusals(store)
    assert len(after) == len(before) + 1, "a refused import must leave a governed trace"
    assert after[-1]["reason_code"] == "SOURCE_FIDELITY_LOSS"
    assert after[-1]["related_refs"] is None
    # no snapshot and no data row were written for any would-be sid
    assert store.get_record(f"{REGSR_SNAPSHOT_PREFIX}.None") is None
    assert _data_row(store, f"{REGSR_SNAPSHOT_PREFIX}.None") is None


# ---------------------------------------------------------------------------
# (5) conflicting re-import refuses and does NOT overwrite the data
# ---------------------------------------------------------------------------

def test_p1_conflicting_reimport_refuses_no_overwrite(store):
    d1 = f"U9{uid()[:4]}-50/26/5a"
    d2 = f"U9{uid()[:4]}-50/26/5b"
    first = regsr.import_regsr_snapshot(store, _fixture_artifact(register_day="2099-01-14", decision=d1))
    sid = first["snapshotRef"]
    # same register day (same sid), DIFFERENT content -> conflict, no overwrite
    conflict = regsr.import_regsr_snapshot(store, _fixture_artifact(register_day="2099-01-14", decision=d2))
    assert conflict["imported"] is False
    assert conflict["problem"]["reasonCode"] == "DUPLICATE_IMPORT_AMBIGUOUS"
    row = _data_row(store, sid)
    decisions = {dd["decisionNumber"] for dd in row["payload"]["productDetails"][0]["decisions"]}
    assert decisions == {d1}, "the original data row must not be overwritten"


# ---------------------------------------------------------------------------
# (6) identical re-import is idempotent (no duplicate snapshot/data)
# ---------------------------------------------------------------------------

def test_p1_identical_reimport_is_idempotent(store):
    art = _fixture_artifact(register_day="2099-01-15", decision=f"U9{uid()[:4]}-50/26/6")
    a = regsr.import_regsr_snapshot(store, art)
    b = regsr.import_regsr_snapshot(store, art)
    assert a["imported"] is True and b["imported"] is True
    assert b["disposition"] == "ALREADY_IMPORTED"
    # exactly one data row for the snapshot (PK + no re-write on idempotent reimport)
    sid = a["snapshotRef"]
    rows = [r for r in store.reference_data(REGSR_DATA_FAMILY) if r["snapshot_ref"] == sid]
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# (7) a changed DETAIL page with an unchanged list-page digest REFUSES as a
#     conflict — the import basis digests the whole artifact, never a silent
#     ALREADY_IMPORTED replay that would leave stale identity data (hostile B1)
# ---------------------------------------------------------------------------

def test_p1_changed_detail_same_list_digest_refuses_as_conflict(store):
    list_digest = f"sha256:{uid()}listpage"
    d1 = f"U9{uid()[:4]}-50/26/8a"
    d2 = f"U9{uid()[:4]}-50/26/8b"
    a1 = _fixture_artifact(register_day="2099-02-01", decision=d1)
    a1["inputs"] = [{"file": "list.html", "digest": list_digest},
                    {"file": "detail-9001.html", "digest": f"sha256:{uid()}detA"}]
    a2 = _fixture_artifact(register_day="2099-02-01", decision=d2)   # changed detail content
    a2["inputs"] = [{"file": "list.html", "digest": list_digest},    # SAME list-page digest
                    {"file": "detail-9001.html", "digest": f"sha256:{uid()}detB"}]
    first = regsr.import_regsr_snapshot(store, a1)
    assert first["imported"] is True and first["disposition"] == "IMPORTED"
    second = regsr.import_regsr_snapshot(store, a2)
    # the changed detail must NOT replay as ALREADY_IMPORTED — it conflicts
    assert second["imported"] is False
    assert second["disposition"] == "CONFLICT"
    assert second["problem"]["reasonCode"] == "DUPLICATE_IMPORT_AMBIGUOUS"
    # the original identity data is intact (not overwritten by the changed detail)
    row = _data_row(store, first["snapshotRef"])
    numbers = {dd["decisionNumber"] for d in row["payload"]["productDetails"]
               for dd in d["decisions"]}
    assert numbers == {d1}


# ---------------------------------------------------------------------------
# (8) D9 composite identity grading is tested directly, without making a
#     synthetic imported candidate active runtime authority (hostile B2)
# ---------------------------------------------------------------------------

def _ambiguous_artifact(*, register_day, decision, issued_a="2024-01-01",
                        until_a="2028-08-15", issued_b="2025-01-01", until_b="2030-08-15"):
    """Two detail records sharing ONE decision number but DIFFERING validity
    windows — an ambiguous D9 composite key (fictional, format-true)."""
    art = _fixture_artifact(register_day=register_day, decision=decision)
    art["products"] = [
        {"regsrCode": "9201", "name": "FIKTIV DVA (fictional)", "registrationValidUntil": until_a},
        {"regsrCode": "9202", "name": "FIKTIV TRI (fictional)", "registrationValidUntil": until_b}]
    art["productCount"] = 2
    art["productDetails"] = [
        {"regsrCode": "9201", "name": "FIKTIV DVA (fictional)",
         "decisions": [{"decisionType": "Registracija", "decisionNumber": decision,
                        "issued": issued_a, "validUntil": until_a}]},
        {"regsrCode": "9202", "name": "FIKTIV TRI (fictional)",
         "decisions": [{"decisionType": "Registracija", "decisionNumber": decision,
                        "issued": issued_b, "validUntil": until_b}]}]
    return art


def test_p1_regsr_lookup_reports_ambiguous_decision_number(store):
    decision = f"U9{uid()[:4]}-50/26/9"
    sid = f"{REGSR_SNAPSHOT_PREFIX}.lookup-ambiguous-{uid()}"
    pr = ProductRegister()
    pr.register_artifact(
        sid,
        _ambiguous_artifact(register_day="2099-03-01", decision=decision),
    )
    result = regsr.regsr_lookup(pr)(sid, decision)
    assert result.grade == NONE
    assert result.candidate_count == 2
    assert result.status_observed == "MULTIPLE_CANDIDATES"
    assert result.discrepancies
    assert "ambiguous" in result.discrepancies[0]["note"]


def test_p1_regsr_lookup_composite_key_disambiguates(store):
    decision = f"U9{uid()[:4]}-50/26/10"
    sid = f"{REGSR_SNAPSHOT_PREFIX}.lookup-composite-{uid()}"
    pr = ProductRegister()
    pr.register_artifact(
        sid,
        _ambiguous_artifact(register_day="2099-03-02", decision=decision),
    )
    result = regsr.regsr_lookup(
        pr, issued="2024-01-01", valid_until="2028-08-15"
    )(sid, decision)
    assert result.grade == IDENTITY
    assert result.candidate_count == 1
    assert result.external_id == decision
    assert result.dates_observed == {
        "statusEffectiveFrom": "2024-01-01T00:00:00Z",
        "statusEffectiveUntil": "2028-08-15T00:00:00Z",
    }


def test_p1_regsr_lookup_true_duplicate_is_one_identity(store):
    # a decision number repeated with the SAME validity window is ONE identity,
    # not an ambiguity — it must still CONFIRM (no over-flagging of duplicates)
    decision = f"U9{uid()[:4]}-50/26/11"
    sid = f"{REGSR_SNAPSHOT_PREFIX}.lookup-duplicate-{uid()}"
    pr = ProductRegister()
    pr.register_artifact(
        sid,
        _ambiguous_artifact(
            register_day="2099-03-03",
            decision=decision,
            issued_a="2024-01-01",
            until_a="2028-08-15",
            issued_b="2024-01-01",
            until_b="2028-08-15",
        ),
    )
    result = regsr.regsr_lookup(pr)(sid, decision)
    assert result.grade == IDENTITY
    assert result.candidate_count == 1


# ---------------------------------------------------------------------------
# lookup grading (unit) + cadence + parser reuse (no fork)
# ---------------------------------------------------------------------------

def test_p1_regsr_lookup_grades_by_decision(store):
    decision = f"U9{uid()[:4]}-50/26/7"
    sid = f"{REGSR_SNAPSHOT_PREFIX}.lookup-unit-{uid()}"
    pr = ProductRegister()
    pr.register_artifact(sid, _fixture_artifact(register_day="2026-06-10", decision=decision))
    lookup = regsr.regsr_lookup(pr)
    hit = lookup(sid, decision)
    assert hit.grade == IDENTITY and hit.external_id == decision
    assert lookup(sid, "U00000-00/00/0").grade == NONE


def test_p1_weekly_cadence_is_declared(store):
    assert regsr.REGSR_CADENCE["period"] == "WEEKLY"
    assert regsr.REGSR_CADENCE["manualFloor"] == "MONTHLY"
    assert regsr.REGSR_CADENCE["liveIntegration"] is False


def test_p1_parse_regsr_html_reuses_tooling_parser(tmp_path):
    html = (
        "<html><body>"
        "<p>Seznam registriranih FFS na dan 18.6.2026</p>"
        "<table>"
        "<tr><td>Ime FFS</td><td>Veljavnost</td><td>Aktivna snov</td>"
        "<td>Proizvajalec</td><td>Zastopnik</td></tr>"
        "<tr><td><a href=\"FFS_Descr.asp?CODE=9001\">FIKTIV ENA (fictional)</a></td>"
        "<td>15.8.2028</td><td>fiktivna snov</td>"
        "<td>Test Maker d.o.o.</td><td>Test Rep d.o.o.</td></tr>"
        "</table></body></html>")
    list_path = tmp_path / "fixture-list.html"
    list_path.write_bytes(html.encode("cp1250"))
    artifact = regsr.parse_regsr_html(list_path)
    assert artifact["registerDay"] == "2026-06-18"
    assert artifact["productCount"] == 1
    assert artifact["products"][0]["regsrCode"] == "9001"
    assert artifact["products"][0]["registrationValidUntil"] == "2028-08-15"
    assert artifact["inputs"][0]["digest"].startswith("sha256:")
