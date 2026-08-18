"""Observe and admit one manifest-pinned security-audit observer root."""
# ruff: noqa: E701, E702 -- the approved admission envelope has an exact 700-line cap.
from __future__ import annotations
from base64 import b64decode, b64encode, urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as BinasciiError
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from json import dumps, loads
from re import fullmatch
from typing import Protocol
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from google.cloud import kms_v1
_MANIFEST_SCHEMA = "ofarm.security-audit-observer-root-admission-manifest.v1"
_ATTESTATION_DOMAIN = b"OFARM2_SECURITY_AUDIT_OBSERVER_ROOT_ATTESTATION_V1\x00"
_EVIDENCE_DOMAIN = b"OFARM2_SECURITY_AUDIT_OBSERVER_ROOT_EVIDENCE_V1\x00"
_PROBE = b"\x00OFARM2-SECURITY-AUDIT-OBSERVER-ROOT-ADMISSION-V1\x00"
_KMS_TIMEOUT = 5.0
_HTTP_TIMEOUT = 5.0
_MAX_SPAN_US = 180_000_000
_LIFETIME_US = 30_000_000
_MAX_UNIX_US = 9_223_372_036_854_775_807
_MAX_MANIFEST = 8_192
_MAX_HTTP = 1_048_576
_MAX_ATTESTATION = 262_144
_MAX_CERTIFICATES = 16
_MAX_CERTIFICATE = 32_768
_RESOURCE_PATTERN = (
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/"
    r"locations/[a-z0-9](?:[a-z0-9-]*[a-z0-9])?/"
    r"keyRings/[A-Za-z0-9_-]{1,63}/"
    r"cryptoKeys/[A-Za-z0-9_-]{1,63}/"
    r"cryptoKeyVersions/[1-9][0-9]*$"
)
_PRINCIPAL_PATTERN = (
    r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@"
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$"
)
_MANIFEST_MEMBERS = ("attestationBundleSha256", "attestationFormat", "kmsKeyVersionResource", "observerKeyRoleEtag", "observerPrincipal", "observerPublicKey", "observerVersionRoleEtag", "schemaVersion", "signerPrincipal", "signerRoleEtag")
_RELEVANCE = {"HEURISTIC_RELEVANCE_NORMAL", "HEURISTIC_RELEVANCE_HIGH"}
_JSON_ENUMS = {"denyAccessState": {"DENY_ACCESS_STATE_DENIED", "DENY_ACCESS_STATE_NOT_DENIED"}, "membership": {"MEMBERSHIP_MATCHED", "MEMBERSHIP_NOT_MATCHED"}, "permissionMatchingState": {"PERMISSION_PATTERN_MATCHED", "PERMISSION_PATTERN_NOT_MATCHED"}, "relevance": _RELEVANCE}
_DENY_RULE_MEMBERS = ("combinedDeniedPermission", "combinedDeniedPrincipal", "combinedExceptionPermission", "combinedExceptionPrincipal", "deniedPermissions", "deniedPrincipals", "denyAccessState", "exceptionPermissions", "exceptionPrincipals", "relevance")
_DENY_POLICY_NAME = r"policies/cloudresourcemanager\.googleapis\.com%2F(?:projects|folders|organizations)%2F[1-9][0-9]*/denypolicies/[a-z](?:[a-z0-9.-]{1,61}[a-z0-9])"
_DENY_PERMISSION = r"[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*\.googleapis\.com/(?:[A-Za-z][A-Za-z0-9]*|\*)\.(?:[A-Za-z][A-Za-z0-9]*|\*)"
_DENY_PRINCIPAL = r"(?:principal://goog/subject/[^/?#\s]+|deleted:principal://goog/subject/[^/?#\s]+\?uid=[1-9][0-9]*|principal://iam\.googleapis\.com/projects/-/serviceAccounts/[^/?#\s]+|deleted:principal://iam\.googleapis\.com/projects/-/serviceAccounts/[^/?#\s]+\?uid=[1-9][0-9]*|principalSet://goog/group/[^/?#\s]+|deleted:principalSet://goog/group/[^/?#\s]+\?uid=[1-9][0-9]*|principalSet://goog/(?:public:all|cloudIdentityCustomerId/[A-Za-z0-9]+)|(?:deleted:)?principal://iam\.googleapis\.com/locations/global/workforcePools/[^/?#\s]+/subject/[^/?#\s]+|principalSet://iam\.googleapis\.com/(?:locations/global/workforcePools/[^/?#\s]+|projects/[1-9][0-9]*/locations/global/workloadIdentityPools/[^/?#\s]+)/(?:group/[^/?#\s]+|attribute\.[A-Za-z0-9_]+/[^/?#\s]+|\*)|principal://iam\.googleapis\.com/projects/[1-9][0-9]*/locations/global/workloadIdentityPools/[^/?#\s]+/subject/[^/?#\s]+|principalSet://cloudresourcemanager\.googleapis\.com/(?:projects|folders|organizations)/[1-9][0-9]*/type/(?:ServiceAccount|ServiceAgent)|principal://[a-z0-9.-]+\.system\.id\.goog/resources/[A-Za-z0-9._~!$&'()+,;=:@%/-]+|principalSet://[a-z0-9.-]+\.system\.id\.goog/(?:\*|attribute\.platformContainer/[A-Za-z0-9._~!$&'()+,;=:@%/-]+))"
class _KmsObserverClient(Protocol):
    def get_crypto_key(self, *, request: kms_v1.GetCryptoKeyRequest, retry: None, timeout: float) -> kms_v1.CryptoKey: ...
    def get_crypto_key_version(self, *, request: kms_v1.GetCryptoKeyVersionRequest, retry: None, timeout: float) -> kms_v1.CryptoKeyVersion: ...
    def get_public_key(self, *, request: kms_v1.GetPublicKeyRequest, retry: None, timeout: float) -> kms_v1.PublicKey: ...
class _KmsSignerClient(Protocol):
    def asymmetric_sign(self, *, request: kms_v1.AsymmetricSignRequest, retry: None, timeout: float) -> kms_v1.AsymmetricSignResponse: ...
class _EvidenceResponse(Protocol):
    status_code: int
    headers: Mapping[str, str]
    def iter_content(self, *, chunk_size: int) -> object: ...
    def close(self) -> None: ...
class _EvidenceSession(Protocol):
    def get(self, url: str, *, headers: Mapping[str, str], allow_redirects: bool, stream: bool, timeout: float) -> _EvidenceResponse: ...
    def post(self, url: str, *, data: bytes, headers: Mapping[str, str], allow_redirects: bool, stream: bool, timeout: float) -> _EvidenceResponse: ...
class _TrustedClock(Protocol):
    def __call__(self) -> int: ...
class SecurityAuditObserverRootAdmissionRefused(RuntimeError):
    pass
@dataclass(frozen=True, slots=True)
class SecurityAuditObserverRootAdmission:
    kms_key_version_resource: str
    observer_public_key: bytes
    signer_principal: str
    observer_principal: str
    attestation_bundle_sha256: bytes
    manifest_sha256: bytes
    snapshot_sha256: bytes
    evidence_sha256: bytes
    observed_at_unix_microseconds: int
    expires_at_unix_microseconds: int
@dataclass(frozen=True, slots=True)
class _Manifest:
    raw: bytes
    resource: str
    key: str
    project: str
    public_key: bytes
    attestation_digest: bytes
    attestation_format: str
    signer: str
    observer: str
    etags: tuple[str, str, str]
@dataclass(frozen=True, slots=True)
class _BindingSpec:
    role: str
    member: str
    permissions: tuple[str, ...]
    title: str
    expression: str
@dataclass(frozen=True, slots=True)
class _AccessSpec:
    principal: str
    resource: str
    permission: str
    required: str
    grant_role: str | None
def _bounded_bytes(value: object, maximum: int) -> bytes:
    if type(value) is not bytes or not value or len(value) > maximum:
        raise ValueError
    return value
def _reject_constant(_value: str) -> object:
    raise ValueError
def _pairs_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for name, member in pairs:
        if name in value:
            raise ValueError
        value[name] = member
    return value
def _canonical(value: object) -> bytes:
    return dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")
def _json_bytes(carrier: object, maximum: int, *, canonical: bool) -> dict[str, object]:
    raw = _bounded_bytes(carrier, maximum)
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError
    value = loads(raw.decode("utf-8"), object_pairs_hook=_pairs_object, parse_constant=_reject_constant)
    if type(value) is not dict or (canonical and _canonical(value) != raw):
        raise ValueError
    return value
def _members(value: object, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError
    names = set(value)
    if not set(required) <= names or not names <= set(required) | set(optional):
        raise ValueError
    return value
def _b64_standard(value: object, minimum: int = 1, maximum: int = 128) -> bytes:
    if type(value) is not str or fullmatch(r"(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?", value) is None:
        raise ValueError
    try:
        decoded = b64decode(value.encode("ascii"), validate=True)
    except (BinasciiError, ValueError):
        raise ValueError from None
    if not minimum <= len(decoded) <= maximum or b64encode(decoded).decode("ascii") != value:
        raise ValueError
    return decoded
def _b64url(value: object, exact: int) -> bytes:
    if type(value) is not str or fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise ValueError
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        decoded = urlsafe_b64decode((value + padding).encode("ascii"))
    except (BinasciiError, ValueError):
        raise ValueError from None
    if len(decoded) != exact or _b64url_text(decoded) != value:
        raise ValueError
    return decoded
def _b64url_text(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
def _manifest(value: object) -> _Manifest:
    document = _json_bytes(value, _MAX_MANIFEST, canonical=True)
    _members(document, _MANIFEST_MEMBERS)
    if tuple(sorted(document)) != tuple(sorted(_MANIFEST_MEMBERS)):
        raise ValueError
    resource = document["kmsKeyVersionResource"]
    signer = document["signerPrincipal"]
    observer = document["observerPrincipal"]
    digest_text = document["attestationBundleSha256"]
    attestation_format = document["attestationFormat"]
    if document["schemaVersion"] != _MANIFEST_SCHEMA or type(resource) is not str or fullmatch(_RESOURCE_PATTERN, resource) is None or type(signer) is not str or fullmatch(_PRINCIPAL_PATTERN, signer) is None or type(observer) is not str or fullmatch(_PRINCIPAL_PATTERN, observer) is None or signer == observer or type(digest_text) is not str or fullmatch(r"[0-9a-f]{64}", digest_text) is None or attestation_format not in {"CAVIUM_V1_COMPRESSED", "CAVIUM_V2_COMPRESSED"}:
        raise ValueError
    public_key = _b64url(document["observerPublicKey"], 32)
    Ed25519PublicKey.from_public_bytes(public_key)
    etags = tuple(document[name] for name in ("signerRoleEtag", "observerVersionRoleEtag", "observerKeyRoleEtag"))
    for etag in etags:
        _b64_standard(etag)
    pieces = resource.split("/")
    return _Manifest(value, resource, "/".join(pieces[:-2]), pieces[1], public_key, bytes.fromhex(digest_text), attestation_format, signer, observer, etags)
def _binding_specs(manifest: _Manifest) -> tuple[_BindingSpec, ...]:
    prefix = f"projects/{manifest.project}/roles/ofarmSecurityAuditObserverRoot"
    version_expression = (
        'resource.type == "cloudkms.googleapis.com/CryptoKeyVersion" && '
        f'resource.name == "{manifest.resource}"'
    )
    key_expression = (
        'resource.type == "cloudkms.googleapis.com/CryptoKey" && '
        f'resource.name == "{manifest.key}"'
    )
    return (
        _BindingSpec(prefix + "SignerV1", "serviceAccount:" + manifest.signer, ("cloudkms.cryptoKeyVersions.useToSign",), "ofarm-security-audit-observer-root-signer-v1", version_expression),
        _BindingSpec(prefix + "VersionReaderV1", "serviceAccount:" + manifest.observer, ("cloudkms.cryptoKeyVersions.get", "cloudkms.cryptoKeyVersions.viewPublicKey"), "ofarm-security-audit-observer-root-version-reader-v1", version_expression),
        _BindingSpec(prefix + "KeyReaderV1", "serviceAccount:" + manifest.observer, ("cloudkms.cryptoKeys.get",), "ofarm-security-audit-observer-root-key-reader-v1", key_expression),
    )
def _access_specs(manifest: _Manifest, bindings: tuple[_BindingSpec, ...]) -> tuple[_AccessSpec, ...]:
    signer, version, key = bindings
    return (
        _AccessSpec(manifest.signer, manifest.resource, "cloudkms.cryptoKeyVersions.useToSign", "CAN_ACCESS", signer.role),
        _AccessSpec(manifest.signer, manifest.resource, "cloudkms.cryptoKeyVersions.get", "CANNOT_ACCESS", None),
        _AccessSpec(manifest.signer, manifest.resource, "cloudkms.cryptoKeyVersions.update", "CANNOT_ACCESS", None),
        _AccessSpec(manifest.signer, manifest.resource, "cloudkms.cryptoKeyVersions.destroy", "CANNOT_ACCESS", None),
        _AccessSpec(manifest.signer, manifest.key, "cloudkms.cryptoKeys.setIamPolicy", "CANNOT_ACCESS", None),
        _AccessSpec(manifest.observer, manifest.resource, "cloudkms.cryptoKeyVersions.get", "CAN_ACCESS", version.role),
        _AccessSpec(manifest.observer, manifest.resource, "cloudkms.cryptoKeyVersions.viewPublicKey", "CAN_ACCESS", version.role),
        _AccessSpec(manifest.observer, manifest.key, "cloudkms.cryptoKeys.get", "CAN_ACCESS", key.role),
        _AccessSpec(manifest.observer, manifest.resource, "cloudkms.cryptoKeyVersions.useToSign", "CANNOT_ACCESS", None),
        _AccessSpec(manifest.observer, manifest.key, "cloudkms.cryptoKeys.setIamPolicy", "CANNOT_ACCESS", None),
    )
def _crc32c(value: bytes) -> int:
    checksum = 0xFFFFFFFF
    for octet in value:
        checksum ^= octet
        for _ in range(8):
            checksum = (checksum >> 1) ^ (0x82F63B78 if checksum & 1 else 0)
    return checksum ^ 0xFFFFFFFF
def _certificate_chain(value: object) -> list[str]:
    if not 1 <= len(value) <= _MAX_CERTIFICATES:
        raise ValueError
    result = []
    for certificate in value:
        if type(certificate) is not str:
            raise ValueError
        encoded = certificate.encode("utf-8")
        if not 1 <= len(encoded) <= _MAX_CERTIFICATE:
            raise ValueError
        result.append(certificate)
    return result
def _crypto_key(client: _KmsObserverClient, manifest: _Manifest) -> dict[str, object]:
    request = kms_v1.GetCryptoKeyRequest(name=manifest.key)
    value = client.get_crypto_key(request=request, retry=None, timeout=_KMS_TIMEOUT)
    if type(value) is not kms_v1.CryptoKey or "version_template" not in value:
        raise ValueError
    template = value.version_template
    if value.name != manifest.key or value.purpose != kms_v1.CryptoKey.CryptoKeyPurpose.ASYMMETRIC_SIGN or value.import_only is not False or "primary" in value or "rotation_period" in value or "next_rotation_time" in value or "key_access_justifications_policy" in value or template.algorithm != kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_ED25519 or template.protection_level != kms_v1.ProtectionLevel.HSM:
        raise ValueError
    return {"importOnly": False, "keyAccessJustificationsPolicyPresent": False, "name": manifest.key, "nextRotationTime": None, "primary": None, "purpose": "ASYMMETRIC_SIGN", "rotationPeriod": None, "versionTemplate": {"algorithm": "EC_SIGN_ED25519", "protectionLevel": "HSM"}}
def _crypto_key_version(client: _KmsObserverClient, manifest: _Manifest) -> dict[str, object]:
    request = kms_v1.GetCryptoKeyVersionRequest(name=manifest.resource)
    value = client.get_crypto_key_version(request=request, retry=None, timeout=_KMS_TIMEOUT)
    if type(value) is not kms_v1.CryptoKeyVersion or "attestation" not in value:
        raise ValueError
    attestation = value.attestation
    content = attestation.content
    chains = attestation.cert_chains
    formats = {
        kms_v1.KeyOperationAttestation.AttestationFormat.CAVIUM_V1_COMPRESSED: "CAVIUM_V1_COMPRESSED",
        kms_v1.KeyOperationAttestation.AttestationFormat.CAVIUM_V2_COMPRESSED: "CAVIUM_V2_COMPRESSED",
    }
    if value.name != manifest.resource or value.state != kms_v1.CryptoKeyVersion.CryptoKeyVersionState.ENABLED or value.algorithm != kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_ED25519 or value.protection_level != kms_v1.ProtectionLevel.HSM or value.reimport_eligible is not False or "import_job" in value or "import_time" in value or attestation.format not in formats or formats[attestation.format] != manifest.attestation_format or type(content) is not bytes or not 1 <= len(content) <= _MAX_ATTESTATION:
        raise ValueError
    bundle = {"caviumCerts": _certificate_chain(chains.cavium_certs), "content": b64encode(content).decode("ascii"), "format": manifest.attestation_format, "googleCardCerts": _certificate_chain(chains.google_card_certs), "googlePartitionCerts": _certificate_chain(chains.google_partition_certs)}
    if sha256(_ATTESTATION_DOMAIN + _canonical(bundle)).digest() != manifest.attestation_digest:
        raise ValueError
    return {"algorithm": "EC_SIGN_ED25519", "attestation": bundle, "importJob": None, "importTime": None, "name": manifest.resource, "protectionLevel": "HSM", "reimportEligible": False, "state": "ENABLED"}
def _public_key(client: _KmsObserverClient, manifest: _Manifest) -> dict[str, object]:
    request = kms_v1.GetPublicKeyRequest(name=manifest.resource, public_key_format=kms_v1.PublicKey.PublicKeyFormat.DER)
    value = client.get_public_key(request=request, retry=None, timeout=_KMS_TIMEOUT)
    if type(value) is not kms_v1.PublicKey or "public_key" not in value:
        raise ValueError
    checked = value.public_key
    der = checked.data
    checksum = checked.crc32c_checksum
    if value.name != manifest.resource or value.algorithm != kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_ED25519 or value.protection_level != kms_v1.ProtectionLevel.HSM or value.public_key_format != kms_v1.PublicKey.PublicKeyFormat.DER or "pem" in value or "pem_crc32c" in value or type(der) is not bytes or der != bytes.fromhex("302a300506032b6570032100") + manifest.public_key or "crc32c_checksum" not in checked or type(checksum) is not int or isinstance(checksum, bool) or not 0 <= checksum <= 0xFFFFFFFF or checksum != _crc32c(der):
        raise ValueError
    return {"algorithm": "EC_SIGN_ED25519", "name": manifest.resource, "pem": None, "pemCrc32c": None, "protectionLevel": "HSM", "publicKey": {"crc32cChecksum": checksum, "data": b64encode(der).decode("ascii")}, "publicKeyFormat": "DER"}
def _http_document(response: object) -> dict[str, object]:
    try:
        if (
            type(response.status_code) is not int
            or response.status_code != 200
            or not isinstance(response.headers, Mapping)
            or not callable(response.iter_content)
            or not callable(response.close)
        ):
            raise ValueError
        content_types = [value for name, value in response.headers.items() if type(name) is str and name.lower() == "content-type"]
        if len(content_types) != 1 or type(content_types[0]) is not str or content_types[0].split(";", 1)[0].strip().lower() != "application/json":
            raise ValueError
        body = bytearray()
        for chunk in response.iter_content(chunk_size=65_536):
            if type(chunk) is not bytes:
                raise ValueError
            body.extend(chunk)
            if len(body) > _MAX_HTTP:
                raise ValueError
        return _json_bytes(bytes(body), _MAX_HTTP, canonical=False)
    finally:
        if callable(getattr(response, "close", None)):
            response.close()
def _role(session: _EvidenceSession, name: str, permissions: tuple[str, ...], etag: str) -> dict[str, object]:
    response = session.get(
        "https://iam.googleapis.com/v1/" + name,
        headers={"Accept": "application/json"},
        allow_redirects=False,
        stream=True,
        timeout=_HTTP_TIMEOUT,
    )
    value = _http_document(response)
    _members(value, ("deleted", "description", "etag", "includedPermissions", "name", "stage", "title"))
    included = value["includedPermissions"]
    if (
        value["name"] != name
        or value["etag"] != etag
        or value["stage"] != "GA"
        or value["deleted"] is not False
        or type(value["title"]) is not str
        or type(value["description"]) is not str
        or type(included) is not list
        or included != list(permissions)
        or any(type(item) is not str for item in included)
    ):
        raise ValueError
    return value
def _text(value: object) -> str:
    if type(value) is not str or not value or len(value.encode("utf-8")) > _MAX_HTTP:
        raise ValueError
    return value
def _expr(value: object) -> dict[str, object]:
    document = _members(value, ("expression",), ("description", "location", "title"))
    result = {"expression": _text(document["expression"])}
    for name in ("description", "location", "title"):
        if name in document:
            if type(document[name]) is not str:
                raise ValueError
            result[name] = document[name]
    return result
def _condition_explanation(value: object) -> dict[str, object]:
    document = _members(value, ("value",), ("errors", "evaluationStates"))
    if type(document["value"]) is not bool or document.get("errors", []) != []:
        raise ValueError
    states = document.get("evaluationStates", [])
    if type(states) is not list:
        raise ValueError
    normalized = []
    for state in states:
        item = _members(state, ("end", "start", "value"), ("errors",))
        if (
            type(item["start"]) is not int
            or isinstance(item["start"], bool)
            or type(item["end"]) is not int
            or isinstance(item["end"], bool)
            or item["start"] < 0
            or item["end"] < item["start"]
            or type(item["value"]) is not bool
            or item.get("errors", []) != []
        ):
            raise ValueError
        normalized.append({"end": item["end"], "errors": [], "start": item["start"], "value": item["value"]})
    return {"errors": [], "evaluationStates": normalized, "value": document["value"]}
def _policy_binding(value: object) -> dict[str, object]:
    document = _members(value, ("members", "role"), ("condition",))
    members = document["members"]
    if (
        fullmatch(r"(?:projects|organizations)/[^/]+/roles/[A-Za-z0-9_.-]+|roles/[A-Za-z0-9_.-]+", _text(document["role"])) is None
        or type(members) is not list
        or not members
        or any(type(member) is not str or not member for member in members)
        or len(set(members)) != len(members)
    ):
        raise ValueError
    result = {"members": sorted(members), "role": document["role"]}
    if "condition" in document:
        result["condition"] = _expr(document["condition"])
    return result
def _audit_config(value: object) -> dict[str, object]:
    document = _members(value, ("auditLogConfigs", "service"))
    configs = document["auditLogConfigs"]
    if type(configs) is not list or type(document["service"]) is not str:
        raise ValueError
    normalized = []
    for config in configs:
        item = _members(config, ("logType",), ("exemptedMembers",))
        exempted = item.get("exemptedMembers", [])
        if item["logType"] not in {"ADMIN_READ", "DATA_READ", "DATA_WRITE"} or type(exempted) is not list or any(type(member) is not str for member in exempted):
            raise ValueError
        normalized.append({"exemptedMembers": sorted(exempted), "logType": item["logType"]})
    return {"auditLogConfigs": sorted(normalized, key=_canonical), "service": document["service"]}
def _iam_policy(value: object) -> dict[str, object]:
    document = _members(value, ("bindings", "etag", "version"), ("auditConfigs",))
    bindings = document["bindings"]
    audits = document.get("auditConfigs", [])
    if (
        type(document["version"]) is not int
        or isinstance(document["version"], bool)
        or document["version"] not in {1, 3}
        or type(bindings) is not list
        or type(audits) is not list
    ):
        raise ValueError
    _b64_standard(document["etag"])
    normalized_bindings = [_policy_binding(binding) for binding in bindings]
    if any("condition" in binding for binding in normalized_bindings) and document["version"] != 3:
        raise ValueError
    return {
        "auditConfigs": sorted((_audit_config(item) for item in audits), key=_canonical),
        "bindings": normalized_bindings,
        "etag": document["etag"],
        "version": document["version"],
    }
def _membership(value: object) -> dict[str, str]:
    document = _members(value, ("membership", "relevance"))
    if document["membership"] not in {"MEMBERSHIP_MATCHED", "MEMBERSHIP_NOT_MATCHED"} or document["relevance"] not in _RELEVANCE:
        raise ValueError
    return {"membership": document["membership"], "relevance": document["relevance"]}
def _allow_binding(value: object, binding: dict[str, object]) -> dict[str, object]:
    required = ("allowAccessState", "combinedMembership", "memberships", "relevance", "role", "rolePermission", "rolePermissionRelevance")
    document = _members(value, required, ("condition", "conditionExplanation"))
    if (
        document["role"] != binding["role"]
        or document["rolePermission"] not in {"ROLE_PERMISSION_INCLUDED", "ROLE_PERMISSION_NOT_INCLUDED"}
        or document["rolePermissionRelevance"] not in _RELEVANCE
        or document["relevance"] not in _RELEVANCE
        or type(document["memberships"]) is not dict
        or set(document["memberships"]) != set(binding["members"])
    ):
        raise ValueError
    memberships = {name: _membership(item) for name, item in document["memberships"].items()}
    combined = _membership(document["combinedMembership"])
    matched = any(item["membership"] == "MEMBERSHIP_MATCHED" for item in memberships.values())
    if combined["membership"] != ("MEMBERSHIP_MATCHED" if matched else "MEMBERSHIP_NOT_MATCHED"):
        raise ValueError
    condition_passes = True
    result = dict(document)
    result["combinedMembership"] = combined
    result["memberships"] = memberships
    if "condition" in binding:
        if "condition" not in document or "conditionExplanation" not in document or _expr(document["condition"]) != binding["condition"]:
            raise ValueError
        result["condition"] = binding["condition"]
        result["conditionExplanation"] = _condition_explanation(document["conditionExplanation"])
        condition_passes = result["conditionExplanation"]["value"]
    elif "condition" in document or "conditionExplanation" in document:
        raise ValueError
    granted = document["rolePermission"] == "ROLE_PERMISSION_INCLUDED" and matched and condition_passes
    if document["allowAccessState"] != ("ALLOW_ACCESS_STATE_GRANTED" if granted else "ALLOW_ACCESS_STATE_NOT_GRANTED"):
        raise ValueError
    return result
def _expected_binding(binding: dict[str, object], spec: _BindingSpec) -> bool:
    condition = binding.get("condition")
    return (
        binding["role"] == spec.role
        and binding["members"] == [spec.member]
        and type(condition) is dict
        and condition.get("expression") == spec.expression
        and condition.get("title") == spec.title
    )
def _allow_policy(value: object, access: _AccessSpec, specs: tuple[_BindingSpec, ...], counts: dict[str, int]) -> tuple[dict[str, object], int]:
    document = _members(value, ("allowAccessState", "bindingExplanations", "fullResourceName", "policy", "relevance"))
    if document["allowAccessState"] not in {"ALLOW_ACCESS_STATE_GRANTED", "ALLOW_ACCESS_STATE_NOT_GRANTED"} or document["relevance"] not in _RELEVANCE or not _text(document["fullResourceName"]).startswith("//"):
        raise ValueError
    policy = _iam_policy(document["policy"])
    explanations = document["bindingExplanations"]
    if type(explanations) is not list or len(explanations) != len(policy["bindings"]):
        raise ValueError
    normalized = []
    grants = 0
    protected = {item.member for item in specs}
    by_role = {item.role: item for item in specs}
    for binding, explanation in zip(policy["bindings"], explanations, strict=True):
        item = _allow_binding(explanation, binding)
        role = binding["role"]
        if role in by_role:
            spec = by_role[role]
            counts[role] += 1
            if not _expected_binding(binding, spec) or document["fullResourceName"] != "//cloudkms.googleapis.com/" + access.resource.rsplit("/cryptoKeyVersions/", 1)[0]:
                raise ValueError
            expected_permission = access.permission in spec.permissions
            if (item["rolePermission"] == "ROLE_PERMISSION_INCLUDED") != expected_permission:
                raise ValueError
        elif protected.intersection(binding["members"]):
            raise ValueError
        if item["combinedMembership"]["membership"] == "MEMBERSHIP_MATCHED":
            if role not in by_role or by_role[role].member != "serviceAccount:" + access.principal:
                raise ValueError
        if access.permission == "cloudkms.cryptoKeyVersions.useToSign" and item["rolePermission"] == "ROLE_PERMISSION_INCLUDED" and role != specs[0].role:
            raise ValueError
        if item["allowAccessState"] == "ALLOW_ACCESS_STATE_GRANTED":
            grants += 1
        normalized.append(item)
    policy_granted = grants > 0
    if document["allowAccessState"] != ("ALLOW_ACCESS_STATE_GRANTED" if policy_granted else "ALLOW_ACCESS_STATE_NOT_GRANTED"):
        raise ValueError
    policy["bindings"] = sorted(policy["bindings"], key=_canonical)
    return ({"allowAccessState": document["allowAccessState"], "bindingExplanations": sorted(normalized, key=_canonical), "fullResourceName": document["fullResourceName"], "policy": policy, "relevance": document["relevance"]}, grants)
def _allow(value: object, access: _AccessSpec, specs: tuple[_BindingSpec, ...]) -> dict[str, object]:
    document = _members(value, ("allowAccessState", "explainedPolicies", "relevance"))
    policies = document["explainedPolicies"]
    if document["allowAccessState"] not in {"ALLOW_ACCESS_STATE_GRANTED", "ALLOW_ACCESS_STATE_NOT_GRANTED"} or document["relevance"] not in _RELEVANCE or type(policies) is not list or not policies:
        raise ValueError
    counts = {item.role: 0 for item in specs}
    normalized = []
    grants = 0
    for policy in policies:
        item, policy_grants = _allow_policy(policy, access, specs, counts)
        normalized.append(item)
        grants += policy_grants
    if any(count != 1 for count in counts.values()) or grants != (1 if access.required == "CAN_ACCESS" else 0):
        raise ValueError
    expected_state = "ALLOW_ACCESS_STATE_GRANTED" if grants else "ALLOW_ACCESS_STATE_NOT_GRANTED"
    if document["allowAccessState"] != expected_state:
        raise ValueError
    if grants and not any(item["role"] == access.grant_role and item["allowAccessState"] == "ALLOW_ACCESS_STATE_GRANTED" for policy in normalized for item in policy["bindingExplanations"]):
        raise ValueError
    return {"allowAccessState": expected_state, "explainedPolicies": sorted(normalized, key=_canonical), "relevance": document["relevance"]}
def _require(condition: bool) -> None:
    if condition is not True: raise ValueError
def _limited(value: object, maximum: int, pattern: str | None = None, minimum: int = 1) -> str:
    _require(type(value) is str and minimum <= len(value) <= maximum and (pattern is None or fullmatch(pattern, value) is not None)); return value
def _deny_timestamp(value: object) -> tuple[datetime, int]:
    text = _limited(value, 30); _require(fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\.(?:[0-9]{3}|[0-9]{6}|[0-9]{9}))?Z", text) is not None); return datetime.fromisoformat(text[:19] + "+00:00"), int(((text[20:-1] if text[19:20] == "." else "") + "000000000")[:9])
def _deny_values(value: object, pattern: str, maximum: int, required: bool) -> list[str]:
    _require(type(value) is list and len(value) <= 500 and (not required or bool(value))); result = [_limited(item, maximum, pattern) for item in value]; _require(len(result) == len(set(result))); return sorted(result)
def _deny_rule(value: object) -> dict[str, object]:
    document = _members(value, ("denyRule",), ("description",)); rule = _members(document["denyRule"], ("deniedPermissions", "deniedPrincipals"), ("denialCondition", "exceptionPermissions", "exceptionPrincipals"))
    result = {"deniedPermissions": _deny_values(rule["deniedPermissions"], _DENY_PERMISSION, 256, True), "deniedPrincipals": _deny_values(rule["deniedPrincipals"], _DENY_PRINCIPAL, 2_048, True), "exceptionPermissions": _deny_values(rule.get("exceptionPermissions", []), _DENY_PERMISSION, 256, False), "exceptionPrincipals": _deny_values(rule.get("exceptionPrincipals", []), _DENY_PRINCIPAL, 2_048, False)}
    _require("principalSet://goog/public:all" not in result["exceptionPrincipals"])
    if "denialCondition" in rule: result["denialCondition"] = _expr(rule["denialCondition"])
    return {"denyRule": result, **({"description": _limited(document["description"], 256, minimum=0)} if "description" in document else {})}
def _deny_policy_text(value: object) -> dict[str, object]:
    document = _members(value, ("createTime", "etag", "kind", "name", "rules", "uid", "updateTime"), ("annotations", "deleteTime", "displayName")); rules = document["rules"]; annotations = document.get("annotations", {})
    _limited(document["name"], 256, _DENY_POLICY_NAME); _limited(document["uid"], 128); _require(document["kind"] == "DenyPolicy" and type(rules) is list and 1 <= len(rules) <= 500 and "deleteTime" not in document); _b64_standard(document["etag"]); _require(_deny_timestamp(document["updateTime"]) >= _deny_timestamp(document["createTime"]))
    _require(type(annotations) is dict and len(annotations) <= 64 and not any(type(key) is not str or not 1 <= len(key) <= 63 or type(item) is not str or len(item) > 255 for key, item in annotations.items()))
    normalized = {name: document[name] for name in ("createTime", "etag", "kind", "name", "uid", "updateTime")}; normalized["rules"] = [_deny_rule(rule) for rule in rules]
    return {**normalized, **({"displayName": _limited(document["displayName"], 63, minimum=0)} if "displayName" in document else {}), **({"annotations": dict(sorted(annotations.items()))} if "annotations" in document else {})}
def _deny_annotation(value: object, state: str) -> dict[str, object]:
    document = _members(value, (state, "relevance")); _require(document[state] in _JSON_ENUMS[state] and document["relevance"] in _RELEVANCE); return document
def _deny_map(value: object, state: str) -> dict[str, object]:
    _require(type(value) is dict and len(value) <= 500 and not any(type(name) is not str or not name for name in value)); return {name: _deny_annotation(item, state) for name, item in value.items()}
def _deny_pair(item: dict[str, object], combined_name: str, map_name: str, state: str, expected: list[str]) -> tuple[dict[str, object], dict[str, object], bool]:
    combined = _deny_annotation(item[combined_name], state); members = _deny_map(item[map_name], state); matched_state = "PERMISSION_PATTERN_MATCHED" if state == "permissionMatchingState" else "MEMBERSHIP_MATCHED"; matched = any(member[state] == matched_state for member in members.values()); _require(set(members) == set(expected) and (combined[state] == matched_state) == matched); return combined, members, matched
def _deny_permission_matches(pattern: str, access: _AccessSpec) -> bool:
    service, member = pattern.split("/", 1); resource, action = member.split(".", 1); expected_resource, expected_action = access.permission.split(".", 1)[1].split(".", 1); return service == "cloudkms.googleapis.com" and resource in {"*", expected_resource} and action in {"*", expected_action}
def _deny_principal_matches(pattern: str, access: _AccessSpec) -> bool | None:
    return True if pattern in {"principal://iam.googleapis.com/projects/-/serviceAccounts/" + access.principal, "principalSet://goog/public:all"} else (False if pattern.startswith(("principal://", "deleted:principal://")) else None)
def _deny_policy(value: object, access: _AccessSpec) -> dict[str, object]:
    document = _members(value, ("denyAccessState", "policy", "relevance", "ruleExplanations")); policy = _deny_policy_text(document["policy"]); explanations = document["ruleExplanations"]; _require(document["denyAccessState"] in _JSON_ENUMS["denyAccessState"] and document["relevance"] in _RELEVANCE and type(explanations) is list and len(explanations) == len(policy["rules"]))
    normalized = []
    for policy_rule, explanation in zip(policy["rules"], explanations, strict=True):
        rule = policy_rule["denyRule"]; item = _members(explanation, _DENY_RULE_MEMBERS, ("condition", "conditionExplanation")); _require(item["denyAccessState"] in _JSON_ENUMS["denyAccessState"] and item["relevance"] in _RELEVANCE)
        result = dict(item); denied_permission = _deny_pair(item, "combinedDeniedPermission", "deniedPermissions", "permissionMatchingState", rule["deniedPermissions"]); exception_permission = _deny_pair(item, "combinedExceptionPermission", "exceptionPermissions", "permissionMatchingState", rule["exceptionPermissions"]); denied_principal = _deny_pair(item, "combinedDeniedPrincipal", "deniedPrincipals", "membership", rule["deniedPrincipals"]); exception_principal = _deny_pair(item, "combinedExceptionPrincipal", "exceptionPrincipals", "membership", rule["exceptionPrincipals"])
        for names, pair in zip((("combinedDeniedPermission", "deniedPermissions"), ("combinedExceptionPermission", "exceptionPermissions"), ("combinedDeniedPrincipal", "deniedPrincipals"), ("combinedExceptionPrincipal", "exceptionPrincipals")), (denied_permission, exception_permission, denied_principal, exception_principal), strict=True): result[names[0]], result[names[1]] = pair[:2]
        _require(not any((annotation["permissionMatchingState"] == "PERMISSION_PATTERN_MATCHED") != _deny_permission_matches(pattern, access) for pair in (denied_permission, exception_permission) for pattern, annotation in pair[1].items()))
        _require(not any((known := _deny_principal_matches(pattern, access)) is not None and (annotation["membership"] == "MEMBERSHIP_MATCHED") != known for pair in (denied_principal, exception_principal) for pattern, annotation in pair[1].items()))
        condition = "denialCondition" in rule; _require(("condition" in item) == condition and ("conditionExplanation" in item) == condition and (not condition or _expr(item["condition"]) == rule["denialCondition"]))
        condition_explanation = _condition_explanation(item["conditionExplanation"]) if condition else None; condition_matches = condition_explanation["value"] if condition_explanation is not None else True
        if condition: result["condition"] = rule["denialCondition"]; result["conditionExplanation"] = condition_explanation
        denied = denied_permission[2] and denied_principal[2] and not exception_permission[2] and not exception_principal[2] and condition_matches; _require(item["denyAccessState"] == ("DENY_ACCESS_STATE_DENIED" if denied else "DENY_ACCESS_STATE_NOT_DENIED")); normalized.append(result)
    denied = any(rule["denyAccessState"] == "DENY_ACCESS_STATE_DENIED" for rule in normalized); _require(document["denyAccessState"] == ("DENY_ACCESS_STATE_DENIED" if denied else "DENY_ACCESS_STATE_NOT_DENIED")); return {"denyAccessState": document["denyAccessState"], "policy": policy, "relevance": document["relevance"], "ruleExplanations": normalized}
def _deny(value: object, access: _AccessSpec) -> dict[str, object]:
    document = _members(value, ("denyAccessState", "explainedResources", "permissionDeniable", "relevance"))
    resources = document["explainedResources"]
    if document["denyAccessState"] not in {"DENY_ACCESS_STATE_DENIED", "DENY_ACCESS_STATE_NOT_DENIED"} or type(document["permissionDeniable"]) is not bool or document["relevance"] not in _RELEVANCE or type(resources) is not list:
        raise ValueError
    normalized = []
    denied = False
    for resource in resources:
        item = _members(resource, ("denyAccessState", "explainedPolicies", "fullResourceName", "relevance"))
        if item["denyAccessState"] not in {"DENY_ACCESS_STATE_DENIED", "DENY_ACCESS_STATE_NOT_DENIED"} or item["relevance"] not in _RELEVANCE or not _text(item["fullResourceName"]).startswith("//") or type(item["explainedPolicies"]) is not list:
            raise ValueError
        policies = sorted((_deny_policy(policy, access) for policy in item["explainedPolicies"]), key=_canonical)
        policy_denied = any(policy.get("denyAccessState") == "DENY_ACCESS_STATE_DENIED" for policy in policies if type(policy) is dict)
        if item["denyAccessState"] != ("DENY_ACCESS_STATE_DENIED" if policy_denied else "DENY_ACCESS_STATE_NOT_DENIED"):
            raise ValueError
        denied |= policy_denied
        normalized.append({**item, "explainedPolicies": policies})
    if document["denyAccessState"] != ("DENY_ACCESS_STATE_DENIED" if denied else "DENY_ACCESS_STATE_NOT_DENIED"):
        raise ValueError
    return {"denyAccessState": document["denyAccessState"], "explainedResources": sorted(normalized, key=_canonical), "permissionDeniable": document["permissionDeniable"], "relevance": document["relevance"]}
def _pab(value: object) -> dict[str, object]:
    document = _members(value, ("principalAccessBoundaryAccessState", "relevance"), ("explainedBindingsAndPolicies",))
    if document["principalAccessBoundaryAccessState"] != "PAB_ACCESS_STATE_NOT_ENFORCED" or document.get("explainedBindingsAndPolicies", []) != [] or document["relevance"] not in _RELEVANCE:
        raise ValueError
    return {"explainedBindingsAndPolicies": [], "principalAccessBoundaryAccessState": "PAB_ACCESS_STATE_NOT_ENFORCED", "relevance": document["relevance"]}
def _effective_tags(value: object) -> list[dict[str, object]]:
    if type(value) is not list:
        raise ValueError
    result = []
    names = ("inherited", "namespacedTagKey", "namespacedTagValue", "tagKey", "tagKeyParentName", "tagValue")
    for tag in value:
        item = _members(tag, names)
        if type(item["inherited"]) is not bool or any(type(item[name]) is not str or not item[name] for name in names[1:]) or fullmatch(r"tagKeys/[1-9][0-9]*", item["tagKey"]) is None or fullmatch(r"tagValues/[1-9][0-9]*", item["tagValue"]) is None or fullmatch(r"(?:organizations|projects)/[1-9][0-9]*", item["tagKeyParentName"]) is None or fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9._-]+", item["namespacedTagKey"]) is None or fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", item["namespacedTagValue"]) is None:
            raise ValueError
        result.append(item)
    return sorted(result, key=_canonical)
def _access_tuple(value: object, access: _AccessSpec) -> dict[str, object]:
    document = _members(value, ("conditionContext", "fullResourceName", "permission", "permissionFqdn", "principal"))
    context = _members(document["conditionContext"], ("resource",), ("effectiveTags",))
    kind = "CryptoKeyVersion" if "/cryptoKeyVersions/" in access.resource else "CryptoKey"
    expected_resource = {"name": access.resource, "service": "cloudkms.googleapis.com", "type": "cloudkms.googleapis.com/" + kind}
    if document["principal"] != access.principal or document["fullResourceName"] != "//cloudkms.googleapis.com/" + access.resource or document["permission"] != access.permission or type(document["permissionFqdn"]) is not str or fullmatch(r"cloudkms\.googleapis\.com/[A-Za-z][A-Za-z0-9.]+", document["permissionFqdn"]) is None or _members(context["resource"], ("name", "service", "type")) != expected_resource:
        raise ValueError
    return {**document, "conditionContext": {"effectiveTags": _effective_tags(context.get("effectiveTags", [])), "resource": expected_resource}}
def _access(session: _EvidenceSession, access: _AccessSpec, specs: tuple[_BindingSpec, ...]) -> dict[str, object]:
    kind = "CryptoKeyVersion" if "/cryptoKeyVersions/" in access.resource else "CryptoKey"
    resource = {"name": access.resource, "service": "cloudkms.googleapis.com", "type": "cloudkms.googleapis.com/" + kind}
    body = _canonical({"accessTuple": {"conditionContext": {"resource": resource}, "fullResourceName": "//cloudkms.googleapis.com/" + access.resource, "permission": access.permission, "principal": access.principal}})
    response = session.post(
        "https://policytroubleshooter.googleapis.com/v3beta/iam:troubleshoot",
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        allow_redirects=False,
        stream=True,
        timeout=_HTTP_TIMEOUT,
    )
    value = _http_document(response)
    _members(value, ("accessTuple", "allowPolicyExplanation", "denyPolicyExplanation", "overallAccessState", "pabPolicyExplanation"))
    if value["overallAccessState"] != access.required:
        raise ValueError
    allow = _allow(value["allowPolicyExplanation"], access, specs)
    deny = _deny(value["denyPolicyExplanation"], access)
    if access.required == "CAN_ACCESS" and deny["denyAccessState"] != "DENY_ACCESS_STATE_NOT_DENIED":
        raise ValueError
    if access.required == "CANNOT_ACCESS" and allow["allowAccessState"] != "ALLOW_ACCESS_STATE_NOT_GRANTED" and deny["denyAccessState"] != "DENY_ACCESS_STATE_DENIED":
        raise ValueError
    return {"accessTuple": _access_tuple(value["accessTuple"], access), "allowPolicyExplanation": allow, "denyPolicyExplanation": deny, "overallAccessState": access.required, "pabPolicyExplanation": _pab(value["pabPolicyExplanation"])}
def _snapshot(observer: _KmsObserverClient, session: _EvidenceSession, manifest: _Manifest, bindings: tuple[_BindingSpec, ...], accesses: tuple[_AccessSpec, ...]) -> dict[str, object]:
    crypto_key = _crypto_key(observer, manifest)
    version = _crypto_key_version(observer, manifest)
    public_key = _public_key(observer, manifest)
    roles = [_role(session, spec.role, spec.permissions, etag) for spec, etag in zip(bindings, manifest.etags, strict=True)]
    evaluations = [_access(session, access, bindings) for access in accesses]
    return {"accessEvaluations": evaluations, "cryptoKey": crypto_key, "cryptoKeyVersion": version, "publicKey": public_key, "roles": roles}
def _probe(signer: _KmsSignerClient, manifest: _Manifest) -> tuple[bytes, bytes]:
    request = kms_v1.AsymmetricSignRequest(name=manifest.resource, data=_PROBE, data_crc32c=_crc32c(_PROBE))
    response = signer.asymmetric_sign(request=request, retry=None, timeout=_KMS_TIMEOUT)
    if type(response) is not kms_v1.AsymmetricSignResponse:
        raise ValueError
    signature = response.signature
    checksum = response.signature_crc32c
    if response.name != manifest.resource or response.protection_level != kms_v1.ProtectionLevel.HSM or response.verified_data_crc32c is not True or response.verified_digest_crc32c is not False or type(signature) is not bytes or len(signature) != 64 or type(checksum) is not int or isinstance(checksum, bool) or not 0 <= checksum <= 0xFFFFFFFF or checksum != _crc32c(signature):
        raise ValueError
    Ed25519PublicKey.from_public_bytes(manifest.public_key).verify(signature, _PROBE)
    request_digest = sha256(_canonical({"data": _b64url_text(_PROBE), "dataCrc32c": _crc32c(_PROBE), "name": manifest.resource})).digest()
    return request_digest, sha256(signature).digest()
def _time(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or not 0 <= value <= _MAX_UNIX_US:
        raise ValueError
    return value
def _admit(manifest: _Manifest, observer: _KmsObserverClient, signer: _KmsSignerClient, session: _EvidenceSession, clock: _TrustedClock) -> SecurityAuditObserverRootAdmission:
    started = _time(clock())
    bindings = _binding_specs(manifest)
    accesses = _access_specs(manifest, bindings)
    before = _snapshot(observer, session, manifest, bindings, accesses)
    probe_request_digest, probe_signature_digest = _probe(signer, manifest)
    after = _snapshot(observer, session, manifest, bindings, accesses)
    finished = _time(clock())
    if finished < started or finished - started > _MAX_SPAN_US or finished > _MAX_UNIX_US - _LIFETIME_US or before != after:
        raise ValueError
    expires = finished + _LIFETIME_US
    manifest_digest = sha256(manifest.raw).digest()
    snapshot_digest = sha256(_canonical(before)).digest()
    evidence = _canonical({
        "expiresAtUnixMicroseconds": expires,
        "manifestSha256": manifest_digest.hex(),
        "observedAtUnixMicroseconds": finished,
        "probeRequestSha256": probe_request_digest.hex(),
        "probeSignatureSha256": probe_signature_digest.hex(),
        "snapshotSha256": snapshot_digest.hex(),
        "startedAtUnixMicroseconds": started,
    })
    return SecurityAuditObserverRootAdmission(
        kms_key_version_resource=manifest.resource,
        observer_public_key=manifest.public_key,
        signer_principal=manifest.signer,
        observer_principal=manifest.observer,
        attestation_bundle_sha256=manifest.attestation_digest,
        manifest_sha256=manifest_digest,
        snapshot_sha256=snapshot_digest,
        evidence_sha256=sha256(_EVIDENCE_DOMAIN + evidence).digest(),
        observed_at_unix_microseconds=finished,
        expires_at_unix_microseconds=expires,
    )
def admit_security_audit_observer_root(
    *,
    manifest_bytes: bytes,
    observer_client: _KmsObserverClient,
    signer_client: _KmsSignerClient,
    evidence_session: _EvidenceSession,
    trusted_clock: _TrustedClock,
) -> SecurityAuditObserverRootAdmission:
    """Return one bounded admission or one fresh empty refusal."""
    refused = False
    try:
        if (
            not callable(observer_client.get_crypto_key)
            or not callable(observer_client.get_crypto_key_version)
            or not callable(observer_client.get_public_key)
            or not callable(signer_client.asymmetric_sign)
            or not callable(evidence_session.get)
            or not callable(evidence_session.post)
            or not callable(trusted_clock)
        ):
            raise ValueError
        parsed = _manifest(manifest_bytes)
        result = _admit(parsed, observer_client, signer_client, evidence_session, trusted_clock)
    except Exception:
        refused = True
    if refused:
        raise SecurityAuditObserverRootAdmissionRefused()
    return result
__all__ = (
    "SecurityAuditObserverRootAdmission",
    "SecurityAuditObserverRootAdmissionRefused",
    "admit_security_audit_observer_root",
)
