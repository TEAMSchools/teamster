select
    o.event_id,
    o.employee_number,
    o.stipend_type,
    o.pay_code,
    o.amount,
    o.payment_date,
    o.description,
    o.first_approval,
    o.first_approver_employee_number,
    o.second_approval,
    o.second_approver_employee_number,
    o.edited_by,
    o.edited_at,
    o.submitter,

    r.preferred_name_lastfirst as teammate,
    r.job_title,
    r.department_home_name as department,
    r.home_work_location_name as `location`,
    r.business_unit_home_name as entity,
    r.route,
    r.position_id,
    r.payroll_group_code as company_code,

    if(
        o.first_approver_employee_number is null and r.route = 'MDSO',
        'MDSO Queue',
        r1.preferred_name_lastfirst
    ) as first_approver,

    if(
        o.second_approver_employee_number is null and r.route = 'MDSO',
        'MDSO Queue',
        r2.preferred_name_lastfirst
    ) as second_approver,
from {{ ref("stg_stipend_and_bonus__output") }} as o
left join
    {{ ref("rpt_appsheet__stipend_app_roster") }} as r
    on o.employee_number = r.employee_number
left join
    {{ ref("base_people__staff_roster") }} as r1
    on o.first_approver_employee_number = r1.employee_number
left join
    {{ ref("base_people__staff_roster") }} as r2
    on o.second_approver_employee_number = r2.employee_number
