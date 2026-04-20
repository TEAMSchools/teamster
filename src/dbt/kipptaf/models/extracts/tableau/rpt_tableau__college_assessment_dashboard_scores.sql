with
    base as (
        select
            s.student_number,
            s.test_type,
            s.scope,
            s.score_type,
            s.subject_area,
            s.aligned_subject_area,
            s.scale_score,
            s.max_scale_score,

            e.region,
            e.school,
            e.graduation_year,
            e.ktc_cohort,

        from {{ ref("int_assessments__college_assessment") }} as s
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on s.student_number = e.student_number
            and e.school_level = 'HS'
            and e.rn_undergrad = 1
            and e.rn_year = 1
            and not e.is_out_of_district
        where
            s.rn_highest = 1
            and s.score_type not in (
                'act_composite',
                'act_english',
                'act_math',
                'act_reading',
                'act_science',
                'psat10_math_test',
                'psat10_reading',
                'sat_math_test_score',
                'sat_reading_test_score'
            )
    )

select
    student_number,
    test_type,
    scope,
    score_type,
    subject_area,
    aligned_subject_area,
    scale_score,
    max_scale_score,
    region,
    school,
    graduation_year,
    ktc_cohort,
    benchmark_name,
from base
cross join unnest(['College-Ready', 'HS-Ready', 'EA/ED-Ready']) as benchmark_name
where aligned_subject_area = 'Total'

union all

select
    student_number,
    test_type,
    scope,
    score_type,
    subject_area,
    aligned_subject_area,
    scale_score,
    max_scale_score,
    region,
    school,
    graduation_year,
    ktc_cohort,
    aligned_subject_area as benchmark_name,
from base
where aligned_subject_area in ('EBRW', 'Math')
