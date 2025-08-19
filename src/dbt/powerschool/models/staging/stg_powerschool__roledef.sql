select
    * except (id, rolemoduleid, islocked, isvisible, isenabled, sortorder),

    /* column transformations */
    id.int_value as id,
    rolemoduleid.int_value as rolemoduleid,
    islocked.int_value as islocked,
    isvisible.int_value as isvisible,
    isenabled.int_value as isenabled,
    sortorder.int_value as sortorder,
from {{ source("powerschool", "src_powerschool__roledef") }}
