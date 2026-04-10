select
    sec._dbt_source_relation,
    sec.schoolid,
    sec.yearid,
    sec.academic_year,
    sec.`quarter`,
    sec.semester,
    sec.quarter_start_date,
    sec.quarter_end_date,
    sec.is_current_term,
    sec.school,
    sec.region,
    sec.week_start_date,
    sec.week_end_date,
    sec.week_start_monday,
    sec.week_end_sunday,
    sec.school_week_start_date_lead,
    sec.week_number_academic_year,
    sec.week_number_quarter,
    sec.hos,
    sec.school_leader,
    sec.school_leader_tableau_username,
    sec.sections_dcid,
    sec.sectionid,
    sec.section_number,
    sec.external_expression,
    sec.course_number,
    sec.course_name,
    sec.credit_type,
    sec.exclude_from_gpa,
    sec.is_ap_course,
    sec.teacher_number,
    sec.teacher_name,
    sec.teacher_tableau_username,
    sec.region_school_level,
    sec.school_level,
    sec.academic_year_display,
    sec.is_quarter_end_date_range,
    sec.section_or_period,
    sec.quarter_end_date_insession,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    sec.is_current_week,

from {{ ref("int_tableau__gradebook_audit_section_week_scaffold") }} as sec
inner join
    {{ ref("stg_google_sheets__gradebook_expectations_assignments") }} as ge
    on sec.region = ge.region
    and sec.school_level = ge.school_level
    and sec.academic_year = ge.academic_year
    and sec.quarter = ge.quarter
    and sec.week_number_quarter = ge.week_number
/* permanently remove rows for certain gradebook category(s) by course_number */
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
    on sec.academic_year = e1.academic_year
    and sec.course_number = e1.course_number
    and ge.assignment_category_code = e1.gradebook_category
    and e1.view_name = 'teacher_category_scaffold'
    and e1.cte = 'final'
/* permanently remove rows for certain gradebook category(s) by course_number
   for a region */
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
    on sec.academic_year = e2.academic_year
    and sec.course_number = e2.course_number
    and sec.region = e2.region
    and ge.assignment_category_code = e2.gradebook_category
    and e2.view_name = 'teacher_category_scaffold'
    and e2.cte = 'final'
/* permanently remove rows for certain gradebook category(s) by credit type for
   a region/school level */
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e3
    on sec.academic_year = e3.academic_year
    and sec.credit_type = e3.credit_type
    and sec.region = e3.region
    and sec.school_level = e3.school_level
    and ge.assignment_category_code = e3.gradebook_category
    and e3.view_name = 'teacher_category_scaffold'
    and e3.cte = 'final'
where e1.include_row is null and e2.include_row is null and e3.include_row is null
