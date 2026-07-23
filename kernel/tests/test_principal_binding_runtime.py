"""Application-owned #172 binding, control-plane, and capability tests."""
from __future__ import annotations

import base64
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from google.api_core.exceptions import FailedPrecondition

from deployment.postgresql.tenant_contract import (
    GOOGLE_KMS_KEY_ALGORITHM,
    GOOGLE_KMS_KEY_PURPOSE,
    GOOGLE_KMS_PROTECTION_LEVEL,
    TENANT_CAPABILITY_PREFLIGHT_PROBE,
    GoogleKmsEd25519PublicKey,
    TENANT_CAPABILITY_RFC8410_PREFIX,
    decode_tenant_capability_jws,
    derive_binder_audience,
    derive_ed25519_key_id,
    raw_public_key_digest,
)
from kernel.auth_oidc import (
    PreBindingOutcome,
    VerifiedOidcIdentity,
)
from kernel.principal_binding import (
    PostgreSQLPrincipalBindingResolver,
    PrincipalBindingAuthority,
)
from kernel.tenant_capability import (
    CapabilityIssuanceError,
    GoogleCloudKmsClientAdapter,
    GoogleKmsEd25519Signer,
    GoogleKmsSigningEvidenceObserver,
    ProductionSigningEvidence,
    ProductionTenantCapabilityIssuer,
    TenantChallenge,
)


ISSUER = "https://issuer.example.test/tenant"
SUBJECT = "subject-01"
PARTY = "party:operator-01"
DIGEST_A = "sha256:" + "11" * 32
DIGEST_B = "sha256:" + "22" * 32
DIGEST_C = "sha256:" + "33" * 32
DIGEST_D = "sha256:" + "44" * 32


def _identity():
    return VerifiedOidcIdentity(
        equality_policy="OIDC_EXACT_UTF8_V1",
        issuer=ISSUER,
        subject=SUBJECT,
        claims={},
    )


def _authority():
    now = datetime.now(UTC)
    return PrincipalBindingAuthority(
        equality_policy="OIDC_EXACT_UTF8_V1",
        issuer=ISSUER,
        subject=SUBJECT,
        binding_version_id=uuid4(),
        binding_version_digest=DIGEST_A,
        lifecycle_head_id=uuid4(),
        lifecycle_head_digest=DIGEST_B,
        tenant_id=uuid4(),
        tenant_registration_digest=DIGEST_C,
        party_ref=PARTY,
        party_record_kind="ofarm.party.v0.1",
        party_record_id=PARTY,
        party_schema_digest=DIGEST_D,
        party_payload_digest="sha256:" + "55" * 32,
        party_state="ACTIVE",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
    )


class _CapabilityResolver:
    def __init__(self, authority):
        self.authority = authority
        self.initialized = False

    def initialize(self):
        self.initialized = True

    def resolve(self, identity):
        assert identity == _identity()
        return self.authority


class _FixtureSigner:
    def __init__(self, private, audience):
        self.private = private
        self._audience = audience
        public = private.public_key().public_bytes_raw()
        self._public = public
        self._kid = derive_ed25519_key_id(public)

    @property
    def key_id(self):
        return self._kid

    @property
    def public_key(self):
        return self._public

    @property
    def audience(self):
        return self._audience

    def initialize(self):
        pass

    def sign(self, data):
        return self.private.sign(data)


def _test_adapter(client):
    return GoogleCloudKmsClientAdapter.for_test(client)


def _production_signer(
    private,
    audience,
    now_us,
    *,
    observed_at_us=None,
    valid_until_us=None,
    key_state="ENABLED",
    client_factory=None,
    evidence_observer=None,
    now_microseconds=None,
):
    public = private.public_key().public_bytes_raw()
    resource = (
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/capability/cryptoKeyVersions/1"
    )
    kid = derive_ed25519_key_id(public)
    observation = GoogleKmsEd25519PublicKey(
        key_version_resource=resource,
        der=TENANT_CAPABILITY_RFC8410_PREFIX + public,
        public_key=public,
        public_key_digest=raw_public_key_digest(public),
        x=base64.urlsafe_b64encode(public).rstrip(b"=").decode("ascii"),
        kid=kid,
    )
    evidence = ProductionSigningEvidence(
        audience=audience,
        key_version_resource=resource,
        key_id=kid,
        public_key_digest=raw_public_key_digest(public),
        key_purpose=GOOGLE_KMS_KEY_PURPOSE,
        key_algorithm=GOOGLE_KMS_KEY_ALGORITHM,
        protection_level=GOOGLE_KMS_PROTECTION_LEVEL,
        key_state=key_state,
        attestation_evidence_digest=DIGEST_A,
        iam_evidence_digest=DIGEST_B,
        database_candidate_digest=DIGEST_C,
        database_lifecycle_head_digest=DIGEST_D,
        observed_at_unix_microseconds=(
            now_us - 1 if observed_at_us is None else observed_at_us
        ),
        valid_until_unix_microseconds=(
            now_us + 60_000_000 if valid_until_us is None else valid_until_us
        ),
    )
    raw_client = (
        _KmsClient(private, resource)
        if client_factory is None
        else client_factory(private, resource)
    )
    return GoogleKmsEd25519Signer.for_test(
        client=_test_adapter(raw_client),
        public_key=observation,
        evidence=evidence,
        evidence_observer=evidence_observer,
        now_microseconds=(
            (lambda: now_us) if now_microseconds is None else now_microseconds
        ),
    )


def test_capability_pins_exact_binding_head_tenant_party_and_challenge():
    authority = _authority()
    audience = derive_binder_audience(uuid4())
    now_us = 1_900_000_000_000_000
    private = Ed25519PrivateKey.generate()
    signer = _production_signer(private, audience, now_us)
    issuer = ProductionTenantCapabilityIssuer.for_test(
        resolver=_CapabilityResolver(authority),
        signer=signer,
        now_microseconds=lambda: now_us,
    )
    issuer.initialize()
    challenge = TenantChallenge(uuid4(), audience)
    token = issuer.mint(_identity(), challenge)
    decoded = decode_tenant_capability_jws(token)
    capability = decoded.capability
    assert capability.challenge_id == challenge.challenge_id
    assert capability.binding_version_id == authority.binding_version_id
    assert capability.binding_version_digest.hex() == DIGEST_A.removeprefix("sha256:")
    assert capability.lifecycle_head_id == authority.lifecycle_head_id
    assert capability.tenant_registration_digest.hex() == DIGEST_C.removeprefix("sha256:")
    assert capability.party_ref == PARTY
    assert capability.party_schema_digest.hex() == DIGEST_D.removeprefix("sha256:")
    assert capability.issuer == ISSUER and capability.subject == SUBJECT
    assert capability.nonce.version == 4
    assert capability.expires_at_unix_microseconds - now_us == 30_000_000
    private.public_key().verify(decoded.signature, decoded.signing_input)


def _crc32c(value):
    checksum = 0xFFFFFFFF
    for octet in value:
        checksum ^= octet
        for _ in range(8):
            checksum = (checksum >> 1) ^ (0x82F63B78 if checksum & 1 else 0)
    return checksum ^ 0xFFFFFFFF


class _KmsClient:
    def __init__(self, private, resource):
        self.private = private
        self.resource = resource
        self.calls = []

    def asymmetric_sign(self, *, request):
        name = request["name"]
        data = request["data"]
        data_crc32c = request["data_crc32c"]
        assert name == self.resource
        assert data_crc32c == _crc32c(data)
        self.calls.append(data)
        signature = self.private.sign(data)
        return type(
            "Response",
            (),
            {
                "name": name,
                "protection_level": type("Protection", (), {"name": "HSM"})(),
                "verified_data_crc32c": True,
                "signature": signature,
                "signature_crc32c": _crc32c(signature),
            },
        )()


def _signed_evidence_receipt(observer_private, evidence):
    canonical = json.dumps(
        evidence,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    signature = observer_private.sign(
        b"OFARM_PRODUCTION_SIGNING_EVIDENCE_V1\x00" + canonical
    )
    return json.dumps(
        {
            "evidence": evidence,
            "signature": base64.urlsafe_b64encode(signature)
            .rstrip(b"=")
            .decode("ascii"),
        },
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _evidence_payload(
    signing_key,
    audience,
    observed_at,
    valid_until,
    *,
    key_state="ENABLED",
):
    return {
        "audience": audience,
        "keyVersionResource": signing_key.key_version_resource,
        "keyId": signing_key.kid,
        "publicKeyDigest": "sha256:" + signing_key.public_key_digest.hex(),
        "keyPurpose": GOOGLE_KMS_KEY_PURPOSE,
        "keyAlgorithm": GOOGLE_KMS_KEY_ALGORITHM,
        "protectionLevel": GOOGLE_KMS_PROTECTION_LEVEL,
        "keyState": key_state,
        "attestationEvidenceDigest": DIGEST_A,
        "iamEvidenceDigest": DIGEST_B,
        "databaseCandidateDigest": DIGEST_C,
        "databaseLifecycleHeadDigest": DIGEST_D,
        "observedAtUnixMicroseconds": observed_at,
        "validUntilUnixMicroseconds": valid_until,
    }


def _production_evidence(
    signing_key,
    audience,
    observed_at,
    valid_until,
    *,
    key_state="ENABLED",
):
    return ProductionSigningEvidence(
        audience=audience,
        key_version_resource=signing_key.key_version_resource,
        key_id=signing_key.kid,
        public_key_digest=signing_key.public_key_digest,
        key_purpose=GOOGLE_KMS_KEY_PURPOSE,
        key_algorithm=GOOGLE_KMS_KEY_ALGORITHM,
        protection_level=GOOGLE_KMS_PROTECTION_LEVEL,
        key_state=key_state,
        attestation_evidence_digest=DIGEST_A,
        iam_evidence_digest=DIGEST_B,
        database_candidate_digest=DIGEST_C,
        database_lifecycle_head_digest=DIGEST_D,
        observed_at_unix_microseconds=observed_at,
        valid_until_unix_microseconds=valid_until,
    )


def _signing_key(private, resource=None):
    if resource is None:
        resource = (
            "projects/ofarm1/locations/europe-west1/keyRings/auth/"
            "cryptoKeys/capability/cryptoKeyVersions/1"
        )
    public = private.public_key().public_bytes_raw()
    return GoogleKmsEd25519PublicKey(
        key_version_resource=resource,
        der=TENANT_CAPABILITY_RFC8410_PREFIX + public,
        public_key=public,
        public_key_digest=raw_public_key_digest(public),
        x=base64.urlsafe_b64encode(public).rstrip(b"=").decode("ascii"),
        kid=derive_ed25519_key_id(public),
    )


class _ObserverPublicKeyClient:
    def __init__(
        self,
        private,
        resource,
        *,
        entered=None,
        release=None,
        block_on_call=2,
    ):
        self.private = private
        self.resource = resource
        self.entered = entered
        self.release = release
        self.block_on_call = block_on_call
        self.calls = 0

    def asymmetric_sign(self, *, request):
        raise AssertionError(request)

    def get_public_key(self, *, request):
        assert request == {"name": self.resource}
        self.calls += 1
        if (
            self.entered is not None
            and self.calls == self.block_on_call
        ):
            self.entered.set()
            assert self.release is not None
            assert self.release.wait(timeout=5)
        pem = self.private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return type(
            "PublicKeyResponse",
            (),
            {
                "name": self.resource,
                "algorithm": type(
                    "Algorithm",
                    (),
                    {"name": GOOGLE_KMS_KEY_ALGORITHM},
                )(),
                "protection_level": type(
                    "Protection",
                    (),
                    {"name": GOOGLE_KMS_PROTECTION_LEVEL},
                )(),
                "pem": pem.decode("ascii"),
                "pem_crc32c": _crc32c(pem),
            },
        )()


def _refreshing_signer_fixture(
    now,
    *,
    initial_valid_until=None,
    observer_entered=None,
    observer_release=None,
    observer_block_on_call=2,
    kms_client_factory=None,
):
    signing_private = Ed25519PrivateKey.generate()
    signing_key = _signing_key(signing_private)
    audience = derive_binder_audience(uuid4())
    observer_private = Ed25519PrivateKey.generate()
    observer_resource = (
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/evidence-observer/cryptoKeyVersions/1"
    )
    valid_until = (
        now[0] + 60_000_000
        if initial_valid_until is None
        else initial_valid_until
    )
    payload = _evidence_payload(
        signing_key,
        audience,
        now[0] - 1,
        valid_until,
    )
    observer_client = _ObserverPublicKeyClient(
        observer_private,
        observer_resource,
        entered=observer_entered,
        release=observer_release,
        block_on_call=observer_block_on_call,
    )
    observer = GoogleKmsSigningEvidenceObserver.for_test(
        client=_test_adapter(observer_client),
        observer_key_resource=observer_resource,
        receipt_bytes=_signed_evidence_receipt(
            observer_private,
            payload,
        ),
    )
    selected_kms_client_factory = (
        _KmsClient
        if kms_client_factory is None
        else kms_client_factory
    )
    raw_kms = selected_kms_client_factory(
        signing_private,
        signing_key.key_version_resource,
    )
    signer = GoogleKmsEd25519Signer.for_test(
        client=_test_adapter(raw_kms),
        public_key=signing_key,
        evidence=_production_evidence(
            signing_key,
            audience,
            now[0] - 1,
            valid_until,
        ),
        evidence_observer=observer,
        now_microseconds=lambda: now[0],
    )
    return (
        signer,
        observer,
        observer_private,
        observer_client,
        raw_kms,
        signing_key,
        audience,
        valid_until,
    )


def test_kms_signer_checks_resource_crc_hsm_and_signature():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes_raw()
    resource = (
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/capability/cryptoKeyVersions/1"
    )
    kid = derive_ed25519_key_id(public)
    observation = GoogleKmsEd25519PublicKey(
        key_version_resource=resource,
        der=TENANT_CAPABILITY_RFC8410_PREFIX + public,
        public_key=public,
        public_key_digest=raw_public_key_digest(public),
        x=base64.urlsafe_b64encode(public).rstrip(b"=").decode("ascii"),
        kid=kid,
    )
    now_us = 1_900_000_000_000_000
    evidence = ProductionSigningEvidence(
        audience=derive_binder_audience(uuid4()),
        key_version_resource=resource,
        key_id=kid,
        public_key_digest=raw_public_key_digest(public),
        key_purpose=GOOGLE_KMS_KEY_PURPOSE,
        key_algorithm=GOOGLE_KMS_KEY_ALGORITHM,
        protection_level=GOOGLE_KMS_PROTECTION_LEVEL,
        key_state="ENABLED",
        attestation_evidence_digest=DIGEST_A,
        iam_evidence_digest=DIGEST_B,
        database_candidate_digest=DIGEST_C,
        database_lifecycle_head_digest=DIGEST_D,
        observed_at_unix_microseconds=now_us - 1,
        valid_until_unix_microseconds=now_us + 1_000_000,
    )
    raw_client = _KmsClient(private, resource)
    client = _test_adapter(raw_client)
    signer = GoogleKmsEd25519Signer.for_test(
        client=client,
        public_key=observation,
        evidence=evidence,
        now_microseconds=lambda: now_us,
    )
    signer.initialize()
    data = b"exact-jws-signing-input"
    signature = signer.sign(data)
    private.public_key().verify(signature, data)
    assert raw_client.calls == [TENANT_CAPABILITY_PREFLIGHT_PROBE, data]


def test_kms_signer_rechecks_evidence_after_slow_signing_response():
    now = [1_900_000_000_000_000]

    class ExpiringKmsClient(_KmsClient):
        def asymmetric_sign(self, *, request):
            response = super().asymmetric_sign(request=request)
            if request["data"] != TENANT_CAPABILITY_PREFLIGHT_PROBE:
                now[0] += 10
            return response

    signer = _production_signer(
        Ed25519PrivateKey.generate(),
        derive_binder_audience(uuid4()),
        now[0],
        valid_until_us=now[0] + 5,
        client_factory=ExpiringKmsClient,
        now_microseconds=lambda: now[0],
    )
    signer.initialize()

    with pytest.raises(CapabilityIssuanceError) as raised:
        signer.sign(b"exact-jws-signing-input")
    assert raised.value.outcome is PreBindingOutcome.SIGNER_UNAVAILABLE
    assert "expired during KMS call" in raised.value.internal_detail


def test_capability_expiry_is_rechecked_after_slow_signing_response():
    now = [1_900_000_000_000_000]

    class SlowKmsClient(_KmsClient):
        def asymmetric_sign(self, *, request):
            response = super().asymmetric_sign(request=request)
            now[0] += 10
            return response

    audience = derive_binder_audience(uuid4())
    signer = _production_signer(
        Ed25519PrivateKey.generate(),
        audience,
        now[0],
        client_factory=SlowKmsClient,
        now_microseconds=lambda: now[0],
    )
    issuer = ProductionTenantCapabilityIssuer.for_test(
        resolver=_CapabilityResolver(_authority()),
        signer=signer,
        lifetime_microseconds=5,
        now_microseconds=lambda: now[0],
    )
    issuer.initialize()

    with pytest.raises(CapabilityIssuanceError) as raised:
        issuer.mint(_identity(), TenantChallenge(uuid4(), audience))
    assert raised.value.outcome is PreBindingOutcome.CAPABILITY_REFUSED


def test_google_client_adapter_sends_only_raw_data_and_checksum():
    class Protection:
        name = "HSM"

    class Response:
        name = "projects/ofarm1/locations/europe-west1/keyRings/auth/cryptoKeys/capability/cryptoKeyVersions/1"
        protection_level = Protection()
        verified_data_crc32c = True
        signature = b"x" * 64
        signature_crc32c = 123

    class Client:
        request = None

        def asymmetric_sign(self, *, request):
            self.request = request
            return Response()

    client = Client()
    adapter = _test_adapter(client)
    result = adapter.asymmetric_sign(name=Response.name, data=b"raw", data_crc32c=7)
    assert client.request == {"name": Response.name, "data": b"raw", "data_crc32c": 7}
    assert "digest" not in client.request
    assert result.protection_level == "HSM"


def test_google_client_adapter_accepts_generated_kms_signing_response():
    from google.cloud.kms_v1.types import AsymmetricSignResponse

    resource = (
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/capability/cryptoKeyVersions/1"
    )
    generated = AsymmetricSignResponse(
        name=resource,
        protection_level="HSM",
        verified_data_crc32c=True,
        signature=b"x" * 64,
        signature_crc32c=123,
    )

    class Client:
        def asymmetric_sign(self, *, request):
            assert request["name"] == resource
            return generated

    result = _test_adapter(Client()).asymmetric_sign(
        name=resource,
        data=b"raw",
        data_crc32c=7,
    )
    assert type(generated.signature_crc32c) is int
    assert result.signature_crc32c == 123


def test_signed_observer_receipt_authenticates_production_evidence():
    from google.cloud.kms_v1.types import PublicKey

    observer_private = Ed25519PrivateKey.generate()
    observer_resource = (
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/evidence-observer/cryptoKeyVersions/1"
    )
    signing_private = Ed25519PrivateKey.generate()
    signing_public = signing_private.public_key().public_bytes_raw()
    signing_resource = (
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/capability/cryptoKeyVersions/1"
    )
    signing_key = GoogleKmsEd25519PublicKey(
        key_version_resource=signing_resource,
        der=TENANT_CAPABILITY_RFC8410_PREFIX + signing_public,
        public_key=signing_public,
        public_key_digest=raw_public_key_digest(signing_public),
        x=base64.urlsafe_b64encode(signing_public).rstrip(b"=").decode("ascii"),
        kid=derive_ed25519_key_id(signing_public),
    )
    evidence = {
        "audience": derive_binder_audience(uuid4()),
        "keyVersionResource": signing_resource,
        "keyId": signing_key.kid,
        "publicKeyDigest": "sha256:" + signing_key.public_key_digest.hex(),
        "keyPurpose": GOOGLE_KMS_KEY_PURPOSE,
        "keyAlgorithm": GOOGLE_KMS_KEY_ALGORITHM,
        "protectionLevel": GOOGLE_KMS_PROTECTION_LEVEL,
        "keyState": "ENABLED",
        "attestationEvidenceDigest": DIGEST_A,
        "iamEvidenceDigest": DIGEST_B,
        "databaseCandidateDigest": DIGEST_C,
        "databaseLifecycleHeadDigest": DIGEST_D,
        "observedAtUnixMicroseconds": 1_900_000_000_000_000,
        "validUntilUnixMicroseconds": 1_900_000_060_000_000,
    }
    canonical = json.dumps(
        evidence,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    signature = observer_private.sign(
        b"OFARM_PRODUCTION_SIGNING_EVIDENCE_V1\x00" + canonical
    )
    receipt = json.dumps(
        {
            "evidence": evidence,
            "signature": base64.urlsafe_b64encode(signature)
            .rstrip(b"=")
            .decode("ascii"),
        },
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    pem = observer_private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    class Client:
        def asymmetric_sign(self, *, request):
            raise AssertionError(request)

        def get_public_key(self, *, request):
            assert request == {"name": observer_resource}
            return PublicKey(
                name=observer_resource,
                algorithm=GOOGLE_KMS_KEY_ALGORITHM,
                protection_level=GOOGLE_KMS_PROTECTION_LEVEL,
                pem=pem,
                pem_crc32c=_crc32c(pem.encode("ascii")),
            )

    observer = GoogleKmsSigningEvidenceObserver.for_test(
        client=_test_adapter(Client()),
        observer_key_resource=observer_resource,
        receipt_bytes=receipt,
    )
    observed = observer.observe(signing_key)
    assert observed.key_version_resource == signing_resource
    assert observed.public_key_digest == signing_key.public_key_digest
    assert observer.production_eligible is False

    tampered_evidence = dict(evidence)
    tampered_evidence["iamEvidenceDigest"] = DIGEST_C
    tampered_receipt = json.dumps(
        {
            "evidence": tampered_evidence,
            "signature": base64.urlsafe_b64encode(signature)
            .rstrip(b"=")
            .decode("ascii"),
        },
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    tampered_observer = GoogleKmsSigningEvidenceObserver.for_test(
        client=_test_adapter(Client()),
        observer_key_resource=observer_resource,
        receipt_bytes=tampered_receipt,
    )
    with pytest.raises(ValueError, match="receipt signature differs"):
        tampered_observer.observe(signing_key)


def test_observer_requires_a_different_crypto_key_parent():
    now_us = 1_900_000_000_000_000
    signing_key = _signing_key(Ed25519PrivateKey.generate())
    observer_private = Ed25519PrivateKey.generate()
    observer_resource = (
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/capability/cryptoKeyVersions/2"
    )
    evidence = _evidence_payload(
        signing_key,
        derive_binder_audience(uuid4()),
        now_us - 1,
        now_us + 60_000_000,
    )
    observer_client = _ObserverPublicKeyClient(
        observer_private,
        observer_resource,
    )
    observer = GoogleKmsSigningEvidenceObserver.for_test(
        client=_test_adapter(observer_client),
        observer_key_resource=observer_resource,
        receipt_bytes=_signed_evidence_receipt(
            observer_private,
            evidence,
        ),
    )

    with pytest.raises(ValueError, match="CryptoKey must differ"):
        observer.observe(signing_key)
    assert observer_client.calls == 0


def test_kms_readiness_preflight_rejects_permission_denial():
    class DeniedKmsClient(_KmsClient):
        def asymmetric_sign(self, *, request):
            raise PermissionError(request["name"])

    signer = _production_signer(
        Ed25519PrivateKey.generate(),
        derive_binder_audience(uuid4()),
        1_900_000_000_000_000,
        client_factory=DeniedKmsClient,
    )

    with pytest.raises(CapabilityIssuanceError) as raised:
        signer.initialize()
    assert raised.value.outcome is PreBindingOutcome.SIGNER_UNAVAILABLE
    assert "KMS signing call failed" in raised.value.internal_detail
    assert signer._initialized is False


def test_kms_readiness_preflight_recovers_after_endpoint_failure():
    class UnavailableKmsClient(_KmsClient):
        unavailable = True

        def asymmetric_sign(self, *, request):
            if self.unavailable:
                raise ConnectionError("KMS endpoint unavailable")
            return super().asymmetric_sign(request=request)

    signer = _production_signer(
        Ed25519PrivateKey.generate(),
        derive_binder_audience(uuid4()),
        1_900_000_000_000_000,
        client_factory=UnavailableKmsClient,
    )
    raw_client = signer._client._client

    with pytest.raises(CapabilityIssuanceError) as raised:
        signer.initialize()
    assert raised.value.outcome is PreBindingOutcome.SIGNER_UNAVAILABLE
    assert "KMS signing call failed" in raised.value.internal_detail
    assert signer._initialized is False

    raw_client.unavailable = False
    signer.initialize()
    assert signer._initialized is True
    assert raw_client.calls == [TENANT_CAPABILITY_PREFLIGHT_PROBE]


def test_kms_readiness_preflight_rejects_disabled_evidence():
    signer = _production_signer(
        Ed25519PrivateKey.generate(),
        derive_binder_audience(uuid4()),
        1_900_000_000_000_000,
        key_state="DISABLED",
    )

    with pytest.raises(CapabilityIssuanceError) as raised:
        signer.initialize()
    assert raised.value.outcome is PreBindingOutcome.SIGNER_UNAVAILABLE
    assert "differs or is stale" in raised.value.internal_detail
    assert signer._client._client.calls == []


def test_kms_readiness_preflight_rejects_an_actually_disabled_key():
    class DisabledKmsClient(_KmsClient):
        def asymmetric_sign(self, *, request):
            assert request["name"] == self.resource
            assert request["data"] == TENANT_CAPABILITY_PREFLIGHT_PROBE
            assert request["data_crc32c"] == _crc32c(request["data"])
            self.calls.append(request["data"])
            raise FailedPrecondition(
                "CryptoKeyVersion state is DISABLED"
            )

    signer = _production_signer(
        Ed25519PrivateKey.generate(),
        derive_binder_audience(uuid4()),
        1_900_000_000_000_000,
        client_factory=DisabledKmsClient,
    )

    with pytest.raises(CapabilityIssuanceError) as raised:
        signer.initialize()
    assert raised.value.outcome is PreBindingOutcome.SIGNER_UNAVAILABLE
    assert "KMS signing call failed" in raised.value.internal_detail
    assert signer._client._client.calls == [
        TENANT_CAPABILITY_PREFLIGHT_PROBE
    ]
    assert signer._evidence is not signer._last_accepted_evidence
    assert signer._last_accepted_evidence is None
    assert signer._initialized is False


def test_kms_refresh_retains_prior_evidence_when_key_becomes_disabled():
    class StatefulKmsClient(_KmsClient):
        disabled = False

        def asymmetric_sign(self, *, request):
            if self.disabled:
                assert request["name"] == self.resource
                assert request["data"] == TENANT_CAPABILITY_PREFLIGHT_PROBE
                assert request["data_crc32c"] == _crc32c(request["data"])
                self.calls.append(request["data"])
                raise FailedPrecondition(
                    "CryptoKeyVersion state is DESTROY_SCHEDULED"
                )
            return super().asymmetric_sign(request=request)

    now = [1_900_000_000_000_000]
    (
        signer,
        observer,
        observer_private,
        _,
        raw_kms,
        signing_key,
        audience,
        initial_valid_until,
    ) = _refreshing_signer_fixture(
        now,
        kms_client_factory=StatefulKmsClient,
    )
    signer.initialize()
    accepted = signer._evidence
    now[0] = initial_valid_until - 20_000_000
    observer._receipt_bytes = _signed_evidence_receipt(
        observer_private,
        _evidence_payload(
            signing_key,
            audience,
            now[0],
            now[0] + 60_000_000,
        ),
    )
    raw_kms.disabled = True

    with pytest.raises(CapabilityIssuanceError) as raised:
        signer.initialize()
    assert raised.value.outcome is PreBindingOutcome.SIGNER_UNAVAILABLE
    assert "KMS signing call failed" in raised.value.internal_detail
    assert signer._evidence is accepted
    assert signer._last_accepted_evidence is accepted
    assert signer._initialized is True

    raw_kms.disabled = False
    signer.sign(b"prior-evidence-remains-usable")


def test_kms_readiness_preflight_rejects_public_key_mismatch():
    wrong_private = Ed25519PrivateKey.generate()

    def wrong_key_client(private, resource):
        del private
        return _KmsClient(wrong_private, resource)

    signer = _production_signer(
        Ed25519PrivateKey.generate(),
        derive_binder_audience(uuid4()),
        1_900_000_000_000_000,
        client_factory=wrong_key_client,
    )

    with pytest.raises(CapabilityIssuanceError) as raised:
        signer.initialize()
    assert raised.value.outcome is PreBindingOutcome.SIGNER_UNAVAILABLE
    assert "signature verification failed" in raised.value.internal_detail


def test_kms_refresh_is_failure_atomic_and_recovers_without_restart():
    now = [1_900_000_000_000_000]
    signing_private = Ed25519PrivateKey.generate()
    signing_key = _signing_key(signing_private)
    observer_private = Ed25519PrivateKey.generate()
    observer_resource = (
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/evidence-observer/cryptoKeyVersions/1"
    )
    audience = derive_binder_audience(uuid4())
    initial_valid_until = now[0] + 60_000_000
    initial_payload = _evidence_payload(
        signing_key,
        audience,
        now[0] - 1,
        initial_valid_until,
    )
    observer_client = _ObserverPublicKeyClient(
        observer_private,
        observer_resource,
    )
    observer = GoogleKmsSigningEvidenceObserver.for_test(
        client=_test_adapter(observer_client),
        observer_key_resource=observer_resource,
        receipt_bytes=_signed_evidence_receipt(
            observer_private,
            initial_payload,
        ),
    )
    raw_kms = _KmsClient(
        signing_private,
        signing_key.key_version_resource,
    )
    signer = GoogleKmsEd25519Signer.for_test(
        client=_test_adapter(raw_kms),
        public_key=signing_key,
        evidence=_production_evidence(
            signing_key,
            audience,
            now[0] - 1,
            initial_valid_until,
        ),
        evidence_observer=observer,
        now_microseconds=lambda: now[0],
    )
    signer.initialize()
    accepted = signer._evidence

    disabled = _evidence_payload(
        signing_key,
        audience,
        now[0],
        now[0] + 60_000_000,
        key_state="DISABLED",
    )
    observer._receipt_bytes = _signed_evidence_receipt(
        observer_private,
        disabled,
    )
    with pytest.raises(CapabilityIssuanceError):
        signer.initialize()
    assert signer._evidence is accepted
    signer.sign(b"old-evidence-remains-valid")

    now[0] = initial_valid_until - 20_000_000
    observer._receipt_bytes = b"not-a-signed-receipt"
    signer.sign(b"observer-failure-uses-current-snapshot")
    assert signer._evidence is accepted

    now[0] += 1_000_001
    rotated_valid_until = now[0] + 60_000_000
    rotated = _evidence_payload(
        signing_key,
        audience,
        now[0],
        rotated_valid_until,
    )
    observer._receipt_bytes = _signed_evidence_receipt(
        observer_private,
        rotated,
    )
    signer.sign(b"rotation-recovers-without-restart")
    assert signer._evidence is not accepted
    assert (
        signer._evidence.valid_until_unix_microseconds
        == rotated_valid_until
    )


@pytest.mark.parametrize(
    ("candidate_kind", "detail"),
    (
        ("older", "observation rolls back"),
        ("conflicting", "conflicts at one observation time"),
    ),
)
def test_kms_refresh_rejects_authenticated_receipt_replay(
    candidate_kind,
    detail,
):
    now = [1_900_000_000_000_000]
    (
        signer,
        observer,
        observer_private,
        _,
        _,
        signing_key,
        audience,
        initial_valid_until,
    ) = _refreshing_signer_fixture(now)
    signer.initialize()
    accepted = signer._evidence
    now[0] = initial_valid_until - 20_000_000

    if candidate_kind == "older":
        candidate = _evidence_payload(
            signing_key,
            audience,
            accepted.observed_at_unix_microseconds - 10_000_000,
            now[0] + 100_000_000,
        )
    else:
        candidate = _evidence_payload(
            signing_key,
            audience,
            accepted.observed_at_unix_microseconds,
            now[0] + 100_000_000,
        )
        candidate["iamEvidenceDigest"] = DIGEST_C
    observer._receipt_bytes = _signed_evidence_receipt(
        observer_private,
        candidate,
    )

    with pytest.raises(CapabilityIssuanceError) as raised:
        signer.initialize()
    assert detail in raised.value.internal_detail
    assert signer._evidence is accepted
    assert signer._last_accepted_evidence is accepted
    assert signer._initialized is True
    signer.sign(b"last-accepted-snapshot-remains-usable")


def test_kms_refresh_backs_off_when_receipt_does_not_advance():
    now = [1_900_000_000_000_000]
    (
        signer,
        _,
        _,
        observer_client,
        raw_kms,
        _,
        _,
        initial_valid_until,
    ) = _refreshing_signer_fixture(now)
    signer.initialize()
    accepted = signer._evidence
    now[0] = initial_valid_until - 20_000_000

    signer.sign(b"unchanged-receipt-0")
    signer.sign(b"unchanged-receipt-1")

    assert signer._evidence is accepted
    assert observer_client.calls == 2
    assert raw_kms.calls == [
        TENANT_CAPABILITY_PREFLIGHT_PROBE,
        TENANT_CAPABILITY_PREFLIGHT_PROBE,
        b"unchanged-receipt-0",
        b"unchanged-receipt-1",
    ]

    now[0] += 1_000_001
    signer.sign(b"unchanged-receipt-after-backoff")
    assert observer_client.calls == 3


def test_kms_refresh_rechecks_expiry_inside_publication_lock(monkeypatch):
    now = [1_900_000_000_000_000]
    initial_valid_until = now[0] + 5
    signer, *_ = _refreshing_signer_fixture(
        now,
        initial_valid_until=initial_valid_until,
    )
    original_progress_check = (
        GoogleKmsEd25519Signer._candidate_is_no_progress
    )

    def expire_before_publication(candidate, previous):
        no_progress = original_progress_check(candidate, previous)
        now[0] = candidate.valid_until_unix_microseconds
        return no_progress

    monkeypatch.setattr(
        GoogleKmsEd25519Signer,
        "_candidate_is_no_progress",
        staticmethod(expire_before_publication),
    )

    with pytest.raises(CapabilityIssuanceError) as raised:
        signer.initialize()
    assert "expired before publication" in raised.value.internal_detail
    assert signer._last_accepted_evidence is None
    assert signer._initialized is False


def test_kms_refresh_never_publishes_evidence_expired_during_preflight():
    now = [1_900_000_000_000_000]

    class ExpiringPreflightClient(_KmsClient):
        expire_during_preflight = False

        def asymmetric_sign(self, *, request):
            response = super().asymmetric_sign(request=request)
            if (
                self.expire_during_preflight
                and request["data"] == TENANT_CAPABILITY_PREFLIGHT_PROBE
            ):
                now[0] += 10
            return response

    signing_private = Ed25519PrivateKey.generate()
    signing_key = _signing_key(signing_private)
    audience = derive_binder_audience(uuid4())
    observer_private = Ed25519PrivateKey.generate()
    observer_resource = (
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/evidence-observer/cryptoKeyVersions/1"
    )
    initial_valid_until = now[0] + 60_000_000
    observer = GoogleKmsSigningEvidenceObserver.for_test(
        client=_test_adapter(
            _ObserverPublicKeyClient(
                observer_private,
                observer_resource,
            )
        ),
        observer_key_resource=observer_resource,
        receipt_bytes=_signed_evidence_receipt(
            observer_private,
            _evidence_payload(
                signing_key,
                audience,
                now[0] - 1,
                initial_valid_until,
            ),
        ),
    )
    raw_kms = ExpiringPreflightClient(
        signing_private,
        signing_key.key_version_resource,
    )
    signer = GoogleKmsEd25519Signer.for_test(
        client=_test_adapter(raw_kms),
        public_key=signing_key,
        evidence=_production_evidence(
            signing_key,
            audience,
            now[0] - 1,
            initial_valid_until,
        ),
        evidence_observer=observer,
        now_microseconds=lambda: now[0],
    )
    signer.initialize()
    accepted = signer._evidence

    candidate_valid_until = now[0] + 5
    observer._receipt_bytes = _signed_evidence_receipt(
        observer_private,
        _evidence_payload(
            signing_key,
            audience,
            now[0],
            candidate_valid_until,
        ),
    )
    raw_kms.expire_during_preflight = True
    with pytest.raises(CapabilityIssuanceError) as raised:
        signer.initialize()
    assert "expired during KMS call" in raised.value.internal_detail
    assert signer._evidence is accepted
    assert signer._initialized is True


def test_kms_cold_start_waiters_share_one_refresh_attempt():
    class WaitTrackingCondition(threading.Condition):
        def __init__(self, expected_waiters):
            super().__init__()
            self.expected_waiters = expected_waiters
            self.waiter_count = 0
            self.all_waiting = threading.Event()

        def wait(self, timeout=None):
            self.waiter_count += 1
            if self.waiter_count == self.expected_waiters:
                self.all_waiting.set()
            return super().wait(timeout=timeout)

    now = [1_900_000_000_000_000]
    entered = threading.Event()
    release = threading.Event()
    (
        signer,
        _,
        _,
        observer_client,
        raw_kms,
        _,
        _,
        _,
    ) = _refreshing_signer_fixture(
        now,
        observer_entered=entered,
        observer_release=release,
        observer_block_on_call=1,
    )
    condition = WaitTrackingCondition(expected_waiters=2)
    signer._state_condition = condition

    with ThreadPoolExecutor(max_workers=3) as executor:
        leader = executor.submit(signer.initialize)
        assert entered.wait(timeout=5)
        waiters = [
            executor.submit(signer.initialize)
            for _ in range(2)
        ]
        try:
            assert condition.all_waiting.wait(timeout=5)
        finally:
            release.set()
        leader.result(timeout=5)
        for waiter in waiters:
            waiter.result(timeout=5)

    assert signer._initialized is True
    assert observer_client.calls == 1
    assert raw_kms.calls == [TENANT_CAPABILITY_PREFLIGHT_PROBE]


def test_kms_expired_waiter_times_out_and_recovers_with_leader(
    monkeypatch,
):
    monkeypatch.setattr(
        "kernel.tenant_capability."
        "_SIGNING_EVIDENCE_REFRESH_WAIT_SECONDS",
        0.01,
    )
    now = [1_900_000_000_000_000]
    entered = threading.Event()
    release = threading.Event()
    (
        signer,
        observer,
        observer_private,
        observer_client,
        _,
        signing_key,
        audience,
        initial_valid_until,
    ) = _refreshing_signer_fixture(
        now,
        observer_entered=entered,
        observer_release=release,
    )
    signer.initialize()
    now[0] = initial_valid_until
    rotated_valid_until = now[0] + 60_000_000
    observer._receipt_bytes = _signed_evidence_receipt(
        observer_private,
        _evidence_payload(
            signing_key,
            audience,
            now[0],
            rotated_valid_until,
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        leader = executor.submit(signer.sign, b"expired-refresh-leader")
        assert entered.wait(timeout=5)
        waiter = executor.submit(
            signer.sign,
            b"expired-refresh-waiter",
        )
        try:
            with pytest.raises(CapabilityIssuanceError) as raised:
                waiter.result(timeout=1)
            assert (
                "refresh did not complete"
                in raised.value.internal_detail
            )
        finally:
            release.set()
        leader.result(timeout=5)

    signer.sign(b"recovered-after-waiter-timeout")
    assert signer._initialized is True
    assert observer_client.calls == 2
    assert (
        signer._evidence.valid_until_unix_microseconds
        == rotated_valid_until
    )


def test_kms_refresh_is_single_flight_for_concurrent_signers():
    now = [1_900_000_000_000_000]
    signing_private = Ed25519PrivateKey.generate()
    signing_key = _signing_key(signing_private)
    audience = derive_binder_audience(uuid4())
    observer_private = Ed25519PrivateKey.generate()
    observer_resource = (
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/evidence-observer/cryptoKeyVersions/1"
    )
    entered = threading.Event()
    release = threading.Event()
    observer_client = _ObserverPublicKeyClient(
        observer_private,
        observer_resource,
        entered=entered,
        release=release,
    )
    initial_valid_until = now[0] + 60_000_000
    observer = GoogleKmsSigningEvidenceObserver.for_test(
        client=_test_adapter(observer_client),
        observer_key_resource=observer_resource,
        receipt_bytes=_signed_evidence_receipt(
            observer_private,
            _evidence_payload(
                signing_key,
                audience,
                now[0] - 1,
                initial_valid_until,
            ),
        ),
    )
    raw_kms = _KmsClient(
        signing_private,
        signing_key.key_version_resource,
    )
    signer = GoogleKmsEd25519Signer.for_test(
        client=_test_adapter(raw_kms),
        public_key=signing_key,
        evidence=_production_evidence(
            signing_key,
            audience,
            now[0] - 1,
            initial_valid_until,
        ),
        evidence_observer=observer,
        now_microseconds=lambda: now[0],
    )
    signer.initialize()

    now[0] = initial_valid_until - 20_000_000
    rotated_valid_until = now[0] + 60_000_000
    observer._receipt_bytes = _signed_evidence_receipt(
        observer_private,
        _evidence_payload(
            signing_key,
            audience,
            now[0],
            rotated_valid_until,
        ),
    )
    with ThreadPoolExecutor(max_workers=4) as executor:
        first = executor.submit(signer.sign, b"concurrent-0")
        assert entered.wait(timeout=5)
        others = [
            executor.submit(
                signer.sign,
                f"concurrent-{index}".encode("ascii"),
            )
            for index in range(1, 4)
        ]
        release.set()
        signatures = [first.result(timeout=5)]
        signatures.extend(
            future.result(timeout=5) for future in others
        )

    assert len(signatures) == 4
    assert observer_client.calls == 2
    assert (
        signer._evidence.valid_until_unix_microseconds
        == rotated_valid_until
    )


def test_capability_wrong_audience_and_stale_signer_refuse_safely():
    authority = _authority()
    audience = derive_binder_audience(uuid4())
    now_us = 1_900_000_000_000_000
    issuer = ProductionTenantCapabilityIssuer.for_test(
        resolver=_CapabilityResolver(authority),
        signer=_production_signer(Ed25519PrivateKey.generate(), audience, now_us),
        now_microseconds=lambda: now_us,
    )
    issuer.initialize()
    with pytest.raises(CapabilityIssuanceError) as raised:
        issuer.mint(_identity(), TenantChallenge(uuid4(), derive_binder_audience(uuid4())))
    assert raised.value.outcome is PreBindingOutcome.CAPABILITY_REFUSED
    assert PARTY not in str(raised.value)


def test_production_issuer_rejects_local_fixture_signer():
    audience = derive_binder_audience(uuid4())
    issuer = ProductionTenantCapabilityIssuer(
        resolver=PostgreSQLPrincipalBindingResolver(lambda: None),
        signer=_FixtureSigner(Ed25519PrivateKey.generate(), audience),
    )
    with pytest.raises(CapabilityIssuanceError) as raised:
        issuer.initialize()
    assert raised.value.outcome is PreBindingOutcome.CONFIGURATION_REFUSED


def test_production_issuer_rejects_local_key_signer_subclass():
    class LocalSignerSubclass(GoogleKmsEd25519Signer):
        def __init__(self, private, audience):
            self.private = private
            self._audience = audience

        @property
        def key_id(self):
            return "local-key"

        @property
        def public_key(self):
            return self.private.public_key().public_bytes_raw()

        @property
        def audience(self):
            return self._audience

        def initialize(self):
            pass

        def sign(self, data):
            return self.private.sign(data)

    issuer = ProductionTenantCapabilityIssuer(
        resolver=PostgreSQLPrincipalBindingResolver(lambda: None),
        signer=LocalSignerSubclass(
            Ed25519PrivateKey.generate(), derive_binder_audience(uuid4())
        ),
    )
    with pytest.raises(CapabilityIssuanceError) as raised:
        issuer.initialize()
    assert raised.value.outcome is PreBindingOutcome.CONFIGURATION_REFUSED


def test_production_issuer_rejects_a_fake_binding_resolver():
    now_us = 1_900_000_000_000_000
    signer = _production_signer(
        Ed25519PrivateKey.generate(),
        derive_binder_audience(uuid4()),
        now_us,
    )
    with pytest.raises(CapabilityIssuanceError) as raised:
        ProductionTenantCapabilityIssuer(
            resolver=_CapabilityResolver(_authority()),
            signer=signer,
        )
    assert raised.value.outcome is PreBindingOutcome.CONFIGURATION_REFUSED
    assert "sealed PostgreSQL" in raised.value.internal_detail


def test_google_adapter_rejects_duck_typed_software_signer():
    private = Ed25519PrivateKey.generate()
    resource = (
        "projects/ofarm1/locations/europe-west1/keyRings/auth/"
        "cryptoKeys/capability/cryptoKeyVersions/1"
    )
    with pytest.raises(TypeError, match="positional argument"):
        GoogleCloudKmsClientAdapter(_KmsClient(private, resource))


def test_google_adapter_constructs_the_official_client_without_network(monkeypatch):
    from google.cloud.kms_v1.services.key_management_service.client import (
        KeyManagementServiceClient,
    )

    constructed = []

    def offline_constructor(client):
        constructed.append(client)

    monkeypatch.setattr(KeyManagementServiceClient, "__init__", offline_constructor)
    adapter = GoogleCloudKmsClientAdapter()

    assert len(constructed) == 1
    assert type(constructed[0]) is KeyManagementServiceClient
    assert adapter.production_eligible is True


def test_exact_google_client_with_custom_transport_cannot_be_injected():
    from google.cloud.kms_v1.services.key_management_service.client import (
        KeyManagementServiceClient,
    )

    exact_client = object.__new__(KeyManagementServiceClient)
    exact_client._transport = object()

    with pytest.raises(TypeError, match="positional argument"):
        GoogleCloudKmsClientAdapter(exact_client)


def test_concrete_kms_signer_rejects_non_google_client():
    private = Ed25519PrivateKey.generate()
    now_us = 1_900_000_000_000_000
    prepared = _production_signer(
        private, derive_binder_audience(uuid4()), now_us
    )
    issuer = ProductionTenantCapabilityIssuer(
        resolver=PostgreSQLPrincipalBindingResolver(lambda: None),
        signer=prepared,
    )
    with pytest.raises(CapabilityIssuanceError) as issuer_error:
        issuer.initialize()
    assert issuer_error.value.outcome is PreBindingOutcome.CONFIGURATION_REFUSED

    with pytest.raises(TypeError, match="evidence"):
        GoogleKmsEd25519Signer(
            client=prepared._client,
            public_key=prepared._public_key_observation,
            evidence=prepared._evidence,
        )

    with pytest.raises(TypeError, match="now_microseconds"):
        GoogleKmsEd25519Signer(
            client=prepared._client,
            public_key=prepared._public_key_observation,
            now_microseconds=lambda: now_us,
        )
    with pytest.raises(TypeError, match="now_microseconds"):
        ProductionTenantCapabilityIssuer(
            resolver=PostgreSQLPrincipalBindingResolver(lambda: None),
            signer=prepared,
            now_microseconds=lambda: now_us,
        )


@pytest.mark.parametrize(
    ("observed_offset", "valid_offset"),
    (
        (-300_000_001, 1),
        (0, 300_000_001),
    ),
)
def test_production_signer_rejects_unbounded_observer_evidence(
    observed_offset, valid_offset
):
    now_us = 1_900_000_000_000_000
    signer = _production_signer(
        Ed25519PrivateKey.generate(),
        derive_binder_audience(uuid4()),
        now_us,
        observed_at_us=now_us + observed_offset,
        valid_until_us=now_us + valid_offset,
    )
    with pytest.raises(CapabilityIssuanceError) as raised:
        signer.initialize()
    assert raised.value.outcome is PreBindingOutcome.SIGNER_UNAVAILABLE
