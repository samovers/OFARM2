"""R03/R06: base-written receipts stay immutable and readable across bundles."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from kernel import demo
from kernel.legacy_m1.api import create_test_app
from kernel.tests.legacy_receipt_scope_history import (  # noqa: F401
    receipt_base_tree,
    receipt_history,
)
from kernel.tests.test_review_confirmation import (
    _assert_prior_records_unchanged,
    _commit,
    _snapshot,
)
from kernel.tests.test_runtime_bundle_receipts import _second_store


def _read_pair(env, result, expected):
    for key in ("resultId", "promotionTraceRef"):
        row = env.store.get_record(result[key])
        response = env.client.get("/records/" + result[key],
                                  headers={"x-acting-party": demo.FARMER})
        assert response.status_code == expected, (key, response.text)
        if expected == 200:
            assert response.json()["payload"] == row["payload"]
            assert response.json()["payloadSha256"] == row["payload_sha256"]
            assert response.json()["runtimeBundleDigest"] == row["runtime_bundle_digest"]
        else:
            assert "PERMISSION_REDACTED" in response.text
            assert "payload" not in response.json()


def _history_unchanged(before, after):
    _assert_prior_records_unchanged(before, after)
    assert after["kernel_edge"] == before["kernel_edge"]
    assert after["kernel_idempotency"] == before["kernel_idempotency"]


def _only_read_receipts(before, after):
    _history_unchanged(before, after)
    old_ids = {row["record_id"] for row in before["kernel_record"]}
    added = [row for row in after["kernel_record"] if row["record_id"] not in old_ids]
    assert added
    assert {row["record_kind"] for row in added} == {
        "ofarm.authorizationdecisionrequest.v0.1",
        "ofarm.authorizationdecisiontrace.v0.1",
        "ofarm.authorizationdecisionresult.v0.1",
    }
    for table in before.keys() - {"kernel_record"}:
        assert after[table] == before[table], table


@pytest.mark.parametrize("family", ("OPERATION_CLAIM", "OBSERVATION_ASSERTION"))
@pytest.mark.parametrize("explicit_farm", (False, True), ids=("field-only", "farm-and-field"))
def test_base_history_and_equal_body_bundle_conflicts(receipt_history, family, explicit_farm):
    env = receipt_history(family, explicit_farm)
    history = env.history
    _history_unchanged(history["snapshot"], _snapshot(env.store))

    def read_history(current):
        before = _snapshot(current.store)
        for label, result in history["cases"].items():
            expected = 403 if not explicit_farm and label in {
                "conflict", "validation_refusal"} else 200
            _read_pair(current, result, expected)
        _only_read_receipts(before, _snapshot(current.store))

    read_history(env)
    # Use the existing accepted bundle-selection/startup fixture. The old
    # producing bundle remains authoritative for association, not permission.
    store_b = _second_store(env.store)
    try:
        assert store_b.runtime_bundle_digest != env.store.runtime_bundle_digest
        original = history["cases"]["original"]
        assert store_b.get_record(original["resultId"])["runtime_bundle_digest"] != \
            store_b.runtime_bundle_digest
        with TestClient(create_test_app(store_b, oidc=None)) as client:
            current = SimpleNamespace(store=store_b, client=client)
            read_history(current)
            before = _snapshot(store_b)
            conflict = _commit(current, deepcopy(history["submission"]))
            assert conflict["decisionOutcome"] == "DENY"
            assert conflict["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
            assert conflict["replayOfRequestId"] == original["requestId"]
            assert conflict["problems"][0]["reasonCode"] == "PACK_CONFLICT"
            original_request = store_b.get_record(original["requestId"])["payload"]
            conflict_request = store_b.get_record(conflict["requestId"])["payload"]
            assert conflict_request["sourcePayloadDigest"] == original_request["sourcePayloadDigest"]
            _history_unchanged(before, _snapshot(store_b))
            reads_before = _snapshot(store_b)
            _read_pair(current, conflict, 200 if explicit_farm else 403)
            if explicit_farm:
                _only_read_receipts(reads_before, _snapshot(store_b))
            else:
                assert _snapshot(store_b) == reads_before
            _history_unchanged(history["snapshot"], _snapshot(store_b))
    finally:
        store_b.close()
