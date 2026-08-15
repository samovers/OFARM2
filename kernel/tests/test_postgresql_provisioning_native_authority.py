"""Lazy provisioning binding and frozen native-authority release gates."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest

from deployment.postgresql import migration_cli
from deployment.postgresql import migration_runner
from deployment.postgresql import migration_sets
from deployment.postgresql import native_release_identity
from deployment.postgresql import provisioning
from deployment.postgresql import provisioning_specs
from deployment.postgresql import readiness
from deployment.postgresql.migration_sets import TENANT_SERVICE
from deployment.postgresql.native_release_identity import (
    EVIDENCE_RECEIPT_PATH,
    IDENTITY_PATH,
    SOURCE_DIRECTORY,
    VERIFICATION_CURRENTNESS_PATH,
    NativeReleaseIdentityError,
    canonical_json_bytes,
    load_native_evidence_receipt,
    load_native_release_identity,
    provisional_evidence_receipt_document,
    provisional_identity_document,
    validate_native_evidence_receipt,
    validate_native_release_identity,
)
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC,
    ProvisioningSpecError,
    require_frozen_tenant_native_verifier_authority,
)


_EXECUTION_ID = UUID("11111111-1111-4111-8111-111111111111")


def _raise_unavailable(*args: object, **kwargs: object) -> None:
    del args, kwargs
    raise NativeReleaseIdentityError("hostile authority file is unavailable")


def _raise_stale(*args: object, **kwargs: object) -> None:
    del args, kwargs
    raise NativeReleaseIdentityError("hostile authority file differs from current files")


@pytest.mark.parametrize(
    "failure_mode",
    ("missing", "stale"),
)
def test_audit_import_and_use_never_loads_tenant_authority(
    failure_mode: str,
) -> None:
    script = """
import json
from pathlib import Path

mode = __FAILURE_MODE__
identity_path = Path(
    'deployment/postgresql/ofarm_ed25519/native_release_identity.json'
).resolve()
receipt_path = Path(
    'deployment/postgresql/ofarm_ed25519/native_evidence_receipt.json'
).resolve()
if mode == 'missing':
    real_lstat = Path.lstat
    missing_paths = {str(identity_path), str(receipt_path)}

    def hostile_lstat(self, *args, **kwargs):
        if str(self) in missing_paths:
            raise FileNotFoundError('hostile authority file is unavailable')
        return real_lstat(self, *args, **kwargs)

    Path.lstat = hostile_lstat
else:
    identity_document = json.loads(identity_path.read_bytes())
    identity_document['sourceInput']['digest'] = 'sha256:' + '0' * 64
    stale_identity = (
        json.dumps(
            identity_document,
            ensure_ascii=True,
            sort_keys=True,
            separators=(',', ':'),
        )
        + '\\n'
    ).encode('ascii')
    real_read_bytes = Path.read_bytes

    def hostile_read_bytes(self):
        if str(self) == str(identity_path):
            return stale_identity
        return real_read_bytes(self)

    Path.read_bytes = hostile_read_bytes

import deployment.postgresql.provisioning_specs as specs
audit = specs.SECURITY_AUDIT_PROVISIONING_SPEC
assert audit.native_verifier is None
assert 'nativeVerifier' not in audit.manifest()['preLedgerBootstrap']
assert audit.digest.startswith('sha256:')
assert audit.canonical_manifest_bytes()
""".replace("__FAILURE_MODE__", repr(failure_mode))
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=provisioning_specs.PACKAGE_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr


def test_tenant_provisioning_manifest_lazily_binds_complete_current_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = TENANT_PROVISIONING_SPEC.native_verifier
    assert verifier is not None
    identity = load_native_release_identity(verify_current_sources=True)
    receipt = load_native_evidence_receipt(
        release_identity=identity,
        verify_current_authority=True,
    )
    identity_calls = 0
    receipt_calls = 0
    real_identity_loader = provisioning_specs.load_native_release_identity
    real_receipt_loader = provisioning_specs.load_native_evidence_receipt

    def count_identity(*args: object, **kwargs: object):
        nonlocal identity_calls
        identity_calls += 1
        assert args == (provisioning_specs.IDENTITY_PATH,)
        assert kwargs == {
            "verify_current_sources": True,
            "source_directory": provisioning_specs.SOURCE_DIRECTORY,
        }
        return real_identity_loader(*args, **kwargs)

    def count_receipt(*args: object, **kwargs: object):
        nonlocal receipt_calls
        receipt_calls += 1
        assert args == (provisioning_specs.EVIDENCE_RECEIPT_PATH,)
        assert kwargs["verify_current_authority"] is True
        assert kwargs["repository_root"] == provisioning_specs.PACKAGE_ROOT
        assert set(kwargs) == {
            "release_identity",
            "repository_root",
            "verify_current_authority",
        }
        return real_receipt_loader(*args, **kwargs)

    monkeypatch.setattr(
        provisioning_specs, "load_native_release_identity", count_identity
    )
    monkeypatch.setattr(
        provisioning_specs, "load_native_evidence_receipt", count_receipt
    )

    authority = verifier.manifest()["checkedReleaseAuthority"]
    assert (identity_calls, receipt_calls) == (1, 1)
    assert authority["releaseIdentity"] == {
        "canonicalDigest": identity.digest,
        "status": identity.status,
        "sourceInputDigest": identity.document["sourceInput"]["digest"],
        "indexDigest": identity.index_digest,
        "document": identity.manifest(),
    }
    assert authority["evidenceReceipt"] == {
        "canonicalDigest": receipt.digest,
        "status": receipt.status,
        "evidenceAuthorityInputDigest": receipt.document[
            "evidenceAuthorityInput"
        ]["digest"],
        "document": receipt.manifest(),
    }

    TENANT_PROVISIONING_SPEC.digest
    assert (identity_calls, receipt_calls) == (2, 2)
    TENANT_PROVISIONING_SPEC.manifest()
    assert (identity_calls, receipt_calls) == (3, 3)
    TENANT_PROVISIONING_SPEC.canonical_manifest_bytes()
    assert (identity_calls, receipt_calls) == (4, 4)


def test_currentness_sidecar_preserves_exact_tenant_provisioning_identity() -> None:
    receipt_bytes = EVIDENCE_RECEIPT_PATH.read_bytes()
    assert len(receipt_bytes) == 25_682
    assert "sha256:" + hashlib.sha256(receipt_bytes).hexdigest() == (
        "sha256:5a13f99a5252828da01df0e2d2e5b8d"
        "491b99ec795736e5becc2659616a575c3"
    )
    assert TENANT_PROVISIONING_SPEC.digest == (
        "sha256:2ac8487b64d4fb09d7576ef1ee09ac1f"
        "2a3cc5b20558f0d2137620b897c7157c"
    )
    manifest_bytes = TENANT_PROVISIONING_SPEC.canonical_manifest_bytes()
    assert b"native_evidence_verification_currentness" not in manifest_bytes
    assert VERIFICATION_CURRENTNESS_PATH.read_bytes() not in manifest_bytes


@pytest.mark.parametrize("mode", ("missing", "stale"))
def test_tenant_manifest_refuses_missing_or_stale_currentness_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    sidecar = tmp_path / "verification-currentness.json"
    if mode == "stale":
        document = json.loads(VERIFICATION_CURRENTNESS_PATH.read_bytes())
        authority = document["verificationAuthorityInput"]
        authority["files"][0]["sha256"] = "sha256:" + "0" * 64
        authority_body = {
            "algorithm": authority["algorithm"],
            "files": authority["files"],
        }
        authority["digest"] = "sha256:" + hashlib.sha256(
            canonical_json_bytes(authority_body)
        ).hexdigest()
        sidecar.write_bytes(canonical_json_bytes(document))
    monkeypatch.setattr(
        native_release_identity,
        "VERIFICATION_CURRENTNESS_PATH",
        sidecar,
    )

    with pytest.raises(ProvisioningSpecError, match="invalid or stale") as raised:
        TENANT_PROVISIONING_SPEC.manifest()

    assert isinstance(raised.value.__cause__, NativeReleaseIdentityError)
    assert "verification currentness" in str(raised.value.__cause__)


@pytest.mark.parametrize("failed_loader", ("identity", "receipt"))
@pytest.mark.parametrize("failure", (_raise_unavailable, _raise_stale))
def test_audit_only_manifests_ignore_missing_or_stale_tenant_authority(
    monkeypatch: pytest.MonkeyPatch,
    failed_loader: str,
    failure,
) -> None:
    monkeypatch.setattr(
        provisioning_specs,
        f"load_native_{'release_identity' if failed_loader == 'identity' else 'evidence_receipt'}",
        failure,
    )

    manifest = SECURITY_AUDIT_PROVISIONING_SPEC.manifest()
    assert manifest["identity"] == SECURITY_AUDIT_PROVISIONING_SPEC.identity
    assert "nativeVerifier" not in manifest["preLedgerBootstrap"]
    assert SECURITY_AUDIT_PROVISIONING_SPEC.digest.startswith("sha256:")
    assert json.loads(
        SECURITY_AUDIT_PROVISIONING_SPEC.canonical_manifest_bytes()
    )["identity"] == SECURITY_AUDIT_PROVISIONING_SPEC.identity


def test_audit_only_manifest_never_loads_currentness_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        native_release_identity,
        "VERIFICATION_CURRENTNESS_PATH",
        tmp_path / "missing-currentness.json",
    )

    manifest = SECURITY_AUDIT_PROVISIONING_SPEC.manifest()
    assert manifest["identity"] == SECURITY_AUDIT_PROVISIONING_SPEC.identity
    assert "nativeVerifier" not in manifest["preLedgerBootstrap"]
    assert SECURITY_AUDIT_PROVISIONING_SPEC.digest.startswith("sha256:")


@pytest.mark.parametrize("failure", (_raise_unavailable, _raise_stale))
def test_tenant_manifest_fails_closed_on_missing_or_stale_authority(
    monkeypatch: pytest.MonkeyPatch,
    failure,
) -> None:
    monkeypatch.setattr(
        provisioning_specs, "load_native_release_identity", failure
    )

    with pytest.raises(ProvisioningSpecError, match="invalid or stale"):
        TENANT_PROVISIONING_SPEC.manifest()


def test_full_schema_rejects_digest_linked_but_incomplete_frozen_pair(
    tmp_path: Path,
) -> None:
    source_copy = tmp_path / "native-source"
    shutil.copytree(SOURCE_DIRECTORY, source_copy)
    identity_path = source_copy / IDENTITY_PATH.name
    identity_document = json.loads(identity_path.read_bytes())
    identity_document["status"] = "frozen"
    identity_document["index"] = {"sha256": "sha256:" + "a" * 64}
    identity_bytes = canonical_json_bytes(identity_document)
    identity_path.write_bytes(identity_bytes)

    receipt_path = source_copy / "native_evidence_receipt.json"
    receipt_document = json.loads(receipt_path.read_bytes())
    receipt_document["status"] = "frozen"
    receipt_document["releaseIdentityDigest"] = (
        "sha256:" + hashlib.sha256(identity_bytes).hexdigest()
    )
    receipt_document["preservation"] = {"status": "verified"}
    receipt_bytes = canonical_json_bytes(receipt_document)
    receipt_path.write_bytes(receipt_bytes)

    assert identity_document["status"] == receipt_document["status"] == "frozen"
    assert identity_document["index"]["sha256"].startswith("sha256:")
    assert receipt_document["releaseIdentityDigest"] == (
        "sha256:" + hashlib.sha256(identity_bytes).hexdigest()
    )
    assert receipt_document["preservation"]["status"] == "verified"

    with pytest.raises(ProvisioningSpecError, match="invalid or stale") as raised:
        provisioning_specs._load_current_native_verifier_authority(
            identity_path=identity_path,
            evidence_receipt_path=receipt_path,
            source_directory=source_copy,
        )

    assert isinstance(raised.value.__cause__, NativeReleaseIdentityError)
    assert "canonical index identity fields" in str(raised.value.__cause__)


def test_validated_provisional_documents_remain_bootstrap_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_document = provisional_identity_document()
    identity_bytes = canonical_json_bytes(identity_document)
    identity = validate_native_release_identity(
        identity_document,
        canonical_bytes=identity_bytes,
        source_directory=SOURCE_DIRECTORY,
    )
    receipt_document = provisional_evidence_receipt_document(
        release_identity=identity
    )
    receipt = validate_native_evidence_receipt(
        receipt_document,
        canonical_bytes=canonical_json_bytes(receipt_document),
        release_identity=identity,
        repository_root=provisioning_specs.PACKAGE_ROOT,
    )
    assert (identity.status, receipt.status, identity.index_digest) == (
        "provisional",
        "provisional",
        None,
    )
    monkeypatch.setattr(
        provisioning_specs,
        "_load_current_native_verifier_authority",
        lambda: (identity, receipt),
    )

    with pytest.raises(ProvisioningSpecError, match="not frozen"):
        require_frozen_tenant_native_verifier_authority()


def test_normal_tenant_entry_points_refuse_before_external_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse() -> None:
        raise ProvisioningSpecError("hostile incomplete frozen authority")

    monkeypatch.setattr(
        provisioning, "require_frozen_tenant_native_verifier_authority", refuse
    )
    with pytest.raises(
        provisioning.ProvisioningTargetError,
        match="incomplete frozen",
    ):
        provisioning._require_fixed_spec(TENANT_PROVISIONING_SPEC)

    monkeypatch.setattr(
        migration_runner,
        "require_frozen_tenant_native_verifier_authority",
        refuse,
    )
    with pytest.raises(
        migration_runner.MigrationInputError,
        match="incomplete frozen",
    ):
        migration_runner._require_fixed_pair(TENANT_PROVISIONING_SPEC, object())

    monkeypatch.setattr(
        readiness, "require_frozen_tenant_native_verifier_authority", refuse
    )
    monkeypatch.setattr(
        readiness.psycopg,
        "connect",
        lambda *args, **kwargs: pytest.fail("tenant readiness connected"),
    )
    with pytest.raises(
        readiness.PostgreSQLVerificationError,
        match="incomplete frozen",
    ):
        readiness.verify_tenant_structural_compatibility(
            tenant_structural_dsn="hostile-route"
        )


def test_missing_currentness_refuses_tenant_entry_points_before_external_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        native_release_identity,
        "VERIFICATION_CURRENTNESS_PATH",
        tmp_path / "missing-currentness.json",
    )

    with pytest.raises(
        provisioning.ProvisioningTargetError,
        match="invalid or stale",
    ):
        provisioning._require_fixed_spec(TENANT_PROVISIONING_SPEC)

    with pytest.raises(
        migration_runner.MigrationInputError,
        match="invalid or stale",
    ):
        migration_runner._require_fixed_pair(TENANT_PROVISIONING_SPEC, object())

    monkeypatch.setattr(
        readiness.psycopg,
        "connect",
        lambda *args, **kwargs: pytest.fail("tenant readiness connected"),
    )
    with pytest.raises(
        readiness.PostgreSQLVerificationError,
        match="invalid or stale",
    ):
        readiness.verify_tenant_structural_compatibility(
            tenant_structural_dsn="hostile-route"
        )

    monkeypatch.delenv("HOSTILE_ADMIN_DSN", raising=False)
    monkeypatch.delenv("HOSTILE_MIGRATOR_DSN", raising=False)
    monkeypatch.setattr(
        migration_cli,
        "load_authoritative_migration_set",
        lambda *args, **kwargs: pytest.fail("migration files were loaded"),
    )
    with pytest.raises(SystemExit) as migration_exit:
        migration_cli.run_fixed_migration_cli(
            service=TENANT_SERVICE,
            spec=TENANT_PROVISIONING_SPEC,
            admin_dsn_environment="HOSTILE_ADMIN_DSN",
            migrator_dsn_environment="HOSTILE_MIGRATOR_DSN",
            argv=(
                "--release-identity",
                "ofarm-release/174",
                "--execution-id",
                str(_EXECUTION_ID),
            ),
        )
    assert migration_exit.value.code == 1

    monkeypatch.setattr(
        migration_sets,
        "load_authoritative_migration_set",
        lambda *args, **kwargs: pytest.fail("migration sources were loaded"),
    )
    with pytest.raises(SystemExit) as preflight_exit:
        migration_sets.preflight_main(TENANT_SERVICE, ())
    assert preflight_exit.value.code == 1


def test_tenant_migration_cli_refuses_provisional_authority_before_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse() -> None:
        raise ProvisioningSpecError("tenant native verifier release authority is not frozen")

    monkeypatch.delenv("HOSTILE_ADMIN_DSN", raising=False)
    monkeypatch.delenv("HOSTILE_MIGRATOR_DSN", raising=False)
    monkeypatch.setattr(
        migration_cli,
        "require_frozen_tenant_native_verifier_authority",
        refuse,
    )
    monkeypatch.setattr(
        migration_cli,
        "load_authoritative_migration_set",
        lambda *args, **kwargs: pytest.fail("migration files were loaded"),
    )

    with pytest.raises(SystemExit) as raised:
        migration_cli.run_fixed_migration_cli(
            service=TENANT_SERVICE,
            spec=TENANT_PROVISIONING_SPEC,
            admin_dsn_environment="HOSTILE_ADMIN_DSN",
            migrator_dsn_environment="HOSTILE_MIGRATOR_DSN",
            argv=(
                "--release-identity",
                "ofarm-release/174",
                "--execution-id",
                str(_EXECUTION_ID),
            ),
        )

    assert raised.value.code == 1


def test_tenant_migration_preflight_refuses_before_loading_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse() -> None:
        raise ProvisioningSpecError("tenant native verifier release authority is not frozen")

    monkeypatch.setattr(
        provisioning_specs,
        "require_frozen_tenant_native_verifier_authority",
        refuse,
    )
    monkeypatch.setattr(
        migration_sets,
        "load_authoritative_migration_set",
        lambda *args, **kwargs: pytest.fail("migration sources were loaded"),
    )

    with pytest.raises(SystemExit) as raised:
        migration_sets.preflight_main(TENANT_SERVICE, ())

    assert raised.value.code == 1


def test_audit_entry_points_never_call_tenant_freeze_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode() -> None:
        pytest.fail("audit path called tenant native-authority gate")

    monkeypatch.setattr(
        provisioning, "require_frozen_tenant_native_verifier_authority", explode
    )
    provisioning._require_fixed_spec(SECURITY_AUDIT_PROVISIONING_SPEC)

    monkeypatch.setattr(
        readiness, "require_frozen_tenant_native_verifier_authority", explode
    )
    monkeypatch.setattr(
        readiness,
        "_verify_lane_structural_compatibility",
        lambda **kwargs: "audit-structural-report",
    )
    assert (
        readiness.verify_security_audit_structural_compatibility(
            audit_structural_dsn="audit-route"
        )
        == "audit-structural-report"
    )
