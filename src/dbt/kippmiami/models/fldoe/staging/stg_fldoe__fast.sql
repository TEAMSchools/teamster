with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("fldoe", "src_fldoe__fast"),
                partition_by=(
                    "student_id, _dagster_partition_grade_level_subject, test_reason"
                ),
                order_by="enrolled_grade desc",
            )
        }}
    ),

    fast_data as (
        -- trunk-ignore(sqlfluff/ST06)
        select
            student_id,
            local_id,

            algebraic_reasoning_performance,
            data_analysis_and_probability_performance,
            fractional_reasoning_performance,
            geometric_reasoning_data_analysis_and_probability_performance,
            -- trunk-ignore(sqlfluff/LT05)
            geometric_reasoning_measurement_and_data_analysis_and_probability_performance,
            geometric_reasoning_performance,
            linear_relationships_data_analysis_and_functions_performance,
            number_sense_and_additive_reasoning_performance,
            number_sense_and_multiplicative_reasoning_performance,
            number_sense_and_operations_and_algebraic_reasoning_performance,
            number_sense_and_operations_and_probability_performance,
            number_sense_and_operations_performance,
            number_sense_and_operations_with_fractions_and_decimals_performance,
            number_sense_and_operations_with_whole_numbers_performance,
            proportional_reasoning_and_relationships_performance,
            reading_across_genres_vocabulary_performance,
            reading_informational_text_performance,
            reading_prose_and_poetry_performance,

            parse_date('%m/%d/%Y', date_taken) as date_taken,
            parse_date('%m/%d/%Y', test_completion_date) as test_completion_date,

            coalesce(
                fast_grade_3_ela_reading_achievement_level,
                grade_3_fast_ela_reading_achievement_level,
                fast_grade_4_ela_reading_achievement_level,
                grade_4_fast_ela_reading_achievement_level,
                fast_grade_5_ela_reading_achievement_level,
                grade_5_fast_ela_reading_achievement_level,
                fast_grade_6_ela_reading_achievement_level,
                grade_6_fast_ela_reading_achievement_level,
                fast_grade_7_ela_reading_achievement_level,
                grade_7_fast_ela_reading_achievement_level,
                fast_grade_8_ela_reading_achievement_level,
                grade_8_fast_ela_reading_achievement_level,
                fast_grade_3_mathematics_achievement_level,
                grade_3_fast_mathematics_achievement_level,
                fast_grade_4_mathematics_achievement_level,
                grade_4_fast_mathematics_achievement_level,
                fast_grade_5_mathematics_achievement_level,
                grade_5_fast_mathematics_achievement_level,
                fast_grade_6_mathematics_achievement_level,
                grade_6_fast_mathematics_achievement_level,
                fast_grade_7_mathematics_achievement_level,
                grade_7_fast_mathematics_achievement_level,
                fast_grade_8_mathematics_achievement_level,
                grade_8_fast_mathematics_achievement_level
            ) as achievement_level,

            coalesce(
                fast_grade_3_ela_reading_percentile_rank,
                fast_grade_3_mathematics_percentile_rank,
                fast_grade_4_ela_reading_percentile_rank,
                fast_grade_4_mathematics_percentile_rank,
                fast_grade_5_ela_reading_percentile_rank,
                fast_grade_5_mathematics_percentile_rank,
                fast_grade_6_ela_reading_percentile_rank,
                fast_grade_6_mathematics_percentile_rank,
                fast_grade_7_ela_reading_percentile_rank,
                fast_grade_7_mathematics_percentile_rank,
                fast_grade_8_ela_reading_percentile_rank,
                fast_grade_8_mathematics_percentile_rank,
                grade_3_fast_ela_reading_percentile_rank,
                grade_3_fast_mathematics_percentile_rank,
                grade_4_fast_ela_reading_percentile_rank,
                grade_4_fast_mathematics_percentile_rank,
                grade_5_fast_ela_reading_percentile_rank,
                grade_5_fast_mathematics_percentile_rank,
                grade_6_fast_ela_reading_percentile_rank,
                grade_6_fast_mathematics_percentile_rank,
                grade_7_fast_ela_reading_percentile_rank,
                grade_7_fast_mathematics_percentile_rank,
                grade_8_fast_ela_reading_percentile_rank,
                grade_8_fast_mathematics_percentile_rank
            ) as percentile_rank,

            coalesce(
                fast_grade_3_ela_reading_scale_score,
                fast_grade_3_mathematics_scale_score,
                fast_grade_4_ela_reading_scale_score,
                fast_grade_4_mathematics_scale_score,
                fast_grade_5_ela_reading_scale_score,
                fast_grade_5_mathematics_scale_score,
                fast_grade_6_ela_reading_scale_score,
                fast_grade_6_mathematics_scale_score,
                fast_grade_7_ela_reading_scale_score,
                fast_grade_7_mathematics_scale_score,
                fast_grade_8_ela_reading_scale_score,
                fast_grade_8_mathematics_scale_score,
                grade_3_fast_ela_reading_scale_score,
                grade_3_fast_mathematics_scale_score,
                grade_4_fast_ela_reading_scale_score,
                grade_4_fast_mathematics_scale_score,
                grade_5_fast_ela_reading_scale_score,
                grade_5_fast_mathematics_scale_score,
                grade_6_fast_ela_reading_scale_score,
                grade_6_fast_mathematics_scale_score,
                grade_7_fast_ela_reading_scale_score,
                grade_7_fast_mathematics_scale_score,
                grade_8_fast_ela_reading_scale_score,
                grade_8_fast_mathematics_scale_score
            ) as scale_score,

            regexp_extract(test_reason, r'\w+\d') as administration_window,

            regexp_extract(
                _dagster_partition_grade_level_subject, r'^Grade\dFAST(\w+)$'
            ) as assessment_subject,

            cast(
                regexp_extract(
                    _dagster_partition_grade_level_subject, r'^Grade(\d)FAST\w+$'
                ) as int
            ) as assessment_grade,

            cast(
                regexp_extract(_dagster_partition_school_year_term, r'^SY(\d+)') as int
            )
            + 1999 as academic_year,
        from deduplicate
    ),

    with_calcs as (
        select
            * except (percentile_rank, scale_score, assessment_subject),

            cast(scale_score as int) as scale_score,

            cast(regexp_extract(percentile_rank, r'\d+') as numeric) as percentile_rank,
            cast(
                regexp_extract(achievement_level, r'\d+') as int
            ) as achievement_level_int,

            if(
                assessment_subject = 'ELAReading',
                concat('ELA0', assessment_grade),
                concat('MAT0', assessment_grade)
            ) as test_code,

            if(
                assessment_subject = 'ELAReading',
                'English Language Arts',
                assessment_subject
            ) as assessment_subject,

            case
                administration_window
                when 'PM1'
                then 'Fall'
                when 'PM2'
                then 'Winter'
                when 'PM3'
                then 'Spring'
            end as season,

            case
                assessment_subject
                when 'ELAReading'
                then 'ELA'
                when 'Mathematics'
                then 'Math'
            end as discipline,
        from fast_data
        where
            achievement_level not in (
                'Insufficient to score',
                'Invalidated',
                'Insufficient to Score/No Response'
            )
    )

select
    *,

    case
        when achievement_level_int >= 3
        then true
        when achievement_level_int < 3
        then false
    end as is_proficient,

    lag(scale_score, 1) over (
        partition by student_id, academic_year, assessment_subject
        order by administration_window asc
    ) as scale_score_prev,
from with_calcs
