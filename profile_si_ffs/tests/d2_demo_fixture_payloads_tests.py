"""D2c — SI demo payload builders are profile-local behind `kernel.demo`.

Engineering tests only. They compare the compatibility facade with the
profile-local payload helper for representative identity, structure, operation,
and submission payloads.
"""
from __future__ import annotations

from kernel import config, demo
from profile_si_ffs.test_fixtures import demo_payloads


__all__ = [
    "test_d2_identity_payload_facades_match_profile_helpers",
    "test_d2_structure_submission_facade_matches_profile_helper",
    "test_d2_spray_payload_and_submission_facades_match_profile_helpers",
]


FIXED_NOW = "2099-03-04T05:06:07Z"


def _refs() -> demo_payloads.DemoPayloadRefs:
    return demo_payloads.refs_from_module(
        demo,
        code_binding_profile_ref=config.CODE_BINDING_PROFILE_REF,
    )


def test_d2_identity_payload_facades_match_profile_helpers(monkeypatch):
    monkeypatch.setattr(demo, "now_iso", lambda: FIXED_NOW)
    refs = _refs()

    assert demo.farm_identity_payload("farm-payload:x") == \
        demo_payloads.farm_identity_payload(
            payload_id="farm-payload:x", recorded_at=FIXED_NOW, refs=refs)
    assert demo.field_identity_payload(
        "field-payload:x", display_name="Field X", area_value=2.5) == \
        demo_payloads.field_identity_payload(
            payload_id="field-payload:x", recorded_at=FIXED_NOW, refs=refs,
            display_name="Field X", area_value=2.5)
    assert demo.cropcycle_identity_payload("cycle-payload:x", auto_created=False) == \
        demo_payloads.cropcycle_identity_payload(
            payload_id="cycle-payload:x", recorded_at=FIXED_NOW, refs=refs,
            auto_created=False)
    assert demo.equipment_identity_payload("equipment-payload:x") == \
        demo_payloads.equipment_identity_payload(
            payload_id="equipment-payload:x", recorded_at=FIXED_NOW, refs=refs)
    assert demo.appliedresource_identity_payload("resource-payload:x") == \
        demo_payloads.appliedresource_identity_payload(
            payload_id="resource-payload:x", recorded_at=FIXED_NOW, refs=refs)


def test_d2_structure_submission_facade_matches_profile_helper(monkeypatch):
    monkeypatch.setattr(demo, "now_iso", lambda: FIXED_NOW)
    refs = _refs()
    payload = demo.farm_identity_payload("farm-payload:structure")

    assert demo.structure_submission(
        payload,
        idem_key="idem:structure",
        actor_ref=demo.ADVISOR,
        confirm=False,
        supersedes="consequence:old",
        event_time="2099-03-05T00:00:00Z",
        evidence_refs=["evidence:custom"],
    ) == demo_payloads.structure_submission(
        payload,
        idem_key="idem:structure",
        refs=refs,
        actor_ref=demo.ADVISOR,
        confirm=False,
        supersedes="consequence:old",
        event_time="2099-03-05T00:00:00Z",
        evidence_refs=["evidence:custom"],
    )


def test_d2_spray_payload_and_submission_facades_match_profile_helpers():
    refs = _refs()
    kwargs = {
        "event_start": "2099-04-01T06:00:00Z",
        "event_end": "2099-04-01T07:00:00Z",
        "binding_refs": [demo.PRODUCT_BINDING],
        "evidence_refs": [demo.PHOTO_EVIDENCE],
        "dose_value": 0.7,
        "unit_ref": "scheme:ucum:mL/har",
    }

    assert demo.spray_payload(
        "erp:payload",
        actor_ref=demo.WORKER,
        **kwargs,
    ) == demo_payloads.spray_payload(
        erp_id="erp:payload",
        refs=refs,
        actor_ref=demo.WORKER,
        **kwargs,
    )
    assert demo.spray_submission(
        "idem:spray",
        actor_ref=demo.WORKER,
        confirm=False,
        erp_id="erp:submission",
        channel="API",
        **kwargs,
    ) == demo_payloads.spray_submission(
        idem_key="idem:spray",
        refs=refs,
        actor_ref=demo.WORKER,
        confirm=False,
        erp_id="erp:submission",
        channel="API",
        payload_kwargs=kwargs,
    )
