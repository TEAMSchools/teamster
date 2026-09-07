select
    e.academic_year,
    e.region,
    e.grade,
    e.admin_season,
    e.round_number,
    e.min_pm_round,
    e.max_pm_round,
    e.month_round,
    e.expected_measure_name_code,
    e.expected_measure_name,
    e.expected_measure_standard,
    e.measure_standard_level,
    e.pm_goal_criteria,
    e.test_code as code,
    e.start_date,
    e.end_date,

    g.admin_season as benchmark_season,
    g.grade_level_standard as benchmark_goal,

from {{ ref("int_google_sheets__dibels_expected_assessments_by_levels") }} as e
left join
    {{ ref("stg_google_sheets__dibels_goals_long") }} as g
    on e.expected_measure_standard = g.measure_standard
    and e.grade = g.grade_level
    and e.admin_season = g.matching_pm_season
where
    e.assessment_type = 'PM'
    -- the sheet's off switch. The internal chain leaves this to its consumers,
    -- which is prod behavior; a new model has no such contract to keep, and a
    -- cancelled round is not an expectation.
    and e.assessment_include is null
    -- pm_goal_include marks a scaffold-fill row: a measure tested elsewhere in
    -- the season but not this round, kept so the internal method's trajectory
    -- stays continuous. Aimline has no trajectory, but the by-levels rows were
    -- generated from the internal sheet and carry the scaffold anyway, so this
    -- filter is what makes the column's absence from the output correct rather
    -- than merely tidy.
    and e.pm_goal_include is null
    -- the window comes from upstream, resolved against each grade's own band. A
    -- null means no term row covers this grade, which leaves "was the student
    -- tested inside the round" unanswerable.
    and e.start_date is not null
