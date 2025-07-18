select
    a.academic_year,
    a.region,
    a.student_number,
    a.assessment_grade,
    a.assessment_grade_int,
    a.period,
    a.measure_standard,
    a.measure_standard_level,
    a.aggregated_measure_standard_level,
    a.foundation_measure_standard_level,
    a.client_date,

    e.school,
    e.entrydate,
    e.exitdate,

    f.grade_goal,
    f.grade_range_goal,

from {{ ref("int_amplify__all_assessments") }} as a
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on a.academic_year = e.academic_year
    and a.region = e.region
    and a.student_number = e.student_number
    and a.assessment_grade_int = e.grade_level
    and a.client_date between e.entrydate and e.exitdate
left join
    {{ ref("stg_google_sheets__dibels_foundation_goals") }} as f
    on a.academic_year = f.academic_year
    and a.region = f.region
    and a.assessment_grade_int = f.grade_level
    and a.benchmark_goal_season = f.period
    and a.foundation_measure_standard_level = f.grade_goal_type
where
    a.academic_year >= 2024
    and a.assessment_type = 'Benchmark'
    and a.measure_standard = 'Composite'
    and a.period != 'EOY'
