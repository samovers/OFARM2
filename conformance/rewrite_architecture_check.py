#!/usr/bin/env python3
"""Keep rewritten trust-boundary modules small and dependency-explicit."""
from __future__ import annotations

import ast
import collections.abc
import copy
import enum
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import platform
import re
import stat
import subprocess
import sys
import tokenize
import types
import typing
from collections import deque
from pathlib import Path


ROOT = Path(__file__).parent.parent
_PYTHON_SOURCE_SNAPSHOT_CONTRACT_IDENTITY = (
    "ofarm.architecture-python-source-snapshot-admission.issue176.v0.1"
)
_PYTHON_SOURCE_SNAPSHOT_INTERFACE_IDENTITY = (
    "ofarm.architecture-python-source-snapshot.v1"
)
_PYTHON_SOURCE_SNAPSHOT_RFC_RELATIVE_PATH = (
    "docs/rfcs/"
    "OFARM_Architecture_Python_Source_Snapshot_Admission_RFC_v0_1.md"
)
_PYTHON_SOURCE_SNAPSHOT_RFC_BYTE_LENGTH = 82_758
_PYTHON_SOURCE_SNAPSHOT_RFC_SHA256 = (
    "sha256:6e4307077525f2bbb48992fa4c652ab75d279875063bd715cf21dc1f1d3216d5"
)
MAX_FUNCTION_LINES = 80
MAX_TEST_LINES = 800
TEST_MODULE_BUDGETS = {
    "kernel/tests/test_profile_runtime_services.py": 1_200,
    "kernel/tests/test_security_audit_process_crash.py": 1_250,
    "kernel/tests/test_security_audit_store_loss.py": 1_700,
}
SECURITY_AUDIT_OBSERVER_ROOT_RELATIVE_PATH = (
    "deployment/postgresql/security_audit_observer_root_admission.py"
)
SECURITY_AUDIT_OBSERVER_ROOT_REFERENCE_HEAD = (
    "3fced1380c429dbe493b80358067f0d792beefed"
)
SECURITY_AUDIT_OBSERVER_ROOT_REFERENCE_AST_SHA256 = (
    "sha256:d8af95faf3cc932c96f60ac611931c35337609aca229f75e8b23d9d39b251af6"
)
SECURITY_AUDIT_OBSERVER_ROOT_MAX_LINES = 1_800
SECURITY_AUDIT_OBSERVER_ROOT_MAX_PHYSICAL_LINE_LENGTH = 120
MODULE_BUDGETS = {
    "kernel/profile_runtime_provider.py": 350,
    "kernel/provider_import_policy.py": 260,
    "kernel/profile_runtime_services.py": 295,
    "kernel/profiles/si_ffs/runtime_provider.py": 120,
    "kernel/profiles/si_ffs/manifest_inputs.py": 90,
    "kernel/authentication.py": 100,
    "kernel/auth_oidc.py": 200,
    "kernel/production_oidc.py": 450,
    "kernel/principal.py": 170,
    "kernel/principal_resolver.py": 110,
    "kernel/principal_control.py": 350,
    "kernel/signing_receipt.py": 250,
    "kernel/signing_authority.py": 250,
    "kernel/google_kms_signer.py": 120,
    "kernel/tenant_capability_issuer.py": 180,
    "kernel/key_control.py": 350,
    "kernel/tenant_uow.py": 450,
    "kernel/api.py": 120,
    "kernel/deployment_identity.py": 50,
    "kernel/runtime_config.py": 180,
    "kernel/application_runtime.py": 230,
    "kernel/legacy_m1/api.py": 370,
    "kernel/legacy_m1/runtime.py": 100,
    "kernel/security_audit.py": 130,
    "kernel/security_audit_client.py": 220,
    "kernel/authentication_audit.py": 140,
    "kernel/request_router_audit.py": 120,
    "kernel/google_kms_correlation_hmac.py": 220,
    "kernel/security_audit_hmac_posture.py": 260,
    "kernel/security_audit_health.py": 170,
    "kernel/security_audit_gap.py": 720,
    "kernel/security_audit_runtime.py": 250,
    "deployment/postgresql/security_audit_hmac_retirement.py": 450,
    "deployment/postgresql/security_audit_approval.py": 640,
    "deployment/postgresql/security_audit_break_glass.py": 1_325,
    "deployment/postgresql/security_audit_authority.py": 388,
    "deployment/postgresql/security_audit_process_crash.py": 650,
    "deployment/postgresql/security_audit_store_loss.py": 1_025,
    SECURITY_AUDIT_OBSERVER_ROOT_RELATIVE_PATH: 1_747,
}
COMMAND_MODULE_BUDGETS = {
    "deployment/postgresql/run_security_audit_hmac_retirement.py": 160,
    "deployment/postgresql/run_security_audit_process_crash.py": 260,
    "deployment/postgresql/run_security_audit_store_loss.py": 250,
}
GROUP_BUDGETS = {
    "profile runtime": (
        1_050,
        (
            "kernel/profile_runtime_provider.py",
            "kernel/provider_import_policy.py",
            "kernel/profile_runtime_services.py",
            "kernel/profiles/si_ffs/runtime_provider.py",
            "kernel/profiles/si_ffs/manifest_inputs.py",
        ),
    ),
    "OIDC verification": (
        650,
        (
            "kernel/authentication.py",
            "kernel/auth_oidc.py",
            "kernel/production_oidc.py",
        ),
    ),
    "principal authority": (
        600,
        (
            "kernel/principal.py",
            "kernel/principal_resolver.py",
            "kernel/principal_control.py",
        ),
    ),
    "capability signing": (
        1_000,
        (
            "kernel/signing_receipt.py",
            "kernel/signing_authority.py",
            "kernel/google_kms_signer.py",
            "kernel/tenant_capability_issuer.py",
            "kernel/key_control.py",
        ),
    ),
    "application runtime": (
        500,
        (
            "kernel/runtime_config.py",
            "kernel/application_runtime.py",
            "kernel/deployment_identity.py",
        ),
    ),
    "legacy M1 composition": (
        450,
        (
            "kernel/legacy_m1/api.py",
            "kernel/legacy_m1/runtime.py",
        ),
    ),
    "tenant transaction": (
        450,
        ("kernel/tenant_uow.py",),
    ),
    "security audit ingest": (
        350,
        (
            "kernel/security_audit.py",
            "kernel/security_audit_client.py",
        ),
    ),
    "authentication audit producer": (
        140,
        ("kernel/authentication_audit.py",),
    ),
    "request-router audit producer": (
        120,
        ("kernel/request_router_audit.py",),
    ),
    "security audit HMAC": (
        220,
        ("kernel/google_kms_correlation_hmac.py",),
    ),
    "security audit HMAC posture": (
        260,
        ("kernel/security_audit_hmac_posture.py",),
    ),
    "security audit health": (
        170,
        ("kernel/security_audit_health.py",),
    ),
    "security audit live gap": (
        720,
        ("kernel/security_audit_gap.py",),
    ),
    "security audit runtime": (
        250,
        ("kernel/security_audit_runtime.py",),
    ),
    "security audit HMAC retirement": (
        610,
        (
            "deployment/postgresql/security_audit_hmac_retirement.py",
            "deployment/postgresql/run_security_audit_hmac_retirement.py",
        ),
    ),
    "security audit store-loss recovery": (
        1_250,
        (
            "deployment/postgresql/security_audit_store_loss.py",
            "deployment/postgresql/run_security_audit_store_loss.py",
        ),
    ),
    "security audit process-crash reconciliation": (
        910,
        (
            "deployment/postgresql/security_audit_process_crash.py",
            "deployment/postgresql/run_security_audit_process_crash.py",
        ),
    ),
}


def _credential_expression_shape(source: str) -> str:
    expression = ast.parse(
        source,
        mode="eval",
        feature_version=(3, 12),
    )
    return ast.dump(expression.body, include_attributes=False)


class _CredentialMethodHeader(typing.NamedTuple):
    name: str
    decorators: tuple[str, ...]
    positional_arguments: tuple[tuple[str, str | None], ...]
    return_annotation: str
    body_authority: str


class _CredentialCarrierDescriptor(typing.NamedTuple):
    relative_path: str
    class_name: str
    protected_fields: tuple[str, ...]
    declarations: tuple[tuple[str, str], ...]
    methods: tuple[_CredentialMethodHeader, ...]


_CREDENTIAL_DIAGNOSTIC_CARRIERS = (
    _CredentialCarrierDescriptor(
        "kernel/runtime_config.py",
        "RuntimeConfig",
        (
            "pg_dsn",
            "tenant_readiness_pg_dsn",
            "security_audit_readiness_pg_dsn",
            "security_audit_authentication_pg_dsn",
            "security_audit_request_router_pg_dsn",
            "security_audit_control_pg_dsn",
        ),
        (
            ("mode", _credential_expression_shape("RuntimeMode")),
            ("deployment_image_digest", _credential_expression_shape("str")),
            ("oidc_issuer", _credential_expression_shape("str")),
            ("oidc_audience", _credential_expression_shape("str")),
            ("oidc_jwks_url", _credential_expression_shape("str")),
            ("pg_dsn", _credential_expression_shape("str")),
            ("tenant_readiness_pg_dsn", _credential_expression_shape("str")),
            (
                "security_audit_readiness_pg_dsn",
                _credential_expression_shape("str"),
            ),
            (
                "security_audit_authentication_pg_dsn",
                _credential_expression_shape("str"),
            ),
            (
                "security_audit_request_router_pg_dsn",
                _credential_expression_shape("str"),
            ),
            (
                "security_audit_control_pg_dsn",
                _credential_expression_shape("str"),
            ),
            (
                "correlation_hmac_kms_key_resource",
                _credential_expression_shape("str"),
            ),
            ("tenant_capability_kid", _credential_expression_shape("str")),
            (
                "signing_evidence_receipt_path",
                _credential_expression_shape("Path"),
            ),
            (
                "signing_evidence_observer_public_key",
                _credential_expression_shape("bytes"),
            ),
        ),
        (
            _CredentialMethodHeader(
                "__eq__",
                (),
                (
                    ("self", None),
                    ("other", _credential_expression_shape("object")),
                ),
                _credential_expression_shape("bool"),
                "exact-equality",
            ),
            _CredentialMethodHeader(
                "from_env",
                (_credential_expression_shape("classmethod"),),
                (("cls", None),),
                _credential_expression_shape("RuntimeConfig"),
                "opaque-deferred",
            ),
        ),
    ),
    _CredentialCarrierDescriptor(
        "deployment/postgresql/security_audit_process_crash.py",
        "ProcessCrashReconciliationSecrets",
        ("control_conninfo",),
        (("control_conninfo", _credential_expression_shape("str")),),
        (
            _CredentialMethodHeader(
                "__eq__",
                (),
                (
                    ("self", None),
                    ("other", _credential_expression_shape("object")),
                ),
                _credential_expression_shape("bool"),
                "exact-equality",
            ),
        ),
    ),
    _CredentialCarrierDescriptor(
        "deployment/postgresql/security_audit_store_loss.py",
        "StoreLossRecoverySecrets",
        ("admin_dsn", "migrator_dsn", "control_dsn", "login_passwords"),
        (
            ("admin_dsn", _credential_expression_shape("str")),
            ("migrator_dsn", _credential_expression_shape("str")),
            ("control_dsn", _credential_expression_shape("str")),
            (
                "login_passwords",
                _credential_expression_shape("tuple[tuple[str, str], ...]"),
            ),
        ),
        (
            _CredentialMethodHeader(
                "__eq__",
                (),
                (
                    ("self", None),
                    ("other", _credential_expression_shape("object")),
                ),
                _credential_expression_shape("bool"),
                "exact-equality",
            ),
        ),
    ),
    _CredentialCarrierDescriptor(
        "deployment/postgresql/security_audit_store_loss.py",
        "_Routes",
        (
            "admin_long",
            "admin_short",
            "admin_target_short",
            "migrator_long",
            "control_short",
        ),
        (
            ("admin_long", _credential_expression_shape("str")),
            ("admin_short", _credential_expression_shape("str")),
            ("admin_target_short", _credential_expression_shape("str")),
            ("migrator_long", _credential_expression_shape("str")),
            ("control_short", _credential_expression_shape("str")),
        ),
        (
            _CredentialMethodHeader(
                "__eq__",
                (),
                (
                    ("self", None),
                    ("other", _credential_expression_shape("object")),
                ),
                _credential_expression_shape("bool"),
                "exact-equality",
            ),
        ),
    ),
    _CredentialCarrierDescriptor(
        "deployment/postgresql/security_audit_store_loss.py",
        "_ValidatedInvocation",
        ("routes", "login_passwords"),
        (
            (
                "request",
                _credential_expression_shape("StoreLossRecoveryRequest"),
            ),
            ("routes", _credential_expression_shape("_Routes")),
            (
                "login_passwords",
                _credential_expression_shape("tuple[tuple[str, str], ...]"),
            ),
        ),
        (
            _CredentialMethodHeader(
                "__eq__",
                (),
                (
                    ("self", None),
                    ("other", _credential_expression_shape("object")),
                ),
                _credential_expression_shape("bool"),
                "exact-equality",
            ),
        ),
    ),
)
TEST_GLOBS = (
    "kernel/tests/*profile_runtime*.py",
    "kernel/tests/*oidc*.py",
    "kernel/tests/*principal*.py",
    "kernel/tests/*signing*.py",
    "kernel/tests/*key_control*.py",
    "kernel/tests/*application_runtime*.py",
    "kernel/tests/*runtime_config*.py",
    "kernel/tests/*tenant_uow*.py",
    "kernel/tests/*security_audit_client*.py",
    "kernel/tests/*authentication_audit*.py",
    "kernel/tests/*request_router_audit*.py",
    "kernel/tests/*google_kms_correlation_hmac*.py",
    "kernel/tests/*security_audit_hmac_posture*.py",
    "kernel/tests/*security_audit_health*.py",
    "kernel/tests/*security_audit_gap*.py",
    "kernel/tests/*security_audit_runtime*.py",
    "kernel/tests/*security_audit_hmac_retirement*.py",
    "kernel/tests/*security_audit_process_crash*.py",
    "kernel/tests/*security_audit_store_loss*.py",
)
DIRECT_IMPORT_BOUNDS = {
    "kernel/security_audit_gap.py": frozenset(
        {
            "deployment.postgresql.audit_contract",
            "kernel.security_audit",
        }
    ),
    "deployment/postgresql/security_audit_hmac_retirement.py": frozenset(
        {
            "deployment.postgresql.audit_contract",
            "kernel.security_audit_hmac_posture",
        }
    ),
    "deployment/postgresql/run_security_audit_hmac_retirement.py": frozenset(
        {"deployment.postgresql.security_audit_hmac_retirement"}
    ),
    "deployment/postgresql/security_audit_approval.py": frozenset(
        {
            "deployment.postgresql.audit_contract",
            "deployment.postgresql.security_audit_access",
        }
    ),
    "deployment/postgresql/security_audit_break_glass.py": frozenset(
        {
            "deployment.postgresql.catalog_identity",
            "deployment.postgresql.migration_sets",
            "deployment.postgresql.security_audit_approval",
            "deployment.postgresql.security_audit_export",
        }
    ),
    "deployment/postgresql/security_audit_authority.py": frozenset(),
    "deployment/postgresql/security_audit_store_loss.py": frozenset(
        {
            "deployment.postgresql.audit_contract",
            "deployment.postgresql.migration_runner",
            "deployment.postgresql.migration_sets",
            "deployment.postgresql.provisioning",
            "deployment.postgresql.provisioning_specs",
            "deployment.postgresql.version_policy",
        }
    ),
    "deployment/postgresql/run_security_audit_store_loss.py": frozenset(
        {"deployment.postgresql.security_audit_store_loss"}
    ),
    "deployment/postgresql/security_audit_process_crash.py": frozenset(
        {
            "deployment.postgresql.audit_contract",
            "deployment.postgresql.provisioning_specs",
            "deployment.postgresql.version_policy",
        }
    ),
    "deployment/postgresql/run_security_audit_process_crash.py": frozenset(
        {"deployment.postgresql.security_audit_process_crash"}
    ),
    "deployment/postgresql/security_audit_observer_root_admission.py": frozenset(),
}
SECURITY_AUDIT_GAP_FORBIDDEN_IMPORTS = frozenset(
    {
        "inspect",
        "logging",
        "pathlib",
        "prometheus_client",
        "queue",
        "socket",
        "sqlite3",
        "tempfile",
        "traceback",
    }
)
SECURITY_AUDIT_GAP_FORBIDDEN_NAMES = frozenset(
    {
        "capture_locals",
        "format_exception",
        "mark_overflow_count_unknown",
        "open",
        "print",
    }
)
SECURITY_AUDIT_APPROVAL_IMPORT_STATEMENTS = frozenset(
    {
        ("__future__", 0, (("annotations", None),)),
        (
            "base64",
            0,
            (("urlsafe_b64decode", None), ("urlsafe_b64encode", None)),
        ),
        ("binascii", 0, (("Error", "BinasciiError"),)),
        ("dataclasses", 0, (("dataclass", None),)),
        ("hashlib", 0, (("sha256", None),)),
        ("json", 0, (("dumps", None), ("loads", None))),
        ("re", 0, (("fullmatch", None),)),
        ("uuid", 0, (("UUID", None),)),
        ("cryptography.exceptions", 0, (("InvalidSignature", None),)),
        (
            "cryptography.hazmat.primitives.asymmetric.ed25519",
            0,
            (("Ed25519PublicKey", None),),
        ),
        (
            "deployment.postgresql.audit_contract",
            0,
            (
                ("EXPORT_ACCESS_PURPOSE_IDENTITY", None),
                ("EXPORT_FUNCTION_IDENTITY", None),
                ("EXPORT_MAX_BYTES", None),
                ("EXPORT_MAX_ROWS", None),
            ),
        ),
        (
            "deployment.postgresql.security_audit_access",
            0,
            (("SecurityAuditAccessCursor", None),),
        ),
    }
)
SECURITY_AUDIT_APPROVAL_FORBIDDEN_NAMES = frozenset(
    {
        "__import__",
        "eval",
        "exec",
        "compile",
        "open",
        "print",
        "input",
        "breakpoint",
        "uuid1",
        "uuid4",
        "getnode",
        "now",
        "utcnow",
        "today",
        "time",
        "time_ns",
        "monotonic",
        "perf_counter",
    }
)
SECURITY_AUDIT_AUTHORITY_IMPORT_STATEMENTS = frozenset(
    {
        ("__future__", 0, (("annotations", None),)),
        (
            "base64",
            0,
            (("urlsafe_b64decode", None), ("urlsafe_b64encode", None)),
        ),
        ("binascii", 0, (("Error", "BinasciiError"),)),
        ("dataclasses", 0, (("dataclass", None),)),
        ("hashlib", 0, (("sha256", None),)),
        ("json", 0, (("dumps", None), ("loads", None))),
        ("re", 0, (("fullmatch", None),)),
        ("typing", 0, (("Protocol", None),)),
        (
            "cryptography.hazmat.primitives.asymmetric.ed25519",
            0,
            (("Ed25519PublicKey", None),),
        ),
        ("google.cloud", 0, (("kms_v1", None),)),
    }
)
SECURITY_AUDIT_AUTHORITY_FORBIDDEN_NAMES = frozenset(
    {
        "__import__",
        "eval",
        "exec",
        "compile",
        "open",
        "print",
        "input",
        "breakpoint",
        "getenv",
        "environ",
        "system",
        "popen",
        "run",
        "sleep",
        "uuid1",
        "uuid4",
        "getnode",
        "now",
        "utcnow",
        "today",
        "time",
        "time_ns",
        "monotonic",
        "perf_counter",
        "token_bytes",
        "randbytes",
    }
)
SECURITY_AUDIT_OBSERVER_ROOT_IMPORT_STATEMENTS = frozenset(
    {
        ("__future__", 0, (("annotations", None),)),
        (
            "base64",
            0,
            (
                ("b64decode", None),
                ("b64encode", None),
                ("urlsafe_b64decode", None),
                ("urlsafe_b64encode", None),
            ),
        ),
        ("binascii", 0, (("Error", "BinasciiError"),)),
        ("collections.abc", 0, (("Mapping", None),)),
        ("dataclasses", 0, (("dataclass", None),)),
        ("datetime", 0, (("datetime", None),)),
        ("hashlib", 0, (("sha256", None),)),
        ("json", 0, (("dumps", None), ("loads", None))),
        ("re", 0, (("fullmatch", None),)),
        ("typing", 0, (("Protocol", None),)),
        (
            "cryptography.hazmat.primitives.asymmetric.ed25519",
            0,
            (("Ed25519PublicKey", None),),
        ),
        ("google.cloud", 0, (("kms_v1", None),)),
    }
)
SECURITY_AUDIT_OBSERVER_ROOT_FORBIDDEN_NAMES = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "connect",
        "create_crypto_key",
        "create_crypto_key_version",
        "create_role",
        "delete",
        "environ",
        "eval",
        "exec",
        "getenv",
        "input",
        "logging",
        "open",
        "popen",
        "print",
        "run",
        "set_iam_policy",
        "sleep",
        "socket",
        "system",
        "test_iam_permissions",
        "time",
        "time_ns",
        "token_bytes",
        "traceback",
        "update_crypto_key",
        "update_crypto_key_version",
        "update_role",
        "uuid1",
        "uuid4",
    }
)
SECURITY_AUDIT_OBSERVER_ROOT_PUBLIC_SURFACE = (
    "SecurityAuditObserverRootAdmission",
    "SecurityAuditObserverRootAdmissionRefused",
    "admit_security_audit_observer_root",
)
SECURITY_AUDIT_OBSERVER_ROOT_PROBE = (
    b"\x00OFARM2-SECURITY-AUDIT-OBSERVER-ROOT-ADMISSION-V1\x00"
)
PROHIBITED_NAMES = {"for_test", "production_eligible"}
_TENANT_UOW_MODULE = "kernel.tenant_uow"
_TENANT_UOW_PUBLIC_SURFACE = frozenset({"binding", "batch", "begin_batch"})
_TENANT_UOW_INIT_PARAMETERS = ("self", "binding", "allocate_batch")
_TENANT_UOW_SLOTS = frozenset(
    {"__binding", "__active", "__allocate_batch", "__batch"}
)
PROVIDER_IMPORT_POLICY_MODULES = (
    "kernel.profile_runtime_provider",
    "kernel.provider_import_policy",
)
LEGACY_MODULE_PREFIXES = ("kernel.legacy_m1", "kernel.profiles.si_ffs")
LEGACY_MODULES = frozenset(
    {
        "kernel.adapters",
        "kernel.auth_oidc",
        "kernel.authority",
        "kernel.config",
        "kernel.context",
        "kernel.contracts",
        "kernel.demo",
        "kernel.emission",
        "kernel.gates",
        "kernel.manifest",
        "kernel.materializer",
        "kernel.policy",
        "kernel.profile_policy",
        "kernel.runtime_activation",
        "kernel.runtime_bundle_repository",
        "kernel.schema_posture",
        "kernel.stages",
        "kernel.store",
        "kernel.sufficiency",
        "kernel.validators",
        "kernel.verification",
    }
)
PRODUCTION_COMPOSITION_MODULES = frozenset(
    {
        "kernel.api",
        "kernel.application_runtime",
        "kernel.authentication_audit",
        "kernel.google_kms_correlation_hmac",
        "kernel.google_kms_signer",
        "kernel.key_control",
        "kernel.principal",
        "kernel.principal_control",
        "kernel.principal_resolver",
        "kernel.production_oidc",
        "kernel.request_router_audit",
        "kernel.runtime_config",
        "kernel.security_audit",
        "kernel.security_audit_client",
        "kernel.security_audit_hmac_posture",
        "kernel.security_audit_health",
        "kernel.security_audit_runtime",
        "kernel.signing_authority",
        "kernel.signing_receipt",
        "kernel.tenant_capability_issuer",
        "kernel.tenant_uow",
    }
)
LEGACY_RESOURCE_NAMES = frozenset({"schema.sql"})
PROFILE_NEUTRAL_MODULES = (
    "conformance.ofarm_profile_runtime_readiness_check",
    "kernel.manifest",
    "kernel.profile_runtime_services",
    "kernel.materializer",
    "kernel.gates",
    "kernel.legacy_m1.runtime",
)
PROFILE_LOADER_MODULE = "kernel.profile_runtime_provider"
SI_SPECIFIC_NAME = re.compile(r"^SI(?![a-z])")


class PythonSourceSnapshotRefusalCodeV1(str, enum.Enum):
    CONTRACT_AUTHORITY_MISMATCH = "CONTRACT_AUTHORITY_MISMATCH"
    UNSUPPORTED_PYTHON_IMPLEMENTATION = "UNSUPPORTED_PYTHON_IMPLEMENTATION"
    UNSUPPORTED_PYTHON_VERSION = "UNSUPPORTED_PYTHON_VERSION"
    UNSUPPORTED_AST_FEATURE_VERSION = "UNSUPPORTED_AST_FEATURE_VERSION"
    UNSUPPORTED_FILESYSTEM_PROFILE = "UNSUPPORTED_FILESYSTEM_PROFILE"
    INVALID_ROOT = "INVALID_ROOT"
    SYMLINK_COMPONENT = "SYMLINK_COMPONENT"
    NON_DIRECTORY_COMPONENT = "NON_DIRECTORY_COMPONENT"
    NON_REGULAR_SOURCE = "NON_REGULAR_SOURCE"
    DUPLICATE_FILE_IDENTITY = "DUPLICATE_FILE_IDENTITY"
    EMPTY_MODULE_NAME = "EMPTY_MODULE_NAME"
    DUPLICATE_MODULE_NAME = "DUPLICATE_MODULE_NAME"
    SOURCE_ACQUISITION_FAILED = "SOURCE_ACQUISITION_FAILED"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    INVENTORY_CHANGED = "INVENTORY_CHANGED"
    INVALID_PATH_ENCODING = "INVALID_PATH_ENCODING"
    INVALID_UTF8 = "INVALID_UTF8"
    INVALID_PYTHON_SYNTAX = "INVALID_PYTHON_SYNTAX"
    MISSING_REQUIRED_IMPORT_ROOT = "MISSING_REQUIRED_IMPORT_ROOT"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    AST_COPY_LIMIT_EXCEEDED = "AST_COPY_LIMIT_EXCEEDED"
    UNSUPPORTED_REACHABILITY_ROOTS = "UNSUPPORTED_REACHABILITY_ROOTS"


class PythonSourceSnapshotRefusal(RuntimeError):
    __slots__ = ("code", "relative_path")

    def __init__(
        self,
        code: PythonSourceSnapshotRefusalCodeV1,
        relative_path: str | None = None,
    ) -> None:
        self.code = code
        self.relative_path = relative_path
        super().__init__(code.value)


class PythonSourceSnapshotDescriptorV1(typing.NamedTuple):
    interface_identity: str
    python_implementation: str
    python_version: tuple[int, int, int]
    ast_feature_version: tuple[int, int]
    filesystem_profile: str
    filesystem_encoding: str
    filesystem_errors: str
    encoding: str
    included_suffix: str
    excluded_component_exact: tuple[str, ...]
    excluded_component_prefix: str
    module_naming: str
    source_acquisition: str
    graph_semantics: str
    production_import_roots: tuple[str, ...]
    legacy_import_roots: tuple[str, ...]
    maximum_source_files: int
    maximum_source_bytes_per_file: int
    maximum_total_source_bytes: int
    maximum_root_path_bytes: int
    maximum_root_components: int
    maximum_inventory_directories: int
    maximum_inventory_entries: int
    maximum_inventory_depth: int
    maximum_relative_path_bytes: int
    maximum_ast_nodes_per_file: int
    maximum_total_ast_nodes: int
    maximum_ast_depth: int
    maximum_import_edges_per_module: int
    maximum_total_import_edges: int
    maximum_ast_copy_calls: int


class PythonSourceContractAuthorityV1(typing.NamedTuple):
    contract_identity: str
    rfc_relative_path: str
    byte_length: int
    sha256: str


class PythonSourceUnitV1(typing.NamedTuple):
    module_name: str
    relative_path: str
    source_bytes: bytes
    source_text: str
    byte_length: int
    sha256: str
    ast_node_count: int
    ast_depth: int


class PythonImportEdgeV1(typing.NamedTuple):
    line: int
    target: str


class _ImportExecutionTransitionKindV1(str, enum.Enum):
    FIXED_ROOT = "FIXED_ROOT"
    EXPLICIT_IMPORT = "EXPLICIT_RETAINED_IMPORT"
    REQUIRED_INITIALIZER = "REQUIRED_INITIALIZER"


class _ImportExecutionFailureKindV1(str, enum.Enum):
    UNRESOLVED_INTERNAL_IMPORT = "UNRESOLVED_INTERNAL_IMPORT"
    PLAIN_MODULE_PACKAGE_CONFLICT = "PLAIN_MODULE_PACKAGE_CONFLICT"
    INVALID_ABOVE_ROOT_RELATIVE = "INVALID_ABOVE_ROOT_RELATIVE"


class _ImportExecutionTransitionV1(typing.NamedTuple):
    kind: _ImportExecutionTransitionKindV1
    predecessor: str | None
    target: str
    line: int | None


_ImportExecutionPathV1: typing.TypeAlias = tuple[_ImportExecutionTransitionV1, ...]


class _ImportExecutionClosuresV1(typing.NamedTuple):
    production: collections.abc.Mapping[str, _ImportExecutionPathV1]
    legacy: collections.abc.Mapping[str, _ImportExecutionPathV1]


class _PackageTopologyV1(typing.NamedTuple):
    regular_packages: frozenset[str]
    plain_modules: frozenset[str]
    namespace_prefixes: frozenset[str]
    internal_top_levels: frozenset[str]


class _NormalizedImportV1(typing.NamedTuple):
    source_module: str
    source_relative_path: str
    line: int
    form: str
    base: str
    candidates: tuple[str, ...]
    relative: bool
    above_root: bool


class _ImportExecutionFailure(RuntimeError):
    def __init__(
        self,
        kind: _ImportExecutionFailureKindV1,
        relative_path: str,
        line: int | None,
        operand: str,
    ) -> None:
        self.kind = kind
        self.relative_path = relative_path
        self.line = line
        self.operand = operand
        location = relative_path if line is None else f"{relative_path}:{line}"
        super().__init__(f"{location}: {kind.value}: {operand!r}")


_FIXED_DESCRIPTOR_V1 = PythonSourceSnapshotDescriptorV1(
    interface_identity=_PYTHON_SOURCE_SNAPSHOT_INTERFACE_IDENTITY,
    python_implementation="CPython",
    python_version=(3, 12, 13),
    ast_feature_version=(3, 12),
    filesystem_profile="POSIX_DESCRIPTOR_RELATIVE_NOFOLLOW_STAT_NS_V1",
    filesystem_encoding="utf-8",
    filesystem_errors="surrogateescape",
    encoding="UTF-8-STRICT",
    included_suffix=".py",
    excluded_component_exact=("__pycache__",),
    excluded_component_prefix=".",
    module_naming="ROOT_RELATIVE_DOTTED_DROP_PY_AND_TERMINAL_INIT_V1",
    source_acquisition=(
        "ONE_DESCRIPTOR_BYTE_ACQUISITION_WITH_PRE_POST_INVENTORY_V1"
    ),
    graph_semantics="STATIC_AST_EXACT_KNOWN_MODULE_V1",
    production_import_roots=("kernel.api", "kernel.application_runtime"),
    legacy_import_roots=("kernel.legacy_m1.api", "kernel.legacy_m1.runtime"),
    maximum_source_files=512,
    maximum_source_bytes_per_file=524_288,
    maximum_total_source_bytes=8_388_608,
    maximum_root_path_bytes=1_024,
    maximum_root_components=64,
    maximum_inventory_directories=256,
    maximum_inventory_entries=2_048,
    maximum_inventory_depth=16,
    maximum_relative_path_bytes=256,
    maximum_ast_nodes_per_file=65_536,
    maximum_total_ast_nodes=1_048_576,
    maximum_ast_depth=64,
    maximum_import_edges_per_module=128,
    maximum_total_import_edges=4_096,
    maximum_ast_copy_calls=512,
)
_FIXED_CONTRACT_AUTHORITY_V1 = PythonSourceContractAuthorityV1(
    contract_identity=_PYTHON_SOURCE_SNAPSHOT_CONTRACT_IDENTITY,
    rfc_relative_path=_PYTHON_SOURCE_SNAPSHOT_RFC_RELATIVE_PATH,
    byte_length=_PYTHON_SOURCE_SNAPSHOT_RFC_BYTE_LENGTH,
    sha256=_PYTHON_SOURCE_SNAPSHOT_RFC_SHA256,
)


class PythonSourceSnapshotV1:
    __slots__ = (
        "_ast_copy_calls",
        "_contract_authority",
        "_content_sha256",
        "_descriptor",
        "_import_graph",
        "_legacy_reachability",
        "_modules_by_name",
        "_modules_by_relative_path",
        "_private_asts",
        "_production_reachability",
        "_root_path",
        "_builder_seal",
        "_source_file_count",
        "_total_ast_nodes",
        "_total_import_edges",
        "_total_source_bytes",
    )

    def __new__(cls) -> typing.NoReturn:
        raise TypeError("PythonSourceSnapshotV1 is built only by its builder")

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    @property
    def descriptor(self) -> PythonSourceSnapshotDescriptorV1:
        return self._descriptor

    @property
    def contract_authority(self) -> PythonSourceContractAuthorityV1:
        return self._contract_authority

    @property
    def root_path(self) -> pathlib.Path:
        return self._root_path

    @property
    def modules_by_name(
        self,
    ) -> collections.abc.Mapping[str, PythonSourceUnitV1]:
        return self._modules_by_name

    @property
    def modules_by_relative_path(
        self,
    ) -> collections.abc.Mapping[str, PythonSourceUnitV1]:
        return self._modules_by_relative_path

    @property
    def import_graph(
        self,
    ) -> collections.abc.Mapping[str, tuple[PythonImportEdgeV1, ...]]:
        return self._import_graph

    @property
    def production_reachability(
        self,
    ) -> collections.abc.Mapping[str, tuple[str, ...]]:
        return self._production_reachability

    @property
    def legacy_reachability(
        self,
    ) -> collections.abc.Mapping[str, tuple[str, ...]]:
        return self._legacy_reachability

    @property
    def source_file_count(self) -> int:
        return self._source_file_count

    @property
    def total_source_bytes(self) -> int:
        return self._total_source_bytes

    @property
    def total_ast_nodes(self) -> int:
        return self._total_ast_nodes

    @property
    def total_import_edges(self) -> int:
        return self._total_import_edges

    @property
    def content_sha256(self) -> str:
        return self._content_sha256

    def ast_for(self, module_name: str) -> ast.Module:
        if not _is_builder_snapshot(self):
            raise TypeError("snapshot must be builder-sealed")
        if type(module_name) is not str:
            raise TypeError("module_name must be str")
        tree = self._private_asts.get(module_name)
        if tree is None:
            raise KeyError(module_name)
        if self._ast_copy_calls >= self.descriptor.maximum_ast_copy_calls:
            raise PythonSourceSnapshotRefusal(
                PythonSourceSnapshotRefusalCodeV1.AST_COPY_LIMIT_EXCEEDED,
            )
        try:
            copied = copy.deepcopy(tree)
        except (MemoryError, RecursionError) as exc:
            raise PythonSourceSnapshotRefusal(
                PythonSourceSnapshotRefusalCodeV1.RESOURCE_LIMIT_EXCEEDED,
                self.modules_by_name[module_name].relative_path,
            ) from exc
        object.__setattr__(self, "_ast_copy_calls", self._ast_copy_calls + 1)
        return copied

    def _comparison_value(self) -> tuple[object, ...]:
        return (
            self.descriptor,
            self.contract_authority,
            self.root_path,
            dict(self.modules_by_name),
            dict(self.modules_by_relative_path),
            dict(self.import_graph),
            dict(self.production_reachability),
            dict(self.legacy_reachability),
            self.source_file_count,
            self.total_source_bytes,
            self.total_ast_nodes,
            self.total_import_edges,
            self.content_sha256,
        )

    def __eq__(self, other: object) -> bool:
        if type(other) is not PythonSourceSnapshotV1:
            return NotImplemented
        return self._comparison_value() == other._comparison_value()

    __hash__ = None


_CandidateV1: typing.TypeAlias = tuple[
    str,
    bytes,
    int,
    int,
    int,
    int,
    int,
    int,
]


def _refuse(
    code: PythonSourceSnapshotRefusalCodeV1,
    relative_path: str | None = None,
) -> typing.NoReturn:
    raise PythonSourceSnapshotRefusal(code, relative_path)


def _fixed_bootstrap_profile_preflight() -> None:
    required_callables = (
        "close",
        "fstat",
        "open",
        "read",
        "scandir",
        "stat",
    )
    required_flags = ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW", "O_RDONLY")
    if any(not callable(getattr(os, name, None)) for name in required_callables):
        _refuse(
            PythonSourceSnapshotRefusalCodeV1.UNSUPPORTED_FILESYSTEM_PROFILE,
        )
    if any(not hasattr(os, name) for name in required_flags):
        _refuse(
            PythonSourceSnapshotRefusalCodeV1.UNSUPPORTED_FILESYSTEM_PROFILE,
        )
    if (
        os.open not in os.supports_dir_fd
        or os.stat not in os.supports_dir_fd
        or os.stat not in os.supports_follow_symlinks
        or os.scandir not in os.supports_fd
    ):
        _refuse(
            PythonSourceSnapshotRefusalCodeV1.UNSUPPORTED_FILESYSTEM_PROFILE,
        )


def _directory_open_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW


def _file_open_flags() -> int:
    return os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW


def _stat_identity(value: os.stat_result) -> tuple[int, int, int]:
    return (value.st_dev, value.st_ino, value.st_mode)


def _source_fingerprint(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _absolute_path_components(
    root: pathlib.Path,
    *,
    authority_path: bool,
) -> tuple[bytes, ...]:
    invalid_code = (
        PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH
        if authority_path
        else PythonSourceSnapshotRefusalCodeV1.INVALID_ROOT
    )
    limit_code = (
        PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH
        if authority_path
        else PythonSourceSnapshotRefusalCodeV1.RESOURCE_LIMIT_EXCEEDED
    )
    encoding_code = (
        PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH
        if authority_path
        else PythonSourceSnapshotRefusalCodeV1.INVALID_PATH_ENCODING
    )
    if not isinstance(root, pathlib.Path) or not root.is_absolute():
        _refuse(invalid_code)
    lexical = os.fspath(root)
    if type(lexical) is not str:
        _refuse(invalid_code)
    if len(lexical) > _FIXED_DESCRIPTOR_V1.maximum_root_path_bytes:
        _refuse(limit_code)
    try:
        raw = os.fsencode(lexical)
        if len(raw) > _FIXED_DESCRIPTOR_V1.maximum_root_path_bytes:
            _refuse(limit_code)
        decoded = raw.decode("utf-8", errors="strict")
    except (UnicodeDecodeError, UnicodeEncodeError):
        _refuse(encoding_code)
    if decoded != lexical or os.fsencode(decoded) != raw:
        _refuse(encoding_code)
    parts = root.parts
    if not parts or parts[0] != os.sep:
        _refuse(invalid_code)
    components = parts[1:]
    if len(components) > _FIXED_DESCRIPTOR_V1.maximum_root_components:
        _refuse(limit_code)
    if any(part in {"", ".", ".."} for part in components):
        _refuse(invalid_code)
    return tuple(part.encode("utf-8") for part in components)


def _open_absolute_directory(
    root: pathlib.Path,
    *,
    authority_path: bool,
) -> int:
    components = _absolute_path_components(root, authority_path=authority_path)
    generic_code = (
        PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH
        if authority_path
        else PythonSourceSnapshotRefusalCodeV1.INVALID_ROOT
    )
    current_fd = -1
    try:
        current_fd = os.open(os.sep, _directory_open_flags())
        for index, component in enumerate(components):
            final = index == len(components) - 1
            next_fd = -1
            try:
                before = os.stat(
                    component,
                    dir_fd=current_fd,
                    follow_symlinks=False,
                )
            except OSError:
                _refuse(generic_code)
            if stat.S_ISLNK(before.st_mode):
                _refuse(
                    PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH
                    if authority_path
                    else PythonSourceSnapshotRefusalCodeV1.SYMLINK_COMPONENT,
                )
            if not stat.S_ISDIR(before.st_mode):
                if authority_path:
                    _refuse(
                        PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH,
                    )
                _refuse(
                    PythonSourceSnapshotRefusalCodeV1.INVALID_ROOT
                    if final
                    else PythonSourceSnapshotRefusalCodeV1.NON_DIRECTORY_COMPONENT,
                )
            try:
                next_fd = os.open(
                    component,
                    _directory_open_flags(),
                    dir_fd=current_fd,
                )
                after = os.fstat(next_fd)
            except OSError:
                if next_fd >= 0:
                    os.close(next_fd)
                _refuse(generic_code)
            if _stat_identity(before) != _stat_identity(after):
                os.close(next_fd)
                _refuse(generic_code)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        if current_fd >= 0:
            os.close(current_fd)
        raise


def _read_descriptor_once(fd: int, maximum_bytes: int) -> bytes:
    retained = bytearray()
    while True:
        chunk = os.read(fd, min(65_536, maximum_bytes + 1 - len(retained)))
        if not chunk:
            return bytes(retained)
        retained.extend(chunk)
        if len(retained) > maximum_bytes:
            return bytes(retained)


def _authenticate_complete_contract() -> None:
    package_fd = -1
    file_fd = -1
    try:
        package_fd = _open_absolute_directory(ROOT, authority_path=True)
        components = tuple(
            part.encode("utf-8")
            for part in _PYTHON_SOURCE_SNAPSHOT_RFC_RELATIVE_PATH.split("/")
        )
        current_fd = package_fd
        owned_current = False
        for component in components[:-1]:
            next_fd = -1
            try:
                before = os.stat(
                    component,
                    dir_fd=current_fd,
                    follow_symlinks=False,
                )
                if not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(
                    before.st_mode
                ):
                    _refuse(
                        PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH,
                    )
                next_fd = os.open(
                    component,
                    _directory_open_flags(),
                    dir_fd=current_fd,
                )
                after = os.fstat(next_fd)
            except OSError:
                if next_fd >= 0:
                    os.close(next_fd)
                _refuse(
                    PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH,
                )
            if _stat_identity(before) != _stat_identity(after):
                os.close(next_fd)
                _refuse(
                    PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH,
                )
            if owned_current:
                os.close(current_fd)
            current_fd = next_fd
            owned_current = True
        target = components[-1]
        try:
            before = os.stat(
                target,
                dir_fd=current_fd,
                follow_symlinks=False,
            )
            if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
                _refuse(
                    PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH,
                )
            file_fd = os.open(target, _file_open_flags(), dir_fd=current_fd)
            opened = os.fstat(file_fd)
            authority_bytes = _read_descriptor_once(
                file_fd,
                _PYTHON_SOURCE_SNAPSHOT_RFC_BYTE_LENGTH,
            )
            after = os.fstat(file_fd)
        except OSError:
            _refuse(
                PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH,
            )
        finally:
            if owned_current:
                os.close(current_fd)
        if not (
            _source_fingerprint(before)
            == _source_fingerprint(opened)
            == _source_fingerprint(after)
        ):
            _refuse(
                PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH,
            )
        digest = f"sha256:{hashlib.sha256(authority_bytes).hexdigest()}"
        if (
            len(authority_bytes) != _PYTHON_SOURCE_SNAPSHOT_RFC_BYTE_LENGTH
            or digest != _PYTHON_SOURCE_SNAPSHOT_RFC_SHA256
        ):
            _refuse(
                PythonSourceSnapshotRefusalCodeV1.CONTRACT_AUTHORITY_MISMATCH,
            )
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if package_fd >= 0:
            os.close(package_fd)


def _runtime_ast_feature_version() -> tuple[int, int]:
    return (3, 12)


def _authenticate_full_execution_profile() -> None:
    if platform.python_implementation() != _FIXED_DESCRIPTOR_V1.python_implementation:
        _refuse(
            PythonSourceSnapshotRefusalCodeV1.UNSUPPORTED_PYTHON_IMPLEMENTATION,
        )
    if tuple(sys.version_info[:3]) != _FIXED_DESCRIPTOR_V1.python_version:
        _refuse(PythonSourceSnapshotRefusalCodeV1.UNSUPPORTED_PYTHON_VERSION)
    if _runtime_ast_feature_version() != _FIXED_DESCRIPTOR_V1.ast_feature_version:
        _refuse(PythonSourceSnapshotRefusalCodeV1.UNSUPPORTED_AST_FEATURE_VERSION)
    if (
        os.name != "posix"
        or sys.getfilesystemencoding() != _FIXED_DESCRIPTOR_V1.filesystem_encoding
        or sys.getfilesystemencodeerrors() != _FIXED_DESCRIPTOR_V1.filesystem_errors
        or any(
            not hasattr(os.stat_result, field)
            for field in (
                "st_dev",
                "st_ino",
                "st_mode",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
            )
        )
    ):
        _refuse(
            PythonSourceSnapshotRefusalCodeV1.UNSUPPORTED_FILESYSTEM_PROFILE,
        )
    _fixed_bootstrap_profile_preflight()


def _validated_relative_name(
    name: str,
    parent_raw: bytes,
    depth: int,
) -> tuple[bytes, str]:
    try:
        raw_name = os.fsencode(name)
        decoded_name = raw_name.decode("utf-8", errors="strict")
    except (UnicodeDecodeError, UnicodeEncodeError):
        _refuse(PythonSourceSnapshotRefusalCodeV1.INVALID_PATH_ENCODING)
    if (
        decoded_name != name
        or os.fsencode(decoded_name) != raw_name
        or b"/" in raw_name
        or not raw_name
    ):
        _refuse(PythonSourceSnapshotRefusalCodeV1.INVALID_PATH_ENCODING)
    raw_relative = raw_name if not parent_raw else parent_raw + b"/" + raw_name
    if (
        len(raw_relative) > _FIXED_DESCRIPTOR_V1.maximum_relative_path_bytes
        or depth > _FIXED_DESCRIPTOR_V1.maximum_inventory_depth
    ):
        _refuse(PythonSourceSnapshotRefusalCodeV1.RESOURCE_LIMIT_EXCEEDED)
    try:
        relative = raw_relative.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        _refuse(PythonSourceSnapshotRefusalCodeV1.INVALID_PATH_ENCODING)
    return raw_relative, relative


def _open_inventory_directory(
    root_fd: int,
    components: tuple[bytes, ...],
    expected_identity: tuple[int, int, int] | None,
) -> tuple[int, bool]:
    if not components:
        return root_fd, False
    current_fd = root_fd
    owned = False
    try:
        for component in components:
            next_fd = -1
            try:
                before = os.stat(
                    component,
                    dir_fd=current_fd,
                    follow_symlinks=False,
                )
            except OSError:
                _refuse(PythonSourceSnapshotRefusalCodeV1.INVENTORY_CHANGED)
            if stat.S_ISLNK(before.st_mode):
                _refuse(PythonSourceSnapshotRefusalCodeV1.SYMLINK_COMPONENT)
            if not stat.S_ISDIR(before.st_mode):
                _refuse(
                    PythonSourceSnapshotRefusalCodeV1.NON_DIRECTORY_COMPONENT,
                )
            try:
                next_fd = os.open(
                    component,
                    _directory_open_flags(),
                    dir_fd=current_fd,
                )
                opened = os.fstat(next_fd)
            except OSError:
                if next_fd >= 0:
                    os.close(next_fd)
                _refuse(PythonSourceSnapshotRefusalCodeV1.INVENTORY_CHANGED)
            if _stat_identity(before) != _stat_identity(opened):
                os.close(next_fd)
                _refuse(PythonSourceSnapshotRefusalCodeV1.INVENTORY_CHANGED)
            if owned:
                os.close(current_fd)
            current_fd = next_fd
            owned = True
        if expected_identity is not None and _stat_identity(
            os.fstat(current_fd)
        ) != expected_identity:
            _refuse(PythonSourceSnapshotRefusalCodeV1.INVENTORY_CHANGED)
        return current_fd, True
    except BaseException:
        if owned:
            os.close(current_fd)
        raise


def _bounded_inventory(root_fd: int) -> tuple[_CandidateV1, ...]:
    root_identity = _stat_identity(os.fstat(root_fd))
    queue: list[
        tuple[bytes, tuple[bytes, ...], tuple[int, int, int] | None]
    ] = [(b"", (), root_identity)]
    candidates: list[_CandidateV1] = []
    file_identities: set[tuple[int, int]] = set()
    directory_count = 1
    entry_count = 0
    declared_total = 0
    while queue:
        queue.sort(key=lambda value: value[0], reverse=True)
        parent_raw, components, expected_identity = queue.pop()
        current_fd, owned = _open_inventory_directory(
            root_fd,
            components,
            expected_identity,
        )
        try:
            batch: list[tuple[bytes, str, bytes, str]] = []
            try:
                with os.scandir(current_fd) as entries:
                    for entry in entries:
                        entry_count += 1
                        if entry_count > _FIXED_DESCRIPTOR_V1.maximum_inventory_entries:
                            _refuse(
                                PythonSourceSnapshotRefusalCodeV1
                                .RESOURCE_LIMIT_EXCEEDED,
                            )
                        raw_relative, relative = _validated_relative_name(
                            entry.name,
                            parent_raw,
                            len(components) + 1,
                        )
                        batch.append(
                            (
                                os.fsencode(entry.name),
                                entry.name,
                                raw_relative,
                                relative,
                            )
                        )
            except OSError:
                _refuse(PythonSourceSnapshotRefusalCodeV1.INVENTORY_CHANGED)
            batch.sort(key=lambda value: value[0])
            for raw_name, name, raw_relative, relative in batch:
                if (
                    name in _FIXED_DESCRIPTOR_V1.excluded_component_exact
                    or name.startswith(
                        _FIXED_DESCRIPTOR_V1.excluded_component_prefix
                    )
                ):
                    continue
                try:
                    metadata = os.stat(
                        raw_name,
                        dir_fd=current_fd,
                        follow_symlinks=False,
                    )
                except OSError:
                    _refuse(
                        PythonSourceSnapshotRefusalCodeV1.INVENTORY_CHANGED,
                        relative,
                    )
                if stat.S_ISLNK(metadata.st_mode):
                    _refuse(
                        PythonSourceSnapshotRefusalCodeV1.SYMLINK_COMPONENT,
                        relative,
                    )
                if stat.S_ISDIR(metadata.st_mode):
                    directory_count += 1
                    if (
                        directory_count
                        > _FIXED_DESCRIPTOR_V1.maximum_inventory_directories
                    ):
                        _refuse(
                            PythonSourceSnapshotRefusalCodeV1.RESOURCE_LIMIT_EXCEEDED,
                            relative,
                        )
                    queue.append(
                        (
                            raw_relative,
                            (*components, raw_name),
                            _stat_identity(metadata),
                        )
                    )
                    continue
                if not name.endswith(_FIXED_DESCRIPTOR_V1.included_suffix):
                    continue
                if not stat.S_ISREG(metadata.st_mode):
                    _refuse(
                        PythonSourceSnapshotRefusalCodeV1.NON_REGULAR_SOURCE,
                        relative,
                    )
                identity = (metadata.st_dev, metadata.st_ino)
                if identity in file_identities:
                    _refuse(
                        PythonSourceSnapshotRefusalCodeV1.DUPLICATE_FILE_IDENTITY,
                        relative,
                    )
                file_identities.add(identity)
                if (
                    type(metadata.st_size) is not int
                    or metadata.st_size < 0
                    or metadata.st_size
                    > _FIXED_DESCRIPTOR_V1.maximum_source_bytes_per_file
                ):
                    _refuse(
                        PythonSourceSnapshotRefusalCodeV1.RESOURCE_LIMIT_EXCEEDED,
                        relative,
                    )
                declared_total += metadata.st_size
                if (
                    len(candidates) + 1
                    > _FIXED_DESCRIPTOR_V1.maximum_source_files
                    or declared_total
                    > _FIXED_DESCRIPTOR_V1.maximum_total_source_bytes
                ):
                    _refuse(
                        PythonSourceSnapshotRefusalCodeV1.RESOURCE_LIMIT_EXCEEDED,
                        relative,
                    )
                candidates.append(
                    (
                        relative,
                        raw_relative,
                        metadata.st_dev,
                        metadata.st_ino,
                        metadata.st_mode,
                        metadata.st_size,
                        metadata.st_mtime_ns,
                        metadata.st_ctime_ns,
                    )
                )
        finally:
            if owned:
                os.close(current_fd)
    candidates.sort(key=lambda value: value[1])
    return tuple(candidates)


def _candidate_source_fingerprint(candidate: _CandidateV1) -> tuple[int, ...]:
    return candidate[2:]


def _acquire_source(root_fd: int, candidate: _CandidateV1) -> bytes:
    relative, raw_relative = candidate[:2]
    components = tuple(raw_relative.split(b"/"))
    parent_fd = root_fd
    owned_parent = False
    file_fd = -1
    try:
        if len(components) > 1:
            try:
                parent_fd, owned_parent = _open_inventory_directory(
                    root_fd,
                    components[:-1],
                    None,
                )
            except PythonSourceSnapshotRefusal as exc:
                if exc.code in {
                    PythonSourceSnapshotRefusalCodeV1.INVENTORY_CHANGED,
                    PythonSourceSnapshotRefusalCodeV1.NON_DIRECTORY_COMPONENT,
                    PythonSourceSnapshotRefusalCodeV1.SYMLINK_COMPONENT,
                }:
                    raise PythonSourceSnapshotRefusal(
                        PythonSourceSnapshotRefusalCodeV1.INVENTORY_CHANGED,
                        relative,
                    ) from exc
                raise
        leaf = components[-1]
        try:
            before = os.stat(
                leaf,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError as exc:
            raise PythonSourceSnapshotRefusal(
                PythonSourceSnapshotRefusalCodeV1.INVENTORY_CHANGED,
                relative,
            ) from exc
        except OSError as exc:
            raise PythonSourceSnapshotRefusal(
                PythonSourceSnapshotRefusalCodeV1.SOURCE_ACQUISITION_FAILED,
                relative,
            ) from exc
        expected = _candidate_source_fingerprint(candidate)
        if _source_fingerprint(before) != expected:
            _refuse(PythonSourceSnapshotRefusalCodeV1.SOURCE_CHANGED, relative)
        try:
            file_fd = os.open(leaf, _file_open_flags(), dir_fd=parent_fd)
            opened = os.fstat(file_fd)
        except OSError as exc:
            try:
                observed = os.stat(
                    leaf,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                raise PythonSourceSnapshotRefusal(
                    PythonSourceSnapshotRefusalCodeV1.INVENTORY_CHANGED,
                    relative,
                ) from exc
            except OSError:
                raise PythonSourceSnapshotRefusal(
                    PythonSourceSnapshotRefusalCodeV1.SOURCE_ACQUISITION_FAILED,
                    relative,
                ) from exc
            if _source_fingerprint(observed) != expected:
                raise PythonSourceSnapshotRefusal(
                    PythonSourceSnapshotRefusalCodeV1.SOURCE_CHANGED,
                    relative,
                ) from exc
            raise PythonSourceSnapshotRefusal(
                PythonSourceSnapshotRefusalCodeV1.SOURCE_ACQUISITION_FAILED,
                relative,
            ) from exc
        if _source_fingerprint(opened) != expected:
            _refuse(PythonSourceSnapshotRefusalCodeV1.SOURCE_CHANGED, relative)
        try:
            retained = _read_descriptor_once(file_fd, candidate[5])
            after = os.fstat(file_fd)
        except OSError as exc:
            raise PythonSourceSnapshotRefusal(
                PythonSourceSnapshotRefusalCodeV1.SOURCE_ACQUISITION_FAILED,
                relative,
            ) from exc
        if (
            len(retained) != candidate[5]
            or _source_fingerprint(after) != expected
        ):
            _refuse(PythonSourceSnapshotRefusalCodeV1.SOURCE_CHANGED, relative)
        return retained
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if owned_parent:
            os.close(parent_fd)


def _module_name(relative_path: str) -> str:
    parts = relative_path.removesuffix(".py").split("/")
    if parts[-1] == "__init__":
        parts.pop()
    if not parts:
        _refuse(
            PythonSourceSnapshotRefusalCodeV1.EMPTY_MODULE_NAME,
            relative_path,
        )
    return ".".join(parts)


def _ast_measurements(tree: ast.Module) -> tuple[int, int]:
    count = 0
    maximum_depth = 0
    pending: list[tuple[ast.AST, int]] = [(tree, 1)]
    while pending:
        node, depth = pending.pop()
        count += 1
        maximum_depth = max(maximum_depth, depth)
        if (
            count > _FIXED_DESCRIPTOR_V1.maximum_ast_nodes_per_file
            or maximum_depth > _FIXED_DESCRIPTOR_V1.maximum_ast_depth
        ):
            _refuse(PythonSourceSnapshotRefusalCodeV1.RESOURCE_LIMIT_EXCEEDED)
        pending.extend(
            (child, depth + 1) for child in ast.iter_child_nodes(node)
        )
    return count, maximum_depth


def _from_import_base(
    module: str,
    relative_path: str,
    node: ast.ImportFrom,
) -> str:
    if node.level == 0:
        return node.module or ""
    package = module.split(".")
    if not relative_path.endswith("/__init__.py") and relative_path != "__init__.py":
        package.pop()
    keep = len(package) - node.level + 1
    base = [] if keep < 0 else package[:keep]
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def _import_edges(
    module: str,
    relative_path: str,
    tree: ast.Module,
    known_modules: set[str],
) -> tuple[PythonImportEdgeV1, ...]:
    edges: set[PythonImportEdgeV1] = set()

    def add_edge(edge: PythonImportEdgeV1) -> None:
        edges.add(edge)
        if len(edges) > _FIXED_DESCRIPTOR_V1.maximum_import_edges_per_module:
            _refuse(
                PythonSourceSnapshotRefusalCodeV1.RESOURCE_LIMIT_EXCEEDED,
                relative_path,
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in known_modules:
                    add_edge(PythonImportEdgeV1(node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            base = _from_import_base(module, relative_path, node)
            if base in known_modules:
                add_edge(PythonImportEdgeV1(node.lineno, base))
            for alias in node.names:
                candidate = f"{base}.{alias.name}" if base else alias.name
                if candidate in known_modules:
                    add_edge(PythonImportEdgeV1(node.lineno, candidate))
    return tuple(sorted(edges, key=lambda edge: (edge.line, edge.target)))


def _derive_reachability(
    graph: collections.abc.Mapping[str, tuple[PythonImportEdgeV1, ...]],
    roots: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    paths: dict[str, tuple[str, ...]] = {}
    pending: deque[str] = deque()
    for root in roots:
        paths[root] = (root,)
        pending.append(root)
    while pending:
        module = pending.popleft()
        for edge in graph[module]:
            if edge.target not in paths:
                paths[edge.target] = (*paths[module], edge.target)
                pending.append(edge.target)
    return paths


def _proper_module_prefixes(module: str) -> tuple[str, ...]:
    components = module.split(".")
    return tuple(".".join(components[:length]) for length in range(1, len(components)))


def _package_topology(snapshot: PythonSourceSnapshotV1) -> _PackageTopologyV1:
    modules = frozenset(snapshot.modules_by_name)
    regular_packages = frozenset(
        module
        for module, unit in snapshot.modules_by_name.items()
        if unit.relative_path == f"{module.replace('.', '/')}/__init__.py"
    )
    prefixes = frozenset(
        prefix for module in modules for prefix in _proper_module_prefixes(module)
    )
    return _PackageTopologyV1(
        regular_packages=regular_packages,
        plain_modules=modules - regular_packages,
        namespace_prefixes=prefixes - modules,
        internal_top_levels=frozenset(module.partition(".")[0] for module in modules),
    )


def _relative_import_is_above_root(
    module: str,
    relative_path: str,
    node: ast.ImportFrom,
) -> bool:
    if node.level == 0:
        return False
    package_depth = len(module.split("."))
    if not relative_path.endswith("/__init__.py"):
        package_depth -= 1
    return node.level > package_depth


def _normalized_imports(
    module: str,
    relative_path: str,
    tree: ast.Module,
) -> tuple[_NormalizedImportV1, ...]:
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(
                _NormalizedImportV1(
                    source_module=module,
                    source_relative_path=relative_path,
                    line=node.lineno,
                    form="IMPORT",
                    base=alias.name,
                    candidates=(),
                    relative=False,
                    above_root=False,
                )
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            base = _from_import_base(module, relative_path, node)
            imports.append(
                _NormalizedImportV1(
                    source_module=module,
                    source_relative_path=relative_path,
                    line=node.lineno,
                    form="FROM",
                    base=base,
                    candidates=tuple(
                        sorted(
                            f"{base}.{alias.name}" if base else alias.name
                            for alias in node.names
                            if alias.name != "*"
                        )
                    ),
                    relative=node.level > 0,
                    above_root=_relative_import_is_above_root(
                        module,
                        relative_path,
                        node,
                    ),
                )
            )
    return tuple(
        sorted(
            imports,
            key=lambda value: (
                value.line,
                value.form,
                value.base,
                value.candidates,
            ),
        )
    )


def _target_kind(
    target: str,
    *,
    relative: bool,
    topology: _PackageTopologyV1,
) -> str:
    if not relative and target.partition(".")[0] not in topology.internal_top_levels:
        return "external"
    if target in topology.regular_packages:
        return "regular"
    if target in topology.plain_modules:
        return "plain"
    if target in topology.namespace_prefixes:
        return "namespace"
    return "missing"


def _raise_unresolved_target(
    target: str,
    topology: _PackageTopologyV1,
    relative_path: str,
    line: int,
) -> typing.NoReturn:
    plain_ancestor = next(
        (
            prefix
            for prefix in _proper_module_prefixes(target)
            if prefix in topology.plain_modules
        ),
        None,
    )
    if plain_ancestor is not None:
        raise _ImportExecutionFailure(
            _ImportExecutionFailureKindV1.PLAIN_MODULE_PACKAGE_CONFLICT,
            relative_path,
            line,
            f"{target} via {plain_ancestor}",
        )
    raise _ImportExecutionFailure(
        _ImportExecutionFailureKindV1.UNRESOLVED_INTERNAL_IMPORT,
        relative_path,
        line,
        target,
    )


def _required_initializers(
    target: str,
    topology: _PackageTopologyV1,
    relative_path: str,
    line: int | None,
) -> tuple[str, ...]:
    required = []
    for prefix in _proper_module_prefixes(target):
        if prefix in topology.plain_modules:
            raise _ImportExecutionFailure(
                _ImportExecutionFailureKindV1.PLAIN_MODULE_PACKAGE_CONFLICT,
                relative_path,
                line,
                f"{target} via {prefix}",
            )
        if prefix in topology.regular_packages:
            required.append(prefix)
    return tuple(required)


def _namespace_initializer_requirements(
    record: _NormalizedImportV1,
    topology: _PackageTopologyV1,
) -> tuple[str, ...]:
    if record.above_root:
        raise _ImportExecutionFailure(
            _ImportExecutionFailureKindV1.INVALID_ABOVE_ROOT_RELATIVE,
            record.source_relative_path,
            record.line,
            record.base,
        )
    base_kind = _target_kind(
        record.base,
        relative=record.relative,
        topology=topology,
    )
    if base_kind == "external":
        return ()
    if base_kind == "missing":
        _raise_unresolved_target(
            record.base,
            topology,
            record.source_relative_path,
            record.line,
        )
    base_initializers = _required_initializers(
        record.base,
        topology,
        record.source_relative_path,
        record.line,
    )
    required = list(base_initializers if base_kind == "namespace" else ())
    if record.form == "IMPORT":
        return tuple(required)
    for target in record.candidates:
        candidate_kind = _target_kind(
            target,
            relative=record.relative,
            topology=topology,
        )
        if candidate_kind == "missing":
            if base_kind in {"plain", "regular"}:
                continue
            _raise_unresolved_target(
                target,
                topology,
                record.source_relative_path,
                record.line,
            )
        candidate_initializers = _required_initializers(
            target,
            topology,
            record.source_relative_path,
            record.line,
        )
        if candidate_kind == "namespace":
            required.extend(candidate_initializers)
    return tuple(dict.fromkeys(required))


def _path_failure_location(
    snapshot: PythonSourceSnapshotV1,
    path: _ImportExecutionPathV1,
) -> tuple[str, int | None]:
    transition = path[-1]
    if (
        transition.kind is _ImportExecutionTransitionKindV1.EXPLICIT_IMPORT
        and transition.predecessor is not None
    ):
        return (
            snapshot.modules_by_name[transition.predecessor].relative_path,
            transition.line,
        )
    return snapshot.modules_by_name[transition.target].relative_path, None


def _enqueue_initializers(
    requiring_module: str,
    required: tuple[str, ...],
    paths: dict[str, _ImportExecutionPathV1],
    pending: deque[str],
) -> None:
    for initializer in required:
        if initializer in paths:
            continue
        transition = _ImportExecutionTransitionV1(
            _ImportExecutionTransitionKindV1.REQUIRED_INITIALIZER,
            requiring_module,
            initializer,
            None,
        )
        paths[initializer] = (*paths[requiring_module], transition)
        pending.append(initializer)


def _derive_import_execution_closure(
    snapshot: PythonSourceSnapshotV1,
    normalized: collections.abc.Mapping[str, tuple[_NormalizedImportV1, ...]],
    topology: _PackageTopologyV1,
    roots: tuple[str, ...],
) -> collections.abc.Mapping[str, _ImportExecutionPathV1]:
    paths: dict[str, _ImportExecutionPathV1] = {}
    pending: deque[str] = deque()
    for root in roots:
        paths[root] = (
            _ImportExecutionTransitionV1(
                _ImportExecutionTransitionKindV1.FIXED_ROOT,
                None,
                root,
                None,
            ),
        )
        pending.append(root)
    while pending:
        module = pending.popleft()
        relative_path, line = _path_failure_location(snapshot, paths[module])
        _enqueue_initializers(
            module,
            _required_initializers(
                module,
                topology,
                relative_path,
                line,
            ),
            paths,
            pending,
        )
        for record in normalized[module]:
            _enqueue_initializers(
                module,
                _namespace_initializer_requirements(
                    record,
                    topology,
                ),
                paths,
                pending,
            )
        for edge in snapshot.import_graph[module]:
            if edge.target in paths:
                continue
            transition = _ImportExecutionTransitionV1(
                _ImportExecutionTransitionKindV1.EXPLICIT_IMPORT,
                module,
                edge.target,
                edge.line,
            )
            paths[edge.target] = (*paths[module], transition)
            pending.append(edge.target)
    return types.MappingProxyType(dict(paths))


def _derive_import_execution_closures(
    snapshot: PythonSourceSnapshotV1,
    trees: collections.abc.Mapping[str, ast.Module],
) -> _ImportExecutionClosuresV1:
    if not _is_builder_snapshot(snapshot):
        raise TypeError("snapshot must be builder-sealed")
    if set(trees) != set(snapshot.modules_by_name) or any(
        type(tree) is not ast.Module for tree in trees.values()
    ):
        raise TypeError("trees must be the complete detached AST mapping")
    topology = _package_topology(snapshot)
    normalized = types.MappingProxyType(
        {
            module: _normalized_imports(
                module,
                snapshot.modules_by_name[module].relative_path,
                trees[module],
            )
            for module in sorted(trees)
        }
    )
    descriptor = snapshot.descriptor
    return _ImportExecutionClosuresV1(
        production=_derive_import_execution_closure(
            snapshot,
            normalized,
            topology,
            descriptor.production_import_roots,
        ),
        legacy=_derive_import_execution_closure(
            snapshot,
            normalized,
            topology,
            descriptor.legacy_import_roots,
        ),
    )


def _content_digest(
    modules: dict[str, PythonSourceUnitV1],
    graph: dict[str, tuple[PythonImportEdgeV1, ...]],
    production: dict[str, tuple[str, ...]],
    legacy: dict[str, tuple[str, ...]],
    total_source_bytes: int,
    total_ast_nodes: int,
    total_import_edges: int,
) -> str:
    authority = _FIXED_CONTRACT_AUTHORITY_V1
    manifest = {
        "contractAuthority": {
            "byteLength": authority.byte_length,
            "contractIdentity": authority.contract_identity,
            "rfcRelativePath": authority.rfc_relative_path,
            "sha256": authority.sha256,
        },
        "descriptor": _FIXED_DESCRIPTOR_V1._asdict(),
        "modules": [
            {
                "astDepth": unit.ast_depth,
                "astNodeCount": unit.ast_node_count,
                "byteLength": unit.byte_length,
                "moduleName": unit.module_name,
                "relativePath": unit.relative_path,
                "sha256": unit.sha256,
            }
            for _, unit in sorted(modules.items())
        ],
        "importGraph": [
            {
                "moduleName": module,
                "edges": [
                    {"line": edge.line, "target": edge.target}
                    for edge in edges
                ],
            }
            for module, edges in sorted(graph.items())
        ],
        "productionReachability": [
            {"moduleName": module, "path": list(path)}
            for module, path in sorted(production.items())
        ],
        "legacyReachability": [
            {"moduleName": module, "path": list(path)}
            for module, path in sorted(legacy.items())
        ],
        "sourceFileCount": len(modules),
        "totalSourceBytes": total_source_bytes,
        "totalAstNodes": total_ast_nodes,
        "totalImportEdges": total_import_edges,
    }
    canonical = json.dumps(
        manifest,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _derive_python_source_snapshot_state(
    root: pathlib.Path,
) -> dict[str, object]:
    _fixed_bootstrap_profile_preflight()
    _authenticate_complete_contract()
    _authenticate_full_execution_profile()
    root_fd = _open_absolute_directory(root, authority_path=False)
    try:
        pre_inventory = _bounded_inventory(root_fd)
        module_names: dict[str, str] = {}
        seen_module_names: set[str] = set()
        for candidate in pre_inventory:
            relative = candidate[0]
            module_name = _module_name(relative)
            if module_name in seen_module_names:
                _refuse(
                    PythonSourceSnapshotRefusalCodeV1.DUPLICATE_MODULE_NAME,
                    relative,
                )
            seen_module_names.add(module_name)
            module_names[relative] = module_name
        retained = {
            candidate[0]: _acquire_source(root_fd, candidate)
            for candidate in pre_inventory
        }
        post_inventory = _bounded_inventory(root_fd)
        if post_inventory != pre_inventory:
            _refuse(PythonSourceSnapshotRefusalCodeV1.INVENTORY_CHANGED)
    finally:
        os.close(root_fd)

    modules: dict[str, PythonSourceUnitV1] = {}
    by_relative: dict[str, PythonSourceUnitV1] = {}
    private_asts: dict[str, ast.Module] = {}
    total_ast_nodes = 0
    for candidate in pre_inventory:
        relative = candidate[0]
        source_bytes = retained[relative]
        try:
            source_text = source_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise PythonSourceSnapshotRefusal(
                PythonSourceSnapshotRefusalCodeV1.INVALID_UTF8,
                relative,
            ) from exc
        try:
            tree = ast.parse(
                source_text,
                filename=relative,
                mode="exec",
                type_comments=False,
                feature_version=_FIXED_DESCRIPTOR_V1.ast_feature_version,
            )
            ast_node_count, ast_depth = _ast_measurements(tree)
        except SyntaxError as exc:
            raise PythonSourceSnapshotRefusal(
                PythonSourceSnapshotRefusalCodeV1.INVALID_PYTHON_SYNTAX,
                relative,
            ) from exc
        except (MemoryError, RecursionError) as exc:
            raise PythonSourceSnapshotRefusal(
                PythonSourceSnapshotRefusalCodeV1.RESOURCE_LIMIT_EXCEEDED,
                relative,
            ) from exc
        total_ast_nodes += ast_node_count
        if total_ast_nodes > _FIXED_DESCRIPTOR_V1.maximum_total_ast_nodes:
            _refuse(
                PythonSourceSnapshotRefusalCodeV1.RESOURCE_LIMIT_EXCEEDED,
                relative,
            )
        module_name = module_names[relative]
        unit = PythonSourceUnitV1(
            module_name=module_name,
            relative_path=relative,
            source_bytes=source_bytes,
            source_text=source_text,
            byte_length=len(source_bytes),
            sha256=f"sha256:{hashlib.sha256(source_bytes).hexdigest()}",
            ast_node_count=ast_node_count,
            ast_depth=ast_depth,
        )
        modules[module_name] = unit
        by_relative[relative] = unit
        private_asts[module_name] = tree

    required_roots = (
        *_FIXED_DESCRIPTOR_V1.production_import_roots,
        *_FIXED_DESCRIPTOR_V1.legacy_import_roots,
    )
    for required_root in required_roots:
        if required_root not in modules:
            _refuse(
                PythonSourceSnapshotRefusalCodeV1.MISSING_REQUIRED_IMPORT_ROOT,
            )
    known_modules = set(modules)
    graph: dict[str, tuple[PythonImportEdgeV1, ...]] = {}
    total_import_edges = 0
    for module_name, unit in sorted(modules.items()):
        edges = _import_edges(
            module_name,
            unit.relative_path,
            private_asts[module_name],
            known_modules,
        )
        total_import_edges += len(edges)
        if total_import_edges > _FIXED_DESCRIPTOR_V1.maximum_total_import_edges:
            _refuse(
                PythonSourceSnapshotRefusalCodeV1.RESOURCE_LIMIT_EXCEEDED,
                unit.relative_path,
            )
        graph[module_name] = edges
    production = _derive_reachability(
        graph,
        _FIXED_DESCRIPTOR_V1.production_import_roots,
    )
    legacy = _derive_reachability(
        graph,
        _FIXED_DESCRIPTOR_V1.legacy_import_roots,
    )
    total_source_bytes = sum(unit.byte_length for unit in modules.values())
    content_sha256 = _content_digest(
        modules,
        graph,
        production,
        legacy,
        total_source_bytes,
        total_ast_nodes,
        total_import_edges,
    )
    return {
        "_descriptor": _FIXED_DESCRIPTOR_V1,
        "_contract_authority": _FIXED_CONTRACT_AUTHORITY_V1,
        "_root_path": root,
        "_modules_by_name": types.MappingProxyType(dict(modules)),
        "_modules_by_relative_path": types.MappingProxyType(dict(by_relative)),
        "_private_asts": types.MappingProxyType(dict(private_asts)),
        "_import_graph": types.MappingProxyType(dict(graph)),
        "_production_reachability": types.MappingProxyType(dict(production)),
        "_legacy_reachability": types.MappingProxyType(dict(legacy)),
        "_source_file_count": len(modules),
        "_total_source_bytes": total_source_bytes,
        "_total_ast_nodes": total_ast_nodes,
        "_total_import_edges": total_import_edges,
        "_content_sha256": content_sha256,
        "_ast_copy_calls": 0,
    }


def _snapshot_builder_and_guard() -> tuple[
    typing.Callable[[pathlib.Path], PythonSourceSnapshotV1],
    typing.Callable[[object], bool],
]:
    builder_seal = object()
    authority_slots = (
        "_contract_authority",
        "_content_sha256",
        "_descriptor",
        "_import_graph",
        "_legacy_reachability",
        "_modules_by_name",
        "_modules_by_relative_path",
        "_private_asts",
        "_production_reachability",
        "_root_path",
        "_source_file_count",
        "_total_ast_nodes",
        "_total_import_edges",
        "_total_source_bytes",
    )

    def builder(root: pathlib.Path) -> PythonSourceSnapshotV1:
        state = _derive_python_source_snapshot_state(root)
        snapshot = object.__new__(PythonSourceSnapshotV1)
        for name, value in state.items():
            object.__setattr__(snapshot, name, value)
        state.clear()
        object.__setattr__(
            snapshot,
            "_builder_seal",
            (
                builder_seal,
                id(snapshot),
                tuple(
                    id(object.__getattribute__(snapshot, name))
                    for name in authority_slots
                ),
            ),
        )
        return snapshot

    def accepts(snapshot: object) -> bool:
        if type(snapshot) is not PythonSourceSnapshotV1:
            return False
        try:
            seal = object.__getattribute__(snapshot, "_builder_seal")
        except AttributeError:
            return False
        try:
            return (
                type(seal) is tuple
                and len(seal) == 3
                and seal[0] is builder_seal
                and seal[1] == id(snapshot)
                and seal[2]
                == tuple(
                    id(object.__getattribute__(snapshot, name))
                    for name in authority_slots
                )
            )
        except AttributeError:
            return False

    return builder, accepts


build_python_source_snapshot, _is_builder_snapshot = (
    _snapshot_builder_and_guard()
)
build_python_source_snapshot.__name__ = "build_python_source_snapshot"
build_python_source_snapshot.__qualname__ = "build_python_source_snapshot"
del _snapshot_builder_and_guard


def _line_count(unit: PythonSourceUnitV1) -> int:
    return len(unit.source_text.splitlines())


def _is_legacy_module(module: str) -> bool:
    return module in LEGACY_MODULES or any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in LEGACY_MODULE_PREFIXES
    )


def _render_import_execution_path(
    snapshot: PythonSourceSnapshotV1,
    path: _ImportExecutionPathV1,
) -> str:
    rendered = [path[0].target]
    for transition in path[1:]:
        if transition.kind is _ImportExecutionTransitionKindV1.REQUIRED_INITIALIZER:
            relative = snapshot.modules_by_name[transition.target].relative_path
            rendered.append(f"[required initializer {relative}]")
        else:
            rendered.append(transition.target)
    return " -> ".join(rendered)


def _incoming_transition(
    path: _ImportExecutionPathV1,
) -> _ImportExecutionTransitionV1 | None:
    return None if len(path) < 2 else path[-1]


def _transition_location(
    snapshot: PythonSourceSnapshotV1,
    transition: _ImportExecutionTransitionV1,
) -> str:
    if (
        transition.kind is _ImportExecutionTransitionKindV1.EXPLICIT_IMPORT
        and transition.predecessor is not None
        and transition.line is not None
    ):
        relative = snapshot.modules_by_name[transition.predecessor].relative_path
        return f"{relative}:{transition.line}"
    return snapshot.modules_by_name[transition.target].relative_path


def _dynamic_import_violations(
    tree: ast.Module,
) -> list[tuple[int, str]]:
    violations = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib" or alias.name.startswith(
                    "importlib."
                ):
                    violations.add(
                        (node.lineno, f"import of {alias.name!r}")
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module and (
                node.module == "importlib"
                or node.module.startswith("importlib.")
            ):
                violations.add(
                    (node.lineno, f"import from {node.module!r}")
                )
            if any(alias.name == "__import__" for alias in node.names):
                violations.add(
                    (node.lineno, "import of built-in '__import__'")
                )
        elif isinstance(node, ast.Name) and node.id == "__import__":
            violations.add(
                (node.lineno, "reference to built-in '__import__'")
            )
        elif isinstance(node, ast.Attribute) and node.attr == "__import__":
            violations.add(
                (node.lineno, "attribute reference to '__import__'")
            )
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
            and (
                (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "getattr"
                )
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "getattr"
                )
            )
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "__import__"
        ):
            violations.add(
                (node.lineno, "literal reflective access to '__import__'")
            )
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == "__import__"
        ):
            violations.add(
                (node.lineno, "literal subscript access to '__import__'")
            )
    return sorted(violations)


def _is_sys_modules(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
        and node.attr == "modules"
    )


def _mutates_sys_modules(node: ast.AST) -> bool:
    if _is_sys_modules(node) or (
        isinstance(node, ast.Subscript) and _is_sys_modules(node.value)
    ):
        return True
    if isinstance(node, ast.Starred):
        return _mutates_sys_modules(node.value)
    if isinstance(node, (ast.List, ast.Tuple)):
        return any(_mutates_sys_modules(item) for item in node.elts)
    return False


def _provider_import_policy_violations(
    tree: ast.Module,
) -> list[tuple[int, str]]:
    violations = set(_dynamic_import_violations(tree))
    mutating_methods = {
        "__delitem__",
        "__setitem__",
        "clear",
        "pop",
        "popitem",
        "setdefault",
        "update",
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Name)
            and node.id in {"compile", "exec"}
        ):
            violations.add(
                (node.lineno, f"reference to built-in {node.id!r}")
            )
        elif (
            isinstance(node, ast.Attribute)
            and node.attr in {"compile", "exec"}
        ):
            violations.add(
                (node.lineno, f"attribute reference to {node.attr!r}")
            )
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else (node.target,)
            )
            if any(_mutates_sys_modules(target) for target in targets):
                violations.add(
                    (node.lineno, "mutation of sys.modules")
                )
        elif isinstance(node, ast.Delete) and any(
            _mutates_sys_modules(target) for target in node.targets
        ):
            violations.add((node.lineno, "mutation of sys.modules"))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and _is_sys_modules(node.func.value)
            and node.func.attr in mutating_methods
        ):
            violations.add((node.lineno, "mutation of sys.modules"))
    return sorted(violations)


def _snapshot_trees(
    snapshot: PythonSourceSnapshotV1,
) -> collections.abc.Mapping[str, ast.Module]:
    return types.MappingProxyType(
        {
            module: snapshot.ast_for(module)
            for module in snapshot.modules_by_name
        }
    )


def _snapshot_and_trees(
    source: pathlib.Path | PythonSourceSnapshotV1,
    trees: collections.abc.Mapping[str, ast.Module] | None,
) -> tuple[
    PythonSourceSnapshotV1,
    collections.abc.Mapping[str, ast.Module],
]:
    snapshot = (
        source
        if type(source) is PythonSourceSnapshotV1
        else build_python_source_snapshot(source)
    )
    if not _is_builder_snapshot(snapshot):
        raise TypeError("source must be pathlib.Path or PythonSourceSnapshotV1")
    return snapshot, trees if trees is not None else _snapshot_trees(snapshot)


def _check_provider_import_policy(
    source: pathlib.Path | PythonSourceSnapshotV1 = ROOT,
    trees: collections.abc.Mapping[str, ast.Module] | None = None,
) -> list[str]:
    snapshot, trees = _snapshot_and_trees(source, trees)
    sources = snapshot.modules_by_name
    failures = []
    for module in PROVIDER_IMPORT_POLICY_MODULES:
        unit = sources.get(module)
        if unit is None:
            failures.append(
                f"required provider import policy module {module!r} is missing"
            )
            continue
        for line, reason in _provider_import_policy_violations(trees[module]):
            failures.append(
                f"{unit.relative_path}:{line}: forbidden provider import mechanism "
                f"({reason})"
            )
    return failures


def _legacy_resource_violations(
    tree: ast.Module,
) -> list[tuple[int, str]]:
    violations = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        normalized = node.value.replace("\\", "/")
        if normalized in LEGACY_RESOURCE_NAMES or any(
            normalized.endswith(f"/kernel/{name}")
            for name in LEGACY_RESOURCE_NAMES
        ):
            violations.add((node.lineno, normalized))
    return sorted(violations)


def _profile_neutrality_violations(
    tree: ast.Module,
) -> list[tuple[int, str]]:
    violations = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("kernel.profiles.si_ffs"):
                    violations.add(
                        (node.lineno, f"import of {alias.name!r}")
                    )
        elif isinstance(node, ast.ImportFrom):
            imported = node.module or ""
            if (
                imported.startswith("kernel.profiles.si_ffs")
                or imported == "profiles.si_ffs"
                or imported.startswith("profiles.si_ffs.")
                or (
                    imported.endswith("profiles")
                    and any(alias.name == "si_ffs" for alias in node.names)
                )
            ):
                violations.add(
                    (node.lineno, f"import from {imported!r}")
                )
        elif isinstance(node, ast.Name) and _is_si_specific_name(node.id):
            violations.add(
                (node.lineno, f"SI-specific name {node.id!r}")
            )
        elif (
            isinstance(node, ast.Attribute)
            and node.attr.lower() == "si_ffs"
        ):
            violations.add(
                (node.lineno, f"SI-specific attribute {node.attr!r}")
            )
        elif (
            isinstance(node, ast.Attribute)
            and _is_si_specific_name(node.attr)
        ):
            violations.add(
                (node.lineno, f"SI-specific attribute {node.attr!r}")
            )
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "si.ffs" in node.value.lower()
        ):
            violations.add(
                (node.lineno, "SI semantic literal")
            )
    return sorted(violations)


def _is_si_specific_name(value: str) -> bool:
    """Recognize the SI acronym without treating ordinary SI words as refs."""
    if SI_SPECIFIC_NAME.match(value) is None:
        return False
    suffix = value[2:]
    return (
        not suffix
        or suffix.startswith("_")
        or (
            len(suffix) > 1
            and suffix[0].isupper()
            and suffix[1].islower()
        )
    )


def _profile_loader_violations(tree: ast.Module) -> list[tuple[int, str]]:
    violations = set(_dynamic_import_violations(tree))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib" or alias.name.startswith(
                    "importlib."
                ):
                    violations.add(
                        (node.lineno, f"import of {alias.name!r}")
                    )
        elif isinstance(node, ast.ImportFrom) and node.module and (
            node.module == "importlib"
            or node.module.startswith("importlib.")
        ):
            violations.add(
                (node.lineno, f"import from {node.module!r}")
            )
        elif isinstance(node, ast.Name) and node.id in {"compile", "exec"}:
            violations.add(
                (node.lineno, f"reference to {node.id!r}")
            )
        elif (
            isinstance(node, ast.Attribute)
            and node.attr in {"compile", "exec"}
        ):
            violations.add(
                (node.lineno, f"attribute reference to {node.attr!r}")
            )
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "sys"
            and node.attr == "modules"
        ):
            violations.add(
                (node.lineno, "reference to 'sys.modules'")
            )
    return sorted(violations)


def _check_import_firewall(
    source: pathlib.Path | PythonSourceSnapshotV1 = ROOT,
    trees: collections.abc.Mapping[str, ast.Module] | None = None,
    execution_closures: _ImportExecutionClosuresV1 | None = None,
) -> list[str]:
    snapshot, trees = _snapshot_and_trees(source, trees)
    sources = snapshot.modules_by_name
    if execution_closures is None:
        execution_closures = _derive_import_execution_closures(
            snapshot,
            trees,
        )
    failures = []

    production_paths = execution_closures.production
    for module, path in sorted(production_paths.items()):
        rendered_path = _render_import_execution_path(snapshot, path)
        if _is_legacy_module(module):
            incoming = _incoming_transition(path)
            if incoming is not None:
                failures.append(
                    f"{_transition_location(snapshot, incoming)}: "
                    f"production import path "
                    f"{rendered_path} reaches legacy module {module!r}"
                )
        for line, reason in _dynamic_import_violations(trees[module]):
            relative = sources[module].relative_path
            failures.append(
                f"{relative}:{line}: forbidden dynamic import mechanism "
                f"({reason}); production import path {rendered_path}"
            )
        for line, resource in _legacy_resource_violations(trees[module]):
            relative = sources[module].relative_path
            failures.append(
                f"{relative}:{line}: production references legacy resource "
                f"{resource!r}; production import path {rendered_path}"
            )

    legacy_paths = execution_closures.legacy
    for module, path in sorted(legacy_paths.items()):
        if module not in PRODUCTION_COMPOSITION_MODULES:
            continue
        incoming = _incoming_transition(path)
        if incoming is None:
            continue
        failures.append(
            f"{_transition_location(snapshot, incoming)}: legacy import path "
            f"{_render_import_execution_path(snapshot, path)} reaches "
            f"production composition "
            f"module {module!r}"
        )
    for module in PROFILE_NEUTRAL_MODULES:
        if module not in trees:
            failures.append(
                f"required profile-neutral module {module!r} is missing"
            )
            continue
        for line, reason in _profile_neutrality_violations(
            trees[module],
        ):
            relative = sources[module].relative_path
            failures.append(
                f"{relative}:{line}: profile-neutral module contains {reason}"
            )
    if PROFILE_LOADER_MODULE not in trees:
        failures.append(
            f"required profile provider loader module "
            f"{PROFILE_LOADER_MODULE!r} is missing"
        )
    else:
        for line, reason in _profile_loader_violations(
            trees[PROFILE_LOADER_MODULE]
        ):
            relative = sources[PROFILE_LOADER_MODULE].relative_path
            failures.append(
                f"{relative}:{line}: profile provider loader contains {reason}"
            )
    return failures


def _annotation_uses_any(annotation: ast.expr | None) -> bool:
    return annotation is not None and any(
        isinstance(node, ast.Name) and node.id == "Any"
        for node in ast.walk(annotation)
    )


def _trust_interface_uses_any(tree: ast.Module) -> list[int]:
    lines = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annotations = [
                *(argument.annotation for argument in node.args.args),
                *(argument.annotation for argument in node.args.kwonlyargs),
                node.returns,
            ]
            if any(_annotation_uses_any(value) for value in annotations):
                lines.append(node.lineno)
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if (
                    isinstance(member, ast.AnnAssign)
                    and _annotation_uses_any(member.annotation)
                ):
                    lines.append(member.lineno)
    return lines


class _EnvironmentReadVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = []
        self.lines: list[int] = []
        self.os_modules = {"os"}
        self.direct_readers: set[str] = set()

    def _visit_scope(self, node) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_ClassDef = _visit_scope
    visit_FunctionDef = _visit_scope
    visit_AsyncFunctionDef = _visit_scope

    def visit_Import(self, node: ast.Import) -> None:
        self.os_modules.update(
            alias.asname or alias.name
            for alias in node.names
            if alias.name == "os"
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "os":
            self.direct_readers.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name in {"getenv", "environ"}
            )

    def _is_environment_reference(self, target) -> bool:
        if isinstance(target, ast.Name):
            return target.id in self.direct_readers
        if not isinstance(target, ast.Attribute):
            return False
        if (
            isinstance(target.value, ast.Name)
            and target.value.id in self.os_modules
            and target.attr in {"getenv", "environ"}
        ):
            return True
        return self._is_environment_reference(target.value)

    def _check(self, node, target) -> None:
        if self._is_environment_reference(target) and self.scope[-2:] != [
            "RuntimeConfig",
            "from_env",
        ]:
            self.lines.append(node.lineno)

    def visit_Call(self, node: ast.Call) -> None:
        self._check(node, node.func)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self._check(node, node.value)
        self.generic_visit(node)


def _environment_reads(tree: ast.Module) -> list[int]:
    visitor = _EnvironmentReadVisitor()
    visitor.visit(tree)
    return visitor.lines


def _tenant_uow_class_violations(tree: ast.Module) -> list[tuple[int, str]]:
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "TenantUnitOfWork"
    ]
    if len(classes) != 1:
        return [(1, "TenantUnitOfWork class count differs")]
    unit = classes[0]
    public_surface = {
        member.name
        for member in unit.body
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not member.name.startswith("_")
    }
    for node in ast.walk(unit):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and not node.attr.startswith("_")
        ):
            public_surface.add(node.attr)
    violations = []
    if public_surface != _TENANT_UOW_PUBLIC_SURFACE:
        violations.append(
            (
                unit.lineno,
                f"TenantUnitOfWork public surface is {sorted(public_surface)!r}",
            )
        )
    initializers = [
        member
        for member in unit.body
        if isinstance(member, ast.FunctionDef) and member.name == "__init__"
    ]
    if len(initializers) != 1:
        violations.append((unit.lineno, "TenantUnitOfWork initializer count differs"))
    else:
        initializer = initializers[0]
        arguments = initializer.args
        positional = (*arguments.posonlyargs, *arguments.args)
        parameter_names = tuple(argument.arg for argument in positional)
        if (
            parameter_names != _TENANT_UOW_INIT_PARAMETERS
            or arguments.vararg is not None
            or arguments.kwarg is not None
            or arguments.kwonlyargs
        ):
            violations.append(
                (initializer.lineno, "TenantUnitOfWork accepts a non-facade dependency")
            )
    slots = None
    for member in unit.body:
        if not isinstance(member, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "__slots__"
            for target in member.targets
        ):
            continue
        if isinstance(member.value, (ast.Tuple, ast.List)) and all(
            isinstance(element, ast.Constant) and type(element.value) is str
            for element in member.value.elts
        ):
            slots = frozenset(element.value for element in member.value.elts)
    if slots != _TENANT_UOW_SLOTS:
        violations.append((unit.lineno, "TenantUnitOfWork slots differ"))
    for node in ast.walk(unit):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and any(
                token in node.attr.lower() for token in ("connection", "cursor", "pool")
            )
        ):
            violations.append((node.lineno, "TenantUnitOfWork stores a raw handle"))
    return sorted(set(violations))


def _tenant_handle_escape_accesses(tree: ast.Module) -> list[tuple[int, str]]:
    """Find direct private-facade access as a static anti-drift signal."""
    return sorted(
        {
            (node.lineno, node.attr)
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr.startswith("_TenantUnitOfWork__")
        }
    )


def _check_tenant_uow_architecture(
    snapshot: PythonSourceSnapshotV1,
    trees: collections.abc.Mapping[str, ast.Module],
    execution_closures: _ImportExecutionClosuresV1,
) -> list[str]:
    failures = [
        f"kernel/tenant_uow.py:{line}: {reason}"
        for line, reason in _tenant_uow_class_violations(trees[_TENANT_UOW_MODULE])
    ]
    for module in sorted(execution_closures.production):
        if module == _TENANT_UOW_MODULE or not (
            module == "kernel" or module.startswith("kernel.")
        ):
            continue
        relative = snapshot.modules_by_name[module].relative_path
        for line, attribute in _tenant_handle_escape_accesses(trees[module]):
            failures.append(
                f"{relative}:{line}: tenant UnitOfWork private-state access "
                f"{attribute!r}"
            )
    return failures


def _check_production(
    snapshot: PythonSourceSnapshotV1,
    trees: collections.abc.Mapping[str, ast.Module],
    relative: str,
    budget: int,
    *,
    allow_environment: bool = False,
) -> list[str]:
    unit = snapshot.modules_by_relative_path[relative]
    tree = trees[unit.module_name]
    failures = []
    line_count = _line_count(unit)
    if line_count > budget:
        failures.append(f"{relative}: {line_count} lines exceeds {budget}")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = node.end_lineno - node.lineno + 1
            if (
                relative != SECURITY_AUDIT_OBSERVER_ROOT_RELATIVE_PATH
                and length > MAX_FUNCTION_LINES
            ):
                failures.append(
                    f"{relative}:{node.lineno}: {node.name} is {length} lines; "
                    f"maximum is {MAX_FUNCTION_LINES}"
                )
        if isinstance(node, ast.Name) and node.id in PROHIBITED_NAMES:
            failures.append(
                f"{relative}:{node.lineno}: prohibited name {node.id!r}"
            )
        if isinstance(node, ast.Attribute) and node.attr in PROHIBITED_NAMES:
            failures.append(
                f"{relative}:{node.lineno}: prohibited attribute {node.attr!r}"
            )
    for line in _trust_interface_uses_any(tree):
        failures.append(f"{relative}:{line}: Any appears at a trust interface")
    if not allow_environment:
        for line in _environment_reads(tree):
            failures.append(
                f"{relative}:{line}: domain module reads the environment"
            )
    return failures


def _check_direct_import_bounds(snapshot: PythonSourceSnapshotV1) -> list[str]:
    failures = []
    for relative, expected in DIRECT_IMPORT_BOUNDS.items():
        module = snapshot.modules_by_relative_path[relative].module_name
        actual = frozenset(edge.target for edge in snapshot.import_graph[module])
        if actual != expected:
            failures.append(
                f"{relative}: direct repository imports {sorted(actual)!r} "
                f"do not equal fixed bound {sorted(expected)!r}"
            )
    return failures


def _check_security_audit_gap_surface(
    snapshot: PythonSourceSnapshotV1,
    trees: collections.abc.Mapping[str, ast.Module],
) -> list[str]:
    relative = "kernel/security_audit_gap.py"
    module = snapshot.modules_by_relative_path[relative].module_name
    failures = []
    for node in ast.walk(trees[module]):
        imported = None
        if isinstance(node, ast.Import):
            imported = tuple(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported = (node.module.split(".", 1)[0],)
        if imported is not None:
            for name in imported:
                if name in SECURITY_AUDIT_GAP_FORBIDDEN_IMPORTS:
                    failures.append(
                        f"{relative}:{node.lineno}: prohibited import {name!r}"
                    )
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        if name in SECURITY_AUDIT_GAP_FORBIDDEN_NAMES:
            failures.append(
                f"{relative}:{node.lineno}: prohibited gap surface {name!r}"
            )
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "ofarm_security." in node.value
            and "ofarm_security.append_audit_gap" not in node.value
        ):
            failures.append(
                f"{relative}:{node.lineno}: alternate audit SQL surface"
            )
    return failures


def _normalized_import_statement(
    node: ast.ImportFrom,
) -> tuple[str | None, int, tuple[tuple[str, str | None], ...]]:
    return (
        node.module,
        node.level,
        tuple((alias.name, alias.asname) for alias in node.names),
    )


def _function_uses_now_us_in_comparison(
    tree: ast.Module,
    function_name: str,
) -> bool:
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    ]
    if len(functions) != 1:
        return False
    function = functions[0]
    if "now_us" not in {
        argument.arg
        for argument in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        )
    }:
        return False
    return any(
        isinstance(node, ast.Compare)
        and any(
            isinstance(member, ast.Name)
            and member.id == "now_us"
            and isinstance(member.ctx, ast.Load)
            for member in ast.walk(node)
        )
        for node in ast.walk(function)
    )


def _security_audit_approval_surface_violations(
    tree: ast.Module,
) -> list[str]:
    violations = []
    import_statements = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            violations.append(
                f"{node.lineno}: whole-module import is prohibited"
            )
        elif isinstance(node, ast.ImportFrom):
            statement = _normalized_import_statement(node)
            import_statements.append(statement)
            if statement not in SECURITY_AUDIT_APPROVAL_IMPORT_STATEMENTS:
                violations.append(
                    f"{node.lineno}: import statement is outside exact allowlist"
                )
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        if name in SECURITY_AUDIT_APPROVAL_FORBIDDEN_NAMES:
            violations.append(
                f"{node.lineno}: prohibited approval surface {name!r}"
            )
        if (
            isinstance(node, ast.Name)
            and node.id == "now_us"
            and isinstance(node.ctx, (ast.Store, ast.Del))
        ):
            violations.append(
                f"{node.lineno}: caller-owned now_us is overwritten"
            )
    if (
        len(import_statements) != len(SECURITY_AUDIT_APPROVAL_IMPORT_STATEMENTS)
        or frozenset(import_statements)
        != SECURITY_AUDIT_APPROVAL_IMPORT_STATEMENTS
    ):
        violations.append("exact import statement set is incomplete or duplicated")
    for function_name in ("_authority", "_request"):
        if not _function_uses_now_us_in_comparison(tree, function_name):
            violations.append(
                f"{function_name} lacks caller-owned now_us freshness comparison"
            )
    return sorted(set(violations))


def _check_security_audit_approval_surface(
    snapshot: PythonSourceSnapshotV1,
    trees: collections.abc.Mapping[str, ast.Module],
) -> list[str]:
    relative = "deployment/postgresql/security_audit_approval.py"
    module = snapshot.modules_by_relative_path[relative].module_name
    return [
        f"{relative}:{violation}"
        for violation in _security_audit_approval_surface_violations(
            trees[module]
        )
    ]


def _top_level_function(
    tree: ast.Module,
    name: str,
) -> ast.FunctionDef | None:
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    return functions[0] if len(functions) == 1 else None


def _top_level_class_fields(
    tree: ast.Module,
    name: str,
) -> tuple[str, ...] | None:
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    ]
    if len(classes) != 1:
        return None
    return tuple(
        node.target.id
        for node in classes[0].body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    )


def _top_level_dataclass_options(
    tree: ast.Module,
    name: str,
) -> dict[str, object] | None:
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    ]
    if len(classes) != 1:
        return None
    decorators = [
        node
        for node in classes[0].decorator_list
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "dataclass"
    ]
    if len(decorators) != 1:
        return None
    return {
        keyword.arg: keyword.value.value
        for keyword in decorators[0].keywords
        if keyword.arg is not None
        and isinstance(keyword.value, ast.Constant)
    }


def _credential_dataclass_options(
    target: ast.ClassDef,
) -> dict[str, bool] | None:
    if len(target.decorator_list) != 1:
        return None
    decorator = target.decorator_list[0]
    if (
        not isinstance(decorator, ast.Call)
        or not isinstance(decorator.func, ast.Name)
        or decorator.func.id != "dataclass"
        or decorator.args
    ):
        return None
    options: dict[str, bool] = {}
    for keyword in decorator.keywords:
        if (
            keyword.arg is None
            or keyword.arg in options
            or not isinstance(keyword.value, ast.Constant)
            or type(keyword.value.value) is not bool
        ):
            return None
        options[keyword.arg] = keyword.value.value
    return options


def _credential_named_attribute(
    node: ast.AST,
    owner: str,
    attribute: str,
) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Load)
        and node.attr == attribute
        and isinstance(node.value, ast.Name)
        and isinstance(node.value.ctx, ast.Load)
        and node.value.id == owner
    )


def _credential_class_rejection(statement: ast.stmt) -> bool:
    if not isinstance(statement, ast.If) or statement.orelse:
        return False
    test = statement.test
    if (
        not isinstance(test, ast.Compare)
        or len(test.ops) != 1
        or not isinstance(test.ops[0], ast.IsNot)
        or len(test.comparators) != 1
        or not _credential_named_attribute(test.left, "other", "__class__")
        or not _credential_named_attribute(
            test.comparators[0], "self", "__class__"
        )
        or len(statement.body) != 1
    ):
        return False
    returned = statement.body[0]
    return (
        isinstance(returned, ast.Return)
        and isinstance(returned.value, ast.Name)
        and returned.value.id == "NotImplemented"
    )


def _credential_cast_assignment(statement: ast.stmt) -> bool:
    if (
        not isinstance(statement, ast.Assign)
        or len(statement.targets) != 1
        or not isinstance(statement.targets[0], ast.Name)
        or statement.targets[0].id != "other_carrier"
        or not isinstance(statement.value, ast.Call)
    ):
        return False
    call = statement.value
    return (
        isinstance(call.func, ast.Name)
        and call.func.id == "cast"
        and len(call.args) == 2
        and not call.keywords
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "Self"
        and isinstance(call.args[1], ast.Name)
        and call.args[1].id == "other"
    )


def _credential_field_tuple(
    node: ast.AST,
    owner: str,
) -> tuple[str, ...] | None:
    if not isinstance(node, ast.Tuple) or not isinstance(node.ctx, ast.Load):
        return None
    fields = []
    for element in node.elts:
        if (
            not isinstance(element, ast.Attribute)
            or not isinstance(element.ctx, ast.Load)
            or not isinstance(element.value, ast.Name)
            or not isinstance(element.value.ctx, ast.Load)
            or element.value.id != owner
        ):
            return None
        fields.append(element.attr)
    return tuple(fields)


def _credential_bound_names(target: ast.AST) -> tuple[str, ...]:
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, ast.Starred):
        return _credential_bound_names(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(
            name
            for element in target.elts
            for name in _credential_bound_names(element)
        )
    return ()


_CREDENTIAL_DISPLAY_OR_HASH_MEMBERS = frozenset(
    {"__hash__", "__repr__", "__str__", "__format__"}
)
_CREDENTIAL_GOVERNED_SPECIAL_MEMBERS = (
    _CREDENTIAL_DISPLAY_OR_HASH_MEMBERS | {"__eq__"}
)
_CREDENTIAL_DYNAMIC_NAMESPACE_CALLS = frozenset(
    {"exec", "eval", "locals", "vars"}
)
_CREDENTIAL_COMPREHENSIONS = (
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


class _CredentialNamespaceEvent(typing.NamedTuple):
    kind: str
    name: str | None
    origin: str
    node: ast.AST
    direct: bool


class _CredentialNamespaceCollector:
    def __init__(
        self,
        *,
        future_annotations: bool,
        annotation_resolution_symbols: frozenset[str],
    ) -> None:
        self._future_annotations = future_annotations
        self._annotation_resolution_symbols = annotation_resolution_symbols
        self._events: list[_CredentialNamespaceEvent] = []

    def collect(
        self,
        target: ast.ClassDef,
    ) -> tuple[_CredentialNamespaceEvent, ...]:
        for statement in target.body:
            self._statement(statement, direct=True)
        return tuple(self._events)

    def _emit(
        self,
        kind: str,
        name: str | None,
        node: ast.AST,
        *,
        direct: bool = False,
    ) -> None:
        self._events.append(
            _CredentialNamespaceEvent(
                kind=kind,
                name=name,
                origin=type(node).__name__,
                node=node,
                direct=direct,
            )
        )

    def _expressions(
        self,
        expressions: collections.abc.Iterable[ast.expr],
    ) -> None:
        for expression in expressions:
            self._expression(expression)

    def _expression_children(self, node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                self._expression(child)
            elif not isinstance(child, ast.stmt):
                self._expression_children(child)

    def _expression(self, node: ast.expr) -> None:
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in {"__annotations__", "globals"}
        ):
            self._emit("unbounded", None, node)
            return
        if isinstance(node, ast.Lambda):
            self._expressions(node.args.defaults)
            self._expressions(
                default
                for default in node.args.kw_defaults
                if default is not None
            )
            return
        if isinstance(node, _CREDENTIAL_COMPREHENSIONS):
            self._emit("unbounded", None, node)
            return
        if isinstance(node, ast.NamedExpr):
            self._expression(node.value)
            self._target_names(node.target, "bind", node)
            return
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _CREDENTIAL_DYNAMIC_NAMESPACE_CALLS
        ):
            self._emit("unbounded", None, node)
        self._expression_children(node)

    def _target_expressions(self, target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            return
        if isinstance(target, ast.Starred):
            self._target_expressions(target.value)
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._target_expressions(element)
            return
        if isinstance(target, ast.Attribute):
            self._expression(target.value)
            return
        if isinstance(target, ast.Subscript):
            self._expression(target.value)
            if isinstance(target.slice, ast.expr):
                self._expression(target.slice)
            else:
                self._expression_children(target.slice)
            return
        self._emit("unbounded", None, target)

    def _target_names(
        self,
        target: ast.AST,
        kind: str,
        origin: ast.AST,
    ) -> None:
        for name in _credential_bound_names(target):
            self._emit(kind, name, origin)

    def _target(
        self,
        target: ast.AST,
        kind: str,
        origin: ast.AST,
    ) -> None:
        self._target_expressions(target)
        self._target_names(target, kind, origin)

    @staticmethod
    def _argument_annotations(arguments: ast.arguments) -> tuple[ast.expr, ...]:
        annotations = [
            argument.annotation
            for argument in (
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
            )
            if argument.annotation is not None
        ]
        if (
            arguments.vararg is not None
            and arguments.vararg.annotation is not None
        ):
            annotations.append(arguments.vararg.annotation)
        if (
            arguments.kwarg is not None
            and arguments.kwarg.annotation is not None
        ):
            annotations.append(arguments.kwarg.annotation)
        return tuple(annotations)

    def _definition(self, statement: ast.stmt, *, direct: bool) -> bool:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._expressions(statement.decorator_list)
            self._expressions(statement.args.defaults)
            self._expressions(
                default
                for default in statement.args.kw_defaults
                if default is not None
            )
            if not self._future_annotations:
                self._expressions(self._argument_annotations(statement.args))
                if statement.returns is not None:
                    self._expression(statement.returns)
            if statement.type_params:
                self._emit("unbounded", None, statement)
            self._emit("bind", statement.name, statement, direct=direct)
            return True
        if isinstance(statement, ast.ClassDef):
            self._expressions(statement.decorator_list)
            self._expressions(statement.bases)
            self._expressions(keyword.value for keyword in statement.keywords)
            if statement.type_params:
                self._emit("unbounded", None, statement)
            self._emit("bind", statement.name, statement, direct=direct)
            return True
        if isinstance(statement, ast.TypeAlias):
            names = _credential_bound_names(statement.name)
            if not names:
                self._emit("unbounded", None, statement)
            for name in names:
                self._emit("bind", name, statement)
            return True
        return False

    def _imports(self, statement: ast.Import | ast.ImportFrom) -> None:
        for alias in statement.names:
            if isinstance(statement, ast.ImportFrom) and alias.name == "*":
                self._emit("unbounded", None, statement)
                continue
            bound = alias.asname or alias.name.split(".", 1)[0]
            self._emit("bind", bound, statement)

    def _assignment(self, statement: ast.stmt) -> bool:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            self._imports(statement)
            return True
        if isinstance(statement, ast.Assign):
            self._expression(statement.value)
            for target in statement.targets:
                self._target(target, "bind", statement)
            return True
        if isinstance(statement, ast.AnnAssign):
            if (
                type(statement.simple) is not int
                or statement.simple not in {0, 1}
                or (
                    statement.simple == 1
                    and not isinstance(statement.target, ast.Name)
                )
            ):
                self._emit("unbounded", None, statement)
                return True
            if statement.value is not None:
                self._expression(statement.value)
            self._target_expressions(statement.target)
            if statement.simple == 1 or statement.value is not None:
                self._target_names(statement.target, "bind", statement)
            if not self._future_annotations:
                self._expression(statement.annotation)
            return True
        if isinstance(statement, ast.AugAssign):
            self._target_expressions(statement.target)
            self._expression(statement.value)
            self._target_names(statement.target, "bind", statement)
            return True
        if isinstance(statement, ast.Delete):
            for target in statement.targets:
                self._target(target, "delete", statement)
            return True
        if isinstance(statement, (ast.Global, ast.Nonlocal)):
            for name in statement.names:
                if name in (
                    _CREDENTIAL_GOVERNED_SPECIAL_MEMBERS
                    | self._annotation_resolution_symbols
                ):
                    self._emit("unbounded", name, statement)
            return True
        return False

    def _pattern(self, pattern: ast.pattern) -> None:
        if isinstance(pattern, ast.MatchValue):
            self._expression(pattern.value)
        elif isinstance(pattern, ast.MatchSingleton):
            return
        elif isinstance(pattern, ast.MatchSequence):
            for child in pattern.patterns:
                self._pattern(child)
        elif isinstance(pattern, ast.MatchMapping):
            self._expressions(pattern.keys)
            for child in pattern.patterns:
                self._pattern(child)
            if pattern.rest is not None:
                self._emit("bind", pattern.rest, pattern)
        elif isinstance(pattern, ast.MatchClass):
            self._expression(pattern.cls)
            for child in (*pattern.patterns, *pattern.kwd_patterns):
                self._pattern(child)
        elif isinstance(pattern, ast.MatchStar):
            if pattern.name is not None:
                self._emit("bind", pattern.name, pattern)
        elif isinstance(pattern, ast.MatchAs):
            if pattern.pattern is not None:
                self._pattern(pattern.pattern)
            if pattern.name is not None:
                self._emit("bind", pattern.name, pattern)
        elif isinstance(pattern, ast.MatchOr):
            for child in pattern.patterns:
                self._pattern(child)
        else:
            self._emit("unbounded", None, pattern)

    def _suite(self, statements: collections.abc.Iterable[ast.stmt]) -> None:
        for statement in statements:
            self._statement(statement, direct=False)

    def _try(self, statement: ast.Try | ast.TryStar) -> None:
        self._suite(statement.body)
        for handler in statement.handlers:
            if handler.type is not None:
                self._expression(handler.type)
            if handler.name is not None:
                self._emit("bind", handler.name, handler)
            self._suite(handler.body)
        self._suite(statement.orelse)
        self._suite(statement.finalbody)

    def _match(self, statement: ast.Match) -> None:
        self._expression(statement.subject)
        for case in statement.cases:
            self._pattern(case.pattern)
            if case.guard is not None:
                self._expression(case.guard)
            self._suite(case.body)

    def _control_flow(self, statement: ast.stmt) -> bool:
        if isinstance(statement, (ast.If, ast.While)):
            self._expression(statement.test)
            self._suite(statement.body)
            self._suite(statement.orelse)
            return True
        if isinstance(statement, (ast.For, ast.AsyncFor)):
            self._expression(statement.iter)
            self._target(statement.target, "bind", statement)
            self._suite(statement.body)
            self._suite(statement.orelse)
            return True
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            for item in statement.items:
                self._expression(item.context_expr)
                if item.optional_vars is not None:
                    self._target(item.optional_vars, "bind", statement)
            self._suite(statement.body)
            return True
        if isinstance(statement, (ast.Try, ast.TryStar)):
            self._try(statement)
            return True
        if isinstance(statement, ast.Match):
            self._match(statement)
            return True
        return False

    def _statement(self, statement: ast.stmt, *, direct: bool) -> None:
        if self._definition(statement, direct=direct):
            return
        if self._assignment(statement):
            return
        if self._control_flow(statement):
            return
        if isinstance(statement, ast.Expr):
            self._expression(statement.value)
            return
        if isinstance(statement, ast.Assert):
            self._expression(statement.test)
            if statement.msg is not None:
                self._expression(statement.msg)
            return
        if isinstance(statement, ast.Raise):
            if statement.exc is not None:
                self._expression(statement.exc)
            if statement.cause is not None:
                self._expression(statement.cause)
            return
        if not isinstance(statement, (ast.Pass, ast.Break, ast.Continue)):
            self._emit("unbounded", None, statement)


def _credential_future_annotations(tree: ast.Module) -> bool:
    return any(
        isinstance(statement, ast.ImportFrom)
        and statement.module == "__future__"
        and any(alias.name == "annotations" for alias in statement.names)
        for statement in tree.body
    )


def _credential_class_namespace_events(
    tree: ast.Module,
    target: ast.ClassDef,
    annotation_resolution_symbols: frozenset[str] = frozenset(),
) -> tuple[_CredentialNamespaceEvent, ...]:
    collector = _CredentialNamespaceCollector(
        future_annotations=_credential_future_annotations(tree),
        annotation_resolution_symbols=annotation_resolution_symbols,
    )
    return collector.collect(target)


class _CredentialDirectProjection(typing.NamedTuple):
    declarations: tuple[ast.AnnAssign, ...]
    methods: tuple[tuple[ast.FunctionDef, str], ...]


def _credential_method_header_matches(
    method: ast.FunctionDef,
    expected: _CredentialMethodHeader,
) -> bool:
    arguments = method.args
    observed_arguments = tuple(
        (
            argument.arg,
            None
            if argument.annotation is None
            else ast.dump(argument.annotation, include_attributes=False),
        )
        for argument in arguments.args
    )
    return (
        method.name == expected.name
        and tuple(
            ast.dump(decorator, include_attributes=False)
            for decorator in method.decorator_list
        )
        == expected.decorators
        and not method.type_params
        and method.type_comment is None
        and not arguments.posonlyargs
        and observed_arguments == expected.positional_arguments
        and all(argument.type_comment is None for argument in arguments.args)
        and arguments.vararg is None
        and not arguments.kwonlyargs
        and arguments.kwarg is None
        and not arguments.defaults
        and not arguments.kw_defaults
        and method.returns is not None
        and ast.dump(method.returns, include_attributes=False)
        == expected.return_annotation
        and expected.body_authority
        in {"exact-equality", "opaque-deferred"}
    )


def _credential_direct_class_projection(
    target: ast.ClassDef,
    declarations: tuple[tuple[str, str], ...],
    methods: tuple[_CredentialMethodHeader, ...],
) -> _CredentialDirectProjection | None:
    if (
        not declarations
        or len({name for name, _annotation in declarations})
        != len(declarations)
        or len({method.name for method in methods}) != len(methods)
        or len(target.body) != len(declarations) + len(methods)
    ):
        return None
    approved_declarations = []
    approved_methods = []
    for index, statement in enumerate(target.body):
        if index < len(declarations):
            name, annotation_shape = declarations[index]
            if not (
                isinstance(statement, ast.AnnAssign)
                and type(statement.simple) is int
                and statement.simple == 1
                and isinstance(statement.target, ast.Name)
                and isinstance(statement.target.ctx, ast.Store)
                and statement.target.id == name
                and statement.value is None
                and ast.dump(statement.annotation, include_attributes=False)
                == annotation_shape
            ):
                return None
            approved_declarations.append(statement)
            continue
        expected_method = methods[index - len(declarations)]
        if not isinstance(statement, ast.FunctionDef) or not (
            _credential_method_header_matches(statement, expected_method)
        ):
            return None
        approved_methods.append((statement, expected_method.body_authority))
    return _CredentialDirectProjection(
        declarations=tuple(approved_declarations),
        methods=tuple(approved_methods),
    )


def _credential_annotation_resolution_symbols(
    declarations: tuple[ast.AnnAssign, ...],
) -> frozenset[str]:
    return frozenset(
        node.id
        for declaration in declarations
        for node in ast.walk(declaration.annotation)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    )


def _credential_collected_simple_declaration_nodes(
    events: tuple[_CredentialNamespaceEvent, ...],
) -> tuple[ast.AnnAssign, ...]:
    return tuple(
        event.node
        for event in events
        if event.kind == "bind"
        and isinstance(event.node, ast.AnnAssign)
        and type(event.node.simple) is int
        and event.node.simple == 1
        and isinstance(event.node.target, ast.Name)
    )


def _credential_eq_violations(
    method: ast.FunctionDef,
    declared_fields: tuple[str, ...],
) -> list[str]:
    violations = []
    arguments = method.args
    if (
        method.decorator_list
        or arguments.posonlyargs
        or tuple(argument.arg for argument in arguments.args)
        != ("self", "other")
        or arguments.vararg is not None
        or arguments.kwonlyargs
        or arguments.kwarg is not None
        or arguments.defaults
        or arguments.kw_defaults
    ):
        violations.append("__eq__ signature differs from the exact contract")
    if len(method.body) != 3:
        violations.append("__eq__ body is not the exact three-step operation")
        return violations
    if not _credential_class_rejection(method.body[0]):
        violations.append("__eq__ lacks exact-class NotImplemented rejection")
    if not _credential_cast_assignment(method.body[1]):
        violations.append("__eq__ cast step differs from the exact contract")
    returned = method.body[2]
    if not isinstance(returned, ast.Return) or not isinstance(
        returned.value, ast.Compare
    ):
        violations.append("__eq__ does not return direct tuple equality")
        return violations
    comparison = returned.value
    if (
        len(comparison.ops) != 1
        or not isinstance(comparison.ops[0], ast.Eq)
        or len(comparison.comparators) != 1
    ):
        violations.append("__eq__ comparison is not one direct equality")
        return violations
    left_fields = _credential_field_tuple(comparison.left, "self")
    right_fields = _credential_field_tuple(
        comparison.comparators[0], "other_carrier"
    )
    if left_fields != declared_fields or right_fields != declared_fields:
        violations.append("__eq__ field tuples differ from declared fields")
    return violations


def _credential_diagnostic_carrier_violations(
    tree: ast.Module,
    class_name: str,
    protected_fields: tuple[str, ...],
    declarations: tuple[tuple[str, str], ...],
    methods: tuple[_CredentialMethodHeader, ...],
) -> list[str]:
    prefix = f"{class_name}: "
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(classes) != 1:
        return [prefix + "exact top-level class is missing or duplicated"]
    target = classes[0]
    violations = []
    declared_fields = tuple(name for name, _annotation in declarations)
    if not declared_fields or len(set(declared_fields)) != len(declared_fields):
        violations.append("declaration authority is invalid")
    if (
        not protected_fields
        or len(set(protected_fields)) != len(protected_fields)
        or any(field not in declared_fields for field in protected_fields)
    ):
        violations.append("protected-field authority is invalid")
    if target.bases or target.keywords or target.type_params:
        violations.append("class must inherit directly from object")
    accepted_options = (
        {"frozen": True, "slots": True, "repr": False},
        {"frozen": True, "slots": True, "repr": False, "eq": True},
    )
    if _credential_dataclass_options(target) not in accepted_options:
        violations.append("dataclass options differ from the opaque posture")
    projection = _credential_direct_class_projection(
        target,
        declarations,
        methods,
    )
    if projection is None:
        violations.append("direct class-body shape differs from the exact contract")
        annotation_resolution_symbols = frozenset()
    else:
        annotation_resolution_symbols = _credential_annotation_resolution_symbols(
            projection.declarations
        )
    events = _credential_class_namespace_events(
        tree,
        target,
        annotation_resolution_symbols,
    )
    if any(event.kind == "unbounded" for event in events):
        violations.append("class namespace binding analysis is unbounded")
    if any(
        event.kind in {"bind", "delete"}
        and event.name in _CREDENTIAL_DISPLAY_OR_HASH_MEMBERS
        for event in events
    ):
        violations.append("class defines forbidden display or hash members")
    if any(
        event.kind in {"bind", "delete"} and event.name == "__annotations__"
        for event in events
    ):
        violations.append("class defines explicit annotation-map authority")
    if any(isinstance(event.node, ast.ClassDef) for event in events):
        violations.append("nested class construction is prohibited")
    if projection is not None:
        collected_declarations = (
            _credential_collected_simple_declaration_nodes(events)
        )
        if len(collected_declarations) != len(projection.declarations) or any(
            observed is not approved
            for observed, approved in zip(
                collected_declarations,
                projection.declarations,
                strict=True,
            )
        ):
            violations.append(
                "collected annotated declarations differ from direct authority"
            )
        for field_name, declaration in zip(
            declared_fields,
            projection.declarations,
            strict=True,
        ):
            field_events = tuple(
                event
                for event in events
                if event.kind in {"bind", "delete"} and event.name == field_name
            )
            if not (
                len(field_events) == 1
                and field_events[0].kind == "bind"
                and field_events[0].node is declaration
            ):
                violations.append(
                    "declared field bindings differ from direct authority"
                )
                break
        if any(
            event.kind in {"bind", "delete"}
            and event.name in annotation_resolution_symbols
            for event in events
        ):
            violations.append("annotation-resolution symbols are rebound")
        for method, body_authority in projection.methods:
            if body_authority == "exact-equality":
                violations.extend(
                    _credential_eq_violations(method, declared_fields)
                )
    equality_events = [event for event in events if event.name == "__eq__"]
    if (
        len(equality_events) != 1
        or equality_events[0].kind != "bind"
        or not equality_events[0].direct
        or not isinstance(equality_events[0].node, ast.FunctionDef)
    ):
        violations.append("class must define exactly one synchronous __eq__")
    return [prefix + violation for violation in sorted(set(violations))]


def _check_credential_diagnostic_carriers(
    snapshot: PythonSourceSnapshotV1,
    trees: collections.abc.Mapping[str, ast.Module],
) -> list[str]:
    failures = []
    for (
        relative,
        class_name,
        protected_fields,
        declarations,
        methods,
    ) in _CREDENTIAL_DIAGNOSTIC_CARRIERS:
        unit = snapshot.modules_by_relative_path.get(relative)
        if unit is None:
            failures.append(
                f"{relative}:{class_name}: authenticated module is missing"
            )
            continue
        tree = trees.get(unit.module_name)
        if tree is None:
            failures.append(
                f"{relative}:{class_name}: detached AST is missing"
            )
            continue
        failures.extend(
            f"{relative}:{violation}"
            for violation in _credential_diagnostic_carrier_violations(
                tree,
                class_name,
                protected_fields,
                declarations,
                methods,
            )
        )
    return sorted(set(failures))


def _statement_line(
    function: ast.FunctionDef,
    source: str,
) -> int | None:
    expected = _statement_shape(source)
    matches = [
        node.lineno
        for node in ast.walk(function)
        if isinstance(node, ast.stmt)
        and ast.dump(node, include_attributes=False) == expected
    ]
    return matches[0] if len(matches) == 1 else None


def _statement_shape(source: str) -> str:
    return ast.dump(ast.parse(source).body[0], include_attributes=False)


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _ordered_call_lines(
    function: ast.FunctionDef,
    names: tuple[str, ...],
) -> tuple[int, ...] | None:
    observed = []
    for name in names:
        lines = [
            node.lineno
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and _call_name(node) == name
        ]
        if len(lines) != 1:
            return None
        observed.append(lines[0])
    return tuple(observed)


def _fixed_integer(tree: ast.Module, name: str) -> int | None:
    values = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
        and isinstance(node.value, ast.Constant)
        and type(node.value.value) is int
    ]
    return values[0] if len(values) == 1 else None


def _private_result_class_violations(tree: ast.Module) -> list[str]:
    violations = []
    public = "ClosedSecurityAuditBreakGlassExport"
    private = "_ClosedSecurityAuditBreakGlassExport"
    class_names = [
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
    ]
    if public in class_names:
        violations.append("public closed-result class remains")
    if _top_level_class_fields(tree, private) != ("operation_id", "page_bytes"):
        violations.append("private closed-result class inventory differs")
    if _top_level_dataclass_options(tree, private) != {
        "frozen": True,
        "slots": True,
        "repr": False,
    }:
        violations.append("private closed-result posture differs")
    exports = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        if isinstance(node.targets[0], ast.Name) and node.targets[0].id == "__all__":
            try:
                exports.append(ast.literal_eval(node.value))
            except (TypeError, ValueError):
                exports.append(None)
    if (
        len(exports) != 1
        or type(exports[0]) is not tuple
        or any(name in exports[0] for name in (public, private))
    ):
        violations.append("closed-result export surface differs")
    return violations


def _private_result_internal_reference_violations(
    tree: ast.Module,
) -> list[str]:
    private = "_ClosedSecurityAuditBreakGlassExport"
    parents = {
        id(child): parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    annotations: set[int] = set()
    for node in ast.walk(tree):
        values: tuple[ast.expr | None, ...] = ()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            values = (
                *(argument.annotation for argument in node.args.args),
                *(argument.annotation for argument in node.args.kwonlyargs),
                node.returns,
            )
        elif isinstance(node, ast.AnnAssign):
            values = (node.annotation,)
        for value in values:
            if value is not None:
                annotations.update(id(member) for member in ast.walk(value))
    references = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == private:
            references.append(node.lineno)
            continue
        if isinstance(node, ast.ImportFrom) and any(
            alias.name == private for alias in node.names
        ):
            references.append(node.lineno)
            continue
        if not isinstance(node, ast.Name) or node.id != private:
            continue
        parent = parents.get(id(node))
        if id(node) in annotations:
            continue
        if isinstance(parent, ast.Call) and parent.func is node:
            continue
        references.append(node.lineno)
    return (
        ["private closed-result direct reference inventory differs"]
        if references
        else []
    )


def _private_result_construction_violations(tree: ast.Module) -> list[str]:
    private = "_ClosedSecurityAuditBreakGlassExport"
    functions = [
        node for node in tree.body if isinstance(node, ast.FunctionDef)
    ]
    constructions = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == private
        ):
            continue
        owners = [
            function.name
            for function in functions
            if any(member is node for member in ast.walk(function))
        ]
        constructions.append(
            (owners[0] if len(owners) == 1 else None, node.lineno)
        )
    if len(constructions) != 1 or constructions[0][0] != "_export_and_close":
        return ["private closed-result construction inventory differs"]
    function = _top_level_function(tree, "_export_and_close")
    if function is None:
        return ["private closed-result construction owner is absent"]
    terminal_sources = (
        """_close_login(
    dependencies,
    preflight.routes.admin,
    preflight.store_migration_execution_id,
    expected_role,
)""",
        """if interrupted is not None:
    raise interrupted""",
        """if export_failed or exported is None:
    raise _ConsumedFailure()""",
        """return _ClosedSecurityAuditBreakGlassExport(
    operation_id=approval.operation_id,
    page_bytes=exported.page_bytes,
)""",
    )
    expected_tail = tuple(_statement_shape(source) for source in terminal_sources)
    observed_tail = tuple(
        ast.dump(statement, include_attributes=False)
        for statement in function.body[-4:]
    )
    close_lines = _ordered_call_lines(function, ("_close_login",))
    returns = [
        node for node in ast.walk(function) if isinstance(node, ast.Return)
    ]
    has_yield = any(
        isinstance(node, (ast.Yield, ast.YieldFrom)) for node in ast.walk(function)
    )
    if (
        len(function.body) < 4
        or len(returns) != 1
        or returns[0] is not function.body[-1]
        or has_yield
        or observed_tail != expected_tail
        or close_lines != (function.body[-4].lineno,)
    ):
        return ["private result is not constructed after closure and validation"]
    return []


def _private_result_reference_violations(
    trees: collections.abc.Mapping[str, ast.Module],
    lifecycle_module: str,
) -> list[str]:
    symbols = {
        "ClosedSecurityAuditBreakGlassExport",
        "_ClosedSecurityAuditBreakGlassExport",
    }
    violations = []
    for module, tree in trees.items():
        if module == lifecycle_module:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names = {alias.name for alias in node.names}
                found = sorted(names & symbols)
                if found:
                    violations.append(
                        f"{module}:{node.lineno}: prohibited result import {found!r}"
                    )
            elif isinstance(node, ast.Attribute) and node.attr in symbols:
                violations.append(
                    f"{module}:{node.lineno}: prohibited result attribute {node.attr!r}"
                )
    return sorted(set(violations))


def _break_glass_deadline_violations(tree: ast.Module) -> list[str]:
    violations = []
    constants = {
        "_MAX_AUTHORITY_DATABASE_DIVERGENCE_GROWTH_US": 1_000_000,
        "_MAX_PASSWORD_AUTHORITY_ADVANCE_US": 61_000_000,
        "_POSTGRES_TIMESTAMP_QUANTUM_US": 1,
    }
    for name, value in constants.items():
        if _fixed_integer(tree, name) != value:
            violations.append(f"fixed deadline reserve {name} differs")
    clock = _top_level_function(tree, "_clock_high_water")
    clock_statements = (
        "row = _exact_row(connection.execute(_CLOCK_SQL), 2)",
        "if (type(row[0]) is not int "
        "or not 0 <= row[0] <= _MAX_UNIX_MICROSECONDS "
        "or row[1] is not False):\n    raise ValueError",
        "return cast(int, row[0])",
    )
    if clock is None or any(
        _statement_line(clock, statement) is None
        for statement in clock_statements
    ):
        violations.append("live database clock acceptance differs")
    derived = _top_level_function(tree, "_derived_expected_role")
    if derived is None:
        return violations + ["derived expected-role helper is absent"]
    statements = (
        "safe_remaining_us = (current.approval.valid_until_us "
        "- max(current.authority_now_us, database_now_us) "
        "- _MAX_AUTHORITY_DATABASE_DIVERGENCE_GROWTH_US "
        "- _MAX_PASSWORD_AUTHORITY_ADVANCE_US "
        "- _POSTGRES_TIMESTAMP_QUANTUM_US)",
        "if safe_remaining_us <= 0:\n    raise ValueError",
        "return _ExpectedRole(_expiry(database_now_us + safe_remaining_us), "
        "password_verifier)",
    )
    if any(_statement_line(derived, statement) is None for statement in statements):
        violations.append("database deadline formula or refusal differs")
    create = _top_level_function(tree, "_create_login")
    if create is None:
        return violations + ["LOGIN creation helper is absent"]
    ordered = _ordered_call_lines(
        create,
        (
            "_clock_high_water",
            "_advance_current_approval",
            "_derived_expected_role",
            "_configure_login",
        ),
    )
    if ordered is None or tuple(sorted(ordered)) != ordered:
        violations.append("LOGIN deadline order is not H3 then A3 then derive then SQL")
    exact_create = (
        "database_now_us = _clock_high_water(connection)",
        "current = _advance_current_approval(dependencies, current)",
        "expected_role = _derived_expected_role("
        "database_now_us, current, password_verifier)",
        "_configure_login(connection, expected_role)",
    )
    if any(_statement_line(create, statement) is None for statement in exact_create):
        violations.append("LOGIN deadline provenance differs")
    return violations


def _break_glass_carrier_violations(tree: ast.Module) -> list[str]:
    violations = []
    if _top_level_class_fields(tree, "_CurrentApprovalCarrier") != (
        "approval", "authority_now_us"
    ):
        violations.append("current-approval carrier differs")
    if _top_level_class_fields(tree, "_LoginCreationOutcome") != (
        "expected_role", "commit_acknowledged"
    ):
        violations.append("LOGIN creation outcome differs")
    for name in ("_CurrentApprovalCarrier", "_LoginCreationOutcome"):
        if _top_level_dataclass_options(tree, name) != {
            "frozen": True,
            "slots": True,
        }:
            violations.append(f"{name} immutable posture differs")
    verified = _top_level_function(tree, "_verified_approval")
    advance = _top_level_function(tree, "_advance_current_approval")
    if verified is None or advance is None:
        return violations + ["authority currentness helper inventory differs"]
    required_verified = (
        "authority_now_us = _authority_time_us(dependencies)",
        "verifier_now_us = max(authority_now_us, preflight.database_high_water_us)",
        "return _CurrentApprovalCarrier(approval, authority_now_us)",
    )
    required_advance = (
        "authority_now_us = _authority_time_us(dependencies)",
        "if authority_now_us < current.authority_now_us:\n    raise ValueError",
        "return _CurrentApprovalCarrier(current.approval, authority_now_us)",
    )
    if any(_statement_line(verified, item) is None for item in required_verified):
        violations.append("verified approval does not retain raw A1")
    if any(_statement_line(advance, item) is None for item in required_advance):
        violations.append("current approval does not reject raw regression")
    execute = _top_level_function(tree, "_execute")
    if execute is None:
        return violations + ["lifecycle executor is absent"]
    ordered = _ordered_call_lines(
        execute,
        (
            "_verified_approval",
            "_advance_current_approval",
            "_consume",
            "_create_or_resolve_login",
            "_export_and_close",
        ),
    )
    if ordered is None or tuple(sorted(ordered)) != ordered:
        violations.append("lifecycle authority and closure order differs")
    if _statement_line(execute, "_consume(dependencies, routes.control, current)") is None:
        violations.append("consumption does not use accepted A2 carrier")
    resolve = _top_level_function(tree, "_resolve_unacknowledged_login")
    create_or_resolve = _top_level_function(tree, "_create_or_resolve_login")
    if resolve is None or create_or_resolve is None:
        return violations + ["LOGIN ambiguity helper inventory differs"]
    if _statement_line(resolve, "expected_role = outcome.expected_role") is None:
        violations.append("LOGIN ambiguity discards derived expected role")
    if any(
        isinstance(node, ast.Call) and _call_name(node) == "_derived_expected_role"
        for node in ast.walk(resolve)
    ):
        violations.append("LOGIN ambiguity recomputes the derived role")
    attributes = {
        node.attr
        for node in ast.walk(create_or_resolve)
        if isinstance(node, ast.Attribute)
    }
    if not {"commit_acknowledged", "expected_role"} <= attributes:
        violations.append("LOGIN creation outcome is not consumed exactly")
    return violations


def _security_audit_break_glass_violations(tree: ast.Module) -> list[str]:
    violations = []
    violations.extend(_private_result_class_violations(tree))
    violations.extend(_private_result_internal_reference_violations(tree))
    violations.extend(_private_result_construction_violations(tree))
    violations.extend(_break_glass_deadline_violations(tree))
    violations.extend(_break_glass_carrier_violations(tree))
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "SecurityAuditBreakGlassRunner"
    ]
    if len(classes) != 1:
        return ["production runner class inventory differs"]
    methods = {
        node.name: node
        for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    expected = {
        "__init__": ("self", "observer_public_key"),
        "run": (
            "self",
            "secret_carrier",
            "authority_receipt_bytes",
            "approval_bundle_bytes",
        ),
        "close_expired": ("self", "secret_carrier"),
    }
    for name, arguments in expected.items():
        method = methods.get(name)
        if method is None:
            violations.append(f"production {name} method is absent")
            continue
        observed = tuple(
            argument.arg
            for argument in (
                *method.args.posonlyargs,
                *method.args.args,
                *method.args.kwonlyargs,
            )
        )
        if (
            observed != arguments
            or method.args.vararg is not None
            or method.args.kwarg is not None
            or method.args.defaults
            or method.args.kw_defaults
        ):
            violations.append(f"production {name} dependency surface differs")
        for node in ast.walk(method):
            if isinstance(node, ast.Name) and node.id == \
                    "_run_security_audit_break_glass_for_testing":
                violations.append(
                    f"production {name} reaches the private test seam"
                )
    run = methods.get("run")
    if run is not None:
        attributes = {
            node.attr
            for node in ast.walk(run)
            if isinstance(node, ast.Attribute)
        }
        names = {
            node.id for node in ast.walk(run) if isinstance(node, ast.Name)
        }
        if "time_ns" not in attributes:
            violations.append("production run does not bind direct authority time")
        if "token_bytes" not in attributes:
            violations.append("production run does not bind direct randomness")
        if "SecurityAuditExportRunner" not in names:
            violations.append("production run does not bind the fixed export runner")
    forbidden_names = {
        "boto3",
        "google",
        "kms_v1",
        "os",
        "subprocess",
        "threading",
        "open",
        "print",
    }
    for node in ast.walk(tree):
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        if name in forbidden_names:
            violations.append(
                f"{node.lineno}: prohibited lifecycle surface {name!r}"
            )
    private_seams = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_run_security_audit_break_glass_for_testing"
    ]
    if len(private_seams) != 1:
        violations.append("private deterministic lifecycle seam differs")
    return sorted(set(violations))


def _check_security_audit_break_glass_surface(
    snapshot: PythonSourceSnapshotV1,
    trees: collections.abc.Mapping[str, ast.Module],
) -> list[str]:
    relative = "deployment/postgresql/security_audit_break_glass.py"
    module = snapshot.modules_by_relative_path[relative].module_name
    failures = [
        f"{relative}:{violation}"
        for violation in _security_audit_break_glass_violations(trees[module])
    ]
    failures.extend(_private_result_reference_violations(trees, module))
    return sorted(set(failures))


def _authority_time_payload_is_exact(tree: ast.Module) -> bool:
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_authority_payload"
    ]
    if len(functions) != 1:
        return False
    for node in ast.walk(functions[0]):
        if not isinstance(node, ast.Dict):
            continue
        members = {
            key.value: value
            for key, value in zip(node.keys, node.values, strict=True)
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        observed = members.get("observedAtUnixMicroseconds")
        expires = members.get("expiresAtUnixMicroseconds")
        if (
            isinstance(observed, ast.Name)
            and observed.id == "now_us"
            and isinstance(expires, ast.BinOp)
            and isinstance(expires.op, ast.Add)
            and isinstance(expires.left, ast.Name)
            and expires.left.id == "now_us"
            and isinstance(expires.right, ast.Name)
            and expires.right.id == "_RECEIPT_LIFETIME_MICROSECONDS"
        ):
            return True
    return False


def _authority_kms_call_violations(tree: ast.Module) -> list[str]:
    violations = []
    client_method_calls = []
    signing_calls = []
    request_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and (
                (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "client"
                )
                or (
                    isinstance(node.func.value, ast.Attribute)
                    and isinstance(node.func.value.value, ast.Name)
                    and node.func.value.value.id == "self"
                    and node.func.value.attr == "_client"
                )
            )
        ):
            client_method_calls.append(node)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "asymmetric_sign":
            signing_calls.append(node)
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "kms_v1"
            and node.func.attr == "AsymmetricSignRequest"
        ):
            request_calls.append(node)
    if any(call.func.attr != "asymmetric_sign" for call in client_method_calls):
        violations.append("constructor client calls a method other than asymmetric_sign")
    if len(signing_calls) != 1 or signing_calls[0] not in client_method_calls:
        violations.append("exactly one direct client asymmetric_sign call is required")
    else:
        call = signing_calls[0]
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        if call.args or set(keywords) != {"request", "retry", "timeout"}:
            violations.append("asymmetric_sign call shape differs")
        elif (
            not isinstance(keywords["request"], ast.Name)
            or keywords["request"].id != "request"
            or not isinstance(keywords["retry"], ast.Constant)
            or keywords["retry"].value is not None
            or not isinstance(keywords["timeout"], ast.Name)
            or keywords["timeout"].id != "_KMS_RPC_TIMEOUT_SECONDS"
        ):
            violations.append("asymmetric_sign retry or timeout differs")
    if len(request_calls) != 1:
        violations.append("exactly one AsymmetricSignRequest constructor is required")
    else:
        request = request_calls[0]
        keywords = {keyword.arg: keyword.value for keyword in request.keywords}
        if request.args or set(keywords) != {"name", "data", "data_crc32c"}:
            violations.append("AsymmetricSignRequest field set differs")
        elif (
            not isinstance(keywords["name"], ast.Name)
            or keywords["name"].id != "resource"
            or not isinstance(keywords["data"], ast.Name)
            or keywords["data"].id != "signing_input"
            or not isinstance(keywords["data_crc32c"], ast.Call)
            or not isinstance(keywords["data_crc32c"].func, ast.Name)
            or keywords["data_crc32c"].func.id != "_crc32c"
            or len(keywords["data_crc32c"].args) != 1
            or not isinstance(keywords["data_crc32c"].args[0], ast.Name)
            or keywords["data_crc32c"].args[0].id != "signing_input"
            or keywords["data_crc32c"].keywords
        ):
            violations.append("AsymmetricSignRequest value authority differs")
    timeout_assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "_KMS_RPC_TIMEOUT_SECONDS"
    ]
    if (
        len(timeout_assignments) != 1
        or not isinstance(timeout_assignments[0].value, ast.Constant)
        or type(timeout_assignments[0].value.value) is not float
        or timeout_assignments[0].value.value != 5.0
    ):
        violations.append("KMS RPC timeout constant differs")
    return violations


def _security_audit_authority_surface_violations(
    tree: ast.Module,
) -> list[str]:
    violations = []
    import_statements = []
    refusal_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            violations.append(f"{node.lineno}: whole-module import is prohibited")
        elif isinstance(node, ast.ImportFrom):
            statement = _normalized_import_statement(node)
            import_statements.append(statement)
            if statement not in SECURITY_AUDIT_AUTHORITY_IMPORT_STATEMENTS:
                violations.append(
                    f"{node.lineno}: import statement is outside exact allowlist"
                )
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        if name in SECURITY_AUDIT_AUTHORITY_FORBIDDEN_NAMES:
            violations.append(
                f"{node.lineno}: prohibited authority surface {name!r}"
            )
        if (
            isinstance(node, ast.Name)
            and node.id == "now_us"
            and isinstance(node.ctx, (ast.Store, ast.Del))
        ):
            violations.append(f"{node.lineno}: caller-owned now_us is overwritten")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "SecurityAuditAuthorityReceiptRefused"
        ):
            refusal_calls.append(node)
    if (
        len(import_statements) != len(SECURITY_AUDIT_AUTHORITY_IMPORT_STATEMENTS)
        or frozenset(import_statements)
        != SECURITY_AUDIT_AUTHORITY_IMPORT_STATEMENTS
    ):
        violations.append("exact import statement set is incomplete or duplicated")
    if len(refusal_calls) != 2 or any(
        call.args or call.keywords for call in refusal_calls
    ):
        violations.append("fixed refusal construction differs")
    if not _authority_time_payload_is_exact(tree):
        violations.append("authority payload does not use exact caller-owned time")
    violations.extend(_authority_kms_call_violations(tree))
    return sorted(set(violations))


def _check_security_audit_authority_surface(
    snapshot: PythonSourceSnapshotV1,
    trees: collections.abc.Mapping[str, ast.Module],
) -> list[str]:
    relative = "deployment/postgresql/security_audit_authority.py"
    module = snapshot.modules_by_relative_path[relative].module_name
    return [
        f"{relative}:{violation}"
        for violation in _security_audit_authority_surface_violations(
            trees[module]
        )
    ]


def _observer_root_literal(
    tree: ast.Module,
    name: str,
) -> object:
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
    ]
    if len(assignments) != 1:
        raise ValueError
    return ast.literal_eval(assignments[0].value)


def _observer_root_function(
    tree: ast.Module,
    name: str,
) -> ast.FunctionDef | None:
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    return functions[0] if len(functions) == 1 else None


def _observer_root_rpc_call_violations(tree: ast.Module) -> list[str]:
    violations = []
    expected = {
        "get_crypto_key": ("_crypto_key", "client"),
        "get_crypto_key_version": ("_crypto_key_version", "client"),
        "get_public_key": ("_public_key", "client"),
        "asymmetric_sign": ("_probe", "signer"),
    }
    for method, (function_name, receiver) in expected.items():
        function = _observer_root_function(tree, function_name)
        calls = [] if function is None else [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == receiver
            and node.func.attr == method
        ]
        all_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == method
        ]
        if len(calls) != 1 or calls != all_calls:
            violations.append(f"exactly one direct {method} call is required")
            continue
        call = calls[0]
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        if call.args or set(keywords) != {"request", "retry", "timeout"}:
            violations.append(f"{method} call shape differs")
        elif (
            not isinstance(keywords["request"], ast.Name)
            or keywords["request"].id != "request"
            or not isinstance(keywords["retry"], ast.Constant)
            or keywords["retry"].value is not None
            or not isinstance(keywords["timeout"], ast.Name)
            or keywords["timeout"].id != "_KMS_TIMEOUT"
        ):
            violations.append(f"{method} retry or timeout differs")
    return violations


def _observer_root_request_violations(tree: ast.Module) -> list[str]:
    violations = []
    expected = {
        "GetCryptoKeyRequest": {"name"},
        "GetCryptoKeyVersionRequest": {"name"},
        "GetPublicKeyRequest": {"name", "public_key_format"},
        "AsymmetricSignRequest": {"data", "data_crc32c", "name"},
    }
    for constructor, fields in expected.items():
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "kms_v1"
            and node.func.attr == constructor
        ]
        if len(calls) != 1:
            violations.append(f"exactly one {constructor} constructor is required")
            continue
        call = calls[0]
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        if call.args or set(keywords) != fields:
            violations.append(f"{constructor} field set differs")
            continue
        if constructor == "AsymmetricSignRequest" and (
            not isinstance(keywords["data"], ast.Name)
            or keywords["data"].id != "_PROBE"
            or not isinstance(keywords["data_crc32c"], ast.Call)
            or not isinstance(keywords["data_crc32c"].func, ast.Name)
            or keywords["data_crc32c"].func.id != "_crc32c"
            or len(keywords["data_crc32c"].args) != 1
            or not isinstance(keywords["data_crc32c"].args[0], ast.Name)
            or keywords["data_crc32c"].args[0].id != "_PROBE"
        ):
            violations.append("AsymmetricSignRequest probe authority differs")
        if constructor == "GetPublicKeyRequest" and not (
            isinstance(keywords["public_key_format"], ast.Attribute)
            and keywords["public_key_format"].attr == "DER"
        ):
            violations.append("GetPublicKeyRequest does not explicitly require DER")
    return violations


def _observer_root_http_call_violations(tree: ast.Module) -> list[str]:
    violations = []
    expected = {
        "get": ("_role", {"allow_redirects", "headers", "stream", "timeout"}),
        "post": (
            "_access",
            {"allow_redirects", "data", "headers", "stream", "timeout"},
        ),
    }
    for method, (function_name, keyword_names) in expected.items():
        function = _observer_root_function(tree, function_name)
        calls = [] if function is None else [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "session"
            and node.func.attr == method
        ]
        if len(calls) != 1:
            violations.append(f"exactly one direct evidence-session {method} call is required")
            continue
        call = calls[0]
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        if len(call.args) != 1 or set(keywords) != keyword_names:
            violations.append(f"evidence-session {method} call shape differs")
        elif (
            not isinstance(keywords["allow_redirects"], ast.Constant)
            or keywords["allow_redirects"].value is not False
            or not isinstance(keywords["stream"], ast.Constant)
            or keywords["stream"].value is not True
            or not isinstance(keywords["timeout"], ast.Name)
            or keywords["timeout"].id != "_HTTP_TIMEOUT"
        ):
            violations.append(f"evidence-session {method} bounds differ")
    strings = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    iam = "https://iam.googleapis.com/v1/"
    troubleshooter = (
        "https://policytroubleshooter.googleapis.com/v3beta/iam:troubleshoot"
    )
    if strings.count(iam) != 1 or strings.count(troubleshooter) != 1:
        violations.append("exact evidence endpoints differ")
    if any(
        "policytroubleshooter.googleapis.com/" in value
        and value != troubleshooter
        for value in strings
    ):
        violations.append("alternate Policy Troubleshooter endpoint is present")
    if any("testIamPermissions" in value for value in strings):
        violations.append("testIamPermissions evidence path is present")
    return violations


def _observer_root_clock_violations(tree: ast.Module) -> list[str]:
    function = _observer_root_function(tree, "_admit")
    if function is None:
        return ["exact _admit transition is missing"]
    calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "clock"
    ]
    all_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "clock"
    ]
    if len(calls) != 2 or calls != all_calls or any(
        call.args or call.keywords for call in calls
    ):
        return ["exactly two zero-argument supplied-clock calls are required"]
    return []


def _observer_root_ast_sha256(tree: ast.Module) -> str:
    normalized = ast.dump(
        tree,
        annotate_fields=True,
        include_attributes=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(normalized).hexdigest()}"


def _observer_root_source_shape_violations(
    tree: ast.Module,
    source_text: str,
) -> list[str]:
    violations = []
    lines = source_text.splitlines()
    budget = MODULE_BUDGETS[SECURITY_AUDIT_OBSERVER_ROOT_RELATIVE_PATH]
    if len(lines) != budget:
        violations.append(
            f"finished physical line count {len(lines)} differs from exact budget "
            f"{budget}"
        )
    if budget > SECURITY_AUDIT_OBSERVER_ROOT_MAX_LINES:
        violations.append(
            f"exact budget {budget} exceeds approved ceiling "
            f"{SECURITY_AUDIT_OBSERVER_ROOT_MAX_LINES}"
        )
    for line_number, line in enumerate(lines, start=1):
        if len(line) > SECURITY_AUDIT_OBSERVER_ROOT_MAX_PHYSICAL_LINE_LENGTH:
            violations.append(
                f"{line_number}: physical line length {len(line)} exceeds "
                f"{SECURITY_AUDIT_OBSERVER_ROOT_MAX_PHYSICAL_LINE_LENGTH}"
            )
    try:
        tokens = tuple(tokenize.generate_tokens(io.StringIO(source_text).readline))
    except (IndentationError, tokenize.TokenError) as exc:
        violations.append(f"source tokenization failed: {type(exc).__name__}")
        tokens = ()
    for token in tokens:
        if token.type == tokenize.COMMENT and "noqa" in token.string.casefold():
            violations.append(f"{token.start[0]}: noqa suppression is prohibited")
        if token.type == tokenize.OP and token.string == ";":
            violations.append(
                f"{token.start[0]}: semicolon statement joining is prohibited"
            )
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            suite = getattr(node, field, None)
            if not isinstance(suite, list) or not suite:
                continue
            first = suite[0]
            line_number = getattr(first, "lineno", 0)
            column = getattr(first, "col_offset", 0)
            if (
                1 <= line_number <= len(lines)
                and lines[line_number - 1][:column].rstrip().endswith(":")
            ):
                violations.append(
                    f"{line_number}: one-line compound-statement body is prohibited"
                )
    observed_ast = _observer_root_ast_sha256(tree)
    if observed_ast != SECURITY_AUDIT_OBSERVER_ROOT_REFERENCE_AST_SHA256:
        violations.append(
            "parsed AST differs from immutable observer-root reference head "
            f"{SECURITY_AUDIT_OBSERVER_ROOT_REFERENCE_HEAD}"
        )
    return sorted(set(violations))


def _observer_root_ruff_python() -> str | None:
    try:
        current_has_ruff = importlib.util.find_spec("ruff") is not None
    except (ImportError, ValueError):
        current_has_ruff = False
    if current_has_ruff:
        return sys.executable
    hosted_tool_python = ROOT / ".review-tools-venv" / "bin" / "python"
    if hosted_tool_python.is_file():
        return str(hosted_tool_python)
    return None


def _observer_root_formatter_violations() -> list[str]:
    python = _observer_root_ruff_python()
    if python is None:
        return ["repository-pinned Ruff formatter is unavailable"]
    environment = dict(os.environ)
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    try:
        version = subprocess.run(
            [python, "-m", "ruff", "--version"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        formatted = subprocess.run(
            [
                python,
                "-m",
                "ruff",
                "format",
                "--check",
                SECURITY_AUDIT_OBSERVER_ROOT_RELATIVE_PATH,
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"repository-pinned Ruff formatter failed: {type(exc).__name__}"]
    violations = []
    if version.returncode != 0 or version.stdout.strip() != "ruff 0.15.5":
        violations.append("repository-pinned Ruff version is not exactly 0.15.5")
    if formatted.returncode != 0:
        violations.append("repository-pinned Ruff format check failed")
    return violations


def _security_audit_observer_root_surface_violations(
    tree: ast.Module,
    source_text: str | None = None,
) -> list[str]:
    violations = []
    imports = []
    refusal_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            violations.append(f"{node.lineno}: whole-module import is prohibited")
        elif isinstance(node, ast.ImportFrom):
            statement = _normalized_import_statement(node)
            imports.append(statement)
            if statement not in SECURITY_AUDIT_OBSERVER_ROOT_IMPORT_STATEMENTS:
                violations.append(
                    f"{node.lineno}: import statement is outside exact allowlist"
                )
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        if name in SECURITY_AUDIT_OBSERVER_ROOT_FORBIDDEN_NAMES:
            violations.append(f"{node.lineno}: prohibited observer-root surface {name!r}")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "SecurityAuditObserverRootAdmissionRefused"
        ):
            refusal_calls.append(node)
    if (
        len(imports) != len(SECURITY_AUDIT_OBSERVER_ROOT_IMPORT_STATEMENTS)
        or frozenset(imports) != SECURITY_AUDIT_OBSERVER_ROOT_IMPORT_STATEMENTS
    ):
        violations.append("exact import statement set is incomplete or duplicated")
    if len(refusal_calls) != 1 or refusal_calls[0].args or refusal_calls[0].keywords:
        violations.append("fixed observer-root refusal construction differs")
    expected_literals = {
        "_MANIFEST_SCHEMA": (
            "ofarm.security-audit-observer-root-admission-manifest.v1"
        ),
        "_ATTESTATION_DOMAIN": (
            b"OFARM2_SECURITY_AUDIT_OBSERVER_ROOT_ATTESTATION_V1\x00"
        ),
        "_EVIDENCE_DOMAIN": (
            b"OFARM2_SECURITY_AUDIT_OBSERVER_ROOT_EVIDENCE_V1\x00"
        ),
        "_KMS_TIMEOUT": 5.0,
        "_HTTP_TIMEOUT": 5.0,
        "_MAX_SPAN_US": 180_000_000,
        "_LIFETIME_US": 30_000_000,
        "_MAX_UNIX_US": 9_223_372_036_854_775_807,
        "_MAX_MANIFEST": 8_192,
        "_MAX_HTTP": 1_048_576,
        "_MAX_ATTESTATION": 262_144,
        "_MAX_CERTIFICATES": 16,
        "_MAX_CERTIFICATE": 32_768,
        "_PROBE": SECURITY_AUDIT_OBSERVER_ROOT_PROBE,
        "__all__": SECURITY_AUDIT_OBSERVER_ROOT_PUBLIC_SURFACE,
    }
    for name, expected in expected_literals.items():
        try:
            observed = _observer_root_literal(tree, name)
        except (ValueError, TypeError):
            observed = object()
        if type(observed) is not type(expected) or observed != expected:
            violations.append(f"{name} literal differs")
    if len(SECURITY_AUDIT_OBSERVER_ROOT_PROBE) != 50:
        violations.append("architecture-owned observer-root probe length differs")
    if any(
        isinstance(node, ast.If)
        and any(
            isinstance(member, ast.Name) and member.id == "__name__"
            for member in ast.walk(node.test)
        )
        for node in ast.walk(tree)
    ):
        violations.append("executable module entry point is prohibited")
    violations.extend(_observer_root_rpc_call_violations(tree))
    violations.extend(_observer_root_request_violations(tree))
    violations.extend(_observer_root_http_call_violations(tree))
    violations.extend(_observer_root_clock_violations(tree))
    if source_text is not None:
        violations.extend(_observer_root_source_shape_violations(tree, source_text))
    return sorted(set(violations))


def _check_security_audit_observer_root_surface(
    snapshot: PythonSourceSnapshotV1,
    trees: collections.abc.Mapping[str, ast.Module],
) -> list[str]:
    relative = SECURITY_AUDIT_OBSERVER_ROOT_RELATIVE_PATH
    unit = snapshot.modules_by_relative_path[relative]
    module = unit.module_name
    violations = _security_audit_observer_root_surface_violations(
        trees[module],
        unit.source_text,
    )
    violations.extend(_observer_root_formatter_violations())
    return [
        f"{relative}:{violation}"
        for violation in sorted(set(violations))
    ]


def main() -> int:
    try:
        snapshot = build_python_source_snapshot(ROOT)
        trees = _snapshot_trees(snapshot)
    except PythonSourceSnapshotRefusal as exc:
        relative = f" ({exc.relative_path})" if exc.relative_path else ""
        print(f"FAIL Python source snapshot refused: {exc.code.value}{relative}")
        return 1
    try:
        execution_closures = _derive_import_execution_closures(
            snapshot,
            trees,
        )
    except _ImportExecutionFailure as exc:
        print(f"FAIL Python import-execution closure refused: {exc}")
        return 1
    failures = _check_import_firewall(
        snapshot,
        trees,
        execution_closures,
    )
    failures.extend(_check_provider_import_policy(snapshot, trees))
    failures.extend(
        _check_tenant_uow_architecture(
            snapshot,
            trees,
            execution_closures,
        )
    )
    failures.extend(_check_direct_import_bounds(snapshot))
    failures.extend(_check_security_audit_gap_surface(snapshot, trees))
    failures.extend(_check_security_audit_approval_surface(snapshot, trees))
    failures.extend(_check_security_audit_break_glass_surface(snapshot, trees))
    failures.extend(_check_security_audit_authority_surface(snapshot, trees))
    failures.extend(_check_security_audit_observer_root_surface(snapshot, trees))
    failures.extend(_check_credential_diagnostic_carriers(snapshot, trees))
    for relative, budget in MODULE_BUDGETS.items():
        failures.extend(_check_production(snapshot, trees, relative, budget))
    for relative, budget in COMMAND_MODULE_BUDGETS.items():
        failures.extend(
            _check_production(
                snapshot,
                trees,
                relative,
                budget,
                allow_environment=True,
            )
        )
    for name, (budget, relatives) in GROUP_BUDGETS.items():
        total = sum(
            _line_count(snapshot.modules_by_relative_path[relative])
            for relative in relatives
        )
        if total > budget:
            failures.append(
                f"{name}: {total} production lines exceeds group budget {budget}"
            )
    test_paths = {
        relative
        for pattern in TEST_GLOBS
        for relative in snapshot.modules_by_relative_path
        if pathlib.PurePosixPath(relative).match(pattern)
    }
    for relative in sorted(test_paths):
        line_count = _line_count(snapshot.modules_by_relative_path[relative])
        budget = TEST_MODULE_BUDGETS.get(relative, MAX_TEST_LINES)
        if line_count > budget:
            failures.append(
                f"{relative}: {line_count} test lines exceeds "
                f"{budget}"
            )
    if failures:
        print("\n".join(f"FAIL {failure}" for failure in failures))
        return 1
    print("rewrite architecture constraints: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
