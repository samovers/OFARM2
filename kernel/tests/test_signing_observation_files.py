"""S1-08/09 local receipt storage: real kinds, bounded reads and disposal."""
from __future__ import annotations

import os
import threading
import time

import pytest

from kernel.signing_authority_io import read_signing_receipt
from kernel.signing_receipt import SIGNING_EVIDENCE_MAX_BYTES


def _closed(descriptors):
    assert descriptors
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)


def _capture_open(monkeypatch):
    import kernel.signing_authority_io as transport
    actual = os.open
    descriptors = []
    def capture(path, flags, *args, **kwargs):
        assert flags & os.O_NONBLOCK
        assert flags & os.O_CLOEXEC
        fd = actual(path, flags, *args, **kwargs)
        descriptors.append(fd)
        return fd
    monkeypatch.setattr(transport.os, "open", capture)
    return descriptors


def test_regular_receipt_is_reopened_after_atomic_replacement(tmp_path, monkeypatch):
    path = tmp_path / "receipt"
    path.write_bytes(b"first")
    descriptors = _capture_open(monkeypatch)
    assert read_signing_receipt(path, deadline=time.monotonic() + 1) == b"first"
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"second")
    replacement.replace(path)
    assert read_signing_receipt(path, deadline=time.monotonic() + 1) == b"second"
    assert len(descriptors) == 2
    _closed(descriptors)


def test_short_regular_file_reads_do_not_truncate_receipt(tmp_path, monkeypatch):
    import kernel.signing_authority_io as transport
    path = tmp_path / "receipt"
    contents = b"signed receipt bytes" * 20
    path.write_bytes(contents)
    actual = os.read
    monkeypatch.setattr(transport.os, "read", lambda fd, count: actual(fd, min(7, count)))
    assert read_signing_receipt(path, deadline=time.monotonic() + 1) == contents


@pytest.mark.parametrize("kind", ("fifo", "directory", "device"))
def test_nonregular_local_kinds_refuse_without_blocking_open(tmp_path, monkeypatch, kind):
    path = tmp_path / "receipt"
    if kind == "fifo":
        os.mkfifo(path)
    elif kind == "directory":
        path.mkdir()
    else:
        path.symlink_to("/dev/null")
    descriptors = _capture_open(monkeypatch)
    with pytest.raises((OSError, ValueError)) as retained:
        read_signing_receipt(path, deadline=time.monotonic() + 1)
    assert retained.value.__traceback__ is not None
    _closed(descriptors)


def test_symlink_to_healthy_local_regular_file_is_read(tmp_path):
    target = tmp_path / "regular"
    target.write_bytes(b"fixture")
    link = tmp_path / "receipt"
    link.symlink_to(target)
    assert read_signing_receipt(link, deadline=time.monotonic() + 1) == b"fixture"


@pytest.mark.parametrize("size", (0, SIGNING_EVIDENCE_MAX_BYTES + 1))
def test_bad_file_size_refuses_and_closes(tmp_path, monkeypatch, size):
    path = tmp_path / "receipt"
    path.write_bytes(b"x" * size)
    descriptors = _capture_open(monkeypatch)
    with pytest.raises((OSError, ValueError)):
        read_signing_receipt(path, deadline=time.monotonic() + 1)
    _closed(descriptors)


@pytest.mark.parametrize("failure", (OSError("read failed"), KeyboardInterrupt(), SystemExit()))
def test_read_failure_retained_traceback_does_not_retain_fd(tmp_path, monkeypatch, failure):
    import kernel.signing_authority_io as transport
    path = tmp_path / "receipt"
    path.write_bytes(b"fixture")
    descriptors = _capture_open(monkeypatch)
    def fail(_fd, _count):
        raise failure
    monkeypatch.setattr(transport.os, "read", fail)
    with pytest.raises(type(failure)) as retained:
        read_signing_receipt(path, deadline=time.monotonic() + 1)
    assert retained.value is failure
    _closed(descriptors)


def test_short_read_cannot_hide_oversized_tail_after_a_valid_signed_prefix(tmp_path, monkeypatch):
    import kernel.signing_authority_io as transport
    from kernel.tests._signing_support import (
        OBSERVER_PRIVATE_KEY, raw_public_key, receipt_payload, signed_receipt, signing_authority,
    )
    from kernel.signing_receipt import SigningEvidenceVerifier
    authority = signing_authority()
    prefix = signed_receipt(receipt_payload(authority))
    SigningEvidenceVerifier(raw_public_key(OBSERVER_PRIVATE_KEY)).verify(
        prefix, now_us=authority.observed_at_us,
    )
    path = tmp_path / "receipt"
    path.write_bytes(prefix + b" " * SIGNING_EVIDENCE_MAX_BYTES)
    actual = os.read
    monkeypatch.setattr(transport.os, "read", lambda fd, count: actual(fd, min(len(prefix), count)))
    with pytest.raises((OSError, ValueError)):
        read_signing_receipt(path, deadline=time.monotonic() + 1)


@pytest.mark.parametrize("stop_kind", ("deadline", "event"))
def test_repeated_delayed_short_reads_share_the_deadline_and_event(tmp_path, monkeypatch, stop_kind):
    import kernel.signing_authority_io as transport
    from kernel.postgres_wait import PostgresWaitStopped
    path = tmp_path / "receipt"
    path.write_bytes(b"x" * 1024)
    descriptors = _capture_open(monkeypatch)
    actual = os.read
    stop = threading.Event()
    calls = []
    def delayed(fd, count):
        calls.append(count)
        time.sleep(0.01)
        if stop_kind == "event":
            stop.set()
        return actual(fd, min(1, count))
    monkeypatch.setattr(transport.os, "read", delayed)
    started = time.monotonic()
    with pytest.raises(PostgresWaitStopped):
        read_signing_receipt(
            path, deadline=started + (0.035 if stop_kind == "deadline" else 1),
            cancel_event=stop,
        )
    assert time.monotonic() - started < 0.2
    assert len(calls) <= 5
    _closed(descriptors)


@pytest.mark.parametrize("control", (KeyboardInterrupt(), SystemExit()))
def test_process_control_survives_receipt_close_failure(tmp_path, monkeypatch, control):
    import kernel.signing_authority_io as transport
    path = tmp_path / "receipt"
    path.write_bytes(b"fixture")
    descriptors = _capture_open(monkeypatch)
    actual_close = os.close
    def fail_read(_fd, _count):
        raise control
    def close_then_fail(fd):
        actual_close(fd)
        raise OSError("receipt close failed after disposal")
    monkeypatch.setattr(transport.os, "read", fail_read)
    monkeypatch.setattr(transport.os, "close", close_then_fail)
    with pytest.raises(type(control)) as retained:
        read_signing_receipt(path, deadline=time.monotonic() + 1)
    assert retained.value is control
    _closed(descriptors)
