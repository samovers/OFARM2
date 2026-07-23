"""FastAPI surface — the platform's governed front door over HTTP.

Refusals are data, not transport errors: a processed commit always returns
its CommitIngressResult envelope (problems inside, reason codes from the
registry); malformed requests are 422s. Read surfaces enforce default deny
per request — there is no unauthenticated path to farm-scoped truth.
"""
from __future__ import annotations

import json

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import auth_oidc, config
from .contracts import ContractViolation
from .gates import GatePipeline
from .principal_binding import PrincipalBindingAuthority
from .problems import runtime_problem
from .runtime_activation import (
    RuntimeActivationObservation,
    complete_store_startup,
    deployment_image_digest_from_env,
    require_deployment_image_digest,
)
from .runtime_bundle import RuntimeBundleBuilder, RuntimeComponentRole
from .runtime_composition import ProductionApplicationRuntime
from .store import Store
from .views import OutputGenerator

# The production factory resolves one explicit authentication mode from the
# environment. Authentication fixtures are accepted only by create_test_app().
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


def create_app(
    store: Store | None = None,
    *,
    authentication=_FROM_ENV,
    principal_binding_resolver=None,
    deployment_image_digest=_FROM_ENV,
) -> FastAPI:
    selected_image_digest = _deployment_image_preflight(
        deployment_image_digest
    )
    if authentication is not _FROM_ENV:
        if type(authentication) is not auth_oidc.ProductionAuthenticationRuntime:
            raise auth_oidc.AuthenticationStartupError(
                "create_app accepts only the exact production authentication "
                "runtime; use create_test_app for authentication fixtures"
            )
        authentication_runtime = authentication
    else:
        authentication_runtime = config.authentication_runtime_from_env(
            principal_binding_resolver=principal_binding_resolver
        )
    production_runtime = (
        config.production_application_runtime(authentication_runtime)
        if type(authentication_runtime)
        is auth_oidc.ProductionAuthenticationRuntime
        else None
    )
    return _create_app_with_runtime(
        store,
        authentication_runtime=authentication_runtime,
        production_runtime=production_runtime,
        selected_image_digest=selected_image_digest,
    )


def create_test_app(
    store: Store | None = None,
    *,
    authentication=_FROM_ENV,
    oidc=_FROM_ENV,
    deployment_image_digest=_FROM_ENV,
) -> FastAPI:
    """Build an application with explicit test-only authentication fixtures."""

    selected_image_digest = _deployment_image_preflight(
        deployment_image_digest
    )
    if authentication is not _FROM_ENV and oidc is not _FROM_ENV:
        raise auth_oidc.AuthenticationStartupError(
            "authentication and oidc test settings cannot both be supplied"
        )
    if authentication is not _FROM_ENV:
        if type(authentication) not in (
            auth_oidc.DevelopmentAuthenticationRuntime,
            auth_oidc.TestAuthenticationRuntime,
            auth_oidc.ProductionAuthenticationRuntime,
        ):
            raise auth_oidc.AuthenticationStartupError(
                "test authentication runtime has the wrong type"
            )
        authentication_runtime = authentication
    elif oidc is not _FROM_ENV:
        if oidc is None:
            authentication_runtime = auth_oidc.AuthenticationRuntime.development()
        elif type(oidc) is auth_oidc.OidcConfig:
            authentication_runtime = auth_oidc.AuthenticationRuntime.test(oidc)
        else:
            raise auth_oidc.AuthenticationStartupError(
                "oidc compatibility setting accepts only exact OidcConfig or None"
            )
    else:
        raise auth_oidc.AuthenticationStartupError(
            "create_test_app requires explicit authentication or oidc test settings"
        )
    return _create_app_with_runtime(
        store,
        authentication_runtime=authentication_runtime,
        production_runtime=None,
        selected_image_digest=selected_image_digest,
    )


def _deployment_image_preflight(deployment_image_digest) -> str:
    return (
        deployment_image_digest_from_env()
        if deployment_image_digest is _FROM_ENV
        else require_deployment_image_digest(deployment_image_digest)
    )


def _create_app_with_runtime(
    store: Store | None,
    *,
    authentication_runtime: auth_oidc.AuthenticationRuntime,
    production_runtime: ProductionApplicationRuntime | None,
    selected_image_digest: str,
) -> FastAPI:
    production_capability_issuer = None
    if production_runtime is None:
        authentication_runtime.initialize()
    else:
        if (
            type(production_runtime) is not ProductionApplicationRuntime
            or production_runtime.authentication is not authentication_runtime
        ):
            raise auth_oidc.AuthenticationStartupError(
                "production application composition differs"
            )
        production_runtime.initialize()
        production_capability_issuer = (
            production_runtime.capability_issuer
        )

    app = FastAPI(
        title="OFARM2 Kernel (M1)",
        description="Implementation and conformance packaging profile — not OFARM "
                    "law. Claims record-keeping completeness only; never "
                    "current-compliance, certification, or production readiness.",
        version="m1.0",
    )
    if store is None:
        selected_bundle = RuntimeBundleBuilder.from_manifest(
            config.PACKAGE_ROOT
        ).build()
        store = Store(
            tenant_ref=config.TENANT_REF,
            runtime_bundle=selected_bundle,
            active_descriptor=config.ACTIVE_PROFILE,
        )
    selected_manifest = json.loads(next(
        component.canonical_bytes
        for component in store.runtime_bundle.components
        if component.role is RuntimeComponentRole.ACTIVE_MANIFEST
    ))
    app.state.store = store
    database_observation = complete_store_startup(app.state.store)
    app.state.runtime_activation = RuntimeActivationObservation(
        tenant_ref=app.state.store.tenant_ref,
        active_profile_ref=app.state.store.active_descriptor.profile_ref,
        runtime_bundle_digest=app.state.store.runtime_bundle_digest,
        deployment_image_digest=selected_image_digest,
        database=database_observation,
    )
    app.state.pipeline = GatePipeline(
        app.state.store, active_descriptor=app.state.store.active_descriptor)
    app.state.outputs = OutputGenerator(
        app.state.store, active_descriptor=app.state.store.active_descriptor)
    # Compatibility observation only. The authoritative immutable runtime is
    # closed over by get_principal and cannot be replaced through app.state.
    app.state.oidc = authentication_runtime.verifier

    @app.middleware("http")
    async def runtime_bundle_receipt_header(request, call_next):
        response = await call_next(request)
        response.headers["X-OFARM-Runtime-Bundle-Digest"] = \
            app.state.store.runtime_bundle_digest
        return response

    def _deny(title: str, detail: str, pid: str):
        raise HTTPException(status_code=401, detail=runtime_problem(
            "AUTHORITY_DENIED", title, detail, problem_id=pid))

    def get_principal(authorization: str | None = Header(None),
                      x_acting_party: str | None = Header(None)) -> str:
        """Resolve one transport principal under the selected explicit mode."""
        try:
            principal, binding = authentication_runtime.resolve_principal(
                authorization=authorization,
                development_header=x_acting_party,
            )
        except auth_oidc.OidcError as exc:
            _deny(
                "Authentication refused",
                f"authentication failed closed ({exc.outcome.value})",
                "problem:api-authentication-refused",
            )
        if authentication_runtime.mode is not auth_oidc.AuthenticationMode.PRODUCTION:
            rec = app.state.store.get_record(principal)
            if (rec is None or rec["record_kind"] != "ofarm.party.v0.1"
                    or rec["payload"].get("partyState") != "ACTIVE"):
                _deny("Principal is not an active Party",
                      "the transport principal is not a recorded active Party; "
                      "default deny", "problem:api-principal-not-party")
        else:
            if (
                type(authentication_runtime)
                is auth_oidc.ProductionAuthenticationRuntime
                and production_capability_issuer is None
            ):
                _deny(
                    "Authentication refused",
                    "production capability boundary is absent; default deny",
                    "problem:api-authentication-refused",
                )
            if type(binding) is not PrincipalBindingAuthority:
                _deny(
                    "Authentication refused",
                    "production principal binding differs; default deny",
                    "problem:api-authentication-refused",
                )
            raise HTTPException(
                status_code=503,
                detail=runtime_problem(
                    "TENANT_BOUNDARY_BLOCKED",
                    "Production tenant surface unavailable",
                    "the legacy Store-backed HTTP surface is refused in "
                    "production until the tenant UnitOfWork carries the full "
                    "immutable principal-binding authority",
                    problem_id="problem:api-production-surface-refused",
                ),
            )
        return principal

    app.state.get_principal = get_principal

    @app.get("/health")
    def health():
        return {"status": "ok",
                "runtimeBundleDigest": app.state.store.runtime_bundle_digest,
                "runtimeActivation": app.state.runtime_activation.as_dict(),
                "unreachableAuthoritativeRecords":
                    app.state.store.unreachable_authoritative_records()}

    @app.post("/commit")
    def commit(body: CommitBody, principal: str = Depends(get_principal)):
        # The transport principal binds to the submitted actor BEFORE the
        # pipeline runs: a body-supplied actingPartyRef is never trusted on its
        # own (hostile review blocker 1). The principal is the OIDC-verified Party
        # in production, the explicit test issuer in test mode, or the explicit
        # development header. The gate's actor is the transport's actor, or it is
        # refused.
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
            return app.state.pipeline.commit(body.submission)
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
    def review_accept(body: ReviewAcceptBody, principal: str = Depends(get_principal)):
        # the review act is the REVIEWER'S own governed commit: the reviewer
        # IS the transport principal — there is no body-named reviewer field
        # to forge (hostile review blocker 1, second pass)
        import uuid as _uuid
        from .context import now_iso as _now
        submission = {
            "commitClass": "GOVERNANCE_DECISION",
            "ingressChannel": "MANUAL_UI",
            "actingPartyRef": principal,
            "farmRef": body.farmRef,
            "idempotencyKey": body.idempotencyKey
                              or f"review-accept:{_uuid.uuid4().hex[:16]}",
            "decisionTime": _now(),
            "reviewTargetAssertionRef": body.assertionRef,
            "reviewRationale": body.rationale,
            "reviewEvidenceRefs": body.evidenceRefs,
            "dominantSemanticConsequence": "review acceptance of a queued claim",
        }
        try:
            return app.state.pipeline.commit(submission)
        except (ContractViolation, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.post("/review/reject")
    def review_reject(body: ReviewAcceptBody, principal: str = Depends(get_principal)):
        # the reject act is the REVIEWER'S own governed decline under their own
        # transport principal (M2 G5-2). The endpoint supplies the normalized
        # review-decision pair (REVIEW_REJECT_OR_CONTEST / REJECTED) so the client
        # never passes raw outcome values (docs/REVIEW_DISPUTE_SEMANTICS.md §3.1).
        # Authority is the DISTINCT REVIEW_REJECT_OR_CONTEST action — a principal
        # holding only REVIEW_ACCEPT is denied. The rationale is mandatory;
        # supplied evidence is validated like acceptance's.
        import uuid as _uuid
        from .context import now_iso as _now
        submission = {
            "commitClass": "GOVERNANCE_DECISION",
            "ingressChannel": "MANUAL_UI",
            "actingPartyRef": principal,
            "farmRef": body.farmRef,
            "idempotencyKey": body.idempotencyKey
                              or f"review-reject:{_uuid.uuid4().hex[:16]}",
            "decisionTime": _now(),
            "reviewTargetAssertionRef": body.assertionRef,
            "reviewAction": "REVIEW_REJECT_OR_CONTEST",
            "decisionOutcomeState": "REJECTED",
            "reviewRationale": body.rationale,
            "reviewEvidenceRefs": body.evidenceRefs,
            "dominantSemanticConsequence": "review rejection of a queued claim",
        }
        try:
            return app.state.pipeline.commit(submission)
        except (ContractViolation, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.post("/review/contest")
    def review_contest(body: ReviewContestBody, principal: str = Depends(get_principal)):
        # a CONTEST opens an append-only dispute against an ALREADY IN-FORCE
        # consequence under the reviewer's own principal (M2 G5-4). The endpoint
        # supplies the normalized pair (REVIEW_REJECT_OR_CONTEST / CONTESTED) and
        # the target consequence ref; authority is the distinct
        # REVIEW_REJECT_OR_CONTEST action; the consequence is flagged (DISPUTE
        # edge) but never edited, and dependent materializations stale (spec §6).
        import uuid as _uuid
        from .context import now_iso as _now
        submission = {
            "commitClass": "GOVERNANCE_DECISION",
            "ingressChannel": "MANUAL_UI",
            "actingPartyRef": principal,
            "farmRef": body.farmRef,
            "idempotencyKey": body.idempotencyKey
                              or f"review-contest:{_uuid.uuid4().hex[:16]}",
            "decisionTime": _now(),
            "reviewTargetConsequenceRef": body.consequenceRef,
            "reviewAction": "REVIEW_REJECT_OR_CONTEST",
            "decisionOutcomeState": "CONTESTED",
            "reviewRationale": body.rationale,
            "reviewEvidenceRefs": body.evidenceRefs,
            "dominantSemanticConsequence": "dispute against an in-force consequence",
        }
        try:
            return app.state.pipeline.commit(submission)
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
        return {"recordId": row["record_id"], "recordKind": row["record_kind"],
                "schemaHash": row["schema_hash"], "payloadSha256": row["payload_sha256"],
                "recordTime": row["record_time"].isoformat(),
                "runtimeBundleDigest": row["runtime_bundle_digest"],
                "payload": payload}

    @app.get("/views/passport/{farm_ref}")
    def passport(farm_ref: str, principal: str = Depends(get_principal)):
        return app.state.outputs.passport_view(farm_ref, principal)

    @app.post("/views/inspection-register/freeze")
    def freeze(body: FreezeBody, principal: str = Depends(get_principal)):
        return app.state.outputs.freeze_inspection_register(
            body.farmRef, principal, body.windowStart, body.windowEnd)

    @app.get("/manifest")
    def get_manifest():
        return selected_manifest

    return app
