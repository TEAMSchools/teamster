with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__phonenumber"),
                partition_by="phonenumberid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (phonenumberid, issms),

    /* column transformations */
    phonenumberid.int_value as phonenumberid,
    issms.int_value as issms,
from deduplicate
