{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

with
    -- trunk-ignore(sqlfluff/ST03)
    assignmentscore as (
        select
            _file_name,
            actualscoreentered,

            /* column transformations */
            assignmentscoreid.int_value as assignmentscoreid,
            studentsdcid.int_value as studentsdcid,
            assignmentsectionid.int_value as assignmentsectionid,
            isexempt.int_value as isexempt,
            islate.int_value as islate,
            ismissing.int_value as ismissing,

            coalesce(
                scorepoints.bytes_decimal_value,
                scorepoints.int_value,
                scorepoints.double_value
            ) as scorepoints,
        from {{ source("powerschool_odbc", "src_powerschool__assignmentscore") }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="assignmentscore",
                partition_by="assignmentscoreid",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select * except (_file_name),
from deduplicate
