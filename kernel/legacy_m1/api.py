"""Explicit development and conformance HTTP surface for the M1 prototype."""
from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from ..contracts import ContractViolation
from ..problems import runtime_problem
from ..stages import IngressHeaderViolation

if TYPE_CHECKING:
    from ..auth_oidc import TestOidcVerifier
    from ..store import Store
    from .runtime import DevelopmentRuntime, TestRuntime


TEST_DEPLOYMENT_IMAGE_DIGEST = "sha256:" + "a" * 64
_MALFORMED_INGRESS_HEADER_DETAIL = "malformed ingress submission header"
PUBLIC_ARTIFACT_KINDS = {
    "ofarm.referencesnapshot.v0.1",
    "ofarm.agronomiccodebindingprofile.v0.1",
    "ofarm.packactivationset.v0.1",
    "ofarm.activeartifactset.v0.1",
}


class CommitBody(BaseModel):
    submission: dict


class FreezeBody(BaseModel):
    farmRef: str
    windowStart: str
    windowEnd: str


class ReviewContestBody(BaseModel):
    farmRef: str
    consequenceRef: str
    rationale: str
    evidenceRefs: list[str] = Field(default_factory=list)
    idempotencyKey: str | None = None


class ReviewAcceptBody(BaseModel):
    farmRef: str
    assertionRef: str
    rationale: str
    evidenceRefs: list[str] = Field(default_factory=list)
    idempotencyKey: str | None = None


def create_test_app(
    store: Store,
    *,
    oidc: TestOidcVerifier | None = None,
    deployment_image_digest: str = TEST_DEPLOYMENT_IMAGE_DIGEST,
) -> FastAPI:
    """Build the explicit conformance surface from injected dependencies."""
    from .runtime import build_test_runtime

    runtime = build_test_runtime(store, deployment_image_digest, oidc)
    return _legacy_app(runtime)


def create_development_app(
    store: Store,
    *,
    deployment_image_digest: str = TEST_DEPLOYMENT_IMAGE_DIGEST,
) -> FastAPI:
    """Build the explicit development surface from an injected Store."""
    from .runtime import build_development_runtime

    runtime = build_development_runtime(store, deployment_image_digest)
    return _legacy_app(runtime)


def _transport_principal(store, oidc):
    def deny(title: str, detail: str, problem_id: str):
        raise HTTPException(
            status_code=401,
            detail=runtime_problem(
                "AUTHORITY_DENIED",
                title,
                detail,
                problem_id=problem_id,
            ),
        )

    def principal(
        authorization: str | None = Header(None),
        x_acting_party: str | None = Header(None),
    ) -> str:
        if oidc is None:
            if not x_acting_party:
                deny(
                    "No transport principal",
                    "no X-Acting-Party principal presented; default deny",
                    "problem:api-no-principal",
                )
            party_ref = x_acting_party
        else:
            from ..auth_oidc import TestOidcError

            if not authorization or not authorization.lower().startswith(
                "bearer "
            ):
                deny(
                    "No bearer token",
                    "no bearer token presented; default deny",
                    "problem:api-no-token",
                )
            try:
                token = authorization.split(" ", 1)[1].strip()
                party_ref = oidc.verify(token)["partyRef"]
            except TestOidcError as exc:
                deny(
                    "Token verification failed",
                    str(exc),
                    "problem:api-token-invalid",
                )
        record = store.get_record(party_ref)
        if (
            record is None
            or record["record_kind"] != "ofarm.party.v0.1"
            or record["payload"].get("partyState") != "ACTIVE"
        ):
            deny(
                "Principal is not an active Party",
                f"{party_ref} is not a recorded active Party; default deny",
                "problem:api-principal-not-party",
            )
        return party_ref

    return principal


def _install_commit_route(app, pipeline, principal) -> None:
    @app.post("/commit")
    def commit(body: CommitBody, party_ref: str = Depends(principal)):
        if body.submission.get("actingPartyRef") != party_ref:
            raise HTTPException(
                status_code=403,
                detail=runtime_problem(
                    "ACTOR_BINDING_UNRESOLVED",
                    "Transport principal mismatch",
                    "submission actor differs from the transport principal",
                    problem_id="problem:api-principal-mismatch",
                ),
            )
        try:
            return pipeline.commit(body.submission)
        except IngressHeaderViolation:
            raise HTTPException(
                status_code=422,
                detail=_MALFORMED_INGRESS_HEADER_DETAIL,
            ) from None
        except (ContractViolation, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))


def _review_submission(kind: str, body, party_ref: str) -> dict:
    from ..context import now_iso

    common = {
        "commitClass": "GOVERNANCE_DECISION",
        "ingressChannel": "MANUAL_UI",
        "actingPartyRef": party_ref,
        "farmRef": body.farmRef,
        "idempotencyKey": body.idempotencyKey
        or f"review-{kind}:{uuid.uuid4().hex[:16]}",
        "decisionTime": now_iso(),
        "reviewRationale": body.rationale,
        "reviewEvidenceRefs": body.evidenceRefs,
    }
    if kind == "accept":
        return common | {
            "reviewTargetAssertionRef": body.assertionRef,
            "dominantSemanticConsequence": "review acceptance of a queued claim",
        }
    outcome = "REJECTED" if kind == "reject" else "CONTESTED"
    target = (
        {"reviewTargetAssertionRef": body.assertionRef}
        if kind == "reject"
        else {"reviewTargetConsequenceRef": body.consequenceRef}
    )
    return common | target | {
        "reviewAction": "REVIEW_REJECT_OR_CONTEST",
        "decisionOutcomeState": outcome,
        "dominantSemanticConsequence": (
            "review rejection of a queued claim"
            if kind == "reject"
            else "dispute against an in-force consequence"
        ),
    }


def _install_review_routes(app, pipeline, principal) -> None:
    def submit(kind: str, body, party_ref: str):
        try:
            return pipeline.commit(_review_submission(kind, body, party_ref))
        except IngressHeaderViolation:
            raise HTTPException(
                status_code=422,
                detail=_MALFORMED_INGRESS_HEADER_DETAIL,
            ) from None
        except (ContractViolation, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.post("/review/accept")
    def accept(body: ReviewAcceptBody, party_ref: str = Depends(principal)):
        return submit("accept", body, party_ref)

    @app.post("/review/reject")
    def reject(body: ReviewAcceptBody, party_ref: str = Depends(principal)):
        return submit("reject", body, party_ref)

    @app.post("/review/contest")
    def contest(body: ReviewContestBody, party_ref: str = Depends(principal)):
        return submit("contest", body, party_ref)


def _read_farm_scopes(store, row) -> list[str] | None:
    payload = row["payload"]
    farms = [
        scope["scopeRef"]
        for field in ("anchorScopes", "targetScopes")
        for scope in payload.get(field, [])
        if isinstance(scope, dict) and scope.get("scopeType") == "FARM"
    ]
    target_scope = payload.get("targetScope")
    if (
        isinstance(target_scope, dict)
        and target_scope.get("scopeType") == "FARM"
    ):
        farms.append(target_scope["scopeRef"])
    target = payload.get("target", {})
    scope = target.get("scope", {}) if isinstance(target, dict) else {}
    if isinstance(scope, dict) and scope.get("scopeType") == "FARM":
        farms.append(scope["scopeRef"])
    if farms:
        return sorted(set(farms))
    for field in ("semanticEventRef", "requestId"):
        reference = payload.get(field)
        if isinstance(reference, str):
            linked = store.get_record(reference)
            if linked is not None and linked["record_id"] != row["record_id"]:
                resolved = _read_farm_scopes(store, linked)
                if resolved:
                    return resolved
    return None


def _record_response(row) -> dict:
    return {
        "recordId": row["record_id"],
        "recordKind": row["record_kind"],
        "schemaHash": row["schema_hash"],
        "payloadSha256": row["payload_sha256"],
        "recordTime": row["record_time"].isoformat(),
        "runtimeBundleDigest": row["runtime_bundle_digest"],
        "payload": row["payload"],
    }


def _install_read_routes(app, store, outputs, principal) -> None:
    def deny():
        raise HTTPException(
            status_code=403,
            detail=runtime_problem(
                "PERMISSION_REDACTED",
                "Read not authorized",
                "the record exists but is not readable by this principal",
                problem_id="problem:api-read-denied",
            ),
        )

    @app.get("/records/{record_id}")
    def get_record(record_id: str, party_ref: str = Depends(principal)):
        row = store.get_record(record_id)
        if row is None:
            raise HTTPException(status_code=404, detail="no such record")
        payload = row["payload"]
        if row["record_kind"] == "ofarm.party.v0.1":
            if payload["partyId"] != party_ref:
                deny()
        elif row["record_kind"] not in PUBLIC_ARTIFACT_KINDS:
            farms = _read_farm_scopes(store, row)
            if not farms:
                deny()
            for farm_ref in farms:
                access = outputs.authority.evaluate_read(
                    requesting_party_ref=party_ref,
                    farm_ref=farm_ref,
                    artifact_family="OTHER",
                )
                with store.tx() as cursor:
                    store.insert_record(cursor, access.request_payload)
                    store.insert_record(cursor, access.trace_payload)
                    store.insert_record(cursor, access.result_payload)
                if not access.allowed:
                    deny()
        return _record_response(row)

    @app.get("/views/passport/{farm_ref}")
    def passport(farm_ref: str, party_ref: str = Depends(principal)):
        return outputs.passport_view(farm_ref, party_ref)

    @app.post("/views/inspection-register/freeze")
    def freeze(body: FreezeBody, party_ref: str = Depends(principal)):
        return outputs.freeze_inspection_register(
            body.farmRef,
            party_ref,
            body.windowStart,
            body.windowEnd,
        )


def _legacy_app(runtime: DevelopmentRuntime | TestRuntime) -> FastAPI:
    from ..runtime_bundle import RuntimeComponentRole
    from .runtime import TestRuntime

    store, pipeline, outputs = runtime.store, runtime.pipeline, runtime.outputs
    oidc = runtime.oidc if isinstance(runtime, TestRuntime) else None
    manifest = json.loads(
        next(
            component.canonical_bytes
            for component in store.runtime_bundle.components
            if component.role is RuntimeComponentRole.ACTIVE_MANIFEST
        )
    )
    app = FastAPI(title="OFARM2 Kernel (M1)", version="m1.0")
    app.state.runtime_metadata = runtime.activation
    principal = _transport_principal(store, oidc)
    _install_commit_route(app, pipeline, principal)
    _install_review_routes(app, pipeline, principal)
    _install_read_routes(app, store, outputs, principal)

    @app.middleware("http")
    async def receipt_header(request, call_next):
        response = await call_next(request)
        response.headers["X-OFARM-Runtime-Bundle-Digest"] = (
            store.runtime_bundle_digest
        )
        return response

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "runtimeBundleDigest": store.runtime_bundle_digest,
            "runtimeActivation": runtime.activation.as_dict(),
            "unreachableAuthoritativeRecords": (
                store.unreachable_authoritative_records()
            ),
        }

    @app.get("/manifest")
    def get_manifest():
        return manifest

    return app
