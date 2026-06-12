# Errata register

The **only** file in this package that accumulates law feedback during implementation. The law freeze holds: findings are recorded here, never patched into reference copies or canonical files. One consolidated amendment after the pilot processes this register.

Rules:
1. One entry per finding; never edit reference copies or extracted contracts in place.
2. An extraction bug (package text contradicts canonical law) is resolved against the canonical repository and recorded here.
3. A law bug (canonical law contradicts implementation reality) is recorded here with evidence and **worked around within law** until the post-pilot amendment.

| ID | Date | Class (EXTRACTION_BUG / LAW_FRICTION / CONTRACT_GAP) | Finding | Evidence | Interim handling |
|----|------|------------------------------------------------------|---------|----------|------------------|
| E-001 | 2026-06-12 | CONTRACT_GAP | The RuntimeProblem reason-code registry (RFC v0.1) defines no code for temporal-conformance failures (unparseable event time, event time outside plausibility window), although temporal-conformance is a named validation sub-gate (Platform RC2.1 / PLATFORM.md) and the registry RFC §6 forbids unregistered codes. | M1 gate implementation: `kernel/gates.py` temporal sub-gate; registry families enumerated in `reference/rfcs/OFARM_RuntimeProblem_Reason_Code_Registry_RFC_v0_1.md` §3 cover authority/evidence/identity/unit/materialization/query/publication/pack/import/retry/permission/correction — nothing temporal. | `EVIDENCE_INSUFFICIENT` used with explanatory detail text naming this entry; post-pilot amendment should add a temporal family (e.g. `EVENT_TIME_UNPARSEABLE`, `EVENT_TIME_IMPLAUSIBLE`). |

Provenance note: this package's kernel rules already incorporate two pre-implementation corrections accepted during plan review — twin metadata attaches to materialization/promotion/output paths rather than every substrate record, and commit class lives on the ingress boundary (`CommitIngressRequest`/`PromotionTrace`), not on `AssertionRecord`. See `KERNEL.md`.
