select
    h.employee_number,
    h.worker_id as associate_id,
    h.work_assignment__fivetran_start as effective_start_date,
    h.work_assignment__fivetran_end as effective_end_date,
    h.department_home_name as home_department,
    h.job_title,
    h.assignment_status_reason as job_change_reason,
    h.base_remuneration_annual_rate_amount_amount_value as annual_salary,
    h.assignment_status_reason as compensation_change_reason,
    h.work_assignment__fivetran_active,

    r.preferred_name_given_name as preferred_first_name,
    r.preferred_name_family_name as preferred_last_name,
    r.report_to_preferred_name_lastfirst as manager_name,
    r.business_unit_home_name as legal_entity_name,
    r.home_work_location_name as primary_site,
    r.assignment_status as current_status,

    lag(h.department_home_name, 1) over (
        partition by h.employee_number order by h.work_assignment__fivetran_start asc
    ) as prev_home_department,
    lag(h.job_title, 1) over (
        partition by h.employee_number order by h.work_assignment__fivetran_start asc
    ) as prev_job_title,
    lag(h.base_remuneration_annual_rate_amount_amount_value, 1) over (
        partition by h.employee_number order by h.work_assignment__fivetran_start asc
    ) as prev_annual_salary,
    /* dedupe positions */
    row_number() over (
        partition by h.employee_number
        order by
            h.primary_indicator desc,
            h.work_assignment__fivetran_start desc,
            case when h.assignment_status = 'Terminated' then 0 else 1 end desc,
            h.work_assignment__fivetran_start desc
    ) as rn_position,
    row_number() over (
        partition by h.employee_number order by h.work_assignment__fivetran_start desc
    ) as rn_curr,
from {{ ref("base_people__staff_roster_history") }} as h
inner join
    {{ ref("base_people__staff_roster") }} as r
    on (h.employee_number = r.employee_number)
where
    (
        h.job_title is not null
        or h.base_remuneration_annual_rate_amount_amount_value is not null
    )
