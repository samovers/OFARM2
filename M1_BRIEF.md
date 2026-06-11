# M1 brief — build the Kernel

Status at handoff (2026-06-12): **M0 CLOSED.** The legal field basis is verbatim-verified, the register snapshot pipeline exists and parsed 623 real products, the parcel onboarding path is round-trip-proven (856,677-record layer, 4/4 PIDs), the SI code-binding profile instance is cut and schema-validated, and both real `ReferenceSnapshot`s sit in the context spine. Nothing in this brief rests on an unverified assumption. Pilot season is 2027 (D13) — build carefully, not hastily.

## The target

A running Kernel: PostgreSQL append-only truth store + the gate pipeline + the materializer, conformant per `KERNEL.md` §"Kernel conformance" and green against `conformance/CONFORMANCE.md` (tests 1–15, fixtures replayed live).

Stack (decided, D10): Python 3.11+ / FastAPI / PostgreSQL / pytest. Repo layout suggestion: `kernel/` (store, gates, materializer, api), `kernel/tests/` (the conformance suite wired to the fixtures).

## Ordered tasks

1. **Absorb the explainable-evidence RFC** (`reference/rfcs/OFARM_Performance_and_Explainable_Current_State_Evidence_RFC_v0_1.md`, contracts in `contracts/drafts_reference/explainable_current_state_evidence/`): read before designing the materializer. Implement the shapes of `MaterializationKey`, `MaterializationFreshnessVector`, `MaterializationDependencyIndex`, `InvalidationEvaluationTrace` behind Kernel law — draft/non-default, so implement, don't promote (D16).
2. **Store schema**: append-only record tables for the Kernel contracts; JSONB payload validated against `contracts/kernel/` on write; explicit edge table (authority, evidence, review, lineage, materialization refs); payload sha256 + schemaVersion + schema hash per record; gate-log/outbox table; the `PromotionTrace` reachability link written in-transaction (D3).
3. **Gate pipeline**: ingress normalization → authority (default deny; `AuthorizationDecision*` envelopes; revocation re-check) → validation sub-gates (schema, semantic/carrier, reference-resolution, temporal-conformance, code-binding vs. the SI profile instance, registry verification) → static profile applicability (`ContextSnapshot` assembly from the shipped instances) → evidence sufficiency (auto-generated `EvidenceSufficiencyCase` from the policy template) → review/promotion (self-review per D8) → materialization → publication gates. Every refusal = `RuntimeProblem` with a reason code.
4. **Materializer**: deterministic in-force-records → current state + `MaterializationBasis` + freshness; basis-set invalidation (D12); dependency index + freshness vector + invalidation traces per task 1.
5. **Conformance green**: wire the 8 gate-sequencing fixtures to run against the live store; implement tests 1–15 from `conformance/CONFORMANCE.md`; keep `ofarm_pkg_contract_check.py` passing. Results land as JSON evidence files — never claim what isn't executed (AGENTS.md rule 7).
6. **Static views**: author the two QuerySpecification + QueryPlanIR JSON artifacts against `views/VIEWS.md` and the real store; wire `PassportViewMetadata` / `DocumentAssemblyMetadata` emission with `ResultQualificationEnvelope`s and refusal behavior.
7. **Capability Manifest**: generate `manifest:si.ffs.pilot.v0_1` from the actual runtime surfaces, declaring every unsupported surface (`PLATFORM.md` list); regenerate `ActiveArtifactSet` to reference real artifacts; verify with the manifest-grounding pattern.

## Definition of done

An engineer (or agent) who has never seen the canonical repository can: commit a spray-record operation claim through the full gate chain using the SI profile and the fictional onboarding example; watch it refuse correctly when the evidence floor is unmet, authority is revoked, or the snapshot binding breaks; promote it via self-review; query a FRESH materialized register whose basis resolves completely; and export a frozen register that refuses when it should. Tests 1–15 green, fixtures green, self-check green.

## Out of scope for M1 (do not drift)

Mobile app (M3) · registry adapter scheduling (M2 — the parser exists, reuse it) · GERK importer (M2) · dynamic packs · public query compiler · AI/agent runtime · anything in `PLATFORM.md`'s unsupported-surfaces list · any law edit (ERRATA only) · any personal data (AGENTS.md rule 1).
