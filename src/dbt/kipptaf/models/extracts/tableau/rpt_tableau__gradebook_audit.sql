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
    null as week_end_sunday,

    null as teacher_running_total_assign_by_cat,
    null as quarter_course_percent_grade,
    null as quarter_course_grade_points,
    null as quarter_comment_value,
    null as cte_grouping,
    null as category_quarter_percent_grade,
    null as assignmentid,
    null as assignment_name,
    null as duedate,
    null as scoretype,
    null as totalpointvalue,

    'No Flags' as audit_flag_name,
    false as audit_flag_value,

    'No Flags' as audit_category,
    'NF' as code_type,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
inner join
    {{ ref("int_tableau__gradebook_audit_scaffold_unpivot") }} as f
    on s._dbt_source_project = f._dbt_source_project
    and s.academic_year = f.academic_year
    and s.schoolid = f.schoolid
    and s.teacher_number = f.teacher_number
    and s.`quarter` = f.`quarter`
    and not f.is_healthy_gradebook
where
    s.academic_year = {{ var("current_academic_year") }}
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
    f.week_end_sunday,

    f.teacher_running_total_assign_by_cat,
    f.quarter_course_percent_grade,
    f.quarter_course_grade_points,
    f.quarter_comment_value,
    f.cte_grouping,
    f.category_quarter_percent_grade,
    f.assignmentid,
    f.assignment_name,
    f.duedate,
    f.scoretype,
    f.totalpointvalue,

    f.audit_flag_name,
    f.audit_flag_value,

    f.audit_category,
    f.code_type,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
inner join
    {{ ref("int_tableau__gradebook_audit_scaffold_unpivot") }} as f
    on s._dbt_source_project = f._dbt_source_project
    and s.academic_year = f.academic_year
    and s.schoolid = f.schoolid
    and s.teacher_number = f.teacher_number
    and s.`quarter` = f.`quarter`
    and not f.is_healthy_gradebook
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'
