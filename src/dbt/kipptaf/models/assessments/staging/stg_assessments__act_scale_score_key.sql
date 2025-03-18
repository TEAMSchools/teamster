select
    assessment_id,
    academic_year,
    test_type,
    administration_round,
    `subject`,
    grade_level,
    raw_score_low,
    raw_score_high,
    scale_score,
from {{ source("assessments", "src_assessments__act_scale_score_key") }}
