with
    user_role_mapping as (
        select
            user_id,
            role_id,
            date_trunc(_fivetran_synced, hour) as trunc_fivetran_synced,
        from {{ source("coupa", "user_role_mapping") }}
    ),

    window_calcs as (
        select
            *,
            max(trunc_fivetran_synced) over (
                partition by user_id
            ) as max_trunc_fivetran_synced,
        from user_role_mapping
    )

select user_id, role_id,
from window_calcs
where trunc_fivetran_synced = max_trunc_fivetran_synced
