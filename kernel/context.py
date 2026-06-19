"""Context spine: SI profile instances, reference snapshots, per-farm
ContextSnapshot assembly (PACK_PROFILE_APPLICABILITY gate support).

Static profile applicability (M1 brief task 3): the pilot runs one pack, one
profile, no overlap (PROFILE.md). ContextSnapshots are assembled from the
shipped instances; per the ContextSnapshot Closure RFC an existing snapshot is
reused while the governing context is materially the same and a NEW snapshot
is minted on basis drift (new reference snapshot version, policy change …).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from . import config
from .contracts import canonical_json

PROFILE_INSTANCE_FILES = [
    "OFARM_AgronomicCodeBindingProfile_si_ffs_v0_1.json",
    "OFARM_PackActivationSet_example_si_ffs_pilot_v0_1.json",
    "OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json",
    "OFARM_ContextSnapshot_example_si_ffs_pilot_compliance_v0_1.json",
    "OFARM_ReferenceSnapshot_example_si_uvhvvr_ffs_reg_2026-06-11.json",
    "OFARM_ReferenceSnapshot_example_si_gerk_layer_2025-06-30.json",
]

REGSR_SNAPSHOT_PREFIX = "referencesnapshot:si.uvhvvr.ffs-reg"
GERK_SNAPSHOT_PREFIX = "referencesnapshot:si.mkgp.gerk-layer"
# store-backed reference-data family for REGSR parsed product data (M2 P1): the
# data_family a governed REGSR import tags its parsed data with, and the family
# ProductRegister loads from the store. ProductRegister is already REGSR-shaped
# (lookup_by_decision, D9), so this REGSR-specific constant lives with it.
REGSR_DATA_FAMILY = "si.uvhvvr.ffs-reg"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def mint(prefix: str) -> str:
    """The kernel's single id-minting helper (id-safe, pattern-conformant)."""
    import uuid
    return f"{prefix}:{uuid.uuid4().hex[:16]}"


def parse_ts(value) -> datetime | None:
    """Timezone-aware timestamp parse; None on junk — never a guess.
    String comparison of mixed timezone spellings is fail-open; every
    temporal comparison in the kernel goes through here instead."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def bootstrap(store) -> list[str]:
    """Load the shipped SI profile instances into the store (idempotent).

    These are package-validated instances (conformance self-check), inserted
    verbatim — never edited (AGENTS.md rule 4).
    """
    inserted = []
    for name in PROFILE_INSTANCE_FILES:
        payload = json.loads((config.PROFILE_ROOT / name).read_text())
        contract = store.registry.get(payload["schemaVersion"])
        record_id = payload[contract.id_field]
        if store.record_exists(record_id):
            continue
        with store.tx() as cur:
            store.insert_record(cur, payload)
        inserted.append(record_id)
    return inserted


def current_reference_snapshot(store, prefix: str,
                               as_of: str | None = None) -> dict | None:
    """The in-force reference snapshot of a family = the latest `effectiveFrom`
    that is actually IN FORCE at the selection bound.

    The bound is `as_of` (AS_OF) or the current time (NOW). A snapshot is in
    force at the bound iff `effectiveFrom <= bound` AND (no `effectiveUntil`, or
    `bound < effectiveUntil`). So a future-effective vintage is never selected
    as current — for NOW or for an earlier AS_OF — and an expired snapshot is
    never in force (PR #11 review). `prefix` is a FAMILY boundary, matched at the
    family root or its '.' delimiter (not a bare string prefix), so a sibling
    family that shares leading characters never collides. None means no snapshot
    of this family was in force at that moment. An unparseable bound (junk
    as_of) selects nothing (fail closed)."""
    rows = store.find_by_kind("ofarm.referencesnapshot.v0.1")
    bound = parse_ts(as_of) if as_of else parse_ts(now_iso())
    if bound is None:
        return None   # unparseable as_of: refuse to guess
    candidates = []
    for r in rows:
        p = r["payload"]
        sid = p["referenceSnapshotId"]
        # family boundary (PR #11 review): a sibling family must not collide by
        # shared leading characters — '...ffs-reg' must not match
        # '...ffs-regression'. Match the family root exactly or up to its '.'
        # delimiter, never as a bare string prefix.
        if not (sid == prefix or sid.startswith(prefix + ".")):
            continue
        eff = parse_ts(p["effectiveFrom"])
        if eff is None or eff > bound:
            continue   # unparseable (fail closed) or not yet effective at the bound
        until = parse_ts(p["effectiveUntil"]) if p.get("effectiveUntil") else None
        if until is not None and bound >= until:
            continue   # expired at the bound — no longer in force
        candidates.append((eff, sid, p))
    if not candidates:
        return None
    # latest effectiveFrom wins; ties break deterministically by snapshot id
    # (content-stable — never dependent on row insertion order)
    return max(candidates, key=lambda c: (c[0], c[1]))[2]


class ProductRegister:
    """Offline product-register lookup for the in-force REGSR snapshots.

    Snapshot artifacts are dated parses of the official HTML surface
    (D9: no official export exists — posture declared, never hidden).
    Tests may register synthetic, clearly-fictional snapshot data through
    the same path; the runtime itself only ever reads registered artifacts.
    """

    def __init__(self):
        self._by_snapshot: dict[str, dict] = {}
        # the shipped real parse (623 products, fictional-free: public register data)
        shipped = config.PROFILE_ROOT / "examples" / "regsr_snapshot_2026-06-12.json"
        if shipped.exists():
            self.register_artifact(config.SHIPPED_REGSR_SNAPSHOT_REF,
                                   json.loads(shipped.read_text()))

    def register_artifact(self, snapshot_id: str, artifact: dict) -> None:
        products = {p["regsrCode"]: p for p in artifact.get("products", [])}
        details = {d.get("regsrCode"): d for d in artifact.get("productDetails", [])}
        # D9: the binding identity is the decision number (stevilka odlocbe)
        # + validity dates; regsrCode is a page locator, never identity. The
        # public list surface carries no decision numbers — only detail pages
        # do — so identity-confirmable lookups exist only where detail data
        # was parsed. That asymmetry is surfaced, never papered over. The
        # decision number is NOT, on its own, a complete identity, so index a
        # LIST per decision number; duplicates with differing validity are
        # never silently collapsed (resolved at lookup time, PR #12 hostile B2).
        by_decision: dict[str, list] = {}
        for d in artifact.get("productDetails", []):
            for decision in d.get("decisions", []):
                number = decision.get("decisionNumber")
                if number:
                    by_decision.setdefault(number, []).append({**d, "decision": decision})
        self._by_snapshot[snapshot_id] = {
            "products": products, "details": details, "byDecision": by_decision,
        }

    def load_from_store(self, store) -> None:
        """Resolve register data for the REGSR snapshots.

        Two sources, in order: (1) store-backed reference data persisted by a
        governed import (M2 P1) — so a SCHEDULED-import snapshot's content is
        resolvable from the store, not only from committed package files; then
        (2) the committed package-file fallback for shipped snapshots, which
        names its artifact in sourceArtifactRefs. The runtime never guesses."""
        for row in store.reference_data(REGSR_DATA_FAMILY):
            sid = row["snapshot_ref"]
            if sid not in self._by_snapshot:
                self.register_artifact(sid, row["payload"])
        for row in store.find_by_kind("ofarm.referencesnapshot.v0.1"):
            payload = row["payload"]
            sid = payload["referenceSnapshotId"]
            if not sid.startswith(REGSR_SNAPSHOT_PREFIX) or sid in self._by_snapshot:
                continue
            for ref in payload.get("sourceArtifactRefs", []):
                if ref.startswith("artifact:"):
                    path = config.PROFILE_ROOT / "examples" / ref.split(":", 1)[1]
                    if path.exists():
                        self.register_artifact(sid, json.loads(path.read_text()))

    def identities_by_decision(self, snapshot_id: str, decision_number: str) -> list[dict]:
        """The DISTINCT D9 identities for a decision number — one record per
        distinct (issued, validUntil) validity window. True duplicates of one
        authorisation count once; the same decision number with *differing*
        validity yields more than one (the decision number alone is ambiguous,
        which callers route to review). Empty when not confirmable on this
        surface — which is NOT the same as 'withdrawn'."""
        data = self._by_snapshot.get(snapshot_id)
        if not data:
            return []
        distinct: dict[tuple, dict] = {}
        for c in data["byDecision"].get(decision_number, []):
            dec = c.get("decision", {})
            distinct.setdefault((dec.get("issued"), dec.get("validUntil")), c)
        return list(distinct.values())

    def lookup_by_decision(self, snapshot_id: str, decision_number: str) -> dict | None:
        """Identity-grade lookup (D9): the sole record for a decision number
        ONLY when that number is an unambiguous identity — exactly one distinct
        validity window. Zero matches OR an ambiguous decision number (multiple
        differing validity windows) returns None: ambiguity is never collapsed
        to a single record, it routes the caller to review."""
        ids = self.identities_by_decision(snapshot_id, decision_number)
        return ids[0] if len(ids) == 1 else None

    def lookup(self, snapshot_id: str, regsr_code: str) -> dict | None:
        """Locator-grade lookup: regsrCode finds the list row, but a row is
        never product identity (D9) — callers must not treat a hit or miss
        here as an identity verdict."""
        data = self._by_snapshot.get(snapshot_id)
        if not data:
            return None
        return data["products"].get(regsr_code)

    def detail(self, snapshot_id: str, regsr_code: str) -> dict | None:
        data = self._by_snapshot.get(snapshot_id)
        if not data:
            return None
        return data["details"].get(regsr_code)

    def has_snapshot(self, snapshot_id: str) -> bool:
        return snapshot_id in self._by_snapshot


class ContextNotReconstructible(Exception):
    """A historical (AS_OF) context cannot be honestly reconstructed."""


class ContextAssembler:
    """Assembles (and reuses) per-farm Compliance-twin ContextSnapshots."""

    def __init__(self, store):
        self.store = store

    def _spine(self, as_of: str | None = None) -> dict:
        artifact_sets = self.store.find_by_kind("ofarm.activeartifactset.v0.1")
        activation_sets = self.store.find_by_kind("ofarm.packactivationset.v0.1")
        profiles = self.store.find_by_kind("ofarm.agronomiccodebindingprofile.v0.1")
        if not (artifact_sets and activation_sets and profiles):
            raise RuntimeError("context spine not bootstrapped — call context.bootstrap(store)")
        if as_of is not None and (len(artifact_sets) > 1 or len(activation_sets) > 1
                                  or len(profiles) > 1):
            # the single-profile M1 pilot has no versioned activation history
            # to select from — with multiple activation/profile/artifact-set
            # records, silently using the latest would apply a possibly-future
            # pack/profile context to an earlier state. Refuse instead
            # (hostile re-review finding 4).
            raise ContextNotReconstructible(
                "multiple activation/profile/artifact-set records exist; the "
                "historical pack/profile context for AS_OF cannot be "
                "reconstructed in this runtime — refusing rather than silently "
                "using the latest")
        # latest of each (single-profile pilot: exactly one of each is shipped)
        artifact_set = artifact_sets[-1]["payload"]
        activation_set = activation_sets[-1]["payload"]
        profile = profiles[-1]["payload"]
        if profile["profileState"] != "ACTIVE":
            raise RuntimeError(f"code-binding profile state is {profile['profileState']}, not ACTIVE")
        return {
            "artifact_set": artifact_set,
            "activation_set": activation_set,
            "profile": profile,
        }

    def assemble(self, cur, farm_ref: str, *, target_twin: str = "COMPLIANCE",
                 evaluation_time_policy: dict | None = None) -> dict:
        """Return the in-force ContextSnapshot payload for a farm, minting a
        new record only on basis drift (content-addressed reuse)."""
        policy = evaluation_time_policy or {"policyType": "NOW"}
        # AS_OF context selects the reference snapshots in force AT that
        # moment; a missing family is honest (none was in force yet) and
        # makes the context content — and therefore the snapshot id and the
        # materialization key — distinct from the NOW answer
        as_of = policy.get("asOfTime") if policy.get("policyType") == "AS_OF" else None
        spine = self._spine(as_of=as_of)
        regsr = current_reference_snapshot(self.store, REGSR_SNAPSHOT_PREFIX, as_of=as_of)
        gerk = current_reference_snapshot(self.store, GERK_SNAPSHOT_PREFIX, as_of=as_of)
        reference_refs = [p["referenceSnapshotId"] for p in (regsr, gerk) if p]

        material_basis = {
            "targetTwin": target_twin,
            "farm": farm_ref,
            "policy": policy,
            "activeArtifactSetRef": spine["artifact_set"]["activeArtifactSetId"],
            "sourcePackActivationSetRefs": [spine["activation_set"]["packActivationSetId"]],
            "activePackRefs": spine["activation_set"]["activePackRefs"],
            "activeProfileRefs": spine["activation_set"]["activeProfileRefs"],
            "referenceSnapshotRefs": reference_refs,
            "evidencePolicyRefs": [config.EVIDENCE_POLICY_REF],
        }
        digest = hashlib.sha256(canonical_json(material_basis).encode()).hexdigest()[:12]
        snapshot_id = f"contextsnapshot:si.ffs.{_local(farm_ref)}.{target_twin.lower()}.{digest}"

        existing = self.store.get_payload(snapshot_id)
        if existing:
            return existing  # basis-preserving reuse (ContextSnapshot Closure RFC §2.4)

        payload = {
            "schemaVersion": "ofarm.contextsnapshot.v0.1",
            "contextSnapshotId": snapshot_id,
            "generatedAt": now_iso(),
            "targetTwin": target_twin,
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
            "evaluationTimePolicy": policy,
            "activeArtifactSetRef": material_basis["activeArtifactSetRef"],
            "sourcePackActivationSetRefs": material_basis["sourcePackActivationSetRefs"],
            "activePackRefs": material_basis["activePackRefs"],
            "activeProfileRefs": material_basis["activeProfileRefs"],
            "relevantPrecedenceClasses": ["JURISDICTION_LAW_SAFETY"],
            "referenceSnapshotRefs": reference_refs,
            "evidencePolicyRefs": [config.EVIDENCE_POLICY_REF],
            "notes": "Per-farm Compliance-twin snapshot assembled from the shipped SI pilot spine.",
        }
        self.store.insert_record(cur, payload)
        return payload


def _local(ref: str) -> str:
    """farm:demo.kmetija.a -> demo.kmetija.a (id-safe local part)."""
    return ref.split(":", 1)[-1].replace(":", ".")
