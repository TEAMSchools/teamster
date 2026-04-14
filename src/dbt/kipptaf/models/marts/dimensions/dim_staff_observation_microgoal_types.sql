select
    {{ dbt_utils.generate_surrogate_key(["tag_id"]) }}
    as staff_observation_microgoal_type_key,

    tag_id as goal_tag_id,
    tag_name as goal_name,
    strand_name,
    bucket_name,
    goal_type_name,
from {{ ref("int_schoolmint_grow__microgoals") }}
