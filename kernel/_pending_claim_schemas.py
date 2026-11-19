"""The fixed v0.1 wire contracts used by the pending-claim promotion producer."""
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from .runtime_bundle import sha256_bytes, strict_json_document


PROMOTION_TRACE_SCHEMA_DIGEST = "sha256:07c073fba6fa023e4463339a383d4b0d881be38c17d626ec7d27caaa688d4e3f"
_SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "contracts" / "kernel"
_SCHEMAS = {
    "ofarm.commitingressrequest.v0.1": (
        "OFARM_CommitIngressRequest_schema_v0_1.json",
        "sha256:397ec3a61ed572b14f9916bc9e7b316ff48150c743c6b7aa2eab94a3be3e8ffc",
    ),
    "ofarm.semanticeventenvelope.v0.1": (
        "OFARM_SemanticEventEnvelope_schema_v0_1.json",
        "sha256:75662a6c4952a62b7e8f8e9de99c23c98899c692914a98ba4b752873f48bd1a4",
    ),
    "ofarm.promotiontrace.v0.1": (
        "OFARM_PromotionTrace_schema_v0_1.json", PROMOTION_TRACE_SCHEMA_DIGEST,
    ),
}


@cache
def _validator(kind: str) -> Draft202012Validator:
    filename, digest = _SCHEMAS[kind]
    raw = (_SCHEMA_ROOT / filename).read_bytes()
    if sha256_bytes(raw) != digest:
        raise ValueError("pending claim schema digest differs")
    schema, _ = strict_json_document(raw, filename)
    return Draft202012Validator(schema, format_checker=FormatChecker(formats=["date-time"]))


def validate_document(kind: str, document: dict) -> None:
    try:
        _validator(kind).validate(document)
    except ValidationError:
        raise ValueError(f"invalid {kind} document") from None
