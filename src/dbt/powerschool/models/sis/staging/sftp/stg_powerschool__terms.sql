with
    terms as (
        select
            * except (
                attendance_calculation_code,
                autobuildbin,
                days_per_cycle,
                dcid,
                id,
                isyearrec,
                noofdays,
                periods_per_day,
                portion,
                schoolid,
                sterms,
                suppresspublicview,
                termsinyear,
                whomodifiedid,
                yearid,
                yearlycredithrs,
                firstday,
                lastday,
                transaction_date
            ),

            cast(attendance_calculation_code as int) as attendance_calculation_code,
            cast(autobuildbin as int) as autobuildbin,
            cast(days_per_cycle as int) as days_per_cycle,
            cast(dcid as int) as dcid,
            cast(id as int) as id,
            cast(isyearrec as int) as isyearrec,
            cast(noofdays as int) as noofdays,
            cast(periods_per_day as int) as periods_per_day,
            cast(portion as int) as portion,
            cast(schoolid as int) as schoolid,
            cast(sterms as int) as sterms,
            cast(suppresspublicview as int) as suppresspublicview,
            cast(termsinyear as int) as termsinyear,
            cast(whomodifiedid as int) as whomodifiedid,
            cast(yearid as int) as yearid,

            cast(yearlycredithrs as float64) as yearlycredithrs,

            cast(firstday as date) as firstday,
            cast(lastday as date) as lastday,

            cast(transaction_date as timestamp) as transaction_date,
        from {{ source("powerschool_sftp", "src_powerschool__terms") }}
    )

select *, yearid + 1990 as academic_year, yearid + 1991 as fiscal_year,
from terms
