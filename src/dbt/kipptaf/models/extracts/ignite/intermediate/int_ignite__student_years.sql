with
    /* grain projection, not dup-masking: one row per resolved study year */
    study_years as (
        select distinct academic_year,
        from {{ ref("stg_google_sheets__ignite__treatment_sections") }}
        where status = 'resolved'
    )

-- rn_year = 1 is the student's latest enrollment that year
select e.student_number, e.academic_year,
from {{ ref("int_extracts__student_enrollments") }} as e
inner join study_years as y on e.academic_year = y.academic_year
where
    e.rn_year = 1
    and e.state = 'NJ'
    and e.grade_level between 9 and 12
    and e.student_number is not null
