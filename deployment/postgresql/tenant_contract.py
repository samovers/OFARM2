"""Exact package-local TenantCapability contract owned by issue #174.

This module performs no network I/O and contains no private signing material.
It reads one checked-in canonical manifest whose exact UTF-8 bytes are the
contract authority shared by PostgreSQL and the independently implemented
issue-#172 issuer.  The manifest freezes strict Cloud KMS public-key
extraction, RFC 7638 key identity, the protected JWS header, binary payload
framing, and refusal rules.

The production signer and Google Cloud KMS/IAM orchestration are not part of
this module.  Tests use a separate RFC-vector fixture signer that is never
imported by production code.
"""

from __future__ import annotations

import base64
import binascii
import copy
import functools
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path


TENANT_CAPABILITY_CONTRACT_DIGEST_POLICY = (
    "OFARM_POSTGRESQL_TENANT_CAPABILITY_CONTRACT_V1"
)
TENANT_CAPABILITY_VERSION = "OFARM_TENANT_CAPABILITY_V1"
TENANT_CAPABILITY_EQUALITY_POLICY = "OIDC_EXACT_UTF8_V1"
TENANT_CAPABILITY_ALGORITHM = "Ed25519"
TENANT_CAPABILITY_TYPE = "ofarm-tenant-capability+jws"
TENANT_CAPABILITY_PARTY_RECORD_KIND = "ofarm.party.v0.1"
TENANT_CAPABILITY_MAX_TOKEN_BYTES = 8192
TENANT_CAPABILITY_MAX_TTL_MICROSECONDS = 60_000_000
TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS = 5_000_000
TENANT_CHALLENGE_MAX_AGE_MICROSECONDS = 60_000_000
TENANT_CAPABILITY_KEY_ISSUANCE_MICROSECONDS = 7_776_000_000_000
TENANT_CAPABILITY_KEY_VERIFICATION_TAIL_MICROSECONDS = 65_000_000
TENANT_CAPABILITY_PUBLIC_KEY_BYTES = 32
TENANT_CAPABILITY_SIGNATURE_BYTES = 64
TENANT_CAPABILITY_KEY_ID_BYTES = 43
TENANT_CAPABILITY_RFC8410_PREFIX = bytes.fromhex("302a300506032b6570032100")
TENANT_CAPABILITY_PREFLIGHT_PROBE = bytes.fromhex(
    "004f4641524d322d54454e414e542d4341504142494c4954592d4b4d532d"
    "505245464c494748542d563100"
)
OIDC_ISSUER_EQUALITY_POLICY = TENANT_CAPABILITY_EQUALITY_POLICY
OIDC_ISSUER_GRAMMAR_POLICY = "OFARM_OIDC_ISSUER_ASCII_HTTPS_V1"
OIDC_ISSUER_MAX_BYTES = 2048
TENANT_CAPABILITY_CONTRACT_MANIFEST_PATH = Path(__file__).with_name(
    "tenant_capability_contract_v1.json"
)
GOOGLE_KMS_PUBLIC_KEY_FORMAT = "DER"
GOOGLE_KMS_KEY_PURPOSE = "ASYMMETRIC_SIGN"
GOOGLE_KMS_KEY_ALGORITHM = "EC_SIGN_ED25519"
GOOGLE_KMS_PROTECTION_LEVEL = "HSM"
GOOGLE_KMS_KEY_VERSION_RESOURCE_PATTERN = (
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/"
    r"locations/[a-z0-9]([a-z0-9-]*[a-z0-9])?/"
    r"keyRings/[A-Za-z0-9_-]{1,63}/"
    r"cryptoKeys/[A-Za-z0-9_-]{1,63}/"
    r"cryptoKeyVersions/[1-9][0-9]*$"
)

_PAYLOAD_DOMAIN = TENANT_CAPABILITY_VERSION.encode("ascii") + b"\x00"
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1
_HOST_LABEL = re.compile(r"[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
_PORT = re.compile(r"[1-9][0-9]{0,4}")
_PATH = re.compile(
    r"(?:/(?:[A-Za-z0-9._~!$&'()*+,;=:@-]|%[0-9A-Fa-f]{2})*)*"
)
_SUBJECT = re.compile(r"[!-~]{1,255}")
_ASCII_ID = re.compile(r"[A-Za-z0-9._:-]{1,255}")
_KEY_ID = re.compile(r"[A-Za-z0-9_-]{43}")
_AUDIENCE = re.compile(
    r"urn:ofarm:tenant-binder:v1:"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_GOOGLE_KMS_KEY_VERSION_RESOURCE = re.compile(
    GOOGLE_KMS_KEY_VERSION_RESOURCE_PATTERN
)
_B64URL = re.compile(rb"[A-Za-z0-9_-]+")


OIDC_ISSUER_VALID_VECTORS = (
    "https://issuer.example.test",
    "https://issuer.example.test/tenant",
    "https://issuer.example.test:443/tenant/v1",
    "https://localhost",
    "https://127.0.0.1:8443/oidc",
    "https://issuer.example.test/a%2Fb",
    "https://issuer.example.test/a%2fb",
    "https://issuer.example.test/a'b",
    "https://issuer.test:1",
    "https://issuer.test:65535",
    "https://" + "a" * 63 + ".test",
)
OIDC_ISSUER_INVALID_VECTORS = (
    "",
    "http://issuer.example.test",
    "https://",
    "https://issuer.example.test?query=1",
    "https://issuer.example.test#fragment",
    "https://user@issuer.example.test",
    "https://issuer.example.test:0",
    "https://issuer.example.test:01",
    "https://issuer.example.test:65536",
    "https://issuer.example.test:70000",
    "https://issuer.example.test:not-a-port",
    "https://[invalid",
    "https://[2001:db8::1]",
    "https://-issuer.example.test",
    "https://issuer-.example.test",
    "https://issuer..example.test",
    "https://issuer.example.test.",
    "https://issuer.example.test/white space",
    "https://issuer.example.test/path\\segment",
    "https://issuer.example.test/%",
    "https://issuer.example.test/%0",
    "https://issuer.example.test/%GG",
    "https://issuer.example.test/ž",
    "https://" + "a" * 64 + ".test",
)

OIDC_SUBJECT_VALID_VECTORS = (
    "!",
    "subject-tenant-01",
    "~",
    "x" * 255,
)
OIDC_SUBJECT_INVALID_VECTORS = (
    "",
    " ",
    "subject with space",
    "subject\x00value",
    "ž",
    "x" * 256,
)

BINDER_AUDIENCE_VALID_VECTORS = (
    "urn:ofarm:tenant-binder:v1:a58b7238-5019-49e2-9aaf-530287e5a6ee",
)
BINDER_AUDIENCE_INVALID_VECTORS = (
    "",
    "urn:ofarm:tenant-binder:v1:00000000-0000-0000-0000-000000000000",
    "urn:ofarm:tenant-binder:v1:A58B7238-5019-49E2-9AAF-530287E5A6EE",
    "urn:ofarm:tenant-binder:v2:a58b7238-5019-49e2-9aaf-530287e5a6ee",
    "a58b7238-5019-49e2-9aaf-530287e5a6ee",
)

GOOGLE_KMS_KEY_VERSION_RESOURCE_VALID_VECTORS = (
    (
        "projects/example/locations/europe-west1/keyRings/ofarm/"
        "cryptoKeys/tenant-capability/cryptoKeyVersions/1"
    ),
    (
        "projects/a1234z/locations/global/keyRings/r/cryptoKeys/k/"
        "cryptoKeyVersions/999"
    ),
    (
        "projects/a1111111111111111111111111111z/locations/a/"
        "keyRings/RING_1/cryptoKeys/KEY-1/cryptoKeyVersions/1"
    ),
)
GOOGLE_KMS_KEY_VERSION_RESOURCE_INVALID_VECTORS = (
    "",
    "projects/a123z/locations/global/keyRings/r/cryptoKeys/k/cryptoKeyVersions/1",
    "projects/Example/locations/global/keyRings/r/cryptoKeys/k/cryptoKeyVersions/1",
    "projects/example/locations//keyRings/r/cryptoKeys/k/cryptoKeyVersions/1",
    "projects/example/locations/-/keyRings/r/cryptoKeys/k/cryptoKeyVersions/1",
    "projects/example/locations/-global/keyRings/r/cryptoKeys/k/cryptoKeyVersions/1",
    "projects/example/locations/global-/keyRings/r/cryptoKeys/k/cryptoKeyVersions/1",
    "projects/example/locations/GLOBAL/keyRings/r/cryptoKeys/k/cryptoKeyVersions/1",
    "projects/example/locations/global/keyRings//cryptoKeys/k/cryptoKeyVersions/1",
    (
        "projects/example/locations/global/keyRings/" + "r" * 64
        + "/cryptoKeys/k/cryptoKeyVersions/1"
    ),
    "projects/example/locations/global/keyRings/r/cryptoKeys//cryptoKeyVersions/1",
    "projects/example/locations/global/keyRings/r/cryptoKeys/k/cryptoKeyVersions/0",
    "projects/example/locations/global/keyRings/r/cryptoKeys/k/cryptoKeyVersions/01",
    "projects/example/locations/global/keyRings/r/cryptoKeys/k/cryptoKeyVersions/x",
    "projects/example/locations/global/keyRings/r/cryptoKeys/k/cryptoKeyVersions/1/",
)

GOOGLE_KMS_ED25519_VECTOR = {
    "name": (
        "projects/example/locations/europe-west1/keyRings/ofarm/"
        "cryptoKeys/tenant-capability/cryptoKeyVersions/1"
    ),
    "derHex": (
        "302a300506032b6570032100"
        "d75a980182b10ab7d54bfed3c964073a"
        "0ee172f3daa62325af021a68f707511a"
    ),
    "transportBase64": (
        "MCowBQYDK2VwAyEA11qYAYKxCrfVS/7TyWQHOg7hcvPapiMlrwIaaPcHURo="
    ),
    "crc32c": 3_927_069_631,
    "rawKeyHex": (
        "d75a980182b10ab7d54bfed3c964073a"
        "0ee172f3daa62325af021a68f707511a"
    ),
    "rawKeySha256": (
        "21fe31dfa154a261626bf854046fd227"
        "1b7bed4b6abe45aa58877ef47f9721b9"
    ),
    "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
    "kid": "kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k",
}


class TenantCapabilityContractError(ValueError):
    """The capability, key, or checked-in manifest is not exact."""


@dataclass(frozen=True, slots=True)
class ContextRoutineSignature:
    """One exact PostgreSQL entry-point identity."""

    name: str
    argument_types: tuple[str, ...]

    @property
    def identity_arguments(self) -> str:
        return ",".join(self.argument_types)

    @property
    def identity(self) -> str:
        return f"ofarm.{self.name}({self.identity_arguments})"

    def manifest(self) -> dict[str, object]:
        return {
            "schema": "ofarm",
            "name": self.name,
            "argumentTypes": list(self.argument_types),
            "identity": self.identity,
        }


TENANT_CONTEXT_ROUTINE_SIGNATURES = (
    ContextRoutineSignature("create_tenant_challenge", ()),
    ContextRoutineSignature("bind_tenant_capability", ("text",)),
    ContextRoutineSignature("current_tenant_context", ()),
    ContextRoutineSignature("current_tenant_id", ()),
    ContextRoutineSignature("take_tenant_write_lock", ()),
)


_PAYLOAD_FIELDS = (
    ("contractDigest", "sha256"),
    ("challengeId", "uuid"),
    ("audience", "ascii"),
    ("keyId", "ascii"),
    ("equalityPolicy", "ascii"),
    ("issuer", "utf8"),
    ("subject", "ascii"),
    ("bindingVersionId", "uuid"),
    ("bindingVersionDigest", "sha256"),
    ("lifecycleHeadId", "uuid"),
    ("lifecycleHeadDigest", "sha256"),
    ("tenantId", "uuid"),
    ("tenantRegistrationDigest", "sha256"),
    ("partyRef", "ascii"),
    ("partyRecordKind", "ascii"),
    ("partyRecordId", "ascii"),
    ("partySchemaDigest", "sha256"),
    ("partyPayloadDigest", "sha256"),
    ("issuedAt", "int64"),
    ("notBefore", "int64"),
    ("expiresAt", "int64"),
    ("nonce", "uuid"),
)


@dataclass(frozen=True, slots=True)
class TenantCapability:
    """All signed V1 payload fields in their exact framing order."""

    contract_digest: bytes
    challenge_id: uuid.UUID
    audience: str
    key_id: str
    equality_policy: str
    issuer: str
    subject: str
    binding_version_id: uuid.UUID
    binding_version_digest: bytes
    lifecycle_head_id: uuid.UUID
    lifecycle_head_digest: bytes
    tenant_id: uuid.UUID
    tenant_registration_digest: bytes
    party_ref: str
    party_record_kind: str
    party_record_id: str
    party_schema_digest: bytes
    party_payload_digest: bytes
    issued_at_unix_microseconds: int
    not_before_unix_microseconds: int
    expires_at_unix_microseconds: int
    nonce: uuid.UUID


@dataclass(frozen=True, slots=True)
class DecodedTenantCapability:
    """Strictly decoded Compact JWS without a cryptographic trust claim."""

    capability: TenantCapability
    protected_header: bytes
    payload: bytes
    signing_input: bytes
    signature: bytes


@dataclass(frozen=True, slots=True)
class GoogleKmsEd25519PublicKey:
    """One exact, checksum-verified Cloud KMS public-key observation."""

    key_version_resource: str
    der: bytes
    public_key: bytes
    public_key_digest: bytes
    x: str
    kid: str


@dataclass(frozen=True, slots=True)
class TenantCapabilityContract:
    """Canonical non-secret manifest of the accepted database contract."""

    identity: str = "ofarm.tenant-capability-and-binder.v1"

    def manifest_without_digest(self) -> dict[str, object]:
        parsed, _ = _checked_in_manifest()
        if parsed.get("identity") != self.identity:
            raise TenantCapabilityContractError(
                "checked-in contract identity differs"
            )
        return copy.deepcopy(parsed)

    def canonical_manifest_without_digest_bytes(self) -> bytes:
        parsed, source = _checked_in_manifest()
        if parsed.get("identity") != self.identity:
            raise TenantCapabilityContractError(
                "checked-in contract identity differs"
            )
        return source

    @property
    def digest(self) -> str:
        source = self.canonical_manifest_without_digest_bytes()
        return "sha256:" + hashlib.sha256(source).hexdigest()

    @property
    def raw_digest(self) -> bytes:
        return bytes.fromhex(self.digest.removeprefix("sha256:"))

    def manifest(self) -> dict[str, object]:
        result = self.manifest_without_digest()
        result["tenantCapabilityContractDigest"] = self.digest
        return result

    def canonical_manifest_bytes(self) -> bytes:
        return _canonical_json(self.manifest())


TENANT_CAPABILITY_CONTRACT = TenantCapabilityContract()
TENANT_CONTEXT_CONTRACT = TENANT_CAPABILITY_CONTRACT
TENANT_CONTEXT_CONTRACT_DIGEST_POLICY = TENANT_CAPABILITY_CONTRACT_DIGEST_POLICY
TenantContextContract = TenantCapabilityContract
TenantContextContractError = TenantCapabilityContractError


def valid_oidc_issuer(value: object) -> bool:
    """Return whether *value* satisfies the closed V1 issuer byte grammar."""

    if type(value) is not str:
        return False
    try:
        encoded = value.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        return False
    if not 1 <= len(encoded) <= OIDC_ISSUER_MAX_BYTES:
        return False
    if not value.startswith("https://"):
        return False
    authority_and_path = value[8:]
    if "/" in authority_and_path:
        authority, suffix = authority_and_path.split("/", 1)
        path = "/" + suffix
    else:
        authority = authority_and_path
        path = ""
    if not authority or "@" in authority or authority.count(":") > 1:
        return False
    if _PATH.fullmatch(path) is None:
        return False
    if ":" in authority:
        host, port_text = authority.rsplit(":", 1)
        if _PORT.fullmatch(port_text) is None:
            return False
        if int(port_text) > 65535:
            return False
    else:
        host = authority
    if not 1 <= len(host) <= 253:
        return False
    return all(_HOST_LABEL.fullmatch(label) is not None for label in host.split("."))


def validate_oidc_issuer(value: object) -> str:
    if not valid_oidc_issuer(value):
        raise TenantCapabilityContractError(
            f"issuer must satisfy {OIDC_ISSUER_GRAMMAR_POLICY}"
        )
    assert isinstance(value, str)
    return value


def derive_binder_audience(instance_id: uuid.UUID) -> str:
    _validate_uuid(instance_id, "binder instance id")
    return f"urn:ofarm:tenant-binder:v1:{instance_id}"


def validate_binder_audience(value: object) -> str:
    if type(value) is not str or _AUDIENCE.fullmatch(value) is None:
        raise TenantCapabilityContractError("binder audience is not canonical")
    parsed = uuid.UUID(value.rsplit(":", 1)[1])
    if parsed.int == 0 or str(parsed) != value.rsplit(":", 1)[1]:
        raise TenantCapabilityContractError("binder audience is not canonical")
    return value


def valid_google_kms_key_version_resource(value: object) -> bool:
    """Match the database candidate table's exact resource-name grammar."""

    return (
        type(value) is str
        and _GOOGLE_KMS_KEY_VERSION_RESOURCE.fullmatch(value) is not None
    )


def validate_google_kms_key_version_resource(value: object) -> str:
    if not valid_google_kms_key_version_resource(value):
        raise TenantCapabilityContractError(
            "KMS key-version resource grammar differs"
        )
    assert isinstance(value, str)
    return value


def extract_rfc8410_ed25519_public_key(der: bytes) -> bytes:
    """Extract only the exact 44-byte RFC 8410 Ed25519 SPKI form."""

    if type(der) is not bytes or len(der) != 44:
        raise TenantCapabilityContractError("Ed25519 SPKI must be exactly 44 bytes")
    if not der.startswith(TENANT_CAPABILITY_RFC8410_PREFIX):
        raise TenantCapabilityContractError("Ed25519 SPKI prefix is not exact")
    return der[len(TENANT_CAPABILITY_RFC8410_PREFIX) :]


def _extract_google_kms_ed25519_public_key(
    *,
    expected_key_version_resource: str,
    response_name: object,
    response_algorithm: object,
    response_protection_level: object,
    response_public_key_format: object,
    der: object,
    crc32c_checksum: object,
) -> GoogleKmsEd25519PublicKey:
    """Map one complete normalized KMS response without retry field mixing."""

    checked_resource = validate_google_kms_key_version_resource(
        expected_key_version_resource
    )
    if response_name != checked_resource:
        raise TenantCapabilityContractError("KMS key-version name differs")
    if response_algorithm != GOOGLE_KMS_KEY_ALGORITHM:
        raise TenantCapabilityContractError("KMS algorithm differs")
    if response_protection_level != GOOGLE_KMS_PROTECTION_LEVEL:
        raise TenantCapabilityContractError("KMS protection level differs")
    if response_public_key_format != GOOGLE_KMS_PUBLIC_KEY_FORMAT:
        raise TenantCapabilityContractError("KMS public-key format differs")
    if type(der) is not bytes:
        raise TenantCapabilityContractError("KMS public-key data must be bytes")
    if (
        type(crc32c_checksum) is not int
        or not 0 <= crc32c_checksum <= 0xFFFFFFFF
    ):
        raise TenantCapabilityContractError("KMS public-key CRC32C is not uint32")
    if _crc32c(der) != crc32c_checksum:
        raise TenantCapabilityContractError("KMS public-key CRC32C differs")
    public_key = extract_rfc8410_ed25519_public_key(der)
    x = _base64url_encode(public_key).decode("ascii")
    return GoogleKmsEd25519PublicKey(
        key_version_resource=checked_resource,
        der=der,
        public_key=public_key,
        public_key_digest=raw_public_key_digest(public_key),
        x=x,
        kid=derive_ed25519_key_id(public_key),
    )


def extract_google_kms_rest_ed25519_public_key(
    response_json: object,
    *,
    expected_key_version_resource: str,
) -> GoogleKmsEd25519PublicKey:
    """Map one complete Cloud KMS v1 REST response and nothing else."""

    if type(response_json) is not bytes:
        raise TenantCapabilityContractError(
            "KMS REST public-key response must be exact JSON bytes"
        )
    try:
        response = json.loads(
            response_json.decode("utf-8", errors="strict"),
            object_pairs_hook=_json_object_without_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TenantCapabilityContractError(
            "KMS REST public-key response JSON is malformed"
        ) from exc
    if type(response) is not dict or set(response) != {
        "name",
        "algorithm",
        "protectionLevel",
        "publicKeyFormat",
        "publicKey",
    }:
        raise TenantCapabilityContractError("KMS public-key response shape differs")
    public_key = response["publicKey"]
    if type(public_key) is not dict or set(public_key) != {
        "data",
        "crc32cChecksum",
    }:
        raise TenantCapabilityContractError("KMS checksummed-data shape differs")
    transport_data = public_key["data"]
    if type(transport_data) is not str:
        raise TenantCapabilityContractError("KMS REST public-key data is not text")
    try:
        transport_bytes = transport_data.encode("ascii", errors="strict")
        der = base64.b64decode(transport_bytes, validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise TenantCapabilityContractError(
            "KMS REST public-key base64 is malformed"
        ) from exc
    if base64.b64encode(der) != transport_bytes:
        raise TenantCapabilityContractError(
            "KMS REST public-key base64 is not canonical"
        )
    checksum_text = public_key["crc32cChecksum"]
    if (
        type(checksum_text) is not str
        or re.fullmatch(r"0|[1-9][0-9]{0,9}", checksum_text) is None
    ):
        raise TenantCapabilityContractError(
            "KMS REST public-key CRC32C is not canonical decimal"
        )
    checksum = int(checksum_text)
    return _extract_google_kms_ed25519_public_key(
        expected_key_version_resource=expected_key_version_resource,
        response_name=response["name"],
        response_algorithm=response["algorithm"],
        response_protection_level=response["protectionLevel"],
        response_public_key_format=response["publicKeyFormat"],
        der=der,
        crc32c_checksum=checksum,
    )


def raw_public_key_digest(public_key: bytes) -> bytes:
    _validate_public_key(public_key)
    return hashlib.sha256(public_key).digest()


def derive_ed25519_key_id(public_key: bytes) -> str:
    _validate_public_key(public_key)
    x = _base64url_encode(public_key).decode("ascii")
    thumbprint_input = (
        '{"crv":"Ed25519","kty":"OKP","x":"' + x + '"}'
    ).encode("ascii")
    return _base64url_encode(hashlib.sha256(thumbprint_input).digest()).decode(
        "ascii"
    )


def protected_header_bytes(key_id: str) -> bytes:
    _validate_key_id(key_id)
    return (
        '{"alg":"Ed25519","kid":"'
        + key_id
        + '","typ":"ofarm-tenant-capability+jws"}'
    ).encode("ascii")


def validate_tenant_capability(
    capability: TenantCapability,
    *,
    now_unix_microseconds: int | None = None,
    challenge_created_at_unix_microseconds: int | None = None,
) -> None:
    """Reject every field or time outside the accepted V1 contract."""

    if type(capability) is not TenantCapability:
        raise TenantCapabilityContractError("capability must be exact V1 type")
    if capability.contract_digest != TENANT_CAPABILITY_CONTRACT.raw_digest:
        raise TenantCapabilityContractError("capability contract digest differs")
    _validate_uuid(capability.challenge_id, "challenge id")
    validate_binder_audience(capability.audience)
    _validate_key_id(capability.key_id)
    if capability.equality_policy != TENANT_CAPABILITY_EQUALITY_POLICY:
        raise TenantCapabilityContractError("equality policy differs")
    validate_oidc_issuer(capability.issuer)
    if type(capability.subject) is not str or _SUBJECT.fullmatch(capability.subject) is None:
        raise TenantCapabilityContractError("subject must be 1-255 visible ASCII bytes")
    _validate_uuid(capability.binding_version_id, "binding version id")
    _validate_digest(capability.binding_version_digest, "binding version digest")
    _validate_uuid(capability.lifecycle_head_id, "lifecycle head id")
    _validate_digest(capability.lifecycle_head_digest, "lifecycle head digest")
    _validate_uuid(capability.tenant_id, "tenant id")
    _validate_digest(
        capability.tenant_registration_digest, "tenant registration digest"
    )
    _validate_ascii_id(capability.party_ref, "party ref")
    if capability.party_record_kind != TENANT_CAPABILITY_PARTY_RECORD_KIND:
        raise TenantCapabilityContractError("Party record kind differs")
    _validate_ascii_id(capability.party_record_id, "Party record id")
    if capability.party_record_id != capability.party_ref:
        raise TenantCapabilityContractError("Party record id must equal Party ref")
    _validate_digest(capability.party_schema_digest, "Party schema digest")
    _validate_digest(capability.party_payload_digest, "Party payload digest")
    issued_at = _validate_int64(capability.issued_at_unix_microseconds, "issued-at")
    not_before = _validate_int64(
        capability.not_before_unix_microseconds, "not-before"
    )
    expires_at = _validate_int64(capability.expires_at_unix_microseconds, "expires-at")
    if not issued_at <= not_before < expires_at:
        raise TenantCapabilityContractError(
            "times must satisfy issued-at <= not-before < expires-at"
        )
    if expires_at - issued_at > TENANT_CAPABILITY_MAX_TTL_MICROSECONDS:
        raise TenantCapabilityContractError("capability lifetime exceeds 60 seconds")
    _validate_uuid_v4(capability.nonce, "nonce")

    if now_unix_microseconds is not None:
        now = _validate_int64(now_unix_microseconds, "database time")
        if now > _INT64_MAX - TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS:
            raise TenantCapabilityContractError("database time cannot add future skew")
        if issued_at > now + TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS:
            raise TenantCapabilityContractError("issued-at exceeds future skew")
        if not_before > now + TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS:
            raise TenantCapabilityContractError("not-before exceeds future skew")
        if now >= expires_at:
            raise TenantCapabilityContractError("capability is expired")

    if challenge_created_at_unix_microseconds is not None:
        created = _validate_int64(
            challenge_created_at_unix_microseconds, "challenge time"
        )
        if created < _INT64_MIN + TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS:
            raise TenantCapabilityContractError("challenge time cannot subtract skew")
        if created > _INT64_MAX - TENANT_CHALLENGE_MAX_AGE_MICROSECONDS:
            raise TenantCapabilityContractError("challenge time cannot add lifetime")
        if issued_at < created - TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS:
            raise TenantCapabilityContractError("issued-at predates challenge skew")
        if expires_at > created + TENANT_CHALLENGE_MAX_AGE_MICROSECONDS:
            raise TenantCapabilityContractError("expiry exceeds challenge lifetime")
        if now_unix_microseconds is not None and (
            now_unix_microseconds >= created + TENANT_CHALLENGE_MAX_AGE_MICROSECONDS
        ):
            raise TenantCapabilityContractError("challenge is expired")


def canonical_tenant_capability_payload(capability: TenantCapability) -> bytes:
    validate_tenant_capability(capability)
    values = (
        capability.contract_digest,
        capability.challenge_id.bytes,
        capability.audience.encode("ascii"),
        capability.key_id.encode("ascii"),
        capability.equality_policy.encode("ascii"),
        capability.issuer.encode("utf-8"),
        capability.subject.encode("ascii"),
        capability.binding_version_id.bytes,
        capability.binding_version_digest,
        capability.lifecycle_head_id.bytes,
        capability.lifecycle_head_digest,
        capability.tenant_id.bytes,
        capability.tenant_registration_digest,
        capability.party_ref.encode("ascii"),
        capability.party_record_kind.encode("ascii"),
        capability.party_record_id.encode("ascii"),
        capability.party_schema_digest,
        capability.party_payload_digest,
        capability.issued_at_unix_microseconds.to_bytes(8, "big", signed=True),
        capability.not_before_unix_microseconds.to_bytes(8, "big", signed=True),
        capability.expires_at_unix_microseconds.to_bytes(8, "big", signed=True),
        capability.nonce.bytes,
    )
    return _PAYLOAD_DOMAIN + b"".join(_lp32(value) for value in values)


def canonical_jws_signing_input(capability: TenantCapability) -> bytes:
    header_segment = _base64url_encode(protected_header_bytes(capability.key_id))
    payload_segment = _base64url_encode(canonical_tenant_capability_payload(capability))
    return header_segment + b"." + payload_segment


def serialize_tenant_capability_jws(
    capability: TenantCapability, signature: bytes
) -> str:
    _validate_signature(signature)
    token = canonical_jws_signing_input(capability) + b"." + _base64url_encode(signature)
    if len(token) > TENANT_CAPABILITY_MAX_TOKEN_BYTES:
        raise TenantCapabilityContractError("TenantCapability token is oversized")
    return token.decode("ascii")


def decode_tenant_capability_jws(token: object) -> DecodedTenantCapability:
    """Strictly decode the token; this function does not verify the signature."""

    if type(token) is not str:
        raise TenantCapabilityContractError("TenantCapability token must be text")
    try:
        token_bytes = token.encode("ascii", errors="strict")
    except UnicodeEncodeError as exc:
        raise TenantCapabilityContractError("TenantCapability token must be ASCII") from exc
    if not 1 <= len(token_bytes) <= TENANT_CAPABILITY_MAX_TOKEN_BYTES:
        raise TenantCapabilityContractError("TenantCapability token size differs")
    segments = token_bytes.split(b".")
    if len(segments) != 3 or any(not segment for segment in segments):
        raise TenantCapabilityContractError("TenantCapability must have three segments")
    header = _base64url_decode(segments[0], "protected header")
    payload = _base64url_decode(segments[1], "payload")
    signature = _base64url_decode(segments[2], "signature")
    _validate_signature(signature)
    key_id = _decode_protected_header(header)
    capability = _decode_payload(payload)
    if capability.key_id != key_id:
        raise TenantCapabilityContractError("header and payload key ids differ")
    signing_input = segments[0] + b"." + segments[1]
    return DecodedTenantCapability(
        capability=capability,
        protected_header=header,
        payload=payload,
        signing_input=signing_input,
        signature=signature,
    )


def _decode_protected_header(header: bytes) -> str:
    prefix = b'{"alg":"Ed25519","kid":"'
    suffix = b'","typ":"ofarm-tenant-capability+jws"}'
    if not header.startswith(prefix) or not header.endswith(suffix):
        raise TenantCapabilityContractError("protected header is not canonical")
    key_bytes = header[len(prefix) : -len(suffix)]
    try:
        key_id = key_bytes.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise TenantCapabilityContractError("protected key id is not ASCII") from exc
    _validate_key_id(key_id)
    if header != protected_header_bytes(key_id):
        raise TenantCapabilityContractError("protected header is not canonical")
    return key_id


def _decode_payload(payload: bytes) -> TenantCapability:
    if not payload.startswith(_PAYLOAD_DOMAIN):
        raise TenantCapabilityContractError("payload domain differs")
    framed = payload[len(_PAYLOAD_DOMAIN) :]
    fields: list[bytes] = []
    position = 0
    for _ in _PAYLOAD_FIELDS:
        if len(framed) - position < 4:
            raise TenantCapabilityContractError("payload lp32 length is truncated")
        length = int.from_bytes(framed[position : position + 4], "big")
        position += 4
        end = position + length
        if end > len(framed):
            raise TenantCapabilityContractError("payload lp32 value is truncated")
        fields.append(framed[position:end])
        position = end
    if position != len(framed):
        raise TenantCapabilityContractError("payload has trailing bytes")

    def ascii_field(index: int, label: str) -> str:
        try:
            return fields[index].decode("ascii", errors="strict")
        except UnicodeDecodeError as exc:
            raise TenantCapabilityContractError(f"{label} is not ASCII") from exc

    def utf8_field(index: int, label: str) -> str:
        try:
            return fields[index].decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise TenantCapabilityContractError(f"{label} is not UTF-8") from exc

    capability = TenantCapability(
        contract_digest=_exact_length(fields[0], 32, "contract digest"),
        challenge_id=_uuid_from_bytes(fields[1], "challenge id"),
        audience=ascii_field(2, "audience"),
        key_id=ascii_field(3, "key id"),
        equality_policy=ascii_field(4, "equality policy"),
        issuer=utf8_field(5, "issuer"),
        subject=ascii_field(6, "subject"),
        binding_version_id=_uuid_from_bytes(fields[7], "binding version id"),
        binding_version_digest=_exact_length(
            fields[8], 32, "binding version digest"
        ),
        lifecycle_head_id=_uuid_from_bytes(fields[9], "lifecycle head id"),
        lifecycle_head_digest=_exact_length(
            fields[10], 32, "lifecycle head digest"
        ),
        tenant_id=_uuid_from_bytes(fields[11], "tenant id"),
        tenant_registration_digest=_exact_length(
            fields[12], 32, "tenant registration digest"
        ),
        party_ref=ascii_field(13, "Party ref"),
        party_record_kind=ascii_field(14, "Party record kind"),
        party_record_id=ascii_field(15, "Party record id"),
        party_schema_digest=_exact_length(fields[16], 32, "Party schema digest"),
        party_payload_digest=_exact_length(fields[17], 32, "Party payload digest"),
        issued_at_unix_microseconds=_int64_from_bytes(fields[18], "issued-at"),
        not_before_unix_microseconds=_int64_from_bytes(fields[19], "not-before"),
        expires_at_unix_microseconds=_int64_from_bytes(fields[20], "expires-at"),
        nonce=_uuid_from_bytes(fields[21], "nonce"),
    )
    validate_tenant_capability(capability)
    return capability


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("ascii")


def _json_object_without_duplicates(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TenantCapabilityContractError(
                "KMS REST public-key response has duplicate fields"
            )
        result[key] = value
    return result


@functools.lru_cache(maxsize=1)
def _checked_in_manifest() -> tuple[dict[str, object], bytes]:
    try:
        source = TENANT_CAPABILITY_CONTRACT_MANIFEST_PATH.read_bytes()
        text = source.decode("utf-8", errors="strict")
        parsed = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TenantCapabilityContractError(
            "checked-in capability manifest cannot be read exactly"
        ) from exc
    if type(parsed) is not dict:
        raise TenantCapabilityContractError(
            "checked-in capability manifest must be one object"
        )
    if "tenantCapabilityContractDigest" in parsed:
        raise TenantCapabilityContractError(
            "checked-in capability manifest must exclude its self digest"
        )
    if _canonical_json(parsed) != source:
        raise TenantCapabilityContractError(
            "checked-in capability manifest is not canonical UTF-8"
        )
    return parsed, source


def _crc32c(value: bytes) -> int:
    """Return CRC-32C/Castagnoli with the standard reflected parameters."""

    checksum = 0xFFFFFFFF
    for octet in value:
        checksum ^= octet
        for _ in range(8):
            checksum = (checksum >> 1) ^ (
                0x82F63B78 if checksum & 1 else 0
            )
    return checksum ^ 0xFFFFFFFF


def _lp32(value: bytes) -> bytes:
    if len(value) >= 2**32:
        raise TenantCapabilityContractError("field exceeds the lp32 bound")
    return len(value).to_bytes(4, "big") + value


def _base64url_encode(value: bytes) -> bytes:
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def _base64url_decode(segment: bytes, label: str) -> bytes:
    if not segment or _B64URL.fullmatch(segment) is None:
        raise TenantCapabilityContractError(f"{label} is not unpadded base64url")
    padding = b"=" * ((4 - len(segment) % 4) % 4)
    try:
        decoded = base64.b64decode(
            segment + padding, altchars=b"-_", validate=True
        )
    except binascii.Error as exc:
        raise TenantCapabilityContractError(f"{label} base64url is malformed") from exc
    if _base64url_encode(decoded) != segment:
        raise TenantCapabilityContractError(f"{label} base64url is not canonical")
    return decoded


def _validate_uuid(value: object, label: str) -> uuid.UUID:
    if type(value) is not uuid.UUID or value.int == 0:
        raise TenantCapabilityContractError(f"{label} must be a non-nil UUID")
    return value


def _validate_uuid_v4(value: object, label: str) -> uuid.UUID:
    parsed = _validate_uuid(value, label)
    if parsed.version != 4 or parsed.variant != uuid.RFC_4122:
        raise TenantCapabilityContractError(
            f"{label} must be an RFC 4122 UUIDv4"
        )
    return parsed


def _validate_digest(value: object, label: str) -> bytes:
    if type(value) is not bytes or len(value) != 32:
        raise TenantCapabilityContractError(f"{label} must be 32 raw bytes")
    return value


def _validate_public_key(value: object) -> bytes:
    if type(value) is not bytes or len(value) != TENANT_CAPABILITY_PUBLIC_KEY_BYTES:
        raise TenantCapabilityContractError("Ed25519 public key must be 32 bytes")
    return value


def _validate_signature(value: object) -> bytes:
    if type(value) is not bytes or len(value) != TENANT_CAPABILITY_SIGNATURE_BYTES:
        raise TenantCapabilityContractError("Ed25519 signature must be 64 bytes")
    return value


def _validate_key_id(value: object) -> str:
    if type(value) is not str or _KEY_ID.fullmatch(value) is None:
        raise TenantCapabilityContractError("key id must be 43 base64url bytes")
    return value


def _validate_ascii_id(value: object, label: str) -> str:
    if type(value) is not str or _ASCII_ID.fullmatch(value) is None:
        raise TenantCapabilityContractError(f"{label} must be a bounded ASCII id")
    return value


def _validate_int64(value: object, label: str) -> int:
    if type(value) is not int or not _INT64_MIN <= value <= _INT64_MAX:
        raise TenantCapabilityContractError(f"{label} must be signed int64")
    return value


def _exact_length(value: bytes, length: int, label: str) -> bytes:
    if len(value) != length:
        raise TenantCapabilityContractError(f"{label} has the wrong length")
    return value


def _uuid_from_bytes(value: bytes, label: str) -> uuid.UUID:
    _exact_length(value, 16, label)
    parsed = uuid.UUID(bytes=value)
    return _validate_uuid(parsed, label)


def _int64_from_bytes(value: bytes, label: str) -> int:
    _exact_length(value, 8, label)
    return int.from_bytes(value, "big", signed=True)


def _validate_checked_in_contract() -> None:
    manifest = TENANT_CAPABILITY_CONTRACT.manifest_without_digest()
    vectors = manifest.get("sharedVectors")
    if type(vectors) is not dict:
        raise TenantCapabilityContractError(
            "checked-in contract vectors are missing"
        )
    kms_response = {
        "name": GOOGLE_KMS_ED25519_VECTOR["name"],
        "algorithm": GOOGLE_KMS_KEY_ALGORITHM,
        "protectionLevel": GOOGLE_KMS_PROTECTION_LEVEL,
        "publicKeyFormat": GOOGLE_KMS_PUBLIC_KEY_FORMAT,
        "publicKey": {
            "data": GOOGLE_KMS_ED25519_VECTOR["transportBase64"],
            "crc32cChecksum": str(GOOGLE_KMS_ED25519_VECTOR["crc32c"]),
        },
    }
    observed = extract_google_kms_rest_ed25519_public_key(
        json.dumps(kms_response, separators=(",", ":")).encode("ascii"),
        expected_key_version_resource=str(GOOGLE_KMS_ED25519_VECTOR["name"]),
    )
    if (
        len(TENANT_CAPABILITY_RFC8410_PREFIX) != 12
        or len(TENANT_CAPABILITY_PREFLIGHT_PROBE) != 43
        or manifest.get("schemaVersion")
        != "ofarm.postgresql-tenant-capability-contract.v1"
        or manifest.get("digestPolicy")
        != (
            "SHA-256 over these exact checked-in UTF-8 bytes; this artifact "
            "contains no self-digest field and no domain prefix is prepended"
        )
        or manifest.get("kmsPublicKeyResponse", {}).get(
            "keyVersionResourceGrammar"
        ) != GOOGLE_KMS_KEY_VERSION_RESOURCE_PATTERN
        or vectors.get("issuer", {}).get("accept")
        != list(OIDC_ISSUER_VALID_VECTORS)
        or vectors.get("issuer", {}).get("refuse")
        != list(OIDC_ISSUER_INVALID_VECTORS)
        or vectors.get("subject", {}).get("accept")
        != list(OIDC_SUBJECT_VALID_VECTORS)
        or vectors.get("subject", {}).get("refuse")
        != list(OIDC_SUBJECT_INVALID_VECTORS)
        or vectors.get("audience", {}).get("accept")
        != list(BINDER_AUDIENCE_VALID_VECTORS)
        or vectors.get("audience", {}).get("refuse")
        != list(BINDER_AUDIENCE_INVALID_VECTORS)
        or vectors.get("kmsKeyVersionResource", {}).get("accept")
        != list(GOOGLE_KMS_KEY_VERSION_RESOURCE_VALID_VECTORS)
        or vectors.get("kmsKeyVersionResource", {}).get("refuse")
        != list(GOOGLE_KMS_KEY_VERSION_RESOURCE_INVALID_VECTORS)
        or observed.der.hex() != GOOGLE_KMS_ED25519_VECTOR["derHex"]
        or observed.public_key.hex() != GOOGLE_KMS_ED25519_VECTOR["rawKeyHex"]
        or observed.public_key_digest.hex()
        != GOOGLE_KMS_ED25519_VECTOR["rawKeySha256"]
        or observed.x != GOOGLE_KMS_ED25519_VECTOR["x"]
        or observed.kid != GOOGLE_KMS_ED25519_VECTOR["kid"]
    ):
        raise TenantCapabilityContractError("checked-in contract is inconsistent")


_validate_checked_in_contract()


__all__ = [
    "BINDER_AUDIENCE_INVALID_VECTORS",
    "BINDER_AUDIENCE_VALID_VECTORS",
    "DecodedTenantCapability",
    "GOOGLE_KMS_ED25519_VECTOR",
    "GOOGLE_KMS_KEY_ALGORITHM",
    "GOOGLE_KMS_KEY_PURPOSE",
    "GOOGLE_KMS_PROTECTION_LEVEL",
    "GOOGLE_KMS_PUBLIC_KEY_FORMAT",
    "GOOGLE_KMS_KEY_VERSION_RESOURCE_INVALID_VECTORS",
    "GOOGLE_KMS_KEY_VERSION_RESOURCE_PATTERN",
    "GOOGLE_KMS_KEY_VERSION_RESOURCE_VALID_VECTORS",
    "GoogleKmsEd25519PublicKey",
    "OIDC_ISSUER_EQUALITY_POLICY",
    "OIDC_ISSUER_GRAMMAR_POLICY",
    "OIDC_ISSUER_INVALID_VECTORS",
    "OIDC_ISSUER_MAX_BYTES",
    "OIDC_ISSUER_VALID_VECTORS",
    "OIDC_SUBJECT_INVALID_VECTORS",
    "OIDC_SUBJECT_VALID_VECTORS",
    "TENANT_CAPABILITY_ALGORITHM",
    "TENANT_CAPABILITY_CONTRACT",
    "TENANT_CAPABILITY_CONTRACT_DIGEST_POLICY",
    "TENANT_CAPABILITY_CONTRACT_MANIFEST_PATH",
    "TENANT_CAPABILITY_EQUALITY_POLICY",
    "TENANT_CAPABILITY_KEY_ID_BYTES",
    "TENANT_CAPABILITY_MAX_FUTURE_SKEW_MICROSECONDS",
    "TENANT_CAPABILITY_MAX_TOKEN_BYTES",
    "TENANT_CAPABILITY_MAX_TTL_MICROSECONDS",
    "TENANT_CAPABILITY_PARTY_RECORD_KIND",
    "TENANT_CAPABILITY_PREFLIGHT_PROBE",
    "TENANT_CAPABILITY_PUBLIC_KEY_BYTES",
    "TENANT_CAPABILITY_RFC8410_PREFIX",
    "TENANT_CAPABILITY_SIGNATURE_BYTES",
    "TENANT_CAPABILITY_TYPE",
    "TENANT_CAPABILITY_VERSION",
    "TENANT_CONTEXT_CONTRACT",
    "TENANT_CONTEXT_CONTRACT_DIGEST_POLICY",
    "TENANT_CONTEXT_ROUTINE_SIGNATURES",
    "ContextRoutineSignature",
    "TenantCapability",
    "TenantCapabilityContract",
    "TenantCapabilityContractError",
    "TenantContextContract",
    "TenantContextContractError",
    "canonical_jws_signing_input",
    "canonical_tenant_capability_payload",
    "decode_tenant_capability_jws",
    "derive_binder_audience",
    "derive_ed25519_key_id",
    "extract_rfc8410_ed25519_public_key",
    "extract_google_kms_rest_ed25519_public_key",
    "protected_header_bytes",
    "raw_public_key_digest",
    "serialize_tenant_capability_jws",
    "valid_oidc_issuer",
    "valid_google_kms_key_version_resource",
    "validate_binder_audience",
    "validate_google_kms_key_version_resource",
    "validate_oidc_issuer",
    "validate_tenant_capability",
]
