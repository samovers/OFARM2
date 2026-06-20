"""M2 G6 — AS_OF reconstruction of the historical pack/profile/artifact-set spine.

Engineering tests, NOT part of the named conformance suite. They pin G6: with
real vintage history, AS_OF selects the spine vintage in force at the as-of time
(by each family's effective timestamp — ActiveArtifactSet.generatedAt,
PackActivationSet.evaluatedAt, AgronomicCodeBindingProfile.issuedAt); a future
vintage is never applied to an earlier state; and AS_OF still REFUSES (refuse
over pretend, Kernel rule 7) when no vintage is in force, when the latest is
ambiguous, or when the as-of time is unparseable. The single-of-each pilot spine
(no versioned history) is governed by the SAME time bound — it reconstructs when
it is in force, but a single future vintage is excluded and refused, never used
as-is just because it is the only record. Each vintage-history test runs on a
fresh DB so session-accumulated spine records cannot pollute the selection.
All identifiers fictional and format-true (privacy rule 1).
"""
from __future__ import annotations

import uuid

import pytest

from kernel import demo
from kernel.context import ContextAssembler, ContextNotReconstructible
from kernel.materializer import Materializer


def uid():
    return uuid.uuid4().hex[:8]


def _activation_vintage(store, evaluated_at: str) -> str:
    """Append a PackActivationSet vintage (a copy of the shipped one with a new id
    and the given evaluatedAt) — synthetic versioned history for AS_OF selection."""
    base = dict(store.find_by_kind("ofarm.packactivationset.v0.1")[0]["payload"])
    base["packActivationSetId"] = f"packactivationset:si.ffs.vintage.{uid()}"
    base["evaluatedAt"] = evaluated_at
    with store.tx() as cur:
        store.insert_record(cur, base)
    return base["packActivationSetId"]


def _asof(store, as_of: str):
    ca = ContextAssembler(store)
    with store.tx() as cur:
        return ca.assemble(cur, demo.FARM,
                           evaluation_time_policy={"policyType": "AS_OF", "asOfTime": as_of})


def _resolve_asof(store, as_of: str):
    with store.tx() as cur:
        return Materializer(store).resolve_for_use(
            cur, demo.FARM,
            time_policy={"policyType": "AS_OF", "asOfTime": as_of},
            recompute_if_needed=True)


# ---------------------------------------------------------------------------
# reconstruction: AS_OF selects the in-force vintage; future vintages excluded
# ---------------------------------------------------------------------------

def test_asof_reconstructs_the_in_force_activation_vintage(fresh_env):
    # The whole shipped pilot spine (artifact-set, profile, activation) is in
    # force only from 2026-06-13; the activation vintages below are dated AFTER
    # that so the other spine families stay reconstructible while we vary the
    # activation family. (At an earlier as-of the single artifact-set/profile
    # would themselves be future and the context would rightly refuse — see
    # test_asof_before_single_spine_effective_refuses.)
    store, _, _ = fresh_env
    shipped = store.find_by_kind(
        "ofarm.packactivationset.v0.1")[0]["payload"]["packActivationSetId"]   # evaluatedAt 2026-06-11
    v1 = _activation_vintage(store, "2026-07-01T00:00:00Z")
    v2 = _activation_vintage(store, "2026-08-01T00:00:00Z")

    def selected(as_of):
        return _asof(store, as_of)["sourcePackActivationSetRefs"]

    # only shipped (2026-06-11) is in force; v1 (07) and v2 (08) are FUTURE -> excluded
    assert selected("2026-06-15T00:00:00Z") == [shipped]
    # shipped + v1 in force -> the latest (v1) is selected
    assert selected("2026-07-15T00:00:00Z") == [v1]
    # all three in force -> the latest (v2, 2026-08) is selected
    assert selected("2026-09-01T00:00:00Z") == [v2]


def test_asof_single_spine_in_force_reconstructs(fresh_env):
    # one-of-each (no versioned history), AS_OF AFTER the spine is in force:
    # the single spine reconstructs (it IS in force at 2026-12)
    store, _, _ = fresh_env
    snap = _asof(store, "2026-12-01T00:00:00Z")
    assert snap["sourcePackActivationSetRefs"] and snap["activeArtifactSetRef"]


def test_asof_before_single_spine_effective_refuses(fresh_env):
    # one-of-each spine, AS_OF BEFORE it is effective (2025, before the M0/M1
    # cut): a single FUTURE vintage is NOT privileged to skip the time bound —
    # it is excluded and refused, never applied to an earlier state (rule 6).
    # resolve_for_use governs this to REFUSE_USE without crashing.
    store, _, _ = fresh_env
    r = _resolve_asof(store, "2025-01-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


def test_asof_reconstructs_via_resolve_for_use_recomputes(fresh_env):
    # the recompute-AS_OF path end-to-end: with a reconstructible history and
    # recompute permitted, resolve_for_use reaches recompute() (which assembles
    # the AS_OF spine a second time) and SUCCEEDS — it never crashes with an
    # uncaught ContextNotReconstructible (the assemble that gates it already
    # succeeded), it recomputes against the in-force vintage.
    store, _, _ = fresh_env
    _activation_vintage(store, "2026-07-01T00:00:00Z")
    _activation_vintage(store, "2026-08-01T00:00:00Z")
    r = _resolve_asof(store, "2026-09-01T00:00:00Z")
    assert r["decision"] == "RECOMPUTE_REQUIRED"
    assert r["recomputed"] is True
    assert not any(p["reasonCode"] == "MATERIALIZATION_INVALID" for p in r["problems"])


# ---------------------------------------------------------------------------
# refuse over pretend: no in-force vintage, ambiguous latest, unparseable as_of
# ---------------------------------------------------------------------------

def test_asof_before_any_vintage_refuses(fresh_env):
    store, _, _ = fresh_env
    _activation_vintage(store, "2026-01-01T00:00:00Z")
    _activation_vintage(store, "2026-03-01T00:00:00Z")
    # at 2025 none of the (now multiple) activation vintages is in force yet
    r = _resolve_asof(store, "2025-01-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


def test_asof_ambiguous_latest_vintage_refuses(fresh_env):
    store, _, _ = fresh_env
    # two activation vintages share the latest effective timestamp -> cannot pick
    # -> refuse. Dated 2026-08 (after the shipped artifact-set/profile are in
    # force at 2026-06-13) so the refusal is the activation AMBIGUITY, not some
    # other family being out of force.
    _activation_vintage(store, "2026-08-01T00:00:00Z")
    _activation_vintage(store, "2026-08-01T00:00:00Z")
    r = _resolve_asof(store, "2026-09-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


def test_asof_unparseable_time_refuses(fresh_env):
    store, _, _ = fresh_env
    with pytest.raises(ContextNotReconstructible):
        _asof(store, "not-a-timestamp")
