-- Miami left PowerSchool for Focus at the start of AY2026: Miami's PowerSchool
-- attendance stops at AY2025 and Focus's begins at AY2026, with no overlap. Every
-- int_students__* conform splits Miami on this boundary, so it is derived once here
-- rather than five times -- and derived from data rather than hardcoded to 2026.
--
-- Derived from RECORDED attendance, not from row presence. int_focus__attendance_daily
-- scaffolds a present-by-default row for every enrolled student-day back to AY2020, so
-- "years with Focus rows" spans AY2020 to AY2026 while Focus holds real attendance for
-- AY2026 only. Deriving from presence would replace six years of real PowerSchool
-- attendance with fabricated perfect attendance.
--
-- A floor, not a set: `min` cannot punch a hole mid-history the way `in (select ...)`
-- can. A Focus year that happened to record no exceptions would otherwise fall back to
-- a PowerSchool archive that holds nothing for it.
select min(academic_year) as focus_start_academic_year,
from {{ ref("int_focus__attendance_daily") }}
where is_attendance_recorded
