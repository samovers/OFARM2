"""Shared PostgreSQL 17.10 schema-local catalog classifier.

PostgreSQL stores schema-local objects in several catalogs with different
namespace and name columns.  Keep that mapping in one place so fresh-target
and migration-boundary scans cannot silently diverge.  Migration-owned SQL
verifiers mirror this fixed list and their tests require exact parity.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SchemaLocalCatalogClass:
    """One schema-local PostgreSQL catalog class and its identifying columns."""

    category: str
    catalog_name: str
    namespace_column: str
    name_column: str


SCHEMA_LOCAL_CATALOG_CLASSES = (
    SchemaLocalCatalogClass("relation", "pg_class", "relnamespace", "relname"),
    SchemaLocalCatalogClass("routine", "pg_proc", "pronamespace", "proname"),
    SchemaLocalCatalogClass("type", "pg_type", "typnamespace", "typname"),
    SchemaLocalCatalogClass(
        "collation", "pg_collation", "collnamespace", "collname"
    ),
    SchemaLocalCatalogClass("operator", "pg_operator", "oprnamespace", "oprname"),
    SchemaLocalCatalogClass(
        "operator_class", "pg_opclass", "opcnamespace", "opcname"
    ),
    SchemaLocalCatalogClass(
        "operator_family", "pg_opfamily", "opfnamespace", "opfname"
    ),
    SchemaLocalCatalogClass(
        "conversion", "pg_conversion", "connamespace", "conname"
    ),
    SchemaLocalCatalogClass(
        "text_search_config", "pg_ts_config", "cfgnamespace", "cfgname"
    ),
    SchemaLocalCatalogClass(
        "text_search_dictionary", "pg_ts_dict", "dictnamespace", "dictname"
    ),
    SchemaLocalCatalogClass(
        "text_search_parser", "pg_ts_parser", "prsnamespace", "prsname"
    ),
    SchemaLocalCatalogClass(
        "text_search_template", "pg_ts_template", "tmplnamespace", "tmplname"
    ),
    SchemaLocalCatalogClass(
        "statistics", "pg_statistic_ext", "stxnamespace", "stxname"
    ),
)


def _schema_local_select(item: SchemaLocalCatalogClass) -> str:
    return f"""SELECT '{item.category}', namespace.nspname::text,
               object_name.{item.name_column}::text
        FROM pg_catalog.{item.catalog_name} AS object_name
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = object_name.{item.namespace_column}
        WHERE namespace.nspname IN (SELECT schema_name FROM target_names)"""


SCHEMA_LOCAL_OBJECT_SELECTS_SQL = "\n        UNION ALL\n        ".join(
    _schema_local_select(item) for item in SCHEMA_LOCAL_CATALOG_CLASSES
)


__all__ = (
    "SCHEMA_LOCAL_CATALOG_CLASSES",
    "SCHEMA_LOCAL_OBJECT_SELECTS_SQL",
    "SchemaLocalCatalogClass",
)
