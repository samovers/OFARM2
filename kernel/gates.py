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

from . import profile_policy
from .authority import AuthorityEvaluator
from .context import ContextAssembler, ProductRegister, SIReferenceBindings, mint, now_iso
from .contracts import sha256_of
from .emission import PromotionTraceWriter, ReplayWriter
from .materializer import Materializer
from .problems import runtime_problem
from .profile_runtime import (ProfileRuntimeError,
                              active_time_bounded_profile_routes,
                              resolve_active_descriptor, resolve_profile_route)
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
        product_register: ProductRegister | None = None,
        *,
        active_descriptor=None,
        active_profile=None,
        profile_route_records=None,
        profile_route_registry=None,
        selected_profile_package_names=None,
        tenant_ref=None,
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
        self.profile_route_records = profile_route_records
        self.profile_route_registry = profile_route_registry
        self.selected_profile_package_names = selected_profile_package_names
        self.tenant_ref = tenant_ref
        if (active_descriptor is not None and active_profile is not None
                and active_descriptor != active_profile):
            raise ProfileRuntimeError(
                "active_descriptor and active_profile refer to different descriptors")
        self.active_profile = resolve_active_descriptor(
            active_descriptor if active_descriptor is not None else active_profile,
            allow_config_default=True,
        )
        self.policy_provider = profile_policy.DescriptorPolicyProvider(
            self.active_profile)
        self.si_reference_bindings = SIReferenceBindings.from_descriptor(
            self.active_profile)
        self.si_reference_bindings_descriptor = self.active_profile
        self.authority = AuthorityEvaluator(store)
        self.context = ContextAssembler(store, active_descriptor=self.active_profile)
        self.materializer = Materializer(store, active_descriptor=self.active_profile)
        self.products = product_register or ProductRegister(self.si_reference_bindings)
        self.products.load_from_store(store)

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
        policy_provider = (
            self.policy_provider
            if self.active_profile == self.policy_provider.descriptor
            else None
        )
        si_reference_bindings = (
            self.si_reference_bindings
            if self.active_profile == self.si_reference_bindings_descriptor
            else None
        )
        return GateContext(
            cur=cur, store=self.store, authority=self.authority,
            context_assembler=self.context, materializer=self.materializer,
            products=self.products, active_profile=self.active_profile,
            policy_provider=policy_provider,
            si_reference_bindings=si_reference_bindings,
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

    def _assert_timeless_route_runtime(self, farm_ref: str) -> None:
        unsupported = active_time_bounded_profile_routes(
            self.profile_route_records,
            tenant_ref=self.tenant_ref,
            farm_ref=farm_ref,
        )
        if unsupported:
            route_ids = ", ".join(route.route_id for route in unsupported)
            raise ProfileRuntimeError(
                "route-backed runtime does not support active time-bounded "
                "profile routes before an accepted route-evaluation time "
                f"policy exists: {route_ids}")

    def _bind_route_resolution(self, ctx: GateContext, resolution) -> None:
        descriptor = resolution.descriptor
        bindings = SIReferenceBindings.from_descriptor(descriptor)
        products = ProductRegister(bindings)
        products.load_from_store(ctx.store)
        ctx.profile_route_resolution = resolution
        ctx.active_profile = descriptor
        ctx.policy_provider = profile_policy.DescriptorPolicyProvider(descriptor)
        ctx.context_assembler = ContextAssembler(
            ctx.store,
            active_descriptor=descriptor,
        )
        ctx.materializer = Materializer(ctx.store, active_descriptor=descriptor)
        ctx.products = products
        ctx.si_reference_bindings = bindings

    def _resolve_profile_route(self, ctx: GateContext):
        try:
            farm_ref = self._route_farm_ref(ctx)
            self._assert_timeless_route_runtime(farm_ref)
            resolution = resolve_profile_route(
                self.profile_route_registry,
                self.selected_profile_package_names,
                self.profile_route_records,
                tenant_ref=self.tenant_ref,
                farm_ref=farm_ref,
            )
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
        self._bind_route_resolution(ctx, resolution)
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
