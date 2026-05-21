select
    {{ dbt_utils.generate_surrogate_key(["tag_id"]) }}
    as staff_observation_goal_type_key,

    tag_name as goal_name,
    strand_name,
    bucket_name,
    goal_type_name as goal_type,
from {{ ref("int_schoolmint_grow__microgoals") }}
