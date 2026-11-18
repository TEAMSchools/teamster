select
    {{
        assessment_goal_key(
            "academic_year",
            "school_id",
            "state_assessment_code",
            "grade_level",
            "illuminate_subject_area",
        )
    }} as assessment_goal_key,

    academic_year,
    state_assessment_code,
    grade_level,
    grade_goal,
    school_goal,
    region_goal,
    organization_goal,
    grade_band_goal,
    assessment_band_goal,

    illuminate_subject_area as academic_subject,
    qa_goal as quarterly_assessment_goal,
from {{ ref("int_assessments__academic_goals") }}
