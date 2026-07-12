"""Context spine: SI profile instances, reference snapshots, per-farm
ContextSnapshot assembly (PACK_PROFILE_APPLICABILITY gate support).

Static profile applicability (M1 brief task 3): the pilot runs one pack, one
profile, no overlap (PROFILE.md). ContextSnapshots are assembled from the
shipped instances; per the ContextSnapshot Closure RFC an existing snapshot is
reused while the governing context is materially the same and a NEW snapshot
is minted on basis drift (new reference snapshot version, policy change …).
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .contracts import ContractRegistry, UnknownContract, canonical_json
from .profile_runtime import ProfileRuntimeError, resolve_active_descriptor
from .runtime_bundle import (
    TENANT_CONTENT_PLACEMENT,
    RuntimeBundleError,
    _build_live_runtime_bundle,
    _copy_runtime_cache_value,
    _freeze_runtime_cache,
    _runtime_cache_state,
    require_store_runtime_bundle,
    sha256_bytes,
)
from .store import (
    Store,
    _RETAINED_GOVERNED_CURSOR_EXECUTE_READ as _CURSOR_EXECUTE_READ,
)

# Private module seam so the lock/atomic-selection regression can observe the
# exact builder call without exporting live-selection authority as a public API.
_build_runtime_bundle_for_bootstrap = _build_live_runtime_bundle

PROFILE_INSTANCE_FILES = list(config.ACTIVE_PROFILE.profile_instance_files)

SI_REGSR_FAMILY_ID = "si.uvhvvr.ffs-reg"
SI_GERK_FAMILY_ID = "si.mkgp.gerk-layer"


@dataclass(frozen=True, slots=True)
class SIReferenceBindings:
    """Active SI REGSR/GERK runtime bindings.

    This is deliberately SI-shaped. It makes the current active runtime's
    country/profile reference seams explicit without introducing a generic
    country abstraction.
    """
    si_profile_root: Path
    regsr_snapshot_prefix: str
    regsr_data_family: str
    regsr_shipped_snapshot_ref: str
    regsr_shipped_artifact_path: Path
    gerk_snapshot_prefix: str
    gerk_data_family: str
    gerk_shipped_snapshot_ref: str

    @classmethod
    def from_descriptor(cls, descriptor, *, runtime_bundle=None) -> "SIReferenceBindings":
        if runtime_bundle is not None and runtime_bundle.descriptor != descriptor:
            raise ProfileRuntimeError(
                "SI reference bindings descriptor does not exactly match RuntimeBundle")
        try:
            si_profile_root = Path(descriptor.profile_root).resolve(
                strict=runtime_bundle is None)
        except (OSError, TypeError) as exc:
            raise ProfileRuntimeError(
                "active SI profile root is unavailable or unreadable") from exc

        regsr_family = descriptor.reference_family(SI_REGSR_FAMILY_ID)
        gerk_family = descriptor.reference_family(SI_GERK_FAMILY_ID)

        regsr_data_family = _required_binding_value(
            regsr_family.data_family, "REGSR data family")
        regsr_shipped_snapshot_ref = _required_binding_value(
            regsr_family.shipped_snapshot_ref, "REGSR shipped snapshot ref")
        gerk_data_family = _required_binding_value(
            gerk_family.data_family, "GERK data family")
        gerk_shipped_snapshot_ref = _required_binding_value(
            gerk_family.shipped_snapshot_ref, "GERK shipped snapshot ref")
        if runtime_bundle is not None:
            snapshot = runtime_bundle.reference_payload(regsr_shipped_snapshot_ref)
            artifact_refs = [
                ref.split(":", 1)[1]
                for ref in snapshot.get("sourceArtifactRefs", [])
                if isinstance(ref, str) and ref.startswith("artifact:")
            ]
            if len(artifact_refs) != 1 or not artifact_refs[0]:
                raise ProfileRuntimeError(
                    "bundled SI shipped REGSR snapshot must name one source artifact")
            # The path is an identity/display aid only. Bundle-backed consumers
            # use its name to address retained REFERENCE_SOURCE bytes and never
            # open this filesystem location.
            regsr_artifact_path = si_profile_root / "examples" / artifact_refs[0]
        else:
            regsr_artifact_path = _regsr_shipped_artifact_path(
                descriptor, si_profile_root, regsr_shipped_snapshot_ref)

        return cls(
            si_profile_root=si_profile_root,
            regsr_snapshot_prefix=regsr_family.snapshot_prefix,
            regsr_data_family=regsr_data_family,
            regsr_shipped_snapshot_ref=regsr_shipped_snapshot_ref,
            regsr_shipped_artifact_path=regsr_artifact_path,
            gerk_snapshot_prefix=gerk_family.snapshot_prefix,
            gerk_data_family=gerk_data_family,
            gerk_shipped_snapshot_ref=gerk_shipped_snapshot_ref,
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


def _snapshot_matches_family(snapshot_id: str, prefix: str) -> bool:
    return snapshot_id == prefix or snapshot_id.startswith(prefix + ".")


SI_REFERENCE_BINDINGS = SIReferenceBindings.from_descriptor(config.ACTIVE_PROFILE)
REGSR_SNAPSHOT_PREFIX = SI_REFERENCE_BINDINGS.regsr_snapshot_prefix
GERK_SNAPSHOT_PREFIX = SI_REFERENCE_BINDINGS.gerk_snapshot_prefix
# store-backed reference-data family for REGSR parsed product data (M2 P1): the
# data_family a governed REGSR import tags its parsed data with, and the family
# ProductRegister loads from the store. ProductRegister is already REGSR-shaped
# (lookup_by_decision, D9), so this REGSR-specific alias remains compatibility
# surface over the explicit SI binding object.
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
    return f"{prefix}:{uuid.uuid4().hex}"


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


def _profile_payloads_from_bundle(store, active_profile, bundle):
    """Read the shipped spine exactly once, from verified bundle bytes."""
    package_root = Path(active_profile.profile_root).resolve().parent
    payloads = []
    for path in active_profile.profile_instance_paths:
        try:
            relative = Path(path).resolve().relative_to(package_root).as_posix()
        except ValueError as exc:
            raise ContextNotReconstructible(
                f"profile instance escapes the bound package root: {path}") from exc
        matches = [component for component in bundle.components
                   if component.repository_path == relative
                   and component.role == "PROFILE_INSTANCE"
                   and component.placement == TENANT_CONTENT_PLACEMENT]
        if len(matches) != 1:
            # Tenant-neutral package/reference instances stay solely in the
            # global content carrier. They are selected by the tenant bundle
            # but are never copied into tenant kernel_record.
            global_matches = [component for component in bundle.components
                              if component.repository_path == relative]
            if len(global_matches) == 1 \
                    and global_matches[0].placement != TENANT_CONTENT_PLACEMENT:
                continue
            raise ContextNotReconstructible(
                f"RuntimeBundle does not contain one tenant profile instance {relative!r}")
        try:
            payload = json.loads(matches[0].canonical_bytes)
            if payload.get("schemaVersion") == "ofarm.contextsnapshot.v0.1":
                # The shipped tenant ContextSnapshot is a fixture/template. NOW
                # and AS_OF snapshots are generated under a farm/tenant basis;
                # package presence is never startup context authority.
                continue
            contract = store.registry.get(payload["schemaVersion"])
            record_id = payload[contract.id_field]
        except (KeyError, TypeError, ValueError, UnknownContract) as exc:
            raise ContextNotReconstructible(
                f"bundled profile instance {relative!r} is malformed: {exc}") from exc
        payloads.append((record_id, contract.kind, payload, matches[0].content_digest))
    return payloads


def bootstrap_for_descriptor(
        store, active_profile, *, profile_route_selection: dict | None = None) -> list[str]:
    """Atomically install one verified bundle and its shipped profile instances.

    Reusing an identifier is permitted only for canonically equal content. A
    conflict aborts the whole bootstrap; no prefix of the profile spine lands.
    """
    # Import every adapter declared as a supported runtime surface before the
    # live Python environment is selected. Later manifest verification and
    # governed imports must execute within a zero-growth module seal.
    from .manifest import preload_runtime_import_surfaces
    preload_runtime_import_surfaces()
    active_profile = _require_active_profile(active_profile)
    bound_bundle = getattr(store, "_runtime_bundle", None)
    if bound_bundle is not None:
        if bound_bundle.descriptor != active_profile:
            raise ContextNotReconstructible(
                "the Store is already bound to a different RuntimeBundle descriptor")
        if profile_route_selection is not None:
            try:
                retained_route_selection = bound_bundle.json_component(
                    "PROFILE_ROUTE_SELECTION", "profile-route-selection:active")
            except RuntimeBundleError as exc:
                raise ContextNotReconstructible(
                    "the bound RuntimeBundle has no matching profile route selection") \
                    from exc
            if retained_route_selection != profile_route_selection:
                raise ContextNotReconstructible(
                    "the bound RuntimeBundle profile route selection differs")
        for record_id, kind, payload, expected_digest in _profile_payloads_from_bundle(
                store, active_profile, bound_bundle):
            existing = store.get_record(record_id)
            if (existing is None or existing["record_kind"] != kind
                    or existing["tenant_ref"] != bound_bundle.tenant_ref
                    or existing["payload_sha256"] != expected_digest
                    or canonical_json(existing["payload"]) != canonical_json(payload)):
                raise ContextNotReconstructible(
                    f"bound profile instance {record_id!r} is absent or byte-mismatched")
        return []

    inserted = []
    bundle = None
    try:
        with Store.serialized_tx(store) as cur:
            # Selection, content verification, persistence, and spine insertion
            # share the import/commit advisory lock. A governed import cannot
            # commit between selection and bundle installation.
            _CURSOR_EXECUTE_READ(cur,
                "SELECT k.payload, k.payload_sha256, k.runtime_bundle_digest, "
                "b.tenant_ref AS origin_tenant_ref FROM ONLY kernel_record k "
                "JOIN ONLY runtime_bundle b "
                "ON b.bundle_digest = k.runtime_bundle_digest "
                "WHERE k.record_kind = 'ofarm.referencesnapshot.v0.1' "
                "AND k.tenant_ref = %s ORDER BY k.record_time, k.record_id",
                (config.TENANT_REF,))
            reference_candidates = cur.fetchall()
            if any(row["origin_tenant_ref"] != config.TENANT_REF
                   for row in reference_candidates):
                raise ContextNotReconstructible(
                    "stored ReferenceSnapshot origin bundle belongs to another tenant")
            family_prefixes = tuple(
                family.snapshot_prefix for family in active_profile.reference_families)
            additional_reference_rows = [
                row for row in reference_candidates
                if isinstance(row["payload"], dict)
                and isinstance(row["payload"].get("referenceSnapshotId"), str)
                and any(
                    row["payload"]["referenceSnapshotId"] == prefix
                    or row["payload"]["referenceSnapshotId"].startswith(prefix + ".")
                    for prefix in family_prefixes)
            ]
            for row in additional_reference_rows:
                contract = ContractRegistry.validate(
                    store.registry, row["payload"])
                if contract.kind != "ofarm.referencesnapshot.v0.1":
                    raise ContextNotReconstructible(
                        "stored ReferenceSnapshot row resolves to the wrong contract")
                if sha256_bytes(canonical_json(row["payload"]).encode("utf-8")) \
                        != row["payload_sha256"]:
                    raise ContextNotReconstructible(
                        "stored ReferenceSnapshot payload digest does not match its bytes")
            additional_references = [
                row["payload"] for row in additional_reference_rows]
            _CURSOR_EXECUTE_READ(cur,
                "SELECT k.payload, k.payload_sha256, k.runtime_bundle_digest, "
                "b.tenant_ref AS origin_tenant_ref FROM ONLY kernel_record k "
                "JOIN ONLY runtime_bundle b "
                "ON b.bundle_digest = k.runtime_bundle_digest "
                "WHERE k.record_kind = ANY(%s) AND k.tenant_ref = %s "
                "ORDER BY k.record_time, k.record_id",
                ([
                    "ofarm.activeartifactset.v0.1",
                    "ofarm.packactivationset.v0.1",
                    "ofarm.agronomiccodebindingprofile.v0.1",
                ], config.TENANT_REF),
            )
            raw_profile_rows = cur.fetchall()
            if any(row["origin_tenant_ref"] != config.TENANT_REF
                   for row in raw_profile_rows):
                raise ContextNotReconstructible(
                    "stored profile spine origin bundle belongs to another tenant")
            expected_scope = {
                "scopeType": "TENANT", "scopeRef": config.TENANT_REF}

            def relevant_deployment(payload, scope_field):
                return (isinstance(payload, dict)
                        and payload.get("activePackRefs") == [active_profile.pack_ref]
                        and payload.get("activeProfileRefs") == [active_profile.profile_ref]
                        and payload.get(scope_field) == expected_scope)

            relevant_artifact_rows = [
                row for row in raw_profile_rows
                if isinstance(row["payload"], dict)
                and row["payload"].get("schemaVersion") ==
                "ofarm.activeartifactset.v0.1"
                and relevant_deployment(row["payload"], "deploymentScope")
            ]
            deployed_code_bindings = {active_profile.code_binding_profile_ref}
            for row in relevant_artifact_rows:
                active_refs = row["payload"].get("activeArtifactRefs")
                if not isinstance(active_refs, list):
                    continue
                deployed_code_bindings.update(
                    ref for ref in active_refs
                    if isinstance(ref, str)
                    and ref.startswith("codebindingprofile:"))
            additional_profile_rows = []
            for row in raw_profile_rows:
                payload = row["payload"]
                if not isinstance(payload, dict):
                    continue
                kind = payload.get("schemaVersion")
                if kind == "ofarm.activeartifactset.v0.1":
                    selected = relevant_deployment(payload, "deploymentScope")
                elif kind == "ofarm.packactivationset.v0.1":
                    selected = relevant_deployment(payload, "targetScope")
                elif kind == "ofarm.agronomiccodebindingprofile.v0.1":
                    profile_scope = payload.get("profileScope")
                    pack_refs = (profile_scope.get("packRefs")
                                 if isinstance(profile_scope, dict) else None)
                    code_binding_ref = payload.get(
                        "agronomicCodeBindingProfileId")
                    selected = (
                        code_binding_ref == active_profile.code_binding_profile_ref
                        or (
                            isinstance(pack_refs, list)
                            and all(isinstance(ref, str) for ref in pack_refs)
                            and active_profile.pack_ref in pack_refs
                            and code_binding_ref in deployed_code_bindings
                        )
                    )
                else:
                    selected = False
                if selected:
                    additional_profile_rows.append(row)
            for row in additional_profile_rows:
                contract = ContractRegistry.validate(
                    store.registry, row["payload"])
                if contract.kind not in {
                    "ofarm.activeartifactset.v0.1",
                    "ofarm.packactivationset.v0.1",
                    "ofarm.agronomiccodebindingprofile.v0.1",
                }:
                    raise ContextNotReconstructible(
                        "stored profile spine row resolves to the wrong contract")
                if sha256_bytes(canonical_json(row["payload"]).encode("utf-8")) \
                        != row["payload_sha256"]:
                    raise ContextNotReconstructible(
                        "stored profile spine payload digest does not match its bytes")
            origin_cache = {}
            profile_origin_bundles = {}
            for row in additional_profile_rows:
                payload = row["payload"]
                if payload.get("schemaVersion") != "ofarm.activeartifactset.v0.1":
                    continue
                if (payload.get("activePackRefs") != [active_profile.pack_ref]
                        or payload.get("activeProfileRefs") != [active_profile.profile_ref]
                        or payload.get("deploymentScope") != {
                            "scopeType": "TENANT", "scopeRef": config.TENANT_REF}):
                    # Out-of-lineage rows are deliberately not runtime inputs and
                    # therefore must not make startup depend on their origin bundle.
                    continue
                origin_digest = row["runtime_bundle_digest"]
                if origin_digest not in origin_cache:
                    origin_cache[origin_digest] = store.cold_load_runtime_bundle(
                        None, origin_digest)
                profile_origin_bundles[payload["activeArtifactSetId"]] = \
                    origin_cache[origin_digest]
            data_families = [family.data_family for family in
                             active_profile.reference_families if family.data_family]
            if data_families:
                _CURSOR_EXECUTE_READ(cur,
                    "SELECT d.snapshot_ref, d.data_family, d.artifact_ref, "
                    "d.source_digest, d.parser_label, d.record_count, d.payload, "
                    "d.payload_sha256, d.runtime_bundle_digest "
                    "FROM ONLY reference_snapshot_data d "
                    "JOIN ONLY runtime_bundle b "
                    "ON b.bundle_digest = d.runtime_bundle_digest "
                    "WHERE d.data_family = ANY(%s) AND b.tenant_ref = %s "
                    "ORDER BY d.snapshot_ref, d.data_family",
                    (data_families, config.TENANT_REF),
                )
                reference_data = cur.fetchall()
            else:
                reference_data = []
            bundle = _build_runtime_bundle_for_bootstrap(
                active_profile,
                additional_profile_payloads=[
                    row["payload"] for row in additional_profile_rows],
                profile_origin_bundles=profile_origin_bundles,
                additional_reference_payloads=additional_references,
                reference_data=reference_data,
                tenant_ref=config.TENANT_REF,
                _database_environment=Store._observe_database_environment(cur),
                _profile_route_selection=profile_route_selection,
            )
            payloads = _profile_payloads_from_bundle(
                store, active_profile, bundle)
            Store.install_runtime_bundle(store, cur, bundle)
            Store.assert_runtime_bundle_compatible(store, bundle)
            with Store._bootstrap_bundle_writes(store, bundle):
                for record_id, kind, payload, expected_digest in payloads:
                    _CURSOR_EXECUTE_READ(cur,
                        "SELECT record_kind, payload, payload_sha256, tenant_ref "
                        "FROM ONLY kernel_record "
                        "WHERE record_id = %s",
                        (record_id,),
                    )
                    existing = cur.fetchone()
                    if existing is not None:
                        if (existing["record_kind"] != kind
                                or existing["tenant_ref"] != bundle.tenant_ref
                                or existing["payload_sha256"] != expected_digest
                                or canonical_json(existing["payload"]) != canonical_json(payload)):
                            raise ContextNotReconstructible(
                                f"profile instance identifier {record_id!r} is already "
                                "bound to different canonical content")
                        continue
                    Store.insert_record(
                        store,
                        cur, payload, runtime_bundle_digest=bundle.digest)
                    inserted.append(record_id)
                # Catalog, registry, persisted-byte, cold-load, and selection-time
                # import-seal checks all run before this transaction may commit.
                # Activation repeats the exact seal check after COMMIT; a hostile
                # concurrent mutation can therefore refuse process binding, while
                # the already persisted bootstrap remains safe for exact restart.
                activation_token = Store._prepare_runtime_bundle_binding(
                    store, bundle)
    except (ContextNotReconstructible, RuntimeBundleError) as exc:
        Store._discard_prepared_runtime_bundle_binding(store)
        if isinstance(exc, RuntimeBundleError):
            raise ContextNotReconstructible(
                f"RuntimeBundle cannot be constructed: {exc}") from exc
        raise
    except Exception as exc:
        Store._discard_prepared_runtime_bundle_binding(store)
        raise ContextNotReconstructible(f"atomic RuntimeBundle bootstrap failed: {exc}") from exc
    Store._activate_prepared_runtime_bundle(store, activation_token)
    return inserted


def bootstrap(store) -> list[str]:
    """Load the shipped SI profile instances into the store (idempotent).

    These are package-validated instances (conformance self-check), inserted
    verbatim — never edited (AGENTS.md rule 4).
    """
    return bootstrap_for_descriptor(store, config.ACTIVE_PROFILE)


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
    # A runtime never reselects mutable store state. New imports become visible
    # only in a newly constructed RuntimeBundle (normally a restart).
    rows = [{"payload": payload} for payload in
            store.runtime_bundle.reference_payloads.values()]
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
        if not family.include_in_context:
            continue
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
        config.ACTIVE_PROFILE,
        as_of=as_of,
    )


class ProductRegister:
    """Offline product-register lookup for the in-force REGSR snapshots.

    Snapshot artifacts are dated parses of the official HTML surface
    (D9: no official export exists — posture declared, never hidden).
    Tests may register synthetic, clearly-fictional snapshot data through
    the same path; the runtime itself only ever reads registered artifacts.
    """

    def __setattr__(self, name, value):
        immutable_fields = {
            "bindings", "runtime_bundle", "_by_snapshot", "_frozen"}
        if ((name in immutable_fields and name in vars(self))
                or (vars(self).get("_frozen", False) is not False
                    and callable(getattr(type(self), name, None)))):
            raise AttributeError("ProductRegister runtime composition is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if (name in {
                "bindings", "runtime_bundle", "_by_snapshot", "_frozen"}
                or (vars(self).get("_frozen", False) is not False
                    and callable(getattr(type(self), name, None)))):
            raise AttributeError(
                "ProductRegister sealed runtime state cannot be deleted")
        object.__delattr__(self, name)

    def __init__(self, bindings: SIReferenceBindings | None = None, *,
                 runtime_bundle=None):
        self.bindings = bindings or SI_REFERENCE_BINDINGS
        self.runtime_bundle = runtime_bundle
        self._by_snapshot: dict[str, dict] = {}
        self._frozen = False
        # the shipped real parse (623 products, fictional-free: public register data)
        shipped = self.bindings.regsr_shipped_artifact_path
        if runtime_bundle is not None:
            self._load_runtime_bundle_bytes()
            self.freeze()
        elif shipped.exists():
            # Construction-only seam for focused parser tests. Governed runtime
            # construction always supplies a RuntimeBundle.
            self.register_artifact(
                self.bindings.regsr_shipped_snapshot_ref,
                json.loads(shipped.read_text()),
            )

    def _load_runtime_bundle_bytes(self) -> None:
        """Build the cache only from retained bytes before it becomes immutable."""
        for reference in self.runtime_bundle.selected_references:
            sid = reference.snapshot_ref
            if not _snapshot_matches_family(
                    sid, self.bindings.regsr_snapshot_prefix):
                continue
            if reference.data_family == self.bindings.regsr_data_family:
                self.register_artifact(
                    sid,
                    self.runtime_bundle.reference_data_payload(
                        sid, self.bindings.regsr_data_family),
                )
                continue
            snapshot = self.runtime_bundle.reference_payload(sid)
            artifact_refs = [
                ref for ref in snapshot.get("sourceArtifactRefs", [])
                if isinstance(ref, str) and ref.startswith("artifact:")]
            if not artifact_refs:
                continue
            if len(artifact_refs) != 1:
                raise RuntimeError(
                    f"selected REGSR snapshot {sid!r} has ambiguous source artifacts")
            component = self.runtime_bundle.component(
                "REFERENCE_SOURCE", artifact_refs[0])
            self.register_artifact(
                sid, json.loads(component.canonical_bytes.decode("utf-8")))

    def register_artifact(self, snapshot_id: str, artifact: dict) -> None:
        if self._frozen is not False:
            raise RuntimeError("ProductRegister is immutable for the RuntimeBundle lifetime")
        artifact = copy.deepcopy(artifact)
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
        if self.runtime_bundle is not None:
            require_store_runtime_bundle(
                store, self.runtime_bundle, "ProductRegister load")
            if self._frozen is not True:
                raise RuntimeBundleError(
                    "bundle-backed ProductRegister was not frozen at construction")
            return
        for row in store.reference_data(self.bindings.regsr_data_family):
            sid = row["snapshot_ref"]
            if sid not in self._by_snapshot:
                self.register_artifact(sid, row["payload"])
        for row in store.find_by_kind("ofarm.referencesnapshot.v0.1"):
            payload = row["payload"]
            sid = payload["referenceSnapshotId"]
            if not _snapshot_matches_family(sid, self.bindings.regsr_snapshot_prefix) \
                    or sid in self._by_snapshot:
                continue
            for ref in payload.get("sourceArtifactRefs", []):
                if isinstance(ref, str) and ref.startswith("artifact:"):
                    path = _resolve_profile_example_artifact(
                        self.bindings.si_profile_root,
                        ref.split(":", 1)[1],
                        required=False,
                        label=f"REGSR source artifact for {sid!r}",
                    )
                    if path is not None:
                        self.register_artifact(sid, json.loads(path.read_text()))

    def freeze(self) -> None:
        """End construction; later selection/cache mutation is forbidden."""
        if self._frozen is True:
            return
        if self._frozen is not False:
            raise RuntimeError("ProductRegister frozen state is malformed")
        object.__setattr__(self, "_by_snapshot", _freeze_runtime_cache(
            self._by_snapshot))
        object.__setattr__(self, "_frozen", True)

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
        return _copy_runtime_cache_value(list(distinct.values()))

    def lookup_by_decision(self, snapshot_id: str, decision_number: str) -> dict | None:
        """Identity-grade lookup (D9): the sole record for a decision number
        ONLY when that number is an unambiguous identity — exactly one distinct
        validity window. Zero matches OR an ambiguous decision number (multiple
        differing validity windows) returns None: ambiguity is never collapsed
        to a single record, it routes the caller to review."""
        ids = ProductRegister.identities_by_decision(
            self, snapshot_id, decision_number)
        return ids[0] if len(ids) == 1 else None

    def lookup(self, snapshot_id: str, regsr_code: str) -> dict | None:
        """Locator-grade lookup: regsrCode finds the list row, but a row is
        never product identity (D9) — callers must not treat a hit or miss
        here as an identity verdict."""
        data = self._by_snapshot.get(snapshot_id)
        if not data:
            return None
        return _copy_runtime_cache_value(data["products"].get(regsr_code))

    def detail(self, snapshot_id: str, regsr_code: str) -> dict | None:
        data = self._by_snapshot.get(snapshot_id)
        if not data:
            return None
        return _copy_runtime_cache_value(data["details"].get(regsr_code))

    def has_snapshot(self, snapshot_id: str) -> bool:
        return snapshot_id in self._by_snapshot


_RETAINED_PRODUCT_REGISTER_TYPE = ProductRegister
_PRODUCT_REGISTER_DECISION_DISPATCH = (
    ("identities_by_decision", ProductRegister.identities_by_decision,
     ProductRegister.identities_by_decision.__code__),
    ("lookup_by_decision", ProductRegister.lookup_by_decision,
     ProductRegister.lookup_by_decision.__code__),
)
_RETAINED_STORE_TRANSACTION_POSTURE = Store._require_transaction_python_posture
_RETAINED_STORE_TRANSACTION_POSTURE_CODE = \
    _RETAINED_STORE_TRANSACTION_POSTURE.__code__
_RETAINED_STORE_INTEGRITY_MARKER = Store._mark_transaction_integrity_violation
_RETAINED_STORE_INTEGRITY_MARKER_CODE = \
    _RETAINED_STORE_INTEGRITY_MARKER.__code__


def _mark_product_register_integrity_violation(store) -> None:
    if (type(store) is Store
            and vars(Store).get("_mark_transaction_integrity_violation") is
            _RETAINED_STORE_INTEGRITY_MARKER
            and _RETAINED_STORE_INTEGRITY_MARKER.__code__ is
            _RETAINED_STORE_INTEGRITY_MARKER_CODE):
        _RETAINED_STORE_INTEGRITY_MARKER(store)


def require_product_register_runtime_composition(
        store, register, label: str) -> None:
    """Require a frozen register rebuilt exactly from the selected bundle."""
    try:
        if (type(store) is not Store
                or globals().get(
                    "require_product_register_runtime_composition") is not
                _RETAINED_PRODUCT_REGISTER_COMPOSITION_GUARD
                or _RETAINED_PRODUCT_REGISTER_COMPOSITION_GUARD.__code__ is not
                _RETAINED_PRODUCT_REGISTER_COMPOSITION_GUARD_CODE
                or vars(Store).get("_require_transaction_python_posture") is not
                _RETAINED_STORE_TRANSACTION_POSTURE
                or _RETAINED_STORE_TRANSACTION_POSTURE.__code__ is not
                _RETAINED_STORE_TRANSACTION_POSTURE_CODE):
            raise RuntimeBundleError(
                f"{label} Store runtime dispatch changed before decision")
        _RETAINED_STORE_TRANSACTION_POSTURE(store)
        bundle = Store.runtime_bundle.fget(store)
        require_store_runtime_bundle(store, bundle, label)
        if (type(register) is not _RETAINED_PRODUCT_REGISTER_TYPE
                or vars(register).get("_frozen") is not True
                or register.runtime_bundle is not bundle
                or any(callable(getattr(_RETAINED_PRODUCT_REGISTER_TYPE, name, None))
                       for name in vars(register))
                or any(
                    vars(_RETAINED_PRODUCT_REGISTER_TYPE).get(name) is not function
                    or function.__code__ is not code
                    for name, function, code
                    in _PRODUCT_REGISTER_DECISION_DISPATCH)):
            raise RuntimeBundleError(
                f"{label} ProductRegister runtime composition changed")
        expected_bindings = SIReferenceBindings.from_descriptor(
            bundle.descriptor, runtime_bundle=bundle)
        expected = _RETAINED_PRODUCT_REGISTER_TYPE(
            expected_bindings, runtime_bundle=bundle)
        if (type(register.bindings) is not SIReferenceBindings
                or register.bindings != expected_bindings
                or _runtime_cache_state(register._by_snapshot) !=
                _runtime_cache_state(expected._by_snapshot)):
            raise RuntimeBundleError(
                f"{label} ProductRegister cache was not derived from selected bytes")
    except BaseException:
        _mark_product_register_integrity_violation(store)
        raise


_RETAINED_PRODUCT_REGISTER_COMPOSITION_GUARD = \
    require_product_register_runtime_composition
_RETAINED_PRODUCT_REGISTER_COMPOSITION_GUARD_CODE = \
    _RETAINED_PRODUCT_REGISTER_COMPOSITION_GUARD.__code__


def invoke_product_register_identities(
        store, register, snapshot_id: str, decision_number: str) -> list[dict]:
    """Invoke retained identity lookup with immediate composition checks."""
    _RETAINED_PRODUCT_REGISTER_COMPOSITION_GUARD(
        store, register, "REGSR product authorisation")
    function = _PRODUCT_REGISTER_DECISION_DISPATCH[0][1]
    try:
        result = function(register, snapshot_id, decision_number)
    except BaseException:
        _RETAINED_PRODUCT_REGISTER_COMPOSITION_GUARD(
            store, register, "REGSR product authorisation")
        raise
    _RETAINED_PRODUCT_REGISTER_COMPOSITION_GUARD(
        store, register, "REGSR product authorisation")
    return result


class ContextNotReconstructible(Exception):
    """A historical (AS_OF) context cannot be honestly reconstructed."""


class ContextAssembler:
    """Assembles (and reuses) per-farm Compliance-twin ContextSnapshots."""

    _SEALED_FIELDS = {
        "store", "active_profile", "runtime_bundle",
        "_runtime_composition_sealed",
    }

    def __setattr__(self, name, value):
        if "_runtime_composition_sealed" in vars(self):
            if name in self._SEALED_FIELDS:
                raise AttributeError(
                    "ContextAssembler runtime composition is immutable")
            if callable(getattr(type(self), name, None)):
                raise AttributeError(
                    "ContextAssembler runtime dispatch is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if ("_runtime_composition_sealed" in vars(self)
                and (name in self._SEALED_FIELDS
                     or callable(getattr(type(self), name, None)))):
            raise AttributeError(
                "ContextAssembler sealed runtime state cannot be deleted")
        object.__delattr__(self, name)

    def __init__(self, store, *, active_descriptor=None, active_profile=None,
                 runtime_bundle=None):
        self.store = store
        if (active_descriptor is not None and active_profile is not None
                and active_descriptor != active_profile):
            raise ProfileRuntimeError(
                "active_descriptor and active_profile refer to different descriptors")
        self.active_profile = _require_active_profile(
            resolve_active_descriptor(
                active_descriptor if active_descriptor is not None else active_profile,
                allow_config_default=True,
            ))
        self.runtime_bundle = runtime_bundle or store.runtime_bundle
        require_store_runtime_bundle(store, self.runtime_bundle, "ContextAssembler")
        if self.runtime_bundle.descriptor != self.active_profile:
            raise ProfileRuntimeError(
                "ContextAssembler descriptor and RuntimeBundle do not match exactly")
        self._runtime_composition_sealed = True

    def _assert_runtime_composition(self, cur=None) -> None:
        try:
            if (type(self) is not ContextAssembler
                    or vars(ContextAssembler).get(
                        "_assert_runtime_composition") is not
                    _RETAINED_CONTEXT_ASSERT_RUNTIME_COMPOSITION
                    or _RETAINED_CONTEXT_ASSERT_RUNTIME_COMPOSITION.__code__ is not
                    _RETAINED_CONTEXT_ASSERT_RUNTIME_COMPOSITION_CODE
                    or type(self.store) is not Store
                    or self._runtime_composition_sealed is not True
                    or self.runtime_bundle is not
                    Store.runtime_bundle.fget(self.store)
                    or self.runtime_bundle.descriptor != self.active_profile
                    or any(callable(getattr(ContextAssembler, name, None))
                           for name in vars(self))):
                raise RuntimeBundleError(
                    "ContextAssembler runtime composition changed")
            Store._require_transaction_python_posture(self.store)
            require_store_runtime_bundle(
                self.store, self.runtime_bundle, "ContextAssembler decision")
            if cur is not None:
                Store._require_active_governed_cursor(self.store, cur)
        except BaseException:
            if type(getattr(self, "store", None)) is Store:
                Store._mark_transaction_integrity_violation(self.store)
            raise

    def _spine(self, as_of: str | None = None) -> dict:
        # Spine selection is over immutable bundle bytes, never live rows that
        # may have appeared after startup. Store rows are bootstrap copies; the
        # bundle is the selected content authority for this runtime lifetime.
        instance_payloads = [
            self.runtime_bundle.json_component(
                component.role, component.logical_ref)
            for component in self.runtime_bundle.components
            if component.role in {"PROFILE_INSTANCE", "REFERENCE_SNAPSHOT"}
        ]
        artifact_sets = [{"payload": payload} for payload in instance_payloads
                         if payload.get("schemaVersion") ==
                         "ofarm.activeartifactset.v0.1"]
        activation_sets = [{"payload": payload} for payload in instance_payloads
                           if payload.get("schemaVersion") ==
                           "ofarm.packactivationset.v0.1"]
        profiles = [{"payload": payload} for payload in instance_payloads
                    if payload.get("schemaVersion") ==
                    "ofarm.agronomiccodebindingprofile.v0.1"]
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
        _RETAINED_CONTEXT_ASSERT_RUNTIME_COMPOSITION(self, cur)
        policy = evaluation_time_policy or {"policyType": "NOW"}
        # AS_OF context selects the reference snapshots in force AT that
        # moment; a missing family is honest (none was in force yet) and
        # makes the context content — and therefore the snapshot id and the
        # materialization key — distinct from the NOW answer
        as_of = policy.get("asOfTime") if policy.get("policyType") == "AS_OF" else None
        spine = ContextAssembler._spine(self, as_of=as_of)
        reference_snapshots = context_reference_snapshots_for_descriptor(
            self.store, self.active_profile, as_of=as_of)
        reference_refs = [p["referenceSnapshotId"] for p in reference_snapshots]

        material_basis = {
            "targetTwin": target_twin,
            "farm": farm_ref,
            "policy": policy,
            "activeArtifactSetRef": spine["artifact_set"]["activeArtifactSetId"],
            "sourcePackActivationSetRefs": [spine["activation_set"]["packActivationSetId"]],
            "activePackRefs": spine["activation_set"]["activePackRefs"],
            "activeProfileRefs": spine["activation_set"]["activeProfileRefs"],
            "referenceSnapshotRefs": reference_refs,
            "evidencePolicyRefs": [self.active_profile.evidence_policy_ref],
            "runtimeBundleDigest": self.runtime_bundle.digest,
        }
        digest = sha256_bytes(canonical_json(material_basis).encode("utf-8"))
        snapshot_id = (
            f"{self.active_profile.context_snapshot_id_prefix}."
            f"{_local(farm_ref)}.{target_twin.lower()}.{digest}"
        )

        existing_row = Store.get_record(self.store, snapshot_id)
        if existing_row:
            existing = existing_row["payload"]
            projected = {
                "targetTwin": existing["targetTwin"],
                "farm": existing["anchorScopes"][0]["scopeRef"],
                "policy": existing["evaluationTimePolicy"],
                "activeArtifactSetRef": existing["activeArtifactSetRef"],
                "sourcePackActivationSetRefs": existing["sourcePackActivationSetRefs"],
                "activePackRefs": existing["activePackRefs"],
                "activeProfileRefs": existing["activeProfileRefs"],
                "referenceSnapshotRefs": existing.get("referenceSnapshotRefs", []),
                "evidencePolicyRefs": existing.get("evidencePolicyRefs", []),
                "runtimeBundleDigest": existing_row["runtime_bundle_digest"],
            }
            if (existing_row["runtime_bundle_digest"] != self.runtime_bundle.digest
                    or canonical_json(projected) != canonical_json(material_basis)):
                raise ContextNotReconstructible(
                    "ContextSnapshot content identity was reused for unequal basis bytes")
            _RETAINED_CONTEXT_ASSERT_RUNTIME_COMPOSITION(self, cur)
            return existing

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
            "evidencePolicyRefs": [self.active_profile.evidence_policy_ref],
            "notes": "Per-farm Compliance-twin snapshot assembled from the shipped SI pilot spine.",
        }
        Store.insert_record(self.store, cur, payload)
        _RETAINED_CONTEXT_ASSERT_RUNTIME_COMPOSITION(self, cur)
        return payload


_RETAINED_CONTEXT_ASSERT_RUNTIME_COMPOSITION = \
    ContextAssembler._assert_runtime_composition
_RETAINED_CONTEXT_ASSERT_RUNTIME_COMPOSITION_CODE = \
    _RETAINED_CONTEXT_ASSERT_RUNTIME_COMPOSITION.__code__
_RETAINED_CONTEXT_ASSEMBLE = ContextAssembler.assemble
_RETAINED_CONTEXT_ASSEMBLE_CODE = _RETAINED_CONTEXT_ASSEMBLE.__code__


def _local(ref: str) -> str:
    """farm:demo.kmetija.a -> demo.kmetija.a (id-safe local part)."""
    return ref.split(":", 1)[-1].replace(":", ".")
