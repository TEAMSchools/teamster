{{ config(severity="error") }}

-- every resolved seed row must name a real PowerSchool section, or its treated
-- students silently vanish through the inner join in
-- int_ignite__treatment_assignment
with
    resolved as (
        select ref_id, school_name, academic_year, course_number, section_number,
        from {{ ref("seed_ignite__treatment_sections") }}
        where status = 'resolved'
    ),

    sections as (
        select distinct school_name, academic_year, course_number, section_number,
        from {{ ref("int_extracts__course_enrollments_by_term") }}
        where academic_year in ({{ var("ignite_academic_years") | join(", ") }})
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
