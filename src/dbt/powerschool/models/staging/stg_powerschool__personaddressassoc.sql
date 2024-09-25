with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__personaddressassoc"),
                partition_by="personaddressassocid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        personaddressassocid,
        personid,
        personaddressid,
        addresstypecodesetid,
        addresspriorityorder
    ),

    /* column transformations */
    personaddressassocid.int_value as personaddressassocid,
    personid.int_value as personid,
    personaddressid.int_value as personaddressid,
    addresstypecodesetid.int_value as addresstypecodesetid,
    addresspriorityorder.int_value as addresspriorityorder,
from deduplicate
