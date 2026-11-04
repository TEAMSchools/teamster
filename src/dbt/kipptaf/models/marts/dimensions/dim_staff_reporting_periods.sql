{#-
  Point-in-time manager resolver. One row per staff member x contiguous window
  during which they held a single primary-assignment reporting relationship,
  formed by intersecting the primary work-assignment window with the reporting
  relationship window (greatest-start / least-end). The inclusive-overlap join
  guarantees start <= end for every emitted row. Consumed by
  dim_staff_work_history (point-in-time manager per period) and
  dim_staff_reporting_chain (current-slice reporting edges). Previously lived in
  the staff_reporting_relationships cube-body sql.
-#}
with
    reporting_periods as (
        select
            swa.staff_key,
            rr.manager_staff_key,
            greatest(
                wap.effective_start_date, rr.effective_start_date
            ) as effective_start_date,
            least(wap.effective_end_date, rr.effective_end_date) as effective_end_date,
        from {{ ref("dim_work_assignment_primary") }} as wap
        inner join
            {{ ref("dim_staff_work_assignments") }} as swa
            on wap.work_assignment_key = swa.work_assignment_key
            and swa.staff_key is not null
        inner join
            {{ ref("dim_work_assignment_reporting_relationships") }} as rr
            on wap.work_assignment_key = rr.work_assignment_key
            and wap.effective_start_date <= rr.effective_end_date
            and wap.effective_end_date >= rr.effective_start_date
        where wap.is_primary_position
    )

select
    {{ dbt_utils.generate_surrogate_key(["staff_key", "effective_start_date"]) }}
    as staff_reporting_periods_key,
    staff_key,
    manager_staff_key,
    effective_start_date,
    effective_end_date,
from reporting_periods
