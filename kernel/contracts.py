"""Contract registry: the package contracts, loaded once, enforced on write.

KERNEL.md conformance condition 1: all Kernel contracts validate on write
(schema validation is necessary, never sufficient — semantic conformance is
separate and lives in the gate pipeline).

Two lanes:
  * canonical — contracts/kernel, contracts/core, contracts/platform
  * draft     — contracts/drafts_reference/explainable_current_state_evidence
                (implemented behind Kernel law, never promoted — D16; draft
                records land in runtime_trace, never in kernel_record)

Extracted contracts are read-only (AGENTS.md rule 4); this module only ever
reads them.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import jsonschema

from . import config


class ContractViolation(Exception):
    """A payload failed validation against its package contract."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class UnknownContract(Exception):
    """A payload carries a schemaVersion no package contract declares."""


def _assert_portable_json(value, path: str = "<root>") -> None:
    """Reject values whose JSON spelling is non-portable or non-standard."""
    if isinstance(value, str):
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError(f"{path} contains a Unicode surrogate") from exc
        return
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_portable_json(item, f"{path}/{index}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} contains a non-string object key")
            _assert_portable_json(key, f"{path}/<key>")
            _assert_portable_json(item, f"{path}/{key}")
        return
    raise ValueError(f"{path} contains unsupported JSON value {type(value).__name__}")


def canonical_json(payload: dict) -> str:
    """Strict UTF-8-portable deterministic serialization used for digests."""
    _assert_portable_json(payload)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_of(payload: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Contract:
    kind: str           # the schemaVersion const, e.g. 'ofarm.assertionrecord.v0.1'
    lane: str           # 'canonical' | 'draft'
    path: Path
    schema_hash: str         # sha256 of the contract file bytes as shipped
    schema_bytes: bytes      # exact bytes named by schema_hash / RuntimeBundle
    id_field: str | None     # payload property holding the record's own id;
                             # None for authored-artifact contracts (views,
                             # manifests) that never land in the record table

    @property
    def schema(self) -> dict:
        """Return a defensive parse; validation never trusts caller-mutable state."""
        return json.loads(self.schema_bytes.decode("utf-8"))


# The property that names each record. Explicit, not guessed: identifier
# collisions across contracts (requestId, resultId) are avoided by minting
# prefixed ids at creation time, not by schema magic.
_ID_FIELDS = {
    "ofarm.party.v0.1": "partyId",
    "ofarm.roleassignment.v0.1": "roleAssignmentId",
    "ofarm.authoritygrant.v0.1": "authorityGrantId",
    "ofarm.delegationgrant.v0.1": "delegationGrantId",
    "ofarm.sharinggrant.v0.1": "sharingGrantId",
    "ofarm.revocationdecision.v0.1": "revocationDecisionId",
    "ofarm.authorizationdecisionrequest.v0.1": "requestId",
    "ofarm.authorizationdecisionresult.v0.1": "resultId",
    "ofarm.authorizationdecisiontrace.v0.1": "traceId",
    "ofarm.identityrecord.v0.1": "identityRecordId",
    "ofarm.identitylifecyclechange.v0.1": "identityLifecycleChangeId",
    "ofarm.assertionrecord.v0.1": "assertionRecordId",
    "ofarm.evidencerecord.v0.1": "evidenceRecordId",
    "ofarm.complianceclaim.v0.1": "complianceClaimId",
    "ofarm.evidencesufficiencycase.v0.2": "sufficiencyCaseId",
    "ofarm.reviewdecision.v0.1": "reviewDecisionId",
    "ofarm.acceptedeventconsequence.v0.1": "acceptedEventConsequenceId",
    "ofarm.commitingressrequest.v0.1": "requestId",
    "ofarm.commitingressresult.v0.1": "resultId",
    "ofarm.promotiontrace.v0.1": "promotionTraceId",
    "ofarm.semanticeventenvelope.v0.1": "semanticEventId",
    "ofarm.runtimeproblem.v0.1": "problemId",
    "ofarm.materializationrequest.v0.1": "requestId",
    "ofarm.materializationresult.v0.1": "resultId",
    "ofarm.materializationbasis.v0.1": "basisId",
    "ofarm.materializationsnapshot.v0.1": "snapshotId",
    "ofarm.contextsnapshot.v0.1": "contextSnapshotId",
}


def _fallback_id_field(kind: str, schema: dict) -> str | None:
    """First required own-name property ending in 'Id'."""
    for name in schema.get("required", []):
        if name.endswith("Id"):
            return name
    return None


class ContractRegistry:
    def __setattr__(self, name, value):
        if getattr(self, "_sealed", False):
            raise AttributeError("ContractRegistry is immutable after construction")
        object.__setattr__(self, name, value)

    def __init__(self, contracts_root: Path | None = None):
        root = contracts_root or config.CONTRACTS_ROOT
        by_kind: dict[str, Contract] = {}
        for lane, directory in (
            ("canonical", root / "kernel"),
            ("canonical", root / "core"),
            ("canonical", root / "platform"),
            ("draft", config.DRAFTS_ROOT),
        ):
            for path in sorted(directory.glob("*.json")):
                raw = path.read_bytes()
                schema = json.loads(raw)
                const = (
                    schema.get("properties", {})
                    .get("schemaVersion", {})
                    .get("const")
                )
                if not const:
                    continue  # e.g. folder.status.json — not a contract
                id_field = _ID_FIELDS.get(const) or _fallback_id_field(const, schema)
                by_kind[const] = Contract(
                    kind=const,
                    lane=lane,
                    path=path,
                    schema_hash="sha256:" + hashlib.sha256(raw).hexdigest(),
                    schema_bytes=raw,
                    id_field=id_field,
                )
        self._by_kind = MappingProxyType(by_kind)
        self._sealed = True

    def get(self, kind: str) -> Contract:
        try:
            return self._by_kind[kind]
        except KeyError:
            raise UnknownContract(f"no package contract declares schemaVersion {kind!r}") from None

    def kinds(self) -> list[str]:
        return sorted(self._by_kind)

    def decision_identity(self) -> tuple:
        """Exact code-owned registry semantics beyond the schema file bytes."""
        return tuple(
            (
                kind,
                contract.lane,
                contract.id_field,
                str(contract.path.resolve()),
                contract.schema_hash,
                contract.schema_bytes,
            )
            for kind, contract in sorted(self._by_kind.items())
        )

    def validate(self, payload: dict) -> Contract:
        """Validate a payload against its declared contract.

        Returns the matched Contract; raises ContractViolation/UnknownContract.
        Schema validation here is necessary, never sufficient (KERNEL.md).
        """
        if not isinstance(payload, dict):
            raise ContractViolation("payload is not a JSON object")
        kind = payload.get("schemaVersion")
        if not isinstance(kind, str):
            raise ContractViolation("payload carries no schemaVersion")
        contract = self.get(kind)
        # Reparse the exact immutable bytes on every validation. Contract.schema
        # is intentionally a defensive view, so mutation after bundle binding
        # cannot alter decision semantics behind an unchanged schema digest.
        schema = json.loads(contract.schema_bytes.decode("utf-8"))
        validator = jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker())
        errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
        if errors:
            details = [
                f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
                for e in errors
            ]
            raise ContractViolation(
                f"payload violates {contract.path.name}: {details[0]}", errors=details
            )
        if contract.id_field is not None:
            record_id = payload.get(contract.id_field)
            if not isinstance(record_id, str) or not record_id:
                raise ContractViolation(
                    f"payload {kind} carries no usable id in field {contract.id_field!r}"
                )
        return contract
