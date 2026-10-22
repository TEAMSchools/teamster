select
    id,
    syear,
    subject,
    school_id,
    student_id,
    grade_level,
    lunch_status,
    race,
    has_ell,
    has_ese,
    has_504,
    low_percentile,
    affects_school_grade,
    above_grade_level,
    l25,
    gain,

    cast(percentile as int64) as percentile,
    cast(_2025_pm3_achievement_level as int64) as pm3_2025_achievement_level,
    cast(_2025_pm3_percentile_rank as int64) as pm3_2025_percentile_rank,
    cast(
        _2025_pm3_scale_score_expanded_standard_score_ as int64
    ) as pm3_2025_scale_score,
from {{ source("focus", "florida_fast_report_students") }}
