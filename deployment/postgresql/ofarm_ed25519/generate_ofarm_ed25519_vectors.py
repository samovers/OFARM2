#!/usr/bin/env python3
"""Validate and render the frozen OFARM Ed25519 adversarial corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "ofarm_ed25519_vectors.json"
DIGEST_PATH = ROOT / "ofarm_ed25519_vectors.sha256"
HEADER_PATH = ROOT / "ofarm_ed25519_vectors.h"
SQL_PATH = ROOT / "ofarm_ed25519_vectors.sql"
MAX_MANIFEST_BYTES = 256 * 1024
LOWER_HEX = re.compile(r"(?:[0-9a-f]{2})*\Z")
REQUIRED_CATEGORIES = [
    "rfc-positive",
    "preflight-positive",
    "negative-zero",
    "identity-r-valid-equation",
    "subgroup-point",
    "noncanonical-point",
    "scalar-s-equals-l",
    "scalar-s-greater-than-l",
    "scalar-high-bit",
    "zero",
    "bit-flips",
    "boundaries",
]
CASE_KEYS = {
    "id",
    "categories",
    "expected",
    "publicKeyHex",
    "signedBytesHex",
    "signatureHex",
}
ED25519_L = 2**252 + 27742317777372353535851937790883648493


class CorpusError(RuntimeError):
    """Raised when the checked-in vector authority is malformed or stale."""


def _duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CorpusError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _read_regular(path: Path, maximum: int) -> bytes:
    file_stat = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(file_stat.st_mode):
        raise CorpusError(f"{path.name} must be one regular file")
    if file_stat.st_size > maximum:
        raise CorpusError(f"{path.name} exceeds its byte limit")
    return path.read_bytes()


def _manifest() -> tuple[dict[str, Any], bytes, str]:
    raw = _read_regular(MANIFEST_PATH, MAX_MANIFEST_BYTES)
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_duplicate_keys,
            parse_constant=lambda number: (_ for _ in ()).throw(
                CorpusError(f"forbidden JSON number {number}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusError("vector manifest is not canonical ASCII JSON") from exc
    if not isinstance(value, dict):
        raise CorpusError("vector manifest must be one JSON object")
    return value, raw, hashlib.sha256(raw).hexdigest()


def _hex(value: Any, label: str, *, exact_bytes: int | None = None) -> str:
    if not isinstance(value, str) or LOWER_HEX.fullmatch(value) is None:
        raise CorpusError(f"{label} is not lowercase even-length hexadecimal")
    if exact_bytes is not None and len(value) != exact_bytes * 2:
        raise CorpusError(f"{label} is not exactly {exact_bytes} bytes")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
        or len(set(value)) != len(value)
    ):
        raise CorpusError(f"{label} is not a unique non-empty string list")
    return value


def _integer_list(value: Any, label: str) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or not all(
            isinstance(item, int) and not isinstance(item, bool) and item >= 0
            for item in value
        )
        or value != sorted(set(value))
    ):
        raise CorpusError(f"{label} is not a sorted unique integer list")
    return value


def _validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if set(manifest) != {
        "schemaVersion",
        "requiredCategories",
        "cases",
        "families",
        "identityRProof",
    }:
        raise CorpusError("vector manifest top-level fields are not exact")
    if manifest.get("schemaVersion") != "ofarm.ed25519-adversarial-vectors.v1":
        raise CorpusError("vector manifest schema is not exact")
    if manifest.get("requiredCategories") != REQUIRED_CATEGORIES:
        raise CorpusError("required vector category inventory is not exact")

    raw_cases = manifest.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise CorpusError("vector cases are absent")
    cases: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    observed_categories: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict) or set(raw_case) != CASE_KEYS:
            raise CorpusError("vector case fields are not exact")
        identifier = raw_case.get("id")
        if (
            not isinstance(identifier, str)
            or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier) is None
            or identifier in identifiers
        ):
            raise CorpusError("vector case identifier is invalid or duplicated")
        identifiers.add(identifier)
        categories = _string_list(raw_case.get("categories"), f"{identifier} categories")
        if any(category not in REQUIRED_CATEGORIES for category in categories):
            raise CorpusError(f"{identifier} names an unknown category")
        observed_categories.update(categories)
        expected = raw_case.get("expected")
        if expected not in {"verified", "refused"}:
            raise CorpusError(f"{identifier} expected result is invalid")
        _hex(raw_case.get("publicKeyHex"), f"{identifier} public key", exact_bytes=32)
        signed_bytes = _hex(raw_case.get("signedBytesHex"), f"{identifier} signed bytes")
        if len(signed_bytes) > 8192 * 2:
            raise CorpusError(f"{identifier} signed bytes exceed the verifier limit")
        _hex(raw_case.get("signatureHex"), f"{identifier} signature", exact_bytes=64)
        cases.append(raw_case)

    families = manifest.get("families")
    if not isinstance(families, dict) or set(families) != {"bitFlips", "boundaries"}:
        raise CorpusError("vector family inventory is not exact")
    bit_flips = families["bitFlips"]
    if (
        not isinstance(bit_flips, dict)
        or set(bit_flips) != {"categories", "baseCaseId", "arguments"}
        or bit_flips.get("categories") != ["bit-flips"]
        or bit_flips.get("baseCaseId") not in identifiers
        or bit_flips.get("arguments") != ["publicKey", "signedBytes", "signature"]
    ):
        raise CorpusError("bit-flip family is not exact")
    observed_categories.update(bit_flips["categories"])

    boundaries = families["boundaries"]
    if not isinstance(boundaries, dict) or set(boundaries) != {
        "categories",
        "publicKeyLengths",
        "signedBytesLengths",
        "signatureLengths",
        "sqlIterations",
        "cIterations",
        "lcgSeed",
        "xorshiftSeedHex",
    }:
        raise CorpusError("boundary family fields are not exact")
    if boundaries.get("categories") != ["boundaries"]:
        raise CorpusError("boundary category is not exact")
    observed_categories.update(boundaries["categories"])
    public_key_lengths = _integer_list(
        boundaries.get("publicKeyLengths"), "public-key boundary lengths"
    )
    signed_bytes_lengths = _integer_list(
        boundaries.get("signedBytesLengths"), "signed-bytes boundary lengths"
    )
    signature_lengths = _integer_list(
        boundaries.get("signatureLengths"), "signature boundary lengths"
    )
    if not {31, 32, 33}.issubset(public_key_lengths):
        raise CorpusError("public-key boundary inventory is incomplete")
    if not {8191, 8192, 8193}.issubset(signed_bytes_lengths):
        raise CorpusError("signed-bytes boundary inventory is incomplete")
    if not {63, 64, 65}.issubset(signature_lengths):
        raise CorpusError("signature boundary inventory is incomplete")
    if boundaries.get("sqlIterations") != 4096:
        raise CorpusError("SQL fuzz iteration count is not exact")
    if boundaries.get("cIterations") != 16384:
        raise CorpusError("C fuzz iteration count is not exact")
    if boundaries.get("lcgSeed") != 1327217885:
        raise CorpusError("SQL fuzz seed is not exact")
    _hex(boundaries.get("xorshiftSeedHex"), "C fuzz seed", exact_bytes=8)

    if observed_categories != set(REQUIRED_CATEGORIES):
        raise CorpusError("required vector categories are not all exercised")

    proof = manifest.get("identityRProof")
    if not isinstance(proof, dict) or set(proof) != {
        "caseId",
        "seedHex",
        "clampedScalarHex",
        "reducedChallengeHex",
        "equation",
    }:
        raise CorpusError("identity-R proof fields are not exact")
    if proof.get("equation") != "[S]B=[h]A":
        raise CorpusError("identity-R equation label is not exact")
    proof_cases = [case for case in cases if case["id"] == proof.get("caseId")]
    if len(proof_cases) != 1:
        raise CorpusError("identity-R proof case is absent")
    proof_case = proof_cases[0]
    seed = bytes.fromhex(_hex(proof.get("seedHex"), "identity-R seed", exact_bytes=32))
    digest = bytearray(hashlib.sha512(seed).digest()[:32])
    digest[0] &= 248
    digest[31] &= 63
    digest[31] |= 64
    if digest.hex() != _hex(
        proof.get("clampedScalarHex"), "identity-R clamped scalar", exact_bytes=32
    ):
        raise CorpusError("identity-R clamped scalar derivation differs")
    signature = bytes.fromhex(proof_case["signatureHex"])
    public_key = bytes.fromhex(proof_case["publicKeyHex"])
    signed_bytes = bytes.fromhex(proof_case["signedBytesHex"])
    identity = b"\x01" + b"\x00" * 31
    if signature[:32] != identity:
        raise CorpusError("identity-R proof does not use the identity encoding")
    challenge = int.from_bytes(
        hashlib.sha512(identity + public_key + signed_bytes).digest(), "little"
    ) % ED25519_L
    challenge_bytes = challenge.to_bytes(32, "little")
    if challenge_bytes.hex() != _hex(
        proof.get("reducedChallengeHex"),
        "identity-R reduced challenge",
        exact_bytes=32,
    ):
        raise CorpusError("identity-R reduced challenge derivation differs")
    scalar = int.from_bytes(digest, "little")
    expected_s = (challenge * scalar % ED25519_L).to_bytes(32, "little")
    if signature[32:] != expected_s:
        raise CorpusError("identity-R signature does not satisfy S=h*a mod L")
    return cases


def _c_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _render_header(
    manifest: dict[str, Any], cases: list[dict[str, Any]], digest: str
) -> bytes:
    boundaries = manifest["families"]["boundaries"]
    proof = manifest["identityRProof"]
    lines = [
        "/* Generated by generate_ofarm_ed25519_vectors.py; do not edit. */",
        "#ifndef OFARM_ED25519_VECTORS_H",
        "#define OFARM_ED25519_VECTORS_H",
        "",
        f'#define OFARM_ED25519_VECTOR_CORPUS_SHA256 "sha256:{digest}"',
        f"#define OFARM_ED25519_VECTOR_CASE_COUNT {len(cases)}U",
        f"#define OFARM_ED25519_VECTOR_SQL_FUZZ_CASES {boundaries['sqlIterations']}U",
        f"#define OFARM_ED25519_VECTOR_C_FUZZ_CASES {boundaries['cIterations']}U",
        f"#define OFARM_ED25519_VECTOR_LCG_SEED {boundaries['lcgSeed']}U",
        (
            "#define OFARM_ED25519_VECTOR_XORSHIFT_SEED UINT64_C(0x"
            f"{boundaries['xorshiftSeedHex']})"
        ),
        "",
        "#ifdef OFARM_ED25519_VECTOR_DEFINE_CASES",
        "typedef struct ofarm_ed25519_vector_case",
        "{",
        "    const char *identifier;",
        "    const char *public_key_hex;",
        "    const char *signed_bytes_hex;",
        "    const char *signature_hex;",
        "    int expected_verified;",
        "} ofarm_ed25519_vector_case;",
        "",
        "static const ofarm_ed25519_vector_case OFARM_ED25519_VECTOR_CASES[] = {",
    ]
    for case in cases:
        lines.extend(
            [
                "    {",
                f"        {_c_string(case['id'])},",
                f"        {_c_string(case['publicKeyHex'])},",
                f"        {_c_string(case['signedBytesHex'])},",
                f"        {_c_string(case['signatureHex'])},",
                "        1" if case["expected"] == "verified" else "        0",
                "    },",
            ]
        )
    lines.extend(
        [
            "};",
            "#endif",
            "",
            "#ifdef OFARM_ED25519_VECTOR_DEFINE_BOUNDARIES",
        ]
    )
    for macro, key in (
        ("PUBLIC_KEY", "publicKeyLengths"),
        ("SIGNED_BYTES", "signedBytesLengths"),
        ("SIGNATURE", "signatureLengths"),
    ):
        values = boundaries[key]
        lines.extend(
            [
                (
                    f"static const size_t OFARM_ED25519_VECTOR_{macro}_LENGTHS[] = "
                    "{" + ", ".join(f"{value}U" for value in values) + "};"
                ),
                (
                    f"#define OFARM_ED25519_VECTOR_{macro}_LENGTH_COUNT "
                    f"{len(values)}U"
                ),
            ]
        )
    lines.extend(
        [
            "#endif",
            "",
            "#ifdef OFARM_ED25519_VECTOR_DEFINE_IDENTITY_R_PROOF",
            (
                "#define OFARM_ED25519_IDENTITY_R_PROOF_CASE_ID "
                f"{_c_string(proof['caseId'])}"
            ),
            (
                "#define OFARM_ED25519_IDENTITY_R_PROOF_SEED_HEX "
                f"{_c_string(proof['seedHex'])}"
            ),
            (
                "#define OFARM_ED25519_IDENTITY_R_PROOF_CHALLENGE_HEX "
                f"{_c_string(proof['reducedChallengeHex'])}"
            ),
            (
                "#define OFARM_ED25519_IDENTITY_R_PROOF_CLAMPED_SCALAR_HEX "
                f"{_c_string(proof['clampedScalarHex'])}"
            ),
            "#endif",
            "",
            "#endif",
            "",
        ]
    )
    return "\n".join(lines).encode("ascii")


def _sql_array(values: list[int]) -> str:
    return "ARRAY[" + ", ".join(str(value) for value in values) + "]"


def _render_sql(
    manifest: dict[str, Any], cases: list[dict[str, Any]], digest: str
) -> bytes:
    boundaries = manifest["families"]["boundaries"]
    base_identifier = manifest["families"]["bitFlips"]["baseCaseId"]
    base = next(case for case in cases if case["id"] == base_identifier)
    values = []
    for case in cases:
        values.append(
            "        ("
            f"'{case['id']}', "
            f"decode('{case['publicKeyHex']}', 'hex'), "
            f"decode('{case['signedBytesHex']}', 'hex'), "
            f"decode('{case['signatureHex']}', 'hex'), "
            f"{'true' if case['expected'] == 'verified' else 'false'}"
            ")"
        )
    sql = f"""-- Generated by generate_ofarm_ed25519_vectors.py; do not edit.
-- Corpus SHA-256: sha256:{digest}

DO $ofarm_canonical_vectors$
DECLARE
    vector record;
    observed boolean;
    altered bytea;
    byte_index integer;
    bit_index integer;
    public_key bytea := decode('{base['publicKeyHex']}', 'hex');
    signed_bytes bytea := decode('{base['signedBytesHex']}', 'hex');
    signature bytea := decode('{base['signatureHex']}', 'hex');
BEGIN
    FOR vector IN
        SELECT *
        FROM (VALUES
{',\n'.join(values)}
        ) AS corpus(identifier, public_key, signed_bytes, signature, expected)
    LOOP
        observed := ofarm_crypto.ed25519_verify(
            vector.public_key, vector.signed_bytes, vector.signature
        );
        IF observed IS DISTINCT FROM vector.expected THEN
            RAISE EXCEPTION 'canonical Ed25519 vector % disagreed',
                vector.identifier;
        END IF;
    END LOOP;

    FOR byte_index IN 0..octet_length(public_key) - 1 LOOP
        FOR bit_index IN 0..7 LOOP
            altered := set_byte(
                public_key,
                byte_index,
                get_byte(public_key, byte_index) # (1 << bit_index)
            );
            IF ofarm_crypto.ed25519_verify(
                altered, signed_bytes, signature
            ) IS DISTINCT FROM false THEN
                RAISE EXCEPTION 'canonical public-key bit flip accepted';
            END IF;
        END LOOP;
    END LOOP;
    FOR byte_index IN 0..octet_length(signed_bytes) - 1 LOOP
        FOR bit_index IN 0..7 LOOP
            altered := set_byte(
                signed_bytes,
                byte_index,
                get_byte(signed_bytes, byte_index) # (1 << bit_index)
            );
            IF ofarm_crypto.ed25519_verify(
                public_key, altered, signature
            ) IS DISTINCT FROM false THEN
                RAISE EXCEPTION 'canonical signed-bytes bit flip accepted';
            END IF;
        END LOOP;
    END LOOP;
    FOR byte_index IN 0..octet_length(signature) - 1 LOOP
        FOR bit_index IN 0..7 LOOP
            altered := set_byte(
                signature,
                byte_index,
                get_byte(signature, byte_index) # (1 << bit_index)
            );
            IF ofarm_crypto.ed25519_verify(
                public_key, signed_bytes, altered
            ) IS DISTINCT FROM false THEN
                RAISE EXCEPTION 'canonical signature bit flip accepted';
            END IF;
        END LOOP;
    END LOOP;

    IF ofarm_crypto.ed25519_verify(
        substring(public_key FROM 1 FOR 31), signed_bytes, signature
    ) IS DISTINCT FROM false
        OR ofarm_crypto.ed25519_verify(
            public_key || decode('00', 'hex'), signed_bytes, signature
        ) IS DISTINCT FROM false
        OR ofarm_crypto.ed25519_verify(
            public_key, signed_bytes, substring(signature FROM 1 FOR 63)
        ) IS DISTINCT FROM false
        OR ofarm_crypto.ed25519_verify(
            public_key, signed_bytes, signature || decode('00', 'hex')
        ) IS DISTINCT FROM false
        OR ofarm_crypto.ed25519_verify(
            public_key, decode(repeat('00', 8193), 'hex'), signature
        ) IS DISTINCT FROM false
        OR ofarm_crypto.ed25519_verify(
            public_key, decode(repeat('00', 8192), 'hex'), signature
        ) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'canonical direct length boundary was not refused';
    END IF;
END
$ofarm_canonical_vectors$;

DO $ofarm_canonical_boundary_fuzz$
DECLARE
    public_key_lengths integer[] := {_sql_array(boundaries['publicKeyLengths'])};
    signed_bytes_lengths integer[] := {_sql_array(boundaries['signedBytesLengths'])};
    signature_lengths integer[] := {_sql_array(boundaries['signatureLengths'])};
    state bigint := {boundaries['lcgSeed']};
    public_key_length integer;
    signed_bytes_length integer;
    signature_length integer;
    fill_octet text;
    iteration integer;
    observed boolean;
BEGIN
    FOR iteration IN 1..{boundaries['sqlIterations']} LOOP
        state := (state * 48271) % 2147483647;
        public_key_length := public_key_lengths[
            1 + (state % array_length(public_key_lengths, 1))::integer
        ];
        state := (state * 48271) % 2147483647;
        signed_bytes_length := signed_bytes_lengths[
            1 + (state % array_length(signed_bytes_lengths, 1))::integer
        ];
        state := (state * 48271) % 2147483647;
        signature_length := signature_lengths[
            1 + (state % array_length(signature_lengths, 1))::integer
        ];
        state := (state * 48271) % 2147483647;
        fill_octet := lpad(to_hex((state % 256)::integer), 2, '0');

        observed := ofarm_crypto.ed25519_verify(
            decode(repeat(fill_octet, public_key_length), 'hex'),
            decode(repeat(fill_octet, signed_bytes_length), 'hex'),
            decode(repeat(fill_octet, signature_length), 'hex')
        );
        IF observed IS DISTINCT FROM false THEN
            RAISE EXCEPTION
                'canonical SQL boundary fuzz case % was not refused', iteration;
        END IF;
    END LOOP;
END
$ofarm_canonical_boundary_fuzz$;
"""
    return sql.encode("ascii")


def _expected_outputs() -> dict[Path, bytes]:
    manifest, _, digest = _manifest()
    cases = _validate_manifest(manifest)
    digest_receipt = f"{digest}  {MANIFEST_PATH.name}\n".encode("ascii")
    return {
        DIGEST_PATH: digest_receipt,
        HEADER_PATH: _render_header(manifest, cases, digest),
        SQL_PATH: _render_sql(manifest, cases, digest),
    }


def _write_or_check(*, check: bool) -> None:
    for path, expected in _expected_outputs().items():
        if check:
            try:
                actual = _read_regular(path, max(len(expected), 1024 * 1024))
            except OSError as exc:
                raise CorpusError(f"generated file {path.name} is absent") from exc
            if actual != expected:
                raise CorpusError(f"generated file {path.name} is stale")
        else:
            path.write_bytes(expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        _write_or_check(check=args.check)
    except (CorpusError, OSError) as exc:
        raise SystemExit(f"Ed25519 vector corpus refused: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
