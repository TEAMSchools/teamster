with
    ms_grad_sub as (
        select
            _dbt_source_relation,
            student_number,
            school_abbreviation as ms_attended,
            row_number() over (
                partition by student_number order by exitdate desc
            ) as rn,
        from {{ ref("base_powerschool__student_enrollments") }}
        where school_level = 'MS'
    ),

    overall_filters as (
        select distinct
            academic_year,
            student_number,
            max(
                case
                    nj_student_tier when 'Bucket 1' then 1 when 'Bucket 2' then 2 else 0
                end
            ) over (partition by academic_year, student_number)
            as nj_overall_student_tier,
        from {{ ref("int_extracts__student_enrollments_subjects") }}
        where academic_year >= {{ var("current_academic_year") - 1 }}

    ),

    attendance_dash as (
        select
            ad.studentid,
            ad.calendardate,
            ad.membershipvalue,
            ad.att_code,
            ad.is_present,
            ad.is_present_weighted,
            ad.is_absent,
            ad.is_tardy,
            ad.is_ontime as pct_ontime_running,
            ad.is_oss as is_oss_running,
            ad.is_iss as is_iss_running,
            ad.is_suspended as is_suspended_running,
            ad.quarter as term,

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
            co.year_in_network,

            enr.cc_section_number as section_number,
            enr.teacher_lastfirst as teacher_name,

            f.nj_overall_student_tier,

            ms.ms_attended,

            if(sp.studentid is not null, 1, 0) as is_counselingservices,
            if(sa.studentid is not null, 1, 0) as is_studentathlete,
        from {{ ref("int_powerschool__ada_detail") }} as ad
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on ad.studentid = co.studentid
            and ad.schoolid = co.schoolid
            and ad.calendardate between co.entrydate and co.exitdate
            and {{ union_dataset_join_clause(left_alias="ad", right_alias="co") }}
        left join
            {{ ref("base_powerschool__course_enrollments") }} as enr
            on co.studentid = enr.cc_studentid
            and co.academic_year = enr.cc_academic_year
            and co.schoolid = enr.cc_schoolid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="enr") }}
            and enr.cc_course_number = 'HR'
            and enr.rn_course_number_year = 1
        left join
            {{ ref("int_powerschool__spenrollments") }} as sp
            on ad.studentid = sp.studentid
            and ad.calendardate between sp.enter_date and sp.exit_date
            and {{ union_dataset_join_clause(left_alias="ad", right_alias="sp") }}
            and sp.specprog_name = 'Counseling Services'
        left join
            {{ ref("int_powerschool__spenrollments") }} as sa
            on ad.studentid = sa.studentid
            and ad.calendardate between sa.enter_date and sa.exit_date
            and {{ union_dataset_join_clause(left_alias="ad", right_alias="sa") }}
            and sa.specprog_name = 'Student Athlete'
        left join
            overall_filters as f
            on co.academic_year = f.academic_year
            and co.student_number = f.student_number
        left join
            ms_grad_sub as ms
            on co.student_number = ms.student_number
            and {{ union_dataset_join_clause(left_alias="co", right_alias="ms") }}
            and ms.rn = 1
        where
            ad.calendardate between date(
                ({{ var("current_academic_year") - 1 }}), 7, 1
            ) and current_date('{{ var("local_timezone") }}')
    )

select
    studentid,
    calendardate,
    membershipvalue,
    is_present,
    is_absent,
    is_present_weighted as is_present_hs_alt,
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
    ms_attended,
    if(
        nj_overall_student_tier = 0,
        'Unbucketed',
        concat('Bucket ', nj_overall_student_tier)
    ) as nj_overall_student_tier,
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
