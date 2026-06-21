"""The agent loop: ask the model for SQL, validate it, execute it, and if
either step fails, feed the error back and retry — bounded by max_attempts.

This is the agentic core of the project. It isn't tool-calling; it's a
generate -> validate -> execute -> self-correct cycle where the environment
(the SQL guard, the database) is the source of feedback the model reasons
over between attempts.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from agent import sql_guard
from agent.catalog import Catalog
from agent.config import AgentConfig
from agent.db_adapters.base import AdapterQueryError, DBAdapter
from agent.groq_client import chat
from agent.prompts import build_retry_prompt, build_system_prompt
from agent.sql_guard import qualify_tables

logger = logging.getLogger(__name__)


class QueryAgentError(RuntimeError):
    """Raised when the agent exhausts its attempt budget without producing
    a valid, executable query."""


@dataclass(frozen=True)
class AttemptRecord:
    attempt: int
    status: str  # "rejected" | "failed" | "ok"
    detail: str


@dataclass(frozen=True)
class QueryResult:
    sql: str
    explanation: str
    columns: list[str]
    rows: list[tuple]
    attempts: int
    history: list[AttemptRecord]


def ask(
    question: str,
    cfg: AgentConfig,
    catalog: Catalog,
    adapter: DBAdapter,
) -> QueryResult:
    dialect = "snowflake" if cfg.db_target == "snowflake" else "duckdb"
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(catalog.to_prompt_context(), dialect)},
        {"role": "user", "content": question},
    ]

    history: list[AttemptRecord] = []
    last_sql = ""
    last_error = ""

    for attempt in range(1, cfg.max_attempts + 1):
        raw = chat(cfg.groq_api_key, cfg.groq_model, messages, temperature=0.1)
        parsed = _parse_response(raw)
        candidate_sql = parsed.get("sql", "") or ""
        explanation = parsed.get("explanation", "")

        if not candidate_sql.strip():
            # Model decided the question can't be answered from the catalog.
            raise QueryAgentError(explanation or "Question cannot be answered from available marts.")

        guard_result = sql_guard.validate(
            candidate_sql, catalog.allowed_table_names, cfg.max_rows, dialect=dialect
        )
        if not guard_result.ok:
            last_sql, last_error = candidate_sql, guard_result.reason or "SQL guard rejected query."
            history.append(AttemptRecord(attempt=attempt, status="rejected", detail=last_error))
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": build_retry_prompt(last_sql, last_error)})
            logger.info("Attempt %s rejected by guard: %s", attempt, last_error)
            continue

        # Qualify bare table names with their schema before execution
        executable_sql = qualify_tables(
            guard_result.safe_sql, catalog.table_schema_map, dialect=dialect
        )

        try:
            columns, rows = adapter.execute(executable_sql)
        except AdapterQueryError as exc:
            last_sql, last_error = candidate_sql, str(exc)
            history.append(AttemptRecord(attempt=attempt, status="failed", detail=last_error))
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": build_retry_prompt(last_sql, last_error)})
            logger.info("Attempt %s failed execution: %s", attempt, last_error)
            continue

        history.append(AttemptRecord(attempt=attempt, status="ok", detail="Executed successfully."))
        return QueryResult(
            sql=executable_sql,
            explanation=explanation,
            columns=columns,
            rows=rows,
            attempts=attempt,
            history=history,
        )

    raise QueryAgentError(
        f"Could not produce a valid, executable query within {cfg.max_attempts} attempts. "
        f"Last error: {last_error}"
    )


def _parse_response(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise QueryAgentError(f"Model did not return valid JSON: {raw[:200]}") from exc
