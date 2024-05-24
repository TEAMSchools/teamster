with
    teacher_unpivot_flags as (
        select distinct
            _dbt_source_relation,
            yearid,
            academic_year,
            region,
            schoolid,
            school_level,
            teacher_number,
            teacher_name,
            course_number,
            `section`,
            sectionid,
            sections_dcid,
            teacher_quarter,
            expected_teacher_assign_category_code,
            expected_teacher_assign_category_name,
            year_week_number,
            quarter_week_number,
            audit_start_date,
            audit_end_date,
            audit_due_date,
            audit_category_exp_audit_week_ytd,
            teacher_assign_id,
            teacher_assign_name,
            teacher_assign_score_type,
            teacher_assign_max_score,
            teacher_assign_due_date,
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

            teacher_flag_name,
            teacher_flag_value,
        from
            {{ ref("int_powerschool__teacher_assignments") }} unpivot (
                teacher_flag_value for teacher_flag_name in (
                    qt_teacher_no_missing_assignments,
                    qt_teacher_s_total_less_200,
                    qt_teacher_s_total_greater_200,
                    w_assign_max_score_not_10,
                    f_assign_max_score_not_10,
                    s_max_score_greater_100,
                    w_expected_assign_count_not_met,
                    f_expected_assign_count_not_met,
                    s_expected_assign_count_not_met
                )
            )
        where
            teacher_flag_value = 1
            and concat(
                expected_teacher_assign_category_code,
                teacher_flag_name
            ) not in (
                'Wqt_eacher_s_total_greater_200',
                'Wqt_teacher_s_total_less_200',
                'Fqt_teacher_s_total_greater_200',
                'Fqt_eacher_s_total_less_200'
            )
    )

select distinct
    _dbt_source_relation,
    yearid,
    academic_year,
    region,
    schoolid,
    school_level,
    teacher_number,
    teacher_name,
    course_number,
    `section`,
    sectionid,
    sections_dcid,
    teacher_quarter,
    expected_teacher_assign_category_code,
    expected_teacher_assign_category_name,
    year_week_number,
    quarter_week_number,
    audit_start_date,
    audit_end_date,
    audit_due_date,
    audit_category_exp_audit_week_ytd,
    teacher_assign_id,
    teacher_assign_name,
    teacher_assign_score_type,
    teacher_assign_max_score,
    teacher_assign_due_date,
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
    qt_teacher_s_total_greater_200,
    w_assign_max_score_not_10,
    f_assign_max_score_not_10,
    s_max_score_greater_100,
    w_expected_assign_count_not_met,
    f_expected_assign_count_not_met,
    s_expected_assign_count_not_met

from
    teacher_unpivot_flags pivot (
        max(teacher_flag_value) for teacher_flag_name in (
            'qt_teacher_no_missing_assignments',
            'qt_teacher_s_total_less_200',
            'qt_teacher_s_total_greater_200',
            'w_assign_max_score_not_10',
            'f_assign_max_score_not_10',
            's_max_score_greater_100',
            'w_expected_assign_count_not_met',
            'f_expected_assign_count_not_met',
            's_expected_assign_count_not_met'
        )
    )
