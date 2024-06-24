select
    _dagster_partition_academic_year as academic_year, 
    _dagster_partition_term as code,
    employee_number,
    etr_score,
    so_score,
    form_long_name as rubric_name,
    form_type as observation_type_abbreviation,
    glows,
    grows,
    measurement_name,
    observation_id,
    observer_employee_number,
    overall_score as observation_score,
    rn_submission,
    row_score_value as row_score,
    rubric_id,
    score_measurement_id,
    score_measurement_shortname as strand_description,
    score_measurement_type as strand_name,
    teacher_id,
    text_box,
    safe_cast(observed_at as date) as observed_at,

from
    {{
        source(
            "performance_management",
            "src_performance_management__observation_details",
        )
    }}
