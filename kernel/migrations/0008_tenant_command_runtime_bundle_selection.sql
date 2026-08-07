-- Admit one immutable tenant-owned RuntimeBundle selection for the governed
-- COMMIT_OPERATION_CLAIM_DRAFT command.  This migration provides storage and
-- one closed control transition only; it adds no runtime read or command path.
-- Binding: ofarm.tenant-command-runtime-bundle-selection.commit-operation-claim-draft.v0.1

DO $migration$
DECLARE
    verifier_source pg_catalog.text;
    allocator_source pg_catalog.text;
BEGIN
    SELECT routine.prosrc
      INTO STRICT verifier_source
      FROM pg_catalog.pg_proc AS routine
     WHERE routine.oid =
            'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure;
    IF pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(verifier_source, 'UTF8')),
            'hex'
       ) <> 'bd284674029103c05677d2de8a564ef3d0b7113a895e070ecffef7dc49fb6931'
       OR pg_catalog.strpos(
            verifier_source, 'observed_migration_count <> 7'
          ) = 0
       OR pg_catalog.strpos(
            verifier_source,
            'sha256:fcc0e96b4520ffe51ddb5537df24040e4d5948a22b3c387351346cc588e87ee5'
          ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-7 tenant verifier source differs';
    END IF;

    SELECT routine.prosrc
      INTO STRICT allocator_source
      FROM pg_catalog.pg_proc AS routine
     WHERE routine.oid =
            'ofarm.allocate_tenant_knowledge_position()'::pg_catalog.regprocedure;
    IF pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(allocator_source, 'UTF8')),
            'hex'
       ) <> '1522e46edbf80c0ee0e3ba61f0713a6f36c5ced82d1b61ac9e0acdfa49506b5f'
       OR pg_catalog.strpos(
            allocator_source,
            'IF SESSION_USER IN (''ofarm_app'', ''ofarm_worker'') THEN'
          ) = 0
       OR pg_catalog.strpos(
            allocator_source,
            'pre-binding tenant genesis is unsupported'
          ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-7 tenant knowledge allocator differs';
    END IF;
END
$migration$;

ALTER TABLE ofarm.governed_write_batch
    ADD CONSTRAINT governed_write_batch_selection_provenance_key UNIQUE (
        tenant_id,
        batch_id,
        knowledge_position,
        runtime_bundle_digest
    );

CREATE TABLE ofarm.tenant_command_runtime_bundle_selection (
    tenant_id pg_catalog.uuid NOT NULL,
    selection_binding_id ofarm.ascii_id NOT NULL,
    selection_binding_canonical_digest ofarm.sha256_id NOT NULL,
    command_id ofarm.ascii_id NOT NULL,
    command_binding_id ofarm.ascii_id NOT NULL,
    command_binding_canonical_digest ofarm.sha256_id NOT NULL,
    runtime_bundle_digest ofarm.sha256_id NOT NULL,
    selection_batch_id ofarm.tenant_local_ref NOT NULL,
    selection_knowledge_position pg_catalog.int8 NOT NULL,
    CONSTRAINT tenant_command_runtime_bundle_selection_pkey PRIMARY KEY (
        tenant_id, selection_binding_id
    ),
    CONSTRAINT tenant_command_runtime_bundle_selection_tenant_fkey
        FOREIGN KEY (tenant_id)
        REFERENCES ofarm.tenant_registry (tenant_id),
    CONSTRAINT tenant_command_runtime_bundle_selection_bundle_fkey
        FOREIGN KEY (tenant_id, runtime_bundle_digest)
        REFERENCES ofarm.runtime_bundle (tenant_id, bundle_digest),
    CONSTRAINT tenant_command_runtime_bundle_selection_batch_fkey
        FOREIGN KEY (
            tenant_id,
            selection_batch_id,
            selection_knowledge_position,
            runtime_bundle_digest
        ) REFERENCES ofarm.governed_write_batch (
            tenant_id,
            batch_id,
            knowledge_position,
            runtime_bundle_digest
        ),
    CONSTRAINT tenant_command_runtime_bundle_selection_binding_check CHECK (
        selection_binding_id::pg_catalog.text =
            'ofarm.tenant-command-runtime-bundle-selection.' ||
            'commit-operation-claim-draft.v0.1'
        AND selection_binding_canonical_digest::pg_catalog.text =
            'sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f'
    ),
    CONSTRAINT tenant_command_runtime_bundle_selection_command_check CHECK (
        command_id::pg_catalog.text = 'COMMIT_OPERATION_CLAIM_DRAFT'
        AND command_binding_id::pg_catalog.text =
            'ofarm.temporal-governed-command.' ||
            'commit-operation-claim-draft.v0.1'
        AND command_binding_canonical_digest::pg_catalog.text =
            'sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1'
    ),
    CONSTRAINT tenant_command_runtime_bundle_selection_position_check CHECK (
        selection_knowledge_position BETWEEN 1 AND 9007199254740991
    )
);

ALTER TABLE ofarm.tenant_command_runtime_bundle_selection
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.tenant_command_runtime_bundle_selection
    FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_command_runtime_bundle_selection_owner
ON ofarm.tenant_command_runtime_bundle_selection
AS PERMISSIVE FOR ALL TO ofarm_owner
USING (
    SESSION_USER = 'ofarm_command_runtime_bundle_selection_control_login'
    AND tenant_id = ofarm.current_tenant_id()
    AND selection_binding_id::pg_catalog.text =
        'ofarm.tenant-command-runtime-bundle-selection.' ||
        'commit-operation-claim-draft.v0.1'
    AND selection_binding_canonical_digest::pg_catalog.text =
        'sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f'
    AND command_id::pg_catalog.text = 'COMMIT_OPERATION_CLAIM_DRAFT'
    AND command_binding_id::pg_catalog.text =
        'ofarm.temporal-governed-command.' ||
        'commit-operation-claim-draft.v0.1'
    AND command_binding_canonical_digest::pg_catalog.text =
        'sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1'
)
WITH CHECK (
    SESSION_USER = 'ofarm_command_runtime_bundle_selection_control_login'
    AND tenant_id = ofarm.current_tenant_id()
    AND selection_binding_id::pg_catalog.text =
        'ofarm.tenant-command-runtime-bundle-selection.' ||
        'commit-operation-claim-draft.v0.1'
    AND selection_binding_canonical_digest::pg_catalog.text =
        'sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f'
    AND command_id::pg_catalog.text = 'COMMIT_OPERATION_CLAIM_DRAFT'
    AND command_binding_id::pg_catalog.text =
        'ofarm.temporal-governed-command.' ||
        'commit-operation-claim-draft.v0.1'
    AND command_binding_canonical_digest::pg_catalog.text =
        'sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1'
);

CREATE POLICY tenant_command_runtime_bundle_activation_owner
ON ofarm.governed_write_batch
AS PERMISSIVE FOR ALL TO ofarm_owner
USING (
    SESSION_USER = 'ofarm_command_runtime_bundle_selection_control_login'
    AND tenant_id = ofarm.current_tenant_id()
)
WITH CHECK (
    SESSION_USER = 'ofarm_command_runtime_bundle_selection_control_login'
    AND tenant_id = ofarm.current_tenant_id()
    AND authenticated_principal_ref::pg_catalog.text =
        ofarm.current_authenticated_principal_ref()
    AND governed_operation::pg_catalog.text =
        'ACTIVATE_COMMAND_RUNTIME_BUNDLE_SELECTION'
    AND batch_id::pg_catalog.text OPERATOR(pg_catalog.~)
        '^selection-batch:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    AND request_id::pg_catalog.text OPERATOR(pg_catalog.~)
        '^selection-request:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    AND knowledge_position BETWEEN 1 AND 9007199254740991
    AND EXISTS (
        SELECT 1
          FROM ofarm.runtime_bundle AS bundle
         WHERE bundle.tenant_id = governed_write_batch.tenant_id
           AND bundle.bundle_digest = governed_write_batch.runtime_bundle_digest
    )
);

CREATE OR REPLACE FUNCTION ofarm.allocate_tenant_knowledge_position()
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

    IF SESSION_USER =
        'ofarm_command_runtime_bundle_selection_control_login' THEN
        IF CURRENT_USER <> 'ofarm_owner' OR NEW.knowledge_position IS NOT NULL THEN
            RAISE EXCEPTION USING ERRCODE = '22023',
                MESSAGE = 'selection knowledge position is database assigned';
        END IF;

        bound_tenant_id := ofarm.current_tenant_id();
        IF NEW.tenant_id IS DISTINCT FROM bound_tenant_id
           OR NEW.authenticated_principal_ref::pg_catalog.text IS DISTINCT FROM
                ofarm.current_authenticated_principal_ref()
           OR NEW.governed_operation::pg_catalog.text IS DISTINCT FROM
                'ACTIVATE_COMMAND_RUNTIME_BUNDLE_SELECTION'
           OR NEW.batch_id::pg_catalog.text OPERATOR(pg_catalog.!~)
                '^selection-batch:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
           OR NEW.request_id::pg_catalog.text OPERATOR(pg_catalog.!~)
                '^selection-request:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
           OR NOT EXISTS (
                SELECT 1
                  FROM ofarm.runtime_bundle AS bundle
                 WHERE bundle.tenant_id = bound_tenant_id
                   AND bundle.bundle_digest = NEW.runtime_bundle_digest
           ) THEN
            RAISE EXCEPTION USING ERRCODE = '42501',
                MESSAGE = 'selection activation batch authority differs';
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

    BEGIN
        SELECT registry.advisory_lock_key
          INTO STRICT fixture_lock_key
          FROM ofarm.tenant_registry AS registry
         WHERE registry.tenant_id = NEW.tenant_id;
    EXCEPTION
        WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
            RAISE EXCEPTION USING ERRCODE = '42501',
                MESSAGE = 'tenant knowledge-position authority is unavailable';
    END;
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
END
$body$;

CREATE FUNCTION
    ofarm.activate_commit_operation_claim_draft_runtime_bundle_selection(
        requested_runtime_bundle_digest pg_catalog.text
    )
RETURNS TABLE (
    selection_batch_id pg_catalog.text,
    selection_knowledge_position pg_catalog.int8,
    runtime_bundle_digest pg_catalog.text
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $body$
DECLARE
    bound_tenant_id pg_catalog.uuid;
    bound_principal_ref pg_catalog.text;
    locked_tenant_id pg_catalog.uuid;
    locked_principal_ref pg_catalog.text;
    selected ofarm.tenant_command_runtime_bundle_selection%ROWTYPE;
    allocated_position pg_catalog.int8;
    generated_batch_id pg_catalog.text;
    generated_request_id pg_catalog.text;
    referenced_batch_exact pg_catalog.bool;
BEGIN
    IF pg_catalog.current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION USING ERRCODE = '25001',
            MESSAGE = 'RuntimeBundle selection requires read committed';
    END IF;
    IF SESSION_USER <>
        'ofarm_command_runtime_bundle_selection_control_login' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'RuntimeBundle selection session differs';
    END IF;

    bound_tenant_id := ofarm.current_tenant_id();
    bound_principal_ref := ofarm.current_authenticated_principal_ref();
    IF requested_runtime_bundle_digest IS NULL
       OR requested_runtime_bundle_digest COLLATE pg_catalog."C"
            OPERATOR(pg_catalog.!~) '^sha256:[0-9a-f]{64}$' THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'selected RuntimeBundle digest is not exact';
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM ofarm.runtime_bundle AS bundle
         WHERE bundle.tenant_id = bound_tenant_id
           AND bundle.bundle_digest::pg_catalog.text =
                requested_runtime_bundle_digest
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'selected same-tenant RuntimeBundle is not sealed';
    END IF;

    PERFORM ofarm.take_tenant_write_lock();
    locked_tenant_id := ofarm.current_tenant_id();
    locked_principal_ref := ofarm.current_authenticated_principal_ref();
    IF locked_tenant_id IS DISTINCT FROM bound_tenant_id
       OR locked_principal_ref IS DISTINCT FROM bound_principal_ref THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'selection tenant binding changed under lock';
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM ofarm.runtime_bundle AS bundle
         WHERE bundle.tenant_id = locked_tenant_id
           AND bundle.bundle_digest::pg_catalog.text =
                requested_runtime_bundle_digest
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'selected same-tenant RuntimeBundle changed under lock';
    END IF;

    SELECT selection.*
      INTO selected
      FROM ofarm.tenant_command_runtime_bundle_selection AS selection
     WHERE selection.tenant_id = locked_tenant_id
       AND selection.selection_binding_id::pg_catalog.text =
            'ofarm.tenant-command-runtime-bundle-selection.' ||
            'commit-operation-claim-draft.v0.1';
    IF FOUND THEN
        SELECT EXISTS (
            SELECT 1
              FROM ofarm.governed_write_batch AS batch
             WHERE batch.tenant_id = selected.tenant_id
               AND batch.batch_id = selected.selection_batch_id
               AND batch.knowledge_position =
                    selected.selection_knowledge_position
               AND batch.runtime_bundle_digest =
                    selected.runtime_bundle_digest
               AND batch.authenticated_principal_ref::pg_catalog.text =
                    locked_principal_ref
               AND batch.governed_operation::pg_catalog.text =
                    'ACTIVATE_COMMAND_RUNTIME_BUNDLE_SELECTION'
               AND batch.request_id::pg_catalog.text
                    OPERATOR(pg_catalog.~)
                    '^selection-request:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        ) INTO STRICT referenced_batch_exact;
        IF selected.selection_binding_canonical_digest::pg_catalog.text <>
                'sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f'
           OR selected.command_id::pg_catalog.text <>
                'COMMIT_OPERATION_CLAIM_DRAFT'
           OR selected.command_binding_id::pg_catalog.text <>
                'ofarm.temporal-governed-command.' ||
                'commit-operation-claim-draft.v0.1'
           OR selected.command_binding_canonical_digest::pg_catalog.text <>
                'sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1'
           OR selected.runtime_bundle_digest::pg_catalog.text <>
                requested_runtime_bundle_digest
           OR NOT referenced_batch_exact THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
                MESSAGE = 'sealed RuntimeBundle selection differs';
        END IF;
        RETURN QUERY SELECT
            selected.selection_batch_id::pg_catalog.text,
            selected.selection_knowledge_position,
            selected.runtime_bundle_digest::pg_catalog.text;
        RETURN;
    END IF;

    generated_batch_id :=
        'selection-batch:' || pg_catalog.gen_random_uuid()::pg_catalog.text;
    generated_request_id :=
        'selection-request:' || pg_catalog.gen_random_uuid()::pg_catalog.text;
    INSERT INTO ofarm.governed_write_batch (
        tenant_id,
        batch_id,
        authenticated_principal_ref,
        governed_operation,
        request_id,
        runtime_bundle_digest
    ) VALUES (
        locked_tenant_id,
        generated_batch_id,
        locked_principal_ref,
        'ACTIVATE_COMMAND_RUNTIME_BUNDLE_SELECTION',
        generated_request_id,
        requested_runtime_bundle_digest
    ) RETURNING knowledge_position INTO STRICT allocated_position;

    INSERT INTO ofarm.tenant_command_runtime_bundle_selection (
        tenant_id,
        selection_binding_id,
        selection_binding_canonical_digest,
        command_id,
        command_binding_id,
        command_binding_canonical_digest,
        runtime_bundle_digest,
        selection_batch_id,
        selection_knowledge_position
    ) VALUES (
        locked_tenant_id,
        'ofarm.tenant-command-runtime-bundle-selection.' ||
            'commit-operation-claim-draft.v0.1',
        'sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f',
        'COMMIT_OPERATION_CLAIM_DRAFT',
        'ofarm.temporal-governed-command.' ||
            'commit-operation-claim-draft.v0.1',
        'sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1',
        requested_runtime_bundle_digest,
        generated_batch_id,
        allocated_position
    );

    RETURN QUERY SELECT
        generated_batch_id,
        allocated_position,
        requested_runtime_bundle_digest;
END
$body$;

REVOKE ALL PRIVILEGES ON FUNCTION
    ofarm.activate_commit_operation_claim_draft_runtime_bundle_selection(
        pg_catalog.text
    )
FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    ofarm.activate_commit_operation_claim_draft_runtime_bundle_selection(
        pg_catalog.text
    )
TO ofarm_command_runtime_bundle_selection_controller;

CREATE TRIGGER tenant_command_runtime_bundle_selection_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE
ON ofarm.tenant_command_runtime_bundle_selection
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();

-- Advance the migration-owned verifier only after every V8 object is exact.
DO $migration$
DECLARE
    verifier_definition pg_catalog.text;
    verifier_source pg_catalog.text;
    routine_fingerprints pg_catalog.text[];
    policy_fingerprints pg_catalog.text[];
    observed_v8_structural_digest pg_catalog.text;
    policy_marker CONSTANT pg_catalog.text :=
        $marker$        SELECT pg_catalog.array_agg(type.typname::pg_catalog.text ORDER BY type.typname)$marker$;
    policy_check pg_catalog.text;
    old_selection_acl CONSTANT pg_catalog.text :=
        $old$        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE NOT (
                       grantee.rolname =
                            'ofarm_command_runtime_bundle_selection_controller'
                       AND grantor.rolname = 'ofarm_binder'
                       AND acl.privilege_type = 'EXECUTE'
                       AND NOT acl.is_grantable
                       AND (
                           (
                               routine.proname = 'create_tenant_challenge'
                               AND pg_catalog.oidvectortypes(
                                       routine.proargtypes
                                   ) = ''
                           )
                           OR
                           (
                               routine.proname = 'bind_tenant_capability'
                               AND pg_catalog.oidvectortypes(
                                       routine.proargtypes
                                   ) = 'text'
                           )
                       )
                   )
               )
          INTO relation_acl_count, invalid_relation_acl_count
          FROM pg_catalog.pg_proc AS routine
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = routine.pronamespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(routine.proacl) AS acl
          JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
          JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
         WHERE namespace.nspname = 'ofarm'
           AND grantee.rolname IN (
                'ofarm_command_runtime_bundle_selection_controller',
                'ofarm_command_runtime_bundle_selection_control_login'
           );
        IF relation_acl_count <> 2 OR invalid_relation_acl_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences,
                'tenant binding selection-control admission ACL differs'
            );
        END IF;

$old$;
    new_selection_acl CONSTANT pg_catalog.text :=
        $new$        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE NOT (
                       grantee.rolname =
                            'ofarm_command_runtime_bundle_selection_controller'
                       AND acl.privilege_type = 'EXECUTE'
                       AND NOT acl.is_grantable
                       AND (
                           (
                               grantor.rolname = 'ofarm_binder'
                               AND (
                                   (
                                       routine.proname = 'create_tenant_challenge'
                                       AND pg_catalog.oidvectortypes(
                                               routine.proargtypes
                                           ) = ''
                                   )
                                   OR
                                   (
                                       routine.proname = 'bind_tenant_capability'
                                       AND pg_catalog.oidvectortypes(
                                               routine.proargtypes
                                           ) = 'text'
                                   )
                               )
                           )
                           OR
                           (
                               grantor.rolname = 'ofarm_owner'
                               AND routine.proname =
                                   'activate_commit_operation_claim_draft_runtime_bundle_selection'
                               AND pg_catalog.oidvectortypes(
                                       routine.proargtypes
                                   ) = 'text'
                           )
                       )
                   )
               )
          INTO relation_acl_count, invalid_relation_acl_count
          FROM pg_catalog.pg_proc AS routine
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = routine.pronamespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(routine.proacl) AS acl
          JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
          JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
         WHERE namespace.nspname = 'ofarm'
           AND grantee.rolname IN (
                'ofarm_command_runtime_bundle_selection_controller',
                'ofarm_command_runtime_bundle_selection_control_login'
           );
        IF relation_acl_count <> 3 OR invalid_relation_acl_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences,
                'tenant binding selection-control admission ACL differs'
            );
        END IF;

$new$;
BEGIN
    SELECT pg_catalog.pg_get_functiondef(routine.oid), routine.prosrc
      INTO STRICT verifier_definition, verifier_source
      FROM pg_catalog.pg_proc AS routine
     WHERE routine.oid =
            'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure;
    IF pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(verifier_source, 'UTF8')),
            'hex'
       ) <> 'bd284674029103c05677d2de8a564ef3d0b7113a895e070ecffef7dc49fb6931'
       OR pg_catalog.strpos(verifier_definition, policy_marker) = 0
       OR pg_catalog.strpos(verifier_definition, old_selection_acl) = 0
       OR pg_catalog.strpos(verifier_definition, new_selection_acl) <> 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-7 tenant verifier definition differs';
    END IF;

    SELECT pg_catalog.array_agg(
               routine.proname::pg_catalog.text || '(' ||
               pg_catalog.pg_get_function_identity_arguments(routine.oid) ||
               ')=' || owner.rolname::pg_catalog.text || ':' ||
               language.lanname::pg_catalog.text || ':' ||
               routine.prosecdef::pg_catalog.text || ':' ||
               routine.proisstrict::pg_catalog.text || ':' ||
               routine.proleakproof::pg_catalog.text || ':' ||
               routine.provolatile::pg_catalog.text || ':' ||
               routine.proparallel::pg_catalog.text || ':' ||
               COALESCE(pg_catalog.array_to_string(routine.proconfig, ','), '') ||
               ':' || pg_catalog.encode(
                    pg_catalog.sha256(
                        pg_catalog.convert_to(routine.prosrc, 'UTF8')
                    ), 'hex'
               ) || ':' || EXISTS (
                    SELECT 1
                      FROM pg_catalog.aclexplode(
                           COALESCE(
                               routine.proacl,
                               pg_catalog.acldefault('f', routine.proowner)
                           )
                      ) AS public_acl
                     WHERE public_acl.grantee = 0
                       AND public_acl.privilege_type = 'EXECUTE'
               )::pg_catalog.text || ':' ||
               pg_catalog.has_function_privilege(
                    'ofarm_app', routine.oid, 'EXECUTE'
               )::pg_catalog.text || ':' ||
               pg_catalog.has_function_privilege(
                    'ofarm_worker', routine.oid, 'EXECUTE'
               )::pg_catalog.text || ':' ||
               pg_catalog.has_function_privilege(
                    'ofarm_owner', routine.oid, 'EXECUTE'
               )::pg_catalog.text || ':' ||
               pg_catalog.has_function_privilege(
                    'ofarm_runtime_bundle_publisher', routine.oid, 'EXECUTE'
               )::pg_catalog.text || ':' ||
               pg_catalog.has_function_privilege(
                    'ofarm_tenant_lock_owner', routine.oid, 'EXECUTE'
               )::pg_catalog.text || ':' ||
               pg_catalog.has_function_privilege(
                    'ofarm_migrator', routine.oid, 'EXECUTE'
               )::pg_catalog.text || ':' ||
               pg_catalog.has_function_privilege(
                    'ofarm_readiness', routine.oid, 'EXECUTE'
               )::pg_catalog.text
               ORDER BY routine.proname
           )
      INTO STRICT routine_fingerprints
      FROM pg_catalog.pg_proc AS routine
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = routine.pronamespace
      JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
      JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
     WHERE namespace.nspname = 'ofarm'
       AND routine.proname IN (
            'activate_commit_operation_claim_draft_runtime_bundle_selection',
            'allocate_tenant_knowledge_position'
       );
    IF pg_catalog.array_length(routine_fingerprints, 1) <> 2 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-8 sealed routine inventory differs';
    END IF;

    SELECT pg_catalog.array_agg(
               class.relname::pg_catalog.text || ':' ||
               policy.polname::pg_catalog.text || ':' ||
               policy.polpermissive::pg_catalog.text || ':' ||
               policy.polcmd::pg_catalog.text || ':' ||
               pg_catalog.array_to_string(
                   ARRAY(
                       SELECT CASE WHEN policy_role.oid = 0 THEN 'PUBLIC'
                                   ELSE governed_role.rolname::pg_catalog.text END
                         FROM pg_catalog.unnest(
                              policy.polroles
                         ) AS policy_role(oid)
                         LEFT JOIN pg_catalog.pg_roles AS governed_role
                           ON governed_role.oid = policy_role.oid
                        ORDER BY (
                            CASE WHEN policy_role.oid = 0 THEN 'PUBLIC'
                                 ELSE governed_role.rolname::pg_catalog.text END
                        ) COLLATE pg_catalog."C"
                   ), ','
               ) || ':' ||
               pg_catalog.pg_get_expr(policy.polqual, policy.polrelid) || ':' ||
               pg_catalog.pg_get_expr(policy.polwithcheck, policy.polrelid)
               ORDER BY class.relname, policy.polname
           )
      INTO STRICT policy_fingerprints
      FROM pg_catalog.pg_policy AS policy
      JOIN pg_catalog.pg_class AS class ON class.oid = policy.polrelid
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = class.relnamespace
     WHERE namespace.nspname = 'ofarm'
       AND policy.polname IN (
            'tenant_command_runtime_bundle_activation_owner',
            'tenant_command_runtime_bundle_selection_owner'
       );
    IF pg_catalog.array_length(policy_fingerprints, 1) <> 2 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-8 selection policy inventory differs';
    END IF;

    SELECT observation.structural_catalog_digest
      INTO STRICT observed_v8_structural_digest
      FROM ofarm.verify_tenant_structure() AS observation;

    policy_check := pg_catalog.format(
        $check$        SELECT pg_catalog.array_agg(
                   class.relname::pg_catalog.text || ':' ||
                   policy.polname::pg_catalog.text || ':' ||
                   policy.polpermissive::pg_catalog.text || ':' ||
                   policy.polcmd::pg_catalog.text || ':' ||
                   pg_catalog.array_to_string(
                       ARRAY(
                           SELECT CASE WHEN policy_role.oid = 0 THEN 'PUBLIC'
                                       ELSE governed_role.rolname::pg_catalog.text END
                             FROM pg_catalog.unnest(
                                  policy.polroles
                             ) AS policy_role(oid)
                             LEFT JOIN pg_catalog.pg_roles AS governed_role
                               ON governed_role.oid = policy_role.oid
                            ORDER BY (
                                CASE WHEN policy_role.oid = 0 THEN 'PUBLIC'
                                     ELSE governed_role.rolname::pg_catalog.text END
                            ) COLLATE pg_catalog."C"
                       ), ','
                   ) || ':' ||
                   pg_catalog.pg_get_expr(policy.polqual, policy.polrelid) || ':' ||
                   pg_catalog.pg_get_expr(policy.polwithcheck, policy.polrelid)
                   ORDER BY class.relname, policy.polname
               )
          INTO observed_routines
          FROM pg_catalog.pg_policy AS policy
          JOIN pg_catalog.pg_class AS class ON class.oid = policy.polrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = class.relnamespace
         WHERE namespace.nspname = 'ofarm'
           AND policy.polname IN (
                'tenant_command_runtime_bundle_activation_owner',
                'tenant_command_runtime_bundle_selection_owner'
           );
        IF observed_routines IS DISTINCT FROM %L::pg_catalog.text[] THEN
            differences := pg_catalog.array_append(
                differences, 'tenant command RuntimeBundle selection policies differ'
            );
        END IF;

$check$,
        policy_fingerprints
    );

    verifier_definition := pg_catalog.replace(
        verifier_definition,
        $old$            'tenant_capability_verification_key',
            'tenant_registry'$old$,
        $new$            'tenant_capability_verification_key',
            'tenant_command_runtime_bundle_selection',
            'tenant_registry'$new$
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        $old$            'runtime_tenant_content_blob',
            'runtime_trace'
        ]::pg_catalog.text[];$old$,
        $new$            'runtime_tenant_content_blob',
            'runtime_trace',
            'tenant_command_runtime_bundle_selection'
        ]::pg_catalog.text[];$new$
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        $old$            'tenant_capability_verification_key:r:p:ofarm_owner:false:false',
            'tenant_registry:r:p:ofarm_owner:false:false'$old$,
        $new$            'tenant_capability_verification_key:r:p:ofarm_owner:false:false',
            'tenant_command_runtime_bundle_selection:r:p:ofarm_owner:true:true',
            'tenant_registry:r:p:ofarm_owner:false:false'$new$
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        $old$         WHERE namespace.nspname = 'ofarm';
        IF policy_count <> 14 OR invalid_policy_count <> 0 THEN$old$,
        $new$         WHERE namespace.nspname = 'ofarm'
           AND policy.polname NOT IN (
                'tenant_command_runtime_bundle_activation_owner',
                'tenant_command_runtime_bundle_selection_owner'
           );
        IF policy_count <> 14 OR invalid_policy_count <> 0 THEN$new$
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, policy_marker, policy_check || policy_marker
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, old_selection_acl, new_selection_acl
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        $old$'create_tenant_challenge',$old$,
        $new$'activate_commit_operation_claim_draft_runtime_bundle_selection',
                 'allocate_tenant_knowledge_position',
                 'create_tenant_challenge',$new$
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        $old$        IF observed_routines IS DISTINCT FROM ARRAY[
            'create_tenant_challenge()=$old$,
        '        IF observed_routines IS DISTINCT FROM ARRAY[' ||
        pg_catalog.chr(10) || '            ' ||
        pg_catalog.quote_literal(routine_fingerprints[1]) || ',' ||
        pg_catalog.chr(10) || '            ' ||
        pg_catalog.quote_literal(routine_fingerprints[2]) || ',' ||
        pg_catalog.chr(10) ||
        $new$            'create_tenant_challenge()=$new$
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'IF guarded_relation_count <> 19 THEN',
        'IF guarded_relation_count <> 20 THEN'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'FILTER (WHERE migration.version = 7)',
        'FILTER (WHERE migration.version = 8)'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'observed_migration_count <> 7',
        'observed_migration_count <> 8'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'observed_head_version <> 7',
        'observed_head_version <> 8'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'sha256:fcc0e96b4520ffe51ddb5537df24040e4d5948a22b3c387351346cc588e87ee5',
        observed_v8_structural_digest
    );
    EXECUTE verifier_definition;
END
$migration$;
