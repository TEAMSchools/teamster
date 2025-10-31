with
    week_rollup as (
        select
            cd.schoolid,
            cd.week_start_date,
            cd.week_end_date,

            sch.school_level,

            t.yearid,
            t.academic_year,
            t.semester,
            t.abbreviation as `quarter`,

            date_add(cd.week_start_date, interval 1 day) as week_start_monday,
            date_add(cd.week_end_date, interval 1 day) as week_end_sunday,

            min(cd.date_value) as school_week_start_date,
            max(cd.date_value) as school_week_end_date,
            count(cd.date_value) as date_count,
        from {{ ref("stg_powerschool__calendar_day") }} as cd
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on cd.schoolid = sch.school_number
        inner join
            {{ ref("stg_powerschool__cycle_day") }} as cy on cd.cycle_day_id = cy.id
        inner join
            {{ ref("stg_powerschool__terms") }} as t
            on cd.schoolid = t.schoolid
            and cd.date_value between t.firstday and t.lastday
            and t.portion = 4  /* quarters */
        inner join
            {{ ref("stg_powerschool__bell_schedule") }} as bs
            on cd.schoolid = bs.schoolid
            and cd.bell_schedule_id = bs.id
        where cd.insession = 1 and cd.membershipvalue > 0
        group by
            cd.schoolid,
            cd.week_start_date,
            cd.week_end_date,
            sch.school_level,
            t.yearid,
            t.academic_year,
            t.semester,
            t.abbreviation
    ),

    window_calcs as (
        select
            *,

            min(week_start_monday) over (
                partition by schoolid, yearid
            ) as first_day_school_year,
            max(week_start_monday) over (
                partition by schoolid, yearid
            ) as last_week_start_school_year,

            lead(school_week_start_date) over (
                partition by schoolid, yearid order by week_start_date asc
            ) as school_week_start_date_lead,

            row_number() over (
                partition by schoolid, yearid order by week_start_date asc
            ) as week_number_academic_year,
            row_number() over (
                partition by schoolid, yearid, `quarter` order by week_start_date asc
            ) as week_number_quarter,
        from week_rollup
    )

select
    *,

    case
        when
            academic_year = {{ var("current_academic_year") }}
            and current_date('{{ var("local_timezone") }}')
            between week_start_monday and week_end_sunday
        then true
        when week_start_monday = last_week_start_school_year
        then true
        else false
    end as is_current_week_mon_sun,
from window_calcs
