with
    student_enrollments as (
        select * from {{ ref("int_extracts__student_enrollments") }}
    ),

    overall_filters as (
        select
            academic_year,
            student_number,
            max(nj_student_tier) as nj_overall_student_tier,
        from {{ ref("int_extracts__student_enrollments_subjects") }}
        where rn_year = 1 and academic_year >= {{ var("current_academic_year") - 1 }}
        group by academic_year, student_number
    ),

    -- attendance_dimensions as (
    -- select 
    -- student_number,
    -- calendar_date,
    -- if (fct_attendance.ada_running <=.90,1,0) as is_chronic_absenteeism,
    -- if (fct_attendance.pct_ontime_running) <=.795,1,0) as is_chronic_tardiness,
    -- if (fct_attendance.is_suspended > 2,1,0) as is_suspended_greater_than_2, {the
    -- max value for all records here is 1}
    -- from {{ ref("fct_attendance") }}
    -- ),
    final as (
        select
            student_enrollments.student_number,
            student_enrollments.entrydate as enrollment_start_date,
            student_enrollments.exitdate as enrollment_end_date,
            student_enrollments.academic_year,
            student_enrollments.schoolid as school_id,
            student_enrollments.iep_status,
            student_enrollments.lep_status,
            student_enrollments.status_504,
            student_enrollments.gender,
            student_enrollments.ethnicity,
            student_enrollments.gifted_and_talented,
            student_enrollments.enroll_status,
            student_enrollments.cohort_primary,
            student_enrollments.year_in_network,
            student_enrollments.is_enrolled_oct01,
            student_enrollments.is_retained_year,
            student_enrollments.boy_status,
            student_enrollments.entry_schoolid as entry_school_id,
            student_enrollments.advisor_lastfirst,
            student_enrollments.advisory_name,
            student_enrollments.is_self_contained,
            student_enrollments.is_out_of_district,
            student_enrollments.grade_level,
            student_enrollments.ms_attended,

            overall_filters.nj_overall_student_tier,

        from student_enrollments
        left join
            overall_filters
            on student_enrollments.academic_year = overall_filters.academic_year
            and student_enrollments.student_number = overall_filters.student_number
    )

select *
from final
