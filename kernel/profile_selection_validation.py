"""Pure validation for one already-decoded profile selection."""
from __future__ import annotations

import re
from dataclasses import dataclass


_DESCRIPTOR_VERSION = "ofarm.profile-runtime-descriptor.local.v0_1"
_OMIT_FROM_CONTEXT = "OMIT_FROM_CONTEXT"
_REFUSE_CONTEXT = "REFUSE_CONTEXT"
_MISSING_BEHAVIORS = {_OMIT_FROM_CONTEXT, _REFUSE_CONTEXT}
_REF_RE = re.compile(r"^[a-z][a-z0-9_-]*:[A-Za-z0-9._:-]+$")
_FAMILY_RE = re.compile(r"^[a-z][a-z0-9_.-]*$")
_DESCRIPTOR_KEYS = {
    "descriptorVersion", "profileRef", "packRef", "packActivationSetRef",
    "activeArtifactSetRef", "codeBindingProfileRef", "evidencePolicyRef",
    "evidencePolicyPath", "profileInstanceFiles", "referenceFamilies",
    "contextSnapshotIdPrefix",
}
_REFERENCE_FAMILY_KEYS = {
    "familyId", "snapshotPrefix", "dataFamily", "requiredForNowContext",
    "requiredForAsOfContext", "missingFamilyBehaviorNow",
    "missingFamilyBehaviorAsOf", "shippedSnapshotRef",
}
_REFERENCE_FAMILY_REQUIRED = _REFERENCE_FAMILY_KEYS - {
    "dataFamily", "shippedSnapshotRef",
}


class ProfileSelectionValidationError(RuntimeError):
    """The decoded profile-selection documents are malformed or incoherent."""


@dataclass(frozen=True, slots=True)
class _ValidatedReferenceFamily:
    family_id: str
    snapshot_prefix: str
    data_family: str | None
    required_for_now_context: bool
    required_for_as_of_context: bool
    missing_family_behavior_now: str
    missing_family_behavior_as_of: str
    shipped_snapshot_ref: str | None


@dataclass(frozen=True, slots=True)
class ValidatedProfileDescriptor:
    """Immutable path-independent values accepted from a profile descriptor."""

    profile_instance_files: tuple[str, ...]
    reference_families: tuple[_ValidatedReferenceFamily, ...]


def validate_profile_descriptor_document(document: object) -> ValidatedProfileDescriptor:
    """Validate and return the path-independent descriptor values."""
    if not isinstance(document, dict):
        raise ProfileSelectionValidationError(
            "profile runtime descriptor must be a JSON object"
        )
    _reject_unknown(document, _DESCRIPTOR_KEYS, "descriptor")
    _require(document, _DESCRIPTOR_KEYS, "descriptor")
    if document["descriptorVersion"] != _DESCRIPTOR_VERSION:
        raise ProfileSelectionValidationError(
            f"unsupported descriptorVersion {document['descriptorVersion']!r}; "
            f"expected {_DESCRIPTOR_VERSION!r}"
        )
    for field in (
        "profileRef", "packRef", "packActivationSetRef", "activeArtifactSetRef",
        "codeBindingProfileRef", "evidencePolicyRef", "contextSnapshotIdPrefix",
    ):
        _validate_ref(document[field], field)
    files = _string_list(document["profileInstanceFiles"], "profileInstanceFiles")
    if len(files) != len(set(files)):
        raise ProfileSelectionValidationError(
            "profileInstanceFiles contains duplicate entries"
        )
    return ValidatedProfileDescriptor(
        tuple(files), _reference_families(document["referenceFamilies"])
    )


def validate_profile_selection_documents(
    descriptor_document: object,
    profile_instance_documents: object,
) -> None:
    """Validate the path-independent active profile spine."""
    descriptor = validate_profile_descriptor_document(descriptor_document)
    try:
        payloads = list(profile_instance_documents)
    except TypeError as exc:
        raise ProfileSelectionValidationError(
            "profile instance documents must be a sequence"
        ) from exc
    if any(not isinstance(payload, dict) for payload in payloads):
        raise ProfileSelectionValidationError(
            "profile instance documents must be JSON objects"
        )
    _validate_active_spine(descriptor_document, payloads)
    _validate_shipped_reference_refs(descriptor.reference_families, payloads)


def _reject_unknown(document: dict, allowed: set[str], label: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        raise ProfileSelectionValidationError(
            f"{label} contains unknown field(s): {unknown}"
        )


def _require(document: dict, required: set[str], label: str) -> None:
    missing = sorted(required - set(document))
    if missing:
        raise ProfileSelectionValidationError(
            f"{label} missing required field(s): {missing}"
        )


def _validate_ref(value: object, field: str) -> str:
    if not isinstance(value, str) or not _REF_RE.fullmatch(value):
        raise ProfileSelectionValidationError(
            f"{field} is not a valid OFARM-style ref: {value!r}"
        )
    return value


def _validate_family_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not _FAMILY_RE.fullmatch(value):
        raise ProfileSelectionValidationError(
            f"{field} is not a valid reference family id: {value!r}"
        )
    return value


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) for item in value
    ):
        raise ProfileSelectionValidationError(
            f"{field} must be a non-empty list of strings"
        )
    return value


def _reference_families(value: object) -> tuple[_ValidatedReferenceFamily, ...]:
    if not isinstance(value, list) or not value:
        raise ProfileSelectionValidationError(
            "referenceFamilies must be a non-empty list"
        )
    families = []
    seen_ids: set[str] = set()
    seen_prefixes: set[str] = set()
    for index, item in enumerate(value):
        label = f"referenceFamilies[{index}]"
        if not isinstance(item, dict):
            raise ProfileSelectionValidationError(f"{label} must be an object")
        _reject_unknown(item, _REFERENCE_FAMILY_KEYS, label)
        _require(item, _REFERENCE_FAMILY_REQUIRED, label)
        family_id = _validate_family_id(item["familyId"], f"{label}.familyId")
        prefix = _validate_ref(item["snapshotPrefix"], f"{label}.snapshotPrefix")
        if family_id in seen_ids:
            raise ProfileSelectionValidationError(
                f"duplicate reference family id {family_id!r}"
            )
        if prefix in seen_prefixes:
            raise ProfileSelectionValidationError(
                f"duplicate reference snapshot prefix {prefix!r}"
            )
        seen_ids.add(family_id)
        seen_prefixes.add(prefix)
        data_family = item.get("dataFamily")
        if data_family is not None:
            _validate_family_id(data_family, f"{label}.dataFamily")
        required_now = _bool(
            item["requiredForNowContext"], f"{label}.requiredForNowContext"
        )
        required_as_of = _bool(
            item["requiredForAsOfContext"], f"{label}.requiredForAsOfContext"
        )
        behavior_now = _missing_behavior(
            item["missingFamilyBehaviorNow"], f"{label}.missingFamilyBehaviorNow"
        )
        behavior_as_of = _missing_behavior(
            item["missingFamilyBehaviorAsOf"], f"{label}.missingFamilyBehaviorAsOf"
        )
        _assert_required_behavior(required_now, behavior_now, f"{label}.NOW")
        _assert_required_behavior(required_as_of, behavior_as_of, f"{label}.AS_OF")
        shipped = item.get("shippedSnapshotRef")
        if shipped is not None:
            _validate_ref(shipped, f"{label}.shippedSnapshotRef")
            if not _matches_family(shipped, prefix):
                raise ProfileSelectionValidationError(
                    f"{label}.shippedSnapshotRef {shipped!r} does not match prefix {prefix!r}"
                )
        families.append(_ValidatedReferenceFamily(
            family_id, prefix, data_family, required_now, required_as_of,
            behavior_now, behavior_as_of, shipped,
        ))
    return tuple(families)


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ProfileSelectionValidationError(f"{field} must be a boolean")
    return value


def _missing_behavior(value: object, field: str) -> str:
    if value not in _MISSING_BEHAVIORS:
        raise ProfileSelectionValidationError(
            f"{field} must be one of {sorted(_MISSING_BEHAVIORS)}"
        )
    return value


def _assert_required_behavior(required: bool, behavior: str, field: str) -> None:
    expected = _REFUSE_CONTEXT if required else _OMIT_FROM_CONTEXT
    if behavior != expected:
        raise ProfileSelectionValidationError(
            f"{field} required flag and missing behavior disagree: "
            f"required={required!r}, behavior={behavior!r}, expected {expected!r}"
        )


def _matches_family(snapshot_ref: str, prefix: str) -> bool:
    return snapshot_ref == prefix or snapshot_ref.startswith(prefix + ".")


def _validate_active_spine(document: dict, payloads: list[dict]) -> None:
    activation = _payload_by_id(
        payloads, "packActivationSetId", document["packActivationSetRef"]
    )
    artifact = _payload_by_id(
        payloads, "activeArtifactSetId", document["activeArtifactSetRef"]
    )
    profile = _payload_by_id(
        payloads, "agronomicCodeBindingProfileId", document["codeBindingProfileRef"]
    )
    if activation.get("activePackRefs") != [document["packRef"]]:
        raise ProfileSelectionValidationError(
            "PackActivationSet must declare exactly one active pack matching packRef"
        )
    if activation.get("activeProfileRefs") != [document["profileRef"]]:
        raise ProfileSelectionValidationError(
            "PackActivationSet must declare exactly one active profile matching profileRef"
        )
    if artifact.get("activePackRefs") != [document["packRef"]]:
        raise ProfileSelectionValidationError(
            "ActiveArtifactSet must declare exactly one active pack matching packRef"
        )
    if artifact.get("activeProfileRefs") != [document["profileRef"]]:
        raise ProfileSelectionValidationError(
            "ActiveArtifactSet must declare exactly one active profile matching profileRef"
        )
    if document["packRef"] not in activation.get("activePackRefs", []):
        raise ProfileSelectionValidationError("packRef is not active in the PackActivationSet")
    if document["profileRef"] not in activation.get("activeProfileRefs", []):
        raise ProfileSelectionValidationError("profileRef is not active in the PackActivationSet")
    if document["packActivationSetRef"] not in artifact.get("sourcePackActivationSetRefs", []):
        raise ProfileSelectionValidationError("ActiveArtifactSet does not source the PackActivationSet")
    if set(artifact.get("activePackRefs", [])) != set(activation.get("activePackRefs", [])):
        raise ProfileSelectionValidationError("ActiveArtifactSet activePackRefs do not match PackActivationSet")
    if set(artifact.get("activeProfileRefs", [])) != set(activation.get("activeProfileRefs", [])):
        raise ProfileSelectionValidationError(
            "ActiveArtifactSet activeProfileRefs do not match PackActivationSet"
        )
    if document["codeBindingProfileRef"] not in artifact.get("activeArtifactRefs", []):
        raise ProfileSelectionValidationError("ActiveArtifactSet does not deploy the code-binding profile")
    if document["evidencePolicyRef"] not in artifact.get("activeArtifactRefs", []):
        raise ProfileSelectionValidationError("ActiveArtifactSet does not deploy the evidence policy")
    if profile.get("profileState") != "ACTIVE":
        raise ProfileSelectionValidationError("code-binding profile is not ACTIVE")
    profile_scope = profile.get("profileScope")
    if not isinstance(profile_scope, dict):
        raise ProfileSelectionValidationError("code-binding profile profileScope must be an object")
    pack_refs = _string_list(profile_scope.get("packRefs"), "code-binding profile profileScope.packRefs")
    if pack_refs != [document["packRef"]]:
        raise ProfileSelectionValidationError(
            "code-binding profile profileScope.packRefs must match descriptor packRef"
        )


def _payload_by_id(payloads: list[dict], id_field: str, expected: object) -> dict:
    matches = [payload for payload in payloads if payload.get(id_field) == expected]
    if len(matches) != 1:
        raise ProfileSelectionValidationError(
            f"expected exactly one profile instance with {id_field}={expected!r}, "
            f"found {len(matches)}"
        )
    return matches[0]


def _validate_shipped_reference_refs(
    families: tuple[_ValidatedReferenceFamily, ...], payloads: list[dict]
) -> None:
    snapshots = {
        payload.get("referenceSnapshotId")
        for payload in payloads
        if payload.get("referenceSnapshotId")
    }
    for family in families:
        if family.shipped_snapshot_ref and family.shipped_snapshot_ref not in snapshots:
            raise ProfileSelectionValidationError(
                f"shipped snapshot {family.shipped_snapshot_ref!r} for family "
                f"{family.family_id!r} is not in profileInstanceFiles"
            )
