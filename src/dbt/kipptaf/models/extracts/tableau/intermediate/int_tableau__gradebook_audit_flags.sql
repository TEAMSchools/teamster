with
    student_unpivot as (
        select
            *,

            case
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
                        'assign_s_hs_score_not_conversion_chart_options'
                    )
                then 'assignment_student'
                when audit_flag_name in ('w_grade_inflation', 'qt_effort_grade_missing')
                then 'student_course_category'
                when
                    audit_flag_name in (
                        'qt_comment_missing',
                        'qt_g1_g8_conduct_code_incorrect',
                        'qt_g1_g8_conduct_code_missing',
                        'qt_grade_70_comment_missing',
                        'qt_kg_conduct_code_incorrect',
                        'qt_kg_conduct_code_missing',
                        'qt_kg_conduct_code_not_hr',
                        'qt_percent_grade_greater_100'
                    )
                then 'student_course'
                when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
                then 'student'
            end as cte_grouping,
        from
            {{ ref("int_tableau__gradebook_audit_assignments_student") }} unpivot (
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
                    assign_s_hs_score_not_conversion_chart_options,
                    w_grade_inflation,
                    qt_effort_grade_missing,
                    qt_comment_missing,
                    qt_g1_g8_conduct_code_incorrect,
                    qt_g1_g8_conduct_code_missing,
                    qt_grade_70_comment_missing,
                    qt_kg_conduct_code_incorrect,
                    qt_kg_conduct_code_missing,
                    qt_kg_conduct_code_not_hr,
                    qt_percent_grade_greater_100,
                    qt_student_is_ada_80_plus_gpa_less_2
                )
            )
    ),

    teacher_unpivot as (
        select
            *,

            case
                when
                    audit_flag_name in (
                        'w_assign_max_score_not_10',
                        'f_assign_max_score_not_10',
                        's_max_score_greater_100'
                    )
                then 'class_category_assignment'
                when
                    audit_flag_name in (
                        'qt_teacher_s_total_greater_200',
                        'w_expected_assign_count_not_met',
                        'f_expected_assign_count_not_met',
                        's_expected_assign_count_not_met'
                    )
                then 'class_category'
            end as cte_grouping,
        from
            {{ ref("int_tableau__gradebook_audit_assignments_teacher") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    w_assign_max_score_not_10,
                    f_assign_max_score_not_10,
                    s_max_score_greater_100,
                    qt_teacher_s_total_greater_200,
                    w_expected_assign_count_not_met,
                    f_expected_assign_count_not_met,
                    s_expected_assign_count_not_met
                )
            )
    )

select
    r._dbt_source_relation,
    r.student_number,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,
    r.grade_level,
    r.ada,
    r.ada_above_or_at_80,
    r.date_enrolled,
    r.sectionid,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    r.section_or_period,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    r.is_ap_course,
    r.teacher_number,
    r.teacher_name,
    r.semester,
    r.quarter,
    r.quarter_start_date,
    r.quarter_end_date,
    r.quarter_end_date as cal_quarter_end_date,
    r.is_current_term as is_current_quarter,
    r.is_quarter_end_date_range,
    r.week_number_quarter as week_number,
    r.week_start_date as audit_start_date,
    r.week_end_date as audit_end_date,
    r.school_week_start_date_lead as audit_due_date,
    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.category_quarter_percent_grade,
    r.category_quarter_average_all_courses,
    r.quarter_course_percent_grade_that_matters,
    r.quarter_course_grade_points_that_matters,
    r.quarter_citizenship,
    r.quarter_comment_value,
    r.assignmentid as teacher_assign_id,
    r.assignment_name as teacher_assign_name,
    r.duedate as teacher_assign_due_date,
    r.scoretype as teacher_assign_score_type,
    r.totalpointvalue as teacher_assign_max_score,
    r.scorepoints as raw_score,
    r.score_entered,
    r.assign_final_score_percent,
    r.is_exempt,
    r.is_late,
    r.is_missing,

    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_expected,
    null as n_expected_scored,
    null as teacher_assign_count,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    r.audit_flag_name,
    r.cte_grouping,

    f.audit_category,

    1 as audit_flag_value,
from student_unpivot as r
left join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.assignment_category_code = f.code
    and r.audit_flag_name = f.audit_flag_name
where r.audit_flag_value

union all

select
    r._dbt_source_relation,

    null as student_number,

    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    null as grade_level,
    null as ada,
    null as ada_above_or_at_80,
    null as date_enrolled,

    r.sectionid,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    r.section_or_period,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    r.is_ap_course,
    r.teacher_number,
    r.teacher_name,
    r.semester,
    r.quarter,
    r.quarter_start_date,
    r.quarter_end_date,
    r.quarter_end_date as cal_quarter_end_date,
    r.is_current_term as is_current_quarter,
    r.is_quarter_end_date_range,
    r.week_number_quarter as week_number,
    r.week_start_date as audit_start_date,
    r.week_end_date as audit_end_date,
    r.school_week_start_date_lead as audit_due_date,
    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
    null as quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    null as quarter_citizenship,
    null as quarter_comment_value,

    r.assignmentid as teacher_assign_id,
    r.assignment_name as teacher_assign_name,
    r.duedate as teacher_assign_due_date,
    r.scoretype as teacher_assign_score_type,
    r.totalpointvalue as teacher_assign_max_score,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,

    r.n_students,
    r.n_late,
    r.n_exempt,
    r.n_missing,
    r.n_expected,
    r.n_expected_scored,
    r.teacher_assign_count,
    r.running_count_assignments_section_category_term
    as teacher_running_total_assign_by_cat,
    r.avg_expected_scored_percent
    as teacher_avg_score_for_assign_per_class_section_and_assign_id,
    r.audit_flag_name,
    r.cte_grouping,

    f.audit_category,

    1 as audit_flag_value,
from teacher_unpivot as r
left join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.assignment_category_code = f.code
    and r.audit_flag_name = f.audit_flag_name
where r.audit_flag_value
