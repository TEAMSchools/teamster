{{ config(severity="error") }}

-- every resolved sheet row must name a real PowerSchool section, or its treated
-- students silently vanish through the inner join in
-- int_ignite__treatment_assignment
with
    resolved as (
        select ref_id, school_name, academic_year, course_number, section_number,
        from {{ ref("stg_google_sheets__ignite__treatment_sections") }}
        where status = 'resolved'
    ),

    /* grain projection, not dup-masking: one row per resolved year */
    resolved_years as (select distinct academic_year, from resolved),

    /* grain projection, not dup-masking: one row per section */
    sections as (
        select distinct
            ce.school_name, ce.academic_year, ce.course_number, ce.section_number,
        from {{ ref("int_extracts__course_enrollments_by_term") }} as ce
        inner join resolved_years as y on ce.academic_year = y.academic_year
    )

select r.ref_id,
from resolved as r
left join
    sections as s
    on r.school_name = s.school_name
    and r.academic_year = s.academic_year
    and r.course_number = s.course_number
    and r.section_number = s.section_number
where s.course_number is null
