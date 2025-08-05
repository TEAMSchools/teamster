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
            -- actualscoregradescaledcid.int_value as actualscoregradescaledcid,
            -- altscoregradescaledcid.int_value as altscoregradescaledcid,
            -- authoredbyuc.int_value as authoredbyuc,
            -- hasretake.int_value as hasretake,
            -- isabsent.int_value as isabsent,
            -- iscollected.int_value as iscollected,
            -- isincomplete.int_value as isincomplete,
            -- scoregradescaledcid.int_value as scoregradescaledcid,
            -- whomodifiedid.int_value as whomodifiedid,
            -- yearid.int_value as yearid,
            -- altnumericgrade.bytes_decimal_value as altnumericgrade,
            -- scorenumericgrade.bytes_decimal_value as scorenumericgrade,
            -- scorepercent.bytes_decimal_value as scorepercent,
            coalesce(
                scorepoints.bytes_decimal_value,
                scorepoints.int_value,
                scorepoints.double_value
            ) as scorepoints,
        from {{ source("powerschool", "src_powerschool__assignmentscore") }}
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
