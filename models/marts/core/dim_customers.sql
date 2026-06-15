{{
    config(
        materialized = 'table'
    )
}}

{#
    Customer dimension enriched with lifetime order metrics. This is the
    table BI tools join against for any "by customer" or "by region" cut of
    the data — e.g. "lifetime revenue by region" is one join + one group by
    away from here.
#}

with customers as (

    select * from {{ ref('stg_customers') }}

),

customer_orders as (

    select
        customer_id,
        min(order_date) as first_order_date,
        max(order_date) as most_recent_order_date,
        count(order_id) as lifetime_order_count,
        sum(amount_paid) as lifetime_revenue

    from {{ ref('fct_orders') }}
    group by customer_id

)

select
    customers.customer_id,
    customers.first_name,
    customers.last_name,
    customers.email,
    customers.region,
    customer_orders.first_order_date,
    customer_orders.most_recent_order_date,
    coalesce(customer_orders.lifetime_order_count, 0) as lifetime_order_count,
    coalesce(customer_orders.lifetime_revenue, 0) as lifetime_revenue

from customers
left join customer_orders
    on customers.customer_id = customer_orders.customer_id
