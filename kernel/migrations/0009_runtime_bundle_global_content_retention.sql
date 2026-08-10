-- Add one content-addressed, globally inert retention transition for the
-- existing RuntimeBundle publisher capability.  This migration does not seal
-- a bundle, select a tenant RuntimeBundle, or activate runtime behavior.
-- Binding: ofarm.runtime-bundle-global-content-retention-admission.issue176.v0.1

DO $migration$
DECLARE
    verifier_source pg_catalog.text;
    publisher_source pg_catalog.text;
    observed_compatible pg_catalog.bool;
    observed_difference_count pg_catalog.int4;
    observed_v8_structural_digest pg_catalog.text;
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
       ) <> 'e0e0f7f4f2248d33a962da4d94518ce1cf2d96ea87849bb0b842358284722b0a'
       OR pg_catalog.strpos(
            verifier_source, 'observed_migration_count <> 8'
          ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-8 tenant verifier source differs';
    END IF;

    SELECT routine.prosrc
      INTO STRICT publisher_source
      FROM pg_catalog.pg_proc AS routine
     WHERE routine.oid =
            'ofarm.publish_runtime_bundle(uuid,text,jsonb)'::pg_catalog.regprocedure;
    IF pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(publisher_source, 'UTF8')),
            'hex'
       ) <> '64562514679a52766a85f2bb62c9da582bc3e129e0ffb4f48174567f6b797c23' THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-8 RuntimeBundle publisher source differs';
    END IF;

    SELECT observation.structurally_compatible,
           observation.difference_count,
           observation.structural_catalog_digest,
           observation.migration_head_version,
           observation.applied_prefix_digest,
           observation.migration_row_count
      INTO STRICT observed_compatible,
           observed_difference_count,
           observed_v8_structural_digest,
           observed_head_version,
           observed_prefix_digest,
           observed_migration_count
      FROM ofarm.verify_tenant_structure() AS observation;
    IF NOT observed_compatible
       OR observed_difference_count <> 0
       OR observed_head_version <> 8
       OR observed_migration_count <> 8
       OR observed_prefix_digest <>
            'sha256:7231c869066c56f7c642460d33391bab00456daecdb04530b34da7210e8e8a54'
       OR observed_v8_structural_digest !~ '^sha256:[0-9a-f]{64}$' THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-8 tenant structure differs';
    END IF;
END
$migration$;

CREATE FUNCTION ofarm.retain_runtime_content(
    expected_content_digest pg_catalog.text,
    canonical_bytes pg_catalog.bytea
)
RETURNS ofarm.sha256_id
LANGUAGE plpgsql VOLATILE CALLED ON NULL INPUT PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $body$
DECLARE
    derived_byte_length pg_catalog.int8;
    computed_content_digest ofarm.sha256_id;
    retained_bytes pg_catalog.bytea;
    retained_byte_length pg_catalog.int8;
BEGIN
    IF NOT (
        pg_catalog.pg_has_role(
            SESSION_USER, 'ofarm_runtime_bundle_publisher', 'USAGE'
        )
        OR pg_catalog.pg_has_role(SESSION_USER, 'ofarm_owner', 'MEMBER')
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '42501',
            MESSAGE = 'runtime content retention caller is not authorized';
    END IF;

    IF expected_content_digest IS NULL OR canonical_bytes IS NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '22023',
            MESSAGE = 'runtime content retention input is null';
    END IF;
    IF (expected_content_digest COLLATE pg_catalog."C")
            OPERATOR(pg_catalog.!~) '^sha256:[0-9a-f]{64}$' THEN
        RAISE EXCEPTION USING
            ERRCODE = '22023',
            MESSAGE = 'runtime content expected digest is not exact';
    END IF;

    derived_byte_length := pg_catalog.octet_length(canonical_bytes);
    IF derived_byte_length NOT BETWEEN 0 AND 1073741823 THEN
        RAISE EXCEPTION USING
            ERRCODE = '22023',
            MESSAGE = 'runtime content byte length is outside the bound';
    END IF;

    computed_content_digest := (
        'sha256:' OPERATOR(pg_catalog.||)
        pg_catalog.encode(pg_catalog.sha256(canonical_bytes), 'hex')
    )::ofarm.sha256_id;
    IF computed_content_digest::pg_catalog.text <> expected_content_digest THEN
        RAISE EXCEPTION USING
            ERRCODE = '22023',
            MESSAGE = 'runtime content digest does not match supplied bytes';
    END IF;

    INSERT INTO ofarm.runtime_content_blob (
        content_digest,
        canonical_bytes,
        byte_length
    ) VALUES (
        computed_content_digest,
        canonical_bytes,
        derived_byte_length
    )
    ON CONFLICT DO NOTHING;

    BEGIN
        SELECT retained.canonical_bytes, retained.byte_length
          INTO STRICT retained_bytes, retained_byte_length
          FROM ofarm.runtime_content_blob AS retained
         WHERE retained.content_digest = computed_content_digest;
    EXCEPTION
        WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'retained runtime content row is not exact';
    END;

    IF retained_bytes IS DISTINCT FROM canonical_bytes
       OR retained_byte_length IS DISTINCT FROM derived_byte_length THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'retained runtime content row differs';
    END IF;

    RETURN computed_content_digest;
END
$body$;

REVOKE ALL PRIVILEGES ON FUNCTION ofarm.retain_runtime_content(
    pg_catalog.text, pg_catalog.bytea
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ofarm.retain_runtime_content(
    pg_catalog.text, pg_catalog.bytea
) TO ofarm_runtime_bundle_publisher;

-- Advance the migration-owned verifier only after the V9 routine and ACL are
-- exact.  The observed catalog digest is derived from this transaction's
-- concrete PostgreSQL 17 catalog rather than guessed in source.
DO $migration$
DECLARE
    verifier_definition pg_catalog.text;
    verifier_source pg_catalog.text;
    retention_fingerprint pg_catalog.text;
    observed_v8_structural_digest pg_catalog.text;
    observed_v9_structural_digest pg_catalog.text;
    old_routine_names CONSTANT pg_catalog.text :=
        $old$                'publish_runtime_bundle',
                'runtime_bundle_tenant_allowed',$old$;
    new_routine_names CONSTANT pg_catalog.text :=
        $new$                'publish_runtime_bundle',
                'retain_runtime_content',
                'runtime_bundle_tenant_allowed',$new$;
    routine_fingerprint_marker CONSTANT pg_catalog.text :=
        $marker$            'runtime_bundle_tenant_allowed(candidate_tenant_id uuid)=$marker$;
    old_migration_count CONSTANT pg_catalog.text :=
        'observed_migration_count <> 8';
    new_migration_count CONSTANT pg_catalog.text :=
        'observed_migration_count <> 9';
    old_head_version CONSTANT pg_catalog.text :=
        'observed_head_version <> 8';
    new_head_version CONSTANT pg_catalog.text :=
        'observed_head_version <> 9';
    old_prefix_expression CONSTANT pg_catalog.text :=
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 8)';
    new_prefix_expression CONSTANT pg_catalog.text :=
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 9)';
BEGIN
    SELECT pg_catalog.pg_get_functiondef(routine.oid), routine.prosrc
      INTO STRICT verifier_definition, verifier_source
      FROM pg_catalog.pg_proc AS routine
     WHERE routine.oid =
            'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure;
    IF pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(verifier_source, 'UTF8')),
            'hex'
       ) <> 'e0e0f7f4f2248d33a962da4d94518ce1cf2d96ea87849bb0b842358284722b0a'
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
            MESSAGE = 'version-8 tenant verifier definition differs';
    END IF;

    SELECT observation.structural_catalog_digest
      INTO STRICT observed_v9_structural_digest
      FROM ofarm.verify_tenant_structure() AS observation;

    SELECT expected.expected_digest
      INTO STRICT observed_v8_structural_digest
      FROM (
        SELECT match[1]::pg_catalog.text AS expected_digest
          FROM pg_catalog.regexp_matches(
                verifier_source,
                'observed_structural_catalog_digest <>[[:space:]]*''(sha256:[0-9a-f]{64})'''
          ) AS match
      ) AS expected;
    IF observed_v8_structural_digest = observed_v9_structural_digest
       OR observed_v9_structural_digest !~ '^sha256:[0-9a-f]{64}$'
       OR pg_catalog.length(verifier_definition) - pg_catalog.length(
            pg_catalog.replace(
                verifier_definition, observed_v8_structural_digest, ''
            )
          ) <> pg_catalog.length(observed_v8_structural_digest) THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-9 tenant catalog digest derivation differs';
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
      INTO STRICT retention_fingerprint
      FROM pg_catalog.pg_proc AS routine
      JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = routine.pronamespace
      JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
      JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
     WHERE namespace.nspname = 'ofarm'
       AND routine.proname = 'retain_runtime_content'
       AND pg_catalog.pg_get_function_identity_arguments(routine.oid) =
            'expected_content_digest text, canonical_bytes bytea';

    verifier_definition := pg_catalog.replace(
        verifier_definition, old_routine_names, new_routine_names
    );
    verifier_definition := pg_catalog.replace(
        verifier_definition,
        routine_fingerprint_marker,
        '            ' || pg_catalog.quote_literal(retention_fingerprint) ||
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
        observed_v8_structural_digest,
        observed_v9_structural_digest
    );
    EXECUTE verifier_definition;
END
$migration$;
