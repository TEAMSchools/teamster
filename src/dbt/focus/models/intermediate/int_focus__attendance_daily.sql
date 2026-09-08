with
    -- Focus's `attendance_calendar` carries one row per school per day it treats
    -- as in session. There is no `insession` flag: presence in the table IS the
    -- flag. `minutes` is the sentinel 999 on every 2026 row and is not read.
    -- grain projection, not dup-masking. `stg_focus__attendance_calendar` has no
    -- unique test on (`school_id`, `syear`, `school_date`), and prod carries
    -- exact-duplicate rows on that key back to syear 2016 — a Focus data-quality
    -- issue, not one introduced here. Every column selected below IS that key,
    -- so identical tuples collapse with no loss. Without the `distinct`, the
    -- inner join 2 CTEs down fans out the membership scaffold by the duplicate
    -- count for every enrolled student on the affected school-day.
    calendar_days as (
        select distinct school_id, syear, school_date,
        from {{ ref("stg_focus__attendance_calendar") }}
    ),

    -- The membership scaffold. `int_focus__attendance_day` cannot represent a
    -- day it holds no row for, so absences nobody recorded are invisible at its
    -- grain. Crossing enrollment with in-session days makes them representable.
    -- Enrollment is the inner side on purpose, which drops the 4 misconfigured
    -- Focus schools that enrolled nobody. It does NOT drop school 60
    -- (Applicants), which carries 1 AY2026 enrollment against a 212-day
    -- holiday-inclusive calendar. School 60 has no locations-sheet row, so the
    -- kipptaf crosswalk drops it before anything published reads it. Ops tracks
    -- the calendar misconfiguration; this model does not filter it.
    --
    -- Inclusive on both ends. The roster dedupes stints to one per
    -- (student_number, academic_year, startdate) and trims each stint to the
    -- day before the next one starts, so the range cannot land a student in
    -- two stints on one day and a stint keeps the in-session day it ends on.
    membership as (
        select
            e.student_number,
            e.network_student_number,
            e.academic_year,
            e.schoolid,
            e.startdate,
            e.grade_level,
            c.school_date,
        from {{ ref("int_focus__student_enrollment_roster") }} as e
        inner join
            calendar_days as c
            on e.schoolid = c.school_id
            and e.academic_year = c.syear
            and c.school_date between e.startdate and e.exitdate
    ),

    -- student_id here is the PREFIXED Focus id, which is what
    -- int_focus__student_enrollment_roster exposes as student_number despite the name.
    attendance as (
        select student_id, schoolid, school_date, state_value, daily_code,
        from {{ ref("int_focus__attendance_day") }}
    )

select
    m.network_student_number as student_number,
    m.schoolid,
    m.academic_year,
    m.startdate,
    m.school_date,
    m.grade_level,

    a.daily_code,

    -- state_value IS the present/absent classification and is populated on every
    -- Focus row, independent of daily_code. NUMERIC upstream, FLOAT64 here to
    -- match the kipptaf ctod.
    cast(coalesce(a.state_value, 1) as float64) as state_value,

    -- The one thing Focus knows that a no-record day would otherwise hide:
    -- whether anybody actually took attendance. Focus's rate is material
    -- (17-23% of completed days in the opening week), so it is worth carrying.
    a.student_id is not null as is_attendance_recorded,

from membership as m
left join
    attendance as a
    on m.student_number = a.student_id
    and m.schoolid = a.schoolid
    and m.school_date = a.school_date
