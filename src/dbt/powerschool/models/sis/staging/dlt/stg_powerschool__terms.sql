with
    transformations as (
        select
            `name`,
            abbreviation,
            importmap,
            terminfo_guid,
            psguid,
            ip_address,
            whomodifiedtype,
            transaction_date,

            cast(dcid as int) as dcid,
            cast(firstday as date) as firstday,
            cast(lastday as date) as lastday,
            cast(id as int) as id,
            cast(yearid as int) as yearid,
            cast(noofdays as int) as noofdays,
            cast(schoolid as int) as schoolid,
            cast(yearlycredithrs as float64) as yearlycredithrs,
            cast(termsinyear as int) as termsinyear,
            cast(portion as int) as portion,
            cast(autobuildbin as int) as autobuildbin,
            cast(isyearrec as int) as isyearrec,
            cast(periods_per_day as int) as periods_per_day,
            cast(days_per_cycle as int) as days_per_cycle,
            cast(attendance_calculation_code as int) as attendance_calculation_code,
            cast(sterms as int) as sterms,
            cast(suppresspublicview as int) as suppresspublicview,
            cast(whomodifiedid as int) as whomodifiedid,
        from {{ source("powerschool_dlt", "terms") }}
    )

select
    *,

    yearid + 1990 as academic_year,
    yearid + 1991 as fiscal_year,

    if(abbreviation in ('Q1', 'Q2'), 'S1', 'S2') as semester,
from transformations
