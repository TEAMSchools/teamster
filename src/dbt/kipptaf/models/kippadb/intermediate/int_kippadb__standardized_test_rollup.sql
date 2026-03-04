with
    tests as (
        select
            student_number as school_specific_id,
            scope as test_type,
            subject_area as test_subject,
            scale_score as score,
        from {{ ref("int_assessments__college_assessment") }}
        where rn_highest = 1 and scope in ('SAT', 'ACT', 'PSAT 8/9', 'PSAT NMSQT')
    )

select school_specific_id, test_type, test_subject, score,
from tests

union all

/* SAT superscore - sum of highest EBRW and Math */
select school_specific_id, test_type, 'Superscore' as test_subject, sum(score) as score,
from tests
where test_type = 'SAT' and test_subject in ('EBRW', 'Math')
group by school_specific_id, test_type

union all

/* ACT Superscore - average of English, Math, Reading, Science */
select
    school_specific_id,
    test_type,

    'Superscore' as test_subject,

    round(avg(score), 1) as score,
from tests
where test_type = 'ACT' and test_subject in ('English', 'Math', 'Reading', 'Science')
group by school_specific_id, test_type
