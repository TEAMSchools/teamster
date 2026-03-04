select
    * except (
        coursesdcid,
        exclude_course_submission_tf,
        sla_include_tf,
        whencreated,
        whenmodified,
        source_file_name
    ),

    cast(coursesdcid as int) as coursesdcid,
    cast(exclude_course_submission_tf as int) as exclude_course_submission_tf,
    cast(sla_include_tf as int) as sla_include_tf,

    parse_timestamp('%m/%d/%Y', whencreated) as whencreated,
    parse_timestamp('%m/%d/%Y', whenmodified) as whenmodified,
from {{ source("powerschool_sftp", "src_powerschool__s_nj_crs_x") }}
