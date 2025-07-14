select
    sr.employee_number,
    sr.formatted_name,
    sr.assignment_status,
    sr.home_business_unit_name,
    sr.home_work_location_name,
    sr.home_department_name,
    sr.job_title,
    sr.user_principal_name,
    sr.reports_to_formatted_name,
    sr.reports_to_user_principal_name,
    kb4.module_name,
    kb4.status,
    kb4.enrollment_date,
    kb4.start_date,
    kb4.completion_date,
    kb4.rn_enrollment,
from {{ ref("int_people__staff_roster") }} as sr
left join
    {{ ref("stg_knowbe4__training_enrollments") }} as kb4
    on sr.employee_number = safe_cast(kb4.user_employee_number as int)
