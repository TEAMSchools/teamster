select
    metric_type,
    academic_year,
    schoolid,
    school,
    layer,
    indicator,
    discipline,
    term,
    term_end,
    is_current_week,
    indicator_display,
    org_level,
    has_goal,
    goal_type,
    goal_direction,
    aggregation_data_type,
    aggregation_type,
    aggregation_hash,
    aggregation_display,
    goal,
    metric_aggregate_value,
    metric_aggregate_value_numeric,
    metric_aggregate_value_integer,
    is_goal_met,
    goal_difference_percent,
    progress_to_goal_pct,

    case
        when region = 'TEAM Academy Charter School'
        then 'Newark'
        when region = 'KIPP Cooper Norcross Academy'
        then 'Camden'
        when region = 'KIPP Miami'
        then 'Miami'
        else region
    end as region,
from {{ ref("int_topline__dashboard_aggregations") }}
