with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("overgrad", "src_overgrad__admissions"),
                partition_by="id",
                order_by="updated_at desc",
            )
        }}
    )

select a.id, cfv.custom_field_id, cfv.number, cfv.date, cfv.select,
from deduplicate as a
cross join unnest(a.custom_field_values) as cfv
