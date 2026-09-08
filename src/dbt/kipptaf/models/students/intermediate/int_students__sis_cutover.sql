-- Recorded attendance, not row presence. int_focus__attendance_daily scaffolds a
-- present-by-default row for every enrolled student-day back to AY2020, so row
-- presence spans AY2020 to AY2026 while Focus holds real attendance for AY2026
-- only. Presence would replace 6 years of real PowerSchool attendance with
-- fabricated perfect attendance.
--
-- A floor, not a set: `min` cannot punch a hole mid-history the way
-- `in (select ...)` can. A Focus year that recorded no exceptions would fall
-- back to a PowerSchool archive that holds nothing for it.
select min(academic_year) as focus_start_academic_year,
from {{ ref("int_focus__attendance_daily") }}
where is_attendance_recorded
