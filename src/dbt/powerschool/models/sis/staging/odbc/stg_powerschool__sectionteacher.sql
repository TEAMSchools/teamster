select
    * except (
        id, teacherid, sectionid, roleid, allocation, priorityorder, whomodifiedid
    ),

    /* column transformations */
    id.int_value as id,
    teacherid.int_value as teacherid,
    sectionid.int_value as sectionid,
    roleid.int_value as roleid,
    allocation.bytes_decimal_value as allocation,
    priorityorder.int_value as priorityorder,
    whomodifiedid.int_value as whomodifiedid,
from {{ source("powerschool_odbc", "src_powerschool__sectionteacher") }}
