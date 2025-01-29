with
    teacher_aggs as (
        select
            academic_year,
            academic_year_display,
            region,
            school_level,
            region_school_level,
            schoolid,
            school,

            semester,
            quarter,
            audit_qt_week_number,
            quarter_start_date,
            quarter_end_date,
            is_current_quarter,
            audit_start_date,
            audit_end_date,
            audit_due_date,

            assignment_category_name,
            assignment_category_code,
            assignment_category_term,
            expectation,
            notes,

            section_or_period,
            sectionid,
            sections_dcid,
            section_number,
            external_expression,
            credit_type,
            course_number,
            course_name,
            exclude_from_gpa,
            is_ap_course,

            teacher_number,
            teacher_name,
            tableau_username,

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
            teacher_running_total_assign_by_cat,
            teacher_avg_score_for_assign_per_class_section_and_assign_id,

            audit_category,
            cte_grouping,
            audit_flag_name,
            max(audit_flag_value) as audit_flag_value,

        from {{ ref("int_tableau__gradebook_audit_final_roster") }}
        group by all  {# TODO: determine cause of duplicates and remove #}
    ),

    valid_flags as (
        select
            academic_year,
            region,
            schoolid,

            quarter,
            audit_qt_week_number,

            assignment_category_term,

            sectionid,

            teacher_number,

            teacher_assign_id,

            studentid,
            student_number,
            student_name,
            grade_level,
            salesforce_id,
            ktc_cohort,
            enroll_status,
            cohort,
            gender,
            ethnicity,
            advisory,
            year_in_school,
            year_in_network,
            rn_undergrad,
            is_out_of_district,
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
            date_enrolled,

            category_quarter_percent_grade,
            category_quarter_average_all_courses,

            quarter_course_percent_grade_that_matters,
            quarter_course_grade_points_that_matters,
            quarter_citizenship,
            quarter_comment_value,

            raw_score,
            score_entered,
            assign_final_score_percent,
            is_exempt,
            is_late,
            is_missing,

            audit_category,
            cte_grouping,
            audit_flag_name,
            audit_flag_value as flag_value,

        from {{ ref("int_tableau__gradebook_audit_final_roster") }}
        where audit_flag_value = 1
        group by all  {# TODO: determine cause of duplicates and remove #}
    )

select
    t.*,
    v.studentid,
    v.student_number,
    v.student_name,
    v.grade_level,
    v.salesforce_id,
    v.ktc_cohort,
    v.enroll_status,
    v.cohort,
    v.gender,
    v.ethnicity,
    v.advisory,
    v.year_in_school,
    v.year_in_network,
    v.rn_undergrad,
    v.is_out_of_district,
    v.is_retained_year,
    v.is_retained_ever,
    v.lunch_status,
    v.gifted_and_talented,
    v.iep_status,
    v.lep_status,
    v.is_504,
    v.is_counseling_services,
    v.is_student_athlete,
    v.ada,
    v.ada_above_or_at_80,
    v.date_enrolled,

    v.category_quarter_percent_grade,
    v.category_quarter_average_all_courses,

    v.quarter_course_percent_grade_that_matters,
    v.quarter_course_grade_points_that_matters,
    v.quarter_citizenship,
    v.quarter_comment_value,

    v.raw_score,
    v.score_entered,
    v.assign_final_score_percent,
    v.is_exempt,
    v.is_late,
    v.is_missing,

    v.flag_value,

from teacher_aggs as t
left join
    valid_flags as v
    on t.academic_year = v.academic_year
    and t.region = v.region
    and t.schoolid = v.schoolid
    and t.quarter = v.quarter
    and t.audit_qt_week_number = v.audit_qt_week_number
    and t.sectionid = v.sectionid
    and t.teacher_number = v.teacher_number
    and t.assignment_category_term = v.assignment_category_term
    and t.teacher_assign_id = v.teacher_assign_id
    and t.audit_category = v.audit_category
    and t.cte_grouping = v.cte_grouping
    and t.audit_flag_name = v.audit_flag_name
