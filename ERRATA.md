# Errata register

The **only** file in this package that accumulates law feedback during implementation. The law freeze holds: findings are recorded here, never patched into reference copies or canonical files. One consolidated amendment after the pilot processes this register.

Rules:
1. One entry per finding; never edit reference copies or extracted contracts in place.
2. An extraction bug (package text contradicts canonical law) is resolved against the canonical repository and recorded here.
3. A law bug (canonical law contradicts implementation reality) is recorded here with evidence and **worked around within law** until the post-pilot amendment.

| ID | Date | Class (EXTRACTION_BUG / LAW_FRICTION / CONTRACT_GAP) | Finding | Evidence | Interim handling |
|----|------|------------------------------------------------------|---------|----------|------------------|
| E-000 | 2026-06-11 | (example row — delete when first real entry lands) | — | — | — |

Provenance note: this package's kernel rules already incorporate two pre-implementation corrections accepted during plan review — twin metadata attaches to materialization/promotion/output paths rather than every substrate record, and commit class lives on the ingress boundary (`CommitIngressRequest`/`PromotionTrace`), not on `AssertionRecord`. See `KERNEL.md`.
