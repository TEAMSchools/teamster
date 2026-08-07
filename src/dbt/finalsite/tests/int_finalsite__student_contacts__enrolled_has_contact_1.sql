{{ config(severity="warn") }}

-- A currently enrolled student with no parent slot at all. The model itself
-- stays SIS-agnostic and emits rows for every student record including
-- prospects and applicants, who legitimately have no parent on file yet -- so
-- the enrolled scope lives here, in the test, rather than in the model.
-- Every row is a Finalsite data-entry gap: a missing `primary`/`financial`
-- flag, or a parent whose own contact record is miskeyed with a student status
-- and therefore fails the adult guard.
select s.finalsite_enrollment_id, s.grade_name, s.school_year_start,
from {{ ref("stg_finalsite__contacts") }} as s
where
    s.status = 'enrolled'
    and s.school_year_start = {{ var("current_academic_year") }}
    and not exists (
        select 1
        from {{ ref("int_finalsite__student_contacts") }} as c
        where
            c.finalsite_enrollment_id = s.finalsite_enrollment_id
            and c.contact_slot = 'contact_1'
    )
