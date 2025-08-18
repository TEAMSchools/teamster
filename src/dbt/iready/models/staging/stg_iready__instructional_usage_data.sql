select
    _dagster_partition_subject,
    academic_year,
    class_es,
    class_teacher_s,
    economically_disadvantaged,
    english_language_learner,
    enrolled,
    first_name,
    hispanic_or_latino,
    last_name,
    migrant,
    race,
    report_group_s,
    school,
    sex,
    special_education,
    student_grade,
    `subject`,
    user_name,

    cast(april_lessons_passed as numeric) as april_lessons_passed,
    cast(april_percent_lessons_passed as numeric) as april_percent_lessons_passed,
    cast(august_lessons_passed as numeric) as august_lessons_passed,
    cast(august_percent_lessons_passed as numeric) as august_percent_lessons_passed,
    cast(december_lessons_passed as numeric) as december_lessons_passed,
    cast(december_percent_lessons_passed as numeric) as december_percent_lessons_passed,
    cast(february_lessons_passed as numeric) as february_lessons_passed,
    cast(february_percent_lessons_passed as numeric) as february_percent_lessons_passed,
    cast(january_lessons_passed as numeric) as january_lessons_passed,
    cast(january_percent_lessons_passed as numeric) as january_percent_lessons_passed,
    cast(july_lessons_passed as numeric) as july_lessons_passed,
    cast(july_percent_lessons_passed as numeric) as july_percent_lessons_passed,
    cast(june_lessons_passed as numeric) as june_lessons_passed,
    cast(june_percent_lessons_passed as numeric) as june_percent_lessons_passed,
    cast(last_week_lessons_passed as numeric) as last_week_lessons_passed,
    cast(
        last_week_percent_lessons_passed as numeric
    ) as last_week_percent_lessons_passed,
    cast(march_lessons_passed as numeric) as march_lessons_passed,
    cast(march_percent_lessons_passed as numeric) as march_percent_lessons_passed,
    cast(may_lessons_passed as numeric) as may_lessons_passed,
    cast(may_percent_lessons_passed as numeric) as may_percent_lessons_passed,
    cast(november_lessons_passed as numeric) as november_lessons_passed,
    cast(november_percent_lessons_passed as numeric) as november_percent_lessons_passed,
    cast(october_lessons_passed as numeric) as october_lessons_passed,
    cast(october_percent_lessons_passed as numeric) as october_percent_lessons_passed,
    cast(september_lessons_passed as numeric) as september_lessons_passed,
    cast(
        september_percent_lessons_passed as numeric
    ) as september_percent_lessons_passed,
    cast(
        year_to_date_algebra_and_algebraic_thinking_lessons_passed as numeric
    ) as year_to_date_algebra_and_algebraic_thinking_lessons_passed,
    cast(
        year_to_date_algebra_and_algebraic_thinking_percent_lessons_passed as numeric
    ) as year_to_date_algebra_and_algebraic_thinking_percent_lessons_passed,
    cast(
        year_to_date_comprehension_close_reading_lessons_passed as numeric
    ) as year_to_date_comprehension_close_reading_lessons_passed,
    cast(
        year_to_date_comprehension_close_reading_percent_lessons_passed as numeric
    ) as year_to_date_comprehension_close_reading_percent_lessons_passed,
    cast(
        year_to_date_comprehension_lessons_passed as numeric
    ) as year_to_date_comprehension_lessons_passed,
    cast(
        year_to_date_comprehension_percent_lessons_passed as numeric
    ) as year_to_date_comprehension_percent_lessons_passed,
    cast(
        year_to_date_geometry_lessons_passed as numeric
    ) as year_to_date_geometry_lessons_passed,
    cast(
        year_to_date_geometry_percent_lessons_passed as numeric
    ) as year_to_date_geometry_percent_lessons_passed,
    cast(
        year_to_date_high_frequency_words_lessons_passed as numeric
    ) as year_to_date_high_frequency_words_lessons_passed,
    cast(
        year_to_date_high_frequency_words_percent_lessons_passed as numeric
    ) as year_to_date_high_frequency_words_percent_lessons_passed,
    cast(
        year_to_date_measurement_and_data_lessons_passed as numeric
    ) as year_to_date_measurement_and_data_lessons_passed,
    cast(
        year_to_date_measurement_and_data_percent_lessons_passed as numeric
    ) as year_to_date_measurement_and_data_percent_lessons_passed,
    cast(
        year_to_date_number_and_operations_lessons_passed as numeric
    ) as year_to_date_number_and_operations_lessons_passed,
    cast(
        year_to_date_number_and_operations_percent_lessons_passed as numeric
    ) as year_to_date_number_and_operations_percent_lessons_passed,
    cast(
        year_to_date_overall_lessons_passed as numeric
    ) as year_to_date_overall_lessons_passed,
    cast(
        year_to_date_overall_percent_lessons_passed as numeric
    ) as year_to_date_overall_percent_lessons_passed,
    cast(
        year_to_date_phonics_lessons_passed as numeric
    ) as year_to_date_phonics_lessons_passed,
    cast(
        year_to_date_phonics_percent_lessons_passed as numeric
    ) as year_to_date_phonics_percent_lessons_passed,
    cast(
        year_to_date_phonological_awareness_lessons_passed as numeric
    ) as year_to_date_phonological_awareness_lessons_passed,
    cast(
        year_to_date_phonological_awareness_percent_lessons_passed as numeric
    ) as year_to_date_phonological_awareness_percent_lessons_passed,
    cast(
        year_to_date_vocabulary_lessons_passed as numeric
    ) as year_to_date_vocabulary_lessons_passed,
    cast(
        year_to_date_vocabulary_percent_lessons_passed as numeric
    ) as year_to_date_vocabulary_percent_lessons_passed,
    cast(_dagster_partition_academic_year as int) as _dagster_partition_academic_year,
    cast(april_lessons_completed as int) as april_lessons_completed,
    cast(april_total_time_on_task_min as int) as april_total_time_on_task_min,
    cast(
        april_weekly_average_time_on_task_min as int
    ) as april_weekly_average_time_on_task_min,
    cast(august_lessons_completed as int) as august_lessons_completed,
    cast(august_total_time_on_task_min as int) as august_total_time_on_task_min,
    cast(
        august_weekly_average_time_on_task_min as int
    ) as august_weekly_average_time_on_task_min,
    cast(december_lessons_completed as int) as december_lessons_completed,
    cast(december_total_time_on_task_min as int) as december_total_time_on_task_min,
    cast(
        december_weekly_average_time_on_task_min as int
    ) as december_weekly_average_time_on_task_min,
    cast(february_lessons_completed as int) as february_lessons_completed,
    cast(february_total_time_on_task_min as int) as february_total_time_on_task_min,
    cast(
        february_weekly_average_time_on_task_min as int
    ) as february_weekly_average_time_on_task_min,
    cast(january_lessons_completed as int) as january_lessons_completed,
    cast(january_total_time_on_task_min as int) as january_total_time_on_task_min,
    cast(
        january_weekly_average_time_on_task_min as int
    ) as january_weekly_average_time_on_task_min,
    cast(july_lessons_completed as int) as july_lessons_completed,
    cast(july_total_time_on_task_min as int) as july_total_time_on_task_min,
    cast(
        july_weekly_average_time_on_task_min as int
    ) as july_weekly_average_time_on_task_min,
    cast(june_lessons_completed as int) as june_lessons_completed,
    cast(june_total_time_on_task_min as int) as june_total_time_on_task_min,
    cast(
        june_weekly_average_time_on_task_min as int
    ) as june_weekly_average_time_on_task_min,
    cast(last_week_lessons_completed as int) as last_week_lessons_completed,
    cast(last_week_time_on_task_min as int) as last_week_time_on_task_min,
    cast(march_lessons_completed as int) as march_lessons_completed,
    cast(march_total_time_on_task_min as int) as march_total_time_on_task_min,
    cast(
        march_weekly_average_time_on_task_min as int
    ) as march_weekly_average_time_on_task_min,
    cast(may_lessons_completed as int) as may_lessons_completed,
    cast(may_total_time_on_task_min as int) as may_total_time_on_task_min,
    cast(
        may_weekly_average_time_on_task_min as int
    ) as may_weekly_average_time_on_task_min,
    cast(november_lessons_completed as int) as november_lessons_completed,
    cast(november_total_time_on_task_min as int) as november_total_time_on_task_min,
    cast(
        november_weekly_average_time_on_task_min as int
    ) as november_weekly_average_time_on_task_min,
    cast(october_lessons_completed as int) as october_lessons_completed,
    cast(october_total_time_on_task_min as int) as october_total_time_on_task_min,
    cast(
        october_weekly_average_time_on_task_min as int
    ) as october_weekly_average_time_on_task_min,
    cast(september_lessons_completed as int) as september_lessons_completed,
    cast(september_total_time_on_task_min as int) as september_total_time_on_task_min,
    cast(
        september_weekly_average_time_on_task_min as int
    ) as september_weekly_average_time_on_task_min,
    cast(student_id as int) as student_id,
    cast(
        year_to_date_algebra_and_algebraic_thinking_lessons_completed as int
    ) as year_to_date_algebra_and_algebraic_thinking_lessons_completed,
    cast(
        year_to_date_algebra_and_algebraic_thinking_time_on_task_min as int
    ) as year_to_date_algebra_and_algebraic_thinking_time_on_task_min,
    cast(
        year_to_date_comprehension_close_reading_lessons_completed as int
    ) as year_to_date_comprehension_close_reading_lessons_completed,
    cast(
        year_to_date_comprehension_close_reading_time_on_task_min as int
    ) as year_to_date_comprehension_close_reading_time_on_task_min,
    cast(
        year_to_date_comprehension_lessons_completed as int
    ) as year_to_date_comprehension_lessons_completed,
    cast(
        year_to_date_comprehension_time_on_task_min as int
    ) as year_to_date_comprehension_time_on_task_min,
    cast(
        year_to_date_geometry_lessons_completed as int
    ) as year_to_date_geometry_lessons_completed,
    cast(
        year_to_date_geometry_time_on_task_min as int
    ) as year_to_date_geometry_time_on_task_min,
    cast(
        year_to_date_high_frequency_words_lessons_completed as int
    ) as year_to_date_high_frequency_words_lessons_completed,
    cast(
        year_to_date_high_frequency_words_time_on_task_min as int
    ) as year_to_date_high_frequency_words_time_on_task_min,
    cast(
        year_to_date_measurement_and_data_lessons_completed as int
    ) as year_to_date_measurement_and_data_lessons_completed,
    cast(
        year_to_date_measurement_and_data_time_on_task_min as int
    ) as year_to_date_measurement_and_data_time_on_task_min,
    cast(
        year_to_date_number_and_operations_lessons_completed as int
    ) as year_to_date_number_and_operations_lessons_completed,
    cast(
        year_to_date_number_and_operations_time_on_task_min as int
    ) as year_to_date_number_and_operations_time_on_task_min,
    cast(
        year_to_date_overall_lessons_completed as int
    ) as year_to_date_overall_lessons_completed,
    cast(
        year_to_date_overall_time_on_task_min as int
    ) as year_to_date_overall_time_on_task_min,
    cast(
        year_to_date_phonics_lessons_completed as int
    ) as year_to_date_phonics_lessons_completed,
    cast(
        year_to_date_phonics_time_on_task_min as int
    ) as year_to_date_phonics_time_on_task_min,
    cast(
        year_to_date_phonological_awareness_lessons_completed as int
    ) as year_to_date_phonological_awareness_lessons_completed,
    cast(
        year_to_date_phonological_awareness_time_on_task_min as int
    ) as year_to_date_phonological_awareness_time_on_task_min,
    cast(
        year_to_date_vocabulary_lessons_completed as int
    ) as year_to_date_vocabulary_lessons_completed,
    cast(
        year_to_date_vocabulary_time_on_task_min as int
    ) as year_to_date_vocabulary_time_on_task_min,

    safe_cast(left(academic_year, 4) as int) as academic_year_int,

    parse_date('%m/%d/%Y', last_week_start_date) as last_week_start_date,
    parse_date('%m/%d/%Y', last_week_end_date) as last_week_end_date,
    parse_date(
        '%m/%d/%Y', first_lesson_completion_date
    ) as first_lesson_completion_date,
    parse_date(
        '%m/%d/%Y', most_recent_lesson_completion_date
    ) as most_recent_lesson_completion_date,
from {{ source("iready", "src_iready__instructional_usage_data") }}
