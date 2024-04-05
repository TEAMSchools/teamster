with
    pm_scores as (
        select employee_number, avg(overall_score) as pm4_overall_score,
        from {{ ref("int_performance_management__observation_details") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and overall_score is not null
            and form_term in ('PM2', 'PM3')
        group by employee_number
    )

select
    b.employee_number as df_employee_number,
    b.legal_name_given_name as first_name,
    b.legal_name_family_name as last_name,
    b.preferred_name_given_name as preferred_first,
    b.preferred_name_family_name as preferred_last,
    b.preferred_name_lastfirst as preferred_name,
    b.business_unit_home_name as legal_entity_name,
    b.home_work_location_name as location_description,
    b.department_home_name as home_department_description,
    b.job_title as job_title_description,
    b.assignment_status as position_status,
    b.worker_original_hire_date as original_hire_date,
    b.worker_rehire_date as rehire_date,
    b.worker_termination_date as termination_date,
    b.worker_type as worker_category_description,
    b.worker_group_value as benefits_eligibility_class_description,
    b.wage_law_coverage_short_name as flsa_description,
    b.ethnicity_long_name as eeo_ethnic_description,
    b.mail,
    b.user_principal_name as userprincipalname,
    b.report_to_employee_number as manager_df_employee_number,
    b.report_to_preferred_name_lastfirst as manager_name,
    b.report_to_mail as manager_mail,
    b.race_ethnicity_reporting,
    b.gender_identity,
    b.primary_grade_level_taught,
    b.base_remuneration_annual_rate_amount_amount_value as base_salary,

    s.salary_rule,
    s.scale_cy_salary,
    s.scale_ny_salary,
    s.scale_step,

    p.pm4_overall_score,
from {{ ref("base_people__staff_roster") }} as b
left join
    {{ ref("int_people__expected_next_year_salary") }} as s
    on b.employee_number = s.employee_number
left join pm_scores as p on b.employee_number = p.employee_number
where b.assignment_status not in ('Terminated', 'Deceased')
