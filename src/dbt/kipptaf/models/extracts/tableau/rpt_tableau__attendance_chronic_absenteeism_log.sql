with
    abs_count as (
        select
            co.student_number,
            co.student_name,
            co.region,
            co.reporting_schoolid,
            co.school,
            co.grade_level,
            co.advisor_lastfirst as team,

            count(att.att_date) as n_absences,
        from {{ ref("int_extracts__student_enrollments") }} as co
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
            and ac.att_code like 'A%'  -- change to exclude AE
        where
            co.academic_year = {{ var("current_academic_year") }}
            and co.rn_year = 1
            and co.enroll_status = 0
        group by
            co.student_number,
            co.student_name,
            co.region,
            co.reporting_schoolid,
            co.school,
            co.grade_level,
            co.advisor_lastfirst
    )

select
    ac.student_number,
    ac.student_name as lastfirst,
    ac.region,
    ac.reporting_schoolid,
    ac.school as school_abbreviation,
    ac.grade_level,
    ac.advisor_lastfirst as team,
    ac.n_absences,

    cl.user_full_name as commlog_staff_name,
    cl.reason as commlog_reason,
    cl.response as commlog_notes,
    cl.topic as commlog_topic,

    null as followup_staff_name,
    null as followup_init_notes,
    null as followup_close_notes,
    null as followup_outstanding,
    null as homeroom,
from abs_count as ac
left join
    {{ ref("int_deanslist__comm_log") }} as cl
    on ac.student_number = cl.student_school_id
    and ac.academic_year = cl.academic_year
    and {{ union_dataset_join_clause(left_alias="ac", right_alias="cl") }}
    and cl.reason like 'Chronic%'
