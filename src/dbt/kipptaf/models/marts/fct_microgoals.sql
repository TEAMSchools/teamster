with

    grow_users as (select *, from {{ ref("stg_schoolmint_grow__users") }}),

    assignments as (
        select user_id, assignment_id, created_date_local, creator_name,
        from {{ ref("stg_schoolmint_grow__assignments") }}
    ),

    /* need to import to link assignment to microgoal name and categories */
    tags as (select *, from {{ ref("int_schoolmint_grow__assignments__tags") }}),

    microgoals as (select *, from {{ ref("int_schoolmint_grow__microgoals") }}),

    final as (
        select
            gu.internal_id_int as employee_number,

            a.assignment_id,
            a.created_date_local as assignment_date,
            a.creator_name,

            m.tag_name as goal_name,
            m.strand_name,
            m.bucket_name,
        from grow_users as gu
        left join assignments as a on gu.user_id = a.user_id
        left join tags as t on a.assignment_id = t.assignment_id
        left join microgoals as m on t.tag_id = m.tag_id

    )

select *,
from final
where goal_name is not null
