"""Tests for catalog.load_catalog against a fixture dbt manifest."""
from __future__ import annotations

import os

from agent.catalog import load_catalog

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "manifest.json")


def test_load_catalog_only_includes_marts():
    catalog = load_catalog(FIXTURE)
    names = {m.name for m in catalog.marts}

    assert names == {"fct_orders", "dim_customers"}
    assert "stg_orders" not in names
    assert "raw_orders_seed" not in names


def test_load_catalog_captures_column_metadata():
    catalog = load_catalog(FIXTURE)
    fct_orders = next(m for m in catalog.marts if m.name == "fct_orders")

    col_names = {c.name for c in fct_orders.columns}
    assert col_names == {"order_id", "customer_id", "order_total", "order_date"}

    order_total = next(c for c in fct_orders.columns if c.name == "order_total")
    assert order_total.data_type == "numeric"
    assert "USD" in order_total.description


def test_allowed_table_names_are_lowercase_bare_names():
    catalog = load_catalog(FIXTURE)
    assert catalog.allowed_table_names == {"fct_orders", "dim_customers"}


def test_prompt_context_includes_table_and_column_info():
    catalog = load_catalog(FIXTURE)
    context = catalog.to_prompt_context()

    assert "fct_orders" in context
    assert "dim_customers" in context
    assert "order_total" in context
    assert "customer_name" in context
