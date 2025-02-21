select
    *,
    timestamp(
        datetime(
            timestamp(parse_timestamp('%m/%d/%Y %I:%M:%S %p', created_at)),
            'America/New_York'
        )
    ) as created_at_local_new_york,

from {{ source("tableau", "src_tableau__view_count_per_view") }}
