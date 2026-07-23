"""Application-owned #172 binding, control-plane, and capability tests."""
from __future__ import annotations

import base64
import json
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from deployment.postgresql.tenant_contract import (
    GOOGLE_KMS_KEY_ALGORITHM,
    GOOGLE_KMS_KEY_PURPOSE,
    GOOGLE_KMS_PROTECTION_LEVEL,
    GoogleKmsEd25519PublicKey,
    TENANT_CAPABILITY_RFC8410_PREFIX,
    decode_tenant_capability_jws,
    derive_binder_audience,
    derive_ed25519_key_id,
    raw_public_key_digest,
)
from kernel.auth_oidc import (
    AuthenticationStartupError,
    OidcError,
    PreBindingOutcome,
    VerifiedOidcIdentity,
)
from kernel.principal_binding import (
    BindingLifecycleHead,
    BindingTransitionRequest,
    BindingVersionCandidate,
    PostgreSQLPrincipalBindingResolver,
    PrincipalBindingAct,
    PrincipalBindingAuthority,
    PrincipalBindingControlError,
    PrincipalBindingControlPlane,
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


class _Result:
    def __init__(self, *, one=None, many=None):
        self.one = one
        self.many = [] if many is None else many

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class _Connection(AbstractContextManager):
    def __init__(self, handler):
        self.handler = handler
        self.statements: list[tuple[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.statements.append((query, params))
        return self.handler(query, params)


class _Factory:
    def __init__(self, connection):
        self.connection = connection

    def __call__(self):
        return self.connection


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


def test_resolver_folds_immutable_authority_and_never_reads_projection():
    authority = _authority()
    row = tuple(getattr(authority, field) for field in authority.__dataclass_fields__) + (
        True,
    )

    def handler(query, _params):
        if "startup-probe" in repr(_params):
            return _Result(many=[])
        return _Result(many=[row])

    connection = _Connection(handler)
    resolver = PostgreSQLPrincipalBindingResolver(_Factory(connection))
    resolver.initialize()
    assert resolver.resolve(_identity()) == authority
    sql = "\n".join(query.lower() for query, _ in connection.statements)
    assert "resolve_principal_binding_authority" in sql
    assert "principal_binding_current" not in sql
    assert "join ofarm.principal_binding" not in sql
    assert "join ofarm.tenant_registry" not in sql
    assert "join ofarm.kernel_record" not in sql


def test_resolver_startup_refuses_unavailable_fixed_database_boundary():
    def handler(query, _params):
        assert "resolve_principal_binding_authority" in query.lower()
        raise PermissionError("simulated unavailable fixed resolver boundary")

    resolver = PostgreSQLPrincipalBindingResolver(
        _Factory(_Connection(handler))
    )
    with pytest.raises(
        AuthenticationStartupError,
        match="principal-binding immutable read path is unavailable",
    ):
        resolver.initialize()


def test_missing_or_ambiguous_binding_fails_closed_with_safe_outcome():
    for rows, outcome in (
        ([], PreBindingOutcome.PRINCIPAL_UNBOUND),
        ([tuple(range(18)), tuple(range(18))], PreBindingOutcome.BINDING_INTEGRITY_REFUSED),
    ):
        calls = 0

        def handler(_query, _params):
            nonlocal calls
            calls += 1
            return _Result(many=[] if calls == 1 else rows)

        resolver = PostgreSQLPrincipalBindingResolver(_Factory(_Connection(handler)))
        resolver.initialize()
        with pytest.raises(OidcError) as raised:
            resolver.resolve(_identity())
        assert raised.value.outcome is outcome
        assert SUBJECT not in str(raised.value)


def test_control_plane_activates_only_through_hardened_functions():
    now = datetime.now(UTC)
    candidate = BindingVersionCandidate(
        binding_version_id=uuid4(),
        tenant_id=uuid4(),
        tenant_registration_digest=DIGEST_A,
        party_ref=PARTY,
        party_record_kind="ofarm.party.v0.1",
        party_record_id=PARTY,
        party_schema_digest=DIGEST_B,
        party_payload_digest=DIGEST_C,
        party_state="ACTIVE",
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(days=1),
    )

    def handler(query, _params):
        if "compute_principal_binding_version_digest" in query:
            return _Result(one=(DIGEST_D,))
        if "compute_principal_lifecycle_act_digest" in query:
            return _Result(one=("sha256:" + "66" * 32,))
        if "transition_principal_binding" in query:
            return _Result(one=(None,))
        raise AssertionError(query)

    connection = _Connection(handler)
    controller = PrincipalBindingControlPlane(_Factory(connection))
    receipt = controller.transition(
        BindingTransitionRequest(
            act_kind=PrincipalBindingAct.ACTIVATE,
            issuer=ISSUER,
            subject=SUBJECT,
            expected_head=None,
            effective_at=now,
            decided_at=now,
            accountable_control_ref="control:identity-admin",
            reason="initial-activation",
            candidate=candidate,
        )
    )
    assert receipt.binding_version_id == candidate.binding_version_id
    assert receipt.binding_version_digest == DIGEST_D
    sql = "\n".join(query.lower() for query, _ in connection.statements)
    assert "compute_principal_binding_version_digest" in sql
    assert "compute_principal_lifecycle_act_digest" in sql
    assert "transition_principal_binding" in sql
    assert not any(word in sql for word in ("insert into", "update ", "delete from"))


def test_control_plane_requires_exact_head_and_predecessor_for_supersession():
    now = datetime.now(UTC)
    current_id = uuid4()
    head = BindingLifecycleHead(
        stream_sequence=1,
        act_id=uuid4(),
        act_digest=DIGEST_A,
        current_state="ACTIVE",
        binding_version_id=current_id,
        binding_version_digest=DIGEST_B,
    )
    bad_candidate = BindingVersionCandidate(
        binding_version_id=uuid4(),
        tenant_id=uuid4(),
        tenant_registration_digest=DIGEST_A,
        party_ref=PARTY,
        party_record_kind="ofarm.party.v0.1",
        party_record_id=PARTY,
        party_schema_digest=DIGEST_B,
        party_payload_digest=DIGEST_C,
        party_state="ACTIVE",
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(days=1),
        predecessor_version_id=uuid4(),
    )
    controller = PrincipalBindingControlPlane(
        _Factory(_Connection(lambda *_: pytest.fail("database must not be called")))
    )
    with pytest.raises(PrincipalBindingControlError):
        controller.transition(
            BindingTransitionRequest(
                act_kind=PrincipalBindingAct.SUPERSEDE,
                issuer=ISSUER,
                subject=SUBJECT,
                expected_head=head,
                current_binding_version_id=current_id,
                current_binding_version_digest=DIGEST_B,
                candidate=bad_candidate,
                effective_at=now,
                decided_at=now,
                accountable_control_ref="control:identity-admin",
                reason="replacement",
            )
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
    client_factory=None,
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
        key_state="ENABLED",
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
    assert raw_client.calls == [data]


def test_kms_signer_rechecks_evidence_after_slow_signing_response():
    now = [1_900_000_000_000_000]

    class ExpiringKmsClient(_KmsClient):
        def asymmetric_sign(self, *, request):
            response = super().asymmetric_sign(request=request)
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
