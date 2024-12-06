select
    b.employee_number as df_employee_number,
    b.legal_given_name as first_name,
    b.legal_family_name as last_name,
    b.given_name as preferred_first,
    b.family_name_1 as preferred_last,
    b.formatted_name as preferred_name,
    b.home_business_unit_name as legal_entity_name,
    b.home_work_location_name as location_description,
    b.home_department_name as home_department_description,
    b.job_title as job_title_description,
    b.assignment_status as position_status,
    b.worker_original_hire_date as original_hire_date,
    b.worker_rehire_date as rehire_date,
    b.worker_termination_date as termination_date,
    b.worker_type_code as worker_category_description,
    b.benefits_eligibility_class as benefits_eligibility_class_description,
    b.wage_law_coverage as flsa_description,
    b.ethnicity_code as eeo_ethnic_description,
    b.mail,
    b.user_principal_name as userprincipalname,
    b.reports_to_employee_number as manager_df_employee_number,
    b.reports_to_formatted_name as manager_name,
    b.reports_to_mail as manager_mail,
    b.race_ethnicity_reporting,
    b.gender_identity,
    b.base_remuneration_annual_rate_amount as base_salary,

    s.salary_rule,
    s.scale_cy_salary,
    s.scale_ny_salary,
    s.scale_step,

    p.final_score as pm4_overall_score,

    tgl.grade_level as primary_grade_level_taught,
from {{ ref("int_people__staff_roster") }} as b
left join
    {{ ref("int_people__expected_next_year_salary") }} as s
    on b.employee_number = s.employee_number
left join
    {{ ref("int_performance_management__overall_scores") }} as p
    on b.employee_number = p.employee_number
    and p.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on b.powerschool_teacher_number = tgl.teachernumber
    and tgl.academic_year = {{ var("current_academic_year") }}
    and tgl.grade_level_rank = 1
where b.assignment_status not in ('Terminated', 'Deceased')
