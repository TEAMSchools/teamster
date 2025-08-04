select contact, test_type, test_subject, score,
from {{ ref("int_kippadb__standardized_test_unpivot") }}
where test_type in ('SAT', 'ACT') and rn_highest = 1

union all

/* SAT superscore - sum of highest EBRW and Math */
select contact, test_type, 'Superscore' as test_subject, sum(score) as score,
from {{ ref("int_kippadb__standardized_test_unpivot") }}
where rn_highest = 1 and test_type = 'SAT' and test_subject in ('EBRW', 'Math')
group by contact, test_type

union all

/* ACT Superscore - average of English, Math, Reading, Science */
select contact, test_type, 'Superscore' as test_subject, round(avg(score), 1) as score,
from {{ ref("int_kippadb__standardized_test_unpivot") }}
where
    rn_highest = 1
    and test_type = 'ACT'
    and test_subject in ('English', 'Math', 'Reading', 'Science')
group by contact, test_type
