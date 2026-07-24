"""Production composition, startup ordering, and dependency sealing."""
from __future__ import annotations

import base64
import inspect
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kernel import api, application_runtime
from kernel.application_runtime import (
    RuntimeMetadata,
    RuntimeStartupError,
)
from kernel.runtime_activation import RuntimeActivationError
from kernel.runtime_config import (
    RuntimeConfig,
    RuntimeConfigurationError,
    RuntimeMode,
)


IMAGE = "sha256:" + "1" * 64
KID = "k" * 43
OBSERVER_KEY = b"o" * 32


def _environment() -> dict[str, str]:
    return {
        "OFARM_AUTH_MODE": "production",
        "OFARM_DEPLOYMENT_IMAGE_DIGEST": IMAGE,
        "OFARM_OIDC_ISSUER": "https://issuer.example/tenant",
        "OFARM_OIDC_AUDIENCE": "external-api",
        "OFARM_OIDC_JWKS_URL": "https://issuer.example/jwks",
        "OFARM_PG_DSN": "dbname=ofarm user=ofarm_app",
        "OFARM_TENANT_CAPABILITY_KID": KID,
        "OFARM_SIGNING_EVIDENCE_RECEIPT_PATH": "/run/ofarm/receipt",
        "OFARM_SIGNING_EVIDENCE_OBSERVER_PUBLIC_KEY_B64": (
            base64.b64encode(OBSERVER_KEY).decode("ascii")
        ),
    }


def _config(*, image: str = IMAGE) -> RuntimeConfig:
    return RuntimeConfig(
        mode=RuntimeMode.PRODUCTION,
        deployment_image_digest=image,
        oidc_issuer="https://issuer.example/tenant",
        oidc_audience="external-api",
        oidc_jwks_url="https://issuer.example/jwks",
        pg_dsn="dbname=ofarm user=ofarm_app",
        tenant_capability_kid=KID,
        signing_evidence_receipt_path=Path("/run/ofarm/receipt"),
        signing_evidence_observer_public_key=OBSERVER_KEY,
    )


def test_runtime_config_is_one_immutable_environment_snapshot(monkeypatch):
    values = _environment()
    monkeypatch.setattr("kernel.runtime_config.os.environ", values)

    config = RuntimeConfig.from_env()
    values["OFARM_OIDC_AUDIENCE"] = "changed-after-snapshot"

    assert config.oidc_audience == "external-api"
    assert config.signing_evidence_observer_public_key == OBSERVER_KEY
    assert config.signing_evidence_receipt_path == Path("/run/ofarm/receipt")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("OFARM_AUTH_MODE", "test"),
        ("OFARM_OIDC_JWKS_URL", "http://issuer.example/jwks"),
        ("OFARM_PG_DSN", "broken=="),
        ("OFARM_TENANT_CAPABILITY_KID", "short"),
        ("OFARM_SIGNING_EVIDENCE_RECEIPT_PATH", "relative/receipt"),
        ("OFARM_SIGNING_EVIDENCE_OBSERVER_PUBLIC_KEY_B64", "not-base64"),
    ],
)
def test_runtime_config_rejects_invalid_static_settings(
    monkeypatch, name, value
):
    values = _environment()
    values[name] = value
    monkeypatch.setattr("kernel.runtime_config.os.environ", values)

    with pytest.raises(RuntimeConfigurationError):
        RuntimeConfig.from_env()


def test_image_identity_is_validated_before_runtime_io(monkeypatch):
    events = []
    monkeypatch.setattr(
        application_runtime.httpx,
        "Client",
        lambda **_kwargs: events.append("http"),
    )

    with pytest.raises(RuntimeActivationError):
        application_runtime.build_application_runtime(_config(image="bad"))

    assert events == []


def _install_graph_fakes(monkeypatch, events, failures=None):
    failures = failures or {}

    class Client:
        def close(self):
            events.append("http.close")
            if failure := failures.get("http.close"):
                raise failure

    class KmsTransport:
        def close(self):
            events.append("kms.close")
            if failure := failures.get("kms.close"):
                raise failure

    class KmsClient:
        def __init__(self):
            self.transport = KmsTransport()

    class Verifier:
        def __init__(self, config, client):
            assert config.audience == "external-api"
            assert isinstance(client, Client)
            events.append("verifier.build")

        def initialize(self):
            events.append("verifier.initialize")
            if failure := failures.get("verifier.initialize"):
                raise failure

    class Resolver:
        audience = "binder-audience"

        def __init__(self, _factory):
            events.append("resolver.build")

        def initialize(self):
            events.append("resolver.initialize")

    class Reader:
        def __init__(self, _factory, _source, _verifier):
            events.append("reader.build")

        def current(self, kid):
            assert kid == KID
            events.append("reader.current")
            return type("Signing", (), {"audience": "binder-audience"})()

    class Signer:
        def __init__(self, client):
            assert isinstance(client, KmsClient)
            events.append("signer.build")

        def sign(self, _data, _authority):
            events.append("signer.sign")
            return b"signature"

    class Issuer:
        def __init__(self, _reader, _signer, *, kid):
            assert kid == KID
            events.append("issuer.build")

        def mint(self, _identity, _authority, _challenge):
            return "capability"

    monkeypatch.setattr(
        application_runtime.httpx,
        "Client",
        lambda **kwargs: (
            events.append(("http.build", kwargs)) or Client()
        ),
    )
    monkeypatch.setattr(
        application_runtime.kms_v1,
        "KeyManagementServiceClient",
        lambda: events.append("kms.build") or KmsClient(),
    )
    monkeypatch.setattr(application_runtime, "ProductionOidcVerifier", Verifier)
    monkeypatch.setattr(application_runtime, "PrincipalBindingResolver", Resolver)
    monkeypatch.setattr(application_runtime, "SigningAuthorityReader", Reader)
    monkeypatch.setattr(
        application_runtime,
        "SigningEvidenceVerifier",
        lambda key: events.append(("receipt-verifier.build", key)) or object(),
    )
    monkeypatch.setattr(application_runtime, "GoogleKmsSigner", Signer)
    monkeypatch.setattr(application_runtime, "TenantCapabilityIssuer", Issuer)


def test_production_graph_initializes_in_fixed_order(monkeypatch):
    events = []
    _install_graph_fakes(monkeypatch, events)

    runtime = application_runtime.build_application_runtime(_config())

    assert events == [
        ("http.build", {"follow_redirects": False}),
        "kms.build",
        "verifier.build",
        "resolver.build",
        ("receipt-verifier.build", OBSERVER_KEY),
        "reader.build",
        "signer.build",
        "issuer.build",
        "verifier.initialize",
        "resolver.initialize",
        "reader.current",
        "signer.sign",
    ]
    assert runtime.metadata.oidc_audience == "external-api"
    assert runtime.metadata.binder_audience == "binder-audience"
    runtime.close()
    assert events[-2:] == ["http.close", "kms.close"]


def test_startup_failure_is_preserved_and_every_client_closes(monkeypatch):
    events = []
    startup_error = RuntimeStartupError("startup refused")
    _install_graph_fakes(
        monkeypatch,
        events,
        {
            "verifier.initialize": startup_error,
            "http.close": RuntimeError("HTTP close failed"),
            "kms.close": RuntimeError("KMS close failed"),
        },
    )

    with pytest.raises(RuntimeStartupError) as raised:
        application_runtime.build_application_runtime(_config())

    assert raised.value is startup_error
    assert events[-2:] == ["http.close", "kms.close"]


def test_create_app_has_no_injection_arguments():
    assert list(inspect.signature(api.create_app).parameters) == []
    assert "store" in inspect.signature(api.create_test_app).parameters


def test_production_and_development_imports_exclude_test_hs256():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import kernel.api, kernel.legacy_runtime; "
            "assert 'kernel.auth_oidc' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


class _ClosedRuntime:
    def __init__(self):
        self.metadata = RuntimeMetadata(
            mode=RuntimeMode.PRODUCTION,
            deployment_image_digest=IMAGE,
            oidc_issuer="https://issuer.example/tenant",
            oidc_audience="external-api",
            binder_audience="binder-audience",
            tenant_capability_kid=KID,
        )
        self.closed = False

    def close(self):
        self.closed = True


def test_production_app_exposes_only_metadata_and_closes_shared_surface():
    runtime = _ClosedRuntime()
    app_instance = api._production_app(runtime)
    assert app_instance.state._state == {
        "runtime_metadata": runtime.metadata
    }
    app_instance.state.runtime_metadata = "tampered"

    with TestClient(app_instance) as client:
        health = client.get("/health")
        responses = [
            client.post("/commit", json={"not": "validated"}),
            client.post("/review/accept"),
            client.get("/records/anything"),
            client.get("/views/passport/anything"),
        ]

    assert health.json()["runtime"] == runtime.metadata.as_dict()
    assert runtime.closed
    assert {response.status_code for response in responses} == {503}
    assert {
        response.json()["detail"]["reasonCode"] for response in responses
    } == {"TENANT_BOUNDARY_BLOCKED"}


def test_application_is_not_published_after_startup_failure(monkeypatch):
    events = []

    class ConfigSource:
        @classmethod
        def from_env(cls):
            events.append("config")
            return object()

    monkeypatch.setattr(api, "RuntimeConfig", ConfigSource)
    monkeypatch.setattr(
        api,
        "build_application_runtime",
        lambda _config: (
            events.append("build")
            or (_ for _ in ()).throw(RuntimeStartupError("refused"))
        ),
    )
    monkeypatch.setattr(
        api,
        "_production_app",
        lambda _runtime: events.append("publish"),
    )

    with pytest.raises(RuntimeStartupError, match="refused"):
        api.create_app()

    assert events == ["config", "build"]
