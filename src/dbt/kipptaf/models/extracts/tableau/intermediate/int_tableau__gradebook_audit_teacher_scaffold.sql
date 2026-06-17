select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.schoolid,
    s.school,
    s.region,
    s.sections_dcid,
    s.sectionid,
    s.section_number,
    s.external_expression,
    s.course_number,
    s.course_name,
    s.credit_type,
    s.exclude_from_gpa,
    s.teacher_number,
    s.teacher_name,
    s.teacher_tableau_username,
    s.manager_employee_number,
    s.manager_name,
    s.manager_tableau_username,
    s.hos,
    s.school_leader,
    s.school_leader_tableau_username,
    s.quarter,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    null as assignment_category_code,
    null as assignment_category_name,
    null as assignment_category_term,
    null as expectation,
    null as notes,

    coalesce(s.school_level_alt, s.school_level) as school_level,

    concat(
        s.region, coalesce(s.school_level_alt, s.school_level)
    ) as region_school_level,

    if(
        coalesce(s.school_level_alt, s.school_level) = 'HS',
        s.external_expression,
        s.section_number
    ) as section_or_period,

    'teacher_scaffold_course' as scaffold_name,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
where s.school_level_alt != 'ES' and s._dbt_source_project != 'kippmiami'

union all

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.schoolid,
    s.school,
    s.region,
    s.sections_dcid,
    s.sectionid,
    s.section_number,
    s.external_expression,
    s.course_number,
    s.course_name,
    s.credit_type,
    s.exclude_from_gpa,
    s.teacher_number,
    s.teacher_name,
    s.teacher_tableau_username,
    s.manager_employee_number,
    s.manager_name,
    s.manager_tableau_username,
    s.hos,
    s.school_leader,
    s.school_leader_tableau_username,
    s.quarter,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    coalesce(s.school_level_alt, s.school_level) as school_level,

    concat(
        s.region, coalesce(s.school_level_alt, s.school_level)
    ) as region_school_level,

    if(
        coalesce(s.school_level_alt, s.school_level) = 'HS',
        s.external_expression,
        s.section_number
    ) as section_or_period,

    'teacher_category_scaffold' as scaffold_name,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
inner join
    {{ ref("int_powerschool__u_expectations_qtd_unpivot") }} as ge
    on s.region = ge.region
    and s.school_level = ge.school_level
    and s.academic_year = ge.academic_year
    and s.quarter = ge.quarter
where s.school_level_alt != 'ES' and s._dbt_source_project != 'kippmiami'

union all

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.schoolid,
    s.school,
    s.region,
    s.sections_dcid,
    s.sectionid,
    s.section_number,
    s.external_expression,
    s.course_number,
    s.course_name,
    s.credit_type,
    s.exclude_from_gpa,
    s.teacher_number,
    s.teacher_name,
    s.teacher_tableau_username,
    s.manager_employee_number,
    s.manager_name,
    s.manager_tableau_username,
    s.hos,
    s.school_leader,
    s.school_leader_tableau_username,
    s.quarter,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    coalesce(s.school_level_alt, s.school_level) as school_level,

    concat(
        s.region, coalesce(s.school_level_alt, s.school_level)
    ) as region_school_level,

    if(
        coalesce(s.school_level_alt, s.school_level) = 'HS',
        s.external_expression,
        s.section_number
    ) as section_or_period,

    'teacher_assignment_scaffold' as scaffold_name,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
inner join
    {{ ref("int_powerschool__u_expectations_qtd_unpivot") }} as ge
    on s.region = ge.region
    and s.school_level = ge.school_level
    and s.academic_year = ge.academic_year
    and s.quarter = ge.quarter
where s.school_level_alt != 'ES' and s._dbt_source_project != 'kippmiami'
