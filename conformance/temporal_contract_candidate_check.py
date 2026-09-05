#!/usr/bin/env python3
"""Validate the inactive temporal-governance candidate package and isolation."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import sys
import types
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol, cast

PACKAGE_ROOT = Path(__file__).parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from conformance import rewrite_architecture_check as architecture  # noqa: E402
COORDINATE_SCHEMA_RELATIVE_PATH = (
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCoordinate_schema_v0_1.json"
)
COORDINATE_SCHEMA_PATH = PACKAGE_ROOT / COORDINATE_SCHEMA_RELATIVE_PATH
CARRIER_SCHEMA_RELATIVE_PATH = (
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCarrierMatrix_schema_v0_1.json"
)
CARRIER_SCHEMA_PATH = PACKAGE_ROOT / CARRIER_SCHEMA_RELATIVE_PATH
CARRIER_MATRIX_RELATIVE_PATH = (
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCarrierMatrix_ADR0002_candidate_v0_1.json"
)
CARRIER_MATRIX_PATH = PACKAGE_ROOT / CARRIER_MATRIX_RELATIVE_PATH
SELECTION_SCHEMA_RELATIVE_PATH = (
    "contracts/candidates/temporal_carrier_selection/"
    "OFARM_TemporalCarrierSelectionBinding_schema_v0_1.json"
)
SELECTION_SCHEMA_PATH = PACKAGE_ROOT / SELECTION_SCHEMA_RELATIVE_PATH
SELECTION_BINDING_RELATIVE_PATH = (
    "contracts/candidates/temporal_carrier_selection/"
    "OFARM_InterventionValidTimeCarrierSelection_candidate_v0_1.json"
)
SELECTION_BINDING_PATH = PACKAGE_ROOT / SELECTION_BINDING_RELATIVE_PATH
COMMAND_SCHEMA_RELATIVE_PATH = (
    "contracts/candidates/temporal_governed_command/"
    "OFARM_TemporalGovernedCommandBinding_schema_v0_1.json"
)
COMMAND_SCHEMA_PATH = PACKAGE_ROOT / COMMAND_SCHEMA_RELATIVE_PATH
COMMAND_BINDING_RELATIVE_PATH = (
    "contracts/candidates/temporal_governed_command/"
    "OFARM_OperationClaimDraftTemporalCommand_candidate_v0_1.json"
)
COMMAND_BINDING_PATH = PACKAGE_ROOT / COMMAND_BINDING_RELATIVE_PATH
RUNTIME_BUNDLE_CARRIER_SCHEMA_RELATIVE_PATH = (
    "contracts/candidates/temporal_runtime_bundle_carrier/"
    "OFARM_TemporalGovernanceRuntimeBundleCarrierBinding_schema_v0_1.json"
)
RUNTIME_BUNDLE_CARRIER_SCHEMA_PATH = (
    PACKAGE_ROOT / RUNTIME_BUNDLE_CARRIER_SCHEMA_RELATIVE_PATH
)
RUNTIME_BUNDLE_CARRIER_BINDING_RELATIVE_PATH = (
    "contracts/candidates/temporal_runtime_bundle_carrier/"
    "OFARM_TemporalGovernanceRuntimeBundleCarrier_candidate_v0_1.json"
)
RUNTIME_BUNDLE_CARRIER_BINDING_PATH = (
    PACKAGE_ROOT / RUNTIME_BUNDLE_CARRIER_BINDING_RELATIVE_PATH
)
RUNTIME_BUNDLE_SELECTION_SCHEMA_RELATIVE_PATH = (
    "contracts/candidates/temporal_runtime_bundle_selection/"
    "OFARM_TenantCommandRuntimeBundleSelectionBinding_schema_v0_1.json"
)
RUNTIME_BUNDLE_SELECTION_SCHEMA_PATH = (
    PACKAGE_ROOT / RUNTIME_BUNDLE_SELECTION_SCHEMA_RELATIVE_PATH
)
RUNTIME_BUNDLE_SELECTION_BINDING_RELATIVE_PATH = (
    "contracts/candidates/temporal_runtime_bundle_selection/"
    "OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json"
)
RUNTIME_BUNDLE_SELECTION_BINDING_PATH = (
    PACKAGE_ROOT / RUNTIME_BUNDLE_SELECTION_BINDING_RELATIVE_PATH
)
PROMOTION_SCHEMA_RELATIVE_PATH = (
    "contracts/candidates/temporal_governance_promotion/"
    "OFARM_TemporalGovernancePromotionBinding_schema_v0_1.json"
)
PROMOTION_SCHEMA_PATH = PACKAGE_ROOT / PROMOTION_SCHEMA_RELATIVE_PATH
PROMOTION_BINDING_RELATIVE_PATH = (
    "contracts/candidates/temporal_governance_promotion/"
    "OFARM_TemporalGovernancePromotion_candidate_v0_1.json"
)
PROMOTION_BINDING_PATH = PACKAGE_ROOT / PROMOTION_BINDING_RELATIVE_PATH
CANDIDATE_RELATIVE_PATHS = frozenset(
    {
        COORDINATE_SCHEMA_RELATIVE_PATH,
        CARRIER_SCHEMA_RELATIVE_PATH,
        CARRIER_MATRIX_RELATIVE_PATH,
        SELECTION_SCHEMA_RELATIVE_PATH,
        SELECTION_BINDING_RELATIVE_PATH,
        COMMAND_SCHEMA_RELATIVE_PATH,
        COMMAND_BINDING_RELATIVE_PATH,
        RUNTIME_BUNDLE_CARRIER_SCHEMA_RELATIVE_PATH,
        RUNTIME_BUNDLE_CARRIER_BINDING_RELATIVE_PATH,
        RUNTIME_BUNDLE_SELECTION_SCHEMA_RELATIVE_PATH,
        RUNTIME_BUNDLE_SELECTION_BINDING_RELATIVE_PATH,
        PROMOTION_SCHEMA_RELATIVE_PATH,
        PROMOTION_BINDING_RELATIVE_PATH,
    }
)
MANIFEST_PATH = PACKAGE_ROOT / "contracts/CONTRACTS_MANIFEST.json"
RFC_PATH = (
    PACKAGE_ROOT
    / "docs/rfcs/OFARM_Temporal_Coordinate_Candidate_RFC_v0_1.md"
)
SELECTION_RFC_PATH = (
    PACKAGE_ROOT
    / "docs/rfcs/"
    "OFARM_Intervention_Valid_Time_Carrier_Selection_RFC_v0_1.md"
)
COMMAND_RFC_PATH = (
    PACKAGE_ROOT
    / "docs/rfcs/OFARM_Operation_Claim_Draft_Temporal_Command_RFC_v0_1.md"
)
RUNTIME_BUNDLE_CARRIER_RFC_PATH = (
    PACKAGE_ROOT
    / "docs/rfcs/"
    "OFARM_Temporal_Governance_RuntimeBundle_Carrier_RFC_v0_1.md"
)
RUNTIME_BUNDLE_SELECTION_RFC_PATH = (
    PACKAGE_ROOT
    / "docs/rfcs/"
    "OFARM_Tenant_Command_RuntimeBundle_Selection_RFC_v0_1.md"
)
PROMOTION_RFC_PATH = (
    PACKAGE_ROOT
    / "docs/rfcs/OFARM_Temporal_Governance_Identity_Promotion_RFC_v0_1.md"
)
KNOWLEDGE_STORAGE_RFC_PATH = (
    PACKAGE_ROOT
    / "docs/rfcs/OFARM_Tenant_Knowledge_Position_Storage_RFC_v0_1.md"
)
MIGRATION_SET_AUTHORITY_PATH = (
    PACKAGE_ROOT / "deployment/postgresql/migration_sets.py"
)
PERSISTENCE_ADMISSION_RFC_PATH = (
    PACKAGE_ROOT
    / "docs/rfcs/"
    "OFARM_Temporal_Governance_Production_"
    "RuntimeBundle_Persistence_Admission_RFC_v0_1.md"
)
ADR_PATH = PACKAGE_ROOT / "docs/adr/0002-valid-time-and-knowledge-time.md"
ERRATA_PATH = PACKAGE_ROOT / "ERRATA.md"
TEMPORAL_CARD_ERRATA_ROW_ID = "E-009"
TEMPORAL_CARD_ERRATA_CARD_DIGEST = (
    "sha256:6f8d61738483ad75c56292297696a372"
    "4950d2e170fab6032a2eea6736e3a759"
)
TEMPORAL_CARD_ERRATA_REQUIRED_MARKERS = (
    "019fa821-93c9-7ef1-8c94-1c0e92ea46b9",
    "019fb246-e554-7c31-a973-facc6bd4376c",
    "2026-07-30T09:06:58.525Z",
    "card canonical byte length `1883`",
    TEMPORAL_CARD_ERRATA_CARD_DIGEST,
    "no later user-authored exact approval sentence",
    "no `governance/temporal-decision-log/` path or entry",
    "withdrawn permanently",
    "does not itself authorize card presentation",
)
ENVELOPE_SCHEMA_PATH = (
    PACKAGE_ROOT / "contracts/kernel/OFARM_SemanticEventEnvelope_schema_v0_1.json"
)
EXECUTION_SCHEMA_PATH = (
    PACKAGE_ROOT / "contracts/core/OFARM_ExecutionRecordPayload_schema_v0_1.json"
)
COMMIT_REQUEST_SCHEMA_PATH = (
    PACKAGE_ROOT / "contracts/kernel/OFARM_CommitIngressRequest_schema_v0_1.json"
)
AUTHORIZATION_REQUEST_SCHEMA_PATH = (
    PACKAGE_ROOT
    / "contracts/kernel/OFARM_AuthorizationDecisionRequest_schema_v0_1.json"
)
AUTHORIZATION_RESULT_SCHEMA_PATH = (
    PACKAGE_ROOT
    / "contracts/kernel/OFARM_AuthorizationDecisionResult_schema_v0_1.json"
)
AUTHORIZATION_TRACE_SCHEMA_PATH = (
    PACKAGE_ROOT
    / "contracts/kernel/OFARM_AuthorizationDecisionTrace_schema_v0_1.json"
)
PROMOTION_TRACE_SCHEMA_PATH = (
    PACKAGE_ROOT / "contracts/kernel/OFARM_PromotionTrace_schema_v0_1.json"
)
COMMIT_RESULT_SCHEMA_PATH = (
    PACKAGE_ROOT / "contracts/kernel/OFARM_CommitIngressResult_schema_v0_1.json"
)
RUNTIME_PROBLEM_SCHEMA_PATH = (
    PACKAGE_ROOT / "contracts/kernel/OFARM_RuntimeProblem_schema_v0_1.json"
)
TEMPORAL_SELECTOR_MODULE_PATH = PACKAGE_ROOT / "kernel/temporal_carriers.py"
RUNTIME_CATALOG_PATH = PACKAGE_ROOT / "kernel/runtime_bundle_components.json"
RUNTIME_BUNDLE_MODEL_PATH = PACKAGE_ROOT / "kernel/runtime_bundle.py"
RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_PATH = (
    PACKAGE_ROOT
    / "docs/rfcs/"
    "OFARM_Temporal_Governance_RuntimeBundle_Model_Admission_RFC_v0_1.md"
)
RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_BYTE_LENGTH = 33787
RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_DIGEST = (
    "9dbe62b18f4214b93b02ae2ccd8d17ee40aed4e1925fff7482993b2eedc9fac8"
)
RUNTIME_BUNDLE_REPOSITORY_PATH = (
    PACKAGE_ROOT / "kernel/runtime_bundle_repository.py"
)
RUNTIME_BUNDLE_SCHEMA_PATH = PACKAGE_ROOT / "kernel/schema.sql"
RUNTIME_BUNDLE_ROLE_FORBIDDEN_AUTHORITY_PATHS = (
    RUNTIME_BUNDLE_REPOSITORY_PATH,
    RUNTIME_BUNDLE_SCHEMA_PATH,
)
ACTIVE_ARTIFACT_SET_PATH = (
    PACKAGE_ROOT
    / "profile_si_ffs/OFARM_ActiveArtifactSet_example_si_ffs_pilot_v0_1.json"
)
CAPABILITY_MANIFEST_PATH = (
    PACKAGE_ROOT
    / "profile_si_ffs/OFARM_Capability_Manifest_si_ffs_pilot_v0_1.json"
)

TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_SELF_RELATIVE_PATH = (
    "docs/rfcs/"
    "OFARM_Temporal_RuntimeBundle_Publication_Conformance_Admission_"
    "RFC_v0_1.md"
)
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_SELF_CONTRACT_IDENTITY = (
    "ofarm.temporal-runtime-bundle-publication-conformance-"
    "admission.issue176.v0.1"
)
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_SELF_BYTE_LENGTH = 42_596
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_SELF_SHA256 = (
    "sha256:17014b754f7401a5ccf809dd8bb4281875592bfc0732abf08ca47dc378fb7cb1"
)
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_PARENT_RELATIVE_PATH = (
    "docs/rfcs/"
    "OFARM_Temporal_RuntimeBundle_Catalog_Publication_Admission_RFC_v0_1.md"
)
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_PARENT_CONTRACT_IDENTITY = (
    "ofarm.temporal-runtime-bundle-catalog-publication-"
    "admission.issue176.v0.1"
)
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_PARENT_BYTE_LENGTH = 47_814
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_PARENT_SHA256 = (
    "sha256:2161e9368f85b373b7cf54b6708edb7b291596defcf9683342e9583657a2298f"
)
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH = (
    "deployment/postgresql/temporal_runtime_bundle_publication.py"
)
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_MODULE = (
    "deployment.postgresql.temporal_runtime_bundle_publication"
)
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT = (
    "TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT"
)
TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_CLASSIFIED = (
    "TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_CLASSIFIED"
)
PUBLICATION_ADAPTER_REQUIRED_MARKERS = (
    "ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1",
    "sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f",
    "sha256:ed48914f77bedacdfce32fb621819da7df7701b54d7862477db0a49ceee5cdc6",
    "sha256:c774100b13ad7d3f353148eeceeabd319167846825c7392ebbaca1f4ba62faea",
    "ofarm.retain_runtime_content",
    "ofarm.publish_runtime_bundle",
)
TEMPORAL_DECISION_LOG_CHECK_RELATIVE_PATH = (
    "conformance/temporal_decision_log_check.py"
)
TEMPORAL_CANDIDATE_CHECK_RELATIVE_PATH = (
    "conformance/temporal_contract_candidate_check.py"
)

GLOBAL_CONTENT_RETENTION_SELF_RELATIVE_PATH = (
    "docs/rfcs/"
    "OFARM_RuntimeBundle_Global_Content_Retention_Conformance_"
    "Admission_RFC_v0_1.md"
)
GLOBAL_CONTENT_RETENTION_SELF_CONTRACT_IDENTITY = (
    "ofarm.runtime-bundle-global-content-retention-conformance-"
    "admission.issue176.v0.1"
)
GLOBAL_CONTENT_RETENTION_SELF_BYTE_LENGTH = 40_726
GLOBAL_CONTENT_RETENTION_SELF_SHA256 = (
    "sha256:7df5ebcb89e2a758c7906e9c4053228e5e151d049ff40e07f83d23a706d7a016"
)
GLOBAL_CONTENT_RETENTION_PARENT_RELATIVE_PATH = (
    "docs/rfcs/"
    "OFARM_RuntimeBundle_Global_Content_Retention_Admission_RFC_v0_1.md"
)
GLOBAL_CONTENT_RETENTION_PARENT_CONTRACT_IDENTITY = (
    "ofarm.runtime-bundle-global-content-retention-admission.issue176.v0.1"
)
GLOBAL_CONTENT_RETENTION_PARENT_BYTE_LENGTH = 38_116
GLOBAL_CONTENT_RETENTION_PARENT_SHA256 = (
    "sha256:aa5de04c08390e1439d59f39c4b6f5608e8b43b320fec531721d9c53b936873a"
)
GLOBAL_CONTENT_RETENTION_MIGRATION_FILENAME = (
    "0009_runtime_bundle_global_content_retention.sql"
)
GLOBAL_CONTENT_RETENTION_V8_PREFIX_DIGEST = (
    "sha256:7231c869066c56f7c642460d33391bab00456daecdb04530b34da7210e8e8a54"
)
GLOBAL_CONTENT_RETENTION_MIGRATION_ABSENT = (
    "GLOBAL_CONTENT_RETENTION_MIGRATION_ABSENT"
)
GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED = (
    "GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED"
)
TRUSTED_COMMAND_SELECTOR_MIGRATION_FILENAME = (
    "0010_tenant_command_runtime_bundle_selector.sql"
)
TRUSTED_COMMAND_SELECTOR_V9_PREFIX_DIGEST = (
    "sha256:cef599a81bda42f84c6c9718845b245ecfa7d97564f5c132b0f12dda526d1293"
)
TRUSTED_COMMAND_SELECTOR_V10_DIGEST = (
    "sha256:bd80785f567e593edea9f88898c18cc8b8269bc8d71eb5aa385c595abc9d7b95"
)
TRUSTED_COMMAND_SELECTOR_MIGRATION_BYTES = 24_684
TRUSTED_COMMAND_SELECTOR_MIGRATION_SHA256 = (
    "sha256:695e38aa0d91ae6a56b8563a6285faf7b2837203e9de378437bc18a6e47da213"
)
TRUSTED_COMMAND_SELECTOR_STRUCTURAL_DIGEST = (
    "sha256:f3d9e802a965e789300240a75dbe8c638743e1d45bcc0ba9ea133877bea0452f"
)
TRUSTED_COMMAND_SELECTOR_CATALOG_DIGEST = (
    "sha256:d9855f9be527f892f54cc5309df17ba00ce16168595bc646ea5a5aa82c53a123"
)
TRUSTED_COMMAND_SELECTOR_RELATIVE_PATH = (
    "kernel/tenant_command_runtime_bundle_selector.py"
)
TRUSTED_COMMAND_SELECTOR_MODULE = (
    "kernel.tenant_command_runtime_bundle_selector"
)
TRUSTED_COMMAND_SELECTOR_MIGRATION_ABSENT = (
    "TRUSTED_COMMAND_SELECTOR_MIGRATION_ABSENT"
)
TRUSTED_COMMAND_SELECTOR_MIGRATION_CLASSIFIED = (
    "TRUSTED_COMMAND_SELECTOR_MIGRATION_CLASSIFIED"
)
TRUSTED_COMMAND_SELECTOR_FIXED_FUNCTION = (
    "ofarm.resolve_commit_operation_claim_draft_runtime_bundle_selection"
)
_GCRC_REQUIRED_MARKERS = (
    "ofarm.runtime-bundle-global-content-retention-admission.issue176.v0.1",
    "ofarm.retain_runtime_content",
)
_GCRC_FORBIDDEN_MIGRATION_MARKERS = (
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCoordinate_schema_v0_1.json",
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCarrierMatrix_schema_v0_1.json",
    "contracts/candidates/temporal_coordinate/"
    "OFARM_TemporalCarrierMatrix_ADR0002_candidate_v0_1.json",
    "contracts/candidates/temporal_carrier_selection/"
    "OFARM_TemporalCarrierSelectionBinding_schema_v0_1.json",
    "contracts/candidates/temporal_carrier_selection/"
    "OFARM_InterventionValidTimeCarrierSelection_candidate_v0_1.json",
    "contracts/candidates/temporal_governed_command/"
    "OFARM_TemporalGovernedCommandBinding_schema_v0_1.json",
    "contracts/candidates/temporal_governed_command/"
    "OFARM_OperationClaimDraftTemporalCommand_candidate_v0_1.json",
    "contracts/candidates/temporal_runtime_bundle_carrier/"
    "OFARM_TemporalGovernanceRuntimeBundleCarrierBinding_schema_v0_1.json",
    "contracts/candidates/temporal_runtime_bundle_carrier/"
    "OFARM_TemporalGovernanceRuntimeBundleCarrier_candidate_v0_1.json",
    "contracts/candidates/temporal_runtime_bundle_selection/"
    "OFARM_TenantCommandRuntimeBundleSelectionBinding_schema_v0_1.json",
    "contracts/candidates/temporal_runtime_bundle_selection/"
    "OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json",
    "contracts/candidates/temporal_governance_promotion/"
    "OFARM_TemporalGovernancePromotionBinding_schema_v0_1.json",
    "contracts/candidates/temporal_governance_promotion/"
    "OFARM_TemporalGovernancePromotion_candidate_v0_1.json",
    "ofarm.temporal-coordinate.v0.1",
    "ofarm.temporal-carrier-matrix.adr0002.v0.1",
    "ofarm.temporal-carrier-selection.intervention.v0.1",
    "ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1",
    "ofarm.temporal-governance-runtime-bundle-carrier.v0.1",
    "TEMPORAL_GOVERNANCE_ARTIFACT",
    (
        "ofarm.tenant-command-runtime-bundle-selection."
        "commit-operation-claim-draft.v0.1"
    ),
    "ofarm.temporal-governance-promotion.issue176-foundation.v0.1",
    "STRUCTURE_EVENT",
    "OBSERVATION_EVENT",
    "OCCURRENCE_EVENT",
    "INTERVENTION_EVENT",
    "MATERIAL_EVENT",
    "EVIDENCE_EVENT",
    "GOVERNANCE_EVENT",
    "ASSERTION_RECORD",
    "ACCEPTED_EVENT_CONSEQUENCE",
    "REVIEW_AND_GOVERNANCE_RECORDS",
    "POINT_OBSERVATION_PAYLOADS",
    "PARTIAL_EXTENT_TEMPORAL_APPLICABILITY",
    "INTERVAL_STATE_OR_OBSERVATION",
    "PENDING_OR_DISPUTED_ANNEX_ENTRY",
    "EVIDENCE_SUFFICIENCY_CASE",
    "OPERATION_CLAIM",
    "sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f",
    "0008_tenant_command_runtime_bundle_selection.sql",
    "deployment/postgresql/tenant_command_runtime_bundle_selection.py",
    "tenant_command_runtime_bundle_selection",
    "activate_tenant_command_runtime_bundle_selection",
    "COMMIT_OPERATION_CLAIM_DRAFT",
    "kernel.api",
    "kernel.application_runtime",
    "kernel.profiles.si_ffs.outputs",
    "contracts/kernel/OFARM_RuntimeProblem_schema_v0_1.json",
    "kernel.legacy_m1.api",
    "#192",
    "ofarm.security-audit-postgresql.v1",
    "security_audit/",
)

SELECTION_STORAGE_AMENDMENT_RELATIVE_PATH = (
    "docs/rfcs/"
    "OFARM_Temporal_Candidate_Conformance_Selection_Storage_"
    "Source_Snapshot_Amendment_RFC_v0_2.md"
)
SELECTION_STORAGE_AMENDMENT_CONTRACT_IDENTITY = (
    "ofarm.temporal-candidate-conformance-selection-storage-"
    "source-snapshot-amendment.issue176.v0.2"
)
SELECTION_STORAGE_AMENDMENT_BYTE_LENGTH = 93_049
SELECTION_STORAGE_AMENDMENT_SHA256 = (
    "sha256:820516d40956b6ea2a158413aea32a305aa078f20816ae35b257eb28491e5867"
)
SELECTION_STORAGE_V0_1_RELATIVE_PATH = (
    "docs/rfcs/"
    "OFARM_Temporal_Candidate_Conformance_Selection_Storage_"
    "Admission_RFC_v0_1.md"
)
SELECTION_STORAGE_V0_1_CONTRACT_IDENTITY = (
    "ofarm.temporal-candidate-conformance-selection-storage-"
    "admission.issue176.v0.1"
)
PYTHON_SNAPSHOT_CONTRACT_IDENTITY = (
    "ofarm.architecture-python-source-snapshot-admission.issue176.v0.1"
)
PYTHON_SNAPSHOT_INTERFACE_IDENTITY = (
    "ofarm.architecture-python-source-snapshot.v1"
)
PYTHON_SNAPSHOT_RFC_RELATIVE_PATH = (
    "docs/rfcs/"
    "OFARM_Architecture_Python_Source_Snapshot_Admission_RFC_v0_1.md"
)
PYTHON_SNAPSHOT_RFC_BYTE_LENGTH = 82_758
PYTHON_SNAPSHOT_RFC_SHA256 = (
    "sha256:6e4307077525f2bbb48992fa4c652ab75d279875063bd715cf21dc1f1d3216d5"
)
SELECTION_STORAGE_REQUIRED_AUTHORITIES = (
    (
        SELECTION_STORAGE_V0_1_RELATIVE_PATH,
        62_540,
        "sha256:716a45927846d068f595f81288b8d29ecc07891bcaf848e0284eb91ece4abc8d",
        SELECTION_STORAGE_V0_1_CONTRACT_IDENTITY,
    ),
    (
        PYTHON_SNAPSHOT_RFC_RELATIVE_PATH,
        PYTHON_SNAPSHOT_RFC_BYTE_LENGTH,
        PYTHON_SNAPSHOT_RFC_SHA256,
        PYTHON_SNAPSHOT_CONTRACT_IDENTITY,
    ),
    (
        "reference/law/OFARM_Platform_Runtime_and_Product_Architecture_RC2_1.md",
        96_406,
        "sha256:76357c6c7c184893f80219720f6343a682a859098f3703eb84c282fba0c02256",
        None,
    ),
    (
        "docs/adr/0001-tenancy-and-schema-migrations.md",
        147_112,
        "sha256:bc49e566ddbdf98868162aa7ccca0940fa76fca1bfaaa261c8c831dbb5515a4d",
        None,
    ),
    (
        "docs/adr/0002-valid-time-and-knowledge-time.md",
        61_427,
        "sha256:c23cb57616207f2f6d39103e429ea778d794ef85d2b198057806c8228d608796",
        None,
    ),
    (
        "docs/adr/0003-tenant-capability-trust-and-binder.md",
        93_419,
        "sha256:b188f4d60e46887fde4231e73bb00adb9bd70b75e807627e8a3906389a0fa5be",
        None,
    ),
    (
        "docs/rfcs/"
        "OFARM_Tenant_Command_RuntimeBundle_Selection_Activation_"
        "Admission_RFC_v0_1.md",
        52_382,
        "sha256:af69370fe268e0632318c95d3e60d83046a49d0948f2ba9cb05d2744ae82d6eb",
        (
            "ofarm.tenant-command-runtime-bundle-selection-activation-"
            "admission.issue176.v0.1"
        ),
    ),
    (
        "contracts/candidates/temporal_runtime_bundle_selection/"
        "OFARM_TenantCommandRuntimeBundleSelectionBinding_schema_v0_1.json",
        17_252,
        "sha256:56604a52465ffc027382e99dea96f2c9bc1bd2479cbaff30dec6bd39c08e6b3d",
        None,
    ),
    (
        "contracts/candidates/temporal_runtime_bundle_selection/"
        "OFARM_TenantCommandRuntimeBundleSelection_candidate_v0_1.json",
        15_993,
        "sha256:1500ffbbfdf11207a6657848fce12618347f767578e55dc070bb282dc5775aac",
        None,
    ),
    (
        "docs/rfcs/"
        "OFARM_Temporal_Governance_Production_RuntimeBundle_"
        "Persistence_Admission_RFC_v0_1.md",
        37_254,
        "sha256:40a20c5053857664cfbb2d6ac2814c6136125eb9908635495af9377e9d9f0870",
        None,
    ),
    (
        "docs/rfcs/OFARM_Tenant_Binding_Selection_Control_Admission_RFC_v0_1.md",
        32_169,
        "sha256:c1d02969811be0d5b02bdae158cb48e5d8148356ca9d4bac956c8861d529c37a",
        None,
    ),
    (
        "docs/rfcs/"
        "OFARM_Tenant_Current_Context_Selection_Owner_Admission_RFC_v0_1.md",
        50_383,
        "sha256:af85e259230b69edeba80ddc2eea2f070a601fd3888fd463ce595f9cc446b13d",
        None,
    ),
    (
        "docs/rfcs/"
        "OFARM_Tenant_Write_Lock_Selection_Owner_Admission_RFC_v0_1.md",
        45_758,
        "sha256:5745ad4b8b588be2b5a1b64b4b84aa757b23f8d2de00ca59e71de8ea304f51b0",
        None,
    ),
)
SELECTION_STORAGE_ALLOWED_PRODUCTION_PATHS = frozenset(
    {
        "kernel/migrations/0008_tenant_command_runtime_bundle_selection.sql",
        "kernel/migrations/0010_tenant_command_runtime_bundle_selector.sql",
        TRUSTED_COMMAND_SELECTOR_RELATIVE_PATH,
        "deployment/postgresql/tenant_command_runtime_bundle_selection.py",
    }
)
SELECTION_STORAGE_MIGRATION_FILENAME = (
    "0008_tenant_command_runtime_bundle_selection.sql"
)
SELECTION_STORAGE_ADAPTER_RELATIVE_PATH = (
    "deployment/postgresql/tenant_command_runtime_bundle_selection.py"
)
SELECTION_STORAGE_ADAPTER_MODULE = (
    "deployment.postgresql.tenant_command_runtime_bundle_selection"
)
POSTGRESQL_INITIALIZER_RELATIVE_PATH = "deployment/postgresql/__init__.py"
POSTGRESQL_INITIALIZER_MODULE = "deployment.postgresql"
SELECTION_STORAGE_MARKERS = (
    (
        "ofarm.tenant-command-runtime-bundle-selection."
        "commit-operation-claim-draft.v0.1"
    ),
    "sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f",
)
TRUSTED_COMMAND_SELECTOR_PIN_LITERALS = {
    "_SELECTION_SCHEMA_BYTES": 17_252,
    "_SELECTION_SCHEMA_DIGEST": (
        "sha256:56604a52465ffc027382e99dea96f2c9bc1bd2479cbaff30dec6bd39c08e6b3d"
    ),
    "_SELECTION_BINDING_FILE_BYTES": 15_993,
    "_SELECTION_BINDING_FILE_DIGEST": (
        "sha256:1500ffbbfdf11207a6657848fce12618347f767578e55dc070bb282dc5775aac"
    ),
    "_SELECTION_BINDING_CANONICAL_BYTES": 13_287,
    "_SELECTION_BINDING_CANONICAL_DIGEST": SELECTION_STORAGE_MARKERS[1],
    "_SELECTION_BINDING_ID": SELECTION_STORAGE_MARKERS[0],
    "_COMMAND_ID": "COMMIT_OPERATION_CLAIM_DRAFT",
    "_COMMAND_BINDING_ID": (
        "ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1"
    ),
    "_COMMAND_BINDING_DIGEST": (
        "sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1"
    ),
}
SELECTION_STORAGE_CONFORMANT_ABSENT = "CONFORMANT_ABSENT"
SELECTION_STORAGE_CONFORMANT_CLASSIFIED = "CONFORMANT_CLASSIFIED"
SELECTION_STORAGE_V3_PREFIX_DIGEST = (
    "sha256:ba7a193e96ca78d01edf529ed2e20bbd1810c0a3a0c13bc717969e8c5c739bf0"
)
SELECTION_STORAGE_V7_DIGEST = (
    "sha256:5616797d1362c55c78175126edab29cc3e88c021ba0709e3766d3196d2b0126b"
)
SELECTION_STORAGE_V7_MIGRATION_PINS = {
    3: (
        "0003_tenant_knowledge_position.sql",
        6_565,
        "sha256:d59af77e23fe012203696023ec343038dbcab5d5ffb9689be11ba67dca22f827",
    ),
    4: (
        "0004_temporal_governance_runtime_bundle_role.sql",
        6_464,
        "sha256:0c51948be7cebf2c1523d472ca44a57e32942bd358124e126ccaf2bad248ecc8",
    ),
    5: (
        "0005_tenant_binding_selection_control_admission.sql",
        8_545,
        "sha256:fde66e835f8c4456d7404eb00b99292e267f573f8b126f781f3ed55bd5e8df9a",
    ),
    6: (
        "0006_tenant_current_context_selection_owner_admission.sql",
        8_655,
        "sha256:a61c668a2bae04026b8413385f8bc1b5fd43f08f8d5281501ff766a57d552b48",
    ),
    7: (
        "0007_tenant_write_lock_selection_owner_admission.sql",
        7_936,
        "sha256:cf8594b6c456953004912722b168d6bdda7c6dbfc903ba8099b018e2f270dff7",
    ),
}
SELECTION_STORAGE_V7_STRUCTURAL_DIGEST = (
    "sha256:fcc0e96b4520ffe51ddb5537df24040e4d5948a22b3c387351346cc588e87ee5"
)
SELECTION_STORAGE_V7_CATALOG_DIGEST = (
    "sha256:026bb61026a9f752fc8dde84bca0e3cbbab374d0ac8f0ba942a72654e44f5f1a"
)
SELECTION_STORAGE_PROVISIONING_DIGEST = (
    "sha256:2ac8487b64d4fb09d7576ef1ee09ac1f2a3cc5b20558f0d2137620b897c7157c"
)
SELECTION_STORAGE_SOURCE_PINS = (
    (
        "deployment/postgresql/provisioning_specs.py",
        "deployment.postgresql.provisioning_specs",
        112_914,
        "sha256:abeec08b9d2ba49eb0819a0376b23a7b6b433c07abd0e50a55c1cf1b309a93d7",
    ),
    (
        "deployment/postgresql/native_release_identity.py",
        "deployment.postgresql.native_release_identity",
        79_101,
        "sha256:507a30c20960d6981f15de7f48def51a727093e0beaecdd647e3474baf706193",
    ),
    (
        "deployment/postgresql/tenant_contract.py",
        "deployment.postgresql.tenant_contract",
        42_795,
        "sha256:557a6f5215ec58df8b209190fc1c9b091102f2b658ddf497c8bfa006765be47e",
    ),
)
SELECTION_STORAGE_ABSENT_CATALOG_PIN = (
    "deployment/postgresql/catalog_identity.py",
    "deployment.postgresql.catalog_identity",
    12_016,
    "sha256:20b985b703320b55887fd434213773144891e8dff4edf82ccbef6e5f3423dbfa",
)
SELECTION_STORAGE_ACTIVE_NON_PYTHON_PATHS = (
    RUNTIME_CATALOG_PATH,
    ACTIVE_ARTIFACT_SET_PATH,
    CAPABILITY_MANIFEST_PATH,
)

CONTRACT_VERSION = "ofarm.temporal-coordinate.v0.1"
CONTRACT_ID = "https://ofarm.dev/schema/temporal-coordinate/v0.1"
MAX_KNOWLEDGE_POSITION = 9007199254740991
NIL_TENANT_ID = "00000000-0000-0000-0000-000000000000"
CARRIER_SCHEMA_VERSION = "ofarm.temporal-carrier-matrix.v0.1"
CARRIER_SCHEMA_ID = "https://ofarm.dev/schema/temporal-carrier-matrix/v0.1"
CARRIER_MATRIX_ID = "ofarm.temporal-carrier-matrix.adr0002.v0.1"
CARRIER_MATRIX_STATUS = "CANDIDATE_INACTIVE"
CARRIER_EXECUTION_POSTURE = "CLASSIFICATION_ONLY_RUNTIME_UNSUPPORTED"
CARRIER_SOURCE_AUTHORITY = (
    "docs/adr/0002-valid-time-and-knowledge-time.md"
    "#governed-carrier-and-window-meaning-matrix"
)
SELECTION_SCHEMA_VERSION = (
    "ofarm.temporal-carrier-selection-binding.v0.1"
)
SELECTION_SCHEMA_ID = (
    "https://ofarm.dev/schema/temporal-carrier-selection-binding/v0.1"
)
SELECTION_BINDING_ID = (
    "ofarm.temporal-carrier-selection.intervention.v0.1"
)
SELECTION_STATUS = "CANDIDATE_INACTIVE"
SELECTION_EXECUTION_POSTURE = "PURE_LIBRARY_PRODUCTION_UNBOUND"
SELECTION_IDENTITY_AUTHORITY = (
    "REVIEWED_BINDING_ARTIFACT_NOT_CALLER_DATA"
)
SELECTION_ROW_ID = "INTERVENTION_EVENT"
ENVELOPE_SCHEMA_VERSION = "ofarm.semanticeventenvelope.v0.1"
EXECUTION_SCHEMA_VERSION = "ofarm.executionrecordpayload.v0.1"
COMMAND_SCHEMA_VERSION = "ofarm.temporal-governed-command-binding.v0.1"
COMMAND_SCHEMA_ID = (
    "https://ofarm.dev/schema/temporal-governed-command-binding/v0.1"
)
COMMAND_BINDING_ID = (
    "ofarm.temporal-governed-command.commit-operation-claim-draft.v0.1"
)
COMMAND_STATUS = "CANDIDATE_INACTIVE"
COMMAND_EXECUTION_POSTURE = "CONTRACT_ONLY_PRODUCTION_SURFACE_CLOSED"
COMMAND_IDENTITY_AUTHORITY = "REVIEWED_BINDING_ARTIFACT_NOT_CALLER_DATA"
COMMAND_SCHEMA_DIGEST = (
    "afda003df90e2787cfdc97f5561e3e5b098177a5add91556af2e935a3b9711db"
)
COMMAND_BINDING_DIGEST = (
    "0909ec653cb99a94cd1b35afaf2d386258aac671c5f730960ed485df8a4b8f2e"
)
RUNTIME_BUNDLE_CARRIER_SCHEMA_VERSION = (
    "ofarm.temporal-governance-runtime-bundle-carrier-binding.v0.1"
)
RUNTIME_BUNDLE_CARRIER_SCHEMA_ID = (
    "https://ofarm.dev/schema/"
    "temporal-governance-runtime-bundle-carrier-binding/v0.1"
)
RUNTIME_BUNDLE_CARRIER_BINDING_ID = (
    "ofarm.temporal-governance-runtime-bundle-carrier.v0.1"
)
RUNTIME_BUNDLE_CARRIER_STATUS = "CANDIDATE_INACTIVE"
RUNTIME_BUNDLE_CARRIER_EXECUTION_POSTURE = (
    "VOCABULARY_ONLY_RUNTIME_UNSUPPORTED"
)
RUNTIME_BUNDLE_CARRIER_IDENTITY_AUTHORITY = (
    "REVIEWED_BINDING_ARTIFACT_NOT_CALLER_DATA"
)
RUNTIME_BUNDLE_CARRIER_ROLE = "TEMPORAL_GOVERNANCE_ARTIFACT"
RUNTIME_BUNDLE_PERSISTENCE_MIGRATION_FILENAME = (
    "0004_temporal_governance_runtime_bundle_role.sql"
)
PERSISTENCE_ADMISSION_RFC_BYTE_LENGTH = 37254
PERSISTENCE_ADMISSION_RFC_DIGEST = (
    "40a20c5053857664cfbb2d6ac2814c6136125eb9908635495af9377e9d9f0870"
)
MIGRATION_AUTHORITY_PRIVATE_MODULE_NAME = (
    "_ofarm_temporal_migration_set_authority"
)
RUNTIME_BUNDLE_CARRIER_SCHEMA_DIGEST = (
    "6a04b0c3a68428ca0b505e70ba056a4295bde31a3c510fb75191222d8dc228bf"
)
RUNTIME_BUNDLE_CARRIER_BINDING_DIGEST = (
    "391c8110029f004375e668e5e902864c0b4aaf6f650005abed8a206d4049e5b4"
)
RUNTIME_BUNDLE_SELECTION_SCHEMA_VERSION = (
    "ofarm.tenant-command-runtime-bundle-selection-binding.v0.1"
)
RUNTIME_BUNDLE_SELECTION_SCHEMA_ID = (
    "https://ofarm.dev/schema/"
    "tenant-command-runtime-bundle-selection-binding/v0.1"
)
RUNTIME_BUNDLE_SELECTION_BINDING_ID = (
    "ofarm.tenant-command-runtime-bundle-selection."
    "commit-operation-claim-draft.v0.1"
)
RUNTIME_BUNDLE_SELECTION_STATUS = "CANDIDATE_INACTIVE"
RUNTIME_BUNDLE_SELECTION_EXECUTION_POSTURE = (
    "CONTRACT_ONLY_PRODUCTION_UNBOUND"
)
RUNTIME_BUNDLE_SELECTION_IDENTITY_AUTHORITY = (
    "REVIEWED_BINDING_ARTIFACT_NOT_CALLER_DATA"
)
RUNTIME_BUNDLE_SELECTION_SCHEMA_DIGEST = (
    "56604a52465ffc027382e99dea96f2c9bc1bd2479cbaff30dec6bd39c08e6b3d"
)
RUNTIME_BUNDLE_SELECTION_BINDING_DIGEST = (
    "1500ffbbfdf11207a6657848fce12618347f767578e55dc070bb282dc5775aac"
)
PROMOTION_SCHEMA_VERSION = "ofarm.temporal-governance-promotion-binding.v0.1"
PROMOTION_SCHEMA_ID = (
    "https://ofarm.dev/schema/temporal-governance-promotion-binding/v0.1"
)
PROMOTION_BINDING_ID = (
    "ofarm.temporal-governance-promotion.issue176-foundation.v0.1"
)
PROMOTION_STATUS = "CANDIDATE_INACTIVE"
PROMOTION_EXECUTION_POSTURE = "CONTRACT_ONLY_NO_PROMOTION_EFFECT"
PROMOTION_IDENTITY_AUTHORITY = (
    "REVIEWED_BINDING_ARTIFACT_AND_HUMAN_CURRENTNESS_DECISION_NOT_CALLER_DATA"
)
PROMOTION_SCHEMA_DIGEST = (
    "6f4545c4101d1b984e3eee55e89ff833184d5474ce1fa8e81b02a85753b8c5c2"
)
PROMOTION_BINDING_DIGEST = (
    "10cf2208a4480c5d86c257fce99725c0284781458cee1796ee6ab3974cc06bf0"
)
PROMOTION_RFC_DIGEST = (
    "be4a8873821045c752cc2df8e61df0898e3dc88db204ee9121acb05d17a13764"
)
PROMOTION_INVARIANTS = (
    "TGP-001_EXACT_SUBJECTS",
    "TGP-002_EXACT_CONTENT",
    "TGP-003_ATOMIC_DECISION",
    "TGP-004_IMMUTABLE_SUBJECTS",
    "TGP-005_EXTERNAL_LIFECYCLE_AUTHORITY",
    "TGP-006_GOVERNED_BUT_INACTIVE",
    "TGP-007_EXECUTION_POSTURE_PRESERVED",
    "TGP-008_NO_INFERENCE",
    "TGP-009_NO_CALLER_AUTHORITY",
    "TGP-010_NO_SUBSTITUTION",
    "TGP-011_POST_PROMOTION_IMMUTABILITY",
    "TGP-012_FAIL_CLOSED",
    "TGP-013_NO_CURRENT_DEFAULT_CLAIM",
    "TGP-014_PRODUCTION_LEGACY_FIREWALL",
)
PROMOTION_NEGATIVE_CASES = (
    "MISSING_ADDITIONAL_DUPLICATED_REORDERED_OR_SUBSTITUTED_SUBJECT",
    "PARTIAL_PROMOTION_SET",
    "SUBJECT_IDENTITY_SCHEMA_DIGEST_CANONICALIZATION_OR_LENGTH_MISMATCH",
    "SUBJECT_SCHEMA_VALIDATION_FAILURE",
    "SELECTOR_MATRIX_IDENTITY_DIGEST_OR_ROW_MISMATCH",
    "COMMAND_SELECTOR_PREREQUISITE_MISMATCH",
    "NON_HUMAN_MISSING_OR_AMBIGUOUS_PROMOTION_AUTHORITY",
    "MISSING_OR_CONFLICTING_CURRENTNESS_TRACE",
    "OUTCOME_OUTSIDE_CLOSED_SET",
    "POSITIVE_DECISION_STRONGER_THAN_GOVERNED_INACTIVE",
    "PROMOTION_INFERRED_FROM_REVIEW_MERGE_MANIFEST_CONFORMANCE_OR_RUNTIME",
    "SCHEMA_CARRIER_SELECTION_OR_OTHER_IDENTITY_PROMOTION",
    "SUBJECT_REWRITE_OR_RELOCATION",
    "PRODUCTION_OR_LEGACY_RUNTIME_IMPORT",
)
KNOWLEDGE_STORAGE_ID = "ofarm.tenant-knowledge-position-storage.v0.1"
KNOWLEDGE_STORAGE_RFC_DIGEST = (
    "6ddf1b6b289c9e638646cf7ddd356165f3ec8cbcc96b3c988e3f6585d11f26f8"
)
KNOWLEDGE_STORAGE_MIGRATION_DIGEST = (
    "d59af77e23fe012203696023ec343038dbcab5d5ffb9689be11ba67dca22f827"
)
KNOWLEDGE_STORAGE_MIGRATION_FILENAME = (
    "0003_tenant_knowledge_position.sql"
)
KNOWLEDGE_STORAGE_MIGRATION_BYTE_LENGTH = 6565
KNOWLEDGE_STORAGE_MIGRATION_PREFIX_DIGEST = (
    "sha256:ba7a193e96ca78d01edf529ed2e20bb"
    "d1810c0a3a0c13bc717969e8c5c739bf0"
)
CARRIER_ROW_IDS = (
    "STRUCTURE_EVENT",
    "OBSERVATION_EVENT",
    "OCCURRENCE_EVENT",
    "INTERVENTION_EVENT",
    "MATERIAL_EVENT",
    "EVIDENCE_EVENT",
    "GOVERNANCE_EVENT",
    "ASSERTION_RECORD",
    "ACCEPTED_EVENT_CONSEQUENCE",
    "REVIEW_AND_GOVERNANCE_RECORDS",
    "POINT_OBSERVATION_PAYLOADS",
    "PARTIAL_EXTENT_TEMPORAL_APPLICABILITY",
    "INTERVAL_STATE_OR_OBSERVATION",
    "PENDING_OR_DISPUTED_ANNEX_ENTRY",
    "EVIDENCE_SUFFICIENCY_CASE",
)
WINDOW_MEANINGS = frozenset({"EVENT_OCCURRENCE", "STATE_OVERLAP"})
_UTC_INSTANT = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"(\.[0-9]{1,6})?Z$"
)
_CANONICAL_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}$"
)


class TemporalCandidateError(ValueError):
    """The candidate document differs from its approved temporal semantics."""


class _AuthenticatedMigration(Protocol):
    version: int
    filename: str
    source_bytes: bytes
    source_sha256: str
    byte_length: int


class _AuthenticatedMigrationSet(Protocol):
    service: object
    migrations: tuple[_AuthenticatedMigration, ...]
    digest: str

    def prefix_digest(self, version: int) -> str: ...


@dataclass(frozen=True)
class TenantMigrationAuthoritySnapshot:
    """One production-authenticated migration release and its stable V3 cut."""

    migration_set: _AuthenticatedMigrationSet
    version_3_prefix: str


@dataclass(frozen=True)
class RefusalVector:
    """One named refusal shared by the package gate and pytest."""

    vector_id: str
    validator: Callable[[object], None]
    value: object
    expected_error: str
    schema_must_refuse: bool = False


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TemporalCandidateError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TemporalCandidateError(f"{path} is not strict JSON") from exc
    if type(value) is not dict:
        raise TemporalCandidateError(f"{path} must contain one JSON object")
    return value


def _closed_object(
    value: object,
    *,
    label: str,
    allowed: frozenset[str],
    required: frozenset[str],
) -> dict[str, object]:
    if type(value) is not dict:
        raise TemporalCandidateError(f"{label} must be an object")
    fields = frozenset(value)
    missing = required - fields
    if missing:
        raise TemporalCandidateError(
            f"{label} is missing fields: {', '.join(sorted(missing))}"
        )
    unknown = fields - allowed
    if unknown:
        raise TemporalCandidateError(
            f"{label} has unknown fields: {', '.join(sorted(unknown))}"
        )
    return value


def canonical_utc_instant(value: object, label: str) -> datetime:
    if type(value) is not str or _UTC_INSTANT.fullmatch(value) is None:
        raise TemporalCandidateError(f"{label} is not canonical UTC")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TemporalCandidateError(f"{label} is not a real UTC instant") from exc
    return instant


def validate_valid_interval(value: object) -> None:
    interval = _closed_object(
        value,
        label="ValidInterval",
        allowed=frozenset({"validFrom", "validUntil"}),
        required=frozenset({"validFrom"}),
    )
    start = canonical_utc_instant(interval["validFrom"], "validFrom")
    if "validUntil" in interval:
        end = canonical_utc_instant(interval["validUntil"], "validUntil")
        if end <= start:
            raise TemporalCandidateError(
                "ValidInterval must be non-empty and half-open"
            )


def validate_valid_cut(value: object) -> None:
    if type(value) is not dict:
        raise TemporalCandidateError("ValidCut must be an object")
    cut_type = value.get("cutType")
    if cut_type == "POINT":
        point = _closed_object(
            value,
            label="POINT ValidCut",
            allowed=frozenset({"cutType", "validAt"}),
            required=frozenset({"cutType", "validAt"}),
        )
        canonical_utc_instant(point["validAt"], "validAt")
        return
    if cut_type == "WINDOW":
        window = _closed_object(
            value,
            label="WINDOW ValidCut",
            allowed=frozenset({"cutType", "windowStart", "windowEnd"}),
            required=frozenset({"cutType", "windowStart", "windowEnd"}),
        )
        start = canonical_utc_instant(window["windowStart"], "windowStart")
        end = canonical_utc_instant(window["windowEnd"], "windowEnd")
        if end <= start:
            raise TemporalCandidateError(
                "WINDOW ValidCut must be non-empty and half-open"
            )
        return
    raise TemporalCandidateError("ValidCut cutType must be POINT or WINDOW")


def validate_knowledge_cut(value: object) -> None:
    cut = _closed_object(
        value,
        label="KnowledgeCut",
        allowed=frozenset({"tenantId", "position"}),
        required=frozenset({"tenantId", "position"}),
    )
    tenant_id = cut["tenantId"]
    if type(tenant_id) is not str or _CANONICAL_UUID.fullmatch(tenant_id) is None:
        raise TemporalCandidateError("KnowledgeCut tenantId is not canonical")
    if tenant_id == NIL_TENANT_ID:
        raise TemporalCandidateError("KnowledgeCut tenantId is not canonical")
    position = cut["position"]
    if (
        type(position) is not int
        or position < 0
        or position > MAX_KNOWLEDGE_POSITION
    ):
        raise TemporalCandidateError(
            "KnowledgeCut position is outside the portable safe-integer range"
        )


def validate_window_meaning(value: object) -> None:
    if type(value) is not str or value not in WINDOW_MEANINGS:
        raise TemporalCandidateError("WindowMeaning is outside the closed vocabulary")


def validate_temporal_coordinate(value: object) -> None:
    coordinate = _closed_object(
        value,
        label="TemporalCoordinate",
        allowed=frozenset({"schemaVersion", "validCut", "knowledgeCut"}),
        required=frozenset({"schemaVersion", "validCut", "knowledgeCut"}),
    )
    if coordinate["schemaVersion"] != CONTRACT_VERSION:
        raise TemporalCandidateError("TemporalCoordinate version differs")
    validate_valid_cut(coordinate["validCut"])
    validate_knowledge_cut(coordinate["knowledgeCut"])


def _schema_semantics(value: object) -> object:
    if type(value) is dict:
        return {
            key: _schema_semantics(item)
            for key, item in value.items()
            if key != "$comment"
        }
    if type(value) is list:
        return [_schema_semantics(item) for item in value]
    return value


def _expect_closed_schema_definition(
    definitions: dict[str, object],
    name: str,
    *,
    required: list[str],
    properties: dict[str, object],
) -> None:
    expected = {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }
    if _schema_semantics(definitions.get(name)) != expected:
        raise TemporalCandidateError(f"candidate {name} definition differs")


def validate_coordinate_schema_shape(schema: dict[str, object]) -> None:
    expected_root_keys = {
        "$schema",
        "$id",
        "title",
        "$comment",
        "type",
        "additionalProperties",
        "required",
        "properties",
        "$defs",
    }
    if set(schema) != expected_root_keys:
        raise TemporalCandidateError("candidate coordinate schema fields differ")
    if (
        schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("$id") != CONTRACT_ID
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or schema.get("required")
        != ["schemaVersion", "validCut", "knowledgeCut"]
        or _schema_semantics(schema.get("properties"))
        != {
            "schemaVersion": {"const": CONTRACT_VERSION},
            "validCut": {"$ref": "#/$defs/validCut"},
            "knowledgeCut": {"$ref": "#/$defs/knowledgeCut"},
        }
    ):
        raise TemporalCandidateError("candidate coordinate root shape differs")
    comment = schema.get("$comment")
    if type(comment) is not str or "NEW_CANDIDATE" not in comment:
        raise TemporalCandidateError("candidate currentness is not explicit")

    definitions = schema.get("$defs")
    expected_definition_names = {
        "canonicalUtcInstant",
        "validInterval",
        "pointValidCut",
        "windowValidCut",
        "validCut",
        "knowledgeCut",
        "windowMeaning",
    }
    if (
        type(definitions) is not dict
        or set(definitions) != expected_definition_names
    ):
        raise TemporalCandidateError("candidate temporal definitions differ")
    if _schema_semantics(definitions["canonicalUtcInstant"]) != {
        "type": "string",
        "format": "date-time",
        "pattern": _UTC_INSTANT.pattern,
    }:
        raise TemporalCandidateError("candidate UTC instant definition differs")
    _expect_closed_schema_definition(
        definitions,
        "validInterval",
        required=["validFrom"],
        properties={
            "validFrom": {"$ref": "#/$defs/canonicalUtcInstant"},
            "validUntil": {"$ref": "#/$defs/canonicalUtcInstant"},
        },
    )
    _expect_closed_schema_definition(
        definitions,
        "pointValidCut",
        required=["cutType", "validAt"],
        properties={
            "cutType": {"const": "POINT"},
            "validAt": {"$ref": "#/$defs/canonicalUtcInstant"},
        },
    )
    _expect_closed_schema_definition(
        definitions,
        "windowValidCut",
        required=["cutType", "windowStart", "windowEnd"],
        properties={
            "cutType": {"const": "WINDOW"},
            "windowStart": {"$ref": "#/$defs/canonicalUtcInstant"},
            "windowEnd": {"$ref": "#/$defs/canonicalUtcInstant"},
        },
    )
    if _schema_semantics(definitions["validCut"]) != {
        "oneOf": [
            {"$ref": "#/$defs/pointValidCut"},
            {"$ref": "#/$defs/windowValidCut"},
        ]
    }:
        raise TemporalCandidateError("candidate ValidCut definition differs")
    _expect_closed_schema_definition(
        definitions,
        "knowledgeCut",
        required=["tenantId", "position"],
        properties={
            "tenantId": {
                "type": "string",
                "pattern": _CANONICAL_UUID.pattern,
                "not": {"const": NIL_TENANT_ID},
            },
            "position": {
                "type": "integer",
                "minimum": 0,
                "maximum": MAX_KNOWLEDGE_POSITION,
            },
        },
    )
    if _schema_semantics(definitions["windowMeaning"]) != {
        "enum": ["EVENT_OCCURRENCE", "STATE_OVERLAP"]
    }:
        raise TemporalCandidateError("candidate WindowMeaning definition differs")


def validate_carrier_schema_shape(schema: dict[str, object]) -> None:
    expected_root_keys = {
        "$schema",
        "$id",
        "title",
        "$comment",
        "type",
        "additionalProperties",
        "required",
        "properties",
        "$defs",
    }
    if set(schema) != expected_root_keys:
        raise TemporalCandidateError("candidate carrier schema fields differ")
    if (
        schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("$id") != CARRIER_SCHEMA_ID
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or schema.get("required")
        != [
            "schemaVersion",
            "matrixId",
            "status",
            "executionPosture",
            "coordinateContract",
            "sourceAuthority",
            "rows",
        ]
    ):
        raise TemporalCandidateError("candidate carrier root shape differs")
    comment = schema.get("$comment")
    if type(comment) is not str or "NEW_CANDIDATE" not in comment:
        raise TemporalCandidateError("candidate carrier currentness differs")
    properties = schema.get("properties")
    if type(properties) is not dict:
        raise TemporalCandidateError("candidate carrier properties are absent")
    rows = properties.get("rows")
    if (
        _schema_semantics(properties.get("schemaVersion"))
        != {"const": CARRIER_SCHEMA_VERSION}
        or _schema_semantics(properties.get("matrixId"))
        != {"const": CARRIER_MATRIX_ID}
        or _schema_semantics(properties.get("status"))
        != {"const": CARRIER_MATRIX_STATUS}
        or _schema_semantics(properties.get("executionPosture"))
        != {"const": CARRIER_EXECUTION_POSTURE}
        or _schema_semantics(properties.get("sourceAuthority"))
        != {"const": CARRIER_SOURCE_AUTHORITY}
        or _schema_semantics(properties.get("coordinateContract"))
        != {
            "type": "object",
            "additionalProperties": False,
            "required": ["schemaVersion", "schemaDigest"],
            "properties": {
                "schemaVersion": {"const": CONTRACT_VERSION},
                "schemaDigest": {
                    "type": "string",
                    "pattern": "^sha256:[0-9a-f]{64}$",
                },
            },
        }
        or _schema_semantics(rows)
        != {
            "type": "array",
            "minItems": len(CARRIER_ROW_IDS),
            "maxItems": len(CARRIER_ROW_IDS),
            "uniqueItems": True,
            "items": {"$ref": "#/$defs/carrierMatrixRow"},
        }
        or set(properties)
        != {
            "schemaVersion",
            "matrixId",
            "status",
            "executionPosture",
            "coordinateContract",
            "sourceAuthority",
            "rows",
        }
    ):
        raise TemporalCandidateError("candidate carrier properties differ")
    definitions = schema.get("$defs")
    if type(definitions) is not dict or set(definitions) != {"carrierMatrixRow"}:
        raise TemporalCandidateError("candidate carrier definitions differ")
    _expect_closed_schema_definition(
        definitions,
        "carrierMatrixRow",
        required=[
            "rowId",
            "recordOrEventFamily",
            "authoritativeValidTimeCarrierRule",
            "allowedSecondaryTimeAndConsistencyRule",
            "windowAndRefusalRule",
        ],
        properties={
            "rowId": {"enum": list(CARRIER_ROW_IDS)},
            "recordOrEventFamily": {"type": "string", "minLength": 1},
            "authoritativeValidTimeCarrierRule": {
                "type": "string",
                "minLength": 1,
            },
            "allowedSecondaryTimeAndConsistencyRule": {
                "type": "string",
                "minLength": 1,
            },
            "windowAndRefusalRule": {"type": "string", "minLength": 1},
        },
    )


def validate_carrier_matrix(value: object) -> None:
    matrix = _closed_object(
        value,
        label="TemporalCarrierMatrix",
        allowed=frozenset(
            {
                "schemaVersion",
                "matrixId",
                "status",
                "executionPosture",
                "coordinateContract",
                "sourceAuthority",
                "rows",
            }
        ),
        required=frozenset(
            {
                "schemaVersion",
                "matrixId",
                "status",
                "executionPosture",
                "coordinateContract",
                "sourceAuthority",
                "rows",
            }
        ),
    )
    if (
        matrix["schemaVersion"] != CARRIER_SCHEMA_VERSION
        or matrix["matrixId"] != CARRIER_MATRIX_ID
        or matrix["status"] != CARRIER_MATRIX_STATUS
        or matrix["executionPosture"] != CARRIER_EXECUTION_POSTURE
        or matrix["sourceAuthority"] != CARRIER_SOURCE_AUTHORITY
    ):
        raise TemporalCandidateError("TemporalCarrierMatrix identity differs")
    coordinate_contract = _closed_object(
        matrix["coordinateContract"],
        label="TemporalCarrierMatrix coordinateContract",
        allowed=frozenset({"schemaVersion", "schemaDigest"}),
        required=frozenset({"schemaVersion", "schemaDigest"}),
    )
    if coordinate_contract != {
        "schemaVersion": CONTRACT_VERSION,
        "schemaDigest": f"sha256:{_sha256(COORDINATE_SCHEMA_PATH)}",
    }:
        raise TemporalCandidateError("carrier matrix coordinate binding differs")
    rows = matrix["rows"]
    if type(rows) is not list or len(rows) != len(CARRIER_ROW_IDS):
        raise TemporalCandidateError("carrier matrix row count differs")
    normalized_adr = ADR_PATH.read_text(encoding="utf-8").replace("`", "")
    observed_row_ids: list[str] = []
    text_fields = (
        "recordOrEventFamily",
        "authoritativeValidTimeCarrierRule",
        "allowedSecondaryTimeAndConsistencyRule",
        "windowAndRefusalRule",
    )
    for index, value_row in enumerate(rows):
        row = _closed_object(
            value_row,
            label=f"TemporalCarrierMatrix row {index}",
            allowed=frozenset({"rowId", *text_fields}),
            required=frozenset({"rowId", *text_fields}),
        )
        row_id = row["rowId"]
        if type(row_id) is not str:
            raise TemporalCandidateError("carrier matrix rowId is not text")
        observed_row_ids.append(row_id)
        for field in text_fields:
            rule = row[field]
            if type(rule) is not str or not rule:
                raise TemporalCandidateError(f"carrier matrix {field} is empty")
            if rule not in normalized_adr:
                raise TemporalCandidateError(
                    f"carrier matrix {row_id} {field} differs from ADR 0002"
                )
    if tuple(observed_row_ids) != CARRIER_ROW_IDS:
        raise TemporalCandidateError("carrier matrix row identities differ")


def validate_selection_schema_shape(schema: dict[str, object]) -> None:
    if (
        schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("$id") != SELECTION_SCHEMA_ID
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or schema.get("required")
        != [
            "schemaVersion",
            "bindingId",
            "status",
            "executionPosture",
            "identityAuthority",
            "coordinateContract",
            "carrierMatrix",
            "sourceContracts",
            "selectors",
            "unsupportedEnvelopeFields",
        ]
    ):
        raise TemporalCandidateError(
            "candidate carrier-selection schema root differs"
        )
    comment = schema.get("$comment")
    properties = schema.get("properties")
    if (
        type(comment) is not str
        or "NEW_CANDIDATE" not in comment
        or "caller data never selects" not in comment
        or type(properties) is not dict
    ):
        raise TemporalCandidateError(
            "candidate carrier-selection schema authority differs"
        )
    expected_constants = {
        "schemaVersion": SELECTION_SCHEMA_VERSION,
        "bindingId": SELECTION_BINDING_ID,
        "status": SELECTION_STATUS,
        "executionPosture": SELECTION_EXECUTION_POSTURE,
        "identityAuthority": SELECTION_IDENTITY_AUTHORITY,
    }
    for field, expected in expected_constants.items():
        if _schema_semantics(properties.get(field)) != {"const": expected}:
            raise TemporalCandidateError(
                f"candidate carrier-selection {field} differs"
            )
    expected_binding = _expected_selection_binding()
    for field in (
        "coordinateContract",
        "carrierMatrix",
        "sourceContracts",
        "selectors",
        "unsupportedEnvelopeFields",
    ):
        if _schema_semantics(properties.get(field)) != {
            "const": expected_binding[field]
        }:
            raise TemporalCandidateError(
                f"candidate carrier-selection {field} authority differs"
            )
    if "$defs" in schema:
        raise TemporalCandidateError(
            "candidate carrier-selection schema has unused definitions"
        )


def _expected_selection_binding() -> dict[str, object]:
    return {
        "schemaVersion": SELECTION_SCHEMA_VERSION,
        "bindingId": SELECTION_BINDING_ID,
        "status": SELECTION_STATUS,
        "executionPosture": SELECTION_EXECUTION_POSTURE,
        "identityAuthority": SELECTION_IDENTITY_AUTHORITY,
        "coordinateContract": {
            "schemaVersion": CONTRACT_VERSION,
            "schemaDigest": f"sha256:{_sha256(COORDINATE_SCHEMA_PATH)}",
        },
        "carrierMatrix": {
            "matrixId": CARRIER_MATRIX_ID,
            "matrixDigest": f"sha256:{_sha256(CARRIER_MATRIX_PATH)}",
            "rowId": SELECTION_ROW_ID,
        },
        "sourceContracts": [
            {
                "contractRole": "SEMANTIC_EVENT_ENVELOPE",
                "schemaVersion": ENVELOPE_SCHEMA_VERSION,
                "schemaDigest": f"sha256:{_sha256(ENVELOPE_SCHEMA_PATH)}",
                "discriminatorPath": "/primaryEventFamily",
                "discriminatorValue": "InterventionEvent",
            },
            {
                "contractRole": "EXECUTION_RECORD_PAYLOAD",
                "schemaVersion": EXECUTION_SCHEMA_VERSION,
                "schemaDigest": f"sha256:{_sha256(EXECUTION_SCHEMA_PATH)}",
                "discriminatorPath": "/recordClass",
                "discriminatorValue": "OPERATION_CLAIM",
            },
        ],
        "selectors": [
            {
                "selectorId": "INTERVENTION_OCCURRENCE",
                "sourceContractRole": "SEMANTIC_EVENT_ENVELOPE",
                "carrierShape": "POINT",
                "valuePath": "/timeSemantics/eventTime",
                "windowMeaning": "EVENT_OCCURRENCE",
            },
            {
                "selectorId": "INTERVENTION_EXECUTION_INTERVAL",
                "sourceContractRole": "EXECUTION_RECORD_PAYLOAD",
                "carrierShape": "BOUNDED_HALF_OPEN_INTERVAL",
                "startPath": "/effectiveTimeInterval/start",
                "endPath": "/effectiveTimeInterval/end",
                "timeBasisPath": "/effectiveTimeInterval/timeBasis",
                "requiredTimeBasis": "EXECUTION_INTERVAL",
                "windowMeaning": "STATE_OVERLAP",
            },
        ],
        "unsupportedEnvelopeFields": [
            "/timeSemantics/effectiveFrom",
            "/timeSemantics/effectiveUntil",
        ],
    }


def validate_selection_binding(value: object) -> None:
    if value != _expected_selection_binding():
        raise TemporalCandidateError(
            "intervention carrier-selection binding differs"
        )


def _schema_version(path: Path) -> str:
    schema = _load_json(path)
    value = (
        schema.get("properties", {})
        .get("schemaVersion", {})
        .get("const")
    )
    if type(value) is not str:
        raise TemporalCandidateError(
            f"{path.name} has no fixed schemaVersion"
        )
    return value


def validate_persistence_admission_authority() -> None:
    if not PERSISTENCE_ADMISSION_RFC_PATH.is_file():
        raise TemporalCandidateError(
            "RuntimeBundle persistence-admission authority is missing"
        )
    try:
        authority_bytes = PERSISTENCE_ADMISSION_RFC_PATH.read_bytes()
    except OSError as exc:
        raise TemporalCandidateError(
            "RuntimeBundle persistence-admission authority is unreadable"
        ) from exc
    if len(authority_bytes) != PERSISTENCE_ADMISSION_RFC_BYTE_LENGTH:
        raise TemporalCandidateError(
            "RuntimeBundle persistence-admission authority byte length differs"
        )
    if (
        hashlib.sha256(authority_bytes).hexdigest()
        != PERSISTENCE_ADMISSION_RFC_DIGEST
    ):
        raise TemporalCandidateError(
            "RuntimeBundle persistence-admission authority digest differs"
        )


def _exact_keyword(call: ast.Call, name: str, label: str) -> ast.expr:
    values = [keyword.value for keyword in call.keywords if keyword.arg == name]
    if len(values) != 1:
        raise TemporalCandidateError(f"{label} {name} field differs")
    return values[0]


def _literal_field(call: ast.Call, name: str, label: str) -> object:
    value = _exact_keyword(call, name, label)
    if not isinstance(value, ast.Constant):
        raise TemporalCandidateError(f"{label} {name} field is not literal")
    return value.value


def _parse_tenant_version_3_literal(module: ast.Module) -> str:
    assignments = [
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "TENANT_AUTHORITATIVE_MIGRATION_SET"
            for target in node.targets
        )
    ]
    if len(assignments) != 1:
        raise TemporalCandidateError(
            "tenant migration-set authority assignment differs"
        )
    assignment = assignments[0]
    if (
        len(assignment.targets) != 1
        or not isinstance(assignment.targets[0], ast.Name)
        or not isinstance(assignment.value, ast.Call)
        or not isinstance(assignment.value.func, ast.Name)
        or assignment.value.func.id != "AuthoritativeMigrationSet"
        or assignment.value.args
        or {keyword.arg for keyword in assignment.value.keywords}
        != {"service", "migrations", "digest"}
    ):
        raise TemporalCandidateError(
            "tenant migration-set authority assignment differs"
        )
    service = _exact_keyword(
        assignment.value,
        "service",
        "tenant migration-set authority",
    )
    migrations = _exact_keyword(
        assignment.value,
        "migrations",
        "tenant migration-set authority",
    )
    digest = _literal_field(
        assignment.value,
        "digest",
        "tenant migration-set authority",
    )
    if (
        not isinstance(service, ast.Name)
        or service.id != "TENANT_SERVICE"
        or not isinstance(migrations, ast.Tuple)
        or type(digest) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
    ):
        raise TemporalCandidateError(
            "tenant migration-set authority structure differs"
        )

    version_3_entries: list[ast.Call] = []
    expected_fields = {
        "version",
        "filename",
        "source_sha256",
        "byte_length",
        "applied_prefix_digest",
    }
    for entry in migrations.elts:
        if (
            not isinstance(entry, ast.Call)
            or not isinstance(entry.func, ast.Name)
            or entry.func.id != "AuthoritativeMigration"
            or entry.args
            or {keyword.arg for keyword in entry.keywords} != expected_fields
        ):
            raise TemporalCandidateError(
                "tenant migration-set authority entry structure differs"
            )
        version = _literal_field(
            entry,
            "version",
            "tenant migration-set authority entry",
        )
        if type(version) is not int:
            raise TemporalCandidateError(
                "tenant migration-set authority entry version is not literal"
            )
        if version == 3:
            version_3_entries.append(entry)
    if len(version_3_entries) != 1:
        raise TemporalCandidateError(
            "tenant migration-set authority version-3 entry differs"
        )

    version_3 = version_3_entries[0]
    observed = {
        name: _literal_field(
            version_3,
            name,
            "tenant migration-set authority version-3 entry",
        )
        for name in expected_fields
    }
    expected = {
        "version": 3,
        "filename": KNOWLEDGE_STORAGE_MIGRATION_FILENAME,
        "source_sha256": f"sha256:{KNOWLEDGE_STORAGE_MIGRATION_DIGEST}",
        "byte_length": KNOWLEDGE_STORAGE_MIGRATION_BYTE_LENGTH,
        "applied_prefix_digest": KNOWLEDGE_STORAGE_MIGRATION_PREFIX_DIGEST,
    }
    if observed != expected:
        raise TemporalCandidateError(
            "tenant migration-set authority version-3 literal differs"
        )
    return KNOWLEDGE_STORAGE_MIGRATION_PREFIX_DIGEST


def _execute_migration_authority_source(source_text: str) -> types.ModuleType:
    if MIGRATION_AUTHORITY_PRIVATE_MODULE_NAME in sys.modules:
        raise TemporalCandidateError(
            "tenant migration-set private module name is already occupied"
        )
    module = types.ModuleType(MIGRATION_AUTHORITY_PRIVATE_MODULE_NAME)
    module.__file__ = str(MIGRATION_SET_AUTHORITY_PATH)
    module.__package__ = ""
    sys.modules[MIGRATION_AUTHORITY_PRIVATE_MODULE_NAME] = module
    try:
        code = compile(
            source_text,
            str(MIGRATION_SET_AUTHORITY_PATH),
            "exec",
        )
        exec(code, module.__dict__)
    except Exception as exc:
        raise TemporalCandidateError(
            "tenant migration-set authority module failed to load"
        ) from exc
    finally:
        sys.modules.pop(MIGRATION_AUTHORITY_PRIVATE_MODULE_NAME, None)
    return module


def _validated_migration_set_shape(value: object) -> _AuthenticatedMigrationSet:
    migrations = getattr(value, "migrations", None)
    prefix_digest = getattr(value, "prefix_digest", None)
    if type(migrations) is not tuple or not migrations or not callable(prefix_digest):
        raise TemporalCandidateError(
            "authenticated tenant migration-set shape differs"
        )
    for migration in migrations:
        if (
            type(getattr(migration, "version", None)) is not int
            or type(getattr(migration, "filename", None)) is not str
            or type(getattr(migration, "source_bytes", None)) is not bytes
            or type(getattr(migration, "source_sha256", None)) is not str
            or type(getattr(migration, "byte_length", None)) is not int
        ):
            raise TemporalCandidateError(
                "authenticated tenant migration entry shape differs"
            )
    return cast(_AuthenticatedMigrationSet, value)


def load_tenant_migration_authority_snapshot() -> TenantMigrationAuthoritySnapshot:
    validate_persistence_admission_authority()
    try:
        source_bytes = MIGRATION_SET_AUTHORITY_PATH.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        parsed_module = ast.parse(
            source_text,
            filename=str(MIGRATION_SET_AUTHORITY_PATH),
        )
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise TemporalCandidateError(
            "tenant migration-set authority is not parseable"
        ) from exc
    module = _execute_migration_authority_source(source_text)
    loader = getattr(module, "load_authoritative_migration_set", None)
    tenant_service = getattr(module, "TENANT_SERVICE", None)
    migration_error = getattr(module, "MigrationSetError", None)
    if (
        not callable(loader)
        or getattr(tenant_service, "identity", None)
        != "ofarm.tenant-postgresql.v1"
        or not isinstance(migration_error, type)
        or not issubclass(migration_error, Exception)
    ):
        raise TemporalCandidateError(
            "tenant migration-set authority exports differ"
        )
    try:
        raw_migration_set = loader(PACKAGE_ROOT, tenant_service)
    except migration_error as exc:
        raise TemporalCandidateError(
            "tenant migration-set authority refused the checked-in release"
        ) from exc
    except Exception as exc:
        raise TemporalCandidateError(
            "tenant migration-set authority loader failed"
        ) from exc
    if getattr(raw_migration_set, "service", None) != tenant_service:
        raise TemporalCandidateError(
            "authenticated tenant migration-set service differs"
        )
    migration_set = _validated_migration_set_shape(raw_migration_set)
    parsed_version_3_prefix = _parse_tenant_version_3_literal(parsed_module)
    if len(migration_set.migrations) < 3:
        raise TemporalCandidateError(
            "authenticated tenant migration-set has no version-3 entry"
        )
    version_3 = migration_set.migrations[2]
    if (
        version_3.version != 3
        or version_3.filename != KNOWLEDGE_STORAGE_MIGRATION_FILENAME
        or version_3.source_sha256
        != f"sha256:{KNOWLEDGE_STORAGE_MIGRATION_DIGEST}"
        or version_3.byte_length != KNOWLEDGE_STORAGE_MIGRATION_BYTE_LENGTH
    ):
        raise TemporalCandidateError(
            "authenticated tenant migration-set version-3 entry differs"
        )
    try:
        authenticated_version_3_prefix = migration_set.prefix_digest(3)
    except Exception as exc:
        raise TemporalCandidateError(
            "authenticated tenant migration-set version-3 prefix failed"
        ) from exc
    if (
        type(authenticated_version_3_prefix) is not str
        or authenticated_version_3_prefix != parsed_version_3_prefix
        or authenticated_version_3_prefix
        != KNOWLEDGE_STORAGE_MIGRATION_PREFIX_DIGEST
    ):
        raise TemporalCandidateError(
            "parsed and authenticated tenant version-3 prefixes differ"
        )
    return TenantMigrationAuthoritySnapshot(
        migration_set=migration_set,
        version_3_prefix=authenticated_version_3_prefix,
    )


def validate_command_schema_shape(
    schema: dict[str, object],
    binding: dict[str, object],
) -> None:
    if _sha256(COMMAND_SCHEMA_PATH) != COMMAND_SCHEMA_DIGEST:
        raise TemporalCandidateError(
            "temporal governed-command schema digest differs"
        )
    if set(schema) != {"$schema", "$id", "title", "$comment", "const"}:
        raise TemporalCandidateError(
            "temporal governed-command schema fields differ"
        )
    if (
        schema.get("$schema")
        != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("$id") != COMMAND_SCHEMA_ID
        or schema.get("title")
        != "OFARM TemporalGovernedCommandBinding v0.1 (candidate)"
        or schema.get("const") != binding
    ):
        raise TemporalCandidateError(
            "temporal governed-command exact schema differs"
        )
    comment = schema.get("$comment")
    if (
        type(comment) is not str
        or "NEW_CANDIDATE exact schema" not in comment
        or "no production route or activation" not in comment
        or "no caller-selected temporal or tenant authority" not in comment
    ):
        raise TemporalCandidateError(
            "temporal governed-command schema posture differs"
        )


def validate_command_binding(
    binding: dict[str, object],
    migration_authority: TenantMigrationAuthoritySnapshot,
) -> None:
    if _sha256(COMMAND_BINDING_PATH) != COMMAND_BINDING_DIGEST:
        raise TemporalCandidateError(
            "temporal governed-command binding digest differs"
        )
    expected_fields = {
        "schemaVersion",
        "bindingId",
        "status",
        "executionPosture",
        "identityAuthority",
        "command",
        "prerequisites",
        "sourceContracts",
        "evidenceContracts",
        "admissionRules",
        "trustedAuthorities",
        "stateTransitions",
        "idempotency",
        "outcomeRules",
        "durableBatch",
        "unsupported",
        "implementationStops",
    }
    if set(binding) != expected_fields:
        raise TemporalCandidateError(
            "temporal governed-command binding fields differ"
        )
    if {
        field: binding.get(field)
        for field in (
            "schemaVersion",
            "bindingId",
            "status",
            "executionPosture",
            "identityAuthority",
        )
    } != {
        "schemaVersion": COMMAND_SCHEMA_VERSION,
        "bindingId": COMMAND_BINDING_ID,
        "status": COMMAND_STATUS,
        "executionPosture": COMMAND_EXECUTION_POSTURE,
        "identityAuthority": COMMAND_IDENTITY_AUTHORITY,
    }:
        raise TemporalCandidateError(
            "temporal governed-command identity differs"
        )
    version_3 = migration_authority.migration_set.migrations[2]
    if binding.get("command") != {
        "commandId": "COMMIT_OPERATION_CLAIM_DRAFT",
        "governedOperation": "COMMIT_OPERATION_CLAIM_DRAFT",
        "ingressChannel": "MANUAL_UI",
        "actionClass": "ASSERT_OPERATION_CLAIM",
        "actionStage": "DRAFT_PREPARATION",
        "successOutcome": "RETAIN_DRAFT",
        "promotionOutcome": "UNSUPPORTED",
        "routePosture": "CLOSED",
    }:
        raise TemporalCandidateError(
            "temporal governed-command specialization differs"
        )
    if binding.get("prerequisites") != [
        {
            "role": "TEMPORAL_COORDINATE",
            "identity": CONTRACT_VERSION,
            "digest": f"sha256:{_sha256(COORDINATE_SCHEMA_PATH)}",
        },
        {
            "role": "TENANT_KNOWLEDGE_POSITION_STORAGE",
            "identity": KNOWLEDGE_STORAGE_ID,
            "rfcDigest": (
                f"sha256:{_sha256(KNOWLEDGE_STORAGE_RFC_PATH)}"
            ),
            "migrationDigest": version_3.source_sha256,
            "migrationSetHead": migration_authority.version_3_prefix,
        },
        {
            "role": "INTERVENTION_VALID_TIME_SELECTION",
            "identity": SELECTION_BINDING_ID,
            "digest": f"sha256:{_sha256(SELECTION_BINDING_PATH)}",
        },
    ]:
        raise TemporalCandidateError(
            "temporal governed-command prerequisite binding differs"
        )
    if (
        _sha256(KNOWLEDGE_STORAGE_RFC_PATH)
        != KNOWLEDGE_STORAGE_RFC_DIGEST
        or version_3.source_sha256
        != f"sha256:{KNOWLEDGE_STORAGE_MIGRATION_DIGEST}"
    ):
        raise TemporalCandidateError(
            "tenant knowledge-position prerequisite digest differs"
        )
    expected_source_contracts = [
        {
            "role": "COMMAND_REQUEST",
            "schemaVersion": _schema_version(COMMIT_REQUEST_SCHEMA_PATH),
            "schemaDigest": (
                f"sha256:{_sha256(COMMIT_REQUEST_SCHEMA_PATH)}"
            ),
            "discriminatorPath": "/commitClass",
            "discriminatorValue": "OPERATION_CLAIM",
        },
        {
            "role": "SEMANTIC_EVENT",
            "schemaVersion": _schema_version(ENVELOPE_SCHEMA_PATH),
            "schemaDigest": f"sha256:{_sha256(ENVELOPE_SCHEMA_PATH)}",
            "discriminatorPath": "/primaryEventFamily",
            "discriminatorValue": "InterventionEvent",
        },
        {
            "role": "EXECUTION_PAYLOAD",
            "schemaVersion": _schema_version(EXECUTION_SCHEMA_PATH),
            "schemaDigest": f"sha256:{_sha256(EXECUTION_SCHEMA_PATH)}",
            "discriminatorPath": "/recordClass",
            "discriminatorValue": "OPERATION_CLAIM",
        },
    ]
    if binding.get("sourceContracts") != expected_source_contracts:
        raise TemporalCandidateError(
            "temporal governed-command source contracts differ"
        )
    expected_evidence_contracts = [
        ("AUTHORIZATION_REQUEST", AUTHORIZATION_REQUEST_SCHEMA_PATH),
        ("AUTHORIZATION_RESULT", AUTHORIZATION_RESULT_SCHEMA_PATH),
        ("AUTHORIZATION_TRACE", AUTHORIZATION_TRACE_SCHEMA_PATH),
        ("PROMOTION_TRACE", PROMOTION_TRACE_SCHEMA_PATH),
        ("COMMAND_RESULT", COMMIT_RESULT_SCHEMA_PATH),
        ("RUNTIME_PROBLEM", RUNTIME_PROBLEM_SCHEMA_PATH),
    ]
    if binding.get("evidenceContracts") != [
        {
            "role": role,
            "schemaVersion": _schema_version(path),
            "schemaDigest": f"sha256:{_sha256(path)}",
        }
        for role, path in expected_evidence_contracts
    ]:
        raise TemporalCandidateError(
            "temporal governed-command evidence contracts differ"
        )

    admission_rules = binding.get("admissionRules")
    trusted_authorities = binding.get("trustedAuthorities")
    outcome_rules = binding.get("outcomeRules")
    durable_batch = binding.get("durableBatch")
    if (
        type(admission_rules) is not list
        or tuple(
            rule.get("ruleId")
            for rule in admission_rules
            if type(rule) is dict
        )
        != (
            "ACTING_PARTY_IS_BOUND_PARTY",
            "HUMAN_PARTY_ONLY",
            "DRAFT_ONLY",
            "REQUEST_EVENT_IDENTITY",
            "EVENT_PAYLOAD_IDENTITY",
            "OPTIONAL_PAYLOAD_EVENT_BACKLINK",
            "EXACT_COMMAND_TARGET",
            "EVENT_TARGET",
            "EVENT_SUBJECT_TARGET",
            "PAYLOAD_SUBJECT_TARGET",
            "PAYLOAD_ANCHOR_TARGET",
            "PAYLOAD_ACTOR_IS_BOUND_PARTY",
            "CLAIMED_RECORD_ONLY",
        )
    ):
        raise TemporalCandidateError(
            "temporal governed-command admission rules differ"
        )
    if (
        type(trusted_authorities) is not list
        or tuple(
            authority.get("name")
            for authority in trusted_authorities
            if type(authority) is dict
        )
        != (
            "TENANT_AND_PRINCIPAL",
            "RUNTIME_BUNDLE_DIGEST",
            "AUTHORIZATION_DECISION",
            "COMMAND_EVALUATION_INSTANT",
            "KNOWLEDGE_POSITION",
            "VALID_TIME_BINDING",
        )
        or any(
            type(authority) is not dict
            or authority.get("callerSelectable") is not False
            for authority in trusted_authorities
        )
    ):
        raise TemporalCandidateError(
            "temporal governed-command authority map differs"
        )
    if (
        type(outcome_rules) is not list
        or tuple(
            rule.get("condition")
            for rule in outcome_rules
            if type(rule) is dict
        )
        != (
            "EXACT_REPLAY",
            "CONFLICTING_REPLAY",
            "AUTHORIZATION_DENY",
            "AUTHORIZATION_REVIEW_REQUIRED",
            "AUTHORIZATION_ALLOW_VALID_TIME_REFUSED",
            "AUTHORIZATION_ALLOW_VALID_TIME_SELECTED",
        )
    ):
        raise TemporalCandidateError(
            "temporal governed-command outcome rules differ"
        )
    if (
        type(durable_batch) is not dict
        or durable_batch.get("allocationPoint")
        != "AFTER_EXACT_REPLAY_CHECK_BEFORE_AUTHORITY_OR_TEMPORAL_OUTCOME"
        or durable_batch.get("knowledgeBeforeCommand")
        != "allocatedKnowledgePositionMinusOne"
        or durable_batch.get("sourceLane") != "draft"
        or durable_batch.get("exactReplayWrites") != []
        or durable_batch.get("conflictingReplayWrites") != []
        or durable_batch.get("newlyWrittenAllowedOutcomes")
        != ["RETAIN_DRAFT", "DENY", "REQUIRE_REVIEW"]
        or durable_batch.get("atomicity")
        != "ONE_BOUND_TENANT_TRANSACTION"
    ):
        raise TemporalCandidateError(
            "temporal governed-command batch policy differs"
        )
    idempotency = binding.get("idempotency")
    if (
        type(idempotency) is not dict
        or idempotency.get("replayEquality")
        != "SAME_REQUEST_DIGEST_AND_SAME_TRUSTED_RUNTIME_BUNDLE_DIGEST"
        or idempotency.get("exactReplay")
        != "RETURN_PRIOR_COMMITTED_RESULT_UNCHANGED_NO_NEW_BATCH"
        or idempotency.get("conflictingReplay")
        != (
            "REFUSE_NO_NEW_BATCH_NO_NEW_RECORD_"
            "NO_SECOND_IDEMPOTENCY_CLAIM"
        )
    ):
        raise TemporalCandidateError(
            "temporal governed-command idempotency policy differs"
        )
    required_unsupported = {
        "ROUTE_ACTIVATION",
        "PROMOTE_ACCEPTED",
        "CURRENT_STATE_MATERIALIZATION",
        "HISTORICAL_OR_WINDOW_EXECUTION",
        "CURRENT_STATE_READ",
        "QUALIFICATION_OR_OUTPUT",
        "DATABASE_OR_MIGRATION_CHANGE",
        "RUNTIME_BUNDLE_OR_PROFILE_ACTIVATION",
        "ISSUE_192_BEHAVIOR",
    }
    required_stops = {
        "NO_REVIEWED_PRODUCTION_AUTHORIZATION_PROVIDER_FOR_THIS_COMMAND",
        "NO_REVIEWED_RUNTIME_BUNDLE_SOURCE_FOR_COMMAND_AND_BINDING_IDENTITY",
        "ANY_REQUIRED_FROZEN_CONTRACT_CHANGE",
        "ANY_REQUIRED_PUBLIC_REFUSAL_VOCABULARY_CHANGE",
        "ANY_REQUIRED_ROUTE_OR_ACTIVE_REGISTRY_CHANGE",
    }
    # The digest still pins this exact version. If a reviewed artifact and
    # digest add stricter unsupported cases, only removal of this safety floor
    # is the semantic conformance failure.
    if (
        type(binding.get("unsupported")) is not list
        or not required_unsupported.issubset(binding["unsupported"])
        or type(binding.get("implementationStops")) is not list
        or set(binding["implementationStops"]) != required_stops
    ):
        raise TemporalCandidateError(
            "temporal governed-command stop conditions differ"
        )


def _expected_runtime_bundle_carrier_allowed_identities() -> list[dict[str, str]]:
    return [
        {
            "artifactKind": "TEMPORAL_CARRIER_MATRIX",
            "schemaVersion": CARRIER_SCHEMA_VERSION,
            "schemaPath": CARRIER_SCHEMA_RELATIVE_PATH,
            "schemaDigest": f"sha256:{_sha256(CARRIER_SCHEMA_PATH)}",
            "instanceIdentity": CARRIER_MATRIX_ID,
            "instancePath": CARRIER_MATRIX_RELATIVE_PATH,
            "instanceFileDigest": f"sha256:{_sha256(CARRIER_MATRIX_PATH)}",
            "canonicalInstanceDigest": _canonical_json_digest(
                CARRIER_MATRIX_PATH
            ),
        },
        {
            "artifactKind": "TEMPORAL_CARRIER_SELECTION_BINDING",
            "schemaVersion": SELECTION_SCHEMA_VERSION,
            "schemaPath": SELECTION_SCHEMA_RELATIVE_PATH,
            "schemaDigest": f"sha256:{_sha256(SELECTION_SCHEMA_PATH)}",
            "instanceIdentity": SELECTION_BINDING_ID,
            "instancePath": SELECTION_BINDING_RELATIVE_PATH,
            "instanceFileDigest": f"sha256:{_sha256(SELECTION_BINDING_PATH)}",
            "canonicalInstanceDigest": _canonical_json_digest(
                SELECTION_BINDING_PATH
            ),
        },
        {
            "artifactKind": "TEMPORAL_GOVERNED_COMMAND_BINDING",
            "schemaVersion": COMMAND_SCHEMA_VERSION,
            "schemaPath": COMMAND_SCHEMA_RELATIVE_PATH,
            "schemaDigest": f"sha256:{_sha256(COMMAND_SCHEMA_PATH)}",
            "instanceIdentity": COMMAND_BINDING_ID,
            "instancePath": COMMAND_BINDING_RELATIVE_PATH,
            "instanceFileDigest": f"sha256:{_sha256(COMMAND_BINDING_PATH)}",
            "canonicalInstanceDigest": _canonical_json_digest(
                COMMAND_BINDING_PATH
            ),
        },
    ]


def _expected_runtime_bundle_carrier_binding() -> dict[str, object]:
    return {
        "schemaVersion": RUNTIME_BUNDLE_CARRIER_SCHEMA_VERSION,
        "bindingId": RUNTIME_BUNDLE_CARRIER_BINDING_ID,
        "status": RUNTIME_BUNDLE_CARRIER_STATUS,
        "executionPosture": RUNTIME_BUNDLE_CARRIER_EXECUTION_POSTURE,
        "identityAuthority": RUNTIME_BUNDLE_CARRIER_IDENTITY_AUTHORITY,
        "componentVocabulary": {
            "role": RUNTIME_BUNDLE_CARRIER_ROLE,
            "canonicalization": "OFARM_CANONICAL_JSON_V1",
            "placement": "GLOBAL_IMMUTABLE_CONTENT",
            "meaning": "IMMUTABLE_PROVENANCE_ONLY",
            "identitySetSemantics": (
                "ALLOWED_IDENTITIES_NOT_REQUIRED_CO_PRESENCE"
            ),
        },
        "allowedIdentities": (
            _expected_runtime_bundle_carrier_allowed_identities()
        ),
        "schemaRelationship": {
            "schemaComponentRole": "CONTRACT_SCHEMA",
            "instanceComponentRole": RUNTIME_BUNDLE_CARRIER_ROLE,
            "sameRuntimeBundleRequiredWhenInstanceIsUsed": True,
            "completeDraft202012ValidationRequired": True,
            "digestReferenceWithoutRetainedInstance": "UNSUPPORTED",
        },
        "closureAuthority": {
            "carrierContractRule": "ELIGIBILITY_ONLY",
            "everyRuntimeBundleRequiresAllAllowedIdentities": False,
            "everyRoleUseRequiresAllAllowedIdentities": False,
            "futureCommandId": "COMMIT_OPERATION_CLAIM_DRAFT",
            "exactRequiredComponentClosureOwner": (
                "LATER_REVIEWED_GOVERNED_COMMAND_AND_TENANT_"
                "RUNTIME_BUNDLE_SELECTION_CONTRACT"
            ),
        },
        "forbiddenContentClasses": [
            "TENANT_IDENTITY",
            "PRINCIPAL_OR_PARTY_IDENTITY",
            "REQUEST_OR_BATCH_IDENTITY",
            "KNOWLEDGE_POSITION",
            "DEPLOYMENT_SECRET_OR_CREDENTIAL",
            "MUTABLE_ACTIVATION_STATE",
        ],
        "candidateIsolation": {
            "runtimeBundleMembership": "UNSUPPORTED",
            "activeRegistryMembership": "UNSUPPORTED",
            "profileActivation": "UNSUPPORTED",
            "presenceMeaningIfLaterPromoted": (
                "PROVENANCE_ONLY_NO_EXECUTION"
            ),
        },
        "implementationStops": [
            "NO_CANDIDATE_RUNTIME_BUNDLE_MEMBERSHIP",
            "NO_TEMPORAL_CANDIDATE_PROMOTION_OR_REWRITE",
            "NO_DATABASE_COMPONENT_ROLE_OR_PUBLISHER_CHANGE",
            "NO_ACTIVE_RUNTIME_BUNDLE_CATALOG_OR_MODEL_CHANGE",
            "NO_TENANT_COMMAND_RUNTIME_BUNDLE_SELECTION",
            "NO_GOVERNED_COMMAND_OR_AUTHORIZATION_CONNECTION",
            "NO_ROUTE_PROFILE_MATERIALIZATION_READ_HISTORY_WINDOW_OR_OUTPUT",
            "NO_ISSUE_192_BEHAVIOR",
        ],
    }


def validate_runtime_bundle_carrier_binding(value: object) -> None:
    expected = _expected_runtime_bundle_carrier_binding()
    binding = _closed_object(
        value,
        label="TemporalGovernanceRuntimeBundleCarrierBinding",
        allowed=frozenset(expected),
        required=frozenset(expected),
    )
    if (
        binding["schemaVersion"] != RUNTIME_BUNDLE_CARRIER_SCHEMA_VERSION
        or binding["bindingId"] != RUNTIME_BUNDLE_CARRIER_BINDING_ID
        or binding["status"] != RUNTIME_BUNDLE_CARRIER_STATUS
        or binding["executionPosture"]
        != RUNTIME_BUNDLE_CARRIER_EXECUTION_POSTURE
        or binding["identityAuthority"]
        != RUNTIME_BUNDLE_CARRIER_IDENTITY_AUTHORITY
    ):
        raise TemporalCandidateError(
            "temporal RuntimeBundle carrier identity differs"
        )
    if binding["componentVocabulary"] != {
        "role": RUNTIME_BUNDLE_CARRIER_ROLE,
        "canonicalization": "OFARM_CANONICAL_JSON_V1",
        "placement": "GLOBAL_IMMUTABLE_CONTENT",
        "meaning": "IMMUTABLE_PROVENANCE_ONLY",
        "identitySetSemantics": (
            "ALLOWED_IDENTITIES_NOT_REQUIRED_CO_PRESENCE"
        ),
    }:
        raise TemporalCandidateError(
            "temporal RuntimeBundle component vocabulary differs"
        )
    allowed_identities = binding["allowedIdentities"]
    expected_identities = expected["allowedIdentities"]
    if (
        type(allowed_identities) is not list
        or allowed_identities != expected_identities
    ):
        raise TemporalCandidateError(
            "temporal RuntimeBundle carrier allowed identity set differs"
        )
    closure = binding["closureAuthority"]
    if (
        type(closure) is not dict
        or closure.get("carrierContractRule") != "ELIGIBILITY_ONLY"
        or closure.get("everyRuntimeBundleRequiresAllAllowedIdentities")
        is not False
        or closure.get("everyRoleUseRequiresAllAllowedIdentities") is not False
        or closure.get("futureCommandId") != "COMMIT_OPERATION_CLAIM_DRAFT"
        or closure.get("exactRequiredComponentClosureOwner")
        != (
            "LATER_REVIEWED_GOVERNED_COMMAND_AND_TENANT_"
            "RUNTIME_BUNDLE_SELECTION_CONTRACT"
        )
    ):
        raise TemporalCandidateError(
            "temporal RuntimeBundle component closure authority differs"
        )
    if binding != expected:
        raise TemporalCandidateError(
            "temporal RuntimeBundle carrier binding differs"
        )


def validate_runtime_bundle_carrier_schema_shape(
    schema: dict[str, object],
    binding: dict[str, object],
) -> None:
    if _sha256(RUNTIME_BUNDLE_CARRIER_SCHEMA_PATH) != (
        RUNTIME_BUNDLE_CARRIER_SCHEMA_DIGEST
    ):
        raise TemporalCandidateError(
            "temporal RuntimeBundle carrier schema digest differs"
        )
    if _sha256(RUNTIME_BUNDLE_CARRIER_BINDING_PATH) != (
        RUNTIME_BUNDLE_CARRIER_BINDING_DIGEST
    ):
        raise TemporalCandidateError(
            "temporal RuntimeBundle carrier binding digest differs"
        )
    if (
        set(schema) != {"$schema", "$id", "title", "$comment", "const"}
        or schema.get("$schema")
        != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("$id") != RUNTIME_BUNDLE_CARRIER_SCHEMA_ID
        or schema.get("title")
        != (
            "OFARM TemporalGovernanceRuntimeBundleCarrierBinding "
            "v0.1 (candidate)"
        )
        or schema.get("const") != binding
    ):
        raise TemporalCandidateError(
            "temporal RuntimeBundle carrier schema shape differs"
        )
    comment = schema.get("$comment")
    if (
        type(comment) is not str
        or "NEW_CANDIDATE" not in comment
        or "closed allowed set, not a required component closure"
        not in comment
        or "inactive" not in comment
        or "changes no RuntimeBundle authority" not in comment
    ):
        raise TemporalCandidateError(
            "temporal RuntimeBundle carrier schema authority differs"
        )


def _exact_bytes_component(
    identity: str,
    relative_path: str,
    path: Path,
) -> dict[str, object]:
    return {
        "role": "CONTRACT_SCHEMA",
        "identity": identity,
        "sourcePath": relative_path,
        "canonicalization": "EXACT_BYTES_V1",
        "placement": "GLOBAL_IMMUTABLE_CONTENT",
        "byteLength": path.stat().st_size,
        "contentDigest": f"sha256:{_sha256(path)}",
    }


def _canonical_governance_component(
    identity: str,
    relative_path: str,
    path: Path,
    schema_identity: str,
) -> dict[str, object]:
    return {
        "role": RUNTIME_BUNDLE_CARRIER_ROLE,
        "identity": identity,
        "sourcePath": relative_path,
        "schemaIdentity": schema_identity,
        "canonicalization": "OFARM_CANONICAL_JSON_V1",
        "placement": "GLOBAL_IMMUTABLE_CONTENT",
        "byteLength": _canonical_json_length(path),
        "contentDigest": _canonical_json_digest(path),
    }


def _expected_runtime_bundle_selection_components() -> list[dict[str, object]]:
    schema_components = (
        (
            f"contract:{CONTRACT_VERSION}",
            COORDINATE_SCHEMA_RELATIVE_PATH,
            COORDINATE_SCHEMA_PATH,
        ),
        (
            f"contract:{CARRIER_SCHEMA_VERSION}",
            CARRIER_SCHEMA_RELATIVE_PATH,
            CARRIER_SCHEMA_PATH,
        ),
        (
            f"contract:{SELECTION_SCHEMA_VERSION}",
            SELECTION_SCHEMA_RELATIVE_PATH,
            SELECTION_SCHEMA_PATH,
        ),
        (
            f"contract:{COMMAND_SCHEMA_VERSION}",
            COMMAND_SCHEMA_RELATIVE_PATH,
            COMMAND_SCHEMA_PATH,
        ),
        (
            f"contract:{_schema_version(COMMIT_REQUEST_SCHEMA_PATH)}",
            COMMIT_REQUEST_SCHEMA_PATH.relative_to(PACKAGE_ROOT).as_posix(),
            COMMIT_REQUEST_SCHEMA_PATH,
        ),
        (
            f"contract:{_schema_version(ENVELOPE_SCHEMA_PATH)}",
            ENVELOPE_SCHEMA_PATH.relative_to(PACKAGE_ROOT).as_posix(),
            ENVELOPE_SCHEMA_PATH,
        ),
        (
            f"contract:{_schema_version(EXECUTION_SCHEMA_PATH)}",
            EXECUTION_SCHEMA_PATH.relative_to(PACKAGE_ROOT).as_posix(),
            EXECUTION_SCHEMA_PATH,
        ),
        (
            f"contract:{_schema_version(AUTHORIZATION_REQUEST_SCHEMA_PATH)}",
            AUTHORIZATION_REQUEST_SCHEMA_PATH.relative_to(
                PACKAGE_ROOT
            ).as_posix(),
            AUTHORIZATION_REQUEST_SCHEMA_PATH,
        ),
        (
            f"contract:{_schema_version(AUTHORIZATION_RESULT_SCHEMA_PATH)}",
            AUTHORIZATION_RESULT_SCHEMA_PATH.relative_to(
                PACKAGE_ROOT
            ).as_posix(),
            AUTHORIZATION_RESULT_SCHEMA_PATH,
        ),
        (
            f"contract:{_schema_version(AUTHORIZATION_TRACE_SCHEMA_PATH)}",
            AUTHORIZATION_TRACE_SCHEMA_PATH.relative_to(
                PACKAGE_ROOT
            ).as_posix(),
            AUTHORIZATION_TRACE_SCHEMA_PATH,
        ),
        (
            f"contract:{_schema_version(PROMOTION_TRACE_SCHEMA_PATH)}",
            PROMOTION_TRACE_SCHEMA_PATH.relative_to(PACKAGE_ROOT).as_posix(),
            PROMOTION_TRACE_SCHEMA_PATH,
        ),
        (
            f"contract:{_schema_version(COMMIT_RESULT_SCHEMA_PATH)}",
            COMMIT_RESULT_SCHEMA_PATH.relative_to(PACKAGE_ROOT).as_posix(),
            COMMIT_RESULT_SCHEMA_PATH,
        ),
        (
            f"contract:{_schema_version(RUNTIME_PROBLEM_SCHEMA_PATH)}",
            RUNTIME_PROBLEM_SCHEMA_PATH.relative_to(PACKAGE_ROOT).as_posix(),
            RUNTIME_PROBLEM_SCHEMA_PATH,
        ),
    )
    result = [
        _exact_bytes_component(identity, relative_path, path)
        for identity, relative_path, path in schema_components
    ]
    result.extend(
        (
            _canonical_governance_component(
                CARRIER_MATRIX_ID,
                CARRIER_MATRIX_RELATIVE_PATH,
                CARRIER_MATRIX_PATH,
                f"contract:{CARRIER_SCHEMA_VERSION}",
            ),
            _canonical_governance_component(
                SELECTION_BINDING_ID,
                SELECTION_BINDING_RELATIVE_PATH,
                SELECTION_BINDING_PATH,
                f"contract:{SELECTION_SCHEMA_VERSION}",
            ),
            _canonical_governance_component(
                COMMAND_BINDING_ID,
                COMMAND_BINDING_RELATIVE_PATH,
                COMMAND_BINDING_PATH,
                f"contract:{COMMAND_SCHEMA_VERSION}",
            ),
        )
    )
    return result


def _assert_runtime_bundle_selection_digests() -> None:
    if _sha256(RUNTIME_BUNDLE_SELECTION_SCHEMA_PATH) != (
        RUNTIME_BUNDLE_SELECTION_SCHEMA_DIGEST
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection schema digest differs"
        )
    if _sha256(RUNTIME_BUNDLE_SELECTION_BINDING_PATH) != (
        RUNTIME_BUNDLE_SELECTION_BINDING_DIGEST
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection binding digest differs"
        )


def validate_runtime_bundle_selection_schema_shape(
    schema: dict[str, object],
    binding: dict[str, object],
) -> None:
    _assert_runtime_bundle_selection_digests()
    if (
        set(schema) != {"$schema", "$id", "title", "$comment", "const"}
        or schema.get("$schema")
        != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("$id") != RUNTIME_BUNDLE_SELECTION_SCHEMA_ID
        or schema.get("title")
        != (
            "OFARM TenantCommandRuntimeBundleSelectionBinding "
            "v0.1 (candidate)"
        )
        or schema.get("const") != binding
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection schema shape differs"
        )
    comment = schema.get("$comment")
    if (
        type(comment) is not str
        or "NEW_CANDIDATE exact schema" not in comment
        or "inactive and production-unbound" not in comment
        or "without adding storage" not in comment
        or "issue #192 behavior" not in comment
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection schema posture differs"
        )


def validate_runtime_bundle_selection_binding(value: object) -> None:
    _assert_runtime_bundle_selection_digests()
    expected = _load_json(RUNTIME_BUNDLE_SELECTION_BINDING_PATH)
    binding = _closed_object(
        value,
        label="TenantCommandRuntimeBundleSelectionBinding",
        allowed=frozenset(expected),
        required=frozenset(expected),
    )
    if {
        field: binding.get(field)
        for field in (
            "schemaVersion",
            "bindingId",
            "status",
            "executionPosture",
            "identityAuthority",
        )
    } != {
        "schemaVersion": RUNTIME_BUNDLE_SELECTION_SCHEMA_VERSION,
        "bindingId": RUNTIME_BUNDLE_SELECTION_BINDING_ID,
        "status": RUNTIME_BUNDLE_SELECTION_STATUS,
        "executionPosture": RUNTIME_BUNDLE_SELECTION_EXECUTION_POSTURE,
        "identityAuthority": RUNTIME_BUNDLE_SELECTION_IDENTITY_AUTHORITY,
    }:
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection identity differs"
        )
    if binding.get("command") != {
        "commandId": "COMMIT_OPERATION_CLAIM_DRAFT",
        "commandBindingId": COMMAND_BINDING_ID,
        "commandBindingCanonicalDigest": _canonical_json_digest(
            COMMAND_BINDING_PATH
        ),
    }:
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection command differs"
        )
    selection_source = binding.get("selectionSource")
    if (
        type(selection_source) is not dict
        or selection_source.get("sourceKind")
        != "IMMUTABLE_TENANT_COMMAND_SELECTION_RECORD"
        or selection_source.get("lookupKey")
        != ["TenantBinding.tenant_id", "LITERAL_SELECTION_BINDING_ID"]
        or selection_source.get("fixedSelectionBindingId")
        != RUNTIME_BUNDLE_SELECTION_BINDING_ID
        or selection_source.get("callerSelectable") is not False
        or selection_source.get("versionRule")
        != "ONE_IMMUTABLE_SELECTION_PER_TENANT_AND_BINDING_VERSION"
        or selection_source.get("changeRule")
        != "NEW_REVIEWED_SELECTION_BINDING_VERSION_REQUIRED"
        or selection_source.get("mutableCurrentPointer") != "UNSUPPORTED"
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection source differs"
        )
    expected_disallowed_selectors = {
        "CALLER_OR_REQUEST_DATA",
        "ROUTE_OR_HEADER_DATA",
        "PROFILE_OR_ENVIRONMENT_DATA",
        "CAPABILITY_OR_PRINCIPAL_DATA",
        "TIMESTAMP_OR_IDEMPOTENCY_DATA",
        "PUBLISHER_OR_BUNDLE_EXISTENCE",
        "LATEST_OR_SOLE_BUNDLE",
        "LOOSE_COMPONENT_ROWS",
    }
    if set(selection_source.get("disallowedSelectors", ())) != (
        expected_disallowed_selectors
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection refusal sources differ"
        )
    record = binding.get("selectionRecord")
    expected_record_fields = [
        "tenantId",
        "selectionBindingId",
        "selectionBindingCanonicalDigest",
        "commandId",
        "commandBindingId",
        "commandBindingCanonicalDigest",
        "runtimeBundleDigest",
        "selectionBatchId",
        "selectionKnowledgePosition",
    ]
    if (
        type(record) is not dict
        or record.get("identityFields")
        != ["tenantId", "selectionBindingId"]
        or record.get("authorityBearingFields") != expected_record_fields
        or record.get("tenantIdAuthority") != "TenantBinding.tenant_id"
        or record.get("selectionBindingIdAuthority")
        != "FIXED_REVIEWED_BINDING_ARTIFACT"
        or record.get("commandIdentityAuthority")
        != "FIXED_REVIEWED_BINDING_ARTIFACT"
        or record.get("runtimeBundleDigestAuthority")
        != "DEDICATED_TENANT_COMMAND_SELECTION_AUTHORITY"
        or record.get("selectionBatchAuthority")
        != "SEPARATELY_GOVERNED_SELECTION_ACTIVATION_BATCH"
        or record.get("selectionKnowledgeRule")
        != "MUST_PRECEDE_COMMAND_KNOWLEDGE_BEFORE"
        or record.get("custody") != "TENANT_OWNED_IMMUTABLE"
        or record.get("creation")
        != "ATOMIC_GOVERNED_SELECTION_ACTIVATION_ONLY"
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection record authority differs"
        )
    if record.get("stateTransitions") != [
        {
            "from": "ABSENT",
            "event": "EXACT_GOVERNED_ACTIVATION",
            "to": "SEALED",
        },
        {
            "from": "SEALED",
            "event": "EXACT_RETRY",
            "to": "SEALED",
            "effect": "NO_OP",
        },
        {
            "from": "SEALED",
            "event": "UNEQUAL_REUSE_UPDATE_DELETE_OR_REPLACEMENT",
            "to": "REFUSED",
            "effect": "NO_WRITE",
        },
    ]:
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection state transitions differ"
        )
    resolution = binding.get("resolution")
    if (
        type(resolution) is not dict
        or resolution.get("after") != "TRUSTED_TENANT_BINDING"
        or resolution.get("before")
        != "COMMAND_ADMISSION_EXACT_REPLAY_AND_BATCH_ALLOCATION"
        or resolution.get("inputAuthorities")
        != ["TenantBinding", "FIXED_REVIEWED_SELECTION_BINDING"]
        or resolution.get("successType") != "TrustedCommandRuntimeBundle"
        or resolution.get("refusal")
        != "RUNTIME_BUNDLE_SELECTION_REFUSED_NO_WRITE"
        or resolution.get("refusalVisibility")
        != "INTERNAL_NO_NEW_PUBLIC_REASON_CODE"
        or resolution.get("refusalWrites") != "NONE"
        or resolution.get("selectedDigestUse")
        != [
            "COMMAND_ADMISSION",
            "IDEMPOTENCY_REPLAY_EQUALITY",
            "BATCH_PROVENANCE",
            "EVIDENCE",
            "COMMAND_RESULT",
        ]
        or resolution.get("digestMutation") != "UNSUPPORTED"
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection resolution differs"
        )
    if binding.get("governancePrerequisite") != {
        "bindingId": RUNTIME_BUNDLE_CARRIER_BINDING_ID,
        "bindingFileDigest": (
            f"sha256:{_sha256(RUNTIME_BUNDLE_CARRIER_BINDING_PATH)}"
        ),
        "role": RUNTIME_BUNDLE_CARRIER_ROLE,
        "relationship": (
            "EXTERNAL_GOVERNANCE_PREREQUISITE_NOT_AN_EXTRA_ROLE_MEMBER"
        ),
    }:
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection prerequisite differs"
        )
    closure = binding.get("requiredComponentClosure")
    expected_components = _expected_runtime_bundle_selection_components()
    if (
        type(closure) is not dict
        or closure.get("semantics")
        != "EXACT_COMMAND_REQUIRED_COMPONENT_SUBSET"
        or closure.get("wholeBundleExactness")
        != "UNRELATED_COMPONENTS_MAY_EXIST_BUT_ARE_INERT_FOR_THIS_COMMAND"
        or closure.get("componentCount") != len(expected_components)
        or closure.get("components") != expected_components
        or closure.get("schemaValidation")
        != (
            "EACH_GOVERNANCE_INSTANCE_VALIDATES_COMPLETELY_"
            "AGAINST_ITS_SAME_BUNDLE_SCHEMA"
        )
        or closure.get("digestOnlyReference") != "UNSUPPORTED"
        or closure.get("missingOrSubstitutedComponent")
        != "RUNTIME_BUNDLE_SELECTION_REFUSED_NO_WRITE"
        or closure.get("unrelatedComponentAuthority") != "NONE"
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection closure differs"
        )
    authority_names = tuple(
        authority.get("name")
        for authority in binding.get("trustedAuthorities", ())
        if type(authority) is dict
    )
    if authority_names != (
        "TENANT_AND_PRINCIPAL_RELATIONSHIP",
        "SELECTION_RECORD",
        "BUNDLE_INTEGRITY",
        "COMPONENT_ROLE_AND_ALLOWED_IDENTITIES",
        "COMMAND_SEMANTICS",
        "KNOWLEDGE_POSITIONS",
        "AUTHORIZATION",
        "AUDIT_RUNTIME",
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection authority map differs"
        )
    expected_invariants = {
        f"TCRS-{number:03d}_{suffix}"
        for number, suffix in enumerate(
            (
                "ONE_COMMAND",
                "ONE_TRUSTED_SELECTION_SOURCE",
                "SEPARATE_SELECTION_CUSTODY",
                "BOUND_TENANT_ONLY",
                "PRIOR_GOVERNED_SELECTION",
                "IMMUTABLE_VERSIONED_SELECTION",
                "SELECTION_BEFORE_ADMISSION_REPLAY_AND_BATCH",
                "SEALED_RUNTIME_BUNDLE_ONLY",
                "EXACT_SIXTEEN_COMPONENT_COMMAND_CLOSURE",
                "SCHEMA_AND_INSTANCE_REQUIRED",
                "ONE_RUNTIME_BUNDLE_DIGEST_END_TO_END",
                "REPLAY_COUPLED_TO_SELECTED_DIGEST",
                "UNRELATED_COMPONENTS_INERT",
                "NO_IMPLICIT_SELECTION",
                "CANDIDATE_INACTIVE",
                "PRODUCTION_LEGACY_FIREWALL",
                "SELECTION_REFUSAL_IS_NO_WRITE",
                "ISSUE_192_SEPARATE",
            ),
            start=1,
        )
    }
    if set(binding.get("invariants", ())) != expected_invariants:
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection invariants differ"
        )
    expected_negative_cases = [
        "SELECTION_BEFORE_TENANT_BINDING",
        "CALLER_SUPPLIES_TENANT_BUNDLE_OR_BINDING_IDENTITY",
        "CAPABILITY_PRINCIPAL_PROFILE_ENVIRONMENT_OR_IDEMPOTENCY_SELECTS",
        "NEWEST_SOLE_OR_TIMESTAMP_ORDERING_SELECTS",
        "PUBLICATION_EXISTENCE_OR_LOOSE_COMPONENT_SELECTS",
        "MISSING_MUTABLE_CROSS_TENANT_OR_UNBATCHED_SELECTION_RECORD",
        "UNSEALED_OR_MISSING_RUNTIME_BUNDLE",
        "BUNDLE_DIGEST_MEMBERSHIP_BYTE_LENGTH_OR_COMPONENT_DIGEST_MISMATCH",
        "MISSING_WRONG_ROLE_OR_SUBSTITUTED_REQUIRED_COMPONENT",
        "GOVERNANCE_INSTANCE_SCHEMA_VALIDATION_FAILURE",
        "UNLISTED_TEMPORAL_IDENTITY_ALIAS_OR_DIGEST_ONLY_REFERENCE",
        "UNRELATED_COMPONENT_AFFECTS_COMMAND",
        "SELECTION_CHANGES_DURING_COMMAND",
        "REPLAY_USES_DIFFERENT_RUNTIME_BUNDLE_DIGEST",
        "SELECTION_REFUSAL_WRITES_ANYTHING",
        "LEGACY_STORE_CONFIG_OR_PROFILE_SELECTS",
        (
            "PUBLISHER_BINDER_APPLICATION_WORKER_AUTHORIZER_"
            "REGISTRAR_OR_IDENTITY_CONTROLLER_SELECTS"
        ),
        "ISSUE_192_BEHAVIOR_IS_ADDED",
    ]
    expected_unsupported = [
        "DATABASE_RELATION_MIGRATION_ROLE_OR_PRIVILEGE",
        "SELECTION_CONTROLLER_OR_ACTIVATION_BATCH",
        "ACTIVE_RUNTIME_BUNDLE_ROLE_MODEL_CATALOG_REPOSITORY_OR_PUBLISHER",
        "PRODUCTION_SELECTOR_OR_APPLICATION_RUNTIME_INTEGRATION",
        "COMMAND_OR_AUTHORIZATION_INTEGRATION",
        "ROUTE_PROFILE_OR_ACTIVE_REGISTRY",
        "MATERIALIZATION_CURRENT_STATE_READ_HISTORICAL_OR_WINDOW_EXECUTION",
        "OUTPUT_RECEIPT_QUALIFICATION_OR_PROMOTION",
        "HOT_RELOAD_UPGRADE_SUPERSESSION_OR_ROLLBACK",
        "FROZEN_ACTIVE_CONTRACT_OR_EXISTING_TEMPORAL_CANDIDATE_REWRITE",
        "ISSUE_192_BEHAVIOR",
    ]
    required_stops = {
        "NO_TEMPORAL_CANDIDATE_PROMOTION_OR_REPLACEMENT",
        "NO_ACTIVE_TEMPORAL_GOVERNANCE_COMPONENT_ROLE_OR_DATABASE_CONSTRAINT",
        "NO_ACTIVE_COMMAND_BINDING_SCHEMA_VERSION_EXTRACTION_FOR_TOP_LEVEL_CONST",
        "NO_REVIEWED_SELECTION_STORAGE_CONTROL_OR_GOVERNED_ACTIVATION",
        "NO_REVIEWED_PRODUCTION_READ_ONLY_SELECTOR_WITHOUT_LEGACY_IMPORTS",
        "NO_REVIEWED_SELECTION_REFUSAL_PUBLIC_REASON_MAPPING",
        "NO_REVIEWED_PRODUCTION_AUTHORIZATION_PROVIDER",
        "NO_GOVERNED_COMMAND_INTEGRATION",
        "NO_ROUTE_PROFILE_MATERIALIZATION_READ_HISTORY_WINDOW_OUTPUT_OR_RECEIPT",
        "NO_ISSUE_192_BEHAVIOR",
    }
    if (
        binding.get("negativeCases") != expected_negative_cases
        or binding.get("unsupported") != expected_unsupported
        or type(binding.get("implementationStops")) is not list
        or set(binding["implementationStops"]) != required_stops
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection stops differ"
        )
    if binding != expected:
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection binding differs"
        )


def _expected_promotion_subjects() -> list[dict[str, object]]:
    return [
        {
            "artifactKind": "TEMPORAL_CARRIER_MATRIX",
            "identity": CARRIER_MATRIX_ID,
            "subjectPath": CARRIER_MATRIX_RELATIVE_PATH,
            "repositoryFileDigest": f"sha256:{_sha256(CARRIER_MATRIX_PATH)}",
            "schemaVersion": CARRIER_SCHEMA_VERSION,
            "schemaPath": CARRIER_SCHEMA_RELATIVE_PATH,
            "schemaDigest": f"sha256:{_sha256(CARRIER_SCHEMA_PATH)}",
            "canonicalization": "OFARM_CANONICAL_JSON_V1",
            "canonicalByteLength": _canonical_json_length(
                CARRIER_MATRIX_PATH
            ),
            "canonicalContentDigest": _canonical_json_digest(
                CARRIER_MATRIX_PATH
            ),
            "creationState": CARRIER_MATRIX_STATUS,
            "preservedExecutionPosture": CARRIER_EXECUTION_POSTURE,
        },
        {
            "artifactKind": "TEMPORAL_CARRIER_SELECTION_BINDING",
            "identity": SELECTION_BINDING_ID,
            "subjectPath": SELECTION_BINDING_RELATIVE_PATH,
            "repositoryFileDigest": (
                f"sha256:{_sha256(SELECTION_BINDING_PATH)}"
            ),
            "schemaVersion": SELECTION_SCHEMA_VERSION,
            "schemaPath": SELECTION_SCHEMA_RELATIVE_PATH,
            "schemaDigest": f"sha256:{_sha256(SELECTION_SCHEMA_PATH)}",
            "canonicalization": "OFARM_CANONICAL_JSON_V1",
            "canonicalByteLength": _canonical_json_length(
                SELECTION_BINDING_PATH
            ),
            "canonicalContentDigest": _canonical_json_digest(
                SELECTION_BINDING_PATH
            ),
            "creationState": SELECTION_STATUS,
            "preservedExecutionPosture": SELECTION_EXECUTION_POSTURE,
        },
        {
            "artifactKind": "TEMPORAL_GOVERNED_COMMAND_BINDING",
            "identity": COMMAND_BINDING_ID,
            "subjectPath": COMMAND_BINDING_RELATIVE_PATH,
            "repositoryFileDigest": (
                f"sha256:{_sha256(COMMAND_BINDING_PATH)}"
            ),
            "schemaVersion": COMMAND_SCHEMA_VERSION,
            "schemaPath": COMMAND_SCHEMA_RELATIVE_PATH,
            "schemaDigest": f"sha256:{_sha256(COMMAND_SCHEMA_PATH)}",
            "canonicalization": "OFARM_CANONICAL_JSON_V1",
            "canonicalByteLength": _canonical_json_length(
                COMMAND_BINDING_PATH
            ),
            "canonicalContentDigest": _canonical_json_digest(
                COMMAND_BINDING_PATH
            ),
            "creationState": COMMAND_STATUS,
            "preservedExecutionPosture": COMMAND_EXECUTION_POSTURE,
        },
    ]


def _expected_promotion_binding() -> dict[str, object]:
    return {
        "schemaVersion": PROMOTION_SCHEMA_VERSION,
        "bindingId": PROMOTION_BINDING_ID,
        "status": PROMOTION_STATUS,
        "executionPosture": PROMOTION_EXECUTION_POSTURE,
        "identityAuthority": PROMOTION_IDENTITY_AUTHORITY,
        "promotionMeaning": {
            "sourceLifecycleState": "CANDIDATE_INACTIVE",
            "targetLifecycleState": "GOVERNED_INACTIVE",
            "effect": "EXTERNAL_LIFECYCLE_CLASSIFICATION_ONLY",
            "embeddedStatusMeaning": "IMMUTABLE_CREATION_STATE_ATTESTATION",
            "effectiveLifecycleAuthority": (
                "REVIEWED_PROMOTION_DECISION_AND_CURRENTNESS_TRACE"
            ),
            "currentDefaultPromotion": False,
            "runtimeActivation": False,
            "productionReadiness": False,
        },
        "subjectSet": {
            "setSemantics": (
                "EXACT_ATOMIC_PROMOTION_SET_NOT_RUNTIME_COMPONENT_CLOSURE"
            ),
            "dependencyOrder": [
                CARRIER_MATRIX_ID,
                SELECTION_BINDING_ID,
                COMMAND_BINDING_ID,
            ],
            "partialPromotion": (
                "REFUSED_ALL_REMAIN_CANDIDATE_INACTIVE"
            ),
            "subjects": _expected_promotion_subjects(),
        },
        "dependencyConsistency": {
            "selectorMatrixIdentity": CARRIER_MATRIX_ID,
            "selectorMatrixRepositoryFileDigest": (
                f"sha256:{_sha256(CARRIER_MATRIX_PATH)}"
            ),
            "selectorMatrixRowId": SELECTION_ROW_ID,
            "commandSelectorIdentity": SELECTION_BINDING_ID,
            "commandSelectorRepositoryFileDigest": (
                f"sha256:{_sha256(SELECTION_BINDING_PATH)}"
            ),
        },
        "decisionContract": {
            "allowedOutcomes": [
                "PROMOTE_GOVERNED_INACTIVE",
                "REFUSE_PROMOTION",
            ],
            "positiveOutcome": "PROMOTE_GOVERNED_INACTIVE",
            "positiveEffect": (
                "ALL_THREE_EXACT_SUBJECTS_BECOME_GOVERNED_INACTIVE"
            ),
            "refusalOutcome": "REFUSE_PROMOTION",
            "refusalEffect": (
                "ALL_THREE_SUBJECTS_REMAIN_CANDIDATE_INACTIVE"
            ),
            "requiredDecisionEvidenceFields": [
                "promotionDecisionRef",
                "humanPromotionAuthorityRef",
                "decidedAt",
                "reviewEvidenceRefs",
                "currentnessTraceRef",
            ],
            "humanGoverned": True,
            "contractApprovalIsPromotion": False,
            "mergeIsPromotion": False,
            "conformanceSuccessIsPromotion": False,
            "callerSelectable": False,
            "conflictDisposition": (
                "REFUSE_ALL_REMAIN_CANDIDATE_INACTIVE"
            ),
        },
        "authoritySeparation": {
            "bindingOwns": (
                "CLOSED_SUBJECT_SET_DIGESTS_ATOMICITY_"
                "AND_GOVERNED_INACTIVE_OUTCOME"
            ),
            "humanPromotionAuthorityOwns": "PROMOTE_OR_REFUSE_DECISION",
            "currentnessTraceOwns": (
                "EFFECTIVE_LIFECYCLE_HEAD_EVIDENCE"
            ),
            "subjectArtifactsOwn": (
                "TEMPORAL_SEMANTICS_AND_EXECUTION_POSTURES"
            ),
            "runtimeAuthoritiesUnchanged": True,
            "issue192AuthorityUnchanged": True,
        },
        "invariants": list(PROMOTION_INVARIANTS),
        "negativeCases": list(PROMOTION_NEGATIVE_CASES),
        "unsupported": [
            "SCHEMA_PROMOTION",
            "CURRENT_DEFAULT_PROMOTION",
            "RUNTIME_OR_PROFILE_ACTIVATION",
            "RUNTIME_BUNDLE_ROLE_OR_MEMBERSHIP_CHANGE",
            "DATABASE_STORAGE_OR_MIGRATION",
            "PROMOTION_DECISION_STORAGE_OR_SIGNING",
            "TENANT_RUNTIME_BUNDLE_SELECTION",
            "PRODUCTION_TEMPORAL_SELECTOR",
            "GOVERNED_COMMAND_INTEGRATION_OR_AUTHORIZATION",
            "ROUTE_OR_PRODUCTION_SEMANTIC_ACTIVATION",
            "MATERIALIZATION_CURRENT_STATE_HISTORY_WINDOW_OR_OUTPUT",
            "LEGACY_SEMANTIC_OR_OUTPUT_IMPORT",
            "ISSUE_192_BEHAVIOR",
        ],
        "implementationStops": [
            (
                "NO_POSITIVE_PROMOTION_WITHOUT_SEPARATE_"
                "HUMAN_DECISION_AND_CURRENTNESS_TRACE"
            ),
            "NO_SUBJECT_OUTSIDE_EXACT_THREE_IDENTITY_SET",
            "NO_SCHEMA_OR_OTHER_IDENTITY_PROMOTION",
            "NO_SUBJECT_REWRITE_OR_RELOCATION",
            "NO_ACTIVE_RUNTIME_BUNDLE_OR_PROFILE_CHANGE",
            "NO_DATABASE_COMMAND_ROUTE_OUTPUT_LEGACY_OR_ISSUE_192_CHANGE",
        ],
    }


def _assert_promotion_digests() -> None:
    if _sha256(PROMOTION_SCHEMA_PATH) != PROMOTION_SCHEMA_DIGEST:
        raise TemporalCandidateError(
            "temporal promotion schema digest differs"
        )
    if _sha256(PROMOTION_BINDING_PATH) != PROMOTION_BINDING_DIGEST:
        raise TemporalCandidateError(
            "temporal promotion binding digest differs"
        )


def _assert_promotion_rfc_digest() -> None:
    if _sha256(PROMOTION_RFC_PATH) != PROMOTION_RFC_DIGEST:
        raise TemporalCandidateError("temporal promotion RFC digest differs")


def validate_promotion_schema_shape(
    schema: dict[str, object],
    binding: dict[str, object],
) -> None:
    _assert_promotion_digests()
    if (
        set(schema) != {"$schema", "$id", "title", "$comment", "const"}
        or schema.get("$schema")
        != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("$id") != PROMOTION_SCHEMA_ID
        or schema.get("title")
        != "OFARM TemporalGovernancePromotionBinding v0.1 (candidate)"
        or schema.get("const") != binding
    ):
        raise TemporalCandidateError(
            "temporal promotion schema shape differs"
        )
    comment = schema.get("$comment")
    if (
        type(comment) is not str
        or "NEW_CANDIDATE exact schema" not in comment
        or "three exact temporal identities" not in comment
        or "has no promotion" not in comment
        or "issue #192 effect" not in comment
    ):
        raise TemporalCandidateError(
            "temporal promotion schema posture differs"
        )


def validate_promotion_binding(value: object) -> None:
    _assert_promotion_digests()
    expected = _expected_promotion_binding()
    binding = _closed_object(
        value,
        label="TemporalGovernancePromotionBinding",
        allowed=frozenset(expected),
        required=frozenset(expected),
    )
    if {
        field: binding.get(field)
        for field in (
            "schemaVersion",
            "bindingId",
            "status",
            "executionPosture",
            "identityAuthority",
        )
    } != {
        "schemaVersion": PROMOTION_SCHEMA_VERSION,
        "bindingId": PROMOTION_BINDING_ID,
        "status": PROMOTION_STATUS,
        "executionPosture": PROMOTION_EXECUTION_POSTURE,
        "identityAuthority": PROMOTION_IDENTITY_AUTHORITY,
    }:
        raise TemporalCandidateError(
            "temporal promotion identity differs"
        )
    subject_set = binding.get("subjectSet")
    if (
        type(subject_set) is not dict
        or subject_set.get("setSemantics")
        != "EXACT_ATOMIC_PROMOTION_SET_NOT_RUNTIME_COMPONENT_CLOSURE"
        or subject_set.get("dependencyOrder")
        != [CARRIER_MATRIX_ID, SELECTION_BINDING_ID, COMMAND_BINDING_ID]
        or subject_set.get("partialPromotion")
        != "REFUSED_ALL_REMAIN_CANDIDATE_INACTIVE"
        or subject_set.get("subjects") != _expected_promotion_subjects()
    ):
        raise TemporalCandidateError(
            "temporal promotion subject set differs"
        )
    decision = binding.get("decisionContract")
    if (
        type(decision) is not dict
        or decision.get("allowedOutcomes")
        != ["PROMOTE_GOVERNED_INACTIVE", "REFUSE_PROMOTION"]
        or decision.get("humanGoverned") is not True
        or decision.get("contractApprovalIsPromotion") is not False
        or decision.get("mergeIsPromotion") is not False
        or decision.get("conformanceSuccessIsPromotion") is not False
        or decision.get("callerSelectable") is not False
        or decision.get("requiredDecisionEvidenceFields")
        != [
            "promotionDecisionRef",
            "humanPromotionAuthorityRef",
            "decidedAt",
            "reviewEvidenceRefs",
            "currentnessTraceRef",
        ]
    ):
        raise TemporalCandidateError(
            "temporal promotion decision authority differs"
        )
    if (
        tuple(binding.get("invariants", ())) != PROMOTION_INVARIANTS
        or tuple(binding.get("negativeCases", ()))
        != PROMOTION_NEGATIVE_CASES
    ):
        raise TemporalCandidateError(
            "temporal promotion invariants or negative cases differ"
        )
    if binding != expected:
        raise TemporalCandidateError(
            "temporal promotion binding differs"
        )


def validate_promotion_dependency_consistency() -> None:
    selection = _load_json(SELECTION_BINDING_PATH)
    command = _load_json(COMMAND_BINDING_PATH)
    if selection.get("carrierMatrix") != {
        "matrixId": CARRIER_MATRIX_ID,
        "matrixDigest": f"sha256:{_sha256(CARRIER_MATRIX_PATH)}",
        "rowId": SELECTION_ROW_ID,
    }:
        raise TemporalCandidateError(
            "promoted selector no longer binds the exact matrix dependency"
        )
    prerequisites = command.get("prerequisites")
    if type(prerequisites) is not list:
        raise TemporalCandidateError(
            "promoted command prerequisites are malformed"
        )
    selector_prerequisites = [
        item
        for item in prerequisites
        if type(item) is dict
        and item.get("role") == "INTERVENTION_VALID_TIME_SELECTION"
    ]
    if selector_prerequisites != [
        {
            "role": "INTERVENTION_VALID_TIME_SELECTION",
            "identity": SELECTION_BINDING_ID,
            "digest": f"sha256:{_sha256(SELECTION_BINDING_PATH)}",
        }
    ]:
        raise TemporalCandidateError(
            "promoted command no longer binds the exact selector dependency"
        )


def validate_runtime_selection_binding() -> None:
    package_root = str(PACKAGE_ROOT)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    from kernel import temporal_carriers

    identity = temporal_carriers.INTERVENTION_BINDING
    expected_identity = {
        "binding_schema_version": SELECTION_SCHEMA_VERSION,
        "binding_id": SELECTION_BINDING_ID,
        "binding_artifact_digest": (
            f"sha256:{_sha256(SELECTION_BINDING_PATH)}"
        ),
        "coordinate_schema_version": CONTRACT_VERSION,
        "coordinate_schema_digest": (
            f"sha256:{_sha256(COORDINATE_SCHEMA_PATH)}"
        ),
        "carrier_matrix_id": CARRIER_MATRIX_ID,
        "carrier_matrix_digest": f"sha256:{_sha256(CARRIER_MATRIX_PATH)}",
        "carrier_matrix_row_id": SELECTION_ROW_ID,
        "envelope_schema_version": ENVELOPE_SCHEMA_VERSION,
        "envelope_schema_digest": f"sha256:{_sha256(ENVELOPE_SCHEMA_PATH)}",
        "execution_schema_version": EXECUTION_SCHEMA_VERSION,
        "execution_schema_digest": f"sha256:{_sha256(EXECUTION_SCHEMA_PATH)}",
    }
    observed_identity = {
        field: getattr(identity, field) for field in expected_identity
    }
    if observed_identity != expected_identity:
        raise TemporalCandidateError(
            "runtime carrier-selection identity differs from its artifact"
        )
    binding = _expected_selection_binding()
    source_contracts = binding["sourceContracts"]
    selectors = binding["selectors"]
    expected_constants = {
        "ENVELOPE_EVENT_FAMILY": source_contracts[0]["discriminatorValue"],
        "EXECUTION_RECORD_CLASS": source_contracts[1]["discriminatorValue"],
        "EXECUTION_TIME_BASIS": selectors[1]["requiredTimeBasis"],
        "EVENT_OCCURRENCE": selectors[0]["windowMeaning"],
        "STATE_OVERLAP": selectors[1]["windowMeaning"],
    }
    observed_constants = {
        field: getattr(temporal_carriers, field)
        for field in expected_constants
    }
    if observed_constants != expected_constants:
        raise TemporalCandidateError(
            "runtime carrier-selection values differ from its artifact"
        )
    if hasattr(temporal_carriers, "CarrierBindingIdentity"):
        raise TemporalCandidateError(
            "runtime carrier-selection identity is publicly constructible"
        )
    try:
        type(identity)(binding_id="caller-selected")
    except TypeError:
        pass
    else:
        raise TemporalCandidateError(
            "runtime carrier-selection authority accepts caller values"
        )


def validate_runtime_selector_paths(binding: dict[str, object]) -> None:
    # validate_selection_binding runs first and fixes this complete shape.
    source_contracts = binding["sourceContracts"]
    selectors = binding["selectors"]
    unsupported = binding["unsupportedEnvelopeFields"]
    envelope_contract, execution_contract = source_contracts
    occurrence_selector, interval_selector = selectors

    def leaf(path: str) -> str:
        return path.rsplit("/", 1)[1]

    expected_gets = [
        ("envelope_object", "schemaVersion"),
        ("envelope_object", leaf(envelope_contract["discriminatorPath"])),
        ("payload_object", "schemaVersion"),
        ("payload_object", leaf(execution_contract["discriminatorPath"])),
        ("envelope_object", "timeSemantics"),
        ("time_semantics", leaf(occurrence_selector["valuePath"])),
        ("payload_object", "effectiveTimeInterval"),
        ("interval", leaf(interval_selector["timeBasisPath"])),
        ("interval", leaf(interval_selector["startPath"])),
        ("interval", leaf(interval_selector["endPath"])),
    ]
    expected_memberships = [
        ("time_semantics", leaf(path)) for path in unsupported
    ]

    try:
        module = ast.parse(
            TEMPORAL_SELECTOR_MODULE_PATH.read_text(encoding="utf-8"),
            filename=str(TEMPORAL_SELECTOR_MODULE_PATH),
        )
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise TemporalCandidateError(
            "carrier-selection implementation is not parseable"
        ) from exc
    functions = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "select_intervention_valid_time"
    ]
    if len(functions) != 1:
        raise TemporalCandidateError(
            "carrier-selection implementation entry point differs"
        )

    observed_gets: list[tuple[str, str]] = []
    observed_memberships: list[tuple[str, str]] = []
    for node in ast.walk(functions[0]):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and len(node.args) == 1
            and not node.keywords
            and isinstance(node.args[0], ast.Constant)
            and type(node.args[0].value) is str
        ):
            observed_gets.append(
                (node.func.value.id, node.args[0].value)
            )
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.In)
            and len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Name)
            and isinstance(node.left, ast.Constant)
            and type(node.left.value) is str
        ):
            observed_memberships.append(
                (node.comparators[0].id, node.left.value)
            )

    if (
        sorted(observed_gets) != sorted(expected_gets)
        or sorted(observed_memberships) != sorted(expected_memberships)
    ):
        raise TemporalCandidateError(
            "runtime selector field lookups differ from its binding artifact"
        )


def _authenticate_authority(
    relative_path: str,
    byte_length: int,
    sha256: str,
    contract_identity: str | None,
    *,
    authority_label: str = "selection-storage",
) -> bytes:
    path = PACKAGE_ROOT / relative_path
    if path.is_symlink() or not path.is_file():
        raise TemporalCandidateError(
            f"{authority_label} authority is missing: {relative_path}"
        )
    try:
        authority_bytes = path.read_bytes()
    except OSError as exc:
        raise TemporalCandidateError(
            f"{authority_label} authority is unreadable: {relative_path}"
        ) from exc
    if len(authority_bytes) != byte_length:
        raise TemporalCandidateError(
            f"{authority_label} authority byte length differs: {relative_path}"
        )
    if "sha256:" + hashlib.sha256(authority_bytes).hexdigest() != sha256:
        raise TemporalCandidateError(
            f"{authority_label} authority digest differs: {relative_path}"
        )
    if (
        contract_identity is not None
        and contract_identity.encode("utf-8") not in authority_bytes
    ):
        raise TemporalCandidateError(
            f"{authority_label} contract identity differs: {relative_path}"
        )
    return authority_bytes


def validate_temporal_runtime_bundle_publication_authorities() -> None:
    for authority in (
        (
            TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_SELF_RELATIVE_PATH,
            TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_SELF_BYTE_LENGTH,
            TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_SELF_SHA256,
            TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_SELF_CONTRACT_IDENTITY,
        ),
        (
            TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_PARENT_RELATIVE_PATH,
            TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_PARENT_BYTE_LENGTH,
            TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_PARENT_SHA256,
            TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_PARENT_CONTRACT_IDENTITY,
        ),
    ):
        _authenticate_authority(
            *authority,
            authority_label="temporal-runtime-bundle-publication",
        )


def validate_global_content_retention_authorities() -> None:
    for authority in (
        (
            GLOBAL_CONTENT_RETENTION_SELF_RELATIVE_PATH,
            GLOBAL_CONTENT_RETENTION_SELF_BYTE_LENGTH,
            GLOBAL_CONTENT_RETENTION_SELF_SHA256,
            GLOBAL_CONTENT_RETENTION_SELF_CONTRACT_IDENTITY,
        ),
        (
            GLOBAL_CONTENT_RETENTION_PARENT_RELATIVE_PATH,
            GLOBAL_CONTENT_RETENTION_PARENT_BYTE_LENGTH,
            GLOBAL_CONTENT_RETENTION_PARENT_SHA256,
            GLOBAL_CONTENT_RETENTION_PARENT_CONTRACT_IDENTITY,
        ),
    ):
        _authenticate_authority(
            *authority,
            authority_label="global-content-retention",
        )


def validate_selection_storage_authorities() -> None:
    _authenticate_authority(
        SELECTION_STORAGE_AMENDMENT_RELATIVE_PATH,
        SELECTION_STORAGE_AMENDMENT_BYTE_LENGTH,
        SELECTION_STORAGE_AMENDMENT_SHA256,
        SELECTION_STORAGE_AMENDMENT_CONTRACT_IDENTITY,
    )
    v0_1_bytes = _authenticate_authority(
        *SELECTION_STORAGE_REQUIRED_AUTHORITIES[0]
    )
    if SELECTION_STORAGE_PROVISIONING_DIGEST.encode("utf-8") not in v0_1_bytes:
        raise TemporalCandidateError(
            "selection-storage provisioning contract value differs"
        )
    for authority in SELECTION_STORAGE_REQUIRED_AUTHORITIES[1:]:
        _authenticate_authority(*authority)


def _build_selection_storage_snapshot() -> architecture.PythonSourceSnapshotV1:
    try:
        snapshot = architecture.build_python_source_snapshot(PACKAGE_ROOT)
    except architecture.PythonSourceSnapshotRefusal as exc:
        raise TemporalCandidateError(
            f"public Python source snapshot refused: {exc.code.value}"
        ) from exc
    if type(snapshot) is not architecture.PythonSourceSnapshotV1:
        raise TemporalCandidateError("public Python source snapshot type differs")
    expected_authority = architecture.PythonSourceContractAuthorityV1(
        contract_identity=PYTHON_SNAPSHOT_CONTRACT_IDENTITY,
        rfc_relative_path=PYTHON_SNAPSHOT_RFC_RELATIVE_PATH,
        byte_length=PYTHON_SNAPSHOT_RFC_BYTE_LENGTH,
        sha256=PYTHON_SNAPSHOT_RFC_SHA256,
    )
    if snapshot.contract_authority != expected_authority:
        raise TemporalCandidateError(
            "public Python source snapshot authority differs"
        )
    descriptor = snapshot.descriptor
    if (
        descriptor.interface_identity != PYTHON_SNAPSHOT_INTERFACE_IDENTITY
        or descriptor.production_import_roots
        != ("kernel.api", "kernel.application_runtime")
        or descriptor.legacy_import_roots
        != ("kernel.legacy_m1.api", "kernel.legacy_m1.runtime")
    ):
        raise TemporalCandidateError(
            "public Python source snapshot descriptor differs"
        )
    return snapshot


def _validate_reachability_map(
    reachability: object,
    roots: tuple[str, ...],
    label: str,
) -> None:
    if not hasattr(reachability, "items"):
        raise TemporalCandidateError(f"{label} reachability map differs")
    for root in roots:
        if reachability.get(root) != (root,):
            raise TemporalCandidateError(
                f"{label} reachability root entry differs"
            )
    for module_name, path in reachability.items():
        if (
            type(module_name) is not str
            or type(path) is not tuple
            or not path
            or path[0] not in roots
            or path[-1] != module_name
            or any(type(part) is not str for part in path)
        ):
            raise TemporalCandidateError(
                f"{label} reachability path structure differs"
            )


def _validate_source_pin(
    snapshot: architecture.PythonSourceSnapshotV1,
    pin: tuple[str, str, int, str],
) -> None:
    relative_path, module_name, byte_length, sha256 = pin
    unit = snapshot.modules_by_relative_path.get(relative_path)
    if (
        unit is None
        or unit.relative_path != relative_path
        or unit.module_name != module_name
        or unit.byte_length != byte_length
        or len(unit.source_bytes) != byte_length
        or unit.sha256 != sha256
        or "sha256:" + hashlib.sha256(unit.source_bytes).hexdigest() != sha256
    ):
        raise TemporalCandidateError(
            f"selection-storage Python source pin differs: {relative_path}"
        )


def _validate_tenant_service(migration_set: _AuthenticatedMigrationSet) -> None:
    service = migration_set.service
    if (
        getattr(service, "identity", None) != "ofarm.tenant-postgresql.v1"
        or getattr(service, "relative_directory", None) != "kernel/migrations"
        or getattr(service, "schema_name", None) != "ofarm"
        or getattr(service, "ledger_name", None) != "schema_migration"
        or getattr(service, "qualified_ledger", None) != "ofarm.schema_migration"
    ):
        raise TemporalCandidateError(
            "authenticated tenant migration service differs"
        )


def _validate_selection_storage_migration_prefix(
    authority: TenantMigrationAuthoritySnapshot,
) -> None:
    migration_set = authority.migration_set
    migrations = migration_set.migrations
    if len(migrations) not in (7, 8, 9, 10):
        raise TemporalCandidateError(
            "selection-storage migration state is not exact V7, V8, V9, or V10"
        )
    if tuple(migration.version for migration in migrations) != tuple(
        range(1, len(migrations) + 1)
    ):
        raise TemporalCandidateError(
            "selection-storage migration versions are not contiguous"
        )
    for migration in migrations:
        observed_digest = "sha256:" + hashlib.sha256(
            migration.source_bytes
        ).hexdigest()
        if (
            len(migration.source_bytes) != migration.byte_length
            or migration.source_sha256 != observed_digest
        ):
            raise TemporalCandidateError(
                f"authenticated migration bytes differ: {migration.filename}"
            )
    for version, expected in SELECTION_STORAGE_V7_MIGRATION_PINS.items():
        migration = migrations[version - 1]
        if (
            migration.filename,
            migration.byte_length,
            migration.source_sha256,
        ) != expected:
            raise TemporalCandidateError(
                f"selection-storage migration {version:04d} differs"
            )
    try:
        prefix_3 = migration_set.prefix_digest(3)
        prefix_7 = migration_set.prefix_digest(7)
    except Exception as exc:
        raise TemporalCandidateError(
            "selection-storage migration prefix authentication failed"
        ) from exc
    if (
        authority.version_3_prefix != SELECTION_STORAGE_V3_PREFIX_DIGEST
        or prefix_3 != SELECTION_STORAGE_V3_PREFIX_DIGEST
        or prefix_7 != SELECTION_STORAGE_V7_DIGEST
    ):
        raise TemporalCandidateError(
            "selection-storage stable migration prefix differs"
        )
    _validate_tenant_service(migration_set)


def _is_python_marker_exemption(relative_path: str) -> bool:
    return relative_path == (
        "conformance/temporal_contract_candidate_check.py"
    ) or relative_path.startswith("kernel/tests/")


def _classify_selection_storage_pair(
    authority: TenantMigrationAuthoritySnapshot,
    snapshot: architecture.PythonSourceSnapshotV1,
) -> str:
    migrations = authority.migration_set.migrations
    adapter_unit = snapshot.modules_by_relative_path.get(
        SELECTION_STORAGE_ADAPTER_RELATIVE_PATH
    )
    has_migration = len(migrations) >= 8
    has_adapter = adapter_unit is not None
    if has_migration:
        migration_8 = migrations[7]
        if migration_8.filename != SELECTION_STORAGE_MIGRATION_FILENAME:
            raise TemporalCandidateError(
                "selection-storage version 0008 filename differs"
            )
    if has_migration != has_adapter:
        raise TemporalCandidateError(
            "selection-storage implementation pair is incomplete"
        )
    marker_bytes = tuple(
        marker.encode("utf-8") for marker in SELECTION_STORAGE_MARKERS
    )
    for migration in migrations:
        occurrences = tuple(
            marker in migration.source_bytes for marker in marker_bytes
        )
        is_v8 = (
            migration.version == 8
            and migration.filename == SELECTION_STORAGE_MIGRATION_FILENAME
        )
        is_v10 = (
            migration.version == 10
            and migration.filename
            == TRUSTED_COMMAND_SELECTOR_MIGRATION_FILENAME
        )
        if any(occurrences) and not (is_v8 or is_v10):
            raise TemporalCandidateError(
                "selection-storage marker entered another authenticated migration"
            )
        if is_v8 and not all(occurrences):
            raise TemporalCandidateError(
                "selection-storage migration marker pair differs"
            )

    for relative_path, unit in snapshot.modules_by_relative_path.items():
        occurrences = tuple(
            marker in unit.source_text for marker in SELECTION_STORAGE_MARKERS
        )
        if relative_path == SELECTION_STORAGE_ADAPTER_RELATIVE_PATH:
            if not all(occurrences):
                raise TemporalCandidateError(
                    "selection-storage adapter marker pair differs"
                )
        elif relative_path in (
            TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH
            , TRUSTED_COMMAND_SELECTOR_RELATIVE_PATH
        ):
            # The subordinate publication classifier owns this exact path and
            # requires the complete six-marker conjunction later in the same
            # checker invocation.
            pass
        elif any(occurrences) and not _is_python_marker_exemption(relative_path):
            raise TemporalCandidateError(
                "selection-storage marker entered another production Python source"
            )

    if has_adapter:
        if adapter_unit.module_name != SELECTION_STORAGE_ADAPTER_MODULE:
            raise TemporalCandidateError(
                "selection-storage adapter module identity differs"
            )
        return SELECTION_STORAGE_CONFORMANT_CLASSIFIED
    return SELECTION_STORAGE_CONFORMANT_ABSENT


def _classify_global_content_retention_migration(
    authority: TenantMigrationAuthoritySnapshot,
    version_8_prefix: str,
) -> str:
    migrations = authority.migration_set.migrations
    if len(migrations) not in (8, 9, 10):
        raise TemporalCandidateError(
            "global-content-retention migration state is not exact V8, V9, or V10"
        )
    if version_8_prefix != GLOBAL_CONTENT_RETENTION_V8_PREFIX_DIGEST:
        raise TemporalCandidateError(
            "global-content-retention version-8 prefix differs"
        )

    required_markers = tuple(
        marker.encode("utf-8") for marker in _GCRC_REQUIRED_MARKERS
    )
    if any(
        marker in migration.source_bytes
        for migration in migrations[:8]
        for marker in required_markers
    ):
        raise TemporalCandidateError(
            "global-content-retention marker entered an earlier migration"
        )
    if len(migrations) == 8:
        return GLOBAL_CONTENT_RETENTION_MIGRATION_ABSENT

    migration_9 = migrations[8]
    if (
        migration_9.version != 9
        or migration_9.filename != GLOBAL_CONTENT_RETENTION_MIGRATION_FILENAME
    ):
        raise TemporalCandidateError(
            "global-content-retention version 0009 identity differs"
        )
    if not all(marker in migration_9.source_bytes for marker in required_markers):
        raise TemporalCandidateError(
            "global-content-retention required marker pair differs"
        )
    if any(
        marker.encode("utf-8") in migration_9.source_bytes
        for marker in _GCRC_FORBIDDEN_MIGRATION_MARKERS
    ):
        raise TemporalCandidateError(
            "global-content-retention migration contains a forbidden marker"
        )

    try:
        prefix_9 = authority.migration_set.prefix_digest(9)
        complete_prefix = authority.migration_set.prefix_digest(len(migrations))
    except Exception as exc:
        raise TemporalCandidateError(
            "global-content-retention version-9 prefix authentication failed"
        ) from exc
    if (
        type(prefix_9) is not str
        or type(complete_prefix) is not str
        or prefix_9 == version_8_prefix
    ):
        raise TemporalCandidateError(
            "global-content-retention version-9 migration-set identity differs"
        )
    if len(migrations) == 9 and (
        complete_prefix != prefix_9
        or authority.migration_set.digest != prefix_9
    ):
        raise TemporalCandidateError(
            "global-content-retention version-9 migration-set identity differs"
        )
    if len(migrations) == 10 and (
        prefix_9 != TRUSTED_COMMAND_SELECTOR_V9_PREFIX_DIGEST
        or complete_prefix != authority.migration_set.digest
    ):
        raise TemporalCandidateError(
            "global-content-retention version-9 migration-set identity differs"
        )
    return GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED


def _top_level_literal(tree: ast.Module, name: str) -> object:
    assignments = [
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Name) and target.id == name
            for target in (
                node.targets if isinstance(node, ast.Assign) else (node.target,)
            )
        )
    ]
    if len(assignments) != 1:
        raise TemporalCandidateError(
            f"trusted command selector literal {name} differs"
        )
    try:
        return ast.literal_eval(assignments[0].value)
    except (TypeError, ValueError) as exc:
        raise TemporalCandidateError(
            f"trusted command selector literal {name} differs"
        ) from exc


def _validate_trusted_selector_module(
    snapshot: architecture.PythonSourceSnapshotV1,
) -> None:
    selector = snapshot.modules_by_relative_path.get(
        TRUSTED_COMMAND_SELECTOR_RELATIVE_PATH
    )
    control_adapter = snapshot.modules_by_relative_path.get(
        SELECTION_STORAGE_ADAPTER_RELATIVE_PATH
    )
    if (
        selector is None
        or selector.module_name != TRUSTED_COMMAND_SELECTOR_MODULE
        or control_adapter is None
        or control_adapter.module_name != SELECTION_STORAGE_ADAPTER_MODULE
    ):
        raise TemporalCandidateError(
            "trusted command selector source pair differs"
        )
    try:
        selector_tree = snapshot.ast_for(TRUSTED_COMMAND_SELECTOR_MODULE)
        control_tree = snapshot.ast_for(SELECTION_STORAGE_ADAPTER_MODULE)
    except (KeyError, architecture.PythonSourceSnapshotRefusal) as exc:
        raise TemporalCandidateError(
            "trusted command selector AST custody failed"
        ) from exc
    for name, expected in TRUSTED_COMMAND_SELECTOR_PIN_LITERALS.items():
        if (
            _top_level_literal(selector_tree, name) != expected
            or _top_level_literal(control_tree, name) != expected
        ):
            raise TemporalCandidateError(
                f"trusted command selector pin parity differs: {name}"
            )
    if _top_level_literal(selector_tree, "__all__") != (
        "CommandRuntimeBundleSelectionRefused",
        "TrustedCommandRuntimeBundle",
    ):
        raise TemporalCandidateError(
            "trusted command selector export surface differs"
        )
    resolvers = [
        node
        for node in selector_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        == "_resolve_commit_operation_claim_draft_runtime_bundle"
    ]
    if len(resolvers) != 1:
        raise TemporalCandidateError(
            "trusted command selector resolver count differs"
        )
    arguments = resolvers[0].args
    if (
        tuple(argument.arg for argument in arguments.args)
        != ("connection", "tenant_id")
        or arguments.posonlyargs
        or arguments.kwonlyargs
        or arguments.vararg is not None
        or arguments.kwarg is not None
        or arguments.defaults
    ):
        raise TemporalCandidateError(
            "trusted command selector resolver signature differs"
        )
    imports = {
        edge.target
        for edge in snapshot.import_graph[TRUSTED_COMMAND_SELECTOR_MODULE]
    }
    if imports != {"kernel.runtime_bundle"}:
        raise TemporalCandidateError(
            "trusted command selector import boundary differs"
        )
    uow_imports = {
        edge.target for edge in snapshot.import_graph["kernel.tenant_uow"]
    }
    if TRUSTED_COMMAND_SELECTOR_MODULE not in uow_imports:
        raise TemporalCandidateError(
            "tenant UnitOfWork does not import the fixed selector"
        )
    path = snapshot.production_reachability.get(
        TRUSTED_COMMAND_SELECTOR_MODULE
    )
    if (
        type(path) is not tuple
        or path[-3:]
        != (
            "kernel.application_runtime",
            "kernel.tenant_uow",
            TRUSTED_COMMAND_SELECTOR_MODULE,
        )
    ):
        raise TemporalCandidateError(
            "trusted command selector production path differs"
        )
    if TRUSTED_COMMAND_SELECTOR_MODULE in snapshot.legacy_reachability:
        raise TemporalCandidateError(
            "trusted command selector entered the legacy import closure"
        )
    function_marker = TRUSTED_COMMAND_SELECTOR_FIXED_FUNCTION + "()"
    owners = [
        unit.relative_path
        for unit in snapshot.modules_by_relative_path.values()
        if function_marker in unit.source_text
        and not _is_python_marker_exemption(unit.relative_path)
    ]
    if owners != [TRUSTED_COMMAND_SELECTOR_RELATIVE_PATH]:
        raise TemporalCandidateError(
            "trusted command selector function marker ownership differs"
        )


def _classify_trusted_command_selector(
    authority: TenantMigrationAuthoritySnapshot,
    snapshot: architecture.PythonSourceSnapshotV1,
    selection_state: str,
    retention_state: str | None,
) -> str:
    migrations = authority.migration_set.migrations
    has_migration = len(migrations) == 10
    has_module = (
        TRUSTED_COMMAND_SELECTOR_RELATIVE_PATH
        in snapshot.modules_by_relative_path
    )
    if has_migration != has_module:
        raise TemporalCandidateError(
            "trusted command selector implementation pair is incomplete"
        )
    if not has_migration:
        return TRUSTED_COMMAND_SELECTOR_MIGRATION_ABSENT
    if (
        selection_state != SELECTION_STORAGE_CONFORMANT_CLASSIFIED
        or retention_state != GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED
    ):
        raise TemporalCandidateError(
            "trusted command selector foundation state differs"
        )
    migration = migrations[9]
    if (
        migration.version != 10
        or migration.filename != TRUSTED_COMMAND_SELECTOR_MIGRATION_FILENAME
        or migration.byte_length != TRUSTED_COMMAND_SELECTOR_MIGRATION_BYTES
        or migration.source_sha256
        != TRUSTED_COMMAND_SELECTOR_MIGRATION_SHA256
        or TRUSTED_COMMAND_SELECTOR_FIXED_FUNCTION.encode("utf-8")
        not in migration.source_bytes
    ):
        raise TemporalCandidateError(
            "trusted command selector version-10 migration differs"
        )
    try:
        prefix_9 = authority.migration_set.prefix_digest(9)
        prefix_10 = authority.migration_set.prefix_digest(10)
    except Exception as exc:
        raise TemporalCandidateError(
            "trusted command selector migration authentication failed"
        ) from exc
    if (
        prefix_9 != TRUSTED_COMMAND_SELECTOR_V9_PREFIX_DIGEST
        or prefix_10 != TRUSTED_COMMAND_SELECTOR_V10_DIGEST
        or authority.migration_set.digest != prefix_10
    ):
        raise TemporalCandidateError(
            "trusted command selector migration-set identity differs"
        )
    catalog = snapshot.modules_by_relative_path.get(
        "deployment/postgresql/catalog_identity.py"
    )
    if (
        catalog is None
        or TRUSTED_COMMAND_SELECTOR_CATALOG_DIGEST
        not in catalog.source_text
    ):
        raise TemporalCandidateError(
            "trusted command selector catalog identity differs"
        )
    _validate_trusted_selector_module(snapshot)
    return TRUSTED_COMMAND_SELECTOR_MIGRATION_CLASSIFIED


def _classify_temporal_runtime_bundle_publication_adapter(
    snapshot: architecture.PythonSourceSnapshotV1,
    selection_state: str,
    retention_state: str | None,
) -> str:
    if selection_state not in (
        SELECTION_STORAGE_CONFORMANT_ABSENT,
        SELECTION_STORAGE_CONFORMANT_CLASSIFIED,
    ):
        raise TemporalCandidateError(
            "temporal RuntimeBundle publication selection state differs"
        )
    if retention_state not in (
        None,
        GLOBAL_CONTENT_RETENTION_MIGRATION_ABSENT,
        GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED,
    ):
        raise TemporalCandidateError(
            "temporal RuntimeBundle publication retention state differs"
        )

    try:
        source_units = tuple(snapshot.modules_by_relative_path.items())
    except (AttributeError, TypeError) as exc:
        raise TemporalCandidateError(
            "temporal RuntimeBundle publication source inventory differs"
        ) from exc

    target_present = False
    selection_ownership = (True, True, False, False, False, False)
    lifecycle_ownership = (False, False, True, False, False, False)
    enforcement_ownership = (True, True, True, True, True, True)
    decision_log_owner_present = False
    temporal_checker_owner_present = False
    for relative_path, unit in source_units:
        try:
            unit_relative_path = unit.relative_path
            unit_module_name = unit.module_name
            source_text = unit.source_text
        except AttributeError as exc:
            raise TemporalCandidateError(
                "temporal RuntimeBundle publication source unit differs"
            ) from exc
        if (
            type(relative_path) is not str
            or unit_relative_path != relative_path
            or type(unit_module_name) is not str
            or type(source_text) is not str
        ):
            raise TemporalCandidateError(
                "temporal RuntimeBundle publication source unit differs"
            )
        occurrences = tuple(
            marker in source_text
            for marker in PUBLICATION_ADAPTER_REQUIRED_MARKERS
        )
        if relative_path == (
            TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH
        ):
            target_present = True
            if unit_module_name != (
                TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_MODULE
            ):
                raise TemporalCandidateError(
                    "temporal RuntimeBundle publication adapter module differs"
                )
            if occurrences != enforcement_ownership:
                raise TemporalCandidateError(
                    "temporal RuntimeBundle publication marker conjunction differs"
                )
            try:
                publication_edges = snapshot.import_graph[unit_module_name]
            except (AttributeError, KeyError, TypeError) as exc:
                raise TemporalCandidateError(
                    "temporal RuntimeBundle publication import evidence differs"
                ) from exc
            if any(
                architecture._is_legacy_module(edge.target)
                for edge in publication_edges
            ):
                raise TemporalCandidateError(
                    "temporal RuntimeBundle publication adapter imports "
                    "legacy authority"
                )
        elif relative_path == SELECTION_STORAGE_ADAPTER_RELATIVE_PATH:
            if occurrences != selection_ownership:
                raise TemporalCandidateError(
                    "selection adapter publication-marker ownership differs"
                )
        elif relative_path == TRUSTED_COMMAND_SELECTOR_RELATIVE_PATH:
            if occurrences != selection_ownership:
                raise TemporalCandidateError(
                    "trusted selector publication-marker ownership differs"
                )
        elif relative_path == TEMPORAL_DECISION_LOG_CHECK_RELATIVE_PATH:
            decision_log_owner_present = True
            if occurrences != lifecycle_ownership:
                raise TemporalCandidateError(
                    "decision-log checker publication-marker ownership differs"
                )
        elif relative_path == TEMPORAL_CANDIDATE_CHECK_RELATIVE_PATH:
            temporal_checker_owner_present = True
            if occurrences != enforcement_ownership:
                raise TemporalCandidateError(
                    "temporal checker publication-marker ownership differs"
                )
        elif relative_path.startswith("kernel/tests/"):
            continue
        elif any(occurrences):
            raise TemporalCandidateError(
                "publication marker entered an unapproved Python source"
            )

    if not decision_log_owner_present or not temporal_checker_owner_present:
        raise TemporalCandidateError(
            "temporal RuntimeBundle publication marker-owner evidence is missing"
        )

    if target_present:
        if (
            selection_state == SELECTION_STORAGE_CONFORMANT_CLASSIFIED
            and retention_state
            == GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED
        ):
            return TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_CLASSIFIED
        raise TemporalCandidateError(
            "temporal RuntimeBundle publication foundation state differs"
        )
    if (
        selection_state == SELECTION_STORAGE_CONFORMANT_ABSENT
        and retention_state is None
    ) or (
        selection_state == SELECTION_STORAGE_CONFORMANT_CLASSIFIED
        and retention_state
        in (
            GLOBAL_CONTENT_RETENTION_MIGRATION_ABSENT,
            GLOBAL_CONTENT_RETENTION_MIGRATION_CLASSIFIED,
        )
    ):
        return TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_ABSENT
    raise TemporalCandidateError(
        "temporal RuntimeBundle publication foundation state differs"
    )


def _validate_global_content_retention_python_isolation(
    snapshot: architecture.PythonSourceSnapshotV1,
) -> None:
    for relative_path, unit in snapshot.modules_by_relative_path.items():
        if (
            any(marker in unit.source_text for marker in _GCRC_REQUIRED_MARKERS)
            and not _is_python_marker_exemption(relative_path)
            and relative_path
            != TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH
        ):
            raise TemporalCandidateError(
                "global-content-retention marker entered production Python source"
            )


def _validate_initializer_import_prohibition(
    snapshot: architecture.PythonSourceSnapshotV1,
    selection_state: str,
    publication_state: str,
) -> None:
    initializer = snapshot.modules_by_relative_path.get(
        POSTGRESQL_INITIALIZER_RELATIVE_PATH
    )
    if (
        initializer is None
        or initializer.module_name != POSTGRESQL_INITIALIZER_MODULE
        or POSTGRESQL_INITIALIZER_MODULE not in snapshot.import_graph
    ):
        raise TemporalCandidateError(
            "PostgreSQL initializer snapshot evidence differs"
        )
    try:
        initializer_tree = snapshot.ast_for(POSTGRESQL_INITIALIZER_MODULE)
    except (KeyError, architecture.PythonSourceSnapshotRefusal) as exc:
        raise TemporalCandidateError(
            "PostgreSQL initializer AST custody failed"
        ) from exc
    if type(initializer_tree) is not ast.Module:
        raise TemporalCandidateError("PostgreSQL initializer AST type differs")

    package_parts = ["deployment", "postgresql"]
    for node in ast.walk(initializer_tree):
        candidates: list[str] = []
        if isinstance(node, ast.Import):
            candidates.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                keep = len(package_parts) - node.level + 1
                base_parts = [] if keep < 0 else package_parts[:keep]
                if node.module:
                    base_parts.extend(node.module.split("."))
                base = ".".join(base_parts)
            if base:
                candidates.append(base)
            candidates.extend(
                ".".join(part for part in (base, alias.name) if part)
                for alias in node.names
            )
        if any(
            module_name in candidates
            for module_name in (
                SELECTION_STORAGE_ADAPTER_MODULE,
                TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_MODULE,
            )
        ):
            raise TemporalCandidateError(
                "PostgreSQL initializer imports an isolated temporal adapter"
            )

    if selection_state == SELECTION_STORAGE_CONFORMANT_CLASSIFIED and any(
        edge.target == SELECTION_STORAGE_ADAPTER_MODULE
        for edge in snapshot.import_graph[POSTGRESQL_INITIALIZER_MODULE]
    ):
        raise TemporalCandidateError(
            "PostgreSQL initializer graph reaches the selection-storage adapter"
        )
    if (
        publication_state
        == TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_CLASSIFIED
        and any(
            edge.target
            == TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_MODULE
            for edge in snapshot.import_graph[POSTGRESQL_INITIALIZER_MODULE]
        )
    ):
        raise TemporalCandidateError(
            "PostgreSQL initializer graph reaches the publication adapter"
        )


def _validate_selection_storage_isolation(
    snapshot: architecture.PythonSourceSnapshotV1,
    selection_state: str,
    publication_state: str,
    selector_state: str,
) -> None:
    # The supported invocation reaches this helper only after
    # _build_selection_storage_snapshot authenticated these descriptor roots.
    for reachability, roots, label in (
        (
            snapshot.production_reachability,
            snapshot.descriptor.production_import_roots,
            "production",
        ),
        (
            snapshot.legacy_reachability,
            snapshot.descriptor.legacy_import_roots,
            "legacy",
        ),
    ):
        _validate_reachability_map(reachability, roots, label)
        if SELECTION_STORAGE_ADAPTER_MODULE in reachability:
            raise TemporalCandidateError(
                f"selection-storage adapter entered the {label} import closure"
            )
        if (
            TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_MODULE
            in reachability
        ):
            raise TemporalCandidateError(
                f"publication adapter entered the {label} import closure"
            )
        selector_reachable = TRUSTED_COMMAND_SELECTOR_MODULE in reachability
        if label == "legacy" and selector_reachable:
            raise TemporalCandidateError(
                "trusted command selector entered the legacy import closure"
            )
        if (
            label == "production"
            and selector_reachable
            != (
                selector_state
                == TRUSTED_COMMAND_SELECTOR_MIGRATION_CLASSIFIED
            )
        ):
            raise TemporalCandidateError(
                "trusted command selector production reachability differs"
            )
        for unit in snapshot.modules_by_relative_path.values():
            if (
                _is_python_marker_exemption(unit.relative_path)
                and unit.module_name in reachability
            ):
                raise TemporalCandidateError(
                    f"temporal verification source entered the {label} import closure"
                )
    _validate_initializer_import_prohibition(
        snapshot,
        selection_state,
        publication_state,
    )


def _validate_selection_storage_active_authorities() -> None:
    markers = (
        *SELECTION_STORAGE_MARKERS,
        *SELECTION_STORAGE_ALLOWED_PRODUCTION_PATHS,
        *_GCRC_REQUIRED_MARKERS,
        *PUBLICATION_ADAPTER_REQUIRED_MARKERS,
        TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_RELATIVE_PATH,
        TEMPORAL_RUNTIME_BUNDLE_PUBLICATION_ADAPTER_MODULE,
        TRUSTED_COMMAND_SELECTOR_FIXED_FUNCTION,
        TRUSTED_COMMAND_SELECTOR_RELATIVE_PATH,
        TRUSTED_COMMAND_SELECTOR_MODULE,
    )
    for path in SELECTION_STORAGE_ACTIVE_NON_PYTHON_PATHS:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise TemporalCandidateError(
                f"active selection-storage authority is unreadable: {path.name}"
            ) from exc
        if any(marker in source for marker in markers):
            raise TemporalCandidateError(
                f"selection-storage authority entered active path: {path.name}"
            )


def _validate_selection_storage_conformance(
    authority: TenantMigrationAuthoritySnapshot,
    snapshot: architecture.PythonSourceSnapshotV1,
) -> str:
    _validate_selection_storage_migration_prefix(authority)
    state = _classify_selection_storage_pair(authority, snapshot)
    retention_state: str | None = None
    for pin in SELECTION_STORAGE_SOURCE_PINS:
        _validate_source_pin(snapshot, pin)
    migration_7 = authority.migration_set.migrations[6]
    if state == SELECTION_STORAGE_CONFORMANT_ABSENT:
        if (
            authority.migration_set.digest != SELECTION_STORAGE_V7_DIGEST
            or SELECTION_STORAGE_V7_STRUCTURAL_DIGEST.encode("utf-8")
            not in migration_7.source_bytes
        ):
            raise TemporalCandidateError(
                "selection-storage exact V7 absent authority differs"
            )
        _validate_source_pin(snapshot, SELECTION_STORAGE_ABSENT_CATALOG_PIN)
        catalog_unit = snapshot.modules_by_relative_path[
            SELECTION_STORAGE_ABSENT_CATALOG_PIN[0]
        ]
        if SELECTION_STORAGE_V7_CATALOG_DIGEST.encode("utf-8") not in (
            catalog_unit.source_bytes
        ):
            raise TemporalCandidateError(
                "selection-storage V7 catalog authority differs"
            )
    else:
        try:
            version_8_prefix = authority.migration_set.prefix_digest(8)
        except Exception as exc:
            raise TemporalCandidateError(
                "selection-storage V8 migration authentication failed"
            ) from exc
        if (
            type(version_8_prefix) is not str
            or version_8_prefix != GLOBAL_CONTENT_RETENTION_V8_PREFIX_DIGEST
        ):
            raise TemporalCandidateError(
                "selection-storage fixed V8 prefix differs"
            )
        retention_state = _classify_global_content_retention_migration(
            authority,
            version_8_prefix,
        )
        if (
            retention_state == GLOBAL_CONTENT_RETENTION_MIGRATION_ABSENT
            and (
                type(authority.migration_set.digest) is not str
                or authority.migration_set.digest == SELECTION_STORAGE_V7_DIGEST
                or authority.migration_set.digest != version_8_prefix
            )
        ):
            raise TemporalCandidateError(
                "selection-storage V8 migration-set identity differs"
            )
    publication_state = (
        _classify_temporal_runtime_bundle_publication_adapter(
            snapshot,
            state,
            retention_state,
        )
    )
    selector_state = _classify_trusted_command_selector(
        authority,
        snapshot,
        state,
        retention_state,
    )
    _validate_global_content_retention_python_isolation(snapshot)
    _validate_selection_storage_active_authorities()
    _validate_selection_storage_isolation(
        snapshot,
        state,
        publication_state,
        selector_state,
    )
    return state


def _validate_runtime_selection_isolation(
    snapshot: architecture.PythonSourceSnapshotV1,
) -> None:
    for reachable, label in (
        (snapshot.production_reachability, "production"),
        (snapshot.legacy_reachability, "legacy"),
    ):
        if "kernel.temporal_carriers" in reachable:
            raise TemporalCandidateError(
                f"carrier selector entered the {label} import closure"
            )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json_digest(path: Path) -> str:
    package_root = str(PACKAGE_ROOT)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    from kernel.runtime_bundle import canonical_json_bytes

    canonical = canonical_json_bytes(_load_json(path))
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _canonical_json_length(path: Path) -> int:
    package_root = str(PACKAGE_ROOT)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    from kernel.runtime_bundle import canonical_json_bytes

    return len(canonical_json_bytes(_load_json(path)))


def _expected_manifest_entry(
    path: str,
    artifact_path: Path,
    currentness_note: str,
    law_basis: str = (
        "ADR 0002 and "
        "docs/rfcs/OFARM_Temporal_Coordinate_Candidate_RFC_v0_1.md"
    ),
) -> dict[str, object]:
    return {
        "packagePath": path,
        "sourcePath": None,
        "sha256": _sha256(artifact_path),
        "status": "NEW_CANDIDATE",
        "promotionLadderStage": "CANDIDATE_ARTIFACT",
        "currentnessNote": currentness_note,
        "lawBasis": law_basis,
    }


def validate_non_activation(runtime_catalog: object) -> None:
    if type(runtime_catalog) is not dict:
        raise TemporalCandidateError("runtime component catalog is malformed")
    contract_paths = runtime_catalog.get("contractSchemas")
    components = runtime_catalog.get("components")
    if type(contract_paths) is not list or type(components) is not list:
        raise TemporalCandidateError("runtime component catalog is malformed")
    if CANDIDATE_RELATIVE_PATHS.intersection(contract_paths):
        raise TemporalCandidateError("candidate entered RuntimeBundle contracts")
    for component in components:
        if (
            type(component) is dict
            and component.get("path") in CANDIDATE_RELATIVE_PATHS
        ):
            raise TemporalCandidateError("candidate entered a runtime component")
    if RUNTIME_BUNDLE_CARRIER_ROLE in json.dumps(
        runtime_catalog, sort_keys=True
    ):
        raise TemporalCandidateError(
            "candidate role entered the active RuntimeBundle catalog"
        )


def validate_runtime_bundle_model_admission_authority() -> None:
    if not RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_PATH.is_file():
        raise TemporalCandidateError(
            "RuntimeBundle model-admission authority is missing"
        )
    authority_bytes = RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_PATH.read_bytes()
    if len(authority_bytes) != RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_BYTE_LENGTH:
        raise TemporalCandidateError(
            "RuntimeBundle model-admission authority byte length differs"
        )
    if (
        hashlib.sha256(authority_bytes).hexdigest()
        != RUNTIME_BUNDLE_MODEL_ADMISSION_RFC_DIGEST
    ):
        raise TemporalCandidateError(
            "RuntimeBundle model-admission authority digest differs"
        )


def validate_runtime_bundle_carrier_role_posture(
    migration_authority: TenantMigrationAuthoritySnapshot,
) -> None:
    validate_runtime_bundle_model_admission_authority()
    if not RUNTIME_BUNDLE_MODEL_PATH.is_file():
        raise TemporalCandidateError(
            "RuntimeBundle model eligibility authority is missing"
        )
    # Role text in this exact model path is inert eligibility, not activation.
    RUNTIME_BUNDLE_MODEL_PATH.read_text(encoding="utf-8")
    for path in RUNTIME_BUNDLE_ROLE_FORBIDDEN_AUTHORITY_PATHS:
        if RUNTIME_BUNDLE_CARRIER_ROLE in path.read_text(encoding="utf-8"):
            raise TemporalCandidateError(
                "candidate role entered an explicitly forbidden "
                f"RuntimeBundle authority: {path}"
            )
    role_bytes = RUNTIME_BUNDLE_CARRIER_ROLE.encode("utf-8")
    for migration in migration_authority.migration_set.migrations:
        if (
            role_bytes in migration.source_bytes
            and migration.filename
            != RUNTIME_BUNDLE_PERSISTENCE_MIGRATION_FILENAME
        ):
            raise TemporalCandidateError(
                "candidate role entered a forbidden authenticated "
                f"migration authority: {migration.filename}"
            )


def validate_active_temporal_activation_inputs() -> None:
    activation_markers = (
        CONTRACT_VERSION,
        CARRIER_SCHEMA_VERSION,
        CARRIER_MATRIX_ID,
        SELECTION_SCHEMA_VERSION,
        SELECTION_BINDING_ID,
        SELECTION_EXECUTION_POSTURE,
        COMMAND_SCHEMA_VERSION,
        COMMAND_BINDING_ID,
        COMMAND_EXECUTION_POSTURE,
        RUNTIME_BUNDLE_CARRIER_SCHEMA_VERSION,
        RUNTIME_BUNDLE_CARRIER_BINDING_ID,
        RUNTIME_BUNDLE_CARRIER_EXECUTION_POSTURE,
        RUNTIME_BUNDLE_CARRIER_ROLE,
        RUNTIME_BUNDLE_SELECTION_SCHEMA_VERSION,
        RUNTIME_BUNDLE_SELECTION_BINDING_ID,
        RUNTIME_BUNDLE_SELECTION_EXECUTION_POSTURE,
        PROMOTION_SCHEMA_VERSION,
        PROMOTION_BINDING_ID,
        PROMOTION_EXECUTION_POSTURE,
        *CANDIDATE_RELATIVE_PATHS,
    )
    for path, label in (
        (ACTIVE_ARTIFACT_SET_PATH, "ActiveArtifactSet"),
        (CAPABILITY_MANIFEST_PATH, "Capability Manifest"),
    ):
        active_text = path.read_text(encoding="utf-8")
        if any(marker in active_text for marker in activation_markers):
            raise TemporalCandidateError(f"candidate entered the {label}")


def _markdown_table_row_identity(line: str) -> str | None:
    cells = line.split("|", 2)
    if len(cells) < 3 or cells[0].strip():
        return None
    return cells[1].strip()


def validate_temporal_card_errata_trace(errata: str) -> None:
    rows = tuple(
        line
        for line in errata.splitlines()
        if _markdown_table_row_identity(line) == TEMPORAL_CARD_ERRATA_ROW_ID
    )
    if len(rows) != 1:
        raise TemporalCandidateError(
            "temporal decision-card ERRATA row identity differs"
        )
    if any(
        rows[0].count(marker) != 1
        for marker in TEMPORAL_CARD_ERRATA_REQUIRED_MARKERS
    ):
        raise TemporalCandidateError(
            "temporal decision-card ERRATA trace markers differ"
        )


def validate_candidate_governance() -> str:
    validate_temporal_runtime_bundle_publication_authorities()
    validate_global_content_retention_authorities()
    validate_selection_storage_authorities()
    migration_authority = load_tenant_migration_authority_snapshot()
    python_snapshot = _build_selection_storage_snapshot()
    selection_storage_state = _validate_selection_storage_conformance(
        migration_authority,
        python_snapshot,
    )
    coordinate_schema = _load_json(COORDINATE_SCHEMA_PATH)
    carrier_schema = _load_json(CARRIER_SCHEMA_PATH)
    carrier_matrix = _load_json(CARRIER_MATRIX_PATH)
    selection_schema = _load_json(SELECTION_SCHEMA_PATH)
    selection_binding = _load_json(SELECTION_BINDING_PATH)
    command_schema = _load_json(COMMAND_SCHEMA_PATH)
    command_binding = _load_json(COMMAND_BINDING_PATH)
    runtime_bundle_carrier_schema = _load_json(
        RUNTIME_BUNDLE_CARRIER_SCHEMA_PATH
    )
    runtime_bundle_carrier_binding = _load_json(
        RUNTIME_BUNDLE_CARRIER_BINDING_PATH
    )
    runtime_bundle_selection_schema = _load_json(
        RUNTIME_BUNDLE_SELECTION_SCHEMA_PATH
    )
    runtime_bundle_selection_binding = _load_json(
        RUNTIME_BUNDLE_SELECTION_BINDING_PATH
    )
    promotion_schema = _load_json(PROMOTION_SCHEMA_PATH)
    promotion_binding = _load_json(PROMOTION_BINDING_PATH)
    validate_coordinate_schema_shape(coordinate_schema)
    validate_carrier_schema_shape(carrier_schema)
    validate_carrier_matrix(carrier_matrix)
    validate_selection_schema_shape(selection_schema)
    validate_selection_binding(selection_binding)
    validate_command_schema_shape(command_schema, command_binding)
    validate_command_binding(
        command_binding,
        migration_authority,
    )
    validate_runtime_bundle_carrier_schema_shape(
        runtime_bundle_carrier_schema,
        runtime_bundle_carrier_binding,
    )
    validate_runtime_bundle_carrier_binding(
        runtime_bundle_carrier_binding
    )
    validate_runtime_bundle_selection_schema_shape(
        runtime_bundle_selection_schema,
        runtime_bundle_selection_binding,
    )
    validate_runtime_bundle_selection_binding(
        runtime_bundle_selection_binding
    )
    validate_promotion_schema_shape(promotion_schema, promotion_binding)
    validate_promotion_binding(promotion_binding)
    validate_promotion_dependency_consistency()
    validate_runtime_selection_binding()
    validate_runtime_selector_paths(selection_binding)
    _validate_runtime_selection_isolation(python_snapshot)

    manifest = _load_json(MANIFEST_PATH)
    entries = manifest.get("entries")
    if type(entries) is not list:
        raise TemporalCandidateError("contract manifest entries are absent")
    expected_entries = {
        COORDINATE_SCHEMA_RELATIVE_PATH: _expected_manifest_entry(
            COORDINATE_SCHEMA_RELATIVE_PATH,
            COORDINATE_SCHEMA_PATH,
            (
                "Package-local temporal-coordinate candidate for issue #176; "
                "not active, promoted, or selected by the production "
                "RuntimeBundle."
            ),
        ),
        CARRIER_SCHEMA_RELATIVE_PATH: _expected_manifest_entry(
            CARRIER_SCHEMA_RELATIVE_PATH,
            CARRIER_SCHEMA_PATH,
            (
                "Package-local temporal carrier-matrix schema candidate for "
                "issue #176; classification-only, inactive, and not selected "
                "by the production RuntimeBundle."
            ),
        ),
        CARRIER_MATRIX_RELATIVE_PATH: _expected_manifest_entry(
            CARRIER_MATRIX_RELATIVE_PATH,
            CARRIER_MATRIX_PATH,
            (
                "Package-local ADR 0002 carrier-matrix candidate for issue "
                "#176; classification-only, inactive, and not selected by "
                "the production RuntimeBundle."
            ),
        ),
        SELECTION_SCHEMA_RELATIVE_PATH: _expected_manifest_entry(
            SELECTION_SCHEMA_RELATIVE_PATH,
            SELECTION_SCHEMA_PATH,
            (
                "Package-local temporal carrier-selection binding schema "
                "candidate for issue #176; inactive, production-unbound, and "
                "not selected by the production RuntimeBundle."
            ),
            (
                "ADR 0002 and docs/rfcs/"
                "OFARM_Intervention_Valid_Time_Carrier_Selection_RFC_v0_1.md"
            ),
        ),
        SELECTION_BINDING_RELATIVE_PATH: _expected_manifest_entry(
            SELECTION_BINDING_RELATIVE_PATH,
            SELECTION_BINDING_PATH,
            (
                "Package-local intervention valid-time carrier-selection "
                "candidate for issue #176; executable only as an isolated "
                "pure library, inactive, and not selected by the production "
                "RuntimeBundle."
            ),
            (
                "ADR 0002 and docs/rfcs/"
                "OFARM_Intervention_Valid_Time_Carrier_Selection_RFC_v0_1.md"
            ),
        ),
        COMMAND_SCHEMA_RELATIVE_PATH: _expected_manifest_entry(
            COMMAND_SCHEMA_RELATIVE_PATH,
            COMMAND_SCHEMA_PATH,
            (
                "Package-local exact schema for one issue #176 "
                "operation-claim draft temporal-command candidate; "
                "contract-only, inactive, production-surface-closed, and "
                "not selected by the production RuntimeBundle."
            ),
            (
                "ADR 0002 and docs/rfcs/"
                "OFARM_Operation_Claim_Draft_Temporal_Command_RFC_v0_1.md"
            ),
        ),
        COMMAND_BINDING_RELATIVE_PATH: _expected_manifest_entry(
            COMMAND_BINDING_RELATIVE_PATH,
            COMMAND_BINDING_PATH,
            (
                "Package-local exact issue #176 operation-claim draft "
                "temporal-command candidate; contract-only, inactive, "
                "production-surface-closed, and not selected by the "
                "production RuntimeBundle."
            ),
            (
                "ADR 0002 and docs/rfcs/"
                "OFARM_Operation_Claim_Draft_Temporal_Command_RFC_v0_1.md"
            ),
        ),
        RUNTIME_BUNDLE_CARRIER_SCHEMA_RELATIVE_PATH: _expected_manifest_entry(
            RUNTIME_BUNDLE_CARRIER_SCHEMA_RELATIVE_PATH,
            RUNTIME_BUNDLE_CARRIER_SCHEMA_PATH,
            (
                "Package-local exact schema for the issue #176 "
                "temporal-governance RuntimeBundle carrier vocabulary; "
                "inactive, eligibility-only, runtime-unsupported, and "
                "absent from every active RuntimeBundle authority."
            ),
            (
                "ADR 0002 and docs/rfcs/"
                "OFARM_Temporal_Governance_RuntimeBundle_Carrier_RFC_v0_1.md"
            ),
        ),
        RUNTIME_BUNDLE_CARRIER_BINDING_RELATIVE_PATH: _expected_manifest_entry(
            RUNTIME_BUNDLE_CARRIER_BINDING_RELATIVE_PATH,
            RUNTIME_BUNDLE_CARRIER_BINDING_PATH,
            (
                "Package-local issue #176 temporal-governance RuntimeBundle "
                "carrier vocabulary candidate; inactive, eligibility-only, "
                "runtime-unsupported, and absent from every active "
                "RuntimeBundle authority."
            ),
            (
                "ADR 0002 and docs/rfcs/"
                "OFARM_Temporal_Governance_RuntimeBundle_Carrier_RFC_v0_1.md"
            ),
        ),
        RUNTIME_BUNDLE_SELECTION_SCHEMA_RELATIVE_PATH: (
            _expected_manifest_entry(
                RUNTIME_BUNDLE_SELECTION_SCHEMA_RELATIVE_PATH,
                RUNTIME_BUNDLE_SELECTION_SCHEMA_PATH,
                (
                    "Package-local exact schema for the issue #176 tenant "
                    "command RuntimeBundle-selection binding; inactive, "
                    "contract-only, production-unbound, and absent from "
                    "every active RuntimeBundle authority."
                ),
                (
                    "ADR 0002 and docs/rfcs/"
                    "OFARM_Tenant_Command_RuntimeBundle_Selection_RFC_v0_1.md"
                ),
            )
        ),
        RUNTIME_BUNDLE_SELECTION_BINDING_RELATIVE_PATH: (
            _expected_manifest_entry(
                RUNTIME_BUNDLE_SELECTION_BINDING_RELATIVE_PATH,
                RUNTIME_BUNDLE_SELECTION_BINDING_PATH,
                (
                    "Package-local issue #176 tenant command "
                    "RuntimeBundle-selection candidate; inactive, "
                    "contract-only, production-unbound, and absent from "
                    "every active RuntimeBundle authority."
                ),
                (
                    "ADR 0002 and docs/rfcs/"
                    "OFARM_Tenant_Command_RuntimeBundle_Selection_RFC_v0_1.md"
                ),
            )
        ),
        PROMOTION_SCHEMA_RELATIVE_PATH: _expected_manifest_entry(
            PROMOTION_SCHEMA_RELATIVE_PATH,
            PROMOTION_SCHEMA_PATH,
            (
                "Package-local exact schema for the issue #176 "
                "temporal-governance promotion contract; inactive, "
                "contract-only, and without promotion, current/default, "
                "or runtime effect."
            ),
            (
                "Constitution RC2.1 section 6.16, CP15, and docs/rfcs/"
                "OFARM_Temporal_Governance_Identity_Promotion_RFC_v0_1.md"
            ),
        ),
        PROMOTION_BINDING_RELATIVE_PATH: _expected_manifest_entry(
            PROMOTION_BINDING_RELATIVE_PATH,
            PROMOTION_BINDING_PATH,
            (
                "Package-local exact issue #176 temporal-governance "
                "promotion candidate for three identities; inactive, "
                "atomic, contract-only, and without promotion, "
                "current/default, or runtime effect."
            ),
            (
                "Constitution RC2.1 section 6.16, CP15, and docs/rfcs/"
                "OFARM_Temporal_Governance_Identity_Promotion_RFC_v0_1.md"
            ),
        ),
    }
    candidate_entries = [
        entry
        for entry in entries
        if type(entry) is dict
        and entry.get("packagePath") in CANDIDATE_RELATIVE_PATHS
    ]
    observed_entries = {
        entry.get("packagePath"): entry for entry in candidate_entries
    }
    if (
        len(candidate_entries) != len(expected_entries)
        or observed_entries != expected_entries
    ):
        raise TemporalCandidateError("candidate manifest metadata differs")

    rfc = RFC_PATH.read_text(encoding="utf-8")
    digest_markers = (
        (
            "**Temporal coordinate schema digest:** "
            f"`sha256:{_sha256(COORDINATE_SCHEMA_PATH)}`"
        ),
        (
            "**Temporal carrier matrix schema digest:** "
            f"`sha256:{_sha256(CARRIER_SCHEMA_PATH)}`"
        ),
        (
            "**Temporal carrier matrix instance digest:** "
            f"`sha256:{_sha256(CARRIER_MATRIX_PATH)}`"
        ),
    )
    if any(rfc.count(marker) != 1 for marker in digest_markers):
        raise TemporalCandidateError("candidate RFC digest binding differs")
    required_rfc_markers = (
        "9007199254740991",
        "pre-promotion",
        "candidate revisions",
        "complete Draft",
        "2020-12 validation path",
        CARRIER_MATRIX_ID,
        CARRIER_EXECUTION_POSTURE,
    )
    if any(marker not in rfc for marker in required_rfc_markers):
        raise TemporalCandidateError("candidate RFC stop conditions differ")

    selection_rfc = SELECTION_RFC_PATH.read_text(encoding="utf-8")
    selection_digest_markers = (
        f"`sha256:{_sha256(SELECTION_SCHEMA_PATH)}`",
        f"`sha256:{_sha256(SELECTION_BINDING_PATH)}`",
    )
    if any(
        selection_rfc.count(marker) != 1
        for marker in selection_digest_markers
    ):
        raise TemporalCandidateError(
            "carrier-selection RFC digest binding differs"
        )
    required_selection_markers = (
        SELECTION_BINDING_ID,
        SELECTION_IDENTITY_AUTHORITY,
        "never taken from caller data",
        "INTERVENTION_EVENT",
        "OPERATION_CLAIM",
        "production-unbound",
    )
    if any(
        marker not in selection_rfc for marker in required_selection_markers
    ):
        raise TemporalCandidateError(
            "carrier-selection RFC authority or stop conditions differ"
        )

    command_rfc = COMMAND_RFC_PATH.read_text(encoding="utf-8")
    command_digest_markers = (
        f"`sha256:{_sha256(COMMAND_SCHEMA_PATH)}`",
        f"`sha256:{_sha256(COMMAND_BINDING_PATH)}`",
    )
    if any(
        command_rfc.count(marker) != 1
        for marker in command_digest_markers
    ):
        raise TemporalCandidateError(
            "temporal governed-command RFC digest binding differs"
        )
    required_command_rfc_markers = (
        COMMAND_BINDING_ID,
        "COMMIT_OPERATION_CLAIM_DRAFT",
        "reviewed versioned artifact. None is accepted from caller data.",
        "Kbefore = Kbatch - 1",
        "returns the prior committed `CommitIngressResult` unchanged",
        "production authorization provider that owns",
        "production source of the trusted RuntimeBundle digest",
        "production-surface-closed and inactive",
        "Current-state reads, historical views, WINDOW behavior",
    )
    if any(
        marker not in command_rfc
        for marker in required_command_rfc_markers
    ):
        raise TemporalCandidateError(
            "temporal governed-command RFC authority or stops differ"
        )
    binding_text = json.dumps(command_binding, sort_keys=True)
    required_command_binding_markers = (
        COMMAND_IDENTITY_AUTHORITY,
        "RETURN_PRIOR_COMMITTED_RESULT_UNCHANGED_NO_NEW_BATCH",
        "NO_REVIEWED_PRODUCTION_AUTHORIZATION_PROVIDER_FOR_THIS_COMMAND",
        "NO_REVIEWED_RUNTIME_BUNDLE_SOURCE_FOR_COMMAND_AND_BINDING_IDENTITY",
    )
    if any(
        marker not in binding_text
        for marker in required_command_binding_markers
    ):
        raise TemporalCandidateError(
            "temporal governed-command binding authority or stops differ"
        )

    runtime_bundle_carrier_rfc = (
        RUNTIME_BUNDLE_CARRIER_RFC_PATH.read_text(encoding="utf-8")
    )
    runtime_bundle_carrier_digest_markers = (
        f"`sha256:{_sha256(RUNTIME_BUNDLE_CARRIER_SCHEMA_PATH)}`",
        f"`sha256:{_sha256(RUNTIME_BUNDLE_CARRIER_BINDING_PATH)}`",
    )
    if any(
        runtime_bundle_carrier_rfc.count(marker) != 1
        for marker in runtime_bundle_carrier_digest_markers
    ):
        raise TemporalCandidateError(
            "temporal RuntimeBundle carrier RFC digest binding differs"
        )
    required_runtime_bundle_carrier_rfc_markers = (
        RUNTIME_BUNDLE_CARRIER_SCHEMA_VERSION,
        RUNTIME_BUNDLE_CARRIER_BINDING_ID,
        RUNTIME_BUNDLE_CARRIER_ROLE,
        "allowed identity set is closed",
        "Eligibility for this role is not a component-closure rule",
        "not require every RuntimeBundle",
        "exact component closure required for",
        "CANDIDATE_INACTIVE",
        "Current-state reads and outputs remain blocked",
    )
    if any(
        marker not in runtime_bundle_carrier_rfc
        for marker in required_runtime_bundle_carrier_rfc_markers
    ):
        raise TemporalCandidateError(
            "temporal RuntimeBundle carrier RFC authority or stops differ"
        )

    runtime_bundle_selection_rfc = (
        RUNTIME_BUNDLE_SELECTION_RFC_PATH.read_text(encoding="utf-8")
    )
    runtime_bundle_selection_digest_markers = (
        f"`sha256:{_sha256(RUNTIME_BUNDLE_SELECTION_SCHEMA_PATH)}`",
        f"`sha256:{_sha256(RUNTIME_BUNDLE_SELECTION_BINDING_PATH)}`",
    )
    if any(
        runtime_bundle_selection_rfc.count(marker) != 1
        for marker in runtime_bundle_selection_digest_markers
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection RFC digest binding differs"
        )
    required_runtime_bundle_selection_rfc_markers = (
        RUNTIME_BUNDLE_SELECTION_SCHEMA_VERSION,
        RUNTIME_BUNDLE_SELECTION_BINDING_ID,
        "The only trusted source of the RuntimeBundle digest",
        "The selection-binding identity is never taken from caller data.",
        "before command admission",
        "exact sixteen",
        "Unrelated components may",
        "RUNTIME_BUNDLE_SELECTION_REFUSED_NO_WRITE",
        "Selection failure is atomic no-write refusal",
        "Mapping this internal refusal to any public result",
        "separate authorization-order and output-governance",
        "Current-state reads and outputs remain blocked",
    )
    if any(
        marker not in runtime_bundle_selection_rfc
        for marker in required_runtime_bundle_selection_rfc_markers
    ):
        raise TemporalCandidateError(
            "tenant command RuntimeBundle-selection RFC authority or stops differ"
        )

    _assert_promotion_rfc_digest()
    promotion_rfc = PROMOTION_RFC_PATH.read_text(encoding="utf-8")
    promotion_digest_markers = (
        f"`sha256:{_sha256(PROMOTION_SCHEMA_PATH)}`",
        f"`sha256:{_sha256(PROMOTION_BINDING_PATH)}`",
    )
    if any(
        promotion_rfc.count(marker) != 1
        for marker in promotion_digest_markers
    ):
        raise TemporalCandidateError(
            "temporal promotion RFC digest binding differs"
        )
    required_promotion_rfc_markers = (
        PROMOTION_SCHEMA_VERSION,
        PROMOTION_BINDING_ID,
        "GOVERNED_INACTIVE",
        "Approval, merge,",
        "currentness trace",
        "exactly three",
        "promotion set is atomic",
        "universal RuntimeBundle co-presence requirement",
        "Current-state reads and outputs remain blocked",
    )
    if any(
        marker not in promotion_rfc
        for marker in required_promotion_rfc_markers
    ):
        raise TemporalCandidateError(
            "temporal promotion RFC authority or stops differ"
        )

    errata = ERRATA_PATH.read_text(encoding="utf-8")
    validate_temporal_card_errata_trace(errata)
    if any(
        marker not in errata
        for marker in (
            "| E-008 |",
            CONTRACT_VERSION,
            CARRIER_MATRIX_ID,
            SELECTION_BINDING_ID,
            COMMAND_BINDING_ID,
            RUNTIME_BUNDLE_CARRIER_BINDING_ID,
            RUNTIME_BUNDLE_CARRIER_ROLE,
            "closed allowed identity set",
            "not as a requirement that every RuntimeBundle",
            RUNTIME_BUNDLE_SELECTION_BINDING_ID,
            "exact sixteen-component command-required subset",
            "creates no storage, selector, active role, or command integration",
            PROMOTION_BINDING_ID,
            "atomic future human-governed lifecycle decision",
            "targets only `GOVERNED_INACTIVE`",
            "separate human decision and currentness trace",
            "production authorization provider",
            "selection storage/control",
            "public refusal mapping",
        )
    ):
        raise TemporalCandidateError("candidate ERRATA governance record differs")

    runtime_catalog = _load_json(RUNTIME_CATALOG_PATH)
    validate_non_activation(runtime_catalog)
    validate_runtime_bundle_carrier_role_posture(migration_authority)
    validate_active_temporal_activation_inputs()
    return selection_storage_state


def _coordinate_value(
    *,
    valid_cut: dict[str, object] | None = None,
    knowledge_cut: dict[str, object] | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "schemaVersion": CONTRACT_VERSION,
        "validCut": valid_cut
        or {
            "cutType": "POINT",
            "validAt": "2026-07-28T10:30:00.123456Z",
        },
        "knowledgeCut": knowledge_cut
        or {
            "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
            "position": 42,
        },
    }
    if extra:
        value.update(extra)
    return value


REFUSAL_VECTORS = (
    RefusalVector(
        "naive-time",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "POINT",
                "validAt": "2026-07-28T10:30:00",
            }
        ),
        "canonical UTC",
        True,
    ),
    RefusalVector(
        "leap-second",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "POINT",
                "validAt": "2026-12-31T23:59:60Z",
            }
        ),
        "canonical UTC",
        True,
    ),
    RefusalVector(
        "excess-fractional-precision",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "POINT",
                "validAt": "2026-07-28T10:30:00.1234567Z",
            }
        ),
        "canonical UTC",
        True,
    ),
    RefusalVector(
        "non-real-gregorian-instant",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "POINT",
                "validAt": "2026-02-30T10:30:00Z",
            }
        ),
        "not a real UTC instant",
    ),
    RefusalVector(
        "mixed-point-window",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "POINT",
                "validAt": "2026-07-28T10:30:00Z",
                "windowStart": "2026-01-01T00:00:00Z",
            }
        ),
        "unknown fields",
        True,
    ),
    RefusalVector(
        "open-query-window",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "WINDOW",
                "windowStart": "2026-01-01T00:00:00Z",
            }
        ),
        "missing fields",
        True,
    ),
    RefusalVector(
        "empty-query-window",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "WINDOW",
                "windowStart": "2026-01-01T00:00:00Z",
                "windowEnd": "2026-01-01T00:00:00Z",
            }
        ),
        "non-empty and half-open",
    ),
    RefusalVector(
        "reversed-query-window",
        validate_temporal_coordinate,
        _coordinate_value(
            valid_cut={
                "cutType": "WINDOW",
                "windowStart": "2027-01-01T00:00:00Z",
                "windowEnd": "2026-01-01T00:00:00Z",
            }
        ),
        "non-empty and half-open",
    ),
    RefusalVector(
        "negative-position",
        validate_temporal_coordinate,
        _coordinate_value(
            knowledge_cut={
                "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
                "position": -1,
            }
        ),
        "portable safe-integer range",
        True,
    ),
    RefusalVector(
        "boolean-position",
        validate_temporal_coordinate,
        _coordinate_value(
            knowledge_cut={
                "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
                "position": True,
            }
        ),
        "portable safe-integer range",
        True,
    ),
    RefusalVector(
        "unsafe-position",
        validate_temporal_coordinate,
        _coordinate_value(
            knowledge_cut={
                "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
                "position": MAX_KNOWLEDGE_POSITION + 1,
            }
        ),
        "portable safe-integer range",
        True,
    ),
    RefusalVector(
        "tenant-alias",
        validate_temporal_coordinate,
        _coordinate_value(
            knowledge_cut={"tenantId": "tenant:demo", "position": 0}
        ),
        "not canonical",
        True,
    ),
    RefusalVector(
        "nil-tenant",
        validate_temporal_coordinate,
        _coordinate_value(
            knowledge_cut={"tenantId": NIL_TENANT_ID, "position": 0}
        ),
        "not canonical",
        True,
    ),
    RefusalVector(
        "unknown-coordinate-field",
        validate_temporal_coordinate,
        _coordinate_value(extra={"asOf": "2026-07-28T10:30:00Z"}),
        "unknown fields",
        True,
    ),
    RefusalVector(
        "empty-valid-interval",
        validate_valid_interval,
        {
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-01-01T00:00:00Z",
        },
        "non-empty and half-open",
    ),
    RefusalVector(
        "reversed-valid-interval",
        validate_valid_interval,
        {
            "validFrom": "2027-01-01T00:00:00Z",
            "validUntil": "2026-01-01T00:00:00Z",
        },
        "non-empty and half-open",
    ),
    RefusalVector(
        "unknown-window-meaning",
        validate_window_meaning,
        "QUERY_WIDE",
        "closed vocabulary",
    ),
)


def _must_refuse(vector: RefusalVector) -> None:
    try:
        vector.validator(copy.deepcopy(vector.value))
    except TemporalCandidateError as exc:
        if re.search(vector.expected_error, str(exc)) is None:
            raise TemporalCandidateError(
                f"negative vector {vector.vector_id!r} returned the wrong refusal"
            ) from exc
        return
    except Exception as exc:
        raise TemporalCandidateError(
            f"negative vector {vector.vector_id!r} crashed"
        ) from exc
    raise TemporalCandidateError(
        f"negative vector {vector.vector_id!r} was accepted"
    )


def validate_semantic_vectors() -> None:
    validate_temporal_coordinate(_coordinate_value())
    validate_temporal_coordinate(
        _coordinate_value(
            valid_cut={
                "cutType": "WINDOW",
                "windowStart": "2026-01-01T00:00:00Z",
                "windowEnd": "2027-01-01T00:00:00Z",
            },
            knowledge_cut={
                "tenantId": "5ca463b4-4dfc-45db-a878-8ae357b17ad4",
                "position": MAX_KNOWLEDGE_POSITION,
            },
        )
    )
    validate_valid_interval({"validFrom": "2026-01-01T00:00:00Z"})
    validate_valid_interval(
        {
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2027-01-01T00:00:00Z",
        }
    )
    for meaning in sorted(WINDOW_MEANINGS):
        validate_window_meaning(meaning)
    validate_carrier_matrix(_load_json(CARRIER_MATRIX_PATH))
    for vector in REFUSAL_VECTORS:
        _must_refuse(vector)


def main() -> int:
    try:
        selection_storage_state = validate_candidate_governance()
        validate_semantic_vectors()
    except (OSError, TemporalCandidateError) as exc:
        print(f"TEMPORAL CANDIDATE FAIL: {exc}")
        return 1
    print(f"TEMPORAL CANDIDATE PASS: {selection_storage_state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
