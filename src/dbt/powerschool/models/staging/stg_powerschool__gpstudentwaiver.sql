select
    authorizedby,
    waiveddate,

    /* records */
    id.int_value as id,
    studentid.int_value as studentid,
    credithourswaived.double_value as credithourswaived,
    gpnodeidforelective.int_value as gpnodeidforelective,
    gpnodeidforwaived.int_value as gpnodeidforwaived,
    gpwaiverconfigidforreason.int_value as gpwaiverconfigidforreason,
    gpwaiverconfigidforsource.int_value as gpwaiverconfigidforsource,
    gpwaiverconfigidfortype.int_value as gpwaiverconfigidfortype,
from {{ source("powerschool", "src_powerschool__gpstudentwaiver") }}
