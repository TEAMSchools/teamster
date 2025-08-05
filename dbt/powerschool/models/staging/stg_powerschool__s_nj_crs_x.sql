with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__s_nj_crs_x"),
                partition_by="coursesdcid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (coursesdcid, exclude_course_submission_tf, sla_include_tf),

    /* column transformations */
    coursesdcid.int_value as coursesdcid,
    exclude_course_submission_tf.int_value as exclude_course_submission_tf,
    sla_include_tf.int_value as sla_include_tf,
from deduplicate
