with
    staging as (
        select
            storecode,
            creditstring,
            description,
            citasmt,
            changegradeto,
            excludedmarks,
            ip_address,
            whomodifiedtype,
            transaction_date,

            cast(dcid as int) as dcid,
            cast(date1 as date) as date1,
            cast(collectiondate as date) as collectiondate,
            cast(date2 as date) as date2,
            cast(id as int) as id,
            cast(termid as int) as termid,
            cast(schoolid as int) as schoolid,
            cast(creditpct as float64) as creditpct,
            cast(collect as int) as collect,
            cast(yearid as int) as yearid,
            cast(showonspreadsht as int) as showonspreadsht,
            cast(currentgrade as int) as currentgrade,
            cast(storegrades as int) as storegrades,
            cast(numattpoints as float64) as numattpoints,
            cast(suppressltrgrd as int) as suppressltrgrd,
            cast(gradescaleid as int) as gradescaleid,
            cast(suppresspercentscr as int) as suppresspercentscr,
            cast(whomodifiedid as int) as whomodifiedid,
        from {{ source("powerschool_dlt", "termbins") }}
    )

select
    *,

    left(storecode, 1) as storecode_type,
    right(storecode, 1) as storecode_order,

    if(
        current_date('{{ var("local_timezone") }}') between date1 and date2, true, false
    ) as is_current_term,

    case
        when storecode in ('Q1', 'Q2')
        then 'S1'
        when storecode in ('Q3', 'Q4')
        then 'S2'
    end as semester,
from staging
