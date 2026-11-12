select
    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "academic_year", "score_source", "module_code"]
        )
    }} as assessment_score_latest_annual_key,

    {{ student_key("student_number") }} as student_key,
    {{ assessment_key("score_source", "module_code", "null", "null") }}
    as assessment_key,

    academic_year,
    test_date as test_date_key,
    scale_score,
    proficiency_level,
    proficiency_level_int,
    is_mastery,
    is_proficient,
from {{ ref("int_assessments__benchmark_scores") }}
where is_latest_in_year and response_type = 'overall'
