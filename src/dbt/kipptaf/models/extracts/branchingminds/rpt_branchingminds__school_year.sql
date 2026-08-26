with
    school_calendar_days as (
        select
            dsc.location_key,
            dd.academic_year,

            count(if(dsc.is_in_session, 1, null)) as instruction_days,
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

            max(scd.end_date) as end_date,

            -- approximation: schools within a region don't all share one
            -- calendar (diverges most at year-end); this averages across
            -- schools in the region rather than reporting per-school
            round(avg(scd.instruction_days)) as instruction_days,
        from school_calendar_days as scd
        inner join
            {{ ref("dim_locations") }} as dl on scd.location_key = dl.location_key
        where not dl.is_campus
        group by dl.region_key, scd.academic_year
    )

select
    rsy.end_date,
    rsy.instruction_days,

    cast(rsy.academic_year + 1 as string) as school_year_id,
    concat(rsy.academic_year, '-', rsy.academic_year + 1) as `name`,

    -- KTAF-assigned BRM district codes (not a state/vendor-issued id)
    case
        dr.name
        when 'Newark'
        then '7325'
        when 'Camden'
        then '1799'
        when 'Paterson'
        then '7899'
    end as district_id,

    -- official first day of school per district -- overrides the
    -- calendar's is_in_session flag, which marks 8/19-8/23 as in-session
    -- for Newark/Paterson too even though their real first day was 8/24
    case
        dr.name when 'Camden' then date '2026-08-19' else date '2026-08-24'
    end as start_date,
from region_school_years as rsy
inner join {{ ref("dim_regions") }} as dr on rsy.region_key = dr.region_key
where dr.name in ('Newark', 'Camden', 'Paterson')
