# NL-to-SQL Agent

A web console where you type a question in plain English and the agent
writes, validates, executes, and — if it gets it wrong — *corrects its own*
SQL against the project's real dbt marts.

---

## Architecture

```
Question → Query Agent → Groq LLM (llama-3.3-70b)
                ↑                       ↓
         dbt manifest.json        Generated SQL
         (mart schemas)                 ↓
                              SQL Guard (sqlglot)
                            SELECT-only, allowed tables, row limit
                                        ↓
                              DuckDB (local) / Snowflake (prod)
                                        ↓
                              Result + attempt trail
```

The loop is bounded by `AGENT_MAX_ATTEMPTS` (default 3): generate → guard →
execute → if either fails, the error goes back to the model and it retries.

---

## Quick start

### 1. Install dependencies

```bash
uv sync --extra agent
```

### 2. Build the dbt project (so there's data + a manifest)

```bash
uv sync --extra dev
uv run dbt deps
uv run dbt build --target local
uv run dbt docs generate --target local
```

### 3. Set environment variables

```bash
export GROQ_API_KEY="gsk_..."        # required — get one at https://console.groq.com
export DB_TARGET="duckdb"            # default; or "snowflake"
export DUCKDB_PATH="dev.duckdb"      # default
export DBT_MANIFEST_PATH="target/manifest.json"  # default
```

### 4. Start the agent

```bash
make agent-serve
# or directly:
uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 — type a question and see the SQL, results, and
attempt trail.

---

## How it works

### Schema grounding (catalog.py)

Parses `target/manifest.json` and extracts only `marts/` models. Staging
and intermediate models stay out of scope. Column names, types, and
descriptions come straight from the manifest.

### SQL guard (sql_guard.py)

Every candidate query is parsed with `sqlglot` before touching a database:

- Must be exactly one `SELECT` statement
- No `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, `MERGE`, `GRANT`
- Every referenced table must be in the mart catalog
- Row limit enforced (`AGENT_MAX_ROWS`, default 200)

### Self-correction loop (query_agent.py)

If the guard rejects a query or the database returns an error, the real
error message goes back to the LLM as the next turn. Every attempt is
recorded and surfaced in the UI as an "attempt trail."

### Dual backend (db_adapters/)

`DB_TARGET=duckdb` (default) runs against the local `dev.duckdb` file.
`DB_TARGET=snowflake` runs the same agent against live Snowflake marts.
The agent code never branches on which one is active.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serves the web console |
| `GET` | `/api/catalog` | Returns the mart schema the agent knows about |
| `POST` | `/api/ask` | Runs the agent loop, returns SQL + results + attempt trail |

### POST /api/ask

Request:
```json
{ "question": "top 5 customers by lifetime order value" }
```

Response:
```json
{
  "sql": "SELECT customer_id, ... LIMIT 5",
  "explanation": "Ranks customers by total order value.",
  "columns": ["customer_id", "..."],
  "rows": [["c1", "..."]],
  "attempts": 1,
  "history": [{"attempt": 1, "status": "ok", "detail": "Executed successfully."}]
}
```

---

## Environment variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `GROQ_API_KEY` | — | ✅ | Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | | LLM model |
| `DB_TARGET` | `duckdb` | | `duckdb` or `snowflake` |
| `DUCKDB_PATH` | `dev.duckdb` | | Path to DuckDB file |
| `DBT_MANIFEST_PATH` | `target/manifest.json` | | Path to dbt manifest |
| `AGENT_MAX_ATTEMPTS` | `3` | | Max self-correction attempts |
| `AGENT_MAX_ROWS` | `200` | | Max rows returned per query |
| `SNOWFLAKE_ACCOUNT` | — | if snowflake | Snowflake account |
| `SNOWFLAKE_USER` | — | if snowflake | Snowflake user |
| `SNOWFLAKE_PASSWORD` | — | if snowflake | Snowflake password |
| `SNOWFLAKE_WAREHOUSE` | — | if snowflake | Snowflake warehouse |
| `SNOWFLAKE_DATABASE` | — | if snowflake | Snowflake database |
| `SNOWFLAKE_SCHEMA` | — | if snowflake | Snowflake schema |

---

## Running tests

```bash
make agent-test
# or:
uv run pytest tests_agent/ -v
```

23 tests, all passing without any live infrastructure:
- **Catalog tests**: run against a fixture `manifest.json`
- **Guard tests**: pure parsing logic
- **DuckDB adapter test**: seeds a real temp DuckDB file (embedded, no server)
- **Snowflake adapter test**: injects a fake module (no driver needed)
- **Agent loop tests**: stub the Groq client to exercise generate → reject → correct → succeed

### Linting

```bash
make agent-lint
# or:
uv run ruff check agent/ app/ tests_agent/
```

---

## Makefile targets

| Target | Description |
|--------|-------------|
| `make agent-install` | Install agent dependencies |
| `make agent-test` | Run agent tests |
| `make agent-lint` | Lint agent code with ruff |
| `make agent-serve` | Start the web console at http://localhost:8000 |

---

## Project structure

```
agent/
├── __init__.py
├── config.py           # Environment-based configuration
├── catalog.py          # Parse dbt manifest → mart schemas
├── groq_client.py      # Thin Groq API wrapper
├── prompts.py          # System + retry prompt templates
├── query_agent.py      # The agentic loop (generate → guard → execute → retry)
├── sql_guard.py        # Read-only SQL validation via sqlglot
└── db_adapters/
    ├── __init__.py
    ├── base.py          # Protocol + error type
    ├── duckdb_adapter.py
    ├── snowflake_adapter.py
    └── factory.py       # Build the right adapter from config
app/
├── main.py             # FastAPI app (3 endpoints)
└── static/
    ├── index.html
    ├── style.css
    └── app.js
tests_agent/
├── test_catalog.py
├── test_sql_guard.py
├── test_db_adapters.py
├── test_query_agent.py
└── fixtures/
    └── manifest.json
```
