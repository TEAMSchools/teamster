with
    school_leadership as (
        select
            home_work_location_powerschool_school_id,
            home_work_location_name,
            business_unit_home_name,
            coalesce(
                max(
                    if(job_title = 'Director School Operations', employee_number, null)
                ),
                max(if(job_title = 'Director Campus Operations', employee_number, null))
            ) as dso_employee_number,
            coalesce(
                max(if(job_title = 'School Leader', employee_number, null)),
                max(if(job_title = 'School Leader in Residence', employee_number, null))
            ) as sl_employee_number,
        from {{ ref("base_people__staff_roster") }}
        where
            job_title in (
                'Director School Operations',
                'Director Campus Operations',
                'School Leader',
                'School Leader in Residence'
            )
            and assignment_status != 'Terminated'
        group by
            home_work_location_powerschool_school_id,
            home_work_location_name,
            business_unit_home_name
    )

select
    l.home_work_location_powerschool_school_id,
    l.home_work_location_name,
    l.business_unit_home_name,
    l.dso_employee_number,
    l.sl_employee_number,

    sl.preferred_name_lastfirst as school_leader_preferred_name_lastfirst,
    sl.mail as school_leader_mail,
    sl.google_email as school_leader_google_email,
    sl.job_title as school_leader_job_title,
    sl.report_to_employee_number as school_leader_report_to_employee_number,

    hos.preferred_name_lastfirst as head_of_school_preferred_name_lastfirst,
    hos.mail as head_of_school_mail,
    hos.google_email as head_of_school_google_email,
    hos.job_title as head_of_school_job_title,

    dso.preferred_name_lastfirst as dso_preferred_name_lastfirst,
    dso.mail as dso_mail,
    dso.google_email as dso_google_email,
    dso.job_title as dso_job_title,
    dso.report_to_employee_number as dso_report_to_employee_number,

    mdso.preferred_name_lastfirst as mdso_preferred_name_lastfirst,
    mdso.mail as mdso_mail,
    mdso.google_email as mdso_google_email,
    mdso.job_title as mdso_job_title,
from school_leadership as l
left join
    {{ ref("base_people__staff_roster") }} as sl
    on l.sl_employee_number = sl.employee_number
left join
    {{ ref("base_people__staff_roster") }} as hos
    on sl.report_to_employee_number = hos.employee_number
left join
    {{ ref("base_people__staff_roster") }} as dso
    on l.dso_employee_number = dso.employee_number
left join
    {{ ref("base_people__staff_roster") }} as mdso
    on dso.report_to_employee_number = mdso.employee_number
