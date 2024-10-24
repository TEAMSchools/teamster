with
    ms_hs_audits as (
        select
            f._dbt_source_relation,
            f.academic_year,
            f.region,
            f.school_level,
            f.schoolid,
            f.student_number,
            f.grade_level,
            f.region_school_level,
            f.ada_above_or_at_80,
            f.quarter,
            f.semester,
            f.quarter_start_date,
            f.quarter_end_date,
            f.is_current_quarter,
            f.sectionid,
            f.section_number,
            f.external_expression,
            f.section_or_period,
            f.credit_type,
            f.course_number,
            f.course_name,
            f.teacher_number,
            f.teacher_name,
            f.is_ap_course,
            f.date_enrolled as student_course_entry_date,
            f.quarter_course_percent_grade_that_matters,
            f.quarter_course_grade_points_that_matters,
            f.quarter_citizenship,
            f.quarter_comment_value,
            f.category_quarter_percent_grade,
            f.category_quarter_average_all_courses,
            f.is_quarter_end_date_range,

            t.week_number_quarter as audit_qt_week_number,
            t.week_start_monday as audit_start_date,
            t.week_end_sunday as audit_end_date,
            t.school_week_start_date_lead as audit_due_date,
            t.assignment_category_code as expected_teacher_assign_category_code,
            t.assignment_category_name as expected_teacher_assign_category_name,
            t.assignment_category_term as expected_teacher_assign_category_term,
            t.expectation as audit_category_exp_audit_week_ytd,
            t.assignmentid as teacher_assign_id,
            t.assignment_name as teacher_assign_name,
            t.duedate as teacher_assign_due_date,
            t.scoretype as teacher_assign_score_type,
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
            t.total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
            t.total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,
            t.total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
            t.total_expected_graded_assignments_by_course_cat_qt_audit_week,
            t.total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,
            t.total_expected_graded_assignments_by_course_assign_id_qt_audit_week,
            t.percent_graded_completion_by_cat_qt_audit_week_all_courses,
            t.percent_graded_completion_by_cat_qt_audit_week,
            t.percent_graded_completion_by_assign_id_qt_audit_week,
            t.qt_teacher_no_missing_assignments,
            t.qt_teacher_s_total_less_200,
            t.qt_teacher_s_total_greater_200,
            t.w_assign_max_score_not_10,
            t.f_assign_max_score_not_10,
            t.w_expected_assign_count_not_met,
            t.f_expected_assign_count_not_met,
            t.s_expected_assign_count_not_met,

            s.actualscoreentered as assign_score_raw,
            s.scorepoints as assign_score_converted,
            s.isexempt as assign_is_exempt,
            s.islate as assign_is_late,
            s.ismissing as assign_is_missing,
            s.assign_final_score_percent,
            s.assign_null_score,
            s.assign_score_above_max,
            s.assign_exempt_with_score,
            s.assign_w_score_less_5,
            s.assign_f_score_less_5,
            s.assign_w_missing_score_not_5,
            s.assign_f_missing_score_not_5,
            s.assign_s_score_less_50p,

            if(
                f.region = 'Miami'
                and f.expected_teacher_assign_category_code = 'S'
                and totalpointvalue > 100,
                true,
                false
            ) as s_max_score_greater_100,

            if(
                region = 'Miami'
                and is_quarter_end_date_range
                and course_name != 'HR'
                and quarter_citizenship is null,
                true,
                false
            ) as qt_g1_g8_conduct_code_missing,

            if(
                region = 'Miami'
                and is_quarter_end_date_range
                and course_name != 'HR'
                and quarter_citizenship is not null
                and quarter_citizenship not in ('A', 'B', 'C', 'D', 'E', 'F'),
                true,
                false
            ) as qt_g1_g8_conduct_code_incorrect,

            if(
                is_quarter_end_date_range
                and quarter_course_percent_grade_that_matters < 70
                and quarter_comment_value is null,
                true,
                false
            ) as qt_grade_70_comment_missing,

            if(
                quarter_course_percent_grade_that_matters > 100, true, false
            ) as qt_percent_grade_greater_100,

            if(
                expected_teacher_assign_category_code = 'W'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as w_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                expected_teacher_assign_category_code = 'F'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as f_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                expected_teacher_assign_category_code = 'S'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as s_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                ada_above_or_at_80 and quarter_course_grade_points_that_matters < 2.0,
                true,
                false
            ) as qt_student_is_ada_80_plus_gpa_less_2,

            if(
                expected_teacher_assign_category_code = 'W'
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
                and expected_teacher_assign_category_code = 'W'
                and category_quarter_percent_grade is null,
                true,
                false
            ) as qt_effort_grade_missing,

            if(
                assign_is_exempt = 0
                and school_level = 'MS'
                and expected_teacher_assign_category_code = 'S'
                and (assign_final_score_percent)
                not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 90, 95, 100),
                true,
                false
            ) as assign_s_ms_score_not_conversion_chart_options,

            if(
                assign_is_exempt = 0
                and school_level = 'HS'
                and expected_teacher_assign_category_code = 'S'
                and is_ap_course
                and (assign_final_score_percent)
                not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 93, 97, 100),
                true,
                false
            ) as assign_s_hs_score_not_conversion_chart_options,

            if(
                sum(
                    if(
                        teacher_assign_id is null
                        and student_course_entry_date >= teacher_assign_due_date - 7,
                        0,
                        1
                    )
                ) over (
                    partition by
                        _dbt_source_relation, sectionid, student_number, `quarter`
                )
                = 0,
                true,
                false
            ) as qt_assign_no_course_assignments,

        from {{ ref("rpt_tableau__gradebook_gpa") }} as f
        left join
            {{ ref("int_powerschool__teacher_assignment_audit") }} as t
            on f.sectionid = t.sectionid
            and f.quarter = t.quarter
            and f.category_name_code = t.assignment_category_code
            and {{ union_dataset_join_clause(left_alias="f", right_alias="t") }}
        left join
            {{ ref("int_powerschool__student_assignment_audit") }} as s
            on f.studentid = s.studentid
            and f.sectionid = s.sectionid
            and f.quarter = s.quarter
            and {{ union_dataset_join_clause(left_alias="f", right_alias="s") }}
            and t.week_number_quarter = s.week_number_quarter
            and t.assignmentid = s.assignmentid
            and {{ union_dataset_join_clause(left_alias="t", right_alias="s") }}
        where
            f.academic_year = {{ var("current_academic_year") }}
            and f.enroll_status = 0
            and f.roster_type = 'Local'
            and f.quarter != 'Y1'
            and f.school_level != 'ES'
    ),

    es_fl_audits as (
        select
            f._dbt_source_relation,
            f.academic_year,
            f.region,
            f.school_level,
            f.schoolid,
            f.student_number,
            f.grade_level,
            f.region_school_level,
            f.quarter,
            f.semester,
            f.quarter_start_date,
            f.quarter_end_date,
            f.is_current_quarter,
            f.sectionid,
            f.section_number,
            f.external_expression,
            f.section_or_period,
            f.credit_type,
            f.course_number,
            f.course_name,
            f.teacher_number,
            f.teacher_name,
            f.date_enrolled as student_course_entry_date,
            f.quarter_course_percent_grade_that_matters,
            f.quarter_course_grade_points_that_matters,
            f.quarter_citizenship,
            f.quarter_comment_value,
            f.category_quarter_percent_grade,
            f.category_quarter_average_all_courses,
            f.is_quarter_end_date_range,

            t.week_number_quarter as audit_qt_week_number,
            t.week_start_monday as audit_start_date,
            t.week_end_sunday as audit_end_date,
            t.school_week_start_date_lead as audit_due_date,
            t.assignment_category_code as expected_teacher_assign_category_code,
            t.assignment_category_name as expected_teacher_assign_category_name,
            t.assignment_category_term as expected_teacher_assign_category_term,
            t.expectation as audit_category_exp_audit_week_ytd,
            t.assignmentid as teacher_assign_id,
            t.assignment_name as teacher_assign_name,
            t.duedate as teacher_assign_due_date,
            t.scoretype as teacher_assign_score_type,
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
            t.total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
            t.total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,
            t.total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
            t.total_expected_graded_assignments_by_course_cat_qt_audit_week,
            t.total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,
            t.total_expected_graded_assignments_by_course_assign_id_qt_audit_week,
            t.percent_graded_completion_by_cat_qt_audit_week_all_courses,
            t.percent_graded_completion_by_cat_qt_audit_week,
            t.percent_graded_completion_by_assign_id_qt_audit_week,
            t.qt_teacher_no_missing_assignments,
            t.qt_teacher_s_total_less_200,
            t.qt_teacher_s_total_greater_200,
            t.w_assign_max_score_not_10,
            t.f_assign_max_score_not_10,
            t.w_expected_assign_count_not_met,
            t.f_expected_assign_count_not_met,
            t.s_expected_assign_count_not_met,

            s.actualscoreentered as assign_score_raw,
            s.scorepoints as assign_score_converted,
            s.isexempt as assign_is_exempt,
            s.islate as assign_is_late,
            s.ismissing as assign_is_missing,
            s.assign_final_score_percent,
            s.assign_null_score,
            s.assign_score_above_max,
            s.assign_exempt_with_score,
            s.assign_w_score_less_5,
            s.assign_f_score_less_5,
            s.assign_w_missing_score_not_5,
            s.assign_f_missing_score_not_5,
            s.assign_s_score_less_50p,

            if(
                region = 'Miami'
                and expected_teacher_assign_category_code = 'S'
                and totalpointvalue > 100,
                true,
                false
            ) as s_max_score_greater_100,

            if(
                region = 'Miami'
                and is_quarter_end_date_range
                and grade_level = 0
                and course_name != 'HR'
                and quarter_citizenship is not null,
                true,
                false
            ) as qt_kg_conduct_code_not_hr,

            case
                when region = 'Miami'
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
                region = 'Miami'
                and grade_level < 5
                and is_quarter_end_date_range
                and quarter_comment_value is null,
                true,
                false
            ) as qt_comment_missing,

            if(
                quarter_course_percent_grade_that_matters > 100, true, false
            ) as qt_percent_grade_greater_100,

            if(
                expected_teacher_assign_category_code = 'W'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as w_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                expected_teacher_assign_category_code = 'F'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as f_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                expected_teacher_assign_category_code = 'S'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as s_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                region = 'Miami'
                and expected_teacher_assign_category_code = 'W'
                and category_quarter_percent_grade is null,
                true,
                false
            ) as qt_effort_grade_missing,

            if(
                sum(
                    if(
                        teacher_assign_id is null
                        and student_course_entry_date >= teacher_assign_due_date - 7,
                        0,
                        1
                    )
                ) over (
                    partition by
                        _dbt_source_relation, sectionid, student_number, `quarter`
                )
                = 0,
                true,
                false
            ) as qt_assign_no_course_assignments,

        from {{ ref("rpt_tableau__gradebook_gpa") }} as f
        left join
            {{ ref("int_powerschool__teacher_assignment_audit") }} as t
            on f.sectionid = t.sectionid
            and f.quarter = t.quarter
            and f.category_name_code = t.assignment_category_code
            and {{ union_dataset_join_clause(left_alias="f", right_alias="t") }}
        left join
            {{ ref("int_powerschool__student_assignment_audit") }} as s
            on f.studentid = s.studentid
            and f.sectionid = s.sectionid
            and f.quarter = s.quarter
            and {{ union_dataset_join_clause(left_alias="f", right_alias="s") }}
            and t.week_number_quarter = s.week_number_quarter
            and t.assignmentid = s.assignmentid
            and {{ union_dataset_join_clause(left_alias="t", right_alias="s") }}
        where
            f.academic_year = {{ var("current_academic_year") }}
            and f.enroll_status = 0
            and f.roster_type = 'Local'
            and f.quarter != 'Y1'
            and f.school_level = 'ES'
            and f.region = 'Miami'
    ),

    es_nj_audits as (
        select
            f._dbt_source_relation,
            f.academic_year,
            f.region,
            f.school_level,
            f.schoolid,
            f.student_number,
            f.grade_level,
            f.region_school_level,
            f.quarter,
            f.semester,
            f.quarter_start_date,
            f.quarter_end_date,
            f.is_current_quarter,
            f.sectionid,
            f.section_number,
            f.external_expression,
            f.section_or_period,
            f.credit_type,
            f.course_number,
            f.course_name,
            f.teacher_number,
            f.teacher_name,
            f.date_enrolled as student_course_entry_date,
            f.quarter_comment_value,
            f.is_quarter_end_date_range,

            t.week_number_quarter as audit_qt_week_number,
            t.week_start_monday as audit_start_date,
            t.week_end_sunday as audit_end_date,
            t.school_week_start_date_lead as audit_due_date,

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
                region != 'Miami'
                and is_quarter_end_date_range
                and grade_level < 5
                and credit_type in ('MATH', 'ENG', 'HR')
                and quarter_comment_value is null,
                true,
                false
            ) as qt_es_comment_missing,

            if(
                region = 'Miami'
                and grade_level < 5
                and is_quarter_end_date_range
                and quarter_comment_value is null,
                true,
                false
            ) as qt_comment_missing,

            if(
                quarter_course_percent_grade_that_matters > 100, true, false
            ) as qt_percent_grade_greater_100,

            if(
                expected_teacher_assign_category_code = 'W'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as w_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                expected_teacher_assign_category_code = 'F'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as f_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                expected_teacher_assign_category_code = 'S'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as s_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                grade_level > 4
                and ada_above_or_at_80
                and quarter_course_grade_points_that_matters < 2.0,
                true,
                false
            ) as qt_student_is_ada_80_plus_gpa_less_2,

            if(
                expected_teacher_assign_category_code = 'W'
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
                and expected_teacher_assign_category_code = 'W'
                and category_quarter_percent_grade is null,
                true,
                false
            ) as qt_effort_grade_missing,

            if(
                assign_is_exempt = 0
                and school_level = 'MS'
                and expected_teacher_assign_category_code = 'S'
                and (assign_final_score_percent)
                not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 90, 95, 100),
                true,
                false
            ) as assign_s_ms_score_not_conversion_chart_options,

            if(
                assign_is_exempt = 0
                and school_level = 'HS'
                and expected_teacher_assign_category_code = 'S'
                and is_ap_course
                and (assign_final_score_percent)
                not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 93, 97, 100),
                true,
                false
            ) as assign_s_hs_score_not_conversion_chart_options,

            if(
                region_school_level not in ('CamdenES', 'NewarkES')
                and sum(
                    if(
                        teacher_assign_id is null
                        and student_course_entry_date >= teacher_assign_due_date - 7,
                        0,
                        1
                    )
                ) over (
                    partition by
                        _dbt_source_relation, sectionid, student_number, `quarter`
                )
                = 0,
                true,
                false
            ) as qt_assign_no_course_assignments,

        from {{ ref("rpt_tableau__gradebook_gpa") }} as f
        left join
            {{ ref("int_powerschool__teacher_assignment_audit") }} as t
            on f.sectionid = t.sectionid
            and f.quarter = t.quarter
            and f.category_name_code = t.assignment_category_code
            and {{ union_dataset_join_clause(left_alias="f", right_alias="t") }}
        where
            f.academic_year = {{ var("current_academic_year") }}
            and f.enroll_status = 0
            and f.roster_type = 'Local'
            and f.quarter != 'Y1'
            and f.school_level = 'ES'
            and f.region != 'Miami'
    )

    audits as (
        select
            *,

            if(
                region = 'Miami'
                and expected_teacher_assign_category_code = 'S'
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
                region != 'Miami'
                and is_quarter_end_date_range
                and grade_level < 5
                and credit_type in ('MATH', 'ENG', 'HR')
                and quarter_comment_value is null,
                true,
                false
            ) as qt_es_comment_missing,

            if(
                region = 'Miami'
                and grade_level < 5
                and is_quarter_end_date_range
                and quarter_comment_value is null,
                true,
                false
            ) as qt_comment_missing,

            if(
                quarter_course_percent_grade_that_matters > 100, true, false
            ) as qt_percent_grade_greater_100,

            if(
                expected_teacher_assign_category_code = 'W'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as w_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                expected_teacher_assign_category_code = 'F'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as f_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                expected_teacher_assign_category_code = 'S'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as s_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                grade_level > 4
                and ada_above_or_at_80
                and quarter_course_grade_points_that_matters < 2.0,
                true,
                false
            ) as qt_student_is_ada_80_plus_gpa_less_2,

            if(
                expected_teacher_assign_category_code = 'W'
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
                and expected_teacher_assign_category_code = 'W'
                and category_quarter_percent_grade is null,
                true,
                false
            ) as qt_effort_grade_missing,

            if(
                assign_is_exempt = 0
                and school_level = 'MS'
                and expected_teacher_assign_category_code = 'S'
                and (assign_final_score_percent)
                not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 90, 95, 100),
                true,
                false
            ) as assign_s_ms_score_not_conversion_chart_options,

            if(
                assign_is_exempt = 0
                and school_level = 'HS'
                and expected_teacher_assign_category_code = 'S'
                and is_ap_course
                and (assign_final_score_percent)
                not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 93, 97, 100),
                true,
                false
            ) as assign_s_hs_score_not_conversion_chart_options,

            if(
                region_school_level not in ('CamdenES', 'NewarkES')
                and sum(
                    if(
                        teacher_assign_id is null
                        and student_course_entry_date >= teacher_assign_due_date - 7,
                        0,
                        1
                    )
                ) over (
                    partition by
                        _dbt_source_relation, sectionid, student_number, `quarter`
                )
                = 0,
                true,
                false
            ) as qt_assign_no_course_assignments,
        from grades_and_assignments
    ),

    unpivot_flags_only as (
        select
            _dbt_source_relation,
            student_number,
            academic_year,
            region,
            school_level,
            schoolid,
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
            credit_type,
            teacher_number,
            teacher_name,
            exclude_from_gpa,
            quarter_course_percent_grade_that_matters,
            quarter_course_grade_points_that_matters,
            quarter_citizenship,
            quarter_comment_value,
            category_quarter_percent_grade,
            category_quarter_average_all_courses,
            audit_qt_week_number,
            audit_start_date,
            audit_end_date,
            audit_due_date,
            expected_teacher_assign_category_code,
            expected_teacher_assign_category_name,
            expected_teacher_assign_category_term,
            audit_category_exp_audit_week_ytd,
            teacher_assign_id,
            teacher_assign_name,
            teacher_assign_score_type,
            totalpointvalue as teacher_assign_max_score,
            teacher_assign_due_date,
            teacher_assign_count,
            n_students,
            n_late,
            n_exempt,
            n_missing,
            n_expected,
            n_expected_scored,
            teacher_running_total_assign_by_cat,
            teacher_avg_score_for_assign_per_class_section_and_assign_id,
            total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
            total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,
            total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
            total_expected_graded_assignments_by_course_cat_qt_audit_week,
            total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,
            total_expected_graded_assignments_by_course_assign_id_qt_audit_week,
            percent_graded_completion_by_cat_qt_audit_week_all_courses,
            percent_graded_completion_by_cat_qt_audit_week,
            percent_graded_completion_by_assign_id_qt_audit_week,

            qt_teacher_no_missing_assignments,
            qt_teacher_s_total_less_200,
            assign_score_raw,
            assign_score_converted,
            totalpointvalue as assign_max_score,
            assign_final_score_percent,
            assign_is_exempt,
            assign_is_late,
            assign_is_missing,

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
                    w_percent_graded_completion_by_qt_audit_week_not_100,
                    f_percent_graded_completion_by_qt_audit_week_not_100,
                    s_percent_graded_completion_by_qt_audit_week_not_100,
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
                    qt_assign_no_course_assignments,
                    qt_kg_conduct_code_missing,
                    qt_kg_conduct_code_not_hr,
                    qt_g1_g8_conduct_code_missing,
                    qt_kg_conduct_code_incorrect,
                    qt_g1_g8_conduct_code_incorrect,
                    qt_grade_70_comment_missing,
                    qt_es_comment_missing,
                    qt_comment_missing,
                    qt_percent_grade_greater_100,
                    qt_teacher_s_total_greater_200,
                    qt_student_is_ada_80_plus_gpa_less_2,
                    qt_effort_grade_missing,
                    w_grade_inflation
                )
            )
        where audit_flag_value
    )

/* categories for ms/hs nj and fl */
select
    *,

    case
        when
            audit_flag_name in (
                'w_assign_max_score_not_10',
                'f_assign_max_score_not_10',
                's_max_score_greater_100',
                'qt_teacher_s_total_greater_200'
            )
        then 'Setup'
        when
            audit_flag_name in (
                'assign_null_score',
                'assign_score_above_max',
                'assign_exempt_with_score',
                'assign_w_score_less_5',
                'assign_f_score_less_5',
                'assign_w_missing_score_not_5',
                'assign_f_missing_score_not_5',
                'assign_s_score_less_50p',
                'assign_s_ms_score_not_conversion_chart_options',
                'assign_s_hs_score_not_conversion_chart_options',
                'qt_assign_no_course_assignments',
                'qt_percent_grade_greater_100'
            )
        then 'Data Entry'
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100'
            )
        then 'Updated'
        when
            audit_flag_name
            in ('w_grade_inflation', 'qt_student_is_ada_80_plus_gpa_less_2')
        then 'Health'
        when
            audit_flag_name in (
                'qt_g1_g8_conduct_code_missing',
                'qt_kg_conduct_code_incorrect',
                'qt_g1_g8_conduct_code_incorrect',
                'qt_grade_70_comment_missing',
                'qt_effort_grade_missing'
            )
        then 'EOQ Gradebook Process'
        else 'Need to categorize'
    end as gradebook_audit_category,
from unpivot_flags_only
where school_level != 'ES'

union all

/* categories for fl es */
select
    *,

    case
        when
            audit_flag_name in (
                'w_assign_max_score_not_10',
                'f_assign_max_score_not_10',
                's_max_score_greater_100',
                'qt_teacher_s_total_greater_200',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then 'Setup'
        when
            audit_flag_name in (
                'assign_null_score',
                'assign_score_above_max',
                'assign_exempt_with_score',
                'assign_w_score_less_5',
                'assign_f_score_less_5',
                'assign_w_missing_score_not_5',
                'assign_f_missing_score_not_5',
                'assign_s_score_less_50p',
                'qt_assign_no_course_assignments',
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'qt_percent_grade_greater_100'
            )
        then 'Data Entry'
        when audit_flag_name = 'qt_comment_missing'
        then 'Comments'
        when
            audit_flag_name in (
                'qt_kg_conduct_code_missing',
                'qt_kg_conduct_code_not_hr',
                'qt_kg_conduct_code_incorrect',
                'qt_g1_g8_conduct_code_missing',
                'qt_g1_g8_conduct_code_incorrect'
            )
        then 'Conduct Code'
        when audit_flag_name = 'qt_effort_grade_missing'
        then 'Effort Grade'
        else 'Need to categorize'
    end as gradebook_audit_category,
from unpivot_flags_only
where school_level = 'ES' and region = 'Miami'

union all

/* categories for nj es */
select *, 'Comments' as gradebook_audit_category,
from unpivot_flags_only
where
    school_level = 'ES'
    and audit_flag_name = 'qt_es_comment_missing'
    and region != 'Miami'
