with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("deanslist", "src_deanslist__incidents"),
                partition_by="IncidentID",
                order_by="_file_name desc",
            )
        }}
    )

select *
from deduplicate
