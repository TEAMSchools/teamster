with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__assignmentscore"),
                partition_by="assignmentscoreid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        actualscoregradescaledcid,
        altnumericgrade,
        altscoregradescaledcid,
        assignmentscoreid,
        assignmentsectionid,
        authoredbyuc,
        hasretake,
        isabsent,
        iscollected,
        isexempt,
        isincomplete,
        islate,
        ismissing,
        scoregradescaledcid,
        scorenumericgrade,
        scorepercent,
        scorepoints,
        studentsdcid,
        whomodifiedid,
        yearid
    ),

    /* column transformations */
    actualscoregradescaledcid.int_value as actualscoregradescaledcid,
    altscoregradescaledcid.int_value as altscoregradescaledcid,
    assignmentscoreid.int_value as assignmentscoreid,
    assignmentsectionid.int_value as assignmentsectionid,
    authoredbyuc.int_value as authoredbyuc,
    hasretake.int_value as hasretake,
    isabsent.int_value as isabsent,
    iscollected.int_value as iscollected,
    isexempt.int_value as isexempt,
    isincomplete.int_value as isincomplete,
    islate.int_value as islate,
    ismissing.int_value as ismissing,
    scoregradescaledcid.int_value as scoregradescaledcid,
    studentsdcid.int_value as studentsdcid,
    whomodifiedid.int_value as whomodifiedid,
    yearid.int_value as yearid,

    altnumericgrade.bytes_decimal_value as altnumericgrade,
    scorenumericgrade.bytes_decimal_value as scorenumericgrade,
    scorepercent.bytes_decimal_value as scorepercent,

    coalesce(
        scorepoints.bytes_decimal_value, scorepoints.int_value, scorepoints.double_value
    ) as scorepoints,
from deduplicate
