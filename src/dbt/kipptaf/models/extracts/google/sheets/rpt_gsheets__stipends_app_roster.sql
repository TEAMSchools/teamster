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
            coalesce(
                sr.home_work_location_abbreviation, sr.home_work_location_name
            ) as location_abbr,
            case
                when
                    sr.home_work_location_name like '%Room%' or sr.home_work_location_name like '%Campus%'
                    and sr.business_unit_home_name not like '%Family%'
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

            coalesce(cc.name, sr.home_work_location_name) as campus,

            lc.dso_employee_number,
            lc.sl_employee_number,
            lc.head_of_school_employee_number,
            lc.mdso_employee_number,

        from {{ ref("base_people__staff_roster") }} as sr
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
    ),

    ktaf_approval as (

        select
            sr2.employee_number as report_to_chief_employee_number,
            sr2.preferred_name_lastfirst as reports_to_chief_preferred_name,
            sr2.job_title as reports_to_chief_job_title,
            sr2.department_home_name as reports_to_chief_department,
            sr1.employee_number as chief_employee_number,
            sr1.preferred_name_lastfirst as chief_preferred_name,
            sr1.job_title as chief_job_title,
            sr1.department_home_name as chief_department

        from {{ ref("base_people__staff_roster") }} as sr1
        left join
            {{ ref("base_people__staff_roster") }} as sr2
            on sr1.employee_number = sr2.report_to_employee_number
        where
            sr1.job_title like '%Chief%'
            and sr1.job_title like '%Officer%'
            and sr1.worker_termination_date is null
            and sr2.worker_termination_date is null

    ),

    regional_approval as (
        select
            employee_number,
            preferred_name_lastfirst,
            job_title,
            worker_termination_date,
            home_work_location_name as location,
            business_unit_home_name as region,
        from {{ ref("base_people__staff_roster") }} as sr
        where
            job_title in (
                'Managing Director of School Operations',
                'Managing Director of Operations',
                'Executive Director'
            )
            and worker_termination_date is null

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

    case
        when r.route = 'Instructional'
        then r.sl_employee_number
        when r.route = 'Operations'
        then r.dso_employee_number
        when r.route = 'CMO'
        then ka.report_to_chief_employee_number
        when r.route = 'Regional'
        then ra.employee_number
    end as first_approver_employee_number,
    case
        when r.route = 'Instructional'
        then r.head_of_school_employee_number
        when r.route = 'Operations'
        then r.mdso_employee_number
        when r.route = 'CMO'
        then ka.chief_employee_number
        when r.route = 'Regional'
        then ra.employee_number
    end as second_approver_employee_number,

from roster as r
left join
    ktaf_approval as ka
    on r.department = ka.reports_to_chief_department
    and r.route = 'CMO'
left join
    regional_approval as ra
on r.region = ra.region
    and r.route = 'Regional'
