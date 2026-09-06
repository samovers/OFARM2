-- Admit one tenant-bound, read-only resolver for the already persisted fixed
-- COMMIT_OPERATION_CLAIM_DRAFT RuntimeBundle selection.  This migration adds
-- no selection write, activation, command, authorization, audit, or output.
-- Decision: OFARM2-ISSUE363-TRUSTED-COMMAND-RUNTIME-BUNDLE-SELECTOR-001 v1

DO $migration$
DECLARE
    verifier_source pg_catalog.text;
    observed_compatible pg_catalog.bool;
    observed_difference_count pg_catalog.int4;
    observed_structural_digest pg_catalog.text;
    observed_head_version pg_catalog.int4;
    observed_prefix_digest pg_catalog.text;
    observed_migration_count pg_catalog.int8;
BEGIN
    SELECT routine.prosrc
      INTO STRICT verifier_source
      FROM pg_catalog.pg_proc AS routine
     WHERE routine.oid =
            'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure;
    IF pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(verifier_source, 'UTF8')),
            'hex'
       ) <> 'ab446a52b0940f4da17221d966a8c98a7448f76d0d541750bde387880783d250'
       OR pg_catalog.strpos(
            verifier_source, 'observed_migration_count <> 9'
          ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-9 tenant verifier source differs';
    END IF;

    SELECT observation.structurally_compatible,
           observation.difference_count,
           observation.structural_catalog_digest,
           observation.migration_head_version,
           observation.applied_prefix_digest,
           observation.migration_row_count
      INTO STRICT observed_compatible,
           observed_difference_count,
           observed_structural_digest,
           observed_head_version,
           observed_prefix_digest,
           observed_migration_count
      FROM ofarm.verify_tenant_structure() AS observation;
    IF NOT observed_compatible
       OR observed_difference_count <> 0
       OR observed_head_version <> 9
       OR observed_migration_count <> 9
       OR observed_prefix_digest <>
            'sha256:cef599a81bda42f84c6c9718845b245ecfa7d97564f5c132b0f12dda526d1293'
       OR observed_structural_digest !~ '^sha256:[0-9a-f]{64}$' THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-9 tenant structure differs';
    END IF;
END
$migration$;

CREATE POLICY tenant_command_runtime_bundle_selection_runtime_reader_owner
ON ofarm.tenant_command_runtime_bundle_selection
AS PERMISSIVE FOR SELECT TO ofarm_owner
USING (
    SESSION_USER IN ('ofarm_app', 'ofarm_worker')
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

CREATE POLICY tenant_command_runtime_bundle_head_runtime_reader_owner
ON ofarm.governed_write_batch
AS PERMISSIVE FOR SELECT TO ofarm_owner
USING (
    SESSION_USER IN ('ofarm_app', 'ofarm_worker')
    AND tenant_id = ofarm.current_tenant_id()
);

CREATE FUNCTION
    ofarm.resolve_commit_operation_claim_draft_runtime_bundle_selection()
RETURNS TABLE (
    tenant_id pg_catalog.uuid,
    tenant_ref pg_catalog.text,
    selection_binding_id pg_catalog.text,
    selection_binding_canonical_digest pg_catalog.text,
    command_id pg_catalog.text,
    command_binding_id pg_catalog.text,
    command_binding_canonical_digest pg_catalog.text,
    selection_batch_id pg_catalog.text,
    selection_knowledge_position pg_catalog.int8,
    runtime_bundle_digest pg_catalog.text,
    selection_knowledge_cut pg_catalog.int8
)
LANGUAGE plpgsql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $body$
BEGIN
    IF pg_catalog.current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION USING ERRCODE = '25001',
            MESSAGE = 'RuntimeBundle resolution requires read committed';
    END IF;
    IF SESSION_USER NOT IN ('ofarm_app', 'ofarm_worker')
       OR CURRENT_USER <> 'ofarm_owner' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'RuntimeBundle resolution session differs';
    END IF;

    RETURN QUERY
    WITH protected_tenant AS MATERIALIZED (
        SELECT ofarm.current_tenant_id() AS tenant_id
    ),
    bound_tenant AS MATERIALIZED (
        SELECT protected.tenant_id,
               registry.tenant_ref::pg_catalog.text AS tenant_ref
          FROM protected_tenant AS protected
          JOIN ofarm.tenant_registry AS registry
            ON registry.tenant_id = protected.tenant_id
    ),
    visible_head AS MATERIALIZED (
        SELECT pg_catalog.max(batch.knowledge_position) AS knowledge_cut
          FROM bound_tenant AS bound
          JOIN ofarm.governed_write_batch AS batch
            ON batch.tenant_id = bound.tenant_id
    )
    SELECT bound.tenant_id,
           bound.tenant_ref,
           selected.selection_binding_id::pg_catalog.text,
           selected.selection_binding_canonical_digest::pg_catalog.text,
           selected.command_id::pg_catalog.text,
           selected.command_binding_id::pg_catalog.text,
           selected.command_binding_canonical_digest::pg_catalog.text,
           selected.selection_batch_id::pg_catalog.text,
           selected.selection_knowledge_position,
           selected.runtime_bundle_digest::pg_catalog.text,
           head.knowledge_cut
      FROM bound_tenant AS bound
      JOIN ofarm.tenant_command_runtime_bundle_selection AS selected
        ON selected.tenant_id = bound.tenant_id
       AND selected.selection_binding_id::pg_catalog.text =
            'ofarm.tenant-command-runtime-bundle-selection.' ||
            'commit-operation-claim-draft.v0.1'
       AND selected.selection_binding_canonical_digest::pg_catalog.text =
            'sha256:56fb0f14a2514b34428841cb7bfc8681bb577ea3ecf57598be480683fb68524f'
       AND selected.command_id::pg_catalog.text =
            'COMMIT_OPERATION_CLAIM_DRAFT'
       AND selected.command_binding_id::pg_catalog.text =
            'ofarm.temporal-governed-command.' ||
            'commit-operation-claim-draft.v0.1'
       AND selected.command_binding_canonical_digest::pg_catalog.text =
            'sha256:6dad47b836b737c8d58b38f566ed0a7d6caeba9023a734357320326630309da1'
      JOIN ofarm.governed_write_batch AS activation
        ON activation.tenant_id = selected.tenant_id
       AND activation.batch_id = selected.selection_batch_id
       AND activation.knowledge_position =
            selected.selection_knowledge_position
       AND activation.runtime_bundle_digest = selected.runtime_bundle_digest
       AND activation.governed_operation::pg_catalog.text =
            'ACTIVATE_COMMAND_RUNTIME_BUNDLE_SELECTION'
       AND activation.batch_id::pg_catalog.text OPERATOR(pg_catalog.~)
            '^selection-batch:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
       AND activation.request_id::pg_catalog.text OPERATOR(pg_catalog.~)
            '^selection-request:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
      CROSS JOIN visible_head AS head
     WHERE selected.selection_knowledge_position BETWEEN 1 AND head.knowledge_cut
       AND head.knowledge_cut BETWEEN 1 AND 9007199254740991
       AND NOT EXISTS (
            SELECT 1
              FROM ofarm.governed_write_batch AS current_batch
             WHERE current_batch.tenant_id = bound.tenant_id
               AND current_batch.full_xid =
                    pg_catalog.pg_current_xact_id_if_assigned()
       );
END
$body$;

ALTER FUNCTION
    ofarm.resolve_commit_operation_claim_draft_runtime_bundle_selection()
OWNER TO ofarm_owner;
REVOKE ALL PRIVILEGES ON FUNCTION
    ofarm.resolve_commit_operation_claim_draft_runtime_bundle_selection()
FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    ofarm.resolve_commit_operation_claim_draft_runtime_bundle_selection()
TO ofarm_app, ofarm_worker;

-- Advance the migration-owned verifier only after the V10 routine, policies,
-- ACL, and their concrete PostgreSQL 17 fingerprints are exact.
DO $migration$
DECLARE
    verifier_definition pg_catalog.text;
    verifier_source pg_catalog.text;
    resolver_fingerprint pg_catalog.text;
    policy_fingerprints pg_catalog.text[];
    reader_check pg_catalog.text;
    observed_v9_structural_digest pg_catalog.text;
    observed_v10_structural_digest pg_catalog.text;
    old_routine_names CONSTANT pg_catalog.text :=
        $old$                'publish_runtime_bundle',
                'retain_runtime_content',
                'runtime_bundle_tenant_allowed',$old$;
    new_routine_names CONSTANT pg_catalog.text :=
        $new$                'publish_runtime_bundle',
                'resolve_commit_operation_claim_draft_runtime_bundle_selection',
                'retain_runtime_content',
                'runtime_bundle_tenant_allowed',$new$;
    routine_fingerprint_marker CONSTANT pg_catalog.text :=
        $marker$            'retain_runtime_content(expected_content_digest text, canonical_bytes bytea)=ofarm_owner:plpgsql:true:false:false:v:u:search_path=pg_catalog, pg_temp:f6af0b45653a8a6df9d63e657ba919524762df66606ebbdcd7467fe53555578d:false:false:false:true:true:false:false:false',$marker$;
    policy_marker CONSTANT pg_catalog.text :=
        $marker$        SELECT pg_catalog.array_agg(type.typname::pg_catalog.text ORDER BY type.typname)$marker$;
    old_policy_exclusion CONSTANT pg_catalog.text :=
        $old$           AND policy.polname NOT IN (
                'tenant_command_runtime_bundle_activation_owner',
                'tenant_command_runtime_bundle_selection_owner'
           );
        IF policy_count <> 14 OR invalid_policy_count <> 0 THEN$old$;
    new_policy_exclusion CONSTANT pg_catalog.text :=
        $new$           AND policy.polname NOT IN (
                'tenant_command_runtime_bundle_activation_owner',
                'tenant_command_runtime_bundle_head_runtime_reader_owner',
                'tenant_command_runtime_bundle_selection_owner',
                'tenant_command_runtime_bundle_selection_runtime_reader_owner'
           );
        IF policy_count <> 14 OR invalid_policy_count <> 0 THEN$new$;
    old_migration_count CONSTANT pg_catalog.text :=
        'observed_migration_count <> 9';
    new_migration_count CONSTANT pg_catalog.text :=
        'observed_migration_count <> 10';
    old_head_version CONSTANT pg_catalog.text :=
        'observed_head_version <> 9';
    new_head_version CONSTANT pg_catalog.text :=
        'observed_head_version <> 10';
    old_prefix_expression CONSTANT pg_catalog.text :=
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 9)';
    new_prefix_expression CONSTANT pg_catalog.text :=
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 10)';
BEGIN
    SELECT pg_catalog.pg_get_functiondef(routine.oid), routine.prosrc
      INTO STRICT verifier_definition, verifier_source
      FROM pg_catalog.pg_proc AS routine
     WHERE routine.oid =
            'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure;
    IF pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(verifier_source, 'UTF8')),
            'hex'
       ) <> 'ab446a52b0940f4da17221d966a8c98a7448f76d0d541750bde387880783d250'
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(verifier_definition, old_routine_names, '')
          ) <> pg_catalog.length(old_routine_names)
       OR pg_catalog.strpos(verifier_definition, new_routine_names) <> 0
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(
                verifier_definition, routine_fingerprint_marker, ''
            )
          ) <> pg_catalog.length(routine_fingerprint_marker)
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(verifier_definition, policy_marker, '')
          ) <> pg_catalog.length(policy_marker)
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(verifier_definition, old_policy_exclusion, '')
          ) <> pg_catalog.length(old_policy_exclusion)
       OR pg_catalog.strpos(verifier_definition, new_policy_exclusion) <> 0
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(verifier_definition, old_migration_count, '')
          ) <> pg_catalog.length(old_migration_count)
       OR pg_catalog.strpos(verifier_definition, new_migration_count) <> 0
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(verifier_definition, old_head_version, '')
          ) <> pg_catalog.length(old_head_version)
       OR pg_catalog.strpos(verifier_definition, new_head_version) <> 0
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(verifier_definition, old_prefix_expression, '')
          ) <> pg_catalog.length(old_prefix_expression)
       OR pg_catalog.strpos(verifier_definition, new_prefix_expression) <> 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-9 tenant verifier definition differs';
    END IF;

    SELECT observation.structural_catalog_digest
      INTO STRICT observed_v10_structural_digest
      FROM ofarm.verify_tenant_structure() AS observation;
    SELECT expected.expected_digest
      INTO STRICT observed_v9_structural_digest
      FROM (
        SELECT match[1]::pg_catalog.text AS expected_digest
          FROM pg_catalog.regexp_matches(
                verifier_source,
                'observed_structural_catalog_digest <>[[:space:]]*''(sha256:[0-9a-f]{64})'''
          ) AS match
      ) AS expected;
    IF observed_v9_structural_digest = observed_v10_structural_digest
       OR observed_v10_structural_digest !~ '^sha256:[0-9a-f]{64}$'
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(
                verifier_definition, observed_v9_structural_digest, ''
            )
          ) <> pg_catalog.length(observed_v9_structural_digest) THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-10 tenant catalog digest derivation differs';
    END IF;

    SELECT routine.proname::pg_catalog.text || '(' ||
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
      INTO STRICT resolver_fingerprint
      FROM pg_catalog.pg_proc AS routine
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = routine.pronamespace
      JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
      JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
     WHERE namespace.nspname = 'ofarm'
       AND routine.proname =
            'resolve_commit_operation_claim_draft_runtime_bundle_selection'
       AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = '';

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
               COALESCE(
                   pg_catalog.pg_get_expr(policy.polqual, policy.polrelid), ''
               ) || ':' ||
               COALESCE(
                   pg_catalog.pg_get_expr(policy.polwithcheck, policy.polrelid), ''
               )
               ORDER BY class.relname, policy.polname
           )
      INTO STRICT policy_fingerprints
      FROM pg_catalog.pg_policy AS policy
      JOIN pg_catalog.pg_class AS class ON class.oid = policy.polrelid
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = class.relnamespace
     WHERE namespace.nspname = 'ofarm'
       AND policy.polname IN (
            'tenant_command_runtime_bundle_head_runtime_reader_owner',
            'tenant_command_runtime_bundle_selection_runtime_reader_owner'
       );
    IF pg_catalog.array_length(policy_fingerprints, 1) <> 2 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-10 runtime reader policy inventory differs';
    END IF;

    reader_check := pg_catalog.format(
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
                   COALESCE(
                       pg_catalog.pg_get_expr(policy.polqual, policy.polrelid), ''
                   ) || ':' ||
                   COALESCE(
                       pg_catalog.pg_get_expr(
                           policy.polwithcheck, policy.polrelid
                       ), ''
                   )
                   ORDER BY class.relname, policy.polname
               )
          INTO observed_routines
          FROM pg_catalog.pg_policy AS policy
          JOIN pg_catalog.pg_class AS class ON class.oid = policy.polrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = class.relnamespace
         WHERE namespace.nspname = 'ofarm'
           AND policy.polname IN (
                'tenant_command_runtime_bundle_head_runtime_reader_owner',
                'tenant_command_runtime_bundle_selection_runtime_reader_owner'
           );
        IF observed_routines IS DISTINCT FROM %L::pg_catalog.text[] THEN
            differences := pg_catalog.array_append(
                differences, 'tenant command RuntimeBundle reader policies differ'
            );
        END IF;

        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE grantee.rolname NOT IN (
                            'ofarm_app', 'ofarm_owner', 'ofarm_worker'
                         )
                      OR grantor.rolname <> 'ofarm_owner'
                      OR acl.privilege_type <> 'EXECUTE'
                      OR acl.is_grantable
               )
          INTO relation_acl_count, invalid_relation_acl_count
          FROM pg_catalog.pg_proc AS routine
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = routine.pronamespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(
               COALESCE(
                   routine.proacl,
                   pg_catalog.acldefault('f', routine.proowner)
               )
          ) AS acl
          LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
          JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
         WHERE namespace.nspname = 'ofarm'
           AND routine.proname =
                'resolve_commit_operation_claim_draft_runtime_bundle_selection'
           AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = '';
        IF relation_acl_count <> 3 OR invalid_relation_acl_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, 'tenant command RuntimeBundle resolver ACL differs'
            );
        END IF;

$check$,
        policy_fingerprints
    );

    verifier_definition := pg_catalog.replace(
        verifier_definition, old_routine_names, new_routine_names
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        routine_fingerprint_marker,
        '            ' || pg_catalog.quote_literal(resolver_fingerprint) ||
        ',' || pg_catalog.chr(10) || routine_fingerprint_marker
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, old_policy_exclusion, new_policy_exclusion
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, policy_marker, reader_check || policy_marker
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, old_migration_count, new_migration_count
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, old_head_version, new_head_version
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, old_prefix_expression, new_prefix_expression
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        observed_v9_structural_digest,
        observed_v10_structural_digest
    );
    EXECUTE verifier_definition;
END
$migration$;
