{#-
  SCD2 period intersection: one row per work assignment x contiguous window
  during which the worker's status, job, worker type, home org unit, location,
  primary-position flag, AND point-in-time manager all held simultaneously.
  Overlaps are anchored to the assignment-level status period
  (dim_work_assignment_status); greatest / least then collapse each combination
  to its true effective range. Primary-position and manager are both folded into
  the intersection (left join + coalesce keeps assignments/staff with no primary
  or reporting row) so each emitted period carries a single is_primary_position
  and a single manager. Combinations whose children do not mutually overlap yield
  start > end and are dropped by the final where. Previously lived in the
  staff_work_history cube-body sql (with the manager logic copy-pasted inline and
  is_primary_position NOT clipped into the intersection, which fanned the grain).

  Known residual: a small number of active+primary staff carry two concurrent
  reporting relationships in ADP (see dim_staff_reporting_chain's dedupe TODO).
  When both manager periods overlap one status window, the mgr range-join emits
  two rows sharing (work_assignment_key, effective_start_date), so the PK unique
  test warns (project default severity) rather than errors. Left as-is pending
  the upstream ADP fix / a product decision on which manager wins; no defensive
  dedupe here.
-#}
with
    work_history as (
        select
            swa.work_assignment_key,
            swa.staff_key,
            swa.full_time_equivalency,
            swa.is_management_position,
            was.status_name,
            was.reason_name as status_reason,
            wj.position_title,
            wj.job_code,
            wt.worker_type_name as worker_type,
            wo.department_name,
            wo.business_unit_name,
            wl.location_key as work_location_key,
            wp.is_primary_position,
            mgr.manager_staff_key,
            greatest(
                was.effective_start_date,
                wj.effective_start_date,
                wt.effective_start_date,
                wo.effective_start_date,
                wl.effective_start_date,
                coalesce(wp.effective_start_date, date '1900-01-01'),
                coalesce(mgr.effective_start_date, date '1900-01-01')
            ) as effective_start_date,
            least(
                was.effective_end_date,
                wj.effective_end_date,
                wt.effective_end_date,
                wo.effective_end_date,
                wl.effective_end_date,
                coalesce(wp.effective_end_date, date '9999-12-31'),
                coalesce(mgr.effective_end_date, date '9999-12-31')
            ) as effective_end_date,
        from {{ ref("dim_staff_work_assignments") }} as swa
        inner join
            {{ ref("dim_work_assignment_status") }} as was
            on swa.work_assignment_key = was.work_assignment_key
        inner join
            {{ ref("dim_work_assignment_jobs") }} as wj
            on swa.work_assignment_key = wj.work_assignment_key
            and was.effective_start_date < wj.effective_end_date
            and was.effective_end_date > wj.effective_start_date
        inner join
            {{ ref("dim_work_assignment_types") }} as wt
            on swa.work_assignment_key = wt.work_assignment_key
            and was.effective_start_date < wt.effective_end_date
            and was.effective_end_date > wt.effective_start_date
        inner join
            {{ ref("dim_work_assignment_organizational_units") }} as wo
            on swa.work_assignment_key = wo.work_assignment_key
            and wo.assignment_type = 'home'
            and was.effective_start_date < wo.effective_end_date
            and was.effective_end_date > wo.effective_start_date
        inner join
            {{ ref("dim_work_assignment_locations") }} as wl
            on swa.work_assignment_key = wl.work_assignment_key
            and was.effective_start_date < wl.effective_end_date
            and was.effective_end_date > wl.effective_start_date
        left join
            {{ ref("dim_work_assignment_primary") }} as wp
            on swa.work_assignment_key = wp.work_assignment_key
            and was.effective_start_date < wp.effective_end_date
            and was.effective_end_date > wp.effective_start_date
        left join
            {{ ref("dim_staff_reporting_periods") }} as mgr
            on swa.staff_key = mgr.staff_key
            and was.effective_start_date < mgr.effective_end_date
            and was.effective_end_date > mgr.effective_start_date
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["work_assignment_key", "effective_start_date"]
        )
    }} as staff_work_history_key,
    work_assignment_key,
    staff_key,
    full_time_equivalency,
    is_management_position,
    status_name,
    status_reason,
    position_title,
    job_code,
    worker_type,
    department_name,
    business_unit_name,
    work_location_key,
    is_primary_position,
    manager_staff_key,
    effective_start_date,
    effective_end_date,
from work_history
where effective_start_date <= effective_end_date
