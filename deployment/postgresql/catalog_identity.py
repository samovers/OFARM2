"""External trust anchor for the migration-owned catalog verifiers.

Each service migration contains a complete symbolic catalog fingerprint.  That
fingerprint deliberately excludes only the verifier's own ``prosrc`` to avoid a
self-referential digest.  This module closes that one gap from outside the SQL
function: one fixed catalog statement authenticates the exact verifier and the
readiness observer that calls it before either result is trusted.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

import psycopg

from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    MigrationService,
)


CATALOG_VERIFIER_IDENTITY_POLICY = "OFARM_POSTGRESQL_CATALOG_VERIFIER_V1"
_DIGEST_DOMAIN = CATALOG_VERIFIER_IDENTITY_POLICY.encode("ascii") + b"\x00"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
CATALOG_OUTPUT_SETTING_ASSIGNMENTS = (
    "standard_conforming_strings = on",
    "TimeZone = 'UTC'",
    "DateStyle = 'ISO, MDY'",
    "quote_all_identifiers = off",
)
CATALOG_OUTPUT_SETTING_VALUES = (
    "on",
    "UTC",
    "ISO, MDY",
    "off",
)

# These literals are derived only from clean, fully migrated PostgreSQL 17
# targets. ``None`` remains fail-closed while a release is being frozen.
TENANT_CATALOG_VERIFIER_DIGEST: str | None = (
    "sha256:d50da4574b611a0675f039170296648fce6aaca7a946812360e4ea69448a960e"
)
SECURITY_AUDIT_CATALOG_VERIFIER_DIGEST: str | None = (
    "sha256:d897f0a02f851b37f64d883d384e2fa01ee356160553ffb5061f24de4581c074"
)


class CatalogIdentityError(RuntimeError):
    """The exact migration-owned catalog verifier could not be authenticated."""


@dataclass(frozen=True, slots=True)
class CatalogIdentityObservation:
    """Content identity of the two routines that anchor one service catalog."""

    policy: str
    service_identity: str
    row_count: int
    digest: str


@dataclass(frozen=True, slots=True)
class _RoutinePair:
    schema_name: str
    verifier_name: str
    observer_name: str

    @property
    def expected_identities(self) -> tuple[str, str]:
        return tuple(
            sorted(
                (
                    f"{self.schema_name}.{self.verifier_name}()",
                    f"{self.schema_name}.{self.observer_name}()",
                )
            )
        )


_TENANT_ROUTINES = _RoutinePair(
    schema_name="ofarm",
    verifier_name="verify_tenant_structure",
    observer_name="observe_tenant_contract",
)
_AUDIT_ROUTINES = _RoutinePair(
    schema_name="ofarm_security",
    verifier_name="verify_security_audit_structure",
    observer_name="observe_security_audit_contract",
)


# The statement is intentionally caller-independent.  Runner verification uses
# the schema owner through SET ROLE while startup uses a readiness LOGIN, so
# session identity and transaction posture belong to their separate route gates
# and must not make the catalog digest vary by caller.
_ROUTINE_IDENTITY_SQL = r"""
    WITH expected(schema_name, routine_name) AS (
        VALUES
            (%s::pg_catalog.text, %s::pg_catalog.text),
            (%s::pg_catalog.text, %s::pg_catalog.text)
    ),
    routine_identity AS (
        SELECT
            'routine'::pg_catalog.text AS section,
            (
                pg_catalog.quote_ident(namespace.nspname)
                || '.' || pg_catalog.quote_ident(routine.proname)
                || '(' || pg_catalog.pg_get_function_identity_arguments(routine.oid)
                || ')'
            )::pg_catalog.text AS object_identity,
            pg_catalog.jsonb_build_object(
                'owner', owner.rolname,
                'language', language.lanname,
                'kind', routine.prokind,
                'securityDefiner', routine.prosecdef,
                'leakproof', routine.proleakproof,
                'strict', routine.proisstrict,
                'volatility', routine.provolatile,
                'parallel', routine.proparallel,
                'returnsSet', routine.proretset,
                'returnType', pg_catalog.format_type(routine.prorettype, NULL),
                'argumentCount', routine.pronargs,
                'defaultArgumentCount', routine.pronargdefaults,
                'arguments', pg_catalog.pg_get_function_arguments(routine.oid),
                'identityArguments',
                    pg_catalog.pg_get_function_identity_arguments(routine.oid),
                'result', pg_catalog.pg_get_function_result(routine.oid),
                'cost', routine.procost,
                'rows', routine.prorows,
                'support', CASE
                    WHEN routine.prosupport = 0 THEN NULL
                    ELSE routine.prosupport::pg_catalog.regprocedure::pg_catalog.text
                END,
                'binary', routine.probin,
                'source', routine.prosrc,
                'config', COALESCE(
                    pg_catalog.to_jsonb(routine.proconfig),
                    '[]'::pg_catalog.jsonb
                ),
                'definition', pg_catalog.pg_get_functiondef(routine.oid),
                'acl', COALESCE(
                    (
                        SELECT pg_catalog.jsonb_agg(
                            pg_catalog.jsonb_build_array(
                                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                                     ELSE grantee.rolname END,
                                acl.privilege_type,
                                acl.is_grantable,
                                grantor.rolname
                            )
                            ORDER BY
                                CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                                     ELSE grantee.rolname END
                                    COLLATE pg_catalog."C",
                                acl.privilege_type COLLATE pg_catalog."C",
                                acl.is_grantable,
                                grantor.rolname COLLATE pg_catalog."C"
                        )
                        FROM pg_catalog.aclexplode(
                            COALESCE(
                                routine.proacl,
                                pg_catalog.acldefault('f', routine.proowner)
                            )
                        ) AS acl
                        LEFT JOIN pg_catalog.pg_roles AS grantee
                          ON grantee.oid = acl.grantee
                        JOIN pg_catalog.pg_roles AS grantor
                          ON grantor.oid = acl.grantor
                    ),
                    '[]'::pg_catalog.jsonb
                )
            )::pg_catalog.text AS detail
        FROM expected
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.nspname = expected.schema_name
        JOIN pg_catalog.pg_proc AS routine
          ON routine.pronamespace = namespace.oid
         AND routine.proname = expected.routine_name
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
        JOIN pg_catalog.pg_language AS language ON language.oid = routine.prolang
    )
    SELECT section, object_identity, detail
    FROM routine_identity
    ORDER BY
        section COLLATE pg_catalog."C",
        object_identity COLLATE pg_catalog."C",
        detail COLLATE pg_catalog."C"
"""


def _routine_pair(service: MigrationService) -> _RoutinePair:
    if service == TENANT_SERVICE:
        return _TENANT_ROUTINES
    if service == SECURITY_AUDIT_SERVICE:
        return _AUDIT_ROUTINES
    raise CatalogIdentityError("catalog service identity is not fixed")


def _expected_digest(service: MigrationService) -> str | None:
    if service == TENANT_SERVICE:
        return TENANT_CATALOG_VERIFIER_DIGEST
    if service == SECURITY_AUDIT_SERVICE:
        return SECURITY_AUDIT_CATALOG_VERIFIER_DIGEST
    raise CatalogIdentityError("catalog service identity is not fixed")


def _lp32(value: bytes) -> bytes:
    if len(value) >= 2**32:
        raise CatalogIdentityError("catalog identity field exceeds its bound")
    return len(value).to_bytes(4, "big", signed=False) + value


def _canonical_digest(
    service: MigrationService,
    rows: tuple[tuple[str, str, str], ...],
) -> str:
    framed = bytearray(_DIGEST_DOMAIN)
    framed.extend(_lp32(service.identity.encode("ascii", errors="strict")))
    framed.extend(len(rows).to_bytes(4, "big", signed=False))
    for row in rows:
        for value in row:
            framed.extend(_lp32(value.encode("utf-8", errors="strict")))
    return "sha256:" + hashlib.sha256(framed).hexdigest()


def _validated_rows(
    service: MigrationService,
    observed: object,
) -> tuple[tuple[str, str, str], ...]:
    pair = _routine_pair(service)
    if type(observed) is not list or len(observed) != 2:
        raise CatalogIdentityError("catalog verifier routine inventory differs")
    rows: list[tuple[str, str, str]] = []
    for row in observed:
        if (
            type(row) is not tuple
            or len(row) != 3
            or any(type(value) is not str or not value for value in row)
        ):
            raise CatalogIdentityError("catalog verifier routine row differs")
        try:
            for value in row:
                value.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise CatalogIdentityError(
                "catalog verifier routine encoding differs"
            ) from exc
        rows.append(row)
    exact = tuple(rows)
    if exact != tuple(sorted(exact)):
        raise CatalogIdentityError("catalog verifier routine order differs")
    if len({(row[0], row[1]) for row in exact}) != len(exact):
        raise CatalogIdentityError("catalog verifier routine identity repeats")
    if any(row[0] != "routine" for row in exact) or tuple(
        row[1] for row in exact
    ) != pair.expected_identities:
        raise CatalogIdentityError("catalog verifier routine identity differs")
    return exact


def observe_catalog_identity(
    connection: psycopg.Connection[Any],
    service: MigrationService,
) -> CatalogIdentityObservation:
    """Observe the exact verifier/observer pair with one catalog statement."""

    pair = _routine_pair(service)
    try:
        rows = connection.execute(
            _ROUTINE_IDENTITY_SQL,
            (
                pair.schema_name,
                pair.verifier_name,
                pair.schema_name,
                pair.observer_name,
            ),
        ).fetchall()
        exact = _validated_rows(service, rows)
        digest = _canonical_digest(service, exact)
    except CatalogIdentityError:
        raise
    except Exception as exc:
        raise CatalogIdentityError(
            "catalog verifier routines are unreadable"
        ) from exc
    return CatalogIdentityObservation(
        policy=CATALOG_VERIFIER_IDENTITY_POLICY,
        service_identity=service.identity,
        row_count=len(exact),
        digest=digest,
    )


def verify_catalog_identity(
    connection: psycopg.Connection[Any],
    service: MigrationService,
    *,
    expected_digest: str | None = None,
) -> CatalogIdentityObservation:
    """Authenticate one service's SQL catalog verifier before executing it."""

    expected = _expected_digest(service) if expected_digest is None else expected_digest
    if type(expected) is not str or _DIGEST.fullmatch(expected) is None:
        raise CatalogIdentityError("catalog verifier trust anchor is unavailable")
    observation = observe_catalog_identity(connection, service)
    if observation.digest != expected:
        raise CatalogIdentityError("catalog verifier identity differs")
    return observation


__all__ = (
    "CATALOG_OUTPUT_SETTING_ASSIGNMENTS",
    "CATALOG_OUTPUT_SETTING_VALUES",
    "CATALOG_VERIFIER_IDENTITY_POLICY",
    "SECURITY_AUDIT_CATALOG_VERIFIER_DIGEST",
    "TENANT_CATALOG_VERIFIER_DIGEST",
    "CatalogIdentityError",
    "CatalogIdentityObservation",
    "observe_catalog_identity",
    "verify_catalog_identity",
)
