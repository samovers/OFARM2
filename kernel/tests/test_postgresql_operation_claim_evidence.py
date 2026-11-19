"""One fictional typed submission through the real tenant transaction manager."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import time
from uuid import uuid4
from zipfile import ZipFile

import psycopg
import pytest
from psycopg import sql

from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome
from kernel.tests import _operation_claim_collector as collector
from kernel.tests._operation_claim_collector import (
    CaptureRefused,
    FixtureEvidenceManager,
    guard_keys,
    read_handoff,
    register,
)
from kernel.tests._operation_claim_specimen import (
    FIXTURES,
    check_owner_subject,
    json_bytes,
    original_sources,
    owner_arguments,
    raw_hash,
    selection,
    unpack,
)
from kernel.tests._physical_outcome_support import lose_commit_reply, physical_harness
from kernel.tests.postgresql_tenant_support import tenant_target as tenant_target
from kernel.tests.test_physical_outcome_runtime import role as role
from kernel.tests.test_postgresql_tenant_migration import (
    authority as authority,
    capability_key as capability_key,
)


@pytest.fixture(scope="module")
def storage(tenant_target, authority):
    case = selection()
    sources = original_sources(case)
    with psycopg.connect(tenant_target.target_admin_dsn) as db:
        db.execute((FIXTURES / "storage.sql").read_text())
        with db.cursor() as cur:
            for tenant in [authority.tenant_id, authority.other_tenant_id]:
                cur.executemany(
                    "INSERT INTO claim_evidence.guard(tenant,key) VALUES (%s,%s)",
                    [(tenant, key) for key in guard_keys(case)],
                )
                cur.executemany(
                    "INSERT INTO claim_evidence.source VALUES (%s,%s,%s,%s)",
                    [(tenant, ref, case["sources"][ref]["revision"], raw) for ref, raw in sources.items()],
                )
                cur.executemany(
                    "INSERT INTO claim_evidence.member VALUES (%s,%s,%s,%s)",
                    [
                        (tenant, case["set"]["key"], pos, ref)
                        for pos, ref in enumerate(case["set"]["members"])
                    ],
                )
    return tenant_target.target_admin_dsn


@pytest.fixture
def harness(tenant_target, authority, capability_key, tmp_path, role, storage):
    with physical_harness(
        tenant_target, authority, capability_key, tmp_path, role, manager_type=FixtureEvidenceManager
    ) as instance:
        yield instance


def counts(db, tenant):
    return db.execute(
        """SELECT (SELECT count(*) FROM ofarm.governed_write_batch WHERE tenant_id=%s),
        (SELECT count(*) FROM ofarm.kernel_record WHERE tenant_id=%s),
        (SELECT count(*) FROM ofarm.kernel_edge WHERE tenant_id=%s)""",
        (tenant,) * 3,
    ).fetchone()


def test_capture_one_submission(harness, authority, storage, tmp_path):
    with psycopg.connect(storage, autocommit=True) as observer:
        ticket = register(observer, authority.tenant_id)
        before = counts(observer, ticket.tenant)
        with harness.manager.submission(harness.principal, storage, ticket) as (session, unit):
            session.capture(unit, ticket)
            nonce = unit.binding.capability_nonce
            with pytest.raises(CaptureRefused, match="No completed"):
                read_handoff(observer, ticket)
        observed = read_handoff(observer, ticket)
        after = counts(observer, ticket.tenant)
        assert after == before
        observed["ledgerDelta"] = dict(
            zip(("batches", "records", "edges"), (a - b for a, b in zip(after, before)))
        )
        assert observed["bindingNonce"] == str(nonce)
        assert observed["finalization"] == "COMPLETED"
        assert observed["missingOwnerInputs"] == ["act"]
        assert observed["captureDisposition"] == "MISSING_OWNER_ORIGINALS"
        with pytest.raises(CaptureRefused, match="Closed"):
            session.capture(unit, ticket)
        with pytest.raises(CaptureRefused, match="spent"):
            with harness.manager.submission(harness.principal, storage, ticket):
                pytest.fail("a completed ticket was reused")
        owners = observed.pop("ownerInputs")
        state = owners["state"]
        context, proof = (json.loads(unpack(state[k + "_bytes"])) for k in ["context", "proof"])
        case = selection()
        expected_keys = {v["key"] for v in case["uses"] if v["role"] != "PROPOSED_WRITE"}
        assert (
            {r["key"] for r in context["requiredReads"]}
            == {r["key"] for r in proof["readGuards"]}
            == expected_keys
        )
        assert [r["key"] for r in proof["negativeGuards"]] == [case["assertionId"]]
        assert [r["ref"] for r in proof["setGuards"][0]["members"]] == case["set"]["members"]
        assert proof["proposedDomainWrites"] == [
            {
                "operation": "INSERT",
                "recordType": "AssertionRecord",
                "key": case["assertionId"],
                **context["proposedAssertion"],
            }
        ]
        assert {k: unpack(v) for k, v in state["records"].items()} == original_sources(case)
        issued = {k: unpack(state[k + "_bytes"]) for k in ["context", "policy", "proof", "snapshot"]}
        for role in issued:
            with pytest.raises(CaptureRefused, match="artifact bytes"):
                read_handoff(observer, ticket, {**issued, role: issued[role] + b" "})
        read_handoff(observer, ticket, issued)
        folder = tmp_path / "captured-submission"
        folder.mkdir()
        (folder / "attempt-selection.json").write_bytes(observed.pop("selectionBytes"))
        (folder / "intent.json").write_bytes(observed.pop("intent"))
        (folder / "proposed.json").write_bytes(observed.pop("proposed"))
        (folder / "owner-inputs.json").write_bytes(json_bytes(owners))
        (folder / "observation.json").write_bytes(json_bytes(observed))


def test_rollback_caught_failure_and_wrong_binding(harness, authority, storage):
    with psycopg.connect(storage, autocommit=True) as observer:
        before = counts(observer, authority.tenant_id)
        for cause in ("caller", "duplicate", "foreign-attempt", "foreign-unit"):
            ticket = register(observer, authority.tenant_id)
            with pytest.raises((CaptureRefused, RuntimeError)):
                with harness.manager.submission(harness.principal, storage, ticket) as (session, unit):
                    session.capture(unit, ticket)
                    if cause == "caller":
                        raise RuntimeError("caller abandoned after capture")
                    with pytest.raises(CaptureRefused):
                        session.capture(
                            object() if cause == "foreign-unit" else unit,
                            replace(ticket, id=uuid4()) if cause == "foreign-attempt" else ticket,
                        )
            assert not observer.execute(
                "SELECT FROM claim_evidence.observation WHERE id=%s", (ticket.id,)
            ).fetchall()
            assert observer.execute(
                "SELECT status FROM claim_evidence.attempt WHERE id=%s", (ticket.id,)
            ).fetchone() == ("aborted",)
            with pytest.raises(CaptureRefused, match="No completed"):
                read_handoff(observer, ticket)
        assert counts(observer, authority.tenant_id) == before


def test_foreign_tenant_and_thread(harness, authority, storage):
    with psycopg.connect(storage, autocommit=True) as observer:
        other = register(observer, authority.other_tenant_id)
        with pytest.raises(CaptureRefused, match="tenant or lease"):
            with harness.manager.submission(harness.principal, storage, other):
                pytest.fail("foreign tenant entered capture")
        ticket = register(observer, authority.tenant_id)
        with harness.manager.submission(harness.principal, storage, ticket) as (session, unit):
            with ThreadPoolExecutor(1) as pool, pytest.raises(CaptureRefused, match="Foreign-thread"):
                pool.submit(session.capture, unit, ticket).result(timeout=3)
            session.capture(unit, ticket)
        with pytest.raises(CaptureRefused, match="No completed"):
            read_handoff(observer, replace(ticket, tenant=other.tenant))
        assert read_handoff(observer, ticket)["tenant"] == str(ticket.tenant)


def test_lost_commit_reply_withholds_custody(harness, authority, storage, monkeypatch):
    with psycopg.connect(storage, autocommit=True) as observer:
        ticket = register(observer, authority.tenant_id)
        before = counts(observer, ticket.tenant)
        lose_commit_reply(monkeypatch, harness)
        with pytest.raises(TenantBoundaryError) as failure:
            with harness.manager.submission(harness.principal, storage, ticket) as (session, unit):
                session.capture(unit, ticket)
        assert failure.value.outcome is TenantBoundaryOutcome.FINALIZATION_UNKNOWN
        assert observer.execute(
            "SELECT status FROM claim_evidence.attempt WHERE id=%s", (ticket.id,)
        ).fetchone() == ("unknown",)
        assert observer.execute(
            "SELECT count(*) FROM claim_evidence.observation WHERE id=%s", (ticket.id,)
        ).fetchone() == (1,)
        with pytest.raises(CaptureRefused, match="No completed"):
            read_handoff(observer, ticket)
        assert counts(observer, ticket.tenant) == before


def test_stale_binding_nonce_refuses_the_open_lease(harness, authority, storage, monkeypatch):
    with psycopg.connect(storage, autocommit=True) as observer:
        ticket = register(observer, authority.tenant_id)
        with pytest.raises(CaptureRefused, match="nonce changed"):
            with harness.manager.submission(harness.principal, storage, ticket) as (session, unit):
                stale = replace(unit.binding, capability_nonce=uuid4())
                with monkeypatch.context() as patch:
                    patch.setattr(type(unit), "binding", property(lambda self: stale))
                    session.capture(unit, ticket)
        with pytest.raises(CaptureRefused, match="No completed"):
            read_handoff(observer, ticket)


@pytest.mark.parametrize("kind", ["source", "absence", "set"])
def test_writer_waits_until_release(kind, harness, authority, storage):
    case = selection()
    ref = {"source": case["intentRef"], "absence": case["assertionId"], "set": case["set"]["key"]}[kind]
    tenant = authority.tenant_id
    with psycopg.connect(storage, autocommit=True) as observer, psycopg.connect(storage) as writer:
        ticket = register(observer, tenant)
        writer.execute("SET LOCAL statement_timeout='10s'")

        def change():
            # The fixture writer must take the conflicting versioned guard before changing this fact.
            writer.execute(
                "UPDATE claim_evidence.guard SET version=version+1 WHERE tenant=%s AND key=%s",
                (tenant, kind + ":" + ref),
            )
            if kind == "source":
                return writer.execute(
                    "UPDATE claim_evidence.source SET revision='next' WHERE tenant=%s AND ref=%s",
                    (tenant, ref),
                ).rowcount
            if kind == "absence":
                return writer.execute(
                    "INSERT INTO claim_evidence.claim_id VALUES (%s,%s)", (tenant, ref)
                ).rowcount
            return writer.execute(
                "INSERT INTO claim_evidence.member VALUES (%s,%s,100,%s)", (tenant, ref, case["intentRef"])
            ).rowcount

        with ThreadPoolExecutor(1) as pool:
            with harness.manager.submission(harness.principal, storage, ticket) as (session, unit):
                pending = pool.submit(change)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    (blockers,) = observer.execute(
                        "SELECT pg_blocking_pids(%s)", (writer.info.backend_pid,)
                    ).fetchone()
                    if session.pid in blockers:
                        break
                    time.sleep(0.01)
                assert session.pid in blockers and not pending.done()
                session.capture(unit, ticket)
            assert pending.result(timeout=5) == 1
        writer.rollback()
        assert read_handoff(observer, ticket)["protection"] == "COOPERATING_FIXTURE_WRITERS"


def test_refuse_changed_originals_and_missing_guard(harness, authority, storage):
    tenant, case = authority.tenant_id, selection()
    with psycopg.connect(storage, autocommit=True) as observer:
        for label, table, key, column in [
            ("Source revision", "source", case["intentRef"], "revision"),
            ("Source bytes", "source", case["assertionId"], "body"),
            ("guard is unavailable", "guard", "set:" + case["set"]["key"], "key"),
        ]:
            ticket = register(observer, tenant)
            ref_column = "key" if table == "guard" else "ref"
            # These are fixed fixture columns. Restore the original after the refusal.
            target = sql.SQL("claim_evidence.{}").format(sql.Identifier(table))
            field, ref = sql.Identifier(column), sql.Identifier(ref_column)
            (old,) = observer.execute(
                sql.SQL("SELECT {} FROM {} WHERE tenant=%s AND {}=%s").format(field, target, ref),
                (tenant, key),
            ).fetchone()
            new = old + (b" " if isinstance(old, bytes) else ":changed")
            update = sql.SQL("UPDATE {} SET {}=%s WHERE tenant=%s AND {}=%s").format(target, field, ref)
            observer.execute(update, (new, tenant, key))
            try:
                with pytest.raises(CaptureRefused, match=label):
                    with harness.manager.submission(harness.principal, storage, ticket):
                        pytest.fail("changed source or missing guard was accepted")
            finally:
                observer.execute(update, (old, tenant, new if column == "key" else key))
            with pytest.raises(CaptureRefused, match="No completed"):
                read_handoff(observer, ticket)


def test_saved_assertion_act_belongs_to_another_submission():
    case = selection()
    records = original_sources(case)
    owners = owner_arguments(case["ownerArguments"], records)
    with ZipFile(FIXTURES / "unmatched-act.zip") as archive:
        rejected = archive.read("act-inputs.json")
    assert raw_hash(rejected) == "49894b5744de8214707c216063083c7cbc734fa6c7289c616b82836501150b9f"
    with pytest.raises(CaptureRefused, match="Assertion act differs"):
        check_owner_subject(
            case,
            {**owners, "act": json.loads(rejected)},
            records[case["intentRef"]],
            records[case["assertionId"]],
        )


def test_prestart_lock_transfers_to_the_bound_backend(harness, authority, storage, monkeypatch):
    native = collector.lock_guards
    key = "absence:" + selection()["assertionId"]
    holders = []
    with psycopg.connect(storage, autocommit=True) as observer:
        ticket = register(observer, authority.tenant_id)

        def acquire_and_probe(connection, tenant, case):
            native(connection, tenant, case)
            with pytest.raises(psycopg.errors.LockNotAvailable):
                observer.execute(
                    "SELECT key FROM claim_evidence.guard WHERE tenant=%s AND key=%s FOR UPDATE NOWAIT",
                    (tenant, key),
                )
            holders.append(connection.info.backend_pid)

        monkeypatch.setattr(collector, "lock_guards", acquire_and_probe)
        with harness.manager.submission(harness.principal, storage, ticket) as (session, unit):
            assert len(holders) == 2 and holders[0] != holders[1] == session.pid
            with pytest.raises(psycopg.errors.LockNotAvailable):
                observer.execute(
                    "SELECT key FROM claim_evidence.guard WHERE tenant=%s AND key=%s FOR UPDATE NOWAIT",
                    (ticket.tenant, key),
                )
            session.capture(unit, ticket)
        assert observer.execute(
            "SELECT key FROM claim_evidence.guard WHERE tenant=%s AND key=%s FOR UPDATE NOWAIT",
            (ticket.tenant, key),
        ).fetchone() == (key,)


def test_incorrect_set_or_authorization_refuses_the_handoff(harness, authority, storage):
    case = selection()
    tenant, set_key = authority.tenant_id, case["set"]["key"]
    with psycopg.connect(storage, autocommit=True) as db:
        for change in ("extra-member", "missing-member", "different-authorization"):
            ticket = register(db, tenant)
            if change == "extra-member":
                db.execute(
                    "INSERT INTO claim_evidence.member VALUES (%s,%s,100,%s)",
                    (tenant, set_key, case["intentRef"]),
                )
            elif change == "missing-member":
                db.execute(
                    "DELETE FROM claim_evidence.member WHERE tenant=%s AND set_key=%s AND position=0",
                    (tenant, set_key),
                )
            else:
                result_ref = case["ownerArguments"]["authorization"]["source_bytes"]["RESULT"][
                    "originalRef"
                ]
                (old,) = db.execute(
                    "SELECT body FROM claim_evidence.source WHERE tenant=%s AND ref=%s",
                    (tenant, result_ref),
                ).fetchone()
                altered = json.loads(old)
                altered["projection"]["selectedPath"]["authoritySubjectPartyRef"] = "party:fixture:other"
                db.execute(
                    "UPDATE claim_evidence.source SET body=%s WHERE tenant=%s AND ref=%s",
                    (json_bytes(altered), tenant, result_ref),
                )
            try:
                with pytest.raises(CaptureRefused, match="membership differs|Source bytes differ"):
                    with harness.manager.submission(harness.principal, storage, ticket):
                        pytest.fail("A substituted observation was accepted")
            finally:
                if change == "extra-member":
                    db.execute(
                        "DELETE FROM claim_evidence.member WHERE tenant=%s AND set_key=%s AND position=100",
                        (tenant, set_key),
                    )
                elif change == "missing-member":
                    db.execute(
                        "INSERT INTO claim_evidence.member VALUES (%s,%s,0,%s)",
                        (tenant, set_key, case["set"]["members"][0]),
                    )
                else:
                    db.execute(
                        "UPDATE claim_evidence.source SET body=%s WHERE tenant=%s AND ref=%s",
                        (old, tenant, result_ref),
                    )
            assert db.execute(
                "SELECT status FROM claim_evidence.attempt WHERE id=%s", (ticket.id,)
            ).fetchone() == ("refused",)
            with pytest.raises(CaptureRefused, match="No completed"):
                read_handoff(db, ticket)
