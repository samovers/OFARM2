"""Transaction-level promotion proof for assertions on the ordinary signed write path."""

from contextlib import contextmanager

import psycopg
import pytest
from psycopg import sql

from kernel.tests.postgresql_tenant_support import tenant_target as tenant_target
from kernel.tests.test_postgresql_tenant_migration import (
    _insert_batch,
    _insert_record,
    _signed_capability_for_new_challenge,
    authority as authority,
    capability_key as capability_key,
    other_authority as other_authority,
)

ASSERTION = "ofarm.assertionrecord.v0.2"
TRACE = "ofarm.promotiontrace.v0.1"
LEGACY = {
    "ofarm.assertionrecord.v0.1": "emittedAssertionRecordRefs",
    "ofarm.semanticeventenvelope.v0.1": "semanticEventRef",
    "ofarm.reviewdecision.v0.1": "emittedReviewDecisionRefs",
    "ofarm.acceptedeventconsequence.v0.1": "emittedAcceptedConsequenceRefs",
}


@pytest.fixture(params=("ofarm_app", "ofarm_worker"))
def role(request):
    return request.param


@contextmanager
def _writer(target, principal, key, role):
    with psycopg.connect(target.role_dsn(role)) as writer:
        capability = _signed_capability_for_new_challenge(writer, authority=principal, key=key)
        writer.execute("SELECT ofarm.bind_tenant_capability(%s)", (capability,))
        assert writer.execute("SELECT current_user, ofarm.current_tenant_id()").fetchone() == (
            role, principal.tenant_id,
        )
        yield writer


def _ledger(target, principal):
    """Read all rows and original transaction stamps in one fresh, authorized snapshot."""
    with psycopg.connect(target.target_admin_dsn) as reader:
        reader.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        assert reader.execute(
            "SELECT 1 FROM ofarm.kernel_record WHERE tenant_id = %s AND record_id = %s",
            (principal.tenant_id, principal.party_ref),
        ).fetchone() == (1,)
        return tuple(
            [row for (row,) in reader.execute(
                sql.SQL("SELECT to_jsonb(r) FROM ofarm.{} r ORDER BY tenant_id, {}")
                .format(sql.Identifier(table), sql.Identifier(key))
            )]
            for table, key in (
                ("governed_write_batch", "batch_id"), ("kernel_record", "record_id"),
                ("kernel_edge", "edge_id"),
            )
        )


def _record(writer, principal, batch, record_id, kind, payload, lane="canonical"):
    _insert_record(writer, principal, batch_id=batch, record_id=record_id, record_kind=kind,
                   payload=payload, lane=lane)


def _edge(writer, principal, batch, trace, assertion):
    writer.execute(
        """INSERT INTO ofarm.kernel_edge (tenant_id, edge_kind, src_record_id, dst_record_id, batch_id)
           VALUES (%s, 'PROMOTION_EMITS', %s, %s, %s)""",
        (principal.tenant_id, trace, assertion, batch),
    )


def _pending(assertion):
    return {"assertionId": assertion, "claimState": "PENDING_REVIEW"}


@pytest.mark.parametrize("order", ["assertion-first", "edge-first", "rollback"])
def test_pending_assertion_and_proof_are_atomic(tenant_target, authority, capability_key, role, order):
    batch = f"atomic-{role}-{order}"
    assertion, trace = batch + "-assertion", batch + "-trace"
    emission = {"emittedAssertionRecordRefs": [assertion]}
    before = _ledger(tenant_target, authority)
    with _writer(tenant_target, authority, capability_key, role) as writer:
        _insert_batch(writer, authority, batch)
        if order == "edge-first":
            _edge(writer, authority, batch, trace, assertion)
        _record(writer, authority, batch, assertion, ASSERTION, _pending(assertion))
        _record(writer, authority, batch, trace, TRACE, emission)
        if order != "edge-first":
            _edge(writer, authority, batch, trace, assertion)
        assert _ledger(tenant_target, authority) == before
        if order == "rollback":
            writer.rollback()
        else:
            writer.commit()

    after = _ledger(tenant_target, authority)
    if order == "rollback":
        assert after == before
        return
    assert tuple([row for row in table if row["batch_id"] != batch] for table in after) == before
    (header,), records, (edge,) = (
        [row for row in table if row["batch_id"] == batch] for table in after
    )
    assert [(r["record_id"], r["record_kind"], r["payload"]) for r in records] == [
        (assertion, ASSERTION, _pending(assertion)), (trace, TRACE, emission),
    ]
    assert (edge["src_record_id"], edge["dst_record_id"], edge["edge_kind"]) == (
        trace, assertion, "PROMOTION_EMITS",
    )
    assert header["tenant_id"] == str(authority.tenant_id)
    assert header["full_xid"]
    for row in (*records, edge):
        assert (row["tenant_id"], row["batch_id"], row["batch_full_xid"]) == (
            header["tenant_id"], header["batch_id"], header["full_xid"],
        )


@pytest.mark.parametrize("case", [
    "missing", "trace-only", "other-kind", "other-id", "event-only", "object",
    "scalar", "nested", "draft-state",
])
def test_bad_proof_refuses_at_commit(tenant_target, authority, capability_key, role, case):
    batch = f"bad-{role}-{case}"
    assertion, trace = batch + "-assertion", batch + "-trace"
    payload = {
        "event-only": {"semanticEventRef": assertion},
        "other-id": {"emittedAssertionRecordRefs": ["another-assertion"]},
        "object": {"emittedAssertionRecordRefs": {assertion: True}},
        "scalar": {"emittedAssertionRecordRefs": assertion},
        "nested": {"emittedAssertionRecordRefs": [[assertion]]},
    }.get(case, {"emittedAssertionRecordRefs": [assertion]})
    before = _ledger(tenant_target, authority)
    with _writer(tenant_target, authority, capability_key, role) as writer:
        _insert_batch(writer, authority, batch)
        _record(writer, authority, batch, batch + "-support", "ofarm.test.v0.1", {})
        if case == "draft-state":
            _record(writer, authority, batch, assertion, ASSERTION, {"claimState": "DRAFT"}, lane="draft")
        else:
            _record(writer, authority, batch, assertion, ASSERTION, _pending(assertion))
        if case not in {"missing", "draft-state"}:
            kind = "ofarm.test.v0.1" if case == "other-kind" else TRACE
            _record(writer, authority, batch, trace, kind, payload)
            if case != "trace-only":
                _edge(writer, authority, batch, trace, assertion)
        assert _ledger(tenant_target, authority) == before
        with pytest.raises(psycopg.errors.CheckViolation) as failure:
            writer.commit()
        if case in {"missing", "trace-only", "event-only", "object", "scalar", "draft-state"}:
            assert failure.value.diag.message_primary == "v0.2 assertion lacks matching promotion proof"
    assert _ledger(tenant_target, authority) == before


@pytest.mark.parametrize("foreign", [False, True], ids=["prior-batch", "foreign-tenant"])
def test_source_must_belong_to_this_save(
    tenant_target, authority, other_authority, capability_key, role, foreign,
):
    batch = f"provenance-{role}-{int(foreign)}"
    prior = batch + "-prior"
    assertion, trace = batch + "-assertion", batch + "-trace"
    source_owner = other_authority if foreign else authority
    with _writer(tenant_target, source_owner, capability_key, role) as writer:
        _insert_batch(writer, source_owner, prior)
        _record(writer, source_owner, prior, trace, TRACE, {"emittedAssertionRecordRefs": [assertion]})
    before = _ledger(tenant_target, authority)
    assert any(r["record_id"] == trace for r in before[1])
    with _writer(tenant_target, authority, capability_key, role) as writer:
        visible = writer.execute("SELECT tenant_id FROM ofarm.kernel_record WHERE record_id = %s",
                                 (trace,)).fetchall()
        assert visible == ([] if foreign else [(authority.tenant_id,)])
        _insert_batch(writer, authority, batch)
        _edge(writer, authority, batch, trace, assertion)
        _record(writer, authority, batch, assertion, ASSERTION, _pending(assertion))
        assert _ledger(tenant_target, authority) == before
        failure = psycopg.errors.ForeignKeyViolation if foreign else psycopg.errors.CheckViolation
        with pytest.raises(failure):
            writer.commit()
    assert _ledger(tenant_target, authority) == before


def test_two_promotion_edges_refuse_at_insert(tenant_target, authority, capability_key, role):
    batch = f"duplicate-{role}"
    assertion = batch + "-assertion"
    before = _ledger(tenant_target, authority)
    with _writer(tenant_target, authority, capability_key, role) as writer:
        _insert_batch(writer, authority, batch)
        _record(writer, authority, batch, assertion, ASSERTION, _pending(assertion))
        for trace in (batch + "-trace-a", batch + "-trace-b"):
            _record(writer, authority, batch, trace, TRACE, {"emittedAssertionRecordRefs": [assertion]})
        _edge(writer, authority, batch, batch + "-trace-a", assertion)
        assert _ledger(tenant_target, authority) == before
        with pytest.raises(psycopg.errors.UniqueViolation) as failure:
            _edge(writer, authority, batch, batch + "-trace-b", assertion)
        assert failure.value.diag.constraint_name == "kernel_edge_promotion_destination_key"
        writer.rollback()
    assert _ledger(tenant_target, authority) == before


def test_legacy_trace_without_edge_still_refuses(tenant_target, authority, capability_key, role):
    batch = f"legacy-trace-only-{role}"
    dest = batch + "-assertion"
    before = _ledger(tenant_target, authority)
    with _writer(tenant_target, authority, capability_key, role) as writer:
        _insert_batch(writer, authority, batch)
        _record(writer, authority, batch, dest, "ofarm.assertionrecord.v0.1", _pending(dest))
        _record(writer, authority, batch, batch + "-trace", TRACE, {"emittedAssertionRecordRefs": [dest]})
        assert _ledger(tenant_target, authority) == before
        with pytest.raises(psycopg.errors.CheckViolation) as missing:
            writer.commit()
        assert missing.value.diag.message_primary == "authoritative record lacks same-batch promotion reachability"
    assert _ledger(tenant_target, authority) == before


@pytest.mark.parametrize("kind,field", LEGACY.items())
def test_older_kinds_still_require_a_trace(tenant_target, authority, capability_key, role, kind, field):
    batch = f"legacy-{role}-{kind}"
    dest, trace = batch + "-dest", batch + "-trace"
    before = _ledger(tenant_target, authority)
    with _writer(tenant_target, authority, capability_key, role) as writer:
        _insert_batch(writer, authority, batch)
        _record(writer, authority, batch, dest, kind, {})
        with pytest.raises(psycopg.errors.CheckViolation) as missing:
            writer.commit()
        assert missing.value.diag.message_primary == "authoritative record lacks same-batch promotion reachability"
    assert _ledger(tenant_target, authority) == before
    with _writer(tenant_target, authority, capability_key, role) as writer:
        _insert_batch(writer, authority, batch)
        _record(writer, authority, batch, dest, kind, {})
        _record(writer, authority, batch, trace, TRACE, {field: dest if field == "semanticEventRef" else [dest]})
        _edge(writer, authority, batch, trace, dest)
        assert _ledger(tenant_target, authority) == before
        writer.commit()
    after = _ledger(tenant_target, authority)
    assert tuple([row for row in table if row["batch_id"] != batch] for table in after) == before
    assert [sum(row["batch_id"] == batch for row in table) for table in after] == [1, 2, 1]
    with _writer(tenant_target, authority, capability_key, role) as writer:
        for statement in (
            "UPDATE ofarm.kernel_record SET payload = payload WHERE record_id = %s",
            "DELETE FROM ofarm.kernel_edge WHERE dst_record_id = %s",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), writer.transaction():
                writer.execute(statement, (dest,))
    assert _ledger(tenant_target, authority) == after
