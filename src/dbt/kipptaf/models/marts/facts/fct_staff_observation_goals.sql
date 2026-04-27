select
    {{
        dbt_utils.generate_surrogate_key(
            ["gu.internal_id_int", "a.assignment_id", "m.tag_id"]
        )
    }} as staff_observation_goal_key,

    if(
        gu.internal_id_int is not null,
        {{ dbt_utils.generate_surrogate_key(["gu.internal_id_int"]) }},
        cast(null as string)
    ) as teacher_staff_key,

    if(
        sr_creator.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["sr_creator.employee_number"]) }},
        cast(null as string)
    ) as creator_staff_key,

    {{ dbt_utils.generate_surrogate_key(["m.tag_id"]) }}
    as staff_observation_goal_type_key,

    a.created_date_local as assignment_date,
    a.created as assignment_created_timestamp,

    {{
        date_to_fiscal_year(
            date_field="a.created_date_local",
            start_month=7,
            year_source="start",
        )
    }} as academic_year,
from {{ ref("stg_schoolmint_grow__assignments") }} as a
inner join {{ ref("stg_schoolmint_grow__users") }} as gu on a.user_id = gu.user_id
inner join
    {{ ref("int_schoolmint_grow__assignments__tags") }} as t
    on a.assignment_id = t.assignment_id
inner join {{ ref("int_schoolmint_grow__microgoals") }} as m on t.tag_id = m.tag_id
left join
    {{ ref("int_people__staff_roster") }} as sr_creator
    on a.creator_name = sr_creator.formatted_name
where gu.internal_id_int is not null
