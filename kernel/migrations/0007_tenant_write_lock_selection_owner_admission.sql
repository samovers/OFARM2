-- Admit only ofarm_owner to the existing tenant write-lock wrapper for issue
-- #176. Fresh provisioning owns the one-use V7 custody capsule. This migration
-- changes only the final tenant structural verifier.

DO $migration$
DECLARE
    verifier_definition pg_catalog.text;
    verifier_source pg_catalog.text;
    old_routine_fragment CONSTANT pg_catalog.text :=
        $routine$'take_tenant_write_lock()=ofarm_tenant_lock_owner:plpgsql:true:false:false:v:u:search_path=pg_catalog, pg_temp:38c75f051ee82b75c2e872fe2e191874e17984da7183add568f481d2eadb0de8:false:true:true:false:false:true:false:false'$routine$;
    new_routine_fragment CONSTANT pg_catalog.text :=
        $routine$'take_tenant_write_lock()=ofarm_tenant_lock_owner:plpgsql:true:false:false:v:u:search_path=pg_catalog, pg_temp:38c75f051ee82b75c2e872fe2e191874e17984da7183add568f481d2eadb0de8:false:true:true:true:false:true:false:false'$routine$;
    routine_inventory_marker CONSTANT pg_catalog.text :=
        $marker$        SELECT pg_catalog.array_agg(
                   routine.proname::pg_catalog.text || '(' ||
                   pg_catalog.pg_get_function_identity_arguments(routine.oid)$marker$;
    write_lock_acl_check CONSTANT pg_catalog.text :=
        $check$        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE NOT (
                       grantor.rolname = 'ofarm_tenant_lock_owner'
                       AND acl.privilege_type = 'EXECUTE'
                       AND NOT acl.is_grantable
                       AND grantee.rolname IN (
                            'ofarm_app',
                            'ofarm_owner',
                            'ofarm_tenant_lock_owner',
                            'ofarm_worker'
                       )
                   )
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
          JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
          JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
         WHERE namespace.nspname = 'ofarm'
           AND routine.proname = 'take_tenant_write_lock'
           AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = '';
        IF relation_acl_count <> 4 OR invalid_relation_acl_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences,
                'tenant write-lock selection-owner admission ACL differs'
            );
        END IF;

$check$;
    old_migration_count CONSTANT pg_catalog.text :=
        'observed_migration_count <> 6';
    new_migration_count CONSTANT pg_catalog.text :=
        'observed_migration_count <> 7';
    old_head_version CONSTANT pg_catalog.text :=
        'observed_head_version <> 6';
    new_head_version CONSTANT pg_catalog.text :=
        'observed_head_version <> 7';
    old_prefix_expression CONSTANT pg_catalog.text :=
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 6)';
    new_prefix_expression CONSTANT pg_catalog.text :=
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 7)';
    old_catalog_digest CONSTANT pg_catalog.text :=
        'sha256:b8f5c3ed14d0347493bdf09e0d2e355ecf5feb361189b87f69194b92ac57b3b9';
    new_catalog_digest CONSTANT pg_catalog.text :=
        'sha256:fcc0e96b4520ffe51ddb5537df24040e4d5948a22b3c387351346cc588e87ee5';
    old_provisioning_digest CONSTANT pg_catalog.text :=
        'sha256:54a86af2f0dfc5573a81de6e40b99e4f347f87fdf7a43b03a60e45e80e455fa9';
    new_provisioning_digest CONSTANT pg_catalog.text :=
        'sha256:2ac8487b64d4fb09d7576ef1ee09ac1f2a3cc5b20558f0d2137620b897c7157c';
BEGIN
    SELECT pg_catalog.pg_get_functiondef(routine.oid), routine.prosrc
      INTO STRICT verifier_definition, verifier_source
      FROM pg_catalog.pg_proc AS routine
     WHERE routine.oid =
            'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure;
    IF pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(verifier_source, 'UTF8')),
            'hex'
       ) <> '08ea1a64626bcb129eecec0bcc3476341c64022d26a43c3b268d0f721b41ba73'
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(verifier_definition, old_routine_fragment, '')
          ) <> pg_catalog.length(old_routine_fragment)
       OR pg_catalog.strpos(verifier_definition, new_routine_fragment) <> 0
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(verifier_definition, routine_inventory_marker, '')
          ) <> pg_catalog.length(routine_inventory_marker)
       OR pg_catalog.strpos(verifier_definition, write_lock_acl_check) <> 0
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
       OR pg_catalog.strpos(verifier_definition, new_prefix_expression) <> 0
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(verifier_definition, old_catalog_digest, '')
          ) <> pg_catalog.length(old_catalog_digest)
       OR pg_catalog.strpos(verifier_definition, new_catalog_digest) <> 0
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(
                verifier_definition, old_provisioning_digest, ''
            )
          ) <> pg_catalog.length(old_provisioning_digest)
       OR pg_catalog.strpos(
            verifier_definition, new_provisioning_digest
          ) <> 0
       OR pg_catalog.strpos(
            verifier_definition,
            'tenant binding selection-control admission ACL differs'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition,
            'tenant current-context selection-owner admission ACL differs'
          ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-6 tenant verifier source differs';
    END IF;

    verifier_definition := pg_catalog.replace(
        verifier_definition, old_routine_fragment, new_routine_fragment
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        routine_inventory_marker,
        write_lock_acl_check || routine_inventory_marker
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
        verifier_definition, old_catalog_digest, new_catalog_digest
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, old_provisioning_digest, new_provisioning_digest
    );
    EXECUTE verifier_definition;
END
$migration$;
