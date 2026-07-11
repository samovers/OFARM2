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
from .context import (ContextAssembler, ProductRegister, SIReferenceBindings,
                      mint, now_iso, parse_ts)
from .contracts import sha256_of
from .emission import PromotionTraceWriter, ReplayWriter
from .materializer import Materializer
from .problems import runtime_problem
from .runtime_bundle import RuntimeBundleError, require_store_runtime_bundle
from .profile_runtime import (ProfileRuntimeError, resolve_active_descriptor,
                              profile_route_selection_document,
                              resolve_profile_route)
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
    _SEALED_FIELDS = {
        "store", "route_backed", "profile_route_records",
        "profile_route_registry", "selected_profile_package_names", "tenant_ref",
        "active_profile", "runtime_bundle", "policy_provider",
        "si_reference_bindings", "si_reference_bindings_descriptor", "authority",
        "context", "materializer", "products",
    }

    def __setattr__(self, name, value):
        if (getattr(self, "_runtime_composition_sealed", False)
                and name in self._SEALED_FIELDS):
            raise AttributeError("GatePipeline runtime composition is immutable")
        object.__setattr__(self, name, value)

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
        runtime_bundle=None,
    ):
        if product_register is not None:
            raise ProfileRuntimeError(
                "caller-supplied ProductRegister is forbidden for governed runtime")
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
        self.profile_route_records = (
            tuple(profile_route_records) if profile_route_records is not None else None)
        self.profile_route_registry = profile_route_registry
        self.selected_profile_package_names = (
            tuple(sorted(selected_profile_package_names))
            if selected_profile_package_names is not None else None)
        self.tenant_ref = tenant_ref
        if (active_descriptor is not None and active_profile is not None
                and active_descriptor != active_profile):
            raise ProfileRuntimeError(
                "active_descriptor and active_profile refer to different descriptors")
        self.active_profile = resolve_active_descriptor(
            active_descriptor if active_descriptor is not None else active_profile,
            allow_config_default=True,
        )
        self.runtime_bundle = runtime_bundle or store.runtime_bundle
        require_store_runtime_bundle(store, self.runtime_bundle, "GatePipeline")
        if self.route_backed and self.tenant_ref != self.runtime_bundle.tenant_ref:
            raise ProfileRuntimeError(
                "profile route tenant must exactly match the RuntimeBundle tenant")
        if self.route_backed:
            if any(route.runtime_bundle_digest != self.runtime_bundle.digest
                   for route in self.profile_route_records):
                raise ProfileRuntimeError(
                    "every profile route must receipt the exact RuntimeBundle digest")
            route_selection = profile_route_selection_document(
                self.profile_route_registry,
                self.selected_profile_package_names,
                self.profile_route_records,
                tenant_ref=self.tenant_ref,
            )
            try:
                retained_route_selection = self.runtime_bundle.json_component(
                    "PROFILE_ROUTE_SELECTION", "profile-route-selection:active")
            except RuntimeBundleError as exc:
                raise ProfileRuntimeError(
                    "route-backed runtime lacks a retained profile route selection") \
                    from exc
            if route_selection != retained_route_selection:
                raise ProfileRuntimeError(
                    "caller profile route selection differs from the RuntimeBundle")
        if self.runtime_bundle.descriptor != self.active_profile:
            raise ProfileRuntimeError(
                "GatePipeline descriptor and RuntimeBundle do not match exactly")
        self.policy_provider = profile_policy.DescriptorPolicyProvider(
            self.active_profile, runtime_bundle=self.runtime_bundle)
        self.si_reference_bindings = SIReferenceBindings.from_descriptor(
            self.active_profile, runtime_bundle=self.runtime_bundle)
        self.si_reference_bindings_descriptor = self.active_profile
        self.authority = AuthorityEvaluator(store)
        self.context = ContextAssembler(
            store, active_descriptor=self.active_profile,
            runtime_bundle=self.runtime_bundle)
        self.materializer = Materializer(
            store, active_descriptor=self.active_profile,
            runtime_bundle=self.runtime_bundle)
        self.products = ProductRegister(
            self.si_reference_bindings, runtime_bundle=self.runtime_bundle)
        self.products.load_from_store(store)
        self.products.freeze()
        self._runtime_composition_sealed = True

    def _assert_runtime_composition(self) -> None:
        require_store_runtime_bundle(
            self.store, self.runtime_bundle, "GatePipeline decision")
        expected_policy_refs = \
            profile_policy.DescriptorPolicyProvider.expected_recognized_rule_refs(
                self.active_profile)
        if (self.runtime_bundle.descriptor != self.active_profile
                or self.policy_provider.descriptor != self.active_profile
                or self.policy_provider.runtime_bundle is not self.runtime_bundle
                or self.policy_provider.policy_ref !=
                self.active_profile.evidence_policy_ref
                or self.policy_provider.recognized_rule_refs != expected_policy_refs
                or self.si_reference_bindings_descriptor != self.active_profile
                or self.context.store is not self.store
                or self.context.runtime_bundle is not self.runtime_bundle
                or self.materializer.store is not self.store
                or self.materializer.runtime_bundle is not self.runtime_bundle
                or self.materializer.context.store is not self.store
                or self.materializer.context.runtime_bundle is not self.runtime_bundle
                or self.products.runtime_bundle is not self.runtime_bundle
                or self.products.bindings != self.si_reference_bindings
                or self.authority.store is not self.store):
            raise RuntimeBundleError(
                "GatePipeline runtime composition changed after construction")

    # ======================================================================
    # the governed front door
    # ======================================================================

    def commit(self, submission: dict) -> dict:
        """Run one capture through the full chain. Returns the
        CommitIngressResult payload. One call = one transaction (D3)."""
        self._assert_runtime_composition()
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
            runtime_bundle=self.runtime_bundle,
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
        descriptor = resolution.descriptor
        if descriptor != self.runtime_bundle.descriptor:
            raise ProfileRuntimeError(
                "profile route targets a descriptor outside the prebuilt RuntimeBundle; "
                "hot bundle construction is forbidden")
        ctx.profile_route_resolution = resolution
        ctx.active_profile = descriptor
        ctx.runtime_bundle = self.runtime_bundle
        ctx.policy_provider = self.policy_provider
        ctx.context_assembler = self.context
        ctx.materializer = self.materializer
        ctx.products = self.products
        ctx.si_reference_bindings = self.si_reference_bindings

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
                runtime_bundle_digest=self.runtime_bundle.digest,
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
