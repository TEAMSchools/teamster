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
        select
            * except (studentsdcid, c_504_status),

            /* column transformations */
            studentsdcid.int_value as studentsdcid,
            safe_cast(c_504_status as int) as c_504_status,

            {% if project_name == "kippmiami" %}
                if(is_gifted.int_value = 1, 'Y', 'N') as gifted_and_talented,
            {% endif %}
        from deduplicate
    )

select *, if(c_504_status = 1, true, false) as is_504,
from transformations
