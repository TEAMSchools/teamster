with
    suspension_att as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,

            count(*) as days_suspended_att,
        from {{ ref("int_powerschool__ps_attendance_daily") }}
        where att_code in ('OS', 'OSS', 'OSSP', 'S', 'ISS', 'SHI')
        group by studentid, academic_year, _dbt_source_relation
    )

select
    co.student_number,
    co.state_studentnumber,
    co.student_name as lastfirst,
    co.academic_year,
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
    co.region,
    co.fedethnicity,

    dli.student_id as dl_student_id,
    dli.incident_id,
    dli.reporting_incident_id,
    dli.status,
    dli.location,
    dli.reported_details,
    dli.admin_summary,
    dli.context,
    dli.update_ts_date as dl_timestamp,
    dli.infraction as incident_type,
    dli.is_referral,
    dli.category as referral_category,
    dli.penalty_name as penaltyname,
    dli.start_date as startdate,
    dli.end_date as enddate,
    dli.num_days as numdays,
    dli.is_suspension as issuspension,
    dli.behavior_category as `Behavior Category`,
    dli.nj_state_reporting as `NJ State Reporting`,
    dli.others_involved as `Others Involved`,
    dli.parent_contacted as `Parent Contacted`,
    dli.perceived_motivation as `Perceived Motivation`,
    dli.restraint_used as `Restraint Used`,
    dli.ssds_incident_id as `SSDS Incident ID`,
    dli.create_lastfirst as created_staff,
    dli.update_lastfirst as last_update_staff,

    d.name as term,

    att.days_suspended_att,

    'Referral' as dl_category,
from {{ ref("int_extracts__student_enrollments") }} as co
left join
    {{ ref("int_deanslist__incidents__penalties") }} as dli
    on co.student_number = dli.student_school_id
    and co.academic_year = dli.create_ts_academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="dli") }}
left join
    {{ ref("stg_reporting__terms") }} as d
    on co.schoolid = d.school_id
    and dli.create_ts_date between d.start_date and d.end_date
    and d.type = 'RT'
left join
    suspension_att as att
    on co.studentid = att.studentid
    and co.academic_year = att.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="att") }}
where co.rn_year = 1 and co.academic_year >= {{ var("current_academic_year") - 1 }}
