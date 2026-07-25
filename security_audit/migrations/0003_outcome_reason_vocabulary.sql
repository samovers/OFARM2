-- Align fresh pre-tenant append reasons with the closed authentication,
-- principal, and tenant-boundary outcomes. Retired reasons remain valid only
-- as immutable historical row values and exact committed retry identities.

ALTER TABLE ofarm_security.operational_security_event
    DROP CONSTRAINT operational_security_event_pretenant_attribution_check;
ALTER TABLE ofarm_security.operational_security_event
    ADD CONSTRAINT operational_security_event_pretenant_attribution_check CHECK (
        event_kind <> 'PRE_TENANT_FAILURE'
        OR (
            producer = 'AUTHENTICATION_BOUNDARY_V1'
            AND component = 'AUTHENTICATION'
            AND reason IN (
                'CREDENTIAL_MISSING', 'CREDENTIAL_MALFORMED',
                'VERIFIER_UNAVAILABLE', 'VERIFICATION_REFUSED',
                'PRINCIPAL_BINDING_REFUSED',
                'AUTHORITY_INTEGRITY_REFUSED', 'AUTHORITY_UNAVAILABLE',
                'TENANT_PARTY_PIN_REFUSED', 'CAPABILITY_REFUSED'
            )
        )
        OR (
            producer = 'REQUEST_ROUTER_BOUNDARY_V1'
            AND component = 'REQUEST_ROUTER'
            AND reason IN (
                'TENANT_BOUNDARY_UNAVAILABLE', 'CAPABILITY_REFUSED',
                'BINDER_REFUSED', 'SECURITY_ROUTE_REFUSED',
                'ACTOR_BINDING_REFUSED'
            )
        )
    );

-- Preserve the reviewed append state machine and replace only its fresh-ID
-- reason policy. Existing event and overflow-receipt checks remain before this
-- block, so historical exact retries still return their original outcomes.
DO $migration$
DECLARE
    definition pg_catalog.text;
    source_digest pg_catalog.text;
BEGIN
    SELECT
        pg_catalog.pg_get_functiondef(routine.oid),
        pg_catalog.encode(
            pg_catalog.sha256(
                pg_catalog.convert_to(routine.prosrc, 'UTF8')
            ),
            'hex'
        )
    INTO STRICT definition, source_digest
    FROM pg_catalog.pg_proc AS routine
    WHERE routine.oid = pg_catalog.to_regprocedure(
        'ofarm_security.append_pretenant_failure('
        'uuid, text, bytea, text, integer)'
    );
    IF source_digest <>
            '356ff27c8e9442025acfe5edfc6112740492ea64053f6e5a8f50cd5a41213bcb'
       OR pg_catalog.strpos(
            definition,
            $old$    IF NOT (
        (v_component = 'AUTHENTICATION' AND p_reason IN (
            'CREDENTIAL_MISSING', 'CREDENTIAL_MALFORMED',
            'VERIFIER_UNAVAILABLE', 'VERIFICATION_REFUSED',
            'PRINCIPAL_BINDING_REFUSED', 'TENANT_PARTY_PIN_REFUSED',
            'CAPABILITY_REFUSED'
        ))
        OR
        (v_component = 'REQUEST_ROUTER' AND p_reason IN (
            'SECURITY_ROUTE_REFUSED', 'CAPABILITY_REFUSED',
            'BINDER_REFUSED', 'ACTOR_BINDING_REFUSED'
        ))
    ) THEN$old$
       ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-2 pre-tenant append source differs';
    END IF;
    definition := pg_catalog.replace(
        definition,
        $old$    IF NOT (
        (v_component = 'AUTHENTICATION' AND p_reason IN (
            'CREDENTIAL_MISSING', 'CREDENTIAL_MALFORMED',
            'VERIFIER_UNAVAILABLE', 'VERIFICATION_REFUSED',
            'PRINCIPAL_BINDING_REFUSED', 'TENANT_PARTY_PIN_REFUSED',
            'CAPABILITY_REFUSED'
        ))
        OR
        (v_component = 'REQUEST_ROUTER' AND p_reason IN (
            'SECURITY_ROUTE_REFUSED', 'CAPABILITY_REFUSED',
            'BINDER_REFUSED', 'ACTOR_BINDING_REFUSED'
        ))
    ) THEN$old$,
        $new$    IF NOT (
        (v_component = 'AUTHENTICATION' AND p_reason IN (
            'CREDENTIAL_MISSING', 'CREDENTIAL_MALFORMED',
            'VERIFIER_UNAVAILABLE', 'VERIFICATION_REFUSED',
            'PRINCIPAL_BINDING_REFUSED', 'AUTHORITY_INTEGRITY_REFUSED',
            'AUTHORITY_UNAVAILABLE'
        ))
        OR
        (v_component = 'REQUEST_ROUTER' AND p_reason IN (
            'TENANT_BOUNDARY_UNAVAILABLE', 'CAPABILITY_REFUSED',
            'BINDER_REFUSED'
        ))
    ) THEN$new$
    );
    EXECUTE definition;

    SELECT
        pg_catalog.pg_get_functiondef(routine.oid),
        pg_catalog.encode(
            pg_catalog.sha256(
                pg_catalog.convert_to(routine.prosrc, 'UTF8')
            ),
            'hex'
        )
    INTO STRICT definition, source_digest
    FROM pg_catalog.pg_proc AS routine
    WHERE routine.oid = pg_catalog.to_regprocedure(
        'ofarm_security.observe_security_audit_contract()'
    );
    IF source_digest <>
            'e645ead5c6540268bf62daeb1dbcccb1bd19e145894abea546744f652cd08e06'
       OR pg_catalog.strpos(
            definition,
            'sha256:ea38388e813f1aa3ce32d9a46bcbe0012ddcbc736b5f5007f4a87e12bba12c74'
       ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-2 audit observer source differs';
    END IF;
    definition := pg_catalog.replace(
        definition,
        'sha256:ea38388e813f1aa3ce32d9a46bcbe0012ddcbc736b5f5007f4a87e12bba12c74',
        'sha256:4807acc1b06366b5594c539ca9b8da86dc1dcbcbcead48e761fca9f6be9342e2'
    );
    EXECUTE definition;
END
$migration$;

-- Extend the structural verifier without copying its large catalog query.
-- Every replacement is pinned to the complete version-2 verifier source.
DO $migration$
DECLARE
    verifier pg_catalog.text;
    source_digest pg_catalog.text;
BEGIN
    SELECT
        pg_catalog.pg_get_functiondef(routine.oid),
        pg_catalog.encode(
            pg_catalog.sha256(
                pg_catalog.convert_to(routine.prosrc, 'UTF8')
            ),
            'hex'
        )
    INTO STRICT verifier, source_digest
    FROM pg_catalog.pg_proc AS routine
    WHERE routine.oid = pg_catalog.to_regprocedure(
        'ofarm_security.verify_security_audit_structure()'
    );
    IF source_digest <>
            '7f54dfa0d9e9801344b79b035525aa80f7bad453e93df9e5abaa68c575d2d405'
       OR pg_catalog.strpos(
            verifier,
            'sha256:c4cc6e1f6f0188dd40817fdacd37dda6304f5a2a48f77df92978ee83429c0703'
       ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-2 audit verifier source differs';
    END IF;
    verifier := pg_catalog.replace(
        verifier,
        $old$    WHERE (
            (version = 1 AND filename = '0001_initial.sql')
            OR
            (version = 2 AND filename = '0002_hmac_v2_operations.sql')
      )
      AND service_identity = 'ofarm.security-audit-postgresql.v1'
      AND provisioning_spec_digest =
          'sha256:9b9d06c6f6ac5527a32014ec1719a3cee9742d4d5ab7d8e8a4ff2797053824f7'
      AND source_sha256 ~ '^sha256:[0-9a-f]{64}$'
      AND applied_prefix_digest ~ '^sha256:[0-9a-f]{64}$';
    IF v_count <> 2 OR (SELECT pg_catalog.count(*)
                        FROM ofarm_security.schema_migration) <> 2 THEN$old$,
        $new$    WHERE (
            (version = 1 AND filename = '0001_initial.sql')
            OR
            (version = 2 AND filename = '0002_hmac_v2_operations.sql')
            OR
            (version = 3
             AND filename = '0003_outcome_reason_vocabulary.sql')
      )
      AND service_identity = 'ofarm.security-audit-postgresql.v1'
      AND provisioning_spec_digest =
          'sha256:9b9d06c6f6ac5527a32014ec1719a3cee9742d4d5ab7d8e8a4ff2797053824f7'
      AND source_sha256 ~ '^sha256:[0-9a-f]{64}$'
      AND applied_prefix_digest ~ '^sha256:[0-9a-f]{64}$';
    IF v_count <> 3 OR (SELECT pg_catalog.count(*)
                        FROM ofarm_security.schema_migration) <> 3 THEN$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        '356ff27c8e9442025acfe5edfc6112740492ea64053f6e5a8f50cd5a41213bcb',
        '6a1f795237509f98e206de68b85423e06a9acbf1d62dfbcbbcb1a1b2476183ba'
    );
    verifier := pg_catalog.replace(
        verifier,
        'sha256:c4cc6e1f6f0188dd40817fdacd37dda6304f5a2a48f77df92978ee83429c0703',
        'sha256:1c76b92c9e71bc3cfdcf42964a6a17d38795200684a2c76fd88f99341a475609'
    );
    EXECUTE verifier;
END
$migration$;
