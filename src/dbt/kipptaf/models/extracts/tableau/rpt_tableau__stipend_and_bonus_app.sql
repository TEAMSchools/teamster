-- trunk-ignore(sqlfluff/ST06): contract column order is mandated
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
    r.entity_short,
    r.position_id,
    r.payroll_group_code as company_code,

    lc.location_clean_name,
    lc.campus_name,

    case
        r3.home_business_unit_name
        when 'TEAM'
        then 'TEAM Academy Charter School'
        when 'KCNA'
        then 'KIPP Cooper Norcross Academy'
        when 'MIA'
        then 'KIPP Miami'
        when 'KNJ'
        then 'KIPP TEAM and Family Schools Inc.'
        else r3.home_business_unit_name
    end as home_business_unit_name,
    r3.home_department_name,
    r3.job_function,
    r3.job_title,

    r3.mail,
    r3.user_principal_name,
    r3.sam_account_name,

    r3.reports_to_mail,
    r3.reports_to_sam_account_name,

from {{ ref("stg_google_appsheet__stipend_and_bonus__output") }} as o
left join
    {{ ref("rpt_appsheet__stipend_app_roster") }} as r
    on o.employee_number = r.employee_number
left join
    {{ ref("int_people__staff_roster") }} as r1
    on o.first_approver_employee_number = r1.employee_number
left join
    {{ ref("int_people__staff_roster") }} as r2
    on o.second_approver_employee_number = r2.employee_number
left join
    {{ ref("int_people__staff_roster") }} as r3
    on o.employee_number = r3.employee_number
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on r3.home_work_location_name = lc.location_name
