"""Build the configured DB adapter from AgentConfig without the rest of the
codebase needing to know which backend is active."""
from __future__ import annotations

from agent.config import AgentConfig
from agent.db_adapters.base import DBAdapter
from agent.db_adapters.duckdb_adapter import DuckDBAdapter


def build_adapter(cfg: AgentConfig) -> DBAdapter:
    if cfg.db_target == "duckdb":
        return DuckDBAdapter(cfg.duckdb_path)

    if cfg.db_target == "snowflake":
        from agent.db_adapters.snowflake_adapter import SnowflakeAdapter  # noqa: PLC0415

        missing = [
            name
            for name, value in [
                ("SNOWFLAKE_ACCOUNT", cfg.snowflake_account),
                ("SNOWFLAKE_USER", cfg.snowflake_user),
                ("SNOWFLAKE_PASSWORD", cfg.snowflake_password),
                ("SNOWFLAKE_WAREHOUSE", cfg.snowflake_warehouse),
                ("SNOWFLAKE_DATABASE", cfg.snowflake_database),
                ("SNOWFLAKE_SCHEMA", cfg.snowflake_schema),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing Snowflake env vars: {', '.join(missing)}")

        return SnowflakeAdapter(
            account=cfg.snowflake_account,
            user=cfg.snowflake_user,
            password=cfg.snowflake_password,
            warehouse=cfg.snowflake_warehouse,
            database=cfg.snowflake_database,
            schema=cfg.snowflake_schema,
            role=cfg.snowflake_role,
        )

    raise RuntimeError(f"Unknown db_target: {cfg.db_target}")
