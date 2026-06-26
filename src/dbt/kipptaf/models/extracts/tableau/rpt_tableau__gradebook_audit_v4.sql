with
    count_not_met_flag as (
        select
            *,

            if(
                total_assign_count_qtd_by_cat_section_actual
                != total_assign_count_qtd_by_cat_section_no_flags,
                true,
                false
            ) as expected_assign_count_not_met,

        from {{ ref("int_tableau__gradebook_audit_flags_calculations") }}
    ),

    flags_unpivot as (
        select
            _dbt_source_project,
            academic_year,
            academic_year_display,
            region_school_level,
            school_level,
            region,
            schoolid,
            school,

            students_dcid,
            studentid,
            student_number,
            student_name,
            grade_level,
            dateenrolled,
            dateleft,
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
            is_self_contained,
            is_retained_year,
            is_retained_ever,
            lunch_status,
            gifted_and_talented,
            iep_status,
            lep_status,
            is_504,
            is_counseling_services,
            is_student_athlete,
            `ada`,
            ada_above_or_at_80,

            course_number,
            course_name,
            credit_type,
            exclude_from_gpa,
            sections_dcid,
            sectionid,
            section_number,
            external_expression,
            section_or_period,
            teacher_number,
            teacher_name,
            school_leader,
            manager_employee_number,
            manager_name,
            hos,

            teacher_tableau_username,
            manager_tableau_username,
            school_leader_tableau_username,

            `quarter`,
            semester,
            quarter_start_date,
            quarter_end_date,
            is_current_quarter,

            assignment_category_code,
            assignment_category_name,
            assignment_category_term,
            expectation,
            notes,

            null as quarter_course_percent_grade,
            null as quarter_course_grade_points,
            cast(null as string) as quarter_comment_value,

            cte_grouping,
            audit_category,

            assignmentid,
            assignment_name,
            duedate,
            scoretype,
            totalpointvalue,
            assignment_has_flags,

            total_assign_count_qtd_by_cat_section_actual,
            total_assign_count_qtd_by_cat_section_no_flags,

            audit_flag_name,
            audit_flag_value,

            max(audit_flag_value) over (
                partition by
                    _dbt_source_project,
                    academic_year,
                    schoolid,
                    teacher_number,
                    `quarter`
            ) as is_healthy_gradebook,

        from
            count_not_met_flag unpivot (
                audit_flag_value for audit_flag_name in (
                    qt_percent_grade_greater_100,
                    qt_grade_70_comment_missing,
                    expected_assign_count_not_met
                )
            )
    )

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,

    s.course_number,
    s.course_name,
    s.credit_type,
    s.exclude_from_gpa,
    s.sections_dcid,
    s.sectionid,
    s.section_number,
    s.external_expression,
    s.section_or_period,
    s.teacher_number,
    s.teacher_name,
    s.school_leader,
    s.manager_employee_number,
    s.manager_name,
    s.hos,

    s.teacher_tableau_username,
    s.manager_tableau_username,
    s.school_leader_tableau_username,

    s.`quarter`,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    null as assignment_category_code,
    null as assignment_category_name,
    null as assignment_category_term,
    null as expectation,
    null as notes,

    0.0 as quarter_course_percent_grade,
    0.0 as quarter_course_grade_points,
    cast(null as string) as quarter_comment_value,
    f.cte_grouping,

    null as assignmentid,
    null as assignment_name,
    null as duedate,
    null as scoretype,
    null as totalpointvalue,
    null as assignment_has_flags,

    'No Flags' as audit_flag_name,
    false as audit_flag_value,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
inner join
    flags_unpivot as f
    on s._dbt_source_project = f._dbt_source_project
    and s.academic_year = f.academic_year
    and s.schoolid = f.schoolid
    and s.teacher_number = f.teacher_number
    and s.`quarter` = f.`quarter`
    and not f.is_healthy_gradebook
where
    s.academic_year = {{ var("current_academic_year") }}  /* summer toggle: see skill */
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'

union all

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,

    s.course_number,
    s.course_name,
    s.credit_type,
    s.exclude_from_gpa,
    s.sections_dcid,
    s.sectionid,
    s.section_number,
    s.external_expression,
    s.section_or_period,
    s.teacher_number,
    s.teacher_name,
    s.school_leader,
    s.manager_employee_number,
    s.manager_name,
    s.hos,

    s.teacher_tableau_username,
    s.manager_tableau_username,
    s.school_leader_tableau_username,

    s.`quarter`,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    f.assignment_category_code,
    f.assignment_category_name,
    f.assignment_category_term,
    f.expectation,
    f.notes,

    f.quarter_course_percent_grade,
    f.quarter_course_grade_points,
    f.quarter_comment_value,
    f.cte_grouping,

    f.assignmentid,
    f.assignment_name,
    f.duedate,
    f.scoretype,
    f.totalpointvalue,
    f.assignment_has_flags,

    f.audit_flag_name,
    f.audit_flag_value,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
inner join
    flags_unpivot as f
    on s._dbt_source_project = f._dbt_source_project
    and s.academic_year = f.academic_year
    and s.schoolid = f.schoolid
    and s.teacher_number = f.teacher_number
    and s.`quarter` = f.`quarter`
    and not f.is_healthy_gradebook
where
    s.academic_year = {{ var("current_academic_year") }}  /* summer toggle: see skill */
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'
