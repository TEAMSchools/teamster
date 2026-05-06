select
    {{ dbt_utils.generate_surrogate_key(["tag_id"]) }} as staff_observation_type_key,
    tag_id,
    abbreviation,
    `name`,
from {{ ref("stg_schoolmint_grow__generic_tags") }}
where tag_type = 'observationtypes' and archived_at is null
