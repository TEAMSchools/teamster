select
    worker_id as associate_id,
    preferred_name_given_name as preferred_first_name,
    preferred_name_family_name as preferred_last_name,
    preferred_name_family_name
    || ', '
    || preferred_name_given_name as preferred_lastfirst,
    home_work_location_name as `location`,
    home_work_location_name as location_custom,
    department_home_name as department,
    department_home_name as subject_dept_custom,
    job_title,
    job_title as job_title_custom,
    report_to_preferred_name_family_name
    || ', '
    || report_to_preferred_name_given_name as reports_to,
    report_to_worker_id as manager_custom_assoc_id,
    if(is_prestart, 'Pre-Start', assignment_status) as position_status,
    worker_termination_date as termination_date,
    mail as email_addr,
    coalesce(worker_rehire_date, worker_original_hire_date) as hire_date,
    work_assignment_actual_start_date as position_start_date,
    employee_number as df_employee_number,
    report_to_employee_number as manager_df_employee_number,
    business_unit_home_name as legal_entity_name,
    user_principal_name as userprincipalname,
    payroll_file_number as file_number,
    position_id,
    legal_name_family_name || ', ' || legal_name_given_name as legal_name,
    communication_person_mobile as mobile_number,
from {{ ref("base_people__staff_roster") }}
