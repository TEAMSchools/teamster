with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__prefs"),
                partition_by="dcid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (dcid, id, schoolid, yearid, userid, whomodifiedid),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    schoolid.int_value as schoolid,
    yearid.int_value as yearid,
    userid.int_value as userid,
    whomodifiedid.int_value as whomodifiedid,
from deduplicate
