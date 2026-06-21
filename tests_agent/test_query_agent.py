"""Tests for query_agent.ask using a stubbed Groq client and a fake adapter."""
from __future__ import annotations

import json

import pytest

from agent.catalog import Catalog, ColumnInfo, MartInfo
from agent.config import AgentConfig
from agent.db_adapters.base import AdapterQueryError
from agent.query_agent import QueryAgentError, ask


def make_cfg(**overrides) -> AgentConfig:
    base = dict(
        groq_api_key="test-key",
        groq_model="llama-3.3-70b-versatile",
        max_attempts=3,
        max_rows=200,
        db_target="duckdb",
        duckdb_path="/tmp/test.duckdb",
        manifest_path="/tmp/manifest.json",
        snowflake_account=None,
        snowflake_user=None,
        snowflake_password=None,
        snowflake_warehouse=None,
        snowflake_database=None,
        snowflake_schema=None,
        snowflake_role=None,
    )
    base.update(overrides)
    return AgentConfig(**base)


def make_catalog() -> Catalog:
    return Catalog(
        marts=[
            MartInfo(
                name="fct_orders",
                relation_name=None,
                schema_name="marts",
                description="Orders fact table.",
                columns=[
                    ColumnInfo("order_id", "varchar", "PK"),
                    ColumnInfo("order_total", "numeric", "Total in USD"),
                ],
            )
        ]
    )


class FakeAdapter:
    def __init__(self, fail_once: bool = False):
        self.fail_once = fail_once
        self.calls = 0

    def execute(self, sql):
        self.calls += 1
        if self.fail_once and self.calls == 1:
            raise AdapterQueryError("column 'order_totl' does not exist")
        return ["order_id", "order_total"], [("o1", 100.0)]


def test_ask_succeeds_on_first_attempt(monkeypatch):
    response = json.dumps(
        {"sql": "SELECT order_id, order_total FROM fct_orders LIMIT 10", "explanation": "Lists orders."}
    )
    monkeypatch.setattr("agent.query_agent.chat", lambda *a, **k: response)

    cfg = make_cfg()
    catalog = make_catalog()
    adapter = FakeAdapter()

    result = ask("show me all orders", cfg, catalog, adapter)

    assert result.attempts == 1
    assert result.columns == ["order_id", "order_total"]
    assert result.history[0].status == "ok"


def test_ask_rejects_disallowed_table_then_self_corrects(monkeypatch):
    calls = []

    def fake_chat(api_key, model, messages, temperature=0.1):
        calls.append(messages)
        if len(calls) == 1:
            return json.dumps(
                {"sql": "SELECT * FROM internal_secrets", "explanation": "wrong table"}
            )
        return json.dumps(
            {"sql": "SELECT order_id FROM fct_orders LIMIT 10", "explanation": "corrected"}
        )

    monkeypatch.setattr("agent.query_agent.chat", fake_chat)

    cfg = make_cfg()
    catalog = make_catalog()
    adapter = FakeAdapter()

    result = ask("show me secrets", cfg, catalog, adapter)

    assert result.attempts == 2
    assert result.history[0].status == "rejected"
    assert result.history[1].status == "ok"
    # The retry message must include the guard's rejection reason so the
    # model has something concrete to correct.
    assert "internal_secrets" in calls[1][-1]["content"]


def test_ask_self_corrects_after_execution_error(monkeypatch):
    response = json.dumps(
        {"sql": "SELECT order_id, order_totl FROM fct_orders LIMIT 10", "explanation": "typo'd column"}
    )
    monkeypatch.setattr("agent.query_agent.chat", lambda *a, **k: response)

    cfg = make_cfg()
    catalog = make_catalog()
    adapter = FakeAdapter(fail_once=True)

    result = ask("show me orders", cfg, catalog, adapter)

    assert result.attempts == 2
    assert result.history[0].status == "failed"
    assert "order_totl" in result.history[0].detail


def test_ask_raises_after_exhausting_budget(monkeypatch):
    response = json.dumps({"sql": "SELECT * FROM internal_secrets", "explanation": "still wrong"})
    monkeypatch.setattr("agent.query_agent.chat", lambda *a, **k: response)

    cfg = make_cfg(max_attempts=2)
    catalog = make_catalog()
    adapter = FakeAdapter()

    with pytest.raises(QueryAgentError):
        ask("show me secrets", cfg, catalog, adapter)


def test_ask_raises_when_model_declines_to_answer(monkeypatch):
    response = json.dumps({"sql": "", "explanation": "No mart contains weather data."})
    monkeypatch.setattr("agent.query_agent.chat", lambda *a, **k: response)

    cfg = make_cfg()
    catalog = make_catalog()
    adapter = FakeAdapter()

    with pytest.raises(QueryAgentError, match="weather"):
        ask("what's the weather today", cfg, catalog, adapter)
