# OFARM Authority Action Matrix v0.1

Date: 2026-04-08  
Status: accepted closure companion artifact (colocated with RFC-4)  
Scope: baseline action-to-authority model for RFC-4

| Action class | Authority family | Typical target scopes | Default inheritance mode | Delegable | AI-assisted default | Notes |
|---|---|---|---|---|---|---|
| OBSERVE_CREATE_OBSERVATION | observe/report | farm, site, field, zone, crop cycle, lot, facility | DESCENDANT_SCOPES or EXACT_ONLY | yes | allowed with trace | Basic observation creation |
| OBSERVE_ATTACH_EVIDENCE | observe/report | same as observation + operation, submission context | DESCENDANT_SCOPES or EXACT_ONLY | yes | allowed with trace | Evidence linking remains traceable |
| ASSERT_STRUCTURE | assert/submit | farm, site, field, zone, facility | EXACT_ONLY by default | yes, with caution | requires human approval if AI-assisted | Structural assertions affect governed identity/scope |
| ASSERT_OPERATION_CLAIM | assert/submit | field, zone, crop cycle, operation | DESCENDANT_SCOPES or EXACT_ONLY | yes | allowed with trace | Does not equal accepted execution truth |
| ASSERT_COMPLIANCE | assert/submit | field, crop cycle, lot, submission scope | EXACT_ONLY by default | yes, with caution | requires human approval if AI-assisted | Compliance assertions are high-risk |
| OPERATE_PLAN_INTERVENTION | operate/intervene | field, zone, crop cycle, operation | DESCENDANT_SCOPES | yes | allowed with trace | Planning action |
| OPERATE_REPORT_EXECUTION | operate/intervene | field, zone, crop cycle, operation | DESCENDANT_SCOPES | yes | allowed with trace | Reporting execution still needs later promotion path |
| REVIEW_REQUEST | review | any governed review scope | EXACT_ONLY | yes | allowed with human accountability | Review request is not final governance |
| REVIEW_ACCEPT | govern/decide | assertion, consequence, case scope | NO_INHERIT by default | no by default | human-only by default | High-governance action |
| REVIEW_REJECT_OR_CONTEST | govern/decide | assertion, consequence, case scope | NO_INHERIT by default | no by default | human-only by default | High-governance action |
| REVIEW_SUPERSEDE | govern/decide | assertion, consequence, state scope | NO_INHERIT by default | no by default | human-only by default | Changes what remains in force |
| CONTEXT_INSTALL_PACK | context-governance | farm, site, field, crop cycle | NO_INHERIT by default | no by default | human-only by default | Context installation affects many downstream paths |
| CONTEXT_ACTIVATE_PACK | context-governance | farm, site, field, crop cycle, lot, operation | NO_INHERIT by default | no by default | human-only by default | Activation is governance-sensitive |
| CONTEXT_DEACTIVATE_PACK | context-governance | same as activation scopes | NO_INHERIT by default | no by default | human-only by default | Deactivation can invalidate paths |
| OUTPUT_APPROVE_DOCUMENT_ASSEMBLY | attest/sign | report, dossier, submission scope | NO_INHERIT by default | no by default | human-only by default | Approval before freezing/signing |
| OUTPUT_ATTEST_DOCUMENT_ASSEMBLY | attest/sign | report, dossier, submission scope | NO_INHERIT by default | no by default | human-only by default | Signature/attestation action |
| OUTPUT_FILE_SUBMISSION_ASSEMBLY | attest/sign or assert/submit depending governance | submission scope | NO_INHERIT by default | yes only if explicit | requires human approval by default | Formal filing/delivery action |
| SHARE_GRANT_ACCESS | share/revoke | any governed scope | EXACT_ONLY by default | yes | requires human approval by default | Sharing does not imply write authority |
| SHARE_REVOKE_ACCESS | share/revoke | any governed scope | EXACT_ONLY by default | yes | requires human approval by default | Revocation is prospective |
| RECEIVE_READ_DATA | receive/use | any governed scope | EXACT_ONLY or DESCENDANT_SCOPES depending grant | yes | allowed | Access/use action only |
