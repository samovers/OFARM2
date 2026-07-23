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
inside ONE transaction (D3); every refusal is a registry-coded RuntimeProblem
(Kernel rule 7); every outcome lands in the gate log and the PromotionTrace;
capture is not commitment (Kernel rule 3).
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
from .profile_runtime_provider import (
    ProfileRuntimeProviderRegistry,
    ProfileRuntimeServices,
    default_profile_runtime_provider_registry,
)
from .stages import (AuthorityGate, EnvelopePersist, EvidenceSufficiencyGate,
                     GateContext, GateRefusal, GateReplay, IngressNormalizer,
                     MaterializationGate, ProfileApplicabilityGate,
                     ReviewPromotionGate)
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
        active_profile=None,
        profile_route_records=None,
        profile_route_registry=None,
        selected_profile_package_names=None,
        tenant_ref=None,
        runtime_provider_registry: ProfileRuntimeProviderRegistry | None = None,
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
        selected_descriptor = resolve_bound_descriptor(
            store,
            active_descriptor=active_descriptor,
            active_profile=active_profile,
        )
        store.require_startup_complete("GatePipeline")
        self.runtime_bundle = store.runtime_bundle
        code_owned_registry = default_profile_runtime_provider_registry()
        if (
            runtime_provider_registry is not None
            and runtime_provider_registry is not code_owned_registry
        ):
            raise ProfileRuntimeError(
                "GatePipeline requires the code-owned profile runtime "
                "provider registry"
            )
        self.runtime_provider_registry = code_owned_registry
        self._runtime_services = self.runtime_provider_registry.build_services(
            store,
            store.active_profile_package_name,
            selected_descriptor,
        )
        self.policy_provider = self.runtime_services.policy_provider
        self.si_reference_bindings = self.runtime_services.reference_bindings
        self.authority = AuthorityEvaluator(store)
        self.context = self.runtime_services.context_assembler
        self.materializer = self.runtime_services.materializer
        self.products = self.runtime_services.product_lookup

    @property
    def runtime_services(self) -> ProfileRuntimeServices | None:
        """The startup-bound services; callers cannot replace this authority."""
        return getattr(self, "_runtime_services", None)

    @property
    def active_profile(self):
        """The descriptor selected by the startup-bound runtime services."""
        services = self.runtime_services
        return getattr(services, "descriptor", None)

    def _available_runtime_services(self) -> ProfileRuntimeServices | None:
        """Return a complete, still Store-bound startup service set."""
        services = self.runtime_services
        if not isinstance(services, ProfileRuntimeServices):
            return None
        descriptor = getattr(services, "descriptor", None)
        if descriptor is None:
            return None
        try:
            bound_descriptor = resolve_bound_descriptor(
                self.store,
                active_descriptor=descriptor,
            )
            provider = self.runtime_provider_registry.provider_for(
                self.store.active_profile_package_name,
                bound_descriptor,
            )
        except (AttributeError, ProfileRuntimeError):
            return None
        if (
            bound_descriptor != descriptor
            or services.provider is not provider
            or services.policy_provider is None
            or services.context_assembler is None
            or services.materializer is None
        ):
            return None
        return services

    # ======================================================================
    # the governed front door
    # ======================================================================

    def commit(self, submission: dict) -> dict:
        """Run one capture through the full chain. Returns the
        CommitIngressResult payload. One call = one transaction (D3)."""
        try:
            with self.store.serialized_tx() as cur:
                return self._commit_in_tx(cur, submission)
        except psycopg.errors.UniqueViolation:
            # a concurrent commit won the idempotency-key race; our transaction
            # rolled back completely — serve the replay path against the winner.
            # (Under the single-writer lock — M2 G2 — writers serialize, so this
            # backstop is now reached only across connections that bypass it.)
            with self.store.serialized_tx() as cur:
                prior = self.store.idempotency_lookup(
                    cur, submission["idempotencyKey"])
                if prior is None:
                    raise
                ctx = self._new_context(cur, submission)
                return ReplayWriter().write(ctx, prior)

    @staticmethod
    def _source_digest(sub: dict) -> str:
        """ALWAYS the server-computed canonical digest of the whole semantic
        submission. A caller-supplied sourcePayloadDigest is evidence metadata
        at most — it never participates in idempotency decisions. Payload-less
        classes digest their full submission, never the constant digest of {}."""
        return sha256_of(
            {k: v for k, v in sub.items() if k != "sourcePayloadDigest"})

    def _new_context(self, cur, sub: dict) -> GateContext:
        runtime_services = self._available_runtime_services()
        active_profile = (
            runtime_services.descriptor if runtime_services is not None else None)
        return GateContext(
            cur=cur, store=self.store, authority=self.authority,
            context_assembler=(
                runtime_services.context_assembler if runtime_services else None
            ),
            materializer=(
                runtime_services.materializer if runtime_services else None
            ),
            products=(
                runtime_services.product_lookup if runtime_services else None
            ),
            active_profile=active_profile,
            runtime_services=runtime_services,
            policy_provider=(runtime_services.policy_provider if runtime_services else None),
            si_reference_bindings=(
                runtime_services.reference_bindings if runtime_services else None
            ),
            sub=sub,
            request_id=mint("cir"), ingested_at=now_iso(),
            source_digest=self._source_digest(sub),
            commit_class=sub["commitClass"], farm_ref=sub["farmRef"],
            acting_party=sub["actingPartyRef"], idem_key=sub["idempotencyKey"],
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
        services = self._available_runtime_services()
        if services is None:
            raise ProfileRuntimeError(
                "startup-bound profile runtime services are unavailable")
        provider = self.runtime_provider_registry.provider_for(
            resolution.candidate.package_name,
            resolution.descriptor,
        )
        descriptor = resolve_bound_descriptor(
            ctx.store,
            active_descriptor=resolution.descriptor,
        )
        if (
            provider is not services.provider
            or descriptor != services.descriptor
        ):
            raise ProfileRuntimeError(
                "resolved profile runtime provider is not the startup-bound provider"
            )
        ctx.profile_route_resolution = resolution
        ctx.active_profile = descriptor
        ctx.runtime_services = services
        ctx.policy_provider = services.policy_provider
        ctx.context_assembler = services.context_assembler
        ctx.materializer = services.materializer
        ctx.products = services.product_lookup
        ctx.si_reference_bindings = services.reference_bindings

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

    def _commit_in_tx(self, cur, sub: dict) -> dict:
        ctx = self._new_context(cur, sub)

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
