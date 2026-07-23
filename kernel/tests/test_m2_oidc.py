"""M2 G4 — OIDC principal binding over the HTTP surface.

Engineering tests, NOT part of the named conformance suite. They pin the OIDC
principal-derivation: a VERIFIED bearer token yields the Party transport
principal (replacing the X-Acting-Party dev header), the actor-binding contract
and default-deny are preserved, and authority is unchanged — a role claim alone
never authorizes (authority still comes only from grants, D4). The verifier is
the explicit zero-dependency HS256 test path; the maintained RS256/JWKS
production verifier is exercised separately and there is no silent fallback.
All identifiers are fictional.
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

ISSUER = "https://keycloak.example/realms/ofarm-dev"
AUDIENCE = "ofarm2-kernel"
SECRET = "dev-conformance-secret-not-production"


def uid():
    return uuid.uuid4().hex[:8]


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


def _encode_json_segment(document: dict) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(document, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()


def _raw_token(header: dict, payload: dict, signature: str = "x") -> str:
    return (
        f"{_encode_json_segment(header)}."
        f"{_encode_json_segment(payload)}."
        f"{signature}"
    )


def _signed(header: dict, payload: dict, secret: str = SECRET) -> str:
    """A correctly HS256-SIGNED token with a CUSTOM header (e.g. carrying crit/b64)."""
    h, p = _encode_json_segment(header), _encode_json_segment(payload)
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


def test_g4_local_hs256_config_refuses_rs256_without_fallback(store):
    # The local fixture verifier cannot become a production verifier by changing
    # an algorithm string, and never falls back to HS256.
    cfg = _cfg(algorithm="RS256")
    client = _client(store, cfg)
    sub = demo.spray_submission("g4-rs256-1", erp_id="erp:g4.rs", actor_ref=demo.FARMER)
    r = client.post("/commit", json={"submission": sub}, headers=_bearer(_token(demo.FARMER)))
    assert r.status_code == 401
    try:
        cfg.verify(_token(demo.FARMER))
        assert False, "RS256 verify must raise"
    except OidcError as exc:
        assert exc.internal_detail == "test algorithm differs"


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
        assert "signature" in exc.internal_detail.lower()


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
