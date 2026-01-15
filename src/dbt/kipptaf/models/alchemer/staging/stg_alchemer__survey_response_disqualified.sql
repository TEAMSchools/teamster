select
    safe_cast(_dagster_partition_key as int) as survey_id,
    safe_cast(id as int) as id,

    concat(_dagster_partition_key, '_', id) as surrogate_key,
from {{ source("alchemer", "src_alchemer__survey_response_disqualified") }}
