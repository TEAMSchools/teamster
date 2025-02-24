with
    years as (
        select effective_date, extract(year from effective_date) - 1 as academic_year,
        from
            unnest(
                generate_date_array(
                    '2024-05-15',
                    '{{ var("current_fiscal_year") }}-05-15',
                    interval 1 year
                )
            ) as effective_date
    )

select
    c.employee_number,

    y.academic_year,

    h.home_business_unit_name,
    h.wf_mgr_pay_rule,
    h.base_remuneration_annual_rate_amount as ay_salary,
    h.base_remuneration_hourly_rate_amount as ay_hourly,

    p.final_tier as ay_pm4_overall_tier,

    pss.scale_cy_salary,
    pss.scale_ny_salary,
    pss.scale_step,

    tss.scale_ny_salary as pm_salary_increase,

    if(
        regexp_contains(h.wf_mgr_pay_rule, r'Hourly'),
        h.base_remuneration_hourly_rate_amount,
        h.base_remuneration_annual_rate_amount
    ) as ay_hourly_salary_rate,

    coalesce(pss.salary_rule, tss.salary_rule, mss.salary_rule, 'Annual Adjustment') as salary_rule,

    coalesce(
        pss.scale_ny_salary,
        tss.scale_ny_salary + h.base_remuneration_annual_rate_amount,
        if(mss.salary_rule = 'PM Increase - Missing PM',h.base_remuneration_annual_rate_amount + mss.scale_ny_salary,null),
        case
            when h.base_remuneration_annual_rate_amount < 60000
            then
                h.base_remuneration_annual_rate_amount
                + h.base_remuneration_annual_rate_amount * 0.05
            when h.base_remuneration_annual_rate_amount < 100000
            then
                h.base_remuneration_annual_rate_amount
                + h.base_remuneration_annual_rate_amount * 0.04
            when h.base_remuneration_annual_rate_amount >= 100000
            then
                h.base_remuneration_annual_rate_amount
                + h.base_remuneration_annual_rate_amount * 0.03
        end
    ) as ny_salary,
from {{ ref("int_people__staff_roster") }} as c
inner join
    years as y
    on y.effective_date between c.worker_original_hire_date and coalesce(
        c.worker_termination_date, date(9999, 12, 31)
    )
left join
    {{ ref("int_people__staff_roster_history") }} as h
    on c.employee_number = h.employee_number
    and y.effective_date between h.effective_date_start and h.effective_date_end
    and h.primary_indicator
    and h.job_title is not null
left join
    {{ ref("int_performance_management__overall_scores") }} as p
    on c.employee_number = p.employee_number
    and y.academic_year = p.academic_year
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on c.powerschool_teacher_number = tgl.teachernumber
    and y.academic_year = tgl.academic_year
    and tgl.grade_level_rank = 1
left join
    {{ ref("stg_people__salary_scale") }} as pss
    on y.academic_year = pss.academic_year
    and h.home_business_unit_name = pss.region
    and h.job_title = pss.job_title
    and h.home_work_location_grade_band
    = coalesce(pss.school_level, h.home_work_location_grade_band)
    and (
        h.base_remuneration_annual_rate_amount + 150
        between pss.scale_cy_salary and pss.scale_ny_salary_plus_1_cent
        or h.base_remuneration_annual_rate_amount
        between pss.scale_ny_salary_minus_1_dollar and pss.scale_ny_salary_plus_1_dollar
    )
left join
    {{ ref("stg_people__salary_scale") }} as tss
    on y.academic_year = tss.academic_year
    and h.job_title = tss.job_title
    and h.home_business_unit_name = tss.region
    and p.final_tier = tss.scale_step
left join
    {{ ref("stg_people__salary_scale")}} as mss
    on y.academic_year = mss.academic_year
    and h.job_title = mss.job_title
    and h.home_business_unit_name = mss.region
    and p.ay_pm4_overall_tier is null
    and mss.salary_rule = 'PM Increase - Missing PM'