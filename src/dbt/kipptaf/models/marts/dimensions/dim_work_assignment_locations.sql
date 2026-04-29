with
    assignments as (
        select wa.item_id, wa.effective_date_start, wa.location_key,
        from {{ ref("int_adp_workforce_now__workers__work_assignments") }} as wa
    ),

    change_detection as (
        select
            *,

            lag(location_key, 1, '') over (
                partition by item_id order by effective_date_start asc
            ) as location_key_lag,
        from assignments
    ),

    change_points as (
        select
            item_id,
            effective_date_start,
            location_key,

            coalesce(
                date_sub(
                    lead(effective_date_start) over (
                        partition by item_id order by effective_date_start asc
                    ),
                    interval 1 day
                ),
                date '9999-12-31'
            ) as effective_date_end,
        from change_detection
        where coalesce(location_key, '') != coalesce(location_key_lag, '')
    )

select
    {{ dbt_utils.generate_surrogate_key(["item_id", "effective_date_start"]) }}
    as work_assignment_location_key,

    {{ dbt_utils.generate_surrogate_key(["item_id"]) }} as work_assignment_key,

    location_key,

    effective_date_start as effective_start_date,
    effective_date_end as effective_end_date,

    if(effective_date_end = '9999-12-31', true, false) as is_current,
from change_points
