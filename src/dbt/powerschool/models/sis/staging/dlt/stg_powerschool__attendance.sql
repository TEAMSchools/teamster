select
    att_comment,
    att_mode_code,

    cast(attendance_codeid as int) as attendance_codeid,
    cast(calendar_dayid as int) as calendar_dayid,
    cast(id as int) as id,
    cast(schoolid as int) as schoolid,
    cast(studentid as int) as studentid,
    cast(yearid as int) as yearid,

    cast(att_date as date) as att_date,
from {{ source("powerschool_dlt", "attendance") }}
