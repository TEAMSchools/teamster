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

from {{ ref("int_amplify__all_assessments") }} as a
where
    a.assessment_type = 'Benchmark'
    and a.measure_standard = 'Composite'
    and a.period != 'EOY'
