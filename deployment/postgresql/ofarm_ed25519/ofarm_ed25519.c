#include "postgres.h"
#include "access/detoast.h"
#include "fmgr.h"
#include "varatt.h"

#include <sodium.h>

#include "ofarm_ed25519_core.h"

#ifdef PG_MODULE_MAGIC
PG_MODULE_MAGIC;
#endif

PGDLLEXPORT void _PG_init(void);
PGDLLEXPORT Datum ofarm_ed25519_verify(PG_FUNCTION_ARGS);

PG_FUNCTION_INFO_V1(ofarm_ed25519_verify);

static const char *const OFARM_CRYPTO_FAILURE =
    "OFARM Ed25519 verifier infrastructure failure";

static bool
raw_bytea_length_may_fit(Datum datum, Size maximum_payload_length)
{
    Size raw_size = toast_raw_datum_size(datum);

    return raw_size <= maximum_payload_length + VARHDRSZ;
}

void
_PG_init(void)
{
    int result = sodium_init();

    if (result != 0 && result != 1)
        ereport(ERROR,
                (errcode(ERRCODE_SYSTEM_ERROR),
                 errmsg_internal("%s", OFARM_CRYPTO_FAILURE)));
}

Datum
ofarm_ed25519_verify(PG_FUNCTION_ARGS)
{
    Datum public_key_datum = PG_GETARG_DATUM(0);
    Datum signed_bytes_datum = PG_GETARG_DATUM(1);
    Datum signature_datum = PG_GETARG_DATUM(2);
    bytea *public_key;
    bytea *signed_bytes;
    bytea *signature;
    Size public_key_length;
    Size signed_bytes_length;
    Size signature_length;
    ofarm_ed25519_result result;

    if (!raw_bytea_length_may_fit(public_key_datum,
                                  OFARM_ED25519_PUBLIC_KEY_BYTES) ||
        !raw_bytea_length_may_fit(signed_bytes_datum,
                                  OFARM_ED25519_MAX_SIGNED_BYTES) ||
        !raw_bytea_length_may_fit(signature_datum,
                                  OFARM_ED25519_SIGNATURE_BYTES))
        PG_RETURN_BOOL(false);

    public_key = PG_GETARG_BYTEA_PP(0);
    signed_bytes = PG_GETARG_BYTEA_PP(1);
    signature = PG_GETARG_BYTEA_PP(2);
    public_key_length = VARSIZE_ANY_EXHDR(public_key);
    signed_bytes_length = VARSIZE_ANY_EXHDR(signed_bytes);
    signature_length = VARSIZE_ANY_EXHDR(signature);

    result = ofarm_ed25519_verify_bytes(
        (const unsigned char *) VARDATA_ANY(public_key),
        (size_t) public_key_length,
        (const unsigned char *) VARDATA_ANY(signed_bytes),
        (size_t) signed_bytes_length,
        (const unsigned char *) VARDATA_ANY(signature),
        (size_t) signature_length);

    PG_FREE_IF_COPY(public_key, 0);
    PG_FREE_IF_COPY(signed_bytes, 1);
    PG_FREE_IF_COPY(signature, 2);

    if (result == OFARM_ED25519_VERIFIED)
        PG_RETURN_BOOL(true);
    if (result == OFARM_ED25519_REFUSED)
        PG_RETURN_BOOL(false);

    ereport(ERROR,
            (errcode(ERRCODE_SYSTEM_ERROR),
             errmsg_internal("%s", OFARM_CRYPTO_FAILURE)));
    PG_RETURN_BOOL(false);
}
