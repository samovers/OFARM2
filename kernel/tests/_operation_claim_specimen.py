"""The independent fictional input selection for the transaction collector."""

import base64
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

from kernel.runtime_bundle import canonical_json_bytes

FIXTURES = Path(__file__).parent / "fixtures" / "operation_claim_transaction"
SELECTION_HASH = "639d5bfc1bf786834b39e5c55e5ab425e7c69359e5642c3fe1c31bce167958c4"
STATE_CONTRACT_HASH = "4f7cabc08dfc18401d0b8a753f42ef11849b626c6c690dba381e74f6513db4c2"


class CaptureRefused(ValueError):
    """The test source cannot attest the requested observation."""


def raw_hash(raw):
    return sha256(raw).hexdigest()


def original(raw):
    return {"originalBytesBase64": base64.b64encode(raw).decode("ascii")}


def unpack(value):
    return base64.b64decode(value["originalBytesBase64"], validate=True)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def binding(ref, document):
    # Generated storage documents have ASCII keys and only string/integer metadata.
    # The independently supplied source digests are checked by the owning verifier.
    return {"ref": ref, "digest": "sha256:" + raw_hash(canonical_json_bytes(document))}


def selection():
    raw = (FIXTURES / "selection.json").read_bytes()
    if raw_hash(raw) != SELECTION_HASH:
        raise CaptureRefused("Independent submission selection changed")
    return json.loads(raw)


def original_sources(case):
    with ZipFile(FIXTURES / "originals.zip") as archive:
        rows = {ref: archive.read(pin["sha256"]) for ref, pin in case["sources"].items()}
    if any(raw_hash(raw) != case["sources"][ref]["sha256"] for ref, raw in rows.items()):
        raise CaptureRefused("Original source bytes differ from the independent selection")
    return rows


def owner_arguments(template, rows):
    if isinstance(template, dict):
        if set(template) == {"originalRef"}:
            return original(rows[template["originalRef"]])
        return {k: owner_arguments(v, rows) for k, v in template.items()}
    if isinstance(template, list):
        return [owner_arguments(v, rows) for v in template]
    return template


def check_owner_subject(case, owners, intent_raw, proposed_raw):
    """Link owner arguments to the selected submission before offering them to #47."""
    result = json.loads(proposed_raw)
    intent = json.loads(intent_raw)
    if (
        result.get("assertionRecordId") != case["assertionId"]
        or intent["effectSubject"]["subjectRef"] != case["assertionId"]
        or result["claimState"] != "PENDING_REVIEW"
    ):
        raise CaptureRefused("Proposed pending assertion identity differs")
    if "authorization" in owners:
        auth = owners["authorization"]
        sources = auth["source_bytes"]
        decision = json.loads(unpack(sources["RESULT"]))["projection"]
        if (
            unpack(sources["EFFECT_INTENT"]) != intent_raw
            or raw_hash(unpack(auth["context_bytes"])) != auth["expected_context_sha256"]
            or decision["actionClass"] != case["action"]
            or decision["selectedPath"]["authoritySubjectPartyRef"] != result["assertedByPartyRef"]
        ):
            raise CaptureRefused("Authorization differs from the selected intent, action or party")
    if "act" in owners:
        act = owners["act"]
        context = json.loads(unpack(act["context_bytes"]))
        if (
            context["intentBytesSha256"] != raw_hash(intent_raw)
            or json.loads(unpack(act["act_bytes"]))["accountablePartyRef"] != result["assertedByPartyRef"]
        ):
            raise CaptureRefused("Assertion act differs from the selected intent or accountable party")
    return sorted(set(case["requiredOwnerInputs"]) - owners.keys())
