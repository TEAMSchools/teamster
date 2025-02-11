select
    b.employee_number as df_employee_number,
    b.legal_name__given_name as first_name,
    b.legal_name__family_name_1 as last_name,
    b.given_name as preferred_first,
    b.family_name_1 as preferred_last,
    b.assignment_status as position_status,
    b.worker_original_hire_date as original_hire_date,
    b.worker_rehire_date as rehire_date,
    b.worker_termination_date as termination_date,
    b.worker_type_code as worker_category_description,
    b.wage_law_coverage as benefits_eligibility_class_description,
    b.wage_law_name as flsa_description,
    b.race_ethnicity as eeo_ethnic_description,
    b.mail,
    b.user_principal_name as userprincipalname,

    b.race_ethnicity_reporting,
    b.gender_identity,

    m.employee_number as manager_df_employee_number,
    m.mail as manager_mail,

    s.ay_business_unit,
    s.ay_job_title,
    s.ay_location,
    s.ay_salary,
    s.academic_year,
    s.ay_pm4_overall_score,
    s.ay_pm4_overall_tier,
    s.ay_primary_grade_level_taught,
    s.scale_cy_salary,
    s.scale_ny_salary,
    s.scale_step,
    s.pm_salary_increase,
    s.seat_tracker_id_number,
    s.ny_location,
    s.ny_dept,
    s.ny_title,
    s.nonrenewal_reason,
    s.nonrenewal_notes,
    s.ny_salary,
    s.salary_rule,

    concat(b.family_name_1,', ',b.given_name) as preferred_name,
    concat(m.family_name_1,', ',m.given_name) as manager_name,
from {{ ref("int_people__staff_roster") }} as b
left join {{ ref("int_people__staff_roster")}} as m
    on b.reports_to_employee_number = m.employee_number
left join
    {{ ref("int_people__renewal_status") }} as s
    on b.employee_number = s.employee_number
    and s.academic_year = {{ var("current_academic_year") }}
