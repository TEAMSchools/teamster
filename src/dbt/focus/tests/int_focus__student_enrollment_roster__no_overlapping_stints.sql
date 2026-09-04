-- A student holds one enrollment stint at a time. Focus accepts a second open
-- stint at another school without closing the first, and every model that
-- scaffolds days from the roster then carries that student twice per day.
--
-- Strict on the boundary: a stint that starts on the day another ends is a
-- normal sequential transfer, and int_focus__attendance_daily already assigns
-- that shared day to the arriving school. Only a stint that starts strictly
-- inside another stint's span is returned. Same-start-date pairs never reach
-- this model: int_focus__student_enrollment_roster dedupes them. Any returned
-- row is a failure.
select
    a.student_number,
    a.academic_year,
    a.schoolid as schoolid_a,
    a.startdate as startdate_a,
    a.exitdate as exitdate_a,
    b.schoolid as schoolid_b,
    b.startdate as startdate_b,
    b.exitdate as exitdate_b,
from {{ ref("int_focus__student_enrollment_roster") }} as a
inner join
    {{ ref("int_focus__student_enrollment_roster") }} as b
    on a.student_number = b.student_number
    and a.academic_year = b.academic_year
    -- ordered pair: b starts after a, so each pair appears once
    and a.startdate < b.startdate
    and a.exitdate > b.startdate
