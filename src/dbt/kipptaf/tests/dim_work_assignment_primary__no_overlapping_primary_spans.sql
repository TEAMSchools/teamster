with
    primary_spans as (
        select
            wap.effective_start_date,
            wap.effective_end_date,

            swa.staff_key,

            lead(wap.effective_start_date) over (
                partition by swa.staff_key order by wap.effective_start_date
            ) as next_start,
        from {{ ref("dim_work_assignment_primary") }} as wap
        -- work_assignment_key is swa's PK: exactly one staff_key per primary
        -- span, so this join cannot fan out the lead() ordering
        inner join
            {{ ref("dim_staff_work_assignments") }} as swa
            on wap.work_assignment_key = swa.work_assignment_key
        where wap.is_primary_position and swa.staff_key is not null
    )

select staff_key, effective_start_date, effective_end_date, next_start,
from primary_spans
where next_start is not null and next_start <= effective_end_date
