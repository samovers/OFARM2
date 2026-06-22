"""Profile-local facade for active SI demo test fixtures.

D2d lets SI profile engineering tests import demo fixture support from the
profile package directly while `kernel.demo` remains the public compatibility
facade for existing root callers and examples. These helpers are test/demo
support only; they are not profile law, runtime adapters, contracts, generated
manifests, or conformance evidence.
"""
from __future__ import annotations

from kernel import config
from kernel.context import now_iso

from . import demo_payloads, demo_records
from .demo_refs import (
    ACTION_CLASSES,
    ADVISOR,
    AGENT,
    APPLIED_RESOURCE,
    CROP_BINDING,
    CYCLE,
    FARM,
    FARMER,
    FARMER_GRANT,
    FIELD,
    INSPECTOR,
    INSPECTOR_SHARE,
    ONBOARDING_EVIDENCE,
    PHOTO_EVIDENCE,
    PRODUCT_BINDING,
    REGSR_SNAPSHOT,
    SPRAYER,
    VALID_FROM,
    WORKER,
    WORKER_DELEGATION,
)


__all__ = [
    "FARM",
    "FIELD",
    "CYCLE",
    "FARMER",
    "WORKER",
    "ADVISOR",
    "INSPECTOR",
    "AGENT",
    "SPRAYER",
    "APPLIED_RESOURCE",
    "PRODUCT_BINDING",
    "CROP_BINDING",
    "PHOTO_EVIDENCE",
    "ONBOARDING_EVIDENCE",
    "FARMER_GRANT",
    "WORKER_DELEGATION",
    "INSPECTOR_SHARE",
    "REGSR_SNAPSHOT",
    "VALID_FROM",
    "ACTION_CLASSES",
    "now_iso",
    "substrate_records",
    "farm_identity_payload",
    "field_identity_payload",
    "cropcycle_identity_payload",
    "equipment_identity_payload",
    "appliedresource_identity_payload",
    "structure_submission",
    "spray_payload",
    "spray_submission",
]


def _substrate_demo_refs() -> demo_records.DemoRefs:
    return demo_records.DemoRefs(
        farm=FARM,
        farmer=FARMER,
        worker=WORKER,
        advisor=ADVISOR,
        inspector=INSPECTOR,
        agent=AGENT,
        product_binding=PRODUCT_BINDING,
        crop_binding=CROP_BINDING,
        photo_evidence=PHOTO_EVIDENCE,
        onboarding_evidence=ONBOARDING_EVIDENCE,
        farmer_grant=FARMER_GRANT,
        worker_delegation=WORKER_DELEGATION,
        inspector_share=INSPECTOR_SHARE,
        regsr_snapshot=REGSR_SNAPSHOT,
        valid_from=VALID_FROM,
        action_classes=ACTION_CLASSES,
    )


def _payload_demo_refs() -> demo_payloads.DemoPayloadRefs:
    return demo_payloads.DemoPayloadRefs(
        farm=FARM,
        field=FIELD,
        cycle=CYCLE,
        farmer=FARMER,
        sprayer=SPRAYER,
        applied_resource=APPLIED_RESOURCE,
        product_binding=PRODUCT_BINDING,
        crop_binding=CROP_BINDING,
        photo_evidence=PHOTO_EVIDENCE,
        onboarding_evidence=ONBOARDING_EVIDENCE,
        code_binding_profile_ref=config.CODE_BINDING_PROFILE_REF,
    )


def substrate_records() -> list[dict]:
    return demo_records.substrate_records(
        recorded_at=now_iso(),
        refs=_substrate_demo_refs(),
        code_binding_profile_ref=config.CODE_BINDING_PROFILE_REF,
    )


def farm_identity_payload(payload_id: str = "farmpayload:demo.kmetija.a") -> dict:
    return demo_payloads.farm_identity_payload(
        payload_id=payload_id,
        recorded_at=now_iso(),
        refs=_payload_demo_refs(),
    )


def field_identity_payload(payload_id: str = "fieldpayload:demo.kmetija.a.field-1",
                           *, display_name: str = "Zgornja njiva (fictional demo field)",
                           area_value: float = 1.42) -> dict:
    return demo_payloads.field_identity_payload(
        payload_id=payload_id,
        recorded_at=now_iso(),
        refs=_payload_demo_refs(),
        display_name=display_name,
        area_value=area_value,
    )


def cropcycle_identity_payload(payload_id: str = "cyclepayload:demo.kmetija.a.vine-2026",
                               *, auto_created: bool = True) -> dict:
    return demo_payloads.cropcycle_identity_payload(
        payload_id=payload_id,
        recorded_at=now_iso(),
        refs=_payload_demo_refs(),
        auto_created=auto_created,
    )


def equipment_identity_payload(payload_id: str = "equippayload:demo.sprayer.one") -> dict:
    return demo_payloads.equipment_identity_payload(
        payload_id=payload_id,
        recorded_at=now_iso(),
        refs=_payload_demo_refs(),
    )


def appliedresource_identity_payload(
        payload_id: str = "resourcepayload:demo.account") -> dict:
    return demo_payloads.appliedresource_identity_payload(
        payload_id=payload_id,
        recorded_at=now_iso(),
        refs=_payload_demo_refs(),
    )


def structure_submission(payload: dict, *, idem_key: str,
                         actor_ref: str = FARMER, confirm: bool = True,
                         supersedes: str | None = None,
                         event_time: str = "2026-01-05T09:00:00Z",
                         evidence_refs: list[str] | None = None) -> dict:
    return demo_payloads.structure_submission(
        payload,
        idem_key=idem_key,
        refs=_payload_demo_refs(),
        actor_ref=actor_ref,
        confirm=confirm,
        supersedes=supersedes,
        event_time=event_time,
        evidence_refs=evidence_refs,
    )


def spray_payload(erp_id: str = "erp:demo.spray.0001", *,
                  actor_ref: str = FARMER,
                  event_start: str = "2026-06-10T07:30:00Z",
                  event_end: str = "2026-06-10T08:15:00Z",
                  binding_refs: list[str] | None = None,
                  evidence_refs: list[str] | None = None,
                  dose_value: float = 0.3,
                  unit_ref: str = "scheme:ucum:L/har") -> dict:
    return demo_payloads.spray_payload(
        erp_id=erp_id,
        refs=_payload_demo_refs(),
        actor_ref=actor_ref,
        event_start=event_start,
        event_end=event_end,
        binding_refs=binding_refs,
        evidence_refs=evidence_refs,
        dose_value=dose_value,
        unit_ref=unit_ref,
    )


def spray_submission(idem_key: str = "device-demo-1:q-0001", *,
                     actor_ref: str = FARMER, confirm: bool = True,
                     erp_id: str = "erp:demo.spray.0001",
                     channel: str = "MANUAL_UI", **payload_kwargs) -> dict:
    return demo_payloads.spray_submission(
        idem_key=idem_key,
        refs=_payload_demo_refs(),
        actor_ref=actor_ref,
        confirm=confirm,
        erp_id=erp_id,
        channel=channel,
        payload_kwargs=payload_kwargs,
    )
