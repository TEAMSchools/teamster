with
    transformations as (
        select
            cr_prevschoolname,
            infosnap_id,
            media_release,
            fleid,

            cast(studentsdcid as int) as studentsdcid,

            safe_cast(c_504_status as int) as c_504_status,

            if(is_gifted = 1, 'Y', 'N') as gifted_and_talented,
        from {{ source("powerschool_dlt", "u_studentsuserfields") }}
    )

select *, if(c_504_status = 1, true, false) as is_504,
from transformations
