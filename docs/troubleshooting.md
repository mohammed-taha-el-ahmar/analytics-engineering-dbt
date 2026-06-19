# Troubleshooting

Common issues and their solutions.

---

## DuckDB

### `error: Failed to spawn: 'duckdb'` / `command not found: duckdb`

**Cause:** The DuckDB CLI binary is not installed on your system. The Python
`duckdb` package (used by `dbt-duckdb`) is a library — it does not ship a
standalone CLI executable.

**Fix:**

```bash
# macOS
brew install duckdb

# Or download from https://duckdb.org/docs/installation/
```

After installing, verify:

```bash
duckdb --version
```

### `Table with name stg_customers does not exist!`

**Cause:** Models are in custom schemas, not in `main`. DuckDB's error
message usually hints at the correct path:
`Did you mean "staging.stg_customers"?`

**Fix:** Always qualify table names with their schema:

```sql
SELECT * FROM staging.stg_customers LIMIT 10;
SELECT * FROM marts.fct_orders LIMIT 10;
SELECT * FROM marts_finance.fct_daily_revenue LIMIT 10;
```

Or set the search path for your session:

```sql
SET search_path = 'staging', 'marts', 'marts_finance', 'raw';
```

See [docs/duckdb-guide.md](duckdb-guide.md) for the full schema layout.

### `SHOW TABLES` returns 0 rows

**Cause:** `SHOW TABLES` only shows tables in the *current* schema (usually
`main`), which is empty because all models are built in custom schemas.

**Fix:** Use the information schema instead:

```sql
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
ORDER BY table_schema, table_name;
```

Or show tables from a specific schema:

```sql
SELECT * FROM information_schema.tables WHERE table_schema = 'staging';
```

### DuckDB file is empty / no models

**Cause:** You haven't run `dbt build --target local` yet, or it failed.

**Fix:**

```bash
uv sync --extra dev
uv run dbt deps
uv run dbt build --target local
```

### `uv run duckdb dev.duckdb` — "Failed to spawn"

**Cause:** `uv run` only runs commands available in the Python virtual
environment. `duckdb` CLI is a system binary, not a Python entry point.

**Fix:** Run `duckdb` directly (after installing via Homebrew), or use
Python:

```bash
# Direct CLI (after brew install duckdb)
duckdb dev.duckdb

# Or via Python
uv run python -c "import duckdb; con=duckdb.connect('dev.duckdb'); con.sql('SHOW ALL TABLES').show()"
```

---

## dbt

### `dbt debug` fails with connection error

**Cause:** Environment variables for Snowflake credentials are not set.

**Fix:**

```bash
# Set credentials (add these to your shell profile or .env file)
export SNOWFLAKE_ACCOUNT="abcd-xy12345"
export SNOWFLAKE_USER="DBT_USER"
export SNOWFLAKE_PASSWORD="your_password"
export SNOWFLAKE_ROLE="TRANSFORM_ROLE"
export SNOWFLAKE_WAREHOUSE="TRANSFORM_WH"
export SNOWFLAKE_DATABASE="ANALYTICS"
export SNOWFLAKE_SCHEMA="DBT_DEV"

# Then test
uv run dbt debug
```

For local-only development (no Snowflake), use:

```bash
uv run dbt debug --target local
```

### `Could not find profile named 'analytics_engineering'`

**Cause:** dbt can't find `profiles.yml` in `~/.dbt/`.

**Fix:**

```bash
mkdir -p ~/.dbt
cp profiles.yml.example ~/.dbt/profiles.yml
```

### `Package not found: dbt_utils`

**Cause:** dbt packages haven't been installed.

**Fix:**

```bash
uv run dbt deps
```

### `Compilation Error: ... is not found in the graph!`

**Cause:** A model references another model that either doesn't exist or
hasn't been compiled yet.

**Fix:**

```bash
# Ensure packages are installed
uv run dbt deps

# Clean and rebuild
uv run dbt clean
uv run dbt deps
uv run dbt build --target local
```

### Tests fail on `fct_daily_revenue` after changing logic

**Cause:** Incremental models only process recent rows. Old rows still
contain stale logic.

**Fix:**

```bash
uv run dbt run --full-refresh -s fct_daily_revenue
uv run dbt test -s fct_daily_revenue
```

Or use the Makefile shortcut:

```bash
make full-refresh
```

---

## Python / uv

### `uv: command not found`

**Fix:** Install uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or via Homebrew:

```bash
brew install uv
```

### `ModuleNotFoundError: No module named 'dbt'`

**Cause:** You're running Python outside the uv-managed virtual environment.

**Fix:** Always prefix commands with `uv run`:

```bash
uv run dbt build
uv run python -c "import dbt; print(dbt.__version__)"
```

### `dbt-duckdb` not found / DuckDB adapter error

**Cause:** Dev dependencies (which include `dbt-duckdb`) aren't installed.

**Fix:**

```bash
uv sync --extra dev
```

---

## sqlfluff

### `sqlfluff lint` gives templating errors

**Cause:** sqlfluff uses the dbt templater, which needs dbt packages
installed and a working target.

**Fix:**

```bash
uv sync --extra dev
uv run dbt deps
uv run sqlfluff lint models/
```

### Lint errors you disagree with

You can disable specific rules in `.sqlfluff` or inline:

```sql
-- noqa: LT05
SELECT very_long_column_name_that_exceeds_line_length FROM some_table;
```

---

## CI / GitHub Actions

### CI fails but local build works

**Common causes:**
1. Missing `dbt deps` step — packages aren't installed in CI.
2. Different Python version — check `pyproject.toml` `requires-python`.
3. Environment variables not set for the Snowflake target.

**Fix:** Run the full CI pipeline locally to reproduce:

```bash
make ci
```

This runs: `uv sync --extra dev` → `dbt deps` → `sqlfluff lint` →
`dbt build --target local`.

---

## Quick diagnostic commands

```bash
# Check Python environment
uv run python --version
uv run dbt --version

# Check dbt can connect
uv run dbt debug --target local

# Check what dbt sees
uv run dbt ls --resource-type model
uv run dbt ls --resource-type test

# Check compiled SQL for a model
uv run dbt compile -s fct_orders
cat target/compiled/analytics_engineering/models/marts/core/fct_orders.sql
```
