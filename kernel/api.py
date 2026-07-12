"""FastAPI surface — the platform's governed front door over HTTP.

Refusals are data, not transport errors: a processed commit always returns
its CommitIngressResult envelope (problems inside, reason codes from the
registry); malformed requests are 422s. Read surfaces enforce default deny
per request — there is no unauthenticated path to farm-scoped truth.
"""
from __future__ import annotations

import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import auth_oidc, config, context
from .contracts import ContractViolation, canonical_json
from .problems import runtime_problem
from .gates import GatePipeline
from .runtime_bundle import (
    JSON_CANONICALIZATION,
    RAW_CANONICALIZATION,
    sha256_bytes,
)
from .store import Store
from .views import OutputGenerator

# create_app default: resolve the OIDC verifier from the environment (the uvicorn
# --factory entrypoint takes no args). Pass oidc=None to FORCE the development/
# conformance X-Acting-Party shim; pass an OidcConfig to verify tokens.
_FROM_ENV = object()


class CommitBody(BaseModel):
    submission: dict


class FreezeBody(BaseModel):
    farmRef: str
    windowStart: str
    windowEnd: str


class ReviewContestBody(BaseModel):
    farmRef: str
    # the in-force AcceptedEventConsequence being disputed (not an assertion)
    consequenceRef: str
    rationale: str
    evidenceRefs: list[str] = []
    idempotencyKey: str | None = None


class ReviewAcceptBody(BaseModel):
    farmRef: str
    assertionRef: str
    # acceptance is a governed RESOLUTION, never a bare pointer: the
    # rationale is mandatory, and routed insufficiencies additionally
    # require reviewer-attached durable evidence (gate-enforced)
    rationale: str
    evidenceRefs: list[str] = []
    idempotencyKey: str | None = None


def create_app(store: Store | None = None, *, oidc=_FROM_ENV) -> FastAPI:
    app = FastAPI(
        title="OFARM2 Kernel (M1)",
        description="Implementation and conformance packaging profile — not OFARM "
                    "law. Claims record-keeping completeness only; never "
                    "current-compliance, certification, or production readiness.",
        version="m1.0",
    )
    app.state.store = store or Store()
    app.state.store.migrate()
    context.bootstrap(app.state.store)
    app.state.pipeline = GatePipeline(app.state.store)
    app.state.outputs = OutputGenerator(app.state.store)
    app.state.oidc = config.oidc_config_from_env() if oidc is _FROM_ENV else oidc

    def _deny(title: str, detail: str, pid: str):
        raise HTTPException(status_code=401, detail=runtime_problem(
            "AUTHORITY_DENIED", title, detail, problem_id=pid))

    def get_principal(authorization: str | None = Header(None),
                      x_acting_party: str | None = Header(None)) -> str:
        """The transport principal (a recorded, ACTIVE Party ref). With OIDC
        configured (M2 G4) it comes ONLY from a verified bearer token; otherwise the
        development/conformance X-Acting-Party header IS the principal (NOT production
        auth — profile_si_ffs/UNSUPPORTED_SURFACES.md). Either way the binding
        contract is identical, an absent/invalid principal is a default-deny refusal,
        and the principal must resolve to a recorded active Party — an issuer subject
        that is not a known active party never becomes a principal (no public-artifact
        read by an arbitrary token subject, PR #16 hostile B3)."""
        oidc_cfg = app.state.oidc
        if oidc_cfg is None:
            if not x_acting_party:
                _deny("No transport principal",
                      "no X-Acting-Party principal presented; default deny",
                      "problem:api-no-principal")
            principal = x_acting_party
        else:
            if not authorization or not authorization.lower().startswith("bearer "):
                _deny("No bearer token",
                      "no Authorization: Bearer token presented; default deny (the "
                      "X-Acting-Party header does not authenticate when OIDC is enabled)",
                      "problem:api-no-token")
            try:
                principal = app.state.oidc.verify(authorization.split(" ", 1)[1].strip())["partyRef"]
            except auth_oidc.OidcError as exc:
                _deny("Token verification failed", str(exc), "problem:api-token-invalid")
        rec = app.state.store.get_record(principal)
        if (rec is None or rec["record_kind"] != "ofarm.party.v0.1"
                or rec["payload"].get("partyState") != "ACTIVE"):
            _deny("Principal is not an active Party",
                  f"the transport principal {principal} is not a recorded active Party; "
                  "default deny", "problem:api-principal-not-party")
        return principal

    app.state.get_principal = get_principal

    def _receipt(
            payload: object, *, status_code: int = 200,
            headers: dict[str, str] | None = None,
            head_request: bool = False) -> Response:
        """Emit, hash, and return one exact canonical JSON byte sequence.

        Returning a Response (rather than a Python object) is intentional:
        FastAPI must not perform a second Pydantic/JSON encoding pass after the
        receipt digest has been calculated. HTTP never delivers a response body
        for HEAD, so a handled HEAD error explicitly emits and hashes empty
        exact bytes instead of hashing the suppressed JSON representation.
        """
        encoded_payload = jsonable_encoder(payload)
        canonical_bytes = canonical_json(encoded_payload).encode("utf-8")
        delivered_bytes = b"" if head_request else canonical_bytes
        protected_headers = {
            "content-length",
            "content-type",
            "x-ofarm-runtime-bundle-digest",
            "x-ofarm-receipt-payload-digest",
            "x-ofarm-receipt-canonicalization",
        }
        forwarded_headers = {
            name: value for name, value in (headers or {}).items()
            if name.lower() not in protected_headers
        }
        response = Response(
            content=delivered_bytes,
            status_code=status_code,
            headers=forwarded_headers,
        )
        if head_request:
            # Content-Length on HEAD describes the corresponding GET
            # representation, not transferred bytes. This method-level error
            # has no such safely equivalent representation, so omit it.
            del response.headers["Content-Length"]
        response.headers["Content-Type"] = "application/json; charset=utf-8"
        response.headers["X-OFARM-Runtime-Bundle-Digest"] = \
            app.state.store.runtime_bundle_digest
        response.headers["X-OFARM-Receipt-Payload-Digest"] = \
            sha256_bytes(delivered_bytes)
        response.headers["X-OFARM-Receipt-Canonicalization"] = \
            RAW_CANONICALIZATION if head_request else JSON_CANONICALIZATION
        return response

    @app.exception_handler(StarletteHTTPException)
    async def receipted_http_exception(
            request: Request, exc: StarletteHTTPException):
        return _receipt(
            {"detail": exc.detail},
            status_code=exc.status_code,
            headers=dict(exc.headers or {}),
            head_request=request.method == "HEAD",
        )

    @app.exception_handler(RequestValidationError)
    async def receipted_validation_exception(
            request: Request, exc: RequestValidationError):
        return _receipt(
            {"detail": exc.errors()},
            status_code=422,
            head_request=request.method == "HEAD",
        )

    @app.exception_handler(Exception)
    async def receipted_unhandled_exception(
            request: Request, exc: Exception):
        # Unexpected implementation failures still cross the governed HTTP
        # boundary as exact receipted bytes.  Never expose exception text or a
        # traceback to the caller; operational logging remains the server's
        # responsibility.
        del exc
        return _receipt(
            {"detail": "Internal Server Error"},
            status_code=500,
            head_request=request.method == "HEAD",
        )

    @app.get("/health")
    def health():
        return _receipt({
            "status": "ok",
            "unreachableAuthoritativeRecords":
                app.state.store.unreachable_authoritative_records(),
        })

    @app.post("/commit")
    def commit(body: CommitBody, principal: str = Depends(get_principal)):
        # The transport principal binds to the submitted actor BEFORE the
        # pipeline runs: a body-supplied actingPartyRef is never trusted on its
        # own (hostile review blocker 1). The principal is the OIDC-verified Party
        # when OIDC is configured (M2 G4), else the development/conformance
        # X-Acting-Party header (UNSUPPORTED_SURFACES.md) — the binding contract is
        # identical: the gate's actor is the transport's actor, or it is refused.
        if body.submission.get("actingPartyRef") != principal:
            # full RuntimeProblem shape even at the transport edge; the fixed
            # problemId keeps these pre-pipeline refusals off the in-pipeline
            # problem counter
            raise HTTPException(status_code=403, detail=runtime_problem(
                "ACTOR_BINDING_UNRESOLVED", "Transport principal mismatch",
                "submission.actingPartyRef does not match the transport "
                "principal; body-level actor spoofing is refused",
                problem_id="problem:api-principal-mismatch"))
        try:
            return _receipt(app.state.pipeline.commit(body.submission))
        except (ContractViolation, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    # Package-published, non-personal artifacts: readable by any recorded
    # party. Everything else needs an affirmative farm-scoped read path.
    PUBLIC_ARTIFACT_KINDS = {
        "ofarm.referencesnapshot.v0.1",
        "ofarm.agronomiccodebindingprofile.v0.1",
        "ofarm.packactivationset.v0.1",
        "ofarm.activeartifactset.v0.1",
    }

    def _read_farm_scopes(store, row) -> list[str] | None:
        """Farm scopes governing a record's readability; None = unresolvable.
        Governance/trace records resolve through their declared scope fields
        or their linked records — never default-open."""
        payload = row["payload"]
        farms = [s["scopeRef"] for s in payload.get("anchorScopes", [])
                 if isinstance(s, dict) and s.get("scopeType") == "FARM"]
        for field in ("targetScopes",):
            farms += [s["scopeRef"] for s in payload.get(field, [])
                      if isinstance(s, dict) and s.get("scopeType") == "FARM"]
        ts = payload.get("targetScope")
        if isinstance(ts, dict) and ts.get("scopeType") == "FARM":
            farms.append(ts["scopeRef"])
        tgt = payload.get("target", {})
        if isinstance(tgt, dict):
            sc = tgt.get("scope", {})
            if isinstance(sc, dict) and sc.get("scopeType") == "FARM":
                farms.append(sc["scopeRef"])
        if farms:
            return sorted(set(farms))
        # follow one link hop for boundary records
        for ref_field in ("semanticEventRef", "requestId"):
            ref = payload.get(ref_field)
            if isinstance(ref, str):
                linked = store.get_record(ref)
                if linked is not None and linked["record_id"] != row["record_id"]:
                    resolved = _read_farm_scopes(store, linked)
                    if resolved:
                        return resolved
        return None

    @app.post("/review/accept")
    def review_accept(body: ReviewAcceptBody,
                      principal: str = Depends(get_principal)):
        # the review act is the REVIEWER'S own governed commit: the reviewer
        # IS the transport principal — there is no body-named reviewer field
        # to forge (hostile review blocker 1, second pass)
        submission = {
            "commitClass": "GOVERNANCE_DECISION",
            "ingressChannel": "MANUAL_UI",
            "actingPartyRef": principal,
            "farmRef": body.farmRef,
            "idempotencyKey": body.idempotencyKey
                              or f"review-accept:{uuid.uuid4().hex}",
            "decisionTime": context.now_iso(),
            "reviewTargetAssertionRef": body.assertionRef,
            "reviewRationale": body.rationale,
            "reviewEvidenceRefs": body.evidenceRefs,
            "dominantSemanticConsequence": "review acceptance of a queued claim",
        }
        try:
            return _receipt(app.state.pipeline.commit(submission))
        except (ContractViolation, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.post("/review/reject")
    def review_reject(body: ReviewAcceptBody,
                      principal: str = Depends(get_principal)):
        # the reject act is the REVIEWER'S own governed decline under their own
        # transport principal (M2 G5-2). The endpoint supplies the normalized
        # review-decision pair (REVIEW_REJECT_OR_CONTEST / REJECTED) so the client
        # never passes raw outcome values (docs/REVIEW_DISPUTE_SEMANTICS.md §3.1).
        # Authority is the DISTINCT REVIEW_REJECT_OR_CONTEST action — a principal
        # holding only REVIEW_ACCEPT is denied. The rationale is mandatory;
        # supplied evidence is validated like acceptance's.
        submission = {
            "commitClass": "GOVERNANCE_DECISION",
            "ingressChannel": "MANUAL_UI",
            "actingPartyRef": principal,
            "farmRef": body.farmRef,
            "idempotencyKey": body.idempotencyKey
                              or f"review-reject:{uuid.uuid4().hex}",
            "decisionTime": context.now_iso(),
            "reviewTargetAssertionRef": body.assertionRef,
            "reviewAction": "REVIEW_REJECT_OR_CONTEST",
            "decisionOutcomeState": "REJECTED",
            "reviewRationale": body.rationale,
            "reviewEvidenceRefs": body.evidenceRefs,
            "dominantSemanticConsequence": "review rejection of a queued claim",
        }
        try:
            return _receipt(app.state.pipeline.commit(submission))
        except (ContractViolation, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.post("/review/contest")
    def review_contest(body: ReviewContestBody,
                       principal: str = Depends(get_principal)):
        # a CONTEST opens an append-only dispute against an ALREADY IN-FORCE
        # consequence under the reviewer's own principal (M2 G5-4). The endpoint
        # supplies the normalized pair (REVIEW_REJECT_OR_CONTEST / CONTESTED) and
        # the target consequence ref; authority is the distinct
        # REVIEW_REJECT_OR_CONTEST action; the consequence is flagged (DISPUTE
        # edge) but never edited, and dependent materializations stale (spec §6).
        submission = {
            "commitClass": "GOVERNANCE_DECISION",
            "ingressChannel": "MANUAL_UI",
            "actingPartyRef": principal,
            "farmRef": body.farmRef,
            "idempotencyKey": body.idempotencyKey
                              or f"review-contest:{uuid.uuid4().hex}",
            "decisionTime": context.now_iso(),
            "reviewTargetConsequenceRef": body.consequenceRef,
            "reviewAction": "REVIEW_REJECT_OR_CONTEST",
            "decisionOutcomeState": "CONTESTED",
            "reviewRationale": body.rationale,
            "reviewEvidenceRefs": body.evidenceRefs,
            "dominantSemanticConsequence": "dispute against an in-force consequence",
        }
        try:
            return _receipt(app.state.pipeline.commit(submission))
        except (ContractViolation, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.get("/records/{record_id}")
    def get_record(record_id: str, principal: str = Depends(get_principal)):
        store = app.state.store
        row = store.get_record(record_id)
        if row is None:
            raise HTTPException(status_code=404, detail="no such record")
        payload, kind = row["payload"], row["record_kind"]

        def deny():
            # default deny; distinguish "exists but permission-limited"
            # from "does not exist" (reason-code registry safe-UI rule)
            raise HTTPException(status_code=403, detail=runtime_problem(
                "PERMISSION_REDACTED", "Read not authorized",
                "the record exists but you are not authorized to read it",
                problem_id="problem:api-read-denied"))

        if kind == "ofarm.party.v0.1":
            # a party record is readable by that party alone at this surface
            if payload["partyId"] != principal:
                deny()
        elif kind not in PUBLIC_ARTIFACT_KINDS:
            farm_scopes = _read_farm_scopes(store, row)
            if not farm_scopes:
                deny()  # unresolvable scope never defaults open (Kernel rule 2)
            for farm_ref in farm_scopes:
                access = app.state.outputs.authority.evaluate_read(
                    requesting_party_ref=principal, farm_ref=farm_ref,
                    artifact_family="OTHER")
                with store.tx() as cur:  # read decisions are recorded too
                    store.insert_record(cur, access.request_payload)
                    store.insert_record(cur, access.trace_payload)
                    store.insert_record(cur, access.result_payload)
                if not access.allowed:
                    deny()
        return _receipt({
            "recordId": row["record_id"], "recordKind": row["record_kind"],
            "schemaHash": row["schema_hash"], "payloadSha256": row["payload_sha256"],
            "runtimeBundleDigest": row["runtime_bundle_digest"],
            "recordTime": row["record_time"].isoformat(), "payload": payload,
        })

    @app.get("/views/passport/{farm_ref}")
    def passport(farm_ref: str, principal: str = Depends(get_principal)):
        return _receipt(app.state.outputs.passport_view(farm_ref, principal))

    @app.post("/views/inspection-register/freeze")
    def freeze(body: FreezeBody, principal: str = Depends(get_principal)):
        return _receipt(
            app.state.outputs.freeze_inspection_register(
                body.farmRef, principal, body.windowStart, body.windowEnd),
        )

    @app.get("/manifest")
    def get_manifest():
        manifests = [component for component in
                     app.state.store.runtime_bundle.components
                     if component.role == "ACTIVE_MANIFEST"]
        if len(manifests) != 1:
            raise HTTPException(
                status_code=503,
                detail="RuntimeBundle does not contain exactly one active manifest",
            )
        return _receipt(
            app.state.store.runtime_bundle.json_component(
                "ACTIVE_MANIFEST", manifests[0].logical_ref),
        )

    return app
