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

from {{ ref("int_google_sheets__dibels_expected_assessments") }} as e
left join
    {{ ref("stg_google_sheets__dibels_goals_long") }} as g
    on e.expected_measure_standard = g.measure_standard
    and e.grade = g.grade_level
    and e.admin_season = g.matching_pm_season
where
    e.assessment_type = 'PM'
    and e.data_model = 'aimline'
    -- the window comes from upstream, resolved against each grade's own band. A
    -- null means no term row covers this grade, which leaves "was the student
    -- tested inside the round" unanswerable.
    and e.start_date is not null
