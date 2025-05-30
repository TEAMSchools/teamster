{{- config(materialized="view") -}}

with
    years as (
        select effective_date, extract(year from effective_date) - 1 as academic_year,
        from
            unnest(
                generate_date_array(
                    '2003-04-30',
                    '{{ var("current_fiscal_year") }}-04-30',
                    interval 1 year
                )
            ) as effective_date
    )

select
    s.employee_number,
    s.worker_id as adp_associate_id,
    s.given_name as preferred_first_name,
    s.family_name_1 as preferred_last_name,
    s.legal_given_name as legal_first_name,
    s.legal_family_name as legal_last_name,
    s.assignment_status as current_status,
    s.worker_termination_date as termination_date,
    s.home_business_unit_name as current_legal_entity,
    s.home_work_location_name as current_location,
    s.job_title as current_role,
    s.home_department_name as current_dept,
    s.race_ethnicity_reporting,
    s.gender_identity as gender,
    s.sam_account_name as samaccountname,
    s.reports_to_formatted_name as current_manager,
    s.reports_to_sam_account_name as manager_samaccountname,
    s.position_id as current_position_id,
    s.payroll_group_code,
    s.payroll_file_number,
    s.management_position_indicator as is_manager,
    s.worker_original_hire_date,
    s.worker_rehire_date,
    s.worker_termination_date,

    y.academic_year,

    e.home_business_unit_name as historic_legal_entity,
    e.home_work_location_name as historic_location,
    e.job_title as historic_role,
    e.home_department_name as historic_dept,
    e.base_remuneration_annual_rate_amount as historic_salary,
    e.effective_date_start,
    e.effective_date_end,
    e.assignment_status as historic_position_status,

    pm.final_score as overall_score,
    pm.final_tier as overall_tier,

    null as pm_term,
    null as etr_score,
    null as etr_tier,
    null as so_score,
    null as so_tier,

    coalesce(
        s.worker_rehire_date, s.worker_original_hire_date
    ) as most_recent_hire_date,

    if(s.ethnicity_code = 'Hispanic or Latino', true, false) as is_hispanic,
from {{ ref("int_people__staff_roster") }} as s
inner join
    years as y
    on y.effective_date between s.worker_original_hire_date and coalesce(
        s.worker_termination_date, date(9999, 12, 31)
    )
left join
    {{ ref("int_people__staff_roster_history") }} as e
    on s.employee_number = e.employee_number
    and y.effective_date between e.effective_date_start and e.effective_date_end
    and e.primary_indicator
    and e.job_title is not null
left join
    {{ ref("int_performance_management__overall_scores") }} as pm
    on s.employee_number = pm.employee_number
    and y.academic_year = pm.academic_year
