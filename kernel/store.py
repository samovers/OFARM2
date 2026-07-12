"""The append-only truth store (M1 brief task 2).

One uniform record table for governed contract records, an explicit edge
table, a gate log, idempotency bookkeeping, and derived (recomputable)
materialization tables. Semantic law lives in the gate pipeline; this module
enforces the storage posture:

  * contract validation on every write (KERNEL.md conformance condition 1)
  * append-only at the database level (Kernel rule 1 — triggers in schema.sql)
  * payload sha256 + schema version + schema hash per record
  * references as durable edges, not JSON-path conventions
  * reachability link written in the same transaction as the commit (D3) —
    the deferred constraint trigger makes a commit without it impossible
  * draft-lane shapes (D16) land in runtime_trace, never in kernel_record
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import types
from contextlib import contextmanager

import psycopg
from psycopg.adapt import AdaptersMap
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from . import config
from .contracts import ContractRegistry, ContractViolation, sha256_of
from .runtime_bundle import (
    RuntimeBundleError,
    _require_decision_semantics,
    require_live_python_import_posture,
    require_runtime_environment_seal,
    require_store_runtime_bundle,
)
from .schema_guard import (
    SchemaGuardError,
    ensure_schema,
    hold_fingerprint_catalog_locks,
    require_exact_schema,
    require_no_temporary_schema,
    verify_static_runtime_catalog,
)

# A clean, private copy of Psycopg's adapter registry is selected at reviewed
# module import. Connections copy this context instead of the mutable public
# ``psycopg.adapters`` map, so an application-registered Dumper/Loader cannot
# receive the raw Connection during parameter adaptation.
_RETAINED_PSYCOPG_ADAPTERS = AdaptersMap(psycopg.adapters)

# Single-writer advisory-lock key (M2 G2): a stable signed-64-bit derived from
# the tenant ref. Every governed WRITE entry point (user commit + scheduled
# import) acquires this transaction-scoped lock, so a scheduled import can never
# interleave with a user commit, and concurrent structure-identity commits
# serialize (closing the D18 read-before-write race — PR #9 H1). The lock stays
# on until the freshness-vector snapshot-isolation/watermark fix (M5/L2).
_SINGLE_WRITER_LOCK_KEY = int.from_bytes(
    hashlib.sha256(config.TENANT_REF.encode()).digest()[:8], "big", signed=True)

AUTHORITATIVE_KINDS = (
    "ofarm.assertionrecord.v0.1",
    "ofarm.semanticeventenvelope.v0.1",
    "ofarm.reviewdecision.v0.1",
    "ofarm.acceptedeventconsequence.v0.1",
)

# Every governed transaction establishes these values transaction-locally
# before it reads decision data or acquires the single-writer lock.  Session
# settings remain mutable to PostgreSQL clients, but they can never influence
# an OFARM decision: the next entry point replaces them and proves the complete
# observation against the retained RuntimeBundle.
_DETERMINISTIC_SESSION_SETTINGS = (
    ("timezone", "TimeZone", "UTC"),
    ("dateStyle", "DateStyle", "ISO, MDY"),
    ("intervalStyle", "IntervalStyle", "postgres"),
    ("searchPath", "search_path", "pg_catalog, public"),
    ("sessionReplicationRole", "session_replication_role", "origin"),
    ("standardConformingStrings", "standard_conforming_strings", "on"),
    ("extraFloatDigits", "extra_float_digits", "1"),
    ("byteaOutput", "bytea_output", "hex"),
)

_ALLOWED_GOVERNED_SQL = re.compile(
    r"\A(?:SELECT|INSERT|UPDATE|DELETE|MERGE|WITH|VALUES|LOCK)\b",
    re.IGNORECASE,
)
_READ_ONLY_GOVERNED_SQL = re.compile(
    r"\A(?:SELECT|VALUES)\b",
    re.IGNORECASE,
)
_MUTATING_SETTING_FUNCTION = re.compile(
    r"\bset_config\b",
    re.IGNORECASE,
)
_PUBLIC_READ_MUTATION = re.compile(
    r"\b(?:"
    r"nextval|setval|lo_create|lo_creat|lo_import|lo_export|lo_unlink|"
    r"pg_advisory_lock|pg_advisory_xact_lock|pg_try_advisory_lock|"
    r"pg_try_advisory_xact_lock|pg_advisory_unlock|pg_advisory_unlock_all|"
    r"pg_cancel_backend|pg_terminate_backend|pg_reload_conf|"
    r"pg_rotate_logfile|pg_log_backend_memory_contexts|"
    r"pg_create_restore_point|pg_switch_wal|pg_wal_replay_pause|"
    r"pg_wal_replay_resume"
    r")\s*\(",
    re.IGNORECASE,
)
_PUBLIC_READ_LOCKING = re.compile(
    r"\bFOR\s+(?:UPDATE|NO\s+KEY\s+UPDATE|SHARE|KEY\s+SHARE)\b",
    re.IGNORECASE,
)


def _governed_query_text(query) -> str:
    if type(query) is str:
        return query
    if type(query) is bytes:
        return query.decode("utf-8")
    raise TypeError(
        "governed cursors accept only exact immutable str/bytes SQL")


def _read_only_sql_text(query) -> str:
    text = _governed_query_text(query).strip()
    if (not text or '"' in text or ";" in text
            or "--" in text or "/*" in text or "*/" in text
            or not _READ_ONLY_GOVERNED_SQL.match(text)
            or _MUTATING_SETTING_FUNCTION.search(text)
            or _PUBLIC_READ_MUTATION.search(text)
            or _PUBLIC_READ_LOCKING.search(text)
            or re.search(r"\bINTO\b", text, re.IGNORECASE)):
        raise RuntimeError(
            "public Store connection access is read-only and accepts only "
            "unambiguous SELECT/VALUES SQL")
    return text


class _TransactionIntegrityLatch:
    """One-way rollback-only state retained outside mutable thread locals."""

    __slots__ = ("__poisoned",)

    def __init__(self):
        object.__setattr__(
            self, "_TransactionIntegrityLatch__poisoned", False)

    def __setattr__(self, _name, _value):
        raise AttributeError("transaction integrity latch is one-way")

    def __delattr__(self, _name):
        raise AttributeError("transaction integrity latch cannot be deleted")

    @property
    def poisoned(self) -> bool:
        return self.__poisoned

    def poison(self) -> None:
        object.__setattr__(
            self, "_TransactionIntegrityLatch__poisoned", True)


class _GovernedSavepoint:
    """Expose a savepoint context without leaking the owning connection."""

    __slots__ = (
        "__connection", "__store", "__token", "__integrity",
        "__transaction", "__entered",
    )

    def __init__(self, connection, store):
        Store._require_nested_transaction_ownership(store)
        object.__setattr__(self, "_GovernedSavepoint__connection", connection)
        object.__setattr__(self, "_GovernedSavepoint__store", store)
        object.__setattr__(
            self, "_GovernedSavepoint__token",
            store._active_transaction_token)
        object.__setattr__(
            self, "_GovernedSavepoint__integrity",
            store._active_transaction_integrity)
        object.__setattr__(self, "_GovernedSavepoint__transaction", None)
        object.__setattr__(self, "_GovernedSavepoint__entered", False)

    def _require_binding(self, *, allow_inerror: bool = False) -> None:
        state = self.__store._transaction_state
        integrity = self.__store._active_transaction_integrity
        allowed_statuses = {psycopg.pq.TransactionStatus.INTRANS}
        if allow_inerror:
            allowed_statuses.add(psycopg.pq.TransactionStatus.INERROR)
        if (self.__store._active_transaction_token is not self.__token
                or self.__store._active_transaction_integrity is not
                self.__integrity
                or getattr(state, "token", None) is not self.__token
                or getattr(state, "integrity", None) is not self.__integrity
                or getattr(state, "ownerThread", None) != threading.get_ident()
                or getattr(state, "connection", None) is not self.__connection
                or type(getattr(state, "depth", None)) is not int
                or state.depth <= 0
                or type(integrity) is not _TransactionIntegrityLatch
                or integrity.poisoned is not False
                or self.__connection.info.transaction_status not in
                allowed_statuses):
            Store._mark_transaction_integrity_violation(self.__store)
            raise RuntimeError(
                "governed savepoint escaped its transaction ownership")

    def __enter__(self):
        _RETAINED_SAVEPOINT_REQUIRE_BINDING(self)
        transaction = self.__connection.transaction()
        object.__setattr__(
            self, "_GovernedSavepoint__transaction", transaction)
        try:
            transaction.__enter__()
            object.__setattr__(self, "_GovernedSavepoint__entered", True)
            return self
        except BaseException:
            object.__setattr__(self, "_GovernedSavepoint__transaction", None)
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        if not self.__entered or self.__transaction is None:
            raise RuntimeError("governed savepoint was not entered")
        try:
            _RETAINED_SAVEPOINT_REQUIRE_BINDING(
                self, allow_inerror=exc_type is not None)
        except BaseException as guard_error:
            try:
                self.__transaction.__exit__(
                    type(guard_error), guard_error, guard_error.__traceback__)
            finally:
                object.__setattr__(self, "_GovernedSavepoint__entered", False)
                object.__setattr__(self, "_GovernedSavepoint__transaction", None)
            raise
        try:
            return self.__transaction.__exit__(
                exc_type, exc_value, traceback)
        finally:
            object.__setattr__(self, "_GovernedSavepoint__entered", False)
            object.__setattr__(self, "_GovernedSavepoint__transaction", None)


class _ConnectionInfoView:
    """Expose transaction state without leaking libpq's command channel."""

    __slots__ = ("__info",)

    def __init__(self, info):
        object.__setattr__(self, "_ConnectionInfoView__info", info)

    @property
    def transaction_status(self):
        return self.__info.transaction_status


class _ExternalConnectionTransaction:
    """Serialize an explicit maintenance transaction against Store work."""

    __slots__ = ("__store", "__transaction", "__entered")

    def __init__(self, connection, store):
        object.__setattr__(self, "_ExternalConnectionTransaction__store", store)
        object.__setattr__(
            self, "_ExternalConnectionTransaction__transaction",
            connection.transaction(),
        )
        object.__setattr__(self, "_ExternalConnectionTransaction__entered", False)

    def __enter__(self):
        lock = self.__store._transaction_lock
        lock.acquire()
        try:
            if (self.__store._active_transaction_token is not None
                    or Store._transaction_depth(self.__store)):
                Store._mark_transaction_integrity_violation(self.__store)
                raise RuntimeError(
                    "direct connection transactions are forbidden during "
                    "governed work")
            self.__transaction.__enter__()
            object.__setattr__(
                self, "_ExternalConnectionTransaction__entered", True)
            return self
        except BaseException:
            lock.release()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return self.__transaction.__exit__(
                exc_type, exc_value, traceback)
        finally:
            if self.__entered:
                object.__setattr__(
                    self, "_ExternalConnectionTransaction__entered", False)
                self.__store._transaction_lock.release()


class _GovernedConnectionView:
    """A dynamic connection facade that cannot be retained around a guard."""

    __slots__ = (
        "__connection", "__store", "__governed", "__token", "__integrity",
    )

    def __init__(self, connection, store, *, governed: bool):
        object.__setattr__(
            self, "_GovernedConnectionView__connection", connection)
        object.__setattr__(self, "_GovernedConnectionView__store", store)
        object.__setattr__(self, "_GovernedConnectionView__governed", governed)
        object.__setattr__(
            self, "_GovernedConnectionView__token",
            store._active_transaction_token if governed else None)
        object.__setattr__(
            self, "_GovernedConnectionView__integrity",
            store._active_transaction_integrity if governed else None)

    def _require_governed_binding(self) -> None:
        try:
            Store._require_nested_transaction_ownership(self.__store)
            if (not self.__governed
                    or self.__store._active_transaction_token is not self.__token
                    or self.__store._active_transaction_integrity is not
                    self.__integrity):
                raise RuntimeError(
                    "governed connection facade escaped its transaction ownership")
        except BaseException:
            Store._mark_transaction_integrity_violation(self.__store)
            raise

    @property
    def info(self):
        return _ConnectionInfoView(self.__connection.info)

    def transaction(self):
        if self.__governed:
            _RETAINED_CONNECTION_REQUIRE_GOVERNED_BINDING(self)
            return _GovernedSavepoint(self.__connection, self.__store)
        raise RuntimeError(
            "public Store connection access is read-only; explicit connection "
            "transactions are private Store implementation state")

    def _reject_direct_connection_control(self, *_args, **_kwargs):
        Store._mark_transaction_integrity_violation(self.__store)
        raise RuntimeError(
            "an active governed transaction exposes no direct connection control")

    def _require_external_control(self) -> None:
        if (self.__governed
                or self.__store._active_transaction_token is not None
                or Store._transaction_depth(self.__store)
                or not self.__connection.autocommit
                or self.__connection.info.transaction_status is not
                psycopg.pq.TransactionStatus.IDLE):
            _RETAINED_CONNECTION_REJECT_CONTROL(self)

    def execute(self, query, *args, **kwargs):
        del query, args, kwargs
        Store._mark_transaction_integrity_violation(self.__store)
        raise RuntimeError(
            "public Store connection SQL is forbidden; use reviewed Store "
            "read methods")

    def cursor(self, *args, **kwargs):
        del args, kwargs
        Store._mark_transaction_integrity_violation(self.__store)
        raise RuntimeError(
            "public Store cursors are forbidden; use reviewed Store read methods")

    def commit(self) -> None:
        _RETAINED_CONNECTION_REJECT_CONTROL(self)

    def rollback(self) -> None:
        _RETAINED_CONNECTION_REJECT_CONTROL(self)

    def close(self) -> None:
        with self.__store._transaction_lock:
            _RETAINED_CONNECTION_REQUIRE_EXTERNAL_CONTROL(self)
            self.__connection.close()

    @property
    def closed(self):
        return self.__connection.closed

    @property
    def autocommit(self):
        return self.__connection.autocommit

    @autocommit.setter
    def autocommit(self, value) -> None:
        del value
        _RETAINED_CONNECTION_REJECT_CONTROL(self)


class _ExternalCursor:
    """An idle/maintenance cursor that rechecks Store ownership per use."""

    __slots__ = (
        "__cursor", "__store", "__connection", "__raw_connection",
    )

    def __init__(self, cursor, store):
        object.__setattr__(self, "_ExternalCursor__cursor", cursor)
        object.__setattr__(self, "_ExternalCursor__store", store)
        object.__setattr__(
            self, "_ExternalCursor__connection",
            _GovernedConnectionView(cursor.connection, store, governed=False),
        )
        object.__setattr__(
            self, "_ExternalCursor__raw_connection", cursor.connection)

    def _require_idle(self) -> None:
        if (self.__store._active_transaction_token is not None
                or Store._transaction_depth(self.__store)):
            Store._mark_transaction_integrity_violation(self.__store)
            raise RuntimeError(
                "a retained maintenance cursor cannot enter governed work")

    def execute(self, query, *args, **kwargs):
        with self.__store._transaction_lock:
            _RETAINED_EXTERNAL_CURSOR_REQUIRE_IDLE(self)
            statement = _RETAINED_READ_ONLY_SQL_TEXT(query)
            with self.__raw_connection.transaction():
                self.__raw_connection.execute("SET TRANSACTION READ ONLY")
                self.__cursor.execute(statement, *args, **kwargs)
            return self

    def executemany(self, query, *args, **kwargs):
        with self.__store._transaction_lock:
            _RETAINED_EXTERNAL_CURSOR_REQUIRE_IDLE(self)
            statement = _RETAINED_READ_ONLY_SQL_TEXT(query)
            with self.__raw_connection.transaction():
                self.__raw_connection.execute("SET TRANSACTION READ ONLY")
                self.__cursor.executemany(statement, *args, **kwargs)
            return self

    def fetchone(self):
        with self.__store._transaction_lock:
            _RETAINED_EXTERNAL_CURSOR_REQUIRE_IDLE(self)
            return self.__cursor.fetchone()

    def fetchmany(self, *args, **kwargs):
        with self.__store._transaction_lock:
            _RETAINED_EXTERNAL_CURSOR_REQUIRE_IDLE(self)
            return self.__cursor.fetchmany(*args, **kwargs)

    def fetchall(self):
        with self.__store._transaction_lock:
            _RETAINED_EXTERNAL_CURSOR_REQUIRE_IDLE(self)
            return self.__cursor.fetchall()

    def close(self) -> None:
        with self.__store._transaction_lock:
            self.__cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.close()

    def __iter__(self):
        return self

    def __next__(self):
        with self.__store._transaction_lock:
            _RETAINED_EXTERNAL_CURSOR_REQUIRE_IDLE(self)
            return next(self.__cursor)

    @property
    def connection(self):
        return self.__connection

    @property
    def rowcount(self):
        return self.__cursor.rowcount

    @property
    def statusmessage(self):
        return self.__cursor.statusmessage

    @property
    def description(self):
        return self.__cursor.description


class _GovernedCursor:
    """Cursor facade that cannot end its owning governed transaction."""

    __slots__ = (
        "__cursor", "__store", "__connection", "__token", "__integrity",
    )

    def __init__(self, cursor, store):
        Store._require_nested_transaction_ownership(store)
        object.__setattr__(self, "_GovernedCursor__cursor", cursor)
        object.__setattr__(self, "_GovernedCursor__store", store)
        object.__setattr__(
            self, "_GovernedCursor__token", store._active_transaction_token)
        object.__setattr__(
            self, "_GovernedCursor__integrity",
            store._active_transaction_integrity)
        object.__setattr__(
            self, "_GovernedCursor__connection",
            _GovernedConnectionView(
                cursor.connection, store, governed=True),
        )

    def _require_ownership(self) -> None:
        try:
            Store._require_nested_transaction_ownership(self.__store)
            if (self.__store._active_transaction_token is not self.__token
                    or self.__store._active_transaction_integrity is not
                    self.__integrity
                    or self.__cursor.closed):
                raise RuntimeError(
                    "governed cursor escaped its transaction ownership")
        except BaseException:
            Store._mark_transaction_integrity_violation(self.__store)
            raise

    def _require_statement(self, query, *, allow_mutation: bool = False) -> str:
        _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP(self)
        try:
            text = _RETAINED_GOVERNED_QUERY_TEXT(query).strip()
        except Exception:
            Store._mark_transaction_integrity_violation(self.__store)
            raise
        # Comments and multi-statements make a tiny transaction-control parser
        # ambiguous.  Governed SQL is generated by reviewed code, so fail
        # closed instead of trying to emulate PostgreSQL's complete lexer.
        if (not text or '"' in text
                or "--" in text or "/*" in text or "*/" in text):
            Store._mark_transaction_integrity_violation(self.__store)
            raise RuntimeError(
                "governed cursor SQL is empty, quoted, or comment-ambiguous")
        if ";" in text:
            Store._mark_transaction_integrity_violation(self.__store)
            raise RuntimeError("governed cursors reject multi-statement SQL")
        if (not _ALLOWED_GOVERNED_SQL.match(text)
                or _MUTATING_SETTING_FUNCTION.search(text)):
            Store._mark_transaction_integrity_violation(self.__store)
            raise RuntimeError(
                "governed cursors cannot execute transaction-control, DDL, "
                "or session-posture SQL")
        if (not allow_mutation
                and (not _READ_ONLY_GOVERNED_SQL.match(text)
                     or re.search(r"\bINTO\b", text, re.IGNORECASE)
                     or _PUBLIC_READ_MUTATION.search(text)
                     or _PUBLIC_READ_LOCKING.search(text))):
            Store._mark_transaction_integrity_violation(self.__store)
            raise RuntimeError(
                "public governed cursor SQL is read-only; reviewed Store "
                "writers own mutation capability")
        return text

    def execute(self, query, *args, **kwargs):
        del query, args, kwargs
        Store._mark_transaction_integrity_violation(self.__store)
        raise RuntimeError(
            "public governed cursor SQL is forbidden; reviewed Store code owns "
            "the read capability")

    def _execute_read(self, query, *args, **kwargs):
        statement = _RETAINED_GOVERNED_CURSOR_REQUIRE_STATEMENT(self, query)
        self.__cursor.execute(statement, *args, **kwargs)
        return self

    def _execute_mutation(self, query, *args, **kwargs):
        _RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR(
            self.__store, self)
        statement = _RETAINED_GOVERNED_CURSOR_REQUIRE_STATEMENT(
            self, query, allow_mutation=True)
        self.__cursor.execute(statement, *args, **kwargs)
        return self

    def executemany(self, query, *args, **kwargs):
        del query, args, kwargs
        Store._mark_transaction_integrity_violation(self.__store)
        raise RuntimeError(
            "public governed cursor SQL is forbidden; reviewed Store code owns "
            "the read capability")

    def _executemany_read(self, query, *args, **kwargs):
        statement = _RETAINED_GOVERNED_CURSOR_REQUIRE_STATEMENT(self, query)
        self.__cursor.executemany(statement, *args, **kwargs)
        return self

    def _executemany_mutation(self, query, *args, **kwargs):
        _RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR(
            self.__store, self)
        statement = _RETAINED_GOVERNED_CURSOR_REQUIRE_STATEMENT(
            self, query, allow_mutation=True)
        self.__cursor.executemany(statement, *args, **kwargs)
        return self

    def fetchone(self):
        _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP(self)
        return self.__cursor.fetchone()

    def fetchmany(self, *args, **kwargs):
        _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP(self)
        return self.__cursor.fetchmany(*args, **kwargs)

    def fetchall(self):
        _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP(self)
        return self.__cursor.fetchall()

    def __iter__(self):
        return self

    def __next__(self):
        _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP(self)
        return next(self.__cursor)

    @property
    def connection(self):
        _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP(self)
        return self.__connection

    @property
    def rowcount(self):
        _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP(self)
        return self.__cursor.rowcount

    @property
    def statusmessage(self):
        _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP(self)
        return self.__cursor.statusmessage

    @property
    def description(self):
        _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP(self)
        return self.__cursor.description


_RETAINED_GOVERNED_QUERY_TEXT = _governed_query_text
_RETAINED_GOVERNED_QUERY_TEXT_CODE = _governed_query_text.__code__
_RETAINED_READ_ONLY_SQL_TEXT = _read_only_sql_text
_RETAINED_READ_ONLY_SQL_TEXT_CODE = _read_only_sql_text.__code__
_RETAINED_SAVEPOINT_REQUIRE_BINDING = _GovernedSavepoint._require_binding
_RETAINED_CONNECTION_REJECT_CONTROL = \
    _GovernedConnectionView._reject_direct_connection_control
_RETAINED_CONNECTION_REQUIRE_GOVERNED_BINDING = \
    _GovernedConnectionView._require_governed_binding
_RETAINED_CONNECTION_REQUIRE_EXTERNAL_CONTROL = \
    _GovernedConnectionView._require_external_control
_RETAINED_EXTERNAL_CURSOR_REQUIRE_IDLE = _ExternalCursor._require_idle
_RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP = \
    _GovernedCursor._require_ownership
_RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP_CODE = \
    _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP.__code__
_RETAINED_GOVERNED_CURSOR_REQUIRE_STATEMENT = \
    _GovernedCursor._require_statement
_RETAINED_GOVERNED_CURSOR_REQUIRE_STATEMENT_CODE = \
    _RETAINED_GOVERNED_CURSOR_REQUIRE_STATEMENT.__code__
_RETAINED_GOVERNED_CURSOR_EXECUTE_READ = _GovernedCursor._execute_read
_RETAINED_GOVERNED_CURSOR_EXECUTE_READ_CODE = \
    _RETAINED_GOVERNED_CURSOR_EXECUTE_READ.__code__
_RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION = \
    _GovernedCursor._execute_mutation
_RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION_CODE = \
    _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION.__code__
_RETAINED_GOVERNED_CURSOR_EXECUTEMANY_READ = \
    _GovernedCursor._executemany_read
_RETAINED_GOVERNED_CURSOR_EXECUTEMANY_READ_CODE = \
    _RETAINED_GOVERNED_CURSOR_EXECUTEMANY_READ.__code__
_RETAINED_GOVERNED_CURSOR_EXECUTEMANY_MUTATION = \
    _GovernedCursor._executemany_mutation
_RETAINED_GOVERNED_CURSOR_EXECUTEMANY_MUTATION_CODE = \
    _RETAINED_GOVERNED_CURSOR_EXECUTEMANY_MUTATION.__code__
_RUNTIME_FACADE_TYPES = (
    _TransactionIntegrityLatch,
    _GovernedSavepoint,
    _ConnectionInfoView,
    _ExternalConnectionTransaction,
    _GovernedConnectionView,
    _ExternalCursor,
    _GovernedCursor,
)


_RUNTIME_POSTURE_VERIFIERS = (
    require_live_python_import_posture,
    require_runtime_environment_seal,
    require_store_runtime_bundle,
    _require_decision_semantics,
)
_RUNTIME_POSTURE_VERIFIER_CODES = tuple(
    verifier.__code__ for verifier in _RUNTIME_POSTURE_VERIFIERS)


def _store_callable_state(
        value: object, active: set[int] | None = None) -> tuple[object, ...]:
    if type(value) is not types.FunctionType:
        return ("IDENTITY", value)
    active = set() if active is None else active
    marker = id(value)
    if marker in active:
        return ("FUNCTION_REF", value)
    active.add(marker)
    try:
        closure = tuple(
            (cell, cell.cell_contents,
             _store_callable_state(cell.cell_contents, active)
             if type(cell.cell_contents) is types.FunctionType else None)
            for cell in (value.__closure__ or ()))
        wrapped = getattr(value, "__wrapped__", None)
        return (
            "FUNCTION", value, value.__code__, value.__defaults__,
            value.__kwdefaults__, closure,
            (_store_callable_state(wrapped, active)
             if type(wrapped) is types.FunctionType else None),
        )
    finally:
        active.remove(marker)


_STORE_CALLABLE_STATE = _store_callable_state
_STORE_CALLABLE_STATE_CODE = _store_callable_state.__code__


def _store_dispatch_snapshot() -> tuple[tuple[object, ...], ...]:
    entries = []
    for owner in (Store, *_RUNTIME_FACADE_TYPES):
        for name, value in sorted(vars(owner).items()):
            if type(value) is types.FunctionType:
                entries.append((
                    owner, name, "FUNCTION", _STORE_CALLABLE_STATE(value)))
            elif type(value) is property:
                entries.append((
                    owner, name, "PROPERTY", value,
                    _STORE_CALLABLE_STATE(value.fget),
                    _STORE_CALLABLE_STATE(value.fset),
                    _STORE_CALLABLE_STATE(value.fdel),
                ))
            elif type(value) in {classmethod, staticmethod}:
                entries.append((
                    owner, name, type(value).__name__, value,
                    _STORE_CALLABLE_STATE(value.__func__),
                ))
    return tuple(entries)


_STORE_DISPATCH_SNAPSHOTTER = _store_dispatch_snapshot
_STORE_DISPATCH_SNAPSHOTTER_CODE = _store_dispatch_snapshot.__code__


def _require_store_dispatch_integrity(store: object) -> None:
    try:
        if (_require_store_dispatch_integrity.__code__ is not
                _STORE_DISPATCH_GUARD_CODE
                or globals().get("_require_store_dispatch_integrity") is not
                _REQUIRE_STORE_DISPATCH_INTEGRITY
                or _STORE_DISPATCH_SNAPSHOTTER.__code__ is not
                _STORE_DISPATCH_SNAPSHOTTER_CODE
                or _STORE_CALLABLE_STATE.__code__ is not
                _STORE_CALLABLE_STATE_CODE
                or globals().get("_store_callable_state") is not
                _STORE_CALLABLE_STATE
                or globals().get("_store_dispatch_snapshot") is not
                _STORE_DISPATCH_SNAPSHOTTER
                or globals().get("_governed_query_text") is not
                _RETAINED_GOVERNED_QUERY_TEXT
                or _RETAINED_GOVERNED_QUERY_TEXT.__code__ is not
                _RETAINED_GOVERNED_QUERY_TEXT_CODE
                or globals().get("_read_only_sql_text") is not
                _RETAINED_READ_ONLY_SQL_TEXT
                or _RETAINED_READ_ONLY_SQL_TEXT.__code__ is not
                _RETAINED_READ_ONLY_SQL_TEXT_CODE
                or globals().get(
                    "_RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR") is not
                Store._require_active_serialized_cursor
                or Store._require_active_serialized_cursor.__code__ is not
                _RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR_CODE
                or type(store) is not Store
                or getattr(store, "_registry_sealed", None) is not True
                or _STORE_DISPATCH_SNAPSHOTTER() != _STORE_DISPATCH_ANCHORS
                or any(callable(getattr(Store, name, None))
                       for name in vars(store))):
            raise RuntimeError(
                "Store runtime dispatch changed after construction")
        Store.registry.fget(store)
    except Exception:
        marker = globals().get("_RETAINED_TRANSACTION_INTEGRITY_MARKER")
        marker_code = globals().get(
            "_RETAINED_TRANSACTION_INTEGRITY_MARKER_CODE")
        if (type(marker) is types.FunctionType
                and marker.__code__ is marker_code):
            try:
                marker(store)
            except Exception:
                pass
        raise


_REQUIRE_STORE_DISPATCH_INTEGRITY = _require_store_dispatch_integrity
_STORE_DISPATCH_GUARD_CODE = _require_store_dispatch_integrity.__code__

_RUNTIME_POSTURE_VERIFIERS = (
    *_RUNTIME_POSTURE_VERIFIERS, _REQUIRE_STORE_DISPATCH_INTEGRITY)
_RUNTIME_POSTURE_VERIFIER_CODES = tuple(
    verifier.__code__ for verifier in _RUNTIME_POSTURE_VERIFIERS)


class Store:
    _SEALED_REGISTRY_FIELDS = {
        "_registry", "_registry_decision_identity", "_registry_sealed",
        "_verified_static_schema", "_transaction_lock", "_transaction_state",
        "_runtime_bundle", "_runtime_environment_seal", "_bootstrap_bundle",
        "_pending_runtime_bundle_activation", "_runtime_posture_verifiers",
        "_runtime_posture_verifier_codes", "_active_transaction_token",
        "_active_transaction_integrity", "_active_transaction_serialized",
        "_application_callable_anchors",
    }

    def __setattr__(self, name, value):
        if getattr(self, "_registry_sealed", False):
            if name in self._SEALED_REGISTRY_FIELDS:
                raise AttributeError(
                    "Store registry/runtime binding is immutable outside its "
                    "sealed lifecycle")
            if callable(getattr(type(self), name, None)):
                raise AttributeError("Store runtime dispatch is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if (getattr(self, "_registry_sealed", False)
                and (name in self._SEALED_REGISTRY_FIELDS
                     or callable(getattr(type(self), name, None)))):
            raise AttributeError("Store sealed runtime state cannot be deleted")
        object.__delattr__(self, name)

    def __init__(self, dsn: str | None = None, registry: ContractRegistry | None = None):
        self._registry_sealed = False
        # This reads only local reviewed bytes.  It must complete before the
        # Store is capable of opening or touching a database connection.
        self._verified_static_schema = verify_static_runtime_catalog(
            config.PACKAGE_ROOT)
        self.dsn = dsn or config.database_dsn()
        self._registry = registry or ContractRegistry()
        self._registry_decision_identity = self._registry.decision_identity()
        self._conn: psycopg.Connection | None = None
        self._runtime_bundle = None
        self._runtime_environment_seal = None
        self._bootstrap_bundle = None
        self._pending_runtime_bundle_activation = None
        self._active_transaction_token = None
        self._active_transaction_integrity = None
        self._active_transaction_serialized = None
        self._application_callable_anchors = ()
        self._runtime_posture_verifiers = _RUNTIME_POSTURE_VERIFIERS
        self._runtime_posture_verifier_codes = \
            _RUNTIME_POSTURE_VERIFIER_CODES
        # One psycopg connection is shared by the synchronous API object.  The
        # lock spans the complete transaction/yield window so another FastAPI
        # worker can never join the first worker's PostgreSQL transaction.  The
        # depth is thread-local: only genuine same-thread nested reads may reuse
        # an already verified cursor/transaction.
        self._transaction_lock = threading.RLock()
        self._transaction_state = threading.local()
        self._registry_sealed = True

    @property
    def registry(self) -> ContractRegistry:
        registry = self._registry
        canonical = ContractRegistry()
        if (type(registry) is not ContractRegistry
                or any(callable(getattr(ContractRegistry, name, None))
                       for name in vars(registry))
                or ContractRegistry.decision_identity(registry) !=
                self._registry_decision_identity
                or ContractRegistry.decision_identity(registry) !=
                ContractRegistry.decision_identity(canonical)):
            raise RuntimeError(
                "Store ContractRegistry decision semantics changed after construction")
        return registry

    def bind_application_callables(self, callables) -> None:
        """Append exact post-bootstrap HTTP/dependency callable anchors."""
        _REQUIRE_STORE_DISPATCH_INTEGRITY(self)
        selected = tuple(callables)
        if (not selected
                or any(type(function) is not types.FunctionType
                       for function in selected)):
            raise RuntimeError("application callable binding is malformed")
        existing = {
            id(function) for function, _state in self._application_callable_anchors
        }
        additions = tuple(
            (function, _STORE_CALLABLE_STATE(function))
            for function in selected if id(function) not in existing
        )
        object.__setattr__(
            self, "_application_callable_anchors",
            (*self._application_callable_anchors, *additions),
        )

    # -- connection / lifecycle ------------------------------------------------

    def _require_static_runtime_catalog(self) -> None:
        """Re-prove reviewed static inputs before any database mutation."""
        current = verify_static_runtime_catalog(config.PACKAGE_ROOT)
        if current != self._verified_static_schema:
            raise SchemaGuardError(
                "static RuntimeBundle catalog or exact schema bytes changed after "
                "Store construction; database startup is forbidden")

    def _require_preconnection_runtime_posture(self) -> None:
        """Re-prove static and import inputs before opening a DB connection."""
        Store._require_static_runtime_catalog(self)
        # Imported decision code is part of the pre-DB posture as well.  The
        # runtime_bundle helper validates module origins and bytes without
        # opening a PostgreSQL connection.
        _REQUIRE_STORE_DISPATCH_INTEGRITY(self)
        Store._require_transaction_python_posture(self)

    def _mark_transaction_integrity_violation(self) -> None:
        """Make the current outer transaction permanently rollback-only."""
        latch = self._active_transaction_integrity
        if type(latch) is _TransactionIntegrityLatch:
            _TransactionIntegrityLatch.poison(latch)

    def _require_transaction_integrity_clean(self) -> None:
        latch = self._active_transaction_integrity
        serialized = self._active_transaction_serialized
        if (type(latch) is not _TransactionIntegrityLatch
                or getattr(self._transaction_state, "integrity", None) is not latch
                or type(serialized) is not bool
                or getattr(self._transaction_state, "serialized", None) is not
                serialized
                or latch.poisoned is not False):
            raise RuntimeBundleError(
                "governed transaction is rollback-only after a runtime "
                "integrity violation")

    def _require_transaction_python_posture(self) -> None:
        """Re-prove executable Python state before every outer DB transaction."""
        try:
            Store._require_transaction_python_posture_unpoisoned(self)
        except Exception:
            Store._mark_transaction_integrity_violation(self)
            raise

    def _require_transaction_python_posture_unpoisoned(self) -> None:
        """Perform the posture proof used by the rollback-only wrapper."""
        (require_live_python_import_posture,
         require_runtime_environment_seal,
         require_store_runtime_bundle,
         require_decision_semantics,
         require_store_dispatch_integrity) = self._runtime_posture_verifiers
        if (len(self._runtime_posture_verifiers)
                != len(_RUNTIME_POSTURE_VERIFIERS)
                or len(self._runtime_posture_verifier_codes)
                != len(_RUNTIME_POSTURE_VERIFIER_CODES)
                or any(
                    verifier is not expected_verifier
                    or expected_code is not retained_code
                    or verifier.__code__ is not retained_code
                    or verifier.__globals__.get(verifier.__name__) is not verifier
                    for verifier, expected_code, expected_verifier, retained_code in zip(
                        self._runtime_posture_verifiers,
                        self._runtime_posture_verifier_codes,
                        _RUNTIME_POSTURE_VERIFIERS,
                        _RUNTIME_POSTURE_VERIFIER_CODES))):
            raise RuntimeError(
                "Store runtime posture verifier changed after construction")
        require_store_dispatch_integrity(self)
        selected_seal = (
            self._runtime_environment_seal
            if self._runtime_bundle is not None
            else (self._pending_runtime_bundle_activation[2]
                  if self._pending_runtime_bundle_activation is not None else None)
        )
        if selected_seal is not None and any(
                function.__code__ is not code
                for function, code in selected_seal.decision_callable_anchors):
            raise RuntimeBundleError(
                "decision semantic state changed after selection")
        if any(
                type(function) is not types.FunctionType
                or _STORE_CALLABLE_STATE(function) != selected_state
                for function, selected_state
                in self._application_callable_anchors):
            raise RuntimeBundleError(
                "application decision callable changed after binding")
        if self._runtime_bundle is None:
            pending = self._pending_runtime_bundle_activation
            if pending is not None:
                require_decision_semantics(pending[2].decision_semantics)
                require_runtime_environment_seal(
                    pending[1], pending[2],
                    "Store pending RuntimeBundle activation",
                )
                return
            require_live_python_import_posture(config.PACKAGE_ROOT)
            return
        require_decision_semantics(
            self._runtime_environment_seal.decision_semantics)
        require_store_runtime_bundle(
            self, self._runtime_bundle, "Store governed transaction")

    def _transaction_depth(self) -> int:
        depth = getattr(self._transaction_state, "depth", 0)
        if type(depth) is not int or depth < 0:
            raise RuntimeError("governed transaction depth must be an exact integer")
        return depth

    def _set_transaction_depth(self, depth: int) -> None:
        if type(depth) is not int or depth < 0:
            raise RuntimeError("governed transaction depth must be an exact integer")
        self._transaction_state.depth = depth

    def _require_nested_transaction_ownership(self) -> None:
        state = self._transaction_state
        token = getattr(state, "token", None)
        connection = self._conn
        integrity = self._active_transaction_integrity
        serialized = self._active_transaction_serialized
        depth = getattr(state, "depth", None)
        if (type(depth) is not int
                or depth <= 0
                or token is None
                or token is not self._active_transaction_token
                or getattr(state, "ownerThread", None) != threading.get_ident()
                or getattr(state, "connection", None) is not connection
                or type(integrity) is not _TransactionIntegrityLatch
                or getattr(state, "integrity", None) is not integrity
                or type(serialized) is not bool
                or getattr(state, "serialized", None) is not serialized
                or integrity.poisoned is not False
                or connection is None
                or connection.closed
                or connection.info.transaction_status !=
                psycopg.pq.TransactionStatus.INTRANS):
            raise RuntimeError(
                "nested governed transaction ownership is unverified")

    def _require_active_governed_cursor(self, cur) -> None:
        """Require the exact cursor yielded by this Store's active transaction."""
        try:
            if (type(self) is not Store
                    or type(cur) is not _GovernedCursor
                    or object.__getattribute__(
                        cur, "_GovernedCursor__store") is not self
                    or vars(_GovernedCursor).get("_require_ownership") is not
                    _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP
                    or _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP.__code__ is not
                    _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP_CODE
                    or vars(_GovernedCursor).get("_require_statement") is not
                    _RETAINED_GOVERNED_CURSOR_REQUIRE_STATEMENT
                    or _RETAINED_GOVERNED_CURSOR_REQUIRE_STATEMENT.__code__ is not
                    _RETAINED_GOVERNED_CURSOR_REQUIRE_STATEMENT_CODE
                    or vars(_GovernedCursor).get("_execute_read") is not
                    _RETAINED_GOVERNED_CURSOR_EXECUTE_READ
                    or _RETAINED_GOVERNED_CURSOR_EXECUTE_READ.__code__ is not
                    _RETAINED_GOVERNED_CURSOR_EXECUTE_READ_CODE
                    or vars(_GovernedCursor).get("_execute_mutation") is not
                    _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION
                    or _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION.__code__ is not
                    _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION_CODE
                    or vars(_GovernedCursor).get("_executemany_read") is not
                    _RETAINED_GOVERNED_CURSOR_EXECUTEMANY_READ
                    or _RETAINED_GOVERNED_CURSOR_EXECUTEMANY_READ.__code__ is not
                    _RETAINED_GOVERNED_CURSOR_EXECUTEMANY_READ_CODE
                    or vars(_GovernedCursor).get("_executemany_mutation") is not
                    _RETAINED_GOVERNED_CURSOR_EXECUTEMANY_MUTATION
                    or _RETAINED_GOVERNED_CURSOR_EXECUTEMANY_MUTATION.__code__ is not
                    _RETAINED_GOVERNED_CURSOR_EXECUTEMANY_MUTATION_CODE):
                raise RuntimeError(
                    "reference resolution requires this Store's exact active "
                    "governed cursor")
            _RETAINED_GOVERNED_CURSOR_REQUIRE_OWNERSHIP(cur)
        except BaseException:
            Store._mark_transaction_integrity_violation(self)
            raise

    def _require_active_serialized_cursor(self, cur) -> None:
        """Require a governed cursor whose transaction holds the writer lock."""
        try:
            Store._require_active_governed_cursor(self, cur)
            if (self._active_transaction_serialized is not True
                    or getattr(
                        self._transaction_state, "serialized", None) is not True):
                raise RuntimeError(
                    "governed mutation or authority evaluation requires the "
                    "active serialized cursor")
        except BaseException:
            Store._mark_transaction_integrity_violation(self)
            raise

    def _require_runtime_dispatch_integrity(self) -> None:
        _REQUIRE_STORE_DISPATCH_INTEGRITY(self)

    def _raw_connection(self) -> psycopg.Connection:
        with self._transaction_lock:
            if self._conn is None or self._conn.closed:
                Store._require_preconnection_runtime_posture(self)
                self._conn = psycopg.connect(
                    self.dsn,
                    row_factory=dict_row,
                    autocommit=True,
                    context=_RETAINED_PSYCOPG_ADAPTERS,
                )
            return self._conn

    @property
    def conn(self) -> _GovernedConnectionView:
        """A maintenance facade that rechecks transaction ownership per use."""
        connection = Store._raw_connection(self)
        return _GovernedConnectionView(
            connection, self, governed=False)

    def migrate(self) -> None:
        """Install exact schema once, or verify an exact no-DDL restart.

        Despite the historical method name, this never forward-migrates,
        backfills, or repairs a non-empty database.
        """
        with self._transaction_lock:
            Store._require_static_runtime_catalog(self)
            ensure_schema(
                Store._raw_connection(self), self._verified_static_schema)

    def close(self) -> None:
        with self._transaction_lock:
            if self._conn is not None and not self._conn.closed:
                self._conn.close()

    @property
    def runtime_bundle(self):
        if self._runtime_bundle is None:
            raise RuntimeError("Store has no verified RuntimeBundle; bootstrap first")
        return self._runtime_bundle

    @property
    def runtime_bundle_digest(self) -> str:
        return self.runtime_bundle.digest

    def bind_runtime_bundle(self, bundle) -> None:
        """Reject direct binding; live activation belongs to atomic bootstrap."""
        if bundle.construction_mode != "LIVE_CURRENT":
            raise RuntimeError(
                "persisted-audit RuntimeBundles cannot be bound for live decisions")
        raise RuntimeError(
            "direct RuntimeBundle binding is forbidden; use atomic context bootstrap")

    @staticmethod
    def _observe_database_environment(cur) -> dict:
        """Capture decision-bearing PostgreSQL state in the bootstrap transaction."""
        if type(cur) is _GovernedCursor:
            def execute_read(query, *args):
                return _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(
                    cur, query, *args)
        else:
            execute_read = cur.execute
        execute_read(
            "SELECT pg_catalog.current_setting('server_version') AS version, "
            "pg_catalog.current_setting('server_version_num') AS version_number, "
            "pg_catalog.current_setting('server_encoding') AS encoding, "
            "pg_catalog.current_setting('TimeZone') AS timezone, "
            "pg_catalog.current_setting('DateStyle') AS date_style, "
            "pg_catalog.current_setting('IntervalStyle') AS interval_style, "
            "pg_catalog.current_setting('search_path') AS search_path, "
            "pg_catalog.current_setting('session_replication_role') "
            "AS session_replication_role, "
            "pg_catalog.current_setting('transaction_isolation') "
            "AS transaction_isolation, "
            "pg_catalog.current_setting('standard_conforming_strings') "
            "AS standard_strings, "
            "pg_catalog.current_setting('extra_float_digits') "
            "AS extra_float_digits, "
            "pg_catalog.current_setting('bytea_output') AS bytea_output, "
            "current_user AS current_user_name, session_user AS session_user_name"
        )
        settings = cur.fetchone()
        normalized = re.match(r"^(\d+\.\d+)", settings["version"])
        if normalized is None:
            raise RuntimeError("observed PostgreSQL version is not parseable")
        execute_read(
            "SELECT datlocprovider::text AS locale_provider, "
            "datcollate AS collation, datctype AS ctype, "
            "datlocale AS locale, daticurules AS icu_rules, "
            "datcollversion AS collation_version "
            "FROM pg_catalog.pg_database "
            "WHERE datname = pg_catalog.current_database()"
        )
        database = cur.fetchone()
        if database is None:
            raise RuntimeError("current PostgreSQL database identity is unavailable")
        execute_read(
            "SELECT extname AS name, extversion AS version "
            "FROM pg_catalog.pg_extension ORDER BY extname"
        )
        extensions = [dict(row) for row in cur.fetchall()]
        return {
            "schemaVersion": "ofarm.runtime-database-observation.local.v1",
            "server": {
                "version": settings["version"],
                "versionNumber": settings["version_number"],
                "normalizedVersion": normalized.group(1),
            },
            "database": {
                "encoding": settings["encoding"],
                "localeProvider": database["locale_provider"],
                "collation": database["collation"],
                "ctype": database["ctype"],
                "locale": database["locale"],
                "icuRules": database["icu_rules"],
                "collationVersion": database["collation_version"],
            },
            "session": {
                "currentUser": settings["current_user_name"],
                "sessionUser": settings["session_user_name"],
                "timezone": settings["timezone"],
                "dateStyle": settings["date_style"],
                "intervalStyle": settings["interval_style"],
                "searchPath": settings["search_path"],
                "sessionReplicationRole": settings["session_replication_role"],
                "transactionIsolation": settings["transaction_isolation"],
                "standardConformingStrings": settings["standard_strings"],
                "extraFloatDigits": settings["extra_float_digits"],
                "byteaOutput": settings["bytea_output"],
            },
            "extensions": extensions,
        }

    def _establish_database_transaction_posture(self, cur) -> dict:
        """Fix and verify all decision-bearing DB state before transaction use."""
        require_no_temporary_schema(cur)
        cur.execute(
            "SELECT CURRENT_USER::pg_catalog.text AS current_user_name, "
            "SESSION_USER::pg_catalog.text AS session_user_name"
        )
        identity = cur.fetchone()
        if identity["current_user_name"] != identity["session_user_name"]:
            raise RuntimeError(
                "PostgreSQL current role differs from the authenticated session "
                "role before the governed transaction")
        for _field_name, setting_name, expected in _DETERMINISTIC_SESSION_SETTINGS:
            cur.execute(
                "SELECT pg_catalog.set_config(%s, %s, true) AS value",
                (setting_name, expected),
            )
            if cur.fetchone()["value"] != expected:
                raise RuntimeError(
                    f"PostgreSQL setting {setting_name!r} could not be fixed "
                    "for the governed transaction")

        return Store._require_database_transaction_posture(self, cur)

    def _require_database_transaction_posture(self, cur) -> dict:
        """Verify DB state without repairing a mutation made by the caller."""
        if cur.connection.info.transaction_status != \
                psycopg.pq.TransactionStatus.INTRANS:
            raise RuntimeError(
                "database posture verification requires the active governed "
                "transaction and its catalog locks")
        require_no_temporary_schema(cur)

        observed = Store._observe_database_environment(cur)
        session = observed["session"]
        if any(session.get(field_name) != expected
               for field_name, _setting_name, expected
               in _DETERMINISTIC_SESSION_SETTINGS):
            raise RuntimeError(
                "PostgreSQL transaction did not retain the deterministic "
                "session posture")
        if session.get("transactionIsolation") != "read committed":
            raise RuntimeError(
                "PostgreSQL transaction did not retain READ COMMITTED isolation")
        if session["currentUser"] != session["sessionUser"]:
            raise RuntimeError(
                "PostgreSQL current role differs from the authenticated session "
                "role in the governed transaction")

        pending = self._pending_runtime_bundle_activation
        selected_bundle = (
            self._runtime_bundle
            or self._bootstrap_bundle
            or (pending[1] if pending is not None else None)
        )
        if selected_bundle is None:
            # Before the first bundle exists there is no retained observation
            # to compare.  Refuse inherited SET ROLE state so it cannot become
            # the baseline selected during bootstrap.
            return observed

        from .runtime_bundle import database_runtime_environment_component
        selected_database = selected_bundle.component(
            "RUNTIME_DATABASE_OBSERVED", "environment:observed-postgresql.v1")
        if database_runtime_environment_component(observed) != selected_database:
            raise RuntimeError(
                "PostgreSQL environment differs from the retained "
                "RuntimeBundle observation")
        return observed

    def _prepare_runtime_bundle_binding(self, bundle):
        """Run every fallible live-binding check inside the bootstrap transaction."""
        if self._bootstrap_bundle is not bundle:
            raise RuntimeError(
                "RuntimeBundle binding preparation requires its verified bootstrap scope")
        Store._require_nested_transaction_ownership(self)
        from .runtime_bundle import (
            assert_runtime_environment_compatible,
            database_runtime_environment_component,
            require_current_runtime_catalog,
        )
        if bundle.tenant_ref != config.TENANT_REF:
            raise RuntimeError(
                "RuntimeBundle tenant does not match this Store runtime tenant")
        require_current_runtime_catalog(bundle, config.PACKAGE_ROOT)
        required_environment, environment_seal = \
            assert_runtime_environment_compatible(bundle)
        connection = self._transaction_state.connection
        with connection.cursor() as cur:
            database_environment = self._observe_database_environment(cur)
        selected_database = bundle.component(
            "RUNTIME_DATABASE_OBSERVED", "environment:observed-postgresql.v1")
        if selected_database != database_runtime_environment_component(
                database_environment):
            raise RuntimeError(
                "observed PostgreSQL environment changed after RuntimeBundle selection")
        if (database_environment["server"]["normalizedVersion"] !=
                required_environment.get("postgresqlVersion")
                or database_environment["session"]["timezone"] !=
                required_environment.get("timezone")
                or database_environment["database"]["encoding"] != "UTF8"
                or database_environment["database"]["localeProvider"] != "c"):
            raise RuntimeError(
                "observed PostgreSQL version, timezone, encoding, or deterministic "
                "locale provider differs from the retained runtime requirement")
        required_settings = {
            "timezone": "UTC",
            "dateStyle": "ISO, MDY",
            "intervalStyle": "postgres",
            "searchPath": "pg_catalog, public",
            "sessionReplicationRole": "origin",
            "transactionIsolation": "read committed",
            "standardConformingStrings": "on",
            "extraFloatDigits": "1",
            "byteaOutput": "hex",
        }
        if any(database_environment["session"].get(name) != value
               for name, value in required_settings.items()):
            raise RuntimeError(
                "observed PostgreSQL semantic settings are unsupported")
        with connection.cursor() as cur:
            require_exact_schema(cur, self._verified_static_schema)
        if self._runtime_bundle is not None and self._runtime_bundle.digest != bundle.digest:
            raise RuntimeError(
                "RuntimeBundle hot switching is forbidden; create a new runtime instance")
        self.assert_runtime_bundle_compatible(bundle)
        cold = self.cold_load_runtime_bundle(bundle.descriptor, bundle.digest)
        if (cold.canonical_document_bytes != bundle.canonical_document_bytes
                or cold.components != bundle.components
                or cold.selected_references != bundle.selected_references):
            raise RuntimeError(
                "cannot bind an incomplete or byte-mismatched persisted RuntimeBundle")
        if self._pending_runtime_bundle_activation is not None:
            raise RuntimeError("a RuntimeBundle activation is already pending")
        token = object()
        object.__setattr__(
            self, "_pending_runtime_bundle_activation",
            (token, bundle, environment_seal),
        )
        return token

    def _activate_prepared_runtime_bundle(self, activation_token) -> None:
        """Consume the exact one-use activation prepared by atomic bootstrap."""
        pending = self._pending_runtime_bundle_activation
        if pending is None or activation_token is not pending[0]:
            raise RuntimeError(
                "RuntimeBundle activation was not successfully prepared by this Store")
        if self.conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
            raise RuntimeError(
                "RuntimeBundle activation is allowed only after bootstrap commits")
        _REQUIRE_STORE_DISPATCH_INTEGRITY(self)
        Store._require_transaction_python_posture(self)
        object.__setattr__(self, "_pending_runtime_bundle_activation", None)
        object.__setattr__(self, "_runtime_bundle", pending[1])
        object.__setattr__(self, "_runtime_environment_seal", pending[2])

    def _discard_prepared_runtime_bundle_binding(self) -> None:
        """Invalidate any one-use activation when bootstrap does not commit."""
        object.__setattr__(self, "_pending_runtime_bundle_activation", None)

    def assert_runtime_bundle_compatible(self, bundle) -> None:
        """Check process-local registry/runtime compatibility before commit."""
        canonical_registry = ContractRegistry()
        if (type(self.registry) is not ContractRegistry
                or ContractRegistry.decision_identity(self.registry) !=
                ContractRegistry.decision_identity(canonical_registry)):
            raise RuntimeError(
                "Store ContractRegistry decision semantics differ from code-owned runtime")
        schema_component = bundle.component(
            "RUNTIME_SCHEMA", "sql:kernel/schema.sql")
        if schema_component.canonical_bytes != \
                self._verified_static_schema.schema_bytes:
            raise RuntimeError(
                "RuntimeBundle schema bytes differ from the schema executed by Store")
        contract_components = {
            component.logical_ref: component for component in bundle.components
            if component.role == "CONTRACT_SCHEMA"
        }
        expected_contract_refs = {
            f"contract:{kind}"
            for kind in ContractRegistry.kinds(self.registry)
        }
        if set(contract_components) != expected_contract_refs:
            raise RuntimeError(
                "RuntimeBundle contract inventory does not equal ContractRegistry")
        for kind in ContractRegistry.kinds(self.registry):
            contract = ContractRegistry.get(self.registry, kind)
            component = contract_components[f"contract:{kind}"]
            if (component.canonicalization != "EXACT_BYTES_V1"
                    or component.content_digest != contract.schema_hash
                    or component.canonical_bytes != contract.schema_bytes):
                raise RuntimeError(
                    f"RuntimeBundle contract bytes do not match registry for {kind!r}")

    def _bundle_digest(self, explicit: str | None = None) -> str:
        if explicit is not None:
            if self._runtime_bundle is not None and explicit != self._runtime_bundle.digest:
                raise RuntimeError(
                    "a bound Store cannot write under a different RuntimeBundle")
            if (self._runtime_bundle is None
                    and (self._bootstrap_bundle is None
                         or explicit != self._bootstrap_bundle.digest)):
                raise RuntimeError(
                    "an unbound Store cannot attribute writes to a RuntimeBundle "
                    "outside verified atomic bootstrap")
            return explicit
        return self.runtime_bundle_digest

    def _bundle_tenant_ref(self) -> str:
        if self._runtime_bundle is not None:
            return self._runtime_bundle.tenant_ref
        if self._bootstrap_bundle is not None:
            return self._bootstrap_bundle.tenant_ref
        raise RuntimeError(
            "Store has no verified RuntimeBundle tenant; bootstrap first")

    @contextmanager
    def _bootstrap_bundle_writes(self, bundle):
        """Narrow pre-bind write authority to one verified bootstrap bundle."""
        if not Store._transaction_depth(self):
            raise RuntimeError(
                "bootstrap write authority requires an active database transaction")
        Store._require_nested_transaction_ownership(self)
        if self._runtime_bundle is not None:
            raise RuntimeError("bootstrap bundle writes require an unbound Store")
        if self._bootstrap_bundle is not None:
            raise RuntimeError("nested RuntimeBundle bootstrap write scopes are forbidden")
        if bundle.construction_mode != "LIVE_CURRENT":
            raise RuntimeError(
                "bootstrap write authority requires a live-selected RuntimeBundle")
        if bundle.tenant_ref != config.TENANT_REF:
            raise RuntimeError(
                "bootstrap write authority tenant differs from this runtime tenant")
        connection = self._transaction_state.connection
        if connection.info.transaction_status == psycopg.pq.TransactionStatus.IDLE:
            raise RuntimeError(
                "bootstrap write authority requires an active database transaction")
        self.assert_runtime_bundle_compatible(bundle)
        object.__setattr__(self, "_bootstrap_bundle", bundle)
        try:
            yield
        finally:
            object.__setattr__(self, "_bootstrap_bundle", None)

    def install_runtime_bundle(self, cur, bundle) -> None:
        """Persist exact bundle/component bytes, verifying every identity reuse."""
        Store._require_active_governed_cursor(self, cur)
        from .runtime_bundle import (
            GLOBAL_CONTENT_PLACEMENT,
            TENANT_CONTENT_PLACEMENT,
        )
        if bundle.tenant_ref != config.TENANT_REF:
            raise RuntimeError(
                "cannot install a RuntimeBundle for a different runtime tenant")
        if bundle.construction_mode != "LIVE_CURRENT":
            raise RuntimeError(
                "only a live-selected RuntimeBundle may be installed")
        if cur.connection.info.transaction_status != psycopg.pq.TransactionStatus.INTRANS:
            raise RuntimeError(
                "RuntimeBundle installation requires one active database transaction")
        _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
            "SELECT tenant_ref, bundle_ref, canonical_document, canonical_bytes, "
            "byte_length FROM ONLY runtime_bundle "
            "WHERE tenant_ref = %s AND bundle_digest = %s",
            (bundle.tenant_ref, bundle.digest),
        )
        prior_bundle = cur.fetchone()
        document = json.loads(bundle.canonical_document_bytes)
        if prior_bundle is not None:
            if (prior_bundle["tenant_ref"] != bundle.tenant_ref
                    or prior_bundle["bundle_ref"] != bundle.bundle_ref
                    or prior_bundle["canonical_document"] != document
                    or bytes(prior_bundle["canonical_bytes"]) !=
                    bundle.canonical_document_bytes
                    or prior_bundle["byte_length"] !=
                    len(bundle.canonical_document_bytes)):
                raise RuntimeError(
                    f"RuntimeBundle digest {bundle.digest} was reused for unequal bytes")
            _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
                "SELECT component_role, logical_ref FROM ONLY runtime_bundle_component "
                "WHERE tenant_ref = %s AND bundle_digest = %s",
                (bundle.tenant_ref, bundle.digest),
            )
            persisted_identities = {
                (row["component_role"], row["logical_ref"])
                for row in cur.fetchall()
            }
            expected_identities = {
                (component.role, component.logical_ref)
                for component in bundle.components
            }
            if persisted_identities != expected_identities:
                raise RuntimeError(
                    f"existing RuntimeBundle {bundle.digest} component set is not exact; "
                    f"missing={sorted(expected_identities - persisted_identities)}, "
                    f"extra={sorted(persisted_identities - expected_identities)}")
        for component in bundle.components:
            if component.placement == GLOBAL_CONTENT_PLACEMENT:
                table = "runtime_content_blob"
                where = "content_digest = %s"
                params = (component.content_digest,)
                columns = (
                    "content_digest, content_class, canonicalization, "
                    "canonical_bytes, byte_length")
                values = (component.content_digest, component.role,
                          component.canonicalization, component.canonical_bytes,
                          len(component.canonical_bytes))
            elif component.placement == TENANT_CONTENT_PLACEMENT:
                table = "runtime_tenant_content_blob"
                where = "tenant_ref = %s AND content_digest = %s"
                params = (bundle.tenant_ref, component.content_digest)
                columns = (
                    "tenant_ref, content_digest, content_class, canonicalization, "
                    "canonical_bytes, byte_length")
                values = (bundle.tenant_ref, component.content_digest,
                          component.role, component.canonicalization,
                          component.canonical_bytes, len(component.canonical_bytes))
            else:
                raise RuntimeError(
                    f"unknown RuntimeBundle component placement {component.placement!r}")
            _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
                f"SELECT content_class, canonicalization, canonical_bytes, byte_length "
                f"FROM {table} WHERE {where}",
                params,
            )
            prior = cur.fetchone()
            if prior is None:
                if prior_bundle is not None:
                    raise RuntimeError(
                        f"existing RuntimeBundle {bundle.digest} is missing retained "
                        f"content for {component.role}/{component.logical_ref}")
                _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION(cur,
                    f"INSERT INTO {table} ({columns}) VALUES (" +
                    ", ".join(["%s"] * len(values)) + ")",
                    values,
                )
            elif (prior["content_class"] != component.role
                  or prior["canonicalization"] != component.canonicalization
                  or bytes(prior["canonical_bytes"]) != component.canonical_bytes
                  or prior["byte_length"] != len(component.canonical_bytes)):
                raise RuntimeError(
                    f"content digest {component.content_digest} was reused for unequal bytes")

        if prior_bundle is None:
            _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION(cur,
                "INSERT INTO runtime_bundle "
                "(tenant_ref, bundle_digest, bundle_ref, canonical_document, "
                "canonical_bytes, byte_length) VALUES (%s, %s, %s, %s, %s, %s)",
                (bundle.tenant_ref, bundle.digest, bundle.bundle_ref, Jsonb(document),
                 bundle.canonical_document_bytes, len(bundle.canonical_document_bytes)),
            )

        for component in bundle.components:
            _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
                "SELECT repository_path, canonicalization, content_placement, "
                "global_content_digest, tenant_content_digest, byte_length "
                "FROM ONLY runtime_bundle_component WHERE tenant_ref = %s "
                "AND bundle_digest = %s "
                "AND component_role = %s AND logical_ref = %s",
                (bundle.tenant_ref, bundle.digest,
                 component.role, component.logical_ref),
            )
            prior = cur.fetchone()
            global_digest = (
                component.content_digest
                if component.placement == GLOBAL_CONTENT_PLACEMENT else None)
            tenant_digest = (
                component.content_digest
                if component.placement == TENANT_CONTENT_PLACEMENT else None)
            expected = (
                component.repository_path, component.canonicalization,
                component.placement, global_digest, tenant_digest,
                len(component.canonical_bytes),
            )
            if prior is None:
                if prior_bundle is not None:
                    raise RuntimeError(
                        f"existing RuntimeBundle {bundle.digest} is missing component "
                        f"{component.role}/{component.logical_ref}")
                _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION(cur,
                    "INSERT INTO runtime_bundle_component "
                    "(tenant_ref, bundle_digest, component_role, logical_ref, "
                    "repository_path, canonicalization, content_placement, "
                    "global_content_digest, tenant_content_digest, byte_length) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (bundle.tenant_ref, bundle.digest, component.role,
                     component.logical_ref, *expected),
                )
            elif (
                prior["repository_path"], prior["canonicalization"],
                prior["content_placement"], prior["global_content_digest"],
                prior["tenant_content_digest"], prior["byte_length"],
            ) != expected:
                raise RuntimeError(
                    f"RuntimeBundle component identity was reused with drift: "
                    f"{component.role}/{component.logical_ref}")

        _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
            "SELECT component_role, logical_ref FROM ONLY runtime_bundle_component "
            "WHERE tenant_ref = %s AND bundle_digest = %s",
            (bundle.tenant_ref, bundle.digest),
        )
        persisted_identities = {
            (row["component_role"], row["logical_ref"]) for row in cur.fetchall()
        }
        expected_identities = {
            (component.role, component.logical_ref) for component in bundle.components
        }
        if persisted_identities != expected_identities:
            raise RuntimeError(
                f"RuntimeBundle {bundle.digest} persisted component set is not exact; "
                f"missing={sorted(expected_identities - persisted_identities)}, "
                f"extra={sorted(persisted_identities - expected_identities)}")

    def persisted_runtime_bundle(self, digest: str) -> dict | None:
        with Store._read_cursor(self) as cur:
            _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
                "SELECT tenant_ref, bundle_digest, bundle_ref, canonical_document, "
                "canonical_bytes, byte_length FROM ONLY runtime_bundle "
                "WHERE tenant_ref = %s AND bundle_digest = %s",
                (config.TENANT_REF, digest),
            )
            bundle = cur.fetchone()
            if bundle is None:
                return None
            _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
                "SELECT c.component_role, c.logical_ref, c.repository_path, "
                "c.canonicalization, c.content_placement, "
                "CASE WHEN c.content_placement = 'GLOBAL_IMMUTABLE_CONTENT' "
                "THEN c.global_content_digest ELSE c.tenant_content_digest END "
                "AS content_digest, c.byte_length, "
                "CASE WHEN c.content_placement = 'GLOBAL_IMMUTABLE_CONTENT' "
                "THEN g.content_class ELSE t.content_class END AS blob_content_class, "
                "CASE WHEN c.content_placement = 'GLOBAL_IMMUTABLE_CONTENT' "
                "THEN g.canonicalization ELSE t.canonicalization END "
                "AS blob_canonicalization, "
                "CASE WHEN c.content_placement = 'GLOBAL_IMMUTABLE_CONTENT' "
                "THEN g.byte_length ELSE t.byte_length END AS blob_byte_length, "
                "CASE WHEN c.content_placement = 'GLOBAL_IMMUTABLE_CONTENT' "
                "THEN g.canonical_bytes ELSE t.canonical_bytes END AS canonical_bytes "
                "FROM ONLY runtime_bundle_component c "
                "LEFT JOIN ONLY runtime_content_blob g "
                "ON g.content_digest = c.global_content_digest "
                "LEFT JOIN ONLY runtime_tenant_content_blob t "
                "ON t.tenant_ref = c.tenant_ref "
                "AND t.content_digest = c.tenant_content_digest "
                "WHERE c.tenant_ref = %s AND c.bundle_digest = %s "
                "ORDER BY c.component_role, c.logical_ref",
                (config.TENANT_REF, digest),
            )
            components = cur.fetchall()
        return {
            "tenant_ref": bundle["tenant_ref"],
            "bundle_digest": bundle["bundle_digest"],
            "bundle_ref": bundle["bundle_ref"],
            "canonical_document": bundle["canonical_document"],
            "canonical_document_bytes": bytes(bundle["canonical_bytes"]),
            "byte_length": bundle["byte_length"],
            "components": components,
        }

    def cold_load_runtime_bundle(self, descriptor, digest: str):
        """Reconstruct and verify a bundle using only immutable persisted bytes."""
        from .runtime_bundle import RuntimeComponent, runtime_bundle_from_persisted
        persisted = self.persisted_runtime_bundle(digest)
        if persisted is None:
            raise RuntimeError(f"no persisted RuntimeBundle {digest}")
        canonical_document_bytes = persisted["canonical_document_bytes"]
        if persisted["bundle_digest"] != digest:
            raise RuntimeError("persisted RuntimeBundle key does not match requested digest")
        if persisted["tenant_ref"] != config.TENANT_REF:
            raise RuntimeError("persisted RuntimeBundle tenant does not match this Store")
        if persisted["bundle_ref"] != f"runtimebundle:{digest}":
            raise RuntimeError("persisted RuntimeBundle ref does not match requested digest")
        if persisted["byte_length"] != len(canonical_document_bytes):
            raise RuntimeError("persisted RuntimeBundle document length mismatch")
        try:
            canonical_document = json.loads(canonical_document_bytes)
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError("persisted RuntimeBundle document bytes are malformed") from exc
        if canonical_document != persisted["canonical_document"]:
            raise RuntimeError(
                "persisted RuntimeBundle canonical JSON and exact bytes disagree")
        if canonical_document.get("tenantRef") != persisted["tenant_ref"]:
            raise RuntimeError(
                "persisted RuntimeBundle document and relational tenant disagree")
        components = []
        for row in persisted["components"]:
            if row["canonical_bytes"] is None:
                raise RuntimeError(
                    "persisted RuntimeBundle component points to the wrong or "
                    "missing content carrier")
            canonical = bytes(row["canonical_bytes"])
            if (row["byte_length"] != len(canonical)
                    or row["blob_byte_length"] != len(canonical)
                    or row["blob_content_class"] != row["component_role"]
                    or row["blob_canonicalization"] != row["canonicalization"]):
                raise RuntimeError(
                    "persisted RuntimeBundle component/blob metadata mismatch")
            components.append(RuntimeComponent(
                role=row["component_role"],
                logical_ref=row["logical_ref"],
                repository_path=row["repository_path"],
                canonicalization=row["canonicalization"],
                content_digest=row["content_digest"],
                canonical_bytes=canonical,
                placement=row["content_placement"],
            ))
        return runtime_bundle_from_persisted(
            descriptor,
            expected_digest=digest,
            canonical_document_bytes=canonical_document_bytes,
            components=components,
            package_root=config.PACKAGE_ROOT,
        )

    @contextmanager
    def _governed_transaction(self, *, serialized: bool):
        """Own one thread-safe transaction and verify all runtime inputs once."""
        _REQUIRE_STORE_DISPATCH_INTEGRITY(self)
        with self._transaction_lock:
            depth = Store._transaction_depth(self)
            outermost = depth == 0
            if outermost:
                if (self._active_transaction_token is not None
                        or self._active_transaction_integrity is not None
                        or self._active_transaction_serialized is not None):
                    raise RuntimeError(
                        "outer governed transaction has stale ownership state")
            else:
                Store._require_nested_transaction_ownership(self)
                if (serialized
                        and self._active_transaction_serialized is not True):
                    raise RuntimeError(
                        "an active read-only transaction cannot be upgraded to "
                        "a serialized writer transaction")
            if outermost:
                # No database decision SQL is exposed until executable Python
                # state has been re-proven against the selected RuntimeBundle.
                Store._require_transaction_python_posture(self)
            connection = (
                Store._raw_connection(self)
                if outermost else self._transaction_state.connection)
            if outermost and (
                    not connection.autocommit
                    or connection.info.transaction_status !=
                    psycopg.pq.TransactionStatus.IDLE):
                raise RuntimeError(
                    "outer governed transaction requires its owned autocommit "
                    "connection to be IDLE; ambient transactions are forbidden")
            depth_initialized = False
            ownership_initialized = False
            try:
                with connection.transaction():
                    with connection.cursor() as cur:
                        if outermost:
                            # This must be the first statement after BEGIN.  A
                            # poisoned session default must never select an older
                            # snapshot before the single-writer lock is acquired.
                            cur.execute(
                                "SET TRANSACTION ISOLATION LEVEL READ COMMITTED, "
                                "READ WRITE")
                            Store._establish_database_transaction_posture(self, cur)
                            # SHARE locks persist through the complete user/yield
                            # window.  Catalog DDL can neither race the fingerprint
                            # nor land between verification and the decision.
                            hold_fingerprint_catalog_locks(cur)
                            require_exact_schema(
                                cur, self._verified_static_schema)
                        elif connection.info.transaction_status != \
                                psycopg.pq.TransactionStatus.INTRANS:
                            raise RuntimeError(
                                "nested governed transaction has no PostgreSQL "
                                "transaction")
                        if serialized and outermost:
                            cur.execute(
                                "SELECT pg_catalog.pg_advisory_xact_lock(%s)",
                                (_SINGLE_WRITER_LOCK_KEY,),
                            )
                        if outermost:
                            token = object()
                            integrity = _TransactionIntegrityLatch()
                            object.__setattr__(
                                self, "_active_transaction_token", token)
                            object.__setattr__(
                                self, "_active_transaction_integrity", integrity)
                            object.__setattr__(
                                self, "_active_transaction_serialized", serialized)
                            ownership_initialized = True
                            self._transaction_state.token = token
                            self._transaction_state.ownerThread = \
                                threading.get_ident()
                            self._transaction_state.connection = connection
                            self._transaction_state.integrity = integrity
                            self._transaction_state.serialized = serialized
                        Store._set_transaction_depth(self, depth + 1)
                        depth_initialized = True
                        yield _GovernedCursor(cur, self)
                        if outermost:
                            Store._require_transaction_integrity_clean(self)
                            # Lazy imports, reloads, or hook/path changes inside
                            # the body must be verified before COMMIT.  A late
                            # failure raises here and rolls the current decision
                            # back instead of deferring detection to the next
                            # transaction.
                            _REQUIRE_STORE_DISPATCH_INTEGRITY(self)
                            Store._require_transaction_python_posture(self)
                            # Observe first, before schema classification can
                            # restore deterministic GUCs.  This makes a late
                            # SET/SET ROLE fail instead of silently repairing it.
                            Store._require_database_transaction_posture(self, cur)
                            # The catalog locks acquired above are still held.
                            # Same-session DDL can therefore be detected before
                            # the context manager reaches COMMIT.
                            require_exact_schema(
                                cur, self._verified_static_schema)
                            # Schema classification fixes its own deterministic
                            # posture; prove that it left the exact retained DB
                            # observation in force as the final pre-COMMIT step.
                            Store._require_database_transaction_posture(self, cur)
                            Store._require_transaction_integrity_clean(self)
            finally:
                try:
                    if depth_initialized:
                        Store._set_transaction_depth(self, depth)
                finally:
                    if outermost and ownership_initialized:
                        for name in (
                            "token", "ownerThread", "connection", "integrity",
                            "serialized",
                        ):
                            if hasattr(self._transaction_state, name):
                                delattr(self._transaction_state, name)
                        object.__setattr__(
                            self, "_active_transaction_token", None)
                        object.__setattr__(
                            self, "_active_transaction_integrity", None)
                        object.__setattr__(
                            self, "_active_transaction_serialized", None)

    @contextmanager
    def tx(self):
        """One transaction. The reachability constraint trigger fires at COMMIT
        of this block (D3).

        This is the current UnitOfWork boundary.  A future UnitOfWork type must
        own this same posture check before it exposes a cursor; callers must
        never depend on a long-lived connection remaining untouched.

        Plain ``tx()`` exposes only the retained private read primitive and does
        not hold the single-writer lock. Every governed mutation and every
        authority decision must instead use the same ``serialized_tx()`` cursor
        that selects and consumes the decision. A live plain transaction cannot
        be upgraded, because a savepoint rollback could release a lock acquired
        by a nested writer while leaving false Python ownership state behind.

        PostgreSQL READ ONLY is deliberately not selected here: the exact-schema
        proof holds SHARE locks on system catalogs to exclude RowExclusive
        catalog changes, and PostgreSQL forbids those locks in a read-only
        transaction. Mutation authority is closed at the governed cursor.
        """
        with Store._governed_transaction(self, serialized=False) as cur:
            yield cur

    @contextmanager
    def serialized_tx(self):
        """A governed WRITE transaction holding the single-writer advisory lock
        (M2 G2). User commits and scheduled imports share this lock, so they can
        never interleave (single-writer invariant by construction) and concurrent
        structure-identity commits serialize (D18 race, PR #9 H1). The lock is
        transaction-scoped — Postgres releases it at COMMIT/ROLLBACK — so it is
        held for exactly the life of the write and never leaks. Within a single
        connection it is granted immediately (no self-contention); it only blocks
        a *different* connection's write, which is the cross-writer race we mean
        to serialize."""
        with Store._governed_transaction(self, serialized=True) as cur:
            yield cur

    @contextmanager
    def _read_cursor(self):
        """Return a cursor only inside a verified governed transaction."""
        _REQUIRE_STORE_DISPATCH_INTEGRITY(self)
        if Store._transaction_depth(self):
            Store._require_nested_transaction_ownership(self)
            connection = self._transaction_state.connection
            if connection.info.transaction_status != \
                    psycopg.pq.TransactionStatus.INTRANS:
                raise RuntimeError(
                    "governed transaction tracking disagrees with PostgreSQL state")
            with connection.cursor() as cur:
                yield _GovernedCursor(cur, self)
            return
        with Store.tx(self) as cur:
            yield cur

    # -- canonical record writes ----------------------------------------------

    def insert_record(self, cur, payload: dict, *, tenant_ref: str | None = None,
                      runtime_bundle_digest: str | None = None) -> str:
        """Validate against the package contract and append. Returns record id."""
        Store._require_active_governed_cursor(self, cur)
        bundle_tenant_ref = self._bundle_tenant_ref()
        if tenant_ref is None:
            tenant_ref = bundle_tenant_ref
        elif tenant_ref != bundle_tenant_ref:
            raise RuntimeError(
                "kernel_record tenant must exactly match the verified RuntimeBundle tenant")
        contract = ContractRegistry.validate(self.registry, payload)
        if contract.lane != "canonical":
            raise ContractViolation(
                f"{contract.kind} is a draft-lane shape; draft records belong in "
                "runtime_trace (D16: implement, never promote)"
            )
        if contract.id_field is None:
            raise ContractViolation(
                f"{contract.kind} is an authored-artifact contract, not a store record"
            )
        record_id = payload[contract.id_field]
        _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION(cur,
            """
            INSERT INTO kernel_record
              (record_id, record_kind, lane, schema_hash, payload, payload_sha256,
               tenant_ref, runtime_bundle_digest)
            VALUES (%s, %s, 'canonical', %s, %s, %s, %s, %s)
            """,
            (record_id, contract.kind, contract.schema_hash, Jsonb(payload),
             sha256_of(payload), tenant_ref, self._bundle_digest(runtime_bundle_digest)),
        )
        return record_id

    def runtime_trace_exists(self, trace_id: str) -> bool:
        with Store._read_cursor(self) as cur:
            _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
                "SELECT 1 FROM ONLY runtime_trace WHERE trace_id = %s", (trace_id,))
            return cur.fetchone() is not None

    def insert_runtime_trace(self, cur, payload: dict, *,
                             runtime_bundle_digest: str | None = None) -> str:
        """Append a draft-lane runtime evidence record (D16)."""
        Store._require_active_governed_cursor(self, cur)
        contract = ContractRegistry.validate(self.registry, payload)
        if contract.lane != "draft":
            raise ContractViolation(
                f"{contract.kind} is canonical-lane; use insert_record"
            )
        trace_id = payload[contract.id_field]
        _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION(cur,
            """
            INSERT INTO runtime_trace
              (trace_id, trace_kind, schema_hash, payload, payload_sha256,
               runtime_bundle_digest)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (trace_id, contract.kind, contract.schema_hash, Jsonb(payload), sha256_of(payload),
             self._bundle_digest(runtime_bundle_digest)),
        )
        return trace_id

    def insert_reference_data(self, cur, snapshot_ref: str, data_family: str,
                              payload: dict, *, artifact_ref: str | None = None,
                              source_digest: str | None = None,
                              parser_label: str | None = None,
                              record_count: int | None = None,
                              runtime_bundle_digest: str | None = None) -> None:
        """Persist store-backed external reference-data for a snapshot (M2 P1) —
        an index cache (NOT OFARM truth) so a scheme reader can resolve an
        imported snapshot's content from the store. The payload is opaque here;
        one row per (snapshot_ref, data_family)."""
        Store._require_active_governed_cursor(self, cur)
        _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION(cur,
            """
            INSERT INTO reference_snapshot_data
              (snapshot_ref, data_family, artifact_ref, source_digest,
               parser_label, record_count, payload, payload_sha256,
               runtime_bundle_digest)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (snapshot_ref, data_family, artifact_ref, source_digest, parser_label,
             record_count, Jsonb(payload), sha256_of(payload),
             self._bundle_digest(runtime_bundle_digest)),
        )

    def reference_data(self, data_family: str) -> list[dict]:
        """Store-backed reference-data rows of a family (snapshot_ref + payload),
        for a scheme reader to load into its lookup index."""
        with Store._read_cursor(self) as cur:
            _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
                "SELECT d.snapshot_ref, d.data_family, d.artifact_ref, "
                "d.source_digest, d.parser_label, d.record_count, d.payload, "
                "d.payload_sha256, d.runtime_bundle_digest "
                "FROM ONLY reference_snapshot_data d "
                "JOIN ONLY runtime_bundle b "
                "ON b.bundle_digest = d.runtime_bundle_digest "
                "WHERE d.data_family = %s AND b.tenant_ref = %s "
                "ORDER BY d.snapshot_ref",
                (data_family, self._bundle_tenant_ref()),
            )
            return cur.fetchall()

    def add_edge(self, cur, edge_type: str, src_record_id: str, dst_record_id: str,
                 *, runtime_bundle_digest: str | None = None) -> None:
        Store._require_active_governed_cursor(self, cur)
        _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION(cur,
            "INSERT INTO kernel_edge (edge_type, src_record_id, dst_record_id, "
            "runtime_bundle_digest) VALUES (%s, %s, %s, %s)",
            (edge_type, src_record_id, dst_record_id,
             self._bundle_digest(runtime_bundle_digest)),
        )

    def log_gate(
        self, cur, request_id: str, gate: str, outcome: str,
        *, reason_code: str | None = None, rationale: str | None = None,
        related_refs: list[str] | None = None,
        runtime_bundle_digest: str | None = None,
    ) -> None:
        Store._require_active_governed_cursor(self, cur)
        _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION(cur,
            """
            INSERT INTO kernel_gate_log
              (request_id, gate, outcome, reason_code, rationale, related_refs,
               runtime_bundle_digest)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (request_id, gate, outcome, reason_code, rationale,
             Jsonb(related_refs) if related_refs is not None else None,
             self._bundle_digest(runtime_bundle_digest)),
        )

    # -- idempotency (ingress boundary RFC §2.4) -------------------------------

    def idempotency_lookup(self, cur, key: str) -> dict | None:
        Store._require_active_governed_cursor(self, cur)
        _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
            "SELECT * FROM ONLY kernel_idempotency WHERE idempotency_key = %s", (key,))
        return cur.fetchone()

    def idempotency_claim(
        self, cur, key: str, request_id: str, source_payload_digest: str | None,
        result_record_id: str, *, runtime_bundle_digest: str | None = None,
    ) -> None:
        Store._require_active_governed_cursor(self, cur)
        _RETAINED_GOVERNED_CURSOR_EXECUTE_MUTATION(cur,
            """
            INSERT INTO kernel_idempotency
              (idempotency_key, request_id, source_payload_digest, result_record_id,
               runtime_bundle_digest)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (key, request_id, source_payload_digest, result_record_id,
             self._bundle_digest(runtime_bundle_digest)),
        )

    # -- reads -----------------------------------------------------------------

    def get_record(self, record_id: str) -> dict | None:
        with Store._read_cursor(self) as cur:
            _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
                "SELECT * FROM ONLY kernel_record WHERE record_id = %s", (record_id,))
            return cur.fetchone()

    def get_payload(self, record_id: str) -> dict | None:
        row = Store.get_record(self, record_id)
        return row["payload"] if row else None

    def record_exists(self, record_id: str) -> bool:
        return Store.get_record(self, record_id) is not None

    def find_by_kind(self, kind: str) -> list[dict]:
        with Store._read_cursor(self) as cur:
            _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
                "SELECT * FROM ONLY kernel_record WHERE record_kind = %s "
                "ORDER BY record_time, record_id",
                (kind,),
            )
            return cur.fetchall()

    def edges_from(self, record_id: str, edge_type: str | None = None) -> list[dict]:
        q = "SELECT * FROM ONLY kernel_edge WHERE src_record_id = %s"
        args: list = [record_id]
        if edge_type:
            q += " AND edge_type = %s"
            args.append(edge_type)
        with Store._read_cursor(self) as cur:
            _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(
                cur, q + " ORDER BY edge_id", args)
            return cur.fetchall()

    def edges_to(self, record_id: str, edge_type: str | None = None) -> list[dict]:
        q = "SELECT * FROM ONLY kernel_edge WHERE dst_record_id = %s"
        args: list = [record_id]
        if edge_type:
            q += " AND edge_type = %s"
            args.append(edge_type)
        with Store._read_cursor(self) as cur:
            _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(
                cur, q + " ORDER BY edge_id", args)
            return cur.fetchall()

    def is_superseded(self, record_id: str) -> bool:
        return bool(Store.edges_to(self, record_id, "LINEAGE_SUPERSEDES"))

    def in_force_consequences(self, farm_scope_ref: str,
                              as_of: str | None = None) -> list[dict]:
        """Accepted event consequences in force for a farm scope.

        In force NOW = payload says IN_FORCE and no LINEAGE_SUPERSEDES edge
        points at the record. With `as_of` (an ISO timestamp) the answer is
        reconstructed from the append-only substrate AS OF that moment on a
        SINGLE time axis — the server commit clock (`record_time`): a
        consequence counts if its record was committed by then and no
        LINEAGE_SUPERSEDES edge against it was committed by then. The record
        row and its supersession edge are written in one transaction and
        share that clock, so the reconstruction can never show a self-
        contradictory hole (or duplicate) at a supersession boundary. The
        payload's `acceptedAt` is a receipt of when acceptance was claimed —
        never the as-of selection key, which would mix the app clock with the
        edge's server clock and collapse Kernel rule 6 (times stay distinct).
        """
        with Store._read_cursor(self) as cur:
            if as_of is None:
                _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
                    """
                    SELECT r.* FROM ONLY kernel_record r
                    WHERE r.record_kind = 'ofarm.acceptedeventconsequence.v0.1'
                      AND r.payload ->> 'inForceState' = 'IN_FORCE'
                      AND r.payload -> 'anchorScopes' @> %s
                      AND NOT EXISTS (
                        SELECT 1 FROM ONLY kernel_edge e
                         WHERE e.dst_record_id = r.record_id
                           AND e.edge_type = 'LINEAGE_SUPERSEDES')
                    ORDER BY r.record_time, r.record_id
                    """,
                    (Jsonb([{"scopeType": "FARM", "scopeRef": farm_scope_ref}]),),
                )
            else:
                _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
                    """
                    SELECT r.* FROM ONLY kernel_record r
                    WHERE r.record_kind = 'ofarm.acceptedeventconsequence.v0.1'
                      AND r.payload ->> 'inForceState' = 'IN_FORCE'
                      AND r.payload -> 'anchorScopes' @> %s
                      AND r.record_time <= %s::timestamptz
                      AND NOT EXISTS (
                        SELECT 1 FROM ONLY kernel_edge e
                         WHERE e.dst_record_id = r.record_id
                           AND e.edge_type = 'LINEAGE_SUPERSEDES'
                           AND e.record_time <= %s::timestamptz)
                    ORDER BY r.record_time, r.record_id
                    """,
                    (Jsonb([{"scopeType": "FARM", "scopeRef": farm_scope_ref}]),
                     as_of, as_of),
                )
            return cur.fetchall()

    # -- conformance helpers ----------------------------------------------------

    def unreachable_authoritative_records(self) -> list[str]:
        """Records violating the reachability invariant (must always be [])."""
        with Store._read_cursor(self) as cur:
            _RETAINED_GOVERNED_CURSOR_EXECUTE_READ(cur,
                """
                SELECT r.record_id FROM ONLY kernel_record r
                WHERE r.record_kind = ANY(%s)
                  AND NOT EXISTS (
                    SELECT 1 FROM ONLY kernel_edge e
                     WHERE e.edge_type = 'PROMOTION_EMITS'
                       AND e.dst_record_id = r.record_id)
                ORDER BY r.record_id
                """,
                (list(AUTHORITATIVE_KINDS),),
            )
            return [row["record_id"] for row in cur.fetchall()]


_RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR = \
    Store._require_active_serialized_cursor
_RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR_CODE = \
    _RETAINED_STORE_REQUIRE_ACTIVE_SERIALIZED_CURSOR.__code__
_RETAINED_TRANSACTION_INTEGRITY_MARKER = \
    Store._mark_transaction_integrity_violation
_RETAINED_TRANSACTION_INTEGRITY_MARKER_CODE = \
    _RETAINED_TRANSACTION_INTEGRITY_MARKER.__code__
_STORE_DISPATCH_ANCHORS = _STORE_DISPATCH_SNAPSHOTTER()
