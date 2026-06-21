"""Tests for the DB adapters.

DuckDB is tested against a real temp database file (it's an embedded
engine, so this costs nothing and isn't really an integration test in the
"needs live infra" sense). Snowflake is tested with a fake module injected
into sys.modules, since snowflake-connector-python is a heavy optional
dependency that the DuckDB-only demo/CI path shouldn't need installed.
"""
from __future__ import annotations

import sys
import types

import duckdb
import pytest

from agent.db_adapters.base import AdapterQueryError
from agent.db_adapters.duckdb_adapter import DuckDBAdapter


@pytest.fixture
def seeded_duckdb_path(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    conn = duckdb.connect(db_path)
    conn.execute("CREATE TABLE fct_orders (order_id VARCHAR, order_total DOUBLE)")
    conn.execute("INSERT INTO fct_orders VALUES ('o1', 100.0), ('o2', 250.5)")
    conn.close()
    return db_path


def test_duckdb_adapter_executes_select(seeded_duckdb_path):
    adapter = DuckDBAdapter(seeded_duckdb_path)
    columns, rows = adapter.execute("SELECT order_id, order_total FROM fct_orders ORDER BY order_id")

    assert columns == ["order_id", "order_total"]
    assert rows == [("o1", 100.0), ("o2", 250.5)]


def test_duckdb_adapter_raises_adapter_error_on_bad_sql(seeded_duckdb_path):
    adapter = DuckDBAdapter(seeded_duckdb_path)
    with pytest.raises(AdapterQueryError):
        adapter.execute("SELECT not_a_real_column FROM fct_orders")


def test_duckdb_adapter_is_read_only(seeded_duckdb_path):
    adapter = DuckDBAdapter(seeded_duckdb_path)
    with pytest.raises(AdapterQueryError):
        adapter.execute("INSERT INTO fct_orders VALUES ('o3', 1.0)")


def test_snowflake_adapter_executes_select(monkeypatch):
    captured = {}

    class FakeCursor:
        description = [("ORDER_ID",), ("ORDER_TOTAL",)]

        def execute(self, sql):
            captured["sql"] = sql

        def fetchall(self):
            return [("o1", 100.0)]

        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    class FakeErrors:
        class ProgrammingError(Exception):
            pass

    def fake_connect(**kwargs):
        captured["conn_kwargs"] = kwargs
        return FakeConn()

    fake_module = types.ModuleType("snowflake.connector")
    fake_module.connect = fake_connect
    fake_module.errors = FakeErrors()

    fake_parent = types.ModuleType("snowflake")
    fake_parent.connector = fake_module

    monkeypatch.setitem(sys.modules, "snowflake", fake_parent)
    monkeypatch.setitem(sys.modules, "snowflake.connector", fake_module)

    from agent.db_adapters.snowflake_adapter import SnowflakeAdapter

    adapter = SnowflakeAdapter(
        account="acct",
        user="user",
        password="pw",
        warehouse="wh",
        database="db",
        schema="marts_core",
    )
    columns, rows = adapter.execute("SELECT order_id, order_total FROM fct_orders")

    assert columns == ["ORDER_ID", "ORDER_TOTAL"]
    assert rows == [("o1", 100.0)]
    assert captured["sql"] == "SELECT order_id, order_total FROM fct_orders"
