with
    pre_agg_union_student as (
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
            {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g
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
            m.academic_year,
            m.region,

            null as schoolid,
            'All' as school,

            m.layer,
            m.indicator,
            m.discipline,
            m.term,
            m.is_current_week,

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
            {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g
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
            m.academic_year,

            'All' as region,
            null as schoolid,
            'All' as school,

            m.layer,
            m.indicator,
            m.discipline,
            m.term,
            m.is_current_week,

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
            {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g
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
    ),

    enrollment as (
        select
            *,

            case
                when org_level = 'org'
                then org_level
                when org_level = 'region'
                then region
                when org_level = 'school'
                then cast(schoolid as string)
            end as join_key,
        from pre_agg_union_student
        where indicator = 'Total Enrollment'
    ),

    targets as (
        select e.*, t.seat_target, t.budget_target,
        from enrollment as e
        inner join
            {{ ref("stg_google_sheets__topline_enrollment_targets") }} as t
            on e.academic_year = t.academic_year
            and e.join_key = t.join_key
    ),

    target_unpivot as (
        select
            academic_year,
            region,
            schoolid,
            school,
            layer,
            discipline,
            term,
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
            metric_aggregate_value,

            cast(target_value as int) as goal,

            if(
                target_type = 'seat_target', 'Seat Target', 'Budget Target'
            ) as indicator,
        from
            targets
            unpivot (target_value for target_type in (seat_target, budget_target))
        where region != 'Paterson'
    ),

    target_goals as (
        select
            tu.academic_year,
            tu.region,
            tu.schoolid,
            tu.school,
            tu.layer,
            tu.indicator,
            tu.discipline,
            tu.term,
            tu.is_current_week,

            tg.indicator_display,
            tg.org_level,
            tg.has_goal,
            tg.goal_type,
            tg.goal_direction,
            tg.aggregation_data_type,
            tg.aggregation_type,
            tg.aggregation_hash,
            tg.aggregation_display,
            tg.goal,

            round(
                safe_divide(tu.metric_aggregate_value, tu.goal), 3
            ) as metric_aggregate_value,
        from target_unpivot as tu
        inner join
            {{ ref("stg_google_sheets__topline_aggregate_goals") }} as tg
            on tu.indicator = tg.topline_indicator
            and tu.layer = tg.layer
            and tu.aggregation_hash = tg.aggregation_hash
            and tg.has_goal
    ),

    agg_union_student as (
        select *,
        from pre_agg_union_student

        union all

        select *,
        from target_goals

        union all

        select *,
        from {{ ref("int_topline__student_retention_weekly_aggregations") }}
    ),

    agg_union_staff as (
        select
            m.academic_year,
            m.home_business_unit_name as region,
            m.home_work_location_powerschool_school_id as schoolid,
            m.home_work_location_name as school,
            m.layer,
            m.indicator,

            cast(null as string) as discipline,

            m.term,
            m.is_current_week,

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

            case
                g.aggregation_type
                when 'Average'
                then round(avg(m.metric_value), 3)
                when 'Divide'
                then round(safe_divide(sum(m.numerator), sum(m.denominator)), 3)
                when 'Sum'
                then round(sum(m.metric_value), 0)
            end as metric_aggregate_value,
        from {{ ref("int_topline__staff_metrics") }} as m
        left join
            {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g
            on m.home_business_unit_name = g.entity
            and m.home_work_location_powerschool_school_id = g.schoolid
            and m.layer = g.layer
            and m.indicator = g.topline_indicator
            and g.org_level = 'school'
        group by
            m.academic_year,
            m.home_business_unit_name,
            m.home_work_location_powerschool_school_id,
            m.home_work_location_name,
            m.layer,
            m.indicator,
            m.term,
            m.is_current_week,
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
            m.academic_year,
            m.home_business_unit_name as region,
            m.home_work_location_powerschool_school_id as schoolid,

            'All' as school,

            m.layer,
            m.indicator,

            cast(null as string) as discipline,

            m.term,
            m.is_current_week,

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

            case
                g.aggregation_type
                when 'Average'
                then round(avg(m.metric_value), 3)
                when 'Divide'
                then round(safe_divide(sum(m.numerator), sum(m.denominator)), 3)
                when 'Sum'
                then round(sum(m.metric_value), 0)
            end as metric_aggregate_value,
        from {{ ref("int_topline__staff_metrics") }} as m
        left join
            {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g
            on m.home_business_unit_name = g.entity
            and m.layer = g.layer
            and m.indicator = g.topline_indicator
            and g.org_level = 'region'
        group by
            m.academic_year,
            m.home_business_unit_name,
            m.home_work_location_powerschool_school_id,
            m.home_work_location_name,
            m.layer,
            m.indicator,
            m.term,
            m.is_current_week,
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
            m.academic_year,

            'All' as region,
            null as schoolid,
            'All' as school,

            m.layer,
            m.indicator,

            cast(null as string) as discipline,

            m.term,
            m.is_current_week,

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

            case
                g.aggregation_type
                when 'Average'
                then round(avg(m.metric_value), 3)
                when 'Divide'
                then round(safe_divide(sum(m.numerator), sum(m.denominator)), 3)
                when 'Sum'
                then round(sum(m.metric_value), 0)
            end as metric_aggregate_value,
        from {{ ref("int_topline__staff_metrics") }} as m
        left join
            {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g
            on m.layer = g.layer
            and m.indicator = g.topline_indicator
            and g.org_level = 'org'
        group by
            m.academic_year,
            m.home_business_unit_name,
            m.layer,
            m.indicator,
            m.term,
            m.is_current_week,
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
            academic_year,
            region,
            schoolid,
            cast(school as string) as school,
            layer,
            indicator,
            cast(null as string) as discipline,
            week_start_monday as term,
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
        from {{ ref("int_topline__seats_staffed_weekly_aggregations") }}
    )

select
    'Student Metrics' as metric_type,

    *,

    if(
        aggregation_data_type = 'Numeric', metric_aggregate_value, null
    ) as metric_aggregate_value_numeric,
    if(
        aggregation_data_type = 'Integer', metric_aggregate_value, null
    ) as metric_aggregate_value_integer,

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

    if(
        case
            when not has_goal
            then null
            when goal_direction = 'baseball'
            then safe_divide(metric_aggregate_value, goal)
            when goal_direction = 'golf'
            then greatest(0, safe_divide(goal, metric_aggregate_value))
        end
        > 1,
        1,
        case
            when not has_goal
            then null
            when goal_direction = 'baseball'
            then safe_divide(metric_aggregate_value, goal)
            when goal_direction = 'golf'
            then greatest(0, safe_divide(goal, metric_aggregate_value))
        end
    ) as progress_to_goal_pct,
from agg_union_student
where term <= current_date('{{ var("local_timezone") }}')

union all

select
    'Staff Metrics' as metric_type,

    *,

    if(
        aggregation_data_type = 'Numeric', metric_aggregate_value, null
    ) as metric_aggregate_value_numeric,
    if(
        aggregation_data_type = 'Integer', metric_aggregate_value, null
    ) as metric_aggregate_value_integer,
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
    if(
        case
            when not has_goal
            then null
            when goal_direction = 'baseball'
            then safe_divide(metric_aggregate_value, goal)
            when goal_direction = 'golf'
            then greatest(0, safe_divide(goal, metric_aggregate_value))
        end
        > 1,
        1,
        case
            when not has_goal
            then null
            when goal_direction = 'baseball'
            then safe_divide(metric_aggregate_value, goal)
            when goal_direction = 'golf'
            then greatest(0, safe_divide(goal, metric_aggregate_value))
        end
    ) as progress_to_goal_pct,
from agg_union_staff
where term <= current_date('{{ var("local_timezone") }}')
