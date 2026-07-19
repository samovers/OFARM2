#include "postgres.h"
#include "fmgr.h"
#include "varatt.h"

#include <sodium.h>

#if defined(ED25519_COMPAT)
#error "ED25519_COMPAT is forbidden by ADR 0003"
#endif

#if defined(ED25519_NONDETERMINISTIC)
#error "ED25519_NONDETERMINISTIC is forbidden by ADR 0003"
#endif

#ifdef PG_MODULE_MAGIC
PG_MODULE_MAGIC;
#endif

PGDLLEXPORT void _PG_init(void);
PGDLLEXPORT Datum ofarm_ed25519_verify(PG_FUNCTION_ARGS);

PG_FUNCTION_INFO_V1(ofarm_ed25519_verify);

static const char *const OFARM_CRYPTO_FAILURE =
    "OFARM Ed25519 verifier infrastructure failure";

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
    bytea *public_key = PG_GETARG_BYTEA_PP(0);
    bytea *signed_bytes = PG_GETARG_BYTEA_PP(1);
    bytea *signature = PG_GETARG_BYTEA_PP(2);
    Size public_key_length = VARSIZE_ANY_EXHDR(public_key);
    Size signed_bytes_length = VARSIZE_ANY_EXHDR(signed_bytes);
    Size signature_length = VARSIZE_ANY_EXHDR(signature);
    const unsigned char *public_key_data;
    const unsigned char *signed_bytes_data;
    const unsigned char *signature_data;
    int verified;

    if (public_key_length != crypto_sign_PUBLICKEYBYTES ||
        signed_bytes_length > 8192 ||
        signature_length != crypto_sign_BYTES)
        PG_RETURN_BOOL(false);

    public_key_data = (const unsigned char *) VARDATA_ANY(public_key);
    signed_bytes_data = (const unsigned char *) VARDATA_ANY(signed_bytes);
    signature_data = (const unsigned char *) VARDATA_ANY(signature);

    if (crypto_core_ed25519_is_valid_point(public_key_data) != 1 ||
        crypto_core_ed25519_is_valid_point(signature_data) != 1)
        PG_RETURN_BOOL(false);

    verified = crypto_sign_verify_detached(signature_data,
                                           signed_bytes_data,
                                           (unsigned long long) signed_bytes_length,
                                           public_key_data);
    if (verified == 0)
        PG_RETURN_BOOL(true);
    if (verified == -1)
        PG_RETURN_BOOL(false);

    ereport(ERROR,
            (errcode(ERRCODE_SYSTEM_ERROR),
             errmsg_internal("%s", OFARM_CRYPTO_FAILURE)));
    PG_RETURN_BOOL(false);
}
