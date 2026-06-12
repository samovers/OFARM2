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
from pathlib import Path

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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
    """The in-force reference snapshot of a family = latest effectiveFrom.

    With `as_of`, the latest snapshot whose effectiveFrom <= asOfTime — an
    AS_OF answer must not silently apply a future register vintage to an
    earlier state (hostile review: context must be as-of-aware too). None
    means no snapshot of this family was in force at that moment."""
    rows = store.find_by_kind("ofarm.referencesnapshot.v0.1")
    bound = parse_ts(as_of) if as_of else None
    candidates = []
    for r in rows:
        p = r["payload"]
        if not p["referenceSnapshotId"].startswith(prefix):
            continue
        eff = parse_ts(p["effectiveFrom"])
        if eff is None:
            continue   # unparseable validity never selects (fail closed)
        if bound is not None and eff > bound:
            continue
        candidates.append((eff, p))
    if not candidates:
        return None
    return max(candidates, key=lambda pair: pair[0])[1]


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
            self.register_artifact("referencesnapshot:si.uvhvvr.ffs-reg.2026-06-11",
                                   json.loads(shipped.read_text()))

    def register_artifact(self, snapshot_id: str, artifact: dict) -> None:
        products = {p["regsrCode"]: p for p in artifact.get("products", [])}
        details = {d.get("regsrCode"): d for d in artifact.get("productDetails", [])}
        # D9: the binding identity is the decision number (stevilka odlocbe)
        # + validity dates; regsrCode is a page locator, never identity. The
        # public list surface carries no decision numbers — only detail pages
        # do — so identity-confirmable lookups exist only where detail data
        # was parsed. That asymmetry is surfaced, never papered over.
        by_decision = {}
        for d in artifact.get("productDetails", []):
            for decision in d.get("decisions", []):
                number = decision.get("decisionNumber")
                if number:
                    by_decision[number] = {**d, "decision": decision}
        self._by_snapshot[snapshot_id] = {
            "products": products, "details": details, "byDecision": by_decision,
        }

    def load_from_store(self, store) -> None:
        """Resolve register data for snapshots by their declared
        sourceArtifactRefs — the snapshot record names its artifact; the
        runtime never guesses."""
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

    def lookup_by_decision(self, snapshot_id: str, decision_number: str) -> dict | None:
        """Identity-grade lookup (D9): by decision number, where the parsed
        surface carries it. None means 'not confirmable on this surface',
        which is NOT the same as 'withdrawn'."""
        data = self._by_snapshot.get(snapshot_id)
        if not data:
            return None
        return data["byDecision"].get(decision_number)

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
