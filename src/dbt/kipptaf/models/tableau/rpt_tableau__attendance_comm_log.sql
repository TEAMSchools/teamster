{{ config(enabled=False) }}
with
    commlog as (
        select
            c.student_school_id,
            c.reason as commlog_reason,
            c.response as commlog_notes,
            c.call_topic as commlog_topic,
            c.call_date_time as commlog_datetime,
            c.call_date_time as commlog_date,
            c._dbt_source_relation,

            concat(u.first_name, ' ', u.last_name) as commlog_staff_name,

            f.init_notes as followup_init_notes,
            f.followup_notes as followup_close_notes,
            f.outstanding,
            concat(f.c_first, ' ', f.c_last) as followup_staff_name,
        from {{ ref("stg_deanslist__comm_log") }} as c
        inner join
            {{ ref("stg_deanslist__users") }} as u
            on c.dluser_id = u.dluser_id
            and {{ union_dataset_join_clause(left_alias="c", right_alias="u") }}
        left join
            {{ ref("stg_deanslist__followups") }} as f
            on c.followup_id = f.followup_id
            and {{ union_dataset_join_clause(left_alias="c", right_alias="f") }}
        where (c.reason like 'Att:%' or c.reason like 'Chronic%')
    ),

    ada as (
        select
            studentid,
            _dbt_source_relation,
            yearid,
            round(avg(cast(attendancevalue as numeric)), 2) as ada,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where membershipvalue = 1 and calendardate <= cast(sysdatetime() as date)
        group by studentid, yearid, _dbt_source_relation
    )

select
    co.student_number,
    co.lastfirst,
    co.academic_year,
    co.region,
    co.reporting_schoolid,
    co.grade_level,
    co.team,
    co.iep_status,
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
    cl.followup_staff_name,
    cl.followup_init_notes,
    cl.followup_close_notes,

    ada.ada,

    gpa.gpa_y1,
    gpa.n_failing_y1,

    {# TODO #}
    null as read_lvl,
    null as goal_status,

    rt.alt_name as term,

    case
        when att.schoolid = 73253 then co.advisor_name else cc.section_number
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
    {{ ref("stg_powerschool__cc") }}
    on att.studentid = cc.studentid
    and att.att_date between cc.dateenrolled and cc.dateleft
    and {{ union_dataset_join_clause(left_alias="att", right_alias="cc") }}
    and cc.course_number = 'HR'
left join
    {{ ref("int_powerschool__gpa_term") }} as gpa
    on co.student_number = gpa.student_number
    and co.academic_year = gpa.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
    and gpa.is_current
left join
    commlog as cl
    on co.student_number = cl.student_school_id
    and att.att_date = cl.commlog_date
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
{# TODO
left join
    lit.achieved_by_round_static as r
    on co.student_number = r.student_number
    and co.academic_year = r.academic_year
    and r.is_curterm = 1 
#}
where co.academic_year = {{ var("current_academic_year") }}
