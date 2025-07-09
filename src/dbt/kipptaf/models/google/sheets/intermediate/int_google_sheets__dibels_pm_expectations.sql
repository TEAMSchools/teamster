select
    e.academic_year,
    e.region,
    e.grade,
    e.admin_season,
    e.`round`,
    e.expected_measure_name_code,
    e.expected_measure_standard,

    t.code,

    g.admin_season as benchmark_season,
    g.matching_pm_season,
    g.grade_level_standard as benchmark_goal,

from {{ ref("stg_google_sheets__dibels_expected_assessments") }} as e
inner join
    {{ ref("stg_reporting__terms") }} as t
    on e.academic_year = t.academic_year
    and e.region = t.region
    and e.admin_season = t.name
    and e.assessment_type = 'PM'
    and t.type = 'LIT'
left join
    {{ ref("stg_google_sheets__dibels_goals_long") }} as g
    on e.expected_measure_standard = g.measure_standard
    and e.grade = g.grade_level
where e.academic_year >= 2024
