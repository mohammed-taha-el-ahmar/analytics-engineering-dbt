with source as (

    select * from {{ source('raw', 'raw_payments') }}

),

renamed as (

    select
        payment_id,
        order_id,
        lower(trim(payment_method)) as payment_method,
        lower(trim(payment_status)) as payment_status,
        amount::numeric(10, 2) as amount,
        payment_date::date as payment_date

    from source

)

select * from renamed
