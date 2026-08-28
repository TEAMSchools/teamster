select
    student_first_name as first_name,
    student_last_name as last_name,
    _dbt_source_project as code_location,

    cast(schoolid as string) as school_id,
    cast(student_number as string) as student_id,

    cast(grade_level as string) as grade_level,

    if(enroll_status = 0, '1', '0') as `status`,
from {{ ref("int_extracts__student_enrollments") }}
where
    -- Every NJ region is in scope and each district wrapper filters this view
    -- down to its own `code_location`. Miami is excluded because it rosters from
    -- Focus rather than PowerSchool — the same carve-out the six rpt_clever__*
    -- feeds make.
    _dbt_source_project != 'kippmiami'
    and academic_year = {{ var("current_academic_year") }}
    and rn_year = 1
    and not is_out_of_district
    and enroll_status in (0, -1)
