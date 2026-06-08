with
    assignment_score_rollup as (
        select
            s._dbt_source_relation,
            s.assignmentsectionid,

            countif(s.is_expected) as n_expected,
            countif(s.is_expected_scored) as n_expected_scored,

        from {{ ref("int_powerschool__gradebook_assignments_scores") }} as s
        group by s._dbt_source_relation, s.assignmentsectionid
    ),

    assignments as (
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

            a.assignmentid,
            a.name as assignment_name,
            a.duedate,
            a.scoretype,
            a.totalpointvalue,

            asg.n_expected,
            asg.n_expected_scored,

            count(a.assignmentid) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sectionid,
                    sec.assignment_category_term
            ) as teacher_running_total_assign_by_cat,

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
                    sec.assignment_category_code
            ) as total_expected_section_quarter_category,

            sum(asg.n_expected_scored) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sectionid,
                    sec.quarter,
                    sec.assignment_category_code
            ) as total_expected_scored_section_quarter_category,

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
    ),

    percent_graded as (
        select
            *,

            safe_divide(
                total_expected_scored_section_quarter_category,
                total_expected_section_quarter_category
            ) as percent_graded_for_quarter_class,

        from assignments
    )

select
    f._dbt_source_relation,
    f.academic_year,
    f.academic_year_display,
    f.yearid,
    f.schoolid,
    f.school,
    f.region,
    f.school_level,
    f.region_school_level,
    f.sections_dcid,
    f.sectionid,
    f.section_number,
    f.external_expression,
    f.course_number,
    f.course_name,
    f.credit_type,
    f.exclude_from_gpa,
    f.teacher_number,
    f.teacher_name,
    f.teacher_tableau_username,
    f.manager_employee_number,
    f.manager_name,
    f.manager_tableau_username,
    f.hos,
    f.school_leader,
    f.school_leader_tableau_username,
    f.quarter,
    f.semester,
    f.quarter_start_date,
    f.quarter_end_date,
    f.is_current_term,
    f.section_or_period,
    f.assignment_category_code,
    f.assignment_category_name,
    f.assignment_category_term,
    f.expectation,
    f.notes,
    f.assignmentid,
    f.assignment_name,
    f.duedate,
    f.scoretype,
    f.totalpointvalue,
    f.n_expected,
    f.n_expected_scored,
    f.teacher_running_total_assign_by_cat,
    f.sum_totalpointvalue_section_quarter_category,
    f.total_expected_section_quarter_category,
    f.total_expected_scored_section_quarter_category,
    f.percent_graded_for_quarter_class,

    if(
        f.assignment_category_code = 'W' and f.percent_graded_for_quarter_class < .7,
        true,
        false
    ) as w_percent_graded_min_not_met,

    if(
        f.assignment_category_code = 'H' and f.percent_graded_for_quarter_class < .7,
        true,
        false
    ) as h_percent_graded_min_not_met,

    if(
        f.assignment_category_code = 'F' and f.percent_graded_for_quarter_class < .7,
        true,
        false
    ) as f_percent_graded_min_not_met,

    if(
        f.assignment_category_code = 'S' and f.percent_graded_for_quarter_class < .7,
        true,
        false
    ) as s_percent_graded_min_not_met,

    if(
        f.assignment_category_code = 'W'
        and f.teacher_running_total_assign_by_cat < f.expectation,
        true,
        false
    ) as w_expected_assign_count_not_met,

    if(
        f.assignment_category_code = 'H'
        and f.teacher_running_total_assign_by_cat < f.expectation,
        true,
        false
    ) as h_expected_assign_count_not_met,

    if(
        f.assignment_category_code = 'F'
        and f.teacher_running_total_assign_by_cat < f.expectation,
        true,
        false
    ) as f_expected_assign_count_not_met,

    if(
        f.assignment_category_code = 'S'
        and f.teacher_running_total_assign_by_cat < f.expectation,
        true,
        false
    ) as s_expected_assign_count_not_met,

from percent_graded as f
