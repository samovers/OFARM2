-- Admit only ofarm_owner to the two existing binder-owned current-context
-- readers for issue #176.
--
-- Fresh provisioning owns the one-use V6 grant capsule. This migration changes
-- only the final tenant structural verifier. The runner appends and authenticates
-- the complete V6 ledger row before it consumes the closed capsule that creates
-- the two binder-attributed grants.

DO $migration$
DECLARE
    verifier_definition pg_catalog.text;
    verifier_source pg_catalog.text;
    old_principal_routine_fragment CONSTANT pg_catalog.text :=
        $routine$'current_authenticated_principal_ref()=ofarm_binder:plpgsql:true:false:false:s:u:search_path=pg_catalog, pg_temp:6b0b3abc610609988a965cb7b8671603b0c8bdd8fde62d5aafdc465507182df7:false:true:true:false:false:false:false:false'$routine$;
    new_principal_routine_fragment CONSTANT pg_catalog.text :=
        $routine$'current_authenticated_principal_ref()=ofarm_binder:plpgsql:true:false:false:s:u:search_path=pg_catalog, pg_temp:6b0b3abc610609988a965cb7b8671603b0c8bdd8fde62d5aafdc465507182df7:false:true:true:true:false:false:false:false'$routine$;
    old_tenant_routine_fragment CONSTANT pg_catalog.text :=
        $routine$'current_tenant_id()=ofarm_binder:plpgsql:true:false:false:s:u:search_path=pg_catalog, pg_temp:2dea636af9e5cd14b7fcb406fd556934ffd8ab408dae965aa318e4120beb0ab0:false:true:true:false:false:true:false:false'$routine$;
    new_tenant_routine_fragment CONSTANT pg_catalog.text :=
        $routine$'current_tenant_id()=ofarm_binder:plpgsql:true:false:false:s:u:search_path=pg_catalog, pg_temp:2dea636af9e5cd14b7fcb406fd556934ffd8ab408dae965aa318e4120beb0ab0:false:true:true:true:false:true:false:false'$routine$;
    routine_inventory_marker CONSTANT pg_catalog.text :=
        $marker$        SELECT pg_catalog.array_agg(
                   routine.proname::pg_catalog.text || '('$marker$;
    current_context_acl_check CONSTANT pg_catalog.text :=
        $check$        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE NOT (
                       grantor.rolname = 'ofarm_binder'
                       AND acl.privilege_type = 'EXECUTE'
                       AND NOT acl.is_grantable
                       AND (
                           (
                               routine.proname =
                                    'current_authenticated_principal_ref'
                               AND pg_catalog.oidvectortypes(
                                       routine.proargtypes
                                   ) = ''
                               AND grantee.rolname IN (
                                    'ofarm_app',
                                    'ofarm_binder',
                                    'ofarm_owner',
                                    'ofarm_worker'
                               )
                           )
                           OR
                           (
                               routine.proname = 'current_tenant_id'
                               AND pg_catalog.oidvectortypes(
                                       routine.proargtypes
                                   ) = ''
                               AND grantee.rolname IN (
                                    'ofarm_app',
                                    'ofarm_binder',
                                    'ofarm_graph_validator',
                                    'ofarm_owner',
                                    'ofarm_tenant_lock_owner',
                                    'ofarm_worker'
                               )
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
           AND routine.proname IN (
                'current_authenticated_principal_ref',
                'current_tenant_id'
           )
           AND pg_catalog.oidvectortypes(routine.proargtypes) = '';
        IF relation_acl_count <> 10 OR invalid_relation_acl_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences,
                'tenant current-context selection-owner admission ACL differs'
            );
        END IF;

$check$;
BEGIN
    SELECT pg_catalog.pg_get_functiondef(routine.oid), routine.prosrc
      INTO STRICT verifier_definition, verifier_source
      FROM pg_catalog.pg_proc AS routine
     WHERE routine.oid =
            'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure;
    IF pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(verifier_source, 'UTF8')),
            'hex'
       ) <> '0764ffc7734db60f150f3ef722a0409a5b8f738b61e5f2618d1a78778672c618'
       OR pg_catalog.strpos(
            verifier_definition, old_principal_routine_fragment
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition, new_principal_routine_fragment
          ) <> 0
       OR pg_catalog.strpos(
            verifier_definition, old_tenant_routine_fragment
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition, new_tenant_routine_fragment
          ) <> 0
       OR pg_catalog.strpos(verifier_definition, routine_inventory_marker) = 0
       OR pg_catalog.strpos(
            verifier_definition, current_context_acl_check
          ) <> 0
       OR pg_catalog.strpos(
            verifier_definition,
            'tenant binding selection-control admission ACL differs'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition, 'observed_migration_count <> 5'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition, 'observed_head_version <> 5'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition,
            'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 5)'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition,
            'sha256:383a646365a29c5e4c487a6defc8f4a6aa40ca7019f1baa9882d855afa73c602'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition,
            'sha256:e15a5d5903681e2796c70ca2cac19b1aa85d3538589f99046a01c3663f5d8556'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition, 'observed_migration_count <> 6'
          ) <> 0
       OR pg_catalog.strpos(
            verifier_definition,
            'sha256:54a86af2f0dfc5573a81de6e40b99e4f347f87fdf7a43b03a60e45e80e455fa9'
          ) <> 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-5 tenant verifier source differs';
    END IF;

    verifier_definition := pg_catalog.replace(
        verifier_definition,
        old_principal_routine_fragment,
        new_principal_routine_fragment
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        old_tenant_routine_fragment,
        new_tenant_routine_fragment
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        routine_inventory_marker,
        current_context_acl_check || routine_inventory_marker
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, 'observed_migration_count <> 5',
        'observed_migration_count <> 6'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, 'observed_head_version <> 5',
        'observed_head_version <> 6'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 5)',
        'pg_catalog.max(migration.applied_prefix_digest) ' ||
        'FILTER (WHERE migration.version = 6)'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'sha256:383a646365a29c5e4c487a6defc8f4a6aa40ca7019f1baa9882d855afa73c602',
        'sha256:b8f5c3ed14d0347493bdf09e0d2e355ecf5feb361189b87f69194b92ac57b3b9'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'sha256:e15a5d5903681e2796c70ca2cac19b1aa85d3538589f99046a01c3663f5d8556',
        'sha256:54a86af2f0dfc5573a81de6e40b99e4f347f87fdf7a43b03a60e45e80e455fa9'
    );
    EXECUTE verifier_definition;
END
$migration$;
