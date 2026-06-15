{{
    config(
        materialized = 'table'
    )
}}

{#
    The central order fact table. Grain: one row per order.

    Built on top of int_order_payments (ephemeral) so the reconciliation
    logic — "how much was actually collected vs. invoiced" — is computed
    once and reused everywhere downstream (this model, dim_customers, and
    fct_daily_revenue all rely on the same definition of amount_paid).
#}

select
    order_id,
    customer_id,
    order_date,
    order_status,
    order_total,
    amount_paid,
    amount_discrepancy,
    successful_payment_count,
    last_payment_date,
    abs(amount_discrepancy) < 0.01 as is_reconciled

from {{ ref('int_order_payments') }}
