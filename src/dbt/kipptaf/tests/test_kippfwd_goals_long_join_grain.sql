-- rpt_gsheets__college_assessments_long joins the All Grades benchmark goals on
-- test type and score type alone, with no academic year binding, and resolves its
-- pivot with any_value(). A second academic year stating a goal for a key that
-- already has one would therefore double every matching score row and pick a
-- threshold arbitrarily, with nothing erroring.
--
-- The goals model already spans two academic years. They do not collide today
-- only because the AY2023 rows are practice ACT while the AY2026 ACT rows are
-- official. That is a property of the current data, not of the model, so it is
-- asserted here rather than assumed.
--
-- The model's own uniqueness test carries academic_year and so cannot catch this.
-- Adding a year binding to the reporting view would be the alternative fix; that
-- is a decision about which year's thresholds a historical score should be judged
-- against, which nobody has needed to make yet. TODO(#4658).
select test_type, score_type, expected_metric_name, count(*) as goal_rows,

from {{ ref("int_google_sheets__kippfwd__goals_unpivot") }}
where expected_goal_type = 'Benchmark' and goal_branch = 'All Grades'
group by test_type, score_type, expected_metric_name
having count(*) > 1
