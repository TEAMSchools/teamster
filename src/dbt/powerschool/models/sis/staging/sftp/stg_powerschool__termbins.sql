select
    * except (
        collect,
        currentgrade,
        dcid,
        gradescaleid,
        id,
        schoolid,
        showonspreadsht,
        storegrades,
        suppressltrgrd,
        suppresspercentscr,
        termid,
        whomodifiedid,
        yearid
    ),

    cast(collect as int) as collect,
    cast(currentgrade as int) as currentgrade,
    cast(dcid as int) as dcid,
    cast(gradescaleid as int) as gradescaleid,
    cast(id as int) as id,
    cast(schoolid as int) as schoolid,
    cast(showonspreadsht as int) as showonspreadsht,
    cast(storegrades as int) as storegrades,
    cast(suppressltrgrd as int) as suppressltrgrd,
    cast(suppresspercentscr as int) as suppresspercentscr,
    cast(termid as int) as termid,
    cast(whomodifiedid as int) as whomodifiedid,
    cast(yearid as int) as yearid,

    cast(creditpct as float64) as creditpct,
    cast(numattpoints as float64) as numattpoints,

    cast(collectiondate as date) as collectiondate,
    cast(date1 as date) as date1,
    cast(date2 as date) as date2,

    cast(transaction_date as timestamp) as transaction_date,

{#
| aregradeslocked    |                 | INT64         | missing in definition |
| executionid        |                 | STRING        | missing in definition |
| storecode_order    |                 | STRING        | missing in definition |
| storecode_type     |                 | STRING        | missing in definition |
#}
from {{ source("powerschool_sftp", "src_powerschool__termbins") }}
