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
from .context import ContextAssembler, ProductRegister, mint, now_iso
from .contracts import sha256_of
from .emission import PromotionTraceWriter, ReplayWriter
from .materializer import Materializer
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
    def __init__(self, store, product_register: ProductRegister | None = None):
        self.store = store
        self.authority = AuthorityEvaluator(store)
        self.context = ContextAssembler(store)
        self.materializer = Materializer(store)
        self.products = product_register or ProductRegister()
        self.products.load_from_store(store)

    # ======================================================================
    # the governed front door
    # ======================================================================

    def commit(self, submission: dict) -> dict:
        """Run one capture through the full chain. Returns the
        CommitIngressResult payload. One call = one transaction (D3)."""
        try:
            with self.store.tx() as cur:
                return self._commit_in_tx(cur, submission)
        except psycopg.errors.UniqueViolation:
            # a concurrent commit won the idempotency-key race; our transaction
            # rolled back completely — serve the replay path against the winner
            with self.store.tx() as cur:
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
        return GateContext(
            cur=cur, store=self.store, authority=self.authority,
            context_assembler=self.context, materializer=self.materializer,
            products=self.products, sub=sub,
            request_id=mint("cir"), ingested_at=now_iso(),
            source_digest=self._source_digest(sub),
            commit_class=sub["commitClass"], farm_ref=sub["farmRef"],
            acting_party=sub["actingPartyRef"], idem_key=sub["idempotencyKey"],
            event_id=mint("event"), assertion_id=mint("assert"))

    def _commit_in_tx(self, cur, sub: dict) -> dict:
        ctx = self._new_context(cur, sub)

        ingress = IngressNormalizer().run(ctx)
        if isinstance(ingress, GateReplay):
            return ingress.result

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
