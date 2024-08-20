with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__assignmentsection"),
                partition_by="assignmentsectionid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        assignmentid,
        assignmentsectionid,
        extracreditpoints,
        iscountedinfinalgrade,
        isscorespublish,
        isscoringneeded,
        maxretakeallowed,
        publishdaysbeforedue,
        publishedscoretypeid,
        relatedgradescaleitemdcid,
        sectionsdcid,
        `weight`,
        whomodifiedid,
        yearid
    ),

    assignmentid.int_value as assignmentid,
    assignmentsectionid.int_value as assignmentsectionid,
    extracreditpoints.bytes_decimal_value as extracreditpoints,
    iscountedinfinalgrade.int_value as iscountedinfinalgrade,
    isscorespublish.int_value as isscorespublish,
    isscoringneeded.int_value as isscoringneeded,
    maxretakeallowed.int_value as maxretakeallowed,
    publishdaysbeforedue.int_value as publishdaysbeforedue,
    publishedscoretypeid.int_value as publishedscoretypeid,
    relatedgradescaleitemdcid.int_value as relatedgradescaleitemdcid,
    sectionsdcid.int_value as sectionsdcid,
    weight.bytes_decimal_value as `weight`,
    whomodifiedid.int_value as whomodifiedid,
    yearid.int_value as yearid,

    coalesce(
        scoreentrypoints.bytes_decimal_value,
        scoreentrypoints.double_value,
        scoreentrypoints.int_value
    ) as scoreentrypoints,
    coalesce(
        totalpointvalue.bytes_decimal_value,
        totalpointvalue.double_value,
        totalpointvalue.int_value
    ) as totalpointvalue,
from deduplicate
