with
    school_leadership as (
        select
            home_work_location_name as location,
            business_unit_home_name as region,
            coalesce(
                max(
                    case
                        when job_title = 'Director School Operations'
                        then employee_number
                    end
                ),
                max(
                    case
                        when job_title = 'Director Campus Operations'
                        then employee_number
                    end
                )
            ) as dso_employee_number,
            coalesce(
                max(case when job_title = 'School Leader' then employee_number end),
                max(
                    case
                        when job_title = 'School Leader in Residence'
                        then employee_number
                    end
                )
            ) as sl_employee_number
        from {{ ref("base_people__staff_roster") }}
        where
            job_title in (
                'Director School Operations',
                'Director Campus Operations',
                'School Leader',
                'School Leader in Residence'
            )
            and assignment_status != 'Terminated'
        group by home_work_location_name, business_unit_home_name
    )

select
    l.location,
    l.region,
    l.dso_employee_number,
    l.sl_employee_number,

    sr1.preferred_name_lastfirst as dso,
    sr1.mail as dso_mail,
    sr1.google_email as dso_google_mail,
    sr1.job_title as dso_title,
    sr1.report_to_employee_number as mdso_employee_number,

    sr2.preferred_name_lastfirst as school_leader,
    sr2.mail as school_leader_mail,
    sr2.google_email as school_leader_google_mail,
    sr2.job_title as school_leader_job_title,
    sr2.report_to_employee_number as hos_employee_number,

    sr3.preferred_name_lastfirst as mdso,
    sr3.mail as mdso_mail,
    sr3.google_email as mdso_google_mail,
    sr3.job_title as mdso_job_title,

    sr4.preferred_name_lastfirst as head_of_schools,
    sr4.mail as head_of_schools_mail,
    sr4.google_email as head_of_schools_google_mail,
    sr4.job_title as head_of_schools_job_title,

from school_leadership as l
left join
    {{ ref("base_people__staff_roster") }} as sr1
    on l.dso_employee_number = sr1.employee_number
left join
    {{ ref("base_people__staff_roster") }} as sr2
    on l.sl_employee_number = sr2.employee_number
left join
    {{ ref("base_people__staff_roster") }} as sr3
    on sr1.report_to_employee_number = sr3.employee_number
left join
    {{ ref("base_people__staff_roster") }} as sr4
    on sr2.report_to_employee_number = sr4.employee_number
