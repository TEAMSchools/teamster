with
    deduplicate as (
        /* students object might contain duplicate ids */
        {{
            dbt_utils.deduplicate(
                relation=source("overgrad", "src_overgrad__students"),
                partition_by="id",
                order_by="id desc",
            )
        }}
    )

select s.id, cfv.custom_field_id, cfv.number, cfv.date, cfv.select,
from deduplicate as s
cross join unnest(s.custom_field_values) as cfv
