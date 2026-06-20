"""M2 G6 — AS_OF reconstruction of the historical pack/profile/artifact-set spine.

Engineering tests, NOT part of the named conformance suite. They pin G6: with
real vintage history, AS_OF selects the spine vintage in force at the as-of time
(by each family's effective timestamp — ActiveArtifactSet.generatedAt,
PackActivationSet.evaluatedAt, AgronomicCodeBindingProfile.issuedAt); a future
vintage is never applied to an earlier state; and AS_OF still REFUSES (refuse
over pretend, Kernel rule 7) when no vintage is in force, when the latest is
ambiguous, when the as-of time is unparseable, when the in-force profile vintage
is not ACTIVE, or when the independently time-selected families do NOT cohere
into a deployment that actually existed together (steward hostile re-review:
the ActiveArtifactSet is the derived artifact — it records the activation it was
generated from and the code-binding profile it deployed, so pairing it with a
different in-force activation/profile would synthesize a context that never was).

The ActiveArtifactSet, PackActivationSet and AgronomicCodeBindingProfile move as
one coherent deployment "generation", so the tests build generations with the
`_generation` helper (artifact generated FROM the activation, deploying that
code-binding profile) rather than mismatched copies. Each test runs on a fresh
DB so session-accumulated spine records cannot pollute selection. All identifiers
fictional and format-true (privacy rule 1).
"""
from __future__ import annotations

import uuid

import pytest

from kernel import demo
from kernel.context import ContextAssembler, ContextNotReconstructible
from kernel.materializer import Materializer


def uid():
    return uuid.uuid4().hex[:8]


def _shipped(store, kind):
    return dict(store.find_by_kind(kind)[0]["payload"])


def _activation_vintage(store, evaluated_at: str) -> str:
    """A bare PackActivationSet vintage (copy of the shipped one, fresh id + the
    given evaluatedAt). Bare = no matching artifact set regenerated from it, used
    to exercise ambiguity and incoherence."""
    act = _shipped(store, "ofarm.packactivationset.v0.1")
    act["packActivationSetId"] = f"{act['packActivationSetId']}.vintage.{uid()}"
    act["evaluatedAt"] = evaluated_at
    with store.tx() as cur:
        store.insert_record(cur, act)
    return act["packActivationSetId"]


def _generation(store, *, at: str, cb_state: str = "ACTIVE") -> dict:
    """Create a coherent deployment generation effective at `at` and return its
    ids. The ActiveArtifactSet is generated FROM this PackActivationSet
    (sourcePackActivationSetRefs) and deploys this AgronomicCodeBindingProfile
    (activeArtifactRefs), with matching activePackRefs/activeProfileRefs — so the
    three pass G6's spine-coherence check as one real deployment."""
    u = uid()
    cb = _shipped(store, "ofarm.agronomiccodebindingprofile.v0.1")
    cb_id = f"{cb['agronomicCodeBindingProfileId']}.gen.{u}"
    cb["agronomicCodeBindingProfileId"] = cb_id
    cb["issuedAt"] = at
    cb["profileState"] = cb_state

    act = _shipped(store, "ofarm.packactivationset.v0.1")
    act_id = f"{act['packActivationSetId']}.gen.{u}"
    act["packActivationSetId"] = act_id
    act["evaluatedAt"] = at

    art = _shipped(store, "ofarm.activeartifactset.v0.1")
    art_id = f"{art['activeArtifactSetId']}.gen.{u}"
    art["activeArtifactSetId"] = art_id
    art["generatedAt"] = at
    art["sourcePackActivationSetRefs"] = [act_id]
    art["activeArtifactRefs"] = [r for r in art["activeArtifactRefs"]
                                 if not r.startswith("codebindingprofile:")] + [cb_id]

    with store.tx() as cur:
        store.insert_record(cur, cb)
        store.insert_record(cur, act)
        store.insert_record(cur, art)
    return {"activation": act_id, "artifact": art_id, "codebinding": cb_id}


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
# reconstruction: AS_OF selects the in-force generation; future ones excluded
# ---------------------------------------------------------------------------

def test_asof_reconstructs_the_in_force_generation(fresh_env):
    store, _, _ = fresh_env
    g0 = _generation(store, at="2025-02-01T00:00:00Z")
    g1 = _generation(store, at="2025-06-01T00:00:00Z")
    g2 = _generation(store, at="2025-09-01T00:00:00Z")

    def selected(as_of):
        snap = _asof(store, as_of)
        return (snap["activeArtifactSetRef"], snap["sourcePackActivationSetRefs"])

    # only g0 in force; g1/g2 (and the shipped 2026-06 generation) are FUTURE
    assert selected("2025-03-01T00:00:00Z") == (g0["artifact"], [g0["activation"]])
    # g0 + g1 in force -> the latest (g1) is selected, coherently
    assert selected("2025-07-01T00:00:00Z") == (g1["artifact"], [g1["activation"]])
    # g0 + g1 + g2 in force -> the latest (g2) is selected, coherently
    assert selected("2025-10-01T00:00:00Z") == (g2["artifact"], [g2["activation"]])


def test_asof_single_spine_in_force_reconstructs(fresh_env):
    # the actual shipped single-of-each pilot deployment (one coherent generation),
    # AS_OF AFTER it is in force (all three families effective by 2026-06-12T21:17):
    # it reconstructs unchanged.
    store, _, _ = fresh_env
    snap = _asof(store, "2026-12-01T00:00:00Z")
    assert snap["sourcePackActivationSetRefs"] and snap["activeArtifactSetRef"]


# ---------------------------------------------------------------------------
# refuse over pretend: not-in-force, incoherent, ambiguous, unparseable, non-ACTIVE
# ---------------------------------------------------------------------------

def test_asof_before_any_generation_refuses(fresh_env):
    # the shipped deployment, AS_OF BEFORE any family is effective (everything is
    # 2026-06; 2025 predates it): a single FUTURE vintage is NOT privileged to skip
    # the time bound — it is excluded and refused, never applied to an earlier
    # state (rule 6). resolve_for_use governs this to REFUSE_USE without crashing.
    store, _, _ = fresh_env
    r = _resolve_asof(store, "2025-01-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


def test_asof_incoherent_artifact_activation_pairing_refuses(fresh_env):
    # steward regression: artifact generated from activation A0 -> later activation
    # A1 (bare, no artifact regenerated from it) -> AS_OF after A1 but before any
    # artifact set generated from A1. The latest artifact (from A0) and the latest
    # activation (A1) never formed a deployment together: refuse as not
    # reconstructible, NOT artifact(A0) + activation(A1).
    store, _, _ = fresh_env
    g0 = _generation(store, at="2025-02-01T00:00:00Z")
    a1 = _activation_vintage(store, "2025-06-01T00:00:00Z")
    assert a1 != g0["activation"]
    with pytest.raises(ContextNotReconstructible, match="incoherent"):
        _asof(store, "2025-07-01T00:00:00Z")
    # and it is governed to MATERIALIZATION_INVALID, never an uncaught error
    r = _resolve_asof(store, "2025-07-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


def test_asof_ambiguous_latest_vintage_refuses(fresh_env):
    # two activation vintages share the latest effective timestamp -> cannot pick
    # -> refuse. A coherent base generation keeps the other families in force, so
    # the refusal is the activation AMBIGUITY, not another family being out of force.
    store, _, _ = fresh_env
    _generation(store, at="2025-02-01T00:00:00Z")
    _activation_vintage(store, "2025-06-01T00:00:00Z")
    _activation_vintage(store, "2025-06-01T00:00:00Z")
    r = _resolve_asof(store, "2025-07-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


def test_asof_unparseable_time_refuses(fresh_env):
    store, _, _ = fresh_env
    with pytest.raises(ContextNotReconstructible):
        _asof(store, "not-a-timestamp")


def test_asof_non_active_profile_vintage_refuses(fresh_env):
    # a COHERENT generation whose code-binding profile vintage is DRAFT (non-ACTIVE):
    # the spine coheres, so the refusal is specifically the non-ACTIVE profile —
    # G6 selects it by issuedAt, then refuses rather than reconstructing a usable
    # context from a non-ACTIVE profile -> governed REFUSE_USE / MATERIALIZATION_INVALID,
    # NOT an uncaught 500. (NOW keeps the loud bootstrap RuntimeError; ERRATA E-007.)
    store, _, _ = fresh_env
    _generation(store, at="2025-02-01T00:00:00Z", cb_state="DRAFT")
    r = _resolve_asof(store, "2025-06-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


# ---------------------------------------------------------------------------
# the recompute-AS_OF path reconstructs end-to-end without an uncaught exception
# ---------------------------------------------------------------------------

def test_asof_reconstructs_via_resolve_for_use_recomputes(fresh_env):
    # with a reconstructible (coherent) history and recompute permitted,
    # resolve_for_use reaches recompute() (which assembles the AS_OF spine a second
    # time) and SUCCEEDS — it never crashes with an uncaught ContextNotReconstructible
    # (the gating assemble already succeeded); it recomputes the in-force generation.
    store, _, _ = fresh_env
    _generation(store, at="2025-02-01T00:00:00Z")
    _generation(store, at="2025-06-01T00:00:00Z")
    r = _resolve_asof(store, "2025-07-01T00:00:00Z")
    assert r["decision"] == "RECOMPUTE_REQUIRED"
    assert r["recomputed"] is True
    assert not any(p["reasonCode"] == "MATERIALIZATION_INVALID" for p in r["problems"])
