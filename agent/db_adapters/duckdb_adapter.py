"""DuckDB adapter — used for local dev, CI, and the public-facing demo.
Opened read-only so the adapter can't write even if a query somehow slipped
past the SQL guard."""
from __future__ import annotations

import duckdb

from agent.db_adapters.base import AdapterQueryError


class DuckDBAdapter:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        try:
            with duckdb.connect(self._db_path, read_only=True) as conn:
                result = conn.execute(sql)
                columns = [desc[0] for desc in result.description]
                rows = result.fetchall()
                return columns, rows
        except duckdb.Error as exc:
            raise AdapterQueryError(str(exc)) from exc
