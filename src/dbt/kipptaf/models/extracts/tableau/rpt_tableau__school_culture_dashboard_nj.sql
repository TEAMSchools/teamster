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
    co.lastfirst,
    co.enroll_status,
    co.academic_year,
    co.region,
    co.reporting_schoolid,
    co.schoolid,
    co.school_name,
    co.school_abbreviation,
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

    dli.student_id as dl_student_id,
    dli.incident_id,
    dli.reporting_incident_id,
    dli.status,
    dli.location,
    dli.reported_details,
    dli.admin_summary,
    dli.context,
    dli.create_ts_date as dl_timestamp,
    dli.infraction as incident_type,
    dli.is_referral,
    dli.is_active,
    dli.category as referral_category,

    dlp.penalty_name as penaltyname,
    dlp.start_date as startdate,
    dlp.end_date as enddate,
    dlp.num_days as numdays,
    dlp.is_suspension as issuspension,

    -- trunk-ignore-begin(sqlfluff/RF05)
    cf.behavior_category as `Behavior Category`,
    cf.nj_state_reporting as `NJ State Reporting`,
    cf.others_involved as `Others Involved`,
    cf.parent_contacted as `Parent Contacted`,
    cf.perceived_motivation as `Perceived Motivation`,
    cf.restraint_used as `Restraint Used`,
    cf.ssds_incident_id as `SSDS Incident ID`,
    -- trunk-ignore-end(sqlfluff/RF05)
    d.name as term,

    att.days_suspended_att,

    'Referral' as dl_category,

    concat(dli.create_last, ', ', dli.create_first) as created_staff,
    concat(dli.update_last, ', ', dli.update_first) as last_update_staff,
    concat(
        'Week of ',
        format_date(
            '%m/%d',
            date_sub(
                dli.create_ts_date,
                interval extract(dayofweek from dli.create_ts_date) - 2 day
            )
        )
    ) as week_of,
from {{ ref("base_powerschool__student_enrollments") }} as co
left join
    {{ ref("stg_deanslist__incidents") }} as dli
    on co.student_number = dli.student_school_id
    and co.academic_year = dli.create_ts_academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="dli") }}
    and dli.is_active
left join
    {{ ref("stg_deanslist__incidents__penalties") }} as dlp
    on dli.incident_id = dlp.incident_id
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="dlp") }}
left join
    {{ ref("int_deanslist__incidents__custom_fields__pivot") }} as cf
    on dli.incident_id = cf.incident_id
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="cf") }}
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
where
    co.rn_year = 1
    and co.region in ('Newark', 'Camden')
    and co.grade_level != 99
    and co.academic_year >= ({{ var("current_academic_year") }} - 1)
