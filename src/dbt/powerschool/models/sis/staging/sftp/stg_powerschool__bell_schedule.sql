select
    * except (attendance_conversion_id, dcid, id, schoolid, year_id, source_file_name),

    cast(attendance_conversion_id as int) as attendance_conversion_id,
    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(schoolid as int) as schoolid,
    cast(year_id as int) as year_id,
from {{ source("powerschool_sftp", "src_powerschool__bell_schedule") }}
