with
    calendar as (
        select
            schoolid,
            academic_year,
            week_start_monday,
            week_end_sunday,
            is_current_week_mon_sun,
        from {{ ref("int_powerschool__calendar_week") }}
        where academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    seat_tracker as (
        select
            staffing_model_id, entity, adp_location, valid_from, valid_to, is_staffed,
        from {{ ref("int_seat_tracker__snapshot") }}
        /* only active seats for the current academic year */
        where academic_year = {{ var("current_academic_year") }} and is_active
    ),

    locations as (
        select location_powerschool_school_id, location_name,
        from {{ ref("int_people__location_crosswalk") }}
    ),

    goals as (
        select
            entity,
            schoolid,
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
            layer,
            topline_indicator,
        from {{ ref("int_google_sheets__topline_aggregate_goals") }}
        where layer = 'Outstanding Teammates' and topline_indicator = 'Staffed'
    ),

    final as (
        select
            st.staffing_model_id,
            st.entity,

            l.location_powerschool_school_id as schoolid,
            l.location_name as school,

            cal.week_start_monday,
            cal.week_end_sunday,
            cal.academic_year,
            cal.is_current_week_mon_sun as is_current_week,

            if(st.is_staffed, 1, 0) as is_staffed,
        from seat_tracker as st
        inner join locations as l on st.adp_location = l.location_name
        inner join
            calendar as cal
            on l.location_powerschool_school_id = cal.schoolid
            and cal.week_start_monday between st.valid_from and st.valid_to
    )

select
    f.academic_year,
    f.entity as region,
    f.schoolid,
    f.school,
    f.week_start_monday,
    f.week_end_sunday,
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
inner join
    goals as g
    on f.entity = g.entity
    and f.schoolid = g.schoolid
    and g.org_level = 'school'
group by
    f.academic_year,
    f.entity,
    f.schoolid,
    f.school,
    f.week_start_monday,
    f.week_end_sunday,
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
    f.week_end_sunday,
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
inner join goals as g on f.entity = g.entity and g.org_level = 'region'
group by
    f.academic_year,
    f.entity,
    f.week_start_monday,
    f.week_end_sunday,
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
    f.week_end_sunday,
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
inner join goals as g on g.org_level = 'org'
group by
    f.academic_year,
    f.week_start_monday,
    f.week_end_sunday,
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
