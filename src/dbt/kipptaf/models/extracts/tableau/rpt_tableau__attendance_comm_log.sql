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
    ),
    ada as (
        select
            studentid,
            _dbt_source_relation,
            yearid,
            round(avg(cast(attendancevalue as numeric)), 2) as ada,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where
            membershipvalue = 1
            and calendardate <= cast(current_date('America/New_York') as date)
        group by studentid, yearid, _dbt_source_relation
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

    gpa.gpa_y1,
    gpa.n_failing_y1,

    null as read_lvl,
    null as goal_status,

    rt.name as term,

    case
        when co.school_level = 'HS'
        then co.advisor_lastfirst
        else cast(co.grade_level as string)
    end as drill_down,
    case
        when
            (
                cl.commlog_reason is not null
                and cl.commlog_reason not like 'Att: Unknown%'
            )
        then true
        else false
    end as is_successful,
    count(distinct att.att_date) over (partition by co.student_number) as abs_count,
    max(
        case when cl.commlog_reason = 'Chronic Absence: 3' then true else false end
    ) over (partition by co.student_number, co.academic_year) as is_chronic_3,
    max(
        case when cl.commlog_reason = 'Chronic Absence: 6' then true else false end
    ) over (partition by co.student_number, co.academic_year) as is_chronic_6,
    max(
        case when cl.commlog_reason = 'Chronic Absence: 10' then true else false end
    ) over (partition by co.student_number, co.academic_year) as is_chronic_10,
    max(
        case when cl.commlog_reason = 'Chronic Absence: 10+' then true else false end
    ) over (partition by co.student_number, co.academic_year) as is_chronic_10_plus,
    max(
        case when cl.commlog_reason = 'Chronic Absence: 20' then true else false end
    ) over (partition by co.student_number, co.academic_year) as is_chronic_20,
    max(
        case when cl.commlog_reason = 'Chronic Absence: 20+' then true else false end
    ) over (partition by co.student_number, co.academic_year) as is_chronic_20_plus,
    ada.ada,

    case
        when att.schoolid = 73253 then co.advisor_lastfirst else cc.section_number
    end as homeroom,
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
    {{ ref("int_powerschool__gpa_term") }} as gpa
    on co.studentid = gpa.studentid
    and co.yearid = gpa.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
    and gpa.is_current
left join
    commlog as cl
    on co.student_number = cl.student_school_id
    and att.att_date = safe_cast(cl.commlog_date as date)
    and {{ union_dataset_join_clause(left_alias="co", right_alias="cl") }}
left join
    ada
    on co.studentid = ada.studentid
    and co.yearid = ada.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ada") }}
left join
    {{ ref("stg_reporting__terms") }} as rt
    on co.schoolid = rt.school_id
    and att.att_date between rt.start_date and rt.end_date
    and rt.type = 'RT'
where
    co.academic_year = {{ var("current_academic_year") }}
    and att.att_date <= current_date('America/New_York')
