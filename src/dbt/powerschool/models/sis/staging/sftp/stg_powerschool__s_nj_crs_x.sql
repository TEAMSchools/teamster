{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    * except (coursesdcid, exclude_course_submission_tf, sla_include_tf),

    /* column transformations */
    coursesdcid.int_value as coursesdcid,
    exclude_course_submission_tf.int_value as exclude_course_submission_tf,
    sla_include_tf.int_value as sla_include_tf,
from {{ source("powerschool", "src_powerschool__s_nj_crs_x") }}
