select
    {{ dbt_utils.generate_surrogate_key(["tag_id"]) }} as staff_observation_type_key,

    tag_id as observation_type_id,
    `name` as observation_type_name,
    abbreviation as observation_type_abbreviation,
from {{ ref("stg_schoolmint_grow__generic_tags") }}
where tag_type = 'observationtypes' and archived_at is null
