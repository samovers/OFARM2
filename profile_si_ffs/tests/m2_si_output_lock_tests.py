"""D6d — active SI output lock engineering tests.

These tests use the active SI pilot output surfaces to prove passport rendering
and inspection-register freeze paths serialize behind the single-writer lock.
They remain engineering tests, not platform MVP conformance evidence.
"""
from __future__ import annotations

import threading
import time

from kernel import context
from kernel.store import Store
from kernel.views import OutputGenerator
from profile_si_ffs.test_fixtures import demo


__all__ = [
    "test_g2_output_render_serializes_under_lock",
    "test_g2_freeze_serializes_under_lock",
]


def _require_advisory_lock_waiter(cur, waiting_pid, done, *, timeout=300):
    """Wait until PostgreSQL, not elapsed wall time, proves lock contention."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        cur.execute(
            """
            SELECT EXISTS (
              SELECT 1
              FROM pg_catalog.pg_locks waiter
              JOIN pg_catalog.pg_locks holder
                ON holder.locktype = waiter.locktype
               AND holder.database IS NOT DISTINCT FROM waiter.database
               AND holder.classid IS NOT DISTINCT FROM waiter.classid
               AND holder.objid IS NOT DISTINCT FROM waiter.objid
               AND holder.objsubid IS NOT DISTINCT FROM waiter.objsubid
              WHERE waiter.locktype = 'advisory'
                AND waiter.pid = %s
                AND waiter.granted = false
                AND holder.pid = pg_catalog.pg_backend_pid()
                AND holder.granted = true
            ) AS waiting
            """,
            (waiting_pid,),
        )
        if cur.fetchone()["waiting"]:
            return
        if done.wait(timeout=0.05):
            raise AssertionError(
                "governed output completed without waiting for the writer lock"
            )
    raise AssertionError(
        "governed output did not reach the writer-lock wait within the deadline"
    )


def test_g2_output_render_serializes_under_lock(store):
    # While connection A holds serialized_tx, a passport render on connection B
    # must block until A releases, not interleave with the write lock.
    a, b = Store(dsn=store.dsn), Store(dsn=store.dsn)
    context.bootstrap(b)
    waiting_pid = Store._raw_connection(b).info.backend_pid
    done = threading.Event()
    box = {}

    def render():
        try:
            box["result"] = OutputGenerator(b).passport_view(demo.FARM, demo.FARMER)
        except Exception as exc:
            box["err"] = repr(exc)
        finally:
            done.set()

    t = threading.Thread(target=render)
    try:
        with a.serialized_tx() as cur:
            t.start()
            _require_advisory_lock_waiter(cur, waiting_pid, done)
        assert done.wait(timeout=300), \
            "render did not complete after the writer lock was released"
        t.join(timeout=10)
        assert "err" not in box, box.get("err")
        assert box["result"] is not None
    finally:
        t.join(timeout=10)
        a.close()
        b.close()


def test_g2_freeze_serializes_under_lock(store):
    # While connection A holds serialized_tx, an inspection-register freeze on
    # connection B must block until A releases.
    a, b = Store(dsn=store.dsn), Store(dsn=store.dsn)
    context.bootstrap(b)
    waiting_pid = Store._raw_connection(b).info.backend_pid
    done = threading.Event()
    box = {}

    def freeze():
        try:
            box["result"] = OutputGenerator(b).freeze_inspection_register(
                demo.FARM, demo.FARMER, "2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z")
        except Exception as exc:
            box["err"] = repr(exc)
        finally:
            done.set()

    t = threading.Thread(target=freeze)
    try:
        with a.serialized_tx() as cur:
            t.start()
            _require_advisory_lock_waiter(cur, waiting_pid, done)
        assert done.wait(timeout=300), \
            "freeze did not complete after the writer lock was released"
        t.join(timeout=10)
        assert "err" not in box, box.get("err")
        assert box["result"] is not None
    finally:
        t.join(timeout=10)
        a.close()
        b.close()
