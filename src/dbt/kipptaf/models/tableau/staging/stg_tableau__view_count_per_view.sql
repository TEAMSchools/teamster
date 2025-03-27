with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("tableau", "src_tableau__view_count_per_view"),
                partition_by="id",
                order_by="extract_created desc",
            )
        }}
    ),

    view_count as (
        select
            * except (created_at_local),

            lower(user_name) as user_name_lower,
            concat(
                'https://tableau.kipp.org/t/KIPPNJ/views/', view_url, '?:embed=y'
            ) as `url`,

            parse_timestamp('%m/%d/%Y %I:%M:%S %p', created_at) as created_at_timestamp,
        from deduplicate
    )

select
    *,

    datetime(created_at_timestamp, '{{ var("local_timezone") }}') as created_at_local,
from view_count
