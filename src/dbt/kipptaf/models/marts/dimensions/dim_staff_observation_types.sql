select staff_observation_type_key, `name`, abbreviation,
from {{ ref("int_schoolmint_grow__observation_types") }}
