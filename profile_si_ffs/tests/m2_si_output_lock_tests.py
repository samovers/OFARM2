"""D6d — active SI output lock engineering tests.

These tests use the active SI pilot output surfaces to prove passport rendering
and inspection-register freeze paths serialize behind the single-writer lock.
They remain engineering tests, not platform MVP conformance evidence.
"""
from __future__ import annotations

import threading

from kernel.runtime_activation import complete_store_startup
from kernel.store import Store
from kernel.views import OutputGenerator
from profile_si_ffs.test_fixtures import demo


__all__ = [
    "test_g2_output_render_serializes_under_lock",
    "test_g2_freeze_serializes_under_lock",
]


def test_g2_output_render_serializes_under_lock(store):
    # While connection A holds serialized_tx, a passport render on connection B
    # must block until A releases, not interleave with the write lock.
    a = Store(
        dsn=store.dsn,
        tenant_ref=store.tenant_ref,
        runtime_bundle=store.runtime_bundle,
        active_descriptor=store.active_descriptor,
    )
    b = Store(
        dsn=store.dsn,
        tenant_ref=store.tenant_ref,
        runtime_bundle=store.runtime_bundle,
        active_descriptor=store.active_descriptor,
    )
    done = threading.Event()
    box = {}
    complete_store_startup(b)

    def render():
        try:
            box["result"] = OutputGenerator(b).passport_view(demo.FARM, demo.FARMER)
        except Exception as exc:
            box["err"] = repr(exc)
        finally:
            done.set()

    t = threading.Thread(target=render)
    try:
        with a.serialized_tx():
            t.start()
            assert not done.wait(timeout=0.6), \
                "passport render must serialize behind the single-writer lock, not interleave"
        t.join(timeout=10)
        assert done.is_set(), "render did not complete after the lock was released"
        assert "err" not in box, box.get("err")
        assert box["result"] is not None
    finally:
        t.join(timeout=10)
        a.close()
        b.close()


def test_g2_freeze_serializes_under_lock(store):
    # While connection A holds serialized_tx, an inspection-register freeze on
    # connection B must block until A releases.
    a = Store(
        dsn=store.dsn,
        tenant_ref=store.tenant_ref,
        runtime_bundle=store.runtime_bundle,
        active_descriptor=store.active_descriptor,
    )
    b = Store(
        dsn=store.dsn,
        tenant_ref=store.tenant_ref,
        runtime_bundle=store.runtime_bundle,
        active_descriptor=store.active_descriptor,
    )
    done = threading.Event()
    box = {}
    complete_store_startup(b)

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
        with a.serialized_tx():
            t.start()
            assert not done.wait(timeout=0.6), \
                "freeze must serialize behind the single-writer lock, not interleave"
        t.join(timeout=10)
        assert done.is_set() and "err" not in box, box.get("err")
        assert box["result"] is not None
    finally:
        t.join(timeout=10)
        a.close()
        b.close()
