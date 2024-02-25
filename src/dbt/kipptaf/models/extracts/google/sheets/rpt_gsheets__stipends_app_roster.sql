with
    roster as (
        select
            sr.employee_number,
            sr.payroll_group_code,
            sr.worker_id,
            sr.payroll_file_number as file_number,
            sr.position_id,
            sr.job_title,
            sr.home_work_location_name as location,
            sr.department_home_name as department,
            sr.preferred_name_lastfirst as preferred_name,
            sr.user_principal_name as email,
            sr.google_email,
            sr.assignment_status as status,
            sr.business_unit_home_name as region,
            sr.worker_termination_date,
            sr.report_to_employee_number as manager_employee_number,

            sr3.employee_number as grandmanager_employee_number,

            lc.dso_employee_number,
            lc.sl_employee_number,
            lc.head_of_school_employee_number,
            lc.mdso_employee_number,

            coalesce(
                sr.home_work_location_abbreviation, sr.home_work_location_name
            ) as location_abbr,
            case
                when
                    sr.business_unit_home_name not like '%Family%'
                    and (
                        sr.home_work_location_name like '%Room%'
                        or sr.home_work_location_name like '%Campus%'
                    )
                then 'Regional'
                when
                    sr.home_work_location_name not like '%Room%'
                    and sr.department_home_name in ('Operations', 'School Support')
                then 'Operations'
                when
                    sr.home_work_location_name not like '%Room%'
                    and sr.business_unit_home_name not like '%Family%'
                then 'Instructional'
                when
                    sr.home_work_location_name like '%Room%'
                    and sr.business_unit_home_name like '%Family%'
                then 'CMO'
                else 'Special'
            end as route,
            case
                when sr.job_title = 'Managing Director of School Operations'
                then 'Region Submitter'
                when sr.job_title = 'Managing Director of Operations'
                then 'Region Approver'
                when sr.job_title like 'Chief%Officer'
                then 'KTAF Approver'
                when sr.job_title like 'Chief%Strategist'
                then 'KTAF Approver'
                when sr2.job_title like 'Chief%Officer' 
                then 'KTAF Submitter'
            end as role_type,

            coalesce(cc.name, sr.home_work_location_name) as campus,
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ ref("base_people__staff_roster") }} as sr2
            on sr.report_to_employee_number = sr2.employee_number
        left join
        {{ ref('base_people__staff_roster') }} as sr3
        on sr2.report_to_employee_number = sr3.employee_number
        left join
            {{ ref("stg_people__campus_crosswalk") }} as cc
            on sr.home_work_location_name = cc.location_name
        left join
            {{ ref("int_people__leadership_crosswalk") }} as lc
            on sr.home_work_location_name = lc.home_work_location_name
        where
            sr.worker_termination_date is null
            or sr.worker_termination_date
            >= date({{ var("current_academic_year") }}, 7, 1)
    )

select
    r.employee_number,
    r.payroll_group_code,
    r.worker_id,
    r.file_number,
    r.position_id,
    r.job_title,
    r.location,
    r.department,
    r.preferred_name,
    r.email,
    r.google_email,
    r.status,
    r.region,
    r.worker_termination_date,
    r.location_abbr,
    r.route,
    r.campus,
    r.manager_employee_number,
    r.grandmanager_employee_number,
    r.role_type,

    case
        when
            r.employee_number in (
                r.sl_employee_number,
                r.dso_employee_number
            )
        then r.manager_employee_number
        when r.route = 'Instructional'
        then r.sl_employee_number
        when r.route = 'Operations'
        then r.dso_employee_number
        when r.route = 'CMO'
        then null
        when r.route = 'Regional'
        then null
    end as first_approver_employee_number,
    case
        when
            r.employee_number in (
                r.sl_employee_number,
                r.dso_employee_number
            )
        then r.grandmanager_employee_number
        when r.route = 'Instructional'
        then r.head_of_school_employee_number
        when r.route = 'Operations'
        then r.mdso_employee_number
        when r.route = 'CMO'
        then null
        when r.route = 'Regional'
        then null
    end as second_approver_employee_number,
from roster as r