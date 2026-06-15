{#
    Custom business-logic test.

    order_date should never be in the future — a future date almost always
    means a timezone bug, a bad default value, or test data leaking into a
    real environment. A passing test returns zero rows.
#}

select
    order_id,
    order_date
from {{ ref('stg_orders') }}
where order_date > current_date()
