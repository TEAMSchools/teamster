with
    status_versions as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_adp_workforce_now__workers__work_assignments"),
                partition_by="item_id, assignment_status__effective_date",
                order_by="effective_date_start desc",
            )
        }}
    ),

    windowed as (
        select
            item_id,
            assignment_status__status_code__code_value as status_code,
            assignment_status__status_code__name as status_name,
            assignment_status__reason_code__code_value as reason_code,
            assignment_status__reason_code__name as reason_name,
            assignment_status__effective_date as effective_date_start,

            coalesce(
                date_sub(
                    lead(assignment_status__effective_date) over (
                        partition by item_id
                        order by assignment_status__effective_date asc
                    ),
                    interval 1 day
                ),
                date '9999-12-31'
            ) as effective_date_end,
        from status_versions
        where assignment_status__effective_date is not null
    )

select
    {{ dbt_utils.generate_surrogate_key(["item_id", "effective_date_start"]) }}
    as work_assignment_status_key,

    {{ dbt_utils.generate_surrogate_key(["item_id"]) }} as work_assignment_key,

    status_code,
    status_name,
    reason_code,
    reason_name,
    effective_date_start as effective_start_date,
    effective_date_end as effective_end_date,

    if(effective_date_end = '9999-12-31', true, false) as is_current,
from windowed
