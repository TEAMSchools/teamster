{{ config(enabled=False) }}
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
    co.academic_year,
    co.reporting_schoolid,
    co.schoolid,
    co.school_name,
    co.school_abbreviation,
    co.grade_level,
    co.team,
    co.advisor_name,
    co.iep_status,
    co.c_504_status,
    co.lep_status,
    co.lunchstatus,
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
    dli.update_ts as dl_timestamp,
    dli.infraction as incident_type,
    dli.is_referral,
    dli.category as referral_category,
    concat(dli.create_last, ', ', dli.create_first) as created_staff,
    concat(dli.update_last, ', ', dli.update_first) as last_update_staff,

    'Referral' as dl_category,

    d.alt_name as term,

    dlp.penaltyname,
    dlp.startdate,
    dlp.enddate,
    dlp.numdays,
    dlp.issuspension,

    cf.`behavior category`,
    cf.`nj state reporting`,
    cf.`others involved`,
    cf.`parent contacted ?`,
    cf.`perceived motivation`,
    cf.`restraint used`,
    cf.`ssds incident id`,

    att.days_suspended_att,
from {{ ref("base_powerschool__student_enrollments") }} as co
left join
    {{ ref("stg_deanslist__incidents") }} as dli
    on co.student_number = dli.student_school_id
    and co.academic_year = dli.create_academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="dli") }}
left join
    {{ ref("stg_deanslist__incidents__penalties") }} as dlp
    on dli.incident_id = dlp.incident_id
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="dlp") }}
left join
    {{ ref("stg_deanslist__incidents__custom_fields") }} as cf
    on dli.incident_id = cf.incident_id
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="cf") }}
left join
    suspension_att as att
    on co.studentid = att.studentid
    and co.academic_year = att.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="att") }}
left join
    {{ ref("stg_reporting__terms") }} as d
    on co.schoolid = d.schoolid
    and dli.create_ts between d.start_date and d.end_date
    and d.identifier = 'RT'
where
    co.rn_year = 1
    and co.grade_level != 99
    and co.academic_year >= ({{ var("current_academic_year") }} - 1)
