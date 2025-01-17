select
    s.*,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,
from {{ ref("int_tableau__gradebook_audit_section_week_scaffold") }} as s
inner join
    {{ ref("stg_reporting__gradebook_expectations") }} as ge
    on s.region = ge.region
    and s.school_level = ge.school_level
    and s.academic_year = ge.academic_year
    and s.quarter = ge.quarter
    and s.week_number_quarter = ge.week_number
where
    concat(s.course_number, ge.assignment_category_code) not in (
        'SEM72005G1F',
        'SEM72005G2F',
        'SEM72005G3F',
        'SEM72005G4F',
        'SEM72005G1S',
        'SEM72005G2S',
        'SEM72005G3S',
        'SEM72005G4S'
    )
