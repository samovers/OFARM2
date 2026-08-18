"""Focused evidence for security-audit observer-root admission."""

from __future__ import annotations

import base64
import ast
import copy
import hashlib
import json
from pathlib import Path
from dataclasses import FrozenInstanceError, fields

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from google.cloud import kms_v1

from conformance import rewrite_architecture_check
from deployment.postgresql import security_audit_observer_root_admission
from deployment.postgresql.security_audit_observer_root_admission import (
    SecurityAuditObserverRootAdmission,
    SecurityAuditObserverRootAdmissionRefused,
    admit_security_audit_observer_root,
)


SCHEMA = "ofarm.security-audit-observer-root-admission-manifest.v1"
ATTESTATION_DOMAIN = b"OFARM2_SECURITY_AUDIT_OBSERVER_ROOT_ATTESTATION_V1\x00"
EVIDENCE_DOMAIN = b"OFARM2_SECURITY_AUDIT_OBSERVER_ROOT_EVIDENCE_V1\x00"
PROBE = b"\x00OFARM2-SECURITY-AUDIT-OBSERVER-ROOT-ADMISSION-V1\x00"
RESOURCE = (
    "projects/example/locations/europe-west1/keyRings/ofarm/cryptoKeys/"
    "security-audit-observer/cryptoKeyVersions/1"
)
KEY = RESOURCE.rsplit("/cryptoKeyVersions/", 1)[0]
SIGNER = "audit-signer@example.iam.gserviceaccount.com"
OBSERVER = "audit-observer@example.iam.gserviceaccount.com"
STARTED = 1_000_000
FINISHED = 2_000_000
ROLE_ETAGS = ("c2lnbmVy", "dmVyc2lvbg==", "a2V5")
POLICY_ETAG = "cG9saWN5"
ATTESTATION_CONTENT = b"reviewed-hsm-attestation"
CERTIFICATES = {
    "caviumCerts": ["-----BEGIN CERTIFICATE-----\nCAVIUM\n-----END CERTIFICATE-----\n"],
    "googleCardCerts": ["-----BEGIN CERTIFICATE-----\nCARD\n-----END CERTIFICATE-----\n"],
    "googlePartitionCerts": ["-----BEGIN CERTIFICATE-----\nPARTITION\n-----END CERTIFICATE-----\n"],
}
PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
PUBLIC_KEY = PRIVATE_KEY.public_key().public_bytes(
    serialization.Encoding.Raw,
    serialization.PublicFormat.Raw,
)
DER = bytes.fromhex("302a300506032b6570032100") + PUBLIC_KEY


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _crc32c(value: bytes) -> int:
    checksum = 0xFFFFFFFF
    for octet in value:
        checksum ^= octet
        for _ in range(8):
            checksum = (checksum >> 1) ^ (
                0x82F63B78 if checksum & 1 else 0
            )
    return checksum ^ 0xFFFFFFFF


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _attestation_bundle() -> dict[str, object]:
    return {
        **CERTIFICATES,
        "content": base64.b64encode(ATTESTATION_CONTENT).decode("ascii"),
        "format": "CAVIUM_V1_COMPRESSED",
    }


def _manifest_document() -> dict[str, object]:
    digest = hashlib.sha256(
        ATTESTATION_DOMAIN + _canonical(_attestation_bundle())
    ).hexdigest()
    return {
        "attestationBundleSha256": digest,
        "attestationFormat": "CAVIUM_V1_COMPRESSED",
        "kmsKeyVersionResource": RESOURCE,
        "observerKeyRoleEtag": ROLE_ETAGS[2],
        "observerPrincipal": OBSERVER,
        "observerPublicKey": _b64url(PUBLIC_KEY),
        "observerVersionRoleEtag": ROLE_ETAGS[1],
        "schemaVersion": SCHEMA,
        "signerPrincipal": SIGNER,
        "signerRoleEtag": ROLE_ETAGS[0],
    }


def _manifest(document: dict[str, object] | None = None) -> bytes:
    return _canonical(document or _manifest_document())


def _role_specs() -> tuple[dict[str, object], ...]:
    prefix = "projects/example/roles/ofarmSecurityAuditObserverRoot"
    version_expression = (
        'resource.type == "cloudkms.googleapis.com/CryptoKeyVersion" && '
        f'resource.name == "{RESOURCE}"'
    )
    key_expression = (
        'resource.type == "cloudkms.googleapis.com/CryptoKey" && '
        f'resource.name == "{KEY}"'
    )
    return (
        {
            "role": prefix + "SignerV1",
            "member": "serviceAccount:" + SIGNER,
            "permissions": ["cloudkms.cryptoKeyVersions.useToSign"],
            "title": "ofarm-security-audit-observer-root-signer-v1",
            "expression": version_expression,
            "etag": ROLE_ETAGS[0],
        },
        {
            "role": prefix + "VersionReaderV1",
            "member": "serviceAccount:" + OBSERVER,
            "permissions": [
                "cloudkms.cryptoKeyVersions.get",
                "cloudkms.cryptoKeyVersions.viewPublicKey",
            ],
            "title": "ofarm-security-audit-observer-root-version-reader-v1",
            "expression": version_expression,
            "etag": ROLE_ETAGS[1],
        },
        {
            "role": prefix + "KeyReaderV1",
            "member": "serviceAccount:" + OBSERVER,
            "permissions": ["cloudkms.cryptoKeys.get"],
            "title": "ofarm-security-audit-observer-root-key-reader-v1",
            "expression": key_expression,
            "etag": ROLE_ETAGS[2],
        },
    )


def _resource_context(resource: str) -> dict[str, str]:
    kind = "CryptoKeyVersion" if "/cryptoKeyVersions/" in resource else "CryptoKey"
    return {
        "name": resource,
        "service": "cloudkms.googleapis.com",
        "type": "cloudkms.googleapis.com/" + kind,
    }


def _condition_value(spec: dict[str, object], resource: str) -> bool:
    expected = RESOURCE if "CryptoKeyVersion" in spec["expression"] else KEY
    return resource == expected


def _allow_binding(
    spec: dict[str, object],
    *,
    principal: str,
    resource: str,
    permission: str,
) -> tuple[dict[str, object], dict[str, object]]:
    matched = spec["member"] == "serviceAccount:" + principal
    included = permission in spec["permissions"]
    condition = _condition_value(spec, resource)
    granted = matched and included and condition
    binding = {
        "role": spec["role"],
        "members": [spec["member"]],
        "condition": {
            "title": spec["title"],
            "description": "fixed observer-root scope",
            "expression": spec["expression"],
        },
    }
    membership = "MEMBERSHIP_MATCHED" if matched else "MEMBERSHIP_NOT_MATCHED"
    explanation = {
        "allowAccessState": (
            "ALLOW_ACCESS_STATE_GRANTED"
            if granted
            else "ALLOW_ACCESS_STATE_NOT_GRANTED"
        ),
        "role": spec["role"],
        "rolePermission": (
            "ROLE_PERMISSION_INCLUDED"
            if included
            else "ROLE_PERMISSION_NOT_INCLUDED"
        ),
        "rolePermissionRelevance": "HEURISTIC_RELEVANCE_HIGH",
        "combinedMembership": {
            "membership": membership,
            "relevance": "HEURISTIC_RELEVANCE_HIGH",
        },
        "memberships": {
            spec["member"]: {
                "membership": membership,
                "relevance": "HEURISTIC_RELEVANCE_HIGH",
            }
        },
        "relevance": "HEURISTIC_RELEVANCE_HIGH",
        "condition": binding["condition"],
        "conditionExplanation": {
            "value": condition,
            "errors": [],
            "evaluationStates": [
                {"start": 0, "end": 7, "value": condition, "errors": []}
            ],
        },
    }
    return binding, explanation


def _troubleshoot_document(request: dict[str, object]) -> dict[str, object]:
    access = request["accessTuple"]
    principal = access["principal"]
    resource = access["conditionContext"]["resource"]["name"]
    permission = access["permission"]
    pairs = [
        _allow_binding(
            spec,
            principal=principal,
            resource=resource,
            permission=permission,
        )
        for spec in _role_specs()
    ]
    grants = [item for _, item in pairs if item["allowAccessState"].endswith("GRANTED") and not item["allowAccessState"].endswith("NOT_GRANTED")]
    allowed = bool(grants)
    allow_state = (
        "ALLOW_ACCESS_STATE_GRANTED"
        if allowed
        else "ALLOW_ACCESS_STATE_NOT_GRANTED"
    )
    return {
        "overallAccessState": "CAN_ACCESS" if allowed else "CANNOT_ACCESS",
        "accessTuple": {
            **access,
            "permissionFqdn": (
                "cloudkms.googleapis.com/" + permission.removeprefix("cloudkms.")
            ),
            "conditionContext": {
                "resource": access["conditionContext"]["resource"],
                "effectiveTags": [],
            },
        },
        "allowPolicyExplanation": {
            "allowAccessState": allow_state,
            "explainedPolicies": [
                {
                    "allowAccessState": allow_state,
                    "fullResourceName": "//cloudkms.googleapis.com/" + KEY,
                    "bindingExplanations": [item for _, item in pairs],
                    "relevance": "HEURISTIC_RELEVANCE_HIGH",
                    "policy": {
                        "version": 3,
                        "etag": POLICY_ETAG,
                        "auditConfigs": [],
                        "bindings": [item for item, _ in pairs],
                    },
                }
            ],
            "relevance": "HEURISTIC_RELEVANCE_HIGH",
        },
        "denyPolicyExplanation": {
            "denyAccessState": "DENY_ACCESS_STATE_NOT_DENIED",
            "explainedResources": [],
            "relevance": "HEURISTIC_RELEVANCE_NORMAL",
            "permissionDeniable": True,
        },
        "pabPolicyExplanation": {
            "principalAccessBoundaryAccessState": (
                "PAB_ACCESS_STATE_NOT_ENFORCED"
            ),
            "explainedBindingsAndPolicies": [],
            "relevance": "HEURISTIC_RELEVANCE_NORMAL",
        },
    }


class _Response:
    def __init__(
        self,
        document: object,
        *,
        status: int = 200,
        content_type: str = "application/json; charset=utf-8",
        body: bytes | None = None,
    ) -> None:
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.body = _canonical(document) if body is None else body
        self.closed = 0

    def iter_content(self, *, chunk_size: int):
        assert chunk_size == 65_536
        yield self.body[:7]
        yield self.body[7:]

    def close(self) -> None:
        self.closed += 1


class _EvidenceSession:
    def __init__(self, mutation=None, failure: BaseException | None = None) -> None:
        self.mutation = mutation
        self.failure = failure
        self.get_calls: list[tuple[str, dict[str, object]]] = []
        self.post_calls: list[tuple[str, dict[str, object]]] = []
        self.responses: list[_Response] = []

    def _response(self, kind: str, index: int, document: object) -> _Response:
        if self.failure is not None:
            raise self.failure
        value = copy.deepcopy(document)
        response = self.mutation(kind, index, value) if self.mutation else value
        if isinstance(response, _Response):
            result = response
        else:
            result = _Response(response)
        self.responses.append(result)
        return result

    def get(self, url: str, **kwargs: object) -> _Response:
        index = len(self.get_calls)
        self.get_calls.append((url, kwargs))
        name = url.removeprefix("https://iam.googleapis.com/v1/")
        spec = next(item for item in _role_specs() if item["role"] == name)
        document = {
            "name": name,
            "title": "OFARM observer-root role",
            "description": "closed permissions",
            "includedPermissions": spec["permissions"],
            "stage": "GA",
            "etag": spec["etag"],
            "deleted": False,
        }
        return self._response("get", index, document)

    def post(self, url: str, **kwargs: object) -> _Response:
        index = len(self.post_calls)
        self.post_calls.append((url, kwargs))
        request = json.loads(kwargs["data"])
        return self._response("post", index, _troubleshoot_document(request))


def _crypto_key() -> kms_v1.CryptoKey:
    return kms_v1.CryptoKey(
        name=KEY,
        purpose=kms_v1.CryptoKey.CryptoKeyPurpose.ASYMMETRIC_SIGN,
        import_only=False,
        version_template=kms_v1.CryptoKeyVersionTemplate(
            algorithm=(
                kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_ED25519
            ),
            protection_level=kms_v1.ProtectionLevel.HSM,
        ),
    )


def _crypto_key_version() -> kms_v1.CryptoKeyVersion:
    return kms_v1.CryptoKeyVersion(
        name=RESOURCE,
        state=kms_v1.CryptoKeyVersion.CryptoKeyVersionState.ENABLED,
        algorithm=(
            kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_ED25519
        ),
        protection_level=kms_v1.ProtectionLevel.HSM,
        reimport_eligible=False,
        attestation=kms_v1.KeyOperationAttestation(
            format=(
                kms_v1.KeyOperationAttestation.AttestationFormat.CAVIUM_V1_COMPRESSED
            ),
            content=ATTESTATION_CONTENT,
            cert_chains=kms_v1.KeyOperationAttestation.CertificateChains(
                cavium_certs=CERTIFICATES["caviumCerts"],
                google_card_certs=CERTIFICATES["googleCardCerts"],
                google_partition_certs=CERTIFICATES["googlePartitionCerts"],
            ),
        ),
    )


def _public_key() -> kms_v1.PublicKey:
    return kms_v1.PublicKey(
        name=RESOURCE,
        algorithm=(
            kms_v1.CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_ED25519
        ),
        protection_level=kms_v1.ProtectionLevel.HSM,
        public_key_format=kms_v1.PublicKey.PublicKeyFormat.DER,
        public_key={"data": DER, "crc32c_checksum": _crc32c(DER)},
    )


class _ObserverClient:
    def __init__(self, mutation=None, failure: BaseException | None = None) -> None:
        self.mutation = mutation
        self.failure = failure
        self.calls: list[tuple[str, object, object, object]] = []

    def _result(self, kind: str, value: object) -> object:
        if self.failure is not None:
            raise self.failure
        return self.mutation(kind, len(self.calls) - 1, value) if self.mutation else value

    def get_crypto_key(self, *, request, retry, timeout):
        self.calls.append(("get_crypto_key", request, retry, timeout))
        return self._result("key", _crypto_key())

    def get_crypto_key_version(self, *, request, retry, timeout):
        self.calls.append(("get_crypto_key_version", request, retry, timeout))
        return self._result("version", _crypto_key_version())

    def get_public_key(self, *, request, retry, timeout):
        self.calls.append(("get_public_key", request, retry, timeout))
        return self._result("public", _public_key())


class _SignerClient:
    def __init__(self, mutation=None, failure: BaseException | None = None) -> None:
        self.mutation = mutation
        self.failure = failure
        self.calls: list[tuple[object, object, object]] = []
        self.signature: bytes | None = None

    def asymmetric_sign(self, *, request, retry, timeout):
        self.calls.append((request, retry, timeout))
        if self.failure is not None:
            raise self.failure
        self.signature = PRIVATE_KEY.sign(request.data)
        response = kms_v1.AsymmetricSignResponse(
            name=RESOURCE,
            signature=self.signature,
            signature_crc32c=_crc32c(self.signature),
            verified_data_crc32c=True,
            verified_digest_crc32c=False,
            protection_level=kms_v1.ProtectionLevel.HSM,
        )
        return self.mutation(response) if self.mutation else response


class _Clock:
    def __init__(self, values: list[object] | None = None) -> None:
        self.values = list(values or [STARTED, FINISHED])
        self.calls = 0

    def __call__(self):
        self.calls += 1
        value = self.values.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


def _admit(
    *,
    manifest: object | None = None,
    observer: object | None = None,
    signer: object | None = None,
    session: object | None = None,
    clock: object | None = None,
):
    observer_value = observer or _ObserverClient()
    signer_value = signer or _SignerClient()
    session_value = session or _EvidenceSession()
    clock_value = clock or _Clock()
    result = admit_security_audit_observer_root(
        manifest_bytes=_manifest() if manifest is None else manifest,
        observer_client=observer_value,
        signer_client=signer_value,
        evidence_session=session_value,
        trusted_clock=clock_value,
    )
    return result, observer_value, signer_value, session_value, clock_value


def _assert_refused(**kwargs: object) -> SecurityAuditObserverRootAdmissionRefused:
    with pytest.raises(SecurityAuditObserverRootAdmissionRefused) as caught:
        _admit(**kwargs)
    error = caught.value
    assert error.args == ()
    assert str(error) == ""
    assert error.__cause__ is None
    assert error.__context__ is None
    return error


def _set(value: object, name: str, replacement: object) -> object:
    setattr(value, name, replacement)
    return value


def test_complete_admission_has_exact_result_digests_and_effect_order() -> None:
    result, observer, signer, session, clock = _admit()

    assert type(result) is SecurityAuditObserverRootAdmission
    assert tuple(field.name for field in fields(result)) == (
        "kms_key_version_resource",
        "observer_public_key",
        "signer_principal",
        "observer_principal",
        "attestation_bundle_sha256",
        "manifest_sha256",
        "snapshot_sha256",
        "evidence_sha256",
        "observed_at_unix_microseconds",
        "expires_at_unix_microseconds",
    )
    assert result.kms_key_version_resource == RESOURCE
    assert result.observer_public_key == PUBLIC_KEY
    assert result.signer_principal == SIGNER
    assert result.observer_principal == OBSERVER
    assert result.attestation_bundle_sha256 == hashlib.sha256(
        ATTESTATION_DOMAIN + _canonical(_attestation_bundle())
    ).digest()
    assert result.manifest_sha256 == hashlib.sha256(_manifest()).digest()
    assert len(result.snapshot_sha256) == 32
    assert result.observed_at_unix_microseconds == FINISHED
    assert result.expires_at_unix_microseconds == FINISHED + 30_000_000
    request, retry, timeout = signer.calls[0]
    assert type(request) is kms_v1.AsymmetricSignRequest
    assert request.name == RESOURCE
    assert request.data == PROBE
    assert request.data_crc32c == _crc32c(PROBE)
    assert retry is None and timeout == 5.0
    request_digest = hashlib.sha256(
        _canonical(
            {
                "data": _b64url(PROBE),
                "dataCrc32c": _crc32c(PROBE),
                "name": RESOURCE,
            }
        )
    ).hexdigest()
    evidence = _canonical(
        {
            "expiresAtUnixMicroseconds": FINISHED + 30_000_000,
            "manifestSha256": result.manifest_sha256.hex(),
            "observedAtUnixMicroseconds": FINISHED,
            "probeRequestSha256": request_digest,
            "probeSignatureSha256": hashlib.sha256(signer.signature).hexdigest(),
            "snapshotSha256": result.snapshot_sha256.hex(),
            "startedAtUnixMicroseconds": STARTED,
        }
    )
    assert result.evidence_sha256 == hashlib.sha256(
        EVIDENCE_DOMAIN + evidence
    ).digest()
    assert clock.calls == 2
    assert [call[0] for call in observer.calls] == [
        "get_crypto_key",
        "get_crypto_key_version",
        "get_public_key",
    ] * 2
    assert len(signer.calls) == 1
    assert len(session.get_calls) == 6
    assert len(session.post_calls) == 20
    assert all(response.closed == 1 for response in session.responses)
    assert all(call[1]["timeout"] == 5.0 for call in session.get_calls)
    assert all(call[1]["allow_redirects"] is False for call in session.post_calls)
    assert all(
        call[0]
        == "https://policytroubleshooter.googleapis.com/v3beta/iam:troubleshoot"
        for call in session.post_calls
    )
    with pytest.raises(FrozenInstanceError):
        result.observer_principal = SIGNER


def test_semantically_unordered_binding_roster_is_stable() -> None:
    def reorder(kind: str, index: int, value: object) -> object:
        if kind == "post" and index >= 10:
            policy = value["allowPolicyExplanation"]["explainedPolicies"][0]
            policy["policy"]["bindings"].reverse()
            policy["bindingExplanations"].reverse()
        return value

    first = _admit()[0]
    second = _admit(session=_EvidenceSession(reorder))[0]
    assert second.snapshot_sha256 == first.snapshot_sha256


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: {**value, "extra": True},
        lambda value: {**value, "schemaVersion": SCHEMA + ".other"},
        lambda value: {
            **value,
            "kmsKeyVersionResource": RESOURCE.rsplit("/", 1)[0] + "/01",
        },
        lambda value: {**value, "observerPrincipal": SIGNER},
        lambda value: {**value, "observerPrincipal": "user@example.com"},
        lambda value: {**value, "observerPublicKey": _b64url(PUBLIC_KEY[:-1])},
        lambda value: {**value, "observerPublicKey": _b64url(PUBLIC_KEY) + "="},
        lambda value: {**value, "signerRoleEtag": "not-base64"},
        lambda value: {**value, "attestationBundleSha256": "A" * 64},
        lambda value: {**value, "attestationFormat": "UNSPECIFIED"},
    ],
)
def test_manifest_mutations_refuse_before_clock_or_network(mutation) -> None:
    document = mutation(_manifest_document())
    observer = _ObserverClient()
    signer = _SignerClient()
    session = _EvidenceSession()
    clock = _Clock()
    _assert_refused(
        manifest=_manifest(document),
        observer=observer,
        signer=signer,
        session=session,
        clock=clock,
    )
    assert clock.calls == 0
    assert observer.calls == [] and signer.calls == []
    assert session.get_calls == [] and session.post_calls == []


@pytest.mark.parametrize(
    "manifest",
    [
        b" " + _manifest(),
        _manifest() + b"\n",
        b"\xef\xbb\xbf" + _manifest(),
        b'{"schemaVersion":"x","schemaVersion":"y"}',
        b"{}" * 4097,
        "å".encode(),
        b"",
    ],
)
def test_noncanonical_manifest_carriers_refuse_without_effect(manifest) -> None:
    clock = _Clock()
    _assert_refused(manifest=manifest, clock=clock)
    assert clock.calls == 0


@pytest.mark.parametrize(
    ("kind", "mutation"),
    [
        ("key", lambda value: _set(value, "name", KEY + "-other")),
        ("key", lambda value: _set(value, "import_only", True)),
        (
            "key",
            lambda value: _set(
                value,
                "purpose",
                kms_v1.CryptoKey.CryptoKeyPurpose.ENCRYPT_DECRYPT,
            ),
        ),
        (
            "key",
            lambda value: _set(
                value,
                "primary",
                kms_v1.CryptoKeyVersion(name=RESOURCE),
            ),
        ),
        (
            "key",
            lambda value: _set(
                value,
                "key_access_justifications_policy",
                kms_v1.KeyAccessJustificationsPolicy(),
            ),
        ),
        (
            "version",
            lambda value: _set(
                value,
                "state",
                kms_v1.CryptoKeyVersion.CryptoKeyVersionState.DISABLED,
            ),
        ),
        ("version", lambda value: _set(value, "reimport_eligible", True)),
        (
            "version",
            lambda value: _set(value.attestation, "content", b"changed") or value,
        ),
        (
            "version",
            lambda value: _set(value.attestation.cert_chains, "cavium_certs", [])
            or value,
        ),
        ("public", lambda value: _set(value.public_key, "data", DER + b"x") or value),
        (
            "public",
            lambda value: _set(value.public_key, "crc32c_checksum", 0) or value,
        ),
        ("public", lambda value: _set(value, "pem", "PEM") or value),
    ],
)
def test_kms_metadata_mutations_refuse_before_probe(kind, mutation) -> None:
    def change(response_kind: str, _index: int, value: object) -> object:
        return mutation(value) if response_kind == kind else value

    observer = _ObserverClient(change)
    signer = _SignerClient()
    clock = _Clock()
    _assert_refused(observer=observer, signer=signer, clock=clock)
    assert clock.calls == 1
    assert signer.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: {**value, "stage": "BETA"},
        lambda value: {**value, "deleted": True},
        lambda value: {**value, "etag": "Y2hhbmdlZA=="},
        lambda value: {
            **value,
            "includedPermissions": value["includedPermissions"] + [
                "cloudkms.cryptoKeys.setIamPolicy"
            ],
        },
        lambda value: {**value, "unexpected": "field"},
    ],
)
def test_role_definition_mutations_refuse_before_probe(mutation) -> None:
    session = _EvidenceSession(
        lambda kind, index, value: mutation(value)
        if kind == "get" and index == 0
        else value
    )
    signer = _SignerClient()
    _assert_refused(session=session, signer=signer)
    assert signer.calls == []
    assert len(session.get_calls) == 1


def _post_mutation(path: tuple[object, ...], replacement: object):
    def mutate(kind: str, index: int, value: object) -> object:
        if kind != "post" or index != 0:
            return value
        target = value
        for member in path[:-1]:
            target = target[member]
        if replacement is _DELETE:
            del target[path[-1]]
        else:
            target[path[-1]] = replacement
        return value

    return mutate


_DELETE = object()


@pytest.mark.parametrize(
    "mutation",
    [
        _post_mutation(("overallAccessState",), "UNKNOWN_INFO"),
        _post_mutation(
            ("pabPolicyExplanation", "principalAccessBoundaryAccessState"),
            "PAB_ACCESS_STATE_ALLOWED",
        ),
        _post_mutation(
            ("pabPolicyExplanation", "explainedBindingsAndPolicies"),
            [{}],
        ),
        _post_mutation(("pabPolicyExplanation",), _DELETE),
        _post_mutation(
            ("accessTuple", "conditionContext", "resource", "name"),
            KEY,
        ),
        _post_mutation(
            ("allowPolicyExplanation", "allowAccessState"),
            "ALLOW_ACCESS_STATE_UNKNOWN_INFO",
        ),
        _post_mutation(
            ("denyPolicyExplanation", "denyAccessState"),
            "DENY_ACCESS_STATE_UNKNOWN_CONDITIONAL",
        ),
        _post_mutation(
            (
                "allowPolicyExplanation",
                "explainedPolicies",
                0,
                "bindingExplanations",
                0,
                "conditionExplanation",
                "value",
            ),
            None,
        ),
        _post_mutation(
            (
                "allowPolicyExplanation",
                "explainedPolicies",
                0,
                "policy",
            ),
            {},
        ),
    ],
)
def test_incomplete_or_unknown_policy_evidence_refuses(mutation) -> None:
    signer = _SignerClient()
    session = _EvidenceSession(mutation)
    _assert_refused(session=session, signer=signer)
    assert signer.calls == []


def test_indirect_or_extra_signer_binding_refuses_even_when_result_says_can() -> None:
    def mutation(kind: str, index: int, value: object) -> object:
        if kind != "post" or index != 0:
            return value
        policy = value["allowPolicyExplanation"]["explainedPolicies"][0]
        extra_binding = copy.deepcopy(policy["policy"]["bindings"][0])
        extra_binding["role"] = "roles/cloudkms.signerVerifier"
        extra_binding["members"] = ["group:security@example.com"]
        extra = copy.deepcopy(policy["bindingExplanations"][0])
        extra["role"] = extra_binding["role"]
        extra["memberships"] = {
            "group:security@example.com": {
                "membership": "MEMBERSHIP_MATCHED",
                "relevance": "HEURISTIC_RELEVANCE_HIGH",
            }
        }
        extra["combinedMembership"]["membership"] = "MEMBERSHIP_MATCHED"
        policy["policy"]["bindings"].append(extra_binding)
        policy["bindingExplanations"].append(extra)
        return value

    _assert_refused(session=_EvidenceSession(mutation))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda response: object(),
        lambda response: _set(response, "name", RESOURCE + "0"),
        lambda response: _set(response, "verified_data_crc32c", False),
        lambda response: _set(response, "verified_digest_crc32c", True),
        lambda response: _set(response, "protection_level", kms_v1.ProtectionLevel.SOFTWARE),
        lambda response: _set(response, "signature", response.signature[:-1]),
        lambda response: _set(response, "signature_crc32c", 0),
    ],
)
def test_probe_response_mutations_stop_before_second_snapshot(mutation) -> None:
    signer = _SignerClient(mutation)
    observer = _ObserverClient()
    session = _EvidenceSession()
    clock = _Clock()
    _assert_refused(observer=observer, signer=signer, session=session, clock=clock)
    assert clock.calls == 1
    assert len(signer.calls) == 1
    assert len(observer.calls) == 3
    assert len(session.get_calls) == 3 and len(session.post_calls) == 10


def test_probe_signature_must_match_the_manifest_public_key() -> None:
    other = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))

    def mutation(response: kms_v1.AsymmetricSignResponse):
        signature = other.sign(PROBE)
        response.signature = signature
        response.signature_crc32c = _crc32c(signature)
        return response

    _assert_refused(signer=_SignerClient(mutation))


def test_valid_snapshot_drift_refuses_after_second_clock() -> None:
    def drift(kind: str, index: int, value: object) -> object:
        if kind == "get" and index == 3:
            value["description"] = "concurrently changed"
        return value

    session = _EvidenceSession(drift)
    signer = _SignerClient()
    clock = _Clock()
    _assert_refused(session=session, signer=signer, clock=clock)
    assert clock.calls == 2
    assert len(signer.calls) == 1
    assert len(session.get_calls) == 6 and len(session.post_calls) == 20


@pytest.mark.parametrize(
    "times",
    [
        [FINISHED, STARTED],
        [0, 180_000_001],
        [0, 9_223_372_036_854_775_807],
        [STARTED, True],
    ],
)
def test_invalid_finished_time_refuses_after_complete_observation(times) -> None:
    clock = _Clock(times)
    signer = _SignerClient()
    _assert_refused(clock=clock, signer=signer)
    assert clock.calls == 2
    assert len(signer.calls) == 1


@pytest.mark.parametrize("value", [-1, True, 1.0, "1", None])
def test_invalid_started_time_makes_no_network_call(value) -> None:
    clock = _Clock([value])
    observer = _ObserverClient()
    signer = _SignerClient()
    session = _EvidenceSession()
    _assert_refused(
        clock=clock,
        observer=observer,
        signer=signer,
        session=session,
    )
    assert clock.calls == 1
    assert observer.calls == [] and signer.calls == []
    assert session.get_calls == [] and session.post_calls == []


@pytest.mark.parametrize(
    ("dependency", "replacement"),
    [
        ("observer", object()),
        ("signer", object()),
        ("session", object()),
        ("clock", object()),
    ],
)
def test_missing_dependency_surface_refuses_before_clock(dependency, replacement) -> None:
    clock = _Clock()
    values = {dependency: replacement, "clock": clock}
    if dependency == "clock":
        values["clock"] = replacement
    _assert_refused(**values)
    if dependency != "clock":
        assert clock.calls == 0


@pytest.mark.parametrize(
    ("kwargs", "ledger"),
    [
        (
            {"observer": _ObserverClient(failure=RuntimeError("provider token"))},
            "observer",
        ),
        (
            {"session": _EvidenceSession(failure=RuntimeError("iam body"))},
            "session",
        ),
        (
            {"signer": _SignerClient(failure=RuntimeError("kms body"))},
            "signer",
        ),
        ({"clock": _Clock([RuntimeError("clock body")])}, "clock"),
    ],
)
def test_ordinary_dependency_errors_become_fresh_empty_refusals(kwargs, ledger) -> None:
    first = _assert_refused(**kwargs)
    if ledger == "clock":
        kwargs = {"clock": _Clock([RuntimeError("different")])}
    elif ledger == "observer":
        kwargs = {"observer": _ObserverClient(failure=ValueError("different"))}
    elif ledger == "session":
        kwargs = {"session": _EvidenceSession(failure=ValueError("different"))}
    else:
        kwargs = {"signer": _SignerClient(failure=ValueError("different"))}
    second = _assert_refused(**kwargs)
    assert second is not first


@pytest.mark.parametrize(
    "kwargs",
    [
        {"clock": _Clock([KeyboardInterrupt()])},
        {"observer": _ObserverClient(failure=KeyboardInterrupt())},
        {"session": _EvidenceSession(failure=KeyboardInterrupt())},
        {"signer": _SignerClient(failure=KeyboardInterrupt())},
    ],
)
def test_base_exception_canaries_propagate(kwargs) -> None:
    with pytest.raises(KeyboardInterrupt):
        _admit(**kwargs)


@pytest.mark.parametrize(
    "response",
    [
        _Response({}, status=302),
        _Response({}, content_type="text/plain"),
        _Response({}, body=b"{\"x\":1,\"x\":2}"),
        _Response({}, body=b"\xef\xbb\xbf{}"),
        _Response({}, body=b"[1]"),
        _Response({}, body=b"x" * 1_048_577),
    ],
)
def test_bounded_http_transport_refuses_malformed_responses(response) -> None:
    session = _EvidenceSession(
        lambda kind, index, value: response if kind == "get" and index == 0 else value
    )
    _assert_refused(session=session)
    assert response.closed == 1


def test_exact_request_shapes_and_matrix_order() -> None:
    _, observer, _, session, _ = _admit()
    for index, (name, request, retry, timeout) in enumerate(observer.calls):
        assert retry is None and timeout == 5.0
        assert request.name == (KEY if name == "get_crypto_key" else RESOURCE)
        if name == "get_public_key":
            assert request.public_key_format == kms_v1.PublicKey.PublicKeyFormat.DER
        assert index // 3 in {0, 1}
    expected = [
        (SIGNER, RESOURCE, "cloudkms.cryptoKeyVersions.useToSign"),
        (SIGNER, RESOURCE, "cloudkms.cryptoKeyVersions.get"),
        (SIGNER, RESOURCE, "cloudkms.cryptoKeyVersions.update"),
        (SIGNER, RESOURCE, "cloudkms.cryptoKeyVersions.destroy"),
        (SIGNER, KEY, "cloudkms.cryptoKeys.setIamPolicy"),
        (OBSERVER, RESOURCE, "cloudkms.cryptoKeyVersions.get"),
        (OBSERVER, RESOURCE, "cloudkms.cryptoKeyVersions.viewPublicKey"),
        (OBSERVER, KEY, "cloudkms.cryptoKeys.get"),
        (OBSERVER, RESOURCE, "cloudkms.cryptoKeyVersions.useToSign"),
        (OBSERVER, KEY, "cloudkms.cryptoKeys.setIamPolicy"),
    ]
    observed = []
    for _, kwargs in session.post_calls[:10]:
        body = json.loads(kwargs["data"])["accessTuple"]
        observed.append((body["principal"], body["conditionContext"]["resource"]["name"], body["permission"]))
        assert set(body) == {"conditionContext", "fullResourceName", "permission", "principal"}
        assert set(body["conditionContext"]) == {"resource"}
        assert kwargs == {
            "data": kwargs["data"],
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            "allow_redirects": False,
            "stream": True,
            "timeout": 5.0,
        }
    assert observed == expected


def _matching(value: str, *, permission: bool) -> dict[str, str]:
    return {
        "permissionMatchingState" if permission else "membership": value,
        "relevance": "HEURISTIC_RELEVANCE_HIGH",
    }


def _deny_policy_explanation() -> dict[str, object]:
    matched_permission = _matching("PERMISSION_PATTERN_MATCHED", permission=True)
    unmatched_permission = _matching(
        "PERMISSION_PATTERN_NOT_MATCHED", permission=True
    )
    matched_principal = _matching("MEMBERSHIP_MATCHED", permission=False)
    unmatched_principal = _matching("MEMBERSHIP_NOT_MATCHED", permission=False)
    return {
        "denyAccessState": "DENY_ACCESS_STATE_DENIED",
        "policy": {
            "name": "policies/security-audit-deny",
            "rules": [{"denyRule": {"deniedPermissions": ["cloudkms.*"]}}],
        },
        "ruleExplanations": [
            {
                "denyAccessState": "DENY_ACCESS_STATE_DENIED",
                "combinedDeniedPermission": matched_permission,
                "deniedPermissions": {"cloudkms.*": matched_permission},
                "combinedExceptionPermission": unmatched_permission,
                "exceptionPermissions": {},
                "combinedDeniedPrincipal": matched_principal,
                "deniedPrincipals": {SIGNER: matched_principal},
                "combinedExceptionPrincipal": unmatched_principal,
                "exceptionPrincipals": {},
                "relevance": "HEURISTIC_RELEVANCE_HIGH",
            }
        ],
        "relevance": "HEURISTIC_RELEVANCE_HIGH",
    }


def test_complete_deny_policy_text_is_validated_normalized_and_bound() -> None:
    def denied(kind: str, index: int, value: object) -> object:
        if kind == "post" and index % 10 == 1:
            explanation = value["denyPolicyExplanation"]
            explanation["denyAccessState"] = "DENY_ACCESS_STATE_DENIED"
            explanation["explainedResources"] = [
                {
                    "denyAccessState": "DENY_ACCESS_STATE_DENIED",
                    "fullResourceName": "//cloudkms.googleapis.com/" + RESOURCE,
                    "explainedPolicies": [_deny_policy_explanation()],
                    "relevance": "HEURISTIC_RELEVANCE_HIGH",
                }
            ]
        return value

    result = _admit(session=_EvidenceSession(denied))[0]
    assert type(result) is SecurityAuditObserverRootAdmission


def test_deny_policy_without_policy_text_refuses() -> None:
    def missing(kind: str, index: int, value: object) -> object:
        if kind == "post" and index == 1:
            explanation = value["denyPolicyExplanation"]
            explanation["denyAccessState"] = "DENY_ACCESS_STATE_DENIED"
            policy = _deny_policy_explanation()
            del policy["policy"]
            explanation["explainedResources"] = [
                {
                    "denyAccessState": "DENY_ACCESS_STATE_DENIED",
                    "fullResourceName": "//cloudkms.googleapis.com/" + RESOURCE,
                    "explainedPolicies": [policy],
                    "relevance": "HEURISTIC_RELEVANCE_HIGH",
                }
            ]
        return value

    _assert_refused(session=_EvidenceSession(missing))


def _effective_tag() -> dict[str, object]:
    return {
        "tagValue": "tagValues/456",
        "namespacedTagValue": "123/environment/production",
        "tagKey": "tagKeys/123",
        "namespacedTagKey": "123/environment",
        "tagKeyParentName": "organizations/123",
        "inherited": True,
    }


def test_effective_tags_are_validated_and_normalized() -> None:
    def tagged(kind: str, _index: int, value: object) -> object:
        if kind == "post":
            value["accessTuple"]["conditionContext"]["effectiveTags"] = [
                _effective_tag()
            ]
        return value

    assert type(_admit(session=_EvidenceSession(tagged))[0]) is (
        SecurityAuditObserverRootAdmission
    )

    def malformed(kind: str, index: int, value: object) -> object:
        if kind == "post" and index == 0:
            tag = _effective_tag()
            tag["tagKey"] = "projects/example/tags/123"
            value["accessTuple"]["conditionContext"]["effectiveTags"] = [tag]
        return value

    _assert_refused(session=_EvidenceSession(malformed))


def test_architecture_guard_rejects_alternate_effects_endpoints_and_probe() -> None:
    source = Path(security_audit_observer_root_admission.__file__).read_text()
    assert rewrite_architecture_check._security_audit_observer_root_surface_violations(
        ast.parse(source)
    ) == []
    mutations = (
        source.replace("v3beta/iam:troubleshoot", "v3/iam:troubleshoot"),
        source.replace("ADMISSION-V1", "ADMISSION-V2"),
        source + "\nopen('credential')\n",
        source.replace("retry=None", "retry=False", 1),
    )
    for mutation in mutations:
        assert rewrite_architecture_check._security_audit_observer_root_surface_violations(
            ast.parse(mutation)
        )


def test_repository_envelope_pins_budget_without_shared_test_cap() -> None:
    relative = "deployment/postgresql/security_audit_observer_root_admission.py"
    source = Path(security_audit_observer_root_admission.__file__).read_text()
    budget = rewrite_architecture_check.MODULE_BUDGETS[relative]
    assert len(source.splitlines()) == budget
    assert budget <= 700
    test_relative = "kernel/tests/test_security_audit_observer_root_admission.py"
    assert not any(
        Path(test_relative).match(pattern)
        for pattern in rewrite_architecture_check.TEST_GLOBS
    )
