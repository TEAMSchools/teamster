-- Guards the tie-break of the same-start-date dedupe in
-- int_focus__student_enrollment. When a student holds two enrollments sharing a
-- year and a start date, that dedupe keeps one, and it decides which by reading
-- the Focus "Second School" checkbox (custom_9). Exactly one of the rows must
-- leave it unchecked -- that row is the primary, home-campus enrollment.
--
-- Both failure directions matter. Two unchecked rows leave the dedupe with no
-- signal, so it falls through to creation time and picks arbitrarily between two
-- schools. Zero unchecked rows mean every enrollment claims to be a second
-- school, and the primary one is missing. Either way the student gets attributed
-- to a campus by accident.
--
-- Asserted on the staging model, not on int_focus__student_enrollment, because
-- the dedupe has already dropped one of the rows by then. A uniqueness test on
-- the deduped grain cannot fail here by construction: the dedupe exists to make
-- that key unique.
--
-- Scoped to groups spanning more than one school. A same-school duplicate is a
-- stub the dedupe resolves on its own terms and needs no primary marker.
-- Any returned row is a failure.
select
    student_id,
    syear,
    start_date,
    count(*) as n_rows,
    count(distinct school_id) as n_schools,
    countif(second_school is null) as n_primary,
from {{ ref("stg_focus__student_enrollment") }}
group by student_id, syear, start_date
having n_schools > 1 and n_primary != 1
