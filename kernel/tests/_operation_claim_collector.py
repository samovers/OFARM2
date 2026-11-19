"""Test-only storage observer on one live tenant lease. All writes are to fixture custody."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
import json
import threading
from uuid import UUID, uuid4

import psycopg

from kernel.tenant_uow import TenantBoundaryError, TenantBoundaryOutcome, TenantUnitOfWorkManager
from kernel.tests._operation_claim_specimen import (
    CaptureRefused,
    SELECTION_HASH,
    binding,
    check_owner_subject,
    json_bytes,
    original,
    owner_arguments,
    raw_hash,
    selection,
    unpack,
)
from kernel.tests._operation_claim_state import (
    artifact_ref,
    guard_policy,
    state_arguments,
    storage_originals,
)


@dataclass(frozen=True)
class Attempt:
    tenant: UUID
    id: UUID


@dataclass(frozen=True)
class Observation:
    rows: dict
    guards: dict
    members: tuple
    present: bool


def guard_keys(case):
    return sorted(
        ["source:" + ref for ref in case["sources"]]
        + ["absence:" + case["assertionId"], "set:" + case["set"]["key"]]
    )


def registration(attempt, case):
    return json_bytes(
        {
            "tenant": str(attempt.tenant),
            "attempt": str(attempt.id),
            "submissionSelectionSha256": SELECTION_HASH,
            "command": case["command"],
            "actionClass": case["action"],
            "proposedId": case["assertionId"],
            "guardKeys": guard_keys(case),
            "guardPolicySha256": raw_hash(json_bytes(guard_policy(attempt))),
            "artifactRefs": {
                r: artifact_ref(attempt, r) for r in ("context", "policy", "snapshot", "proof")
            },
        }
    )


def register(controller, tenant):
    """Independent test setup chooses the ticket and artifact roles before binding a lease."""
    attempt = Attempt(tenant, uuid4())
    controller.execute(
        "INSERT INTO claim_evidence.attempt (tenant, id, selection) VALUES (%s,%s,%s)",
        (tenant, attempt.id, registration(attempt, selection())),
    )
    return attempt


def lock_guards(db, tenant, case):
    keys = guard_keys(case)
    rows = db.execute(
        """SELECT key FROM claim_evidence.guard WHERE tenant=%s AND key=ANY(%s)
                         ORDER BY key FOR SHARE NOWAIT""",
        (tenant, keys),
    ).fetchall()
    if {r[0] for r in rows} != set(keys):
        raise CaptureRefused("A required source, absence or membership guard is unavailable")


def observe(db, tenant, case):
    records = db.execute(
        """SELECT ref,revision,body,xmin::text FROM claim_evidence.source
                            WHERE tenant=%s AND ref=ANY(%s)""",
        (tenant, list(case["sources"])),
    ).fetchall()
    rows = {ref: (revision, raw, version) for ref, revision, raw, version in records}
    if rows.keys() != case["sources"].keys():
        raise CaptureRefused("A selected source is unavailable")
    for ref, (revision, raw, _) in rows.items():
        selected = case["sources"][ref]
        if revision != selected["revision"]:
            raise CaptureRefused("Source revision differs: " + ref)
        if raw_hash(raw) != selected["sha256"]:
            raise CaptureRefused("Source bytes differ: " + ref)
    guards = dict(
        db.execute(
            """SELECT key,xmin::text FROM claim_evidence.guard
                               WHERE tenant=%s AND key=ANY(%s)""",
            (tenant, guard_keys(case)),
        ).fetchall()
    )
    members = tuple(
        r[0]
        for r in db.execute(
            """SELECT ref FROM claim_evidence.member
                         WHERE tenant=%s AND set_key=%s ORDER BY position""",
            (tenant, case["set"]["key"]),
        )
    )
    if members != tuple(case["set"]["members"]):
        raise CaptureRefused("Selected membership differs")
    (present,) = db.execute(
        """SELECT EXISTS (SELECT FROM claim_evidence.claim_id WHERE tenant=%s AND id=%s)
                           OR EXISTS (SELECT FROM ofarm.kernel_record WHERE tenant_id=%s AND record_id=%s)""",
        (tenant, case["assertionId"], tenant, case["assertionId"]),
    ).fetchone()
    if present:
        raise CaptureRefused("The proposed assertion ID already exists")
    return Observation(rows, guards, members, present)


class _Session:
    def __init__(self, db, unit, attempt, case, start, token, controller_pid):
        self._connection, self.unit, self.attempt, self.case = db, unit, attempt, case
        self.start, self.token = start, token
        self.controller_pid = controller_pid
        self.thread = threading.current_thread()
        self.active = True
        self.staged = False
        self.refused = False
        self.pid, self.xid, self.started, isolation = db.execute(
            "SELECT pg_backend_pid(), pg_current_xact_id()::text, transaction_timestamp(), current_setting('transaction_isolation')"
        ).fetchone()
        if isolation != "read committed":
            raise CaptureRefused("Unexpected transaction isolation")

    def _live(self, unit, attempt):
        if not self.active or threading.current_thread() is not self.thread:
            raise CaptureRefused("Closed or foreign-thread capture")
        if unit is not self.unit or attempt != self.attempt or unit.binding.tenant_id != attempt.tenant:
            raise CaptureRefused("Wrong tenant, unit or attempt")
        pid, xid, now, nonce = (
            self._connection.execute("""SELECT pg_backend_pid(), pg_current_xact_id()::text,
            clock_timestamp(), capability_nonce FROM ofarm.current_tenant_context()""").fetchone()
        )
        if (pid, xid, nonce) != (self.pid, self.xid, unit.binding.capability_nonce):
            raise CaptureRefused("Lease or binding nonce changed")
        if now >= self.started + timedelta(seconds=60):
            raise CaptureRefused("The fixture attempt expired")

    def capture(self, unit, attempt):
        if threading.current_thread() is not self.thread:
            raise CaptureRefused("Foreign-thread capture")
        try:
            self._live(unit, attempt)
            if self.staged or self.refused:
                raise CaptureRefused("Attempt already used or refused")
            observed = observe(self._connection, attempt.tenant, self.case)
            if observed != self.start:
                raise CaptureRefused("Protected versions changed since the start")
            rows = {ref: entry[1] for ref, entry in observed.rows.items()}
            owners = owner_arguments(self.case["ownerArguments"], rows)
            intent, proposed = rows[self.case["intentRef"]], rows[self.case["assertionId"]]
            missing = check_owner_subject(self.case, owners, intent, proposed)
            artifacts = storage_originals(
                self.case, attempt, self.start, observed, self.token, self.started
            )
            # The only insert is an unpublished conformance observation in the disposable schema.
            evidence = {
                "tenant": str(attempt.tenant),
                "attempt": str(attempt.id),
                "backendPid": self.pid,
                "prestartControllerPid": self.controller_pid,
                "snapshotScope": "SELECTED_FIXTURE_KEYS_PROTECTED_BEFORE_TENANT_TRANSACTION",
                "transactionIsolation": "READ COMMITTED",
                "fullXid": self.xid,
                "protection": "COOPERATING_FIXTURE_WRITERS",
                "bindingNonce": str(unit.binding.capability_nonce),
                "missingOwnerInputs": missing,
                "captureDisposition": "MISSING_OWNER_ORIGINALS"
                if missing
                else "SELECTED_ORIGINALS_CAPTURED",
                "artifacts": {k: original(v) for k, v in artifacts.items()},
                "records": {ref: original(raw) for ref, raw in rows.items()},
            }
            self._connection.execute(
                "INSERT INTO claim_evidence.observation (tenant,id,body) VALUES (%s,%s,%s)",
                (attempt.tenant, attempt.id, json_bytes(evidence)),
            )
            self.staged = True
        except BaseException:
            self.refused = True
            raise

    def finish(self):
        self._live(self.unit, self.attempt)
        if (
            self.refused
            or not self.staged
            or observe(self._connection, self.attempt.tenant, self.case) != self.start
        ):
            raise CaptureRefused("Capture refused, unfinished or changed before finalization")


class FixtureEvidenceManager(TenantUnitOfWorkManager):
    """The production factory returns no claim operation, including in this test subclass."""

    def __init__(self, pool, minter):
        super().__init__(pool, minter)
        self._fixture = threading.local()

    def _bind_claim_operation(self, connection, binding):
        if getattr(self._fixture, "opening", False):
            self._fixture.lease = (connection, binding)
        return None

    @contextmanager
    def submission(self, principal, controller_dsn, ticket):
        case = selection()
        if getattr(self._fixture, "opening", False):
            raise CaptureRefused("Nested evidence capture")
        with psycopg.connect(controller_dsn, autocommit=True) as controller:
            row = controller.execute(
                """UPDATE claim_evidence.attempt SET status='started'
                WHERE tenant=%s AND id=%s AND status='registered' AND selection=%s RETURNING id""",
                (ticket.tenant, ticket.id, registration(ticket, case)),
            ).fetchone()
            if not row:
                raise CaptureRefused("Unknown, mismatched or spent attempt selection")
            self._fixture.opening = True
            entered = False
            try:
                controller.execute("BEGIN")
                lock_guards(controller, ticket.tenant, case)
                start = observe(controller, ticket.tenant, case)
                (token,) = controller.execute("SELECT pg_current_snapshot()::text").fetchone()
                with self.unit_of_work(principal) as unit:
                    entered = True
                    db, live_binding = self._fixture.lease
                    if live_binding is not unit.binding or unit.binding.tenant_id != ticket.tenant:
                        raise CaptureRefused("Transaction tenant or lease differs")
                    lock_guards(db, ticket.tenant, case)
                    controller.execute("COMMIT")
                    handle = _Session(db, unit, ticket, case, start, token, controller.info.backend_pid)
                    try:
                        yield handle, unit
                        handle.finish()
                    finally:
                        handle.active = False
            except BaseException as failure:
                status = "aborted" if entered else "refused"
                if (
                    isinstance(failure, TenantBoundaryError)
                    and failure.outcome is TenantBoundaryOutcome.FINALIZATION_UNKNOWN
                ):
                    status = "unknown"
                try:
                    controller.rollback()
                    controller.execute(
                        """UPDATE claim_evidence.attempt SET status=%s
                               WHERE tenant=%s AND id=%s AND status='started'""",
                        (status, ticket.tenant, ticket.id),
                    )
                except psycopg.Error as report_error:
                    failure.add_note(
                        "The controller could not record finalization: " + type(report_error).__name__
                    )
                raise
            finally:
                self._fixture.opening = False
                self._fixture.lease = None
            # A rollback, unknown COMMIT or failure publishing the custody row cannot release a handoff.
            controller.execute(
                """UPDATE claim_evidence.attempt SET status='completed'
                       WHERE tenant=%s AND id=%s AND status='started'""",
                (ticket.tenant, ticket.id),
            )


def read_handoff(observer, ticket, offered=None):
    """Fetch sealed originals on an independent connection, then compare any offered copies."""
    row = observer.execute(
        """SELECT a.selection,o.body FROM claim_evidence.attempt a
        JOIN claim_evidence.observation o USING (tenant,id)
        WHERE a.tenant=%s AND a.id=%s AND a.status='completed'""",
        (ticket.tenant, ticket.id),
    ).fetchone()
    case = selection()
    if not row or row[0] != registration(ticket, case):
        raise CaptureRefused("No completed handoff for the selected attempt")
    selected = json.loads(row[0])
    evidence = json.loads(row[1])
    artifacts = {role: unpack(enc) for role, enc in evidence.pop("artifacts").items()}
    if offered is not None and offered != artifacts:
        raise CaptureRefused("Offered protected artifact bytes differ from custody")
    if (
        set(artifacts) != selected["artifactRefs"].keys()
        or any(
            json.loads(raw)[role + "Id"] != selected["artifactRefs"][role]
            for role, raw in artifacts.items()
        )
        or raw_hash(artifacts["policy"]) != selected["guardPolicySha256"]
    ):
        raise CaptureRefused("Custody roles or independently selected guard policy differ")
    records = {ref: unpack(enc) for ref, enc in evidence.pop("records").items()}
    if (evidence["tenant"], evidence["attempt"]) != (str(ticket.tenant), str(ticket.id)):
        raise CaptureRefused("Stored observation belongs to a different attempt")
    if records.keys() != case["sources"].keys() or any(
        raw_hash(raw) != case["sources"][ref]["sha256"] for ref, raw in records.items()
    ):
        raise CaptureRefused("Custody originals differ from the selected byte inventory")
    owners = owner_arguments(case["ownerArguments"], records)
    proof_pin = binding(selected["artifactRefs"]["proof"], json.loads(artifacts["proof"]))
    owners["state"] = state_arguments(artifacts, records, proof_pin)
    return {
        **evidence,
        "finalization": "COMPLETED",
        "selection": selected,
        "selectionBytes": row[0],
        "selectionSha256": raw_hash(row[0]),
        "artifactSha256": {k: raw_hash(v) for k, v in artifacts.items()},
        "intent": records[case["intentRef"]],
        "proposed": records[case["assertionId"]],
        "ownerInputs": owners,
    }
