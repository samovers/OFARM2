"""Capture/import proof for an isolated manual operation claim."""
from dataclasses import fields, replace
from hashlib import sha256
import json
from uuid import UUID

import psycopg
import pytest

from kernel._capture_normalization import CaptureSelection, MANUAL_MAPPING, ManualCaptureFixture


A = CaptureSelection(
    tenant_id=UUID(int=451),
    party_ref="party:grower",
    capture_id="capture:A",
    revision=1,
    mapping_ref=MANUAL_MAPPING,
    operation="ASSERT_OPERATION_CLAIM",
    request_id="request:A",
    ingested_at="2000-01-02T03:04:05Z",
    target_scopes=(("FARM", "farm:fictional"), ("FIELD", "field:orchard")),
    event_ref="event:submission-A",
    caller_key="key:Mixed.Case",
)


def _draft(selection):
    draft = {
        "operation": selection.operation,
        "partyRef": selection.party_ref,
        "scopes": [
            {"scopeType": scope_type, "scopeRef": scope_ref}
            for scope_type, scope_ref in selection.target_scopes
        ],
        "eventRef": selection.event_ref,
        "callerKey": selection.caller_key,
    }
    if selection.agent_ref is not None:
        draft["agentRef"] = selection.agent_ref
    return draft


def _source(selection, **updates):
    draft = {**_draft(selection), **updates}
    return (json.dumps(draft, indent=2) + "\n").encode()


def _key(selection):
    return selection.tenant_id, selection.capture_id, selection.revision


def _convert(fixture, selection=A, **updates):
    fixture.bind(selection, _source(selection, **updates))
    return fixture.normalizer(selection).convert()


def _passing(fixture, selection=A):
    record = _convert(fixture, selection)
    assert record.disposition == "NORMALIZED_DRAFT"
    evidence = fixture.reader(selection).read(record.reference)
    assert evidence is not None
    return record, evidence


def test_two_reads_recover_originals_and_result_without_writing(monkeypatch):
    fixture = ManualCaptureFixture()
    record = _convert(fixture)
    key = _key(A)
    emitted = fixture._requests[key]
    assert json.loads(emitted) == {
        "schemaVersion": "ofarm.commitingressrequest.v0.1",
        "requestId": "request:A",
        "ingestedAt": "2000-01-02T03:04:05Z",
        "ingressChannel": "MANUAL_UI",
        "commitClass": "OPERATION_CLAIM",
        "actingPartyRef": "party:grower",
        "targetScopes": [
            {"scopeType": "FARM", "scopeRef": "farm:fictional"},
            {"scopeType": "FIELD", "scopeRef": "field:orchard"},
        ],
        "semanticEventRef": "event:submission-A",
        "idempotencyKey": "key:Mixed.Case",
    }
    assert record.selection == A
    assert record.capture_sha256 == sha256(_source(A)).hexdigest()
    assert record.request_sha256 == sha256(emitted).hexdigest()
    assert record.disposition == "NORMALIZED_DRAFT"

    def forbid_write(*args, **kwargs):
        pytest.fail("readback invoked the converter or opened a farm database connection")

    monkeypatch.setattr(type(fixture.normalizer(A)), "convert", forbid_write)
    monkeypatch.setattr(psycopg, "connect", forbid_write)
    before = (fixture._captures.copy(), fixture._records.copy(), fixture._requests.copy())
    first_reader = fixture.reader(A)
    second_reader = fixture.reader(A)
    assert first_reader is not second_reader
    first = first_reader.read(record.reference)
    second = second_reader.read(record.reference)
    assert first is not None and first == second
    assert first.capture_bytes == _source(A)
    assert first.request_bytes == emitted
    assert first.reference == record.reference
    assert first.disposition == record.disposition
    # The consumer gets normalization evidence only. It has no save or gate result.
    assert {field.name for field in fields(first)} == {
        "reference", "capture_bytes", "request_bytes", "disposition",
    }
    assert second_reader.read("capture:unknown") is None
    assert (fixture._captures, fixture._records, fixture._requests) == before


def test_withhold_only_original_request_keep_draft_receipt_and_owner_record():
    fixture = ManualCaptureFixture()
    key = _key(A)
    # Fictional capture intake already holds a draft and its acknowledgement.
    # That receipt identifies the submission before normalization has run.
    drafts = {key: _source(A)}
    receipts = {A.request_id: {"tenant": A.tenant_id, "capture": A.capture_id,
                               "revision": A.revision, "request": A.request_id}}
    fixture.bind(A, drafts[key])
    record = fixture.normalizer(A).convert()
    reader = fixture.reader(A)
    assert reader.read(record.reference).request_bytes == fixture._requests[key]
    del fixture._requests[key]
    receipt = receipts[A.request_id]
    retained_key = (receipt["tenant"], receipt["capture"], receipt["revision"])
    assert fixture._records[retained_key] == record
    assert fixture._captures[retained_key] == drafts[retained_key]
    assert sha256(drafts[retained_key]).hexdigest() == record.capture_sha256
    assert receipt["request"] == record.selection.request_id
    assert reader.read(record.reference) is None
    assert key not in fixture._requests


def test_genuine_second_request_only_confirms_its_own_submission():
    fixture = ManualCaptureFixture()
    selection_b = replace(A, capture_id="capture:B", request_id="request:B",
                          event_ref="event:submission-B", caller_key="key:mixed.case")
    record_a, evidence_a = _passing(fixture)
    record_b, evidence_b = _passing(fixture, selection_b)
    assert selection_b.tenant_id == A.tenant_id and selection_b.party_ref == A.party_ref
    assert selection_b.target_scopes == A.target_scopes
    assert record_a.reference != record_b.reference
    assert evidence_b.request_bytes != evidence_a.request_bytes
    assert json.loads(evidence_b.request_bytes)["idempotencyKey"] == "key:mixed.case"
    assert json.loads(evidence_a.request_bytes)["idempotencyKey"] == "key:Mixed.Case"
    reader_a = fixture.reader(A)
    assert reader_a.read(record_b.reference) is None
    fixture._requests[_key(A)] = evidence_b.request_bytes
    assert reader_a.read(record_a.reference) is None
    assert fixture.reader(selection_b).read(record_b.reference) == evidence_b
    fixture._requests[_key(A)] = evidence_a.request_bytes
    assert reader_a.read(record_a.reference) == evidence_a


@pytest.mark.parametrize(("field", "value"), [
    ("tenant_id", UUID(int=999)), ("capture_id", "capture:other"), ("revision", 2),
    ("party_ref", "party:other"), ("agent_ref", "agent:unbound"),
    ("target_scopes", (("FARM", "farm:other"),)), ("event_ref", "event:other"),
    ("operation", "ASSERT_OBSERVATION"), ("mapping_ref", "mapping:other"),
    ("request_id", "request:other"), ("ingested_at", "2000-01-02T03:04:06Z"),
    ("caller_key", "key:mixed.case"),
], ids=lambda value: str(value) if isinstance(value, str) else None)
def test_changed_trusted_selection_refuses(field, value):
    fixture = ManualCaptureFixture()
    record, _ = _passing(fixture)
    assert fixture.reader(replace(A, **{field: value})).read(record.reference) is None


@pytest.mark.parametrize("change", [
    "missing-capture", "changed-capture", "reserialized-request", "missing-record",
    "capture-digest", "request-digest", "record-reference", "record-selection",
])
def test_missing_partial_changed_or_conflicting_record_refuses(change):
    fixture = ManualCaptureFixture()
    record, evidence = _passing(fixture)
    key = _key(A)
    if change == "missing-capture":
        del fixture._captures[key]
    elif change == "changed-capture":
        fixture._captures[key] = evidence.capture_bytes + b" "
    elif change == "reserialized-request":
        replacement = evidence.request_bytes + b"\n"
        assert json.loads(replacement) == json.loads(evidence.request_bytes)
        fixture._requests[key] = replacement
    elif change == "missing-record":
        del fixture._records[key]
    elif change == "capture-digest":
        fixture._records[key] = replace(record, capture_sha256=None)
    elif change == "request-digest":
        fixture._records[key] = replace(record, request_sha256="0" * 64)
    elif change == "record-reference":
        fixture._records[key] = replace(record, reference="evidence:other")
    else:
        fixture._records[key] = replace(record, selection=replace(A, request_id="request:B"))
    assert fixture.reader(A).read(record.reference) is None


def test_converter_records_its_own_refusal_while_both_originals_exist():
    fixture = ManualCaptureFixture()
    record = _convert(fixture, callerKey="key:mixed.case")
    assert record.disposition and record.disposition != "NORMALIZED_DRAFT"
    key = _key(A)
    assert fixture._records[key] == record
    assert record.capture_sha256 == sha256(fixture._captures[key]).hexdigest()
    assert record.request_sha256 == sha256(fixture._requests[key]).hexdigest()
    assert fixture.reader(A).read(record.reference) is None
    assert fixture._records[key].disposition == record.disposition


@pytest.mark.parametrize("outcome", [None, "UNRECOGNIZED", "refusal"])
def test_otherwise_valid_originals_require_owner_recorded_success(outcome):
    fixture = ManualCaptureFixture()
    record, _ = _passing(fixture)
    if outcome == "refusal":
        # Use the normalizer's genuine refusal vocabulary from a separate submission.
        refused = replace(A, capture_id="capture:refused", request_id="request:refused",
                          event_ref="event:refused")
        outcome = _convert(fixture, refused, callerKey="key:other").disposition
        assert outcome and outcome != "NORMALIZED_DRAFT"
    fixture._records[_key(A)] = replace(record, disposition=outcome)
    assert fixture.reader(A).read(record.reference) is None
    assert fixture._records[_key(A)].disposition == outcome


@pytest.mark.parametrize("updates", [
    {"partyRef": "party:other"},
    {"agentRef": "agent:self-claimed"},
    {"scopes": [{"scopeType": "FARM", "scopeRef": "farm:other"}]},
    {"eventRef": "event:other"},
    {"operation": "ASSERT_OBSERVATION"},
    {"reference": "evidence:mine"},
    {"requestSha256": "0" * 64},
    {"disposition": "NORMALIZED_DRAFT"},
], ids=["actor", "unbound-agent", "scope", "event", "operation", "reference", "digest", "result"])
def test_untrusted_capture_cannot_change_selected_mapping_or_supply_proof(updates):
    fixture = ManualCaptureFixture()
    record = _convert(fixture, **updates)
    assert record.disposition != "NORMALIZED_DRAFT"
    assert fixture.reader(A).read(record.reference) is None


def test_independently_selected_agent_is_preserved_and_required():
    fixture = ManualCaptureFixture()
    selected = replace(A, agent_ref="agent:bound")
    record, evidence = _passing(fixture, selected)
    assert json.loads(evidence.request_bytes)["actingAgentRef"] == "agent:bound"
    assert json.loads(evidence.request_bytes)["actingPartyRef"] == A.party_ref
    assert fixture.reader(A).read(record.reference) is None


@pytest.mark.parametrize(("field", "value"), [
    ("caller_key", " key:Mixed.Case"), ("caller_key", "key:Mixed. Case"),
    ("caller_key", "key:Mixed.Case "), ("caller_key", "key:Mixed.Case\n"),
    ("request_id", "request:A "), ("ingested_at", "2000-02-31T05:04:03Z"),
])
def test_schema_checks_wire_values_without_repairing_them(field, value):
    fixture = ManualCaptureFixture()
    selected = replace(A, **{field: value})
    record = _convert(fixture, selected)
    assert record.disposition != "NORMALIZED_DRAFT"
    assert fixture.reader(selected).read(record.reference) is None


@pytest.mark.parametrize(("original", "updates"), [
    ("request", {"commitClass": "NOTE"}),
    ("request", {"actingPartyRef": "party:other"}),
    ("request", {"actingAgentRef": "agent:self-claimed"}),
    ("request", {"requestId": "request:B"}),
    ("request", {"idempotencyKey": "key:mixed.case"}),
    ("source", {"eventRef": "event:B"}),
], ids=["class", "party", "agent", "request-id", "key", "capture-event"])
def test_readback_checks_mapping_even_when_changed_bytes_match_recorded_digest(original, updates):
    fixture = ManualCaptureFixture()
    record, evidence = _passing(fixture)
    key = _key(A)
    if original == "request":
        replacement = json.dumps({**json.loads(evidence.request_bytes), **updates}).encode()
        fixture._requests[key] = replacement
        fixture._records[key] = replace(record, request_sha256=sha256(replacement).hexdigest())
    else:
        replacement = json.dumps({**json.loads(evidence.capture_bytes), **updates}).encode()
        fixture._captures[key] = replacement
        fixture._records[key] = replace(record, capture_sha256=sha256(replacement).hexdigest())
    assert fixture.reader(A).read(record.reference) is None


def test_conflicting_bind_cannot_replace_the_initial_conversion():
    fixture = ManualCaptureFixture()
    record, evidence = _passing(fixture)
    with pytest.raises(ValueError):
        fixture.bind(A, _source(A, callerKey="key:other"))
    assert fixture.reader(A).read(record.reference) == evidence


def test_caller_supplied_proof_cannot_replace_another_captures_record():
    fixture = ManualCaptureFixture()
    record_a, evidence_a = _passing(fixture)
    selection_b = replace(A, capture_id="capture:B", request_id="request:B",
                          event_ref="event:submission-B", caller_key="key:B")
    record_b = _convert(fixture, selection_b, reference=record_a.reference,
                        requestSha256=record_a.request_sha256, disposition=record_a.disposition)
    assert record_b.reference != record_a.reference
    assert fixture.reader(selection_b).read(record_b.reference) is None
    assert fixture.reader(A).read(record_a.reference) == evidence_a
    assert fixture._records[_key(A)] == record_a


@pytest.mark.parametrize("raw", [b"{", b'{"operation":"first","operation":"second"}'])
def test_incomplete_or_ambiguous_capture_records_refusal_without_a_request(raw):
    fixture = ManualCaptureFixture()
    fixture.bind(A, raw)
    record = fixture.normalizer(A).convert()
    assert record.disposition and record.disposition != "NORMALIZED_DRAFT"
    assert record.capture_sha256 == sha256(raw).hexdigest()
    assert record.request_sha256 is None
    assert _key(A) not in fixture._requests
    assert fixture.reader(A).read(record.reference) is None
