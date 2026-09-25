-- Every student_id shipped in enrollments.csv must resolve to a row in
-- students.csv. students.csv is scoped to the current academic year while
-- enrollments.csv is not, so a region whose SIS is frozen at a prior year keeps
-- shipping enrollments against students Clever no longer has -- the failure mode
-- that left Miami with live enrollment rows and zero students.
with
    enrollment_students as (
        select cast(student_id as string) as student_id,
        from {{ ref("rpt_clever__enrollments") }}
    ),

    feed_students as (
        -- grain projection: students.csv is one row per student per contact slot
        -- per phone type; project it back to the student grain it rosters
        select distinct student_id, from {{ ref("rpt_clever__students") }}
    )

select e.student_id, count(*) as orphan_rows,
from enrollment_students as e
left join feed_students as s on e.student_id = s.student_id
where s.student_id is null
group by e.student_id
