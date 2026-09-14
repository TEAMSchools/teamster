-- Carry-forward must never repair a leaver. An offboarding writes a new
-- effective-dated work assignment row whose job_function_code comes back null,
-- which is indistinguishable from the ADP erosion this model repairs, so
-- without a termination guard the departing person's scopes replay onto their
-- own termination row. Observed on 2026-09-14, when the only staff member the
-- carry-forward would have fired for network-wide was a termination effective
-- the next day.
select a.staff_key, a.job_function_code_source, swa.termination_date,
from {{ ref("dim_staff_cube_access") }} as a
-- staff_key is not unique in swa (one row per assignment), but is_current plus
-- a non-null termination_date is the leaver condition this asserts against, and
-- a duplicate here only repeats an already-failing row
inner join
    {{ ref("dim_staff_work_assignments") }} as swa
    on a.staff_key = swa.staff_key
    and swa.is_current
where
    a.job_function_code_source = 'carried_forward' and swa.termination_date is not null
