with
    transformations as (
        select
            _dbt_source_project,
            sectionsdcid,
            assignmentsectionid,
            assignmentid,
            assignment_name,
            duedate,
            scoretype,
            totalpointvalue,
            category_code,

            count(students_dcid) as n_students,
            countif(is_expected) as n_expected,
            countif(is_expected_scored) as n_expected_scored,

            sum(is_expected_late) as n_late,
            sum(is_exempt) as n_exempt,
            sum(is_expected_missing) as n_missing,
            sum(is_expected_null) as n_null,
            sum(is_expected_academic_dishonesty) as n_academic_dishonesty,

            sum(
                if(is_expected_null = 1 and is_expected_missing = 1, 1, 0)
            ) as n_is_null_missing,

            sum(
                if(is_expected_null = 1 and is_expected_missing = 0, 1, 0)
            ) as n_is_null_not_missing,

            avg(
                if(is_expected_scored, assign_final_score_percent, null)
            ) as avg_score_for_assign,

        from {{ ref("int_powerschool__gradebook_assignments_scores") }}
        where _dbt_source_project != 'kippmiami'
        group by
            _dbt_source_project,
            sectionsdcid,
            assignmentsectionid,
            assignmentid,
            assignment_name,
            duedate,
            scoretype,
            totalpointvalue,
            category_code
    )

select
    *,

    -- flags
    if(
        category_code in ('H', 'W', 'F') and totalpointvalue != 10, true, false
    ) as assign_max_score_not_10,

    if(.5 * n_students <= n_exempt, true, false) as overly_exempt_assignment,

    safe_divide(n_expected_scored, n_expected) as assign_percent_graded,

from transformations
