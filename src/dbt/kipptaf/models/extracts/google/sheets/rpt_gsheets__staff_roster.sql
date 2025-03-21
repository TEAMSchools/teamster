-- trunk-ignore(sqlfluff/ST06)
select
    worker_id as associate_id,
    given_name as preferred_first_name,
    family_name_1 as preferred_last_name,
    formatted_name as preferred_lastfirst,
    home_work_location_name as `location`,
    home_work_location_name as location_custom,
    home_department_name as department,
    home_department_name as subject_dept_custom,
    job_title,
    job_title as job_title_custom,
    reports_to_formatted_name as reports_to,
    reports_to_worker_id as manager_custom_assoc_id,

    if(is_prestart, 'Pre-Start', assignment_status) as position_status,

    worker_termination_date as termination_date,
    mail as email_addr,

    coalesce(worker_rehire_date, worker_original_hire_date) as hire_date,

    work_assignment_actual_start_date as position_start_date,
    employee_number as df_employee_number,
    reports_to_employee_number as manager_df_employee_number,
    home_business_unit_name as legal_entity_name,
    user_principal_name as userprincipalname,
    payroll_file_number as file_number,
    position_id,

    legal_family_name || ', ' || legal_given_name as legal_name,

    personal_cell as mobile_number,
from {{ ref("int_people__staff_roster") }}
