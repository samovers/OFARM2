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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .contracts import ContractViolation, UnknownContract, canonical_json
from .profile_runtime import ProfileRuntimeError, resolve_bound_descriptor
from .runtime_bundle import RuntimeComponentRole

PROFILE_INSTANCE_FILES = list(config.ACTIVE_PROFILE.profile_instance_files)

SI_REGSR_FAMILY_ID = "si.uvhvvr.ffs-reg"
SI_GERK_FAMILY_ID = "si.mkgp.gerk-layer"
SI_FFSNAPRAVE_FAMILY_ID = "si.uvhvvr.ffs-naprave"


@dataclass(frozen=True)
class SIReferenceBindings:
    """Active SI REGSR, GERK, and FFSNaprave runtime bindings.

    This is deliberately SI-shaped. It makes the current active runtime's
    country/profile reference seams explicit without introducing a generic
    country abstraction.
    """
    si_profile_root: Path | None
    regsr_snapshot_prefix: str
    regsr_data_family: str
    regsr_shipped_snapshot_ref: str
    regsr_shipped_artifact_path: Path | None
    gerk_snapshot_prefix: str
    gerk_data_family: str
    gerk_shipped_snapshot_ref: str
    ffsnaprave_snapshot_prefix: str
    ffsnaprave_data_family: str

    @classmethod
    def from_descriptor(cls, descriptor) -> "SIReferenceBindings":
        """Compatibility bindings that retain the shipped release-path artifact."""
        return cls._from_descriptor(descriptor, include_compatibility_path=True)

    @classmethod
    def from_runtime_descriptor(cls, descriptor) -> "SIReferenceBindings":
        """Runtime bindings with no filesystem reference-data authority."""
        return cls._from_descriptor(descriptor, include_compatibility_path=False)

    @classmethod
    def _from_descriptor(
        cls, descriptor, *, include_compatibility_path: bool
    ) -> "SIReferenceBindings":
        si_profile_root = None
        if include_compatibility_path:
            try:
                si_profile_root = Path(descriptor.profile_root).resolve(strict=True)
            except (OSError, TypeError) as exc:
                raise ProfileRuntimeError(
                    "active SI profile root is unavailable or unreadable"
                ) from exc

        regsr_family = descriptor.reference_family(SI_REGSR_FAMILY_ID)
        gerk_family = descriptor.reference_family(SI_GERK_FAMILY_ID)
        ffsnaprave_family = descriptor.reference_family(SI_FFSNAPRAVE_FAMILY_ID)

        regsr_data_family = _required_binding_value(
            regsr_family.data_family, "REGSR data family")
        regsr_shipped_snapshot_ref = _required_binding_value(
            regsr_family.shipped_snapshot_ref, "REGSR shipped snapshot ref")
        gerk_data_family = _required_binding_value(
            gerk_family.data_family, "GERK data family")
        gerk_shipped_snapshot_ref = _required_binding_value(
            gerk_family.shipped_snapshot_ref, "GERK shipped snapshot ref")
        ffsnaprave_data_family = _required_binding_value(
            ffsnaprave_family.data_family, "FFSNaprave data family")
        regsr_artifact_path = (
            _regsr_shipped_artifact_path(
                descriptor, si_profile_root, regsr_shipped_snapshot_ref
            )
            if include_compatibility_path else None
        )

        return cls(
            si_profile_root=si_profile_root,
            regsr_snapshot_prefix=regsr_family.snapshot_prefix,
            regsr_data_family=regsr_data_family,
            regsr_shipped_snapshot_ref=regsr_shipped_snapshot_ref,
            regsr_shipped_artifact_path=regsr_artifact_path,
            gerk_snapshot_prefix=gerk_family.snapshot_prefix,
            gerk_data_family=gerk_data_family,
            gerk_shipped_snapshot_ref=gerk_shipped_snapshot_ref,
            ffsnaprave_snapshot_prefix=ffsnaprave_family.snapshot_prefix,
            ffsnaprave_data_family=ffsnaprave_data_family,
        )


def _required_binding_value(value, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProfileRuntimeError(
            f"active SI profile descriptor must name the {label}")
    return value


def _regsr_shipped_artifact_path(
    descriptor,
    si_profile_root: Path,
    shipped_snapshot_ref: str,
) -> Path:
    matches = []
    for path in descriptor.profile_instance_paths:
        try:
            payload = json.loads(Path(path).read_text())
        except (OSError, ValueError) as exc:
            raise ProfileRuntimeError(
                f"active SI profile instance unreadable or malformed at {path}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            continue
        if payload.get("referenceSnapshotId") == shipped_snapshot_ref:
            matches.append((Path(path), payload))
    if len(matches) != 1:
        raise ProfileRuntimeError(
            f"active SI shipped REGSR snapshot {shipped_snapshot_ref!r} matched "
            f"{len(matches)} profile instance payloads")

    source_refs = matches[0][1].get("sourceArtifactRefs", [])
    artifact_refs = [
        ref.split(":", 1)[1]
        for ref in source_refs
        if isinstance(ref, str) and ref.startswith("artifact:")
    ]
    if len(artifact_refs) != 1 or not artifact_refs[0]:
        raise ProfileRuntimeError(
            f"active SI shipped REGSR snapshot {shipped_snapshot_ref!r} must "
            "name exactly one artifact: source ref")
    return _resolve_profile_example_artifact(
        si_profile_root,
        artifact_refs[0],
        required=True,
        label=f"active SI shipped REGSR artifact for {shipped_snapshot_ref!r}",
    )


def _resolve_profile_example_artifact(
    profile_root: Path,
    artifact_name: str,
    *,
    required: bool,
    label: str,
) -> Path | None:
    try:
        examples_root = (profile_root / "examples").resolve(strict=True)
        candidate = (examples_root / artifact_name).resolve(strict=True)
        candidate.relative_to(examples_root)
    except (OSError, ValueError) as exc:
        if required:
            raise ProfileRuntimeError(f"{label} is absent or escapes profile examples") from exc
        return None
    if not candidate.is_file():
        if required:
            raise ProfileRuntimeError(f"{label} is not a file")
        return None
    return candidate


SI_REFERENCE_BINDINGS = SIReferenceBindings.from_runtime_descriptor(
    config.ACTIVE_PROFILE
)
REGSR_SNAPSHOT_PREFIX = SI_REFERENCE_BINDINGS.regsr_snapshot_prefix
GERK_SNAPSHOT_PREFIX = SI_REFERENCE_BINDINGS.gerk_snapshot_prefix
# Candidate/audit data family a governed REGSR import tags (M2 P1).
# ProductRegister's Store-bound path reads exact bundle source bytes instead;
# this alias remains compatibility surface over the explicit SI binding object.
REGSR_DATA_FAMILY = SI_REFERENCE_BINDINGS.regsr_data_family

_ACTIVE_PROFILE_REQUIRED_FIELDS = (
    "profile_ref",
    "pack_ref",
    "pack_activation_set_ref",
    "active_artifact_set_ref",
    "code_binding_profile_ref",
    "evidence_policy_ref",
    "reference_families",
    "context_snapshot_id_prefix",
    "profile_instance_paths",
)


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


def _require_active_profile(active_profile):
    if active_profile is None:
        raise ContextNotReconstructible("active profile descriptor is required")
    missing = [
        field for field in _ACTIVE_PROFILE_REQUIRED_FIELDS
        if not hasattr(active_profile, field)
    ]
    if missing:
        raise ContextNotReconstructible(
            f"active profile descriptor lacks required field(s) {missing}")
    return active_profile


def bootstrap_for_descriptor(store, active_profile) -> list[str]:
    """Load the Store's bundle-selected canonical instances atomically."""
    active_profile = _require_active_profile(active_profile)
    try:
        resolve_bound_descriptor(store, active_descriptor=active_profile)
    except ProfileRuntimeError as exc:
        raise ContextNotReconstructible(
            f"active profile descriptor is not the Store startup selection: {exc}"
        ) from exc

    prepared = []
    selected_roles = {
        RuntimeComponentRole.PROFILE_INSTANCE,
        RuntimeComponentRole.REFERENCE_SNAPSHOT,
    }
    for component in store.runtime_bundle.components:
        if component.role not in selected_roles:
            continue
        payload = json.loads(component.canonical_bytes)
        try:
            contract = store.registry.validate(payload)
            record_id = payload[contract.id_field]
        except (ContractViolation, KeyError, TypeError, UnknownContract) as exc:
            raise ContextNotReconstructible(
                f"bundle-selected canonical instance {component.logical_ref!r} "
                f"is not a valid Store record: {exc}"
            ) from exc
        prepared.append((payload, contract, record_id, component.content_digest))

    inserted = []
    with store.tx() as cur:
        missing = []
        for payload, contract, record_id, selected_payload_digest in prepared:
            existing = store.get_record(record_id)
            if existing is None:
                missing.append((payload, record_id))
                continue
            if (
                existing["tenant_ref"] != store.tenant_ref
                or existing["lane"] != "canonical"
                or existing["record_kind"] != contract.kind
                or existing["schema_hash"] != contract.schema_hash
                or existing["payload_sha256"] != selected_payload_digest
                or existing["payload"] != payload
            ):
                raise ContextNotReconstructible(
                    f"existing active profile instance {record_id} is not the "
                    "exact selected contract and payload"
                )
        for payload, record_id in missing:
            store.insert_record(cur, payload)
            inserted.append(record_id)
    return inserted


def bootstrap(store) -> list[str]:
    """Load the shipped SI profile instances into the store (idempotent).

    These are package-validated instances (conformance self-check), inserted
    verbatim — never edited (AGENTS.md rule 4).
    """
    return bootstrap_for_descriptor(store, store.active_descriptor)


def current_reference_snapshot(store, prefix: str,
                               as_of: str | None = None) -> dict | None:
    """The in-force reference snapshot of a family = the latest `effectiveFrom`
    that is actually IN FORCE at the selection bound.

    The bound is `as_of` (AS_OF) or the current time (NOW). A snapshot is in
    force at the bound iff it is selected by the Store's RuntimeBundle,
    `effectiveFrom <= bound`, and (no `effectiveUntil`, or `bound <
    effectiveUntil`). A governed import can retain a candidate snapshot, but it
    cannot hot-activate it under the current bundle; selection changes require a
    new bundle. `prefix` is a FAMILY boundary, matched at the family root or its
    '.' delimiter (not a bare string prefix), so a sibling family that shares
    leading characters never collides. None means no selected snapshot of this
    family was in force at that moment. An unparseable bound selects nothing."""
    rows = store.find_by_kind("ofarm.referencesnapshot.v0.1")
    selected_refs = store.selected_reference_snapshot_refs
    bound = parse_ts(as_of) if as_of else parse_ts(now_iso())
    if bound is None:
        return None   # unparseable as_of: refuse to guess
    candidates = []
    for r in rows:
        p = r["payload"]
        sid = p["referenceSnapshotId"]
        if sid not in selected_refs:
            continue
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


def context_reference_snapshots_for_descriptor(
    store,
    active_profile,
    as_of: str | None = None,
) -> list[dict]:
    """Reference snapshots required by an explicit active profile descriptor.

    Missing spine vintages are handled in ContextAssembler._spine. Missing
    reference families are separate: the descriptor decides whether absence means
    omission from context or refusal for NOW/AS_OF.
    """
    active_profile = _require_active_profile(active_profile)
    snapshots = []
    as_of_mode = as_of is not None
    for family in active_profile.reference_families:
        snapshot = current_reference_snapshot(store, family.snapshot_prefix, as_of=as_of)
        if snapshot:
            snapshots.append(snapshot)
            continue
        if family.missing_behavior(as_of=as_of_mode) == "REFUSE_CONTEXT":
            bound = f"AS_OF {as_of!r}" if as_of_mode else "NOW"
            raise ContextNotReconstructible(
                f"required reference family {family.family_id!r} has no in-force "
                f"snapshot for {bound} context")
    return snapshots


def context_reference_snapshots(store, as_of: str | None = None) -> list[dict]:
    """Reference snapshots required by the active profile descriptor."""
    return context_reference_snapshots_for_descriptor(
        store,
        store.active_descriptor,
        as_of=as_of,
    )


class SIProductRegister:
    """Offline product-register lookup for the in-force REGSR snapshots.

    Snapshot artifacts are dated parses of the official HTML surface
    (D9: no official export exists — posture declared, never hidden).
    Tests may register synthetic, clearly-fictional snapshot data through
    the same path; the runtime itself only ever reads registered artifacts.
    """

    def __init__(self, bindings: SIReferenceBindings | None = None):
        self.bindings = bindings or SIReferenceBindings.from_descriptor(
            config.ACTIVE_PROFILE
        )
        self._by_snapshot: dict[str, dict] = {}
        # the shipped real parse (623 products, fictional-free: public register data)
        shipped = self.bindings.regsr_shipped_artifact_path
        if shipped is not None and shipped.exists():
            self.register_artifact(
                self.bindings.regsr_shipped_snapshot_ref,
                json.loads(shipped.read_text()),
            )

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
        """Resolve exact bundle-selected REGSR source data.

        Constructor-loaded package data is a compatibility surface for direct
        register use; Store-bound runtime loading discards it. Database cache
        rows remain candidate/audit data and never override the source bytes
        selected by the RuntimeBundle.
        """
        runtime_bindings = SIReferenceBindings.from_runtime_descriptor(
            store.active_descriptor
        )
        self.bindings = runtime_bindings
        self._by_snapshot.clear()
        for row in store.selected_reference_source_data(
            runtime_bindings.regsr_snapshot_prefix
        ):
            self.register_artifact(row["snapshot_ref"], row["payload"])

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


# Compatibility name for direct tests and existing SI adapter callers. Generic
# runtime composition uses SIProductRegister through the registered SI provider.
ProductRegister = SIProductRegister


class ContextNotReconstructible(Exception):
    """A historical (AS_OF) context cannot be honestly reconstructed."""


class ContextAssembler:
    """Assembles (and reuses) per-farm Compliance-twin ContextSnapshots."""

    def __init__(self, store, *, active_descriptor=None, active_profile=None):
        self.store = store
        self.active_profile = _require_active_profile(
            resolve_bound_descriptor(
                store,
                active_descriptor=active_descriptor,
                active_profile=active_profile,
            )
        )
        self.runtime_bundle = store.runtime_bundle

    def _spine(self, as_of: str | None = None) -> dict:
        artifact_sets = self.store.find_by_kind("ofarm.activeartifactset.v0.1")
        activation_sets = self.store.find_by_kind("ofarm.packactivationset.v0.1")
        profiles = self.store.find_by_kind("ofarm.agronomiccodebindingprofile.v0.1")
        if not (artifact_sets and activation_sets and profiles):
            raise ContextNotReconstructible(
                "context spine not bootstrapped — call context.bootstrap(store)")
        if as_of is None:
            # NOW: select the descriptor-declared active SI pilot spine, never
            # whichever row happens to sort last in the store.
            artifact_set = self._declared_spine_record(
                artifact_sets, "activeArtifactSetId",
                self.active_profile.active_artifact_set_ref, "ActiveArtifactSet")
            activation_set = self._declared_spine_record(
                activation_sets, "packActivationSetId",
                self.active_profile.pack_activation_set_ref, "PackActivationSet")
            profile = self._declared_spine_record(
                profiles, "agronomicCodeBindingProfileId",
                self.active_profile.code_binding_profile_ref, "AgronomicCodeBindingProfile")
        else:
            # AS_OF: reconstruct the vintage in force at as_of by each family's
            # effective timestamp (G6). Each family selects the latest effective
            # <= as_of; a future vintage is never applied to an earlier state,
            # whether it is one of several or the only record (a single record is
            # not privileged to skip the time bound). The whole spine must be in
            # force: if ANY family has no vintage in force at as_of, the context
            # is not reconstructible. Refuse over pretend (Kernel rule 7) when no
            # vintage is in force or the latest is ambiguous (identical timestamps
            # -> cannot pick deterministically).
            bound = parse_ts(as_of)
            if bound is None:
                raise ContextNotReconstructible(
                    f"AS_OF time {as_of!r} is unparseable — refusing to guess a vintage")
            artifact_set = self._vintage(artifact_sets, "generatedAt", bound, "ActiveArtifactSet")
            activation_set = self._vintage(activation_sets, "evaluatedAt", bound, "PackActivationSet")
            profile = self._vintage(profiles, "issuedAt", bound, "AgronomicCodeBindingProfile")
        if profile["profileState"] != "ACTIVE":
            if as_of is None:
                raise ContextNotReconstructible(
                    f"the descriptor-declared AgronomicCodeBindingProfile is "
                    f"{profile['profileState']}, not ACTIVE — refusing NOW context")
            # AS_OF: G6 selects the profile vintage in force by issuedAt; if that
            # vintage is not ACTIVE the historical context cannot be reconstructed
            # into a usable profile, so refuse over pretend (rule 7) — a governed
            # MATERIALIZATION_INVALID via resolve_for_use, never an uncaught 500.
            # NOTE: whether a non-ACTIVE in-force vintage should instead be SKIPPED
            # in favour of the latest ACTIVE one is a profile-lifecycle decision
            # (supersession/draft semantics) deferred beyond G6's timestamp-based
            # selection — recorded as ERRATA E-007.
            raise ContextNotReconstructible(
                f"the AgronomicCodeBindingProfile vintage in force at {bound.isoformat()} is "
                f"{profile['profileState']}, not ACTIVE — the historical context cannot be "
                "reconstructed into a usable profile")
        # AS_OF selects the three families independently by their own timestamps;
        # NOW selects the descriptor-declared active spine. In both cases, verify
        # the selected records cohere before creating a ContextSnapshot.
        self._assert_coherent_spine(artifact_set, activation_set, profile,
                                    bound if as_of is not None else None)
        return {
            "artifact_set": artifact_set,
            "activation_set": activation_set,
            "profile": profile,
        }

    @staticmethod
    def _declared_spine_record(records: list[dict], id_field: str,
                               expected_ref: str, label: str) -> dict:
        matches = [r["payload"] for r in records if r["payload"].get(id_field) == expected_ref]
        if len(matches) != 1:
            raise ContextNotReconstructible(
                f"descriptor-declared {label} {expected_ref!r} matched {len(matches)} "
                "in-force store records; refusing rather than selecting by store order")
        return matches[0]

    @staticmethod
    def _vintage(records: list[dict], date_field: str, bound, label: str) -> dict:
        """The spine-family vintage in force at `bound` (AS_OF, G6): the latest
        `date_field` that is <= bound. The same rule governs one record or many —
        a single record is NOT privileged to skip the time bound: a future vintage
        (effective > bound) is excluded whether or not it is the only one, never
        applied to an earlier state (Kernel rule 6). Refuse (ContextNotReconstructible)
        when none is in force (none datable <= bound), or when two share the latest
        timestamp and the choice is ambiguous — refuse over pretend (rule 7), never
        silently use the latest."""
        dated = []
        for r in records:
            eff = parse_ts(r["payload"].get(date_field))
            if eff is not None and eff <= bound:
                dated.append((eff, r["payload"]))
        if not dated:
            raise ContextNotReconstructible(
                f"no {label} vintage was in force at {bound.isoformat()} (by {date_field}); "
                "the historical context cannot be reconstructed")
        latest = max(eff for eff, _ in dated)
        in_force = [p for eff, p in dated if eff == latest]
        if len(in_force) > 1:
            raise ContextNotReconstructible(
                f"{label} history is ambiguous at {bound.isoformat()}: "
                f"{len(in_force)} records share the latest {date_field} {latest.isoformat()} — "
                "refusing rather than guessing which vintage was in force")
        return in_force[0]

    def _assert_coherent_spine(self, artifact_set: dict, activation_set: dict,
                               profile: dict, bound) -> None:
        """Refuse a spine whose selected records never formed a real deployment.

        The ActiveArtifactSet is the integrated, derived artifact: it carries
        the PackActivationSet(s) it was generated from, the active pack/profile
        refs it deployed, and the concrete artifacts (incl. the code-binding
        profile) it shipped. For AS_OF, independently time-selected families must
        cohere. For NOW, descriptor-declared records must cohere. Otherwise the
        context is a synthetic fiction. ContextNotReconstructible is governed to
        MATERIALIZATION_INVALID by resolve_for_use."""
        when = bound.isoformat() if bound is not None else "NOW"
        expected_pack = [self.active_profile.pack_ref]
        expected_profile = [self.active_profile.profile_ref]
        if activation_set.get("activePackRefs") != expected_pack:
            raise ContextNotReconstructible(
                f"context spine at {when} is incoherent: PackActivationSet activePackRefs "
                f"{activation_set.get('activePackRefs')} do not match descriptor packRef "
                f"{expected_pack}")
        if activation_set.get("activeProfileRefs") != expected_profile:
            raise ContextNotReconstructible(
                f"context spine at {when} is incoherent: PackActivationSet activeProfileRefs "
                f"{activation_set.get('activeProfileRefs')} do not match descriptor profileRef "
                f"{expected_profile}")
        if artifact_set.get("activePackRefs") != expected_pack:
            raise ContextNotReconstructible(
                f"context spine at {when} is incoherent: ActiveArtifactSet activePackRefs "
                f"{artifact_set.get('activePackRefs')} do not match descriptor packRef "
                f"{expected_pack}")
        if artifact_set.get("activeProfileRefs") != expected_profile:
            raise ContextNotReconstructible(
                f"context spine at {when} is incoherent: ActiveArtifactSet activeProfileRefs "
                f"{artifact_set.get('activeProfileRefs')} do not match descriptor profileRef "
                f"{expected_profile}")
        if self.active_profile.evidence_policy_ref not in artifact_set.get("activeArtifactRefs", []):
            raise ContextNotReconstructible(
                f"context spine at {when} is incoherent: ActiveArtifactSet does not deploy "
                f"descriptor evidence policy {self.active_profile.evidence_policy_ref!r}")
        if (profile.get("profileScope") or {}).get("packRefs") != expected_pack:
            raise ContextNotReconstructible(
                f"context spine at {when} is incoherent: AgronomicCodeBindingProfile "
                f"profileScope.packRefs {(profile.get('profileScope') or {}).get('packRefs')} "
                f"do not match descriptor packRef {expected_pack}")
        act_id = activation_set["packActivationSetId"]
        source = artifact_set.get("sourcePackActivationSetRefs")
        # The ActiveArtifactSet is derived FROM activation(s); the in-force one
        # must record the in-force activation as a source. A missing or EMPTY
        # source list records no lineage and so cannot be reconciled with any
        # activation — refuse rather than pair on unverifiable provenance (an
        # empty/None list is falsy and must NOT silently skip the inclusion test).
        if not source or act_id not in source:
            recorded = f"was generated from {source}" if source else "records no source PackActivationSet"
            raise ContextNotReconstructible(
                f"context spine at {when} is incoherent: the selected ActiveArtifactSet {recorded}, "
                f"so it cannot be paired with the in-force PackActivationSet {act_id!r} — refusing to "
                "synthesize a pack/artifact context that never existed together")
        if set(artifact_set.get("activePackRefs", [])) != set(activation_set.get("activePackRefs", [])):
            raise ContextNotReconstructible(
                f"context spine at {when} is incoherent: ActiveArtifactSet activePackRefs "
                f"{artifact_set.get('activePackRefs')} != PackActivationSet activePackRefs "
                f"{activation_set.get('activePackRefs')} — refusing rather than synthesize a context")
        if set(artifact_set.get("activeProfileRefs", [])) != set(activation_set.get("activeProfileRefs", [])):
            raise ContextNotReconstructible(
                f"context spine at {when} is incoherent: ActiveArtifactSet activeProfileRefs "
                f"{artifact_set.get('activeProfileRefs')} != PackActivationSet activeProfileRefs "
                f"{activation_set.get('activeProfileRefs')} — refusing rather than synthesize a context")
        cb_id = profile["agronomicCodeBindingProfileId"]
        if cb_id not in artifact_set.get("activeArtifactRefs", []):
            raise ContextNotReconstructible(
                f"context spine at {when} is incoherent: the selected AgronomicCodeBindingProfile {cb_id!r} "
                "is not among the in-force ActiveArtifactSet's deployed artifacts — refusing to pair a "
                "code-binding profile vintage with an artifact set that did not deploy it")

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
        reference_snapshots = context_reference_snapshots_for_descriptor(
            self.store, self.active_profile, as_of=as_of)
        reference_refs = [p["referenceSnapshotId"] for p in reference_snapshots]

        material_basis = {
            "schemaVersion": "ofarm.contextsnapshot.v0.1",
            "targetTwin": target_twin,
            "anchorScopes": [{"scopeType": "FARM", "scopeRef": farm_ref}],
            "evaluationTimePolicy": policy,
            "activeArtifactSetRef": spine["artifact_set"]["activeArtifactSetId"],
            "sourcePackActivationSetRefs": [spine["activation_set"]["packActivationSetId"]],
            "activePackRefs": spine["activation_set"]["activePackRefs"],
            "activeProfileRefs": spine["activation_set"]["activeProfileRefs"],
            "relevantPrecedenceClasses": ["JURISDICTION_LAW_SAFETY"],
            "referenceSnapshotRefs": reference_refs,
            "evidencePolicyRefs": [self.active_profile.evidence_policy_ref],
        }
        identity_basis = {
            **material_basis,
            "runtimeBundleDigest": self.runtime_bundle.digest,
        }
        digest = hashlib.sha256(
            canonical_json(identity_basis).encode()
        ).hexdigest()
        snapshot_id = (
            f"{self.active_profile.context_snapshot_id_prefix}."
            f"{_local(farm_ref)}.{target_twin.lower()}.{digest}"
        )

        existing = self.store.get_record(snapshot_id)
        if existing:
            if (
                existing["tenant_ref"] != self.store.tenant_ref
                or existing["runtime_bundle_digest"] != self.runtime_bundle.digest
            ):
                raise ContextNotReconstructible(
                    f"ContextSnapshot identity {snapshot_id} belongs to another "
                    "RuntimeBundle; refusing cross-bundle reuse")
            observed_basis = {
                field: existing["payload"].get(field)
                for field in material_basis
            }
            if (
                existing["record_kind"] != material_basis["schemaVersion"]
                or existing["payload"].get("contextSnapshotId") != snapshot_id
                or observed_basis != material_basis
            ):
                raise ContextNotReconstructible(
                    f"ContextSnapshot identity {snapshot_id} was reused with "
                    "unequal canonical identity inputs"
                )
            return existing["payload"]  # basis-preserving reuse (Closure RFC §2.4)

        payload = {
            **material_basis,
            "contextSnapshotId": snapshot_id,
            "generatedAt": now_iso(),
            "notes": "Per-farm Compliance-twin snapshot assembled from the shipped SI pilot spine.",
        }
        self.store.insert_record(cur, payload)
        return payload


def _local(ref: str) -> str:
    """farm:demo.kmetija.a -> demo.kmetija.a (id-safe local part)."""
    return ref.split(":", 1)[-1].replace(":", ".")
