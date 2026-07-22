#ifndef OFARM_ED25519_CORE_H
#define OFARM_ED25519_CORE_H

#include <stddef.h>

#define OFARM_ED25519_PUBLIC_KEY_BYTES 32U
#define OFARM_ED25519_SIGNATURE_BYTES 64U
#define OFARM_ED25519_MAX_SIGNED_BYTES 8192U

typedef enum ofarm_ed25519_result
{
    OFARM_ED25519_ERROR = -1,
    OFARM_ED25519_REFUSED = 0,
    OFARM_ED25519_VERIFIED = 1
} ofarm_ed25519_result;

ofarm_ed25519_result ofarm_ed25519_verify_bytes(
    const unsigned char *public_key,
    size_t public_key_length,
    const unsigned char *signed_bytes,
    size_t signed_bytes_length,
    const unsigned char *signature,
    size_t signature_length);

#endif
