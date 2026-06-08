with
    assignment_score_rollup as (
        select
            _dbt_source_relation,
            assignmentsectionid,

            count(students_dcid) as n_students,

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

            countif(is_expected) as n_expected,
            countif(is_expected_scored) as n_expected_scored,

            avg(
                if(is_expected_scored, assign_final_score_percent, null)
            ) as teacher_avg_score_for_assign_per_class_section_and_assign_id,

        from {{ ref("int_powerschool__gradebook_assignments_scores") }}
        group by _dbt_source_relation, assignmentsectionid
    )

select
    sec._dbt_source_relation,
    sec.academic_year,
    sec.academic_year_display,
    sec.yearid,
    sec.schoolid,
    sec.school,
    sec.region,
    sec.school_level,
    sec.region_school_level,
    sec.sections_dcid,
    sec.sectionid,
    sec.section_number,
    sec.external_expression,
    sec.course_number,
    sec.course_name,
    sec.credit_type,
    sec.exclude_from_gpa,
    sec.teacher_number,
    sec.teacher_name,
    sec.teacher_tableau_username,
    sec.manager_employee_number,
    sec.manager_name,
    sec.manager_tableau_username,
    sec.hos,
    sec.school_leader,
    sec.school_leader_tableau_username,
    sec.quarter,
    sec.semester,
    sec.quarter_start_date,
    sec.quarter_end_date,
    sec.is_current_term,
    sec.section_or_period,
    sec.assignment_category_code,
    sec.assignment_category_name,
    sec.assignment_category_term,
    sec.expectation,
    sec.notes,
    sec.scaffold_name,

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
    asg.n_academic_dishonesty,
    asg.n_null,
    asg.n_is_null_missing,
    asg.n_is_null_not_missing,
    asg.n_expected,
    asg.n_expected_scored,
    asg.teacher_avg_score_for_assign_per_class_section_and_assign_id,

    if(
        sec.assignment_category_code = 'W' and a.totalpointvalue != 10, true, false
    ) as w_assign_max_score_not_10,

    if(
        sec.assignment_category_code = 'F' and a.totalpointvalue != 10, true, false
    ) as f_assign_max_score_not_10,

    if(
        sec.assignment_category_code = 'H'
        and sec.school_level != 'ES'
        and a.totalpointvalue != 10,
        true,
        false
    ) as h_assign_max_score_not_10,

    sum(a.totalpointvalue) over (
        partition by
            sec._dbt_source_relation,
            sec.quarter,
            sec.sectionid,
            sec.assignment_category_code
    ) as sum_totalpointvalue_section_quarter_category,

    count(a.assignmentid) over (
        partition by
            sec._dbt_source_relation, sec.sectionid, sec.assignment_category_term
    ) as teacher_running_total_assign_by_cat,

from {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as sec
left join
    {{ ref("int_powerschool__gradebook_assignments") }} as a
    on sec.sections_dcid = a.sectionsdcid
    and sec.assignment_category_name = a.category_name
    and a.duedate between sec.quarter_start_date and sec.quarter_end_date
    and {{ union_dataset_join_clause(left_alias="sec", right_alias="a") }}
left join
    assignment_score_rollup as asg
    on a.assignmentsectionid = asg.assignmentsectionid
    and {{ union_dataset_join_clause(left_alias="a", right_alias="asg") }}
where sec.scaffold_name = 'teacher_category_scaffold'
