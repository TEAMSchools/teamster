with
    commlog as (
        select
            c._dbt_source_relation,
            c.student_school_id,
            c.reason as commlog_reason,
            c.response as commlog_notes,
            c.topic as commlog_topic,

            concat(u.first_name, ' ', u.last_name) as commlog_staff_name,

            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="call_date_time", start_month=7, year_source="start"
                )
            }} as academic_year,
        from {{ ref("stg_deanslist__comm_log") }} as c
        inner join
            {{ ref("stg_deanslist__users") }} as u
            on c.user_id = u.dl_user_id
            and {{ union_dataset_join_clause(left_alias="c", right_alias="u") }}
        where c.reason like 'Chronic%'
    ),

    abs_count as (
        select co.student_number, co.academic_year, count(att.att_date) as n_absences,
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
            and ac.att_code like 'A%'  -- change to exclude AE
        where co.rn_year = 1
        group by co.student_number, co.academic_year
    )

select
    co.student_number,
    co.lastfirst,
    co.region,
    co.reporting_schoolid,
    co.school_abbreviation,
    co.grade_level,
    co.advisor_lastfirst as team,

    ac.n_absences,

    cl.commlog_staff_name,
    cl.commlog_reason,
    cl.commlog_notes,
    cl.commlog_topic,

    null as followup_staff_name,
    null as followup_init_notes,
    null as followup_close_notes,
    null as followup_outstanding,
    null as homeroom,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    abs_count as ac
    on ac.student_number = co.student_number
    and ac.academic_year = co.academic_year
left join
    commlog as cl
    on co.student_number = cl.student_school_id
    and co.academic_year = cl.academic_year
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.enroll_status = 0
