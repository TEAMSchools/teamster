with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("instagram_business", "media_insights"),
                partition_by="id",
                order_by="_fivetran_synced desc",
            )
        }}
    )

select *, like_count + comment_count as total_like_comments,  -- noqa: AM04
from deduplicate
