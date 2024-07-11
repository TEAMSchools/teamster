with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__calendar_day"),
                partition_by="dcid.int_value",
                order_by="_file_name desc",
            )
        }}
    ),

    staging as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            * except (
                dcid,
                id,
                schoolid,
                a,
                b,
                c,
                d,
                e,
                f,
                insession,
                membershipvalue,
                cycle_day_id,
                bell_schedule_id,
                week_num,
                whomodifiedid
            ),

            dcid.int_value as dcid,
            id.int_value as id,
            schoolid.int_value as schoolid,
            a.int_value as a,
            b.int_value as b,
            c.int_value as c,
            d.int_value as d,
            e.int_value as e,
            f.int_value as f,
            insession.int_value as insession,
            membershipvalue.double_value as membershipvalue,
            cycle_day_id.int_value as cycle_day_id,
            bell_schedule_id.int_value as bell_schedule_id,
            week_num.int_value as week_num,
            whomodifiedid.int_value as whomodifiedid,
        from deduplicate
    ),

    with_start as (
        select *, date_trunc(date_value, week) as week_start_date, from staging
    )

select *, date_add(week_start_date, interval 6 day) as week_end_date,
from with_start
