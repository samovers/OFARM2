\set ON_ERROR_STOP on

CREATE EXTENSION ofarm_ed25519;

DO $test$
BEGIN
    IF NOT ofarm_crypto.ed25519_verify(
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
        )
    ) THEN
        RAISE EXCEPTION 'inline-short RFC 8032 vector was refused';
    END IF;
END
$test$;

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
        ) FROM ofarm_ed25519_large_input) THEN
        RAISE EXCEPTION 'oversized public key was accepted';
    END IF;

    IF (SELECT ofarm_crypto.ed25519_verify(
            decode(repeat('00', 32), 'hex'),
            value,
            decode(repeat('00', 64), 'hex')
        ) FROM ofarm_ed25519_large_input) THEN
        RAISE EXCEPTION 'oversized signed bytes were accepted';
    END IF;

    IF (SELECT ofarm_crypto.ed25519_verify(
            decode(repeat('00', 32), 'hex'),
            decode(repeat('00', 1), 'hex'),
            value
        ) FROM ofarm_ed25519_large_input) THEN
        RAISE EXCEPTION 'oversized signature was accepted';
    END IF;
END
$test$;

DROP TABLE ofarm_ed25519_large_input;
