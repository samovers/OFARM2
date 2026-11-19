"""Original-source comparisons for a pending claim, with fictional owner inputs."""
from __future__ import annotations

import json
from hashlib import sha256

import pytest

from kernel._pending_claim_ingress_sources import verify_original_ingress_sources


def _sources(family="MaterialEvent"):
    scope = {"scopeType": "FIELD", "scopeRef": "field:test"}
    request = {
        "schemaVersion": "ofarm.commitingressrequest.v0.1",
        "requestId": "request:test",
        "ingestedAt": "2000-01-01T12:10:00Z",
        "ingressChannel": "MANUAL_UI",
        "commitClass": "OPERATION_CLAIM",
        "semanticEventRef": "event:test",
        "actingPartyRef": "party:test",
        "targetScopes": [scope],
        "idempotencyKey": "key:test",
    }
    envelope = {
        "schemaVersion": "ofarm.semanticeventenvelope.v0.1",
        "semanticEventId": "event:test",
        "primaryEventFamily": family,
        "dominantSemanticConsequence": "Fictional source for an operation claim.",
        "anchorScopes": [scope, {"scopeType": "FARM", "scopeRef": "farm:test"}],
        "subjectRefs": ["operation:test"],
        "timeSemantics": {
            "eventTime": "2000-01-01T12:00:00Z",
            "recordTime": "2000-01-01T12:09:00Z",
        },
    }
    request_bytes = json.dumps(request, indent=2).encode()
    envelope_bytes = json.dumps(envelope, indent=2).encode()
    return dict(
        request_bytes=request_bytes,
        envelope_bytes=envelope_bytes,
        request_bytes_sha256=sha256(request_bytes).hexdigest(),
        envelope_bytes_sha256=sha256(envelope_bytes).hexdigest(),
        batch_request_id="request:test",
        admitted_idempotency_key="key:test",
        classified_family=family,
    )


@pytest.mark.parametrize("family", ["MaterialEvent", "InterventionEvent"])
def test_reads_exact_originals_with_independent_family(family):
    assert verify_original_ingress_sources(**_sources(family)) == "event:test"


@pytest.mark.parametrize("source", ["request_bytes", "envelope_bytes"])
def test_whitespace_changes_raw_digest_with_same_json_value(source):
    inputs = _sources()
    inputs[source] += b"\n"
    with pytest.raises(ValueError, match="byte digest"):
        verify_original_ingress_sources(**inputs)


@pytest.mark.parametrize(("key", "different"), [
    ("batch_request_id", "request:other"),
    ("admitted_idempotency_key", "key:other"),
    ("classified_family", "ObservationEvent"),
    ("classified_family", None),
    ("request_bytes", None),
    ("envelope_bytes", None),
])
def test_refuses_missing_or_foreign_source_bindings(key, different):
    inputs = _sources()
    inputs[key] = different
    with pytest.raises(ValueError):
        verify_original_ingress_sources(**inputs)


@pytest.mark.parametrize(("source", "field", "value"), [
    ("request_bytes", "semanticEventRef", "event:other"),
    ("request_bytes", "commitClass", "EVIDENCE_RECORD"),
    ("request_bytes", "ingestedAt", "not-a-date"),
    ("request_bytes", "schemaVersion", "ofarm.commitingressrequest.v0.2"),
    ("envelope_bytes", "schemaVersion", "ofarm.semanticeventenvelope.v0.2"),
    ("envelope_bytes", "primaryEventFamily", "unknown"),
    ("envelope_bytes", "timeSemantics", {"recordTime": "2000-01-01T12:09:00Z"}),
])
def test_rejects_schema_or_join_mismatch_even_with_matching_raw_hash(source, field, value):
    inputs = _sources()
    document = json.loads(inputs[source])
    document[field] = value
    inputs[source] = json.dumps(document).encode()
    inputs[source + "_sha256"] = sha256(inputs[source]).hexdigest()
    with pytest.raises(ValueError):
        verify_original_ingress_sources(**inputs)


@pytest.mark.parametrize("source", ["request_bytes", "envelope_bytes"])
def test_duplicate_property_in_otherwise_valid_original_refuses(source):
    inputs = _sources()
    raw = inputs[source].replace(b"{", b'{"schemaVersion":"ignored",', 1)
    inputs[source] = raw
    inputs[source + "_sha256"] = sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="invalid original ingress JSON"):
        verify_original_ingress_sources(**inputs)
