with
    teammates as (select * from {{ ref("dim_teammates") }}),

    grow_users as (select * from {{ ref("stg_schoolmint_grow__users") }}),

    assignments as (
        select user_id, assignment_id, created_date_local, creator_name,
        from {{ ref("stg_schoolmint_grow__assignments") }}
    ),

    {# need to import to link assignment to microgoal name and categories #}
    tags as (select * from {{ ref("stg_schoolmint_grow__assignments__tags") }}),

    microgoals as (select * from {{ ref("stg_schoolmint_grow__microgoals") }}),

    final as (

        select
            teammates.employee_number,
            assignments.assignment_id as microgoal_assignment_id,
            assignments.created_date_local as microgoal_date,
            assignments.creator_name as microgoal_creator,
            microgoals.goal_name,
            microgoals.strand_name,
            microgoals.bucket_name,
        from teammates
        left join grow_users on teammates.employee_number = grow_users.internal_id_int
        left join assignments on grow_users.user_id = assignments.user_id
        left join tags on assignments.assignment_id = tags.assignment_id
        left join microgoals on tags.tag_id = microgoals.goal_tag_id
        {# filtering out microgoals that have been deleted from Grow #}
        where goal_name is not null
    )

select *
from final
