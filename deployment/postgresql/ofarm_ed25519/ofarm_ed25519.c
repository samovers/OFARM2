#include "postgres.h"
#include "access/detoast.h"
#include "fmgr.h"
#include "varatt.h"

#include <sodium.h>

#include "ofarm_ed25519_core.h"

#if !defined(OFARM_ED25519_TEST_BUILD) && \
    (defined(OFARM_ED25519_TEST_FAULT_SODIUM_INIT) || \
     defined(OFARM_ED25519_TEST_FAULT_DETOAST_OOM) || \
     defined(OFARM_ED25519_TEST_FAULT_DETOAST_CANCEL) || \
     defined(OFARM_ED25519_TEST_FAULT_DETOAST_TIMEOUT) || \
     defined(OFARM_ED25519_TEST_FAULT_DETOAST_TRANSACTION) || \
     defined(OFARM_ED25519_TEST_FAULT_DETOAST_STORAGE))
#error "OFARM Ed25519 fault injection is test-build-only"
#endif

#if (defined(OFARM_ED25519_TEST_FAULT_DETOAST_OOM) + \
     defined(OFARM_ED25519_TEST_FAULT_DETOAST_CANCEL) + \
     defined(OFARM_ED25519_TEST_FAULT_DETOAST_TIMEOUT) + \
     defined(OFARM_ED25519_TEST_FAULT_DETOAST_TRANSACTION) + \
     defined(OFARM_ED25519_TEST_FAULT_DETOAST_STORAGE)) > 1
#error "select exactly one OFARM Ed25519 detoast fault"
#endif

#ifdef PG_MODULE_MAGIC
PG_MODULE_MAGIC;
#endif

PGDLLEXPORT void _PG_init(void);
PGDLLEXPORT Datum ofarm_ed25519_verify(PG_FUNCTION_ARGS);

PG_FUNCTION_INFO_V1(ofarm_ed25519_verify);

static const char *const OFARM_CRYPTO_FAILURE =
    "OFARM Ed25519 verifier infrastructure failure";

static void
raise_crypto_failure(void)
{
    ereport(ERROR,
            (errcode(ERRCODE_SYSTEM_ERROR),
             errmsg_internal("%s", OFARM_CRYPTO_FAILURE)));
}

static bool
raw_bytea_length_may_fit(Datum datum, Size maximum_payload_length)
{
    Size raw_size = toast_raw_datum_size(datum);

    return raw_size <= maximum_payload_length + VARHDRSZ;
}

/*
 * Detoasting is the only verifier-owned operation here that may allocate in a
 * PostgreSQL memory context.  Translate only its out-of-memory condition.  An
 * interrupt, timeout, transaction failure, storage failure, or any other
 * PostgreSQL error retains its original ErrorData and is rethrown unchanged.
 */
static bytea *
detoast_bytea(Datum datum, int argument_number)
{
    MemoryContext caller_context = CurrentMemoryContext;
    bytea *volatile value = NULL;

    (void) argument_number;
    PG_TRY();
    {
#if defined(OFARM_ED25519_TEST_FAULT_DETOAST_OOM)
        if (argument_number == 1)
            ereport(ERROR,
                    (errcode(ERRCODE_OUT_OF_MEMORY),
                     errmsg_internal("OFARM test-only detoast allocation")));
#elif defined(OFARM_ED25519_TEST_FAULT_DETOAST_CANCEL)
        if (argument_number == 1)
            ereport(ERROR,
                    (errcode(ERRCODE_QUERY_CANCELED),
                     errmsg_internal("OFARM test-only cancellation")));
#elif defined(OFARM_ED25519_TEST_FAULT_DETOAST_TIMEOUT)
        if (argument_number == 1)
            ereport(ERROR,
                    (errcode(ERRCODE_QUERY_CANCELED),
                     errmsg_internal("OFARM test-only statement timeout")));
#elif defined(OFARM_ED25519_TEST_FAULT_DETOAST_TRANSACTION)
        if (argument_number == 1)
            ereport(ERROR,
                    (errcode(ERRCODE_T_R_SERIALIZATION_FAILURE),
                     errmsg_internal("OFARM test-only transaction failure")));
#elif defined(OFARM_ED25519_TEST_FAULT_DETOAST_STORAGE)
        if (argument_number == 1)
            ereport(ERROR,
                    (errcode(ERRCODE_IO_ERROR),
                     errmsg_internal("OFARM test-only storage failure")));
#endif
        value = DatumGetByteaPP(datum);
    }
    PG_CATCH();
    {
        if (geterrcode() != ERRCODE_OUT_OF_MEMORY)
            PG_RE_THROW();
        MemoryContextSwitchTo(caller_context);
        FlushErrorState();
        raise_crypto_failure();
    }
    PG_END_TRY();

    return (bytea *) value;
}

void
_PG_init(void)
{
#if defined(OFARM_ED25519_TEST_FAULT_SODIUM_INIT)
    int result = -1;
#else
    int result = sodium_init();
#endif

    if (result != 0 && result != 1)
        raise_crypto_failure();
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

    public_key = detoast_bytea(public_key_datum, 0);
    signed_bytes = detoast_bytea(signed_bytes_datum, 1);
    signature = detoast_bytea(signature_datum, 2);
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

    raise_crypto_failure();
    PG_RETURN_BOOL(false);
}
