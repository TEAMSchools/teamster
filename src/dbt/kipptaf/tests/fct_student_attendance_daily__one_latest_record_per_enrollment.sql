-- Exactly one is_latest_record = TRUE per enrollment stint. is_latest_record is
-- the per-stint last attendance day (not membership-gated), so every stint with
-- rows has exactly one — backs both the attendance "latest CA status" pattern
-- and the enrollment cube's is_latest_record dimension.
select student_enrollment_key, countif(is_latest_record) as n_latest,
from {{ ref("fct_student_attendance_daily") }}
group by student_enrollment_key
having countif(is_latest_record) != 1
