-- Admit the governed-inactive temporal artifact carrier to production tenant
-- RuntimeBundle persistence for issue #176.
--
-- This migration changes only the closed persisted component-role vocabulary.
-- It does not select a temporal artifact, activate one in a RuntimeBundle, or
-- grant a caller any new publication authority.

DO $migration$
DECLARE
    observed_constraint pg_catalog.text;
    publisher_definition pg_catalog.text;
    publisher_source pg_catalog.text;
    verifier_definition pg_catalog.text;
    verifier_source pg_catalog.text;
    old_role_fragment CONSTANT pg_catalog.text :=
        $role$'REFERENCE_SNAPSHOT', 'REFERENCE_SOURCE'$role$;
    new_role_fragment CONSTANT pg_catalog.text :=
        $role$'REFERENCE_SNAPSHOT', 'REFERENCE_SOURCE',
                'TEMPORAL_GOVERNANCE_ARTIFACT'$role$;
BEGIN
    -- All V3 authorities are authenticated before the first catalog change.
    SELECT pg_catalog.pg_get_constraintdef(constraint_row.oid, true)
      INTO STRICT observed_constraint
      FROM pg_catalog.pg_constraint AS constraint_row
     WHERE constraint_row.conname = 'runtime_bundle_component_role_check'
       AND constraint_row.conrelid =
            'ofarm.runtime_bundle_component'::pg_catalog.regclass;
    IF observed_constraint IS DISTINCT FROM
        $constraint$CHECK (component_role = ANY (ARRAY['PROFILE_DESCRIPTOR'::text, 'ACTIVE_MANIFEST'::text, 'PROFILE_INSTANCE'::text, 'PROFILE_POLICY'::text, 'QUERY_SPECIFICATION'::text, 'QUERY_PLAN'::text, 'VIEW_BINDING'::text, 'CONTRACT_SCHEMA'::text, 'DRAFT_CONTRACT_SCHEMA'::text, 'VALIDATOR_SOURCE'::text, 'ADAPTER_SOURCE'::text, 'QUERY_OUTPUT_SOURCE'::text, 'REFERENCE_SNAPSHOT'::text, 'REFERENCE_SOURCE'::text]))$constraint$
    THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-3 RuntimeBundle role constraint differs';
    END IF;

    SELECT pg_catalog.pg_get_functiondef(routine.oid), routine.prosrc
      INTO STRICT publisher_definition, publisher_source
      FROM pg_catalog.pg_proc AS routine
     WHERE routine.oid =
            'ofarm.publish_runtime_bundle(uuid,text,jsonb)'::pg_catalog.regprocedure;
    IF pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(publisher_source, 'UTF8')),
            'hex'
       ) <> '02a4cd5b6d42902ac8e261d3c81e0ddd25dd0493b2e0c360effa99f4cc897441'
       OR pg_catalog.encode(
            pg_catalog.sha256(
                pg_catalog.convert_to(publisher_definition, 'UTF8')
            ),
            'hex'
          ) <> 'a262bf8e351d1ed4fdafcad85b35c50331afa20f0b1c7bcd29469fc9c1fb0c63'
       OR pg_catalog.strpos(publisher_definition, old_role_fragment) = 0
       OR pg_catalog.strpos(
            publisher_definition, 'TEMPORAL_GOVERNANCE_ARTIFACT'
          ) <> 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-3 RuntimeBundle publisher differs';
    END IF;

    SELECT pg_catalog.pg_get_functiondef(routine.oid), routine.prosrc
      INTO STRICT verifier_definition, verifier_source
      FROM pg_catalog.pg_proc AS routine
     WHERE routine.oid =
            'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure;
    IF pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(verifier_source, 'UTF8')),
            'hex'
       ) <> '262c4f76bf1a4ffe3f0fabb262f06b3376d3c173358cd952bea9f87a0db993b5'
       OR pg_catalog.strpos(
            verifier_definition, 'observed_migration_count <> 3'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition, 'observed_head_version <> 3'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition,
            'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 3)'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition,
            '02a4cd5b6d42902ac8e261d3c81e0ddd25dd0493b2e0c360effa99f4cc897441'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition,
            'sha256:a975adc87f7706cffebdaedce8fef761a88bad1b7b7184ba919410e099492a25'
          ) = 0
       OR pg_catalog.strpos(
            verifier_definition, 'observed_migration_count <> 4'
          ) <> 0
       OR pg_catalog.strpos(
            verifier_definition,
            '64562514679a52766a85f2bb62c9da582bc3e129e0ffb4f48174567f6b797c23'
          ) <> 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-3 tenant verifier source differs';
    END IF;

    ALTER TABLE ofarm.runtime_bundle_component
        DROP CONSTRAINT runtime_bundle_component_role_check;
    ALTER TABLE ofarm.runtime_bundle_component
        ADD CONSTRAINT runtime_bundle_component_role_check CHECK (
            component_role IN (
                'PROFILE_DESCRIPTOR', 'ACTIVE_MANIFEST', 'PROFILE_INSTANCE',
                'PROFILE_POLICY', 'QUERY_SPECIFICATION', 'QUERY_PLAN',
                'VIEW_BINDING', 'CONTRACT_SCHEMA', 'DRAFT_CONTRACT_SCHEMA',
                'VALIDATOR_SOURCE', 'ADAPTER_SOURCE', 'QUERY_OUTPUT_SOURCE',
                'REFERENCE_SNAPSHOT', 'REFERENCE_SOURCE',
                'TEMPORAL_GOVERNANCE_ARTIFACT'
            )
        );

    publisher_definition := pg_catalog.replace(
        publisher_definition, old_role_fragment, new_role_fragment
    );
    EXECUTE publisher_definition;

    verifier_definition := pg_catalog.replace(
        verifier_definition, 'observed_migration_count <> 3',
        'observed_migration_count <> 4'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition, 'observed_head_version <> 3',
        'observed_head_version <> 4'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 3)',
        'pg_catalog.max(migration.applied_prefix_digest) ' ||
        'FILTER (WHERE migration.version = 4)'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        '02a4cd5b6d42902ac8e261d3c81e0ddd25dd0493b2e0c360effa99f4cc897441',
        '64562514679a52766a85f2bb62c9da582bc3e129e0ffb4f48174567f6b797c23'
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        'sha256:a975adc87f7706cffebdaedce8fef761a88bad1b7b7184ba919410e099492a25',
        'sha256:d4819f6ede7496d42bbae566e8d8a8db76b453108ab3b53cc1a6ef01f8b9fe8f'
    );
    EXECUTE verifier_definition;
END
$migration$;
