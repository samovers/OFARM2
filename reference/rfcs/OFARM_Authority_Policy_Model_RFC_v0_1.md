# OFARM Authority Policy Model RFC v0.1

Date: 2026-04-08  
Status: accepted post-charter RFC  
Scope: formalize executable authority decisions through action classes, scope inheritance, delegation constraints, AI-assisted action rules, and traceable authorization outcomes

---

## 1. Problem statement

RC2 and the authority policy already say:
- authority is explicit
- role is not the same as authority
- delegation and sharing are distinct
- revocation is prospective
- farm-scoped truth and access need governance boundaries

That is constitutionally sound.
It is not yet an executable policy model.

The missing question is:

**How does the platform decide whether a Party may perform a specific action at a specific scope and time?**

This RFC closes that gap.

It formalizes:
- authority action classes
- scope inheritance modes
- authorization decision outcomes
- delegation limits
- AI-assisted and non-human action rules
- authorization decision trace

---

## 2. Core stance

### 2.1 Action-based authorization
Authority must be evaluated against a governed **AuthorityActionClass**, not just a generic “role” or broad family name.

### 2.2 Default deny
If OFARM cannot justify a valid action path through:
- role basis
- authority grant
- scope/time fit
- delegation rules where relevant
- revocation status
- non-human/AI rules where relevant

the default is:
- **DENY**

### 2.3 No silent inheritance
Broad-scope grants do not automatically imply all narrower or derived-scope powers.
Inheritance must be explicit through a governed inheritance mode.

### 2.4 Human governance remains stricter
In v0.1, non-human actors and AI-assisted flows may support many actions, but:
- govern/decide actions
- attestation/signing actions
- context-governance actions

remain human-governed by default unless explicitly relaxed by later governance.

---

## 3. AuthorityActionClass

OFARM fixes at least these baseline **AuthorityActionClass** values:

### Observe/report family
- **OBSERVE_CREATE_OBSERVATION**
- **OBSERVE_ATTACH_EVIDENCE**

### Assert/submit family
- **ASSERT_STRUCTURE**
- **ASSERT_OPERATION_CLAIM**
- **ASSERT_COMPLIANCE**

### Operate/intervene family
- **OPERATE_PLAN_INTERVENTION**
- **OPERATE_REPORT_EXECUTION**

### Review/govern family
- **REVIEW_REQUEST**
- **REVIEW_ACCEPT**
- **REVIEW_REJECT_OR_CONTEST**
- **REVIEW_SUPERSEDE**

### Context-governance family
- **CONTEXT_INSTALL_PACK**
- **CONTEXT_ACTIVATE_PACK**
- **CONTEXT_DEACTIVATE_PACK**

### Output family
- **OUTPUT_APPROVE_DOCUMENT_ASSEMBLY**
- **OUTPUT_ATTEST_DOCUMENT_ASSEMBLY**
- **OUTPUT_FILE_SUBMISSION_ASSEMBLY**

### Sharing/access family
- **SHARE_GRANT_ACCESS**
- **SHARE_REVOKE_ACCESS**
- **RECEIVE_READ_DATA**

These are baseline action classes, not the eternal final set.
But they are enough to make authorization executable instead of vague.

---

## 4. Scope inheritance model

### 4.1 ScopeInheritanceMode
OFARM fixes these baseline **ScopeInheritanceMode** values:

- **EXACT_ONLY**
- **DESCENDANT_SCOPES**
- **DERIVED_LINEAGE_SCOPES**
- **NO_INHERIT**

### 4.2 Meaning of modes

#### EXACT_ONLY
The grant applies only to the explicitly granted scope.

#### DESCENDANT_SCOPES
The grant may apply to directly or indirectly contained child scopes in the same operational containment tree, subject to action-class restrictions.

Typical example:
- a farm-scoped operational grant that also applies to fields and zones of that farm

#### DERIVED_LINEAGE_SCOPES
The grant may apply to scopes that are not simple descendants but are explicitly linked through governed lineage or derivation.

Typical example:
- lot or crop-cycle actions that depend on explicit lineage from the granted scope

#### NO_INHERIT
The grant does not flow beyond the explicitly granted scope.

### 4.3 No upward inheritance
OFARM does not allow automatic upward inheritance.

A field-scoped grant does not automatically authorize farm-wide actions.

### 4.4 Sensitive action default
The following action areas default to **NO_INHERIT** unless explicitly granted otherwise:
- REVIEW_ACCEPT
- REVIEW_REJECT_OR_CONTEST
- REVIEW_SUPERSEDE
- CONTEXT_INSTALL_PACK
- CONTEXT_ACTIVATE_PACK
- CONTEXT_DEACTIVATE_PACK
- OUTPUT_APPROVE_DOCUMENT_ASSEMBLY
- OUTPUT_ATTEST_DOCUMENT_ASSEMBLY
- OUTPUT_FILE_SUBMISSION_ASSEMBLY

---

## 5. Authorization decision model

### 5.1 AuthorizationDecision
An authorization decision must evaluate at least:
- acting Party / software agent
- requested AuthorityActionClass
- target scope
- target time
- purpose where relevant
- applicable RoleAssignments
- applicable AuthorityGrants
- applicable DelegationGrants
- applicable SharingGrants when access is the action
- applicable RevocationDecisions
- applicable ScopeInheritanceMode

### 5.2 AuthorizationDecisionOutcome
OFARM fixes these baseline outcomes:

- **ALLOW**
- **DENY**
- **REQUIRE_REVIEW**
- **REQUIRE_HUMAN_APPROVAL**

### 5.3 Why these outcomes
A binary allow/deny model is too weak for OFARM because some cases are:
- structurally authorized but governance-sensitive
- AI-assisted and therefore requiring human approval
- partially prepared but not yet approvable as final action

---

## 6. Role-to-authority mapping patterns

This RFC does not lock a giant universal role matrix into the Constitution.
But it does recognize baseline patterns.

### 6.1 Farmer
Typically may hold broad farm-side authority for:
- observe/report
- assert/submit
- operate/intervene
- share/revoke
- receive/use

May also hold context-governance and output approval/signing authority when governance or tenancy makes that appropriate.

### 6.2 Operator
Typically oriented toward:
- observe/report
- operate/intervene
- limited assert/submit

Not governance/signing by default.

### 6.3 Advisor
Typically oriented toward:
- observe/report
- receive/use
- draft assistance

Not govern/decide, sign, or context-govern by default without explicit grant.

### 6.4 Inspector / certifier
Typically oriented toward:
- receive/use
- review
- govern/decide within the certified or public scope explicitly granted

Not farm-operate by default.

### 6.5 Buyer
Typically oriented toward:
- receive/use
- possibly restricted submission receipt

Not farm-truth mutation by default.

### 6.6 Service provider
Typically oriented toward:
- operate/intervene
- observe/report
- delegated assert/submit where explicit

Not govern/decide or sign by default.

These are patterns, not substitutes for explicit grants.

---

## 7. Delegation constraints

### 7.1 Delegation must be explicit
A DelegationGrant is required when one Party acts on behalf of another in a way that matters to authority.

### 7.2 Delegation may not exceed source authority
Delegation may not grant more than the delegator validly possesses.

### 7.3 Delegation and inheritance interact
Delegation does not automatically widen scope inheritance.
The delegated action still follows the granted inheritance mode.

### 7.4 Delegation trace
The platform must retain who:
- held original authority
- delegated it
- acted under it
- within which scope/time/purpose

---

## 8. Revocation behavior

### 8.1 Revocation is prospective
Revocation narrows future authority or future access.
It does not erase already valid historical actions.

### 8.2 Revocation check is mandatory
Every authorization decision must consider active RevocationDecisions relevant to:
- the acting Party
- the grant
- the scope/time
- the action class

### 8.3 Long-running flows
If a draft or prepared action crosses a revocation boundary before final promotion, the final authorization decision must re-evaluate against current authority state.

---

## 9. AI-assisted and non-human actions

### 9.1 AI-assisted action
If AI assists a human-authorized actor:
- the human remains the accountable actor for the final action
- AI assistance should be traceable
- the platform may return **REQUIRE_HUMAN_APPROVAL** for action classes where AI may prepare but not finalize

### 9.2 Non-human actor baseline
A software agent may act only if:
- it is a recognized Party/agent form allowed by governance
- it holds an explicit AuthorityGrant or is acting inside a valid delegated envelope
- the requested action class is allowed for non-human actors

### 9.3 Non-human default restrictions
In v0.1, the following action classes default to human-only unless a later governance layer explicitly relaxes them:
- REVIEW_ACCEPT
- REVIEW_REJECT_OR_CONTEST
- REVIEW_SUPERSEDE
- CONTEXT_INSTALL_PACK
- CONTEXT_ACTIVATE_PACK
- CONTEXT_DEACTIVATE_PACK
- OUTPUT_APPROVE_DOCUMENT_ASSEMBLY
- OUTPUT_ATTEST_DOCUMENT_ASSEMBLY
- OUTPUT_FILE_SUBMISSION_ASSEMBLY

### 9.4 Assistance is not silent authority borrowing
The platform must not treat “AI suggested it” as equivalent to “the human authorized it.”

---

## 10. AuthorizationDecisionTrace

The platform must be able to produce an **AuthorizationDecisionTrace** that explains at minimum:

- acting Party / agent
- requested action class
- target scope/time
- role basis used
- grant basis used
- delegation basis used where relevant
- revocation check result
- inheritance mode applied
- decision outcome
- reason for DENY / REQUIRE_REVIEW / REQUIRE_HUMAN_APPROVAL where relevant

This is necessary because permission bugs in OFARM are governance bugs, not only technical bugs.

---

## 11. Authority Action Matrix artifact

This RFC introduces the companion artifact:

- **OFARM Authority Action Matrix v0.1**

Its purpose is to give implementers and reviewers a baseline executable matrix linking:
- action class
- authority family
- typical scopes
- default inheritance mode
- delegability
- AI-assisted default posture
- notes

The matrix is a governed reference artifact, not just background prose.

---

## 12. Minimal conformance expectations

A conforming implementation should be able to decide, for the covered action classes:

- whether the action is allowed, denied, review-required, or human-approval-required
- which inheritance mode is in effect
- whether delegation is valid
- whether revocation blocks the action
- whether a non-human or AI-assisted path is legal
- what trace explains the decision

At minimum, conformance fixtures should include:
- farmer allowed to report execution at field scope via inherited farm grant
- advisor denied pack activation without explicit context-governance grant
- service provider allowed to report execution only inside delegated scope/time
- buyer allowed to read a Lot PassportView but denied write/update
- inspector allowed to review but denied operate
- revoked grant blocks final submission after draft preparation
- AI-assisted compliance submission preparation requires human approval
- software agent denied attestation/signing by default

---

## 13. Main patch consequences

This RFC requires:
- Constitution patching in authority law and conformance direction
- Platform patching in authorization evaluation and traces
- Alignment Register update for authority-policy concepts
- a first Authority Action Matrix artifact

---

## 14. Hard stop question

The RFC succeeds only if the platform can answer:

**Who is trying to do what, at which scope/time, under which grant/delegation/inheritance basis, and why is the answer ALLOW, DENY, REQUIRE_REVIEW, or REQUIRE_HUMAN_APPROVAL?**
