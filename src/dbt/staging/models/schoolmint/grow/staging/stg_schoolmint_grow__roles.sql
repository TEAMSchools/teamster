select _id as role_id, `name`, category, district,
from {{ source("schoolmint_grow", "src_schoolmint_grow__roles") }}
where _dagster_partition_key = 'f'
