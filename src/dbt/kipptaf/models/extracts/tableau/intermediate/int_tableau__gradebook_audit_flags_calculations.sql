with
    quarter_course_grades as (
        select
            _dbt_source_project,
            academic_year,
            studentid,
            sectionid,
            storecode,
            termbin_start_date,
            term_percent_grade_adjusted as quarter_course_percent_grade,
            term_grade_points as quarter_course_grade_points,
            comment_value as quarter_comment_value,

            'current_year' as grades_type,

        from {{ ref("base_powerschool__final_grades") }}

        union all

        select
            _dbt_source_project,
            academic_year,
            studentid,
            sectionid,
            storecode,
            null as termbin_start_date,
            `percent` as quarter_course_percent_grade,
            gpa_points as quarter_course_grade_points,
            comment_value as quarter_comment_value,

            'last_year' as grades_type,

        from {{ ref("stg_powerschool__storedgrades") }}
        where
            academic_year = {{ var("current_academic_year") - 1 }}
            and storecode_type = 'Q'
            and not is_transfer_grade
    )

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level,
    s.school_level,
    s.region,
    s.schoolid,
    s.school,

    s.students_dcid,
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

    s.quarter,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    s.scaffold_name,

    s.assignment_category_code,
    s.assignment_category_name,
    s.assignment_category_term,
    s.expectation,
    s.notes,

    null as category_quarter_percent_grade,

    if(
        qg.quarter_course_percent_grade > 100, true, false
    ) as qt_percent_grade_greater_100,

    if(
        qg.quarter_course_percent_grade < 70 and qg.quarter_comment_value is null,
        true,
        false
    ) as qt_grade_70_comment_missing,

from {{ ref("int_tableau__gradebook_audit_scaffold") }} as s
left join
    quarter_course_grades as qg
    on s.academic_year = qg.academic_year
    and s.studentid = qg.studentid
    and s.sectionid = qg.sectionid
    and s._dbt_source_project = qg._dbt_source_project
    and s.quarter = qg.storecode
    and s.quarter_start_date <= current_date('{{ var("local_timezone") }}')
    and qg.grades_type = 'current_year'  /* summer toggle: see skill */
where s.scaffold_name = 'student_scaffold_course'

union all

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level,
    s.school_level,
    s.region,
    s.schoolid,
    s.school,

    s.students_dcid,
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

    s.quarter,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    s.scaffold_name,

    s.assignment_category_code,
    s.assignment_category_name,
    s.assignment_category_term,
    s.expectation,
    s.notes,

    cg.percent_grade as category_quarter_percent_grade,

    null as qt_percent_grade_greater_100,
    null as qt_grade_70_comment_missing,

from {{ ref("int_tableau__gradebook_audit_scaffold") }} as s
left join
    {{ ref("int_powerschool__category_grades") }} as cg
    on s.academic_year = cg.academic_year
    and s.studentid = cg.studentid
    and s.sectionid = cg.sectionid
    and s._dbt_source_project = cg._dbt_source_project
    and s.quarter = cg.storecode
    and s.quarter_start_date <= current_date('{{ var("local_timezone") }}')
where s.scaffold_name = 'student_scaffold_category'
