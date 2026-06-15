with source as (

    select * from {{ source('raw', 'raw_customers') }}

),

renamed as (

    select
        customer_id,
        first_name,
        last_name,
        lower(trim(email)) as email,
        region,
        created_at::timestamp as created_at

    from source

)

select * from renamed
