from pydantic import BaseModel


class IReadyBaseModel(BaseModel):
    academic_year: str | None = None
    class_es: str | None = None
    class_teacher_s: str | None = None
    economically_disadvantaged: str | None = None
    english_language_learner: str | None = None
    enrolled: str | None = None
    first_name: str | None = None
    hispanic_or_latino: str | None = None
    last_name: str | None = None
    migrant: str | None = None
    race: str | None = None
    report_group_s: str | None = None
    school: str | None = None
    sex: str | None = None
    special_education: str | None = None
    student_grade: str | None = None
    student_id: str | None = None
    subject: str | None = None
    user_name: str | None = None


class DiagnosticInstruction(IReadyBaseModel):
    annual_stretch_growth_measure: str | None = None
    annual_typical_growth_measure: str | None = None
    diagnostic_completion_date_1: str | None = None
    diagnostic_completion_date_2: str | None = None
    diagnostic_completion_date_3: str | None = None
    diagnostic_completion_date_4: str | None = None
    diagnostic_completion_date_5: str | None = None
    diagnostic_completion_date_most_recent: str | None = None
    diagnostic_gain_note_negative_gains_zero: str | None = None
    diagnostic_grouping_most_recent: str | None = None
    diagnostic_language_1: str | None = None
    diagnostic_language_2: str | None = None
    diagnostic_language_3: str | None = None
    diagnostic_language_4: str | None = None
    diagnostic_language_5: str | None = None
    diagnostic_language_most_recent: str | None = None
    diagnostic_lexile_measure_most_recent: str | None = None
    diagnostic_lexile_range_most_recent: str | None = None
    diagnostic_overall_placement_1: str | None = None
    diagnostic_overall_placement_2: str | None = None
    diagnostic_overall_placement_3: str | None = None
    diagnostic_overall_placement_4: str | None = None
    diagnostic_overall_placement_5: str | None = None
    diagnostic_overall_placement_most_recent: str | None = None
    diagnostic_overall_relative_placement_1: str | None = None
    diagnostic_overall_relative_placement_2: str | None = None
    diagnostic_overall_relative_placement_3: str | None = None
    diagnostic_overall_relative_placement_4: str | None = None
    diagnostic_overall_relative_placement_5: str | None = None
    diagnostic_overall_relative_placement_most_recent: str | None = None
    diagnostic_overall_scale_score_1: str | None = None
    diagnostic_overall_scale_score_2: str | None = None
    diagnostic_overall_scale_score_3: str | None = None
    diagnostic_overall_scale_score_4: str | None = None
    diagnostic_overall_scale_score_5: str | None = None
    diagnostic_overall_scale_score_most_recent: str | None = None
    diagnostic_percentile_1: str | None = None
    diagnostic_percentile_2: str | None = None
    diagnostic_percentile_3: str | None = None
    diagnostic_percentile_4: str | None = None
    diagnostic_percentile_5: str | None = None
    diagnostic_percentile_most_recent: str | None = None
    diagnostic_quantile_measure_most_recent: str | None = None
    diagnostic_quantile_range_most_recent: str | None = None
    diagnostic_rush_flag_1: str | None = None
    diagnostic_rush_flag_2: str | None = None
    diagnostic_rush_flag_3: str | None = None
    diagnostic_rush_flag_4: str | None = None
    diagnostic_rush_flag_5: str | None = None
    diagnostic_rush_flag_most_recent: str | None = None
    diagnostic_start_date_1: str | None = None
    diagnostic_start_date_2: str | None = None
    diagnostic_start_date_3: str | None = None
    diagnostic_start_date_4: str | None = None
    diagnostic_start_date_5: str | None = None
    diagnostic_start_date_most_recent: str | None = None
    diagnostic_tier_1: str | None = None
    diagnostic_tier_2: str | None = None
    diagnostic_tier_3: str | None = None
    diagnostic_tier_4: str | None = None
    diagnostic_tier_5: str | None = None
    diagnostic_tier_most_recent: str | None = None
    diagnostic_time_on_task_min_1: str | None = None
    diagnostic_time_on_task_min_2: str | None = None
    diagnostic_time_on_task_min_3: str | None = None
    diagnostic_time_on_task_min_4: str | None = None
    diagnostic_time_on_task_min_5: str | None = None
    diagnostic_time_on_task_min_most_recent: str | None = None
    instruction_overall_lessons_completed: str | None = None
    instruction_overall_lessons_not_passed: str | None = None
    instruction_overall_lessons_passed: str | None = None
    instruction_overall_pass_rate_percent: str | None = None
    instruction_overall_pass_rate: str | None = None
    instruction_overall_time_on_task_min: str | None = None
    number_of_completed_diagnostics_during_the_time_frame: str | None = None


class DiagnosticResults(IReadyBaseModel):
    algebra_and_algebraic_thinking_placement: str | None = None
    algebra_and_algebraic_thinking_relative_placement: str | None = None
    algebra_and_algebraic_thinking_scale_score: str | None = None
    annual_stretch_growth_measure: str | None = None
    annual_typical_growth_measure: str | None = None
    baseline_diagnostic_y_n: str | None = None
    completion_date: str | None = None
    comprehension_informational_text_placement: str | None = None
    comprehension_informational_text_relative_placement: str | None = None
    comprehension_informational_text_scale_score: str | None = None
    comprehension_literature_placement: str | None = None
    comprehension_literature_relative_placement: str | None = None
    comprehension_literature_scale_score: str | None = None
    comprehension_overall_placement: str | None = None
    comprehension_overall_relative_placement: str | None = None
    comprehension_overall_scale_score: str | None = None
    diagnostic_gain: str | None = None
    diagnostic_language: str | None = None
    duration_min: str | None = None
    geometry_placement: str | None = None
    geometry_relative_placement: str | None = None
    geometry_scale_score: str | None = None
    grouping: str | None = None
    high_frequency_words_placement: str | None = None
    high_frequency_words_relative_placement: str | None = None
    high_frequency_words_scale_score: str | None = None
    lexile_measure: str | None = None
    lexile_range: str | None = None
    measurement_and_data_placement: str | None = None
    measurement_and_data_relative_placement: str | None = None
    measurement_and_data_scale_score: str | None = None
    mid_on_grade_level_scale_score: str | None = None
    most_recent_diagnostic_y_n: str | None = None
    most_recent_diagnostic_ytd_y_n: str | None = None
    number_and_operations_placement: str | None = None
    number_and_operations_relative_placement: str | None = None
    number_and_operations_scale_score: str | None = None
    overall_placement: str | None = None
    overall_relative_placement: str | None = None
    overall_scale_score: str | None = None
    percent_progress_to_annual_stretch_growth_percent: str | None = None
    percent_progress_to_annual_typical_growth_percent: str | None = None
    percentile: str | None = None
    phonics_placement: str | None = None
    phonics_relative_placement: str | None = None
    phonics_scale_score: str | None = None
    phonological_awareness_placement: str | None = None
    phonological_awareness_relative_placement: str | None = None
    phonological_awareness_scale_score: str | None = None
    quantile_measure: str | None = None
    quantile_range: str | None = None
    read_aloud: str | None = None
    reading_comprehension_informational_text_placement: str | None = None
    reading_comprehension_informational_text_relative_placement: str | None = None
    reading_comprehension_informational_text_scale_score: str | None = None
    reading_comprehension_literature_placement: str | None = None
    reading_comprehension_literature_relative_placement: str | None = None
    reading_comprehension_literature_scale_score: str | None = None
    reading_comprehension_overall_placement: str | None = None
    reading_comprehension_overall_relative_placement: str | None = None
    reading_comprehension_overall_scale_score: str | None = None
    reading_difficulty_indicator_y_n: str | None = None
    rush_flag: str | None = None
    start_date: str | None = None
    vocabulary_placement: str | None = None
    vocabulary_relative_placement: str | None = None
    vocabulary_scale_score: str | None = None


class InstructionalUsage(IReadyBaseModel):
    april_lessons_completed: str | None = None
    april_lessons_passed: str | None = None
    april_percent_lessons_passed: str | None = None
    april_total_time_on_task_min: str | None = None
    april_weekly_average_time_on_task_min: str | None = None
    august_lessons_completed: str | None = None
    august_lessons_passed: str | None = None
    august_percent_lessons_passed: str | None = None
    august_total_time_on_task_min: str | None = None
    august_weekly_average_time_on_task_min: str | None = None
    december_lessons_completed: str | None = None
    december_lessons_passed: str | None = None
    december_percent_lessons_passed: str | None = None
    december_total_time_on_task_min: str | None = None
    december_weekly_average_time_on_task_min: str | None = None
    february_lessons_completed: str | None = None
    february_lessons_passed: str | None = None
    february_percent_lessons_passed: str | None = None
    february_total_time_on_task_min: str | None = None
    february_weekly_average_time_on_task_min: str | None = None
    first_lesson_completion_date: str | None = None
    january_lessons_completed: str | None = None
    january_lessons_passed: str | None = None
    january_percent_lessons_passed: str | None = None
    january_total_time_on_task_min: str | None = None
    january_weekly_average_time_on_task_min: str | None = None
    july_lessons_completed: str | None = None
    july_lessons_passed: str | None = None
    july_percent_lessons_passed: str | None = None
    july_total_time_on_task_min: str | None = None
    july_weekly_average_time_on_task_min: str | None = None
    june_lessons_completed: str | None = None
    june_lessons_passed: str | None = None
    june_percent_lessons_passed: str | None = None
    june_total_time_on_task_min: str | None = None
    june_weekly_average_time_on_task_min: str | None = None
    last_week_end_date: str | None = None
    last_week_lessons_completed: str | None = None
    last_week_lessons_passed: str | None = None
    last_week_percent_lessons_passed: str | None = None
    last_week_start_date: str | None = None
    last_week_time_on_task_min: str | None = None
    march_lessons_completed: str | None = None
    march_lessons_passed: str | None = None
    march_percent_lessons_passed: str | None = None
    march_total_time_on_task_min: str | None = None
    march_weekly_average_time_on_task_min: str | None = None
    may_lessons_completed: str | None = None
    may_lessons_passed: str | None = None
    may_percent_lessons_passed: str | None = None
    may_total_time_on_task_min: str | None = None
    may_weekly_average_time_on_task_min: str | None = None
    most_recent_lesson_completion_date: str | None = None
    november_lessons_completed: str | None = None
    november_lessons_passed: str | None = None
    november_percent_lessons_passed: str | None = None
    november_total_time_on_task_min: str | None = None
    november_weekly_average_time_on_task_min: str | None = None
    october_lessons_completed: str | None = None
    october_lessons_passed: str | None = None
    october_percent_lessons_passed: str | None = None
    october_total_time_on_task_min: str | None = None
    october_weekly_average_time_on_task_min: str | None = None
    september_lessons_completed: str | None = None
    september_lessons_passed: str | None = None
    september_percent_lessons_passed: str | None = None
    september_total_time_on_task_min: str | None = None
    september_weekly_average_time_on_task_min: str | None = None
    year_to_date_algebra_and_algebraic_thinking_lessons_completed: str | None = None
    year_to_date_algebra_and_algebraic_thinking_lessons_passed: str | None = None
    year_to_date_algebra_and_algebraic_thinking_percent_lessons_passed: str | None = (
        None
    )
    year_to_date_algebra_and_algebraic_thinking_time_on_task_min: str | None = None
    year_to_date_comprehension_close_reading_lessons_completed: str | None = None
    year_to_date_comprehension_close_reading_lessons_passed: str | None = None
    year_to_date_comprehension_close_reading_percent_lessons_passed: str | None = None
    year_to_date_comprehension_close_reading_time_on_task_min: str | None = None
    year_to_date_comprehension_lessons_completed: str | None = None
    year_to_date_comprehension_lessons_passed: str | None = None
    year_to_date_comprehension_percent_lessons_passed: str | None = None
    year_to_date_comprehension_time_on_task_min: str | None = None
    year_to_date_geometry_lessons_completed: str | None = None
    year_to_date_geometry_lessons_passed: str | None = None
    year_to_date_geometry_percent_lessons_passed: str | None = None
    year_to_date_geometry_time_on_task_min: str | None = None
    year_to_date_high_frequency_words_lessons_completed: str | None = None
    year_to_date_high_frequency_words_lessons_passed: str | None = None
    year_to_date_high_frequency_words_percent_lessons_passed: str | None = None
    year_to_date_high_frequency_words_time_on_task_min: str | None = None
    year_to_date_measurement_and_data_lessons_completed: str | None = None
    year_to_date_measurement_and_data_lessons_passed: str | None = None
    year_to_date_measurement_and_data_percent_lessons_passed: str | None = None
    year_to_date_measurement_and_data_time_on_task_min: str | None = None
    year_to_date_number_and_operations_lessons_completed: str | None = None
    year_to_date_number_and_operations_lessons_passed: str | None = None
    year_to_date_number_and_operations_percent_lessons_passed: str | None = None
    year_to_date_number_and_operations_time_on_task_min: str | None = None
    year_to_date_overall_lessons_completed: str | None = None
    year_to_date_overall_lessons_passed: str | None = None
    year_to_date_overall_percent_lessons_passed: str | None = None
    year_to_date_overall_time_on_task_min: str | None = None
    year_to_date_phonics_lessons_completed: str | None = None
    year_to_date_phonics_lessons_passed: str | None = None
    year_to_date_phonics_percent_lessons_passed: str | None = None
    year_to_date_phonics_time_on_task_min: str | None = None
    year_to_date_phonological_awareness_lessons_completed: str | None = None
    year_to_date_phonological_awareness_lessons_passed: str | None = None
    year_to_date_phonological_awareness_percent_lessons_passed: str | None = None
    year_to_date_phonological_awareness_time_on_task_min: str | None = None
    year_to_date_vocabulary_lessons_completed: str | None = None
    year_to_date_vocabulary_lessons_passed: str | None = None
    year_to_date_vocabulary_percent_lessons_passed: str | None = None
    year_to_date_vocabulary_time_on_task_min: str | None = None


class PersonalizedInstruction(IReadyBaseModel):
    completion_date: str | None = None
    domain: str | None = None
    lesson_grade: str | None = None
    lesson_id: str | None = None
    lesson_language: str | None = None
    lesson_level: str | None = None
    lesson_name: str | None = None
    lesson_objective: str | None = None
    passed_or_not_passed: str | None = None
    score: str | None = None
    teacher_assigned_lesson: str | None = None
    total_time_on_lesson_min: str | None = None


class InstructionByLesson(IReadyBaseModel):
    completion_date: str | None = None
    foundational_skills_completed: str | None = None
    foundational_skills_successful: str | None = None
    language_comprehension_items_completed: str | None = None
    language_comprehension_items_correct: str | None = None
    lesson_language: str | None = None
    lesson_level: str | None = None
    lesson_result: str | None = None
    lesson_status: str | None = None
    lesson_time_on_task_min: str | None = None
    lesson_title: str | None = None
    lesson_topic: str | None = None
    lesson: str | None = None
    level: str | None = None
    percent_foundational_skills_successful: str | None = None
    percent_language_comprehension_items_correct: str | None = None
    percent_skills_successful: str | None = None
    skills_completed: str | None = None
    skills_successful: str | None = None
    teacher_assigned_lesson: str | None = None
    topic: str | None = None
