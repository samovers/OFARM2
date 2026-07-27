"""Transport-shape tests for the legacy semantic ingress boundary."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import FrozenInstanceError
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import psycopg
import pytest

import kernel.gates as gates_module
from kernel.contracts import ContractViolation
from kernel.gates import GatePipeline
from kernel.legacy_m1.api import _install_commit_route
from kernel.stages import (
    IngressHeader,
    IngressHeaderViolation,
    parse_ingress_header,
)


def _valid_submission() -> dict:
    return {
        "commitClass": "OPERATION_CLAIM",
        "farmRef": "farm:transport-test",
        "actingPartyRef": "party:transport-test",
        "idempotencyKey": "idem:transport-test",
    }


def _without(field_name: str) -> dict:
    submission = _valid_submission()
    submission.pop(field_name)
    return submission


def _with(field_name: str, value) -> dict:
    submission = _valid_submission()
    submission[field_name] = value
    return submission


_MALFORMED_DIRECT_SUBMISSIONS = [
    pytest.param(None, id="body-none"),
    pytest.param([], id="body-list"),
    pytest.param("submission", id="body-string"),
]
for _field_name in (
    "commitClass",
    "farmRef",
    "actingPartyRef",
    "idempotencyKey",
):
    _MALFORMED_DIRECT_SUBMISSIONS.append(
        pytest.param(_without(_field_name), id=f"missing-{_field_name}")
    )
    for _label, _value in (
        ("none", None),
        ("boolean", False),
        ("number", 7),
        ("list", ["raw-value"]),
        ("object", {"raw": "value"}),
        ("empty", ""),
    ):
        _MALFORMED_DIRECT_SUBMISSIONS.append(
            pytest.param(
                _with(_field_name, _value),
                id=f"{_field_name}-{_label}",
            )
        )


class _NoTransactionStore:
    def __init__(self):
        self.transaction_calls = 0

    def serialized_tx(self):
        self.transaction_calls += 1
        raise AssertionError("malformed ingress must not open a transaction")


def _pipeline_with_store(store) -> GatePipeline:
    pipeline = GatePipeline.__new__(GatePipeline)
    pipeline.store = store
    pipeline.authority = object()
    pipeline.runtime_services = object()
    return pipeline


@pytest.mark.parametrize("submission", _MALFORMED_DIRECT_SUBMISSIONS)
def test_malformed_direct_header_raises_only_typed_transport_violation(
    submission,
):
    store = _NoTransactionStore()
    pipeline = _pipeline_with_store(store)

    with pytest.raises(IngressHeaderViolation) as raised:
        pipeline.commit(submission)

    assert not isinstance(raised.value, ContractViolation)
    assert raised.value.args == ()
    assert raised.value.__dict__ == {}
    assert str(raised.value) == ""
    assert store.transaction_calls == 0


def test_ingress_header_is_frozen_and_preserves_exact_strings():
    submission = {
        "commitClass": " UNKNOWN_CLASS ",
        "farmRef": " farm:untrimmed ",
        "actingPartyRef": "party:ümlaut",
        "idempotencyKey": " idem:Mixed.Case ",
    }

    header = parse_ingress_header(submission)

    assert header == IngressHeader(
        commit_class=" UNKNOWN_CLASS ",
        farm_ref=" farm:untrimmed ",
        acting_party_ref="party:ümlaut",
        idempotency_key=" idem:Mixed.Case ",
    )
    with pytest.raises(FrozenInstanceError):
        header.idempotency_key = "idem:changed"


def _commit_client(store, principal: str) -> TestClient:
    app = FastAPI()
    pipeline = _pipeline_with_store(store)

    def resolved_principal() -> str:
        return principal

    _install_commit_route(app, pipeline, resolved_principal)
    return TestClient(app)


@pytest.mark.parametrize(
    "submission",
    (
        pytest.param(
            _without("commitClass"),
            id="missing-commit-class",
        ),
        pytest.param(
            _with("commitClass", ""),
            id="empty-commit-class",
        ),
        pytest.param(
            _with("farmRef", ["raw-secret-marker"]),
            id="wrong-farm-type",
        ),
        pytest.param(
            _with("idempotencyKey", {"raw": "raw-secret-marker"}),
            id="wrong-idempotency-type",
        ),
    ),
)
def test_legacy_http_maps_transport_violation_to_one_fixed_safe_422(
    submission,
):
    store = _NoTransactionStore()
    client = _commit_client(store, submission["actingPartyRef"])

    response = client.post("/commit", json={"submission": submission})

    assert response.status_code == 422
    assert response.json() == {
        "detail": "malformed ingress submission header"
    }
    encoded = json.dumps(response.json(), sort_keys=True)
    assert "reasonCode" not in encoded
    assert "problemId" not in encoded
    assert "schemaVersion" not in encoded
    assert "raw-secret-marker" not in encoded
    assert store.transaction_calls == 0


@pytest.mark.parametrize(
    "actor",
    (
        pytest.param(None, id="missing"),
        pytest.param(["raw-secret-marker"], id="wrong-type"),
        pytest.param("party:different", id="different"),
    ),
)
def test_existing_http_actor_binding_outcome_takes_precedence(actor):
    store = _NoTransactionStore()
    principal = "party:transport-test"
    submission = _valid_submission()
    if actor is None:
        submission.pop("actingPartyRef")
    else:
        submission["actingPartyRef"] = actor
    client = _commit_client(store, principal)

    response = client.post("/commit", json={"submission": submission})

    assert response.status_code == 403
    assert response.json()["detail"]["reasonCode"] == \
        "ACTOR_BINDING_UNRESOLVED"
    assert "raw-secret-marker" not in json.dumps(response.json())
    assert store.transaction_calls == 0


class _RecoveryStore:
    def __init__(self, prior):
        self.prior = prior
        self.transaction_calls = 0
        self.lookup_calls = []

    @contextmanager
    def serialized_tx(self):
        self.transaction_calls += 1
        yield f"cursor:{self.transaction_calls}"

    def idempotency_lookup(self, cur, key):
        self.lookup_calls.append((cur, key))
        return self.prior


def test_concurrency_recovery_reuses_one_parsed_header(monkeypatch):
    prior = {"marker": "winner"}
    store = _RecoveryStore(prior)
    pipeline = _pipeline_with_store(store)
    submission = _valid_submission()
    original = submission.copy()
    parse_calls = []
    first_attempt_headers = []
    replay_context = {}
    real_parser = gates_module.parse_ingress_header

    def tracked_parser(value):
        parse_calls.append(value)
        return real_parser(value)

    def lose_race(_cur, raw_submission, header):
        first_attempt_headers.append(header)
        raw_submission.update(
            {
                "commitClass": 7,
                "farmRef": None,
                "actingPartyRef": {"changed": True},
                "idempotencyKey": ["changed"],
            }
        )
        raise psycopg.errors.UniqueViolation("simulated idempotency race")

    class _ReplayWriter:
        def write(self, ctx, received_prior):
            replay_context.update(
                {
                    "prior": received_prior,
                    "commit_class": ctx.commit_class,
                    "farm_ref": ctx.farm_ref,
                    "acting_party": ctx.acting_party,
                    "idempotency_key": ctx.idem_key,
                    "raw_submission": ctx.sub,
                }
            )
            return {"status": "replayed"}

    monkeypatch.setattr(gates_module, "parse_ingress_header", tracked_parser)
    monkeypatch.setattr(pipeline, "_commit_in_tx", lose_race)
    monkeypatch.setattr(gates_module, "ReplayWriter", _ReplayWriter)

    result = pipeline.commit(submission)

    assert result == {"status": "replayed"}
    assert len(parse_calls) == 1
    assert first_attempt_headers == [
        IngressHeader(
            commit_class=original["commitClass"],
            farm_ref=original["farmRef"],
            acting_party_ref=original["actingPartyRef"],
            idempotency_key=original["idempotencyKey"],
        )
    ]
    assert store.transaction_calls == 2
    assert store.lookup_calls == [
        ("cursor:2", original["idempotencyKey"])
    ]
    assert replay_context == {
        "prior": prior,
        "commit_class": original["commitClass"],
        "farm_ref": original["farmRef"],
        "acting_party": original["actingPartyRef"],
        "idempotency_key": original["idempotencyKey"],
        "raw_submission": submission,
    }


def test_concurrency_recovery_preserves_unmatched_integrity_error(monkeypatch):
    store = _RecoveryStore(prior=None)
    pipeline = _pipeline_with_store(store)
    submission = _valid_submission()
    original_error = psycopg.errors.UniqueViolation(
        "unrelated integrity failure"
    )

    def fail(_cur, _submission, _header):
        raise original_error

    monkeypatch.setattr(pipeline, "_commit_in_tx", fail)

    with pytest.raises(psycopg.errors.UniqueViolation) as raised:
        pipeline.commit(submission)

    assert raised.value is original_error
    assert store.transaction_calls == 2
    assert store.lookup_calls == [
        ("cursor:2", submission["idempotencyKey"])
    ]
