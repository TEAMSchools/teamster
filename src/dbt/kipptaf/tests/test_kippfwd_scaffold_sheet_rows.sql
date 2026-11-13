-- depends_on: {{ ref("stg_google_sheets__kippfwd__scaffold") }}
with
    scaffold as (
        select
            academic_year,
            expected_test_type,
            expected_scope,
            expected_grade_level,
            expected_score_type,

            {{ kippfwd_scaffold_problem() }} as problem,
        from {{ source("google_sheets", "src_google_sheets__kippfwd__scaffold") }}
    ),

    duplicate_keys as (
        select
            academic_year,
            expected_test_type,
            expected_scope,
            expected_grade_level,
            expected_score_type,

            'key appears on more than one row' as problem,
        from scaffold
        where problem is null
        group by
            academic_year,
            expected_test_type,
            expected_scope,
            expected_grade_level,
            expected_score_type
        having count(*) > 1
    )

select
    academic_year,
    expected_test_type,
    expected_scope,
    expected_grade_level,
    expected_score_type,
    problem,
from scaffold
where problem is not null

union all

select
    academic_year,
    expected_test_type,
    expected_scope,
    expected_grade_level,
    expected_score_type,
    problem,
from duplicate_keys
