"""Tests for sql_guard.validate."""
from __future__ import annotations

from agent import sql_guard

ALLOWED = {"fct_orders", "dim_customers"}


def test_valid_select_passes():
    result = sql_guard.validate(
        "SELECT order_id, order_total FROM fct_orders LIMIT 10", ALLOWED, max_rows=200
    )
    assert result.ok is True
    assert "LIMIT 10" in result.safe_sql.upper()


def test_rejects_insert():
    result = sql_guard.validate(
        "INSERT INTO fct_orders (order_id) VALUES ('x')", ALLOWED, max_rows=200
    )
    assert result.ok is False
    assert "forbidden" in result.reason.lower() or "select" in result.reason.lower()


def test_rejects_delete():
    result = sql_guard.validate("DELETE FROM fct_orders WHERE order_id = 'x'", ALLOWED, max_rows=200)
    assert result.ok is False


def test_rejects_drop():
    result = sql_guard.validate("DROP TABLE fct_orders", ALLOWED, max_rows=200)
    assert result.ok is False


def test_rejects_multiple_statements():
    result = sql_guard.validate(
        "SELECT * FROM fct_orders; SELECT * FROM dim_customers;", ALLOWED, max_rows=200
    )
    assert result.ok is False
    assert "one sql statement" in result.reason.lower()


def test_rejects_table_not_in_catalog():
    result = sql_guard.validate("SELECT * FROM internal_secrets", ALLOWED, max_rows=200)
    assert result.ok is False
    assert "internal_secrets" in result.reason


def test_injects_limit_when_missing():
    result = sql_guard.validate("SELECT order_id FROM fct_orders", ALLOWED, max_rows=50)
    assert result.ok is True
    assert "LIMIT 50" in result.safe_sql.upper()


def test_tightens_limit_that_exceeds_max():
    result = sql_guard.validate(
        "SELECT order_id FROM fct_orders LIMIT 5000", ALLOWED, max_rows=50
    )
    assert result.ok is True
    assert "LIMIT 50" in result.safe_sql.upper()
    assert "5000" not in result.safe_sql


def test_preserves_limit_already_under_max():
    result = sql_guard.validate("SELECT order_id FROM fct_orders LIMIT 3", ALLOWED, max_rows=200)
    assert result.ok is True
    assert "LIMIT 3" in result.safe_sql.upper()


def test_rejects_unparseable_sql():
    result = sql_guard.validate("SELEKT * FORM fct_orders", ALLOWED, max_rows=200)
    assert result.ok is False
