with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__pgfinalgrades"),
                partition_by="dcid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

    transformations as (
        select
            * except (
                calculatedpercent,
                citizenship,
                comment_value,
                dcid,
                grade,
                gradebooktype,
                id,
                isexempt,
                isincomplete,
                percent,
                points,
                pointspossible,
                sectionid,
                studentid,
                varcredit,
                whomodifiedid
            ),

            /* column transformations */
            nullif(grade, '--') as grade,
            nullif(citizenship, '') as citizenship,
            nullif(comment_value, '') as comment_value,

            /* records */
            dcid.int_value as dcid,
            id.int_value as id,
            sectionid.int_value as sectionid,
            studentid.int_value as studentid,
            points.double_value as points,
            pointspossible.double_value as pointspossible,
            varcredit.double_value as varcredit,
            gradebooktype.int_value as gradebooktype,
            calculatedpercent.double_value as calculatedpercent,
            isincomplete.int_value as isincomplete,
            isexempt.int_value as isexempt,
            whomodifiedid.int_value as whomodifiedid,

            if(grade = '--', null, percent.double_value) as percent,
        from deduplicate
    ),

    with_percent_decimal as (
        select *, percent / 100.0 as percent_decimal, from transformations
    )

select
    *,

    if(percent_decimal < 0.5, 0.5, percent_decimal) as percent_decimal_adjusted,
    if(percent_decimal < 0.5, 'F*', grade) as grade_adjusted,
from with_percent_decimal
