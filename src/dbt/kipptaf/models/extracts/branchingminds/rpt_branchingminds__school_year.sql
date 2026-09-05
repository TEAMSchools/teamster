with
    school_calendar_days as (
        select
            dsc.location_key,
            dd.academic_year,

            count(if(dsc.is_in_session, 1, null)) as instruction_days,
            min(if(dsc.is_in_session, dsc.date_key, null)) as start_date,
            max(if(dsc.is_in_session, dsc.date_key, null)) as end_date,
        from {{ ref("dim_school_calendars") }} as dsc
        inner join {{ ref("dim_dates") }} as dd on dsc.date_key = dd.date_key
        where dd.is_current_academic_year
        group by dsc.location_key, dd.academic_year
    ),

    region_school_years as (
        select
            dl.region_key,

            scd.academic_year,

            -- approximation: schools within a region don't all share one
            -- calendar (diverges most at year-end); this averages across
            -- schools in the region rather than reporting per-school
            cast(round(avg(scd.instruction_days)) as int64) as instruction_days,

            min(scd.start_date) as start_date,
            max(scd.end_date) as end_date,
        from school_calendar_days as scd
        inner join
            {{ ref("dim_locations") }} as dl on scd.location_key = dl.location_key
        where not dl.is_campus
        group by dl.region_key, scd.academic_year
    )

select
    rsy.start_date,
    rsy.end_date,
    rsy.instruction_days,

    dr.state_district_id as district_id,

    cast(rsy.academic_year + 1 as string) as school_year_id,
    concat(rsy.academic_year, '-', rsy.academic_year + 1) as `name`,
from region_school_years as rsy
inner join {{ ref("dim_regions") }} as dr on rsy.region_key = dr.region_key
where dr.name in ('Newark', 'Camden', 'Paterson')
