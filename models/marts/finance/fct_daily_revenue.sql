{{
    config(
        materialized = 'incremental',
        unique_key = 'order_date',
        incremental_strategy = 'merge',
        on_schema_change = 'sync_all_columns'
    )
}}

{#
    Daily revenue rollup, one row per order_date.

    Why incremental: fct_orders (and the orders table behind it) only grows.
    Re-aggregating the entire order history on every run is wasted compute —
    cost and run time would grow linearly with the lifetime size of the
    orders table. Incremental builds keep both bounded: on a normal run we
    only re-scan and re-merge days that are new or could still be changing
    (today and yesterday, to absorb late-arriving payments).

    `unique_key = 'order_date'` + `merge` strategy means Snowflake upserts:
    existing days are replaced, new days are inserted, untouched history is
    left alone.

    Run `dbt run --full-refresh -s fct_daily_revenue` to rebuild from scratch
    (e.g. after a backfill or a logic change to this model).
#}

with orders as (

    select * from {{ ref('fct_orders') }}

    {% if is_incremental() %}
        -- Only reprocess recent days: today/yesterday may still receive
        -- late-arriving payments that change amount_paid for those dates.
        -- dbt.dateadd() dispatches to the right SQL per warehouse (Snowflake,
        -- DuckDB for local testing, etc.) instead of hardcoding one dialect.
        where order_date >= {{ dbt.dateadd("day", -2, "(select max(order_date) from " ~ this ~ ")") }}
    {% endif %}

)

select
    order_date,
    count(order_id) as order_count,
    sum(order_total) as gross_revenue,
    sum(amount_paid) as collected_revenue,
    sum(case when not is_reconciled then amount_discrepancy else 0 end) as unreconciled_amount

from orders
group by order_date
