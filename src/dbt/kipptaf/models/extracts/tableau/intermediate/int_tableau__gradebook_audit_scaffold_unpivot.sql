with
    invalid_assignment_flag as (
        select
            _dbt_source_project,
            academic_year,
            schoolid,
            sections_dcid,
            `quarter`,
            assignment_category_code,
            assignmentid,

            cte_grouping,

            max(
                teacher_running_total_assign_by_cat
            ) as teacher_running_total_assign_by_cat,

            max(expectation) as expectation,

            max(audit_flag_value) as assignment_has_flags,

        from
            {{ ref("int_tableau__gradebook_audit_flags_calculations") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    assign_null_score,
                    assign_score_above_max,
                    assign_w_score_less_5,
                    assign_h_score_less_5,
                    assign_f_score_less_5,
                    assign_w_missing_score_not_5,
                    assign_f_missing_score_not_5,
                    assign_h_missing_score_not_5,
                    assign_w_missing_score_not_0,
                    assign_f_missing_score_not_0,
                    assign_h_missing_score_not_0,
                    assign_s_missing_score_not_0,
                    assign_s_score_less_50p,
                    assign_s_hs_score_less_50p,
                    assign_max_score_not_10,
                    overly_exempt_assignment,
                    percent_graded_min_not_met
                )
            )
        where cte_grouping != 'student_course'
        group by
            _dbt_source_project,
            academic_year,
            schoolid,
            sections_dcid,
            `quarter`,
            assignment_category_code,
            assignmentid,
            cte_grouping
    ),

    invalid_assignment_calc as (
        select
            _dbt_source_project,
            academic_year,
            schoolid,
            sections_dcid,
            `quarter`,
            assignment_category_code,
            assignmentid,
            assignment_has_flags,

            if(
                teacher_running_total_assign_by_cat >= expectation
                and assignment_has_flags,
                false,
                true
            ) as expected_assign_count_not_met,

        from invalid_assignment_flag
        where cte_grouping = 'assignment_teacher'
    ),

    flags_combined as (
        select b.*, c.assignment_has_flags, c.expected_assign_count_not_met,
        from {{ ref("int_tableau__gradebook_audit_flags_calculations") }} as b
        left join
            invalid_assignment_calc as c
            on b._dbt_source_project = c._dbt_source_project
            and b.academic_year = c.academic_year
            and b.schoolid = c.schoolid
            and b.sections_dcid = c.sections_dcid
            and b.`quarter` = c.`quarter`
            and b.assignment_category_code = c.assignment_category_code
            and b.assignmentid = c.assignmentid
    )

select
    u._dbt_source_project,
    u.academic_year,
    u.academic_year_display,
    u.region_school_level,
    u.school_level,
    u.region,
    u.schoolid,
    u.school,

    u.students_dcid,
    u.studentid,
    u.student_number,
    u.student_name,
    u.grade_level,
    u.dateenrolled,
    u.dateleft,
    u.salesforce_id,
    u.ktc_cohort,
    u.enroll_status,
    u.cohort,
    u.gender,
    u.ethnicity,
    u.advisory,
    u.year_in_school,
    u.year_in_network,
    u.rn_undergrad,
    u.is_out_of_district,
    u.is_self_contained,
    u.is_retained_year,
    u.is_retained_ever,
    u.lunch_status,
    u.gifted_and_talented,
    u.iep_status,
    u.lep_status,
    u.is_504,
    u.is_counseling_services,
    u.is_student_athlete,
    u.`ada`,
    u.ada_above_or_at_80,

    u.course_number,
    u.course_name,
    u.credit_type,
    u.exclude_from_gpa,
    u.sections_dcid,
    u.sectionid,
    u.section_number,
    u.external_expression,
    u.section_or_period,
    u.teacher_number,
    u.teacher_name,
    u.school_leader,
    u.manager_employee_number,
    u.manager_name,
    u.hos,

    u.teacher_tableau_username,
    u.manager_tableau_username,
    u.school_leader_tableau_username,

    u.`quarter`,
    u.semester,
    u.quarter_start_date,
    u.quarter_end_date,
    u.is_current_quarter,

    u.assignment_category_code,
    u.assignment_category_name,
    u.assignment_category_term,
    u.expectation,
    u.notes,
    u.week_end_sunday,

    u.teacher_running_total_assign_by_cat,
    u.quarter_course_percent_grade,
    u.quarter_course_grade_points,
    u.quarter_comment_value,
    u.cte_grouping,
    u.category_quarter_percent_grade,
    u.assignmentid,
    u.assignment_name,
    u.duedate,
    u.scoretype,
    u.totalpointvalue,
    u.scorepoints,
    u.is_expected_late,
    u.is_exempt,
    u.is_expected_missing,
    u.is_expected_zero,
    u.is_expected_academic_dishonesty,
    u.score_entered,
    u.assign_final_score_percent,

    u.audit_flag_name,
    u.audit_flag_value,

    f.audit_category,
    f.code_type,

    max(audit_flag_value) over (
        partition by
            u._dbt_source_project,
            u.academic_year,
            u.schoolid,
            u.teacher_number,
            u.`quarter`
    ) as is_healthy_gradebook,

from
    flags_combined unpivot (
        audit_flag_value for audit_flag_name in (
            qt_percent_grade_greater_100,
            qt_grade_70_comment_missing,
            assignment_has_flags,
            expected_assign_count_not_met
        )
    ) as u
inner join
    {{ ref("stg_google_sheets__gradebook_flags") }} as f
    on u.academic_year = f.academic_year
    and u.region = f.region
    and u.school_level = f.school_level
    and u.assignment_category_code = f.code
    and u.audit_flag_name = f.audit_flag_name
    and f.cte_grouping != 'assignment_student'
