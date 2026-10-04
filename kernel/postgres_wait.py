"""Mechanical, owned waiting for pinned psycopg readiness generators."""
from __future__ import annotations

import math
import selectors
import time
from contextlib import contextmanager
from threading import Event


class PostgresWaitStopped(RuntimeError):
    pass


def checkpoint(deadline: float, cancel_event: Event | None) -> None:
    if (
        isinstance(deadline, bool)
        or not isinstance(deadline, (int, float))
        or not math.isfinite(deadline)
        or time.monotonic() >= deadline
        or (cancel_event is not None and cancel_event.is_set())
    ):
        raise PostgresWaitStopped("PostgreSQL observation stopped")


@contextmanager
def disposing(close):
    """Always clean up; an ordinary cleanup error cannot replace process control."""
    try:
        yield
    except BaseException as failure:
        try:
            close()
        except Exception:
            if isinstance(failure, Exception):
                raise
        raise
    else:
        close()


def wait(gen, fileno, deadline: float, cancel_event: Event | None = None):
    """Own the selector/generator; the caller owns any connection or result."""
    with disposing(gen.close):
        checkpoint(deadline, cancel_event)
        selector = None
        with disposing(lambda: selector.close() if selector is not None else None):
            selector = selectors.DefaultSelector()
            registered = None
            try:
                requested = next(gen)
                while True:
                    checkpoint(deadline, cancel_event)
                    fd = fileno()
                    if registered is not None:
                        selector.unregister(registered)
                        registered = None
                    selector.register(fd, int(requested))
                    registered = fd
                    ready = selector.select(min(0.05, max(0, deadline - time.monotonic())))
                    checkpoint(deadline, cancel_event)
                    flags = 0
                    for _, events in ready:
                        flags |= events
                    requested = gen.send(flags)
            except StopIteration as complete:
                # Resource-bearing completion already has its caller's owner.
                checkpoint(deadline, cancel_event)
                return complete.value
