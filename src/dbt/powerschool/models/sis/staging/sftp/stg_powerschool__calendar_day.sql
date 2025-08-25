with
    calendar_day as (
        select
            * except (
                `date`,
                a,
                b,
                bell_schedule_id,
                c,
                cycle_day_id,
                d,
                dcid,
                e,
                f,
                id,
                insession,
                membershipvalue,
                schoolid,
                week_num,
                whomodifiedid
            ),

            cast(dcid as int) as dcid,
            cast(id as int) as id,
            cast(a as int) as a,
            cast(b as int) as b,
            cast(c as int) as c,
            cast(d as int) as d,
            cast(e as int) as e,
            cast(f as int) as f,
            cast(bell_schedule_id as int) as bell_schedule_id,
            cast(cycle_day_id as int) as cycle_day_id,
            cast(insession as int) as insession,
            cast(schoolid as int) as schoolid,
            cast(week_num as int) as week_num,
            cast(whomodifiedid as int) as whomodifiedid,

            cast(membershipvalue as float64) as membershipvalue,

            cast(`date` as date) as date_value,
        from {{ source("powerschool_sftp", "src_powerschool__calendar_day") }}
    ),

    week_calc as (
        select *, date_trunc(date_value, week) as week_start_date, from calendar_day
    )

select *, date_add(week_start_date, interval 6 day) as week_end_date,
from week_calc
