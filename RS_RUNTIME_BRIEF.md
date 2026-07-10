# First Serbian Runtime Brief

Status: binding implementation-local planning for RS0 / issue #158. This brief
is not OFARM law, not a contract, not a runtime descriptor, not legal advice,
and not a capability or production-readiness claim.

Decision date: 2026-07-10.

## Decision Summary

The first Serbian runtime is a **narrow standalone profile** for one all-organic
crop farm. It governs only:

- farm/holding registration evidence and status;
- organic certificate evidence and status;
- organic certifier authority references; and
- corrections, review, objection, contest, and supersession of those records.

It does not govern fields, crop cycles, equipment, inputs, field operations,
transport, operational registers, mobile/PWA capture, or offline sync. Those
surfaces have no Serbian source, evidence, currentness, parser, or refusal floor
in this repository and must not be added by analogy with Slovenia.

The profile shape is **A: one standalone first-deployment profile**. Every
supported submission is governed by that one profile. The first scope does not
need ordinary Serbian operational rules plus an organic extension for the same
submission. If that becomes a requirement, this decision no longer applies:
MP7.7 must stop and a separate profile-composition design track is required.

`profile_rs_organic_crop/` remains the narrow design/source package created by
#131. It is input to a new, explicitly versioned standalone runtime package; it
is not renamed, silently broadened, given a descriptor, or activated in place.
The new package identity is to be fixed in the later disabled-descriptor slice,
after its genuinely applicable runtime inputs are known.

When activation is eventually justified, the deployment selects **RS only**.
SI remains in the repository as regression/reference material, but is disabled,
unselected, and unrouted in that deployment. Concurrent SI and RS execution is
not a first-deployment requirement.

## Greenfield Replacement Posture

Nothing is deployed and there is no production data to migrate. Internal code,
SI-shaped service names, candidate package structure, deployment configuration,
and implementation-only interfaces may therefore be replaced where a cleaner
RS boundary needs it. There is no external backward-compatibility requirement.
SI regression checks remain useful during construction because they expose
hidden profile coupling; they are not a deployed compatibility promise.

That cheap replacement posture does **not** relax the boundaries that create
truth and authority:

- canonical law and read-only `reference/**` material remain governed;
- extracted or candidate contracts are not promoted by implementation;
- authentication remains distinct from authority and delegation;
- missing Serbian sources remain missing;
- live current state does not become historical evidence;
- design cases do not become executed evidence;
- a successful OFARM review does not become a government or certification
  decision; and
- capability and output claims remain limited to what source-backed runtime
  evidence proves.

Greenfield means implementation can be replaced cheaply. It does not turn an
assumption into Serbian law, an unpreserved web page into evidence, or an OFARM
record into an official decision.

## First-Deployment Scope

| Surface | Decision | First-deployment boundary |
| --- | --- | --- |
| Farm/holding onboarding and identity | **IN, narrowly** | Create only the farm/operator identity and holding identifier linkage needed to submit and reconcile a registration-status assertion. No full farm master-data, subsidy, parcel, or annual-declaration workflow. |
| Deployment bootstrap and control plane | **IN as an activation prerequisite** | Before the first profile submission, a governed pre-provisioning ceremony creates the tenant, Party/Farm identities, holder linkage, tenant/farm route, initial submit/review grants, and any initial read-only sharing. This is generic control-plane work, not a fifth Serbian profile commit surface. |
| Farm registration status | **IN, source-blocked** | Represent an evidence-backed status for a stated transaction date or claim year. A live lookup alone never proves that status. |
| Parcel/field identity and geometry | **OUT** | No Serbian parcel/land-use source, identifier policy, geometry provenance rule, or evidence floor is packeted here. |
| Crop cycles | **OUT** | No crop-cycle submissions or derived crop state. |
| Equipment identity | **OUT** | No equipment registry, inspection, calibration, or operational equipment claim. |
| Planned field operations | **OUT** | No plan/intention workflow. |
| Completed field operations | **OUT** | No operational occurrence, intervention, or execution records. |
| Seed inputs | **OUT** | No seed identity, lot, organic status, use, or compliance claim. |
| Fertiliser inputs | **OUT** | No product identity, application, authorisation, or compliance claim. |
| Soil-improver inputs | **OUT** | No product identity, application, authorisation, or compliance claim. |
| Plant-protection-product inputs | **OUT** | No Serbian product register, application record, authorisation check, or current-compliance claim. The SI REGSR service must not be reused. |
| Water inputs | **OUT** | No irrigation, abstraction, quality, right, or quantity record. |
| Application records | **OUT** | No sowing-independent input application record. |
| Sowing records | **OUT** | No sowing or planting record. |
| Harvest records | **OUT** | No harvest, yield, lot, or stock record. |
| Transport records | **OUT** | No internal movement, dispatch, chain-of-custody, or official transport record. |
| Operator/advisor/reviewer flows | **IN, narrowly** | Farm holder evidence submission, a separately authorised OFARM reviewer, and read-only shared review are in. Employee/operator, contractor, and agronomist/advisor state-affecting workflows are out until delegation evidence is closed. |
| Corrections, rejection, contest, supersession | **IN** | Apply only to the four supported status/authority/review surfaces. Every change appends a new record or decision; nothing is edited in place. |
| Organic certificate/status governance | **IN, source-blocked** | Preserve and evaluate certificate, subject/scope, validity, issuing-body, Ministry, ATS, adverse-status, and review evidence. OFARM neither issues nor decides certification. |
| Certifier authority reference | **IN, source-blocked** | Require both the relevant Ministry authorisation evidence and date/scope-specific ATS accreditation evidence. |
| Registers | **OUT** | No operational, input, crop, parcel, organic-production, or statutory register is claimed. |
| PassportViews | **IN, two bounded views** | A registration-status view and an organic-certificate-status view, each showing evidence time, basis, gaps, review state, and qualification. |
| DocumentAssemblies / export | **IN, one bounded assembly** | A frozen farm-registration and organic-certificate evidence packet for farm-controlled review or sharing. It is not an official filing, certificate, or inspection decision. |
| Inspection outputs | **OUT as official output** | The bounded evidence packet may be shown to an inspector, but it is not an official inspection form, finding, approval, or submission. |
| Offline capture and later sync | **OUT** | No mobile/PWA or offline queue in the first Serbian runtime. A later operational product brief must define idempotency, draft authority, re-check, and conflict behavior before adding it. |
| Live/public registry lookup | **OUT as authority** | No live integration is required. A lookup may later be preserved as corroboration, but it can never be the sole historical or high-consequence basis. |
| Preserved transaction-time artefacts | **IN and required** | Official or controlled artefacts, source identity, retrieval/issue time, effective time, digest, and parser version where applicable form the evidence basis. |

Any expansion of an **OUT** row is a new scope decision. It is not an RS1 seam
extraction detail and must not enter by adapting SI behavior.

## Supported Commit And Action Surfaces

The first runtime supports exactly these profile-local commit surfaces:

1. `rs.farm_holding.registration_assertion`.
2. `rs.organic.certification_status_assertion`.
3. `rs.organic.certifier_authority_reference`.
4. `rs.review.appeal_or_objection_event`.

The names above describe the existing candidate design surfaces. This brief
does not promote them into Core or freeze a machine contract.

An empty deployment has an explicit pre-provisioning prerequisite outside that
four-item profile catalogue. There is no self-service onboarding bootstrap. A
named deployment owner must run a governed bootstrap/control-plane ceremony
that, before any Serbian submission:

1. records the deployment activation decision and the bootstrap principal as an
   explicit implementation trust anchor, not a Serbian public authority;
2. appends the tenant and holder/reviewer Party identities, the Farm identity,
   and the evidence-backed holder-to-farm linkage;
3. appends the one tenant/farm route to the disabled Serbian candidate and only
   activates that route during the later reviewed RS activation ceremony;
4. appends the minimum submit and distinct-review grants, plus any explicitly
   requested read-only SharingGrant; and
5. records a bootstrap receipt naming the owner, records created, scope, time,
   approval basis, and the later revocation/administration owner.

The bootstrap must use a generic governed command/control-plane path and append
records atomically; direct database seeding, role-name authorization, or hidden
configuration truth is forbidden. A correction to Party, Farm, or holder
linkage appends the applicable identity/lifecycle or structure record with
explicit lineage/supersession. A route or grant correction appends a replacement
or revocation; it never edits the original. If the existing contracts and
generic command paths cannot express that ceremony, activation stops for a
separate control-plane design rather than inventing a Serbian exception.

Allowed actions are limited to:

- submit a new assertion/reference/review event with its evidence;
- retain draft or refuse when authority, evidence, identity reconciliation,
  time, source, or currentness is insufficient;
- route each of the four supported submissions to a separately authorised
  OFARM reviewer;
- append `ACCEPT`, `REJECT`, or `CONTEST` review state through the existing
  governed review semantics;
- append a correction that explicitly supersedes the affected in-force record;
- append later objection, appeal, court-challenge, adverse-status, or finality
  evidence without flattening the earlier state; and
- share a qualified view or frozen assembly under an explicit sharing grant.

An `ACCEPT` result means only that the submitted OFARM assertion met the
declared profile evidence floor. It is not organic certification, government
registration, administrative finality, legal compliance, or advice.

Not supported are field/operation commits, input or code bindings, scheduled
live registry imports, official submissions, certificate issuance, inspection
findings created by OFARM, or any action that changes an external register.

## Profile Shape And Existing Package

### Chosen shape: A, standalone first-deployment profile

One routed Serbian profile can independently govern all four supported commit
surfaces. No supported submission needs a separate base Serbian operational
profile. Organic certificate rules and farm-registration rules are both owned
by the same deliberately narrow profile.

This decision is valid only for this status/evidence slice. It does not decide
how future Serbian fields, operations, inputs, mixed organic/conventional scope,
or operation-level organic claims should compose.

### Relationship to `profile_rs_organic_crop/`

The existing package remains:

- a narrow design/source package;
- descriptorless, disabled, unselected, unrouted, absent from active runtime
  manifests and ActiveArtifactSets, and unclaimed as executable support;
- under release posture
  `RS_ORGANIC_CROP_FARM_REG_CERT_IMPLEMENTATION_CANDIDATE_PRODUCTION_HOLD`; and
- a source-posture-bearing, parse-only planning input for a new versioned
  runtime package; it carries no official local source copies or source hashes.

The later runtime package must carry forward every applicable production
blocker and cite the originating design/source material. It must not treat the
current Markdown files or parse-only source manifest as executable policy,
official source packets, test evidence, or activation evidence.

Because there is no deployed compatibility burden, the runtime package may use
a clearer new identity rather than preserving a misleading candidate identity.
RS3 must choose that identity together with a real descriptor and policy spine;
this brief deliberately does not fabricate those artifacts.

## Actors And Authority

Authentication proves who controls a session. It never proves who may act for
a farm, who may review a status assertion, or who has Serbian public authority.

| Actor | First-deployment role | Required authority source | Boundary |
| --- | --- | --- | --- |
| Farm owner/holder | Submit the farm identity linkage, registration artefact, certificate artefact, and corrections for the farm/operator. | Authenticated Party plus explicit farm-scoped OFARM authority; the holder/operator relationship must reconcile to preserved evidence. | May not self-certify organic status or turn login into legal authority. |
| Employee/operator | **Unsupported state-affecting actor.** | Would require explicit, scoped, time-bounded delegation plus source-backed proof of the delegator's authority. | Generic delegation evidence is not closed. |
| Contractor | **Unsupported state-affecting actor.** | Would require explicit contract/delegation evidence and OFARM authority for the exact action/scope/time. | Authentication, invoice, or farm association alone is insufficient. |
| Agronomist/advisor | May receive read-only sharing only; no submission, acceptance, or contest authority in the first scope. | SharingGrant for read access. A future state-affecting role needs source-backed delegation and an OFARM grant. | Advice stays advisory and cannot promote Compliance Twin state. |
| OFARM status reviewer | Review the four supported commit surfaces and append accept/reject/contest decisions. | Separate, explicit profile/farm-scoped review grant; reviewer identity and decision trace. | Review confirms the OFARM evidence floor only and creates no Serbian official decision. |
| Organic control body | Evidence issuer and subject of the certifier-authority reference; not an interactive actor by default. | Preserved certificate/control-body artefact plus Ministry authorisation and ATS accreditation for the relevant date/scope. | A website, certificate logo, or authenticated account alone is insufficient. |
| Inspector or competent authority | Evidence issuer or read-only recipient when separately shared; no direct write/filing integration in v1. | Preserved official act for evidence; SharingGrant for OFARM read access. | OFARM does not infer public authority from a role label. |
| Read-only reviewer | Inspect qualified views and the frozen evidence packet. | Explicit SharingGrant with farm/output scope and time. | No submit, accept, reject, contest, correction, or export-authority implication. |
| Trusted import/service actor | Ingest a controlled, preserved source packet when RS4 implements that path. | Explicit code-owned provider registration and narrowly scoped import authority. | Technical trust is not Serbian legal authority; partial/failed imports remain atomic and traceable. |

As an OFARM first-deployment implementation policy and claim boundary, the first
deployment requires a reviewer distinct from the submitter for **all four**
supported surfaces: farm registration, certifier authority, organic-certificate
status, and appeal/objection/review-event preservation. This is not asserted to
be Serbian law. For the fourth surface, the affected holder or other authorised
party may submit the challenged act and review artefact, but another OFARM
reviewer must check the preservation evidence; that reviewer does not decide the
appeal's merits or infer finality beyond the official artefact. A party that
submits an OFARM contest cannot review its own contest. This separation prevents
OFARM self-review from being mistaken for independent public or certification
authority while source and authority routes remain under production hold. The
SI bounded self-review rule must not be copied to these status/review surfaces.

### Authority control-plane lifecycle

Default deny is reachable only if the first grants have a visible owner and the
runtime can create, evaluate, replace, and revoke them without role fallback.
The following are activation prerequisites and OFARM implementation policy, not
claims about Serbian public-law delegation:

- **Owner/root of trust.** The deployment activation decision names one
  deployment authority owner and bootstrap principal. Its approval/receipt is
  the source of the initial implementation grants. Public authority is never
  inferred from this technical ownership.
- **Create.** The bootstrap ceremony may append only the minimum farm-scoped
  submit/review/share grants named above. After bootstrap, a new grant may be
  appended only by a principal holding the applicable current grant-management
  authority under the existing authority vocabulary. If that authority cannot
  be represented without inventing an action or contract field, activation
  stops for control-plane design.
- **Scope and time.** Every grant names the grantor, grantee, allowed action,
  tenant, farm, profile/output scope where applicable, start/end, issuance time,
  and approval/source reference. A role label supplies none of these.
- **Currentness.** Submit, review, contest, sharing, and output requests
  re-evaluate the complete grant, delegator, time, scope, and revocation chain at
  the governed action time. There is no cached or login-time allow.
- **Correct and replace.** A changed grant is a new grant with explicit lineage
  or replacement linkage. The prior grant remains in history.
- **Revoke.** Revocation appends a `RevocationDecision`; it never deletes or
  edits the grant. Future requests deny immediately when the relevant
  revocation is effective.
- **Sharing.** A SharingGrant may be issued only by the deployment owner or a
  holder/principal with explicit current sharing authority, and must identify
  recipient, output/farm scope, purpose where required, and time window. It is
  revoked through the same append-only discipline.
- **Refuse.** Missing owner/approval receipt, missing grant, ambiguous scope,
  time mismatch, invalid grantor authority, or effective revocation produces a
  governed refusal/trace. The runtime must not fall back to farmer, reviewer,
  inspector, or administrator role names.

Activation requires a reproducible bootstrap receipt plus tests proving initial
grant creation, default deny before grant, scope/time denial, replacement
history, revocation denial, and SharingGrant access removal.

## Source, Evidence, Currentness, And Refusal Inventory

No official Serbian source copies are currently committed in
`profile_rs_organic_crop/source_packet_extracts/`. Its manifest is a parse-only
inventory of missing packets and research posture. `Official packet` below
therefore means a controlled, digest-receipted source packet that must still be
obtained; it does not describe current repository content.

| Governed surface | Source / authority owner | Identifier or evidence artefact | Historical / transaction-time requirement | Freshness / currentness rule | Parser or adapter need | Official packet | Hard refusal | Production blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025 Organic Production Law basis | Serbian official legal publication / Ministry context, as confirmed by a controlled official source | Official 2025 Organic Production Law artefact plus publication identity, effective/application dates, amendments, digest, and packet receipt | Preserve the exact official version and amendment context used to derive the profile policy; the current research summary is not a substitute | Application/effective dates and later amendments or implementing acts must be versioned from the controlled packet | Controlled legal-source packet and receipt; no runtime parser is implied | **No** | Refuse activation or any legal/currentness rule that depends on the unpacketed research summary being treated as official law | Official packeted 2025 law source and downstream bylaw/form context are not committed |
| Deployment bootstrap and route | Named OFARM deployment owner under the reviewed activation decision | Activation decision, bootstrap-principal identity, tenant/Party/Farm records, holder linkage, tenant/farm route, created-record refs, approval and bootstrap receipt | Preserve the complete ceremony and every later identity/route correction, retirement, or revocation | Route and bootstrap-derived authority must be valid for the activation/request time; zero or ambiguous routes fail closed | Generic governed bootstrap/control-plane command; no Serbian source parser | Not a Serbian source packet | Missing owner or receipt; direct DB seed; missing/ambiguous route; identity/linkage cannot be reconstructed; route not enabled/selected at activation | Activation blocked until the generic ceremony, ownership, correction path, receipt, and route tests exist |
| OFARM submit/review/share authority lifecycle | Named deployment authority owner, then only principals with explicit current grant-management or sharing authority | AuthorityGrant/SharingGrant records, grantor/grantee identities, action/scope/time, approval/source refs, replacement lineage, RevocationDecision and decision trace | Preserve every grant, replacement, revocation, and authorization decision used for the request | Re-evaluate the full chain at each governed action/output time; no role/login/cache fallback | Generic authority control-plane and evaluator; no Serbian source parser | Not a Serbian source packet | Missing/invalid grant owner; absent action/scope/time; invalid grantor; expired/revoked grant; ambiguous scope; self-review where distinct review is required | Activation blocked until initial grant ownership and create/replace/revoke/share lifecycle are implemented and tested |
| Farm/operator identity linkage | Farm holder/operator plus the competent registration authority represented by UAP/eRPG/eAgrar/eSanduče artefacts | BPG or accepted holding identifier; operator/holder identity evidence; farm-scoped OFARM authority | Preserve the artefact used to connect operator, holding, and asserted date/year; no current lookup substitution | Reconcile identity and authority for the assertion's date/scope | Farm-side evidence importer; official artefact parser only after formats are packeted | **No** | Missing identifier, subject mismatch, missing actor authority, or login-only authority | Accepted identifier/formats and durable actor/holder evidence are not fully packeted |
| Farm registration status | Directorate for Agrarian Payments / UAP through eRPG/eAgrar/eSanduče | Official registration, active/passive, submission, or renewal artefact for the relevant date/year; public lookup only as corroboration | Preserve the issued/retrieved artefact, source time, effective/status date, digest, and claim year | Status must cover the asserted transaction date/year; required renewal must be present | Controlled artefact parser/importer; optional corroborative lookup capture, never live truth | **No** | Live lookup only; missing BPG; unreadable status; missing status date; required renewal absent; passive status when active is asserted | Durable transaction-date eRPG/UAP active/passive proof artefact is not closed |
| Certifier authority | Ministry of Agriculture, Forestry and Water Management and ATS | Relevant-year Ministry authorised-control-body list; body identity/code; ATS accreditation record with status, validity, and scope | Preserve both source snapshots used for the same body, date, and scope | Ministry evidence is year-versioned; ATS evidence is date- and scope-specific; suspension/withdrawal/expiry applies at the asserted time | Ministry-list and ATS-record parsers with identity reconciliation | **No** | Either side missing; body mismatch; unclear/wrong ATS scope; expired/suspended/withdrawn status; live-only evidence | Exact 2026 Ministry roster and named 2026 ATS body/scope records are not packeted |
| Organic certificate identity and form | Authorised organic control body, within Ministry/ATS authority context | Certificate artefact; operator/subject; product category or scope; validity period; issuing body identity; electronic artefact where available | Preserve the actual certificate version and digest used for the assertion | Validity must cover the asserted transaction time; subject, scope, and issuer must reconcile | Certificate evidence importer; form-specific parser only after the minister-prescribed form is packeted | **No** | Certificate missing/expired; subject mismatch; scope missing; issuer unresolved; private-site-only proof | Post-2025 minister-prescribed certificate form is not packeted; older forms cannot be presumed current |
| Organic certificate adverse status | Ministry, inspection, or authorised control-body context, as the controlled source establishes | Official suspended, withdrawn, replaced, or otherwise adverse-status artefact/snapshot | Preserve the artefact actually consulted for the asserted/output time | Must cover the relevant date and be re-evaluated for a later qualified output; never infer absence from a missing result | Adverse-status source parser/adapter after source ownership and format are packeted | **No** | Required adverse-status check missing; suspended/withdrawn status; source/time cannot be reconstructed | Official adverse-status source and artefact are not packeted |
| Organic certificate status assertion | Combined certificate, Ministry, ATS, adverse-status, farm/operator, actor-authority, and review evidence | Evidence refs to every contributing artefact plus explicit asserted/effective times and review state | Every contributing source must be replayable as of the assertion time | Any expired, superseded, disputed, missing, or context-drifted basis prevents a clean status | Profile sufficiency, identity-reconciliation, temporal, authority, and review validators | **No complete packet** | Any component above is missing/incoherent; open review is flattened; current status is asserted from stale or live-only material | All component blockers remain active |
| Appeal, objection, or review event | Challenged control body/authority; Ministry/inspection route; Administrative Court where source-backed | Challenged act; service/delivery proof where applicable; appeal/objection/comment/waiver/court artefact; addressed authority; review status | Preserve each event and source artefact in sequence; later events never overwrite earlier ones | State must remain pending, waived, final, challenged, or unknown according to preserved evidence | Review-artefact importer; route-specific parser only after official route/source packets exist | **No** | Missing challenged act; generic “under review” note; finality asserted while route/window/status is unresolved; submitter reviews its own event/contest | Direct farmer-side review route for certificate refusal/withdrawal is not fully pinned |
| Delegation for a non-holder actor | Farm holder/competent source as later source work establishes, plus OFARM authority records | Delegation artefact; delegator and delegate identities; action, farm, scope, start/end, revocation status | Preserve the delegation and all revocation/supersession events used at action time | Re-check on every state-affecting request; authentication time is not authority time | Delegation evidence importer and authority reconciliation | **No** | Missing/ambiguous scope; delegator authority unproved; expired/revoked grant; authentication only | Generic adviser/delegate authority is unresolved; such actors stay unsupported |
| Registration-status PassportView | OFARM derived state over accepted registration assertions and their evidence | Materialization basis, ContextSnapshot, source/effective times, evidence refs, review/dispute state, gaps and qualification | Reconstruct the exact accepted basis for the requested as-of time | Never label “current” without a source-backed policy and fresh basis; otherwise show last-evidenced/unknown/refused | Profile-owned query/view specification and output gate | Not a source packet | Missing/stale/invalid/disputed basis; unresolved authority; unqualified clean output | View cannot ship as a clean status until registration source blockers close |
| Organic-certificate-status PassportView | OFARM derived state over accepted certificate and certifier-authority assertions | Same trace surfaces plus certificate scope/validity and adverse-status basis | Reconstruct all certificate, Ministry, ATS, adverse-status, and review contributors | Clean status requires time-aligned, non-disputed, non-stale evidence; otherwise refuse or disclose | Profile-owned query/view specification and output gate | Not a source packet | Any component source missing/stale; scope/subject mismatch; dispute/open review; certification language | View cannot ship as a clean status until certificate/authority/adverse-status blockers close |
| Frozen evidence packet DocumentAssembly | OFARM governed output over the two status views and review history | Frozen snapshot, basis/context, sufficiency cases, source receipts, gaps, dispute/review state, output qualification | Freeze the exact records and artefacts used at the requested as-of time | Refuse a clean packet when required basis is stale, invalid, disputed, or incomplete; a gap-bearing review packet must say so | Profile-owned assembly specification and deterministic output generator | Not a source packet | Missing trace/basis; official-form/filing/inspection claim; hidden gap; mutable or live-only source | No Serbian official packet/form supports an official filing or inspection-output claim |

The eight existing hold facts remain explicit: the official packeted 2025
Organic Production Law, eRPG/UAP transaction evidence, the Ministry 2026
authorisation roster, ATS body/scope records, the post-2025 certificate form,
adverse certificate status, certificate review routes, and generic delegation.
Renaming or moving the profile must not make any of them disappear.

## Required Outputs And Honest Claims

### 1. Registration-status PassportView

Shows the latest evidence-backed farm-registration assertion for the requested
as-of time, including holder/holding reconciliation, evidence issue/effective
times, source receipts, review state, freshness, gaps, and qualification.

It may claim only that OFARM preserves and derives the displayed status from the
named evidence under the named profile policy. It may not claim official current
registration, successful renewal, filing, entitlement, or compliance when the
required source basis is absent or stale.

### 2. Organic-certificate-status PassportView

Shows certificate subject/scope/validity, issuing-body reconciliation, Ministry
and ATS evidence, adverse-status basis, review/dispute state, times, gaps, and
qualification for the requested as-of time.

It may claim only that the displayed OFARM assertion is supported by the named
preserved evidence. It may not issue a certificate, decide certification,
declare current compliance, or convert missing adverse-status evidence into a
clean result.

### 3. Farm-registration and organic-certificate evidence packet

A frozen DocumentAssembly containing the two status results, their complete
traceable basis, relevant review/correction history, evidence receipts,
unresolved gaps, and output qualification. A farm may use it for controlled
review or share it with a reviewer/inspector under an explicit grant.

It is a farm-controlled evidence packet, not an official filing, statutory
register, government extract, certificate, inspection result, or legal opinion.
Any machine-readable or human-readable rendering is an export of the same
qualified assembly and must not strengthen its claim.

These are required future profile-owned outputs only if the existing generic
PassportView, DocumentAssembly, result-qualification, and trace envelopes can
express their basis, gaps, and refusals without semantic distortion. The later
output slice must stop for a separate contract/schema governance decision if it
cannot express them; it must not invent fields, promote a schema, or weaken the
output claim to make the existing envelope fit.

No other register, PassportView, DocumentAssembly, dashboard, filing, or public
output belongs to the first Serbian runtime.

The following claim rules are binding for all three outputs:

- no current-compliance claim without separately grounded support;
- no certification decision by OFARM;
- no official filing unless separately implemented, evidenced, and reviewed;
- no live public register treated as historical truth; and
- no AI or advisory result promoted into Compliance Twin facts.

## Deployment And Activation Posture

The first deployment is a single-active-RS deployment:

- one selected Serbian package;
- one explicit tenant/farm route to that package;
- SI retained as regression/reference only;
- no concurrent SI route, global profile-choice menu, or request-selected
  profile law; and
- no same-farm profile composition.

Before activation, the Serbian package remains disabled, unselected, unrouted,
and absent from active manifests and ActiveArtifactSets. RS1 and later seam work
may replace implementation-only internals freely, but cannot treat the current
design package as executable support.

RS3-RS7 may build and test a disabled candidate with fictional, format-true
fixtures. RS8 may not activate the **declared full scope** until the official
2025 Organic Production Law packet and the source packets required for farm
registration, certifier authority, certificate form and status, adverse status,
and review/finality are controlled and replayable, and until the bootstrap and
authority-lifecycle activation prerequisites above pass.
If the project instead wants a narrower record-storage-only deployment while
those sources remain missing, that is a new RS0 scope decision, not a silent
downgrade of this brief.

## What RS1 May Abstract

RS1 is restricted to provider registration/selection and the dependency slots
needed to preserve current SI behavior. It may:

- add an explicit, trusted, code-owned descriptor-to-provider registry and
  fail-closed provider selection;
- put the services the current SI pipeline already constructs or consumes
  behind one SI-owned capability-specific bundle: descriptor-scoped policy,
  SI reference bindings/resolvers, the SI/REGSR product-verification service,
  context-assembly dependencies, and profile-sensitive validation support;
- select that bundle at the existing runtime composition boundary and pass only
  the slots required by current SI execution;
- refuse explicit construction or routed execution when the selected descriptor
  has no registered provider, without falling back to SI services;
- prevent descriptor-backed validation from falling back to legacy
  config-created policy; and
- prove descriptor discovery alone neither registers nor activates a provider.

RS1 must not add an RS provider or descriptor, dynamically import executable
code from descriptor paths, generalize tenant/materialization/output routing,
create evidence-ingestion hooks, change authority/review mechanics, generalize
materialization or output gates, write evidence, or touch manifests and
ActiveArtifactSets. Selected-runtime tenant/materialization/output plumbing is
RS2; Serbian governed evidence ingestion is RS4; Serbian authority/review
behavior is RS5; Serbian materialization and outputs are RS6.

RS1 must keep SI-specific behavior behind the SI provider and must not invent RS
services merely to prove the seam. Since nothing is deployed, preserving a
misleading generic `ProductRegister` name or compatibility constructor is not a
goal; preserving truth, trace, refusal, and SI regression behavior is.

The following remain Serbian profile-owned and must not become Core/Kernel or a
universal `Country` abstraction:

- BPG/eRPG/UAP/eAgrar/eSanduče identifiers and artefacts;
- Ministry and ATS authority identities and reconciliation;
- certificate form, subject/scope, validity, and adverse-status rules;
- Serbian review/finality routes;
- every freshness/currentness and evidence-sufficiency floor;
- parser mappings and source packet receipts;
- supported commit-class catalogue and action matrix;
- view/assembly identities, visible fields, refusal/qualification policy;
- profile-local fixtures, executed evidence, and manifest grounding; and
- all unsupported-surface and production-hold declarations.

## Build Gates And Stop Conditions

Continue with RS1 only on the understanding that it is an SI-only,
behavior-preserving provider-seam extraction. Stop rather than deciding silently
if any later slice encounters one of these conditions:

1. A field, crop, equipment, input, operation, transport, mobile, offline, or
   official-filing surface is required for the first deployment.
2. One submission needs both ordinary Serbian rules and organic program rules
   from separate profiles. This selects shape B and requires a separate
   composition track before activation.
3. Mixed organic and conventional scopes must be governed together and cannot
   be represented by one independently sufficient standalone profile.
4. A named runtime surface lacks an explicit evidence basis, currentness rule,
   parser/adapter posture, refusal case, and test plan.
5. A required Serbian legal, source, authority, identifier, form, delegation,
   or review fact remains unresolved for a claim the runtime is expected to
   make. Preserve it as a blocker; do not infer it.
6. An official parcel, input-authorisation, operation-recordkeeping,
   certification, inspection, or filing claim is requested without its own
   controlled Serbian source track.
7. The current descriptor shape would require decorative SI reference,
   code-binding, policy, view, or artifact objects. Open a versioned descriptor
   capability design instead of fabricating them.
8. Core/Kernel law, `reference/**`, an extracted contract, or schema promotion
   appears necessary. Use a separate governance path; RS0 does not authorize it.
9. A design document, source manifest, fixture, or engineering test would need
   to be represented as official source evidence or executed capability proof.
10. A live/public lookup, private certifier page, AI interpretation, or cache
    would become authoritative or historical truth.
11. A clean output would hide missing, stale, disputed, unresolved, or
    unpacketized basis.
12. Activation would require weakening an authority, evidence, currentness,
    review, privacy, traceability, or claim boundary.

## Non-Claims

This brief does not create Serbian runtime support, whole-country coverage,
production readiness, current-compliance support, organic certification,
official registration verification, live integration, official filing,
inspection readiness, profile composition, MP7.7 activation, executable policy,
evidence, manifests, ActiveArtifactSets, contracts, schemas, or law.

The next authorized step after review is RS1: isolate the explicit fail-closed
profile-runtime provider seam with SI registered only.
