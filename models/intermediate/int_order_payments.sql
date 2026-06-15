{#
    Reusable building block: one row per order, enriched with how much of it
    has actually been paid for successfully.

    This logic (filtering to successful payments, aggregating per order) is
    needed by more than one mart (fct_orders today; potentially a customer
    payments mart later), so it lives here rather than being duplicated.
    Materialized as `ephemeral` (the project default for intermediate/) — it
    compiles into a CTE inside whichever model refs it, so it adds zero extra
    objects to the warehouse while still being its own testable, documented
    dbt node.
#}

with orders as (

    select * from {{ ref('stg_orders') }}

),

payments as (

    select * from {{ ref('stg_payments') }}

),

successful_payments_per_order as (

    select
        order_id,
        sum(amount) as amount_paid,
        count(*) as successful_payment_count,
        max(payment_date) as last_payment_date

    from payments
    where payment_status = 'success'
    group by order_id

),

joined as (

    select
        orders.order_id,
        orders.customer_id,
        orders.order_date,
        orders.status as order_status,
        orders.order_total,
        coalesce(successful_payments_per_order.amount_paid, 0) as amount_paid,
        coalesce(successful_payments_per_order.successful_payment_count, 0) as successful_payment_count,
        successful_payments_per_order.last_payment_date,
        orders.order_total - coalesce(successful_payments_per_order.amount_paid, 0) as amount_discrepancy

    from orders
    left join successful_payments_per_order
        on orders.order_id = successful_payments_per_order.order_id

)

select * from joined
