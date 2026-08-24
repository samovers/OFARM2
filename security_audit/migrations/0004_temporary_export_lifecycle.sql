-- Add one bounded, owner-only first-use relation and its sole control-login
-- consumption function.  Temporary LOGIN creation and closure remain in the
-- application lifecycle; this migration grants no relation access.

CREATE TABLE ofarm_security.temporary_export_approval_consumption (
    operation_id pg_catalog.uuid NOT NULL,
    valid_until pg_catalog.timestamptz NOT NULL,
    consumed_at pg_catalog.timestamptz NOT NULL,
    CONSTRAINT temporary_export_approval_consumption_pkey
        PRIMARY KEY (operation_id),
    CONSTRAINT temporary_export_approval_consumption_operation_id_check
        CHECK (
            operation_id <>
                '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
        ),
    CONSTRAINT temporary_export_approval_consumption_time_check
        CHECK (
            pg_catalog.isfinite(valid_until)
            AND pg_catalog.isfinite(consumed_at)
            AND consumed_at < valid_until
        )
);

REVOKE ALL PRIVILEGES ON TABLE
ofarm_security.temporary_export_approval_consumption FROM PUBLIC;

CREATE FUNCTION ofarm_security.consume_temporary_export_approval(
    p_operation_id pg_catalog.uuid,
    p_store_migration_execution_id pg_catalog.uuid,
    p_valid_from_unix_microseconds pg_catalog.int8,
    p_valid_until_unix_microseconds pg_catalog.int8,
    p_authority_now_unix_microseconds pg_catalog.int8
)
RETURNS pg_catalog.bool
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $consume_temporary_export_approval$
DECLARE
    v_store_migration_execution_id pg_catalog.uuid;
    v_clock pg_catalog.record;
    v_maximum_unix_microseconds pg_catalog.int8;
    v_maximum_at pg_catalog.timestamptz;
    v_valid_until pg_catalog.timestamptz;
    v_live_count pg_catalog.int8;
    v_inserted_count pg_catalog.int8;
BEGIN
    IF session_user <> 'ofarm_security_audit_control_login' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'session user is not the audit control login';
    END IF;
    IF p_operation_id IS NULL
            OR p_operation_id =
                '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
            OR p_store_migration_execution_id IS NULL
            OR p_store_migration_execution_id =
                '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
            OR p_valid_from_unix_microseconds IS NULL
            OR p_valid_until_unix_microseconds IS NULL
            OR p_authority_now_unix_microseconds IS NULL
            OR p_valid_from_unix_microseconds < 0
            OR p_valid_until_unix_microseconds < 0
            OR p_authority_now_unix_microseconds < 0
            OR p_valid_until_unix_microseconds <=
                p_valid_from_unix_microseconds
            OR p_valid_until_unix_microseconds -
                p_valid_from_unix_microseconds > 300000000 THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'temporary export approval arguments are invalid';
    END IF;

    SELECT execution_id
    INTO STRICT v_store_migration_execution_id
    FROM ofarm_security.schema_migration
    WHERE version = 1
      AND filename = '0001_initial.sql'
      AND service_identity = 'ofarm.security-audit-postgresql.v1';
    IF v_store_migration_execution_id <>
            p_store_migration_execution_id THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'temporary export approval store differs';
    END IF;

    SELECT observed_at, high_water_microseconds, clock_regressed
    INTO STRICT v_clock
    FROM ofarm_security._observe_nonregressing_access_clock();
    IF v_clock.clock_regressed
            OR v_clock.high_water_microseconds < 0
            OR v_clock.high_water_microseconds >
                9223372036554775807 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'temporary export approval clock is unavailable';
    END IF;

    v_maximum_unix_microseconds := GREATEST(
        p_authority_now_unix_microseconds,
        v_clock.high_water_microseconds
    );
    IF p_valid_from_unix_microseconds >
            v_maximum_unix_microseconds
            OR v_maximum_unix_microseconds >=
                p_valid_until_unix_microseconds
            OR p_valid_until_unix_microseconds >
                v_clock.high_water_microseconds + 300000000 THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'temporary export approval is not current';
    END IF;

    v_maximum_at := pg_catalog.to_timestamp(
        v_maximum_unix_microseconds / 1000000
    ) + (v_maximum_unix_microseconds % 1000000)::pg_catalog.float8
        * pg_catalog.make_interval(secs => 0.000001);
    v_valid_until := pg_catalog.to_timestamp(
        p_valid_until_unix_microseconds / 1000000
    ) + (p_valid_until_unix_microseconds % 1000000)::pg_catalog.float8
        * pg_catalog.make_interval(secs => 0.000001);

    LOCK TABLE ofarm_security.temporary_export_approval_consumption
        IN EXCLUSIVE MODE;
    DELETE FROM ofarm_security.temporary_export_approval_consumption
    WHERE valid_until <= v_maximum_at;
    SELECT pg_catalog.count(*)
    INTO STRICT v_live_count
    FROM ofarm_security.temporary_export_approval_consumption;
    IF v_live_count >= 1024 THEN
        RAISE EXCEPTION USING ERRCODE = '54000',
            MESSAGE = 'temporary export approval capacity is exhausted';
    END IF;

    INSERT INTO ofarm_security.temporary_export_approval_consumption (
        operation_id, valid_until, consumed_at
    ) VALUES (
        p_operation_id, v_valid_until, v_clock.observed_at
    )
    ON CONFLICT (operation_id) DO NOTHING;
    GET DIAGNOSTICS v_inserted_count = ROW_COUNT;
    RETURN v_inserted_count = 1;
END
$consume_temporary_export_approval$;

REVOKE ALL PRIVILEGES ON FUNCTION
ofarm_security.consume_temporary_export_approval(
    pg_catalog.uuid, pg_catalog.uuid, pg_catalog.int8, pg_catalog.int8,
    pg_catalog.int8
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
ofarm_security.consume_temporary_export_approval(
    pg_catalog.uuid, pg_catalog.uuid, pg_catalog.int8, pg_catalog.int8,
    pg_catalog.int8
) TO ofarm_security_audit_control;

-- Advance the contract observer only from the exact reviewed version-3
-- source.  The new digest includes the control-only consume function.
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
        'ofarm_security.observe_security_audit_contract()'
    );
    IF source_digest <>
            '81e9318b6536ed4cdc22e338a49b4a5087a9b7f47a9fd2969441fb6fe93fd713'
       OR pg_catalog.strpos(
            definition,
            'sha256:4807acc1b06366b5594c539ca9b8da86dc1dcbcbcead48e761fca9f6be9342e2'
       ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-3 audit observer source differs';
    END IF;
    definition := pg_catalog.replace(
        definition,
        'sha256:4807acc1b06366b5594c539ca9b8da86dc1dcbcbcead48e761fca9f6be9342e2',
        'sha256:19c797f1d9de06b555c737ee666a6f4cecba5091a7c5dc8851ba40af37f66e81'
    );
    EXECUTE definition;
END
$migration$;

-- Extend the complete structural verifier from the exact version-3 source.
-- The verifier remains the normal-state authority and therefore continues to
-- reject any present temporary export LOGIN.
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
            '6fee5e6117a5fd2404f6081dab58f531ef5b0d8e4173e3700bed0088227860e2'
       OR pg_catalog.strpos(
            verifier,
            'sha256:1c76b92c9e71bc3cfdcf42964a6a17d38795200684a2c76fd88f99341a475609'
       ) = 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-3 audit verifier source differs';
    END IF;

    verifier := pg_catalog.replace(
        verifier,
        $old$        'schema_migration'
    ]::pg_catalog.text[] THEN$old$,
        $new$        'schema_migration',
        'temporary_export_approval_consumption'
    ]::pg_catalog.text[] THEN$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$        'schema_migration_filename_key',
        'schema_migration_pkey'
    ]::pg_catalog.text[] THEN$old$,
        $new$        'schema_migration_filename_key',
        'schema_migration_pkey',
        'temporary_export_approval_consumption_pkey'
    ]::pg_catalog.text[] THEN$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$    SELECT pg_catalog.count(*) INTO v_count
    FROM ofarm_security.operational_security_overflow_identity_receipt;
    IF v_count <> 512 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_attribute AS attribute$old$,
        $new$    SELECT pg_catalog.count(*) INTO v_count
    FROM ofarm_security.operational_security_overflow_identity_receipt;
    IF v_count <> 512 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(attribute.attname::pg_catalog.text
            ORDER BY attribute.attnum)
    INTO v_names
    FROM pg_catalog.pg_attribute AS attribute
    WHERE attribute.attrelid =
            'ofarm_security.temporary_export_approval_consumption'::
                pg_catalog.regclass
      AND attribute.attnum > 0
      AND NOT attribute.attisdropped;
    IF v_names IS DISTINCT FROM ARRAY[
        'operation_id', 'valid_until', 'consumed_at'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM ofarm_security.temporary_export_approval_consumption;
    IF v_count > 1024 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_attribute AS attribute$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$          'operational_security_quota_bucket',
          'operational_security_quota_high_water'
      )$old$,
        $new$          'operational_security_quota_bucket',
          'operational_security_quota_high_water',
          'temporary_export_approval_consumption'
      )$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$    IF v_names IS DISTINCT FROM ARRAY[
        'operational_security_overflow_receipt_attribution_check',
        'operational_security_overflow_receipt_event_id_key',
        'operational_security_overflow_receipt_pkey',
        'operational_security_overflow_receipt_shape_check',
        'operational_security_overflow_receipt_slot_check'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_constraint AS con$old$,
        $new$    IF v_names IS DISTINCT FROM ARRAY[
        'operational_security_overflow_receipt_attribution_check',
        'operational_security_overflow_receipt_event_id_key',
        'operational_security_overflow_receipt_pkey',
        'operational_security_overflow_receipt_shape_check',
        'operational_security_overflow_receipt_slot_check'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(con.conname::pg_catalog.text
            ORDER BY con.conname::pg_catalog.text)
    INTO v_names
    FROM pg_catalog.pg_constraint AS con
    WHERE con.conrelid =
        'ofarm_security.temporary_export_approval_consumption'::
            pg_catalog.regclass;
    IF v_names IS DISTINCT FROM ARRAY[
        'temporary_export_approval_consumption_operation_id_check',
        'temporary_export_approval_consumption_pkey',
        'temporary_export_approval_consumption_time_check'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_constraint AS con$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$        'commit_audit_access_intent',
        'export_operational_security_events',$old$,
        $new$        'commit_audit_access_intent',
        'consume_temporary_export_approval',
        'export_operational_security_events',$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$        ('ofarm_security.commit_audit_access_intent(text, text, timestamp with time zone, uuid, integer, bigint)',
         'ofarm_security.audit_access_intent_result',
         'ofarm_security_audit_control'),
        ('ofarm_security.append_audit_gap$old$,
        $new$        ('ofarm_security.commit_audit_access_intent(text, text, timestamp with time zone, uuid, integer, bigint)',
         'ofarm_security.audit_access_intent_result',
         'ofarm_security_audit_control'),
        ('ofarm_security.consume_temporary_export_approval(uuid, uuid, bigint, bigint, bigint)',
         'boolean', 'ofarm_security_audit_control'),
        ('ofarm_security.append_audit_gap$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$        ('ofarm_security.commit_audit_access_intent(text, text, timestamp with time zone, uuid, integer, bigint)',
         'ofarm_security_audit_control'),
        ('ofarm_security.append_audit_gap$old$,
        $new$        ('ofarm_security.commit_audit_access_intent(text, text, timestamp with time zone, uuid, integer, bigint)',
         'ofarm_security_audit_control'),
        ('ofarm_security.consume_temporary_export_approval(uuid, uuid, bigint, bigint, bigint)',
         'ofarm_security_audit_control'),
        ('ofarm_security.append_audit_gap$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$        'ofarm_security.operational_security_quota_high_water'::pg_catalog.regclass
    ) AND NOT trigger.tgisinternal;$old$,
        $new$        'ofarm_security.operational_security_quota_high_water'::pg_catalog.regclass,
        'ofarm_security.temporary_export_approval_consumption'::pg_catalog.regclass
    ) AND NOT trigger.tgisinternal;$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$        'ofarm_security.operational_security_quota_high_water'::pg_catalog.regclass
    )
      AND acl.grantee <> class.relowner;$old$,
        $new$        'ofarm_security.operational_security_quota_high_water'::pg_catalog.regclass,
        'ofarm_security.temporary_export_approval_consumption'::pg_catalog.regclass
    )
      AND acl.grantee <> class.relowner;$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        $old$    WHERE (
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
                        FROM ofarm_security.schema_migration) <> 3 THEN$old$,
        $new$    WHERE (
            (version = 1 AND filename = '0001_initial.sql')
            OR
            (version = 2 AND filename = '0002_hmac_v2_operations.sql')
            OR
            (version = 3
             AND filename = '0003_outcome_reason_vocabulary.sql')
            OR
            (version = 4
             AND filename = '0004_temporary_export_lifecycle.sql')
      )
      AND service_identity = 'ofarm.security-audit-postgresql.v1'
      AND provisioning_spec_digest =
          'sha256:9b9d06c6f6ac5527a32014ec1719a3cee9742d4d5ab7d8e8a4ff2797053824f7'
      AND source_sha256 ~ '^sha256:[0-9a-f]{64}$'
      AND applied_prefix_digest ~ '^sha256:[0-9a-f]{64}$';
    IF v_count <> 4 OR (SELECT pg_catalog.count(*)
                        FROM ofarm_security.schema_migration) <> 4 THEN$new$
    );
    verifier := pg_catalog.replace(
        verifier,
        'sha256:1c76b92c9e71bc3cfdcf42964a6a17d38795200684a2c76fd88f99341a475609',
        'sha256:944993a9154e7ed9238d4b3456070388c983b3228e075f1d41e3c2a053d34ff8'
    );
    EXECUTE verifier;
END
$migration$;
