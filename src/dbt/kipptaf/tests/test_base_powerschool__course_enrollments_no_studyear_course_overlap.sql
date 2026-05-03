/* Within a (student, year, course) — `cc_studyear` is PowerSchool's composite
   student+year identifier — consecutive enrollment rows must not have date
   ranges that overlap by more than one day. A single shared boundary day (one
   row's `cc_dateleft` = next row's `cc_dateenrolled`) is a normal sequential
   transfer and is allowed; multi-day overlap is a source-side defect that
   causes scaffold's date-between join to fan out an admin to multiple schools.
   Severity warn + store_failures inherit from project defaults. */
with
    enrollments as (
        select
            _dbt_source_relation,
            cc_studyear,
            cc_course_number,
            cc_studentid,
            cc_dateenrolled,
            cc_dateleft,
            lag(cc_dateleft) over (
                partition by _dbt_source_relation, cc_studyear, cc_course_number
                order by cc_dateenrolled, cc_dateleft
            ) as prev_dateleft,
        from {{ ref("base_powerschool__course_enrollments") }}
    )

select
    _dbt_source_relation,
    cc_studyear,
    cc_course_number,
    cc_studentid,
    cc_dateenrolled,
    cc_dateleft,
    prev_dateleft,
from enrollments
where cc_dateenrolled < prev_dateleft
