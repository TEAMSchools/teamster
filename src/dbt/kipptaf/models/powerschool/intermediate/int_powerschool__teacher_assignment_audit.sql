{{- config(materialized="table") -}}

with
    assignments as (
        select
            c._dbt_source_relation,
            c.sectionid,
            c.schoolid,
            c.teacher_number,
            c.yearid,
            c.semester,
            c.quarter,
            c.week_number_quarter,
            c.week_start_monday,
            c.week_end_sunday,
            c.school_week_start_date_lead,
            c.assignmentid,
            c.assignment_name,
            c.duedate,
            c.scoretype,
            c.totalpointvalue,
            c.n_students,
            c.n_late,
            c.n_exempt,
            c.n_missing,
            c.n_expected,
            c.n_expected_scored,
            c.teacher_avg_score_for_assign_per_class_section_and_assign_id,

            ge.assignment_category_code,
            ge.assignment_category_name,
            ge.assignment_category_term,
            ge.expectation,

            sum(c.totalpointvalue) over (
                partition by c._dbt_source_relation, c.sectionid, c.quarter
            ) as total_totalpointvalue_section_quarter,

            sum(c.n_missing) over (
                partition by c._dbt_source_relation, c.sectionid, c.quarter
            ) as total_missing_section_quarter,

            count(c.assignmentid) over (
                partition by
                    c._dbt_source_relation,
                    c.sectionid,
                    c.quarter,
                    c.assignment_category_code
                order by c.week_number_quarter asc
            ) as assignment_count_section_quarter_category_running_week,

            sum(c.n_expected) over (
                partition by
                    c._dbt_source_relation,
                    c.sectionid,
                    c.quarter,
                    c.week_number_quarter,
                    c.assignment_category_code
            ) as total_expected_section_quarter_week_category,

            sum(c.n_expected_scored) over (
                partition by
                    c._dbt_source_relation,
                    c.sectionid,
                    c.quarter,
                    c.week_number_quarter,
                    c.assignment_category_code
            ) as total_expected_scored_section_quarter_week_category,

            sum(c.n_expected) over (
                partition by
                    c._dbt_source_relation,
                    c.teacher_number,
                    c.schoolid,
                    c.quarter,
                    c.week_number_quarter,
                    c.assignment_category_code
            ) as total_expected_teacher_school_quarter_week_category,

            sum(c.n_expected_scored) over (
                partition by
                    c._dbt_source_relation,
                    c.teacher_number,
                    c.schoolid,
                    c.quarter,
                    c.week_number_quarter,
                    c.assignment_category_code
            ) as total_expected_scored_teacher_school_quarter_week_category,

        from {{ ref("int_powerschool__teacher_assignment_audit_base") }} as c
        inner join
            {{ ref("stg_reporting__gradebook_expectations") }} as ge
            on c.academic_year = ge.academic_year
            and c.region = ge.region
            and c.quarter = ge.quarter
            and c.week_number_quarter = ge.week_number
            and c.school_level = ge.school_level
    )

select
    _dbt_source_relation,
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
    assignmentid,
    assignment_name,
    scoretype,
    totalpointvalue,
    duedate,
    n_students,
    n_late,
    n_exempt,
    n_missing,
    n_expected,
    n_expected_scored,
    teacher_avg_score_for_assign_per_class_section_and_assign_id,

    assignment_count_section_quarter_category_running_week
    as teacher_running_total_assign_by_cat,
    total_expected_scored_teacher_school_quarter_week_category
    as total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
    total_expected_teacher_school_quarter_week_category
    as total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,
    total_expected_scored_section_quarter_week_category
    as total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
    total_expected_section_quarter_week_category
    as total_expected_graded_assignments_by_course_cat_qt_audit_week,
    n_expected_scored
    as total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,
    n_expected as total_expected_graded_assignments_by_course_assign_id_qt_audit_week,

    if(assignmentid is not null, 1, 0) as teacher_assign_count,

    if(
        assignment_category_code = 'W'
        and assignment_count_section_quarter_category_running_week < expectation,
        true,
        false
    ) as w_expected_assign_count_not_met,

    if(
        assignment_category_code = 'F'
        and assignment_count_section_quarter_category_running_week < expectation,
        true,
        false
    ) as f_expected_assign_count_not_met,

    if(
        assignment_category_code = 'S'
        and assignment_count_section_quarter_category_running_week < expectation,
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
        total_missing_section_quarter = 0, true, false
    ) as qt_teacher_no_missing_assignments,

    if(
        assignment_category_code = 'S'
        and n_expected >= 1
        and total_totalpointvalue_section_quarter < 200,
        true,
        false
    ) as qt_teacher_s_total_less_200,

    if(
        assignment_category_code = 'S'
        and n_expected = 1
        and total_totalpointvalue_section_quarter > 200,
        true,
        false
    ) as qt_teacher_s_total_greater_200,

    round(
        safe_divide(
            total_expected_scored_teacher_school_quarter_week_category,
            total_expected_teacher_school_quarter_week_category
        ),
        2
    ) as percent_graded_completion_by_cat_qt_audit_week_all_courses,

    round(
        safe_divide(
            total_expected_scored_section_quarter_week_category,
            total_expected_section_quarter_week_category
        ),
        2
    ) as percent_graded_completion_by_cat_qt_audit_week,

    round(
        safe_divide(n_expected_scored, n_expected), 2
    ) as percent_graded_completion_by_assign_id_qt_audit_week,
from assignments
