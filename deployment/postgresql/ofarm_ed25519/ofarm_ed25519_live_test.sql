\set ON_ERROR_STOP on

CREATE EXTENSION ofarm_ed25519;

\ir /tmp/ofarm_ed25519_vectors.sql

DO $strict_contract$
BEGIN
    IF ofarm_crypto.ed25519_verify(
        NULL::bytea, decode('', 'hex'), decode('', 'hex')
    ) IS NOT NULL THEN
        RAISE EXCEPTION 'STRICT null contract violated';
    END IF;
END
$strict_contract$;

CREATE TABLE ofarm_ed25519_large_input (
    value bytea NOT NULL
) WITH (toast_tuple_target = 128);

INSERT INTO ofarm_ed25519_large_input (value)
VALUES (decode(repeat('a5', 1024 * 1024), 'hex'));

DO $test$
DECLARE
    physical_size integer;
    logical_size integer;
BEGIN
    SELECT pg_column_size(value), octet_length(value)
      INTO physical_size, logical_size
      FROM ofarm_ed25519_large_input;

    IF physical_size >= logical_size THEN
        RAISE EXCEPTION 'large hostile input was not stored compressed/toasted';
    END IF;

    IF (SELECT ofarm_crypto.ed25519_verify(
            value,
            decode(repeat('00', 1), 'hex'),
            decode(repeat('00', 1), 'hex')
        ) FROM ofarm_ed25519_large_input) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'oversized public key was accepted';
    END IF;

    IF (SELECT ofarm_crypto.ed25519_verify(
            decode(repeat('00', 32), 'hex'),
            value,
            decode(repeat('00', 64), 'hex')
        ) FROM ofarm_ed25519_large_input) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'oversized signed bytes were accepted';
    END IF;

    IF (SELECT ofarm_crypto.ed25519_verify(
            decode(repeat('00', 32), 'hex'),
            decode(repeat('00', 1), 'hex'),
            value
        ) FROM ofarm_ed25519_large_input) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'oversized signature was accepted';
    END IF;
END
$test$;

DROP TABLE ofarm_ed25519_large_input;

CREATE TABLE ofarm_ed25519_admitted_toast (
    signed_bytes bytea NOT NULL
) WITH (toast_tuple_target = 128);

INSERT INTO ofarm_ed25519_admitted_toast (signed_bytes)
VALUES (decode(repeat('a5', 8192), 'hex'));

DO $test$
DECLARE
    physical_size integer;
    logical_size integer;
BEGIN
    SELECT pg_column_size(signed_bytes), octet_length(signed_bytes)
      INTO physical_size, logical_size
      FROM ofarm_ed25519_admitted_toast;

    IF logical_size <> 8192 OR physical_size >= logical_size THEN
        RAISE EXCEPTION 'admitted input did not exercise compressed detoast';
    END IF;

    IF (SELECT ofarm_crypto.ed25519_verify(
            decode(repeat('00', 32), 'hex'),
            signed_bytes,
            decode(repeat('00', 64), 'hex')
        ) FROM ofarm_ed25519_admitted_toast) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'invalid admitted toasted input was accepted';
    END IF;
END
$test$;

DROP TABLE ofarm_ed25519_admitted_toast;

CREATE TABLE ofarm_ed25519_four_byte_input (
    value bytea NOT NULL
);

INSERT INTO ofarm_ed25519_four_byte_input (value)
VALUES (decode(repeat('a5', 127), 'hex'));

DO $four_byte$
DECLARE
    physical_size integer;
    logical_size integer;
    toast_chunk_id oid;
BEGIN
    SELECT pg_column_size(value),
           octet_length(value),
           pg_column_toast_chunk_id(value)
      INTO physical_size, logical_size, toast_chunk_id
      FROM ofarm_ed25519_four_byte_input;

    IF physical_size IS DISTINCT FROM logical_size + 4
        OR logical_size IS DISTINCT FROM 127
        OR toast_chunk_id IS NOT NULL THEN
        RAISE EXCEPTION 'ordinary four-byte varlena posture was not proved';
    END IF;

    IF (SELECT ofarm_crypto.ed25519_verify(
            value,
            decode('', 'hex'),
            decode(repeat('00', 64), 'hex')
        ) FROM ofarm_ed25519_four_byte_input) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'ordinary four-byte public key was not refused';
    END IF;

    IF (SELECT ofarm_crypto.ed25519_verify(
            decode(repeat('00', 32), 'hex'),
            value,
            decode(repeat('00', 64), 'hex')
        ) FROM ofarm_ed25519_four_byte_input) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'ordinary four-byte signed bytes were not refused';
    END IF;

    IF (SELECT ofarm_crypto.ed25519_verify(
            decode(repeat('00', 32), 'hex'),
            decode('', 'hex'),
            value
        ) FROM ofarm_ed25519_four_byte_input) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'ordinary four-byte signature was not refused';
    END IF;
END
$four_byte$;

DROP TABLE ofarm_ed25519_four_byte_input;

CREATE TABLE ofarm_ed25519_external_input (
    value bytea NOT NULL
) WITH (toast_tuple_target = 128);

ALTER TABLE ofarm_ed25519_external_input
    ALTER COLUMN value SET STORAGE EXTERNAL;

INSERT INTO ofarm_ed25519_external_input (value)
VALUES (decode(repeat('a5', 1024 * 1024), 'hex'));

DO $external$
DECLARE
    physical_size integer;
    logical_size integer;
    storage_strategy "char";
    toast_chunk_id oid;
BEGIN
    SELECT pg_column_size(input.value),
           octet_length(input.value),
           attribute.attstorage,
           pg_column_toast_chunk_id(input.value)
      INTO physical_size, logical_size, storage_strategy, toast_chunk_id
      FROM ofarm_ed25519_external_input AS input
      JOIN pg_catalog.pg_attribute AS attribute
        ON attribute.attrelid = 'ofarm_ed25519_external_input'::regclass
       AND attribute.attname = 'value'
       AND attribute.attnum > 0
       AND NOT attribute.attisdropped;

    IF storage_strategy IS DISTINCT FROM 'e'::"char"
        OR toast_chunk_id IS NULL
        OR physical_size IS DISTINCT FROM logical_size
        OR logical_size IS DISTINCT FROM 1024 * 1024 THEN
        RAISE EXCEPTION 'external uncompressed TOAST posture was not proved';
    END IF;

    IF (SELECT ofarm_crypto.ed25519_verify(
            value,
            decode('', 'hex'),
            decode(repeat('00', 64), 'hex')
        ) FROM ofarm_ed25519_external_input) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'external uncompressed public key was not refused';
    END IF;

    IF (SELECT ofarm_crypto.ed25519_verify(
            decode(repeat('00', 32), 'hex'),
            value,
            decode(repeat('00', 64), 'hex')
        ) FROM ofarm_ed25519_external_input) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'external uncompressed signed bytes were not refused';
    END IF;

    IF (SELECT ofarm_crypto.ed25519_verify(
            decode(repeat('00', 32), 'hex'),
            decode('', 'hex'),
            value
        ) FROM ofarm_ed25519_external_input) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'external uncompressed signature was not refused';
    END IF;
END
$external$;

DROP TABLE ofarm_ed25519_external_input;
