-- Activate correlation-HMAC key version 2 and expose two bounded control
-- observations. Historical version-1 rows remain valid, but only an exact
-- retry of a committed event identity can pass the append transition.

ALTER TABLE ofarm_security.operational_security_event
    DROP CONSTRAINT operational_security_event_pretenant_shape_check;
ALTER TABLE ofarm_security.operational_security_event
    ADD CONSTRAINT operational_security_event_pretenant_shape_check CHECK (
        (event_kind = 'PRE_TENANT_FAILURE') = (
            reason IS NOT NULL
            AND correlation_hmac_domain IS NOT NULL
            AND correlation_hmac_domain = 'OFARM_PRETENANT_CORRELATION_V1'
            AND correlation_hmac_key_version IS NOT NULL
            AND correlation_hmac_key_version IN (1, 2)
            AND correlation_hmac_value IS NOT NULL
            AND pg_catalog.octet_length(correlation_hmac_value) = 32
        )
    );

-- Rotation changes the shape allowlist above, the observer allowlist below,
-- and the observer's active-version predicate as one policy.

-- Preserve the reviewed append state machine and change only its active key.
-- Its committed-event and overflow-receipt checks deliberately precede this
-- policy check, which is the stable retry identity rule for historical V1.
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
            'aadb04a6c86ebe27e142ec71c95a1a48422a5930e942fdfa61cd2095340a3934'
       OR pg_catalog.strpos(
            definition,
            'p_correlation_hmac_key_version <> 1'
       ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-1 pre-tenant append source differs';
    END IF;
    definition := pg_catalog.replace(
        definition,
        'p_correlation_hmac_key_version <> 1',
        'p_correlation_hmac_key_version <> 2'
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
            'eee23f3fcbe528cea2664caac9c826a5964dee209e954fb11a8409d0870d06af'
       OR pg_catalog.strpos(
            definition,
            'sha256:013b5e00232c86f6ef9824c98184c18b899a412305151ee31eb9991a633dc8db'
       ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-1 audit observer source differs';
    END IF;
    definition := pg_catalog.replace(
        definition,
        'sha256:013b5e00232c86f6ef9824c98184c18b899a412305151ee31eb9991a633dc8db',
        'sha256:ea38388e813f1aa3ce32d9a46bcbe0012ddcbc736b5f5007f4a87e12bba12c74'
    );
    definition := pg_catalog.replace(
        definition,
        $old$        'OFARM_PRETENANT_CORRELATION_V1',
        1,
        'ofarm.security-audit-postgresql.v1',$old$,
        $new$        'OFARM_PRETENANT_CORRELATION_V1',
        2,
        'ofarm.security-audit-postgresql.v1',$new$
    );
    EXECUTE definition;
END
$migration$;

CREATE INDEX operational_security_event_hmac_retention_idx
    ON ofarm_security.operational_security_event
        (correlation_hmac_key_version, purge_after DESC)
    WHERE event_kind = 'PRE_TENANT_FAILURE';

CREATE FUNCTION ofarm_security.observe_next_closeable_overflow_bucket()
RETURNS TABLE (
    producer pg_catalog.text,
    component pg_catalog.text,
    bucket_start pg_catalog.timestamptz
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $body$
BEGIN
    IF session_user <> 'ofarm_security_audit_control_login' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'session user is not the audit control observer';
    END IF;
    RETURN QUERY
    SELECT bucket.producer, bucket.component, bucket.bucket_start
    FROM ofarm_security.operational_security_quota_bucket AS bucket
    WHERE bucket.overflow_started_at IS NOT NULL
      AND bucket.bucket_start < pg_catalog.date_bin(
            pg_catalog.make_interval(secs => 60),
            pg_catalog.clock_timestamp(),
            '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
      )
    ORDER BY
        bucket.bucket_start,
        bucket.producer COLLATE pg_catalog."C",
        bucket.component COLLATE pg_catalog."C"
    LIMIT 1;
END
$body$;

CREATE FUNCTION ofarm_security.observe_correlation_hmac_key_retention(
    p_key_version pg_catalog.int4
)
RETURNS TABLE (
    key_version pg_catalog.int4,
    active pg_catalog.bool,
    greatest_purge_after pg_catalog.timestamptz
)
LANGUAGE plpgsql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $body$
BEGIN
    IF session_user <> 'ofarm_security_audit_control_login' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'session user is not the audit control observer';
    END IF;
    IF p_key_version IS NULL OR p_key_version NOT IN (1, 2) THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'correlation HMAC key version is unknown';
    END IF;
    RETURN QUERY
    SELECT
        p_key_version,
        p_key_version = 2,
        pg_catalog.max(event.purge_after)
    FROM ofarm_security.operational_security_event AS event
    WHERE event.event_kind = 'PRE_TENANT_FAILURE'
      AND event.correlation_hmac_key_version = p_key_version;
END
$body$;

REVOKE ALL PRIVILEGES ON FUNCTION
    ofarm_security.observe_next_closeable_overflow_bucket(),
    ofarm_security.observe_correlation_hmac_key_retention(pg_catalog.int4)
FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    ofarm_security.observe_next_closeable_overflow_bucket(),
    ofarm_security.observe_correlation_hmac_key_retention(pg_catalog.int4)
TO ofarm_security_audit_control;

-- Extend the migration-owned structural verifier without copying its large,
-- reviewed catalog query. The full V1 source digest makes every replacement
-- deterministic; the verifier still owns one literal final catalog digest.
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
            'f450d61e7a86c87f4675ab97475ca75d02cceae287ca99420313012e60d41437'
       OR pg_catalog.strpos(
            verifier,
            'sha256:90f439c108b77a33e44cc987a057b601c27dfe2e4a4c3bb1e128d4cb2106f663'
       ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-1 audit verifier source differs';
    END IF;

    verifier := pg_catalog.replace(
        verifier,
        $old$        'operational_security_event_identity_lock_pkey',
        'operational_security_event_live_order_idx',$old$,
        $new$        'operational_security_event_hmac_retention_idx',
        'operational_security_event_identity_lock_pkey',
        'operational_security_event_live_order_idx',$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$        'observe_security_audit_contract',$old$,
        $new$        'observe_correlation_hmac_key_retention',
        'observe_next_closeable_overflow_bucket',
        'observe_security_audit_contract',$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$        ('ofarm_security.observe_security_audit_contract()',
         'ofarm_security.security_audit_contract_observation',
         'ofarm_security_audit_readiness'),$old$,
        $new$        ('ofarm_security.observe_correlation_hmac_key_retention(integer)',
         'TABLE(key_version integer, active boolean, greatest_purge_after timestamp with time zone)',
         'ofarm_security_audit_control'),
        ('ofarm_security.observe_next_closeable_overflow_bucket()',
         'TABLE(producer text, component text, bucket_start timestamp with time zone)',
         'ofarm_security_audit_control'),
        ('ofarm_security.observe_security_audit_contract()',
         'ofarm_security.security_audit_contract_observation',
         'ofarm_security_audit_readiness'),$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$        ('ofarm_security.observe_security_audit_contract()',
         'ofarm_security_audit_readiness'),$old$,
        $new$        ('ofarm_security.observe_correlation_hmac_key_retention(integer)',
         'ofarm_security_audit_control'),
        ('ofarm_security.observe_next_closeable_overflow_bucket()',
         'ofarm_security_audit_control'),
        ('ofarm_security.observe_security_audit_contract()',
         'ofarm_security_audit_readiness'),$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$    WHERE version = 1
      AND filename = '0001_initial.sql'
      AND service_identity = 'ofarm.security-audit-postgresql.v1'
      AND provisioning_spec_digest =
          'sha256:9b9d06c6f6ac5527a32014ec1719a3cee9742d4d5ab7d8e8a4ff2797053824f7'
      AND source_sha256 ~ '^sha256:[0-9a-f]{64}$'
      AND applied_prefix_digest ~ '^sha256:[0-9a-f]{64}$';
    IF v_count <> 1 OR (SELECT pg_catalog.count(*)
                        FROM ofarm_security.schema_migration) <> 1 THEN$old$,
        $new$    WHERE (
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
                        FROM ofarm_security.schema_migration) <> 2 THEN$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        'aadb04a6c86ebe27e142ec71c95a1a48422a5930e942fdfa61cd2095340a3934',
        'a614ea8089ff2cdd0769e95b4186dc6ad52cb12dc8e688ac09e79db98853d10b'
    );
    verifier := pg_catalog.replace(
        verifier,
        'sha256:90f439c108b77a33e44cc987a057b601c27dfe2e4a4c3bb1e128d4cb2106f663',
        'sha256:452118f0c24fc15be4fc7c3e1046283306826580590c0d3aef8573479463a0d8'
    );
    EXECUTE verifier;
END
$migration$;
