"""D2b — SI demo substrate records are built profile-locally.

Engineering tests only. They prove `kernel.demo.substrate_records()` remains the
compatibility facade while construction lives under `profile_si_ffs`.
"""
from __future__ import annotations

from kernel import config, demo
from profile_si_ffs.test_fixtures import demo_records


__all__ = [
    "test_d2_substrate_records_facade_matches_profile_helper",
    "test_d2_substrate_records_preserve_demo_ids_and_no_bootstrapped_identities",
]


FIXED_NOW = "2099-01-02T03:04:05Z"


def _record_id(record: dict) -> str:
    for field in (
        "partyId",
        "roleAssignmentId",
        "authorityGrantId",
        "delegationGrantId",
        "sharingGrantId",
        "evidenceRecordId",
        "agronomicIdentityBindingId",
        "externalRegistryVerificationTraceId",
    ):
        if field in record:
            return record[field]
    raise AssertionError(f"record has no expected id field: {record}")


def test_d2_substrate_records_facade_matches_profile_helper(monkeypatch):
    monkeypatch.setattr(demo, "now_iso", lambda: FIXED_NOW)

    direct = demo_records.substrate_records(
        recorded_at=FIXED_NOW,
        refs=demo_records.refs_from_module(demo),
        code_binding_profile_ref=config.CODE_BINDING_PROFILE_REF,
    )

    assert demo.substrate_records() == direct


def test_d2_substrate_records_preserve_demo_ids_and_no_bootstrapped_identities(
        monkeypatch):
    monkeypatch.setattr(demo, "now_iso", lambda: FIXED_NOW)

    records = demo.substrate_records()

    assert [_record_id(record) for record in records] == [
        demo.FARMER,
        demo.WORKER,
        demo.ADVISOR,
        demo.INSPECTOR,
        demo.AGENT,
        "role:demo.farmer.one.holder",
        demo.FARMER_GRANT,
        "grant:demo.farmer.one.review",
        "grant:demo.advisor.one.review",
        demo.WORKER_DELEGATION,
        demo.INSPECTOR_SHARE,
        demo.PHOTO_EVIDENCE,
        demo.ONBOARDING_EVIDENCE,
        demo.PRODUCT_BINDING,
        "trace:demo.regver.account",
        demo.CROP_BINDING,
    ]
    assert not any(
        record["schemaVersion"] == "ofarm.identityrecord.v0.1"
        for record in records
    )
