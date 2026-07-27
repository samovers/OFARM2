"""Gate pipeline (M1 brief task 3): the EnforcementChain as a
transaction-scoped orchestration chain.

ingress normalization → authority (default deny; revocation re-check)
→ validation (named validator units, kernel/validators.py)
→ static profile applicability (ContextSnapshot assembly)
→ evidence sufficiency (auto-generated EvidenceSufficiencyCase)
→ review/promotion (self-review per D8; queue acceptance)
→ materialization → trace/result writing.

This module is the ORCHESTRATION SHELL only (issue #3): runtime policy lives
in kernel/policy.py as declarative tables, each gate is a named stage in
kernel/stages.py with a narrow typed contract (GatePass / GateRefusal /
GateReplay), validation is decomposed into named units in
kernel/validators.py, and every PROMOTION-flavor emission (assertions,
reviews, consequences, traces, results, replays) lives in
kernel/emission.py — stages and validators store their own gate records
(authority decisions, sufficiency cases, carriers) where they decide them.

The invariants are unchanged: every authoritative write crosses the chain
inside ONE transaction (D3); every governed refusal after context construction
is a registry-coded RuntimeProblem (Kernel rule 7); every governed outcome
lands in the gate log and the PromotionTrace; capture is not commitment
(Kernel rule 3). An unusable transport header is rejected before the governed
chain and cannot invent a trace or domain outcome.
"""
from __future__ import annotations

import psycopg

from .authority import AuthorityEvaluator
from .context import mint, now_iso, parse_ts
from .contracts import sha256_of
from .emission import PromotionTraceWriter, ReplayWriter
from .problems import runtime_problem
from .profile_runtime import (ProfileRuntimeError, resolve_bound_descriptor,
                              resolve_profile_route)
from .profile_runtime_provider import load_profile_runtime_services
from .profile_runtime_services import ProfileRuntimeServices
from .stages import (AuthorityGate, EnvelopePersist, EvidenceSufficiencyGate,
                     GateContext, GateRefusal, GateReplay, IngressHeader,
                     IngressNormalizer, MaterializationGate,
                     ProfileApplicabilityGate, ReviewPromotionGate,
                     parse_ingress_header)
from .validators import ValidationGate

# law-pinned stage order (PLATFORM.md gate pipeline); validation's internal
# order lives in kernel/validators.py (the common sequence, then the
# class-specific branch: governance acceptance, compliance claim, or the
# operation sequence)
CHAIN = (
    AuthorityGate(),
    ValidationGate(),
    EnvelopePersist(),
    ProfileApplicabilityGate(),
    EvidenceSufficiencyGate(),
    ReviewPromotionGate(),
)


class GatePipeline:
    def __init__(
        self,
        store,
        *,
        active_descriptor=None,
        profile_route_records=None,
        profile_route_registry=None,
        selected_profile_package_names=None,
        tenant_ref=None,
        runtime_services: ProfileRuntimeServices | None = None,
    ):
        self.store = store
        route_inputs = (
            profile_route_records,
            profile_route_registry,
            selected_profile_package_names,
            tenant_ref,
        )
        self.route_backed = any(value is not None for value in route_inputs)
        if self.route_backed and any(value is None for value in route_inputs):
            raise ProfileRuntimeError(
                "route-backed GatePipeline requires profile_route_records, "
                "profile_route_registry, selected_profile_package_names, and "
                "tenant_ref")
        if self.route_backed and tenant_ref != store.tenant_ref:
            raise ProfileRuntimeError(
                "route-backed GatePipeline tenant_ref must match Store tenant_ref")
        self.profile_route_records = profile_route_records
        self.profile_route_registry = profile_route_registry
        self.selected_profile_package_names = selected_profile_package_names
        self.tenant_ref = tenant_ref
        descriptor = resolve_bound_descriptor(
            store,
            active_descriptor=active_descriptor,
        )
        store.require_startup_complete("GatePipeline")
        if runtime_services is None:
            runtime_services = load_profile_runtime_services(
                store,
                store.active_profile_package_name,
                descriptor,
            )
        elif (
            type(runtime_services) is not ProfileRuntimeServices
            or runtime_services.descriptor is not descriptor
        ):
            raise ProfileRuntimeError(
                "GatePipeline requires services bound to its exact descriptor"
            )
        self.runtime_services = runtime_services
        self.authority = AuthorityEvaluator(store)

    # ======================================================================
    # the governed front door
    # ======================================================================

    def commit(self, submission: object) -> dict:
        """Run one typed capture through the full chain.

        A valid call returns its CommitIngressResult from one transaction
        (D3). Unusable transport shape is rejected before a transaction exists.
        """
        header = parse_ingress_header(submission)
        try:
            with self.store.serialized_tx() as cur:
                return self._commit_in_tx(cur, submission, header)
        except psycopg.errors.UniqueViolation:
            # a concurrent commit won the idempotency-key race; our transaction
            # rolled back completely — serve the replay path against the winner.
            # (Under the single-writer lock — M2 G2 — writers serialize, so this
            # backstop is now reached only across connections that bypass it.)
            with self.store.serialized_tx() as cur:
                prior = self.store.idempotency_lookup(
                    cur, header.idempotency_key)
                if prior is None:
                    raise
                ctx = self._new_context(cur, submission, header)
                return ReplayWriter().write(ctx, prior)

    @staticmethod
    def _source_digest(sub: dict) -> str:
        """ALWAYS the server-computed canonical digest of the whole semantic
        submission. A caller-supplied sourcePayloadDigest is evidence metadata
        at most — it never participates in idempotency decisions. Payload-less
        classes digest their full submission, never the constant digest of {}."""
        return sha256_of(
            {k: v for k, v in sub.items() if k != "sourcePayloadDigest"})

    def _new_context(
        self,
        cur,
        sub: dict,
        header: IngressHeader,
    ) -> GateContext:
        return GateContext(
            cur=cur, store=self.store, authority=self.authority,
            runtime_services=self.runtime_services,
            sub=sub,
            request_id=mint("cir"), ingested_at=now_iso(),
            source_digest=self._source_digest(sub),
            commit_class=header.commit_class, farm_ref=header.farm_ref,
            acting_party=header.acting_party_ref,
            idem_key=header.idempotency_key,
            event_id=mint("event"), assertion_id=mint("assert"))

    @staticmethod
    def _route_farm_ref(ctx: GateContext) -> str:
        scopes = ((ctx.envelope or {}).get("anchorScopes") or [])
        farm_scopes = [
            scope for scope in scopes
            if isinstance(scope, dict) and scope.get("scopeType") == "FARM"
        ]
        if len(farm_scopes) != 1:
            raise ProfileRuntimeError(
                "profile route resolution requires exactly one FARM anchor "
                "scope entry in the normalized submission envelope")
        farm_ref = farm_scopes[0].get("scopeRef")
        if not farm_ref:
            raise ProfileRuntimeError(
                "profile route FARM anchor scope must include scopeRef")
        if farm_ref != ctx.farm_ref:
            raise ProfileRuntimeError(
                "profile route FARM anchor scope must match the top-level "
                "submission farmRef")
        return farm_ref

    @staticmethod
    def _route_effective_time(ctx: GateContext):
        if ctx.commit_class == "GOVERNANCE_DECISION":
            raw = ctx.sub.get("decisionTime")
            field = "decisionTime"
        elif ctx.commit_class in {
            "OPERATION_CLAIM",
            "COMPLIANCE_ASSERTION",
            "STRUCTURE_ASSERTION",
        }:
            if ctx.temporal_problem:
                raise ProfileRuntimeError(
                    "profile route eventTime is unparseable")
            raw = ctx.event_time
            field = "eventTime"
        else:
            raise ProfileRuntimeError(
                f"profile route time source is unsupported for "
                f"{ctx.commit_class!r}")
        if not raw:
            raise ProfileRuntimeError(
                f"profile route requires normalized claim-time field {field}")
        parsed = parse_ts(raw)
        if parsed is None:
            raise ProfileRuntimeError(
                f"profile route claim-time field {field} is not parseable")
        return parsed

    def _bind_route_resolution(self, ctx: GateContext, resolution) -> None:
        descriptor = resolve_bound_descriptor(
            ctx.store,
            active_descriptor=resolution.descriptor,
        )
        if (
            resolution.candidate.package_name
            != ctx.store.active_profile_package_name
            or descriptor != self.runtime_services.descriptor
        ):
            raise ProfileRuntimeError(
                "resolved profile runtime provider is not the startup-bound provider"
            )
        ctx.profile_route_resolution = resolution

    def _resolve_profile_route(self, ctx: GateContext):
        try:
            farm_ref = self._route_farm_ref(ctx)
            effective_time = self._route_effective_time(ctx)
            resolution = resolve_profile_route(
                self.profile_route_registry,
                self.selected_profile_package_names,
                self.profile_route_records,
                tenant_ref=self.tenant_ref,
                farm_ref=farm_ref,
                effective_time=effective_time,
            )
            self._bind_route_resolution(ctx, resolution)
        except ProfileRuntimeError as exc:
            ctx.log("PACK_PROFILE_APPLICABILITY", "PROFILE_ROUTE_REFUSE",
                    reason_code="PROFILE_NOT_ACTIVE",
                    rationale=f"PROFILE_ROUTE: {exc}")
            return GateRefusal(
                "PACK_PROFILE_APPLICABILITY", "PROFILE_ROUTE_REFUSE",
                "RETAIN_DRAFT",
                [runtime_problem(
                    "PROFILE_NOT_ACTIVE", "Profile route unavailable",
                    "the active profile route could not be resolved "
                    f"({exc}); the claim stays a draft (fail closed)",
                    suggested_remediation="restore an explicit active "
                    "tenant/farm profile route before resubmitting")])
        ctx.farm_ref = farm_ref
        ctx.log("PACK_PROFILE_APPLICABILITY", "PROFILE_ROUTE_PASS",
                rationale="PROFILE_ROUTE: resolved active profile route",
                refs=[resolution.route.route_id, resolution.descriptor.profile_ref])
        return None

    def _commit_in_tx(
        self,
        cur,
        sub: dict,
        header: IngressHeader,
    ) -> dict:
        ctx = self._new_context(cur, sub, header)

        ingress = IngressNormalizer().run(ctx)
        if isinstance(ingress, GateReplay):
            return ingress.result

        if self.route_backed:
            route_outcome = self._resolve_profile_route(ctx)
            if isinstance(route_outcome, GateRefusal):
                ctx.problems.extend(route_outcome.problems)
                ctx.final_outcome = route_outcome.final_outcome
                ctx.ensure_envelope_stored()
                return PromotionTraceWriter().write(ctx)

        for stage in CHAIN:
            outcome = stage.run(ctx)
            if isinstance(outcome, GateRefusal):
                ctx.problems.extend(outcome.problems)
                ctx.final_outcome = outcome.final_outcome
                # the normalized draft event is still recorded (refusals are
                # traceable history, not silence) — emitted under this trace
                ctx.ensure_envelope_stored()
                return PromotionTraceWriter().write(ctx)

        if ctx.final_outcome == "PROMOTE_ACCEPTED":
            MaterializationGate().run(ctx)

        return PromotionTraceWriter().write(ctx)
