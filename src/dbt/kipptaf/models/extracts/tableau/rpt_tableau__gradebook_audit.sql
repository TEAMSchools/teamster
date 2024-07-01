with
    grades_and_assignments as (
        select
            f._dbt_source_relation,
            f.studentid,
            f.student_number,
            f.salesforce_id,
            f.lastfirst,
            f.enroll_status,
            f.cohort,
            f.ktc_cohort,
            f.gender,
            f.ethnicity,

            f.academic_year,
            f.region,
            f.school_level,
            f.schoolid,
            f.school,
            f.grade_level,
            f.advisory,
            f.advisor_name,
            f.hos,
            f.region_school_level,

            f.year_in_school,
            f.year_in_network,
            f.rn_undergrad,
            f.is_out_of_district,
            f.is_pathways,
            f.is_retained_year,
            f.is_retained_ever,
            f.lunch_status,
            f.iep_status,
            f.lep_status,
            f.is_504,
            f.is_counseling_services,
            f.is_student_athlete,

            f.ada,
            f.ada_above_or_at_80,

            f.quarter,
            f.semester,
            f.quarter_start_date,
            f.quarter_end_date,
            f.is_current_quarter,

            f.sectionid,
            f.sections_dcid,
            f.section_number,
            f.external_expression,
            f.section_or_period,
            f.date_enrolled,
            f.credit_type,
            f.course_number,
            f.course_name,
            f.exclude_from_gpa,
            f.teacher_number,
            f.teacher_name,
            f.tableau_username,
            f.tutoring_nj,
            f.nj_student_tier,
            f.is_ap_course,

            f.quarter_course_percent_grade_that_matters,
            f.quarter_course_letter_grade_that_matters,
            f.quarter_course_grade_points_that_matters,

            f.y1_course_in_progress_percent_grade,
            f.y1_course_in_progress_percent_grade_adjusted,
            f.y1_course_in_progress_letter_grade,
            f.y1_course_in_progress_letter_grade_adjusted,
            f.y1_course_in_progress_grade_points,
            f.y1_course_in_progress_grade_points_unweighted,

            f.quarter_citizenship,
            f.quarter_comment_value,

            f.category_name_code,
            f.category_quarter_code,
            f.category_quarter_percent_grade,
            f.category_y1_percent_grade_running,
            f.category_y1_percent_grade_current,
            f.category_quarter_average_all_courses,

            t.week_number_quarter,
            t.week_start_date,
            t.week_end_date,
            t.school_week_start_date_lead,

            t.assignment_category_code,
            t.assignment_category_name,
            t.assignment_category_term,
            t.expectation,

            t.assignmentid,
            t.assignment_name,
            t.duedate,
            t.scoretype,
            t.totalpointvalue,

            t.teacher_assign_count,
            t.teacher_running_total_assign_by_cat,
            t.teacher_avg_score_for_assign_per_class_section_and_assign_id,
            t.total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
            t.total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,
            t.total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
            t.total_expected_graded_assignments_by_course_cat_qt_audit_week,
            -- trunk-ignore(sqlfluff/LT05)
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

            s.scorepoints,
            s.score_converted,
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

            if(
                current_date('{{ var("local_timezone") }}')
                between (f.quarter_end_date - 7) and (f.quarter_end_date + 30),
                true,
                false
            ) as is_quarter_end_date_range,
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
            and f.roster_type = 'Local'
            and f.quarter != 'Y1'
            and f.region_school_level not in ('ESCamden', 'ESNewark')
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
                region != 'Miami'
                and is_quarter_end_date_range
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
                and (course_name = 'HR' or credit_type in ('MATH', 'ENG'))
                and quarter_comment_value is null,
                true,
                false
            ) as qt_es_comment_missing,

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
                assignment_category_code = 'W'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as w_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                assignment_category_code = 'F'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                true,
                false
            ) as f_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                assignment_category_code = 'S'
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
                region = 'Miami' and category_quarter_percent_grade is null, true, false
            ) as qt_category_grade_missing,

            if(
                isexempt = 0
                and school_level = 'MS'
                and assignment_category_code = 'S'
                and (assign_final_score_percent * 100)
                not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 90, 95, 100),
                true,
                false
            ) as assign_s_ms_score_not_conversion_chart_options,

            if(
                isexempt = 0
                and school_level = 'HS'
                and assignment_category_code = 'S'
                and is_ap_course
                and (assign_final_score_percent * 100)
                not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 93, 97, 100),
                true,
                false
            ) as assign_s_hs_score_not_conversion_chart_options,

            if(
                region_school_level not in ('CamdenES', 'NewarkES')
                and sum(
                    if(assignmentid is null and date_enrolled >= duedate - 7, 0, 1)
                ) over (
                    partition by
                        _dbt_source_relation, sectionid, student_number, `quarter`
                )
                = 0,
                true,
                false
            ) as qt_assign_no_course_assignments,
        from grades_and_assignments
    )

select
    _dbt_source_relation,
    academic_year,
    region,
    school_level,
    schoolid,
    school,
    student_number,
    lastfirst,
    gender,
    grade_level,
    ethnicity,
    lep_status,
    is_504,
    is_pathways,
    iep_status,
    is_counseling_services,
    is_student_athlete,
    tutoring_nj,
    nj_student_tier,
    ada,
    ada_above_or_at_80,
    advisory,
    advisor_name,
    hos,
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
    tableau_username,
    exclude_from_gpa,
    quarter_course_percent_grade_that_matters,
    quarter_course_grade_points_that_matters,
    quarter_citizenship,
    quarter_comment_value,
    category_quarter_percent_grade,
    category_quarter_average_all_courses,
    week_number_quarter as audit_qt_week_number,
    week_start_date as audit_start_date,
    week_end_date as audit_end_date,
    school_week_start_date_lead as audit_due_date,
    assignment_category_code as expected_teacher_assign_category_code,
    assignment_category_name as expected_teacher_assign_category_name,
    expectation as audit_category_exp_audit_week_ytd,
    assignmentid as teacher_assign_id,
    assignment_name as teacher_assign_name,
    scoretype as teacher_assign_score_type,
    totalpointvalue as teacher_assign_max_score,
    duedate as teacher_assign_due_date,
    teacher_assign_count,
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
    date_enrolled as student_course_entry_date,
    scorepoints as assign_score_raw,
    score_converted as assign_score_converted,
    totalpointvalue as assign_max_score,
    assign_final_score_percent,
    isexempt as assign_is_exempt,
    islate as assign_is_late,
    ismissing as assign_is_missing,

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
            w_grade_inflation
        )
    )
where audit_flag_value
