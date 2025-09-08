with
    goals as (
        select
            *,

            case
                org_level
                when 'org'
                then 'org_' || grade_low || '-' || grade_high
                when 'region'
                then entity || '_' || grade_low || '-' || grade_high
                when 'school'
                then schoolid || '_' || grade_low || '-' || grade_high
            end as aggregation_hash,
        from {{ ref("stg_google_sheets__topline_aggregate_goals") }}
    ),

    school_agg as (
        select
            m.academic_year,
            m.region,
            m.schoolid,
            m.school,
            m.layer,
            m.indicator,
            m.discipline,
            m.term,

            g.has_goal,
            g.goal_direction,
            g.aggregation_type,
            g.aggregation_hash,
            g.goal,

            case
                g.aggregation_type
                when 'Average'
                then round(avg(m.metric_value), 3)
                when 'Divide'
                then round(safe_divide(sum(m.numerator), sum(m.denominator)), 3)
                when 'Sum'
                then round(sum(m.metric_value), 0)
            end as metric_aggregate_value,
        from {{ ref("int_topline__student_metrics") }} as m
        left join
            goals as g
            on m.region = g.entity
            and m.schoolid = g.schoolid
            and m.grade_level between g.grade_low and g.grade_high
            and m.layer = g.layer
            and m.indicator = g.topline_indicator
            and g.org_level = 'school'
        group by
            m.academic_year,
            m.region,
            m.schoolid,
            m.school,
            m.layer,
            m.indicator,
            m.discipline,
            m.term,
            g.has_goal,
            g.goal_direction,
            g.aggregation_type,
            g.aggregation_hash,
            g.goal
    )

select
    *,

    case
        when not has_goal
        then null
        when goal_direction = 'baseball' and metric_aggregate_value >= goal
        then true
        when goal_direction = 'golf' and metric_aggregate_value < goal
        then true
        else false
    end as is_goal_met,

    case
        when not has_goal
        then null
        when goal_direction = 'baseball'
        then (goal - metric_aggregate_value) / goal
        when goal_direction = 'golf'
        then (metric_aggregate_value - goal) / goal
    end as goal_difference_percent,
from school_agg
