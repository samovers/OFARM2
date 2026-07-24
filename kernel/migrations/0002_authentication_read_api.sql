-- Read-only authentication authority for issue #172.
--
-- These SECURITY DEFINER functions remain owned by the unreachable schema
-- owner.  The application login receives EXECUTE only; it receives no direct
-- authority over identity, tenant, Party, or signing-control relations.

CREATE FUNCTION ofarm.observe_authentication_runtime_contract()
RETURNS TABLE (
    audience pg_catalog.text,
    capability_contract_digest pg_catalog.text,
    api_version pg_catalog.text
)
LANGUAGE plpgsql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $body$
DECLARE
    instance ofarm.tenant_binder_instance%ROWTYPE;
BEGIN
    IF SESSION_USER <> 'ofarm_app' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'authentication contract caller differs';
    END IF;
    BEGIN
        SELECT row.* INTO STRICT instance
          FROM ofarm.tenant_binder_instance AS row
         WHERE row.singleton;
    EXCEPTION WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
        RAISE EXCEPTION USING ERRCODE = 'PT001',
            MESSAGE = 'authentication contract authority differs';
    END;
    IF instance.audience IS DISTINCT FROM
            'urn:ofarm:tenant-binder:v1:' || instance.instance_id::pg_catalog.text
       OR instance.contract_digest::pg_catalog.text IS DISTINCT FROM
            'sha256:39e979fa296122cb66d42eae5e2d7c6dc797ac77ef4324515ae1ab6020088d83'
       OR instance.database_name IS DISTINCT FROM
            pg_catalog.current_database()::pg_catalog.text
       OR instance.row_digest::pg_catalog.text IS DISTINCT FROM
            ofarm.compute_tenant_binder_instance_digest(
                instance.instance_id, instance.audience,
                instance.contract_digest::pg_catalog.text,
                instance.database_name, instance.created_at
            ) THEN
        RAISE EXCEPTION USING ERRCODE = 'PT001',
            MESSAGE = 'authentication contract authority differs';
    END IF;
    RETURN QUERY SELECT instance.audience,
        instance.contract_digest::pg_catalog.text,
        'ofarm.authentication-runtime.v1'::pg_catalog.text;
END
$body$;

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
    valid_until pg_catalog.timestamptz
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $body$
DECLARE
    act ofarm.principal_binding_lifecycle%ROWTYPE;
    binding ofarm.principal_binding%ROWTYPE;
    projected ofarm.principal_binding_current%ROWTYPE;
    registry ofarm.tenant_registry%ROWTYPE;
    expected_sequence pg_catalog.int8 := 0;
    expected_prior_id pg_catalog.uuid;
    expected_prior_digest pg_catalog.text;
    active_id pg_catalog.uuid;
    active_digest pg_catalog.text;
    head_id pg_catalog.uuid;
    head_digest pg_catalog.text;
    observed_at pg_catalog.timestamptz := pg_catalog.clock_timestamp();
BEGIN
    IF SESSION_USER <> 'ofarm_app' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'principal authority caller differs';
    END IF;
    IF requested_equality_policy IS DISTINCT FROM 'OIDC_EXACT_UTF8_V1'
       OR requested_issuer IS NULL OR requested_subject IS NULL THEN
        RETURN;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint AS constraint_row
         WHERE constraint_row.conrelid =
                'ofarm.principal_binding'::pg_catalog.regclass
           AND constraint_row.conname = 'principal_binding_party_fkey'
           AND constraint_row.contype = 'f'
           AND constraint_row.convalidated
           AND pg_catalog.pg_get_constraintdef(constraint_row.oid, false) =
                'FOREIGN KEY (tenant_id, party_record_id, party_record_kind, party_schema_digest, party_payload_digest, party_state, party_payload_party_id) REFERENCES ofarm.kernel_record(tenant_id, record_id, record_kind, schema_digest, payload_digest, party_state, party_id) DEFERRABLE INITIALLY DEFERRED'
    ) THEN
        RAISE EXCEPTION USING ERRCODE = 'PT001',
            MESSAGE = 'principal Party reference authority differs';
    END IF;

    FOR act IN
        SELECT row.* FROM ofarm.principal_binding_lifecycle AS row
         WHERE row.equality_policy = requested_equality_policy
           AND row.issuer::pg_catalog.text COLLATE pg_catalog."C" =
               requested_issuer COLLATE pg_catalog."C"
           AND row.subject::pg_catalog.text COLLATE pg_catalog."C" =
               requested_subject COLLATE pg_catalog."C"
         ORDER BY row.stream_sequence
    LOOP
        IF act.stream_sequence <> expected_sequence + 1
           OR act.prior_act_id IS DISTINCT FROM expected_prior_id
           OR act.prior_act_digest::pg_catalog.text
                IS DISTINCT FROM expected_prior_digest
           OR act.act_digest::pg_catalog.text IS DISTINCT FROM
                ofarm.compute_principal_lifecycle_act_digest(
                    act.equality_policy, act.issuer::pg_catalog.text,
                    act.subject::pg_catalog.text, act.stream_sequence,
                    act.act_id, act.act_kind, act.binding_version_id,
                    act.binding_version_digest::pg_catalog.text,
                    act.prior_act_id, act.prior_act_digest::pg_catalog.text,
                    act.successor_version_id,
                    act.successor_version_digest::pg_catalog.text,
                    act.effective_at, act.decided_at,
                    act.accountable_control_ref::pg_catalog.text,
                    act.reason::pg_catalog.text
                ) THEN
            RAISE EXCEPTION USING ERRCODE = 'PT001',
                MESSAGE = 'principal lifecycle authority differs';
        END IF;
        BEGIN
            SELECT row.* INTO STRICT binding
              FROM ofarm.principal_binding AS row
             WHERE row.equality_policy = requested_equality_policy
               AND row.issuer::pg_catalog.text COLLATE pg_catalog."C" =
                   requested_issuer COLLATE pg_catalog."C"
               AND row.subject::pg_catalog.text COLLATE pg_catalog."C" =
                   requested_subject COLLATE pg_catalog."C"
               AND row.binding_version_id = act.binding_version_id
               AND row.binding_version_digest = act.binding_version_digest;
        EXCEPTION WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
            RAISE EXCEPTION USING ERRCODE = 'PT001',
                MESSAGE = 'principal lifecycle reference differs';
        END;
        IF act.act_kind = 'ACTIVATE' AND active_id IS NULL
           AND act.successor_version_id IS NULL THEN
            active_id := act.binding_version_id;
            active_digest := act.binding_version_digest::pg_catalog.text;
        ELSIF act.act_kind = 'SUPERSEDE'
           AND act.binding_version_id IS NOT DISTINCT FROM active_id
           AND act.binding_version_digest::pg_catalog.text
                IS NOT DISTINCT FROM active_digest
           AND act.successor_version_id IS NOT NULL THEN
            active_id := act.successor_version_id;
            active_digest := act.successor_version_digest::pg_catalog.text;
        ELSIF act.act_kind IN ('REVOKE', 'EXPIRE')
           AND act.binding_version_id IS NOT DISTINCT FROM active_id
           AND act.binding_version_digest::pg_catalog.text
                IS NOT DISTINCT FROM active_digest
           AND act.successor_version_id IS NULL THEN
            active_id := NULL;
            active_digest := NULL;
        ELSE
            RAISE EXCEPTION USING ERRCODE = 'PT001',
                MESSAGE = 'principal lifecycle transition differs';
        END IF;
        expected_sequence := act.stream_sequence;
        expected_prior_id := act.act_id;
        expected_prior_digest := act.act_digest::pg_catalog.text;
        head_id := act.act_id;
        head_digest := act.act_digest::pg_catalog.text;
    END LOOP;
    IF expected_sequence = 0 OR active_id IS NULL THEN
        RETURN;
    END IF;

    BEGIN
        SELECT row.* INTO STRICT projected
          FROM ofarm.principal_binding_current AS row
         WHERE row.equality_policy = requested_equality_policy
           AND row.issuer::pg_catalog.text COLLATE pg_catalog."C" =
               requested_issuer COLLATE pg_catalog."C"
           AND row.subject::pg_catalog.text COLLATE pg_catalog."C" =
               requested_subject COLLATE pg_catalog."C";
        SELECT row.* INTO STRICT binding
          FROM ofarm.principal_binding AS row
         WHERE row.binding_version_id = active_id
           AND row.binding_version_digest::pg_catalog.text = active_digest;
        SELECT row.* INTO STRICT registry
          FROM ofarm.tenant_registry AS row
         WHERE row.tenant_id = binding.tenant_id
           AND row.registration_digest =
               binding.tenant_registration_digest;
    EXCEPTION WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
        RAISE EXCEPTION USING ERRCODE = 'PT001',
            MESSAGE = 'principal immutable reference differs';
    END;
    IF projected.current_state <> 'ACTIVE'
       OR projected.binding_version_id IS DISTINCT FROM active_id
       OR projected.binding_version_digest::pg_catalog.text
            IS DISTINCT FROM active_digest
       OR projected.lifecycle_head_id IS DISTINCT FROM head_id
       OR projected.lifecycle_head_digest::pg_catalog.text
            IS DISTINCT FROM head_digest
       OR binding.binding_version_digest::pg_catalog.text IS DISTINCT FROM
            ofarm.compute_principal_binding_version_digest(
                binding.equality_policy, binding.issuer::pg_catalog.text,
                binding.subject::pg_catalog.text, binding.binding_version_id,
                binding.tenant_id,
                binding.tenant_registration_digest::pg_catalog.text,
                binding.party_ref::pg_catalog.text, binding.party_record_kind,
                binding.party_record_id::pg_catalog.text,
                binding.party_schema_digest::pg_catalog.text,
                binding.party_payload_digest::pg_catalog.text,
                binding.party_state, binding.valid_from, binding.valid_until,
                binding.predecessor_version_id
            )
       OR registry.registration_digest::pg_catalog.text IS DISTINCT FROM
            ofarm.compute_tenant_registration_digest(
                registry.tenant_id, registry.tenant_ref::pg_catalog.text,
                registry.advisory_lock_key
            ) THEN
        RAISE EXCEPTION USING ERRCODE = 'PT001',
            MESSAGE = 'principal authority projection differs';
    END IF;
    IF binding.party_record_kind <> 'ofarm.party.v0.1'
       OR binding.party_record_id <> binding.party_ref
       OR binding.party_state <> 'ACTIVE'
       OR observed_at < binding.valid_from
       OR observed_at >= binding.valid_until THEN
        RETURN;
    END IF;
    RETURN QUERY SELECT binding.equality_policy,
        binding.issuer::pg_catalog.text, binding.subject::pg_catalog.text,
        binding.binding_version_id,
        binding.binding_version_digest::pg_catalog.text, head_id, head_digest,
        binding.tenant_id,
        binding.tenant_registration_digest::pg_catalog.text,
        binding.party_ref::pg_catalog.text, binding.party_record_kind,
        binding.party_record_id::pg_catalog.text,
        binding.party_schema_digest::pg_catalog.text,
        binding.party_payload_digest::pg_catalog.text, binding.party_state,
        binding.valid_from, binding.valid_until;
END
$body$;

CREATE FUNCTION ofarm.observe_signing_authority(requested_kid pg_catalog.text)
RETURNS TABLE (
    binder_instance_id pg_catalog.uuid,
    audience pg_catalog.text,
    capability_contract_digest pg_catalog.text,
    candidate_id pg_catalog.uuid,
    kid pg_catalog.text,
    candidate_digest pg_catalog.text,
    public_key pg_catalog.bytea,
    public_key_digest pg_catalog.text,
    kms_key_version_resource pg_catalog.text,
    kms_attestation_digest pg_catalog.text,
    admission_state pg_catalog.text,
    lifecycle_head_sequence pg_catalog.int8,
    lifecycle_head_id pg_catalog.uuid,
    lifecycle_head_digest pg_catalog.text,
    issuance_start_us pg_catalog.int8,
    issuance_end_us pg_catalog.int8,
    kms_evidence_digest pg_catalog.text,
    iam_evidence_digest pg_catalog.text,
    observed_at_us pg_catalog.int8
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $body$
DECLARE
    instance ofarm.tenant_binder_instance%ROWTYPE;
    ring ofarm.tenant_capability_keyring%ROWTYPE;
    candidate ofarm.tenant_capability_verification_key%ROWTYPE;
    act ofarm.tenant_capability_key_lifecycle%ROWTYPE;
    expected_sequence pg_catalog.int8 := 0;
    expected_prior_id pg_catalog.uuid;
    expected_prior_digest pg_catalog.text;
    head ofarm.tenant_capability_key_lifecycle%ROWTYPE;
    activated_at_us pg_catalog.int8;
    issuance_until_us pg_catalog.int8;
BEGIN
    IF SESSION_USER <> 'ofarm_app' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'signing authority caller differs';
    END IF;
    IF requested_kid IS NULL
       OR pg_catalog.octet_length(requested_kid) <> 43
       OR requested_kid OPERATOR(pg_catalog.!~) '^[A-Za-z0-9_-]{43}$' THEN
        RETURN;
    END IF;
    BEGIN
        SELECT row.* INTO STRICT instance
          FROM ofarm.tenant_binder_instance AS row WHERE row.singleton;
        SELECT row.* INTO STRICT ring
          FROM ofarm.tenant_capability_keyring AS row
         WHERE row.audience = instance.audience;
    EXCEPTION WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
        RAISE EXCEPTION USING ERRCODE = 'PT001',
            MESSAGE = 'signing authority projection differs';
    END;

    FOR act IN
        SELECT row.* FROM ofarm.tenant_capability_key_lifecycle AS row
         ORDER BY row.stream_sequence
    LOOP
        IF act.stream_sequence <> expected_sequence + 1
           OR act.prior_act_id IS DISTINCT FROM expected_prior_id
           OR act.prior_act_digest::pg_catalog.text
                IS DISTINCT FROM expected_prior_digest
           OR act.audience <> instance.audience
           OR act.algorithm <> 'Ed25519'
           OR act.act_digest::pg_catalog.text IS DISTINCT FROM
                ofarm.compute_tenant_capability_key_act_digest(
                    act.stream_sequence, act.act_id, act.prior_act_id,
                    act.prior_act_digest::pg_catalog.text, act.act_kind,
                    act.old_kid, act.old_candidate_digest::pg_catalog.text,
                    act.new_kid, act.new_candidate_digest::pg_catalog.text,
                    act.audience, act.algorithm, act.decided_at_us,
                    act.effective_at_us, act.new_issuance_end_us,
                    act.old_verification_end_us, act.incident_id,
                    act.close_receipt_id,
                    act.preflight_receipt_digest::pg_catalog.text,
                    act.kms_evidence_digest::pg_catalog.text,
                    act.iam_evidence_digest::pg_catalog.text,
                    act.accountable_control_ref::pg_catalog.text,
                    act.reason::pg_catalog.text
                ) THEN
            RAISE EXCEPTION USING ERRCODE = 'PT001',
                MESSAGE = 'signing lifecycle authority differs';
        END IF;
        expected_sequence := act.stream_sequence;
        expected_prior_id := act.act_id;
        expected_prior_digest := act.act_digest::pg_catalog.text;
        head := act;
        IF act.new_kid = requested_kid THEN
            activated_at_us := act.effective_at_us;
            issuance_until_us := act.new_issuance_end_us;
        ELSIF act.old_kid = requested_kid AND act.act_kind = 'ROTATE' THEN
            issuance_until_us := act.effective_at_us;
        END IF;
    END LOOP;
    IF ring.projected_head_sequence IS DISTINCT FROM expected_sequence
       OR ring.projected_head_id IS DISTINCT FROM expected_prior_id
       OR ring.projected_head_digest::pg_catalog.text
            IS DISTINCT FROM expected_prior_digest THEN
        RAISE EXCEPTION USING ERRCODE = 'PT001',
            MESSAGE = 'signing authority head differs';
    END IF;
    IF ring.projected_issuing_kid IS DISTINCT FROM requested_kid THEN
        RETURN;
    END IF;
    BEGIN
        SELECT row.* INTO STRICT candidate
          FROM ofarm.tenant_capability_verification_key AS row
         WHERE row.kid = requested_kid
           AND row.candidate_digest =
               ring.projected_issuing_candidate_digest;
    EXCEPTION WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
        RAISE EXCEPTION USING ERRCODE = 'PT001',
            MESSAGE = 'signing candidate reference differs';
    END;
    IF candidate.audience <> instance.audience
       OR candidate.algorithm <> 'Ed25519'
       OR candidate.kid <> ofarm.tenant_capability_key_id(candidate.public_key)
       OR candidate.public_key_digest::pg_catalog.text IS DISTINCT FROM
            'sha256:' || pg_catalog.encode(
                pg_catalog.sha256(candidate.public_key), 'hex'
            )
       OR candidate.candidate_digest::pg_catalog.text IS DISTINCT FROM
            ofarm.compute_tenant_capability_candidate_digest(
                candidate.candidate_id, candidate.kid, candidate.public_key,
                candidate.public_key_digest::pg_catalog.text,
                candidate.algorithm, candidate.audience,
                candidate.kms_key_version_resource, candidate.kms_purpose,
                candidate.kms_algorithm, candidate.kms_protection_level,
                candidate.kms_attestation_digest::pg_catalog.text,
                candidate.registered_at,
                candidate.accountable_control_ref::pg_catalog.text
            )
       OR activated_at_us IS NULL OR issuance_until_us IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'PT001',
            MESSAGE = 'signing candidate authority differs';
    END IF;
    RETURN QUERY SELECT instance.instance_id, instance.audience,
        instance.contract_digest::pg_catalog.text, candidate.candidate_id,
        candidate.kid, candidate.candidate_digest::pg_catalog.text,
        candidate.public_key, candidate.public_key_digest::pg_catalog.text,
        candidate.kms_key_version_resource,
        candidate.kms_attestation_digest::pg_catalog.text,
        ring.projected_admission_state, expected_sequence, expected_prior_id,
        expected_prior_digest, activated_at_us, issuance_until_us,
        head.kms_evidence_digest::pg_catalog.text,
        head.iam_evidence_digest::pg_catalog.text,
        (extract(epoch FROM pg_catalog.clock_timestamp()) * 1000000)
            ::pg_catalog.int8;
END
$body$;

REVOKE ALL PRIVILEGES ON FUNCTION
    ofarm.observe_authentication_runtime_contract(),
    ofarm.resolve_principal_binding_authority(
        pg_catalog.text, pg_catalog.text, pg_catalog.text
    ),
    ofarm.observe_signing_authority(pg_catalog.text)
FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    ofarm.observe_authentication_runtime_contract(),
    ofarm.resolve_principal_binding_authority(
        pg_catalog.text, pg_catalog.text, pg_catalog.text
    ),
    ofarm.observe_signing_authority(pg_catalog.text)
TO ofarm_app;

-- Advance the migration-head checks and freeze the additive catalog.
DO $migration$
DECLARE
    verifier pg_catalog.text;
BEGIN
    SELECT pg_catalog.pg_get_functiondef(
        'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure
    ) INTO STRICT verifier;
    IF pg_catalog.strpos(verifier, 'observed_migration_count <> 1') = 0
       OR pg_catalog.strpos(verifier, 'observed_head_version <> 1') = 0
       OR pg_catalog.strpos(
            verifier,
            'sha256:f7c72a008792173e110b9359006271fea263b3e26fb53c8ac6303839d0460fc4'
          ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-1 tenant verifier source differs';
    END IF;
    verifier := pg_catalog.replace(
        verifier, 'observed_migration_count <> 1',
        'observed_migration_count <> 2'
    );
    verifier := pg_catalog.replace(
        verifier, 'observed_head_version <> 1',
        'observed_head_version <> 2'
    );
    verifier := pg_catalog.replace(
        verifier, 'migration 0001 ledger identity differs',
        'migration ledger identity differs'
    );
    verifier := pg_catalog.replace(
        verifier, 'pg_catalog.max(migration.applied_prefix_digest)',
        'pg_catalog.max(migration.applied_prefix_digest) ' ||
        'FILTER (WHERE migration.version = 2)'
    );
    verifier := pg_catalog.replace(
        verifier,
        'sha256:f7c72a008792173e110b9359006271fea263b3e26fb53c8ac6303839d0460fc4',
        'sha256:897001ea090224da95746e9de94a6f0098c8a2eae01abab68ac1f32b6509e950'
    );
    EXECUTE verifier;
END
$migration$;
