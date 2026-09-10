select
    fsad.student_attendance_daily_key as event_id,
    fsad.date_key as `date`,

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
from {{ ref("fct_student_attendance_daily") }} as fsad
inner join
    {{ ref("dim_student_enrollments") }} as dse
    on fsad.student_enrollment_key = dse.student_enrollment_key
inner join {{ ref("dim_students") }} as ds on dse.student_key = ds.student_key
inner join {{ ref("dim_locations") }} as dl on dse.location_key = dl.location_key
inner join {{ ref("dim_regions") }} as dr on dl.region_key = dr.region_key
inner join {{ ref("dim_dates") }} as dd on fsad.date_key = dd.date_key
where
    dr.name in ('Newark', 'Camden', 'Paterson')
    and dd.is_current_academic_year
    and fsad.membership_value > 0
    -- days with no recorded attendance have no category to send
    and fsad.attendance_category is not null
