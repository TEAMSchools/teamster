with
    subject_disciplines as (
        -- grain projection, not dup-masking: several courses share a subject
        select distinct illuminate_subject_area, discipline,
        from {{ ref("stg_google_sheets__assessments__course_subject_crosswalk") }}
    )

select
    r.region,
    r.module_type,
    r.grade_min,
    r.grade_max,
    r.goal,
    r.goal_offset,

    sd.illuminate_subject_area,
from {{ ref("stg_google_sheets__assessments__module_goal_rules") }} as r
inner join subject_disciplines as sd on r.discipline = sd.discipline

union all

select
    region,
    module_type,
    grade_min,
    grade_max,
    goal,
    goal_offset,

    cast(null as string) as illuminate_subject_area,
from {{ ref("stg_google_sheets__assessments__module_goal_rules") }}
where discipline is null
