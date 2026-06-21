"""Ground the agent in real schema metadata by reading dbt's manifest.json
(produced by `dbt docs generate`) instead of a hand-maintained schema file
that inevitably drifts from the actual marts.

Only models tagged or pathed as marts are exposed to the agent — staging
and intermediate models stay out of scope, same as they would for an
analyst querying the warehouse directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str | None
    description: str


@dataclass(frozen=True)
class MartInfo:
    name: str
    relation_name: str | None  # fully qualified name from manifest, if present
    schema_name: str | None  # schema where the model lives (e.g. "marts", "marts_finance")
    description: str
    columns: list[ColumnInfo] = field(default_factory=list)


@dataclass(frozen=True)
class Catalog:
    marts: list[MartInfo]

    @property
    def allowed_table_names(self) -> set[str]:
        """Bare (unqualified) lowercase model names the agent may query.

        Matching on the bare name rather than a fully qualified
        db.schema.table path keeps the same generated SQL portable between
        the DuckDB dev/demo backend and the Snowflake prod backend, which
        live in different schemas. The tradeoff — losing per-environment
        qualification — is documented in the README as a known v1
        simplification.
        """
        return {mart.name.lower() for mart in self.marts}

    @property
    def table_schema_map(self) -> dict[str, str]:
        """Map bare table name → schema name for SQL qualification."""
        return {
            mart.name.lower(): mart.schema_name
            for mart in self.marts
            if mart.schema_name
        }

    def to_prompt_context(self) -> str:
        """Render a compact schema description for the LLM's system prompt."""
        blocks = []
        for mart in self.marts:
            col_lines = "\n".join(
                f"  - {col.name} ({col.data_type or 'unknown'}): "
                f"{col.description or 'no description'}"
                for col in mart.columns
            )
            blocks.append(
                f"### {mart.name}\n{mart.description or 'No description.'}\n{col_lines}"
            )
        return "\n\n".join(blocks)


def load_catalog(manifest_path: str, marts_path_prefix: str = "marts/") -> Catalog:
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    marts: list[MartInfo] = []
    for node in manifest.get("nodes", {}).values():
        if node.get("resource_type") != "model":
            continue
        path = node.get("path", "")
        tags = node.get("tags", [])
        is_mart = path.startswith(marts_path_prefix) or "marts" in tags
        if not is_mart:
            continue

        columns = [
            ColumnInfo(
                name=col_name,
                data_type=col_meta.get("data_type"),
                description=col_meta.get("description", ""),
            )
            for col_name, col_meta in node.get("columns", {}).items()
        ]
        marts.append(
            MartInfo(
                name=node.get("name", ""),
                relation_name=node.get("relation_name"),
                schema_name=node.get("schema"),
                description=node.get("description", ""),
                columns=columns,
            )
        )

    return Catalog(marts=marts)
