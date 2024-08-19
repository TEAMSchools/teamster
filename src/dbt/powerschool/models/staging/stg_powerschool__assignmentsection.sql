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
        assignmentsectionid,
        yearid,
        sectionsdcid,
        assignmentid,
        relatedgradescaleitemdcid,
        scoreentrypoints,
        extracreditpoints,
        `weight`,
        totalpointvalue,
        iscountedinfinalgrade,
        isscoringneeded,
        publishdaysbeforedue,
        publishedscoretypeid,
        isscorespublish,
        maxretakeallowed,
        whomodifiedid
    ),

    assignmentsectionid.int_value as assignmentsectionid,
    yearid.int_value as yearid,
    sectionsdcid.int_value as sectionsdcid,
    assignmentid.int_value as assignmentid,
    relatedgradescaleitemdcid.int_value as relatedgradescaleitemdcid,
    extracreditpoints.bytes_decimal_value as extracreditpoints,
    weight.bytes_decimal_value as `weight`,
    totalpointvalue.bytes_decimal_value as totalpointvalue,
    iscountedinfinalgrade.int_value as iscountedinfinalgrade,
    isscoringneeded.int_value as isscoringneeded,
    publishdaysbeforedue.int_value as publishdaysbeforedue,
    publishedscoretypeid.int_value as publishedscoretypeid,
    isscorespublish.int_value as isscorespublish,
    maxretakeallowed.int_value as maxretakeallowed,
    whomodifiedid.int_value as whomodifiedid,

    coalesce(
        scoreentrypoints.bytes_decimal_value,
        scoreentrypoints.double_value,
        scoreentrypoints.int_value
    ) as scoreentrypoints,
from deduplicate
