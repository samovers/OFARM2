"""One call-local physical observation; no retry or logical-outcome authority."""
from __future__ import annotations

import time
from contextlib import suppress
from dataclasses import astuple, dataclass, replace
from datetime import datetime
from threading import Event
from typing import TYPE_CHECKING
from uuid import UUID

from psycopg.pq import TransactionStatus

from .postgres_wait import checkpoint, wait
from .tenant_capability_issuer import CapabilityMintError

if TYPE_CHECKING:
    from .tenant_uow import GovernedWriteBatch


@dataclass(frozen=True, slots=True)
class PhysicalObservation:
    physical_status: str = "UNKNOWN"
    batch_observation: str = "UNAVAILABLE"
    original_batch: GovernedWriteBatch | None = None
    observed_batch: tuple[UUID, str, str, str, str, str, str, int, datetime] | None = None
    raw_status: str | None = None
    status_received: bool = False
    integrity_problem: str | None = None
    observer_failure: str | None = None
    cleanup: str = "NOT_ACQUIRED"


class _BoundedTransaction:
    """Borrow one owned lease, retaining psycopg's query/result machinery."""

    def __init__(self, connection, cancel_event):
        self.connection = connection
        self.cancel_event = cancel_event
        self.cursor = None

    def close(self):
        cursor, self.cursor = self.cursor, None
        if cursor is not None:
            cursor.close()

    def _wait(self, generator):
        try:
            return wait(
                generator, lambda: self.connection.pgconn.socket,
                time.monotonic() + 2.0, self.cancel_event,
            )
        except BaseException as failure:
            try:
                if not self.connection.closed:
                    self.connection.close()
            except BaseException:
                if isinstance(failure, Exception):
                    raise
            raise

    def execute(self, query, params=None):
        self.close()
        self.cursor = self.connection.cursor()
        with self.connection.lock:
            self._wait(self.cursor._execute_gen(query, params, prepare=False))
        return self.cursor

    def command(self, query):
        self.close()
        with self.connection.lock:
            self._wait(self.connection._exec_command(query))

    def rollback(self):
        self.close()
        with self.connection.lock:
            self._wait(self.connection._rollback_gen())


def check_tenant_connection(connection) -> None:
    """Same empty checkout probe, with a finite client transport wait."""
    transaction = _BoundedTransaction(connection, None)
    failure = None
    try:
        autocommit = connection.autocommit
        connection.autocommit = True
        transaction.execute("")
    except BaseException as error:
        failure = error
    try:
        transaction.close()
        if failure is None and not connection.closed:
            connection.autocommit = autocommit
    except BaseException as error:
        if failure is None or isinstance(failure, Exception):
            failure = error
    if failure is not None:
        try:
            if not connection.closed:
                connection.close()
        except BaseException as error:
            if isinstance(failure, Exception):
                failure = error
        # The pinned pool returns Exception failures itself, but not process control.
        if not isinstance(failure, Exception):
            try:
                connection._pool.putconn(connection)
            finally:
                raise failure
        raise failure


def _combine(observation: PhysicalObservation, rows) -> PhysicalObservation:
    if not rows:
        return replace(observation, batch_observation="ABSENT_AT_OBSERVATION")
    expected = astuple(observation.original_batch)
    # The query returns xid8 as text, just as the original allocator does.
    expected = (*expected[:2], str(expected[2]), *expected[3:])
    if len(rows) == 1:
        row = rows[0]
        if (
            type(row) is not tuple or len(row) != 9
            or any(type(value) is not type(model) for value, model in zip(row, expected))
        ):
            return replace(observation, observer_failure="BATCH_UNAVAILABLE")
        observation = replace(observation, observed_batch=row)
    if len(rows) != 1 or rows[0] != expected:
        return replace(
            observation, physical_status="UNKNOWN", batch_observation="CONFLICT",
            integrity_problem="BATCH_DIFFERS",
        )
    if observation.raw_status == "aborted":
        return replace(
            observation, physical_status="UNKNOWN",
            batch_observation="MATCHING_COMMITTED", integrity_problem="STATUS_CONFLICT",
        )
    return replace(
        observation, physical_status="COMMITTED", batch_observation="MATCHING_COMMITTED",
    )


def _read_outcome(transaction, observation):
    batch = observation.original_batch
    row = transaction.execute(
        "SELECT pg_catalog.pg_xact_status(%s::pg_catalog.xid8)",
        (str(batch.full_xid),),
    ).fetchall()
    if (
        len(row) != 1 or type(row[0]) is not tuple or len(row[0]) != 1
        or (row[0][0] is not None and type(row[0][0]) is not str)
        or row[0][0] not in (None, "in progress", "committed", "aborted")
    ):
        raise ValueError("physical status unavailable")
    raw_status = row[0][0]
    return replace(
        observation, raw_status=raw_status, status_received=True,
        physical_status="ABORTED" if raw_status == "aborted" else "UNKNOWN",
    )


def _read_batch(transaction, observation):
    batch = observation.original_batch
    rows = transaction.execute(
        """
        SELECT tenant_id, batch_id, full_xid::pg_catalog.text,
               authenticated_principal_ref, governed_operation,
               request_id, runtime_bundle_digest, knowledge_position, created_at
        FROM ofarm.governed_write_batch WHERE tenant_id = %s AND full_xid = %s::pg_catalog.xid8
        """,
        (batch.tenant_id, str(batch.full_xid)),
    ).fetchall()
    return _combine(observation, rows)


def _cleanup(pool, connection, transaction, observation):
    failure = None
    try:
        if connection.closed or transaction is None or transaction.cancel_event.is_set():
            raise RuntimeError("observer cleanup unavailable")
        transaction.rollback()
        if connection.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError("observer did not finish idle")
    except BaseException:
        failure = "CLEANUP_UNAVAILABLE"
        if transaction is not None:
            transaction.cancel_event.set()
    finally:
        try:
            if transaction is not None:
                transaction.close()
        except BaseException:
            failure = "CLEANUP_UNAVAILABLE"
            if transaction is not None:
                transaction.cancel_event.set()
        if failure and not connection.closed:
            with suppress(BaseException):
                connection.close()
        disposition = "DISCARDED" if connection.closed else "RETURNED"
        try:
            pool.putconn(connection)
        except BaseException:
            if not connection.closed:
                with suppress(BaseException):
                    connection.close()
            disposition = "RETURN_FAILED"
            failure = "CLEANUP_UNAVAILABLE"
    return replace(
        observation, cleanup=disposition,
        observer_failure=observation.observer_failure or failure,
    )


def observe_physical_outcome(pool, bind, principal, capture) -> PhysicalObservation:
    """Observe once after the original lease was returned; P1 is required."""
    batch = capture[0][1] if capture else None
    observation = PhysicalObservation(original_batch=batch)
    if not capture or capture[0][2] is not True:
        return replace(observation, observer_failure="RECOVERY_UNAVAILABLE")
    original_binding = capture[0][0]
    cancel_event = Event()
    connection = transaction = None
    stage = "CHECKOUT_UNAVAILABLE"
    try:
        connection = pool.getconn(timeout=0.1)
        checkpoint(time.monotonic() + 2.0, cancel_event)
        if connection.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError("observer lease is not idle")
        transaction = _BoundedTransaction(connection, cancel_event)
        stage = "BINDING_REFUSED"
        transaction.command("BEGIN ISOLATION LEVEL READ COMMITTED")
        transaction.execute(
            "SELECT pg_catalog.set_config('statement_timeout', '2000', true), "
            "pg_catalog.set_config('lock_timeout', '500', true)"
        )
        binding = bind(
            transaction, principal, cancel_event=cancel_event,
            deadline_monotonic=time.monotonic() + 5.0,
        )
        checkpoint(time.monotonic() + 2.0, cancel_event)
        if astuple(binding)[:14] != astuple(original_binding)[:14]:
            raise ValueError("original binding differs")
        stage = "STATUS_UNAVAILABLE"
        observation = _read_outcome(transaction, observation)
        stage = "BATCH_UNAVAILABLE"
        observation = _read_batch(transaction, observation)
    except CapabilityMintError:
        cancel_event.set()
        observation = replace(observation, observer_failure="CAPABILITY_REFUSED")
    except BaseException as failure:
        stopped = cancel_event.is_set() or not isinstance(failure, Exception)
        cancel_event.set()
        observation = replace(observation, observer_failure="CANCELLED" if stopped else stage)
    finally:
        if connection is not None:
            observation = _cleanup(pool, connection, transaction, observation)
    return observation
