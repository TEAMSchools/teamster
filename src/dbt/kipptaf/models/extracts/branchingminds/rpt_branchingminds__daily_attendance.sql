with
    region_first_day as (
        select
            dl.region_key, dd.academic_year, min(dsc.date_key) as calendar_start_date,
        from {{ ref("dim_school_calendars") }} as dsc
        inner join {{ ref("dim_dates") }} as dd on dsc.date_key = dd.date_key
        inner join
            {{ ref("dim_locations") }} as dl on dsc.location_key = dl.location_key
        where dd.is_current_academic_year and dsc.is_in_session and not dl.is_campus
        group by dl.region_key, dd.academic_year
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by the Branching Minds template
select
    fsad.student_attendance_daily_key as event_id,
    cast(dd.academic_year + 1 as string) as school_year_id,
    cast(ds.lea_student_identifier as string) as student_id,

    -- no excused/unexcused split exists anywhere upstream -- only
    -- Present / Tardy / Absent / In-School Suspension / Out-of-School
    -- Suspension. Suspensions collapse into "Absent" below.
    case
        fsad.attendance_category
        when 'Present'
        then 'Present'
        when 'Tardy'
        then 'Tardy'
        else 'Absent'
    end as record_category,
    fsad.date_key as `date`,
from {{ ref("fct_student_attendance_daily") }} as fsad
inner join
    {{ ref("dim_student_enrollments") }} as dse
    on fsad.student_enrollment_key = dse.student_enrollment_key
inner join {{ ref("dim_students") }} as ds on dse.student_key = ds.student_key
inner join {{ ref("dim_locations") }} as dl on dse.location_key = dl.location_key
inner join {{ ref("dim_regions") }} as dr on dl.region_key = dr.region_key
inner join {{ ref("dim_dates") }} as dd on fsad.date_key = dd.date_key
inner join
    region_first_day as rfd
    on dl.region_key = rfd.region_key
    and dd.academic_year = rfd.academic_year
where
    dr.name in ('Newark', 'Camden', 'Paterson')
    and dd.is_current_academic_year
    and fsad.membership_value > 0
    -- drop attendance logged before the district's official first day
    and fsad.date_key >= coalesce(
        {{ branchingminds_first_day_override("dr.name", "dd.academic_year") }},
        rfd.calendar_start_date
    )
