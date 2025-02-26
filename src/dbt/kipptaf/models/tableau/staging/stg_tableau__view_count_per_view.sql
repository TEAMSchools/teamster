select
    *,
    lower(`user_name`) as user_name_lower,
    concat(
        'https://tableau.kipp.org/t/KIPPNJ/views/', vc.view_url, '?:embed=y'
    ) as `url`,
    parse_timestamp('%m/%d/%Y %I:%M:%S %p', created_at) as created_at_timestamp,
    datetime(
        parse_timestamp('%m/%d/%Y %I:%M:%S %p', created_at),
        '{{ var("local_timezone") }}'
    ) as created_at_local,

from {{ source("tableau", "src_tableau__view_count_per_view") }}
