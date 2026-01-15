with
    staff_roster as (
        select
            employee_number,
            formatted_name,
            mail,
            sam_account_name,
            google_email,
            job_title,
            home_work_location_name,
            home_work_location_region,
            home_work_location_powerschool_school_id,
            home_work_location_abbreviation,
            home_work_location_campus_name,
            reports_to_employee_number,
        from {{ ref("int_people__staff_roster") }}
        where
            job_title in (
                'Director School Operations',
                'Director Campus Operations',
                'Managing Director of Operations',
                'School Leader',
                'School Leader in Residence'
            )
            and assignment_status != 'Terminated'
            and home_work_location_powerschool_school_id != 0
    ),

    school_leadership as (
        select
            home_work_location_name,
            home_work_location_region,
            home_work_location_powerschool_school_id,
            home_work_location_abbreviation,
            home_work_location_campus_name,

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
        from staff_roster
        group by
            home_work_location_name,
            home_work_location_region,
            home_work_location_powerschool_school_id,
            home_work_location_abbreviation,
            home_work_location_campus_name
    ),

    mdo as (
        select
            home_work_location_region,

            max(
                if(job_title = 'Managing Director of Operations', employee_number, null)
            ) as mdo_employee_number,
        from staff_roster
        group by home_work_location_region
    )

select
    l.home_work_location_powerschool_school_id,
    l.home_work_location_name,
    l.home_work_location_abbreviation,
    l.home_work_location_campus_name,
    l.dso_employee_number,
    l.sl_employee_number,

    sl.formatted_name as school_leader_preferred_name_lastfirst,
    sl.mail as school_leader_mail,
    sl.google_email as school_leader_google_email,
    sl.job_title as school_leader_job_title,
    sl.reports_to_employee_number as school_leader_report_to_employee_number,
    sl.sam_account_name as school_leader_sam_account_name,

    hos.employee_number as head_of_school_employee_number,
    hos.formatted_name as head_of_school_preferred_name_lastfirst,
    hos.mail as head_of_school_mail,
    hos.google_email as head_of_school_google_email,
    hos.job_title as head_of_school_job_title,
    hos.sam_account_name as head_of_school_sam_account_name,

    dso.formatted_name as dso_preferred_name_lastfirst,
    dso.mail as dso_mail,
    dso.google_email as dso_google_email,
    dso.job_title as dso_job_title,
    dso.reports_to_employee_number as dso_report_to_employee_number,
    dso.sam_account_name as dso_sam_account_name,

    mdso.employee_number as mdso_employee_number,
    mdso.formatted_name as mdso_preferred_name_lastfirst,
    mdso.mail as mdso_mail,
    mdso.google_email as mdso_google_email,
    mdso.job_title as mdso_job_title,
    mdso.sam_account_name as mdso_sam_account_name,

    mdo.employee_number as mdo_employee_number,
    mdo.formatted_name as mdo_preferred_name_lastfirst,
    mdo.mail as mdo_mail,
    mdo.google_email as mdo_google_email,
    mdo.job_title as mdo_job_title,
    mdo.sam_account_name as mdo_sam_account_name,
from school_leadership as l
left join staff_roster as sl on l.sl_employee_number = sl.employee_number
left join staff_roster as hos on sl.reports_to_employee_number = hos.employee_number
left join staff_roster as dso on l.dso_employee_number = dso.employee_number
left join staff_roster as mdso on dso.reports_to_employee_number = mdso.employee_number
left join mdo as m on l.home_work_location_region = m.home_work_location_region
left join staff_roster as mdo on m.mdo_employee_number = mdo.employee_number
