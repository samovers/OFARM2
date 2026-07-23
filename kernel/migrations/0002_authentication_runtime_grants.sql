-- Preserve the accepted version-1 source while adding the immutable
-- principal-binding read privileges required by the production runtime.
--
-- The structural verifier excludes its own source from the catalog digest.
-- Rebuild only that code-owned verifier so its migration-head and final ACL
-- expectations describe this additive release.
DO $migration$
DECLARE
    verifier_definition pg_catalog.text;
    revised_definition pg_catalog.text;
BEGIN
    SELECT pg_catalog.pg_get_functiondef(
               'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure
           )
      INTO verifier_definition;

    IF pg_catalog.strpos(
           verifier_definition,
           'observed_migration_count <> 1'
       ) = 0
       OR pg_catalog.strpos(
           verifier_definition,
           'observed_head_version <> 1'
       ) = 0
       OR pg_catalog.strpos(
           verifier_definition,
           'migration 0001 ledger identity differs'
       ) = 0
       OR pg_catalog.strpos(
           verifier_definition,
           'pg_catalog.max(migration.applied_prefix_digest)'
       ) = 0
       OR pg_catalog.strpos(
           verifier_definition,
           'sha256:f7c72a008792173e110b9359006271fea263b3e26fb53c8ac6303839d0460fc4'
       ) = 0 THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'version-1 tenant verifier source differs';
    END IF;

    revised_definition := pg_catalog.replace(
        verifier_definition,
        'observed_migration_count <> 1',
        'observed_migration_count <> 2'
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        'observed_head_version <> 1',
        'observed_head_version <> 2'
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        'migration 0001 ledger identity differs',
        'migration ledger identity differs'
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        'pg_catalog.max(migration.applied_prefix_digest)',
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 2)'
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        'sha256:f7c72a008792173e110b9359006271fea263b3e26fb53c8ac6303839d0460fc4',
        'sha256:938fdd790029d2e1200373ad987c62fcf4d30dc85e1442daed2352c9c4583a5c'
    );
    EXECUTE revised_definition;
END
$migration$;

GRANT EXECUTE ON FUNCTION
    ofarm.lp32(pg_catalog.bytea),
    ofarm.compute_principal_binding_version_digest(
        pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.uuid,
        pg_catalog.uuid, pg_catalog.text, pg_catalog.text, pg_catalog.text,
        pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.text,
        pg_catalog.timestamptz, pg_catalog.timestamptz, pg_catalog.uuid
    )
TO ofarm_binder;
