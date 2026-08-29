-- Within a (student, year, course) -- cc_studyear is PowerSchool's composite
-- student-and-year identifier -- consecutive enrollment rows must not have date
-- ranges that overlap by more than one day. A single shared boundary day (one
-- row's cc_dateleft equal to the next row's cc_dateenrolled) is a normal
-- sequential transfer and is allowed; multi-day overlap is a source-side defect
-- that fans out date-range joins.
--
-- Lives in the package, not kipptaf: this asserts PowerSchool source quality,
-- and each district project holds one district, so no _dbt_source_relation
-- partition key is needed. The package's own base_powerschool__course_enrollments
-- already windows is_dropped_course on exactly (cc_studyear, cc_course_number).
--
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
