with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("adp_workforce_now", "person_history"),
                partition_by="worker_id",
                order_by="_fivetran_synced desc",
            )
        }}
    )

select *,  -- noqa: AM04
from deduplicate
