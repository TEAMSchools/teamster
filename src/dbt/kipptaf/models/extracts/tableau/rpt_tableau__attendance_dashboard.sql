with
    overall_filters as (
        select
            academic_year,
            student_number,

            max(nj_student_tier) as nj_overall_student_tier,
        from {{ ref("int_extracts__student_enrollments_subjects") }}
        where academic_year >= {{ var("current_academic_year") - 1 }}
        group by academic_year, student_number

    ),

    attendance_dash as (
        select
            ad.studentid,
            ad.calendardate,
            ad.membershipvalue,
            ad.att_code,
            ad.attendancevalue,
            ad.is_present_weighted,
            ad.is_absent,
            ad.is_tardy,
            ad.is_ontime,
            ad.is_oss,
            ad.is_iss,
            ad.is_suspended,
            ad.term,

            co.student_number,
            co.student_name,
            co.enroll_status,
            co.academic_year,
            co.region,
            co.school_level,
            co.reporting_schoolid,
            co.school,
            co.grade_level,
            co.advisory_name,
            co.advisory_section_number,
            co.advisor_lastfirst,
            co.spedlep,
            co.lep_status,
            co.is_504,
            co.gender,
            co.ethnicity,
            co.is_self_contained,
            co.year_in_network,
            co.ms_attended,

            coalesce(co.is_counseling_services, 0) as is_counseling_services,
            coalesce(co.is_student_athlete, 0) as is_student_athlete,

            coalesce(
                f.nj_overall_student_tier, 'Unbucketed'
            ) as nj_overall_student_tier,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as ad
        inner join
            {{ ref("int_extracts__student_enrollments") }} as co
            on ad.studentid = co.studentid
            and ad.schoolid = co.schoolid
            and ad.calendardate between co.entrydate and co.exitdate
            and {{ union_dataset_join_clause(left_alias="ad", right_alias="co") }}
        left join
            overall_filters as f
            on co.academic_year = f.academic_year
            and co.student_number = f.student_number
        where
            ad.membershipvalue = 1
            and ad.attendancevalue is not null
            and ad.calendardate between date(
                ({{ var("current_academic_year") - 1 }}), 7, 1
            ) and current_date('{{ var("local_timezone") }}')
    )

select
    studentid,
    calendardate,
    membershipvalue,
    attendancevalue as is_present,
    is_absent,
    is_present_weighted as is_present_hs_alt,
    student_number,
    student_name as lastfirst,
    enroll_status,
    academic_year,
    region,
    school_level,
    reporting_schoolid as schoolid,
    school as school_abbreviation,
    grade_level,
    team,
    spedlep as iep_status,
    lep_status,
    is_504 as c_504_status,
    gender,
    ethnicity,
    is_self_contained,
    advisory_name as team,
    advisory_section_number as section_number,
    advisor_lastfirst as teacher_name,
    att_code,
    is_counseling_services as is_counselingservices,
    is_student_athlete as is_studentathlete,
    term,
    ms_attended,
    nj_overall_student_tier,

    avg(attendancevalue) over (
        partition by studentid, academic_year order by calendardate
    ) as ada_running,
    avg(is_ontime) over (
        partition by student_number, academic_year order by calendardate
    ) as pct_ontime_running,

    max(is_oss) over (
        partition by student_number, academic_year order by calendardate
    ) as is_oss_running,
    max(is_iss) over (
        partition by student_number, academic_year order by calendardate
    ) as is_iss_running,
    max(is_suspended) over (
        partition by student_number, academic_year order by calendardate
    ) as is_suspended_running,

    if(
        mod(
            sum(if(att_code in ('T', 'T10'), 1, 0)) over (
                partition by student_number, academic_year order by calendardate asc
            ),
            3
        )
        = 0
        and sum(if(att_code in ('T', 'T10'), 1, 0)) over (
            partition by student_number, academic_year order by calendardate asc
        )
        != 0
        and att_code in ('T', 'T10'),
        true,
        false
    ) as is_present_flip,
from attendance_dash
