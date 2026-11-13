with
    scaffold as (
        select
            academic_year,
            expected_aligned_test_type,
            expected_test_type,
            expected_grade_level,
            expected_scope,
            expected_aligned_scope,
            expected_practice_test_subject,
            expected_subject_area,
            expected_aligned_subject_area,
            expected_grouping,
            expected_course_discipline,
            expected_score_category,
            expected_score_type,
            a1_attempt_min_score,
            a2_plus_attempts_min_score,
            hs_grad_ready_min_score,
            college_ready_min_score,

            {{ kippfwd_scaffold_problem() }} as problem,
        from {{ source("google_sheets", "src_google_sheets__kippfwd__scaffold") }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    valid_scaffold as (
        select *,
        from scaffold
        /* a blank or misspelled row matches nothing correctly, so it is dropped */
        where problem is null
    ),

    /* duplicate key: the stricter benchmark wins */
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="valid_scaffold",
                partition_by="academic_year, expected_test_type, expected_scope, expected_grade_level, expected_score_type",
                order_by="college_ready_min_score desc, hs_grad_ready_min_score desc, a1_attempt_min_score desc, a2_plus_attempts_min_score desc",
            )
        }}
    )

select
    academic_year,
    expected_aligned_test_type,
    expected_test_type,
    expected_grade_level,
    expected_scope,
    expected_aligned_scope,
    expected_practice_test_subject,
    expected_subject_area,
    expected_aligned_subject_area,
    expected_grouping,
    expected_course_discipline,
    expected_score_category,
    expected_score_type,
    a1_attempt_min_score,
    a2_plus_attempts_min_score,
    hs_grad_ready_min_score,
    college_ready_min_score,
from deduplicate
