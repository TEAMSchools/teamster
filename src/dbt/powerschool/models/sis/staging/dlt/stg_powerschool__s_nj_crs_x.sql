select
    * replace (
        cast(coursesdcid as int) as coursesdcid,
        cast(exclude_course_submission_tf as int) as exclude_course_submission_tf,
        cast(sla_include_tf as int) as sla_include_tf
    ),
from {{ source("powerschool_dlt", "s_nj_crs_x") }}
