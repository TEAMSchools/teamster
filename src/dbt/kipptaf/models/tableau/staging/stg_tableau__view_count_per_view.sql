select *, from {{ source("tableau", "src_tableau__view_count_per_view") }}
