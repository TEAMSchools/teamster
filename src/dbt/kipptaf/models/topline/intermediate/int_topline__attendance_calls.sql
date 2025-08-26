with
    call_roster as (
        select
            co.student_number,
            co.student_name,
            co.academic_year,
            co.region,
            co.school_level,
            co.school,
            co.grade_level,
            co.team,
            co.iep_status,
            co.gender,
            co.is_retained_year,
            co.enroll_status,
            co.absences_unexcused_year,
            co.unweighted_ada,

            att.calendardate,
            att.att_code,

            com.educator_name as commlog_staff_name,
            com.reason as commlog_reason,
            com.response as commlog_notes,
            com.topic as commlog_topic,
            com.call_type as commlog_type,
            com.call_status as commlog_status,

            if(
                com.reason is not null and com.reason not like 'Att: Unknown%',
                true,
                false
            ) as is_successful,
            if(
                com.reason is not null and com.reason not like 'Att: Unknown%', 1, 0
            ) as is_successful_int,
            row_number() over (
                partition by co.studentid, att.calendardate
                order by com.call_date_time desc
            ) as rn_date,
        from {{ ref("int_extracts__student_enrollments") }} as co
        inner join
            {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as att
            on co.student_number = att.student_number
            and co.yearid = att.yearid
            and co.schoolid = att.schoolid
            and att.calendardate between co.entrydate and co.exitdate
            and att.is_absent = 1
            and att.membershipvalue = 1
        left join
            {{ ref("int_deanslist__comm_log") }} as com
            on co.student_number = com.student_school_id
            and co.academic_year = com.academic_year
            and att.calendardate = com.call_date
            and com.is_attendance_call
    )

select
    student_number,
    student_name,
    academic_year,
    region,
    school_level,
    school,
    grade_level,
    team,
    iep_status,
    gender,
    is_retained_year,
    enroll_status,
    absences_unexcused_year,
    unweighted_ada,
    calendardate,
    att_code,
    commlog_staff_name,
    commlog_reason,
    commlog_notes,
    commlog_topic,
    commlog_type,
    commlog_status,
    is_successful,
    is_successful_int,
from call_roster
where rn_date = 1
