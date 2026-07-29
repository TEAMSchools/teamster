select
    academic_year,
    metric,
    aggregation_hash,
    org_level,
    region,
    schoolid,
    grade_band,
    goal_proportion,
    metric_rate,
    is_goal_met,
    progress_to_goal,
from {{ ref("int_gpa__goal_aggregations") }}
