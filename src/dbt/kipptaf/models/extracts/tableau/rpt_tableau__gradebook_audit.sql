with
    count_not_met_flag as (
        select
            *,

            -- short on valid assignments: flagged assignments don't count as
            -- valid, so fewer valid than expected (incl. zero entered) fires
            if(
                total_assign_count_qtd_by_cat_section_no_flags < expectation,
                true,
                false
            ) as expected_assign_count_not_met,

        from {{ ref("int_tableau__gradebook_audit_flags_calculations") }}
    ),

    health_calc as (
        select
            _dbt_source_project,
            academic_year,
            schoolid,
            teacher_number,
            `quarter`,

            -- fix: negate max so TRUE means no flags fired
            not max(audit_flag_value) as is_healthy_gradebook,

        from
            count_not_met_flag unpivot (
                audit_flag_value for audit_flag_name in (
                    qt_percent_grade_greater_100,
                    qt_grade_70_comment_missing,
                    expected_assign_count_not_met
                )
            )
        group by _dbt_source_project, academic_year, schoolid, teacher_number, `quarter`
    ),

    flags_unpivot as (
        -- student flags only
        select *,
        from
            count_not_met_flag unpivot (
                audit_flag_value for audit_flag_name
                in (qt_percent_grade_greater_100, qt_grade_70_comment_missing)
            )
        where cte_grouping = 'student_course' and audit_flag_value
    )

-- quarter x teacher x section - healthy only
select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,

    s.students_dcid,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level,
    s.dateenrolled,
    s.dateleft,
    s.salesforce_id,
    s.ktc_cohort,
    s.enroll_status,
    s.cohort,
    s.gender,
    s.ethnicity,
    s.advisory,
    s.year_in_school,
    s.year_in_network,
    s.rn_undergrad,
    s.is_out_of_district,
    s.is_self_contained,
    s.is_retained_year,
    s.is_retained_ever,
    s.lunch_status,
    s.gifted_and_talented,
    s.iep_status,
    s.lep_status,
    s.is_504,
    s.is_counseling_services,
    s.is_student_athlete,
    s.`ada`,
    s.ada_above_or_at_80,

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

    s.assignment_category_code,
    s.assignment_category_name,
    s.assignment_category_term,
    s.expectation,
    s.notes,

    s.quarter_course_percent_grade,
    s.quarter_comment_value,

    s.cte_grouping,
    s.audit_category,

    s.assignmentid,
    s.assignment_name,
    s.duedate,
    s.scoretype,
    s.totalpointvalue,
    s.assignment_has_flags,

    s.total_assign_count_qtd_by_cat_section_actual,
    s.total_assign_count_qtd_by_cat_section_no_flags,

    'No Flags' as audit_flag_name,
    false as audit_flag_value,

    h.is_healthy_gradebook,

from {{ ref("int_tableau__gradebook_audit_flags_calculations") }} as s
inner join
    health_calc as h
    on s._dbt_source_project = h._dbt_source_project
    and s.academic_year = h.academic_year
    and s.schoolid = h.schoolid
    and s.teacher_number = h.teacher_number
    and s.`quarter` = h.`quarter`
    and h.is_healthy_gradebook
where
    s.academic_year = {{ var("current_academic_year") }}  /* summer toggle: see skill */
    and s.school_level != 'ES'
    and s._dbt_source_project != 'kippmiami'
    and s.cte_grouping = 'sections_teacher'

union all

/* quarter x teacher x section x assignment - not-healthy -
   expected_assign_count_not_met */
select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,

    s.students_dcid,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level,
    s.dateenrolled,
    s.dateleft,
    s.salesforce_id,
    s.ktc_cohort,
    s.enroll_status,
    s.cohort,
    s.gender,
    s.ethnicity,
    s.advisory,
    s.year_in_school,
    s.year_in_network,
    s.rn_undergrad,
    s.is_out_of_district,
    s.is_self_contained,
    s.is_retained_year,
    s.is_retained_ever,
    s.lunch_status,
    s.gifted_and_talented,
    s.iep_status,
    s.lep_status,
    s.is_504,
    s.is_counseling_services,
    s.is_student_athlete,
    s.`ada`,
    s.ada_above_or_at_80,

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

    s.assignment_category_code,
    s.assignment_category_name,
    s.assignment_category_term,
    s.expectation,
    s.notes,

    s.quarter_course_percent_grade,
    s.quarter_comment_value,

    s.cte_grouping,
    s.audit_category,

    s.assignmentid,
    s.assignment_name,
    s.duedate,
    s.scoretype,
    s.totalpointvalue,
    s.assignment_has_flags,

    s.total_assign_count_qtd_by_cat_section_actual,
    s.total_assign_count_qtd_by_cat_section_no_flags,

    'expected_assign_count_not_met' as audit_flag_name,
    true as audit_flag_value,

    h.is_healthy_gradebook,

from count_not_met_flag as s
inner join
    health_calc as h
    on s._dbt_source_project = h._dbt_source_project
    and s.academic_year = h.academic_year
    and s.schoolid = h.schoolid
    and s.teacher_number = h.teacher_number
    and s.`quarter` = h.`quarter`
where
    s.academic_year = {{ var("current_academic_year") }}  /* summer toggle: see skill */
    and s.school_level != 'ES'
    and s._dbt_source_project != 'kippmiami'
    and s.cte_grouping = 'assignment_teacher'
    and s.expected_assign_count_not_met

union all

/* quarter x teacher x student: qt_percent_grade_greater_100,
   qt_grade_70_comment_missing */
select
    _dbt_source_project,
    academic_year,
    academic_year_display,
    region_school_level,
    region,
    school_level,
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

    quarter_course_percent_grade,
    quarter_comment_value,
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

    false as is_healthy_gradebook,

from flags_unpivot
