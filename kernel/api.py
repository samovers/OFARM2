"""FastAPI surface — the platform's governed front door over HTTP.

Refusals are data, not transport errors: a processed commit always returns
its CommitIngressResult envelope (problems inside, reason codes from the
registry); malformed requests are 422s. Read surfaces enforce default deny
per request — there is no unauthenticated path to farm-scoped truth.
"""
from __future__ import annotations

import json

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import config, context, manifest as manifest_mod
from .contracts import ContractViolation
from .gates import GatePipeline
from .store import Store
from .views import OutputGenerator


class CommitBody(BaseModel):
    submission: dict


class FreezeBody(BaseModel):
    farmRef: str
    windowStart: str
    windowEnd: str


class ReviewAcceptBody(BaseModel):
    farmRef: str
    assertionRef: str
    # acceptance is a governed RESOLUTION, never a bare pointer: the
    # rationale is mandatory, and routed insufficiencies additionally
    # require reviewer-attached durable evidence (gate-enforced)
    rationale: str
    evidenceRefs: list[str] = []
    idempotencyKey: str | None = None


def create_app(store: Store | None = None) -> FastAPI:
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

    @app.get("/health")
    def health():
        return {"status": "ok",
                "unreachableAuthoritativeRecords":
                    app.state.store.unreachable_authoritative_records()}

    @app.post("/commit")
    def commit(body: CommitBody, x_acting_party: str = Header(...)):
        # The transport principal binds to the submitted actor BEFORE the
        # pipeline runs: a body-supplied actingPartyRef is never trusted on
        # its own (hostile review blocker 1). In M1 the principal is the
        # required X-Acting-Party header — a development principal pending
        # OIDC (M2), declared in profile_si_ffs/UNSUPPORTED_SURFACES.md —
        # but the binding contract is the same one OIDC will fill: the
        # gate's actor is the transport's actor, or the commit is refused.
        if body.submission.get("actingPartyRef") != x_acting_party:
            raise HTTPException(status_code=403, detail={
                "reasonCode": "ACTOR_BINDING_UNRESOLVED",
                "detail": "submission.actingPartyRef does not match the "
                          "transport principal (X-Acting-Party); body-level "
                          "actor spoofing is refused"})
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
        payload, kind = row["payload"], row["record_kind"]
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
    def review_accept(body: ReviewAcceptBody, x_acting_party: str = Header(...)):
        # the review act is the REVIEWER'S own governed commit: the reviewer
        # IS the transport principal — there is no body-named reviewer field
        # to forge (hostile review blocker 1, second pass)
        import uuid as _uuid
        from .context import now_iso as _now
        submission = {
            "commitClass": "GOVERNANCE_DECISION",
            "ingressChannel": "MANUAL_UI",
            "actingPartyRef": x_acting_party,
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

    @app.get("/records/{record_id}")
    def get_record(record_id: str, x_acting_party: str = Header(...)):
        store = app.state.store
        row = store.get_record(record_id)
        if row is None:
            raise HTTPException(status_code=404, detail="no such record")
        payload, kind = row["payload"], row["record_kind"]

        def deny():
            # default deny; distinguish "exists but permission-limited"
            # from "does not exist" (reason-code registry safe-UI rule)
            raise HTTPException(status_code=403, detail={
                "reasonCode": "PERMISSION_REDACTED",
                "detail": "the record exists but you are not authorized to read it"})

        if kind == "ofarm.party.v0.1":
            # a party record is readable by that party alone at this surface
            if payload["partyId"] != x_acting_party:
                deny()
        elif kind not in PUBLIC_ARTIFACT_KINDS:
            farm_scopes = _read_farm_scopes(store, row)
            if not farm_scopes:
                deny()  # unresolvable scope never defaults open (Kernel rule 2)
            for farm_ref in farm_scopes:
                access = app.state.outputs.authority.evaluate_read(
                    requesting_party_ref=x_acting_party, farm_ref=farm_ref,
                    artifact_family="OTHER")
                with store.tx() as cur:  # read decisions are recorded too
                    store.insert_record(cur, access.request_payload)
                    store.insert_record(cur, access.trace_payload)
                    store.insert_record(cur, access.result_payload)
                if not access.allowed:
                    deny()
        return {"recordId": row["record_id"], "recordKind": row["record_kind"],
                "schemaHash": row["schema_hash"], "payloadSha256": row["payload_sha256"],
                "recordTime": row["record_time"].isoformat(), "payload": payload}

    @app.get("/views/passport/{farm_ref}")
    def passport(farm_ref: str, x_acting_party: str = Header(...)):
        return app.state.outputs.passport_view(farm_ref, x_acting_party)

    @app.post("/views/inspection-register/freeze")
    def freeze(body: FreezeBody, x_acting_party: str = Header(...)):
        return app.state.outputs.freeze_inspection_register(
            body.farmRef, x_acting_party, body.windowStart, body.windowEnd)

    @app.get("/manifest")
    def get_manifest():
        if manifest_mod.MANIFEST_PATH.exists():
            return json.loads(manifest_mod.MANIFEST_PATH.read_text())
        return manifest_mod.build_manifest(app.state.store)

    return app
