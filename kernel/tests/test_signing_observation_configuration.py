"""S1-11 early, pure whole-runtime H1 support profile acceptance."""
from __future__ import annotations

import builtins
import os
import socket
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from psycopg.conninfo import conninfo_to_dict

from kernel import api, application_runtime
from kernel.runtime_config import RuntimeConfig, RuntimeConfigurationError
from kernel.signing_authority_io import (
    SigningObservationConfigError, prepare_signing_conninfo,
)
from kernel.tests.test_application_runtime import _config, _environment
from kernel.tests._signing_support import connected_test_dsn


BASE = "dbname=ofarm user=ofarm_app password=fixture sslmode=disable gssencmode=disable"


@pytest.fixture(autouse=True)
def no_pg_environment(monkeypatch):
    for name in os.environ:
        if name.startswith("PG"):
            monkeypatch.delenv(name)


@pytest.mark.parametrize("route", (
    "host=127.0.0.1 port=5432",
    "host=::1 port=5432",
    "host='/tmp/signing socket' port=5432",
    "host=signing.test hostaddr=127.0.0.1 port=5432",
))
def test_explicit_single_routes_are_frozen_without_io(monkeypatch, route):
    before = dict(os.environ)
    def forbidden(*_args, **_kwargs):
        pytest.fail("pure H1 preflight attempted file/network I/O")
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(os, "open", forbidden)
        patch.setattr(socket, "getaddrinfo", forbidden)
        patch.setattr(socket, "socket", forbidden)
        frozen = prepare_signing_conninfo(f"{route} {BASE}")
    values = conninfo_to_dict(frozen.decode())
    assert values["host"] == conninfo_to_dict(route)["host"]
    assert values["port"] == "5432"
    assert values["password"] == "fixture"
    assert os.environ == before


def test_uri_route_preserves_paired_tls_hostname_and_credentials():
    dsn = (
        "postgresql://ofarm_app:fixture@signing.test:5432/ofarm?"
        "hostaddr=127.0.0.1&sslmode=verify-full&gssencmode=disable&"
        "sslrootcert=/tmp/fixture-ca.pem&sslcertmode=disable"
    )
    values = conninfo_to_dict(prepare_signing_conninfo(dsn).decode())
    assert values["host"] == "signing.test"
    assert values["hostaddr"] == "127.0.0.1"
    assert values["sslmode"] == "verify-full"
    assert values["sslrootcert"] == "/tmp/fixture-ca.pem"
    assert values["password"] == "fixture"


@pytest.mark.parametrize("route", (
    "", "host=localhost port=5432", "host=127.0.0.1", "host='' port=5432",
    "host=127.0.0.1,127.0.0.2 port=5432", "host=127.0.0.1 port=5432,5433",
    "hostaddr=127.0.0.1,127.0.0.2 port=5432", "service=signing",
    "host=127.0.0.1 hostaddr=127.0.0.2 port=5432",
    "host=relative/socket port=5432", "host=127.0.0.1 port=0",
))
def test_unsupported_route_refuses_without_dependency_creation(monkeypatch, route):
    events = []
    config = replace(_config(), pg_dsn=f"{route} {BASE}")
    def forbidden(*_args, **_kwargs):
        events.append("I/O")
        raise AssertionError("startup crossed pure preflight")
    for name in (
        "require_deployment_image_digest", "_connection_factory",
        "PrincipalBindingResolver", "ProductionOidcVerifier", "SigningEvidenceVerifier",
        "create_tenant_connection_pool", "build_pretenant_audit_runtime",
    ):
        monkeypatch.setattr(application_runtime, name, forbidden)
    monkeypatch.setattr(application_runtime.httpx, "Client", forbidden)
    monkeypatch.setattr(application_runtime.kms_v1, "KeyManagementServiceClient", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    with pytest.raises(RuntimeConfigurationError) as raised:
        application_runtime.build_application_runtime(config)
    assert events == []
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None or isinstance(raised.value.__context__, SigningObservationConfigError)
    assert "fixture" not in str(raised.value)


@pytest.mark.parametrize("option", (
    "service=signing", "passfile=file:///tmp/passwords",
    "sslmode=require sslcertmode=require sslkey=/tmp/key",
    "gssencmode=prefer", "gssencmode=require",
    "require_auth=gss", "require_auth=oauth", "oauth_issuer=https://issuer.test",
))
def test_external_credential_or_uncertain_facility_refuses(option):
    with pytest.raises(SigningObservationConfigError):
        prepare_signing_conninfo(f"host=127.0.0.1 port=5432 {BASE} {option}")


@pytest.mark.parametrize("name,value", (
    ("PGSERVICE", "hidden"), ("PGSERVICEFILE", "/tmp/service"),
    ("PGHOSTADDR", "127.0.0.2"), ("PGREQUIREAUTH", "gss"),
))
def test_hidden_environment_facilities_are_not_silently_expanded(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    before = dict(os.environ)
    with pytest.raises(SigningObservationConfigError):
        prepare_signing_conninfo(f"host=127.0.0.1 port=5432 {BASE}")
    assert os.environ == before


def test_missing_password_and_tls_auth_defaults_are_not_external_fallbacks():
    # An omitted password may trigger ~/.pgpass; omitted TLS settings may trigger
    # client certificates/private keys or other libpq ambient facilities.
    with pytest.raises(SigningObservationConfigError):
        prepare_signing_conninfo("host=127.0.0.1 port=5432 dbname=ofarm user=ofarm_app")


def test_create_app_refuses_static_route_before_fastapi_or_files(monkeypatch):
    values = _environment()
    values["OFARM_PG_DSN"] = f"host=dns-only.test port=5432 {BASE}"
    monkeypatch.setattr("kernel.runtime_config.os.environ", values)
    events = []
    def forbidden(*_args, **_kwargs):
        events.append("created")
        pytest.fail("static configuration created an application or dependency")
    monkeypatch.setattr(api, "FastAPI", forbidden)
    monkeypatch.setattr(application_runtime.httpx, "Client", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    with pytest.raises(RuntimeConfigurationError):
        api.create_app()
    assert events == []
    # The generic syntax parser remains independently usable for this valid DSN.
    assert RuntimeConfig.from_env().pg_dsn == values["OFARM_PG_DSN"]


@pytest.mark.parametrize("name,value", (
    ("PGHOST", "remote.test"), ("PGPORT", "9999"), ("PGGSSENCMODE", "require"),
))
def test_explicit_parameters_cannot_be_overridden_by_ambient_defaults(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    before = dict(os.environ)
    values = conninfo_to_dict(prepare_signing_conninfo(
        f"host=127.0.0.1 port=5432 {BASE}",
    ).decode())
    assert values["host"] == "127.0.0.1"
    assert values["port"] == "5432"
    assert values["gssencmode"] == "disable"
    assert os.environ == before


@pytest.mark.parametrize("option", (
    "sslmode=require sslkey=pkcs11:fixture sslpassword=fixture",
    "sslmode=require sslkey=engine:fixture sslpassword=fixture",
    "requirepeer=fixture", "sslkeylogfile=/tmp/fixture-keylog",
))
def test_external_tls_key_engine_peer_lookup_and_keylog_facilities_refuse(option):
    with pytest.raises(SigningObservationConfigError):
        prepare_signing_conninfo(f"host=127.0.0.1 port=5432 {BASE} {option}")


def test_local_credentials_and_noninteractive_key_password_are_preserved():
    dsn = (
        f"host=signing.test hostaddr=127.0.0.1 port=5432 {BASE} "
        "sslmode=verify-full sslkey=/tmp/fixture-key.pem "
        "sslcert=/tmp/fixture-cert.pem sslrootcert=/tmp/fixture-ca.pem "
        "passfile=/tmp/fixture-passfile sslpassword=fixture-passphrase"
    )
    values = conninfo_to_dict(prepare_signing_conninfo(dsn).decode())
    for key, value in conninfo_to_dict(dsn).items():
        assert values[key] == value


def test_implicit_config_files_are_frozen_and_preparation_is_idempotent():
    first = prepare_signing_conninfo(f"host=127.0.0.1 port=5432 {BASE}")
    assert prepare_signing_conninfo(first.decode()) == first
    values = conninfo_to_dict(first.decode())
    for name in ("passfile", "sslkey", "sslcert", "sslrootcert", "sslcrl"):
        assert Path(values[name]).is_absolute()
    assert set(values["require_auth"].split(",")) <= {"none", "password", "md5", "scram-sha-256"}


@pytest.mark.parametrize("host,address", (
    ("localhost", "127.0.0.1"),
    ("database.fixture.test", "::1"),
    ("/tmp/fixture-socket", ""),
))
def test_fixture_pins_only_the_observed_address_and_preserves_identity_and_tls(
    monkeypatch, host, address,
):
    dsn = (
        f"host={host} port=6543 user=fixture dbname=fixture password=fixture "
        "sslmode=verify-full sslcertmode=disable gssencmode=disable "
        "sslrootcert=/tmp/fixture-ca.pem"
    )
    original = conninfo_to_dict(dsn)
    assert "hostaddr" not in original
    def forbidden(*_args, **_kwargs):
        pytest.fail("fixture must reuse the connected address, not resolve a new endpoint")
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    if address:
        with pytest.raises(SigningObservationConfigError):
            prepare_signing_conninfo(dsn)
    connection = SimpleNamespace(info=SimpleNamespace(hostaddr=address))
    explicit = connected_test_dsn(dsn, connection)
    expected = {**original, **({"hostaddr": address} if address else {})}
    assert conninfo_to_dict(explicit) == expected
    frozen = conninfo_to_dict(prepare_signing_conninfo(explicit).decode())
    assert all(frozen[name] == value for name, value in expected.items())
