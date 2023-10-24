with
    attendance_dash as (
        select
            mem.studentid,
            mem.calendardate,
            mem.membershipvalue,

            co.student_number,
            co.lastfirst,
            co.enroll_status,
            co.academic_year,
            co.region,
            co.school_level,
            co.reporting_schoolid as schoolid,
            co.school_abbreviation,
            co.grade_level,
            co.advisory_name as team,
            co.spedlep as iep_status,
            co.lep_status,
            co.is_504 as c_504_status,
            co.gender,
            co.ethnicity,
            co.is_self_contained,

            enr.cc_section_number as section_number,
            enr.teacher_lastfirst as teacher_name,

            att.att_code,

            dt.name as term,

            cast(mem.attendancevalue as numeric) as is_present,
            abs(mem.attendancevalue - 1) as is_absent,

            if(att.att_code in ('T', 'T10'), 0.0, 1.0) as pct_ontime_running,
            if(
                att.att_code in ('OS', 'OSS', 'OSSP', 'SHI'), 1.0, 0.0
            ) as is_oss_running,
            if(att.att_code in ('S', 'ISS'), 1.0, 0.0) as is_iss_running,
            if(
                att.att_code in ('OS', 'OSS', 'OSSP', 'S', 'ISS', 'SHI'), 1.0, 0.0
            ) as is_suspended_running,

            if(sp.studentid is not null, 1, 0) as is_counselingservices,

            if(sa.studentid is not null, 1, 0) as is_studentathlete,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on mem.studentid = co.studentid
            and mem.schoolid = co.schoolid
            and mem.calendardate between co.entrydate and co.exitdate
            and {{ union_dataset_join_clause(left_alias="mem", right_alias="co") }}
        left join
            {{ ref("base_powerschool__course_enrollments") }} as enr
            on co.studentid = enr.cc_studentid
            and co.academic_year = enr.cc_academic_year
            and co.schoolid = enr.cc_schoolid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="enr") }}
            and enr.cc_course_number = 'HR'
            and enr.rn_course_number_year = 1
        left join
            {{ ref("int_powerschool__ps_attendance_daily") }} as att
            on mem.studentid = att.studentid
            and mem.calendardate = att.att_date
            and {{ union_dataset_join_clause(left_alias="mem", right_alias="att") }}
        left join
            {{ ref("int_powerschool__spenrollments") }} as sp
            on mem.studentid = sp.studentid
            and mem.calendardate between sp.enter_date and sp.exit_date
            and {{ union_dataset_join_clause(left_alias="mem", right_alias="sp") }}
            and sp.specprog_name = 'Counseling Services'
        left join
            {{ ref("int_powerschool__spenrollments") }} as sa
            on mem.studentid = sa.studentid
            and mem.calendardate between sa.enter_date and sa.exit_date
            and {{ union_dataset_join_clause(left_alias="mem", right_alias="sa") }}
            and sa.specprog_name = 'Student Athlete'
        left join
            {{ ref("stg_reporting__terms") }} as dt
            on mem.schoolid = dt.school_id
            and mem.calendardate between dt.start_date and dt.end_date
            and dt.type = 'RT'
        where
            mem.attendancevalue is not null
            and mem.membershipvalue > 0
            and mem.calendardate between date(
                ({{ var("current_academic_year") }} - 1), 7, 1
            ) and current_date('{{ var("local_timezone") }}')
    )

select
    studentid,
    calendardate,
    membershipvalue,
    is_present,
    is_absent,
    student_number,
    lastfirst,
    enroll_status,
    academic_year,
    region,
    school_level,
    schoolid,
    school_abbreviation,
    grade_level,
    team,
    iep_status,
    lep_status,
    c_504_status,
    gender,
    ethnicity,
    is_self_contained,
    section_number,
    teacher_name,
    att_code,
    is_counselingservices,
    is_studentathlete,
    term,
    avg(is_present) over (
        partition by studentid, academic_year order by calendardate
    ) as ada_running,
    avg(pct_ontime_running) over (
        partition by student_number, academic_year order by calendardate
    ) as pct_ontime_running,
    max(is_oss_running) over (
        partition by student_number, academic_year order by calendardate
    ) as is_oss_running,
    max(is_iss_running) over (
        partition by student_number, academic_year order by calendardate
    ) as is_iss_running,
    max(is_suspended_running) over (
        partition by student_number, academic_year order by calendardate
    ) as is_suspended_running,
from attendance_dash
