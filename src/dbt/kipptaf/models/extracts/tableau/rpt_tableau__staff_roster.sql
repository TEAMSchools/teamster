select
    b.employee_number as df_employee_number,
    b.worker_id as associate_id,
    b.position_id,
    b.payroll_file_number as file_number,
    b.legal_given_name as first_name,
    b.legal_family_name as last_name,
    b.given_name as preferred_first,
    b.family_name_1 as preferred_last,
    b.formatted_name as preferred_name,
    b.home_business_unit_name as legal_entity_name,
    b.home_work_location_name as location_description,
    b.home_department_name as home_department_description,
    b.job_title as job_title_description,
    b.management_position_indicator as is_management,
    b.assignment_status as position_status,
    b.assignment_status_reason as termination_reason_description,
    b.worker_original_hire_date as original_hire_date,
    b.worker_rehire_date as rehire_date,
    b.worker_termination_date as termination_date,
    b.work_assignment_actual_start_date as position_start_date,
    b.payroll_group_code as payroll_company_code,
    b.worker_type_code as worker_category_description,
    b.benefits_eligibility_class as benefits_eligibility_class_description,
    b.wage_law_coverage as flsa_description,
    b.ethnicity_code as eeo_ethnic_description,
    b.birth_date,
    b.legal_address_line_one as `address`,
    b.legal_address_city_name as primary_address_city,
    b.legal_address_country_subdivision_level_1_code
    as primary_address_state_territory_code,
    b.legal_address_postal_code as primary_address_zip_postal_code,
    b.personal_cell as personal_contact_personal_mobile,
    b.mail,
    b.user_principal_name as userprincipalname,
    b.reports_to_employee_number as manager_df_employee_number,
    b.reports_to_worker_id as manager_custom_assoc_id,
    b.reports_to_formatted_name as manager_name,
    b.reports_to_mail as manager_mail,
    b.race_ethnicity,
    b.is_hispanic,
    b.race_ethnicity_reporting,
    b.gender_identity,
    b.relay_status,
    b.community_grew_up,
    b.community_professional_exp,
    b.alumni_status,
    b.path_to_education,
    b.level_of_education,
    b.base_remuneration_annual_rate_amount as base_salary,

    ye.years_at_kipp_total,
    ye.years_teaching_total,
    ye.years_experience_total,

    tgl.grade_level as primary_grade_level_taught,

    /* retired fields, kept to not break tableau */
    null as salesforce_job_position_name_custom,
    null as is_regional_staff,
    null as maiden_name,
    null as eeo_ethnic_code,
    null as subject_dept_custom,
    null as job_title_custom,
    null as location_custom,
    null as this_is_a_management_position,
    null as reports_to_name,
    null as gender,
    null as grades_taught_custom,

    lc.school_leader_mail,
    lc.school_leader_preferred_name_lastfirst,
    lc.dso_mail,
    lc.dso_preferred_name_lastfirst,
from {{ ref("int_people__staff_roster") }} as b
left join
    {{ ref("int_people__years_experience") }} as ye
    on b.employee_number = ye.employee_number
    and ye.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on b.powerschool_teacher_number = tgl.teachernumber
    and tgl.academic_year = {{ var("current_academic_year") }}
    and tgl.grade_level_rank = 1
left join
    {{ ref("int_people__leadership_crosswalk") }} as lc
    on b.home_work_location_name = lc.home_work_location_name
