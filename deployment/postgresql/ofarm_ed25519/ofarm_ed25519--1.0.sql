\echo Use "CREATE EXTENSION ofarm_ed25519" to load this file. \quit

CREATE FUNCTION ed25519_verify(
    public_key pg_catalog.bytea,
    signed_bytes pg_catalog.bytea,
    signature pg_catalog.bytea
)
RETURNS pg_catalog.bool
AS 'MODULE_PATHNAME', 'ofarm_ed25519_verify'
LANGUAGE C
IMMUTABLE STRICT PARALLEL UNSAFE SECURITY INVOKER;

REVOKE ALL PRIVILEGES ON FUNCTION ed25519_verify(
    pg_catalog.bytea, pg_catalog.bytea, pg_catalog.bytea
) FROM PUBLIC;

