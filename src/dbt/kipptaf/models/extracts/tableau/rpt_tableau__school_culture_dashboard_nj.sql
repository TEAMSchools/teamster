with
    suspension_att as (
        select
            studentid,
            academic_year,
            _dbt_source_relation,

            count(*) as days_suspended_att,
        from {{ ref("int_powerschool__ps_attendance_daily") }}
        where att_code in ('OS', 'OSS', 'OSSP', 'S', 'ISS', 'SHI')
        group by studentid, academic_year, _dbt_source_relation
    )

select
    co.student_number,
    co.state_studentnumber,
    co.student_name as lastfirst,
    co.enroll_status,
    co.academic_year,
    co.region,
    co.reporting_schoolid,
    co.schoolid,
    co.school_name,
    co.school as school_abbreviation,
    co.grade_level,
    co.advisory_name as team,
    co.advisor_lastfirst as advisor_name,
    co.spedlep as iep_status,
    co.is_504 as c_504_status,
    co.lep_status,
    co.lunch_status as lunchstatus,
    co.is_retained_year,
    co.is_retained_ever,
    co.gender,
    co.ethnicity,
    co.fedethnicity,

    dlp.student_id as dl_student_id,
    dlp.incident_id,
    dlp.reporting_incident_id,
    dlp.status,
    dlp.location,
    dlp.reported_details,
    dlp.admin_summary,
    dlp.context,
    dlp.create_ts_date as dl_timestamp,
    dlp.infraction as incident_type,
    dlp.is_referral,
    dlp.is_active,
    dlp.category as referral_category,
    dlp.penalty_name as penaltyname,
    dlp.start_date as startdate,
    dlp.end_date as enddate,
    dlp.num_days as numdays,
    dlp.is_suspension as issuspension,
    dlp.create_lastfirst as created_staff,
    dlp.update_lastfirst as last_update_staff,
    dlp.behavior_category as `Behavior Category`,
    dlp.nj_state_reporting as `NJ State Reporting`,
    dlp.others_involved as `Others Involved`,
    dlp.parent_contacted as `Parent Contacted`,
    dlp.perceived_motivation as `Perceived Motivation`,
    dlp.restraint_used as `Restraint Used`,
    dlp.ssds_incident_id as `SSDS Incident ID`,

    d.name as term,

    att.days_suspended_att,

    'Referral' as dl_category,

    concat(
        'Week of ',
        format_date(
            '%m/%d',
            date_sub(
                dlp.create_ts_date,
                interval extract(dayofweek from dlp.create_ts_date) - 2 day
            )
        )
    ) as week_of,
from {{ ref("int_extracts__student_enrollments") }} as co
left join
    {{ ref("int_deanslist__incidents__penalties") }} as dlp
    on co.student_number = dlp.student_school_id
    and co.academic_year = dlp.create_ts_academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="dlp") }}
    and dlp.is_active
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as d
    on co.schoolid = d.school_id
    and dlp.create_ts_date between d.start_date and d.end_date
    and d.type = 'RT'
left join
    suspension_att as att
    on co.studentid = att.studentid
    and co.academic_year = att.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="att") }}
where
    co.rn_year = 1
    and co.region in ('Newark', 'Camden')
    and co.academic_year >= {{ var("current_academic_year") - 1 }}
