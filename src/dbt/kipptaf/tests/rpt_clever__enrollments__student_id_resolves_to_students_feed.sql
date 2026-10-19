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
