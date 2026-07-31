with
    enrolled as (
        select grade_level, cast(schoolid as string) as school_id,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            _dbt_source_project = 'kippnewark'
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
        select distinct school_id, grade_level, from enrolled
    ),

    section_attributes as (
        select
            school_id,
            grade_level,

            cast(grade_level as string) as grade_str,
            lpad(cast(grade_level as string), 2, '0') as grade_padded,
        from grade_sections
    ),

    section_owner as (
        -- ParentSquare requires a staff_id on every section and exactly one
        -- primary per section. Which of the six Operations leaders owns a section
        -- is a formality — their access to every school comes from their
        -- rpt_parentsquare__staff rows, not from section membership — so this
        -- picks one deterministically. Reading it from the staff feed rather than
        -- restating the leader list guarantees the value resolves in staff.csv.
        select min(staff_id) as staff_id, from {{ ref("rpt_parentsquare__staff") }}
    )

-- One synthetic section per (school, grade). The Integration Planner sets
-- granularity at "School + Grade Level only" (question 5) and excludes
-- teacher-classroom rostering, so these stand in for real course sections: they
-- give ParentSquare the grade-level grouping it needs to satisfy sections.csv and
-- rosters.csv without importing any teacher. Mirrors the auto-generated ENR
-- section pattern in rpt_clever__sections.
select
    a.school_id,
    a.grade_str as section_number,

    o.staff_id,

    '1' as is_primary,

    concat(a.school_id, a.grade_padded) as section_id,

    if(a.grade_level = 0, 'Kindergarten', concat('Grade ', a.grade_str)) as course_name,
from section_attributes as a
cross join section_owner as o
