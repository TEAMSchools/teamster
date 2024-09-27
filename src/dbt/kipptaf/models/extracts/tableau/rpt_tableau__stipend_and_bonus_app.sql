select
    r.preferred_name_lastfirst,
    r.job_title,
    r.department_home_name,
    r.home_work_location_name,
    r.business_unit_home_name,
    r.route,

    o.*,

    case
    when o.first_approver_employee_number is null and route = 'MDSO'
    then 'MDSO Queue'
    else r1.preferred_name_lastfirst
    end as first_approver,
    case
    when o.second_approver_employee_number is null and route = 'MDSO'
    then 'MDSO Queue'
    else r2.preferred_name_lastfirst
    end as second_approver,

from {{ ref("rpt_appsheet__stipend_app_roster") }} as r
left join
    {{ ref("stg_stipend_and_bonus__output") }} as o
    on r.employee_number = o.employee_number
left join
    {{ ref("base_people__staff_roster") }} as r1
    on o.first_approver_employee_number = r1.employee_number
left join
    {{ ref("base_people__staff_roster") }} as r2
    on o.second_approver_employee_number = r2.employee_number