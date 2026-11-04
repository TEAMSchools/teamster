with
    transformations as (
        select
            finalgradename,
            overridefg,
            calculatedgrade,
            ip_address,
            whomodifiedtype,
            transaction_date,
            executionid,

            cast(startdate as date) as startdate,
            cast(enddate as date) as enddate,
            cast(lastgradeupdate as date) as lastgradeupdate,
            cast(dcid as int) as dcid,
            cast(id as int) as id,
            cast(sectionid as int) as sectionid,
            cast(studentid as int) as studentid,
            cast(points as float64) as points,
            cast(pointspossible as float64) as pointspossible,
            cast(varcredit as float64) as varcredit,
            cast(gradebooktype as int) as gradebooktype,
            cast(calculatedpercent as float64) as calculatedpercent,
            cast(isincomplete as int) as isincomplete,
            cast(isexempt as int) as isexempt,
            cast(whomodifiedid as int) as whomodifiedid,

            nullif(grade, '--') as grade,
            nullif(citizenship, '') as citizenship,
            nullif(comment_value, '') as comment_value,

            if(grade = '--', null, cast(`percent` as float64)) as `percent`,
        from {{ source("powerschool_dlt", "pgfinalgrades") }}
    ),

    with_percent_decimal as (
        select *, `percent` / 100.0 as percent_decimal, from transformations
    )

select
    *,

    if(percent_decimal < 0.5, 0.5, percent_decimal) as percent_decimal_adjusted,
    if(percent_decimal < 0.5, 'F*', grade) as grade_adjusted,
from with_percent_decimal
