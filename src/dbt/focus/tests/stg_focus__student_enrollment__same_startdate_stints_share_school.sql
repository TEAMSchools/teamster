-- Guards the unstated premise of the same-start-date dedupe in
-- int_focus__student_enrollment, which partitions by (student_number,
-- academic_year, startdate) and keeps one row. Dropping a row is only safe
-- when the collapsed rows are the SAME school -- two stints at DIFFERENT
-- schools are distinct enrollments, and demoting one silently deletes it,
-- orphaning every schedule row that belongs to the dropped school.
--
-- Asserted here on the staging model rather than on int_focus__student_enrollment
-- because the dropped row only exists upstream of the dedupe. Downstream, the
-- evidence is already gone, so no test on the deduped grain can see it -- and a
-- uniqueness test on the dedupe's own key can never fail by construction.
--
-- Same-school duplicates are NOT flagged: those are the case the dedupe exists
-- to resolve. Any returned row is a failure.
select
    student_id,
    syear,
    start_date,
    count(*) as n_rows,
    count(distinct school_id) as n_schools,
from {{ ref("stg_focus__student_enrollment") }}
group by student_id, syear, start_date
having n_schools > 1
