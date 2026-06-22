"""D2c/D2d — SI demo payload builders are profile-local behind `kernel.demo`.

Engineering tests only. They compare the compatibility facade with the
profile-local payload helper for representative identity, structure, operation,
and submission payloads, and pin the D2d profile-local test facade against the
public `kernel.demo` compatibility facade.
"""
from __future__ import annotations

from kernel import config, demo
from profile_si_ffs.test_fixtures import demo as profile_demo
from profile_si_ffs.test_fixtures import demo_payloads, demo_refs


__all__ = [
    "test_d2_identity_payload_facades_match_profile_helpers",
    "test_d2_structure_submission_facade_matches_profile_helper",
    "test_d2_spray_payload_and_submission_facades_match_profile_helpers",
    "test_d2d_profile_demo_facade_matches_kernel_demo",
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


def test_d2d_profile_demo_facade_matches_kernel_demo(monkeypatch):
    monkeypatch.setattr(demo, "now_iso", lambda: FIXED_NOW)
    monkeypatch.setattr(profile_demo, "now_iso", lambda: FIXED_NOW)

    for name in demo_refs.DEMO_REF_NAMES:
        assert name in profile_demo.__all__
        assert getattr(profile_demo, name) == getattr(demo, name)

    assert profile_demo.substrate_records() == demo.substrate_records()

    assert profile_demo.farm_identity_payload("farm-payload:d2d") == \
        demo.farm_identity_payload("farm-payload:d2d")
    assert profile_demo.field_identity_payload(
        "field-payload:d2d", display_name="D2d Field", area_value=3.2) == \
        demo.field_identity_payload(
            "field-payload:d2d", display_name="D2d Field", area_value=3.2)
    assert profile_demo.cropcycle_identity_payload(
        "cycle-payload:d2d", auto_created=False) == \
        demo.cropcycle_identity_payload("cycle-payload:d2d", auto_created=False)
    assert profile_demo.equipment_identity_payload("equipment-payload:d2d") == \
        demo.equipment_identity_payload("equipment-payload:d2d")
    assert profile_demo.appliedresource_identity_payload("resource-payload:d2d") == \
        demo.appliedresource_identity_payload("resource-payload:d2d")

    payload = demo.farm_identity_payload("farm-payload:d2d-structure")
    assert profile_demo.structure_submission(
        payload,
        idem_key="idem:d2d-structure",
        actor_ref=demo.ADVISOR,
        confirm=False,
        supersedes="consequence:d2d-old",
        event_time="2099-05-01T00:00:00Z",
        evidence_refs=["evidence:d2d-custom"],
    ) == demo.structure_submission(
        payload,
        idem_key="idem:d2d-structure",
        actor_ref=demo.ADVISOR,
        confirm=False,
        supersedes="consequence:d2d-old",
        event_time="2099-05-01T00:00:00Z",
        evidence_refs=["evidence:d2d-custom"],
    )

    kwargs = {
        "event_start": "2099-06-01T06:00:00Z",
        "event_end": "2099-06-01T07:00:00Z",
        "binding_refs": [demo.PRODUCT_BINDING],
        "evidence_refs": [demo.PHOTO_EVIDENCE],
        "dose_value": 1.1,
        "unit_ref": "scheme:ucum:mL/har",
    }
    assert profile_demo.spray_payload(
        "erp:d2d-payload",
        actor_ref=demo.WORKER,
        **kwargs,
    ) == demo.spray_payload(
        "erp:d2d-payload",
        actor_ref=demo.WORKER,
        **kwargs,
    )
    assert profile_demo.spray_submission(
        "idem:d2d-spray",
        actor_ref=demo.WORKER,
        confirm=False,
        erp_id="erp:d2d-submission",
        channel="API",
        **kwargs,
    ) == demo.spray_submission(
        "idem:d2d-spray",
        actor_ref=demo.WORKER,
        confirm=False,
        erp_id="erp:d2d-submission",
        channel="API",
        **kwargs,
    )
