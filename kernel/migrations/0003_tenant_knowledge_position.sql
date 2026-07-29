-- Tenant knowledge-position storage for issue #176 boundary 2.
--
-- The append-only governed_write_batch ledger is the only committed head.
-- Runtime allocation is tenant-bound and serialized by the existing protected
-- tenant transaction lock.  The only unbound posture is the separately
-- approved target-admin conformance genesis at position 1.

DO $migration$
BEGIN
    -- The migration owner is intentionally subject to FORCE ROW LEVEL
    -- SECURITY, whose runtime-only policies would otherwise hide every
    -- existing batch. Both posture changes and the guard execute inside this
    -- one DO statement, so even an unsupported autocommit invocation cannot
    -- leave FORCE disabled after refusal. The supported migration runner also
    -- keeps the ACCESS EXCLUSIVE lock through the complete migration.
    EXECUTE 'ALTER TABLE ofarm.governed_write_batch ' ||
            'NO FORCE ROW LEVEL SECURITY';
    IF EXISTS (SELECT 1 FROM ofarm.governed_write_batch) THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'tenant knowledge-position migration requires an empty batch ledger';
    END IF;
    EXECUTE 'ALTER TABLE ofarm.governed_write_batch ' ||
            'FORCE ROW LEVEL SECURITY';
END
$migration$;

ALTER TABLE ofarm.governed_write_batch
    ADD COLUMN knowledge_position pg_catalog.int8 NOT NULL,
    ADD CONSTRAINT governed_write_batch_knowledge_position_check
        CHECK (
            knowledge_position BETWEEN 1 AND 9007199254740991
        ),
    ADD CONSTRAINT governed_write_batch_knowledge_position_key
        UNIQUE (tenant_id, knowledge_position);

CREATE FUNCTION ofarm.allocate_tenant_knowledge_position()
RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $body$
DECLARE
    bound_tenant_id pg_catalog.uuid;
    committed_head pg_catalog.int8;
    fixture_lock_key pg_catalog.int8;
    caller_is_superuser pg_catalog.bool;
BEGIN
    IF pg_catalog.current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION USING ERRCODE = '25001',
            MESSAGE = 'tenant knowledge allocation requires read committed';
    END IF;

    IF SESSION_USER IN ('ofarm_app', 'ofarm_worker') THEN
        IF NEW.knowledge_position IS NOT NULL THEN
            RAISE EXCEPTION USING ERRCODE = '22023',
                MESSAGE = 'runtime knowledge position is database assigned';
        END IF;

        bound_tenant_id := ofarm.current_tenant_id();
        IF NEW.tenant_id IS DISTINCT FROM bound_tenant_id
           OR NEW.authenticated_principal_ref::pg_catalog.text IS DISTINCT FROM
                ofarm.current_authenticated_principal_ref() THEN
            RAISE EXCEPTION USING ERRCODE = '42501',
                MESSAGE = 'governed batch binding differs';
        END IF;

        PERFORM ofarm.take_tenant_write_lock();
        SELECT COALESCE(pg_catalog.max(batch.knowledge_position), 0)
          INTO STRICT committed_head
          FROM ofarm.governed_write_batch AS batch
         WHERE batch.tenant_id = bound_tenant_id;

        IF committed_head >= 9007199254740991 THEN
            RAISE EXCEPTION USING ERRCODE = '22003',
                MESSAGE = 'tenant knowledge position is exhausted';
        END IF;
        NEW.knowledge_position := committed_head + 1;
        RETURN NEW;
    END IF;

    SELECT role.rolsuper
      INTO STRICT caller_is_superuser
      FROM pg_catalog.pg_roles AS role
     WHERE role.rolname = SESSION_USER;
    IF NOT caller_is_superuser
       OR NEW.governed_operation::pg_catalog.text <> 'AUTHORITY_BOOTSTRAP'
       OR NEW.knowledge_position IS DISTINCT FROM 1 THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'pre-binding tenant genesis is unsupported';
    END IF;

    SELECT registry.advisory_lock_key
      INTO STRICT fixture_lock_key
      FROM ofarm.tenant_registry AS registry
     WHERE registry.tenant_id = NEW.tenant_id;
    PERFORM pg_catalog.pg_advisory_xact_lock(fixture_lock_key);
    IF EXISTS (
        SELECT 1
          FROM ofarm.governed_write_batch AS batch
         WHERE batch.tenant_id = NEW.tenant_id
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23505',
            MESSAGE = 'tenant genesis batch already exists',
            CONSTRAINT = 'governed_write_batch_knowledge_position_key';
    END IF;
    RETURN NEW;
EXCEPTION
    WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'tenant knowledge-position authority is unavailable';
END
$body$;

REVOKE ALL PRIVILEGES ON FUNCTION
    ofarm.allocate_tenant_knowledge_position()
FROM PUBLIC;

CREATE TRIGGER governed_write_batch_allocate_knowledge_position
BEFORE INSERT ON ofarm.governed_write_batch
FOR EACH ROW EXECUTE FUNCTION ofarm.allocate_tenant_knowledge_position();

-- Advance the migration-head checks and freeze the additive catalog.
DO $migration$
DECLARE
    verifier pg_catalog.text;
BEGIN
    SELECT pg_catalog.pg_get_functiondef(
        'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure
    ) INTO STRICT verifier;
    IF pg_catalog.strpos(verifier, 'observed_migration_count <> 2') = 0
       OR pg_catalog.strpos(verifier, 'observed_head_version <> 2') = 0
       OR pg_catalog.strpos(
            verifier,
            'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 2)'
          ) = 0
       OR pg_catalog.strpos(
            verifier,
            'sha256:897001ea090224da95746e9de94a6f0098c8a2eae01abab68ac1f32b6509e950'
          ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-2 tenant verifier source differs';
    END IF;
    verifier := pg_catalog.replace(
        verifier, 'observed_migration_count <> 2',
        'observed_migration_count <> 3'
    );
    verifier := pg_catalog.replace(
        verifier, 'observed_head_version <> 2',
        'observed_head_version <> 3'
    );
    verifier := pg_catalog.replace(
        verifier,
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 2)',
        'pg_catalog.max(migration.applied_prefix_digest) ' ||
        'FILTER (WHERE migration.version = 3)'
    );
    verifier := pg_catalog.replace(
        verifier,
        'sha256:897001ea090224da95746e9de94a6f0098c8a2eae01abab68ac1f32b6509e950',
        'sha256:e501479c20111d914e74a6b41b826f5b459e65e9be2ff90d36dcda29f03c2826'
    );
    EXECUTE verifier;
END
$migration$;
