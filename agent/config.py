"""Configuration for the NL-to-SQL agent.

DB_TARGET selects the execution backend: 'duckdb' for local dev / CI / the
public demo (zero-cost, no credentials), or 'snowflake' for querying live
prod marts. Both adapters share the same interface, so the agent code never
branches on which one is active.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    groq_api_key: str
    groq_model: str
    max_attempts: int
    max_rows: int
    db_target: str  # "duckdb" | "snowflake"
    duckdb_path: str
    manifest_path: str
    snowflake_account: str | None
    snowflake_user: str | None
    snowflake_password: str | None
    snowflake_warehouse: str | None
    snowflake_database: str | None
    snowflake_schema: str | None
    snowflake_role: str | None

    @classmethod
    def from_env(cls) -> "AgentConfig":
        db_target = os.getenv("DB_TARGET", "duckdb").lower()
        if db_target not in {"duckdb", "snowflake"}:
            raise RuntimeError(f"Invalid DB_TARGET: {db_target!r} (expected duckdb|snowflake)")

        return cls(
            groq_api_key=_require_env("GROQ_API_KEY"),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            max_attempts=int(os.getenv("AGENT_MAX_ATTEMPTS", "3")),
            max_rows=int(os.getenv("AGENT_MAX_ROWS", "200")),
            db_target=db_target,
            duckdb_path=os.getenv("DUCKDB_PATH", "dev.duckdb"),
            manifest_path=os.getenv("DBT_MANIFEST_PATH", "target/manifest.json"),
            snowflake_account=os.getenv("SNOWFLAKE_ACCOUNT"),
            snowflake_user=os.getenv("SNOWFLAKE_USER"),
            snowflake_password=os.getenv("SNOWFLAKE_PASSWORD"),
            snowflake_warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            snowflake_database=os.getenv("SNOWFLAKE_DATABASE"),
            snowflake_schema=os.getenv("SNOWFLAKE_SCHEMA"),
            snowflake_role=os.getenv("SNOWFLAKE_ROLE"),
        )


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
