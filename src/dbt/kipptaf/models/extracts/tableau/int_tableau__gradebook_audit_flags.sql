{{- config(materialized="table") -}}

with
    grades_and_assignments as (
        select
            f._dbt_source_relation,
            f.academic_year,
            f.academic_year_display,
            f.region,
            f.school_level,
            f.schoolid,
            f.school,
            f.studentid,
            f.student_number,
            f.student_name,
            f.grade_level,
            f.advisory,
            f.region_school_level,
            f.ada,
            f.`quarter`,
            f.semester,
            f.quarter_start_date,
            f.quarter_end_date,
            f.cal_quarter_end_date,
            f.is_current_quarter,
            f.is_quarter_end_date_range,
            f.ada_above_or_at_80,
            f.section_or_period,
            f.expectation,
            f.sectionid,
            f.sections_dcid,
            f.section_number,
            f.external_expression,
            f.date_enrolled,
            f.credit_type,
            f.course_number,
            f.course_name,
            f.exclude_from_gpa,
            f.teacher_number,
            f.teacher_name,
            f.is_ap_course,
            f.category_quarter_percent_grade,
            f.category_quarter_average_all_courses,
            f.quarter_course_percent_grade_that_matters,
            f.quarter_course_grade_points_that_matters,
            f.quarter_citizenship,
            f.quarter_comment_value,

            t.week_number_quarter,
            t.week_start_monday,
            t.week_end_sunday,
            t.school_week_start_date_lead,
            t.assignment_category_code,
            t.assignment_category_name,
            t.assignment_category_term,
            t.assignmentid,
            t.assignment_name,
            t.duedate,
            t.scoretype,
            t.totalpointvalue,
            t.n_students,
            t.n_late,
            t.n_exempt,
            t.n_missing,
            t.n_expected,
            t.n_expected_scored,
            t.teacher_assign_count,
            t.teacher_running_total_assign_by_cat,
            t.teacher_avg_score_for_assign_per_class_section_and_assign_id,
            t.qt_teacher_s_total_greater_200,
            t.w_assign_max_score_not_10,
            t.f_assign_max_score_not_10,
            t.w_expected_assign_count_not_met,
            t.f_expected_assign_count_not_met,
            t.s_expected_assign_count_not_met,

            s.scorepoints,
            s.isexempt,
            s.islate,
            s.ismissing,
            s.assign_final_score_percent,
            s.assign_null_score,
            s.assign_score_above_max,
            s.assign_exempt_with_score,
            s.assign_w_score_less_5,
            s.assign_f_score_less_5,
            s.assign_w_missing_score_not_5,
            s.assign_f_missing_score_not_5,
            s.assign_s_score_less_50p,

            -- TODO: historical grades have letter grades on this field, so maybe we
            -- can split it for old grades and new grades?
            safe_cast(s.actualscoreentered as numeric) as actualscoreentered,

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
            and t.assignmentid = s.assignmentid
            and {{ union_dataset_join_clause(left_alias="t", right_alias="s") }}
    ),

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

            if(
                isexempt = 0
                and school_level = 'MS'
                and assignment_category_code = 'S'
                and (assign_final_score_percent)
                not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 90, 95, 100),
                true,
                false
            ) as assign_s_ms_score_not_conversion_chart_options,

            if(
                isexempt = 0
                and school_level = 'HS'
                and assignment_category_code = 'S'
                and not is_ap_course
                and (assign_final_score_percent)
                not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 93, 97, 100),
                true,
                false
            ) as assign_s_hs_score_not_conversion_chart_options,

        from grades_and_assignments
    )

select distinct
    _dbt_source_relation,
    academic_year,
    region,
    school_level,
    schoolid,
    school,
    student_number,
    student_name,
    grade_level,
    semester,
    `quarter`,
    quarter_start_date,
    quarter_end_date,
    is_current_quarter,
    course_name,
    course_number,
    section_number,
    external_expression,
    section_or_period,
    teacher_number,
    teacher_name,

    week_number_quarter as audit_qt_week_number,
    assignment_category_code as expected_teacher_assign_category_code,
    assignment_category_name as expected_teacher_assign_category_name,
    expectation as audit_category_exp_audit_week_ytd,
    assignmentid as teacher_assign_id,
    assignment_name as teacher_assign_name,
    scoretype as teacher_assign_score_type,
    totalpointvalue as teacher_assign_max_score,
    duedate as teacher_assign_due_date,
    actualscoreentered as assign_score_raw,
    scorepoints as assign_score_converted,
    totalpointvalue as assign_max_score,
    assign_final_score_percent as assign_final_score_percent,

    audit_flag_name,

    if(audit_flag_value, 1, 0) as audit_flag_value,
from
    audits unpivot (
        audit_flag_value for audit_flag_name in (
            w_assign_max_score_not_10,
            f_assign_max_score_not_10,
            s_max_score_greater_100,
            w_expected_assign_count_not_met,
            f_expected_assign_count_not_met,
            s_expected_assign_count_not_met,
            assign_s_hs_score_not_conversion_chart_options,
            assign_s_ms_score_not_conversion_chart_options,
            assign_null_score,
            assign_score_above_max,
            assign_exempt_with_score,
            assign_w_score_less_5,
            assign_f_score_less_5,
            assign_w_missing_score_not_5,
            assign_f_missing_score_not_5,
            assign_s_score_less_50p,
            qt_kg_conduct_code_missing,
            qt_kg_conduct_code_not_hr,
            qt_g1_g8_conduct_code_missing,
            qt_kg_conduct_code_incorrect,
            qt_g1_g8_conduct_code_incorrect,
            qt_grade_70_comment_missing,
            qt_comment_missing,
            qt_percent_grade_greater_100,
            qt_teacher_s_total_greater_200,
            qt_student_is_ada_80_plus_gpa_less_2,
            qt_effort_grade_missing,
            w_grade_inflation
        )
    )
where audit_flag_value
