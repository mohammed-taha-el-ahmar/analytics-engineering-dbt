# Commands Reference

All commands assume you are in the project root and have run `uv sync` at
least once.

---

## Makefile shortcuts

| Command | What it does |
|---------|-------------|
| `make install` | Install Python deps (dbt-core + dbt-snowflake) into `.venv` via `uv` |
| `make deps` | Install dbt packages (dbt_utils) from `packages.yml` |
| `make seed` | Load seed CSVs into the RAW schema |
| `make run` | Build all models (staging → intermediate → marts) |
| `make test` | Run all tests (schema + singular) |
| `make build` | seed + run + test in dependency order |
| `make full-refresh` | Full rebuild of `fct_daily_revenue` (incremental model) |
| `make docs` | Generate the docs site (catalog + lineage graph) |
| `make docs-serve` | Serve docs locally at `http://localhost:8080` |
| `make clean` | Remove dbt artifacts and installed packages |
| `make local-test` | Run the full project against DuckDB (no Snowflake needed) |
| `make lint` | Lint SQL with sqlfluff (dbt templater) |
| `make ci` | Full CI pipeline locally: sync dev deps → lint → DuckDB build |

---

## dbt commands (raw)

These are the underlying commands the Makefile wraps.

### Project setup

```bash
# Install Python dependencies
uv sync                   # production deps (dbt-core + dbt-snowflake)
uv sync --extra dev       # + dbt-duckdb + sqlfluff

# Install dbt packages
uv run dbt deps

# Verify connection to Snowflake/DuckDB
uv run dbt debug
uv run dbt debug --target local   # DuckDB
```

### Building models

```bash
# Run all models
uv run dbt run

# Run a specific model
uv run dbt run -s stg_orders

# Run a model and all its downstream dependents
uv run dbt run -s stg_orders+

# Run all models in a folder
uv run dbt run -s staging.*

# Run against DuckDB locally
uv run dbt run --target local

# Full refresh an incremental model
uv run dbt run --full-refresh -s fct_daily_revenue
```

### Seeds

```bash
# Load all seed CSVs
uv run dbt seed

# Load a specific seed
uv run dbt seed -s raw_customers
```

### Testing

```bash
# Run all tests
uv run dbt test

# Run tests for a specific model
uv run dbt test -s stg_orders

# Run only singular (custom SQL) tests
uv run dbt test -s test_type:singular

# Run only schema (generic) tests
uv run dbt test -s test_type:generic
```

### Build (seed + run + test combined)

```bash
# Full build (recommended)
uv run dbt build

# Build just staging layer
uv run dbt build -s staging.*

# Build a model and everything upstream
uv run dbt build -s +fct_daily_revenue
```

### Documentation

```bash
# Generate docs
uv run dbt docs generate

# Serve docs locally
uv run dbt docs serve --port 8080
```

### Utility

```bash
# List all models
uv run dbt ls --resource-type model

# List all tests
uv run dbt ls --resource-type test

# List all sources
uv run dbt ls --resource-type source

# Show compiled SQL for a model
uv run dbt show -s fct_orders --limit 5

# Compile (generate SQL without running)
uv run dbt compile -s fct_orders
```

---

## sqlfluff (SQL linting)

```bash
# Lint all SQL files
uv run sqlfluff lint models tests macros

# Fix auto-fixable issues
uv run sqlfluff fix models tests macros

# Lint a specific file
uv run sqlfluff lint models/staging/stg_orders.sql
```

---

## Model selection syntax cheatsheet

| Selector | Meaning |
|----------|---------|
| `model_name` | A specific model |
| `+model_name` | The model and all its ancestors (upstream) |
| `model_name+` | The model and all its descendants (downstream) |
| `+model_name+` | Full lineage (upstream + model + downstream) |
| `staging.*` | All models in the staging folder |
| `tag:finance` | All models with the `finance` tag |
| `source:jaffle_shop.*` | All models reading from the `jaffle_shop` source |
