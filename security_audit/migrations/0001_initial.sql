-- OFARM isolated pre-tenant operational security audit baseline.
-- This file is immutable after release. It intentionally installs no extension,
-- partition, replica, publication, subscription, backup, or restore surface.

CREATE TABLE "ofarm_security"."schema_migration" (
    version pg_catalog.int4 NOT NULL,
    filename pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    source_sha256 pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    source_byte_length pg_catalog.int8 NOT NULL,
    applied_prefix_digest pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    service_identity pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    provisioning_spec_digest pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    release_identity pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    execution_id pg_catalog.uuid NOT NULL,
    applied_at pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),

    CONSTRAINT schema_migration_pkey PRIMARY KEY (version),
    CONSTRAINT schema_migration_filename_key UNIQUE (filename),
    CONSTRAINT schema_migration_version_check
        CHECK (version BETWEEN 1 AND 9999),
    CONSTRAINT schema_migration_filename_check
        CHECK (
            filename ~ '^[0-9]{4}_[a-z][a-z0-9_]*[.]sql$'
            AND pg_catalog.substring(filename, 1, 4)
                = pg_catalog.lpad(version::pg_catalog.text, 4, '0')
        ),
    CONSTRAINT schema_migration_source_sha256_check
        CHECK (source_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    CONSTRAINT schema_migration_source_length_check
        CHECK (source_byte_length > 0),
    CONSTRAINT schema_migration_prefix_digest_check
        CHECK (applied_prefix_digest ~ '^sha256:[0-9a-f]{64}$'),
    CONSTRAINT schema_migration_service_check
        CHECK (service_identity = 'ofarm.security-audit-postgresql.v1'),
    CONSTRAINT schema_migration_provisioning_digest_check
        CHECK (provisioning_spec_digest ~ '^sha256:[0-9a-f]{64}$'),
    CONSTRAINT schema_migration_release_check
        CHECK (release_identity ~ '^[!-~]{1,128}$'),
    CONSTRAINT schema_migration_execution_id_check
        CHECK (
            execution_id <>
            '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
        ),
    CONSTRAINT schema_migration_applied_at_check
        CHECK (
            applied_at <> 'infinity'::pg_catalog.timestamptz
            AND applied_at <> '-infinity'::pg_catalog.timestamptz
        )
);

CREATE FUNCTION "ofarm_security"."reject_schema_migration_mutation"() RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN RAISE EXCEPTION USING ERRCODE = ''55000'', MESSAGE = ''schema_migration is append-only''; END';

REVOKE ALL PRIVILEGES ON FUNCTION "ofarm_security"."reject_schema_migration_mutation"() FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TABLE "ofarm_security"."schema_migration" FROM PUBLIC;

CREATE TRIGGER "schema_migration_reject_update_delete"
BEFORE UPDATE OR DELETE ON "ofarm_security"."schema_migration"
FOR EACH ROW EXECUTE FUNCTION "ofarm_security"."reject_schema_migration_mutation"();

CREATE TRIGGER "schema_migration_reject_truncate"
BEFORE TRUNCATE ON "ofarm_security"."schema_migration"
FOR EACH STATEMENT EXECUTE FUNCTION "ofarm_security"."reject_schema_migration_mutation"();

GRANT SELECT (
    version,
    filename,
    source_sha256,
    source_byte_length,
    applied_prefix_digest,
    service_identity,
    provisioning_spec_digest
) ON TABLE "ofarm_security"."schema_migration" TO "ofarm_security_audit_readiness";

CREATE TYPE ofarm_security.operational_security_event_identity AS (
    event_id pg_catalog.uuid,
    observed_at pg_catalog.timestamptz,
    purge_after pg_catalog.timestamptz
);

CREATE TYPE ofarm_security.append_pretenant_failure_result AS (
    event_id pg_catalog.uuid,
    observed_at pg_catalog.timestamptz,
    purge_after pg_catalog.timestamptz,
    stored_individually pg_catalog.bool,
    overflow_bucket_start pg_catalog.timestamptz,
    overflow_count_unknown pg_catalog.bool
);

CREATE TYPE ofarm_security.audit_access_intent_result AS (
    access_event_id pg_catalog.uuid,
    data_cut pg_catalog.timestamptz,
    expires_at pg_catalog.timestamptz
);

CREATE TYPE ofarm_security.audit_retention_result AS (
    cutoff pg_catalog.timestamptz,
    deleted_count pg_catalog.int8,
    retention_event_id pg_catalog.uuid,
    observed_at pg_catalog.timestamptz,
    purge_after pg_catalog.timestamptz
);

CREATE TYPE ofarm_security.operational_security_event_report AS (
    event_id pg_catalog.uuid,
    observed_at pg_catalog.timestamptz,
    purge_after pg_catalog.timestamptz,
    event_kind pg_catalog.text,
    producer pg_catalog.text,
    component pg_catalog.text,
    reason pg_catalog.text,
    correlation_hmac_domain pg_catalog.text,
    correlation_hmac_key_version pg_catalog.int4,
    correlation_hmac_value pg_catalog.bytea,
    event_format_identity pg_catalog.text,
    redaction_policy_identity pg_catalog.text,
    retention_policy_identity pg_catalog.text,
    append_input_fingerprint pg_catalog.bytea,
    access_purpose pg_catalog.text,
    access_function_identity pg_catalog.text,
    access_data_cut pg_catalog.timestamptz,
    access_cursor_observed_at pg_catalog.timestamptz,
    access_cursor_event_id pg_catalog.uuid,
    access_max_rows pg_catalog.int4,
    access_max_bytes pg_catalog.int8,
    access_expires_at pg_catalog.timestamptz,
    retention_cutoff pg_catalog.timestamptz,
    retention_deleted_count pg_catalog.int8,
    interval_start pg_catalog.timestamptz,
    interval_end pg_catalog.timestamptz,
    interval_event_count pg_catalog.int8,
    interval_count_unknown pg_catalog.bool,
    affected_producer pg_catalog.text,
    affected_component pg_catalog.text
);

CREATE TYPE ofarm_security.security_audit_structure_report AS (
    structurally_compatible pg_catalog.bool,
    difference_count pg_catalog.int4,
    break_glass_login_present pg_catalog.bool
);

CREATE TYPE ofarm_security.security_audit_contract_observation AS (
    contract_identity pg_catalog.text,
    security_audit_contract_digest pg_catalog.text,
    event_format_identity pg_catalog.text,
    redaction_policy_identity pg_catalog.text,
    retention_policy_identity pg_catalog.text,
    correlation_hmac_domain pg_catalog.text,
    correlation_hmac_key_version pg_catalog.int4,
    service_identity pg_catalog.text,
    provisioning_spec_digest pg_catalog.text,
    migration_version pg_catalog.int4,
    migration_prefix_digest pg_catalog.text,
    structurally_compatible pg_catalog.bool,
    break_glass_login_present pg_catalog.bool
);

CREATE TABLE ofarm_security.operational_security_event (
    event_id pg_catalog.uuid NOT NULL,
    event_insert_xid pg_catalog.xid8 NOT NULL,
    observed_at pg_catalog.timestamptz NOT NULL,
    purge_after pg_catalog.timestamptz NOT NULL,
    event_kind pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    producer pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    component pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    reason pg_catalog.text COLLATE pg_catalog."C",
    correlation_hmac_domain pg_catalog.text COLLATE pg_catalog."C",
    correlation_hmac_key_version pg_catalog.int4,
    correlation_hmac_value pg_catalog.bytea,
    event_format_identity pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    redaction_policy_identity pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    retention_policy_identity pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    append_input_fingerprint pg_catalog.bytea NOT NULL,
    access_purpose pg_catalog.text COLLATE pg_catalog."C",
    access_function_identity pg_catalog.text COLLATE pg_catalog."C",
    access_data_cut pg_catalog.timestamptz,
    access_visibility_snapshot pg_catalog.pg_snapshot,
    access_cursor_observed_at pg_catalog.timestamptz,
    access_cursor_event_id pg_catalog.uuid,
    access_max_rows pg_catalog.int4,
    access_max_bytes pg_catalog.int8,
    access_expires_at pg_catalog.timestamptz,
    retention_cutoff pg_catalog.timestamptz,
    retention_deleted_count pg_catalog.int8,
    interval_start pg_catalog.timestamptz,
    interval_end pg_catalog.timestamptz,
    interval_event_count pg_catalog.int8,
    interval_count_unknown pg_catalog.bool,
    affected_producer pg_catalog.text COLLATE pg_catalog."C",
    affected_component pg_catalog.text COLLATE pg_catalog."C",

    CONSTRAINT operational_security_event_pkey PRIMARY KEY (event_id),
    CONSTRAINT operational_security_event_id_check CHECK (
        event_id <> '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
    ),
    CONSTRAINT operational_security_event_time_check CHECK (
        observed_at <> 'infinity'::pg_catalog.timestamptz
        AND observed_at <> '-infinity'::pg_catalog.timestamptz
        AND purge_after = observed_at + pg_catalog.make_interval(days => 30)
    ),
    CONSTRAINT operational_security_event_kind_check CHECK (
        event_kind IN (
            'PRE_TENANT_FAILURE', 'AUDIT_ACCESS', 'AUDIT_RETENTION',
            'AUDIT_GAP', 'OVERFLOW_STARTED', 'OVERFLOW_ENDED'
        )
    ),
    CONSTRAINT operational_security_event_policy_check CHECK (
        event_format_identity = 'OFARM_PRETENANT_SECURITY_EVENT_V1'
        AND redaction_policy_identity = 'CORRELATION_HMAC_ONLY_V1'
        AND retention_policy_identity = 'SECURITY_DIAGNOSTIC_30D_V1'
        AND pg_catalog.octet_length(append_input_fingerprint) = 32
    ),
    CONSTRAINT operational_security_event_principal_free_check CHECK (
        pg_catalog.octet_length(producer) BETWEEN 1 AND 64
        AND pg_catalog.octet_length(component) BETWEEN 1 AND 64
        AND (reason IS NULL OR pg_catalog.octet_length(reason) BETWEEN 1 AND 64)
    ),
    CONSTRAINT operational_security_event_pretenant_shape_check CHECK (
        (event_kind = 'PRE_TENANT_FAILURE') = (
            reason IS NOT NULL
            AND correlation_hmac_domain IS NOT NULL
            AND correlation_hmac_domain = 'OFARM_PRETENANT_CORRELATION_V1'
            AND correlation_hmac_key_version IS NOT NULL
            AND correlation_hmac_key_version = 1
            AND correlation_hmac_value IS NOT NULL
            AND pg_catalog.octet_length(correlation_hmac_value) = 32
        )
    ),
    CONSTRAINT operational_security_event_pretenant_attribution_check CHECK (
        event_kind <> 'PRE_TENANT_FAILURE'
        OR (
            producer = 'AUTHENTICATION_BOUNDARY_V1'
            AND component = 'AUTHENTICATION'
            AND reason IN (
                'CREDENTIAL_MISSING', 'CREDENTIAL_MALFORMED',
                'VERIFIER_UNAVAILABLE', 'VERIFICATION_REFUSED',
                'PRINCIPAL_BINDING_REFUSED', 'TENANT_PARTY_PIN_REFUSED',
                'CAPABILITY_REFUSED'
            )
        )
        OR (
            producer = 'REQUEST_ROUTER_BOUNDARY_V1'
            AND component = 'REQUEST_ROUTER'
            AND reason IN (
                'SECURITY_ROUTE_REFUSED', 'CAPABILITY_REFUSED',
                'BINDER_REFUSED', 'ACTOR_BINDING_REFUSED'
            )
        )
    ),
    CONSTRAINT operational_security_event_maintenance_hmac_check CHECK (
        event_kind = 'PRE_TENANT_FAILURE'
        OR (
            reason IS NULL
            AND correlation_hmac_domain IS NULL
            AND correlation_hmac_key_version IS NULL
            AND correlation_hmac_value IS NULL
        )
    ),
    CONSTRAINT operational_security_event_access_shape_check CHECK (
        (event_kind = 'AUDIT_ACCESS') = (
            access_purpose IS NOT NULL
            AND access_function_identity IS NOT NULL
            AND access_data_cut IS NOT NULL
            AND access_visibility_snapshot IS NOT NULL
            AND access_max_rows IS NOT NULL
            AND access_max_bytes IS NOT NULL
            AND access_expires_at IS NOT NULL
            AND access_expires_at = access_data_cut
                + pg_catalog.make_interval(secs => 300)
            AND ((access_cursor_observed_at IS NULL)
                = (access_cursor_event_id IS NULL))
        )
    ),
    CONSTRAINT operational_security_event_access_values_check CHECK (
        event_kind <> 'AUDIT_ACCESS'
        OR (
            producer = 'SECURITY_OPERATIONS_V1'
            AND component = 'AUDIT_CONTROL'
            AND (
                (
                    access_purpose = 'OPERATIONAL_DIAGNOSTIC_QUERY_V1'
                    AND access_function_identity =
                        'ofarm_security.query_operational_security_events(uuid, timestamptz, uuid, integer, bigint)'
                    AND access_max_rows BETWEEN 1 AND 256
                    AND access_max_bytes BETWEEN 1 AND 1048576
                )
                OR (
                    access_purpose = 'DUAL_APPROVED_BREAK_GLASS_EXPORT_V1'
                    AND access_function_identity =
                        'ofarm_security.export_operational_security_events(uuid, timestamptz, uuid, integer, bigint)'
                    AND access_max_rows BETWEEN 1 AND 2048
                    AND access_max_bytes BETWEEN 1 AND 8388608
                )
            )
        )
    ),
    CONSTRAINT operational_security_event_retention_shape_check CHECK (
        (event_kind = 'AUDIT_RETENTION') = (
            retention_cutoff IS NOT NULL
            AND retention_deleted_count IS NOT NULL
            AND retention_deleted_count BETWEEN 0 AND 1024
        )
    ),
    CONSTRAINT operational_security_event_retention_values_check CHECK (
        event_kind <> 'AUDIT_RETENTION'
        OR (
            producer = 'SECURITY_OPERATIONS_V1'
            AND component = 'AUDIT_RETENTION'
        )
    ),
    CONSTRAINT operational_security_event_interval_shape_check CHECK (
        (event_kind IN ('AUDIT_GAP', 'OVERFLOW_STARTED', 'OVERFLOW_ENDED')) = (
            interval_start IS NOT NULL
            AND interval_end IS NOT NULL
            AND interval_start < interval_end
            AND interval_start <> '-infinity'::pg_catalog.timestamptz
            AND interval_end <> 'infinity'::pg_catalog.timestamptz
            AND interval_count_unknown IS NOT NULL
        )
    ),
    CONSTRAINT operational_security_event_interval_count_check CHECK (
        event_kind NOT IN ('AUDIT_GAP', 'OVERFLOW_ENDED')
        OR (
            (interval_count_unknown AND interval_event_count IS NULL)
            OR (
                NOT interval_count_unknown
                AND interval_event_count IS NOT NULL
                AND interval_event_count >= 0
            )
        )
    ),
    CONSTRAINT operational_security_event_overflow_start_check CHECK (
        event_kind <> 'OVERFLOW_STARTED'
        OR (
            interval_count_unknown = false
            AND interval_event_count IS NULL
        )
    ),
    CONSTRAINT operational_security_event_interval_attribution_check CHECK (
        event_kind NOT IN ('AUDIT_GAP', 'OVERFLOW_STARTED', 'OVERFLOW_ENDED')
        OR (
            producer = 'SECURITY_OPERATIONS_V1'
            AND component = 'AUDIT_CONTROL'
            AND (
                (event_kind = 'AUDIT_GAP'
                    AND affected_producer IS NULL
                    AND affected_component IS NULL)
                OR (
                    event_kind IN ('OVERFLOW_STARTED', 'OVERFLOW_ENDED')
                    AND (
                        (affected_producer = 'AUTHENTICATION_BOUNDARY_V1'
                            AND affected_component = 'AUTHENTICATION')
                        OR
                        (affected_producer = 'REQUEST_ROUTER_BOUNDARY_V1'
                            AND affected_component = 'REQUEST_ROUTER')
                    )
                )
            )
        )
    ),
    CONSTRAINT operational_security_event_extension_absence_check CHECK (
        (event_kind = 'AUDIT_ACCESS' OR (
            access_purpose IS NULL
            AND access_function_identity IS NULL
            AND access_data_cut IS NULL
            AND access_visibility_snapshot IS NULL
            AND access_cursor_observed_at IS NULL
            AND access_cursor_event_id IS NULL
            AND access_max_rows IS NULL
            AND access_max_bytes IS NULL
            AND access_expires_at IS NULL
        ))
        AND (event_kind = 'AUDIT_RETENTION' OR (
            retention_cutoff IS NULL
            AND retention_deleted_count IS NULL
        ))
        AND (event_kind IN ('AUDIT_GAP', 'OVERFLOW_STARTED', 'OVERFLOW_ENDED') OR (
            interval_start IS NULL
            AND interval_end IS NULL
            AND interval_event_count IS NULL
            AND interval_count_unknown IS NULL
            AND affected_producer IS NULL
            AND affected_component IS NULL
        ))
    )
);

CREATE INDEX operational_security_event_live_order_idx
ON ofarm_security.operational_security_event (
    observed_at DESC,
    event_id DESC,
    purge_after
);

CREATE INDEX operational_security_event_purge_idx
ON ofarm_security.operational_security_event (purge_after, event_id);

CREATE TABLE ofarm_security.operational_security_quota_bucket (
    producer pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    component pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    bucket_start pg_catalog.timestamptz NOT NULL,
    accepted_event_count pg_catalog.int4 NOT NULL DEFAULT 0,
    overflow_event_count pg_catalog.int8 NOT NULL DEFAULT 0,
    overflow_started_at pg_catalog.timestamptz,
    count_unknown pg_catalog.bool NOT NULL DEFAULT false,

    CONSTRAINT operational_security_quota_bucket_pkey
        PRIMARY KEY (producer, component, bucket_start),
    CONSTRAINT operational_security_quota_bucket_attribution_check CHECK (
        (producer = 'AUTHENTICATION_BOUNDARY_V1'
            AND component = 'AUTHENTICATION')
        OR
        (producer = 'REQUEST_ROUTER_BOUNDARY_V1'
            AND component = 'REQUEST_ROUTER')
    ),
    CONSTRAINT operational_security_quota_bucket_start_check CHECK (
        bucket_start = pg_catalog.date_bin(
            pg_catalog.make_interval(secs => 60),
            bucket_start,
            '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
        )
    ),
    CONSTRAINT operational_security_quota_bucket_count_check CHECK (
        accepted_event_count BETWEEN 0 AND 1024
        AND overflow_event_count >= 0
    ),
    CONSTRAINT operational_security_quota_bucket_overflow_check CHECK (
        (overflow_started_at IS NULL OR accepted_event_count = 1024)
        AND (NOT count_unknown OR overflow_started_at IS NOT NULL)
    )
);

REVOKE ALL PRIVILEGES ON TABLE ofarm_security.operational_security_event FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TABLE ofarm_security.operational_security_quota_bucket FROM PUBLIC;

CREATE FUNCTION ofarm_security._event_fingerprint(
    VARIADIC p_fields pg_catalog.bytea[]
) RETURNS pg_catalog.bytea
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $fingerprint$
DECLARE
    v_field pg_catalog.bytea;
    v_framed pg_catalog.bytea :=
        pg_catalog.convert_to(
            'OFARM_PRETENANT_APPEND_INPUT_FINGERPRINT_V1', 'UTF8'
        ) || pg_catalog.decode('00', 'hex');
BEGIN
    FOREACH v_field IN ARRAY p_fields LOOP
        IF v_field IS NULL THEN
            v_framed := v_framed || pg_catalog.decode('00', 'hex');
        ELSE
            v_framed := v_framed
                || pg_catalog.decode('01', 'hex')
                || pg_catalog.int4send(pg_catalog.octet_length(v_field))
                || v_field;
        END IF;
    END LOOP;
    RETURN pg_catalog.sha256(v_framed);
END
$fingerprint$;

REVOKE ALL PRIVILEGES ON FUNCTION ofarm_security._event_fingerprint(
    VARIADIC pg_catalog.bytea[]
) FROM PUBLIC;

CREATE FUNCTION ofarm_security._pretenant_event_fingerprint(
    p_event_id pg_catalog.uuid,
    p_producer pg_catalog.text,
    p_component pg_catalog.text,
    p_reason pg_catalog.text,
    p_correlation_hmac_domain pg_catalog.text,
    p_correlation_hmac_key_version pg_catalog.int4,
    p_correlation_hmac pg_catalog.bytea
) RETURNS pg_catalog.bytea
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $pretenant_fingerprint$
SELECT ofarm_security._event_fingerprint(
    VARIADIC ARRAY[
        pg_catalog.uuid_send(p_event_id),
        pg_catalog.convert_to(p_producer, 'UTF8'),
        pg_catalog.convert_to(p_component, 'UTF8'),
        pg_catalog.convert_to('PRE_TENANT_FAILURE', 'UTF8'),
        pg_catalog.convert_to(p_reason, 'UTF8'),
        pg_catalog.convert_to(p_correlation_hmac_domain, 'UTF8'),
        pg_catalog.int4send(p_correlation_hmac_key_version),
        p_correlation_hmac,
        pg_catalog.convert_to('OFARM_PRETENANT_SECURITY_EVENT_V1', 'UTF8'),
        pg_catalog.convert_to('CORRELATION_HMAC_ONLY_V1', 'UTF8'),
        pg_catalog.convert_to('SECURITY_DIAGNOSTIC_30D_V1', 'UTF8'),
        NULL::pg_catalog.bytea, NULL::pg_catalog.bytea,
        NULL::pg_catalog.bytea, NULL::pg_catalog.bytea,
        NULL::pg_catalog.bytea, NULL::pg_catalog.bytea,
        NULL::pg_catalog.bytea, NULL::pg_catalog.bytea,
        NULL::pg_catalog.bytea, NULL::pg_catalog.bytea,
        NULL::pg_catalog.bytea, NULL::pg_catalog.bytea,
        NULL::pg_catalog.bytea, NULL::pg_catalog.bytea,
        NULL::pg_catalog.bytea, NULL::pg_catalog.bytea
    ]::pg_catalog.bytea[]
)
$pretenant_fingerprint$;

REVOKE ALL PRIVILEGES ON FUNCTION
ofarm_security._pretenant_event_fingerprint(
    pg_catalog.uuid, pg_catalog.text, pg_catalog.text, pg_catalog.text,
    pg_catalog.text, pg_catalog.int4, pg_catalog.bytea
) FROM PUBLIC;

CREATE FUNCTION ofarm_security._insert_maintenance_event(
    p_event_kind pg_catalog.text,
    p_component pg_catalog.text,
    p_access_purpose pg_catalog.text,
    p_access_function_identity pg_catalog.text,
    p_access_data_cut pg_catalog.timestamptz,
    p_access_cursor_observed_at pg_catalog.timestamptz,
    p_access_cursor_event_id pg_catalog.uuid,
    p_access_max_rows pg_catalog.int4,
    p_access_max_bytes pg_catalog.int8,
    p_access_expires_at pg_catalog.timestamptz,
    p_retention_cutoff pg_catalog.timestamptz,
    p_retention_deleted_count pg_catalog.int8,
    p_interval_start pg_catalog.timestamptz,
    p_interval_end pg_catalog.timestamptz,
    p_interval_event_count pg_catalog.int8,
    p_interval_count_unknown pg_catalog.bool,
    p_affected_producer pg_catalog.text,
    p_affected_component pg_catalog.text,
    p_access_visibility_snapshot pg_catalog.pg_snapshot
) RETURNS ofarm_security.operational_security_event_identity
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $maintenance$
DECLARE
    v_event_id pg_catalog.uuid;
    v_event_insert_xid pg_catalog.xid8;
    v_observed_at pg_catalog.timestamptz;
    v_purge_after pg_catalog.timestamptz;
    v_fingerprint pg_catalog.bytea;
BEGIN
    LOCK TABLE ofarm_security.operational_security_event
        IN ROW EXCLUSIVE MODE;
    v_event_id := pg_catalog.gen_random_uuid();
    v_event_insert_xid := pg_catalog.pg_current_xact_id();
    v_observed_at := pg_catalog.clock_timestamp();
    v_purge_after := v_observed_at + pg_catalog.make_interval(days => 30);
    v_fingerprint := ofarm_security._event_fingerprint(
        VARIADIC ARRAY[
            pg_catalog.uuid_send(v_event_id),
            pg_catalog.convert_to('SECURITY_OPERATIONS_V1', 'UTF8'),
            pg_catalog.convert_to(p_component, 'UTF8'),
            pg_catalog.convert_to(p_event_kind, 'UTF8'),
            NULL::pg_catalog.bytea,
            NULL::pg_catalog.bytea,
            NULL::pg_catalog.bytea,
            NULL::pg_catalog.bytea,
            pg_catalog.convert_to('OFARM_PRETENANT_SECURITY_EVENT_V1', 'UTF8'),
            pg_catalog.convert_to('CORRELATION_HMAC_ONLY_V1', 'UTF8'),
            pg_catalog.convert_to('SECURITY_DIAGNOSTIC_30D_V1', 'UTF8'),
            pg_catalog.convert_to(p_access_purpose, 'UTF8'),
            pg_catalog.convert_to(p_access_function_identity, 'UTF8'),
            pg_catalog.timestamptz_send(p_access_data_cut),
            pg_catalog.timestamptz_send(p_access_cursor_observed_at),
            pg_catalog.uuid_send(p_access_cursor_event_id),
            pg_catalog.int4send(p_access_max_rows),
            pg_catalog.int8send(p_access_max_bytes),
            pg_catalog.timestamptz_send(p_access_expires_at),
            pg_catalog.timestamptz_send(p_retention_cutoff),
            pg_catalog.int8send(p_retention_deleted_count),
            pg_catalog.timestamptz_send(p_interval_start),
            pg_catalog.timestamptz_send(p_interval_end),
            pg_catalog.int8send(p_interval_event_count),
            pg_catalog.boolsend(p_interval_count_unknown),
            pg_catalog.convert_to(p_affected_producer, 'UTF8'),
            pg_catalog.convert_to(p_affected_component, 'UTF8'),
            pg_catalog.convert_to(
                p_access_visibility_snapshot::pg_catalog.text, 'UTF8'
            )
        ]::pg_catalog.bytea[]
    );

    INSERT INTO ofarm_security.operational_security_event (
        event_id, event_insert_xid, observed_at, purge_after, event_kind,
        producer, component,
        reason, correlation_hmac_domain, correlation_hmac_key_version,
        correlation_hmac_value, event_format_identity,
        redaction_policy_identity, retention_policy_identity,
        append_input_fingerprint, access_purpose,
        access_function_identity, access_data_cut,
        access_visibility_snapshot,
        access_cursor_observed_at, access_cursor_event_id, access_max_rows,
        access_max_bytes, access_expires_at, retention_cutoff,
        retention_deleted_count, interval_start, interval_end,
        interval_event_count, interval_count_unknown, affected_producer,
        affected_component
    ) VALUES (
        v_event_id, v_event_insert_xid, v_observed_at, v_purge_after,
        p_event_kind,
        'SECURITY_OPERATIONS_V1', p_component, NULL, NULL, NULL, NULL,
        'OFARM_PRETENANT_SECURITY_EVENT_V1', 'CORRELATION_HMAC_ONLY_V1',
        'SECURITY_DIAGNOSTIC_30D_V1', v_fingerprint, p_access_purpose,
        p_access_function_identity, p_access_data_cut,
        p_access_visibility_snapshot,
        p_access_cursor_observed_at, p_access_cursor_event_id,
        p_access_max_rows, p_access_max_bytes, p_access_expires_at,
        p_retention_cutoff, p_retention_deleted_count, p_interval_start,
        p_interval_end, p_interval_event_count, p_interval_count_unknown,
        p_affected_producer, p_affected_component
    );

    RETURN ROW(v_event_id, v_observed_at, v_purge_after)::
        ofarm_security.operational_security_event_identity;
END
$maintenance$;

REVOKE ALL PRIVILEGES ON FUNCTION ofarm_security._insert_maintenance_event(
    pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.text,
    pg_catalog.timestamptz, pg_catalog.timestamptz, pg_catalog.uuid,
    pg_catalog.int4, pg_catalog.int8, pg_catalog.timestamptz,
    pg_catalog.timestamptz, pg_catalog.int8, pg_catalog.timestamptz,
    pg_catalog.timestamptz, pg_catalog.int8, pg_catalog.bool,
    pg_catalog.text, pg_catalog.text, pg_catalog.pg_snapshot
) FROM PUBLIC;

CREATE FUNCTION ofarm_security.append_pretenant_failure(
    p_event_id pg_catalog.uuid,
    p_reason pg_catalog.text,
    p_correlation_hmac pg_catalog.bytea,
    p_correlation_hmac_domain pg_catalog.text,
    p_correlation_hmac_key_version pg_catalog.int4
) RETURNS ofarm_security.append_pretenant_failure_result
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $append$
DECLARE
    v_producer pg_catalog.text;
    v_component pg_catalog.text;
    v_bucket_start pg_catalog.timestamptz;
    v_now pg_catalog.timestamptz;
    v_purge_after pg_catalog.timestamptz;
    v_fingerprint pg_catalog.bytea;
    v_existing ofarm_security.operational_security_event%ROWTYPE;
    v_bucket ofarm_security.operational_security_quota_bucket%ROWTYPE;
    v_marker ofarm_security.operational_security_event_identity;
BEGIN
    IF p_event_id IS NULL OR p_event_id =
            '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'pre-tenant event identity is invalid';
    END IF;
    IF p_reason IS NULL OR p_correlation_hmac IS NULL
            OR p_correlation_hmac_domain IS NULL
            OR p_correlation_hmac_key_version IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '22004',
            MESSAGE = 'pre-tenant event input is incomplete';
    END IF;
    IF 16 + pg_catalog.octet_length(p_reason)
            + pg_catalog.octet_length(p_correlation_hmac)
            + pg_catalog.octet_length(p_correlation_hmac_domain) + 4 > 4096 THEN
        RAISE EXCEPTION USING ERRCODE = '54000',
            MESSAGE = 'pre-tenant event input exceeds 4096 bytes';
    END IF;

    CASE session_user
        WHEN 'ofarm_security_authentication_producer_login' THEN
            v_producer := 'AUTHENTICATION_BOUNDARY_V1';
            v_component := 'AUTHENTICATION';
        WHEN 'ofarm_security_request_router_producer_login' THEN
            v_producer := 'REQUEST_ROUTER_BOUNDARY_V1';
            v_component := 'REQUEST_ROUTER';
        ELSE
            RAISE EXCEPTION USING ERRCODE = '42501',
                MESSAGE = 'session user is not an audit producer';
    END CASE;

    v_fingerprint := ofarm_security._pretenant_event_fingerprint(
        p_event_id, v_producer, v_component, p_reason,
        p_correlation_hmac_domain, p_correlation_hmac_key_version,
        p_correlation_hmac
    );

    SELECT * INTO v_existing
    FROM ofarm_security.operational_security_event
    WHERE event_id = p_event_id;

    IF FOUND THEN
        IF v_existing.event_kind <> 'PRE_TENANT_FAILURE'
                OR v_existing.producer <> v_producer
                OR v_existing.component <> v_component
                OR v_existing.reason IS DISTINCT FROM p_reason
                OR v_existing.correlation_hmac_domain IS DISTINCT FROM
                    p_correlation_hmac_domain
                OR v_existing.correlation_hmac_key_version IS DISTINCT FROM
                    p_correlation_hmac_key_version
                OR v_existing.correlation_hmac_value IS DISTINCT FROM
                    p_correlation_hmac
                OR v_existing.append_input_fingerprint IS DISTINCT FROM
                    v_fingerprint THEN
            RAISE EXCEPTION USING ERRCODE = '22000',
                MESSAGE = 'event identity was already used with different input';
        END IF;
        RETURN ROW(
            v_existing.event_id, v_existing.observed_at,
            v_existing.purge_after, true, NULL, false
        )::ofarm_security.append_pretenant_failure_result;
    END IF;

    IF p_correlation_hmac_domain <> 'OFARM_PRETENANT_CORRELATION_V1'
            OR p_correlation_hmac_key_version <> 1
            OR pg_catalog.octet_length(p_correlation_hmac) <> 32 THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'correlation HMAC policy is not active';
    END IF;
    IF NOT (
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
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'reason is not allowed for this producer';
    END IF;

    LOCK TABLE ofarm_security.operational_security_event
        IN ROW EXCLUSIVE MODE;
    v_now := pg_catalog.clock_timestamp();
    v_bucket_start := pg_catalog.date_bin(
        pg_catalog.make_interval(secs => 60),
        v_now,
        '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
    );
    INSERT INTO ofarm_security.operational_security_quota_bucket (
        producer, component, bucket_start
    ) VALUES (v_producer, v_component, v_bucket_start)
    ON CONFLICT (producer, component, bucket_start) DO NOTHING;

    SELECT * INTO STRICT v_bucket
    FROM ofarm_security.operational_security_quota_bucket
    WHERE producer = v_producer
      AND component = v_component
      AND bucket_start = v_bucket_start
    FOR UPDATE;

    SELECT * INTO v_existing
    FROM ofarm_security.operational_security_event
    WHERE event_id = p_event_id;
    IF FOUND THEN
        IF v_existing.event_kind <> 'PRE_TENANT_FAILURE'
                OR v_existing.producer <> v_producer
                OR v_existing.component <> v_component
                OR v_existing.reason IS DISTINCT FROM p_reason
                OR v_existing.correlation_hmac_domain IS DISTINCT FROM
                    p_correlation_hmac_domain
                OR v_existing.correlation_hmac_key_version IS DISTINCT FROM
                    p_correlation_hmac_key_version
                OR v_existing.correlation_hmac_value IS DISTINCT FROM
                    p_correlation_hmac
                OR v_existing.append_input_fingerprint IS DISTINCT FROM
                    v_fingerprint THEN
            RAISE EXCEPTION USING ERRCODE = '22000',
                MESSAGE = 'event identity was already used with different input';
        END IF;
        RETURN ROW(
            v_existing.event_id, v_existing.observed_at,
            v_existing.purge_after, true, NULL, false
        )::ofarm_security.append_pretenant_failure_result;
    END IF;

    IF v_bucket.accepted_event_count < 1024 THEN
        BEGIN
            UPDATE ofarm_security.operational_security_quota_bucket
            SET accepted_event_count = accepted_event_count + 1
            WHERE producer = v_producer
              AND component = v_component
              AND bucket_start = v_bucket_start;

            v_purge_after := v_now + pg_catalog.make_interval(days => 30);
            INSERT INTO ofarm_security.operational_security_event (
                event_id, event_insert_xid, observed_at, purge_after,
                event_kind, producer, component, reason,
                correlation_hmac_domain,
                correlation_hmac_key_version, correlation_hmac_value,
                event_format_identity, redaction_policy_identity,
                retention_policy_identity, append_input_fingerprint
            ) VALUES (
                p_event_id, pg_catalog.pg_current_xact_id(), v_now,
                v_purge_after, 'PRE_TENANT_FAILURE',
                v_producer, v_component, p_reason, p_correlation_hmac_domain,
                p_correlation_hmac_key_version, p_correlation_hmac,
                'OFARM_PRETENANT_SECURITY_EVENT_V1',
                'CORRELATION_HMAC_ONLY_V1', 'SECURITY_DIAGNOSTIC_30D_V1',
                v_fingerprint
            );
        EXCEPTION
            WHEN unique_violation THEN
                SELECT * INTO v_existing
                FROM ofarm_security.operational_security_event
                WHERE event_id = p_event_id;
                IF NOT FOUND THEN
                    RAISE;
                END IF;
                IF v_existing.event_kind <> 'PRE_TENANT_FAILURE'
                        OR v_existing.producer <> v_producer
                        OR v_existing.component <> v_component
                        OR v_existing.reason IS DISTINCT FROM p_reason
                        OR v_existing.correlation_hmac_domain IS DISTINCT FROM
                            p_correlation_hmac_domain
                        OR v_existing.correlation_hmac_key_version IS DISTINCT FROM
                            p_correlation_hmac_key_version
                        OR v_existing.correlation_hmac_value IS DISTINCT FROM
                            p_correlation_hmac
                        OR v_existing.append_input_fingerprint IS DISTINCT FROM
                            v_fingerprint THEN
                    RAISE EXCEPTION USING ERRCODE = '22000',
                        MESSAGE =
                            'event identity was already used with different input';
                END IF;
                RETURN ROW(
                    v_existing.event_id, v_existing.observed_at,
                    v_existing.purge_after, true, NULL, false
                )::ofarm_security.append_pretenant_failure_result;
        END;
        RETURN ROW(
            p_event_id, v_now, v_purge_after, true, NULL, false
        )::ofarm_security.append_pretenant_failure_result;
    END IF;

    IF v_bucket.overflow_started_at IS NULL THEN
        v_marker := ofarm_security._insert_maintenance_event(
            'OVERFLOW_STARTED', 'AUDIT_CONTROL', NULL, NULL, NULL, NULL,
            NULL, NULL, NULL, NULL, NULL, NULL, v_bucket_start,
            v_bucket_start + pg_catalog.make_interval(secs => 60),
            NULL, false, v_producer, v_component, NULL
        );
        UPDATE ofarm_security.operational_security_quota_bucket
        SET overflow_started_at = v_marker.observed_at
        WHERE producer = v_producer
          AND component = v_component
          AND bucket_start = v_bucket_start;
    END IF;

    IF v_bucket.count_unknown
            OR v_bucket.overflow_event_count = 9223372036854775807 THEN
        UPDATE ofarm_security.operational_security_quota_bucket
        SET count_unknown = true
        WHERE producer = v_producer
          AND component = v_component
          AND bucket_start = v_bucket_start;
    ELSE
        UPDATE ofarm_security.operational_security_quota_bucket
        SET overflow_event_count = overflow_event_count + 1
        WHERE producer = v_producer
          AND component = v_component
          AND bucket_start = v_bucket_start;
    END IF;

    SELECT * INTO STRICT v_bucket
    FROM ofarm_security.operational_security_quota_bucket
    WHERE producer = v_producer
      AND component = v_component
      AND bucket_start = v_bucket_start;
    RETURN ROW(
        NULL, NULL, NULL, false, v_bucket_start, v_bucket.count_unknown
    )::ofarm_security.append_pretenant_failure_result;
END
$append$;

REVOKE ALL PRIVILEGES ON FUNCTION ofarm_security.append_pretenant_failure(
    pg_catalog.uuid, pg_catalog.text, pg_catalog.bytea, pg_catalog.text,
    pg_catalog.int4
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ofarm_security.append_pretenant_failure(
    pg_catalog.uuid, pg_catalog.text, pg_catalog.bytea, pg_catalog.text,
    pg_catalog.int4
) TO ofarm_security_audit_ingest;

CREATE FUNCTION ofarm_security.commit_audit_access_intent(
    p_purpose pg_catalog.text,
    p_function_identity pg_catalog.text,
    p_cursor_observed_at pg_catalog.timestamptz,
    p_cursor_event_id pg_catalog.uuid,
    p_max_rows pg_catalog.int4,
    p_max_bytes pg_catalog.int8
) RETURNS ofarm_security.audit_access_intent_result
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $access_intent$
DECLARE
    v_data_cut pg_catalog.timestamptz;
    v_visibility_snapshot pg_catalog.pg_snapshot;
    v_expires_at pg_catalog.timestamptz;
    v_event ofarm_security.operational_security_event_identity;
BEGIN
    IF session_user <> 'ofarm_security_audit_control_login' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'session user is not the audit control operator';
    END IF;
    IF p_purpose IS NULL OR p_function_identity IS NULL
            OR p_max_rows IS NULL OR p_max_bytes IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '22004',
            MESSAGE = 'audit access intent is incomplete';
    END IF;
    IF (p_cursor_observed_at IS NULL) <> (p_cursor_event_id IS NULL)
            OR p_cursor_observed_at IN (
                'infinity'::pg_catalog.timestamptz,
                '-infinity'::pg_catalog.timestamptz
            )
            OR p_cursor_event_id =
                '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'audit access cursor is invalid';
    END IF;
    IF NOT (
        p_purpose = 'OPERATIONAL_DIAGNOSTIC_QUERY_V1'
        AND p_function_identity =
            'ofarm_security.query_operational_security_events(uuid, timestamptz, uuid, integer, bigint)'
        AND p_max_rows BETWEEN 1 AND 256
        AND p_max_bytes BETWEEN 1 AND 1048576
    ) AND NOT (
        p_purpose = 'DUAL_APPROVED_BREAK_GLASS_EXPORT_V1'
        AND p_function_identity =
            'ofarm_security.export_operational_security_events(uuid, timestamptz, uuid, integer, bigint)'
        AND p_max_rows BETWEEN 1 AND 2048
        AND p_max_bytes BETWEEN 1 AND 8388608
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'audit access purpose, function, or ceiling is invalid';
    END IF;
    IF pg_catalog.octet_length(p_purpose)
            + pg_catalog.octet_length(p_function_identity) + 44 > 4096 THEN
        RAISE EXCEPTION USING ERRCODE = '54000',
            MESSAGE = 'audit access input exceeds 4096 bytes';
    END IF;

    v_data_cut := pg_catalog.clock_timestamp();
    v_visibility_snapshot := pg_catalog.pg_current_snapshot();
    v_expires_at := v_data_cut + pg_catalog.make_interval(secs => 300);
    v_event := ofarm_security._insert_maintenance_event(
        'AUDIT_ACCESS', 'AUDIT_CONTROL', p_purpose, p_function_identity,
        v_data_cut, p_cursor_observed_at, p_cursor_event_id, p_max_rows,
        p_max_bytes, v_expires_at, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, v_visibility_snapshot
    );
    RETURN ROW(v_event.event_id, v_data_cut, v_expires_at)::
        ofarm_security.audit_access_intent_result;
END
$access_intent$;

REVOKE ALL PRIVILEGES ON FUNCTION ofarm_security.commit_audit_access_intent(
    pg_catalog.text, pg_catalog.text, pg_catalog.timestamptz,
    pg_catalog.uuid, pg_catalog.int4, pg_catalog.int8
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ofarm_security.commit_audit_access_intent(
    pg_catalog.text, pg_catalog.text, pg_catalog.timestamptz,
    pg_catalog.uuid, pg_catalog.int4, pg_catalog.int8
) TO ofarm_security_audit_control;

CREATE FUNCTION ofarm_security.append_audit_gap(
    p_interval_start pg_catalog.timestamptz,
    p_interval_end pg_catalog.timestamptz,
    p_event_count pg_catalog.int8,
    p_count_unknown pg_catalog.bool
) RETURNS ofarm_security.operational_security_event_identity
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $audit_gap$
DECLARE
    v_event ofarm_security.operational_security_event_identity;
BEGIN
    IF session_user <> 'ofarm_security_audit_control_login' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'session user is not the audit control operator';
    END IF;
    IF p_interval_start IS NULL OR p_interval_end IS NULL
            OR p_event_count IS NULL OR p_count_unknown IS NULL
            OR p_interval_start IN (
                'infinity'::pg_catalog.timestamptz,
                '-infinity'::pg_catalog.timestamptz
            )
            OR p_interval_end IN (
                'infinity'::pg_catalog.timestamptz,
                '-infinity'::pg_catalog.timestamptz
            )
            OR p_interval_start >= p_interval_end
            OR p_event_count < 0
            OR (p_count_unknown AND p_event_count <> 0) THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'audit gap interval or count is invalid';
    END IF;

    v_event := ofarm_security._insert_maintenance_event(
        'AUDIT_GAP', 'AUDIT_CONTROL', NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, p_interval_start, p_interval_end,
        CASE WHEN p_count_unknown THEN NULL ELSE p_event_count END,
        p_count_unknown, NULL, NULL, NULL
    );
    RETURN v_event;
END
$audit_gap$;

REVOKE ALL PRIVILEGES ON FUNCTION ofarm_security.append_audit_gap(
    pg_catalog.timestamptz, pg_catalog.timestamptz, pg_catalog.int8,
    pg_catalog.bool
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ofarm_security.append_audit_gap(
    pg_catalog.timestamptz, pg_catalog.timestamptz, pg_catalog.int8,
    pg_catalog.bool
) TO ofarm_security_audit_control;

CREATE FUNCTION ofarm_security.mark_overflow_count_unknown(
    p_producer pg_catalog.text,
    p_component pg_catalog.text,
    p_bucket_start pg_catalog.timestamptz
) RETURNS pg_catalog.void
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $overflow_unknown$
BEGIN
    IF session_user <> 'ofarm_security_audit_control_login' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'session user is not the audit control operator';
    END IF;
    IF p_bucket_start IS NULL OR p_bucket_start <> pg_catalog.date_bin(
        pg_catalog.make_interval(secs => 60), p_bucket_start,
        '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
    ) OR NOT (
        (p_producer = 'AUTHENTICATION_BOUNDARY_V1'
            AND p_component = 'AUTHENTICATION')
        OR
        (p_producer = 'REQUEST_ROUTER_BOUNDARY_V1'
            AND p_component = 'REQUEST_ROUTER')
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'overflow bucket identity is invalid';
    END IF;

    UPDATE ofarm_security.operational_security_quota_bucket
    SET count_unknown = true
    WHERE producer = p_producer
      AND component = p_component
      AND bucket_start = p_bucket_start
      AND overflow_started_at IS NOT NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'overflow bucket is not open';
    END IF;
END
$overflow_unknown$;

REVOKE ALL PRIVILEGES ON FUNCTION ofarm_security.mark_overflow_count_unknown(
    pg_catalog.text, pg_catalog.text, pg_catalog.timestamptz
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ofarm_security.mark_overflow_count_unknown(
    pg_catalog.text, pg_catalog.text, pg_catalog.timestamptz
) TO ofarm_security_audit_control;

CREATE FUNCTION ofarm_security.close_overflow_bucket(
    p_producer pg_catalog.text,
    p_component pg_catalog.text,
    p_bucket_start pg_catalog.timestamptz
) RETURNS ofarm_security.operational_security_event_identity
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $overflow_close$
DECLARE
    v_bucket ofarm_security.operational_security_quota_bucket%ROWTYPE;
    v_event ofarm_security.operational_security_event_identity;
    v_now_bucket pg_catalog.timestamptz;
BEGIN
    IF session_user <> 'ofarm_security_audit_control_login' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'session user is not the audit control operator';
    END IF;
    LOCK TABLE ofarm_security.operational_security_event
        IN SHARE ROW EXCLUSIVE MODE;
    v_now_bucket := pg_catalog.date_bin(
        pg_catalog.make_interval(secs => 60), pg_catalog.clock_timestamp(),
        '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
    );
    IF p_bucket_start IS NULL OR p_bucket_start >= v_now_bucket
            OR p_bucket_start <> pg_catalog.date_bin(
                pg_catalog.make_interval(secs => 60), p_bucket_start,
                '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
            ) OR NOT (
                (p_producer = 'AUTHENTICATION_BOUNDARY_V1'
                    AND p_component = 'AUTHENTICATION')
                OR
                (p_producer = 'REQUEST_ROUTER_BOUNDARY_V1'
                    AND p_component = 'REQUEST_ROUTER')
            ) THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'overflow bucket identity is invalid or still active';
    END IF;

    SELECT * INTO v_bucket
    FROM ofarm_security.operational_security_quota_bucket
    WHERE producer = p_producer
      AND component = p_component
      AND bucket_start = p_bucket_start
    FOR UPDATE;
    IF NOT FOUND THEN
        SELECT event_id, observed_at, purge_after INTO v_event
        FROM ofarm_security.operational_security_event
        WHERE event_kind = 'OVERFLOW_ENDED'
          AND affected_producer = p_producer
          AND affected_component = p_component
          AND interval_start = p_bucket_start
          AND interval_end = p_bucket_start
                + pg_catalog.make_interval(secs => 60)
        ORDER BY observed_at, event_id
        LIMIT 1;
        IF FOUND THEN
            RETURN v_event;
        END IF;
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'overflow bucket does not exist';
    END IF;
    IF v_bucket.overflow_started_at IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'quota bucket never entered overflow';
    END IF;

    v_event := ofarm_security._insert_maintenance_event(
        'OVERFLOW_ENDED', 'AUDIT_CONTROL', NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, p_bucket_start,
        p_bucket_start + pg_catalog.make_interval(secs => 60),
        CASE WHEN v_bucket.count_unknown
            THEN NULL ELSE v_bucket.overflow_event_count END,
        v_bucket.count_unknown, p_producer, p_component, NULL
    );
    DELETE FROM ofarm_security.operational_security_quota_bucket
    WHERE producer = p_producer
      AND component = p_component
      AND bucket_start = p_bucket_start;
    RETURN v_event;
END
$overflow_close$;

REVOKE ALL PRIVILEGES ON FUNCTION ofarm_security.close_overflow_bucket(
    pg_catalog.text, pg_catalog.text, pg_catalog.timestamptz
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ofarm_security.close_overflow_bucket(
    pg_catalog.text, pg_catalog.text, pg_catalog.timestamptz
) TO ofarm_security_audit_control;

CREATE FUNCTION ofarm_security._bounded_operational_security_events(
    p_access_event_id pg_catalog.uuid,
    p_cursor_observed_at pg_catalog.timestamptz,
    p_cursor_event_id pg_catalog.uuid,
    p_max_rows pg_catalog.int4,
    p_max_bytes pg_catalog.int8,
    p_expected_purpose pg_catalog.text,
    p_expected_function_identity pg_catalog.text
) RETURNS SETOF ofarm_security.operational_security_event_report
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $bounded_events$
DECLARE
    v_access ofarm_security.operational_security_event%ROWTYPE;
    v_report ofarm_security.operational_security_event_report;
    v_now pg_catalog.timestamptz := pg_catalog.clock_timestamp();
    v_row_bytes pg_catalog.int8;
    v_total_bytes pg_catalog.int8 := 0;
BEGIN
    IF p_access_event_id IS NULL
            OR p_access_event_id =
                '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
            OR p_max_rows IS NULL OR p_max_bytes IS NULL
            OR (p_cursor_observed_at IS NULL) <> (p_cursor_event_id IS NULL)
            OR p_cursor_observed_at IN (
                'infinity'::pg_catalog.timestamptz,
                '-infinity'::pg_catalog.timestamptz
            )
            OR p_cursor_event_id =
                '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'bounded audit query arguments are invalid';
    END IF;

    SELECT * INTO v_access
    FROM ofarm_security.operational_security_event
    WHERE event_id = p_access_event_id
      AND purge_after > v_now;
    IF NOT FOUND OR v_access.event_kind <> 'AUDIT_ACCESS'
            OR v_access.access_purpose <> p_expected_purpose
            OR v_access.access_function_identity <>
                p_expected_function_identity
            OR v_access.access_cursor_observed_at IS DISTINCT FROM
                p_cursor_observed_at
            OR v_access.access_cursor_event_id IS DISTINCT FROM
                p_cursor_event_id
            OR v_access.access_max_rows <> p_max_rows
            OR v_access.access_max_bytes <> p_max_bytes
            OR v_access.access_expires_at <= v_now THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'committed audit access intent is absent, expired, or unequal';
    END IF;

    FOR v_report IN
        SELECT
            e.event_id,
            e.observed_at,
            e.purge_after,
            e.event_kind,
            e.producer,
            e.component,
            e.reason,
            e.correlation_hmac_domain,
            e.correlation_hmac_key_version,
            e.correlation_hmac_value,
            e.event_format_identity,
            e.redaction_policy_identity,
            e.retention_policy_identity,
            e.append_input_fingerprint,
            e.access_purpose,
            e.access_function_identity,
            e.access_data_cut,
            e.access_cursor_observed_at,
            e.access_cursor_event_id,
            e.access_max_rows,
            e.access_max_bytes,
            e.access_expires_at,
            e.retention_cutoff,
            e.retention_deleted_count,
            e.interval_start,
            e.interval_end,
            e.interval_event_count,
            e.interval_count_unknown,
            e.affected_producer,
            e.affected_component
        FROM ofarm_security.operational_security_event AS e
        WHERE e.purge_after > v_now
          AND e.observed_at <= v_access.access_data_cut
          AND pg_catalog.pg_visible_in_snapshot(
              e.event_insert_xid, v_access.access_visibility_snapshot
          )
          AND (
              p_cursor_observed_at IS NULL
              OR (e.observed_at, e.event_id) <
                  (p_cursor_observed_at, p_cursor_event_id)
          )
        ORDER BY e.observed_at DESC, e.event_id DESC
        LIMIT p_max_rows
    LOOP
        v_row_bytes := pg_catalog.octet_length(
            pg_catalog.convert_to(
                pg_catalog.row_to_json(v_report)::pg_catalog.text,
                'UTF8'
            )
        );
        IF v_total_bytes + v_row_bytes > p_max_bytes THEN
            EXIT;
        END IF;
        v_total_bytes := v_total_bytes + v_row_bytes;
        RETURN NEXT v_report;
    END LOOP;
    RETURN;
END
$bounded_events$;

REVOKE ALL PRIVILEGES ON FUNCTION
ofarm_security._bounded_operational_security_events(
    pg_catalog.uuid, pg_catalog.timestamptz, pg_catalog.uuid,
    pg_catalog.int4, pg_catalog.int8, pg_catalog.text, pg_catalog.text
) FROM PUBLIC;

CREATE FUNCTION ofarm_security.query_operational_security_events(
    p_access_event_id pg_catalog.uuid,
    p_cursor_observed_at pg_catalog.timestamptz,
    p_cursor_event_id pg_catalog.uuid,
    p_max_rows pg_catalog.int4,
    p_max_bytes pg_catalog.int8
) RETURNS SETOF ofarm_security.operational_security_event_report
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $query_events$
BEGIN
    IF session_user <> 'ofarm_security_audit_reader_login' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'session user is not the bounded audit reader';
    END IF;
    IF p_max_rows NOT BETWEEN 1 AND 256
            OR p_max_bytes NOT BETWEEN 1 AND 1048576 THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'bounded audit query ceiling is invalid';
    END IF;
    RETURN QUERY
    SELECT *
    FROM ofarm_security._bounded_operational_security_events(
        p_access_event_id, p_cursor_observed_at, p_cursor_event_id,
        p_max_rows, p_max_bytes, 'OPERATIONAL_DIAGNOSTIC_QUERY_V1',
        'ofarm_security.query_operational_security_events(uuid, timestamptz, uuid, integer, bigint)'
    );
END
$query_events$;

REVOKE ALL PRIVILEGES ON FUNCTION
ofarm_security.query_operational_security_events(
    pg_catalog.uuid, pg_catalog.timestamptz, pg_catalog.uuid,
    pg_catalog.int4, pg_catalog.int8
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
ofarm_security.query_operational_security_events(
    pg_catalog.uuid, pg_catalog.timestamptz, pg_catalog.uuid,
    pg_catalog.int4, pg_catalog.int8
) TO ofarm_security_audit_reader;

CREATE FUNCTION ofarm_security.export_operational_security_events(
    p_access_event_id pg_catalog.uuid,
    p_cursor_observed_at pg_catalog.timestamptz,
    p_cursor_event_id pg_catalog.uuid,
    p_max_rows pg_catalog.int4,
    p_max_bytes pg_catalog.int8
) RETURNS SETOF ofarm_security.operational_security_event_report
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $export_events$
BEGIN
    IF session_user <> 'ofarm_security_audit_export_login' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'session user is not the approved break-glass exporter';
    END IF;
    IF p_max_rows NOT BETWEEN 1 AND 2048
            OR p_max_bytes NOT BETWEEN 1 AND 8388608 THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'bounded audit export ceiling is invalid';
    END IF;
    RETURN QUERY
    SELECT *
    FROM ofarm_security._bounded_operational_security_events(
        p_access_event_id, p_cursor_observed_at, p_cursor_event_id,
        p_max_rows, p_max_bytes, 'DUAL_APPROVED_BREAK_GLASS_EXPORT_V1',
        'ofarm_security.export_operational_security_events(uuid, timestamptz, uuid, integer, bigint)'
    );
END
$export_events$;

REVOKE ALL PRIVILEGES ON FUNCTION
ofarm_security.export_operational_security_events(
    pg_catalog.uuid, pg_catalog.timestamptz, pg_catalog.uuid,
    pg_catalog.int4, pg_catalog.int8
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
ofarm_security.export_operational_security_events(
    pg_catalog.uuid, pg_catalog.timestamptz, pg_catalog.uuid,
    pg_catalog.int4, pg_catalog.int8
) TO ofarm_security_audit_export;

CREATE FUNCTION ofarm_security.purge_expired_operational_security_events()
RETURNS ofarm_security.audit_retention_result
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $purge_events$
DECLARE
    v_cutoff pg_catalog.timestamptz := pg_catalog.clock_timestamp();
    v_deleted_count pg_catalog.int8;
    v_event ofarm_security.operational_security_event_identity;
BEGIN
    IF session_user <> 'ofarm_security_audit_retention_login' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'session user is not the audit retention operator';
    END IF;

    WITH victims AS (
        SELECT event.ctid
        FROM ofarm_security.operational_security_event AS event
        WHERE event.purge_after <= v_cutoff
        ORDER BY event.purge_after, event.event_id
        LIMIT 1024
        FOR UPDATE SKIP LOCKED
    ), deleted AS (
        DELETE FROM ofarm_security.operational_security_event AS event
        USING victims
        WHERE event.ctid = victims.ctid
        RETURNING 1
    )
    SELECT pg_catalog.count(*) INTO v_deleted_count FROM deleted;

    WITH stale_buckets AS (
        SELECT bucket.ctid
        FROM ofarm_security.operational_security_quota_bucket AS bucket
        WHERE bucket.overflow_started_at IS NULL
          AND bucket.bucket_start + pg_catalog.make_interval(secs => 60)
                <= v_cutoff
        ORDER BY bucket.bucket_start, bucket.producer, bucket.component
        LIMIT 1024
        FOR UPDATE SKIP LOCKED
    )
    DELETE FROM ofarm_security.operational_security_quota_bucket AS bucket
    USING stale_buckets
    WHERE bucket.ctid = stale_buckets.ctid;

    v_event := ofarm_security._insert_maintenance_event(
        'AUDIT_RETENTION', 'AUDIT_RETENTION', NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, v_cutoff, v_deleted_count, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL
    );
    RETURN ROW(
        v_cutoff, v_deleted_count, v_event.event_id, v_event.observed_at,
        v_event.purge_after
    )::ofarm_security.audit_retention_result;
END
$purge_events$;

REVOKE ALL PRIVILEGES ON FUNCTION
ofarm_security.purge_expired_operational_security_events() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
ofarm_security.purge_expired_operational_security_events()
TO ofarm_security_audit_retention;

CREATE FUNCTION ofarm_security.verify_security_audit_structure()
RETURNS ofarm_security.security_audit_structure_report
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
SET TimeZone = 'UTC'
SET DateStyle = 'ISO, MDY'
SET quote_all_identifiers = off
SET standard_conforming_strings = on
AS $verify_structure$
DECLARE
    v_differences pg_catalog.int4 := 0;
    v_break_glass_present pg_catalog.bool;
    v_catalog_fingerprint pg_catalog.text;
    v_names pg_catalog.text[];
    v_count pg_catalog.int8;
    v_invalid_count pg_catalog.int8;
    v_no_live_physical_replication pg_catalog.bool;
BEGIN
    IF session_user NOT IN (
        'ofarm_security_audit_readiness_login',
        'ofarm_migrator'
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'session user cannot verify the audit structure';
    END IF;

    SELECT pg_catalog.array_agg(
               database.datname::pg_catalog.text
               ORDER BY database.datname::pg_catalog.text
                        COLLATE pg_catalog."C"
           )
    INTO v_names
    FROM pg_catalog.pg_database AS database;
    IF v_names IS DISTINCT FROM ARRAY[
        'ofarm_security_audit', 'postgres', 'template0', 'template1'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(
               namespace.nspname::pg_catalog.text
               ORDER BY namespace.nspname::pg_catalog.text
                        COLLATE pg_catalog."C"
           )
    INTO v_names
    FROM pg_catalog.pg_namespace AS namespace;
    IF v_names IS DISTINCT FROM ARRAY[
        'information_schema',
        'ofarm_infrastructure',
        'ofarm_security',
        'pg_catalog',
        'pg_toast',
        'public'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*)
    INTO v_count
    FROM pg_catalog.pg_roles AS role
    CROSS JOIN pg_catalog.pg_database AS database
    WHERE role.rolname OPERATOR(pg_catalog.~) '^ofarm_'
      AND role.rolcanlogin
      AND (
          pg_catalog.has_database_privilege(
              role.oid, database.oid, 'CONNECT'
          ) IS DISTINCT FROM (database.datname = 'ofarm_security_audit')
          OR pg_catalog.has_database_privilege(
              role.oid, database.oid, 'TEMPORARY'
          ) IS DISTINCT FROM false
      );
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT
        (SELECT pg_catalog.count(*)
         FROM pg_catalog.pg_extension AS extension
         JOIN pg_catalog.pg_namespace AS namespace
           ON namespace.oid = extension.extnamespace
         JOIN pg_catalog.pg_roles AS owner
           ON owner.oid = extension.extowner
         WHERE NOT (
             extension.extname = 'plpgsql'
             AND extension.extversion = '1.0'
             AND namespace.nspname = 'pg_catalog'
             AND owner.rolsuper
             AND NOT extension.extrelocatable
             AND extension.extconfig IS NULL
             AND extension.extcondition IS NULL
         ))
        + (SELECT pg_catalog.count(*) FROM pg_catalog.pg_event_trigger)
        + (SELECT pg_catalog.count(*) FROM pg_catalog.pg_publication)
        + (SELECT pg_catalog.count(*) FROM pg_catalog.pg_subscription)
        + (SELECT pg_catalog.count(*) FROM pg_catalog.pg_foreign_data_wrapper)
        + (SELECT pg_catalog.count(*) FROM pg_catalog.pg_foreign_server)
        + (SELECT pg_catalog.count(*) FROM pg_catalog.pg_largeobject_metadata)
        + (SELECT pg_catalog.count(*) FROM pg_catalog.pg_transform)
        + (SELECT pg_catalog.count(*)
           FROM pg_catalog.pg_cast AS governed_cast
           WHERE governed_cast.oid >= 16384)
        + (SELECT pg_catalog.count(*)
           FROM pg_catalog.pg_am AS access_method
           WHERE access_method.oid >= 16384)
        + (SELECT pg_catalog.count(*)
           FROM pg_catalog.pg_language AS language
           WHERE language.oid >= 16384)
        + (SELECT pg_catalog.count(*)
           FROM pg_catalog.pg_tablespace AS tablespace
           WHERE tablespace.spcname NOT IN ('pg_default', 'pg_global'))
        + (SELECT pg_catalog.count(*) FROM pg_catalog.pg_replication_slots)
        + (SELECT pg_catalog.count(*) FROM pg_catalog.pg_prepared_xacts)
    INTO v_count;
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    -- PREPARED_TRANSACTION_STARTUP_POSTURE_V1
    IF pg_catalog.current_setting(
           'max_prepared_transactions'
       )::pg_catalog.int4 <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(class.relname::pg_catalog.text
            ORDER BY class.relname::pg_catalog.text)
    INTO v_names
    FROM pg_catalog.pg_class AS class
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    WHERE namespace.nspname = 'ofarm_security'
      AND class.relkind = 'r';
    IF v_names IS DISTINCT FROM ARRAY[
        'operational_security_event',
        'operational_security_quota_bucket',
        'schema_migration'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(class.relname::pg_catalog.text
            ORDER BY class.relname::pg_catalog.text)
    INTO v_names
    FROM pg_catalog.pg_class AS class
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    WHERE namespace.nspname = 'ofarm_security'
      AND class.relkind = 'i';
    IF v_names IS DISTINCT FROM ARRAY[
        'operational_security_event_live_order_idx',
        'operational_security_event_pkey',
        'operational_security_event_purge_idx',
        'operational_security_quota_bucket_pkey',
        'schema_migration_filename_key',
        'schema_migration_pkey'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(class.relname::pg_catalog.text
            ORDER BY class.relname::pg_catalog.text)
    INTO v_names
    FROM pg_catalog.pg_class AS class
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    WHERE namespace.nspname = 'ofarm_security'
      AND class.relkind = 'c';
    IF v_names IS DISTINCT FROM ARRAY[
        'append_pretenant_failure_result',
        'audit_access_intent_result',
        'audit_retention_result',
        'operational_security_event_identity',
        'operational_security_event_report',
        'security_audit_contract_observation',
        'security_audit_structure_report'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_class AS class
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    JOIN pg_catalog.pg_roles AS owner ON owner.oid = class.relowner
    WHERE namespace.nspname = 'ofarm_security'
      AND class.relkind IN ('r', 'i', 'c')
      AND (
          owner.rolname <> 'ofarm_security_audit_owner'
          OR class.relpersistence <> 'p'
          OR class.relkind = 'r' AND (
              class.relrowsecurity OR class.relforcerowsecurity
              OR class.relreplident <> 'd'
              OR class.reloptions IS NOT NULL
          )
      );
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(attribute.attname::pg_catalog.text
            ORDER BY attribute.attnum)
    INTO v_names
    FROM pg_catalog.pg_attribute AS attribute
    WHERE attribute.attrelid =
            'ofarm_security.operational_security_event'::pg_catalog.regclass
      AND attribute.attnum > 0
      AND NOT attribute.attisdropped;
    IF v_names IS DISTINCT FROM ARRAY[
        'event_id', 'event_insert_xid', 'observed_at', 'purge_after',
        'event_kind', 'producer', 'component', 'reason',
        'correlation_hmac_domain',
        'correlation_hmac_key_version', 'correlation_hmac_value',
        'event_format_identity', 'redaction_policy_identity',
        'retention_policy_identity', 'append_input_fingerprint',
        'access_purpose', 'access_function_identity', 'access_data_cut',
        'access_visibility_snapshot', 'access_cursor_observed_at',
        'access_cursor_event_id',
        'access_max_rows', 'access_max_bytes', 'access_expires_at',
        'retention_cutoff', 'retention_deleted_count', 'interval_start',
        'interval_end', 'interval_event_count', 'interval_count_unknown',
        'affected_producer', 'affected_component'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(attribute.attname::pg_catalog.text
            ORDER BY attribute.attnum)
    INTO v_names
    FROM pg_catalog.pg_attribute AS attribute
    WHERE attribute.attrelid =
            'ofarm_security.operational_security_quota_bucket'::pg_catalog.regclass
      AND attribute.attnum > 0
      AND NOT attribute.attisdropped;
    IF v_names IS DISTINCT FROM ARRAY[
        'producer', 'component', 'bucket_start', 'accepted_event_count',
        'overflow_event_count', 'overflow_started_at', 'count_unknown'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_attribute AS attribute
    JOIN pg_catalog.pg_class AS class ON class.oid = attribute.attrelid
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    WHERE namespace.nspname = 'ofarm_security'
      AND class.relname IN (
          'operational_security_event',
          'operational_security_quota_bucket'
      )
      AND attribute.attnum > 0
      AND NOT attribute.attisdropped
      AND attribute.atttypid = 'pg_catalog.text'::pg_catalog.regtype
      AND attribute.attcollation <>
          'pg_catalog."C"'::pg_catalog.regcollation;
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(con.conname::pg_catalog.text
            ORDER BY con.conname::pg_catalog.text)
    INTO v_names
    FROM pg_catalog.pg_constraint AS con
    WHERE con.conrelid =
        'ofarm_security.operational_security_event'::pg_catalog.regclass;
    IF v_names IS DISTINCT FROM ARRAY[
        'operational_security_event_access_shape_check',
        'operational_security_event_access_values_check',
        'operational_security_event_extension_absence_check',
        'operational_security_event_id_check',
        'operational_security_event_interval_attribution_check',
        'operational_security_event_interval_count_check',
        'operational_security_event_interval_shape_check',
        'operational_security_event_kind_check',
        'operational_security_event_maintenance_hmac_check',
        'operational_security_event_overflow_start_check',
        'operational_security_event_pkey',
        'operational_security_event_policy_check',
        'operational_security_event_pretenant_attribution_check',
        'operational_security_event_pretenant_shape_check',
        'operational_security_event_principal_free_check',
        'operational_security_event_retention_shape_check',
        'operational_security_event_retention_values_check',
        'operational_security_event_time_check'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(con.conname::pg_catalog.text
            ORDER BY con.conname::pg_catalog.text)
    INTO v_names
    FROM pg_catalog.pg_constraint AS con
    WHERE con.conrelid =
        'ofarm_security.operational_security_quota_bucket'::pg_catalog.regclass;
    IF v_names IS DISTINCT FROM ARRAY[
        'operational_security_quota_bucket_attribution_check',
        'operational_security_quota_bucket_count_check',
        'operational_security_quota_bucket_overflow_check',
        'operational_security_quota_bucket_pkey',
        'operational_security_quota_bucket_start_check'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_constraint AS con
    JOIN pg_catalog.pg_class AS class ON class.oid = con.conrelid
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    WHERE namespace.nspname = 'ofarm_security'
      AND class.relname IN (
          'operational_security_event',
          'operational_security_quota_bucket'
      )
      AND (
          NOT con.convalidated OR con.condeferrable
          OR con.condeferred OR (con.contype = 'c' AND con.connoinherit)
      );
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(routine.proname::pg_catalog.text
            ORDER BY routine.proname::pg_catalog.text)
    INTO v_names
    FROM pg_catalog.pg_proc AS routine
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = routine.pronamespace
    WHERE namespace.nspname = 'ofarm_security';
    IF v_names IS DISTINCT FROM ARRAY[
        '_bounded_operational_security_events',
        '_event_fingerprint',
        '_insert_maintenance_event',
        '_pretenant_event_fingerprint',
        'append_audit_gap',
        'append_pretenant_failure',
        'close_overflow_bucket',
        'commit_audit_access_intent',
        'export_operational_security_events',
        'mark_overflow_count_unknown',
        'observe_security_audit_contract',
        'purge_expired_operational_security_events',
        'query_operational_security_events',
        'reject_schema_migration_mutation',
        'verify_security_audit_structure'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    WITH expected(identity, result_type, grantee) AS (
        VALUES
        ('ofarm_security.append_pretenant_failure(uuid, text, bytea, text, integer)',
         'ofarm_security.append_pretenant_failure_result',
         'ofarm_security_audit_ingest'),
        ('ofarm_security.commit_audit_access_intent(text, text, timestamp with time zone, uuid, integer, bigint)',
         'ofarm_security.audit_access_intent_result',
         'ofarm_security_audit_control'),
        ('ofarm_security.append_audit_gap(timestamp with time zone, timestamp with time zone, bigint, boolean)',
         'ofarm_security.operational_security_event_identity',
         'ofarm_security_audit_control'),
        ('ofarm_security.mark_overflow_count_unknown(text, text, timestamp with time zone)',
         'void', 'ofarm_security_audit_control'),
        ('ofarm_security.close_overflow_bucket(text, text, timestamp with time zone)',
         'ofarm_security.operational_security_event_identity',
         'ofarm_security_audit_control'),
        ('ofarm_security.query_operational_security_events(uuid, timestamp with time zone, uuid, integer, bigint)',
         'SETOF ofarm_security.operational_security_event_report',
         'ofarm_security_audit_reader'),
        ('ofarm_security.export_operational_security_events(uuid, timestamp with time zone, uuid, integer, bigint)',
         'SETOF ofarm_security.operational_security_event_report',
         'ofarm_security_audit_export'),
        ('ofarm_security.purge_expired_operational_security_events()',
         'ofarm_security.audit_retention_result',
         'ofarm_security_audit_retention'),
        ('ofarm_security.observe_security_audit_contract()',
         'ofarm_security.security_audit_contract_observation',
         'ofarm_security_audit_readiness'),
        ('ofarm_security.verify_security_audit_structure()',
         'ofarm_security.security_audit_structure_report',
         'ofarm_security_audit_readiness')
    )
    SELECT pg_catalog.count(*) INTO v_count
    FROM expected
    LEFT JOIN pg_catalog.pg_proc AS routine
      ON routine.oid = pg_catalog.to_regprocedure(expected.identity)
    LEFT JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
    WHERE routine.oid IS NULL
       OR owner.rolname <> 'ofarm_security_audit_owner'
       OR NOT routine.prosecdef
       OR routine.proleakproof
       OR routine.proparallel <> 'u'
       OR routine.proconfig IS DISTINCT FROM
            CASE WHEN expected.identity =
                    'ofarm_security.verify_security_audit_structure()'
                 THEN ARRAY[
                    'search_path=pg_catalog, pg_temp',
                    'TimeZone=UTC',
                    'DateStyle=ISO, MDY',
                    'quote_all_identifiers=off',
                    'standard_conforming_strings=on'
                 ]::pg_catalog.text[]
                 ELSE ARRAY[
                    'search_path=pg_catalog, pg_temp'
                 ]::pg_catalog.text[]
            END
       OR pg_catalog.pg_get_function_result(routine.oid) <>
            expected.result_type
       OR NOT pg_catalog.has_function_privilege(
            expected.grantee, routine.oid, 'EXECUTE'
       );
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    WITH expected(identity, grantee) AS (
        VALUES
        ('ofarm_security.append_pretenant_failure(uuid, text, bytea, text, integer)',
         'ofarm_security_audit_ingest'),
        ('ofarm_security.commit_audit_access_intent(text, text, timestamp with time zone, uuid, integer, bigint)',
         'ofarm_security_audit_control'),
        ('ofarm_security.append_audit_gap(timestamp with time zone, timestamp with time zone, bigint, boolean)',
         'ofarm_security_audit_control'),
        ('ofarm_security.mark_overflow_count_unknown(text, text, timestamp with time zone)',
         'ofarm_security_audit_control'),
        ('ofarm_security.close_overflow_bucket(text, text, timestamp with time zone)',
         'ofarm_security_audit_control'),
        ('ofarm_security.query_operational_security_events(uuid, timestamp with time zone, uuid, integer, bigint)',
         'ofarm_security_audit_reader'),
        ('ofarm_security.export_operational_security_events(uuid, timestamp with time zone, uuid, integer, bigint)',
         'ofarm_security_audit_export'),
        ('ofarm_security.purge_expired_operational_security_events()',
         'ofarm_security_audit_retention'),
        ('ofarm_security.observe_security_audit_contract()',
         'ofarm_security_audit_readiness'),
        ('ofarm_security.verify_security_audit_structure()',
         'ofarm_security_audit_readiness')
    ), unexpected AS (
        SELECT expected.identity, acl.grantee
        FROM expected
        JOIN pg_catalog.pg_proc AS routine
          ON routine.oid = pg_catalog.to_regprocedure(expected.identity)
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                routine.proacl,
                pg_catalog.acldefault('f', routine.proowner)
            )
        ) AS acl
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        LEFT JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        WHERE acl.privilege_type = 'EXECUTE'
          AND COALESCE(grantee.rolname, 'PUBLIC') NOT IN (
              owner.rolname, expected.grantee
          )
    )
    SELECT pg_catalog.count(*) INTO v_count FROM unexpected;
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(role.rolname::pg_catalog.text
            ORDER BY role.rolname::pg_catalog.text)
    INTO v_names
    FROM pg_catalog.pg_roles AS role
    WHERE role.rolname::pg_catalog.text LIKE 'ofarm\_%' ESCAPE '\';
    IF v_names IS DISTINCT FROM ARRAY[
        'ofarm_migrator',
        'ofarm_security_audit_control',
        'ofarm_security_audit_control_login',
        'ofarm_security_audit_export',
        'ofarm_security_audit_ingest',
        'ofarm_security_audit_migration_lock_owner',
        'ofarm_security_audit_owner',
        'ofarm_security_audit_reader',
        'ofarm_security_audit_reader_login',
        'ofarm_security_audit_readiness',
        'ofarm_security_audit_readiness_login',
        'ofarm_security_audit_retention',
        'ofarm_security_audit_retention_login',
        'ofarm_security_authentication_producer_login',
        'ofarm_security_request_router_producer_login'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    WITH expected(
        role_name, can_login, inherits, bypasses_rls, connection_limit
    ) AS (
        VALUES
        ('ofarm_security_audit_owner', false, false, false, -1),
        ('ofarm_security_audit_migration_lock_owner', false, false, false, -1),
        ('ofarm_migrator', true, false, false, 2),
        ('ofarm_security_audit_ingest', false, false, false, -1),
        ('ofarm_security_audit_control', false, false, false, -1),
        ('ofarm_security_audit_reader', false, false, false, -1),
        ('ofarm_security_audit_export', false, false, false, -1),
        ('ofarm_security_audit_retention', false, false, false, -1),
        ('ofarm_security_audit_readiness', false, false, false, -1),
        ('ofarm_security_authentication_producer_login', true, true, false, 2),
        ('ofarm_security_request_router_producer_login', true, true, false, 4),
        ('ofarm_security_audit_control_login', true, true, false, 1),
        ('ofarm_security_audit_reader_login', true, true, false, 2),
        ('ofarm_security_audit_retention_login', true, true, false, 1),
        ('ofarm_security_audit_readiness_login', true, true, false, 2)
    )
    SELECT pg_catalog.count(*) INTO v_count
    FROM expected
    LEFT JOIN pg_catalog.pg_roles AS role
      ON role.rolname = expected.role_name
    WHERE role.oid IS NULL
       OR role.rolcanlogin IS DISTINCT FROM expected.can_login
       OR role.rolinherit IS DISTINCT FROM expected.inherits
       OR role.rolbypassrls IS DISTINCT FROM expected.bypasses_rls
       OR role.rolconnlimit IS DISTINCT FROM expected.connection_limit
       OR role.rolsuper OR role.rolcreatedb OR role.rolcreaterole
       OR role.rolreplication OR role.rolvaliduntil IS NOT NULL
       OR role.rolconfig IS NOT NULL;
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    WITH expected(
        granted_role, member_role, inherits, can_set_role, can_admin
    ) AS (
        VALUES
        ('ofarm_security_audit_owner', 'ofarm_migrator', false, true, false),
        ('ofarm_security_audit_ingest',
         'ofarm_security_authentication_producer_login', true, false, false),
        ('ofarm_security_audit_ingest',
         'ofarm_security_request_router_producer_login', true, false, false),
        ('ofarm_security_audit_control',
         'ofarm_security_audit_control_login', true, false, false),
        ('ofarm_security_audit_reader',
         'ofarm_security_audit_reader_login', true, false, false),
        ('ofarm_security_audit_retention',
         'ofarm_security_audit_retention_login', true, false, false),
        ('ofarm_security_audit_readiness',
         'ofarm_security_audit_readiness_login', true, false, false)
    ), actual AS (
        SELECT granted.rolname::pg_catalog.text AS granted_role,
               member.rolname::pg_catalog.text AS member_role,
               membership.inherit_option AS inherits,
               membership.set_option AS can_set_role,
               membership.admin_option AS can_admin
        FROM pg_catalog.pg_auth_members AS membership
        JOIN pg_catalog.pg_roles AS granted
          ON granted.oid = membership.roleid
        JOIN pg_catalog.pg_roles AS member
          ON member.oid = membership.member
        WHERE granted.rolname::pg_catalog.text LIKE 'ofarm\_%' ESCAPE '\'
           OR member.rolname::pg_catalog.text LIKE 'ofarm\_%' ESCAPE '\'
    ), differences AS (
        SELECT COALESCE(expected.granted_role, actual.granted_role)
        FROM expected
        FULL JOIN actual
          ON actual.granted_role = expected.granted_role
         AND actual.member_role = expected.member_role
        WHERE expected.granted_role IS NULL
           OR actual.granted_role IS NULL
           OR actual.inherits IS DISTINCT FROM expected.inherits
           OR actual.can_set_role IS DISTINCT FROM expected.can_set_role
           OR actual.can_admin IS DISTINCT FROM expected.can_admin
    )
    SELECT pg_catalog.count(*) INTO v_count FROM differences;
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_proc AS routine
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = routine.pronamespace
    WHERE namespace.nspname = 'ofarm_security'
      AND routine.proname = 'append_pretenant_failure'
      AND pg_catalog.sha256(
            pg_catalog.convert_to(routine.prosrc, 'UTF8')
          ) = pg_catalog.decode(
            '27890717ec304d2aeda00aac949f3df6f9e2dc2ca32210e167b0d8f24ea0111a',
            'hex'
          );
    IF v_count <> 1 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_policy AS policy
    JOIN pg_catalog.pg_class AS class ON class.oid = policy.polrelid
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    WHERE namespace.nspname = 'ofarm_security';
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_trigger AS trigger
    JOIN pg_catalog.pg_class AS class ON class.oid = trigger.tgrelid
    WHERE class.oid IN (
        'ofarm_security.operational_security_event'::pg_catalog.regclass,
        'ofarm_security.operational_security_quota_bucket'::pg_catalog.regclass
    ) AND NOT trigger.tgisinternal;
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_class AS class
    CROSS JOIN LATERAL pg_catalog.aclexplode(
        COALESCE(class.relacl, pg_catalog.acldefault('r', class.relowner))
    ) AS acl
    WHERE class.oid IN (
        'ofarm_security.operational_security_event'::pg_catalog.regclass,
        'ofarm_security.operational_security_quota_bucket'::pg_catalog.regclass
    )
      AND acl.grantee <> class.relowner;
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM ofarm_security.schema_migration
    WHERE version = 1
      AND filename = '0001_initial.sql'
      AND service_identity = 'ofarm.security-audit-postgresql.v1'
      AND provisioning_spec_digest =
          'sha256:770165332bbdb7a5e67e468f021d9fe82df817a2aee1a8a70191a08e869c307a'
      AND source_sha256 ~ '^sha256:[0-9a-f]{64}$'
      AND applied_prefix_digest ~ '^sha256:[0-9a-f]{64}$';
    IF v_count <> 1 OR (SELECT pg_catalog.count(*)
                        FROM ofarm_security.schema_migration) <> 1 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.to_regrole(
        'ofarm_security_audit_export_login'
    ) IS NOT NULL INTO v_break_glass_present;
    IF v_break_glass_present
            OR pg_catalog.to_regrole(
                'ofarm_security_audit_backup_reader'
            ) IS NOT NULL
            OR pg_catalog.to_regrole(
                'ofarm_security_audit_restore_operator'
            ) IS NOT NULL THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_auth_members AS membership
    WHERE membership.roleid =
        'ofarm_security_audit_export'::pg_catalog.regrole;
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT
        (SELECT pg_catalog.count(*) FROM pg_catalog.pg_publication)
        + (SELECT pg_catalog.count(*) FROM pg_catalog.pg_subscription
           WHERE subdbid = (SELECT oid FROM pg_catalog.pg_database
                            WHERE datname = pg_catalog.current_database()))
        + (SELECT pg_catalog.count(*) FROM pg_catalog.pg_replication_slots
           WHERE database = pg_catalog.current_database())
    INTO v_count;
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT NOT EXISTS (
            SELECT 1
            FROM pg_catalog.pg_stat_get_wal_senders()
        )
        AND NOT EXISTS (
            SELECT 1
            FROM pg_catalog.pg_stat_get_wal_receiver() AS receiver
            WHERE receiver.pid IS NOT NULL
        )
    INTO v_no_live_physical_replication;
    IF NOT v_no_live_physical_replication THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(
               routine.proname::pg_catalog.text || '(' ||
               pg_catalog.pg_get_function_identity_arguments(routine.oid) || ')'
               ORDER BY (
                   routine.proname::pg_catalog.text || '(' ||
                   pg_catalog.pg_get_function_identity_arguments(routine.oid) || ')'
               ) COLLATE pg_catalog."C"
           )
    INTO v_names
    FROM pg_catalog.pg_proc AS routine
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = routine.pronamespace
    WHERE namespace.nspname = 'pg_catalog'
      AND (
        pg_catalog.left(routine.proname::pg_catalog.text, 3) = 'lo_'
        OR routine.proname IN ('loread', 'lowrite')
      );
    IF v_names IS DISTINCT FROM ARRAY[
        'lo_close(integer)',
        'lo_creat(integer)',
        'lo_create(oid)',
        'lo_export(oid, text)',
        'lo_from_bytea(oid, bytea)',
        'lo_get(oid)',
        'lo_get(oid, bigint, integer)',
        'lo_import(text)',
        'lo_import(text, oid)',
        'lo_lseek(integer, integer, integer)',
        'lo_lseek64(integer, bigint, integer)',
        'lo_open(oid, integer)',
        'lo_put(oid, bigint, bytea)',
        'lo_tell(integer)',
        'lo_tell64(integer)',
        'lo_truncate(integer, integer)',
        'lo_truncate64(integer, bigint)',
        'lo_unlink(oid)',
        'loread(integer, integer)',
        'lowrite(integer, bytea)'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_largeobject_metadata;
    IF v_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*) INTO v_count
    FROM pg_catalog.pg_class AS class
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    JOIN pg_catalog.pg_roles AS owner ON owner.oid = class.relowner
    WHERE namespace.nspname = 'pg_catalog'
      AND class.relname = 'pg_stat_activity'
      AND class.relkind = 'v'
      AND class.relpersistence = 'p'
      AND owner.rolsuper
      AND NOT class.relispartition
      AND NOT class.relrowsecurity
      AND NOT class.relforcerowsecurity;
    IF v_count <> 1 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*),
           pg_catalog.count(*) FILTER (
               WHERE NOT owner.rolsuper
                  OR acl.grantor <> class.relowner
                  OR acl.grantee <> class.relowner
                  OR acl.privilege_type NOT IN (
                      'DELETE',
                      'INSERT',
                      'MAINTAIN',
                      'REFERENCES',
                      'SELECT',
                      'TRIGGER',
                      'TRUNCATE',
                      'UPDATE'
                  )
                  OR acl.is_grantable
           )
    INTO v_count, v_invalid_count
    FROM pg_catalog.pg_class AS class
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    JOIN pg_catalog.pg_roles AS owner ON owner.oid = class.relowner
    CROSS JOIN LATERAL pg_catalog.aclexplode(
        COALESCE(
            class.relacl,
            pg_catalog.acldefault('r', class.relowner)
        )
    ) AS acl
    WHERE namespace.nspname = 'pg_catalog'
      AND class.relname = 'pg_stat_activity'
      AND class.relkind = 'v';
    IF v_count <> 8 OR v_invalid_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.array_agg(
               routine.proname::pg_catalog.text || '(' ||
                   pg_catalog.oidvectortypes(routine.proargtypes) || ')'
               ORDER BY
                   routine.proname COLLATE pg_catalog."C",
                   pg_catalog.oidvectortypes(routine.proargtypes)
                       COLLATE pg_catalog."C"
           )
    INTO v_names
    FROM pg_catalog.pg_proc AS routine
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = routine.pronamespace
    WHERE namespace.nspname = 'pg_catalog'
      AND pg_catalog.left(
              routine.proname::pg_catalog.text, 20
          ) IN ('pg_stat_get_activity', 'pg_stat_get_backend_');
    IF v_names IS DISTINCT FROM ARRAY[
        'pg_stat_get_activity(integer)',
        'pg_stat_get_backend_activity(integer)',
        'pg_stat_get_backend_activity_start(integer)',
        'pg_stat_get_backend_client_addr(integer)',
        'pg_stat_get_backend_client_port(integer)',
        'pg_stat_get_backend_dbid(integer)',
        'pg_stat_get_backend_idset()',
        'pg_stat_get_backend_pid(integer)',
        'pg_stat_get_backend_start(integer)',
        'pg_stat_get_backend_subxact(integer)',
        'pg_stat_get_backend_userid(integer)',
        'pg_stat_get_backend_wait_event(integer)',
        'pg_stat_get_backend_wait_event_type(integer)',
        'pg_stat_get_backend_xact_start(integer)'
    ]::pg_catalog.text[] THEN
        v_differences := v_differences + 1;
    END IF;

    SELECT pg_catalog.count(*),
           pg_catalog.count(*) FILTER (
               WHERE NOT owner.rolsuper
                  OR acl.grantor <> routine.proowner
                  OR acl.grantee <> routine.proowner
                  OR acl.privilege_type <> 'EXECUTE'
                  OR acl.is_grantable
           )
    INTO v_count, v_invalid_count
    FROM pg_catalog.pg_proc AS routine
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = routine.pronamespace
    JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
    CROSS JOIN LATERAL pg_catalog.aclexplode(
        COALESCE(
            routine.proacl,
            pg_catalog.acldefault('f', routine.proowner)
        )
    ) AS acl
    WHERE namespace.nspname = 'pg_catalog'
      AND pg_catalog.left(
              routine.proname::pg_catalog.text, 20
          ) IN ('pg_stat_get_activity', 'pg_stat_get_backend_');
    IF v_count <> 14 OR v_invalid_count <> 0 THEN
        v_differences := v_differences + 1;
    END IF;

    WITH governed_schema(schema_name) AS (
        VALUES
            ('ofarm_security'::pg_catalog.text),
            ('ofarm_infrastructure'::pg_catalog.text),
            ('public'::pg_catalog.text)
    ),
    catalog_entry(category, object_identity, definition) AS (
        SELECT
            'role',
            role.rolname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                role.rolsuper,
                role.rolinherit,
                role.rolcreaterole,
                role.rolcreatedb,
                role.rolcanlogin,
                role.rolreplication,
                role.rolconnlimit,
                role.rolbypassrls,
                role.rolvaliduntil,
                role.rolconfig
            )::pg_catalog.text
        FROM pg_catalog.pg_roles AS role
        WHERE role.rolname OPERATOR(pg_catalog.~) '^ofarm_'

        UNION ALL
        SELECT
            'membership',
            granted.rolname::pg_catalog.text || ':' ||
                member.rolname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                CASE WHEN grantor.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE grantor.rolname::pg_catalog.text END,
                membership.inherit_option,
                membership.set_option,
                membership.admin_option
            )::pg_catalog.text
        FROM pg_catalog.pg_auth_members AS membership
        JOIN pg_catalog.pg_roles AS granted
          ON granted.oid = membership.roleid
        JOIN pg_catalog.pg_roles AS member
          ON member.oid = membership.member
        JOIN pg_catalog.pg_roles AS grantor
          ON grantor.oid = membership.grantor
        WHERE granted.rolname OPERATOR(pg_catalog.~) '^ofarm_'
           OR member.rolname OPERATOR(pg_catalog.~) '^ofarm_'

        UNION ALL
        SELECT
            'database',
            database.datname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                owner.rolname,
                pg_catalog.pg_encoding_to_char(database.encoding),
                database.datlocprovider,
                database.datcollate,
                database.datctype,
                database.datlocale,
                database.daticurules,
                database.datcollversion,
                database.datistemplate,
                database.datallowconn,
                database.datconnlimit,
                tablespace.spcname,
                database.datacl IS NULL
            )::pg_catalog.text
        FROM pg_catalog.pg_database AS database
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = database.datdba
        JOIN pg_catalog.pg_tablespace AS tablespace
          ON tablespace.oid = database.dattablespace
        WHERE database.datname = 'ofarm_security_audit'

        UNION ALL
        SELECT
            'database-acl',
            database.datname::pg_catalog.text || ':' ||
                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                     ELSE grantee.rolname::pg_catalog.text END || ':' ||
                acl.privilege_type,
            pg_catalog.jsonb_build_array(
                acl.is_grantable,
                grantor.rolname
            )::pg_catalog.text
        FROM pg_catalog.pg_database AS database
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                database.datacl,
                pg_catalog.acldefault('d', database.datdba)
            )
        ) AS acl
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
        WHERE database.datname = 'ofarm_security_audit'

        UNION ALL
        SELECT
            'role-setting',
            CASE WHEN role_setting.setdatabase = 0 THEN 'ALL_DATABASES'
                 ELSE database.datname::pg_catalog.text END || ':' ||
                CASE WHEN role_setting.setrole = 0 THEN 'ALL_ROLES'
                     ELSE role.rolname::pg_catalog.text END || ':' || setting.value,
            '[]'::pg_catalog.text
        FROM pg_catalog.pg_db_role_setting AS role_setting
        LEFT JOIN pg_catalog.pg_database AS database
          ON database.oid = role_setting.setdatabase
        LEFT JOIN pg_catalog.pg_roles AS role ON role.oid = role_setting.setrole
        CROSS JOIN LATERAL pg_catalog.unnest(
            role_setting.setconfig
        ) AS setting(value)
        WHERE database.datname = 'ofarm_security_audit'
           OR role.rolname OPERATOR(pg_catalog.~) '^ofarm_'
           OR (
                role_setting.setdatabase = 0
                AND role_setting.setrole = 0
           )

        UNION ALL
        SELECT
            'schema',
            namespace.nspname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                owner.rolname,
                namespace.nspacl IS NULL
            )::pg_catalog.text
        FROM pg_catalog.pg_namespace AS namespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = namespace.nspowner
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )

        UNION ALL
        SELECT
            'schema-acl',
            namespace.nspname::pg_catalog.text || ':' ||
                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                     ELSE grantee.rolname::pg_catalog.text END || ':' ||
                acl.privilege_type,
            pg_catalog.jsonb_build_array(
                acl.is_grantable,
                grantor.rolname
            )::pg_catalog.text
        FROM pg_catalog.pg_namespace AS namespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                namespace.nspacl,
                pg_catalog.acldefault('n', namespace.nspowner)
            )
        ) AS acl
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )

        UNION ALL
        SELECT
            'relation',
            namespace.nspname::pg_catalog.text || '.' ||
                class.relname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                owner.rolname,
                class.relkind,
                class.relpersistence,
                access_method.amname,
                tablespace.spcname,
                class.relrowsecurity,
                class.relforcerowsecurity,
                class.relhasrules,
                class.relreplident,
                class.relispartition,
                class.reloptions,
                class.relacl IS NULL,
                pg_catalog.pg_get_expr(class.relpartbound, class.oid)
            )::pg_catalog.text
        FROM pg_catalog.pg_class AS class
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = class.relnamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = class.relowner
        LEFT JOIN pg_catalog.pg_am AS access_method
          ON access_method.oid = class.relam
        LEFT JOIN pg_catalog.pg_tablespace AS tablespace
          ON tablespace.oid = class.reltablespace
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )

        UNION ALL
        -- GOVERNED_RELATION_REWRITE_RULE_V1
        SELECT
            'rewrite-rule',
            namespace.nspname::pg_catalog.text || '.' ||
                class.relname::pg_catalog.text || ':' ||
                rewrite_rule.rulename::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                rewrite_rule.ev_type,
                rewrite_rule.ev_enabled,
                rewrite_rule.is_instead,
                pg_catalog.pg_get_ruledef(rewrite_rule.oid, false)
            )::pg_catalog.text
        FROM pg_catalog.pg_rewrite AS rewrite_rule
        JOIN pg_catalog.pg_class AS class
          ON class.oid = rewrite_rule.ev_class
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = class.relnamespace
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )
          AND class.relkind IN ('r', 'p', 'v', 'm', 'f')

        UNION ALL
        SELECT
            'column',
            namespace.nspname::pg_catalog.text || '.' ||
                class.relname::pg_catalog.text || ':' ||
                attribute.attnum::pg_catalog.text || ':' ||
                attribute.attname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                pg_catalog.format_type(attribute.atttypid, attribute.atttypmod),
                attribute.attnotnull,
                attribute.attidentity,
                attribute.attgenerated,
                attribute.attstorage,
                attribute.attcompression,
                attribute.attstattarget,
                attribute.attinhcount,
                attribute.attislocal,
                attribute.attoptions,
                attribute.attacl IS NULL,
                CASE WHEN attribute.attcollation = 0 THEN NULL
                     ELSE attribute.attcollation::pg_catalog.regcollation::pg_catalog.text END,
                pg_catalog.pg_get_expr(default_value.adbin, default_value.adrelid)
            )::pg_catalog.text
        FROM pg_catalog.pg_attribute AS attribute
        JOIN pg_catalog.pg_class AS class ON class.oid = attribute.attrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = class.relnamespace
        LEFT JOIN pg_catalog.pg_attrdef AS default_value
          ON default_value.adrelid = attribute.attrelid
         AND default_value.adnum = attribute.attnum
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )
          AND attribute.attnum > 0
          AND NOT attribute.attisdropped

        UNION ALL
        SELECT
            'type',
            namespace.nspname::pg_catalog.text || '.' ||
                type.typname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                owner.rolname,
                type.typtype,
                type.typcategory,
                type.typispreferred,
                type.typisdefined,
                type.typdelim,
                type.typlen,
                type.typbyval,
                type.typalign,
                type.typstorage,
                type.typnotnull,
                type.typbasetype::pg_catalog.regtype::pg_catalog.text,
                type.typtypmod,
                type.typndims,
                type.typcollation::pg_catalog.regcollation::pg_catalog.text,
                type.typdefault,
                type.typinput::pg_catalog.regproc::pg_catalog.text,
                type.typoutput::pg_catalog.regproc::pg_catalog.text,
                type.typreceive::pg_catalog.regproc::pg_catalog.text,
                type.typsend::pg_catalog.regproc::pg_catalog.text,
                CASE WHEN type.typrelid = 0 THEN NULL
                     ELSE type.typrelid::pg_catalog.regclass::pg_catalog.text END,
                type.typacl IS NULL
            )::pg_catalog.text
        FROM pg_catalog.pg_type AS type
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = type.typnamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = type.typowner
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )

        UNION ALL
        SELECT
            'enum',
            namespace.nspname::pg_catalog.text || '.' ||
                type.typname::pg_catalog.text || ':' ||
                enum.enumsortorder::pg_catalog.text,
            pg_catalog.to_jsonb(enum.enumlabel)::pg_catalog.text
        FROM pg_catalog.pg_enum AS enum
        JOIN pg_catalog.pg_type AS type ON type.oid = enum.enumtypid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = type.typnamespace
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )

        UNION ALL
        SELECT
            'constraint',
            namespace.nspname::pg_catalog.text || '.' ||
                CASE WHEN governed_constraint.conrelid = 0
                     THEN governed_type.typname::pg_catalog.text
                     ELSE governed_relation.relname::pg_catalog.text END ||
                ':' || governed_constraint.conname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                governed_constraint.contype,
                governed_constraint.condeferrable,
                governed_constraint.condeferred,
                governed_constraint.convalidated,
                governed_constraint.connoinherit,
                pg_catalog.pg_get_constraintdef(
                    governed_constraint.oid, false
                )
            )::pg_catalog.text
        FROM pg_catalog.pg_constraint AS governed_constraint
        LEFT JOIN pg_catalog.pg_class AS governed_relation
          ON governed_relation.oid = governed_constraint.conrelid
        LEFT JOIN pg_catalog.pg_type AS governed_type
          ON governed_type.oid = governed_constraint.contypid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = governed_constraint.connamespace
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )

        UNION ALL
        SELECT
            'index',
            namespace.nspname::pg_catalog.text || '.' ||
                index_class.relname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                table_class.relname,
                owner.rolname,
                governed_index.indisunique,
                governed_index.indisprimary,
                governed_index.indisexclusion,
                governed_index.indimmediate,
                governed_index.indisclustered,
                governed_index.indisvalid,
                governed_index.indcheckxmin,
                governed_index.indisready,
                governed_index.indislive,
                governed_index.indisreplident,
                pg_catalog.pg_get_indexdef(index_class.oid)
            )::pg_catalog.text
        FROM pg_catalog.pg_index AS governed_index
        JOIN pg_catalog.pg_class AS index_class
          ON index_class.oid = governed_index.indexrelid
        JOIN pg_catalog.pg_class AS table_class
          ON table_class.oid = governed_index.indrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = table_class.relnamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = index_class.relowner
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )

        UNION ALL
        SELECT
            'trigger',
            namespace.nspname::pg_catalog.text || '.' ||
                class.relname::pg_catalog.text || ':' ||
                trigger.tgname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                trigger.tgenabled,
                trigger.tgdeferrable,
                trigger.tginitdeferred,
                pg_catalog.pg_get_triggerdef(trigger.oid, false)
            )::pg_catalog.text
        FROM pg_catalog.pg_trigger AS trigger
        JOIN pg_catalog.pg_class AS class ON class.oid = trigger.tgrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = class.relnamespace
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )
          AND NOT trigger.tgisinternal

        UNION ALL
        SELECT
            'policy',
            namespace.nspname::pg_catalog.text || '.' ||
                class.relname::pg_catalog.text || ':' ||
                policy.polname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                policy.polpermissive,
                policy.polcmd,
                ARRAY(
                    SELECT CASE WHEN policy_role.oid = 0 THEN 'PUBLIC'
                                ELSE governed_role.rolname::pg_catalog.text END
                    FROM pg_catalog.unnest(policy.polroles) AS policy_role(oid)
                    LEFT JOIN pg_catalog.pg_roles AS governed_role
                      ON governed_role.oid = policy_role.oid
                    ORDER BY
                        (CASE WHEN policy_role.oid = 0 THEN 'PUBLIC'
                              ELSE governed_role.rolname::pg_catalog.text END)
                        COLLATE pg_catalog."C"
                ),
                pg_catalog.pg_get_expr(policy.polqual, policy.polrelid),
                pg_catalog.pg_get_expr(policy.polwithcheck, policy.polrelid)
            )::pg_catalog.text
        FROM pg_catalog.pg_policy AS policy
        JOIN pg_catalog.pg_class AS class ON class.oid = policy.polrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = class.relnamespace
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )

        UNION ALL
        SELECT
            'routine',
            namespace.nspname::pg_catalog.text || '.' ||
                routine.proname::pg_catalog.text || '(' ||
                pg_catalog.pg_get_function_identity_arguments(routine.oid) || ')',
            pg_catalog.jsonb_build_array(
                owner.rolname,
                language.lanname,
                routine.prokind,
                routine.prosecdef,
                routine.proleakproof,
                routine.proisstrict,
                routine.provolatile,
                routine.proparallel,
                routine.proretset,
                pg_catalog.pg_get_function_arguments(routine.oid),
                pg_catalog.pg_get_function_result(routine.oid),
                routine.proconfig,
                routine.procost,
                routine.prorows,
                routine.prosupport::pg_catalog.regproc::pg_catalog.text,
                routine.probin,
                routine.proacl IS NULL,
                CASE WHEN namespace.nspname = 'ofarm_security'
                           AND routine.proname =
                                'verify_security_audit_structure'
                           AND pg_catalog.pg_get_function_identity_arguments(
                                routine.oid
                           ) = ''
                     THEN 'SELF_SOURCE_EXCLUDED'
                     ELSE routine.prosrc END
            )::pg_catalog.text
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )

        UNION ALL
        SELECT
            'routine-acl',
            namespace.nspname::pg_catalog.text || '.' ||
                routine.proname::pg_catalog.text || '(' ||
                pg_catalog.pg_get_function_identity_arguments(routine.oid) || '):' ||
                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                     ELSE grantee.rolname::pg_catalog.text END || ':' ||
                acl.privilege_type,
            pg_catalog.jsonb_build_array(
                acl.is_grantable,
                grantor.rolname
            )::pg_catalog.text
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = routine.pronamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                routine.proacl,
                pg_catalog.acldefault('f', routine.proowner)
            )
        ) AS acl
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )

        UNION ALL
        SELECT
            'type-acl',
            namespace.nspname::pg_catalog.text || '.' ||
                type.typname::pg_catalog.text || ':' ||
                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                     ELSE grantee.rolname::pg_catalog.text END || ':' ||
                acl.privilege_type,
            pg_catalog.jsonb_build_array(
                acl.is_grantable,
                grantor.rolname
            )::pg_catalog.text
        FROM pg_catalog.pg_type AS type
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = type.typnamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                type.typacl,
                pg_catalog.acldefault('T', type.typowner)
            )
        ) AS acl
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )

        UNION ALL
        SELECT
            'relation-acl',
            namespace.nspname::pg_catalog.text || '.' ||
                class.relname::pg_catalog.text || ':' ||
                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                     ELSE grantee.rolname::pg_catalog.text END || ':' ||
                acl.privilege_type,
            pg_catalog.jsonb_build_array(
                acl.is_grantable,
                grantor.rolname
            )::pg_catalog.text
        FROM pg_catalog.pg_class AS class
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = class.relnamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                class.relacl,
                pg_catalog.acldefault(
                    CASE WHEN class.relkind = 'S' THEN 'S'::pg_catalog."char"
                         ELSE 'r'::pg_catalog."char" END,
                    class.relowner
                )
            )
        ) AS acl
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )
          AND class.relkind IN ('r', 'p', 'S', 'v', 'm', 'f')

        UNION ALL
        SELECT
            'column-acl',
            namespace.nspname::pg_catalog.text || '.' ||
                class.relname::pg_catalog.text || ':' ||
                attribute.attname::pg_catalog.text || ':' ||
                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                     ELSE grantee.rolname::pg_catalog.text END || ':' ||
                acl.privilege_type,
            pg_catalog.jsonb_build_array(
                acl.is_grantable,
                grantor.rolname
            )::pg_catalog.text
        FROM pg_catalog.pg_attribute AS attribute
        JOIN pg_catalog.pg_class AS class ON class.oid = attribute.attrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = class.relnamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) AS acl
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
        WHERE namespace.nspname IN (
            'ofarm_security', 'ofarm_infrastructure', 'public'
        )
          AND attribute.attnum > 0
          AND NOT attribute.attisdropped

        UNION ALL
        SELECT
            'default-acl',
            owner.rolname::pg_catalog.text || ':' ||
                COALESCE(namespace.nspname::pg_catalog.text, '') || ':' ||
                default_acl.defaclobjtype::pg_catalog.text || ':' ||
                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                     ELSE grantee.rolname::pg_catalog.text END || ':' ||
                acl.privilege_type,
            pg_catalog.jsonb_build_array(
                acl.is_grantable,
                grantor.rolname
            )::pg_catalog.text
        FROM pg_catalog.pg_default_acl AS default_acl
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = default_acl.defaclrole
        LEFT JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = default_acl.defaclnamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            default_acl.defaclacl
        ) AS acl
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
        WHERE owner.rolname OPERATOR(pg_catalog.~) '^ofarm_'
           OR namespace.nspname IN (
                'ofarm_security', 'ofarm_infrastructure', 'public'
           )

        UNION ALL
        SELECT
            'parameter-acl',
            'pg_catalog.pg_parameter_acl',
            COALESCE(
                pg_catalog.jsonb_agg(
                    pg_catalog.jsonb_build_array(
                        parameter.parname,
                        parameter.paracl IS NULL,
                        CASE WHEN acl.grantee IS NULL THEN NULL
                             WHEN acl.grantee = 0 THEN 'PUBLIC'
                             WHEN grantee.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                             ELSE grantee.rolname::pg_catalog.text END,
                        acl.privilege_type,
                        acl.is_grantable,
                        CASE WHEN acl.grantor IS NULL THEN NULL
                             WHEN grantor.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                             ELSE grantor.rolname::pg_catalog.text END
                    )
                    ORDER BY
                        parameter.parname COLLATE pg_catalog."C",
                        (CASE WHEN acl.grantee IS NULL THEN NULL
                              WHEN acl.grantee = 0 THEN 'PUBLIC'
                              WHEN grantee.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                              ELSE grantee.rolname::pg_catalog.text END)
                            COLLATE pg_catalog."C",
                        acl.privilege_type COLLATE pg_catalog."C",
                        acl.is_grantable,
                        (CASE WHEN acl.grantor IS NULL THEN NULL
                              WHEN grantor.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                              ELSE grantor.rolname::pg_catalog.text END)
                            COLLATE pg_catalog."C"
                ) FILTER (WHERE parameter.parname IS NOT NULL),
                '[]'::pg_catalog.jsonb
            )::pg_catalog.text
        FROM pg_catalog.pg_parameter_acl AS parameter
        LEFT JOIN LATERAL pg_catalog.aclexplode(
            parameter.paracl
        ) AS acl ON true
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        LEFT JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor

        UNION ALL
        SELECT
            'extension',
            extension.extname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                extension.extversion,
                CASE WHEN owner.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE owner.rolname::pg_catalog.text END,
                namespace.nspname
            )::pg_catalog.text
        FROM pg_catalog.pg_extension AS extension
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = extension.extowner
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = extension.extnamespace

        UNION ALL
        SELECT
            'collation',
            namespace.nspname::pg_catalog.text || '.' ||
                governed_collation.collname::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                governed_collation.collprovider,
                governed_collation.collisdeterministic,
                governed_collation.collencoding,
                governed_collation.collcollate,
                governed_collation.collctype,
                governed_collation.colllocale,
                governed_collation.collicurules,
                governed_collation.collversion
            )::pg_catalog.text
        FROM pg_catalog.pg_collation AS governed_collation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = governed_collation.collnamespace
        WHERE namespace.nspname = 'pg_catalog'
          AND governed_collation.collname IN ('C', 'default')

        UNION ALL
        SELECT
            'advisory-routine-acl',
            routine.proname::pg_catalog.text || '(' ||
                pg_catalog.pg_get_function_identity_arguments(routine.oid) || '):' ||
                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                     WHEN grantee.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE grantee.rolname::pg_catalog.text END || ':' ||
                acl.privilege_type,
            pg_catalog.jsonb_build_array(
                acl.is_grantable,
                CASE WHEN grantor.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE grantor.rolname::pg_catalog.text END
            )::pg_catalog.text
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = routine.pronamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                routine.proacl,
                pg_catalog.acldefault('f', routine.proowner)
            )
        ) AS acl
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
        WHERE namespace.nspname = 'pg_catalog'
          AND routine.proname IN (
            'pg_advisory_lock',
            'pg_advisory_lock_shared',
            'pg_advisory_unlock',
            'pg_advisory_unlock_all',
            'pg_advisory_unlock_shared',
            'pg_advisory_xact_lock',
            'pg_advisory_xact_lock_shared',
            'pg_try_advisory_lock',
            'pg_try_advisory_lock_shared',
            'pg_try_advisory_xact_lock',
            'pg_try_advisory_xact_lock_shared'
          )

        UNION ALL
        SELECT
            'backend-statistics-view',
            'pg_catalog.pg_stat_activity',
            pg_catalog.jsonb_build_array(
                CASE WHEN owner.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE owner.rolname::pg_catalog.text END,
                class.relkind,
                class.relpersistence,
                class.relispartition,
                class.relrowsecurity,
                class.relforcerowsecurity,
                class.relhasrules,
                class.relhastriggers,
                class.relhassubclass,
                class.relhasindex,
                class.relnatts,
                class.relchecks,
                class.relreplident,
                class.reloptions,
                class.relispopulated,
                class.relrewrite = 0,
                class.relam = 0,
                class.reltablespace = 0,
                pg_catalog.pg_get_viewdef(class.oid, false)
            )::pg_catalog.text
        FROM pg_catalog.pg_class AS class
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = class.relnamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = class.relowner
        WHERE namespace.nspname = 'pg_catalog'
          AND class.relname = 'pg_stat_activity'

        UNION ALL
        SELECT
            'backend-statistics-view-columns',
            'pg_catalog.pg_stat_activity',
            pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_array(
                    attribute.attnum,
                    attribute.attname,
                    pg_catalog.format_type(
                        attribute.atttypid, attribute.atttypmod
                    ),
                    attribute.attnotnull,
                    attribute.attidentity,
                    attribute.attgenerated,
                    attribute.attstorage,
                    attribute.attcompression,
                    attribute.attstattarget,
                    attribute.attoptions,
                    CASE WHEN attribute.attcollation = 0 THEN NULL
                         ELSE attribute.attcollation::pg_catalog.regcollation::pg_catalog.text END,
                    attribute.attinhcount,
                    attribute.attislocal,
                    attribute.atthasdef,
                    attribute.atthasmissing,
                    pg_catalog.pg_get_expr(
                        default_value.adbin, default_value.adrelid
                    )
                )
                ORDER BY attribute.attnum
            )::pg_catalog.text
        FROM pg_catalog.pg_attribute AS attribute
        JOIN pg_catalog.pg_class AS class ON class.oid = attribute.attrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = class.relnamespace
        LEFT JOIN pg_catalog.pg_attrdef AS default_value
          ON default_value.adrelid = attribute.attrelid
         AND default_value.adnum = attribute.attnum
        WHERE namespace.nspname = 'pg_catalog'
          AND class.relname = 'pg_stat_activity'
          AND attribute.attnum > 0
          AND NOT attribute.attisdropped
        GROUP BY class.oid

        UNION ALL
        SELECT
            'backend-statistics-view-rewrite',
            'pg_catalog.pg_stat_activity:' ||
                rewrite.rulename::pg_catalog.text,
            pg_catalog.jsonb_build_array(
                rewrite.ev_type,
                rewrite.ev_enabled,
                rewrite.is_instead,
                pg_catalog.pg_get_ruledef(rewrite.oid, false)
            )::pg_catalog.text
        FROM pg_catalog.pg_rewrite AS rewrite
        JOIN pg_catalog.pg_class AS class ON class.oid = rewrite.ev_class
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = class.relnamespace
        WHERE namespace.nspname = 'pg_catalog'
          AND class.relname = 'pg_stat_activity'

        UNION ALL
        SELECT
            'backend-statistics-view-acl',
            'pg_catalog.pg_stat_activity:' ||
                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                     WHEN grantee.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE grantee.rolname::pg_catalog.text END || ':' ||
                acl.privilege_type,
            pg_catalog.jsonb_build_array(
                acl.is_grantable,
                CASE WHEN grantor.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE grantor.rolname::pg_catalog.text END
            )::pg_catalog.text
        FROM pg_catalog.pg_class AS class
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = class.relnamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                class.relacl,
                pg_catalog.acldefault('r', class.relowner)
            )
        ) AS acl
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
        WHERE namespace.nspname = 'pg_catalog'
          AND class.relname = 'pg_stat_activity'
          AND class.relkind = 'v'

        UNION ALL
        SELECT
            'backend-statistics-routine',
            routine.proname::pg_catalog.text || '(' ||
                pg_catalog.pg_get_function_identity_arguments(routine.oid) || ')',
            pg_catalog.jsonb_build_array(
                CASE WHEN owner.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE owner.rolname::pg_catalog.text END,
                language.lanname,
                routine.prokind,
                routine.prosecdef,
                routine.proleakproof,
                routine.proisstrict,
                routine.provolatile,
                routine.proparallel,
                routine.proretset,
                pg_catalog.pg_get_function_result(routine.oid),
                routine.pronargs,
                routine.pronargdefaults,
                pg_catalog.pg_get_function_arguments(routine.oid),
                pg_catalog.pg_get_function_identity_arguments(routine.oid),
                routine.prosrc,
                routine.probin,
                routine.proconfig,
                routine.procost,
                routine.prorows,
                routine.prosupport = 0,
                routine.prosqlbody IS NULL
            )::pg_catalog.text
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
        WHERE namespace.nspname = 'pg_catalog'
          AND pg_catalog.left(
                  routine.proname::pg_catalog.text, 20
              ) IN ('pg_stat_get_activity', 'pg_stat_get_backend_')

        UNION ALL
        SELECT
            'backend-statistics-routine-acl',
            routine.proname::pg_catalog.text || '(' ||
                pg_catalog.pg_get_function_identity_arguments(routine.oid) || '):' ||
                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                     WHEN grantee.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE grantee.rolname::pg_catalog.text END || ':' ||
                acl.privilege_type,
            pg_catalog.jsonb_build_array(
                acl.is_grantable,
                CASE WHEN grantor.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE grantor.rolname::pg_catalog.text END
            )::pg_catalog.text
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = routine.pronamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                routine.proacl,
                pg_catalog.acldefault('f', routine.proowner)
            )
        ) AS acl
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
        WHERE namespace.nspname = 'pg_catalog'
          AND pg_catalog.left(
                  routine.proname::pg_catalog.text, 20
              ) IN ('pg_stat_get_activity', 'pg_stat_get_backend_')

        UNION ALL
        SELECT
            'large-object-routine',
            routine.proname::pg_catalog.text || '(' ||
                pg_catalog.pg_get_function_identity_arguments(routine.oid) || ')',
            pg_catalog.jsonb_build_array(
                CASE WHEN owner.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE owner.rolname::pg_catalog.text END,
                language.lanname,
                routine.prokind,
                routine.prosecdef,
                routine.proleakproof,
                routine.proisstrict,
                routine.provolatile,
                routine.proparallel,
                routine.proretset,
                pg_catalog.pg_get_function_result(routine.oid),
                routine.pronargs,
                routine.pronargdefaults,
                pg_catalog.pg_get_function_arguments(routine.oid),
                pg_catalog.pg_get_function_identity_arguments(routine.oid),
                routine.prosrc,
                routine.probin,
                routine.proconfig,
                routine.procost,
                routine.prorows,
                routine.prosupport = 0,
                routine.prosqlbody IS NULL,
                routine.proacl IS NULL
            )::pg_catalog.text
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = routine.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
        WHERE namespace.nspname = 'pg_catalog'
          AND (
            pg_catalog.left(routine.proname::pg_catalog.text, 3) = 'lo_'
            OR routine.proname IN ('loread', 'lowrite')
          )

        UNION ALL
        SELECT
            'large-object-routine-acl',
            routine.proname::pg_catalog.text || '(' ||
                pg_catalog.pg_get_function_identity_arguments(routine.oid) || '):' ||
                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                     WHEN grantee.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE grantee.rolname::pg_catalog.text END || ':' ||
                acl.privilege_type,
            pg_catalog.jsonb_build_array(
                acl.is_grantable,
                CASE WHEN grantor.rolsuper THEN 'BOOTSTRAP_SUPERUSER'
                     ELSE grantor.rolname::pg_catalog.text END
            )::pg_catalog.text
        FROM pg_catalog.pg_proc AS routine
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = routine.pronamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(
                routine.proacl,
                pg_catalog.acldefault('f', routine.proowner)
            )
        ) AS acl
        LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
        JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
        WHERE namespace.nspname = 'pg_catalog'
          AND (
            pg_catalog.left(routine.proname::pg_catalog.text, 3) = 'lo_'
            OR routine.proname IN ('loread', 'lowrite')
          )

        -- SCHEMA_LOCAL_CATALOG_CLASSIFIER_V1
        -- Keep this block in exact parity with catalog_classifier.py.
        UNION ALL
        SELECT
            'schema-local-relation',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.relname::pg_catalog.text,
            'pg_catalog.pg_class'
        FROM pg_catalog.pg_class AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.relnamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )

        UNION ALL
        SELECT
            'schema-local-routine',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.proname::pg_catalog.text,
            'pg_catalog.pg_proc'
        FROM pg_catalog.pg_proc AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.pronamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )

        UNION ALL
        SELECT
            'schema-local-type',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.typname::pg_catalog.text,
            'pg_catalog.pg_type'
        FROM pg_catalog.pg_type AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.typnamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )

        UNION ALL
        SELECT
            'schema-local-collation',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.collname::pg_catalog.text,
            'pg_catalog.pg_collation'
        FROM pg_catalog.pg_collation AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.collnamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )

        UNION ALL
        SELECT
            'schema-local-operator',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.oprname::pg_catalog.text,
            'pg_catalog.pg_operator'
        FROM pg_catalog.pg_operator AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.oprnamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )

        UNION ALL
        SELECT
            'schema-local-operator_class',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.opcname::pg_catalog.text,
            'pg_catalog.pg_opclass'
        FROM pg_catalog.pg_opclass AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.opcnamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )

        UNION ALL
        SELECT
            'schema-local-operator_family',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.opfname::pg_catalog.text,
            'pg_catalog.pg_opfamily'
        FROM pg_catalog.pg_opfamily AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.opfnamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )

        UNION ALL
        SELECT
            'schema-local-conversion',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.conname::pg_catalog.text,
            'pg_catalog.pg_conversion'
        FROM pg_catalog.pg_conversion AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.connamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )

        UNION ALL
        SELECT
            'schema-local-text_search_config',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.cfgname::pg_catalog.text,
            'pg_catalog.pg_ts_config'
        FROM pg_catalog.pg_ts_config AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.cfgnamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )

        UNION ALL
        SELECT
            'schema-local-text_search_dictionary',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.dictname::pg_catalog.text,
            'pg_catalog.pg_ts_dict'
        FROM pg_catalog.pg_ts_dict AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.dictnamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )

        UNION ALL
        SELECT
            'schema-local-text_search_parser',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.prsname::pg_catalog.text,
            'pg_catalog.pg_ts_parser'
        FROM pg_catalog.pg_ts_parser AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.prsnamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )

        UNION ALL
        SELECT
            'schema-local-text_search_template',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.tmplname::pg_catalog.text,
            'pg_catalog.pg_ts_template'
        FROM pg_catalog.pg_ts_template AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.tmplnamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )

        UNION ALL
        SELECT
            'schema-local-statistics',
            namespace.nspname::pg_catalog.text || '.' ||
                schema_local_object.stxname::pg_catalog.text,
            'pg_catalog.pg_statistic_ext'
        FROM pg_catalog.pg_statistic_ext AS schema_local_object
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = schema_local_object.stxnamespace
        WHERE namespace.nspname IN (
            SELECT schema_name FROM governed_schema
        )
    )
    SELECT 'sha256:' || pg_catalog.encode(
        pg_catalog.sha256(
            pg_catalog.convert_to(
                'OFARM_SECURITY_AUDIT_COMPLETE_CATALOG_V1' ||
                pg_catalog.chr(29) ||
                COALESCE(
                    pg_catalog.jsonb_agg(
                        pg_catalog.jsonb_build_array(
                            category, object_identity, definition
                        )
                        ORDER BY
                            category COLLATE pg_catalog."C",
                            object_identity COLLATE pg_catalog."C",
                            definition COLLATE pg_catalog."C"
                    )::pg_catalog.text,
                    '[]'
                ),
                'UTF8'
            )
        ),
        'hex'
    )
    INTO v_catalog_fingerprint
    FROM catalog_entry;
    IF v_catalog_fingerprint <>
            'sha256:66395db8f49699ca4631e7fcb76adec48b354ba9fc774391cc381cfaa8704c32' THEN
        v_differences := v_differences + 1;
    END IF;

    RETURN ROW(
        v_differences = 0,
        v_differences,
        v_break_glass_present
    )::ofarm_security.security_audit_structure_report;
END
$verify_structure$;

REVOKE ALL PRIVILEGES ON FUNCTION
ofarm_security.verify_security_audit_structure() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
ofarm_security.verify_security_audit_structure()
TO ofarm_security_audit_readiness;

CREATE FUNCTION ofarm_security.observe_security_audit_contract()
RETURNS ofarm_security.security_audit_contract_observation
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $observe_contract$
DECLARE
    v_structure ofarm_security.security_audit_structure_report;
    v_version pg_catalog.int4;
    v_prefix_digest pg_catalog.text;
BEGIN
    IF session_user <> 'ofarm_security_audit_readiness_login' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'session user is not the audit readiness observer';
    END IF;
    v_structure := ofarm_security.verify_security_audit_structure();
    SELECT version, applied_prefix_digest
    INTO v_version, v_prefix_digest
    FROM ofarm_security.schema_migration
    ORDER BY version DESC
    LIMIT 1;

    RETURN ROW(
        'ofarm.security-audit-database-contract.v1',
        'sha256:a7bf363d590e27334470ae633bc694b9ba83afecd29a3d1c7f0be2606d1ab18b',
        'OFARM_PRETENANT_SECURITY_EVENT_V1',
        'CORRELATION_HMAC_ONLY_V1',
        'SECURITY_DIAGNOSTIC_30D_V1',
        'OFARM_PRETENANT_CORRELATION_V1',
        1,
        'ofarm.security-audit-postgresql.v1',
        'sha256:770165332bbdb7a5e67e468f021d9fe82df817a2aee1a8a70191a08e869c307a',
        v_version,
        v_prefix_digest,
        v_structure.structurally_compatible,
        v_structure.break_glass_login_present
    )::ofarm_security.security_audit_contract_observation;
END
$observe_contract$;

REVOKE ALL PRIVILEGES ON FUNCTION
ofarm_security.observe_security_audit_contract() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
ofarm_security.observe_security_audit_contract()
TO ofarm_security_audit_readiness;

REVOKE ALL PRIVILEGES ON TYPE
ofarm_security.operational_security_event_identity FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TYPE
ofarm_security.append_pretenant_failure_result FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TYPE
ofarm_security.audit_access_intent_result FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TYPE
ofarm_security.audit_retention_result FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TYPE
ofarm_security.operational_security_event_report FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TYPE
ofarm_security.security_audit_structure_report FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TYPE
ofarm_security.security_audit_contract_observation FROM PUBLIC;

GRANT USAGE ON TYPE ofarm_security.append_pretenant_failure_result
TO ofarm_security_audit_ingest;
GRANT USAGE ON TYPE ofarm_security.audit_access_intent_result
TO ofarm_security_audit_control;
GRANT USAGE ON TYPE ofarm_security.operational_security_event_identity
TO ofarm_security_audit_control;
GRANT USAGE ON TYPE ofarm_security.operational_security_event_report
TO ofarm_security_audit_reader, ofarm_security_audit_export;
GRANT USAGE ON TYPE ofarm_security.audit_retention_result
TO ofarm_security_audit_retention;
GRANT USAGE ON TYPE ofarm_security.security_audit_structure_report
TO ofarm_security_audit_readiness;
GRANT USAGE ON TYPE ofarm_security.security_audit_contract_observation
TO ofarm_security_audit_readiness;
