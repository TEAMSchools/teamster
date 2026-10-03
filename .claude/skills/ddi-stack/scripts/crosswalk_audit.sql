-- Course subject crosswalk audit (ddi-stack rollover step 7).
-- Current-year-enrollment courses missing from the crosswalk sheet.
-- Set the year filter to the fall-dated year (2026 means SY26-27).
-- Expect homeroom, lunch, and co-curricular rows; those stay off the sheet.
-- Run read-only (BigQuery MCP); hand the result to c3/academic ops.
select
    enr.courses_course_number,

    any_value(enr.courses_course_name) as course_name,
    any_value(enr.courses_credittype) as credittype,
    count(distinct enr.students_student_number) as n_students,
from `teamster-332318`.kipptaf_powerschool.base_powerschool__course_enrollments as enr
-- trunk-ignore(sqlfluff/ST11): anti-join by design; cw is the exclusion probe
left join
    -- trunk-ignore(sqlfluff/LT05): one fully-qualified relation name
    `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__assessments__course_subject_crosswalk
    as cw
    on enr.courses_course_number = cw.powerschool_course_number
where
    enr.cc_academic_year = 2026
    and not enr.is_dropped_section
    and cw.powerschool_course_number is null
group by enr.courses_course_number
order by n_students desc
