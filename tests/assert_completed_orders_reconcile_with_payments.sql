{#
    Custom business-logic test.

    For any order in a final "completed" state, the amount successfully
    collected should equal the amount invoiced (order_total). A non-empty
    result here means a completed order has an unexplained gap between what
    the customer was charged and what was actually collected — exactly the
    kind of thing finance would otherwise discover manually, weeks later,
    while reconciling the books.

    A passing test returns zero rows.
#}

select
    order_id,
    order_total,
    amount_paid,
    amount_discrepancy
from {{ ref('fct_orders') }}
where
    order_status = 'completed'
    and abs(amount_discrepancy) > 0.01
