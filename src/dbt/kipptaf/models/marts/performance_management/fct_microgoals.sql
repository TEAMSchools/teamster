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
            grow_users.internal_id_int as employee_number,
            assignments.assignment_id,
            assignments.created_date_local as assignment_date,
            assignments.creator_name,
            microgoals.tag_name as goal_name,
            microgoals.strand_name,
            microgoals.bucket_name,
        from grow_users
        left join assignments on grow_users.user_id = assignments.user_id
        left join tags on assignments.assignment_id = tags.assignment_id
        left join microgoals on tags.tag_id = microgoals.tag_id

    )

select *,
from final
where goal_name is not null
