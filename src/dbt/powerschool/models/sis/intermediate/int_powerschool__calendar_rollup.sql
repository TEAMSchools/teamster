with
    calendar_day as (
        select cd.schoolid, cd.date_value, cd.a, cd.b, cd.c, cd.d, cd.e, cd.f, t.yearid,
        from {{ ref("stg_powerschool__calendar_day") }} as cd
        inner join
            {{ ref("stg_powerschool__terms") }} as t
            on cd.schoolid = t.schoolid
            and cd.date_value between t.firstday and t.lastday
            and t.isyearrec = 1
        inner join
            {{ ref("stg_powerschool__cycle_day") }} as cy on cd.cycle_day_id = cy.id
        inner join
            {{ ref("stg_powerschool__bell_schedule") }} as bs
            on cd.schoolid = bs.schoolid
            and cd.bell_schedule_id = bs.id
        where cd.insession = 1 and cd.membershipvalue > 0
    ),

    cal_long as (
        select schoolid, date_value, yearid, values_column, upper(name_column) as track,
        from calendar_day unpivot (values_column for name_column in (a, b, c, d, e, f))
    )

select
    schoolid,
    yearid,
    track,
    min(date_value) as min_calendardate,
    max(date_value) as max_calendardate,
    count(date_value) as days_total,
    sum(
        if(date_value > current_date('{{ var("local_timezone") }}'), 1, 0)
    ) as days_remaining
from cal_long
where values_column = 1
group by schoolid, yearid, track
