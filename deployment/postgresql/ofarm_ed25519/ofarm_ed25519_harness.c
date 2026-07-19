#include "ofarm_ed25519_core.h"

#include <sodium.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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
    unsigned char *copy = (unsigned char *) malloc(length);

    if (copy == NULL && length != 0U)
        fail("exact-sized allocation failed");
    if (length != 0U)
        (void) memcpy(copy, source, length);
    return copy;
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
exercise_known_answers(unsigned char public_key[OFARM_ED25519_PUBLIC_KEY_BYTES],
                       unsigned char rfc_signature[OFARM_ED25519_SIGNATURE_BYTES],
                       unsigned char preflight[43],
                       unsigned char preflight_signature[OFARM_ED25519_SIGNATURE_BYTES])
{
    static const unsigned char empty[1] = {0};

    decode_hex(
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        public_key,
        OFARM_ED25519_PUBLIC_KEY_BYTES);
    decode_hex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
        rfc_signature,
        OFARM_ED25519_SIGNATURE_BYTES);
    decode_hex(
        "004f4641524d322d54454e414e542d4341504142494c4954592d4b4d532d5052"
        "45464c494748542d563100",
        preflight,
        43U);
    decode_hex(
        "b8c5d75bfcdfaf6c33ae31eb6dba6f47ae6a7c11d925982ffbc00d2897a15c1b"
        "dee4b25b894d6a64f22466d698d536bc5a87fa0650ead4da5cc6496154ffe102",
        preflight_signature,
        OFARM_ED25519_SIGNATURE_BYTES);

    expect_result("RFC 8032 empty-message vector refused",
                  public_key,
                  OFARM_ED25519_PUBLIC_KEY_BYTES,
                  empty,
                  0U,
                  rfc_signature,
                  OFARM_ED25519_SIGNATURE_BYTES,
                  OFARM_ED25519_VERIFIED);
    expect_result("fixed preflight vector refused",
                  public_key,
                  OFARM_ED25519_PUBLIC_KEY_BYTES,
                  preflight,
                  43U,
                  preflight_signature,
                  OFARM_ED25519_SIGNATURE_BYTES,
                  OFARM_ED25519_VERIFIED);
}

static void
exercise_length_boundaries(const unsigned char public_key[OFARM_ED25519_PUBLIC_KEY_BYTES],
                           const unsigned char signature[OFARM_ED25519_SIGNATURE_BYTES])
{
    unsigned char oversized_message[OFARM_ED25519_MAX_SIGNED_BYTES + 1U];
    unsigned char oversized_public_key[OFARM_ED25519_PUBLIC_KEY_BYTES + 1U];
    unsigned char oversized_signature[OFARM_ED25519_SIGNATURE_BYTES + 1U];

    (void) memset(oversized_message, 0x5a, sizeof oversized_message);
    (void) memcpy(oversized_public_key, public_key,
                  OFARM_ED25519_PUBLIC_KEY_BYTES);
    oversized_public_key[OFARM_ED25519_PUBLIC_KEY_BYTES] = 0;
    (void) memcpy(oversized_signature, signature,
                  OFARM_ED25519_SIGNATURE_BYTES);
    oversized_signature[OFARM_ED25519_SIGNATURE_BYTES] = 0;
    expect_result("31-byte public key accepted",
                  public_key, 31U, oversized_message, 1U,
                  signature, OFARM_ED25519_SIGNATURE_BYTES,
                  OFARM_ED25519_REFUSED);
    expect_result("33-byte public key accepted",
                  oversized_public_key, sizeof oversized_public_key,
                  oversized_message, 1U,
                  signature, OFARM_ED25519_SIGNATURE_BYTES,
                  OFARM_ED25519_REFUSED);
    expect_result("63-byte signature accepted",
                  public_key, OFARM_ED25519_PUBLIC_KEY_BYTES,
                  oversized_message, 1U, signature, 63U,
                  OFARM_ED25519_REFUSED);
    expect_result("65-byte signature accepted",
                  public_key, OFARM_ED25519_PUBLIC_KEY_BYTES,
                  oversized_message, 1U,
                  oversized_signature, sizeof oversized_signature,
                  OFARM_ED25519_REFUSED);
    expect_result("8193-byte message accepted",
                  public_key, OFARM_ED25519_PUBLIC_KEY_BYTES,
                  oversized_message, sizeof oversized_message,
                  signature, OFARM_ED25519_SIGNATURE_BYTES,
                  OFARM_ED25519_REFUSED);
}

static void
exercise_hostile_points_and_scalars(
    const unsigned char public_key[OFARM_ED25519_PUBLIC_KEY_BYTES],
    const unsigned char signature[OFARM_ED25519_SIGNATURE_BYTES])
{
    static const char *const point_hex[] = {
        "0000000000000000000000000000000000000000000000000000000000000000",
        "0100000000000000000000000000000000000000000000000000000000000000",
        "0200000000000000000000000000000000000000000000000000000000000000",
        "9599999999999999999999999999999999999999999999999999999999999999",
        "f5ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
        "f6ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f"
    };
    static const char scalar_l_hex[] =
        "edd3f55c1a631258d69cf7a2def9de1400000000000000000000000000000010";
    static const char scalar_over_l_hex[] =
        "eed3f55c1a631258d69cf7a2def9de1400000000000000000000000000000010";
    static const unsigned char empty[1] = {0};
    unsigned char point[OFARM_ED25519_PUBLIC_KEY_BYTES];
    unsigned char hostile_signature[OFARM_ED25519_SIGNATURE_BYTES];
    size_t index;

    for (index = 0; index < sizeof point_hex / sizeof point_hex[0]; index++) {
        decode_hex(point_hex[index], point, sizeof point);
        expect_result("hostile public-key point accepted",
                      point, sizeof point, empty, 0U,
                      signature, OFARM_ED25519_SIGNATURE_BYTES,
                      OFARM_ED25519_REFUSED);
        (void) memcpy(hostile_signature, signature, sizeof hostile_signature);
        (void) memcpy(hostile_signature, point, sizeof point);
        expect_result("hostile signature R point accepted",
                      public_key, OFARM_ED25519_PUBLIC_KEY_BYTES,
                      empty, 0U, hostile_signature, sizeof hostile_signature,
                      OFARM_ED25519_REFUSED);
    }

    (void) memcpy(hostile_signature, signature, sizeof hostile_signature);
    decode_hex(scalar_l_hex,
               hostile_signature + OFARM_ED25519_PUBLIC_KEY_BYTES,
               OFARM_ED25519_PUBLIC_KEY_BYTES);
    expect_result("signature scalar S=L accepted",
                  public_key, OFARM_ED25519_PUBLIC_KEY_BYTES,
                  empty, 0U, hostile_signature, sizeof hostile_signature,
                  OFARM_ED25519_REFUSED);

    decode_hex(scalar_over_l_hex,
               hostile_signature + OFARM_ED25519_PUBLIC_KEY_BYTES,
               OFARM_ED25519_PUBLIC_KEY_BYTES);
    expect_result("signature scalar S>L accepted",
                  public_key, OFARM_ED25519_PUBLIC_KEY_BYTES,
                  empty, 0U, hostile_signature, sizeof hostile_signature,
                  OFARM_ED25519_REFUSED);

    (void) memset(hostile_signature, 0, sizeof hostile_signature);
    expect_result("all-zero signature accepted",
                  public_key, OFARM_ED25519_PUBLIC_KEY_BYTES,
                  empty, 0U, hostile_signature, sizeof hostile_signature,
                  OFARM_ED25519_REFUSED);
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
    static const char seed_hex[] =
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60";
    static const char expected_public_key_hex[] =
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a";
    static const unsigned char empty[1] = {0};
    unsigned char seed[crypto_sign_SEEDBYTES];
    unsigned char public_key[crypto_sign_PUBLICKEYBYTES];
    unsigned char expected_public_key[crypto_sign_PUBLICKEYBYTES];
    unsigned char secret_key[crypto_sign_SECRETKEYBYTES];
    unsigned char signature[crypto_sign_BYTES];
    size_t length;

    decode_hex(seed_hex, seed, sizeof seed);
    decode_hex(expected_public_key_hex, expected_public_key,
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

    exercise_known_answers(public_key,
                           rfc_signature,
                           preflight,
                           preflight_signature);
    exercise_length_boundaries(public_key, rfc_signature);
    exercise_hostile_points_and_scalars(public_key, rfc_signature);
    exercise_bit_flips(public_key, preflight, preflight_signature);
    exercise_every_message_length();

    (void) puts("ofarm_ed25519_harness: ok");
    return EXIT_SUCCESS;
}
