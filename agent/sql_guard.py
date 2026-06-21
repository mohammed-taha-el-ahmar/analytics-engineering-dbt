"""Enforce that any SQL the agent wants to run is a single, read-only SELECT
against tables the catalog actually exposes — and that it can't return an
unbounded number of rows.

This is the gate between "an LLM wrote some SQL" and "that SQL touches a
real database." Nothing reaches the adapter without passing through here.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

# Statement types that must never appear, anywhere in the parsed tree —
# not just as the top-level statement, since a malicious/confused
# generation could nest one inside a CTE or subquery.
FORBIDDEN_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Grant,
    exp.Merge,
)


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reason: str | None = None
    safe_sql: str | None = None  # original SQL with a LIMIT enforced


def validate(sql: str, allowed_tables: set[str], max_rows: int, dialect: str = "duckdb") -> GuardResult:
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except Exception as exc:  # noqa: BLE001 - any parse failure is a guard rejection
        return GuardResult(ok=False, reason=f"SQL did not parse: {exc}")

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        return GuardResult(ok=False, reason="Exactly one SQL statement is required.")

    root = statements[0]

    if not isinstance(root, exp.Select):
        return GuardResult(ok=False, reason="Only SELECT statements are permitted.")

    for forbidden in FORBIDDEN_EXPRESSIONS:
        if list(root.find_all(forbidden)):
            return GuardResult(
                ok=False, reason=f"Statement contains a forbidden operation: {forbidden.__name__}"
            )

    referenced = {table.name.lower() for table in root.find_all(exp.Table)}
    disallowed = referenced - allowed_tables
    if disallowed:
        return GuardResult(
            ok=False,
            reason=(
                f"Query references table(s) not in the mart catalog: "
                f"{', '.join(sorted(disallowed))}"
            ),
        )

    safe_root = _enforce_limit(root, max_rows)
    return GuardResult(ok=True, safe_sql=safe_root.sql(dialect=dialect))


def _enforce_limit(root: exp.Select, max_rows: int) -> exp.Select:
    """Cap the result set, tightening an existing LIMIT if needed but never
    loosening one the model already set lower."""
    existing = root.args.get("limit")
    if existing is not None:
        try:
            existing_value = int(existing.expression.this)
        except (AttributeError, ValueError, TypeError):
            existing_value = max_rows
        if existing_value <= max_rows:
            return root
    return root.limit(max_rows)


def qualify_tables(sql: str, table_schema_map: dict[str, str], dialect: str = "duckdb") -> str:
    """Rewrite bare table names in the SQL to schema-qualified names.

    E.g. 'SELECT * FROM fct_orders' → 'SELECT * FROM marts.fct_orders'
    This is needed because DuckDB and Snowflake both require schema-qualified
    names when models aren't in the default schema.
    """
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except Exception:  # noqa: BLE001
        return sql  # can't parse → return unchanged, let execution fail naturally

    if not statements or statements[0] is None:
        return sql

    root = statements[0]
    for table in root.find_all(exp.Table):
        bare_name = table.name.lower()
        # Only qualify if it's a bare name (no schema already set)
        if bare_name in table_schema_map and not table.args.get("db") and not table.args.get("catalog"):
            schema = table_schema_map[bare_name]
            table.set("db", exp.to_identifier(schema))

    return root.sql(dialect=dialect)
