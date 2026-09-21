with
    enrolled as (
        select
            grade_level,
            _dbt_source_project as code_location,

            cast(schoolid as string) as school_id,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            -- Every NJ region is in scope and each district wrapper filters this
            -- view down to its own `code_location`. Miami is excluded because it
            -- rosters from Focus rather than PowerSchool — the same carve-out the
            -- six rpt_clever__* feeds make.
            _dbt_source_project != 'kippmiami'
            and academic_year = {{ var("current_academic_year") }}
            and rn_year = 1
            and not is_out_of_district
            and enroll_status in (0, -1)
    ),

    grade_sections as (
        -- grain projection, not dup-masking
        -- Derived from the (school, grade) pairs students are actually enrolled
        -- in, not from each school's `low_grade`..`high_grade` span. No empty
        -- section is emitted, and every `rpt_parentsquare__rosters` row is
        -- guaranteed a section to point at.
        select distinct school_id, grade_level, code_location, from enrolled
    ),

    section_attributes as (
        select
            school_id,
            grade_level,
            code_location,

            cast(grade_level as string) as grade_str,
            lpad(cast(grade_level as string), 2, '0') as grade_padded,
        from grade_sections
    ),

    section_owner as (
        select code_location, min(staff_id) as staff_id,
        from {{ ref("rpt_parentsquare__staff") }}
        group by code_location
    )

-- Mirrors the auto-generated ENR section pattern in rpt_clever__sections.
-- The owner join is LEFT on purpose. `section_owner` groups by region, so a
-- region whose Ops group is emptied or renamed contributes no owner row. An
-- inner join drops that region's sections, and the extract factory skips a
-- zero-row sections.csv, so ParentSquare keeps a stale file and nothing fails.
-- A null owner keeps the section and lets the `not_null` test on staff_id fire.
select
    a.school_id,
    a.code_location,
    a.grade_str as section_number,

    o.staff_id,

    '1' as is_primary,

    concat(a.school_id, a.grade_padded) as section_id,

    if(a.grade_level = 0, 'Kindergarten', concat('Grade ', a.grade_str)) as course_name,
from section_attributes as a
left join section_owner as o on a.code_location = o.code_location
