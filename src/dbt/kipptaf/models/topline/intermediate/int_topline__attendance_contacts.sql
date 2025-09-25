with
    comm_log as (
        select
            student_school_id,
            academic_year,
            call_date,
            educator_name as commlog_staff_name,
            reason as commlog_reason,
            response as commlog_notes,
            topic as commlog_topic,
            call_type as commlog_type,
            call_status as commlog_status,

            row_number() over (
                partition by student_school_id, call_date order by call_date_time desc
            ) as rn_date,
        from {{ ref("int_deanslist__comm_log") }}
        where is_attendance_call and call_status = 'Completed'
    )

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

    rt.name as term,

    com.educator_name as commlog_staff_name,
    com.reason as commlog_reason,
    com.response as commlog_notes,
    com.topic as commlog_topic,
    com.call_type as commlog_type,
    com.call_status as commlog_status,

    if(
        com.student_school_id is not null and com.reason not like 'Att: Unknown%',
        true,
        false
    ) as is_successful,

    if(
        com.student_school_id is not null and com.reason not like 'Att: Unknown%', 1, 0
    ) as is_successful_int,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
inner join
    {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as att
    on co.student_number = att.student_number
    and co.schoolid = att.schoolid
    and att.calendardate between co.week_start_monday and co.week_end_sunday
    and att.is_absent = 1
    and att.is_suspended = 0
    and att.membershipvalue = 1
left join
    {{ ref("stg_reporting__terms") }} as rt
    on att.schoolid = rt.school_id
    and att.calendardate between rt.start_date and rt.end_date
    and rt.type = 'RT'
left join
    comm_log as com
    on co.student_number = com.student_school_id
    and att.calendardate = com.call_date
    and com.rn_date = 1
