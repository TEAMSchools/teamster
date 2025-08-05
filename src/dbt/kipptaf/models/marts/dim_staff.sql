with staff_roster as (select *, from {{ ref("int_people__staff_roster") }})

select
    employee_number,
    home_business_unit_name as entity,
    home_work_location_name as `location`,
    home_work_location_grade_band as grade_band,
    home_department_name as department,
    job_title,
    reports_to_formatted_name as manager,
    worker_original_hire_date,
    work_assignment_actual_start_date,
    assignment_status,
    race_ethnicity_reporting,
    if(
        job_title
        in ('Teacher', 'Teacher in Residence', 'ESE Teacher', 'Learning Specialist'),
        true,
        false
    ) as is_teacher,
from staff_roster
