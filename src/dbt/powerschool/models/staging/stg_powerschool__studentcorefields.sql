{%- set lep_status_true = ["1", "YES", "Y"] -%}

with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__studentcorefields"),
                partition_by="studentsdcid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

select
    * except (studentsdcid, lep_status),

    /* column transformations */
    studentsdcid.int_value as studentsdcid,

    if(lep_status in unnest({{ lep_status_true }}), true, false) as lep_status,
    if(homeless_code in ('Y1', 'Y2'), true, false) as is_homeless,
from deduplicate
