with
    default_calendars as (
        select calendar_id, syear,
        from {{ source("kippmiami_dlt_focus", "attendance_calendars") }}
        where default_calendar = 'Y'
    ),

    calendar_days as (
        select calendar_id, school_date,
        from {{ source("kippmiami_dlt_focus", "attendance_calendar") }}
        where minutes > 0
    )

select dc.syear, min(cd.school_date) as first_day_of_school,
from default_calendars as dc
inner join calendar_days as cd on dc.calendar_id = cd.calendar_id
group by dc.syear
