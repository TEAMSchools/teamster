select
    o.*,

    r.preferred_name_lastfirst as teammate,
    r.job_title,
    r.department_home_name as department,
    r.home_work_location_name as location,
    r.business_unit_home_name as entity,
    r.route,
    r.position_id,
    r.payroll_group_code as company_code,

    case
        when o.first_approver_employee_number is null and r.route = 'MDSO'
        then 'MDSO Queue'
        else r1.preferred_name_lastfirst
    end as first_approver,
    case
        when o.second_approver_employee_number is null and r.route = 'MDSO'
        then 'MDSO Queue'
        else r2.preferred_name_lastfirst
    end as second_approver,

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
