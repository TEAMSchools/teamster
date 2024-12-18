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
            f.salesforce_id,
            f.ktc_cohort,
            f.enroll_status,
            f.cohort,
            f.gender,
            f.ethnicity,
            f.advisory,
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
            f.gifted_and_talented,
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
            f.quarter_course_grade_points_that_matters,
            f.quarter_citizenship,
            f.quarter_comment_value,
            f.category_name_code,
            f.category_quarter_code,
            f.category_quarter_percent_grade,
            f.category_quarter_average_all_courses,

            t.week_number_quarter,
            t.week_start_monday,
            t.week_end_sunday,
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

            if(
                current_date('{{ var("local_timezone") }}')
                between (f.quarter_end_date - 4) and (f.quarter_end_date + 14),
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
            and f.enroll_status = 0
            and f.roster_type = 'Local'
            and f.quarter != 'Y1'
            and f.region_school_level not in ('CamdenES', 'NewarkES')
    ),

    audits_non_es_nj as (
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

select distinct
    _dbt_source_relation,
    academic_year,
    academic_year_display,
    region,
    school_level,
    schoolid,
    school,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else student_number
    end as student_number,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else student_name
    end as student_name,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else gender
    end as gender,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else grade_level
    end as grade_level,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else enroll_status
    end as enroll_status,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else ethnicity
    end as ethnicity,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else lep_status
    end as lep_status,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else is_504
    end as is_504,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else is_pathways
    end as is_pathways,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else iep_status
    end as iep_status,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else gifted_and_talented
    end as gifted_and_talented,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else is_counseling_services
    end as is_counseling_services,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else is_student_athlete
    end as is_student_athlete,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else tutoring_nj
    end as tutoring_nj,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else nj_student_tier
    end as nj_student_tier,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else ada
    end as ada,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else ada_above_or_at_80
    end as ada_above_or_at_80,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else advisory
    end as advisory,
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
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else quarter_course_percent_grade_that_matters
    end as quarter_course_percent_grade_that_matters,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met'
            )
        then null
        else quarter_course_grade_points_that_matters
    end as quarter_course_grade_points_that_matters,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2'
            )
        then null
        else quarter_citizenship
    end as quarter_citizenship,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2'
            )
        then null
        else quarter_comment_value
    end as quarter_comment_value,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2'
            )
        then null
        else category_quarter_percent_grade
    end as category_quarter_percent_grade,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2'
            )
        then null
        else category_quarter_average_all_courses
    end as category_quarter_average_all_courses,
    week_number_quarter as audit_qt_week_number,
    week_start_monday as audit_start_date,
    week_end_sunday as audit_end_date,
    school_week_start_date_lead as audit_due_date,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else assignment_category_code
    end as expected_teacher_assign_category_code,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else assignment_category_name
    end as expected_teacher_assign_category_name,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else expectation
    end as audit_category_exp_audit_week_ytd,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2',
                'w_grade_inflation',
                'qt_effort_grade_missing'
            )
        then null
        else assignmentid
    end as teacher_assign_id,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2',
                'w_grade_inflation',
                'qt_effort_grade_missing'
            )
        then null
        else assignment_name
    end as teacher_assign_name,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2',
                'w_grade_inflation',
                'qt_effort_grade_missing'
            )
        then null
        else scoretype
    end as teacher_assign_score_type,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2',
                'w_grade_inflation',
                'qt_effort_grade_missing'
            )
        then null
        else totalpointvalue
    end as teacher_assign_max_score,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2',
                'w_grade_inflation',
                'qt_effort_grade_missing'
            )
        then null
        else duedate
    end as teacher_assign_due_date,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else teacher_assign_count
    end as teacher_assign_count,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else n_students
    end as n_students,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else n_late
    end as n_late,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else n_exempt
    end as n_exempt,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else n_missing
    end as n_missing,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else n_expected
    end as n_expected,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else n_expected_scored
    end as n_expected_scored,

    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else teacher_running_total_assign_by_cat
    end as teacher_running_total_assign_by_cat,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else teacher_avg_score_for_assign_per_class_section_and_assign_id
    end as teacher_avg_score_for_assign_per_class_section_and_assign_id,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses
    end as total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else total_expected_graded_assignments_by_cat_qt_audit_week_all_courses
    end as total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else total_expected_actual_graded_assignments_by_course_cat_qt_audit_week
    end as total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else total_expected_graded_assignments_by_course_cat_qt_audit_week
    end as total_expected_graded_assignments_by_course_cat_qt_audit_week,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week
    end as total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else total_expected_graded_assignments_by_course_assign_id_qt_audit_week
    end as total_expected_graded_assignments_by_course_assign_id_qt_audit_week,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else percent_graded_completion_by_cat_qt_audit_week_all_courses
    end as percent_graded_completion_by_cat_qt_audit_week_all_courses,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else percent_graded_completion_by_cat_qt_audit_week
    end as percent_graded_completion_by_cat_qt_audit_week,
    case
        when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
        then null
        else percent_graded_completion_by_assign_id_qt_audit_week
    end as percent_graded_completion_by_assign_id_qt_audit_week,

    qt_teacher_no_missing_assignments,
    qt_teacher_s_total_less_200,

    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2'
            )
        then null
        else date_enrolled
    end as student_course_entry_date,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2',
                'w_grade_inflation'
            )
        then null
        else actualscoreentered
    end as assign_score_raw,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2',
                'w_grade_inflation'
            )
        then null
        else scorepoints
    end as assign_score_converted,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2',
                'w_grade_inflation'
            )
        then null
        else totalpointvalue
    end as assign_max_score,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2',
                'w_grade_inflation'
            )
        then null
        else assign_final_score_percent
    end as assign_final_score_percent,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2',
                'w_grade_inflation'
            )
        then null
        else isexempt
    end as assign_is_exempt,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2',
                'w_grade_inflation'
            )
        then null
        else islate
    end as assign_is_late,
    case
        when
            audit_flag_name in (
                'w_percent_graded_completion_by_qt_audit_week_not_100',
                'f_percent_graded_completion_by_qt_audit_week_not_100',
                's_percent_graded_completion_by_qt_audit_week_not_100',
                'w_expected_assign_count_not_met',
                'f_expected_assign_count_not_met',
                's_expected_assign_count_not_met',
                'qt_student_is_ada_80_plus_gpa_less_2',
                'w_grade_inflation'
            )
        then null
        else ismissing
    end as assign_is_missing,
    audit_flag_name,

    if(audit_flag_value, 1, 0) as audit_flag_value,
from
    audits_non_es_nj unpivot (
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
            qt_comment_missing,
            qt_percent_grade_greater_100,
            qt_teacher_s_total_greater_200,
            qt_student_is_ada_80_plus_gpa_less_2,
            qt_effort_grade_missing,
            w_grade_inflation
        )
    )
where audit_flag_value

union all

select *
from {{ ref("rpt_tableau__gradebook_audit_nj_es") }}
