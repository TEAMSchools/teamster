select
    academic_year,
    school_id,
    grade_level,
    state_assessment_code,
    illuminate_subject_area,
    grade_goal,
    school_goal,
    region_goal,
    organization_goal,
    grade_band_goal,
from {{ source("assessments", "src_assessments__academic_goals") }}
