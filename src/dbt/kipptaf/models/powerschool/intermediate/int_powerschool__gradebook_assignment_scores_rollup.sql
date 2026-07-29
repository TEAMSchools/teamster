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

            sum(is_expected_late) as n_expected_late,
            sum(is_exempt) as n_exempt,
            sum(is_expected_missing) as n_expected_missing,
            sum(is_expected_null) as n_expected_null,
            sum(if(assign_score_above_max, 1, 0)) as n_score_above_max,
            sum(is_expected_academic_dishonesty) as n_expected_academic_dishonesty,

            sum(if(assign_mh_hwf_score_less_5, 1, 0)) as n_assign_mh_hwf_score_less_5,

            sum(
                if(assign_ms_hwf_missing_score_not_5, 1, 0)
            ) as n_assign_ms_hwf_missing_score_not_5,

            sum(
                if(assign_hs_hwfs_missing_score_not_0, 1, 0)
            ) as n_assign_hs_hwfs_missing_score_not_0,

            sum(if(assign_ms_s_score_less_50p, 1, 0)) as n_assign_ms_s_score_less_50p,
            sum(if(assign_hs_s_score_less_50p, 1, 0)) as n_assign_hs_s_score_less_50p,

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
    ),

    flags as (
        select
            *,

            -- flags
            if(
                category_code in ('H', 'W', 'F') and totalpointvalue != 10, true, false
            ) as assign_max_score_not_10,

            if(.5 * n_students <= n_exempt, true, false) as overly_exempt_assignment,

            safe_divide(n_expected_scored, n_expected) as assign_percent_graded,

        from transformations
    ),

    invalid_assign_check as (
        select
            *,

            (
                n_expected_null
                + n_score_above_max
                + n_assign_mh_hwf_score_less_5
                + n_assign_ms_hwf_missing_score_not_5
                + n_assign_hs_hwfs_missing_score_not_0
                + n_assign_ms_s_score_less_50p
                + n_assign_hs_s_score_less_50p
            ) as flags_sum,

            if(assign_percent_graded < 0.90, true, false) as percent_graded_min_not_met,

        from flags
    )

select
    *,

    if(
        assign_max_score_not_10
        or overly_exempt_assignment
        or flags_sum > 0
        or percent_graded_min_not_met,
        true,
        false
    ) as assignment_has_flags,

from invalid_assign_check
