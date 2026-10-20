-- A student must not sit in two course periods of the same course, in the same
-- class period, at the same time.
--
-- The marking-period resolution is load-bearing. int_focus__schedule.end_date
-- is null on most rows because Focus bounds a schedule row by its marking
-- period rather than by the row's own end_date. Taken literally, every
-- Semester 1 row reads as open-ended and collides with its Semester 2 partner,
-- though the pair is simply a year-long course scheduled as two halves.
-- Falling back to the marking period's dates, which int_focus__schedule
-- resolves including the full-year sentinel, removes all of them.
--
-- Scoped to a shared period_id. Two course periods of one course in DIFFERENT
-- class periods is a separate, much larger pattern that reads as a course
-- meeting several times a week. It is with Ops for a ruling and is deliberately
-- not asserted here.
--
-- A single shared boundary day is a normal sequential transfer, so the
-- comparison is strict on both sides: only a genuine multi-day overlap is
-- returned. Any returned row is a failure.
with
    resolved as (
        select
            student_id,
            course_id,
            academic_year,
            course_period_id,
            period_id,

            coalesce(start_date, marking_period_start_date) as effective_start_date,
            coalesce(
                end_date, marking_period_end_date, date '9999-12-31'
            ) as effective_end_date,
        from {{ ref("int_focus__schedule") }}
    )

select
    a.student_id,
    a.course_id,
    a.academic_year,
    a.period_id,
    a.course_period_id as course_period_id_a,
    a.effective_start_date as effective_start_date_a,
    a.effective_end_date as effective_end_date_a,
    b.course_period_id as course_period_id_b,
    b.effective_start_date as effective_start_date_b,
    b.effective_end_date as effective_end_date_b,
from resolved as a
inner join
    resolved as b
    on a.student_id = b.student_id
    and a.course_id = b.course_id
    and a.academic_year = b.academic_year
    and a.period_id = b.period_id
    -- ordered pair: compares each combination once, never a row to itself
    and a.course_period_id < b.course_period_id
    and a.effective_start_date < b.effective_end_date
    and a.effective_end_date > b.effective_start_date
