# Analytics Engineering with dbt + Snowflake

[![CI](https://github.com/mohammed-taha-el-ahmar/analytics-engineering-dbt/actions/workflows/ci.yml/badge.svg)](https://github.com/mohammed-taha-el-ahmar/analytics-engineering-dbt/actions/workflows/ci.yml)

Transforms raw operational data into trusted, documented, tested business
metrics — with full lineage so anyone can trace a number back to its source.

This is a small but complete dbt project: layered SQL models, a generic +
custom test suite that runs on every build, auto-generated documentation with
a lineage graph, and an incremental model for the highest-volume table. It's
built to run against a Snowflake free trial, and can also run entirely
locally (no Snowflake account needed) via DuckDB for fast iteration.

## Architecture

```
Seed CSVs (stand-in for an EL tool landing data into Snowflake)
        |
        v
+----------------------------+
| RAW schema                  |  raw_customers, raw_orders, raw_payments
+----------------------------+
        |
        v
+----------------------------+
| STAGING (views)             |  stg_customers, stg_orders, stg_payments
| 1:1 with sources, cleaned   |  - lowercase/trim text, cast types
+----------------------------+
        |
        v
+----------------------------+
| INTERMEDIATE (ephemeral)    |  int_order_payments
| reusable business logic     |  - successful payments per order,
+----------------------------+    amount_discrepancy
        |
        v
+----------------------------+
| MARTS                       |
|  core/      fct_orders,     |  tested, documented, BI-facing tables
|             dim_customers   |
|  finance/   fct_daily_rev.  |  incremental — only recomputes recent days
+----------------------------+
        |
        v
   BI tool / dbt docs (lineage graph = data catalog)
```

## Why this exists

Two recurring problems on data teams:

1. **"Where does this number come from?"** A stakeholder asks why revenue
   for March looks off. Without lineage, answering means grepping through
   ETL scripts, Slack history, and tribal knowledge — often a half-day
   exercise, sometimes longer if the original author has left.
2. **Silent breakage.** A schema change or a bad batch of source data quietly
   produces a wrong number in a dashboard, and nobody notices until a
   stakeholder does.

This project addresses both:

- **Lineage**: every model is `ref()`-ed, so `dbt docs generate` produces a
  full dependency graph from raw table to dashboard-facing mart. Clicking
  `fct_daily_revenue` shows exactly which staging models, which source
  tables, and which transformation logic produced it.
- **Tests as a contract**: `dbt build` runs 59 tests — generic (`not_null`,
  `unique`, `relationships`, `accepted_values`), a custom generic test
  (`not_negative`), and custom singular business-logic tests (payment/order
  reconciliation, no future-dated orders). If an assumption breaks, the build
  fails with a specific, named test — not a wrong number three layers
  downstream.

### The before/after demo

| | Before | After |
|---|---|---|
| "Where does `gross_revenue` in the finance dashboard come from?" | Open the BI tool, find the underlying query, trace table names back through one or more ETL scripts, ask around about which script actually runs in production. **~30-60 minutes, often more.** | Open `dbt docs`, click `fct_daily_revenue`, view its lineage graph and column-level description. It's `sum(order_total)` from `fct_orders`, which comes from `int_order_payments`, which comes from `stg_orders` + `stg_payments`, which come from `raw_orders` / `raw_payments`. **Under 2 minutes, self-serve.** |
| "Did last night's load break anything?" | Nobody knows until a stakeholder flags a wrong dashboard number — hours or days later. | `dbt build` fails immediately with a named test (e.g. `assert_completed_orders_reconcile_with_payments`), pointing at the exact model and rows. |

For a portfolio demo: take a screenshot of the `dbt docs` lineage graph
centered on `fct_daily_revenue`, and pair it with the table above.

## Repo layout

```
.
├── pyproject.toml          # uv-managed deps: dbt-core, dbt-snowflake (+ optional dbt-duckdb, sqlfluff)
├── dbt_project.yml          # layer config: staging=view, intermediate=ephemeral, marts=table
├── packages.yml              # dbt_utils (pinned by git revision)
├── profiles.yml.example     # copy to ~/.dbt/profiles.yml and fill in env vars
├── .sqlfluff                  # SQL lint config (dbt templater, snowflake dialect)
├── Makefile                  # uv run dbt <command> shortcuts, incl. `make ci`
├── .github/workflows/
│   ├── ci.yml                # PR/push: lint + dbt build --target local (DuckDB, no secrets)
│   └── cd.yml                # main: dbt build --target prod (Snowflake) + publish dbt docs
├── scripts/
│   └── snowflake_setup.sql  # one-time warehouse/db/schema/role setup
├── seeds/                     # raw_customers, raw_orders, raw_payments (CSV)
├── models/
│   ├── staging/              # stg_customers, stg_orders, stg_payments + sources.yml
│   ├── intermediate/         # int_order_payments (ephemeral)
│   └── marts/
│       ├── core/             # fct_orders, dim_customers
│       └── finance/          # fct_daily_revenue (incremental)
├── macros/
│   ├── generate_schema_name.sql   # exact +schema names, no target prefix
│   └── generic_tests/
│       └── test_not_negative.sql  # custom generic test
└── tests/                     # singular business-logic tests
    ├── assert_completed_orders_reconcile_with_payments.sql
    └── assert_no_future_order_dates.sql
```

## Key technical decisions

### 1. Layered modeling: staging → intermediate → marts

- **`staging/`** is a thin, 1:1 layer over each source table: rename, cast,
  lowercase/trim. Materialized as **views** (`+materialized: view`) — cheap,
  always reflect the latest raw data, nothing to maintain.
- **`intermediate/`** holds reusable logic that doesn't belong to a single
  mart — here, `int_order_payments` computes "how much of this order was
  actually paid for" once, so both `fct_orders` and `fct_daily_revenue` rely
  on the same definition. Materialized as **ephemeral**: it compiles into a
  CTE inside whatever refs it, so it's testable and documented as its own
  node without adding an extra object to the warehouse.
- **`marts/`** are business-facing, tested, documented **tables**, split by
  subject area (`core/`, `finance/`) so ownership and lineage stay legible as
  the project grows. These are what a BI tool queries directly.

Each layer can be built and tested independently
(`dbt build -s staging.*`), and a break in one layer is caught before it
propagates — a malformed `stg_orders` row fails staging tests rather than
silently corrupting `fct_daily_revenue`.

### 2. Tests as the contract

Every model has column-level tests in its `_*.yml` file:

- `unique` / `not_null` on primary keys
- `relationships` for every foreign key (e.g. `fct_orders.customer_id` →
  `dim_customers.customer_id`)
- `accepted_values` for enum-like columns (`order_status`, `payment_status`)
- a **custom generic test**, `not_negative` (`macros/generic_tests/`), applied
  to every monetary column — a domain rule no built-in test covers

Plus two **custom singular tests** encoding business logic that spans models:

- `assert_completed_orders_reconcile_with_payments.sql` — for any order with
  `status = 'completed'`, the amount collected must equal the amount
  invoiced (within 1 cent). This is the test that would catch a payment
  processor bug or a join error before it reaches the revenue dashboard.
- `assert_no_future_order_dates.sql` — guards against bad data / timezone
  bugs producing impossible dates.

All 59 tests run on every `dbt build`, in CI or locally. A broken assumption
fails the build with a named test pointing at the offending model and rows —
not a quietly wrong number in a dashboard.

### 3. Documentation and lineage as a data catalog

Every source, model, and column has a `description:` in its `_*.yml` file.
`dbt docs generate && dbt docs serve` produces a browsable site with:

- A full **lineage graph** (DAG) from raw source tables through every layer
  to each mart
- Column-level descriptions and the tests applied to each column
- Compiled SQL for every model, so "what does this actually run" is one
  click away

For a small team, this *is* the data catalog — no separate tool to maintain,
and it can never drift out of sync with the code because it's generated from
the code.

### 4. Incremental models for cost/performance at scale

`fct_daily_revenue` is the one model likely to be queried by a live
dashboard and to grow large over time (one row per order-date, but built
from a `fct_orders` that only grows). It's configured as:

```sql
{{ config(
    materialized = 'incremental',
    unique_key = 'order_date',
    incremental_strategy = 'merge',
    on_schema_change = 'sync_all_columns'
) }}
```

On an incremental run, it only re-scans and re-merges the **last two days**
of `fct_orders` (recent days may still receive late-arriving payments that
change `amount_paid`). Older history is untouched. This keeps both run time
and warehouse cost roughly constant as `fct_orders` grows from thousands to
millions of rows — a full rebuild every run would scale linearly with table
size.

Use `dbt run --full-refresh -s fct_daily_revenue` (or
`make full-refresh`) to force a complete rebuild, e.g. after a backfill or a
logic change to the model.

The incremental filter uses dbt's cross-database `dbt.dateadd()` macro rather
than hardcoded Snowflake SQL, so the same model also runs against the local
DuckDB target described below.

### 5. Predictable schema layout (`generate_schema_name` override)

By default, dbt prefixes custom schemas with your target schema (e.g.
`+schema: raw` → `dbt_alice_raw`). `macros/generate_schema_name.sql`
overrides this to use the configured schema name **as-is**, so the project
always produces `RAW`, `STAGING`, `MARTS`, and `MARTS_FINANCE` — in dev, in
CI, and in prod — matching `scripts/snowflake_setup.sql`.

### 6. CI/CD: fast, free PR checks; Snowflake + dbt docs on merge

Two GitHub Actions workflows (`.github/workflows/`):

- **`ci.yml`** — runs on every push and PR. Installs deps with `uv`, lints
  every model with `sqlfluff` (via the dbt templater, so Jinja/`ref()`/
  `config()` are resolved before linting), then runs `dbt build --target
  local` — the full seed → run → test suite (68 nodes, 59 tests) against
  DuckDB. **No Snowflake account or secrets required**, so it runs on PRs
  from forks too, and gives feedback in seconds.
- **`cd.yml`** — runs on push to `main`. Runs `dbt build --target prod`
  against the real Snowflake warehouse, then `dbt docs generate` and
  publishes the resulting site (the lineage graph / data catalog) to
  **GitHub Pages**.

This mirrors how a real team would work: every PR proves the *logic* is
correct and tested for free before anyone touches the warehouse; merging to
`main` is what actually updates Snowflake and republishes the living data
catalog.

`make ci` runs the same checks (`sqlfluff` + `dbt build --target local`)
locally before you push.

**To enable the CD workflow** on your own fork/repo:
1. Settings → Secrets and variables → Actions → add `SNOWFLAKE_ACCOUNT`,
   `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_ROLE`,
   `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE` (from `scripts/snowflake_setup.sql`).
2. Settings → Pages → Source = "GitHub Actions".
3. Push to `main` — the docs site (with the lineage graph) will be live at
   `https://<you>.github.io/<repo>/`.

## Getting started


### Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- A Snowflake account — the [free trial](https://signup.snowflake.com/) is
  sufficient (includes $400 of credits)

### 1. Set up Snowflake

In a Snowflake worksheet (as `ACCOUNTADMIN`), run
[`scripts/snowflake_setup.sql`](scripts/snowflake_setup.sql). It creates:

- An auto-suspending `TRANSFORM_WH` warehouse (so idle time doesn't burn
  trial credits)
- A `TRANSFORM_ROLE` and `DBT_USER` service account
- An `ANALYTICS` database with `RAW`, `STAGING`, `MARTS`, and
  `MARTS_FINANCE` schemas

Replace the placeholder password before running it.

### 2. Install dependencies

```bash
uv sync
```

This creates `.venv/` with `dbt-core` and `dbt-snowflake` pinned via
`uv.lock`.

### 3. Configure your dbt profile

```bash
mkdir -p ~/.dbt
cp profiles.yml.example ~/.dbt/profiles.yml
```

Then export the credentials from step 1 (e.g. in your shell profile or a
local `.env` you source (source .env) — never commit these):

```bash
export SNOWFLAKE_ACCOUNT="abcd-xy12345"     # everything before .snowflakecomputing.com
export SNOWFLAKE_USER="DBT_USER"
export SNOWFLAKE_PASSWORD="..."
export SNOWFLAKE_ROLE="TRANSFORM_ROLE"
export SNOWFLAKE_WAREHOUSE="TRANSFORM_WH"
export SNOWFLAKE_DATABASE="ANALYTICS"
export SNOWFLAKE_SCHEMA="DBT_DEV"           # your personal dev schema, e.g. dbt_<you>
```

Verify the connection:

```bash
uv run dbt debug
```

### 4. Install dbt packages, seed, build, and test

```bash
uv run dbt deps    # installs dbt_utils
uv run dbt seed    # loads raw_customers/orders/payments into RAW
uv run dbt build   # runs staging -> intermediate -> marts, then all tests
```

Or with the Makefile:

```bash
make install
make deps
make build
```

### 5. Generate the docs / lineage graph

```bash
make docs-serve
```

Opens a local docs site at `http://localhost:8080` — click through the
lineage graph (the "DAG" view) starting from `fct_daily_revenue` to see the
full path back to `raw_orders` and `raw_payments`.

## Testing locally without Snowflake

The project also runs entirely on [DuckDB](https://duckdb.org/) — useful for
fast iteration on model logic without touching the warehouse or any free-tier
credits:

```bash
uv sync --extra dev          # installs dbt-duckdb
uv run dbt build --target local
```

The `local` target in `profiles.yml.example` points dbt at a local
`dev.duckdb` file. All 59 tests, the layered models, and the incremental
finance model all run identically (the incremental filter uses
`dbt.dateadd()`, which dispatches to the right SQL for each adapter).

## Project structure reference

| Model | Layer | Materialization | Grain | Purpose |
|---|---|---|---|---|
| `stg_customers` | staging | view | 1 row / customer | Cleaned customer records |
| `stg_orders` | staging | view | 1 row / order | Cleaned order records, normalized status |
| `stg_payments` | staging | view | 1 row / payment attempt | Cleaned payment records |
| `int_order_payments` | intermediate | ephemeral | 1 row / order | Order + amount successfully paid + discrepancy |
| `fct_orders` | marts/core | table | 1 row / order | Central order fact table |
| `dim_customers` | marts/core | table | 1 row / customer | Customer dimension + lifetime order metrics |
| `fct_daily_revenue` | marts/finance | incremental | 1 row / order_date | Daily revenue rollup for BI |

## Documentation

Detailed guides live in the [`docs/`](docs/) folder:

| Guide | Description |
|-------|-------------|
| [Commands Reference](docs/commands.md) | All Makefile targets, dbt commands, sqlfluff, and model selection syntax |
| [DuckDB Guide](docs/duckdb-guide.md) | How to open, query, and explore the local DuckDB database |
| [Troubleshooting](docs/troubleshooting.md) | Common errors and fixes (DuckDB, dbt, Python/uv, CI) |

### Quick reference: querying DuckDB locally

```bash
# Open the database (requires: brew install duckdb)
duckdb dev.duckdb
```

```sql
-- Models live in custom schemas, NOT in main
SELECT table_schema, table_name FROM information_schema.tables
WHERE table_schema NOT IN ('information_schema', 'pg_catalog');

-- Query examples
SELECT * FROM staging.stg_customers LIMIT 10;
SELECT * FROM marts.fct_orders LIMIT 10;
SELECT * FROM marts_finance.fct_daily_revenue LIMIT 10;
```

---

## Possible extensions

- `dbt_utils.accepted_range` checks on top of `not_negative` for tighter
  monetary bounds
- A `dbt-expectations` package for distribution-based anomaly tests
  (e.g. "today's order count shouldn't drop >50% vs. the trailing average")
- Snapshots (`snapshots/`) for slowly-changing customer attributes
- A real BI layer (e.g. a small Streamlit/Evidence dashboard) reading from
  `fct_daily_revenue` and `dim_customers`
