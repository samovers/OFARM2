# MP7 Profile Extension Boundary Decision

Status: documentation-only decision record. This file does not change runtime
behavior, active-profile selection, route resolution, contracts, schemas,
manifests, active artifact sets, evidence files, adapters, or profile package
substance.

## Decision

OFARM should distinguish standalone second-profile activation from same-farm
profile extension or profile composition before MP7.7.

MP7.7 may activate a second runtime profile only when a submission is governed
by exactly one routed runtime profile. If the same submission must be governed
by a base profile plus an additional governed program, MP7.7 must stop and a
separate profile-extension design is required.

The motivating case is a Slovenian tenant where the same farm may have both
ordinary/conventional activity and organic fields or products. If OFARM only
stores an organic label for display or reporting, that can remain tenant or farm
configuration. If OFARM decides whether an operation, crop, parcel, product, or
claim may be treated as organic, organic becomes a governed program surface and
needs profile-extension semantics.

## Canonical OFARM Alignment

This decision is aligned with existing canonical OFARM material in
`samovers/OFARM`. It does not introduce a new composition theory.

Relevant canonical materials include:

- `01_companion_artifacts/OFARM_Pack_Safety_and_Compatibility_Policy_v0_2.md`,
  which treats compatibility as a `PackActivationSet` question over active
  packs, active profiles, active scoped extensions, scope, time, and precedence.
- `02_accepted_rfcs/OFARM_Pack_Merge_Semantics_RFC_v0_1.md`, which defines
  surface-specific merge modes such as `STRONGEST_REQUIREMENT` for cumulative
  evidence-policy requirements and `HARD_FAIL` for contradictory requirements.
- `02_accepted_rfcs/OFARM_ContextSnapshot_Closure_RFC_v0_1.md`, which says
  context snapshots must account for active pack/profile/scoped-extension
  changes and relevant merge-resolution traces.
- `02_accepted_rfcs/OFARM_Agronomic_Code_Binding_and_Standards_Profile_RFC_v0_1.md`,
  which treats certificates, accreditation, and provenance wrappers as
  attestation surfaces, not as Core truth by themselves.
- `04_implementation_and_conformance/examples_and_fixtures/examples/machine_contracts/agronomic/OFARM_PackCompatibilityDeclaration_example_slovenia_organic_orchard_merge_v0_1.json`,
  which already models a Slovenia + organic + orchard case as
  `COMPATIBLE_WITH_DECLARED_MERGE`.
- `04_implementation_and_conformance/examples_and_fixtures/examples/machine_contracts/agronomic/OFARM_PackMergePolicy_example_evidence_policy_organic_orchard_v0_1.json`,
  which models organic certification evidence as primary while allowing
  compatible orchard evidence to be added through `STRONGEST_REQUIREMENT`.
- `04_implementation_and_conformance/examples_and_fixtures/examples/machine_contracts/agronomic/OFARM_PackMergeResolutionTrace_example_field_17_orchard_evidence_merge_v0_1.json`,
  which records the governed merge trace for that evidence-policy composition.

Those canonical materials support the same boundary recorded here: organic or
other certification-program behavior should be modeled through governed
pack/profile/scoped-extension composition when it combines with a base profile.
It should not be smuggled into MP7.7 as a standalone second-profile activation
unless it can govern the routed submission by itself.

## Vocabulary

| Term | Meaning | Boundary |
| --- | --- | --- |
| Tenant | The operating/customer boundary using OFARM. | A tenant is not a profile by itself. |
| Base runtime profile | The routed profile that supplies the normal governed runtime rules for a submission. | Current example: `profile_si_ffs`. |
| Standalone second profile | A second runtime profile that can govern a routed submission by itself. | This is the only kind of second profile MP7.7 may activate. |
| Profile extension | Additional governed rules that apply on top of a base runtime profile for a program, certification, product line, or claim type. | Not supported by MP7.7 activation semantics. |
| Tenant or farm configuration | Settings, labels, preferences, or stored facts that do not change governed evidence floors, refusal rules, legal refs, or output claims. | Does not count as a second profile. |
| Program scope | The field, parcel, product, claim, certification, or commit-class condition that decides whether an extension applies. | Needs explicit design before runtime use. |

## Classification Rule

Treat a difference as tenant/farm configuration when it only changes:

- UI labels;
- reporting filters;
- user preferences;
- stored non-governing facts;
- tenant deployment settings;
- ordinary crop or product metadata that does not affect a governed decision.

Treat a difference as a profile extension when it changes any of:

- required evidence;
- source currentness rules;
- refusal or retain-draft behavior;
- policy refs;
- legal or authority refs;
- certification or program status checks;
- manifest capability grounding;
- output or audit claims;
- sufficiency cases;
- validator routing;
- profile executed-evidence expectations.

Treat a difference as a standalone second profile only when one routed profile
can govern the submission without needing to merge with another active profile
for the same tenant/farm/claim context.

## Organic Program Implication

A Slovenian farm may have both organic and non-organic activity. That does not
automatically create two tenants, and it does not automatically create two
standalone runtime profiles.

If an event is simply an ordinary SI farm operation, `profile_si_ffs` can remain
the governing base profile.

If an event claims organic status, OFARM likely needs both:

- the base SI farm/field/operation checks; and
- organic program checks such as certificate, validity period, subject/scope
  match, product or production category, control-body/authority status, and
  adverse or suspended status.

In that case, the organic surface is best treated as a future profile extension
or governed program slice, not as an MP7.7 standalone second profile.

Missing organic evidence should refuse or retain draft for the organic claim. It
should not automatically make the underlying non-organic farm operation invalid
unless the submitted claim itself depends on organic status.

## MP7 Impact

MP7.7 must not be used to implement same-farm profile merging, base-plus-organic
composition, or program-extension semantics.

MP7.7 may proceed only for a candidate runtime profile that can satisfy all
MP7.5/MP7.6 readiness checks and govern a route independently. If the candidate
needs to be combined with `profile_si_ffs` for the same tenant/farm submission,
the correct next step is a new profile-extension design track.

Before any profile extension is implemented, OFARM needs a separate accepted
design for:

- how an extension declares its base profile;
- how route predicates select the extension by commit class, program, product,
  parcel, field, time, or claim;
- how base and extension policies compose;
- how evidence floors merge without weakening either surface;
- how refusal reasons distinguish base-profile failure from extension failure;
- how materialization and output metadata name both governing surfaces;
- how manifests and profile executed evidence prove extension behavior;
- how conflicts between base and extension refs are rejected;
- how the extension remains tenant/farm scoped without becoming a universal
  country abstraction.

## Stop Conditions

Stop and re-plan if a future PR would:

- activate an organic or certification-program surface as a standalone profile
  while it still depends on base SI runtime checks;
- route one submission through two profiles without an accepted composition
  model;
- treat organic status as only a label while using it to make governed
  decisions;
- merge evidence floors from two profiles ad hoc;
- let an extension weaken base-profile refusals;
- claim profile-extension readiness through README files, navigation indexes,
  source manifests, or design plans;
- add organic manifest capability claims without generated or generator-verified
  grounding and executed evidence.

## Non-Claims

This decision record does not claim or create:

- profile-extension runtime support;
- organic runtime support;
- Slovenian organic production readiness;
- second-profile activation;
- multi-profile runtime readiness;
- manifest generation changes;
- evidence writing;
- active artifact set updates;
- schema or contract changes;
- a universal country abstraction layer;
- legal advice.

## Validation

For this docs-only decision record, run:

```sh
python3 conformance/ofarm_profile_extraction_consistency_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --cached --check
```
