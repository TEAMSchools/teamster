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
        -- Derived from the (school, grade) pairs students are actually enrolled
        -- in, not from each school's low_grade..high_grade span, so no empty
        -- section is emitted and every rpt_parentsquare__rosters row is
        -- guaranteed a section to point at.
        -- grain projection: every selected column is functionally determined by
        -- the partition key; not a mask for upstream duplicates.
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

-- One synthetic section per (school, grade). The Integration Planner sets
-- granularity at "School + Grade Level only" (question 5) and excludes
-- teacher-classroom rostering, so these stand in for real course sections: they
-- give ParentSquare the grade-level grouping it needs to satisfy sections.csv and
-- rosters.csv without importing any teacher. Mirrors the auto-generated ENR
-- section pattern in rpt_clever__sections.
--
-- The owner join is a LEFT join deliberately. `section_owner` groups by region, so
-- a region whose Ops group is emptied or renamed contributes no owner row — an
-- inner join would silently drop that region's sections entirely, and a zero-row
-- sections.csv is skipped by the extract factory, leaving ParentSquare on a stale
-- file with nothing failing. Preserving the section with a null owner is what lets
-- the `not_null` test on staff_id fire instead.
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
