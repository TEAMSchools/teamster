with
    -- trunk-ignore(sqlfluff/ST03)
    user_history as (
        select
            id,
            followers_count,
            media_count,
            _fivetran_synced,

            cast(_fivetran_synced as date) as _fivetran_synced_date,
        from {{ source("instagram_business", "user_history") }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="user_history",
                partition_by="id, _fivetran_synced_date",
                order_by="_fivetran_synced desc",
            )
        }}
    )

select
    id,
    followers_count,
    media_count,
    _fivetran_synced_date,

    lag(_fivetran_synced_date, 1, '2010-10-06') over (
        partition by id order by _fivetran_synced_date asc
    ) as _fivetran_synced_date_prev,
from deduplicate
