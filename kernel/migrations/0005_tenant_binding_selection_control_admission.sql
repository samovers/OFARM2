-- Admit only the isolated command RuntimeBundle selection-control role to the
-- two existing tenant-binding entry points for issue #176.
--
-- The roles, membership, CONNECT, schema USAGE, and one-use grant capsule are
-- fresh-provisioning custody.  This migration changes only the final tenant
-- structural verifier.  The runner appends and authenticates the V5 ledger
-- row before it consumes the closed capsule that creates the binder grants.

DO $migration$
DECLARE
    verifier_definition pg_catalog.text;
    verifier_source pg_catalog.text;
    old_role_fragment CONSTANT pg_catalog.text :=
        $role$'ofarm_capability_key_controller:false:false:false:false:false:false:false:-1',
            'ofarm_crypto_installer:true:false:false:false:false:false:false:-1'$role$;
    new_role_fragment CONSTANT pg_catalog.text :=
        $role$'ofarm_capability_key_controller:false:false:false:false:false:false:false:-1',
            'ofarm_command_runtime_bundle_selection_control_login:false:false:false:false:true:true:false:1',
            'ofarm_command_runtime_bundle_selection_controller:false:false:false:false:false:false:false:-1',
            'ofarm_crypto_installer:true:false:false:false:false:false:false:-1'$role$;
    old_membership_fragment CONSTANT pg_catalog.text :=
        $membership$'ofarm_capability_key_controller>ofarm_capability_key_control_login:true:false:false',
            'ofarm_identity_writer>ofarm_identity_control_login:true:false:false'$membership$;
    new_membership_fragment CONSTANT pg_catalog.text :=
        $membership$'ofarm_capability_key_controller>ofarm_capability_key_control_login:true:false:false',
            'ofarm_command_runtime_bundle_selection_controller>ofarm_command_runtime_bundle_selection_control_login:true:false:false',
            'ofarm_identity_writer>ofarm_identity_control_login:true:false:false'$membership$;
    old_control_role_fragment CONSTANT pg_catalog.text :=
        $control$'ofarm_readiness',
            'ofarm_runtime_bundle_control_login'$control$;
    new_control_role_fragment CONSTANT pg_catalog.text :=
        $control$'ofarm_readiness',
            'ofarm_command_runtime_bundle_selection_control_login',
            'ofarm_command_runtime_bundle_selection_controller',
            'ofarm_runtime_bundle_control_login'$control$;
    routine_inventory_marker CONSTANT pg_catalog.text :=
        $marker$        SELECT pg_catalog.array_agg(
                   routine.proname::pg_catalog.text || '('$marker$;
    selection_acl_check CONSTANT pg_catalog.text :=
        $check$        SELECT pg_catalog.count(*),
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
       ) <> '35a4425d473905311f56d25796a14e917977e3c8724f8180b9a0a0baaa166c23'
       OR pg_catalog.strpos(verifier_definition, old_role_fragment) = 0
       OR pg_catalog.strpos(verifier_definition, new_role_fragment) <> 0
       OR pg_catalog.strpos(verifier_definition, old_membership_fragment) = 0
       OR pg_catalog.strpos(verifier_definition, new_membership_fragment) <> 0
       OR pg_catalog.strpos(verifier_definition, old_control_role_fragment) = 0
       OR pg_catalog.strpos(verifier_definition, new_control_role_fragment) <> 0
       OR pg_catalog.strpos(verifier_definition, routine_inventory_marker) = 0
       OR pg_catalog.strpos(verifier_definition, selection_acl_check) <> 0
       OR pg_catalog.strpos(
            verifier_definition, 'observed_migration_count <> 4'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition, 'observed_head_version <> 4'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition,
            'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 4)'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition,
            'sha256:d4819f6ede7496d42bbae566e8d8a8db76b453108ab3b53cc1a6ef01f8b9fe8f'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition,
            'sha256:87122affe6e45127d33b50bb7ee7cb9e35f5e66d81549bcae821019b3fd15f00'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition, 'observed_migration_count <> 5'
          ) <> 0
       OR pg_catalog.strpos(
            verifier_definition,
            'sha256:e15a5d5903681e2796c70ca2cac19b1aa85d3538589f99046a01c3663f5d8556'
          ) <> 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-4 tenant verifier source differs';
    END IF;

    verifier_definition := pg_catalog.replace(
        verifier_definition, old_role_fragment, new_role_fragment
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, old_membership_fragment, new_membership_fragment
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, old_control_role_fragment, new_control_role_fragment
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        routine_inventory_marker,
        selection_acl_check || routine_inventory_marker
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, 'observed_migration_count <> 4',
        'observed_migration_count <> 5'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, 'observed_head_version <> 4',
        'observed_head_version <> 5'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 4)',
        'pg_catalog.max(migration.applied_prefix_digest) ' ||
        'FILTER (WHERE migration.version = 5)'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'sha256:d4819f6ede7496d42bbae566e8d8a8db76b453108ab3b53cc1a6ef01f8b9fe8f',
        'sha256:383a646365a29c5e4c487a6defc8f4a6aa40ca7019f1baa9882d855afa73c602'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'sha256:87122affe6e45127d33b50bb7ee7cb9e35f5e66d81549bcae821019b3fd15f00',
        'sha256:e15a5d5903681e2796c70ca2cac19b1aa85d3538589f99046a01c3663f5d8556'
    );
    EXECUTE verifier_definition;
END
$migration$;
