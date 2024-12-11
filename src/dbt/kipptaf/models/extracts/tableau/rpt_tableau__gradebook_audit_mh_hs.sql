with
    audits_with_audit_cat as (
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
                        'assign_s_ms_score_not_conversion_chart_options',
                        'assign_s_hs_score_not_conversion_chart_options',
                        'assign_s_score_less_50p',
                        'qt_assign_no_course_assignments',
                        'qt_percent_grade_greater_100'
                    )
                then 'Data Entry'
                when
                    audit_flag_name in (
                        'w_expected_assign_count_not_met',
                        'f_expected_assign_count_not_met',
                        's_expected_assign_count_not_met'
                    )
                then 'Updated'
                when
                    audit_flag_name
                    in ('w_grade_inflation', 'qt_student_is_ada_80_plus_gpa_less_2')
                then 'Health'
                when
                    audit_flag_name in (
                        'qt_kg_conduct_code_missing',
                        'qt_kg_conduct_code_not_hr',
                        'qt_kg_conduct_code_incorrect',
                        'qt_g1_g8_conduct_code_missing',
                        'qt_kg_conduct_code_incorrect',
                        'qt_g1_g8_conduct_code_incorrect',
                        'qt_grade_70_comment_missing',
                        'qt_comment_missing',
                        'qt_effort_grade_missing'
                    )
                then 'EOQ Gradebook Process'
            end as gradebook_audit_category,

        from {{ ref("int_tableau__gradebook_audit_flags") }}
        where school_level != 'ES'
    )

-- teacher: class + category
select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level,
    s.salesforce_id,
    s.ktc_cohort,
    s.enroll_status,
    s.cohort,
    s.gender,
    s.ethnicity,
    s.advisory,
    s.hos,
    s.region_school_level,
    s.year_in_school,
    s.year_in_network,
    s.rn_undergrad,
    s.is_out_of_district,
    s.is_pathways,
    s.is_retained_year,
    s.is_retained_ever,
    s.lunch_status,
    s.gifted_and_talented,
    s.iep_status,
    s.lep_status,
    s.is_504,
    s.is_counseling_services,
    s.is_student_athlete,
    s.ada,
    s.`quarter`,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.cal_quarter_end_date,
    s.is_current_quarter,
    s.is_quarter_end_date_range,
    s.ada_above_or_at_80,
    s.section_or_period,
    s.week_number,
    s.assignment_category_name,
    s.assignment_category_code,
    s.assignment_category_term,
    s.expectation,
    s.notes,
    s.sectionid,
    s.sections_dcid,
    s.section_number,
    s.external_expression,
    s.date_enrolled,
    s.credit_type,
    s.course_number,
    s.course_name,
    s.exclude_from_gpa,
    s.teacher_number,
    s.teacher_name,
    s.tutoring_nj,
    s.nj_student_tier,
    s.is_ap_course,
    s.tableau_username,
    s.category_quarter_percent_grade,
    s.category_quarter_average_all_courses,
    s.quarter_course_percent_grade_that_matters,
    s.quarter_course_grade_points_that_matters,
    s.quarter_citizenship,
    s.quarter_comment_value,

    a.gradebook_audit_category,
    a.audit_flag_name,
    a.audit_flag_value,

from {{ ref("int_tableau__gradebook_audit_roster") }} as s
left join
    audits_with_audit_cat as a
    on s.schoolid = a.schoolid
    and s.quarter = a.quarter
    and s.week_number = a.audit_qt_week_number
    and s.teacher_number = a.teacher_number
    and s.section_or_period = a.section_or_period
    and s.assignment_category_code = a.expected_teacher_assign_category_code
    and audit_flag_name in (
        'qt_teacher_s_total_greater_200',
        'w_expected_assign_count_not_met',
        'f_expected_assign_count_not_met',
        's_expected_assign_count_not_met'
    )
