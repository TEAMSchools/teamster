-- Rationale lives in this test's tests/properties.yml description.
-- Any returned row is a failure.
with
    enrollments as (
        select
            cc_studyear,
            cc_course_number,
            cc_studentid,
            cc_dateenrolled,
            cc_dateleft,

            lag(cc_dateleft) over (
                partition by cc_studyear, cc_course_number
                order by cc_dateenrolled, cc_dateleft
            ) as prev_dateleft,
        from {{ ref("base_powerschool__course_enrollments") }}
        where not is_dropped_section
    )

select
    cc_studyear,
    cc_course_number,
    cc_studentid,
    cc_dateenrolled,
    cc_dateleft,
    prev_dateleft,
from enrollments
where cc_dateenrolled < prev_dateleft
