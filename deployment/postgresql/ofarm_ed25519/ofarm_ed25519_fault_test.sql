\set ON_ERROR_STOP on

CREATE FUNCTION pg_temp.assert_ofarm_error(
    label pg_catalog.text,
    observed_state pg_catalog.text,
    observed_message pg_catalog.text,
    observed_detail pg_catalog.text,
    observed_hint pg_catalog.text,
    observed_schema pg_catalog.text,
    observed_table pg_catalog.text,
    observed_column pg_catalog.text,
    observed_constraint pg_catalog.text,
    expected_state pg_catalog.text,
    expected_message pg_catalog.text
)
RETURNS pg_catalog.void
LANGUAGE plpgsql
AS $function$
BEGIN
    IF observed_state IS DISTINCT FROM expected_state THEN
        RAISE EXCEPTION '% returned SQLSTATE %, expected %',
            label, observed_state, expected_state;
    END IF;
    IF observed_message IS DISTINCT FROM expected_message THEN
        RAISE EXCEPTION '% returned message %, expected %',
            label, observed_message, expected_message;
    END IF;
    IF COALESCE(observed_detail, '') <> '' OR
       COALESCE(observed_hint, '') <> '' OR
       COALESCE(observed_schema, '') <> '' OR
       COALESCE(observed_table, '') <> '' OR
       COALESCE(observed_column, '') <> '' OR
       COALESCE(observed_constraint, '') <> '' THEN
        RAISE EXCEPTION '% exposed diagnostic detail', label;
    END IF;
END
$function$;

DO $test$
DECLARE
    caught boolean := false;
    observed_state text;
    observed_message text;
    observed_detail text;
    observed_hint text;
    observed_schema text;
    observed_table text;
    observed_column text;
    observed_constraint text;
BEGIN
    BEGIN
        EXECUTE $sql$
            CREATE FUNCTION pg_temp.ofarm_fault_sodium(bytea, bytea, bytea)
            RETURNS boolean
            AS '/opt/ofarm-test-only/ofarm_ed25519_fault_sodium',
               'ofarm_ed25519_verify'
            LANGUAGE C IMMUTABLE STRICT PARALLEL UNSAFE SECURITY INVOKER
        $sql$;
    EXCEPTION WHEN query_canceled OR OTHERS THEN
        caught := true;
        GET STACKED DIAGNOSTICS
            observed_state = RETURNED_SQLSTATE,
            observed_message = MESSAGE_TEXT,
            observed_detail = PG_EXCEPTION_DETAIL,
            observed_hint = PG_EXCEPTION_HINT,
            observed_schema = SCHEMA_NAME,
            observed_table = TABLE_NAME,
            observed_column = COLUMN_NAME,
            observed_constraint = CONSTRAINT_NAME;
        PERFORM pg_temp.assert_ofarm_error(
            'sodium_init failure',
            observed_state, observed_message, observed_detail, observed_hint,
            observed_schema, observed_table, observed_column,
            observed_constraint,
            '58000', 'OFARM Ed25519 verifier infrastructure failure'
        );
    END;
    IF NOT caught THEN
        RAISE EXCEPTION 'sodium_init fault did not fail';
    END IF;
END
$test$;

CREATE FUNCTION pg_temp.ofarm_fault_unexpected(bytea, bytea, bytea)
RETURNS boolean
AS '/opt/ofarm-test-only/ofarm_ed25519_fault_unexpected',
   'ofarm_ed25519_verify'
LANGUAGE C IMMUTABLE STRICT PARALLEL UNSAFE SECURITY INVOKER;

CREATE FUNCTION pg_temp.ofarm_fault_oom(bytea, bytea, bytea)
RETURNS boolean
AS '/opt/ofarm-test-only/ofarm_ed25519_fault_oom', 'ofarm_ed25519_verify'
LANGUAGE C IMMUTABLE STRICT PARALLEL UNSAFE SECURITY INVOKER;

CREATE FUNCTION pg_temp.ofarm_fault_cancel(bytea, bytea, bytea)
RETURNS boolean
AS '/opt/ofarm-test-only/ofarm_ed25519_fault_cancel', 'ofarm_ed25519_verify'
LANGUAGE C IMMUTABLE STRICT PARALLEL UNSAFE SECURITY INVOKER;

CREATE FUNCTION pg_temp.ofarm_fault_timeout(bytea, bytea, bytea)
RETURNS boolean
AS '/opt/ofarm-test-only/ofarm_ed25519_fault_timeout', 'ofarm_ed25519_verify'
LANGUAGE C IMMUTABLE STRICT PARALLEL UNSAFE SECURITY INVOKER;

CREATE FUNCTION pg_temp.ofarm_fault_transaction(bytea, bytea, bytea)
RETURNS boolean
AS '/opt/ofarm-test-only/ofarm_ed25519_fault_transaction',
   'ofarm_ed25519_verify'
LANGUAGE C IMMUTABLE STRICT PARALLEL UNSAFE SECURITY INVOKER;

CREATE FUNCTION pg_temp.ofarm_fault_storage(bytea, bytea, bytea)
RETURNS boolean
AS '/opt/ofarm-test-only/ofarm_ed25519_fault_storage', 'ofarm_ed25519_verify'
LANGUAGE C IMMUTABLE STRICT PARALLEL UNSAFE SECURITY INVOKER;

CREATE FUNCTION pg_temp.exercise_ofarm_fault(
    test_function pg_catalog.text,
    label pg_catalog.text,
    expected_state pg_catalog.text,
    expected_message pg_catalog.text
)
RETURNS pg_catalog.void
LANGUAGE plpgsql
AS $function$
DECLARE
    caught boolean := false;
    observed_state text;
    observed_message text;
    observed_detail text;
    observed_hint text;
    observed_schema text;
    observed_table text;
    observed_column text;
    observed_constraint text;
BEGIN
    BEGIN
        EXECUTE pg_catalog.format(
            'SELECT pg_temp.%I($1, $2, $3)',
            test_function
        ) USING
            decode(
                'd75a980182b10ab7d54bfed3c964073a' ||
                '0ee172f3daa62325af021a68f707511a',
                'hex'
            ),
            decode('', 'hex'),
            decode(
                'e5564300c360ac729086e2cc806e828a' ||
                '84877f1eb8e5d974d873e06522490155' ||
                '5fb8821590a33bacc61e39701cf9b46b' ||
                'd25bf5f0595bbe24655141438e7a100b',
                'hex'
            );
    EXCEPTION WHEN query_canceled OR OTHERS THEN
        caught := true;
        GET STACKED DIAGNOSTICS
            observed_state = RETURNED_SQLSTATE,
            observed_message = MESSAGE_TEXT,
            observed_detail = PG_EXCEPTION_DETAIL,
            observed_hint = PG_EXCEPTION_HINT,
            observed_schema = SCHEMA_NAME,
            observed_table = TABLE_NAME,
            observed_column = COLUMN_NAME,
            observed_constraint = CONSTRAINT_NAME;
        PERFORM pg_temp.assert_ofarm_error(
            label,
            observed_state, observed_message, observed_detail, observed_hint,
            observed_schema, observed_table, observed_column,
            observed_constraint,
            expected_state, expected_message
        );
    END;
    IF NOT caught THEN
        RAISE EXCEPTION '% fault did not fail', label;
    END IF;
END
$function$;

SELECT pg_temp.exercise_ofarm_fault(
    'ofarm_fault_unexpected',
    'unexpected verifier return',
    '58000',
    'OFARM Ed25519 verifier infrastructure failure'
);
SELECT pg_temp.exercise_ofarm_fault(
    'ofarm_fault_oom',
    'detoast allocation failure',
    '58000',
    'OFARM Ed25519 verifier infrastructure failure'
);
SELECT pg_temp.exercise_ofarm_fault(
    'ofarm_fault_cancel',
    'cancellation',
    '57014',
    'OFARM test-only cancellation'
);
SELECT pg_temp.exercise_ofarm_fault(
    'ofarm_fault_timeout',
    'statement timeout',
    '57014',
    'OFARM test-only statement timeout'
);
SELECT pg_temp.exercise_ofarm_fault(
    'ofarm_fault_transaction',
    'transaction failure',
    '40001',
    'OFARM test-only transaction failure'
);
SELECT pg_temp.exercise_ofarm_fault(
    'ofarm_fault_storage',
    'storage failure',
    '58030',
    'OFARM test-only storage failure'
);
