select
    g.academic_year,
    g.region,
    g.admin_season,
    g.assessment_grade,
    g.assessment_grade_int,
    g.measure_standard,
    g.`round`,
    g.benchmark_goal,
    g.round_growth_words_goal,
    g.cumulative_growth_words,

    a.student_number,
    a.measure_name_code,
    a.measure_standard_score,

    if(
        a.measure_standard_score >= g.cumulative_growth_words, 1, 0
    ) as met_measure_standard_goal,

from {{ ref("stg_google_sheets__dibels_pm_goals") }} as g
left join
    {{ ref("int_amplify__all_assessments") }} as a
    on g.academic_year = a.academic_year
    and g.region = a.region
    and g.assessment_grade_int = g.assessment_grade_int
    and g.admin_season = a.period
    and g.`round` = a.`round`
    and g.measure_standard = a.measure_standard
    and a.assessment_type = 'PM'
    and a.overall_probe_eligible = 'Yes'
where g.pm_goal_include is null
