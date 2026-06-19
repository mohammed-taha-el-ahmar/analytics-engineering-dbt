# DuckDB Local Development Guide

This project can run entirely on DuckDB — no Snowflake account, no
credentials, no cost. The local DuckDB file is `dev.duckdb` in the project
root.

---

## Building models into DuckDB

```bash
# Install dev dependencies (includes dbt-duckdb)
uv sync --extra dev

# Run the full project against DuckDB
uv run dbt build --target local
```

This creates/updates `dev.duckdb` with all seeds, models, and tests.

---

## Opening the DuckDB database

### Option 1: Install the DuckDB CLI (recommended)

```bash
# macOS
brew install duckdb

# Then open your database
duckdb dev.duckdb
```

### Option 2: Use the Python package (already installed)

```bash
uv run python -c "
import duckdb
con = duckdb.connect('dev.duckdb')
print(con.sql('SHOW ALL TABLES').fetchdf().to_string())
"
```

### Option 3: Interactive Python session

```bash
uv run python
```

```python
import duckdb
con = duckdb.connect('dev.duckdb')

# List all tables
con.sql("SHOW ALL TABLES").show()

# Query a model
con.sql("SELECT * FROM staging.stg_customers LIMIT 10").show()

# Get as a pandas DataFrame
df = con.sql("SELECT * FROM marts.fct_orders").fetchdf()
print(df.head())
```

---

## Schema layout in DuckDB

Models are **not** in the default `main` schema. The `generate_schema_name`
macro places them in purpose-specific schemas:

| Schema | Contents |
|--------|----------|
| `raw` | Seed tables: `raw_customers`, `raw_orders`, `raw_payments` |
| `staging` | Views: `stg_customers`, `stg_orders`, `stg_payments` |
| `marts` | Tables: `fct_orders`, `dim_customers` |
| `marts_finance` | Tables: `fct_daily_revenue` |

> **Important:** You must qualify table names with their schema, e.g.
> `staging.stg_orders`, not just `stg_orders`.

---

## Useful DuckDB queries

### Discover what's available

```sql
-- List all schemas
SELECT schema_name FROM information_schema.schemata ORDER BY 1;

-- List all tables and views with schema
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
ORDER BY table_schema, table_name;

-- Describe a specific table
DESCRIBE staging.stg_orders;

-- Row counts across all models
SELECT table_schema, table_name, 
       (SELECT COUNT(*) FROM information_schema.columns c 
        WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) as col_count
FROM information_schema.tables t
WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
ORDER BY table_schema, table_name;
```

### Explore the data

```sql
-- Peek at raw data
SELECT * FROM raw.raw_customers LIMIT 10;
SELECT * FROM raw.raw_orders LIMIT 10;
SELECT * FROM raw.raw_payments LIMIT 10;

-- Staging layer
SELECT * FROM staging.stg_customers LIMIT 10;
SELECT * FROM staging.stg_orders LIMIT 10;
SELECT * FROM staging.stg_payments LIMIT 10;

-- Mart layer
SELECT * FROM marts.fct_orders LIMIT 10;
SELECT * FROM marts.dim_customers LIMIT 10;
SELECT * FROM marts_finance.fct_daily_revenue LIMIT 10;
```

### Business questions

```sql
-- Total revenue by status
SELECT order_status, 
       COUNT(*) AS order_count, 
       SUM(amount_paid) AS total_paid
FROM marts.fct_orders
GROUP BY order_status
ORDER BY total_paid DESC;

-- Top customers by lifetime value
SELECT customer_id, 
       lifetime_order_count, 
       lifetime_revenue
FROM marts.dim_customers
ORDER BY lifetime_revenue DESC
LIMIT 10;

-- Daily revenue trend
SELECT order_date, 
       daily_revenue, 
       order_count
FROM marts_finance.fct_daily_revenue
ORDER BY order_date DESC
LIMIT 30;

-- Orders with payment discrepancy
SELECT order_id, order_total, amount_paid, 
       order_total - amount_paid AS discrepancy
FROM marts.fct_orders
WHERE order_total != amount_paid;
```

### Data quality checks

```sql
-- Check for NULLs in primary keys
SELECT 'fct_orders' AS model, COUNT(*) AS null_pks
FROM marts.fct_orders WHERE order_id IS NULL
UNION ALL
SELECT 'dim_customers', COUNT(*)
FROM marts.dim_customers WHERE customer_id IS NULL;

-- Referential integrity: orders without matching customers
SELECT f.order_id, f.customer_id
FROM marts.fct_orders f
LEFT JOIN marts.dim_customers d ON f.customer_id = d.customer_id
WHERE d.customer_id IS NULL;
```

---

## DuckDB CLI tips

```sql
-- Pretty table output
.mode table

-- Export query results to CSV
COPY (SELECT * FROM marts.fct_orders) TO 'output.csv' (HEADER, DELIMITER ',');

-- Export to Parquet
COPY (SELECT * FROM marts.fct_orders) TO 'output.parquet' (FORMAT PARQUET);

-- Set a default schema (avoids typing schema prefix)
SET search_path = 'staging';
SELECT * FROM stg_customers LIMIT 5;

-- Exit
.exit
```

---

## Resetting the DuckDB database

If you need a fresh start:

```bash
rm dev.duckdb
uv run dbt build --target local
```

This will recreate the database from scratch with all seeds and models.
