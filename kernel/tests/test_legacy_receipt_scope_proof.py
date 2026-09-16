"""Defensive graph doubles for R02/R03/R07, not emitted runtime history.

These intentionally incomplete in-memory rows isolate malformed relationships.
They never enter a Store or database and do not establish write reachability.
Real writer/history controls live in the companion HTTP and history suites.
"""
from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace

import pytest

from kernel import policy
from kernel.contracts import ContractRegistry
from kernel.legacy_m1 import receipt_scope as scope


FARM = {"scopeType": "FARM", "scopeRef": "farm:fictional.proof"}
FIELD = {"scopeType": "FIELD", "scopeRef": "field:fictional.proof"}
TENANT = "tenant:fictional.proof"
BUNDLE = "sha256:" + "a" * 64
DIGEST = "sha256:" + "b" * 64
MISSING = object()


class Graph:
    """A defensive Store double with observable, bounded point lookups only."""

    def __init__(self, registry, family="OPERATION_CLAIM", explicit_farm=False):
        self.registry, self.tenant_ref = registry, TENANT
        self.rows, self.lookups, self.index_lookups = {}, [], []
        self.conn = SimpleNamespace(cursor=lambda: nullcontext(object()))
        self.scopes = [FARM, FIELD] if explicit_farm else [FIELD]
        self.family = family
        self.put("event", scope.EVENT,
                 primaryEventFamily=policy.COMMIT_CLASS_TO_FAMILY[family],
                 anchorScopes=deepcopy(self.scopes))
        self.put("authority-request", scope.AUTH_REQUEST,
                 actingPartyRef="party:fictional.author",
                 actionClass=policy.COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS[family],
                 actionStage="PROMOTION", target={"scope": deepcopy(FARM)})
        self.put("authority-result", scope.AUTH_RESULT,
                 requestId="authority-request",
                 requestedActionClass=policy.COMMIT_CLASS_TO_AUTHORITY_ACTION_CLASS[family],
                 actionStage="PROMOTION", decisionOutcome="ALLOW", finalActionPermitted=True)
        self.attempt("original", "NEW_REQUEST")
        self.index = {"idempotency_key": "fictional:key", "request_id": "original-request",
                      "source_payload_digest": DIGEST, "result_record_id": "original-result",
                      "tenant_ref": TENANT, "runtime_bundle_digest": BUNDLE}

    def put(self, reference, kind, **payload):
        self.rows[reference] = {
            "record_id": reference, "record_kind": kind,
            "tenant_ref": TENANT, "runtime_bundle_digest": BUNDLE,
            "payload": {"schemaVersion": kind, self.registry.get(kind).id_field: reference,
                        **payload},
        }

    def attempt(self, name, disposition, original="original-request"):
        common = {"requestId": name + "-request", "semanticEventRef": "event",
                  "commitClass": self.family,
                  "primaryEventFamily": policy.COMMIT_CLASS_TO_FAMILY[self.family]}
        self.put(name + "-request", scope.REQUEST,
                 semanticEventRef="event", commitClass=self.family,
                 actingPartyRef="party:fictional.author", idempotencyKey="fictional:key",
                 sourcePayloadDigest=DIGEST, targetScopes=deepcopy(self.scopes))
        outcome = {"NEW_REQUEST": "RETAIN_DRAFT",
                   "REPLAY_MATCH_REUSED_RESULT": "REPLAY_REUSED_RESULT",
                   "CONFLICTING_REPLAY_BLOCKED": "DENY"}[disposition]
        replay = {} if disposition == "NEW_REQUEST" else {"replayOfRequestId": original}
        self.put(name + "-trace", scope.TRACE, **common, **replay,
                 idempotencyKey="fictional:key", idempotencyDisposition=disposition,
                 finalOutcome=outcome)
        self.put(name + "-result", scope.RESULT, **common, **replay,
                 promotionTraceRef=name + "-trace", idempotencyDisposition=disposition,
                 decisionOutcome=outcome)
        if disposition == "NEW_REQUEST":
            self.payload(name + "-trace").update(
                authorizationDecisionResultRef="authority-result",
                emittedAssertionRecordRefs=["assertion:fictional.capture"],
                gateSequence=[{"gate": "AUTHORITY", "outcome": "ALLOW",
                               "relatedArtifactRefs": ["authority-request", "authority-result"]},
                              {"gate": "VALIDATION", "outcome": "PASS"}])
        if disposition != "CONFLICTING_REPLAY_BLOCKED":
            # Real ReplayWriter carries these on the result, not its trace.
            self.payload(name + "-result")["emittedAssertionRecordRefs"] = [
                "assertion:fictional.capture"]

    def payload(self, reference):
        return self.rows[reference]["payload"]

    def get_record(self, reference):
        self.lookups.append(reference)
        assert len(self.lookups) <= 12, "resolver exceeded the closed typed path"
        return self.rows.get(reference)

    def idempotency_lookup(self, cursor, key):
        self.index_lookups.append(key)
        assert len(self.index_lookups) <= 1, "resolver followed a second replay hop"
        return self.index

    def resolve(self, reference):
        self.lookups.clear()
        self.index_lookups.clear()
        return scope.receipt_farm_scopes(self, self.rows.get(reference))


@pytest.fixture(scope="module")
def registry():
    return ContractRegistry()


@pytest.fixture
def graph(registry):
    return Graph(registry)


@pytest.mark.parametrize("family", ("OPERATION_CLAIM", "OBSERVATION_ASSERTION"))
@pytest.mark.parametrize("explicit_farm", (False, True), ids=("field", "farm"))
@pytest.mark.parametrize("root", ("result", "trace"))
@pytest.mark.parametrize("disposition", (
    "NEW_REQUEST", "REPLAY_MATCH_REUSED_RESULT", "CONFLICTING_REPLAY_BLOCKED"))
def test_typed_proof_controls(registry, family, explicit_farm, root, disposition):
    graph = Graph(registry, family, explicit_farm)
    name = "original"
    if disposition != "NEW_REQUEST":
        name = "retry"
        graph.attempt(name, disposition)
    expected = None if disposition == "CONFLICTING_REPLAY_BLOCKED" and not explicit_farm \
        else [FARM["scopeRef"]]
    assert graph.resolve(name + "-" + root) == expected
    assert len(graph.index_lookups) == (0 if disposition == "NEW_REQUEST" else 1)


@pytest.mark.parametrize("root", ("result", "trace"))
@pytest.mark.parametrize("reference", (
    "original-trace", "original-request", "event", "authority-result", "authority-request"))
@pytest.mark.parametrize("defect", ("missing", "kind", "schema", "row-id", "payload-id",
                                     "tenant", "bundle"))
def test_broken_typed_links_deny(graph, root, reference, defect):
    row = graph.rows[reference]
    if defect == "missing":
        del graph.rows[reference]
    elif defect == "kind":
        row["record_kind"] = scope.REQUEST if row["record_kind"] != scope.REQUEST else scope.EVENT
    elif defect == "schema":
        row["payload"]["schemaVersion"] = scope.RESULT
    elif defect == "row-id":
        row["record_id"] = "fictional:wrong-row"
    elif defect == "payload-id":
        row["payload"][graph.registry.get(row["record_kind"]).id_field] = "fictional:wrong-payload"
    elif defect == "tenant":
        row["tenant_ref"] = "tenant:fictional.foreign"
    else:
        row["runtime_bundle_digest"] = "sha256:" + "c" * 64
    assert graph.resolve("original-" + root) is None
    assert not graph.index_lookups


@pytest.mark.parametrize("root", ("result", "trace"))
@pytest.mark.parametrize("scopes", (MISSING, None, [], {}, [None], [{}],
                                     [{"scopeType": "FIELD", "scopeRef": ""}],
                                     [{"scopeType": [], "scopeRef": "field:fictional"}],
                                     [{"scopeType": "TENANT", "scopeRef": TENANT}]))
def test_missing_or_malformed_field_scopes_deny(graph, root, scopes):
    for reference, field in (("event", "anchorScopes"), ("original-request", "targetScopes")):
        if scopes is MISSING:
            del graph.payload(reference)[field]
        else:
            graph.payload(reference)[field] = deepcopy(scopes)
    assert graph.resolve("original-" + root) is None


@pytest.mark.parametrize("root", ("result", "trace"))
@pytest.mark.parametrize("defect", (
    "no-authority", "no-pass", "reversed", "duplicate-authority", "wrong-refs",
    "wrong-actor", "wrong-action", "wrong-stage", "denied", "not-permitted",
    "wrong-target", "different-scopes", "mixed-farms", "farm-authority-disagrees"))
def test_missing_or_inconsistent_association_evidence_denies(graph, root, defect):
    trace = graph.payload("original-trace")
    gates = trace["gateSequence"]
    if defect == "no-authority":
        del trace["authorizationDecisionResultRef"]
    elif defect == "no-pass":
        gates[1]["outcome"] = "FAIL"
    elif defect == "reversed":
        gates.reverse()
    elif defect == "duplicate-authority":
        gates.insert(0, deepcopy(gates[0]))
    elif defect == "wrong-refs":
        gates[0]["relatedArtifactRefs"] = ["authority-result", "fictional:other-request"]
    elif defect == "wrong-actor":
        graph.payload("authority-request")["actingPartyRef"] = "party:fictional.other"
    elif defect == "wrong-action":
        graph.payload("authority-result")["requestedActionClass"] = "REVIEW_ACCEPT"
    elif defect == "wrong-stage":
        graph.payload("authority-request")["actionStage"] = "READ"
    elif defect == "denied":
        graph.payload("authority-result")["decisionOutcome"] = "DENY"
    elif defect == "not-permitted":
        graph.payload("authority-result")["finalActionPermitted"] = False
    elif defect == "wrong-target":
        graph.payload("authority-request")["target"]["scope"] = deepcopy(FIELD)
    elif defect == "different-scopes":
        graph.payload("original-request")["targetScopes"] = [deepcopy(FARM)]
    else:
        scopes = [deepcopy(FARM), {"scopeType": "FARM", "scopeRef": "farm:fictional.other"}]
        if defect == "farm-authority-disagrees":
            scopes.pop(0)
        graph.payload("original-request")["targetScopes"] = deepcopy(scopes)
        graph.payload("event")["anchorScopes"] = deepcopy(scopes)
    assert graph.resolve("original-" + root) is None


@pytest.mark.parametrize("sequence,permitted", (
    (("REGISTRY_REVERIFIED", "PASS"), True),
    (("REGISTRY_REVERIFIED", "PASS", "FAIL_CARRIER"), True),
    (("PASS", "FAIL_CARRIER"), True),
    (("REGISTRY_REVERIFIED",), False),
    (("REGISTRY_REVERIFIED", "FAIL_REFERENCE_RESOLUTION", "PASS"), False),
    (("FAIL_REFERENCE_RESOLUTION", "REGISTRY_REVERIFIED", "PASS"), False),
    (("UNKNOWN", "PASS"), False),
    ((None, "PASS"), False),
))
def test_validation_completion_for_original_and_matching_receipts(graph, sequence, permitted):
    gates = graph.payload("original-trace")["gateSequence"]
    gates[1:] = [{"gate": "VALIDATION", "outcome": outcome} for outcome in sequence]
    graph.attempt("retry", "REPLAY_MATCH_REUSED_RESULT")
    expected = [FARM["scopeRef"]] if permitted else None
    for attempt in ("original", "retry"):
        for root in ("result", "trace"):
            assert graph.resolve(attempt + "-" + root) == expected, (attempt, root)


@pytest.mark.parametrize("defect", ("validation-before-authority", "duplicate-authority"))
def test_reverification_does_not_relax_authority_order(graph, defect):
    gates = graph.payload("original-trace")["gateSequence"]
    gates.insert(1, {"gate": "VALIDATION", "outcome": "REGISTRY_REVERIFIED"})
    if defect == "validation-before-authority":
        gates[0], gates[1] = gates[1], gates[0]
    else:
        gates.insert(1, deepcopy(gates[0]))
    graph.attempt("retry", "REPLAY_MATCH_REUSED_RESULT")
    for attempt in ("original", "retry"):
        for root in ("result", "trace"):
            assert graph.resolve(attempt + "-" + root) is None, (attempt, root)


@pytest.mark.parametrize("root", ("result", "trace"))
@pytest.mark.parametrize("disposition", ("REPLAY_MATCH_REUSED_RESULT", "CONFLICTING_REPLAY_BLOCKED"))
@pytest.mark.parametrize("defect", (
    "missing", "key", "request", "result", "digest", "tenant", "bundle", "original-is-replay"))
def test_replay_requires_one_index_bound_original(registry, root, disposition, defect):
    graph = Graph(registry, explicit_farm=True)
    graph.attempt("retry", disposition)
    if defect == "missing":
        graph.index = None
    elif defect == "original-is-replay":
        graph.attempt("original", "CONFLICTING_REPLAY_BLOCKED", "retry-request")
    else:
        field = {"key": "idempotency_key", "request": "request_id", "result": "result_record_id",
                 "digest": "source_payload_digest", "tenant": "tenant_ref",
                 "bundle": "runtime_bundle_digest"}[defect]
        graph.index[field] = "fictional:mismatch"
    assert graph.resolve("retry-" + root) is None
    assert len(graph.index_lookups) == 1


@pytest.mark.parametrize("root", ("result", "trace"))
@pytest.mark.parametrize("defect", ("digest", "bundle", "scopes"))
def test_matching_attempt_must_agree_with_original(graph, root, defect):
    graph.attempt("retry", "REPLAY_MATCH_REUSED_RESULT")
    if defect == "digest":
        graph.payload("retry-request")["sourcePayloadDigest"] = "sha256:" + "c" * 64
    elif defect == "bundle":
        for suffix in ("result", "trace", "request"):
            graph.rows["retry-" + suffix]["runtime_bundle_digest"] = "sha256:" + "c" * 64
    else:
        graph.payload("retry-request")["targetScopes"] = [deepcopy(FARM)]
    assert graph.resolve("retry-" + root) is None


def test_matching_result_checks_reused_emissions_without_requiring_trace_copies(graph):
    graph.attempt("retry", "REPLAY_MATCH_REUSED_RESULT")
    assert "emittedAssertionRecordRefs" not in graph.payload("retry-trace")
    assert graph.resolve("retry-result") == [FARM["scopeRef"]]
    assert graph.resolve("retry-trace") == [FARM["scopeRef"]]
    graph.payload("retry-result")["emittedAssertionRecordRefs"] = ["assertion:fictional.other"]
    assert graph.resolve("retry-result") is None
    # Trace roots have no reverse result link; do not invent a graph search.
    assert graph.resolve("retry-trace") == [FARM["scopeRef"]]


@pytest.mark.parametrize("root", ("result", "trace"))
def test_b1_matching_retry_request_cannot_replace_original(registry, root):
    graph = Graph(registry, explicit_farm=True)
    graph.attempt("matching", "REPLAY_MATCH_REUSED_RESULT")
    graph.attempt("conflict", "CONFLICTING_REPLAY_BLOCKED", "matching-request")
    # O/R/C agree on key, event, class and FARM. Only the existing index binds O.
    assert graph.resolve("conflict-" + root) is None
    assert graph.index_lookups == ["fictional:key"]


@pytest.mark.parametrize("root", ("result", "trace"))
@pytest.mark.parametrize("cycle", ("self", "two-node"))
def test_replay_cycles_terminate_without_second_index_hop(registry, root, cycle):
    graph = Graph(registry, explicit_farm=True)
    graph.attempt("retry", "CONFLICTING_REPLAY_BLOCKED",
                  "retry-request" if cycle == "self" else "original-request")
    if cycle == "self":
        graph.index.update(request_id="retry-request", result_record_id="retry-result")
    else:
        graph.attempt("original", "CONFLICTING_REPLAY_BLOCKED", "retry-request")
    assert graph.resolve("retry-" + root) is None
    assert len(graph.index_lookups) == 1
