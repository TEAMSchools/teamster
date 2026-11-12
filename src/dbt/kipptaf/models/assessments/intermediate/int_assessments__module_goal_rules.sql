with
    rules as (
        select
            region,
            module_type,
            discipline,
            grade_min,
            grade_max,
            goal,
            goal_offset,

            (goal is null) != (goal_offset is null)
            and grade_min <= grade_max
            and (goal is null or goal between 0 and 1)
            and (goal_offset is null or abs(goal_offset) < 1) as is_well_formed,
        from {{ ref("stg_google_sheets__assessments__module_goal_rules") }}
    ),

    rule_overlaps as (
        -- counts the rule itself, so 1 means no other well-formed rule overlaps
        select
            a.region,
            a.module_type,
            a.discipline,
            a.grade_min,
            a.grade_max,
            a.goal,
            a.goal_offset,

            count(*) as n_overlapping_rules,
        from rules as a
        inner join
            rules as b
            on a.region = b.region
            and a.module_type = b.module_type
            and a.grade_min <= b.grade_max
            and a.grade_max >= b.grade_min
            and (
                a.discipline = b.discipline
                or a.discipline is null
                or b.discipline is null
            )
            and b.is_well_formed
        where a.is_well_formed
        group by
            a.region,
            a.module_type,
            a.discipline,
            a.grade_min,
            a.grade_max,
            a.goal,
            a.goal_offset
    ),

    subject_disciplines as (
        -- a subject the crosswalk splits across 2 disciplines matches no rule
        select cw.illuminate_subject_area, max(cw.discipline) as discipline,
        from {{ ref("stg_google_sheets__assessments__course_subject_crosswalk") }} as cw
        where cw.illuminate_subject_area is not null
        group by cw.illuminate_subject_area
        having count(distinct cw.discipline) = 1
    )

select
    r.region,
    r.module_type,
    r.grade_min,
    r.grade_max,
    r.goal,
    r.goal_offset,

    sd.illuminate_subject_area,
from rule_overlaps as r
inner join subject_disciplines as sd on r.discipline = sd.discipline
where r.n_overlapping_rules = 1

union all

select
    region,
    module_type,
    grade_min,
    grade_max,
    goal,
    goal_offset,

    cast(null as string) as illuminate_subject_area,
from rule_overlaps
where discipline is null and n_overlapping_rules = 1
