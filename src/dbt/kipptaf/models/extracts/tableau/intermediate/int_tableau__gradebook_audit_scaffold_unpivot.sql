with
    -- trunk-ignore(sqlfluff/ST03)
    flags_calculations as (
        select *, from {{ ref("int_tableau__gradebook_audit_flags_calculations") }}
    )

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level_alt as region_school_level,
    s.region,
    s.school_level_alt as school_level,
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

    s.quarter,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'
