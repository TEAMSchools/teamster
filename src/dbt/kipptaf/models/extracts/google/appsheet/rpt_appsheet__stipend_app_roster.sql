/* roster that feeds into Stipend and Bonus AppSheet*/
select
    r.employee_number,
    r.payroll_group_code,
    r.worker_id,
    r.payroll_file_number,
    r.position_id,
    r.job_title,
    r.home_work_location_name,
    r.home_department_name,
    r.formatted_name,
    r.user_principal_name,
    r.google_email,
    r.assignment_status,
    r.home_business_unit_name,
    r.home_business_unit_code,
    r.worker_termination_date,
    r.home_work_location_campus_name,
from {{ ref("int_people__staff_roster") }} as r
