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

import json
import uuid
from contextlib import contextmanager

import pytest

from kernel import config, context, demo
from kernel.context import ContextAssembler, ContextNotReconstructible
from kernel.materializer import Materializer
from kernel.store import Store


def uid():
    return uuid.uuid4().hex[:8]


def _shipped(store, kind):
    rows = store.find_by_kind(kind)
    if rows:
        return dict(rows[0]["payload"])
    for component in store.runtime_bundle.components:
        if component.role != "PROFILE_INSTANCE":
            continue
        payload = json.loads(component.canonical_bytes)
        if payload.get("schemaVersion") == kind:
            return payload
    raise AssertionError(f"missing shipped profile instance {kind}")


def _activation_vintage(store, evaluated_at: str) -> str:
    """A bare PackActivationSet vintage (copy of the shipped one, fresh id + the
    given evaluatedAt). Bare = no matching artifact set regenerated from it, used
    to exercise ambiguity and incoherence."""
    act = _shipped(store, "ofarm.packactivationset.v0.1")
    act["packActivationSetId"] = f"{act['packActivationSetId']}.vintage.{uid()}"
    act["evaluatedAt"] = evaluated_at
    with store.serialized_tx() as cur:
        store.insert_record(cur, act)
    return act["packActivationSetId"]


def _generation(store, *, at: str, cb_state: str = "ACTIVE",
                tenant_ref: str = config.TENANT_REF) -> dict:
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
    act["targetScope"] = {"scopeType": "TENANT", "scopeRef": tenant_ref}

    art = _shipped(store, "ofarm.activeartifactset.v0.1")
    art_id = f"{art['activeArtifactSetId']}.gen.{u}"
    art["activeArtifactSetId"] = art_id
    art["generatedAt"] = at
    art["deploymentScope"] = {"scopeType": "TENANT", "scopeRef": tenant_ref}
    art["sourcePackActivationSetRefs"] = [act_id]
    art["activeArtifactRefs"] = [r for r in art["activeArtifactRefs"]
                                 if not r.startswith("codebindingprofile:")] + [cb_id]

    with store.serialized_tx() as cur:
        store.insert_record(cur, cb, tenant_ref=tenant_ref)
        store.insert_record(cur, act, tenant_ref=tenant_ref)
        store.insert_record(cur, art, tenant_ref=tenant_ref)
    return {"activation": act_id, "artifact": art_id, "codebinding": cb_id}


@contextmanager
def _rebundled(store):
    """Start a new runtime so newly appended historical rows are selected."""
    runtime = Store(dsn=store.dsn)
    try:
        context.bootstrap(runtime)
        yield runtime
    finally:
        runtime.close()


def _asof(store, as_of: str):
    with _rebundled(store) as runtime:
        ca = ContextAssembler(runtime)
        with runtime.serialized_tx() as cur:
            return ca.assemble(
                cur, demo.FARM,
                evaluation_time_policy={"policyType": "AS_OF", "asOfTime": as_of})


def _resolve_asof(store, as_of: str):
    with _rebundled(store) as runtime:
        with runtime.serialized_tx() as cur:
            return Materializer(runtime).resolve_for_use(
                cur, demo.FARM,
                time_policy={"policyType": "AS_OF", "asOfTime": as_of},
                recompute_if_needed=True)


# ---------------------------------------------------------------------------
# reconstruction: AS_OF selects the in-force generation; future ones excluded
# ---------------------------------------------------------------------------

def test_asof_reconstructs_the_in_force_generation(fresh_store):
    store = fresh_store
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


def test_asof_ignores_newer_unrelated_profile_spine(fresh_store):
    store = fresh_store
    g0 = _generation(store, at="2025-02-01T00:00:00Z")
    other_pack = "pack:test.unrelated.v0_1"
    other_profile = "profile:test.unrelated.v0_1"
    cb = _shipped(store, "ofarm.agronomiccodebindingprofile.v0.1")
    cb["agronomicCodeBindingProfileId"] = f"codebindingprofile:test.unrelated.{uid()}"
    cb["issuedAt"] = "2025-12-01T00:00:00Z"
    cb["profileScope"]["packRefs"] = [other_pack]
    act = _shipped(store, "ofarm.packactivationset.v0.1")
    act["packActivationSetId"] = f"packactivationset:test.unrelated.{uid()}"
    act["evaluatedAt"] = "2025-12-01T00:00:00Z"
    act["activePackRefs"] = [other_pack]
    act["activeProfileRefs"] = [other_profile]
    art = _shipped(store, "ofarm.activeartifactset.v0.1")
    art["activeArtifactSetId"] = f"activeartifactset:test.unrelated.{uid()}"
    art["generatedAt"] = "2025-12-01T00:00:00Z"
    art["activePackRefs"] = [other_pack]
    art["activeProfileRefs"] = [other_profile]
    art["sourcePackActivationSetRefs"] = [act["packActivationSetId"]]
    art["activeArtifactRefs"] = [
        ref for ref in art["activeArtifactRefs"]
        if not ref.startswith("codebindingprofile:")
    ] + [cb["agronomicCodeBindingProfileId"]]
    with store.serialized_tx() as cur:
        store.insert_record(cur, cb)
        store.insert_record(cur, act)
        store.insert_record(cur, art)

    snap = _asof(store, "2026-01-01T00:00:00Z")
    assert snap["activeArtifactSetRef"] == g0["artifact"]
    assert snap["sourcePackActivationSetRefs"] == [g0["activation"]]


def test_asof_rejects_same_pack_profile_generation_for_other_tenant(fresh_store):
    store = fresh_store
    g0 = _generation(store, at="2025-02-01T00:00:00Z")
    with pytest.raises(RuntimeError, match="exactly match the verified RuntimeBundle tenant"):
        _generation(
            store, at="2025-12-01T00:00:00Z",
            tenant_ref="tenant:issue171.other")

    snap = _asof(store, "2026-01-01T00:00:00Z")
    assert snap["activeArtifactSetRef"] == g0["artifact"]
    assert snap["sourcePackActivationSetRefs"] == [g0["activation"]]


def test_asof_ignores_same_pack_codebinding_never_deployed_by_artifact_set(fresh_store):
    store = fresh_store
    g0 = _generation(store, at="2025-02-01T00:00:00Z")
    sibling = _shipped(store, "ofarm.agronomiccodebindingprofile.v0.1")
    sibling["agronomicCodeBindingProfileId"] = (
        f"codebindingprofile:si.ffs.undeployed.{uid()}")
    sibling["issuedAt"] = "2025-12-01T00:00:00Z"
    with store.serialized_tx() as cur:
        store.insert_record(cur, sibling)

    snap = _asof(store, "2026-01-01T00:00:00Z")
    assert snap["activeArtifactSetRef"] == g0["artifact"]
    assert snap["sourcePackActivationSetRefs"] == [g0["activation"]]


def test_asof_single_spine_in_force_reconstructs(fresh_store):
    # the actual shipped single-of-each pilot deployment (one coherent generation),
    # AS_OF well AFTER it is in force (the shipped spine is effective in mid-2026 —
    # the exact artifact-set generatedAt moves on each P6 regeneration): it
    # reconstructs unchanged.
    store = fresh_store
    snap = _asof(store, "2026-12-01T00:00:00Z")
    assert snap["sourcePackActivationSetRefs"] and snap["activeArtifactSetRef"]


# ---------------------------------------------------------------------------
# refuse over pretend: not-in-force, incoherent, ambiguous, unparseable, non-ACTIVE
# ---------------------------------------------------------------------------

def test_asof_before_any_generation_refuses(fresh_store):
    # the shipped deployment, AS_OF BEFORE any family is effective (everything is
    # 2026-06; 2025 predates it): a single FUTURE vintage is NOT privileged to skip
    # the time bound — it is excluded and refused, never applied to an earlier
    # state (rule 6). resolve_for_use governs this to REFUSE_USE without crashing.
    store = fresh_store
    r = _resolve_asof(store, "2025-01-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


def test_asof_incoherent_artifact_activation_pairing_refuses(fresh_store):
    # steward regression: artifact generated from activation A0 -> later activation
    # A1 (bare, no artifact regenerated from it) -> AS_OF after A1 but before any
    # artifact set generated from A1. The latest artifact (from A0) and the latest
    # activation (A1) never formed a deployment together: refuse as not
    # reconstructible, NOT artifact(A0) + activation(A1).
    store = fresh_store
    g0 = _generation(store, at="2025-02-01T00:00:00Z")
    a1 = _activation_vintage(store, "2025-06-01T00:00:00Z")
    assert a1 != g0["activation"]
    with pytest.raises(ContextNotReconstructible, match="incoherent"):
        _asof(store, "2025-07-01T00:00:00Z")
    # and it is governed to MATERIALIZATION_INVALID, never an uncaught error
    r = _resolve_asof(store, "2025-07-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


def test_asof_artifact_without_source_activation_refuses(fresh_store):
    # an ActiveArtifactSet that records NO source PackActivationSet (empty list)
    # cannot be reconciled with any in-force activation: refuse rather than pair
    # on unverifiable provenance. The empty list is falsy and must not silently
    # skip the source-inclusion check. Built coherent with g0 in every OTHER way
    # (same packs/profiles, references g0's code-binding profile) so the refusal
    # isolates the empty-source check, not a coincidental other mismatch.
    store = fresh_store
    g0 = _generation(store, at="2025-02-01T00:00:00Z")
    art = next(dict(r["payload"]) for r in store.find_by_kind("ofarm.activeartifactset.v0.1")
               if r["payload"]["activeArtifactSetId"] == g0["artifact"])
    art["activeArtifactSetId"] = f"{art['activeArtifactSetId']}.nosrc.{uid()}"
    art["generatedAt"] = "2025-06-01T00:00:00Z"   # latest -> selected at 2025-07
    art["sourcePackActivationSetRefs"] = []
    with store.serialized_tx() as cur:
        store.insert_record(cur, art)
    with pytest.raises(
            ContextNotReconstructible,
            match="has no retained source activation set"):
        _asof(store, "2025-07-01T00:00:00Z")


def test_asof_historical_artifact_with_unknown_active_ref_refuses_startup(fresh_store):
    store = fresh_store
    g0 = _generation(store, at="2025-02-01T00:00:00Z")
    art = next(dict(row["payload"]) for row in store.find_by_kind(
        "ofarm.activeartifactset.v0.1")
        if row["payload"]["activeArtifactSetId"] == g0["artifact"])
    art["activeArtifactSetId"] = f"{art['activeArtifactSetId']}.unknown.{uid()}"
    art["generatedAt"] = "2025-06-01T00:00:00Z"
    art["activeArtifactRefs"].append("queryplan:test.unknown.v0_1")
    with store.serialized_tx() as cur:
        store.insert_record(cur, art)
    with pytest.raises(
            ContextNotReconstructible,
            match="does not resolve to byte-identical components"):
        _asof(store, "2025-07-01T00:00:00Z")


def test_asof_ambiguous_latest_vintage_refuses(fresh_store):
    # two activation vintages share the latest effective timestamp -> cannot pick
    # -> refuse. A coherent base generation keeps the other families in force, so
    # the refusal is the activation AMBIGUITY, not another family being out of force.
    store = fresh_store
    _generation(store, at="2025-02-01T00:00:00Z")
    _activation_vintage(store, "2025-06-01T00:00:00Z")
    _activation_vintage(store, "2025-06-01T00:00:00Z")
    r = _resolve_asof(store, "2025-07-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


def test_asof_unparseable_time_refuses(fresh_store):
    store = fresh_store
    with pytest.raises(ContextNotReconstructible):
        _asof(store, "not-a-timestamp")


def test_asof_non_active_profile_vintage_refuses(fresh_store):
    # a COHERENT generation whose code-binding profile vintage is DRAFT (non-ACTIVE):
    # the spine coheres, so the refusal is specifically the non-ACTIVE profile —
    # G6 selects it by issuedAt, then refuses rather than reconstructing a usable
    # context from a non-ACTIVE profile -> governed REFUSE_USE / MATERIALIZATION_INVALID,
    # NOT an uncaught 500. (NOW keeps the loud bootstrap RuntimeError; ERRATA E-007.)
    store = fresh_store
    _generation(store, at="2025-02-01T00:00:00Z", cb_state="DRAFT")
    r = _resolve_asof(store, "2025-06-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


# ---------------------------------------------------------------------------
# the recompute-AS_OF path reconstructs end-to-end without an uncaught exception
# ---------------------------------------------------------------------------

def test_asof_reconstructs_via_resolve_for_use_recomputes(fresh_store):
    # with a reconstructible (coherent) history and recompute permitted,
    # resolve_for_use reaches recompute() (which assembles the AS_OF spine a second
    # time) and SUCCEEDS — it never crashes with an uncaught ContextNotReconstructible
    # (the gating assemble already succeeded); it recomputes the in-force generation.
    store = fresh_store
    _generation(store, at="2025-02-01T00:00:00Z")
    _generation(store, at="2025-06-01T00:00:00Z")
    r = _resolve_asof(store, "2025-07-01T00:00:00Z")
    assert r["decision"] == "RECOMPUTE_REQUIRED"
    assert r["recomputed"] is True
    assert not any(p["reasonCode"] == "MATERIALIZATION_INVALID" for p in r["problems"])
