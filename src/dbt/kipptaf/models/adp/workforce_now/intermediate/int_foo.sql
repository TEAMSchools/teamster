select
    w.work_assignment_worker_id,
    w.worker_original_hire_date,
    w.worker_rehire_date,
    w.worker_termination_date,

    w.work_assignment_assignment_status_effective_date,
    w.work_assignment_assignment_status_long_name,
    w.work_assignment_job_title,
    w.work_assignment__reports_to__associate_oid,
    w.work_assignment_home_work_location_name_long_name,
    w.work_assignment_home_work_location_name_short_name,

    w.organizational_unit_business_unit_assigned_name_long_name,
    w.organizational_unit_business_unit_assigned_name_short_name,
    w.organizational_unit_department_assigned_name_long_name,
    w.organizational_unit_department_assigned_name_short_name,

    p.person_birth_date,
    p.person_preferred_name_given_name,
    p.person_legal_name_given_name,
    p.person_preferred_name_family_name_1,
    p.person_legal_name_family_name_1,

-- en.employee_number,
from {{ ref("int_adp_workforce_now__worker") }} as w
inner join
    {{ ref("int_adp_workforce_now__person") }} as p
    on w.work_assignment_worker_id = p.person_worker_id
