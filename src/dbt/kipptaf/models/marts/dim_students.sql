with
    student_enrollments as (
        select * from {{ ref("int_extracts__student_enrollments") }}
    ),

    student_tiers as (
        select
            academic_year,
            student_number,
            max(nj_student_tier) as nj_overall_student_tier,
        from {{ ref("int_extracts__student_enrollments_subjects") }}
        where rn_year = 1 and academic_year >= {{ var("current_academic_year") - 1 }}
        group by academic_year, student_number
    ),

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

            student_tiers.nj_overall_student_tier,

        from student_enrollments
        left join
            student_tiers
            on student_enrollments.academic_year = student_tiers.academic_year
            and student_enrollments.student_number = student_tiers.student_number
    )

select *
from final
