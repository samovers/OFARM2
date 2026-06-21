# Core-Neutral Rewording Candidates

These are candidate wording replacements for a later neutrality-hardening PR. They are not applied in this PR.

| Current wording pattern | Candidate profile-neutral wording | Notes |
| --- | --- | --- |
| `KMG-MID` when used as a Core identity example | `profile-specific holding identifier` | The SI profile can still bind this to KMG-MID. |
| `KMG` when used as a Slovenian holding shorthand | `profile-specific holding` or `holding under the active profile` | Avoid making Slovenian farm-register vocabulary a Core concept. |
| `GERK` when used as a Core parcel example | `profile-specific parcel identifier` | The SI profile can still bind this to GERK. |
| `GERK-PID` when used as a privacy or fixture example | `profile-specific parcel id` | Use only fictional, format-true examples when a concrete profile fixture is required. |
| `SI profile binding` in generic Core tables | `profile binding` | Keep `SI` only in profile-local docs or explicit examples. |
| `per SI self-review policy` | `per the active profile review policy` | Preserves governed review without naming one country profile. |
| `SI evidence floor` | `active profile evidence floor` | Use where the loader or gate is intended to be profile-neutral. |
| `SI currentness policy` | `active profile currentness policy` | Use only if the statement is not intentionally describing the current SI pilot. |
| `UVHVVR register` or `Seznam registriranih FFS` in Core-facing code-binding examples | `profile-specific product authorization register` | Concrete authority and register names belong in `profile_si_ffs/`. |
| `REGSR` or `FFSNaprave` as generic adapter examples | `profile-specific source system` or `profile-specific evidence source` | Keep concrete source-system names in profile adapter docs. |
| `Slovenia pilot` where a generic runtime principle is meant | `active profile pilot` or `current pilot profile` | Do not rewrite root claim-limit text unless the repo posture changes. |
| `Slovenian source expectation` in generic refusal text | `profile-specific source expectation` | Keep the refusal invariant while moving jurisdictional detail to the profile. |

## Suggested Neutral Sentence Shapes

- Core identity: "A farm identity may carry a profile-specific holding identifier as a governed binding; Core does not make any national identifier universal law."
- Core parcel identity: "A field identity may carry a profile-specific parcel identifier as a governed binding; Core does not make any national parcel scheme universal law."
- Evidence floor: "Promotion requires the evidence floor declared by the active profile and captured as transaction-time evidence."
- Currentness: "Mutable public data may corroborate a claim, but it is not sufficient by itself for high-consequence promotion unless captured under the active profile currentness policy."
- Source systems: "Profile adapters may bind to profile-specific evidence sources, registers, or reference datasets without making those sources Core law."

