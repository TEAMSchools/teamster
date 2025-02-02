with
    assignments as (
        select
            sec.*,

            a.assignmentsectionid,
            a.assignmentid,
            a.name as assignment_name,
            a.duedate,
            a.scoretype,
            a.totalpointvalue,

            asg.n_students,
            asg.n_late,
            asg.n_exempt,
            asg.n_missing,
            asg.n_null,
            asg.n_expected,
            asg.n_expected_scored,
            asg.avg_expected_scored_percent,

            count(a.assignmentid) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sectionid,
                    sec.assignment_category_term
                order by sec.week_number_quarter asc
            ) as running_count_assignments_section_category_term,

            sum(a.totalpointvalue) over (
                partition by
                    sec._dbt_source_relation,
                    sec.quarter,
                    sec.sectionid,
                    sec.assignment_category_code
            ) as sum_totalpointvalue_section_quarter_category,

            sum(asg.n_expected) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sectionid,
                    sec.quarter,
                    sec.week_number_quarter,
                    sec.assignment_category_code
            ) as total_expected_section_quarter_week_category,

            sum(asg.n_expected_scored) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sectionid,
                    sec.quarter,
                    sec.week_number_quarter,
                    sec.assignment_category_code
            ) as total_expected_scored_section_quarter_week_category,

        from
            {{ ref("int_tableau__gradebook_audit_section_week_category_scaffold") }}
            as sec
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on sec.sections_dcid = a.sectionsdcid
            and sec.assignment_category_name = a.category_name
            and a.duedate between sec.week_start_monday and sec.week_end_sunday
            and {{ union_dataset_join_clause(left_alias="sec", right_alias="a") }}
        left join
            {{ ref("int_powerschool__assignment_score_rollup") }} as asg
            on a.assignmentsectionid = asg.assignmentsectionid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="asg") }}

    ),

    final as (
        select
            *,

            safe_divide(
                total_expected_scored_section_quarter_week_category,
                total_expected_section_quarter_week_category
            ) as percent_graded_for_quarter_week_class,

        from assignments
    )

select
    *,

    if(assignmentid is not null, 1, 0) as teacher_assign_count,

    if(
        assignment_category_code = 'W' and percent_graded_for_quarter_week_class < .7,
        true,
        false
    ) as w_percent_graded_min_not_met,

    if(
        assignment_category_code = 'F' and percent_graded_for_quarter_week_class < .7,
        true,
        false
    ) as f_percent_graded_min_not_met,

    if(
        assignment_category_code = 'S' and percent_graded_for_quarter_week_class < .7,
        true,
        false
    ) as s_percent_graded_min_not_met,

    if(
        assignment_category_code = 'W'
        and running_count_assignments_section_category_term < expectation,
        true,
        false
    ) as w_expected_assign_count_not_met,

    if(
        assignment_category_code = 'F'
        and running_count_assignments_section_category_term < expectation,
        true,
        false
    ) as f_expected_assign_count_not_met,

    if(
        assignment_category_code = 'S'
        and running_count_assignments_section_category_term < expectation,
        true,
        false
    ) as s_expected_assign_count_not_met,

    if(
        assignment_category_code = 'W' and totalpointvalue != 10, true, false
    ) as w_assign_max_score_not_10,

    if(
        assignment_category_code = 'F' and totalpointvalue != 10, true, false
    ) as f_assign_max_score_not_10,

    if(
        region = 'Miami' and assignment_category_code = 'S' and totalpointvalue > 100,
        true,
        false
    ) as s_max_score_greater_100,

    if(
        assignment_category_code = 'S'
        and sum_totalpointvalue_section_quarter_category > 200,
        true,
        false
    ) as qt_teacher_s_total_greater_200,

    if(
        assignment_category_code = 'S'
        and sum_totalpointvalue_section_quarter_category < 200,
        true,
        false
    ) as qt_teacher_s_total_less_200,

from final
