with
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
            end as join_clause
        from {{ ref("int_topline__dashboard_aggregations") }}
        where indicator = 'Total Enrollment'
    ),

    targets as (
        select e.*, t.seat_target, t.budget_target
        from enrollment as e
        inner join
            {{ ref("stg_google_sheets__topline_enrollment_targets") }} as t
            on e.academic_year = t.academic_year
            and e.join_clause = t.join_clause
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
            goal_direction,
            aggregation_data_type,
            aggregation_type,
            aggregation_hash,
            join_clause,
            metric_aggregate_value,
            if(
                target_type = 'seat_target', 'Seat Target', 'Budget Target'
            ) as indicator,
            cast(target_value as int64) as goal,
        from
            targets
            unpivot (target_value for target_type in (seat_target, budget_target))
        where region != 'Paterson'
    )

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
    tg.goal_direction,
    tg.aggregation_data_type,
    tg.aggregation_type,
    tg.aggregation_hash,
    tg.goal,

    round(safe_divide(tu.metric_aggregate_value, tu.goal), 3) as metric_aggregate_value,
from target_unpivot as tu
left join
    {{ ref("stg_google_sheets__topline_aggregate_goals") }} as tg
    on tu.indicator = tg.topline_indicator
    and tu.layer = tg.layer
    and tu.aggregation_hash = tg.aggregation_hash
where tg.has_goal
