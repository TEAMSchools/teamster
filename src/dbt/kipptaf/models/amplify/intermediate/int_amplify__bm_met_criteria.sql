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

    e.school,

from {{ ref("int_amplify__all_assessments") }} as a
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on a.academic_year = e.academic_year
    and a.region = e.region
    and a.student_number = e.student_number
    and a.assessment_grade_int = e.grade_level
    and a.client_date between e.entrydate and e.exitdate
where
    a.assessment_type = 'Benchmark'
    and a.measure_standard = 'Composite'
    and a.period != 'EOY'
