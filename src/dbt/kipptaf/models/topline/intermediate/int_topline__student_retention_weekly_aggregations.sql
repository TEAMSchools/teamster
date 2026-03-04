with
    retention_over_time as (
        select
            student_number,
            academic_year,
            attrition_year,
            region,
            schoolid,
            grade_level,
            school,
            week_start_monday,
            week_end_sunday,
            is_current_week,
            is_retained_int,
        from {{ ref("int_students__retention_over_time") }}
        where
            academic_year >= {{ var("current_academic_year") - 1 }}
            and region != 'Paterson'
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="retention_over_time",
                partition_by="student_number, week_start_monday",
                order_by="attrition_year desc",
            )
        }}
    )

select
    s.academic_year,
    s.region,
    s.schoolid,
    s.school,
    s.week_start_monday as term,
    s.week_end_sunday as term_end,
    s.is_current_week,

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

    'Student and Family Experience' as layer,
    'Student Retention' as indicator,

    round(avg(s.is_retained_int), 3) as metric_aggregate_value,
from deduplicate as s
inner join
    {{ ref("int_google_sheets__topline_aggregate_goals") }} as g
    on s.region = g.entity
    and s.schoolid = g.schoolid
    and s.grade_level between g.grade_low and g.grade_high
    and g.topline_indicator = 'Student Retention'
    and g.org_level = 'school'
group by
    s.academic_year,
    s.region,
    s.school,
    s.schoolid,
    s.week_start_monday,
    s.week_end_sunday,
    s.is_current_week,
    g.indicator_display,
    g.org_level,
    g.has_goal,
    g.goal_type,
    g.goal_direction,
    g.aggregation_data_type,
    g.aggregation_type,
    g.aggregation_hash,
    g.aggregation_display,
    g.goal

union all

select
    s.academic_year,
    s.region,

    null as schoolid,
    'All' as school,

    s.week_start_monday as term,
    s.week_end_sunday as term_end,
    s.is_current_week,

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

    'Student and Family Experience' as layer,
    'Student Retention' as indicator,

    round(avg(s.is_retained_int), 3) as metric_aggregate_value,
from deduplicate as s
inner join
    {{ ref("int_google_sheets__topline_aggregate_goals") }} as g
    on s.region = g.entity
    and s.grade_level between g.grade_low and g.grade_high
    and g.topline_indicator = 'Student Retention'
    and g.org_level = 'region'
group by
    s.academic_year,
    s.region,
    s.week_start_monday,
    s.week_end_sunday,
    s.is_current_week,
    g.indicator_display,
    g.org_level,
    g.has_goal,
    g.goal_type,
    g.goal_direction,
    g.aggregation_data_type,
    g.aggregation_type,
    g.aggregation_hash,
    g.aggregation_display,
    g.goal

union all

select
    s.academic_year,

    'All' as region,
    null as schoolid,
    'All' as school,

    s.week_start_monday as term,
    s.week_end_sunday as term_end,
    s.is_current_week,

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

    'Student and Family Experience' as layer,
    'Student Retention' as indicator,

    round(avg(s.is_retained_int), 3) as metric_aggregate_value,
from deduplicate as s
inner join
    {{ ref("int_google_sheets__topline_aggregate_goals") }} as g
    on s.grade_level between g.grade_low and g.grade_high
    and g.topline_indicator = 'Student Retention'
    and g.org_level = 'org'
group by
    s.academic_year,
    s.week_start_monday,
    s.week_end_sunday,
    s.is_current_week,
    g.indicator_display,
    g.org_level,
    g.has_goal,
    g.goal_type,
    g.goal_direction,
    g.aggregation_data_type,
    g.aggregation_type,
    g.aggregation_hash,
    g.aggregation_display,
    g.goal
