with source as (

    select * from {{ source('raw', 'raw_orders') }}

),

renamed as (

    select
        order_id,
        customer_id,
        order_date::date as order_date,
        lower(trim(status)) as status,
        order_total::numeric(10, 2) as order_total

    from source

)

select * from renamed
