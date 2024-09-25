with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "powerschool", "src_powerschool__u_studentsuserfields"
                ),
                partition_by="studentsdcid.int_value",
                order_by="_file_name desc",
            )
        }}
    ),

    transformations as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            * except (studentsdcid, c_504_status),

            /* column transformations */
            studentsdcid.int_value as studentsdcid,
            safe_cast(c_504_status as int) as c_504_status,
        from deduplicate
    )

select *, if(c_504_status = 1, true, false) as is_504,
from transformations
