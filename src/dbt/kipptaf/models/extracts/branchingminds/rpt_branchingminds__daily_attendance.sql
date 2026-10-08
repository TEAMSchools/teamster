select
    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "calendardate"]
        )
    }} as event_id,

    calendardate as `date`,

    cast(academic_year + 1 as string) as school_year_id,
    cast(student_number as string) as student_id,

    -- no excused/unexcused split exists anywhere upstream -- only
    -- Present / Tardy / Absent / In-School Suspension / Out-of-School
    -- Suspension. Suspensions collapse into "Absent" below.
    case
        attendance_category
        when 'Present'
        then 'Present'
        when 'Tardy'
        then 'Tardy'
        else 'Absent'
    end as record_category,
from {{ ref("int_students__attendance_daily") }}
where
    _dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
    and academic_year = {{ var("current_academic_year") }}
    -- scheduled days carry a placeholder Present until the register is taken,
    -- and the feed runs before school, so today is excluded too
    and calendardate < current_date('{{ var("local_timezone") }}')
    and membershipvalue > 0
    -- days with no recorded attendance have no category to send
    and attendance_category is not null
