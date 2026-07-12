"""M2 G4 — OIDC principal binding over the HTTP surface.

Engineering tests, NOT part of the named conformance suite. They pin the OIDC
principal-derivation: a VERIFIED bearer token yields the Party transport
principal (replacing the X-Acting-Party dev header), the actor-binding contract
and default-deny are preserved, and authority is unchanged — a role claim alone
never authorizes (authority still comes only from grants, D4). The verifier is
the zero-dependency HS256 dev/conformance path; RS256/JWKS (Keycloak) is a
deliberate NotImplemented production path with no silent fallback. All identifiers
fictional.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from kernel import demo
from kernel.api import create_app
from kernel.auth_oidc import OidcConfig, OidcError, issue_dev_token


def uid():
    return uuid.uuid4().hex[:8]

ISSUER = "https://keycloak.example/realms/ofarm-dev"
AUDIENCE = "ofarm2-kernel"
SECRET = "dev-conformance-secret-not-production"


def _cfg(**over):
    kw = dict(issuer=ISSUER, audience=AUDIENCE, algorithm="HS256",
              hs256_secret=SECRET, roles_claim="roles")
    kw.update(over)
    return OidcConfig(**kw)


def _client(store, cfg=None):
    return TestClient(create_app(store, oidc=cfg if cfg is not None else _cfg()))


def _token(sub, *, secret=SECRET, iss=ISSUER, aud=AUDIENCE, exp_delta=3600,
           nbf_delta=None, roles=None):
    now = int(time.time())
    claims = {"sub": sub, "iss": iss, "aud": aud, "iat": now, "exp": now + exp_delta}
    if nbf_delta is not None:
        claims["nbf"] = now + nbf_delta
    if roles is not None:
        claims["roles"] = roles
    return issue_dev_token(claims, secret=secret)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _encode_json_segment(value: dict) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(value, separators=(",", ":")).encode(),
    ).rstrip(b"=").decode()


def _raw_token(header: dict, payload: dict, signature: str = "x") -> str:
    return (
        f"{_encode_json_segment(header)}."
        f"{_encode_json_segment(payload)}.{signature}"
    )


def _signed(header: dict, payload: dict, secret: str = SECRET) -> str:
    """A correctly HS256-SIGNED token with a CUSTOM header (e.g. carrying crit/b64)."""
    h = _encode_json_segment(header)
    p = _encode_json_segment(payload)
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{h}.{p}.{sig}"


# ---------------------------------------------------------------------------
# the principal-binding contract over a verified token
# ---------------------------------------------------------------------------

def test_g4_valid_token_binds_principal_and_commits(store):
    client = _client(store)
    sub = demo.spray_submission(f"g4-ok:{uid()}", erp_id=f"erp:g4.ok.{uid()}", actor_ref=demo.FARMER)
    r = client.post("/commit", json={"submission": sub},
                    headers=_bearer(_token(demo.FARMER)))
    assert r.status_code == 200 and r.json()["decisionOutcome"]


def test_g4_token_principal_mismatch_refuses(store):
    client = _client(store)
    sub = demo.spray_submission("g4-mismatch-1", erp_id="erp:g4.mm", actor_ref=demo.FARMER)
    # token says WORKER, body claims FARMER -> the binding refuses before the pipeline
    r = client.post("/commit", json={"submission": sub}, headers=_bearer(_token(demo.WORKER)))
    assert r.status_code == 403
    assert r.json()["detail"]["reasonCode"] == "ACTOR_BINDING_UNRESOLVED"


def test_g4_role_claim_alone_does_not_authorize(store):
    # a token for ADVISOR (who holds REVIEW_ACCEPT but NOT ASSERT_OPERATION_CLAIM)
    # carrying privileged role claims must NOT authorize a spray — authority comes
    # only from grants (D4); roles map to RoleAssignment, never a grant.
    client = _client(store)
    sub = demo.spray_submission("g4-roleclaim-1", erp_id="erp:g4.role", actor_ref=demo.ADVISOR)
    r = client.post("/commit", json={"submission": sub},
                    headers=_bearer(_token(demo.ADVISOR, roles=["operator", "admin", "farm-owner"])))
    assert r.status_code == 200, "the binding passes (principal == actor); the gate decides"
    result = r.json()
    assert result["decisionOutcome"] != "PROMOTE_ACCEPTED", \
        "a role claim must not authorize an action that lacks a grant"
    assert "AUTHORITY_DENIED" in json.dumps(result), "authority denied — the role did not grant it"


# ---------------------------------------------------------------------------
# default deny: absent / invalid token never reaches farm-scoped truth
# ---------------------------------------------------------------------------

def test_g4_absent_token_denied(store):
    client = _client(store)
    sub = demo.spray_submission("g4-noauth-1", erp_id="erp:g4.noauth", actor_ref=demo.FARMER)
    assert client.post("/commit", json={"submission": sub}).status_code == 401
    # the X-Acting-Party header does NOT authenticate when OIDC is enabled
    assert client.post("/commit", json={"submission": sub},
                       headers={"x-acting-party": demo.FARMER}).status_code == 401
    # read surface is likewise default-deny without a token
    assert client.get(f"/records/{demo.FARM}").status_code == 401


def test_g4_invalid_tokens_denied(store):
    client = _client(store)
    sub = demo.spray_submission("g4-bad-1", erp_id="erp:g4.bad", actor_ref=demo.FARMER)

    def denied(token):
        r = client.post("/commit", json={"submission": sub}, headers=_bearer(token))
        assert r.status_code == 401, f"token must be rejected: {token[:24]}..."

    denied(_token(demo.FARMER, secret="wrong-secret"))            # bad signature
    denied(_token(demo.FARMER, exp_delta=-10))                    # expired
    denied(_token(demo.FARMER, nbf_delta=3600))                   # not yet valid
    denied(_token(demo.FARMER, iss="https://evil.example"))       # wrong issuer
    denied(_token(demo.FARMER, aud="some-other-audience"))        # wrong audience
    denied("not.a.jwt")                                           # malformed structure
    denied("@@@.@@@.@@@")                                         # malformed base64url
    # alg=none (a signed-looking but unsigned token) is rejected outright
    denied(_raw_token({"alg": "none", "typ": "JWT"},
                      {"sub": demo.FARMER, "iss": ISSUER, "aud": AUDIENCE,
                       "exp": int(time.time()) + 3600}))
    # a token missing required claims
    denied(issue_dev_token({"iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 3600},
                           secret=SECRET))                        # no sub


def test_g4_rs256_is_not_implemented_no_fallback(store):
    # production RS256/JWKS is a deliberate NotImplemented path — a token is NOT
    # silently verified by HS256 even if it would pass HS256
    cfg = _cfg(algorithm="RS256")
    client = _client(store, cfg)
    sub = demo.spray_submission("g4-rs256-1", erp_id="erp:g4.rs", actor_ref=demo.FARMER)
    r = client.post("/commit", json={"submission": sub}, headers=_bearer(_token(demo.FARMER)))
    assert r.status_code == 401
    # and the verifier itself raises a clear NotImplemented-style error
    try:
        cfg.verify(_token(demo.FARMER))
        assert False, "RS256 verify must raise"
    except OidcError as exc:
        assert "RS256" in str(exc) and "not implemented" in str(exc).lower()
        assert "fallback" in str(exc).lower()


# ---------------------------------------------------------------------------
# the development/conformance X-Acting-Party shim (OIDC disabled) is unchanged
# ---------------------------------------------------------------------------

def test_g4_shim_mode_uses_x_acting_party_when_oidc_disabled(store):
    client = TestClient(create_app(store, oidc=None))   # forced shim
    sub = demo.spray_submission("g4-shim-1", erp_id="erp:g4.shim", actor_ref=demo.FARMER)
    bound = client.post("/commit", json={"submission": sub}, headers={"x-acting-party": demo.FARMER})
    assert bound.status_code == 200 and bound.json()["decisionOutcome"]
    mismatch = client.post("/commit", json={"submission": sub}, headers={"x-acting-party": demo.WORKER})
    assert mismatch.status_code == 403 and mismatch.json()["detail"]["reasonCode"] == "ACTOR_BINDING_UNRESOLVED"
    assert client.post("/commit", json={"submission": sub}).status_code == 401   # no principal


# ---------------------------------------------------------------------------
# verifier unit checks (the security boundary), direct
# ---------------------------------------------------------------------------

def test_g4_verifier_returns_party_and_roles_separately(store):
    claims = _cfg().verify(_token(demo.FARMER, roles=["operator"]))
    assert claims["partyRef"] == demo.FARMER
    assert claims["roles"] == ["operator"]   # surfaced as RoleAssignment-level, never authority


def test_g4_application_rejects_post_start_oidc_config_mutation(store):
    cfg = _cfg()
    assert not hasattr(cfg, "__dict__")
    client = TestClient(
        create_app(store, oidc=cfg), raise_server_exceptions=False)
    object.__setattr__(cfg, "hs256_secret", "attacker-controlled-secret")
    forged = _token(
        demo.FARMER, secret="attacker-controlled-secret")

    response = client.get(
        f"/records/{demo.FARMER}", headers=_bearer(forged))
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}


def test_g4_oidc_config_rejects_equal_but_behavioral_subclasses():
    class BehavioralString(str):
        def encode(self, *_args, **_kwargs):
            return b"attacker-controlled-secret"

    with pytest.raises(TypeError, match="exact string"):
        OidcConfig(
            issuer=ISSUER,
            audience=AUDIENCE,
            hs256_secret=BehavioralString(SECRET),
        )


def test_g4_application_rejects_equal_behavioral_oidc_mutation(store):
    class BehavioralSecret(str):
        def encode(self, *_args, **_kwargs):
            return b"attacker-controlled-secret"

    cfg = _cfg()
    client = TestClient(
        create_app(store, oidc=cfg), raise_server_exceptions=False)
    poisoned = BehavioralSecret(SECRET)
    assert poisoned == SECRET
    object.__setattr__(cfg, "hs256_secret", poisoned)
    forged = _token(
        demo.FARMER, secret="attacker-controlled-secret")

    response = client.get(
        f"/records/{demo.FARMER}", headers=_bearer(forged))
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}


def test_g4_application_rejects_oidc_helper_replacement(
        store, monkeypatch):
    import kernel.auth_oidc as oidc_runtime

    called = False

    def hostile_verify(*_args, **_kwargs):
        nonlocal called
        called = True
        return {"sub": demo.FARMER}

    client = _client(store)
    monkeypatch.setattr(oidc_runtime, "_verify_hs256", hostile_verify)
    response = client.get(
        f"/records/{demo.FARMER}",
        headers=_bearer(_token(demo.FARMER)),
    )
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
    assert called is False


def test_g4_verifier_rejects_retained_helper_alias_replacement(monkeypatch):
    import kernel.auth_oidc as oidc_runtime

    called = False

    def hostile_verify(*_args, **_kwargs):
        nonlocal called
        called = True
        return {
            "sub": "party:forged",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": int(time.time()) + 3600,
        }

    monkeypatch.setattr(
        oidc_runtime, "_RETAINED_VERIFY_HS256", hostile_verify)
    with pytest.raises(OidcError, match="runtime composition changed"):
        _cfg().verify("not.a.token")
    assert called is False


def test_g4_non_finite_numericdate_is_fail_closed_401(store):
    # PR #16 hostile B1: NaN / Infinity exp or nbf must FAIL CLOSED (401), never
    # crash int()/the endpoint into a 500. The verifier raises OidcError, not
    # ValueError/OverflowError.
    client = _client(store)
    sub = demo.spray_submission(f"g4-nan:{uid()}", erp_id=f"erp:g4.nan.{uid()}", actor_ref=demo.FARMER)
    now = int(time.time())
    for bad in (float("nan"), float("inf"), float("-inf")):
        tok = issue_dev_token({"sub": demo.FARMER, "iss": ISSUER, "aud": AUDIENCE,
                               "iat": now, "exp": bad}, secret=SECRET)
        assert client.post("/commit", json={"submission": sub}, headers=_bearer(tok)).status_code == 401, \
            f"exp={bad} must fail closed (401), never 500"
        with pytest.raises(OidcError):
            _cfg().verify(tok)
    nbf_nan = issue_dev_token({"sub": demo.FARMER, "iss": ISSUER, "aud": AUDIENCE,
                               "exp": now + 3600, "nbf": float("nan")}, secret=SECRET)
    assert client.post("/commit", json={"submission": sub}, headers=_bearer(nbf_nan)).status_code == 401


@pytest.mark.parametrize(
    "huge", (1 << 4096, -(1 << 4096)),
    ids=("positive", "negative"),
)
@pytest.mark.parametrize("claim_name", ("exp", "nbf"))
def test_g4_huge_integer_numericdate_is_fail_closed_oidc_error(
        store, huge, claim_name):
    now = int(time.time())
    claims = {
        "sub": demo.FARMER,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": now + 3600,
    }
    claims[claim_name] = huge
    token = issue_dev_token(claims, secret=SECRET)

    with pytest.raises(OidcError, match="signed-64-bit NumericDate"):
        _cfg().verify(token)
    response = _client(store).get(
        f"/records/{demo.FARMER}", headers=_bearer(token))
    assert response.status_code == 401


def test_g4_noncanonical_base64url_segment_rejected_even_if_signed(store):
    # PR #16 hostile B2: compact-JWS segments are UNPADDED base64url. A canonically-
    # PADDED payload segment (non-canonical for JWS) decodes fine on a lenient
    # verifier and, RE-SIGNED over that exact padded form with the real secret,
    # would be accepted. The strict verifier rejects it on the alphabet check ('=').
    header_b64, payload_b64, _ = _token(demo.FARMER).split(".")
    padded = payload_b64 + ("=" * (-len(payload_b64) % 4) or "=")   # non-canonical '=' present
    sig = base64.urlsafe_b64encode(
        hmac.new(SECRET.encode(), f"{header_b64}.{padded}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    forged = f"{header_b64}.{padded}.{sig}"
    assert "=" in padded
    with pytest.raises(OidcError):
        _cfg().verify(forged)
    sub = demo.spray_submission(f"g4-nc:{uid()}", erp_id=f"erp:g4.nc.{uid()}", actor_ref=demo.FARMER)
    assert _client(store).post("/commit", json={"submission": sub},
                               headers=_bearer(forged)).status_code == 401


def test_g4_verifier_rejects_tampered_payload(store):
    token = _token(demo.FARMER)
    header_b64, payload_b64, sig = token.split(".")
    # swap in a different subject without re-signing
    forged_payload = base64.urlsafe_b64encode(
        json.dumps({"sub": demo.WORKER, "iss": ISSUER, "aud": AUDIENCE,
                    "exp": int(time.time()) + 3600}, separators=(",", ":")).encode()).rstrip(b"=").decode()
    try:
        _cfg().verify(f"{header_b64}.{forged_payload}.{sig}")
        assert False, "tampered payload must fail signature verification"
    except OidcError as exc:
        assert "signature" in str(exc).lower()


# ---------------------------------------------------------------------------
# hostile re-review (PR #16): crit/b64 headers; env-config determinism;
# unrecorded token subject is not a principal
# ---------------------------------------------------------------------------

def test_g4_critical_jose_headers_rejected_even_if_signed(store):
    # PR #16 hostile B1: this minimal verifier understands NO critical JOSE header
    # extensions, so crit / b64 must be rejected even when correctly HS256-signed.
    client = _client(store)
    sub = demo.spray_submission(f"g4-crit:{uid()}", erp_id=f"erp:g4.crit.{uid()}", actor_ref=demo.FARMER)
    now = int(time.time())
    claims = {"sub": demo.FARMER, "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 3600}
    for header in ({"alg": "HS256", "crit": ["exp"]},
                   {"alg": "HS256", "b64": False},
                   {"alg": "HS256", "b64": False, "crit": ["b64"]}):
        tok = _signed(header, claims)
        assert client.post("/commit", json={"submission": sub}, headers=_bearer(tok)).status_code == 401, \
            f"critical/unsupported header {header} must be rejected"
        with pytest.raises(OidcError):
            _cfg().verify(tok)


def test_g4_from_env_default_reads_oidc_config_deterministically(store, monkeypatch):
    # PR #16 hostile B2: create_app(store) (default _FROM_ENV) reads OIDC from the
    # environment — with OFARM_OIDC_* set it enables OIDC, cleared it is the shim.
    # (Conformance shim tests force oidc=None, so they are deterministic regardless.)
    monkeypatch.setenv("OFARM_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OFARM_OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("OFARM_OIDC_HS256_SECRET", SECRET)
    monkeypatch.setenv("OFARM_OIDC_ROLES_CLAIM", "roles")
    enabled = TestClient(create_app(store))   # _FROM_ENV -> OIDC enabled
    sub = demo.spray_submission(f"g4-env:{uid()}", erp_id=f"erp:g4.env.{uid()}", actor_ref=demo.FARMER)
    assert enabled.post("/commit", json={"submission": sub},
                        headers={"x-acting-party": demo.FARMER}).status_code == 401  # header != auth
    assert enabled.post("/commit", json={"submission": sub},
                        headers=_bearer(_token(demo.FARMER))).status_code == 200
    monkeypatch.delenv("OFARM_OIDC_ISSUER")
    monkeypatch.delenv("OFARM_OIDC_AUDIENCE")
    shim = TestClient(create_app(store))      # _FROM_ENV -> no issuer/aud -> shim
    sub2 = demo.spray_submission(f"g4-env2:{uid()}", erp_id=f"erp:g4.env2.{uid()}", actor_ref=demo.FARMER)
    assert shim.post("/commit", json={"submission": sub2},
                     headers={"x-acting-party": demo.FARMER}).status_code == 200


def test_g4_unrecorded_token_subject_is_not_a_principal(store):
    # PR #16 hostile B3: a valid token from the configured issuer whose sub is NOT a
    # recorded active Party must NOT become a principal — it cannot read even public
    # artifacts (the principal check fires before the read).
    client = _client(store)
    rec_id = "referencesnapshot:si.uvhvvr.ffs-reg.public-test"   # a public-artifact kind id
    bad = client.get(f"/records/{rec_id}", headers=_bearer(_token("party:not.in.store")))
    assert bad.status_code == 401 and bad.json()["detail"]["reasonCode"] == "AUTHORITY_DENIED"
    # a recorded active party with a valid token passes the principal check (not 401)
    ok = client.get(f"/records/{rec_id}", headers=_bearer(_token(demo.FARMER)))
    assert ok.status_code != 401, "a recorded active party is a valid principal"
    # and an inactive/unknown party in shim mode is likewise not a principal
    shim = TestClient(create_app(store, oidc=None))
    assert shim.get(f"/records/{rec_id}", headers={"x-acting-party": "party:ghost"}).status_code == 401
