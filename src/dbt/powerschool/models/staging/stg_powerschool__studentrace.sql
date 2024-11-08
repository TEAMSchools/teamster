with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__studentrace"),
                partition_by="dcid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (dcid, id, studentid),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    studentid.int_value as studentid,
from deduplicate
