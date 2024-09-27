with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__personaddress"),
                partition_by="personaddressid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        personaddressid,
        statescodesetid,
        countrycodesetid,
        geocodelatitude,
        geocodelongitude
    ),

    /* column transformations */
    personaddressid.int_value as personaddressid,
    statescodesetid.int_value as statescodesetid,
    countrycodesetid.int_value as countrycodesetid,
    geocodelatitude.bytes_decimal_value as geocodelatitude,
    geocodelongitude.bytes_decimal_value as geocodelongitude,
from deduplicate
