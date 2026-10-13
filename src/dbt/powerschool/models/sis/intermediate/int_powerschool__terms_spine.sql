with
    -- Defensive only: keeps a duplicate raw record from doubling a school year's
    -- raw rows. dcid is the staging primary key, so the pick is deterministic.
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=ref("stg_powerschool__terms"),
                partition_by="schoolid, yearid, abbreviation",
                order_by="dcid desc",
            )
        }}
    )

select
    dcid,
    `name`,
    firstday,
    lastday,
    abbreviation,
    importmap,
    terminfo_guid,
    psguid,
    ip_address,
    whomodifiedtype,
    transaction_date,
    id,
    noofdays,
    yearlycredithrs,
    termsinyear,
    portion,
    autobuildbin,
    isyearrec,
    periods_per_day,
    days_per_cycle,
    attendance_calculation_code,
    sterms,
    suppresspublicview,
    whomodifiedid,
    fiscal_year,
    cast(null as string) as term,
    cast(null as date) as term_start_date,
    cast(null as date) as term_end_date,
    cast(null as string) as semester,
    cast(null as bool) as is_current_term,
    schoolid,
    yearid,
    academic_year,
from deduplicate

union all

-- Positional union: this list mirrors the raw branch column for column, with a
-- typed null where the quarter branch has no equivalent.
select
    cast(null as int64) as dcid,
    cast(null as string) as `name`,
    cast(null as date) as firstday,
    cast(null as date) as lastday,
    cast(null as string) as abbreviation,
    cast(null as string) as importmap,
    cast(null as string) as terminfo_guid,
    cast(null as string) as psguid,
    cast(null as string) as ip_address,
    cast(null as string) as whomodifiedtype,
    cast(null as timestamp) as transaction_date,
    cast(null as int64) as id,
    cast(null as int64) as noofdays,
    cast(null as float64) as yearlycredithrs,
    cast(null as int64) as termsinyear,
    cast(null as int64) as portion,
    cast(null as int64) as autobuildbin,
    cast(null as int64) as isyearrec,
    cast(null as int64) as periods_per_day,
    cast(null as int64) as days_per_cycle,
    cast(null as int64) as attendance_calculation_code,
    cast(null as int64) as sterms,
    cast(null as int64) as suppresspublicview,
    cast(null as int64) as whomodifiedid,
    cast(null as int64) as fiscal_year,
    term,
    term_start_date,
    term_end_date,
    semester,
    is_current_term,
    schoolid,
    yearid,
    academic_year,
from {{ ref("int_powerschool__terms") }}
