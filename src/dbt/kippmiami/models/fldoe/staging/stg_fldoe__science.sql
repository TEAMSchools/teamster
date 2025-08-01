with
    science as (
        select
            student_id,
            local_id,
            student_name,
            student_dob,
            ethnicity,
            english_language_learner_ell_status,
            gender_k_12,
            gender_postsecondary_only,
            primary_exceptionality,
            section_504,
            enrolled_district,
            enrolled_school,
            date_taken,
            test_completion_date,
            test_oppnumber,
            test_reason,
            testing_location,
            field_1_nature_of_science_performance as nature_of_science_performance,
            field_2_earth_and_space_science_performance
            as earth_and_space_science_performance,
            field_3_physical_science_performance as physical_science_performance,
            field_4_life_science_performance as life_science_performance,

            'PM3' as administration_window,
            'Spring' as season,
            'Science' as discipline,
            'Science' as assessment_subject,

            cast(_dagster_partition_grade_level_subject as int) as assessment_grade,
            cast(_dagster_partition_school_year_term as int) as academic_year,
            cast(enrolled_grade as int) as enrolled_grade,

            cast(
                coalesce(
                    grade_5_science_scale_score, grade_8_science_scale_score
                ) as int
            ) as scale_score,

            coalesce(
                grade_5_science_achievement_level, grade_8_science_achievement_level
            ) as achievement_level,
        from {{ source("fldoe", "src_fldoe__science") }}
    ),

    with_achievement_level_int as (
        select *, cast(right(achievement_level, 1) as int) as achievement_level_int,
        from science
    )

select
    *,

    if(achievement_level_int >= 3, true, false) as is_proficient,

    case assessment_grade when 5 then 'SCI05' when 8 then 'SCI08' end as test_code,
from with_achievement_level_int
