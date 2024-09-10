with
    roster as (
        select
            sr.employee_number,
            sr.payroll_group_code,
            sr.worker_id,
            sr.payroll_file_number as file_number,
            sr.position_id,
            sr.job_title,
            sr.home_work_location_name as `location`,
            sr.department_home_name as department,
            sr.preferred_name_lastfirst as preferred_name,
            sr.user_principal_name as email,
            sr.google_email,
            sr.assignment_status as `status`,
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
            end as `route`,
            case
                when
                    sr.job_title like '%Director%'
                    and sr.business_unit_home_name not like '%Family%'
                then 'Region Submitter'
                when
                    sr.department_home_name = 'School Support'
                    and sr.home_work_location_name like '%Room%'
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
            {{ ref("base_people__staff_roster") }} as sr3
            on sr2.report_to_employee_number = sr3.employee_number
        left join
            {{ ref("stg_people__campus_crosswalk") }} as cc
            on sr.home_work_location_name = cc.location_name
        left join
            {{ ref("int_people__leadership_crosswalk") }} as lc
            on sr.home_work_location_name = lc.home_work_location_name
        where
            sr.worker_termination_date is null
            or sr.worker_termination_date >= '{{ var("current_academic_year") }}-07-01'
    )

select
    employee_number,
    payroll_group_code,
    worker_id,
    file_number,
    position_id,
    job_title,
    `location`,
    department,
    preferred_name,
    email,
    google_email,
    `status`,
    region,
    worker_termination_date,
    location_abbr,
    `route`,
    campus,
    manager_employee_number,
    grandmanager_employee_number,
    role_type,

    case
        when employee_number in (sl_employee_number, dso_employee_number)
        then manager_employee_number
        when `route` = 'Instructional'
        then sl_employee_number
        when `route` = 'Operations'
        then dso_employee_number
        when `route` = 'CMO'
        then null
        when `route` = 'Regional'
        then null
    end as first_approver_employee_number,
    case
        when employee_number in (sl_employee_number, dso_employee_number)
        then grandmanager_employee_number
        when `route` = 'Instructional'
        then head_of_school_employee_number
        when `route` = 'Operations'
        then mdso_employee_number
        when `route` = 'CMO'
        then null
        when `route` = 'Regional'
        then null
    end as second_approver_employee_number,
from roster
