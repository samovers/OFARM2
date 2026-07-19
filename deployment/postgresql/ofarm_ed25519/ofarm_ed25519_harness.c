#include "ofarm_ed25519_core.h"

#include <sodium.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define OFARM_ED25519_VECTOR_DEFINE_CASES
#define OFARM_ED25519_VECTOR_DEFINE_BOUNDARIES
#define OFARM_ED25519_VECTOR_DEFINE_IDENTITY_R_PROOF
#include "ofarm_ed25519_vectors.h"

static void
fail(const char *label)
{
    (void) fprintf(stderr, "ofarm_ed25519_harness: %s\n", label);
    exit(EXIT_FAILURE);
}

static unsigned char
hex_nibble(char value)
{
    if (value >= '0' && value <= '9')
        return (unsigned char) (value - '0');
    if (value >= 'a' && value <= 'f')
        return (unsigned char) (value - 'a' + 10);
    fail("invalid checked-in hexadecimal vector");
    return 0;
}

static void
decode_hex(const char *hex, unsigned char *output, size_t output_length)
{
    size_t index;

    if (strlen(hex) != output_length * 2U)
        fail("wrong checked-in hexadecimal vector length");
    for (index = 0; index < output_length; index++)
        output[index] = (unsigned char) ((hex_nibble(hex[index * 2U]) << 4) |
                                         hex_nibble(hex[index * 2U + 1U]));
}

static unsigned char *
clone_exact(const unsigned char *source, size_t length)
{
    unsigned char *copy = (unsigned char *) malloc(length == 0U ? 1U : length);

    if (copy == NULL && length != 0U)
        fail("exact-sized allocation failed");
    if (length != 0U)
        (void) memcpy(copy, source, length);
    return copy;
}

static const ofarm_ed25519_vector_case *
find_vector(const char *identifier)
{
    size_t index;

    for (index = 0; index < OFARM_ED25519_VECTOR_CASE_COUNT; index++) {
        if (strcmp(OFARM_ED25519_VECTOR_CASES[index].identifier, identifier) == 0)
            return &OFARM_ED25519_VECTOR_CASES[index];
    }
    fail("required canonical vector is absent");
    return NULL;
}

static unsigned char *
decode_allocated_hex(const char *hex, size_t *output_length)
{
    size_t length = strlen(hex) / 2U;
    unsigned char *output = (unsigned char *) malloc(length == 0U ? 1U : length);

    if (output == NULL)
        fail("canonical vector allocation failed");
    decode_hex(hex, output, length);
    *output_length = length;
    return output;
}

static void
expect_result(const char *label,
              const unsigned char *public_key,
              size_t public_key_length,
              const unsigned char *signed_bytes,
              size_t signed_bytes_length,
              const unsigned char *signature,
              size_t signature_length,
              ofarm_ed25519_result expected)
{
    unsigned char *public_key_copy = clone_exact(public_key, public_key_length);
    unsigned char *signed_bytes_copy = clone_exact(signed_bytes, signed_bytes_length);
    unsigned char *signature_copy = clone_exact(signature, signature_length);
    ofarm_ed25519_result actual = ofarm_ed25519_verify_bytes(
        public_key_copy,
        public_key_length,
        signed_bytes_copy,
        signed_bytes_length,
        signature_copy,
        signature_length);

    free(signature_copy);
    free(signed_bytes_copy);
    free(public_key_copy);
    if (actual != expected)
        fail(label);
}

static void
exercise_canonical_cases(void)
{
    size_t index;

    for (index = 0; index < OFARM_ED25519_VECTOR_CASE_COUNT; index++) {
        const ofarm_ed25519_vector_case *vector =
            &OFARM_ED25519_VECTOR_CASES[index];
        size_t public_key_length;
        size_t signed_bytes_length;
        size_t signature_length;
        unsigned char *public_key = decode_allocated_hex(
            vector->public_key_hex, &public_key_length);
        unsigned char *signed_bytes = decode_allocated_hex(
            vector->signed_bytes_hex, &signed_bytes_length);
        unsigned char *signature = decode_allocated_hex(
            vector->signature_hex, &signature_length);

        expect_result(vector->identifier,
                      public_key,
                      public_key_length,
                      signed_bytes,
                      signed_bytes_length,
                      signature,
                      signature_length,
                      vector->expected_verified ? OFARM_ED25519_VERIFIED :
                                                  OFARM_ED25519_REFUSED);
        free(signature);
        free(signed_bytes);
        free(public_key);
    }
}

static void
exercise_known_answers(unsigned char public_key[OFARM_ED25519_PUBLIC_KEY_BYTES],
                       unsigned char rfc_signature[OFARM_ED25519_SIGNATURE_BYTES],
                       unsigned char preflight[43],
                       unsigned char preflight_signature[OFARM_ED25519_SIGNATURE_BYTES])
{
    const ofarm_ed25519_vector_case *rfc =
        find_vector("rfc8032-empty-positive");
    const ofarm_ed25519_vector_case *probe =
        find_vector("kms-preflight-positive");

    decode_hex(rfc->public_key_hex,
               public_key,
               OFARM_ED25519_PUBLIC_KEY_BYTES);
    decode_hex(rfc->signature_hex,
               rfc_signature,
               OFARM_ED25519_SIGNATURE_BYTES);
    decode_hex(probe->signed_bytes_hex, preflight, 43U);
    decode_hex(probe->signature_hex,
               preflight_signature,
               OFARM_ED25519_SIGNATURE_BYTES);
}

static void
exercise_length_boundaries(const unsigned char public_key[OFARM_ED25519_PUBLIC_KEY_BYTES],
                           const unsigned char signature[OFARM_ED25519_SIGNATURE_BYTES])
{
    static const unsigned char empty[1] = {0};
    size_t index;

    for (index = 0;
         index < OFARM_ED25519_VECTOR_PUBLIC_KEY_LENGTH_COUNT;
         index++) {
        size_t length = OFARM_ED25519_VECTOR_PUBLIC_KEY_LENGTHS[index];
        unsigned char *value;

        if (length == OFARM_ED25519_PUBLIC_KEY_BYTES)
            continue;
        value = (unsigned char *) calloc(length == 0U ? 1U : length, 1U);
        if (value == NULL)
            fail("canonical public-key boundary allocation failed");
        expect_result("canonical public-key boundary accepted",
                      value, length, empty, 0U,
                      signature, OFARM_ED25519_SIGNATURE_BYTES,
                      OFARM_ED25519_REFUSED);
        free(value);
    }
    for (index = 0;
         index < OFARM_ED25519_VECTOR_SIGNED_BYTES_LENGTH_COUNT;
         index++) {
        size_t length = OFARM_ED25519_VECTOR_SIGNED_BYTES_LENGTHS[index];
        unsigned char *value;

        if (length <= OFARM_ED25519_MAX_SIGNED_BYTES)
            continue;
        value = (unsigned char *) calloc(length, 1U);
        if (value == NULL)
            fail("canonical signed-bytes boundary allocation failed");
        expect_result("canonical signed-bytes boundary accepted",
                      public_key, OFARM_ED25519_PUBLIC_KEY_BYTES,
                      value, length,
                      signature, OFARM_ED25519_SIGNATURE_BYTES,
                      OFARM_ED25519_REFUSED);
        free(value);
    }
    for (index = 0;
         index < OFARM_ED25519_VECTOR_SIGNATURE_LENGTH_COUNT;
         index++) {
        size_t length = OFARM_ED25519_VECTOR_SIGNATURE_LENGTHS[index];
        unsigned char *value;

        if (length == OFARM_ED25519_SIGNATURE_BYTES)
            continue;
        value = (unsigned char *) calloc(length == 0U ? 1U : length, 1U);
        if (value == NULL)
            fail("canonical signature boundary allocation failed");
        expect_result("canonical signature boundary accepted",
                      public_key, OFARM_ED25519_PUBLIC_KEY_BYTES,
                      empty, 0U,
                      value, length,
                      OFARM_ED25519_REFUSED);
        free(value);
    }
}

static void
exercise_identity_r_equation_proof(void)
{
    const ofarm_ed25519_vector_case *vector =
        find_vector(OFARM_ED25519_IDENTITY_R_PROOF_CASE_ID);
    unsigned char seed[crypto_sign_SEEDBYTES];
    unsigned char expanded_seed[crypto_hash_sha512_BYTES];
    unsigned char expected_scalar[crypto_core_ed25519_SCALARBYTES];
    unsigned char challenge_hash[crypto_hash_sha512_BYTES];
    unsigned char challenge[crypto_core_ed25519_SCALARBYTES];
    unsigned char expected_challenge[crypto_core_ed25519_SCALARBYTES];
    unsigned char public_key[crypto_sign_PUBLICKEYBYTES];
    unsigned char expected_public_key[crypto_sign_PUBLICKEYBYTES];
    unsigned char secret_key[crypto_sign_SECRETKEYBYTES];
    unsigned char signature[crypto_sign_BYTES];
    unsigned char left[crypto_core_ed25519_BYTES];
    unsigned char right[crypto_core_ed25519_BYTES];
    crypto_hash_sha512_state hash_state;

    decode_hex(OFARM_ED25519_IDENTITY_R_PROOF_SEED_HEX, seed, sizeof seed);
    decode_hex(OFARM_ED25519_IDENTITY_R_PROOF_CLAMPED_SCALAR_HEX,
               expected_scalar,
               sizeof expected_scalar);
    decode_hex(OFARM_ED25519_IDENTITY_R_PROOF_CHALLENGE_HEX,
               expected_challenge,
               sizeof expected_challenge);
    decode_hex(vector->public_key_hex,
               expected_public_key,
               sizeof expected_public_key);
    decode_hex(vector->signature_hex, signature, sizeof signature);
    if (vector->signed_bytes_hex[0] != '\0')
        fail("identity-R proof message is not empty");

    if (crypto_hash_sha512(expanded_seed, seed, sizeof seed) != 0)
        fail("identity-R seed expansion failed");
    expanded_seed[0] &= 248U;
    expanded_seed[31] &= 63U;
    expanded_seed[31] |= 64U;
    if (sodium_memcmp(expanded_seed, expected_scalar,
                      sizeof expected_scalar) != 0)
        fail("identity-R clamped scalar proof changed");
    if (crypto_sign_seed_keypair(public_key, secret_key, seed) != 0 ||
        sodium_memcmp(public_key, expected_public_key,
                      sizeof public_key) != 0)
        fail("identity-R proof public key changed");

    if (crypto_hash_sha512_init(&hash_state) != 0 ||
        crypto_hash_sha512_update(&hash_state, signature, 32U) != 0 ||
        crypto_hash_sha512_update(&hash_state,
                                  expected_public_key,
                                  sizeof expected_public_key) != 0 ||
        crypto_hash_sha512_final(&hash_state, challenge_hash) != 0)
        fail("identity-R challenge hash failed");
    crypto_core_ed25519_scalar_reduce(challenge, challenge_hash);
    if (sodium_memcmp(challenge, expected_challenge,
                      sizeof challenge) != 0)
        fail("identity-R reduced challenge proof changed");

    if (crypto_scalarmult_ed25519_base_noclamp(left, signature + 32U) != 0 ||
        crypto_scalarmult_ed25519_noclamp(right,
                                         challenge,
                                         expected_public_key) != 0 ||
        sodium_memcmp(left, right, sizeof left) != 0)
        fail("identity-R signature does not satisfy [S]B=[h]A");

    sodium_memzero(secret_key, sizeof secret_key);
    sodium_memzero(expanded_seed, sizeof expanded_seed);
    sodium_memzero(seed, sizeof seed);
}

static void
exercise_bit_flips(const unsigned char public_key[OFARM_ED25519_PUBLIC_KEY_BYTES],
                   const unsigned char preflight[43],
                   const unsigned char signature[OFARM_ED25519_SIGNATURE_BYTES])
{
    unsigned char changed_public_key[OFARM_ED25519_PUBLIC_KEY_BYTES];
    unsigned char changed_preflight[43];
    unsigned char changed_signature[OFARM_ED25519_SIGNATURE_BYTES];
    size_t bit;

    for (bit = 0; bit < sizeof changed_public_key * 8U; bit++) {
        (void) memcpy(changed_public_key, public_key, sizeof changed_public_key);
        changed_public_key[bit / 8U] ^= (unsigned char) (1U << (bit % 8U));
        expect_result("public-key bit flip accepted",
                      changed_public_key, sizeof changed_public_key,
                      preflight, 43U, signature, OFARM_ED25519_SIGNATURE_BYTES,
                      OFARM_ED25519_REFUSED);
    }

    for (bit = 0; bit < sizeof changed_preflight * 8U; bit++) {
        (void) memcpy(changed_preflight, preflight, sizeof changed_preflight);
        changed_preflight[bit / 8U] ^= (unsigned char) (1U << (bit % 8U));
        expect_result("message bit flip accepted",
                      public_key, OFARM_ED25519_PUBLIC_KEY_BYTES,
                      changed_preflight, sizeof changed_preflight,
                      signature, OFARM_ED25519_SIGNATURE_BYTES,
                      OFARM_ED25519_REFUSED);
    }

    for (bit = 0; bit < sizeof changed_signature * 8U; bit++) {
        (void) memcpy(changed_signature, signature, sizeof changed_signature);
        changed_signature[bit / 8U] ^= (unsigned char) (1U << (bit % 8U));
        expect_result("signature bit flip accepted",
                      public_key, OFARM_ED25519_PUBLIC_KEY_BYTES,
                      preflight, 43U, changed_signature,
                      sizeof changed_signature,
                      OFARM_ED25519_REFUSED);
    }
}

static void
exercise_every_message_length(void)
{
    const ofarm_ed25519_vector_case *identity_proof =
        find_vector(OFARM_ED25519_IDENTITY_R_PROOF_CASE_ID);
    static const unsigned char empty[1] = {0};
    unsigned char seed[crypto_sign_SEEDBYTES];
    unsigned char public_key[crypto_sign_PUBLICKEYBYTES];
    unsigned char expected_public_key[crypto_sign_PUBLICKEYBYTES];
    unsigned char secret_key[crypto_sign_SECRETKEYBYTES];
    unsigned char signature[crypto_sign_BYTES];
    size_t length;

    decode_hex(OFARM_ED25519_IDENTITY_R_PROOF_SEED_HEX, seed, sizeof seed);
    decode_hex(identity_proof->public_key_hex, expected_public_key,
               sizeof expected_public_key);
    if (crypto_sign_seed_keypair(public_key, secret_key, seed) != 0)
        fail("deterministic test key generation failed");
    if (sodium_memcmp(public_key, expected_public_key,
                      sizeof expected_public_key) != 0)
        fail("deterministic test public key changed");

    for (length = 0; length <= OFARM_ED25519_MAX_SIGNED_BYTES; length++) {
        unsigned char *message = (unsigned char *) malloc(length);
        const unsigned char *signing_message;
        unsigned long long signature_length = 0;
        size_t index;

        if (message == NULL && length != 0U)
            fail("deterministic exact-sized message allocation failed");
        for (index = 0; index < length; index++)
            message[index] = (unsigned char) ((length * 17U + index * 131U) & 0xffU);
        signing_message = length == 0U ? empty : message;
        if (crypto_sign_detached(signature,
                                 &signature_length,
                                 signing_message,
                                 (unsigned long long) length,
                                 secret_key) != 0 ||
            signature_length != OFARM_ED25519_SIGNATURE_BYTES)
            fail("deterministic length signature failed");
        expect_result("deterministic signed length refused",
                      public_key, sizeof public_key,
                      signing_message, length,
                      signature, sizeof signature,
                      OFARM_ED25519_VERIFIED);
        free(message);
    }

    sodium_memzero(signature, sizeof signature);
    sodium_memzero(secret_key, sizeof secret_key);
    sodium_memzero(seed, sizeof seed);
}

int
main(void)
{
    unsigned char public_key[OFARM_ED25519_PUBLIC_KEY_BYTES];
    unsigned char rfc_signature[OFARM_ED25519_SIGNATURE_BYTES];
    unsigned char preflight[43];
    unsigned char preflight_signature[OFARM_ED25519_SIGNATURE_BYTES];

    if (sodium_init() < 0)
        fail("libsodium initialization failed");

    exercise_canonical_cases();
    exercise_known_answers(public_key,
                           rfc_signature,
                           preflight,
                           preflight_signature);
    exercise_length_boundaries(public_key, rfc_signature);
    exercise_identity_r_equation_proof();
    exercise_bit_flips(public_key, preflight, preflight_signature);
    exercise_every_message_length();

    (void) puts("ofarm_ed25519_harness: ok");
    return EXIT_SUCCESS;
}
