select
    o.observation_id,
    o.rubric_id,
    o.rubric_name,
    o.score,
    o.score_averaged_by_strand,
    o.glows,
    o.grows,
    o.locked,
    o.observed_at,
    o.observed_at_date_local,
    o.academic_year,
    o.is_published,

    s.name as school_name,

    gt.name as observation_type_name,
    gt.abbreviation as observation_type_abbreviation,

    safe_cast(ut.internal_id as int) as teacher_internal_id,

    safe_cast(uo.internal_id as int) as observer_internal_id,
from {{ ref("stg_schoolmint_grow__observations") }} as o
left join {{ ref("stg_schoolmint_grow__users") }} as ut on o.teacher_id = ut.user_id
left join {{ ref("stg_schoolmint_grow__users") }} as uo on o.observer_id = uo.user_id
left join
    {{ ref("stg_schoolmint_grow__schools") }} as s
    on o.teaching_assignment_school = s.school_id
left join
    {{ ref("stg_schoolmint_grow__generic_tags") }} as gt
    on o.observation_type = gt.tag_id
