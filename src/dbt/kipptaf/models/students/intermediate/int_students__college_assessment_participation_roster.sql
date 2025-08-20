select
    e._dbt_source_relation,
    e.student_number,
    e.salesforce_id,
    e.grade_level,

    a.scope,
    a.test_month,
    a.score_type,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    {{ ref("int_assessments__college_assessment") }} as a
    on e.academic_year = a.academic_year
    and e.student_number = a.student_number
    and a.score_type in (
        'act_composite',
        'sat_total_score',
        'psat89_total',
        'psatnmsqt_total',
        'psat10_total'
    )
where e.school_level = 'HS' and e.rn_year = 1
