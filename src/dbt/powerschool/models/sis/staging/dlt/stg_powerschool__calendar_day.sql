with
    staging as (
        select
            scheduleid,
            note,
            `type`,
            psguid,
            whomodifiedtype,
            ip_address,

            cast(id as int) as id,
            cast(date_value as date) as date_value,
            cast(dcid as int) as dcid,
            cast(schoolid as int) as schoolid,
            cast(a as int) as a,
            cast(b as int) as b,
            cast(c as int) as c,
            cast(d as int) as d,
            cast(e as int) as e,
            cast(f as int) as f,
            cast(insession as int) as insession,
            cast(membershipvalue as float64) as membershipvalue,
            cast(cycle_day_id as int) as cycle_day_id,
            cast(bell_schedule_id as int) as bell_schedule_id,
            cast(week_num as int) as week_num,
            cast(whomodifiedid as int) as whomodifiedid,
        from {{ source("powerschool_dlt", "calendar_day") }}
    ),

    with_start as (
        select *, date_trunc(date_value, week) as week_start_date, from staging
    )

select *, date_add(week_start_date, interval 6 day) as week_end_date,
from with_start
