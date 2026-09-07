-- Expose only the original UUID and time of the caller's current CHALLENGE.
-- Creation, consumption, expiry policy and sealed binder custody do not change.
-- Decision: OFARM2-TENANT-CHALLENGE-OBSERVATION-001 version 1; Delivery #375.

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
       ) <> '8af1cd56b249145440eca1d68b6f1d3da105e697f1dec5c6d324b7a8b709fc22' THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-10 tenant verifier source differs';
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
       OR observed_head_version <> 10
       OR observed_migration_count <> 10
       OR observed_prefix_digest <>
            'sha256:bd80785f567e593edea9f88898c18cc8b8269bc8d71eb5aa385c595abc9d7b95'
       OR observed_structural_digest !~ '^sha256:[0-9a-f]{64}$' THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-10 tenant structure differs';
    END IF;
END
$migration$;

CREATE FUNCTION ofarm.current_tenant_challenge()
RETURNS TABLE (
    challenge_id pg_catalog.uuid,
    challenge_created_at_unix_microseconds pg_catalog.int8
)
LANGUAGE plpgsql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $body$
DECLARE
    observed_full_xid pg_catalog.xid8;
BEGIN
    observed_full_xid := pg_catalog.pg_current_xact_id_if_assigned();
    IF observed_full_xid IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'current tenant challenge is unavailable';
    END IF;

    SELECT context.challenge_id,
           (extract(epoch FROM context.challenge_created_at) *
                1000000)::pg_catalog.int8
      INTO STRICT challenge_id, challenge_created_at_unix_microseconds
      FROM ofarm.tenant_binding_context AS context
     WHERE context.backend_pid = pg_catalog.pg_backend_pid()
       AND context.full_xid = observed_full_xid
       AND context.context_state = 'CHALLENGE';
    RETURN NEXT;
EXCEPTION
    WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'current tenant challenge is unavailable';
END
$body$;

ALTER FUNCTION ofarm.current_tenant_challenge() OWNER TO ofarm_owner;
REVOKE ALL PRIVILEGES ON FUNCTION ofarm.current_tenant_challenge() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ofarm.current_tenant_challenge()
TO ofarm_app, ofarm_worker;

-- Preserve the existing verifier and add this reader to its exact routine
-- inventory. Its complete catalog digest also covers return columns, ACLs,
-- function properties and all other catalog state. The verifier's own source
-- is deliberately excluded from that digest, as in the preceding migrations.
DO $migration$
DECLARE
    verifier_definition pg_catalog.text;
    verifier_source pg_catalog.text;
    observed_v10_structural_digest pg_catalog.text;
    observed_v11_structural_digest pg_catalog.text;
    old_routine_names CONSTANT pg_catalog.text :=
        $old$                'current_authenticated_principal_ref',
                'current_tenant_id',$old$;
    new_routine_names CONSTANT pg_catalog.text :=
        $new$                'current_authenticated_principal_ref',
                'current_tenant_challenge',
                'current_tenant_id',$new$;
    routine_fingerprint_marker CONSTANT pg_catalog.text :=
        $marker$            'current_tenant_id()=$marker$;
    reader_fingerprint CONSTANT pg_catalog.text :=
        'current_tenant_challenge()=ofarm_owner:plpgsql:true:false:false:s:u:search_path=pg_catalog, pg_temp:5b89d7be932f143a5a680b8aa328ae3f2a5bfe040dd13f9b36fe908c04732d7b:false:true:true:true:false:false:false:false';
    old_migration_count CONSTANT pg_catalog.text :=
        'observed_migration_count <> 10';
    new_migration_count CONSTANT pg_catalog.text :=
        'observed_migration_count <> 11';
    old_head_version CONSTANT pg_catalog.text :=
        'observed_head_version <> 10';
    new_head_version CONSTANT pg_catalog.text :=
        'observed_head_version <> 11';
    old_prefix_expression CONSTANT pg_catalog.text :=
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 10)';
    new_prefix_expression CONSTANT pg_catalog.text :=
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 11)';
BEGIN
    SELECT pg_catalog.pg_get_functiondef(routine.oid), routine.prosrc
      INTO STRICT verifier_definition, verifier_source
      FROM pg_catalog.pg_proc AS routine
     WHERE routine.oid =
            'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure;
    IF pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(verifier_source, 'UTF8')),
            'hex'
       ) <> '8af1cd56b249145440eca1d68b6f1d3da105e697f1dec5c6d324b7a8b709fc22'
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(verifier_definition, old_routine_names, '')
          ) <> pg_catalog.length(old_routine_names)
       OR pg_catalog.strpos(verifier_definition, 'current_tenant_challenge') <> 0
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(
                verifier_definition, routine_fingerprint_marker, ''
            )
          ) <> pg_catalog.length(routine_fingerprint_marker)
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
            MESSAGE = 'version-10 tenant verifier definition differs';
    END IF;

    SELECT observation.structural_catalog_digest
      INTO STRICT observed_v11_structural_digest
      FROM ofarm.verify_tenant_structure() AS observation;
    SELECT expected.expected_digest
      INTO STRICT observed_v10_structural_digest
      FROM (
        SELECT match[1]::pg_catalog.text AS expected_digest
          FROM pg_catalog.regexp_matches(
                verifier_source,
                'observed_structural_catalog_digest <>[[:space:]]*''(sha256:[0-9a-f]{64})'''
          ) AS match
      ) AS expected;
    IF observed_v10_structural_digest = observed_v11_structural_digest
       OR observed_v11_structural_digest !~ '^sha256:[0-9a-f]{64}$'
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(
                verifier_definition, observed_v10_structural_digest, ''
            )
          ) <> pg_catalog.length(observed_v10_structural_digest) THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-11 tenant catalog digest derivation differs';
    END IF;

    verifier_definition := pg_catalog.replace(
        verifier_definition, old_routine_names, new_routine_names
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        routine_fingerprint_marker,
        '            ' || pg_catalog.quote_literal(reader_fingerprint) ||
        ',' || pg_catalog.chr(10) || routine_fingerprint_marker
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
        observed_v10_structural_digest,
        observed_v11_structural_digest
    );
    EXECUTE verifier_definition;
END
$migration$;
