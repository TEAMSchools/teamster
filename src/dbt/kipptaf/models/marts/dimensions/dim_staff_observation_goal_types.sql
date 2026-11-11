with
    goals as (
        /* grain projection, not dup-masking: one row per (goal_tag_id, goal_name) */
        select distinct
            goal_tag_id, goal_name, strand_name, bucket_name, goal_type_name,
        from {{ ref("int_performance_management__observation_goals") }}
    )

select
    {{ staff_observation_goal_type_key("goal_tag_id", "goal_name") }}
    as staff_observation_goal_type_key,

    goal_name,
    strand_name,
    bucket_name,
    goal_type_name as goal_type,
from goals
