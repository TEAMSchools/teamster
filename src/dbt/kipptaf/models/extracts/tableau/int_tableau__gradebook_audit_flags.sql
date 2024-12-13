{{- config(materialized="table") -}}

with
    assignment_student as (
        select
            f._dbt_source_relation,
            f.academic_year,
            f.academic_year_display,
            f.region,
            f.school_level,
            f.region_school_level,
            f.schoolid,
            f.school,

            f.student_number,
            f.grade_level,

            f.semester,
            f.`quarter`,
            f.week_number,
            f.quarter_start_date,
            f.quarter_end_date,
            f.cal_quarter_end_date,
            f.is_current_quarter,
            f.is_quarter_end_date_range,
            f.audit_due_date,

            f.assignment_category_name,
            f.assignment_category_code,
            f.assignment_category_term,
            f.expectation,
            f.notes,
            f.sectionid,
            f.course_number,
            f.course_name,
            f.is_ap_course,

            f.teacher_number,
            f.teacher_name,

            t.teacher_assign_id,

            s.raw_score,
            s.score_entered,
            s.assign_final_score_percent,
            s.is_exempt,
            s.is_late,
            s.is_missing,

            s.assign_null_score,
            s.assign_score_above_max,
            s.assign_exempt_with_score,
            s.assign_w_score_less_5,
            s.assign_f_score_less_5,
            s.assign_w_missing_score_not_5,
            s.assign_f_missing_score_not_5,
            s.assign_s_score_less_50p,
            s.assign_s_ms_score_not_conversion_chart_options,
            s.assign_s_hs_score_not_conversion_chart_options,

        from {{ ref("int_tableau__gradebook_audit_roster") }} as f
        inner join
            {{ ref("int_powerschool__teacher_assignment_audit") }} as t
            on f.sectionid = t.sectionid
            and f.quarter = t.quarter
            and f.assignment_category_code = t.assignment_category_code
            and {{ union_dataset_join_clause(left_alias="f", right_alias="t") }}
        inner join
            {{ ref("int_powerschool__student_assignment_audit") }} as s
            on f.studentid = s.studentid
            and f.sectionid = s.sectionid
            and f.quarter = s.quarter
            and {{ union_dataset_join_clause(left_alias="f", right_alias="s") }}
            and t.week_number_quarter = s.week_number_quarter
            and t.teacher_assign_id = s.assignmentid
            and {{ union_dataset_join_clause(left_alias="t", right_alias="s") }}
    )
/*
    audits as (
        select
            *,

            if(
                region = 'Miami'
                and assignment_category_code = 'S'
                and totalpointvalue > 100,
                true,
                false
            ) as s_max_score_greater_100,

            case
                when region != 'Miami'
                then false
                when not is_quarter_end_date_range
                then false
                when
                    grade_level = 0
                    and course_name = 'HR'
                    and quarter_citizenship is null
                then true
                else false
            end as qt_kg_conduct_code_missing,

            if(
                region = 'Miami'
                and is_quarter_end_date_range
                and grade_level = 0
                and course_name != 'HR'
                and quarter_citizenship is not null,
                true,
                false
            ) as qt_kg_conduct_code_not_hr,

            if(
                region = 'Miami'
                and is_quarter_end_date_range
                and grade_level != 0
                and course_name != 'HR'
                and quarter_citizenship is null,
                true,
                false
            ) as qt_g1_g8_conduct_code_missing,

            if(
                region = 'Miami'
                and is_quarter_end_date_range
                and grade_level = 0
                and course_name = 'HR'
                and quarter_citizenship is not null
                and quarter_citizenship not in ('E', 'G', 'S', 'M'),
                true,
                false
            ) as qt_kg_conduct_code_incorrect,

            if(
                region = 'Miami'
                and is_quarter_end_date_range
                and grade_level != 0
                and course_name != 'HR'
                and quarter_citizenship is not null
                and quarter_citizenship not in ('A', 'B', 'C', 'D', 'E', 'F'),
                true,
                false
            ) as qt_g1_g8_conduct_code_incorrect,

            if(
                is_quarter_end_date_range
                and grade_level > 4
                and quarter_course_percent_grade_that_matters < 70
                and quarter_comment_value is null,
                true,
                false
            ) as qt_grade_70_comment_missing,

            if(
                region = 'Miami'
                and is_quarter_end_date_range
                and quarter_comment_value is null,
                true,
                false
            ) as qt_comment_missing,

            if(
                quarter_course_percent_grade_that_matters > 100, true, false
            ) as qt_percent_grade_greater_100,

            if(
                grade_level > 4
                and ada_above_or_at_80
                and quarter_course_grade_points_that_matters < 2.0,
                true,
                false
            ) as qt_student_is_ada_80_plus_gpa_less_2,

            if(
                assignment_category_code = 'W'
                and grade_level > 4
                and abs(
                    round(category_quarter_average_all_courses, 2)
                    - round(category_quarter_percent_grade, 2)
                )
                >= 30,
                true,
                false
            ) as w_grade_inflation,

            if(
                region = 'Miami'
                and assignment_category_code = 'W'
                and category_quarter_percent_grade is null
                and is_quarter_end_date_range,
                true,
                false
            ) as qt_effort_grade_missing,



        from grades_and_assignments
    )*/
select
    _dbt_source_relation,
    academic_year,
    academic_year_display,
    region,
    school_level,
    region_school_level,
    schoolid,
    school,

    studentid,
    student_number,
    student_name,
    grade_level,
    salesforce_id,
    ktc_cohort,
    cohort,
    gender,
    ethnicity,
    advisory,
    hos,
    year_in_school,
    year_in_network,
    rn_undergrad,
    is_out_of_district,
    is_pathways,
    is_retained_year,
    is_retained_ever,
    lunch_status,
    gifted_and_talented,
    iep_status,
    lep_status,
    is_504,
    is_counseling_services,
    is_student_athlete,
    ada,
    ada_above_or_at_80,
    tutoring_nj,
    nj_student_tier,
    date_enrolled,

    semester,
    `quarter`,
    week_number,
    quarter_start_date,
    quarter_end_date,
    cal_quarter_end_date,
    is_current_quarter,
    is_quarter_end_date_range,
    audit_due_date,

    assignment_category_name,
    assignment_category_code,
    assignment_category_term,
    expectation,
    notes,
    sectionid,
    sections_dcid,
    section_number,
    external_expression,
    section_or_period,
    credit_type,
    course_number,
    course_name,
    exclude_from_gpa,
    is_ap_course,

    teacher_number,
    teacher_name,
    tableau_username,

    category_quarter_percent_grade,
    category_quarter_average_all_courses,
    quarter_course_percent_grade_that_matters,
    quarter_course_grade_points_that_matters,
    quarter_citizenship,
    quarter_comment_value,

    teacher_assign_id,
    teacher_assign_name,
    teacher_assign_due_date,
    teacher_assign_score_type,
    teacher_assign_max_score,
    n_students,
    n_late,
    n_exempt,
    n_missing,
    n_expected,
    n_expected_scored,
    teacher_assign_count,
    teacher_running_total_assign_by_cat,
    teacher_avg_score_for_assign_per_class_section_and_assign_id,

    raw_score,
    score_entered,
    assign_final_score_percent,
    is_exempt,
    is_late,
    is_missing,

    audit_flag_name,

    'assignment_student' as cte_grouping,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from
    assignment_student unpivot (
        audit_flag_value for audit_flag_name in (
            assign_null_score,
            assign_score_above_max,
            assign_exempt_with_score,
            assign_w_score_less_5,
            assign_f_score_less_5,
            assign_w_missing_score_not_5,
            assign_f_missing_score_not_5,
            assign_s_score_less_50p,
            assign_s_ms_score_not_conversion_chart_options,
            assign_s_hs_score_not_conversion_chart_options
        )
    )
where audit_flag_value
