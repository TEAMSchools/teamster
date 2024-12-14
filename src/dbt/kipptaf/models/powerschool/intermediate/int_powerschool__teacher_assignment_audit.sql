{{- config(materialized="table") -}}

with
    assignments as (
        select
            c._dbt_source_relation,
            c.region,
            c.sectionid,
            c.schoolid,
            c.teacher_number,
            c.yearid,
            c.semester,
            c.quarter,
            c.week_number_quarter,
            c.week_start_monday,
            c.week_end_sunday,
            c.audit_due_date,
            c.assignment_category_code,
            c.assignment_category_name,
            c.assignment_category_term,
            c.expectation,
            c.teacher_assign_id,
            c.teacher_assign_name,
            c.teacher_assign_due_date,
            c.teacher_assign_score_type,
            c.teacher_assign_max_score,
            c.n_students,
            c.n_late,
            c.n_exempt,
            c.n_missing,
            c.n_expected,
            c.n_expected_scored,
            c.teacher_avg_score_for_assign_per_class_section_and_assign_id,

            sum(c.teacher_assign_max_score) over (
                partition by c._dbt_source_relation, c.sectionid, c.quarter
            ) as total_totalpointvalue_section_quarter,

            sum(c.n_missing) over (
                partition by c._dbt_source_relation, c.sectionid, c.quarter
            ) as total_missing_section_quarter,

            count(c.teacher_assign_id) over (
                partition by
                    c._dbt_source_relation,
                    c.sectionid,
                    c.quarter,
                    c.assignment_category_code
                order by c.week_number_quarter asc
            ) as assignment_count_section_quarter_category_running_week,

        from {{ ref("int_powerschool__teacher_assignment_audit_base") }} as c
        where c.yearid = {{ var("current_academic_year") - 1990 }}

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
    audit_due_date,
    assignment_category_code,
    assignment_category_name,
    assignment_category_term,
    expectation,
    teacher_assign_id,
    teacher_assign_name,
    teacher_assign_score_type,
    teacher_assign_max_score,
    teacher_assign_due_date,
    n_students,
    n_late,
    n_exempt,
    n_missing,
    n_expected,
    n_expected_scored,
    teacher_avg_score_for_assign_per_class_section_and_assign_id,

    assignment_count_section_quarter_category_running_week
    as teacher_running_total_assign_by_cat,
    if(teacher_assign_id is not null, 1, 0) as teacher_assign_count,

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
        assignment_category_code = 'W' and teacher_assign_max_score != 10, true, false
    ) as w_assign_max_score_not_10,

    if(
        assignment_category_code = 'F' and teacher_assign_max_score != 10, true, false
    ) as f_assign_max_score_not_10,

    if(
        assignment_category_code = 'S'
        and n_expected = 1
        and total_totalpointvalue_section_quarter > 200,
        true,
        false
    ) as qt_teacher_s_total_greater_200,

    if(
        region = 'Miami'
        and assignment_category_code = 'S'
        and teacher_assign_max_score > 100,
        true,
        false
    ) as s_max_score_greater_100,

from assignments
