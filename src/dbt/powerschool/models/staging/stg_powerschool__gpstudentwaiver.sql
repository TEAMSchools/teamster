with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__gpstudentwaiver"),
                partition_by="id.int_value",
                order_by="_file_name desc",
            )
        }}
    )

select
    authorizedby,
    waiveddate,

    /* records */
    gpwaiverconfigidforsource,
    gpwaiverconfigidforreason,

    id.int_value as id,
    studentid.int_value as studentid,
    gpnodeidforwaived.int_value as gpnodeidforwaived,
    gpnodeidforelective.int_value as gpnodeidforelective,
    gpwaiverconfigidfortype.int_value as gpwaiverconfigidfortype,
    credithourswaived.double_value as credithourswaived,
from deduplicate
