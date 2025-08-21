select
    * except (
        dcid,
        id,
        a,
        b,
        c,
        d,
        e,
        f,
        bell_schedule_id,
        cycle_day_id,
        insession,
        schoolid,
        week_num,
        whomodifiedid,
        membershipvalue
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

{# | date | string | | missing in contract | 
    | date_value | | date | missing in definition | 
    | week_end_date | | date | missing in definition | 
    | week_start_date | | date | missing in definition | #}
from {{ source("powerschool_sftp", "src_powerschool__calendar_day") }}
