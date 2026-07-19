#include "ofarm_ed25519_core.h"

#include <sodium.h>

#if defined(ED25519_COMPAT)
#error "ED25519_COMPAT is forbidden by ADR 0003"
#endif

#if defined(ED25519_NONDETERMINISTIC)
#error "ED25519_NONDETERMINISTIC is forbidden by ADR 0003"
#endif

ofarm_ed25519_result
ofarm_ed25519_verify_bytes(const unsigned char *public_key,
                           size_t public_key_length,
                           const unsigned char *signed_bytes,
                           size_t signed_bytes_length,
                           const unsigned char *signature,
                           size_t signature_length)
{
    int verified;

    if (public_key_length != OFARM_ED25519_PUBLIC_KEY_BYTES ||
        signed_bytes_length > OFARM_ED25519_MAX_SIGNED_BYTES ||
        signature_length != OFARM_ED25519_SIGNATURE_BYTES)
        return OFARM_ED25519_REFUSED;

    if (crypto_core_ed25519_is_valid_point(public_key) != 1 ||
        crypto_core_ed25519_is_valid_point(signature) != 1)
        return OFARM_ED25519_REFUSED;

    verified = crypto_sign_verify_detached(signature,
                                           signed_bytes,
                                           (unsigned long long) signed_bytes_length,
                                           public_key);
    if (verified == 0)
        return OFARM_ED25519_VERIFIED;
    if (verified == -1)
        return OFARM_ED25519_REFUSED;
    return OFARM_ED25519_ERROR;
}
