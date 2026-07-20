-- OFARM tenant PostgreSQL baseline for issue #174.
--
-- These bytes are immutable after acceptance. The migration runner executes
-- them as ofarm_owner inside the same transaction as its ledger append.

CREATE FUNCTION ofarm.valid_ascii_id(value pg_catalog.text)
RETURNS pg_catalog.bool
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT pg_catalog.octet_length(value) BETWEEN 1 AND 255
           AND value OPERATOR(pg_catalog.~) ''^[A-Za-z0-9._:-]+$''';

CREATE FUNCTION ofarm.valid_oidc_issuer(value pg_catalog.text)
RETURNS pg_catalog.bool
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        authority_and_path pg_catalog.text;
        authority pg_catalog.text;
        path_value pg_catalog.text := '''';
        host_value pg_catalog.text;
        port_text pg_catalog.text;
        port_value pg_catalog.int4;
        slash_position pg_catalog.int4;
        path_index pg_catalog.int4;
        label_value pg_catalog.text;
    BEGIN
        IF pg_catalog.octet_length(value) NOT BETWEEN 1 AND 2048
           OR (value COLLATE pg_catalog."C")
                OPERATOR(pg_catalog.!~) ''^[!-~]+$''
           OR pg_catalog.left(value, 8) <> ''https://'' THEN
            RETURN false;
        END IF;

        authority_and_path := pg_catalog.substring(value, 9);
        slash_position := pg_catalog.strpos(authority_and_path, ''/'');
        IF slash_position = 0 THEN
            authority := authority_and_path;
        ELSE
            authority := pg_catalog.left(
                authority_and_path, slash_position - 1
            );
            path_value := pg_catalog.substring(
                authority_and_path, slash_position
            );
        END IF;

        IF authority = ''''
           OR pg_catalog.strpos(authority, ''@'') <> 0
           OR pg_catalog.length(authority) - pg_catalog.length(
                pg_catalog.replace(authority, '':'', '''')
           ) > 1
           OR (
                path_value <> ''''
                AND (
                    pg_catalog.replace(
                        path_value, pg_catalog.chr(39), ''''
                    ) COLLATE pg_catalog."C"
                )
                    OPERATOR(pg_catalog.!~)
                    ''^/[A-Za-z0-9._~!$&()*+,;=:@%/-]*$''
           ) THEN
            RETURN false;
        END IF;

        path_index := 1;
        WHILE path_index <= pg_catalog.octet_length(path_value) LOOP
            IF pg_catalog.get_byte(
                    pg_catalog.convert_to(path_value, ''SQL_ASCII''),
                    path_index - 1
               ) = 37 THEN
                IF path_index + 2 > pg_catalog.octet_length(path_value)
                   OR (
                        pg_catalog.substring(path_value, path_index, 3)
                        COLLATE pg_catalog."C"
                      ) OPERATOR(pg_catalog.!~) ''^%[0-9A-Fa-f]{2}$'' THEN
                    RETURN false;
                END IF;
                path_index := path_index + 3;
            ELSE
                path_index := path_index + 1;
            END IF;
        END LOOP;

        IF pg_catalog.strpos(authority, '':'') <> 0 THEN
            host_value := pg_catalog.split_part(authority, '':'', 1);
            port_text := pg_catalog.split_part(authority, '':'', 2);
            IF (port_text COLLATE pg_catalog."C")
                    OPERATOR(pg_catalog.!~) ''^[1-9][0-9]{0,4}$'' THEN
                RETURN false;
            END IF;
            port_value := port_text::pg_catalog.int4;
            IF port_value NOT BETWEEN 1 AND 65535 THEN
                RETURN false;
            END IF;
        ELSE
            host_value := authority;
        END IF;

        IF pg_catalog.octet_length(host_value) NOT BETWEEN 1 AND 253 THEN
            RETURN false;
        END IF;
        FOREACH label_value IN ARRAY pg_catalog.string_to_array(host_value, ''.'') LOOP
            IF pg_catalog.octet_length(label_value) NOT BETWEEN 1 AND 63
               OR (label_value COLLATE pg_catalog."C")
                    OPERATOR(pg_catalog.!~)
                    ''^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$'' THEN
                RETURN false;
            END IF;
        END LOOP;
        RETURN true;
    END';

CREATE FUNCTION ofarm.valid_runtime_logical_ref(value pg_catalog.text)
RETURNS pg_catalog.bool
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT pg_catalog.octet_length(value) BETWEEN 1 AND 1024
           AND value OPERATOR(pg_catalog.~)
               ''^[A-Za-z0-9][A-Za-z0-9._:/#-]*$''';

CREATE DOMAIN ofarm.ascii_id AS pg_catalog.text COLLATE pg_catalog."C"
    CONSTRAINT ascii_id_policy_check
    CHECK (ofarm.valid_ascii_id(VALUE));

CREATE DOMAIN ofarm.tenant_ref AS pg_catalog.text COLLATE pg_catalog."C"
    CONSTRAINT tenant_ref_policy_check
    CHECK (ofarm.valid_ascii_id(VALUE));

CREATE DOMAIN ofarm.tenant_local_ref AS pg_catalog.text COLLATE pg_catalog."C"
    CONSTRAINT tenant_local_ref_policy_check
    CHECK (ofarm.valid_ascii_id(VALUE));

CREATE DOMAIN ofarm.runtime_logical_ref
    AS pg_catalog.text COLLATE pg_catalog."C"
    CONSTRAINT runtime_logical_ref_policy_check
    CHECK (ofarm.valid_runtime_logical_ref(VALUE));

CREATE DOMAIN ofarm.idempotency_caller_key
    AS pg_catalog.text COLLATE pg_catalog."C"
    CONSTRAINT idempotency_caller_key_policy_check
    CHECK (ofarm.valid_ascii_id(VALUE));

CREATE DOMAIN ofarm.oidc_issuer AS pg_catalog.text COLLATE pg_catalog."C"
    CONSTRAINT oidc_issuer_policy_check
    CHECK (ofarm.valid_oidc_issuer(VALUE));

CREATE DOMAIN ofarm.oidc_subject AS pg_catalog.text COLLATE pg_catalog."C"
    CONSTRAINT oidc_subject_policy_check
    CHECK (
        pg_catalog.octet_length(VALUE) BETWEEN 1 AND 255
        AND VALUE OPERATOR(pg_catalog.~) '^[!-~]+$'
    );

CREATE DOMAIN ofarm.sha256_id AS pg_catalog.text COLLATE pg_catalog."C"
    CONSTRAINT sha256_id_canonical_check
    CHECK (VALUE OPERATOR(pg_catalog.~) '^sha256:[0-9a-f]{64}$');

CREATE FUNCTION ofarm.lp32(value pg_catalog.bytea)
RETURNS pg_catalog.bytea
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT pg_catalog.int4send(pg_catalog.octet_length(value)) OPERATOR(pg_catalog.||) value';

CREATE FUNCTION ofarm.reject_immutable_row_mutation()
RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN
        RAISE EXCEPTION USING
            ERRCODE = ''55000'',
            MESSAGE = TG_TABLE_SCHEMA || ''.'' || TG_TABLE_NAME || '' is immutable'';
    END';

CREATE FUNCTION ofarm.reject_immutable_relation_truncate()
RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN
        RAISE EXCEPTION USING
            ERRCODE = ''55000'',
            MESSAGE = TG_TABLE_SCHEMA || ''.'' || TG_TABLE_NAME || '' is immutable'';
    END';

CREATE FUNCTION ofarm.stamp_governed_batch_full_xid()
RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN
        NEW.full_xid := pg_catalog.pg_current_xact_id();
        RETURN NEW;
    END';

CREATE FUNCTION ofarm.stamp_batch_member_full_xid()
RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN
        NEW.batch_full_xid := pg_catalog.pg_current_xact_id();
        RETURN NEW;
    END';

CREATE TABLE "ofarm"."schema_migration" (
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
        CHECK (service_identity = 'ofarm.tenant-postgresql.v1'),
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

CREATE FUNCTION "ofarm"."reject_schema_migration_mutation"() RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN RAISE EXCEPTION USING ERRCODE = ''55000'', MESSAGE = ''schema_migration is append-only''; END';

REVOKE ALL PRIVILEGES ON FUNCTION "ofarm"."reject_schema_migration_mutation"() FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TABLE "ofarm"."schema_migration" FROM PUBLIC;

CREATE TRIGGER "schema_migration_reject_update_delete"
BEFORE UPDATE OR DELETE ON "ofarm"."schema_migration"
FOR EACH ROW EXECUTE FUNCTION "ofarm"."reject_schema_migration_mutation"();

CREATE TRIGGER "schema_migration_reject_truncate"
BEFORE TRUNCATE ON "ofarm"."schema_migration"
FOR EACH STATEMENT EXECUTE FUNCTION "ofarm"."reject_schema_migration_mutation"();

GRANT SELECT (
    version,
    filename,
    source_sha256,
    source_byte_length,
    applied_prefix_digest,
    service_identity,
    provisioning_spec_digest
) ON TABLE "ofarm"."schema_migration" TO "ofarm_readiness";

CREATE FUNCTION ofarm.compute_tenant_registration_digest(
    tenant_id pg_catalog.uuid,
    tenant_ref pg_catalog.text,
    advisory_lock_key pg_catalog.int8
)
RETURNS pg_catalog.text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT ''sha256:'' OPERATOR(pg_catalog.||)
           pg_catalog.encode(
               pg_catalog.sha256(
                   pg_catalog.convert_to(
                       ''OFARM_TENANT_REGISTRATION_V1'', ''UTF8''
                   ) OPERATOR(pg_catalog.||) decode(''00'', ''hex'')
                   OPERATOR(pg_catalog.||) pg_catalog.uuid_send(tenant_id)
                   OPERATOR(pg_catalog.||) ofarm.lp32(
                       pg_catalog.convert_to(''OFARM_ASCII_ID_V1'', ''UTF8'')
                   )
                   OPERATOR(pg_catalog.||) ofarm.lp32(
                       pg_catalog.convert_to(tenant_ref, ''UTF8'')
                   )
                   OPERATOR(pg_catalog.||) pg_catalog.int8send(advisory_lock_key)
               ),
               ''hex''
           )';

CREATE FUNCTION ofarm.compute_principal_binding_version_digest(
    equality_policy pg_catalog.text,
    issuer pg_catalog.text,
    subject pg_catalog.text,
    binding_version_id pg_catalog.uuid,
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
    predecessor_version_id pg_catalog.uuid
)
RETURNS pg_catalog.text
LANGUAGE sql IMMUTABLE PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT ''sha256:'' || pg_catalog.encode(
        pg_catalog.sha256(
            pg_catalog.convert_to(
                ''OFARM_PRINCIPAL_BINDING_VERSION_V1'', ''UTF8''
            ) || pg_catalog.decode(''00'', ''hex'')
            || ofarm.lp32(pg_catalog.convert_to(equality_policy, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(issuer, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(subject, ''UTF8''))
            || ofarm.lp32(pg_catalog.uuid_send(binding_version_id))
            || ofarm.lp32(pg_catalog.uuid_send(tenant_id))
            || ofarm.lp32(pg_catalog.decode(
                pg_catalog.substr(tenant_registration_digest, 8), ''hex''
            ))
            || ofarm.lp32(pg_catalog.convert_to(party_ref, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(party_record_kind, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(party_record_id, ''UTF8''))
            || ofarm.lp32(pg_catalog.decode(
                pg_catalog.substr(party_schema_digest, 8), ''hex''
            ))
            || ofarm.lp32(pg_catalog.decode(
                pg_catalog.substr(party_payload_digest, 8), ''hex''
            ))
            || ofarm.lp32(pg_catalog.convert_to(party_state, ''UTF8''))
            || ofarm.lp32(pg_catalog.int8send(
                pg_catalog.floor(EXTRACT(EPOCH FROM valid_from) * 1000000)::pg_catalog.int8
            ))
            || ofarm.lp32(pg_catalog.int8send(
                pg_catalog.floor(EXTRACT(EPOCH FROM valid_until) * 1000000)::pg_catalog.int8
            ))
            || ofarm.lp32(
                CASE
                    WHEN predecessor_version_id IS NULL THEN ''''::pg_catalog.bytea
                    ELSE pg_catalog.uuid_send(predecessor_version_id)
                END
            )
        ),
        ''hex''
    )';

CREATE FUNCTION ofarm.compute_principal_lifecycle_act_digest(
    equality_policy pg_catalog.text,
    issuer pg_catalog.text,
    subject pg_catalog.text,
    stream_sequence pg_catalog.int8,
    act_id pg_catalog.uuid,
    act_kind pg_catalog.text,
    binding_version_id pg_catalog.uuid,
    binding_version_digest pg_catalog.text,
    prior_act_id pg_catalog.uuid,
    prior_act_digest pg_catalog.text,
    successor_version_id pg_catalog.uuid,
    successor_version_digest pg_catalog.text,
    effective_at pg_catalog.timestamptz,
    decided_at pg_catalog.timestamptz,
    accountable_control_ref pg_catalog.text,
    reason pg_catalog.text
)
RETURNS pg_catalog.text
LANGUAGE sql IMMUTABLE PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT ''sha256:'' || pg_catalog.encode(
        pg_catalog.sha256(
            pg_catalog.convert_to(
                ''OFARM_PRINCIPAL_BINDING_LIFECYCLE_ACT_V1'', ''UTF8''
            ) || pg_catalog.decode(''00'', ''hex'')
            || ofarm.lp32(pg_catalog.convert_to(equality_policy, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(issuer, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(subject, ''UTF8''))
            || ofarm.lp32(pg_catalog.int8send(stream_sequence))
            || ofarm.lp32(pg_catalog.uuid_send(act_id))
            || ofarm.lp32(pg_catalog.convert_to(act_kind, ''UTF8''))
            || ofarm.lp32(pg_catalog.uuid_send(binding_version_id))
            || ofarm.lp32(pg_catalog.decode(
                pg_catalog.substr(binding_version_digest, 8), ''hex''
            ))
            || ofarm.lp32(
                CASE WHEN prior_act_id IS NULL THEN ''''::pg_catalog.bytea
                     ELSE pg_catalog.uuid_send(prior_act_id) END
            )
            || ofarm.lp32(
                CASE WHEN prior_act_digest IS NULL THEN ''''::pg_catalog.bytea
                     ELSE pg_catalog.decode(
                        pg_catalog.substr(prior_act_digest, 8), ''hex''
                     ) END
            )
            || ofarm.lp32(
                CASE WHEN successor_version_id IS NULL THEN ''''::pg_catalog.bytea
                     ELSE pg_catalog.uuid_send(successor_version_id) END
            )
            || ofarm.lp32(
                CASE WHEN successor_version_digest IS NULL
                     THEN ''''::pg_catalog.bytea
                     ELSE pg_catalog.decode(
                        pg_catalog.substr(successor_version_digest, 8), ''hex''
                     ) END
            )
            || ofarm.lp32(pg_catalog.int8send(
                pg_catalog.floor(EXTRACT(EPOCH FROM effective_at) * 1000000)::pg_catalog.int8
            ))
            || ofarm.lp32(pg_catalog.int8send(
                pg_catalog.floor(EXTRACT(EPOCH FROM decided_at) * 1000000)::pg_catalog.int8
            ))
            || ofarm.lp32(pg_catalog.convert_to(accountable_control_ref, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(reason, ''UTF8''))
        ),
        ''hex''
    )';

CREATE FUNCTION ofarm.compute_materialization_key_digest(
    materialization_key pg_catalog.jsonb
)
RETURNS pg_catalog.text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT ''sha256:'' || pg_catalog.encode(
        pg_catalog.sha256(
            pg_catalog.convert_to(
                materialization_key::pg_catalog.text,
                ''UTF8''
            )
        ),
        ''hex''
    )';

CREATE TABLE ofarm.tenant_registry (
    tenant_id pg_catalog.uuid NOT NULL,
    tenant_ref ofarm.tenant_ref NOT NULL,
    equality_policy pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    advisory_lock_key pg_catalog.int8 NOT NULL,
    registration_digest ofarm.sha256_id NOT NULL,
    registered_at pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT tenant_registry_pkey PRIMARY KEY (tenant_id),
    CONSTRAINT tenant_registry_tenant_ref_key UNIQUE (tenant_ref),
    CONSTRAINT tenant_registry_advisory_lock_key_key UNIQUE (advisory_lock_key),
    CONSTRAINT tenant_registry_id_digest_key
        UNIQUE (tenant_id, registration_digest),
    CONSTRAINT tenant_registry_tenant_id_check CHECK (
        tenant_id <> '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
    ),
    CONSTRAINT tenant_registry_equality_policy_check CHECK (
        equality_policy = 'OFARM_ASCII_ID_V1'
    ),
    CONSTRAINT tenant_registry_digest_check CHECK (
        registration_digest = ofarm.compute_tenant_registration_digest(
            tenant_id, tenant_ref::pg_catalog.text, advisory_lock_key
        )
    )
);

CREATE FUNCTION ofarm.base64url_encode(value pg_catalog.bytea)
RETURNS pg_catalog.text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT pg_catalog.replace(
               pg_catalog.replace(
                   pg_catalog.rtrim(
                       pg_catalog.replace(
                           pg_catalog.replace(
                               pg_catalog.encode(value, ''base64''),
                               pg_catalog.chr(10), ''''
                           ),
                           pg_catalog.chr(13), ''''
                       ),
                       ''=''
                   ),
                   ''+'', ''-''
               ),
               ''/'', ''_''
           )';

CREATE FUNCTION ofarm.base64url_decode(value pg_catalog.text)
RETURNS pg_catalog.bytea
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        decoded pg_catalog.bytea;
    BEGIN
        IF pg_catalog.octet_length(value) < 1
           OR (value COLLATE pg_catalog."C")
                OPERATOR(pg_catalog.!~) ''^[A-Za-z0-9_-]+$'' THEN
            RAISE EXCEPTION USING
                ERRCODE = ''22023'',
                MESSAGE = ''base64url value is not canonical'';
        END IF;
        decoded := pg_catalog.decode(
            pg_catalog.translate(value, ''-_'', ''+/'') ||
            pg_catalog.repeat(
                ''='',
                (4 - pg_catalog.octet_length(value) % 4) % 4
            ),
            ''base64''
        );
        IF ofarm.base64url_encode(decoded) <> value THEN
            RAISE EXCEPTION USING
                ERRCODE = ''22023'',
                MESSAGE = ''base64url value is not canonical'';
        END IF;
        RETURN decoded;
    END';

CREATE FUNCTION ofarm.tenant_capability_key_id(public_key pg_catalog.bytea)
RETURNS pg_catalog.text
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        key_x pg_catalog.text;
        thumbprint_input pg_catalog.bytea;
    BEGIN
        IF pg_catalog.octet_length(public_key) <> 32 THEN
            RAISE EXCEPTION USING
                ERRCODE = ''22023'',
                MESSAGE = ''Ed25519 public key length differs'';
        END IF;
        key_x := ofarm.base64url_encode(public_key);
        thumbprint_input := pg_catalog.convert_to(
            ''{"crv":"Ed25519","kty":"OKP","x":"'' || key_x || ''"}'',
            ''UTF8''
        );
        RETURN ofarm.base64url_encode(pg_catalog.sha256(thumbprint_input));
    END';

CREATE FUNCTION ofarm.compute_tenant_binder_instance_digest(
    instance_id pg_catalog.uuid,
    audience pg_catalog.text,
    contract_digest pg_catalog.text,
    database_name pg_catalog.text,
    created_at pg_catalog.timestamptz
)
RETURNS pg_catalog.text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT ''sha256:'' || pg_catalog.encode(
        pg_catalog.sha256(
            pg_catalog.convert_to(''OFARM_TENANT_BINDER_INSTANCE_V1'', ''UTF8'')
            || pg_catalog.decode(''00'', ''hex'')
            || ofarm.lp32(pg_catalog.uuid_send(instance_id))
            || ofarm.lp32(pg_catalog.convert_to(audience, ''UTF8''))
            || ofarm.lp32(pg_catalog.decode(
                pg_catalog.substr(contract_digest, 8), ''hex''
            ))
            || ofarm.lp32(pg_catalog.convert_to(database_name, ''UTF8''))
            || ofarm.lp32(pg_catalog.int8send(
                (extract(epoch FROM created_at) * 1000000)::pg_catalog.int8
            ))
        ),
        ''hex''
    )';

CREATE TABLE ofarm.tenant_binder_instance (
    singleton pg_catalog.bool NOT NULL DEFAULT true,
    instance_id pg_catalog.uuid NOT NULL,
    audience pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    contract_digest ofarm.sha256_id NOT NULL,
    database_name pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    created_at pg_catalog.timestamptz NOT NULL,
    row_digest ofarm.sha256_id NOT NULL,
    CONSTRAINT tenant_binder_instance_pkey PRIMARY KEY (singleton),
    CONSTRAINT tenant_binder_instance_id_key UNIQUE (instance_id),
    CONSTRAINT tenant_binder_instance_audience_key UNIQUE (audience),
    CONSTRAINT tenant_binder_instance_singleton_check CHECK (singleton),
    CONSTRAINT tenant_binder_instance_id_check CHECK (
        instance_id <> '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
    ),
    CONSTRAINT tenant_binder_instance_contract_check CHECK (
        contract_digest::pg_catalog.text =
        'sha256:39e979fa296122cb66d42eae5e2d7c6dc797ac77ef4324515ae1ab6020088d83'
    ),
    CONSTRAINT tenant_binder_instance_audience_check CHECK (
        audience = 'urn:ofarm:tenant-binder:v1:' || instance_id::pg_catalog.text
    ),
    CONSTRAINT tenant_binder_instance_database_check CHECK (
        pg_catalog.octet_length(database_name) BETWEEN 1 AND 63
        AND database_name OPERATOR(pg_catalog.~) '^[a-z][a-z0-9_]*$'
    ),
    CONSTRAINT tenant_binder_instance_time_check CHECK (
        created_at NOT IN (
            '-infinity'::pg_catalog.timestamptz,
            'infinity'::pg_catalog.timestamptz
        )
    ),
    CONSTRAINT tenant_binder_instance_digest_check CHECK (
        row_digest::pg_catalog.text =
        ofarm.compute_tenant_binder_instance_digest(
            instance_id,
            audience,
            contract_digest::pg_catalog.text,
            database_name,
            created_at
        )
    )
);

WITH identity AS (
    SELECT pg_catalog.gen_random_uuid() AS instance_id,
           pg_catalog.clock_timestamp() AS created_at
), framed AS (
    SELECT instance_id,
           'urn:ofarm:tenant-binder:v1:' ||
               instance_id::pg_catalog.text AS audience,
           'sha256:39e979fa296122cb66d42eae5e2d7c6dc797ac77ef4324515ae1ab6020088d83'
               AS contract_digest,
           pg_catalog.current_database()::pg_catalog.text AS database_name,
           created_at
      FROM identity
)
INSERT INTO ofarm.tenant_binder_instance (
    instance_id,
    audience,
    contract_digest,
    database_name,
    created_at,
    row_digest
)
SELECT instance_id,
       audience,
       contract_digest,
       database_name,
       created_at,
       ofarm.compute_tenant_binder_instance_digest(
           instance_id, audience, contract_digest, database_name, created_at
       )
  FROM framed;

CREATE FUNCTION ofarm.compute_tenant_capability_candidate_digest(
    candidate_id pg_catalog.uuid,
    kid pg_catalog.text,
    public_key pg_catalog.bytea,
    public_key_digest pg_catalog.text,
    algorithm pg_catalog.text,
    audience pg_catalog.text,
    kms_key_version_resource pg_catalog.text,
    kms_purpose pg_catalog.text,
    kms_algorithm pg_catalog.text,
    kms_protection_level pg_catalog.text,
    kms_attestation_digest pg_catalog.text,
    registered_at pg_catalog.timestamptz,
    accountable_control_ref pg_catalog.text
)
RETURNS pg_catalog.text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT ''sha256:'' || pg_catalog.encode(
        pg_catalog.sha256(
            pg_catalog.convert_to(
                ''OFARM_TENANT_CAPABILITY_VERIFICATION_KEY_V1'', ''UTF8''
            ) || pg_catalog.decode(''00'', ''hex'')
            || ofarm.lp32(pg_catalog.uuid_send(candidate_id))
            || ofarm.lp32(pg_catalog.convert_to(kid, ''UTF8''))
            || ofarm.lp32(public_key)
            || ofarm.lp32(pg_catalog.decode(
                pg_catalog.substr(public_key_digest, 8), ''hex''
            ))
            || ofarm.lp32(pg_catalog.convert_to(algorithm, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(audience, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(
                kms_key_version_resource, ''UTF8''
            ))
            || ofarm.lp32(pg_catalog.convert_to(kms_purpose, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(kms_algorithm, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(
                kms_protection_level, ''UTF8''
            ))
            || ofarm.lp32(pg_catalog.decode(
                pg_catalog.substr(kms_attestation_digest, 8), ''hex''
            ))
            || ofarm.lp32(pg_catalog.int8send(
                (extract(epoch FROM registered_at) * 1000000)::pg_catalog.int8
            ))
            || ofarm.lp32(pg_catalog.convert_to(
                accountable_control_ref, ''UTF8''
            ))
        ),
        ''hex''
    )';

CREATE TABLE ofarm.tenant_capability_verification_key (
    candidate_id pg_catalog.uuid NOT NULL,
    kid pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    public_key pg_catalog.bytea NOT NULL,
    public_key_digest ofarm.sha256_id NOT NULL,
    algorithm pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    audience pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    kms_key_version_resource pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    kms_purpose pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    kms_algorithm pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    kms_protection_level pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    kms_attestation_digest ofarm.sha256_id NOT NULL,
    registered_at pg_catalog.timestamptz NOT NULL,
    accountable_control_ref ofarm.ascii_id NOT NULL,
    candidate_digest ofarm.sha256_id NOT NULL,
    CONSTRAINT tenant_capability_verification_key_pkey PRIMARY KEY (candidate_id),
    CONSTRAINT tenant_capability_verification_key_kid_key UNIQUE (kid),
    CONSTRAINT tenant_capability_verification_key_public_key_key UNIQUE (public_key),
    CONSTRAINT tenant_capability_verification_key_resource_key
        UNIQUE (kms_key_version_resource),
    CONSTRAINT tenant_capability_verification_key_kid_digest_key
        UNIQUE (kid, candidate_digest),
    CONSTRAINT tenant_capability_verification_key_id_check CHECK (
        candidate_id <> '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
    ),
    CONSTRAINT tenant_capability_verification_key_shape_check CHECK (
        pg_catalog.octet_length(public_key) = 32
        AND pg_catalog.octet_length(kid) = 43
        AND kid = ofarm.tenant_capability_key_id(public_key)
        AND public_key_digest::pg_catalog.text = 'sha256:' ||
            pg_catalog.encode(pg_catalog.sha256(public_key), 'hex')
        AND algorithm = 'Ed25519'
        AND kms_purpose = 'ASYMMETRIC_SIGN'
        AND kms_algorithm = 'EC_SIGN_ED25519'
        AND kms_protection_level = 'HSM'
        AND kms_key_version_resource OPERATOR(pg_catalog.~)
            '^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/locations/[a-z0-9]([a-z0-9-]*[a-z0-9])?/keyRings/[A-Za-z0-9_-]{1,63}/cryptoKeys/[A-Za-z0-9_-]{1,63}/cryptoKeyVersions/[1-9][0-9]*$'
    ),
    CONSTRAINT tenant_capability_verification_key_time_check CHECK (
        registered_at NOT IN (
            '-infinity'::pg_catalog.timestamptz,
            'infinity'::pg_catalog.timestamptz
        )
    ),
    CONSTRAINT tenant_capability_verification_key_digest_check CHECK (
        candidate_digest::pg_catalog.text =
        ofarm.compute_tenant_capability_candidate_digest(
            candidate_id,
            kid,
            public_key,
            public_key_digest::pg_catalog.text,
            algorithm,
            audience,
            kms_key_version_resource,
            kms_purpose,
            kms_algorithm,
            kms_protection_level,
            kms_attestation_digest::pg_catalog.text,
            registered_at,
            accountable_control_ref::pg_catalog.text
        )
    )
);

CREATE FUNCTION ofarm.compute_tenant_capability_key_act_digest(
    stream_sequence pg_catalog.int8,
    act_id pg_catalog.uuid,
    prior_act_id pg_catalog.uuid,
    prior_act_digest pg_catalog.text,
    act_kind pg_catalog.text,
    old_kid pg_catalog.text,
    old_candidate_digest pg_catalog.text,
    new_kid pg_catalog.text,
    new_candidate_digest pg_catalog.text,
    audience pg_catalog.text,
    algorithm pg_catalog.text,
    decided_at_us pg_catalog.int8,
    effective_at_us pg_catalog.int8,
    new_issuance_end_us pg_catalog.int8,
    old_verification_end_us pg_catalog.int8,
    incident_id pg_catalog.uuid,
    close_receipt_id pg_catalog.uuid,
    preflight_receipt_digest pg_catalog.text,
    kms_evidence_digest pg_catalog.text,
    iam_evidence_digest pg_catalog.text,
    accountable_control_ref pg_catalog.text,
    reason pg_catalog.text
)
RETURNS pg_catalog.text
LANGUAGE sql IMMUTABLE PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT ''sha256:'' || pg_catalog.encode(
        pg_catalog.sha256(
            pg_catalog.convert_to(
                ''OFARM_TENANT_CAPABILITY_KEY_LIFECYCLE_ACT_V1'', ''UTF8''
            ) || pg_catalog.decode(''00'', ''hex'')
            || ofarm.lp32(pg_catalog.int8send(stream_sequence))
            || ofarm.lp32(pg_catalog.uuid_send(act_id))
            || ofarm.lp32(CASE WHEN prior_act_id IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.uuid_send(prior_act_id) END)
            || ofarm.lp32(CASE WHEN prior_act_digest IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.decode(pg_catalog.substr(prior_act_digest, 8), ''hex'') END)
            || ofarm.lp32(pg_catalog.convert_to(act_kind, ''UTF8''))
            || ofarm.lp32(CASE WHEN old_kid IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.convert_to(old_kid, ''UTF8'') END)
            || ofarm.lp32(CASE WHEN old_candidate_digest IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.decode(pg_catalog.substr(old_candidate_digest, 8), ''hex'') END)
            || ofarm.lp32(CASE WHEN new_kid IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.convert_to(new_kid, ''UTF8'') END)
            || ofarm.lp32(CASE WHEN new_candidate_digest IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.decode(pg_catalog.substr(new_candidate_digest, 8), ''hex'') END)
            || ofarm.lp32(pg_catalog.convert_to(audience, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(algorithm, ''UTF8''))
            || ofarm.lp32(pg_catalog.int8send(decided_at_us))
            || ofarm.lp32(pg_catalog.int8send(effective_at_us))
            || ofarm.lp32(CASE WHEN new_issuance_end_us IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.int8send(new_issuance_end_us) END)
            || ofarm.lp32(CASE WHEN old_verification_end_us IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.int8send(old_verification_end_us) END)
            || ofarm.lp32(CASE WHEN incident_id IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.uuid_send(incident_id) END)
            || ofarm.lp32(CASE WHEN close_receipt_id IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.uuid_send(close_receipt_id) END)
            || ofarm.lp32(CASE WHEN preflight_receipt_digest IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.decode(pg_catalog.substr(preflight_receipt_digest, 8), ''hex'') END)
            || ofarm.lp32(CASE WHEN kms_evidence_digest IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.decode(pg_catalog.substr(kms_evidence_digest, 8), ''hex'') END)
            || ofarm.lp32(CASE WHEN iam_evidence_digest IS NULL THEN ''''::pg_catalog.bytea
                ELSE pg_catalog.decode(pg_catalog.substr(iam_evidence_digest, 8), ''hex'') END)
            || ofarm.lp32(pg_catalog.convert_to(accountable_control_ref, ''UTF8''))
            || ofarm.lp32(pg_catalog.convert_to(reason, ''UTF8''))
        ),
        ''hex''
    )';

CREATE TABLE ofarm.tenant_capability_key_lifecycle (
    stream_sequence pg_catalog.int8 NOT NULL,
    act_id pg_catalog.uuid NOT NULL,
    act_digest ofarm.sha256_id NOT NULL,
    prior_act_id pg_catalog.uuid,
    prior_act_digest ofarm.sha256_id,
    act_kind pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    old_kid pg_catalog.text COLLATE pg_catalog."C",
    old_candidate_digest ofarm.sha256_id,
    new_kid pg_catalog.text COLLATE pg_catalog."C",
    new_candidate_digest ofarm.sha256_id,
    audience pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    algorithm pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    decided_at_us pg_catalog.int8 NOT NULL,
    effective_at_us pg_catalog.int8 NOT NULL,
    new_issuance_end_us pg_catalog.int8,
    old_verification_end_us pg_catalog.int8,
    incident_id pg_catalog.uuid,
    close_receipt_id pg_catalog.uuid,
    preflight_receipt_digest ofarm.sha256_id,
    kms_evidence_digest ofarm.sha256_id,
    iam_evidence_digest ofarm.sha256_id,
    accountable_control_ref ofarm.ascii_id NOT NULL,
    reason ofarm.ascii_id NOT NULL,
    CONSTRAINT tenant_capability_key_lifecycle_pkey PRIMARY KEY (act_id),
    CONSTRAINT tenant_capability_key_lifecycle_sequence_key
        UNIQUE (stream_sequence),
    CONSTRAINT tenant_capability_key_lifecycle_digest_key UNIQUE (act_digest),
    CONSTRAINT tenant_capability_key_lifecycle_id_digest_key
        UNIQUE (act_id, act_digest),
    CONSTRAINT tenant_capability_key_lifecycle_prior_key UNIQUE (prior_act_id),
    CONSTRAINT tenant_capability_key_lifecycle_old_fkey FOREIGN KEY (
        old_kid, old_candidate_digest
    ) REFERENCES ofarm.tenant_capability_verification_key (
        kid, candidate_digest
    ),
    CONSTRAINT tenant_capability_key_lifecycle_new_fkey FOREIGN KEY (
        new_kid, new_candidate_digest
    ) REFERENCES ofarm.tenant_capability_verification_key (
        kid, candidate_digest
    ),
    CONSTRAINT tenant_capability_key_lifecycle_prior_fkey FOREIGN KEY (
        prior_act_id, prior_act_digest
    ) REFERENCES ofarm.tenant_capability_key_lifecycle (
        act_id, act_digest
    ) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT tenant_capability_key_lifecycle_sequence_check CHECK (
        stream_sequence >= 1
        AND ((stream_sequence = 1) = (prior_act_id IS NULL))
        AND ((prior_act_id IS NULL) = (prior_act_digest IS NULL))
    ),
    CONSTRAINT tenant_capability_key_lifecycle_kind_check CHECK (
        act_kind IN (
            'ACTIVATE', 'ROTATE', 'CLOSE_ADMISSION', 'REVOKE',
            'RESUME_ADMISSION'
        )
    ),
    CONSTRAINT tenant_capability_key_lifecycle_key_pair_check CHECK (
        (old_kid IS NULL) = (old_candidate_digest IS NULL)
        AND (new_kid IS NULL) = (new_candidate_digest IS NULL)
        AND algorithm = 'Ed25519'
    ),
    CONSTRAINT tenant_capability_key_lifecycle_time_check CHECK (
        effective_at_us = decided_at_us
        AND (new_issuance_end_us IS NULL OR new_issuance_end_us > effective_at_us)
        AND (old_verification_end_us IS NULL OR
             old_verification_end_us > effective_at_us)
    ),
    CONSTRAINT tenant_capability_key_lifecycle_incident_check CHECK (
        (incident_id IS NULL) = (close_receipt_id IS NULL)
    ),
    CONSTRAINT tenant_capability_key_lifecycle_evidence_shape_check CHECK (
        (
            act_kind = 'ACTIVATE'
            AND old_kid IS NULL AND old_candidate_digest IS NULL
            AND new_kid IS NOT NULL AND new_candidate_digest IS NOT NULL
            AND new_issuance_end_us IS NOT NULL
            AND old_verification_end_us IS NULL
            AND incident_id IS NULL AND close_receipt_id IS NULL
            AND preflight_receipt_digest IS NOT NULL
            AND kms_evidence_digest IS NOT NULL
            AND iam_evidence_digest IS NOT NULL
        )
        OR
        (
            act_kind = 'ROTATE'
            AND old_kid IS NOT NULL AND old_candidate_digest IS NOT NULL
            AND new_kid IS NOT NULL AND new_candidate_digest IS NOT NULL
            AND new_issuance_end_us IS NOT NULL
            AND old_verification_end_us IS NOT NULL
            AND incident_id IS NULL AND close_receipt_id IS NULL
            AND preflight_receipt_digest IS NOT NULL
            AND kms_evidence_digest IS NOT NULL
            AND iam_evidence_digest IS NOT NULL
        )
        OR
        (
            act_kind IN ('CLOSE_ADMISSION', 'REVOKE')
            AND old_kid IS NOT NULL AND old_candidate_digest IS NOT NULL
            AND new_kid IS NULL AND new_candidate_digest IS NULL
            AND new_issuance_end_us IS NULL
            AND old_verification_end_us IS NULL
            AND incident_id IS NOT NULL AND close_receipt_id IS NOT NULL
            AND preflight_receipt_digest IS NULL
            AND kms_evidence_digest IS NOT NULL
            AND iam_evidence_digest IS NOT NULL
        )
        OR
        (
            act_kind = 'RESUME_ADMISSION'
            AND old_kid IS NULL AND old_candidate_digest IS NULL
            AND new_kid IS NOT NULL AND new_candidate_digest IS NOT NULL
            AND new_issuance_end_us IS NULL
            AND old_verification_end_us IS NULL
            AND incident_id IS NOT NULL AND close_receipt_id IS NOT NULL
            AND preflight_receipt_digest IS NULL
            AND kms_evidence_digest IS NOT NULL
            AND iam_evidence_digest IS NOT NULL
        )
    ),
    CONSTRAINT tenant_capability_key_lifecycle_digest_check CHECK (
        act_digest::pg_catalog.text =
        ofarm.compute_tenant_capability_key_act_digest(
            stream_sequence,
            act_id,
            prior_act_id,
            prior_act_digest::pg_catalog.text,
            act_kind,
            old_kid,
            old_candidate_digest::pg_catalog.text,
            new_kid,
            new_candidate_digest::pg_catalog.text,
            audience,
            algorithm,
            decided_at_us,
            effective_at_us,
            new_issuance_end_us,
            old_verification_end_us,
            incident_id,
            close_receipt_id,
            preflight_receipt_digest::pg_catalog.text,
            kms_evidence_digest::pg_catalog.text,
            iam_evidence_digest::pg_catalog.text,
            accountable_control_ref::pg_catalog.text,
            reason::pg_catalog.text
        )
    )
);

CREATE TABLE ofarm.tenant_capability_keyring (
    audience pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    projected_head_sequence pg_catalog.int8,
    projected_head_id pg_catalog.uuid,
    projected_head_digest ofarm.sha256_id,
    projected_admission_state pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    projected_issuing_kid pg_catalog.text COLLATE pg_catalog."C",
    projected_issuing_candidate_digest ofarm.sha256_id,
    unresolved_incident_id pg_catalog.uuid,
    close_act_id pg_catalog.uuid,
    close_receipt_id pg_catalog.uuid,
    rebuilt_at pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT tenant_capability_keyring_pkey PRIMARY KEY (audience),
    CONSTRAINT tenant_capability_keyring_head_fkey FOREIGN KEY (
        projected_head_id, projected_head_digest
    ) REFERENCES ofarm.tenant_capability_key_lifecycle (
        act_id, act_digest
    ) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT tenant_capability_keyring_issuing_fkey FOREIGN KEY (
        projected_issuing_kid, projected_issuing_candidate_digest
    ) REFERENCES ofarm.tenant_capability_verification_key (
        kid, candidate_digest
    ),
    CONSTRAINT tenant_capability_keyring_head_shape_check CHECK (
        (projected_head_sequence IS NULL) = (projected_head_id IS NULL)
        AND (projected_head_id IS NULL) = (projected_head_digest IS NULL)
    ),
    CONSTRAINT tenant_capability_keyring_admission_check CHECK (
        projected_admission_state IN ('OPEN', 'CLOSED')
        AND (projected_issuing_kid IS NULL) =
            (projected_issuing_candidate_digest IS NULL)
        AND (unresolved_incident_id IS NULL) = (close_act_id IS NULL)
        AND (close_act_id IS NULL) = (close_receipt_id IS NULL)
    )
);

INSERT INTO ofarm.tenant_capability_keyring (
    audience,
    projected_admission_state
)
SELECT audience, 'CLOSED'
  FROM ofarm.tenant_binder_instance;

CREATE UNLOGGED TABLE ofarm.tenant_binding_context (
    backend_pid pg_catalog.int4 NOT NULL,
    backend_start pg_catalog.timestamptz NOT NULL,
    full_xid pg_catalog.xid8 NOT NULL,
    challenge_id pg_catalog.uuid NOT NULL,
    context_state pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    challenge_created_at pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    equality_policy pg_catalog.text COLLATE pg_catalog."C",
    issuer pg_catalog.text COLLATE pg_catalog."C",
    subject pg_catalog.text COLLATE pg_catalog."C",
    binding_version_id pg_catalog.uuid,
    binding_version_digest pg_catalog.text COLLATE pg_catalog."C",
    lifecycle_head_id pg_catalog.uuid,
    lifecycle_head_digest pg_catalog.text COLLATE pg_catalog."C",
    tenant_id pg_catalog.uuid,
    tenant_registration_digest pg_catalog.text COLLATE pg_catalog."C",
    party_ref pg_catalog.text COLLATE pg_catalog."C",
    party_record_kind pg_catalog.text COLLATE pg_catalog."C",
    party_record_id pg_catalog.text COLLATE pg_catalog."C",
    party_schema_digest pg_catalog.text COLLATE pg_catalog."C",
    party_payload_digest pg_catalog.text COLLATE pg_catalog."C",
    capability_key_id pg_catalog.text COLLATE pg_catalog."C",
    capability_key_lifecycle_head_id pg_catalog.uuid,
    capability_key_lifecycle_head_digest pg_catalog.text COLLATE pg_catalog."C",
    capability_nonce pg_catalog.uuid,
    bound_at pg_catalog.timestamptz,
    CONSTRAINT tenant_binding_context_pkey
        PRIMARY KEY (backend_pid, backend_start, full_xid),
    CONSTRAINT tenant_binding_context_backend_key
        UNIQUE (backend_pid, backend_start),
    CONSTRAINT tenant_binding_context_challenge_key UNIQUE (challenge_id),
    CONSTRAINT tenant_binding_context_challenge_id_check CHECK (
        challenge_id <> '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
    ),
    CONSTRAINT tenant_binding_context_state_check CHECK (
        context_state IN ('CHALLENGE', 'BOUND')
    ),
    CONSTRAINT tenant_binding_context_shape_check CHECK (
        (
            context_state = 'CHALLENGE'
            AND equality_policy IS NULL
            AND issuer IS NULL
            AND subject IS NULL
            AND binding_version_id IS NULL
            AND binding_version_digest IS NULL
            AND lifecycle_head_id IS NULL
            AND lifecycle_head_digest IS NULL
            AND tenant_id IS NULL
            AND tenant_registration_digest IS NULL
            AND party_ref IS NULL
            AND party_record_kind IS NULL
            AND party_record_id IS NULL
            AND party_schema_digest IS NULL
            AND party_payload_digest IS NULL
            AND capability_key_id IS NULL
            AND capability_key_lifecycle_head_id IS NULL
            AND capability_key_lifecycle_head_digest IS NULL
            AND capability_nonce IS NULL
            AND bound_at IS NULL
        )
        OR
        (
            context_state = 'BOUND'
            AND equality_policy IS NOT NULL
            AND issuer IS NOT NULL
            AND subject IS NOT NULL
            AND binding_version_id IS NOT NULL
            AND binding_version_digest IS NOT NULL
            AND lifecycle_head_id IS NOT NULL
            AND lifecycle_head_digest IS NOT NULL
            AND tenant_id IS NOT NULL
            AND tenant_registration_digest IS NOT NULL
            AND party_ref IS NOT NULL
            AND party_record_kind = 'ofarm.party.v0.1'
            AND party_record_id = party_ref
            AND party_schema_digest IS NOT NULL
            AND party_payload_digest IS NOT NULL
            AND capability_key_id IS NOT NULL
            AND capability_key_lifecycle_head_id IS NOT NULL
            AND capability_key_lifecycle_head_digest IS NOT NULL
            AND capability_nonce IS NOT NULL
            AND bound_at IS NOT NULL
        )
    )
);

CREATE FUNCTION ofarm.current_backend_start()
RETURNS pg_catalog.timestamptz
LANGUAGE plpgsql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        observed_backend_start pg_catalog.timestamptz;
    BEGIN
        SELECT activity.backend_start
          INTO STRICT observed_backend_start
          FROM pg_catalog.pg_stat_activity AS activity
         WHERE activity.pid = pg_catalog.pg_backend_pid();
        RETURN observed_backend_start;
    EXCEPTION
        WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
            RAISE EXCEPTION USING
                ERRCODE = ''55000'',
                MESSAGE = ''current backend incarnation is unavailable'';
    END';

CREATE FUNCTION ofarm.backend_incarnation_is_live(
    pg_catalog.int4,
    pg_catalog.timestamptz
)
RETURNS pg_catalog.bool
LANGUAGE sql STABLE STRICT PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'SELECT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_stat_activity AS activity
         WHERE activity.pid = $1
           AND activity.backend_start = $2
    )';

CREATE FUNCTION ofarm.current_tenant_id()
RETURNS pg_catalog.uuid
LANGUAGE plpgsql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        observed_backend_start pg_catalog.timestamptz;
        observed_tenant_id pg_catalog.uuid;
    BEGIN
        observed_backend_start := ofarm.current_backend_start();

        SELECT context.tenant_id
          INTO STRICT observed_tenant_id
          FROM ofarm.tenant_binding_context AS context
         WHERE context.backend_pid = pg_catalog.pg_backend_pid()
           AND context.backend_start = observed_backend_start
           AND context.full_xid = pg_catalog.pg_current_xact_id()
           AND context.context_state = ''BOUND'';

        RETURN observed_tenant_id;
    EXCEPTION
        WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
            RAISE EXCEPTION USING
                ERRCODE = ''42501'',
                MESSAGE = ''verified tenant context is absent'';
    END';

CREATE TABLE ofarm.runtime_content_blob (
    content_digest ofarm.sha256_id NOT NULL,
    canonical_bytes pg_catalog.bytea NOT NULL,
    byte_length pg_catalog.int8 NOT NULL,
    CONSTRAINT runtime_content_blob_pkey PRIMARY KEY (content_digest),
    CONSTRAINT runtime_content_blob_digest_length_key
        UNIQUE (content_digest, byte_length),
    CONSTRAINT runtime_content_blob_length_check CHECK (
        byte_length >= 0
        AND byte_length = pg_catalog.octet_length(canonical_bytes)
    ),
    CONSTRAINT runtime_content_blob_digest_check CHECK (
        content_digest::pg_catalog.text =
        'sha256:' OPERATOR(pg_catalog.||)
        pg_catalog.encode(pg_catalog.sha256(canonical_bytes), 'hex')
    )
);

CREATE TABLE ofarm.runtime_tenant_content_blob (
    tenant_id pg_catalog.uuid NOT NULL,
    content_digest ofarm.sha256_id NOT NULL,
    canonical_bytes pg_catalog.bytea NOT NULL,
    byte_length pg_catalog.int8 NOT NULL,
    CONSTRAINT runtime_tenant_content_blob_pkey
        PRIMARY KEY (tenant_id, content_digest),
    CONSTRAINT runtime_tenant_content_blob_digest_length_key
        UNIQUE (tenant_id, content_digest, byte_length),
    CONSTRAINT runtime_tenant_content_blob_tenant_fkey
        FOREIGN KEY (tenant_id) REFERENCES ofarm.tenant_registry (tenant_id),
    CONSTRAINT runtime_tenant_content_blob_length_check CHECK (
        byte_length >= 0
        AND byte_length = pg_catalog.octet_length(canonical_bytes)
    ),
    CONSTRAINT runtime_tenant_content_blob_digest_check CHECK (
        content_digest::pg_catalog.text =
        'sha256:' OPERATOR(pg_catalog.||)
        pg_catalog.encode(pg_catalog.sha256(canonical_bytes), 'hex')
    )
);

CREATE TABLE ofarm.runtime_bundle (
    tenant_id pg_catalog.uuid NOT NULL,
    bundle_digest ofarm.sha256_id NOT NULL,
    bundle_ref ofarm.tenant_local_ref NOT NULL,
    canonical_bytes pg_catalog.bytea NOT NULL,
    byte_length pg_catalog.int8 NOT NULL,
    record_time pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT runtime_bundle_pkey PRIMARY KEY (tenant_id, bundle_digest),
    CONSTRAINT runtime_bundle_ref_key UNIQUE (tenant_id, bundle_ref),
    CONSTRAINT runtime_bundle_tenant_fkey
        FOREIGN KEY (tenant_id) REFERENCES ofarm.tenant_registry (tenant_id),
    CONSTRAINT runtime_bundle_ref_check CHECK (
        bundle_ref::pg_catalog.text =
        'runtimebundle:' OPERATOR(pg_catalog.||) bundle_digest::pg_catalog.text
    ),
    CONSTRAINT runtime_bundle_length_check CHECK (
        byte_length >= 0
        AND byte_length = pg_catalog.octet_length(canonical_bytes)
    ),
    CONSTRAINT runtime_bundle_digest_check CHECK (
        bundle_digest::pg_catalog.text =
        'sha256:' OPERATOR(pg_catalog.||)
        pg_catalog.encode(pg_catalog.sha256(canonical_bytes), 'hex')
    )
);

CREATE TABLE ofarm.runtime_bundle_component (
    tenant_id pg_catalog.uuid NOT NULL,
    bundle_digest ofarm.sha256_id NOT NULL,
    component_role pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    logical_ref ofarm.runtime_logical_ref NOT NULL,
    canonicalization pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    content_placement pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    global_content_digest ofarm.sha256_id,
    tenant_content_digest ofarm.sha256_id,
    byte_length pg_catalog.int8 NOT NULL,
    CONSTRAINT runtime_bundle_component_pkey PRIMARY KEY (
        tenant_id, bundle_digest, component_role, logical_ref
    ),
    CONSTRAINT runtime_bundle_component_bundle_fkey
        FOREIGN KEY (tenant_id, bundle_digest)
        REFERENCES ofarm.runtime_bundle (tenant_id, bundle_digest),
    CONSTRAINT runtime_bundle_component_global_fkey
        FOREIGN KEY (global_content_digest, byte_length)
        REFERENCES ofarm.runtime_content_blob (content_digest, byte_length),
    CONSTRAINT runtime_bundle_component_tenant_fkey
        FOREIGN KEY (tenant_id, tenant_content_digest, byte_length)
        REFERENCES ofarm.runtime_tenant_content_blob (
            tenant_id, content_digest, byte_length
        ),
    CONSTRAINT runtime_bundle_component_role_check CHECK (
        component_role IN (
            'PROFILE_DESCRIPTOR', 'ACTIVE_MANIFEST', 'PROFILE_INSTANCE',
            'PROFILE_POLICY', 'QUERY_SPECIFICATION', 'QUERY_PLAN',
            'VIEW_BINDING', 'CONTRACT_SCHEMA', 'DRAFT_CONTRACT_SCHEMA',
            'VALIDATOR_SOURCE', 'ADAPTER_SOURCE', 'QUERY_OUTPUT_SOURCE',
            'REFERENCE_SNAPSHOT', 'REFERENCE_SOURCE'
        )
    ),
    CONSTRAINT runtime_bundle_component_canonicalization_check CHECK (
        canonicalization IN ('OFARM_CANONICAL_JSON_V1', 'EXACT_BYTES_V1')
    ),
    CONSTRAINT runtime_bundle_component_placement_check CHECK (
        (
            content_placement = 'GLOBAL_IMMUTABLE_CONTENT'
            AND global_content_digest IS NOT NULL
            AND tenant_content_digest IS NULL
        )
        OR
        (
            content_placement = 'TENANT_RUNTIME_SELECTION'
            AND global_content_digest IS NULL
            AND tenant_content_digest IS NOT NULL
        )
    ),
    CONSTRAINT runtime_bundle_component_length_check CHECK (byte_length >= 0)
);

CREATE TABLE ofarm.governed_write_batch (
    tenant_id pg_catalog.uuid NOT NULL,
    batch_id ofarm.tenant_local_ref NOT NULL,
    full_xid pg_catalog.xid8 NOT NULL
        DEFAULT pg_catalog.pg_current_xact_id(),
    authenticated_principal_ref ofarm.tenant_local_ref NOT NULL,
    governed_operation ofarm.ascii_id NOT NULL,
    request_id ofarm.tenant_local_ref NOT NULL,
    runtime_bundle_digest ofarm.sha256_id NOT NULL,
    created_at pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT governed_write_batch_pkey PRIMARY KEY (tenant_id, batch_id),
    CONSTRAINT governed_write_batch_identity_key
        UNIQUE (tenant_id, batch_id, full_xid),
    CONSTRAINT governed_write_batch_transaction_key
        UNIQUE (tenant_id, full_xid),
    CONSTRAINT governed_write_batch_request_key
        UNIQUE (tenant_id, request_id),
    CONSTRAINT governed_write_batch_gate_command_key
        UNIQUE (tenant_id, batch_id, full_xid, request_id),
    CONSTRAINT governed_write_batch_idempotency_command_key
        UNIQUE (
            tenant_id, batch_id, full_xid, request_id,
            authenticated_principal_ref, governed_operation
        ),
    CONSTRAINT governed_write_batch_record_provenance_key
        UNIQUE (tenant_id, batch_id, full_xid, runtime_bundle_digest),
    CONSTRAINT governed_write_batch_tenant_fkey
        FOREIGN KEY (tenant_id) REFERENCES ofarm.tenant_registry (tenant_id),
    CONSTRAINT governed_write_batch_bundle_fkey
        FOREIGN KEY (tenant_id, runtime_bundle_digest)
        REFERENCES ofarm.runtime_bundle (tenant_id, bundle_digest)
);

CREATE TABLE ofarm.kernel_record (
    tenant_id pg_catalog.uuid NOT NULL,
    record_id ofarm.tenant_local_ref NOT NULL,
    record_kind ofarm.ascii_id NOT NULL,
    lane pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    schema_digest ofarm.sha256_id NOT NULL,
    payload pg_catalog.jsonb NOT NULL,
    payload_digest ofarm.sha256_id NOT NULL,
    party_state pg_catalog.text COLLATE pg_catalog."C"
        GENERATED ALWAYS AS (
            CASE
                WHEN record_kind = 'ofarm.party.v0.1'
                THEN payload ->> 'partyState'
                ELSE NULL
            END
        ) STORED,
    party_id pg_catalog.text COLLATE pg_catalog."C"
        GENERATED ALWAYS AS (
            CASE
                WHEN record_kind = 'ofarm.party.v0.1'
                THEN payload ->> 'partyId'
                ELSE NULL
            END
        ) STORED,
    batch_id ofarm.tenant_local_ref NOT NULL,
    batch_full_xid pg_catalog.xid8 NOT NULL
        DEFAULT pg_catalog.pg_current_xact_id(),
    runtime_bundle_digest ofarm.sha256_id NOT NULL,
    record_time pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT kernel_record_pkey PRIMARY KEY (tenant_id, record_id),
    CONSTRAINT kernel_record_tenant_record_batch_key
        UNIQUE (tenant_id, record_id, batch_id, batch_full_xid),
    CONSTRAINT kernel_record_party_eligibility_key UNIQUE (
        tenant_id,
        record_id,
        record_kind,
        schema_digest,
        payload_digest,
        party_state,
        party_id
    ),
    CONSTRAINT kernel_record_batch_provenance_fkey
        FOREIGN KEY (
            tenant_id, batch_id, batch_full_xid, runtime_bundle_digest
        ) REFERENCES ofarm.governed_write_batch (
            tenant_id, batch_id, full_xid, runtime_bundle_digest
        )
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT kernel_record_lane_check CHECK (
        lane IN ('canonical', 'draft')
    )
);

CREATE INDEX kernel_record_kind_idx
    ON ofarm.kernel_record (tenant_id, record_kind COLLATE pg_catalog."C");

CREATE TABLE ofarm.principal_binding (
    equality_policy pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    issuer ofarm.oidc_issuer NOT NULL,
    subject ofarm.oidc_subject NOT NULL,
    binding_version_id pg_catalog.uuid NOT NULL,
    binding_version_digest ofarm.sha256_id NOT NULL,
    tenant_id pg_catalog.uuid NOT NULL,
    tenant_registration_digest ofarm.sha256_id NOT NULL,
    party_ref ofarm.tenant_local_ref NOT NULL,
    party_record_kind pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    party_record_id ofarm.tenant_local_ref NOT NULL,
    party_schema_digest ofarm.sha256_id NOT NULL,
    party_payload_digest ofarm.sha256_id NOT NULL,
    party_state pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    party_payload_party_id ofarm.tenant_local_ref NOT NULL,
    valid_from pg_catalog.timestamptz NOT NULL,
    valid_until pg_catalog.timestamptz NOT NULL,
    predecessor_version_id pg_catalog.uuid,
    created_at pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT principal_binding_pkey PRIMARY KEY (binding_version_id),
    CONSTRAINT principal_binding_digest_key UNIQUE (binding_version_digest),
    CONSTRAINT principal_binding_id_digest_key UNIQUE (
        binding_version_id, binding_version_digest
    ),
    CONSTRAINT principal_binding_principal_version_key UNIQUE (
        equality_policy, issuer, subject, binding_version_id
    ),
    CONSTRAINT principal_binding_principal_version_digest_key UNIQUE (
        equality_policy,
        issuer,
        subject,
        binding_version_id,
        binding_version_digest
    ),
    CONSTRAINT principal_binding_tenant_fkey
        FOREIGN KEY (tenant_id, tenant_registration_digest)
        REFERENCES ofarm.tenant_registry (
            tenant_id, registration_digest
        ),
    CONSTRAINT principal_binding_party_fkey
        FOREIGN KEY (
            tenant_id,
            party_record_id,
            party_record_kind,
            party_schema_digest,
            party_payload_digest,
            party_state,
            party_payload_party_id
        ) REFERENCES ofarm.kernel_record (
            tenant_id,
            record_id,
            record_kind,
            schema_digest,
            payload_digest,
            party_state,
            party_id
        )
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT principal_binding_predecessor_fkey
        FOREIGN KEY (
            equality_policy,
            issuer,
            subject,
            predecessor_version_id
        ) REFERENCES ofarm.principal_binding (
            equality_policy,
            issuer,
            subject,
            binding_version_id
        ),
    CONSTRAINT principal_binding_version_id_check CHECK (
        binding_version_id <>
        '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
    ),
    CONSTRAINT principal_binding_equality_policy_check CHECK (
        equality_policy = 'OIDC_EXACT_UTF8_V1'
    ),
    CONSTRAINT principal_binding_party_shape_check CHECK (
        party_record_kind = 'ofarm.party.v0.1'
        AND party_record_id = party_ref
        AND party_state = 'ACTIVE'
        AND party_payload_party_id = party_ref
    ),
    CONSTRAINT principal_binding_validity_check CHECK (
        valid_from < valid_until
        AND valid_from <> '-infinity'::pg_catalog.timestamptz
        AND valid_until <> 'infinity'::pg_catalog.timestamptz
    ),
    CONSTRAINT principal_binding_digest_check CHECK (
        binding_version_digest::pg_catalog.text =
        ofarm.compute_principal_binding_version_digest(
            equality_policy,
            issuer::pg_catalog.text,
            subject::pg_catalog.text,
            binding_version_id,
            tenant_id,
            tenant_registration_digest::pg_catalog.text,
            party_ref::pg_catalog.text,
            party_record_kind,
            party_record_id::pg_catalog.text,
            party_schema_digest::pg_catalog.text,
            party_payload_digest::pg_catalog.text,
            party_state,
            valid_from,
            valid_until,
            predecessor_version_id
        )
    )
);

CREATE TABLE ofarm.principal_binding_lifecycle (
    equality_policy pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    issuer ofarm.oidc_issuer NOT NULL,
    subject ofarm.oidc_subject NOT NULL,
    stream_sequence pg_catalog.int8 NOT NULL,
    act_id pg_catalog.uuid NOT NULL,
    act_digest ofarm.sha256_id NOT NULL,
    act_kind pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    binding_version_id pg_catalog.uuid NOT NULL,
    binding_version_digest ofarm.sha256_id NOT NULL,
    prior_act_id pg_catalog.uuid,
    prior_act_digest ofarm.sha256_id,
    successor_version_id pg_catalog.uuid,
    successor_version_digest ofarm.sha256_id,
    effective_at pg_catalog.timestamptz NOT NULL,
    decided_at pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    accountable_control_ref ofarm.ascii_id NOT NULL,
    reason ofarm.ascii_id NOT NULL,
    CONSTRAINT principal_binding_lifecycle_pkey PRIMARY KEY (act_id),
    CONSTRAINT principal_binding_lifecycle_digest_key UNIQUE (act_digest),
    CONSTRAINT principal_binding_lifecycle_stream_sequence_key UNIQUE (
        equality_policy, issuer, subject, stream_sequence
    ),
    CONSTRAINT principal_binding_lifecycle_stream_act_key UNIQUE (
        equality_policy, issuer, subject, act_id
    ),
    CONSTRAINT principal_binding_lifecycle_stream_act_digest_key UNIQUE (
        equality_policy, issuer, subject, act_id, act_digest
    ),
    CONSTRAINT principal_binding_lifecycle_prior_key UNIQUE (
        equality_policy, issuer, subject, prior_act_id
    ),
    CONSTRAINT principal_binding_lifecycle_binding_fkey
        FOREIGN KEY (
            equality_policy,
            issuer,
            subject,
            binding_version_id,
            binding_version_digest
        ) REFERENCES ofarm.principal_binding (
            equality_policy,
            issuer,
            subject,
            binding_version_id,
            binding_version_digest
        ),
    CONSTRAINT principal_binding_lifecycle_prior_fkey
        FOREIGN KEY (
            equality_policy,
            issuer,
            subject,
            prior_act_id,
            prior_act_digest
        )
        REFERENCES ofarm.principal_binding_lifecycle (
            equality_policy, issuer, subject, act_id, act_digest
        ) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT principal_binding_lifecycle_successor_fkey
        FOREIGN KEY (
            equality_policy,
            issuer,
            subject,
            successor_version_id,
            successor_version_digest
        ) REFERENCES ofarm.principal_binding (
            equality_policy,
            issuer,
            subject,
            binding_version_id,
            binding_version_digest
        ),
    CONSTRAINT principal_binding_lifecycle_sequence_check CHECK (
        stream_sequence >= 1
        AND ((stream_sequence = 1) = (prior_act_id IS NULL))
        AND ((prior_act_id IS NULL) = (prior_act_digest IS NULL))
    ),
    CONSTRAINT principal_binding_lifecycle_kind_check CHECK (
        act_kind IN ('ACTIVATE', 'REVOKE', 'EXPIRE', 'SUPERSEDE')
    ),
    CONSTRAINT principal_binding_lifecycle_successor_shape_check CHECK (
        (act_kind = 'SUPERSEDE') = (successor_version_id IS NOT NULL)
        AND (successor_version_id IS NULL) =
            (successor_version_digest IS NULL)
    ),
    CONSTRAINT principal_binding_lifecycle_time_check CHECK (
        effective_at <> '-infinity'::pg_catalog.timestamptz
        AND effective_at <> 'infinity'::pg_catalog.timestamptz
        AND decided_at <> '-infinity'::pg_catalog.timestamptz
        AND decided_at <> 'infinity'::pg_catalog.timestamptz
        AND effective_at <= decided_at
    ),
    CONSTRAINT principal_binding_lifecycle_digest_check CHECK (
        act_digest::pg_catalog.text =
        ofarm.compute_principal_lifecycle_act_digest(
            equality_policy,
            issuer::pg_catalog.text,
            subject::pg_catalog.text,
            stream_sequence,
            act_id,
            act_kind,
            binding_version_id,
            binding_version_digest::pg_catalog.text,
            prior_act_id,
            prior_act_digest::pg_catalog.text,
            successor_version_id,
            successor_version_digest::pg_catalog.text,
            effective_at,
            decided_at,
            accountable_control_ref::pg_catalog.text,
            reason::pg_catalog.text
        )
    )
);

CREATE TABLE ofarm.principal_binding_current (
    equality_policy pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    issuer ofarm.oidc_issuer NOT NULL,
    subject ofarm.oidc_subject NOT NULL,
    current_state pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    binding_version_id pg_catalog.uuid,
    binding_version_digest ofarm.sha256_id,
    lifecycle_head_id pg_catalog.uuid NOT NULL,
    lifecycle_head_digest ofarm.sha256_id NOT NULL,
    rebuilt_at pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT principal_binding_current_pkey
        PRIMARY KEY (equality_policy, issuer, subject),
    CONSTRAINT principal_binding_current_binding_fkey
        FOREIGN KEY (
            equality_policy,
            issuer,
            subject,
            binding_version_id,
            binding_version_digest
        ) REFERENCES ofarm.principal_binding (
            equality_policy,
            issuer,
            subject,
            binding_version_id,
            binding_version_digest
        ),
    CONSTRAINT principal_binding_current_head_fkey
        FOREIGN KEY (
            equality_policy,
            issuer,
            subject,
            lifecycle_head_id,
            lifecycle_head_digest
        ) REFERENCES ofarm.principal_binding_lifecycle (
            equality_policy, issuer, subject, act_id, act_digest
        ) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT principal_binding_current_state_check CHECK (
        current_state IN ('ACTIVE', 'INACTIVE')
    ),
    CONSTRAINT principal_binding_current_shape_check CHECK (
        (current_state = 'ACTIVE') = (binding_version_id IS NOT NULL)
        AND (binding_version_id IS NULL) = (binding_version_digest IS NULL)
    )
);

CREATE TABLE ofarm.kernel_edge (
    tenant_id pg_catalog.uuid NOT NULL,
    edge_id pg_catalog.uuid NOT NULL DEFAULT pg_catalog.gen_random_uuid(),
    edge_kind ofarm.ascii_id NOT NULL,
    src_record_id ofarm.tenant_local_ref NOT NULL,
    dst_record_id ofarm.tenant_local_ref NOT NULL,
    batch_id ofarm.tenant_local_ref NOT NULL,
    batch_full_xid pg_catalog.xid8 NOT NULL
        DEFAULT pg_catalog.pg_current_xact_id(),
    record_time pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT kernel_edge_pkey PRIMARY KEY (tenant_id, edge_id),
    CONSTRAINT kernel_edge_src_fkey
        FOREIGN KEY (tenant_id, src_record_id)
        REFERENCES ofarm.kernel_record (tenant_id, record_id)
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT kernel_edge_dst_fkey
        FOREIGN KEY (tenant_id, dst_record_id)
        REFERENCES ofarm.kernel_record (tenant_id, record_id)
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT kernel_edge_batch_fkey
        FOREIGN KEY (tenant_id, batch_id, batch_full_xid)
        REFERENCES ofarm.governed_write_batch (tenant_id, batch_id, full_xid)
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT kernel_edge_id_check CHECK (
        edge_id <> '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
    ),
    CONSTRAINT kernel_edge_kind_check CHECK (
        edge_kind IN (
            'AUTHORITY_BASIS',
            'EVIDENCE',
            'REVIEW',
            'EVENT_SOURCE',
            'LINEAGE_SUPERSEDES',
            'LINEAGE_REVISES',
            'MATERIALIZATION_BASIS',
            'PROMOTION_EMITS',
            'COMPLIANCE_CLAIM',
            'STRUCTURE_PAYLOAD',
            'LINEAGE_SUPERSEDES_INTENT',
            'DISPUTE'
        )
    )
);

CREATE INDEX kernel_edge_src_idx
    ON ofarm.kernel_edge (
        tenant_id, src_record_id COLLATE pg_catalog."C",
        edge_kind COLLATE pg_catalog."C"
    );
CREATE INDEX kernel_edge_dst_idx
    ON ofarm.kernel_edge (
        tenant_id, dst_record_id COLLATE pg_catalog."C",
        edge_kind COLLATE pg_catalog."C"
    );
CREATE UNIQUE INDEX kernel_edge_promotion_destination_key
    ON ofarm.kernel_edge (tenant_id, dst_record_id COLLATE pg_catalog."C")
    WHERE edge_kind = 'PROMOTION_EMITS';

CREATE FUNCTION ofarm.validate_promotion_edge()
RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        source_record_kind pg_catalog.text;
        source_payload pg_catalog.jsonb;
        source_batch_id pg_catalog.text;
        source_batch_full_xid pg_catalog.xid8;
        destination_batch_id pg_catalog.text;
        destination_batch_full_xid pg_catalog.xid8;
    BEGIN
        IF NEW.edge_kind <> ''PROMOTION_EMITS'' THEN
            RETURN NULL;
        END IF;

        SELECT record.record_kind,
               record.payload,
               record.batch_id,
               record.batch_full_xid
          INTO STRICT source_record_kind,
                      source_payload,
                      source_batch_id,
                      source_batch_full_xid
          FROM ofarm.kernel_record AS record
         WHERE record.tenant_id = NEW.tenant_id
           AND record.record_id = NEW.src_record_id;
        SELECT record.batch_id,
               record.batch_full_xid
          INTO STRICT destination_batch_id,
                      destination_batch_full_xid
          FROM ofarm.kernel_record AS record
         WHERE record.tenant_id = NEW.tenant_id
           AND record.record_id = NEW.dst_record_id;

        IF source_record_kind <> ''ofarm.promotiontrace.v0.1''
           OR source_batch_id <> NEW.batch_id
           OR source_batch_full_xid <> NEW.batch_full_xid
           OR destination_batch_id <> NEW.batch_id
           OR destination_batch_full_xid <> NEW.batch_full_xid THEN
            RAISE EXCEPTION USING
                ERRCODE = ''23514'',
                MESSAGE = ''promotion reachability must share tenant and batch'';
        END IF;

        IF (
            source_payload ->> ''semanticEventRef'' = NEW.dst_record_id
            OR COALESCE(
                source_payload -> ''emittedAssertionRecordRefs'',
                ''[]''::pg_catalog.jsonb
            ) OPERATOR(pg_catalog.?) NEW.dst_record_id::pg_catalog.text
            OR COALESCE(
                source_payload -> ''emittedReviewDecisionRefs'',
                ''[]''::pg_catalog.jsonb
            ) OPERATOR(pg_catalog.?) NEW.dst_record_id::pg_catalog.text
            OR COALESCE(
                source_payload -> ''emittedAcceptedConsequenceRefs'',
                ''[]''::pg_catalog.jsonb
            ) OPERATOR(pg_catalog.?) NEW.dst_record_id::pg_catalog.text
        ) IS NOT TRUE THEN
            RAISE EXCEPTION USING
                ERRCODE = ''23514'',
                MESSAGE = ''promotion destination is absent from the trace payload'';
        END IF;
        RETURN NULL;
    END';

CREATE FUNCTION ofarm.require_promotion_reachability()
RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN
        IF NEW.record_kind IN (
            ''ofarm.assertionrecord.v0.1'',
            ''ofarm.semanticeventenvelope.v0.1'',
            ''ofarm.reviewdecision.v0.1'',
            ''ofarm.acceptedeventconsequence.v0.1''
        ) AND NOT EXISTS (
            SELECT 1
              FROM ofarm.kernel_edge AS edge
             WHERE edge.tenant_id = NEW.tenant_id
               AND edge.dst_record_id = NEW.record_id
               AND edge.batch_id = NEW.batch_id
               AND edge.batch_full_xid = NEW.batch_full_xid
               AND edge.edge_kind = ''PROMOTION_EMITS''
        ) THEN
            RAISE EXCEPTION USING
                ERRCODE = ''23514'',
                MESSAGE = ''authoritative record lacks same-batch promotion reachability'';
        END IF;
        RETURN NULL;
    END';

CREATE CONSTRAINT TRIGGER kernel_edge_validate_promotion
AFTER INSERT ON ofarm.kernel_edge
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION ofarm.validate_promotion_edge();

CREATE CONSTRAINT TRIGGER kernel_record_require_promotion
AFTER INSERT ON ofarm.kernel_record
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION ofarm.require_promotion_reachability();

CREATE TABLE ofarm.kernel_gate_log (
    tenant_id pg_catalog.uuid NOT NULL,
    entry_id pg_catalog.uuid NOT NULL DEFAULT pg_catalog.gen_random_uuid(),
    batch_id ofarm.tenant_local_ref NOT NULL,
    batch_full_xid pg_catalog.xid8 NOT NULL
        DEFAULT pg_catalog.pg_current_xact_id(),
    request_id ofarm.tenant_local_ref NOT NULL,
    gate ofarm.ascii_id NOT NULL,
    outcome ofarm.ascii_id NOT NULL,
    reason_code ofarm.ascii_id,
    rationale pg_catalog.text COLLATE pg_catalog."C",
    related_refs pg_catalog.jsonb,
    record_time pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT kernel_gate_log_pkey PRIMARY KEY (tenant_id, entry_id),
    CONSTRAINT kernel_gate_log_command_fkey
        FOREIGN KEY (tenant_id, batch_id, batch_full_xid, request_id)
        REFERENCES ofarm.governed_write_batch (
            tenant_id, batch_id, full_xid, request_id
        )
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT kernel_gate_log_entry_id_check CHECK (
        entry_id <> '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
    )
);

CREATE INDEX kernel_gate_log_request_idx
    ON ofarm.kernel_gate_log (
        tenant_id, request_id COLLATE pg_catalog."C"
    );

CREATE TABLE ofarm.kernel_idempotency (
    tenant_id pg_catalog.uuid NOT NULL,
    authenticated_principal_ref ofarm.tenant_local_ref NOT NULL,
    governed_operation ofarm.ascii_id NOT NULL,
    caller_key ofarm.idempotency_caller_key NOT NULL,
    request_digest ofarm.sha256_id NOT NULL,
    request_id ofarm.tenant_local_ref NOT NULL,
    batch_id ofarm.tenant_local_ref NOT NULL,
    batch_full_xid pg_catalog.xid8 NOT NULL
        DEFAULT pg_catalog.pg_current_xact_id(),
    result_record_id ofarm.tenant_local_ref NOT NULL,
    created_at pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT kernel_idempotency_pkey PRIMARY KEY (
        tenant_id,
        authenticated_principal_ref,
        governed_operation,
        caller_key
    ),
    CONSTRAINT kernel_idempotency_command_fkey
        FOREIGN KEY (
            tenant_id, batch_id, batch_full_xid, request_id,
            authenticated_principal_ref, governed_operation
        ) REFERENCES ofarm.governed_write_batch (
            tenant_id, batch_id, full_xid, request_id,
            authenticated_principal_ref, governed_operation
        )
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT kernel_idempotency_result_fkey
        FOREIGN KEY (
            tenant_id, result_record_id, batch_id, batch_full_xid
        ) REFERENCES ofarm.kernel_record (
            tenant_id, record_id, batch_id, batch_full_xid
        )
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE ofarm.derived_materialization (
    tenant_id pg_catalog.uuid NOT NULL,
    materialization_id ofarm.tenant_local_ref NOT NULL,
    key_digest ofarm.sha256_id NOT NULL,
    materialization_key pg_catalog.jsonb NOT NULL,
    target_twin ofarm.tenant_local_ref NOT NULL,
    anchor_scope_ref ofarm.tenant_local_ref NOT NULL,
    time_policy pg_catalog.jsonb NOT NULL,
    use_class ofarm.ascii_id NOT NULL,
    freshness pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    current_state pg_catalog.jsonb NOT NULL,
    basis_record_id ofarm.tenant_local_ref NOT NULL,
    snapshot_record_id ofarm.tenant_local_ref NOT NULL,
    context_snapshot_ref ofarm.tenant_local_ref NOT NULL,
    freshness_vector pg_catalog.jsonb NOT NULL,
    batch_id ofarm.tenant_local_ref NOT NULL,
    batch_full_xid pg_catalog.xid8 NOT NULL
        DEFAULT pg_catalog.pg_current_xact_id(),
    generated_at pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    superseded_by ofarm.tenant_local_ref,
    CONSTRAINT derived_materialization_pkey
        PRIMARY KEY (tenant_id, materialization_id),
    CONSTRAINT derived_materialization_id_key_identity_key
        UNIQUE (
            tenant_id,
            materialization_id,
            key_digest,
            materialization_key
        ),
    CONSTRAINT derived_materialization_basis_fkey
        FOREIGN KEY (tenant_id, basis_record_id)
        REFERENCES ofarm.kernel_record (tenant_id, record_id),
    CONSTRAINT derived_materialization_snapshot_fkey
        FOREIGN KEY (tenant_id, snapshot_record_id)
        REFERENCES ofarm.kernel_record (tenant_id, record_id),
    CONSTRAINT derived_materialization_context_fkey
        FOREIGN KEY (tenant_id, context_snapshot_ref)
        REFERENCES ofarm.kernel_record (tenant_id, record_id),
    CONSTRAINT derived_materialization_batch_fkey
        FOREIGN KEY (tenant_id, batch_id, batch_full_xid)
        REFERENCES ofarm.governed_write_batch (tenant_id, batch_id, full_xid)
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT derived_materialization_superseded_fkey
        FOREIGN KEY (
            tenant_id,
            superseded_by,
            key_digest,
            materialization_key
        )
        REFERENCES ofarm.derived_materialization (
            tenant_id,
            materialization_id,
            key_digest,
            materialization_key
        )
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT derived_materialization_freshness_check CHECK (
        freshness IN ('FRESH', 'STALE', 'INVALID')
    ),
    CONSTRAINT derived_materialization_key_digest_check CHECK (
        key_digest::pg_catalog.text =
            ofarm.compute_materialization_key_digest(materialization_key)
    )
);

CREATE UNIQUE INDEX derived_materialization_live_key_key
    ON ofarm.derived_materialization (
        tenant_id,
        key_digest COLLATE pg_catalog."C",
        materialization_key
    )
    WHERE superseded_by IS NULL;

CREATE TABLE ofarm.derived_dependency_index (
    tenant_id pg_catalog.uuid NOT NULL,
    entry_id pg_catalog.uuid NOT NULL DEFAULT pg_catalog.gen_random_uuid(),
    dependency_source_ref pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    dependency_source_family ofarm.ascii_id NOT NULL,
    dependency_source_lane pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    dependency_runtime_bundle_digest ofarm.sha256_id,
    dependency_runtime_component_role pg_catalog.text COLLATE pg_catalog."C",
    dependency_kernel_record_ref ofarm.tenant_local_ref
        GENERATED ALWAYS AS (
            CASE WHEN dependency_source_lane = 'KERNEL_RECORD'
                 THEN dependency_source_ref ELSE NULL END
        ) STORED,
    dependency_runtime_logical_ref ofarm.runtime_logical_ref
        GENERATED ALWAYS AS (
            CASE WHEN dependency_source_lane = 'RUNTIME_BUNDLE_COMPONENT'
                 THEN dependency_source_ref::pg_catalog.text ELSE NULL END
        ) STORED,
    materialization_id ofarm.tenant_local_ref NOT NULL,
    key_digest ofarm.sha256_id NOT NULL,
    materialization_key pg_catalog.jsonb NOT NULL,
    entry pg_catalog.jsonb NOT NULL,
    generated_at pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT derived_dependency_index_pkey PRIMARY KEY (tenant_id, entry_id),
    CONSTRAINT derived_dependency_index_materialization_fkey
        FOREIGN KEY (
            tenant_id,
            materialization_id,
            key_digest,
            materialization_key
        )
        REFERENCES ofarm.derived_materialization (
            tenant_id,
            materialization_id,
            key_digest,
            materialization_key
        ),
    CONSTRAINT derived_dependency_index_kernel_source_fkey
        FOREIGN KEY (tenant_id, dependency_kernel_record_ref)
        REFERENCES ofarm.kernel_record (tenant_id, record_id),
    CONSTRAINT derived_dependency_index_runtime_source_fkey
        FOREIGN KEY (
            tenant_id,
            dependency_runtime_bundle_digest,
            dependency_runtime_component_role,
            dependency_runtime_logical_ref
        ) REFERENCES ofarm.runtime_bundle_component (
            tenant_id,
            bundle_digest,
            component_role,
            logical_ref
        ),
    CONSTRAINT derived_dependency_index_source_lane_check CHECK (
        (
            dependency_source_lane = 'KERNEL_RECORD'
            AND ofarm.valid_ascii_id(dependency_source_ref)
            AND dependency_kernel_record_ref IS NOT NULL
            AND dependency_runtime_bundle_digest IS NULL
            AND dependency_runtime_component_role IS NULL
            AND dependency_runtime_logical_ref IS NULL
        )
        OR
        (
            dependency_source_lane = 'RUNTIME_BUNDLE_COMPONENT'
            AND ofarm.valid_runtime_logical_ref(dependency_source_ref)
            AND dependency_kernel_record_ref IS NULL
            AND dependency_runtime_bundle_digest IS NOT NULL
            AND dependency_runtime_component_role IS NOT NULL
            AND dependency_runtime_logical_ref IS NOT NULL
        )
        OR
        (
            dependency_source_lane = 'EVALUATION_TIME_BOUNDARY'
            AND dependency_source_ref = 'evaluation-time-boundary'
            AND dependency_kernel_record_ref IS NULL
            AND dependency_runtime_bundle_digest IS NULL
            AND dependency_runtime_component_role IS NULL
            AND dependency_runtime_logical_ref IS NULL
        )
    ),
    CONSTRAINT derived_dependency_index_key_digest_check CHECK (
        key_digest::pg_catalog.text =
            ofarm.compute_materialization_key_digest(materialization_key)
    ),
    CONSTRAINT derived_dependency_index_entry_id_check CHECK (
        entry_id <> '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
    )
);

CREATE INDEX derived_dependency_source_idx
    ON ofarm.derived_dependency_index (
        tenant_id, dependency_source_ref COLLATE pg_catalog."C"
    );
CREATE INDEX derived_dependency_key_idx
    ON ofarm.derived_dependency_index (
        tenant_id, key_digest COLLATE pg_catalog."C"
    );

CREATE TABLE ofarm.reference_snapshot_data (
    tenant_id pg_catalog.uuid NOT NULL,
    snapshot_ref ofarm.tenant_local_ref NOT NULL,
    data_family ofarm.ascii_id NOT NULL,
    artifact_ref ofarm.tenant_local_ref,
    source_digest ofarm.sha256_id,
    parser_label ofarm.ascii_id,
    record_count pg_catalog.int4,
    payload pg_catalog.jsonb NOT NULL,
    payload_digest ofarm.sha256_id NOT NULL,
    batch_id ofarm.tenant_local_ref NOT NULL,
    batch_full_xid pg_catalog.xid8 NOT NULL
        DEFAULT pg_catalog.pg_current_xact_id(),
    record_time pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT reference_snapshot_data_pkey
        PRIMARY KEY (tenant_id, snapshot_ref, data_family),
    CONSTRAINT reference_snapshot_data_snapshot_fkey
        FOREIGN KEY (tenant_id, snapshot_ref)
        REFERENCES ofarm.kernel_record (tenant_id, record_id),
    CONSTRAINT reference_snapshot_data_batch_fkey
        FOREIGN KEY (tenant_id, batch_id, batch_full_xid)
        REFERENCES ofarm.governed_write_batch (tenant_id, batch_id, full_xid)
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT reference_snapshot_data_count_check CHECK (
        record_count IS NULL OR record_count >= 0
    )
);

CREATE TABLE ofarm.runtime_trace (
    tenant_id pg_catalog.uuid NOT NULL,
    trace_id ofarm.tenant_local_ref NOT NULL,
    trace_kind ofarm.ascii_id NOT NULL,
    schema_digest ofarm.sha256_id NOT NULL,
    payload pg_catalog.jsonb NOT NULL,
    payload_digest ofarm.sha256_id NOT NULL,
    batch_id ofarm.tenant_local_ref NOT NULL,
    batch_full_xid pg_catalog.xid8 NOT NULL
        DEFAULT pg_catalog.pg_current_xact_id(),
    record_time pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT runtime_trace_pkey PRIMARY KEY (tenant_id, trace_id),
    CONSTRAINT runtime_trace_batch_fkey
        FOREIGN KEY (tenant_id, batch_id, batch_full_xid)
        REFERENCES ofarm.governed_write_batch (tenant_id, batch_id, full_xid)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE ofarm.export_artifact (
    tenant_id pg_catalog.uuid NOT NULL,
    artifact_ref ofarm.tenant_local_ref NOT NULL,
    digest ofarm.sha256_id NOT NULL,
    metadata_record_id ofarm.tenant_local_ref NOT NULL,
    document pg_catalog.jsonb NOT NULL,
    batch_id ofarm.tenant_local_ref NOT NULL,
    batch_full_xid pg_catalog.xid8 NOT NULL
        DEFAULT pg_catalog.pg_current_xact_id(),
    record_time pg_catalog.timestamptz NOT NULL
        DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT export_artifact_pkey PRIMARY KEY (tenant_id, artifact_ref),
    CONSTRAINT export_artifact_metadata_fkey
        FOREIGN KEY (tenant_id, metadata_record_id)
        REFERENCES ofarm.kernel_record (tenant_id, record_id),
    CONSTRAINT export_artifact_batch_fkey
        FOREIGN KEY (tenant_id, batch_id, batch_full_xid)
        REFERENCES ofarm.governed_write_batch (tenant_id, batch_id, full_xid)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE ofarm.kernel_record_reference (
    tenant_id pg_catalog.uuid NOT NULL,
    owner_record_id ofarm.tenant_local_ref NOT NULL,
    reference_role ofarm.ascii_id NOT NULL,
    json_pointer pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    stable_ordinal pg_catalog.int4 NOT NULL,
    extraction_rule_version pg_catalog.int4 NOT NULL,
    extraction_rule_digest ofarm.sha256_id NOT NULL,
    batch_id ofarm.tenant_local_ref NOT NULL,
    batch_full_xid pg_catalog.xid8 NOT NULL
        DEFAULT pg_catalog.pg_current_xact_id(),
    target_lane pg_catalog.text COLLATE pg_catalog."C" NOT NULL,
    target_record_id ofarm.tenant_local_ref,
    global_content_kind ofarm.ascii_id,
    global_content_digest ofarm.sha256_id,
    CONSTRAINT kernel_record_reference_pkey PRIMARY KEY (
        tenant_id,
        owner_record_id,
        reference_role,
        json_pointer,
        stable_ordinal
    ),
    CONSTRAINT kernel_record_reference_owner_fkey
        FOREIGN KEY (
            tenant_id, owner_record_id, batch_id, batch_full_xid
        ) REFERENCES ofarm.kernel_record (
            tenant_id, record_id, batch_id, batch_full_xid
        ) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT kernel_record_reference_target_fkey
        FOREIGN KEY (tenant_id, target_record_id)
        REFERENCES ofarm.kernel_record (tenant_id, record_id)
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT kernel_record_reference_global_fkey
        FOREIGN KEY (global_content_digest)
        REFERENCES ofarm.runtime_content_blob (content_digest),
    CONSTRAINT kernel_record_reference_ordinal_check CHECK (
        stable_ordinal >= 0 AND extraction_rule_version >= 1
    ),
    CONSTRAINT kernel_record_reference_pointer_check CHECK (
        pg_catalog.octet_length(json_pointer) BETWEEN 1 AND 2048
        AND json_pointer ~ '^/'
    ),
    CONSTRAINT kernel_record_reference_lane_check CHECK (
        (
            target_lane = 'TENANT_RECORD'
            AND target_record_id IS NOT NULL
            AND global_content_kind IS NULL
            AND global_content_digest IS NULL
        )
        OR
        (
            target_lane = 'GLOBAL_CONTENT'
            AND target_record_id IS NULL
            AND global_content_kind IS NOT NULL
            AND global_content_digest IS NOT NULL
        )
    )
);

CREATE FUNCTION ofarm.register_tenant(requested_tenant_ref pg_catalog.text)
RETURNS TABLE (
    tenant_id pg_catalog.uuid,
    tenant_ref pg_catalog.text,
    registration_digest pg_catalog.text
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        checked_tenant_ref ofarm.tenant_ref;
        generated_tenant_id pg_catalog.uuid;
        generated_lock_key pg_catalog.int8;
        generated_digest pg_catalog.text;
        attempts pg_catalog.int4 := 0;
    BEGIN
        checked_tenant_ref := requested_tenant_ref::ofarm.tenant_ref;
        IF EXISTS (
            SELECT 1
              FROM ofarm.tenant_registry AS registry
             WHERE registry.tenant_ref = checked_tenant_ref
        ) THEN
            RAISE EXCEPTION USING
                ERRCODE = ''23505'',
                MESSAGE = ''tenant reference is already registered'';
        END IF;

        LOOP
            attempts := attempts + 1;
            IF attempts > 16 THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''55000'',
                    MESSAGE = ''tenant identity allocation refused'';
            END IF;
            generated_tenant_id := pg_catalog.gen_random_uuid();
            generated_lock_key := pg_catalog.hashtextextended(
                ''OFARM_TENANT_LOCK_V1'' || generated_tenant_id::pg_catalog.text,
                0
            );
            generated_digest := ofarm.compute_tenant_registration_digest(
                generated_tenant_id,
                checked_tenant_ref::pg_catalog.text,
                generated_lock_key
            );
            BEGIN
                INSERT INTO ofarm.tenant_registry (
                    tenant_id,
                    tenant_ref,
                    equality_policy,
                    advisory_lock_key,
                    registration_digest
                ) VALUES (
                    generated_tenant_id,
                    checked_tenant_ref,
                    ''OFARM_ASCII_ID_V1'',
                    generated_lock_key,
                    generated_digest
                );
                EXIT;
            EXCEPTION
                WHEN unique_violation THEN
                    IF EXISTS (
                        SELECT 1
                          FROM ofarm.tenant_registry AS registry
                         WHERE registry.tenant_ref = checked_tenant_ref
                    ) THEN
                        RAISE EXCEPTION USING
                            ERRCODE = ''23505'',
                            MESSAGE = ''tenant reference is already registered'';
                    END IF;
            END;
        END LOOP;

        RETURN QUERY SELECT
            generated_tenant_id,
            checked_tenant_ref::pg_catalog.text,
            generated_digest;
    END';

CREATE FUNCTION ofarm.transition_principal_binding(
    requested_equality_policy pg_catalog.text,
    requested_issuer pg_catalog.text,
    requested_subject pg_catalog.text,
    expected_head_id pg_catalog.uuid,
    expected_head_digest pg_catalog.text,
    requested_act_id pg_catalog.uuid,
    requested_act_digest pg_catalog.text,
    requested_act_kind pg_catalog.text,
    requested_binding_version_id pg_catalog.uuid,
    requested_binding_version_digest pg_catalog.text,
    requested_candidate_version_id pg_catalog.uuid,
    requested_candidate_version_digest pg_catalog.text,
    requested_tenant_id pg_catalog.uuid,
    requested_tenant_registration_digest pg_catalog.text,
    requested_party_ref pg_catalog.text,
    requested_party_record_kind pg_catalog.text,
    requested_party_record_id pg_catalog.text,
    requested_party_schema_digest pg_catalog.text,
    requested_party_payload_digest pg_catalog.text,
    requested_party_state pg_catalog.text,
    requested_valid_from pg_catalog.timestamptz,
    requested_valid_until pg_catalog.timestamptz,
    requested_predecessor_version_id pg_catalog.uuid,
    requested_effective_at pg_catalog.timestamptz,
    requested_decided_at pg_catalog.timestamptz,
    requested_accountable_control_ref pg_catalog.text,
    requested_reason pg_catalog.text
)
RETURNS pg_catalog.void
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        checked_issuer ofarm.oidc_issuer;
        checked_subject ofarm.oidc_subject;
        previous_act ofarm.principal_binding_lifecycle%ROWTYPE;
        projected ofarm.principal_binding_current%ROWTYPE;
        folded_act pg_catalog.record;
        projection_present pg_catalog.bool;
        previous_act_present pg_catalog.bool;
        fold_state pg_catalog.text := ''INACTIVE'';
        fold_active_version_id pg_catalog.uuid;
        fold_active_version_digest pg_catalog.text;
        fold_prior_act_id pg_catalog.uuid;
        fold_prior_act_digest pg_catalog.text;
        fold_sequence pg_catalog.int8 := 0;
        prior_active_version_id pg_catalog.uuid;
        prior_active_version_digest pg_catalog.text;
        next_active_version_id pg_catalog.uuid;
        next_active_version_digest pg_catalog.text;
        lifecycle_successor_version_id pg_catalog.uuid;
        lifecycle_successor_version_digest pg_catalog.text;
        next_state pg_catalog.text;
        next_sequence pg_catalog.int8;
        observed_decision_now pg_catalog.timestamptz;
    BEGIN
        IF pg_catalog.current_setting(''transaction_isolation'') <>
                ''read committed'' THEN
            RAISE EXCEPTION USING
                ERRCODE = ''25001'',
                MESSAGE = ''principal transition requires READ COMMITTED'';
        END IF;
        PERFORM pg_catalog.pg_advisory_xact_lock(1330004306, 1413694001);
        IF requested_equality_policy <> ''OIDC_EXACT_UTF8_V1'' THEN
            RAISE EXCEPTION USING
                ERRCODE = ''22023'', MESSAGE = ''equality policy is not exact'';
        END IF;
        checked_issuer := requested_issuer::ofarm.oidc_issuer;
        checked_subject := requested_subject::ofarm.oidc_subject;
        observed_decision_now := pg_catalog.clock_timestamp();
        IF (expected_head_id IS NULL) <> (expected_head_digest IS NULL) THEN
            RAISE EXCEPTION USING
                ERRCODE = ''22023'', MESSAGE = ''expected lifecycle head is partial'';
        END IF;
        IF requested_effective_at IS NULL
           OR requested_decided_at IS NULL
           OR requested_effective_at > requested_decided_at
           OR requested_decided_at > observed_decision_now
           OR requested_effective_at IN (
                ''-infinity''::pg_catalog.timestamptz,
                ''infinity''::pg_catalog.timestamptz
           )
           OR requested_decided_at IN (
                ''-infinity''::pg_catalog.timestamptz,
                ''infinity''::pg_catalog.timestamptz
           ) THEN
            RAISE EXCEPTION USING
                ERRCODE = ''22023'',
                MESSAGE = ''lifecycle decision time is not presently effective'';
        END IF;

        SELECT current_row.* INTO projected
          FROM ofarm.principal_binding_current AS current_row
         WHERE current_row.equality_policy = requested_equality_policy
           AND current_row.issuer = checked_issuer
           AND current_row.subject = checked_subject
         FOR UPDATE;
        projection_present := FOUND;

        SELECT act.* INTO previous_act
          FROM ofarm.principal_binding_lifecycle AS act
         WHERE act.equality_policy = requested_equality_policy
           AND act.issuer = checked_issuer
           AND act.subject = checked_subject
         ORDER BY act.stream_sequence DESC
         LIMIT 1;
        previous_act_present := FOUND;

        IF NOT previous_act_present THEN
            IF expected_head_id IS NOT NULL OR projection_present THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''40001'', MESSAGE = ''lifecycle head is not empty'';
            END IF;
            IF requested_act_kind <> ''ACTIVATE'' THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''23514'', MESSAGE = ''first lifecycle act must activate'';
            END IF;
            next_sequence := 1;
            prior_active_version_id := NULL;
        ELSE
            FOR folded_act IN
                SELECT act.stream_sequence,
                       act.act_id,
                       act.act_digest,
                       act.act_kind,
                       act.binding_version_id,
                       act.binding_version_digest,
                       act.prior_act_id,
                       act.prior_act_digest,
                       act.successor_version_id,
                       act.successor_version_digest
                  FROM ofarm.principal_binding_lifecycle AS act
                 WHERE act.equality_policy = requested_equality_policy
                   AND act.issuer = checked_issuer
                   AND act.subject = checked_subject
                 ORDER BY act.stream_sequence
            LOOP
                IF folded_act.stream_sequence <> fold_sequence + 1
                   OR folded_act.prior_act_id IS DISTINCT FROM fold_prior_act_id
                   OR folded_act.prior_act_digest::pg_catalog.text
                        IS DISTINCT FROM fold_prior_act_digest THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''lifecycle authority chain differs'';
                END IF;
                IF folded_act.act_kind = ''ACTIVATE'' THEN
                    IF fold_state = ''ACTIVE''
                       OR folded_act.successor_version_id IS NOT NULL
                       OR folded_act.successor_version_digest IS NOT NULL THEN
                        RAISE EXCEPTION USING
                            ERRCODE = ''55000'',
                            MESSAGE = ''lifecycle activation fold differs'';
                    END IF;
                    fold_state := ''ACTIVE'';
                    fold_active_version_id := folded_act.binding_version_id;
                    fold_active_version_digest :=
                        folded_act.binding_version_digest::pg_catalog.text;
                ELSIF folded_act.act_kind = ''SUPERSEDE'' THEN
                    IF fold_state <> ''ACTIVE''
                       OR folded_act.binding_version_id IS DISTINCT FROM
                            fold_active_version_id
                       OR folded_act.binding_version_digest::pg_catalog.text
                            IS DISTINCT FROM fold_active_version_digest
                       OR folded_act.successor_version_id IS NULL
                       OR folded_act.successor_version_digest IS NULL THEN
                        RAISE EXCEPTION USING
                            ERRCODE = ''55000'',
                            MESSAGE = ''lifecycle supersession fold differs'';
                    END IF;
                    fold_active_version_id := folded_act.successor_version_id;
                    fold_active_version_digest :=
                        folded_act.successor_version_digest::pg_catalog.text;
                ELSIF folded_act.act_kind IN (''REVOKE'', ''EXPIRE'') THEN
                    IF fold_state <> ''ACTIVE''
                       OR folded_act.binding_version_id IS DISTINCT FROM
                            fold_active_version_id
                       OR folded_act.binding_version_digest::pg_catalog.text
                            IS DISTINCT FROM fold_active_version_digest
                       OR folded_act.successor_version_id IS NOT NULL
                       OR folded_act.successor_version_digest IS NOT NULL THEN
                        RAISE EXCEPTION USING
                            ERRCODE = ''55000'',
                            MESSAGE = ''lifecycle inactivation fold differs'';
                    END IF;
                    fold_state := ''INACTIVE'';
                    fold_active_version_id := NULL;
                    fold_active_version_digest := NULL;
                ELSE
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''lifecycle act kind is not closed'';
                END IF;
                fold_sequence := folded_act.stream_sequence;
                fold_prior_act_id := folded_act.act_id;
                fold_prior_act_digest :=
                    folded_act.act_digest::pg_catalog.text;
            END LOOP;

            IF previous_act.act_id IS DISTINCT FROM expected_head_id
               OR previous_act.act_digest::pg_catalog.text
                    IS DISTINCT FROM expected_head_digest THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''40001'', MESSAGE = ''lifecycle head precondition failed'';
            END IF;
            IF fold_sequence <> previous_act.stream_sequence
               OR fold_prior_act_id IS DISTINCT FROM previous_act.act_id
               OR fold_prior_act_digest IS DISTINCT FROM
                    previous_act.act_digest::pg_catalog.text THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''55000'', MESSAGE = ''lifecycle authority head differs'';
            END IF;
            IF NOT projection_present
               OR projected.current_state IS DISTINCT FROM fold_state
               OR projected.binding_version_id IS DISTINCT FROM
                    fold_active_version_id
               OR projected.binding_version_digest::pg_catalog.text
                    IS DISTINCT FROM fold_active_version_digest
               OR projected.lifecycle_head_id IS DISTINCT FROM previous_act.act_id
               OR projected.lifecycle_head_digest IS DISTINCT FROM
                    previous_act.act_digest THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''55000'', MESSAGE = ''lifecycle projection differs'';
            END IF;
            next_sequence := previous_act.stream_sequence + 1;
            prior_active_version_id := fold_active_version_id;
            prior_active_version_digest := fold_active_version_digest;
        END IF;

        IF requested_act_kind = ''ACTIVATE'' THEN
            IF prior_active_version_id IS NOT NULL
               OR requested_candidate_version_id IS DISTINCT FROM
                    requested_binding_version_id
               OR requested_candidate_version_digest IS DISTINCT FROM
                    requested_binding_version_digest THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''23514'', MESSAGE = ''active binding already exists'';
            END IF;
            next_active_version_id := requested_candidate_version_id;
            next_active_version_digest := requested_candidate_version_digest;
            lifecycle_successor_version_id := NULL;
            lifecycle_successor_version_digest := NULL;
            next_state := ''ACTIVE'';
        ELSIF requested_act_kind IN (''REVOKE'', ''EXPIRE'') THEN
            IF prior_active_version_id IS DISTINCT FROM requested_binding_version_id
               OR prior_active_version_digest IS DISTINCT FROM
                    requested_binding_version_digest
               OR requested_candidate_version_id IS NOT NULL
               OR requested_candidate_version_digest IS NOT NULL
               OR requested_tenant_id IS NOT NULL
               OR requested_tenant_registration_digest IS NOT NULL
               OR requested_party_ref IS NOT NULL
               OR requested_party_record_kind IS NOT NULL
               OR requested_party_record_id IS NOT NULL
               OR requested_party_schema_digest IS NOT NULL
               OR requested_party_payload_digest IS NOT NULL
               OR requested_party_state IS NOT NULL
               OR requested_valid_from IS NOT NULL
               OR requested_valid_until IS NOT NULL
               OR requested_predecessor_version_id IS NOT NULL THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''23514'', MESSAGE = ''inactive transition target differs'';
            END IF;
            next_active_version_id := NULL;
            next_active_version_digest := NULL;
            lifecycle_successor_version_id := NULL;
            lifecycle_successor_version_digest := NULL;
            next_state := ''INACTIVE'';
        ELSIF requested_act_kind = ''SUPERSEDE'' THEN
            IF prior_active_version_id IS DISTINCT FROM requested_binding_version_id
               OR prior_active_version_digest IS DISTINCT FROM
                    requested_binding_version_digest
               OR requested_candidate_version_id IS NULL
               OR requested_candidate_version_digest IS NULL
               OR requested_predecessor_version_id IS DISTINCT FROM
                    requested_binding_version_id THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''23514'', MESSAGE = ''supersession target differs'';
            END IF;
            next_active_version_id := requested_candidate_version_id;
            next_active_version_digest := requested_candidate_version_digest;
            lifecycle_successor_version_id := requested_candidate_version_id;
            lifecycle_successor_version_digest := requested_candidate_version_digest;
            next_state := ''ACTIVE'';
        ELSE
            RAISE EXCEPTION USING
                ERRCODE = ''23514'', MESSAGE = ''lifecycle act kind is not closed'';
        END IF;

        IF requested_act_kind IN (''ACTIVATE'', ''SUPERSEDE'') THEN
            IF requested_valid_from IS NULL
               OR requested_valid_until IS NULL
               OR requested_valid_from > requested_effective_at
               OR requested_effective_at >= requested_valid_until
               OR requested_valid_from > observed_decision_now
               OR observed_decision_now >= requested_valid_until THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''23514'',
                    MESSAGE = ''binding validity does not cover lifecycle activation'';
            END IF;
            INSERT INTO ofarm.principal_binding (
                equality_policy,
                issuer,
                subject,
                binding_version_id,
                binding_version_digest,
                tenant_id,
                tenant_registration_digest,
                party_ref,
                party_record_kind,
                party_record_id,
                party_schema_digest,
                party_payload_digest,
                party_state,
                party_payload_party_id,
                valid_from,
                valid_until,
                predecessor_version_id
            ) VALUES (
                requested_equality_policy,
                checked_issuer,
                checked_subject,
                requested_candidate_version_id,
                requested_candidate_version_digest::ofarm.sha256_id,
                requested_tenant_id,
                requested_tenant_registration_digest::ofarm.sha256_id,
                requested_party_ref::ofarm.tenant_local_ref,
                requested_party_record_kind,
                requested_party_record_id::ofarm.tenant_local_ref,
                requested_party_schema_digest::ofarm.sha256_id,
                requested_party_payload_digest::ofarm.sha256_id,
                requested_party_state,
                requested_party_ref::ofarm.tenant_local_ref,
                requested_valid_from,
                requested_valid_until,
                requested_predecessor_version_id
            );
        ELSE
            PERFORM 1
              FROM ofarm.principal_binding AS binding
             WHERE binding.equality_policy = requested_equality_policy
               AND binding.issuer = checked_issuer
               AND binding.subject = checked_subject
               AND binding.binding_version_id = requested_binding_version_id
               AND binding.binding_version_digest::pg_catalog.text =
                    requested_binding_version_digest;
            IF NOT FOUND THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''23514'', MESSAGE = ''transition binding differs'';
            END IF;
        END IF;

        INSERT INTO ofarm.principal_binding_lifecycle (
            equality_policy,
            issuer,
            subject,
            stream_sequence,
            act_id,
            act_digest,
            act_kind,
            binding_version_id,
            binding_version_digest,
            prior_act_id,
            prior_act_digest,
            successor_version_id,
            successor_version_digest,
            effective_at,
            decided_at,
            accountable_control_ref,
            reason
        ) VALUES (
            requested_equality_policy,
            checked_issuer,
            checked_subject,
            next_sequence,
            requested_act_id,
            requested_act_digest::ofarm.sha256_id,
            requested_act_kind,
            requested_binding_version_id,
            requested_binding_version_digest::ofarm.sha256_id,
            previous_act.act_id,
            previous_act.act_digest,
            lifecycle_successor_version_id,
            lifecycle_successor_version_digest::ofarm.sha256_id,
            requested_effective_at,
            requested_decided_at,
            requested_accountable_control_ref::ofarm.ascii_id,
            requested_reason::ofarm.ascii_id
        );

        INSERT INTO ofarm.principal_binding_current (
            equality_policy,
            issuer,
            subject,
            current_state,
            binding_version_id,
            binding_version_digest,
            lifecycle_head_id,
            lifecycle_head_digest,
            rebuilt_at
        ) VALUES (
            requested_equality_policy,
            checked_issuer,
            checked_subject,
            next_state,
            next_active_version_id,
            next_active_version_digest,
            requested_act_id,
            requested_act_digest::ofarm.sha256_id,
            pg_catalog.clock_timestamp()
        )
        ON CONFLICT (equality_policy, issuer, subject) DO UPDATE SET
            current_state = EXCLUDED.current_state,
            binding_version_id = EXCLUDED.binding_version_id,
            binding_version_digest = EXCLUDED.binding_version_digest,
            lifecycle_head_id = EXCLUDED.lifecycle_head_id,
            lifecycle_head_digest = EXCLUDED.lifecycle_head_digest,
            rebuilt_at = EXCLUDED.rebuilt_at;
    END';

CREATE FUNCTION ofarm.rebuild_principal_binding_current()
RETURNS pg_catalog.int8
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        act_row pg_catalog.record;
        stream_started pg_catalog.bool := false;
        stream_equality_policy pg_catalog.text;
        stream_issuer ofarm.oidc_issuer;
        stream_subject ofarm.oidc_subject;
        fold_state pg_catalog.text;
        fold_active_version_id pg_catalog.uuid;
        fold_active_version_digest ofarm.sha256_id;
        fold_prior_act_id pg_catalog.uuid;
        fold_prior_act_digest ofarm.sha256_id;
        fold_sequence pg_catalog.int8;
        fold_head_id pg_catalog.uuid;
        fold_head_digest ofarm.sha256_id;
        rebuilt_count pg_catalog.int8 := 0;
    BEGIN
        IF pg_catalog.current_setting(''transaction_isolation'') <>
                ''read committed'' THEN
            RAISE EXCEPTION USING
                ERRCODE = ''25001'',
                MESSAGE = ''principal rebuild requires READ COMMITTED'';
        END IF;
        PERFORM pg_catalog.pg_advisory_xact_lock(1330004306, 1413694001);
        DELETE FROM ofarm.principal_binding_current;
        FOR act_row IN
            SELECT act.*
              FROM ofarm.principal_binding_lifecycle AS act
             ORDER BY
                act.equality_policy COLLATE pg_catalog."C",
                act.issuer COLLATE pg_catalog."C",
                act.subject COLLATE pg_catalog."C",
                act.stream_sequence
        LOOP
            IF NOT stream_started
               OR act_row.equality_policy IS DISTINCT FROM stream_equality_policy
               OR act_row.issuer IS DISTINCT FROM stream_issuer
               OR act_row.subject IS DISTINCT FROM stream_subject THEN
                IF stream_started THEN
                    INSERT INTO ofarm.principal_binding_current (
                        equality_policy,
                        issuer,
                        subject,
                        current_state,
                        binding_version_id,
                        binding_version_digest,
                        lifecycle_head_id,
                        lifecycle_head_digest,
                        rebuilt_at
                    ) VALUES (
                        stream_equality_policy,
                        stream_issuer,
                        stream_subject,
                        fold_state,
                        fold_active_version_id,
                        fold_active_version_digest,
                        fold_head_id,
                        fold_head_digest,
                        pg_catalog.clock_timestamp()
                    );
                    rebuilt_count := rebuilt_count + 1;
                END IF;
                stream_started := true;
                stream_equality_policy := act_row.equality_policy;
                stream_issuer := act_row.issuer;
                stream_subject := act_row.subject;
                fold_state := ''INACTIVE'';
                fold_active_version_id := NULL;
                fold_active_version_digest := NULL;
                fold_prior_act_id := NULL;
                fold_prior_act_digest := NULL;
                fold_sequence := 0;
                fold_head_id := NULL;
                fold_head_digest := NULL;
            END IF;

            IF act_row.stream_sequence <> fold_sequence + 1
               OR act_row.prior_act_id IS DISTINCT FROM fold_prior_act_id
               OR act_row.prior_act_digest IS DISTINCT FROM fold_prior_act_digest THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''55000'',
                    MESSAGE = ''lifecycle authority chain differs during rebuild'';
            END IF;

            PERFORM 1
              FROM ofarm.principal_binding AS binding
             WHERE binding.equality_policy = stream_equality_policy
               AND binding.issuer = stream_issuer
               AND binding.subject = stream_subject
               AND binding.binding_version_id = act_row.binding_version_id
               AND binding.binding_version_digest = act_row.binding_version_digest;
            IF NOT FOUND THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''55000'',
                    MESSAGE = ''lifecycle binding differs during rebuild'';
            END IF;

            IF act_row.act_kind = ''ACTIVATE'' THEN
                IF fold_state = ''ACTIVE''
                   OR act_row.successor_version_id IS NOT NULL
                   OR act_row.successor_version_digest IS NOT NULL THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''lifecycle activation differs during rebuild'';
                END IF;
                fold_state := ''ACTIVE'';
                fold_active_version_id := act_row.binding_version_id;
                fold_active_version_digest := act_row.binding_version_digest;
            ELSIF act_row.act_kind = ''SUPERSEDE'' THEN
                IF fold_state <> ''ACTIVE''
                   OR act_row.binding_version_id IS DISTINCT FROM
                        fold_active_version_id
                   OR act_row.binding_version_digest IS DISTINCT FROM
                        fold_active_version_digest
                   OR act_row.successor_version_id IS NULL
                   OR act_row.successor_version_digest IS NULL THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''lifecycle supersession differs during rebuild'';
                END IF;
                PERFORM 1
                  FROM ofarm.principal_binding AS successor
                 WHERE successor.equality_policy = stream_equality_policy
                   AND successor.issuer = stream_issuer
                   AND successor.subject = stream_subject
                   AND successor.binding_version_id =
                        act_row.successor_version_id
                   AND successor.binding_version_digest =
                        act_row.successor_version_digest;
                IF NOT FOUND THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''lifecycle successor differs during rebuild'';
                END IF;
                fold_active_version_id := act_row.successor_version_id;
                fold_active_version_digest := act_row.successor_version_digest;
            ELSIF act_row.act_kind IN (''REVOKE'', ''EXPIRE'') THEN
                IF fold_state <> ''ACTIVE''
                   OR act_row.binding_version_id IS DISTINCT FROM
                        fold_active_version_id
                   OR act_row.binding_version_digest IS DISTINCT FROM
                        fold_active_version_digest
                   OR act_row.successor_version_id IS NOT NULL
                   OR act_row.successor_version_digest IS NOT NULL THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''lifecycle inactivation differs during rebuild'';
                END IF;
                fold_state := ''INACTIVE'';
                fold_active_version_id := NULL;
                fold_active_version_digest := NULL;
            ELSE
                RAISE EXCEPTION USING
                    ERRCODE = ''55000'',
                    MESSAGE = ''lifecycle act kind differs during rebuild'';
            END IF;

            fold_sequence := act_row.stream_sequence;
            fold_prior_act_id := act_row.act_id;
            fold_prior_act_digest := act_row.act_digest;
            fold_head_id := act_row.act_id;
            fold_head_digest := act_row.act_digest;
        END LOOP;

        IF stream_started THEN
            INSERT INTO ofarm.principal_binding_current (
                equality_policy,
                issuer,
                subject,
                current_state,
                binding_version_id,
                binding_version_digest,
                lifecycle_head_id,
                lifecycle_head_digest,
                rebuilt_at
            ) VALUES (
                stream_equality_policy,
                stream_issuer,
                stream_subject,
                fold_state,
                fold_active_version_id,
                fold_active_version_digest,
                fold_head_id,
                fold_head_digest,
                pg_catalog.clock_timestamp()
            );
            rebuilt_count := rebuilt_count + 1;
        END IF;
        RETURN rebuilt_count;
    END';

CREATE FUNCTION ofarm.fold_principal_binding_authority(
    requested_equality_policy pg_catalog.text,
    requested_issuer pg_catalog.text,
    requested_subject pg_catalog.text
)
RETURNS TABLE (
    current_state pg_catalog.text,
    binding_version_id pg_catalog.uuid,
    binding_version_digest pg_catalog.text,
    lifecycle_head_id pg_catalog.uuid,
    lifecycle_head_digest pg_catalog.text
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        act_row ofarm.principal_binding_lifecycle%ROWTYPE;
        expected_sequence pg_catalog.int8 := 0;
        expected_prior_id pg_catalog.uuid;
        expected_prior_digest pg_catalog.text;
        recomputed_digest pg_catalog.text;
        observed_any pg_catalog.bool := false;
    BEGIN
        current_state := ''INACTIVE'';
        binding_version_id := NULL;
        binding_version_digest := NULL;
        lifecycle_head_id := NULL;
        lifecycle_head_digest := NULL;

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
                    ERRCODE = ''55000'',
                    MESSAGE = ''principal lifecycle authority differs'';
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
                    ERRCODE = ''55000'',
                    MESSAGE = ''principal lifecycle binding differs'';
            END IF;

            IF act_row.act_kind = ''ACTIVATE'' THEN
                IF current_state = ''ACTIVE''
                   OR act_row.successor_version_id IS NOT NULL
                   OR act_row.successor_version_digest IS NOT NULL THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''principal activation authority differs'';
                END IF;
                current_state := ''ACTIVE'';
                binding_version_id := act_row.binding_version_id;
                binding_version_digest :=
                    act_row.binding_version_digest::pg_catalog.text;
            ELSIF act_row.act_kind = ''SUPERSEDE'' THEN
                IF current_state <> ''ACTIVE''
                   OR act_row.binding_version_id IS DISTINCT FROM
                        binding_version_id
                   OR act_row.binding_version_digest::pg_catalog.text
                        IS DISTINCT FROM binding_version_digest
                   OR act_row.successor_version_id IS NULL
                   OR act_row.successor_version_digest IS NULL THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''principal supersession authority differs'';
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
                        ERRCODE = ''55000'',
                        MESSAGE = ''principal successor authority differs'';
                END IF;
                binding_version_id := act_row.successor_version_id;
                binding_version_digest :=
                    act_row.successor_version_digest::pg_catalog.text;
            ELSIF act_row.act_kind IN (''REVOKE'', ''EXPIRE'') THEN
                IF current_state <> ''ACTIVE''
                   OR act_row.binding_version_id IS DISTINCT FROM
                        binding_version_id
                   OR act_row.binding_version_digest::pg_catalog.text
                        IS DISTINCT FROM binding_version_digest
                   OR act_row.successor_version_id IS NOT NULL
                   OR act_row.successor_version_digest IS NOT NULL THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''principal inactivation authority differs'';
                END IF;
                current_state := ''INACTIVE'';
                binding_version_id := NULL;
                binding_version_digest := NULL;
            ELSE
                RAISE EXCEPTION USING
                    ERRCODE = ''55000'',
                    MESSAGE = ''principal lifecycle kind differs'';
            END IF;

            expected_sequence := act_row.stream_sequence;
            expected_prior_id := act_row.act_id;
            expected_prior_digest := act_row.act_digest::pg_catalog.text;
            lifecycle_head_id := act_row.act_id;
            lifecycle_head_digest := act_row.act_digest::pg_catalog.text;
        END LOOP;

        IF observed_any THEN
            RETURN NEXT;
        END IF;
    END';

CREATE FUNCTION ofarm.fold_tenant_capability_key_lifecycle(
    selected_key_id pg_catalog.text
)
RETURNS TABLE (
    admission_state pg_catalog.text,
    head_sequence pg_catalog.int8,
    head_id pg_catalog.uuid,
    head_digest pg_catalog.text,
    issuing_kid pg_catalog.text,
    issuing_candidate_digest pg_catalog.text,
    issuing_activated_at_us pg_catalog.int8,
    issuing_retirement_us pg_catalog.int8,
    issuing_verification_end_us pg_catalog.int8,
    selected_ever_activated pg_catalog.bool,
    selected_candidate_digest pg_catalog.text,
    selected_activated_at_us pg_catalog.int8,
    selected_retirement_us pg_catalog.int8,
    selected_verification_end_us pg_catalog.int8,
    selected_revoked pg_catalog.bool,
    unresolved_incident_id pg_catalog.uuid,
    close_act_id pg_catalog.uuid,
    close_receipt_id pg_catalog.uuid,
    close_reason pg_catalog.text,
    close_target_kid pg_catalog.text,
    close_target_candidate_digest pg_catalog.text,
    close_target_revoked pg_catalog.bool
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        act_row ofarm.tenant_capability_key_lifecycle%ROWTYPE;
        expected_sequence pg_catalog.int8 := 0;
        expected_prior_id pg_catalog.uuid;
        expected_prior_digest pg_catalog.text;
        recomputed_digest pg_catalog.text;
        binder_audience pg_catalog.text;
        last_rotated_old_kid pg_catalog.text;
        last_rotated_old_digest pg_catalog.text;
        known_kids pg_catalog.text[] := ARRAY[]::pg_catalog.text[];
        known_candidate_digests pg_catalog.text[] := ARRAY[]::pg_catalog.text[];
        known_activated_at_us pg_catalog.int8[] := ARRAY[]::pg_catalog.int8[];
        known_retirement_us pg_catalog.int8[] := ARRAY[]::pg_catalog.int8[];
        known_verification_end_us pg_catalog.int8[] := ARRAY[]::pg_catalog.int8[];
        known_revoked pg_catalog.bool[] := ARRAY[]::pg_catalog.bool[];
        old_key_index pg_catalog.int4;
        new_key_index pg_catalog.int4;
        target_key_index pg_catalog.int4;
    BEGIN
        SELECT instance.audience INTO STRICT binder_audience
          FROM ofarm.tenant_binder_instance AS instance
         WHERE instance.singleton;
        admission_state := ''CLOSED'';
        head_sequence := NULL;
        head_id := NULL;
        head_digest := NULL;
        issuing_kid := NULL;
        issuing_candidate_digest := NULL;
        issuing_activated_at_us := NULL;
        issuing_retirement_us := NULL;
        issuing_verification_end_us := NULL;
        selected_ever_activated := false;
        selected_candidate_digest := NULL;
        selected_activated_at_us := NULL;
        selected_retirement_us := NULL;
        selected_verification_end_us := NULL;
        selected_revoked := false;
        unresolved_incident_id := NULL;
        close_act_id := NULL;
        close_receipt_id := NULL;
        close_reason := NULL;
        close_target_kid := NULL;
        close_target_candidate_digest := NULL;
        close_target_revoked := false;

        FOR act_row IN
            SELECT act.*
              FROM ofarm.tenant_capability_key_lifecycle AS act
             ORDER BY act.stream_sequence
        LOOP
            IF act_row.stream_sequence <> expected_sequence + 1
               OR act_row.prior_act_id IS DISTINCT FROM expected_prior_id
               OR act_row.prior_act_digest::pg_catalog.text
                    IS DISTINCT FROM expected_prior_digest
               OR act_row.audience <> binder_audience
               OR act_row.algorithm <> ''Ed25519''
               OR act_row.accountable_control_ref::pg_catalog.text <>
                    ''ofarm_capability_key_control_login'' THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''55000'',
                    MESSAGE = ''capability key lifecycle authority differs'';
            END IF;
            recomputed_digest := ofarm.compute_tenant_capability_key_act_digest(
                act_row.stream_sequence,
                act_row.act_id,
                act_row.prior_act_id,
                act_row.prior_act_digest::pg_catalog.text,
                act_row.act_kind,
                act_row.old_kid,
                act_row.old_candidate_digest::pg_catalog.text,
                act_row.new_kid,
                act_row.new_candidate_digest::pg_catalog.text,
                act_row.audience,
                act_row.algorithm,
                act_row.decided_at_us,
                act_row.effective_at_us,
                act_row.new_issuance_end_us,
                act_row.old_verification_end_us,
                act_row.incident_id,
                act_row.close_receipt_id,
                act_row.preflight_receipt_digest::pg_catalog.text,
                act_row.kms_evidence_digest::pg_catalog.text,
                act_row.iam_evidence_digest::pg_catalog.text,
                act_row.accountable_control_ref::pg_catalog.text,
                act_row.reason::pg_catalog.text
            );
            IF recomputed_digest <> act_row.act_digest::pg_catalog.text THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''55000'',
                    MESSAGE = ''capability key lifecycle digest differs'';
            END IF;

            IF act_row.act_kind = ''ACTIVATE'' THEN
                new_key_index := pg_catalog.array_position(
                    known_kids, act_row.new_kid
                );
                IF act_row.old_kid IS NOT NULL
                   OR act_row.new_kid IS NULL
                   OR new_key_index IS NOT NULL
                   OR act_row.preflight_receipt_digest IS NULL
                   OR act_row.kms_evidence_digest IS NULL
                   OR act_row.iam_evidence_digest IS NULL
                   OR act_row.new_issuance_end_us <>
                        act_row.effective_at_us + 7776000000000
                   OR act_row.old_verification_end_us IS NOT NULL
                   OR act_row.incident_id IS NOT NULL
                   OR act_row.reason IS DISTINCT FROM (CASE
                        WHEN expected_sequence = 0 THEN ''INITIAL_ACTIVATION''
                        WHEN close_reason = ''COMPROMISE''
                            THEN ''COMPROMISE_REPLACEMENT''
                        WHEN close_reason = ''NATURAL_RETIREMENT''
                            THEN ''NATURAL_RETIREMENT_REPLACEMENT''
                        ELSE NULL
                      END)
                   OR (
                        expected_sequence = 0
                        AND admission_state <> ''CLOSED''
                   )
                   OR (
                        expected_sequence > 0
                        AND (
                            admission_state <> ''CLOSED''
                            OR unresolved_incident_id IS NULL
                            OR (
                                issuing_verification_end_us IS NOT NULL
                                AND act_row.effective_at_us <
                                    issuing_verification_end_us
                            )
                        )
                   ) THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''capability key activation fold differs'';
                END IF;
                known_kids := pg_catalog.array_append(
                    known_kids, act_row.new_kid
                );
                known_candidate_digests := pg_catalog.array_append(
                    known_candidate_digests,
                    act_row.new_candidate_digest::pg_catalog.text
                );
                known_activated_at_us := pg_catalog.array_append(
                    known_activated_at_us, act_row.effective_at_us
                );
                known_retirement_us := pg_catalog.array_append(
                    known_retirement_us, act_row.new_issuance_end_us
                );
                known_verification_end_us := pg_catalog.array_append(
                    known_verification_end_us,
                    act_row.new_issuance_end_us + 65000000
                );
                known_revoked := pg_catalog.array_append(known_revoked, false);
                issuing_kid := act_row.new_kid;
                issuing_candidate_digest :=
                    act_row.new_candidate_digest::pg_catalog.text;
                issuing_activated_at_us := act_row.effective_at_us;
                issuing_retirement_us := act_row.new_issuance_end_us;
                issuing_verification_end_us :=
                    act_row.new_issuance_end_us + 65000000;
                IF selected_key_id = act_row.new_kid THEN
                    selected_ever_activated := true;
                    selected_candidate_digest :=
                        act_row.new_candidate_digest::pg_catalog.text;
                    selected_activated_at_us := act_row.effective_at_us;
                    selected_retirement_us := act_row.new_issuance_end_us;
                    selected_verification_end_us :=
                        act_row.new_issuance_end_us + 65000000;
                    selected_revoked := false;
                END IF;
                IF expected_sequence = 0 THEN
                    admission_state := ''OPEN'';
                    last_rotated_old_kid := NULL;
                    last_rotated_old_digest := NULL;
                END IF;
            ELSIF act_row.act_kind = ''ROTATE'' THEN
                old_key_index := pg_catalog.array_position(
                    known_kids, act_row.old_kid
                );
                new_key_index := pg_catalog.array_position(
                    known_kids, act_row.new_kid
                );
                IF admission_state <> ''OPEN''
                   OR last_rotated_old_kid IS NOT NULL
                   OR old_key_index IS NULL
                   OR known_candidate_digests[old_key_index] IS DISTINCT FROM
                        act_row.old_candidate_digest::pg_catalog.text
                   OR known_revoked[old_key_index]
                   OR act_row.old_kid IS DISTINCT FROM issuing_kid
                   OR act_row.old_candidate_digest::pg_catalog.text
                        IS DISTINCT FROM issuing_candidate_digest
                   OR act_row.new_kid IS NULL
                   OR act_row.new_kid = act_row.old_kid
                   OR new_key_index IS NOT NULL
                   OR act_row.preflight_receipt_digest IS NULL
                   OR act_row.kms_evidence_digest IS NULL
                   OR act_row.iam_evidence_digest IS NULL
                   OR act_row.new_issuance_end_us <>
                        act_row.effective_at_us + 7776000000000
                   OR act_row.old_verification_end_us <>
                        act_row.effective_at_us + 65000000
                   OR act_row.incident_id IS NOT NULL
                   OR act_row.reason <> ''GRACEFUL_ROTATION'' THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''capability key rotation fold differs'';
                END IF;
                known_retirement_us[old_key_index] := act_row.effective_at_us;
                known_verification_end_us[old_key_index] :=
                    act_row.old_verification_end_us;
                known_kids := pg_catalog.array_append(
                    known_kids, act_row.new_kid
                );
                known_candidate_digests := pg_catalog.array_append(
                    known_candidate_digests,
                    act_row.new_candidate_digest::pg_catalog.text
                );
                known_activated_at_us := pg_catalog.array_append(
                    known_activated_at_us, act_row.effective_at_us
                );
                known_retirement_us := pg_catalog.array_append(
                    known_retirement_us, act_row.new_issuance_end_us
                );
                known_verification_end_us := pg_catalog.array_append(
                    known_verification_end_us,
                    act_row.new_issuance_end_us + 65000000
                );
                known_revoked := pg_catalog.array_append(known_revoked, false);
                IF selected_key_id = act_row.old_kid THEN
                    selected_retirement_us := act_row.effective_at_us;
                    selected_verification_end_us :=
                        act_row.old_verification_end_us;
                END IF;
                IF selected_key_id = act_row.new_kid THEN
                    selected_ever_activated := true;
                    selected_candidate_digest :=
                        act_row.new_candidate_digest::pg_catalog.text;
                    selected_activated_at_us := act_row.effective_at_us;
                    selected_retirement_us := act_row.new_issuance_end_us;
                    selected_verification_end_us :=
                        act_row.new_issuance_end_us + 65000000;
                    selected_revoked := false;
                END IF;
                last_rotated_old_kid := act_row.old_kid;
                last_rotated_old_digest :=
                    act_row.old_candidate_digest::pg_catalog.text;
                issuing_kid := act_row.new_kid;
                issuing_candidate_digest :=
                    act_row.new_candidate_digest::pg_catalog.text;
                issuing_activated_at_us := act_row.effective_at_us;
                issuing_retirement_us := act_row.new_issuance_end_us;
                issuing_verification_end_us :=
                    act_row.new_issuance_end_us + 65000000;
            ELSIF act_row.act_kind = ''CLOSE_ADMISSION'' THEN
                target_key_index := pg_catalog.array_position(
                    known_kids, act_row.old_kid
                );
                IF admission_state <> ''OPEN''
                   OR act_row.old_kid IS NULL
                   OR act_row.new_kid IS NOT NULL
                   OR act_row.incident_id IS NULL
                   OR act_row.preflight_receipt_digest IS NOT NULL
                   OR act_row.kms_evidence_digest IS NULL
                   OR act_row.iam_evidence_digest IS NULL
                   OR act_row.new_issuance_end_us IS NOT NULL
                   OR act_row.old_verification_end_us IS NOT NULL
                   OR act_row.reason NOT IN (
                        ''COMPROMISE'', ''ROTATION_HANDOFF'',
                        ''NATURAL_RETIREMENT''
                   )
                   OR target_key_index IS NULL
                   OR known_candidate_digests[target_key_index]
                        IS DISTINCT FROM
                        act_row.old_candidate_digest::pg_catalog.text
                   OR NOT (
                        (
                            act_row.old_kid IS NOT DISTINCT FROM issuing_kid
                            AND act_row.old_candidate_digest::pg_catalog.text
                                IS NOT DISTINCT FROM issuing_candidate_digest
                            AND act_row.reason = ''NATURAL_RETIREMENT''
                            AND act_row.effective_at_us >=
                                issuing_verification_end_us
                        )
                        OR
                        (
                            act_row.reason = ''COMPROMISE''
                            AND NOT known_revoked[target_key_index]
                            AND act_row.effective_at_us <
                                known_verification_end_us[target_key_index]
                        )
                        OR
                        (
                            act_row.reason = ''ROTATION_HANDOFF''
                            AND act_row.old_kid IS NOT DISTINCT FROM
                                last_rotated_old_kid
                            AND act_row.old_candidate_digest::pg_catalog.text
                                IS NOT DISTINCT FROM last_rotated_old_digest
                        )
                   ) THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''capability admission close fold differs'';
                END IF;
                admission_state := ''CLOSED'';
                unresolved_incident_id := act_row.incident_id;
                close_act_id := act_row.act_id;
                close_receipt_id := act_row.close_receipt_id;
                close_reason := act_row.reason::pg_catalog.text;
                close_target_kid := act_row.old_kid;
                close_target_candidate_digest :=
                    act_row.old_candidate_digest::pg_catalog.text;
                close_target_revoked := false;
            ELSIF act_row.act_kind = ''REVOKE'' THEN
                target_key_index := pg_catalog.array_position(
                    known_kids, act_row.old_kid
                );
                IF admission_state <> ''CLOSED''
                   OR unresolved_incident_id IS NULL
                   OR act_row.incident_id IS DISTINCT FROM unresolved_incident_id
                   OR act_row.close_receipt_id IS DISTINCT FROM close_receipt_id
                   OR act_row.old_kid IS NULL
                   OR act_row.new_kid IS NOT NULL
                   OR act_row.preflight_receipt_digest IS NOT NULL
                   OR act_row.kms_evidence_digest IS NULL
                   OR act_row.iam_evidence_digest IS NULL
                   OR act_row.new_issuance_end_us IS NOT NULL
                   OR act_row.old_verification_end_us IS NOT NULL
                   OR target_key_index IS NULL
                   OR known_revoked[target_key_index]
                   OR known_candidate_digests[target_key_index]
                        IS DISTINCT FROM
                        act_row.old_candidate_digest::pg_catalog.text
                   OR (
                        act_row.effective_at_us >=
                            known_verification_end_us[target_key_index]
                        AND NOT (
                            close_reason = ''ROTATION_HANDOFF''
                            AND act_row.old_kid IS NOT DISTINCT FROM
                                last_rotated_old_kid
                            AND act_row.old_candidate_digest::pg_catalog.text
                                IS NOT DISTINCT FROM last_rotated_old_digest
                        )
                   )
                   OR act_row.old_kid IS DISTINCT FROM close_target_kid
                   OR act_row.old_candidate_digest::pg_catalog.text
                        IS DISTINCT FROM close_target_candidate_digest
                   OR act_row.reason IS DISTINCT FROM close_reason THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''capability key revocation fold differs'';
                END IF;
                known_revoked[target_key_index] := true;
                IF selected_key_id = act_row.old_kid THEN
                    selected_revoked := true;
                END IF;
                close_target_revoked := true;
                IF act_row.old_kid IS NOT DISTINCT FROM issuing_kid THEN
                    issuing_kid := NULL;
                    issuing_candidate_digest := NULL;
                    issuing_activated_at_us := NULL;
                    issuing_retirement_us := NULL;
                    issuing_verification_end_us := NULL;
                END IF;
                IF act_row.old_kid IS NOT DISTINCT FROM
                        last_rotated_old_kid THEN
                    last_rotated_old_kid := NULL;
                    last_rotated_old_digest := NULL;
                END IF;
            ELSIF act_row.act_kind = ''RESUME_ADMISSION'' THEN
                IF admission_state <> ''CLOSED''
                   OR unresolved_incident_id IS NULL
                   OR act_row.incident_id IS DISTINCT FROM unresolved_incident_id
                   OR act_row.close_receipt_id IS DISTINCT FROM close_receipt_id
                   OR act_row.old_kid IS NOT NULL
                   OR act_row.new_kid IS DISTINCT FROM issuing_kid
                   OR act_row.new_candidate_digest::pg_catalog.text
                        IS DISTINCT FROM issuing_candidate_digest
                   OR act_row.preflight_receipt_digest IS NOT NULL
                   OR act_row.kms_evidence_digest IS NULL
                   OR act_row.iam_evidence_digest IS NULL
                   OR act_row.new_issuance_end_us IS NOT NULL
                   OR act_row.old_verification_end_us IS NOT NULL
                   OR last_rotated_old_kid IS NOT NULL
                   OR act_row.reason IS DISTINCT FROM (CASE close_reason
                        WHEN ''COMPROMISE'' THEN ''COMPROMISE_RESOLVED''
                        WHEN ''ROTATION_HANDOFF''
                            THEN ''ROTATION_HANDOFF_COMPLETE''
                        WHEN ''NATURAL_RETIREMENT''
                            THEN ''NATURAL_RETIREMENT_COMPLETE''
                        ELSE NULL
                      END)
                   OR (
                        close_reason IN (
                            ''ROTATION_HANDOFF'', ''COMPROMISE''
                        )
                        AND (
                            NOT close_target_revoked
                            OR issuing_kid IS NULL
                            OR issuing_kid = close_target_kid
                        )
                   )
                   OR (
                        close_reason = ''NATURAL_RETIREMENT''
                        AND (
                            issuing_kid IS NULL
                            OR issuing_kid = close_target_kid
                        )
                   ) THEN
                    RAISE EXCEPTION USING
                        ERRCODE = ''55000'',
                        MESSAGE = ''capability admission resume fold differs'';
                END IF;
                admission_state := ''OPEN'';
                unresolved_incident_id := NULL;
                close_act_id := NULL;
                close_receipt_id := NULL;
                close_reason := NULL;
                close_target_kid := NULL;
                close_target_candidate_digest := NULL;
                close_target_revoked := false;
            ELSE
                RAISE EXCEPTION USING
                    ERRCODE = ''55000'',
                    MESSAGE = ''capability key lifecycle act kind differs'';
            END IF;

            expected_sequence := act_row.stream_sequence;
            expected_prior_id := act_row.act_id;
            expected_prior_digest := act_row.act_digest::pg_catalog.text;
            head_sequence := act_row.stream_sequence;
            head_id := act_row.act_id;
            head_digest := act_row.act_digest::pg_catalog.text;
        END LOOP;
        RETURN NEXT;
    END';

CREATE FUNCTION ofarm.verify_tenant_capability_preflight(
    public_key pg_catalog.bytea,
    signature pg_catalog.bytea
)
RETURNS pg_catalog.bool
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN
        RETURN ofarm_crypto.ed25519_verify(
            public_key,
            pg_catalog.decode(
                ''004f4641524d322d54454e414e542d4341504142494c4954592d4b4d532d505245464c494748542d563100'',
                ''hex''
            ),
            signature
        );
    END';

CREATE FUNCTION ofarm.register_tenant_capability_key(
    requested_public_key pg_catalog.bytea,
    requested_kms_key_version_resource pg_catalog.text,
    requested_kms_attestation_digest pg_catalog.text
)
RETURNS TABLE (
    candidate_id pg_catalog.uuid,
    kid pg_catalog.text,
    candidate_digest pg_catalog.text
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        generated_candidate_id pg_catalog.uuid;
        generated_kid pg_catalog.text;
        generated_public_key_digest pg_catalog.text;
        generated_candidate_digest pg_catalog.text;
        observed_registered_at pg_catalog.timestamptz;
        protected_audience pg_catalog.text;
        keyring ofarm.tenant_capability_keyring%ROWTYPE;
        authority pg_catalog.record;
    BEGIN
        IF pg_catalog.current_setting(''transaction_isolation'') <>
                ''read committed'' THEN
            RAISE EXCEPTION USING ERRCODE = ''25001'',
                MESSAGE = ''key registration requires READ COMMITTED'';
        END IF;
        IF SESSION_USER <> ''ofarm_capability_key_control_login'' THEN
            RAISE EXCEPTION USING ERRCODE = ''42501'',
                MESSAGE = ''key controller identity differs'';
        END IF;
        PERFORM pg_catalog.pg_advisory_xact_lock(1330004306, 1413694001);
        SELECT instance.audience INTO STRICT protected_audience
          FROM ofarm.tenant_binder_instance AS instance
         WHERE instance.singleton;
        SELECT ring.* INTO STRICT keyring
          FROM ofarm.tenant_capability_keyring AS ring
         FOR UPDATE;
        SELECT * INTO STRICT authority
          FROM ofarm.fold_tenant_capability_key_lifecycle(NULL);
        IF keyring.audience IS DISTINCT FROM protected_audience
           OR keyring.projected_head_sequence IS DISTINCT FROM authority.head_sequence
           OR keyring.projected_head_id IS DISTINCT FROM authority.head_id
           OR keyring.projected_head_digest::pg_catalog.text
                IS DISTINCT FROM authority.head_digest
           OR keyring.projected_admission_state IS DISTINCT FROM
                authority.admission_state
           OR keyring.projected_issuing_kid IS DISTINCT FROM authority.issuing_kid
           OR keyring.projected_issuing_candidate_digest::pg_catalog.text
                IS DISTINCT FROM authority.issuing_candidate_digest
           OR keyring.unresolved_incident_id IS DISTINCT FROM
                authority.unresolved_incident_id
           OR keyring.close_act_id IS DISTINCT FROM authority.close_act_id
           OR keyring.close_receipt_id IS DISTINCT FROM authority.close_receipt_id THEN
            RAISE EXCEPTION USING ERRCODE = ''55000'',
                MESSAGE = ''capability keyring projection differs'';
        END IF;
        IF requested_public_key IS NULL
           OR requested_kms_key_version_resource IS NULL
           OR requested_kms_attestation_digest IS NULL
           OR pg_catalog.octet_length(requested_public_key) <> 32
           OR requested_kms_key_version_resource OPERATOR(pg_catalog.!~)
                ''^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/locations/[a-z0-9]([a-z0-9-]*[a-z0-9])?/keyRings/[A-Za-z0-9_-]{1,63}/cryptoKeys/[A-Za-z0-9_-]{1,63}/cryptoKeyVersions/[1-9][0-9]*$''
           OR requested_kms_attestation_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$'' THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''candidate registration arguments differ'';
        END IF;
        generated_candidate_id := pg_catalog.gen_random_uuid();
        generated_kid := ofarm.tenant_capability_key_id(requested_public_key);
        generated_public_key_digest := ''sha256:'' || pg_catalog.encode(
            pg_catalog.sha256(requested_public_key), ''hex''
        );
        observed_registered_at := pg_catalog.clock_timestamp();
        generated_candidate_digest :=
            ofarm.compute_tenant_capability_candidate_digest(
                generated_candidate_id,
                generated_kid,
                requested_public_key,
                generated_public_key_digest,
                ''Ed25519'',
                protected_audience,
                requested_kms_key_version_resource,
                ''ASYMMETRIC_SIGN'',
                ''EC_SIGN_ED25519'',
                ''HSM'',
                requested_kms_attestation_digest,
                observed_registered_at,
                SESSION_USER::pg_catalog.text
            );
        INSERT INTO ofarm.tenant_capability_verification_key (
            candidate_id,
            kid,
            public_key,
            public_key_digest,
            algorithm,
            audience,
            kms_key_version_resource,
            kms_purpose,
            kms_algorithm,
            kms_protection_level,
            kms_attestation_digest,
            registered_at,
            accountable_control_ref,
            candidate_digest
        ) VALUES (
            generated_candidate_id,
            generated_kid,
            requested_public_key,
            generated_public_key_digest,
            ''Ed25519'',
            protected_audience,
            requested_kms_key_version_resource,
            ''ASYMMETRIC_SIGN'',
            ''EC_SIGN_ED25519'',
            ''HSM'',
            requested_kms_attestation_digest::ofarm.sha256_id,
            observed_registered_at,
            SESSION_USER::pg_catalog.text::ofarm.ascii_id,
            generated_candidate_digest::ofarm.sha256_id
        );
        RETURN QUERY SELECT generated_candidate_id,
                            generated_kid,
                            generated_candidate_digest;
    END';

CREATE FUNCTION ofarm.verify_tenant_capability_candidate_preflight(
    requested_kid pg_catalog.text,
    requested_signature pg_catalog.bytea
)
RETURNS pg_catalog.bool
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        candidate ofarm.tenant_capability_verification_key%ROWTYPE;
        keyring ofarm.tenant_capability_keyring%ROWTYPE;
    BEGIN
        IF pg_catalog.current_setting(''transaction_isolation'') <>
                ''read committed'' THEN
            RAISE EXCEPTION USING ERRCODE = ''25001'',
                MESSAGE = ''candidate preflight requires READ COMMITTED'';
        END IF;
        IF SESSION_USER <> ''ofarm_capability_key_control_login'' THEN
            RAISE EXCEPTION USING ERRCODE = ''42501'',
                MESSAGE = ''key controller identity differs'';
        END IF;
        IF requested_kid IS NULL OR requested_signature IS NULL
           OR pg_catalog.octet_length(requested_kid) <> 43
           OR requested_kid OPERATOR(pg_catalog.!~) ''^[A-Za-z0-9_-]{43}$''
           OR pg_catalog.octet_length(requested_signature) <> 64 THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''candidate preflight arguments differ'';
        END IF;
        PERFORM pg_catalog.pg_advisory_xact_lock(1330004306, 1413694001);
        SELECT ring.* INTO STRICT keyring
          FROM ofarm.tenant_capability_keyring AS ring
         FOR UPDATE;
        SELECT key.* INTO candidate
          FROM ofarm.tenant_capability_verification_key AS key
         WHERE key.kid = requested_kid
         FOR UPDATE;
        IF NOT FOUND
           OR candidate.audience IS DISTINCT FROM keyring.audience
           OR EXISTS (
                SELECT 1
                  FROM ofarm.tenant_capability_key_lifecycle AS act
                 WHERE act.old_kid = requested_kid
                    OR act.new_kid = requested_kid
           ) THEN
            RAISE EXCEPTION USING ERRCODE = ''28000'',
                MESSAGE = ''inactive candidate preflight refuses'';
        END IF;
        RETURN ofarm.verify_tenant_capability_preflight(
            candidate.public_key,
            requested_signature
        ) IS NOT DISTINCT FROM true;
    END';

CREATE FUNCTION ofarm.activate_tenant_capability_key(
    requested_kid pg_catalog.text,
    expected_head_id pg_catalog.uuid,
    expected_head_digest pg_catalog.text,
    requested_preflight_receipt_digest pg_catalog.text,
    requested_kms_evidence_digest pg_catalog.text,
    requested_iam_evidence_digest pg_catalog.text,
    requested_reason pg_catalog.text
)
RETURNS TABLE (
    act_id pg_catalog.uuid,
    act_digest pg_catalog.text,
    decided_at_us pg_catalog.int8
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        candidate ofarm.tenant_capability_verification_key%ROWTYPE;
        keyring ofarm.tenant_capability_keyring%ROWTYPE;
        authority pg_catalog.record;
        generated_act_id pg_catalog.uuid;
        generated_act_digest pg_catalog.text;
        observed_now_us pg_catalog.int8;
        next_sequence pg_catalog.int8;
        next_issuance_end_us pg_catalog.int8;
        next_admission_state pg_catalog.text;
        changed_rows pg_catalog.int4;
    BEGIN
        IF pg_catalog.current_setting(''transaction_isolation'') <>
                ''read committed'' THEN
            RAISE EXCEPTION USING ERRCODE = ''25001'',
                MESSAGE = ''key activation requires READ COMMITTED'';
        END IF;
        IF SESSION_USER <> ''ofarm_capability_key_control_login'' THEN
            RAISE EXCEPTION USING ERRCODE = ''42501'',
                MESSAGE = ''key controller identity differs'';
        END IF;
        IF requested_kid IS NULL
           OR pg_catalog.octet_length(requested_kid) <> 43
           OR requested_kid OPERATOR(pg_catalog.!~) ''^[A-Za-z0-9_-]{43}$''
           OR (expected_head_id IS NULL) <> (expected_head_digest IS NULL)
           OR (
                expected_head_digest IS NOT NULL
                AND expected_head_digest OPERATOR(pg_catalog.!~)
                    ''^sha256:[0-9a-f]{64}$''
           )
           OR requested_preflight_receipt_digest IS NULL
           OR requested_kms_evidence_digest IS NULL
           OR requested_iam_evidence_digest IS NULL
           OR requested_reason IS NULL
           OR requested_preflight_receipt_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_kms_evidence_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_iam_evidence_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$'' THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''key activation arguments differ'';
        END IF;
        PERFORM pg_catalog.pg_advisory_xact_lock(1330004306, 1413694001);
        SELECT ring.* INTO STRICT keyring
          FROM ofarm.tenant_capability_keyring AS ring
         FOR UPDATE;
        SELECT key.* INTO STRICT candidate
          FROM ofarm.tenant_capability_verification_key AS key
         WHERE key.kid = requested_kid
         FOR UPDATE;
        SELECT * INTO STRICT authority
          FROM ofarm.fold_tenant_capability_key_lifecycle(requested_kid);
        IF keyring.audience IS DISTINCT FROM candidate.audience
           OR keyring.projected_head_sequence IS DISTINCT FROM authority.head_sequence
           OR keyring.projected_head_id IS DISTINCT FROM authority.head_id
           OR keyring.projected_head_digest::pg_catalog.text
                IS DISTINCT FROM authority.head_digest
           OR keyring.projected_admission_state IS DISTINCT FROM
                authority.admission_state
           OR keyring.projected_issuing_kid IS DISTINCT FROM authority.issuing_kid
           OR keyring.projected_issuing_candidate_digest::pg_catalog.text
                IS DISTINCT FROM authority.issuing_candidate_digest
           OR keyring.unresolved_incident_id IS DISTINCT FROM
                authority.unresolved_incident_id
           OR keyring.close_act_id IS DISTINCT FROM authority.close_act_id
           OR keyring.close_receipt_id IS DISTINCT FROM authority.close_receipt_id THEN
            RAISE EXCEPTION USING ERRCODE = ''55000'',
                MESSAGE = ''capability keyring projection differs'';
        END IF;
        IF authority.head_id IS DISTINCT FROM expected_head_id
           OR authority.head_digest IS DISTINCT FROM expected_head_digest
           OR authority.admission_state <> ''CLOSED''
           OR authority.selected_ever_activated
           OR requested_reason IS DISTINCT FROM (CASE
                WHEN authority.head_id IS NULL THEN ''INITIAL_ACTIVATION''
                WHEN authority.close_reason = ''COMPROMISE''
                    THEN ''COMPROMISE_REPLACEMENT''
                WHEN authority.close_reason = ''NATURAL_RETIREMENT''
                    THEN ''NATURAL_RETIREMENT_REPLACEMENT''
                ELSE NULL
              END) THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''key activation precondition failed'';
        END IF;
        observed_now_us := (
            extract(epoch FROM pg_catalog.clock_timestamp()) * 1000000
        )::pg_catalog.int8;
        IF observed_now_us > 9223372036854775807 - 7776065000000
           OR (
                authority.head_id IS NOT NULL
                AND authority.issuing_verification_end_us IS NOT NULL
                AND observed_now_us < authority.issuing_verification_end_us
           ) THEN
            RAISE EXCEPTION USING ERRCODE = ''22003'',
                MESSAGE = ''key activation time precondition failed'';
        END IF;
        generated_act_id := pg_catalog.gen_random_uuid();
        next_sequence := COALESCE(authority.head_sequence, 0) + 1;
        next_issuance_end_us := observed_now_us + 7776000000000;
        generated_act_digest := ofarm.compute_tenant_capability_key_act_digest(
            next_sequence,
            generated_act_id,
            authority.head_id,
            authority.head_digest,
            ''ACTIVATE'',
            NULL,
            NULL,
            candidate.kid,
            candidate.candidate_digest::pg_catalog.text,
            candidate.audience,
            ''Ed25519'',
            observed_now_us,
            observed_now_us,
            next_issuance_end_us,
            NULL,
            NULL,
            NULL,
            requested_preflight_receipt_digest,
            requested_kms_evidence_digest,
            requested_iam_evidence_digest,
            SESSION_USER::pg_catalog.text,
            requested_reason
        );
        INSERT INTO ofarm.tenant_capability_key_lifecycle (
            stream_sequence, act_id, act_digest, prior_act_id, prior_act_digest,
            act_kind, new_kid, new_candidate_digest, audience, algorithm,
            decided_at_us, effective_at_us, new_issuance_end_us,
            preflight_receipt_digest, kms_evidence_digest, iam_evidence_digest,
            accountable_control_ref, reason
        ) VALUES (
            next_sequence, generated_act_id, generated_act_digest,
            authority.head_id, authority.head_digest, ''ACTIVATE'',
            candidate.kid, candidate.candidate_digest, candidate.audience,
            ''Ed25519'', observed_now_us, observed_now_us,
            next_issuance_end_us,
            requested_preflight_receipt_digest::ofarm.sha256_id,
            requested_kms_evidence_digest::ofarm.sha256_id,
            requested_iam_evidence_digest::ofarm.sha256_id,
            SESSION_USER::pg_catalog.text::ofarm.ascii_id,
            requested_reason::ofarm.ascii_id
        );
        next_admission_state := CASE WHEN authority.head_id IS NULL
            THEN ''OPEN'' ELSE ''CLOSED'' END;
        UPDATE ofarm.tenant_capability_keyring AS ring SET
            projected_head_sequence = next_sequence,
            projected_head_id = generated_act_id,
            projected_head_digest = generated_act_digest,
            projected_admission_state = next_admission_state,
            projected_issuing_kid = candidate.kid,
            projected_issuing_candidate_digest = candidate.candidate_digest,
            rebuilt_at = pg_catalog.clock_timestamp()
         WHERE ring.audience = candidate.audience
           AND ring.projected_head_id IS NOT DISTINCT FROM expected_head_id
           AND ring.projected_head_digest::pg_catalog.text
                IS NOT DISTINCT FROM expected_head_digest;
        GET DIAGNOSTICS changed_rows = ROW_COUNT;
        IF changed_rows <> 1 THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''key activation projection race refused'';
        END IF;
        PERFORM *
          FROM ofarm.fold_tenant_capability_key_lifecycle(requested_kid);
        RETURN QUERY SELECT generated_act_id,
                            generated_act_digest,
                            observed_now_us;
    END';

CREATE FUNCTION ofarm.rotate_tenant_capability_key(
    requested_old_kid pg_catalog.text,
    requested_new_kid pg_catalog.text,
    expected_head_id pg_catalog.uuid,
    expected_head_digest pg_catalog.text,
    requested_preflight_receipt_digest pg_catalog.text,
    requested_kms_evidence_digest pg_catalog.text,
    requested_iam_evidence_digest pg_catalog.text,
    requested_reason pg_catalog.text
)
RETURNS TABLE (
    act_id pg_catalog.uuid,
    act_digest pg_catalog.text,
    decided_at_us pg_catalog.int8,
    old_verification_end_us pg_catalog.int8
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        old_candidate ofarm.tenant_capability_verification_key%ROWTYPE;
        new_candidate ofarm.tenant_capability_verification_key%ROWTYPE;
        keyring ofarm.tenant_capability_keyring%ROWTYPE;
        authority pg_catalog.record;
        generated_act_id pg_catalog.uuid;
        generated_act_digest pg_catalog.text;
        observed_now_us pg_catalog.int8;
        next_sequence pg_catalog.int8;
        next_issuance_end_us pg_catalog.int8;
        old_tail_end_us pg_catalog.int8;
        changed_rows pg_catalog.int4;
    BEGIN
        IF pg_catalog.current_setting(''transaction_isolation'') <>
                ''read committed'' THEN
            RAISE EXCEPTION USING ERRCODE = ''25001'',
                MESSAGE = ''key rotation requires READ COMMITTED'';
        END IF;
        IF SESSION_USER <> ''ofarm_capability_key_control_login'' THEN
            RAISE EXCEPTION USING ERRCODE = ''42501'',
                MESSAGE = ''key controller identity differs'';
        END IF;
        IF requested_old_kid IS NULL OR requested_new_kid IS NULL
           OR pg_catalog.octet_length(requested_old_kid) <> 43
           OR pg_catalog.octet_length(requested_new_kid) <> 43
           OR requested_old_kid OPERATOR(pg_catalog.!~) ''^[A-Za-z0-9_-]{43}$''
           OR requested_new_kid OPERATOR(pg_catalog.!~) ''^[A-Za-z0-9_-]{43}$''
           OR expected_head_id IS NULL OR expected_head_digest IS NULL
           OR expected_head_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_preflight_receipt_digest IS NULL
           OR requested_kms_evidence_digest IS NULL
           OR requested_iam_evidence_digest IS NULL
           OR requested_reason IS NULL
           OR requested_preflight_receipt_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_kms_evidence_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_iam_evidence_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_old_kid = requested_new_kid
           OR requested_reason <> ''GRACEFUL_ROTATION'' THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''key rotation arguments differ'';
        END IF;
        PERFORM pg_catalog.pg_advisory_xact_lock(1330004306, 1413694001);
        SELECT ring.* INTO STRICT keyring
          FROM ofarm.tenant_capability_keyring AS ring
         FOR UPDATE;
        PERFORM 1
          FROM ofarm.tenant_capability_verification_key AS key
         WHERE key.kid IN (requested_old_kid, requested_new_kid)
         ORDER BY key.kid COLLATE pg_catalog."C"
         FOR UPDATE;
        SELECT key.* INTO STRICT old_candidate
          FROM ofarm.tenant_capability_verification_key AS key
         WHERE key.kid = requested_old_kid;
        SELECT key.* INTO STRICT new_candidate
          FROM ofarm.tenant_capability_verification_key AS key
         WHERE key.kid = requested_new_kid;
        SELECT * INTO STRICT authority
          FROM ofarm.fold_tenant_capability_key_lifecycle(requested_new_kid);
        IF keyring.audience IS DISTINCT FROM new_candidate.audience
           OR keyring.projected_head_sequence IS DISTINCT FROM authority.head_sequence
           OR keyring.projected_head_id IS DISTINCT FROM authority.head_id
           OR keyring.projected_head_digest::pg_catalog.text
                IS DISTINCT FROM authority.head_digest
           OR keyring.projected_admission_state IS DISTINCT FROM
                authority.admission_state
           OR keyring.projected_issuing_kid IS DISTINCT FROM authority.issuing_kid
           OR keyring.projected_issuing_candidate_digest::pg_catalog.text
                IS DISTINCT FROM authority.issuing_candidate_digest
           OR keyring.unresolved_incident_id IS DISTINCT FROM
                authority.unresolved_incident_id
           OR keyring.close_act_id IS DISTINCT FROM authority.close_act_id
           OR keyring.close_receipt_id IS DISTINCT FROM authority.close_receipt_id
           OR authority.head_id IS DISTINCT FROM expected_head_id
           OR authority.head_digest IS DISTINCT FROM expected_head_digest
           OR authority.admission_state <> ''OPEN''
           OR authority.issuing_kid IS DISTINCT FROM old_candidate.kid
           OR authority.issuing_candidate_digest IS DISTINCT FROM
                old_candidate.candidate_digest::pg_catalog.text
           OR authority.selected_ever_activated
           OR old_candidate.audience <> new_candidate.audience THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''key rotation precondition failed'';
        END IF;
        observed_now_us := (
            extract(epoch FROM pg_catalog.clock_timestamp()) * 1000000
        )::pg_catalog.int8;
        IF observed_now_us >= authority.issuing_retirement_us
           OR observed_now_us > 9223372036854775807 - 7776065000000 THEN
            RAISE EXCEPTION USING ERRCODE = ''22003'',
                MESSAGE = ''key rotation time precondition failed'';
        END IF;
        next_sequence := authority.head_sequence + 1;
        next_issuance_end_us := observed_now_us + 7776000000000;
        old_tail_end_us := observed_now_us + 65000000;
        generated_act_id := pg_catalog.gen_random_uuid();
        generated_act_digest := ofarm.compute_tenant_capability_key_act_digest(
            next_sequence, generated_act_id, authority.head_id,
            authority.head_digest, ''ROTATE'', old_candidate.kid,
            old_candidate.candidate_digest::pg_catalog.text,
            new_candidate.kid,
            new_candidate.candidate_digest::pg_catalog.text,
            new_candidate.audience, ''Ed25519'',
            observed_now_us, observed_now_us,
            next_issuance_end_us, old_tail_end_us, NULL, NULL,
            requested_preflight_receipt_digest,
            requested_kms_evidence_digest, requested_iam_evidence_digest,
            SESSION_USER::pg_catalog.text, requested_reason
        );
        INSERT INTO ofarm.tenant_capability_key_lifecycle (
            stream_sequence, act_id, act_digest, prior_act_id, prior_act_digest,
            act_kind, old_kid, old_candidate_digest, new_kid,
            new_candidate_digest, audience, algorithm, decided_at_us,
            effective_at_us, new_issuance_end_us, old_verification_end_us,
            preflight_receipt_digest, kms_evidence_digest, iam_evidence_digest,
            accountable_control_ref, reason
        ) VALUES (
            next_sequence, generated_act_id, generated_act_digest,
            authority.head_id, authority.head_digest, ''ROTATE'',
            old_candidate.kid, old_candidate.candidate_digest,
            new_candidate.kid, new_candidate.candidate_digest,
            new_candidate.audience, ''Ed25519'', observed_now_us,
            observed_now_us, next_issuance_end_us, old_tail_end_us,
            requested_preflight_receipt_digest::ofarm.sha256_id,
            requested_kms_evidence_digest::ofarm.sha256_id,
            requested_iam_evidence_digest::ofarm.sha256_id,
            SESSION_USER::pg_catalog.text::ofarm.ascii_id,
            requested_reason::ofarm.ascii_id
        );
        UPDATE ofarm.tenant_capability_keyring AS ring SET
            projected_head_sequence = next_sequence,
            projected_head_id = generated_act_id,
            projected_head_digest = generated_act_digest,
            projected_issuing_kid = new_candidate.kid,
            projected_issuing_candidate_digest = new_candidate.candidate_digest,
            rebuilt_at = pg_catalog.clock_timestamp()
         WHERE ring.audience = new_candidate.audience
           AND ring.projected_head_id = expected_head_id
           AND ring.projected_head_digest::pg_catalog.text = expected_head_digest;
        GET DIAGNOSTICS changed_rows = ROW_COUNT;
        IF changed_rows <> 1 THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''key rotation projection race refused'';
        END IF;
        PERFORM *
          FROM ofarm.fold_tenant_capability_key_lifecycle(requested_new_kid);
        RETURN QUERY SELECT generated_act_id, generated_act_digest,
                            observed_now_us, old_tail_end_us;
    END';

CREATE FUNCTION ofarm.close_tenant_capability_admission(
    expected_head_id pg_catalog.uuid,
    expected_head_digest pg_catalog.text,
    affected_key pg_catalog.text,
    requested_kms_evidence_digest pg_catalog.text,
    requested_iam_evidence_digest pg_catalog.text,
    requested_reason pg_catalog.text
)
RETURNS TABLE (
    act_id pg_catalog.uuid,
    act_digest pg_catalog.text,
    incident_id pg_catalog.uuid,
    close_receipt_id pg_catalog.uuid,
    decided_at_us pg_catalog.int8
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        candidate ofarm.tenant_capability_verification_key%ROWTYPE;
        keyring ofarm.tenant_capability_keyring%ROWTYPE;
        authority pg_catalog.record;
        generated_act_id pg_catalog.uuid;
        generated_act_digest pg_catalog.text;
        generated_incident_id pg_catalog.uuid;
        generated_close_receipt_id pg_catalog.uuid;
        observed_now_us pg_catalog.int8;
        next_sequence pg_catalog.int8;
        changed_rows pg_catalog.int4;
    BEGIN
        IF pg_catalog.current_setting(''transaction_isolation'') <>
                ''read committed'' THEN
            RAISE EXCEPTION USING ERRCODE = ''25001'',
                MESSAGE = ''admission close requires READ COMMITTED'';
        END IF;
        IF SESSION_USER <> ''ofarm_capability_key_control_login'' THEN
            RAISE EXCEPTION USING ERRCODE = ''42501'',
                MESSAGE = ''key controller identity differs'';
        END IF;
        IF expected_head_id IS NULL OR expected_head_digest IS NULL
           OR expected_head_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR affected_key IS NULL
           OR pg_catalog.octet_length(affected_key) <> 43
           OR affected_key OPERATOR(pg_catalog.!~) ''^[A-Za-z0-9_-]{43}$''
           OR requested_kms_evidence_digest IS NULL
           OR requested_iam_evidence_digest IS NULL
           OR requested_reason IS NULL
           OR requested_kms_evidence_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_iam_evidence_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_reason NOT IN (
                ''COMPROMISE'', ''ROTATION_HANDOFF'', ''NATURAL_RETIREMENT''
           ) THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''admission close arguments differ'';
        END IF;
        SELECT * INTO STRICT authority
          FROM ofarm.fold_tenant_capability_key_lifecycle(affected_key);
        SELECT key.* INTO STRICT candidate
          FROM ofarm.tenant_capability_verification_key AS key
         WHERE key.kid = affected_key;
        SELECT ring.* INTO STRICT keyring
          FROM ofarm.tenant_capability_keyring AS ring
         WHERE ring.audience = candidate.audience;
        IF keyring.audience IS DISTINCT FROM candidate.audience
           OR keyring.projected_head_id IS DISTINCT FROM authority.head_id
           OR keyring.projected_head_digest::pg_catalog.text
                IS DISTINCT FROM authority.head_digest
           OR keyring.projected_admission_state IS DISTINCT FROM
                authority.admission_state
           OR authority.head_id IS DISTINCT FROM expected_head_id
           OR authority.head_digest IS DISTINCT FROM expected_head_digest
           OR authority.admission_state <> ''OPEN'' THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''admission close precondition failed'';
        END IF;
        observed_now_us := (
            extract(epoch FROM pg_catalog.clock_timestamp()) * 1000000
        )::pg_catalog.int8;
        IF requested_reason = ''COMPROMISE''
           AND (
                NOT authority.selected_ever_activated
                OR authority.selected_revoked
                OR authority.selected_candidate_digest IS DISTINCT FROM
                    candidate.candidate_digest::pg_catalog.text
                OR observed_now_us >= authority.selected_verification_end_us
           ) THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''compromise close target is not key-eligible'';
        END IF;
        generated_act_id := pg_catalog.gen_random_uuid();
        generated_incident_id := pg_catalog.gen_random_uuid();
        generated_close_receipt_id := pg_catalog.gen_random_uuid();
        next_sequence := authority.head_sequence + 1;
        generated_act_digest := ofarm.compute_tenant_capability_key_act_digest(
            next_sequence, generated_act_id, authority.head_id,
            authority.head_digest, ''CLOSE_ADMISSION'', candidate.kid,
            candidate.candidate_digest::pg_catalog.text, NULL, NULL,
            candidate.audience, ''Ed25519'',
            observed_now_us, observed_now_us,
            NULL, NULL, generated_incident_id, generated_close_receipt_id,
            NULL, requested_kms_evidence_digest, requested_iam_evidence_digest,
            SESSION_USER::pg_catalog.text, requested_reason
        );
        INSERT INTO ofarm.tenant_capability_key_lifecycle (
            stream_sequence, act_id, act_digest, prior_act_id, prior_act_digest,
            act_kind, old_kid, old_candidate_digest, audience, algorithm,
            decided_at_us, effective_at_us, incident_id, close_receipt_id,
            kms_evidence_digest, iam_evidence_digest, accountable_control_ref,
            reason
        ) VALUES (
            next_sequence, generated_act_id, generated_act_digest,
            authority.head_id, authority.head_digest, ''CLOSE_ADMISSION'',
            candidate.kid, candidate.candidate_digest, candidate.audience,
            ''Ed25519'', observed_now_us, observed_now_us,
            generated_incident_id, generated_close_receipt_id,
            requested_kms_evidence_digest::ofarm.sha256_id,
            requested_iam_evidence_digest::ofarm.sha256_id,
            SESSION_USER::pg_catalog.text::ofarm.ascii_id,
            requested_reason::ofarm.ascii_id
        );
        PERFORM *
          FROM ofarm.fold_tenant_capability_key_lifecycle(affected_key);
        UPDATE ofarm.tenant_capability_keyring AS ring SET
            projected_head_sequence = next_sequence,
            projected_head_id = generated_act_id,
            projected_head_digest = generated_act_digest,
            projected_admission_state = ''CLOSED'',
            unresolved_incident_id = generated_incident_id,
            close_act_id = generated_act_id,
            close_receipt_id = generated_close_receipt_id,
            rebuilt_at = pg_catalog.clock_timestamp()
         WHERE ring.audience = candidate.audience
           AND ring.projected_head_id = expected_head_id
           AND ring.projected_head_digest::pg_catalog.text = expected_head_digest
           AND ring.projected_admission_state = ''OPEN'';
        GET DIAGNOSTICS changed_rows = ROW_COUNT;
        IF changed_rows <> 1 THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''admission close projection race refused'';
        END IF;
        RETURN QUERY SELECT generated_act_id, generated_act_digest,
                            generated_incident_id, generated_close_receipt_id,
                            observed_now_us;
    END';

CREATE FUNCTION ofarm.revoke_tenant_capability_key(
    requested_kid pg_catalog.text,
    expected_head_id pg_catalog.uuid,
    expected_head_digest pg_catalog.text,
    requested_incident_id pg_catalog.uuid,
    requested_close_receipt_id pg_catalog.uuid,
    requested_kms_evidence_digest pg_catalog.text,
    requested_iam_evidence_digest pg_catalog.text,
    requested_reason pg_catalog.text
)
RETURNS TABLE (
    act_id pg_catalog.uuid,
    act_digest pg_catalog.text,
    decided_at_us pg_catalog.int8
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        candidate ofarm.tenant_capability_verification_key%ROWTYPE;
        keyring ofarm.tenant_capability_keyring%ROWTYPE;
        authority pg_catalog.record;
        generated_act_id pg_catalog.uuid;
        generated_act_digest pg_catalog.text;
        observed_now_us pg_catalog.int8;
        next_sequence pg_catalog.int8;
        changed_rows pg_catalog.int4;
    BEGIN
        IF pg_catalog.current_setting(''transaction_isolation'') <>
                ''read committed'' THEN
            RAISE EXCEPTION USING ERRCODE = ''25001'',
                MESSAGE = ''key revocation requires READ COMMITTED'';
        END IF;
        IF SESSION_USER <> ''ofarm_capability_key_control_login'' THEN
            RAISE EXCEPTION USING ERRCODE = ''42501'',
                MESSAGE = ''key controller identity differs'';
        END IF;
        IF requested_kid IS NULL
           OR pg_catalog.octet_length(requested_kid) <> 43
           OR requested_kid OPERATOR(pg_catalog.!~) ''^[A-Za-z0-9_-]{43}$''
           OR expected_head_id IS NULL
           OR expected_head_id =
                ''00000000-0000-0000-0000-000000000000''::pg_catalog.uuid
           OR expected_head_digest IS NULL
           OR expected_head_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_incident_id IS NULL
           OR requested_incident_id =
                ''00000000-0000-0000-0000-000000000000''::pg_catalog.uuid
           OR requested_close_receipt_id IS NULL
           OR requested_close_receipt_id =
                ''00000000-0000-0000-0000-000000000000''::pg_catalog.uuid
           OR requested_kms_evidence_digest IS NULL
           OR requested_kms_evidence_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_iam_evidence_digest IS NULL
           OR requested_iam_evidence_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_reason IS NULL THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''key revocation arguments differ'';
        END IF;
        PERFORM pg_catalog.pg_advisory_xact_lock(1330004306, 1413694001);
        SELECT ring.* INTO STRICT keyring
          FROM ofarm.tenant_capability_keyring AS ring
         FOR UPDATE;
        SELECT key.* INTO STRICT candidate
          FROM ofarm.tenant_capability_verification_key AS key
         WHERE key.kid = requested_kid
         FOR UPDATE;
        SELECT * INTO STRICT authority
          FROM ofarm.fold_tenant_capability_key_lifecycle(requested_kid);
        IF keyring.audience IS DISTINCT FROM candidate.audience
           OR keyring.projected_head_sequence IS DISTINCT FROM authority.head_sequence
           OR keyring.projected_head_id IS DISTINCT FROM authority.head_id
           OR keyring.projected_head_digest::pg_catalog.text
                IS DISTINCT FROM authority.head_digest
           OR keyring.projected_admission_state IS DISTINCT FROM
                authority.admission_state
           OR keyring.projected_issuing_kid IS DISTINCT FROM authority.issuing_kid
           OR keyring.projected_issuing_candidate_digest::pg_catalog.text
                IS DISTINCT FROM authority.issuing_candidate_digest
           OR keyring.unresolved_incident_id IS DISTINCT FROM
                authority.unresolved_incident_id
           OR keyring.close_act_id IS DISTINCT FROM authority.close_act_id
           OR keyring.close_receipt_id IS DISTINCT FROM authority.close_receipt_id
           OR authority.head_id IS DISTINCT FROM expected_head_id
           OR authority.head_digest IS DISTINCT FROM expected_head_digest
           OR authority.admission_state <> ''CLOSED''
           OR authority.unresolved_incident_id IS DISTINCT FROM
                requested_incident_id
           OR authority.close_receipt_id IS DISTINCT FROM
                requested_close_receipt_id
           OR authority.selected_revoked
           OR authority.close_target_kid IS DISTINCT FROM candidate.kid
           OR authority.close_target_candidate_digest IS DISTINCT FROM
                candidate.candidate_digest::pg_catalog.text
           OR authority.close_target_revoked
           OR requested_reason IS DISTINCT FROM authority.close_reason
           OR keyring.projected_head_id IS DISTINCT FROM authority.head_id
           OR keyring.projected_head_digest::pg_catalog.text
                IS DISTINCT FROM authority.head_digest THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''key revocation precondition failed'';
        END IF;
        observed_now_us := (
            extract(epoch FROM pg_catalog.clock_timestamp()) * 1000000
        )::pg_catalog.int8;
        IF authority.selected_verification_end_us IS NULL
           OR (
                observed_now_us >= authority.selected_verification_end_us
                AND authority.close_reason IS DISTINCT FROM
                    ''ROTATION_HANDOFF''
           ) THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''key revocation target is not eligible'';
        END IF;
        next_sequence := authority.head_sequence + 1;
        generated_act_id := pg_catalog.gen_random_uuid();
        generated_act_digest := ofarm.compute_tenant_capability_key_act_digest(
            next_sequence, generated_act_id, authority.head_id,
            authority.head_digest, ''REVOKE'', candidate.kid,
            candidate.candidate_digest::pg_catalog.text, NULL, NULL,
            candidate.audience, ''Ed25519'',
            observed_now_us, observed_now_us,
            NULL, NULL, requested_incident_id, requested_close_receipt_id,
            NULL, requested_kms_evidence_digest, requested_iam_evidence_digest,
            SESSION_USER::pg_catalog.text, requested_reason
        );
        INSERT INTO ofarm.tenant_capability_key_lifecycle (
            stream_sequence, act_id, act_digest, prior_act_id, prior_act_digest,
            act_kind, old_kid, old_candidate_digest, audience, algorithm,
            decided_at_us, effective_at_us, incident_id, close_receipt_id,
            kms_evidence_digest, iam_evidence_digest, accountable_control_ref,
            reason
        ) VALUES (
            next_sequence, generated_act_id, generated_act_digest,
            authority.head_id, authority.head_digest, ''REVOKE'',
            candidate.kid, candidate.candidate_digest, candidate.audience,
            ''Ed25519'', observed_now_us, observed_now_us,
            requested_incident_id, requested_close_receipt_id,
            requested_kms_evidence_digest::ofarm.sha256_id,
            requested_iam_evidence_digest::ofarm.sha256_id,
            SESSION_USER::pg_catalog.text::ofarm.ascii_id,
            requested_reason::ofarm.ascii_id
        );
        PERFORM *
          FROM ofarm.fold_tenant_capability_key_lifecycle(requested_kid);
        UPDATE ofarm.tenant_capability_keyring AS ring SET
            projected_head_sequence = next_sequence,
            projected_head_id = generated_act_id,
            projected_head_digest = generated_act_digest,
            projected_issuing_kid = CASE
                WHEN ring.projected_issuing_kid = candidate.kid THEN NULL
                ELSE ring.projected_issuing_kid END,
            projected_issuing_candidate_digest = CASE
                WHEN ring.projected_issuing_kid = candidate.kid THEN NULL
                ELSE ring.projected_issuing_candidate_digest END,
            rebuilt_at = pg_catalog.clock_timestamp()
         WHERE ring.audience = candidate.audience
           AND ring.projected_head_id = expected_head_id
           AND ring.projected_head_digest::pg_catalog.text = expected_head_digest
           AND ring.projected_admission_state = ''CLOSED'';
        GET DIAGNOSTICS changed_rows = ROW_COUNT;
        IF changed_rows <> 1 THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''key revocation projection race refused'';
        END IF;
        RETURN QUERY SELECT generated_act_id, generated_act_digest,
                            observed_now_us;
    END';

CREATE FUNCTION ofarm.resume_tenant_capability_admission(
    expected_head_id pg_catalog.uuid,
    expected_head_digest pg_catalog.text,
    requested_incident_id pg_catalog.uuid,
    requested_close_receipt_id pg_catalog.uuid,
    requested_kms_evidence_digest pg_catalog.text,
    requested_iam_evidence_digest pg_catalog.text,
    requested_reason pg_catalog.text
)
RETURNS TABLE (
    act_id pg_catalog.uuid,
    act_digest pg_catalog.text,
    decided_at_us pg_catalog.int8
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        candidate ofarm.tenant_capability_verification_key%ROWTYPE;
        keyring ofarm.tenant_capability_keyring%ROWTYPE;
        authority pg_catalog.record;
        selected_authority pg_catalog.record;
        generated_act_id pg_catalog.uuid;
        generated_act_digest pg_catalog.text;
        observed_now_us pg_catalog.int8;
        next_sequence pg_catalog.int8;
        changed_rows pg_catalog.int4;
    BEGIN
        IF pg_catalog.current_setting(''transaction_isolation'') <>
                ''read committed'' THEN
            RAISE EXCEPTION USING ERRCODE = ''25001'',
                MESSAGE = ''admission resume requires READ COMMITTED'';
        END IF;
        IF SESSION_USER <> ''ofarm_capability_key_control_login'' THEN
            RAISE EXCEPTION USING ERRCODE = ''42501'',
                MESSAGE = ''key controller identity differs'';
        END IF;
        IF expected_head_id IS NULL
           OR expected_head_id =
                ''00000000-0000-0000-0000-000000000000''::pg_catalog.uuid
           OR expected_head_digest IS NULL
           OR expected_head_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_incident_id IS NULL
           OR requested_incident_id =
                ''00000000-0000-0000-0000-000000000000''::pg_catalog.uuid
           OR requested_close_receipt_id IS NULL
           OR requested_close_receipt_id =
                ''00000000-0000-0000-0000-000000000000''::pg_catalog.uuid
           OR requested_kms_evidence_digest IS NULL
           OR requested_kms_evidence_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_iam_evidence_digest IS NULL
           OR requested_iam_evidence_digest OPERATOR(pg_catalog.!~)
                ''^sha256:[0-9a-f]{64}$''
           OR requested_reason IS NULL THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''admission resume arguments differ'';
        END IF;
        PERFORM pg_catalog.pg_advisory_xact_lock(1330004306, 1413694001);
        SELECT ring.* INTO STRICT keyring
          FROM ofarm.tenant_capability_keyring AS ring
         FOR UPDATE;
        SELECT * INTO STRICT authority
          FROM ofarm.fold_tenant_capability_key_lifecycle(NULL);
        IF authority.issuing_kid IS NULL THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''admission resume has no issuing key'';
        END IF;
        SELECT key.* INTO STRICT candidate
          FROM ofarm.tenant_capability_verification_key AS key
         WHERE key.kid = authority.issuing_kid
         FOR UPDATE;
        SELECT * INTO STRICT selected_authority
          FROM ofarm.fold_tenant_capability_key_lifecycle(candidate.kid);
        IF keyring.audience IS DISTINCT FROM candidate.audience
           OR keyring.projected_head_sequence IS DISTINCT FROM authority.head_sequence
           OR keyring.projected_head_id IS DISTINCT FROM authority.head_id
           OR keyring.projected_head_digest::pg_catalog.text
                IS DISTINCT FROM authority.head_digest
           OR keyring.projected_admission_state IS DISTINCT FROM
                authority.admission_state
           OR keyring.projected_issuing_kid IS DISTINCT FROM authority.issuing_kid
           OR keyring.projected_issuing_candidate_digest::pg_catalog.text
                IS DISTINCT FROM authority.issuing_candidate_digest
           OR keyring.unresolved_incident_id IS DISTINCT FROM
                authority.unresolved_incident_id
           OR keyring.close_act_id IS DISTINCT FROM authority.close_act_id
           OR keyring.close_receipt_id IS DISTINCT FROM authority.close_receipt_id
           OR authority.head_id IS DISTINCT FROM expected_head_id
           OR authority.head_digest IS DISTINCT FROM expected_head_digest
           OR authority.admission_state <> ''CLOSED''
           OR authority.unresolved_incident_id IS DISTINCT FROM
                requested_incident_id
           OR authority.close_receipt_id IS DISTINCT FROM
                requested_close_receipt_id
           OR selected_authority.selected_revoked
           OR (
                authority.close_reason IN (
                    ''ROTATION_HANDOFF'', ''COMPROMISE''
                )
                AND NOT authority.close_target_revoked
           )
           OR candidate.kid IS NOT DISTINCT FROM authority.close_target_kid
           OR requested_reason IS DISTINCT FROM (CASE authority.close_reason
                WHEN ''COMPROMISE'' THEN ''COMPROMISE_RESOLVED''
                WHEN ''ROTATION_HANDOFF'' THEN ''ROTATION_HANDOFF_COMPLETE''
                WHEN ''NATURAL_RETIREMENT''
                    THEN ''NATURAL_RETIREMENT_COMPLETE''
                ELSE NULL
              END)
           OR keyring.projected_head_id IS DISTINCT FROM authority.head_id
           OR keyring.projected_head_digest::pg_catalog.text
                IS DISTINCT FROM authority.head_digest THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''admission resume precondition failed'';
        END IF;
        observed_now_us := (
            extract(epoch FROM pg_catalog.clock_timestamp()) * 1000000
        )::pg_catalog.int8;
        IF observed_now_us >= authority.issuing_retirement_us THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''admission resume key is not issuing'';
        END IF;
        next_sequence := authority.head_sequence + 1;
        generated_act_id := pg_catalog.gen_random_uuid();
        generated_act_digest := ofarm.compute_tenant_capability_key_act_digest(
            next_sequence, generated_act_id, authority.head_id,
            authority.head_digest, ''RESUME_ADMISSION'', NULL, NULL,
            candidate.kid, candidate.candidate_digest::pg_catalog.text,
            candidate.audience, ''Ed25519'',
            observed_now_us, observed_now_us,
            NULL, NULL, requested_incident_id, requested_close_receipt_id,
            NULL, requested_kms_evidence_digest, requested_iam_evidence_digest,
            SESSION_USER::pg_catalog.text, requested_reason
        );
        INSERT INTO ofarm.tenant_capability_key_lifecycle (
            stream_sequence, act_id, act_digest, prior_act_id, prior_act_digest,
            act_kind, new_kid, new_candidate_digest, audience, algorithm,
            decided_at_us, effective_at_us, incident_id, close_receipt_id,
            kms_evidence_digest, iam_evidence_digest, accountable_control_ref,
            reason
        ) VALUES (
            next_sequence, generated_act_id, generated_act_digest,
            authority.head_id, authority.head_digest, ''RESUME_ADMISSION'',
            candidate.kid, candidate.candidate_digest, candidate.audience,
            ''Ed25519'', observed_now_us, observed_now_us,
            requested_incident_id, requested_close_receipt_id,
            requested_kms_evidence_digest::ofarm.sha256_id,
            requested_iam_evidence_digest::ofarm.sha256_id,
            SESSION_USER::pg_catalog.text::ofarm.ascii_id,
            requested_reason::ofarm.ascii_id
        );
        PERFORM *
          FROM ofarm.fold_tenant_capability_key_lifecycle(candidate.kid);
        UPDATE ofarm.tenant_capability_keyring AS ring SET
            projected_head_sequence = next_sequence,
            projected_head_id = generated_act_id,
            projected_head_digest = generated_act_digest,
            projected_admission_state = ''OPEN'',
            unresolved_incident_id = NULL,
            close_act_id = NULL,
            close_receipt_id = NULL,
            rebuilt_at = pg_catalog.clock_timestamp()
         WHERE ring.audience = candidate.audience
           AND ring.projected_head_id = expected_head_id
           AND ring.projected_head_digest::pg_catalog.text = expected_head_digest
           AND ring.projected_admission_state = ''CLOSED'';
        GET DIAGNOSTICS changed_rows = ROW_COUNT;
        IF changed_rows <> 1 THEN
            RAISE EXCEPTION USING ERRCODE = ''40001'',
                MESSAGE = ''admission resume projection race refused'';
        END IF;
        RETURN QUERY SELECT generated_act_id, generated_act_digest,
                            observed_now_us;
    END';

CREATE FUNCTION ofarm.rebuild_tenant_capability_keyring()
RETURNS TABLE (
    deleted_projection_rows pg_catalog.int8,
    upserted_projection_rows pg_catalog.int8
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        authority pg_catalog.record;
        protected_audience pg_catalog.text;
    BEGIN
        IF pg_catalog.current_setting(''transaction_isolation'') <>
                ''read committed'' THEN
            RAISE EXCEPTION USING ERRCODE = ''25001'',
                MESSAGE = ''keyring rebuild requires READ COMMITTED'';
        END IF;
        IF SESSION_USER <> ''ofarm_capability_key_control_login'' THEN
            RAISE EXCEPTION USING ERRCODE = ''42501'',
                MESSAGE = ''key controller identity differs'';
        END IF;
        PERFORM pg_catalog.pg_advisory_xact_lock(1330004306, 1413694001);
        SELECT instance.audience INTO STRICT protected_audience
          FROM ofarm.tenant_binder_instance AS instance
         WHERE instance.singleton;
        PERFORM 1 FROM ofarm.tenant_capability_keyring FOR UPDATE;
        DELETE FROM ofarm.tenant_capability_keyring AS ring
         WHERE ring.audience <> protected_audience;
        GET DIAGNOSTICS deleted_projection_rows = ROW_COUNT;
        SELECT * INTO STRICT authority
          FROM ofarm.fold_tenant_capability_key_lifecycle(NULL);
        INSERT INTO ofarm.tenant_capability_keyring (
            audience, projected_head_sequence, projected_head_id,
            projected_head_digest, projected_admission_state,
            projected_issuing_kid, projected_issuing_candidate_digest,
            unresolved_incident_id, close_act_id, close_receipt_id, rebuilt_at
        ) VALUES (
            protected_audience, authority.head_sequence, authority.head_id,
            authority.head_digest, authority.admission_state,
            authority.issuing_kid, authority.issuing_candidate_digest,
            authority.unresolved_incident_id, authority.close_act_id,
            authority.close_receipt_id, pg_catalog.clock_timestamp()
        )
        ON CONFLICT (audience) DO UPDATE SET
            projected_head_sequence = EXCLUDED.projected_head_sequence,
            projected_head_id = EXCLUDED.projected_head_id,
            projected_head_digest = EXCLUDED.projected_head_digest,
            projected_admission_state = EXCLUDED.projected_admission_state,
            projected_issuing_kid = EXCLUDED.projected_issuing_kid,
            projected_issuing_candidate_digest =
                EXCLUDED.projected_issuing_candidate_digest,
            unresolved_incident_id = EXCLUDED.unresolved_incident_id,
            close_act_id = EXCLUDED.close_act_id,
            close_receipt_id = EXCLUDED.close_receipt_id,
            rebuilt_at = EXCLUDED.rebuilt_at;
        GET DIAGNOSTICS upserted_projection_rows = ROW_COUNT;
        IF upserted_projection_rows <> 1 THEN
            RAISE EXCEPTION USING ERRCODE = ''55000'',
                MESSAGE = ''keyring singleton differs'';
        END IF;
        RETURN NEXT;
    END';

CREATE FUNCTION ofarm.observe_tenant_capability_key(
    requested_kid pg_catalog.text
)
RETURNS TABLE (
    binder_instance_id pg_catalog.uuid,
    audience pg_catalog.text,
    contract_digest pg_catalog.text,
    observed_at_us pg_catalog.int8,
    candidate_kid pg_catalog.text,
    candidate_digest pg_catalog.text,
    public_key pg_catalog.bytea,
    public_key_digest pg_catalog.text,
    kms_key_version_resource pg_catalog.text,
    admission_state pg_catalog.text,
    head_sequence pg_catalog.int8,
    head_id pg_catalog.uuid,
    head_digest pg_catalog.text,
    head_prior_id pg_catalog.uuid,
    head_prior_digest pg_catalog.text,
    head_kind pg_catalog.text,
    head_old_kid pg_catalog.text,
    head_old_candidate_digest pg_catalog.text,
    head_new_kid pg_catalog.text,
    head_new_candidate_digest pg_catalog.text,
    head_algorithm pg_catalog.text,
    head_decided_at_us pg_catalog.int8,
    head_effective_at_us pg_catalog.int8,
    head_new_issuance_end_us pg_catalog.int8,
    head_old_verification_end_us pg_catalog.int8,
    head_incident_id pg_catalog.uuid,
    head_close_receipt_id pg_catalog.uuid,
    head_preflight_receipt_digest pg_catalog.text,
    head_kms_evidence_digest pg_catalog.text,
    head_iam_evidence_digest pg_catalog.text,
    head_accountable_control_ref pg_catalog.text,
    head_reason pg_catalog.text,
    issuing_kid pg_catalog.text,
    issuing_candidate_digest pg_catalog.text,
    issuing_activated_at_us pg_catalog.int8,
    issuing_retirement_us pg_catalog.int8,
    issuing_verification_end_us pg_catalog.int8,
    selected_ever_activated pg_catalog.bool,
    selected_activated_at_us pg_catalog.int8,
    selected_retirement_us pg_catalog.int8,
    selected_verification_end_us pg_catalog.int8,
    selected_revoked pg_catalog.bool,
    unresolved_incident_id pg_catalog.uuid,
    close_act_id pg_catalog.uuid,
    close_receipt_id pg_catalog.uuid,
    close_reason pg_catalog.text,
    close_target_kid pg_catalog.text,
    close_target_candidate_digest pg_catalog.text,
    close_target_revoked pg_catalog.bool
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        instance ofarm.tenant_binder_instance%ROWTYPE;
        candidate ofarm.tenant_capability_verification_key%ROWTYPE;
        authority pg_catalog.record;
        head ofarm.tenant_capability_key_lifecycle%ROWTYPE;
    BEGIN
        IF SESSION_USER <> ''ofarm_capability_key_control_login'' THEN
            RAISE EXCEPTION USING ERRCODE = ''42501'',
                MESSAGE = ''key lifecycle observer identity differs'';
        END IF;
        IF requested_kid IS NULL
           OR pg_catalog.octet_length(requested_kid) <> 43
           OR requested_kid OPERATOR(pg_catalog.!~) ''^[A-Za-z0-9_-]{43}$'' THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''key lifecycle observer argument differs'';
        END IF;
        SELECT protected.* INTO STRICT instance
          FROM ofarm.tenant_binder_instance AS protected
         WHERE protected.singleton;
        SELECT key.* INTO STRICT candidate
          FROM ofarm.tenant_capability_verification_key AS key
         WHERE key.kid = requested_kid;
        SELECT * INTO STRICT authority
          FROM ofarm.fold_tenant_capability_key_lifecycle(candidate.kid);
        IF candidate.audience <> instance.audience
           OR candidate.algorithm <> ''Ed25519''
           OR candidate.accountable_control_ref::pg_catalog.text <>
                ''ofarm_capability_key_control_login''
           OR (
                authority.selected_ever_activated
                AND authority.selected_candidate_digest IS DISTINCT FROM
                    candidate.candidate_digest::pg_catalog.text
           ) THEN
            RAISE EXCEPTION USING ERRCODE = ''55000'',
                MESSAGE = ''key lifecycle observation authority differs'';
        END IF;
        IF authority.head_id IS NOT NULL THEN
            SELECT act.* INTO STRICT head
              FROM ofarm.tenant_capability_key_lifecycle AS act
             WHERE act.stream_sequence = authority.head_sequence
               AND act.act_id = authority.head_id
               AND act.act_digest::pg_catalog.text = authority.head_digest;
        END IF;
        binder_instance_id := instance.instance_id;
        audience := instance.audience;
        contract_digest := instance.contract_digest::pg_catalog.text;
        observed_at_us := (
            extract(epoch FROM pg_catalog.clock_timestamp()) * 1000000
        )::pg_catalog.int8;
        candidate_kid := candidate.kid;
        candidate_digest := candidate.candidate_digest::pg_catalog.text;
        public_key := candidate.public_key;
        public_key_digest := candidate.public_key_digest::pg_catalog.text;
        kms_key_version_resource := candidate.kms_key_version_resource;
        admission_state := authority.admission_state;
        head_sequence := authority.head_sequence;
        head_id := authority.head_id;
        head_digest := authority.head_digest;
        head_prior_id := head.prior_act_id;
        head_prior_digest := head.prior_act_digest::pg_catalog.text;
        head_kind := head.act_kind;
        head_old_kid := head.old_kid;
        head_old_candidate_digest :=
            head.old_candidate_digest::pg_catalog.text;
        head_new_kid := head.new_kid;
        head_new_candidate_digest :=
            head.new_candidate_digest::pg_catalog.text;
        head_algorithm := head.algorithm;
        head_decided_at_us := head.decided_at_us;
        head_effective_at_us := head.effective_at_us;
        head_new_issuance_end_us := head.new_issuance_end_us;
        head_old_verification_end_us := head.old_verification_end_us;
        head_incident_id := head.incident_id;
        head_close_receipt_id := head.close_receipt_id;
        head_preflight_receipt_digest :=
            head.preflight_receipt_digest::pg_catalog.text;
        head_kms_evidence_digest :=
            head.kms_evidence_digest::pg_catalog.text;
        head_iam_evidence_digest :=
            head.iam_evidence_digest::pg_catalog.text;
        head_accountable_control_ref :=
            head.accountable_control_ref::pg_catalog.text;
        head_reason := head.reason::pg_catalog.text;
        issuing_kid := authority.issuing_kid;
        issuing_candidate_digest := authority.issuing_candidate_digest;
        issuing_activated_at_us := authority.issuing_activated_at_us;
        issuing_retirement_us := authority.issuing_retirement_us;
        issuing_verification_end_us := authority.issuing_verification_end_us;
        selected_ever_activated := authority.selected_ever_activated;
        selected_activated_at_us := authority.selected_activated_at_us;
        selected_retirement_us := authority.selected_retirement_us;
        selected_verification_end_us :=
            authority.selected_verification_end_us;
        selected_revoked := authority.selected_revoked;
        unresolved_incident_id := authority.unresolved_incident_id;
        close_act_id := authority.close_act_id;
        close_receipt_id := authority.close_receipt_id;
        close_reason := authority.close_reason;
        close_target_kid := authority.close_target_kid;
        close_target_candidate_digest :=
            authority.close_target_candidate_digest;
        close_target_revoked := authority.close_target_revoked;
        RETURN NEXT;
    END';

CREATE TRIGGER governed_write_batch_stamp_full_xid
BEFORE INSERT ON ofarm.governed_write_batch
FOR EACH ROW EXECUTE FUNCTION ofarm.stamp_governed_batch_full_xid();
CREATE TRIGGER kernel_record_stamp_batch_full_xid
BEFORE INSERT ON ofarm.kernel_record
FOR EACH ROW EXECUTE FUNCTION ofarm.stamp_batch_member_full_xid();
CREATE TRIGGER kernel_edge_stamp_batch_full_xid
BEFORE INSERT ON ofarm.kernel_edge
FOR EACH ROW EXECUTE FUNCTION ofarm.stamp_batch_member_full_xid();
CREATE TRIGGER kernel_gate_log_stamp_batch_full_xid
BEFORE INSERT ON ofarm.kernel_gate_log
FOR EACH ROW EXECUTE FUNCTION ofarm.stamp_batch_member_full_xid();
CREATE TRIGGER kernel_idempotency_stamp_batch_full_xid
BEFORE INSERT ON ofarm.kernel_idempotency
FOR EACH ROW EXECUTE FUNCTION ofarm.stamp_batch_member_full_xid();
CREATE TRIGGER derived_materialization_stamp_batch_full_xid
BEFORE INSERT ON ofarm.derived_materialization
FOR EACH ROW EXECUTE FUNCTION ofarm.stamp_batch_member_full_xid();
CREATE TRIGGER reference_snapshot_data_stamp_batch_full_xid
BEFORE INSERT ON ofarm.reference_snapshot_data
FOR EACH ROW EXECUTE FUNCTION ofarm.stamp_batch_member_full_xid();
CREATE TRIGGER runtime_trace_stamp_batch_full_xid
BEFORE INSERT ON ofarm.runtime_trace
FOR EACH ROW EXECUTE FUNCTION ofarm.stamp_batch_member_full_xid();
CREATE TRIGGER export_artifact_stamp_batch_full_xid
BEFORE INSERT ON ofarm.export_artifact
FOR EACH ROW EXECUTE FUNCTION ofarm.stamp_batch_member_full_xid();
CREATE TRIGGER kernel_record_reference_stamp_batch_full_xid
BEFORE INSERT ON ofarm.kernel_record_reference
FOR EACH ROW EXECUTE FUNCTION ofarm.stamp_batch_member_full_xid();

CREATE TRIGGER tenant_registry_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.tenant_registry
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER runtime_content_blob_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.runtime_content_blob
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER runtime_tenant_content_blob_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.runtime_tenant_content_blob
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER runtime_bundle_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.runtime_bundle
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER runtime_bundle_component_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.runtime_bundle_component
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER governed_write_batch_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.governed_write_batch
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER kernel_record_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.kernel_record
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER principal_binding_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.principal_binding
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER principal_binding_lifecycle_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.principal_binding_lifecycle
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER tenant_binder_instance_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.tenant_binder_instance
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER tenant_capability_verification_key_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.tenant_capability_verification_key
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER tenant_capability_key_lifecycle_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.tenant_capability_key_lifecycle
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER kernel_edge_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.kernel_edge
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER kernel_gate_log_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.kernel_gate_log
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER kernel_idempotency_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.kernel_idempotency
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER reference_snapshot_data_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.reference_snapshot_data
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER runtime_trace_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.runtime_trace
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER export_artifact_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.export_artifact
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();
CREATE TRIGGER kernel_record_reference_reject_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON ofarm.kernel_record_reference
FOR EACH STATEMENT EXECUTE FUNCTION ofarm.reject_immutable_relation_truncate();

ALTER TABLE ofarm.runtime_tenant_content_blob ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.runtime_tenant_content_blob FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.runtime_tenant_content_blob
TO ofarm_app, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.runtime_bundle ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.runtime_bundle FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.runtime_bundle
TO ofarm_app, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.runtime_bundle_component ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.runtime_bundle_component FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.runtime_bundle_component
TO ofarm_app, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.governed_write_batch ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.governed_write_batch FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.governed_write_batch
TO ofarm_app, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.kernel_record ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.kernel_record FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.kernel_record
TO ofarm_app, ofarm_graph_validator, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.kernel_edge ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.kernel_edge FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.kernel_edge
TO ofarm_app, ofarm_graph_validator, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.kernel_gate_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.kernel_gate_log FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.kernel_gate_log
TO ofarm_app, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.kernel_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.kernel_idempotency FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.kernel_idempotency
TO ofarm_app, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.derived_materialization ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.derived_materialization FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.derived_materialization
TO ofarm_app, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.derived_dependency_index ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.derived_dependency_index FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.derived_dependency_index
TO ofarm_app, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.reference_snapshot_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.reference_snapshot_data FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.reference_snapshot_data
TO ofarm_app, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.runtime_trace ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.runtime_trace FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.runtime_trace
TO ofarm_app, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.export_artifact ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.export_artifact FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.export_artifact
TO ofarm_app, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

ALTER TABLE ofarm.kernel_record_reference ENABLE ROW LEVEL SECURITY;
ALTER TABLE ofarm.kernel_record_reference FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ofarm.kernel_record_reference
TO ofarm_app, ofarm_worker
USING (tenant_id = ofarm.current_tenant_id())
WITH CHECK (tenant_id = ofarm.current_tenant_id());

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA ofarm FROM PUBLIC;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA ofarm FROM PUBLIC;

GRANT SELECT ON TABLE ofarm.runtime_content_blob TO ofarm_app, ofarm_worker;
GRANT SELECT, INSERT ON TABLE
    ofarm.runtime_tenant_content_blob,
    ofarm.runtime_bundle,
    ofarm.runtime_bundle_component,
    ofarm.governed_write_batch,
    ofarm.kernel_record,
    ofarm.kernel_edge,
    ofarm.kernel_gate_log,
    ofarm.kernel_idempotency,
    ofarm.reference_snapshot_data,
    ofarm.runtime_trace,
    ofarm.export_artifact,
    ofarm.kernel_record_reference
TO ofarm_app, ofarm_worker;
GRANT SELECT, INSERT, DELETE ON TABLE
    ofarm.derived_materialization
TO ofarm_app, ofarm_worker;
GRANT UPDATE (freshness, superseded_by)
ON TABLE ofarm.derived_materialization TO ofarm_app, ofarm_worker;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    ofarm.derived_dependency_index
TO ofarm_app, ofarm_worker;
GRANT EXECUTE ON FUNCTION ofarm.compute_materialization_key_digest(
    pg_catalog.jsonb
) TO ofarm_app, ofarm_worker;
GRANT EXECUTE ON FUNCTION ofarm.valid_ascii_id(pg_catalog.text)
TO ofarm_app, ofarm_worker;
GRANT EXECUTE ON FUNCTION ofarm.valid_runtime_logical_ref(pg_catalog.text)
TO ofarm_app, ofarm_worker;

GRANT EXECUTE ON FUNCTION ofarm.register_tenant(pg_catalog.text)
TO ofarm_tenant_registrar;
GRANT EXECUTE ON FUNCTION ofarm.compute_principal_binding_version_digest(
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.uuid,
    pg_catalog.uuid,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.timestamptz,
    pg_catalog.timestamptz,
    pg_catalog.uuid
) TO ofarm_identity_writer;
GRANT EXECUTE ON FUNCTION ofarm.lp32(pg_catalog.bytea)
TO ofarm_identity_writer;
GRANT EXECUTE ON FUNCTION ofarm.compute_principal_lifecycle_act_digest(
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.int8,
    pg_catalog.uuid,
    pg_catalog.text,
    pg_catalog.uuid,
    pg_catalog.text,
    pg_catalog.uuid,
    pg_catalog.text,
    pg_catalog.uuid,
    pg_catalog.text,
    pg_catalog.timestamptz,
    pg_catalog.timestamptz,
    pg_catalog.text,
    pg_catalog.text
) TO ofarm_identity_writer;
GRANT EXECUTE ON FUNCTION ofarm.transition_principal_binding(
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.uuid,
    pg_catalog.text,
    pg_catalog.uuid,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.uuid,
    pg_catalog.text,
    pg_catalog.uuid,
    pg_catalog.text,
    pg_catalog.uuid,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.text,
    pg_catalog.timestamptz,
    pg_catalog.timestamptz,
    pg_catalog.uuid,
    pg_catalog.timestamptz,
    pg_catalog.timestamptz,
    pg_catalog.text,
    pg_catalog.text
) TO ofarm_identity_writer;
GRANT EXECUTE ON FUNCTION ofarm.rebuild_principal_binding_current()
TO ofarm_identity_writer;

CREATE FUNCTION ofarm.uuid_from_network(value pg_catalog.bytea)
RETURNS pg_catalog.uuid
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        encoded pg_catalog.text;
        decoded pg_catalog.uuid;
    BEGIN
        IF pg_catalog.octet_length(value) <> 16 THEN
            RAISE EXCEPTION USING
                ERRCODE = ''22023'',
                MESSAGE = ''UUID field length differs'';
        END IF;
        encoded := pg_catalog.encode(value, ''hex'');
        decoded := (
            pg_catalog.substr(encoded, 1, 8) || ''-'' ||
            pg_catalog.substr(encoded, 9, 4) || ''-'' ||
            pg_catalog.substr(encoded, 13, 4) || ''-'' ||
            pg_catalog.substr(encoded, 17, 4) || ''-'' ||
            pg_catalog.substr(encoded, 21, 12)
        )::pg_catalog.uuid;
        IF decoded = ''00000000-0000-0000-0000-000000000000''::pg_catalog.uuid
           OR pg_catalog.uuid_send(decoded) <> value THEN
            RAISE EXCEPTION USING
                ERRCODE = ''22023'',
                MESSAGE = ''UUID field is not canonical'';
        END IF;
        RETURN decoded;
    END';

CREATE FUNCTION ofarm.int8_from_network(value pg_catalog.bytea)
RETURNS pg_catalog.int8
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        accumulator pg_catalog.numeric := 0;
        byte_index pg_catalog.int4;
    BEGIN
        IF pg_catalog.octet_length(value) <> 8 THEN
            RAISE EXCEPTION USING
                ERRCODE = ''22023'',
                MESSAGE = ''int64 field length differs'';
        END IF;
        FOR byte_index IN 0..7 LOOP
            accumulator := accumulator * 256 +
                pg_catalog.get_byte(value, byte_index);
        END LOOP;
        IF accumulator >= 9223372036854775808::pg_catalog.numeric THEN
            accumulator := accumulator -
                18446744073709551616::pg_catalog.numeric;
        END IF;
        RETURN accumulator::pg_catalog.int8;
    END';

CREATE FUNCTION ofarm.parse_tenant_capability_payload(
    payload pg_catalog.bytea
)
RETURNS TABLE (
    contract_digest_bytes pg_catalog.bytea,
    challenge_id_bytes pg_catalog.bytea,
    audience_bytes pg_catalog.bytea,
    key_id_bytes pg_catalog.bytea,
    equality_policy_bytes pg_catalog.bytea,
    issuer_bytes pg_catalog.bytea,
    subject_bytes pg_catalog.bytea,
    binding_version_id_bytes pg_catalog.bytea,
    binding_version_digest_bytes pg_catalog.bytea,
    lifecycle_head_id_bytes pg_catalog.bytea,
    lifecycle_head_digest_bytes pg_catalog.bytea,
    tenant_id_bytes pg_catalog.bytea,
    tenant_registration_digest_bytes pg_catalog.bytea,
    party_ref_bytes pg_catalog.bytea,
    party_record_kind_bytes pg_catalog.bytea,
    party_record_id_bytes pg_catalog.bytea,
    party_schema_digest_bytes pg_catalog.bytea,
    party_payload_digest_bytes pg_catalog.bytea,
    issued_at_bytes pg_catalog.bytea,
    not_before_bytes pg_catalog.bytea,
    expires_at_bytes pg_catalog.bytea,
    nonce_bytes pg_catalog.bytea
)
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        domain_bytes pg_catalog.bytea := pg_catalog.convert_to(
            ''OFARM_TENANT_CAPABILITY_V1'', ''UTF8''
        ) || pg_catalog.decode(''00'', ''hex'');
        parsed_fields pg_catalog.bytea[] := ARRAY[]::pg_catalog.bytea[];
        cursor_position pg_catalog.int8;
        field_index pg_catalog.int4;
        field_length pg_catalog.int8;
        payload_length pg_catalog.int8 := pg_catalog.octet_length(payload);
    BEGIN
        IF payload_length > 8192
           OR payload_length < pg_catalog.octet_length(domain_bytes) + 88
           OR pg_catalog.substring(
                payload, 1, pg_catalog.octet_length(domain_bytes)
              ) <> domain_bytes THEN
            RAISE EXCEPTION USING
                ERRCODE = ''22023'',
                MESSAGE = ''tenant capability payload domain differs'';
        END IF;
        cursor_position := pg_catalog.octet_length(domain_bytes) + 1;
        FOR field_index IN 1..22 LOOP
            IF cursor_position + 3 > payload_length THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''22023'',
                    MESSAGE = ''tenant capability payload frame is truncated'';
            END IF;
            field_length :=
                pg_catalog.get_byte(payload, cursor_position::pg_catalog.int4 - 1)::pg_catalog.int8 * 16777216
                + pg_catalog.get_byte(payload, cursor_position::pg_catalog.int4)::pg_catalog.int8 * 65536
                + pg_catalog.get_byte(payload, cursor_position::pg_catalog.int4 + 1)::pg_catalog.int8 * 256
                + pg_catalog.get_byte(payload, cursor_position::pg_catalog.int4 + 2)::pg_catalog.int8;
            IF field_length > payload_length - cursor_position - 3 THEN
                RAISE EXCEPTION USING
                    ERRCODE = ''22023'',
                    MESSAGE = ''tenant capability payload field is truncated'';
            END IF;
            parsed_fields := pg_catalog.array_append(
                parsed_fields,
                pg_catalog.substring(
                    payload,
                    cursor_position::pg_catalog.int4 + 4,
                    field_length::pg_catalog.int4
                )
            );
            cursor_position := cursor_position + 4 + field_length;
        END LOOP;
        IF cursor_position <> payload_length + 1 THEN
            RAISE EXCEPTION USING
                ERRCODE = ''22023'',
                MESSAGE = ''tenant capability payload has trailing bytes'';
        END IF;
        RETURN QUERY SELECT
            parsed_fields[1], parsed_fields[2], parsed_fields[3],
            parsed_fields[4], parsed_fields[5], parsed_fields[6],
            parsed_fields[7], parsed_fields[8], parsed_fields[9],
            parsed_fields[10], parsed_fields[11], parsed_fields[12],
            parsed_fields[13], parsed_fields[14], parsed_fields[15],
            parsed_fields[16], parsed_fields[17], parsed_fields[18],
            parsed_fields[19], parsed_fields[20], parsed_fields[21],
            parsed_fields[22];
    END';

CREATE FUNCTION ofarm.purge_stale_tenant_context()
RETURNS pg_catalog.int4
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        deleted_count pg_catalog.int4;
    BEGIN
        DELETE FROM ofarm.tenant_binding_context AS context
         WHERE context.ctid IN (
            SELECT candidate.ctid
              FROM ofarm.tenant_binding_context AS candidate
             WHERE NOT ofarm.backend_incarnation_is_live(
                    candidate.backend_pid,
                    candidate.backend_start
             )
             ORDER BY
                candidate.challenge_created_at,
                candidate.backend_pid,
                candidate.full_xid
             LIMIT 1024
             FOR UPDATE OF candidate SKIP LOCKED
         );
        GET DIAGNOSTICS deleted_count = ROW_COUNT;
        RETURN deleted_count;
    END';

CREATE FUNCTION ofarm.create_tenant_challenge()
RETURNS TABLE (
    challenge_id pg_catalog.uuid,
    audience pg_catalog.text
)
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        observed_backend_start pg_catalog.timestamptz;
        observed_full_xid pg_catalog.xid8;
        generated_challenge_id pg_catalog.uuid;
        protected_audience pg_catalog.text;
    BEGIN
        PERFORM ofarm.purge_stale_tenant_context();
        observed_backend_start := ofarm.current_backend_start();
        observed_full_xid := pg_catalog.pg_current_xact_id();

        DELETE FROM ofarm.tenant_binding_context AS context
         WHERE context.backend_pid = pg_catalog.pg_backend_pid()
           AND context.backend_start = observed_backend_start
           AND context.full_xid <> observed_full_xid;

        IF EXISTS (
            SELECT 1
              FROM ofarm.tenant_binding_context AS context
             WHERE context.backend_pid = pg_catalog.pg_backend_pid()
               AND context.backend_start = observed_backend_start
        ) THEN
            RAISE EXCEPTION USING
                ERRCODE = ''55000'',
                MESSAGE = ''tenant challenge already exists for this transaction'';
        END IF;

        generated_challenge_id := pg_catalog.gen_random_uuid();
        INSERT INTO ofarm.tenant_binding_context (
            backend_pid,
            backend_start,
            full_xid,
            challenge_id,
            context_state
        ) VALUES (
            pg_catalog.pg_backend_pid(),
            observed_backend_start,
            observed_full_xid,
            generated_challenge_id,
            ''CHALLENGE''
        );
        SELECT instance.audience
          INTO STRICT protected_audience
          FROM ofarm.tenant_binder_instance AS instance
         WHERE instance.singleton;
        RETURN QUERY SELECT generated_challenge_id, protected_audience;
    END';

CREATE FUNCTION ofarm.valid_tenant_capability_time_window(
    issued_at_us pg_catalog.int8,
    not_before_us pg_catalog.int8,
    expires_at_us pg_catalog.int8,
    observed_now_us pg_catalog.int8,
    challenge_created_at_us pg_catalog.int8
)
RETURNS pg_catalog.bool
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT observed_now_us <= 9223372036849775807
           AND challenge_created_at_us >= -9223372036849775808
           AND challenge_created_at_us <= 9223372036794775807
           AND issued_at_us <= not_before_us
           AND not_before_us < expires_at_us
           AND expires_at_us::pg_catalog.numeric -
                issued_at_us::pg_catalog.numeric <= 60000000
           AND issued_at_us::pg_catalog.numeric >=
                challenge_created_at_us::pg_catalog.numeric - 5000000
           AND issued_at_us::pg_catalog.numeric <=
                observed_now_us::pg_catalog.numeric + 5000000
           AND not_before_us::pg_catalog.numeric <=
                observed_now_us::pg_catalog.numeric + 5000000
           AND observed_now_us < expires_at_us
           AND expires_at_us::pg_catalog.numeric <=
                challenge_created_at_us::pg_catalog.numeric + 60000000
           AND observed_now_us::pg_catalog.numeric <
                challenge_created_at_us::pg_catalog.numeric + 60000000';

CREATE FUNCTION ofarm.bind_tenant_capability(
    serialized_capability pg_catalog.text
)
RETURNS pg_catalog.void
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        observed_backend_start pg_catalog.timestamptz;
        observed_full_xid pg_catalog.xid8;
        protected_context ofarm.tenant_binding_context%ROWTYPE;
        protected_instance ofarm.tenant_binder_instance%ROWTYPE;
        projected_keyring ofarm.tenant_capability_keyring%ROWTYPE;
        selected_candidate ofarm.tenant_capability_verification_key%ROWTYPE;
        key_authority pg_catalog.record;
        projected_principal ofarm.principal_binding_current%ROWTYPE;
        principal_authority pg_catalog.record;
        selected_binding ofarm.principal_binding%ROWTYPE;
        selected_tenant ofarm.tenant_registry%ROWTYPE;
        selected_party pg_catalog.record;
        payload_fields pg_catalog.record;
        protected_segment pg_catalog.text;
        payload_segment pg_catalog.text;
        signature_segment pg_catalog.text;
        protected_bytes pg_catalog.bytea;
        payload_bytes pg_catalog.bytea;
        signature_bytes pg_catalog.bytea;
        signing_input pg_catalog.bytea;
        protected_prefix pg_catalog.bytea := pg_catalog.convert_to(
            ''{"alg":"Ed25519","kid":"'', ''UTF8''
        );
        protected_suffix pg_catalog.bytea := pg_catalog.convert_to(
            ''","typ":"ofarm-tenant-capability+jws"}'', ''UTF8''
        );
        protected_kid pg_catalog.text;
        payload_audience pg_catalog.text;
        payload_kid pg_catalog.text;
        payload_equality_policy pg_catalog.text;
        payload_issuer pg_catalog.text;
        payload_subject pg_catalog.text;
        payload_party_ref pg_catalog.text;
        payload_party_record_kind pg_catalog.text;
        payload_party_record_id pg_catalog.text;
        payload_challenge_id pg_catalog.uuid;
        payload_binding_version_id pg_catalog.uuid;
        payload_lifecycle_head_id pg_catalog.uuid;
        payload_tenant_id pg_catalog.uuid;
        payload_nonce pg_catalog.uuid;
        payload_binding_version_digest pg_catalog.text;
        payload_lifecycle_head_digest pg_catalog.text;
        payload_tenant_registration_digest pg_catalog.text;
        payload_party_schema_digest pg_catalog.text;
        payload_party_payload_digest pg_catalog.text;
        payload_issued_at_us pg_catalog.int8;
        payload_not_before_us pg_catalog.int8;
        payload_expires_at_us pg_catalog.int8;
        observed_now pg_catalog.timestamptz;
        observed_now_us pg_catalog.int8;
        challenge_created_at_us pg_catalog.int8;
        changed_rows pg_catalog.int4;
    BEGIN
        IF pg_catalog.current_setting(''transaction_isolation'') <>
                ''read committed'' THEN
            RAISE EXCEPTION USING ERRCODE = ''25001'',
                MESSAGE = ''tenant capability binding requires READ COMMITTED'';
        END IF;
        IF serialized_capability IS NULL
           OR pg_catalog.octet_length(serialized_capability) NOT BETWEEN 5 AND 8192
           OR (serialized_capability COLLATE pg_catalog."C")
                OPERATOR(pg_catalog.!~)
                ''^[A-Za-z0-9_-]+[.][A-Za-z0-9_-]+[.][A-Za-z0-9_-]+$'' THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''tenant capability envelope differs'';
        END IF;

        observed_backend_start := ofarm.current_backend_start();
        observed_full_xid := pg_catalog.pg_current_xact_id();
        SELECT context.* INTO STRICT protected_context
          FROM ofarm.tenant_binding_context AS context
         WHERE context.backend_pid = pg_catalog.pg_backend_pid()
           AND context.backend_start = observed_backend_start
           AND context.full_xid = observed_full_xid
           AND context.context_state = ''CHALLENGE''
         FOR UPDATE;

        protected_segment := pg_catalog.split_part(serialized_capability, ''.'', 1);
        payload_segment := pg_catalog.split_part(serialized_capability, ''.'', 2);
        signature_segment := pg_catalog.split_part(serialized_capability, ''.'', 3);
        protected_bytes := ofarm.base64url_decode(protected_segment);
        payload_bytes := ofarm.base64url_decode(payload_segment);
        signature_bytes := ofarm.base64url_decode(signature_segment);
        IF pg_catalog.octet_length(protected_bytes) <>
                pg_catalog.octet_length(protected_prefix) + 43 +
                pg_catalog.octet_length(protected_suffix)
           OR pg_catalog.octet_length(signature_bytes) <> 64
           OR pg_catalog.substring(
                protected_bytes, 1,
                pg_catalog.octet_length(protected_prefix)
              ) <> protected_prefix
           OR pg_catalog.substring(
                protected_bytes,
                pg_catalog.octet_length(protected_prefix) + 44
              ) <> protected_suffix THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''tenant capability protected header differs'';
        END IF;
        protected_kid := pg_catalog.convert_from(
            pg_catalog.substring(
                protected_bytes,
                pg_catalog.octet_length(protected_prefix) + 1, 43
            ), ''UTF8''
        );
        IF (protected_kid COLLATE pg_catalog."C")
                OPERATOR(pg_catalog.!~) ''^[A-Za-z0-9_-]{43}$''
           OR protected_bytes <> protected_prefix ||
                pg_catalog.convert_to(protected_kid, ''UTF8'') ||
                protected_suffix THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''tenant capability protected key differs'';
        END IF;
        signing_input := pg_catalog.convert_to(
            protected_segment || ''.'' || payload_segment, ''SQL_ASCII''
        );

        PERFORM pg_catalog.pg_advisory_xact_lock_shared(1330004306, 1413694001);
        SELECT * INTO STRICT key_authority
          FROM ofarm.fold_tenant_capability_key_lifecycle(protected_kid);
        IF key_authority.admission_state <> ''OPEN''
           OR key_authority.head_id IS NULL
           OR NOT key_authority.selected_ever_activated
           OR key_authority.selected_revoked THEN
            RAISE EXCEPTION USING ERRCODE = ''28000'',
                MESSAGE = ''tenant capability key is not admitted'';
        END IF;

        SELECT instance.* INTO STRICT protected_instance
          FROM ofarm.tenant_binder_instance AS instance
         WHERE instance.singleton;
        SELECT keyring.* INTO STRICT projected_keyring
          FROM ofarm.tenant_capability_keyring AS keyring
         WHERE keyring.audience = protected_instance.audience
         FOR KEY SHARE;
        SELECT candidate.* INTO STRICT selected_candidate
          FROM ofarm.tenant_capability_verification_key AS candidate
         WHERE candidate.kid = protected_kid
           AND candidate.audience = protected_instance.audience
         FOR KEY SHARE;
        IF selected_candidate.candidate_digest::pg_catalog.text
                IS DISTINCT FROM key_authority.selected_candidate_digest
           OR selected_candidate.kid <> ofarm.tenant_capability_key_id(
                selected_candidate.public_key
              )
           OR selected_candidate.public_key_digest::pg_catalog.text <>
                ''sha256:'' || pg_catalog.encode(
                    pg_catalog.sha256(selected_candidate.public_key), ''hex''
                )
           OR projected_keyring.projected_head_sequence IS DISTINCT FROM
                key_authority.head_sequence
           OR projected_keyring.projected_head_id IS DISTINCT FROM
                key_authority.head_id
           OR projected_keyring.projected_head_digest::pg_catalog.text
                IS DISTINCT FROM key_authority.head_digest
           OR projected_keyring.projected_admission_state IS DISTINCT FROM
                key_authority.admission_state
           OR projected_keyring.projected_issuing_kid IS DISTINCT FROM
                key_authority.issuing_kid
           OR projected_keyring.projected_issuing_candidate_digest::pg_catalog.text
                IS DISTINCT FROM key_authority.issuing_candidate_digest
           OR projected_keyring.unresolved_incident_id IS DISTINCT FROM
                key_authority.unresolved_incident_id
           OR projected_keyring.close_act_id IS DISTINCT FROM key_authority.close_act_id
           OR projected_keyring.close_receipt_id IS DISTINCT FROM
                key_authority.close_receipt_id THEN
            RAISE EXCEPTION USING ERRCODE = ''55000'',
                MESSAGE = ''tenant capability keyring projection differs'';
        END IF;
        IF ofarm_crypto.ed25519_verify(
            selected_candidate.public_key, signing_input, signature_bytes
        ) IS DISTINCT FROM true THEN
            RAISE EXCEPTION USING ERRCODE = ''28000'',
                MESSAGE = ''tenant capability signature refuses'';
        END IF;

        SELECT * INTO STRICT payload_fields
          FROM ofarm.parse_tenant_capability_payload(payload_bytes);
        IF pg_catalog.octet_length(payload_fields.contract_digest_bytes) <> 32
           OR pg_catalog.octet_length(
                payload_fields.binding_version_digest_bytes
              ) <> 32
           OR pg_catalog.octet_length(
                payload_fields.lifecycle_head_digest_bytes
              ) <> 32
           OR pg_catalog.octet_length(
                payload_fields.tenant_registration_digest_bytes
              ) <> 32
           OR pg_catalog.octet_length(
                payload_fields.party_schema_digest_bytes
              ) <> 32
           OR pg_catalog.octet_length(
                payload_fields.party_payload_digest_bytes
              ) <> 32 THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''tenant capability digest field length differs'';
        END IF;
        IF payload_fields.contract_digest_bytes <> pg_catalog.decode(
                ''39e979fa296122cb66d42eae5e2d7c6dc797ac77ef4324515ae1ab6020088d83'',
                ''hex''
           ) THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''tenant capability contract digest differs'';
        END IF;

        payload_challenge_id := ofarm.uuid_from_network(
            payload_fields.challenge_id_bytes
        );
        payload_binding_version_id := ofarm.uuid_from_network(
            payload_fields.binding_version_id_bytes
        );
        payload_lifecycle_head_id := ofarm.uuid_from_network(
            payload_fields.lifecycle_head_id_bytes
        );
        payload_tenant_id := ofarm.uuid_from_network(payload_fields.tenant_id_bytes);
        payload_nonce := ofarm.uuid_from_network(payload_fields.nonce_bytes);
        IF (pg_catalog.get_byte(payload_fields.nonce_bytes, 6) >> 4) <> 4
           OR (pg_catalog.get_byte(payload_fields.nonce_bytes, 8) & 192) <> 128 THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''tenant capability nonce is not UUIDv4'';
        END IF;

        payload_audience := pg_catalog.convert_from(
            payload_fields.audience_bytes, ''UTF8''
        );
        payload_kid := pg_catalog.convert_from(payload_fields.key_id_bytes, ''UTF8'');
        payload_equality_policy := pg_catalog.convert_from(
            payload_fields.equality_policy_bytes, ''UTF8''
        );
        payload_issuer := pg_catalog.convert_from(payload_fields.issuer_bytes, ''UTF8'');
        payload_subject := pg_catalog.convert_from(payload_fields.subject_bytes, ''UTF8'');
        payload_party_ref := pg_catalog.convert_from(
            payload_fields.party_ref_bytes, ''UTF8''
        );
        payload_party_record_kind := pg_catalog.convert_from(
            payload_fields.party_record_kind_bytes, ''UTF8''
        );
        payload_party_record_id := pg_catalog.convert_from(
            payload_fields.party_record_id_bytes, ''UTF8''
        );
        IF pg_catalog.convert_to(payload_audience, ''UTF8'') <>
                payload_fields.audience_bytes
           OR pg_catalog.convert_to(payload_kid, ''UTF8'') <>
                payload_fields.key_id_bytes
           OR pg_catalog.convert_to(payload_equality_policy, ''UTF8'') <>
                payload_fields.equality_policy_bytes
           OR pg_catalog.convert_to(payload_issuer, ''UTF8'') <>
                payload_fields.issuer_bytes
           OR pg_catalog.convert_to(payload_subject, ''UTF8'') <>
                payload_fields.subject_bytes
           OR pg_catalog.convert_to(payload_party_ref, ''UTF8'') <>
                payload_fields.party_ref_bytes
           OR pg_catalog.convert_to(payload_party_record_kind, ''UTF8'') <>
                payload_fields.party_record_kind_bytes
           OR pg_catalog.convert_to(payload_party_record_id, ''UTF8'') <>
                payload_fields.party_record_id_bytes THEN
            RAISE EXCEPTION USING ERRCODE = ''22023'',
                MESSAGE = ''tenant capability text encoding differs'';
        END IF;
        PERFORM payload_issuer::ofarm.oidc_issuer;
        PERFORM payload_subject::ofarm.oidc_subject;
        PERFORM payload_party_ref::ofarm.tenant_local_ref;
        PERFORM payload_party_record_id::ofarm.tenant_local_ref;
        IF payload_audience <> protected_instance.audience
           OR payload_kid <> protected_kid
           OR payload_equality_policy <> ''OIDC_EXACT_UTF8_V1''
           OR payload_party_record_kind <> ''ofarm.party.v0.1''
           OR payload_party_record_id <> payload_party_ref
           OR payload_challenge_id <> protected_context.challenge_id THEN
            RAISE EXCEPTION USING ERRCODE = ''28000'',
                MESSAGE = ''tenant capability identity fields differ'';
        END IF;

        payload_binding_version_digest := ''sha256:'' || pg_catalog.encode(
            payload_fields.binding_version_digest_bytes, ''hex''
        );
        payload_lifecycle_head_digest := ''sha256:'' || pg_catalog.encode(
            payload_fields.lifecycle_head_digest_bytes, ''hex''
        );
        payload_tenant_registration_digest := ''sha256:'' || pg_catalog.encode(
            payload_fields.tenant_registration_digest_bytes, ''hex''
        );
        payload_party_schema_digest := ''sha256:'' || pg_catalog.encode(
            payload_fields.party_schema_digest_bytes, ''hex''
        );
        payload_party_payload_digest := ''sha256:'' || pg_catalog.encode(
            payload_fields.party_payload_digest_bytes, ''hex''
        );
        payload_issued_at_us := ofarm.int8_from_network(
            payload_fields.issued_at_bytes
        );
        payload_not_before_us := ofarm.int8_from_network(
            payload_fields.not_before_bytes
        );
        payload_expires_at_us := ofarm.int8_from_network(
            payload_fields.expires_at_bytes
        );

        SELECT current.* INTO STRICT projected_principal
          FROM ofarm.principal_binding_current AS current
         WHERE current.equality_policy = payload_equality_policy
           AND current.issuer::pg_catalog.text = payload_issuer
           AND current.subject::pg_catalog.text = payload_subject
         FOR KEY SHARE;
        SELECT * INTO STRICT principal_authority
          FROM ofarm.fold_principal_binding_authority(
                payload_equality_policy, payload_issuer, payload_subject
          );
        IF principal_authority.current_state <> ''ACTIVE''
           OR projected_principal.current_state <> ''ACTIVE''
           OR projected_principal.binding_version_id IS DISTINCT FROM
                principal_authority.binding_version_id
           OR projected_principal.binding_version_digest::pg_catalog.text
                IS DISTINCT FROM principal_authority.binding_version_digest
           OR projected_principal.lifecycle_head_id IS DISTINCT FROM
                principal_authority.lifecycle_head_id
           OR projected_principal.lifecycle_head_digest::pg_catalog.text
                IS DISTINCT FROM principal_authority.lifecycle_head_digest
           OR payload_binding_version_id IS DISTINCT FROM
                principal_authority.binding_version_id
           OR payload_binding_version_digest IS DISTINCT FROM
                principal_authority.binding_version_digest
           OR payload_lifecycle_head_id IS DISTINCT FROM
                principal_authority.lifecycle_head_id
           OR payload_lifecycle_head_digest IS DISTINCT FROM
                principal_authority.lifecycle_head_digest THEN
            RAISE EXCEPTION USING ERRCODE = ''28000'',
                MESSAGE = ''tenant capability principal authority differs'';
        END IF;

        SELECT binding.* INTO STRICT selected_binding
          FROM ofarm.principal_binding AS binding
         WHERE binding.equality_policy = payload_equality_policy
           AND binding.issuer::pg_catalog.text = payload_issuer
           AND binding.subject::pg_catalog.text = payload_subject
           AND binding.binding_version_id = payload_binding_version_id
           AND binding.binding_version_digest::pg_catalog.text =
                payload_binding_version_digest;
        SELECT tenant.* INTO STRICT selected_tenant
          FROM ofarm.tenant_registry AS tenant
         WHERE tenant.tenant_id = payload_tenant_id
           AND tenant.registration_digest::pg_catalog.text =
                payload_tenant_registration_digest;
        SELECT party.tenant_id,
               party.record_id,
               party.record_kind,
               party.schema_digest,
               party.payload_digest,
               party.party_state,
               party.party_id
          INTO STRICT selected_party
          FROM ofarm.kernel_record AS party
         WHERE party.tenant_id = payload_tenant_id
           AND party.record_id::pg_catalog.text = payload_party_record_id
           AND party.record_kind = payload_party_record_kind
           AND party.schema_digest::pg_catalog.text = payload_party_schema_digest
           AND party.payload_digest::pg_catalog.text = payload_party_payload_digest
           AND party.party_state = ''ACTIVE''
           AND party.party_id::pg_catalog.text = payload_party_ref;
        IF selected_binding.tenant_id <> payload_tenant_id
           OR selected_binding.tenant_registration_digest::pg_catalog.text <>
                payload_tenant_registration_digest
           OR selected_binding.party_ref::pg_catalog.text <> payload_party_ref
           OR selected_binding.party_record_kind <> payload_party_record_kind
           OR selected_binding.party_record_id::pg_catalog.text <>
                payload_party_record_id
           OR selected_binding.party_schema_digest::pg_catalog.text <>
                payload_party_schema_digest
           OR selected_binding.party_payload_digest::pg_catalog.text <>
                payload_party_payload_digest
           OR selected_binding.party_state <> ''ACTIVE''
           OR selected_binding.party_payload_party_id::pg_catalog.text <>
                payload_party_ref
           OR selected_tenant.equality_policy <> ''OFARM_ASCII_ID_V1'' THEN
            RAISE EXCEPTION USING ERRCODE = ''28000'',
                MESSAGE = ''tenant capability authoritative tuple differs'';
        END IF;

        observed_now := pg_catalog.clock_timestamp();
        observed_now_us := (
            extract(epoch FROM observed_now) * 1000000
        )::pg_catalog.int8;
        challenge_created_at_us := (
            extract(epoch FROM protected_context.challenge_created_at) *
            1000000
        )::pg_catalog.int8;
        IF ofarm.valid_tenant_capability_time_window(
                payload_issued_at_us,
                payload_not_before_us,
                payload_expires_at_us,
                observed_now_us,
                challenge_created_at_us
           ) IS DISTINCT FROM true
           OR payload_issued_at_us::pg_catalog.numeric <
                key_authority.selected_activated_at_us::pg_catalog.numeric - 5000000
           OR payload_issued_at_us::pg_catalog.numeric >
                key_authority.selected_retirement_us::pg_catalog.numeric + 5000000
           OR payload_expires_at_us > key_authority.selected_verification_end_us
           OR observed_now_us >= key_authority.selected_verification_end_us
           OR observed_now < selected_binding.valid_from
           OR observed_now >= selected_binding.valid_until THEN
            RAISE EXCEPTION USING ERRCODE = ''28000'',
                MESSAGE = ''tenant capability time window refuses'';
        END IF;

        UPDATE ofarm.tenant_binding_context AS context SET
            context_state = ''BOUND'',
            equality_policy = payload_equality_policy,
            issuer = payload_issuer,
            subject = payload_subject,
            binding_version_id = payload_binding_version_id,
            binding_version_digest = payload_binding_version_digest,
            lifecycle_head_id = payload_lifecycle_head_id,
            lifecycle_head_digest = payload_lifecycle_head_digest,
            tenant_id = payload_tenant_id,
            tenant_registration_digest = payload_tenant_registration_digest,
            party_ref = payload_party_ref,
            party_record_kind = payload_party_record_kind,
            party_record_id = payload_party_record_id,
            party_schema_digest = payload_party_schema_digest,
            party_payload_digest = payload_party_payload_digest,
            capability_key_id = protected_kid,
            capability_key_lifecycle_head_id = key_authority.head_id,
            capability_key_lifecycle_head_digest = key_authority.head_digest,
            capability_nonce = payload_nonce,
            bound_at = observed_now
         WHERE context.backend_pid = pg_catalog.pg_backend_pid()
           AND context.backend_start = observed_backend_start
           AND context.full_xid = observed_full_xid
           AND context.challenge_id = payload_challenge_id
           AND context.context_state = ''CHALLENGE'';
        GET DIAGNOSTICS changed_rows = ROW_COUNT;
        IF changed_rows <> 1 THEN
            RAISE EXCEPTION USING ERRCODE = ''55000'',
                MESSAGE = ''tenant capability context transition refused'';
        END IF;
    EXCEPTION
        WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
            RAISE EXCEPTION USING ERRCODE = ''28000'',
                MESSAGE = ''tenant capability authority is unavailable'';
    END';

CREATE FUNCTION ofarm.current_tenant_context()
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
    capability_key_id pg_catalog.text,
    capability_key_lifecycle_head_id pg_catalog.uuid,
    capability_key_lifecycle_head_digest pg_catalog.text,
    capability_nonce pg_catalog.uuid,
    bound_at pg_catalog.timestamptz
)
LANGUAGE plpgsql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        observed_backend_start pg_catalog.timestamptz;
    BEGIN
        observed_backend_start := ofarm.current_backend_start();
        RETURN QUERY
        SELECT context.equality_policy, context.issuer, context.subject,
               context.binding_version_id, context.binding_version_digest,
               context.lifecycle_head_id, context.lifecycle_head_digest,
               context.tenant_id, context.tenant_registration_digest,
               context.party_ref, context.party_record_kind,
               context.party_record_id, context.party_schema_digest,
               context.party_payload_digest, context.capability_key_id,
               context.capability_key_lifecycle_head_id,
               context.capability_key_lifecycle_head_digest,
               context.capability_nonce, context.bound_at
          FROM ofarm.tenant_binding_context AS context
         WHERE context.backend_pid = pg_catalog.pg_backend_pid()
           AND context.backend_start = observed_backend_start
           AND context.full_xid = pg_catalog.pg_current_xact_id()
           AND context.context_state = ''BOUND'';
        IF NOT FOUND THEN
            RAISE EXCEPTION USING ERRCODE = ''42501'',
                MESSAGE = ''verified tenant context is absent'';
        END IF;
    END';

CREATE FUNCTION ofarm.take_tenant_write_lock()
RETURNS pg_catalog.void
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
        bound_tenant_id pg_catalog.uuid;
        bound_lock_key pg_catalog.int8;
    BEGIN
        bound_tenant_id := ofarm.current_tenant_id();
        SELECT registry.advisory_lock_key
          INTO STRICT bound_lock_key
          FROM ofarm.tenant_registry AS registry
         WHERE registry.tenant_id = bound_tenant_id;
        PERFORM pg_catalog.pg_advisory_xact_lock(bound_lock_key);
    END';

REVOKE ALL PRIVILEGES ON FUNCTION ofarm.current_backend_start()
FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION ofarm.backend_incarnation_is_live(
    pg_catalog.int4, pg_catalog.timestamptz
) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION ofarm.purge_stale_tenant_context()
FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION ofarm.create_tenant_challenge()
FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION ofarm.take_tenant_write_lock()
FROM PUBLIC;

GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE ofarm.tenant_binding_context TO ofarm_binder;
GRANT SELECT (
    tenant_id,
    record_id,
    record_kind,
    payload,
    batch_id,
    batch_full_xid
) ON TABLE ofarm.kernel_record TO ofarm_graph_validator;
GRANT SELECT (
    tenant_id,
    dst_record_id,
    edge_kind,
    batch_id,
    batch_full_xid
) ON TABLE ofarm.kernel_edge TO ofarm_graph_validator;

GRANT EXECUTE ON FUNCTION ofarm.current_backend_start()
TO ofarm_binder;
GRANT SELECT ON TABLE
    ofarm.tenant_binder_instance,
    ofarm.tenant_capability_verification_key,
    ofarm.tenant_capability_key_lifecycle,
    ofarm.tenant_capability_keyring,
    ofarm.principal_binding,
    ofarm.principal_binding_lifecycle,
    ofarm.principal_binding_current,
    ofarm.tenant_registry
TO ofarm_admission_lock_owner;
GRANT EXECUTE ON FUNCTION ofarm.backend_incarnation_is_live(
    pg_catalog.int4, pg_catalog.timestamptz
) TO ofarm_binder;
GRANT EXECUTE ON FUNCTION ofarm.purge_stale_tenant_context()
TO ofarm_binder;
GRANT EXECUTE ON FUNCTION ofarm.create_tenant_challenge()
TO ofarm_app, ofarm_worker;
GRANT EXECUTE ON FUNCTION ofarm.current_tenant_id()
TO ofarm_app, ofarm_worker;
GRANT EXECUTE ON FUNCTION ofarm.current_tenant_id()
TO ofarm_graph_validator;
GRANT EXECUTE ON FUNCTION ofarm.take_tenant_write_lock()
TO ofarm_app, ofarm_worker;

GRANT EXECUTE ON FUNCTION ofarm.current_tenant_id()
TO ofarm_tenant_lock_owner;
GRANT SELECT (
    tenant_id, advisory_lock_key
) ON TABLE ofarm.tenant_registry TO ofarm_tenant_lock_owner;

CREATE FUNCTION ofarm.verify_tenant_structure()
RETURNS TABLE (
    structurally_compatible pg_catalog.bool,
    tenant_context_contract_digest pg_catalog.text,
    difference_count pg_catalog.int4,
    structural_catalog_digest pg_catalog.text,
    relation_inventory_digest pg_catalog.text,
    provisioning_spec_digest pg_catalog.text,
    migration_service_identity pg_catalog.text,
    migration_head_version pg_catalog.int4,
    applied_prefix_digest pg_catalog.text,
    migration_row_count pg_catalog.int8,
    breakglass_login_present pg_catalog.bool
)
LANGUAGE plpgsql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
SET quote_all_identifiers = off
AS 'DECLARE
        differences pg_catalog.text[] := ARRAY[]::pg_catalog.text[];
        expected_relations pg_catalog.text[] := ARRAY[
            ''derived_dependency_index'',
            ''derived_materialization'',
            ''export_artifact'',
            ''governed_write_batch'',
            ''kernel_edge'',
            ''kernel_gate_log'',
            ''kernel_idempotency'',
            ''kernel_record'',
            ''kernel_record_reference'',
            ''principal_binding'',
            ''principal_binding_current'',
            ''principal_binding_lifecycle'',
            ''reference_snapshot_data'',
            ''runtime_bundle'',
            ''runtime_bundle_component'',
            ''runtime_content_blob'',
            ''runtime_tenant_content_blob'',
            ''runtime_trace'',
            ''schema_migration'',
            ''tenant_binder_instance'',
            ''tenant_binding_context'',
            ''tenant_capability_key_lifecycle'',
            ''tenant_capability_keyring'',
            ''tenant_capability_verification_key'',
            ''tenant_registry''
        ]::pg_catalog.text[];
        expected_tenant_relations pg_catalog.text[] := ARRAY[
            ''derived_dependency_index'',
            ''derived_materialization'',
            ''export_artifact'',
            ''governed_write_batch'',
            ''kernel_edge'',
            ''kernel_gate_log'',
            ''kernel_idempotency'',
            ''kernel_record'',
            ''kernel_record_reference'',
            ''reference_snapshot_data'',
            ''runtime_bundle'',
            ''runtime_bundle_component'',
            ''runtime_tenant_content_blob'',
            ''runtime_trace''
        ]::pg_catalog.text[];
        observed_relations pg_catalog.text[];
        observed_relation_posture pg_catalog.text[];
        observed_tenant_relations pg_catalog.text[];
        observed_domains pg_catalog.text[];
        observed_routines pg_catalog.text[];
        observed_roles pg_catalog.text[];
        observed_memberships pg_catalog.text[];
        observed_database_inventory pg_catalog.text[];
        observed_schema_inventory pg_catalog.text[];
        observed_relation_inventory pg_catalog.text;
        observed_provisioning_digest pg_catalog.text;
        observed_service_identity pg_catalog.text;
        observed_head_version pg_catalog.int4;
        observed_prefix_digest pg_catalog.text;
        observed_migration_count pg_catalog.int8;
        observed_structural_catalog_digest pg_catalog.text;
        observed_breakglass pg_catalog.bool;
        guarded_relation_count pg_catalog.int8;
        graph_constraint_count pg_catalog.int8;
        policy_count pg_catalog.int8;
        invalid_policy_count pg_catalog.int8;
        database_exact pg_catalog.bool;
        unexpected_extension_count pg_catalog.int8;
        large_object_metadata_count pg_catalog.int8;
        large_object_routine_acl_count pg_catalog.int8;
        invalid_large_object_routine_acl_count pg_catalog.int8;
        backend_statistics_view_count pg_catalog.int8;
        invalid_backend_statistics_view_count pg_catalog.int8;
        backend_statistics_view_acl_count pg_catalog.int8;
        invalid_backend_statistics_view_acl_count pg_catalog.int8;
        observed_backend_statistics_routines pg_catalog.text[];
        backend_statistics_routine_acl_count pg_catalog.int8;
        invalid_backend_statistics_routine_acl_count pg_catalog.int8;
        logical_replication_object_count pg_catalog.int8;
        domain_constraint_count pg_catalog.int8;
        invalid_domain_constraint_count pg_catalog.int8;
        invalid_index_collation_count pg_catalog.int8;
        relation_acl_count pg_catalog.int8;
        invalid_relation_acl_count pg_catalog.int8;
        column_acl_count pg_catalog.int8;
        invalid_column_acl_count pg_catalog.int8;
        invalid_cluster_database_access_count pg_catalog.int8;
        unexpected_global_object_count pg_catalog.int8;
        role_name pg_catalog.text;
        relation_name pg_catalog.text;
    BEGIN
        IF SESSION_USER NOT IN (''ofarm_readiness'', ''ofarm_migrator'') THEN
            RAISE EXCEPTION USING
                ERRCODE = ''42501'',
                MESSAGE = ''tenant structure verification caller differs'';
        END IF;

        SELECT pg_catalog.array_agg(
                   role.rolname::pg_catalog.text || '':'' ||
                   role.rolsuper::pg_catalog.text || '':'' ||
                   role.rolcreatedb::pg_catalog.text || '':'' ||
                   role.rolcreaterole::pg_catalog.text || '':'' ||
                   role.rolreplication::pg_catalog.text || '':'' ||
                   role.rolcanlogin::pg_catalog.text || '':'' ||
                   role.rolinherit::pg_catalog.text || '':'' ||
                   role.rolbypassrls::pg_catalog.text || '':'' ||
                   role.rolconnlimit::pg_catalog.text
                   ORDER BY role.rolname
               )
         INTO observed_roles
          FROM pg_catalog.pg_roles AS role
         WHERE role.rolname OPERATOR(pg_catalog.~) ''^ofarm_''
            OR role.rolname = ''pg_read_all_stats'';
        IF observed_roles IS DISTINCT FROM ARRAY[
            ''ofarm_admission_lock_owner:false:false:false:false:false:false:false:-1'',
            ''ofarm_app:false:false:false:false:true:true:false:24'',
            ''ofarm_backend_observer:false:false:false:false:false:true:false:-1'',
            ''ofarm_binder:false:false:false:false:false:false:true:-1'',
            ''ofarm_capability_key_control_login:false:false:false:false:true:true:false:1'',
            ''ofarm_capability_key_controller:false:false:false:false:false:false:false:-1'',
            ''ofarm_crypto_installer:true:false:false:false:false:false:false:-1'',
            ''ofarm_graph_validator:false:false:false:false:false:false:false:-1'',
            ''ofarm_identity_control_login:false:false:false:false:true:true:false:1'',
            ''ofarm_identity_writer:false:false:false:false:false:false:false:-1'',
            ''ofarm_migrator:false:false:false:false:true:false:false:2'',
            ''ofarm_owner:false:false:false:false:false:false:false:-1'',
            ''ofarm_readiness:false:false:false:false:true:true:false:2'',
            ''ofarm_tenant_control_login:false:false:false:false:true:true:false:1'',
            ''ofarm_tenant_lock_owner:false:false:false:false:false:false:false:-1'',
            ''ofarm_tenant_migration_lock_owner:false:false:false:false:false:false:false:-1'',
            ''ofarm_tenant_registrar:false:false:false:false:false:false:false:-1'',
            ''ofarm_worker:false:false:false:false:true:true:false:12'',
            ''pg_read_all_stats:false:false:false:false:false:true:false:-1''
        ]::pg_catalog.text[] THEN
            differences := pg_catalog.array_append(
                differences, ''role attribute inventory differs''
            );
        END IF;

        SELECT pg_catalog.array_agg(
                   granted.rolname::pg_catalog.text || ''>'' ||
                   member.rolname::pg_catalog.text || '':'' ||
                   membership.inherit_option::pg_catalog.text || '':'' ||
                   membership.set_option::pg_catalog.text || '':'' ||
                   membership.admin_option::pg_catalog.text
                   ORDER BY granted.rolname, member.rolname
               )
          INTO observed_memberships
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted
            ON granted.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member
            ON member.oid = membership.member
         WHERE granted.rolname OPERATOR(pg_catalog.~) ''^ofarm_''
            OR member.rolname OPERATOR(pg_catalog.~) ''^ofarm_''
            OR member.rolname = ''pg_read_all_stats'';
        IF observed_memberships IS DISTINCT FROM ARRAY[
            ''ofarm_capability_key_controller>ofarm_capability_key_control_login:true:false:false'',
            ''ofarm_identity_writer>ofarm_identity_control_login:true:false:false'',
            ''ofarm_owner>ofarm_migrator:false:true:false'',
            ''ofarm_tenant_registrar>ofarm_tenant_control_login:true:false:false'',
            ''pg_read_all_stats>ofarm_backend_observer:true:false:false''
        ]::pg_catalog.text[] THEN
            differences := pg_catalog.array_append(
                differences, ''role membership inventory differs''
            );
        END IF;

        SELECT
            database.encoding = pg_catalog.pg_char_to_encoding(''UTF8'')
            AND database.datlocprovider = ''b''
            AND database.datcollate = ''C''
            AND database.datctype = ''C''
            AND database.datlocale = ''C''
            AND database.daticurules IS NULL
            AND database.datcollversion = ''1''
          INTO database_exact
          FROM pg_catalog.pg_database AS database
         WHERE database.datname = pg_catalog.current_database();
        IF database_exact IS DISTINCT FROM true THEN
            differences := pg_catalog.array_append(
                differences, ''database equality posture differs''
            );
        END IF;

        SELECT pg_catalog.array_agg(
                   database.datname::pg_catalog.text
                   ORDER BY database.datname::pg_catalog.text
                            COLLATE pg_catalog."C"
               )
          INTO observed_database_inventory
          FROM pg_catalog.pg_database AS database;
        IF observed_database_inventory IS DISTINCT FROM ARRAY[
            ''ofarm_tenant'', ''postgres'', ''template0'', ''template1''
        ]::pg_catalog.text[] THEN
            differences := pg_catalog.array_append(
                differences, ''cluster database inventory differs''
            );
        END IF;

        SELECT pg_catalog.array_agg(
                   namespace.nspname::pg_catalog.text
                   ORDER BY namespace.nspname::pg_catalog.text
                            COLLATE pg_catalog."C"
               )
          INTO observed_schema_inventory
          FROM pg_catalog.pg_namespace AS namespace;
        IF observed_schema_inventory IS DISTINCT FROM ARRAY[
            ''information_schema'',
            ''ofarm'',
            ''ofarm_crypto'',
            ''ofarm_infrastructure'',
            ''pg_catalog'',
            ''pg_toast'',
            ''public''
        ]::pg_catalog.text[] THEN
            differences := pg_catalog.array_append(
                differences, ''database schema inventory differs''
            );
        END IF;

        SELECT pg_catalog.count(*)
          INTO invalid_cluster_database_access_count
          FROM pg_catalog.pg_roles AS role
          CROSS JOIN pg_catalog.pg_database AS database
         WHERE role.rolname OPERATOR(pg_catalog.~) ''^ofarm_''
           AND role.rolcanlogin
           AND (
                pg_catalog.has_database_privilege(
                    role.oid, database.oid, ''CONNECT''
                ) IS DISTINCT FROM (database.datname = ''ofarm_tenant'')
                OR pg_catalog.has_database_privilege(
                    role.oid, database.oid, ''TEMPORARY''
                ) IS DISTINCT FROM false
           );
        IF invalid_cluster_database_access_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''OFARM LOGIN cross-database access differs''
            );
        END IF;

        SELECT pg_catalog.count(*)
          INTO unexpected_global_object_count
          FROM pg_catalog.pg_extension AS extension
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = extension.extnamespace
          JOIN pg_catalog.pg_roles AS owner
            ON owner.oid = extension.extowner
         WHERE extension.extname = ''ofarm_ed25519''
           AND extension.extversion = ''1.0''
           AND namespace.nspname = ''ofarm_crypto''
           AND owner.rolname = ''ofarm_crypto_installer''
           AND NOT extension.extrelocatable
           AND extension.extconfig IS NULL
           AND extension.extcondition IS NULL;
        IF unexpected_global_object_count <> 1 THEN
            differences := pg_catalog.array_append(
                differences, ''native verifier extension identity differs''
            );
        END IF;

        SELECT
            (SELECT pg_catalog.count(*)
               FROM pg_catalog.pg_extension AS extension
               JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = extension.extnamespace
               JOIN pg_catalog.pg_roles AS owner
                 ON owner.oid = extension.extowner
              WHERE NOT (
                    extension.extname = ''plpgsql''
                    AND extension.extversion = ''1.0''
                    AND namespace.nspname = ''pg_catalog''
                    AND owner.rolsuper
                    AND NOT extension.extrelocatable
                    AND extension.extconfig IS NULL
                    AND extension.extcondition IS NULL
              )
                AND NOT (
                    extension.extname = ''ofarm_ed25519''
                    AND extension.extversion = ''1.0''
                    AND namespace.nspname = ''ofarm_crypto''
                    AND owner.rolname = ''ofarm_crypto_installer''
                    AND NOT extension.extrelocatable
                    AND extension.extconfig IS NULL
                    AND extension.extcondition IS NULL
              ))
            + (SELECT pg_catalog.count(*)
                 FROM pg_catalog.pg_event_trigger)
            + (SELECT pg_catalog.count(*)
                 FROM pg_catalog.pg_publication)
            + (SELECT pg_catalog.count(*)
                 FROM pg_catalog.pg_subscription)
            + (SELECT pg_catalog.count(*)
                 FROM pg_catalog.pg_foreign_data_wrapper)
            + (SELECT pg_catalog.count(*)
                 FROM pg_catalog.pg_foreign_server)
            + (SELECT pg_catalog.count(*)
                 FROM pg_catalog.pg_largeobject_metadata)
            + (SELECT pg_catalog.count(*)
                 FROM pg_catalog.pg_transform)
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
                WHERE tablespace.spcname NOT IN (''pg_default'', ''pg_global''))
            + (SELECT pg_catalog.count(*)
                 FROM pg_catalog.pg_replication_slots)
            + (SELECT pg_catalog.count(*)
                 FROM pg_catalog.pg_prepared_xacts)
          INTO unexpected_global_object_count;
        IF unexpected_global_object_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''unexpected database or cluster object is present''
            );
        END IF;

        -- PREPARED_TRANSACTION_STARTUP_POSTURE_V1
        IF pg_catalog.current_setting(
                ''max_prepared_transactions''
           )::pg_catalog.int4 <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''prepared transaction capacity differs''
            );
        END IF;

        SELECT pg_catalog.array_agg(class.relname::pg_catalog.text ORDER BY class.relname),
               ''sha256:'' || pg_catalog.encode(
                    pg_catalog.sha256(
                        pg_catalog.convert_to(
                            pg_catalog.string_agg(
                                class.relname::pg_catalog.text || '':'' ||
                                class.relkind::pg_catalog.text || '':'' ||
                                class.relpersistence::pg_catalog.text || '':'' ||
                                class.relrowsecurity::pg_catalog.text || '':'' ||
                                class.relforcerowsecurity::pg_catalog.text,
                                '','' ORDER BY class.relname
                            ),
                            ''UTF8''
                        )
                    ),
                    ''hex''
               )
          INTO observed_relations, observed_relation_inventory
          FROM pg_catalog.pg_class AS class
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = class.relnamespace
         WHERE namespace.nspname = ''ofarm''
           AND class.relkind IN (''r'', ''p'');
        IF observed_relations IS DISTINCT FROM expected_relations THEN
            differences := pg_catalog.array_append(
                differences, ''relation inventory differs''
            );
        END IF;

        SELECT pg_catalog.array_agg(
                   class.relname::pg_catalog.text || '':'' ||
                   class.relkind::pg_catalog.text || '':'' ||
                   class.relpersistence::pg_catalog.text || '':'' ||
                   owner.rolname::pg_catalog.text || '':'' ||
                   class.relrowsecurity::pg_catalog.text || '':'' ||
                   class.relforcerowsecurity::pg_catalog.text
                   ORDER BY class.relname
               )
          INTO observed_relation_posture
          FROM pg_catalog.pg_class AS class
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = class.relnamespace
          JOIN pg_catalog.pg_roles AS owner ON owner.oid = class.relowner
         WHERE namespace.nspname = ''ofarm''
           AND class.relkind IN (''r'', ''p'');
        IF observed_relation_posture IS DISTINCT FROM ARRAY[
            ''derived_dependency_index:r:p:ofarm_owner:true:true'',
            ''derived_materialization:r:p:ofarm_owner:true:true'',
            ''export_artifact:r:p:ofarm_owner:true:true'',
            ''governed_write_batch:r:p:ofarm_owner:true:true'',
            ''kernel_edge:r:p:ofarm_owner:true:true'',
            ''kernel_gate_log:r:p:ofarm_owner:true:true'',
            ''kernel_idempotency:r:p:ofarm_owner:true:true'',
            ''kernel_record:r:p:ofarm_owner:true:true'',
            ''kernel_record_reference:r:p:ofarm_owner:true:true'',
            ''principal_binding:r:p:ofarm_owner:false:false'',
            ''principal_binding_current:r:p:ofarm_owner:false:false'',
            ''principal_binding_lifecycle:r:p:ofarm_owner:false:false'',
            ''reference_snapshot_data:r:p:ofarm_owner:true:true'',
            ''runtime_bundle:r:p:ofarm_owner:true:true'',
            ''runtime_bundle_component:r:p:ofarm_owner:true:true'',
            ''runtime_content_blob:r:p:ofarm_owner:false:false'',
            ''runtime_tenant_content_blob:r:p:ofarm_owner:true:true'',
            ''runtime_trace:r:p:ofarm_owner:true:true'',
            ''schema_migration:r:p:ofarm_owner:false:false'',
            ''tenant_binder_instance:r:p:ofarm_owner:false:false'',
            ''tenant_binding_context:r:u:ofarm_owner:false:false'',
            ''tenant_capability_key_lifecycle:r:p:ofarm_owner:false:false'',
            ''tenant_capability_keyring:r:p:ofarm_owner:false:false'',
            ''tenant_capability_verification_key:r:p:ofarm_owner:false:false'',
            ''tenant_registry:r:p:ofarm_owner:false:false''
        ]::pg_catalog.text[] THEN
            differences := pg_catalog.array_append(
                differences, ''relation owner or persistence differs''
            );
        END IF;

        SELECT pg_catalog.array_agg(class.relname::pg_catalog.text ORDER BY class.relname)
          INTO observed_tenant_relations
          FROM pg_catalog.pg_class AS class
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = class.relnamespace
         WHERE namespace.nspname = ''ofarm''
           AND class.relkind IN (''r'', ''p'')
           AND class.relrowsecurity
           AND class.relforcerowsecurity;
        IF observed_tenant_relations IS DISTINCT FROM expected_tenant_relations THEN
            differences := pg_catalog.array_append(
                differences, ''forced RLS inventory differs''
            );
        END IF;

        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE policy.polname <> ''tenant_isolation''
                      OR policy.polcmd <> ''*''
                      OR NOT policy.polpermissive
                      OR (
                        SELECT pg_catalog.array_agg(role.rolname ORDER BY role.rolname)
                          FROM pg_catalog.unnest(policy.polroles) AS member(role_oid)
                          JOIN pg_catalog.pg_roles AS role ON role.oid = member.role_oid
                      ) IS DISTINCT FROM CASE
                            WHEN class.relname IN (''kernel_edge'', ''kernel_record'')
                            THEN ARRAY[
                                ''ofarm_app'',
                                ''ofarm_graph_validator'',
                                ''ofarm_worker''
                            ]::pg_catalog.name[]
                            ELSE ARRAY[
                                ''ofarm_app'', ''ofarm_worker''
                            ]::pg_catalog.name[]
                        END
                      OR pg_catalog.pg_get_expr(
                            policy.polqual, policy.polrelid
                         ) <> ''(tenant_id = ofarm.current_tenant_id())''
                      OR pg_catalog.pg_get_expr(
                            policy.polwithcheck, policy.polrelid
                         ) <> ''(tenant_id = ofarm.current_tenant_id())''
               )
          INTO policy_count, invalid_policy_count
          FROM pg_catalog.pg_policy AS policy
          JOIN pg_catalog.pg_class AS class ON class.oid = policy.polrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = class.relnamespace
         WHERE namespace.nspname = ''ofarm'';
        IF policy_count <> 14 OR invalid_policy_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''RLS policy inventory or expression differs''
            );
        END IF;

        SELECT pg_catalog.array_agg(type.typname::pg_catalog.text ORDER BY type.typname)
          INTO observed_domains
          FROM pg_catalog.pg_type AS type
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = type.typnamespace
          JOIN pg_catalog.pg_collation AS governed_collation
            ON governed_collation.oid = type.typcollation
         WHERE namespace.nspname = ''ofarm''
           AND type.typtype = ''d''
           AND governed_collation.collname = ''C''
           AND governed_collation.collprovider = ''c''
           AND governed_collation.collisdeterministic;
        IF observed_domains IS DISTINCT FROM ARRAY[
            ''ascii_id'',
            ''idempotency_caller_key'',
            ''oidc_issuer'',
            ''oidc_subject'',
            ''runtime_logical_ref'',
            ''sha256_id'',
            ''tenant_local_ref'',
            ''tenant_ref''
        ]::pg_catalog.text[] THEN
            differences := pg_catalog.array_append(
                differences, ''identity domain collation differs''
            );
        END IF;

        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE NOT governed_constraint.convalidated
                      OR governed_constraint.contype <> ''c''
               )
          INTO domain_constraint_count, invalid_domain_constraint_count
          FROM pg_catalog.pg_constraint AS governed_constraint
          JOIN pg_catalog.pg_type AS type
            ON type.oid = governed_constraint.contypid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = type.typnamespace
         WHERE namespace.nspname = ''ofarm''
           AND type.typtype = ''d'';
        IF domain_constraint_count <> 8
           OR invalid_domain_constraint_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''identity domain constraint inventory differs''
            );
        END IF;

        SELECT pg_catalog.count(*)
          INTO invalid_index_collation_count
          FROM pg_catalog.pg_index AS governed_index
          JOIN pg_catalog.pg_class AS index_class
            ON index_class.oid = governed_index.indexrelid
          JOIN pg_catalog.pg_class AS table_class
            ON table_class.oid = governed_index.indrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = table_class.relnamespace
          CROSS JOIN LATERAL pg_catalog.unnest(
                governed_index.indcollation::pg_catalog.oid[]
          ) AS indexed_collation(collation_oid)
          JOIN pg_catalog.pg_collation AS governed_collation
            ON governed_collation.oid = indexed_collation.collation_oid
         WHERE namespace.nspname = ''ofarm''
           AND indexed_collation.collation_oid <> 0
           AND (
                governed_collation.collname <> ''C''
                OR governed_collation.collprovider <> ''c''
                OR NOT governed_collation.collisdeterministic
           );
        IF invalid_index_collation_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''identity index collation differs''
            );
        END IF;

        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE acl.grantee = 0 OR NOT (
                       (
                           grantee.rolname = ''ofarm_binder''
                           AND (
                               (class.relname = ''tenant_binding_context''
                                AND acl.privilege_type IN (
                                    ''SELECT'', ''INSERT'', ''UPDATE'', ''DELETE''
                                ))
                                OR
                                (class.relname IN (
                                    ''tenant_binder_instance'',
                                    ''tenant_capability_verification_key'',
                                    ''tenant_capability_key_lifecycle'',
                                    ''tenant_capability_keyring'',
                                    ''principal_binding'',
                                    ''principal_binding_lifecycle'',
                                    ''principal_binding_current'',
                                    ''tenant_registry''
                                ) AND acl.privilege_type = ''SELECT'')
                           )
                       )
                       OR
                       (
                           grantee.rolname = ''ofarm_admission_lock_owner''
                           AND (
                               (class.relname IN (
                                    ''tenant_binder_instance'',
                                    ''tenant_registry''
                                ) AND acl.privilege_type = ''SELECT'')
                               OR
                               (class.relname IN (
                                    ''tenant_capability_verification_key'',
                                    ''tenant_capability_key_lifecycle'',
                                    ''principal_binding'',
                                    ''principal_binding_lifecycle''
                                ) AND acl.privilege_type IN (''SELECT'', ''INSERT''))
                               OR
                               (class.relname IN (
                                    ''tenant_capability_keyring'',
                                    ''principal_binding_current''
                                ) AND acl.privilege_type IN (
                                    ''SELECT'', ''INSERT'', ''UPDATE'', ''DELETE''
                                ))
                           )
                       )
                       OR
                       (
                           grantee.rolname IN (''ofarm_app'', ''ofarm_worker'')
                           AND (
                               (class.relname = ''runtime_content_blob''
                                AND acl.privilege_type = ''SELECT'')
                               OR
                               (class.relname IN (
                                    ''runtime_tenant_content_blob'',
                                    ''runtime_bundle'',
                                    ''runtime_bundle_component'',
                                    ''governed_write_batch'',
                                    ''kernel_record'',
                                    ''kernel_edge'',
                                    ''kernel_gate_log'',
                                    ''kernel_idempotency'',
                                    ''reference_snapshot_data'',
                                    ''runtime_trace'',
                                    ''export_artifact'',
                                    ''kernel_record_reference''
                                ) AND acl.privilege_type IN (''SELECT'', ''INSERT''))
                               OR
                               (class.relname = ''derived_materialization''
                                AND acl.privilege_type IN (
                                    ''SELECT'', ''INSERT'', ''DELETE''
                                ))
                               OR
                               (class.relname = ''derived_dependency_index''
                                AND acl.privilege_type IN (
                                    ''SELECT'', ''INSERT'', ''UPDATE'', ''DELETE''
                                ))
                           )
                       )
                   ) OR acl.is_grantable
               )
          INTO relation_acl_count, invalid_relation_acl_count
          FROM pg_catalog.pg_class AS class
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = class.relnamespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(class.relacl) AS acl
          LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
         WHERE namespace.nspname = ''ofarm''
           AND class.relkind IN (''r'', ''p'')
           AND acl.grantee <> class.relowner;
        IF relation_acl_count <> 94 OR invalid_relation_acl_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''relation ACL inventory differs''
            );
        END IF;

        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE acl.grantee = 0 OR NOT (
                       (
                           grantee.rolname = ''ofarm_readiness''
                           AND class.relname = ''schema_migration''
                           AND attribute.attname IN (
                                ''version'',
                                ''filename'',
                                ''source_sha256'',
                                ''source_byte_length'',
                                ''applied_prefix_digest'',
                                ''service_identity'',
                                ''provisioning_spec_digest''
                           )
                           AND acl.privilege_type = ''SELECT''
                       )
                       OR
                       (
                           grantee.rolname = ''ofarm_graph_validator''
                           AND acl.privilege_type = ''SELECT''
                           AND (
                               (
                                   class.relname = ''kernel_record''
                                   AND attribute.attname IN (
                                        ''tenant_id'', ''record_id'', ''record_kind'',
                                        ''payload'', ''batch_id'', ''batch_full_xid''
                                   )
                               )
                               OR
                               (
                                   class.relname = ''kernel_edge''
                                   AND attribute.attname IN (
                                        ''tenant_id'', ''dst_record_id'', ''edge_kind'',
                                        ''batch_id'', ''batch_full_xid''
                                   )
                               )
                           )
                       )
                       OR
                       (
                           grantee.rolname = ''ofarm_tenant_lock_owner''
                           AND class.relname = ''tenant_registry''
                           AND attribute.attname IN (
                                ''tenant_id'', ''advisory_lock_key''
                           )
                           AND acl.privilege_type = ''SELECT''
                       )
                       OR
                       (
                           grantee.rolname IN (
                                ''ofarm_binder'', ''ofarm_admission_lock_owner''
                           )
                           AND class.relname = ''kernel_record''
                           AND attribute.attname IN (
                                ''tenant_id'', ''record_id'', ''record_kind'',
                                ''schema_digest'', ''payload_digest'',
                                ''party_state'', ''party_id''
                           )
                           AND acl.privilege_type = ''SELECT''
                       )
                       OR
                       (
                           grantee.rolname IN (''ofarm_app'', ''ofarm_worker'')
                           AND class.relname = ''derived_materialization''
                           AND attribute.attname IN (
                                ''freshness'', ''superseded_by''
                           )
                           AND acl.privilege_type = ''UPDATE''
                       )
                       OR
                       (
                           grantee.rolname = ''ofarm_admission_lock_owner''
                           AND class.relname =
                                ''tenant_capability_verification_key''
                           AND attribute.attname = ''kid''
                           AND acl.privilege_type = ''UPDATE''
                       )
                       OR
                       (
                           grantee.rolname = ''ofarm_binder''
                           AND acl.privilege_type = ''UPDATE''
                           AND (
                                (class.relname =
                                    ''tenant_capability_verification_key''
                                 AND attribute.attname = ''kid'')
                                OR
                                (class.relname = ''tenant_capability_keyring''
                                 AND attribute.attname = ''audience'')
                                OR
                                (class.relname = ''principal_binding_current''
                                 AND attribute.attname = ''subject'')
                           )
                       )
                   ) OR acl.is_grantable
               )
          INTO column_acl_count, invalid_column_acl_count
          FROM pg_catalog.pg_attribute AS attribute
          JOIN pg_catalog.pg_class AS class ON class.oid = attribute.attrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = class.relnamespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) AS acl
          LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
         WHERE namespace.nspname = ''ofarm''
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped;
        IF column_acl_count <> 42 OR invalid_column_acl_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''column ACL inventory differs''
            );
        END IF;

        SELECT pg_catalog.array_agg(
                   routine.proname::pg_catalog.text || ''('' ||
                   pg_catalog.pg_get_function_identity_arguments(routine.oid) ||
                   '')='' || owner.rolname::pg_catalog.text || '':'' ||
                   language.lanname::pg_catalog.text || '':'' ||
                   routine.prosecdef::pg_catalog.text || '':'' ||
                   routine.proisstrict::pg_catalog.text || '':'' ||
                   routine.proleakproof::pg_catalog.text || '':'' ||
                   routine.provolatile::pg_catalog.text || '':'' ||
                   routine.proparallel::pg_catalog.text || '':'' ||
                   COALESCE(
                       pg_catalog.array_to_string(routine.proconfig, '',''), ''''
                   ) || '':'' ||
                   pg_catalog.encode(
                       pg_catalog.sha256(
                           pg_catalog.convert_to(routine.prosrc, ''UTF8'')
                       ),
                       ''hex''
                   ) || '':'' ||
                   EXISTS (
                       SELECT 1
                         FROM pg_catalog.aclexplode(
                            COALESCE(
                                routine.proacl,
                                pg_catalog.acldefault(''f'', routine.proowner)
                            )
                         ) AS public_acl
                        WHERE public_acl.grantee = 0
                          AND public_acl.privilege_type = ''EXECUTE''
                   )::pg_catalog.text || '':'' ||
                   pg_catalog.has_function_privilege(
                       ''ofarm_app'', routine.oid, ''EXECUTE''
                   )::pg_catalog.text || '':'' ||
                   pg_catalog.has_function_privilege(
                       ''ofarm_worker'', routine.oid, ''EXECUTE''
                   )::pg_catalog.text || '':'' ||
                   pg_catalog.has_function_privilege(
                       ''ofarm_tenant_lock_owner'', routine.oid, ''EXECUTE''
                   )::pg_catalog.text || '':'' ||
                   pg_catalog.has_function_privilege(
                       ''ofarm_migrator'', routine.oid, ''EXECUTE''
                   )::pg_catalog.text || '':'' ||
                   pg_catalog.has_function_privilege(
                       ''ofarm_readiness'', routine.oid, ''EXECUTE''
                   )::pg_catalog.text
                   ORDER BY routine.proname,
                            pg_catalog.pg_get_function_identity_arguments(routine.oid)
               )
          INTO observed_routines
          FROM pg_catalog.pg_proc AS routine
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = routine.pronamespace
          JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
          JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
         WHERE namespace.nspname = ''ofarm''
           AND routine.proname = ANY (ARRAY[
                ''create_tenant_challenge'',
                ''current_tenant_id'',
                ''take_tenant_write_lock''
           ]::pg_catalog.text[]);
        IF observed_routines IS DISTINCT FROM ARRAY[
            ''create_tenant_challenge()=ofarm_binder:plpgsql:true:false:false:v:u:search_path=pg_catalog, pg_temp:da7cd7c1ac111700f4dcd9490d910770f7dec213a40dee1c533edccc8500dd56:false:true:true:false:false:false'',
            ''current_tenant_id()=ofarm_binder:plpgsql:true:false:false:s:u:search_path=pg_catalog, pg_temp:2dea636af9e5cd14b7fcb406fd556934ffd8ab408dae965aa318e4120beb0ab0:false:true:true:true:false:false'',
            ''take_tenant_write_lock()=ofarm_tenant_lock_owner:plpgsql:true:false:false:v:u:search_path=pg_catalog, pg_temp:38c75f051ee82b75c2e872fe2e191874e17984da7183add568f481d2eadb0de8:false:true:true:true:false:false''
        ]::pg_catalog.text[] THEN
            differences := pg_catalog.array_append(
                differences, ''sealed tenant routine inventory differs''
            );
        END IF;

        SELECT pg_catalog.count(*)
          INTO guarded_relation_count
          FROM pg_catalog.pg_trigger AS trigger
          JOIN pg_catalog.pg_class AS class ON class.oid = trigger.tgrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = class.relnamespace
         WHERE namespace.nspname = ''ofarm''
           AND trigger.tgname OPERATOR(pg_catalog.~) ''_reject_mutation$''
           AND NOT trigger.tgisinternal
           AND trigger.tgenabled = ''O'';
        IF guarded_relation_count <> 19 THEN
            differences := pg_catalog.array_append(
                differences, ''immutable relation guard inventory differs''
            );
        END IF;

        SELECT pg_catalog.count(*)
          INTO graph_constraint_count
          FROM pg_catalog.pg_trigger AS trigger
          JOIN pg_catalog.pg_class AS class ON class.oid = trigger.tgrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = class.relnamespace
         WHERE namespace.nspname = ''ofarm''
           AND trigger.tgname IN (
                ''kernel_edge_validate_promotion'',
                ''kernel_record_require_promotion''
           )
           AND trigger.tgconstraint <> 0
           AND trigger.tgdeferrable
           AND trigger.tginitdeferred;
        IF graph_constraint_count <> 2 THEN
            differences := pg_catalog.array_append(
                differences, ''deferred graph guards differ''
            );
        END IF;

        SELECT pg_catalog.count(*)
          INTO unexpected_extension_count
          FROM (
                SELECT extension.extname::pg_catalog.text
                  FROM pg_catalog.pg_extension AS extension
                 WHERE extension.extname NOT IN (''plpgsql'', ''ofarm_ed25519'')
                UNION ALL
                SELECT ''missing ofarm_ed25519''::pg_catalog.text
                 WHERE NOT EXISTS (
                    SELECT 1
                      FROM pg_catalog.pg_extension AS extension
                     WHERE extension.extname = ''ofarm_ed25519''
                 )
          ) AS invalid_extension;
        IF unexpected_extension_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''migration-owned extension inventory differs''
            );
        END IF;

        SELECT pg_catalog.count(*)
          INTO large_object_metadata_count
          FROM pg_catalog.pg_largeobject_metadata;
        IF large_object_metadata_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''large-object storage is present''
            );
        END IF;

        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE acl.grantee <> routine.proowner
                      OR acl.grantor <> routine.proowner
                      OR NOT owner.rolsuper
                      OR acl.privilege_type <> ''EXECUTE''
                      OR acl.is_grantable
               )
          INTO large_object_routine_acl_count,
               invalid_large_object_routine_acl_count
          FROM pg_catalog.pg_proc AS routine
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = routine.pronamespace
          JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
          CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(
                    routine.proacl,
                    pg_catalog.acldefault(''f'', routine.proowner)
                )
          ) AS acl
         WHERE namespace.nspname = ''pg_catalog''
           AND (
                pg_catalog.left(routine.proname::pg_catalog.text, 3) = ''lo_''
                OR routine.proname IN (''loread'', ''lowrite'')
           );
        IF large_object_routine_acl_count <> 20
           OR invalid_large_object_routine_acl_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''large-object routine ACL inventory differs''
            );
        END IF;

        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE class.relkind <> ''v''
                      OR class.relpersistence <> ''p''
                      OR NOT owner.rolsuper
                      OR class.relispartition
                      OR class.relrowsecurity
                      OR class.relforcerowsecurity
               )
          INTO backend_statistics_view_count,
               invalid_backend_statistics_view_count
          FROM pg_catalog.pg_class AS class
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = class.relnamespace
          JOIN pg_catalog.pg_roles AS owner ON owner.oid = class.relowner
         WHERE namespace.nspname = ''pg_catalog''
           AND class.relname = ''pg_stat_activity'';
        IF backend_statistics_view_count <> 1
           OR invalid_backend_statistics_view_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''backend-statistics view posture differs''
            );
        END IF;

        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE acl.grantor <> class.relowner
                      OR acl.is_grantable
                      OR NOT (
                           (
                               acl.grantee = class.relowner
                               AND acl.privilege_type IN (
                                   ''DELETE'',
                                   ''INSERT'',
                                   ''MAINTAIN'',
                                   ''REFERENCES'',
                                   ''SELECT'',
                                   ''TRIGGER'',
                                   ''TRUNCATE'',
                                   ''UPDATE''
                               )
                           )
                           OR (
                               grantee.rolname = ''ofarm_backend_observer''
                               AND acl.privilege_type = ''SELECT''
                           )
                      )
               )
          INTO backend_statistics_view_acl_count,
               invalid_backend_statistics_view_acl_count
          FROM pg_catalog.pg_class AS class
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = class.relnamespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(
                    class.relacl,
                    pg_catalog.acldefault(''r'', class.relowner)
                )
          ) AS acl
          LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
         WHERE namespace.nspname = ''pg_catalog''
           AND class.relname = ''pg_stat_activity''
           AND class.relkind = ''v'';
        IF backend_statistics_view_acl_count <> 9
           OR invalid_backend_statistics_view_acl_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''backend-statistics view ACL inventory differs''
            );
        END IF;

        SELECT pg_catalog.array_agg(
                   routine.proname::pg_catalog.text || ''('' ||
                       pg_catalog.oidvectortypes(routine.proargtypes) || '')''
                   ORDER BY
                       routine.proname COLLATE pg_catalog."C",
                       pg_catalog.oidvectortypes(routine.proargtypes)
                           COLLATE pg_catalog."C"
               )
          INTO observed_backend_statistics_routines
          FROM pg_catalog.pg_proc AS routine
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = routine.pronamespace
         WHERE namespace.nspname = ''pg_catalog''
           AND pg_catalog.left(
                   routine.proname::pg_catalog.text, 20
               ) IN (''pg_stat_get_activity'', ''pg_stat_get_backend_'');
        IF observed_backend_statistics_routines IS DISTINCT FROM ARRAY[
            ''pg_stat_get_activity(integer)'',
            ''pg_stat_get_backend_activity(integer)'',
            ''pg_stat_get_backend_activity_start(integer)'',
            ''pg_stat_get_backend_client_addr(integer)'',
            ''pg_stat_get_backend_client_port(integer)'',
            ''pg_stat_get_backend_dbid(integer)'',
            ''pg_stat_get_backend_idset()'',
            ''pg_stat_get_backend_pid(integer)'',
            ''pg_stat_get_backend_start(integer)'',
            ''pg_stat_get_backend_subxact(integer)'',
            ''pg_stat_get_backend_userid(integer)'',
            ''pg_stat_get_backend_wait_event(integer)'',
            ''pg_stat_get_backend_wait_event_type(integer)'',
            ''pg_stat_get_backend_xact_start(integer)''
        ]::pg_catalog.text[] THEN
            differences := pg_catalog.array_append(
                differences, ''backend-statistics routine inventory differs''
            );
        END IF;

        SELECT pg_catalog.count(*),
               pg_catalog.count(*) FILTER (
                   WHERE acl.grantor <> routine.proowner
                      OR NOT owner.rolsuper
                      OR acl.privilege_type <> ''EXECUTE''
                      OR acl.is_grantable
                      OR NOT (
                           acl.grantee = routine.proowner
                           OR (
                               routine.proname = ''pg_stat_get_activity''
                               AND grantee.rolname = ''ofarm_backend_observer''
                           )
                      )
               )
          INTO backend_statistics_routine_acl_count,
               invalid_backend_statistics_routine_acl_count
          FROM pg_catalog.pg_proc AS routine
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = routine.pronamespace
          JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
          CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(
                    routine.proacl,
                    pg_catalog.acldefault(''f'', routine.proowner)
                )
          ) AS acl
          LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
         WHERE namespace.nspname = ''pg_catalog''
           AND pg_catalog.left(
                   routine.proname::pg_catalog.text, 20
               ) IN (''pg_stat_get_activity'', ''pg_stat_get_backend_'');
        IF backend_statistics_routine_acl_count <> 15
           OR invalid_backend_statistics_routine_acl_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences, ''backend-statistics routine ACL inventory differs''
            );
        END IF;

        SELECT
            (SELECT pg_catalog.count(*) FROM pg_catalog.pg_publication)
            + (
                SELECT pg_catalog.count(*)
                  FROM pg_catalog.pg_subscription AS subscription
                 WHERE subscription.subdbid = (
                        SELECT database.oid
                          FROM pg_catalog.pg_database AS database
                         WHERE database.datname = pg_catalog.current_database()
                 )
            )
            + (
                SELECT pg_catalog.count(*)
                  FROM pg_catalog.pg_replication_slots AS slot
                 WHERE slot.database = pg_catalog.current_database()
            )
            + (
                SELECT pg_catalog.count(*)
                  FROM pg_catalog.pg_stat_get_wal_senders()
            )
            + (
                SELECT pg_catalog.count(*)
                  FROM pg_catalog.pg_stat_get_wal_receiver() AS receiver
                 WHERE receiver.pid IS NOT NULL
            )
          INTO logical_replication_object_count;
        IF logical_replication_object_count <> 0 THEN
            differences := pg_catalog.array_append(
                differences,
                ''publication, subscription, replication slot, or live replica is present''
            );
        END IF;

        FOREACH role_name IN ARRAY ARRAY[
            ''ofarm_app'',
            ''ofarm_worker'',
            ''ofarm_readiness'',
            ''ofarm_tenant_registrar'',
            ''ofarm_identity_writer''
        ]::pg_catalog.text[] LOOP
            FOREACH relation_name IN ARRAY ARRAY[
                ''tenant_registry'',
                ''principal_binding'',
                ''principal_binding_lifecycle'',
                ''principal_binding_current'',
                ''tenant_binding_context''
            ]::pg_catalog.text[] LOOP
                IF pg_catalog.has_table_privilege(
                    role_name,
                    ''ofarm.'' || relation_name,
                    ''SELECT''
                ) OR pg_catalog.has_table_privilege(
                    role_name,
                    ''ofarm.'' || relation_name,
                    ''INSERT''
                ) OR pg_catalog.has_table_privilege(
                    role_name,
                    ''ofarm.'' || relation_name,
                    ''UPDATE''
                ) OR pg_catalog.has_table_privilege(
                    role_name,
                    ''ofarm.'' || relation_name,
                    ''DELETE''
                ) THEN
                    differences := pg_catalog.array_append(
                        differences,
                        role_name || '' has direct control-relation authority''
                    );
                END IF;
            END LOOP;
        END LOOP;

        SELECT pg_catalog.bool_or(role.rolcanlogin)
          INTO observed_breakglass
          FROM pg_catalog.pg_roles AS role
         WHERE role.rolname IN (
            ''ofarm_backup_reader'',
            ''ofarm_restore_operator'',
            ''ofarm_recovery_readiness''
         );
        observed_breakglass := COALESCE(observed_breakglass, false);
        IF observed_breakglass THEN
            differences := pg_catalog.array_append(
                differences, ''breakglass or recovery LOGIN is present''
            );
        END IF;

        SELECT pg_catalog.count(*),
               pg_catalog.max(migration.version),
               pg_catalog.max(migration.service_identity),
               pg_catalog.max(migration.provisioning_spec_digest),
               pg_catalog.max(migration.applied_prefix_digest)
          INTO observed_migration_count,
               observed_head_version,
               observed_service_identity,
               observed_provisioning_digest,
               observed_prefix_digest
          FROM ofarm.schema_migration AS migration;
        IF observed_migration_count <> 1
           OR observed_head_version <> 1
           OR observed_service_identity <> ''ofarm.tenant-postgresql.v1''
           OR observed_provisioning_digest <>
                ''sha256:5aea41d4e235d58c1b0f740983f6bd570751198008e0bf8c2a2bc6d6bdffd9bf''
           OR observed_prefix_digest !~ ''^sha256:[0-9a-f]{64}$'' THEN
            differences := pg_catalog.array_append(
                differences, ''migration 0001 ledger identity differs''
            );
        END IF;

        -- SCHEMA_LOCAL_CATALOG_CLASSIFIER_V1
        -- relation|pg_class|relnamespace|relname
        -- routine|pg_proc|pronamespace|proname
        -- type|pg_type|typnamespace|typname
        -- collation|pg_collation|collnamespace|collname
        -- operator|pg_operator|oprnamespace|oprname
        -- operator_class|pg_opclass|opcnamespace|opcname
        -- operator_family|pg_opfamily|opfnamespace|opfname
        -- conversion|pg_conversion|connamespace|conname
        -- text_search_config|pg_ts_config|cfgnamespace|cfgname
        -- text_search_dictionary|pg_ts_dict|dictnamespace|dictname
        -- text_search_parser|pg_ts_parser|prsnamespace|prsname
        -- text_search_template|pg_ts_template|tmplnamespace|tmplname
        -- statistics|pg_statistic_ext|stxnamespace|stxname
        WITH catalog_entry(category, object_identity, definition) AS (
            SELECT
                ''role'',
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
             WHERE role.rolname OPERATOR(pg_catalog.~) ''^ofarm_''
                OR role.rolname = ''pg_read_all_stats''

            UNION ALL
            SELECT
                ''membership'',
                granted.rolname::pg_catalog.text || '':'' ||
                    member.rolname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    membership.inherit_option,
                    membership.set_option,
                    membership.admin_option
                )::pg_catalog.text
              FROM pg_catalog.pg_auth_members AS membership
              JOIN pg_catalog.pg_roles AS granted
                ON granted.oid = membership.roleid
              JOIN pg_catalog.pg_roles AS member
                ON member.oid = membership.member
             WHERE granted.rolname OPERATOR(pg_catalog.~) ''^ofarm_''
                OR member.rolname OPERATOR(pg_catalog.~) ''^ofarm_''
                OR member.rolname = ''pg_read_all_stats''

            UNION ALL
            SELECT
                ''database'',
                database.datname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    owner.rolname,
                    database.datallowconn,
                    database.datconnlimit,
                    database.datistemplate
                )::pg_catalog.text
              FROM pg_catalog.pg_database AS database
              JOIN pg_catalog.pg_roles AS owner ON owner.oid = database.datdba
             WHERE database.datname = ''ofarm_tenant''

            UNION ALL
            SELECT
                ''database-acl'',
                database.datname::pg_catalog.text || '':'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
                    acl.privilege_type,
                pg_catalog.jsonb_build_array(
                    acl.is_grantable,
                    grantor.rolname
                )::pg_catalog.text
              FROM pg_catalog.pg_database AS database
              CROSS JOIN LATERAL pg_catalog.aclexplode(
                    COALESCE(
                        database.datacl,
                        pg_catalog.acldefault(''d'', database.datdba)
                    )
              ) AS acl
              LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
              JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
             WHERE database.datname = ''ofarm_tenant''

            UNION ALL
            SELECT
                ''role-setting'',
                CASE WHEN role_setting.setdatabase = 0 THEN ''ALL_DATABASES''
                     ELSE database.datname::pg_catalog.text END || '':'' ||
                    CASE WHEN role_setting.setrole = 0 THEN ''ALL_ROLES''
                         ELSE role.rolname::pg_catalog.text END || '':'' ||
                    setting.value,
                ''[]''::pg_catalog.text
              FROM pg_catalog.pg_db_role_setting AS role_setting
              LEFT JOIN pg_catalog.pg_database AS database
                ON database.oid = role_setting.setdatabase
              LEFT JOIN pg_catalog.pg_roles AS role
                ON role.oid = role_setting.setrole
              CROSS JOIN LATERAL pg_catalog.unnest(
                    role_setting.setconfig
              ) AS setting(value)
             WHERE database.datname = ''ofarm_tenant''
                OR role.rolname OPERATOR(pg_catalog.~) ''^ofarm_''
                OR (
                    role_setting.setdatabase = 0
                    AND role_setting.setrole = 0
                )

            UNION ALL
            SELECT
                ''schema'',
                namespace.nspname::pg_catalog.text,
                pg_catalog.jsonb_build_array(owner.rolname)::pg_catalog.text
              FROM pg_catalog.pg_namespace AS namespace
              JOIN pg_catalog.pg_roles AS owner ON owner.oid = namespace.nspowner
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''schema-acl'',
                namespace.nspname::pg_catalog.text || '':'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
                    acl.privilege_type,
                pg_catalog.jsonb_build_array(
                    acl.is_grantable,
                    grantor.rolname
                )::pg_catalog.text
              FROM pg_catalog.pg_namespace AS namespace
              CROSS JOIN LATERAL pg_catalog.aclexplode(
                    COALESCE(
                        namespace.nspacl,
                        pg_catalog.acldefault(''n'', namespace.nspowner)
                    )
              ) AS acl
              LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
              JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''type'',
                namespace.nspname::pg_catalog.text || ''.'' ||
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
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''collation'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    governed_collation.collname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    owner.rolname,
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
              JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = governed_collation.collowner
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''operator'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    governed_operator.oprname::pg_catalog.text || ''('' ||
                    pg_catalog.format_type(governed_operator.oprleft, NULL) || '','' ||
                    pg_catalog.format_type(governed_operator.oprright, NULL) || '')'',
                pg_catalog.jsonb_build_array(
                    owner.rolname,
                    governed_operator.oprkind,
                    governed_operator.oprcanmerge,
                    governed_operator.oprcanhash,
                    pg_catalog.format_type(governed_operator.oprresult, NULL),
                    governed_operator.oprcode::pg_catalog.regprocedure::pg_catalog.text,
                    governed_operator.oprrest::pg_catalog.regprocedure::pg_catalog.text,
                    governed_operator.oprjoin::pg_catalog.regprocedure::pg_catalog.text
                )::pg_catalog.text
              FROM pg_catalog.pg_operator AS governed_operator
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = governed_operator.oprnamespace
              JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = governed_operator.oprowner
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''operator_class'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    operator_class.opcname::pg_catalog.text || '':'' ||
                    access_method.amname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    owner.rolname,
                    operator_family_namespace.nspname,
                    operator_family.opfname,
                    operator_class.opcintype::pg_catalog.regtype::pg_catalog.text,
                    CASE WHEN operator_class.opckeytype = 0 THEN NULL
                         ELSE operator_class.opckeytype::pg_catalog.regtype::pg_catalog.text END,
                    operator_class.opcdefault
                )::pg_catalog.text
              FROM pg_catalog.pg_opclass AS operator_class
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = operator_class.opcnamespace
              JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = operator_class.opcowner
              JOIN pg_catalog.pg_am AS access_method
                ON access_method.oid = operator_class.opcmethod
              JOIN pg_catalog.pg_opfamily AS operator_family
                ON operator_family.oid = operator_class.opcfamily
              JOIN pg_catalog.pg_namespace AS operator_family_namespace
                ON operator_family_namespace.oid = operator_family.opfnamespace
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''operator_family'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    operator_family.opfname::pg_catalog.text || '':'' ||
                    access_method.amname::pg_catalog.text,
                pg_catalog.jsonb_build_array(owner.rolname)::pg_catalog.text
              FROM pg_catalog.pg_opfamily AS operator_family
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = operator_family.opfnamespace
              JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = operator_family.opfowner
              JOIN pg_catalog.pg_am AS access_method
                ON access_method.oid = operator_family.opfmethod
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''conversion'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    conversion.conname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    owner.rolname,
                    conversion.conforencoding,
                    conversion.contoencoding,
                    conversion.conproc::pg_catalog.regprocedure::pg_catalog.text,
                    conversion.condefault
                )::pg_catalog.text
              FROM pg_catalog.pg_conversion AS conversion
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = conversion.connamespace
              JOIN pg_catalog.pg_roles AS owner ON owner.oid = conversion.conowner
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''text_search_config'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    configuration.cfgname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    owner.rolname,
                    parser_namespace.nspname,
                    parser.prsname
                )::pg_catalog.text
              FROM pg_catalog.pg_ts_config AS configuration
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = configuration.cfgnamespace
              JOIN pg_catalog.pg_roles AS owner ON owner.oid = configuration.cfgowner
              JOIN pg_catalog.pg_ts_parser AS parser
                ON parser.oid = configuration.cfgparser
              JOIN pg_catalog.pg_namespace AS parser_namespace
                ON parser_namespace.oid = parser.prsnamespace
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''text_search_dictionary'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    dictionary.dictname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    owner.rolname,
                    template_namespace.nspname,
                    template.tmplname,
                    dictionary.dictinitoption
                )::pg_catalog.text
              FROM pg_catalog.pg_ts_dict AS dictionary
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = dictionary.dictnamespace
              JOIN pg_catalog.pg_roles AS owner ON owner.oid = dictionary.dictowner
              JOIN pg_catalog.pg_ts_template AS template
                ON template.oid = dictionary.dicttemplate
              JOIN pg_catalog.pg_namespace AS template_namespace
                ON template_namespace.oid = template.tmplnamespace
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''text_search_parser'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    parser.prsname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    parser.prsstart::pg_catalog.regprocedure::pg_catalog.text,
                    parser.prstoken::pg_catalog.regprocedure::pg_catalog.text,
                    parser.prsend::pg_catalog.regprocedure::pg_catalog.text,
                    parser.prsheadline::pg_catalog.regprocedure::pg_catalog.text,
                    parser.prslextype::pg_catalog.regprocedure::pg_catalog.text
                )::pg_catalog.text
              FROM pg_catalog.pg_ts_parser AS parser
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = parser.prsnamespace
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''text_search_template'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    template.tmplname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    template.tmplinit::pg_catalog.regprocedure::pg_catalog.text,
                    template.tmpllexize::pg_catalog.regprocedure::pg_catalog.text
                )::pg_catalog.text
              FROM pg_catalog.pg_ts_template AS template
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = template.tmplnamespace
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''statistics'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    statistics.stxname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    owner.rolname,
                    statistics.stxrelid::pg_catalog.regclass::pg_catalog.text,
                    statistics.stxkeys::pg_catalog.text,
                    statistics.stxkind,
                    pg_catalog.pg_get_expr(
                        statistics.stxexprs, statistics.stxrelid
                    )
                )::pg_catalog.text
              FROM pg_catalog.pg_statistic_ext AS statistics
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = statistics.stxnamespace
              JOIN pg_catalog.pg_roles AS owner ON owner.oid = statistics.stxowner
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''relation'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    class.relname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    owner.rolname,
                    class.relkind,
                    class.relpersistence,
                    class.relrowsecurity,
                    class.relforcerowsecurity,
                    EXISTS (
                        SELECT 1
                          FROM pg_catalog.pg_rewrite AS relation_rule
                         WHERE relation_rule.ev_class = class.oid
                    ),
                    class.relreplident,
                    class.reloptions
                )::pg_catalog.text
              FROM pg_catalog.pg_class AS class
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = class.relnamespace
              JOIN pg_catalog.pg_roles AS owner ON owner.oid = class.relowner
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )
               AND class.relkind IN (''r'', ''p'', ''S'', ''v'', ''m'', ''f'')

            UNION ALL
            -- GOVERNED_RELATION_REWRITE_RULE_V1
            SELECT
                ''rewrite-rule'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    class.relname::pg_catalog.text || '':'' ||
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
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )
               AND class.relkind IN (''r'', ''p'', ''v'', ''m'', ''f'')

            UNION ALL
            SELECT
                ''column'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    class.relname::pg_catalog.text || '':'' ||
                    attribute.attnum::pg_catalog.text || '':'' ||
                    attribute.attname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    pg_catalog.format_type(attribute.atttypid, attribute.atttypmod),
                    attribute.attnotnull,
                    attribute.attidentity,
                    attribute.attgenerated,
                    attribute.attstorage,
                    attribute.attcompression,
                    attribute.attstattarget,
                    attribute.attoptions,
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
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )
               AND class.relkind IN (''r'', ''p'', ''S'', ''v'', ''m'', ''f'')
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped

            UNION ALL
            SELECT
                ''constraint'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    CASE WHEN governed_constraint.conrelid = 0
                         THEN governed_type.typname::pg_catalog.text
                         ELSE governed_relation.relname::pg_catalog.text END ||
                    '':'' || governed_constraint.conname::pg_catalog.text,
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
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''index'',
                namespace.nspname::pg_catalog.text || ''.'' ||
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
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''trigger'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    class.relname::pg_catalog.text || '':'' ||
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
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )
               AND NOT trigger.tgisinternal

            UNION ALL
            SELECT
                ''policy'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    class.relname::pg_catalog.text || '':'' ||
                    policy.polname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    policy.polpermissive,
                    policy.polcmd,
                    ARRAY(
                        SELECT CASE WHEN policy_role.oid = 0 THEN ''PUBLIC''
                                    ELSE governed_role.rolname::pg_catalog.text END
                          FROM pg_catalog.unnest(policy.polroles) AS policy_role(oid)
                          LEFT JOIN pg_catalog.pg_roles AS governed_role
                            ON governed_role.oid = policy_role.oid
                         ORDER BY
                            (CASE WHEN policy_role.oid = 0 THEN ''PUBLIC''
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
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''routine'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    routine.proname::pg_catalog.text || ''('' ||
                    pg_catalog.pg_get_function_identity_arguments(routine.oid) || '')'',
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
                    routine.pronargs,
                    routine.pronargdefaults,
                    pg_catalog.pg_get_function_arguments(routine.oid),
                    pg_catalog.pg_get_function_identity_arguments(routine.oid),
                    pg_catalog.pg_get_function_result(routine.oid),
                    routine.proconfig,
                    routine.procost,
                    routine.prorows,
                    CASE WHEN routine.prosupport = 0 THEN NULL
                         ELSE routine.prosupport::pg_catalog.regprocedure::pg_catalog.text
                    END,
                    routine.probin,
                    routine.prosqlbody IS NULL,
                    routine.proacl IS NULL,
                    CASE WHEN namespace.nspname = ''ofarm''
                              AND routine.proname = ''verify_tenant_structure''
                              AND pg_catalog.pg_get_function_identity_arguments(
                                    routine.oid
                              ) = ''''
                         THEN ''SELF_SOURCE_EXCLUDED''
                         ELSE routine.prosrc END
                )::pg_catalog.text
              FROM pg_catalog.pg_proc AS routine
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = routine.pronamespace
              JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
              JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''routine-acl'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    routine.proname::pg_catalog.text || ''('' ||
                    pg_catalog.pg_get_function_identity_arguments(routine.oid) || ''):'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
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
                        pg_catalog.acldefault(''f'', routine.proowner)
                    )
              ) AS acl
              LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
              JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''type-acl'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    type.typname::pg_catalog.text || '':'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
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
                        pg_catalog.acldefault(''T'', type.typowner)
                    )
              ) AS acl
              LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
              JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )

            UNION ALL
            SELECT
                ''relation-acl'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    class.relname::pg_catalog.text || '':'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
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
                            CASE WHEN class.relkind = ''S'' THEN ''S''::pg_catalog."char"
                                 ELSE ''r''::pg_catalog."char" END,
                            class.relowner
                        )
                    )
              ) AS acl
              LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
              JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
             WHERE namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )
               AND class.relkind IN (''r'', ''p'', ''S'', ''v'', ''m'', ''f'')

            UNION ALL
            SELECT
                ''column-acl'',
                namespace.nspname::pg_catalog.text || ''.'' ||
                    class.relname::pg_catalog.text || '':'' ||
                    attribute.attname::pg_catalog.text || '':'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
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
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
             )
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped

            UNION ALL
            SELECT
                ''default-acl'',
                owner.rolname::pg_catalog.text || '':'' ||
                    COALESCE(namespace.nspname::pg_catalog.text, '''') || '':'' ||
                    default_acl.defaclobjtype::pg_catalog.text || '':'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
                    acl.privilege_type,
                pg_catalog.jsonb_build_array(
                    acl.is_grantable,
                    grantor.rolname
                )::pg_catalog.text
              FROM pg_catalog.pg_default_acl AS default_acl
              JOIN pg_catalog.pg_roles AS owner ON owner.oid = default_acl.defaclrole
              LEFT JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = default_acl.defaclnamespace
              CROSS JOIN LATERAL pg_catalog.aclexplode(default_acl.defaclacl) AS acl
              LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
              JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
             WHERE owner.rolname OPERATOR(pg_catalog.~) ''^ofarm_''
                OR namespace.nspname IN (
                    ''ofarm'', ''ofarm_crypto'', ''ofarm_infrastructure'', ''public''
                )

            UNION ALL
            SELECT
                ''parameter-acl'',
                parameter.parname::pg_catalog.text || '':'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         WHEN grantee.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
                    acl.privilege_type,
                pg_catalog.jsonb_build_array(
                    acl.is_grantable,
                    CASE WHEN grantor.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE grantor.rolname::pg_catalog.text END
                )::pg_catalog.text
              FROM pg_catalog.pg_parameter_acl AS parameter
              CROSS JOIN LATERAL pg_catalog.aclexplode(parameter.paracl) AS acl
              LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
              JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor

            UNION ALL
            SELECT
                ''extension'',
                extension.extname::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    extension.extversion,
                    CASE WHEN owner.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE owner.rolname::pg_catalog.text END,
                    namespace.nspname
                )::pg_catalog.text
              FROM pg_catalog.pg_extension AS extension
              JOIN pg_catalog.pg_roles AS owner ON owner.oid = extension.extowner
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = extension.extnamespace

            UNION ALL
            SELECT
                ''extension-dependency'',
                extension.extname::pg_catalog.text || '':'' ||
                    identified.type || '':'' ||
                    COALESCE(identified.schema, '''') || '':'' ||
                    COALESCE(identified.name, '''') || '':'' ||
                    identified.identity,
                pg_catalog.jsonb_build_array(
                    dependency.classid::pg_catalog.regclass::pg_catalog.text,
                    dependency.objsubid,
                    dependency.refobjsubid,
                    dependency.deptype
                )::pg_catalog.text
              FROM pg_catalog.pg_depend AS dependency
              JOIN pg_catalog.pg_extension AS extension
                ON extension.oid = dependency.refobjid
              CROSS JOIN LATERAL pg_catalog.pg_identify_object(
                    dependency.classid,
                    dependency.objid,
                    dependency.objsubid
              ) AS identified(type, schema, name, identity)
             WHERE dependency.refclassid =
                    ''pg_catalog.pg_extension''::pg_catalog.regclass
               AND (
                    extension.extname = ''ofarm_ed25519''
                    OR identified.schema IN (
                        ''ofarm'',
                        ''ofarm_crypto'',
                        ''ofarm_infrastructure'',
                        ''public''
                    )
               )

            UNION ALL
            SELECT
                ''backend-statistics-view'',
                ''pg_catalog.pg_stat_activity'',
                pg_catalog.jsonb_build_array(
                    CASE WHEN owner.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE owner.rolname::pg_catalog.text END,
                    class.relkind,
                    class.relpersistence,
                    class.relispartition,
                    class.relrowsecurity,
                    class.relforcerowsecurity,
                    EXISTS (
                        SELECT 1
                          FROM pg_catalog.pg_rewrite AS relation_rule
                         WHERE relation_rule.ev_class = class.oid
                    ),
                    EXISTS (
                        SELECT 1
                          FROM pg_catalog.pg_trigger AS relation_trigger
                         WHERE relation_trigger.tgrelid = class.oid
                    ),
                    EXISTS (
                        SELECT 1
                          FROM pg_catalog.pg_inherits AS relation_child
                         WHERE relation_child.inhparent = class.oid
                    ),
                    EXISTS (
                        SELECT 1
                          FROM pg_catalog.pg_index AS relation_index
                         WHERE relation_index.indrelid = class.oid
                    ),
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
             WHERE namespace.nspname = ''pg_catalog''
               AND class.relname = ''pg_stat_activity''

            UNION ALL
            SELECT
                ''backend-statistics-view-columns'',
                ''pg_catalog.pg_stat_activity'',
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
             WHERE namespace.nspname = ''pg_catalog''
               AND class.relname = ''pg_stat_activity''
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
             GROUP BY class.oid

            UNION ALL
            SELECT
                ''backend-statistics-view-rewrite'',
                ''pg_catalog.pg_stat_activity:'' ||
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
             WHERE namespace.nspname = ''pg_catalog''
               AND class.relname = ''pg_stat_activity''

            UNION ALL
            SELECT
                ''backend-statistics-view-acl'',
                ''pg_catalog.pg_stat_activity:'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         WHEN grantee.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
                    acl.privilege_type,
                pg_catalog.jsonb_build_array(
                    acl.is_grantable,
                    CASE WHEN grantor.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE grantor.rolname::pg_catalog.text END
                )::pg_catalog.text
              FROM pg_catalog.pg_class AS class
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = class.relnamespace
              CROSS JOIN LATERAL pg_catalog.aclexplode(
                    COALESCE(
                        class.relacl,
                        pg_catalog.acldefault(''r'', class.relowner)
                    )
              ) AS acl
              LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
              JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
             WHERE namespace.nspname = ''pg_catalog''
               AND class.relname = ''pg_stat_activity''
               AND class.relkind = ''v''

            UNION ALL
            SELECT
                ''backend-statistics-routine'',
                routine.proname::pg_catalog.text || ''('' ||
                    pg_catalog.pg_get_function_identity_arguments(routine.oid) || '')'',
                pg_catalog.jsonb_build_array(
                    CASE WHEN owner.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
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
             WHERE namespace.nspname = ''pg_catalog''
               AND pg_catalog.left(
                       routine.proname::pg_catalog.text, 20
                   ) IN (''pg_stat_get_activity'', ''pg_stat_get_backend_'')

            UNION ALL
            SELECT
                ''backend-statistics-routine-acl'',
                routine.proname::pg_catalog.text || ''('' ||
                    pg_catalog.pg_get_function_identity_arguments(routine.oid) || ''):'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         WHEN grantee.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
                    acl.privilege_type,
                pg_catalog.jsonb_build_array(
                    acl.is_grantable,
                    CASE WHEN grantor.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE grantor.rolname::pg_catalog.text END
                )::pg_catalog.text
              FROM pg_catalog.pg_proc AS routine
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = routine.pronamespace
              CROSS JOIN LATERAL pg_catalog.aclexplode(
                    COALESCE(
                        routine.proacl,
                        pg_catalog.acldefault(''f'', routine.proowner)
                    )
              ) AS acl
              LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
              JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
             WHERE namespace.nspname = ''pg_catalog''
               AND pg_catalog.left(
                       routine.proname::pg_catalog.text, 20
                   ) IN (''pg_stat_get_activity'', ''pg_stat_get_backend_'')

            UNION ALL
            SELECT
                ''large-object-routine'',
                routine.proname::pg_catalog.text || ''('' ||
                    pg_catalog.pg_get_function_identity_arguments(routine.oid) || '')'',
                pg_catalog.jsonb_build_array(
                    CASE WHEN owner.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
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
             WHERE namespace.nspname = ''pg_catalog''
               AND (
                    pg_catalog.left(routine.proname::pg_catalog.text, 3) = ''lo_''
                    OR routine.proname IN (''loread'', ''lowrite'')
               )

            UNION ALL
            SELECT
                ''large-object-routine-acl'',
                routine.proname::pg_catalog.text || ''('' ||
                    pg_catalog.pg_get_function_identity_arguments(routine.oid) || ''):'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         WHEN grantee.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
                    acl.privilege_type,
                pg_catalog.jsonb_build_array(
                    acl.is_grantable,
                    CASE WHEN grantor.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE grantor.rolname::pg_catalog.text END
                )::pg_catalog.text
              FROM pg_catalog.pg_proc AS routine
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = routine.pronamespace
              CROSS JOIN LATERAL pg_catalog.aclexplode(
                    COALESCE(
                        routine.proacl,
                        pg_catalog.acldefault(''f'', routine.proowner)
                    )
              ) AS acl
              LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
              JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
             WHERE namespace.nspname = ''pg_catalog''
               AND (
                    pg_catalog.left(routine.proname::pg_catalog.text, 3) = ''lo_''
                    OR routine.proname IN (''loread'', ''lowrite'')
               )

            UNION ALL
            SELECT
                ''large-object'',
                large_object.oid::pg_catalog.text,
                pg_catalog.jsonb_build_array(
                    CASE WHEN owner.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE owner.rolname::pg_catalog.text END
                )::pg_catalog.text
              FROM pg_catalog.pg_largeobject_metadata AS large_object
              JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = large_object.lomowner

            UNION ALL
            SELECT
                ''large-object-acl'',
                large_object.oid::pg_catalog.text || '':'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         WHEN grantee.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
                    acl.privilege_type,
                pg_catalog.jsonb_build_array(
                    acl.is_grantable,
                    CASE WHEN grantor.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE grantor.rolname::pg_catalog.text END
                )::pg_catalog.text
              FROM pg_catalog.pg_largeobject_metadata AS large_object
              CROSS JOIN LATERAL pg_catalog.aclexplode(
                    COALESCE(
                        large_object.lomacl,
                        pg_catalog.acldefault(''L'', large_object.lomowner)
                    )
              ) AS acl
              LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
              JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor

            UNION ALL
            SELECT
                ''advisory-routine-acl'',
                routine.proname::pg_catalog.text || ''('' ||
                    pg_catalog.pg_get_function_identity_arguments(routine.oid) || ''):'' ||
                    CASE WHEN acl.grantee = 0 THEN ''PUBLIC''
                         WHEN grantee.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE grantee.rolname::pg_catalog.text END || '':'' ||
                    acl.privilege_type,
                pg_catalog.jsonb_build_array(
                    acl.is_grantable,
                    CASE WHEN grantor.rolsuper THEN ''BOOTSTRAP_SUPERUSER''
                         ELSE grantor.rolname::pg_catalog.text END
                )::pg_catalog.text
              FROM pg_catalog.pg_proc AS routine
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = routine.pronamespace
              CROSS JOIN LATERAL pg_catalog.aclexplode(
                    COALESCE(
                        routine.proacl,
                        pg_catalog.acldefault(''f'', routine.proowner)
                    )
              ) AS acl
              LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
              JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
             WHERE namespace.nspname = ''pg_catalog''
               AND routine.proname IN (
                    ''pg_advisory_lock'',
                    ''pg_advisory_lock_shared'',
                    ''pg_advisory_unlock'',
                    ''pg_advisory_unlock_all'',
                    ''pg_advisory_unlock_shared'',
                    ''pg_advisory_xact_lock'',
                    ''pg_advisory_xact_lock_shared'',
                    ''pg_try_advisory_lock'',
                    ''pg_try_advisory_lock_shared'',
                    ''pg_try_advisory_xact_lock'',
                    ''pg_try_advisory_xact_lock_shared''
               )
        )
        SELECT ''sha256:'' || pg_catalog.encode(
                   pg_catalog.sha256(
                       pg_catalog.convert_to(
                           ''OFARM_TENANT_COMPLETE_CATALOG_V1'' ||
                           pg_catalog.chr(29) ||
                           pg_catalog.string_agg(
                               category || pg_catalog.chr(31) ||
                               object_identity || pg_catalog.chr(31) || definition,
                               pg_catalog.chr(30)
                               ORDER BY
                                   category COLLATE pg_catalog."C",
                                   object_identity COLLATE pg_catalog."C",
                                   definition COLLATE pg_catalog."C"
                           ),
                           ''UTF8''
                       )
                   ),
                   ''hex''
               )
          INTO observed_structural_catalog_digest
          FROM catalog_entry;
        IF observed_structural_catalog_digest <>
                ''sha256:41e8540211ecadf08a6dcd80f499a0bc17c93ba8e5c64914d1c620ab17686fd3'' THEN
            differences := pg_catalog.array_append(
                differences, ''complete tenant catalog fingerprint differs''
            );
        END IF;

        RETURN QUERY SELECT
            pg_catalog.cardinality(differences) = 0,
            ''sha256:39e979fa296122cb66d42eae5e2d7c6dc797ac77ef4324515ae1ab6020088d83''::pg_catalog.text,
            pg_catalog.cardinality(differences),
            observed_structural_catalog_digest,
            observed_relation_inventory,
            observed_provisioning_digest,
            observed_service_identity,
            observed_head_version,
            observed_prefix_digest,
            observed_migration_count,
            observed_breakglass;
    END';

CREATE FUNCTION ofarm.observe_tenant_contract()
RETURNS TABLE (
    structurally_compatible pg_catalog.bool,
    tenant_context_contract_digest pg_catalog.text,
    difference_count pg_catalog.int4,
    structural_catalog_digest pg_catalog.text,
    relation_inventory_digest pg_catalog.text,
    provisioning_spec_digest pg_catalog.text,
    migration_service_identity pg_catalog.text,
    migration_head_version pg_catalog.int4,
    applied_prefix_digest pg_catalog.text,
    migration_row_count pg_catalog.int8,
    breakglass_login_present pg_catalog.bool
)
LANGUAGE plpgsql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN
        IF SESSION_USER <> ''ofarm_readiness'' THEN
            RAISE EXCEPTION USING
                ERRCODE = ''42501'',
                MESSAGE = ''tenant contract observation caller differs'';
        END IF;
        RETURN QUERY SELECT * FROM ofarm.verify_tenant_structure();
    END';

REVOKE ALL PRIVILEGES ON FUNCTION ofarm.verify_tenant_structure()
FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION ofarm.observe_tenant_contract()
FROM PUBLIC;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA ofarm FROM PUBLIC;

GRANT SELECT ON TABLE
    ofarm.tenant_binder_instance,
    ofarm.tenant_capability_verification_key,
    ofarm.tenant_capability_key_lifecycle,
    ofarm.tenant_capability_keyring,
    ofarm.principal_binding,
    ofarm.principal_binding_lifecycle,
    ofarm.principal_binding_current,
    ofarm.tenant_registry
TO ofarm_binder;
-- PostgreSQL requires UPDATE on at least one column for each ADR-mandated
-- binder FOR KEY SHARE row lock.  These grants expose no LOGIN or SET path.
GRANT UPDATE (kid)
ON TABLE ofarm.tenant_capability_verification_key TO ofarm_binder;
GRANT UPDATE (audience)
ON TABLE ofarm.tenant_capability_keyring TO ofarm_binder;
GRANT UPDATE (subject)
ON TABLE ofarm.principal_binding_current TO ofarm_binder;
GRANT INSERT ON TABLE
    ofarm.tenant_capability_verification_key,
    ofarm.tenant_capability_key_lifecycle,
    ofarm.principal_binding,
    ofarm.principal_binding_lifecycle
TO ofarm_admission_lock_owner;
-- PostgreSQL requires UPDATE on at least one column for the ADR-mandated
-- candidate FOR UPDATE row lock.  The immutable-row trigger still refuses
-- every attempted candidate mutation.
GRANT UPDATE (kid) ON TABLE ofarm.tenant_capability_verification_key
TO ofarm_admission_lock_owner;
GRANT INSERT, UPDATE, DELETE ON TABLE ofarm.tenant_capability_keyring
TO ofarm_admission_lock_owner;
GRANT INSERT, UPDATE, DELETE ON TABLE ofarm.principal_binding_current
TO ofarm_admission_lock_owner;
GRANT SELECT (
    tenant_id, record_id, record_kind, schema_digest, payload_digest,
    party_state, party_id
) ON TABLE ofarm.kernel_record TO ofarm_binder;
GRANT SELECT (
    tenant_id, record_id, record_kind, schema_digest, payload_digest,
    party_state, party_id
) ON TABLE ofarm.kernel_record TO ofarm_admission_lock_owner;

GRANT EXECUTE ON FUNCTION ofarm.base64url_decode(pg_catalog.text),
    ofarm.base64url_encode(pg_catalog.bytea),
    ofarm.valid_ascii_id(pg_catalog.text),
    ofarm.valid_oidc_issuer(pg_catalog.text),
    ofarm.tenant_capability_key_id(pg_catalog.bytea),
    ofarm.uuid_from_network(pg_catalog.bytea),
    ofarm.int8_from_network(pg_catalog.bytea),
    ofarm.parse_tenant_capability_payload(pg_catalog.bytea),
    ofarm.fold_principal_binding_authority(
        pg_catalog.text, pg_catalog.text, pg_catalog.text
    ),
    ofarm.fold_tenant_capability_key_lifecycle(pg_catalog.text)
TO ofarm_binder;
GRANT EXECUTE ON FUNCTION
    ofarm.lp32(pg_catalog.bytea),
    ofarm.base64url_encode(pg_catalog.bytea),
    ofarm.tenant_capability_key_id(pg_catalog.bytea),
    ofarm.valid_ascii_id(pg_catalog.text),
    ofarm.valid_oidc_issuer(pg_catalog.text),
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
        pg_catalog.timestamptz, pg_catalog.timestamptz, pg_catalog.text,
        pg_catalog.text
    ),
    ofarm.compute_tenant_capability_candidate_digest(
        pg_catalog.uuid, pg_catalog.text, pg_catalog.bytea, pg_catalog.text,
        pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.text,
        pg_catalog.text, pg_catalog.text, pg_catalog.text,
        pg_catalog.timestamptz, pg_catalog.text
    ),
    ofarm.compute_tenant_capability_key_act_digest(
        pg_catalog.int8, pg_catalog.uuid, pg_catalog.uuid, pg_catalog.text,
        pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.text,
        pg_catalog.text, pg_catalog.text, pg_catalog.text,
        pg_catalog.int8, pg_catalog.int8,
        pg_catalog.int8, pg_catalog.int8, pg_catalog.uuid, pg_catalog.uuid,
        pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.text,
        pg_catalog.text
    )
TO ofarm_admission_lock_owner;
-- The bridge is owned by the unreachable NOLOGIN/NOINHERIT binder so its
-- SECURITY DEFINER body can call the generic native verifier. PostgreSQL gives
-- every function owner implicit EXECUTE; only the admission owner receives an
-- explicit bridge grant, and no LOGIN role can SET either owner role.
GRANT EXECUTE ON FUNCTION ofarm.verify_tenant_capability_preflight(
    pg_catalog.bytea, pg_catalog.bytea
) TO ofarm_admission_lock_owner;
GRANT EXECUTE ON FUNCTION ofarm.bind_tenant_capability(pg_catalog.text),
    ofarm.create_tenant_challenge(),
    ofarm.current_tenant_context(),
    ofarm.current_tenant_id(),
    ofarm.take_tenant_write_lock()
TO ofarm_app, ofarm_worker;

GRANT EXECUTE ON FUNCTION ofarm.register_tenant_capability_key(
        pg_catalog.bytea, pg_catalog.text, pg_catalog.text
    ),
    ofarm.verify_tenant_capability_candidate_preflight(
        pg_catalog.text, pg_catalog.bytea
    ),
    ofarm.activate_tenant_capability_key(
        pg_catalog.text, pg_catalog.uuid, pg_catalog.text, pg_catalog.text,
        pg_catalog.text, pg_catalog.text, pg_catalog.text
    ),
    ofarm.rotate_tenant_capability_key(
        pg_catalog.text, pg_catalog.text, pg_catalog.uuid, pg_catalog.text,
        pg_catalog.text, pg_catalog.text, pg_catalog.text, pg_catalog.text
    ),
    ofarm.close_tenant_capability_admission(
        pg_catalog.uuid, pg_catalog.text, pg_catalog.text, pg_catalog.text,
        pg_catalog.text, pg_catalog.text
    ),
    ofarm.revoke_tenant_capability_key(
        pg_catalog.text, pg_catalog.uuid, pg_catalog.text, pg_catalog.uuid,
        pg_catalog.uuid, pg_catalog.text, pg_catalog.text, pg_catalog.text
    ),
    ofarm.resume_tenant_capability_admission(
        pg_catalog.uuid, pg_catalog.text, pg_catalog.uuid, pg_catalog.uuid,
        pg_catalog.text, pg_catalog.text, pg_catalog.text
    ),
    ofarm.rebuild_tenant_capability_keyring(),
    ofarm.observe_tenant_capability_key(pg_catalog.text)
TO ofarm_capability_key_controller;
GRANT EXECUTE ON FUNCTION ofarm.observe_tenant_contract()
TO ofarm_readiness;
