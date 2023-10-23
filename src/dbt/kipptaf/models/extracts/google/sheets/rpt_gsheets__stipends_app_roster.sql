with
    approval_loops as (
        select
            home_work_location_name as location,
            business_unit_home_name as region,
            department_home_name as department,
            preferred_name_lastfirst as first_approver_name,
            user_principal_name as first_approver_email,
            google_email as first_approver_google,
            report_to_preferred_name_lastfirst as second_approver_name,
            report_to_mail as second_approver_email,
            case
                when business_unit_home_name not like '%Miami%'
                then concat(report_to_sam_account_name, '@apps.teamschools.org')
                when business_unit_home_name like '%Miami%'
                then concat(report_to_sam_account_name, '@kippmiami.org')
            end as second_approver_google,
            employee_number as first_approver_employee_number,
            report_to_employee_number as second_approver_employee_number,
            case
                when department_home_name = 'Operations'
                then 'Operations'
                when department_home_name = 'School Leadership'
                then 'Instructional'
                when business_unit_home_name like '%Family%'
                then 'CMO'
                else 'Regional'
            end as route
        from {{ ref("base_people__staff_roster") }}
        where
            job_title in (
                'Director School Operations',
                'Director Campus Operations',
                'Director',
                'School Leader',
                'School Leader in Residence'
            )
            and assignment_status != 'Terminated'
    ),

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
                    sr.home_work_location_name not like '%Room%'
                    and sr.department_home_name in ('Operations', 'School Support')
                then 'Operations'
                when
                    sr.home_work_location_name not like '%Room%'
                    and sr.business_unit_home_name not like '%Family%'
                then 'Instructional'
                when
                    sr.home_work_location_name like '%Room%'
                    and sr.business_unit_home_name not like '%Family%'
                then 'Special'
                when
                    sr.home_work_location_name like '%Room%'
                    and sr.business_unit_home_name like '%Family%'
                then 'CMO'
                else 'Regional'
            end as route,
            coalesce(cc.name, sr.home_work_location_name) as campus,
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ ref("stg_people__campus_crosswalk") }} as cc
            on sr.home_work_location_name = cc.location_name
        where
            sr.worker_termination_date is null
            or sr.worker_termination_date > '2023-07-01'
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
    a.first_approver_employee_number,
    a.first_approver_name,
    a.first_approver_email,
    a.first_approver_google,
    a.second_approver_employee_number,
    a.second_approver_name,
    a.second_approver_email,
    a.second_approver_google

from roster as r
left join approval_loops as a on r.location = a.location and r.route = a.route
