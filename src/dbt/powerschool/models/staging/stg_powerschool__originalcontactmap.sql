with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__originalcontactmap"),
                partition_by="originalcontactmapid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (originalcontactmapid, studentcontactassocid),

    /* column transformations */
    originalcontactmapid.int_value as originalcontactmapid,
    studentcontactassocid.int_value as studentcontactassocid,
from deduplicate
