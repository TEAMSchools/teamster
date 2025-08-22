with
    -- trunk-ignore(sqlfluff/ST03)
    attendance as (
        select
            _file_name,
            att_comment,
            att_date,
            att_mode_code,

            /* column transformations */
            id.int_value as id,
            attendance_codeid.int_value as attendance_codeid,
            calendar_dayid.int_value as calendar_dayid,
            schoolid.int_value as schoolid,
            studentid.int_value as studentid,
            yearid.int_value as yearid,
        from {{ source("powerschool_odbc", "src_powerschool__attendance") }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="attendance", partition_by="id", order_by="_file_name desc"
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select * except (_file_name),
from deduplicate
