with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__emailaddress"),
                partition_by="emailaddressid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (emailaddressid),

    /* column transformations */
    emailaddressid.int_value as emailaddressid,
from deduplicate
