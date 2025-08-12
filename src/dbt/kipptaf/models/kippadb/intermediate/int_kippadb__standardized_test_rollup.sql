{{ config(materialized="ephemeral") }}

with
    tests as (
        select school_specific_id, test_type, test_subject, score,
        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where
            rn_highest = 1
            and test_type in ('SAT', 'ACT')
            and score_type not in (
                'sat_critical_reading_pre_2016',
                'sat_math_pre_2016',
                'sat_writing_pre_2016'
            )
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
from {{ ref("int_kippadb__standardized_test_unpivot") }}
where test_type = 'ACT' and test_subject in ('English', 'Math', 'Reading', 'Science')
group by school_specific_id, test_type
