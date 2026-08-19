with
    -- Already deduped to one row per (student_number, academic_year, startdate)
    -- in int_focus__student_enrollment, so the cross with calendar days below
    -- cannot fan out on Focus's duplicate open stints (#4905).
    enrollments as (
        select
            student_number,
            network_student_number,
            academic_year,
            schoolid,
            startdate,
            exitdate,
            grade_level,
        from {{ ref("int_focus__student_enrollment") }}
    ),

    -- Focus's attendance_calendar carries one row per school per day it treats
    -- as in session. There is no insession flag -- presence in the table IS the
    -- flag. minutes is the sentinel 999 on every 2026 row and is not read.
    -- distinct is grain projection, not dup-masking: stg_focus__attendance_calendar
    -- has no unique test on (school_id, syear, school_date) and prod carries
    -- exact-duplicate rows on that key going back to syear 2016 (a Focus/SIS
    -- data-quality issue, not introduced here); every column selected below IS
    -- that key, so identical tuples collapse with no information loss. Without
    -- this, the inner join two CTEs down fans out the membership scaffold by the
    -- duplicate count for every enrolled student on the affected school/day.
    calendar_days as (
        select distinct school_id, syear, school_date,
        from {{ ref("stg_focus__attendance_calendar") }}
    ),

    -- The membership scaffold. int_focus__attendance_day cannot represent a day
    -- it holds no row for, so absences that were never recorded are invisible
    -- at its grain; crossing enrollment with in-session days is what makes them
    -- representable. Enrollment is the inner side deliberately: five Focus
    -- schools (2 closed, 3 non-instructional) carry unfiltered 212-day
    -- calendars that include holidays, and all five have zero enrollments, so
    -- this join drops them. Tracked with Ops, not filtered here.
    membership as (
        select
            e.student_number,
            e.network_student_number,
            e.academic_year,
            e.schoolid,
            e.startdate,
            e.grade_level,
            c.school_date,
        from enrollments as e
        inner join
            calendar_days as c
            on e.schoolid = c.school_id
            and e.academic_year = c.syear
            and c.school_date between e.startdate and e.exitdate
    ),

    -- student_id here is the PREFIXED Focus id, which is what
    -- int_focus__student_enrollment exposes as student_number despite the name.
    attendance as (
        select student_id, schoolid, school_date, state_value, daily_code,
        from {{ ref("int_focus__attendance_day") }}
    )

select
    m.schoolid,
    m.grade_level,
    m.network_student_number as student_number,
    m.startdate as entrydate,
    m.school_date as calendardate,

    a.daily_code as att_code_focus,

    -- Phase 1 left studentid unpopulated for Focus in
    -- int_students__student_enrollment_union, so it stays null here for
    -- consistency. Every downstream join therefore uses student_number.
    cast(null as int64) as studentid,

    -- PowerSchool-only attendance-conversion machinery with no Focus analogue.
    -- Focus's own fteid is a student FLEID, an unrelated name collision.
    cast(null as int64) as fteid,
    cast(null as int64) as attendance_conversion_id,

    -- PowerSchool calendar tracks. Passthrough columns at kipptaf, never read in
    -- a calc, and Miami's track is already null network-wide.
    cast(null as int64) as ontrack,
    cast(null as int64) as offtrack,
    cast(null as string) as student_track,

    cast(1 as float64) as potential_attendancevalue,
    cast(1 as float64) as membershipvalue,

    -- state_value IS the present/absent classification and is populated on every
    -- Focus row, independent of daily_code. NUMERIC upstream, FLOAT64 here to
    -- match the kipptaf ctod.
    cast(coalesce(a.state_value, 1) as float64) as attendancevalue,

    m.academic_year - 1990 as yearid,

    -- Focus's four day codes conform to the PowerSchool vocabulary with one
    -- rename. AE and AD already match exactly. U must NOT pass through: U means
    -- Unprepared in PowerSchool, so an unmapped U would merge unexcused
    -- absences into an unrelated code. A day with no record maps to M (Missing
    -- Attendance) and counts present, which is what the district ctod does when
    -- no absence row exists.
    case
        when a.student_id is null
        then 'M'
        when a.daily_code = 'U'
        then 'A'
        else a.daily_code
    end as att_code,

from membership as m
left join
    attendance as a
    on m.student_number = a.student_id
    and m.schoolid = a.schoolid
    and m.school_date = a.school_date
