-- Preserve the accepted version-1 source while adding the immutable
-- principal-binding read privileges required by the production runtime.
--
-- The structural verifier excludes its own source from the catalog digest.
-- Rebuild only that code-owned verifier so its migration-head and final ACL
-- expectations describe this additive release.
CREATE FUNCTION ofarm.resolve_principal_binding_authority(
    requested_equality_policy pg_catalog.text,
    requested_issuer pg_catalog.text,
    requested_subject pg_catalog.text
)
RETURNS TABLE (
    equality_policy pg_catalog.text,
    issuer pg_catalog.text,
    subject pg_catalog.text,
    binding_version_id pg_catalog.uuid,
    binding_version_digest pg_catalog.text,
    lifecycle_head_id pg_catalog.uuid,
    lifecycle_head_digest pg_catalog.text,
    tenant_id pg_catalog.uuid,
    tenant_registration_digest pg_catalog.text,
    party_ref pg_catalog.text,
    party_record_kind pg_catalog.text,
    party_record_id pg_catalog.text,
    party_schema_digest pg_catalog.text,
    party_payload_digest pg_catalog.text,
    party_state pg_catalog.text,
    valid_from pg_catalog.timestamptz,
    valid_until pg_catalog.timestamptz,
    binding_digest_matches pg_catalog.bool
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $resolver$
DECLARE
    act_row ofarm.principal_binding_lifecycle%ROWTYPE;
    expected_sequence pg_catalog.int8 := 0;
    expected_prior_id pg_catalog.uuid;
    expected_prior_digest pg_catalog.text;
    recomputed_digest pg_catalog.text;
    observed_any pg_catalog.bool := false;
    fold_state pg_catalog.text := 'INACTIVE';
    fold_binding_version_id pg_catalog.uuid;
    fold_binding_version_digest pg_catalog.text;
    fold_head_id pg_catalog.uuid;
    fold_head_digest pg_catalog.text;
    observed_at pg_catalog.timestamptz := pg_catalog.clock_timestamp();
BEGIN
    IF SESSION_USER <> 'ofarm_identity_resolver' THEN
        RAISE EXCEPTION USING
            ERRCODE = '42501',
            MESSAGE = 'principal-binding resolver caller differs';
    END IF;
    IF requested_equality_policy <> 'OIDC_EXACT_UTF8_V1'
       OR requested_issuer IS NULL
       OR requested_subject IS NULL THEN
        RETURN;
    END IF;

    FOR act_row IN
        SELECT act.*
          FROM ofarm.principal_binding_lifecycle AS act
         WHERE act.equality_policy = requested_equality_policy
           AND act.issuer::pg_catalog.text = requested_issuer
           AND act.subject::pg_catalog.text = requested_subject
         ORDER BY act.stream_sequence
    LOOP
        observed_any := true;
        recomputed_digest := ofarm.compute_principal_lifecycle_act_digest(
            act_row.equality_policy,
            act_row.issuer::pg_catalog.text,
            act_row.subject::pg_catalog.text,
            act_row.stream_sequence,
            act_row.act_id,
            act_row.act_kind,
            act_row.binding_version_id,
            act_row.binding_version_digest::pg_catalog.text,
            act_row.prior_act_id,
            act_row.prior_act_digest::pg_catalog.text,
            act_row.successor_version_id,
            act_row.successor_version_digest::pg_catalog.text,
            act_row.effective_at,
            act_row.decided_at,
            act_row.accountable_control_ref::pg_catalog.text,
            act_row.reason::pg_catalog.text
        );
        IF act_row.stream_sequence <> expected_sequence + 1
           OR act_row.prior_act_id IS DISTINCT FROM expected_prior_id
           OR act_row.prior_act_digest::pg_catalog.text
                IS DISTINCT FROM expected_prior_digest
           OR act_row.act_digest::pg_catalog.text <> recomputed_digest THEN
            RAISE EXCEPTION USING
                ERRCODE = 'PT001',
                MESSAGE = 'principal lifecycle authority differs';
        END IF;

        PERFORM 1
          FROM ofarm.principal_binding AS binding
         WHERE binding.equality_policy = requested_equality_policy
           AND binding.issuer::pg_catalog.text = requested_issuer
           AND binding.subject::pg_catalog.text = requested_subject
           AND binding.binding_version_id = act_row.binding_version_id
           AND binding.binding_version_digest =
                act_row.binding_version_digest;
        IF NOT FOUND THEN
            RAISE EXCEPTION USING
                ERRCODE = 'PT001',
                MESSAGE = 'principal lifecycle binding differs';
        END IF;

        IF act_row.act_kind = 'ACTIVATE' THEN
            IF fold_state = 'ACTIVE'
               OR act_row.successor_version_id IS NOT NULL
               OR act_row.successor_version_digest IS NOT NULL THEN
                RAISE EXCEPTION USING
                    ERRCODE = 'PT001',
                    MESSAGE = 'principal activation authority differs';
            END IF;
            fold_state := 'ACTIVE';
            fold_binding_version_id := act_row.binding_version_id;
            fold_binding_version_digest :=
                act_row.binding_version_digest::pg_catalog.text;
        ELSIF act_row.act_kind = 'SUPERSEDE' THEN
            IF fold_state <> 'ACTIVE'
               OR act_row.binding_version_id IS DISTINCT FROM
                    fold_binding_version_id
               OR act_row.binding_version_digest::pg_catalog.text
                    IS DISTINCT FROM fold_binding_version_digest
               OR act_row.successor_version_id IS NULL
               OR act_row.successor_version_digest IS NULL THEN
                RAISE EXCEPTION USING
                    ERRCODE = 'PT001',
                    MESSAGE = 'principal supersession authority differs';
            END IF;
            PERFORM 1
              FROM ofarm.principal_binding AS successor
             WHERE successor.equality_policy = requested_equality_policy
               AND successor.issuer::pg_catalog.text = requested_issuer
               AND successor.subject::pg_catalog.text = requested_subject
               AND successor.binding_version_id =
                    act_row.successor_version_id
               AND successor.binding_version_digest =
                    act_row.successor_version_digest;
            IF NOT FOUND THEN
                RAISE EXCEPTION USING
                    ERRCODE = 'PT001',
                    MESSAGE = 'principal successor authority differs';
            END IF;
            fold_binding_version_id := act_row.successor_version_id;
            fold_binding_version_digest :=
                act_row.successor_version_digest::pg_catalog.text;
        ELSIF act_row.act_kind IN ('REVOKE', 'EXPIRE') THEN
            IF fold_state <> 'ACTIVE'
               OR act_row.binding_version_id IS DISTINCT FROM
                    fold_binding_version_id
               OR act_row.binding_version_digest::pg_catalog.text
                    IS DISTINCT FROM fold_binding_version_digest
               OR act_row.successor_version_id IS NOT NULL
               OR act_row.successor_version_digest IS NOT NULL THEN
                RAISE EXCEPTION USING
                    ERRCODE = 'PT001',
                    MESSAGE = 'principal inactivation authority differs';
            END IF;
            fold_state := 'INACTIVE';
            fold_binding_version_id := NULL;
            fold_binding_version_digest := NULL;
        ELSE
            RAISE EXCEPTION USING
                ERRCODE = 'PT001',
                MESSAGE = 'principal lifecycle kind differs';
        END IF;

        expected_sequence := act_row.stream_sequence;
        expected_prior_id := act_row.act_id;
        expected_prior_digest := act_row.act_digest::pg_catalog.text;
        fold_head_id := act_row.act_id;
        fold_head_digest := act_row.act_digest::pg_catalog.text;
    END LOOP;

    IF NOT observed_any OR fold_state <> 'ACTIVE' THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT requested_equality_policy,
           requested_issuer,
           requested_subject,
           binding.binding_version_id,
           binding.binding_version_digest::pg_catalog.text,
           fold_head_id,
           fold_head_digest,
           binding.tenant_id,
           binding.tenant_registration_digest::pg_catalog.text,
           binding.party_ref::pg_catalog.text,
           binding.party_record_kind,
           binding.party_record_id::pg_catalog.text,
           binding.party_schema_digest::pg_catalog.text,
           binding.party_payload_digest::pg_catalog.text,
           binding.party_state,
           binding.valid_from,
           binding.valid_until,
           binding.binding_version_digest::pg_catalog.text =
               ofarm.compute_principal_binding_version_digest(
                   binding.equality_policy,
                   binding.issuer::pg_catalog.text,
                   binding.subject::pg_catalog.text,
                   binding.binding_version_id,
                   binding.tenant_id,
                   binding.tenant_registration_digest::pg_catalog.text,
                   binding.party_ref::pg_catalog.text,
                   binding.party_record_kind,
                   binding.party_record_id::pg_catalog.text,
                   binding.party_schema_digest::pg_catalog.text,
                   binding.party_payload_digest::pg_catalog.text,
                   binding.party_state,
                   binding.valid_from,
                   binding.valid_until,
                   binding.predecessor_version_id
               )
      FROM ofarm.principal_binding AS binding
      JOIN ofarm.tenant_registry AS registry
        ON registry.tenant_id = binding.tenant_id
       AND registry.registration_digest =
           binding.tenant_registration_digest
      JOIN ofarm.kernel_record AS party
        ON party.tenant_id = binding.tenant_id
       AND party.record_id = binding.party_record_id
       AND party.record_kind = binding.party_record_kind
       AND party.schema_digest = binding.party_schema_digest
       AND party.payload_digest = binding.party_payload_digest
       AND party.party_state = binding.party_state
       AND party.party_id = binding.party_ref
     WHERE binding.equality_policy = requested_equality_policy
       AND binding.issuer::pg_catalog.text = requested_issuer
       AND binding.subject::pg_catalog.text = requested_subject
       AND binding.binding_version_id = fold_binding_version_id
       AND binding.binding_version_digest::pg_catalog.text =
           fold_binding_version_digest
       AND binding.party_record_kind = 'ofarm.party.v0.1'
       AND binding.party_record_id = binding.party_ref
       AND binding.party_state = 'ACTIVE'
       AND binding.valid_from <= observed_at
       AND observed_at < binding.valid_until;
END
$resolver$;

CREATE FUNCTION ofarm.check_principal_binding_resolution_dependencies()
RETURNS pg_catalog.text
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $health$
DECLARE
    binder_singleton pg_catalog.bool;
    binder_instance_id pg_catalog.uuid;
    binder_audience pg_catalog.text;
    binder_contract_digest pg_catalog.text;
    binder_database_name pg_catalog.text;
    binder_created_at pg_catalog.timestamptz;
    binder_row_digest pg_catalog.text;
    binding_digest pg_catalog.text;
    lifecycle_digest pg_catalog.text;
BEGIN
    IF SESSION_USER <> 'ofarm_identity_resolver' THEN
        RAISE EXCEPTION USING
            ERRCODE = '42501',
            MESSAGE = 'principal-binding health caller differs';
    END IF;
    IF CURRENT_USER <> 'ofarm_principal_resolver_owner'
       OR NOT EXISTS (
            SELECT 1
              FROM pg_catalog.pg_roles AS owner
              JOIN pg_catalog.pg_proc AS resolver
                ON resolver.oid = (
                    'ofarm.resolve_principal_binding_authority(text,text,text)'
                        ::pg_catalog.regprocedure
                )
              JOIN pg_catalog.pg_proc AS health
                ON health.oid = (
                    'ofarm.check_principal_binding_resolution_dependencies()'
                        ::pg_catalog.regprocedure
                )
             WHERE owner.rolname = 'ofarm_principal_resolver_owner'
               AND NOT owner.rolcanlogin
               AND owner.rolbypassrls
               AND resolver.proowner = owner.oid
               AND health.proowner = owner.oid
               AND resolver.prosecdef
               AND health.prosecdef
       ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '42501',
            MESSAGE = 'principal-binding resolver owner posture differs';
    END IF;
    IF NOT pg_catalog.has_function_privilege(
        SESSION_USER,
        'ofarm.resolve_principal_binding_authority(text,text,text)'
            ::pg_catalog.regprocedure,
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '42501',
            MESSAGE = 'principal-binding resolver execute privilege differs';
    END IF;

    BEGIN
        SELECT instance.singleton,
               instance.instance_id,
               instance.audience,
               instance.contract_digest::pg_catalog.text,
               instance.database_name,
               instance.created_at,
               instance.row_digest::pg_catalog.text
          INTO STRICT binder_singleton,
                      binder_instance_id,
                      binder_audience,
                      binder_contract_digest,
                      binder_database_name,
                      binder_created_at,
                      binder_row_digest
          FROM ofarm.tenant_binder_instance AS instance;
    EXCEPTION
        WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
            RAISE EXCEPTION USING
                ERRCODE = 'PT001',
                MESSAGE = 'tenant binder audience cardinality differs';
    END;
    IF binder_singleton IS DISTINCT FROM true
       OR binder_instance_id IS NULL
       OR binder_instance_id =
            '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
       OR binder_audience IS DISTINCT FROM
            'urn:ofarm:tenant-binder:v1:' ||
            binder_instance_id::pg_catalog.text
       OR binder_contract_digest IS DISTINCT FROM
            'sha256:39e979fa296122cb66d42eae5e2d7c6dc797ac77ef4324515ae1ab6020088d83'
       OR binder_database_name IS DISTINCT FROM
            pg_catalog.current_database()::pg_catalog.text
       OR binder_created_at IS NULL
       OR binder_created_at IN (
            '-infinity'::pg_catalog.timestamptz,
            'infinity'::pg_catalog.timestamptz
       )
       OR binder_row_digest IS DISTINCT FROM
            ofarm.compute_tenant_binder_instance_digest(
                binder_instance_id,
                binder_audience,
                binder_contract_digest,
                binder_database_name,
                binder_created_at
            ) THEN
        RAISE EXCEPTION USING
            ERRCODE = 'PT001',
            MESSAGE = 'tenant binder audience authority differs';
    END IF;

    PERFORM binding.equality_policy,
            binding.issuer,
            binding.subject,
            binding.binding_version_id,
            binding.binding_version_digest,
            binding.tenant_id,
            binding.tenant_registration_digest,
            binding.party_ref,
            binding.party_record_kind,
            binding.party_record_id,
            binding.party_schema_digest,
            binding.party_payload_digest,
            binding.party_state,
            binding.valid_from,
            binding.valid_until,
            binding.predecessor_version_id
      FROM ofarm.principal_binding AS binding
     WHERE false;
    PERFORM act.equality_policy,
            act.issuer,
            act.subject,
            act.stream_sequence,
            act.act_id,
            act.act_digest,
            act.act_kind,
            act.binding_version_id,
            act.binding_version_digest,
            act.prior_act_id,
            act.prior_act_digest,
            act.successor_version_id,
            act.successor_version_digest,
            act.effective_at,
            act.decided_at,
            act.accountable_control_ref,
            act.reason
      FROM ofarm.principal_binding_lifecycle AS act
     WHERE false;
    PERFORM registry.tenant_id,
            registry.registration_digest
      FROM ofarm.tenant_registry AS registry
     WHERE false;
    PERFORM party.tenant_id,
            party.record_id,
            party.record_kind,
            party.schema_digest,
            party.payload_digest,
            party.party_state,
            party.party_id
      FROM ofarm.kernel_record AS party
     WHERE false;
    IF NOT pg_catalog.has_type_privilege(
           CURRENT_USER, 'ofarm.ascii_id', 'USAGE'
       )
       OR NOT pg_catalog.has_type_privilege(
           CURRENT_USER, 'ofarm.oidc_issuer', 'USAGE'
       )
       OR NOT pg_catalog.has_type_privilege(
           CURRENT_USER, 'ofarm.oidc_subject', 'USAGE'
       )
       OR NOT pg_catalog.has_type_privilege(
           CURRENT_USER, 'ofarm.sha256_id', 'USAGE'
       )
       OR NOT pg_catalog.has_type_privilege(
           CURRENT_USER, 'ofarm.tenant_local_ref', 'USAGE'
       ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '42501',
            MESSAGE = 'principal-binding resolver type privilege differs';
    END IF;
    PERFORM NULL::ofarm.ascii_id,
            NULL::ofarm.oidc_issuer,
            NULL::ofarm.oidc_subject,
            NULL::ofarm.sha256_id,
            NULL::ofarm.tenant_local_ref;

    binding_digest := ofarm.compute_principal_binding_version_digest(
        'OIDC_EXACT_UTF8_V1',
        'https://principal-binding-health.invalid',
        'health-subject',
        '00000000-0000-0000-0000-000000000001'::pg_catalog.uuid,
        '00000000-0000-0000-0000-000000000002'::pg_catalog.uuid,
        'sha256:1111111111111111111111111111111111111111111111111111111111111111',
        'health-party',
        'ofarm.party.v0.1',
        'health-party',
        'sha256:2222222222222222222222222222222222222222222222222222222222222222',
        'sha256:3333333333333333333333333333333333333333333333333333333333333333',
        'ACTIVE',
        '2000-01-01 00:00:00+00'::pg_catalog.timestamptz,
        '2100-01-01 00:00:00+00'::pg_catalog.timestamptz,
        NULL::pg_catalog.uuid
    );
    lifecycle_digest := ofarm.compute_principal_lifecycle_act_digest(
        'OIDC_EXACT_UTF8_V1',
        'https://principal-binding-health.invalid',
        'health-subject',
        1,
        '00000000-0000-0000-0000-000000000003'::pg_catalog.uuid,
        'ACTIVATE',
        '00000000-0000-0000-0000-000000000001'::pg_catalog.uuid,
        binding_digest,
        NULL::pg_catalog.uuid,
        NULL::pg_catalog.text,
        NULL::pg_catalog.uuid,
        NULL::pg_catalog.text,
        '2000-01-01 00:00:00+00'::pg_catalog.timestamptz,
        '2000-01-01 00:00:01+00'::pg_catalog.timestamptz,
        'health-control',
        'health-check'
    );
    IF binding_digest !~ '^sha256:[0-9a-f]{64}$'
       OR lifecycle_digest !~ '^sha256:[0-9a-f]{64}$' THEN
        RAISE EXCEPTION USING
            ERRCODE = 'PT001',
            MESSAGE = 'principal-binding health digest differs';
    END IF;
    RETURN binder_audience;
END
$health$;

REVOKE ALL PRIVILEGES ON FUNCTION
    ofarm.resolve_principal_binding_authority(
        pg_catalog.text, pg_catalog.text, pg_catalog.text
    ),
    ofarm.check_principal_binding_resolution_dependencies()
FROM PUBLIC;
GRANT CREATE ON SCHEMA ofarm TO ofarm_principal_resolver_owner;
GRANT EXECUTE ON FUNCTION
    ofarm.resolve_principal_binding_authority(
        pg_catalog.text, pg_catalog.text, pg_catalog.text
    ),
    ofarm.check_principal_binding_resolution_dependencies()
TO ofarm_identity_resolver;
ALTER FUNCTION
    ofarm.resolve_principal_binding_authority(
        pg_catalog.text, pg_catalog.text, pg_catalog.text
    )
OWNER TO ofarm_principal_resolver_owner;
ALTER FUNCTION
    ofarm.check_principal_binding_resolution_dependencies()
OWNER TO ofarm_principal_resolver_owner;
REVOKE CREATE ON SCHEMA ofarm FROM ofarm_principal_resolver_owner;
GRANT SELECT ON TABLE
    ofarm.tenant_binder_instance,
    ofarm.principal_binding,
    ofarm.principal_binding_lifecycle,
    ofarm.tenant_registry
TO ofarm_principal_resolver_owner;
GRANT SELECT (
    tenant_id, record_id, record_kind, schema_digest, payload_digest,
    party_state, party_id
) ON TABLE ofarm.kernel_record TO ofarm_principal_resolver_owner;
GRANT USAGE ON TYPE
    ofarm.ascii_id,
    ofarm.oidc_issuer,
    ofarm.oidc_subject,
    ofarm.sha256_id,
    ofarm.tenant_local_ref
TO ofarm_principal_resolver_owner;
GRANT EXECUTE ON FUNCTION
    ofarm.lp32(pg_catalog.bytea),
    ofarm.valid_ascii_id(pg_catalog.text),
    ofarm.valid_oidc_issuer(pg_catalog.text),
    ofarm.compute_tenant_binder_instance_digest(
        pg_catalog.uuid, pg_catalog.text, pg_catalog.text,
        pg_catalog.text, pg_catalog.timestamptz
    ),
    ofarm.compute_principal_binding_version_digest(
        pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.uuid,
        pg_catalog.uuid, pg_catalog.text, pg_catalog.text, pg_catalog.text,
        pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.text,
        pg_catalog.timestamptz, pg_catalog.timestamptz, pg_catalog.uuid
    ),
    ofarm.compute_principal_lifecycle_act_digest(
        pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.int8,
        pg_catalog.uuid, pg_catalog.text, pg_catalog.uuid, pg_catalog.text,
        pg_catalog.uuid, pg_catalog.text, pg_catalog.uuid, pg_catalog.text,
        pg_catalog.timestamptz, pg_catalog.timestamptz,
        pg_catalog.text, pg_catalog.text
    )
TO ofarm_principal_resolver_owner;

REVOKE ALL PRIVILEGES ON TABLE
    ofarm.tenant_binder_instance,
    ofarm.principal_binding,
    ofarm.principal_binding_lifecycle,
    ofarm.tenant_registry,
    ofarm.kernel_record
FROM ofarm_identity_resolver;
REVOKE ALL PRIVILEGES ON FUNCTION
    ofarm.lp32(pg_catalog.bytea),
    ofarm.valid_ascii_id(pg_catalog.text),
    ofarm.valid_oidc_issuer(pg_catalog.text),
    ofarm.compute_tenant_binder_instance_digest(
        pg_catalog.uuid, pg_catalog.text, pg_catalog.text,
        pg_catalog.text, pg_catalog.timestamptz
    ),
    ofarm.compute_principal_binding_version_digest(
        pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.uuid,
        pg_catalog.uuid, pg_catalog.text, pg_catalog.text, pg_catalog.text,
        pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.text,
        pg_catalog.timestamptz, pg_catalog.timestamptz, pg_catalog.uuid
    ),
    ofarm.compute_principal_lifecycle_act_digest(
        pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.int8,
        pg_catalog.uuid, pg_catalog.text, pg_catalog.uuid, pg_catalog.text,
        pg_catalog.uuid, pg_catalog.text, pg_catalog.uuid, pg_catalog.text,
        pg_catalog.timestamptz, pg_catalog.timestamptz,
        pg_catalog.text, pg_catalog.text
    )
FROM ofarm_identity_resolver;

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
           'pg_catalog.max(migration.provisioning_spec_digest)'
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
        'sha256:87122affe6e45127d33b50bb7ee7cb9e35f5e66d81549bcae821019b3fd15f00',
        'sha256:02bbcef56dcdc1e4d3c0d359b817aec4e41b1611d19238a3ec17ad8c5db31237'
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        'pg_catalog.max(migration.provisioning_spec_digest)',
        'pg_catalog.max(migration.provisioning_spec_digest) FILTER (WHERE migration.version = 2)'
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        'pg_catalog.max(migration.applied_prefix_digest)',
        'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 2)'
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        'sha256:f7c72a008792173e110b9359006271fea263b3e26fb53c8ac6303839d0460fc4',
        'sha256:60accbf4e3fc16669cfc58f142e25000129bdb1f9fff11f6188c69637de4124c'
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        $roles$'ofarm_identity_control_login:false:false:false:false:true:true:false:1',
            'ofarm_identity_writer:false:false:false:false:false:false:false:-1'$roles$,
        $roles$'ofarm_identity_control_login:false:false:false:false:true:true:false:1',
            'ofarm_identity_resolver:false:false:false:false:true:false:false:8',
            'ofarm_identity_writer:false:false:false:false:false:false:false:-1'$roles$
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        $roles$'ofarm_owner:false:false:false:false:false:false:false:-1',
            'ofarm_readiness:false:false:false:false:true:true:false:2'$roles$,
        $roles$'ofarm_owner:false:false:false:false:false:false:false:-1',
            'ofarm_principal_resolver_owner:false:false:false:false:false:false:true:-1',
            'ofarm_readiness:false:false:false:false:true:true:false:2'$roles$
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        $memberships$'ofarm_owner>ofarm_migrator:false:true:false',
            'ofarm_runtime_bundle_publisher>ofarm_runtime_bundle_control_login:true:false:false'$memberships$,
        $memberships$'ofarm_owner>ofarm_migrator:false:true:false',
            'ofarm_principal_resolver_owner>ofarm_owner:false:true:false',
            'ofarm_runtime_bundle_publisher>ofarm_runtime_bundle_control_login:true:false:false'$memberships$
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        'relation_acl_count <> 88',
        'relation_acl_count <> 92'
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        $relation_acl$                       OR
                       (
                           grantee.rolname = 'ofarm_admission_lock_owner'$relation_acl$,
        $relation_acl$                       OR
                       (
                           grantee.rolname = 'ofarm_principal_resolver_owner'
                           AND class.relname IN (
                                'tenant_binder_instance',
                                'principal_binding',
                                'principal_binding_lifecycle',
                                'tenant_registry'
                           )
                           AND acl.privilege_type = 'SELECT'
                       )
                       OR
                       (
                           grantee.rolname = 'ofarm_admission_lock_owner'$relation_acl$
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        'column_acl_count <> 42',
        'column_acl_count <> 49'
    );
    revised_definition := pg_catalog.replace(
        revised_definition,
        $column_acl$grantee.rolname IN (
                                'ofarm_binder', 'ofarm_admission_lock_owner'
                           )$column_acl$,
        $column_acl$grantee.rolname IN (
                                'ofarm_binder', 'ofarm_admission_lock_owner',
                                'ofarm_principal_resolver_owner'
                           )$column_acl$
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
