with
    commlog as (
        select
            c.student_school_id,
            c.reason as commlog_reason,
            c.response as commlog_notes,
            c.topic as commlog_topic,
            c.call_date_time as commlog_datetime,
            c.call_date_time as commlog_date,
            c._dbt_source_relation,
            c.call_type as commlog_type,
            c.call_status as commlog_status,

            f.init_notes as followup_init_notes,
            f.followup_notes as followup_close_notes,
            f.outstanding,

            concat(u.first_name, ' ', u.last_name) as commlog_staff_name,
            concat(f.c_first, ' ', f.c_last) as followup_staff_name,
        from {{ ref("stg_deanslist__comm_log") }} as c
        inner join
            {{ ref("stg_deanslist__users") }} as u
            on c.user_id = u.dl_user_id
            and {{ union_dataset_join_clause(left_alias="c", right_alias="u") }}
        left join
            {{ ref("stg_deanslist__followups") }} as f
            on c.record_id = f.source_id
            and {{ union_dataset_join_clause(left_alias="c", right_alias="f") }}
        where c.reason like 'Att:%' and c.call_status = 'Completed'
    )

select
    co.student_number,
    co.lastfirst,
    co.academic_year,
    co.region,
    co.school_level,
    co.reporting_schoolid,
    co.school_abbreviation,
    co.grade_level,
    co.advisory_name as team,
    co.spedlep as iep_status,
    co.gender,
    co.is_retained_year,
    co.enroll_status,

    att.att_date,
    att.att_comment,

    ac.att_code,

    cl.commlog_staff_name,
    cl.commlog_reason,
    cl.commlog_notes,
    cl.commlog_topic,
    cl.commlog_type,
    cl.commlog_status,
    cl.followup_staff_name,
    cl.followup_init_notes,
    cl.followup_close_notes,

    rt.name as term,

    a.days_absent_unexcused as abs_count,
    a.ada,

    if(
        co.school_level = 'HS', co.advisor_lastfirst, cast(co.grade_level as string)
    ) as drill_down,
    if(
        cl.commlog_reason is not null and cl.commlog_reason not like 'Att: Unknown%',
        true,
        false
    ) as is_successful,
    if(co.school_level = 'HS', co.advisor_lastfirst, cc.section_number) as homeroom,
    row_number() over (
        partition by co.studentid, att.att_date order by cl.commlog_datetime desc
    ) as rn_date,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("stg_powerschool__attendance") }} as att
    on co.studentid = att.studentid
    and att.att_date between co.entrydate and co.exitdate
    and {{ union_dataset_join_clause(left_alias="co", right_alias="att") }}
    and att.att_mode_code = 'ATT_ModeDaily'
inner join
    {{ ref("stg_powerschool__attendance_code") }} as ac
    on att.attendance_codeid = ac.id
    and {{ union_dataset_join_clause(left_alias="att", right_alias="ac") }}
    and ac.att_code like 'A%'
left join
    {{ ref("stg_powerschool__cc") }} as cc
    on att.studentid = cc.studentid
    and att.att_date between cc.dateenrolled and cc.dateleft
    and {{ union_dataset_join_clause(left_alias="att", right_alias="cc") }}
    and cc.course_number = 'HR'
left join
    commlog as cl
    on co.student_number = cl.student_school_id
    and att.att_date = safe_cast(cl.commlog_date as date)
    and {{ union_dataset_join_clause(left_alias="co", right_alias="cl") }}
left join
    {{ ref("int_powerschool__ada") }} as a
    on co.studentid = a.studentid
    and co.yearid = a.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="a") }}
left join
    {{ ref("stg_reporting__terms") }} as rt
    on co.schoolid = rt.school_id
    and att.att_date between rt.start_date and rt.end_date
    and rt.type = 'RT'
where
    co.academic_year = {{ var("current_academic_year") }}
    and att.att_date <= current_date('America/New_York')
