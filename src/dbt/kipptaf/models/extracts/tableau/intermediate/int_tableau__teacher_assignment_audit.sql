with
    assignments as (
        select
            sec._dbt_source_relation,
            sec.region,
            sec.school_level,
            sec.academic_year,
            sec.yearid,
            sec.semester,
            sec.quarter,
            sec.week_number_quarter,
            sec.week_start_monday,
            sec.week_end_sunday,
            sec.school_week_start_date_lead,
            sec.assignment_category_code,
            sec.assignment_category_name,
            sec.assignment_category_term,
            sec.expectation,
            sec.sectionid,
            sec.teacher_number,

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
                partition by sec._dbt_source_relation, sec.quarter, sec.sectionid
            ) as sum_totalpointvalue_section_quarter,
        from {{ ref("int_tableau__gradebook_audit_section_scaffold") }} as sec
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

    )

select
    _dbt_source_relation,
    region,
    sectionid,
    teacher_number,
    `quarter`,
    semester,
    week_number_quarter,
    week_start_monday,
    week_end_sunday,
    school_week_start_date_lead,
    assignment_category_code,
    assignment_category_name,
    assignment_category_term,
    expectation,
    assignmentsectionid,
    assignmentid as teacher_assign_id,
    assignment_name as teacher_assign_name,
    duedate as teacher_assign_due_date,
    scoretype as teacher_assign_score_type,
    totalpointvalue as teacher_assign_max_score,
    n_students,
    n_late,
    n_exempt,
    n_missing,
    n_expected,
    n_expected_scored,
    running_count_assignments_section_category_term
    as teacher_running_total_assign_by_cat,
    avg_expected_scored_percent
    as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    if(assignmentid is not null, 1, 0) as teacher_assign_count,

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
        and n_expected = 1
        and sum_totalpointvalue_section_quarter > 200,
        true,
        false
    ) as qt_teacher_s_total_greater_200,
from assignments
