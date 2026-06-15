# Convenience wrappers around `uv run dbt ...`.
# All commands assume ~/.dbt/profiles.yml is configured (see profiles.yml.example).

.PHONY: install deps seed run test build docs docs-serve clean full-refresh local-test lint ci

# Install Python deps (dbt-core + dbt-snowflake) into .venv via uv
install:
	uv sync

# Install dbt packages (dbt_utils) defined in packages.yml
deps:
	uv run dbt deps

# Load seed CSVs as the "raw" tables
seed:
	uv run dbt seed

# Build all models (staging -> intermediate -> marts)
run:
	uv run dbt run

# Run all tests (schema tests + custom singular tests)
test:
	uv run dbt test

# seed + run + test in dependency order, stopping on first failure
build:
	uv run dbt build

# Full rebuild of the incremental finance model (e.g. after a logic change)
full-refresh:
	uv run dbt run --full-refresh -s fct_daily_revenue

# Generate the docs site (data catalog + lineage graph)
docs:
	uv run dbt docs generate

# Serve the docs site locally at http://localhost:8080
docs-serve: docs
	uv run dbt docs serve --port 8080

# Remove dbt artifacts and installed packages
clean:
	uv run dbt clean

# Run the whole project locally against DuckDB instead of Snowflake.
# Requires: uv sync --extra dev, and a `local` target in profiles.yml
# (type: duckdb, path: ./dev.duckdb). See README "Testing locally" section.
local-test:
	uv run dbt build --target local

# Lint SQL with sqlfluff (dbt templater, compiled via the `local` target)
lint:
	uv run sqlfluff lint models tests macros

# Mirrors the CI workflow end-to-end, locally
ci:
	uv sync --extra dev
	uv run dbt deps
	$(MAKE) lint
	$(MAKE) local-test
