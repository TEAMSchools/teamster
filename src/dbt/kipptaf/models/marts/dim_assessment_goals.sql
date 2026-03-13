select
    academic_year,
    school_id,
    state_assessment_code,
    illuminate_subject_area,
    grade_level as assessment_grade_level,
    grade_goal,
    school_goal,
    region_goal,
    organization_goal,
    grade_band_goal,
    assessment_band_goal,
    school_level,
    region,

    {{
        dbt_utils.generate_surrogate_key(
            ["academic_year", "school_id", "state_assessment_code"]
        )
    }} as assessment_goals_key,

from {{ ref("int_assessments__academic_goals") }}
