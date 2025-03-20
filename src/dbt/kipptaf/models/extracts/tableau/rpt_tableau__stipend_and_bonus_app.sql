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

    r.formatted_name as teammate,
    r.job_title,
    r.department,
    r.location,
    r.entity,
    r.entity_short,
    r.position_id,
    r.payroll_group_code as company_code,

from {{ ref("stg_stipend_and_bonus__output") }} as o
left join
    {{ ref("rpt_appsheet__stipend_app_roster") }} as r
    on o.employee_number = r.employee_number
left join
    {{ ref("int_people__staff_roster") }} as r1
    on o.first_approver_employee_number = r1.employee_number
left join
    {{ ref("int_people__staff_roster") }} as r2
    on o.second_approver_employee_number = r2.employee_number
