select
    db.metric_type,
    db.academic_year,
    db.schoolid,
    db.school,
    db.layer,
    db.indicator,
    db.discipline,
    db.term,
    db.term_end,
    db.is_current_week,
    db.period_type,
    db.period_label,
    db.is_current_period,
    db.is_most_recent_complete_period,
    db.indicator_display,
    db.org_level,
    db.has_goal,
    db.goal_type,
    db.goal_direction,
    db.aggregation_data_type,
    db.aggregation_type,
    db.aggregation_hash,
    db.aggregation_display,
    db.goal,
    db.metric_aggregate_value,
    db.metric_aggregate_value_numeric,
    db.metric_aggregate_value_integer,
    db.is_goal_met,
    db.goal_difference_percent,
    db.progress_to_goal_pct,
    db.goal_difference,
    db.goal_difference_numeric,
    db.goal_difference_integer,
    db.metric_numerator,
    db.metric_denominator,
    db.region,

    lc.mdso_preferred_name_lastfirst as mdso_name,
    lc.head_of_school_preferred_name_lastfirst as hos_name,

    if(
        db.period_type = 'week' and db.is_most_recent_complete_period, true, false
    ) as is_most_recent_complete_week,
from {{ ref("int_topline__dashboard_aggregations") }} as db
left join
    {{ ref("int_people__leadership_crosswalk") }} as lc
    on db.schoolid = lc.home_work_location_powerschool_school_id
