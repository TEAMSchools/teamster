with
    goals as (
        select
            *,
            if(
                topline_indicator = 'Total Enrollment', 'Integer', 'Decimal'
            ) as data_type,
        from {{ ref("stg_google_sheets__topline_aggregate_goals") }}
    ),

    agg_union_student as (
        select
            m.academic_year,
            m.region,
            m.schoolid,
            m.school,
            m.layer,
            m.indicator,
            m.discipline,
            m.term,
            m.is_current_week,

            g.org_level,
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
                when 'Comp'
                then round(sum(m.metric_value), 0) / max(target_value)
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
            m.is_current_week,
            g.org_level,
            g.has_goal,
            g.goal_direction,
            g.aggregation_type,
            g.aggregation_hash,
            g.goal

        union all

        select
            m.academic_year,
            m.region,
            null as schoolid,
            'All' as school,
            m.layer,
            m.indicator,
            m.discipline,
            m.term,
            m.is_current_week,

            g.org_level,
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
                when 'Comp'
                then round(sum(m.metric_value), 0) / max(target_value)
            end as metric_aggregate_value,
        from {{ ref("int_topline__student_metrics") }} as m
        left join
            goals as g
            on m.region = g.entity
            and m.grade_level between g.grade_low and g.grade_high
            and m.layer = g.layer
            and m.indicator = g.topline_indicator
            and g.org_level = 'region'
        group by
            m.academic_year,
            m.region,
            m.layer,
            m.indicator,
            m.discipline,
            m.term,
            m.is_current_week,
            g.org_level,
            g.has_goal,
            g.goal_direction,
            g.aggregation_type,
            g.aggregation_hash,
            g.goal

        union all

        select
            m.academic_year,
            'All' as region,
            null as schoolid,
            'All' as school,
            m.layer,
            m.indicator,
            m.discipline,
            m.term,
            m.is_current_week,

            g.org_level,
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
                when 'Comp'
                then round(sum(m.metric_value), 0) / max(target_value)
            end as metric_aggregate_value,
        from {{ ref("int_topline__student_metrics") }} as m
        left join
            goals as g
            on m.grade_level between g.grade_low and g.grade_high
            and m.layer = g.layer
            and m.indicator = g.topline_indicator
            and g.org_level = 'org'
        group by
            m.academic_year,
            m.layer,
            m.indicator,
            m.discipline,
            m.term,
            m.is_current_week,
            g.org_level,
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
from agg_union_student
where term <= current_date('America/New_York')
