"""Snowflake adapter — used against live prod marts.

The snowflake-connector-python import is deliberately lazy: the public demo
and CI only ever exercise the DuckDB path, so they shouldn't need the
Snowflake driver installed at all. It's only imported when this adapter is
actually instantiated.
"""
from __future__ import annotations

from agent.db_adapters.base import AdapterQueryError


class SnowflakeAdapter:
    def __init__(
        self,
        account: str,
        user: str,
        password: str,
        warehouse: str,
        database: str,
        schema: str,
        role: str | None = None,
    ):
        try:
            import snowflake.connector  # noqa: PLC0415 - intentionally lazy
        except ImportError as exc:
            raise RuntimeError(
                "snowflake-connector-python is required for DB_TARGET=snowflake. "
                "Install it with: pip install snowflake-connector-python"
            ) from exc

        self._connector = snowflake.connector
        self._conn_kwargs = dict(
            account=account,
            user=user,
            password=password,
            warehouse=warehouse,
            database=database,
            schema=schema,
            role=role,
            # Read-only intent at the session level, on top of the SQL guard.
            session_parameters={"QUERY_TAG": "nl_sql_agent_readonly"},
        )

    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        conn = self._connector.connect(**self._conn_kwargs)
        try:
            cur = conn.cursor()
            try:
                cur.execute(sql)
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return columns, rows
            except self._connector.errors.ProgrammingError as exc:
                raise AdapterQueryError(str(exc)) from exc
            finally:
                cur.close()
        finally:
            conn.close()
