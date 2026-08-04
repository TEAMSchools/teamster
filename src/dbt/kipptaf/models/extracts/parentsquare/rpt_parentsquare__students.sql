-- Neither `student_email` nor `state_student_id` is sent. Both are optional in
-- ParentSquare's spec, and Ops excluded them: a student email address triggers
-- ParentSquare's automatic account-creation mail to every student in the file
-- (~6,800 for Newark) and student logins are not part of this deployment, while
-- the state id has no consumer on the ParentSquare side. Adding either back is a
-- column add here plus a properties entry — no upstream change.
select
    student_first_name as first_name,
    student_last_name as last_name,

    cast(schoolid as string) as school_id,
    cast(student_number as string) as student_id,

    -- ParentSquare's grade scale runs -4..12 with K = 0, which the Newark
    -- grade_level domain (0..12) already satisfies, so this is a plain cast. A
    -- PreK grade would need a mapping (PreK1 = -4, PreK2 = -3, Junior K = -2,
    -- Transitional K = -1); Newark operates none.
    cast(grade_level as string) as grade_level,

    -- ParentSquare reads 1 as active and 0 as incoming, which is what a
    -- pre-registered (enroll_status -1) student is, so those rows belong in the
    -- feed rather than being filtered out.
    if(enroll_status = 0, '1', '0') as `status`,
from {{ ref("int_extracts__student_enrollments") }}
where
    _dbt_source_project = 'kippnewark'
    and academic_year = {{ var("current_academic_year") }}
    and rn_year = 1
    and not is_out_of_district
    and enroll_status in (0, -1)
