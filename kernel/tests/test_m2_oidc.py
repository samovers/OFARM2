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
import json
import time
import uuid


def uid():
    return uuid.uuid4().hex[:8]

from fastapi.testclient import TestClient

from kernel import demo
from kernel.api import create_app
from kernel.auth_oidc import OidcConfig, OidcError, issue_dev_token

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


def _raw_token(header: dict, payload: dict, signature: str = "x") -> str:
    enc = lambda d: base64.urlsafe_b64encode(
        json.dumps(d, separators=(",", ":")).encode()).rstrip(b"=").decode()
    return f"{enc(header)}.{enc(payload)}.{signature}"


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
