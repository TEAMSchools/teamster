select
    id,
    syear,
    subject,
    school_id,
    student_id,
    grade_level,
    lunch_status,
    race,
    l25,
    gain,

    cast(has_ell as bool) as has_ell,
    cast(has_ese as bool) as has_ese,
    cast(has_504 as bool) as has_504,
    cast(low_percentile as bool) as is_low_percentile,
    cast(affects_school_grade as bool) as is_counted_in_school_grade,
    cast(above_grade_level as bool) as is_above_grade_level,
    cast(percentile as int64) as percentile,
    cast(_2025_pm3_achievement_level as int64) as pm3_2025_achievement_level,
    cast(_2025_pm3_percentile_rank as int64) as pm3_2025_percentile_rank,
    -- dlt rewrites the source's trailing underscore as `x`
    cast(
        _2025_pm3_scale_score_expanded_standard_scorex as int64
    ) as pm3_2025_scale_score,
from {{ source("focus", "florida_fast_report_students") }}
