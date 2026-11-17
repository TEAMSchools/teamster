with
    observations as (
        select
            *,

            /*
                TODO(#6426): Grow keeps the type an observation was submitted
                with, and this form once submitted as Comments. Key it to
                Teacher Reflection by form name until those submissions age out.
            */
            if(
                rubric_name = 'Teacher Reflection',
                -- Performance Management: Teacher Reflection
                '667d84c657cfd7001154b630',
                observation_type
            ) as observation_type_tag_id,
        from {{ ref("stg_schoolmint_grow__observations") }}
    )

select
    o.observation_id,
    o.rubric_id,
    o.rubric_name,
    o.score,
    o.list_two_column_a_str as glows,
    o.list_two_column_b_str as grows,
    o.locked,
    o.observed_at,
    o.observed_at_date_local,
    o.academic_year,
    o.is_published,
    o.magic_notes_text,

    s.name as school_name,

    ot.staff_observation_type_key,
    ot.name as observation_type_name,
    ot.abbreviation as observation_type_abbreviation,

    gt2.name as observation_course,

    gt3.name as observation_grade,

    loc.location_key,

    safe_cast(ut.internal_id as int) as teacher_internal_id,

    safe_cast(uo.internal_id as int) as observer_internal_id,

    {{ dbt_utils.generate_surrogate_key(["o.rubric_id"]) }}
    as staff_observation_rubric_key,
from observations as o
left join {{ ref("stg_schoolmint_grow__users") }} as ut on o.teacher_id = ut.user_id
left join {{ ref("stg_schoolmint_grow__users") }} as uo on o.observer_id = uo.user_id
left join
    {{ ref("stg_schoolmint_grow__schools") }} as s
    on o.teaching_assignment_school = s.school_id
left join
    {{ ref("int_schoolmint_grow__observation_types") }} as ot
    on o.observation_type_tag_id = ot.tag_id
left join
    {{ ref("stg_schoolmint_grow__generic_tags") }} as gt2
    on o.teaching_assignment_course = gt2.tag_id
left join
    {{ ref("stg_schoolmint_grow__generic_tags") }} as gt3
    on o.teaching_assignment_grade = gt3.tag_id
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on s.school_id = loc.grow_location_id
    and not loc.is_pathways
    and loc.location_name <> 'KIPP Whittier Elementary'
