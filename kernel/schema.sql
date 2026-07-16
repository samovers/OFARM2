-- OFARM2 Kernel truth store DDL (M1 brief task 2)
-- Storage posture per PLATFORM.md §"Storage posture (binding for the pilot)":
--   * append-only record tables, immutable payload digests (sha256)
--   * schema version + schema hash stored per record
--   * explicit relation/edge table (authority, evidence, review, lineage, materialization refs)
--   * materialization/projection tables marked derived / derived-recomputable
--   * no authoritative writes into projections, caches, or report stores
--   * outbox/gate-log tables for enforcement traces
--   * the PromotionTrace reachability link written in the same transaction as the commit (D3)

-- ---------------------------------------------------------------------------
-- Append-only enforcement (Kernel rule 1): correction is supersession.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION kernel_forbid_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'OFARM Kernel rule 1 (append-only): % on %.% is forbidden; correction is supersession',
    TG_OP, TG_TABLE_SCHEMA, TG_TABLE_NAME;
END
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION kernel_valid_tenant_ref(value text) RETURNS boolean AS $$
  SELECT value ~ '^tenant:[A-Za-z0-9._:-]{1,248}$'
$$ LANGUAGE sql IMMUTABLE STRICT;

-- Exact bytes of this schema.sql are selected once at startup. The fixed,
-- append-only identity separates database deployment posture from RuntimeBundle
-- identity and prevents a restart from silently repairing a different schema.
CREATE TABLE IF NOT EXISTS runtime_schema_identity (
  identity_key text COLLATE "C" PRIMARY KEY CHECK (
    identity_key = 'ofarm-kernel-schema'),
  schema_digest text COLLATE "C" NOT NULL CHECK (
    schema_digest ~ '^sha256:[0-9a-f]{64}$')
);

DROP TRIGGER IF EXISTS trg_runtime_schema_identity_append_only
  ON runtime_schema_identity;
CREATE TRIGGER trg_runtime_schema_identity_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON runtime_schema_identity
  FOR EACH STATEMENT EXECUTE FUNCTION kernel_forbid_mutation();

-- ---------------------------------------------------------------------------
-- Immutable, content-addressed RuntimeBundles (issue #171). These tables are
-- implementation receipts, not promoted contracts. They retain exact bytes
-- by placement and verify exact equality whenever a content identity is reused.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS runtime_content_blob (
  content_digest  text COLLATE "C" PRIMARY KEY CHECK (
    content_digest ~ '^sha256:[0-9a-f]{64}$'),
  canonical_bytes bytea NOT NULL,
  byte_length bigint NOT NULL CHECK (
    byte_length >= 0 AND byte_length = octet_length(canonical_bytes))
);

CREATE TABLE IF NOT EXISTS runtime_tenant_content_blob (
  tenant_ref      text COLLATE "C" NOT NULL CHECK (kernel_valid_tenant_ref(tenant_ref)),
  content_digest  text COLLATE "C" NOT NULL CHECK (
    content_digest ~ '^sha256:[0-9a-f]{64}$'),
  canonical_bytes bytea NOT NULL,
  byte_length bigint NOT NULL CHECK (
    byte_length >= 0 AND byte_length = octet_length(canonical_bytes)),
  PRIMARY KEY (tenant_ref, content_digest)
);
CREATE INDEX IF NOT EXISTS ix_runtime_tenant_content_digest
  ON runtime_tenant_content_blob (content_digest);

CREATE TABLE IF NOT EXISTS runtime_bundle (
  tenant_ref      text COLLATE "C" NOT NULL CHECK (kernel_valid_tenant_ref(tenant_ref)),
  bundle_digest   text COLLATE "C" NOT NULL CHECK (
    bundle_digest ~ '^sha256:[0-9a-f]{64}$'),
  bundle_ref      text COLLATE "C" NOT NULL,
  canonical_bytes bytea NOT NULL,
  byte_length     bigint NOT NULL CHECK (
    byte_length >= 0 AND byte_length = octet_length(canonical_bytes)),
  record_time     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_ref, bundle_digest),
  UNIQUE (tenant_ref, bundle_ref),
  CHECK (bundle_ref = 'runtimebundle:' || bundle_digest)
);
CREATE INDEX IF NOT EXISTS ix_runtime_bundle_digest
  ON runtime_bundle (bundle_digest);

CREATE TABLE IF NOT EXISTS runtime_bundle_component (
  tenant_ref       text COLLATE "C" NOT NULL CHECK (kernel_valid_tenant_ref(tenant_ref)),
  bundle_digest    text COLLATE "C" NOT NULL,
  component_role   text COLLATE "C" NOT NULL CHECK (component_role IN (
    'PROFILE_DESCRIPTOR', 'ACTIVE_MANIFEST', 'PROFILE_INSTANCE',
    'PROFILE_POLICY', 'QUERY_SPECIFICATION', 'QUERY_PLAN', 'VIEW_BINDING',
    'CONTRACT_SCHEMA', 'DRAFT_CONTRACT_SCHEMA', 'VALIDATOR_SOURCE',
    'ADAPTER_SOURCE',
    'QUERY_OUTPUT_SOURCE', 'REFERENCE_SNAPSHOT', 'REFERENCE_SOURCE')),
  logical_ref      text COLLATE "C" NOT NULL CHECK (length(logical_ref) BETWEEN 1 AND 1024),
  canonicalization text COLLATE "C" NOT NULL CHECK (canonicalization IN (
    'OFARM_CANONICAL_JSON_V1', 'EXACT_BYTES_V1')),
  content_placement text COLLATE "C" NOT NULL CHECK (content_placement IN (
    'GLOBAL_IMMUTABLE_CONTENT', 'TENANT_RUNTIME_SELECTION')),
  global_content_digest text COLLATE "C" REFERENCES runtime_content_blob(content_digest),
  tenant_content_digest text COLLATE "C",
  byte_length      bigint NOT NULL CHECK (byte_length >= 0),
  PRIMARY KEY (tenant_ref, bundle_digest, component_role, logical_ref),
  FOREIGN KEY (tenant_ref, bundle_digest)
    REFERENCES runtime_bundle(tenant_ref, bundle_digest),
  FOREIGN KEY (tenant_ref, tenant_content_digest)
    REFERENCES runtime_tenant_content_blob(tenant_ref, content_digest),
  CHECK (
    (content_placement = 'GLOBAL_IMMUTABLE_CONTENT'
      AND global_content_digest IS NOT NULL
      AND tenant_content_digest IS NULL)
    OR
    (content_placement = 'TENANT_RUNTIME_SELECTION'
      AND global_content_digest IS NULL
      AND tenant_content_digest IS NOT NULL))
);

DROP TRIGGER IF EXISTS trg_runtime_content_blob_append_only
  ON runtime_content_blob;
CREATE TRIGGER trg_runtime_content_blob_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON runtime_content_blob
  FOR EACH STATEMENT EXECUTE FUNCTION kernel_forbid_mutation();

DROP TRIGGER IF EXISTS trg_runtime_tenant_content_blob_append_only
  ON runtime_tenant_content_blob;
CREATE TRIGGER trg_runtime_tenant_content_blob_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON runtime_tenant_content_blob
  FOR EACH STATEMENT EXECUTE FUNCTION kernel_forbid_mutation();

DROP TRIGGER IF EXISTS trg_runtime_bundle_append_only ON runtime_bundle;
CREATE TRIGGER trg_runtime_bundle_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON runtime_bundle
  FOR EACH STATEMENT EXECUTE FUNCTION kernel_forbid_mutation();

DROP TRIGGER IF EXISTS trg_runtime_bundle_component_append_only
  ON runtime_bundle_component;
CREATE TRIGGER trg_runtime_bundle_component_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON runtime_bundle_component
  FOR EACH STATEMENT EXECUTE FUNCTION kernel_forbid_mutation();

-- ---------------------------------------------------------------------------
-- kernel_record: one row per governed contract record. JSONB payload is
-- validated against the package contracts on write (application layer);
-- payload_sha256 is the digest of the canonical JSON serialization;
-- schema_hash is the sha256 of the exact contract file used to validate.
-- record_time is server commit time and never collapses with the event /
-- assertion / effective times inside the payload (Kernel rule 6).
-- lane: 'canonical' = package contract lane; 'draft' = drafts_reference
-- shapes implemented behind Kernel law without promotion (D16).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kernel_record (
  record_id      text PRIMARY KEY,
  record_kind    text NOT NULL,            -- schemaVersion const, e.g. 'ofarm.assertionrecord.v0.1'
  lane           text NOT NULL DEFAULT 'canonical' CHECK (lane IN ('canonical', 'draft')),
  schema_hash    text NOT NULL,
  payload        jsonb NOT NULL,
  payload_sha256 text NOT NULL,
  record_time    timestamptz NOT NULL DEFAULT now(),
  tenant_ref     text COLLATE "C" NOT NULL,
  runtime_bundle_digest text COLLATE "C" NOT NULL,
  FOREIGN KEY (tenant_ref, runtime_bundle_digest)
    REFERENCES runtime_bundle(tenant_ref, bundle_digest)
);
CREATE INDEX IF NOT EXISTS ix_kernel_record_kind ON kernel_record (record_kind);

DROP TRIGGER IF EXISTS trg_kernel_record_append_only ON kernel_record;
CREATE TRIGGER trg_kernel_record_append_only
  BEFORE UPDATE OR DELETE ON kernel_record
  FOR EACH STATEMENT EXECUTE FUNCTION kernel_forbid_mutation();

-- ---------------------------------------------------------------------------
-- kernel_edge: explicit, durable relation table. References are edges,
-- not JSON-path conventions (PLATFORM.md). Append-only.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kernel_edge (
  edge_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  edge_type     text NOT NULL CHECK (edge_type IN (
                  'AUTHORITY_BASIS',        -- record -> AuthorizationDecisionResult / grant
                  'EVIDENCE',               -- record -> EvidenceRecord
                  'REVIEW',                 -- consequence/assertion -> ReviewDecision
                  'EVENT_SOURCE',           -- assertion/consequence -> SemanticEventEnvelope
                  'LINEAGE_SUPERSEDES',     -- new record -> superseded record
                  'LINEAGE_REVISES',        -- reserved; M1 emits corrections as LINEAGE_SUPERSEDES
                  'MATERIALIZATION_BASIS',  -- MaterializationBasis -> contributing record
                  'PROMOTION_EMITS',        -- PromotionTrace -> emitted record (reachability, D3)
                  'COMPLIANCE_CLAIM',       -- semantic event -> ComplianceClaim carrier record
                  'STRUCTURE_PAYLOAD',      -- semantic event -> typed identity-payload carrier (M2 G1)
                  'LINEAGE_SUPERSEDES_INTENT', -- pending assertion -> consequence it will supersede on acceptance (M2 G1)
                  'DISPUTE'                 -- in-force consequence -> contest ReviewDecision (M2 G5-4)
                )),
  src_record_id text NOT NULL,
  dst_record_id text NOT NULL,
  record_time   timestamptz NOT NULL DEFAULT now(),
  tenant_ref    text COLLATE "C" NOT NULL,
  runtime_bundle_digest text COLLATE "C" NOT NULL,
  FOREIGN KEY (tenant_ref, runtime_bundle_digest)
    REFERENCES runtime_bundle(tenant_ref, bundle_digest)
);
-- CREATE TABLE IF NOT EXISTS never updates an existing CHECK: refresh the
-- edge vocabulary idempotently so pre-existing databases pick up new types
ALTER TABLE kernel_edge DROP CONSTRAINT IF EXISTS kernel_edge_edge_type_check;
ALTER TABLE kernel_edge ADD CONSTRAINT kernel_edge_edge_type_check CHECK (edge_type IN (
  'AUTHORITY_BASIS', 'EVIDENCE', 'REVIEW', 'EVENT_SOURCE',
  'LINEAGE_SUPERSEDES', 'LINEAGE_REVISES', 'MATERIALIZATION_BASIS',
  'PROMOTION_EMITS', 'COMPLIANCE_CLAIM', 'STRUCTURE_PAYLOAD',
  'LINEAGE_SUPERSEDES_INTENT', 'DISPUTE'));

CREATE INDEX IF NOT EXISTS ix_kernel_edge_src ON kernel_edge (src_record_id, edge_type);
CREATE INDEX IF NOT EXISTS ix_kernel_edge_dst ON kernel_edge (dst_record_id, edge_type);

-- Reachability invariant (KERNEL.md): every authoritative record reachable
-- from EXACTLY ONE PromotionTrace. "At most one" is this unique index;
-- "at least one" is the deferred constraint trigger below.
CREATE UNIQUE INDEX IF NOT EXISTS uq_promotion_emits_dst
  ON kernel_edge (dst_record_id) WHERE edge_type = 'PROMOTION_EMITS';

DROP TRIGGER IF EXISTS trg_kernel_edge_append_only ON kernel_edge;
CREATE TRIGGER trg_kernel_edge_append_only
  BEFORE UPDATE OR DELETE ON kernel_edge
  FOR EACH STATEMENT EXECUTE FUNCTION kernel_forbid_mutation();

-- A PROMOTION_EMITS edge is only reachability evidence if its SOURCE really
-- is a stored PromotionTrace AND that trace's own payload agrees: the edge
-- destination must be the trace's semantic event or appear in its emitted
-- refs, and an accepted consequence may only be emitted under a promotion-
-- compatible outcome. Reconstruction from the edge table and from the trace
-- payload must never disagree (hostile review blockers 5 + 7). Checked
-- deferred so the trace can land later in the same transaction.
CREATE OR REPLACE FUNCTION kernel_require_trace_source() RETURNS trigger AS $$
DECLARE
  trace jsonb;
BEGIN
  IF NEW.edge_type <> 'PROMOTION_EMITS' THEN
    RETURN NULL;
  END IF;
  SELECT payload INTO trace FROM kernel_record
   WHERE record_id = NEW.src_record_id
     AND record_kind = 'ofarm.promotiontrace.v0.1';
  IF trace IS NULL THEN
    RAISE EXCEPTION 'OFARM Kernel reachability invariant: PROMOTION_EMITS source % is not a stored PromotionTrace',
      NEW.src_record_id;
  END IF;
  IF NOT (trace ->> 'semanticEventRef' = NEW.dst_record_id
          OR COALESCE(trace -> 'emittedAssertionRecordRefs', '[]'::jsonb) ? NEW.dst_record_id
          OR COALESCE(trace -> 'emittedReviewDecisionRefs', '[]'::jsonb) ? NEW.dst_record_id
          OR COALESCE(trace -> 'emittedAcceptedConsequenceRefs', '[]'::jsonb) ? NEW.dst_record_id)
  THEN
    RAISE EXCEPTION 'OFARM Kernel reachability invariant: edge destination % is not listed in the payload of PromotionTrace %',
      NEW.dst_record_id, NEW.src_record_id;
  END IF;
  IF COALESCE(trace -> 'emittedAcceptedConsequenceRefs', '[]'::jsonb) ? NEW.dst_record_id
     AND trace ->> 'finalOutcome' <> 'PROMOTE_ACCEPTED'
  THEN
    RAISE EXCEPTION 'OFARM Kernel reachability invariant: accepted consequence % emitted under non-promotion outcome %',
      NEW.dst_record_id, trace ->> 'finalOutcome';
  END IF;
  RETURN NULL;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_kernel_edge_trace_source ON kernel_edge;
CREATE CONSTRAINT TRIGGER trg_kernel_edge_trace_source
  AFTER INSERT ON kernel_edge
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION kernel_require_trace_source();

-- "At least one" half of the reachability invariant, checked at COMMIT time
-- so the PROMOTION_EMITS edge can land later in the same transaction (D3:
-- linked in the same transaction; no schema change is required or permitted).
CREATE OR REPLACE FUNCTION kernel_require_promotion_reachability() RETURNS trigger AS $$
BEGIN
  IF NEW.record_kind IN (
       'ofarm.assertionrecord.v0.1',
       'ofarm.semanticeventenvelope.v0.1',
       'ofarm.reviewdecision.v0.1',
       'ofarm.acceptedeventconsequence.v0.1'
     )
     AND NOT EXISTS (
       SELECT 1 FROM kernel_edge
        WHERE edge_type = 'PROMOTION_EMITS' AND dst_record_id = NEW.record_id
     )
  THEN
    RAISE EXCEPTION 'OFARM Kernel reachability invariant: authoritative record % (%) has no PromotionTrace link in this transaction',
      NEW.record_id, NEW.record_kind;
  END IF;
  RETURN NULL;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_kernel_record_reachability ON kernel_record;
CREATE CONSTRAINT TRIGGER trg_kernel_record_reachability
  AFTER INSERT ON kernel_record
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION kernel_require_promotion_reachability();

-- ---------------------------------------------------------------------------
-- kernel_gate_log: enforcement/outbox trace. Every gate outcome that affects
-- promotion, rejection, review, activation, or publication lands here
-- (PLATFORM.md). Append-only. Zero silent acceptances (PILOT_SI.md success
-- criterion) is auditable from this table joined to kernel_record.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kernel_gate_log (
  entry_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  request_id   text NOT NULL,
  gate         text NOT NULL,
  outcome      text NOT NULL,
  reason_code  text,
  rationale    text,
  related_refs jsonb,
  record_time  timestamptz NOT NULL DEFAULT now(),
  tenant_ref   text COLLATE "C" NOT NULL,
  runtime_bundle_digest text COLLATE "C" NOT NULL,
  FOREIGN KEY (tenant_ref, runtime_bundle_digest)
    REFERENCES runtime_bundle(tenant_ref, bundle_digest)
);
CREATE INDEX IF NOT EXISTS ix_kernel_gate_log_request ON kernel_gate_log (request_id);

DROP TRIGGER IF EXISTS trg_kernel_gate_log_append_only ON kernel_gate_log;
CREATE TRIGGER trg_kernel_gate_log_append_only
  BEFORE UPDATE OR DELETE ON kernel_gate_log
  FOR EACH STATEMENT EXECUTE FUNCTION kernel_forbid_mutation();

-- ---------------------------------------------------------------------------
-- kernel_idempotency: replay bookkeeping for the ingress boundary
-- (Event Ingress and Promotion Boundary Closure RFC §2.4). Append-only:
-- a key is claimed once; replays read, never rewrite.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kernel_idempotency (
  idempotency_key       text NOT NULL,
  request_id            text NOT NULL,
  source_payload_digest text,
  result_record_id      text NOT NULL,
  record_time           timestamptz NOT NULL DEFAULT now(),
  tenant_ref            text COLLATE "C" NOT NULL,
  runtime_bundle_digest text COLLATE "C" NOT NULL,
  PRIMARY KEY (tenant_ref, idempotency_key),
  FOREIGN KEY (tenant_ref, runtime_bundle_digest)
    REFERENCES runtime_bundle(tenant_ref, bundle_digest)
);

DROP TRIGGER IF EXISTS trg_kernel_idempotency_append_only ON kernel_idempotency;
CREATE TRIGGER trg_kernel_idempotency_append_only
  BEFORE UPDATE OR DELETE ON kernel_idempotency
  FOR EACH STATEMENT EXECUTE FUNCTION kernel_forbid_mutation();

-- ---------------------------------------------------------------------------
-- DERIVED / RECOMPUTABLE tables. Never authoritative (Kernel rule 5; the
-- explainable-evidence RFC §6.2: the dependency index may accelerate
-- invalidation; it may not become the only surviving explanation of truth).
-- These tables are recomputable from kernel_record + kernel_edge and are
-- exempt from the append-only rule for that reason.
-- ---------------------------------------------------------------------------

-- derived: one row per live materialization key/answer. The governed records
-- (MaterializationBasis/Result/Snapshot, ContextSnapshot) live in
-- kernel_record; this is the runtime index over them.
CREATE TABLE IF NOT EXISTS derived_materialization (
  materialization_id   text PRIMARY KEY,
  key_digest           text NOT NULL,        -- digest of the draft MaterializationKey shape
  materialization_key  jsonb NOT NULL,       -- draft MaterializationKey (implemented, not promoted — D16)
  target_twin          text NOT NULL,
  anchor_scope_ref     text NOT NULL,
  time_policy          jsonb NOT NULL,
  use_class            text NOT NULL,
  freshness            text NOT NULL CHECK (freshness IN ('FRESH', 'STALE', 'INVALID')),
  current_state        jsonb NOT NULL,
  basis_record_id      text NOT NULL,
  snapshot_record_id   text NOT NULL,
  context_snapshot_ref text NOT NULL,
  freshness_vector     jsonb NOT NULL,       -- draft MaterializationFreshnessVector (D16)
  generated_at         timestamptz NOT NULL DEFAULT now(),
  superseded_by        text,
  tenant_ref           text COLLATE "C" NOT NULL,
  runtime_bundle_digest text COLLATE "C" NOT NULL,
  FOREIGN KEY (tenant_ref, runtime_bundle_digest)
    REFERENCES runtime_bundle(tenant_ref, bundle_digest)
);
CREATE INDEX IF NOT EXISTS ix_derived_mat_key
  ON derived_materialization (tenant_ref, runtime_bundle_digest, key_digest);

-- derived: dependency index entries (draft MaterializationDependencyIndex
-- shape, D16). Connects basis changes to affected materialization keys
-- (explainable-evidence RFC §6).
CREATE TABLE IF NOT EXISTS derived_dependency_index (
  entry_id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dependency_source_ref    text NOT NULL,
  dependency_source_family text NOT NULL,
  key_digest               text NOT NULL,
  entry                    jsonb NOT NULL,
  generated_at             timestamptz NOT NULL DEFAULT now(),
  tenant_ref               text COLLATE "C" NOT NULL,
  runtime_bundle_digest    text COLLATE "C" NOT NULL,
  FOREIGN KEY (tenant_ref, runtime_bundle_digest)
    REFERENCES runtime_bundle(tenant_ref, bundle_digest)
);
CREATE INDEX IF NOT EXISTS ix_derived_dep_source ON derived_dependency_index (dependency_source_ref);
CREATE INDEX IF NOT EXISTS ix_derived_dep_key ON derived_dependency_index (key_digest);

-- derived: store-backed external reference-data cache (M2 P1). When a governed
-- import (kernel/adapters.py) is given a data payload, it persists the parsed
-- source DATA here, keyed by ReferenceSnapshot id + data_family, in the SAME
-- serialized transaction as the snapshot + gate-log entry. This is NOT OFARM
-- truth: it is an external artifact/index cache so a verification register can
-- resolve an imported snapshot's content from the store (not only from committed
-- package files). The ReferenceSnapshot remains the canonical governed import
-- record; the payload is opaque to the generic runner (a scheme-specific reader,
-- e.g. ProductRegister, interprets it). Scheme-agnostic: data_family is a
-- parameter, never a hardcoded scheme. One row per (snapshot_ref, data_family);
-- a conflicting re-import is refused at the snapshot gate, so this never
-- overwrites. Retain it append-only until durable source bytes and deterministic
-- rebuildability are proven.
CREATE TABLE IF NOT EXISTS reference_snapshot_data (
  snapshot_ref   text NOT NULL,
  data_family    text NOT NULL,
  artifact_ref   text,
  source_digest  text,
  parser_label   text,
  record_count   integer,
  payload        jsonb NOT NULL,
  payload_sha256 text NOT NULL,
  record_time    timestamptz NOT NULL DEFAULT now(),
  tenant_ref     text COLLATE "C" NOT NULL,
  runtime_bundle_digest text COLLATE "C" NOT NULL,
  PRIMARY KEY (tenant_ref, runtime_bundle_digest, snapshot_ref, data_family),
  FOREIGN KEY (tenant_ref, runtime_bundle_digest)
    REFERENCES runtime_bundle(tenant_ref, bundle_digest)
);
CREATE INDEX IF NOT EXISTS ix_reference_snapshot_data_family ON reference_snapshot_data (data_family);

DROP TRIGGER IF EXISTS trg_reference_snapshot_data_append_only
  ON reference_snapshot_data;
CREATE TRIGGER trg_reference_snapshot_data_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON reference_snapshot_data
  FOR EACH STATEMENT EXECUTE FUNCTION kernel_forbid_mutation();

-- runtime evidence lane: draft-shape traces (InvalidationEvaluationTrace …)
-- recorded append-only but OUTSIDE the canonical record table — implemented
-- behind Kernel law without promoting the draft contracts (D16). Not part of
-- the reachability invariant (traces are runtime evidence, not source truth).
CREATE TABLE IF NOT EXISTS runtime_trace (
  trace_id       text PRIMARY KEY,
  trace_kind     text NOT NULL,
  schema_hash    text NOT NULL,
  payload        jsonb NOT NULL,
  payload_sha256 text NOT NULL,
  record_time    timestamptz NOT NULL DEFAULT now(),
  tenant_ref     text COLLATE "C" NOT NULL,
  runtime_bundle_digest text COLLATE "C" NOT NULL,
  FOREIGN KEY (tenant_ref, runtime_bundle_digest)
    REFERENCES runtime_bundle(tenant_ref, bundle_digest)
);

DROP TRIGGER IF EXISTS trg_runtime_trace_append_only ON runtime_trace;
CREATE TRIGGER trg_runtime_trace_append_only
  BEFORE UPDATE OR DELETE ON runtime_trace
  FOR EACH STATEMENT EXECUTE FUNCTION kernel_forbid_mutation();

-- frozen export artifacts (DocumentAssembly documents): durable, append-only,
-- digest-addressed so a later inspection can verify the handed-over artifact
-- against the store (views/VIEWS.md "Identification").
CREATE TABLE IF NOT EXISTS export_artifact (
  artifact_ref       text PRIMARY KEY,
  digest             text NOT NULL,
  metadata_record_id text NOT NULL,
  document           jsonb NOT NULL,
  record_time        timestamptz NOT NULL DEFAULT now(),
  tenant_ref         text COLLATE "C" NOT NULL,
  runtime_bundle_digest text COLLATE "C" NOT NULL,
  FOREIGN KEY (tenant_ref, runtime_bundle_digest)
    REFERENCES runtime_bundle(tenant_ref, bundle_digest)
);

DROP TRIGGER IF EXISTS trg_export_artifact_append_only ON export_artifact;
CREATE TRIGGER trg_export_artifact_append_only
  BEFORE UPDATE OR DELETE ON export_artifact
  FOR EACH STATEMENT EXECUTE FUNCTION kernel_forbid_mutation();
