-- the half-open join drops null-entrydate graduate placeholder stints;
-- their student_enrollment_key cannot appear in the daily fact
select sed.student_enrollment_key,
from {{ ref("fct_student_enrollment_daily") }} as sed
inner join
    {{ ref("dim_student_enrollments") }} as dse
    on sed.student_enrollment_key = dse.student_enrollment_key
where dse.entry_date_key is null
