with
    years as (
        select
            effective_date,

            extract(year from effective_date) as fiscal_year,
            extract(year from effective_date) - 1 as academic_year,
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

    h.home_business_unit_name as ay_business_unit,
    h.home_department_name as ay_department,
    h.job_title as ay_job_title,
    h.home_work_location_name as ay_location,
    h.base_remuneration_annual_rate_amount as ay_salary,

    p.final_score as ay_pm4_overall_score,
    p.final_tier as ay_pm4_overall_tier,

    tgl.grade_level as ay_primary_grade_level_taught,

    sp.scale_cy_salary,
    sp.scale_ny_salary,
    sp.scale_step,
    sp.scale_ny_salary as pm_salary_increase,
    sp.ny_salary,
    sp.salary_rule,

    s.staffing_model_id as seat_tracker_id_number,
    s.adp_location as ny_location,
    s.adp_dept as ny_dept,
    s.adp_title as ny_title,
    s.entity as ny_entity,
    s.edited_at as seat_tracker_last_edited,
    s.status_detail as ny_status,

    stp.nonrenewal_reason,
    stp.nonrenewal_notes,
    stp.gutcheck,

    ayl.abbreviation as ay_school_shortname,

    nyl.abbreviation as ny_school_shortname,

    ayc.name as ay_campus_name,

    nyc.name as ny_campus_name,

    ayhos.sam_account_name as ay_head_of_school_samaccount,

    nyhos.sam_account_name as ny_head_of_school_samaccount,

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
    and p.academic_year = y.academic_year
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on c.powerschool_teacher_number = tgl.teachernumber
    and tgl.academic_year = y.academic_year
    and tgl.grade_level_rank = 1
left join
    {{ ref("int_people__next_year_salary_projections") }} as sp
    on c.employee_number = sp.employee_number
    and y.academic_year = sp.academic_year
left join
    {{ ref("stg_seat_tracker__seats") }} as s
    on c.employee_number = s.teammate
    and y.fiscal_year = s.academic_year
left join
    {{ ref("stg_people__seat_tracker_people") }} as stp
    on c.employee_number = stp.employee_number
    and y.academic_year = stp.academic_year

left join
    {{ ref("stg_people__location_crosswalk") }} as ayl
    on h.home_work_location_name = ayl.name
left join
    {{ ref("stg_people__location_crosswalk") }} as nyl on s.adp_location = nyl.name
left join
    {{ ref("stg_people__campus_crosswalk") }} as ayc
    on ayl.clean_name = ayc.location_name
left join
    {{ ref("stg_people__campus_crosswalk") }} as nyc
    on nyl.clean_name = nyc.location_name
left join
    {{ ref("int_people__staff_roster") }} as ayhos
    on ayl.head_of_schools_employee_number = ayhos.employee_number
left join
    {{ ref("int_people__staff_roster") }} as nyhos
    on nyl.head_of_schools_employee_number = nyhos.employee_number
