select
    st.streak_start_date as absence_start_date,
    st.streak_end_date as absence_end_date,
    st.streak_length_membership as absence_length_in_days,

    co.student_number,
    co.state_studentnumber,
    co.student_name,
    co.academic_year,
    co.region,
    co.school as school_name,
    co.grade_level,
    co.entrydate,
    co.exitdate,
    co.exitcode,
    co.exitcomment,

    c.reason as commlog_reason,
    c.response as commlog_notes,
    c.topic as commlog_topic,
from {{ ref("int_powerschool__attendance_streak") }} as st
inner join
    {{ ref("int_extracts__student_enrollments") }} as co
    on st.studentid = co.studentid
    and st.yearid = co.yearid
    and st._dbt_source_project = co._dbt_source_project
left join
    {{ ref("int_deanslist__comm_log") }} as c
    on co.student_number = c.student_school_id
    and c.call_date between st.streak_start_date and st.streak_end_date
    and co._dbt_source_project = c._dbt_source_project
    and c.reason like 'Att:%'
where
    st.att_code in ('A', 'AD', 'M')
    and st.streak_length_membership >= 10
    and st.yearid >= {{ var("current_academic_year") - 1991 }}
