"""M2 G6 — AS_OF reconstruction of the historical pack/profile/artifact-set spine.

Engineering tests, NOT part of the named conformance suite. They pin G6: with
real vintage history, AS_OF selects the spine vintage in force at the as-of time
(by each family's effective timestamp — ActiveArtifactSet.generatedAt,
PackActivationSet.evaluatedAt, AgronomicCodeBindingProfile.issuedAt); a future
vintage is never applied to an earlier state; and AS_OF still REFUSES (refuse
over pretend, Kernel rule 7) when no vintage is in force, when the latest is
ambiguous, when the as-of time is unparseable, or when the in-force profile
vintage is not ACTIVE. The same time bound governs a single record and many —
a lone future vintage is excluded and refused, never used as-is just because it
is the only record.

The shipped pilot spine is single-of-each and effective only from mid-2026
(activation 2026-06-11, profile 2026-06-12, artifact-set 2026-06-12T21:17).
To test a family's vintage SELECTION in isolation, the family-selection tests
lay an explicit early full-spine baseline (one ACTIVE vintage of the other two
families) so those families stay in force across the window while we vary one
family — otherwise a refusal/selection could be attributed to the wrong family.
Each test runs on a fresh DB so session-accumulated spine records cannot pollute
the selection. All identifiers fictional and format-true (privacy rule 1).
"""
from __future__ import annotations

import uuid

import pytest

from kernel import demo
from kernel.context import ContextAssembler, ContextNotReconstructible
from kernel.materializer import Materializer


def uid():
    return uuid.uuid4().hex[:8]


def _vintage_copy(store, kind: str, id_field: str, **overrides) -> str:
    """Append a vintage of a spine family — a copy of the shipped record with a
    fresh id (suffix-appended so the id format is preserved) and the given field
    overrides (e.g. the effective timestamp). Synthetic versioned history for
    AS_OF selection."""
    base = dict(store.find_by_kind(kind)[0]["payload"])
    base[id_field] = f"{base[id_field]}.vintage.{uid()}"
    base.update(overrides)
    with store.tx() as cur:
        store.insert_record(cur, base)
    return base[id_field]


def _activation_vintage(store, evaluated_at: str) -> str:
    return _vintage_copy(store, "ofarm.packactivationset.v0.1",
                         "packActivationSetId", evaluatedAt=evaluated_at)


def _artifact_vintage(store, generated_at: str) -> str:
    return _vintage_copy(store, "ofarm.activeartifactset.v0.1",
                         "activeArtifactSetId", generatedAt=generated_at)


def _profile_vintage(store, issued_at: str, *, profile_state: str = "ACTIVE") -> str:
    return _vintage_copy(store, "ofarm.agronomiccodebindingprofile.v0.1",
                         "agronomicCodeBindingProfileId",
                         issuedAt=issued_at, profileState=profile_state)


def _baseline_other_families(store, at: str = "2025-01-01T00:00:00Z") -> None:
    """Lay an early ACTIVE artifact-set and profile vintage so those two families
    stay in force across the test window; the activation family is then varied in
    isolation. (Not activation — the test controls that family explicitly.)"""
    _artifact_vintage(store, at)
    _profile_vintage(store, at)


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
    # Early baseline keeps artifact-set + profile in force across the window, so
    # what we observe is purely the activation family's vintage selection.
    store, _, _ = fresh_env
    _baseline_other_families(store, "2025-01-01T00:00:00Z")
    a0 = _activation_vintage(store, "2025-02-01T00:00:00Z")
    a1 = _activation_vintage(store, "2025-06-01T00:00:00Z")
    a2 = _activation_vintage(store, "2025-09-01T00:00:00Z")

    def selected(as_of):
        return _asof(store, as_of)["sourcePackActivationSetRefs"]

    # only a0 is in force; a1/a2 (and the shipped 2026-06) are FUTURE -> excluded
    assert selected("2025-03-01T00:00:00Z") == [a0]
    # a0 + a1 in force -> the latest (a1) is selected
    assert selected("2025-07-01T00:00:00Z") == [a1]
    # a0 + a1 + a2 in force -> the latest (a2) is selected
    assert selected("2025-10-01T00:00:00Z") == [a2]


def test_asof_single_spine_in_force_reconstructs(fresh_env):
    # the actual shipped single-of-each pilot spine (no added history), AS_OF
    # AFTER it is in force (all three families effective by 2026-06-12T21:17):
    # the single spine reconstructs unchanged.
    store, _, _ = fresh_env
    snap = _asof(store, "2026-12-01T00:00:00Z")
    assert snap["sourcePackActivationSetRefs"] and snap["activeArtifactSetRef"]


# ---------------------------------------------------------------------------
# refuse over pretend: not-in-force, ambiguous latest, unparseable, non-ACTIVE
# ---------------------------------------------------------------------------

def test_asof_before_single_spine_effective_refuses(fresh_env):
    # the shipped single-of-each spine, AS_OF BEFORE any family is effective
    # (everything is 2026-06; 2025 predates it): a single FUTURE vintage is NOT
    # privileged to skip the time bound — it is excluded and refused, never
    # applied to an earlier state (rule 6). resolve_for_use governs this to
    # REFUSE_USE without crashing.
    store, _, _ = fresh_env
    r = _resolve_asof(store, "2025-01-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


def test_asof_no_in_force_activation_vintage_refuses(fresh_env):
    # artifact-set + profile in force early (2025-01); the activation family's
    # earliest vintage is the shipped 2026-06-11, so at 2025-06 the OTHER two
    # families reconstruct but the activation family has NO vintage in force ->
    # the per-family refusal is specifically the activation family (match=), not
    # a coincidental out-of-force family.
    store, _, _ = fresh_env
    _baseline_other_families(store, "2025-01-01T00:00:00Z")
    with pytest.raises(ContextNotReconstructible, match="PackActivationSet"):
        _asof(store, "2025-06-01T00:00:00Z")


def test_asof_ambiguous_latest_vintage_refuses(fresh_env):
    # two activation vintages share the latest effective timestamp -> cannot pick
    # -> refuse. Baseline keeps the other families in force so the refusal is the
    # activation AMBIGUITY, not another family being out of force.
    store, _, _ = fresh_env
    _baseline_other_families(store, "2025-01-01T00:00:00Z")
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
    # the profile vintage in force at as_of is non-ACTIVE (a DRAFT issued after
    # the ACTIVE baseline): G6 selects it by issuedAt, then refuses rather than
    # reconstructing a usable context from a non-ACTIVE profile -> governed
    # REFUSE_USE / MATERIALIZATION_INVALID, NOT an uncaught 500. (NOW keeps the
    # loud bootstrap RuntimeError; ERRATA E-007.)
    store, _, _ = fresh_env
    _artifact_vintage(store, "2025-01-01T00:00:00Z")
    _activation_vintage(store, "2025-01-01T00:00:00Z")
    _profile_vintage(store, "2025-01-01T00:00:00Z", profile_state="ACTIVE")
    _profile_vintage(store, "2025-03-01T00:00:00Z", profile_state="DRAFT")  # latest <= bound
    r = _resolve_asof(store, "2025-06-01T00:00:00Z")
    assert r["decision"] == "REFUSE_USE"
    assert r["problems"][0]["reasonCode"] == "MATERIALIZATION_INVALID"


# ---------------------------------------------------------------------------
# the recompute-AS_OF path reconstructs end-to-end without an uncaught exception
# ---------------------------------------------------------------------------

def test_asof_reconstructs_via_resolve_for_use_recomputes(fresh_env):
    # with a reconstructible history and recompute permitted, resolve_for_use
    # reaches recompute() (which assembles the AS_OF spine a second time) and
    # SUCCEEDS — it never crashes with an uncaught ContextNotReconstructible
    # (the gating assemble already succeeded); it recomputes the in-force vintage.
    store, _, _ = fresh_env
    _baseline_other_families(store, "2025-01-01T00:00:00Z")
    _activation_vintage(store, "2025-06-01T00:00:00Z")
    _activation_vintage(store, "2025-09-01T00:00:00Z")
    r = _resolve_asof(store, "2025-10-01T00:00:00Z")
    assert r["decision"] == "RECOMPUTE_REQUIRED"
    assert r["recomputed"] is True
    assert not any(p["reasonCode"] == "MATERIALIZATION_INVALID" for p in r["problems"])
