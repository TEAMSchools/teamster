with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnj_iready", "stg_iready__diagnostic_results"),
                    source("kippmiami_iready", "stg_iready__diagnostic_results"),
                ]
            )
        }}
    ),

    with_code_location as (
        select
            student_id,
            `user_name`,
            academic_year,
            academic_year_int,
            school,
            student_grade,
            subject,
            duration_min,
            class_es,
            class_teacher_s,
            `grouping`,
            report_group_s,

            placement_3_level,
            diagnostic_gain,

            lexile_measure,
            lexile_range,

            percentile,
            quantile_measure,
            quantile_range,

            annual_stretch_growth_measure,
            annual_typical_growth_measure,
            percent_progress_to_annual_stretch_growth,
            percent_progress_to_annual_typical_growth,

            rush_flag,
            baseline_diagnostic_y_n,
            most_recent_diagnostic_y_n,
            reading_difficulty_indicator_y_n,

            overall_placement,
            overall_relative_placement,
            overall_scale_score,
            overall_relative_placement_int,
            overall_scale_score_plus_stretch_growth,
            overall_scale_score_plus_typical_growth,

            mid_on_grade_level_scale_score,

            algebra_and_algebraic_thinking_placement,
            algebra_and_algebraic_thinking_relative_placement,
            algebra_and_algebraic_thinking_scale_score,

            geometry_placement,
            geometry_relative_placement,
            geometry_scale_score,

            high_frequency_words_placement,
            high_frequency_words_relative_placement,
            high_frequency_words_scale_score,

            measurement_and_data_placement,
            measurement_and_data_relative_placement,
            measurement_and_data_scale_score,

            number_and_operations_placement,
            number_and_operations_relative_placement,
            number_and_operations_scale_score,

            phonics_placement,
            phonics_relative_placement,
            phonics_scale_score,

            phonological_awareness_placement,
            phonological_awareness_relative_placement,
            phonological_awareness_scale_score,

            reading_comprehension_informational_text_placement,
            reading_comprehension_informational_text_relative_placement,
            reading_comprehension_informational_text_scale_score,

            reading_comprehension_literature_placement,
            reading_comprehension_literature_relative_placement,
            reading_comprehension_literature_scale_score,

            reading_comprehension_overall_placement,
            reading_comprehension_overall_relative_placement,
            reading_comprehension_overall_scale_score,

            vocabulary_placement,
            vocabulary_relative_placement,
            vocabulary_scale_score,

            _dbt_source_relation,

            parse_date('%m/%d/%Y', start_date) as start_date,
            parse_date('%m/%d/%Y', completion_date) as completion_date,
            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as code_location,
        from union_relations
    )

select
    *,
    case
        code_location when 'kippnewark' then 'NJSLA' when 'kippmiami' then 'FL'
    end as state_assessment_type,
from with_code_location
