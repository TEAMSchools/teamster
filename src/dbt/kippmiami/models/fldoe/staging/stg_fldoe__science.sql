with
    source as (
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
            `1_nature_of_science_performance`,
            `2_earth_and_space_science_performance`,
            `3_physical_science_performance`,
            `4_life_science_performance`,

            cast(_dagster_partition_grade_level_subject as int) as test_grade_level,
            cast(_dagster_partition_school_year_term as int) as academic_year,

            coalesce(
                grade_5_science_scale_score, grade_8_science_scale_score
            ) as scale_score,
            coalesce(
                grade_5_science_achievement_level, grade_8_science_achievement_level
            ) as achievement_level,

            coalesce(
                enrolled_grade.long_value, cast(enrolled_grade.double_value as int)
            ) as enrolled_grade,
        from {{ source("fldoe", "src_fldoe__science") }}
    ),

    with_achievement_level_int as (
        select
            *, safe_cast(right(achievement_level, 1) as int) as achievement_level_int,
        from source
    )

select *, if(achievement_level_int >= 3, true, false) as is_proficient,
from with_achievement_level_int
