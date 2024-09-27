with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__period"),
                partition_by="dcid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (dcid, id, schoolid, year_id, period_number, sort_order),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    schoolid.int_value as schoolid,
    year_id.int_value as year_id,
    period_number.int_value as period_number,
    sort_order.int_value as sort_order,
from deduplicate
