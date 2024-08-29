with
    schools as (
        select
            _dbt_source_relation,
            school_number,

            case
                high_grade when 12 then 'HS' when 8 then 'MS' when 4 then 'ES'
            end as school_level,
        from `kipptaf_powerschool.stg_powerschool__schools`
    ),

    week_rollup as (
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
            count(cd.date_value) as date_count,

            row_number() over (
                partition by cd.schoolid, t.yearid order by cd.week_start_date asc
            ) as week_number_academic_year,

            row_number() over (
                partition by cd.schoolid, t.yearid, t.abbreviation
                order by cd.week_start_date asc
            ) as week_number_quarter,
        from {{ ref("stg_powerschool__calendar_day") }} as cd
        inner join
            {{ ref("stg_powerschool__terms") }} as t
            on cd.schoolid = t.schoolid
            and cd.date_value between t.firstday and t.lastday
            and t.portion = 4  /* quarters */
        inner join
            {{ ref("stg_powerschool__cycle_day") }} as cy on cd.cycle_day_id = cy.id
        inner join
            {{ ref("stg_powerschool__bell_schedule") }} as bs
            on cd.schoolid = bs.schoolid
            and cd.bell_schedule_id = bs.id
        where cd.insession = 1 and cd.membershipvalue > 0
        group by
            cd.schoolid, cd.week_start_date, cd.week_end_date, t.yearid, t.abbreviation
    )

select
    w.*,

    date_add(w.week_start_date, interval 1 day) as week_start_monday,
    date_add(w.week_end_date, interval 1 day) as week_end_sunday,

    lead(w.school_week_start_date) over (
        partition by w.schoolid, w.yearid order by w.week_start_date asc
    ) as school_week_start_date_lead,
from week_rollup as w
left join schools as s on w.schoolid = s.school_number
