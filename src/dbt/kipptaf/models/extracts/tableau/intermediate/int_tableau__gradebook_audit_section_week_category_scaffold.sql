select
    s.*,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

from {{ ref("int_tableau__gradebook_audit_section_week_scaffold") }} as s
inner join
    {{ ref("stg_google_sheets__gradebook_expectations_assignments") }} as ge
    on s.region = ge.region
    and s.school_level = ge.school_level
    and s.academic_year = ge.academic_year
    and s.quarter = ge.quarter
    and s.week_number_quarter = ge.week_number
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
    on s.academic_year = e1.academic_year
    and s.course_number = e1.course_number
    and ge.assignment_category_code = e1.gradebook_category
    and e1.view_name = 'gradebook_audit_section_week_category_scaffold'
where e1.include is null
