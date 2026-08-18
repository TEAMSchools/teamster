with
    -- not a join: schedule repeats a student/course-period pair on ~299
    -- combinations, and joining it as a table would double those grades.
    -- grain projection: student_id, course_period_id are the partition key
    -- itself; not a mask for upstream duplicates
    student_course_periods as (
        select distinct student_id, course_period_id,
        from {{ ref("stg_focus__schedule") }}
    ),

    -- An assignment is assigned to many sections, so the link alone fans a
    -- grade out. Intersecting with the student's own sections picks exactly
    -- one. Inner joins here are deliberate: this CTE holds only grades whose
    -- course period resolved, and it is LEFT joined back on below so the rest
    -- survive.
    grade_course_periods as (
        select
            gg.id as student_gradebook_grade_id,

            ajcp.course_period_id,
            ajcp.marking_period_id,
            ajcp.assigned_date,
            ajcp.due_date,
            ajcp.publish_date,
        from {{ ref("stg_focus__gradebook_grades") }} as gg
        inner join
            {{ ref("stg_focus__gradebook_assignments_join_course_periods") }} as ajcp
            on gg.assignment_id = ajcp.assignment_id
        inner join
            student_course_periods as scp
            on gg.student_id = scp.student_id
            and ajcp.course_period_id = scp.course_period_id
    )

select
    gg.id as student_gradebook_grade_id,
    gg.student_id,
    gg.assignment_id,
    gg.standard_id,
    gg.points,
    gg.possible_points,
    gg.letter_grade,
    gg.exclude_from_average,
    gg.late,
    gg.highlight,
    gg.comment,
    gg.comment_codes,
    gg.accommodations,
    gg.last_updated_user,
    gg.last_updated_date,

    gcp.course_period_id,
    gcp.marking_period_id,
    gcp.assigned_date,
    gcp.due_date,
    gcp.publish_date,

    ga.assignment_type_id,
    ga.title as assignment_title,
    ga.points as assignment_points,
    ga.description as assignment_description,
    ga.exclude_from_average as assignment_exclude_from_average,

    gat.title as assignment_type_title,

    atjcp.final_grade_percent as assignment_type_final_grade_percent,
    atjcp.drop_lowest_grades as assignment_type_drop_lowest_grades,

from {{ ref("stg_focus__gradebook_grades") }} as gg
left join grade_course_periods as gcp on gg.id = gcp.student_gradebook_grade_id
left join
    {{ ref("stg_focus__gradebook_assignments") }} as ga
    on gg.assignment_id = ga.assignment_id
left join
    {{ ref("stg_focus__gradebook_assignment_types") }} as gat
    on ga.assignment_type_id = gat.assignment_type_id
-- the triple, not the pair: the same category and section repeat across marking
-- periods with different weights
left join
    {{ ref("stg_focus__gradebook_assignment_types_join_course_periods") }} as atjcp
    on ga.assignment_type_id = atjcp.assignment_type_id
    and gcp.course_period_id = atjcp.course_period_id
    and gcp.marking_period_id = atjcp.marking_period_id
