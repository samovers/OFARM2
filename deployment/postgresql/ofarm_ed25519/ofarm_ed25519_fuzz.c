#include "ofarm_ed25519_core.h"

#include <sodium.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define OFARM_ED25519_VECTOR_DEFINE_BOUNDARIES
#include "ofarm_ed25519_vectors.h"

static uint64_t fuzz_state = OFARM_ED25519_VECTOR_XORSHIFT_SEED;

static void
fail(const char *label)
{
    (void) fprintf(stderr, "ofarm_ed25519_fuzz: %s\n", label);
    exit(EXIT_FAILURE);
}

static uint32_t
next_u32(void)
{
    fuzz_state ^= fuzz_state << 13;
    fuzz_state ^= fuzz_state >> 7;
    fuzz_state ^= fuzz_state << 17;
    return (uint32_t) (fuzz_state >> 16);
}

static unsigned char *
allocate_bytes(size_t length)
{
    unsigned char *value = (unsigned char *) malloc(length);

    if (value == NULL && length != 0U)
        fail("bounded allocation failed");
    return value;
}

static void
fill_bytes(unsigned char *value, size_t length)
{
    size_t index;

    for (index = 0; index < length; index++)
        value[index] = (unsigned char) next_u32();
}

static void
exercise_random_boundary_tuple(void)
{
    size_t public_key_length = OFARM_ED25519_VECTOR_PUBLIC_KEY_LENGTHS[
        next_u32() % OFARM_ED25519_VECTOR_PUBLIC_KEY_LENGTH_COUNT];
    size_t signed_bytes_length = OFARM_ED25519_VECTOR_SIGNED_BYTES_LENGTHS[
        next_u32() % OFARM_ED25519_VECTOR_SIGNED_BYTES_LENGTH_COUNT];
    size_t signature_length = OFARM_ED25519_VECTOR_SIGNATURE_LENGTHS[
        next_u32() % OFARM_ED25519_VECTOR_SIGNATURE_LENGTH_COUNT];
    unsigned char *public_key = allocate_bytes(public_key_length);
    unsigned char *signed_bytes = allocate_bytes(signed_bytes_length);
    unsigned char *signature = allocate_bytes(signature_length);
    ofarm_ed25519_result result;

    fill_bytes(public_key, public_key_length);
    fill_bytes(signed_bytes, signed_bytes_length);
    fill_bytes(signature, signature_length);
    result = ofarm_ed25519_verify_bytes(public_key,
                                        public_key_length,
                                        signed_bytes,
                                        signed_bytes_length,
                                        signature,
                                        signature_length);
    free(signature);
    free(signed_bytes);
    free(public_key);
    if (result != OFARM_ED25519_REFUSED)
        fail("deterministic random boundary tuple was not refused");
}

static void
exercise_extreme_refusal_lengths(void)
{
    static const unsigned char one_byte[1] = {0};
    size_t index;

    for (index = 0;
         index < OFARM_ED25519_VECTOR_PUBLIC_KEY_LENGTH_COUNT;
         index++) {
        size_t length = OFARM_ED25519_VECTOR_PUBLIC_KEY_LENGTHS[index];
        ofarm_ed25519_result result;

        if (length != OFARM_ED25519_PUBLIC_KEY_BYTES) {
            result = ofarm_ed25519_verify_bytes(one_byte,
                                                length,
                                                one_byte,
                                                0U,
                                                one_byte,
                                                0U);
            if (result != OFARM_ED25519_REFUSED)
                fail("extreme public-key length was not refused");
        }
    }
    for (index = 0;
         index < OFARM_ED25519_VECTOR_SIGNED_BYTES_LENGTH_COUNT;
         index++) {
        size_t length = OFARM_ED25519_VECTOR_SIGNED_BYTES_LENGTHS[index];
        ofarm_ed25519_result result;

        if (length > OFARM_ED25519_MAX_SIGNED_BYTES) {
            result = ofarm_ed25519_verify_bytes(one_byte,
                                                OFARM_ED25519_PUBLIC_KEY_BYTES,
                                                one_byte,
                                                length,
                                                one_byte,
                                                OFARM_ED25519_SIGNATURE_BYTES);
            if (result != OFARM_ED25519_REFUSED)
                fail("extreme signed-message length was not refused");
        }
    }
    for (index = 0;
         index < OFARM_ED25519_VECTOR_SIGNATURE_LENGTH_COUNT;
         index++) {
        size_t length = OFARM_ED25519_VECTOR_SIGNATURE_LENGTHS[index];
        ofarm_ed25519_result result;

        if (length != OFARM_ED25519_SIGNATURE_BYTES) {
            result = ofarm_ed25519_verify_bytes(one_byte,
                                                OFARM_ED25519_PUBLIC_KEY_BYTES,
                                                one_byte,
                                                0U,
                                                one_byte,
                                                length);
            if (result != OFARM_ED25519_REFUSED)
                fail("extreme signature length was not refused");
        }
    }
    if (ofarm_ed25519_verify_bytes(one_byte,
                                   SIZE_MAX,
                                   one_byte,
                                   0U,
                                   one_byte,
                                   0U) != OFARM_ED25519_REFUSED ||
        ofarm_ed25519_verify_bytes(one_byte,
                                   OFARM_ED25519_PUBLIC_KEY_BYTES,
                                   one_byte,
                                   SIZE_MAX,
                                   one_byte,
                                   OFARM_ED25519_SIGNATURE_BYTES) !=
            OFARM_ED25519_REFUSED ||
        ofarm_ed25519_verify_bytes(one_byte,
                                   OFARM_ED25519_PUBLIC_KEY_BYTES,
                                   one_byte,
                                   0U,
                                   one_byte,
                                   SIZE_MAX) != OFARM_ED25519_REFUSED)
        fail("SIZE_MAX refusal boundary changed");
}

int
main(void)
{
    size_t iteration;

    if (sodium_init() < 0)
        fail("libsodium initialization failed");
    exercise_extreme_refusal_lengths();
    for (iteration = 0;
         iteration < OFARM_ED25519_VECTOR_C_FUZZ_CASES;
         iteration++)
        exercise_random_boundary_tuple();
    (void) puts("ofarm_ed25519_fuzz: 16384 deterministic cases ok");
    return EXIT_SUCCESS;
}
