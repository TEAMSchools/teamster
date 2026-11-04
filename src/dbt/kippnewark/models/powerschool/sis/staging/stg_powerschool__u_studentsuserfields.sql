with
    transformations as (
        select
            cr_prevschoolname,
            infosnap_id,
            infosnap_opt_in,
            media_release,
            newark_enrollment_number,
            rides_staff,

            cast(studentsdcid as int) as studentsdcid,
            safe_cast(c_504_status as int) as c_504_status,
        from {{ source("powerschool_dlt", "u_studentsuserfields") }}
    )

select *, if(c_504_status = 1, true, false) as is_504,
from transformations
