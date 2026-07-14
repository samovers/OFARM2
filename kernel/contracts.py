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
from .callable_state import capture_callable_state, callable_state_matches


class ContractViolation(Exception):
    """A payload failed validation against its package contract."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class UnknownContract(Exception):
    """A payload carries a schemaVersion no package contract declares."""


class ContractDispatchError(RuntimeError):
    """Retained contract-validation code no longer matches class dispatch."""


def copy_exact_json(
        value,
        _isfinite=math.isfinite,
        _type=type,
        _id=id,
        _range=range,
        _set_type=set,
        _str_type=str,
        _bool_type=bool,
        _int_type=int,
        _float_type=float,
        _dict_type=dict,
        _dict_items=dict.items,
        _list_type=list,
        _list_len=list.__len__,
        _list_getitem=list.__getitem__,
        _violation_type=ContractViolation,
        _unicode_error=UnicodeEncodeError,
        _runtime_error=RuntimeError,
        _index_error=IndexError,
        _recursion_error=RecursionError,
):
    """Return a private JSON tree without caller-owned container dispatch.

    Contract validation, hashing, and persistence must all operate on one
    exact-built-in snapshot.  Calling ordinary ``dict``/``list`` methods on a
    subclass would let caller code change validation semantics after an
    adjacent integrity check and restore them before the next check.
    """
    active: set[int] = _set_type()

    def copy_value(item):
        item_type = _type(item)
        if item is None or item_type in {_str_type, _bool_type, _int_type}:
            if item_type is _str_type:
                try:
                    item.encode("utf-8", errors="strict")
                except _unicode_error as exc:
                    raise _violation_type(
                        "JSON payload contains a Unicode surrogate") from exc
            return item
        if item_type is _float_type:
            if not _isfinite(item):
                raise _violation_type(
                    "JSON payload contains a non-finite number")
            return item
        if item_type not in {_dict_type, _list_type}:
            raise _violation_type(
                "payload must contain only exact built-in JSON values")

        marker = _id(item)
        if marker in active:
            raise _violation_type("JSON payload contains a cyclic container")
        active.add(marker)
        try:
            if item_type is _list_type:
                return [
                    copy_value(_list_getitem(item, index))
                    for index in _range(_list_len(item))
                ]
            copied = {}
            for key, nested in _dict_items(item):
                if _type(key) is not _str_type:
                    raise _violation_type(
                        "JSON payload contains a non-string object key")
                try:
                    key.encode("utf-8", errors="strict")
                except _unicode_error as exc:
                    raise _violation_type(
                        "JSON payload contains a Unicode surrogate") from exc
                copied[key] = copy_value(nested)
            return copied
        except (_runtime_error, _index_error) as exc:
            raise _violation_type(
                "JSON payload changed while its snapshot was created") from exc
        finally:
            active.remove(marker)

    try:
        return copy_value(value)
    except _recursion_error as exc:
        raise _violation_type("JSON payload nesting is too deep") from exc


_RETAINED_COPY_EXACT_JSON = copy_exact_json


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


def _has_exact_builtin_json_types(value) -> bool:
    """Recognize the ordinary JSON tree without constructing error paths.

    Cycles are left for ``json.dumps`` and the strict diagnostic fallback to
    reject.  Subclasses deliberately take the fallback too, preserving their
    established validation and serialization behavior exactly.
    """
    pending = [value]
    visited_containers: dict[int, object] = {}
    while pending:
        item = pending.pop()
        item_type = type(item)
        if (item is None
                or item_type is str
                or item_type is bool
                or item_type is int
                or item_type is float):
            continue
        if item_type is list:
            marker = id(item)
            if marker not in visited_containers:
                visited_containers[marker] = item
                pending.extend(item)
            continue
        if item_type is dict:
            marker = id(item)
            if marker in visited_containers:
                continue
            visited_containers[marker] = item
            for key, nested in item.items():
                if type(key) is not str:
                    return False
                pending.append(nested)
            continue
        return False
    return True


def canonical_json(payload: dict) -> str:
    """Strict UTF-8-portable deterministic serialization used for digests."""
    if not _has_exact_builtin_json_types(payload):
        _assert_portable_json(payload)
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    try:
        rendered = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        rendered.encode("utf-8", errors="strict")
    except (TypeError, ValueError, RecursionError):
        # Preserve the existing path-specific exception type and message for
        # non-finite numbers, surrogates, cycles, and concurrent mutation.
        _assert_portable_json(payload)
        raise
    return rendered


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
_ID_FIELDS = MappingProxyType({
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
})


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

    def validate(
            self, payload: dict,
            _copy_exact_json=_RETAINED_COPY_EXACT_JSON,
            _json_loads=json.loads,
            _validator_type=jsonschema.Draft202012Validator,
            _format_checker_type=jsonschema.FormatChecker,
    ) -> Contract:
        """Validate a payload against its declared contract.

        Returns the matched Contract; raises ContractViolation/UnknownContract.
        Schema validation here is necessary, never sufficient (KERNEL.md).
        """
        if type(payload) is not dict:
            raise ContractViolation(
                "payload must be an exact built-in JSON object")
        payload = _copy_exact_json(payload)
        kind = payload.get("schemaVersion")
        if not isinstance(kind, str):
            raise ContractViolation("payload carries no schemaVersion")
        try:
            contract = self._by_kind[kind]
        except KeyError:
            raise UnknownContract(
                f"no package contract declares schemaVersion {kind!r}") from None
        # Reparse the exact immutable bytes on every validation. Contract.schema
        # is intentionally a defensive view, so mutation after bundle binding
        # cannot alter decision semantics behind an unchanged schema digest.
        schema = _json_loads(contract.schema_bytes.decode("utf-8"))
        validator = _validator_type(
            schema, format_checker=_format_checker_type())
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


_RETAINED_CONTRACT_REGISTRY_GET = ContractRegistry.get
_RETAINED_CONTRACT_REGISTRY_GET_CODE = ContractRegistry.get.__code__
_RETAINED_CONTRACT_REGISTRY_GET_STATE = capture_callable_state(
    _RETAINED_CONTRACT_REGISTRY_GET)
_RETAINED_CONTRACT_REGISTRY_VALIDATE = ContractRegistry.validate
_RETAINED_CONTRACT_REGISTRY_VALIDATE_CODE = ContractRegistry.validate.__code__
_RETAINED_CONTRACT_REGISTRY_VALIDATE_STATE = capture_callable_state(
    _RETAINED_CONTRACT_REGISTRY_VALIDATE)


def invoke_retained_contract_validation(
        registry: ContractRegistry, payload: dict,
        _get=_RETAINED_CONTRACT_REGISTRY_GET,
        _get_code=_RETAINED_CONTRACT_REGISTRY_GET_CODE,
        _get_state=_RETAINED_CONTRACT_REGISTRY_GET_STATE,
        _validate=_RETAINED_CONTRACT_REGISTRY_VALIDATE,
        _validate_code=_RETAINED_CONTRACT_REGISTRY_VALIDATE_CODE,
        _validate_state=_RETAINED_CONTRACT_REGISTRY_VALIDATE_STATE,
        _state_matches=callable_state_matches,
) -> Contract:
    """Invoke the reviewed validator directly, never mutable method dispatch."""
    def require() -> None:
        try:
            namespace = object.__getattribute__(registry, "__dict__")
        except AttributeError:
            namespace = None
        if (type(registry) is not ContractRegistry
                or type(namespace) is not dict
                or "validate" in namespace
                or "get" in namespace
                or vars(ContractRegistry).get("get") is not
                _get
                or _get.__code__ is not _get_code
                or not _state_matches(_get, _get_state)
                or vars(ContractRegistry).get("validate") is not
                _validate
                or _validate.__code__ is not _validate_code
                or not _state_matches(_validate, _validate_state)):
            raise ContractDispatchError(
                "ContractRegistry validation dispatch changed")

    require()
    try:
        result = _validate(registry, payload)
    except BaseException:
        require()
        raise
    require()
    return result
