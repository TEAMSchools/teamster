with
    overall_filters as (
        select
            academic_year,
            student_number,

            max(nj_student_tier) as nj_overall_student_tier,
        from {{ ref("int_extracts__student_enrollments_subjects") }}
        where rn_year = 1 and academic_year >= {{ var("current_academic_year") - 1 }}
        group by academic_year, student_number
    )

select
    se.student_number,
    se.entrydate as enrollment_start_date,
    se.exitdate as enrollment_end_date,
    se.academic_year,
    se.schoolid as school_id,
    se.iep_status,
    se.lep_status,
    se.status_504,
    se.gender,
    se.ethnicity,
    se.gifted_and_talented,
    se.enroll_status,
    se.cohort_primary,
    se.year_in_network,
    se.is_enrolled_oct01,
    se.is_retained_year,
    se.boy_status,
    se.entry_schoolid as entry_school_id,
    se.advisor_lastfirst,
    se.advisory_name,
    se.is_self_contained,
    se.is_out_of_district,
    se.grade_level,
    se.ms_attended,

    ov.nj_overall_student_tier,

    {{ dbt_utils.generate_surrogate_key(["se.student_number", "se.entrydate"]) }}
    as student_enrollments_key,
from {{ ref("int_extracts__student_enrollments") }} as se
left join
    overall_filters as ov
    on se.academic_year = ov.academic_year
    and se.student_number = ov.student_number
where se.entrydate is not null
