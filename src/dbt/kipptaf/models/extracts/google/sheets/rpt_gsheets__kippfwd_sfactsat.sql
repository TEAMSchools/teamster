with
    base_scores as (
        select
            contact,
            `date`,
            test_type,
            score_type,
            score,

            if(
                test_type = 'ACT', '01280000000BQ2UAAW', '01280000000BQ2ZAAW'
            ) as record_typeid,

        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where test_type in ('ACT', 'SAT') and date is not null
    ),

    current_scores as (select *, from {{ ref("int_assessments__college_assessment") }})

select *,
from current_scores
