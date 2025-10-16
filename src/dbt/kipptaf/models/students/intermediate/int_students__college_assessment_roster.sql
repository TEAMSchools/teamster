select
    s.*,

    e.grade_level,
    e.graduation_year,

    if(
        s.subject_area in ('Composite', 'Combined'), 'Total', s.subject_area
    ) as aligned_subject_area,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "s.student_number",
                "s.test_type",
                "s.score_type",
                "s.test_date",
            ]
        )
    }} as surrogate_key,

from {{ ref("int_assessments__college_assessment") }} as s
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on s.academic_year = e.academic_year
    and s.student_number = e.student_number
    and e.school_level = 'HS'
    and e.rn_year = 1
