with
    week_rollup as (
        select
            cd.schoolid,
            cd.week_start_date,
            cd.week_end_date,
            cd.academic_year,

            sch.school_level,

            date_add(cd.week_start_date, interval 1 day) as week_start_monday,
            date_add(cd.week_end_date, interval 1 day) as week_end_sunday,

            min(cd.school_date) as school_week_start_date,
            max(cd.school_date) as school_week_end_date,
            count(cd.school_date) as date_count,

            max(mp.quarter_semester) as semester,
            max(mp.short_name) as `quarter`,
        from {{ ref("int_focus__calendar_day") }} as cd
        inner join {{ ref("int_focus__schools") }} as sch on cd.schoolid = sch.id
        -- Quarter marking periods only, matching the PowerSchool version's
        -- portion = 4 filter on termbins.
        inner join
            {{ ref("stg_focus__marking_periods") }} as mp
            on cd.schoolid = mp.school_id
            and cd.academic_year = mp.syear
            and cd.school_date between mp.start_date and mp.end_date
            and mp.type = 'quarter'
        group by
            cd.schoolid,
            cd.week_start_date,
            cd.week_end_date,
            cd.academic_year,
            sch.school_level
    ),

    window_calcs as (
        select
            *,

            min(week_start_monday) over (
                partition by schoolid, academic_year
            ) as first_day_school_year,
            max(week_start_monday) over (
                partition by schoolid, academic_year
            ) as last_week_start_school_year,

            max(school_week_end_date) over (
                partition by schoolid, academic_year
            ) as last_day_school_year,

            lead(school_week_start_date) over (
                partition by schoolid, academic_year order by week_start_date asc
            ) as school_week_start_date_lead,

            row_number() over (
                partition by schoolid, academic_year order by week_start_date asc
            ) as week_number_academic_year,
            row_number() over (
                partition by schoolid, academic_year, `quarter`
                order by week_start_date asc
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
        when
            academic_year = {{ var("current_academic_year") }}
            and current_date('{{ var("local_timezone") }}')
            > date_add(last_week_start_school_year, interval 6 day)
            and week_start_monday = last_week_start_school_year
        then true
        else false
    end as is_current_week_mon_sun,

from window_calcs
