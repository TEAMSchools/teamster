-- A student holds one enrollment stint at a time. Focus accepts a second open
-- stint at another school without closing the first.
-- int_focus__student_enrollment_roster trims the earlier stint to the day
-- before the next one starts, so every model downstream sees clean stints and
-- this is the one place the source shape is still visible.
--
-- Strict on the boundary: a stint that starts on the day another ends is a
-- normal sequential transfer. Only a stint that starts strictly inside another
-- stint's span is returned. Same-start-date pairs are a different defect, held
-- by the staging uniqueness tests. An open stint ends June 30 of its year, the
-- same default the roster applies. Any returned row is a failure, and the fix
-- is in Focus: close the stale stint.
with
    stints as (
        select
            student_id,
            syear,
            school_id,
            start_date,

            coalesce(end_date, date(syear + 1, 6, 30)) as end_date,
        from {{ ref("int_focus__student_enrollment") }}
    )

select
    a.student_id,
    a.syear,
    a.school_id as school_id_a,
    a.start_date as start_date_a,
    a.end_date as end_date_a,
    b.school_id as school_id_b,
    b.start_date as start_date_b,
    b.end_date as end_date_b,
from stints as a
inner join
    stints as b
    on a.student_id = b.student_id
    and a.syear = b.syear
    -- ordered pair: b starts after a, so each pair appears once
    and a.start_date < b.start_date
    and a.end_date > b.start_date
