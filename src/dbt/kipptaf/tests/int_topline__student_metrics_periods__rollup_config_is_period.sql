/* TODO(#4363): repoint to int_google_sheets__topline_aggregate_goals
   .period_rollup at sheet cutover (plan Task 13) */
with
    period_indicators as (
        select distinct layer, indicator,
        from {{ ref("int_topline__student_metrics_periods") }}
    )

select p.layer, p.indicator, rc.period_rollup,
from period_indicators as p
left join
    {{ ref("seed_topline_period_rollup") }} as rc
    on p.layer = rc.layer
    and p.indicator = rc.topline_indicator
where rc.period_rollup is null or rc.period_rollup != 'period'
