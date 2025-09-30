with
    calendar as (select *, from {{ ref("int_powerschool__calendar_week") }}),

    /* only active seats for the current academic year */
    seat_tracker as (
        select *,
        from {{ ref("int_seat_tracker__snapshot") }}
        where academic_year = {{ var("current_academic_year") }} and is_active
    ),

    locations as (select *, from {{ ref("int_people__location_crosswalk") }}),

    goals as (
        select *,
        from {{ ref("int_google_sheets__topline_aggregate_goals") }}
        where layer = 'Outstanding Teammates' and topline_indicator = 'Staffed'
    ),

    final as (
        select
            seat_tracker.staffing_model_id,
            seat_tracker.entity,

            locations.location_powerschool_school_id as schoolid,
            locations.location_name as school,

            calendar.week_start_monday,
            calendar.week_end_sunday,
            calendar.academic_year,
            calendar.is_current_week_mon_sun as is_current_week,

            if(seat_tracker.is_staffed, 1, 0) as is_staffed,
        from seat_tracker
        left join locations on seat_tracker.adp_location = locations.location_name
        inner join
            calendar
            on locations.location_powerschool_school_id = calendar.schoolid
            and calendar.week_start_monday
            between seat_tracker.valid_from and seat_tracker.valid_to
    )

select
    f.academic_year,
    f.entity as region,
    f.schoolid,
    f.school,
    f.week_start_monday,
    f.is_current_week,

    g.indicator_display,
    g.org_level,
    g.has_goal,
    g.goal_type,
    g.goal_direction,
    g.aggregation_data_type,
    g.aggregation_type,
    g.aggregation_hash,
    g.aggregation_display,
    g.goal,
    g.layer,
    g.topline_indicator as indicator,

    round(avg(f.is_staffed), 3) as metric_aggregate_value,
from final as f
inner join goals as g on f.entity = g.entity and f.schoolid = g.schoolid
group by
    f.academic_year,
    f.entity,
    f.schoolid,
    f.school,
    f.week_start_monday,
    f.is_current_week,
    g.indicator_display,
    g.org_level,
    g.has_goal,
    g.goal_type,
    g.goal_direction,
    g.aggregation_data_type,
    g.aggregation_type,
    g.aggregation_hash,
    g.aggregation_display,
    g.goal,
    g.layer,
    g.topline_indicator

union all

select
    f.academic_year,
    f.entity as region,

    null as schoolid,
    'All' as school,

    f.week_start_monday,
    f.is_current_week,

    g.indicator_display,
    g.org_level,
    g.has_goal,
    g.goal_type,
    g.goal_direction,
    g.aggregation_data_type,
    g.aggregation_type,
    g.aggregation_hash,
    g.aggregation_display,
    g.goal,
    g.layer,
    g.topline_indicator as indicator,

    round(avg(f.is_staffed), 3) as metric_aggregate_value,
from final as f
inner join goals as g on f.entity = g.entity
group by
    f.academic_year,
    f.entity,
    f.week_start_monday,
    f.is_current_week,
    g.indicator_display,
    g.org_level,
    g.has_goal,
    g.goal_type,
    g.goal_direction,
    g.aggregation_data_type,
    g.aggregation_type,
    g.aggregation_hash,
    g.aggregation_display,
    g.goal,
    g.layer,
    g.topline_indicator

union all

select
    f.academic_year,

    'All' as region,
    null as schoolid,
    'All' as school,

    f.week_start_monday,
    f.is_current_week,

    g.indicator_display,
    g.org_level,
    g.has_goal,
    g.goal_type,
    g.goal_direction,
    g.aggregation_data_type,
    g.aggregation_type,
    g.aggregation_hash,
    g.aggregation_display,
    g.goal,
    g.layer,
    g.topline_indicator as indicator,

    round(avg(f.is_staffed), 3) as metric_aggregate_value,
from final as f
cross join goals as g
group by
    f.academic_year,
    f.week_start_monday,
    f.is_current_week,
    g.indicator_display,
    g.org_level,
    g.has_goal,
    g.goal_type,
    g.goal_direction,
    g.aggregation_data_type,
    g.aggregation_type,
    g.aggregation_hash,
    g.aggregation_display,
    g.goal,
    g.layer,
    g.topline_indicator
