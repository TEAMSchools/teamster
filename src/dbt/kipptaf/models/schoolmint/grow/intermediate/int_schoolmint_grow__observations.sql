select
    o.observation_id,
    o.rubric_id,
    o.rubric_name,
    o.score,
    o.glows,
    o.grows,
    o.locked,
    o.observed_at,
    o.observed_at_date_local,
    o.academic_year,
    o.is_published,

    string_agg(mn.text, "; ") as magic_notes_text,

    s.name as school_name,

    gt.name as observation_type_name,
    gt.abbreviation as observation_type_abbreviation,

    gt2.name as observation_course,
    gt3.name as observation_grade,

    safe_cast(ut.internal_id as int) as teacher_internal_id,

    safe_cast(uo.internal_id as int) as observer_internal_id,
from {{ ref("stg_schoolmint_grow__observations") }} as o
left join
    {{ ref("stg_schoolmint_grow__observations__magic_notes") }} as mn
    on o.observation_id = mn.observation_id
left join {{ ref("stg_schoolmint_grow__users") }} as ut on o.teacher_id = ut.user_id
left join {{ ref("stg_schoolmint_grow__users") }} as uo on o.observer_id = uo.user_id
left join
    {{ ref("stg_schoolmint_grow__schools") }} as s
    on o.teaching_assignment_school = s.school_id
left join
    {{ ref("stg_schoolmint_grow__generic_tags") }} as gt
    on o.observation_type = gt.tag_id
left join
    {{ ref("stg_schoolmint_grow__generic_tags") }} as gt2
    on o.teaching_assignment_course = gt2.tag_id
left join
    {{ ref("stg_schoolmint_grow__generic_tags") }} as gt3
    on o.teaching_assignment_grade = gt3.tag_id
group by
    o.observation_id,
    o.rubric_id,
    o.rubric_name,
    o.score,
    o.glows,
    o.grows,
    o.locked,
    o.observed_at,
    o.observed_at_date_local,
    o.academic_year,
    o.is_published,
    s.name,
    gt.name,
    gt.abbreviation,
    gt2.name,
    gt3.name,
    ut.internal_id,
    uo.internal_id