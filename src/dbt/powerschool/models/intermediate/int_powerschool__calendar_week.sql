select
    cd.schoolid,
    cd.week_start_date,
    cd.week_end_date,

    t.yearid,
    t.abbreviation as `quarter`,

    t.yearid + 1990 as academic_year,

    if(t.abbreviation in ('Q1', 'Q2'), 'S1', 'S2') as semester,

    min(cd.date_value) as school_week_start_date,
    max(cd.date_value) as school_week_end_date,

    row_number() over (
        partition by cd.schoolid, t.yearid order by cd.week_start_date asc
    ) as week_number_academic_year,

    row_number() over (
        partition by cd.schoolid, t.yearid, t.abbreviation
        order by cd.week_start_date asc
    ) as week_number_quarter,

    lead(min(cd.date_value)) over (
        partition by cd.schoolid, t.yearid order by cd.week_start_date asc
    ) as school_week_start_date_lead,
from {{ ref("stg_powerschool__calendar_day") }} as cd
inner join
    {{ ref("stg_powerschool__terms") }} as t
    on cd.schoolid = t.schoolid
    and cd.date_value between t.firstday and t.lastday
    and t.portion = 4  /* quarters */
inner join {{ ref("stg_powerschool__cycle_day") }} as cy on cd.cycle_day_id = cy.id
inner join
    {{ ref("stg_powerschool__bell_schedule") }} as bs
    on cd.schoolid = bs.schoolid
    and cd.bell_schedule_id = bs.id
where
    cd.insession = 1
    and cd.membershipvalue > 0
    and cd.date_value >= date({{ var("current_academic_year") }}, 7, 1)
group by cd.schoolid, cd.week_start_date, cd.week_end_date, t.yearid, t.abbreviation
