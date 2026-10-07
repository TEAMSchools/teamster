-- int_google_sheets__kippfwd__goals_unpivot collapses the goals sheet's grade
-- rows to one row for the over time branch, taking the over time goal where the
-- sheet states one and the per-grade goal otherwise. Either path is a silent
-- pick if the values it collapses disagree, so this fires on both: an over time
-- goal stated inconsistently across a score type's grade rows, or a per-grade
-- goal that disagrees where no over time goal exists to override it.
select
    academic_year,
    test_type,
    score_type,
    expected_metric_type,

    countif(is_over_time_goal) as n_over_time_rows,
    count(
        distinct if(is_over_time_goal, expected_metric_goal, null)
    ) as n_over_time_goals,
    count(distinct expected_metric_goal) as n_goals,

from {{ ref("stg_google_sheets__kippfwd__goals") }}
group by academic_year, test_type, score_type, expected_metric_type
having
    count(distinct if(is_over_time_goal, expected_metric_goal, null)) > 1
    or (countif(is_over_time_goal) = 0 and count(distinct expected_metric_goal) > 1)
