# GO + GLMC 7 Currentness Policy

Status: profile currentness policy for
`policy:nl.go-glmc7.currentness.2026.v0_1`. This is package material, not OFARM
Core law.

## Currentness Rules

- Law and crop-code interpretation are claim-year-versioned to 2026.
- GO submission proof is transaction-time evidence and must preserve the filed
  artefact or submission proof for the send event being relied on.
- Parcel and crop facts for the 2026 GO must preserve the 15 May 2026
  `peildatum` context.
- Historical 2023-2025 parcel and crop facts must be source-preserved by year.
  Later public state may not overwrite or silently repair history.
- Mutable RVO layers, parcel data, crop-code lists, and guidance-derived
  reference surfaces must be snapshotted before use when they are relied on.
- Public current-state data is never sufficient by itself for high-consequence
  promotion. It may corroborate transaction-time or claim-year evidence.
- Direct Wettenbank/Wetten.nl consolidated text capture is audit hardening, not
  required for this amendment-chain release posture.
- No derived projection, materialized table, view cache, or export may become a
  hidden truth store. Current state must remain derived from assertion/history
  with receipts.

## Refusal Bias

When freshness cannot be proven for the law version, GO filing artefact,
Gewascodelijst version, parcel history, sand/loess source, rustgewas evidence,
exemption proof, or delegation authority, the assertion refuses or routes to
review. It must not silently promote from stale or ambiguous evidence.

