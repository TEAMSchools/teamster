-- Finalsite never rolls a graduated cohort off `enrolled` -- last year's
-- seniors keep that status indefinitely -- and separately, some students who
-- are still enrolled never get a current-year record created. Both surface as
-- an `enrolled` contact stamped with a prior school year. Warn, not error:
-- this is a standing Ops worklist inside Finalsite, and the count only falls
-- when someone corrects records at the source.
select finalsite_enrollment_id, status, school_year_start, grade_name,
from {{ ref("stg_finalsite__contacts") }}
where status = 'enrolled' and school_year_start < {{ var("current_academic_year") }}
