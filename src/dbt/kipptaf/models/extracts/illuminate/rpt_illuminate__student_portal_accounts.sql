select
    -- trunk-ignore-begin(sqlfluff/RF05)
    student_number as `01 Student ID`,
    username as `02 Username`,
    student_web_id as `03 Email`,

    1 as `04 Enable Portal`,

    student_web_password as `05 Temporary Password`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_extracts__student_enrollments") }}
where rn_all = 1 and enroll_status = 0
