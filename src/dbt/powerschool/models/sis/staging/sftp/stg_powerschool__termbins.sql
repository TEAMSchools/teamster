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
        yearid,
        creditpct,
        numattpoints,
        collectiondate,
        date1,
        date2,
        transaction_date
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

    left(storecode, 1) as storecode_type,
    right(storecode, 1) as storecode_order,
from {{ source("powerschool_sftp", "src_powerschool__termbins") }}
