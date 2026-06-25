# Serbian Database-Copy Adapter Boundary Plan

Status: documentation-only boundary plan for Serbian adapter rehearsal. This file
does not add runtime code, adapters, database files, fixtures with real data,
manifests, evidence files, contracts, schemas, profile descriptors, active
selections, or platform behavior.

Boundary status:
`SERBIAN_DATABASE_COPY_ADAPTER_REHEARSAL_ONLY`

This plan records how a private copy of a Serbian farm database may be used for
schema discovery and adapter rehearsal without converting that copy into Serbia
runtime support, official evidence, production truth, profile readiness, or
compliance decisioning.

## Status Labels

The copied Serbian database and any local adapter rehearsal work using it must
carry all of these labels:

| Label | Meaning |
| --- | --- |
| `SERBIAN_DATABASE_COPY_ADAPTER_REHEARSAL_ONLY` | The copy may support local adapter rehearsal, schema discovery, and platform-development learning only. |
| `not production evidence` | Copied rows, local notes, local adapter output, and rehearsal logs are not OFARM evidence. |
| `not live official truth` | The copy is not an official eRPG, Ministry, ATS, adverse-status, or certificate source. |
| `not Serbia runtime readiness` | The copy does not prove that Serbia runtime support, adapters, route behavior, evidence lanes, or manifest grounding exist. |
| `not profile activation` | The copy does not activate `profile_rs_organic_crop` or any Serbia active profile selection. |
| `not legal advice` | Nothing derived from the copy may be presented as legal, certification, compliance, or production advice. |

These labels apply even when local adapter code can parse tables, reconcile
columns, or emit rehearsal-shaped records.

## Allowed Uses

The copied database may be used locally and privately for these purposes only:

- schema discovery;
- adapter mapping rehearsal;
- data-quality exploration;
- synthetic or redacted fixture design;
- platform rehearsal mode;
- privacy and redaction planning.

Allowed use does not authorize committing real data, creating official evidence,
claiming capability, or selecting Serbia as an active runtime profile.

## Forbidden Uses

This PR and any follow-on rehearsal work must not include or claim any of the
following:

- committed real database dump;
- real BPG, JMBG, MB, PIB, parcel IDs, certificate numbers, addresses,
  signatures, screenshots, document dates, or filenames containing identifiers;
- AI-tool exposure of real identifiers unless separately approved and redacted;
- generated evidence;
- manifest capability claim;
- `runtime_profile_descriptor.json`;
- Serbia active profile selection;
- live registry truth claim;
- production or compliance decision claim.

The same prohibition applies to PR bodies, review comments, commit messages,
issue comments, screenshots, local logs pasted into GitHub, and example
filenames.

## Future Adapter Posture

A later adapter prototype may be considered only as a separate implementation
PR. This plan does not implement or approve that adapter.

If a future adapter reads the copied database, its outputs must be explicitly
marked as copied-database rehearsal records. The output label must survive in
logs, fixture-generation notes, debug views, and any local platform rehearsal UI
or export.

Imported rows from the copied database are not official current state. They must
not be promoted as Serbian farm registration status, organic certificate status,
certifier authority status, adverse-status proof, or production-grade profile
state.

Official or live eRPG, Ministry, ATS, adverse-status, and certificate sources
remain required before production-grade Serbian organic decisions can be made.
The copied database may help design mappings and identify data-quality issues,
but it cannot close the source-packet blockers already listed in
`profile_rs_organic_crop/README.md` and
`profile_rs_organic_crop/source_packet_extracts/source_manifest.json`.

Any future adapter prototype must remain rehearsal-only until separate profile
readiness work supplies, at minimum, explicit descriptors, policy hooks,
adapters, tests, evidence-lane grounding, manifest grounding, and source-packet
closure for the relevant Serbian decision surface.

## Privacy Gates Before Any Implementation

Before any implementation PR is opened, all of these gates must be true:

- the copied database stays outside the repository;
- access to the copy is limited to approved local/private users and machines;
- logs, screenshots, console output, and debug exports are identifier-safe;
- committed tests use synthetic or redacted fixtures only;
- PR bodies do not include real identifiers or screenshots;
- local rehearsal mode has clear `copied data / non-production` labeling;
- no file path, fixture name, test name, or screenshot filename includes a real
  person, farm, company, parcel, certificate, address, or document identifier;
- pasted AI prompts and AI-tool inputs contain only synthetic, masked, or
  separately approved redacted values.

If any gate fails, the implementation must stop before commit or PR publication.

## Repository Boundary

This plan is confined to `profile_rs_organic_crop/` because Serbian identifiers,
source posture, currentness policy, and evidence rules are profile-local. It does
not change Core, Kernel, Platform, SI profile behavior, generated manifests,
contracts, schemas, adapters, evidence, or active runtime selection.

The plan preserves the current profile posture:
`RS_ORGANIC_CROP_FARM_REG_CERT_IMPLEMENTATION_CANDIDATE_PRODUCTION_HOLD`.

## Required Follow-On Shape

The next implementation PR, if any, should be an adapter prototype in rehearsal
mode using synthetic or redacted fixtures only. It should explicitly refuse to
produce Compliance Twin promotions, generated evidence, manifest capability
claims, or Serbia runtime readiness claims from copied-database rows.

A future rehearsal-mode adapter should make these distinctions machine-visible:

| Surface | Rehearsal copy posture | Production posture |
| --- | --- | --- |
| Parsed database row | Copied-database rehearsal record only | Not sufficient by itself |
| Reconciled table or column mapping | Adapter-design input | Not evidence |
| Generated synthetic fixture | Test support | Not official evidence |
| Redacted fixture | Test support after review | Not official evidence |
| Official eRPG, Ministry, ATS, adverse-status, or certificate artefact | Still required | Required source or corroboration according to profile policy |

## Stop Conditions

Stop and re-plan if a future PR would:

- commit a real Serbian database dump or extracted sample;
- include real Serbian identifiers in code, tests, logs, screenshots, filenames,
  PR text, or AI-visible material;
- treat copied rows as official current state;
- produce generated evidence from copied rows;
- add a manifest capability claim for Serbia from copied-database rehearsal;
- add `runtime_profile_descriptor.json` for Serbia without separate readiness
  closure;
- select Serbia as an active runtime profile;
- claim live registry integration, production readiness, compliance decisioning,
  legal advice, or profile activation from this rehearsal work;
- use copied data to close source-packet blockers that require official or live
  source artefacts.

## Validation

For this docs-only boundary plan, run:

```sh
python3 -m json.tool profile_rs_organic_crop/source_packet_extracts/source_manifest.json
python3 conformance/ofarm_profile_extraction_consistency_check.py
python3 conformance/ofarm_pkg_contract_check.py
git diff --check
git diff --cached --check
```

Do not run pytest unless explicitly requested. If pytest is run and creates a
`conformance/evidence/platform_mvp_results_*.json` file, remove the generated
file before commit.

Manual review must confirm that all new Serbia material stays under
`profile_rs_organic_crop/`, no real Serbian identifiers, screenshots, database
samples, filenames, or document examples are committed, and the PR does not add
runtime code, adapters, manifests, evidence, contracts, schemas, or active
profile descriptors.
