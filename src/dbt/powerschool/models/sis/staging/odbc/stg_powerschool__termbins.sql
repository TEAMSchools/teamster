{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

with
    staging as (
        select
            * except (
                dcid,
                id,
                termid,
                schoolid,
                creditpct,
                collect,
                yearid,
                showonspreadsht,
                currentgrade,
                storegrades,
                numattpoints,
                suppressltrgrd,
                gradescaleid,
                suppresspercentscr,
                aregradeslocked,
                whomodifiedid
            ),

            dcid.int_value as dcid,
            id.int_value as id,
            termid.int_value as termid,
            schoolid.int_value as schoolid,
            creditpct.double_value as creditpct,
            collect.int_value as collect,
            yearid.int_value as yearid,
            showonspreadsht.int_value as showonspreadsht,
            currentgrade.int_value as currentgrade,
            storegrades.int_value as storegrades,
            numattpoints.double_value as numattpoints,
            suppressltrgrd.int_value as suppressltrgrd,
            gradescaleid.int_value as gradescaleid,
            suppresspercentscr.int_value as suppresspercentscr,
            aregradeslocked.int_value as aregradeslocked,
            whomodifiedid.int_value as whomodifiedid,
        from {{ source("powerschool_odbc", "src_powerschool__termbins") }}
    )

select *, left(storecode, 1) as storecode_type, right(storecode, 1) as storecode_order,
from staging
