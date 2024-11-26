with
    commlog as (
        select
            student_school_id as student_number,
            reason as commlog_reason,
            response as commlog_notes,
            topic as commlog_topic,
            _dbt_source_relation,

            date(call_date_time) as commlog_date,
            {{
                date_to_fiscal_year(
                    date_field="call_date_time", start_month=7, year_source="start"
                )
            }} as academic_year
        from {{ ref("stg_deanslist__comm_log") }} as c
        where c.reason like 'Att:%'
    )

select
    co.academic_year,
    co.region,
    co.school_abbreviation as school_name,
    co.grade_level,
    co.student_number,
    co.state_studentnumber,
    co.lastfirst as student_name,
    co.entrydate,
    co.exitdate,
    co.exitcode,
    co.exitcomment,

    st.streak_start_date as absence_start_date,
    st.streak_end_date as absence_end_date,
    st.streak_length_membership as absence_length_in_days,

    c.commlog_reason,
    c.commlog_notes,
    c.commlog_topic,
from {{ ref("int_powerschool__attendance_streak") }} as st
inner join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on st.studentid = co.studentid
    and st.yearid = co.yearid
    and {{ union_dataset_join_clause(left_alias="st", right_alias="co") }}
    and co.academic_year >= {{ var("current_academic_year") - 1 }}
left join
    commlog as c
    on co.student_number = c.student_number
    and c.commlog_date between st.streak_start_date and st.streak_end_date
    and {{ union_dataset_join_clause(left_alias="co", right_alias="c") }}
where st.att_code in ('A', 'AD', 'M') and st.streak_length_membership >= 10
