with
    transformations as (
        select
            * except (studentsdcid, c_504_status),

            /* column transformations */
            studentsdcid.int_value as studentsdcid,

            safe_cast(c_504_status as int) as c_504_status,
        from {{ source("powerschool_odbc", "src_powerschool__u_studentsuserfields") }}
    )

select *, if(c_504_status = 1, true, false) as is_504,
from transformations
