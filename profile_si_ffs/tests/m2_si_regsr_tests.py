"""M2 P1 — SI REGSR scheduled snapshot import (package content).

Engineering tests, NOT part of the named conformance suite. They pin the SI
REGSR adapter riding the generic G2 import + G3 verification mechanisms, with the
store-backed reference-data cache (D-store decision, PR review): a parsed artifact
imports as a dated REGSR ReferenceSnapshot AND its parsed data is persisted to the
store; ProductRegister loads that data FROM THE STORE (not a committed file); a
decision number (Številka odločbe, D9) then drives an identity-grade verify
end-to-end; an unknown decision routes to review; failed/conflicting/identical
re-imports behave; the weekly cadence is declared; and the tooling parser is
REUSED (no fork). All product/decision values fictional and format-true.

Test isolation (PR-review FIX): these tests import into the REAL, shared REGSR
family (REGSR_SNAPSHOT_PREFIX) in the session-scoped store, so they MUST NOT
leave a snapshot that becomes the NOW-current REGSR vintage — otherwise an
unrelated test (e.g. conformance product verification) resolving the current
REGSR snapshot would silently pick up a fixture and break under a different
collection order. So every imported snapshot is dated FAR in the future (2099):
the in-force resolver (G3) excludes future-effective snapshots from every NOW
and every 2026-era as_of, so these fixtures are invisible to all other tests;
test 3 verifies its own snapshot via a far-future as_of where it is the
deterministic max of the REGSR family.
"""
from __future__ import annotations

import uuid

from kernel.context import (ProductRegister, REGSR_DATA_FAMILY,
                            REGSR_SNAPSHOT_PREFIX)
from kernel.profiles.si_ffs import regsr_adapter as regsr
from kernel.verification import CONFIRM, IDENTITY, NONE, REVIEW
from profile_si_ffs.tests.m2_si_binding_fixtures import (
    bundled_product_register,
    selected_runtime,
)


def uid():
    return uuid.uuid4().hex[:8]


def _fixture_artifact(*, register_day, decision="U99999-50/26/1"):
    """A small, fictional REGSR parse artifact (the parser's output shape)."""
    return {
        "snapshotKind": "SI_UVHVVR_FFS_REG_HTML_PARSE",
        "parserCodeDigest": regsr.parser_code_digest(),
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
    result = regsr.import_regsr_snapshot(store, art)
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
# (2) ProductRegister loads the imported data FROM THE STORE (not a disk file)
# ---------------------------------------------------------------------------

def test_p1_product_register_loads_imported_data_from_store(store):
    decision = f"U9{uid()[:4]}-50/26/2"
    art = _fixture_artifact(register_day="2099-01-13", decision=decision)
    sid = regsr.import_regsr_snapshot(store, art)["snapshotRef"]
    # the imported snapshot carries NO "artifact:" file ref, so the disk-fallback
    # path cannot load it — finding its data proves it was loaded from the store
    assert not any(r.startswith("artifact:")
                   for r in store.get_record(sid)["payload"]["sourceArtifactRefs"])
    pr = ProductRegister()
    pr.load_from_store(store)
    assert pr.lookup_by_decision(sid, decision) is not None, \
        "imported snapshot data must load from the store, not only from package files"


# ---------------------------------------------------------------------------
# (3) end-to-end: import -> store -> load -> G3 identity-grade verify (CONFIRM)
# ---------------------------------------------------------------------------

def test_p1_import_load_verify_confirms_end_to_end(store):
    decision = f"U9{uid()[:4]}-50/26/3"
    # far-future date (the max REGSR vintage among these tests) so it never
    # becomes a NOW-current fixture for other tests; verify as-of just after it
    # is effective, where it is the deterministic max of the REGSR family
    art = _fixture_artifact(register_day="2099-06-17", decision=decision)
    sid = regsr.import_regsr_snapshot(store, art)["snapshotRef"]
    with selected_runtime(store) as runtime:
        pr = bundled_product_register(runtime)
        with runtime.serialized_tx() as cur:
            r = regsr.verify_product_authorisation(
                runtime, cur, pr, decision,
                as_of="2099-06-17T12:00:00Z")
    assert r["snapshotRef"] == sid, "verify must resolve the imported snapshot"
    assert r["verdict"] == CONFIRM
    t = r["trace"]
    assert t["finalOutcome"] == "PASS"
    assert t["verificationPurpose"] == "PRODUCT_AUTHORISATION_IDENTITY"
    assert t["selectedExternalId"] == {"externalId": decision,
                                       "externalIdRole": "AUTHORISATION_NUMBER"}


def test_p1_unknown_decision_routes_to_review(store):
    with selected_runtime(store) as runtime:
        pr = bundled_product_register(runtime)
        with runtime.serialized_tx() as cur:
            r = regsr.verify_product_authorisation(
                runtime, cur, pr, "U00000-00/00/0")
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


def test_p1_identical_reimport_repairs_missing_data_then_restarts(store):
    decision = f"U9{uid()[:4]}-50/26/repair"
    art = _fixture_artifact(register_day="2099-01-17", decision=decision)
    first = regsr.import_regsr_snapshot(store, art)
    sid = first["snapshotRef"]
    with store.serialized_tx() as cur:
        cur.execute(
            "DELETE FROM reference_snapshot_data WHERE snapshot_ref = %s "
            "AND data_family = %s", (sid, REGSR_DATA_FAMILY))
    replay = regsr.import_regsr_snapshot(store, art)
    assert replay["imported"] is True
    assert replay["disposition"] == "ALREADY_IMPORTED"
    with selected_runtime(store) as runtime:
        register = bundled_product_register(runtime)
        assert register.lookup_by_decision(sid, decision) is not None


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
# (8) D9 composite identity (decision number + validity dates): a duplicate
#     decision number with DIFFERING validity is ambiguous -> REVIEW, never a
#     collapsed PASS; the full composite query disambiguates -> CONFIRM; a true
#     duplicate (same validity) stays one identity -> CONFIRM (hostile B2)
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


def test_p1_ambiguous_decision_number_routes_to_review_not_pass(store):
    decision = f"U9{uid()[:4]}-50/26/9"
    regsr.import_regsr_snapshot(store, _ambiguous_artifact(register_day="2099-03-01", decision=decision))
    with selected_runtime(store) as runtime:
        pr = bundled_product_register(runtime)
        with runtime.serialized_tx() as cur:
            r = regsr.verify_product_authorisation(
                runtime, cur, pr, decision,
                as_of="2099-03-01T12:00:00Z")
    assert r["verdict"] == REVIEW, "an ambiguous composite key must never CONFIRM/PASS"
    assert r["problem"]["reasonCode"] == "PRODUCT_BINDING_UNRESOLVED"
    t = r["trace"]
    assert t["finalOutcome"] == "REVIEW_REQUIRED"
    assert t["candidateCount"] == 2
    assert t["statusObserved"] == "MULTIPLE_CANDIDATES"
    assert t["selectedExternalId"]["externalIdRole"] == "NONE"
    assert t["discrepancies"] and "ambiguous" in t["discrepancies"][0]["note"]


def test_p1_composite_key_disambiguates_to_confirm(store):
    decision = f"U9{uid()[:4]}-50/26/10"
    regsr.import_regsr_snapshot(store, _ambiguous_artifact(register_day="2099-03-02", decision=decision))
    # the SAME ambiguous decision number, now with the full D9 composite key,
    # resolves to exactly one identity -> CONFIRM the right validity window
    with selected_runtime(store) as runtime:
        pr = bundled_product_register(runtime)
        with runtime.serialized_tx() as cur:
            r = regsr.verify_product_authorisation(
                runtime, cur, pr, decision,
                issued="2024-01-01", valid_until="2028-08-15",
                as_of="2099-03-02T12:00:00Z")
    assert r["verdict"] == CONFIRM
    t = r["trace"]
    assert t["finalOutcome"] == "PASS"
    assert t["candidateCount"] == 1
    assert t["selectedExternalId"] == {"externalId": decision, "externalIdRole": "AUTHORISATION_NUMBER"}
    assert t["datesObserved"]["statusEffectiveUntil"] == "2028-08-15T00:00:00Z"
    assert t["datesObserved"]["statusEffectiveFrom"] == "2024-01-01T00:00:00Z"


def test_p1_true_duplicate_same_validity_is_one_identity_confirm(store):
    # a decision number repeated with the SAME validity window is ONE identity,
    # not an ambiguity — it must still CONFIRM (no over-flagging of duplicates)
    decision = f"U9{uid()[:4]}-50/26/11"
    regsr.import_regsr_snapshot(store, _ambiguous_artifact(
        register_day="2099-03-03", decision=decision,
        issued_a="2024-01-01", until_a="2028-08-15",
        issued_b="2024-01-01", until_b="2028-08-15"))
    with selected_runtime(store) as runtime:
        pr = bundled_product_register(runtime)
        with runtime.serialized_tx() as cur:
            r = regsr.verify_product_authorisation(
                runtime, cur, pr, decision,
                as_of="2099-03-03T12:00:00Z")
    assert r["verdict"] == CONFIRM, "a true duplicate (same validity) is one identity"
    assert r["trace"]["candidateCount"] == 1


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
