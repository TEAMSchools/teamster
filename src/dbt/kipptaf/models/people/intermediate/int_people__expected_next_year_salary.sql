select
    sr.employee_number,
    sr.job_title,
    sr.base_remuneration_annual_rate_amount_amount_value,

    pss.scale_cy_salary,
    pss.scale_ny_salary,
    pss.scale_step,

    case
        when pss.salary_rule is not null
        then pss.salary_rule
        when
            sr.job_title
            in ('Teacher', 'Teacher ESL', 'Learning Specialist', 'ESE Teacher')
        then concat('Teacher PM - ', sr.business_unit_assigned_code)
        else 'Annual Adjustment'
    end as salary_rule,
from {{ ref("base_people__staff_roster") }} as sr
left join
    {{ ref("stg_people__salary_scale") }} as pss
    on sr.job_title = pss.job_title
    and sr.business_unit_assigned_name = pss.region
    and sr.home_work_location_grade_band
    = coalesce(pss.school_level, sr.home_work_location_grade_band)
    and (
        (sr.base_remuneration_annual_rate_amount_amount_value + 150)
        between pss.scale_cy_salary and (pss.scale_ny_salary + 0.01)
        or (
            sr.base_remuneration_annual_rate_amount_amount_value
            between (pss.scale_cy_salary - 1) and (pss.scale_cy_salary + 1)
        )
    )

where sr.assignment_status not in ('Terminated', 'Deceased') and sr.primary_indicator
