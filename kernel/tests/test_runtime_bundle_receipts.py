"""RuntimeBundle origin receipts and cross-bundle continuation guards (#171)."""
from __future__ import annotations

import copy
import json
import uuid
from contextlib import contextmanager
from dataclasses import replace

import psycopg
import psycopg.conninfo
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from kernel import config, context, demo
from kernel.adapters import ImportRunner, ParseResult
from kernel.api import create_app
from kernel.authority import AuthorityEvaluator
from kernel.contracts import sha256_of
from kernel.gates import GatePipeline
from kernel.materializer import MaterializationIdentityError, Materializer
from kernel.profiles.si_ffs.gerk_adapter import GerkLayer
from kernel.profiles.si_ffs import si_bindings as sib
from kernel.profile_runtime import load_profile_runtime_descriptor
from kernel.runtime_bundle import (
    Canonicalization,
    ContentPlacement,
    RuntimeBundle,
    RuntimeBundleBuilder,
    RuntimeComponent,
    RuntimeComponentRole,
    canonical_json_bytes,
)
from kernel.runtime_activation import complete_store_startup
from kernel.schema_posture import SchemaPostureError
from kernel.store import RuntimeBundleBindingError, Store
from kernel.tests.conftest import _admin_dsn
from kernel.views import OutputGenerator


RECEIPT_TABLES = (
    "kernel_record",
    "kernel_edge",
    "kernel_gate_log",
    "kernel_idempotency",
    "derived_materialization",
    "derived_dependency_index",
    "reference_snapshot_data",
    "runtime_trace",
    "export_artifact",
)

CONTINUATION_BUSINESS_KINDS = (
    "ofarm.assertionrecord.v0.1",
    "ofarm.reviewdecision.v0.1",
    "ofarm.acceptedeventconsequence.v0.1",
    "ofarm.contextsnapshot.v0.1",
    "ofarm.materializationbasis.v0.1",
    "ofarm.materializationsnapshot.v0.1",
)


def _uid() -> str:
    return uuid.uuid4().hex[:10]


def _continuation_business_state(store: Store) -> tuple:
    records = store.conn.execute(
        "SELECT record_kind, COUNT(*) AS count FROM kernel_record "
        "WHERE record_kind = ANY(%s) GROUP BY record_kind ORDER BY record_kind",
        (list(CONTINUATION_BUSINESS_KINDS),),
    ).fetchall()
    derived = store.conn.execute(
        "SELECT COUNT(*) AS count, "
        "COUNT(*) FILTER (WHERE superseded_by IS NOT NULL) AS superseded, "
        "COUNT(*) FILTER (WHERE freshness <> 'FRESH') AS non_fresh "
        "FROM derived_materialization"
    ).fetchone()
    dependencies = store.conn.execute(
        "SELECT COUNT(*) AS count FROM derived_dependency_index"
    ).fetchone()
    reference_data = store.conn.execute(
        "SELECT COUNT(*) AS count FROM reference_snapshot_data"
    ).fetchone()
    return (
        tuple((row["record_kind"], row["count"]) for row in records),
        (derived["count"], derived["superseded"], derived["non_fresh"]),
        dependencies["count"],
        reference_data["count"],
    )


def _variant_bundle(base: RuntimeBundle) -> RuntimeBundle:
    marker = RuntimeComponent.from_selected_bytes(
        role=RuntimeComponentRole.ADAPTER_SOURCE,
        logical_ref=f"python:test.runtime-bundle-receipts:variant-{_uid()}",
        canonicalization=Canonicalization.EXACT_BYTES,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=b"# alternate verified runtime selection for issue 171\n",
    )
    return RuntimeBundle.create((*base.components, marker))


def _bundle_with_extra_selected_snapshot(
    base: RuntimeBundle,
) -> tuple[RuntimeBundle, RuntimeComponent]:
    """Build a valid bundle with one selected snapshot outside the descriptor paths."""
    snapshot_id = "referencesnapshot:si.uvhvvr.ffs-reg.bootstrap-extra.2099-01-01"
    artifact_ref = "artifact:test.bootstrap-extra-regsr.json"
    source = RuntimeComponent.from_selected_bytes(
        role=RuntimeComponentRole.REFERENCE_SOURCE,
        logical_ref=artifact_ref,
        canonicalization=Canonicalization.EXACT_BYTES,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=canonical_json_bytes({
            "fixture": "bundle-selected bootstrap source",
        }),
    )
    template = next(
        component for component in base.components
        if component.role is RuntimeComponentRole.REFERENCE_SNAPSHOT
        and component.logical_ref.startswith("referencesnapshot:si.uvhvvr.ffs-reg.")
    )
    snapshot_payload = json.loads(template.canonical_bytes)
    snapshot_payload.update({
        "referenceSnapshotId": snapshot_id,
        "canonicalVersionLabel": "bootstrap-extra-2099-01-01",
        "effectiveFrom": "2099-01-01T00:00:00Z",
        "sourceArtifactRefs": [
            artifact_ref,
            f"digest:{source.content_digest}",
        ],
        "notes": "Fictional bundle-selected snapshot for bootstrap regression coverage.",
    })
    snapshot = RuntimeComponent.from_selected_bytes(
        role=RuntimeComponentRole.REFERENCE_SNAPSHOT,
        logical_ref=snapshot_id,
        canonicalization=Canonicalization.CANONICAL_JSON,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=canonical_json_bytes(snapshot_payload),
    )

    components = []
    for component in base.components:
        if component.role is RuntimeComponentRole.PROFILE_INSTANCE:
            payload = json.loads(component.canonical_bytes)
            if payload.get("schemaVersion") == "ofarm.activeartifactset.v0.1":
                payload["activeArtifactRefs"] = [
                    *payload["activeArtifactRefs"], snapshot_id]
                component = RuntimeComponent.from_selected_bytes(
                    role=component.role,
                    logical_ref=component.logical_ref,
                    canonicalization=component.canonicalization,
                    placement=component.placement,
                    selected_bytes=canonical_json_bytes(payload),
                )
            elif payload.get("schemaVersion") == "ofarm.contextsnapshot.v0.1":
                payload["referenceSnapshotRefs"] = [
                    *payload["referenceSnapshotRefs"], snapshot_id]
                component = RuntimeComponent.from_selected_bytes(
                    role=component.role,
                    logical_ref=component.logical_ref,
                    canonicalization=component.canonicalization,
                    placement=component.placement,
                    selected_bytes=canonical_json_bytes(payload),
                )
        components.append(component)
    return RuntimeBundle.create((*components, source, snapshot)), snapshot


def _bundle_with_alternate_regsr_source(
    base: RuntimeBundle,
    artifact: dict,
) -> RuntimeBundle:
    snapshot = next(
        component for component in base.components
        if component.role is RuntimeComponentRole.REFERENCE_SNAPSHOT
        and component.logical_ref.startswith(
            context.SI_REFERENCE_BINDINGS.regsr_snapshot_prefix + "."
        )
    )
    snapshot_payload = json.loads(snapshot.canonical_bytes)
    artifact_refs = [
        ref for ref in snapshot_payload["sourceArtifactRefs"]
        if ref.startswith("artifact:")
    ]
    assert len(artifact_refs) == 1
    source = RuntimeComponent.from_selected_bytes(
        role=RuntimeComponentRole.REFERENCE_SOURCE,
        logical_ref=artifact_refs[0],
        canonicalization=Canonicalization.EXACT_BYTES,
        placement=ContentPlacement.GLOBAL,
        selected_bytes=canonical_json_bytes(artifact),
    )
    snapshot_payload["sourceArtifactRefs"] = [
        f"digest:{source.content_digest}" if ref.startswith("digest:") else ref
        for ref in snapshot_payload["sourceArtifactRefs"]
    ]
    selected_snapshot = RuntimeComponent.from_selected_bytes(
        role=snapshot.role,
        logical_ref=snapshot.logical_ref,
        canonicalization=snapshot.canonicalization,
        placement=snapshot.placement,
        selected_bytes=canonical_json_bytes(snapshot_payload),
    )
    return RuntimeBundle.create(
        source
        if component.role is RuntimeComponentRole.REFERENCE_SOURCE
        and component.logical_ref == source.logical_ref
        else selected_snapshot
        if component is snapshot
        else component
        for component in base.components
    )


def _bundle_for_tenant(base: RuntimeBundle, tenant_ref: str) -> RuntimeBundle:
    def retarget(value) -> None:
        if isinstance(value, dict):
            if value.get("scopeType") == "TENANT" and "scopeRef" in value:
                value["scopeRef"] = tenant_ref
            for child in value.values():
                retarget(child)
        elif isinstance(value, list):
            for child in value:
                retarget(child)

    components = []
    for component in base.components:
        if (
            component.canonicalization is Canonicalization.CANONICAL_JSON
            and component.placement is ContentPlacement.TENANT
        ):
            document = json.loads(component.canonical_bytes)
            retarget(document)
            selected_bytes = canonical_json_bytes(document)
            if selected_bytes != component.canonical_bytes:
                component = RuntimeComponent.from_selected_bytes(
                    role=component.role,
                    logical_ref=component.logical_ref,
                    canonicalization=component.canonicalization,
                    placement=component.placement,
                    selected_bytes=selected_bytes,
                )
        components.append(component)
    bundle = RuntimeBundle.create(components)
    assert bundle.selected_tenant_ref == tenant_ref
    return bundle


def _selected_bundle() -> RuntimeBundle:
    return RuntimeBundleBuilder.from_manifest(config.PACKAGE_ROOT).build()


def _selected_regsr_source(store: Store) -> tuple[dict, RuntimeComponent, str]:
    prefix = context.SIReferenceBindings.from_runtime_descriptor(
        store.active_descriptor
    ).regsr_snapshot_prefix
    snapshot_component = next(
        component for component in store.runtime_bundle.components
        if component.role is RuntimeComponentRole.REFERENCE_SNAPSHOT
        and (
            component.logical_ref == prefix
            or component.logical_ref.startswith(prefix + ".")
        )
    )
    snapshot = json.loads(snapshot_component.canonical_bytes)
    artifact_ref = next(
        ref for ref in snapshot["sourceArtifactRefs"]
        if ref.startswith("artifact:")
    )
    source = store.runtime_bundle.component(
        RuntimeComponentRole.REFERENCE_SOURCE,
        artifact_ref,
    )
    artifact = json.loads(source.canonical_bytes)
    decision = next(
        decision["decisionNumber"]
        for detail in artifact["productDetails"]
        for decision in detail.get("decisions", [])
        if decision.get("decisionNumber")
    )
    return snapshot, source, decision


def _second_store(first: Store) -> Store:
    store = Store(
        dsn=first.dsn,
        tenant_ref=first.tenant_ref,
        runtime_bundle=_variant_bundle(first.runtime_bundle),
        active_descriptor=first.active_descriptor,
    )
    complete_store_startup(store)
    return store


@contextmanager
def _foreign_tenant_store(source: Store, label: str):
    tenant_ref = f"tenant:foreign-{label}.{_uid()}"
    store = Store(
        dsn=source.dsn,
        tenant_ref=tenant_ref,
        runtime_bundle=_bundle_for_tenant(source.runtime_bundle, tenant_ref),
        active_descriptor=source.active_descriptor,
    )
    try:
        store.migrate()
        yield tenant_ref, store
    finally:
        store.close()


@contextmanager
def _isolated_store(label: str):
    dbname = f"ofarm_171_{label}_{uuid.uuid4().hex[:10]}"
    admin_dsn = _admin_dsn()
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    params = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    params["dbname"] = dbname
    store = Store(
        dsn=psycopg.conninfo.make_conninfo(**params),
        tenant_ref=config.TENANT_REF,
        runtime_bundle=_selected_bundle(),
        active_descriptor=config.ACTIVE_PROFILE,
    )
    try:
        yield store
    finally:
        store.close()
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (dbname,),
            )
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname))
            )


def _accept_submission(target: str, key: str) -> dict:
    return {
        "commitClass": "GOVERNANCE_DECISION",
        "ingressChannel": "MANUAL_UI",
        "actingPartyRef": demo.ADVISOR,
        "farmRef": demo.FARM,
        "idempotencyKey": key,
        "decisionTime": context.now_iso(),
        "reviewTargetAssertionRef": target,
        "reviewRationale": "advisor accepts after reviewing the queued claim",
        "dominantSemanticConsequence": "review acceptance of a queued claim",
    }


def _reject_submission(target: str, key: str) -> dict:
    return {
        **_accept_submission(target, key),
        "reviewAction": "REVIEW_REJECT_OR_CONTEST",
        "decisionOutcomeState": "REJECTED",
        "reviewRationale": "advisor declines the historical queued claim",
        "dominantSemanticConsequence": "review rejection of a queued claim",
    }


def _contest_submission(target: str, key: str) -> dict:
    return {
        "commitClass": "GOVERNANCE_DECISION",
        "ingressChannel": "MANUAL_UI",
        "actingPartyRef": demo.ADVISOR,
        "farmRef": demo.FARM,
        "idempotencyKey": key,
        "decisionTime": context.now_iso(),
        "reviewTargetConsequenceRef": target,
        "reviewAction": "REVIEW_REJECT_OR_CONTEST",
        "decisionOutcomeState": "CONTESTED",
        "reviewRationale": "advisor disputes the historical consequence",
        "dominantSemanticConsequence": "dispute against an in-force consequence",
    }


def _seed_foreign_review_target(
    source_store: Store,
    foreign_store: Store,
    *,
    source_target: str,
    foreign_target: str,
    identity_field: str,
    emitted_refs_field: str,
) -> None:
    target_payload = copy.deepcopy(source_store.get_record(source_target)["payload"])
    target_payload[identity_field] = foreign_target
    source_edges = source_store.edges_to(source_target, "PROMOTION_EMITS")
    assert len(source_edges) == 1
    trace_payload = copy.deepcopy(
        source_store.get_record(source_edges[0]["src_record_id"])["payload"]
    )
    foreign_trace = f"promtrace:foreign-tenant.{_uid()}"
    trace_payload["promotionTraceId"] = foreign_trace
    trace_payload[emitted_refs_field] = [
        foreign_target if ref == source_target else ref
        for ref in trace_payload[emitted_refs_field]
    ]

    with foreign_store.tx() as cur:
        foreign_store.insert_record(cur, target_payload)
        foreign_store.insert_record(cur, trace_payload)
        foreign_store.add_edge(
            cur, "PROMOTION_EMITS", foreign_trace, foreign_target
        )


def _seed_foreign_evidence(
    source_store: Store,
    foreign_store: Store,
    foreign_evidence: str,
) -> None:
    payload = copy.deepcopy(source_store.get_record(demo.PHOTO_EVIDENCE)["payload"])
    payload["evidenceRecordId"] = foreign_evidence
    with foreign_store.tx() as cur:
        foreign_store.insert_record(cur, payload)


def _assert_redacted_review_refusal(
    result: dict,
    *,
    foreign_tenant: str,
    foreign_bundle: str,
    foreign_kind: str,
) -> None:
    assert result["decisionOutcome"] == "RETAIN_DRAFT"
    assert result["problems"][0]["reasonCode"] == \
        "EVIDENCE_REFERENCE_UNAVAILABLE"
    serialized = json.dumps(result, sort_keys=True)
    for unavailable_detail in (
        foreign_tenant,
        foreign_bundle,
        foreign_kind,
        "PACK_CONFLICT",
    ):
        assert unavailable_detail not in serialized


def _snapshot_meta(snapshot_id: str) -> dict:
    return {
        "referenceSnapshotId": snapshot_id,
        "referenceClass": "CODE_LIST",
        "domain": "fictional RuntimeBundle cache fixture",
        "issuingAuthorityRef": "party:fixture.authority",
        "jurisdictionRef": "jurisdiction:FIXTURE",
        "canonicalVersionLabel": "fixture.runtime-bundle.v1",
        "effectiveFrom": "2026-05-01T00:00:00Z",
        "sourceArtifactRefs": ["surface:fixture.runtime-bundle"],
        "notes": "fictional parsed-cache fixture",
    }


def test_store_requires_explicit_tenant_and_bundle_pairing():
    bundle = _selected_bundle()

    with pytest.raises(RuntimeBundleBindingError, match="supplied together"):
        Store(runtime_bundle=bundle)
    with pytest.raises(RuntimeBundleBindingError, match="supplied together"):
        Store(tenant_ref=config.TENANT_REF)
    for invalid_tenant_ref in ("x", "farm:x"):
        with pytest.raises(RuntimeBundleBindingError, match="must be tenant:"):
            Store(
                tenant_ref=invalid_tenant_ref,
                runtime_bundle=bundle,
                active_descriptor=config.ACTIVE_PROFILE,
            )
    with pytest.raises(
        RuntimeBundleBindingError,
        match="does not match bundle-selected tenant",
    ):
        Store(
            tenant_ref="tenant:other",
            runtime_bundle=bundle,
            active_descriptor=config.ACTIVE_PROFILE,
        )

    store = Store(
        tenant_ref=config.TENANT_REF,
        runtime_bundle=bundle,
        active_descriptor=config.ACTIVE_PROFILE,
    )
    try:
        assert store.tenant_ref == config.TENANT_REF
        assert store.runtime_bundle_digest == bundle.digest
    finally:
        store.close()


def test_store_refuses_descriptor_observation_outside_selected_bundle():
    bundle = _selected_bundle()
    changed = replace(
        config.ACTIVE_PROFILE,
        evidence_policy_ref="policy:si.ffs.not-selected.v0_1",
    )

    with pytest.raises(RuntimeBundleBindingError, match="exact descriptor selected"):
        Store(
            tenant_ref=config.TENANT_REF,
            runtime_bundle=bundle,
            active_descriptor=changed,
        )


def test_live_schema_catalog_requires_validated_composite_foreign_keys():
    with _isolated_store("not_valid_fk") as store:
        store.migrate()
        row = store.conn.execute(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'kernel_gate_log'::regclass AND contype = 'f' "
            "AND confrelid = 'runtime_bundle'::regclass"
        ).fetchone()
        with store.conn.transaction():
            with store.conn.cursor() as cur:
                cur.execute(sql.SQL("ALTER TABLE kernel_gate_log DROP CONSTRAINT {}").format(
                    sql.Identifier(row["conname"])
                ))
                cur.execute(
                    "INSERT INTO kernel_gate_log "
                    "(request_id, gate, outcome, tenant_ref, runtime_bundle_digest) "
                    "VALUES ('orphan:request', 'TEST', 'REFUSED', %s, %s)",
                    (store.tenant_ref, "sha256:" + "0" * 64),
                )
                cur.execute(
                    "ALTER TABLE kernel_gate_log ADD CONSTRAINT "
                    "kernel_gate_log_runtime_bundle_not_valid_fk FOREIGN KEY "
                    "(tenant_ref, runtime_bundle_digest) REFERENCES runtime_bundle "
                    "(tenant_ref, bundle_digest) NOT VALID"
                )

        with pytest.raises(
            SchemaPostureError,
            match="live database schema catalog does not match",
        ):
            store.migrate()


def test_profile_bootstrap_refuses_non_exact_existing_selected_instance():
    with _isolated_store("profile_reuse") as store:
        store.migrate()
        path = next(
            path for path in config.ACTIVE_PROFILE.profile_instance_paths
            if "ActiveArtifactSet" in path.name
        )
        payload = json.loads(path.read_text())
        payload["notes"] += " Mutated pre-existing payload."
        with store.tx() as cur:
            store.insert_record(cur, payload)

        with pytest.raises(
            context.ContextNotReconstructible,
            match="not the exact selected contract and payload",
        ):
            context.bootstrap_for_descriptor(store, config.ACTIVE_PROFILE)


def test_profile_bootstrap_inserts_every_bundle_selected_canonical_instance():
    with _isolated_store("complete_selected_bootstrap") as source_store:
        selected_bundle, extra_snapshot = _bundle_with_extra_selected_snapshot(
            source_store.runtime_bundle)
        selected_store = Store(
            dsn=source_store.dsn,
            tenant_ref=source_store.tenant_ref,
            runtime_bundle=selected_bundle,
            active_descriptor=source_store.active_descriptor,
        )
        try:
            create_app(selected_store, oidc=None)

            selected_components = [
                component for component in selected_bundle.components
                if component.role in {
                    RuntimeComponentRole.PROFILE_INSTANCE,
                    RuntimeComponentRole.REFERENCE_SNAPSHOT,
                }
            ]
            assert extra_snapshot in selected_components
            for component in selected_components:
                row = selected_store.get_record(component.logical_ref)
                assert row is not None
                assert row["payload"] == json.loads(component.canonical_bytes)
                assert row["payload_sha256"] == component.content_digest
        finally:
            selected_store.close()


def test_profile_bootstrap_refuses_extra_selected_snapshot_mismatch_atomically():
    with _isolated_store("extra_selected_mismatch") as seed_store:
        seed_store.migrate()
        selected_bundle, extra_snapshot = _bundle_with_extra_selected_snapshot(
            seed_store.runtime_bundle)
        unequal = json.loads(extra_snapshot.canonical_bytes)
        unequal["notes"] += " Pre-existing unequal payload."
        with seed_store.tx() as cur:
            seed_store.insert_record(cur, unequal)

        refusing_store = Store(
            dsn=seed_store.dsn,
            tenant_ref=seed_store.tenant_ref,
            runtime_bundle=selected_bundle,
            active_descriptor=seed_store.active_descriptor,
        )
        try:
            with pytest.raises(
                context.ContextNotReconstructible,
                match="not the exact selected contract and payload",
            ):
                create_app(refusing_store, oidc=None)

            assert seed_store.conn.execute(
                "SELECT COUNT(*) AS count FROM runtime_bundle "
                "WHERE tenant_ref = %s AND bundle_digest = %s",
                (seed_store.tenant_ref, selected_bundle.digest),
            ).fetchone()["count"] == 0
            rows = seed_store.conn.execute(
                "SELECT record_id, payload FROM kernel_record ORDER BY record_id"
            ).fetchall()
            assert rows == [{
                "record_id": extra_snapshot.logical_ref,
                "payload": unequal,
            }]
        finally:
            refusing_store.close()


def test_profile_bootstrap_refuses_changed_path_absent_from_bound_bundle(tmp_path):
    selected = next(
        path for path in config.ACTIVE_PROFILE.profile_instance_paths
        if "ActiveArtifactSet" in path.name
    )
    payload = json.loads(selected.read_text())
    payload["notes"] += " Changed after RuntimeBundle activation."
    changed = tmp_path / selected.name
    changed.write_text(json.dumps(payload), encoding="utf-8")
    paths = tuple(
        changed if path == selected else path
        for path in config.ACTIVE_PROFILE.profile_instance_paths
    )
    descriptor = replace(config.ACTIVE_PROFILE, profile_instance_paths=paths)

    with _isolated_store("changed_profile") as store:
        store.migrate()
        with pytest.raises(
            context.ContextNotReconstructible,
            match="not the Store startup selection",
        ):
            context.bootstrap_for_descriptor(store, descriptor)
        selected_ids = []
        for path in config.ACTIVE_PROFILE.profile_instance_paths:
            selected_payload = json.loads(path.read_text())
            contract = store.registry.get(selected_payload["schemaVersion"])
            selected_ids.append(selected_payload[contract.id_field])
        assert all(store.get_record(record_id) is None for record_id in selected_ids)


def test_application_bootstrap_uses_bundle_selected_bytes_not_profile_paths():
    with _isolated_store("atomic_app") as store:
        selected = next(
            component for component in store.runtime_bundle.components
            if component.role is RuntimeComponentRole.PROFILE_INSTANCE
        )
        changed_payload = json.loads(selected.canonical_bytes)
        changed_payload["notes"] = (
            str(changed_payload.get("notes", "")) + " Changed after selection."
        )
        changed = RuntimeComponent.from_selected_bytes(
            role=selected.role,
            logical_ref=selected.logical_ref,
            canonicalization=selected.canonicalization,
            placement=selected.placement,
            selected_bytes=json.dumps(changed_payload).encode("utf-8"),
        )
        changed_bundle = RuntimeBundle.create(
            changed if component is selected else component
            for component in store.runtime_bundle.components
        )
        refusing_store = Store(
            dsn=store.dsn,
            tenant_ref=store.tenant_ref,
            runtime_bundle=changed_bundle,
            active_descriptor=store.active_descriptor,
        )
        try:
            create_app(refusing_store, oidc=None)
            row = refusing_store.get_record(changed.logical_ref)
            assert row is not None
            assert row["payload"] == changed_payload
            assert row["payload_sha256"] == changed.content_digest
        finally:
            refusing_store.close()


def test_every_operational_carrier_has_the_exact_runtime_receipt(fresh_env):
    store, pipeline, outputs = fresh_env
    digest = store.runtime_bundle_digest

    accepted = pipeline.commit(demo.spray_submission(
        f"receipt:{_uid()}", erp_id=f"erp:receipt.{_uid()}", confirm=True))
    assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED"

    passport = outputs.passport_view(demo.FARM, demo.FARMER)
    assert passport["refused"] is False
    assert passport["runtimeReceipt"]["runtimeBundleDigest"] == digest
    assert set(passport["runtimeReceipt"]["payloadDigests"]) == {
        "body", "metadata", "qualification"
    }

    refused = outputs.passport_view(demo.FARM, f"party:missing.{_uid()}")
    assert refused["refused"] is True
    assert refused["runtimeReceipt"]["runtimeBundleDigest"] == digest

    frozen = outputs.freeze_inspection_register(
        demo.FARM, demo.FARMER,
        "2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z")
    assert frozen["refused"] is False
    assert frozen["runtimeReceipt"]["runtimeBundleDigest"] == digest
    assert frozen["document"]["receipts"]["runtimeBundleDigest"] == digest
    assert len(frozen["metadata"]["durableArtifactRef"].rsplit(".", 1)[-1]) == 64

    with store.tx() as cur:
        store.insert_reference_data(
            cur, f"referencesnapshot:receipt.{_uid()}", "receipt-fixture",
            {"rows": [{"value": "fictional"}]})

    for table in RECEIPT_TABLES:
        rows = store.conn.execute(
            f"SELECT DISTINCT tenant_ref, runtime_bundle_digest FROM {table}"
        ).fetchall()
        assert rows, f"{table} should have a receipt-bearing row in this scenario"
        assert {(row["tenant_ref"], row["runtime_bundle_digest"]) for row in rows} == {
            (store.tenant_ref, digest)
        }

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with store.tx() as cur:
            cur.execute(
                "INSERT INTO kernel_gate_log "
                "(request_id, gate, outcome, tenant_ref, runtime_bundle_digest) "
                "VALUES (%s, 'TEST', 'REFUSED', %s, %s)",
                (f"request:wrong-bundle.{_uid()}", "tenant:other", digest),
            )

    with TestClient(create_app(store, oidc=None)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.headers["x-ofarm-runtime-bundle-digest"] == digest
        assert health.json()["runtimeBundleDigest"] == digest
        record = client.get(
            f"/records/{demo.FARMER}",
            headers={"x-acting-party": demo.FARMER},
        )
        assert record.status_code == 200
        assert record.headers["x-ofarm-runtime-bundle-digest"] == digest
        assert record.json()["runtimeBundleDigest"] == digest


def test_materialization_key_reuse_requires_exact_identity_inputs(fresh_env):
    store, _pipeline, _outputs = fresh_env
    materializer = Materializer(store)
    time_policy = {
        "policyType": "AS_OF",
        "asOfTime": "2099-01-01T00:00:00Z",
    }
    with store.serialized_tx() as cur:
        snapshot = materializer.context.assemble(
            cur, demo.FARM, evaluation_time_policy=time_policy
        )
        key = materializer.build_key(
            demo.FARM,
            twin="COMPLIANCE",
            use_class="OPERATIONAL_DASHBOARD",
            time_policy=time_policy,
            context_snapshot_ref=snapshot["contextSnapshotId"],
        )
        unequal = copy.deepcopy(key)
        unequal["useClass"] = "FORENSIC_AUDIT"
        store.insert_runtime_trace(cur, unequal)

    with pytest.raises(MaterializationIdentityError, match="reused unequally"):
        with store.serialized_tx() as cur:
            materializer.resolve_for_use(cur, demo.FARM, time_policy=time_policy)


def test_context_snapshot_reuse_requires_exact_identity_inputs(fresh_env):
    store, _pipeline, _outputs = fresh_env
    assembler = context.ContextAssembler(store)
    time_policy = {
        "policyType": "AS_OF",
        "asOfTime": "2098-12-31T00:00:00Z",
    }

    class RollbackProbe(Exception):
        pass

    with pytest.raises(RollbackProbe):
        with store.serialized_tx() as cur:
            expected = assembler.assemble(
                cur,
                demo.FARM,
                evaluation_time_policy=time_policy,
            )
            raise RollbackProbe

    unequal = copy.deepcopy(expected)
    unequal["evaluationTimePolicy"] = {"policyType": "NOW"}
    with store.serialized_tx() as cur:
        store.insert_record(cur, unequal)

    with pytest.raises(
        context.ContextNotReconstructible,
        match="unequal canonical identity inputs",
    ):
        with store.serialized_tx() as cur:
            assembler.assemble(
                cur,
                demo.FARM,
                evaluation_time_policy=time_policy,
            )


@pytest.mark.parametrize(
    "submission_factory",
    [
        pytest.param(_accept_submission, id="accept"),
        pytest.param(_reject_submission, id="reject"),
    ],
)
def test_cross_tenant_assertion_review_is_redacted_and_atomic(
    fresh_env,
    submission_factory,
):
    store, pipeline, _ = fresh_env
    queued = pipeline.commit(demo.spray_submission(
        f"queue-tenant:{_uid()}",
        erp_id=f"erp:queue-tenant.{_uid()}",
        confirm=False,
    ))
    source_target = queued["emittedAssertionRecordRefs"][0]
    foreign_target = f"assert:foreign-tenant.{_uid()}"

    with _foreign_tenant_store(store, "review") as (tenant_ref, foreign_store):
        _seed_foreign_review_target(
            store,
            foreign_store,
            source_target=source_target,
            foreign_target=foreign_target,
            identity_field="assertionRecordId",
            emitted_refs_field="emittedAssertionRecordRefs",
        )
        reviews_before = len(store.find_by_kind("ofarm.reviewdecision.v0.1"))
        business_before = _continuation_business_state(store)

        refused = pipeline.commit(submission_factory(
            foreign_target, f"queue-tenant-review:{_uid()}"
        ))

        _assert_redacted_review_refusal(
            refused,
            foreign_tenant=tenant_ref,
            foreign_bundle=foreign_store.runtime_bundle_digest,
            foreign_kind="ofarm.assertionrecord.v0.1",
        )
        assert len(store.find_by_kind(
            "ofarm.reviewdecision.v0.1"
        )) == reviews_before
        assert store.edges_from(foreign_target, "REVIEW") == []
        assert _continuation_business_state(store) == business_before


def test_cross_tenant_consequence_contest_is_redacted_and_atomic(fresh_env):
    store, pipeline, _ = fresh_env
    committed = pipeline.commit(demo.spray_submission(
        f"contest-tenant:{_uid()}",
        erp_id=f"erp:contest-tenant.{_uid()}",
        confirm=True,
    ))
    source_target = committed["emittedAcceptedConsequenceRefs"][0]
    foreign_target = f"conseq:foreign-tenant.{_uid()}"

    with _foreign_tenant_store(store, "contest") as (tenant_ref, foreign_store):
        _seed_foreign_review_target(
            store,
            foreign_store,
            source_target=source_target,
            foreign_target=foreign_target,
            identity_field="acceptedEventConsequenceId",
            emitted_refs_field="emittedAcceptedConsequenceRefs",
        )
        reviews_before = len(store.find_by_kind("ofarm.reviewdecision.v0.1"))
        business_before = _continuation_business_state(store)

        refused = pipeline.commit(_contest_submission(
            foreign_target, f"contest-tenant-review:{_uid()}"
        ))

        _assert_redacted_review_refusal(
            refused,
            foreign_tenant=tenant_ref,
            foreign_bundle=foreign_store.runtime_bundle_digest,
            foreign_kind="ofarm.acceptedeventconsequence.v0.1",
        )
        assert len(store.find_by_kind(
            "ofarm.reviewdecision.v0.1"
        )) == reviews_before
        assert store.edges_from(foreign_target, "DISPUTE") == []
        assert store.edges_from(foreign_target, "REVIEW") == []
        assert _continuation_business_state(store) == business_before


@pytest.mark.parametrize("branch", ["accept", "reject", "contest"])
def test_cross_tenant_review_evidence_is_redacted_and_atomic(fresh_env, branch):
    store, pipeline, _ = fresh_env
    if branch == "contest":
        committed = pipeline.commit(demo.spray_submission(
            f"evidence-contest:{_uid()}",
            erp_id=f"erp:evidence-contest.{_uid()}",
            confirm=True,
        ))
        target = committed["emittedAcceptedConsequenceRefs"][0]
        submission = _contest_submission(
            target, f"evidence-contest-review:{_uid()}"
        )
        target_edge = "DISPUTE"
    else:
        queued = pipeline.commit(demo.spray_submission(
            f"evidence-queue:{_uid()}",
            erp_id=f"erp:evidence-queue.{_uid()}",
            confirm=False,
        ))
        target = queued["emittedAssertionRecordRefs"][0]
        submission_factory = (
            _accept_submission if branch == "accept" else _reject_submission
        )
        submission = submission_factory(
            target, f"evidence-{branch}-review:{_uid()}"
        )
        target_edge = "REVIEW"

    foreign_evidence = f"evidence:foreign-tenant.{_uid()}"
    with _foreign_tenant_store(store, "evidence") as (tenant_ref, foreign_store):
        _seed_foreign_evidence(store, foreign_store, foreign_evidence)
        submission["reviewEvidenceRefs"] = [foreign_evidence]
        reviews_before = len(store.find_by_kind("ofarm.reviewdecision.v0.1"))
        business_before = _continuation_business_state(store)

        refused = pipeline.commit(submission)

        _assert_redacted_review_refusal(
            refused,
            foreign_tenant=tenant_ref,
            foreign_bundle=foreign_store.runtime_bundle_digest,
            foreign_kind="ofarm.evidencerecord.v0.1",
        )
        assert len(store.find_by_kind(
            "ofarm.reviewdecision.v0.1"
        )) == reviews_before
        assert store.edges_from(target, target_edge) == []
        assert store.edges_to(foreign_evidence, "EVIDENCE") == []
        assert _continuation_business_state(store) == business_before


def test_foreign_tenant_party_and_grant_do_not_bind_local_authority(fresh_env):
    store, _, _ = fresh_env
    foreign_party = f"party:foreign-tenant.{_uid()}"
    foreign_grant = f"grant:foreign-tenant.{_uid()}"
    party = copy.deepcopy(store.get_payload(demo.FARMER))
    party.update(
        partyId=foreign_party,
        displayName="Foreign Tenant Farmer (fictional)",
        registeredIdentifiers=[],
    )
    grant = copy.deepcopy(store.get_payload(demo.FARMER_GRANT))
    grant.update(
        authorityGrantId=foreign_grant,
        grantedByPartyRef=foreign_party,
        grantTarget={"targetKind": "PARTY", "targetRef": foreign_party},
    )

    with _foreign_tenant_store(store, "authority") as (_, foreign_store):
        with foreign_store.tx() as cur:
            foreign_store.insert_record(cur, party)
            foreign_store.insert_record(cur, grant)

        assert foreign_store.get_record(foreign_party) is not None
        assert store.get_record(foreign_party) is None
        assert store.get_payload(foreign_party) is None
        assert not store.record_exists(foreign_party)
        assert foreign_grant not in {
            row["payload"]["authorityGrantId"]
            for row in store.find_by_kind("ofarm.authoritygrant.v0.1")
        }

        decision = AuthorityEvaluator(store).evaluate(
            acting_party_ref=foreign_party,
            action_class="ASSERT_OPERATION_CLAIM",
            action_stage="PROMOTION",
            scope={"scopeType": "FARM", "scopeRef": demo.FARM},
        )
        assert decision.outcome == "DENY"
        assert foreign_grant not in decision.result_payload["grantBasisUsed"]

        with TestClient(create_app(store, oidc=None)) as client:
            response = client.get(
                f"/records/{foreign_party}",
                headers={"x-acting-party": foreign_party},
            )
        assert response.status_code == 401
        assert response.json()["detail"]["reasonCode"] == "AUTHORITY_DENIED"


def test_foreign_tenant_history_cannot_enter_materialization_or_output(fresh_env):
    store, pipeline, outputs = fresh_env
    committed = pipeline.commit(demo.spray_submission(
        f"tenant-history:{_uid()}",
        erp_id=f"erp:tenant-history.{_uid()}",
        confirm=True,
    ))
    queued = pipeline.commit(demo.spray_submission(
        f"tenant-output:{_uid()}",
        erp_id=f"erp:tenant-output.{_uid()}",
        confirm=False,
    ))
    foreign_consequence = f"conseq:foreign-tenant.{_uid()}"
    foreign_assertion = f"assert:foreign-tenant.{_uid()}"

    with _foreign_tenant_store(store, "history") as (_, foreign_store):
        _seed_foreign_review_target(
            store,
            foreign_store,
            source_target=committed["emittedAcceptedConsequenceRefs"][0],
            foreign_target=foreign_consequence,
            identity_field="acceptedEventConsequenceId",
            emitted_refs_field="emittedAcceptedConsequenceRefs",
        )
        _seed_foreign_review_target(
            store,
            foreign_store,
            source_target=queued["emittedAssertionRecordRefs"][0],
            foreign_target=foreign_assertion,
            identity_field="assertionRecordId",
            emitted_refs_field="emittedAssertionRecordRefs",
        )

        assert foreign_store.get_record(foreign_consequence) is not None
        assert foreign_consequence not in {
            row["record_id"]
            for row in store.in_force_consequences(demo.FARM)
        }

        with store.serialized_tx() as cur:
            resolution = Materializer(store).resolve_for_use(
                cur,
                demo.FARM,
                time_policy={
                    "policyType": "AS_OF",
                    "asOfTime": "2099-01-01T00:00:00Z",
                },
            )
        materialization = resolution["materialization"]
        basis = store.get_payload(materialization["basis_record_id"])
        assert foreign_consequence not in \
            basis["contributingAcceptedConsequenceRefs"]
        assert foreign_consequence not in {
            entry["consequenceRef"]
            for entry in materialization["current_state"]["entries"]
        }

        passport = outputs.passport_view(demo.FARM, demo.FARMER)
        assert passport["refused"] is False
        assert foreign_assertion not in {
            item["assertionRef"] for item in passport["body"]["exceptions"]
        }


def test_cross_tenant_edge_is_refused_without_mutation(fresh_env):
    store, pipeline, _ = fresh_env
    queued = pipeline.commit(demo.spray_submission(
        f"tenant-edge:{_uid()}",
        erp_id=f"erp:tenant-edge.{_uid()}",
        confirm=False,
    ))
    local_assertion = queued["emittedAssertionRecordRefs"][0]
    foreign_evidence = f"evidence:foreign-tenant.{_uid()}"

    with _foreign_tenant_store(store, "edge") as (_, foreign_store):
        _seed_foreign_evidence(store, foreign_store, foreign_evidence)
        edge_args = (local_assertion, foreign_evidence, store.tenant_ref)

        def edge_count() -> int:
            return store.conn.execute(
                "SELECT COUNT(*) AS count FROM kernel_edge "
                "WHERE edge_type = 'EVIDENCE' AND src_record_id = %s "
                "AND dst_record_id = %s AND tenant_ref = %s",
                edge_args,
            ).fetchone()["count"]

        assert edge_count() == 0
        with pytest.raises(RuntimeBundleBindingError):
            with store.tx() as cur:
                store.add_edge(
                    cur,
                    "EVIDENCE",
                    local_assertion,
                    foreign_evidence,
                )
        assert edge_count() == 0
        assert foreign_store.get_record(foreign_evidence) is not None


def test_same_tenant_history_remains_visible_after_bundle_change(fresh_env):
    store_a, pipeline_a, _ = fresh_env
    committed = pipeline_a.commit(demo.spray_submission(
        f"same-tenant-history:{_uid()}",
        erp_id=f"erp:same-tenant-history.{_uid()}",
        confirm=True,
    ))
    consequence = committed["emittedAcceptedConsequenceRefs"][0]
    source_bundle = store_a.runtime_bundle_digest

    store_b = _second_store(store_a)
    try:
        assert store_b.runtime_bundle_digest != source_bundle
        assert store_b.get_record(consequence)["runtime_bundle_digest"] == \
            source_bundle
        assert consequence in {
            row["record_id"]
            for row in store_b.find_by_kind(
                "ofarm.acceptedeventconsequence.v0.1"
            )
        }
        assert consequence in {
            row["record_id"]
            for row in store_b.in_force_consequences(demo.FARM)
        }
        assert store_b.edges_to(consequence, "PROMOTION_EMITS")
    finally:
        store_b.close()


def test_cross_bundle_queue_acceptance_refuses_but_rejection_can_close_history(
    fresh_env,
):
    store_a, pipeline_a, _ = fresh_env
    queued = pipeline_a.commit(demo.spray_submission(
        f"queue-a:{_uid()}", erp_id=f"erp:queue-a.{_uid()}", confirm=False))
    target = queued["emittedAssertionRecordRefs"][0]
    assert store_a.get_record(target)["runtime_bundle_digest"] == \
        store_a.runtime_bundle_digest

    store_b = _second_store(store_a)
    try:
        pipeline_b = GatePipeline(store_b)
        reviews_before = len(store_b.find_by_kind("ofarm.reviewdecision.v0.1"))
        consequences_before = len(store_b.find_by_kind(
            "ofarm.acceptedeventconsequence.v0.1"))
        business_before = _continuation_business_state(store_b)

        refused = pipeline_b.commit(_accept_submission(
            target, f"queue-accept-b:{_uid()}"))
        assert refused["decisionOutcome"] == "RETAIN_DRAFT"
        assert refused["problems"][0]["reasonCode"] == "PACK_CONFLICT"
        assert store_b.edges_from(target, "REVIEW") == []
        assert len(store_b.find_by_kind("ofarm.reviewdecision.v0.1")) == reviews_before
        assert len(store_b.find_by_kind(
            "ofarm.acceptedeventconsequence.v0.1")) == consequences_before
        assert _continuation_business_state(store_b) == business_before
        assert target in {
            row["assertionRef"]
            for row in OutputGenerator(store_b)._pending_claims(demo.FARM)
        }
        assert store_b.get_record(refused["resultId"])["runtime_bundle_digest"] == \
            store_b.runtime_bundle_digest

        rejected = pipeline_b.commit(_reject_submission(
            target, f"queue-reject-b:{_uid()}"))
        assert rejected["decisionOutcome"] == "RETAIN_DRAFT"
        assert "emittedAcceptedConsequenceRefs" not in rejected
        review_id = rejected["emittedReviewDecisionRefs"][0]
        assert store_b.get_record(review_id)["runtime_bundle_digest"] == \
            store_b.runtime_bundle_digest
        assert len(store_b.edges_from(target, "REVIEW")) == 1
        assert len(store_b.find_by_kind(
            "ofarm.acceptedeventconsequence.v0.1")) == consequences_before
        assert target not in {
            row["assertionRef"]
            for row in OutputGenerator(store_b)._pending_claims(demo.FARM)
        }
        later = pipeline_b.commit(_accept_submission(
            target, f"queue-after-reject-b:{_uid()}"))
        assert later["decisionOutcome"] == "RETAIN_DRAFT"
        assert later["problems"][0]["reasonCode"] == "PACK_CONFLICT"
        assert len(store_b.edges_from(target, "REVIEW")) == 1
        assert len(store_b.find_by_kind(
            "ofarm.acceptedeventconsequence.v0.1")) == consequences_before
    finally:
        store_b.close()


def test_cross_bundle_idempotency_replay_is_blocked(fresh_env):
    store_a, pipeline_a, _ = fresh_env
    submission = demo.spray_submission(
        f"replay-a:{_uid()}", erp_id=f"erp:replay-a.{_uid()}", confirm=True)
    first = pipeline_a.commit(copy.deepcopy(submission))
    assert first["decisionOutcome"] == "PROMOTE_ACCEPTED"
    consequences_before = len(store_a.find_by_kind(
        "ofarm.acceptedeventconsequence.v0.1"))

    store_b = _second_store(store_a)
    try:
        business_before = _continuation_business_state(store_b)
        blocked = GatePipeline(store_b).commit(copy.deepcopy(submission))
        assert blocked["decisionOutcome"] == "DENY"
        assert blocked["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
        assert blocked["problems"][0]["reasonCode"] == "PACK_CONFLICT"
        assert blocked["replayOfRequestId"] == first["requestId"]
        assert len(store_b.find_by_kind(
            "ofarm.acceptedeventconsequence.v0.1")) == consequences_before
        assert _continuation_business_state(store_b) == business_before
        assert store_b.get_record(blocked["resultId"])["runtime_bundle_digest"] == \
            store_b.runtime_bundle_digest
        prior = store_b.conn.execute(
            "SELECT runtime_bundle_digest FROM kernel_idempotency "
            "WHERE idempotency_key = %s", (submission["idempotencyKey"],)
        ).fetchone()
        assert prior["runtime_bundle_digest"] == store_a.runtime_bundle_digest
    finally:
        store_b.close()


def test_idempotency_keys_are_tenant_qualified(fresh_env):
    store, _, _ = fresh_env
    key = f"idempotency:tenant-qualified.{_uid()}"
    foreign_request = f"request:foreign-tenant.{_uid()}"
    local_request = f"request:local-tenant.{_uid()}"

    with _foreign_tenant_store(store, "idempotency") as (
        foreign_tenant,
        foreign_store,
    ):
        with foreign_store.tx() as cur:
            foreign_store.idempotency_claim(
                cur,
                key,
                foreign_request,
                sha256_of({"tenant": foreign_tenant}),
                f"cires:foreign-tenant.{_uid()}",
            )
        with store.tx() as cur:
            assert store.idempotency_lookup(cur, key) is None
            store.idempotency_claim(
                cur,
                key,
                local_request,
                sha256_of({"tenant": store.tenant_ref}),
                f"cires:local-tenant.{_uid()}",
            )
        with foreign_store.tx() as cur:
            assert foreign_store.idempotency_lookup(cur, key)["request_id"] == \
                foreign_request
        with store.tx() as cur:
            assert store.idempotency_lookup(cur, key)["request_id"] == local_request

        rows = store.conn.execute(
            "SELECT tenant_ref, request_id FROM kernel_idempotency "
            "WHERE idempotency_key = %s ORDER BY tenant_ref",
            (key,),
        ).fetchall()
        assert {(row["tenant_ref"], row["request_id"]) for row in rows} == {
            (foreign_tenant, foreign_request),
            (store.tenant_ref, local_request),
        }


def test_cross_bundle_materialization_recomputes_and_reuses_only_its_own_cache(
    fresh_env,
):
    store_a, pipeline_a, _ = fresh_env
    materializer_a = Materializer(store_a)
    with store_a.serialized_tx() as cur:
        first = materializer_a.resolve_for_use(cur, demo.FARM)
    row_a = first["materialization"]

    store_b = _second_store(store_a)
    try:
        assert context.bootstrap_for_descriptor(
            store_b, config.ACTIVE_PROFILE
        ) == [], "unchanged selected bytes may be reused across bundles"
        materializer_b = Materializer(store_b)
        with store_b.serialized_tx() as cur:
            second = materializer_b.resolve_for_use(cur, demo.FARM)
        assert second["decision"] == "RECOMPUTE_REQUIRED"
        row_b = second["materialization"]
        assert row_b["materialization_id"] != row_a["materialization_id"]
        assert row_b["key_digest"] != row_a["key_digest"]
        assert row_b["context_snapshot_ref"] != row_a["context_snapshot_ref"]
        assert len(row_b["key_digest"].split(":", 1)[1]) == 64
        assert len(row_b["context_snapshot_ref"].rsplit(".", 1)[1]) == 64
        assert row_a["runtime_bundle_digest"] == store_a.runtime_bundle_digest
        assert row_b["runtime_bundle_digest"] == store_b.runtime_bundle_digest
        assert store_b.get_record(
            row_b["context_snapshot_ref"])["runtime_bundle_digest"] == \
            store_b.runtime_bundle_digest

        with store_b.serialized_tx() as cur:
            reused = materializer_b.resolve_for_use(cur, demo.FARM)
        assert reused["decision"] == "ALLOW_REUSE"
        assert reused["materialization"]["materialization_id"] == \
            row_b["materialization_id"]

        advanced = pipeline_a.commit(demo.spray_submission(
            f"advance-a:{_uid()}", erp_id=f"erp:advance-a.{_uid()}",
            confirm=True))
        assert advanced["decisionOutcome"] == "PROMOTE_ACCEPTED"
        stale_b = store_b.conn.execute(
            "SELECT freshness FROM derived_materialization "
            "WHERE materialization_id = %s",
            (row_b["materialization_id"],),
        ).fetchone()
        assert stale_b["freshness"] == "STALE"

        with store_b.serialized_tx() as cur:
            refreshed = materializer_b.resolve_for_use(cur, demo.FARM)
        assert refreshed["decision"] == "RECOMPUTE_REQUIRED"
        assert refreshed["materialization"]["materialization_id"] != \
            row_b["materialization_id"]
    finally:
        store_b.close()


def test_cross_bundle_identical_import_rebuilds_current_parsed_cache(fresh_env):
    store_a, _, _ = fresh_env
    snapshot_id = f"referencesnapshot:bundle-cache.{_uid()}"
    parsed = ParseResult(
        ok=True,
        sourceDigest=f"sha256-cache-{_uid()}",
        artifactRef=f"artifact:bundle-cache.{_uid()}",
        recordCount=1,
        records={"rows": [{"code": "fictional-1"}]},
    )
    meta = _snapshot_meta(snapshot_id)
    first = ImportRunner(store_a).run_import(
        parsed, meta, data_family="bundle-cache-fixture")
    assert first["disposition"] == "IMPORTED"
    assert store_a.reference_data("bundle-cache-fixture")

    store_b = _second_store(store_a)
    try:
        assert store_b.reference_data("bundle-cache-fixture") == []
        replay = ImportRunner(store_b).run_import(
            parsed, meta, data_family="bundle-cache-fixture")
        assert replay["disposition"] == "ALREADY_IMPORTED"
        rebuilt = store_b.reference_data("bundle-cache-fixture")
        assert rebuilt == [{
            "snapshot_ref": snapshot_id,
            "payload": parsed.records,
        }]
        assert store_b.get_record(snapshot_id)["runtime_bundle_digest"] == \
            store_a.runtime_bundle_digest
        cache_row = store_b.conn.execute(
            "SELECT runtime_bundle_digest FROM reference_snapshot_data "
            "WHERE snapshot_ref = %s AND data_family = %s "
            "AND tenant_ref = %s",
            (snapshot_id, "bundle-cache-fixture", store_b.tenant_ref),
        ).fetchall()
        assert {row["runtime_bundle_digest"] for row in cache_row} == {
            store_a.runtime_bundle_digest, store_b.runtime_bundle_digest}
    finally:
        store_b.close()


def test_selected_regsr_lookup_is_unchanged_by_governed_cache_fill(fresh_env):
    store, _, _ = fresh_env
    bindings = context.SIReferenceBindings.from_runtime_descriptor(
        store.active_descriptor
    )
    snapshot, source, selected_decision = _selected_regsr_source(store)
    injected_decision = f"FICTIONAL-CACHE-{_uid()}"
    injected = {
        "products": [],
        "productDetails": [{
            "name": "FICTIONAL CACHE INPUT",
            "decisions": [{
                "decisionNumber": injected_decision,
                "issued": "2026-01-01",
                "validUntil": "2099-01-01",
            }],
        }],
    }
    before = context.ProductRegister(bindings)
    before.load_from_store(store)
    expected = before.lookup_by_decision(
        snapshot["referenceSnapshotId"], selected_decision
    )
    assert expected is not None

    replay = ImportRunner(store).run_import(
        ParseResult(
            ok=True,
            sourceDigest=source.content_digest,
            artifactRef=source.logical_ref,
            recordCount=1,
            records=injected,
        ),
        snapshot,
        data_family=bindings.regsr_data_family,
    )

    assert replay["disposition"] == "ALREADY_IMPORTED"
    assert any(
        row["snapshot_ref"] == snapshot["referenceSnapshotId"]
        and row["payload"] == injected
        for row in store.reference_data(bindings.regsr_data_family)
    )
    after = context.ProductRegister(bindings)
    after.load_from_store(store)
    assert after.lookup_by_decision(
        snapshot["referenceSnapshotId"], selected_decision
    ) == expected
    assert after.lookup_by_decision(
        snapshot["referenceSnapshotId"], injected_decision
    ) is None


def test_unequal_regsr_cache_cannot_override_selected_source(fresh_env):
    store, _, _ = fresh_env
    bindings = context.SIReferenceBindings.from_runtime_descriptor(
        store.active_descriptor
    )
    snapshot, source, selected_decision = _selected_regsr_source(store)
    injected_decision = f"FICTIONAL-UNEQUAL-{_uid()}"
    unequal = {
        "products": [],
        "productDetails": [{
            "name": "FICTIONAL UNEQUAL CACHE",
            "decisions": [{"decisionNumber": injected_decision}],
        }],
    }
    with store.tx() as cur:
        store.insert_reference_data(
            cur,
            snapshot["referenceSnapshotId"],
            bindings.regsr_data_family,
            unequal,
            artifact_ref=source.logical_ref,
            source_digest=source.content_digest,
            parser_label=snapshot["canonicalVersionLabel"],
            record_count=1,
        )

    register = context.ProductRegister(bindings)
    register.load_from_store(store)
    assert register.lookup_by_decision(
        snapshot["referenceSnapshotId"], selected_decision
    ) is not None
    assert register.lookup_by_decision(
        snapshot["referenceSnapshotId"], injected_decision
    ) is None


def test_selected_gerk_without_retained_source_refuses_operational_load(
    fresh_env,
):
    store, _, _ = fresh_env
    bindings = context.SIReferenceBindings.from_runtime_descriptor(
        store.active_descriptor
    )
    snapshot_ref = next(
        ref for ref in store.selected_reference_snapshot_refs
        if ref == bindings.gerk_snapshot_prefix
        or ref.startswith(bindings.gerk_snapshot_prefix + ".")
    )
    cache_payload = {
        "features": [{
            "gerkPid": "9999999",
            "rabaId": "1300",
            "area": "1.0000",
            "opisRabe": "fictional cache-only parcel",
        }],
    }
    with store.tx() as cur:
        store.insert_reference_data(
            cur,
            snapshot_ref,
            bindings.gerk_data_family,
            cache_payload,
            artifact_ref="archive:fictional-cache-only-gerk.zip",
            source_digest="sha256:" + "f" * 64,
            parser_label="fictional-cache-only",
            record_count=1,
        )

    with pytest.raises(
        RuntimeBundleBindingError,
        match="has no exact operational source",
    ):
        GerkLayer().load_from_store(store)


def test_cold_restart_uses_same_selected_regsr_bytes_without_cache(fresh_env):
    first, _, _ = fresh_env
    bindings = context.SIReferenceBindings.from_runtime_descriptor(
        first.active_descriptor
    )
    snapshot, _source, selected_decision = _selected_regsr_source(first)
    assert first.reference_data(bindings.regsr_data_family) == []
    first_register = context.ProductRegister(bindings)
    first_register.load_from_store(first)
    expected = first_register.lookup_by_decision(
        snapshot["referenceSnapshotId"], selected_decision
    )

    reconstructed_bundle = _selected_bundle()
    reconstructed_descriptor = load_profile_runtime_descriptor(
        config.ACTIVE_PROFILE.profile_root,
        descriptor_path=config.ACTIVE_PROFILE.descriptor_path,
    )
    assert reconstructed_bundle is not first.runtime_bundle
    assert reconstructed_bundle.digest == first.runtime_bundle_digest
    assert reconstructed_descriptor is not first.active_descriptor
    assert reconstructed_descriptor == first.active_descriptor
    restarted = Store(
        dsn=first.dsn,
        tenant_ref=first.tenant_ref,
        runtime_bundle=reconstructed_bundle,
        active_descriptor=reconstructed_descriptor,
    )
    try:
        complete_store_startup(restarted)
        assert restarted.reference_data(bindings.regsr_data_family) == []
        restarted_register = context.ProductRegister(bindings)
        restarted_register.load_from_store(restarted)
        assert restarted_register.lookup_by_decision(
            snapshot["referenceSnapshotId"], selected_decision
        ) == expected
    finally:
        restarted.close()


def test_product_authorisation_uses_only_bundle_selected_regsr_source_bytes():
    selected_decision = f"U9{_uid()[:4]}-50/26/s"
    release_path_decision = "U34330-50/23/16"
    selected_artifact = {
        "products": [],
        "productDetails": [{
            "name": "FIKTIV SELECTED (fictional)",
            "decisions": [{
                "decisionType": "Registracija",
                "decisionNumber": selected_decision,
                "issued": "2026-01-01",
                "validUntil": "2028-08-15",
            }],
        }],
    }

    with _isolated_store("selected_regsr_source") as source_store:
        selected_bundle = _bundle_with_alternate_regsr_source(
            source_store.runtime_bundle,
            selected_artifact,
        )
        selected_store = Store(
            dsn=source_store.dsn,
            tenant_ref=source_store.tenant_ref,
            runtime_bundle=selected_bundle,
            active_descriptor=source_store.active_descriptor,
        )
        try:
            create_app(selected_store, oidc=None)
            evidence = next(
                payload for payload in demo.substrate_records()
                if payload.get("evidenceRecordId") == demo.ONBOARDING_EVIDENCE
            )
            with selected_store.tx() as cur:
                selected_store.insert_record(cur, evidence)

            with selected_store.serialized_tx() as cur:
                selected = sib.resolve_product_authorisation(
                    selected_store,
                    cur,
                    selected_decision,
                    f"resource:selected.{_uid()}",
                    created_by=demo.FARMER,
                    evidence_ref=demo.ONBOARDING_EVIDENCE,
                    as_of="2026-06-12T12:00:00Z",
                )
            with selected_store.serialized_tx() as cur:
                release_path = sib.resolve_product_authorisation(
                    selected_store,
                    cur,
                    release_path_decision,
                    f"resource:path.{_uid()}",
                    created_by=demo.FARMER,
                    evidence_ref=demo.ONBOARDING_EVIDENCE,
                    as_of="2026-06-12T12:00:00Z",
                )

            assert selected["verdict"] == "CONFIRM"
            assert selected["trace"]["finalOutcome"] == "PASS"
            assert selected["binding"]["bindingState"] == "VERIFIED"
            assert selected["binding"]["promotionBoundary"][
                "maySupportPromotion"
            ] is True
            assert release_path["verdict"] != "CONFIRM"
            assert release_path["trace"]["finalOutcome"] != "PASS"
            assert release_path["binding"]["bindingState"] != "VERIFIED"
            assert release_path["binding"]["promotionBoundary"][
                "maySupportPromotion"
            ] is False
        finally:
            selected_store.close()


def test_imported_reference_snapshot_remains_inactive_under_current_bundle(
    fresh_env,
):
    store, pipeline_before, _ = fresh_env
    bindings = pipeline_before.runtime_services.reference_bindings
    selected_before = context.current_reference_snapshot(
        store, bindings.regsr_snapshot_prefix
    )
    assert selected_before is not None

    candidate_id = f"{bindings.regsr_snapshot_prefix}.candidate-{_uid()}"
    candidate_decision = f"fictional-decision-{_uid()}"
    records = {
        "products": [{"regsrCode": "fictional-1", "name": "FICTIONAL"}],
        "productDetails": [{
            "regsrCode": "fictional-1",
            "decisions": [{
                "decisionType": "FICTIONAL TEST",
                "decisionNumber": candidate_decision,
                "validUntil": "2099-12-31",
            }],
        }],
    }
    parsed = ParseResult(
        ok=True,
        sourceDigest=f"sha256-candidate-{_uid()}",
        artifactRef=f"artifact:candidate-{_uid()}",
        recordCount=1,
        records=records,
    )
    meta = _snapshot_meta(candidate_id)
    meta["effectiveFrom"] = context.now_iso()

    imported = ImportRunner(store).run_import(
        parsed,
        meta,
        data_family=bindings.regsr_data_family,
    )

    assert imported["disposition"] == "IMPORTED"
    assert any(
        row["snapshot_ref"] == candidate_id and row["payload"] == records
        for row in store.reference_data(bindings.regsr_data_family)
    ), "the candidate remains auditable in the bundle-qualified cache"
    selected_after = context.current_reference_snapshot(
        store, bindings.regsr_snapshot_prefix
    )
    assert selected_after["referenceSnapshotId"] == \
        selected_before["referenceSnapshotId"]
    assert candidate_id not in {
        component.logical_ref
        for component in store.runtime_bundle.components
        if component.role is RuntimeComponentRole.REFERENCE_SNAPSHOT
    }

    pipeline_after = GatePipeline(store)
    assert pipeline_before.runtime_services.product_lookup.lookup_by_decision(
        candidate_id, candidate_decision
    ) is None
    assert pipeline_after.runtime_services.product_lookup.lookup_by_decision(
        candidate_id, candidate_decision
    ) is None


def test_same_bundle_parsed_cache_refuses_unequal_reuse(fresh_env):
    store, _, _ = fresh_env
    snapshot_id = f"referencesnapshot:bundle-cache-equality.{_uid()}"
    family = "bundle-cache-equality-fixture"
    parsed = ParseResult(
        ok=True,
        sourceDigest=f"sha256-cache-equality-{_uid()}",
        artifactRef=f"artifact:bundle-cache-equality.{_uid()}",
        recordCount=1,
        records={"rows": [{"code": "fictional-1"}]},
    )
    meta = _snapshot_meta(snapshot_id)
    first = ImportRunner(store).run_import(parsed, meta)
    assert first["disposition"] == "IMPORTED"
    with store.tx() as cur:
        store.insert_reference_data(
            cur,
            snapshot_id,
            family,
            parsed.records,
            artifact_ref=parsed.artifactRef,
            source_digest=parsed.sourceDigest,
            parser_label=meta["canonicalVersionLabel"],
            record_count=parsed.recordCount,
        )
    changed = replace(
        parsed,
        records={"rows": [{"code": "fictional-2"}]},
    )
    before = store.conn.execute(
        "SELECT payload, payload_sha256, tenant_ref, runtime_bundle_digest "
        "FROM reference_snapshot_data WHERE snapshot_ref = %s "
        "AND data_family = %s AND tenant_ref = %s "
        "AND runtime_bundle_digest = %s",
        (snapshot_id, family, store.tenant_ref, store.runtime_bundle_digest),
    ).fetchone()

    refused = ImportRunner(store).run_import(changed, meta, data_family=family)
    assert refused["disposition"] == "CONFLICT"
    assert refused["problem"]["reasonCode"] == "DUPLICATE_IMPORT_AMBIGUOUS"
    after = store.conn.execute(
        "SELECT payload, payload_sha256, tenant_ref, runtime_bundle_digest "
        "FROM reference_snapshot_data WHERE snapshot_ref = %s "
        "AND data_family = %s AND tenant_ref = %s "
        "AND runtime_bundle_digest = %s",
        (snapshot_id, family, store.tenant_ref, store.runtime_bundle_digest),
    ).fetchone()
    assert after == before
    refusal = store.conn.execute(
        "SELECT runtime_bundle_digest FROM kernel_gate_log "
        "WHERE gate = 'GOVERNED_IMPORT' AND reason_code = "
        "'DUPLICATE_IMPORT_AMBIGUOUS' ORDER BY entry_id DESC LIMIT 1"
    ).fetchone()
    assert refusal["runtime_bundle_digest"] == store.runtime_bundle_digest


def test_same_bundle_parsed_cache_refuses_metadata_only_mismatch(fresh_env):
    store, _, _ = fresh_env
    snapshot_id = f"referencesnapshot:bundle-cache-metadata.{_uid()}"
    family = "bundle-cache-metadata-fixture"
    parsed = ParseResult(
        ok=True,
        sourceDigest=f"sha256-cache-metadata-{_uid()}",
        artifactRef=f"artifact:bundle-cache-metadata.{_uid()}",
        recordCount=1,
        records={"rows": [{"code": "fictional-1"}]},
    )
    meta = _snapshot_meta(snapshot_id)
    first = ImportRunner(store).run_import(parsed, meta)
    assert first["disposition"] == "IMPORTED"
    with store.tx() as cur:
        store.insert_reference_data(
            cur,
            snapshot_id,
            family,
            parsed.records,
            artifact_ref=parsed.artifactRef,
            source_digest=parsed.sourceDigest,
            parser_label=meta["canonicalVersionLabel"],
            record_count=parsed.recordCount,
        )
    semantic_columns = (
        "snapshot_ref, data_family, artifact_ref, source_digest, parser_label, "
        "record_count, payload, payload_sha256, tenant_ref, runtime_bundle_digest"
    )
    before = store.conn.execute(
        f"SELECT {semantic_columns} FROM reference_snapshot_data "
        "WHERE snapshot_ref = %s AND data_family = %s AND tenant_ref = %s "
        "AND runtime_bundle_digest = %s",
        (snapshot_id, family, store.tenant_ref, store.runtime_bundle_digest),
    ).fetchone()
    assert before["record_count"] == 1

    refused = ImportRunner(store).run_import(
        replace(parsed, recordCount=2),
        meta,
        data_family=family,
    )

    assert refused["disposition"] == "CONFLICT"
    assert refused["problem"]["reasonCode"] == "DUPLICATE_IMPORT_AMBIGUOUS"
    after = store.conn.execute(
        f"SELECT {semantic_columns} FROM reference_snapshot_data "
        "WHERE snapshot_ref = %s AND data_family = %s AND tenant_ref = %s "
        "AND runtime_bundle_digest = %s",
        (snapshot_id, family, store.tenant_ref, store.runtime_bundle_digest),
    ).fetchone()
    assert after == before
    refusal = store.conn.execute(
        "SELECT runtime_bundle_digest FROM kernel_gate_log "
        "WHERE gate = 'GOVERNED_IMPORT' AND reason_code = "
        "'DUPLICATE_IMPORT_AMBIGUOUS' ORDER BY entry_id DESC LIMIT 1"
    ).fetchone()
    assert refusal["runtime_bundle_digest"] == store.runtime_bundle_digest


def test_reference_snapshot_cache_is_append_only(fresh_env):
    store, _, _ = fresh_env
    before = store.conn.execute(
        "SELECT COUNT(*) AS count FROM reference_snapshot_data"
    ).fetchone()["count"]
    mutations = (
        "UPDATE reference_snapshot_data SET record_count = record_count",
        "DELETE FROM reference_snapshot_data",
        "TRUNCATE TABLE reference_snapshot_data",
    )

    for statement in mutations:
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            with store.tx() as cur:
                cur.execute(statement)
        after = store.conn.execute(
            "SELECT COUNT(*) AS count FROM reference_snapshot_data"
        ).fetchone()["count"]
        assert after == before


def test_reference_snapshot_cache_read_verifies_payload_digest(fresh_env):
    store, _, _ = fresh_env
    snapshot_id = f"referencesnapshot:corrupt-cache.{_uid()}"
    family = f"corrupt-cache-{_uid()}"
    payload = {"rows": [{"code": "fictional-corrupt"}]}
    with store.tx() as cur:
        cur.execute(
            "INSERT INTO reference_snapshot_data "
            "(snapshot_ref, data_family, payload, payload_sha256, tenant_ref, "
            "runtime_bundle_digest) VALUES (%s, %s, %s::jsonb, %s, %s, %s)",
            (
                snapshot_id,
                family,
                json.dumps(payload),
                sha256_of({"different": "payload"}),
                store.tenant_ref,
                store.runtime_bundle_digest,
            ),
        )

    with pytest.raises(RuntimeBundleBindingError, match="payload digest verification"):
        store.reference_data(family)
