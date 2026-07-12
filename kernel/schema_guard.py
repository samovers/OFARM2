"""Fail-closed PostgreSQL schema installation and restart verification.

The application never treats ``CREATE ... IF NOT EXISTS`` as a migration
mechanism.  Static RuntimeBundle inputs are verified before a connection is
opened.  The target ``public`` schema is then classified without writes as one
of:

* empty -- the exact reviewed schema may be installed once, atomically;
* current -- the protected install ledger and live catalog are byte-equal; or
* other -- legacy, partial, or drifted state which must be recreated.

The catalog document intentionally contains PostgreSQL semantic metadata, not
planner statistics or timestamps.  Its canonical bytes are retained in the
ledger so every later process can compare the live catalog with the catalog
created by the exact schema bytes used for the first install.  A closed-world
inventory covers every public namespaced catalog class, including aggregates,
operators, collations, operator classes/families, statistics objects, and text
search objects that are easy to miss in table-only fingerprints.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb


CATALOG_VERSION = "ofarm.postgresql-catalog-fingerprint.local.v3"
LEDGER_KEY = "ofarm-kernel-schema"
_SCHEMA_LOGICAL_REF = "sql:kernel/schema.sql"
_SCHEMA_PATH = "kernel/schema.sql"
_INSTALL_LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"OFARM2 exact schema installation v1").digest()[:8],
    "big",
    signed=True,
)
_SCHEMA_TRANSACTION_SETTINGS = (
    ("TimeZone", "UTC"),
    ("DateStyle", "ISO, MDY"),
    ("IntervalStyle", "postgres"),
    ("search_path", "pg_catalog, public"),
    ("session_replication_role", "origin"),
    ("standard_conforming_strings", "on"),
    ("extra_float_digits", "1"),
    ("bytea_output", "hex"),
)
_CATALOG_LOCK_ATTEMPTS = 100
_CATALOG_LOCK_RETRY_DELAY_SECONDS = 0.01
_CATALOG_LOCK_SAVEPOINT = "ofarm_catalog_lock_attempt"
_FINGERPRINT_CATALOGS = (
    "pg_aggregate",
    "pg_am",
    "pg_amop",
    "pg_amproc",
    "pg_attribute",
    "pg_attrdef",
    "pg_authid",
    "pg_cast",
    "pg_class",
    "pg_collation",
    "pg_conversion",
    "pg_constraint",
    "pg_default_acl",
    "pg_depend",
    "pg_enum",
    "pg_event_trigger",
    "pg_extension",
    "pg_index",
    "pg_inherits",
    "pg_language",
    "pg_namespace",
    "pg_opclass",
    "pg_operator",
    "pg_opfamily",
    "pg_policy",
    "pg_proc",
    "pg_range",
    "pg_rewrite",
    "pg_sequence",
    "pg_statistic_ext",
    "pg_ts_config",
    "pg_ts_config_map",
    "pg_ts_dict",
    "pg_ts_parser",
    "pg_ts_template",
    "pg_trigger",
    "pg_transform",
    "pg_type",
)


class SchemaGuardError(RuntimeError):
    """Static catalog or target PostgreSQL schema is not exactly verifiable."""


class SchemaState(str, Enum):
    EMPTY = "EMPTY"
    EXACT_CURRENT = "EXACT_CURRENT"
    OTHER = "OTHER"


@dataclass(frozen=True)
class VerifiedStaticSchema:
    """Exact startup inputs proven against the canonical component lock."""

    schema_bytes: bytes
    schema_sql: str
    schema_digest: str
    lock_digest: str


@dataclass(frozen=True)
class SchemaClassification:
    state: SchemaState
    detail: str
    catalog_document: dict[str, Any]
    catalog_bytes: bytes
    catalog_fingerprint: str


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def require_no_temporary_schema(cur) -> None:
    """Refuse a session once PostgreSQL has created its implicit pg_temp schema.

    ``pg_temp`` is searched for relation and type names even when it is absent
    from ``search_path``.  Merely setting ``search_path = pg_catalog, public``
    therefore does not prevent a temporary relation from shadowing reviewed
    schema DDL or runtime SQL.  A fresh connection has OID zero here; once a
    temporary namespace exists, this process discards the connection rather
    than attempting to prove which temporary objects have existed.
    """
    cur.execute(
        "SELECT pg_catalog.pg_my_temp_schema()::pg_catalog.oid AS temp_schema_oid"
    )
    if int(cur.fetchone()["temp_schema_oid"]) != 0:
        raise SchemaGuardError(
            "PostgreSQL session has an implicit temporary schema; pg_temp can "
            "shadow reviewed public relations, so governed use is forbidden on "
            "this connection"
        )


def _establish_schema_transaction_posture(cur) -> None:
    """Fix all rendering/DDL GUCs and refuse inherited SET ROLE authority."""
    require_no_temporary_schema(cur)
    cur.execute(
        "SELECT CURRENT_USER::pg_catalog.text AS current_user_name, "
        "SESSION_USER::pg_catalog.text AS session_user_name"
    )
    identity = cur.fetchone()
    if identity["current_user_name"] != identity["session_user_name"]:
        raise SchemaGuardError(
            "schema classification refuses a current role different from the "
            "authenticated PostgreSQL session role"
        )
    for setting_name, expected in _SCHEMA_TRANSACTION_SETTINGS:
        cur.execute(
            "SELECT pg_catalog.set_config(%s, %s, true) AS value",
            (setting_name, expected),
        )
        if cur.fetchone()["value"] != expected:
            raise SchemaGuardError(
                f"schema classification could not fix PostgreSQL setting "
                f"{setting_name!r}"
            )
    cur.execute(
        "SELECT " + ", ".join(
            f"pg_catalog.current_setting('{name}') AS setting_{index}"
            for index, (name, _expected) in enumerate(
                _SCHEMA_TRANSACTION_SETTINGS)
        )
    )
    observed = cur.fetchone()
    if any(observed[f"setting_{index}"] != expected
           for index, (_name, expected) in enumerate(
               _SCHEMA_TRANSACTION_SETTINGS)):
        raise SchemaGuardError(
            "schema classification did not retain its deterministic PostgreSQL "
            "transaction posture"
        )


def hold_fingerprint_catalog_locks(cur) -> None:
    """Exclude non-cooperating DDL until the caller transaction completes.

    PostgreSQL retains explicit relation locks through COMMIT/ROLLBACK.  Runtime
    callers take these locks before recomputing the exact catalog receipt and
    keep them for the complete governed decision transaction, closing the
    otherwise unavoidable check/DDL race.
    """
    require_no_temporary_schema(cur)
    if cur.connection.info.transaction_status != \
            psycopg.pq.TransactionStatus.INTRANS:
        raise SchemaGuardError(
            "schema catalog locks require one active PostgreSQL transaction")
    qualified = ", ".join(
        f"pg_catalog.{name}" for name in _FINGERPRINT_CATALOGS)
    lock_sql = f"LOCK TABLE {qualified} IN SHARE MODE NOWAIT"
    last_contention = None
    for attempt in range(_CATALOG_LOCK_ATTEMPTS):
        cur.execute(f"SAVEPOINT {_CATALOG_LOCK_SAVEPOINT}")
        try:
            cur.execute(lock_sql)
        except psycopg.errors.LockNotAvailable as exc:
            # One multi-relation LOCK can acquire an earlier catalog before a
            # later catalog is found busy. Rolling back the savepoint releases
            # that partial prefix, so retrying cannot deadlock with autovacuum's
            # own target-catalog -> dependency-catalog lock order.
            cur.execute(f"ROLLBACK TO SAVEPOINT {_CATALOG_LOCK_SAVEPOINT}")
            cur.execute(f"RELEASE SAVEPOINT {_CATALOG_LOCK_SAVEPOINT}")
            last_contention = exc
            if attempt + 1 < _CATALOG_LOCK_ATTEMPTS:
                time.sleep(_CATALOG_LOCK_RETRY_DELAY_SECONDS)
                continue
        except psycopg.Error as exc:
            cur.execute(f"ROLLBACK TO SAVEPOINT {_CATALOG_LOCK_SAVEPOINT}")
            cur.execute(f"RELEASE SAVEPOINT {_CATALOG_LOCK_SAVEPOINT}")
            raise SchemaGuardError(
                "cannot lock PostgreSQL catalogs against concurrent DDL; exact "
                "schema installation or governed runtime use is forbidden"
            ) from exc
        else:
            # Explicit relation locks acquired inside a savepoint remain held
            # by the outer transaction after RELEASE and therefore cover the
            # fingerprint plus the complete governed decision body.
            cur.execute(f"RELEASE SAVEPOINT {_CATALOG_LOCK_SAVEPOINT}")
            return
    raise SchemaGuardError(
        "PostgreSQL catalogs remained busy while excluding concurrent DDL; exact "
        "schema installation or governed runtime use is forbidden"
    ) from last_contention


def verify_static_runtime_catalog(package_root: Path) -> VerifiedStaticSchema:
    """Verify the full static catalog, lock, and exact schema before DB access."""
    root = Path(package_root).resolve()
    try:
        from tooling.runtime_bundle_lock import (
            CatalogError,
            LOCK_PATH,
            ROOT,
            build_catalog,
            verify_lock_bytes,
        )
    except ImportError as exc:
        raise SchemaGuardError(
            f"RuntimeBundle catalog verifier is unavailable before database startup: {exc}"
        ) from exc
    if Path(ROOT).resolve() != root:
        raise SchemaGuardError(
            "RuntimeBundle catalog verifier is rooted at another package; "
            "database startup is forbidden"
        )
    try:
        expected = build_catalog()
        lock_bytes = Path(LOCK_PATH).read_bytes()
        verify_lock_bytes(lock_bytes, expected)
    except (OSError, CatalogError) as exc:
        raise SchemaGuardError(
            "static RuntimeBundle catalog/lock verification failed before database "
            f"startup: {exc}"
        ) from exc

    schema_entries = [
        entry for entry in expected["components"]
        if entry.get("role") == "RUNTIME_SCHEMA"
        and entry.get("logicalRef") == _SCHEMA_LOGICAL_REF
    ]
    if len(schema_entries) != 1:
        raise SchemaGuardError(
            "static RuntimeBundle catalog does not contain exactly one kernel schema"
        )
    entry = schema_entries[0]
    if (entry.get("path") != _SCHEMA_PATH
            or entry.get("canonicalization") != "EXACT_BYTES_V1"
            or entry.get("placement") != "GLOBAL_IMMUTABLE_CONTENT"):
        raise SchemaGuardError(
            "kernel schema catalog identity/canonicalization/placement is invalid"
        )
    try:
        schema_bytes = (root / _SCHEMA_PATH).read_bytes()
        schema_sql = schema_bytes.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        raise SchemaGuardError(
            f"exact kernel schema bytes are unreadable or not UTF-8: {exc}"
        ) from exc
    if schema_sql.startswith("\ufeff"):
        raise SchemaGuardError("exact kernel schema bytes must not contain a UTF-8 BOM")
    schema_digest = _sha256(schema_bytes)
    if entry.get("sha256") != schema_digest:
        raise SchemaGuardError(
            "exact kernel schema bytes differ from the verified RuntimeBundle catalog"
        )
    return VerifiedStaticSchema(
        schema_bytes=schema_bytes,
        schema_sql=schema_sql,
        schema_digest=schema_digest,
        lock_digest=_sha256(lock_bytes),
    )


def _rows(cur, query: str) -> list[dict[str, Any]]:
    cur.execute(query)
    return [dict(row) for row in cur.fetchall()]


def postgres_catalog_document(cur) -> dict[str, Any]:
    """Return a deterministic, OID-free document for decision-bearing objects."""
    # Fix name rendering performed by pg_get_* and format_type.  Every object
    # query is also explicitly scoped to public; caller search_path cannot add
    # or hide an object from the fingerprint. Restore the exact caller value
    # before returning because this verifier may run inside a governed
    # transaction whose receipted session posture must not change.
    cur.execute(
        "SELECT pg_catalog.current_setting('search_path') AS search_path")
    original_search_path = cur.fetchone()["search_path"]
    cur.execute(
        "SELECT pg_catalog.set_config("
        "'search_path', 'pg_catalog, public', true) "
        "AS search_path"
    )

    namespace = _rows(cur, """
        SELECT n.nspname AS name, owner.rolname AS owner
        FROM pg_namespace n
        JOIN pg_roles owner ON owner.oid = n.nspowner
        WHERE n.nspname = 'public'
        ORDER BY n.nspname
    """)
    relations = _rows(cur, """
        SELECT c.relname AS name, c.relkind::text AS kind,
               c.relpersistence::text AS persistence,
               owner.rolname AS owner,
               c.relrowsecurity AS row_security,
               c.relforcerowsecurity AS force_row_security,
               c.relhassubclass AS has_subclass,
               c.relreplident::text AS replica_identity,
               COALESCE(c.reloptions, ARRAY[]::text[]) AS options,
               CASE WHEN c.relkind IN ('v', 'm')
                    THEN pg_get_viewdef(c.oid, true) ELSE NULL END AS definition
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_roles owner ON owner.oid = c.relowner
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
        ORDER BY c.relname, c.relkind
    """)
    inheritance = _rows(cur, """
        SELECT child_ns.nspname AS child_schema,
               child.relname AS child_relation,
               parent_ns.nspname AS parent_schema,
               parent.relname AS parent_relation,
               inheritance.inhseqno AS sequence,
               inheritance.inhdetachpending AS detach_pending
        FROM pg_inherits inheritance
        JOIN pg_class child ON child.oid = inheritance.inhrelid
        JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
        JOIN pg_class parent ON parent.oid = inheritance.inhparent
        JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
        WHERE child_ns.nspname = 'public' OR parent_ns.nspname = 'public'
        ORDER BY parent_ns.nspname, parent.relname,
                 child_ns.nspname, child.relname, inheritance.inhseqno
    """)
    columns = _rows(cur, """
        SELECT c.relname AS relation, a.attnum AS position,
               a.attname AS name, format_type(a.atttypid, a.atttypmod) AS type,
               a.attnotnull AS not_null,
               a.attidentity::text AS identity,
               a.attgenerated::text AS generated,
               CASE WHEN a.attcollation = 0 THEN NULL
                    ELSE coll_ns.nspname || '.' || coll.collname END AS collation,
               pg_get_expr(ad.adbin, ad.adrelid, true) AS default_expression,
               a.attstorage::text AS storage,
               a.attcompression::text AS compression
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_attrdef ad
          ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
        LEFT JOIN pg_collation coll ON coll.oid = a.attcollation
        LEFT JOIN pg_namespace coll_ns ON coll_ns.oid = coll.collnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY c.relname, a.attnum
    """)
    sequences = _rows(cur, """
        SELECT c.relname AS name,
               format_type(s.seqtypid, NULL) AS type,
               s.seqstart::text AS start_value,
               s.seqincrement::text AS increment_by,
               s.seqmax::text AS max_value,
               s.seqmin::text AS min_value,
               s.seqcache::text AS cache_size,
               s.seqcycle AS cycle,
               owned.relname AS owned_relation,
               owned_att.attname AS owned_column
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_sequence s ON s.seqrelid = c.oid
        LEFT JOIN pg_depend dep
          ON dep.classid = 'pg_class'::regclass
         AND dep.objid = c.oid
         AND dep.refclassid = 'pg_class'::regclass
         AND dep.deptype IN ('a', 'i')
        LEFT JOIN pg_class owned ON owned.oid = dep.refobjid
        LEFT JOIN pg_attribute owned_att
          ON owned_att.attrelid = dep.refobjid
         AND owned_att.attnum = dep.refobjsubid
        WHERE n.nspname = 'public' AND c.relkind = 'S'
        ORDER BY c.relname
    """)
    types = _rows(cur, """
        SELECT t.typname AS name, t.typtype::text AS kind,
               owner.rolname AS owner,
               t.typcategory::text AS category,
               t.typispreferred AS preferred,
               t.typisdefined AS defined,
               t.typdelim::text AS delimiter,
               t.typlen AS internal_length,
               t.typbyval AS passed_by_value,
               t.typalign::text AS alignment,
               t.typstorage::text AS storage,
               input_fn_ns.nspname || '.' || input_fn.proname AS input_function,
               output_fn_ns.nspname || '.' || output_fn.proname AS output_function,
               CASE WHEN t.typbasetype = 0 THEN NULL
                    ELSE format_type(t.typbasetype, t.typtypmod) END AS base_type,
               t.typnotnull AS not_null,
               t.typdefault AS default_expression,
               format_type(r.rngsubtype, NULL) AS range_subtype,
               ARRAY(
                 SELECT e.enumlabel
                 FROM pg_enum e
                 WHERE e.enumtypid = t.oid
                 ORDER BY e.enumsortorder
               ) AS enum_labels,
               COALESCE((
                 SELECT jsonb_agg(jsonb_build_object(
                   'position', a.attnum,
                   'name', a.attname,
                   'type', format_type(a.atttypid, a.atttypmod),
                   'collation', CASE WHEN a.attcollation = 0 THEN NULL
                     ELSE attr_coll_ns.nspname || '.' || attr_coll.collname END
                 ) ORDER BY a.attnum)
                 FROM pg_class composite
                 JOIN pg_attribute a ON a.attrelid = composite.oid
                 LEFT JOIN pg_collation attr_coll
                   ON attr_coll.oid = a.attcollation
                 LEFT JOIN pg_namespace attr_coll_ns
                   ON attr_coll_ns.oid = attr_coll.collnamespace
                 WHERE composite.reltype = t.oid AND composite.relkind = 'c'
                   AND a.attnum > 0 AND NOT a.attisdropped
               ), '[]'::jsonb) AS composite_attributes
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_roles owner ON owner.oid = t.typowner
        LEFT JOIN pg_proc input_fn ON input_fn.oid = t.typinput
        LEFT JOIN pg_namespace input_fn_ns ON input_fn_ns.oid = input_fn.pronamespace
        LEFT JOIN pg_proc output_fn ON output_fn.oid = t.typoutput
        LEFT JOIN pg_namespace output_fn_ns ON output_fn_ns.oid = output_fn.pronamespace
        LEFT JOIN pg_range r ON r.rngtypid = t.oid
        WHERE n.nspname = 'public'
          AND NOT EXISTS (SELECT 1 FROM pg_type parent WHERE parent.typarray = t.oid)
          AND NOT EXISTS (
            SELECT 1 FROM pg_class relation_type
            WHERE relation_type.reltype = t.oid AND relation_type.relkind <> 'c'
          )
        ORDER BY t.typname
    """)
    constraints = _rows(cur, """
        SELECT con.conname AS name, rel.relname AS relation,
               typ.typname AS domain_type,
               con.contype::text AS kind,
               con.condeferrable AS deferrable,
               con.condeferred AS initially_deferred,
               con.convalidated AS validated,
               pg_get_constraintdef(con.oid, true) AS definition
        FROM pg_constraint con
        JOIN pg_namespace n ON n.oid = con.connamespace
        LEFT JOIN pg_class rel ON rel.oid = con.conrelid
        LEFT JOIN pg_type typ ON typ.oid = con.contypid
        WHERE n.nspname = 'public'
        ORDER BY COALESCE(rel.relname, typ.typname), con.conname
    """)
    indexes = _rows(cur, """
        SELECT table_rel.relname AS relation, index_rel.relname AS name,
               owner.rolname AS owner,
               idx.indisunique AS unique,
               idx.indisprimary AS primary,
               idx.indisexclusion AS exclusion,
               idx.indimmediate AS immediate,
               idx.indisclustered AS clustered,
               idx.indisvalid AS valid,
               idx.indisready AS ready,
               idx.indislive AS live,
               idx.indisreplident AS replica_identity,
               pg_get_indexdef(index_rel.oid) AS definition
        FROM pg_index idx
        JOIN pg_class index_rel ON index_rel.oid = idx.indexrelid
        JOIN pg_class table_rel ON table_rel.oid = idx.indrelid
        JOIN pg_namespace n ON n.oid = table_rel.relnamespace
        JOIN pg_roles owner ON owner.oid = index_rel.relowner
        WHERE n.nspname = 'public'
        ORDER BY table_rel.relname, index_rel.relname
    """)
    triggers = _rows(cur, """
        SELECT rel.relname AS relation, trg.tgname AS name,
               trg.tgenabled::text AS enabled,
               fn_ns.nspname AS function_schema,
               fn.proname AS function_name,
               pg_get_function_identity_arguments(fn.oid) AS function_arguments,
               pg_get_triggerdef(trg.oid, true) AS definition
        FROM pg_trigger trg
        JOIN pg_class rel ON rel.oid = trg.tgrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        JOIN pg_proc fn ON fn.oid = trg.tgfoid
        JOIN pg_namespace fn_ns ON fn_ns.oid = fn.pronamespace
        WHERE n.nspname = 'public' AND NOT trg.tgisinternal
        ORDER BY rel.relname, trg.tgname
    """)
    internal_constraint_triggers = _rows(cur, """
        SELECT rel.relname AS relation,
               con.conname AS constraint_name,
               referenced.relname AS referenced_relation,
               fn_ns.nspname AS function_schema,
               fn.proname AS function_name,
               pg_get_function_identity_arguments(fn.oid) AS function_arguments,
               trg.tgtype::integer AS trigger_type,
               trg.tgenabled::text AS enabled,
               trg.tgdeferrable AS deferrable,
               trg.tginitdeferred AS initially_deferred
        FROM pg_trigger trg
        JOIN pg_class rel ON rel.oid = trg.tgrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        JOIN pg_proc fn ON fn.oid = trg.tgfoid
        JOIN pg_namespace fn_ns ON fn_ns.oid = fn.pronamespace
        LEFT JOIN pg_constraint con ON con.oid = trg.tgconstraint
        LEFT JOIN pg_class referenced ON referenced.oid = con.confrelid
        WHERE n.nspname = 'public' AND trg.tgisinternal
        ORDER BY rel.relname, con.conname, referenced.relname,
                 fn_ns.nspname, fn.proname,
                 pg_get_function_identity_arguments(fn.oid), trg.tgtype
    """)
    rules = _rows(cur, """
        SELECT rel.relname AS relation, rewrite.rulename AS name,
               rewrite.ev_enabled::text AS enabled,
               rewrite.is_instead AS instead,
               pg_get_ruledef(rewrite.oid, true) AS definition
        FROM pg_rewrite rewrite
        JOIN pg_class rel ON rel.oid = rewrite.ev_class
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        WHERE n.nspname = 'public'
        ORDER BY rel.relname, rewrite.rulename
    """)
    functions = _rows(cur, """
        SELECT p.proname AS name,
               pg_get_function_identity_arguments(p.oid) AS identity_arguments,
               pg_get_function_result(p.oid) AS result_type,
               p.prokind::text AS kind,
               lang.lanname AS language,
               owner.rolname AS owner,
               p.provolatile::text AS volatility,
               p.proisstrict AS strict,
               p.prosecdef AS security_definer,
               p.proleakproof AS leakproof,
               p.proparallel::text AS parallel,
               p.procost::text AS cost,
               p.prorows::text AS rows,
               COALESCE(p.proconfig, ARRAY[]::text[]) AS configuration,
               pg_get_functiondef(p.oid) AS definition
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        JOIN pg_language lang ON lang.oid = p.prolang
        JOIN pg_roles owner ON owner.oid = p.proowner
        WHERE n.nspname = 'public' AND p.prokind IN ('f', 'p', 'w')
        ORDER BY p.proname, pg_get_function_identity_arguments(p.oid)
    """)
    policies = _rows(cur, """
        SELECT rel.relname AS relation, pol.polname AS name,
               pol.polpermissive AS permissive,
               ARRAY(
                 SELECT CASE WHEN policy_role.role_oid = 0
                             THEN 'PUBLIC' ELSE role.rolname END
                 FROM unnest(pol.polroles) AS policy_role(role_oid)
                 LEFT JOIN pg_roles role ON role.oid = policy_role.role_oid
                 ORDER BY CASE WHEN policy_role.role_oid = 0
                               THEN 'PUBLIC' ELSE role.rolname END
               ) AS roles,
               pol.polcmd::text AS command,
               pg_get_expr(pol.polqual, pol.polrelid, true) AS using_expression,
               pg_get_expr(pol.polwithcheck, pol.polrelid, true) AS check_expression
        FROM pg_policy pol
        JOIN pg_class rel ON rel.oid = pol.polrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        WHERE n.nspname = 'public'
        ORDER BY rel.relname, pol.polname
    """)
    grants = _rows(cur, """
        SELECT object_kind, object_name, subobject_name, grantor, grantee,
               privilege_type, is_grantable
        FROM (
          SELECT 'SCHEMA'::text AS object_kind, n.nspname AS object_name,
                 NULL::text AS subobject_name,
                 grantor.rolname AS grantor,
                 CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE grantee.rolname END AS grantee,
                 acl.privilege_type, acl.is_grantable
          FROM pg_namespace n
          CROSS JOIN LATERAL aclexplode(
            COALESCE(n.nspacl, acldefault('n', n.nspowner))) acl
          JOIN pg_roles grantor ON grantor.oid = acl.grantor
          LEFT JOIN pg_roles grantee ON grantee.oid = acl.grantee
          WHERE n.nspname = 'public'

          UNION ALL

          SELECT 'RELATION', c.relname, NULL,
                 grantor.rolname,
                 CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE grantee.rolname END,
                 acl.privilege_type, acl.is_grantable
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL aclexplode(COALESCE(
            c.relacl,
            acldefault(CASE WHEN c.relkind = 'S' THEN 's'::"char"
                            ELSE 'r'::"char" END, c.relowner))) acl
          JOIN pg_roles grantor ON grantor.oid = acl.grantor
          LEFT JOIN pg_roles grantee ON grantee.oid = acl.grantee
          WHERE n.nspname = 'public'
            AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')

          UNION ALL

          SELECT 'COLUMN', c.relname, a.attname,
                 grantor.rolname,
                 CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE grantee.rolname END,
                 acl.privilege_type, acl.is_grantable
          FROM pg_attribute a
          JOIN pg_class c ON c.oid = a.attrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL aclexplode(a.attacl) acl
          JOIN pg_roles grantor ON grantor.oid = acl.grantor
          LEFT JOIN pg_roles grantee ON grantee.oid = acl.grantee
          WHERE n.nspname = 'public' AND a.attnum > 0 AND NOT a.attisdropped

          UNION ALL

          SELECT 'FUNCTION',
                 p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')',
                 NULL, grantor.rolname,
                 CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE grantee.rolname END,
                 acl.privilege_type, acl.is_grantable
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
          CROSS JOIN LATERAL aclexplode(
            COALESCE(p.proacl, acldefault('f', p.proowner))) acl
          JOIN pg_roles grantor ON grantor.oid = acl.grantor
          LEFT JOIN pg_roles grantee ON grantee.oid = acl.grantee
          WHERE n.nspname = 'public' AND p.prokind IN ('f', 'p', 'w')

          UNION ALL

          SELECT 'TYPE', t.typname, NULL, grantor.rolname,
                 CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE grantee.rolname END,
                 acl.privilege_type, acl.is_grantable
          FROM pg_type t
          JOIN pg_namespace n ON n.oid = t.typnamespace
          CROSS JOIN LATERAL aclexplode(
            COALESCE(t.typacl, acldefault('T', t.typowner))) acl
          JOIN pg_roles grantor ON grantor.oid = acl.grantor
          LEFT JOIN pg_roles grantee ON grantee.oid = acl.grantee
          WHERE n.nspname = 'public'
            AND NOT EXISTS (
              SELECT 1 FROM pg_type parent WHERE parent.typarray = t.oid)
            AND NOT EXISTS (
              SELECT 1 FROM pg_class relation_type
              WHERE relation_type.reltype = t.oid AND relation_type.relkind <> 'c'
            )
        ) all_grants
        ORDER BY object_kind, object_name, subobject_name,
                 grantor, grantee, privilege_type, is_grantable
    """)
    default_grants = _rows(cur, """
        SELECT owner.rolname AS owner,
               CASE WHEN defaults.defaclnamespace = 0
                    THEN '*' ELSE n.nspname END AS target_schema,
               defaults.defaclobjtype::text AS object_kind,
               grantor.rolname AS grantor,
               CASE WHEN acl.grantee = 0
                    THEN 'PUBLIC' ELSE grantee.rolname END AS grantee,
               acl.privilege_type, acl.is_grantable
        FROM pg_default_acl defaults
        JOIN pg_roles owner ON owner.oid = defaults.defaclrole
        LEFT JOIN pg_namespace n ON n.oid = defaults.defaclnamespace
        CROSS JOIN LATERAL aclexplode(defaults.defaclacl) acl
        JOIN pg_roles grantor ON grantor.oid = acl.grantor
        LEFT JOIN pg_roles grantee ON grantee.oid = acl.grantee
        WHERE defaults.defaclnamespace = 0 OR n.nspname = 'public'
        ORDER BY owner, target_schema, object_kind, grantor, grantee,
                 privilege_type, is_grantable
    """)
    # Closed-world inventory for every catalog class whose objects may live in
    # a namespace.  Detailed table/type/constraint metadata is retained above;
    # this inventory makes an otherwise-unmodelled public object a fingerprint
    # change instead of silently blessing it (notably pg_proc aggregates).
    namespace_object_inventory = _rows(cur, """
        SELECT catalog, object_kind, object_identity
        FROM (
          SELECT 'pg_class'::text AS catalog, c.relkind::text AS object_kind,
                 c.relname::text AS object_identity
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_type', t.typtype::text, t.typname::text
          FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_constraint', con.contype::text,
                 con.conname || ':' ||
                 COALESCE(rel.relname, typ.typname, '')
          FROM pg_constraint con
          JOIN pg_namespace n ON n.oid = con.connamespace
          LEFT JOIN pg_class rel ON rel.oid = con.conrelid
          LEFT JOIN pg_type typ ON typ.oid = con.contypid
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_proc', p.prokind::text,
                 p.proname || '(' ||
                 pg_get_function_identity_arguments(p.oid) || ')'
          FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_operator', o.oprkind::text,
                 o.oprname || '(' || format_type(o.oprleft, NULL) || ',' ||
                 format_type(o.oprright, NULL) || ')'
          FROM pg_operator o JOIN pg_namespace n ON n.oid = o.oprnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_opclass', am.amname::text,
                 opc.opcname || ':' || format_type(opc.opcintype, NULL)
          FROM pg_opclass opc
          JOIN pg_namespace n ON n.oid = opc.opcnamespace
          JOIN pg_am am ON am.oid = opc.opcmethod
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_opfamily', am.amname::text, opf.opfname::text
          FROM pg_opfamily opf
          JOIN pg_namespace n ON n.oid = opf.opfnamespace
          JOIN pg_am am ON am.oid = opf.opfmethod
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_collation', coll.collprovider::text,
                 coll.collname || ':' || coll.collencoding::text
          FROM pg_collation coll
          JOIN pg_namespace n ON n.oid = coll.collnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_conversion', con.condefault::text, con.conname::text
          FROM pg_conversion con
          JOIN pg_namespace n ON n.oid = con.connamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_statistic_ext', 'statistics', stx.stxname::text
          FROM pg_statistic_ext stx
          JOIN pg_namespace n ON n.oid = stx.stxnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_ts_parser', 'text-search-parser', prs.prsname::text
          FROM pg_ts_parser prs
          JOIN pg_namespace n ON n.oid = prs.prsnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_ts_dict', 'text-search-dictionary', dict.dictname::text
          FROM pg_ts_dict dict
          JOIN pg_namespace n ON n.oid = dict.dictnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_ts_template', 'text-search-template', tmpl.tmplname::text
          FROM pg_ts_template tmpl
          JOIN pg_namespace n ON n.oid = tmpl.tmplnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_ts_config', 'text-search-configuration', cfg.cfgname::text
          FROM pg_ts_config cfg
          JOIN pg_namespace n ON n.oid = cfg.cfgnamespace
          WHERE n.nspname = 'public'
        ) namespaced
        ORDER BY catalog, object_kind, object_identity
    """)
    # Exact catalog rows (minus their own local identity/namespace OIDs) retain
    # executable definitions and OID references to their dependencies.  Those
    # dependency OIDs are stable for the lifetime of this one local ledger and
    # make drop/recreate or retargeting detectable without trying to reverse-
    # engineer every PostgreSQL executable object class independently.
    executable_catalog_objects = _rows(cur, """
        SELECT catalog, object_identity, metadata
        FROM (
          SELECT 'pg_proc'::text AS catalog,
                 p.proname || '(' ||
                 pg_get_function_identity_arguments(p.oid) || ')[' ||
                 p.prokind::text || ']' AS object_identity,
                 (to_jsonb(p) - 'oid' - 'pronamespace') ||
                 CASE WHEN agg.aggfnoid IS NULL THEN '{}'::jsonb
                      ELSE jsonb_build_object(
                        'aggregate', to_jsonb(agg) - 'aggfnoid') END AS metadata
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
          LEFT JOIN pg_aggregate agg ON agg.aggfnoid = p.oid
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_operator',
                 o.oprname || '(' || format_type(o.oprleft, NULL) || ',' ||
                 format_type(o.oprright, NULL) || ')',
                 to_jsonb(o) - 'oid' - 'oprnamespace'
          FROM pg_operator o
          JOIN pg_namespace n ON n.oid = o.oprnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_opfamily', am.amname || ':' || opf.opfname,
                 (to_jsonb(opf) - 'oid' - 'opfnamespace') ||
                 jsonb_build_object(
                   'operators', COALESCE((
                     SELECT jsonb_agg(to_jsonb(amop) - 'oid'
                                      ORDER BY amop.amopstrategy,
                                               amop.amoplefttype,
                                               amop.amoprighttype,
                                               amop.amoppurpose)
                     FROM pg_amop amop WHERE amop.amopfamily = opf.oid
                   ), '[]'::jsonb),
                   'procedures', COALESCE((
                     SELECT jsonb_agg(to_jsonb(amproc) - 'oid'
                                      ORDER BY amproc.amprocnum,
                                               amproc.amproclefttype,
                                               amproc.amprocrighttype)
                     FROM pg_amproc amproc WHERE amproc.amprocfamily = opf.oid
                   ), '[]'::jsonb))
          FROM pg_opfamily opf
          JOIN pg_namespace n ON n.oid = opf.opfnamespace
          JOIN pg_am am ON am.oid = opf.opfmethod
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_opclass', am.amname || ':' || opc.opcname,
                 to_jsonb(opc) - 'oid' - 'opcnamespace'
          FROM pg_opclass opc
          JOIN pg_namespace n ON n.oid = opc.opcnamespace
          JOIN pg_am am ON am.oid = opc.opcmethod
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_collation', coll.collname || ':' || coll.collencoding::text,
                 to_jsonb(coll) - 'oid' - 'collnamespace'
          FROM pg_collation coll
          JOIN pg_namespace n ON n.oid = coll.collnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_conversion', con.conname,
                 to_jsonb(con) - 'oid' - 'connamespace'
          FROM pg_conversion con
          JOIN pg_namespace n ON n.oid = con.connamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_statistic_ext', stx.stxname,
                 (to_jsonb(stx) - 'oid' - 'stxnamespace') ||
                 jsonb_build_object(
                   'definition', pg_get_statisticsobjdef(stx.oid))
          FROM pg_statistic_ext stx
          JOIN pg_namespace n ON n.oid = stx.stxnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_ts_parser', prs.prsname,
                 to_jsonb(prs) - 'oid' - 'prsnamespace'
          FROM pg_ts_parser prs
          JOIN pg_namespace n ON n.oid = prs.prsnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_ts_dict', dict.dictname,
                 to_jsonb(dict) - 'oid' - 'dictnamespace'
          FROM pg_ts_dict dict
          JOIN pg_namespace n ON n.oid = dict.dictnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_ts_template', tmpl.tmplname,
                 to_jsonb(tmpl) - 'oid' - 'tmplnamespace'
          FROM pg_ts_template tmpl
          JOIN pg_namespace n ON n.oid = tmpl.tmplnamespace
          WHERE n.nspname = 'public'

          UNION ALL
          SELECT 'pg_ts_config', cfg.cfgname,
                 (to_jsonb(cfg) - 'oid' - 'cfgnamespace') ||
                 jsonb_build_object(
                   'mapping', COALESCE((
                     SELECT jsonb_agg(to_jsonb(mapping)
                                      ORDER BY mapping.maptokentype,
                                               mapping.mapseqno)
                     FROM pg_ts_config_map mapping
                     WHERE mapping.mapcfg = cfg.oid
                   ), '[]'::jsonb))
          FROM pg_ts_config cfg
          JOIN pg_namespace n ON n.oid = cfg.cfgnamespace
          WHERE n.nspname = 'public'
        ) executable
        ORDER BY catalog, object_identity
    """)
    event_triggers = _rows(cur, """
        SELECT evt.evtname AS name, evt.evtevent AS event,
               evt.evtenabled::text AS enabled,
               COALESCE(evt.evttags, ARRAY[]::text[]) AS tags,
               fn_ns.nspname AS function_schema, fn.proname AS function_name,
               pg_get_function_identity_arguments(fn.oid) AS function_arguments
        FROM pg_event_trigger evt
        JOIN pg_proc fn ON fn.oid = evt.evtfoid
        JOIN pg_namespace fn_ns ON fn_ns.oid = fn.pronamespace
        ORDER BY evt.evtname
    """)
    extensions = _rows(cur, """
        SELECT ext.extname AS name, ext.extversion AS version,
               owner.rolname AS owner, n.nspname AS schema,
               ext.extrelocatable AS relocatable
        FROM pg_extension ext
        JOIN pg_roles owner ON owner.oid = ext.extowner
        JOIN pg_namespace n ON n.oid = ext.extnamespace
        ORDER BY ext.extname
    """)
    casts = _rows(cur, """
        SELECT format_type(cst.castsource, NULL) AS source_type,
               format_type(cst.casttarget, NULL) AS target_type,
               cst.castcontext::text AS context,
               cst.castmethod::text AS method,
               fn_ns.nspname AS function_schema,
               fn.proname AS function_name,
               pg_get_function_identity_arguments(fn.oid) AS function_arguments
        FROM pg_cast cst
        LEFT JOIN pg_proc fn ON fn.oid = cst.castfunc
        LEFT JOIN pg_namespace fn_ns ON fn_ns.oid = fn.pronamespace
        ORDER BY format_type(cst.castsource, NULL),
                 format_type(cst.casttarget, NULL)
    """)
    transforms = _rows(cur, """
        SELECT format_type(transform.trftype, NULL) AS transformed_type,
               lang.lanname AS language,
               from_ns.nspname AS from_sql_function_schema,
               from_fn.proname AS from_sql_function_name,
               to_ns.nspname AS to_sql_function_schema,
               to_fn.proname AS to_sql_function_name
        FROM pg_transform transform
        JOIN pg_language lang ON lang.oid = transform.trflang
        LEFT JOIN pg_proc from_fn ON from_fn.oid = transform.trffromsql
        LEFT JOIN pg_namespace from_ns ON from_ns.oid = from_fn.pronamespace
        LEFT JOIN pg_proc to_fn ON to_fn.oid = transform.trftosql
        LEFT JOIN pg_namespace to_ns ON to_ns.oid = to_fn.pronamespace
        ORDER BY format_type(transform.trftype, NULL), lang.lanname
    """)
    access_methods = _rows(cur, """
        SELECT am.amname AS name, am.amtype::text AS type,
               fn_ns.nspname AS handler_schema, fn.proname AS handler_name,
               pg_get_function_identity_arguments(fn.oid) AS handler_arguments
        FROM pg_am am
        JOIN pg_proc fn ON fn.oid = am.amhandler
        JOIN pg_namespace fn_ns ON fn_ns.oid = fn.pronamespace
        ORDER BY am.amname
    """)
    languages = _rows(cur, """
        SELECT lang.lanname AS name, owner.rolname AS owner,
               lang.lanpltrusted AS trusted, lang.lanispl AS procedural,
               handler_ns.nspname AS handler_schema,
               handler.proname AS handler_name,
               inline_ns.nspname AS inline_schema,
               inline_fn.proname AS inline_name,
               validator_ns.nspname AS validator_schema,
               validator.proname AS validator_name, lang.lanacl AS acl
        FROM pg_language lang
        JOIN pg_roles owner ON owner.oid = lang.lanowner
        LEFT JOIN pg_proc handler ON handler.oid = lang.lanplcallfoid
        LEFT JOIN pg_namespace handler_ns ON handler_ns.oid = handler.pronamespace
        LEFT JOIN pg_proc inline_fn ON inline_fn.oid = lang.laninline
        LEFT JOIN pg_namespace inline_ns ON inline_ns.oid = inline_fn.pronamespace
        LEFT JOIN pg_proc validator ON validator.oid = lang.lanvalidator
        LEFT JOIN pg_namespace validator_ns ON validator_ns.oid = validator.pronamespace
        ORDER BY lang.lanname
    """)
    user_defined_casts = _rows(cur, """
        SELECT format_type(cst.castsource, NULL) AS source_type,
               format_type(cst.casttarget, NULL) AS target_type,
               cst.castcontext::text AS context,
               cst.castmethod::text AS method,
               fn_ns.nspname AS function_schema,
               fn.proname AS function_name,
               pg_get_function_identity_arguments(fn.oid) AS function_arguments,
               to_jsonb(cst) - 'oid' AS catalog_metadata
        FROM pg_cast cst
        LEFT JOIN pg_proc fn ON fn.oid = cst.castfunc
        LEFT JOIN pg_namespace fn_ns ON fn_ns.oid = fn.pronamespace
        WHERE cst.oid >= 16384
        ORDER BY format_type(cst.castsource, NULL),
                 format_type(cst.casttarget, NULL)
    """)
    user_defined_transforms = _rows(cur, """
        SELECT format_type(transform.trftype, NULL) AS transformed_type,
               lang.lanname AS language,
               from_ns.nspname AS from_sql_function_schema,
               from_fn.proname AS from_sql_function_name,
               to_ns.nspname AS to_sql_function_schema,
               to_fn.proname AS to_sql_function_name,
               to_jsonb(transform) - 'oid' AS catalog_metadata
        FROM pg_transform transform
        JOIN pg_language lang ON lang.oid = transform.trflang
        LEFT JOIN pg_proc from_fn ON from_fn.oid = transform.trffromsql
        LEFT JOIN pg_namespace from_ns ON from_ns.oid = from_fn.pronamespace
        LEFT JOIN pg_proc to_fn ON to_fn.oid = transform.trftosql
        LEFT JOIN pg_namespace to_ns ON to_ns.oid = to_fn.pronamespace
        WHERE transform.oid >= 16384
        ORDER BY format_type(transform.trftype, NULL), lang.lanname
    """)
    user_defined_access_methods = _rows(cur, """
        SELECT am.amname AS name, am.amtype::text AS type,
               fn_ns.nspname AS handler_schema, fn.proname AS handler_name,
               pg_get_function_identity_arguments(fn.oid) AS handler_arguments,
               to_jsonb(am) - 'oid' AS catalog_metadata
        FROM pg_am am
        JOIN pg_proc fn ON fn.oid = am.amhandler
        JOIN pg_namespace fn_ns ON fn_ns.oid = fn.pronamespace
        WHERE am.oid >= 16384
        ORDER BY am.amname
    """)
    user_defined_languages = _rows(cur, """
        SELECT lang.lanname AS name, lang.lanpltrusted AS trusted,
               lang.lanispl AS procedural,
               handler_ns.nspname AS handler_schema,
               handler.proname AS handler_name,
               inline_ns.nspname AS inline_schema,
               inline_fn.proname AS inline_name,
               validator_ns.nspname AS validator_schema,
               validator.proname AS validator_name,
               to_jsonb(lang) - 'oid' AS catalog_metadata
        FROM pg_language lang
        LEFT JOIN pg_proc handler ON handler.oid = lang.lanplcallfoid
        LEFT JOIN pg_namespace handler_ns ON handler_ns.oid = handler.pronamespace
        LEFT JOIN pg_proc inline_fn ON inline_fn.oid = lang.laninline
        LEFT JOIN pg_namespace inline_ns ON inline_ns.oid = inline_fn.pronamespace
        LEFT JOIN pg_proc validator ON validator.oid = lang.lanvalidator
        LEFT JOIN pg_namespace validator_ns ON validator_ns.oid = validator.pronamespace
        WHERE lang.oid >= 16384 AND lang.lanname <> 'plpgsql'
        ORDER BY lang.lanname
    """)
    document = {
        "catalogVersion": CATALOG_VERSION,
        "namespace": namespace,
        "relations": relations,
        "inheritance": inheritance,
        "columns": columns,
        "sequences": sequences,
        "types": types,
        "constraints": constraints,
        "indexes": indexes,
        "triggers": triggers,
        "internalConstraintTriggers": internal_constraint_triggers,
        "rules": rules,
        "functions": functions,
        "policies": policies,
        "grants": grants,
        "defaultGrants": default_grants,
        "namespaceObjectInventory": namespace_object_inventory,
        "executableCatalogObjects": executable_catalog_objects,
        "eventTriggers": event_triggers,
        "extensions": extensions,
        "casts": casts,
        "transforms": transforms,
        "accessMethods": access_methods,
        "languages": languages,
        "userDefinedCasts": user_defined_casts,
        "userDefinedTransforms": user_defined_transforms,
        "userDefinedAccessMethods": user_defined_access_methods,
        "userDefinedLanguages": user_defined_languages,
    }
    cur.execute(
        "SELECT pg_catalog.set_config('search_path', %s, true) AS search_path",
        (original_search_path,),
    )
    if cur.fetchone()["search_path"] != original_search_path:
        raise SchemaGuardError(
            "catalog verification could not restore the PostgreSQL search_path")
    return document


def _catalog_identity(cur) -> tuple[dict[str, Any], bytes, str]:
    document = postgres_catalog_document(cur)
    canonical = _canonical_json_bytes(document)
    return document, canonical, _sha256(canonical)


def _catalog_has_objects(document: dict[str, Any]) -> bool:
    # The public namespace and its default grants exist in a newly-created
    # database. Every listed category below represents a user schema object.
    return any(document[name] for name in (
        "relations", "inheritance", "columns", "sequences", "types", "constraints",
        "indexes", "triggers", "internalConstraintTriggers", "rules",
        "functions", "policies", "namespaceObjectInventory",
        "executableCatalogObjects", "eventTriggers", "userDefinedCasts",
        "userDefinedTransforms", "userDefinedAccessMethods",
        "userDefinedLanguages",
    ))


def _has_pristine_public_namespace(document: dict[str, Any]) -> bool:
    """Accept the PG15+ empty-public baseline for its provisioned owner only."""
    if (len(document["namespace"]) != 1
            or document["defaultGrants"]
            or [entry["name"] for entry in document["extensions"]] != ["plpgsql"]
            or document["eventTriggers"]
            or document["userDefinedCasts"]
            or document["userDefinedTransforms"]
            or document["userDefinedAccessMethods"]
            or document["userDefinedLanguages"]):
        return False
    namespace = document["namespace"][0]
    if namespace.get("name") != "public" or not namespace.get("owner"):
        return False
    owner = namespace["owner"]
    actual = {
        (
            row["object_kind"], row["object_name"], row["subobject_name"],
            row["grantor"], row["grantee"], row["privilege_type"],
            row["is_grantable"],
        )
        for row in document["grants"]
    }
    expected = {
        ("SCHEMA", "public", None, owner, owner, "CREATE", False),
        ("SCHEMA", "public", None, owner, owner, "USAGE", False),
        ("SCHEMA", "public", None, owner, "PUBLIC", "USAGE", False),
    }
    return actual == expected


def classify_schema(cur, verified: VerifiedStaticSchema) -> SchemaClassification:
    """Classify using catalog reads only; never repair or execute target DDL."""
    if cur.connection.info.transaction_status != \
            psycopg.pq.TransactionStatus.INTRANS:
        raise SchemaGuardError(
            "schema classification requires one active PostgreSQL transaction")
    _establish_schema_transaction_posture(cur)
    document, canonical, fingerprint = _catalog_identity(cur)
    base = dict(
        catalog_document=document,
        catalog_bytes=canonical,
        catalog_fingerprint=fingerprint,
    )
    if not _catalog_has_objects(document) \
            and _has_pristine_public_namespace(document):
        return SchemaClassification(
            SchemaState.EMPTY,
            "public contains no user schema objects",
            **base,
        )
    if not _catalog_has_objects(document):
        return SchemaClassification(
            SchemaState.OTHER,
            "public has no objects but its owner/default ACL posture, extension "
            "posture, or global executable-catalog posture is not the reviewed "
            "empty PostgreSQL baseline",
            **base,
        )

    ledger_relations = [
        row for row in document["relations"]
        if row["name"] == "runtime_schema_ledger" and row["kind"] == "r"
    ]
    if len(ledger_relations) != 1:
        return SchemaClassification(
            SchemaState.OTHER,
            "the protected runtime_schema_ledger table is absent or malformed",
            **base,
        )
    try:
        # A savepoint keeps a malformed/permission-denied ledger read from
        # poisoning the caller's classification transaction.
        with cur.connection.transaction():
            cur.execute(
                "SELECT ledger_key, schema_digest, catalog_fingerprint, "
                "catalog_document, catalog_bytes, byte_length "
                "FROM public.runtime_schema_ledger ORDER BY ledger_key"
            )
            ledger_rows = cur.fetchall()
    except psycopg.Error as exc:
        return SchemaClassification(
            SchemaState.OTHER,
            f"the protected schema ledger cannot be read exactly: {exc.sqlstate or exc}",
            **base,
        )
    if len(ledger_rows) != 1:
        return SchemaClassification(
            SchemaState.OTHER,
            "the protected schema ledger does not contain exactly one install receipt",
            **base,
        )
    row = ledger_rows[0]
    try:
        retained_bytes = bytes(row["catalog_bytes"])
    except (KeyError, TypeError, ValueError) as exc:
        return SchemaClassification(
            SchemaState.OTHER,
            f"the protected schema ledger bytes are malformed: {exc}",
            **base,
        )
    if (row["ledger_key"] != LEDGER_KEY
            or row["schema_digest"] != verified.schema_digest
            or row["catalog_fingerprint"] != fingerprint
            or retained_bytes != canonical
            or row["byte_length"] != len(canonical)
            or row["catalog_document"] != document
            or _sha256(retained_bytes) != row["catalog_fingerprint"]):
        return SchemaClassification(
            SchemaState.OTHER,
            "live pg_catalog state differs from the exact protected install receipt",
            **base,
        )
    return SchemaClassification(
        SchemaState.EXACT_CURRENT,
        "live pg_catalog state exactly matches the protected install receipt",
        **base,
    )


def _recreate_error(classification: SchemaClassification) -> SchemaGuardError:
    return SchemaGuardError(
        "target public schema is legacy, partial, or catalog-drifted; no DDL was "
        "executed. This pre-deployment build has no forward migration path: recreate "
        "the target database (or drop and recreate its public schema) and restart. "
        f"Classification detail: {classification.detail}"
    )


def ensure_schema(conn, verified: VerifiedStaticSchema) -> SchemaState:
    """Verify current schema or install exact verified DDL into an empty target."""
    # The first classification is explicitly read-only.  A legacy or drifted
    # target therefore reaches the recreate refusal before any DDL/DML.
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE, READ ONLY")
                initial = classify_schema(cur, verified)
    except psycopg.Error as exc:
        raise SchemaGuardError(
            f"target PostgreSQL schema could not be classified read-only: {exc}"
        ) from exc
    if initial.state is SchemaState.EXACT_CURRENT:
        return SchemaState.EXACT_CURRENT
    if initial.state is SchemaState.OTHER:
        raise _recreate_error(initial)

    # Empty installation is one transaction.  The advisory lock serializes
    # cooperating startup processes; the second read-only-style classification
    # inside that transaction closes the check/install race between them.
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                _establish_schema_transaction_posture(cur)
                cur.execute(
                    "SELECT pg_catalog.pg_advisory_xact_lock(%s)",
                    (_INSTALL_LOCK_KEY,),
                )
                hold_fingerprint_catalog_locks(cur)
                current = classify_schema(cur, verified)
                if current.state is SchemaState.EXACT_CURRENT:
                    return SchemaState.EXACT_CURRENT
                if current.state is SchemaState.OTHER:
                    raise _recreate_error(current)
                cur.execute("SET LOCAL search_path = public, pg_catalog")
                cur.execute(verified.schema_sql)
                document, canonical, fingerprint = _catalog_identity(cur)
                cur.execute(
                    "INSERT INTO public.runtime_schema_ledger "
                    "(ledger_key, schema_digest, catalog_fingerprint, "
                    "catalog_document, catalog_bytes, byte_length) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        LEDGER_KEY,
                        verified.schema_digest,
                        fingerprint,
                        Jsonb(document),
                        canonical,
                        len(canonical),
                    ),
                )
                installed = classify_schema(cur, verified)
                if installed.state is not SchemaState.EXACT_CURRENT:
                    raise SchemaGuardError(
                        "exact schema installation did not reproduce its protected "
                        f"catalog receipt: {installed.detail}"
                    )
    except SchemaGuardError:
        raise
    except psycopg.Error as exc:
        raise SchemaGuardError(
            f"exact schema installation failed atomically; target was rolled back: {exc}"
        ) from exc
    return SchemaState.EMPTY


def require_exact_schema(cur, verified: VerifiedStaticSchema) -> None:
    """Refuse runtime activation if catalog state drifted since installation."""
    classification = classify_schema(cur, verified)
    if classification.state is not SchemaState.EXACT_CURRENT:
        raise _recreate_error(classification)
