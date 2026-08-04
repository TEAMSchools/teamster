with
    enrolled as (
        select student_number, grade_level, cast(schoolid as string) as school_id,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            _dbt_source_project = 'kippnewark'
            and academic_year = {{ var("current_academic_year") }}
            and rn_year = 1
            and not is_out_of_district
            and enroll_status in (0, -1)
    ),

    roster_keys as (
        select
            student_number,
            school_id,

            lpad(cast(grade_level as string), 2, '0') as grade_padded,
        from enrolled
    )

-- One row per student, placing them in their school-and-grade section. The
-- section_id expression is identical to the one in rpt_parentsquare__sections and
-- both models read the same enrollment filter, so every roster row resolves to a
-- section by construction; the relationships test on section_id enforces it.
select
    school_id,

    cast(student_number as string) as student_id,

    concat(school_id, grade_padded) as section_id,
from roster_keys
