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
    r.studentid,
    r.student_number,
    r.salesforce_id,
    r.student_name,
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
    r.enroll_status,
    r.date_enrolled,
    r.cohort,
    r.ktc_cohort,
    r.gender,
    r.ethnicity,
    r.advisory,
    r.hos,
    r.year_in_school,
    r.year_in_network,
    r.rn_undergrad,
    r.is_out_of_district,
    r.is_self_contained as is_pathways,
    r.is_retained_year,
    r.is_retained_ever,
    r.is_counseling_services,
    r.is_student_athlete,
    r.gifted_and_talented,
    r.lunch_status,
    r.iep_status,
    r.lep_status,
    r.is_504,
    r.is_tutoring as tutoring_nj,
    r.nj_student_tier,
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
    r.tableau_username,
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
    r.expectation,
    r.notes,
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

    null as studentid,
    null as student_number,
    null as salesforce_id,
    null as student_name,

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
    null as enroll_status,
    null as date_enrolled,
    null as cohort,
    null as ktc_cohort,
    null as gender,
    null as ethnicity,
    null as advisory,
    null as hos,
    null as year_in_school,
    null as year_in_network,
    null as rn_undergrad,
    null as is_out_of_district,
    null as is_pathways,
    null as is_retained_year,
    null as is_retained_ever,
    null as is_counseling_services,
    null as is_student_athlete,
    null as gifted_and_talented,
    null as lunch_status,
    null as iep_status,
    null as lep_status,
    null as is_504,
    null as tutoring_nj,
    null as nj_student_tier,

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
    r.tableau_username,
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
    r.expectation,
    r.notes,

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
