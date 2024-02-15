with
    step_scales as (
        select
            sr.employee_number,
            sr.business_unit_assigned_code,
            sr.job_title,
            pss.salary_rule,
            pss.scale_cy_salary,
            pss.scale_ny_salary,
            pss.scale_step,
            pss.school_level,
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ source("people", "src_people__salary_scale") }} as pss
            on sr.job_title = pss.job_title
            and sr.business_unit_assigned_name = pss.region
            and sr.base_remuneration_annual_rate_amount_amount_value + 150
            >= pss.scale_cy_salary
            and sr.base_remuneration_annual_rate_amount_amount_value + 150
            < pss.scale_ny_salary
            and pss.school_level is null
        where
            sr.assignment_status not in ('Terminated', 'Deceased')
            and pss.school_level is null

        union all

        select
            sr.employee_number,
            sr.business_unit_assigned_code,
            sr.job_title,
            pss.salary_rule,
            pss.scale_cy_salary,
            pss.scale_ny_salary,
            pss.scale_step,
            pss.school_level,
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ source("people", "src_people__salary_scale") }} as pss
            on sr.job_title = pss.job_title
            and sr.business_unit_assigned_name = pss.region
            and sr.base_remuneration_annual_rate_amount_amount_value + 150
            >= pss.scale_cy_salary
            and sr.base_remuneration_annual_rate_amount_amount_value + 150
            < pss.scale_ny_salary
            and pss.school_level = sr.home_work_location_grade_band
        where
            sr.assignment_status not in ('Terminated', 'Deceased')
            and pss.school_level is not null
            and sr.home_work_location_grade_band is not null

    )

select
    employee_number,
    job_title,
    scale_cy_salary,
    scale_ny_salary,
    scale_step,
    case
        when salary_rule is not null
        then salary_rule
        when job_title in ('Teacher', 'Teacher ESL', 'Learrning Specialist')
        then concat('Teacher PM - ', business_unit_assigned_code)
        else 'Annual Adjustment'
    end as salary_rule,
from step_scales
